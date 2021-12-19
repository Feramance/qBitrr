import io
import json
import logging
import platform
import sys
import zipfile

import requests

from qBitrr.config import FF_PROBE, FF_VERSION, FFPROBE_AUTO_UPDATE
from qBitrr.logger import run_logs


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
            with session.get(self.api) as response:
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
        if not FFPROBE_AUTO_UPDATE:
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
        self.logger.debug("Downloading newer FFprobe: %s", ffprobe_url)
        self.download_and_extract(ffprobe_url)
        self.logger.debug("Updating local version of FFprobe: %s", upstream_version)
        self.version_file.write_text(json.dumps({"version": upstream_version}))

    def download_and_extract(self, ffprobe_url):
        r = requests.get(ffprobe_url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        self.logger.debug("Extracting downloaded FFprobe to: %s", FF_PROBE.parent)
        z.extract(member=self.probe_path.name, path=FF_PROBE.parent)

    def get_arch(self):
        part1 = None
        is_64bits = sys.maxsize > 2 ** 32
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
                "https://github.com/Drapersniper/Qbitrr."
            )

        return part1 + part2
