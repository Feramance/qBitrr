from datetime import datetime
from typing import Any

from toml_config.core import Config

default = {
    "Managed": True,
    "URI": "CHANGE_ME",
    "APIKey": "CHANGE_ME",
    "ReSearch": True,
    "importMode": "Move",
    "RssSyncTimer": 10,
    "RefreshDownloadsTimer": 1,
    "Torrent": {
        "AutoDelete": True,
        "CaseSensitiveMatches": False,
        "DoNotRemoveSlow": False,
        "IgnoreTorrentsYoungerThan": 180,
        "MaximumETA": 18000,
        "MaximumDeletablePercentage": 0.99,
        "FolderExclusionRegex": [
            r"\bextras?\b",
            r"\bfeaturettes?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
            r"\bspecials?\b",
            r"\bova\b",
            r"\bnc(ed|op)?(\\d+)?\b",
        ],
        "FileNameExclusionRegex": [
            r"\bncop\\d+?\b",
            r"\bnced\\d+?\b",
            r"\bsample\b",
            r"brarbg.com\b",
            r"\btrailer\b",
            r"music video",
            r"comandotorrents.com",
        ],
        "FileExtensionAllowlist": [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"],
        "SeedingMode": {
            "Enabled": False,
            "add_tags": ["Seeding Allowed"],
            "DownloadRateLimitPerTorrent": None,
            "UploadRateLimitPerTorrent": None,
            "MaxUploadRatio": None,
            "MaxSeedingTime": None,
            "Trackers": [
                {
                    "Name": "Rarbg",
                    "url": "udp://9.rarbg.com:2810/announce",
                    "add_tags": [
                        "rarbg",
                    ],
                    "DownloadRateLimit": None,
                    "MaxUploadRatio": None,
                    "MaxSeedingTime": None,
                    "UploadRateLimit": None,
                    "SuperSeedMode": False,
                },
                {
                    "Name": "Nyaa",
                    "url": "http://nyaa.tracker.wf:7777/announce",
                    "add_tags": ["anime", "Nyaa"],
                    "DownloadRateLimit": None,
                    "MaxUploadRatio": None,
                    "MaxSeedingTime": None,
                    "UploadRateLimit": None,
                    "SuperSeedMode": False,
                },
            ],
        },
    },
    "EntrySearch": {
        "SearchMissing": False,
        "PrioritizeTodaysReleases": True,
        "AlsoSearchSpecials": False,
        "SearchLimit": 5,
        "DatabaseFile": "CHANGE_ME/radarr.db",
        "SearchByYear": True,
        "StartYear": datetime.now().year,
        "LastYear": 1990,
        "SearchInReverse": False,
        "DoUpgradeSearch": False,
        "QualityUnmetSearch": False,
        "SearchRequestsEvery": 1800,
        "Ombi": {
            "SearchOmbiRequests": False,
            "OmbiURI": "http://localhost:5000",
            "OmbiAPIKey": "CHANGE_ME",
            "ApprovedOnly": True,
        },
        "Overseerr": {
            "SearchOverseerrRequests": False,
            "OverseerrURI": "http://localhost:5000",
            "OverseerrAPIKey": "CHANGE_ME",
            "ApprovedOnly": True,
        },
    },
}


data = {
    "Radarr-1080p": {**default, **{"Category": "radarr-1080"}},
    "Radarr-4k": {**default, **{"Category": "radarr-4k"}},
    "Sonarr-Anime": {**default, **{"Category": "sonarr-anime"}},
    "Sonarr-TV": {**default, **{"Category": "sonarr-tv"}},
    "QBit": {"Host": "localhost", "Port": "8105", "UserName": None, "Password": None},
    "Settings": {
        "ConsoleLevel": "INFO",
        "CompletedDownloadFolder": "CHANGE_ME",
        "NoInternetSleepTimer": 15,
        "LoopSleepTimer": 5,
        "FailedCategory": "failed",
        "RecheckCategory": "recheck",
        "IgnoreTorrentsYoungerThan": 180,
        "FFprobeAutoUpdate": True,
        "PingURLS": ["one.one.one.one", "dns.google"],
    },
}

data["Sonarr-TV"]["EntrySearch"]["SearchBySeries"] = True
data["Sonarr-TV"]["EntrySearch"]["DatabaseFile"] = "CHANGE_ME/sonarr.db"

data["Sonarr-Anime"]["EntrySearch"]["SearchBySeries"] = True
data["Sonarr-Anime"]["EntrySearch"]["DatabaseFile"] = "CHANGE_ME/sonarr.db"
data["Sonarr-Anime"]["Torrent"]["FolderExclusionRegex"] = [
    r"\bextras?\b",
    r"\bfeaturettes?\b",
    r"\bsamples?\b",
    r"\bscreens?\b",
    r"\bnc(ed|op)?(\\d+)?\b",
]


class MyConfig(Config):
    def get_section(self, section_name: str) -> Config:
        """
        This method makes the section active.
        :param section_name: str

        """

        if self.state:
            section = self.config.get(
                section_name,
                None if not isinstance(self.section, dict) else self.section.get(section_name),
            )
            if isinstance(section, dict):
                self.active_section = section_name
                self.section = section
            else:
                raise ValueError(
                    f"{section_name} does not exist, valid sections are {self.config.keys()}"
                )

        return self

    def get(self, param: str, fallback: Any = None):
        if self.state:
            if (value := self.section.get(param, ...)) is not ...:
                self.value = value
            else:
                self.value = fallback
        return self.value


def _write_config_file():
    pass

    conf = MyConfig("./config.example.toml")
    conf.config = data
    conf.save()
