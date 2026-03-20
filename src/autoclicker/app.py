from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from autoclicker.services.app_logging import LoggingSession, configure_logging, get_logger
from autoclicker.services.click_engine import ClickEngine
from autoclicker.services.config_store import ConfigStore
from autoclicker.services.hotkey_service import HotkeyService
from autoclicker.services.window_service import WindowService
from autoclicker.ui.main_window import MainWindow
from autoclicker.ui.theme import apply_app_theme


APP_NAME = "Advanced Background Auto-Clicker"
LOGGER = get_logger("app")


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


def install_exception_hook(runtime_directory: Path, logging_session: LoggingSession) -> None:
    def _handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        LOGGER.exception("Unhandled exception reached sys.excepthook.", exc_info=(exc_type, exc_value, exc_traceback))
        report_path = _write_crash_report(runtime_directory, exc_type, exc_value, exc_traceback)
        if report_path is not None:
            LOGGER.error("Crash report written to %s", report_path)
            message = (
                "An unexpected error occurred.\n\n"
                f"Diagnostic log: {logging_session.latest_log_path}\n"
                f"Crash report: {report_path}"
            )
        else:
            message = (
                "An unexpected error occurred and the crash report could not be written.\n\n"
                f"Diagnostic log: {logging_session.latest_log_path}"
            )

        try:
            QMessageBox.critical(None, APP_NAME, message)
        except Exception:
            pass

        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception


def build_main_window(
    *,
    config_path: Path | None = None,
    diagnostic_log_path: Path | None = None,
) -> MainWindow:
    resolved_config_path = config_path or default_config_path()
    LOGGER.info("Building main window with config path %s", resolved_config_path)
    config_store = ConfigStore(resolved_config_path)
    window_service = WindowService()
    click_engine = ClickEngine()
    hotkey_service = HotkeyService()
    return MainWindow(
        config_store=config_store,
        window_service=window_service,
        click_engine=click_engine,
        hotkey_service=hotkey_service,
        diagnostic_log_path=diagnostic_log_path,
    )


def run() -> int:
    runtime_directory = runtime_root()
    logging_session = configure_logging(runtime_directory)
    install_exception_hook(runtime_directory, logging_session)
    LOGGER.info("Runtime root: %s", runtime_directory)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Codex")
    app.setStyle("Fusion")
    apply_app_theme(app)

    window = build_main_window(
        config_path=runtime_directory / "config.json",
        diagnostic_log_path=logging_session.latest_log_path,
    )
    window.show()
    LOGGER.info("Application window shown.")
    return app.exec()


def main() -> int:
    return run()
