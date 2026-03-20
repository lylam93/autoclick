from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TargetWindow:
    hwnd: int | None = None
    title: str = ""
    class_name: str = ""
    process_id: int | None = None
    child_hwnd: int | None = None


@dataclass(slots=True)
class ClickPoint:
    name: str = "Primary"
    x: int = 0
    y: int = 0


@dataclass(slots=True)
class ClickSettings:
    delay_ms: int = 1000
    use_random_delay: bool = False
    random_min_ms: int = 900
    random_max_ms: int = 1100
    max_clicks: int | None = None
    mouse_button: str = "left"


@dataclass(slots=True)
class HotkeySettings:
    start_stop: str = "F8"
    capture_point: str = "F9"


@dataclass(slots=True)
class RuntimeStatus:
    state: str = "Ready"
    completed_clicks: int = 0
    last_message: str = "Project scaffold created."


@dataclass(slots=True)
class AppConfig:
    target_window: TargetWindow = field(default_factory=TargetWindow)
    click_settings: ClickSettings = field(default_factory=ClickSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    points: list[ClickPoint] = field(default_factory=lambda: [ClickPoint()])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        target_window = TargetWindow(**raw.get("target_window", {}))
        click_settings = ClickSettings(**raw.get("click_settings", {}))
        hotkeys = HotkeySettings(**raw.get("hotkeys", {}))
        points = [ClickPoint(**point) for point in raw.get("points", [])] or [ClickPoint()]
        return cls(
            target_window=target_window,
            click_settings=click_settings,
            hotkeys=hotkeys,
            points=points,
        )

