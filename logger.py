import sys

import logbook

from config import *

logging_map = {
    "CRITICAL": logbook.CRITICAL,
    "ERROR": logbook.ERROR,
    "WARNING": logbook.WARNING,
    "NOTICE": logbook.NOTICE,
    "INFO": logbook.INFO,
    "DEBUG": logbook.DEBUG,
    "TRACE": logbook.TRACE,
}
CONSOLE_LOGGING_LEVEL = logging_map.get(CONSOLE_LOGGING_LEVEL_STRING)
logbook.StreamHandler(sys.stdout, level=CONSOLE_LOGGING_LEVEL).push_application()
logger = logbook.Logger("Misc")
logger.info("Ping URLs:  {PingURL}", PingURL=PING_URLS)
logger.info("Script Config:  FailedCategory={FailedCategory}", FailedCategory=FAILED_CATEGORY)
logger.info("Script Config:  RecheckCategory={RecheckCategory}", RecheckCategory=RECHECK_CATEGORY)
logger.info("Script Config:  CompletedDownloadFolder={Folder}", Folder=COMPLETED_DOWNLOAD_FOLDER)
logger.info("Script Config:  LoopSleepTimer={LoopSleepTimer}", LoopSleepTimer=LOOP_SLEEP_TIMER)
logger.info(
    "Script Config:  NoInternetSleepTimer={NoInternetSleepTimer}",
    NoInternetSleepTimer=NO_INTERNET_SLEEP_TIMER,
)
logger.info(
    "Script Config:  IgnoreTorrentsYoungerThan={IgnoreTorrentsYoungerThan}",
    IgnoreTorrentsYoungerThan=IGNORE_TORRENTS_YOUNGER_THAN,
)
