from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit


class HotkeyLineEdit(QLineEdit):
    """Captures a hotkey chord directly from keyboard input."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Press a hotkey...")
        self.setClearButtonEnabled(True)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab} and modifiers == Qt.KeyboardModifier.NoModifier:
            super().keyPressEvent(event)
            return

        if key in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete} and modifiers == Qt.KeyboardModifier.NoModifier:
            self.clear()
            event.accept()
            return

        hotkey_text = self._format_hotkey(key, modifiers)
        if hotkey_text is None:
            event.accept()
            return

        self.setText(hotkey_text)
        self.editingFinished.emit()
        event.accept()

    def _format_hotkey(self, key: int, modifiers: Qt.KeyboardModifier) -> str | None:
        if key in {
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        }:
            return None

        main_key = self._key_to_string(key)
        if main_key is None:
            return None

        parts: list[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")
        parts.append(main_key)
        return "+".join(parts)

    def _key_to_string(self, key: int) -> str | None:
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            return f"F{key - Qt.Key.Key_F1 + 1}"

        aliases = {
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Escape: "Esc",
            Qt.Key.Key_Backspace: "Backspace",
            Qt.Key.Key_Insert: "Insert",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Home: "Home",
            Qt.Key.Key_End: "End",
            Qt.Key.Key_PageUp: "PageUp",
            Qt.Key.Key_PageDown: "PageDown",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
        }
        return aliases.get(key)
