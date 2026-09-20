"""自动填充系统"打开文件"对话框 —— openfile 步骤的执行载体。

背景: ISP300 等工控软件通过系统标准对话框选固件(.i3s), 人工操作 = 点开按钮 ->
在弹出的"打开"对话框里输路径/选文件 -> 点"打开(O)"。openfile 步骤把这段变成
"程序自动填路径并确认"。

第一性策略:
- 系统打开对话框分两类: 老式 GetOpenFileName(窗口类 #32770 + Win32 标准控件,
  文件名框 control id=1148, "打开"按钮 id=1) 与 Vista+ 的 IFileOpenDialog
  (DirectUI 子结构, 靠 UIA 控件名定位)。两者控件结构差异大且无法在本机模拟,
  因此不赌单一结构, 采用"多后端(UIA/win32) + 多候选定位器 + 写入后文本校验 +
  找不到按钮时回车兜底"的组合式填充, 任一环节命中即成功。
- 本模块可被后台执行线程调用: pywinauto 的 UIA 后端依赖线程 COM 初始化,
  入口处做幂等 CoInitialize 保护, 避免 COM 未初始化导致崩溃。

对外 API:
- find_latest_file(dir, pattern): 目录内 mtime 最新的匹配文件(供 latest 模式)。
- resolve_pick_steps(steps, asker): 把 pick 模式解析成固定路径(供主线程预解析)。
- fill_open_dialog(path, ...): 等对话框出现 -> 填路径 -> 确认, 返回 (ok, message)。
"""
from __future__ import annotations

import fnmatch
import os
import time
from typing import Callable, Dict, List, Optional, Tuple

from core.constants import OpenFileModes, SimulatorConfig, StepTypes
from core.logger import get_logger

logger = get_logger(__name__)

# 目标对话框标题(精确匹配; 中文系统为"打开", 保留常见英文/变体以兼容)
DIALOG_TITLES = ("打开", "打开文件", "Open", "Open File")
# 老式对话框"文件名(N):"编辑框的经典 control id (0x047C)
CLASSIC_FILENAME_EDIT_ID = 1148
# 打开对话框中的"打开(O)"按钮 control id (IDOK)
CLASSIC_OK_BUTTON_ID = 1
# 默认文件名匹配模式(固件)
DEFAULT_PATTERN = "*.i3s"
# 每轮填充尝试的内部等待(秒)
_CTRL_TIMEOUT = 1.5


# ---------------------------------------------------------------------- #
# 纯函数: 目录内最新文件 / pick 预解析(便于单测, 无 GUI/COM 依赖)
# ---------------------------------------------------------------------- #
def find_latest_file(directory: str, pattern: str = DEFAULT_PATTERN) -> Optional[str]:
    """返回目录下修改时间最新的匹配文件路径; 无匹配/目录无效/异常返回 None。

    大小写不敏感匹配(Windows 语义), 只扫描该层、忽略子目录与失败项。
    """
    directory = (directory or "").strip()
    pattern = (pattern or DEFAULT_PATTERN).strip() or DEFAULT_PATTERN
    if not os.path.isdir(directory):
        return None
    lowered = pattern.lower()
    latest_path: Optional[str] = None
    latest_mtime = -1.0
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if not entry.is_file():
                        continue
                except OSError:
                    continue
                if not fnmatch.fnmatch(entry.name.lower(), lowered):
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_path = entry.path
    except OSError:
        return None
    return latest_path


def resolve_pick_steps(
    steps: List[dict],
    asker: Callable[[str], Optional[str]],
) -> Optional[List[dict]]:
    """把 steps 中 mode=pick 的 openfile 步骤解析为固定路径步骤(浅拷贝, 不改原列表)。

    asker(prompt) -> Optional[str]: 由调用方注入"主线程文件选择器"(Tk 非线程安全,
    因此必须在主线程预解析, 执行线程只见解析结果)。
    任一次选择被取消 -> 返回 None, 表示调用方应中止本次执行。
    非 dict / 非法步骤原样保留, 交由校验层处理。
    """
    resolved: List[dict] = []
    for index, step in enumerate(steps):
        if (
            isinstance(step, dict)
            and step.get("type") == StepTypes.OPENFILE
            and (step.get("mode") or OpenFileModes.PATH) == OpenFileModes.PICK
        ):
            path = asker(f"请选择第 {index + 1} 步要打开的固件文件")
            if not path:
                return None
            new_step = dict(step)
            new_step["mode"] = OpenFileModes.PATH
            new_step["path"] = path
            resolved.append(new_step)
        else:
            resolved.append(dict(step) if isinstance(step, dict) else step)
    return resolved


