from __future__ import annotations

from threading import RLock
from typing import Any

from peewee import Model, SqliteDatabase, TextField

from qBitrr.home_path import APPDATA_FOLDER

_DB_LOCK = RLock()
_DB_INSTANCE: SqliteDatabase | None = None


def _get_database() -> SqliteDatabase:
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        path = APPDATA_FOLDER.joinpath("webui_activity.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        _DB_INSTANCE = SqliteDatabase(
            str(path),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -64_000,
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 0,
                "read_uncommitted": 1,
            },
            timeout=15,
            check_same_thread=False,
        )
    return _DB_INSTANCE


class BaseModel(Model):
    class Meta:
        database = _get_database()


class SearchActivity(BaseModel):
    category = TextField(primary_key=True)
    summary = TextField(null=True)
    timestamp = TextField(null=True)


def _ensure_tables() -> None:
    db = _get_database()
    with _DB_LOCK:
        db.connect(reuse_if_open=True)
        db.create_tables([SearchActivity], safe=True)


def record_search_activity(category: str, summary: str | None, timestamp: str | None) -> None:
    if not category:
        return
    _ensure_tables()
    if timestamp is not None and not isinstance(timestamp, str):
        timestamp = str(timestamp)
    data: dict[str, Any] = {"summary": summary, "timestamp": timestamp}
    with _get_database().atomic():
        SearchActivity.insert(category=category, **data).on_conflict(
            conflict_target=[SearchActivity.category],
            update=data,
        ).execute()


def fetch_search_activities() -> dict[str, dict[str, str | None]]:
    _ensure_tables()
    activities: dict[str, dict[str, str | None]] = {}
    db = _get_database()
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
    _ensure_tables()
    with _get_database().atomic():
        SearchActivity.delete().where(SearchActivity.category == category).execute()
