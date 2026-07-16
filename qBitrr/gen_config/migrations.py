from __future__ import annotations

import pathlib
from typing import TypeVar

from tomlkit import inline_table, table

from qBitrr.home_path import HOME_PATH

T = TypeVar("T")

from qBitrr.gen_config.config_class import MyConfig
from qBitrr.gen_config.sections import generate_doc, iter_arr_sections
from qBitrr.gen_config.validate import (
    _validate_and_fill_config,
)


def _migrate_webui_config(config: MyConfig) -> bool:
    """
    Migrate WebUI configuration from old location (Settings section) to new location (WebUI section).
    Returns True if any migration was performed, False otherwise.
    """
    migrated = False

    # Check if WebUI section exists, if not create it
    if "WebUI" not in config.config:
        config.config["WebUI"] = table()

    webui_section = config.config.get("WebUI", {})

    # Migrate Host from Settings to WebUI
    if "Host" not in webui_section:
        old_host = config.get("Settings.Host", fallback=None)
        if old_host is not None:
            webui_section["Host"] = old_host
            migrated = True
            print(f"Migrated WebUI Host from Settings to WebUI section: {old_host}")

    # Migrate Port from Settings to WebUI
    if "Port" not in webui_section:
        old_port = config.get("Settings.Port", fallback=None)
        if old_port is not None:
            webui_section["Port"] = old_port
            migrated = True
            print(f"Migrated WebUI Port from Settings to WebUI section: {old_port}")

    # Migrate Token from Settings to WebUI
    if "Token" not in webui_section:
        old_token = config.get("Settings.Token", fallback=None)
        if old_token is not None:
            webui_section["Token"] = old_token
            migrated = True
            print(f"Migrated WebUI Token from Settings to WebUI section")

    # Rename SecureCookies to BehindHttpsProxy
    if "SecureCookies" in webui_section and "BehindHttpsProxy" not in webui_section:
        webui_section["BehindHttpsProxy"] = webui_section["SecureCookies"]
        del webui_section["SecureCookies"]
        migrated = True
        print("Migrated WebUI SecureCookies to BehindHttpsProxy")

    # Remove obsolete GroupSonarr / GroupLidarr (browse is always series/artist rows)
    for obsolete_key in ("GroupSonarr", "GroupLidarr"):
        if obsolete_key in webui_section:
            del webui_section[obsolete_key]
            migrated = True
            print(f"Removed obsolete WebUI.{obsolete_key}")

    return migrated


def _migrate_process_restart_settings(config: MyConfig) -> bool:
    """
    Add process auto-restart settings to existing configs.

    Migration runs if:
    - ConfigVersion < "0.0.3"

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.3"):
        return False  # Already migrated

    # Ensure Settings section exists
    if "Settings" not in config.config:
        config.config["Settings"] = table()

    settings = config.config["Settings"]
    changes_made = False

    # Add AutoRestartProcesses if missing
    if "AutoRestartProcesses" not in settings:
        settings["AutoRestartProcesses"] = True
        changes_made = True
        logger.info("Added AutoRestartProcesses = true (default: enabled)")

    # Add MaxProcessRestarts if missing
    if "MaxProcessRestarts" not in settings:
        settings["MaxProcessRestarts"] = 5
        changes_made = True
        logger.info("Added MaxProcessRestarts = 5 (default)")

    # Add ProcessRestartWindow if missing
    if "ProcessRestartWindow" not in settings:
        settings["ProcessRestartWindow"] = 300
        changes_made = True
        logger.info("Added ProcessRestartWindow = 300 seconds (5 minutes)")

    # Add ProcessRestartDelay if missing
    if "ProcessRestartDelay" not in settings:
        settings["ProcessRestartDelay"] = 5
        changes_made = True
        logger.info("Added ProcessRestartDelay = 5 seconds")

    if changes_made:
        print("Migration v2→v3: Added process auto-restart configuration settings")

    return changes_made


def _migrate_quality_profile_mappings(config: MyConfig) -> bool:
    """
    Migrate from list-based profile config to dict-based mappings.

    Migration runs if:
    - ConfigVersion < "0.0.2"

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.2"):
        return False  # Already migrated

    changes_made = False

    for key in iter_arr_sections(config):
        entry_search_key = f"{key}.EntrySearch"
        entry_search_section = config.get(entry_search_key, fallback=None)
        if not entry_search_section:
            continue

        # Check for old format
        main_profiles = config.get(f"{entry_search_key}.MainQualityProfile", fallback=None)
        temp_profiles = config.get(f"{entry_search_key}.TempQualityProfile", fallback=None)

        # Skip if no old format found
        if not main_profiles or not temp_profiles:
            continue

        # Validate list lengths match
        if len(main_profiles) != len(temp_profiles):
            logger.error(
                f"Cannot migrate {key}: MainQualityProfile ({len(main_profiles)}) "
                f"and TempQualityProfile ({len(temp_profiles)}) have different lengths"
            )
            continue

        # Create mappings dict, filtering out empty/None values
        mappings = {
            str(main).strip(): str(temp).strip()
            for main, temp in zip(main_profiles, temp_profiles)
            if main and temp and str(main).strip() and str(temp).strip()
        }

        if mappings:
            # Set new format - use tomlkit's inline_table to ensure it's rendered as inline dict
            inline_mappings = inline_table()
            inline_mappings.update(mappings)
            config.config[str(key)]["EntrySearch"]["QualityProfileMappings"] = inline_mappings
            changes_made = True
            logger.info("Migrated %s to QualityProfileMappings: %s", key, mappings)

            # Remove old format
            del config.config[str(key)]["EntrySearch"]["MainQualityProfile"]
            del config.config[str(key)]["EntrySearch"]["TempQualityProfile"]
            logger.debug("Removed legacy profile lists from %s", key)

    return changes_made


