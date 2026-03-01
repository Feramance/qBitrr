from __future__ import annotations

import logging
from threading import RLock
from typing import Any

from peewee import Model, TextField

from qBitrr.database import get_database
from qBitrr.db_lock import database_lock

logger = logging.getLogger("qBitrr.SearchActivityStore")

_DB_LOCK = RLock()


class SearchActivity(Model):
    category = TextField(primary_key=True)
    summary = TextField(null=True)
    timestamp = TextField(null=True)


def _ensure_tables() -> None:
    db = get_database()
    with database_lock():
        with _DB_LOCK:
            # Bind model to database if not already bound
            if not SearchActivity._meta.database:
                db.bind([SearchActivity])
            db.create_tables([SearchActivity], safe=True)


def record_search_activity(category: str, summary: str | None, timestamp: str | None) -> None:
    if not category:
        return
    _ensure_tables()
    if timestamp is not None and not isinstance(timestamp, str):
        timestamp = str(timestamp)
    data: dict[str, Any] = {"summary": summary, "timestamp": timestamp}
    with database_lock():
        with _DB_LOCK:
            with get_database().atomic():
                SearchActivity.insert(category=category, **data).on_conflict(
                    conflict_target=[SearchActivity.category],
                    update=data,
                ).execute()


def fetch_search_activities() -> dict[str, dict[str, str | None]]:
    _ensure_tables()
    activities: dict[str, dict[str, str | None]] = {}
    try:
        with database_lock():
            with _DB_LOCK:
                query = SearchActivity.select()
                for row in query:
                    activities[str(row.category)] = {
                        "summary": row.summary,
                        "timestamp": row.timestamp,
                    }
    except Exception as e:
        logger.error("Failed to fetch search activities: %s", e)
    return activities


def clear_search_activity(category: str) -> None:
    if not category:
        return
    _ensure_tables()
    with database_lock():
        with _DB_LOCK:
            with get_database().atomic():
                SearchActivity.delete().where(SearchActivity.category == category).execute()
