from __future__ import annotations

from autoclicker.domain.models import RuntimeStatus


class ClickEngine:
    """Owns the future background click loop and runtime state."""

    def __init__(self) -> None:
        self._status = RuntimeStatus()
        self._running = False

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True
        self._status.state = "Running"
        self._status.last_message = "Click engine scaffold started."

    def stop(self) -> None:
        self._running = False
        self._status.state = "Stopped"
        self._status.last_message = "Click engine scaffold stopped."

