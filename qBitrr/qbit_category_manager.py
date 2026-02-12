"""qBit Category Manager - Manages torrents in qBit-managed categories with seeding settings."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

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
        self.logger = logging.getLogger(f"qBitrr.qBitCategory.{instance_name}")

        self.logger.info(
            "Initialized qBit category manager for instance '%s' with %d categories: %s",
            instance_name,
            len(self.managed_categories),
            ", ".join(self.managed_categories),
        )

    def get_client(self):
        """Get the qBit client for this instance."""
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

            # Apply seeding limits
            self._apply_seeding_limits(torrent, config)

            # Check if torrent should be removed
            if self._should_remove_torrent(torrent, config):
                self._remove_torrent(torrent, category)

        except Exception as e:
            self.logger.error(
                "Error processing torrent '%s' in category '%s': %s",
                torrent.name,
                category,
                e,
                exc_info=True,
            )

    def _apply_seeding_limits(self, torrent: TorrentDictionary, config: dict):
        """
        Apply seeding limits to a torrent.

        Args:
            torrent: qBittorrent torrent object
            config: Seeding configuration dict
        """
        ratio_limit = config.get("MaxUploadRatio", -1)
        time_limit = config.get("MaxSeedingTime", -1)

        # Prepare share limits
        share_limits = {}
        if ratio_limit > 0:
            share_limits["ratio_limit"] = ratio_limit
        if time_limit > 0:
            share_limits["seeding_time_limit"] = time_limit

        # Apply share limits if any
        if share_limits:
            try:
                torrent.set_share_limits(**share_limits)
                self.logger.debug(
                    "Applied share limits to '%s': %s",
                    torrent.name,
                    share_limits,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to set share limits for '%s': %s",
                    torrent.name,
                    e,
                )

        # Apply download rate limit
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

        Args:
            torrent: qBittorrent torrent object
            config: Seeding configuration dict

        Returns:
            True if torrent should be removed, False otherwise
        """
        remove_mode = config.get("RemoveTorrent", -1)

        if remove_mode == -1:
            return False  # Never remove

        ratio_limit = config.get("MaxUploadRatio", -1)
        time_limit = config.get("MaxSeedingTime", -1)

        # Check if limits are met
        ratio_met = ratio_limit > 0 and torrent.ratio >= ratio_limit
        time_met = time_limit > 0 and torrent.seeding_time >= time_limit

        # Determine removal based on mode
        should_remove = False
        if remove_mode == 1:  # Remove on ratio only
            should_remove = ratio_met
        elif remove_mode == 2:  # Remove on time only
            should_remove = time_met
        elif remove_mode == 3:  # Remove on OR (either condition)
            should_remove = ratio_met or time_met
        elif remove_mode == 4:  # Remove on AND (both conditions)
            should_remove = ratio_met and time_met

        # HnR protection: block removal if obligations not met
        if should_remove and not self._hnr_safe_to_remove(torrent, config):
            self.logger.debug(
                "HnR protection: keeping '%s' (ratio=%.2f, seeding=%ds)",
                torrent.name,
                torrent.ratio,
                torrent.seeding_time,
            )
            return False

        return should_remove

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
        partial_ratio = config.get("HitAndRunPartialSeedRatio", 1.0)
        buffer_secs = config.get("TrackerUpdateBuffer", 0)

        is_partial = torrent.progress < 1.0 and torrent.progress >= 0.1
        effective_seeding_time = torrent.seeding_time - buffer_secs

        if torrent.progress < 0.1:
            return True  # Negligible download, no HnR obligation
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

    def run_processing_loop(self):
        """
        Main processing loop for qBit-managed categories.

        This runs in a separate process and continuously processes torrents.
        """
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
