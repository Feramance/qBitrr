"""Combination coverage for arr_tracker_index helpers."""

from __future__ import annotations

import unittest

from qBitrr.arr_tracker_index import (
    build_tracker_index,
    extract_tracker_host,
    merge_tracker_configs,
)


class TestExtractTrackerHostCombinations(unittest.TestCase):
    def test_host_extraction_matrix(self) -> None:
        cases = [
            ("", ""),
            ("tracker.example.org", "tracker.example.org"),
            ("https://tracker.example.org/a/key/announce", "tracker.example.org"),
            ("tracker.example.org/announce", "tracker.example.org"),
            ("  HTTPS://Tracker.Example.ORG/  ", "tracker.example.org"),
        ]
        for uri, expected in cases:
            with self.subTest(uri=uri):
                self.assertEqual(extract_tracker_host(uri), expected)


class TestMergeTrackerConfigsCombinations(unittest.TestCase):
    def test_arr_overwrites_qbit_for_same_uri(self) -> None:
        qbit = [{"URI": "https://a/announce", "AddTrackerIfMissing": False}]
        arr = [{"URI": "https://a/announce", "AddTrackerIfMissing": True}]
        merged = merge_tracker_configs(qbit, arr)
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["AddTrackerIfMissing"])

    def test_preserves_distinct_uris_in_order(self) -> None:
        qbit = [{"URI": "https://first/announce"}]
        arr = [{"URI": "https://second/announce"}]
        merged = merge_tracker_configs(qbit, arr)
        uris = [row["URI"] for row in merged]
        self.assertEqual(uris, ["https://first/announce", "https://second/announce"])

    def test_skips_invalid_rows(self) -> None:
        merged = merge_tracker_configs(
            [{"URI": ""}, {"NoURI": True}, "bad"],
            [{"URI": "https://valid/announce"}],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["URI"], "https://valid/announce")


class TestBuildTrackerIndexCombinations(unittest.TestCase):
    def test_remove_if_exists_excludes_from_monitored_and_add(self) -> None:
        trackers = [
            {"URI": "https://remove/announce", "RemoveIfExists": True},
            {"URI": "https://keep/announce", "AddTrackerIfMissing": True},
        ]
        index = build_tracker_index(trackers)
        self.assertIn("https://remove/announce", index.remove_trackers_if_exists)
        self.assertNotIn("https://remove/announce", index.monitored_tracker_urls)
        self.assertNotIn("https://remove/announce", index.add_trackers_if_missing)
        self.assertIn("https://keep/announce", index.add_trackers_if_missing)

    def test_host_mapping_uses_first_seen_config_order(self) -> None:
        trackers = [
            {"URI": "https://tracker.example.org/announce"},
            {"URI": "https://tracker.example.org/alt/announce"},
        ]
        index = build_tracker_index(trackers)
        host_map = dict(index.host_to_config_uri)
        self.assertEqual(host_map["tracker.example.org"], "https://tracker.example.org/announce")

    def test_bad_tracker_messages_normalized_lowercase(self) -> None:
        index = build_tracker_index([], bad_tracker_messages=["Unregistered", "RATIO HIT"])
        self.assertEqual(
            index.normalized_bad_tracker_msgs, frozenset({"unregistered", "ratio hit"})
        )

    def test_remove_hosts_derived_from_remove_uris(self) -> None:
        trackers = [{"URI": "https://dead.tracker/announce", "RemoveIfExists": True}]
        index = build_tracker_index(trackers)
        self.assertIn("dead.tracker", index.remove_tracker_hosts)


if __name__ == "__main__":
    unittest.main()
