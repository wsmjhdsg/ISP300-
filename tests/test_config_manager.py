"""ConfigManager 单元测试: CRUD / 文件联动 / mtime 缓存失效 / 原子写 / 损坏自愈。"""
import json
import time

import pytest

from core import config_manager as cm
from core.config_manager import ConfigManager


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """把 ConfigManager 指向临时目录的隔离实例。"""
    monkeypatch.setattr(cm, "app_base_dir", lambda: tmp_path)
    ConfigManager.reset_instance()
    inst = ConfigManager()
    yield inst
    ConfigManager.reset_instance()


# ---------------------------------------------------------------------- #
# 机种 / 累进 CRUD 与步序文件联动
# ---------------------------------------------------------------------- #
def test_machine_crud(cfg):
    assert cfg.add_machine("VRV6") is True
    assert cfg.add_machine("VRV6") is False  # 重复
    assert cfg.get_machine_names() == ["VRV6"]

    cfg.add_rate("VRV6", "2P787591-1")
    cfg.add_rate("VRV6", "V1.2")
    assert cfg.get_machine_rates("VRV6") == ["2P787591-1", "V1.2"]

    assert cfg.rename_machine("VRV6", "VRV7") is True
    assert cfg.get_machine_names() == ["VRV7"]
    assert cfg.get_machine_rates("VRV7") == ["2P787591-1", "V1.2"]


def test_delete_machine_removes_step_files(cfg):
    cfg.add_machine("A")
    cfg.add_rate("A", "R1")
    cfg.set_steps("A", "R1", [{"type": "wait", "seconds": 1}])
    assert cfg.get_steps_file("A", "R1") and __import__("os").path.exists(
        cfg.get_steps_file("A", "R1")
    )
    assert cfg.delete_machine("A") is True
    assert __import__("os").path.exists(cfg.get_steps_file("A", "R1")) is False


def test_rate_rename_moves_step_file(cfg):
    cfg.add_machine("M")
    cfg.add_rate("M", "old")
    cfg.set_steps("M", "old", [{"type": "wait", "seconds": 1}])
    assert cfg.rename_rate("M", "old", "new") is True
    assert cfg.has_steps("M", "new") is True
    assert cfg.has_steps("M", "old") is False
    # 旧文件应已被改名(不再存在)
    import os

    assert os.path.exists(cfg.get_steps_file("M", "old")) is False


# ---------------------------------------------------------------------- #
# 步序读写 + mtime 感知缓存
# ---------------------------------------------------------------------- #
def test_steps_roundtrip(cfg):
    cfg.add_machine("M")
    cfg.add_rate("M", "R")
    steps = [
        {"type": "launch", "path": "C:/x/y.exe"},
        {"type": "wait", "seconds": 0.5},
    ]
    assert cfg.set_steps("M", "R", steps) is True
    assert cfg.get_steps("M", "R") == steps
    assert cfg.has_steps("M", "R") is True


def test_external_edit_reloads_by_mtime(cfg):
    """外部手动编辑步骤文件(README Q6)后, 缓存在 mtime 变化时应自动重读。"""
    cfg.add_machine("M")
    cfg.add_rate("M", "R")
    cfg.set_steps("M", "R", [{"type": "wait", "seconds": 1}])
    assert cfg.get_steps("M", "R") == [{"type": "wait", "seconds": 1}]

    filepath = cfg._step_file_path("M", "R")
    time.sleep(0.01)  # 保证 mtime_ns 变化
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([{"type": "key", "key": "enter"}], f, ensure_ascii=False)
    assert cfg.get_steps("M", "R") == [{"type": "key", "key": "enter"}]


def test_atomic_write_leaves_no_tmp(cfg):
    cfg.add_machine("M")
    cfg.add_rate("M", "R")
    cfg.set_steps("M", "R", [])
    tmp_files = list(cfg._steps_dir.glob("*.tmp"))
    assert tmp_files == []


def test_corrupt_json_preserved_and_default(cfg):
    cfg.add_machine("M")
    cfg.add_rate("M", "R")
    filepath = cfg._step_file_path("M", "R")
    filepath.write_text("{ not valid json", encoding="utf-8")
    assert cfg.get_steps("M", "R") == []
    # 坏文件被改名留存, 不再覆盖
    corrupts = list(cfg._steps_dir.glob("*.json.corrupt-*"))
    assert len(corrupts) == 1
    assert filepath.exists() is False


# ---------------------------------------------------------------------- #
# 点击位置库
# ---------------------------------------------------------------------- #
def test_click_point_crud(cfg):
    cfg.add_click_point("点A", 100, 200, "left")
    assert cfg.get_click_point("点A") == {"x": 100, "y": 200, "button": "left"}

    cfg.add_control_point("控件B", "Button", "开始", "id_1", "double")
    data = cfg.get_click_point("控件B")
    assert data["type"] == "control" and data["control_type"] == "Button"

    assert cfg.update_click_point("点A", 300, 400, "right") is True
    assert cfg.delete_click_point("点A") is True
    assert cfg.delete_click_point("点A") is False
