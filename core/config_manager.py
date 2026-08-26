import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.logger import get_logger

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

    def _initialize(self) -> None:
        self._base_dir = Path(__file__).parent.parent.resolve()
        self._config_dir = self._base_dir / "config"
        self._config_dir.mkdir(exist_ok=True)

        self._steps_dir = self._config_dir / "steps"
        self._steps_dir.mkdir(exist_ok=True)

        self._machines_file = self._config_dir / "machines.json"
        self._click_points_file = self._config_dir / "click_points.json"
        self._burner_file = self._config_dir / "burner.json"

        self.machines: Dict[str, List[str]] = self._load_json(
            self._machines_file, default={}
        )
        self._migrate_old_format()

        raw_click_points = self._load_json(self._click_points_file, default={})
        self.click_points: Dict[str, dict] = {}
        for name, data in raw_click_points.items():
            if isinstance(data, dict):
                self.click_points[name] = data

        raw_burner = self._load_json(self._burner_file, default={"path": ""})
        self.burner: Dict[str, str] = (
            raw_burner if isinstance(raw_burner, dict) else {"path": ""}
        )

        self._steps_cache: Dict[Tuple[str, str], List[dict]] = {}
        logger.info("ConfigManager initialized")

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

    @staticmethod
    def _safe_name(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", name)

    def _step_file_path(self, machine: str, rate: str) -> Path:
        filename = f"{self._safe_name(machine)}_{self._safe_name(rate)}.json"
        return self._steps_dir / filename

    def _load_json(self, filepath: Path, default):
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load {filepath}: {e}")
                return default
        return default

    def _save_json(self, filepath: Path, data) -> None:
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save {filepath}: {e}")
            raise

    def _save_steps_to_disk(self, machine: str, rate: str, steps: List[dict]) -> None:
        filepath = self._step_file_path(machine, rate)
        self._save_json(filepath, steps)

    def get_burner_path(self) -> str:
        return self.burner.get("path", "")

    def set_burner_path(self, path: str) -> None:
        self.burner["path"] = path
        self._save_json(self._burner_file, self.burner)
        logger.info(f"Burner path updated: {path}")

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
            rates = self.machines[name]
            for rate in rates:
                f = self._step_file_path(name, rate)
                if f.exists():
                    try:
                        f.unlink()
                    except OSError as e:
                        logger.warning(f"Failed to delete step file {f}: {e}")
                self._steps_cache.pop((name, rate), None)
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
            f = self._step_file_path(machine, rate)
            if f.exists():
                try:
                    f.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete step file {f}: {e}")
            self._steps_cache.pop((machine, rate), None)
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

    def get_steps(self, machine: str, rate: str) -> List[dict]:
        key = (machine, rate)
        if key in self._steps_cache:
            return list(self._steps_cache[key])
        filepath = self._step_file_path(machine, rate)
        steps: List[dict] = []
        if filepath.exists():
            data = self._load_json(filepath, default=[])
            if isinstance(data, list):
                steps = data
        self._steps_cache[key] = steps
        return list(steps)

    def set_steps(self, machine: str, rate: str, steps: List[dict]) -> bool:
        filepath = self._step_file_path(machine, rate)
        self._save_json(filepath, steps)
        self._steps_cache[(machine, rate)] = list(steps)
        logger.info(f"Steps saved: {machine}/{rate} ({len(steps)} steps)")
        return True

    def has_steps(self, machine: str, rate: str) -> bool:
        return len(self.get_steps(machine, rate)) > 0

    def get_steps_file(self, machine: str, rate: str) -> str:
        return str(self._step_file_path(machine, rate))

    def get_click_point_names(self) -> List[str]:
        return list(self.click_points.keys())

    def get_click_point(self, name: str) -> dict:
        return dict(self.click_points.get(name, {}))

    def add_click_point(self, name: str, x: int, y: int, button: str = "left") -> None:
        self.click_points[name] = {"x": int(x), "y": int(y), "button": button}
        self._save_json(self._click_points_file, self.click_points)
        logger.info(f"Click point added: {name} ({x}, {y}) {button}")

    def delete_click_point(self, name: str) -> bool:
        if name in self.click_points:
            del self.click_points[name]
            self._save_json(self._click_points_file, self.click_points)
            logger.info(f"Click point deleted: {name}")
            return True
        return False

    def update_click_point(
        self, name: str, x: int, y: int, button: str = "left"
    ) -> bool:
        if name in self.click_points:
            self.click_points[name] = {"x": int(x), "y": int(y), "button": button}
            self._save_json(self._click_points_file, self.click_points)
            logger.info(f"Click point updated: {name} ({x}, {y}) {button}")
            return True
        return False
