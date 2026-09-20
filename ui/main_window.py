"""主窗口: 浅色工业风「自动化脚本工具」。

职责:
- 顶部钢灰铭牌栏(标题 + 状态指示灯 + 设置菜单);
- 烧录任务参数(机种 / 累进)、开始 / 停止、进度、状态、滚动日志;
- 后台线程执行步序(ExecutionSession 实例化隔离), 跨线程刷新统一走 _ui() helper;
- 日志区行数上限(工业长执行不卡), 执行中支持主动停止与关闭确认。
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from core.constants import SimulatorConfig, UISettings
from core.file_dialog import resolve_pick_steps
from core.logger import get_logger
from core.paths import resource_path
from core.simulator import ExecutionSession
from core.ui_scale import fit_window_to_content
from ui.click_point_editor import ClickPointEditorDialog
from ui.machine_editor import MachineEditorDialog
from ui.styles import (
    apply_ttk_theme,
    create_action_button,
    create_led,
    create_primary_button,
    create_scrolled_text,
    set_action_button_state,
)

logger = get_logger(__name__)


class MainWindow(tk.Tk):
    LOG_MAX_LINES = 1500  # 日志区保留行数上限, 超出裁剪头部(完整日志在 logs/auto_isp.log)
    # 低于此宽度时顶栏收起装饰性 subtitle, 保证"设置"按钮不被挤出可视区。
    # 注意: 必须大于实际的窗口最小宽度(WINDOW_MINSIZE[0]), 否则窗口永远到不了
    # 这个宽度, 该规则就成了死代码(踩过的坑)。
    NARROW_WIDTH = UISettings.WINDOW_MINSIZE[0] + 120

    def __init__(self, config_manager):
        super().__init__()
        self.title("自动化脚本工具")
        self.config_manager = config_manager

        self.is_running = False
        self.session: ExecutionSession | None = None
        # "失败即中止"开关(默认开启, 产线防烧错): 任一步骤失败立即停止后续执行
        self.fail_fast_var = tk.BooleanVar(value=SimulatorConfig.STOP_ON_ERROR)

        self._apply_window_icon()

    def _apply_window_icon(self):
        """窗口标题栏/任务栏图标(源码=assets/, 打包=PyInstaller 解压目录)。"""
        try:
            icon = resource_path(UISettings.APP_ICON)
            if icon.is_file():
                self.iconbitmap(str(icon))
        except Exception:
            pass  # 图标缺失/异常不阻断启动

        apply_ttk_theme(self)
        self._build_ui()
        # 几何收敛放到 UI 构建之后: 此时已算得出内容所需尺寸, 便于小屏合理分配
        fit_window_to_content(self, UISettings.WINDOW_SIZE, UISettings.WINDOW_MINSIZE)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_window_resize)

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        colors = UISettings.COLORS

        # ---- 顶部铭牌栏(深钢灰) ----
        topbar = tk.Frame(self, bg=colors["bg_topbar"])
        topbar.pack(fill=tk.X)

        # 左侧品牌区(允许被压缩, 不与右侧挤占)
        brand = tk.Frame(topbar, bg=colors["bg_topbar"])
        brand.pack(side=tk.LEFT, padx=(14, 8), pady=8)
        self.brand_label = tk.Label(
            brand,
            text="AUTOMATION  ISP300",
            bg=colors["bg_topbar"],
            fg=colors["text_on_dark"],
            font=(UISettings.FONT_TITLE, 13, "bold"),
        )
        self.brand_label.pack(side=tk.LEFT)
        # 副标题: 窄窗口下自动隐藏, 避免与右侧状态区重叠
        self.subtitle_label = tk.Label(
            brand,
            text="自动化脚本工具",
            bg=colors["bg_topbar"],
            fg=colors["text_on_dark"],
            font=(UISettings.FONT_FAMILY, 11),
        )
        self.subtitle_label.pack(side=tk.LEFT, padx=(10, 0))

        # 状态指示灯 + 状态文字(右侧, 优先保留)
        right = tk.Frame(topbar, bg=colors["bg_topbar"])
        right.pack(side=tk.RIGHT, padx=8, pady=6)
        self.led, self._led_set_color = create_led(right)
        self.led.pack(side=tk.LEFT, padx=(0, 6))
        self.state_label = tk.Label(
            right,
            text="空闲",
            bg=colors["bg_topbar"],
            fg=colors["text_on_dark"],
            font=(UISettings.FONT_FAMILY, 10),
        )
        self.state_label.pack(side=tk.LEFT, padx=(0, 10))
        self.settings_btn = tk.Button(
            right,
            text="设置",
            command=self._toggle_settings_menu,
            font=(UISettings.FONT_FAMILY, 10),
            relief=tk.FLAT,
            bg=colors["bg_topbar"],
            fg=colors["text_on_dark"],
            activebackground=colors["bg_window"],
            activeforeground=colors["text"],
            cursor="hand2",
            padx=14,
            pady=3,
            highlightthickness=0,
        )
        self.settings_btn.pack(side=tk.LEFT)

        self.settings_menu = tk.Menu(self, tearoff=0)
        self.settings_menu.add_command(label="机种编辑", command=self._open_machine_editor)
        self.settings_menu.add_command(label="点击位置编辑", command=self._open_click_point_editor)

        # ---- 主体: 铝灰底 + 白色任务卡片 ----
        main = ttk.Frame(self, style="Window.TFrame", padding=UISettings.PAD_MD)
        main.pack(fill=tk.BOTH, expand=True)

        card = ttk.Frame(main, style="Card.TFrame", padding=UISettings.PAD_LG)
        card.pack(fill=tk.BOTH, expand=True)

        # 任务参数
        param = ttk.LabelFrame(card, text="烧录任务参数", padding=10)
        param.pack(fill=tk.X)

        ttk.Label(param, text="机种:", style="Section.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )
        self.machine_var = tk.StringVar()
        self.machine_combo = ttk.Combobox(
            param, textvariable=self.machine_var, width=40, state="readonly"
        )
        self.machine_combo.grid(row=0, column=1, sticky=tk.EW, pady=6)
        self.machine_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_rates())

        ttk.Label(param, text="烧录累进:", style="Section.TLabel").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )
        self.rate_var = tk.StringVar()
        self.rate_combo = ttk.Combobox(
            param, textvariable=self.rate_var, width=40, state="readonly"
        )
        self.rate_combo.grid(row=1, column=1, sticky=tk.EW, pady=6)
        # 输入框列吸收所有多余宽度 -> 窗口缩放时不产生空白或溢出
        param.grid_columnconfigure(1, weight=1)

        # 操作区: 开始(信号橙) / 停止(工控红)
        # 布局策略: 左侧按钮组 + 右侧任务标签分占两端; 任务标签可被压缩且过长时截断显示,
        # 避免窄窗口下与左侧按钮重叠。
        action = ttk.Frame(card, style="Card.TFrame")
        action.pack(fill=tk.X, pady=(UISettings.PAD_MD, 2))

        action_left = ttk.Frame(action, style="Card.TFrame")
        action_left.pack(side=tk.LEFT)
        self.start_btn = create_primary_button(
            action_left, "开始执行", self._start_burn, width=14
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = create_action_button(
            action_left,
            "停止",
            self._stop_burn,
            bg=UISettings.COLORS["danger"],
            hover_bg="#A61E1E",
            width=10,
            font_size=12,
            disabled_bg=UISettings.COLORS["bg_hover"],
        )
        self.stop_btn.configure(state=tk.DISABLED, cursor="arrow")
        self.stop_btn.pack(side=tk.LEFT)
        set_action_button_state(self.stop_btn, False)
        self.fail_fast_check = ttk.Checkbutton(
            action_left,
            text="失败即中止(防烧错)",
            variable=self.fail_fast_var,
        )
        self.fail_fast_check.pack(side=tk.LEFT, padx=(14, 0))

        # 任务标签: 右侧对齐, 宽度受限时由 Tk 自动裁切, 不与左侧争位
        self.task_label = ttk.Label(
            action,
            text="尚未选择任务",
            foreground=UISettings.COLORS["text_secondary"],
            font=(UISettings.FONT_FAMILY, 10),
            anchor=tk.E,
        )
        self.task_label.pack(side=tk.RIGHT, padx=(UISettings.PAD_SM, 0))

        # 进度 + 状态
        prog_row = ttk.Frame(card, style="Card.TFrame")
        prog_row.pack(fill=tk.X, pady=(UISettings.PAD_SM, 0))
        ttk.Label(prog_row, text="执行进度:", font=(UISettings.FONT_FAMILY, 10)).pack(
            side=tk.LEFT
        )
        self.progress = ttk.Progressbar(prog_row, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.percent_label = ttk.Label(
            prog_row, text="0%", width=5, anchor=tk.E, font=(UISettings.FONT_MONO, 10)
        )
        self.percent_label.pack(side=tk.LEFT)

        self.status_label = ttk.Label(
            card,
            text="等待开始...",
            foreground=UISettings.COLORS["text_secondary"],
            font=(UISettings.FONT_FAMILY, 10),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=680,   # 长状态自动换行, 不撑破窗口(随窗口宽度动态更新)
        )
        self.status_label.pack(fill=tk.X, pady=(UISettings.PAD_SM, 2))

        # 执行日志: 权重化的自适应区域(窗口拉高时自动扩展, 压缩时自动收缩)
        self.log_frame = ttk.LabelFrame(
            card,
            text="执行日志 (界面仅保留最近 %d 行, 完整日志见 logs/)" % self.LOG_MAX_LINES,
            padding=6,
        )
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log_text = create_scrolled_text(self.log_frame, width=60, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._refresh_machines()

    # ------------------------------------------------------------------ #
    # 响应式: 宽度变化时收敛文字与换行宽度
    # ------------------------------------------------------------------ #
    def _on_window_resize(self, event=None):
        """窗口尺寸变化时的轻量适配(去抖: 只在宽度真正变化时处理)。"""
        if event is not None and event.widget is not self:
            return
        try:
            w = self.winfo_width()
        except Exception:
            return
        if getattr(self, "_last_w", None) == w:
            return
        self._last_w = w

        # 顶栏副标题: 窄窗口隐藏, 保证右侧状态/设置按钮始终可见可点
        try:
            if w < self.NARROW_WIDTH:
                if self.subtitle_label.winfo_ismapped():
                    self.subtitle_label.pack_forget()
            elif not self.subtitle_label.winfo_ismapped():
                self.subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        except Exception:
            pass

        # 状态文字换行宽度跟随窗口, 避免长文案撑出横向滚动条
        try:
            self.status_label.configure(wraplength=max(240, w - 120))
        except Exception:
            pass


    # ------------------------------------------------------------------ #
    # 跨线程安全刷新: 统一收敛到 after(0, ...)
    # ------------------------------------------------------------------ #
    def _ui(self, fn):
        """把 UI 更新调度回主线程; 窗口已销毁时静默忽略。"""
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _log(self, msg: str):
        def do():
            text = self.log_text
            text.insert(tk.END, msg + "\n")
            text.see(tk.END)
            lines = int(text.index("end-1c").split(".")[0])
            if lines > self.LOG_MAX_LINES:
                text.delete("1.0", f"{lines - self.LOG_MAX_LINES}.0")

        self._ui(do)

    def _set_status(self, text: str, color_key: str = "text", led: str | None = None):
        def do():
            colors = UISettings.COLORS
            self.status_label.configure(
                text=text, foreground=colors.get(color_key, colors["text"])
            )
            self.state_label.configure(text=text.split("  ")[0] if text else "空闲")
            if led:
                self._led_set_color(colors[led])

        self._ui(do)

    # ------------------------------------------------------------------ #
    # 数据刷新 / 菜单
    # ------------------------------------------------------------------ #
    def _refresh_machines(self):
        names = self.config_manager.get_machine_names()
        self.machine_combo["values"] = names
        if self.machine_var.get() not in names:
            self.machine_var.set(names[0] if names else "")
        self._refresh_rates()

    def _refresh_rates(self):
        name = self.machine_var.get()
        rates = self.config_manager.get_machine_rates(name) if name else []
        self.rate_combo["values"] = rates
        if self.rate_var.get() not in rates:
            self.rate_var.set(rates[0] if rates else "")
        self._update_task_label()

    def _update_task_label(self):
        machine = self.machine_var.get()
        rate = self.rate_var.get()
        if machine and rate:
            steps = self.config_manager.get_steps(machine, rate)
            self.task_label.configure(
                text=f"任务: {machine} / {rate}  共 {len(steps)} 步"
            )
        else:
            self.task_label.configure(text="尚未选择任务")

    def _toggle_settings_menu(self):
        x = self.settings_btn.winfo_rootx()
        y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
        self.settings_menu.tk_popup(x, y)

    def _open_machine_editor(self):
        MachineEditorDialog(self, self.config_manager)
        self._refresh_machines()

    def _open_click_point_editor(self):
        ClickPointEditorDialog(self, self.config_manager)

    # ------------------------------------------------------------------ #
    # 执行流程
    # ------------------------------------------------------------------ #
    def _prepare_run(self) -> Optional[List[dict]]:
        """执行前主线程预检: 读取步序 + 解析 pick 模式(手选固件)。

        返回解析后的步序列表; 未选机种/累进、无步序或用户取消 pick 选择时返回 None。
        注意: 本方法不进入执行态, 取消时无副作用(不置灰按钮/不写日志)。
        Tk 文件选择器只能在主线程使用, 因此 pick 在此解析成固定路径后再交给后台线程。
        """
        machine = self.machine_var.get()
        rate = self.rate_var.get()
        if not machine or not rate:
            messagebox.showinfo(
                "提示", "请先选择机种和累进\n(如无数据, 请先在设置中配置)", parent=self
            )
            return None
        steps = self.config_manager.get_steps(machine, rate)
        if not steps:
            messagebox.showinfo(
                "提示",
                f"机种 '{machine}' / 累进 '{rate}' 还没有配置自动化步序\n请在 设置 → 机种编辑 中添加",
                parent=self,
            )
            return None

        def asker(prompt: str) -> Optional[str]:
            return filedialog.askopenfilename(
                title=prompt,
                filetypes=[("固件文件", "*.i3s"), ("所有文件", "*.*")],
                parent=self,
            )

        resolved = resolve_pick_steps(steps, asker)
        if resolved is None:
            messagebox.showinfo(
                "已取消", "已取消开始执行(未选择需要打开的文件)", parent=self
            )
            return None
        return resolved

    def _enter_running_state(self, machine: str, rate: str, steps: List[dict]) -> None:
        """进入执行态(仅预检与文件选择全部通过后调用)。"""
        self.is_running = True
        self._led_set_color(UISettings.COLORS["led_running"])
        # 开始按钮: 禁用 + 文案切换 + 琥珀色提示正在执行
        set_action_button_state(
            self.start_btn, False, text="执行中...", bg=UISettings.COLORS["warning"]
        )
        # 停止按钮: 启用(红色可点)
        set_action_button_state(self.stop_btn, True, bg=UISettings.COLORS["danger"])
        self.progress.configure(value=0)
        self.percent_label.configure(text="0%")
        self.log_text.delete("1.0", tk.END)
        self._set_status(f"准备执行: {machine} / {rate}  共{len(steps)}步", "info")

        self._log("═══════════════════════════════════════")
        self._log(f"[配置] 机种 = {machine}")
        self._log(f"[配置] 累进 = {rate}")
        self._log(f"[配置] 步数 = {len(steps)}")
        self._log("═══════════════════════════════════════")

    def _start_burn(self):
        if self.is_running:
            return
        steps = self._prepare_run()
        if steps is None:
            return

        machine = self.machine_var.get()
        rate = self.rate_var.get()
        self._enter_running_state(machine, rate, steps)
        session = ExecutionSession()
        self.session = session

        def run_thread():
            try:
                self._log("═══════════════════════════════════════")
                self._log("[开始] 执行自动化步序 (按 ESC 或点'停止'可随时中止)")
                self._set_status(f"执行中: 0/{len(steps)}", "info")

                def progress_cb(v):
                    def do():
                        self.progress.configure(value=v)
                        self.percent_label.configure(text=f"{v}%")
                        current = int(v / 100 * len(steps)) if v < 100 else len(steps)
                        self.state_label.configure(text=f"执行中 {current}/{len(steps)}")

                    self._ui(do)

                summary = session.execute_steps(
                    steps,
                    self.config_manager.click_points,
                    progress_callback=progress_cb,
                    log_callback=self._log,
                    stop_on_error=self.fail_fast_var.get(),
                )
                self.after(0, lambda: self._finish_run(summary, machine, rate))
            except Exception as e:
                logger.exception(f"Execution error: {e}")
                self._log(f"[错误] {e}")
                self._set_status(f"执行出错: {e}", "danger", led="led_error")
                self.after(0, lambda: self._reset_controls())
                self.after(0, lambda: messagebox.showerror("执行出错", str(e), parent=self))

        threading.Thread(target=run_thread, daemon=True).start()

    def _stop_burn(self):
        if self.is_running and self.session:
            self._log("[请求] 正在请求停止... (当前步结束后立即中止)")
            self.session.request_stop()

    def _finish_run(self, summary: dict, machine: str, rate: str):
        """统一收尾: 无论 完成/中断/手动停止 都从这里复位界面。"""
        self._reset_controls()
        total = summary.get("total", 0)
        success = summary.get("success", 0)
        failed = summary.get("failed", 0)
        elapsed = summary.get("elapsed", 0)
        self._log("═══════════════════════════════════════")
        self._log(
            f"[完成] 总步数: {total}  成功: {success}  失败: {failed}  耗时: {elapsed}秒"
        )
        self._log("═══════════════════════════════════════")

        if summary.get("stopped"):
            self._set_status(
                f"已停止(ESC/停止按钮)! 已完成: {success}/{total}  耗时: {elapsed}秒",
                "warning",
                led="led_idle",
            )
            messagebox.showwarning(
                "已停止",
                f"执行已被停止(按 ESC 或点'停止'中止)!\n\n机种: {machine}\n累进: {rate}\n已完成: {success}/{total} 步\n失败: {failed} 步\n耗时: {elapsed}秒",
                parent=self,
            )
        elif summary.get("aborted"):
            aborted_at = summary.get("aborted_at") or "?"
            self._set_status(
                f"已中止(第 {aborted_at} 步失败, 失败即中止)! 成功: {success}/{total}  耗时: {elapsed}秒",
                "danger",
                led="led_error",
            )
            messagebox.showwarning(
                "执行中止",
                f"第 {aborted_at}/{total} 步失败, 已按『失败即中止』停止后续执行(防烧错)!\n\n"
                f"机种: {machine}\n累进: {rate}\n已成功: {success} 步\n耗时: {elapsed}秒\n\n"
                f"请查看上方日志确认失败原因后重试。",
                parent=self,
            )
        else:
            if failed:
                self._set_status(
                    f"完成(有失败步骤)! 成功 {success}/{total}  耗时: {elapsed}秒",
                    "warning",
                    led="led_success",
                )
            else:
                self._set_status(
                    f"完成! 总步数: {total}  成功: {success}  耗时: {elapsed}秒",
                    "success",
                    led="led_success",
                )
            messagebox.showinfo(
                "执行完成",
                f"自动化脚本已执行完成!\n\n机种: {machine}\n累进: {rate}\n总步数: {total}\n成功: {success}\n失败: {failed}\n耗时: {elapsed}秒",
                parent=self,
            )
        self.session = None

    def _reset_controls(self):
        colors = UISettings.COLORS
        self.is_running = False
        # 开始按钮: 恢复信号橙 + 原文案
        set_action_button_state(
            self.start_btn, True, text="开始执行", bg=colors["accent"]
        )
        # 停止按钮: 回到禁用态
        set_action_button_state(self.stop_btn, False)
        self._led_set_color(colors["led_idle"])

    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno(
                "执行中",
                "自动化步序仍在执行中!\n\n关闭窗口后后台线程将立即终止(可能留下未完成操作)。\n确定要退出吗?",
                parent=self,
            ):
                return
        self.destroy()

    def run(self):
        self.mainloop()
