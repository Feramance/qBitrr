"""Shared qBit pause/resume/delete side-effect helpers for Arr workers."""

from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
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


def resolve_removal_torrent(
    worker: Any, hash_: str, instance_name: str | None = None
) -> tuple[str, Any, Any] | None:
    """Resolve a fresh torrent without guessing the owner of a legacy hash-only request."""
    matches = []
    try:
        instances = (
            [instance_name]
            if instance_name
            else list(worker.manager.qbit_manager.get_all_instances())
        )
        if not instances:
            return None
        for instance in instances:
            client = worker._get_qbit_client(instance)
            if client is None:
                return None
            for torrent in client.torrents_info(torrent_hashes=hash_):
                if torrent.hash.lower() == hash_.lower():
                    torrent._qbitrr_instance = instance
                    matches.append((instance, client, torrent))
    except Exception as exc:
        worker.logger.warning("HnR ownership lookup failed for %s: %s", hash_, type(exc).__name__)
        return None
    return matches[0] if len(matches) == 1 else None


def _torrent_file_paths(client: Any, torrent: Any) -> list[Path]:
    """Resolve only file paths contained within the torrent's declared save root."""
    root = Path(torrent.save_path)
    if not root.is_absolute() or root.resolve() == root.resolve().parent:
        raise ValueError("Unknown or unsafe torrent save root")
    root = root.resolve()
    paths = []
    for file in client.torrents_files(torrent_hash=torrent.hash):
        relative = Path(file.name)
        path = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise ValueError("Torrent file escapes its save root")
        paths.append(path)
    return paths


def removal_candidate(torrent: Any) -> tuple:
    """Identify the torrent incarnation and activity behind a removal decision."""
    return tuple(
        getattr(torrent, key, None)
        for key in (
            "added_on",
            "category",
            "state",
            "progress",
            "last_activity",
            "save_path",
            "content_path",
            "eta",
            "availability",
        )
    )


def content_removal_allowed(worker: Any, paths: list[Path]) -> bool:
    """Verify HnR for every current torrent referencing any targeted content path."""
    owners = []
    try:
        targets = [path.resolve() for path in paths]
        for instance in worker.manager.qbit_manager.get_all_instances():
            client = worker._get_qbit_client(instance)
            if client is None:
                return False
            for torrent in client.torrents_info():
                files = _torrent_file_paths(client, torrent)
                if not files:
                    return False
                for path in files:
                    if any(path == target or path.is_relative_to(target) for target in targets):
                        owners.append((instance, client, torrent))
                        break
        if not owners:
            return False
        for instance, client, torrent in owners:
            fresh = resolve_removal_torrent(worker, torrent.hash, instance)
            if fresh is None or not worker._deletion_rules_allow(
                fresh[2], "torrent content cleanup", instance_name=instance, client=client
            ):
                return False
        return True
    except Exception as exc:
        worker.logger.warning("HnR content lookup failed: %s", type(exc).__name__)
        return False


def delete_hashes_per_instance(
    worker: Any,
    batches: dict[str, set[str]],
    *,
    use_qbit_retry: bool = True,
    delete_files: bool = True,
) -> set[tuple[str, str]]:
    """Delete only freshly cleared torrents; preserve client identity in confirmed results."""
    deleted = set()
    for instance_name, hashes in batches.items():
        for hash_ in hashes:
            expected = getattr(worker, "_removal_candidates", {}).get((instance_name, hash_))

            def attempt() -> bool:
                nonlocal expected
                current = resolve_removal_torrent(worker, hash_, instance_name)
                if current is None:
                    return False
                instance, client, torrent = current
                snapshot = removal_candidate(torrent)
                if expected is None:
                    expected = snapshot
                if expected != snapshot:
                    return False
                reason = getattr(worker, "_removal_reasons", {}).get((instance, hash_))
                if reason == "CF unmet deletion" and not (
                    worker.custom_format_unmet_search and worker.custom_format_unmet_check(torrent)
                ):
                    return False
                if not worker._deletion_rules_allow(
                    torrent, "final torrent removal", instance_name=instance, client=client
                ):
                    return False
                if delete_files:
                    paths = _torrent_file_paths(client, torrent)
                    if not paths or not content_removal_allowed(worker, paths):
                        return False
                # A content scan can be lengthy; refresh the candidate again before mutation.
                current = resolve_removal_torrent(worker, hash_, instance)
                if (
                    current is None
                    or removal_candidate(current[2]) != snapshot
                    or not worker._deletion_rules_allow(
                        current[2], "final torrent removal", instance_name=instance, client=client
                    )
                ):
                    return False
                result = client.torrents_delete(hashes=[hash_], delete_files=delete_files)
                return result is not False

            try:
                result = (
                    worker._qbit_retry(attempt)
                    if use_qbit_retry and hasattr(worker, "_qbit_retry")
                    else with_retry(
                        attempt,
                        retries=3,
                        backoff=0.5,
                        max_backoff=3,
                        exceptions=_QBIT_TORRENT_DELETE_EXCEPTIONS,
                    )
                )
                if result:
                    deleted.add((instance_name, hash_))
                    worker.logger.info(
                        "Removed torrent %s from %s after HnR clearance", hash_, instance_name
                    )
            except Exception as exc:
                worker.logger.warning(
                    "Removal retained for %s on %s: %s", hash_, instance_name, type(exc).__name__
                )
    return deleted


def delete_hashes_on_primary(
    worker: Any,
    hashes: set[str],
    *,
    use_qbit_retry: bool = True,
    warn_if_missing: bool = False,
    error_label: str = "from qBit",
) -> set[tuple[str, str]]:
    """Compatibility entry point: resolve unique owners instead of falling back to a primary."""
    batches = defaultdict(set)
    for hash_ in hashes:
        current = resolve_removal_torrent(worker, hash_)
        if current:
            batches[current[0]].add(hash_)
        else:
            worker.logger.warning(
                "Removal blocked for %s: owning client is unavailable or ambiguous", hash_
            )
    return delete_hashes_per_instance(worker, batches, use_qbit_retry=use_qbit_retry)
