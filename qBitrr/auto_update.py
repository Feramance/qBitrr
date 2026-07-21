from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from croniter import croniter
from croniter.croniter import CroniterBadCronError

from qBitrr.versioning import (
    DEFAULT_REPOSITORY,
    NIGHTLY_PIP_URL,
    github_request_headers,
    is_newer_version,
    normalize_update_channel,
    normalize_version,
)

RUNTIME_DIR_NAME = "runtime"
VERSION_MARKER = ".qbitrr-version"
NIGHTLY_SHA_MARKER = ".qbitrr-nightly-sha"
BINARY_OLD_SUFFIX = ".old"
BINARY_NEW_SUFFIX = ".new"


def _is_docker_runtime() -> bool:
    """Return True when running inside the qBitrr Docker image / container."""
    if os.environ.get("QBITRR_DOCKER_RUNNING") == "69420":
        return True
    try:
        from qBitrr.home_path import ON_DOCKER

        if ON_DOCKER:
            return True
    except Exception:
        pass
    try:
        from jaraco.docker import is_docker

        return bool(is_docker())
    except Exception:
        return False


def _is_truthy_env(value: str | None) -> bool:
    """Return True for common truthy environment flag values."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _repo_root() -> Path:
    """Return the qBitrr repository / package root directory."""
    return Path(__file__).resolve().parent.parent


def _is_source_build_marker() -> bool:
    """True when this process is a source checkout or explicitly marked as one."""
    if (_repo_root() / ".git").exists():
        return True
    return _is_truthy_env(os.environ.get("QBITRR_SOURCE_BUILD"))


def is_auto_update_supported(install_type: str | None = None) -> bool:
    """Return whether auto-update apply is supported for the installation type.

    Source builds (``.git`` or ``QBITRR_SOURCE_BUILD``) never support auto-update.
    The legacy alias ``git`` is treated the same as ``source``.
    """
    resolved = install_type or get_installation_type()
    if resolved in {"source", "git"}:
        return False
    return resolved in {"pip", "docker", "binary"}


def get_installation_type() -> str:
    """Detect how qBitrr is installed.

    Returns:
        ``binary``, ``source``, ``docker``, or ``pip``.

    Detection order: frozen binary → source (``.git`` / ``QBITRR_SOURCE_BUILD``) →
    docker → pip. Source is checked before docker so containers built from a git
    tree (or with ``QBITRR_SOURCE_BUILD=1``) are not treated as updatable docker
    installs.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return "binary"
    if _is_source_build_marker():
        return "source"
    if _is_docker_runtime():
        return "docker"
    return "pip"


def get_runtime_overlay_dir() -> Path:
    """Return the persistent Docker runtime overlay directory (``/config/runtime``)."""
    from qBitrr.home_path import HOME_PATH

    return Path(HOME_PATH) / RUNTIME_DIR_NAME


def _activate_runtime_overlay(runtime: Path) -> None:
    """Ensure a restarted interpreter imports the Docker runtime overlay first."""
    runtime_path = str(runtime)
    existing = os.environ.get("PYTHONPATH")
    paths = existing.split(os.pathsep) if existing else []
    if runtime_path not in paths:
        os.environ["PYTHONPATH"] = os.pathsep.join([runtime_path, *paths])


def get_nightly_sha_path() -> Path:
    """Path used to persist the last-applied nightly commit SHA."""
    install_type = get_installation_type()
    if install_type == "docker":
        return get_runtime_overlay_dir() / NIGHTLY_SHA_MARKER
    from qBitrr.home_path import APPDATA_FOLDER

    return Path(APPDATA_FOLDER) / NIGHTLY_SHA_MARKER


def read_nightly_sha() -> str | None:
    """Read the last-applied nightly SHA marker, if present."""
    path = get_nightly_sha_path()
    try:
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            return value or None
    except OSError:
        return None
    return None