def _migrate_qbit_subcategory_match(config: MyConfig) -> bool:
    """Add ``MatchSubcategories=false`` to every qBit section that lacks it.

    Idempotent on every startup so configs predating the subcategory feature pick
    up the new flag without any explicit version bump. Default ``false`` keeps
    existing behaviour identical (qBittorrent's ``torrents/info`` filter is
    exact-match — see ``docs/configuration/qbittorrent.md``).

    Returns:
        True if any section was updated, False otherwise.
    """
    import logging

    logger = logging.getLogger(__name__)

    changes_made = False
    for section in list(config.config.keys()):
        section_str = str(section)
        if section_str == "qBit" or section_str.startswith("qBit-"):
            qbit_section = config.config[section_str]
            if "MatchSubcategories" not in qbit_section:
                qbit_section["MatchSubcategories"] = False
                changes_made = True
                logger.info("Added MatchSubcategories = false to [%s]", section_str)
    return changes_made


def _migrate_qbit_category_settings(config: MyConfig) -> bool:
    """
    Add qBit category management settings to existing configs.

    Migration runs if:
    - ConfigVersion < "0.0.4"

    Adds ManagedCategories and CategorySeeding configuration to all qBit sections.

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.4"):
        return False  # Already migrated

    changes_made = False

    # Migrate default qBit section
    if "qBit" in config.config:
        qbit_section = config.config["qBit"]
        if "ManagedCategories" not in qbit_section:
            qbit_section["ManagedCategories"] = []
            changes_made = True
            logger.info("Added ManagedCategories = [] to [qBit]")

        # Add CategorySeeding subsection
        if "CategorySeeding" not in qbit_section:
            seeding = table()
            seeding["DownloadRateLimitPerTorrent"] = -1
            seeding["UploadRateLimitPerTorrent"] = -1
            seeding["MaxUploadRatio"] = -1
            seeding["MaxSeedingTime"] = -1
            seeding["RemoveTorrent"] = -1
            seeding["HitAndRunMode"] = "disabled"
            seeding["MinSeedRatio"] = 1.0
            seeding["MinSeedingTimeDays"] = 0
            seeding["HitAndRunMinimumDownloadPercent"] = 10
            seeding["HitAndRunPartialSeedRatio"] = 1.0
            seeding["TrackerUpdateBuffer"] = 0
            qbit_section["CategorySeeding"] = seeding
            changes_made = True
            logger.info("Added CategorySeeding configuration to [qBit]")

    # Migrate additional qBit instances (qBit-XXX)
    for section in config.config.keys():
        if str(section).startswith("qBit-"):
            qbit_section = config.config[str(section)]
            if "ManagedCategories" not in qbit_section:
                qbit_section["ManagedCategories"] = []
                changes_made = True
                logger.info("Added ManagedCategories = [] to [%s]", section)

            if "CategorySeeding" not in qbit_section:
                seeding = table()
                seeding["DownloadRateLimitPerTorrent"] = -1
                seeding["UploadRateLimitPerTorrent"] = -1
                seeding["MaxUploadRatio"] = -1
                seeding["MaxSeedingTime"] = -1
                seeding["RemoveTorrent"] = -1
                seeding["HitAndRunMode"] = "disabled"
                seeding["MinSeedRatio"] = 1.0
                seeding["MinSeedingTimeDays"] = 0
                seeding["HitAndRunMinimumDownloadPercent"] = 10
                seeding["HitAndRunPartialSeedRatio"] = 1.0
                seeding["TrackerUpdateBuffer"] = 0
                qbit_section["CategorySeeding"] = seeding
                changes_made = True
                logger.info("Added CategorySeeding configuration to [%s]", section)

    if changes_made:
        print("Migration v3→v4: Added qBit category management settings")

    return changes_made


def _migrate_hnr_settings(config: MyConfig) -> bool:
    """
    Add Hit and Run protection settings to existing configs.

    Migration runs if:
    - ConfigVersion < "5.8.8"

    Adds HnR fields to Tracker and CategorySeeding sections for all Arr and qBit instances.

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("5.8.8"):
        return False  # Already migrated

    changes_made = False
    hnr_seeding_defaults = {
        "HitAndRunMode": "disabled",
        "MinSeedRatio": 1.0,
        "MinSeedingTimeDays": 0,
        "HitAndRunMinimumDownloadPercent": 10,
        "HitAndRunPartialSeedRatio": 1.0,
        "TrackerUpdateBuffer": 0,
    }

    # Remove HnR fields from Arr SeedingMode sections (moved to tracker-only)
    for key in iter_arr_sections(config):
        if "Torrent" in config.config.get(str(key), {}):
            torrent_section = config.config[str(key)]["Torrent"]

            if "SeedingMode" in torrent_section:
                seeding = torrent_section["SeedingMode"]
                for field in hnr_seeding_defaults:
                    if field in seeding:
                        del seeding[field]
                        changes_made = True

            # Add HnR fields to each tracker
            if "Trackers" in torrent_section:
                trackers = torrent_section["Trackers"]
                if isinstance(trackers, list):
                    for tracker in trackers:
                        for field, default in hnr_seeding_defaults.items():
                            if field not in tracker:
                                tracker[field] = default
                                changes_made = True

    # Add HnR fields to qBit CategorySeeding sections
    for key in list(config.config.keys()):
        if str(key) == "qBit" or str(key).startswith("qBit-"):
            qbit_section = config.config[str(key)]
            if "CategorySeeding" in qbit_section:
                cat_seeding = qbit_section["CategorySeeding"]
                for field, default in hnr_seeding_defaults.items():
                    if field not in cat_seeding:
                        cat_seeding[field] = default
                        changes_made = True

    # Promote Arr-level trackers to qBit.Trackers (shared tracker configs)
    # Collect all Arr trackers, deduplicate by URI, promote to qBit level
    for key in list(config.config.keys()):
        if str(key) == "qBit" or str(key).startswith("qBit-"):
            qbit_section = config.config[str(key)]
            if "Trackers" not in qbit_section:
                # Collect trackers from all Arr instances
                promoted: dict[str, dict] = {}  # URI -> tracker config
                for arr_key in iter_arr_sections(config):
                    arr_key_str = str(arr_key)
                    arr_section = config.config.get(arr_key_str, {})
                    torrent_section = (
                        arr_section.get("Torrent", {}) if isinstance(arr_section, dict) else {}
                    )
                    arr_trackers = (
                        torrent_section.get("Trackers", [])
                        if isinstance(torrent_section, dict)
                        else []
                    )
                    if isinstance(arr_trackers, list):
                        for tracker in arr_trackers:
                            if isinstance(tracker, dict):
                                uri = (tracker.get("URI") or "").strip().rstrip("/")
                                if uri and uri not in promoted:
                                    promoted[uri] = dict(tracker)

                if promoted:
                    qbit_section["Trackers"] = list(promoted.values())
                    changes_made = True
                    logger.info(
                        "Promoted %d tracker(s) to [%s.Trackers]",
                        len(promoted),
                        str(key),
                    )

                    # Remove Arr-level trackers that are identical to promoted ones
                    for arr_key in list(config.config.keys()):
                        arr_key_str = str(arr_key)
                        is_arr = arr_key_str.startswith(ARR_SECTION_PREFIXES)
                        if not is_arr:
                            continue
                        arr_section = config.config.get(arr_key_str, {})
                        if not isinstance(arr_section, dict):
                            continue
                        torrent_section = arr_section.get("Torrent", {})
                        if not isinstance(torrent_section, dict):
                            continue
                        arr_trackers = torrent_section.get("Trackers", [])
                        if not isinstance(arr_trackers, list) or not arr_trackers:
                            continue

                        # Keep only trackers that differ from promoted version
                        remaining = []
                        for tracker in arr_trackers:
                            if not isinstance(tracker, dict):
                                remaining.append(tracker)
                                continue
                            uri = (tracker.get("URI") or "").strip().rstrip("/")
                            if uri in promoted and dict(tracker) == promoted[uri]:
                                continue  # Identical to qBit level, remove
                            remaining.append(tracker)

                        if len(remaining) != len(arr_trackers):
                            config.config[arr_key_str]["Torrent"]["Trackers"] = remaining
                            changes_made = True
                            logger.info(
                                "Cleaned %d identical tracker(s) from [%s.Torrent.Trackers]",
                                len(arr_trackers) - len(remaining),
                                arr_key_str,
                            )
                else:
                    qbit_section["Trackers"] = []
                    changes_made = True

    if changes_made:
        print(
            "Migration: Added Hit and Run protection settings and promoted trackers to qBit level"
        )
        logger.info("Added Hit and Run protection settings and promoted trackers to config")

    return changes_made


