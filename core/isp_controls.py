"""ISP300 控件自动化: 通过 pywinauto 的 UIA 后端枚举 / 查找 / 点击控件。

相比屏幕坐标定位, 控件定位按 control_type / title / automation_id 匹配,
对窗口移动、缩放更鲁棒。pywinauto 按需(函数内)导入, 不影响无 ISP300 的场景。

优化(v3):
- find_isp_window 增加"最近窗口"缓存并每次验活(exists), 避免每个控件点击都全桌面枚举;
- find_control / enumerate_controls 加递归深度上限与遍历预算, 防 UIA 树过深卡死;
- click_control 提供 UIA 原生 left / right / double 点击。
"""
import time
from typing import Dict, List, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)

# 需要枚举 / 可点击的控件类型
INTERESTING_CONTROL_TYPES = (
    "Button", "ComboBox", "Edit", "CheckBox", "RadioButton",
    "TabItem", "ListItem", "MenuItem",
)

# ISP300 主窗口标题关键字(标题中含 "I.S.P" 即视为目标窗口)
ISP_WINDOW_TITLE_KEY = "I.S.P"

# 递归安全上限: 防异常窗口树过深导致遍历卡死
MAX_DEPTH = 16
# 单次遍历最多访问的元素数(预算保护)
MAX_VISITS = 4000

# 最近一次命中的窗口(缓存, 使用前校验 exists 防失效)
_cached_window = None


def _desktop():
    from pywinauto import Desktop

    return Desktop(backend="uia")


def _walk(window, visit):
    """带深度与访问预算的 UIA 树遍历; visit(elem) 返回 True 表示命中即停止。"""
    budget = {"used": 0}

    def rec(elem, depth):
        if budget["used"] >= MAX_VISITS or depth > MAX_DEPTH:
            return None
        budget["used"] += 1
        if visit(elem):
            return elem
        try:
            children = elem.children()
        except Exception:
            return None
        for child in children:
            found = rec(child, depth + 1)
            if found is not None:
                return found
        return None

    return rec(window, 0)


def _window_alive(wrapper) -> bool:
    """判断窗口 wrapper 是否仍有效。

    注意: UIA 后端的 wrapper 没有 .exists() 属性(实测会抛 AttributeError),
    用 is_visible() 做验活 —— 窗口销毁时该调用抛异常即视为失效。
    """
    try:
        return bool(wrapper.is_visible())
    except Exception:
        return False


def find_isp_window(use_cache: bool = True):
    """查找 ISP300 主窗口(UIA 元素), 找不到返回 None。带最近窗口缓存(每次验活)。"""
    global _cached_window
    if use_cache and _cached_window is not None:
        if _window_alive(_cached_window):
            return _cached_window
        _cached_window = None

    try:
        desktop = _desktop()
        for w in desktop.windows():
            try:
                if ISP_WINDOW_TITLE_KEY in (w.window_text() or ""):
                    _cached_window = w
                    return w
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"查找 ISP300 窗口失败: {e}")
    return None


def _describe(elem) -> Dict[str, str]:
    def _safe(getter):
        try:
            return getter() or ""
        except Exception:
            return ""

    return {
        "control_type": _safe(lambda: elem.element_info.control_type),
        "title": _safe(elem.window_text),
        "auto_id": _safe(lambda: elem.element_info.automation_id),
    }


def enumerate_controls(window=None, use_cache: bool = True) -> List[Dict[str, str]]:
    """枚举窗口内可用控件, 返回 [{control_type, title, auto_id}, ...]。"""
    if window is None:
        window = find_isp_window(use_cache=use_cache)
    if window is None:
        return []

    results: List[Dict[str, str]] = []

    def visit(elem) -> bool:
        desc = _describe(elem)
        if (
            desc["control_type"] in INTERESTING_CONTROL_TYPES
            and (desc["title"] or desc["auto_id"])
        ):
            results.append(desc)
        return False  # 永远继续遍历(枚举不需要提前命中)

    try:
        _walk(window, visit)
    except Exception as e:
        logger.warning(f"枚举 ISP300 控件失败: {e}")
    return results


def find_control(
    window,
    control_type: Optional[str] = None,
    title: Optional[str] = None,
    auto_id: Optional[str] = None,
):
    """在窗口内查找第一个匹配控件, 返回 UIA 元素或 None。"""
    if not (control_type or title or auto_id):
        return None

    def matches(desc: Dict[str, str]) -> bool:
        if control_type and desc["control_type"] != control_type:
            return False
        if title and desc["title"] != title:
            return False
        if auto_id and desc["auto_id"] != auto_id:
            return False
        return True

    def visit(elem) -> bool:
        return matches(_describe(elem))

    try:
        return _walk(window, visit)
    except Exception as e:
        logger.warning(f"查找 ISP300 控件失败: {e}")
        return None


