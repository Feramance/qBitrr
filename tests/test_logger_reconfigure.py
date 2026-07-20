"""Tests for live logging reconfiguration (L4)."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch


class TestReconfigureLoggingFromConfig(unittest.TestCase):
    def test_applies_console_level_from_config(self) -> None:
        from qBitrr.logger import reconfigure_logging_from_config

        config_mock = MagicMock()
        config_mock.get.return_value = "DEBUG"
        env_mock = MagicMock()
        env_mock.settings.console_level = None

        test_logger = logging.getLogger("qBitrr.test.reconfigure")
        with (
            patch("qBitrr.logger.CONFIG", config_mock),
            patch("qBitrr.logger.ENVIRO_CONFIG", env_mock),
        ):
            level_name = reconfigure_logging_from_config()

        self.assertEqual(level_name, "DEBUG")
        self.assertEqual(test_logger.level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
