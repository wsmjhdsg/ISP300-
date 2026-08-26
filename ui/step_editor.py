import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Optional

from core.constants import (
    BUTTON_DISPLAY_VALUES,
    BUTTON_FROM_DISPLAY,
    BUTTON_SHORT_LABELS,
    QUICK_KEYS,
    QUICK_WAIT_SECONDS,
    StepTypes,
    UISettings,
)
from core.logger import get_logger
from core.simulator import Simulator

logger = get_logger(__name__)


class StepEditorDialog(tk.Toplevel):
    STEP_TYPES = [
        (StepTypes.LAUNCH, "打开软件 - 启动外部程序"),
        (StepTypes.CLICK, "点击 - 调用已记录坐标"),
        (StepTypes.TYPE, "输入文本"),
        (StepTypes.KEY, "按键 - 如 Enter/Tab/Esc/F1"),
        (StepTypes.WAIT, "等待 - 暂停指定秒数"),
    ]

    def __init__(self, master, config_manager, machine, rate, steps):
        super().__init__(master)
        self.title(f"步序编辑 - {machine} / {rate}")
        self.geometry(UISettings.STEP_EDITOR_SIZE)
        self.minsize(720, 520)
        self.config_manager = config_manager
        self.machine = machine
        self.rate = rate
        self.steps: List[dict] = list(steps)

        self._build_ui()
        self._refresh_steps()

    def _build_ui(self):
        info = ttk.Frame(self, padding=(10, 10))
        info.pack(fill=tk.X)
        ttk.Label(
            info,
            text=f" 当前编辑: 机种 [{self.machine}]  /  累进 [{self.rate}]",
            font=(UISettings.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(info, text=f"    (共 {len(self.steps)} 步)", foreground="gray").pack(
            side=tk.LEFT
        )

        btn_bar = ttk.Frame(self, padding=(10, 5))
        btn_bar.pack(fill=tk.X)

        ttk.Button(btn_bar, text="末尾新增", command=self._add_step_at_end, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="上方插入", command=self._insert_step_before, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="下方插入", command=self._insert_step_after, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="修改选中", command=self._edit_step, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="删除选中", command=self._delete_step, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="上移", command=lambda: self._move_step(-1), width=10).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(btn_bar, text="下移", command=lambda: self._move_step(1), width=10).pack(
            side=tk.LEFT, padx=3
        )

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        list_frame = ttk.LabelFrame(self, text="步序列表(双击某步骤可修改)", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("idx", "type", "detail", "wait")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=18)
        self.tree.heading("idx", text="序号")
        self.tree.heading("type", text="类型")
        self.tree.heading("detail", text="详细内容")
        self.tree.heading("wait", text="事后等待")
        self.tree.column("idx", width=60, anchor=tk.CENTER)
        self.tree.column("type", width=160)
        self.tree.column("detail", width=450)
        self.tree.column("wait", width=80, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", lambda e: self._edit_step())

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill=tk.X)

        self.count_label = ttk.Label(bottom, text=f"当前共 {len(self.steps)} 个步骤", foreground="blue")
        self.count_label.pack(side=tk.LEFT)

        ttk.Button(bottom, text="保存步序", command=self._save, width=14).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT, padx=5)

    def _type_label(self, t: str) -> str:
        for k, v in self.STEP_TYPES:
            if k == t:
                short = v.split(" ", 1)[1] if " " in v else v
                return short
        return t

    def _step_detail(self, step: dict) -> str:
        t = step.get("type", "")
        if t == StepTypes.LAUNCH:
            path = step.get("path", "")
            display = path if len(path) <= 60 else "..." + path[-60:]
            return f"启动: {display}"
        elif t == StepTypes.CLICK:
            name = step.get("point_name", "")
            x = step.get("x", "")
            y = step.get("y", "")
            btn = step.get("button", "left")
            btn_label = BUTTON_SHORT_LABELS.get(btn, btn)
            if name:
                return f"[{name}]  → {btn_label}点击"
            elif x is not None and y is not None and x != "":
                return f"坐标({x}, {y})  → {btn_label}点击"
            else:
                return "[未选择坐标]"
        elif t == StepTypes.TYPE:
            text = step.get("text", "")
            display = text if len(text) <= 40 else text[:40] + "..."
            return f"'{display}'"
        elif t == StepTypes.KEY:
            return f"按 [{step.get('key', '')}]"
        elif t == StepTypes.WAIT:
            return f"{step.get('seconds', 1.0)} 秒"
        return ""

    def _refresh_steps(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, s in enumerate(self.steps, 1):
            wait_time = s.get("wait", s.get("seconds", "-"))
            detail = self._step_detail(s)
            self.tree.insert("", tk.END, values=(i, self._type_label(s.get("type", "")), detail, wait_time))
        self.count_label.config(text=f"当前共 {len(self.steps)} 个步骤")

    def _get_selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0]) - 1

    def _select_index(self, idx: int):
        if 0 <= idx < len(self.steps):
            children = self.tree.get_children()
            if idx < len(children):
                self.tree.selection_set(children[idx])
                self.tree.see(children[idx])

    def _add_step_at_end(self):
        step = self._open_step_dialog(None)
        if step:
            self.steps.append(step)
            self._refresh_steps()
            self._select_index(len(self.steps) - 1)

    def _insert_step_before(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先选中一个步骤作为插入位置参考", parent=self)
            return
        step = self._open_step_dialog(None)
        if step:
            self.steps.insert(idx, step)
            self._refresh_steps()
            self._select_index(idx)

    def _insert_step_after(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先选中一个步骤作为插入位置参考", parent=self)
            return
        step = self._open_step_dialog(None)
        if step:
            self.steps.insert(idx + 1, step)
            self._refresh_steps()
            self._select_index(idx + 1)

    def _edit_step(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先选中要修改的步骤(或双击该步骤)", parent=self)
            return
        step = self._open_step_dialog(self.steps[idx])
        if step:
            self.steps[idx] = step
            self._refresh_steps()
            self._select_index(idx)

    def _delete_step(self):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先选中要删除的步骤", parent=self)
            return
        if messagebox.askyesno("确认", f"确定删除第 {idx+1} 步吗?", parent=self):
            del self.steps[idx]
            self._refresh_steps()

    def _move_step(self, delta: int):
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("提示", "请先选中要移动的步骤", parent=self)
            return
        new_idx = idx + delta
        if 0 <= new_idx < len(self.steps):
            self.steps[idx], self.steps[new_idx] = self.steps[new_idx], self.steps[idx]
            self._refresh_steps()
            self._select_index(new_idx)
        else:
            if delta < 0:
                messagebox.showinfo("提示", "已在最顶部, 无法再上移", parent=self)
            else:
                messagebox.showinfo("提示", "已在最底部, 无法再下移", parent=self)

    def _save(self):
        if not self.steps:
            if not messagebox.askyesno("确认", "当前没有任何步骤, 确定要保存一个空步序吗?", parent=self):
                return
        self.config_manager.set_steps(self.machine, self.rate, self.steps)
        messagebox.showinfo("完成", f"已保存 {len(self.steps)} 个步骤到步序文件", parent=self)
        self.destroy()

    def _open_step_dialog(self, existing_step: Optional[dict]) -> Optional[dict]:
        dlg = tk.Toplevel(self)
        dlg.title("编辑步骤" if existing_step else "新增步骤")
        dlg.geometry("520x440")
        dlg.minsize(480, 400)
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="步骤类型:", font=(UISettings.FONT_FAMILY, 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=8
        )
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(
            frm,
            textvariable=type_var,
            values=[v for _, v in self.STEP_TYPES],
            width=38,
            state="readonly",
        )
        type_combo.grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=8)

        ttk.Separator(frm, orient=tk.HORIZONTAL).grid(
            row=1, column=0, columnspan=3, sticky=tk.EW, pady=10
        )

        dynamic = ttk.Frame(frm)
        dynamic.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW, pady=5)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(2, weight=1)

        result = {"value": None}

        def get_type_key(label: str) -> str:
            for k, v in self.STEP_TYPES:
                if v == label:
                    return k
            return label.split()[0] if " " in label else label

        def refresh_dynamic(*args):
            for w in dynamic.winfo_children():
                w.destroy()
            key = get_type_key(type_var.get())

            if key == StepTypes.LAUNCH:
                self._build_launch_ui(dynamic, existing_step, result)
            elif key == StepTypes.CLICK:
                self._build_click_ui(dynamic, existing_step, result)
            elif key == StepTypes.TYPE:
                self._build_type_ui(dynamic, existing_step, result)
            elif key == StepTypes.KEY:
                self._build_key_ui(dynamic, existing_step, result)
            elif key == StepTypes.WAIT:
                self._build_wait_ui(dynamic, existing_step, result)

        if existing_step:
            existing_type = existing_step.get("type", StepTypes.CLICK)
            for k, v in self.STEP_TYPES:
                if k == existing_type:
                    type_var.set(v)
                    break
        else:
            type_var.set(self.STEP_TYPES[0][1])

        type_combo.bind("<<ComboboxSelected>>", refresh_dynamic)
        refresh_dynamic()

        ttk.Separator(frm, orient=tk.HORIZONTAL).grid(
            row=4, column=0, columnspan=3, sticky=tk.EW, pady=10
        )
        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=5, column=0, columnspan=3)

        def on_ok():
            pack = result.get("pack")
            if pack:
                s = pack()
                if s:
                    result["value"] = s
                    dlg.destroy()

        ttk.Button(btn_frm, text="确定", command=on_ok, width=12).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frm, text="取消", command=dlg.destroy, width=12).pack(side=tk.LEFT, padx=10)

        dlg.wait_window()
        return result["value"]

    def _build_launch_ui(self, parent, existing_step, result):
        ttk.Label(
            parent,
            text="选择要打开的软件路径(.exe 或快捷方式):",
            font=(UISettings.FONT_FAMILY, 10),
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        path_var = tk.StringVar(
            value=(
                existing_step.get("path", "")
                if existing_step and existing_step.get("type") == StepTypes.LAUNCH
                else ""
            )
        )

        row_path = ttk.Frame(parent)
        row_path.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=5)
        ttk.Entry(row_path, textvariable=path_var, width=55).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5)
        )

        def browse():
            p = filedialog.askopenfilename(
                title="选择要打开的软件",
                filetypes=[("可执行文件 / 快捷方式", "*.exe;*.lnk"), ("所有文件", "*.*")],
                parent=self,
            )
            if p:
                path_var.set(p)

        ttk.Button(row_path, text="浏览...", command=browse).pack(side=tk.LEFT)

        def test_launch():
            p = path_var.get().strip()
            if not p:
                messagebox.showinfo("提示", "请先填写路径", parent=self)
                return
            ok = Simulator.launch_program(p)
            messagebox.showinfo("测试结果", "启动成功!" if ok else "启动失败, 请检查路径", parent=self)

        ttk.Button(parent, text="测试启动", command=test_launch).grid(row=2, column=0, sticky=tk.W, pady=5)

        def pack_step():
            p = path_var.get().strip()
            if not p:
                messagebox.showerror("错误", "请填写软件路径", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.LAUNCH, "path": p}

        result["pack"] = pack_step

    def _build_click_ui(self, parent, existing_step, result):
        names = self.config_manager.get_click_point_names()

        ttk.Label(
            parent, text="选择已记录的坐标:", font=(UISettings.FONT_FAMILY, 10)
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        point_var = tk.StringVar()
        if existing_step and existing_step.get("type") == StepTypes.CLICK and existing_step.get("point_name"):
            point_var.set(existing_step.get("point_name"))

        if names:
            ttk.Combobox(
                parent, textvariable=point_var, values=names, width=40, state="readonly"
            ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        else:
            ttk.Label(
                parent,
                text="(还没有记录坐标, 请先在 \"点击位置编辑\" 中添加)",
                foreground="red",
            ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        ttk.Label(
            parent, text="或手动填写坐标(二选一):", foreground="gray"
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        row_xy = ttk.Frame(parent)
        row_xy.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)

        ttk.Label(row_xy, text="X:").pack(side=tk.LEFT)
        x_default = ""
        y_default = ""
        if existing_step and existing_step.get("type") == StepTypes.CLICK and not existing_step.get("point_name"):
            x_default = str(existing_step.get("x", ""))
            y_default = str(existing_step.get("y", ""))
        x_var = tk.StringVar(value=x_default)
        ttk.Entry(row_xy, textvariable=x_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(row_xy, text="Y:").pack(side=tk.LEFT, padx=(10, 0))
        y_var = tk.StringVar(value=y_default)
        ttk.Entry(row_xy, textvariable=y_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            parent,
            text="按键方式(必须选择! 不允许默认):",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground="blue",
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(15, 0))

        btn_var = tk.StringVar()
        btn_combo = ttk.Combobox(
            parent,
            textvariable=btn_var,
            values=list(BUTTON_DISPLAY_VALUES.values()),
            width=25,
            state="readonly",
        )
        btn_combo.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=5)

        if existing_step and existing_step.get("type") == StepTypes.CLICK:
            existing_btn = existing_step.get("button", "")
            if existing_btn in ("left", "right", "double"):
                btn_combo.set(BUTTON_DISPLAY_VALUES[existing_btn])

        ttk.Label(
            parent,
            text="说明: 如已选择坐标, 则优先使用坐标记录的按键方式;\n如手动填写坐标, 则必须在此处明确选择按键方式。",
            foreground="gray",
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        def pack_step():
            step = {"type": StepTypes.CLICK}
            pname = point_var.get().strip()
            x_val = x_var.get().strip()
            y_val = y_var.get().strip()

            if pname:
                step["point_name"] = pname
            elif x_val and y_val:
                try:
                    step["x"] = int(x_val)
                    step["y"] = int(y_val)
                except ValueError:
                    messagebox.showerror("错误", "坐标必须是数字", parent=parent.winfo_toplevel())
                    return None
            else:
                messagebox.showerror(
                    "错误", "请选择坐标名称或填写坐标(二选一)", parent=parent.winfo_toplevel()
                )
                return None

            b = btn_var.get()
            if not b:
                messagebox.showerror("错误", "必须明确选择按键方式", parent=parent.winfo_toplevel())
                return None
            step["button"] = b.split()[0]
            return step

        result["pack"] = pack_step

    def _build_type_ui(self, parent, existing_step, result):
        ttk.Label(
            parent,
            text="输入文本内容(区分大小写!):",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground="blue",
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        text_box = tk.Text(parent, width=50, height=6, font=(UISettings.FONT_MONO, 11))
        text_box.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        if existing_step and existing_step.get("type") == StepTypes.TYPE:
            text_box.insert("1.0", existing_step.get("text", ""))

        ttk.Label(
            parent,
            text="注意: Hello ≠ hello, 大小写不同。中文/数字/符号均正常支持。",
            foreground="gray",
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 10))

        def pack_step():
            txt = text_box.get("1.0", tk.END).strip()
            if not txt:
                messagebox.showerror("错误", "请输入文本内容", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.TYPE, "text": txt}

        result["pack"] = pack_step

    def _build_key_ui(self, parent, existing_step, result):
        ttk.Label(
            parent, text="按键名称(单个按键):", font=(UISettings.FONT_FAMILY, 10, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        ttk.Label(parent, text="常用按键:", foreground="blue").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        ttk.Label(
            parent,
            text="enter  tab  esc  space  delete  backspace\nf1 f2 f3 ... f12  up  down  left  right",
            foreground="gray",
        ).grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=5)

        key_var = tk.StringVar(
            value=(
                existing_step.get("key", "")
                if existing_step and existing_step.get("type") == StepTypes.KEY
                else ""
            )
        )

        row_key = ttk.Frame(parent)
        row_key.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)
        ttk.Label(row_key, text="按键: ").pack(side=tk.LEFT)
        ttk.Entry(row_key, textvariable=key_var, width=20).pack(side=tk.LEFT, padx=5)

        quick_frame = ttk.Frame(parent)
        quick_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        for quick_key in QUICK_KEYS:
            def set_k(k=quick_key):
                key_var.set(k)
            ttk.Button(quick_frame, text=quick_key.upper(), command=set_k, width=6).pack(
                side=tk.LEFT, padx=2
            )

        def pack_step():
            k = key_var.get().strip().lower()
            if not k:
                messagebox.showerror("错误", "请输入按键名称", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.KEY, "key": k}

        result["pack"] = pack_step

    def _build_wait_ui(self, parent, existing_step, result):
        ttk.Label(
            parent,
            text="暂停多少秒后继续下一步:",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        sec_default = "1.0"
        if existing_step and existing_step.get("type") == StepTypes.WAIT:
            sec_default = str(existing_step.get("seconds", 1.0))
        sec_var = tk.StringVar(value=sec_default)

        row_sec = ttk.Frame(parent)
        row_sec.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=10)
        ttk.Entry(row_sec, textvariable=sec_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(row_sec, text="秒", font=(UISettings.FONT_FAMILY, 11)).pack(side=tk.LEFT)

        quick_frame = ttk.Frame(parent)
        quick_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)
        for quick_sec in QUICK_WAIT_SECONDS:
            def set_s(s=quick_sec):
                sec_var.set(s)
            ttk.Button(quick_frame, text=f"{quick_sec}秒", command=set_s, width=6).pack(
                side=tk.LEFT, padx=2
            )

        ttk.Label(
            parent, text="用途: 等待软件加载、等待弹窗出现等场景。", foreground="gray"
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        def pack_step():
            try:
                sec = float(sec_var.get())
            except ValueError:
                messagebox.showerror("错误", "等待秒数必须是数字", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.WAIT, "seconds": sec}

        result["pack"] = pack_step
