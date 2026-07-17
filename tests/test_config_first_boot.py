"""Regression: first-boot generates config without NameError; runtime exits cleanly."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestConfigFirstBoot(unittest.TestCase):
    """Empty data path must write config.toml and remain import-safe (no NameError)."""

    def _env(self, data_path: Path, repo_root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["QBITRR_OVERRIDES_DATA_PATH"] = str(data_path)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
        env.pop("PYTEST_CURRENT_TEST", None)
        return env

    def test_empty_data_path_generates_config_and_imports_cleanly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="qbitrr-first-boot-") as tmp:
            data_path = Path(tmp) / "data"
            cwd_path = Path(tmp) / "cwd"
            data_path.mkdir()
            cwd_path.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import qBitrr.config as c; "
                    "print('EXISTS', c.CONFIG_EXISTS); "
                    "assert c.CONFIG is not None",
                ],
                cwd=str(cwd_path),
                env=self._env(data_path, repo_root),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "first-boot import must succeed after writing default config; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )
            self.assertNotIn("NameError", result.stderr)
            self.assertNotIn("NameError", result.stdout)
            self.assertIn("EXISTS False", result.stdout)
            self.assertTrue(
                (data_path / "config.toml").exists(),
                "default config.toml must be written under QBITRR_OVERRIDES_DATA_PATH",
            )
            self.assertIn("has been generated with default values", result.stdout)

    def test_main_run_exits_zero_on_first_boot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="qbitrr-first-boot-run-") as tmp:
            data_path = Path(tmp) / "data"
            cwd_path = Path(tmp) / "cwd"
            data_path.mkdir()
            cwd_path.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from qBitrr.main import run; run()",
                ],
                cwd=str(cwd_path),
                env=self._env(data_path, repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "main.run() must exit 0 on first boot; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )
            self.assertTrue((data_path / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
