from __future__ import annotations

import json
from pathlib import Path

from autoclicker.domain.models import AppConfig


class ConfigStore:
    """Reads and writes the MVP `config.json` file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("config.json")

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(raw)

    def save(self, config: AppConfig) -> None:
        payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False)
        self._path.write_text(payload + "\n", encoding="utf-8")

