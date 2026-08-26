import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from core.constants import UISettings
from core.logger import get_logger
from core.simulator import Simulator
from ui.click_point_editor import ClickPointEditorDialog
from ui.machine_editor import MachineEditorDialog
from ui.styles import apply_ttk_theme, create_primary_button, set_button_idle, set_button_running

logger = get_logger(__name__)


class MainWindow(tk.Tk):
    def __init__(self, config_manager):
        super().__init__()
        self.title("自动化脚本工具")
        self.geometry(UISettings.WINDOW_SIZE)
        self.minsize(*UISettings.WINDOW_MINSIZE)
        self.config_manager = config_manager
        self.is_running = False
        self.settings_menu = None

        apply_ttk_theme(self)
        self._build_ui()

    def _build_ui(self):
        colors = UISettings.COLORS

        topbar = tk.Frame(self, bg=colors["bg_topbar"])
        topbar.pack(fill=tk.X)

        self.settings_btn = tk.Button(
            topbar,
            text="设置",
            command=self._toggle_settings_menu,
            font=(UISettings.FONT_FAMILY, 10),
            relief=tk.FLAT,
            bg=colors["bg_topbar"],
            cursor="hand2",
            padx=10,
        )
        self.settings_btn.pack(side=tk.LEFT, padx=10, pady=8)

        tk.Label(
            topbar,
            text="自动化脚本工具",
            bg=colors["bg_topbar"],
            font=(UISettings.FONT_FAMILY, 12, "bold"),
        ).pack(side=tk.LEFT, pady=8)

        self.settings_menu = tk.Menu(self, tearoff=0)
        self.settings_menu.add_command(label="机种编辑", command=self._open_machine_editor)
        self.settings_menu.add_command(label="点击位置编辑", command=self._open_click_point_editor)

        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="机种:", font=(UISettings.FONT_FAMILY, 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=8, padx=(0, 10)
        )
        self.machine_var = tk.StringVar()
        self.machine_combo = ttk.Combobox(
            main, textvariable=self.machine_var, width=38, state="readonly"
        )
        self.machine_combo.grid(row=0, column=1, sticky=tk.EW, pady=8)
        self.machine_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_rates())

        ttk.Label(main, text="烧录累进:", font=(UISettings.FONT_FAMILY, 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=8, padx=(0, 10)
        )
        self.rate_var = tk.StringVar()
        self.rate_combo = ttk.Combobox(
            main, textvariable=self.rate_var, width=38, state="readonly"
        )
        self.rate_combo.grid(row=1, column=1, sticky=tk.EW, pady=8)

        self.start_btn = create_primary_button(main, "开始执行", self._start_burn)
        self.start_btn.grid(row=2, column=0, columnspan=2, pady=15)

        self.status_label = ttk.Label(
            main, text="等待开始...", foreground="gray", font=(UISettings.FONT_FAMILY, 10)
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        ttk.Label(main, text="执行进度:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=4, column=0, sticky=tk.W, pady=(5, 5)
        )
        self.progress = ttk.Progressbar(main, mode="determinate", length=500)
        self.progress.grid(row=4, column=1, sticky=tk.EW, pady=(5, 5))

        ttk.Label(main, text="执行日志:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=5, column=0, sticky=tk.NW, pady=(10, 5)
        )
        self.log_text = scrolledtext.ScrolledText(
            main, width=70, height=20, wrap=tk.WORD, font=(UISettings.FONT_MONO, 10)
        )
        self.log_text.grid(row=5, column=1, sticky=tk.NSEW, pady=(10, 5))

        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(5, weight=1)

        self._refresh_machines()

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

    def _toggle_settings_menu(self):
        x = self.settings_btn.winfo_rootx()
        y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
        self.settings_menu.tk_popup(x, y)

    def _open_machine_editor(self):
        MachineEditorDialog(self, self.config_manager)
        self._refresh_machines()

    def _open_click_point_editor(self):
        ClickPointEditorDialog(self, self.config_manager)

    def _log(self, msg: str):
        def do():
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        self.after(0, do)

    def _set_status(self, text: str, color: str = "black"):
        def do():
            self.status_label.config(text=text, foreground=color)
        self.after(0, do)

    def _start_burn(self):
        if self.is_running:
            return
        machine = self.machine_var.get()
        rate = self.rate_var.get()
        if not machine or not rate:
            messagebox.showinfo(
                "提示", "请先选择机种和累进\n(如无数据, 请先在设置中配置)", parent=self
            )
            return
        steps = self.config_manager.get_steps(machine, rate)
        if not steps:
            messagebox.showinfo(
                "提示",
                f"机种 '{machine}' / 累进 '{rate}' 还没有配置自动化步序\n请在 设置 → 机种编辑 中添加",
                parent=self,
            )
            return

        self.is_running = True
        set_button_running(self.start_btn)
        self.progress.configure(value=0)
        self.log_text.delete("1.0", tk.END)
        self._set_status(f"准备执行: {machine} / {rate}  共{len(steps)}步", "blue")

        self._log("═══════════════════════════════════════")
        self._log(f"[配置] 机种 = {machine}")
        self._log(f"[配置] 累进 = {rate}")
        self._log(f"[配置] 步数 = {len(steps)}")
        self._log("═══════════════════════════════════════")

        def run_thread():
            try:
                self._log("═══════════════════════════════════════")
                self._log("[开始] 执行自动化步序 (执行期间请勿移动鼠标)")
                self._set_status(f"执行中: 0/{len(steps)}", "blue")

                def progress_cb(v):
                    self.progress.configure(value=v)
                    current = int(v / 100 * len(steps)) if v < 100 else len(steps)
                    self._set_status(f"执行中: {current}/{len(steps)}", "blue")

                summary = Simulator.execute_steps(
                    steps,
                    self.config_manager.click_points,
                    progress_callback=lambda v: self.after(0, lambda: progress_cb(v)),
                    log_callback=lambda m: self._log(m),
                )

                self._log("═══════════════════════════════════════")
                self._log(
                    f"[完成] 总步数: {summary['total']}  成功: {summary['success']}  耗时: {summary['elapsed']}秒"
                )
                self._log("═══════════════════════════════════════")
                self.after(0, lambda: self.progress.configure(value=100))

                if summary.get("interrupted", False):
                    self._set_status(
                        f"执行失败! (用户移动鼠标) 已完成: {summary['success']}/{summary['total']}  耗时: {summary['elapsed']}秒",
                        "red",
                    )
                    self.after(
                        0,
                        lambda: messagebox.showwarning(
                            "执行失败",
                            f"执行已中止!\n\n原因: 检测到用户手动移动鼠标\n机种: {machine}\n累进: {rate}\n已完成: {summary['success']}/{summary['total']} 步\n耗时: {summary['elapsed']}秒",
                            parent=self,
                        ),
                    )
                else:
                    self._set_status(
                        f"完成! 总步数: {summary['total']}  耗时: {summary['elapsed']}秒",
                        "green",
                    )
                    self.after(
                        0,
                        lambda: messagebox.showinfo(
                            "执行完成",
                            f"自动化脚本已执行完成!\n\n机种: {machine}\n累进: {rate}\n总步数: {summary['total']}\n耗时: {summary['elapsed']}秒",
                            parent=self,
                        ),
                    )

            except Exception as e:
                logger.exception(f"Execution error: {e}")
                self._log(f"[错误] {e}")
                self._set_status(f"执行出错: {e}", "red")
                self.after(0, lambda: messagebox.showerror("执行出错", str(e), parent=self))
            finally:
                self.is_running = False
                self.after(0, lambda: set_button_idle(self.start_btn))

        threading.Thread(target=run_thread, daemon=True).start()

    def run(self):
        self.mainloop()
