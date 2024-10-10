class qBitManagerError(Exception):
    """Base Exception"""


class UnhandledError(qBitManagerError):
    """Use to raise when there an unhandled edge case"""


class ConfigException(qBitManagerError):
    """Base Exception for Config related exceptions"""


class ArrManagerException(qBitManagerError):
    """Base Exception for Arr related Exceptions"""


class SkipException(qBitManagerError):
    """Dummy error to skip actions"""


class RequireConfigValue(qBitManagerError):
    """Exception raised when a config value requires a value."""

    def __init__(self, config_class: str, config_key: str):
        self.message = f"Config key '{config_key}' in '{config_class}' requires a value."


class NoConnectionrException(qBitManagerError):
    def __init__(self, message: str, type: str = "delay"):
        self.message = message
        self.type = type


class DelayLoopException(qBitManagerError):
    def __init__(self, length: int, type: str):
        self.type = type
        self.length = length


class RestartLoopException(ArrManagerException):
    """Exception to trigger a loop restart"""
