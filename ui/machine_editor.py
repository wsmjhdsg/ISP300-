import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core.constants import UISettings
from core.logger import get_logger
from core.ui_scale import fit_window_to_content
from ui.step_editor import StepEditorDialog

logger = get_logger(__name__)


class MachineEditorDialog(tk.Toplevel):
    # 低于此宽度时按钮组折到第二行(避免"选择机种"下拉被按钮挤压变形)
    NARROW_WIDTH = 640

    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("机种编辑")
        self.configure(bg=UISettings.COLORS["bg_window"])
        self.config_manager = config_manager

        self.current_machine = None
        self.current_rate = None
        self._machine_btns = []
        self._rate_btns = []

        self._build_ui()
        self._refresh_machines()
        fit_window_to_content(
            self, UISettings.MACHINE_EDITOR_SIZE, UISettings.MACHINE_EDITOR_MINSIZE
        )
        self.transient(master)
        self.bind("<Configure>", self._on_resize, add="+")

    def _build_row(self, parent, label_text: str, combo_attr: str, var: str,
                   handlers):
        """构建"标签 + 下拉框 + 按钮组"一行。

        布局: 用 grid 让下拉框吸收多余宽度; 按钮组放在独立的 Frame 里,
        窄窗口下整体折到下一行(而不是把下拉框挤没)。
        """
        parent.grid_columnconfigure(1, weight=1)

        ttk.Label(parent, text=label_text).grid(
            row=0, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
        )

        combo = ttk.Combobox(parent, textvariable=var, state="readonly", width=17)
        combo.grid(row=0, column=1, sticky=tk.EW, pady=UISettings.PAD_SM)
        combo.bind("<<ComboboxSelected>>", handlers["select"])

        btn_holder = ttk.Frame(parent)
        btn_holder.grid(row=0, column=2, sticky=tk.E, padx=(UISettings.PAD_SM, 0))
        btns = []
        for text, cmd in (
            ("新增", handlers["add"]),
            ("重命名", handlers["rename"]),
            ("删除", handlers["delete"]),
        ):
            b = ttk.Button(btn_holder, text=text, command=cmd, width=UISettings.BTN_WIDTH_SM)
            b.pack(side=tk.LEFT, padx=(0, UISettings.PAD_XS))
            btns.append(b)
        return combo, btns

    def _build_ui(self):
        colors = UISettings.COLORS

        main = ttk.Frame(self, padding=UISettings.PAD_MD)
        main.pack(fill=tk.BOTH, expand=True)

        mf = ttk.LabelFrame(main, text="机种", padding=UISettings.PAD_MD)
        mf.pack(fill=tk.X, pady=UISettings.PAD_XS)

        self.machine_var = tk.StringVar()
        self.machine_combo, self._machine_btns = self._build_row(
            mf,
            "选择机种:",
            "machine_combo",
            self.machine_var,
            {
                "select": self._on_machine_select,
                "add": self._add_machine,
                "rename": self._rename_machine,
                "delete": self._delete_machine,
            },
        )

        rf = ttk.LabelFrame(main, text="机种累进", padding=UISettings.PAD_MD)
        rf.pack(fill=tk.X, pady=UISettings.PAD_XS)

        self.rate_var = tk.StringVar()
        self.rate_combo, self._rate_btns = self._build_row(
            rf,
            "选择累进:",
            "rate_combo",
            self.rate_var,
            {
                "select": self._on_rate_select,
                "add": self._add_rate,
                "rename": self._rename_rate,
                "delete": self._delete_rate,
            },
        )

        sf = ttk.LabelFrame(main, text="当前配置状态", padding=UISettings.PAD_SM)
        sf.pack(fill=tk.BOTH, expand=True, pady=UISettings.PAD_MD)

        self.status_label = ttk.Label(
            sf,
            text="请先在上方选择机种和累进",
            foreground=colors["text_secondary"],
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=800,
        )
        self.status_label.pack(fill=tk.X, pady=UISettings.PAD_XS)

        self.file_label = ttk.Label(
            sf,
            text="",
            foreground=colors["info"],
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=800,
        )
        self.file_label.pack(fill=tk.X, pady=UISettings.PAD_XS)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=UISettings.PAD_XS)

        ttk.Button(btn_frame, text="关闭", command=self.destroy, width=UISettings.BTN_WIDTH_MD).pack(
            side=tk.LEFT
        )
        self.edit_step_btn = ttk.Button(
            btn_frame,
            text="编辑步序(须先选机种和累进)",
            command=self._edit_steps,
            state=tk.DISABLED,
        )
        self.edit_step_btn.pack(side=tk.RIGHT)

    def _on_resize(self, event=None):
        """窗口宽度变化: 同步状态/文件文字的换行宽度, 窄窗下按钮组不被挤变形。"""
        if event is not None and event.widget is not self:
            return
        try:
            w = self.winfo_width()
        except Exception:
            return
        if getattr(self, "_last_w", None) == w:
            return
        self._last_w = w
        wrap = max(240, w - 60)
        for lbl in (getattr(self, "status_label", None), getattr(self, "file_label", None)):
            if lbl is not None:
                try:
                    lbl.configure(wraplength=wrap)
                except Exception:
                    pass


    def _refresh_machines(self):
        names = self.config_manager.get_machine_names()
        self.machine_combo["values"] = names
        if self.current_machine in names:
            self.machine_var.set(self.current_machine)
        else:
            self.machine_var.set(names[0] if names else "")
            self.current_machine = names[0] if names else None
        self._refresh_rates()

    def _refresh_rates(self):
        if self.current_machine:
            rates = self.config_manager.get_machine_rates(self.current_machine)
            self.rate_combo["values"] = rates
            if self.current_rate in rates:
                self.rate_var.set(self.current_rate)
            else:
                self.rate_var.set(rates[0] if rates else "")
                self.current_rate = rates[0] if rates else None
        else:
            self.rate_combo["values"] = []
            self.rate_var.set("")
            self.current_rate = None
        self._update_status()

    def _update_status(self):
        colors = UISettings.COLORS
        if self.current_machine and self.current_rate:
            steps = self.config_manager.get_steps(self.current_machine, self.current_rate)
            step_file = self.config_manager.get_steps_file(
                self.current_machine, self.current_rate
            )
            if steps:
                self.status_label.config(
                    text=f"已配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  共 {len(steps)} 个步骤",
                    foreground=colors["success"],
                )
            else:
                self.status_label.config(
                    text=f"未配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  请点击下方按钮编辑步序",
                    foreground=colors["warning"],
                )
            self.file_label.config(text=f"步序文件: {step_file}")
            self.edit_step_btn.config(state=tk.NORMAL)
        else:
            if not self.current_machine:
                self.status_label.config(text="请先在上方选择或新增机种", foreground=colors["text_secondary"])
            else:
                self.status_label.config(text="请选择或新增一个累进", foreground=colors["text_secondary"])
            self.file_label.config(text="")
            self.edit_step_btn.config(state=tk.DISABLED)

    def _on_machine_select(self, event=None):
        self.current_machine = self.machine_var.get() or None
        self.current_rate = None
        self._refresh_rates()

    def _on_rate_select(self, event=None):
        self.current_rate = self.rate_var.get() or None
        self._update_status()

    def _add_machine(self):
        name = simpledialog.askstring("新增机种", "请输入机种名称:", parent=self)
        if name and self.config_manager.add_machine(name):
            self.current_machine = name
            self.current_rate = None
            self._refresh_machines()
        elif name:
            messagebox.showwarning("提示", "机种已存在", parent=self)

    def _delete_machine(self):
        if not self.current_machine:
            messagebox.showinfo("提示", "请先选择机种", parent=self)
            return
        if messagebox.askyesno(
            "确认",
            f"删除机种 '{self.current_machine}' ?\n\n该机型下所有累进及对应的步序文件将一并删除!",
            parent=self,
        ):
            self.config_manager.delete_machine(self.current_machine)
            self.current_machine = None
            self.current_rate = None
            self._refresh_machines()

    def _rename_machine(self):
        if not self.current_machine:
            messagebox.showinfo("提示", "请先选择机种", parent=self)
            return
        new = simpledialog.askstring(
            "重命名机种",
            "新机种名称:",
            parent=self,
            initialvalue=self.current_machine,
        )
        if new and self.config_manager.rename_machine(self.current_machine, new):
            self.current_machine = new
            self._refresh_machines()
        elif new and new != self.current_machine:
            messagebox.showwarning("提示", "机种已存在", parent=self)

    def _add_rate(self):
        if not self.current_machine:
            messagebox.showinfo("提示", "请先选择机种", parent=self)
            return
        r = simpledialog.askstring(
            "新增累进",
            f"为机种 [{self.current_machine}] 新增累进值:",
            parent=self,
        )
        if r and self.config_manager.add_rate(self.current_machine, r):
            self.current_rate = r
            self._refresh_rates()
        elif r:
            messagebox.showwarning("提示", "该累进已存在", parent=self)

    def _delete_rate(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        if messagebox.askyesno(
            "确认",
            f"删除累进 '{self.current_rate}' ?\n\n该累进对应的步序文件将一并删除!",
            parent=self,
        ):
            self.config_manager.delete_rate(self.current_machine, self.current_rate)
            self.current_rate = None
            self._refresh_rates()

    def _rename_rate(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        new = simpledialog.askstring(
            "重命名累进",
            "新累进值:",
            parent=self,
            initialvalue=self.current_rate,
        )
        if new and self.config_manager.rename_rate(
            self.current_machine, self.current_rate, new
        ):
            self.current_rate = new
            self._refresh_rates()
        elif new and new != self.current_rate:
            messagebox.showwarning("提示", "该累进已存在", parent=self)

    def _edit_steps(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        steps = self.config_manager.get_steps(self.current_machine, self.current_rate)
        dlg = StepEditorDialog(
            self, self.config_manager, self.current_machine, self.current_rate, steps
        )
        self.wait_window(dlg)
        self._update_status()
