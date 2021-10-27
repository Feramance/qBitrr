import configparser
import contextlib
import json
import logging
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import timedelta
from typing import Iterator, List, NoReturn, Set, Tuple, Union

import ffmpeg
import logbook
import qbittorrentapi
import requests
from pyarr import RadarrAPI, SonarrAPI
from qbittorrentapi import TorrentDictionary, TorrentStates

config = configparser.ConfigParser(converters={'list': lambda x: [i.strip() for i in x.split(',')],
                                               'int': lambda x: int(x),
                                               'float': lambda x: float(x),
                                               'boolean': lambda x: x.lower().strip() in {"1",
                                                                                          "true",
                                                                                          "on",
                                                                                          "enabled"},
                                               'upper': lambda x: str(x).upper().strip()
                                               })
config.read("./config.ini")
base_folder = pathlib.Path().home().joinpath(".config", "qBitManager")
base_folder.mkdir(parents=True, exist_ok=True)
logging_map = {
    "CRITICAL": logbook.CRITICAL,
    "ERROR": logbook.ERROR,
    "WARNING": logbook.WARNING,
    "NOTICE": logbook.NOTICE,
    "INFO": logbook.INFO,
    "DEBUG": logbook.DEBUG,
    "TRACE": logbook.TRACE
}
logging_level = logging_map.get(config.getupper("Logging", "FileLevel", fallback="NOTICE"))
Console_level = logging_map.get(config.getupper("Logging", "ConsoleLevel", fallback="NOTICE"))
logging_file = base_folder.joinpath(config.get("Logging", "LogFileName"))
logger = logbook.Logger('QbitManager')
logger.handlers.append(logbook.StderrHandler(level=Console_level))
logger.handlers.append(logbook.RotatingFileHandler(filename=logging_file,
                            encoding="utf-8",
                            mode="w",
                            level=logging_level,
                            backup_count=config.getint("Logging", "LogFileCount", fallback=1),
                            max_size=config.getint("Logging", "LogFileMaximumSize",
                                                   fallback=1024 * 1024)
                            ))


# Sonarr Config Values
Sonarr_URI = config.get("Sonarr", "URI", fallback="http://localhost:8989")
Sonarr_APIKey = config.get("Sonarr", "APIKey")
Sonarr_Managed = config.getboolean("Sonarr", "Managed")
Sonarr_Category = config.get("Sonarr", "Category")
Sonarr_Research = config.getboolean("Sonarr", "Research")
Sonarr_importMode = config.get("Sonarr", "importMode", fallback="Move")
logger.debug(
    "Sonarr Config: Managed: {Sonarr_Managed}, Research: {Sonarr_Research}, ImportMode: {Sonarr_importMode}, Category: {Sonarr_Category} URI: {Sonarr_URI}, API Key: {Sonarr_APIKey}",
    Sonarr_importMode=Sonarr_importMode,
    Sonarr_Managed=Sonarr_Managed,
    Sonarr_Research=Sonarr_Research,
    Sonarr_Category=Sonarr_Category,
    Sonarr_URI=Sonarr_URI,
    Sonarr_APIKey=Sonarr_APIKey)

# Radarr Config Values
Radarr_URI = config.get("Radarr", "URI", fallback="http://localhost:7878")
Radarr_APIKey = config.get("Radarr", "APIKey")
Radarr_Managed = config.getboolean("Radarr", "Managed")
Radarr_Category = config.get("Radarr", "Category")
Radarr_Research = config.getboolean("Radarr", "Research")
Radarr_importMode = config.get("Sonarr", "importMode", fallback="Move")

logger.debug(
    "Radarr Config: Managed: {Radarr_Managed}, Research: {Radarr_Research}, ImportMode: {Radarr_importMode}, Category: {Radarr_Category} URI: {Radarr_URI}, API Key: {Radarr_APIKey}",
    Radarr_importMode=Radarr_importMode,
    Radarr_Managed=Radarr_Managed,
    Radarr_Research=Radarr_Research,
    Radarr_Category=Radarr_Category,
    Radarr_URI=Radarr_URI,
    Radarr_APIKey=Radarr_APIKey)

