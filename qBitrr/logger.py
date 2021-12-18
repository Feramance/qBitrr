from __future__ import annotations

import contextlib
import logging
import time
from logging import Logger
from typing import Iterable

import coloredlogs

from qBitrr.config import (
    APPDATA_FOLDER,
    COMPLETED_DOWNLOAD_FOLDER,
    FAILED_CATEGORY,
    IGNORE_TORRENTS_YOUNGER_THAN,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    PING_URLS,
    RECHECK_CATEGORY,
)

__all__ = ()


def addLoggingLevel(
    levelName, levelNum, methodName=None, logger=None
):  # Credits goes to Mad Physicist https://stackoverflow.com/a/35804945
    from qBitrr.config import CONSOLE_LOGGING_LEVEL_STRING

    if not methodName:
        methodName = levelName.lower()

    # if hasattr(logging, levelName):
    #     raise AttributeError(f"{levelName} already defined in logging module")
    # if hasattr(logging, methodName):
    #     raise AttributeError(f"{methodName} already defined in logging module")
    # if hasattr(logging.getLoggerClass(), methodName):
    #     raise AttributeError(f"{methodName} already defined in logger class")

    if logger:
        if hasattr(logger, methodName):
            raise AttributeError(f"{methodName} already defined in logging module")
        if hasattr(logger, methodName):
            raise AttributeError(f"{methodName} already defined in logger class")

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)

    if logger:
        setattr(logger, levelName, levelNum)
        logger.setLevel(CONSOLE_LOGGING_LEVEL_STRING)


def _update_config():
    global APPDATA_FOLDER, CONFIG, COMPLETED_DOWNLOAD_FOLDER, CONSOLE_LOGGING_LEVEL_STRING, FAILED_CATEGORY, IGNORE_TORRENTS_YOUNGER_THAN, LOOP_SLEEP_TIMER, NO_INTERNET_SLEEP_TIMER, PING_URLS, RECHECK_CATEGORY
    from qBitrr.config import (
        APPDATA_FOLDER,
        COMPLETED_DOWNLOAD_FOLDER,
        CONFIG,
        CONSOLE_LOGGING_LEVEL_STRING,
        FAILED_CATEGORY,
        IGNORE_TORRENTS_YOUNGER_THAN,
        LOOP_SLEEP_TIMER,
        NO_INTERNET_SLEEP_TIMER,
        PING_URLS,
        RECHECK_CATEGORY,
    )


HAS_RUN = False


def run_logs(logger: Logger, configkeys: Iterable | None = None) -> None:
    global HAS_RUN
    with contextlib.suppress(Exception):
        addLoggingLevel("SUCCESS", logging.INFO + 5, "success", logger=logger)
    with contextlib.suppress(Exception):
        addLoggingLevel("HNOTICE", logging.INFO + 4, "hnotice", logger=logger)
    with contextlib.suppress(Exception):
        addLoggingLevel("NOTICE", logging.INFO + 3, "notice", logger=logger)
    with contextlib.suppress(Exception):
        addLoggingLevel("TRACE", logging.DEBUG - 5, "trace", logger=logger)
    _update_config()
    from qBitrr.config import CONSOLE_LOGGING_LEVEL_STRING

    logger.setLevel(CONSOLE_LOGGING_LEVEL_STRING)
    try:
        if configkeys is None:
            from qBitrr.config import CONFIG

            configkeys = CONFIG.sections()
        key_length = max(len(max(configkeys, key=len)), 10)
    except BaseException:
        key_length = 10
    coloredlogs.install(
        level=logging._levelToName.get(CONSOLE_LOGGING_LEVEL_STRING),
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


def dynamic_update(configkeys: list | None = None) -> str:
    _update_config()
    global log
    from qBitrr.config import CONSOLE_LOGGING_LEVEL_STRING, COPIED_TO_NEW_DIR

    logger = logging.getLogger("Misc")
    if COPIED_TO_NEW_DIR is not None and not APPDATA_FOLDER.joinpath("config.toml").exists():
        logger.warning(
            "Config.toml should exist in '%s', in a future update this will be a requirement.",
            APPDATA_FOLDER,
        )
        time.sleep(5)
    if COPIED_TO_NEW_DIR:
        logger.warning("Config.toml new location is %s", APPDATA_FOLDER)
        time.sleep(5)
    run_logs(logger, configkeys)
    logger.setLevel(CONSOLE_LOGGING_LEVEL_STRING)
    return CONSOLE_LOGGING_LEVEL_STRING
