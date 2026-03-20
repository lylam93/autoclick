from __future__ import annotations

import ctypes
from ctypes import wintypes

from autoclicker.domain.models import PointCaptureResult, TargetWindow
from autoclicker.services.app_logging import get_logger

user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
PREFERRED_RENDER_CLASSES = ("Chrome_RenderWidgetHostHWND",)
GA_ROOT = 2
GW_HWNDNEXT = 2

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
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.GetTopWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
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
user32.RealChildWindowFromPoint.argtypes = [wintypes.HWND, wintypes.POINT]
user32.RealChildWindowFromPoint.restype = wintypes.HWND
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND

LOGGER = get_logger("services.window_service")


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
        LOGGER.debug("Enumerated %s visible titled top-level windows.", len(windows))
        return sorted(windows, key=lambda window: (window.title.lower(), window.hwnd or 0))

    def list_child_windows(self, parent_hwnd: int) -> list[TargetWindow]:
        if not parent_hwnd or not user32.IsWindow(parent_hwnd):
            LOGGER.debug("Cannot enumerate child windows for invalid parent HWND %s", parent_hwnd)
            return []

        windows: list[TargetWindow] = []

        @EnumWindowsProc
        def callback(hwnd: int, _lparam: int) -> bool:
            window = self._inspect_window(hwnd)
            if window is not None:
                windows.append(window)
            return True

        user32.EnumChildWindows(parent_hwnd, callback, 0)
        LOGGER.debug("Enumerated %s child windows for parent HWND %s.", len(windows), parent_hwnd)
        return windows

    def get_window(self, hwnd: int | None) -> TargetWindow | None:
        if hwnd is None or hwnd <= 0 or not user32.IsWindow(hwnd):
            return None

        return self._inspect_window(hwnd)

    def resolve_click_target(self, target_window: TargetWindow | None) -> TargetWindow | None:
        if target_window is None or target_window.hwnd is None:
            LOGGER.debug("resolve_click_target called without a valid target window.")
            return None

        top_level_window = self.get_window(target_window.hwnd)
        if top_level_window is None:
            LOGGER.debug("Top-level HWND %s is no longer valid.", target_window.hwnd)
            return None

        if target_window.child_hwnd and user32.IsWindow(target_window.child_hwnd):
            child_window = self.get_window(target_window.child_hwnd)
            if child_window is not None:
                LOGGER.debug(
                    "Using previously saved child HWND %s for parent HWND %s.",
                    target_window.child_hwnd,
                    target_window.hwnd,
                )
                return self._merge_target_window(top_level_window, child_window)

        if top_level_window.class_name in PREFERRED_RENDER_CLASSES:
            LOGGER.debug("Top-level window %s already matches a preferred render class.", top_level_window.hwnd)
            return top_level_window

        for child_window in self.list_child_windows(top_level_window.hwnd or 0):
            if child_window.class_name in PREFERRED_RENDER_CLASSES:
                LOGGER.info(
                    "Resolved child render HWND %s (%s) for parent HWND %s.",
                    child_window.hwnd,
                    child_window.class_name,
                    top_level_window.hwnd,
                )
                return self._merge_target_window(top_level_window, child_window)

        LOGGER.debug("Falling back to top-level HWND %s for click delivery.", top_level_window.hwnd)
        return top_level_window

    def rehydrate_target(self, target_window: TargetWindow | None) -> TargetWindow | None:
        if target_window is None:
            return None

        resolved_target = self.resolve_click_target(target_window)
        if resolved_target is not None:
            return resolved_target

        LOGGER.info(
            "Attempting to rehydrate stale target HWND %s using saved metadata title=%r class=%r pid=%r.",
            target_window.hwnd,
            target_window.title,
            target_window.class_name,
            target_window.process_id,
        )
        matched_window = self.find_saved_window_match(target_window)
        if matched_window is None:
            LOGGER.warning(
                "Could not find a unique live window matching the saved target title=%r class=%r pid=%r.",
                target_window.title,
                target_window.class_name,
                target_window.process_id,
            )
            return None

        LOGGER.info("Rehydrated saved target to live HWND %s.", matched_window.hwnd)
        return self.resolve_click_target(matched_window) or matched_window

    def with_effective_hwnd(self, target_window: TargetWindow | None, effective_hwnd: int | None) -> TargetWindow | None:
        if target_window is None or target_window.hwnd is None:
            return None

        top_level_window = self.get_window(target_window.hwnd) or target_window
        if effective_hwnd is None or effective_hwnd == top_level_window.hwnd:
            return top_level_window
        if not user32.IsWindow(effective_hwnd):
            LOGGER.debug("Cannot adopt invalid effective HWND %s for parent HWND %s.", effective_hwnd, top_level_window.hwnd)
            return top_level_window
        if not user32.IsChild(top_level_window.hwnd or 0, effective_hwnd):
            LOGGER.debug(
                "Rejected effective HWND %s because it is not a child of parent HWND %s.",
                effective_hwnd,
                top_level_window.hwnd,
            )
            return top_level_window

        child_window = self.get_window(effective_hwnd)
        if child_window is None:
            return top_level_window

        LOGGER.info(
            "Resolved effective click target to child HWND %s (%s) under parent HWND %s.",
            child_window.hwnd,
            child_window.class_name or "UnknownClass",
            top_level_window.hwnd,
        )
        return self._merge_target_window(top_level_window, child_window)

    def find_saved_window_match(
        self,
        target_window: TargetWindow | None,
        candidates: list[TargetWindow] | None = None,
    ) -> TargetWindow | None:
        if target_window is None:
            return None

        windows = candidates if candidates is not None else self.list_windows()
        best_window: TargetWindow | None = None
        best_score = 0
        best_count = 0

        for candidate in windows:
            score = self._score_saved_window_match(target_window, candidate)
            if score <= 0:
                continue
            LOGGER.debug(
                "Candidate HWND %s scored %s for saved target title=%r class=%r pid=%r.",
                candidate.hwnd,
                score,
                target_window.title,
                target_window.class_name,
                target_window.process_id,
            )
            if score > best_score:
                best_window = candidate
                best_score = score
                best_count = 1
            elif score == best_score:
                best_count += 1

        if best_score <= 0 or best_count != 1:
            return None
        return best_window

    def pick_window_from_cursor(self) -> TargetWindow | None:
        screen_point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(screen_point)):
            LOGGER.warning("GetCursorPos failed while picking a window from the cursor.")
            return None

        hovered_hwnd = user32.WindowFromPoint(screen_point)
        if not hovered_hwnd:
            LOGGER.warning("WindowFromPoint did not return a window under cursor (%s,%s).", screen_point.x, screen_point.y)
            return None

        root_hwnd = user32.GetAncestor(hovered_hwnd, GA_ROOT) or hovered_hwnd
        top_level_window = self._pick_top_level_window_from_point(screen_point, root_hwnd)
        if top_level_window is None:
            LOGGER.warning("Could not inspect root HWND %s from cursor picker.", root_hwnd)
            return None

        hovered_window = self.get_window(hovered_hwnd)
        if hovered_window is not None and hovered_window.hwnd != top_level_window.hwnd:
            if hovered_window.class_name in PREFERRED_RENDER_CLASSES:
                LOGGER.info(
                    "Cursor picker selected child render HWND %s for parent HWND %s.",
                    hovered_window.hwnd,
                    top_level_window.hwnd,
                )
                return self._merge_target_window(top_level_window, hovered_window)

        LOGGER.info("Cursor picker selected top-level HWND %s.", top_level_window.hwnd)
        return self.resolve_click_target(top_level_window) or top_level_window

    def capture_cursor_point(self, target_window: TargetWindow | None) -> PointCaptureResult:
        if target_window is None or target_window.hwnd is None:
            message = "Select a valid target window before capturing a point."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
            )

        resolved_target = self.resolve_click_target(target_window)
        if resolved_target is None or resolved_target.effective_hwnd is None:
            message = "The selected target window is no longer valid."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                target_hwnd=target_window.effective_hwnd,
            )

        parent_hwnd = resolved_target.hwnd or resolved_target.effective_hwnd
        effective_hwnd = resolved_target.effective_hwnd
        if not user32.IsWindow(effective_hwnd):
            message = f"Target HWND {effective_hwnd} is no longer valid."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                target_hwnd=effective_hwnd,
            )

        screen_point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(screen_point)):
            message = "Windows did not return the current cursor position."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                target_hwnd=effective_hwnd,
            )

        hovered_hwnd = user32.WindowFromPoint(screen_point)
        if parent_hwnd and not self._contains_screen_point(parent_hwnd, screen_point):
            message = (
                "Move the cursor over the selected target window before capturing the point. "
                f"Current screen position is ({screen_point.x}, {screen_point.y})."
            )
            LOGGER.info(message)
            return PointCaptureResult(
                success=False,
                message=message,
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                target_hwnd=effective_hwnd,
            )

        if hovered_hwnd and not self._belongs_to_target_family(hovered_hwnd, resolved_target):
            hovered_root_hwnd = user32.GetAncestor(hovered_hwnd, GA_ROOT) or hovered_hwnd
            LOGGER.info(
                "WindowFromPoint returned HWND %s (root HWND %s) while capturing for parent HWND %s. "
                "Continuing because the screen point is inside the selected window bounds.",
                hovered_hwnd,
                hovered_root_hwnd,
                parent_hwnd,
            )

        point_target = self.resolve_click_target_for_point(resolved_target, screen_point) or resolved_target
        effective_hwnd = point_target.effective_hwnd
        if effective_hwnd is None or not user32.IsWindow(effective_hwnd):
            message = "The selected click target could not be resolved for the captured point."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                target_hwnd=resolved_target.effective_hwnd,
            )

        client_point = wintypes.POINT(screen_point.x, screen_point.y)
        if not user32.ScreenToClient(effective_hwnd, ctypes.byref(client_point)):
            message = f"ScreenToClient failed for HWND {effective_hwnd}."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                target_hwnd=effective_hwnd,
            )

        client_rect = wintypes.RECT()
        if not user32.GetClientRect(effective_hwnd, ctypes.byref(client_rect)):
            message = f"GetClientRect failed for HWND {effective_hwnd}."
            LOGGER.warning(message)
            return PointCaptureResult(
                success=False,
                message=message,
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                client_x=client_point.x,
                client_y=client_point.y,
                target_hwnd=effective_hwnd,
            )

        if not (0 <= client_point.x < client_rect.right and 0 <= client_point.y < client_rect.bottom):
            message = (
                f"Captured point ({client_point.x}, {client_point.y}) is outside the client area "
                f"of HWND {effective_hwnd}."
            )
            LOGGER.info(message)
            return PointCaptureResult(
                success=False,
                message=message,
                screen_x=screen_point.x,
                screen_y=screen_point.y,
                client_x=client_point.x,
                client_y=client_point.y,
                target_hwnd=effective_hwnd,
            )

        message = (
            f"Captured client point ({client_point.x}, {client_point.y}) from screen "
            f"({screen_point.x}, {screen_point.y}) for HWND {effective_hwnd}."
        )
        if point_target.hwnd and effective_hwnd != point_target.hwnd:
            message += f" Parent HWND is {point_target.hwnd}."
        LOGGER.info(message)
        return PointCaptureResult(
            success=True,
            message=message,
            screen_x=screen_point.x,
            screen_y=screen_point.y,
            client_x=client_point.x,
            client_y=client_point.y,
            target_hwnd=effective_hwnd,
        )

    def resolve_click_target_for_point(
        self,
        target_window: TargetWindow | None,
        screen_point: wintypes.POINT,
    ) -> TargetWindow | None:
        resolved_target = self.resolve_click_target(target_window)
        if resolved_target is None or resolved_target.hwnd is None:
            return None

        point_hwnd = self._find_deepest_child_at_screen_point(resolved_target.hwnd, screen_point)
        if point_hwnd and point_hwnd != resolved_target.hwnd:
            point_target = self.with_effective_hwnd(resolved_target, point_hwnd)
            if point_target is not None:
                return point_target
        return resolved_target

    def _score_saved_window_match(self, target_window: TargetWindow, candidate: TargetWindow) -> int:
        if candidate.hwnd is None:
            return 0

        score = 0
        saved_title = target_window.title.strip().casefold()
        candidate_title = candidate.title.strip().casefold()
        if saved_title:
            if candidate_title == saved_title:
                score += 8
            elif saved_title in candidate_title or candidate_title in saved_title:
                score += 4

        saved_class = target_window.class_name.strip().casefold()
        candidate_class = candidate.class_name.strip().casefold()
        if saved_class and candidate_class == saved_class:
            score += 3

        if target_window.process_id is not None and candidate.process_id == target_window.process_id:
            score += 2

        return score

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

    def _pick_top_level_window_from_point(
        self,
        screen_point: wintypes.POINT,
        hovered_root_hwnd: int,
    ) -> TargetWindow | None:
        hovered_root = self.get_window(hovered_root_hwnd)
        if hovered_root is not None and hovered_root.title:
            return hovered_root

        for hwnd in self._iter_top_level_windows_in_z_order():
            if hwnd == hovered_root_hwnd:
                continue

            candidate = self.get_window(hwnd)
            if candidate is None or not candidate.title:
                continue
            if not self._contains_screen_point(hwnd, screen_point):
                continue

            LOGGER.info(
                "Cursor picker skipped top-level HWND %s (%s) with no title and selected titled HWND %s (%r) underneath.",
                hovered_root_hwnd,
                hovered_root.class_name if hovered_root is not None else "UnknownClass",
                candidate.hwnd,
                candidate.title,
            )
            return candidate

        return hovered_root

    def _iter_top_level_windows_in_z_order(self):
        shell_window = user32.GetShellWindow()
        hwnd = user32.GetTopWindow(0)
        seen: set[int] = set()

        while hwnd and hwnd not in seen:
            seen.add(hwnd)
            if hwnd != shell_window and user32.IsWindowVisible(hwnd):
                yield hwnd
            hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)

    def _find_deepest_child_at_screen_point(self, parent_hwnd: int, screen_point: wintypes.POINT) -> int | None:
        if not parent_hwnd or not user32.IsWindow(parent_hwnd):
            return None

        current_hwnd = parent_hwnd
        visited = {parent_hwnd}
        while True:
            client_point = wintypes.POINT(screen_point.x, screen_point.y)
            if not user32.ScreenToClient(current_hwnd, ctypes.byref(client_point)):
                break

            child_hwnd = user32.RealChildWindowFromPoint(current_hwnd, client_point)
            if not child_hwnd or child_hwnd == current_hwnd or child_hwnd in visited or not user32.IsWindow(child_hwnd):
                break

            visited.add(child_hwnd)
            current_hwnd = child_hwnd

        if current_hwnd != parent_hwnd:
            LOGGER.info(
                "Point-based child resolution selected HWND %s under parent HWND %s.",
                current_hwnd,
                parent_hwnd,
            )
        return current_hwnd

    def _contains_screen_point(self, hwnd: int, screen_point: wintypes.POINT) -> bool:
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        return rect.left <= screen_point.x < rect.right and rect.top <= screen_point.y < rect.bottom

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
