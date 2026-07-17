from __future__ import annotations

import logging
import pathlib
import re
from typing import TYPE_CHECKING

from qBitrr.arss._shared import (
    CONFIG,
    QBIT_DISABLED,
    SEARCH_ONLY,
    SkipException,
    find_overlap_conflicts,
    get_auto_pause_resume_effective,
    get_effective_qbit_disabled,
    get_failed_category_effective,
    get_free_space_guard_settings,
    get_recheck_category_effective,
    has_subcategory_separator,
    matches_configured,
    normalize_category,
    qbit_sections,
    run_logs,
)
from qBitrr.arss.base import ArrBase
from qBitrr.arss.factory import build_arr_instance
from qBitrr.arss.placeholder import PlaceHolderArr
from qBitrr.arss.torrent_policy import TorrentPolicyManager

if TYPE_CHECKING:
    from qBitrr.main import qBitManager


class ArrManager:
    def __init__(self, qbitmanager: qBitManager):
        self.groups: set[str] = set()
        self.uris: set[str] = set()
        self.special_categories: set[str] = {
            get_failed_category_effective(),
            get_recheck_category_effective(),
        }
        self.arr_categories: set[str] = set()
        self.qbit_managed_categories: set[str] = set()
        self.qbit_managed_category_sections: dict[str, str] = {}
        self.policy_manager_tracker_sync_owner: bool = False
        self.policy_manager_tracker_sync_categories: set[str] = set()
        self.category_allowlist: set[str] = self.special_categories.copy()
        self.completed_folders: set[pathlib.Path] = set()
        self.managed_objects: dict[str, ArrBase] = {}
        # Prefix dispatch: all Arr + qBit-managed category keys used as roots for
        # :meth:`matches_configured` when instance-level ``MatchSubcategories`` /
        # per-Arr overrides allow prefix matching (see ``_prefix_match_allowed_for_owner``).
        self.subcategory_prefix_owners: set[str] = set()
        # True when any ``[qBit*]`` **or** explicit ``[Radarr-*].MatchSubcategories = true``
        # (etc.) is active — used only for startup overlap / info logs.
        self.subcategory_match_enabled: bool = False
        self.qbit_manager: qBitManager = qbitmanager
        self.ffprobe_available: bool = self.qbit_manager.ffprobe_downloader.probe_path.exists()
        self.logger = logging.getLogger("qBitrr.ArrManager")
        run_logs(self.logger)
        if not self.ffprobe_available and not (QBIT_DISABLED or SEARCH_ONLY):
            self.logger.error(
                "'%s' was not found, disabling all functionality dependant on it",
                self.qbit_manager.ffprobe_downloader.probe_path,
            )

    @staticmethod
    def any_arr_match_subcategories_explicit_true() -> bool:
        """True when some Arr section explicitly enables MatchSubcategories (truthy), not inherit."""
        for key in CONFIG.sections():
            if re.match(r"(rad|son|anim|lid)arr", key, re.IGNORECASE):
                raw = CONFIG.get(f"{key}.MatchSubcategories", fallback=None)
                if raw is not None and bool(raw):
                    return True
        return False

    def arr_match_subcategories_effective(self, arr_name: str, qbit_section: str) -> bool:
        """Whether prefix/subcategory matching applies to ``arr_name`` on ``qbit_section``.

        Mirrors :meth:`Arr._get_torrents_from_all_instances`: a per-Arr
        ``[<Arr>].MatchSubcategories`` value wins when present; otherwise the
        ``[qBit*]`` flag for ``qbit_section`` is used.
        """
        arr_override = CONFIG.get(f"{arr_name}.MatchSubcategories", fallback=None)
        if arr_override is not None:
            return bool(arr_override)
        return bool(CONFIG.get(f"{qbit_section}.MatchSubcategories", fallback=False))

    def qbit_section_needs_full_torrent_list_for_policy_manager(self, qbit_section: str) -> bool:
        """True when TorrentPolicyManager must omit ``category=`` for this qBit client.

        Uses the same per-instance rules as Arr torrent scans: full list only if
        prefix matching is active here (any managed Arr via
        :meth:`arr_match_subcategories_effective`, or ``ManagedCategories`` under
        this section with ``[qBit*].MatchSubcategories``). Avoids pulling every
        torrent from instances that only use exact ``category=`` filters.
        """
        qbit_flag = bool(CONFIG.get(f"{qbit_section}.MatchSubcategories", fallback=False))
        if qbit_flag and any(
            self.qbit_managed_category_sections.get(cat) == qbit_section
            for cat in self.qbit_managed_categories
        ):
            return True
        return any(
            self.arr_match_subcategories_effective(name, qbit_section) for name in self.groups
        )

    def _prefix_match_allowed_for_owner(self, owner_key: str, *, qbit_section: str | None) -> bool:
        """Whether prefix / descendant matching may claim ``owner_key`` for this qBit instance."""
        obj = self.managed_objects.get(owner_key)
        if obj is None or owner_key == "TorrentPolicyManager":
            return False
        if getattr(obj, "type", None) == "placeholder":
            if qbit_section:
                return bool(CONFIG.get(f"{qbit_section}.MatchSubcategories", fallback=False))
            return any(
                CONFIG.get(f"{s}.MatchSubcategories", fallback=False)
                for s in CONFIG.sections()
                if s == "qBit" or s.startswith("qBit-")
            )
        arr_name = getattr(obj, "_name", None)
        if not arr_name:
            return False
        arr_ov = CONFIG.get(f"{arr_name}.MatchSubcategories", fallback=None)
        if arr_ov is not None:
            return bool(arr_ov)
        if qbit_section:
            return bool(CONFIG.get(f"{qbit_section}.MatchSubcategories", fallback=False))
        return any(
            CONFIG.get(f"{s}.MatchSubcategories", fallback=False)
            for s in CONFIG.sections()
            if s == "qBit" or s.startswith("qBit-")
        )

    def resolve_owning_category(
        self,
        torrent_category: str | None,
        *,
        qbit_section: str | None = None,
    ) -> str | None:
        """Return the ``managed_objects`` key that owns ``torrent_category`` (or None).

        Exact match wins first. Otherwise, when prefix matching is allowed for a
        configured root category on this qBit instance (``MatchSubcategories`` on
        ``[qBit*]`` and/or per-Arr overrides), the **longest** configured prefix
        wins — see :mod:`qBitrr.category_paths`.
        """
        if not torrent_category:
            return None
        norm = normalize_category(torrent_category)
        if not norm:
            return None
        if norm in self.managed_objects:
            return norm
        if not self.subcategory_prefix_owners:
            self.logger.trace(
                "No prefix owners registered; category %r (norm=%r) has no owner",
                torrent_category,
                norm,
            )
            return None
        eligible = [
            k
            for k in self.subcategory_prefix_owners
            if self._prefix_match_allowed_for_owner(k, qbit_section=qbit_section)
        ]
        if not eligible:
            self.logger.trace(
                "Category %r (norm=%r, qbit_section=%r) matched no eligible prefix owners",
                torrent_category,
                norm,
                qbit_section,
            )
            return None
        match = matches_configured(norm, eligible, prefix=True)
        resolved = match if match in self.managed_objects else None
        if resolved is None:
            self.logger.trace(
                "No owning managed_objects entry for torrent category %r "
                "(norm=%r, qbit_section=%r, eligible=%s)",
                torrent_category,
                norm,
                qbit_section,
                sorted(eligible),
            )
        return resolved

    def category_is_monitored(
        self, torrent_category: str | None, *, qbit_section: str | None = None
    ) -> bool:
        """True when ``torrent_category`` is owned (exact or prefix when enabled)."""
        return (
            self.resolve_owning_category(torrent_category, qbit_section=qbit_section) is not None
        )

    def _normalise_managed_categories(self, raw: list, *, source: str) -> list[str]:
        """Normalise a ``ManagedCategories`` list and warn about backslashes/empties."""
        out: list[str] = []
        for value in raw or []:
            if isinstance(value, str) and "\\" in value:
                self.logger.warning(
                    "Category '%s' from %s contains backslashes; qBittorrent uses '/' "
                    "as the subcategory separator. Treating segments around backslashes "
                    "literally — please update the config.",
                    value,
                    source,
                )
            normalised = normalize_category(value)
            if not normalised:
                if value not in (None, "", []):
                    self.logger.warning(
                        "Skipping empty/whitespace ManagedCategories entry from %s: %r",
                        source,
                        value,
                    )
                continue
            if normalised != str(value).strip():
                self.logger.info(
                    "Normalised ManagedCategories entry %r → %r (from %s)",
                    str(value),
                    normalised,
                    source,
                )
            if normalised not in out:
                out.append(normalised)
        return out

    def _validate_category_assignments(self):
        """
        Validate that no category is managed by both Arr and qBit instances.

        Collects all qBit-managed categories from all qBit instances and checks
        for conflicts with Arr-managed categories. Allows same category on
        multiple qBit instances (acceptable).

        Subcategory paths (``parent/child``) are normalised in place and we warn
        when configured prefixes overlap across different owners (for example
        ``seed`` for one Arr while ``seed/tleech`` is also configured elsewhere)
        because qBittorrent's ``torrents/info`` filter is exact-match — see
        :mod:`qBitrr.category_paths` and ``docs/configuration/qbittorrent.md``.

        Raises:
            ValueError: If any category is managed by both Arr and qBit
        """
        # MatchSubcategories logging / ManagedCategories '/' hint: true when any qBit
        # instance opts in OR some Arr sets ``MatchSubcategories = true`` explicitly.
        self.subcategory_match_enabled = False
        for section in qbit_sections(CONFIG):
            if bool(CONFIG.get(f"{section}.MatchSubcategories", fallback=False)):
                self.subcategory_match_enabled = True
                break
        if not self.subcategory_match_enabled:
            self.subcategory_match_enabled = self.any_arr_match_subcategories_explicit_true()

        # Collect qBit-managed categories from all instances
        self.qbit_managed_categories.clear()
        self.qbit_managed_category_sections.clear()
        self.subcategory_prefix_owners.clear()
        for section in qbit_sections(CONFIG):
            instance_label = "default" if section == "qBit" else section.replace("qBit-", "", 1)
            raw_cats = CONFIG.get(f"{section}.ManagedCategories", fallback=[])
            managed_cats = self._normalise_managed_categories(raw_cats, source=section)
            if managed_cats:
                self.qbit_managed_categories.update(managed_cats)
                for category in managed_cats:
                    owner = self.qbit_managed_category_sections.setdefault(category, section)
                    if owner != section:
                        self.logger.warning(
                            "Category '%s' is managed by both '%s' and '%s'; "
                            "PlaceHolderArr will use '%s' seeding config",
                            category,
                            owner,
                            section,
                            owner,
                        )
                self.logger.debug(
                    "qBit instance '%s' manages categories: %s",
                    instance_label,
                    ", ".join(managed_cats),
                )

        # Check for conflicts between Arr and qBit categories
        conflicts = self.arr_categories & self.qbit_managed_categories
        if conflicts:
            conflict_list = ", ".join(sorted(conflicts))
            error_msg = (
                f"Category conflict detected: {conflict_list} "
                f"cannot be managed by both Arr instances and qBit instances. "
                f"Please assign each category to either Arr OR qBit management, not both."
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # Subcategory overlap detection (Arr ↔ qBit and Arr ↔ Arr / qBit ↔ qBit)
        all_owned = self.arr_categories | self.qbit_managed_categories
        overlaps = find_overlap_conflicts(all_owned)
        if overlaps:
            for parent, child in overlaps:
                self.logger.warning(
                    "Configured category overlap: '%s' is a subcategory of '%s'. "
                    "The qBittorrent API lists torrents by exact category string only; "
                    "with MatchSubcategories off, a torrent in '%s' is not picked up by "
                    "a '%s' owner. Enable MatchSubcategories (where appropriate) or use "
                    "the full path as the configured category.",
                    child,
                    parent,
                    child,
                    parent,
                )

        # Warn about subcategory paths configured without MatchSubcategories enabled —
        # these only behave correctly when the configured value is the exact qBit string.
        if not self.subcategory_match_enabled:
            for cat in sorted(self.qbit_managed_categories):
                if has_subcategory_separator(cat):
                    self.logger.info(
                        "qBit-managed category '%s' contains '/'. "
                        "Exact-match mode is in effect (MatchSubcategories disabled); "
                        "qBitrr will manage only torrents whose qBit category is exactly '%s'.",
                        cat,
                        cat,
                    )

        # Update category allowlist to include qBit-managed categories
        self.category_allowlist.update(self.qbit_managed_categories)

        # Prefix roots for :meth:`resolve_owning_category` (exact match still wins first).
        self.subcategory_prefix_owners.update(self.arr_categories)
        self.subcategory_prefix_owners.update(self.qbit_managed_categories)
        if self.subcategory_prefix_owners:
            self.logger.debug(
                "Category prefix roots for subcategory dispatch: %s",
                ", ".join(sorted(self.subcategory_prefix_owners)),
            )

        if self.qbit_managed_categories:
            self.logger.info(
                "qBit-managed categories registered: %s",
                ", ".join(sorted(self.qbit_managed_categories)),
            )
        self.logger.debug("Category validation passed - no conflicts detected")

    def policy_manager_owns_tracker_sync_for_category(
        self,
        category: str | None,
        *,
        qbit_section: str | None = None,
    ) -> bool:
        """Return True when TorrentPolicyManager owns tracker/tag sync for ``category``."""
        if not category or not self.policy_manager_tracker_sync_owner:
            return False
        owner = self.resolve_owning_category(category, qbit_section=qbit_section)
        return owner is not None and owner in self.policy_manager_tracker_sync_categories

    def build_arr_instances(self):
        self.policy_manager_tracker_sync_owner = False
        self.policy_manager_tracker_sync_categories.clear()
        for key in CONFIG.sections():
            if search := re.match("(rad|son|anim|lid)arr.*", key, re.IGNORECASE):
                name = search.group(0)
                try:
                    managed_object = build_arr_instance(name, self)
                    self.groups.add(name)
                    self.uris.add(managed_object.uri)
                    self.managed_objects[managed_object.category] = managed_object
                    self.arr_categories.add(managed_object.category)
                except ValueError as e:
                    self.logger.exception("Value Error: %s", e)
                except SkipException:
                    continue
                except (OSError, TypeError) as e:
                    self.logger.exception(e)

        # Validate category assignments after all Arr instances are initialized
        self._validate_category_assignments()

        # Global torrent policy worker monitors both Arr-managed and qBit-managed categories
        all_monitored_categories = self.arr_categories | self.qbit_managed_categories
        configured_qbit_sections = qbit_sections(CONFIG)
        has_configured_qbit_instance = len(configured_qbit_sections) > 0
        _fs_guard, _ = get_free_space_guard_settings()
        fs_enabled = (
            _fs_guard != "-1"
            and get_auto_pause_resume_effective()
            and not get_effective_qbit_disabled()
        )
        sort_enabled = ArrBase.global_sort_torrents_enabled() and not get_effective_qbit_disabled()
        should_start_torrent_policy_manager = bool(
            all_monitored_categories and has_configured_qbit_instance
        )
        if should_start_torrent_policy_manager:
            self.managed_objects["TorrentPolicyManager"] = TorrentPolicyManager(
                all_monitored_categories,
                self,
                enable_tracker_sort=sort_enabled,
                enable_free_space=fs_enabled,
            )
            self.logger.info(
                "Starting TorrentPolicyManager (categories=%d, configured_qbit_instances=%d, "
                "tracker_sort=%s, free_space=%s)",
                len(all_monitored_categories),
                len(configured_qbit_sections),
                sort_enabled,
                fs_enabled,
            )
            if sort_enabled:
                self.policy_manager_tracker_sync_owner = True
                self.policy_manager_tracker_sync_categories = set(all_monitored_categories)
                self.logger.debug(
                    "Tracker/tag sync owner set to TorrentPolicyManager for %d categories",
                    len(self.policy_manager_tracker_sync_categories),
                )
        else:
            self.logger.debug(
                "Skipping TorrentPolicyManager startup (categories=%d, configured_qbit_instances=%d)",
                len(all_monitored_categories),
                len(configured_qbit_sections),
            )
        for cat in self.special_categories:
            managed_object = PlaceHolderArr(cat, self)
            self.managed_objects[cat] = managed_object
        # qBit-managed categories get the same torrent behaviour (recheck, missing files,
        # stalled, etc.) via PlaceHolderArr when not already an Arr category.
        for cat in self.qbit_managed_categories:
            if cat not in self.managed_objects:
                managed_object = PlaceHolderArr(cat, self)
                self.managed_objects[cat] = managed_object
        return self
