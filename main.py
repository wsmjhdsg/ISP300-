"""
ISP300 自动化烧录工具 - 主入口
"""
from core.config_manager import ConfigManager
from ui.main_window import MainWindow


def main():
    config = ConfigManager()
    app = MainWindow(config)
    app.run()


if __name__ == "__main__":
    main()