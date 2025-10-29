from __future__ import annotations

from threading import RLock
from typing import Any

from peewee import SqliteDatabase

from qBitrr.tables import SearchActivity, ensure_table_schema, get_database

_DB_LOCK = RLock()
_TABLE_READY = False


def _ensure_ready() -> SqliteDatabase:
    global _TABLE_READY
    db = get_database()
    if _TABLE_READY:
        return db
    with _DB_LOCK:
        if not _TABLE_READY:
            ensure_table_schema(SearchActivity)
            _TABLE_READY = True
    return db


def record_search_activity(category: str, summary: str | None, timestamp: str | None) -> None:
    if not category:
        return
    db = _ensure_ready()
    if timestamp is not None and not isinstance(timestamp, str):
        timestamp = str(timestamp)
    data: dict[str, Any] = {"summary": summary, "timestamp": timestamp}
    with db.atomic():
        SearchActivity.insert(category=category, **data).on_conflict(
            conflict_target=[SearchActivity.category],
            update=data,
        ).execute()


def fetch_search_activities() -> dict[str, dict[str, str | None]]:
    db = _ensure_ready()
    activities: dict[str, dict[str, str | None]] = {}
    db.connect(reuse_if_open=True)
    try:
        query = SearchActivity.select()
    except Exception:
        return activities
    for row in query:
        activities[str(row.category)] = {
            "summary": row.summary,
            "timestamp": row.timestamp,
        }
    return activities


def clear_search_activity(category: str) -> None:
    if not category:
        return
    db = _ensure_ready()
    with db.atomic():
        SearchActivity.delete().where(SearchActivity.category == category).execute()
