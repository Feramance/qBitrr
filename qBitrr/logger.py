from __future__ import annotations

import logging
import time
from logging import Logger

import coloredlogs

from qBitrr.config import (
    APPDATA_FOLDER,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    CONSOLE_LOGGING_LEVEL_STRING,
    COPIED_TO_NEW_DIR,
    FAILED_CATEGORY,
    IGNORE_TORRENTS_YOUNGER_THAN,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    PING_URLS,
    RECHECK_CATEGORY,
)

__all__ = ()


class VerboseLogger(Logger):
    def _init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_config_level()

    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(25):
            self._log(25, message, args, **kwargs)

    def hnotice(self, message, *args, **kwargs):
        if self.isEnabledFor(24):
            self._log(24, message, args, **kwargs)

    def notice(self, message, *args, **kwargs):
        if self.isEnabledFor(23):
            self._log(23, message, args, **kwargs)

    def verbose(self, message, *args, **kwargs):
        if self.isEnabledFor(5):
            self._log(7, message, args, **kwargs)

    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(5):
            self._log(5, message, args, **kwargs)

    def set_config_level(self):
        self.setLevel(CONSOLE_LOGGING_LEVEL_STRING)


logging.addLevelName(25, "SUCCESS")
logging.addLevelName(24, "HNOTICE")
logging.addLevelName(23, "NOTICE")
logging.addLevelName(7, "VERBOSE")
logging.addLevelName(5, "TRACE")
logging.setLoggerClass(VerboseLogger)


def getLogger(name: str | None = None) -> VerboseLogger:
    if name:
        return VerboseLogger.manager.getLogger(name)
    else:
        return logging.root


logging.getLogger = getLogger


logger = logging.getLogger("Misc")


HAS_RUN = False


def run_logs(logger: Logger) -> None:
    global HAS_RUN
    try:
        configkeys = CONFIG.sections()
        key_length = max(len(max(configkeys, key=len)), 10)
    except BaseException:
        key_length = 10
    coloredlogs.install(
        logger=logger,
        level=logging._nameToLevel.get(CONSOLE_LOGGING_LEVEL_STRING),
        fmt="[%(asctime)-15s] [pid:%(process)8d][tid:%(thread)8d] "
        f"%(levelname)-8s: %(name)-{key_length}s: %(message)s",
        level_styles=dict(
            trace=dict(color="black", bold=True),
            debug=dict(color="magenta", bold=True),
            verbose=dict(color="blue", bold=True),
            info=dict(color="white"),
            notice=dict(color="cyan"),
            hnotice=dict(color="cyan", bold=True),
            warning=dict(color="yellow", bold=True),
            success=dict(color="green", bold=True),
            error=dict(color="red"),
            critical=dict(color="red", bold=True),
        ),
        field_styles=dict(
            asctime=dict(color="green"),
            process=dict(color="magenta"),
            levelname=dict(color="red", bold=True),
            name=dict(color="blue", bold=True),
            thread=dict(color="cyan"),
        ),
        reconfigure=True,
    )
    if HAS_RUN is False:
        logger.debug("Log Level: %s", CONSOLE_LOGGING_LEVEL_STRING)
        logger.debug("Ping URLs:  %s", PING_URLS)
        logger.debug("Script Config:  FailedCategory=%s", FAILED_CATEGORY)
        logger.debug("Script Config:  RecheckCategory=%s", RECHECK_CATEGORY)
        logger.debug("Script Config:  CompletedDownloadFolder=%s", COMPLETED_DOWNLOAD_FOLDER)
        logger.debug("Script Config:  LoopSleepTimer=%s", LOOP_SLEEP_TIMER)
        logger.debug(
            "Script Config:  NoInternetSleepTimer=%s",
            NO_INTERNET_SLEEP_TIMER,
        )
        logger.debug(
            "Script Config:  IgnoreTorrentsYoungerThan=%s",
            IGNORE_TORRENTS_YOUNGER_THAN,
        )
        HAS_RUN = True


if COPIED_TO_NEW_DIR is not None and not APPDATA_FOLDER.joinpath("config.toml").exists():
    logger.warning(
        "Config.toml should exist in '%s', in a future update this will be a requirement.",
        APPDATA_FOLDER,
    )
    time.sleep(5)
if COPIED_TO_NEW_DIR:
    logger.warning("Config.toml new location is %s", APPDATA_FOLDER)
    time.sleep(5)
run_logs(logger)
