import logging
import sys
from pathlib import Path
from typing import Optional


_logger: Optional[logging.Logger] = None


def get_logger(name: str = "auto_isp") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger.getChild(name) if name != "auto_isp" else _logger

    _logger = logging.getLogger("auto_isp")
    _logger.setLevel(logging.DEBUG)

    if not _logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)

        try:
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            file_handler = logging.FileHandler(
                log_dir / "auto_isp.log", encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            _logger.addHandler(file_handler)
        except OSError:
            pass

    return _logger.getChild(name) if name != "auto_isp" else _logger
