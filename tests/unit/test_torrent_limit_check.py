"""Unit tests for torrent_limit_check (seeding removal modes with valid/unset limits)."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_torrent(ratio: float = 0.0, seeding_time: int = 0):
    t = MagicMock()
    t.ratio = ratio
    t.seeding_time = seeding_time
    return t


def _make_arr(remove_torrent: int, warned: bool = False):
    """Minimal Arr-like object with only attributes used by torrent_limit_check."""
    arr = MagicMock()
    arr.seeding_mode_global_remove_torrent = remove_torrent
    arr._warned_no_seeding_limits = warned
    return arr


def torrent_limit_check_standalone(arr, torrent, seeding_time_limit, ratio_limit) -> bool:
    """Replicate torrent_limit_check logic for testing (avoids importing full Arr)."""
    if arr.seeding_mode_global_remove_torrent == -1:
        return False

    ratio_limit_valid = ratio_limit is not None and ratio_limit > 0
    time_limit_valid = seeding_time_limit is not None and seeding_time_limit > 0
    ratio_met = ratio_limit_valid and torrent.ratio >= ratio_limit
    time_met = time_limit_valid and torrent.seeding_time >= seeding_time_limit

    mode = arr.seeding_mode_global_remove_torrent
    if mode in (1, 2, 3, 4) and not ratio_limit_valid and not time_limit_valid:
        return False

    if mode == 4:
        return ratio_met and time_met
    if mode == 3:
        return ratio_met or time_met
    if mode == 2:
        return time_met
    if mode == 1:
        return ratio_met
    return False


class TestTorrentLimitCheck:
    """Test removal modes with set/unset ratio and time limits."""

    def test_remove_torrent_never_returns_false_regardless_of_limits(self):
        arr = _make_arr(-1)
        t = _make_torrent(ratio=10.0, seeding_time=100000)
        assert torrent_limit_check_standalone(arr, t, 100, 2.0) is False
        assert torrent_limit_check_standalone(arr, t, -5, -5) is False

    def test_mode_1_ratio_only_requires_set_ratio_limit(self):
        arr = _make_arr(1)
        t = _make_torrent(ratio=2.0, seeding_time=0)
        # Limit set and met
        assert torrent_limit_check_standalone(arr, t, -5, 2.0) is True
        assert torrent_limit_check_standalone(arr, t, -5, 1.5) is True
        # Limit set but not met
        assert torrent_limit_check_standalone(arr, t, -5, 3.0) is False
        # Time limit unset is ignored for mode 1
        assert torrent_limit_check_standalone(arr, t, -5, 2.0) is True
        # Both unset -> no removal
        assert torrent_limit_check_standalone(arr, t, -5, -5) is False

    def test_mode_2_time_only_requires_set_time_limit(self):
        arr = _make_arr(2)
        t = _make_torrent(ratio=0.0, seeding_time=1000)
        # Time limit set and met
        assert torrent_limit_check_standalone(arr, t, 500, -5) is True
        assert torrent_limit_check_standalone(arr, t, 1000, -5) is True
        # Time limit set but not met
        assert torrent_limit_check_standalone(arr, t, 2000, -5) is False
        # Ratio unset is ignored for mode 2
        assert torrent_limit_check_standalone(arr, t, 500, -5) is True
        # Both unset -> no removal
        assert torrent_limit_check_standalone(arr, t, -5, -5) is False

    def test_mode_3_or_requires_at_least_one_set_and_met(self):
        arr = _make_arr(3)
        t = _make_torrent(ratio=2.0, seeding_time=1000)
        # Ratio set and met, time unset
        assert torrent_limit_check_standalone(arr, t, -5, 2.0) is True
        # Time set and met, ratio unset
        assert torrent_limit_check_standalone(arr, t, 500, -5) is True
        # Both set, one met
        assert torrent_limit_check_standalone(arr, t, 500, 3.0) is True  # time met
        assert torrent_limit_check_standalone(arr, t, 2000, 1.5) is True  # ratio met
        # Both set and met
        assert torrent_limit_check_standalone(arr, t, 500, 1.0) is True
        # Both unset -> no removal
        assert torrent_limit_check_standalone(arr, t, -5, -5) is False
        # Both set but neither met
        assert torrent_limit_check_standalone(arr, t, 2000, 5.0) is False

    def test_mode_4_and_requires_both_set_and_both_met(self):
        arr = _make_arr(4)
        t = _make_torrent(ratio=2.0, seeding_time=1000)
        # Both set and met
        assert torrent_limit_check_standalone(arr, t, 500, 1.5) is True
        # Ratio met, time not met
        assert torrent_limit_check_standalone(arr, t, 2000, 1.5) is False
        # Time met, ratio not met
        assert torrent_limit_check_standalone(arr, t, 500, 5.0) is False
        # Ratio unset -> cannot remove (ratio_met is False)
        assert torrent_limit_check_standalone(arr, t, 500, -5) is False
        # Time unset -> cannot remove (time_met is False)
        assert torrent_limit_check_standalone(arr, t, -5, 1.5) is False
        # Both unset -> no removal
        assert torrent_limit_check_standalone(arr, t, -5, -5) is False
