"""执行引擎: 逐条执行步序, 模拟鼠标键盘操作 ISP300 上位机。

重构说明(v3):
- 原 Simulator 全静态方法 + 类变量承载执行状态(IME 句柄 / 鼠标监控线程),
  存在跨执行残留与并发互相踩踏的风险; 现改为 ExecutionSession —— 一次执行
  一个实例, 状态实例化隔离, 资源清理(停键盘监听 + 恢复输入法)收敛进 try/finally。
- execute_step 返回 (ok, message) 结构化结果, 修正"失败步骤也被计成功"的统计失真。
- 长文本 type 自动走"剪贴板 + Ctrl+V", 提速并规避逐键转义问题。
- 提供 request_stop() 主动停止(主窗口"停止"按钮), wait 用 Event.wait 可即时响应。

中断机制(v3.3): 移除"鼠标移动超容差即中断"(产线振动易误触发、用户体验差),
改为全局键盘监听 —— 按 ESC 等价于请求停止(stop_event), wait/步骤间隙即时响应。
pyautogui 函数内延迟导入, 加快冷启动。
"""
import ctypes
import os
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import file_dialog as fdm
from core import result_dialog as rdm
from core.constants import (
    BUTTON_SHORT_LABELS,
    ClickPointTypes,
    MouseButtons,
    OpenFileModes,
    SimulatorConfig,
    StepTypes,
)
from core.logger import get_logger
from core.validation import validate_step

logger = get_logger(__name__)


def _pag():
    """延迟导入 pyautogui(仅执行相关函数用到), 编辑/配置场景不加载。"""
    import pyautogui

    return pyautogui


class Simulator:
    """无状态操作集合, 供 UI 侧直接调用(如步序编辑器的"测试启动")。"""

    @staticmethod
    def launch_program(path: str) -> bool:
        if not path or not os.path.exists(path):
            logger.warning(f"Program path not found: {path}")
            return False
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen([path])
            logger.info(f"Launched program: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch program {path}: {e}")
            return False


