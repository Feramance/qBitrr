"""Torrent batch side-effects pipeline role composed into ArrBase.

Call graph (per loop):
  Arr.process_torrents → TorrentDispatch._process_single_torrent
  → TorrentInspect._process_single_torrent_* (decide) → Arr.process
  → TorrentBatch._process_* (pause / import / fail / resume / file priority).
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from collections.abc import Iterable

import qbittorrentapi

from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    _QBIT_TORRENT_DELETE_EXCEPTIONS,
    _QBIT_WRITE_RETRY_EXCEPTIONS,
    _collect_instance_hash_map_hashes,
    execute_command,
    validate_and_return_torrent_file,
    with_retry,
)


class TorrentBatch:
    def _import_file_allowlist_status(
        self, torrent: qbittorrentapi.TorrentDictionary, path: pathlib.Path
    ) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
        """Return allowed and disallowed files visible at an Arr import path."""
        content_path = pathlib.Path(torrent.content_path)
        if content_path.is_file():
            # validate_and_return_torrent_file expands a single-file torrent to its
            # parent for Arr. Do not let unrelated sibling files affect this torrent.
            files = [content_path]
        elif path.is_dir():
            files = []
            for torrent_file in getattr(torrent, "files", ()):
                file_name = getattr(torrent_file, "name", None)
                if not file_name:
                    continue
                relative_path = pathlib.Path(file_name)
                candidates = [path / relative_path]
                # qBittorrent may report the torrent name as the first path
                # component even when the content path already points at that
                # folder. Support that layout without scanning unrelated files.
                if relative_path.parts and relative_path.parts[0] == path.name:
                    candidates.append(path / pathlib.Path(*relative_path.parts[1:]))
                for candidate in candidates:
                    if candidate.is_file():
                        files.append(candidate)
                        break
        else:
            files = []
        allowed: list[pathlib.Path] = []
        disallowed: list[pathlib.Path] = []
        for candidate in files:
            if candidate.name in {"desktop.ini", ".DS_Store"}:
                continue
            excluded_folder = self.folder_exclusion_regex and any(
                self.folder_exclusion_regex_re.search(parent.name.lower())
                for parent in candidate.relative_to(path).parents
                if parent.name
            )
            excluded_name = self.file_name_exclusion_regex and (
                (match := self.file_name_exclusion_regex_re.search(candidate.name))
                and match.group()
            )
            if (
                not excluded_folder
                and not excluded_name
                and (
                    not self.file_extension_allowlist
                    or (
                        (match := self.file_extension_allowlist_re.search(candidate.suffix))
                        and match.group()
                    )
                )
            ):
                allowed.append(candidate)
            elif candidate.suffix.lower() != ".parts":
                disallowed.append(candidate)
        return allowed, disallowed

    def _enforce_import_file_allowlist(
        self, torrent: qbittorrentapi.TorrentDictionary, path: pathlib.Path, instance_name: str
    ) -> bool:
        """Ensure a completed download is allowlist-safe before invoking Arr."""
        allowed, disallowed = self._import_file_allowlist_status(torrent, path)
        if not allowed:
            if self._hnr_allows_delete(torrent, "all-files-excluded deletion"):
                self._mark_for_deletion(
                    torrent, "all-files-excluded deletion", instance_name=instance_name
                )
            return False
        if disallowed and self.auto_delete:
            for candidate in disallowed:
                self.remove_and_maybe_blocklist(None, candidate)
            allowed, disallowed = self._import_file_allowlist_status(torrent, path)

        if not allowed:
            if self._hnr_allows_delete(torrent, "all-files-excluded deletion"):
                self._mark_for_deletion(
                    torrent, "all-files-excluded deletion", instance_name=instance_name
                )
            return False
        if not disallowed:
            return True

        warning_cache = self.allowlist_import_warning_cache
        if torrent.hash not in warning_cache:
            self.logger.warning(
                "Import blocked: disallowed files remain and Torrent.AutoDelete is disabled or "
                "could not remove them | %s (%s) | %s",
                torrent.name,
                torrent.hash,
                [str(candidate) for candidate in disallowed],
            )
            warning_cache.add(torrent.hash)
        return False

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
                if torrent.hash not in self.cleaned_torrents:
                    continue
                if not self._enforce_import_file_allowlist(torrent, path, instance_name):
                    continue
                scan_succeeded = False
                try:
                    scan_commands = {
                        "sonarr": "DownloadedEpisodesScan",
                        "radarr": "DownloadedMoviesScan",
                        "lidarr": "DownloadedAlbumsScan",
                        "readarr": "DownloadedBooksScan",
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
        self,
        hash_: str,
        entry: int,
        skip_blacklist: set[str],
        remove_from_client: bool = False,
        object_id: object = None,
    ) -> None:
        """Remove one Arr queue entry and search again using its saved media identity."""
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
        object_id = object_id if object_id is not None else self.requeue_cache.get(entry)
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

    def _log_deletion_summary_line(self, candidates: int, removed: int, pending: int) -> None:
        """Report actual client outcomes, counting deferred refusals as blocked."""
        self.logger.info(
            "Deletion summary: candidates=%d, blocked=%d, pending=%d, confirmed_removed=%d",
            candidates,
            candidates - removed - pending,
            pending,
            removed,
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
        stalled_since = getattr(self, "_stalled_up_since", None)
        for h in hashes:
            self.cleaned_torrents.discard(h)
            self.sent_to_scan_hashes.discard(h)
            if stalled_since is not None:
                stalled_since.pop(h, None)
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
        """Queue Arr cleanup only for confirmed client removals."""
        if not to_delete_all:
            return
        if cross_arr:
            for arr in self.manager.managed_objects.values():
                if payload := arr.process_entries(to_delete_all):
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._queue_failed_delete(hash_, entry, skip_blacklist)
                arr._retry_pending_queue_deletes()
        else:
            self.needs_cleanup = True
            payload = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._queue_failed_delete(hash_, entry, skip_blacklist)
            self._retry_pending_queue_deletes()

    def _removal_queue_followups(
        self, hashes: set[str], skip_blacklist: set[str], *, cross_arr: bool = False
    ) -> dict[str, list[tuple]]:
        """Snapshot Arr queue and media identities before attempting client deletion."""
        targets = {hash_.lower() for hash_ in hashes}
        followups = defaultdict(list)
        arrs = self.manager.managed_objects.values() if cross_arr else [self]
        for arr in arrs:
            for hash_, entry in getattr(arr, "cache", {}).items():
                if hash_.lower() in targets:
                    followups[hash_.lower()].append(
                        (
                            arr,
                            entry,
                            hash_,
                            hash_.upper() in skip_blacklist,
                            getattr(arr, "requeue_cache", {}).get(entry),
                        )
                    )
        return dict(followups)

    def _queue_failed_delete(
        self, hash_: str, entry: int, skip_blacklist: set[str], *, object_id: object = None
    ) -> None:
        """Keep confirmed removal work independently of future torrent/Arr observations."""
        if not hasattr(self, "_pending_queue_deletes"):
            self._pending_queue_deletes = {}
        self._pending_queue_deletes.setdefault(
            entry,
            (
                hash_,
                hash_ in skip_blacklist,
                object_id if object_id is not None else self.requeue_cache.get(entry),
            ),
        )

    def _retry_pending_queue_deletes(self) -> None:
        """Retry queue cleanup and replacement searches after the torrent is gone."""
        for entry, (hash_, skip, object_id) in list(
            getattr(self, "_pending_queue_deletes", {}).items()
        ):
            try:
                self._process_failed_individual(
                    hash_, entry, {hash_} if skip else set(), object_id=object_id
                )
            except Exception as exc:
                self.logger.warning(
                    "Arr queue cleanup will retry %s: %s", entry, type(exc).__name__
                )
            else:
                del self._pending_queue_deletes[entry]

    def _process_failed(self) -> None:
        self._process_failed_deletes(
            use_qbit_retry=True,
            warn_if_missing=False,
            cross_arr=False,
        )

    def _reset_removal_requests(self, *, cross_arr: bool = False) -> None:
        """Reclassify blocked removals from current observations on every scan."""
        from qBitrr.arss.qbit_side_effects import reconcile_removal_attempts

        reconcile_removal_attempts(self)
        observations = getattr(self, "_removal_observations", {})
        self._blocked_removals = {
            key: value
            for key, value in getattr(self, "_blocked_removals", {}).items()
            if key in observations
        }
        self._removal_observations = {}
        # Queue retries must run even when the next torrent listing is empty.
        if cross_arr:
            for arr in self.manager.managed_objects.values():
                arr._retry_pending_queue_deletes()
        else:
            self._retry_pending_queue_deletes()
        for name in (
            "delete",
            "remove_from_qbit",
            "skip_blacklist",
            "missing_files_post_delete",
            "downloads_with_bad_error_message_blocklist",
            "delete_by_instance",
            "remove_from_qbit_by_instance",
        ):
            getattr(self, name, {}).clear()
        self._removal_candidates = {}
        self._removal_reasons = {}

    def _process_failed_deletes(
        self,
        *,
        use_qbit_retry: bool,
        warn_if_missing: bool,
        cross_arr: bool,
    ) -> None:
        """Delete queued failed torrents and optionally dispatch Arr queue deletes."""
        if cross_arr:
            for arr in self.manager.managed_objects.values():
                arr._retry_pending_queue_deletes()
        else:
            self._retry_pending_queue_deletes()
        to_delete_all = self.delete.union(
            self.missing_files_post_delete, self.downloads_with_bad_error_message_blocklist
        )
        queue_delete_targets = set(to_delete_all)
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        queue_followups = self._removal_queue_followups(
            queue_delete_targets, skip_blacklist, cross_arr=cross_arr
        )
        if not (
            to_delete_all
            or self.remove_from_qbit
            or self.skip_blacklist
            or self.remove_from_qbit_by_instance
            or self.delete_by_instance
        ):
            return
        self._log_deletion_sample_debug(to_delete_all)
        from qBitrr.arss.qbit_side_effects import (
            complete_removal_followups,
            delete_hashes_on_primary,
            delete_hashes_per_instance,
            resolve_removal_torrent,
        )

        if "default" not in self.manager.qbit_manager.get_all_instances():
            for mapping in (self.remove_from_qbit_by_instance, self.delete_by_instance):
                for hash_ in list(mapping.get("default", set())):
                    current = resolve_removal_torrent(self, hash_)
                    if current:
                        for name in ("_removal_candidates", "_removal_reasons"):
                            records = getattr(self, name, {})
                            if ("default", hash_) in records:
                                records[(current[0], hash_)] = records.pop(("default", hash_))
                        mapping.setdefault(current[0], set()).add(hash_)
                        mapping["default"].discard(hash_)
                if "default" in mapping and not mapping["default"]:
                    del mapping["default"]
        per_instance_batches: dict[str, set[str]] = {}
        for inst_name, hashes in self.remove_from_qbit_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        for inst_name, hashes in self.delete_by_instance.items():
            if hashes:
                per_instance_batches.setdefault(inst_name, set()).update(hashes)
        candidate_pairs = {
            (instance, hash_.lower())
            for instance, hashes in per_instance_batches.items()
            for hash_ in hashes
        }
        mapped_hashes = {hash_ for _, hash_ in candidate_pairs}
        legacy_hashes = to_delete_all | self.remove_from_qbit | self.skip_blacklist
        legacy_targets = {hash_.lower() for hash_ in legacy_hashes} - mapped_hashes
        candidate_count = len(candidate_pairs) + len(legacy_targets)
        confirmed_pairs = delete_hashes_per_instance(
            self,
            per_instance_batches,
            use_qbit_retry=use_qbit_retry,
            queue_followups=queue_followups,
        )
        for instance, hash_ in confirmed_pairs:
            for mapping in (self.remove_from_qbit_by_instance, self.delete_by_instance):
                if instance in mapping:
                    mapping[instance].discard(hash_)
                    if not mapping[instance]:
                        del mapping[instance]
        pending_per_instance = {
            hash_.lower()
            for hash_ in _collect_instance_hash_map_hashes(
                self.delete_by_instance, self.remove_from_qbit_by_instance
            )
        }
        per_instance_deleted = {
            hash_ for _, hash_ in confirmed_pairs if hash_.lower() not in pending_per_instance
        }
        deleted_hashes = set(per_instance_deleted)
        to_delete_default = {
            hash_ for hash_ in to_delete_all if hash_.lower() not in mapped_hashes
        }
        primary_pairs: set[tuple[str, str]] = set()
        if self.remove_from_qbit or self.skip_blacklist or to_delete_default:
            if to_delete_default:
                primary_pairs.update(
                    delete_hashes_on_primary(
                        self,
                        to_delete_default,
                        use_qbit_retry=use_qbit_retry,
                        warn_if_missing=warn_if_missing,
                        error_label=(
                            "from qBit (to_delete_all)" if warn_if_missing else "from qBit"
                        ),
                        queue_followups=queue_followups,
                    )
                )
            if self.remove_from_qbit or self.skip_blacklist:
                handled_hashes = mapped_hashes | {
                    hash_.lower() for _, hash_ in confirmed_pairs | primary_pairs
                }
                rest = {
                    hash_
                    for hash_ in self.remove_from_qbit | self.skip_blacklist
                    if hash_.lower() not in handled_hashes
                }
                primary_pairs.update(
                    delete_hashes_on_primary(
                        self,
                        rest,
                        use_qbit_retry=use_qbit_retry,
                        warn_if_missing=warn_if_missing,
                        error_label=(
                            "from qBit (remove/blacklist)" if warn_if_missing else "from qBit"
                        ),
                        queue_followups=queue_followups,
                    )
                )
            primary_deleted = {hash_ for _, hash_ in primary_pairs}
            self._evict_hashes_from_qbit_side_caches(deleted_hashes | primary_deleted)
        primary_deleted = {hash_ for _, hash_ in primary_pairs}
        confirmed_deleted = deleted_hashes | primary_deleted
        self._evict_hashes_from_qbit_side_caches(confirmed_deleted)
        removed_hashes = {hash_.lower() for hash_ in confirmed_deleted}
        dispatch_targets = {
            hash_ for hash_ in queue_delete_targets if hash_.lower() in removed_hashes
        }
        if dispatch_targets:
            complete_removal_followups(self, dispatch_targets)
            self._process_failed_dispatch_queue_deletes(
                dispatch_targets, skip_blacklist, cross_arr=cross_arr
            )
        removed_pairs = {
            (instance, hash_.lower()) for instance, hash_ in confirmed_pairs | primary_pairs
        }
        removed_legacy = {hash_ for _, hash_ in removed_pairs} & legacy_targets
        pending_pairs = {
            (instance, hash_.lower())
            for instance, hash_ in getattr(self, "_pending_client_removals", {})
        }
        pending_legacy = ({hash_ for _, hash_ in pending_pairs} & legacy_targets) - removed_legacy
        pending_count = len((pending_pairs & candidate_pairs) - removed_pairs) + len(
            pending_legacy
        )
        self._log_deletion_summary_line(
            candidate_count,
            len(removed_pairs & candidate_pairs) + len(removed_legacy),
            pending_count,
        )
        for requests in (
            self.missing_files_post_delete,
            self.downloads_with_bad_error_message_blocklist,
            self.skip_blacklist,
            self.remove_from_qbit,
            self.delete,
        ):
            requests.difference_update(
                {hash_ for hash_ in requests if hash_.lower() in removed_hashes}
            )

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
                self.cleaned_torrents.discard(hash_)
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
                    self.cleaned_torrents.add(hash_)
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
                self.cleaned_torrents.discard(hash_)
                try:
                    self._apply_file_priority_update(client, hash_, files)
                    self.cleaned_torrents.add(hash_)
                except Exception:
                    still_pending_by_instance[instance_name][hash_] = files
        self.change_priority_by_instance = still_pending_by_instance

    def _process_resume(self) -> None:
        from qBitrr.arss.qbit_side_effects import resume_hashes_by_instance, resume_legacy_hash_set

        resume_hashes_by_instance(self, warn_missing_client=True)
        resume_legacy_hash_set(self)