# QBitTorrent Config Values
qBit_Host = config.get("QBit", "Host", fallback="localhost")
qBit_Port = config.getint("QBit", "Port")
qBit_UserName = config.get("QBit", "UserName")
qBit_Password = config.get("QBit", "Password", fallback=None)
qBit_SIMPLE_RESPONSES = config.getboolean("QBit", "SIMPLE_RESPONSES", fallback=False)
CompletedDownloadFolder = config.get("QBit", "CompletedDownloadFolder")
logger.debug(
    "QBitTorrent Config: Host: {qBit_Host}, Port: {qBit_Port}, Username: {qBit_UserName}, Password: {qBit_Password}, SIMPLE_RESPONSES={qBit_SIMPLE_RESPONSES}, CompletedDownloadFolder={CompletedDownloadFolder}"
    , qBit_Host=qBit_Host, qBit_Port=qBit_Port, qBit_UserName=qBit_UserName,
    qBit_Password=qBit_Password, qBit_SIMPLE_RESPONSES=qBit_SIMPLE_RESPONSES,
    CompletedDownloadFolder=CompletedDownloadFolder
    )

# Others Config Values
PingURL = config.get("Others", "PingURL", fallback="http://www.google.com", )
logger.debug("Ping URL {PingURL}", PingURL=PingURL)

# Settings Config Values
CaseSensitiveMatches = config.getboolean("Settings", "CaseSensitiveMatches")
FolderExclusionRegex = config.getlist("Settings", "FolderExclusionRegex")
FileNameExclusionRegex = config.getlist("Settings", "FileNameExclusionRegex")
FileExtensionAllowlist = config.getlist("Settings", "FileExtensionAllowlist")
NoInternetSleepTimer = config.getint("Settings", "NoInternetSleepTimer", fallback=60)
LoopSleepTimer = config.getint("Settings", "LoopSleepTimer", fallback=5)
AutoDelete = config.getboolean("Settings", "AutoDelete")
IgnoreTorrentsYoungerThan = config.getint("Settings", "IgnoreTorrentsYoungerThan", fallback=600)
MaximumETA = config.getint("Settings", "MaximumETA", fallback=18000)
MaximumDeletablePercentage = config.getfloat("Settings", "MaximumDeletablePercentage",
                                             fallback=0.95)

logger.debug("Script Config:  CaseSensitiveMatches={CaseSensitiveMatches}",
             CaseSensitiveMatches=CaseSensitiveMatches)
logger.debug("Script Config:  FolderExclusionRegex={FolderExclusionRegex}",
             FolderExclusionRegex=FolderExclusionRegex)
logger.debug("Script Config:  FileNameExclusionRegex={FileNameExclusionRegex}",
             FileNameExclusionRegex=FileNameExclusionRegex)
logger.debug("Script Config:  FileExtensionAllowlist={FileExtensionAllowlist}",
             FileExtensionAllowlist=FileExtensionAllowlist)
logger.debug("Script Config:  AutoDelete={AutoDelete}", AutoDelete=AutoDelete)
logger.debug("Script Config:  LoopSleepTimer={LoopSleepTimer}", LoopSleepTimer=LoopSleepTimer)
logger.debug("Script Config:  NoInternetSleepTimer={NoInternetSleepTimer}",
             NoInternetSleepTimer=NoInternetSleepTimer)
logger.debug("Script Config:  IgnoreTorrentsYoungerThan={IgnoreTorrentsYoungerThan}",
             IgnoreTorrentsYoungerThan=IgnoreTorrentsYoungerThan)
logger.debug("Script Config:  MaximumETA={MaximumETA}", MaximumETA=MaximumETA)
logger.debug("Script Config:  MaximumDeletablePercentage={MaximumDeletablePercentage}",
             MaximumDeletablePercentage=MaximumDeletablePercentage)