def _rect_on_visible_screen(rect) -> bool:
    """判断元素中心是否落在某个可见显示器范围内。

    实测: WinForms 窗口最小化/未布局时, UIA 里元素仍"存在且 is_visible()=True",
    但 rectangle() 返回负数(如 L-47538) —— click_input 会把鼠标点到屏幕外,
    界面毫无反应。因此点击前必须先做屏幕内校验, 离屏视为"未就绪"进入重试。
    """
    try:
        import ctypes

        user32 = ctypes.windll.user32
        vs_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        vs_y = user32.GetSystemMetrics(77)
        vs_cx = user32.GetSystemMetrics(78)
        vs_cy = user32.GetSystemMetrics(79)
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        return vs_x <= cx <= vs_x + vs_cx and vs_y <= cy <= vs_y + vs_cy
    except Exception:
        return True  # 查询失败时不拦(交给点击本身报错)


def _restore_if_iconic(hwnd_text_wrapper) -> bool:
    """若目标窗口处于最小化则恢复(SW_RESTORE); 返回是否执行了恢复。"""
    try:
        import ctypes

        wrapper = hwnd_text_wrapper
        handle = wrapper.handle  # pywinauto wrapper 的窗口句柄
        user32 = ctypes.windll.user32
        if user32.IsIconic(handle):
            user32.ShowWindow(handle, 9)  # SW_RESTORE
            time.sleep(0.4)
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------- #
# ListItem 行号定位(修复"[18]"类失败)
#
# 根因: 设备列表行的标题随内容实时变化 —— 录制时空槽行标题是纯数字(如 "18"),
# 执行 Read I.S.P / LOAD 后同一行可能已被设备占用, 标题变成
# " 18 <device> <freq> <file> ..."(行首还有空格), 按"标题精确匹配"必然失配。
# 方案: 纯数字标题(ListItem 且无 auto_id)不再匹配文本, 而是解释为"该列表中的
# 行号"(1-based, 与设备槽位号一致) —— 枚举当前全部 ListItem 后按行号取元素,
# select() + click_input() 由控件自身保证滚动到可见区, 与行内容是否刷新无关。
# ---------------------------------------------------------------------- #
def row_number_from_title(title: Optional[str]) -> Optional[int]:
    """纯数字标题 -> 行号(>=1); 非纯数字/空/0 -> None(走普通精确匹配)。

    兼容历史配置: 早期空槽位行的 title 可能以 int 存储(如 18 而非 "18"),
    统一先转 str 再判断, 避免 'int' object has no attribute 'strip'。
    """
    if title is None:
        return None
    text = str(title).strip()
    if text.isdigit():
        n = int(text)
        if n >= 1:
            return n
    return None


def _list_item_rows(window) -> List[object]:
    """收集窗口内的 ListItem 行(按 UI 顺序)。

    优先: 找 List/ListView/ListBox 容器, 取各容器下的 ListItem(设备列表行次序
    与容器内子元素次序一致 = 槽位号次序); 找不到容器时退化为整窗文档序遍历。
    任何异常都返回空列表(不抛)。
    """
    containers: List[object] = []

    def find_containers(elem) -> bool:
        try:
            if _describe(elem).get("control_type") in ("List", "ListView", "ListBox"):
                containers.append(elem)
        except Exception:
            pass
        return False  # 继续遍历, 收集所有列表容器

    try:
        _walk(window, find_containers)
    except Exception:
        containers = []

    if containers:
        rows: List[object] = []
        for c in containers:
            try:
                for child in c.children(control_type="ListItem"):
                    rows.append(child)
            except Exception:
                continue
        if rows:
            return rows

    # 兜底: 整窗按文档序收集 ListItem
    rows = []
    try:
        def collect_all(elem) -> bool:
            if _describe(elem).get("control_type") == "ListItem":
                rows.append(elem)
            return False  # 继续遍历

        _walk(window, collect_all)
    except Exception:
        pass
    return rows


def _click_list_item_row(window, row_index: int, button: str) -> Tuple[bool, str]:
    """按行号点击列表第 row_index 行(1-based)。返回 (ok, 原因)。"""
    rows = _list_item_rows(window)
    if not rows:
        return False, "列表当前为空(未枚举到任何 ListItem 行, 可能尚未加载完成)"
    if row_index < 1 or row_index > len(rows):
        return False, (
            f"行号 {row_index} 超出当前列表范围(当前共枚举到 {len(rows)} 行)"
        )
    elem = rows[row_index - 1]
    try:
        # 若窗口最小化导致离屏, 尝试恢复(由外层重试循环兜底)
        try:
            rect = elem.rectangle()
            if not _rect_on_visible_screen(rect):
                _restore_if_iconic(window)
        except Exception:
            pass
        # UIA ListItem 支持 SelectionItemPattern 时 select() 可精准选中并自动
        # 滚动到可见; 不支持(抛异常)则退化为直接点击
        try:
            elem.select()
            time.sleep(0.15)
        except Exception:
            pass
        rect = elem.rectangle()
        if not _rect_on_visible_screen(rect):
            return False, f"第 {row_index} 行位于屏幕外({rect}), 未能点击"
        if button == "right":
            elem.right_click_input()
        elif button == "double":
            elem.double_click_input()
        else:
            elem.click_input()
        return True, ""
    except Exception as e:
        return False, f"点击第 {row_index} 行失败: {e}"


