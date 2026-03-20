from __future__ import annotations

from autoclicker.domain.models import HotkeySettings


class HotkeyService:
    """Placeholder service for configurable global hotkeys."""

    def __init__(self) -> None:
        self._registered = False

    @property
    def is_registered(self) -> bool:
        return self._registered

    def register(self, hotkeys: HotkeySettings) -> None:
        _ = hotkeys
        self._registered = True

    def unregister(self) -> None:
        self._registered = False

