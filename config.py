import configparser
import pathlib

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
FAILED_CATEGORY = CONFIG.get("Settings", "FailedCategory", fallback="failed")
RECHECK_CATEGORY = CONFIG.get("Settings", "RecheckCategory", fallback="recheck")
CONSOLE_LOGGING_LEVEL_STRING = CONFIG.getupper("Settings", "ConsoleLevel", fallback="NOTICE")
COMPLETED_DOWNLOAD_FOLDER = CONFIG.get("Settings", "CompletedDownloadFolder")
NO_INTERNET_SLEEP_TIMER = CONFIG.getint("Settings", "NoInternetSleepTimer", fallback=60)
LOOP_SLEEP_TIMER = CONFIG.getint("Settings", "LoopSleepTimer", fallback=5)
PING_URLS = CONFIG.getlist(
    "Settings",
    "PingURL",
    fallback=["https://1.0.0.1", "https://8.8.8.8", "https://1.1.1.1", "https://8.8.4.4"],
)
IGNORE_TORRENTS_YOUNGER_THAN = CONFIG.getint("Settings", "IgnoreTorrentsYoungerThan", fallback=600)
