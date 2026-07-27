from __future__ import annotations

import contextlib
import pathlib
import shutil
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

import qbittorrentapi
import requests
from peewee import SqliteDatabase
from qbittorrentapi import TorrentDictionary, TorrentStates

from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.arr_shared import (
    _QBIT_READ_RETRY_EXCEPTIONS,
    APPDATA_FOLDER,
    TAGLESS,
    DelayLoopException,
    NoConnectionrException,
    TorrentLibrary,
    build_tracker_index,
    database_lock,
    get_auto_pause_resume_effective,
    get_completed_download_folder_effective,
    get_effective_qbit_disabled,
    get_free_space_guard_settings,
    get_loop_sleep_timer_effective,
    get_no_internet_sleep_timer_effective,
    has_internet,
    parse_size,
    sync_config_from_disk,
    with_retry,
)

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class TorrentPolicyManager(ArrBase):
    """
    Single global worker handling tracker sorting and free-space policy.

    Processing order is deterministic and intentional:
      1) tracker priority queue ordering
      2) free-space pause/resume/tag handling
    """

    def __init__(
        self,
        categories: set[str],
        manager: ArrManager,
        *,
        enable_tracker_sort: bool,
        enable_free_space: bool,
    ):
        self._name = "TorrentPolicyManager"
        self.type = "TorrentPolicyManager"
        self.manager = manager
        self.category = self._name
        self.uri = ""
        self.client = None
        self._temp_overseer_request_cache: dict[str, set[int | str]] = defaultdict(set)
        self._configure_worker_logging(self._name)
        self.cache = {}
        self.categories = set(categories)
        self.enable_tracker_sort = bool(enable_tracker_sort)
        self.enable_free_space = bool(enable_free_space)
        self._init_worker_expiring_timeouts()
        self._app_data_folder = APPDATA_FOLDER
        self.search_setup_completed = False
        self.search_missing = False
        self.do_upgrade_search = False
        self.quality_unmet_search = False
        self.custom_format_unmet_search = False
        self.ombi_search_requests = False
        self.overseerr_requests = False
        self.session = None
        self._init_qbit_action_buckets(include_recheck=False, include_delete=False)
        self.needs_cleanup = False
        self.torrents = None
        self.torrent_db: SqliteDatabase | None = None
        self.last_search_description: str | None = None
        self.last_search_timestamp: str | None = None
        self.queue_active_count = 0
        self.category_torrent_count = 0
        self.free_space_tagged_count = 0
        self._torrent_important_trackers_cache: dict[str, tuple[set[str], set[str]]] = {}
        self._dedicated_qbit_clients: dict[str, qbittorrentapi.Client] = {}

        # Tracker sort state
        self.monitored_trackers = ArrBase.merge_global_tracker_blocks()
        bad_msgs = ArrBase.global_bad_tracker_messages_union()
        self.seeding_mode_global_bad_tracker_msg = bad_msgs
        self.seeding_mode_global_remove_torrent = -1
        self.seeding_mode_global_max_upload_ratio = -1
        self.seeding_mode_global_max_seeding_time = -1
        self.seeding_mode_global_download_limit = -1
        self.seeding_mode_global_upload_limit = -1
        self._install_tracker_index(
            build_tracker_index(self.monitored_trackers, bad_tracker_messages=bad_msgs)
        )
        self.remove_dead_trackers = ArrBase.global_remove_dead_trackers_union()

        # Free-space state (only needed when free-space policy is enabled).
        self.completed_folder = pathlib.Path(get_completed_download_folder_effective())
        self._disk_usage_path = pathlib.Path(get_completed_download_folder_effective()).resolve()
        self._path_for_disk_usage = self._disk_usage_path
        self._free_space_folder_is_auto = True
        self.min_free_space = "-1"
        self._min_free_space_bytes = 0
        self.current_free_space = 0
        if self.enable_free_space:
            _free_space, _free_space_folder = get_free_space_guard_settings()
            self._apply_free_space_paths(_free_space, _free_space_folder)
            self.current_free_space = (
                shutil.disk_usage(self._path_for_disk_usage).free - self._min_free_space_bytes
            )

        _client = self._get_primary_qbit_client()
        if self.enable_free_space and _client is not None:
            _client.torrents_create_tags(["qBitrr-free_space_paused"])

        self.register_search_mode()
        self.logger.hnotice(
            "Starting %s | Categories: %d | tracker_sort=%s | free_space=%s",
            self._name,
            len(self.categories),
            self.enable_tracker_sort,
            self.enable_free_space,
        )
        self._register_sqlite_db_atexit("torrent_db")

    @staticmethod
    def _first_existing_parent(path: pathlib.Path) -> pathlib.Path | None:
        current = path
        while not current.exists():
            parent = current.parent
            if parent == current:
                return None
            current = parent
        return current

    def _apply_free_space_paths(
        self,
        free_space: str,
        free_space_folder: str,
    ) -> None:
        """Resolve completed_folder / disk-usage paths from live FreeSpace settings."""
        use_auto = free_space == "-1" or free_space_folder in ("", "CHANGE_ME")
        if use_auto:
            arr_cats = self.categories & self.manager.arr_categories
            chosen = next(iter(arr_cats), None) or next(iter(self.categories), None)
            completed_root = pathlib.Path(get_completed_download_folder_effective())
            self.completed_folder = completed_root.joinpath(chosen) if chosen else completed_root
            self._disk_usage_path = completed_root.resolve()
        else:
            self.completed_folder = pathlib.Path(free_space_folder)
            self._disk_usage_path = pathlib.Path(free_space_folder).resolve()
        self._free_space_folder_is_auto = use_auto
        self.min_free_space = free_space
        self._min_free_space_bytes = parse_size(free_space) if free_space != "-1" else 0
        if use_auto and not self.completed_folder.exists():
            parent = pathlib.Path(get_completed_download_folder_effective())
            if parent.exists():
                self.completed_folder = parent
        self._path_for_disk_usage = self._disk_usage_path
        if self._free_space_folder_is_auto:
            existing = self._first_existing_parent(self._disk_usage_path)
            if existing:
                self._path_for_disk_usage = existing

    def _sync_free_space_settings_from_config(self) -> None:
        """Re-read FreeSpace settings each loop; enable→disable skips free-space work.

        Flipping from disabled→enabled at runtime activates free-space processing without
        respawning; tracker-sort ownership and process spawn still follow manager init.
        """
        sync_config_from_disk()
        self._sync_tracker_sort_settings_from_config()
        free_space, free_space_folder = get_free_space_guard_settings()
        want_enabled = (
            free_space != "-1"
            and get_auto_pause_resume_effective()
            and not get_effective_qbit_disabled()
        )
        was_enabled = self.enable_free_space
        self.enable_free_space = want_enabled
        if not want_enabled:
            self.min_free_space = "-1"
            self._min_free_space_bytes = 0
            return
        self._apply_free_space_paths(free_space, free_space_folder)
        if not was_enabled:
            client = self._get_primary_qbit_client()
            if client is not None:
                with contextlib.suppress(Exception):
                    client.torrents_create_tags(["qBitrr-free_space_paused"])

    def _sync_tracker_sort_settings_from_config(self) -> None:
        """Refresh merged tracker index / dead-tracker flags from live CONFIG."""
        self.monitored_trackers = ArrBase.merge_global_tracker_blocks()
        bad_msgs = ArrBase.global_bad_tracker_messages_union()
        self.seeding_mode_global_bad_tracker_msg = bad_msgs
        self._install_tracker_index(
            build_tracker_index(self.monitored_trackers, bad_tracker_messages=bad_msgs)
        )
        self.remove_dead_trackers = ArrBase.global_remove_dead_trackers_union()

    @property
    def is_alive(self) -> bool:
        return True

    def _get_models(
        self,
    ) -> tuple[
        None,
        None,
        None,
        None,
        type[TorrentLibrary] | None,
    ]:
        return None, None, None, None, (TorrentLibrary if TAGLESS else None)

    @staticmethod
    def is_free_space_download_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.QUEUED_DOWNLOAD,
            TorrentStates.PAUSED_DOWNLOAD,
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.FORCED_METADATA_DOWNLOAD,
        )

    def _clear_free_space_paused_flags_for_hashes(
        self,
        client: qbittorrentapi.Client | None,
        instance_name: str,
        hashes: set[str],
    ) -> None:
        if not hashes:
            return
        if TAGLESS:
            if self.torrents is None:
                return
            with database_lock():
                self.torrents.update({self.torrents.FreeSpacePaused: False}).where(
                    (self.torrents.Hash.in_(list(hashes)))
                    & (self.torrents.QbitInstance == instance_name)
                ).execute()
            return
        if client is None:
            return
        with_retry(
            lambda: client.torrents_remove_tags(
                tags=["qBitrr-free_space_paused"],
                torrent_hashes=list(hashes),
            ),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=(
                qbittorrentapi.exceptions.APIError,
                qbittorrentapi.exceptions.APIConnectionError,
                requests.exceptions.RequestException,
            ),
        )

    def _process_single_torrent_pause_disk_space(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self.pause_by_instance[instance_name].add(torrent.hash)

    def _process_single_torrent(self, torrent, instance_name: str = "default"):
        if self.is_free_space_download_state(torrent):
            free_space_test = self.current_free_space - torrent["amount_left"]
            if torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test <= 0:
                self.add_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
                self._process_single_torrent_pause_disk_space(torrent, instance_name)
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test <= 0:
                self.add_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
            elif torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                self.remove_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                if self.in_tags(torrent, "qBitrr-free_space_paused", instance_name):
                    self.resume_by_instance[instance_name].add(torrent.hash)
            if free_space_test > 0:
                self.current_free_space = free_space_test
        elif not self.is_free_space_download_state(torrent) and self.in_tags(
            torrent, "qBitrr-free_space_paused", instance_name
        ):
            self.remove_tags(torrent, ["qBitrr-free_space_paused"], instance_name)

    def _process_resume(self) -> None:
        from qBitrr.arss.qbit_side_effects import resume_hashes_by_instance

        resume_hashes_by_instance(
            self,
            warn_missing_client=False,
            after_success=self._clear_free_space_paused_flags_for_hashes,
        )

    def _process_paused(self) -> None:
        from qBitrr.arss.qbit_side_effects import pause_hashes_by_instance, pause_legacy_hash_set

        pause_hashes_by_instance(self, warn_missing_client=False, log_names=False)
        pause_legacy_hash_set(self, log_names=False)

    def process(self):
        self._process_resume()
        self._process_paused()

    def _collect_monitored_torrents(self) -> list[tuple[str, qbittorrentapi.TorrentDictionary]]:
        """Fetch torrents whose category is monitored by an Arr or qBit instance.

        Uses a full ``torrents.info()`` **without** ``category=`` only on qBit
        instances where prefix matching is actually active — same per-instance
        rules as :meth:`ArrBase._get_torrents_from_all_instances` (each Arr may
        override ``MatchSubcategories``; otherwise the ``[qBit*]`` flag applies),
        plus ``ManagedCategories`` under a section when that section enables
        ``MatchSubcategories``. Other instances keep the fast exact-match path
        (one ``category=`` filter per configured category).

        When listing all torrents, owners resolved via :meth:`ArrManager.resolve_owning_category`
        still exclude ``self.categories`` so special categories (failed/recheck placeholders)
        are not gathered — same scope as the ``category=`` branch.
        """
        qbit_manager = self.manager.qbit_manager
        result = []
        seen = set()
        instance_failures = 0
        last_error: Exception | None = None
        for instance_name in qbit_manager.get_all_instances():
            if not self._is_qbit_instance_reachable(instance_name):
                continue
            client = self._get_qbit_client(instance_name)
            if client is None:
                continue
            section = instance_name
            use_full_list = self.manager.qbit_section_needs_full_torrent_list_for_policy_manager(
                section
            )
            if use_full_list:
                try:
                    torrents = client.torrents.info(
                        status_filter="all",
                        sort="added_on",
                        reverse=False,
                    )
                    for torrent in torrents:
                        if not hasattr(torrent, "category"):
                            continue
                        owner = self.manager.resolve_owning_category(
                            getattr(torrent, "category", None),
                            qbit_section=instance_name,
                        )
                        if owner is None:
                            continue
                        # Match the per-category branch: only Arr/qBit-managed categories, not
                        # special PlaceHolderArr keys (failed/recheck) or TorrentPolicyManager.
                        if owner not in self.categories:
                            continue
                        if "qBitrr-ignored" in torrent.tags:
                            continue
                        key = (instance_name, torrent.hash)
                        if key in seen:
                            continue
                        seen.add(key)
                        result.append((instance_name, torrent))
                except _QBIT_READ_RETRY_EXCEPTIONS as e:
                    self.logger.warning(
                        "Failed to get monitored torrents from instance '%s': %s",
                        instance_name,
                        e,
                    )
                    instance_failures += 1
                    last_error = e
                continue
            for cat in self.categories:
                try:
                    torrents = client.torrents.info(
                        status_filter="all",
                        category=cat,
                        sort="added_on",
                        reverse=False,
                    )
                    for torrent in torrents:
                        if not hasattr(torrent, "category"):
                            continue
                        if torrent.category not in self.categories:
                            continue
                        if "qBitrr-ignored" in torrent.tags:
                            continue
                        key = (instance_name, torrent.hash)
                        if key in seen:
                            continue
                        seen.add(key)
                        result.append((instance_name, torrent))
                except _QBIT_READ_RETRY_EXCEPTIONS as e:
                    self.logger.warning(
                        "Failed to get monitored torrents from instance '%s' category '%s': %s",
                        instance_name,
                        cat,
                        e,
                    )
                    instance_failures += 1
                    last_error = e
        if instance_failures and not result:
            if last_error is not None:
                raise last_error
            raise qbittorrentapi.exceptions.APIError(
                "Failed to fetch monitored torrents from all qBit instances"
            )
        return result

    def _sync_tracker_tags_before_sort(self) -> None:
        """
        Refresh tracker checks and managed AddTags labels before queue sorting.

        ``TorrentPolicyManager`` is the single owner of this path when sorting
        is enabled, so Arr loops can skip duplicate tracker/tag sync work.
        """
        torrents_with_instances = with_retry(
            self._collect_monitored_torrents,
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
        )
        if not torrents_with_instances:
            self.logger.debug("Pre-sort tracker/tag sync skipped: no monitored torrents")
            return
        managed_tag_pool = ArrBase.merge_global_tracker_configured_add_tags()
        for instance_name, torrent in torrents_with_instances:
            with contextlib.suppress(qbittorrentapi.NotFound404Error):
                self._process_single_torrent_trackers(
                    torrent,
                    instance_name=instance_name,
                    managed_tag_pool=managed_tag_pool,
                )
        self.logger.debug(
            "Pre-sort tracker/tag sync processed %d torrents",
            len(torrents_with_instances),
        )

    def _validate_qbit_preflight(self) -> None:
        if not self._is_any_qbit_instance_reachable():
            raise DelayLoopException(
                length=get_loop_sleep_timer_effective(), error_type="no_downloads"
            )
        if not has_internet(self._get_primary_qbit_client()):
            self.manager.qbit_manager.should_delay_torrent_scan = True
            raise DelayLoopException(
                length=get_no_internet_sleep_timer_effective(), error_type="internet"
            )
        if self.manager.qbit_manager.should_delay_torrent_scan:
            raise DelayLoopException(
                length=get_no_internet_sleep_timer_effective(), error_type="delay"
            )

    def process_torrents(self):
        try:
            try:
                self._sync_free_space_settings_from_config()
                self._validate_qbit_preflight()

                if self.enable_tracker_sort:
                    self.logger.debug(
                        "TorrentPolicyManager workflow: pre-sort tracker/tag sync -> queue sort -> free-space"
                    )
                    self._torrent_important_trackers_cache.clear()
                    self._sync_tracker_tags_before_sort()
                    self._torrent_important_trackers_cache.clear()
                    self._sort_torrents_by_tracker_priority()
                else:
                    self.logger.debug(
                        "TorrentPolicyManager tracker sorting disabled: Arr loops retain tracker/tag sync ownership"
                    )

                if not self.enable_free_space:
                    # Flush any pending pause/resume actions from previous loop state.
                    self.process()
                    return

                if self._free_space_folder_is_auto:
                    _p = self._first_existing_parent(self._disk_usage_path)
                    if _p:
                        self._path_for_disk_usage = _p

                self.current_free_space = (
                    shutil.disk_usage(self._path_for_disk_usage).free - self._min_free_space_bytes
                )
                torrents_with_instances = with_retry(
                    self._collect_monitored_torrents,
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
                )
                self.category_torrent_count = len(torrents_with_instances)
                self.free_space_tagged_count = sum(
                    1
                    for instance_name, torrent in torrents_with_instances
                    if self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
                )
                if not torrents_with_instances:
                    # Ensure queued pause/resume actions still apply when monitored torrents disappear.
                    self.process()
                    return
                sorted_torrents = sorted(
                    torrents_with_instances,
                    key=lambda i: ArrBase._torrent_queue_position_sort_key(i[1]),
                )
                for instance_name, torrent in sorted_torrents:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(torrent, instance_name=instance_name)
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except qbittorrentapi.exceptions.APIError as e:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
                raise DelayLoopException(length=300, error_type="qbit")
            except qbittorrentapi.exceptions.APIConnectionError:
                self.logger.warning("Max retries exceeded")
                raise DelayLoopException(length=300, error_type="qbit")
            except DelayLoopException:
                raise
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except DelayLoopException:
            raise

    def run_search_loop(self):
        return