def _dump_list_rows(window) -> None:
    """诊断用: 把列表当前所有行(行号 + 标题 repr)打进日志, 便于定位失配原因。"""
    rows = _list_item_rows(window)
    if not rows:
        logger.warning("ISP300 列表当前为空(未枚举到任何 ListItem 行)")
        return
    parts = [
        f"{i}:{_describe(el).get('title')!r}" for i, el in enumerate(rows, 1)
    ]
    logger.warning(f"ISP300 列表当前共 {len(rows)} 行 -> " + " | ".join(parts))


def click_control(
    control_type: Optional[str] = None,
    title: Optional[str] = None,
    auto_id: Optional[str] = None,
    button: str = "left",
    retries: int = 3,
    retry_delay: float = 1.0,
) -> bool:
    """点击指定控件(button: left / right / double), 成功返回 True。

    v3.4 健壮性修复(针对真机"控件已加载却点击无反应"):
    - 就绪自动重试: 目标软件刚处理完上一步(如加载文件)时, 控件可能尚未进入
      UIA 树, 或窗口处于最小化/未布局使元素 rect 变成屏幕外负坐标 ——
      这种状态下 click_input 会把鼠标点到屏幕外, 界面毫无反应。
      每轮都重新找窗口与控件, 点击前校验元素在可视屏幕内(离屏则尝试恢复窗口
      后进入下一轮重试)。
    - 精确失败原因: 未找到窗口 / 未找到控件 / 控件在屏幕外 / 点击失败(含异常)。

    v3.5(修复"控件[18]仍失败"): ListItem 且标题为纯数字(录制时的空槽位行,
    如 "18")不再按标题文本匹配 —— 列表行内容随 Read I.S.P / LOAD 刷新后会变
    (空槽被设备占用后标题变为 " 18 <device> ..."), 改为解释为"列表行号"按
    位置定位, select() + click_input() 与行内容无关; 最终失败时 dump 列表当前
    全部行(标题 repr)到日志, 供定位失配/滚动问题。
    """
    # 定位参数统一转字符串: 历史配置里空槽位行的 title 可能是 int(如 18),
    # 字符串匹配(==)与后续 .strip() 都会因此失配/崩溃。None 表示"不过滤", 保持原义。
    if control_type is not None:
        control_type = str(control_type)
    if title is not None:
        title = str(title)
    if auto_id is not None:
        auto_id = str(auto_id)

    locator = f"type={control_type!r} title={title!r} auto_id={auto_id!r}"
    attempts = max(1, retries)
    last_reason = ""
    last_window = None
    # 纯数字标题的 ListItem(且无 auto_id) -> 解释为"列表行号"定位,
    # 与行内容刷新无关(修复录制时空槽 "18" 在执行时被设备占用的失配)
    row_index = None
    if control_type == "ListItem" and not auto_id:
        row_index = row_number_from_title(title)
    for attempt in range(1, attempts + 1):
        window = find_isp_window()
        if window is None:
            last_reason = "未找到 ISP300 窗口(请确认软件已打开)"
        else:
            last_window = window
            if row_index is not None:
                ok, reason = _click_list_item_row(window, row_index, button)
                if ok:
                    logger.debug(
                        f"已点击控件: type={control_type} 按行号第 {row_index} 行"
                        f"(录制标题 {title!r}) button={button}(第 {attempt} 次尝试)"
                    )
                    return True
                last_reason = f"按行号第 {row_index} 行点击失败: {reason}"
            else:
                elem = find_control(window, control_type, title, auto_id)
                if elem is None:
                    last_reason = "未找到控件(可能尚未加载完成)"
                else:
                    try:
                        rect = elem.rectangle()
                        if not _rect_on_visible_screen(rect):
                            # 离屏通常意味着窗口最小化/未布局: 尝试恢复, 留待下轮重试
                            restored = _restore_if_iconic(window)
                            last_reason = (
                                f"控件位于屏幕外({rect})"
                                + (" -> 已尝试恢复窗口" if restored else "")
                            )
                        else:
                            if button == "right":
                                elem.right_click_input()
                            elif button == "double":
                                elem.double_click_input()
                            else:
                                elem.click_input()
                            logger.debug(
                                f"已点击控件: type={control_type} title={title} "
                                f"auto_id={auto_id} button={button}(第 {attempt} 次尝试)"
                            )
                            return True
                    except Exception as e:
                        last_reason = f"找到控件但点击失败: {e}"
        if attempt < attempts:
            logger.debug(
                f"点击控件第 {attempt}/{attempts} 次失败({last_reason}), "
                f"{retry_delay}s 后重试"
            )
            time.sleep(max(0.0, retry_delay))

    logger.warning(f"点击控件最终失败(已重试 {retries} 次) {locator}: {last_reason}")
    # ListItem 失败时 dump 列表当前行, 给下一次诊断留证据(空槽/占用/滚动一目了然)
    if control_type == "ListItem" and last_window is not None:
        try:
            _dump_list_rows(last_window)
        except Exception:
            pass
    return False
