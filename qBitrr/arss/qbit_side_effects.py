"""Shared qBit pause/resume/delete side-effect helpers for Arr workers."""

from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from qBitrr.arss._shared import (
    _QBIT_TORRENT_DELETE_EXCEPTIONS,
    _QBIT_WRITE_RETRY_EXCEPTIONS,
    AUTO_PAUSE_RESUME,
    with_retry,
)


def pause_hashes_by_instance(
    worker: Any,
    *,
    warn_missing_client: bool = True,
    log_names: bool = False,
) -> None:
    """Pause ``worker.pause_by_instance`` hashes on their owning qBit clients."""
    if not worker.pause_by_instance or not AUTO_PAUSE_RESUME:
        return
    worker.needs_cleanup = True
    still_pending: defaultdict[str, set[str]] = defaultdict(set)
    qbit_manager = worker.manager.qbit_manager
    for instance_name, hashes in worker.pause_by_instance.items():
        if not hashes:
            continue
        client = worker._get_qbit_client(instance_name)
        if client is None:
            if warn_missing_client:
                worker.logger.warning(
                    "Cannot pause %d torrent(s) on qBit instance '%s': no client",
                    len(hashes),
                    instance_name,
                )
            still_pending[instance_name].update(hashes)
            continue
        if log_names:
            for torrent_hash in hashes:
                worker.logger.debug(
                    "Pausing %s (%s)", torrent_hash, qbit_manager.name_cache.get(torrent_hash)
                )
        try:
            with_retry(
                lambda c=client, hs=hashes: c.torrents_pause(torrent_hashes=list(hs)),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
        except Exception:
            still_pending[instance_name].update(hashes)
            continue
    worker.pause_by_instance = still_pending


def pause_legacy_hash_set(worker: Any, *, log_names: bool = False) -> None:
    """Pause hashes in the legacy ``worker.pause`` set via the primary qBit client."""
    if not worker.pause or not AUTO_PAUSE_RESUME:
        return
    worker.needs_cleanup = True
    qbit_manager = worker.manager.qbit_manager
    if log_names:
        for torrent_hash in worker.pause:
            worker.logger.debug(
                "Pausing %s (%s)", torrent_hash, qbit_manager.name_cache.get(torrent_hash)
            )
    primary = worker._get_primary_qbit_client()
    if primary is not None:
        with contextlib.suppress(Exception):
            with_retry(
                lambda c=primary: c.torrents_pause(torrent_hashes=list(worker.pause)),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
    worker.pause.clear()


def resume_hashes_by_instance(
    worker: Any,
    *,
    warn_missing_client: bool = True,
    after_success: Callable[[Any, str, Iterable[str]], None] | None = None,
) -> None:
    """Resume ``worker.resume_by_instance`` hashes on their owning qBit clients."""
    if not worker.resume_by_instance or not AUTO_PAUSE_RESUME:
        return
    worker.needs_cleanup = True
    still_pending: defaultdict[str, set[str]] = defaultdict(set)
    for instance_name, hashes in worker.resume_by_instance.items():
        if not hashes:
            continue
        client = worker._get_qbit_client(instance_name)
        if client is None:
            if warn_missing_client:
                worker.logger.warning(
                    "Cannot resume %d torrent(s) on qBit instance '%s': no client",
                    len(hashes),
                    instance_name,
                )
            still_pending[instance_name].update(hashes)
            continue
        try:
            with_retry(
                lambda c=client, hs=hashes: c.torrents_resume(torrent_hashes=list(hs)),
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
        for torrent_hash in hashes:
            worker.timed_ignore_cache.add(torrent_hash)
    worker.resume_by_instance = still_pending


def resume_legacy_hash_set(worker: Any) -> None:
    """Resume hashes in the legacy ``worker.resume`` set via the primary qBit client."""
    if not worker.resume or not AUTO_PAUSE_RESUME:
        return
    worker.needs_cleanup = True
    primary = worker._get_primary_qbit_client()
    if primary is not None:
        with contextlib.suppress(Exception):
            with_retry(
                lambda c=primary, hs=worker.resume: c.torrents_resume(torrent_hashes=list(hs)),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
            )
    for torrent_hash in worker.resume:
        worker.timed_ignore_cache.add(torrent_hash)
    worker.resume.clear()


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
