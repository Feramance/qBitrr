"""Shared tracker config → derived sets/dicts for Arr and qBit-managed workers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse


def extract_tracker_host(uri: str) -> str:
    """Extract the hostname from a tracker URI for matching purposes.

    Handles bare domains (``tracker.example.org``), full announce URLs
    (``https://tracker.example.org/a/key/announce``), and scheme-less paths
    (``tracker.example.org/announce``).  Returns the lowercased hostname so
    that a config URI ``tracker.example.org`` will match the qBit announce
    URL ``https://tracker.example.org/a/passkey/announce``.
    """
    uri = uri.strip().rstrip("/")
    if not uri:
        return ""
    if "://" not in uri:
        uri = "https://" + uri
    try:
        parsed = urlparse(uri)
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


@dataclass(frozen=True)
class TrackerIndex:
    """Derived structures from ``monitored_trackers`` (qBit + Arr merged list)."""

    remove_trackers_if_exists: frozenset[str]
    monitored_tracker_urls: frozenset[str]
    add_trackers_if_missing: frozenset[str]
    host_to_config_uri: dict[str, str]
    remove_tracker_hosts: frozenset[str]
    normalized_bad_tracker_msgs: frozenset[str]


def build_tracker_index(
    monitored_trackers: list,
    *,
    bad_tracker_messages: Iterable[str] | None = None,
) -> TrackerIndex:
    """Build host-based lookup and normalized sets from merged tracker config rows."""
    remove_if_exists: set[str] = {
        uri
        for i in monitored_trackers
        if i.get("RemoveIfExists") is True and (uri := (i.get("URI") or "").strip().rstrip("/"))
    }
    monitored_urls: set[str] = {
        uri
        for i in monitored_trackers
        if (uri := (i.get("URI") or "").strip().rstrip("/")) and uri not in remove_if_exists
    }
    add_if_missing: set[str] = {
        uri
        for i in monitored_trackers
        if i.get("AddTrackerIfMissing") is True
        and (uri := (i.get("URI") or "").strip().rstrip("/"))
    }
    host_to_config_uri: dict[str, str] = {}
    for _uri in monitored_urls:
        _host = extract_tracker_host(_uri)
        if _host:
            host_to_config_uri[_host] = _uri
    remove_hosts: set[str] = {h for u in remove_if_exists if (h := extract_tracker_host(u))}
    bad_iter = bad_tracker_messages if bad_tracker_messages is not None else ()
    normalized_bad: set[str] = {msg.lower() for msg in bad_iter if isinstance(msg, str)}
    return TrackerIndex(
        remove_trackers_if_exists=frozenset(remove_if_exists),
        monitored_tracker_urls=frozenset(monitored_urls),
        add_trackers_if_missing=frozenset(add_if_missing),
        host_to_config_uri=dict(host_to_config_uri),
        remove_tracker_hosts=frozenset(remove_hosts),
        normalized_bad_tracker_msgs=frozenset(normalized_bad),
    )
