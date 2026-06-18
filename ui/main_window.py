"""
主窗口
- 左上角设置菜单
- 机种选择 + 累进选择
- 开始烧录按钮
- 更大的日志区域 + 进度条 + 执行完成提示
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
from ui.editor_dialogs import BurnerSettingsDialog, MachineEditorDialog, ClickPointEditorDialog
from core.simulator import Simulator


class MainWindow(tk.Tk):

    def __init__(self, config_manager):
        super().__init__()
        self.title("ISP300 自动化烧录工具")
        self.geometry("720x680")  # 加大窗口, 让所有内容都能看到
        self.minsize(680, 600)    # 最小窗口尺寸, 避免内容被挤压
        self.config_manager = config_manager
        self.is_running = False
        self.settings_menu = None
        self._build_ui()

    def _build_ui(self):
        # ========== 顶部栏 ==========
        topbar = tk.Frame(self, bg="#f0f0f0")
        topbar.pack(fill=tk.X)
        self.settings_btn = tk.Button(topbar, text="⚙ 设置 ▾", command=self._toggle_settings_menu,
                                      font=("Arial", 10))
        self.settings_btn.pack(side=tk.LEFT, padx=10, pady=8)
        ttk.Label(topbar, text="ISP300 自动化烧录工具", font=("Arial", 12, "bold")).pack(side=tk.LEFT, pady=8)

        # 创建设置下拉菜单
        self.settings_menu = tk.Menu(self, tearoff=0)
        self.settings_menu.add_command(label="① 烧录器设置", command=self._open_burner_settings)
        self.settings_menu.add_command(label="② 机种编辑", command=self._open_machine_editor)
        self.settings_menu.add_command(label="③ 点击位置编辑", command=self._open_click_point_editor)

        # ========== 主内容区 ==========
        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # --- 机种选择 ---
        ttk.Label(main, text="机种:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=8, padx=(0, 10))
        self.machine_var = tk.StringVar()
        self.machine_combo = ttk.Combobox(main, textvariable=self.machine_var,
                                          width=38, state="readonly")
        self.machine_combo.grid(row=0, column=1, sticky=tk.EW, pady=8)
        self.machine_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_rates())

        # --- 累进选择 ---
        ttk.Label(main, text="烧录累进:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=8, padx=(0, 10))
        self.rate_var = tk.StringVar()
        self.rate_combo = ttk.Combobox(main, textvariable=self.rate_var,
                                       width=38, state="readonly")
        self.rate_combo.grid(row=1, column=1, sticky=tk.EW, pady=8)

        # --- 烧录按钮 ---
        self.start_btn = tk.Button(main, text="▶ 开始烧录", command=self._start_burn,
                                   font=("Arial", 14, "bold"),
                                   bg="#4CAF50", fg="white", height=2, width=20)
        self.start_btn.grid(row=2, column=0, columnspan=2, pady=15)

        # --- 状态标签 ---
        self.status_label = ttk.Label(main, text="等待开始...", foreground="gray", font=("Arial", 10))
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        # --- 进度条 ---
        ttk.Label(main, text="执行进度:", font=("Arial", 10)).grid(row=4, column=0, sticky=tk.W, pady=(5, 5))
        self.progress = ttk.Progressbar(main, mode="determinate", length=500)
        self.progress.grid(row=4, column=1, sticky=tk.EW, pady=(5, 5))

        # --- 日志区域 (加大) ---
        ttk.Label(main, text="执行日志:", font=("Arial", 10)).grid(row=5, column=0, sticky=tk.NW, pady=(10, 5))
        # 日志框加大, 可显示更多内容, 自动滚动
        self.log_text = scrolledtext.ScrolledText(main, width=70, height=20,
                                                    wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.grid(row=5, column=1, sticky=tk.NSEW, pady=(10, 5))

        # 让第二列可以随窗口伸缩
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(5, weight=1)

        self._refresh_machines()

    # ---------- UI刷新 ----------
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

    # ---------- 设置下拉菜单 ----------
    def _toggle_settings_menu(self):
        x = self.settings_btn.winfo_rootx()
        y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
        self.settings_menu.tk_popup(x, y)

    def _open_burner_settings(self):
        BurnerSettingsDialog(self, self.config_manager)

    def _open_machine_editor(self):
        MachineEditorDialog(self, self.config_manager)
        self._refresh_machines()

    def _open_click_point_editor(self):
        ClickPointEditorDialog(self, self.config_manager)

    # ---------- 日志 ----------
    def _log(self, msg):
        def do():
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)  # 自动滚动到底部
        self.after(0, do)

    def _set_status(self, text, color="black"):
        def do():
            self.status_label.config(text=text, foreground=color)
        self.after(0, do)

    # ---------- 烧录主流程 ----------
    def _start_burn(self):
        if self.is_running:
            return
        machine = self.machine_var.get()
        rate = self.rate_var.get()
        if not machine or not rate:
            messagebox.showinfo("提示", "请先选择机种和累进\n(如无数据, 请先在设置中配置)", parent=self)
            return
        steps = self.config_manager.get_steps(machine, rate)
        if not steps:
            messagebox.showinfo("提示",
                                 f"机种 '{machine}' / 累进 '{rate}' 还没有配置自动化步序\n请在 设置 → 机种编辑 中添加",
                                 parent=self)
            return

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED, text="● 执行中...", bg="#f39c12")
        self.progress.configure(value=0)
        self.log_text.delete("1.0", tk.END)
        self._set_status(f"准备执行: {machine} / {rate}  共{len(steps)}步", "blue")

        self._log("═══════════════════════════════════════")
        self._log(f"[配置] 机种 = {machine}")
        self._log(f"[配置] 累进 = {rate}")
        self._log(f"[配置] 步数 = {len(steps)}")
        self._log("═══════════════════════════════════════")

        burner_path = self.config_manager.get_burner_path()
        if burner_path:
            self._log(f"[启动] 烧录器软件: {burner_path}")
        else:
            self._log("[提示] 未配置烧录器软件路径 (可在设置中配置)")

        def run_thread():
            try:
                # 1. 启动烧录器
                if burner_path:
                    ok = Simulator.launch_program(burner_path)
                    if ok:
                        self._log("[启动] 烧录器软件已启动")
                    else:
                        self._log("[警告] 启动失败, 继续执行自动化步骤...")
                else:
                    self._log("[跳过] 未配置软件路径")

                # 2. 倒计时 - 让软件有时间加载
                self._log("[等待] 8秒后开始执行自动化步序 (请勿移动鼠标)...")
                self._set_status("倒计时中... 请勿移动鼠标", "orange")
                for i in range(8, 0, -1):
                    time.sleep(1)
                    self._log(f"   ... {i} ...")

                # 3. 执行步骤
                self._log("═══════════════════════════════════════")
                self._log("[开始] 执行自动化步序")
                self._set_status(f"执行中: 0/{len(steps)}", "blue")

                def progress_cb(v):
                    self.progress.configure(value=v)
                    current = int(v / 100 * len(steps)) if v < 100 else len(steps)
                    self._set_status(f"执行中: {current}/{len(steps)}", "blue")

                summary = Simulator.execute_steps(
                    steps,
                    self.config_manager.click_points,
                    progress_callback=lambda v: self.after(0, lambda: progress_cb(v)),
                    log_callback=lambda m: self._log(m)
                )

                self._log("═══════════════════════════════════════")
                self._log(f"[✓完成] 总步数: {summary['total']}  成功: {summary['success']}  耗时: {summary['elapsed']}秒")
                self._log("═══════════════════════════════════════")
                self.after(0, lambda: self.progress.configure(value=100))
                self._set_status(f"✓ 完成! 总步数: {summary['total']}  耗时: {summary['elapsed']}秒", "green")

                # 执行完成弹窗提示
                self.after(0, lambda: messagebox.showinfo(
                    "执行完成",
                    f"自动化烧录已完成!\n\n机种: {machine}\n累进: {rate}\n总步数: {summary['total']}\n耗时: {summary['elapsed']}秒",
                    parent=self
                ))

            except Exception as e:
                self._log(f"[✗错误] {e}")
                self._set_status(f"✗ 执行出错: {e}", "red")
                self.after(0, lambda: messagebox.showerror("执行出错", str(e), parent=self))
            finally:
                self.is_running = False
                self.after(0, lambda: self.start_btn.config(state=tk.NORMAL, text="▶ 开始烧录", bg="#4CAF50"))

        threading.Thread(target=run_thread, daemon=True).start()

    def run(self):
        self.mainloop()