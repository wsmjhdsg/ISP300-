"""烧录结果弹窗监控 —— waitresult 步骤的执行载体。

背景: ISP300 烧录完成会弹出结果弹窗(标题/正文含 "COMPLETE"、"Verify OK"、
按钮 "确定")。waitresult 步骤 = 轮询结果弹窗 -> 读正文 -> 含 "Verify OK"
判 OK -> **自动点"确定"关窗(判定与确认一体)**; 内容非 OK(如 Verify NG)
或超时未收到 -> 判失败, 上层"失败即中止"随即停止后续步骤(满足
"OK 就继续 / NG 就停止")。超时未收到也判失败 —— 用户明确无需识别失败文案,
"没收到就是失败"(宁严勿松, 防把未烧录当成功)。

第一性策略:
- 定位**不依赖标题栏文字**: 先按标题精确匹配(COMPLETE); 标题匹配不到时,
  限定在 ISP300 进程内按正文关键词 "Verify OK" 兜底定位 —— 兼容自绘
  无标题栏/标题不同的弹窗(真机实测标题匹配会漏, 弹窗在屏却 120s 识别不到)。
- 关窗**不依赖匹配到的窗口就是弹窗**: 候选可能先命中主窗口(弹窗内嵌其
  UIA 树) —— 逐个候选递归找"确定/OK"按钮点击, 直到候选消失(≤4s 尽力)。
- 判定只看正文是否含 "verify ok"(小写折叠); NG/超时一律失败并由上层停止。
- 后台线程可安全调用: 入口复用 file_dialog._coinit 的幂等 COM 保护;
  轮询循环每轮检查 stop_check, ESC/停止按钮可即时中断, 不阻塞会话收尾。

对外 API: wait_burn_result(timeout, poll, stop_check) -> (ok, message)
"""
from __future__ import annotations

import re
import time
from typing import Callable, Optional, Tuple

from core.constants import SimulatorConfig
from core.file_dialog import _coinit
from core.logger import get_logger

logger = get_logger(__name__)

# 目标弹窗标题(精确匹配; 大小写不敏感)
RESULT_TITLE = "COMPLETE"
# 正文成功标志(小写折叠后包含即成功)
OK_MARKER = "verify ok"
# 关窗按钮文本候选(归一化后精确匹配; 支持 '确定(O)' / 'OK(&O)' 等加速键形式)
CLOSE_TEXT_MARKERS: tuple = ("确定", "ok")
# 旧版 child_window 标题正则(向后兼容)
CLOSE_BUTTON_TITLES = ("确定", "OK")

# 正文收集的递归深度/访问预算(防 UIA 树过深)
_MAX_TEXT_DEPTH = 8
_MAX_TEXT_VISITS = 300


# ---------------------------------------------------------------------- #
# 纯函数(便于单测, 无 GUI 依赖)
# ---------------------------------------------------------------------- #
def is_result_title(title: Optional[str]) -> bool:
    """是否为目标"烧录完成"弹窗标题。"""
    text = (title or "").strip()
    return text.lower() == RESULT_TITLE.lower()


def body_is_ok(body: Optional[str]) -> bool:
    """正文是否表示烧录成功(含 'verify ok', 大小写不敏感)。"""
    return OK_MARKER in (body or "").lower()


# ---------------------------------------------------------------------- #
# UIA 弹窗查找 / 正文读取 / 关窗(均为尽力而为, 异常吸收)
# ---------------------------------------------------------------------- #
def _is_button_like(elem) -> bool:
    try:
        ctype = (elem.element_info.control_type or "").lower()
    except Exception:
        ctype = ""
    try:
        cls = (elem.class_name() or "").lower()
    except Exception:
        cls = ""
    return ctype in ("button", "menuitem", "tabitem", "hyperlink") or "button" in cls


def _collect_body_texts(elem, depth: int, budget: dict, out: list) -> None:
    """收集元素子树内非按钮控件的可见文本(标题之外的正文)。"""
    if depth > _MAX_TEXT_DEPTH or budget["used"] >= _MAX_TEXT_VISITS:
        return
    budget["used"] += 1
    try:
        text = (elem.window_text() or "").strip()
    except Exception:
        text = ""
    if text and not _is_button_like(elem):
        out.append(text)
    try:
        children = elem.children()
    except Exception:
        return
    for child in children:
        _collect_body_texts(child, depth + 1, budget, out)


def _dialog_body_text(dialog) -> str:
    """读取弹窗正文(拼接各非按钮子元素文本; 失败返回空串)。"""
    try:
        out: list = []
        _collect_body_texts(dialog, 0, {"used": 0}, out)
        return " ".join(t for t in out if t)
    except Exception:
        return ""


def _looks_like_ok_button(text: Optional[str]) -> bool:
    """按钮文本是否表示'确定/OK'(归一化后精确匹配, 兼容 '确定(&O)' / 'OK(&O)')。"""
    norm = _normalize_btn(text)
    return norm in CLOSE_TEXT_MARKERS


