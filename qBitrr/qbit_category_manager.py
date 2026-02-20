"""qBit Category Manager - Manages torrents in qBit-managed categories with seeding settings."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from qbittorrentapi import TorrentStates

from qBitrr.arss import _extract_tracker_host
from qBitrr.errors import DelayLoopException

if TYPE_CHECKING:
    from qbittorrentapi import TorrentDictionary

    from qBitrr.main import qBitManager

# Sleep timer between processing loops (seconds)
LOOP_SLEEP_TIMER = 10


class qBitCategoryManager:
    """Manages torrents in qBit-managed categories with custom seeding settings."""

    def __init__(self, instance_name: str, qbit_manager: qBitManager, config: dict):
        """
        Initialize the qBit category manager.

        Args:
            instance_name: Name of the qBit instance
            qbit_manager: Reference to qBitManager
            config: Configuration dict containing:
                - managed_categories: List of category names
                - default_seeding: Default seeding settings
                - category_overrides: Per-category seeding overrides
        """
        self.instance_name = instance_name
        self.qbit_manager = qbit_manager
        self.managed_categories = config.get("managed_categories", [])
        self.default_seeding = config.get("default_seeding", {})
        self.category_overrides = config.get("category_overrides", {})
        self.trackers = self._build_merged_trackers(config.get("trackers", []))
        self.logger = logging.getLogger(f"qBitrr.qBitCategory.{instance_name}")

        self.logger.info(
            "Initialized qBit category manager for instance '%s' with %d categories: %s",
            instance_name,
            len(self.managed_categories),
            ", ".join(self.managed_categories),
        )

    @staticmethod
    def _build_merged_trackers(qbit_trackers: list) -> list:
        """
        Build a merged tracker list from qBit-level and all Arr-level Torrent.Trackers.

        Arr-level tracker configs override qBit-level entries with the same URI,
        matching the merge logic used by ArrManager.
        """
        from qBitrr.config import CONFIG

        merged: dict[str, dict] = {}
        for tracker in qbit_trackers:
            if isinstance(tracker, dict):
                uri = (tracker.get("URI") or "").strip().rstrip("/")
                if uri:
                    merged[uri] = dict(tracker)
        for section in CONFIG.sections():
            if section == "qBit" or section.startswith("qBit-"):
                continue
            for tracker in CONFIG.get(f"{section}.Torrent.Trackers", fallback=[]):
                if isinstance(tracker, dict):
                    uri = (tracker.get("URI") or "").strip().rstrip("/")
                    if uri:
                        merged[uri] = dict(tracker)
        return list(merged.values())

    def get_client(self):
        """Get the qBit client for this instance.

        Uses a dedicated client if running in a child process (set in run_processing_loop),
        otherwise falls back to the shared client from qBitManager.
        """
        if hasattr(self, "_dedicated_client") and self._dedicated_client is not None:
            return self._dedicated_client
        return self.qbit_manager.get_client(self.instance_name)

    def get_seeding_config(self, category: str) -> dict:
        """
        Get seeding configuration for a category.

        Args:
            category: Category name

        Returns:
            Seeding config dict (per-category override or default)
        """
        if category in self.category_overrides:
            self.logger.debug("Using category-specific seeding config for '%s'", category)
            return self.category_overrides[category]
        return self.default_seeding

    def process_torrents(self):
        """Process all torrents in managed categories."""
        client = self.get_client()
        if not client:
            self.logger.warning(
                "qBit client not available for instance '%s', skipping", self.instance_name
            )
            return

        for category in self.managed_categories:
            try:
                # Fetch torrents in this category
                torrents = client.torrents_info(category=category)
                self.logger.debug(
                    "Processing %d torrents in category '%s'",
                    len(torrents),
                    category,
                )

                for torrent in torrents:
                    self._process_single_torrent(torrent, category)

            except Exception as e:
                self.logger.error(
                    "Error processing category '%s': %s",
                    category,
                    e,
                    exc_info=True,
                )

    def _process_single_torrent(self, torrent: TorrentDictionary, category: str):
        """
        Process a single torrent - apply seeding settings and check removal.

        Args:
            torrent: qBittorrent torrent object
            category: Category name
        """
        try:
            config = self.get_seeding_config(category)

            # Get tracker-specific config and apply tags / override seeding values
            tracker_config = self._get_tracker_config(torrent)
            if tracker_config:
                # Apply tracker-specific tags
                tags = tracker_config.get("AddTags", [])
                if tags:
                    self._apply_tags(torrent, tags)
                # Merge tracker overrides into effective config (tracker wins over category
                # for seeding fields; skip non-seeding tracker metadata keys)
                _skip = {"URI", "Priority", "Name", "AddTags", "HitAndRunMode",
                         "MinSeedRatio", "MinSeedingTimeDays", "HitAndRunMinimumDownloadPercent",
                         "HitAndRunPartialSeedRatio", "TrackerUpdateBuffer"}
                effective_config = {
                    **config,
                    **{k: v for k, v in tracker_config.items() if k not in _skip},
                }
            else:
                effective_config = config

            # Apply seeding limits using effective (possibly tracker-overridden) config
            self._apply_seeding_limits(torrent, effective_config)

            # Check if torrent should be removed
            if self._should_remove_torrent(torrent, effective_config):
                self._remove_torrent(torrent, category)

        except Exception as e:
            self.logger.error(
                "Error processing torrent '%s' in category '%s': %s",
                torrent.name,
                category,
                e,
                exc_info=True,
            )

    def _apply_tags(self, torrent: TorrentDictionary, tags: list):
        """
        Apply tags to a torrent if not already present.

        Args:
            torrent: qBittorrent torrent object
            tags: List of tag strings to apply
        """
        try:
            existing_tags = {t.strip() for t in (torrent.tags or "").split(",") if t.strip()}
            new_tags = [t for t in tags if t not in existing_tags]
            self.logger.debug(
                "Tag check for '%s': existing=%s, want=%s, new=%s",
                torrent.name,
                existing_tags,
                tags,
                new_tags,
            )
            if new_tags:
                torrent.add_tags(tags=new_tags)
                self.logger.debug("Applied tags %s to '%s'", new_tags, torrent.name)
        except Exception as e:
            self.logger.error("Failed to apply tags to '%s': %s", torrent.name, e)

    def _apply_seeding_limits(self, torrent: TorrentDictionary, config: dict):
        """
        Apply rate limits to a torrent.

        qBitrr owns all deletion decisions based on configured limits.
        Never delegate stop/pause to qBit via share limits.

        Args:
            torrent: qBittorrent torrent object
            config: Seeding configuration dict
        """
        dl_limit = config.get("DownloadRateLimitPerTorrent", -1)
        if dl_limit >= 0:
            try:
                # qBittorrent expects rate limits in bytes/s
                # Config is in KB/s, so multiply by 1024
                limit_bytes = dl_limit * 1024 if dl_limit > 0 else -1
                torrent.set_download_limit(limit=limit_bytes)
                self.logger.debug(
                    "Set download limit for '%s': %d KB/s",
                    torrent.name,
                    dl_limit,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to set download limit for '%s': %s",
                    torrent.name,
                    e,
                )

        # Apply upload rate limit
        ul_limit = config.get("UploadRateLimitPerTorrent", -1)
        if ul_limit >= 0:
            try:
                # qBittorrent expects rate limits in bytes/s
                # Config is in KB/s, so multiply by 1024
                limit_bytes = ul_limit * 1024 if ul_limit > 0 else -1
                torrent.set_upload_limit(limit=limit_bytes)
                self.logger.debug(
                    "Set upload limit for '%s': %d KB/s",
                    torrent.name,
                    ul_limit,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to set upload limit for '%s': %s",
                    torrent.name,
                    e,
                )

    def _should_remove_torrent(self, torrent: TorrentDictionary, config: dict) -> bool:
        """
        Check if torrent meets removal conditions.

        - Seeding limits (ratio/time) only apply to COMPLETED/UPLOADING torrents
        - HnR protection only applies to DOWNLOADING torrents

        Args:
            torrent: qBittorrent torrent object
            config: Seeding configuration dict

        Returns:
            True if torrent should be removed, False otherwise
        """
        remove_mode = config.get("RemoveTorrent", -1)

        if remove_mode == -1:
            return False

        is_uploading = torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
            TorrentStates.FORCED_UPLOAD,
        )
        is_downloading = torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.QUEUED_DOWNLOAD,
            TorrentStates.PAUSED_DOWNLOAD,
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.METADATA_DOWNLOAD,
        )

        if not is_uploading:
            return False

        ratio_limit = config.get("MaxUploadRatio", -1)
        time_limit = config.get("MaxSeedingTime", -1)

        ratio_met = ratio_limit > 0 and torrent.ratio >= ratio_limit
        time_met = time_limit > 0 and torrent.seeding_time >= time_limit

        should_remove = False
        if remove_mode == 1:
            should_remove = ratio_met
        elif remove_mode == 2:
            should_remove = time_met
        elif remove_mode == 3:
            should_remove = ratio_met or time_met
        elif remove_mode == 4:
            should_remove = ratio_met and time_met

        if should_remove:
            tracker_config = self._get_tracker_config(torrent)
            hnr_config = tracker_config if tracker_config else config

            if hnr_config.get("HitAndRunMode", False) and self._hnr_tracker_is_dead(
                torrent, hnr_config
            ):
                self.logger.debug(
                    "HnR bypass: tracker reports torrent as unregistered/dead '%s'",
                    torrent.name,
                )
                return True

            if is_downloading and not self._hnr_safe_to_remove(torrent, hnr_config):
                self.logger.debug(
                    "HnR protection: keeping downloading torrent '%s' (ratio=%.2f, seeding=%ds)",
                    torrent.name,
                    torrent.ratio,
                    torrent.seeding_time,
                )
                return False

        return should_remove

    def _get_tracker_config(self, torrent: TorrentDictionary) -> dict | None:
        """Find the highest-priority matching tracker config for this torrent."""
        if not self.trackers:
            return None
        try:
            torrent_hosts = {
                _extract_tracker_host(getattr(t, "url", ""))
                for t in torrent.trackers
                if hasattr(t, "url")
            } - {""}
        except Exception as e:
            self.logger.debug("Failed to get trackers for '%s': %s", torrent.name, e)
            return None
        config_hosts = {
            _extract_tracker_host((tc.get("URI") or "").strip().rstrip("/"))
            for tc in self.trackers
            if isinstance(tc, dict)
        } - {""}
        self.logger.debug(
            "Tracker match for '%s': torrent_hosts=%s, config_hosts=%s",
            torrent.name,
            torrent_hosts,
            config_hosts,
        )
        best = None
        best_priority = -1
        for tracker_cfg in self.trackers:
            if not isinstance(tracker_cfg, dict):
                continue
            uri = (tracker_cfg.get("URI") or "").strip().rstrip("/")
            priority = tracker_cfg.get("Priority", 0)
            cfg_host = _extract_tracker_host(uri)
            # Use apex/suffix matching: cfg_host "example.com" matches both
            # "example.com" (exact) and "sub.example.com" (subdomain)
            host_match = any(
                h == cfg_host or h.endswith("." + cfg_host) for h in torrent_hosts
            )
            if cfg_host and host_match and priority > best_priority:
                best = tracker_cfg
                best_priority = priority
        return best

    def _hnr_tracker_is_dead(self, torrent: TorrentDictionary, config: dict) -> bool:
        """Check if the HnR-enabled tracker reports the torrent as unregistered."""
        _dead_keywords = {
            "unregistered torrent",
            "torrent not registered",
            "info hash is not authorized",
            "torrent is not authorized",
            "not found",
            "torrent not found",
        }
        uri = (config.get("URI") or "").strip().rstrip("/")
        cfg_host = _extract_tracker_host(uri)
        if not cfg_host:
            return False
        try:
            for tracker in torrent.trackers:
                tracker_url = (getattr(tracker, "url", None) or "").rstrip("/")
                if _extract_tracker_host(tracker_url) != cfg_host:
                    continue
                message_text = (getattr(tracker, "msg", "") or "").lower()
                if any(keyword in message_text for keyword in _dead_keywords):
                    return True
        except Exception:
            pass
        return False

    def _hnr_safe_to_remove(self, torrent: TorrentDictionary, config: dict) -> bool:
        """
        Check if Hit and Run obligations are met for this torrent.

        Args:
            torrent: qBittorrent torrent object
            config: Seeding configuration dict

        Returns:
            True if HnR obligations are met (safe to remove), False otherwise
        """
        if not config.get("HitAndRunMode", False):
            return True

        min_ratio = config.get("MinSeedRatio", 1.0)
        min_time_secs = config.get("MinSeedingTimeDays", 0) * 86400
        min_dl_pct = config.get("HitAndRunMinimumDownloadPercent", 10) / 100.0
        partial_ratio = config.get("HitAndRunPartialSeedRatio", 1.0)
        buffer_secs = config.get("TrackerUpdateBuffer", 0)

        is_partial = torrent.progress < 1.0 and torrent.progress >= min_dl_pct
        effective_seeding_time = torrent.seeding_time - buffer_secs

        if torrent.progress < min_dl_pct:
            return True  # Below minimum download threshold, no HnR obligation
        if is_partial:
            return torrent.ratio >= partial_ratio  # Partial: ratio only

        ratio_met = torrent.ratio >= min_ratio if min_ratio > 0 else False
        time_met = effective_seeding_time >= min_time_secs if min_time_secs > 0 else False

        if min_ratio > 0 and min_time_secs > 0:
            return ratio_met or time_met  # Either clears HnR
        elif min_ratio > 0:
            return ratio_met
        elif min_time_secs > 0:
            return time_met
        return True

    def _remove_torrent(self, torrent: TorrentDictionary, category: str):
        """
        Remove torrent that met seeding goals.

        Args:
            torrent: qBittorrent torrent object
            category: Category name
        """
        try:
            self.logger.info(
                "Removing torrent '%s' from category '%s' " "(ratio: %.2f, seeding time: %ds)",
                torrent.name,
                category,
                torrent.ratio,
                torrent.seeding_time,
            )
            # Remove from qBit but keep files
            torrent.delete(delete_files=False)
        except Exception as e:
            self.logger.error(
                "Failed to remove torrent '%s': %s",
                torrent.name,
                e,
                exc_info=True,
            )

    def _create_dedicated_client(self):
        """Create a dedicated qBit client for this process to avoid HTTP session sharing."""
        import qbittorrentapi

        metadata = self.qbit_manager.instance_metadata.get(self.instance_name, {})
        host = metadata.get("host", "localhost")
        port = metadata.get("port", 8080)
        username = metadata.get("username")
        # Read password from config since it's not stored in metadata
        from qBitrr.config import CONFIG

        # instance_name is the config section name (e.g. "qBit" or "qBit-Seedbox")
        password = CONFIG.get(f"{self.instance_name}.Password", fallback=None)
        client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            SIMPLE_RESPONSES=False,
        )
        self.logger.debug(
            "Created dedicated qBit client for category manager '%s'",
            self.instance_name,
        )
        return client

    def run_processing_loop(self):
        """
        Main processing loop for qBit-managed categories.

        This runs in a separate process and continuously processes torrents.
        """
        # Create a dedicated client for this process to avoid sharing
        # the parent's HTTP session, which causes response cross-contamination
        # ("Invalid version" errors) when concurrent requests are made.
        self._dedicated_client = self._create_dedicated_client()

        # Pre-create all tracker AddTags in qBittorrent so they exist before
        # being added to individual torrents (some qBit versions need this)
        all_tracker_tags = list(
            {tag for tc in self.trackers if isinstance(tc, dict) for tag in tc.get("AddTags", [])}
        )
        if all_tracker_tags:
            try:
                self._dedicated_client.torrents_create_tags(tags=all_tracker_tags)
                self.logger.debug("Pre-created tracker tags: %s", all_tracker_tags)
            except Exception as e:
                self.logger.warning("Failed to pre-create tracker tags: %s", e)

        self.logger.info(
            "Starting processing loop for qBit category manager '%s'",
            self.instance_name,
        )

        while not self.qbit_manager.shutdown_event.is_set():
            try:
                self.process_torrents()
                time.sleep(LOOP_SLEEP_TIMER)

            except DelayLoopException as e:
                # Intentional delay requested
                self.logger.debug("Delaying loop for %d seconds", e.length)
                time.sleep(e.length)

            except Exception as e:
                self.logger.error(
                    "Error in qBit category processing loop: %s",
                    e,
                    exc_info=True,
                )
                # Sleep before retrying to avoid rapid error loops
                time.sleep(60)

        self.logger.info(
            "Shutdown event received, stopping processing loop for '%s'",
            self.instance_name,
        )
