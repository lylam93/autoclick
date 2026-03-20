from __future__ import annotations

import ctypes
from ctypes import wintypes

from autoclicker.domain.models import ClickDeliveryResult, ClickPoint, RuntimeStatus, TargetWindow

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
    """Owns runtime state and Win32 message-based click delivery."""

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

        self._status.completed_clicks += 1
        self._status.last_message = (
            f"{transport_name} dispatched a {button} click to HWND {target_hwnd} "
            f"at client point ({point.x}, {point.y})."
        )
        return self._build_result(
            success=True,
            message=self._status.last_message,
            target_window=target_window,
            point=point,
            button=button,
            used_post_message=use_post_message,
        )

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