def _normalize_btn(text: Optional[str]) -> str:
    """归一化按钮文本: 去尾括号加速键、空格、小写。

    例: '确定(O)' -> '确定', 'OK(&O)' -> 'ok', '  OK  ' -> 'ok'
    """
    if not text:
        return ""
    cleaned = re.sub(r"\(.*\)$", "", str(text)).strip()
    return cleaned.lower()


def _find_text_element(window, marker: str, depth: int = 0, budget: Optional[dict] = None):
    """递归在窗口子树内找文本归一化后 == marker 的元素, 返回元素或 None。

    与 _find_ok_button 的区别: 本函数**不限制控件类型**, 用于兜底——
    当"确定/OK"是某个 Static 文本(非 UIA Button 控件)时, 仍能定位到,
    配合 pyautogui 坐标点击可触发关闭(兼容自绘/无标头栏弹窗)。
    """
    norm_marker = _normalize_btn(marker)
    if not norm_marker:
        return None
    if budget is None:
        budget = {"used": 0}
    if depth > _MAX_TEXT_DEPTH or budget["used"] >= _MAX_TEXT_VISITS:
        return None
    budget["used"] += 1
    try:
        if _normalize_btn(window.window_text()) == norm_marker:
            return window
    except Exception:
        pass
    try:
        children = window.children()
    except Exception:
        return None
    for child in children:
        found = _find_text_element(child, marker, depth + 1, budget)
        if found is not None:
            return found
    return None


def _find_ok_button(window, depth: int = 0, budget: Optional[dict] = None):
    """递归在窗口子树内找文本为 确定/OK 的可点击按钮, 返回元素或 None。"""
    if budget is None:
        budget = {"used": 0}
    if depth > _MAX_TEXT_DEPTH or budget["used"] >= _MAX_TEXT_VISITS:
        return None
    budget["used"] += 1
    try:
        if _is_button_like(window) and _looks_like_ok_button(window.window_text()):
            return window
    except Exception:
        pass
    try:
        children = window.children()
    except Exception:
        return None
    for child in children:
        found = _find_ok_button(child, depth + 1, budget)
        if found is not None:
            return found
    return None


def _close_dialog(dialog) -> bool:
    """点弹窗内'确定/OK'以关闭。优先级: ①UIA Button 控件 ②文本'确定/OK' 坐标点击 ③回车。"""
    # ① UIA Button 控件(标准对话框)
    btn = None
    try:
        btn = _find_ok_button(dialog)
    except Exception:
        btn = None
    if btn is not None:
        try:
            btn.wait("enabled", timeout=1.5)
            btn.click_input()
            return True
        except Exception:
            pass
    # 兼容老逻辑: child_window 直查
    for title in CLOSE_BUTTON_TITLES:
        try:
            b = dialog.child_window(control_type="Button", title_re=f".*{title}.*")
            b.wait("enabled", timeout=0.5)
            b.click_input()
            return True
        except Exception:
            continue
    # ② 兜底: 找"确定"或"OK"文本元素, 用 pyautogui 在其中心点点击
    # (修复: 弹窗是主窗口内嵌子面板时, 控件类型不是 Button, UIA 点击无效,
    # 但鼠标点屏幕坐标仍可触发弹窗的命中测试并关闭)
    for marker in CLOSE_TEXT_MARKERS:
        elem = None
        try:
            elem = _find_text_element(dialog, marker)
        except Exception:
            elem = None
        if elem is None:
            continue
        try:
            rect = elem.rectangle()
        except Exception:
            rect = None
        if rect is None or rect.width() <= 0 or rect.height() <= 0:
            continue
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        try:
            import pyautogui  # 延迟导入(可能未安装时退化为回车)

            pyautogui.click(cx, cy)
            logger.debug(f"结果弹窗点确定(坐标点击): marker={marker!r} ({cx},{cy})")
            return True
        except Exception as e:
            logger.debug(f"pyautogui 点击 {marker!r} 失败: {e}")
    # ③ 终极兜底: 回车(标准对话框默认按钮)
    try:
        dialog.type_keys("{ENTER}", set_foreground=False)
        time.sleep(0.3)
        dialog.type_keys("{ENTER}")
        return True
    except Exception:
        return False


def _window_contains_marker(window, marker: str) -> bool:
    """判断某顶层窗口子树内是否出现目标文本(小写折叠, 预算保护)。

    用途: 有些工控弹窗是自绘无标题栏(或标题栏非 "COMPLETE"),
    窗口里的大字 "COMPLETE"/"Verify OK" 其实是子 Static 文本 —— 只按标题
    匹配永远认不出。此函数用于"标题匹配失败后按正文关键词兜底定位"。
    """
    low = (marker or "").lower()
    if not low:
        return False
    budget = {"used": 0}
    found = False

    def rec(elem, depth: int) -> None:
        nonlocal found
        if found or depth > _MAX_TEXT_DEPTH or budget["used"] >= _MAX_TEXT_VISITS:
            return
        budget["used"] += 1
        try:
            if low in (elem.window_text() or "").lower():
                found = True
                return
        except Exception:
            pass
        try:
            children = elem.children()
        except Exception:
            return
        for child in children:
            rec(child, depth + 1)

    try:
        rec(window, 0)
    except Exception:
        pass
    return found


