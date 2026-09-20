from typing import Dict, Final


class MouseButtons:
    LEFT: Final[str] = "left"
    RIGHT: Final[str] = "right"
    DOUBLE: Final[str] = "double"
    VALID: Final[tuple] = (LEFT, RIGHT, DOUBLE)


class StepTypes:
    LAUNCH: Final[str] = "launch"
    CLICK: Final[str] = "click"
    OPENFILE: Final[str] = "openfile"  # 自动填充系统"打开文件"对话框(选固件等)
    TYPE: Final[str] = "type"
    KEY: Final[str] = "key"
    WAIT: Final[str] = "wait"
    WAITRESULT: Final[str] = "waitresult"  # 轮询烧录完成弹窗(COMPLETE/Verify OK)判成败
    ALL: Final[tuple] = (LAUNCH, CLICK, OPENFILE, TYPE, KEY, WAIT, WAITRESULT)


class ClickPointTypes:
    # 控件定位(control_type / title / automation_id); 坐标定位点不带 type 字段
    CONTROL: Final[str] = "control"


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

# 步骤类型: 中文短名(列表列用) + 描述(下拉框提示用), 显式映射取代
# "从显示文本 split 反推 type key" 的脆弱写法(见 step_editor 旧 get_type_key)。
# openfile 步骤的取值模式
class OpenFileModes:
    PATH: Final[str] = "path"      # 固定路径
    LATEST: Final[str] = "latest"  # 从目录取修改时间最新的匹配文件
    PICK: Final[str] = "pick"      # 执行前弹出文件选择器手选一次
    ALL: Final[tuple] = (PATH, LATEST, PICK)


STEP_SHORT_LABELS: Final[Dict[str, str]] = {
    StepTypes.LAUNCH: "打开软件",
    StepTypes.CLICK: "点击",
    StepTypes.OPENFILE: "选择文件",
    StepTypes.TYPE: "输入文本",
    StepTypes.KEY: "按键",
    StepTypes.WAIT: "等待",
    StepTypes.WAITRESULT: "烧录判定",
}

STEP_DESCRIPTIONS: Final[Dict[str, str]] = {
    StepTypes.LAUNCH: "启动外部程序(.exe / .lnk)",
    StepTypes.CLICK: "调用已记录的坐标点 / 控件点, 或直接填坐标",
    StepTypes.OPENFILE: "自动填充弹出的'打开文件'对话框(选固件等)",
    StepTypes.TYPE: "在当前光标处逐字符模拟输入, 区分大小写",
    StepTypes.KEY: "按下单个按键 (Enter/Tab/Esc/F1~F12...)",
    StepTypes.WAIT: "暂停指定秒数, 用于等待软件加载/弹窗",
    StepTypes.WAITRESULT: "轮询'烧录完成'弹窗(COMPLETE / Verify OK), 自动关闭并判定成功",
}

STEP_DISPLAY_VALUES: Final[Dict[str, str]] = {
    StepTypes.LAUNCH: f"{StepTypes.LAUNCH} {STEP_SHORT_LABELS[StepTypes.LAUNCH]} - {STEP_DESCRIPTIONS[StepTypes.LAUNCH]}",
    StepTypes.CLICK: f"{StepTypes.CLICK} {STEP_SHORT_LABELS[StepTypes.CLICK]} - {STEP_DESCRIPTIONS[StepTypes.CLICK]}",
    StepTypes.OPENFILE: f"{StepTypes.OPENFILE} {STEP_SHORT_LABELS[StepTypes.OPENFILE]} - {STEP_DESCRIPTIONS[StepTypes.OPENFILE]}",
    StepTypes.TYPE: f"{StepTypes.TYPE} {STEP_SHORT_LABELS[StepTypes.TYPE]} - {STEP_DESCRIPTIONS[StepTypes.TYPE]}",
    StepTypes.KEY: f"{StepTypes.KEY} {STEP_SHORT_LABELS[StepTypes.KEY]} - {STEP_DESCRIPTIONS[StepTypes.KEY]}",
    StepTypes.WAIT: f"{StepTypes.WAIT} {STEP_SHORT_LABELS[StepTypes.WAIT]} - {STEP_DESCRIPTIONS[StepTypes.WAIT]}",
    StepTypes.WAITRESULT: f"{StepTypes.WAITRESULT} {STEP_SHORT_LABELS[StepTypes.WAITRESULT]} - {STEP_DESCRIPTIONS[StepTypes.WAITRESULT]}",
}

STEP_KEY_FROM_DISPLAY: Final[Dict[str, str]] = {v: k for k, v in STEP_DISPLAY_VALUES.items()}


