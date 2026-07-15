from __future__ import annotations

import logging
import pathlib
import random
import re
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import ping3
import qbittorrentapi
from cachetools import TTLCache

ping3.EXCEPTIONS = True

logger = logging.getLogger("qBitrr.Utils")

CACHE = TTLCache(maxsize=50, ttl=60)

UNITS = {"k": 1024, "m": 1048576, "g": 1073741824, "t": 1099511627776}


def coerce_bool(value: Any) -> bool:
    """Parse request/config values as boolean.

    Treats ``"0"``, ``"false"``, and ``"none"`` (case-insensitive) as falsy in addition
    to standard Python falsy values.
    """
    return bool(value) and str(value).lower() not in {"0", "false", "none"}


def normalize_url_base(value: str | None) -> str:
    """Normalize WebUI.UrlBase to '' or a leading-slash path without trailing slash."""
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    if not raw.startswith("/"):
        raw = f"/{raw}"
    return raw.rstrip("/")


def qbit_sections(config: Any) -> list[str]:
    """Return all qBit / qBit-* config section names."""
    return [s for s in config.sections() if s == "qBit" or s.startswith("qBit-")]


def with_retry(
    func, *, retries=3, backoff=0.5, max_backoff=5.0, jitter=0.25, exceptions=(Exception,)
):
    """Run `func()` with exponential backoff and jitter for transient failures.

    - retries: total attempts (including first). Set to 1 for no retry.
    - backoff: initial backoff seconds, doubles each attempt up to max_backoff.
    - jitter: random jitter in seconds added to each delay.
    - exceptions: tuple of exception types to catch and retry on.
    """
    attempt = 0
    while True:
        try:
            return func()
        except exceptions as e:
            attempt += 1
            if attempt >= retries:
                raise
            delay = min(max_backoff, backoff * (2 ** (attempt - 1))) + random.random() * jitter
            logger.debug(
                "Retryable error: %s. Retrying in %.2fs (attempt %s/%s)",
                e,
                delay,
                attempt + 1,
                retries,
            )
            time.sleep(delay)


def absolute_file_paths(directory: pathlib.Path | str) -> Iterator[pathlib.Path]:
    """Yield all file paths under directory. Retries on transient FileNotFoundError."""
    max_retries = 10
    for attempt in range(max_retries):
        try:
            # Collect full list before yielding so retries do not duplicate items
            items = list(pathlib.Path(directory).glob("**/*"))
            yield from items
            return
        except FileNotFoundError as e:
            if attempt == 0:
                logger.warning("%s - %s", e.strerror, e.filename)
            if attempt < max_retries - 1:
                time.sleep(0.1)
            else:
                logger.warning(
                    "Giving up on directory after %d retries: %s", max_retries, directory
                )


def validate_and_return_torrent_file(file: str) -> pathlib.Path:
    path = pathlib.Path(file)
    if path.is_file():
        path = path.parent.absolute()
    for attempt in range(10):
        if path.exists() and str(path) != ".":
            return path
        logger.debug(
            "Attempt %s/10: File does not yet exist! (Possibly being moved?) | "
            "%s | Sleeping for 0.1s",
            attempt + 1,
            path,
        )
        time.sleep(0.1)
        path = pathlib.Path(file)
        if path.is_file():
            path = path.parent.absolute()
    return path


def has_internet(client: qbittorrentapi.Client):
    from qBitrr.config import PING_URLS

    if client is None:
        return False

    # Prefer qBit's connection status to avoid frequent pings
    try:
        status = client.transfer_info().get("connection_status")
        if status and status != "disconnected":
            return True
    except Exception as e:
        logger.debug("transfer_info unavailable: %s", e)
    # Fallback to a single ping
    url = random.choice(PING_URLS)
    try:
        if is_connected(url):
            logger.debug("Successfully connected to %s", url)
            return True
    except Exception as e:
        logger.debug("Ping to %s failed: %s", url, e)
    return False


def _basic_ping(hostname):
    host = "N/A"
    try:
        # if this hostname was called within the last 10 seconds skip it
        # if it was previous successful
        # Reducing the number of call to it and the likelihood of rate-limits.
        if hostname in CACHE:
            return CACHE[hostname]
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(hostname)
        # connect to the host -- tells us if the host is actually
        # reachable
        s = socket.create_connection((host, 80), 5)
        s.close()
        CACHE[hostname] = True
        return True
    except Exception as e:
        logger.debug("Error when connecting to host: %s %s %s", hostname, host, e)
        return False


def is_connected(hostname):
    try:
        # if this hostname was called within the last 10 seconds skip it
        # if it was previous successful
        # Reducing the number of call to it and the likelihood of rate-limits.
        if hostname in CACHE:
            return CACHE[hostname]
        ping3.ping(hostname, timeout=5)
        CACHE[hostname] = True
        return True
    except ping3.errors.PingError as e:  # All ping3 errors are subclasses of `PingError`.
        logger.debug("Error when connecting to host: %s %s", hostname, e)
        return False
    except (
        Exception
    ):  # Ping3 is far more robust but may requite root access, if root access is not available then run the basic mode
        return _basic_ping(hostname)


def parse_size(size):
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)([kmgt]?)$", size, re.IGNORECASE)
    if not m:
        raise ValueError("Unsupported value for leave_free_space")
    val = float(m.group(1))
    unit = m.group(2)
    if unit:
        val *= UNITS[unit.lower()]
    return val


class ExpiringSet:
    def __init__(self, *args: list, **kwargs):
        max_age_seconds = kwargs.get("max_age_seconds", 0)
        assert max_age_seconds > 0
        self.age = max_age_seconds
        self._lock = threading.Lock()
        self.container = {}
        for arg in args:
            self.add(arg)

    def __repr__(self):
        with self._lock:
            self.__update__()
            return f"{self.__class__.__name__}({', '.join(map(str, self.container.keys()))})"

    def extend(self, args):
        """Add several items at once."""
        for arg in args:
            self.add(arg)

    def add(self, value):
        with self._lock:
            self.container[value] = time.time()

    def remove(self, item):
        with self._lock:
            del self.container[item]

    def contains(self, value):
        with self._lock:
            if value not in self.container:
                return False
            if time.time() - self.container[value] > self.age:
                del self.container[value]
                return False
            return True

    __contains__ = contains

    def __getitem__(self, index):
        with self._lock:
            self.__update__()
            return list(self.container.keys())[index]

    def __iter__(self):
        with self._lock:
            self.__update__()
            return iter(self.container.copy())

    def __len__(self):
        with self._lock:
            self.__update__()
            return len(self.container)

    def __copy__(self):
        with self._lock:
            self.__update__()
            temp = ExpiringSet(max_age_seconds=self.age)
            temp.container = self.container.copy()
            return temp

    def __update__(self):
        """Expire old entries. Caller must hold self._lock."""
        now = time.time()
        expired = [k for k, b in self.container.items() if now - b > self.age]
        for k in expired:
            del self.container[k]

    def __eq__(self, other):
        if not isinstance(other, ExpiringSet):
            return False
        if self is other:
            return True
        # Acquire locks in a consistent order (by object id) to prevent deadlock
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                self.__update__()
                other.__update__()
                return set(self.container.keys()) == set(other.container.keys())


def mask_secret(value: str | None) -> str:
    """Return '[redacted]' if value is truthy, else empty string."""
    return "[redacted]" if value else ""