def _migrate_hnr_single_key(config: MyConfig) -> bool:
    """
    Consolidate HitAndRunMode (bool) + HitAndRunClearMode (string) into single HitAndRunMode string.

    Runs when ConfigVersion < "5.9.2" or when already 5.9.2 but HitAndRunClearMode is present.
    Sets HitAndRunMode = "and" | "or" | "disabled", removes HitAndRunClearMode.
    Returns True if any change was made.
    """
    from qBitrr.config_version import _parse_version, get_config_version

    current_version = _parse_version(get_config_version(config))
    valid_modes = ("and", "or", "disabled")

    def _has_hnr_clear_mode_anywhere() -> bool:
        for key in list(config.config.keys()):
            section = config.config.get(str(key))
            if not isinstance(section, dict):
                continue
            if "CategorySeeding" in section:
                cs = section["CategorySeeding"]
                if isinstance(cs, dict) and "HitAndRunClearMode" in cs:
                    return True
            if "Trackers" in section and isinstance(section["Trackers"], list):
                for t in section["Trackers"]:
                    if isinstance(t, dict) and "HitAndRunClearMode" in t:
                        return True
            if "Torrent" in section and isinstance(section["Torrent"], dict):
                tt = section["Torrent"]
                if "Trackers" in tt and isinstance(tt["Trackers"], list):
                    for t in tt["Trackers"]:
                        if isinstance(t, dict) and "HitAndRunClearMode" in t:
                            return True
        return False

    if current_version >= _parse_version("5.9.2") and not _has_hnr_clear_mode_anywhere():
        return False

    def _resolve(d: dict) -> str:
        raw_clear = d.get("HitAndRunClearMode")
        if isinstance(raw_clear, str) and raw_clear.strip().lower() in valid_modes:
            return raw_clear.strip().lower()
        raw_mode = d.get("HitAndRunMode")
        if isinstance(raw_mode, str) and raw_mode.strip().lower() in valid_modes:
            return raw_mode.strip().lower()
        # Legacy boolean HitAndRunMode
        if raw_mode is True:
            return "and"
        return "disabled"

    changes_made = False
    for key in list(config.config.keys()):
        section = config.config[str(key)]
        if not isinstance(section, dict):
            continue
        if "CategorySeeding" in section:
            cs = section["CategorySeeding"]
            if isinstance(cs, dict):
                had_clear = "HitAndRunClearMode" in cs
                had_bool = isinstance(cs.get("HitAndRunMode"), bool)
                resolved = _resolve(cs)
                cs["HitAndRunMode"] = resolved
                if had_clear:
                    del cs["HitAndRunClearMode"]
                if had_clear or had_bool:
                    changes_made = True
        if "Trackers" in section and isinstance(section["Trackers"], list):
            for tracker in section["Trackers"]:
                if isinstance(tracker, dict):
                    had_clear = "HitAndRunClearMode" in tracker
                    had_bool = isinstance(tracker.get("HitAndRunMode"), bool)
                    resolved = _resolve(tracker)
                    tracker["HitAndRunMode"] = resolved
                    if had_clear:
                        del tracker["HitAndRunClearMode"]
                    if had_clear or had_bool:
                        changes_made = True
        if "Torrent" in section and isinstance(section["Torrent"], dict):
            tt = section["Torrent"]
            if "Trackers" in tt and isinstance(tt["Trackers"], list):
                for tracker in tt["Trackers"]:
                    if isinstance(tracker, dict):
                        had_clear = "HitAndRunClearMode" in tracker
                        had_bool = isinstance(tracker.get("HitAndRunMode"), bool)
                        resolved = _resolve(tracker)
                        tracker["HitAndRunMode"] = resolved
                        if had_clear:
                            del tracker["HitAndRunClearMode"]
                        if had_clear or had_bool:
                            changes_made = True

    if changes_made:
        print("Migration 5.9.x→5.9.2: Consolidated HitAndRunMode to single key (and/or/disabled)")
    return changes_made


