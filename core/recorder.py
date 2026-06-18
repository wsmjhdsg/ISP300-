"""
点击位置记录器
通过监听鼠标点击来记录屏幕位置和按键类型（左键 / 右键 / 双击）
鼠标按键方式必须明确区分，不使用"默认"。
"""
from pynput import mouse
import time


class ClickRecorder:

    # 双击判定阈值（秒）——两次左键点击间隔小于该值视为双击
    DOUBLE_CLICK_INTERVAL = 0.3

    def __init__(self):
        self.listener = None
        self.is_recording = False
        self.callback = None
        self._last_left_click_time = 0

    def start(self, callback=None):
        """开始记录。捕获一次鼠标点击（左键 / 右键 / 双击）后自动停止。"""
        if self.is_recording:
            return
        self.callback = callback
        self.is_recording = True
        self._last_left_click_time = 0

        def on_click(x, y, button, pressed):
            if not self.is_recording:
                return False
            if not pressed:
                return True  # 只处理按下事件, 不处理松开

            btn_str = None
            now = time.time()

            if button == mouse.Button.left:
                # 判定是否为双击(与上一次左键点击的时间差)
                if now - self._last_left_click_time < ClickRecorder.DOUBLE_CLICK_INTERVAL:
                    btn_str = "double"  # 明确标记为双击
                else:
                    # 先不要立即提交, 再等一小段时间看是否有下一次点击
                    self._last_left_click_time = now
                    # 延迟判定: 如果在 DOUBLE_CLICK_INTERVAL 内没有第二次点击, 则视为普通左键
                    def _delayed_check():
                        time.sleep(ClickRecorder.DOUBLE_CLICK_INTERVAL + 0.05)
                        if not self.is_recording:
                            return  # 已经在双击时提交
                        if self._last_left_click_time == now:
                            # 间隔期内没有新的左键, 视为普通左键单击
                            point = {"x": int(x), "y": int(y), "button": "left"}
                            self.is_recording = False
                            if self.callback:
                                try:
                                    self.callback(point)
                                except Exception:
                                    pass
                    import threading
                    threading.Thread(target=_delayed_check, daemon=True).start()
                    return True

            elif button == mouse.Button.right:
                btn_str = "right"  # 明确标记为右键单击

            if btn_str:
                point = {"x": int(x), "y": int(y), "button": btn_str}
                self.is_recording = False
                if self.callback:
                    try:
                        self.callback(point)
                    except Exception:
                        pass
                return False  # 停止监听

            return True

        self.listener = mouse.Listener(on_click=on_click)
        self.listener.daemon = True
        self.listener.start()

    def stop(self):
        """主动停止记录（如用户按 ESC 取消）"""
        self.is_recording = False
        if self.listener:
            self.listener.stop()
            self.listener = None