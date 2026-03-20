from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from autoclicker.services.click_engine import ClickEngine
from autoclicker.services.config_store import ConfigStore
from autoclicker.services.hotkey_service import HotkeyService
from autoclicker.services.window_service import WindowService
from autoclicker.ui.main_window import MainWindow
from autoclicker.ui.theme import apply_app_theme


APP_NAME = "Advanced Background Auto-Clicker"


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_config_path() -> Path:
    return runtime_root() / "config.json"


def _write_crash_report(
    runtime_directory: Path,
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> Path | None:
    logs_directory = runtime_directory / "logs"
    try:
        logs_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        report_path = logs_directory / f"crash-{timestamp}.log"
        report = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        report_path.write_text(report, encoding="utf-8")
        return report_path
    except OSError:
        return None


def install_exception_hook(runtime_directory: Path) -> None:
    def _handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        report_path = _write_crash_report(runtime_directory, exc_type, exc_value, exc_traceback)
        if report_path is not None:
            message = (
                f"An unexpected error occurred. A crash report was written to:\n{report_path}"
            )
        else:
            message = "An unexpected error occurred and the crash report could not be written."

        try:
            QMessageBox.critical(None, APP_NAME, message)
        except Exception:
            pass

        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception


def build_main_window(*, config_path: Path | None = None) -> MainWindow:
    config_store = ConfigStore(config_path or default_config_path())
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
    runtime_directory = runtime_root()
    install_exception_hook(runtime_directory)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Codex")
    app.setStyle("Fusion")
    apply_app_theme(app)

    window = build_main_window(config_path=runtime_directory / "config.json")
    window.show()
    return app.exec()


def main() -> int:
    return run()
