from __future__ import annotations

import logging
import pathlib
import time
from logging import Logger

import coloredlogs

from qBitrr.config import (
    AUTO_PAUSE_RESUME,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    CONSOLE_LOGGING_LEVEL_STRING,
    COPIED_TO_NEW_DIR,
    ENABLE_LOGS,
    FAILED_CATEGORY,
    FREE_SPACE,
    HOME_PATH,
    IGNORE_TORRENTS_YOUNGER_THAN,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    PING_URLS,
    RECHECK_CATEGORY,
    SEARCH_LOOP_DELAY,
    TAGLESS,
)

__all__ = ("run_logs",)

TRACE = 5
VERBOSE = 7
NOTICE = 23
HNOTICE = 24
SUCCESS = 25


class VerboseLogger(Logger):
    def _init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.name.startswith("qBitrr"):
            self.set_config_level()

    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, message, args, **kwargs)

    def hnotice(self, message, *args, **kwargs):
        if self.isEnabledFor(HNOTICE):
            self._log(HNOTICE, message, args, **kwargs)

    def notice(self, message, *args, **kwargs):
        if self.isEnabledFor(NOTICE):
            self._log(NOTICE, message, args, **kwargs)

    def verbose(self, message, *args, **kwargs):
        if self.isEnabledFor(VERBOSE):
            self._log(VERBOSE, message, args, **kwargs)

    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    def set_config_level(self):
        self.setLevel(CONSOLE_LOGGING_LEVEL_STRING)


logging.addLevelName(SUCCESS, "SUCCESS")
logging.addLevelName(HNOTICE, "HNOTICE")
logging.addLevelName(NOTICE, "NOTICE")
logging.addLevelName(VERBOSE, "VERBOSE")
logging.addLevelName(TRACE, "TRACE")
logging.setLoggerClass(VerboseLogger)


def getLogger(name: str | None = None):
    return VerboseLogger.manager.getLogger(name) if name else logging.root


logging.getLogger = getLogger


logger = logging.getLogger("qBitrr.Misc")


HAS_RUN = False


def run_logs(logger: Logger, _name: str = None) -> None:
    global HAS_RUN
    try:
        configkeys = {f"qBitrr.{i}" for i in CONFIG.sections()}
        key_length = max(len(max(configkeys, key=len)), 10)
    except BaseException:
        key_length = 10
    coloredlogs.install(
        logger=logger,
        level=logging._nameToLevel.get(CONSOLE_LOGGING_LEVEL_STRING),
        fmt="[%(asctime)-15s] [pid:%(process)8d][tid:%(thread)8d] "
        f"%(levelname)-8s: %(name)-{key_length}s: %(message)s",
        level_styles={
            "trace": {"color": "black", "bold": True},
            "debug": {"color": "magenta", "bold": True},
            "verbose": {"color": "blue", "bold": True},
            "info": {"color": "white"},
            "notice": {"color": "cyan"},
            "hnotice": {"color": "cyan", "bold": True},
            "warning": {"color": "yellow", "bold": True},
            "success": {"color": "green", "bold": True},
            "error": {"color": "red"},
            "critical": {"color": "red", "bold": True},
        },
        field_styles={
            "asctime": {"color": "green"},
            "process": {"color": "magenta"},
            "levelname": {"color": "red", "bold": True},
            "name": {"color": "blue", "bold": True},
            "thread": {"color": "cyan"},
        },
        reconfigure=True,
    )
    if ENABLE_LOGS and _name:
        logs_folder = HOME_PATH.joinpath("logs")
        logs_folder.mkdir(parents=True, exist_ok=True)
        logs_folder.chmod(mode=0o777)
        logfile = logs_folder.joinpath(_name + ".log")
        if pathlib.Path(logfile).is_file():
            logold = logs_folder.joinpath(_name + ".log.old")
            if pathlib.Path(logold).exists():
                logold.unlink()
            logfile.rename(logold)
        fh = logging.FileHandler(logfile)
        fh.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)-15s] " f"%(levelname)-8s: %(name)-{key_length}s: %(message)s"
            )
        )
        logger.addHandler(fh)
    if HAS_RUN is False:
        HAS_RUN = True
        log_debugs(logger)


def log_debugs(logger):
    logger.debug("Log Level: %s", CONSOLE_LOGGING_LEVEL_STRING)
    logger.debug("Ping URLs:  %s", PING_URLS)
    logger.debug("Script Config:  Logging=%s", ENABLE_LOGS)
    logger.debug("Script Config:  FailedCategory=%s", FAILED_CATEGORY)
    logger.debug("Script Config:  RecheckCategory=%s", RECHECK_CATEGORY)
    logger.debug("Script Config:  Tagless=%s", TAGLESS)
    logger.debug("Script Config:  CompletedDownloadFolder=%s", COMPLETED_DOWNLOAD_FOLDER)
    logger.debug("Script Config:  FreeSpace=%s", FREE_SPACE)
    logger.debug("Script Config:  LoopSleepTimer=%s", LOOP_SLEEP_TIMER)
    logger.debug("Script Config:  SearchLoopDelay=%s", SEARCH_LOOP_DELAY)
    logger.debug("Script Config:  AutoPauseResume=%s", AUTO_PAUSE_RESUME)
    logger.debug("Script Config:  NoInternetSleepTimer=%s", NO_INTERNET_SLEEP_TIMER)
    logger.debug("Script Config:  IgnoreTorrentsYoungerThan=%s", IGNORE_TORRENTS_YOUNGER_THAN)


if COPIED_TO_NEW_DIR is False and not HOME_PATH.joinpath("config.toml").exists():
    logger.warning(
        "Config.toml should exist in '%s', in a future update this will be a requirement.",
        HOME_PATH,
    )
    time.sleep(5)
if COPIED_TO_NEW_DIR:
    logger.warning("Config.toml new location is %s", HOME_PATH)
    time.sleep(5)
run_logs(logger)
