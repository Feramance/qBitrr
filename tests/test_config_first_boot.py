"""Regression: first-boot generates config and exits cleanly (no NameError)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestConfigFirstBoot(unittest.TestCase):
    """Importing config with an empty data path must exit 0 after writing config.toml."""

    def test_empty_data_path_generates_config_and_exits_zero(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="qbitrr-first-boot-") as tmp:
            data_path = Path(tmp) / "data"
            cwd_path = Path(tmp) / "cwd"
            data_path.mkdir()
            cwd_path.mkdir()

            env = os.environ.copy()
            env["QBITRR_OVERRIDES_DATA_PATH"] = str(data_path)
            # Prefer repo on PYTHONPATH so we exercise this checkout, not a site package.
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
            )
            # Avoid leftover argv flags that short-circuit config generation.
            env.pop("PYTEST_CURRENT_TEST", None)

            result = subprocess.run(
                [sys.executable, "-c", "import qBitrr.config"],
                cwd=str(cwd_path),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "first-boot import must exit 0 after writing default config; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )
            self.assertNotIn("NameError", result.stderr)
            self.assertNotIn("NameError", result.stdout)
            self.assertTrue(
                (data_path / "config.toml").exists(),
                "default config.toml must be written under QBITRR_OVERRIDES_DATA_PATH",
            )
            self.assertIn("has been generated with default values", result.stdout)


if __name__ == "__main__":
    unittest.main()
