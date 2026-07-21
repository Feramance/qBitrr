"""Combination coverage for auto_update helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qBitrr.auto_update import (
    AutoUpdater,
    cleanup_stale_runtime_overlay,
    get_binary_asset_patterns,
    get_installation_type,
    is_auto_update_supported,
    perform_binary_self_update,
    perform_self_update,
    read_overlay_version,
    write_overlay_version,
)
from qBitrr.versioning import (
    fetch_channel_release,
    is_stable_release_version,
    normalize_update_channel,
    version_build_segment,
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
    @mock.patch("qBitrr.auto_update._is_source_build_marker", return_value=False)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=False)
    @mock.patch("qBitrr.auto_update.sys")
    def test_detects_binary(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock, _source: mock.MagicMock
    ) -> None:
        mock_sys.frozen = True
        mock_sys._MEIPASS = "/tmp/frozen"
        self.assertEqual(get_installation_type(), "binary")

    @mock.patch("qBitrr.auto_update._is_source_build_marker", return_value=False)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=True)
    @mock.patch("qBitrr.auto_update.sys")
    def test_detects_docker_when_not_source(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock, _source: mock.MagicMock
    ) -> None:
        mock_sys.frozen = False
        self.assertEqual(get_installation_type(), "docker")

    @mock.patch("qBitrr.auto_update._is_source_build_marker", return_value=True)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=True)
    @mock.patch("qBitrr.auto_update.sys")
    def test_source_wins_over_docker(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock, _source: mock.MagicMock
    ) -> None:
        mock_sys.frozen = False
        self.assertEqual(get_installation_type(), "source")

    @mock.patch.dict("os.environ", {"QBITRR_SOURCE_BUILD": "1"}, clear=False)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=True)
    @mock.patch("qBitrr.auto_update.sys")
    def test_source_env_marker_in_docker(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock
    ) -> None:
        mock_sys.frozen = False
        with mock.patch("qBitrr.auto_update._repo_root") as root:
            root.return_value = mock.MagicMock(
                __truediv__=mock.MagicMock(
                    return_value=mock.MagicMock(exists=mock.MagicMock(return_value=False))
                )
            )
            self.assertEqual(get_installation_type(), "source")

    @mock.patch("qBitrr.auto_update._is_source_build_marker", return_value=True)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=False)
    @mock.patch("qBitrr.auto_update.sys")
    def test_detects_source(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock, _source: mock.MagicMock
    ) -> None:
        mock_sys.frozen = False
        self.assertEqual(get_installation_type(), "source")

    @mock.patch("qBitrr.auto_update._is_source_build_marker", return_value=False)
    @mock.patch("qBitrr.auto_update._is_docker_runtime", return_value=False)
    @mock.patch("qBitrr.auto_update.sys")
    def test_defaults_to_pip(
        self, mock_sys: mock.MagicMock, _docker: mock.MagicMock, _source: mock.MagicMock
    ) -> None:
        mock_sys.frozen = False
        self.assertEqual(get_installation_type(), "pip")


class TestIsAutoUpdateSupported(unittest.TestCase):
    def test_source_and_git_unsupported(self) -> None:
        self.assertFalse(is_auto_update_supported("source"))
        self.assertFalse(is_auto_update_supported("git"))

    def test_pip_docker_binary_supported(self) -> None:
        self.assertTrue(is_auto_update_supported("pip"))
        self.assertTrue(is_auto_update_supported("docker"))
        self.assertTrue(is_auto_update_supported("binary"))


class TestUpdateChannelHelpers(unittest.TestCase):
    def test_normalize_update_channel(self) -> None:
        self.assertEqual(normalize_update_channel("STABLE"), "stable")
        self.assertEqual(normalize_update_channel("nope"), "latest")

    def test_stable_build_segment(self) -> None:
        self.assertEqual(version_build_segment("5.12.12-1"), 1)
        self.assertEqual(version_build_segment("5.12.12-2"), 2)
        self.assertTrue(is_stable_release_version("5.12.12-1"))
        self.assertFalse(is_stable_release_version("5.12.12-2"))

    @mock.patch("qBitrr.versioning.requests.get")
    def test_fetch_stable_skips_build_releases(self, mock_get: mock.MagicMock) -> None:
        mock_get.return_value = mock.MagicMock(
            raise_for_status=mock.MagicMock(),
            json=mock.MagicMock(
                return_value=[
                    {
                        "tag_name": "v5.12.12-2",
                        "draft": False,
                        "prerelease": False,
                        "body": "build",
                        "html_url": "https://example/2",
                    },
                    {
                        "tag_name": "v5.12.12-1",
                        "draft": False,
                        "prerelease": False,
                        "body": "stable",
                        "html_url": "https://example/1",
                    },
                ]
            ),
        )
        info = fetch_channel_release("stable")
        self.assertIsNone(info.get("error"))
        self.assertEqual(info.get("normalized"), "5.12.12-1")
        self.assertEqual(info.get("channel"), "stable")

    @mock.patch("qBitrr.versioning.requests.get")
    def test_fetch_nightly_compares_sha(self, mock_get: mock.MagicMock) -> None:
        mock_get.return_value = mock.MagicMock(
            raise_for_status=mock.MagicMock(),
            json=mock.MagicMock(
                return_value={
                    "sha": "abc123def456",
                    "commit": {"message": "tip"},
                }
            ),
        )
        info = fetch_channel_release("nightly", current_nightly_sha="abc123def456")
        self.assertFalse(info.get("update_available"))
        info2 = fetch_channel_release("nightly", current_nightly_sha="old")
        self.assertTrue(info2.get("update_available"))


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
    def test_binary_nightly_refused(self, _typ: mock.MagicMock) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_self_update(logger, target_version="1.2.3", channel="nightly"))

    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="source")
    def test_source_refuses_update(self, _typ: mock.MagicMock) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_self_update(logger, target_version="1.2.3"))
        logger.error.assert_called()

    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="git")
    def test_legacy_git_alias_refuses_update(self, _typ: mock.MagicMock) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_self_update(logger, target_version="1.2.3"))

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

    @mock.patch("qBitrr.auto_update.get_runtime_overlay_dir")
    @mock.patch("qBitrr.auto_update.subprocess.run")
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="docker")
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_docker_installs_into_overlay(
        self, _typ: mock.MagicMock, run: mock.MagicMock, overlay_dir: mock.MagicMock
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            overlay_dir.return_value = runtime
            run.return_value = mock.MagicMock(stdout="ok", returncode=0)
            logger = mock.MagicMock()
            self.assertTrue(perform_self_update(logger, target_version="1.2.3"))
            args = run.call_args.args[0]
            self.assertIn("--target", args)
            self.assertIn(str(runtime), args)
            self.assertEqual(read_overlay_version(), "1.2.3")
            # Regression: execv bypasses docker-entrypoint.sh, so a first-time overlay
            # must be added to the current environment before the process restarts.
            self.assertEqual(os.environ.get("PYTHONPATH"), str(runtime))


class TestBinarySelfUpdate(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.fetch_release_sha256sums", return_value={})
    @mock.patch(
        "qBitrr.auto_update.get_binary_download_url",
        return_value={
            "url": "https://example/qBitrr.tar.gz",
            "name": "qBitrr.tar.gz",
            "size": 1,
            "error": None,
        },
    )
    def test_checksum_missing_refuses(self, _url: mock.MagicMock, _sums: mock.MagicMock) -> None:
        logger = mock.MagicMock()
        self.assertFalse(perform_binary_self_update(logger, "1.2.3"))

    @mock.patch("qBitrr.auto_update.fetch_release_sha256sums")
    @mock.patch("qBitrr.auto_update.get_binary_download_url")
    @mock.patch("qBitrr.auto_update._sha256_file", return_value="deadbeef")
    def test_checksum_mismatch_refuses(
        self,
        _hash: mock.MagicMock,
        mock_url: mock.MagicMock,
        mock_sums: mock.MagicMock,
    ) -> None:
        mock_url.return_value = {
            "url": "https://example/qBitrr.tar.gz",
            "name": "qBitrr.tar.gz",
            "size": 1,
            "error": None,
        }
        mock_sums.return_value = {"qBitrr.tar.gz": "cafebabe"}
        with mock.patch("qBitrr.auto_update.requests.get") as mock_get:
            response = mock.MagicMock()
            response.__enter__ = mock.MagicMock(return_value=response)
            response.__exit__ = mock.MagicMock(return_value=False)
            response.iter_content = mock.MagicMock(return_value=[b"data"])
            response.raise_for_status = mock.MagicMock()
            mock_get.return_value = response
            logger = mock.MagicMock()
            self.assertFalse(perform_binary_self_update(logger, "1.2.3"))


class TestDockerOverlayCleanup(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.get_runtime_overlay_dir")
    def test_clears_stale_overlay_when_image_ahead(self, overlay_dir: mock.MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            overlay_dir.return_value = runtime
            write_overlay_version("1.0.0")
            cleared = cleanup_stale_runtime_overlay(image_version="2.0.0")
            self.assertTrue(cleared)
            self.assertIsNone(read_overlay_version())


class TestPerformAutoUpdateVerifyGate(unittest.TestCase):
    @mock.patch("qBitrr.main.perform_self_update", return_value=True)
    @mock.patch("qBitrr.auto_update.verify_update_success", return_value=False)
    @mock.patch("qBitrr.auto_update.is_auto_update_supported", return_value=True)
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="pip")
    @mock.patch("qBitrr.main.fetch_channel_release")
    @mock.patch("qBitrr.main.get_auto_update_settings", return_value=(True, "0 3 * * 0", "latest"))
    @mock.patch("qBitrr.main.read_nightly_sha", return_value=None)
    def test_verify_failure_skips_restart(
        self,
        _sha: mock.MagicMock,
        _settings: mock.MagicMock,
        mock_fetch: mock.MagicMock,
        _typ: mock.MagicMock,
        _supported: mock.MagicMock,
        _verify: mock.MagicMock,
        _perform: mock.MagicMock,
    ) -> None:
        mock_fetch.return_value = {
            "error": None,
            "normalized": "9.9.9",
            "raw_tag": "v9.9.9",
            "update_available": True,
            "nightly_sha": None,
        }
        manager = mock.MagicMock()
        manager.logger = mock.MagicMock()
        manager.request_restart = mock.MagicMock()

        from qBitrr.main import qBitManager

        qBitManager._perform_auto_update(manager)
        manager.request_restart.assert_not_called()

    @mock.patch("qBitrr.auto_update.is_auto_update_supported", return_value=False)
    @mock.patch("qBitrr.auto_update.get_installation_type", return_value="source")
    @mock.patch("qBitrr.main.get_auto_update_settings", return_value=(True, "0 3 * * 0", "latest"))
    def test_configure_skips_source_install(
        self,
        _settings: mock.MagicMock,
        _typ: mock.MagicMock,
        _supported: mock.MagicMock,
    ) -> None:
        from qBitrr.main import qBitManager

        manager = mock.MagicMock()
        manager.logger = mock.MagicMock()
        manager.auto_updater = None
        qBitManager.configure_auto_update(manager)
        self.assertIsNone(manager.auto_updater)
        manager.logger.info.assert_called()


if __name__ == "__main__":
    unittest.main()
