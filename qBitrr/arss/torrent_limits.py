"""Torrent seeding-limits / HnR / leave-alone pipeline role composed into ArrBase.

Call graph (per loop):
  Arr.process_torrents → TorrentDispatch._process_single_torrent
  → TorrentLimits._should_leave_alone / torrent_limit_check / custom_format_unmet_check
  → TorrentInspect._process_single_torrent_* (decide; uses _hnr_allows_delete)
  → Arr.process → TorrentBatch._process_* (pause / import / fail / resume / file priority).
"""

from __future__ import annotations

from datetime import timedelta

import qbittorrentapi
from qbittorrentapi import TorrentStates

from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS,
    _extract_tracker_host,
    _TrackerDataUnavailable,
    with_retry,
)


class TorrentLimits:
    def _resolve_hnr_clear_mode(self, tracker_or_config: dict) -> str:
        """Resolve HnR mode from single HitAndRunMode key: 'and' | 'or' | 'disabled'."""
        raw = tracker_or_config.get("HitAndRunMode")
        if isinstance(raw, str) and raw.strip().lower() in ("and", "or", "disabled"):
            return raw.strip().lower()
        # Legacy: boolean HitAndRunMode (pre-migration)
        if raw is True:
            return "and"
        return "disabled"

    def _get_torrent_limit_meta(self, torrent: qbittorrentapi.TorrentDictionary):
        def _to_number(value, default):
            if value is None or isinstance(value, bool):
                return default
            if isinstance(value, (int, float)):
                return value
            try:
                text = str(value).strip()
                if not text:
                    return default
                return float(text) if "." in text else int(text)
            except (TypeError, ValueError):
                return default

        def _positive_or_sentinel(value):
            parsed = _to_number(value, default=-5)
            return parsed if parsed > 0 else -5

        _, monitored_trackers = self._get_torrent_important_trackers(torrent)
        most_important_tracker, _unique_tags = self._get_most_important_tracker_and_tags(
            monitored_trackers, {}
        )

        data_settings = {
            "ratio_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "MaxUploadRatio", self.seeding_mode_global_max_upload_ratio
                )
            ),
            "seeding_time_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "MaxSeedingTime", self.seeding_mode_global_max_seeding_time
                )
            ),
            "dl_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "DownloadRateLimit", self.seeding_mode_global_download_limit
                )
            ),
            "up_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "UploadRateLimit", self.seeding_mode_global_upload_limit
                )
            ),
            "super_seeding": most_important_tracker.get("SuperSeedMode", torrent.super_seeding),
            "max_eta": _to_number(
                most_important_tracker.get("MaximumETA", self.maximum_eta),
                self.maximum_eta,
            ),
            "hnr_clear_mode": self._resolve_hnr_clear_mode(most_important_tracker),
            "hnr_min_seed_ratio": _to_number(
                most_important_tracker.get("MinSeedRatio", 1.0),
                1.0,
            ),
            "hnr_min_seeding_time_days": _to_number(
                most_important_tracker.get("MinSeedingTimeDays", 0),
                0,
            ),
            "hnr_min_download_percent": _to_number(
                most_important_tracker.get("HitAndRunMinimumDownloadPercent", 10),
                10,
            ),
            "hnr_partial_seed_ratio": _to_number(
                most_important_tracker.get("HitAndRunPartialSeedRatio", 1.0),
                1.0,
            ),
            "hnr_tracker_update_buffer": _to_number(
                most_important_tracker.get("TrackerUpdateBuffer", 0),
                0,
            ),
        }

        data_torrent = {
            "ratio_limit": _positive_or_sentinel(getattr(torrent, "ratio_limit", -5)),
            "seeding_time_limit": _positive_or_sentinel(
                getattr(torrent, "seeding_time_limit", -5)
            ),
            "dl_limit": _positive_or_sentinel(getattr(torrent, "dl_limit", -5)),
            "up_limit": _positive_or_sentinel(getattr(torrent, "up_limit", -5)),
            "super_seeding": torrent.super_seeding,
        }
        return data_settings, data_torrent

    def _should_leave_alone(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ) -> tuple[bool, int, bool, dict | None, dict | None]:
        return_value = True
        remove_torrent = False
        if torrent.super_seeding or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            return return_value, -1, remove_torrent, None, None

        is_uploading = torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
        )
        is_downloading = torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.QUEUED_DOWNLOAD,
            TorrentStates.PAUSED_DOWNLOAD,
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.FORCED_METADATA_DOWNLOAD,
        )

        try:
            data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
        except _TrackerDataUnavailable:
            self.logger.warning(
                "Skipping tracker-dependent seeding checks for torrent '%s' (%s) this pass",
                getattr(torrent, "name", "<unknown>"),
                getattr(torrent, "hash", "<unknown>"),
            )
            return return_value, self.maximum_eta, remove_torrent, None, None
        self.logger.trace("Config Settings for torrent [%s]: %r", torrent.name, data_settings)
        self.logger.trace("Torrent Settings for torrent [%s]: %r", torrent.name, data_torrent)

        ratio_limit_dat = data_settings.get("ratio_limit", -5)
        ratio_limit_tor = data_torrent.get("ratio_limit", -5)
        seeding_time_limit_dat = data_settings.get("seeding_time_limit", -5)
        seeding_time_limit_tor = data_torrent.get("seeding_time_limit", -5)

        seeding_time_limit = max(seeding_time_limit_dat, seeding_time_limit_tor)
        ratio_limit = max(ratio_limit_dat, ratio_limit_tor)

        if is_uploading and self.seeding_mode_global_remove_torrent != -1:
            remove_torrent = self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
        else:
            remove_torrent = False

        hnr_override = False
        if (
            is_downloading
            and remove_torrent
            and not self._hnr_safe_to_remove(torrent, data_settings)
        ):
            self.logger.debug(
                "HnR protection: keeping downloading torrent [%s] (ratio=%.2f, seeding=%s)",
                torrent.name,
                torrent.ratio,
                timedelta(seconds=torrent.seeding_time),
            )
            remove_torrent = False
            hnr_override = True

        if hnr_override:
            return_value = True
        else:
            return_value = not (
                is_uploading and self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
            )
        if data_settings.get("super_seeding", False) or data_torrent.get("super_seeding", False):
            return_value = True
        if self.in_tags(torrent, "qBitrr-free_space_paused", instance_name):
            return_value = True
        if (
            return_value
            and not self.in_tags(torrent, "qBitrr-allowed_seeding", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
        ):
            self.add_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
        elif (
            not return_value and self.in_tags(torrent, "qBitrr-allowed_seeding", instance_name)
        ) or self.in_tags(torrent, "qBitrr-free_space_paused", instance_name):
            self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)

        if hnr_override and not self.in_tags(torrent, "qBitrr-hnr_active", instance_name):
            self.add_tags(torrent, ["qBitrr-hnr_active"], instance_name)
        elif not hnr_override and self.in_tags(torrent, "qBitrr-hnr_active", instance_name):
            self.remove_tags(torrent, ["qBitrr-hnr_active"], instance_name)

        self.logger.trace("Config Settings returned [%s]: %r", torrent.name, data_settings)
        return (
            return_value,
            data_settings.get("max_eta", self.maximum_eta),
            remove_torrent,
            data_settings,
            data_torrent,
        )

    def custom_format_unmet_check(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        try:
            queue = with_retry(
                lambda: self.client.queue.get(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )

            if not queue.get("records"):
                return False

            download_id = torrent.hash.upper()
            record = next(
                (r for r in queue["records"] if r.get("downloadId") == download_id), None
            )

            if not record:
                return False

            custom_format_score = record.get("customFormatScore")
            if custom_format_score is None:
                return False

            # Default assumption: custom format requirements are met
            cf_unmet = False

            fields = self._custom_format_queue_fields()
            if fields is None:
                return False
            entry_id_field, file_id_field = fields

            entry_id = record.get(entry_id_field)
            if not entry_id:
                return False

            # Retrieve the model entry from the database
            model_entry = (
                self.model_file.select()
                .where(
                    (self.model_file.EntryId == entry_id)
                    & (self.model_file.ArrInstance == self._name)
                )
                .first()
            )
            if not model_entry:
                return False

            if file_id_field is None:
                if self.force_minimum_custom_format:
                    min_score = getattr(model_entry, "MinCustomFormatScore", 0)
                    cf_unmet = custom_format_score < min_score
            else:
                file_id = getattr(model_entry, file_id_field, 0)
                if file_id != 0:
                    model_cf_score = getattr(model_entry, "CustomFormatScore", 0)
                    cf_unmet = custom_format_score < model_cf_score
                    if self.force_minimum_custom_format:
                        min_score = getattr(model_entry, "MinCustomFormatScore", 0)
                        cf_unmet = cf_unmet and custom_format_score < min_score

            return cf_unmet

        except Exception:
            return False

    def _hnr_allows_delete(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        *,
        data_settings: dict | None = None,
    ) -> bool:
        """Check if HnR obligations allow deleting this torrent.

        Fetches tracker metadata and checks HnR. Returns True if deletion
        is allowed, False if HnR protection blocks it.
        """
        if not any(self._resolve_hnr_clear_mode(t) != "disabled" for t in self.monitored_trackers):
            return True  # Fast path: no HnR on any tracker

        # If the HnR-enabled tracker reports the torrent as unregistered/dead,
        # HnR no longer applies (tracker has removed the torrent).
        if self._hnr_tracker_is_dead(torrent):
            self.logger.debug(
                "HnR bypass: tracker reports torrent as unregistered/dead [%s]",
                torrent.name,
            )
            return True

        if data_settings is None:
            try:
                data_settings, _ = self._get_torrent_limit_meta(torrent)
            except _TrackerDataUnavailable as exc:
                self.logger.warning(
                    "HnR check skipped for torrent '%s' (%s): %s",
                    getattr(torrent, "name", "<unknown>"),
                    getattr(torrent, "hash", "<unknown>"),
                    str(exc),
                )
                # Fail safe: without tracker metadata, do not allow deletion.
                return False
        if self._hnr_safe_to_remove(torrent, data_settings):
            return True
        self.logger.info(
            "HnR protection: blocking %s of [%s] (ratio=%.2f, seeding=%s, progress=%.1f%%)",
            reason,
            torrent.name,
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            torrent.progress * 100,
        )
        return False

    def _hnr_tracker_is_dead(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """Check if the HnR-enabled tracker reports the torrent as unregistered or dead.

        If a tracker says the torrent is unregistered/unauthorized, the torrent
        no longer exists on the tracker and HnR obligations cannot apply.
        """
        _dead_keywords = {
            "unregistered torrent",
            "torrent not registered",
            "info hash is not authorized",
            "torrent is not authorized",
            "torrent not found",
        }
        # Build set of HnR-enabled tracker hostnames
        hnr_hosts = {
            _extract_tracker_host(t.get("URI") or "")
            for t in self.monitored_trackers
            if self._resolve_hnr_clear_mode(t) != "disabled"
        } - {""}
        if not hnr_hosts:
            return False
        try:
            for tracker in torrent.trackers:
                tracker_url = (getattr(tracker, "url", None) or "").rstrip("/")
                if not tracker_url or _extract_tracker_host(tracker_url) not in hnr_hosts:
                    continue
                message_text = (getattr(tracker, "msg", "") or "").lower()
                if any(keyword in message_text for keyword in _dead_keywords):
                    return True
        except Exception:
            pass
        return False

    def _hnr_safe_to_remove(
        self, torrent: qbittorrentapi.TorrentDictionary, tracker_meta: dict
    ) -> bool:
        """Returns True only if Hit and Run obligations are met."""
        clear_mode = (tracker_meta.get("hnr_clear_mode") or "disabled").strip().lower()
        if clear_mode == "disabled":
            return True

        min_ratio = tracker_meta.get("hnr_min_seed_ratio", 1.0)
        min_time_secs = tracker_meta.get("hnr_min_seeding_time_days", 0) * 86400
        min_dl_pct = tracker_meta.get("hnr_min_download_percent", 10) / 100.0
        partial_ratio = tracker_meta.get("hnr_partial_seed_ratio", 1.0)
        buffer_secs = tracker_meta.get("hnr_tracker_update_buffer", 0)

        is_partial = torrent.progress < 1.0 and torrent.progress >= min_dl_pct
        effective_seeding_time = torrent.seeding_time - buffer_secs

        if torrent.progress < min_dl_pct:
            return True  # Below minimum download threshold, no HnR obligation
        if is_partial:
            return torrent.ratio >= partial_ratio  # Partial: ratio only

        ratio_met = torrent.ratio >= min_ratio if min_ratio > 0 else False
        time_met = effective_seeding_time >= min_time_secs if min_time_secs > 0 else False

        if clear_mode == "and":
            if min_ratio > 0 and min_time_secs > 0:
                return ratio_met and time_met
            if min_ratio > 0:
                return ratio_met
            if min_time_secs > 0:
                return time_met
            return True
        if clear_mode == "or":
            if min_ratio > 0 and min_time_secs > 0:
                return ratio_met or time_met
            if min_ratio > 0:
                return ratio_met
            if min_time_secs > 0:
                return time_met
            return True
        return True

    def torrent_limit_check(
        self, torrent: qbittorrentapi.TorrentDictionary, seeding_time_limit, ratio_limit
    ) -> bool:
        # -1 = Never remove (regardless of ratio/time limits)
        if self.seeding_mode_global_remove_torrent == -1:
            return False

        # Treat limits <= 0 as unset; only consider a limit "met" when it is set (>0) and satisfied
        ratio_limit_valid = ratio_limit is not None and ratio_limit > 0
        time_limit_valid = seeding_time_limit is not None and seeding_time_limit > 0
        ratio_met = ratio_limit_valid and torrent.ratio >= ratio_limit
        time_met = time_limit_valid and torrent.seeding_time >= seeding_time_limit

        mode = self.seeding_mode_global_remove_torrent
        if mode in (1, 2, 3, 4) and not ratio_limit_valid and not time_limit_valid:
            if not self._warned_no_seeding_limits:
                self.logger.warning(
                    "RemoveTorrent=%s but neither MaxUploadRatio nor MaxSeedingTime is set; "
                    "skipping seeding-based removal until at least one limit is configured",
                    mode,
                )
                self._warned_no_seeding_limits = True
            return False

        if mode == 4:
            return ratio_met and time_met
        if mode == 3:
            return ratio_met or time_met
        if mode == 2:
            return time_met
        if mode == 1:
            return ratio_met
        return False
