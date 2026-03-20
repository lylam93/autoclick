from __future__ import annotations

import logging
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autoclicker.services.app_logging import configure_logging, get_logger


class AppLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_root = PROJECT_ROOT / ".test-temp"
        self._scratch_root.mkdir(parents=True, exist_ok=True)
        self._workspace = self._scratch_root / f"logging-{uuid.uuid4().hex}"
        self._workspace.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        logger = get_logger()
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        shutil.rmtree(self._workspace, ignore_errors=True)

    def test_configure_logging_creates_session_and_latest_logs(self) -> None:
        session = configure_logging(self._workspace)
        logger = get_logger("tests.logging")
        logger.info("hello from logging test")
        for handler in get_logger().handlers:
            handler.flush()

        self.assertTrue(session.logs_directory.exists())
        self.assertTrue(session.session_log_path.exists())
        self.assertTrue(session.latest_log_path.exists())
        latest_text = session.latest_log_path.read_text(encoding="utf-8")
        self.assertIn("hello from logging test", latest_text)


if __name__ == "__main__":
    unittest.main()
