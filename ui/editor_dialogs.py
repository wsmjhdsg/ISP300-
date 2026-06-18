"""
各种编辑器对话框
- BurnerSettingsDialog: 烧录器软件路径设置
- ClickPointEditorDialog: 点击坐标记录/管理
- StepEditorDialog: 步序编辑(改进版, 操作清晰, 按键必须明确选择)
- MachineEditorDialog: 机种/累进管理
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import time


# ======================================================================
# 烧录器设置 - 配置烧录器软件的快捷方式路径
# ======================================================================

class BurnerSettingsDialog(tk.Toplevel):

    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("① 烧录器设置")
        self.geometry("560x240")
        self.minsize(500, 220)
        self.config_manager = config_manager
        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=20)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="烧录器软件快捷方式路径(可选):",
                   font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

        ttk.Label(frm, text="如不设置则不自动启动软件, 直接执行步序。",
                   foreground="gray").grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        self.path_var = tk.StringVar(value=self.config_manager.get_burner_path())
        ttk.Entry(frm, textvariable=self.path_var, width=55).grid(row=2, column=0, sticky=tk.EW, padx=(0, 5), pady=5)
        frm.grid_columnconfigure(0, weight=1)

        ttk.Button(frm, text="浏览...", command=self._browse).grid(row=2, column=1, padx=3)
        ttk.Button(frm, text="测试启动", command=self._test_launch).grid(row=2, column=2, padx=3)

        self.status_label = ttk.Label(frm, text="", foreground="gray")
        self.status_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, pady=(15, 0))
        ttk.Button(btns, text="保存", command=self._save, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="关闭", command=self.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="选择烧录器软件或快捷方式",
            filetypes=[("可执行文件 / 快捷方式", "*.exe;*.lnk"), ("所有文件", "*.*")],
            parent=self
        )
        if path:
            self.path_var.set(path)

    def _test_launch(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showinfo("提示", "请先填写路径", parent=self)
            return
        from core.simulator import Simulator
        ok = Simulator.launch_program(path)
        self.status_label.config(text=("已启动: " + path) if ok else ("启动失败, 请检查路径"),
                                  foreground=("green" if ok else "red"))

    def _save(self):
        self.config_manager.set_burner_path(self.path_var.get().strip())
        messagebox.showinfo("完成", "烧录器软件路径已保存", parent=self)


# ======================================================================
# 点击位置编辑 - 管理坐标, 每个坐标必须明确指定按键方式
# ======================================================================

class ClickPointEditorDialog(tk.Toplevel):

    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("③ 点击位置编辑")
        self.geometry("600x480")
        self.minsize(550, 400)
        self.config_manager = config_manager
        self.recorder = None
        self.pending_name = None

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        # 顶部操作栏
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Button(top, text="➕ 新增坐标(点击记录)", command=self._add_point).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="✎ 修改选中", command=self._edit_point).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="🗑 删除选中", command=self._delete_point).pack(side=tk.LEFT, padx=3)

        self.status_label = ttk.Label(top, text="", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=15)

        # 说明文字
        hint = ttk.Label(self, text="说明: 点击 \"新增坐标\" 后, 窗口会变淡, 请在目标位置点击一次鼠标(左键/右键/双击)来记录坐标。\n每个坐标都会记录点击的按键方式, 后续在步序编辑中使用该坐标时会沿用此按键方式。",
                          foreground="gray", padding=(10, 0))
        hint.pack(fill=tk.X)

        # 坐标列表(加大)
        cols = ("name", "x", "y", "button")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        self.tree.heading("name", text="名称")
        self.tree.heading("x", text="X坐标")
        self.tree.heading("y", text="Y坐标")
        self.tree.heading("button", text="按键方式")
        self.tree.column("name", width=200)
        self.tree.column("x", width=80, anchor=tk.CENTER)
        self.tree.column("y", width=80, anchor=tk.CENTER)
        self.tree.column("button", width=120, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda e: self._edit_point())

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, data in self.config_manager.click_points.items():
            btn = data.get("button", "left")
            btn_label = {"left": "左键单击", "right": "右键单击", "double": "左键双击"}.get(btn, btn)
            self.tree.insert("", tk.END, values=(name, data.get("x", ""),
                                                  data.get("y", ""), btn_label))

    def _add_point(self):
        if self.recorder and self.recorder.is_recording:
            messagebox.showinfo("提示", "正在记录中, 请先完成...", parent=self)
            return
        name = simpledialog.askstring("新增坐标", "请输入坐标名称(如 \"开始按钮\"):", parent=self)
        if not name:
            return
        if name in self.config_manager.click_points:
            if not messagebox.askyesno("确认", f"名称 '{name}' 已存在, 是否覆盖?", parent=self):
                return

        self.pending_name = name
        self.status_label.config(text=f"[记录中] 请在目标位置点击一次(左键/右键/双击)... 按 ESC 取消")
        self.update()

        try:
            self.attributes("-alpha", 0.3)
        except Exception:
            pass

        from core.recorder import ClickRecorder
        self.recorder = ClickRecorder()
        self.recorder.start(callback=self._on_recorded)
        self.bind("<Escape>", self._cancel_record)

    def _on_recorded(self, point):
        name = self.pending_name
        self.pending_name = None
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.unbind("<Escape>")
        if name:
            btn = point.get("button", "left")
            btn_label = {"left": "左键", "right": "右键", "double": "双击"}.get(btn, btn)
            self.config_manager.add_click_point(name, point["x"], point["y"], btn)
            self.status_label.config(text=f"[已记录] {name} = ({point['x']},{point['y']}) {btn_label}点击", foreground="green")
            self._refresh()

    def _cancel_record(self, event=None):
        if self.recorder:
            self.recorder.stop()
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.unbind("<Escape>")
        self.pending_name = None
        self.status_label.config(text="已取消记录", foreground="gray")

    def _get_selected_name(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][0]

    def _delete_point(self):
        name = self._get_selected_name()
        if not name:
            messagebox.showinfo("提示", "请先选择要删除的记录", parent=self)
            return
        if messagebox.askyesno("确认", f"确定删除 '{name}' 吗?", parent=self):
            self.config_manager.delete_click_point(name)
            self.status_label.config(text=f"已删除: {name}")
            self._refresh()

    def _edit_point(self):
        name = self._get_selected_name()
        if not name:
            messagebox.showinfo("提示", "请先选择要编辑的记录(或双击该记录)", parent=self)
            return
        data = self.config_manager.get_click_point(name)

        dlg = tk.Toplevel(self)
        dlg.title(f"编辑坐标: {name}")
        dlg.geometry("380x280")
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="X坐标:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=8)
        x_var = tk.StringVar(value=str(data.get("x", 0)))
        ttk.Entry(frm, textvariable=x_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="Y坐标:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=8)
        y_var = tk.StringVar(value=str(data.get("y", 0)))
        ttk.Entry(frm, textvariable=y_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="按键方式:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=8)
        btn_var = tk.StringVar(value=data.get("button", "left"))
        btn_combo = ttk.Combobox(frm, textvariable=btn_var,
                                   values=["left 左键单击", "right 右键单击", "double 左键双击"],
                                   width=18, state="readonly")
        # 设置初始值
        current_btn = data.get("button", "left")
        btn_combo.set({"left": "left 左键单击", "right": "right 右键单击", "double": "double 左键双击"}.get(current_btn, "left 左键单击"))
        btn_combo.grid(row=2, column=1, sticky=tk.W, pady=8)

        def save():
            try:
                x_val = int(x_var.get())
                y_val = int(y_var.get())
            except ValueError:
                messagebox.showerror("错误", "坐标必须是数字", parent=dlg)
                return
            # 解析按键值
            btn_val = btn_var.get().split()[0]
            self.config_manager.update_click_point(name, x_val, y_val, btn_val)
            self.status_label.config(text=f"已更新: {name}")
            self._refresh()
            dlg.destroy()

        ttk.Button(frm, text="保存", command=save, width=12).grid(row=3, column=0, columnspan=2, pady=15)


# ======================================================================
# 步序编辑 - 优化版
# 特点:
#   - 步骤一目了然(序号 + 类型 + 详细内容)
#   - 按键方式必须明确选择(left/right/double), 不允许默认
#   - 文本输入提示区分大小写
#   - 新增/删除/上移/下移按钮清晰明了
# ======================================================================

class StepEditorDialog(tk.Toplevel):

    # 步骤类型: (内部key, 显示名称, 图标)
    STEP_TYPES = [
        ("click", "① 点击 - 调用已记录坐标"),
        ("type", "② 输入文本 - 区分大小写"),
        ("key", "③ 按键 - 如 Enter/Tab/Esc/F1"),
        ("wait", "④ 等待 - 暂停指定秒数"),
    ]

    def __init__(self, master, config_manager, machine, rate, steps):
        super().__init__(master)
        self.title(f"步序编辑 - {machine} / {rate}")
        self.geometry("800x620")
        self.minsize(720, 520)
        self.config_manager = config_manager
        self.machine = machine
        self.rate = rate
        self.steps = list(steps)  # 本地副本, 取消时不保存

        self._build_ui()
        self._refresh_steps()

    def _build_ui(self):
        # ========== 顶部信息栏 ==========
        info = ttk.Frame(self, padding=(10, 10))
        info.pack(fill=tk.X)
        ttk.Label(info, text=f"📋 当前编辑: 机种 [{self.machine}]  /  累进 [{self.rate}]",
                   font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(info, text=f"    (共 {len(self.steps)} 步)", foreground="gray").pack(side=tk.LEFT)

        # ========== 操作按钮栏 ==========
        btn_bar = ttk.Frame(self, padding=(10, 5))
        btn_bar.pack(fill=tk.X)

        ttk.Button(btn_bar, text="➕ 在末尾新增", command=self._add_step_at_end).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="↩ 在选中上方插入", command=self._insert_step_before).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="↪ 在选中下方插入", command=self._insert_step_after).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✎ 修改选中", command=self._edit_step).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="🗑 删除选中", command=self._delete_step).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="⬆ 上移", command=lambda: self._move_step(-1)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="⬇ 下移", command=lambda: self._move_step(1)).pack(side=tk.LEFT, padx=3)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        # ========== 步骤列表 ==========
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

        # ========== 底部保存按钮 ==========
        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill=tk.X)

        self.count_label = ttk.Label(bottom, text=f"当前共 {len(self.steps)} 个步骤", foreground="blue")
        self.count_label.pack(side=tk.LEFT)

        ttk.Button(bottom, text="💾 保存步序", command=self._save, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT, padx=5)

    # ---------- 列表刷新 ----------
    def _type_label(self, t):
        for k, v in self.STEP_TYPES:
            if k == t:
                # 去掉开头的序号前缀, 只保留简短名称
                short = v.split(" ", 1)[1] if " " in v else v
                return short
        return t

    def _step_detail(self, step):
        t = step.get("type", "")
        if t == "click":
            name = step.get("point_name", "")
            x = step.get("x", "")
            y = step.get("y", "")
            btn = step.get("button", "left")
            btn_label = {"left": "左键", "right": "右键", "double": "双击"}.get(btn, btn)
            if name:
                return f"[{name}]  → {btn_label}点击"
            elif x is not None and y is not None and x != "":
                return f"坐标({x}, {y})  → {btn_label}点击"
            else:
                return "[未选择坐标]"
        elif t == "type":
            text = step.get("text", "")
            display = text if len(text) <= 40 else text[:40] + "..."
            return f"'{display}'"
        elif t == "key":
            return f"按 [{step.get('key', '')}]"
        elif t == "wait":
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

    # ---------- 获取选中项 ----------
    def _get_selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0]) - 1

    def _select_index(self, idx):
        """选中指定索引(用于新增后自动选中新项)"""
        if 0 <= idx < len(self.steps):
            children = self.tree.get_children()
            if idx < len(children):
                self.tree.selection_set(children[idx])
                self.tree.see(children[idx])

    # ---------- 新增/编辑/删除/移动 ----------
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

    def _move_step(self, delta):
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
            # 到顶/到底的提示
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

    # ---------- 步骤编辑对话框(核心!) ----------
    def _open_step_dialog(self, existing_step):
        """弹出编辑一个步骤的对话框, 返回步骤dict或None"""
        dlg = tk.Toplevel(self)
        dlg.title("编辑步骤" if existing_step else "新增步骤")
        dlg.geometry("520x440")
        dlg.minsize(480, 400)
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        # --- 步骤类型选择 ---
        ttk.Label(frm, text="步骤类型:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=8)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(frm, textvariable=type_var,
                                  values=[v for _, v in self.STEP_TYPES],
                                  width=38, state="readonly")
        type_combo.grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=8)

        # 分割线
        ttk.Separator(frm, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=10)

        # --- 动态内容区 ---
        dynamic = ttk.Frame(frm)
        dynamic.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW, pady=5)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(2, weight=1)

        # 存储结果
        result = {"value": None}

        def get_type_key(label):
            for k, v in self.STEP_TYPES:
                if v == label:
                    return k
            return label.split()[0] if " " in label else label

        def refresh_dynamic(*args):
            """根据选择的类型刷新动态内容区"""
            for w in dynamic.winfo_children():
                w.destroy()
            key = get_type_key(type_var.get())

            # ========== ① 点击 ==========
            if key == "click":
                names = self.config_manager.get_click_point_names()

                ttk.Label(dynamic, text="选择已记录的坐标:",
                           font=("Arial", 10)).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

                point_var = tk.StringVar()
                if existing_step and existing_step.get("type") == "click" and existing_step.get("point_name"):
                    point_var.set(existing_step.get("point_name"))

                if names:
                    point_combo = ttk.Combobox(dynamic, textvariable=point_var, values=names,
                                                width=40, state="readonly")
                    point_combo.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
                else:
                    ttk.Label(dynamic, text="(还没有记录坐标, 请先在 \"点击位置编辑\" 中添加)",
                               foreground="red").grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

                # 备选: 手动填写坐标
                ttk.Label(dynamic, text="或手动填写坐标(二选一):",
                           foreground="gray").grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

                row_xy = ttk.Frame(dynamic)
                row_xy.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)

                ttk.Label(row_xy, text="X:").pack(side=tk.LEFT)
                x_var = tk.StringVar(value=str(existing_step.get("x", "")) if existing_step and existing_step.get("type") == "click" and not existing_step.get("point_name") else "")
                ttk.Entry(row_xy, textvariable=x_var, width=10).pack(side=tk.LEFT, padx=5)

                ttk.Label(row_xy, text="Y:").pack(side=tk.LEFT, padx=(10, 0))
                y_var = tk.StringVar(value=str(existing_step.get("y", "")) if existing_step and existing_step.get("type") == "click" and not existing_step.get("point_name") else "")
                ttk.Entry(row_xy, textvariable=y_var, width=10).pack(side=tk.LEFT, padx=5)

                # 按键方式(必须明确选择, 不允许默认!)
                ttk.Label(dynamic, text="按键方式(必须选择! 不允许默认):",
                           font=("Arial", 10, "bold"), foreground="blue").grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(15, 0))

                btn_var = tk.StringVar()
                btn_options = ["left 左键单击", "right 右键单击", "double 左键双击"]
                btn_combo = ttk.Combobox(dynamic, textvariable=btn_var, values=btn_options,
                                          width=25, state="readonly")
                btn_combo.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=5)

                # 编辑已有步骤时, 保留原有的按键方式; 新增时留空, 强迫用户明确选择
                if existing_step and existing_step.get("type") == "click":
                    existing_btn = existing_step.get("button", "")
                    if existing_btn in ("left", "right", "double"):
                        btn_combo.set({"left": "left 左键单击", "right": "right 右键单击", "double": "double 左键双击"}[existing_btn])
                    # 如果已有步骤没有明确按键, 同样留空强迫选择
                # 其他情况(新增步骤): 不设置任何值, 下拉框显示为空 —— 用户必须明确三选一

                ttk.Label(dynamic, text="说明: 如已选择坐标, 则优先使用坐标记录的按键方式;\n如手动填写坐标, 则必须在此处明确选择按键方式。",
                           foreground="gray").grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

                # 步骤后等待
                ttk.Label(dynamic, text="步骤后等待(秒):", font=("Arial", 10)).grid(row=7, column=0, sticky=tk.W, pady=(15, 0))
                wait_var = tk.StringVar(value=str(existing_step.get("wait", 0.5)) if existing_step and existing_step.get("type") == "click" else "0.5")
                ttk.Entry(dynamic, textvariable=wait_var, width=12).grid(row=7, column=1, sticky=tk.W, pady=(15, 0))

                def pack_step():
                    step = {"type": "click"}
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
                            messagebox.showerror("错误", "坐标必须是数字", parent=dlg)
                            return
                    else:
                        messagebox.showerror("错误", "请选择坐标名称或填写坐标(二选一)", parent=dlg)
                        return

                    # 按键方式必须明确
                    b = btn_var.get()
                    if not b:
                        messagebox.showerror("错误", "必须明确选择按键方式", parent=dlg)
                        return
                    step["button"] = b.split()[0]  # 取 "left"/"right"/"double"

                    try:
                        step["wait"] = float(wait_var.get())
                    except ValueError:
                        step["wait"] = 0.5
                    return step

                result["pack"] = pack_step

            # ========== ② 输入文本 ==========
            elif key == "type":
                ttk.Label(dynamic, text="输入文本内容(区分大小写!):",
                           font=("Arial", 10, "bold"), foreground="blue").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

                text_box = tk.Text(dynamic, width=50, height=6, font=("Consolas", 11))
                text_box.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
                if existing_step and existing_step.get("type") == "type":
                    text_box.insert("1.0", existing_step.get("text", ""))

                ttk.Label(dynamic, text="注意: Hello ≠ hello, 大小写不同。中文/数字/符号均正常支持。",
                           foreground="gray").grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 10))

                ttk.Label(dynamic, text="步骤后等待(秒):", font=("Arial", 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
                wait_var = tk.StringVar(value=str(existing_step.get("wait", 0.3)) if existing_step and existing_step.get("type") == "type" else "0.3")
                ttk.Entry(dynamic, textvariable=wait_var, width=12).grid(row=3, column=1, sticky=tk.W, pady=5)

                def pack_step():
                    txt = text_box.get("1.0", tk.END).strip()
                    if not txt:
                        messagebox.showerror("错误", "请输入文本内容", parent=dlg)
                        return
                    step = {"type": "type", "text": txt}
                    try:
                        step["wait"] = float(wait_var.get())
                    except ValueError:
                        step["wait"] = 0.3
                    return step

                result["pack"] = pack_step

            # ========== ③ 按键 ==========
            elif key == "key":
                ttk.Label(dynamic, text="按键名称(单个按键):", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

                ttk.Label(dynamic, text="常用按键:", foreground="blue").grid(row=1, column=0, sticky=tk.W, pady=5)
                ttk.Label(dynamic, text="enter  tab  esc  space  delete  backspace\nf1 f2 f3 ... f12  up  down  left  right",
                           foreground="gray").grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=5)

                key_var = tk.StringVar(
                    value=(existing_step.get("key", "") if existing_step and existing_step.get("type") == "key" else ""))

                row_key = ttk.Frame(dynamic)
                row_key.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)
                ttk.Label(row_key, text="按键: ").pack(side=tk.LEFT)
                ttk.Entry(row_key, textvariable=key_var, width=20).pack(side=tk.LEFT, padx=5)

                # 快捷按钮
                quick_frame = ttk.Frame(dynamic)
                quick_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
                for quick_key in ["enter", "tab", "esc", "space", "f1", "f2", "delete"]:
                    def set_k(k=quick_key):
                        key_var.set(k)
                    ttk.Button(quick_frame, text=quick_key.upper(), command=set_k, width=6).pack(side=tk.LEFT, padx=2)

                ttk.Label(dynamic, text="步骤后等待(秒):", font=("Arial", 10)).grid(row=4, column=0, sticky=tk.W, pady=(15, 0))
                wait_var = tk.StringVar(value=str(existing_step.get("wait", 0.3)) if existing_step and existing_step.get("type") == "key" else "0.3")
                ttk.Entry(dynamic, textvariable=wait_var, width=12).grid(row=4, column=1, sticky=tk.W, pady=(15, 0))

                def pack_step():
                    k = key_var.get().strip().lower()
                    if not k:
                        messagebox.showerror("错误", "请输入按键名称", parent=dlg)
                        return
                    step = {"type": "key", "key": k}
                    try:
                        step["wait"] = float(wait_var.get())
                    except ValueError:
                        step["wait"] = 0.3
                    return step

                result["pack"] = pack_step

            # ========== ④ 等待 ==========
            elif key == "wait":
                ttk.Label(dynamic, text="暂停多少秒后继续下一步:",
                           font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(5, 5))

                sec_var = tk.StringVar(
                    value=str(existing_step.get("seconds", 1.0)) if existing_step and existing_step.get("type") == "wait" else "1.0")

                row_sec = ttk.Frame(dynamic)
                row_sec.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=10)
                ttk.Entry(row_sec, textvariable=sec_var, width=15).pack(side=tk.LEFT, padx=5)
                ttk.Label(row_sec, text="秒", font=("Arial", 11)).pack(side=tk.LEFT)

                # 快捷按钮
                quick_frame = ttk.Frame(dynamic)
                quick_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)
                for quick_sec in ["0.5", "1", "2", "3", "5"]:
                    def set_s(s=quick_sec):
                        sec_var.set(s)
                    ttk.Button(quick_frame, text=f"{quick_sec}秒", command=set_s, width=6).pack(side=tk.LEFT, padx=2)

                ttk.Label(dynamic, text="用途: 等待软件加载、等待弹窗出现等场景。",
                           foreground="gray").grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

                def pack_step():
                    try:
                        sec = float(sec_var.get())
                    except ValueError:
                        messagebox.showerror("错误", "等待秒数必须是数字", parent=dlg)
                        return
                    return {"type": "wait", "seconds": sec}

                result["pack"] = pack_step

        # 设置初始类型
        if existing_step:
            existing_type = existing_step.get("type", "click")
            for k, v in self.STEP_TYPES:
                if k == existing_type:
                    type_var.set(v)
                    break
        else:
            type_var.set(self.STEP_TYPES[0][1])  # 默认选第一个

        type_combo.bind("<<ComboboxSelected>>", refresh_dynamic)
        refresh_dynamic()  # 首次渲染

        # --- 底部按钮 ---
        ttk.Separator(frm, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)
        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=5, column=0, columnspan=3)

        def on_ok():
            pack = result.get("pack")
            if pack:
                s = pack()
                if s:
                    result["value"] = s
                    dlg.destroy()

        ttk.Button(btn_frm, text="✓ 确定", command=on_ok, width=12).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frm, text="取消", command=dlg.destroy, width=12).pack(side=tk.LEFT, padx=10)

        dlg.wait_window()
        return result["value"]


# ======================================================================
# 机种编辑对话框 - 机种/累进使用下拉框, 步序编辑独立页面
# ======================================================================

class MachineEditorDialog(tk.Toplevel):

    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("② 机种编辑")
        self.geometry("640x500")
        self.minsize(580, 440)
        self.config_manager = config_manager
        self.current_machine = None
        self.current_rate = None

        self._build_ui()
        self._refresh_machines()

    def _build_ui(self):
        main = ttk.Frame(self, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        # ========== 机种区域 ==========
        mf = ttk.LabelFrame(main, text="① 机种", padding=10)
        mf.pack(fill=tk.X, pady=5)

        ttk.Label(mf, text="选择机种:", font=("Arial", 10)).grid(row=0, column=0, padx=(0, 10))

        self.machine_var = tk.StringVar()
        self.machine_combo = ttk.Combobox(mf, textvariable=self.machine_var,
                                          state="readonly", width=35)
        self.machine_combo.grid(row=0, column=1, padx=(0, 10))
        self.machine_combo.bind("<<ComboboxSelected>>", self._on_machine_select)

        ttk.Button(mf, text="➕新增", command=self._add_machine, width=8).grid(row=0, column=2, padx=2)
        ttk.Button(mf, text="✎重命名", command=self._rename_machine, width=8).grid(row=0, column=3, padx=2)
        ttk.Button(mf, text="🗑删除", command=self._delete_machine, width=8).grid(row=0, column=4, padx=2)

        # ========== 累进区域 ==========
        rf = ttk.LabelFrame(main, text="② 机种累进", padding=10)
        rf.pack(fill=tk.X, pady=5)

        ttk.Label(rf, text="选择累进:", font=("Arial", 10)).grid(row=0, column=0, padx=(0, 10))

        self.rate_var = tk.StringVar()
        self.rate_combo = ttk.Combobox(rf, textvariable=self.rate_var,
                                        state="readonly", width=35)
        self.rate_combo.grid(row=0, column=1, padx=(0, 10))
        self.rate_combo.bind("<<ComboboxSelected>>", self._on_rate_select)

        ttk.Button(rf, text="➕新增", command=self._add_rate, width=8).grid(row=0, column=2, padx=2)
        ttk.Button(rf, text="✎重命名", command=self._rename_rate, width=8).grid(row=0, column=3, padx=2)
        ttk.Button(rf, text="🗑删除", command=self._delete_rate, width=8).grid(row=0, column=4, padx=2)

        # ========== 状态信息区 ==========
        sf = ttk.LabelFrame(main, text="③ 当前配置状态", padding=10)
        sf.pack(fill=tk.BOTH, expand=True, pady=10)

        self.status_label = ttk.Label(sf, text="请先在上方选择机种和累进",
                                       foreground="gray", font=("Arial", 11))
        self.status_label.pack(pady=5, padx=10, anchor=tk.W)

        self.file_label = ttk.Label(sf, text="", foreground="blue", font=("Arial", 10))
        self.file_label.pack(pady=3, padx=10, anchor=tk.W)

        self.preview_label = ttk.Label(sf, text="", foreground="#555", font=("Arial", 10))
        self.preview_label.pack(pady=5, padx=10, anchor=tk.W)

        # ========== 步序编辑按钮 ==========
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="关闭", command=self.destroy, width=12).pack(side=tk.LEFT, padx=5)

        self.edit_step_btn = ttk.Button(btn_frame, text="▶ 打开步序编辑器(须先选机种和累进)",
                                         command=self._edit_steps,
                                         state=tk.DISABLED)
        self.edit_step_btn.pack(side=tk.RIGHT, ipadx=10, ipady=3)

    # --- 刷新/更新 ---
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
            step_file = self.config_manager.get_steps_file(self.current_machine, self.current_rate)
            if steps:
                self.status_label.config(
                    text=f"✓ 已配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  共 {len(steps)} 个步骤",
                    foreground="green")
            else:
                self.status_label.config(
                    text=f"○ 未配置: 机种 [{self.current_machine}]  累进 [{self.current_rate}]  —  请点击下方按钮编辑步序",
                    foreground="orange")
            self.file_label.config(text=f"步序文件: {step_file}")
            if steps:
                preview_lines = []
                for i, s in enumerate(steps[:5], 1):
                    t = s.get("type", "")
                    if t == "click":
                        preview_lines.append(f"  {i}. 点击 [{s.get('point_name', '(坐标)')}]")
                    elif t == "type":
                        text = s.get("text", "")
                        preview_lines.append(f"  {i}. 输入 '{text[:20]}...'" if len(text) > 20 else f"  {i}. 输入 '{text}'")
                    elif t == "key":
                        preview_lines.append(f"  {i}. 按键 [{s.get('key', '')}]")
                    elif t == "wait":
                        preview_lines.append(f"  {i}. 等待 {s.get('seconds', '')} 秒")
                if len(steps) > 5:
                    preview_lines.append(f"  ... 还有 {len(steps)-5} 个步骤")
                self.preview_label.config(text="步骤预览:\n" + "\n".join(preview_lines))
            else:
                self.preview_label.config(text="")
            self.edit_step_btn.config(state=tk.NORMAL)
        else:
            if not self.current_machine:
                self.status_label.config(text="请先在上方选择或新增机种", foreground="gray")
            else:
                self.status_label.config(text="请选择或新增一个累进", foreground="gray")
            self.file_label.config(text="")
            self.preview_label.config(text="")
            self.edit_step_btn.config(state=tk.DISABLED)

    # --- 下拉框选择事件 ---
    def _on_machine_select(self, event=None):
        self.current_machine = self.machine_var.get() or None
        self.current_rate = None
        self._refresh_rates()

    def _on_rate_select(self, event=None):
        self.current_rate = self.rate_var.get() or None
        self._update_status()

    # --- 机种操作 ---
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
        if messagebox.askyesno("确认",
                               f"删除机种 '{self.current_machine}' ?\n\n该机型下所有累进及对应的步序文件将一并删除!",
                               parent=self):
            self.config_manager.delete_machine(self.current_machine)
            self.current_machine = None
            self.current_rate = None
            self._refresh_machines()

    def _rename_machine(self):
        if not self.current_machine:
            messagebox.showinfo("提示", "请先选择机种", parent=self)
            return
        new = simpledialog.askstring("重命名机种", "新机种名称:",
                                      parent=self, initialvalue=self.current_machine)
        if new and self.config_manager.rename_machine(self.current_machine, new):
            self.current_machine = new
            self._refresh_machines()
        elif new and new != self.current_machine:
            messagebox.showwarning("提示", "机种已存在", parent=self)

    # --- 累进操作 ---
    def _add_rate(self):
        if not self.current_machine:
            messagebox.showinfo("提示", "请先选择机种", parent=self)
            return
        r = simpledialog.askstring("新增累进", f"为机种 [{self.current_machine}] 新增累进值:", parent=self)
        if r and self.config_manager.add_rate(self.current_machine, r):
            self.current_rate = r
            self._refresh_rates()
        elif r:
            messagebox.showwarning("提示", "该累进已存在", parent=self)

    def _delete_rate(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        if messagebox.askyesno("确认",
                               f"删除累进 '{self.current_rate}' ?\n\n该累进对应的步序文件将一并删除!",
                               parent=self):
            self.config_manager.delete_rate(self.current_machine, self.current_rate)
            self.current_rate = None
            self._refresh_rates()

    def _rename_rate(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        new = simpledialog.askstring("重命名累进", "新累进值:",
                                      parent=self, initialvalue=self.current_rate)
        if new and self.config_manager.rename_rate(self.current_machine, self.current_rate, new):
            self.current_rate = new
            self._refresh_rates()
        elif new and new != self.current_rate:
            messagebox.showwarning("提示", "该累进已存在", parent=self)

    # --- 步序编辑 ---
    def _edit_steps(self):
        if not self.current_machine or not self.current_rate:
            messagebox.showinfo("提示", "请先选择机种和累进", parent=self)
            return
        steps = self.config_manager.get_steps(self.current_machine, self.current_rate)
        dlg = StepEditorDialog(self, self.config_manager, self.current_machine, self.current_rate, steps)
        self.wait_window(dlg)
        self._update_status()