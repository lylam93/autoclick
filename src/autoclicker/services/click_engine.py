from __future__ import annotations

import ctypes
import random
import threading
import time
from dataclasses import replace
from ctypes import wintypes

from autoclicker.domain.models import ClickDeliveryResult, ClickPoint, ClickSettings, RuntimeStatus, TargetWindow
from autoclicker.services.app_logging import get_logger

user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
SW_RESTORE = 9
FOREGROUND_FOCUS_SETTLE_SECONDS = 0.05
FOREGROUND_CLICK_SETTLE_SECONDS = 0.01


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

LOGGER = get_logger("services.click_engine")


class ClickEngine:
    """Owns runtime state, Win32 click delivery, and the click loop."""

    def __init__(self) -> None:
        self._status = RuntimeStatus()
        self._running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        LOGGER.debug("ClickEngine initialized.")

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
    ) -> bool:
        target_hwnd = target_window.effective_hwnd
        if target_hwnd is None or not user32.IsWindow(target_hwnd):
            with self._lock:
                self._status.state = "Error"
                self._status.last_message = "Select a valid target window before starting the loop."
            LOGGER.warning("Refused to start loop because target HWND is invalid: %s", target_hwnd)
            return False

        delivery_mode = self._normalize_delivery_mode(settings.delivery_mode)
        transport_name = self._transport_name(delivery_mode)

        with self._lock:
            if self._running:
                self._status.last_message = "Click loop is already running."
                LOGGER.info("Ignored start request because the click loop is already running.")
                return False

            self._stop_event.clear()
            self._running = True
            self._status.state = "Running"
            self._status.completed_clicks = 0
            self._status.last_message = (
                f"Click loop started using {transport_name} for HWND {target_hwnd} at point ({point.x}, {point.y})."
            )

            worker_target = replace(target_window)
            worker_point = replace(point)
            worker_settings = replace(settings)
            self._worker_thread = threading.Thread(
                target=self._run_loop,
                args=(worker_target, worker_point, worker_settings),
                daemon=True,
                name="click-loop",
            )
            self._worker_thread.start()

        LOGGER.info(
            "Click loop started. transport=%s hwnd=%s point=(%s,%s) button=%s delay_ms=%s random=%s max_clicks=%s",
            transport_name,
            target_hwnd,
            point.x,
            point.y,
            settings.mouse_button,
            settings.delay_ms,
            settings.use_random_delay,
            settings.max_clicks,
        )
        return True

    def stop(self) -> None:
        thread_to_join: threading.Thread | None = None

        with self._lock:
            if not self._running and self._worker_thread is None:
                self._status.state = "Stopped"
                self._status.last_message = "Click loop is not running."
                LOGGER.info("Stop requested while the click loop was already stopped.")
                return

            self._stop_event.set()
            self._status.state = "Stopping"
            self._status.last_message = "Stopping click loop..."
            thread_to_join = self._worker_thread

        LOGGER.info("Stopping click loop.")
        if thread_to_join is not None and thread_to_join.is_alive() and threading.current_thread() is not thread_to_join:
            thread_to_join.join(timeout=1.0)

    def send_test_click(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        *,
        button: str = "left",
        delivery_mode: str = "send",
        restore_environment: bool = True,
    ) -> ClickDeliveryResult:
        delivery_mode = self._normalize_delivery_mode(delivery_mode)
        target_hwnd = target_window.effective_hwnd
        transport_name = self._transport_name(delivery_mode)
        LOGGER.debug(
            "Dispatching test click. transport=%s parent_hwnd=%s target_hwnd=%s point=(%s,%s) button=%s",
            transport_name,
            target_window.hwnd,
            target_hwnd,
            point.x,
            point.y,
            button,
        )

        if target_hwnd is None:
            LOGGER.warning("No target window is selected for click delivery.")
            return self._build_result(
                success=False,
                message="No target window is selected for click delivery.",
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        if not user32.IsWindow(target_hwnd):
            LOGGER.warning("Target HWND %s is no longer valid.", target_hwnd)
            return self._build_result(
                success=False,
                message=f"Target HWND {target_hwnd} is no longer valid.",
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        if delivery_mode == "foreground":
            return self._send_foreground_click(
                target_window,
                point,
                button=button,
                restore_environment=restore_environment,
            )
        return self._send_message_click(target_window, point, button=button, delivery_mode=delivery_mode)

    def _run_loop(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        settings: ClickSettings,
    ) -> None:
        delivery_mode = self._normalize_delivery_mode(settings.delivery_mode)
        restore_cursor = self._capture_cursor_position() if delivery_mode == "foreground" else None
        restore_foreground_hwnd = user32.GetForegroundWindow() if delivery_mode == "foreground" else None

        try:
            while not self._stop_event.is_set():
                result = self.send_test_click(
                    target_window,
                    point,
                    button=settings.mouse_button,
                    delivery_mode=delivery_mode,
                    restore_environment=False,
                )
                if not result.success:
                    with self._lock:
                        self._status.state = "Error"
                        self._status.last_message = result.message
                        self._running = False
                        self._worker_thread = None
                    LOGGER.error("Click loop aborted because click delivery failed: %s", result.message)
                    return

                max_clicks = settings.max_clicks if settings.max_clicks and settings.max_clicks > 0 else None
                if max_clicks is not None:
                    with self._lock:
                        completed_clicks = self._status.completed_clicks
                    if completed_clicks >= max_clicks:
                        with self._lock:
                            self._status.state = "Stopped"
                            self._status.last_message = f"Click loop reached the max click limit ({max_clicks})."
                            self._running = False
                            self._worker_thread = None
                        LOGGER.info("Click loop reached max_clicks=%s.", max_clicks)
                        return

                delay_seconds = self._next_delay_seconds(settings)
                LOGGER.debug("Next click delay: %.3f seconds", delay_seconds)
                if self._stop_event.wait(delay_seconds):
                    break
        finally:
            if delivery_mode == "foreground":
                self._restore_environment(restore_cursor, restore_foreground_hwnd)

            with self._lock:
                if self._status.state == "Running":
                    self._status.state = "Stopped"
                    self._status.last_message = "Click loop stopped."
                elif self._status.state == "Stopping":
                    self._status.state = "Stopped"
                    self._status.last_message = "Click loop stopped."
                self._running = False
                self._worker_thread = None
                self._stop_event.clear()
            LOGGER.info("Click loop stopped.")

    def _send_message_click(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        *,
        button: str,
        delivery_mode: str,
    ) -> ClickDeliveryResult:
        target_hwnd = target_window.effective_hwnd
        transport_name = self._transport_name(delivery_mode)
        down_message, up_message, down_wparam = self._resolve_button_messages(button)
        lparam = self._pack_point(point.x, point.y)

        if delivery_mode == "post":
            move_ok = bool(user32.PostMessageW(target_hwnd, WM_MOUSEMOVE, 0, lparam))
            down_ok = bool(user32.PostMessageW(target_hwnd, down_message, down_wparam, lparam))
            up_ok = bool(user32.PostMessageW(target_hwnd, up_message, 0, lparam))
            if not (move_ok and down_ok and up_ok):
                error_code = ctypes.get_last_error()
                LOGGER.warning(
                    "%s failed for HWND %s at (%s,%s). Win32 error=%s",
                    transport_name,
                    target_hwnd,
                    point.x,
                    point.y,
                    error_code,
                )
                return self._build_result(
                    success=False,
                    message=(
                        f"{transport_name} failed for HWND {target_hwnd} at ({point.x}, {point.y}). "
                        f"Win32 last error: {error_code}."
                    ),
                    target_window=target_window,
                    point=point,
                    button=button,
                    delivery_mode=delivery_mode,
                )
        else:
            user32.SendMessageW(target_hwnd, WM_MOUSEMOVE, 0, lparam)
            user32.SendMessageW(target_hwnd, down_message, down_wparam, lparam)
            user32.SendMessageW(target_hwnd, up_message, 0, lparam)

        return self._mark_click_success(
            target_window,
            point,
            button=button,
            delivery_mode=delivery_mode,
            message=(
                f"{transport_name} dispatched a {button} click to HWND {target_hwnd} "
                f"at client point ({point.x}, {point.y})."
            ),
        )

    def _send_foreground_click(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        *,
        button: str,
        restore_environment: bool,
    ) -> ClickDeliveryResult:
        parent_hwnd = target_window.hwnd or target_window.effective_hwnd
        target_hwnd = target_window.effective_hwnd
        delivery_mode = "foreground"
        transport_name = self._transport_name(delivery_mode)

        if parent_hwnd is None or target_hwnd is None:
            return self._build_result(
                success=False,
                message="Select a valid target window before using Foreground / SendInput.",
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        previous_cursor = self._capture_cursor_position() if restore_environment else None
        previous_foreground_hwnd = user32.GetForegroundWindow() if restore_environment else None

        if not self._prepare_foreground_target(parent_hwnd):
            self._restore_environment(previous_cursor, previous_foreground_hwnd)
            return self._build_result(
                success=False,
                message=(
                    f"{transport_name} could not bring HWND {parent_hwnd} to the foreground. "
                    "Try clicking the target window once manually and retry."
                ),
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        screen_point = self._client_to_screen(target_hwnd, point)
        if screen_point is None:
            self._restore_environment(previous_cursor, previous_foreground_hwnd)
            return self._build_result(
                success=False,
                message=f"{transport_name} could not convert client point ({point.x}, {point.y}) to screen coordinates.",
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        if not bool(user32.SetCursorPos(screen_point.x, screen_point.y)):
            error_code = ctypes.get_last_error()
            self._restore_environment(previous_cursor, previous_foreground_hwnd)
            LOGGER.warning(
                "%s failed to move the cursor to screen point (%s,%s). Win32 error=%s",
                transport_name,
                screen_point.x,
                screen_point.y,
                error_code,
            )
            return self._build_result(
                success=False,
                message=(
                    f"{transport_name} could not move the real cursor to screen point "
                    f"({screen_point.x}, {screen_point.y}). Win32 last error: {error_code}."
                ),
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        time.sleep(FOREGROUND_CLICK_SETTLE_SECONDS)
        if not self._send_input_button(button):
            error_code = ctypes.get_last_error()
            self._restore_environment(previous_cursor, previous_foreground_hwnd)
            LOGGER.warning(
                "%s failed while sending hardware mouse input to HWND %s. Win32 error=%s",
                transport_name,
                target_hwnd,
                error_code,
            )
            return self._build_result(
                success=False,
                message=f"{transport_name} failed to send hardware mouse input. Win32 last error: {error_code}.",
                target_window=target_window,
                point=point,
                button=button,
                delivery_mode=delivery_mode,
            )

        if restore_environment:
            self._restore_environment(previous_cursor, previous_foreground_hwnd)

        return self._mark_click_success(
            target_window,
            point,
            button=button,
            delivery_mode=delivery_mode,
            message=(
                f"{transport_name} dispatched a {button} click to HWND {target_hwnd} "
                f"at client point ({point.x}, {point.y})."
            ),
        )

    def _prepare_foreground_target(self, parent_hwnd: int) -> bool:
        if not user32.IsWindow(parent_hwnd):
            return False

        if bool(user32.IsIconic(parent_hwnd)):
            user32.ShowWindow(parent_hwnd, SW_RESTORE)
            time.sleep(FOREGROUND_FOCUS_SETTLE_SECONDS)

        user32.BringWindowToTop(parent_hwnd)
        user32.SetForegroundWindow(parent_hwnd)
        time.sleep(FOREGROUND_FOCUS_SETTLE_SECONDS)
        return user32.GetForegroundWindow() == parent_hwnd

    def _client_to_screen(self, target_hwnd: int, point: ClickPoint) -> wintypes.POINT | None:
        screen_point = wintypes.POINT(point.x, point.y)
        if not bool(user32.ClientToScreen(target_hwnd, ctypes.byref(screen_point))):
            return None
        return screen_point

    def _capture_cursor_position(self) -> wintypes.POINT | None:
        cursor_point = wintypes.POINT()
        if not bool(user32.GetCursorPos(ctypes.byref(cursor_point))):
            return None
        return cursor_point

    def _restore_environment(
        self,
        cursor_point: wintypes.POINT | None,
        foreground_hwnd: int | None,
    ) -> None:
        if cursor_point is not None:
            user32.SetCursorPos(cursor_point.x, cursor_point.y)
        if foreground_hwnd and user32.IsWindow(foreground_hwnd):
            user32.BringWindowToTop(foreground_hwnd)
            user32.SetForegroundWindow(foreground_hwnd)

    def _send_input_button(self, button: str) -> bool:
        down_flag, up_flag = self._resolve_sendinput_flags(button)
        inputs = (INPUT * 2)(
            INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=down_flag)),
            INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=up_flag)),
        )
        sent = user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        return sent == len(inputs)

    def _build_result(
        self,
        *,
        success: bool,
        message: str,
        target_window: TargetWindow,
        point: ClickPoint,
        button: str,
        delivery_mode: str,
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
            used_post_message=delivery_mode == "post",
            delivery_mode=delivery_mode,
        )

    def _mark_click_success(
        self,
        target_window: TargetWindow,
        point: ClickPoint,
        *,
        button: str,
        delivery_mode: str,
        message: str,
    ) -> ClickDeliveryResult:
        with self._lock:
            self._status.completed_clicks += 1
            self._status.last_message = message

        LOGGER.debug(message)
        return ClickDeliveryResult(
            success=True,
            message=message,
            parent_hwnd=target_window.hwnd,
            target_hwnd=target_window.effective_hwnd,
            x=point.x,
            y=point.y,
            button=button,
            used_post_message=delivery_mode == "post",
            delivery_mode=delivery_mode,
        )

    def _resolve_button_messages(self, button: str) -> tuple[int, int, int]:
        normalized = button.lower().strip()
        if normalized == "right":
            return WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON
        return WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON

    def _resolve_sendinput_flags(self, button: str) -> tuple[int, int]:
        normalized = button.lower().strip()
        if normalized == "right":
            return MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        return MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    def _pack_point(self, x: int, y: int) -> int:
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    def _next_delay_seconds(self, settings: ClickSettings) -> float:
        if settings.use_random_delay:
            minimum = max(1, settings.random_min_ms)
            maximum = max(1, settings.random_max_ms)
            low, high = sorted((minimum, maximum))
            return random.uniform(low, high) / 1000.0
        return max(1, settings.delay_ms) / 1000.0

    def _normalize_delivery_mode(self, delivery_mode: str) -> str:
        normalized = delivery_mode.lower().strip()
        if normalized in {"send", "post", "foreground"}:
            return normalized
        return "send"

    def _transport_name(self, delivery_mode: str) -> str:
        if delivery_mode == "post":
            return "PostMessage"
        if delivery_mode == "foreground":
            return "Foreground / SendInput"
        return "SendMessage"
