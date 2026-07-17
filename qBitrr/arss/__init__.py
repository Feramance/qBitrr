"""Arr worker package (split from legacy arss.py)."""

from qBitrr.arss.arr import Arr
from qBitrr.arss.base import ArrBase
from qBitrr.arss.factory import arr_class_for_section, build_arr_instance
from qBitrr.arss.lidarr import LidarrArr
from qBitrr.arss.manager import ArrManager
from qBitrr.arss.placeholder import PlaceHolderArr
from qBitrr.arss.radarr import RadarrArr
from qBitrr.arss.sonarr import SonarrArr
from qBitrr.arss.torrent_policy import TorrentPolicyManager

__all__ = [
    "Arr",
    "ArrBase",
    "ArrManager",
    "LidarrArr",
    "PlaceHolderArr",
    "RadarrArr",
    "SonarrArr",
    "TorrentPolicyManager",
    "arr_class_for_section",
    "build_arr_instance",
]
