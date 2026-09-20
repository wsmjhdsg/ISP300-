import sys
from pathlib import Path


def app_base_dir() -> Path:
    """程序基准目录(绿色便携: 配置/日志都放这里)。

    - 源码运行: 项目根目录。
    - PyInstaller 打包后 (frozen): exe 所在目录, 保证 config/logs 写在 exe 旁,
      不依赖 __file__ 的临时解压目录, 整个文件夹拷贝即迁移。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()


def resource_path(name: str) -> Path:
    """定位随程序打包的资源文件(如图标)。

    - PyInstaller onefile: 资源经 --add-data 打进包, 运行期解压到临时目录,
      需从 sys._MEIPASS 读取(不是 exe 旁)。
    - 源码运行: 项目根下直接找。
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return Path(base) / name