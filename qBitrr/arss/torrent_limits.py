"""Torrent seeding-limits / HnR / leave-alone pipeline role composed into ArrBase.

Call graph (per loop):
  Arr.process_torrents → TorrentDispatch._process_single_torrent
  → TorrentLimits._should_leave_alone / torrent_limit_check / custom_format_unmet_check
  → TorrentInspect._process_single_torrent_* (decide; uses _hnr_allows_delete)
  → Arr.process → TorrentBatch._process_* (pause / import / fail / resume / file priority).
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime, timedelta

import qbittorrentapi
from qbittorrentapi import TorrentStates

from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS,
    _extract_tracker_host,
    _TrackerDataUnavailable,
    with_retry,
)
from qBitrr.duration_config import _DURATION_PATTERN, _MAX_DURATION_STRING_LEN, parse_duration


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

    def _get_torrent_limit_meta(
        self, torrent: qbittorrentapi.TorrentDictionary, *, seeding_policy=None, trackers=None
    ):
        def _to_number(value, default):
            if value is None or isinstance(value, bool):
                return default
            if isinstance(value, (int, float)):
                return value
            try:
                text = str(value).strip()
                if not text or len(text) > _MAX_DURATION_STRING_LEN:
                    return default
                if _DURATION_PATTERN.match(text):
                    return parse_duration(text, unit="seconds", fallback=default)
                return float(text) if "." in text else int(text)
            except (TypeError, ValueError):
                return default

        def _positive_or_sentinel(value):
            parsed = _to_number(value, default=-5)
            return parsed if parsed > 0 else -5

        def _prefer_limit(tracker_raw, global_value):
            """Prefer any positive limit over unlimited/unset from either source.

            Tracker ``-1`` / missing / <=0 means no limit from the tracker (not
            "force unlimited"). Unlimited is residual only when neither tracker
            nor parent contributes a positive limit. When both are positive, the
            tracker value wins as an explicit per-tracker override.
            """
            tracker_parsed = _to_number(tracker_raw, default=-5)
            if tracker_parsed is not None and tracker_parsed > 0:
                return tracker_parsed
            return global_value

        if trackers is None:
            _, monitored_trackers = self._get_torrent_important_trackers(torrent)
            most_important_tracker, _unique_tags = self._get_most_important_tracker_and_tags(
                monitored_trackers, {}
            )
        else:
            most_important_tracker = max(
                (item for item in trackers if item.get("RemoveIfExists") is not True),
                key=lambda item: item.get("Priority", -100),
                default={},
            )
        policy = seeding_policy or {}

        data_settings = {
            "ratio_limit": _positive_or_sentinel(
                _prefer_limit(
                    most_important_tracker.get("MaxUploadRatio"),
                    policy.get(
                        "MaxUploadRatio", getattr(self, "seeding_mode_global_max_upload_ratio", -1)
                    ),
                )
            ),
            "seeding_time_limit": _positive_or_sentinel(
                _prefer_limit(
                    most_important_tracker.get("MaxSeedingTime"),
                    policy.get(
                        "MaxSeedingTime", getattr(self, "seeding_mode_global_max_seeding_time", -1)
                    ),
                )
            ),
            "dl_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "DownloadRateLimit",
                    policy.get(
                        "DownloadRateLimitPerTorrent",
                        getattr(self, "seeding_mode_global_download_limit", -1),
                    ),
                )
            ),
            "up_limit": _positive_or_sentinel(
                most_important_tracker.get(
                    "UploadRateLimit",
                    policy.get(
                        "UploadRateLimitPerTorrent",
                        getattr(self, "seeding_mode_global_upload_limit", -1),
                    ),
                )
            ),
            "super_seeding": most_important_tracker.get("SuperSeedMode", torrent.super_seeding),
            "max_eta": _to_number(
                _prefer_limit(
                    most_important_tracker.get("MaximumETA"),
                    policy.get("MaximumETA", getattr(self, "maximum_eta", -1)),
                ),
                policy.get("MaximumETA", getattr(self, "maximum_eta", -1)),
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
        self._touch_stalled_up_since(torrent)
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

    def _removal_arr_section(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str
    ) -> str | None:
        """Resolve the torrent's Arr owner independently of the worker doing cleanup."""
        from qBitrr.category_paths import matches_configured, normalize_category
        from qBitrr.config import CONFIG

        category = normalize_category(torrent.category)
        owners = {}
        eligible = []
        for section in CONFIG.sections():
            if not re.match(r"(rad|son|lid|read)arr.*", section, re.IGNORECASE):
                continue
            configured = normalize_category(CONFIG.get(f"{section}.Category", fallback=section))
            prefix = CONFIG.get(
                f"{section}.MatchSubcategories",
                fallback=CONFIG.get(f"{instance_name}.MatchSubcategories", fallback=False),
            )
            owners.setdefault(configured, []).append(section)
            if category == configured or prefix:
                eligible.append(configured)
        owner = matches_configured(category, eligible, prefix=True)
        matches = owners.get(owner, [])
        if len(matches) > 1:
            raise ValueError("Torrent Arr ownership is ambiguous")
        return matches[0] if matches else None

    def _deletion_rules_allow(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        *,
        instance_name: str,
        client: qbittorrentapi.Client,
    ) -> bool:
        """Require all applicable protection rules immediately before destructive work."""
        from qBitrr.config import CONFIG
        from qBitrr.qbit_seeding_config import load_qbit_seeding_config

        try:
            for key in ("progress", "ratio", "seeding_time", "added_on", "last_activity"):
                value = getattr(torrent, key)
                if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                    return False
            if torrent.progress > 1:
                return False
            if not self._hnr_allows_delete(
                torrent, reason, instance_name=instance_name, client=client
            ):
                return False
            if CONFIG.get(f"{instance_name}.Disabled", fallback=False):
                return False
            tags = {tag.strip() for tag in (getattr(torrent, "tags", "") or "").split(",")}
            if tags & {"qBitrr-ignored", "qBitrr-free_space_paused"}:
                return False
            if torrent.super_seeding or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
                return False
            loaded = load_qbit_seeding_config(instance_name)
            policy = dict(loaded["default_seeding"])
            matches = [
                name
                for name in loaded["category_overrides"]
                if torrent.category == name
                or (
                    loaded["match_subcategories"]
                    and torrent.category.startswith(name.rstrip("/") + "/")
                )
            ]
            if matches:
                policy.update(loaded["category_overrides"][max(matches, key=len)])
            arr_section = self._removal_arr_section(torrent, instance_name)
            age = max(
                CONFIG.get_duration("Settings.IgnoreTorrentsYoungerThan", fallback=180),
                loaded.get("ignore_torrents_younger_than", 180),
                parse_duration(policy.get("IgnoreTorrentsYoungerThan", 0), fallback=-1),
                (
                    CONFIG.get_duration(
                        f"{arr_section}.Torrent.IgnoreTorrentsYoungerThan", fallback=0
                    )
                    if arr_section
                    else 0
                ),
            )
            now = time.time()
            if not 0 < torrent.added_on <= now or now - torrent.added_on < age:
                return False
            arr_policy = (
                CONFIG.get(f"{arr_section}.Torrent.SeedingMode", fallback={})
                if arr_section
                else None
            )
            if isinstance(arr_policy, dict):
                for key in ("MaxUploadRatio", "MaxSeedingTime", "RemoveTorrent"):
                    value = arr_policy.get(key, -1)
                    if key == "MaxSeedingTime":
                        value = parse_duration(value, fallback=-1)
                    if value > 0:
                        policy[key] = value
            for key in ("MaxUploadRatio", "MaxSeedingTime"):
                value = policy.get(key, -1)
                if key == "MaxSeedingTime":
                    value = parse_duration(value, fallback=float("nan"))
                if isinstance(value, bool) or not math.isfinite(value):
                    return False
                policy[key] = value
            mode = policy.get("RemoveTorrent", -1)
            if isinstance(arr_policy, dict):
                mode = arr_policy.get("RemoveTorrent", -1)
            if isinstance(mode, bool) or mode not in (1, 2, 3, 4):
                return False
            if torrent.progress < 1:
                delay = parse_duration(
                    policy.get("StalledDelay", loaded.get("stalled_delay", -1)),
                    unit="minutes",
                    fallback=-1,
                )
                if arr_section:
                    delay = CONFIG.get_duration(
                        f"{arr_section}.Torrent.StalledDelay", fallback=15, unit="minutes"
                    )
                reference = (
                    torrent.added_on
                    if torrent.state_enum
                    in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.FORCED_METADATA_DOWNLOAD)
                    else torrent.last_activity
                )
                return (
                    math.isfinite(delay)
                    and delay >= 0
                    and 0 < reference <= now
                    and now - reference >= max(age, delay * 60)
                )
            actual_hosts = {
                _extract_tracker_host(t.url)
                for t in client.torrents_trackers(torrent_hash=torrent.hash)
            }
            from qBitrr.arr_tracker_index import merge_tracker_configs

            configured = merge_tracker_configs(
                loaded["trackers"],
                CONFIG.get(f"{arr_section}.Torrent.Trackers", fallback=[]) if arr_section else [],
            )
            matching_trackers = [
                item
                for item in configured
                if any(
                    host == (configured_host := _extract_tracker_host(item.get("URI", "")))
                    or (configured_host and host.endswith("." + configured_host))
                    for host in actual_hosts
                )
            ]
            settings, native = self._get_torrent_limit_meta(
                torrent, seeding_policy=policy, trackers=matching_trackers
            )
            ratio = max(settings.get("ratio_limit", -1), native.get("ratio_limit", -1))
            seed_time = max(
                settings.get("seeding_time_limit", -1), native.get("seeding_time_limit", -1)
            )
            if not math.isfinite(ratio) or not math.isfinite(seed_time):
                return False
            if settings.get("ratio_limit", -1) <= 0:
                ratio = max(ratio, policy.get("MaxUploadRatio", -1))
            if settings.get("seeding_time_limit", -1) <= 0:
                seed_time = max(seed_time, policy.get("MaxSeedingTime", -1))
            return self.torrent_limit_check(torrent, seed_time, ratio, remove_mode=mode)
        except Exception as exc:
            self.logger.warning(
                "Removal rules unavailable for %s on %s: %s",
                torrent.hash,
                instance_name,
                type(exc).__name__,
            )
            return False

    def _hnr_allows_delete(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        *,
        data_settings: dict | None = None,
        instance_name: str | None = None,
        client: qbittorrentapi.Client | None = None,
    ) -> bool:
        """Require verified clearance for every applicable tracker and category obligation."""
        from qBitrr.arss.qbit_side_effects import resolve_removal_torrent
        from qBitrr.config import CONFIG
        from qBitrr.qbit_seeding_config import load_qbit_seeding_config

        def mode(policy: dict) -> str:
            raw = policy.get("HitAndRunMode", "disabled")
            if raw is True:
                return "and"
            if raw is False:
                return "disabled"
            if isinstance(raw, str) and raw.strip().lower() in ("and", "or", "disabled"):
                return raw.strip().lower()
            raise ValueError("Invalid HnR mode")

        try:
            instance_name = instance_name or getattr(torrent, "_qbitrr_instance", None)
            if client is None:
                current = resolve_removal_torrent(self, torrent.hash, instance_name)
                if current is None:
                    return False
                instance_name, client, torrent = current
            properties = client.torrents_properties(torrent_hash=torrent.hash)
            private = properties.get("is_private")
            trackers = list(client.torrents_trackers(torrent_hash=torrent.hash))
            if "is_private" not in properties:
                # Older qBit versions mark all three discovery rows with a localized private message.
                discovery = {
                    t.url: t
                    for t in trackers
                    if t.url in {"** [DHT] **", "** [PeX] **", "** [LSD] **"}
                }
                messages = [getattr(t, "msg", None) for t in discovery.values()]
                if (
                    len(discovery) == 3
                    and all(isinstance(msg, str) for msg in messages)
                    and len(set(messages)) == 1
                    and torrent.state_enum
                    not in (
                        TorrentStates.METADATA_DOWNLOAD,
                        TorrentStates.FORCED_METADATA_DOWNLOAD,
                    )
                ):
                    private = bool(messages[0])
            if not isinstance(private, bool):
                raise ValueError("Torrent privacy is unknown")
            actual = [t for t in trackers if _extract_tracker_host(t.url)]
            if not actual:
                raise ValueError("Tracker information is unavailable")
            seeding = load_qbit_seeding_config(instance_name, include_ignore_younger=False)
            category = dict(seeding["default_seeding"])
            overrides = seeding["category_overrides"]
            matching = [
                name
                for name in overrides
                if torrent.category == name
                or (
                    seeding["match_subcategories"]
                    and torrent.category.startswith(name.rstrip("/") + "/")
                )
            ]
            if matching:
                category.update(overrides[max(matching, key=len)])
            arr_section = self._removal_arr_section(torrent, instance_name)
            configs = list(seeding["trackers"]) + list(
                CONFIG.get(f"{arr_section}.Torrent.Trackers", fallback=[])
                if arr_section
                else getattr(self, "monitored_trackers", []) if not hasattr(self, "_name") else []
            )
            policies = []
            hosts = set()
            for tracker in actual:
                host = _extract_tracker_host(tracker.url)
                matched = [
                    c
                    for c in configs
                    if (configured := _extract_tracker_host(c.get("URI", "")))
                    and (host == configured or host.endswith("." + configured))
                ]
                enabled = [c for c in matched if mode(c) != "disabled"]
                if enabled:
                    if tracker.status != 2 or (getattr(tracker, "msg", "") or "").strip():
                        raise ValueError("Tracker accounting is unhealthy or unknown")
                    hosts.add(host)
                    policies.extend(enabled)
            category_enabled = mode(category) != "disabled"
            if category_enabled:
                if any(t.status != 2 or (getattr(t, "msg", "") or "").strip() for t in actual):
                    raise ValueError("Category accounting is unhealthy or unknown")
                policies.append(category)
            if (
                private
                and not category_enabled
                and any(_extract_tracker_host(t.url) not in hosts for t in actual)
            ):
                raise ValueError("Private tracker has no verified clearance requirements")
            for policy in policies:
                settings = {"hnr_clear_mode": mode(policy)}
                for source, target, default in (
                    ("MinSeedRatio", "hnr_min_seed_ratio", 1),
                    ("MinSeedingTimeDays", "hnr_min_seeding_time_days", 0),
                    ("HitAndRunMinimumDownloadPercent", "hnr_min_download_percent", 10),
                    ("HitAndRunPartialSeedRatio", "hnr_partial_seed_ratio", 1),
                    ("TrackerUpdateBuffer", "hnr_tracker_update_buffer", 0),
                ):
                    value = policy.get(
                        source,
                        (
                            policy.get("MinSeedingTime", default)
                            if source == "MinSeedingTimeDays"
                            else default
                        ),
                    )
                    if isinstance(value, str) and source == "TrackerUpdateBuffer":
                        value = parse_duration(value, unit="seconds", fallback=-1)
                    elif (
                        isinstance(value, str)
                        and source == "MinSeedingTimeDays"
                        and not value.replace(".", "", 1).isdigit()
                    ):
                        value = parse_duration(value, unit="seconds", fallback=-86400) / 86400
                    elif (
                        isinstance(value, str)
                        and source == "MinSeedingTimeDays"
                        and not value.replace(".", "", 1).isdigit()
                    ):
                        value = parse_duration(value, unit="seconds", fallback=-86400) / 86400
                    if (
                        isinstance(value, bool)
                        or not math.isfinite(float(value))
                        or float(value) < 0
                    ):
                        raise ValueError("Invalid HnR threshold")
                    settings[target] = float(value)
                if settings["hnr_min_download_percent"] > 100:
                    raise ValueError("Invalid download threshold")
                if (
                    any(
                        not math.isfinite(float(getattr(torrent, name)))
                        or float(getattr(torrent, name)) < 0
                        for name in ("progress", "ratio", "seeding_time")
                    )
                    or torrent.progress > 1
                ):
                    raise ValueError("Invalid torrent accounting")
                if not self._hnr_safe_to_remove(torrent, settings):
                    raise ValueError("Configured HnR obligations remain unmet")
            return True
        except Exception as exc:
            self.logger.info(
                "HnR blocked %s of %s on %s (%s): %s",
                reason,
                getattr(torrent, "name", "unknown"),
                instance_name or "unknown client",
                getattr(torrent, "hash", "unknown"),
                str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
            )
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
        return False

    def _touch_stalled_up_since(self, torrent: qbittorrentapi.TorrentDictionary) -> float | None:
        """Record or clear the first time this hash was seen in ``stalledUP``.

        Returns the epoch timestamp when qBitrr first observed this torrent in
        ``stalledUP`` during this process lifetime, or ``None`` if it is not
        currently stalled. Queued, paused, stopped, forced, and uploading states
        reset the clock so a later ``stalledUP`` does not inherit queue/pause age.
        """
        stalled_since = getattr(self, "_stalled_up_since", None)
        if stalled_since is None:
            self._stalled_up_since = stalled_since = {}
        torrent_hash = getattr(torrent, "hash", None)
        if not torrent_hash:
            return None
        if getattr(torrent, "state_enum", None) != TorrentStates.STALLED_UPLOAD:
            stalled_since.pop(torrent_hash, None)
            return None
        return stalled_since.setdefault(torrent_hash, time.time())

    def _stalled_upload_idle_exceeds_limit(
        self, torrent: qbittorrentapi.TorrentDictionary, seeding_time_limit
    ) -> bool:
        """Return True when qBitrr has observed this hash in stalledUP for MaxSeedingTime.

        Uses a process-local ``stalledUP``-since stamp, not qBittorrent
        ``last_activity`` (last payload) or ``seeding_time``. Restart resets the
        observation window (conservative: delays deletion, never premie-deletes).
        """
        if seeding_time_limit is None or seeding_time_limit <= 0:
            return False
        since = self._touch_stalled_up_since(torrent)
        if since is None:
            return False
        return (time.time() - since) >= seeding_time_limit

    def torrent_limit_check(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        seeding_time_limit,
        ratio_limit,
        *,
        remove_mode: int | None = None,
    ) -> bool:
        mode = self.seeding_mode_global_remove_torrent if remove_mode is None else remove_mode
        # -1 = Never remove (regardless of ratio/time limits)
        if mode == -1:
            return False

        # Treat limits <= 0 as unset; only consider a limit "met" when it is set (>0) and satisfied
        ratio_limit_valid = ratio_limit is not None and ratio_limit > 0
        time_limit_valid = seeding_time_limit is not None and seeding_time_limit > 0
        ratio_met = ratio_limit_valid and torrent.ratio >= ratio_limit
        seeding_time_met = time_limit_valid and torrent.seeding_time >= seeding_time_limit
        idle_met = time_limit_valid and self._stalled_upload_idle_exceeds_limit(
            torrent, seeding_time_limit
        )
        if idle_met and not seeding_time_met:
            since = self._touch_stalled_up_since(torrent)
            self.logger.debug(
                "Stalled upload observed idle time met MaxSeedingTime for [%s] "
                "(seeding_time=%s, stalled_since=%s, limit=%s)",
                torrent.name,
                timedelta(seconds=torrent.seeding_time),
                datetime.fromtimestamp(since) if since else None,
                timedelta(seconds=seeding_time_limit),
            )
        time_met = seeding_time_met or idle_met

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
