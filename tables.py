from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    TextField,
)


class MoviesFilesModel(Model):
    title = CharField()
    monitored = BooleanField()
    TmdbId = IntegerField()
    year = IntegerField()
    EntryId = IntegerField(unique=True)
    searched = BooleanField(default=False)
    MovieFileId = IntegerField()


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
    searched = BooleanField(default=False)


class MovieQueueModel(Model):
    EntryId = IntegerField(unique=True)
    completed = BooleanField(default=False)


class EpisodeQueueModel(Model):
    EntryId = IntegerField(unique=True)
    completed = BooleanField(default=False)
