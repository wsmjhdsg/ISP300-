"""core.file_dialog 纯函数测试: 最新文件选取与 pick 预解析(无 GUI/COM 依赖)。"""
import os
import time

import pytest

from core.constants import OpenFileModes
from core.file_dialog import find_latest_file, resolve_pick_steps


@pytest.fixture
def fw_dir(tmp_path):
    """构造固件目录: 两个 .i3s + 一个干扰文件 + 一个子目录。"""
    d = tmp_path / "fw"
    d.mkdir()
    old = d / "A_OLD.i3s"
    new = d / "b_new.i3S"  # 混用大小写验证忽略大小写
    old.write_text("1")
    new.write_text("2")
    (d / "readme.txt").write_text("no")
    sub = d / "sub"
    sub.mkdir()
    (sub / "hidden.i3s").write_text("in-sub")
    os.utime(old, (time.time() - 100, time.time() - 100))
    return d


def test_latest_picks_newest_file(fw_dir):
    newest = fw_dir / "b_new.i3S"
    os.utime(newest, (time.time(), time.time()))  # 保证最晚
    assert find_latest_file(str(fw_dir)) == str(newest)


def test_latest_ignores_case_of_pattern(fw_dir):
    found = find_latest_file(str(fw_dir), "*.I3S")
    # 大小写不敏感, 一定命中某个 .i3s; 且不会取子目录里的
    assert found is not None and "hidden" not in found


def test_latest_ignores_non_matching_and_subdir(fw_dir):
    assert find_latest_file(str(fw_dir), "*.bin") is None


def test_latest_bad_inputs():
    assert find_latest_file("") is None
    assert find_latest_file("C:/__definitely_not_exist__") is None
    assert find_latest_file(None) is None  # type: ignore[arg-type]


def test_latest_empty_pattern_falls_back_to_default(tmp_path):
    (tmp_path / "x.i3s").write_text("1")
    assert find_latest_file(str(tmp_path), "") == str(tmp_path / "x.i3s")


def test_resolve_pick_uses_asker_and_replaces():
    steps = [
        {"type": "openfile", "mode": "pick"},
        {"type": "wait", "seconds": 1},
    ]
    resolved = resolve_pick_steps(steps, lambda prompt: "C:/fw/1.i3s")
    assert resolved is not None
    assert resolved[0]["mode"] == OpenFileModes.PATH
    assert resolved[0]["path"] == "C:/fw/1.i3s"
    assert resolved[1] == {"type": "wait", "seconds": 1}
    # 原列表未被修改
    assert steps[0].get("path") is None


def test_resolve_pick_cancel_returns_none():
    assert resolve_pick_steps([{"type": "openfile", "mode": "pick"}], lambda p: None) is None


def test_resolve_pick_passes_through_others():
    steps = [{"type": "openfile", "mode": "path", "path": "x.i3s"}]
    resolved = resolve_pick_steps(steps, lambda p: "y.i3s")
    assert resolved == steps
    assert resolved is not steps


def test_resolve_pick_defaults_missing_mode_to_path():
    # mode 缺省 = path(与执行/校验层一致), 不应被当作 pick 弹选择, 原样透传
    steps = [{"type": "openfile"}]
    resolved = resolve_pick_steps(steps, lambda p: (_ for _ in ()).throw(AssertionError("不应触发选择")))
    assert resolved is not None
    assert resolved[0] == {"type": "openfile"}  # 未添加/修改任何字段
