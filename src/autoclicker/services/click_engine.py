from __future__ import annotations

import ctypes
import random
import threading
from dataclasses import replace
from ctypes import wintypes

from autoclicker.domain.models import ClickDeliveryResult, ClickPoint, ClickSettings, RuntimeStatus, TargetWindow

user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL


class ClickEngine:
    """Owns runtime state, Win32 click delivery, and the background click loop."""

    def __init__(self) -> None:
        self._status = RuntimeStatus()
        self._running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    @property
    def status(self) -> RuntimeStatus:
        with self._lock:
            return replace(self._status)

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start_loop(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        settings: ClickSettings,
        *,
        use_post_message: bool = False,
    ) -> bool:
        target_hwnd = target_window.effective_hwnd
        if target_hwnd is None or not user32.IsWindow(target_hwnd):
            with self._lock:
                self._status.state = "Error"
                self._status.last_message = "Select a valid target window before starting the loop."
            return False

        with self._lock:
            if self._running:
                self._status.last_message = "Background click loop is already running."
                return False

            self._stop_event.clear()
            self._running = True
            self._status.state = "Running"
            self._status.completed_clicks = 0
            self._status.last_message = (
                f"Background click loop started for HWND {target_hwnd} at point ({point.x}, {point.y})."
            )

            worker_target = replace(target_window)
            worker_point = replace(point)
            worker_settings = replace(settings)
            self._worker_thread = threading.Thread(
                target=self._run_loop,
                args=(worker_target, worker_point, worker_settings, use_post_message),
                daemon=True,
                name="background-click-loop",
            )
            self._worker_thread.start()
            return True

    def stop(self) -> None:
        thread_to_join: threading.Thread | None = None

        with self._lock:
            if not self._running and self._worker_thread is None:
                self._status.state = "Stopped"
                self._status.last_message = "Background click loop is not running."
                return

            self._stop_event.set()
            self._status.state = "Stopping"
            self._status.last_message = "Stopping background click loop..."
            thread_to_join = self._worker_thread

        if thread_to_join is not None and thread_to_join.is_alive() and threading.current_thread() is not thread_to_join:
            thread_to_join.join(timeout=1.0)

    def send_test_click(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        *,
        button: str = "left",
        use_post_message: bool = False,
    ) -> ClickDeliveryResult:
        target_hwnd = target_window.effective_hwnd
        if target_hwnd is None:
            return self._build_result(
                success=False,
                message="No target window is selected for background click.",
                target_window=target_window,
                point=point,
                button=button,
                used_post_message=use_post_message,
            )

        if not user32.IsWindow(target_hwnd):
            return self._build_result(
                success=False,
                message=f"Target HWND {target_hwnd} is no longer valid.",
                target_window=target_window,
                point=point,
                button=button,
                used_post_message=use_post_message,
            )

        down_message, up_message, down_wparam = self._resolve_button_messages(button)
        lparam = self._pack_point(point.x, point.y)
        transport_name = "PostMessage" if use_post_message else "SendMessage"

        if use_post_message:
            move_ok = bool(user32.PostMessageW(target_hwnd, WM_MOUSEMOVE, 0, lparam))
            down_ok = bool(user32.PostMessageW(target_hwnd, down_message, down_wparam, lparam))
            up_ok = bool(user32.PostMessageW(target_hwnd, up_message, 0, lparam))
            if not (move_ok and down_ok and up_ok):
                error_code = ctypes.get_last_error()
                return self._build_result(
                    success=False,
                    message=(
                        f"{transport_name} failed for HWND {target_hwnd} at ({point.x}, {point.y}). "
                        f"Win32 last error: {error_code}."
                    ),
                    target_window=target_window,
                    point=point,
                    button=button,
                    used_post_message=use_post_message,
                )
        else:
            user32.SendMessageW(target_hwnd, WM_MOUSEMOVE, 0, lparam)
            user32.SendMessageW(target_hwnd, down_message, down_wparam, lparam)
            user32.SendMessageW(target_hwnd, up_message, 0, lparam)

        with self._lock:
            self._status.completed_clicks += 1
            self._status.last_message = (
                f"{transport_name} dispatched a {button} click to HWND {target_hwnd} "
                f"at client point ({point.x}, {point.y})."
            )
            message = self._status.last_message

        return ClickDeliveryResult(
            success=True,
            message=message,
            parent_hwnd=target_window.hwnd,
            target_hwnd=target_window.effective_hwnd,
            x=point.x,
            y=point.y,
            button=button,
            used_post_message=use_post_message,
        )

    def _run_loop(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        settings: ClickSettings,
        use_post_message: bool,
    ) -> None:
        try:
            while not self._stop_event.is_set():
                result = self.send_test_click(
                    target_window,
                    point,
                    button=settings.mouse_button,
                    use_post_message=use_post_message,
                )
                if not result.success:
                    with self._lock:
                        self._status.state = "Error"
                        self._status.last_message = result.message
                        self._running = False
                        self._worker_thread = None
                    return

                max_clicks = settings.max_clicks if settings.max_clicks and settings.max_clicks > 0 else None
                if max_clicks is not None:
                    with self._lock:
                        completed_clicks = self._status.completed_clicks
                    if completed_clicks >= max_clicks:
                        with self._lock:
                            self._status.state = "Stopped"
                            self._status.last_message = (
                                f"Background click loop reached the max click limit ({max_clicks})."
                            )
                            self._running = False
                            self._worker_thread = None
                        return

                delay_seconds = self._next_delay_seconds(settings)
                if self._stop_event.wait(delay_seconds):
                    break
        finally:
            with self._lock:
                if self._status.state == "Running":
                    self._status.state = "Stopped"
                    self._status.last_message = "Background click loop stopped."
                elif self._status.state == "Stopping":
                    self._status.state = "Stopped"
                    self._status.last_message = "Background click loop stopped."
                self._running = False
                self._worker_thread = None
                self._stop_event.clear()

    def _build_result(
        self,
        *,
        success: bool,
        message: str,
        target_window: TargetWindow,
        point: ClickPoint,
        button: str,
        used_post_message: bool,
    ) -> ClickDeliveryResult:
        with self._lock:
            self._status.last_message = message

        return ClickDeliveryResult(
            success=success,
            message=message,
            parent_hwnd=target_window.hwnd,
            target_hwnd=target_window.effective_hwnd,
            x=point.x,
            y=point.y,
            button=button,
            used_post_message=used_post_message,
        )

    def _resolve_button_messages(self, button: str) -> tuple[int, int, int]:
        normalized = button.lower().strip()
        if normalized == "right":
            return WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON
        return WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON

    def _pack_point(self, x: int, y: int) -> int:
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    def _next_delay_seconds(self, settings: ClickSettings) -> float:
        if settings.use_random_delay:
            minimum = max(1, settings.random_min_ms)
            maximum = max(1, settings.random_max_ms)
            low, high = sorted((minimum, maximum))
            return random.uniform(low, high) / 1000.0
        return max(1, settings.delay_ms) / 1000.0
