from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from autoclicker.services.click_engine import ClickEngine
from autoclicker.services.config_store import ConfigStore
from autoclicker.services.hotkey_service import HotkeyService
from autoclicker.services.window_service import WindowService
from autoclicker.ui.main_window import MainWindow
from autoclicker.ui.theme import apply_app_theme


def build_main_window() -> MainWindow:
    config_store = ConfigStore()
    window_service = WindowService()
    click_engine = ClickEngine()
    hotkey_service = HotkeyService()
    return MainWindow(
        config_store=config_store,
        window_service=window_service,
        click_engine=click_engine,
        hotkey_service=hotkey_service,
    )


def run() -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("Advanced Background Auto-Clicker")
    app.setOrganizationName("Codex")
    app.setStyle("Fusion")
    apply_app_theme(app)

    window = build_main_window()
    window.show()
    return app.exec()


def main() -> int:
    return run()

