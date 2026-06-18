"""
配置管理模块
- 烧录器软件路径 (burner.json)
- 机种及累进结构 (machines.json)
- 点击坐标 + 点击方式 (click_points.json)
- 每个"机种+累进"独立步序文件 (steps/机种_累进.json)
"""
import json
import os
import re


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_dir = os.path.join(base_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.steps_dir = os.path.join(self.config_dir, "steps")
        os.makedirs(self.steps_dir, exist_ok=True)

        self.machines_file = os.path.join(self.config_dir, "machines.json")
        self.click_points_file = os.path.join(self.config_dir, "click_points.json")
        self.burner_file = os.path.join(self.config_dir, "burner.json")

        # 数据结构：
        # self.machines = { "机种名": ["累进1", "累进2", ...] }
        self.machines = self._load_json(self.machines_file, default={})

        # 兼容旧格式升级（如果之前是 {机种: {"rates": {...}}} 结构，自动转成新格式）
        self._migrate_old_format()

        # self.click_points = { "名称": {"x": 100, "y": 200, "button": "left"} }
        self.click_points = self._load_json(self.click_points_file, default={})

        # self.burner = { "path": "C:\\...\\ISP300.exe" }
        self.burner = self._load_json(self.burner_file, default={"path": ""})

    def _migrate_old_format(self):
        """兼容旧格式 machines.json，将内嵌步骤拆到独立文件"""
        changed = False
        for machine, value in list(self.machines.items()):
            if isinstance(value, dict) and "rates" in value:
                # 旧格式: {"rates": {rate: steps_array}}
                new_rates = []
                for rate, steps in value["rates"].items():
                    new_rates.append(rate)
                    # 如果有步骤内容，存到独立文件
                    if steps:
                        self.set_steps(machine, rate, steps)
                self.machines[machine] = new_rates
                changed = True
        if changed:
            self._save_json(self.machines_file, self.machines)

    def _safe_name(self, name):
        """将机种/累进名转为安全的文件名（替换特殊字符）"""
        return re.sub(r'[\\/:*?"<>|]', "_", name)

    def _step_file(self, machine, rate):
        """返回某个机种+累进对应的步序文件路径"""
        filename = f"{self._safe_name(machine)}_{self._safe_name(rate)}.json"
        return os.path.join(self.steps_dir, filename)

    def _load_json(self, filepath, default):
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return default
        return default

    def _save_json(self, filepath, data):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ========== 烧录器设置 ==========

    def get_burner_path(self):
        return self.burner.get("path", "")

    def set_burner_path(self, path):
        self.burner["path"] = path
        self._save_json(self.burner_file, self.burner)

    # ========== 机种管理 ==========

    def get_machine_names(self):
        return list(self.machines.keys())

    def get_machine_rates(self, name):
        return list(self.machines.get(name, []))

    def add_machine(self, name):
        if name not in self.machines:
            self.machines[name] = []
            self._save_json(self.machines_file, self.machines)
            return True
        return False

    def rename_machine(self, old_name, new_name):
        if old_name in self.machines and new_name not in self.machines:
            # 重命名机种时，对应的步序文件也要改名
            rates = self.machines[old_name]
            for rate in rates:
                old_file = self._step_file(old_name, rate)
                new_file = self._step_file(new_name, rate)
                if os.path.exists(old_file):
                    os.rename(old_file, new_file)
            self.machines[new_name] = self.machines.pop(old_name)
            self._save_json(self.machines_file, self.machines)
            return True
        return False

    def delete_machine(self, name):
        if name in self.machines:
            # 删除机种时，连带删除它下面所有累进的步序文件
            rates = self.machines[name]
            for rate in rates:
                f = self._step_file(name, rate)
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            del self.machines[name]
            self._save_json(self.machines_file, self.machines)
            return True
        return False

    def add_rate(self, machine, rate):
        if machine in self.machines:
            if rate not in self.machines[machine]:
                self.machines[machine].append(rate)
                self._save_json(self.machines_file, self.machines)
                return True
        return False

    def delete_rate(self, machine, rate):
        if machine in self.machines and rate in self.machines[machine]:
            # 删除累进时，对应的步序文件也删除
            f = self._step_file(machine, rate)
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
            self.machines[machine].remove(rate)
            self._save_json(self.machines_file, self.machines)
            return True
        return False

    def rename_rate(self, machine, old_rate, new_rate):
        if machine in self.machines and old_rate in self.machines[machine]:
            if new_rate not in self.machines[machine]:
                # 对应的步序文件改名
                old_file = self._step_file(machine, old_rate)
                new_file = self._step_file(machine, new_rate)
                if os.path.exists(old_file):
                    os.rename(old_file, new_file)
                idx = self.machines[machine].index(old_rate)
                self.machines[machine][idx] = new_rate
                self._save_json(self.machines_file, self.machines)
                return True
        return False

    # ========== 步序管理 (每个机种+累进存独立文件) ==========

    def get_steps(self, machine, rate):
        """读取某机种+累进的步骤数组"""
        filepath = self._step_file(machine, rate)
        if os.path.exists(filepath):
            steps = self._load_json(filepath, default=[])
            if isinstance(steps, list):
                return steps
        return []

    def set_steps(self, machine, rate, steps):
        """保存某机种+累进的步骤数组为独立 JSON 文件"""
        filepath = self._step_file(machine, rate)
        self._save_json(filepath, steps)
        return True

    def has_steps(self, machine, rate):
        """检查是否存在该组合的步序文件"""
        return os.path.exists(self._step_file(machine, rate))

    def get_steps_file(self, machine, rate):
        """返回步序文件路径（供外部查看/调试）"""
        return self._step_file(machine, rate)

    # ========== 点击位置管理 ==========

    def get_click_point_names(self):
        return list(self.click_points.keys())

    def get_click_point(self, name):
        return self.click_points.get(name, {})

    def add_click_point(self, name, x, y, button="left"):
        self.click_points[name] = {"x": x, "y": y, "button": button}
        self._save_json(self.click_points_file, self.click_points)

    def delete_click_point(self, name):
        if name in self.click_points:
            del self.click_points[name]
            self._save_json(self.click_points_file, self.click_points)
            return True
        return False

    def update_click_point(self, name, x, y, button="left"):
        if name in self.click_points:
            self.click_points[name] = {"x": x, "y": y, "button": button}
            self._save_json(self.click_points_file, self.click_points)
            return True
        return False