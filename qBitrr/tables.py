from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

from peewee import (
    BooleanField,
    CharField,
    DatabaseProxy,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

from qBitrr.home_path import APPDATA_FOLDER

DATABASE_FILE = APPDATA_FOLDER.joinpath("qbitrr.db")
_database_proxy: DatabaseProxy = DatabaseProxy()
_DATABASE: SqliteDatabase | None = None


class BaseModel(Model):
    class Meta:
        database = _database_proxy


def get_database() -> SqliteDatabase:
    global _DATABASE
    if _DATABASE is None:
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DATABASE = SqliteDatabase(
            str(DATABASE_FILE),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -64_000,
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 0,
            },
            timeout=15,
            check_same_thread=False,
        )
        _database_proxy.initialize(_DATABASE)
    _DATABASE.connect(reuse_if_open=True)
    return _DATABASE


def ensure_table_schema(model: type[BaseModel]) -> None:
    database = get_database()
    table_name = model._meta.table_name
    with database:
        database.create_tables([model], safe=True)
        existing_columns = {column.name for column in database.get_columns(table_name)}
        for field in model._meta.sorted_fields:
            column_name = field.column_name
            if column_name not in existing_columns:
                database.add_column(table_name, column_name, field)


class FilesQueued(BaseModel):
    EntryId = IntegerField(primary_key=True, null=False, unique=True)


class MoviesFilesModel(BaseModel):
    Title = CharField()
    Monitored = BooleanField()
    TmdbId = IntegerField()
    Year = IntegerField()
    EntryId = IntegerField(unique=True)
    Searched = BooleanField(default=False)
    MovieFileId = IntegerField()
    IsRequest = BooleanField(default=False)
    QualityMet = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    CustomFormatScore = IntegerField(null=True)
    MinCustomFormatScore = IntegerField(null=True)
    CustomFormatMet = BooleanField(default=False)
    Reason = TextField(null=True)


class EpisodeFilesModel(BaseModel):
    EntryId = IntegerField(primary_key=True)
    SeriesTitle = TextField(null=True)
    Title = TextField(null=True)
    SeriesId = IntegerField(null=False)
    EpisodeFileId = IntegerField(null=True)
    EpisodeNumber = IntegerField(null=False)
    SeasonNumber = IntegerField(null=False)
    AbsoluteEpisodeNumber = IntegerField(null=True)
    SceneAbsoluteEpisodeNumber = IntegerField(null=True)
    AirDateUtc = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)
    IsRequest = BooleanField(default=False)
    QualityMet = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    CustomFormatScore = IntegerField(null=True)
    MinCustomFormatScore = IntegerField(null=True)
    CustomFormatMet = BooleanField(default=False)
    Reason = TextField(null=True)


class SeriesFilesModel(BaseModel):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    MinCustomFormatScore = IntegerField(null=True)


class MovieQueueModel(BaseModel):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class EpisodeQueueModel(BaseModel):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class TorrentLibrary(BaseModel):
    Hash = TextField(null=False)
    Category = TextField(null=False)
    AllowedSeeding = BooleanField(default=False)
    Imported = BooleanField(default=False)
    AllowedStalled = BooleanField(default=False)
    FreeSpacePaused = BooleanField(default=False)

    class Meta:
        table_name = "torrent_library"


class SearchActivity(BaseModel):
    category = TextField(primary_key=True)
    summary = TextField(null=True)
    timestamp = TextField(null=True)

    class Meta:
        table_name = "search_activity"


class ArrTables(NamedTuple):
    files: type[BaseModel]
    queue: type[BaseModel]
    series: type[BaseModel] | None
    persisting_queue: type[BaseModel]
    torrents: type[BaseModel] | None


_SAFE_IDENTIFIER = re.compile(r"[^a-z0-9_]+")


def _sanitize_identifier(name: str) -> str:
    token = name.strip().lower().replace(" ", "_")
    token = _SAFE_IDENTIFIER.sub("_", token)
    token = token.strip("_")
    if not token:
        token = "arr"
    if token[0].isdigit():
        token = f"arr_{token}"
    return token


@lru_cache(maxsize=None)
def create_arr_tables(
    arr_name: str,
    arr_type: str,
    *,
    include_series: bool,
    include_torrents: bool,
) -> ArrTables:
    table_prefix = _sanitize_identifier(arr_name)
    files_base: type[BaseModel]
    queue_base: type[BaseModel]
    if arr_type.lower() == "sonarr":
        files_base = EpisodeFilesModel
        queue_base = EpisodeQueueModel
    elif arr_type.lower() == "radarr":
        files_base = MoviesFilesModel
        queue_base = MovieQueueModel
    else:
        raise ValueError(f"Unknown arr_type '{arr_type}'")

    class Files(files_base):
        class Meta:
            table_name = f"{table_prefix}_files"

    class Queue(queue_base):
        class Meta:
            table_name = f"{table_prefix}_queue"

    class PersistingQueue(FilesQueued):
        class Meta:
            table_name = f"{table_prefix}_persisting_queue"

    series_model: type[BaseModel] | None = None
    if include_series:

        class Series(SeriesFilesModel):
            class Meta:
                table_name = f"{table_prefix}_series"

        series_model = Series

    torrents_model: type[BaseModel] | None = TorrentLibrary if include_torrents else None

    ensure_table_schema(Files)
    ensure_table_schema(Queue)
    ensure_table_schema(PersistingQueue)
    if series_model is not None:
        ensure_table_schema(series_model)
    if torrents_model is not None:
        ensure_table_schema(torrents_model)

    return ArrTables(
        files=Files,
        queue=Queue,
        series=series_model,
        persisting_queue=PersistingQueue,
        torrents=torrents_model,
    )


def ensure_core_tables() -> None:
    ensure_table_schema(TorrentLibrary)
    ensure_table_schema(SearchActivity)
