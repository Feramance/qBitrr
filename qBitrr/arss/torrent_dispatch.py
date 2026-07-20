"""Torrent decision-tree pipeline role composed into ArrBase.

Call graph (per loop):
  Arr.process_torrents → TorrentDispatch._process_single_torrent
  → TorrentInspect._process_single_torrent_* (decide) → Arr.process
  → TorrentBatch._process_* (pause / import / fail / resume / file priority).
"""

from __future__ import annotations

import contextlib
import time
from datetime import datetime, timedelta

import qbittorrentapi
from qbittorrentapi import TorrentStates

from qBitrr.arss.arr_shared import (
    _extract_tracker_host,
    _parse_qbittorrent_tag_list,
    _TrackerDataUnavailable,
    get_failed_category_effective,
    get_recheck_category_effective,
)


class TorrentDispatch:
    def _process_single_torrent_trackers(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        instance_name: str = "default",
        managed_tag_pool: frozenset[str] | None = None,
    ):
        if torrent.hash in self.tracker_delay:
            return
        self.tracker_delay.add(torrent.hash)
        _remove_urls = set()
        try:
            need_to_be_added, monitored_trackers = self._get_torrent_important_trackers(torrent)
        except _TrackerDataUnavailable:
            return
        tracker_set_changed = False
        if need_to_be_added:
            torrent.add_trackers(need_to_be_added)
            tracker_set_changed = True
        with contextlib.suppress(BaseException):
            for tracker in torrent.trackers:
                tracker_url = getattr(tracker, "url", None)
                message_text = (getattr(tracker, "msg", "") or "").lower()
                remove_for_message = (
                    self.remove_dead_trackers
                    and self._normalized_bad_tracker_msgs
                    and any(
                        keyword in message_text for keyword in self._normalized_bad_tracker_msgs
                    )
                )
                if not tracker_url:
                    continue
                if (
                    remove_for_message
                    or _extract_tracker_host(tracker_url) in self._remove_tracker_hosts
                ):
                    _remove_urls.add(tracker_url)
        if _remove_urls:
            self.logger.trace(
                "Removing trackers from torrent: %s (%s) - %s",
                torrent.name,
                torrent.hash,
                _remove_urls,
            )
            with contextlib.suppress(qbittorrentapi.Conflict409Error):
                torrent.remove_trackers(_remove_urls)
            tracker_set_changed = True
        if tracker_set_changed:
            self._torrent_important_trackers_cache.pop(torrent.hash, None)
            # Tracker membership changed (add/remove), so recompute from fresh data.
            try:
                _, monitored_trackers = self._get_torrent_important_trackers(
                    torrent, use_cache=False
                )
            except _TrackerDataUnavailable:
                return
        most_important_tracker, unique_tags = self._get_most_important_tracker_and_tags(
            monitored_trackers, _remove_urls
        )
        if monitored_trackers and most_important_tracker:
            dl_r = most_important_tracker.get(
                "DownloadRateLimit", self.seeding_mode_global_download_limit
            )
            if dl_r != 0 and torrent.dl_limit != dl_r:
                torrent.set_download_limit(limit=dl_r)
            elif dl_r < 0:
                torrent.set_download_limit(limit=-1)
            ul_r = most_important_tracker.get(
                "UploadRateLimit", self.seeding_mode_global_upload_limit
            )
            if ul_r != 0 and torrent.up_limit != ul_r:
                torrent.set_upload_limit(limit=ul_r)
            elif ul_r < 0:
                torrent.set_upload_limit(limit=-1)
            if (
                r := most_important_tracker.get("SuperSeedMode", False)
            ) and torrent.super_seeding != r:
                torrent.set_super_seeding(enabled=r)

        else:
            dl_r = self.seeding_mode_global_download_limit
            if dl_r != 0 and torrent.dl_limit != dl_r:
                torrent.set_download_limit(limit=dl_r)
            elif dl_r < 0:
                torrent.set_download_limit(limit=-1)
            ul_r = self.seeding_mode_global_upload_limit
            if ul_r != 0 and torrent.up_limit != ul_r:
                torrent.set_upload_limit(limit=ul_r)
            elif ul_r < 0:
                torrent.set_upload_limit(limit=-1)

        if managed_tag_pool is None:
            managed_tag_pool = type(self).merge_global_tracker_configured_add_tags()
        current_tags = _parse_qbittorrent_tag_list(getattr(torrent, "tags", None))
        if unique_tags:
            add_tags = unique_tags.difference(current_tags)
            if add_tags:
                self.add_tags(torrent, add_tags, instance_name)
        tags_to_remove = list((current_tags & managed_tag_pool) - unique_tags)
        if tags_to_remove:
            self.remove_tags(torrent, tags_to_remove, instance_name)

    def _stalled_check(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        time_now: float,
        instance_name: str = "default",
    ) -> bool:
        stalled_ignore = True
        if not self.allowed_stalled:
            self.logger.trace("Stalled check: Stalled delay disabled")
            return False
        stalled_delay_seconds = int(timedelta(minutes=self.stalled_delay).total_seconds())
        if time_now < torrent.added_on + self.ignore_torrents_younger_than:
            self.logger.trace(
                "Stalled check: In recent queue %s [Current:%s][Added:%s][Starting:%s]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(torrent.added_on),
                datetime.fromtimestamp(torrent.added_on + self.ignore_torrents_younger_than),
            )
            return True
        is_metadata_stuck = self._is_metadata_stuck_state(torrent)
        stall_reference = torrent.added_on if is_metadata_stuck else torrent.last_activity
        if self.stalled_delay == 0:
            self.logger.trace(
                "Stalled check: %s [Current:%s][Reference:%s][Limit:No Limit]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(stall_reference),
            )
        else:
            self.logger.trace(
                "Stalled check: %s [Current:%s][Reference:%s][Limit:%s]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(stall_reference),
                datetime.fromtimestamp(stall_reference + stalled_delay_seconds),
            )
        if (
            (
                torrent.state_enum
                in (
                    TorrentStates.METADATA_DOWNLOAD,
                    TorrentStates.FORCED_METADATA_DOWNLOAD,
                    TorrentStates.STALLED_DOWNLOAD,
                )
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            )
            or (
                torrent.availability < 1
                and torrent.hash in self.cleaned_torrents
                and torrent.state_enum in (TorrentStates.DOWNLOADING)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            )
        ) and self.allowed_stalled:
            if self.stalled_delay > 0 and time_now >= stall_reference + stalled_delay_seconds:
                stalled_ignore = False
                self.logger.trace("Process stalled, delay expired: %s", torrent.name)
            elif not self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
                self.add_tags(torrent, ["qBitrr-allowed_stalled"], instance_name)
                if self.re_search_stalled:
                    self.logger.trace(
                        "Stalled, adding tag, blocklosting and re-searching: %s", torrent.name
                    )
                    skip_blacklist = set()
                    payload = self.process_entries([torrent.hash])
                    if payload:
                        for entry, hash_ in payload:
                            self._process_failed_individual(
                                hash_=hash_,
                                entry=entry,
                                skip_blacklist=skip_blacklist,
                                remove_from_client=False,
                            )
                else:
                    self.logger.trace("Stalled, adding tag: %s", torrent.name)
            elif self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
                self.logger.trace(
                    "Stalled: %s [Current:%s][Reference:%s][Limit:%s]",
                    torrent.name,
                    datetime.fromtimestamp(time_now),
                    datetime.fromtimestamp(stall_reference),
                    datetime.fromtimestamp(stall_reference + stalled_delay_seconds),
                )

        elif self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
            self.remove_tags(torrent, ["qBitrr-allowed_stalled"], instance_name)
            stalled_ignore = False
            self.logger.trace("Not stalled, removing tag: %s", torrent.name)
        else:
            stalled_ignore = False
            self.logger.trace("Not stalled: %s", torrent.name)
        return stalled_ignore

    def _process_single_torrent(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        instance_name: str = "default",
        managed_tag_pool: frozenset[str] | None = None,
    ):
        if torrent.category != get_recheck_category_effective():
            self.manager.qbit_manager.cache[torrent.hash] = torrent.category
        category = getattr(torrent, "category", None)
        tracker_sync_owned_by_policy_manager = bool(
            self.manager
            and category
            and self.manager.policy_manager_owns_tracker_sync_for_category(
                category,
                qbit_section=instance_name if instance_name != "default" else None,
            )
        )
        if tracker_sync_owned_by_policy_manager:
            self.logger.trace(
                "Tracker/tag sync owned by TorrentPolicyManager; skipping Arr sync for %s (%s)",
                torrent.name,
                torrent.hash,
            )
        if not tracker_sync_owned_by_policy_manager:
            self._process_single_torrent_trackers(
                torrent, instance_name, managed_tag_pool=managed_tag_pool
            )
        self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
        time_now = time.time()
        leave_alone, _tracker_max_eta, remove_torrent, _data_settings, _data_torrent = (
            self._should_leave_alone(torrent, instance_name)
        )
        self.logger.trace(
            "Torrent [%s]: Leave Alone (allow seeding): %s, Max ETA: %s, State[%s]",
            torrent.name,
            leave_alone,
            _tracker_max_eta,
            torrent.state_enum,
        )
        maximum_eta = _tracker_max_eta

        if torrent.state_enum in (
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.FORCED_METADATA_DOWNLOAD,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.DOWNLOADING,
        ):
            stalled_ignore = self._stalled_check(torrent, time_now, instance_name)
        else:
            stalled_ignore = False

        if self.in_tags(torrent, "qBitrr-ignored", instance_name):
            self.remove_tags(
                torrent, ["qBitrr-allowed_seeding", "qBitrr-free_space_paused"], instance_name
            )

        if (
            self.custom_format_unmet_search
            and self.custom_format_unmet_check(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
        ):
            self._process_single_torrent_delete_cfunmet(torrent, instance_name)
        elif (
            remove_torrent
            and not leave_alone
            and torrent.amount_left == 0
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
        ):
            self._process_single_torrent_delete_ratio_seed(
                torrent,
                limit_meta=(_data_settings, _data_torrent),
                instance_name=instance_name,
            )
        elif torrent.category == get_failed_category_effective():
            # Bypass everything if manually marked as failed
            self._process_single_torrent_failed_cat(torrent, instance_name)
        elif torrent.category == get_recheck_category_effective():
            # Bypass everything else if manually marked for rechecking
            self._process_single_torrent_recheck_cat(torrent, instance_name)
        elif self._is_missing_files_torrent(torrent):
            # Missing-files (and ERROR+missingFiles): bypass all other processing, delete from client.
            self._process_single_torrent_missing_files(torrent, instance_name)
        elif self.is_ignored_state(torrent):
            self._process_single_torrent_ignored(torrent)
        elif (
            torrent.state_enum in (TorrentStates.STOPPED_DOWNLOAD, TorrentStates.STOPPED_UPLOAD)
            and leave_alone
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
        ):
            self.resume_by_instance[instance_name].add(torrent.hash)
            self.logger.debug(
                "Resuming stopped torrent: %s (%s) - State[%s]",
                torrent.name,
                torrent.hash,
                torrent.state_enum,
            )
        elif (
            torrent.state_enum
            in (
                TorrentStates.METADATA_DOWNLOAD,
                TorrentStates.FORCED_METADATA_DOWNLOAD,
                TorrentStates.STALLED_DOWNLOAD,
            )
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not stalled_ignore
        ):
            self._process_single_torrent_stalled_torrent(torrent, "Stalled State", instance_name)
        elif (
            torrent.state_enum.is_downloading
            and not self._is_metadata_stuck_state(torrent)
            and torrent.hash not in self.special_casing_file_check
            and torrent.hash not in self.cleaned_torrents
        ):
            self._process_single_torrent_process_files(torrent, True, instance_name)
        elif torrent.hash in self.timed_ignore_cache:
            if (
                torrent.state_enum
                in (TorrentStates.STOPPED_DOWNLOAD, TorrentStates.STOPPED_UPLOAD)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            ):
                self.resume_by_instance[instance_name].add(torrent.hash)
                self.logger.debug(
                    "Resuming stopped torrent (in ignore cache): %s (%s) - State[%s]",
                    torrent.name,
                    torrent.hash,
                    torrent.state_enum,
                )
            else:
                self._process_single_torrent_added_to_ignore_cache(torrent)
        elif torrent.state_enum == TorrentStates.QUEUED_UPLOAD:
            self._process_single_torrent_queued_upload(torrent, leave_alone, instance_name)
        # Resume monitored downloads which have been paused.
        elif (
            torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD
            and torrent.amount_left != 0
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
        ):
            self._process_single_torrent_paused(torrent, instance_name)
        elif (
            torrent.progress <= self.maximum_deletable_percentage
            and not self.is_complete_state(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not stalled_ignore
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_percentage_threshold(torrent, maximum_eta, instance_name)
        # Ignore torrents which have been submitted to their respective Arr
        # instance for import. Resolve the owning category through ArrManager so
        # subcategory paths (``seed/tleech``) and orphaned categories don't raise
        # KeyError on the hot path — see :mod:`qBitrr.category_paths` and the
        # subcategory section in ``docs/configuration/qbittorrent.md``.
        elif (
            (
                _owner_key := self.manager.resolve_owning_category(
                    getattr(torrent, "category", None),
                    qbit_section=instance_name if instance_name != "default" else None,
                )
            )
            and torrent.hash in self.manager.managed_objects[_owner_key].sent_to_scan_hashes
            and torrent.hash in self.cleaned_torrents
        ):
            self._process_single_torrent_already_sent_to_scan(torrent)

        # Sometimes torrents will error, this causes them to be rechecked so they
        # complete downloading.
        elif torrent.state_enum == TorrentStates.ERROR:
            self._process_single_torrent_errored(torrent, instance_name)
        # If a torrent was not just added,
        # and the amount left to download is 0 and the torrent
        # is Paused tell the Arr tools to process it.
        elif (
            torrent.added_on > 0
            and torrent.completion_on
            and torrent.amount_left == 0
            and torrent.state_enum != TorrentStates.PAUSED_UPLOAD
            and self.is_complete_state(torrent)
            and torrent.content_path
            and torrent.completion_on < time_now - 60
        ):
            self._process_single_torrent_fully_completed_torrent(torrent, leave_alone)
        # If a torrent is Uploading Pause it, as long as its not being Forced Uploaded.
        elif (
            self.is_uploading_state(torrent)
            and torrent.seeding_time > 1
            and torrent.amount_left == 0
            and torrent.added_on > 0
            and torrent.content_path
            and self.seeding_mode_global_remove_torrent != -1
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_uploading(torrent, leave_alone, instance_name)
        # Mark a torrent for deletion
        elif (
            torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD
            and torrent.state_enum.is_downloading
            and time_now > torrent.added_on + self.ignore_torrents_younger_than
            and 0 < maximum_eta < torrent.eta
            and not self.do_not_remove_slow
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not stalled_ignore
        ):
            self._process_single_torrent_delete_slow(torrent, instance_name)
        # Process uncompleted torrents
        elif torrent.state_enum.is_downloading:
            # If a torrent availability hasn't reached 100% or more within the configurable
            # "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
            if (
                (
                    time_now > torrent.added_on + self.ignore_torrents_younger_than
                    and torrent.availability < 1
                )
                and torrent.hash in self.cleaned_torrents
                and self.is_downloading_state(torrent)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
                and not stalled_ignore
            ):
                self._process_single_torrent_stalled_torrent(torrent, "Unavailable", instance_name)
            else:
                if torrent.hash in self.cleaned_torrents:
                    self._process_single_torrent_already_cleaned_up(torrent)
                    return
                # A downloading torrent is not stalled, parse its contents.
                self._process_single_torrent_process_files(torrent, instance_name=instance_name)
        elif self.is_complete_state(torrent) and leave_alone:
            self._process_single_completed_paused_torrent(torrent, leave_alone, instance_name)
        else:
            self._process_single_torrent_unprocessed(torrent)