def _isp_process_id() -> Optional[int]:
    """取 ISP300 主窗口所在进程 PID(用于把弹窗候选限制在本程序内)。

    找不到 ISP300 窗口(如软件已关闭)返回 None, 此时降级为全桌面标题匹配。
    """
    try:
        from core.isp_controls import find_isp_window

        window = find_isp_window()
        if window is not None:
            pid = window.process_id()
            return int(pid) if pid else None
    except Exception:
        pass
    return None


def _visible_result_windows() -> list:
    """返回当前桌面上的"结果弹窗"候选(按优先级排序)。

    优先级: ①标题栏精确 = COMPLETE 的顶层窗口;
            ②ISP300 进程内、子树含 "Verify OK" 的顶层窗口(兼容自绘无标题栏);
            ③找不到 ISP 主窗口时, 仅限系统经典对话框(#32770)里含该文本者。
    限定进程/类名是为了不把全桌面窗口都递归扫一遍(避免高 CPU 与误判)。
    """
    out: list = []
    try:
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        visible = []
        for w in desktop.windows():
            try:
                if w.is_visible():
                    visible.append(w)
            except Exception:
                continue

        for w in visible:
            try:
                if is_result_title(w.window_text()):
                    out.append(w)
            except Exception:
                continue

        pid = _isp_process_id()
        for w in visible:
            if any(w is seen for seen in out):
                continue
            try:
                if pid is not None:
                    if int(w.process_id()) == pid and _window_contains_marker(
                        w, OK_MARKER
                    ):
                        out.append(w)
                else:
                    cls = (w.class_name() or "").lower()
                    if "32770" in cls and _window_contains_marker(w, OK_MARKER):
                        out.append(w)
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"枚举结果弹窗失败: {e}")
    return out


def _find_result_dialog():
    """返回第一个候选结果弹窗(不存在则 None)。"""
    try:
        windows = _visible_result_windows()
        return windows[0] if windows else None
    except Exception:
        return None


def _dismiss_result_dialog(timeout: float = 4.0) -> None:
    """判定结束后尽力点掉结果弹窗, 并确认其消失(不影响判定结果)。

    修复真机"判定成功却没点掉确定": 候选可能先命中主窗口而不是弹窗本身,
    因此按候选列表逐个尝试点'确定/OK', 直到所有候选消失或超时 —— 无论弹窗
    是独立顶层窗口还是内嵌在主窗口 UIA 树里, 都能被关掉。
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        windows = _visible_result_windows()
        if not windows:
            return
        clicked = False
        for w in windows:
            try:
                if _close_dialog(w):
                    clicked = True
            except Exception:
                continue
        time.sleep(0.35)  # 等待点击生效 / 窗口关闭动画
    logger.debug("结果弹窗未在限时内确认关闭(不影响判定结果)")


# ---------------------------------------------------------------------- #
# 对外主入口
# ---------------------------------------------------------------------- #
def wait_burn_result(
    timeout: Optional[float] = None,
    poll: Optional[float] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str]:
    """轮询烧录完成弹窗, 返回 (ok, message)。

    - 收到标题 COMPLETE 且正文含 Verify OK -> 自动关窗, 返回 (True, 摘要)。
    - 收到 COMPLETE 但正文不含 OK / 超时未收到 -> 返回 (False, 原因)(按失败)。
    - stop_check() 返回 True 时提前退出(用户停止)。
    """
    timeout = SimulatorConfig.RESULT_TIMEOUT if timeout is None else max(0.0, float(timeout))
    poll = SimulatorConfig.RESULT_POLL if poll is None else max(0.05, float(poll))

    _coinit()
    deadline = time.monotonic() + timeout
    while True:
        if stop_check is not None:
            try:
                if stop_check():
                    return False, "用户已请求停止, 未完成烧录结果判定"
            except Exception:
                pass

        dialog = _find_result_dialog()
        if dialog is not None:
            body = _dialog_body_text(dialog)
            shown = (body or "").strip()[:120]
            ok = body_is_ok(body)
            # 判定与关窗一体: 无论 OK / NG 都尽力点掉弹窗的"确定"(OK=确认关闭,
            # NG=关掉残局), 之后才返回 —— 上层把"返回 False"视为失败并(默认)中止
            # 后续步骤, 正好满足"OK 继续 / NG 停止"。
            _dismiss_result_dialog()
            if ok:
                return True, "烧录结果判定: OK(Verify OK) —— 已自动点击'确定'关闭弹窗"
            return False, (
                f"烧录结果判定: 非 OK(内容: {shown!r}) —— 已关闭弹窗, 按失败中止后续步骤"
            )

        if time.monotonic() >= deadline:
            return (
                False,
                f"等待烧录完成弹窗超时({timeout:.0f}s): 未收到结果弹窗, 按失败中止后续步骤",
            )
        time.sleep(max(0.0, poll))
