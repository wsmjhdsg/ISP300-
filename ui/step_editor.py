import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional

from core.constants import (
    BUTTON_DISPLAY_VALUES,
    BUTTON_FROM_DISPLAY,
    BUTTON_SHORT_LABELS,
    MouseButtons,
    OpenFileModes,
    QUICK_KEYS,
    QUICK_WAIT_SECONDS,
    STEP_DISPLAY_VALUES,
    STEP_KEY_FROM_DISPLAY,
    STEP_SHORT_LABELS,
    StepTypes,
    UISettings,
)
from core.logger import get_logger
from core.simulator import Simulator

logger = get_logger(__name__)


class StepEditorDialog(tk.Toplevel):
    # (type key, 下拉展示文本)。展示文本与 key 的映射在 constants 中显式声明,
    # 不再依赖"从显示文本 split 反推 key"的脆弱写法。
    STEP_TYPES = [(k, STEP_DISPLAY_VALUES[k]) for k in StepTypes.ALL]

    def __init__(self, master, config_manager, machine, rate, steps):
        super().__init__(master)
        self.title(f"步序编辑 - {machine} / {rate}")
        self.geometry(UISettings.STEP_EDITOR_SIZE)
        self.minsize(720, 520)
        self.configure(bg=UISettings.COLORS["bg_window"])
        self.config_manager = config_manager
        self.machine = machine
        self.rate = rate
        self.steps: List[dict] = list(steps)
        # 打开时的磁盘快照: 关闭/取消时据此判断是否有未保存修改, 防止配好误关丢失
        self._saved_steps: List[dict] = [dict(s) for s in steps]

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._refresh_steps()

    def _build_ui(self):
        info = ttk.Frame(self, padding=(10, 10))
        info.pack(fill=tk.X)
        ttk.Label(
            info,
            text=f" 当前编辑: 机种 [{self.machine}]  /  累进 [{self.rate}]",
            style="Title.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            info, text=f"    (共 {len(self.steps)} 步)",
            foreground=UISettings.COLORS["text_secondary"],
        ).pack(side=tk.LEFT)

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
        # 复制步序: 把其他机种/累进的已保存步序追加到当前编辑列表(复用现有加载/保存逻辑)
        ttk.Button(
            btn_bar, text="复制自其他机种…", command=self._copy_steps_from_other, width=18
        ).pack(side=tk.LEFT, padx=(20, 3))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        list_frame = ttk.LabelFrame(self, text="步序列表(双击某步骤可修改)", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("idx", "type", "detail", "wait")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=18)
        self.tree.heading("idx", text="序号")
        self.tree.heading("type", text="类型")
        self.tree.heading("detail", text="详细内容")
        self.tree.heading("wait", text="等待(秒)")
        self.tree.column("idx", width=60, anchor=tk.CENTER)
        self.tree.column("type", width=160)
        self.tree.column("detail", width=450)
        self.tree.column("wait", width=80, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", lambda e: self._edit_step())

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill=tk.X)

        self.count_label = ttk.Label(
            bottom,
            text=f"当前共 {len(self.steps)} 个步骤",
            foreground=UISettings.COLORS["info"],
        )
        self.count_label.pack(side=tk.LEFT)

        ttk.Button(bottom, text="保存步序", command=self._save, width=14).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="取消", command=self._on_close, width=10).pack(side=tk.RIGHT, padx=5)

    def _type_label(self, t: str) -> str:
        return STEP_SHORT_LABELS.get(t, t)

    def _trunc(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else "..." + text[-(limit - 3) :]

    def _step_detail(self, step: dict) -> str:
        t = step.get("type", "")
        if t == StepTypes.LAUNCH:
            path = step.get("path", "")
            return f"启动: {self._trunc(path, 60)}"
        elif t == StepTypes.OPENFILE:
            mode = step.get("mode") or OpenFileModes.PATH
            if mode == OpenFileModes.LATEST:
                directory = step.get("dir", "")
                pattern = step.get("pattern") or "*.i3s"
                return f"自动选最新: {self._trunc(directory, 40)} 匹配 {pattern}"
            if mode == OpenFileModes.PICK:
                return "每次执行前手选固件文件"
            path = step.get("path", "")
            return f"选择文件: {self._trunc(path, 60)}"
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
        elif t == StepTypes.WAITRESULT:
            return f"等待烧录完成弹窗(COMPLETE/Verify OK), 超时 {step.get('timeout', 120)}s"
        return ""

    def _refresh_steps(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, s in enumerate(self.steps, 1):
            # "等待秒数"列: 仅独立 wait 步骤展示; 历史遗留的 step.wait 字段已弃用,
            # 统一以显式 wait 步骤为准, 不再在此列展示以免误导。
            wait_time = (
                str(s.get("seconds", "-")) if s.get("type") == StepTypes.WAIT else "-"
            )
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

    def _copy_steps_from_other(self):
        """从其他机种/累进的【已保存】步序复制步骤, 追加到当前编辑列表。

        最小改动原则:
        - 复用 config_manager 现有 API(get_machine_names/get_machine_rates/get_steps),
          只读来源文件, 不新增依赖、不改存储格式;
        - 结果只追加进 self.steps, 仍由现有「保存步序」经 set_steps 落地,
          沿用现有持久化与校验逻辑;
        - 重名/冲突不做特殊处理, 完全沿用现有编辑规则(用户可自行修改/删除/排序)。
        """
        sources = []  # [(机种, 累进, 已保存步数), ...]
        for name in self.config_manager.get_machine_names():
            for rate in self.config_manager.get_machine_rates(name):
                if name == self.machine and rate == self.rate:
                    continue  # 跳过当前正在编辑的对象
                count = len(self.config_manager.get_steps(name, rate))
                if count > 0:
                    sources.append((name, rate, count))

        if not sources:
            messagebox.showinfo("提示", "没有其他机种保存过步序, 无法复制。", parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title("复制步序")
        dlg.geometry("460x230")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frm,
            text="选择要复制的来源(其他机种已保存的步序):",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        labels = [f"{n} / {r}   ({c} 步)" for n, r, c in sources]
        src_var = tk.StringVar(value=labels[0])
        combo = ttk.Combobox(
            frm, textvariable=src_var, values=labels, width=44, state="readonly"
        )
        combo.pack(anchor=tk.W, pady=(0, 10))

        hint = ttk.Label(
            frm,
            text="",
            foreground=UISettings.COLORS["text_secondary"],
            wraplength=420,
            justify=tk.LEFT,
        )
        hint.pack(anchor=tk.W, pady=(0, 12))

        def refresh_hint(*_args):
            try:
                idx = labels.index(src_var.get())
            except ValueError:
                return
            n, r, c = sources[idx]
            hint.config(text=f"将把 [{n} / {r}] 的 {c} 个步骤追加到当前步序末尾(原步序保留)。")

        combo.bind("<<ComboboxSelected>>", refresh_hint)
        refresh_hint()

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(anchor=tk.E)

        def on_ok():
            try:
                idx = labels.index(src_var.get())
            except ValueError:
                return
            n, r, _ = sources[idx]
            src_steps = self.config_manager.get_steps(n, r)
            if not src_steps:
                messagebox.showinfo("提示", "该来源目前没有可复制的步骤。", parent=dlg)
                return
            # 深拷贝追加: 与来源解耦, 后续编辑当前步序不会影响来源
            self.steps.extend([dict(s) for s in src_steps])
            self._refresh_steps()
            self._select_index(len(self.steps) - 1)
            logger.info(
                f"Copied {len(src_steps)} steps from {n}/{r} into {self.machine}/{self.rate}"
            )
            dlg.destroy()
            messagebox.showinfo(
                "完成",
                f"已从 [{n} / {r}] 复制 {len(src_steps)} 个步骤到当前列表。\n"
                "确认无误后请点「保存步序」写入。",
                parent=self,
            )

        ttk.Button(btn_frm, text="复制", command=on_ok, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frm, text="取消", command=dlg.destroy, width=12).pack(
            side=tk.RIGHT, padx=5
        )

        dlg.wait_window()

    def _save(self) -> bool:
        """保存步序到文件; 成功返回 True(并关闭窗口), 失败弹窗提示并留在窗口。"""
        if not self.steps:
            if not messagebox.askyesno("确认", "当前没有任何步骤, 确定要保存一个空步序吗?", parent=self):
                return False
        try:
            self.config_manager.set_steps(self.machine, self.rate, self.steps)
        except Exception as e:
            logger.exception("Failed to save steps")
            messagebox.showerror(
                "保存失败",
                f"写入步序文件失败, 本次修改未保存!\n\n{e}\n\n"
                "常见原因: config/steps/ 下的文件被其它程序(如记事本)占用。\n"
                "关闭占用程序后请重新点「保存步序」。",
                parent=self,
            )
            return False
        self._saved_steps = [dict(s) for s in self.steps]
        messagebox.showinfo("完成", f"已保存 {len(self.steps)} 个步骤到步序文件", parent=self)
        self.destroy()
        return True

    def _is_modified(self) -> bool:
        return self.steps != self._saved_steps

    def _on_close(self):
        """点标题栏 × 或「取消」: 若有未保存修改先询问, 避免配好的步序静默丢失。"""
        if self._is_modified():
            choice = messagebox.askyesnocancel(
                "未保存的修改",
                "步序有修改尚未保存!\n\n"
                "[是]  保存并退出\n"
                "[否]  放弃修改(不保存)\n"
                "[取消] 返回继续编辑",
                parent=self,
            )
            if choice is None:   # 取消 -> 留在编辑窗口
                return
            if choice:           # 是 -> 保存(失败会提示并留在窗口)
                self._save()
                return
        # 无修改或选择放弃 -> 直接关闭
        self.destroy()

    def _open_step_dialog(self, existing_step: Optional[dict]) -> Optional[dict]:
        dlg = tk.Toplevel(self)
        dlg.title("编辑步骤" if existing_step else "新增步骤")
        dlg.geometry("520x440")
        dlg.minsize(480, 400)
        dlg.configure(bg=UISettings.COLORS["bg_window"])
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
            return STEP_KEY_FROM_DISPLAY.get(
                label, label.split()[0] if " " in label else label
            )

        def refresh_dynamic(*args):
            for w in dynamic.winfo_children():
                w.destroy()
            key = get_type_key(type_var.get())

            if key == StepTypes.LAUNCH:
                self._build_launch_ui(dynamic, existing_step, result)
            elif key == StepTypes.OPENFILE:
                self._build_openfile_ui(dynamic, existing_step, result)
            elif key == StepTypes.CLICK:
                self._build_click_ui(dynamic, existing_step, result)
            elif key == StepTypes.TYPE:
                self._build_type_ui(dynamic, existing_step, result)
            elif key == StepTypes.KEY:
                self._build_key_ui(dynamic, existing_step, result)
            elif key == StepTypes.WAIT:
                self._build_wait_ui(dynamic, existing_step, result)
            elif key == StepTypes.WAITRESULT:
                self._build_waitresult_ui(dynamic, existing_step, result)

        if existing_step:
            existing_type = existing_step.get("type", StepTypes.CLICK)
            for k, v in self.STEP_TYPES:
                if k == existing_type:
                    type_var.set(v)
                    break
        else:
            # 新增步骤默认类型 = "点击"(显式映射, 不依赖下拉列表顺序)
            type_var.set(STEP_DISPLAY_VALUES[StepTypes.CLICK])

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

    def _build_openfile_ui(self, parent, existing_step, result):
        """openfile 表单: 三模式(固定路径 / 目录自动选最新 / 执行前手选)。"""
        existing = (
            existing_step
            if existing_step and existing_step.get("type") == StepTypes.OPENFILE
            else {}
        )
        existing_mode = existing.get("mode") or OpenFileModes.PATH

        mode_display = {
            OpenFileModes.PATH: "固定路径",
            OpenFileModes.LATEST: "目录中自动选最新文件",
            OpenFileModes.PICK: "每次执行前手选",
        }
        display_to_mode = {v: k for k, v in mode_display.items()}

        ttk.Label(
            parent,
            text="文件来源: (执行时自动填充弹出的'打开文件'对话框)",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground=UISettings.COLORS["info"],
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        mode_var = tk.StringVar(
            value=mode_display.get(existing_mode, mode_display[OpenFileModes.PATH])
        )
        mode_combo = ttk.Combobox(
            parent,
            textvariable=mode_var,
            values=list(mode_display.values()),
            width=34,
            state="readonly",
        )
        mode_combo.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        def current_mode() -> str:
            return display_to_mode.get(mode_var.get(), OpenFileModes.PATH)

        body = ttk.Frame(parent)
        body.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW, pady=2)
        fields: Dict[str, tk.StringVar] = {}

        def rebuild(*_args):
            for w in body.winfo_children():
                w.destroy()
            fields.clear()
            mode = current_mode()

            def add_row(frame_text: Optional[str] = None):
                row = ttk.Frame(body)
                row.pack(fill=tk.X, pady=3)
                if frame_text:
                    ttk.Label(row, text=frame_text, width=10).pack(side=tk.LEFT)
                return row

            def add_hint(text: str, color: str = "text_secondary"):
                ttk.Label(
                    body,
                    text=text,
                    foreground=UISettings.COLORS.get(color, UISettings.COLORS["text_secondary"]),
                    wraplength=430,
                    justify=tk.LEFT,
                ).pack(anchor=tk.W, pady=(0, 2))

            if mode == OpenFileModes.PATH:
                fields["path_var"] = tk.StringVar(value=str(existing.get("path", "")))
                row = add_row("文件路径:")
                ttk.Entry(row, textvariable=fields["path_var"], width=48).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5)
                )

                def browse():
                    p = filedialog.askopenfilename(
                        title="选择固件文件",
                        filetypes=[("固件文件", "*.i3s"), ("所有文件", "*.*")],
                        parent=self,
                    )
                    if p:
                        fields["path_var"].set(p)

                ttk.Button(row, text="浏览...", command=browse).pack(side=tk.LEFT)
                add_hint("执行时校验文件存在; 若不存在该步骤将直接失败(不会干等对话框)。")

            elif mode == OpenFileModes.LATEST:
                fields["dir_var"] = tk.StringVar(value=str(existing.get("dir", "")))
                fields["pattern_var"] = tk.StringVar(
                    value=str(existing.get("pattern") or "*.i3s")
                )
                row = add_row("固件目录:")
                ttk.Entry(row, textvariable=fields["dir_var"], width=48).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5)
                )

                def browse_dir():
                    d = filedialog.askdirectory(title="选择固件所在目录", parent=self)
                    if d:
                        fields["dir_var"].set(d)

                ttk.Button(row, text="浏览...", command=browse_dir).pack(side=tk.LEFT)

                row2 = add_row("文件名模式:")
                ttk.Entry(row2, textvariable=fields["pattern_var"], width=20).pack(
                    side=tk.LEFT
                )
                add_hint("执行时自动选取该目录下【修改时间最新】的匹配文件(默认 *.i3s, 不含子目录)。")

            else:  # PICK
                add_hint(
                    "执行到本步前会弹出文件选择窗口, 由你当次选择(选择结果只影响当次执行)。",
                    color="warning",
                )

        mode_combo.bind("<<ComboboxSelected>>", rebuild)
        rebuild()

        def pack_step() -> Optional[dict]:
            mode = current_mode()
            step = {"type": StepTypes.OPENFILE, "mode": mode}
            if mode == OpenFileModes.PATH:
                path = fields.get("path_var").get().strip()
                if not path:
                    messagebox.showerror(
                        "错误", "请填写固件文件路径", parent=parent.winfo_toplevel()
                    )
                    return None
                step["path"] = path
            elif mode == OpenFileModes.LATEST:
                directory = fields.get("dir_var").get().strip()
                if not directory:
                    messagebox.showerror(
                        "错误", "请填写固件目录", parent=parent.winfo_toplevel()
                    )
                    return None
                step["dir"] = directory
                pattern = fields.get("pattern_var").get().strip() or "*.i3s"
                step["pattern"] = pattern
            # PICK 无需额外字段
            return step

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
                foreground=UISettings.COLORS["danger"],
            ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        ttk.Label(
            parent, text="或手动填写坐标(二选一):", foreground=UISettings.COLORS["text_secondary"]
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
            text="按键方式(默认左键单击, 可修改):",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground=UISettings.COLORS["info"],
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(15, 0))

        # 默认"左键单击"(用户可改); 不再强制必选
        default_btn_display = BUTTON_DISPLAY_VALUES[MouseButtons.LEFT]
        btn_var = tk.StringVar(value=default_btn_display)
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
            foreground=UISettings.COLORS["text_secondary"],
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
                # 理论不可达(var 有默认值); 防御兜底为左键, 不再弹错阻断
                b = BUTTON_DISPLAY_VALUES[MouseButtons.LEFT]
            step["button"] = b.split()[0]
            return step

        result["pack"] = pack_step

    def _build_type_ui(self, parent, existing_step, result):
        ttk.Label(
            parent,
            text="输入文本内容(区分大小写!):",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground=UISettings.COLORS["info"],
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        text_box = tk.Text(
            parent,
            width=50,
            height=6,
            font=(UISettings.FONT_MONO, 11),
            bg=UISettings.COLORS["bg_card"],
            fg=UISettings.COLORS["text"],
            insertbackground=UISettings.COLORS["text"],
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=UISettings.COLORS["border_light"],
            highlightcolor=UISettings.COLORS["accent"],
        )
        text_box.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        if existing_step and existing_step.get("type") == StepTypes.TYPE:
            text_box.insert("1.0", existing_step.get("text", ""))

        ttk.Label(
            parent,
            text="注意: Hello ≠ hello, 大小写不同。中文/数字/符号均正常支持。",
            foreground=UISettings.COLORS["text_secondary"],
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

        ttk.Label(parent, text="常用按键:", foreground=UISettings.COLORS["info"]).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        ttk.Label(
            parent,
            text="enter  tab  esc  space  delete  backspace\nf1 f2 f3 ... f12  up  down  left  right",
            foreground=UISettings.COLORS["text_secondary"],
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
            parent,
            text="用途: 等待软件加载、等待弹窗出现等场景。",
            foreground=UISettings.COLORS["text_secondary"],
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        def pack_step():
            try:
                sec = float(sec_var.get())
            except ValueError:
                messagebox.showerror("错误", "等待秒数必须是数字", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.WAIT, "seconds": sec}

        result["pack"] = pack_step

    def _build_waitresult_ui(self, parent, existing_step, result):
        """waitresult 表单: 设置轮询"烧录完成"弹窗的总超时。"""
        ttk.Label(
            parent,
            text="等待'烧录完成'弹窗并判定烧录结果:",
            font=(UISettings.FONT_FAMILY, 10, "bold"),
            foreground=UISettings.COLORS["info"],
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 2))
        ttk.Label(
            parent,
            text="监控 ISP300 弹出标题为 COMPLETE 的弹窗:\n正文含 Verify OK -> 判定成功并自动点[确定]关闭;\n超时未收到 -> 判定失败(宁严勿松)。建议紧跟 Send Data 步骤。",
            foreground=UISettings.COLORS["text_secondary"],
            wraplength=430,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))

        timeout_default = "120"
        if existing_step and existing_step.get("type") == StepTypes.WAITRESULT:
            timeout_default = str(existing_step.get("timeout", 120))
        timeout_var = tk.StringVar(value=timeout_default)

        row_sec = ttk.Frame(parent)
        row_sec.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Label(row_sec, text="等待超时(秒): ").pack(side=tk.LEFT)
        ttk.Entry(row_sec, textvariable=timeout_var, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(row_sec, text="秒", font=(UISettings.FONT_FAMILY, 11)).pack(side=tk.LEFT)

        quick_frame = ttk.Frame(parent)
        quick_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        for quick_sec in ("30", "60", "120", "180", "300"):
            def set_s(s=quick_sec):
                timeout_var.set(s)
            ttk.Button(quick_frame, text=f"{quick_sec}s", command=set_s, width=6).pack(
                side=tk.LEFT, padx=2
            )

        def pack_step():
            try:
                timeout = float(timeout_var.get())
                if timeout < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "等待超时必须是非负数字", parent=parent.winfo_toplevel())
                return None
            return {"type": StepTypes.WAITRESULT, "timeout": timeout}

        result["pack"] = pack_step
