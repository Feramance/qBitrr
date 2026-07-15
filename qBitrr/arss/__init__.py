"""Arr worker package (split from legacy arss.py)."""

from qBitrr.arr_client import execute_command
from qBitrr.arss._shared import (
    AUTO_PAUSE_RESUME,
    _collect_instance_hash_map_hashes,
    _prune_instance_hash_map,
)
from qBitrr.arss.arr import Arr
from qBitrr.arss.manager import ArrManager
from qBitrr.arss.placeholder import PlaceHolderArr
from qBitrr.arss.torrent_policy import TorrentPolicyManager
from qBitrr.utils import with_retry

__all__ = [
    "Arr",
    "ArrManager",
    "AUTO_PAUSE_RESUME",
    "PlaceHolderArr",
    "TorrentPolicyManager",
    "_collect_instance_hash_map_hashes",
    "_prune_instance_hash_map",
    "execute_command",
    "with_retry",
]
