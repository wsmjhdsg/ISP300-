"""ExecutionSession 执行循环测试: 统计口径 / 校验跳过 / 主动停止 / finally 清理。

pyautogui 在 simulator 内是"函数内延迟导入", 测试时向 sys.modules 注入伪造模块,
避免真实依赖与真实鼠标动作; 同时关闭 IME 真实切换(IME_ENABLED=False)。
openfile 步骤: file_dialog 的对话框填充以 monkeypatch 替身注入, 验证调度分支。
"""
import os
import sys
import threading
import time

import pytest

from core.constants import OpenFileModes
from core.simulator import ExecutionSession, Simulator


class _FakePyAutoGui:
    """记录调用但不产生真实鼠标/键盘动作的替身。"""

    def __init__(self):
        self.calls = []

    def position(self):
        return (0, 0)

    def moveTo(self, *a, **k):
        self.calls.append(("moveTo", a))

    def click(self, *a, **k):
        self.calls.append(("click", a))

    def rightClick(self, *a, **k):
        self.calls.append(("rightClick", a))

    def doubleClick(self, *a, **k):
        self.calls.append(("doubleClick", a))

    def typewrite(self, text, **k):
        self.calls.append(("typewrite", text))

    def press(self, key, **k):
        self.calls.append(("press", key))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))


@pytest.fixture(autouse=True)
def fake_pyautogui(monkeypatch):
    fake = _FakePyAutoGui()
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setattr(ExecutionSession, "IME_ENABLED", False)
    monkeypatch.setattr(ExecutionSession, "ESC_ENABLED", False)  # 不注册真实键盘钩子
    return fake


def _run(steps, points=None, session=None, stop_on_error=True):
    """同步执行并返回 (summary, logs)。默认开启'失败即中止'(与引擎默认一致)。"""
    session = session or ExecutionSession()
    logs = []
    summary = session.execute_steps(
        steps, points or {}, log_callback=logs.append, stop_on_error=stop_on_error
    )
    return summary, logs


def test_all_success_counts_correct():
    steps = [
        {"type": "wait", "seconds": 0.01},
        {"type": "key", "key": "enter"},
        {"type": "type", "text": "abc"},
    ]
    summary, _ = _run(steps)
    assert summary["total"] == 3
    assert summary["success"] == 3
    assert summary["failed"] == 0
    assert not summary.get("stopped")


def test_failed_and_invalid_steps_not_counted_as_success():
    # 关闭"失败即中止"以验证统计口径: launch 文件不存在 -> 执行失败;
    # 未知类型 -> 校验失败跳过; 两者都不计 success, 且不阻断后续步骤
    monkeypatch_fail = pytest.MonkeyPatch()
    monkeypatch_fail.setattr(
        Simulator, "launch_program", staticmethod(lambda path: False)
    )
    try:
        steps = [
            {"type": "launch", "path": "C:/__no_such__/app.exe"},
            {"type": "wat"},
            {"type": "wait", "seconds": 0.01},
        ]
        summary, _ = _run(steps, stop_on_error=False)
    finally:
        monkeypatch_fail.undo()
    assert summary["total"] == 3
    assert summary["success"] == 1
    assert summary["failed"] == 2
    assert not summary.get("aborted")


def test_stop_on_error_aborts_and_skips_following():
    # 默认(失败即中止): 第 1 步失败 -> 后续步骤不再执行
    monkeypatch_fail = pytest.MonkeyPatch()
    monkeypatch_fail.setattr(
        Simulator, "launch_program", staticmethod(lambda path: False)
    )
    try:
        steps = [
            {"type": "launch", "path": "C:/__no_such__/app.exe"},
            {"type": "wait", "seconds": 0.01},
        ]
        summary, logs = _run(steps)
    finally:
        monkeypatch_fail.undo()
    assert summary["total"] == 2
    assert summary["success"] == 0
    assert summary["failed"] == 1
    assert summary.get("aborted") is True
    assert summary.get("aborted_at") == 1
    assert any("失败即中止" in line for line in logs)


def test_stop_on_error_validation_error_also_aborts():
    # 校验失败(未知步骤类型)同样触发中止
    summary, logs = _run([{"type": "wat"}, {"type": "wait", "seconds": 0.01}])
    assert summary["success"] == 0
    assert summary["failed"] == 1
    assert summary.get("aborted") is True
    assert summary.get("aborted_at") == 1


def test_click_missing_point_reported_as_failed():
    steps = [{"type": "click", "point_name": "不存在", "x": None, "y": None}]
    summary, _ = _run(steps, points={})
    assert summary["failed"] == 1
    assert summary["success"] == 0


