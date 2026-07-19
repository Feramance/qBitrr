"""Combination coverage for auto_update helpers."""

from __future__ import annotations

import unittest
from unittest import mock

from qBitrr.auto_update import (
    AutoUpdater,
    get_binary_asset_patterns,
    get_installation_type,
    perform_self_update,
)


class TestGetBinaryAssetPatterns(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.platform.machine", return_value="x86_64")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="Linux")
    def test_linux_x64_pattern(self, _sys: mock.MagicMock, _mach: mock.MagicMock) -> None:
        self.assertEqual(get_binary_asset_patterns(), ["ubuntu-latest-x64"])

    @mock.patch("qBitrr.auto_update.platform.machine", return_value="arm64")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="Darwin")
    def test_macos_arm64_pattern(self, _sys: mock.MagicMock, _mach: mock.MagicMock) -> None:
        self.assertEqual(get_binary_asset_patterns(), ["macOS-latest-arm64"])

    @mock.patch("qBitrr.auto_update.platform.machine", return_value="AMD64")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="Windows")
    def test_windows_tries_legacy_runner_names(
        self, _sys: mock.MagicMock, _mach: mock.MagicMock
    ) -> None:
        patterns = get_binary_asset_patterns()
        self.assertEqual(
            patterns,
            ["windows-2025-vs2026-x64", "windows-2025-x64", "windows-latest-x64"],
        )

    @mock.patch("qBitrr.auto_update.platform.machine", return_value="arm64")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="FreeBSD")
    def test_unsupported_os_raises(self, _sys: mock.MagicMock, _mach: mock.MagicMock) -> None:
        with self.assertRaises(RuntimeError):
            get_binary_asset_patterns()


class TestAutoUpdateUnsupportedPlatformMessageFixedOnRefactor(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.requests.get")
    @mock.patch("qBitrr.auto_update.get_binary_asset_patterns")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="Windows")
    @mock.patch("qBitrr.auto_update.platform.machine", return_value="ARM64")
    def test_names_first_matching_unsupported_pattern(
        self,
        _machine: mock.MagicMock,
        _system: mock.MagicMock,
        mock_patterns: mock.MagicMock,
        mock_get: mock.MagicMock,
    ) -> None:
        from qBitrr.auto_update import get_binary_download_url

        mock_patterns.return_value = [
            "windows-2025-vs2026-arm64",
            "windows-2025-arm64",
            "windows-latest-arm64",
        ]
        mock_get.return_value = mock.MagicMock(
            raise_for_status=mock.MagicMock(),
            json=mock.MagicMock(return_value={"assets": []}),
        )
        logger = mock.MagicMock()
        result = get_binary_download_url("v1.0.0", logger)
        error = result["error"]
        self.assertIsNotNone(error)
        self.assertIn("windows-2025-vs2026-arm64", error)
        self.assertIn("not built by release workflow", error)


class TestGetInstallationType(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.sys")
    def test_detects_binary(self, mock_sys: mock.MagicMock) -> None:
        mock_sys.frozen = True
        mock_sys._MEIPASS = "/tmp/frozen"
        self.assertEqual(get_installation_type(), "binary")

    @mock.patch("qBitrr.auto_update.Path")
    @mock.patch("qBitrr.auto_update.sys")
    def test_detects_git(self, mock_sys: mock.MagicMock, mock_path: mock.MagicMock) -> None:
        mock_sys.frozen = False
        mock_path.return_value.resolve.return_value.parent.parent = mock.MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.__truediv__ = mock.MagicMock(
            return_value=mock.MagicMock(exists=mock.MagicMock(return_value=True))
        )
        self.assertEqual(get_installation_type(), "git")

    @mock.patch("qBitrr.auto_update.Path")
    @mock.patch("qBitrr.auto_update.sys")
    def test_defaults_to_pip(self, mock_sys: mock.MagicMock, mock_path: mock.MagicMock) -> None:
        mock_sys.frozen = False
        git_dir = mock.MagicMock()
        git_dir.exists.return_value = False
        mock_path.return_value.resolve.return_value.parent.parent.__truediv__ = mock.MagicMock(
            return_value=git_dir
        )
        self.assertEqual(get_installation_type(), "pip")


class TestAutoUpdater(unittest.TestCase):
    def test_start_rejects_invalid_cron(self) -> None:
        logger = mock.MagicMock()
        updater = AutoUpdater("not a cron", lambda: None, logger)
        self.assertFalse(updater.start())
        logger.error.assert_called()

    def test_start_accepts_valid_cron(self) -> None:
        logger = mock.MagicMock()
        updater = AutoUpdater("0 3 * * 0", lambda: None, logger)
        self.assertTrue(updater.start())
        updater.stop()

    def test_callback_exceptions_are_logged_not_raised(self) -> None:
        logger = mock.MagicMock()

        def boom() -> None:
            raise RuntimeError("boom")

        updater = AutoUpdater("* * * * *", boom, logger)
        updater._execute()
        logger.exception.assert_called_with("Auto update failed")


class TestPerformSelfUpdate(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="binary")
    def test_binary_returns_false(self, _typ: mock.MagicMock) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_self_update(logger, target_version="1.2.3"))
        logger.info.assert_any_call("Binary installation detected - manual update required")

    @mock.patch("qBitrr.auto_update.subprocess.run")
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="pip")
    def test_pip_upgrade_invokes_pip(self, _typ: mock.MagicMock, run: mock.MagicMock) -> None:
        run.return_value = mock.MagicMock(stdout="ok", returncode=0)
        logger = mock.MagicMock()
        self.assertTrue(perform_self_update(logger, target_version="1.2.3"))
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertIn("pip", args)
        self.assertIn("install", args)
        self.assertIn("qBitrr2==1.2.3", args)

    @mock.patch("qBitrr.auto_update.subprocess.run")
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="pip")
    def test_pip_refuses_unversioned_upgrade(
        self, _typ: mock.MagicMock, run: mock.MagicMock
    ) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_self_update(logger))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
