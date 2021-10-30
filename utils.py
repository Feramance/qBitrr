import pathlib
import random
import sys
import time
from typing import Iterator, Union

import logbook
import requests

from config import PING_URLS
from logger import CONSOLE_LOGGING_LEVEL

logger = logbook.Logger("Utilities")
logger.handlers.append(logbook.StderrHandler(level=CONSOLE_LOGGING_LEVEL))


def absolute_file_paths(directory: Union[pathlib.Path, str]) -> Iterator[pathlib.Path]:
    for path in pathlib.Path(directory).glob("**/*"):
        yield path


def validate_and_return_torrent_file(file: str) -> pathlib.Path:
    path = pathlib.Path(file)
    if path.is_file():
        path = path.parent.absolute()
    count = 10
    while not path.exists():
        logger.trace(
            "Attempt {count}/10 : File does not yet exists! (Possibly being moved?) - "
            "{path} - Sleeping for 0.1s",
            path=path,
            count=11 - count,
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
                "Attempt {count}/10 :File does not yet exists! (Possibly being moved?) - "
                "{path} - Sleeping for 0.1s",
                path=path,
                count=11 - count,
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


def has_internet() -> bool:
    try:
        requests.get(random.choice(PING_URLS), timeout=5)
        logger.trace("has_internet check: True")
        return True
    except (requests.ConnectionError, requests.Timeout):
        logger.warning("has_internet check: False")
        return False
    except Exception:
        logger.error(exc_info=sys.exc_info())
        return False


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
        return "%s(%s)" % (self.__class__.__name__, ", ".join(self.container.keys()))

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
