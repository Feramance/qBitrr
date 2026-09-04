"""Tests for database schema migrations (ArtistFiles profile-switch columns)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from peewee import SqliteDatabase

from qBitrr.database import (
    _DB_SCHEMA_VERSION_ARTIST_PROFILE_SWITCH,
    _DB_SCHEMA_VERSION_LIDARR_TRACK_DURATION_SECONDS,
    _apply_db_schema_migrations,
    _get_db_schema_version,
    _get_table_columns,
    _migrate_v4_artist_profile_switch_columns,
    _set_db_schema_version,
)
from qBitrr.tables import ArtistFilesModel


class TestMigrateV4ArtistProfileSwitchColumns(unittest.TestCase):
    """v4 adds LastProfileSwitchTime / CurrentProfileId / OriginalProfileId to artists."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = Path(self._tmpdir.name) / "test.db"
        self.db = SqliteDatabase(str(self.db_path))
        self.db.connect()
        self.addCleanup(self.db.close)

    def _create_legacy_artist_table(self) -> None:
        self.db.execute_sql("""
            CREATE TABLE artistfilesmodel (
                EntryId INTEGER NOT NULL,
                Title TEXT,
                Monitored INTEGER,
                ArrInstance TEXT DEFAULT '',
                Searched INTEGER DEFAULT 0,
                Upgrade INTEGER DEFAULT 0,
                MinCustomFormatScore INTEGER,
                QualityProfileId INTEGER,
                QualityProfileName TEXT,
                AlbumCount INTEGER DEFAULT 0,
                TrackTotalCount INTEGER DEFAULT 0,
                PRIMARY KEY (EntryId, ArrInstance)
            )
            """)

    def test_adds_missing_profile_switch_columns(self) -> None:
        self._create_legacy_artist_table()
        before = set(_get_table_columns(self.db, ArtistFilesModel._meta.table_name))
        self.assertNotIn("LastProfileSwitchTime", before)
        self.assertNotIn("CurrentProfileId", before)
        self.assertNotIn("OriginalProfileId", before)

        self.assertTrue(_migrate_v4_artist_profile_switch_columns(self.db))

        after = set(_get_table_columns(self.db, ArtistFilesModel._meta.table_name))
        self.assertIn("LastProfileSwitchTime", after)
        self.assertIn("CurrentProfileId", after)
        self.assertIn("OriginalProfileId", after)

    def test_idempotent_when_columns_already_present(self) -> None:
        self._create_legacy_artist_table()
        self.assertTrue(_migrate_v4_artist_profile_switch_columns(self.db))
        self.assertTrue(_migrate_v4_artist_profile_switch_columns(self.db))

    def test_apply_migrations_bumps_user_version_to_v4(self) -> None:
        self._create_legacy_artist_table()
        _set_db_schema_version(self.db, _DB_SCHEMA_VERSION_LIDARR_TRACK_DURATION_SECONDS)
        _apply_db_schema_migrations(self.db)
        self.assertEqual(
            _get_db_schema_version(self.db),
            _DB_SCHEMA_VERSION_ARTIST_PROFILE_SWITCH,
        )
        cols = set(_get_table_columns(self.db, ArtistFilesModel._meta.table_name))
        self.assertTrue(
            {"LastProfileSwitchTime", "CurrentProfileId", "OriginalProfileId"}.issubset(cols)
        )