class UISettings:
    """浅色工业风 UI 常量: 铝灰底 + 深钢灰栏 + 信号橙强调, 全 hex 收敛于此。"""

    # 图标(相对项目根 / PyInstaller _MEIPASS 的资源路径)
    APP_ICON: Final[str] = "assets/icon.ico"

    # —— 窗口尺寸 ——
    # 说明: 这些值现在作为【首选尺寸/下限】使用, 实际显示尺寸由
    # ui/styles.fit_window_to_screen() 依据当前屏幕与 DPI 收敛, 保证小屏可用、大屏不局促。
    WINDOW_SIZE: Final[str] = "780x720"
    WINDOW_MINSIZE: Final[tuple] = (700, 620)
    CLICK_POINT_EDITOR_SIZE: Final[str] = "600x480"
    CLICK_POINT_EDITOR_MINSIZE: Final[tuple] = (560, 420)
    STEP_EDITOR_SIZE: Final[str] = "1050x650"
    STEP_EDITOR_MINSIZE: Final[tuple] = (820, 520)
    MACHINE_EDITOR_SIZE: Final[str] = "920x450"
    MACHINE_EDITOR_MINSIZE: Final[tuple] = (760, 420)

    # 窗口占屏幕可用区域的最大比例(留出任务栏/边距, 避免顶天立地)
    WINDOW_SCREEN_RATIO: Final[float] = 0.92
    # 内容区最小可视高度/宽度(低于此值自动启用滚动容器, 见 styles.ScrollableFrame)
    MIN_CONTENT_HEIGHT: Final[int] = 480

    # —— 间距 token(统一内边距/外边距节奏, 避免各处随手写数字) ——
    PAD_XS: Final[int] = 4
    PAD_SM: Final[int] = 8
    PAD_MD: Final[int] = 12
    PAD_LG: Final[int] = 16

    # —— 控件尺寸 token(保证全站按钮/输入框高度视觉一致) ——
    BTN_PAD_X: Final[int] = 14          # ttk 按钮左右内边距
    BTN_PAD_Y: Final[int] = 7           # ttk 按钮上下内边距
    BTN_WIDTH_SM: Final[int] = 10       # 字符宽: 短按钮(上移/下移)
    BTN_WIDTH_MD: Final[int] = 12       # 字符宽: 常规操作按钮
    BTN_WIDTH_LG: Final[int] = 18       # 字符宽: 长文案按钮
    ENTRY_PAD: Final[int] = 5           # 输入框内边距
    ROW_HEIGHT: Final[int] = 26         # 表格行高
    ROW_HEIGHT_COMPACT: Final[int] = 24 # 表格行高(紧凑模式, 小屏用)

    # 工业风字体: 正文 Segoe UI(清爽), 标题 Bahnschrift(工程感 DIN 风), 日志等宽 Consolas
    FONT_FAMILY: Final[str] = "Segoe UI"
    FONT_TITLE: Final[str] = "Bahnschrift"
    FONT_MONO: Final[str] = "Consolas"

    COLORS: Final[Dict[str, str]] = {
        # —— 浅色工业风: 浅铝灰底 + 深钢灰顶栏 + 白卡片 + 信号橙主操作 + 工控红停止 ——
        "bg_topbar": "#3A4653",        # 顶部深钢灰蓝(铭牌栏)
        "bg_window": "#E7EAED",        # 窗口浅铝灰底
        "bg_panel": "#F0F3F5",         # 面板/表头浅底
        "bg_card": "#FFFFFF",          # 内容白色卡片
        "bg_hover": "#D9DFE4",         # 悬停/进度条槽底色
        "accent": "#E8590C",           # 信号橙(开始执行/强调)
        "accent_hover": "#D9480F",     # 强调悬停
        "accent_soft": "#DCE8F1",      # 表格选中行(工业蓝浅底)
        "text": "#1F2933",             # 主文字(近黑)
        "text_secondary": "#5E6C76",   # 次要文字(钢灰)
        "text_on_dark": "#F8FAFC",     # 深钢灰栏上的文字
        "text_on_accent": "#FFFFFF",   # 橙按钮上的文字
        "border": "#8A97A3",           # 控件边框(钢灰)
        "border_light": "#CBD3DA",     # 分组框/分隔浅边框
        "success": "#2B8A3E",          # 成功(工控绿)
        "warning": "#C77414",          # 警示(琥珀)
        "danger": "#C92A2A",           # 危险/停止(工控红)
        "info": "#1C6BA0",             # 信息(工业蓝)
        # —— 工业指示灯 ——
        "led_idle": "#9AA5B1",         # 空闲: 灰
        "led_running": "#E8930C",      # 执行中: 琥珀
        "led_success": "#2B8A3E",      # 完成: 绿
        "led_error": "#C92A2A",        # 失败: 红
    }


class SimulatorConfig:
    MOVE_DURATION: Final[float] = 0.2
    MOVE_PAUSE: Final[float] = 0.2
    TYPE_INTERVAL: Final[float] = 0.05
    IME_SWITCH_DELAY: Final[float] = 0.2
    # 超过该长度的 type 文本改用"剪贴板 + Ctrl+V", 输入提速且规避逐键转义问题
    TYPE_PASTE_THRESHOLD: Final[int] = 40
    # openfile 步骤: 等待"打开文件"对话框出现的总超时与轮询间隔
    FILE_DIALOG_TIMEOUT: Final[float] = 10.0
    FILE_DIALOG_POLL: Final[float] = 0.2
    # waitresult 步骤: 轮询"烧录完成"弹窗(COMPLETE/Verify OK)的总超时与轮询间隔
    RESULT_TIMEOUT: Final[float] = 120.0
    RESULT_POLL: Final[float] = 0.5
    # 步骤失败后的默认策略: 失败即中止后续执行(防烧错; UI 可关)
    STOP_ON_ERROR: Final[bool] = True


class RecorderConfig:
    DOUBLE_CLICK_INTERVAL: Final[float] = 0.3
    DOUBLE_CLICK_DELAY_BUFFER: Final[float] = 0.05


QUICK_KEYS: Final[tuple] = ("enter", "tab", "esc", "space", "f1", "f2", "delete")
QUICK_WAIT_SECONDS: Final[tuple] = ("0.5", "1", "2", "3", "5")
