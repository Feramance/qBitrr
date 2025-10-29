from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from qBitrr.home_path import APPDATA_FOLDER

if os.name == "nt":  # pragma: no cover - platform specific
    import msvcrt
else:  # pragma: no cover
    import fcntl

_LOCK_FILE = APPDATA_FOLDER.joinpath("qbitrr.db.lock")


class _InterProcessFileLock:
    """Cross-process, re-entrant file lock to guard SQLite access."""

    def __init__(self, path: Path):
        self._path = path
        self._thread_gate = threading.RLock()
        self._local = threading.local()

    def acquire(self) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth == 0:
            self._thread_gate.acquire()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(self._path, "a+b")
            try:
                if os.name == "nt":  # pragma: no cover - Windows specific branch
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:  # pragma: no cover - POSIX branch
                    fcntl.flock(handle, fcntl.LOCK_EX)
            except Exception:
                handle.close()
                self._thread_gate.release()
                raise
            self._local.handle = handle
        self._local.depth = depth + 1

    def release(self) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth <= 0:
            raise RuntimeError("Attempted to release an unacquired database lock")
        depth -= 1
        if depth == 0:
            handle = getattr(self._local, "handle")
            try:
                if os.name == "nt":  # pragma: no cover
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    fcntl.flock(handle, fcntl.LOCK_UN)
            finally:
                handle.close()
                del self._local.handle
                self._thread_gate.release()
        self._local.depth = depth

    @contextmanager
    def context(self) -> Iterator[None]:
        self.acquire()
        try:
            yield
        finally:
            self.release()


_DB_LOCK = _InterProcessFileLock(_LOCK_FILE)


@contextmanager
def database_lock() -> Iterator[None]:
    """Provide a shared lock used to serialize SQLite access across processes."""
    with _DB_LOCK.context():
        yield
