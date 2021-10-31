import time
from datetime import timedelta
from typing import NoReturn

import qbittorrentapi
import requests

from qbittorrentapi import (
    APINames,
    TorrentDictionary,
    TorrentStates,
    login_required,
    response_text,
)

from arss import ArrManager
from errors import DelayLoopException, NoConnectionrException
from logger import *
from config import (
    CONFIG,
    FAILED_CATEGORY,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    RECHECK_CATEGORY,
)
from utils import has_internet

logger = logbook.Logger("qBitManager")

# QBitTorrent Config Values
qBit_Host = CONFIG.get("QBit", "Host", fallback="localhost")
qBit_Port = CONFIG.getint("QBit", "Port")
qBit_UserName = CONFIG.get("QBit", "UserName")
qBit_Password = CONFIG.get("QBit", "Password", fallback=None)
logger.debug(
    "QBitTorrent Config: Host: {qBit_Host}, Port: {qBit_Port}, Username: {qBit_UserName}, "
    "Password: {qBit_Password}",
    qBit_Host=qBit_Host,
    qBit_Port=qBit_Port,
    qBit_UserName=qBit_UserName,
    qBit_Password=qBit_Password,
)


class qBitManager:
    def __init__(self):
        self.client = qbittorrentapi.Client(
            host=qBit_Host,
            port=qBit_Port,
            username=qBit_UserName,
            password=qBit_Password,
            SIMPLE_RESPONSES=False,
        )
        self.arr_manager = ArrManager.build_from_config(self)
        self.logger = logger
        self.cache = dict()
        self.name_cache = dict()
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.

    @response_text(str)
    @login_required
    def app_version(self, **kwargs):
        """
        Retrieve application version

        :return: string
        """
        return self.client._get(
            _name=APINames.Application,
            _method="version",
            _retries=0,
            _retry_backoff_factor=0,
            **kwargs,
        )

    @property
    def is_alive(self) -> bool:
        try:
            self.client.app_version()
            self.logger.trace(
                "Successfully connected to {url}:{port}", url=qBit_Host, port=qBit_Port
            )
            return True
        except requests.RequestException:

            self.logger.warning("Could not connect to {url}:{port}", url=qBit_Host, port=qBit_Port)
        self.should_delay_torrent_scan = True
        return False

    @staticmethod
    def is_ignored_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.FORCED_UPLOAD,
            TorrentStates.CHECKING_UPLOAD,
            TorrentStates.CHECKING_DOWNLOAD,
            TorrentStates.CHECKING_RESUME_DATA,
            TorrentStates.ALLOCATING,
            TorrentStates.MOVING,
        )

    @staticmethod
    def is_uploading_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_complete_state(torrent: TorrentDictionary):
        """Returns True if the State is categorized as Complete."""
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_downloading_state(torrent: TorrentDictionary):
        """Returns True if the State is categorized as Downloading."""
        return torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.PAUSED_DOWNLOAD,
        )

    def process_torrents(self) -> None:
        if has_internet() is False:
            self.should_delay_torrent_scan = True
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
        if self.should_delay_torrent_scan:
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
        for key, arr in self.arr_manager.managed_objects.items():
            try:
                if key not in self.arr_manager.special_categories:
                    arr.api_calls()
                    arr.refresh_download_queue()
                time_now = time.time()

                torrents = self.client.torrents.info.all(
                    category=arr.category, sort="added_on", reverse=False
                )
                for torrent in torrents:
                    if torrent.category != RECHECK_CATEGORY:
                        self.cache[torrent.hash] = torrent.category
                    self.name_cache[torrent.hash] = torrent.name
                    # Bypass everything if manually marked as failed
                    if torrent.category == FAILED_CATEGORY:
                        arr.logger.notice(
                            "Deleting manually failed torrent: "
                            "[Progress: {progress}%][Time Left: {timedelta}] | "
                            "{torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            timedelta=timedelta(seconds=torrent.eta),
                            progress=round(torrent.progress * 100, 2),
                        )
                        self.arr_manager.managed_objects[torrent.category].delete.add(torrent.hash)
                    # Bypass everything else if manually marked for rechecking
                    elif torrent.category == RECHECK_CATEGORY:
                        arr.logger.notice(
                            "Re-cheking manually set torrent: "
                            "[Progress: {progress}%][Time Left: {timedelta}] | "
                            "{torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            timedelta=timedelta(seconds=torrent.eta),
                            progress=round(torrent.progress * 100, 2),
                        )
                        self.arr_manager.managed_objects[torrent.category].recheck.add(
                            (torrent.hash, torrent.category)
                        )
                    # Do not touch torrents that do not have a allowlisted category.
                    elif torrent.category not in self.arr_manager.category_allowlist:
                        continue
                    # Do not touch torrents that are currently "Checking".
                    elif self.is_ignored_state(torrent):
                        continue
                    # Do not touch torrents recently resumed/reched (A torrent can temporarely stall after being resumed from a paused state).
                    elif (
                        torrent.hash
                        in self.arr_manager.managed_objects[torrent.category].timed_ignore_cache
                    ) or (
                        torrent.hash
                        in self.arr_manager.managed_objects[torrent.category].timed_skip
                    ):
                        continue
                    # Ignore torrents who have reached maximum percentage as long as the last activity is within the MaximumETA set for this category
                    # For example if you set MaximumETA to 5 mines, this will ignore all torrets that have stalled at a higher percentage as long as there is activity
                    # And the window of activity is determined by the current time - MaximumETA, if the last active was after this value ignore this torrent
                    # the idea here is that if a torrent isn't completely dead some leecher/seeder may contribute towards your progress.
                    # However if its completely dead and no activity is observed, then lets remove it and requeue a new torrent.
                    elif (
                        torrent.progress >= arr.maximum_deletable_percentage
                        and self.is_complete_state(torrent) is False
                    ):
                        if torrent.last_activity < time_now - arr.maximum_eta:
                            arr.logger.info(
                                "Deleting Stale torrent: "
                                "[Progress: {progress}%] | ({torrent.hash}) {torrent.name}",
                                torrent=torrent,
                                progress=round(torrent.progress * 100, 2),
                            )
                            self.arr_manager.managed_objects[torrent.category].delete.add(
                                torrent.hash
                            )
                        else:
                            continue
                    # Ignore torrents which have been submitted to their respective Arr instance for import.
                    elif (
                        torrent.hash
                        in self.arr_manager.managed_objects[torrent.category].sent_to_scan_hashes
                    ):
                        continue
                    # Some times torrents will error, this causes them to be rechecked so they complete downloading.
                    elif torrent.state_enum == TorrentStates.ERROR:
                        arr.logger.info(
                            "Rechecking Erroed torrent: " "{torrent.name} ({torrent.hash})",
                            torrent=torrent,
                        )
                        self.arr_manager.managed_objects[torrent.category].recheck.add(
                            (torrent.hash, torrent.category)
                        )
                    # If a torrent was not just added, and the amount left to download is 0 and the torrent is Paused tell the Arr tools to process it.
                    elif (
                        torrent.added_on > 0
                        and torrent.amount_left == 0
                        and self.is_complete_state(torrent)
                        and torrent.content_path
                        and torrent.completion_on < time_now - 30
                    ):
                        arr.logger.info(
                            "Pausing Completed torrent: "
                            "{torrent.name} ({torrent.hash}) | {torrent.state_enum}",
                            torrent=torrent,
                        )
                        self.arr_manager.managed_objects[torrent.category].pause.add(torrent.hash)
                        self.arr_manager.managed_objects[torrent.category].import_torrents.append(
                            torrent
                        )
                    # Sometimes Sonarr/Radarr does not automatically remove the torrent for some reason,
                    # this ensures that we can safelly remove it if the client is reporting the status of the client as "Missing files"
                    elif torrent.state_enum == TorrentStates.MISSING_FILES:
                        arr.logger.info(
                            "Deleting torrent with missing files: "
                            "{torrent.name} ({torrent.hash})",
                            torrent=torrent,
                        )
                        # We do not want to blacklist these!!
                        self.arr_manager.managed_objects[torrent.category].skip_blacklist.add(
                            torrent.hash
                        )
                    # Resume monitored downloads which have been paused.
                    elif (
                        torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD
                        and torrent.progress < 1
                    ):
                        self.arr_manager.managed_objects[torrent.category].resume.add(torrent.hash)
                    # Process torrents who have stalled at this point, only mark from for deletion if they have been added more than "IgnoreTorrentsYoungerThan" seconds ago
                    elif torrent.state_enum in (
                        TorrentStates.METADATA_DOWNLOAD,
                        TorrentStates.STALLED_DOWNLOAD,
                    ):
                        self.arr_manager.managed_objects[torrent.category].timed_skip.add(
                            torrent.hash
                        )
                        if torrent.added_on < time_now - arr.ignore_torrents_younger_than:
                            arr.logger.info(
                                "Deleting Stale torrent: "
                                "[Progress: {progress}%] | {torrent.name} ({torrent.hash})",
                                torrent=torrent,
                                progress=round(torrent.progress * 100, 2),
                            )
                            self.arr_manager.managed_objects[torrent.category].delete.add(
                                torrent.hash
                            )
                    # If a torrent is Uploading Pause it, as long as its for being Forced Uploaded.
                    elif (
                        self.is_uploading_state(torrent)
                        and torrent.seeding_time > 1
                        and torrent.amount_left == 0
                        and torrent.added_on > 0
                        and torrent.content_path
                    ):
                        arr.logger.info(
                            "Pausing uploading torrent: "
                            "{torrent.name} ({torrent.hash}) | {torrent.state_enum}",
                            torrent=torrent,
                        )
                        self.arr_manager.managed_objects[torrent.category].pause.add(torrent.hash)
                    # Mark a torrent for deletion
                    elif (
                        torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD
                        and torrent.state_enum.is_downloading
                        and torrent.added_on < time_now - arr.ignore_torrents_younger_than
                        and torrent.eta > arr.maximum_eta
                    ):
                        arr.logger.info(
                            "Deleting slow torrent: "
                            "[Progress: {progress}%][Time Left: {timedelta}] | "
                            "{torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            timedelta=timedelta(seconds=torrent.eta),
                            progress=round(torrent.progress * 100, 2),
                        )
                        self.arr_manager.managed_objects[torrent.category].delete.add(torrent.hash)
                    # Process uncompleted torrents
                    elif torrent.state_enum.is_downloading:
                        # If a torrent availability hasn't reached 100% or more within the configurable "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
                        if (
                            torrent.added_on < time_now - arr.ignore_torrents_younger_than
                            and torrent.availability < 1
                        ):
                            arr.logger.info(
                                "Deleting Stale torrent: "
                                "[Progress: {progress}%][Availability: {availability}%]"
                                "[Last active: {last_activity}] | {torrent.name} ({torrent.hash})",
                                torrent=torrent,
                                progress=round(torrent.progress * 100, 2),
                                availability=round(torrent.availability * 100, 2),
                                last_activity=torrent.last_activity,
                            )
                            self.arr_manager.managed_objects[torrent.category].delete.add(
                                torrent.hash
                            )

                        else:
                            # A downloading torrent is not stalled, parse its contents.
                            _remove_files = set()
                            total = len(torrent.files)
                            for file in torrent.files:
                                file_path = pathlib.Path(file.name)
                                # Acknowledge files that already been marked as "Don't download"
                                if file.priority == 0:
                                    total -= 1
                                    continue
                                # A file in the torrent does not have the allowlisted extensions, mark it for exclusion.
                                if file_path.suffix not in arr.file_extension_allowlist:
                                    arr.logger.debug(
                                        "Removing File: Not allowed - Extension: "
                                        "{suffix}  | {torrent.name} ({torrent.hash}) | {file.name} ",
                                        torrent=torrent,
                                        file=file,
                                        suffix=file_path.suffix,
                                    )
                                    _remove_files.add(file.id)
                                    total -= 1
                                # A folder within the folder tree matched the terms in FolderExclusionRegex, mark it for exclusion.
                                elif any(
                                    arr.folder_exclusion_regex_re.match(p.name.lower())
                                    for p in file_path.parents
                                    if (folder_match := p.name)
                                ):
                                    arr.logger.debug(
                                        "Removing File: Not allowed - Parent: "
                                        "{folder_match} | {torrent.name} ({torrent.hash}) | {file.name} ",
                                        torrent=torrent,
                                        file=file,
                                        folder_match=folder_match,
                                    )
                                    _remove_files.add(file.id)
                                    total -= 1
                                # A file matched and entry in FileNameExclusionRegex, mark it for exclusion.
                                elif match := arr.file_name_exclusion_regex_re.search(
                                    file_path.name
                                ):
                                    arr.logger.debug(
                                        "Removing File: Not allowed - Name: "
                                        "{match} | {torrent.name} ({torrent.hash}) | {file.name}",
                                        torrent=torrent,
                                        file=file,
                                        match=match.group(),
                                    )
                                    _remove_files.add(file.id)
                                    total -= 1
                                # If all files in the torrent are marked for exlusion then delete the torrent.
                                if total == 0:
                                    arr.logger.info(
                                        "Deleting All files ignored: "
                                        "{torrent.name} ({torrent.hash})",
                                        torrent=torrent,
                                    )
                                    self.arr_manager.managed_objects[torrent.category].delete.add(
                                        torrent.hash
                                    )
                                # Mark all bad files and folder for exclusion.
                                elif (
                                    _remove_files
                                    and torrent.hash
                                    not in self.arr_manager.managed_objects[
                                        torrent.category
                                    ].change_priority
                                ):
                                    self.arr_manager.managed_objects[
                                        torrent.category
                                    ].change_priority[torrent.hash] = list(_remove_files)
                arr.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())

    def schedule(self) -> NoReturn:
        while True:
            try:
                try:
                    if not self.is_alive:
                        raise NoConnectionrException("Could not connect to qBit client.")
                    self.process_torrents()
                except NoConnectionrException as e:
                    self.logger.error(e.message)
                    self.should_delay_torrent_scan = True
                    raise DelayLoopException(length=300, type="qbit")
                except DelayLoopException:
                    raise
                except Exception as e:
                    self.logger.error(e, exc_info=sys.exc_info())
                time.sleep(LOOP_SLEEP_TIMER)
            except DelayLoopException as e:
                if e.type == "qbit":
                    self.logger.critical(
                        "Failed to connected to qBit client, sleeping for %s."
                        % timedelta(seconds=e.length)
                    )
                elif e.type == "internet":
                    self.logger.critical(
                        "Failed to connected to the internet, sleeping for %s."
                        % timedelta(seconds=e.length)
                    )
                elif e.type == "delay":
                    self.logger.critical(
                        "Forced delay due to temporary issue with environment, sleeping for %s."
                        % timedelta(seconds=e.length)
                    )
                time.sleep(e.length)
                self.should_delay_torrent_scan = False


if __name__ == "__main__":
    qBitManager().schedule()