def write_nightly_sha(sha: str) -> None:
    """Persist the applied nightly commit SHA."""
    path = get_nightly_sha_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sha.strip() + "\n", encoding="utf-8")


def read_overlay_version() -> str | None:
    """Read the Docker overlay version marker."""
    marker = get_runtime_overlay_dir() / VERSION_MARKER
    try:
        if marker.is_file():
            return normalize_version(marker.read_text(encoding="utf-8").strip())
    except OSError:
        return None
    return None


def write_overlay_version(version: str) -> None:
    """Write the Docker overlay version marker."""
    runtime = get_runtime_overlay_dir()
    runtime.mkdir(parents=True, exist_ok=True)
    normalized = normalize_version(version) or version
    (runtime / VERSION_MARKER).write_text(normalized + "\n", encoding="utf-8")


def clear_runtime_overlay() -> None:
    """Remove the Docker runtime overlay directory if it exists."""
    runtime = get_runtime_overlay_dir()
    if runtime.exists():
        shutil.rmtree(runtime, ignore_errors=True)


def cleanup_stale_runtime_overlay(image_version: str | None = None) -> bool:
    """Clear overlay when the image version is already newer/equal (non-nightly).

    Returns:
        True when the overlay was cleared.
    """
    from qBitrr.bundled_data import patched_version

    overlay = read_overlay_version()
    if not overlay:
        return False
    current = normalize_version(image_version or patched_version)
    # If image is not older than overlay, drop the overlay so a newer image wins.
    if current and not is_newer_version(overlay, current):
        clear_runtime_overlay()
        return True
    return False


def get_binary_asset_pattern() -> str:
    """Get the preferred asset filename pattern for the current platform."""
    return get_binary_asset_patterns()[0]


def get_binary_asset_patterns() -> list[str]:
    """Return asset filename patterns to try, most preferred first."""
    system = platform.system()
    machine = platform.machine()

    if system == "Linux":
        os_parts = ["ubuntu-latest"]
        arch_part = "x64" if machine in ("x86_64", "AMD64") else "arm64"
    elif system == "Darwin":
        os_parts = ["macOS-latest"]
        arch_part = "arm64" if machine == "arm64" else "x64"
    elif system == "Windows":
        os_parts = ["windows-2025-vs2026", "windows-2025", "windows-latest"]
        arch_part = "x64" if machine in ("x86_64", "AMD64") else "arm64"
    else:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    return [f"{os_part}-{arch_part}" for os_part in os_parts]


