# -*- coding: utf-8 -*-
"""打包产物存活冒烟: 启动 exe, 检查进程存活 + 日志是否生成。

不能依赖控制台输出(windowed 模式无 stdout), 故用"进程存活 + 日志文件"
两个可观测信号判断。日志路径 = <exe 所在目录>/logs/auto_isp.log
"""
import subprocess
import sys
import time
from pathlib import Path

EXE = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/AutoISP300.exe").resolve()
WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 14

log = EXE.parent / "logs" / "auto_isp.log"
if log.exists():
    log.unlink()
print(f"exe      : {EXE}")
print(f"启动前日志: {'已清理' if not log.exists() else '存在'}")

proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
print(f"已启动 PID={proc.pid}, 等待 {WAIT}s ...")
time.sleep(WAIT)

alive = proc.poll() is None
print(f"进程存活: {alive}  (exit code: {proc.poll()})")

log_ok = log.exists()
print(f"日志生成: {log_ok}")
if log_ok:
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"日志行数: {len(lines)}")
    for ln in lines[-5:]:
        print("   ", ln)

if alive:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    print("已终止进程")

ok = alive and log_ok
print()
print("打包产物存活冒烟:", "通过" if ok else "失败")
raise SystemExit(0 if ok else 1)
