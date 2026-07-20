import hashlib
import io
import json
import logging
import os
import platform
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from qBitrr.config import FF_PROBE, FF_VERSION, get_ffprobe_auto_update_effective
from qBitrr.logger import run_logs

# Third-party binary host; only HTTPS URLs on these hosts are accepted.
_ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "ffbinaries.com",
        "www.ffbinaries.com",
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)


def _safe_extract_path(base: Path, member: str) -> Path:
    """Resolve zip member under ``base`` without allowing path escape."""
    root = base.resolve()
    candidate = (root / member).resolve()
    candidate.relative_to(root)
    return candidate


class FFprobeDownloader:
    def __init__(self):
        self.api = "https://ffbinaries.com/api/v1/version/latest"
        self.version_file = FF_VERSION
        self.logger = logging.getLogger("qBitrr.FFprobe")
        run_logs(self.logger)
        self.platform = platform.system()
        if self.platform == "Windows":
            self.probe_path = FF_PROBE.with_suffix(".exe")
        else:
            self.probe_path = FF_PROBE

    def get_upstream_version(self) -> dict:
        with requests.Session() as session:
            with session.get(self.api, timeout=(10, 60)) as response:
                if response.status_code != 200:
                    self.logger.warning("Failed to retrieve ffprobe version from API.")
                    return {}
                return response.json()

    def get_current_version(self):
        try:
            with self.version_file.open(mode="r") as file:
                data = json.load(file)
            return data.get("version")
        except Exception:  # If file can't be found or read or parsed
            self.logger.warning("Failed to retrieve current ffprobe version.")
            return ""

    def update(self):
        if not get_ffprobe_auto_update_effective():
            return
        current_version = self.get_current_version()
        upstream_data = self.get_upstream_version()
        upstream_version = upstream_data.get("version")
        if upstream_version is None:
            self.logger.debug(
                "Failed to retrieve ffprobe version from API.'upstream_version' is None"
            )
            return
        probe_file_exists = self.probe_path.exists()
        if current_version == upstream_version and probe_file_exists:
            self.logger.debug("Current FFprobe is up to date.")
            return
        arch_key = self.get_arch()
        urls = upstream_data.get("bin", {}).get(arch_key)
        if urls is None:
            self.logger.debug("Failed to retrieve ffprobe version from API.'urls' is None")
            return
        ffprobe_url = urls.get("ffprobe")
        expected_sha256 = self._extract_checksum(urls, upstream_data)
        self.logger.debug("Downloading newer FFprobe: %s", ffprobe_url)
        self.logger.warning(
            "Downloading third-party FFprobe binary from %s. Prefer a distro/system "
            "ffprobe when available (especially in Docker).",
            ffprobe_url,
        )
        if not self.download_and_extract(ffprobe_url, expected_sha256=expected_sha256):
            return
        self.logger.debug("Updating local version of FFprobe: %s", upstream_version)
        self.version_file.write_text(json.dumps({"version": upstream_version}))
        try:
            os.chmod(self.probe_path, 0o755)
            self.logger.debug("Successfully changed permissions for ffprobe")
        except Exception as e:
            self.logger.debug("Failed to change permissions for ffprobe, %s", e)

    @staticmethod
    def _extract_checksum(urls: dict, upstream_data: dict) -> str | None:
        """Return a SHA-256 hex digest if the upstream payload provides one."""
        for key in ("ffprobe_sha256", "sha256", "checksum"):
            value = urls.get(key) if isinstance(urls, dict) else None
            if isinstance(value, str) and len(value) == 64:
                return value.lower()
        checksums = upstream_data.get("checksums") or upstream_data.get("sha256")
        if isinstance(checksums, dict):
            for key in ("ffprobe", "ffprobe_sha256"):
                value = checksums.get(key)
                if isinstance(value, str) and len(value) == 64:
                    return value.lower()
        return None

    @staticmethod
    def _url_allowed(ffprobe_url: str) -> bool:
        try:
            parsed = urlparse(ffprobe_url)
        except Exception:
            return False
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if host in _ALLOWED_DOWNLOAD_HOSTS:
            return True
        # Allow CDN subdomains under ffbinaries.com
        return host.endswith(".ffbinaries.com")

    def download_and_extract(self, ffprobe_url, expected_sha256: str | None = None) -> bool:
        """Download, optionally verify, extract to a temp dir, then atomically replace."""
        if not ffprobe_url or not self._url_allowed(ffprobe_url):
            self.logger.error(
                "Refusing FFprobe download from disallowed or non-HTTPS URL: %s", ffprobe_url
            )
            return False
        r = requests.get(ffprobe_url, timeout=(10, 300))
        r.raise_for_status()
        content = r.content
        r.close()
        if expected_sha256:
            digest = hashlib.sha256(content).hexdigest()
            if digest != expected_sha256:
                self.logger.error(
                    "FFprobe download checksum mismatch (expected %s, got %s)",
                    expected_sha256,
                    digest,
                )
                return False
        else:
            self.logger.debug(
                "No upstream SHA-256 provided for FFprobe; relying on HTTPS host allowlist only."
            )

        member_name = self.probe_path.name
        dest_dir = FF_PROBE.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if member_name not in z.namelist():
                    matches = [n for n in z.namelist() if n.rstrip("/").endswith(member_name)]
                    if len(matches) != 1:
                        self.logger.error(
                            "FFprobe archive does not contain expected member %s", member_name
                        )
                        return False
                    member_name = matches[0]
                info = z.getinfo(member_name)
                normalized = member_name.replace("\\", "/")
                if info.is_dir() or ".." in normalized.split("/"):
                    self.logger.error("Refusing unsafe zip member path: %s", member_name)
                    return False
                with tempfile.TemporaryDirectory(dir=str(dest_dir)) as tmp:
                    z.extract(member=member_name, path=tmp)
                    extracted = _safe_extract_path(Path(tmp), member_name)
                    if not extracted.is_file():
                        self.logger.error("Extracted FFprobe path is not a file: %s", extracted)
                        return False
                    os.replace(extracted, self.probe_path)
            self.logger.debug("Extracted downloaded FFprobe to: %s", self.probe_path)
            return True
        except Exception:
            self.logger.exception("Failed to extract FFprobe archive")
            return False

    def get_arch(self):
        part1 = None
        is_64bits = sys.maxsize > 2**32
        part2 = "64" if is_64bits else "32"
        if self.platform == "Windows":
            part1 = "windows-"
        elif self.platform == "Linux":
            part1 = "linux-"
            machine = platform.machine()
            if machine == "armv6l":
                part2 = "armhf"
            elif ("arm" in machine and is_64bits) or machine == "aarch64":
                part2 = "arm64"
            # Else just 32/64, Not armel - because just no
        elif self.platform == "Darwin":
            part1 = "osx-"
            part2 = "64"
        if part1 is None:
            raise RuntimeError(
                "You are running in an unsupported platform, "
                "if you expect this to be supported please open an issue on GitHub "
                "https://github.com/Feramance/qBitrr."
            )

        return part1 + part2
