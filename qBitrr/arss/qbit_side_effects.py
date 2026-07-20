"""Shared qBit pause/resume/delete side-effect helpers for Arr workers."""

from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from qBitrr.arss.arr_shared import (
    _QBIT_TORRENT_DELETE_EXCEPTIONS,
    _QBIT_WRITE_RETRY_EXCEPTIONS,
    get_auto_pause_resume_effective,
    with_retry,
)


def _mutate_hashes_by_instance(
    worker: Any,
    bucket_attr: str,
    api_method: str,
    *,
    action_verb: str,
    warn_missing_client: bool = True,
    log_names: bool = False,
    after_success: Callable[[Any, str, Iterable[str]], None] | None = None,
    add_to_timed_ignore: bool = False,
) -> None:
    """Pause or resume ``worker.<bucket_attr>`` hashes on their owning qBit clients."""
    bucket = getattr(worker, bucket_attr)
    if not bucket or not get_auto_pause_resume_effective():
        return
    worker.needs_cleanup = True
    still_pending: defaultdict[str, set[str]] = defaultdict(set)
    qbit_manager = worker.manager.qbit_manager
    for instance_name, hashes in bucket.items():
        if not hashes:
            continue
        client = worker._get_qbit_client(instance_name)
        if client is None:
            if warn_missing_client:
                worker.logger.warning(
                    "Cannot %s %d torrent(s) on qBit instance '%s': no client",
                    action_verb,
                    len(hashes),
                    instance_name,
                )
            still_pending[instance_name].update(hashes)
            continue
        if log_names:
            label = "Pausing" if api_method == "torrents_pause" else "Resuming"
            for torrent_hash in hashes:
                worker.logger.debug(
                    "%s %s (%s)",
                    label,
                    torrent_hash,
                    qbit_manager.name_cache.get(torrent_hash),
                )
        try:
            api = getattr(client, api_method)
            with_retry(
                lambda a=api, hs=hashes: a(torrent_hashes=list(hs)),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
        except Exception:
            still_pending[instance_name].update(hashes)
            continue
        if after_success is not None:
            with contextlib.suppress(Exception):
                after_success(client, instance_name, hashes)
        if add_to_timed_ignore:
            for torrent_hash in hashes:
                worker.timed_ignore_cache.add(torrent_hash)
    setattr(worker, bucket_attr, still_pending)


def _mutate_legacy_hash_set(
    worker: Any,
    set_attr: str,
    api_method: str,
    *,
    log_names: bool = False,
    add_to_timed_ignore: bool = False,
) -> None:
    """Pause or resume hashes in a legacy ``worker.<set_attr>`` set via the primary client."""
    hashes = getattr(worker, set_attr)
    if not hashes or not get_auto_pause_resume_effective():
        return
    worker.needs_cleanup = True
    qbit_manager = worker.manager.qbit_manager
    if log_names:
        label = "Pausing" if api_method == "torrents_pause" else "Resuming"
        for torrent_hash in hashes:
            worker.logger.debug(
                "%s %s (%s)",
                label,
                torrent_hash,
                qbit_manager.name_cache.get(torrent_hash),
            )
    primary = worker._get_primary_qbit_client()
    if primary is not None:
        api = getattr(primary, api_method)
        with contextlib.suppress(Exception):
            with_retry(
                lambda a=api, hs=hashes: a(torrent_hashes=list(hs)),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
    if add_to_timed_ignore:
        for torrent_hash in hashes:
            worker.timed_ignore_cache.add(torrent_hash)
    hashes.clear()


def pause_hashes_by_instance(
    worker: Any,
    *,
    warn_missing_client: bool = True,
    log_names: bool = False,
) -> None:
    """Pause ``worker.pause_by_instance`` hashes on their owning qBit clients."""
    _mutate_hashes_by_instance(
        worker,
        "pause_by_instance",
        "torrents_pause",
        action_verb="pause",
        warn_missing_client=warn_missing_client,
        log_names=log_names,
    )


def pause_legacy_hash_set(worker: Any, *, log_names: bool = False) -> None:
    """Pause hashes in the legacy ``worker.pause`` set via the primary qBit client."""
    _mutate_legacy_hash_set(worker, "pause", "torrents_pause", log_names=log_names)


def resume_hashes_by_instance(
    worker: Any,
    *,
    warn_missing_client: bool = True,
    after_success: Callable[[Any, str, Iterable[str]], None] | None = None,
) -> None:
    """Resume ``worker.resume_by_instance`` hashes on their owning qBit clients."""
    _mutate_hashes_by_instance(
        worker,
        "resume_by_instance",
        "torrents_resume",
        action_verb="resume",
        warn_missing_client=warn_missing_client,
        after_success=after_success,
        add_to_timed_ignore=True,
    )


def resume_legacy_hash_set(worker: Any) -> None:
    """Resume hashes in the legacy ``worker.resume`` set via the primary qBit client."""
    _mutate_legacy_hash_set(worker, "resume", "torrents_resume", add_to_timed_ignore=True)


def delete_hashes_per_instance(
    worker: Any,
    batches: dict[str, set[str]],
    *,
    use_qbit_retry: bool = True,
    after_success: Callable[[set[str]], None] | None = None,
) -> set[str]:
    """Delete per-instance hash batches; return successfully deleted hashes."""
    deleted: set[str] = set()
    for instance_name, hashes in batches.items():
        if not hashes:
            continue
        client = worker._get_qbit_client(instance_name)
        if client is None:
            worker.logger.warning(
                "Cannot delete %d torrent(s) from qBit instance '%s': no client",
                len(hashes),
                instance_name,
            )
            continue
        try:
            if use_qbit_retry and hasattr(worker, "_qbit_retry"):
                worker._qbit_retry(
                    lambda c=client, h=list(hashes): c.torrents_delete(hashes=h, delete_files=True)
                )
            else:
                with_retry(
                    lambda c=client, h=hashes: c.torrents_delete(hashes=h, delete_files=True),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
                )
            deleted.update(hashes)
            if after_success is not None:
                after_success(set(hashes))
        except _QBIT_TORRENT_DELETE_EXCEPTIONS as exc:
            worker.logger.error(
                "Failed to delete %d torrent(s) from qBit instance '%s': %s",
                len(hashes),
                instance_name,
                exc,
            )
    return deleted


def delete_hashes_on_primary(
    worker: Any,
    hashes: set[str],
    *,
    use_qbit_retry: bool = True,
    warn_if_missing: bool = False,
    error_label: str = "from qBit",
) -> set[str]:
    """Delete hashes via the primary qBit client; return successfully deleted hashes."""
    if not hashes:
        return set()
    primary = worker._get_primary_qbit_client()
    if primary is None:
        if warn_if_missing:
            worker.logger.warning(
                "Cannot delete %d torrent(s): no qBit client available",
                len(hashes),
            )
        return set()
    try:
        if use_qbit_retry and hasattr(worker, "_qbit_retry"):
            worker._qbit_retry(
                lambda c=primary, h=hashes: c.torrents_delete(hashes=h, delete_files=True)
            )
        else:
            with_retry(
                lambda c=primary, h=hashes: c.torrents_delete(hashes=h, delete_files=True),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
            )
        return set(hashes)
    except _QBIT_TORRENT_DELETE_EXCEPTIONS as exc:
        worker.logger.error(
            "Failed to delete %d torrent(s) %s: %s",
            len(hashes),
            error_label,
            exc,
        )
        return set()
