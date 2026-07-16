"""Torrent processing mixin extracted from Arr."""

from __future__ import annotations

from qBitrr.arss._shared import *


class TorrentInspectorMixin:
    @property
    def is_alive(self) -> bool:
        try:
            if 1 in self.expiring_bool:
                return True
            if self.session is None:
                self.expiring_bool.add(1)
                return True
            req = self.session.get(
                f"{self.uri}/api/v3/system/status",
                timeout=10,
                headers={"X-Api-Key": self.apikey},
                verify=not self.skip_tls_verify_servarr,
            )
            req.raise_for_status()
            self.logger.trace("Successfully connected to %s", self.uri)
            self.expiring_bool.add(1)
            return True
        except requests.HTTPError:
            self.expiring_bool.add(1)
            return True
        except requests.RequestException:
            self.logger.warning("Could not connect to %s", self.uri)
            # Clear the cache to ensure we retry on next check
            with contextlib.suppress(KeyError):
                self.expiring_bool.remove(1)
        return False

    _METADATA_STUCK_STATES = (
        TorrentStates.METADATA_DOWNLOAD,
        TorrentStates.FORCED_METADATA_DOWNLOAD,
    )

    @staticmethod
    def _is_metadata_stuck_state(torrent: TorrentDictionary) -> bool:
        """True when qBittorrent is fetching torrent metadata (metaDL / forcedMetaDL)."""
        return torrent.state_enum in TorrentInspectorMixin._METADATA_STUCK_STATES

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
            TorrentStates.QUEUED_DOWNLOAD,
        )

    @staticmethod
    def _is_missing_files_torrent(torrent: TorrentDictionary) -> bool:
        """True if torrent is in missing-files state (delete from client, no blacklist)."""
        if torrent.state_enum == TorrentStates.MISSING_FILES:
            return True
        if torrent.state_enum == TorrentStates.ERROR:
            raw = getattr(torrent, "state", None)
            if raw is None and hasattr(torrent, "get"):
                raw = torrent.get("state")
            if isinstance(raw, str):
                return raw == "missingFiles" or "missing" in raw.lower()
        return False

    @staticmethod
    def is_uploading_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_complete_state(torrent: TorrentDictionary) -> bool:
        """Returns True if the State is categorized as Complete."""
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_queue_seeding_for_sort(torrent: TorrentDictionary) -> bool:
        """
        True if the torrent is on qBittorrent's seeding/upload side of the queue.

        Used by :meth:`_sort_torrents_by_tracker_priority` (separate from
        :meth:`is_complete_state`, which drives other Arr import/seeding logic).
        Includes forced upload and recheck-after-complete so ``topPrio`` targets
        the correct queue (aligned with qBittorrent UI).
        """
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
            TorrentStates.FORCED_UPLOAD,
            TorrentStates.CHECKING_UPLOAD,
        )

    @staticmethod
    def _normalize_torrent_queue_priority_value(torrent: TorrentDictionary) -> int:
        """Normalize Web API ``priority`` (queue position; ``-1`` when queuing disabled)."""
        raw = getattr(torrent, "priority", -1)
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def _torrent_queue_position_sort_key(torrent: TorrentDictionary) -> tuple[bool, int]:
        """Sort key matching qBittorrent queue ordering (active queue first, then position)."""
        nq = TorrentInspectorMixin._normalize_torrent_queue_priority_value(torrent)
        return (not (nq > 0), nq)

    @staticmethod
    def _normalize_torrent_added_on_value(torrent: TorrentDictionary) -> int:
        """Normalize qBittorrent ``added_on`` timestamp for deterministic ordering."""
        raw = getattr(torrent, "added_on", 0)
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def is_downloading_state(torrent: TorrentDictionary) -> bool:
        """Returns True if the State is categorized as Downloading."""
        return torrent.state_enum in (TorrentStates.DOWNLOADING, TorrentStates.PAUSED_DOWNLOAD)

    def _process_single_torrent_failed_cat(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self._mark_for_deletion(torrent, "manually failed", instance_name=instance_name)

    def _process_single_torrent_recheck_cat(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self.logger.notice(
            "Re-checking manually set torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.recheck_by_instance.setdefault(instance_name, set()).add(torrent.hash)

    def _mark_for_deletion(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        ratio_limit=None,
        seeding_time_limit=None,
        instance_name: str = "default",
    ) -> None:
        """Mark torrent for deletion and log reason with current stats and effective limits."""
        extra = ""
        if ratio_limit is not None or seeding_time_limit is not None:
            parts = []
            if ratio_limit is not None:
                parts.append("ratio_limit=%s" % (ratio_limit if ratio_limit > 0 else "unset"))
            if seeding_time_limit is not None:
                parts.append(
                    "seeding_time_limit=%s"
                    % (seeding_time_limit if seeding_time_limit > 0 else "unset")
                )
            extra = " [%s]" % ", ".join(parts)
        self.logger.info(
            "Marking for deletion (%s): [Progress: %s%%][Ratio: %s][Seeding time: %s] | %s (%s)%s",
            reason,
            round(torrent.progress * 100, 2),
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            torrent.name,
            torrent.hash,
            extra,
        )
        self.delete.add(torrent.hash)
        self.delete_by_instance.setdefault(instance_name, set()).add(torrent.hash)

    def _process_single_torrent_ignored(self, torrent: qbittorrentapi.TorrentDictionary):
        # Do not touch torrents that are currently being ignored.
        self.logger.trace(
            "Skipping torrent: Ignored state | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_added_to_ignore_cache(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping torrent: Marked for skipping | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_queued_upload(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        leave_alone: bool,
        instance_name: str = "default",
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Queued Upload | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.pause_by_instance[instance_name].add(torrent.hash)
            self.logger.trace(
                "Pausing torrent: Queued Upload | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_stalled_torrent(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        extra: str,
        instance_name: str = "default",
    ):
        # Process torrents who have stalled at this point, only mark for
        # deletion if they have been added more than "IgnoreTorrentsYoungerThan"
        # seconds ago. Metadata downloads use added_on only because last_activity
        # can keep updating during tracker/DHT metadata retries.
        now = time.time()
        younger_threshold = now - self.ignore_torrents_younger_than
        if self._is_metadata_stuck_state(torrent):
            ready_for_removal = torrent.added_on < younger_threshold
        else:
            ready_for_removal = (
                torrent.added_on < younger_threshold and torrent.last_activity < younger_threshold
            )
        if ready_for_removal:
            if self._hnr_allows_delete(torrent, extra):
                self._mark_for_deletion(torrent, extra, instance_name=instance_name)
        else:
            self.logger.trace(
                "Ignoring Stale torrent (%s): "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                extra,
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_percentage_threshold(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        maximum_eta: int,
        instance_name: str = "default",
    ):
        # Ignore torrents who have reached maximum percentage as long as
        # the last activity is within the MaximumETA set for this category
        # For example if you set MaximumETA to 5 mines, this will ignore all
        # torrents that have stalled at a higher percentage as long as there is activity
        # And the window of activity is determined by the current time - MaximumETA,
        # if the last active was after this value ignore this torrent
        # the idea here is that if a torrent isn't completely dead some leecher/seeder
        # may contribute towards your progress.
        # However if its completely dead and no activity is observed, then lets
        # remove it and requeue a new torrent.
        if maximum_eta > 0 and torrent.last_activity < (time.time() - maximum_eta):
            if self._hnr_allows_delete(torrent, "stale high-percentage deletion"):
                self._mark_for_deletion(
                    torrent, "stale high-percentage deletion", instance_name=instance_name
                )
        else:
            self.logger.trace(
                "Skipping torrent: Reached Maximum completed "
                "percentage and is active | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_paused(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self.timed_ignore_cache.add(torrent.hash)
        self.resume_by_instance[instance_name].add(torrent.hash)
        self.logger.debug(
            "Resuming incomplete paused torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_already_sent_to_scan(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping torrent: Already sent for import | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_errored(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self.logger.trace(
            "Rechecking Errored torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.recheck_by_instance.setdefault(instance_name, set()).add(torrent.hash)

    def _process_single_torrent_fully_completed_torrent(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        leave_alone: bool,
        instance_name: str = "default",
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Completed | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        elif not self.in_tags(torrent, "qBitrr-imported", instance_name):
            self.logger.info(
                "Importing Completed torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            content_path = pathlib.Path(torrent.content_path)
            if content_path.is_dir() and content_path.name == torrent.name:
                torrent_folder = content_path
            else:
                if content_path.is_file() and content_path.parent.name == torrent.name:
                    torrent_folder = content_path.parent
                else:
                    torrent_folder = content_path
            self.files_to_cleanup.add((torrent.hash, torrent_folder))
            self.import_torrents.append((torrent, instance_name))

    def _process_single_torrent_missing_files(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        instance_name: str = "default",
    ):
        # Sometimes Sonarr/Radarr does not automatically remove the
        # torrent for some reason,
        # this ensures that we can safely remove it if the client is reporting
        # the status of the client as "Missing files"
        self.logger.info(
            "Deleting torrent with missing files: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        # We do not want to blacklist these!!
        self.remove_from_qbit_by_instance.setdefault(instance_name, set()).add(torrent.hash)

    def _process_single_torrent_uploading(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        leave_alone: bool,
        instance_name: str = "default",
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Queued Upload | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.logger.info(
                "Pausing uploading torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            self.pause_by_instance[instance_name].add(torrent.hash)

    def _process_single_torrent_already_cleaned_up(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping file check: Already been cleaned up | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_delete_slow(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        self.logger.trace(
            "Deleting slow torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        if self._hnr_allows_delete(torrent, "slow torrent deletion"):
            self._mark_for_deletion(torrent, "slow torrent deletion", instance_name=instance_name)

    def _process_single_torrent_delete_cfunmet(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = ""
    ):
        if self._hnr_allows_delete(torrent, "CF unmet deletion"):
            self._mark_for_deletion(
                torrent, "CF unmet deletion", instance_name=instance_name or "default"
            )

    def _process_single_torrent_delete_ratio_seed(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        limit_meta: tuple[dict, dict] | None = None,
        instance_name: str = "default",
    ):
        if limit_meta is not None:
            data_settings, data_torrent = limit_meta
        else:
            try:
                data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
            except _TrackerDataUnavailable:
                self.logger.warning(
                    "Skipping ratio/seed deletion for torrent '%s' (%s) this pass because "
                    "tracker metadata is unavailable",
                    getattr(torrent, "name", "<unknown>"),
                    getattr(torrent, "hash", "<unknown>"),
                )
                return
        r_dat = data_settings.get("ratio_limit", -5)
        r_tor = data_torrent.get("ratio_limit", -5)
        t_dat = data_settings.get("seeding_time_limit", -5)
        t_tor = data_torrent.get("seeding_time_limit", -5)
        ratio_limit = max(r_dat, r_tor) if (r_dat > 0 or r_tor > 0) else -5
        seeding_time_limit = max(t_dat, t_tor) if (t_dat > 0 or t_tor > 0) else -5
        if self._hnr_allows_delete(
            torrent, "ratio/seed limit deletion", data_settings=data_settings
        ):
            self._mark_for_deletion(
                torrent,
                "ratio/seed limit deletion",
                ratio_limit=ratio_limit,
                seeding_time_limit=seeding_time_limit,
                instance_name=instance_name,
            )

    def _process_single_torrent_process_files(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        special_case: bool = False,
        instance_name: str = "default",
    ):
        _remove_files = set()
        total = len(torrent.files)
        if total == 0:
            return
        elif special_case:
            self.special_casing_file_check.add(torrent.hash)
        for file in torrent.files:
            if not hasattr(file, "name"):
                continue
            file_path = pathlib.Path(file.name)
            # Acknowledge files that already been marked as "Don't download"
            if file.priority == 0:
                total -= 1
                continue
            # A folder within the folder tree matched the terms
            # in FolderExclusionRegex, mark it for exclusion.
            if self.folder_exclusion_regex and any(
                self.folder_exclusion_regex_re.search(p.name.lower())
                for p in file_path.parents
                if (folder_match := p.name)
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Parent: %s  | %s (%s) | %s ",
                    folder_match,
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            # A file matched and entry in FileNameExclusionRegex, mark it for
            # exclusion.
            elif self.file_name_exclusion_regex and (
                (match := self.file_name_exclusion_regex_re.search(file_path.name))
                and match.group()
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Name: %s  | %s (%s) | %s ",
                    match.group(),
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            elif self.file_extension_allowlist and not (
                (match := self.file_extension_allowlist_re.search(file_path.suffix))
                and match.group()
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Extension: %s  | %s (%s) | %s ",
                    file_path.suffix,
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            # If all files in the torrent are marked for exclusion then delete the
            # torrent.
            if total == 0:
                if self._hnr_allows_delete(torrent, "all-files-excluded deletion"):
                    self._mark_for_deletion(
                        torrent, "all-files-excluded deletion", instance_name=instance_name
                    )
            # Mark all bad files and folder for exclusion.
            elif _remove_files:
                self.change_priority_by_instance[instance_name][torrent.hash] = list(_remove_files)

        self.cleaned_torrents.add(torrent.hash)

    def _process_single_completed_paused_torrent(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        leave_alone: bool,
        instance_name: str = "default",
    ):
        if leave_alone:
            self.resume_by_instance[instance_name].add(torrent.hash)
            self.logger.trace(
                "Resuming torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.logger.trace(
                "Skipping torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_unprocessed(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Skipping torrent: Unresolved state: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
