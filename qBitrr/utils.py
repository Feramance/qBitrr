from __future__ import annotations

import logging
import pathlib
import random
import re
import socket
import time
from typing import Iterator

import ping3
import qbittorrentapi
from cachetools import TTLCache

ping3.EXCEPTIONS = True

logger = logging.getLogger("qBitrr.Utils")

CACHE = TTLCache(maxsize=50, ttl=60)

UNITS = {"k": 1024, "m": 1048576, "g": 1073741824, "t": 1099511627776}


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
    file_counter = 0
    error = True
    while error:
        try:
            if file_counter == 50:
                error = False
            yield from pathlib.Path(directory).glob("**/*")
            error = False
            file_counter = 0
        except FileNotFoundError as e:
            file_counter += 1
            if file_counter == 1:
                logger.warning("%s - %s", e.strerror, e.filename)


def validate_and_return_torrent_file(file: str) -> pathlib.Path:
    path = pathlib.Path(file)
    if path.is_file():
        path = path.parent.absolute()
    count = 9
    while not path.exists():
        logger.debug(
            "Attempt %s/10: File does not yet exist! (Possibly being moved?) | "
            "%s | Sleeping for 0.1s",
            10 - count,
            path,
        )
        time.sleep(0.1)
        if count == 0:
            break
        count -= 1
    else:
        count = 0
    while str(path) == ".":
        path = pathlib.Path(file)
        if path.is_file():
            path = path.parent.absolute()
        while not path.exists():
            logger.debug(
                "Attempt %s/10: File does not yet exist! (Possibly being moved?) | "
                "%s | Sleeping for 0.1s",
                10 - count,
                path,
            )
            time.sleep(0.1)
            if count == 0:
                break
            count -= 1
        else:
            count = 0
        if count == 0:
            break
        count -= 1
    return path


def has_internet(client: qbittorrentapi.Client):
    from qBitrr.config import PING_URLS

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
        self.container = {}
        for arg in args:
            self.add(arg)

    def __repr__(self):
        self.__update__()
        return f"{self.__class__.__name__}({', '.join(map(str, self.container.keys()))})"

    def extend(self, args):
        """Add several items at once."""
        for arg in args:
            self.add(arg)

    def add(self, value):
        self.container[value] = time.time()

    def remove(self, item):
        del self.container[item]

    def contains(self, value):
        if value not in self.container:
            return False
        if time.time() - self.container[value] > self.age:
            del self.container[value]
            return False
        return True

    __contains__ = contains

    def __getitem__(self, index):
        self.__update__()
        return list(self.container.keys())[index]

    def __iter__(self):
        self.__update__()
        return iter(self.container.copy())

    def __len__(self):
        self.__update__()
        return len(self.container)

    def __copy__(self):
        self.__update__()
        temp = ExpiringSet(max_age_seconds=self.age)
        temp.container = self.container.copy()
        return temp

    def __update__(self):
        for k, b in self.container.copy().items():
            if time.time() - b > self.age:
                del self.container[k]
                return False

    def __eq__(self, other):
        if not isinstance(other, ExpiringSet):
            return False
        self.__update__()
        other.__update__()
        return set(self.container.keys()) == set(other.container.keys())
