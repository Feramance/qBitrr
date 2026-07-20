from __future__ import annotations

import pathlib
from functools import reduce

from tomlkit import document, parse
from tomlkit.toml_document import TOMLDocument

from qBitrr.duration_config import parse_duration
from qBitrr.gen_config.sections import generate_doc


class MyConfig:
    # Original code taken from https://github.com/SemenovAV/toml_config
    # Licence is MIT, can be located at
    # https://github.com/SemenovAV/toml_config/blob/master/LICENSE.txt

    path: pathlib.Path
    config: TOMLDocument
    defaults_config: TOMLDocument

    def __init__(self, path: pathlib.Path | str, config: TOMLDocument | None = None):
        self.path = pathlib.Path(path)
        self._giving_data = bool(config)
        self.config = config or document()
        self.defaults_config = generate_doc()
        self.err = None
        self.state = True
        self.load()

    def __str__(self):
        return self.config.as_string()

    def load(self) -> MyConfig:
        if self.state:
            try:
                if self._giving_data:
                    return self
                with self.path.open() as file:
                    self.config = parse(file.read())
                    return self
            except (OSError, TypeError) as err:
                self.state = False
                self.err = err
        return self

    def save(self) -> MyConfig:
        if self.state:
            try:
                with open(self.path, "w", encoding="utf8") as file:
                    file.write(self.config.as_string())
                    return self
            except OSError as err:
                self._value_error(
                    err, "Possible permissions while attempting to read the config file.\n"
                )
            except TypeError as err:
                self._value_error(err, "While attempting to read the config file.\n")
        return self

    def _value_error(self, err, arg1):
        self.state = False
        self.err = err
        raise ValueError(f"{arg1}{err}")

    def get(self, section: str, fallback: Any = None) -> T:
        return self._deep_get(section, default=fallback)

    def get_duration(self, dotted_key: str, fallback: int = -1, unit: str = "seconds") -> int:
        """
        Get a time value in seconds or minutes. Accepts int or suffixed string (e.g. "1w", "60m").
        Plain numbers are treated as the key's base unit (seconds or minutes).
        """
        raw = self._deep_get(dotted_key, default=fallback)
        if raw is ... or raw is None:
            return fallback
        if unit == "minutes":
            return parse_duration(raw, unit="minutes", fallback=fallback)
        return parse_duration(raw, unit="seconds", fallback=fallback)

    def get_or_raise(self, section: str) -> T:
        if (r := self._deep_get(section, default=KeyError)) is KeyError:
            raise KeyError(f"{section} does not exist")
        return r

    def sections(self):
        return self.config.keys()

    def _deep_get(self, keys, default=...):
        values = reduce(
            lambda d, key: d.get(key, ...) if isinstance(d, dict) else ...,
            keys.split("."),
            self.config,
        )

        return values if values is not ... else default
