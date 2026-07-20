"""Structured config field registry shared by generate_doc, schema API, and UI codegen.

Phase 2 elevates imperative ``_gen_default_line`` calls into :class:`ConfigField`
entries. ``generate_doc()`` consumes the registry without changing emitted TOML
semantics. WebUI field inventory is derived via build-time codegen and/or
``GET /api/config/schema``; custom validators/editors stay in FE overlays.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from tomlkit import comment, nl, table
from tomlkit.items import Table

from qBitrr.home_path import APPDATA_FOLDER

FieldKind = Literal[
    "text",
    "number",
    "checkbox",
    "password",
    "select",
    "tags",
    "duration",
    "mapping",
    "trackers",
]

Comments = str | tuple[str, ...] | list[str]
CommentsFactory = Callable[[], Comments]
DefaultFactory = Callable[[], Any]


@dataclass(frozen=True)
class ConfigField:
    """One config leaf (or nested path) with TOML + optional UI metadata."""

    path: tuple[str, ...]
    default: Any
    comments: Comments | CommentsFactory
    label: str = ""
    kind: FieldKind = "text"
    options: tuple[str, ...] | None = None
    required: bool = False
    secure: bool = False
    description: str | None = None
    placeholder: str | None = None
    native_unit: Literal["seconds", "minutes"] | None = None
    allow_negative: bool = False
    """Inclusive lower bound for number/duration values (when set)."""
    minimum: float | int | None = None
    """Inclusive upper bound for number/duration values (when set)."""
    maximum: float | int | None = None
    """When False, omitted from WebUI field inventory / schema UI list."""
    ui_expose: bool = True
    """Restrict Arr template fields to these kinds (``sonarr``/``radarr``/``lidarr``)."""
    arr_kinds: frozenset[str] | None = None
    apply_live: bool | None = None
    requires_restart: bool | None = None

    @property
    def key(self) -> str:
        return self.path[-1]

    @property
    def dotted(self) -> str:
        return ".".join(self.path)

    def resolved_comments(self) -> Comments:
        if callable(self.comments):
            return self.comments()
        return self.comments

    def resolved_default(self) -> Any:
        if callable(self.default) and not isinstance(self.default, (list, dict)):
            # Only call zero-arg factories; leave lists/dicts alone.
            try:
                return self.default()  # type: ignore[misc]
            except TypeError:
                return self.default
        return self.default


def _ffprobe_comments() -> list[str]:
    return [
        "FFprobe auto updates, binaries are downloaded from https://ffbinaries.com/downloads",
        "If this is disabled and you want ffprobe to work",
        "Ensure that you add the ffprobe binary to the folder"
        f"\"{APPDATA_FOLDER.joinpath('ffprobe.exe')}\"",
        "If no `ffprobe` binary is found in the folder above all ffprobe functionality will be disabled.",
        "By default this will always be on even if config does not have these key - to disable you need to explicitly set it to `False`",
    ]


def apply_fields(target: Table, fields: Sequence[ConfigField]) -> None:
    """Write registry fields into a tomlkit table, creating nested tables as needed.

    Reuses existing nested tables on ``target`` so callers can apply fields in
    stages (e.g. Arr torrent leaves, then Trackers, then SeedingMode).
    """
    nested: dict[tuple[str, ...], Table] = {(): target}
    for cfg in fields:
        parent_path = cfg.path[:-1]
        if parent_path not in nested:
            for depth in range(1, len(parent_path) + 1):
                partial = parent_path[:depth]
                if partial in nested:
                    continue
                parent = nested[partial[:-1]]
                key = partial[-1]
                existing = parent.get(key)
                if isinstance(existing, Table):
                    nested[partial] = existing
                else:
                    child = table()
                    parent.add(key, child)
                    nested[partial] = child
        dest = nested[parent_path]
        comments = cfg.resolved_comments()
        if isinstance(comments, (list, tuple)):
            for c in comments:
                dest.add(comment(c))
        else:
            dest.add(comment(comments))
        dest.add(cfg.key, cfg.resolved_default())
        dest.add(nl())


def filter_arr_fields(fields: Sequence[ConfigField], category: str) -> list[ConfigField]:
    """Return Arr template fields applicable to ``category`` (e.g. ``Sonarr-TV``)."""
    lower = category.lower()
    kind = "sonarr" if "sonarr" in lower else "radarr" if "radarr" in lower else "lidarr"
    out: list[ConfigField] = []
    for cfg in fields:
        if cfg.arr_kinds is None or kind in cfg.arr_kinds:
            out.append(cfg)
    return out


def enrich_reload_metadata(section: str, fields: Sequence[ConfigField]) -> list[ConfigField]:
    """Attach ``apply_live`` / ``requires_restart`` from :mod:`config_reload_policy`."""
    from qBitrr.config_reload_policy import (
        FRONTEND_ONLY_KEYS,
        SETTINGS_FULL_RESTART_KEYS,
        SETTINGS_LIVE_KEYS,
        WEBUI_RESTART_KEYS,
    )

    enriched: list[ConfigField] = []
    for cfg in fields:
        key = f"{section}.{cfg.dotted}" if section else cfg.dotted
        apply_live = cfg.apply_live
        requires_restart = cfg.requires_restart
        if apply_live is None:
            apply_live = key in SETTINGS_LIVE_KEYS or key in FRONTEND_ONLY_KEYS
        if requires_restart is None:
            requires_restart = key in SETTINGS_FULL_RESTART_KEYS or key in WEBUI_RESTART_KEYS
        if apply_live == cfg.apply_live and requires_restart == cfg.requires_restart:
            enriched.append(cfg)
        else:
            enriched.append(replace(cfg, apply_live=apply_live, requires_restart=requires_restart))
    return enriched


def field_to_schema_dict(section: str, cfg: ConfigField) -> dict[str, Any]:
    """JSON-serializable schema entry for one field."""
    data = {
        "section": section,
        "path": list(cfg.path),
        "key": cfg.dotted,
        "label": cfg.label or cfg.key,
        "kind": cfg.kind,
        "default": cfg.resolved_default(),
        "comments": cfg.resolved_comments(),
        "required": cfg.required,
        "secure": cfg.secure,
        "uiExpose": cfg.ui_expose,
        "applyLive": cfg.apply_live,
        "requiresRestart": cfg.requires_restart,
    }
    if cfg.options is not None:
        data["options"] = list(cfg.options)
    if cfg.description:
        data["description"] = cfg.description
    if cfg.placeholder:
        data["placeholder"] = cfg.placeholder
    if cfg.native_unit:
        data["nativeUnit"] = cfg.native_unit
    if cfg.allow_negative:
        data["allowNegative"] = True
    if cfg.minimum is not None:
        data["minimum"] = cfg.minimum
    if cfg.maximum is not None:
        data["maximum"] = cfg.maximum
    if cfg.arr_kinds is not None:
        data["arrKinds"] = sorted(cfg.arr_kinds)
    return data


def build_config_schema() -> dict[str, Any]:
    """Full registry snapshot for ``GET /api/config/schema`` and codegen."""
    from qBitrr.gen_config.fields_arr import ARR_FIELDS

    settings = enrich_reload_metadata("Settings", SETTINGS_FIELDS)
    webui = enrich_reload_metadata("WebUI", WEBUI_FIELDS)
    qbit = enrich_reload_metadata("qBit", QBIT_FIELDS)
    arr = list(ARR_FIELDS)
    return {
        "version": 1,
        "sections": {
            "Settings": [field_to_schema_dict("Settings", f) for f in settings],
            "WebUI": [field_to_schema_dict("WebUI", f) for f in webui],
            "qBit": [field_to_schema_dict("qBit", f) for f in qbit],
            "Arr": [field_to_schema_dict("Arr", f) for f in arr],
        },
    }


def iter_inventory_paths() -> Iterable[str]:
    """Dotted inventory paths (Settings./WebUI./qBit./Arr.) for drift tooling."""
    from qBitrr.gen_config.fields_arr import ARR_FIELDS

    for f in SETTINGS_FIELDS:
        yield f"Settings.{f.dotted}"
    for f in WEBUI_FIELDS:
        yield f"WebUI.{f.dotted}"
    for f in QBIT_FIELDS:
        yield f"qBit.{f.dotted}"
    for f in ARR_FIELDS:
        yield f"Arr.{f.dotted}"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

SETTINGS_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        ("ConfigVersion",),
        "5.12.12",
        (
            "Internal config schema version - DO NOT MODIFY",
            "This is managed automatically by qBitrr for config migrations",
        ),
        label="Config Version",
        ui_expose=False,
    ),
    ConfigField(
        ("ConsoleLevel",),
        "INFO",
        "Level of logging; One of CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE",
        label="Console Level",
        kind="select",
        options=(
            "CRITICAL",
            "ERROR",
            "WARNING",
            "NOTICE",
            "INFO",
            "DEBUG",
            "TRACE",
        ),
        required=True,
    ),
    ConfigField(
        ("Logging",),
        True,
        "Enable logging to files",
        label="Logging",
        kind="checkbox",
    ),
    ConfigField(
        ("CompletedDownloadFolder",),
        "CHANGE_ME",
        "Folder where your completed downloads are put into. Can be found in qBitTorrent -> Options -> Downloads -> Default Save Path (Please note, replace all '\\' with '/')",
        label="Completed Download Folder",
        required=True,
    ),
    ConfigField(
        ("FreeSpace",),
        "-1",
        "The desired amount of free space in the downloads directory [K=kilobytes, M=megabytes, G=gigabytes, T=terabytes] (set to -1 to disable, this bypasses AutoPauseResume)",
        label="Free Space",
        required=True,
    ),
    ConfigField(
        ("FreeSpaceFolder",),
        "CHANGE_ME",
        "Folder where the free space handler will check for free space (Please note, replace all '' with '/')",
        label="Free Space Folder",
    ),
    ConfigField(
        ("AutoPauseResume",),
        True,
        "Enable automation of pausing and resuming torrents as needed (Required enabled for the FreeSpace logic to function)",
        label="Auto Pause/Resume",
        kind="checkbox",
    ),
    ConfigField(
        ("NoInternetSleepTimer",),
        15,
        "Time to sleep for if there is no internet (in seconds: 600 = 10 Minutes)",
        label="No Internet Sleep",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("LoopSleepTimer",),
        5,
        "Time to sleep between reprocessing torrents (in seconds: 600 = 10 Minutes)",
        label="Loop Sleep",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("SearchLoopDelay",),
        -1,
        "Time to sleep between posting search commands (in seconds: 600 = 10 Minutes)",
        label="Search Loop Delay",
        kind="duration",
        native_unit="seconds",
        allow_negative=True,
    ),
    ConfigField(
        ("FailedCategory",),
        "failed",
        "Add torrents to this category to mark them as failed",
        label="Failed Category",
    ),
    ConfigField(
        ("RecheckCategory",),
        "recheck",
        "Add torrents to this category to trigger them to be rechecked properly",
        label="Recheck Category",
    ),
    ConfigField(
        ("Tagless",),
        False,
        "Tagless operation",
        label="Tagless",
        kind="checkbox",
    ),
    ConfigField(
        ("IgnoreTorrentsYoungerThan",),
        180,
        (
            "Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)",
            "Only applicable to Re-check and failed categories",
        ),
        label="Ignore Torrents Younger Than",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("PingURLS",),
        ["one.one.one.one", "dns.google.com"],
        (
            "URL to be pinged to check if you have a valid internet connection",
            "These will be pinged a **LOT** make sure the service is okay with you sending all the continuous pings.",
        ),
        label="Ping URLs",
        kind="tags",
        placeholder="one.one.one.one",
    ),
    ConfigField(
        ("FFprobeAutoUpdate",),
        True,
        _ffprobe_comments,
        label="FFprobe Auto Update",
        kind="checkbox",
    ),
    ConfigField(
        ("AutoUpdateEnabled",),
        False,
        (
            "Automatically attempt to update qBitrr on a schedule",
            "Set to true to enable the auto-update worker.",
        ),
        label="Auto Update Enabled",
        kind="checkbox",
    ),
    ConfigField(
        ("AutoUpdateCron",),
        "0 3 * * 0",
        (
            "Cron expression describing when to check for updates",
            "Default is weekly Sunday at 03:00 (0 3 * * 0).",
        ),
        label="Auto Update Cron",
        placeholder="0 3 * * 0",
        required=True,
    ),
    ConfigField(
        ("AutoRestartProcesses",),
        True,
        (
            "Automatically restart worker processes that fail or crash",
            "Set to false to disable auto-restart (processes will only log failures)",
        ),
        label="Auto-Restart Processes",
        kind="checkbox",
    ),
    ConfigField(
        ("MaxProcessRestarts",),
        5,
        (
            "Maximum number of restart attempts per process within the restart window",
            "Prevents infinite restart loops for processes that crash immediately",
        ),
        label="Max Process Restarts",
        kind="number",
        minimum=1,
    ),
    ConfigField(
        ("ProcessRestartWindow",),
        300,
        (
            "Time window (seconds) for tracking restart attempts",
            "If a process restarts MaxProcessRestarts times within this window, auto-restart is disabled for that process",
        ),
        label="Process Restart Window",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("ProcessRestartDelay",),
        5,
        "Delay (seconds) before attempting to restart a failed process",
        label="Process Restart Delay",
        kind="duration",
        native_unit="seconds",
    ),
)

# ---------------------------------------------------------------------------
# WebUI
# ---------------------------------------------------------------------------

WEBUI_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        ("Host",),
        "0.0.0.0",
        "WebUI listen host (default 0.0.0.0; use 127.0.0.1 for localhost-only)",
        label="WebUI Host",
        required=True,
    ),
    ConfigField(
        ("Port",),
        6969,
        "WebUI listen port (default 6969)",
        label="WebUI Port",
        kind="number",
        minimum=1,
        maximum=65535,
    ),
    ConfigField(
        ("Token",),
        "",
        (
            "Bearer token used when authentication is enabled; does not enable auth by itself.",
            "Available via /api/token and /web/token when authorized (including when AuthDisabled).",
            "Send as Authorization: Bearer <token> on API requests when auth is required.",
        ),
        label="WebUI Token",
        kind="password",
        secure=True,
    ),
    ConfigField(
        ("AuthDisabled",),
        False,
        (
            "When true, login is not required and the full admin API is open to anyone who can",
            "reach the WebUI port (including token retrieval, config writes, and self-update).",
            "New installs default to false (login required). Legacy configs missing this key",
            "still treat auth as disabled for backward compatibility.",
        ),
        label="Auth Disabled",
        kind="checkbox",
        description=(
            "Disable login requirement. Opens the full admin API when true "
            "(default false for new installs; missing key = disabled for legacy configs)."
        ),
    ),
    ConfigField(
        ("AllowInsecureExposure",),
        False,
        (
            "Required acknowledgment when AuthDisabled is true and Host is 0.0.0.0 or ::.",
            "Set to true only if you intentionally expose an unauthenticated admin WebUI",
            "(e.g. behind a reverse proxy that already authenticates clients).",
            "Legacy configs missing this key keep warn-only behavior; new installs default false.",
        ),
        label="Allow Insecure Exposure",
        kind="checkbox",
        description=(
            "Acknowledge AuthDisabled on a public bind (0.0.0.0/::). "
            "Required when both are set; missing key = warn-only for legacy configs."
        ),
    ),
    ConfigField(
        ("AllowInsecureTokenQuery",),
        False,
        (
            "Allow authentication via ?token= query parameter (insecure: leaks in logs/history).",
            "Prefer Authorization: Bearer. Legacy configs missing this key still accept query tokens.",
        ),
        label="Allow Insecure Token Query",
        kind="checkbox",
        description="Allow ?token= auth (insecure). Prefer Authorization: Bearer header.",
    ),
    ConfigField(
        ("BehindHttpsProxy",),
        False,
        (
            "Set to true when the WebUI is reached over HTTPS (e.g. behind a reverse proxy).",
            "When true, the app trusts X-Forwarded-Proto and sets the session cookie as Secure.",
            "Leave false for plain HTTP.",
        ),
        label="Behind HTTPS Proxy",
        kind="checkbox",
        description="Set when the WebUI is reached over HTTPS (e.g. reverse proxy). Enables Secure cookies.",
    ),
    ConfigField(
        ("UrlBase",),
        "",
        (
            "Public URL path prefix when served behind a reverse proxy (no trailing slash).",
            'Example: "/qbitrr" serves the UI at https://host/qbitrr/ui. Leave empty for site root.',
        ),
        label="Url Base",
        placeholder="/qbitrr",
        description="Public path prefix when behind a reverse proxy (e.g. /qbitrr). Leave empty for site root.",
    ),
    ConfigField(
        ("LocalAuthEnabled",),
        False,
        "Enable username/password login",
        label="Local Auth Enabled",
        kind="checkbox",
    ),
    ConfigField(
        ("OIDCEnabled",),
        False,
        "Enable OIDC login",
        label="OIDC Enabled",
        kind="checkbox",
    ),
    ConfigField(
        ("Username",),
        "",
        "Username for local auth",
        label="Username",
        description="Username for local auth login",
    ),
    ConfigField(
        ("PasswordHash",),
        "",
        "BCrypt password hash — set via the WebUI 'Set Password' button, never plain text",
        label="Password Hash",
        ui_expose=False,
    ),
    ConfigField(
        ("OIDC", "Authority"),
        "",
        "OIDC issuer/authority URL (e.g. https://auth.example.com/application/o/qbitrr)",
        label="OIDC Authority",
    ),
    ConfigField(
        ("OIDC", "ClientId"),
        "",
        "OAuth2 client ID",
        label="OIDC Client ID",
    ),
    ConfigField(
        ("OIDC", "ClientSecret"),
        "",
        "OAuth2 client secret",
        label="OIDC Client Secret",
        kind="password",
        secure=True,
    ),
    ConfigField(
        ("OIDC", "Scopes"),
        "openid profile",
        "Space-separated OIDC scopes",
        label="OIDC Scopes",
    ),
    ConfigField(
        ("OIDC", "CallbackPath"),
        "/signin-oidc",
        "OIDC callback path (must match IdP redirect URI)",
        label="OIDC Callback Path",
    ),
    ConfigField(
        ("OIDC", "RequireHttpsMetadata"),
        True,
        "Require HTTPS for IdP metadata (set false only for local dev OIDC)",
        label="OIDC Require HTTPS Metadata",
        kind="checkbox",
    ),
    ConfigField(
        ("LiveArr",),
        True,
        "Enable live updates for Arr catalogs and the qBittorrent overview",
        label="Live",
        kind="checkbox",
        ui_expose=False,
    ),
    ConfigField(
        ("Theme",),
        "Dark",
        "WebUI theme (Light or Dark)",
        label="Theme",
        kind="select",
        options=("Light", "Dark"),
        ui_expose=False,
    ),
    ConfigField(
        ("ViewDensity",),
        "Comfortable",
        "WebUI view density (Comfortable or Compact)",
        label="View Density",
        kind="select",
        options=("Comfortable", "Compact"),
        ui_expose=False,
    ),
)

# ---------------------------------------------------------------------------
# qBit (connection + CategorySeeding; Trackers AoT stays in sections.py)
# ---------------------------------------------------------------------------

QBIT_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        ("Disabled",),
        False,
        (
            "If this is enabled qBitrr can run in headless mode where it will only process searches.",
            "If media search is enabled in their individual categories",
            "This is useful if you use for example Sabnzbd/NZBGet for downloading content but still want the faster media searches provided by qbit",
        ),
        label="Disabled",
        kind="checkbox",
    ),
    ConfigField(
        ("Host",),
        "CHANGE_ME",
        'qbittorrent WebUI URL/IP - Can be found in Options > Web UI (called "IP Address")',
        label="Host",
    ),
    ConfigField(
        ("Port",),
        8080,
        'qbittorrent WebUI Port - Can be found in Options > Web UI (called "Port" on top right corner of the window)',
        label="Port",
        kind="number",
        minimum=1,
        maximum=65535,
    ),
    ConfigField(
        ("UserName",),
        "CHANGE_ME",
        "qbittorrent WebUI Authentication - Can be found in Options > Web UI > Authentication",
        label="UserName",
    ),
    ConfigField(
        ("Password",),
        "CHANGE_ME",
        'If you set "Bypass authentication on localhost or whitelisted IPs" remove this field.',
        label="Password",
        kind="password",
        secure=True,
    ),
    ConfigField(
        ("SkipTLSVerify",),
        False,
        (
            "If true, do not verify TLS certificates for HTTPS WebUI (self-signed certs). "
            "Disables MITM protection for that connection.",
        ),
        label="Skip TLS Verify",
        kind="checkbox",
    ),
    ConfigField(
        ("ManagedCategories",),
        [],
        (
            "Categories managed directly by this qBit instance (not managed by Arr instances).",
            "These categories will have seeding settings applied according to CategorySeeding configuration.",
            "Subcategory paths use '/' to match qBittorrent (for example 'seed/tleech').",
            "Example: ['downloads', 'private-tracker', 'long-term-seed']",
        ),
        label="Managed Categories",
        kind="tags",
    ),
    ConfigField(
        ("MatchSubcategories",),
        False,
        (
            "When true, configured categories ALSO match torrents in any subcategory beneath them.",
            "Example: setting MatchSubcategories=true with ManagedCategories=['seed'] manages",
            "torrents whose qBit category is 'seed', 'seed/tleech', 'seed/longterm', etc.",
            "When false (default) the qBit category string must match exactly.",
        ),
        label="Match Subcategories",
        kind="checkbox",
    ),
    ConfigField(
        ("CategorySeeding", "DownloadRateLimitPerTorrent"),
        -1,
        "Download rate limit per torrent in KB/s (-1 = disabled)",
        label="Download Rate Limit Per Torrent",
        kind="number",
        allow_negative=True,
    ),
    ConfigField(
        ("CategorySeeding", "UploadRateLimitPerTorrent"),
        -1,
        "Upload rate limit per torrent in KB/s (-1 = disabled)",
        label="Upload Rate Limit Per Torrent",
        kind="number",
        allow_negative=True,
    ),
    ConfigField(
        ("CategorySeeding", "MaxUploadRatio"),
        -1,
        "Maximum upload ratio (-1 = disabled, e.g. 2.0 for 200%)",
        label="Max Upload Ratio",
        kind="number",
        allow_negative=True,
    ),
    ConfigField(
        ("CategorySeeding", "MaxSeedingTime"),
        -1,
        "Maximum seeding time in seconds (-1 = disabled, e.g. 604800 for 7 days)",
        label="Max Seeding Time",
        kind="duration",
        native_unit="seconds",
        allow_negative=True,
    ),
    ConfigField(
        ("CategorySeeding", "RemoveTorrent"),
        -1,
        (
            "When to remove torrents from qBittorrent:",
            "  -1 = Never remove",
            "   1 = Remove when MaxUploadRatio is reached",
            "   2 = Remove when MaxSeedingTime is reached",
            "   3 = Remove when either condition is met (OR)",
            "   4 = Remove when both conditions are met (AND)",
        ),
        label="Remove Torrent",
        kind="select",
        options=("-1", "1", "2", "3", "4"),
    ),
    ConfigField(
        ("CategorySeeding", "HitAndRunMode"),
        "disabled",
        (
            "Hit and Run mode: and = require both ratio and time; or = either clears; disabled = no HnR.",
        ),
        label="Hit and Run Mode",
        kind="select",
        options=("disabled", "and", "or"),
    ),
    ConfigField(
        ("CategorySeeding", "MinSeedRatio"),
        1.0,
        "Minimum seed ratio before removal allowed (HnR protection)",
        label="Min Seed Ratio",
        kind="number",
    ),
    ConfigField(
        ("CategorySeeding", "MinSeedingTimeDays"),
        0,
        "Minimum seeding time in days before removal allowed (HnR protection, 0 = ratio only)",
        label="Min Seeding Time Days",
        kind="number",
    ),
    ConfigField(
        ("CategorySeeding", "HitAndRunMinimumDownloadPercent"),
        10,
        "Minimum download percentage before a torrent is considered for HnR (0-100, default 10)",
        label="Hit and Run Minimum Download Percent",
        kind="number",
        minimum=0,
        maximum=100,
    ),
    ConfigField(
        ("CategorySeeding", "HitAndRunPartialSeedRatio"),
        1.0,
        "Minimum ratio for partial downloads (>=HitAndRunMinimumDownloadPercent% but <100% complete)",
        label="Hit and Run Partial Seed Ratio",
        kind="number",
    ),
    ConfigField(
        ("CategorySeeding", "TrackerUpdateBuffer"),
        0,
        "Extra seconds buffer for tracker stats lag (0 = disabled)",
        label="Tracker Update Buffer",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("CategorySeeding", "StalledDelay"),
        -1,
        "Maximum time stalled downloads can sit before removal, in minutes (-1 = disabled, 0 = infinite).",
        label="Stalled Delay",
        kind="duration",
        native_unit="minutes",
        allow_negative=True,
    ),
    ConfigField(
        ("CategorySeeding", "IgnoreTorrentsYoungerThan"),
        180,
        "Ignore torrents younger than this (seconds). Stalled removal also requires last_activity older than this.",
        label="Ignore Torrents Younger Than",
        kind="duration",
        native_unit="seconds",
    ),
)

__all__ = [
    "ConfigField",
    "QBIT_FIELDS",
    "SETTINGS_FIELDS",
    "WEBUI_FIELDS",
    "apply_fields",
    "build_config_schema",
    "enrich_reload_metadata",
    "filter_arr_fields",
    "iter_inventory_paths",
]