# ---------------------------------------------------------------------- #
# 线程 COM 初始化(pywinauto UIA 后端要求)
# ---------------------------------------------------------------------- #
def _coinit() -> None:
    try:
        import comtypes

        comtypes.CoInitialize()
    except Exception:
        pass  # 已初始化或不可用时忽略; win32 后端不依赖 COM


# ---------------------------------------------------------------------- #
# 对话框查找(先 UIA 后 win32, 均延迟导入 pywinauto)
# ---------------------------------------------------------------------- #
def _is_visible(w) -> bool:
    try:
        return bool(w.is_visible())
    except Exception:
        return True  # 查询失败时按可见处理, 避免漏掉


def _title_is_target(title: str) -> bool:
    text = (title or "").strip()
    if not text:
        return False
    lowered = text.lower()
    return any(d.lower() == lowered for d in DIALOG_TITLES)


def _find_by_backend(backend: str):
    from pywinauto import Desktop

    desktop = Desktop(backend=backend)
    for w in desktop.windows():
        try:
            if _is_visible(w) and _title_is_target(w.window_text()):
                # 老式对话框一定是 #32770; 新式(DirectUI)放宽为类名含 Dialog
                cls = ""
                try:
                    cls = w.class_name() or ""
                except Exception:
                    pass
                if backend == "win32" and cls and cls != "#32770":
                    continue
                if backend == "uia" and cls and "#32770" not in cls and "dialog" not in cls.lower():
                    continue
                return w
        except Exception:
            continue
    return None


def _find_dialog() -> Tuple[Optional[str], object]:
    """返回 (backend, wrapper); 找不到返回 (None, None)。"""
    _coinit()
    for backend in ("uia", "win32"):
        try:
            w = _find_by_backend(backend)
        except Exception:
            w = None
        if w is not None:
            return backend, w
    return None, None


# ---------------------------------------------------------------------- #
# 填路径(写入后校验文本一致), 分 UIA / win32 两条实现
# ---------------------------------------------------------------------- #
def _edit_text(wrapper) -> str:
    """读取编辑框当前文本(UIA 优先 ValuePattern, win32 直接取文本)。"""
    try:
        getter = getattr(wrapper, "get_value", None)
        if getter:
            return getter() or ""
    except Exception:
        pass
    try:
        return wrapper.window_text() or ""
    except Exception:
        return ""


def _set_edit_text(wrapper, path: str) -> bool:
    """写入路径并校验; 校验不一致返回 False(会触发上层换候选/重试)。"""
    try:
        if hasattr(wrapper, "set_edit_text"):
            wrapper.set_edit_text(path)
        elif hasattr(wrapper, "set_value"):
            wrapper.set_value(path)
        else:
            return False
    except Exception:
        return False
    return _edit_text(wrapper) == path


def _uia_find_edit(dialog) -> object:
    """UIA 下按多种候选定位"文件名"编辑框, 返回 wrapper 或 None。"""
    specs: List[Dict[str, str]] = [
        {"class_name": "Edit", "auto_id": str(CLASSIC_FILENAME_EDIT_ID)},
        {"control_type": "Edit", "title": "文件名(N):"},
        {"control_type": "Edit", "title": "文件名:"},
        {"control_type": "Edit", "title_re": "文件名.*"},
    ]
    for spec in specs:
        try:
            child = dialog.child_window(**spec)
            child.wait("exists", timeout=_CTRL_TIMEOUT)
            return child
        except Exception:
            continue
    # 最后兜底: 第一个可用的 Edit
    try:
        children = dialog.children(control_type="Edit")
        return children[0] if children else None
    except Exception:
        return None


def _uia_click_open(dialog) -> bool:
    for spec in (
        {"control_type": "Button", "title_re": "打开.*|Open.*|&OK|OK"},
        {"control_type": "Button", "title": "打开(O)"},
        {"class_name": "Button", "title": "打开"},
    ):
        try:
            btn = dialog.child_window(**spec)
            btn.wait("enabled", timeout=_CTRL_TIMEOUT)
            btn.click_input()
            return True
        except Exception:
            continue
    return False


