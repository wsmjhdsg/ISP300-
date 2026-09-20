"""result_dialog(烧录完成弹窗判定)纯函数 + 替身驱动测试(不触碰真实桌面)。"""
import pytest

from core import result_dialog as rdm


# ---------------------------------------------------------------------- #
# 纯函数
# ---------------------------------------------------------------------- #
def test_is_result_title_matching():
    assert rdm.is_result_title("COMPLETE")
    assert rdm.is_result_title("  complete  ")  # 去空格 + 大小写不敏感
    assert not rdm.is_result_title("Meter")
    assert not rdm.is_result_title("")
    assert not rdm.is_result_title(None)
    assert not rdm.is_result_title("COMPLETE-2026")  # 必须精确


def test_body_is_ok():
    assert rdm.body_is_ok("Verify OK")
    assert rdm.body_is_ok("verify ok")
    assert rdm.body_is_ok("... Verify OK ...")
    assert rdm.body_is_ok("烧录成功 Verify OK")
    assert not rdm.body_is_ok("Verify NG")
    assert not rdm.body_is_ok("Error")
    assert not rdm.body_is_ok("")
    assert not rdm.body_is_ok(None)


# ---------------------------------------------------------------------- #
# wait_burn_result 判定语义(替身 _find_result_dialog / _dialog_body_text)
# ---------------------------------------------------------------------- #
def test_ok_dialog_success_and_dismissed(monkeypatch):
    """OK 判定成功 -> 触发统一关窗(_dismiss_result_dialog)。"""
    dismissed = {"n": 0}
    monkeypatch.setattr(rdm, "_find_result_dialog", lambda: object())
    monkeypatch.setattr(rdm, "_dialog_body_text", lambda d: "Verify OK")
    monkeypatch.setattr(
        rdm, "_dismiss_result_dialog", lambda timeout=4.0: dismissed.__setitem__("n", dismissed["n"] + 1)
    )
    ok, msg = rdm.wait_burn_result(timeout=1)
    assert ok is True
    assert "OK" in msg
    assert dismissed["n"] == 1  # 判定与点确定一体: 成功也要触发关窗


def test_non_ok_body_is_failure_and_still_dismissed(monkeypatch):
    """NG 弹窗 -> 判失败, 但仍先关窗清残局(上层失败即中止随后停止)。"""
    dismissed = {"n": 0}
    monkeypatch.setattr(rdm, "_find_result_dialog", lambda: object())
    monkeypatch.setattr(rdm, "_dialog_body_text", lambda d: "Verify NG")
    monkeypatch.setattr(
        rdm, "_dismiss_result_dialog", lambda timeout=4.0: dismissed.__setitem__("n", dismissed["n"] + 1)
    )
    ok, msg = rdm.wait_burn_result(timeout=1)
    assert ok is False
    assert "NG" in msg or "非 OK" in msg
    assert dismissed["n"] == 1


def test_timeout_no_dialog_is_failure(monkeypatch):
    monkeypatch.setattr(rdm, "_find_result_dialog", lambda: None)
    ok, msg = rdm.wait_burn_result(timeout=0.1, poll=0.05)
    assert ok is False
    assert "超时" in msg


def test_stop_check_interrupts_poll(monkeypatch):
    monkeypatch.setattr(rdm, "_find_result_dialog", lambda: None)
    calls = {"n": 0}

    def stop():
        calls["n"] += 1
        return calls["n"] >= 1

    ok, msg = rdm.wait_burn_result(timeout=60, poll=0.05, stop_check=stop)
    assert ok is False
    assert "停止" in msg


def test_looks_like_ok_button():
    assert rdm._looks_like_ok_button("确定")
    assert rdm._looks_like_ok_button("OK")
    assert rdm._looks_like_ok_button("ok")
    assert rdm._looks_like_ok_button("确定(O)")
    assert rdm._looks_like_ok_button("OK(&O)")
    assert rdm._looks_like_ok_button("  OK  ")
    assert not rdm._looks_like_ok_button("取消")
    assert not rdm._looks_like_ok_button("Cancel")
    assert not rdm._looks_like_ok_button("Cook")  # 子串 ok 不再误判
    assert not rdm._looks_like_ok_button("")
    assert not rdm._looks_like_ok_button(None)


def test_find_text_element_locates_non_button_label():
    """修复真机: 弹窗是主窗口内嵌子面板时, '确定' 可能是 Static 文本(非 Button)也要能定位到。"""
    ok_label = _FakeElem("确定", ctype="Text")  # 控件类型 Text, 不是 Button
    root = _FakeElem(
        "I.S.P-300 Series V5.35",
        [_FakeElem("Verify OK", []), _FakeElem("", [ok_label])],
    )
    found = rdm._find_text_element(root, "确定")
    assert found is ok_label


def test_find_text_element_handles_parenthetical_suffix():
    elem = _FakeElem("确定(O)", ctype="Text")
    assert rdm._find_text_element(elem, "确定") is elem
    assert rdm._find_text_element(elem, "OK") is None  # 不同 marker


def test_find_text_element_rejects_unrelated_text():
    root = _FakeElem("COMPUTE", [_FakeElem("确定下一步", ctype="Text")])
    # '确定' 是 '确定下一步' 的子串, 但归一化精确匹配应拒绝
    assert rdm._find_text_element(root, "确定") is None
    assert rdm._find_text_element(root, "ok") is None


def test_find_ok_button_recursive():
    ok_btn = _FakeElem("确定", ctype="Button")
    root = _FakeElem(
        "COMPLETE", [_FakeElem("Verify OK", []), _FakeElem("", [ok_btn])]
    )
    found = rdm._find_ok_button(root)
    # 返回的按钮元素即我们埋入的那个(按文本标识比对)
    assert found is not None and found.window_text() == "确定"


def test_find_ok_button_none_when_absent():
    root = _FakeElem(
        "COMPLETE",
        [_FakeElem("Verify NG", []), _FakeElem("取消", ctype="Button")],
    )
    assert rdm._find_ok_button(root) is None


# ---------------------------------------------------------------------- #
# 正文关键词兜底识别(自绘无标题栏弹窗 / 标题非 COMPLETE 的场景)
# ---------------------------------------------------------------------- #
class _FakeElem:
    """极简 UIA wrapper 替身: window_text() + children() + 可选控件类型。"""

    def __init__(self, text="", children=(), ctype=""):
        self._text = text
        self._children = list(children)
        self.element_info = type("EI", (), {"control_type": ctype})()

    def window_text(self):
        return self._text

    def children(self):
        return self._children

    def class_name(self):
        return ""


def test_window_contains_marker_deeply_nested():
    deep = _FakeElem(
        "COMPLETE",
        [_FakeElem("Verify OK", [_FakeElem("确定", [])])],
    )
    root = _FakeElem("ISP300Host", [_FakeElem("一些控件", [deep])])
    assert rdm._window_contains_marker(root, "Verify OK") is True
    assert rdm._window_contains_marker(root, "COMPLETE") is True


def test_window_contains_marker_not_found():
    root = _FakeElem("ISP300Host", [_FakeElem("Verify NG", []), _FakeElem("OK", [])])
    assert rdm._window_contains_marker(root, "Verify OK") is False
    assert rdm._window_contains_marker(_FakeElem(), "Verify OK") is False
    assert rdm._window_contains_marker(None, "Verify OK") is False


def test_window_contains_marker_case_insensitive():
    root = _FakeElem("", [_FakeElem("vErIfY oK", [])])
    assert rdm._window_contains_marker(root, "Verify OK") is True
