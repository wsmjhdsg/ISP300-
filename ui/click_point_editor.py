import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core.constants import (
    BUTTON_DISPLAY_VALUES,
    BUTTON_FROM_DISPLAY,
    BUTTON_LABELS,
    ClickPointTypes,
    UISettings,
)
from core.logger import get_logger
from core.recorder import ClickRecorder
from core.ui_scale import fit_window_to_content
from ui.styles import (
    ButtonFlow,
    apply_responsive_treeview_columns,
    fit_window_to_screen,
)

logger = get_logger(__name__)


class ClickPointEditorDialog(tk.Toplevel):
    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("点击位置编辑")
        self.configure(bg=UISettings.COLORS["bg_window"])
        self.config_manager = config_manager
        self.recorder = None
        self.pending_name = None

        self._build_ui()
        self._refresh()
        # 内容已构建: 按"实际内容 + 首选"收敛尺寸并居中(小屏不越界, 大屏不局促)
        fit_window_to_content(
            self, UISettings.CLICK_POINT_EDITOR_SIZE, UISettings.CLICK_POINT_EDITOR_MINSIZE
        )
        self.transient(master)

    def _build_ui(self):
        colors = UISettings.COLORS

        top = ttk.Frame(self, padding=(UISettings.PAD_MD, UISettings.PAD_SM))
        top.pack(fill=tk.X)

        # 工具条: 自动换行, 窄窗口下折成两行而不是把按钮挤掉/文字截断
        toolbar = ButtonFlow(top, padding=(0, 2))
        toolbar.pack(fill=tk.X)
        toolbar.add(
            "新增坐标(点击记录)", self._add_point, width=UISettings.BTN_WIDTH_LG
        )
        toolbar.add(
            "新增控件(枚举ISP300)", self._add_control, width=UISettings.BTN_WIDTH_LG
        )
        toolbar.add("修改选中", self._edit_point, width=UISettings.BTN_WIDTH_MD)
        toolbar.add("删除选中", self._delete_point, width=UISettings.BTN_WIDTH_MD)

        # 状态行: 与工具条同宽, 长文案自动换行(不撑出横向滚动条)
        self.status_label = ttk.Label(
            top,
            text="",
            foreground=colors["info"],
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=560,
        )
        self.status_label.pack(fill=tk.X, pady=(UISettings.PAD_SM, 0), anchor=tk.W)

        self.hint = ttk.Label(
            self,
            text=(
                "说明: \"新增坐标\" 后点击目标位置记录屏幕坐标; \"新增控件\" 枚举 ISP300 的"
                "按钮/下拉框/输入框等控件按类型和标识定位(抗窗口移动)。\n"
                "每个点都会记录按键方式, 在步序编辑中使用该点时沿用此按键方式。"
            ),
            foreground=colors["text_secondary"],
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=560,
        )
        self.hint.pack(fill=tk.X, padx=UISettings.PAD_MD)

        cols = ("name", "kind", "locator", "button")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        self.tree.heading("name", text="名称")
        self.tree.heading("kind", text="类型")
        self.tree.heading("locator", text="定位信息")
        self.tree.heading("button", text="按键方式")
        self.tree.column("name", width=150, anchor=tk.W)
        self.tree.column("kind", width=60, anchor=tk.CENTER, stretch=False)
        self.tree.column("locator", width=220, anchor=tk.W)
        self.tree.column("button", width=100, anchor=tk.CENTER, stretch=False)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=UISettings.PAD_MD, pady=UISettings.PAD_MD)
        self.tree.bind("<Double-1>", lambda e: self._edit_point())
        # 名称/定位信息吸收多余宽度, 类型与按键保持固定 -> 永不横向滚动
        apply_responsive_treeview_columns(self.tree, weights=[2, 0, 4, 0])

        # 窗口宽度变化: 同步提示文字与状态文字的换行宽度
        self.bind("<Configure>", self._on_resize, add="+")

    def _on_resize(self, event=None):
        if event is not None and event.widget is not self:
            return
        try:
            w = self.winfo_width()
        except Exception:
            return
        if getattr(self, "_last_w", None) == w:
            return
        self._last_w = w
        wrap = max(240, w - 40)
        for lbl in (getattr(self, "hint", None), getattr(self, "status_label", None)):
            if lbl is not None:
                try:
                    lbl.configure(wraplength=wrap)
                except Exception:
                    pass

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, data in self.config_manager.click_points.items():
            btn = data.get("button", "left")
            btn_label = BUTTON_LABELS.get(btn, btn)
            if data.get("type") == ClickPointTypes.CONTROL:
                ctype = data.get("control_type", "")
                title = data.get("title", "")
                auto_id = data.get("auto_id", "")
                locator = f"{ctype} · {title or auto_id}" if ctype else (title or auto_id)
                self.tree.insert("", tk.END, values=(name, "控件", locator, btn_label))
            else:
                locator = f"({data.get('x', '')}, {data.get('y', '')})"
                self.tree.insert("", tk.END, values=(name, "坐标", locator, btn_label))

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
            btn_label = BUTTON_LABELS.get(btn, btn)
            self.config_manager.add_click_point(name, point["x"], point["y"], btn)
            self.status_label.config(
                text=f"[已记录] {name} = ({point['x']},{point['y']}) {btn_label}点击",
                foreground=UISettings.COLORS["success"],
            )
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
        self.status_label.config(
            text="已取消记录", foreground=UISettings.COLORS["text_secondary"]
        )

    def _add_control(self):
        from core.isp_controls import enumerate_controls

        try:
            controls = enumerate_controls()
        except Exception as e:
            messagebox.showerror("错误", f"枚举 ISP300 控件失败:\n{e}", parent=self)
            return
        if not controls:
            messagebox.showinfo(
                "提示",
                "未找到 ISP300 窗口或没有可用的控件。\n请先启动 ISP300 软件。",
                parent=self,
            )
            return

        picked = self._pick_control(controls)
        if not picked:
            return

        ctype = picked.get("control_type", "")
        title = picked.get("title", "")
        auto_id = picked.get("auto_id", "")
        default_name = title or auto_id or ctype
        name = simpledialog.askstring(
            "新增控件", "请输入控件名称:", initialvalue=default_name, parent=self
        )
        if not name:
            return
        if name in self.config_manager.click_points:
            if not messagebox.askyesno("确认", f"名称 '{name}' 已存在, 是否覆盖?", parent=self):
                return

        self.config_manager.add_control_point(name, ctype, title, auto_id, "left")
        self.status_label.config(
            text=f"[已添加] 控件 {name} = {ctype} {title or auto_id}",
            foreground=UISettings.COLORS["success"],
        )
        self._refresh()

    def _pick_control(self, controls):
        dlg = tk.Toplevel(self)
        dlg.title("选择 ISP300 控件")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        result = {"control": None}

        frm = ttk.Frame(dlg, padding=UISettings.PAD_MD)
        frm.pack(fill=tk.BOTH, expand=True)

        row_filter = ttk.Frame(frm)
        row_filter.pack(fill=tk.X, pady=(0, UISettings.PAD_SM))
        ttk.Label(row_filter, text="过滤:").pack(side=tk.LEFT)
        filter_var = tk.StringVar()
        filter_entry = ttk.Entry(row_filter, textvariable=filter_var)
        filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(UISettings.PAD_XS, 0))
        filter_entry.focus_set()

        cols = ("ctype", "title", "aid")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=13)
        tree.heading("ctype", text="类型")
        tree.heading("title", text="标题")
        tree.heading("aid", text="automation_id")
        tree.column("ctype", width=100, stretch=False)
        tree.column("title", width=200)
        tree.column("aid", width=180)
        tree.pack(fill=tk.BOTH, expand=True)
        # 标题列吸收多余宽度, 类型列固定 -> 窄窗口不产生横向滚动
        apply_responsive_treeview_columns(tree, weights=[0, 2, 1])

        def refresh(filter_text=""):
            for i in tree.get_children():
                tree.delete(i)
            ft = filter_text.lower()
            for c in controls:
                ctype = c.get("control_type", "")
                title = c.get("title", "")
                aid = c.get("auto_id", "")
                if ft and ft not in (ctype + " " + title + " " + aid).lower():
                    continue
                tree.insert("", tk.END, values=(ctype, title, aid))

        refresh()
        filter_var.trace_add("write", lambda *a: refresh(filter_var.get()))

        def confirm(evt=None):
            sel = tree.selection()
            if not sel:
                return
            values = tree.item(sel[0])["values"]
            result["control"] = {
                "control_type": values[0],
                "title": values[1],
                "auto_id": values[2],
            }
            dlg.destroy()

        tree.bind("<Double-1>", confirm)
        filter_entry.bind("<Return>", lambda e: confirm())

        btn_bar = ttk.Frame(frm)
        btn_bar.pack(fill=tk.X, pady=(UISettings.PAD_SM, 0))
        ttk.Button(btn_bar, text="确定", command=confirm, width=UISettings.BTN_WIDTH_MD).pack(
            side=tk.RIGHT, padx=(UISettings.PAD_XS, 0)
        )
        ttk.Button(btn_bar, text="取消", command=dlg.destroy, width=UISettings.BTN_WIDTH_MD).pack(
            side=tk.RIGHT, padx=UISettings.PAD_XS
        )

        # 几何收敛放到控件构建之后(此时才量得出内容尺寸)
        fit_window_to_screen(dlg, "620x460", (480, 340))
        dlg.wait_window()
        return result["control"]

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

        if data.get("type") == ClickPointTypes.CONTROL:
            self._edit_control_point(name, data)
        else:
            self._edit_coord_point(name, data)

    def _edit_coord_point(self, name, data):
        dlg = tk.Toplevel(self)
        dlg.title(f"编辑坐标: {name}")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=UISettings.PAD_LG)
        frm.pack(fill=tk.BOTH, expand=True)
        # 第 1 列放输入控件并吸收多余宽度 -> 窗口变宽时输入框跟着变宽而非留白
        frm.grid_columnconfigure(1, weight=1)

        ttk.Label(frm, text="X坐标:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
        )
        x_var = tk.StringVar(value=str(data.get("x", 0)))
        ttk.Entry(frm, textvariable=x_var).grid(
            row=0, column=1, sticky=tk.EW, pady=UISettings.PAD_SM
        )

        ttk.Label(frm, text="Y坐标:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
        )
        y_var = tk.StringVar(value=str(data.get("y", 0)))
        ttk.Entry(frm, textvariable=y_var).grid(
            row=1, column=1, sticky=tk.EW, pady=UISettings.PAD_SM
        )

        ttk.Label(frm, text="按键方式:").grid(
            row=2, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
        )
        btn_var = tk.StringVar(value=data.get("button", "left"))
        btn_combo = ttk.Combobox(
            frm,
            textvariable=btn_var,
            values=list(BUTTON_DISPLAY_VALUES.values()),
            state="readonly",
        )
        current_btn = data.get("button", "left")
        btn_combo.set(BUTTON_DISPLAY_VALUES.get(current_btn, BUTTON_DISPLAY_VALUES["left"]))
        btn_combo.grid(row=2, column=1, sticky=tk.EW, pady=UISettings.PAD_SM)

        def save():
            try:
                x_val = int(x_var.get())
                y_val = int(y_var.get())
            except ValueError:
                messagebox.showerror("错误", "坐标必须是数字", parent=dlg)
                return
            btn_display = btn_var.get()
            btn_val = BUTTON_FROM_DISPLAY.get(btn_display, "left")
            self.config_manager.update_click_point(name, x_val, y_val, btn_val)
            self.status_label.config(text=f"已更新: {name}")
            self._refresh()
            dlg.destroy()

        bar = ttk.Frame(frm)
        bar.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(UISettings.PAD_LG, 0))
        ttk.Button(bar, text="保存", command=save, width=UISettings.BTN_WIDTH_MD).pack(side=tk.RIGHT)
        ttk.Button(bar, text="取消", command=dlg.destroy, width=UISettings.BTN_WIDTH_MD).pack(
            side=tk.RIGHT, padx=(0, UISettings.PAD_SM)
        )

        fit_window_to_screen(dlg, "420x300", (360, 260))
        dlg.wait_window()

    def _edit_control_point(self, name, data):
        dlg = tk.Toplevel(self)
        dlg.title(f"编辑控件: {name}")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=UISettings.PAD_LG)
        frm.pack(fill=tk.BOTH, expand=True)
        frm.grid_columnconfigure(1, weight=1)

        ctype = data.get("control_type", "")
        title = data.get("title", "")
        auto_id = data.get("auto_id", "")

        rows = [("类型:", ctype or "-"), ("标题:", title or "-"), ("automation_id:", auto_id or "-")]
        for r, (label, value) in enumerate(rows):
            ttk.Label(frm, text=label).grid(
                row=r, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
            )
            # 值可能很长(automation_id 尤甚): 用可换行标签, 避免撑宽窗口
            ttk.Label(
                frm, text=value, justify=tk.LEFT, anchor=tk.W, wraplength=260
            ).grid(row=r, column=1, sticky=tk.EW, pady=UISettings.PAD_SM)

        ttk.Label(frm, text="按键方式:").grid(
            row=3, column=0, sticky=tk.W, padx=(0, UISettings.PAD_SM), pady=UISettings.PAD_SM
        )
        btn_var = tk.StringVar(value=data.get("button", "left"))
        btn_combo = ttk.Combobox(
            frm,
            textvariable=btn_var,
            values=list(BUTTON_DISPLAY_VALUES.values()),
            state="readonly",
        )
        btn_combo.set(
            BUTTON_DISPLAY_VALUES.get(data.get("button", "left"), BUTTON_DISPLAY_VALUES["left"])
        )
        btn_combo.grid(row=3, column=1, sticky=tk.EW, pady=UISettings.PAD_SM)

        def save():
            btn_display = btn_var.get()
            btn_val = BUTTON_FROM_DISPLAY.get(btn_display, "left")
            self.config_manager.update_control_point(name, ctype, title, auto_id, btn_val)
            self.status_label.config(text=f"已更新: {name}")
            self._refresh()
            dlg.destroy()

        bar = ttk.Frame(frm)
        bar.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=(UISettings.PAD_LG, 0))
        ttk.Button(bar, text="保存", command=save, width=UISettings.BTN_WIDTH_MD).pack(side=tk.RIGHT)
        ttk.Button(bar, text="取消", command=dlg.destroy, width=UISettings.BTN_WIDTH_MD).pack(
            side=tk.RIGHT, padx=(0, UISettings.PAD_SM)
        )

        fit_window_to_screen(dlg, "480x320", (400, 280))
        dlg.wait_window()
