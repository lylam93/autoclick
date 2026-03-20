from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autoclicker.domain.models import AppConfig, ClickSettings


class AppConfigModelTests(unittest.TestCase):
    def test_from_dict_normalizes_legacy_values(self) -> None:
        config = AppConfig.from_dict(
            {
                "target_window": {
                    "hwnd": "123",
                    "child_hwnd": "123",
                    "process_id": "456",
                    "title": " Legacy Window ",
                },
                "click_settings": {
                    "delay_ms": "0",
                    "use_random_delay": "yes",
                    "random_min_ms": "1500",
                    "random_max_ms": "1000",
                    "max_clicks": 0,
                    "mouse_button": "middle",
                    "delivery_mode": "queue",
                },
                "hotkeys": {
                    "start_stop": "",
                    "capture_point": None,
                },
                "points": [
                    {
                        "name": "",
                        "x": "12",
                        "y": "34",
                    }
                ],
            }
        )

        self.assertEqual(config.target_window.hwnd, 123)
        self.assertIsNone(config.target_window.child_hwnd)
        self.assertEqual(config.target_window.process_id, 456)
        self.assertEqual(config.target_window.title, "Legacy Window")
        self.assertEqual(config.click_settings.delay_ms, 1)
        self.assertTrue(config.click_settings.use_random_delay)
        self.assertEqual(config.click_settings.random_min_ms, 1000)
        self.assertEqual(config.click_settings.random_max_ms, 1500)
        self.assertIsNone(config.click_settings.max_clicks)
        self.assertEqual(config.click_settings.mouse_button, "left")
        self.assertEqual(config.click_settings.delivery_mode, "send")
        self.assertEqual(config.hotkeys.start_stop, "F8")
        self.assertEqual(config.hotkeys.capture_point, "F9")
        self.assertEqual(config.points[0].name, "Primary")
        self.assertEqual((config.points[0].x, config.points[0].y), (12, 34))

    def test_click_settings_from_dict_preserves_valid_values(self) -> None:
        settings = ClickSettings.from_dict(
            {
                "delay_ms": 250,
                "use_random_delay": True,
                "random_min_ms": 350,
                "random_max_ms": 700,
                "max_clicks": 10,
                "mouse_button": "right",
                "delivery_mode": "post",
            }
        )

        self.assertEqual(settings.delay_ms, 250)
        self.assertTrue(settings.use_random_delay)
        self.assertEqual(settings.random_min_ms, 350)
        self.assertEqual(settings.random_max_ms, 700)
        self.assertEqual(settings.max_clicks, 10)
        self.assertEqual(settings.mouse_button, "right")
        self.assertEqual(settings.delivery_mode, "post")

    def test_to_dict_returns_normalized_payload(self) -> None:
        config = AppConfig.from_dict(
            {
                "click_settings": {
                    "delay_ms": "-25",
                    "random_min_ms": "9999",
                    "random_max_ms": "1",
                }
            }
        )

        payload = config.to_dict()
        self.assertEqual(payload["click_settings"]["delay_ms"], 1)
        self.assertEqual(payload["click_settings"]["random_min_ms"], 1)
        self.assertEqual(payload["click_settings"]["random_max_ms"], 9999)


if __name__ == "__main__":
    unittest.main()