if CaseSensitiveMatches:
    FolderExclusionRegex_re = re.compile("|".join(FolderExclusionRegex), re.DOTALL)
    FileNameExclusionRegex_re = re.compile("|".join(FileNameExclusionRegex), re.DOTALL)
else:
    FolderExclusionRegex_re = re.compile("|".join(FolderExclusionRegex), re.IGNORECASE | re.DOTALL)
    FileNameExclusionRegex_re = re.compile("|".join(FileNameExclusionRegex),
                                           re.IGNORECASE | re.DOTALL)


def has_internet() -> bool:
    try:
        requests.get(PingURL, timeout=1)
        logger.trace("has_internet check: True")
        return True
    except (requests.ConnectionError, requests.Timeout):
        logger.warning("has_internet check: False")
        return False
    except Exception:
        logger.error(exc_info=sys.exc_info())
        return False


class qBitManager:
    client = qbittorrentapi.Client(host=qBit_Host, port=qBit_Port, username=qBit_UserName,
                                   password=qBit_Password, SIMPLE_RESPONSES=qBit_SIMPLE_RESPONSES)
    completed_folders = set()
    category_allowlist = set()
    _radarr_queue = []
    _sonarr_queue = []
    _radarr_cache = {}
    _sonarr_cache = {}
    _radarr_requeue_cache = {}
    _sonarr_requeue_cache = {}
    _sent_to_scan_radarr = set()
    _sent_to_scan_sonarr = set()
    _skip_probe = set()
    _ffprobe_enabled = shutil.which("ffprobe")
    if not _ffprobe_enabled:
        logger.error("ffprobe was not found in your PATH.")

    if Radarr_Managed:
        radarr = RadarrAPI(host_url="http://localhost:7878",
                           api_key="626ccef1fefb4a8c891c55b793cba169")
        radarr_completed_folder = pathlib.Path(CompletedDownloadFolder).joinpath(Radarr_Category)
        category_allowlist.add(Radarr_Category)
        if not radarr_completed_folder.exists():
            logger.critical(
                "Completed download folder does not exist, disabling all features that expect this folder: {radarr_completed_folder}",
                radarr_completed_folder=radarr_completed_folder.absolute())
            raise EnvironmentError("Radarr completed folder is a requirement.")
        else:
            completed_folders.add(radarr_completed_folder)
    else:
        radarr = None
        radarr_completed_folder = None
    if Sonarr_Managed:
        sonarr = SonarrAPI(host_url="http://localhost:8989",
                           api_key="3b17b069ce5842429117b831caecaf78")
        category_allowlist.add(Sonarr_Category)
        sonarr_completed_folder = pathlib.Path(CompletedDownloadFolder).joinpath(Sonarr_Category)
        if not radarr_completed_folder.exists():
            logger.critical(
                "Completed download folder does not exist, disabling all features that expect this folder: {sonarr_completed_folder}",
                sonarr_completed_folder=sonarr_completed_folder.absolute())
            raise EnvironmentError("Sonarr completed folder is a requirement.")
        else:
            completed_folders.add(sonarr_completed_folder)
    else:
        sonarr = None
        sonarr_completed_folder = None

    # Radarr updated their API and now expect the arg to be "blocklist" instead of "blacklist", but pyarr hasn't updated it yet
    def radarr_del_queue(self, id_, remove_from_client=True, blacklist=True):
        params = {"removeFromClient": remove_from_client, "blocklist": blacklist}
        path = f"/api/v3/queue/{id_}"
        res = self.radarr.request_del(path, params=params)
        return res

    # Sonarr updated their API and now expect the arg to be "blocklist" instead of "blacklist", but pyarr hasn't updated it yet
    def sonarr_del_queue(self, id_, remove_from_client=True, blacklist=True):
        params = {"removeFromClient": remove_from_client, "blocklist": blacklist}
        path = f"/api/v3/queue/{id_}"
        res = self.radarr.request_del(path, params=params)
        return res

    @staticmethod
    def absoluteFilePaths(directory: Union[pathlib.Path, str]) -> Iterator[pathlib.Path]:
        for object in pathlib.Path(directory).glob("**/*"):
            yield object

    @staticmethod
    def is_stalled(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.METADATA_DOWNLOAD,
            # We do not want to touch any torrent where the user set it to Force Upload/Download
            # TorrentStates.FORCED_DOWNLOAD,
        )

    @staticmethod
    def is_downloading(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            # We do not want to touch any torrent where the user set it to Force Upload/Download
            # TorrentStates.FORCED_DOWNLOAD,
        )

    @staticmethod
    def is_trying_to_download(self):
        """Returns True if the State is categorized as Downloading."""
        return self in (
            TorrentStates.DOWNLOADING,
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.STALLED_DOWNLOAD,
        )

    @staticmethod
    def is_uploading(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            # We do not want to touch any torrent where the user set it to Force Upload/Download
            # TorrentStates.FORCED_UPLOAD,
        )

    def refresh_download_qeueue_from_arrs(self) -> None:
        if self.radarr:
            self._radarr_queue = self.radarr.get_queue(page_size=10000).get("records", [])
            self._radarr_cache = {entry["downloadId"]: entry["id"] for entry in self._radarr_queue
                                  if entry.get("downloadId")}
            self._radarr_requeue_cache = {entry["id"]: entry["movieId"] for entry in
                                          self._radarr_queue if entry.get("movieId")}
        if self.sonarr:
            self._sonarr_queue = self.sonarr.get_queue()
            self._sonarr_cache = {entry["downloadId"]: entry["id"] for entry in self._sonarr_queue
                                  if entry.get("downloadId")}
            self._sonarr_requeue_cache = defaultdict(list)
            for entry in self._sonarr_queue:
                if "episode" in entry:
                    self._sonarr_requeue_cache[entry["id"]].append(entry["episode"]["id"])

    def process_radarr_entries(self, hashes: Set[str]) -> Tuple[List[Tuple[int, str]], Set[str]]:
        if self.radarr:
            payload = [(_id, h.upper()) for h in hashes if
                       (_id := self._radarr_cache.get(h.upper())) is not None and not logger.debug(
                           "[Radarr] Blacklisting: {hash}", hash=h)]
            hashes = {h for h in hashes if (_id := self._radarr_cache.get(h.upper())) is not None}
            return payload, hashes
        else:
            return [], set()

    def process_sonarr_entries(self, hashes: Set[str]) -> Tuple[List[Tuple[int, str]], Set[str]]:
        if self.sonarr:
            payload = [(_id, h.upper()) for h in hashes if
                       (_id := self._sonarr_cache.get(h.upper())) is not None and not logger.debug(
                           "[Sonarr] Blacklisting: {hash}", hash=h)]
            hashes = {h for h in hashes if (_id := self._sonarr_cache.get(h.upper())) is not None}
            return payload, hashes
        else:
            return [], set()

    def remove_empty_folders(self, path_abs: Union[pathlib.Path, str]) -> None:
        if path_abs not in self.completed_folders:
            return
        for path in self.absoluteFilePaths(path_abs):
            if path not in self.completed_folders and path.is_dir() and not len(
                    list(self.absoluteFilePaths(path))):
                path.rmdir()
                logger.trace("Removing empty folder: {path}", path=path)
        else:
            if path_abs == self.sonarr_completed_folder and not len(
                    list(self.absoluteFilePaths(self.sonarr_completed_folder))):
                self._sent_to_scan_sonarr = set()
            if path_abs == self.radarr_completed_folder and not len(
                    list(self.absoluteFilePaths(self.radarr_completed_folder))):
                self._sent_to_scan_radarr = set()

    def file_is_probeable(self, file: pathlib.Path) -> bool:
        if not self._ffprobe_enabled:
            return True  # ffprobe is not in PATH, so we say every file is acceptable.
        try:
            if file in self._skip_probe:
                return True
            if file.is_dir():
                return False
            output = ffmpeg.probe(str(file.absolute()))
            if not output:
                return False
            self._skip_probe.add(file)
            return True
        except ffmpeg.Error as e:
            error = e.stderr.decode()
            if "Invalid data found when processing input" in error:
                logger.trace("{e}", e=e.stderr.decode())
                return False
            return False

    def folder_cleanup(self, folder: Union[pathlib.Path, str]) -> None:
        for file in self.absoluteFilePaths(folder):
            if file.name not in {"desktop.ini", ".DS_Store"}:
                continue
            if file.suffix in FileExtensionAllowlist:
                continue
            if not self.file_is_probeable(file) and file.suffix != ".parts":
                path = pathlib.Path(file)
                path.unlink(missing_ok=True)
                logger.debug("Removing bad file: {path}", path=path)
        self.remove_empty_folders(folder)

    def validate_and_return_torrent_file(self, file: str) -> pathlib.Path:
        path = pathlib.Path(file)
        if path.is_file():
            path = path.parent.absolute()
        count = 10
        while not path.exists():
            logger.trace(
                "Attempt {count}/10 : File does not yet exists! (Possibly being moved?) - {path} - Sleeping for 0.1s",
                path=path, count=11 - count)
            time.sleep(0.1)
            if count == 0:
                break
            count -= 1
        else:
            count = 0
        while str(path) == ".":
            path = pathlib.Path(file)
            if path.is_file():
                path = path.parent.absolute()
            while not path.exists():
                logger.trace(
                    "Attempt {count}/10 :File does not yet exists! (Possibly being moved?) - {path} - Sleeping for 0.1s",
                    path=path, count=11 - count)
                time.sleep(0.1)
                if count == 0:
                    break
                count -= 1
            else:
                count = 0
            if count == 0:
                break
            count -= 1
        return path

    def process_torrents(self) -> None:
        if has_internet() is False:
            time.sleep(NoInternetSleepTimer)
            return
        torrents = self.client.torrents.info.all(sort="category", reverse=True)
        to_delete = set()
        skip_blacklist = set()
        to_pause = set()
        to_recheck = set()
        radarr_import = []
        sonarr_import = []
        to_change_prority = dict()

        self.refresh_download_qeueue_from_arrs()
        for torrent in torrents:
            # Do not touch torrents that do not have a allowlisted category.
            if torrent.category not in self.category_allowlist:
                continue
            # Do not touch torrents that are currently "Checking".
            if torrent.state_enum.is_checking:
                continue
            if torrent.progress >= MaximumDeletablePercentage:
                continue
            if torrent.hash in self._sent_to_scan_radarr or torrent.hash in self._sent_to_scan_radarr:
                continue
            # Mark a torrent for deletion
            if torrent.state_enum not in [TorrentStates.QUEUED_DOWNLOAD, TorrentStates.PAUSED_DOWNLOAD] and torrent.state_enum.is_downloading and torrent.added_on < time.time() - IgnoreTorrentsYoungerThan and torrent.eta > MaximumETA:
                logger.info(
                    "Deleting slow torrent: [{torrent.category}] [Progress: {progress}%][Time Left: {timedelta}] - ({torrent.hash}) {torrent.name}",
                    torrent=torrent, timedelta=timedelta(seconds=torrent.eta),
                    progress=round(torrent.progress * 100, 2))
                to_delete.add(torrent.hash)
            # Sometimes Sonarr/Radarr does not automatically remove the torrent for some reason, this ensures that we can safelly remove it if the client is reporting the status of the client as "Missing files"
            elif torrent.state_enum == TorrentStates.MISSING_FILES:
                logger.info(
                    "Deleting torrent with missing files: [{torrent.category}] - ({torrent.hash}) {torrent.name}",
                    torrent=torrent)
                skip_blacklist.add(torrent.hash)  # We do not want to blacklist these!!
            # Some times torrents will error, this causes them to be rechecked so they complete downloading.
            elif torrent.state_enum == TorrentStates.ERROR:
                logger.info(
                    "Rechecking Erroed torrent: [{torrent.category}] - ({torrent.hash}) {torrent.name}",
                    torrent=torrent)
                to_recheck.add(torrent.hash)
            elif torrent.state_enum in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.STALLED_DOWNLOAD):
                if torrent.added_on < time.time() - IgnoreTorrentsYoungerThan:
                    logger.info(
                        "Deleting Stale torrent: [{torrent.category}] [Progress: {progress}%]- ({torrent.hash}) {torrent.name}",
                        torrent=torrent, progress=round(torrent.progress * 100, 2))
                    to_delete.add(torrent.hash)
            # Process uncompleted torrents
            elif torrent.state_enum != TorrentStates.QUEUED_DOWNLOAD and torrent.state_enum.is_downloading:
                # If a torrent availability hasn't reached 100% or more within the configurable "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
                if torrent.added_on < time.time() - IgnoreTorrentsYoungerThan and torrent.availability < 1:
                    logger.info(
                        "Deleting Stale torrent: [{torrent.category}] [Progress: {progress}%][Availability: {availability}%][Last active: {last_activity}] - ({torrent.hash}) {torrent.name}",
                        torrent=torrent, progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        last_activity=torrent.last_activity)
                    to_delete.add(torrent.hash)

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
                        if file_path.suffix not in FileExtensionAllowlist:
                            logger.debug(
                                "Removing File: Not allowed - Extension: [{torrent.category}] - {suffix}  | ({torrent.hash}) | {file.name} ",
                                torrent=torrent, file=file, suffix=file_path.suffix)
                            _remove_files.add(file.id)
                            total -= 1
                        # A folder within the folder tree matched the terms in FolderExclusionRegex, mark it for exclusion.
                        elif any(FolderExclusionRegex_re.match(p.name.lower()) for p in
                                 file_path.parents if (folder_match := p.name)):
                            logger.debug(
                                "Removing File: Not allowed - Parent: [{torrent.category}] - {folder_match} | ({torrent.hash}) | {file.name} ",
                                torrent=torrent, file=file, folder_match=folder_match)
                            _remove_files.add(file.id)
                            total -= 1
                        # A file matched and entry in FileNameExclusionRegex, mark it for exclusion.
                        elif (match := FileNameExclusionRegex_re.search(file_path.name)):
                            logger.debug(
                                "Removing File: Not allowed - Name: [{torrent.category}] - {match} | ({torrent.hash}) | {file.name}",
                                torrent=torrent, file=file, match=match.group())
                            _remove_files.add(file.id)
                            total -= 1

                        # If all files in the torrent are marked for exlusion then delete the torrent.
                        if total == 0:
                            logger.info(
                                "Deleting All files ignored: [{torrent.category}] - ({torrent.hash}) {torrent.name}",
                                torrent=torrent)
                            to_delete.add(torrent.hash)
                        # Mark all bad files and folder for exlusion.
                        elif _remove_files and torrent.hash not in to_change_prority:
                            to_change_prority[torrent.hash] = list(_remove_files)
                        # if a torrent is Paused Unpause it.
                        if torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD:
                            torrent.resume()
            # If a torrent is Uploading Pause it.
            elif torrent.state_enum != TorrentStates.CHECKING_UPLOAD and torrent.state_enum.is_uploading:
                logger.info(
                    "Pausing uploading torrent: [{torrent.category}] - ({torrent.hash}) {torrent.name} - {torrent.state_enum}",
                    torrent=torrent)
                to_pause.add(torrent.hash)
            # If a torrent was not just added, and the amount left to download is 0 and the torrent is Paused tell the Arr tools to process it.
            elif torrent.added_on > 0 and torrent.amount_left == 0 and torrent.state_enum.PAUSED_UPLOAD and torrent.content_path:
                if self.sonarr and torrent.category == Sonarr_Category and torrent.hash not in self._sent_to_scan_sonarr:
                    sonarr_import.append(torrent)
                elif self.radarr and torrent.category == Radarr_Category and torrent.hash not in self._sent_to_scan_radarr:
                    radarr_import.append(torrent)

        # Bulks pause all torrents flagged for pausing.
        if to_pause:
            self.client.torrents_pause(torrent_hashes=to_pause)
        if sonarr_import:
            for torrent in sonarr_import:
                path = self.validate_and_return_torrent_file(torrent.content_path)
                if not path.exists():
                    skip_blacklist.add(torrent.hash)
                    logger.info("Deleting Missing Torrent: [{torrent.category}] - ({torrent.hash}) {torrent.name} ", torrent=torrent)
                    continue
                if torrent.hash in self._sent_to_scan_sonarr:
                    continue
                logger.info("DownloadedEpisodesScan: [{torrent.category}] - {path}", torrent=torrent, path=path)
                self.sonarr.post_command("DownloadedEpisodesScan", path=str(path), downloadClientId=torrent.hash.upper(), importMode=Sonarr_importMode)
                self._sent_to_scan_sonarr.add(torrent.hash)
        if radarr_import:
            for torrent in radarr_import:
                path = self.validate_and_return_torrent_file(torrent.content_path)
                if not path.exists():
                    skip_blacklist.add(torrent.hash)
                    logger.info("Deleting Missing Torrent: [{torrent.category}] - {torrent.name}", torrent=torrent)
                    continue
                if torrent.hash in self._sent_to_scan_radarr:
                    continue
                logger.info("DownloadedMoviesScan: [{torrent.category}] - {path}",
                             torrent=torrent, path=path)
                self.radarr.post_command("DownloadedMoviesScan", path=str(path), downloadClientId=torrent.hash.upper(), importMode=Radarr_importMode)
                self._sent_to_scan_radarr.add(torrent.hash)

        to_delete_all = to_delete.union(skip_blacklist)
        skip_blacklist = {i.upper() for i in skip_blacklist}
        if to_delete_all:
            radarr_payload, radarr_hashes = self.process_radarr_entries(to_delete_all)
            sonarr_payload, sonarr_hashes = self.process_sonarr_entries(to_delete_all)
            if radarr_payload:
                for entry, hash_ in radarr_payload:
                    with contextlib.suppress(Exception):
                        if hash_ not in skip_blacklist:
                            self.radarr_del_queue(id_=entry, remove_from_client=True, blacklist=True)
                        else:
                            self.radarr_del_queue(id_=entry, remove_from_client=True, blacklist=False)
                    movie_id = self._radarr_requeue_cache.get(entry)
                    if movie_id:
                        logger.notice(f"Radarr | Re-Searching movies: {movie_id}")
                        self.radarr.post_command("MoviesSearch", movieIds=[movie_id])
            if sonarr_payload:
                for entry, hash_ in sonarr_payload:
                    if hash_ not in skip_blacklist:
                        self.sonarr_del_queue(id_=entry, blacklist=False)
                    else:
                        self.sonarr_del_queue(id_=entry, blacklist=True)
                    episode_ids = self._sonarr_requeue_cache.get(entry)
                    if episode_ids:
                        logger.notice(f"Sonarr | Re-Searching episodes: {' '.join([f'{i}' for i in episode_ids])}")
                        self.sonarr.post_command("EpisodeSearch", episodeIds=episode_ids)
            # Remove all bad torrents from the Client.
            if to_delete_all:
                self.client.torrents_delete(hashes=to_delete_all, delete_files=True)

        # Recheck all torrents marked for rechecking.
        if to_recheck:
            self.client.torrents_recheck(torrent_hashes=to_recheck)

        # Set all files marked as "Do not download" to not download.
        for hash, files in to_change_prority.items():
            if hash not in to_delete_all:
                self.client.torrents_file_priority(torrent_hash=hash, file_ids=files, priority=0)
        if AutoDelete and self.radarr_completed_folder:
            self.folder_cleanup(self.radarr_completed_folder)
        if AutoDelete and self.sonarr_completed_folder:
            self.folder_cleanup(self.sonarr_completed_folder)

    def schedule(self) -> NoReturn:
        while True:
            try:
                self.process_torrents()
            except BaseException as e:
                logger.error(e, exc_info=sys.exc_info())
            time.sleep(LoopSleepTimer)


if __name__ == "__main__":
    qBitManager().schedule()
