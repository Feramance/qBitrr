import os
import sys
import time

import logbook
from logbook import StreamHandler
from logbook.more import ColorizingStreamHandlerMixin

from .config import *

__all__ = ()
logging_map = {
    "CRITICAL": logbook.CRITICAL,
    "ERROR": logbook.ERROR,
    "WARNING": logbook.WARNING,
    "NOTICE": logbook.NOTICE,
    "INFO": logbook.INFO,
    "DEBUG": logbook.DEBUG,
    "TRACE": logbook.TRACE,
}


def update_logbook():
    _level_names = {
        17: "HNOTICE",
        16: "SUCCESS",
        logbook.CRITICAL: "CRITICAL",
        logbook.ERROR: "ERROR",
        logbook.WARNING: "WARNING",
        logbook.NOTICE: "NOTICE",
        logbook.INFO: "INFO",
        logbook.DEBUG: "DEBUG",
        logbook.TRACE: "TRACE",
        logbook.NOTSET: "NOTSET",
    }
    _reverse_level_names = dict((v, k) for (k, v) in dict.items(_level_names))
    setattr(logbook, "_level_names", _level_names)
    setattr(logbook, "_reverse_level_names", _reverse_level_names)
    setattr(logbook.base, "_level_names", _level_names)
    setattr(logbook.base, "_reverse_level_names", _reverse_level_names)


update_logbook()


class CustomColorizedStdoutHandler(ColorizingStreamHandlerMixin, StreamHandler):
    def __init__(self, *args, **kwargs):
        self.imported_colorama = False
        StreamHandler.__init__(self, *args, **kwargs)
        try:
            import colorama

            self.imported_colorama = True
        except ImportError:
            pass
        else:
            colorama.init()

    def should_colorize(self, record):
        """Returns `True` if colorizing should be applied to this
        record.  The default implementation returns `True` if the
        stream is a tty. If we are executing on Windows, colorama must be
        installed.
        """
        # The default implementation of this is awfully inefficient.
        # As reimport on every single format() call
        if os.name == "nt" and not self.imported_colorama:
            try:
                import colorama

                self.imported_colorama = True
            except ImportError:
                return False
        if self._use_color is not None:
            return self._use_color
        isatty = getattr(self.stream, "isatty", None)
        return isatty and isatty()

    def get_color(self, record):
        if record.level >= 17:
            return "yellow"
        elif record.level >= 16:
            return "darkgreen"
        elif record.level >= logbook.CRITICAL:
            return "darkred"
        elif record.level >= logbook.ERROR:
            return "red"
        elif record.level >= logbook.WARNING:
            return "darkyellow"
        elif record.level >= logbook.NOTICE:
            return "darkteal"
        elif record.level >= logbook.INFO:
            return "white"
        elif record.level >= logbook.DEBUG:
            return "fuchsia"
        elif record.level >= logbook.TRACE:
            return "darkgray"
        return "lightgray"


CONSOLE_LOGGING_LEVEL = logging_map.get(CONSOLE_LOGGING_LEVEL_STRING)
log = CustomColorizedStdoutHandler(
    sys.stdout,
    level=CONSOLE_LOGGING_LEVEL,
    format_string="[{record.time:%Y-%m-%d %H:%M:%S.%f%z}] [{record.thread}] {record.level_name}: {record.channel}: {record.message}",
)
log.push_application()
logger = logbook.Logger("Misc")
HAS_RUN = False


def run_logs():
    global HAS_RUN
    logger.debug("Ping URLs:  {PingURL}", PingURL=PING_URLS)
    logger.debug("Script Config:  FailedCategory={FailedCategory}", FailedCategory=FAILED_CATEGORY)
    logger.debug(
        "Script Config:  RecheckCategory={RecheckCategory}", RecheckCategory=RECHECK_CATEGORY
    )
    logger.debug(
        "Script Config:  CompletedDownloadFolder={Folder}", Folder=COMPLETED_DOWNLOAD_FOLDER
    )
    logger.debug(
        "Script Config:  LoopSleepTimer={LoopSleepTimer}", LoopSleepTimer=LOOP_SLEEP_TIMER
    )
    logger.debug(
        "Script Config:  NoInternetSleepTimer={NoInternetSleepTimer}",
        NoInternetSleepTimer=NO_INTERNET_SLEEP_TIMER,
    )
    logger.debug(
        "Script Config:  IgnoreTorrentsYoungerThan={IgnoreTorrentsYoungerThan}",
        IgnoreTorrentsYoungerThan=IGNORE_TORRENTS_YOUNGER_THAN,
    )
    HAS_RUN = True


if not HAS_RUN:
    if not APPDATA_FOLDER.joinpath("config.ini").exists():
        logbook.warning(
            "Config.ini should exist in '{APPDATA_FOLDER}', in a future update this will be a requirement.",
            APPDATA_FOLDER=APPDATA_FOLDER,
        )
        time.sleep(5)
    if COPIED_TO_NEW_DIR:
        logbook.warning(
            "Config.ini new location is {APPDATA_FOLDER}", APPDATA_FOLDER=APPDATA_FOLDER
        )
        time.sleep(5)
    run_logs()
