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
        super().__init__(self.message)


class NoConnectionrException(qBitManagerError):
    """Raised when a connection to a service cannot be established.

    The ``error_type`` attribute (``"delay"`` or ``"no_internet"``) controls
    whether the caller should retry after a short delay or treat the outage
    as a prolonged connectivity failure.
    """

    def __init__(self, message: str, error_type: str = "delay"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class DelayLoopException(qBitManagerError):
    """Raised to signal that the current event-loop iteration should pause.

    This is a control-flow exception, not an error.  ``length`` is the
    requested sleep duration in seconds and ``error_type`` indicates the
    reason (e.g. ``"delay"`` or ``"no_internet"``).
    """

    def __init__(self, length: int, error_type: str):
        self.error_type = error_type
        self.length = length
        super().__init__(f"Delay loop: {error_type}")


class RestartLoopException(ArrManagerException):
    """Exception to trigger a loop restart"""
