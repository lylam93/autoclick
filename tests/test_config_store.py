from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autoclicker.domain.models import AppConfig
from autoclicker.services.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_root = PROJECT_ROOT / ".test-temp"
        self._scratch_root.mkdir(parents=True, exist_ok=True)
        self._workspace = self._scratch_root / f"config-store-{uuid.uuid4().hex}"
        self._workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._workspace, ignore_errors=True)

    def test_load_missing_file_returns_defaults(self) -> None:
        path = self._workspace / "config.json"
        store = ConfigStore(path)

        config = store.load()

        self.assertEqual(config, AppConfig())
        self.assertIn("No config file was found", store.last_message)

    def test_load_invalid_json_returns_defaults(self) -> None:
        path = self._workspace / "broken.json"
        path.write_text("{bad json", encoding="utf-8")
        store = ConfigStore(path)

        config = store.load()

        self.assertEqual(config, AppConfig())
        self.assertIn("Could not read", store.last_message)

    def test_legacy_config_is_upgraded_on_save(self) -> None:
        path = self._workspace / "config.json"
        path.write_text(
            json.dumps(
                {
                    "target_window": {"hwnd": "321", "title": " Demo "},
                    "click_settings": {"delivery_mode": "post", "mouse_button": "right"},
                    "hotkeys": {"start_stop": "F10", "capture_point": "F11"},
                    "points": [{"name": "Farm", "x": 11, "y": 22}],
                }
            ),
            encoding="utf-8",
        )
        store = ConfigStore(path)

        config = store.load()
        self.assertIn("Loaded legacy configuration", store.last_message)
        self.assertEqual(config.target_window.hwnd, 321)
        self.assertEqual(config.click_settings.delivery_mode, "post")

        store.save(config)
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], ConfigStore.CURRENT_VERSION)
        self.assertEqual(payload["app"], "Advanced Background Auto-Clicker")
        self.assertIn("saved_at", payload)
        self.assertEqual(payload["config"]["target_window"]["hwnd"], 321)
        self.assertEqual(payload["config"]["click_settings"]["delivery_mode"], "post")
        self.assertIn("format v2", store.last_message)


if __name__ == "__main__":
    unittest.main()
