"""Compatibility shim: prefer ArrBase / RadarrArr / SonarrArr / LidarrArr."""

from qBitrr.arss.base import ArrBase

# Short alias for tests and call sites that still import ``Arr``.
Arr = ArrBase

__all__ = ["Arr", "ArrBase"]
