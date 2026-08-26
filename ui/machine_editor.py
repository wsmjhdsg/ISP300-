import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core.constants import UISettings
from core.logger import get_logger
from ui.step_editor import StepEditorDialog

logger = get_logger(__name__)


class MachineEditorDialog(tk.Toplevel):
    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("机种编辑")
        self.geometry(UISettings.MACHINE_EDITOR_SIZE)
        self.minsize(760, 400)
        self.config_manager = config_manager

        self.current_machine = None
        self.current_rate = None

        self._build_ui()
        self._refresh_machines()

    def _build_ui(self):
        main = ttk.Frame(self, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        mf = ttk.LabelFrame(main, text="机种", padding=15)
        mf.pack(fill=tk.X, pady=5)

        ttk.Label(mf, text="选择机种:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=0, column=0, padx=(0, 10)
        )

        self.machine_var = tk.StringVar()
        self.machine_combo = ttk.Combobox(
            mf, textvariable=self.machine_var, state="readonly", width=17
        )
        self.machine_combo.grid(row=0, column=1, padx=(0, 10))
        self.machine_combo.bind("<<ComboboxSelected>>", self._on_machine_select)

        ttk.Button(mf, text="新增", command=self._add_machine, width=12).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(mf, text="重命名", command=self._rename_machine, width=12).grid(
            row=0, column=3, padx=4
        )
        ttk.Button(mf, text="删除", command=self._delete_machine, width=12).grid(
            row=0, column=4, padx=4
        )

        rf = ttk.LabelFrame(main, text="机种累进", padding=15)
        rf.pack(fill=tk.X, pady=5)

        ttk.Label(rf, text="选择累进:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=0, column=0, padx=(0, 10)
        )

        self.rate_var = tk.StringVar()
        self.rate_combo = ttk.Combobox(
            rf, textvariable=self.rate_var, state="readonly", width=17
        )
        self.rate_combo.grid(row=0, column=1, padx=(0, 10))
        self.rate_combo.bind("<<ComboboxSelected>>", self._on_rate_select)

        ttk.Button(rf, text="新增", command=self._add_rate, width=12).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(rf, text="重命名", command=self._rename_rate, width=12).grid(
            row=0, column=3, padx=4
        )
        ttk.Button(rf, text="删除", command=self._delete_rate, width=12).grid(
            row=0, column=4, padx=4
        )

        sf = ttk.LabelFrame(main, text="当前配置状态", padding=10)
        sf.pack(fill=tk.BOTH, expand=True, pady=10)

        self.status_label = ttk.Label(
            sf,
            text="请先在上方选择机种和累进",
            foreground="gray",
            font=(UISettings.FONT_FAMILY, 11),
        )
        self.status_label.pack(pady=5, padx=10, anchor=tk.W)

        self.file_label = ttk.Label(
            sf, text="", foreground="blue", font=(UISettings.FONT_FAMILY, 10)
        )
        self.file_label.pack(pady=3, padx=10, anchor=tk.W)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="关闭", command=self.destroy, width=12).pack(
            side=tk.LEFT, padx=5
        )

        self.edit_step_btn = ttk.Button(
            btn_frame,
            text="编辑步序(须先选机种和累进)",
            command=self._edit_steps,
            state=tk.DISABLED,
        )
        self.edit_step_btn.pack(side=tk.RIGHT, ipadx=10, ipady=3)

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
        if self.current_machine and self.current_rate:
            steps = self.config_manager.get_steps(self.current_machine, self.current_rate)
            step_file = self.config_manager.get_steps_file(
                self.current_machine, self.current_rate
            )
            if steps:
                self.status_label.config(
                    text=f"已配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  共 {len(steps)} 个步骤",
                    foreground="green",
                )
            else:
                self.status_label.config(
                    text=f"未配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  请点击下方按钮编辑步序",
                    foreground="orange",
                )
            self.file_label.config(text=f"步序文件: {step_file}")
            self.edit_step_btn.config(state=tk.NORMAL)
        else:
            if not self.current_machine:
                self.status_label.config(text="请先在上方选择或新增机种", foreground="gray")
            else:
                self.status_label.config(text="请选择或新增一个累进", foreground="gray")
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
