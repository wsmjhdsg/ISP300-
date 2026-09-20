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

    实现要点(Tk 陷阱): 若把所有按钮都 grid 到同一个网格里, grid 的每一列宽度
    取【该列全部行】的最大请求宽度——第 2 行放到第 1 列的按钮会把第 1 列整体
    撑宽, 导致"每行都算过没超, 合起来却溢出"的假性换行失败。
    因此这里改为"每行一个子 Frame + 内部 pack(side=LEFT)":
    行与行之间互不影响, 只要单行累计宽度 <= 容器宽度就一定不横向溢出。

    用法:
        flow = ButtonFlow(parent)
        flow.pack(fill=tk.X)
        flow.add("末尾新增", self._add, width=12)
        flow.add("上移", lambda: self._move(-1), width=10)
    """

    def __init__(self, master, gap: int = UISettings.PAD_XS, **kwargs):
        super().__init__(master, **kwargs)
        self._gap = gap
        self._items: list = []          # [(widget, width_chars)]
        self._rows: list = []           # 当前使用的行 Frame 列表
        self._last_sig = None           # 上次布局签名, 用于跳过无变化的重复重排
        self.bind("<Configure>", self._reflow)

    def add(self, text: str, command, width: int = UISettings.BTN_WIDTH_MD,
            style: str = "TButton") -> ttk.Button:
        btn = ttk.Button(self, text=text, command=command, width=width, style=style)
        self._items.append((btn, width))
        self._last_sig = None        # 强制下次重排
        self._reflow()
        # 首帧字体尚未测量时 reqwidth 偏小, 字体就绪后再排一次
        try:
            self.after_idle(lambda: self._reflow(force=True))
        except Exception:
            pass
        return btn

    def _pad_x(self) -> int:
        """读取自身左右内边距(ttk 可能返回元组或字符串, 两种都要兼容)。"""
        try:
            pad = self.cget("padding")
        except Exception:
            return 0
        try:
            if isinstance(pad, (tuple, list)):
                if len(pad) == 1:
                    return int(pad[0]) * 2
                return int(pad[1]) * 2
            parts = str(pad).split()
            if len(parts) == 1:
                return int(parts[0]) * 2
            return int(parts[1]) * 2
        except Exception:
            return 0

    def _btn_px(self, btn, fallback_chars: int) -> int:
        """按钮占位宽度: 优先用 Tk 实测 reqwidth, 不可用时按字符宽估算。

        重要: 这里绝不能用 winfo_width()——按钮被 pack 后可能因父容器
        宽度不足而被压缩, 用它做换行判断会陷入"越挤越窄、越窄越不换行"的
        死循环, 直接导致横向溢出。
        """
        try:
            # 未映射的按钮 reqwidth 已是准确值; 已映射的同样可用
            req = btn.winfo_reqwidth()
        except Exception:
            req = 0
        if req > 1:
            return req
        # 回退: 字符数 * 近似字宽 + 左右内边距
        return fallback_chars * 8 + UISettings.BTN_PAD_X * 2 + 8

    def _reflow(self, event=None, force: bool = False):
        try:
            avail = (event.width if event is not None else self.winfo_width())
        except Exception:
            return
        if avail <= 1 or not self._items:
            return

        usable = max(1, avail - self._pad_x())

        # 逐行累积: 每行能塞几个塞几个。用 reqwidth 而非 winfo_width,
        # 保证"不因压缩而误判", 任何窄宽度下都必然折行而不溢出。
        rows: list = []              # [[btn, ...], ...]
        current: list = []
        used = 0
        for btn, chars in self._items:
            px = self._btn_px(btn, chars)
            need = px + (self._gap if current else 0)
            if current and used + need > usable:
                rows.append(current)
                current = []
                used = 0
                need = px
            current.append(btn)
            used += need
        if current:
            rows.append(current)

        signature = tuple(tuple(str(b) for b in row) for row in rows)
        if (
            not force
            and signature == getattr(self, "_last_sig", None)
            and len(self._rows) == len(rows)
        ):
            return
        self._last_sig = signature

        # 行数变化才重建行 Frame; 否则复用(避免闪烁)
        if len(rows) != len(self._rows):
            for f in self._rows:
                f.destroy()
            self._rows = []
            for i in range(len(rows)):
                f = ttk.Frame(self)
                f.grid(row=i, column=0, sticky=tk.W)
                self._rows.append(f)
            self.grid_columnconfigure(0, weight=1)

        # 重新指派 pack: 先全部解绑, 再按新行归属 pack 回去
        for btn, _ in self._items:
            try:
                btn.pack_forget()
            except Exception:
                pass
        for row_idx, row_btns in enumerate(rows):
            frame = self._rows[row_idx]
            for btn in row_btns:
                btn.pack(in_=frame, side=tk.LEFT, padx=(0, self._gap), pady=2)





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
        remain = max(0, total - fixed - 4)
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
