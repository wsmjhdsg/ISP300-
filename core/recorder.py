import threading
import time
from typing import Callable, Optional

from core.constants import MouseButtons, RecorderConfig
from core.logger import get_logger

logger = get_logger(__name__)


class ClickRecorder:
    def __init__(self) -> None:
        # pynput 在 start() 内延迟导入: 不进入录制时不加载, 加快冷启动
        self.listener = None
        self.is_recording: bool = False
        self.callback: Optional[Callable[[dict], None]] = None
        self._last_left_click_time: float = 0

    def start(self, callback: Optional[Callable[[dict], None]] = None) -> None:
        if self.is_recording:
            return
        self.callback = callback
        self.is_recording = True
        self._last_left_click_time = 0

        def on_click(x, y, button, pressed):
            if not self.is_recording:
                return False
            if not pressed:
                return True

            btn_str: Optional[str] = None
            now = time.time()

            if button == mouse.Button.left:
                if (
                    now - self._last_left_click_time
                    < RecorderConfig.DOUBLE_CLICK_INTERVAL
                ):
                    btn_str = MouseButtons.DOUBLE
                else:
                    self._last_left_click_time = now

                    def _delayed_check():
                        time.sleep(
                            RecorderConfig.DOUBLE_CLICK_INTERVAL
                            + RecorderConfig.DOUBLE_CLICK_DELAY_BUFFER
                        )
                        if not self.is_recording:
                            return
                        if self._last_left_click_time == now:
                            point = {
                                "x": int(x),
                                "y": int(y),
                                "button": MouseButtons.LEFT,
                            }
                            self.is_recording = False
                            if self.callback:
                                try:
                                    self.callback(point)
                                except Exception as e:
                                    logger.debug(f"Callback error: {e}")

                    threading.Thread(target=_delayed_check, daemon=True).start()
                    return True

            elif button == mouse.Button.right:
                btn_str = MouseButtons.RIGHT

            if btn_str:
                point = {"x": int(x), "y": int(y), "button": btn_str}
                self.is_recording = False
                if self.callback:
                    try:
                        self.callback(point)
                    except Exception as e:
                        logger.debug(f"Callback error: {e}")
                return False

            return True

        from pynput import mouse  # 延迟导入(见 __init__ 注释)

        self.listener = mouse.Listener(on_click=on_click)
        self.listener.daemon = True
        self.listener.start()
        logger.debug("Click recorder started")

    def stop(self) -> None:
        self.is_recording = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        logger.debug("Click recorder stopped")
