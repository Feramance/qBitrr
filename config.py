import configparser
import pathlib
import re

CONFIG = configparser.ConfigParser(
    converters={
        "list": lambda x: [i.strip() for i in x.split(",")],
        "int": lambda x: int(x),
        "float": lambda x: float(x),
        "boolean": lambda x: x.lower().strip() in {"1", "true", "on", "enabled"},
        "upper": lambda x: str(x).upper().strip(),
    }
)
CONFIG.read("./config.ini")
APPDATA_FOLDER = pathlib.Path().home().joinpath(".config", "qBitManager")
APPDATA_FOLDER.mkdir(parents=True, exist_ok=True)

# Settings Config Values
CONSOLE_LOGGING_LEVEL_STRING = CONFIG.getupper("Logging", "ConsoleLevel", fallback="NOTICE")
COMPLETED_DOWNLOAD_FOLDER = CONFIG.get("Settings", "CompletedDownloadFolder")
CASE_SENSITIVE_MATCHES = CONFIG.getboolean("Settings", "CaseSensitiveMatches")
FOLDER_EXCLUSION_REGEX = CONFIG.getlist("Settings", "FolderExclusionRegex")
FILE_NAME_EXCLUSION_REGEX = CONFIG.getlist("Settings", "FileNameExclusionRegex")
FILE_EXTENSION_ALLOWLIST = CONFIG.getlist("Settings", "FileExtensionAllowlist")
NO_INTERNET_SLEEP_TIMER = CONFIG.getint("Settings", "NoInternetSleepTimer", fallback=60)
LOOP_SLEEP_TIMER = CONFIG.getint("Settings", "LoopSleepTimer", fallback=5)
AUTO_DELETE = CONFIG.getboolean("Settings", "AutoDelete", fallback=False)
IGNORE_TORRENTS_YOUNGER_THAN = CONFIG.getint("Settings", "IgnoreTorrentsYoungerThan", fallback=600)
MAXIMUM_ETA = CONFIG.getint("Settings", "MaximumETA", fallback=86400)
FAILED_CATEGORY = CONFIG.get("Settings", "FailedCategory", fallback="failed")
RECHECK_CATEGORY = CONFIG.get("Settings", "RecheckCategory", fallback="recheck")
MAXIMUM_DELETABLE_PERCENTAGE = CONFIG.getfloat(
    "Settings", "MaximumDeletablePercentage", fallback=0.95
)
PING_URLS = CONFIG.getlist(
    "Settings",
    "PingURL",
    fallback=[
        "https://1.0.0.1",
        "https://8.8.8.8",
        "https://1.1.1.1",
        "https://8.8.4.4",
        "https://139.130.4.5",
    ],
)

if CASE_SENSITIVE_MATCHES:
    FOLDER_EXCLUSION_REGEX_RE = re.compile("|".join(FOLDER_EXCLUSION_REGEX), re.DOTALL)
    FILE_NAME_EXCLUSION_REGEX_RE = re.compile("|".join(FILE_NAME_EXCLUSION_REGEX), re.DOTALL)
else:
    FOLDER_EXCLUSION_REGEX_RE = re.compile(
        "|".join(FOLDER_EXCLUSION_REGEX), re.IGNORECASE | re.DOTALL
    )
    FILE_NAME_EXCLUSION_REGEX_RE = re.compile(
        "|".join(FILE_NAME_EXCLUSION_REGEX), re.IGNORECASE | re.DOTALL
    )
