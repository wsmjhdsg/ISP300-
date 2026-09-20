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

    # ---------- 按钮: 直角钢灰描边(工业感) ----------
    style.configure(
        "TButton",
        font=(family, 10),
        padding=(14, 7),
        background=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        focuscolor=c["accent"],
    )
    style.map(
        "TButton",
        background=[("active", c["bg_hover"]), ("disabled", c["bg_panel"])],
        foreground=[("disabled", c["text_secondary"])],
        bordercolor=[("active", c["border"])],
    )

    # ---------- 输入控件 ----------
    style.configure(
        "TEntry",
        fieldbackground=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        padding=5,
    )
    style.map("TEntry", bordercolor=[("focus", c["accent"])])

    style.configure(
        "TCombobox",
        fieldbackground=c["bg_card"],
        background=c["bg_card"],
        foreground=c["text"],
        bordercolor=c["border"],
        borderwidth=1,
        arrowcolor=c["text_secondary"],
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", c["bg_card"]),
            ("active", c["bg_card"]),
            ("focus", c["bg_card"]),
        ],
        bordercolor=[("focus", c["accent"])],
        selectbackground=[("readonly", c["bg_card"])],
        selectforeground=[("readonly", c["text"])],
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
        rowheight=26,
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

    # ---------- 滚动条 ----------
    style.configure(
        "Vertical.TScrollbar",
        background=c["bg_hover"],
        troughcolor=c["bg_card"],
        bordercolor=c["bg_card"],
        arrowcolor=c["text_secondary"],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=c["bg_hover"],
        troughcolor=c["bg_card"],
        bordercolor=c["bg_card"],
        arrowcolor=c["text_secondary"],
    )


def create_action_button(
    parent,
    text: str,
    command,
    bg: str,
    hover_bg: str,
    width: int = 20,
    font_size: int = 13,
    fg: str = "#FFFFFF",
) -> tk.Button:
    """方形工业风操作按钮(主操作橙 / 停止红等), 颜色由调用方按语义传入。"""
    return tk.Button(
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
    )


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