def apply_config_migrations(config: MyConfig) -> None:
    """
    Apply all configuration migrations and validations.
    Saves the config if any changes were made.
    """
    from qBitrr.config_version import (
        EXPECTED_CONFIG_VERSION,
        _parse_version,
        backup_config,
        get_config_version,
        set_config_version,
        validate_config_version,
    )

    changes_made = False

    # Validate config version
    is_valid, validation_result = validate_config_version(config)

    if not is_valid:
        # Config version is newer than expected - log error but continue
        print(f"WARNING: {validation_result}")
        print("Continuing with potentially incompatible config...")

    # Check if migration is needed
    current_version = _parse_version(get_config_version(config))
    expected_version = _parse_version(EXPECTED_CONFIG_VERSION)
    needs_migration = current_version < expected_version

    if needs_migration:
        print(f"Config schema upgrade needed ({current_version} -> {expected_version})")
        # Create backup before migration
        backup_path = backup_config(config.path)
        if backup_path:
            print(f"Config backup created: {backup_path}")
        else:
            print("WARNING: Could not create config backup, proceeding with migration anyway")

    # Apply migrations in order
    if _migrate_webui_config(config):
        changes_made = True

    # Migrate quality profile mappings from list to dict format (< 0.0.2)
    if _migrate_quality_profile_mappings(config):
        changes_made = True

    # Add process auto-restart settings (< 0.0.3)
    if _migrate_process_restart_settings(config):
        changes_made = True

    # Add qBit category management settings (< 0.0.4)
    if _migrate_qbit_category_settings(config):
        changes_made = True

    # Idempotent: ensure MatchSubcategories key exists on every qBit section
    if _migrate_qbit_subcategory_match(config):
        changes_made = True

    # Add Hit and Run protection settings to trackers/CategorySeeding (< 5.8.8)
    if _migrate_hnr_settings(config):
        changes_made = True

    # Consolidate HitAndRunMode to single key and/or/disabled (< 5.9.2 or 5.9.2 with ClearMode)
    if _migrate_hnr_single_key(config):
        changes_made = True

    # Database schema migrations are applied during DB startup in qBitrr.database
    # and tracked with SQLite PRAGMA user_version. ConfigVersion is still bumped here
    # so existing installs pick up release-level migration notes consistently.

    # Validate and fill config (this also ensures ConfigVersion field exists)
    if _validate_and_fill_config(config):
        changes_made = True

    # Update config version if migration was needed
    if needs_migration and current_version < expected_version:
        set_config_version(config, EXPECTED_CONFIG_VERSION)
        changes_made = True

    # Save if changes were made
    if changes_made:
        config.save()
        print("Configuration has been updated with migrations and defaults.")


def _write_config_file(docker: bool = False) -> pathlib.Path:
    doc = generate_doc()
    config_file = HOME_PATH.joinpath("config.toml")
    if docker:
        if config_file.exists():
            print(f"{config_file} already exists, keeping current configuration.")
            return config_file
    elif config_file.exists():
        print(f"{config_file} already exists, File is not being replaced.")
        config_file = pathlib.Path.cwd().joinpath("config_new.toml")
    config = MyConfig(config_file, config=doc)
    config.save()
    print(f'New config file has been saved to "{config_file}"')
    return config_file