def test_request_stop_aborts_promptly():
    session = ExecutionSession()
    result = {}

    def worker():
        logs = []
        result["summary"] = session.execute_steps(
            [{"type": "wait", "seconds": 60}], {}, log_callback=logs.append
        )

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    time.sleep(0.2)
    session.request_stop()
    t.join(timeout=3)
    assert not t.is_alive()
    assert result["summary"]["stopped"] is True
    assert result["summary"]["elapsed"] < 10  # 未被 60s 长等待拖住


def test_finally_restores_ime_and_stops_listener_even_on_error():
    session = ExecutionSession()
    session._ime_switched = True  # 模拟曾切换(IME_ENABLED=False 下不会被真实执行切换)
    steps = [{"type": "launch", "path": "C:/__no_such__/app.exe"}]
    summary, _ = _run(steps, session=session)
    # 即便单步失败, 收尾逻辑也跑完: 键盘监听已停、IME 状态已复位
    assert session._kb_listener is None
    assert session._ime_switched is False
    assert summary["failed"] == 1


def test_esc_listener_sets_stop_event(monkeypatch):
    """ESC 全局监听(假 pynput): 按下 ESC -> stop_event 置位, 收尾 stop 监听。"""
    import types

    class _Key:
        esc = object()

    class _FakeListener:
        instances = []

        def __init__(self, on_press=None):
            self.on_press = on_press
            self.stopped = False

        def start(self):
            _FakeListener.instances.append(self)

        def stop(self):
            self.stopped = True

        def join(self, timeout=None):
            pass

    pynput_mod = types.ModuleType("pynput")
    keyboard_mod = types.ModuleType("pynput.keyboard")
    keyboard_mod.Key = _Key
    keyboard_mod.Listener = _FakeListener
    pynput_mod.keyboard = keyboard_mod
    monkeypatch.setitem(sys.modules, "pynput", pynput_mod)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard_mod)
    monkeypatch.setattr(ExecutionSession, "ESC_ENABLED", True)

    session = ExecutionSession()
    session._start_esc_listener()
    assert _FakeListener.instances, "监听器应已启动"
    listener = _FakeListener.instances[-1]
    assert not session._stop_requested()

    listener.on_press(_Key.esc)  # 模拟用户按 ESC
    assert session._stop_requested(), "按 ESC 应触发停止"

    session._stop_esc_listener()
    assert session._kb_listener is None
    assert listener.stopped


# ---------------------------------------------------------------------- #
# openfile 步骤调度分支(以 monkeypatch 替身验证, 不触碰真实对话框)
# ---------------------------------------------------------------------- #
@pytest.fixture
def fake_fdm(monkeypatch):
    """把 simulator 引用的 core.file_dialog 挂到替身上。"""
    import core.file_dialog as fdm

    calls = {"fill": 0, "fill_paths": [], "latest": None}

    def fake_fill(path, timeout=None, poll=None, stop_check=None):
        calls["fill"] += 1
        calls["fill_paths"].append(path)
        return True, "filled"

    def fake_latest(directory, pattern="*.i3s"):
        return str(directory) + "/latest.i3s"

    monkeypatch.setattr(fdm, "fill_open_dialog", fake_fill)
    monkeypatch.setattr(fdm, "find_latest_file", fake_latest)
    return calls


def test_openfile_path_mode_success_counts(fake_fdm):
    steps = [{"type": "openfile", "mode": "path", "path": __file__}]
    summary, _ = _run(steps)
    assert summary["success"] == 1 and summary["failed"] == 0
    assert fake_fdm["fill"] == 1


def test_openfile_path_missing_file_fails_without_fill(fake_fdm):
    steps = [{"type": "openfile", "mode": "path", "path": "C:/__no_such__.i3s"}]
    summary, logs = _run(steps)
    assert summary["failed"] == 1 and summary["success"] == 0
    assert fake_fdm["fill"] == 0  # 不存在时不应打开对话框干等
    assert any("不存在" in line for line in logs)


def test_openfile_latest_mode(fake_fdm, tmp_path):
    steps = [
        {
            "type": "openfile",
            "mode": OpenFileModes.LATEST,
            "dir": str(tmp_path),
            "pattern": "*.i3s",
        }
    ]
    summary, _ = _run(steps)
    assert summary["success"] == 1 and summary["failed"] == 0


