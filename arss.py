from __future__ import annotations

import contextlib
import pathlib
import re
import shutil
import sys
from collections import defaultdict
from configparser import NoOptionError, NoSectionError
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Protocol, Set, Tuple, Type, Union

import ffmpeg
import logbook
import qbittorrentapi
from pyarr import RadarrAPI, SonarrAPI

from config import (
    AUTO_DELETE,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    FAILED_CATEGORY,
    FILE_EXTENSION_ALLOWLIST,
    IGNORE_TORRENTS_YOUNGER_THAN,
    RECHECK_CATEGORY,
)
from errors import SkipException
from logger import CONSOLE_LOGGING_LEVEL
from utils import ExpiringSet, absolute_file_paths, validate_and_return_torrent_file

logger = logbook.Logger("ArrManager")
logger.handlers.append(logbook.StderrHandler(level=CONSOLE_LOGGING_LEVEL))


class Arr:
    def __init__(
        self,
        name: str,
        manager: Type[ArrManager],
        client_cls: Type[Callable | RadarrAPI | SonarrAPI],
    ):
        if name in manager.groups:
            raise EnvironmentError("Group '{name}' has already been registered.")
        self._name = name
        self.managed = CONFIG.getboolean(name, "Managed")
        if not self.managed:
            raise SkipException
        self.uri = CONFIG.get(name, "URI")
        if self.uri in manager.uris:
            raise EnvironmentError(
                "Group '{name}' is trying to manage Radarr instance: '{uri}' which has already been registered."
            )

        self.category = CONFIG.get(name, "Category", fallback=self._name)
        self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)
        if not self.completed_folder.exists():
            raise EnvironmentError(
                f"{self._name} completed folder is a requirement, The specified folder does not exist '{self.completed_folder}'"
            )
        self.apikey = CONFIG.get(name, "APIKey")

        self.re_search = CONFIG.getboolean(name, "Research")
        self.import_mode = CONFIG.get(name, "importMode", fallback="Move")
        self.refresh_downloads_timer = CONFIG.getint(name, "RefreshDownloadsTimer", fallback=1)
        self.rss_sync_timer = CONFIG.getint(name, "RssSyncTimer", fallback=15)

        self.client = client_cls(host_url=self.uri, api_key=self.apikey)
        if isinstance(self.client, SonarrAPI):
            self.type = "sonarr"
        else:
            self.type = "radarr"
        self.manager = manager
        if self.rss_sync_timer > 0:
            self.rss_sync_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.rss_sync_timer_last_checked = None
        if self.refresh_downloads_timer > 0:
            self.refresh_downloads_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.refresh_downloads_timer_last_checked = None

        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.import_torrents = []
        self.change_priority = dict()
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.delete = set()
        self.resume = set()

        self.timed_ignore_cache = ExpiringSet(max_age_seconds=IGNORE_TORRENTS_YOUNGER_THAN)
        self.timed_skip = ExpiringSet(max_age_seconds=IGNORE_TORRENTS_YOUNGER_THAN)

        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)
        self.logger = logbook.Logger(self._name)
        self.logger.handlers.append(logbook.StderrHandler(level=CONSOLE_LOGGING_LEVEL))
        self.logger.debug(
            "{group} Config: "
            "Managed: {managed}, "
            "Re-search: {search}, "
            "ImportMode: {import_mode}, "
            "Category: {category}, "
            "URI: {uri}, "
            "API Key: {apikey}, "
            "RefreshDownloadsTimer={refresh_downloads_timer}, "
            "RssSyncTimer={rss_sync_timer}",
            group=self._name,
            import_mode=self.import_mode,
            managed=self.managed,
            search=self.re_search,
            category=self.category,
            uri=self.uri,
            apikey=self.apikey,
            refresh_downloads_timer=self.refresh_downloads_timer,
            rss_sync_timer=self.rss_sync_timer,
        )

    def delete_from_queue(self, id_, remove_from_client=True, blacklist=True):
        params = {"removeFromClient": remove_from_client, "blocklist": blacklist}
        path = f"/api/v3/queue/{id_}"
        res = self.client.request_del(path, params=params)
        return res

    def post_command(self, name, **kwargs):
        data = {
            "name": name,
            **kwargs,
        }
        path = "/api/v3/command"
        res = self.client.request_post(path, data=data)
        return res

    def refresh_download_queue(self):
        if self.type == "sonarr":
            self.queue = self.client.get_queue()
        else:
            self.queue = self.client.get_queue(page_size=10000).get("records", [])

        self.cache = {
            entry["downloadId"]: entry["id"] for entry in self.queue if entry.get("downloadId")
        }
        if self.type == "sonarr":
            self.requeue_cache = defaultdict(list)
            for entry in self.queue:
                if "episode" in entry:
                    self.requeue_cache[entry["id"]].append(entry["episode"]["id"])
        else:
            self.requeue_cache = {
                entry["id"]: entry["movieId"] for entry in self.queue if entry.get("movieId")
            }

    def _remove_empty_folders(self) -> None:
        new_sent_to_scan = set()
        for path in absolute_file_paths(self.completed_folder):
            if path.is_dir() and not len(list(absolute_file_paths(path))):
                path.rmdir()
                self.logger.trace("Removing empty folder: {path}", path=path)
                if path in self.sent_to_scan:
                    self.sent_to_scan.discard(path)
                else:
                    new_sent_to_scan.add(path)
        self.sent_to_scan = new_sent_to_scan
        if not len(list(absolute_file_paths(self.completed_folder))):
            self.sent_to_scan = set()
            self.sent_to_scan_hashes = set()

    def process_entries(self, hashes: Set[str]) -> Tuple[List[Tuple[int, str]], Set[str]]:
        payload = [
            (_id, h.upper())
            for h in hashes
            if (_id := self.cache.get(h.upper())) is not None
            and not self.logger.debug("Blocklisting: {hash}", hash=h)
        ]
        hashes = {h for h in hashes if (_id := self.cache.get(h.upper())) is not None}

        return payload, hashes

    def folder_cleanup(self) -> None:
        if AUTO_DELETE is False:
            return
        folder = self.completed_folder
        self.logger.debug("Folder Cleanup: {folder}", folder=folder)
        for file in absolute_file_paths(folder):
            if file.name in {"desktop.ini", ".DS_Store"}:
                continue
            if file.is_dir():
                self.logger.trace("Folder Cleanup: File is a folder:  {file}", file=file)
                continue
            if file.suffix in FILE_EXTENSION_ALLOWLIST and self.file_is_probeable(file):
                self.logger.trace(
                    "Folder Cleanup: File has an allowed extension: {file}", file=file
                )
                continue
            try:
                file.unlink(missing_ok=True)
                self.logger.debug("File removed: {path}", path=file)
            except PermissionError:
                self.logger.debug("File in use: Failed to remove file: {path}", path=file)
        self._remove_empty_folders()

    def file_is_probeable(self, file: pathlib.Path) -> bool:
        if not self.manager.ffprobe_available:
            return True  # ffprobe is not in PATH, so we say every file is acceptable.
        try:
            if file in self.files_probed:
                self.logger.trace("Probeable: File has already been probed: {file}", file=file)
                return True
            if file.is_dir():
                self.logger.trace("Not Probeable: File is a directory: {file}", file=file)
                return False
            output = ffmpeg.probe(str(file.absolute()))
            if not output:
                self.logger.trace("Not Probeable: Probe returned no output: {file}", file=file)
                return False
            self.files_probed.add(file)
            return True
        except ffmpeg.Error as e:
            error = e.stderr.decode()
            self.logger.trace(
                "Not Probeable: Probe returned an error: {file}:\n{e.stderr}",
                e=e,
                file=file,
                exc_info=sys.exc_info(),
            )
            if "Invalid data found when processing input" in error:
                return False
            return False

    def api_calls(self):
        now = datetime.now()
        if (
            self.rss_sync_timer_last_checked is not None
            and self.rss_sync_timer_last_checked < now - timedelta(minutes=self.rss_sync_timer)
        ):
            self.post_command("RssSync")
            self.rss_sync_timer_last_checked = now

        if (
            self.refresh_downloads_timer_last_checked is not None
            and self.refresh_downloads_timer_last_checked
            < now - timedelta(minutes=self.refresh_downloads_timer)
        ):
            self.post_command("RefreshMonitoredDownloads")
            self.refresh_downloads_timer_last_checked = now

    def _process_paused(self):
        # Bulks pause all torrents flagged for pausing.
        if self.pause:
            self.logger.debug("Pausing {count} completed torrents", count=len(self.pause))
            self.manager.qbit.torrents_pause(torrent_hashes=self.pause)
            self.pause.clear()

    def _process_imports(self):
        if self.import_torrents:
            for torrent in self.import_torrents:
                if torrent.hash in self.sent_to_scan:
                    continue
                path = validate_and_return_torrent_file(torrent.content_path)
                if not path.exists():
                    self.skip_blacklist.add(torrent.hash.upper())
                    self.logger.info(
                        "Deleting Missing Torrent: [{torrent.category}] - "
                        "({torrent.hash}) {torrent.name} ",
                        torrent=torrent,
                    )
                    continue
                if path in self.sent_to_scan:
                    continue
                self.sent_to_scan_hashes.add(torrent.hash)
                self.logger.notice(
                    "DownloadedEpisodesScan: [{torrent.category}] - {path}",
                    torrent=torrent,
                    path=path,
                )
                self.post_command(
                    "DownloadedEpisodesScan",
                    path=str(path),
                    downloadClientId=torrent.hash.upper(),
                    importMode=self.import_mode,
                )
                self.sent_to_scan.add(path)
            self.import_torrents.clear()

    def _process_failed_individual(self, hash_: str, entry: int, skip_blacklist: Set[str]):
        with contextlib.suppress(Exception):
            if hash_ not in skip_blacklist:
                self.delete_from_queue(id_=entry, blacklist=True)
            else:
                self.delete_from_queue(id_=entry, blacklist=False)
        object_id = self.requeue_cache.get(entry)
        if object_id:
            if self.type == "sonarr":
                data = self.client.get_episode_by_episode_id(object_id[0])
                name = data.get("title")
                if name:
                    episodeNumber = data.get("episodeNumber", 0)
                    absoluteEpisodeNumber = data.get("absoluteEpisodeNumber", 0)
                    seasonNumber = data.get("seasonNumber", 0)
                    seriesTitle = data.get("series", {}).get("title")
                    year = data.get("series", {}).get("year", 0)
                    tvdbId = data.get("series", {}).get("tvdbId", 0)
                    self.logger.notice(
                        "{category} | Re-Searching episode: {seriesTitle} ({year}) - "
                        "S{seasonNumber:02d}E{episodeNumber:03d} "
                        "({absoluteEpisodeNumber:04d}) - "
                        "{title}  "
                        "[tvdbId={tvdbId}|id={episode_ids}]",
                        category=self.category,
                        episode_ids=object_id[0],
                        title=name,
                        year=year,
                        tvdbId=tvdbId,
                        seriesTitle=seriesTitle,
                        seasonNumber=seasonNumber,
                        absoluteEpisodeNumber=absoluteEpisodeNumber,
                        episodeNumber=episodeNumber,
                    )
                else:
                    self.logger.notice(
                        f"{self.category} | Re-Searching episodes: {' '.join([f'{i}' for i in object_id])}"
                    )
                self.post_command("EpisodeSearch", episodeIds=object_id)
            else:
                data = self.client.get_movie_by_movie_id(object_id)
                name = data.get("title")
                if name:
                    year = data.get("year", 0)
                    tmdbId = data.get("tmdbId", 0)
                    self.logger.notice(
                        "{category} | Re-Searching movie:   {name} ({year}) "
                        "[tmdbId={tmdbId}|id={movie_id}]",
                        category=self.category,
                        movie_id=object_id,
                        name=name,
                        year=year,
                        tmdbId=tmdbId,
                    )
                else:
                    self.logger.notice(
                        "{category} | Re-Searching movie:   {movie_id}",
                        movie_id=object_id,
                        category=self.category,
                    )
                self.post_command("MoviesSearch", movieIds=[object_id])

    def _process_failed(self):
        to_delete_all = self.delete.union(self.skip_blacklist)
        skip_blacklist = {i.upper() for i in self.skip_blacklist}
        if to_delete_all:
            payload, hashes = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._process_failed_individual(
                        hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                    )
            # Remove all bad torrents from the Client.
            self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
        self.skip_blacklist.clear()
        self.delete.clear()

    def _process_errored(self, torrent_cache: Dict[str, str]):
        # Recheck all torrents marked for rechecking.
        if self.recheck:
            updated_recheck = [r[0] for r in self.recheck]
            self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck)
            for k in updated_recheck:
                self.timed_ignore_cache.add(k)
            self.recheck.clear()

    def _process_resume(self):
        if self.resume:
            self.manager.qbit.torrents_resume(torrent_hashes=self.resume)
            for k in self.resume:
                self.timed_ignore_cache.add(k)
            self.resume.clear()

    def _process_file_priority(self):
        # Set all files marked as "Do not download" to not download.
        for hash_, files in self.change_priority.copy().items():
            torrent_info = self.manager.qbit.torrents_info(torrent_hashes=hash_)
            if torrent_info:
                torrent = torrent_info[0]
                self.logger.debug(
                    "Updating file priority on torrent: ({torrent.hash}) {torrent.name}",
                    torrent=torrent,
                )
                self.manager.qbit.torrents_file_priority(torrent_hash=hash_, file_ids=files, priority=0)
            else:
                self.logger.error("Torrent does not exist? {hash}", hash=hash_)
            del self.change_priority[hash_]

    def process(self, torrent_cache: Dict[str, str]):
        self._process_paused()
        self._process_failed()
        self._process_errored(torrent_cache)
        self._process_file_priority()
        self.folder_cleanup()
        self._process_imports()


