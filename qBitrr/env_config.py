from distutils.util import strtobool
from typing import Optional

import environ


class Converter:
    @staticmethod
    def int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def list(value: Optional[str], delimiter=",", converter=str) -> Optional[list]:
        if value is None:
            return None
        return list(map(converter, value.split(delimiter)))

    @staticmethod
    def bool(value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        return strtobool(value)


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
        completed_download_folder = environ.var(None)
        no_internet_sleep_timer = environ.var(None, converter=Converter.int)
        loop_sleep_timer = environ.var(None, converter=Converter.int)
        failed_category = environ.var(None)
        recheck_category = environ.var(None)
        ignore_torrents_younger_than = environ.var(None, converter=Converter.int)
        ping_urls = environ.var(None, converter=Converter.list)
        ffprobe_auto_update = environ.var(None, converter=Converter.bool)

    @environ.config(prefix="QBIT", frozen=True)
    class Qbit:
        disabled = environ.var(None, converter=Converter.bool)
        host = environ.var(None)
        port = environ.var(None, converter=Converter.int)
        username = environ.var(None)
        password = environ.var(None)

    overrides: Overrides = environ.group(Overrides)
    settings: Settings = environ.group(Settings)
    qbit: Qbit = environ.group(Qbit)


ENVIRO_CONFIG: AppConfig = environ.to_config(AppConfig)
