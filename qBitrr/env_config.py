from __future__ import annotations

import environ


def _strtobool(value: str) -> int:
    """Return 1 for truthy strings and 0 for falsy strings, mirroring distutils.util.strtobool."""
    if value is None:
        raise ValueError("Boolean value must be a string")
    normalized = value.strip().lower()
    if normalized in {"y", "yes", "t", "true", "on", "1"}:
        return 1
    if normalized in {"n", "no", "f", "false", "off", "0"}:
        return 0
    raise ValueError(f"Invalid truth value {value!r}")


class Converter:
    @staticmethod
    def int(value: str | None) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def list(value: str | None, delimiter=",", converter=str) -> list | None:
        return None if value is None else list(map(converter, value.split(delimiter)))

    @staticmethod
    def bool(value: str | None) -> bool | None:
        return None if value is None else _strtobool(value) == 1


@environ.config(prefix="QBITRR", frozen=True)
class AppConfig:
    @environ.config(prefix="OVERRIDES", frozen=True)
    class Overrides:
        search_only = environ.var(None, converter=Converter.bool)
        processing_only = environ.var(None, converter=Converter.bool)
        data_path = environ.var(None)

    @environ.config(prefix="SETTINGS", frozen=True)
    class Settings:
        console_level = environ.var(None)
        logging = environ.var(None, converter=Converter.bool)
        completed_download_folder = environ.var(None)
        free_space = environ.var(None)
        free_space_folder = environ.var(None)
        no_internet_sleep_timer = environ.var(None, converter=Converter.int)
        loop_sleep_timer = environ.var(None, converter=Converter.int)
        search_loop_delay = environ.var(None, converter=Converter.int)
        auto_pause_resume = environ.var(None, converter=Converter.bool)
        failed_category = environ.var(None)
        recheck_category = environ.var(None)
        tagless = environ.var(None, converter=Converter.bool)
        ignore_torrents_younger_than = environ.var(None, converter=Converter.int)
        ping_urls = environ.var(None, converter=Converter.list)
        ffprobe_auto_update = environ.var(None, converter=Converter.bool)
        auto_update_enabled = environ.var(None, converter=Converter.bool)
        auto_update_cron = environ.var(None)

    @environ.config(prefix="QBIT", frozen=True)
    class qBit:
        disabled = environ.var(None, converter=Converter.bool)
        host = environ.var(None)
        port = environ.var(None, converter=Converter.int)
        username = environ.var(None)
        password = environ.var(None)

    overrides: Overrides = environ.group(Overrides)
    settings: Settings = environ.group(Settings)
    qbit: qBit = environ.group(qBit)


ENVIRO_CONFIG: AppConfig = environ.to_config(AppConfig)
