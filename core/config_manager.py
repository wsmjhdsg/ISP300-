"""配置管理器: 机种/累进 CRUD、点击位置库、步序文件读写(带缓存)与旧格式迁移。

设计要点:
- 单例门面: UI 层统一经由 ConfigManager 访问配置, 避免各自拼路径。
- 原子写盘: 先写 *.json.tmp 再 os.replace, 防止崩溃/断电损坏配置(历史教训:
  直接 open(w) 写一半被杀会损坏整个 JSON, 下次启动静默回退默认值)。
- 损坏自愈: 读取 JSON 失败时把坏文件改名留存(便于人工找回), 不覆盖、不静默丢数据。
- 步序缓存感知外部编辑: 缓存携带文件 mtime, 用户手动改 JSON(README Q6)后
  get_steps 自动重读, 不再出现"改了文件界面还是旧值"。
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.constants import ClickPointTypes
from core.logger import get_logger
from core.paths import app_base_dir

logger = get_logger(__name__)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ------------------------------------------------------------------ #
    # 初始化与通用 JSON 读写
    # ------------------------------------------------------------------ #
    def _initialize(self) -> None:
        self._base_dir = app_base_dir()
        self._config_dir = self._base_dir / "config"
        self._config_dir.mkdir(exist_ok=True)

        self._steps_dir = self._config_dir / "steps"
        self._steps_dir.mkdir(exist_ok=True)

        self._machines_file = self._config_dir / "machines.json"
        self._click_points_file = self._config_dir / "click_points.json"

        self.machines: Dict[str, List[str]] = self._load_json(
            self._machines_file, default={}
        )
        if not isinstance(self.machines, dict):
            self.machines = {}
        self._migrate_old_format()

        raw_click_points = self._load_json(self._click_points_file, default={})
        self.click_points: Dict[str, dict] = {
            name: data
            for name, data in raw_click_points.items()
            if isinstance(data, dict)
        }

        # 步序缓存: key=(机种, 累进) -> (文件 mtime_ns, 步骤列表); mtime 变化即失效
        self._steps_cache: Dict[Tuple[str, str], Tuple[Optional[int], List[dict]]] = {}
        logger.info("ConfigManager initialized")

    @staticmethod
    def _safe_name(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", name)

    def _step_file_path(self, machine: str, rate: str) -> Path:
        filename = f"{self._safe_name(machine)}_{self._safe_name(rate)}.json"
        return self._steps_dir / filename

    def _load_json(self, filepath: Path, default):
        if not filepath.exists():
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load {filepath}: {e}")
            # 坏文件改名留存, 避免下次启动反复告警, 也便于人工找回原始内容
            try:
                corrupt = filepath.with_suffix(
                    filepath.suffix + f".corrupt-{time.time_ns()}"
                )
                filepath.rename(corrupt)
                logger.warning(f"Corrupt file preserved as: {corrupt}")
            except OSError as rename_err:
                logger.error(f"Failed to preserve corrupt file: {rename_err}")
            return default

    @staticmethod
    def _atomic_write(filepath: Path, data) -> None:
        """原子写盘: 临时文件 + os.replace。崩溃/断电时要么旧文件完整, 要么新文件完整。"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = filepath.with_suffix(filepath.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, filepath)
        except OSError:
            try:  # 失败时清理残留临时文件, 避免掩盖后续问题
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _save_json(self, filepath: Path, data) -> None:
        try:
            self._atomic_write(filepath, data)
        except OSError as e:
            logger.error(f"Failed to save {filepath}: {e}")
            raise

    # ------------------------------------------------------------------ #
    # 旧格式迁移 (步骤内嵌在机种值下的早期格式 -> 独立步序文件)
    # ------------------------------------------------------------------ #
    def _migrate_old_format(self) -> None:
        changed = False
        for machine, value in list(self.machines.items()):
            if isinstance(value, dict) and "rates" in value:
                new_rates = []
                for rate, steps in value["rates"].items():
                    new_rates.append(rate)
                    if steps:
                        self._save_steps_to_disk(machine, rate, steps)
                self.machines[machine] = new_rates
                changed = True
        if changed:
            self._save_json(self._machines_file, self.machines)
            logger.info("Migrated old machine format")

    def _save_steps_to_disk(self, machine: str, rate: str, steps: List[dict]) -> None:
        self._save_json(self._step_file_path(machine, rate), steps)

    # ------------------------------------------------------------------ #
    # 机种 / 累进 CRUD (重命名/删除会联动步骤文件与缓存)
    # ------------------------------------------------------------------ #
    def get_machine_names(self) -> List[str]:
        return list(self.machines.keys())

    def get_machine_rates(self, name: str) -> List[str]:
        return list(self.machines.get(name, []))

    def add_machine(self, name: str) -> bool:
        if not name or not name.strip():
            return False
        name = name.strip()
        if name not in self.machines:
            self.machines[name] = []
            self._save_json(self._machines_file, self.machines)
            logger.info(f"Machine added: {name}")
            return True
        return False

    def rename_machine(self, old_name: str, new_name: str) -> bool:
        if not new_name or not new_name.strip():
            return False
        new_name = new_name.strip()
        if old_name in self.machines and new_name not in self.machines:
            rates = self.machines[old_name]
            for rate in rates:
                old_file = self._step_file_path(old_name, rate)
                new_file = self._step_file_path(new_name, rate)
                if old_file.exists():
                    old_file.rename(new_file)
                self._steps_cache.pop((old_name, rate), None)
            self.machines[new_name] = self.machines.pop(old_name)
            self._save_json(self._machines_file, self.machines)
            logger.info(f"Machine renamed: {old_name} -> {new_name}")
            return True
        return False

    def delete_machine(self, name: str) -> bool:
        if name in self.machines:
            for rate in self.machines[name]:
                self._delete_step_file(name, rate)
            del self.machines[name]
            self._save_json(self._machines_file, self.machines)
            logger.info(f"Machine deleted: {name}")
            return True
        return False

    def add_rate(self, machine: str, rate: str) -> bool:
        if not rate or not rate.strip():
            return False
        rate = rate.strip()
        if machine in self.machines and rate not in self.machines[machine]:
            self.machines[machine].append(rate)
            self._save_json(self._machines_file, self.machines)
            logger.info(f"Rate added: {machine}/{rate}")
            return True
        return False

    def delete_rate(self, machine: str, rate: str) -> bool:
        if machine in self.machines and rate in self.machines[machine]:
            self._delete_step_file(machine, rate)
            self.machines[machine].remove(rate)
            self._save_json(self._machines_file, self.machines)
            logger.info(f"Rate deleted: {machine}/{rate}")
            return True
        return False

    def rename_rate(self, machine: str, old_rate: str, new_rate: str) -> bool:
        if not new_rate or not new_rate.strip():
            return False
        new_rate = new_rate.strip()
        if machine in self.machines and old_rate in self.machines[machine]:
            if new_rate not in self.machines[machine]:
                old_file = self._step_file_path(machine, old_rate)
                new_file = self._step_file_path(machine, new_rate)
                if old_file.exists():
                    old_file.rename(new_file)
                self._steps_cache.pop((machine, old_rate), None)
                idx = self.machines[machine].index(old_rate)
                self.machines[machine][idx] = new_rate
                self._save_json(self._machines_file, self.machines)
                logger.info(f"Rate renamed: {machine}/{old_rate} -> {new_rate}")
                return True
        return False

    def _delete_step_file(self, machine: str, rate: str) -> None:
        f = self._step_file_path(machine, rate)
        if f.exists():
            try:
                f.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete step file {f}: {e}")
        self._steps_cache.pop((machine, rate), None)

    # ------------------------------------------------------------------ #
    # 步序文件: 读写 + mtime 感知缓存
    # ------------------------------------------------------------------ #
    def _step_mtime(self, filepath: Path) -> Optional[int]:
        try:
            return filepath.stat().st_mtime_ns
        except OSError:
            return None

    def get_steps(self, machine: str, rate: str) -> List[dict]:
        key = (machine, rate)
        filepath = self._step_file_path(machine, rate)
        mtime = self._step_mtime(filepath)

        cached = self._steps_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return list(cached[1])

        steps: List[dict] = []
        if filepath.exists():
            data = self._load_json(filepath, default=[])
            if isinstance(data, list):
                steps = data
        self._steps_cache[key] = (mtime, steps)
        return list(steps)

    def set_steps(self, machine: str, rate: str, steps: List[dict]) -> bool:
        filepath = self._step_file_path(machine, rate)
        self._save_json(filepath, steps)
        self._steps_cache[(machine, rate)] = (
            self._step_mtime(filepath),
            list(steps),
        )
        logger.info(f"Steps saved: {machine}/{rate} ({len(steps)} steps)")
        return True

    def has_steps(self, machine: str, rate: str) -> bool:
        return len(self.get_steps(machine, rate)) > 0

    def get_steps_file(self, machine: str, rate: str) -> str:
        return str(self._step_file_path(machine, rate))

    # ------------------------------------------------------------------ #
    # 点击位置库 (坐标点 + 控件点)
    # ------------------------------------------------------------------ #
    def get_click_point_names(self) -> List[str]:
        return list(self.click_points.keys())

    def get_click_point(self, name: str) -> dict:
        return dict(self.click_points.get(name, {}))

    def _save_click_points(self) -> None:
        self._save_json(self._click_points_file, self.click_points)

    def add_click_point(self, name: str, x: int, y: int, button: str = "left") -> None:
        self.click_points[name] = {"x": int(x), "y": int(y), "button": button}
        self._save_click_points()
        logger.info(f"Click point added: {name} ({x}, {y}) {button}")

    def add_control_point(
        self,
        name: str,
        control_type: str,
        title: str,
        auto_id: str,
        button: str = "left",
    ) -> None:
        self.click_points[name] = {
            "type": ClickPointTypes.CONTROL,
            "control_type": control_type or "",
            "title": title or "",
            "auto_id": auto_id or "",
            "button": button,
        }
        self._save_click_points()
        logger.info(f"Control point added: {name} ({control_type} {title} {auto_id})")

    def update_control_point(
        self,
        name: str,
        control_type: str,
        title: str,
        auto_id: str,
        button: str = "left",
    ) -> bool:
        if name in self.click_points:
            self.click_points[name] = {
                "type": ClickPointTypes.CONTROL,
                "control_type": control_type or "",
                "title": title or "",
                "auto_id": auto_id or "",
                "button": button,
            }
            self._save_click_points()
            logger.info(
                f"Control point updated: {name} ({control_type} {title} {auto_id})"
            )
            return True
        return False

    def delete_click_point(self, name: str) -> bool:
        if name in self.click_points:
            del self.click_points[name]
            self._save_click_points()
            logger.info(f"Click point deleted: {name}")
            return True
        return False

    def update_click_point(
        self, name: str, x: int, y: int, button: str = "left"
    ) -> bool:
        if name in self.click_points:
            self.click_points[name] = {"x": int(x), "y": int(y), "button": button}
            self._save_click_points()
            logger.info(f"Click point updated: {name} ({x}, {y}) {button}")
            return True
        return False
