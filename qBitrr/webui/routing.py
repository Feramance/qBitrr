from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Flask


def dual_route(app: Flask, path: str, *, methods: tuple[str, ...] = ("GET",)) -> Any:
    """Register identical ``/api`` and ``/web`` handlers (escape hatch: register divergent pairs manually).

    Intentionally separate (not dual_route): ``/meta`` (web adds auth fields),
    ``/token`` (different auth gates), ``/config`` GET (web wraps version warnings).
    """

    def decorator(fn: Any) -> Any:
        endpoint_base = fn.__name__

        @wraps(fn)
        def api_view(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        @wraps(fn)
        def web_view(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        app.add_url_rule(
            f"/api{path}",
            endpoint=f"api_{endpoint_base}",
            view_func=api_view,
            methods=list(methods),
        )
        app.add_url_rule(
            f"/web{path}",
            endpoint=f"web_{endpoint_base}",
            view_func=web_view,
            methods=list(methods),
        )
        return fn

    return decorator