class PlaceHolderArr(Arr):
    def __init__(
        self,
        name: str,
        manager: Type[ArrManager],
    ):
        if name in manager.groups:
            raise EnvironmentError("Group '{name}' has already been registered.")
        self._name = name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.import_torrents = []
        self.change_priority = dict()
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.delete = set()
        self.resume = set()

        self.timed_ignore_cache = ExpiringSet(max_age_seconds=IGNORE_TORRENTS_YOUNGER_THAN)
        self.timed_skip = ExpiringSet(max_age_seconds=IGNORE_TORRENTS_YOUNGER_THAN)

    def _process_failed(self):
        if not (self.delete or self.skip_blacklist):
            return
        to_delete_all = self.delete.union(self.skip_blacklist)
        skip_blacklist = {i.upper() for i in self.skip_blacklist}
        if to_delete_all:
            for arr in self.manager.managed_objects.values():
                payload, hashes = arr.process_entries(to_delete_all)
                if payload:
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._process_failed_individual(
                                hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                            )

            # Remove all bad torrents from the Client.
            self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
        self.skip_blacklist.clear()
        self.delete.clear()

    def _process_errored(self, torrent_cache: Dict[str, str]):
        # Recheck all torrents marked for rechecking.
        if self.recheck:
            temp = defaultdict(list)
            updated_recheck = []
            for h, c in self.recheck:
                updated_recheck.append(h)
                if c := torrent_cache.get(h):
                    temp[c].append(h)
            self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck)
            for k, v in temp.items():
                self.manager.qbit.torrents_set_category(torrent_hashes=v, category=k)

            for k in updated_recheck:
                self.timed_ignore_cache.add(k)
            self.recheck.clear()

    def process(self, torrent_cache: Dict[str, str]):
        self._process_failed()
        self._process_errored(torrent_cache)


