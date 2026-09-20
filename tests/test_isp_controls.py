"""isp_controls 控件定位单元测试: 纯函数 + 点击分派(替身注入, 无真实桌面)。

ListItem 纯数字标题 = 行号定位是修复"控件[18]"的核心, 重点覆盖:
- row_number_from_title 解析规则(纯数字 -> 行号; 其它 -> None)
- click_control 对纯数字 ListItem 走行号分派而非标题精确匹配
- 失败时调用 _dump_list_rows 留诊断证据
"""
import pytest

from core import isp_controls as ic


# ---------------------------------------------------------------------- #
# 纯函数: 标题 -> 行号
# ---------------------------------------------------------------------- #
def test_row_number_from_title():
    assert ic.row_number_from_title("18") == 18
    assert ic.row_number_from_title("  6  ") == 6
    assert ic.row_number_from_title(18) == 18  # 兼容历史 int 配置
    assert ic.row_number_from_title(0) is None
    assert ic.row_number_from_title("0") is None  # 0 无意义
    assert ic.row_number_from_title("-2") is None
    assert ic.row_number_from_title(" 18 TMPM3HxFDp 0.0000") is None  # 占用行
    assert ic.row_number_from_title("abc") is None
    assert ic.row_number_from_title("") is None
    assert ic.row_number_from_title(None) is None


def test_click_control_accepts_int_title_without_strip_crash(monkeypatch):
    """历史配置 title 存为 int(如 18): 不得抛 'int' object has no attribute 'strip'。"""
    window = object()
    calls = {"row": None}
    monkeypatch.setattr(ic, "find_isp_window", lambda: window)
    monkeypatch.setattr(ic, "find_control", lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应走标题精确匹配")))

    def fake_row_click(w, row_index, button):
        calls["row"] = row_index
        return True, ""

    monkeypatch.setattr(ic, "_click_list_item_row", fake_row_click)

    # int 18 与 str "18" 都能定位到第 18 行
    assert ic.click_control(control_type="ListItem", title=18) is True
    assert calls["row"] == 18


# ---------------------------------------------------------------------- #
# click_control 分派: 纯数字标题 -> _click_list_item_row
# ---------------------------------------------------------------------- #
def test_click_control_dispatches_numeric_listitem_to_row(monkeypatch):
    """控件点 title='18'(ListItem, 无 auto_id): 必须走'按行号点击'分支。"""
    window = object()
    calls = {"row": None, "button": None, "window": None}
    monkeypatch.setattr(ic, "find_isp_window", lambda: window)
    monkeypatch.setattr(ic, "find_control", lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应走标题精确匹配")))

    def fake_row_click(w, row_index, button):
        calls.update(window=w, row=row_index, button=button)
        return True, ""

    monkeypatch.setattr(ic, "_click_list_item_row", fake_row_click)

    assert ic.click_control(control_type="ListItem", title="18") is True
    assert calls["row"] == 18
    assert calls["button"] == "left"
    assert calls["window"] is window


def test_click_control_non_numeric_goes_exact_match(monkeypatch):
    """非纯数字标题(如占用行 ' 2 TMPM3...')仍走标题精确匹配, 不影响旧控件。"""
    window = object()
    monkeypatch.setattr(ic, "find_isp_window", lambda: window)
    monkeypatch.setattr(ic, "_click_list_item_row", lambda *a, **k: (_ for _ in ()).throw(AssertionError("行号分支不应触发")))

    class _Elem:
        def rectangle(self):
            return type("R", (), {"left": 0, "top": 0, "right": 100, "bottom": 100})()

        def click_input(self):
            pass

        def right_click_input(self):
            pass

        def double_click_input(self):
            pass

    monkeypatch.setattr(ic, "find_control", lambda *a, **k: _Elem())
    monkeypatch.setattr(ic, "_rect_on_visible_screen", lambda r: True)

    assert ic.click_control(control_type="Button", title="Send Data") is True


def test_click_control_numeric_listitem_row_failure_dumps_list(monkeypatch):
    """行号点击失败 -> 最终失败日志会 dump 列表行(诊断证据)。"""
    window = object()
    monkeypatch.setattr(ic, "find_isp_window", lambda: window)
    monkeypatch.setattr(ic, "_click_list_item_row", lambda w, r, b: (False, "列表当前为空"))
    dumped = {"n": 0}
    monkeypatch.setattr(ic, "_dump_list_rows", lambda w: dumped.__setitem__("n", dumped["n"] + 1))

    assert ic.click_control(control_type="ListItem", title="18", retries=1) is False
    assert dumped["n"] == 1  # 失败后必须 dump 当前行状态


def test_click_control_numeric_listitem_retries_then_succeeds(monkeypatch):
    """列表行在重试窗口内出现(如 LOAD 后列表刷新): 第 2 次尝试成功。"""
    window = object()
    monkeypatch.setattr(ic, "find_isp_window", lambda: window)
    attempts = {"n": 0}

    def fake_row_click(w, row_index, button):
        attempts["n"] += 1
        if attempts["n"] < 2:
            return False, "列表当前为空(未枚举到任何 ListItem 行)"
        return True, ""

    monkeypatch.setattr(ic, "_click_list_item_row", fake_row_click)
    monkeypatch.setattr(ic, "time", type("_T", (), {"sleep": staticmethod(lambda s: None)})())

    assert ic.click_control(control_type="ListItem", title="18", retries=3, retry_delay=0) is True
    assert attempts["n"] == 2
