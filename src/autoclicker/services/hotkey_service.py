from __future__ import annotations

import ctypes
import threading
from dataclasses import dataclass
from ctypes import wintypes
from typing import Callable

from autoclicker.domain.models import HotkeySettings

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ALREADY_REGISTERED = 1409

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


@dataclass(slots=True)
class HotkeyRegistrationResult:
    success: bool
    message: str
    normalized_start_stop: str | None = None
    normalized_capture_point: str | None = None


@dataclass(slots=True)
class _PreparedHotkey:
    hotkey_id: int
    action_name: str
    display: str
    modifiers: int
    virtual_key: int
    callback: Callable[[], None]


class HotkeyService:
    """Registers configurable global hotkeys with a native Win32 message loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registered = False
        self._listener_thread: threading.Thread | None = None
        self._listener_thread_id: int | None = None
        self._last_message = "Global hotkeys are not registered."

    @property
    def is_registered(self) -> bool:
        with self._lock:
            return self._registered

    @property
    def last_message(self) -> str:
        with self._lock:
            return self._last_message

    def register(
        self,
        hotkeys: HotkeySettings,
        *,
        on_start_stop: Callable[[], None],
        on_capture_point: Callable[[], None],
    ) -> HotkeyRegistrationResult:
        prepared_start_stop = self._parse_hotkey(
            hotkeys.start_stop,
            hotkey_id=1,
            action_name="Start / Stop",
            callback=on_start_stop,
        )
        if isinstance(prepared_start_stop, HotkeyRegistrationResult):
            return prepared_start_stop

        prepared_capture = self._parse_hotkey(
            hotkeys.capture_point,
            hotkey_id=2,
            action_name="Get Position",
            callback=on_capture_point,
        )
        if isinstance(prepared_capture, HotkeyRegistrationResult):
            return prepared_capture

        if (
            prepared_start_stop.modifiers == prepared_capture.modifiers
            and prepared_start_stop.virtual_key == prepared_capture.virtual_key
        ):
            return HotkeyRegistrationResult(
                success=False,
                message="Start / Stop and Get Position cannot use the same hotkey.",
            )

        self.unregister()

        ready_event = threading.Event()
        startup_state: dict[str, object] = {}
        thread = threading.Thread(
            target=self._listener_main,
            args=([prepared_start_stop, prepared_capture], ready_event, startup_state),
            daemon=True,
            name="global-hotkey-listener",
        )
        thread.start()

        if not ready_event.wait(timeout=2.0):
            self.unregister()
            result = HotkeyRegistrationResult(
                success=False,
                message="Timed out while starting the global hotkey listener thread.",
            )
            with self._lock:
                self._last_message = result.message
            return result

        if not bool(startup_state.get("success")):
            result = HotkeyRegistrationResult(
                success=False,
                message=str(startup_state.get("message", "Failed to register global hotkeys.")),
                normalized_start_stop=prepared_start_stop.display,
                normalized_capture_point=prepared_capture.display,
            )
            with self._lock:
                self._registered = False
                self._listener_thread = None
                self._listener_thread_id = None
                self._last_message = result.message
            return result

        with self._lock:
            self._registered = True
            self._listener_thread = thread
            self._last_message = str(startup_state.get("message", "Global hotkeys registered."))

        return HotkeyRegistrationResult(
            success=True,
            message=self._last_message,
            normalized_start_stop=prepared_start_stop.display,
            normalized_capture_point=prepared_capture.display,
        )

    def unregister(self) -> None:
        thread_to_join: threading.Thread | None = None
        thread_id: int | None = None

        with self._lock:
            thread_to_join = self._listener_thread
            thread_id = self._listener_thread_id
            self._registered = False
            self._listener_thread = None
            self._listener_thread_id = None

        if thread_id is not None:
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)

        if thread_to_join is not None and thread_to_join.is_alive():
            thread_to_join.join(timeout=1.0)

        with self._lock:
            self._last_message = "Global hotkeys are not registered."

    def _listener_main(
        self,
        prepared_hotkeys: list[_PreparedHotkey],
        ready_event: threading.Event,
        startup_state: dict[str, object],
    ) -> None:
        thread_id = int(kernel32.GetCurrentThreadId())
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        with self._lock:
            self._listener_thread_id = thread_id

        registered_ids: list[int] = []
        try:
            for prepared in prepared_hotkeys:
                success = user32.RegisterHotKey(
                    None,
                    prepared.hotkey_id,
                    prepared.modifiers | MOD_NOREPEAT,
                    prepared.virtual_key,
                )
                if not success:
                    error_code = ctypes.get_last_error()
                    for hotkey_id in registered_ids:
                        user32.UnregisterHotKey(None, hotkey_id)

                    startup_state["success"] = False
                    startup_state["message"] = self._format_registration_error(prepared, error_code)
                    ready_event.set()
                    return

                registered_ids.append(prepared.hotkey_id)

            startup_state["success"] = True
            startup_state["message"] = (
                f"Global hotkeys active: Start / Stop = {prepared_hotkeys[0].display}, "
                f"Get Position = {prepared_hotkeys[1].display}."
            )
            ready_event.set()

            callbacks = {prepared.hotkey_id: prepared.callback for prepared in prepared_hotkeys}
            while True:
                message_result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if message_result == 0:
                    break
                if message_result == -1:
                    break

                if msg.message == WM_HOTKEY:
                    callback = callbacks.get(int(msg.wParam))
                    if callback is not None:
                        callback()
        finally:
            for hotkey_id in registered_ids:
                user32.UnregisterHotKey(None, hotkey_id)

            with self._lock:
                self._registered = False
                self._listener_thread_id = None

    def _parse_hotkey(
        self,
        text: str,
        *,
        hotkey_id: int,
        action_name: str,
        callback: Callable[[], None],
    ) -> _PreparedHotkey | HotkeyRegistrationResult:
        raw_tokens = [token.strip() for token in text.replace("-", "+").split("+") if token.strip()]
        if not raw_tokens:
            return HotkeyRegistrationResult(
                success=False,
                message=f"{action_name} hotkey cannot be empty.",
            )

        modifiers = 0
        key_display: str | None = None
        virtual_key: int | None = None
        modifier_labels: list[str] = []

        for token in raw_tokens:
            upper = token.upper()
            if upper in {"CTRL", "CONTROL"}:
                modifiers |= MOD_CONTROL
                if "Ctrl" not in modifier_labels:
                    modifier_labels.append("Ctrl")
                continue
            if upper == "ALT":
                modifiers |= MOD_ALT
                if "Alt" not in modifier_labels:
                    modifier_labels.append("Alt")
                continue
            if upper == "SHIFT":
                modifiers |= MOD_SHIFT
                if "Shift" not in modifier_labels:
                    modifier_labels.append("Shift")
                continue
            if upper in {"WIN", "WINDOWS", "META"}:
                modifiers |= MOD_WIN
                if "Win" not in modifier_labels:
                    modifier_labels.append("Win")
                continue

            if key_display is not None:
                return HotkeyRegistrationResult(
                    success=False,
                    message=f"{action_name} hotkey must contain exactly one main key.",
                )

            key_info = self._parse_primary_key(token)
            if key_info is None:
                return HotkeyRegistrationResult(
                    success=False,
                    message=f"{action_name} hotkey uses an unsupported key: {token}.",
                )

            key_display, virtual_key = key_info

        if key_display is None or virtual_key is None:
            return HotkeyRegistrationResult(
                success=False,
                message=f"{action_name} hotkey must include a non-modifier key.",
            )

        ordered_modifiers = [
            label for label, flag in (("Ctrl", MOD_CONTROL), ("Alt", MOD_ALT), ("Shift", MOD_SHIFT), ("Win", MOD_WIN))
            if modifiers & flag
        ]
        display = "+".join(ordered_modifiers + [key_display])

        return _PreparedHotkey(
            hotkey_id=hotkey_id,
            action_name=action_name,
            display=display,
            modifiers=modifiers,
            virtual_key=virtual_key,
            callback=callback,
        )

    def _parse_primary_key(self, token: str) -> tuple[str, int] | None:
        upper = token.strip().upper()
        aliases: dict[str, tuple[str, int]] = {
            "SPACE": ("Space", 0x20),
            "TAB": ("Tab", 0x09),
            "ENTER": ("Enter", 0x0D),
            "RETURN": ("Enter", 0x0D),
            "ESC": ("Esc", 0x1B),
            "ESCAPE": ("Esc", 0x1B),
            "BACKSPACE": ("Backspace", 0x08),
            "INSERT": ("Insert", 0x2D),
            "DELETE": ("Delete", 0x2E),
            "HOME": ("Home", 0x24),
            "END": ("End", 0x23),
            "PAGEUP": ("PageUp", 0x21),
            "PAGEDOWN": ("PageDown", 0x22),
            "LEFT": ("Left", 0x25),
            "UP": ("Up", 0x26),
            "RIGHT": ("Right", 0x27),
            "DOWN": ("Down", 0x28),
        }
        if upper in aliases:
            return aliases[upper]

        if len(upper) == 1 and "A" <= upper <= "Z":
            return upper, ord(upper)
        if len(upper) == 1 and "0" <= upper <= "9":
            return upper, ord(upper)
        if upper.startswith("F") and upper[1:].isdigit():
            index = int(upper[1:])
            if 1 <= index <= 24:
                return f"F{index}", 0x70 + index - 1
        return None

    def _format_registration_error(self, prepared: _PreparedHotkey, error_code: int) -> str:
        if error_code == HOTKEY_ALREADY_REGISTERED:
            return (
                f"Could not register {prepared.action_name} hotkey {prepared.display}. "
                "Another app is already using it."
            )
        return (
            f"Could not register {prepared.action_name} hotkey {prepared.display}. "
            f"Win32 error: {error_code}."
        )
