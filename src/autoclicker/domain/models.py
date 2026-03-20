from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


TRUE_TEXTS = {"1", "true", "yes", "y", "on"}
FALSE_TEXTS = {"0", "false", "no", "n", "off"}
MOUSE_BUTTONS = {"left", "right"}
DELIVERY_MODES = {"send", "post"}


def _coerce_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    return text or default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUE_TEXTS:
            return True
        if normalized in FALSE_TEXTS:
            return False
    return default


def _coerce_int(
    value: Any,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        coerced = int(value)
    except (TypeError, ValueError):
        coerced = default

    if minimum is not None:
        coerced = max(minimum, coerced)
    if maximum is not None:
        coerced = min(maximum, coerced)
    return coerced


def _coerce_optional_int(
    value: Any,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None or value == "":
        return None

    try:
        if isinstance(value, bool):
            raise ValueError
        coerced = int(value)
    except (TypeError, ValueError):
        return None

    if minimum is not None and coerced < minimum:
        return None
    if maximum is not None and coerced > maximum:
        return None
    return coerced


def _coerce_choice(value: Any, *, allowed: set[str], default: str) -> str:
    normalized = _coerce_text(value, default=default).lower()
    return normalized if normalized in allowed else default


@dataclass(slots=True)
class TargetWindow:
    hwnd: int | None = None
    title: str = ""
    class_name: str = ""
    process_id: int | None = None
    child_hwnd: int | None = None

    @property
    def effective_hwnd(self) -> int | None:
        return self.child_hwnd or self.hwnd

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "TargetWindow":
        if not isinstance(raw, Mapping):
            return cls()

        hwnd = _coerce_optional_int(raw.get("hwnd"), minimum=1)
        child_hwnd = _coerce_optional_int(raw.get("child_hwnd"), minimum=1)
        if child_hwnd == hwnd:
            child_hwnd = None

        return cls(
            hwnd=hwnd,
            title=_coerce_text(raw.get("title")),
            class_name=_coerce_text(raw.get("class_name")),
            process_id=_coerce_optional_int(raw.get("process_id"), minimum=1),
            child_hwnd=child_hwnd,
        )


@dataclass(slots=True)
class ClickPoint:
    name: str = "Primary"
    x: int = 0
    y: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "ClickPoint":
        if not isinstance(raw, Mapping):
            return cls()

        return cls(
            name=_coerce_text(raw.get("name"), default="Primary"),
            x=_coerce_int(raw.get("x"), 0),
            y=_coerce_int(raw.get("y"), 0),
        )


@dataclass(slots=True)
class ClickSettings:
    delay_ms: int = 1000
    use_random_delay: bool = False
    random_min_ms: int = 900
    random_max_ms: int = 1100
    max_clicks: int | None = None
    mouse_button: str = "left"
    delivery_mode: str = "send"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "ClickSettings":
        if not isinstance(raw, Mapping):
            return cls()

        random_min_ms = _coerce_int(raw.get("random_min_ms"), 900, minimum=1, maximum=3_600_000)
        random_max_ms = _coerce_int(raw.get("random_max_ms"), 1100, minimum=1, maximum=3_600_000)
        random_min_ms, random_max_ms = sorted((random_min_ms, random_max_ms))

        return cls(
            delay_ms=_coerce_int(raw.get("delay_ms"), 1000, minimum=1, maximum=3_600_000),
            use_random_delay=_coerce_bool(raw.get("use_random_delay"), default=False),
            random_min_ms=random_min_ms,
            random_max_ms=random_max_ms,
            max_clicks=_coerce_optional_int(raw.get("max_clicks"), minimum=1),
            mouse_button=_coerce_choice(raw.get("mouse_button"), allowed=MOUSE_BUTTONS, default="left"),
            delivery_mode=_coerce_choice(raw.get("delivery_mode"), allowed=DELIVERY_MODES, default="send"),
        )


@dataclass(slots=True)
class HotkeySettings:
    start_stop: str = "F8"
    capture_point: str = "F9"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "HotkeySettings":
        if not isinstance(raw, Mapping):
            return cls()

        return cls(
            start_stop=_coerce_text(raw.get("start_stop"), default="F8"),
            capture_point=_coerce_text(raw.get("capture_point"), default="F9"),
        )


@dataclass(slots=True)
class RuntimeStatus:
    state: str = "Ready"
    completed_clicks: int = 0
    last_message: str = "Project scaffold created."


@dataclass(slots=True)
class ClickDeliveryResult:
    success: bool
    message: str
    parent_hwnd: int | None = None
    target_hwnd: int | None = None
    x: int = 0
    y: int = 0
    button: str = "left"
    used_post_message: bool = False


@dataclass(slots=True)
class PointCaptureResult:
    success: bool
    message: str
    screen_x: int = 0
    screen_y: int = 0
    client_x: int = 0
    client_y: int = 0
    target_hwnd: int | None = None


@dataclass(slots=True)
class AppConfig:
    target_window: TargetWindow = field(default_factory=TargetWindow)
    click_settings: ClickSettings = field(default_factory=ClickSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    points: list[ClickPoint] = field(default_factory=lambda: [ClickPoint()])

    def normalized(self) -> "AppConfig":
        return AppConfig.from_dict(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | Mapping[str, Any] | None) -> "AppConfig":
        if not isinstance(raw, Mapping):
            return cls()

        points_raw = raw.get("points")
        points = [ClickPoint.from_dict(point) for point in points_raw] if isinstance(points_raw, list) else []
        points = points or [ClickPoint()]

        return cls(
            target_window=TargetWindow.from_dict(raw.get("target_window")),
            click_settings=ClickSettings.from_dict(raw.get("click_settings")),
            hotkeys=HotkeySettings.from_dict(raw.get("hotkeys")),
            points=points,
        )

