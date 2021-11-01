from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    TextField,
)


class MoviesFilesModel(Model):
    Title = CharField()
    Monitored = BooleanField()
    TmdbId = IntegerField()
    Year = IntegerField()
    EntryId = IntegerField(unique=True)
    Searched = BooleanField(default=False)
    MovieFileId = IntegerField()
    Ombi = BooleanField(default=False)


class EpisodeFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    SeriesTitle = TextField(null=True)
    Title = TextField(null=True)
    SeriesId = IntegerField(null=False)
    EpisodeFileId = IntegerField(null=True)
    EpisodeNumber = IntegerField(null=False)
    SeasonNumber = IntegerField(null=False)
    AbsoluteEpisodeNumber = IntegerField(null=True)
    SceneAbsoluteEpisodeNumber = IntegerField(null=True)
    LastSearchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    AirDateUtc = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)
    Ombi = BooleanField(default=False)


class Series(Model):
    Title = TextField()
    EpisodeCount = IntegerField()
    EpisodeFileCount = IntegerField()
    Monitored = BooleanField()
    TvdbId = IntegerField()
    EntryId = IntegerField(unique=True)
    Searched = BooleanField(default=False)


class MovieQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class EpisodeQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)
