from __future__ import annotations

import logging
import pathlib
import random
import socket
import time
from typing import Iterator

import ping3
from cachetools import TTLCache

ping3.EXCEPTIONS = True

logger = logging.getLogger("qBitrr.Utils")

CACHE = TTLCache(maxsize=50, ttl=60)


def absolute_file_paths(directory: pathlib.Path | str) -> Iterator[pathlib.Path]:
    error = True
    while error is True:
        try:
            yield from pathlib.Path(directory).glob("**/*")
            error = False
        except FileNotFoundError as e:
            logger.warning("%s - %s", e.strerror, e.filename)


def validate_and_return_torrent_file(file: str) -> pathlib.Path:
    path = pathlib.Path(file)
    if path.is_file():
        path = path.parent.absolute()
    count = 9
    while not path.exists():
        logger.trace(
            "Attempt %s/10: File does not yet exists! (Possibly being moved?) | "
            "%s | Sleeping for 0.1s",
            path,
            10 - count,
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
            logger.trace(
                "Attempt %s/10:File does not yet exists! (Possibly being moved?) | "
                "%s | Sleeping for 0.1s",
                path,
                10 - count,
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


def has_internet():
    from qBitrr.config import PING_URLS

    url = random.choice(PING_URLS)
    if not is_connected(url):
        return False
    logger.trace("Successfully connected to %s", url)
    return True


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
        logger.trace(
            "Error when connecting to host: %s %s %s",
            hostname,
            host,
            e,
        )
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
        logger.debug(
            "Error when connecting to host: %s %s",
            hostname,
            e,
        )
    except Exception:  # Ping3 is far more robust but may requite root access, if root access is not available then run the basic mode
        return _basic_ping(hostname)


class ExpiringSet:
    def __init__(self, *args, **kwargs):
        max_age_seconds = kwargs.get("max_age_seconds", 0)
        assert max_age_seconds > 0
        self.age = max_age_seconds
        self.container = {}
        for arg in args:
            self.add(arg)

    def __repr__(self):
        self.__update__()
        return f"{self.__class__.__name__}({', '.join(self.container.keys())})"

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

    def __hash__(self):
        return hash(*(self.container.keys()))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()