def test_openfile_latest_bad_dir_fails(fake_fdm, monkeypatch, tmp_path):
    import core.file_dialog as fdm

    monkeypatch.setattr(fdm, "find_latest_file", lambda d, p="*.i3s": None)
    steps = [
        {"type": "openfile", "mode": "latest", "dir": str(tmp_path), "pattern": "*.i3s"}
    ]
    summary, _ = _run(steps)
    assert summary["failed"] == 1 and fake_fdm["fill"] == 0


def test_openfile_pick_unresolved_fails(fake_fdm):
    # 绕过界面直接执行 pick -> 明确失败而不是抛异常
    steps = [{"type": "openfile", "mode": "pick"}]
    summary, logs = _run(steps)
    assert summary["failed"] == 1 and fake_fdm["fill"] == 0
    assert any("pick" in line.lower() for line in logs)


def test_openfile_path_normalized_to_backslashes(fake_fdm, tmp_path):
    """Tk 选择器返回正斜杠路径: 填入对话框前必须规范化为反斜杠(修复'文件名无效')。"""
    f = tmp_path / "SOFT.i3s"
    f.write_text("x")
    fwd = str(f).replace("\\", "/")  # 模拟 Tk 返回形式
    steps = [{"type": "openfile", "mode": "path", "path": fwd}]
    summary, _ = _run(steps)
    assert summary["success"] == 1
    assert fake_fdm["fill_paths"] == [os.path.normpath(fwd)]


# ---------------------------------------------------------------------- #
# waitresult 步骤(烧录完成弹窗判定)调度分支 —— 以替身验证, 不触碰真实弹窗
# ---------------------------------------------------------------------- #
@pytest.fixture
def fake_rdm(monkeypatch):
    """把 simulator 引用的 core.result_dialog 挂到替身上。"""
    import core.result_dialog as rdm

    calls = {"count": 0, "timeouts": [], "result": (True, "Verify OK")}

    def fake_wait(timeout=None, poll=None, stop_check=None):
        calls["count"] += 1
        calls["timeouts"].append(timeout)
        return calls["result"]

    monkeypatch.setattr(rdm, "wait_burn_result", fake_wait)
    return calls


def test_waitresult_ok_counts_success(fake_rdm):
    fake_rdm["result"] = (True, "Verify OK")
    summary, logs = _run([{"type": "waitresult", "timeout": 30}])
    assert summary["success"] == 1 and summary["failed"] == 0
    assert fake_rdm["count"] == 1
    assert fake_rdm["timeouts"] == [30]
    assert any("成功" in line for line in logs)


def test_waitresult_timeout_is_failure_and_aborts(fake_rdm):
    # 用户确认: 没收到 OK 弹窗就是失败(超时 / 内容非 OK 都按失败, 且失败即中止)
    fake_rdm["result"] = (False, "等待烧录完成弹窗超时(120s)")
    steps = [{"type": "waitresult"}, {"type": "wait", "seconds": 0.01}]
    summary, logs = _run(steps)
    assert summary["success"] == 0
    assert summary["failed"] == 1
    assert summary.get("aborted") is True
    assert fake_rdm["count"] == 1
    # 默认超时来自 SimulatorConfig.RESULT_TIMEOUT
    assert fake_rdm["timeouts"] == [120.0]


def test_waitresult_default_timeout_passed(fake_rdm):
    from core.constants import SimulatorConfig

    _run([{"type": "waitresult"}])
    assert fake_rdm["timeouts"] == [SimulatorConfig.RESULT_TIMEOUT]


def test_waitresult_failure_always_aborts_even_if_fail_fast_disabled(fake_rdm):
    """NG/超时是成败判定: 即便关掉通用'失败即中止', waitresult 失败也必须停止。"""
    fake_rdm["result"] = (False, "等待烧录完成弹窗超时(120s)")
    steps = [{"type": "waitresult"}, {"type": "wait", "seconds": 0.01}]
    summary, _ = _run(steps, stop_on_error=False)
    assert summary["success"] == 0
    assert summary["failed"] == 1
    assert summary.get("aborted") is True


def test_waitresult_invalid_timeout_fails_validation(monkeypatch):
    # 手改 JSON 塞入非法 timeout: 校验层拦截 -> 步骤失败并中止(不进入轮询)
    steps = [{"type": "waitresult", "timeout": "abc"}]
    monkeypatch.setattr(
        "core.simulator.rdm.wait_burn_result",
        lambda **k: (_ for _ in ()).throw(AssertionError("不应调用轮询")),
    )
    summary, logs = _run(steps)
    assert summary["failed"] == 1 and summary["success"] == 0
    assert summary.get("aborted") is True
    assert any("timeout" in line for line in logs)
