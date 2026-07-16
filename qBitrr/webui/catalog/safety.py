from __future__ import annotations

import logging
from functools import wraps

from flask import jsonify


def _is_database_corruption_error(exc: BaseException) -> bool:
    """Return True when *exc* (or its cause chain) indicates SQLite corruption."""
    msg = str(exc).lower()
    if (
        "disk image is malformed" in msg
        or "database disk image is malformed" in msg
        or "database corruption" in msg
    ):
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return _is_database_corruption_error(cause)
    return False


def _arr_catalog_db_safe(handler):
    """Catch catalog DB corruption, attempt repair, return 503 instead of 500."""

    @wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as e:
            if not _is_database_corruption_error(e):
                raise
            log = logging.getLogger("qBitrr.WebUI")
            log.error(
                "Database corruption in Arr catalog handler %s: %s",
                handler.__name__,
                e,
                exc_info=True,
            )
            from qBitrr.database import maintain_database

            repaired = maintain_database(repair_if_unhealthy=True)
            message = (
                "Database was repaired — retry shortly"
                if repaired
                else "Database corruption detected — automatic repair failed"
            )
            return jsonify({"error": message}), 503

    return wrapper