def _fill_uia(dialog, path: str) -> bool:
    edit = _uia_find_edit(dialog)
    if edit is None:
        return False
    # 写入 + 校验, 最多 3 次(UI 忙/焦点变化时自愈)
    for _ in range(3):
        if _set_edit_text(edit, path):
            break
        time.sleep(0.3)
    else:
        return False
    if _uia_click_open(dialog):
        return True
    # 兜底: 回车(在文件名框有文本时等价于点"打开")
    try:
        dialog.type_keys("{ENTER}", set_foreground=False)
        return True
    except Exception:
        return False


def _win32_fill(dialog, path: str) -> bool:
    """老式对话框: 优先 control_id=1148, 否则取位于底部的 Edit(文件名框)。"""
    edit = None
    try:
        candidates = dialog.children(class_name="Edit")
    except Exception:
        candidates = []
    for e in candidates or []:
        try:
            if e.control_id() == CLASSIC_FILENAME_EDIT_ID:
                edit = e
                break
        except Exception:
            continue
    if edit is None and candidates:
        try:
            edit = max(candidates, key=lambda e: e.rectangle().top)
        except Exception:
            edit = candidates[0]
    if edit is None:
        return False
    for _ in range(3):
        if _set_edit_text(edit, path):
            break
        time.sleep(0.3)
    else:
        return False
    try:  # 打开(O) 按钮 = IDOK
        ok = dialog.child_window(class_name="Button", control_id=CLASSIC_OK_BUTTON_ID)
        ok.wait("enabled", timeout=_CTRL_TIMEOUT)
        ok.click_input()
        return True
    except Exception:
        pass
    try:
        dialog.type_keys("{ENTER}", set_foreground=False)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------- #
# 对外主入口
# ---------------------------------------------------------------------- #
def fill_open_dialog(
    path: str,
    timeout: Optional[float] = None,
    poll: Optional[float] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str]:
    """等待目标"打开"对话框出现 -> 填充 path -> 确认, 返回 (ok, message)。

    全部内部异常均被吸收并转为失败信息; 用户点"停止"(stop_check 返回 True)时
    提前退出, 不阻塞会话收尾。
    """
    path = str(path or "").strip()
    if not path:
        return False, "路径为空"
    # 修复: Tk 文件选择器返回 "C:/x/y" 形式(正斜杠), os.path.isfile 能识别,
    # 但 Windows"打开"对话框(尤其老式 GetOpenFileName)不接受正斜杠分隔的
    # 绝对路径, 填入后点"打开"会报"文件名无效"。统一规范化为反斜杠形式,
    # 确保填入内容与所选文件完全一致(覆盖 path/latest/pick 三种来源)。
    path = os.path.normpath(path)
    timeout = SimulatorConfig.FILE_DIALOG_TIMEOUT if timeout is None else timeout
    poll = SimulatorConfig.FILE_DIALOG_POLL if poll is None else poll

    # 阶段一: 等对话框出现(可被停止信号打断)
    deadline = time.monotonic() + max(0.0, timeout)
    backend = None
    dialog = None
    while True:
        if stop_check is not None:
            try:
                if stop_check():
                    return False, "用户已请求停止"
            except Exception:
                pass
        backend, dialog = _find_dialog()
        if dialog is not None:
            break
        if time.monotonic() >= deadline:
            return (
                False,
                f"等待'打开文件'对话框超时({timeout:.0f}s)。"
                "请确认目标软件确实弹出了选择窗口(如点了错误位置)。",
            )
        time.sleep(max(0.0, poll))

    # 阶段二: 填充并确认; 首选后端失败时换另一后端再试一次
    attempts: List[Tuple[str, object]] = [(backend, dialog)]
    other = "win32" if backend == "uia" else "uia"
    other_backend, other_dialog = _find_dialog()
    if other_backend == other and other_dialog is not None:
        attempts.append((other_backend, other_dialog))

    fillers = {"uia": _fill_uia, "win32": _win32_fill}
    for bk, dlg in attempts:
        filler = fillers.get(bk)
        if filler is None:
            continue
        try:
            if filler(dlg, path):
                return True, f"已自动填入文件并确认: {path}"
        except Exception as e:  # 兜底: 单候选异常不致命
            logger.debug(f"fill via {bk} failed: {e}")
    return (
        False,
        "未能自动填充文件对话框: 未定位到文件名输入框或'打开'按钮。"
        "请人工完成该次选择(控件结构因软件/系统而异, 可反馈日志协助适配)。",
    )
