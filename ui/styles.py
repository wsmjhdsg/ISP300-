import tkinter as tk
from tkinter import ttk

from core.constants import UISettings


def apply_ttk_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")
    elif "default" in available_themes:
        style.theme_use("default")

    font_family = UISettings.FONT_FAMILY
    colors = UISettings.COLORS

    style.configure(".", font=(font_family, 10))
    style.configure("TLabel", font=(font_family, 10))
    style.configure("TButton", font=(font_family, 10), padding=6)
    style.configure("TEntry", font=(font_family, 10), padding=4)
    style.configure("TCombobox", font=(font_family, 10), padding=4)
    style.configure("TFrame", background=colors["bg_topbar"])
    style.configure("TLabelframe", font=(font_family, 10, "bold"))
    style.configure("TLabelframe.Label", font=(font_family, 10, "bold"))
    style.configure("Treeview", font=(font_family, 9), rowheight=26)
    style.configure("Treeview.Heading", font=(font_family, 9, "bold"))
    style.configure("TProgressbar", thickness=20)


def create_primary_button(
    parent, text: str, command, width: int = 20, font_size: int = 14
) -> tk.Button:
    colors = UISettings.COLORS
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=(UISettings.FONT_FAMILY, font_size, "bold"),
        bg=colors["primary"],
        fg="white",
        activebackground=colors["primary_hover"],
        activeforeground="white",
        height=2,
        width=width,
        relief=tk.FLAT,
        cursor="hand2",
    )
    return btn


def set_button_running(btn: tk.Button) -> None:
    btn.config(
        state=tk.DISABLED,
        text="执行中...",
        bg=UISettings.COLORS["warning"],
        fg="white",
    )


def set_button_idle(btn: tk.Button) -> None:
    btn.config(
        state=tk.NORMAL,
        text="开始执行",
        bg=UISettings.COLORS["primary"],
        fg="white",
    )
