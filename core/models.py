from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ClickPoint:
    name: str
    x: int
    y: int
    button: str = "left"

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "button": self.button}

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "ClickPoint":
        return cls(
            name=name,
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            button=data.get("button", "left"),
        )


@dataclass
class Step:
    type: str
    point_name: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    path: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    seconds: Optional[float] = None
    wait: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.type}
        if self.point_name is not None:
            result["point_name"] = self.point_name
        if self.x is not None:
            result["x"] = self.x
        if self.y is not None:
            result["y"] = self.y
        if self.button is not None:
            result["button"] = self.button
        if self.path is not None:
            result["path"] = self.path
        if self.text is not None:
            result["text"] = self.text
        if self.key is not None:
            result["key"] = self.key
        if self.seconds is not None:
            result["seconds"] = self.seconds
        if self.wait is not None:
            result["wait"] = self.wait
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Step":
        return cls(
            type=data.get("type", ""),
            point_name=data.get("point_name"),
            x=data.get("x"),
            y=data.get("y"),
            button=data.get("button"),
            path=data.get("path"),
            text=data.get("text"),
            key=data.get("key"),
            seconds=data.get("seconds"),
            wait=data.get("wait"),
        )


@dataclass
class ExecutionSummary:
    total: int = 0
    success: int = 0
    elapsed: float = 0.0
    interrupted: bool = False


@dataclass
class BurnerConfig:
    path: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"path": self.path}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BurnerConfig":
        return cls(path=data.get("path", ""))


@dataclass
class AppConfig:
    machines: Dict[str, List[str]] = field(default_factory=dict)
    click_points: Dict[str, ClickPoint] = field(default_factory=dict)
    burner: BurnerConfig = field(default_factory=BurnerConfig)