class ArrManager:
    groups: Set[str] = set()
    uris: Set[str] = set()
    special_categories: Set[str] = {FAILED_CATEGORY, RECHECK_CATEGORY}
    category_allowlist: Set[str] = special_categories.copy()

    completed_folders: Set[pathlib.Path] = set()
    managed_objects: Dict[str, Arr] = {}
    ffprobe_available: bool = bool(shutil.which("ffprobe"))
    qbit: qbittorrentapi.Client = None
    if not ffprobe_available:
        logger.error(
            "ffprobe was not found in your PATH, disabling all functionality dependant on it."
        )

    @classmethod
    def build_from_config(cls, qbit: qbittorrentapi.Client):
        cls.qbit = qbit
        for key in CONFIG.sections():
            if search := re.match("(rad|son)arr.*", key, re.IGNORECASE):
                name = search.group(0)
                match = search.group(1)
                if match.lower() == "son":
                    call_cls = SonarrAPI
                elif match.lower() == "rad":
                    call_cls = RadarrAPI
                else:
                    call_cls = None
                try:
                    managed_object = Arr(name, cls, client_cls=call_cls)
                    cls.groups.add(name)
                    cls.uris.add(managed_object.uri)
                    cls.managed_objects[managed_object.category] = managed_object
                except (NoSectionError, NoOptionError) as e:
                    logger.exception(e.message)
                except SkipException:
                    continue
                except EnvironmentError as e:
                    logger.exception(e)
        for cat in cls.special_categories:
            managed_object = PlaceHolderArr(cat, cls)
            cls.managed_objects[cat] = managed_object
        return cls
