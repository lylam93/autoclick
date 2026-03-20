from __future__ import annotations

import ctypes
from ctypes import wintypes

from autoclicker.domain.models import PointCaptureResult, TargetWindow

user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
PREFERRED_RENDER_CLASSES = ("Chrome_RenderWidgetHostHWND",)
GA_ROOT = 2

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetShellWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
user32.IsChild.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND


class WindowService:
    """Discovers top-level and child windows for Win32 targeting."""

    def list_windows(self) -> list[TargetWindow]:
        shell_window = user32.GetShellWindow()
        windows: list[TargetWindow] = []

        @EnumWindowsProc
        def callback(hwnd: int, _lparam: int) -> bool:
            if hwnd == shell_window:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True

            window = self._inspect_window(hwnd)
            if window is None or not window.title:
                return True

            windows.append(window)
            return True

        user32.EnumWindows(callback, 0)
        return sorted(windows, key=lambda window: (window.title.lower(), window.hwnd or 0))

    def list_child_windows(self, parent_hwnd: int) -> list[TargetWindow]:
        if not parent_hwnd or not user32.IsWindow(parent_hwnd):
            return []

        windows: list[TargetWindow] = []

        @EnumWindowsProc
        def callback(hwnd: int, _lparam: int) -> bool:
            window = self._inspect_window(hwnd)
            if window is not None:
                windows.append(window)
            return True

        user32.EnumChildWindows(parent_hwnd, callback, 0)
        return windows

    def get_window(self, hwnd: int | None) -> TargetWindow | None:
        if hwnd is None or hwnd <= 0 or not user32.IsWindow(hwnd):
            return None

        return self._inspect_window(hwnd)

    def resolve_click_target(self, target_window: TargetWindow | None) -> TargetWindow | None:
        if target_window is None or target_window.hwnd is None:
            return None

        top_level_window = self.get_window(target_window.hwnd)
        if top_level_window is None:
            return None

        if target_window.child_hwnd and user32.IsWindow(target_window.child_hwnd):
            child_window = self.get_window(target_window.child_hwnd)
            if child_window is not None:
                return self._merge_target_window(top_level_window, child_window)

        if top_level_window.class_name in PREFERRED_RENDER_CLASSES:
            return top_level_window

        for child_window in self.list_child_windows(top_level_window.hwnd or 0):
            if child_window.class_name in PREFERRED_RENDER_CLASSES:
                return self._merge_target_window(top_level_window, child_window)

        return top_level_window

    def pick_window_from_cursor(self) -> TargetWindow | None:
        screen_point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(screen_point)):
            return None

        hovered_hwnd = user32.WindowFromPoint(screen_point)
        if not hovered_hwnd:
            return None

        root_hwnd = user32.GetAncestor(hovered_hwnd, GA_ROOT) or hovered_hwnd
        top_level_window = self.get_window(root_hwnd)
        if top_level_window is None:
            return None

        hovered_window = self.get_window(hovered_hwnd)
        if hovered_window is not None and hovered_window.hwnd != top_level_window.hwnd:
            if hovered_window.class_name in PREFERRED_RENDER_CLASSES:
                return self._merge_target_window(top_level_window, hovered_window)

        return self.resolve_click_target(top_level_window) or top_level_window

    def capture_cursor_point(self, target_window: TargetWindow | None) -> PointCaptureResult:
        if target_window is None or target_window.hwnd is None:
            return PointCaptureResult(
                success=False,
                message="Select a valid target window before capturing a point.",
            )

        resolved_target = self.resolve_click_target(target_window)
        if resolved_target is None or resolved_target.effective_hwnd is None:
            return PointCaptureResult(
                success=False,
                message="The selected target window is no longer valid.",
                target_hwnd=target_window.effective_hwnd,
            )

        effective_hwnd = resolved_target.effective_hwnd
        if not user32.IsWindow(effective_hwnd):
            return PointCaptureResult(
                success=False,
                message=f"Target HWND {effective_hwnd} is no longer valid.",
                target_hwnd=effective_hwnd,
            )

        screen_point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(screen_point)):
            return PointCaptureResult(
                success=False,
                message="Windows did not return the current cursor position.",
                target_hwnd=effective_hwnd,
            )

        hovered_hwnd = user32.WindowFromPoint(screen_point)
        if hovered_hwnd and not self._belongs_to_target_family(hovered_hwnd, resolved_target):
            return PointCaptureResult(
                success=False,
                message=(
                    "Move the cursor over the selected target window before capturing the point. "
                    f"Current screen position is ({screen_point.x}, {screen_point.y})."
                ),
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                target_hwnd=effective_hwnd,
            )

        client_point = wintypes.POINT(screen_point.x, screen_point.y)
        if not user32.ScreenToClient(effective_hwnd, ctypes.byref(client_point)):
            return PointCaptureResult(
                success=False,
                message=f"ScreenToClient failed for HWND {effective_hwnd}.",
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                target_hwnd=effective_hwnd,
            )

        client_rect = wintypes.RECT()
        if not user32.GetClientRect(effective_hwnd, ctypes.byref(client_rect)):
            return PointCaptureResult(
                success=False,
                message=f"GetClientRect failed for HWND {effective_hwnd}.",
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                client_x=client_point.x,
                client_y=client_point.y,
                target_hwnd=effective_hwnd,
            )

        if not (0 <= client_point.x < client_rect.right and 0 <= client_point.y < client_rect.bottom):
            return PointCaptureResult(
                success=False,
                message=(
                    f"Captured point ({client_point.x}, {client_point.y}) is outside the client area "
                    f"of HWND {effective_hwnd}."
                ),
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                client_x=client_point.x,
                client_y=client_point.y,
                target_hwnd=effective_hwnd,
            )

        return PointCaptureResult(
            success=True,
            message=(
                f"Captured client point ({client_point.x}, {client_point.y}) from screen "
                f"({screen_point.x}, {screen_point.y}) for HWND {effective_hwnd}."
            ),
            screen_x=screen_point.x,
            screen_y=screen_point.y,
            client_x=client_point.x,
            client_y=client_point.y,
            target_hwnd=effective_hwnd,
        )

    def _belongs_to_target_family(self, hovered_hwnd: int, target_window: TargetWindow) -> bool:
        parent_hwnd = target_window.hwnd or 0
        effective_hwnd = target_window.effective_hwnd or 0

        if hovered_hwnd in {parent_hwnd, effective_hwnd}:
            return True
        if effective_hwnd and user32.IsChild(effective_hwnd, hovered_hwnd):
            return True
        if parent_hwnd and user32.IsChild(parent_hwnd, hovered_hwnd):
            return True
        return False

    def _merge_target_window(self, parent_window: TargetWindow, child_window: TargetWindow) -> TargetWindow:
        return TargetWindow(
            hwnd=parent_window.hwnd,
            title=parent_window.title,
            class_name=child_window.class_name or parent_window.class_name,
            process_id=parent_window.process_id,
            child_hwnd=child_window.hwnd,
        )

    def _inspect_window(self, hwnd: int) -> TargetWindow | None:
        if not user32.IsWindow(hwnd):
            return None

        title = self._get_window_text(hwnd).strip()
        class_name = self._get_class_name(hwnd).strip()
        process_id = self._get_process_id(hwnd)

        return TargetWindow(
            hwnd=int(hwnd),
            title=title,
            class_name=class_name,
            process_id=process_id,
        )

    def _get_window_text(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    def _get_class_name(self, hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        length = user32.GetClassNameW(hwnd, buffer, len(buffer))
        if length <= 0:
            return ""
        return buffer.value

    def _get_process_id(self, hwnd: int) -> int | None:
        process_id = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value) if process_id.value else None