class ExecutionSession:
    """一次步序执行会话: 独立持有 IME 状态、ESC 键盘监听与停止信号。

    用法(主窗口): session = ExecutionSession(); 执行中可随时 session.request_stop(),
    或直接按 ESC(全局键盘监听触发); 在后台线程调用 execute_steps(...) 执行。
    """

    # 测试时可置 False 跳过真实输入法切换 / 真实键盘监听(避免污染测试环境)
    IME_ENABLED: bool = True
    ESC_ENABLED: bool = True

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._kb_listener = None  # pynput keyboard.Listener(ESC -> 停止)

        # 输入法(会话内切换/恢复): _ime_switched=True 表示中文输入法被本会话临时关闭(英文模式)
        self._ime_switched: bool = False

    # ------------------------------------------------------------------ #
    # 对外: 主动停止(线程安全)
    # ------------------------------------------------------------------ #
    def request_stop(self) -> None:
        self._stop_event.set()
        logger.info("Stop requested by user")

    def _stop_requested(self) -> bool:
        return self._stop_event.is_set()

    # ------------------------------------------------------------------ #
    # ESC 全局监听: 按 ESC 等价于 request_stop()
    # ------------------------------------------------------------------ #
    def _start_esc_listener(self) -> None:
        if not self.ESC_ENABLED:
            return
        from pynput import keyboard  # 延迟导入: 不执行时不加载 pynput

        def on_press(key) -> None:
            try:
                if key == keyboard.Key.esc:
                    self._stop_event.set()
                    logger.info("ESC pressed, stopping execution")
            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        self._kb_listener = listener

    def _stop_esc_listener(self) -> None:
        listener = self._kb_listener
        self._kb_listener = None
        if listener is not None:
            try:
                listener.stop()
                listener.join(timeout=0.6)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # 输入法: 切换英文 / 恢复原布局(会话级, 由 try/finally 保障恢复)
    # ------------------------------------------------------------------ #
    def _ensure_english_ime(self) -> bool:
        """type 输入前的"中/英模式切换": 临时关闭当前中文输入法使其输出英文。

        注意: 只做中文输入法的开启/关闭切换(等价于在语言栏把"中"切到"英"),
        **不切换键盘布局、不加载/激活 00000409 英文布局**, 不会改动系统输入法列表。
        若前台窗口无输入上下文(本身就是英文键盘布局)或输入法本就在英文模式,
        无需处理也无需恢复。返回 True 表示"本会话关闭了中文输入法, 结束需恢复"。
        """
        if not self.IME_ENABLED or os.name != "nt":
            return False
        if self._ime_switched:
            return True
        try:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            imm32 = ctypes.windll.imm32
            # 64 位句柄必须显式声明类型, 否则默认 int 会截断
            imm32.ImmGetContext.restype = ctypes.c_void_p
            imm32.ImmGetContext.argtypes = [ctypes.c_void_p]
            imm32.ImmGetOpenStatus.argtypes = [ctypes.c_void_p]
            imm32.ImmGetOpenStatus.restype = ctypes.c_int
            imm32.ImmSetOpenStatus.argtypes = [ctypes.c_void_p, ctypes.c_int]
            imm32.ImmSetOpenStatus.restype = ctypes.c_int
            imm32.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            himc = imm32.ImmGetContext(hwnd)
            if not himc:
                return False  # 前台无输入上下文(英文键盘/非 IME), 无需处理
            try:
                if imm32.ImmGetOpenStatus(himc):   # 中文输入法开启(中文模式)
                    imm32.ImmSetOpenStatus(himc, 0)  # 关闭 = 切到英文模式
                    self._ime_switched = True
                    time.sleep(SimulatorConfig.IME_SWITCH_DELAY)
                    logger.debug("中文输入法已临时关闭(英文模式)")
                    return True
                # 输入法本来就在英文模式(关闭态), 无需切换也无需恢复
                return False
            finally:
                imm32.ImmReleaseContext(hwnd, himc)
        except Exception as e:
            logger.warning(f"切换输入法中/英模式失败: {e}")
            return False

    def _restore_ime(self) -> None:
        """把本会话临时关闭的中文输入法重新开启(恢复到中文模式)。"""
        if os.name != "nt" or not self._ime_switched:
            return
        try:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            hwnd = user32.GetForegroundWindow()

            imm32 = ctypes.windll.imm32
            imm32.ImmGetContext.restype = ctypes.c_void_p
            imm32.ImmGetContext.argtypes = [ctypes.c_void_p]
            imm32.ImmGetOpenStatus.argtypes = [ctypes.c_void_p]
            imm32.ImmGetOpenStatus.restype = ctypes.c_int
            imm32.ImmSetOpenStatus.argtypes = [ctypes.c_void_p, ctypes.c_int]
            imm32.ImmSetOpenStatus.restype = ctypes.c_int
            imm32.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            if hwnd:
                himc = imm32.ImmGetContext(hwnd)
                if himc:
                    try:
                        if not imm32.ImmGetOpenStatus(himc):
                            imm32.ImmSetOpenStatus(himc, 1)  # 重新开启中文输入法
                            time.sleep(SimulatorConfig.IME_SWITCH_DELAY)
                    finally:
                        imm32.ImmReleaseContext(hwnd, himc)
                logger.debug("已恢复中文输入法开启状态")
        except Exception as e:
            logger.debug(f"恢复输入法失败: {e}")
        finally:
            # 无论恢复是否成功, 会话状态都必须复位, 避免残留到下次执行
            self._ime_switched = False

    # ------------------------------------------------------------------ #
    # 剪贴板(长文本粘贴方案, 纯 Win32 API, 无第三方依赖)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clipboard_set_text(text: str) -> bool:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(None):
                return False
            try:
                user32.EmptyClipboard()
                data = text.encode("utf-16-le") + b"\x00\x00"
                handle = kernel32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE|ZEROINIT
                if not handle:
                    return False
                ptr = kernel32.GlobalLock(handle)
                ctypes.memmove(ptr, data, len(data))
                kernel32.GlobalUnlock(handle)
                user32.SetClipboardData(13, handle)  # CF_UNICODETEXT
            finally:
                user32.CloseClipboard()
            return True
        except Exception as e:
            logger.warning(f"Clipboard write failed: {e}")
            return False

    @staticmethod
    def _clipboard_clear() -> None:
        try:
            user32 = ctypes.windll.user32
            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 基础动作: 鼠标 / 键盘 / 等待(感知会话状态)
    # ------------------------------------------------------------------ #
    def _click_at(self, x: int, y: int, button: str = MouseButtons.LEFT) -> bool:
        if button not in MouseButtons.VALID:
            button = MouseButtons.LEFT
        pag = _pag()
        try:
            pag.moveTo(int(x), int(y), duration=SimulatorConfig.MOVE_DURATION)
            time.sleep(SimulatorConfig.MOVE_PAUSE)
            if button == MouseButtons.RIGHT:
                pag.rightClick()
            elif button == MouseButtons.DOUBLE:
                pag.doubleClick()
            else:
                pag.click()
            logger.debug(f"Clicked at ({x}, {y}) with {button}")
            return True
        except Exception as e:
            logger.error(f"Click failed at ({x}, {y}): {e}")
            return False

    def _type_text(self, text: str) -> bool:
        """输入文本: 短文本逐键模拟(区分大小写); 长文本自动剪贴板 + Ctrl+V 提速。"""
        try:
            self._ensure_english_ime()
            pag = _pag()
            if len(text) > SimulatorConfig.TYPE_PASTE_THRESHOLD:
                if not self._clipboard_set_text(text):
                    logger.warning("Clipboard unavailable, fallback to typewrite")
                    pag.typewrite(text, interval=SimulatorConfig.TYPE_INTERVAL)
                else:
                    try:
                        pag.hotkey("ctrl", "v")
                        time.sleep(0.15)  # 给目标控件留出处理时间再清剪贴板
                    finally:
                        self._clipboard_clear()
            else:
                pag.typewrite(text, interval=SimulatorConfig.TYPE_INTERVAL)
            logger.debug(f"Typed text (length={len(text)})")
            return True
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False

    def _press_key(self, key: str) -> bool:
        try:
            _pag().press(key)
            logger.debug(f"Pressed key: {key}")
            return True
        except Exception as e:
            logger.error(f"Key press failed '{key}': {e}")
            return False

    def _wait(self, seconds: float) -> None:
        """可中断等待: 点"停止"时 Event 立即唤醒, 主循环随即检测退出。"""
        self._stop_event.wait(max(0.0, seconds))

    # ------------------------------------------------------------------ #
    # 单步执行: 返回 (ok, message)
    # ------------------------------------------------------------------ #
    def _execute_one(self, step: dict, points: Dict[str, dict]) -> Tuple[bool, str]:
        step_type = step.get("type", "")

        if step_type == StepTypes.LAUNCH:
            path = step.get("path", "")
            if path:
                ok = Simulator.launch_program(path)
                display = path if len(path) <= 50 else "..." + path[-50:]
                return (
                    ok,
                    (f"启动软件成功: {display}" if ok else f"[警告] 启动软件失败: {display}"),
                )
            return False, "[跳过] 未指定软件路径"

        if step_type == StepTypes.CLICK:
            point_name = step.get("point_name", "")
            if point_name and point_name in points:
                pt = points[point_name]
                button = step.get("button") or pt.get("button", MouseButtons.LEFT)
                if button not in MouseButtons.VALID:
                    button = MouseButtons.LEFT
                if pt.get("type") == ClickPointTypes.CONTROL:
                    from core.isp_controls import click_control as isp_click

                    ok = isp_click(
                        pt.get("control_type"),
                        pt.get("title"),
                        pt.get("auto_id"),
                        button=button,
                    )
                    desc = (
                        pt.get("title")
                        or pt.get("auto_id")
                        or pt.get("control_type")
                        or ""
                    )
                    return (
                        ok,
                        f"点击控件[{point_name}]({desc}) → "
                        f"{'成功' if ok else '[警告] 未找到或点击失败'}",
                    )
                ok = self._click_at(pt["x"], pt["y"], button=button)
                label = BUTTON_SHORT_LABELS.get(button, button)
                return ok, f"移动到[{point_name}]({pt['x']},{pt['y']}) → {label}点击"
            else:
                x, y = step.get("x"), step.get("y")
                button = step.get("button", MouseButtons.LEFT)
                if button not in MouseButtons.VALID:
                    button = MouseButtons.LEFT
                if x is not None and y is not None:
                    ok = self._click_at(x, y, button=button)
                    label = BUTTON_SHORT_LABELS.get(button, button)
                    return ok, f"移动到({x},{y}) → {label}点击"
                return False, f"[跳过] 找不到点击位置: {point_name}"

        if step_type == StepTypes.OPENFILE:
            return self._open_file_step(step)

        if step_type == StepTypes.TYPE:
            text = step.get("text", "")
            ok = self._type_text(text)
            display = text if len(text) <= 30 else text[:30] + "..."
            return ok, f"输入文本(区分大小写): '{display}'"

        if step_type == StepTypes.KEY:
            key = step.get("key", "")
            ok = self._press_key(key)
            return ok, f"按键: [{key}]"

        if step_type == StepTypes.WAIT:
            seconds = float(step.get("seconds", 1.0))
            self._wait(seconds)
            return True, f"等待 {seconds} 秒"

        if step_type == StepTypes.WAITRESULT:
            timeout = step.get("timeout")
            try:
                timeout = float(timeout) if timeout is not None else SimulatorConfig.RESULT_TIMEOUT
            except (TypeError, ValueError):
                timeout = SimulatorConfig.RESULT_TIMEOUT
            ok, detail = rdm.wait_burn_result(
                timeout=timeout, stop_check=self._stop_requested
            )
            if ok:
                return True, f"烧录结果判定: 成功({detail})"
            return False, f"[警告] 烧录结果判定: 未确认成功 —— {detail}"

        return False, f"[跳过] 未知步骤类型: {step_type}"

    def _open_file_step(self, step: dict) -> Tuple[bool, str]:
        """openfile 步骤: 解析目标文件路径后自动填充弹出的"打开文件"对话框。

        mode 语义: path=固定路径(不存在则直接失败, 不开对话框干等);
        latest=取目录内最新匹配文件; pick=应由主界面开始执行前解析为 path,
        若绕过界面直接执行, 返回明确失败而不是抛异常。
        """
        mode = step.get("mode") or OpenFileModes.PATH
        target = ""

        if mode == OpenFileModes.LATEST:
            directory = (step.get("dir") or "").strip()
            if not os.path.isdir(directory):
                return False, f"[跳过] 固件目录不存在: {directory}"
            pattern = (step.get("pattern") or fdm.DEFAULT_PATTERN).strip()
            target = fdm.find_latest_file(directory, pattern)
            if target is None:
                return (
                    False,
                    f"[跳过] 目录中未找到匹配 '{pattern}' 的固件文件: {directory}",
                )
        elif mode == OpenFileModes.PATH:
            target = (step.get("path") or "").strip()
            if not target:
                return False, "[跳过] openfile 未指定文件路径"
            if not os.path.isfile(target):
                return False, f"[跳过] 固件文件不存在: {target}"
        else:  # PICK 未在界面预解析
            return False, "[跳过] 手选(pick)模式需在点击'开始执行'时选择文件, 请通过界面执行"

        # 统一规范化(正斜杠 -> 反斜杠): Tk 选择器返回 "C:/x/y" 形式,
        # Windows"打开"对话框不接受, 直接填入会报"文件名无效"
        target = os.path.normpath(target)
        ok, detail = fdm.fill_open_dialog(target, stop_check=self._stop_requested)
        if ok:
            return True, f"自动选择文件: {target}"
        return False, f"[警告] 选择文件失败({os.path.basename(target)}): {detail}"

    # ------------------------------------------------------------------ #
    # 批量执行主入口
    # ------------------------------------------------------------------ #
    def execute_steps(
        self,
        steps: List[dict],
        click_points: Dict[str, dict],
        progress_callback: Optional[Callable[[int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        stop_on_error: bool = SimulatorConfig.STOP_ON_ERROR,
    ) -> Dict[str, Any]:
        """批量执行步序, 返回 summary。

        stop_on_error=True(默认, 产线防烧错): 任一步骤校验失败或执行失败都会
        立即中止后续步骤(不再继续可能"烧错目标"的操作), summary.aborted=True。
        界面"失败即中止"开关关闭时传 False: 失败步骤计 failed 并继续执行。
        """
        def safe_log(msg: str) -> None:
            if log_callback:
                try:
                    log_callback(msg)
                except Exception:
                    pass

        def safe_progress(value: int) -> None:
            if progress_callback:
                try:
                    progress_callback(value)
                except Exception:
                    pass

        points_map = {name: dict(data) for name, data in click_points.items()}
        names = list(points_map.keys())

        self._ensure_english_ime()
        if self._ime_switched:
            safe_log("[准备] 输入法已临时切到英文模式(中文输入法已关闭), 确保模拟键盘输入有效")
        self._start_esc_listener()
        safe_log("[准备] 已启用全局键盘监听: 执行期间按 ESC(或点'停止')可随时中止")

        total = len(steps)
        success_count = 0
        failed_count = 0
        stopped = False
        aborted = False
        aborted_at = 0
        start_time = time.time()

        try:
            for i, step in enumerate(steps):
                if self._stop_requested():
                    stopped = True
                    safe_log(f"[停止] 已请求停止 (已完成 {i}/{total} 步)")
                    break

                index = i + 1
                errs = validate_step(step, names)
                if errs:
                    failed_count += 1
                    safe_log(f"[{index}/{total}][跳过] 步骤校验未通过: {'; '.join(errs)}")
                    safe_progress(int(index / total * 100))
                    if stop_on_error:
                        aborted, aborted_at = True, index
                        safe_log(
                            f"[中止] 第 {index}/{total} 步校验未通过, 已按『失败即中止』"
                            "停止后续步骤(防止带着异常继续烧录)"
                        )
                        break
                    continue

                ok, message = self._execute_one(step, points_map)
                safe_log(f"[{index}/{total}] {message}")
                safe_progress(int(index / total * 100))
                if ok:
                    success_count += 1
                else:
                    failed_count += 1
                    # waitresult(NG/超时)是烧录成败判定: 无论"失败即中止"是否开启
                    # 都立即停止(绝不在 NG/未判定成功时继续跑后续, 防烧错/防把NG当成功)
                    if stop_on_error or step.get("type") == StepTypes.WAITRESULT:
                        aborted, aborted_at = True, index
                        safe_log(
                            f"[中止] 第 {index}/{total} 步失败, 已停止后续步骤"
                            "(防止带着错误继续烧录, 例如烧错芯片)"
                        )
                        break
                # wait 等长等待内 ESC/停止按钮会即时唤醒 Event, 此处统一收敛为"已停止"
                if self._stop_requested():
                    stopped = True
                    safe_log(f"[停止] 已请求停止 (已完成 {index}/{total} 步)")
                    break
        finally:
            self._stop_esc_listener()
            if self._ime_switched:
                self._restore_ime()
                safe_log("[完成] 输入法已恢复(中文输入法已重新开启)")

        elapsed = round(time.time() - start_time, 1)
        summary = {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "elapsed": elapsed,
            "stopped": stopped,
            "aborted": aborted,
            "aborted_at": aborted_at,
        }

        if aborted:
            safe_log(
                f"═══ 已中止(第 {aborted_at} 步失败, 失败即中止) ═══  "
                f"总步数: {total}  成功: {success_count}  失败: {failed_count}  耗时: {elapsed}秒"
            )
        elif stopped:
            safe_log(
                f"═══ 已停止(ESC/停止按钮) ═══  总步数: {total}  成功: {success_count}  失败: {failed_count}  耗时: {elapsed}秒"
            )
        else:
            safe_log(
                f"═══ 执行完成 ═══  总步数: {total}  成功: {success_count}  失败: {failed_count}  耗时: {elapsed}秒"
            )
        return summary
