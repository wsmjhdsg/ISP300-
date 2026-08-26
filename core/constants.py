from typing import Dict, Final


class MouseButtons:
    LEFT: Final[str] = "left"
    RIGHT: Final[str] = "right"
    DOUBLE: Final[str] = "double"
    VALID: Final[tuple] = (LEFT, RIGHT, DOUBLE)


class StepTypes:
    LAUNCH: Final[str] = "launch"
    CLICK: Final[str] = "click"
    TYPE: Final[str] = "type"
    KEY: Final[str] = "key"
    WAIT: Final[str] = "wait"
    ALL: Final[tuple] = (LAUNCH, CLICK, TYPE, KEY, WAIT)


BUTTON_LABELS: Final[Dict[str, str]] = {
    MouseButtons.LEFT: "左键单击",
    MouseButtons.RIGHT: "右键单击",
    MouseButtons.DOUBLE: "左键双击",
}

BUTTON_SHORT_LABELS: Final[Dict[str, str]] = {
    MouseButtons.LEFT: "左键",
    MouseButtons.RIGHT: "右键",
    MouseButtons.DOUBLE: "双击",
}

BUTTON_DISPLAY_VALUES: Final[Dict[str, str]] = {
    MouseButtons.LEFT: "left 左键单击",
    MouseButtons.RIGHT: "right 右键单击",
    MouseButtons.DOUBLE: "double 左键双击",
}

BUTTON_FROM_DISPLAY: Final[Dict[str, str]] = {v: k for k, v in BUTTON_DISPLAY_VALUES.items()}


class UISettings:
    WINDOW_SIZE: Final[str] = "720x680"
    WINDOW_MINSIZE: Final[tuple] = (680, 600)
    CLICK_POINT_EDITOR_SIZE: Final[str] = "600x480"
    STEP_EDITOR_SIZE: Final[str] = "1050x650"
    MACHINE_EDITOR_SIZE: Final[str] = "920x450"

    FONT_FAMILY: Final[str] = "Microsoft YaHei UI"
    FONT_MONO: Final[str] = "Consolas"

    COLORS: Final[Dict[str, str]] = {
        "bg_topbar": "#f5f5f5",
        "primary": "#4CAF50",
        "primary_hover": "#45a049",
        "warning": "#f39c12",
        "danger": "#e74c3c",
        "success": "#27ae60",
        "text": "#333333",
        "text_gray": "#666666",
        "border": "#ddd",
    }


class SimulatorConfig:
    MOVE_DURATION: Final[float] = 0.2
    MOVE_PAUSE: Final[float] = 0.2
    MOUSE_TOLERANCE: Final[int] = 5
    MOUSE_CHECK_INTERVAL: Final[float] = 0.1
    TYPE_INTERVAL: Final[float] = 0.05
    IME_SWITCH_DELAY: Final[float] = 0.2


class RecorderConfig:
    DOUBLE_CLICK_INTERVAL: Final[float] = 0.3
    DOUBLE_CLICK_DELAY_BUFFER: Final[float] = 0.05


QUICK_KEYS: Final[tuple] = ("enter", "tab", "esc", "space", "f1", "f2", "delete")
QUICK_WAIT_SECONDS: Final[tuple] = ("0.5", "1", "2", "3", "5")
