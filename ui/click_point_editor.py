import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core.constants import BUTTON_DISPLAY_VALUES, BUTTON_FROM_DISPLAY, BUTTON_LABELS, UISettings
from core.logger import get_logger
from core.recorder import ClickRecorder

logger = get_logger(__name__)


class ClickPointEditorDialog(tk.Toplevel):
    def __init__(self, master, config_manager):
        super().__init__(master)
        self.title("点击位置编辑")
        self.geometry(UISettings.CLICK_POINT_EDITOR_SIZE)
        self.minsize(550, 400)
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
        ttk.Button(top, text="修改选中", command=self._edit_point, width=12).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(top, text="删除选中", command=self._delete_point, width=12).pack(
            side=tk.LEFT, padx=3
        )

        self.status_label = ttk.Label(top, text="", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=15)

        hint = ttk.Label(
            self,
            text="说明: 点击 \"新增坐标\" 后, 窗口会变淡, 请在目标位置点击一次鼠标(左键/右键/双击)来记录坐标。\n每个坐标都会记录点击的按键方式, 后续在步序编辑中使用该坐标时会沿用此按键方式。",
            foreground="gray",
            padding=(10, 0),
        )
        hint.pack(fill=tk.X)

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
            btn_label = BUTTON_LABELS.get(btn, btn)
            self.tree.insert(
                "", tk.END, values=(name, data.get("x", ""), data.get("y", ""), btn_label)
            )

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
                foreground="green",
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
