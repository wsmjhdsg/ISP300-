"""UI 主题与公共控件工厂: 浅色工业风。

色板 token 全部来自 core.constants.UISettings.COLORS, 本文件不出现裸 hex。
风格要点: 铝灰浅底 + 白色卡片 + 钢灰描边 + 信号橙主操作 + 工控红停止;
标题字体用 Bahnschrift(工程 DIN 风), 正文 Segoe UI, 日志等宽 Consolas。
"""
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Optional

from core.constants import UISettings


def apply_ttk_theme(root: tk.Tk) -> None:
    """应用浅色工业风 ttk 主题。"""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    elif "default" in style.theme_names():
        style.theme_use("default")

    root.configure(bg=UISettings.COLORS["bg_window"])

    family = UISettings.FONT_FAMILY
    title_font = UISettings.FONT_TITLE
    c = UISettings.COLORS

    style.configure(".", font=(family, 10))

    # ---------- 容器框架: 铝灰窗底 / 浅灰面板 / 白卡片 ----------
    style.configure("TFrame", background=c["bg_card"])
    style.configure("Window.TFrame", background=c["bg_window"])
    style.configure("Panel.TFrame", background=c["bg_panel"])
    style.configure("Card.TFrame", background=c["bg_card"])

    # ---------- 标签 ----------
    style.configure("TLabel", background=c["bg_card"], foreground=c["text"])
    style.configure("Window.TLabel", background=c["bg_window"], foreground=c["text"])
    style.configure("Panel.TLabel", background=c["bg_panel"], foreground=c["text"])
    style.configure(
        "Title.TLabel",
        font=(title_font, 13, "bold"),
        foreground=c["text"],
        background=c["bg_card"],
    )
    style.configure(
        "Section.TLabel",
        font=(family, 10, "bold"),
        foreground=c["text"],
        background=c["bg_card"],
    )
    # 次要说明文字(统一灰阶, 避免各处手写 foreground)
    style.configure(
        "Hint.TLabel", background=c["bg_card"], foreground=c["text_secondary"]
    )
    style.configure(
        "Status.TLabel", background=c["bg_card"], foreground=c["text_secondary"]
    )

    # ---------- 按钮: 直角钢灰描边(工业感) ----------
    # 状态语义: 正常=白底钢灰描边 / 悬停=浅灰底 / 按下=更深灰底 / 禁用=浅面板底+灰字
    style.configure(
        "TButton",
        font=(family, 10),
        padding=(UISettings.BTN_PAD_X, UISettings.BTN_PAD_Y),
        background=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        focuscolor=c["accent"],
        relief=tk.RAISED,
        anchor=tk.CENTER,
    )
    style.map(
        "TButton",
        background=[
            ("disabled", c["bg_panel"]),
            ("pressed", c["bg_hover"]),
            ("active", c["bg_hover"]),
        ],
        foreground=[("disabled", c["text_secondary"])],
        bordercolor=[("active", c["border"]), ("disabled", c["border_light"])],
        relief=[("pressed", tk.SUNKEN), ("active", tk.RAISED)],
    )

    # 紧凑按钮变体: 用于工具条等横向空间紧张处
    style.configure("Compact.TButton", padding=(UISettings.PAD_SM, 5), font=(family, 9))
    style.map(
        "Compact.TButton",
        background=[
            ("disabled", c["bg_panel"]),
            ("pressed", c["bg_hover"]),
            ("active", c["bg_hover"]),
        ],
        foreground=[("disabled", c["text_secondary"])],
    )

    # ---------- 复选框: 与白卡片同底(clam 默认灰底会与卡片撞色) ----------
    style.configure(
        "TCheckbutton",
        background=c["bg_card"],
        foreground=c["text"],
        focuscolor=c["accent"],
        indicatorcolor=c["bg_card"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", c["bg_card"]), ("disabled", c["bg_card"])],
        foreground=[("disabled", c["text_secondary"])],
    )

    # ---------- 输入控件 ----------
    style.configure(
        "TEntry",
        fieldbackground=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        padding=UISettings.ENTRY_PAD,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", c["accent"])],
        fieldbackground=[("disabled", c["bg_panel"])],
        foreground=[("disabled", c["text_secondary"])],
    )

    # 只读路径选择框(Path.TEntry): 用于「文件路径 / 固件目录 / 软件路径」等
    # 只允许弹窗选择、不允许手输的字段。readonly 态需显式映射, 否则会落到
    # Tk 默认的灰底灰字, 在浅色工业风下对比度不达标(见 §6.2 打磨底线)。
    # 视觉上刻意做成"可点击的输入框": 白底 + 正常字色 + 手型光标。
    style.configure(
        "Path.TEntry",
        fieldbackground=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        padding=UISettings.ENTRY_PAD,
    )
    style.map(
        "Path.TEntry",
        bordercolor=[("focus", c["accent"]), ("active", c["accent"])],
        fieldbackground=[
            ("readonly", c["bg_card"]),
            ("focus", c["bg_card"]),
            ("active", c["bg_card"]),
            ("disabled", c["bg_panel"]),
        ],
        foreground=[
            ("readonly", c["text"]),
            ("disabled", c["text_secondary"]),
        ],
    )

    style.configure(
        "TCombobox",
        fieldbackground=c["bg_card"],
        background=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        arrowcolor=c["text_secondary"],
        padding=UISettings.ENTRY_PAD,
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", c["bg_card"]),
            ("active", c["bg_card"]),
            ("focus", c["bg_card"]),
            ("disabled", c["bg_panel"]),
        ],
        bordercolor=[("focus", c["accent"])],
        selectbackground=[("readonly", c["bg_card"])],
        selectforeground=[("readonly", c["text"])],
        foreground=[("disabled", c["text_secondary"])],
        arrowcolor=[("disabled", c["text_secondary"])],
    )

    # ---------- 分组框: 钢灰细描边 ----------
    style.configure(
        "TLabelframe",
        background=c["bg_card"],
        bordercolor=c["border_light"],
        borderwidth=1,
        relief=tk.SOLID,
    )
    style.configure(
        "TLabelframe.Label",
        font=(family, 10, "bold"),
        background=c["bg_card"],
        foreground=c["text"],
    )

    # ---------- 表格 ----------
    style.configure(
        "Treeview",
        font=(family, 9),
        rowheight=UISettings.ROW_HEIGHT,
        background=c["bg_card"],
        fieldbackground=c["bg_card"],
        foreground=c["text"],
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", c["accent_soft"])],
        foreground=[("selected", c["text"])],
    )
    style.configure(
        "Treeview.Heading",
        font=(family, 9, "bold"),
        background=c["bg_panel"],
        foreground=c["text"],
        bordercolor=c["border_light"],
        borderwidth=1,
        relief=tk.FLAT,
        padding=(UISettings.PAD_SM, 4),
    )
    style.map("Treeview.Heading", background=[("active", c["bg_hover"])])

    # ---------- 进度条: 信号橙 ----------
    style.configure(
        "TProgressbar",
        thickness=16,
        background=c["accent"],
        troughcolor=c["bg_hover"],
        bordercolor=c["border_light"],
        lightcolor=c["accent"],
        darkcolor=c["accent"],
    )

    # ---------- 分隔线 ----------
    style.configure("TSeparator", background=c["border_light"])

    # ---------- 滚动条 ----------
    style.configure(
        "Vertical.TScrollbar",
        background=c["bg_hover"],
        troughcolor=c["bg_card"],
        bordercolor=c["bg_card"],
        arrowcolor=c["text_secondary"],
        width=12,
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=c["bg_hover"],
        troughcolor=c["bg_card"],
        bordercolor=c["bg_card"],
        arrowcolor=c["text_secondary"],
        width=12,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", c["border_light"]), ("pressed", c["border"])],
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", c["border_light"]), ("pressed", c["border"])],
    )


