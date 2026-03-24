from __future__ import annotations

"""Compatibility imports for pyarr client class naming changes.

Recent pyarr versions expose client classes as ``Radarr``, ``Sonarr``, and
``Lidarr`` instead of ``RadarrAPI``, ``SonarrAPI``, and ``LidarrAPI``.
qBitrr historically used the ``*API`` names. This module normalizes imports so
the rest of the code can keep using ``RadarrAPI``/``SonarrAPI``/``LidarrAPI``.
"""

try:
    pass
except ImportError:
    pass
