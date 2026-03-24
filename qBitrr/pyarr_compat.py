from __future__ import annotations

"""Compatibility imports for pyarr client class naming changes.

Recent pyarr versions expose client classes as ``Radarr``, ``Sonarr``, and
``Lidarr`` instead of ``RadarrAPI``, ``SonarrAPI``, and ``LidarrAPI``.
qBitrr historically used the ``*API`` names. This module normalizes imports so
the rest of the code can keep using ``RadarrAPI``/``SonarrAPI``/``LidarrAPI``.
"""

try:
    # Legacy pyarr naming (<= v5.x style)
    from pyarr import LidarrAPI, RadarrAPI, SonarrAPI
except ImportError:
    # Newer pyarr naming (v6+ style)
    from pyarr import Lidarr as LidarrAPI
    from pyarr import Radarr as RadarrAPI
    from pyarr import Sonarr as SonarrAPI

__all__ = ["RadarrAPI", "SonarrAPI", "LidarrAPI"]