# ---------------------------------------------------------------------- #
# 响应式布局辅助
# ---------------------------------------------------------------------- #
def _screen_workarea(widget: tk.Misc) -> tuple:
    """返回当前屏幕可用区域 (宽, 高)。取主屏尺寸并扣除任务栏等保留区。

    尺寸单位与 Tk 的 geometry 一致(逻辑像素), 因此高 DPI 缩放已由 Tk 处理,
    无需自行换算 DPI。异常时回退到 1920x1080 保守值。
    """
    try:
        w = widget.winfo_screenwidth()
        h = widget.winfo_screenheight()
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 1920, 1080


def fit_window_to_screen(
    window: tk.Misc,
    preferred: str,
    minsize: Optional[tuple] = None,
    ratio: Optional[float] = None,
) -> None:
    """把窗口几何收敛到屏幕可用范围内, 并居中显示。

    规则(从第一性原则出发: 窗口不得大于屏幕, 也不得小到装不下内容):
    1. 解析 preferred("宽x高")作为【首选】尺寸;
    2. 上限 = 屏幕可用区 * ratio(默认 WINDOW_SCREEN_RATIO), 超出则收缩;
    3. 下限 = minsize 与 preferred 取较小者(不与首选冲突), 防止屏幕过小时
       下限反而超过屏幕导致无法显示;
    4. 居中摆放, 保证多显示器/小屏笔记本上都能完整看到窗口。

    这样大屏获得更大的初始窗口(不局促), 小屏自动收缩且不溢出屏幕(无横向滚动条)。

    注意: Tk 在窗口首次映射前读取 geometry() 会返回 "1x1", 这是正常现象,
    实际尺寸在 update 后才生效, 不影响本函数设置结果。
    """
    try:
        pw, ph = (int(x) for x in preferred.lower().split("x"))
    except Exception:
        pw, ph = 780, 720

    scr_w, scr_h = _screen_workarea(window)
    limit_w = int(scr_w * (ratio if ratio is not None else UISettings.WINDOW_SCREEN_RATIO))
    limit_h = int(scr_h * (ratio if ratio is not None else UISettings.WINDOW_SCREEN_RATIO))

    # 首选尺寸夹在 (屏幕上限) 之内
    w = min(pw, limit_w)
    h = min(ph, limit_h)

    # 下限同样不得超过屏幕上限, 否则小屏上窗口会顶破屏幕
    if minsize:
        min_w = min(minsize[0], limit_w)
        min_h = min(minsize[1], limit_h)
        window.minsize(min_w, min_h)

    x = max(0, (scr_w - w) // 2)
    y = max(0, (scr_h - h) // 3)  # 略偏上, 视觉更稳
    window.geometry(f"{w}x{h}+{x}+{y}")


class ScrollableFrame(ttk.Frame):
    """可垂直滚动的容器: 内容超出可视区时出现纵向滚动条, 而非被裁掉。

    用途: 小屏/窗口被压矮时, 表单类页面(步序编辑等)仍能访问全部控件。
    对外接口与原 ttk.Frame 兼容: 把自己当作父容器使用 self.body 挂载子控件。
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        colors = UISettings.COLORS

        self._canvas = tk.Canvas(
            self, highlightthickness=0, bd=0, bg=colors["bg_window"]
        )
        self._vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 真正承载内容的容器
        self.body = ttk.Frame(self._canvas, style="Window.TFrame")
        self._win = self._canvas.create_window((0, 0), window=self.body, anchor=tk.NW)

        self.body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # 鼠标进入时才绑定滚轮, 避免抢占其他区域滚动
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_body_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._auto_hide_scrollbar()

    def _on_canvas_configure(self, event):
        # 内容宽度始终跟随画布宽度 -> 不产生横向滚动条, 只纵向滚动
        self._canvas.itemconfigure(self._win, width=event.width)
        self._auto_hide_scrollbar()

    def _auto_hide_scrollbar(self):
        """内容装得下时隐藏滚动条, 避免视觉噪音。"""
        try:
            need = self.body.winfo_reqheight() > self._canvas.winfo_height()
            if need and not self._vsb.winfo_ismapped():
                self._vsb.pack(side=tk.RIGHT, fill=tk.Y)
            elif not need and self._vsb.winfo_ismapped():
                self._vsb.pack_forget()
        except Exception:
            pass

    def _bind_wheel(self, _event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        try:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass


class ButtonFlow(ttk.Frame):
    """自动换行的按钮流式布局容器。

    问题背景: 工具条用 pack(side=LEFT) 平铺时, 窗口变窄按钮会被裁掉(文字截断)。
    本容器按容器实际宽度动态计算每行可放按钮数, 窄则换行、宽则单行。

    实现要点(Tk 陷阱, 全部为实测踩坑):
    1. 若把所有按钮 grid 到同一个网格, grid 的每一列宽度取【该列全部行】的最大
       请求宽度 —— 第 2 行放到第 1 列的按钮会把第 1 列整体撑宽, 造成"每行单独算
       都没超, 合起来却溢出"。故改为"每行一个子 Frame + 内部 pack(side=LEFT)"。
    2. 行 Frame 的 grid sticky 必须带 N(北)。只给 W 时行 Frame 会在网格单元内
       垂直居中, 容器被拉高后上方出现一片空白。
    3. 按钮的 master 必须就是它所在的行 Frame。ttk 的 pack(in_=...) 只能把控件
       放进其祖先链上的容器, 而按钮若建在 ButtonFlow 下、行 Frame 是它的兄弟,
       pack(in_=frame) 不会生效(按钮会神秘消失)。因此重排时按需重建按钮,
       直接以行 Frame 作为 parent。
    4. 容器宽度在首次映射前恒为 1, 必须多级回退取宽度, 否则重排会永久提前退出。

    用法:
        flow = ButtonFlow(parent)
        flow.pack(fill=tk.X)
        flow.add("末尾新增", self._add, width=12)
        flow.add("上移", lambda: self._move(-1), width=10)
    """

    def __init__(self, master, gap: int = UISettings.PAD_XS, **kwargs):
        super().__init__(master, **kwargs)
        self._gap = gap
        # [(text, command, width, style)] 只存"规格", 按钮实例按需重建
        self._specs: list = []
        self._buttons: list = []
        self._rows: list = []           # 当前行 Frame 列表
        self._last_sig = None           # 上次布局签名, 用于跳过无变化的重复重排
        self._pending = False
        self.bind("<Configure>", self._on_configure)

    # ---------- 对外接口 ----------

    def add(self, text: str, command, width: int = UISettings.BTN_WIDTH_MD,
            style: str = "TButton"):
        """添加一个按钮。重排后按钮实例会被重建, 请通过 flow.buttons 取最新实例。"""
        self._specs.append((text, command, width, style))
        self._last_sig = None
        self._schedule_reflow()
        return self._buttons[-1] if self._buttons else None

    @property
    def buttons(self) -> list:
        """当前实际存在的按钮实例(按添加顺序)。"""
        return list(self._buttons)

    # ---------- 内部实现 ----------

    def _schedule_reflow(self):
        """合并多次 add 的重排请求, 避免批量添加时反复重建造成闪烁。"""
        if self._pending:
            return
        self._pending = True
        try:
            self.after_idle(self._reflow_now)
        except Exception:
            self._pending = False
        # 字体测量完成后再兜底排一次(首帧估算可能偏小)
        try:
            self.after(90, self._reflow_force)
        except Exception:
            pass

    def _reflow_now(self):
        self._pending = False
        self._reflow(force=True)

    def _reflow_force(self):
        self._reflow(force=True)

    def _on_configure(self, event=None):
        self._reflow(event)

    def _pad_x(self) -> int:
        """读取自身左右内边距之和(用于从容器宽度扣掉, 得到真正可用的排布宽度)。

        ttk 的 padding 语义: (水平, 垂直) —— 水平值会同时作用于左右两侧。
        因此左右总量 = 水平值 * 2。ttk 可能把 padding 归一为字符串或含 4 个
        分量的元组, 这里统一按 Tcl 列表逐个解析。
        """
        try:
            pad = self.cget("padding")
        except Exception:
            return 0
        nums = []
        try:
            if isinstance(pad, (tuple, list)):
                for v in pad:
                    nums.append(int(v))
            else:
                for part in str(pad).split():
                    nums.append(int(part))
        except Exception:
            return 0
        if not nums:
            return 0
        if len(nums) == 1:
            return nums[0] * 2          # 单值: 四周同值
        if len(nums) == 2:
            return nums[0] * 2          # (水平, 垂直)
        if len(nums) == 4:
            return nums[0] + nums[2]    # (左, 上, 右, 下)
        return nums[0] * 2

    def _avail_width(self, event=None) -> int:
        """取得可用于排布按钮的宽度(映射前 winfo_width 恒为 1, 需多级回退)。"""
        if event is not None:
            try:
                if event.width > 1:
                    return int(event.width)
            except Exception:
                pass
        try:
            w = self.winfo_width()
            if w > 1:
                return int(w)
        except Exception:
            pass
        try:
            mw = self.master.winfo_width()
            if mw > 1:
                return int(mw)
        except Exception:
            pass
        try:
            mw = self.winfo_toplevel().winfo_width()
            if mw > 1:
                return int(mw)
        except Exception:
            pass
        try:
            return int(self.winfo_screenwidth() * 0.8)
        except Exception:
            return 800

    def _btn_px(self, text: str, chars: int, style: str) -> int:
        """估算按钮像素宽(用于换行判断)。

        重要: 绝不能用按钮的 winfo_width() —— 被 pack 后可能因父容器宽度不足
        而被压缩, 用它做换行判断会陷入"越挤越窄、越窄越不换行"的死循环。
        也不依赖 winfo_reqwidth(): 按钮重排时会被重建, 重建瞬间尺寸为 0。

        公式为实测校准(本主题 + 默认字体):
            width=12 -> 118px, width=10 -> 104px, width=18 -> 160px
        即 ttk 的 width 单位约合 7px/字符, 加上固定内边距约 34px。
        长文案按文字实际字数再取一次较大值, 保证不会被低估。
        """
        px = chars * 7 + 34
        est = len(str(text)) * 8 + 30
        return max(px, est)

    def _compute_rows(self, usable: int) -> list:
        """把按钮规格按可用宽度分行, 返回 [[spec_index, ...], ...]。"""
        rows: list = []
        current: list = []
        used = 0
        for idx, (text, _cmd, width, style) in enumerate(self._specs):
            px = self._btn_px(text, width, style)
            need = px + (self._gap if current else 0)
            if current and used + need > usable:
                rows.append(current)
                current = []
                used = 0
                need = px
            current.append(idx)
            used += need
        if current:
            rows.append(current)
        return rows

    def _reflow(self, event=None, force: bool = False):
        if not self._specs:
            return
        avail = self._avail_width(event)
        if avail <= 1:
            return
        usable = max(1, avail - self._pad_x())
        rows = self._compute_rows(usable)

        signature = tuple(tuple(r) for r in rows)
        if (
            not force
            and signature == self._last_sig
            and len(self._rows) == len(rows)
            and self._layout_ok(rows)
        ):
            return
        self._last_sig = signature

        # 按钮的 parent 必须是其所属行 Frame, 故一律重建(行数不变但按钮缺失时也要重建)
        if not self._layout_ok(rows):
            self._rebuild(rows)

    def _layout_ok(self, rows: list) -> bool:
        """校验按钮实例与行结构是否一致。"""
        try:
            if len(self._rows) != len(rows):
                return False
            total = sum(len(r) for r in rows)
            if len(self._buttons) != total or total != len(self._specs):
                return False
            for row_idx, idxs in enumerate(rows):
                frame = self._rows[row_idx]
                if len(frame.winfo_children()) != len(idxs):
                    return False
            return True
        except Exception:
            return False

    def _rebuild(self, rows: list):
        """按行结构重建: 销毁旧行与旧按钮, 以行 Frame 为 parent 重新创建按钮。"""
        for f in self._rows:
            try:
                f.destroy()
            except Exception:
                pass
        self._rows = []
        self._buttons = []

        for i in range(len(rows)):
            f = ttk.Frame(self)
            # sticky 必须带 N: 只给 W 会让行在网格单元内垂直居中, 上方留白
            f.grid(row=i, column=0, sticky=tk.NW)
            self._rows.append(f)
        self.grid_columnconfigure(0, weight=1)
        for i in range(len(rows)):
            self.grid_rowconfigure(i, weight=0)
        # 末行之后留一个"吸收行", 让按钮组整体靠上紧凑排列
        self.grid_rowconfigure(len(rows), weight=1)

        for row_idx, idxs in enumerate(rows):
            frame = self._rows[row_idx]
            for idx in idxs:
                text, command, width, style = self._specs[idx]
                btn = ttk.Button(frame, text=text, command=command,
                                 width=width, style=style)
                btn.pack(side=tk.LEFT, padx=(0, self._gap), pady=2)
                self._buttons.append(btn)

def apply_responsive_treeview_columns(tree: ttk.Treeview, weights: list) -> None:
    """让 Treeview 各列按权重分配剩余宽度, 消除横向滚动条。

    weights: 与列顺序对应的相对权重列表, 例如 [0, 1, 3, 0] 表示第 2 列固定、
    第 3 列吸收多余空间(数字列通常给 0, 文本列给较大值)。

    实现: 监听控件宽度变化, 按"固定列保持最小宽度, 弹性列按权重分摊剩余"重算列宽。
    """
    cols = tree["columns"]
    if not cols:
        return
    weights = (list(weights) + [0] * len(cols))[: len(cols)]

    # 记录每列的最小宽度(初始设定值)作为不压缩下限
    min_widths = []
    for col in cols:
        try:
            min_widths.append(int(tree.column(col, "width")))
        except Exception:
            min_widths.append(80)

    def _resize(event=None):
        try:
            total = tree.winfo_width()
        except Exception:
            return
        if total <= 1:
            return
        fixed = sum(w for w, wt in zip(min_widths, weights) if wt == 0)
        flex_w = sum(wt for wt in weights if wt > 0)
        # 无弹性列时直接按原宽处理(不做拉伸, 避免内容被拉宽变形)
        if flex_w == 0:
            return
        # Treeview 自身边框 + 可能的纵向滚动条要占用宽度, 必须扣掉;
        # 这个开销随主题变化, 故实测而非常量(常量会导致末列表头被切掉几像素)。
        overhead = max(0, total - sum(_tree_col_widths(tree)))
        remain = max(0, total - fixed - overhead)
        for col, w, wt in zip(cols, min_widths, weights):
            if wt == 0:
                try:
                    tree.column(col, width=w, stretch=False)
                except Exception:
                    pass
            else:
                new_w = max(w, int(remain * wt / flex_w))
                try:
                    tree.column(col, width=new_w, stretch=True)
                except Exception:
                    pass

    tree.bind("<Configure>", _resize, add="+")
    tree.after(120, _resize)  # 首次布局完成后再算一次


def _tree_col_widths(tree: ttk.Treeview) -> list:
    """读取各列当前宽度, 用于推算 Treeview 的固定开销(边框/滚动条)。"""
    widths = []
    for col in tree["columns"]:
        try:
            widths.append(int(tree.column(col, "width")))
        except Exception:
            widths.append(0)
    return widths


def apply_adaptive_tree_height(
    tree: ttk.Treeview,
    min_rows: int = 5,
    reserved_h: int = 0,
    row_height: Optional[int] = None,
    extra_budget: int = 0,
    bottom_widget=None,
) -> None:
    """让 Treeview 显示行数随可用高度自适应, 而不是钉死固定行数。

    第一性原理: 表格的目的是"尽可能多地展示步骤", 能显示几行应当由窗口
    实际剩余空间决定。若把行数写死(如 height=12), 当窗口较矮或上方控件
    (如换行的工具条)变高时, 表格会顽固地索要固定高度, 把下方按钮挤出窗口
    —— 这正是"底部按钮被截断"的成因。

    reserved_h: 除表格可视区外其它区域占用的总高(必须与表格当前高度无关,
                否则会形成循环依赖, 参见调用方的注释)。
    row_height: 单行像素高; 不传则用 Tk 默认字体下的实测值。
    extra_budget: 额外预留的余量(如滚动条/多显示器取整误差)。
    bottom_widget: 位于表格下方的控件(如底部按钮区)。校验时以"它是否仍完整
        落在窗口可视区内"为最终判据 —— 这比比较 tree 与其父容器可靠得多,
        因为父容器本身也会被 pack 压缩, 永远"不溢出"。

    实现要点——为何不"一步算到位"而采用逐行逼近:
    行高与表头开销是 Tk 主题决定的近似值, 直接除法算出的行数常有一两行误差,
    误差累积后正好把底部按钮挤出可视区。因此这里"先算再验、超了就减",
    以"渲染后底部控件不越界"为最终判据, 保证结果一定装得下。
    """
    def _row_h() -> float:
        if row_height and row_height > 0:
            return float(row_height)
        try:
            cur = max(1, int(tree.cget("height")))
            h = tree.winfo_reqheight()
            # reqheight = 表头 + 行数*行高 + 边框, 先扣表头开销再均分
            est = (h - _TREE_CHROME_H) / cur
            if 10 <= est <= 80:
                return est
        except Exception:
            pass
        return 26.0

    def _clipped() -> bool:
        """底部区域内的控件是否被挤出窗口可视区(即"按钮被截断")。

        第一性原则: 只要底部控件不在窗口可视区内, 对用户就是"看不见/被切掉"。
        因此判定必须覆盖三种情况, 缺一不可:
        1. 控件底边超出窗口底边(被切);
        2. 控件底边超出其容器底边(容器被压扁, 内部溢出);
        3. 控件未被映射(容器高度不足以放置子控件时 Tk 直接不显示它)
           —— 这是最严重的情况, 却最容易被"只看 ismapped"的写法漏掉。

        绝不能加 `if not w.winfo_ismapped(): continue` 这种跳过条件:
        未映射恰恰是最该报警的状态。
        """
        if bottom_widget is None:
            return False
        try:
            win = tree.winfo_toplevel()
            win_h = win.winfo_height()
            if win_h <= 1:
                return False
            base = win.winfo_rooty()
            c_h = bottom_widget.winfo_height()

            # 情况 0: 容器自身被压扁(实际高度 < 请求高度) -> 内部按钮必被裁掉。
            # 这是最隐蔽的一种: 按钮可能仍"映射着"且在窗口内, 但只露出上半截,
            # 视觉上就是"按钮被切成两半"。
            if c_h < bottom_widget.winfo_reqheight():
                return True

            for w in bottom_widget.winfo_children():
                # 情况 3: 子控件未被映射 -> 用户看不到 -> 视为被切
                if not w.winfo_ismapped():
                    return True
                # 子控件自身被压扁
                if w.winfo_height() < w.winfo_reqheight():
                    return True
                # 情况 1: 超出窗口
                if w.winfo_rooty() - base + w.winfo_height() > win_h:
                    return True
                # 情况 2: 溢出容器
                if w.winfo_y() + w.winfo_height() > c_h:
                    return True
            return False
        except Exception:
            return False

    def _fit(event=None):
        if _fitting[0]:
            return
        try:
            top = tree.winfo_toplevel()
            avail = top.winfo_height()
        except Exception:
            return
        if avail <= 1:
            return

        _fitting[0] = True
        try:
            rh = _row_h()
            box = max(0, avail - reserved_h - _TREE_CHROME_H - extra_budget)
            rows = max(min_rows, int(box / rh))
            try:
                tree.configure(height=rows)
                tree.update_idletasks()
            except Exception:
                return
            # 逐行回退直到底部控件不再越界(至少保留 min_rows 行)
            guard = 0
            while _clipped() and rows > min_rows and guard < 80:
                rows -= 1
                try:
                    tree.configure(height=rows)
                    tree.update_idletasks()
                except Exception:
                    break
                guard += 1
            # 若已退到下限仍被切, 说明窗口本身太矮: 记录状态供调用方决策
            _last_clipped[0] = _clipped()
        finally:
            _fitting[0] = False

    _fitting = [False]
    _last_clipped = [False]
    tree.bind("<Configure>", _fit, add="+")
    # 首帧字体/主题尚未测量完毕(工具条是否换行、按钮实际高度都还在变),
    # 因此分多个时点各校正一次。仅靠 <Configure> 不够: 窗口尺寸不变时
    # 该事件不再触发, 而 reserved_h 会因字体测量完成而发生变化。
    for delay in (80, 200, 400, 700, 1200):
        try:
            tree.after(delay, _fit)
        except Exception:
            pass
    # 暴露状态, 便于调用方自检或上报
    tree._adaptive_clipped = _last_clipped  # type: ignore[attr-defined]


# Treeview 的表头 + 水平边框等固定占用高度(实测约 26~30, 取保守值)
_TREE_CHROME_H = 30




def create_action_button(
    parent,
    text: str,
    command,
    bg: str,
    hover_bg: str,
    width: int = 20,
    font_size: int = 13,
    fg: str = "#FFFFFF",
    disabled_bg: Optional[str] = None,
) -> tk.Button:
    """方形工业风操作按钮(主操作橙 / 停止红等), 颜色由调用方按语义传入。

    兼容 Tk 原生按钮的禁用态: Tk 的 tk.Button 不遵循 ttk 样式表, 禁用时默认
    只把文字变灰、底色保持原色, 视觉上仍像可点。这里通过 <Map>/<Unmap> 之外
    的通用做法——在 state 变化时由调用方配合 set_action_button_state() 切换底色,
    同时默认给一个中性 disabled 底色以降低误点风险。
    """
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=(UISettings.FONT_FAMILY, font_size, "bold"),
        bg=bg,
        fg=fg,
        activebackground=hover_bg,
        activeforeground=fg,
        height=2,
        width=width,
        relief=tk.FLAT,
        cursor="hand2",
        highlightthickness=0,
        highlightbackground=bg,
        disabledforeground=UISettings.COLORS["text_secondary"],
    )
    # 记录语义色, 供 set_action_button_state 在启用/禁用间切换
    btn._action_bg = bg               # type: ignore[attr-defined]
    btn._action_hover = hover_bg      # type: ignore[attr-defined]
    btn._action_disabled = disabled_bg or UISettings.COLORS["bg_panel"]  # type: ignore[attr-defined]
    return btn


def set_action_button_state(
    btn: tk.Button, enabled: bool, text: Optional[str] = None, bg: Optional[str] = None
) -> None:
    """统一设置 tk 按钮的启用/禁用外观与光标, 保证全站状态表现一致。

    语义:
    - 启用: 恢复语义底色(或调用方指定色) + hand2 光标;
    - 禁用 + 显式传 bg: 表示"执行中"这类业务状态(如开始按钮转琥珀),
      此时用传入色并保留可识别性, 光标 arrow;
    - 禁用 + 未传 bg: 普通不可点状态, 用中性浅底 + arrow 光标。
    """
    try:
        if enabled:
            use_bg = bg or getattr(btn, "_action_bg", UISettings.COLORS["bg_card"])
            btn.configure(state=tk.NORMAL, bg=use_bg, cursor="hand2")
        elif bg:
            # 业务性禁用(执行中): 保留语义色以传达"正在进行"
            btn.configure(state=tk.DISABLED, bg=bg, cursor="arrow")
        else:
            btn.configure(
                state=tk.DISABLED,
                bg=getattr(btn, "_action_disabled", UISettings.COLORS["bg_panel"]),
                cursor="arrow",
            )
        if text is not None:
            btn.configure(text=text)
    except Exception:
        pass



def create_primary_button(parent, text, command, width: int = 20, font_size: int = 13):
    """信号橙主按钮(开始执行等核心操作)。"""
    colors = UISettings.COLORS
    return create_action_button(
        parent,
        text,
        command,
        bg=colors["accent"],
        hover_bg=colors["accent_hover"],
        width=width,
        font_size=font_size,
        fg=colors["text_on_accent"],
    )


def create_led(parent, size: int = 14):
    """工业指示灯(canvas 圆点)。返回 (canvas, set_color 回调)。"""
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        bg=UISettings.COLORS["bg_topbar"],
        highlightthickness=0,
        bd=0,
    )
    r = size / 2 - 2
    dot = canvas.create_oval(2, 2, size - 2, size - 2, fill=UISettings.COLORS["led_idle"], outline="")

    def set_color(color: str) -> None:
        canvas.itemconfig(dot, fill=color)

    return canvas, set_color


def create_scrolled_text(parent, width: int = 70, height: int = 20):
    """工业白底等宽日志框(细钢灰描边)。"""
    colors = UISettings.COLORS
    return scrolledtext.ScrolledText(
        parent,
        width=width,
        height=height,
        wrap=tk.WORD,
        font=(UISettings.FONT_MONO, 10),
        bg=colors["bg_card"],
        fg=colors["text"],
        insertbackground=colors["text"],
        relief=tk.SOLID,
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=colors["border_light"],
        highlightcolor=colors["accent"],
    )
