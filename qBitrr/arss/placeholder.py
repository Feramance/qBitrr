from qBitrr.arss._shared import *
from qBitrr.arss.arr import Arr


class PlaceHolderArr(Arr):
    def __init__(self, name: str, manager: ArrManager):
        self.type = "placeholder"
        # Subcategory paths: titlecase each segment for logs/UI; use spaced slashes
        # so ``seed/tleech`` reads as ``Seed / Tleech``.
        display = normalize_category(name) or name
        self._name = " / ".join(s.title() for s in display.split("/")) if display else name
        self.category = normalize_category(name) or name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.files_to_cleanup = set()
        self.import_torrents = []
        self.change_priority = {}
        self.change_priority_by_instance: dict[str, dict[str, list]] = defaultdict(dict)
        self.recheck_by_instance: dict[str, set[str]] = {}
        self.pause = set()
        self.pause_by_instance: dict[str, set[str]] = defaultdict(set)
        self.skip_blacklist = set()
        self.remove_from_qbit = set()
        self.remove_from_qbit_by_instance: dict[str, set[str]] = {}
        self.delete_by_instance: dict[str, set[str]] = {}
        self.delete = set()
        self.resume = set()
        self.resume_by_instance: dict[str, set[str]] = defaultdict(set)
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.ignore_torrents_younger_than = get_ignore_torrents_younger_than_effective()
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_ignore_cache_2 = ExpiringSet(
            max_age_seconds=self.ignore_torrents_younger_than * 2
        )
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.cleaned_torrents = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.needs_cleanup = False
        self._warned_no_seeding_limits = False
        self._torrent_important_trackers_cache: dict[str, tuple[set[str], set[str]]] = {}
        self._dedicated_qbit_clients: dict[str, qbittorrentapi.Client] = {}
        self.custom_format_unmet_search = False
        self.do_not_remove_slow = False
        self.maximum_eta = CONFIG.get_duration("Settings.Torrent.MaximumETA", fallback=86400)
        self.maximum_deletable_percentage = CONFIG.get(
            "Settings.Torrent.MaximumDeletablePercentage", fallback=0.95
        )
        self.folder_exclusion_regex = None
        self.file_name_exclusion_regex = None
        self.file_extension_allowlist = None
        self.folder_exclusion_regex_re = None
        self.file_name_exclusion_regex_re = None
        self.file_extension_allowlist_re = None
        self.re_search_stalled = False
        self.monitored_trackers = []
        self._host_to_config_uri = {}
        self._add_trackers_if_missing = set()
        self._remove_trackers_if_exists = set()
        self._monitored_tracker_urls = set()
        self.remove_dead_trackers = False
        self._remove_tracker_hosts = set()
        self._normalized_bad_tracker_msgs = set()
        self.seeding_mode_global_remove_torrent = -1
        self.seeding_mode_global_max_upload_ratio = -1
        self.seeding_mode_global_max_seeding_time = -1
        self.seeding_mode_global_download_limit = -1
        self.seeding_mode_global_upload_limit = -1
        self.seeding_mode_global_bad_tracker_msg = []
        self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)
        self._configure_worker_logging(self._name)
        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)
        self.stalled_delay = -1
        self.allowed_stalled = False
        if self.category in self.manager.qbit_managed_categories:
            self._apply_qbit_seeding_config()
        self.search_missing = False
        self.session = None
        self.search_setup_completed = False
        self.last_search_description: str | None = None
        self.last_search_timestamp: str | None = None
        self.queue_active_count: int = 0
        self.category_torrent_count: int = 0
        self.free_space_tagged_count: int = 0
        if TAGLESS:
            self.register_search_mode()
        else:
            self.torrents = None
            self.db = None
            self.search_setup_completed = True
        self.logger.hnotice("Starting %s monitor", self._name)

    def _get_models(
        self,
    ) -> tuple[
        None,
        None,
        None,
        None,
        type[TorrentLibrary] | None,
    ]:
        """PlaceHolderArr has no file/queue models; only TorrentLibrary when TAGLESS."""
        return None, None, None, None, (TorrentLibrary if TAGLESS else None)

    def custom_format_unmet_check(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """PlaceHolderArr does not use Arr queue; never trigger custom-format branch."""
        return False

    def _apply_qbit_seeding_config(self) -> None:
        """Load qBit CategorySeeding/Trackers for this category's owning qBit section."""
        section = self.manager.qbit_managed_category_sections.get(self.category, "qBit")
        seeding = load_qbit_seeding_config(section, include_ignore_younger=False)
        effective = dict(seeding["default_seeding"])
        if self.category in seeding["category_overrides"]:
            effective.update(seeding["category_overrides"][self.category])
        self.seeding_mode_global_remove_torrent = effective.get("RemoveTorrent", -1)
        self.seeding_mode_global_max_upload_ratio = effective.get("MaxUploadRatio", -1)
        self.seeding_mode_global_max_seeding_time = effective.get("MaxSeedingTime", -1)
        self.seeding_mode_global_download_limit = effective.get("DownloadRateLimitPerTorrent", -1)
        self.seeding_mode_global_upload_limit = effective.get("UploadRateLimitPerTorrent", -1)
        self.stalled_delay = seeding["stalled_delay"]
        self.allowed_stalled = self.stalled_delay != -1
        self.monitored_trackers = seeding["trackers"]
        self._install_tracker_index(
            build_tracker_index(
                self.monitored_trackers,
                bad_tracker_messages=self.seeding_mode_global_bad_tracker_msg,
            )
        )
        self.logger.debug(
            "Applied qBit seeding config from section '%s' for category '%s': "
            "RemoveTorrent=%s, StalledDelay=%s",
            section,
            self.category,
            self.seeding_mode_global_remove_torrent,
            self.stalled_delay,
        )

    def _process_failed(self) -> None:
        """Delete torrents from the correct qBit instance and log any delete failures."""
        to_delete_all = self.delete.union(
            self.missing_files_post_delete, self.downloads_with_bad_error_message_blocklist
        )
        queue_delete_targets = set(to_delete_all)
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        if not (
            to_delete_all
            or self.remove_from_qbit
            or self.skip_blacklist
            or self.remove_from_qbit_by_instance
            or self.delete_by_instance
        ):
            return
        self._log_deletion_summary_line()
        self._log_deletion_sample_debug(to_delete_all)
        deleted_hashes: set[str] = set()
        per_instance_batches: dict[str, set[str]] = {}
        for inst_name, hashes in self.remove_from_qbit_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        for inst_name, hashes in self.delete_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        per_instance_deleted: set[str] = set()
        # Delete per-instance so we use the correct qBit client.
        for instance_name, hashes in per_instance_batches.items():
            client = self._get_qbit_client(instance_name)
            if client is None:
                self.logger.warning(
                    "Cannot delete %d torrent(s) from qBit instance '%s': no client",
                    len(hashes),
                    instance_name,
                )
                continue
            try:
                with_retry(
                    lambda c=client, h=hashes: c.torrents_delete(hashes=h, delete_files=True),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
                )
                per_instance_deleted.update(hashes)
                deleted_hashes.update(hashes)
            except _QBIT_TORRENT_DELETE_EXCEPTIONS as e:
                self.logger.error(
                    "Failed to delete %d torrent(s) from qBit instance '%s': %s",
                    len(hashes),
                    instance_name,
                    e,
                )
        _prune_instance_hash_map(self.remove_from_qbit_by_instance, per_instance_deleted)
        _prune_instance_hash_map(self.delete_by_instance, per_instance_deleted)
        pending_per_instance = _collect_instance_hash_map_hashes(
            self.delete_by_instance, self.remove_from_qbit_by_instance
        )
        to_delete_all = to_delete_all - per_instance_deleted
        to_delete_default = to_delete_all - pending_per_instance
        temp_to_delete: set[str] = set()
        # Remaining remove_from_qbit/skip_blacklist and to_delete_default via default client.
        if self.remove_from_qbit or self.skip_blacklist or to_delete_default:
            if to_delete_default:
                legacy_client = self._get_legacy_default_qbit_client()
                if legacy_client is not None:
                    try:
                        with_retry(
                            lambda c=legacy_client: c.torrents_delete(
                                hashes=to_delete_default, delete_files=True
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
                        )
                        temp_to_delete.update(to_delete_default)
                    except _QBIT_TORRENT_DELETE_EXCEPTIONS as e:
                        self.logger.error(
                            "Failed to delete %d torrent(s) from qBit (to_delete_all): %s",
                            len(to_delete_default),
                            e,
                        )
                else:
                    self.logger.warning("Cannot delete to_delete_all: no qBit client available")
            if self.remove_from_qbit or self.skip_blacklist:
                rest = (self.remove_from_qbit.union(self.skip_blacklist)) - deleted_hashes
                legacy_client = self._get_legacy_default_qbit_client()
                if rest and legacy_client is not None:
                    try:
                        with_retry(
                            lambda c=legacy_client, h=rest: c.torrents_delete(
                                hashes=h, delete_files=True
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
                        )
                        temp_to_delete.update(rest)
                    except _QBIT_TORRENT_DELETE_EXCEPTIONS as e:
                        self.logger.error(
                            "Failed to delete %d torrent(s) from qBit (remove/blacklist): %s",
                            len(rest),
                            e,
                        )
                elif rest:
                    self.logger.warning(
                        "Cannot delete %d torrent(s): no qBit client available",
                        len(rest),
                    )
            cleaned_hashes = deleted_hashes.union(temp_to_delete)
            self._evict_hashes_from_qbit_side_caches(cleaned_hashes)
        confirmed_deleted = deleted_hashes | temp_to_delete
        dispatch_targets = confirmed_deleted & queue_delete_targets
        if dispatch_targets:
            self._process_failed_dispatch_queue_deletes(
                dispatch_targets, skip_blacklist, cross_arr=True
            )
        all_deleted = confirmed_deleted
        if self.missing_files_post_delete:
            self.missing_files_post_delete -= all_deleted
        if self.downloads_with_bad_error_message_blocklist:
            self.downloads_with_bad_error_message_blocklist -= all_deleted
        self.skip_blacklist -= all_deleted
        self.remove_from_qbit -= all_deleted
        self.delete -= all_deleted

    def _process_errored(self):
        # Recheck all torrents marked for rechecking on their owning qBit instance.
        if not self.recheck_by_instance:
            return
        qbit_manager = self.manager.qbit_manager
        still_pending: dict[str, set[str]] = {}
        for instance_name, hashes in self.recheck_by_instance.items():
            if not hashes:
                continue
            client = self._get_qbit_client(instance_name)
            if client is None:
                self.logger.warning(
                    "Cannot recheck %d torrent(s) on qBit instance '%s': no client",
                    len(hashes),
                    instance_name,
                )
                still_pending[instance_name] = set(hashes)
                continue
            temp = defaultdict(list)
            updated_recheck = list(hashes)
            for h in updated_recheck:
                if c := qbit_manager.cache.get(h):
                    temp[c].append(h)
            try:
                with_retry(
                    lambda c=client, h=updated_recheck: c.torrents_recheck(torrent_hashes=h),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
                )
            except _QBIT_TORRENT_DELETE_EXCEPTIONS as e:
                self.logger.error(
                    "Failed to recheck %d torrent(s) on qBit instance '%s': %s",
                    len(updated_recheck),
                    instance_name,
                    e,
                )
                still_pending[instance_name] = set(hashes)
                continue
            for category, torrent_hashes in temp.items():
                with contextlib.suppress(Exception):
                    with_retry(
                        lambda c=client, cat=category, hs=torrent_hashes: c.torrents_set_category(
                            torrent_hashes=hs, category=cat
                        ),
                        retries=3,
                        backoff=0.5,
                        max_backoff=3,
                        exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
                    )
            for k in updated_recheck:
                self.timed_ignore_cache.add(k)
        self.recheck_by_instance = still_pending

    def process(self):
        self._process_resume()
        self._process_paused()
        self._process_errored()
        self._process_file_priority()
        self._process_failed()
        self.import_torrents.clear()
        with contextlib.suppress(AttributeError):
            self.files_to_cleanup.clear()

    def process_torrents(self):
        try:
            try:
                torrents_with_instances = with_retry(
                    lambda: self._get_torrents_from_all_instances(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
                )

                torrents_with_instances = [
                    (instance, t)
                    for instance, t in torrents_with_instances
                    if getattr(t, "category", None) == self.category
                ]
                self._warned_no_seeding_limits = False
                self.category_torrent_count = len(torrents_with_instances)
                self._torrent_important_trackers_cache.clear()
                if not torrents_with_instances:
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

                managed_tag_pool = Arr.merge_global_tracker_configured_add_tags()
                for instance_name, torrent in torrents_with_instances:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(
                            torrent,
                            instance_name=instance_name,
                            managed_tag_pool=managed_tag_pool,
                        )
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
