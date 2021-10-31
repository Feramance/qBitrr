class QBitManagerExceptions(Exception):
    """Base Exception"""


class ConfigException(QBitManagerExceptions):
    """Base Exception for Config related exceptions"""


class ArrManagerException(QBitManagerExceptions):
    """Base Exception for Arr related Exceptions"""


class SkipException(QBitManagerExceptions):
    """Dummy error to skip actions"""


class RequireConfigValue(QBitManagerExceptions):
    """Exception raised when a config value requires a value."""

    def __init__(self, config_class: str, config_key: str):
        self.message = f"Config key '{config_key}' in '{config_class}' requires a value."


class NoConnectionrException(QBitManagerExceptions):
    def __init__(self, message: str):
        self.message = message


class DelayLoopException(QBitManagerExceptions):
    def __init__(self, length: int, type: str):
        self.type = type
        self.length = length