def get_binary_download_url(release_tag: str, logger: logging.Logger) -> dict[str, Any]:
    """Get the download URL for the binary asset matching current platform."""
    try:
        asset_patterns = get_binary_asset_patterns()
        logger.debug("Looking for binary asset matching: %s", asset_patterns)

        tag = release_tag if release_tag.startswith(("v", "V")) else f"v{release_tag}"
        url = f"https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases/tags/{tag}"
        response = requests.get(url, headers=github_request_headers(), timeout=30)
        response.raise_for_status()
        release_data = response.json()

        assets = release_data.get("assets", [])
        for asset_pattern in asset_patterns:
            for asset in assets:
                name = asset.get("name", "")
                if asset_pattern in name and not name.endswith(".sha256"):
                    if name.endswith((".tar.gz", ".zip", ".tgz")):
                        return {
                            "url": asset["browser_download_url"],
                            "name": name,
                            "size": asset.get("size", 0),
                            "error": None,
                        }

        available = [a.get("name") for a in assets]
        logger.error(
            "No binary asset found for platform %s in release %s",
            asset_patterns,
            release_tag,
        )
        logger.debug("Available assets: %s", available)

        system = platform.system()
        machine = platform.machine()
        unsupported_platforms = [
            "ubuntu-latest-arm64",
            "macOS-latest-x64",
            "windows-2025-vs2026-arm64",
            "windows-2025-arm64",
            "windows-latest-arm64",
        ]
        error_msg = f"No binary available for {system} {machine}"
        matched = next((p for p in asset_patterns if p in unsupported_platforms), None)
        if matched:
            error_msg += f" (platform {matched} is not built by release workflow)"

        return {"url": None, "name": None, "size": None, "error": error_msg}

    except Exception as exc:
        logger.error("Failed to fetch binary asset info: %s", exc)
        return {"url": None, "name": None, "size": None, "error": str(exc)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_release_sha256sums(release_tag: str, logger: logging.Logger) -> dict[str, str]:
    """Download and parse SHA256 checksums for a release tag.

    Supports a combined ``SHA256SUMS`` asset and per-asset ``*.sha256`` files.
    """
    tag = release_tag if release_tag.startswith(("v", "V")) else f"v{release_tag}"
    url = f"https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases/tags/{tag}"
    response = requests.get(url, headers=github_request_headers(), timeout=30)
    response.raise_for_status()
    assets = response.json().get("assets", [])
    checksums: dict[str, str] = {}

    def _parse_sums(text: str) -> None:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                digest, name = parts[0], parts[-1]
                name = name.lstrip("*")
                checksums[name] = digest.lower()

    for asset in assets:
        name = asset.get("name") or ""
        download_url = asset.get("browser_download_url")
        if not download_url:
            continue
        if name == "SHA256SUMS" or name.endswith(".sha256"):
            try:
                content = requests.get(download_url, headers=github_request_headers(), timeout=60)
                content.raise_for_status()
                text = content.text.strip()
                if name.endswith(".sha256") and len(text.split()) == 1:
                    # Single digest for the basename without .sha256
                    checksums[name[: -len(".sha256")]] = text.split()[0].lower()
                else:
                    _parse_sums(text)
            except Exception as exc:
                logger.warning("Failed to fetch checksum asset %s: %s", name, exc)

    return checksums


def _find_extracted_binary(extract_dir: Path) -> Path | None:
    """Locate the qBitrr executable inside an extracted release archive."""
    candidates: list[Path] = []
    for path in extract_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name in {"qbitrr", "qbitrr.exe"}:
            candidates.append(path)
    if not candidates:
        return None
    # Prefer deepest match under dist/
    candidates.sort(key=lambda p: (0 if "dist" in p.parts else 1, len(p.parts)))
    return candidates[0]


def _atomic_replace_binary(current: Path, new_binary: Path, logger: logging.Logger) -> None:
    """Replace the running binary using a side-by-side rename pattern."""
    old_path = current.with_suffix(current.suffix + BINARY_OLD_SUFFIX)
    new_staging = current.with_suffix(current.suffix + BINARY_NEW_SUFFIX)
    if new_staging.exists():
        new_staging.unlink()
    shutil.copy2(new_binary, new_staging)
    if os.name != "nt":
        new_staging.chmod(new_staging.stat().st_mode | 0o111)

    if old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            logger.debug("Could not remove previous .old binary at %s", old_path)

    os.replace(current, old_path)
    try:
        os.replace(new_staging, current)
    except Exception:
        # Attempt rollback
        with contextlib.suppress(OSError):
            os.replace(old_path, current)
        raise


def cleanup_old_binary() -> None:
    """Delete leftover ``*.old`` binary from a previous successful self-update."""
    if not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")):
        return
    current = Path(sys.executable).resolve()
    old_path = current.with_suffix(current.suffix + BINARY_OLD_SUFFIX)
    if old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            pass


def perform_binary_self_update(logger: logging.Logger, target_version: str) -> bool:
    """Download, verify, and replace the frozen binary for ``target_version``."""
    tag = target_version if target_version.startswith(("v", "V")) else f"v{target_version}"
    asset = get_binary_download_url(tag, logger)
    if asset.get("error") or not asset.get("url") or not asset.get("name"):
        logger.error("Binary update aborted: %s", asset.get("error") or "missing asset URL")
        return False

    asset_name = asset["name"]
    try:
        checksums = fetch_release_sha256sums(tag, logger)
    except Exception as exc:
        logger.error("Failed to load release checksums: %s", exc)
        return False

    expected = checksums.get(asset_name)
    if not expected:
        logger.error(
            "No SHA256 digest found for %s; refusing binary self-update without checksum",
            asset_name,
        )
        return False

    current = Path(sys.executable).resolve()
    with tempfile.TemporaryDirectory(prefix="qbitrr-update-") as tmp:
        tmp_dir = Path(tmp)
        archive_path = tmp_dir / asset_name
        logger.info("Downloading binary update: %s", asset_name)
        with requests.get(
            asset["url"], headers=github_request_headers(), stream=True, timeout=300
        ) as response:
            response.raise_for_status()
            with archive_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

        actual = _sha256_file(archive_path)
        if actual.lower() != expected.lower():
            logger.error(
                "Binary checksum mismatch for %s: expected %s, got %s",
                asset_name,
                expected,
                actual,
            )
            return False

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        if asset_name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(extract_dir)
        else:
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(extract_dir)

        new_binary = _find_extracted_binary(extract_dir)
        if not new_binary:
            logger.error("Could not locate qBitrr executable inside %s", asset_name)
            return False

        logger.info("Replacing binary at %s", current)
        _atomic_replace_binary(current, new_binary, logger)
    return True


def _pip_install(
    logger: logging.Logger,
    package_spec: str,
    *,
    target: Path | None = None,
) -> bool:
    """Run ``python -m pip install --upgrade`` for ``package_spec``."""
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--target", str(target)])
    cmd.append(package_spec)
    logger.debug("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = (result.stdout or "").strip()
        if stdout:
            logger.info("pip install output:\n%s", stdout)
        return True
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        logger.error("Failed to install %s via pip: %s", package_spec, stderr or exc)
        return False


class AutoUpdater:
    """Background worker that executes a callback on a cron schedule."""

    def __init__(self, cron_expr: str, callback: Callable[[], None], logger: logging.Logger):
        self._cron_expr = cron_expr
        self._callback = callback
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._iterator = None

    def start(self) -> bool:
        """Start the background worker. Returns False if cron expression is invalid."""
        self.stop()
        try:
            self._iterator = croniter(self._cron_expr, datetime.now())
        except CroniterBadCronError as exc:
            self._logger.error(
                "Auto update disabled: invalid cron expression '%s' (%s)",
                self._cron_expr,
                exc,
            )
            self._iterator = None
            return False

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="AutoUpdater", daemon=True)
        self._thread.start()
        self._logger.info("Auto update scheduled with cron '%s'.", self._cron_expr)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                self._logger.warning("Auto update worker failed to stop within timeout")
        self._thread = None

    def _run(self) -> None:
        iterator = self._iterator
        if iterator is None:
            return
        stop_event = self._stop_event
        while True:
            next_run = iterator.get_next(datetime)
            self._logger.debug("Next auto update scheduled for %s", next_run.isoformat())
            while True:
                if stop_event.is_set():
                    return
                wait_seconds = (next_run - datetime.now()).total_seconds()
                if wait_seconds <= 0:
                    break
                stop_event.wait(timeout=min(wait_seconds, 60))
            if stop_event.is_set():
                return
            self._execute()

    def _execute(self) -> None:
        self._logger.info("Auto update triggered")
        try:
            self._callback()
        except Exception:  # pragma: no cover - safeguard for background thread
            self._logger.exception("Auto update failed")
        else:
            self._logger.info("Auto update completed")


def verify_update_success(
    expected_version: str,
    logger: logging.Logger,
    *,
    channel: str | None = None,
    expected_nightly_sha: str | None = None,
) -> bool:
    """Verify that the installed version matches the expected target."""
    resolved_channel = normalize_update_channel(channel)
    install_type = get_installation_type()
    try:
        if install_type == "binary":
            current = Path(sys.executable).resolve()
            if current.is_file():
                logger.info("Binary update verified on disk at %s", current)
                return True
            logger.error("Binary executable missing after update: %s", current)
            return False

        if resolved_channel == "nightly":
            if expected_nightly_sha:
                current_sha = read_nightly_sha()
                if install_type in {"source", "git"}:
                    repo_root = _repo_root()
                    try:
                        current_sha = subprocess.run(
                            ["git", "rev-parse", "HEAD"],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            check=True,
                        ).stdout.strip()
                    except Exception:
                        pass
                if current_sha and current_sha.lower() == expected_nightly_sha.lower():
                    logger.info("Nightly update verified: SHA %s", current_sha[:12])
                    return True
                logger.warning(
                    "Nightly SHA mismatch after update: expected %s, got %s",
                    expected_nightly_sha,
                    current_sha,
                )
                return False
            logger.warning("Nightly verify skipped: no expected SHA provided")
            return False

        if "qBitrr.bundled_data" in sys.modules:
            del sys.modules["qBitrr.bundled_data"]

        from qBitrr import bundled_data

        current = normalize_version(bundled_data.version)
        # Docker overlay may update target packages without reloading image bundled_data;
        # prefer overlay marker when present.
        overlay = read_overlay_version() if install_type == "docker" else None
        if overlay:
            current = overlay
        expected = normalize_version(expected_version)

        if current == expected:
            logger.info("Update verified: version %s installed successfully", current)
            return True
        logger.warning(
            "Version mismatch after update: expected %s, got %s",
            expected,
            current,
        )
        return False

    except Exception as exc:
        logger.error("Failed to verify update: %s", exc)
        return False


def perform_self_update(
    logger: logging.Logger,
    target_version: str | None = None,
    *,
    channel: str | None = None,
    nightly_sha: str | None = None,
) -> bool:
    """Attempt to update qBitrr in-place for the detected installation type."""
    install_type = get_installation_type()
    resolved_channel = normalize_update_channel(channel)
    nightly = resolved_channel == "nightly"
    logger.debug("Installation type detected: %s (channel=%s)", install_type, resolved_channel)

    if install_type == "binary":
        if nightly:
            logger.error(
                "Nightly channel is not supported for binary installations "
                "(no nightly binary assets are published)."
            )
            return False
        if not target_version:
            logger.error("Binary update requires a target release version")
            return False
        return perform_binary_self_update(logger, target_version)

    if install_type in {"source", "git"}:
        logger.error(
            "Source builds do not support auto-update "
            "(detected .git checkout or QBITRR_SOURCE_BUILD). "
            "Update the working tree manually."
        )
        return False

    if install_type == "docker":
        runtime = get_runtime_overlay_dir()
        if nightly:
            ok = _pip_install(logger, NIGHTLY_PIP_URL, target=runtime)
            if ok and nightly_sha:
                write_nightly_sha(nightly_sha)
                write_overlay_version(f"nightly-{nightly_sha[:7]}")
            if ok:
                _activate_runtime_overlay(runtime)
            return ok
        if not target_version:
            logger.error(
                "Refusing unversioned docker upgrade; a target release version is required"
            )
            return False
        version = target_version[1:] if target_version.startswith("v") else target_version
        ok = _pip_install(logger, f"qBitrr2=={version}", target=runtime)
        if ok:
            write_overlay_version(version)
            _activate_runtime_overlay(runtime)
        return ok

    if install_type == "pip":
        if nightly:
            ok = _pip_install(logger, NIGHTLY_PIP_URL)
            if ok and nightly_sha:
                write_nightly_sha(nightly_sha)
            return ok
        if not target_version:
            logger.error(
                "Refusing unversioned pip upgrade; a target release version is required "
                "(install qBitrr2==<version> only)."
            )
            return False
        version = target_version[1:] if target_version.startswith("v") else target_version
        return _pip_install(logger, f"qBitrr2=={version}")

    logger.error("Unknown installation type: %s", install_type)
    return False
