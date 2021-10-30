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
logger = logbook.Logger("Misc")
logger.handlers.append(logbook.StderrHandler(level=CONSOLE_LOGGING_LEVEL))

logger.info("Ping URLs:  {PingURL}", PingURL=PING_URLS)
logger.info(
    "Script Config:  CaseSensitiveMatches={CaseSensitiveMatches}",
    CaseSensitiveMatches=CASE_SENSITIVE_MATCHES,
)
logger.info(
    "Script Config:  FolderExclusionRegex={FolderExclusionRegex}",
    FolderExclusionRegex=FOLDER_EXCLUSION_REGEX,
)
logger.info(
    "Script Config:  FileNameExclusionRegex={FileNameExclusionRegex}",
    FileNameExclusionRegex=FILE_NAME_EXCLUSION_REGEX,
)
logger.info(
    "Script Config:  FileExtensionAllowlist={FileExtensionAllowlist}",
    FileExtensionAllowlist=FILE_EXTENSION_ALLOWLIST,
)
logger.info("Script Config:  AutoDelete={AutoDelete}", AutoDelete=AUTO_DELETE)
logger.info("Script Config:  LoopSleepTimer={LoopSleepTimer}", LoopSleepTimer=LOOP_SLEEP_TIMER)
logger.info(
    "Script Config:  NoInternetSleepTimer={NoInternetSleepTimer}",
    NoInternetSleepTimer=NO_INTERNET_SLEEP_TIMER,
)
logger.info(
    "Script Config:  IgnoreTorrentsYoungerThan={IgnoreTorrentsYoungerThan}",
    IgnoreTorrentsYoungerThan=IGNORE_TORRENTS_YOUNGER_THAN,
)
logger.info("Script Config:  MaximumETA={MaximumETA}", MaximumETA=MAXIMUM_ETA)
logger.info(
    "Script Config:  MaximumDeletablePercentage={MaximumDeletablePercentage}",
    MaximumDeletablePercentage=MAXIMUM_DELETABLE_PERCENTAGE,
)
logger.info("Script Config:  FailedCategory={FailedCategory}", FailedCategory=FAILED_CATEGORY)
logger.info("Script Config:  RecheckCategory={RecheckCategory}", RecheckCategory=RECHECK_CATEGORY)
logger.info("Script Config:  CompletedDownloadFolder={Folder}", Folder=COMPLETED_DOWNLOAD_FOLDER)
