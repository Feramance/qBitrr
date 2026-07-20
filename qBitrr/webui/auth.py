from __future__ import annotations

import threading
import time

import bcrypt

from qBitrr.config import CONFIG as _CONFIG_DEFAULT

_MISSING = object()


def _get_config():
    import qBitrr.webui as webui_mod

    return getattr(webui_mod, "CONFIG", _CONFIG_DEFAULT)


def _optional_bool(key: str) -> bool | None:
    """Return True/False when ``key`` is present; ``None`` when the key is missing."""
    value = _get_config().get(key, fallback=_MISSING)
    if value is _MISSING:
        return None
    return bool(value)


class _RateLimiter:
    """Sliding-window IP rate limiter (thread-safe)."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self._max = max_attempts
        self._window = window_seconds
        self._data: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            # Opportunistically prune stale entries so old IP keys do not accumulate forever.
            for existing_key, existing_times in list(self._data.items()):
                filtered_times = [t for t in existing_times if now - t < self._window]
                if filtered_times:
                    self._data[existing_key] = filtered_times
                else:
                    self._data.pop(existing_key, None)

            times = self._data.get(key, [])
            if len(times) >= self._max:
                return False
            times.append(now)
            self._data[key] = times
            return True


_login_limiter = _RateLimiter(max_attempts=10, window_seconds=900)
_setpw_limiter = _RateLimiter(max_attempts=5, window_seconds=900)
# Unauthenticated /web/meta?force=1 can hit GitHub; keep this tight.
_meta_force_limiter = _RateLimiter(max_attempts=6, window_seconds=900)
_setpw_lock = threading.Lock()


def _pw_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _pw_verify(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def _auth_disabled() -> bool:
    return bool(_get_config().get("WebUI.AuthDisabled", fallback=True))


def _allow_insecure_exposure() -> bool | None:
    """Whether public bind + AuthDisabled is explicitly acknowledged.

    Returns:
        True/False when ``WebUI.AllowInsecureExposure`` is set.
        None when the key is absent (legacy configs: warn only, do not refuse).
    """
    return _optional_bool("WebUI.AllowInsecureExposure")


def _allow_insecure_token_query() -> bool:
    """Whether ``?token=`` auth is accepted.

    Missing key defaults to True for backward compatibility; new installs set False.
    """
    value = _optional_bool("WebUI.AllowInsecureTokenQuery")
    if value is None:
        return True
    return value


def _is_public_bind_host(host: str) -> bool:
    return host in {"0.0.0.0", "::"}


def _check_insecure_exposure(host: str) -> str | None:
    """Return an error message when AuthDisabled + public bind is not acknowledged.

    Legacy configs missing ``AllowInsecureExposure`` return None (warn-only path).
    """
    if not _auth_disabled() or not _is_public_bind_host(host):
        return None
    allowed = _allow_insecure_exposure()
    if allowed is None:
        return None
    if allowed:
        return None
    return (
        "WebUI authentication is disabled while listening on a public interface "
        f"({host}) and WebUI.AllowInsecureExposure is false. Set "
        "WebUI.AllowInsecureExposure = true to acknowledge that the full admin API "
        "(including /api/token, /web/token, config, and self-update) is reachable "
        "without credentials; bind WebUI.Host to 127.0.0.1; or set "
        "WebUI.AuthDisabled = false."
    )


def _local_auth_enabled() -> bool:
    return bool(_get_config().get("WebUI.LocalAuthEnabled", fallback=False))


def _oidc_enabled() -> bool:
    return (
        bool(_get_config().get("WebUI.OIDCEnabled", fallback=False))
        and bool(_get_config().get("WebUI.OIDC.Authority", fallback=""))
        and bool(_get_config().get("WebUI.OIDC.ClientId", fallback=""))
    )
