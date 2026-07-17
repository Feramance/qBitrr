"""Torrent batch side-effects mixin extracted from Arr.

Call graph (per loop):
  Arr.process_torrents → TorrentDispatcherMixin._process_single_torrent
  → TorrentInspectorMixin._process_single_torrent_* (decide) → Arr.process
  → TorrentBatchMixin._process_* (pause / import / fail / resume / file priority).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import qbittorrentapi

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    _QBIT_TORRENT_DELETE_EXCEPTIONS,
    _QBIT_WRITE_RETRY_EXCEPTIONS,
    _collect_instance_hash_map_hashes,
    _prune_instance_hash_map,
    execute_command,
    validate_and_return_torrent_file,
    with_retry,
)


class TorrentBatchMixin:
    def _process_paused(self) -> None:
        # Pause torrents on their owning qBittorrent instance.
        from qBitrr.arss.qbit_side_effects import pause_hashes_by_instance, pause_legacy_hash_set

        pause_hashes_by_instance(self, warn_missing_client=True, log_names=True)
        pause_legacy_hash_set(self, log_names=True)

    def _process_imports(self) -> None:
        if self.import_torrents:
            self.needs_cleanup = True
            for torrent, instance_name in self.import_torrents:
                if torrent.hash in self.sent_to_scan:
                    continue
                path = validate_and_return_torrent_file(torrent.content_path)
                if not path.exists():
                    self.timed_ignore_cache.add(torrent.hash)
                    self.logger.warning(
                        "Missing Torrent: [%s] %s (%s) - File does not seem to exist: %s",
                        torrent.state_enum,
                        torrent.name,
                        torrent.hash,
                        path,
                    )
                    continue
                if path in self.sent_to_scan:
                    continue
                scan_succeeded = False
                try:
                    scan_commands = {
                        "sonarr": "DownloadedEpisodesScan",
                        "radarr": "DownloadedMoviesScan",
                        "lidarr": "DownloadedAlbumsScan",
                    }
                    scan_cmd = scan_commands.get(self.type)
                    if scan_cmd:
                        _path = str(path)
                        _hash = torrent.hash.upper()
                        _mode = self.import_mode
                        with_retry(
                            lambda: execute_command(
                                self.client,
                                scan_cmd,
                                path=_path,
                                downloadClientId=_hash,
                                importMode=_mode,
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
                        )
                        self.logger.success("%s: %s", scan_cmd, path)
                        scan_succeeded = True
                except Exception as ex:
                    self.logger.error(
                        "Downloaded scan error: [%s][%s][%s][%s]",
                        path,
                        torrent.hash.upper(),
                        self.import_mode,
                        ex,
                    )
                if scan_succeeded:
                    self.sent_to_scan_hashes.add(torrent.hash)
                    self.add_tags(torrent, ["qBitrr-imported"], instance_name)
                    self.sent_to_scan.add(path)
            self.import_torrents.clear()

    def _process_failed_individual(
        self, hash_: str, entry: int, skip_blacklist: set[str], remove_from_client: bool = True
    ) -> None:
        self.logger.debug(
            "Deleting from queue: %s, [%s][Blocklisting:%s][Remove from client:%s]",
            hash_,
            self.manager.qbit_manager.name_cache.get(hash_, "Blocklisted"),
            True if hash_ not in skip_blacklist else False,
            remove_from_client,
        )
        if hash_ not in skip_blacklist:
            self.delete_from_queue(
                id_=entry, remove_from_client=remove_from_client, blacklist=True
            )
        else:
            self.delete_from_queue(
                id_=entry, remove_from_client=remove_from_client, blacklist=False
            )
        object_id = self.requeue_cache.get(entry)
        if self.re_search and object_id:
            self._re_search_failed_media(object_id)

    def _process_errored(self) -> None:
        # Recheck all torrents marked for rechecking on their owning qBit instance.
        if not self.recheck_by_instance:
            return
        self.needs_cleanup = True
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
            updated_recheck = list(hashes)
            try:
                self._qbit_retry(
                    lambda c=client, h=updated_recheck: c.torrents_recheck(torrent_hashes=h)
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
            for k in updated_recheck:
                if k not in self.timed_ignore_cache_2:
                    self.timed_ignore_cache_2.add(k)
                    self.timed_ignore_cache.add(k)
        self.recheck_by_instance = still_pending

    def _log_deletion_summary_line(self) -> None:
        n_delete = len(self.delete)
        n_missing = len(self.missing_files_post_delete)
        n_bad_msg = len(self.downloads_with_bad_error_message_blocklist)
        n_remove = len(self.remove_from_qbit)
        n_remove_by_inst = sum(len(s) for s in self.remove_from_qbit_by_instance.values())
        n_delete_by_inst = sum(len(s) for s in self.delete_by_instance.values())
        n_skip = len(self.skip_blacklist)
        self.logger.info(
            "Deletion summary: delete=%d, missing_files=%d, bad_error_blocklist=%d, "
            "remove_from_qbit=%d, remove_by_instance=%d, delete_by_instance=%d, skip_blacklist=%d",
            n_delete,
            n_missing,
            n_bad_msg,
            n_remove,
            n_remove_by_inst,
            n_delete_by_inst,
            n_skip,
        )

    def _log_deletion_sample_debug(self, to_delete_all: set[str]) -> None:
        if not to_delete_all or not self.logger.isEnabledFor(10):
            return
        sample = list(to_delete_all)[:5]
        names = [self.manager.qbit_manager.name_cache.get(h, h) for h in sample]
        self.logger.debug(
            "Deletion sample (first 5): %s",
            list(zip(sample, names)),
        )

    def _evict_hashes_from_qbit_side_caches(self, hashes: Iterable[str]) -> None:
        qm = self.manager.qbit_manager
        for h in hashes:
            self.cleaned_torrents.discard(h)
            self.sent_to_scan_hashes.discard(h)
            if h in qm.name_cache:
                del qm.name_cache[h]
            if h in qm.cache:
                del qm.cache[h]

    def _process_failed_dispatch_queue_deletes(
        self,
        to_delete_all: set[str],
        skip_blacklist: set[str],
        *,
        cross_arr: bool,
    ) -> None:
        if not to_delete_all:
            return
        if cross_arr:
            for arr in self.manager.managed_objects.values():
                if payload := arr.process_entries(to_delete_all):
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._process_failed_individual(
                                hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                            )
        else:
            self.needs_cleanup = True
            payload = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._process_failed_individual(
                        hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                    )

    def _process_failed(self) -> None:
        self._process_failed_deletes(
            use_qbit_retry=True,
            warn_if_missing=False,
            cross_arr=False,
        )

    def _process_failed_deletes(
        self,
        *,
        use_qbit_retry: bool,
        warn_if_missing: bool,
        cross_arr: bool,
    ) -> None:
        """Delete queued failed torrents and optionally dispatch Arr queue deletes."""
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
        from qBitrr.arss.qbit_side_effects import (
            delete_hashes_on_primary,
            delete_hashes_per_instance,
        )

        per_instance_batches: dict[str, set[str]] = {}
        for inst_name, hashes in self.remove_from_qbit_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        for inst_name, hashes in self.delete_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        after_success = self._evict_hashes_from_qbit_side_caches if use_qbit_retry else None
        per_instance_deleted = delete_hashes_per_instance(
            self,
            per_instance_batches,
            use_qbit_retry=use_qbit_retry,
            after_success=after_success,
        )
        deleted_hashes: set[str] = set(per_instance_deleted)
        _prune_instance_hash_map(self.remove_from_qbit_by_instance, per_instance_deleted)
        _prune_instance_hash_map(self.delete_by_instance, per_instance_deleted)
        pending_per_instance = _collect_instance_hash_map_hashes(
            self.delete_by_instance, self.remove_from_qbit_by_instance
        )
        to_delete_all = to_delete_all - per_instance_deleted
        to_delete_default = to_delete_all - pending_per_instance
        primary_deleted: set[str] = set()
        if self.remove_from_qbit or self.skip_blacklist or to_delete_default:
            if to_delete_default:
                primary_deleted.update(
                    delete_hashes_on_primary(
                        self,
                        to_delete_default,
                        use_qbit_retry=use_qbit_retry,
                        warn_if_missing=warn_if_missing,
                        error_label=(
                            "from qBit (to_delete_all)" if warn_if_missing else "from qBit"
                        ),
                    )
                )
            if self.remove_from_qbit or self.skip_blacklist:
                rest = self.remove_from_qbit.union(self.skip_blacklist) - deleted_hashes
                primary_deleted.update(
                    delete_hashes_on_primary(
                        self,
                        rest,
                        use_qbit_retry=use_qbit_retry,
                        warn_if_missing=warn_if_missing,
                        error_label=(
                            "from qBit (remove/blacklist)" if warn_if_missing else "from qBit"
                        ),
                    )
                )
            self._evict_hashes_from_qbit_side_caches(deleted_hashes | primary_deleted)
        confirmed_deleted = deleted_hashes | primary_deleted
        dispatch_targets = confirmed_deleted & queue_delete_targets
        if dispatch_targets:
            self._process_failed_dispatch_queue_deletes(
                dispatch_targets, skip_blacklist, cross_arr=cross_arr
            )
        all_deleted = confirmed_deleted
        if self.missing_files_post_delete:
            self.missing_files_post_delete -= all_deleted
        if self.downloads_with_bad_error_message_blocklist:
            self.downloads_with_bad_error_message_blocklist -= all_deleted
        self.skip_blacklist -= all_deleted
        self.remove_from_qbit -= all_deleted
        self.delete -= all_deleted

    def _apply_file_priority_update(
        self,
        client: qbittorrentapi.Client,
        hash_: str,
        files: list,
    ) -> None:
        """Set excluded files to 'do not download' on the given qBit client."""
        name = self.manager.qbit_manager.name_cache.get(hash_)
        if name:
            self.logger.debug("Updating file priority on torrent: %s (%s)", name, hash_)
            with_retry(
                lambda c=client, h=hash_, f=files: c.torrents_file_priority(
                    torrent_hash=h, file_ids=f, priority=0
                ),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
        else:
            self.logger.error("Torrent does not exist? %s", hash_)
            raise LookupError(f"Cannot update file priority for unknown torrent hash {hash_}")

    def _process_file_priority(self) -> None:
        # Set all files marked as "Do not download" to not download.
        if self.change_priority or self.change_priority_by_instance:
            self.needs_cleanup = True
        if self.change_priority:
            still_pending_legacy: dict[str, list] = {}
            primary_client = self._get_primary_qbit_client()
            for hash_, files in list(self.change_priority.items()):
                if primary_client is None:
                    name = self.manager.qbit_manager.name_cache.get(hash_, hash_)
                    self.logger.warning(
                        "Cannot update file priority for %s (%s): no qBit client",
                        name,
                        hash_,
                    )
                    still_pending_legacy[hash_] = files
                    continue
                try:
                    self._apply_file_priority_update(primary_client, hash_, files)
                except Exception:
                    still_pending_legacy[hash_] = files
            self.change_priority = still_pending_legacy
        still_pending_by_instance: defaultdict[str, dict[str, list]] = defaultdict(dict)
        for instance_name, hash_map in list(self.change_priority_by_instance.items()):
            if not hash_map:
                continue
            client = self._get_qbit_client(instance_name)
            if client is None:
                self.logger.warning(
                    "Cannot update file priority for %d torrent(s) on qBit instance '%s': no client",
                    len(hash_map),
                    instance_name,
                )
                still_pending_by_instance[instance_name].update(hash_map)
                continue
            for hash_, files in list(hash_map.items()):
                try:
                    self._apply_file_priority_update(client, hash_, files)
                except Exception:
                    still_pending_by_instance[instance_name][hash_] = files
        self.change_priority_by_instance = still_pending_by_instance

    def _process_resume(self) -> None:
        from qBitrr.arss.qbit_side_effects import resume_hashes_by_instance, resume_legacy_hash_set

        resume_hashes_by_instance(self, warn_missing_client=True)
        resume_legacy_hash_set(self)
