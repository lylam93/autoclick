from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autoclicker.domain.models import AppConfig
from autoclicker.services.app_logging import get_logger


LOGGER = get_logger("services.config_store")


class ConfigStore:
    """Reads and writes the MVP `config.json` file."""

    CURRENT_VERSION = 2

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("config.json")
        self._last_message = f"Configuration path is {self._path.resolve()}."
        LOGGER.debug("ConfigStore initialized for %s", self._path.resolve())

    @property
    def path(self) -> Path:
        return self._path

    @property
    def last_message(self) -> str:
        return self._last_message

    def load(self) -> AppConfig:
        if not self._path.exists():
            self._last_message = (
                f"No config file was found at {self._path.resolve()}. "
                "Using the default settings for this session."
            )
            LOGGER.info(self._last_message)
            return AppConfig()

        try:
            raw_payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._last_message = (
                f"Could not read {self._path.resolve()} cleanly ({exc}). "
                "Using the default settings for this session."
            )
            LOGGER.warning(self._last_message)
            return AppConfig()

        if not isinstance(raw_payload, dict):
            self._last_message = (
                f"Config file {self._path.resolve()} does not contain a JSON object. "
                "Using the default settings for this session."
            )
            LOGGER.warning(self._last_message)
            return AppConfig()

        version = raw_payload.get("version")
        raw_config: Any = raw_payload
        message: str

        if isinstance(raw_payload.get("config"), dict):
            raw_config = raw_payload["config"]
            if version is None:
                message = f"Loaded configuration from {self._path.resolve()} with an unspecified file format version."
            else:
                message = f"Loaded configuration from {self._path.resolve()} (format v{version})."
        else:
            message = (
                f"Loaded legacy configuration from {self._path.resolve()}. "
                f"The next save will upgrade it to format v{self.CURRENT_VERSION}."
            )

        config = AppConfig.from_dict(raw_config if isinstance(raw_config, dict) else None)
        self._last_message = message
        LOGGER.info(message)
        return config

    def save(self, config: AppConfig) -> None:
        normalized_config = config.normalized()
        payload = {
            "version": self.CURRENT_VERSION,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "app": "Advanced Background Auto-Clicker",
            "config": normalized_config.to_dict(),
        }

        serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary_path.write_text(serialized, encoding="utf-8")
        temporary_path.replace(self._path)

        self._last_message = (
            f"Configuration saved to {self._path.resolve()} "
            f"(format v{self.CURRENT_VERSION})."
        )
        LOGGER.info(self._last_message)
