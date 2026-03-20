from __future__ import annotations

import ctypes
from ctypes import wintypes

from autoclicker.domain.models import TargetWindow

user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
PREFERRED_RENDER_CLASSES = ("Chrome_RenderWidgetHostHWND",)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetShellWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL


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
