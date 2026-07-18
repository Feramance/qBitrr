"""Classify config key changes into reload strategies for live config updates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from qBitrr.gen_config import ARR_SECTION_PREFIXES

_ARR_KEY_RE = re.compile(
    r"^(?P<prefix>Radarr|Sonarr|Lidarr)"
    r"(?P<inst_suffix>[-.][A-Za-z0-9-]+)?"
    r"\.(?P<suffix>.+)$",
    re.IGNORECASE,
)

FRONTEND_ONLY_KEYS = frozenset(
    {
        "WebUI.LiveArr",
        "WebUI.Theme",
        "WebUI.ViewDensity",
    }
)

WEBUI_RESTART_KEYS = frozenset(
    {
        "WebUI.Host",
        "WebUI.Port",
        "WebUI.Token",
        "WebUI.UrlBase",
        "WebUI.AuthDisabled",
        "WebUI.BehindHttpsProxy",
        "WebUI.LocalAuthEnabled",
        "WebUI.OIDCEnabled",
        "WebUI.PasswordHash",
        "WebUI.OIDC.Authority",
        "WebUI.OIDC.ClientId",
        "WebUI.OIDC.ClientSecret",
        "WebUI.OIDC.Scopes",
        "WebUI.OIDC.CallbackPath",
        "WebUI.OIDC.RequireHttpsMetadata",
    }
)

SETTINGS_LIVE_KEYS = frozenset(
    {
        "Settings.ConsoleLevel",
        "Settings.LoopSleepTimer",
        "Settings.SearchLoopDelay",
        "Settings.NoInternetSleepTimer",
        "Settings.CompletedDownloadFolder",
        "Settings.AutoPauseResume",
        "Settings.PingURLS",
        "Settings.IgnoreTorrentsYoungerThan",
        "Settings.FFprobeAutoUpdate",
        "Settings.AutoUpdateEnabled",
        "Settings.AutoUpdateCron",
        "Settings.FreeSpace",
        "Settings.FreeSpaceFolder",
    }
)

SETTINGS_FULL_RESTART_KEYS = frozenset(
    {
        "Settings.Logging",
        "Settings.Tagless",
        # PlaceHolderArr registers failed/recheck category names at ArrManager init;
        # renames require a full rebuild so workers track the new category strings.
        "Settings.FailedCategory",
        "Settings.RecheckCategory",
        "Settings.AutoRestartProcesses",
        "Settings.MaxProcessRestarts",
        "Settings.ProcessRestartWindow",
        "Settings.ProcessRestartDelay",
        "Settings.ConfigVersion",
    }
)

QBIT_CONNECTION_SUFFIXES = frozenset(
    {"Disabled", "Host", "Port", "UserName", "Password", "SkipTLSVerify"}
)

QBIT_HOT_SUFFIXES = (
    "ManagedCategories",
    "MatchSubcategories",
    "Trackers",
    "CategorySeeding",
)

ARR_RESET_DB_SUFFIXES = frozenset(
    {
        "EntrySearch.QualityProfileMappings",
        "EntrySearch.MainQualityProfile",
        "EntrySearch.TempQualityProfile",
        "EntrySearch.UseTempForMissing",
        "EntrySearch.KeepTempProfile",
        "EntrySearch.ForceResetTempProfiles",
        "EntrySearch.ProfileSwitchRetryAttempts",
        "EntrySearch.TempProfileResetTimeoutMinutes",
    }
)

ARR_RESPAWN_PRESERVE_DB_SUFFIXES = frozenset(
    {
        "URI",
        "APIKey",
        "SkipTLSVerify",
        "Category",
        "Managed",
        "importMode",
    }
)


class ReloadCategory(StrEnum):
    """Reload strategy for a config key or batch of changes."""

    LIVE = "live"
    ARR_PRESERVE_DB = "arr_preserve_db"
    ARR_RESET_DB = "arr_reset_db"
    QBIT_HOT = "qbit_hot"
    WEBUI_RESTART = "webui_restart"
    FRONTEND_ONLY = "frontend_only"
    FULL_RESTART = "full_restart"


@dataclass
class ReloadPlan:
    """Aggregated reload plan for a config update request."""

    by_key: dict[str, ReloadCategory] = field(default_factory=dict)
    live_keys: list[str] = field(default_factory=list)
    frontend_keys: list[str] = field(default_factory=list)
    webui_keys: list[str] = field(default_factory=list)
    full_restart_keys: list[str] = field(default_factory=list)
    qbit_hot_sections: set[str] = field(default_factory=set)
    arr_reset_instances: dict[str, list[str]] = field(default_factory=dict)
    arr_respawn_instances: dict[str, list[str]] = field(default_factory=dict)
    arr_live_instances: dict[str, list[str]] = field(default_factory=dict)

    @property
    def needs_full_restart(self) -> bool:
        return bool(self.full_restart_keys)

    @property
    def needs_webui_restart(self) -> bool:
        return bool(self.webui_keys)

    @property
    def needs_qbit_hot(self) -> bool:
        return bool(self.qbit_hot_sections)

    @property
    def has_arr_worker_reload(self) -> bool:
        return bool(self.arr_reset_instances or self.arr_respawn_instances)

    @property
    def affected_arr_instances(self) -> set[str]:
        instances: set[str] = set()
        instances.update(self.arr_reset_instances)
        instances.update(self.arr_respawn_instances)
        instances.update(self.arr_live_instances)
        return instances

    def primary_reload_type(self) -> str:
        """Return the WebUI ``reloadType`` string for this plan."""
        if self.needs_full_restart:
            return "full"
        if self.arr_reset_instances or self.arr_respawn_instances:
            count = len(set(self.arr_reset_instances) | set(self.arr_respawn_instances))
            return "multi_arr" if count > 1 else "single_arr"
        if self.needs_webui_restart:
            return "webui"
        if self.needs_qbit_hot:
            return "qbit_hot"
        if self.live_keys or self.arr_live_instances:
            return "live"
        if self.frontend_keys:
            return "frontend"
        return "none"


def _is_qbit_section_prefix(section: str) -> bool:
    return section == "qBit" or section.startswith("qBit-")


def _qbit_section_for_key(key: str) -> str | None:
    section = key.split(".", 1)[0]
    if _is_qbit_section_prefix(section):
        return section
    return None


def _arr_instance_for_key(key: str) -> tuple[str, str] | None:
    match = _ARR_KEY_RE.match(key)
    if not match:
        return None
    instance = match.group("prefix") + (match.group("inst_suffix") or "")
    return instance, match.group("suffix")


def _classify_arr_suffix(suffix: str) -> ReloadCategory:
    lowered = suffix.casefold()
    for preserve in ARR_RESPAWN_PRESERVE_DB_SUFFIXES:
        if lowered == preserve.casefold():
            return ReloadCategory.ARR_PRESERVE_DB
    for reset_suffix in ARR_RESET_DB_SUFFIXES:
        reset_lower = reset_suffix.casefold()
        if lowered == reset_lower or lowered.startswith(f"{reset_lower}."):
            return ReloadCategory.ARR_RESET_DB
    return ReloadCategory.LIVE


def _classify_qbit_key(key: str) -> ReloadCategory:
    section = _qbit_section_for_key(key)
    if section is None:
        return ReloadCategory.FULL_RESTART
    suffix = key.split(".", 1)[1] if "." in key else ""
    lowered = suffix.casefold()
    if any(lowered == conn.casefold() for conn in QBIT_CONNECTION_SUFFIXES):
        return ReloadCategory.FULL_RESTART
    for hot in QBIT_HOT_SUFFIXES:
        hot_lower = hot.casefold()
        if lowered == hot_lower or lowered.startswith(f"{hot_lower}."):
            return ReloadCategory.QBIT_HOT
    return ReloadCategory.FULL_RESTART


def _frozenset_member(key: str, members: frozenset[str]) -> str | None:
    """Return the canonical frozenset member for ``key`` (case-insensitive)."""
    if key in members:
        return key
    lowered = key.casefold()
    for member in members:
        if member.casefold() == lowered:
            return member
    return None


def classify_config_key(key: str) -> ReloadCategory:
    """Classify a dotted config key into a reload category."""
    if _frozenset_member(key, FRONTEND_ONLY_KEYS):
        return ReloadCategory.FRONTEND_ONLY
    if _frozenset_member(key, WEBUI_RESTART_KEYS):
        return ReloadCategory.WEBUI_RESTART
    if key.casefold().startswith("webui."):
        return ReloadCategory.WEBUI_RESTART
    if key.casefold().startswith("settings."):
        if _frozenset_member(key, SETTINGS_LIVE_KEYS):
            return ReloadCategory.LIVE
        return ReloadCategory.FULL_RESTART

    qbit_section = _qbit_section_for_key(key)
    if qbit_section is not None:
        return _classify_qbit_key(key)

    arr_match = _arr_instance_for_key(key)
    if arr_match is not None:
        instance, suffix = arr_match
        if not any(instance.casefold().startswith(p.casefold()) for p in ARR_SECTION_PREFIXES):
            return ReloadCategory.FULL_RESTART
        return _classify_arr_suffix(suffix)

    return ReloadCategory.FULL_RESTART


def classify_config_changes(changes: Mapping[str, Any]) -> ReloadPlan:
    """Build a reload plan from a ``changes`` dict (dotted keys → values)."""
    plan = ReloadPlan()

    for key in changes:
        category = classify_config_key(key)
        plan.by_key[key] = category

        if category == ReloadCategory.FRONTEND_ONLY:
            plan.frontend_keys.append(key)
        elif category == ReloadCategory.WEBUI_RESTART:
            plan.webui_keys.append(key)
        elif category == ReloadCategory.FULL_RESTART:
            plan.full_restart_keys.append(key)
        elif category == ReloadCategory.LIVE:
            arr_match = _arr_instance_for_key(key)
            if arr_match:
                plan.arr_live_instances.setdefault(arr_match[0], []).append(key)
            else:
                plan.live_keys.append(key)
        elif category == ReloadCategory.QBIT_HOT:
            section = _qbit_section_for_key(key)
            if section:
                plan.qbit_hot_sections.add(section)
        elif category == ReloadCategory.ARR_RESET_DB:
            arr_match = _arr_instance_for_key(key)
            if arr_match:
                plan.arr_reset_instances.setdefault(arr_match[0], []).append(key)
        elif category == ReloadCategory.ARR_PRESERVE_DB:
            arr_match = _arr_instance_for_key(key)
            if arr_match:
                plan.arr_respawn_instances.setdefault(arr_match[0], []).append(key)
        else:
            arr_match = _arr_instance_for_key(key)
            if arr_match:
                plan.arr_live_instances.setdefault(arr_match[0], []).append(key)

    return plan


def qbit_sections_from_changes(changes: Mapping[str, Any]) -> list[str]:
    """Return qBit section names referenced in a changes dict."""
    sections: set[str] = set()
    for key in changes:
        section = _qbit_section_for_key(key)
        if section:
            sections.add(section)
    return sorted(sections)
