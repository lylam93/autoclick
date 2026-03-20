from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_LOGGER_NAME = "autoclicker"
MAX_LATEST_LOG_BYTES = 1_000_000
LATEST_LOG_BACKUP_COUNT = 3

_base_logger = logging.getLogger(APP_LOGGER_NAME)
if not _base_logger.handlers:
    _base_logger.addHandler(logging.NullHandler())


@dataclass(slots=True)
class LoggingSession:
    logs_directory: Path
    session_log_path: Path
    latest_log_path: Path


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(APP_LOGGER_NAME)

    normalized = name.strip()
    if normalized.startswith(f"{APP_LOGGER_NAME}.") or normalized == APP_LOGGER_NAME:
        return logging.getLogger(normalized)
    return logging.getLogger(f"{APP_LOGGER_NAME}.{normalized}")


def configure_logging(runtime_directory: Path) -> LoggingSession:
    logs_directory = runtime_directory / "logs"
    logs_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    session_log_path = logs_directory / f"session-{timestamp}.log"
    latest_log_path = logs_directory / "latest.log"

    logger = get_logger()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    session_handler = logging.FileHandler(session_log_path, encoding="utf-8")
    session_handler.setLevel(logging.DEBUG)
    session_handler.setFormatter(formatter)

    latest_handler = RotatingFileHandler(
        latest_log_path,
        maxBytes=MAX_LATEST_LOG_BYTES,
        backupCount=LATEST_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    latest_handler.setLevel(logging.DEBUG)
    latest_handler.setFormatter(formatter)

    logger.addHandler(session_handler)
    logger.addHandler(latest_handler)
    logger.info("Logging initialized.")
    logger.info("Session log file: %s", session_log_path)
    logger.info("Latest log file: %s", latest_log_path)

    return LoggingSession(
        logs_directory=logs_directory,
        session_log_path=session_log_path,
        latest_log_path=latest_log_path,
    )
