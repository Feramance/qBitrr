"""Arr factory helpers: section name → concrete ArrBase subclass."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from qBitrr.arr_client import (
    Lidarr,
    Radarr,
    Sonarr,
    build_lidarr_client,
    build_radarr_client,
    build_sonarr_client,
)
from qBitrr.arss.base import ArrBase
from qBitrr.arss.lidarr import LidarrArr
from qBitrr.arss.radarr import RadarrArr
from qBitrr.arss.sonarr import SonarrArr

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager

_ARR_SECTION_RE = re.compile(r"^(rad|son|anim|lid)arr", re.IGNORECASE)


def arr_class_for_section(section_name: str) -> type[ArrBase]:
    """Return the concrete Arr class for a config section name."""
    match = _ARR_SECTION_RE.match(section_name)
    if not match:
        raise ValueError(f"Unknown Arr section: {section_name}")
    prefix = match.group(1).lower()
    if prefix in ("son", "anim"):
        return SonarrArr
    if prefix == "rad":
        return RadarrArr
    if prefix == "lid":
        return LidarrArr
    raise ValueError(f"Unknown Arr section prefix: {prefix}")


def client_builder_for_section(
    section_name: str,
) -> Callable[..., Radarr | Sonarr | Lidarr]:
    """Return the pyarr client builder for a config section name."""
    match = _ARR_SECTION_RE.match(section_name)
    if not match:
        raise ValueError(f"Unknown Arr section: {section_name}")
    prefix = match.group(1).lower()
    if prefix in ("son", "anim"):
        return build_sonarr_client
    if prefix == "rad":
        return build_radarr_client
    if prefix == "lid":
        return build_lidarr_client
    raise ValueError(f"Unknown Arr section prefix: {prefix}")


def build_arr_instance(section_name: str, manager: ArrManager) -> ArrBase:
    """Instantiate the correct Arr subclass for ``section_name``."""
    cls = arr_class_for_section(section_name)
    builder = client_builder_for_section(section_name)
    return cls(section_name, manager, client_builder=builder)
