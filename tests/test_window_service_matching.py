from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autoclicker.domain.models import TargetWindow
from autoclicker.services.window_service import WindowService


class WindowServiceMatchingTests(unittest.TestCase):
    def test_find_saved_window_match_prefers_title_and_class(self) -> None:
        service = WindowService()
        saved_target = TargetWindow(
            hwnd=111,
            title="My Game Window",
            class_name="Tango3",
            process_id=999,
        )
        candidates = [
            TargetWindow(hwnd=201, title="Other Window", class_name="Tango3", process_id=123),
            TargetWindow(hwnd=202, title="My Game Window", class_name="Tango3", process_id=456),
        ]

        match = service.find_saved_window_match(saved_target, candidates)

        self.assertIsNotNone(match)
        self.assertEqual(match.hwnd, 202)

    def test_find_saved_window_match_returns_none_when_ambiguous(self) -> None:
        service = WindowService()
        saved_target = TargetWindow(
            hwnd=111,
            title="Same Title",
            class_name="Tango3",
        )
        candidates = [
            TargetWindow(hwnd=201, title="Same Title", class_name="Tango3"),
            TargetWindow(hwnd=202, title="Same Title", class_name="Tango3"),
        ]

        match = service.find_saved_window_match(saved_target, candidates)

        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
