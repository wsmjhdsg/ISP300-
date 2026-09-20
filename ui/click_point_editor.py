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

logger = get_logger(__name__)


class ClickPointEditorDialog(tk.Toplevel):
    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("点击位置编辑")
        self.geometry(UISettings.CLICK_POINT_EDITOR_SIZE)
        self.minsize(550, 400)
        self.configure(bg=UISettings.COLORS["bg_window"])
        self.config_manager = config_manager
        self.recorder = None
        self.pending_name = None

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Button(top, text="新增坐标(点击记录)", command=self._add_point, width=18).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(top, text="新增控件(枚举ISP300)", command=self._add_control, width=20).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(top, text="修改选中", command=self._edit_point, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(top, text="删除选中", command=self._delete_point, width=12).pack(
            side=tk.LEFT, padx=3
        )

        self.status_label = ttk.Label(top, text="", foreground=UISettings.COLORS["info"])
        self.status_label.pack(side=tk.LEFT, padx=15)

        hint = ttk.Label(
            self,
            text="说明: \"新增坐标\" 后点击目标位置记录屏幕坐标; \"新增控件\" 枚举 ISP300 的按钮/下拉框/输入框等控件按类型和标识定位(抗窗口移动)。\n每个点都会记录按键方式, 在步序编辑中使用该点时沿用此按键方式。",
            foreground=UISettings.COLORS["text_secondary"],
            padding=(10, 0),
        )
        hint.pack(fill=tk.X)

        cols = ("name", "kind", "locator", "button")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        self.tree.heading("name", text="名称")
        self.tree.heading("kind", text="类型")
        self.tree.heading("locator", text="定位信息")
        self.tree.heading("button", text="按键方式")
        self.tree.column("name", width=150)
        self.tree.column("kind", width=60, anchor=tk.CENTER)
        self.tree.column("locator", width=220)
        self.tree.column("button", width=100, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda e: self._edit_point())

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
        dlg.geometry("560x420")
        dlg.minsize(480, 320)
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        result = {"control": None}

        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        row_filter = ttk.Frame(frm)
        row_filter.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row_filter, text="过滤:").pack(side=tk.LEFT)
        filter_var = tk.StringVar()
        ttk.Entry(row_filter, textvariable=filter_var, width=30).pack(side=tk.LEFT, padx=5)

        cols = ("ctype", "title", "aid")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        tree.heading("ctype", text="类型")
        tree.heading("title", text="标题")
        tree.heading("aid", text="automation_id")
        tree.column("ctype", width=100)
        tree.column("title", width=200)
        tree.column("aid", width=180)
        tree.pack(fill=tk.BOTH, expand=True)

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

        btn_bar = ttk.Frame(frm)
        btn_bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_bar, text="确定", command=confirm, width=12).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(btn_bar, text="取消", command=dlg.destroy, width=12).pack(
            side=tk.RIGHT, padx=5
        )

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
        dlg.geometry("380x280")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="X坐标:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=0, column=0, sticky=tk.W, pady=8
        )
        x_var = tk.StringVar(value=str(data.get("x", 0)))
        ttk.Entry(frm, textvariable=x_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="Y坐标:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=1, column=0, sticky=tk.W, pady=8
        )
        y_var = tk.StringVar(value=str(data.get("y", 0)))
        ttk.Entry(frm, textvariable=y_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="按键方式:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=2, column=0, sticky=tk.W, pady=8
        )
        btn_var = tk.StringVar(value=data.get("button", "left"))
        btn_combo = ttk.Combobox(
            frm,
            textvariable=btn_var,
            values=list(BUTTON_DISPLAY_VALUES.values()),
            width=18,
            state="readonly",
        )
        current_btn = data.get("button", "left")
        btn_combo.set(BUTTON_DISPLAY_VALUES.get(current_btn, BUTTON_DISPLAY_VALUES["left"]))
        btn_combo.grid(row=2, column=1, sticky=tk.W, pady=8)

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

        ttk.Button(frm, text="保存", command=save, width=12).grid(
            row=3, column=0, columnspan=2, pady=15
        )

    def _edit_control_point(self, name, data):
        dlg = tk.Toplevel(self)
        dlg.title(f"编辑控件: {name}")
        dlg.geometry("440x260")
        dlg.configure(bg=UISettings.COLORS["bg_window"])
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ctype = data.get("control_type", "")
        title = data.get("title", "")
        auto_id = data.get("auto_id", "")

        ttk.Label(frm, text="类型:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=0, column=0, sticky=tk.W, pady=8
        )
        ttk.Label(frm, text=ctype or "-").grid(row=0, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="标题:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=1, column=0, sticky=tk.W, pady=8
        )
        ttk.Label(frm, text=title or "-").grid(row=1, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="automation_id:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=2, column=0, sticky=tk.W, pady=8
        )
        ttk.Label(frm, text=auto_id or "-").grid(row=2, column=1, sticky=tk.W, pady=8)

        ttk.Label(frm, text="按键方式:", font=(UISettings.FONT_FAMILY, 10)).grid(
            row=3, column=0, sticky=tk.W, pady=8
        )
        btn_var = tk.StringVar(value=data.get("button", "left"))
        btn_combo = ttk.Combobox(
            frm,
            textvariable=btn_var,
            values=list(BUTTON_DISPLAY_VALUES.values()),
            width=18,
            state="readonly",
        )
        btn_combo.set(BUTTON_DISPLAY_VALUES.get(data.get("button", "left"), BUTTON_DISPLAY_VALUES["left"]))
        btn_combo.grid(row=3, column=1, sticky=tk.W, pady=8)

        def save():
            btn_display = btn_var.get()
            btn_val = BUTTON_FROM_DISPLAY.get(btn_display, "left")
            self.config_manager.update_control_point(name, ctype, title, auto_id, btn_val)
            self.status_label.config(text=f"已更新: {name}")
            self._refresh()
            dlg.destroy()

        ttk.Button(frm, text="保存", command=save, width=12).grid(
            row=4, column=0, columnspan=2, pady=15
        )
