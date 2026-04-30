"""qBit Category Manager - Manages torrents in qBit-managed categories with seeding settings."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from qBitrr.arr_tracker_index import extract_tracker_host
from qBitrr.category_paths import (
    has_subcategory_separator,
    matches_configured,
    normalize_category,
)
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
                - trackers: Tracker config list
                - stalled_delay: Minutes before removing stalled downloads (-1 = disabled)
                - ignore_torrents_younger_than: Seconds; don't remove torrents younger than this
        """
        self.instance_name = instance_name
        self.qbit_manager = qbit_manager
        self.managed_categories = [
            normalize_category(c) for c in config.get("managed_categories", []) if c
        ]
        self.managed_categories = [c for c in self.managed_categories if c]
        self.default_seeding = config.get("default_seeding", {})
        self.category_overrides = {
            normalize_category(k): v
            for k, v in (config.get("category_overrides") or {}).items()
            if k
        }
        self.trackers = self._build_merged_trackers(config.get("trackers", []))
        self.stalled_delay = config.get("stalled_delay", -1)
        self.ignore_torrents_younger_than = config.get("ignore_torrents_younger_than", 600)
        self.allowed_stalled = self.stalled_delay != -1
        self.match_subcategories = bool(config.get("match_subcategories", False))
        self.logger = logging.getLogger(f"qBitrr.qBitCategory.{instance_name}")

        self.logger.info(
            "Initialized qBit category manager for instance '%s' with %d categories: %s "
            "(MatchSubcategories=%s)",
            instance_name,
            len(self.managed_categories),
            ", ".join(self.managed_categories),
            self.match_subcategories,
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

        With ``MatchSubcategories=true`` the override registered for the parent
        prefix (``seed``) is used for any descendant (``seed/tleech``) unless a
        more specific override exists. Exact match always wins.

        Args:
            category: Category name (full qBittorrent path)

        Returns:
            Seeding config dict (per-category override or default)
        """
        norm = normalize_category(category)
        if not norm:
            return self.default_seeding
        if norm in self.category_overrides:
            self.logger.debug("Using category-specific seeding config for '%s'", norm)
            return self.category_overrides[norm]
        if self.match_subcategories:
            match = matches_configured(norm, list(self.category_overrides.keys()), prefix=True)
            if match:
                self.logger.debug(
                    "Using inherited seeding config for '%s' (from prefix '%s')", norm, match
                )
                return self.category_overrides[match]
        return self.default_seeding

    def _owning_managed_category(self, torrent_category: str | None) -> str | None:
        """Return which configured ManagedCategories entry owns ``torrent_category``."""
        if not torrent_category:
            return None
        norm = normalize_category(torrent_category)
        if not norm:
            return None
        return matches_configured(norm, self.managed_categories, prefix=self.match_subcategories)

    def process_torrents(self):
        """Process all torrents in managed categories.

        Strategy:
        - Exact-match mode (``MatchSubcategories=false``): fetch each configured
          category individually with the qBit ``category=`` filter (fast path).
        - Subcategory-match mode: fetch the full torrent list once and dispatch
          torrents to their owning configured prefix in Python. This is necessary
          because qBittorrent's API filter is exact-match and would silently miss
          children of a configured parent.
        """
        client = self.get_client()
        if not client:
            self.logger.warning(
                "qBit client not available for instance '%s', skipping", self.instance_name
            )
            return

        if self.match_subcategories:
            try:
                torrents = client.torrents_info()
            except Exception as e:
                self.logger.error(
                    "Error fetching torrents for subcategory dispatch: %s", e, exc_info=True
                )
                return
            dispatched = 0
            for torrent in torrents:
                cat = getattr(torrent, "category", None)
                owner = self._owning_managed_category(cat)
                if owner is None:
                    continue
                dispatched += 1
                self._process_single_torrent(torrent, normalize_category(cat) or owner)
            self.logger.debug(
                "Subcategory dispatch processed %d torrents across %d categories",
                dispatched,
                len(self.managed_categories),
            )
            return

        for category in self.managed_categories:
            try:
                if has_subcategory_separator(category):
                    self.logger.debug(
                        "Fetching torrents for subcategory path '%s' (exact match)", category
                    )
                # Fetch torrents in this category (exact match)
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
        Process a single torrent - apply seeding settings, stalled removal, and ratio/time removal.

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
                _skip = {
                    "URI",
                    "Priority",
                    "Name",
                    "AddTags",
                    "HitAndRunMode",
                    "MinSeedRatio",
                    "MinSeedingTimeDays",
                    "HitAndRunMinimumDownloadPercent",
                    "HitAndRunPartialSeedRatio",
                    "TrackerUpdateBuffer",
                }
                effective_config = {
                    **config,
                    **{k: v for k, v in tracker_config.items() if k not in _skip},
                }
            else:
                effective_config = config

            # Apply seeding limits using effective (possibly tracker-overridden) config
            self._apply_seeding_limits(torrent, effective_config)

            # PlaceHolderArr runs the full state machine for qBit-managed categories (stalled,
            # ratio/time removal, missing files, recheck). No duplicate removal here.
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

    def _get_tracker_config(self, torrent: TorrentDictionary) -> dict | None:
        """Find the highest-priority matching tracker config for this torrent."""
        if not self.trackers:
            return None
        try:
            torrent_hosts = {
                extract_tracker_host(getattr(t, "url", ""))
                for t in torrent.trackers
                if hasattr(t, "url")
            } - {""}
        except Exception as e:
            self.logger.debug("Failed to get trackers for '%s': %s", torrent.name, e)
            return None
        config_hosts = {
            extract_tracker_host((tc.get("URI") or "").strip().rstrip("/"))
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
            cfg_host = extract_tracker_host(uri)
            # Use apex/suffix matching: cfg_host "example.com" matches both
            # "example.com" (exact) and "sub.example.com" (subdomain)
            host_match = any(h == cfg_host or h.endswith("." + cfg_host) for h in torrent_hosts)
            if cfg_host and host_match and priority > best_priority:
                best = tracker_cfg
                best_priority = priority
        return best

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
        skip_tls_verify = CONFIG.get(f"{self.instance_name}.SkipTLSVerify", fallback=False)
        client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            SIMPLE_RESPONSES=False,
            VERIFY_WEBUI_CERTIFICATE=not skip_tls_verify,
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
