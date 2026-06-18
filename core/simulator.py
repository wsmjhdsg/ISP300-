"""
模拟操作模块
- 点击: 先移动鼠标到坐标位置 -> 停顿 -> 点击 (按键方式必须明确指定, 不允许默认)
- 输入文本: 区分大小写
- 按键: 单个按键操作
- 等待: 等待指定秒数
"""
import time
import os
import subprocess
import pyautogui


class Simulator:

    # 鼠标移动速度(秒) - 越小越快, 0=瞬间移动, 0.2=平滑移动
    MOVE_DURATION = 0.2
    # 移动到目标位置后、点击前的停顿(秒) - 让操作者看到鼠标已到位
    MOVE_PAUSE = 0.2

    # 允许的按键方式 (必须明确选择, 不允许默认)
    VALID_BUTTONS = ["left", "right", "double"]

    @staticmethod
    def launch_program(path):
        """启动外部程序(如烧录器软件)"""
        if not path or not os.path.exists(path):
            return False
        try:
            os.startfile(path) if os.name == "nt" else subprocess.Popen([path])
            return True
        except Exception as e:
            print(f"启动失败: {e}")
            return False

    @staticmethod
    def click(x, y, button="left", wait=0.5):
        """
        先移动鼠标到坐标位置, 再执行点击操作(过程可视化)
        button 必须是 left/right/double 之一, 不允许使用默认值
        """
        if button not in Simulator.VALID_BUTTONS:
            button = "left"  # 兜底
        try:
            # 第一步: 平滑移动鼠标到目标坐标
            pyautogui.moveTo(x, y, duration=Simulator.MOVE_DURATION)
            # 第二步: 短暂停顿, 让操作者看到鼠标已到位
            time.sleep(Simulator.MOVE_PAUSE)
            # 第三步: 根据按键方式执行点击
            if button == "right":
                pyautogui.rightClick()
            elif button == "double":
                pyautogui.doubleClick()
            else:
                pyautogui.click()
            # 第四步: 点击后等待(给软件响应时间)
            time.sleep(wait)
            return True
        except Exception as e:
            print(f"点击失败 ({x}, {y}): {e}")
            return False

    @staticmethod
    def type_text(text, wait=0.3):
        """
        输入文本, 区分大小写
        pyautogui.typewrite 本身就区分大小写:
          - "Hello" -> 会正确输入大写H和小写ello
          - "ABC123" -> 会正确输入大写字母
        """
        try:
            pyautogui.typewrite(text, interval=0.05)
            time.sleep(wait)
            return True
        except Exception as e:
            print(f"输入失败 {text}: {e}")
            return False

    @staticmethod
    def press_key(key, wait=0.3):
        """按单个键, key 如: enter, tab, esc, f1, space, delete, backspace, shift, ctrl, alt"""
        try:
            pyautogui.press(key)
            time.sleep(wait)
            return True
        except Exception as e:
            print(f"按键失败 {key}: {e}")
            return False

    @staticmethod
    def wait(seconds):
        time.sleep(max(0, seconds))
        return True

    @staticmethod
    def execute_step(step, click_points_map):
        step_type = step.get("type", "")
        wait = step.get("wait", 0.5)

        if step_type == "click":
            point_name = step.get("point_name", "")
            if point_name and point_name in click_points_map:
                pt = click_points_map[point_name]
                # 优先使用点击位置中记录的按键方式; 若步骤中显式指定则覆盖
                button = step.get("button") or pt.get("button", "left")
                if button not in Simulator.VALID_BUTTONS:
                    button = "left"
                Simulator.click(pt["x"], pt["y"], button=button, wait=wait)
                btn_label = {"left": "左键", "right": "右键", "double": "双击"}.get(button, button)
                return f"移动到[{point_name}]({pt['x']},{pt['y']}) → {btn_label}点击"
            else:
                x = step.get("x")
                y = step.get("y")
                button = step.get("button", "left")
                if button not in Simulator.VALID_BUTTONS:
                    button = "left"
                if x is not None and y is not None:
                    Simulator.click(x, y, button=button, wait=wait)
                    btn_label = {"left": "左键", "right": "右键", "double": "双击"}.get(button, button)
                    return f"移动到({x},{y}) → {btn_label}点击"
            return f"[跳过] 找不到点击位置: {point_name}"

        elif step_type == "type":
            text = step.get("text", "")
            Simulator.type_text(text, wait=wait)
            # 显示文本的前20个字符, 太长用省略号
            display_text = text if len(text) <= 30 else text[:30] + "..."
            return f"输入文本(区分大小写): '{display_text}'"

        elif step_type == "key":
            key = step.get("key", "")
            Simulator.press_key(key, wait=wait)
            return f"按键: [{key}]"

        elif step_type == "wait":
            seconds = step.get("seconds", 1.0)
            Simulator.wait(seconds)
            return f"等待 {seconds} 秒"

        return f"[跳过] 未知步骤类型: {step_type}"

    @staticmethod
    def execute_steps(steps, click_points, progress_callback=None, log_callback=None):
        """
        按顺序执行一系列步骤
        执行完成后返回执行统计信息
        """
        click_points_map = {name: data for name, data in click_points.items()}
        total = len(steps)
        success_count = 0
        start_time = time.time()

        for i, step in enumerate(steps):
            result = Simulator.execute_step(step, click_points_map)
            if log_callback:
                try:
                    log_callback(f"[{i+1}/{total}] {result}")
                except Exception:
                    pass
            if progress_callback:
                try:
                    progress_callback(int((i + 1) / total * 100))
                except Exception:
                    pass
            success_count += 1

        elapsed = round(time.time() - start_time, 1)

        # 执行完成提示
        summary = {
            "total": total,
            "success": success_count,
            "elapsed": elapsed
        }
        if log_callback:
            try:
                log_callback(f"═══ 执行完成 ═══  总步数: {total}  成功: {success_count}  耗时: {elapsed}秒")
            except Exception:
                pass
        return summary