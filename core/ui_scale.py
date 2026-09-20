"""按内容调优窗口尺寸: 让窗口随分辨率和字体自动收敛到"刚好合身"。

问题背景:
固定 geometry(如 "780x720")在 4K 大屏上显得局促(内容只占一小块),
在 1366x768 小屏上又可能超出屏幕。单纯按"屏幕比例"缩放只能解决"不越界",
解决不了"内容装不下"或"太空旷"。

正解是"询问 Tk 自身":
1. update 一次让控件算出请求尺寸(winfo_reqwidth/reqheight);
2. 取 preferred 与 req 的较大值(内容多则给足空间, 内容少则不低于首选);
3. 用 fit_window_to_screen 夹到屏幕上限并居中。

这样同一份代码在 1366x768 与 3840x2160 上都能得到自然的结果,
不会出现"内容被裁掉"或"窗口比内容大出一片空白"。
"""
from typing import Optional


def fit_window_to_content(
    window,
    preferred: str,
    minsize: Optional[tuple] = None,
    ratio: Optional[float] = None,
    extra_w: int = 0,
    extra_h: int = 0,
) -> None:
    """按"实际内容所需尺寸"与"首选尺寸"中较大者设置窗口几何。

    extra_w / extra_h: 给内容尺寸留的余量(滚动条、边框等)。
    """
    try:
        pw, ph = (int(x) for x in preferred.lower().split("x"))
    except Exception:
        pw, ph = 780, 720

    try:
        window.update_idletasks()
        cw = window.winfo_reqwidth() + extra_w
        ch = window.winfo_reqheight() + extra_h
    except Exception:
        cw, ch = 0, 0

    # 4K 大屏上窗口可略大, 但不占满全屏(留出桌面感知)
    scr_w = window.winfo_screenwidth()
    scr_h = window.winfo_screenheight()
    limit_w = int(scr_w * 0.72)
    limit_h = int(scr_h * 0.80)

    w = min(max(pw, cw), limit_w)
    h = min(max(ph, ch), limit_h)

    _apply_geometry(window, f"{int(w)}x{int(h)}", minsize, ratio)


def _apply_geometry(window, preferred: str, minsize=None, ratio=None) -> None:
    """窗口几何收敛与居中(与 ui.styles.fit_window_to_screen 同一策略)。

    此处内联一份最小实现而非 import ui.styles, 以保持 core -> ui 的单向依赖
    (core 层不应依赖 UI 层)。
    """
    from core.constants import UISettings

    try:
        pw, ph = (int(x) for x in preferred.lower().split("x"))
    except Exception:
        pw, ph = 780, 720

    scr_w, scr_h = window.winfo_screenwidth(), window.winfo_screenheight()
    if scr_w <= 0 or scr_h <= 0:
        scr_w, scr_h = 1920, 1080
    use_ratio = ratio if ratio is not None else UISettings.WINDOW_SCREEN_RATIO
    limit_w = int(scr_w * use_ratio)
    limit_h = int(scr_h * use_ratio)

    w = min(pw, limit_w)
    h = min(ph, limit_h)

    if minsize:
        window.minsize(min(minsize[0], limit_w), min(minsize[1], limit_h))

    x = max(0, (scr_w - w) // 2)
    y = max(0, (scr_h - h) // 3)  # 略偏上, 视觉更稳
    window.geometry(f"{w}x{h}+{x}+{y}")
