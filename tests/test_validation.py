"""步序 / 点击点校验层单元测试。"""
import pytest

from core.validation import validate_click_point, validate_click_points, validate_step


def test_validate_unknown_type():
    errs = validate_step({"type": "hack"})
    assert any("未知步骤类型" in e for e in errs)


def test_validate_launch_requires_path():
    assert validate_step({"type": "launch"})
    assert validate_step({"type": "launch", "path": ""})
    assert not validate_step({"type": "launch", "path": "C:/x.exe"})


def test_validate_click_needs_point_or_xy():
    assert validate_step({"type": "click"})
    assert not validate_step({"type": "click", "x": 10, "y": 20})
    assert not validate_step({"type": "click", "point_name": "P"})


def test_validate_click_point_reference_missing():
    errs = validate_step({"type": "click", "point_name": "不存在"}, click_point_names=["A"])
    assert any("不存在" in e for e in errs)
    assert not validate_step({"type": "click", "point_name": "A"}, click_point_names=["A"])


def test_validate_type_key_wait():
    assert validate_step({"type": "type", "text": ""})
    assert not validate_step({"type": "type", "text": "hi"})
    assert validate_step({"type": "key", "key": ""})
    assert not validate_step({"type": "key", "key": "enter"})
    assert validate_step({"type": "wait", "seconds": -1})
    assert validate_step({"type": "wait", "seconds": "abc"})
    assert not validate_step({"type": "wait", "seconds": 2})


def test_validate_openfile():
    # path 模式需要 path
    assert validate_step({"type": "openfile", "mode": "path"})
    assert validate_step({"type": "openfile"})  # mode 缺省=path, 仍需 path
    assert not validate_step({"type": "openfile", "mode": "path", "path": "C:/a.i3s"})
    # latest 模式需要 dir
    assert validate_step({"type": "openfile", "mode": "latest"})
    assert not validate_step({"type": "openfile", "mode": "latest", "dir": "C:/fw"})
    # pick 不需要额外字段
    assert not validate_step({"type": "openfile", "mode": "pick"})
    # 非法模式
    assert validate_step({"type": "openfile", "mode": "weird", "path": "x"})


def test_validate_button_invalid():
    errs = validate_step({"type": "click", "x": 1, "y": 2, "button": "middle"})
    assert any("button" in e for e in errs)


def test_validate_click_point_coord():
    assert not validate_click_point("a", {"x": 1, "y": 2})
    assert validate_click_point("a", {"x": "oops", "y": 2})


def test_validate_click_point_control_locator():
    assert validate_click_point("c", {"type": "control", "control_type": "", "title": "", "auto_id": ""})
    assert not validate_click_point("c", {"type": "control", "title": "开始"})


def test_validate_click_points_batch():
    bad = validate_click_points({"good": {"x": 1, "y": 2}, "bad": {"x": "x"}})
    assert "good" not in bad and "bad" in bad
