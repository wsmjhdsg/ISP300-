import os
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional

import pyautogui

from core.constants import (
    BUTTON_SHORT_LABELS,
    MouseButtons,
    SimulatorConfig,
    StepTypes,
)
from core.exceptions import ExecutionInterruptedError
from core.logger import get_logger

logger = get_logger(__name__)


class Simulator:
    _original_hkl: Optional[int] = None
    _expected_pos: Optional[tuple] = None
    _mouse_interrupted: bool = False
    _monitoring: bool = False
    _monitor_thread: Optional[threading.Thread] = None
    _monitor_lock: threading.Lock = threading.Lock()

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

    @staticmethod
    def _switch_to_english_ime() -> bool:
        if os.name != "nt":
            return False
        try:
            user32 = __import__("ctypes").windll.user32
            kernel32 = __import__("ctypes").windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            current_thread_id = kernel32.GetCurrentThreadId()

            current_hkl = user32.GetKeyboardLayout(target_thread_id)
            lang_id = current_hkl & 0xFFFF

            HKL_ENGLISH = user32.LoadKeyboardLayoutW("00000409", 1)

            if lang_id == 0x0409:
                Simulator._original_hkl = None
                return False

            Simulator._original_hkl = current_hkl

            if target_thread_id != current_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, True)

            user32.ActivateKeyboardLayout(HKL_ENGLISH, 0)

            if target_thread_id != current_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)

            try:
                user32.SendMessageW(hwnd, 0x0050, 2, HKL_ENGLISH)
            except Exception:
                pass

            time.sleep(SimulatorConfig.IME_SWITCH_DELAY)
            logger.debug("Switched to English IME")
            return True
        except Exception as e:
            logger.warning(f"Failed to switch to English IME: {e}")
            Simulator._original_hkl = None
            return False

    @staticmethod
    def _restore_ime() -> None:
        if os.name != "nt" or Simulator._original_hkl is None:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                Simulator._original_hkl = None
                return

            target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            current_thread_id = kernel32.GetCurrentThreadId()

            if target_thread_id != current_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, True)

            user32.ActivateKeyboardLayout(Simulator._original_hkl, 0)

            if target_thread_id != current_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)

            try:
                user32.SendMessageW(hwnd, 0x0050, 2, Simulator._original_hkl)
            except Exception:
                pass

            time.sleep(SimulatorConfig.IME_SWITCH_DELAY)
            Simulator._original_hkl = None
            logger.debug("Restored original IME")
        except Exception as e:
            logger.debug(f"Failed to restore IME: {e}")
            Simulator._original_hkl = None

    @staticmethod
    def _start_mouse_monitor() -> None:
        with Simulator._monitor_lock:
            Simulator._mouse_interrupted = False
            Simulator._expected_pos = None
            Simulator._monitoring = True

        Simulator._monitor_thread = threading.Thread(
            target=Simulator._monitor_loop, daemon=True
        )
        Simulator._monitor_thread.start()

    @staticmethod
    def _stop_mouse_monitor() -> None:
        with Simulator._monitor_lock:
            Simulator._monitoring = False
        if Simulator._monitor_thread:
            Simulator._monitor_thread.join(timeout=0.5)
        Simulator._monitor_thread = None

    @staticmethod
    def _monitor_loop() -> None:
        while True:
            with Simulator._monitor_lock:
                if not Simulator._monitoring:
                    break

            try:
                current_x, current_y = pyautogui.position()

                with Simulator._monitor_lock:
                    expected = Simulator._expected_pos

                if expected is not None:
                    dx = abs(current_x - expected[0])
                    dy = abs(current_y - expected[1])
                    if (
                        dx > SimulatorConfig.MOUSE_TOLERANCE
                        or dy > SimulatorConfig.MOUSE_TOLERANCE
                    ):
                        with Simulator._monitor_lock:
                            Simulator._mouse_interrupted = True
                            Simulator._monitoring = False
                        logger.info("Execution interrupted by user mouse movement")
                        break
            except Exception:
                pass

            time.sleep(SimulatorConfig.MOUSE_CHECK_INTERVAL)

    @staticmethod
    def _update_expected_pos(x: int, y: int) -> None:
        with Simulator._monitor_lock:
            Simulator._expected_pos = (int(x), int(y))

    @staticmethod
    def _is_interrupted() -> bool:
        with Simulator._monitor_lock:
            return Simulator._mouse_interrupted

    @staticmethod
    def click(x: int, y: int, button: str = MouseButtons.LEFT) -> bool:
        if button not in MouseButtons.VALID:
            logger.warning(f"Invalid button '{button}', falling back to left click")
            button = MouseButtons.LEFT
        try:
            pyautogui.moveTo(x, y, duration=SimulatorConfig.MOVE_DURATION)
            Simulator._update_expected_pos(x, y)
            time.sleep(SimulatorConfig.MOVE_PAUSE)

            if button == MouseButtons.RIGHT:
                pyautogui.rightClick()
            elif button == MouseButtons.DOUBLE:
                pyautogui.doubleClick()
            else:
                pyautogui.click()

            Simulator._update_expected_pos(x, y)
            logger.debug(f"Clicked at ({x}, {y}) with {button}")
            return True
        except Exception as e:
            logger.error(f"Click failed at ({x}, {y}): {e}")
            return False

    @staticmethod
    def type_text(text: str) -> bool:
        try:
            Simulator._switch_to_english_ime()
            pyautogui.typewrite(text, interval=SimulatorConfig.TYPE_INTERVAL)
            logger.debug(f"Typed text (length={len(text)})")
            return True
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False

    @staticmethod
    def press_key(key: str) -> bool:
        try:
            pyautogui.press(key)
            logger.debug(f"Pressed key: {key}")
            return True
        except Exception as e:
            logger.error(f"Key press failed '{key}': {e}")
            return False

    @staticmethod
    def wait(seconds: float) -> bool:
        time.sleep(max(0, seconds))
        return True

    @staticmethod
    def execute_step(step: dict, click_points_map: Dict[str, dict]) -> str:
        step_type = step.get("type", "")

        if step_type == StepTypes.LAUNCH:
            path = step.get("path", "")
            if path:
                ok = Simulator.launch_program(path)
                display_path = path if len(path) <= 50 else "..." + path[-50:]
                return f"{'启动软件成功' if ok else '[警告] 启动软件失败'}: {display_path}"
            return "[跳过] 未指定软件路径"

        elif step_type == StepTypes.CLICK:
            point_name = step.get("point_name", "")
            if point_name and point_name in click_points_map:
                pt = click_points_map[point_name]
                button = step.get("button") or pt.get("button", MouseButtons.LEFT)
                if button not in MouseButtons.VALID:
                    button = MouseButtons.LEFT
                Simulator.click(pt["x"], pt["y"], button=button)
                btn_label = BUTTON_SHORT_LABELS.get(button, button)
                return f"移动到[{point_name}]({pt['x']},{pt['y']}) → {btn_label}点击"
            else:
                x = step.get("x")
                y = step.get("y")
                button = step.get("button", MouseButtons.LEFT)
                if button not in MouseButtons.VALID:
                    button = MouseButtons.LEFT
                if x is not None and y is not None:
                    Simulator.click(x, y, button=button)
                    btn_label = BUTTON_SHORT_LABELS.get(button, button)
                    return f"移动到({x},{y}) → {btn_label}点击"
            return f"[跳过] 找不到点击位置: {point_name}"

        elif step_type == StepTypes.TYPE:
            text = step.get("text", "")
            Simulator.type_text(text)
            display_text = text if len(text) <= 30 else text[:30] + "..."
            return f"输入文本(区分大小写): '{display_text}'"

        elif step_type == StepTypes.KEY:
            key = step.get("key", "")
            Simulator.press_key(key)
            return f"按键: [{key}]"

        elif step_type == StepTypes.WAIT:
            seconds = step.get("seconds", 1.0)
            Simulator.wait(seconds)
            return f"等待 {seconds} 秒"

        return f"[跳过] 未知步骤类型: {step_type}"

    @staticmethod
    def execute_steps(
        steps: List[dict],
        click_points: Dict[str, dict],
        progress_callback: Optional[Callable[[int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> dict:
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

        switched = Simulator._switch_to_english_ime()
        if switched:
            safe_log("[准备] 已切换输入法到英文状态, 确保模拟键盘输入有效")

        Simulator._start_mouse_monitor()
        safe_log("[准备] 鼠标监控已启动, 执行期间请勿移动鼠标")

        click_points_map = {name: dict(data) for name, data in click_points.items()}
        total = len(steps)
        success_count = 0
        interrupted = False
        start_time = time.time()

        for i, step in enumerate(steps):
            if Simulator._is_interrupted():
                interrupted = True
                safe_log(
                    f"[失败] 检测到用户手动移动鼠标, 执行已中止 (已完成 {i}/{total} 步)"
                )
                break

            result = Simulator.execute_step(step, click_points_map)
            safe_log(f"[{i+1}/{total}] {result}")
            safe_progress(int((i + 1) / total * 100))
            success_count += 1

        elapsed = round(time.time() - start_time, 1)

        Simulator._stop_mouse_monitor()

        if switched:
            Simulator._restore_ime()
            safe_log("[完成] 已恢复原来的输入法")

        summary = {
            "total": total,
            "success": success_count,
            "elapsed": elapsed,
            "interrupted": interrupted,
        }

        if interrupted:
            safe_log(
                f"═══ 执行失败 ═══  总步数: {total}  已完成: {success_count}  耗时: {elapsed}秒  (检测到用户手动移动鼠标)"
            )
        else:
            safe_log(
                f"═══ 执行完成 ═══  总步数: {total}  成功: {success_count}  耗时: {elapsed}秒"
            )

        return summary
