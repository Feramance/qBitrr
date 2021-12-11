from peewee import BooleanField, CharField, DateTimeField, IntegerField, Model, TextField


class FilesQueued(Model):
    EntryId = IntegerField(primary_key=True, null=False, unique=True)


class MoviesFilesModel(Model):
    Title = CharField()
    Monitored = BooleanField()
    TmdbId = IntegerField()
    Year = IntegerField()
    EntryId = IntegerField(unique=True)
    Searched = BooleanField(default=False)
    MovieFileId = IntegerField()
    IsRequest = BooleanField(default=False)
    QualityMet = BooleanField(default=False)


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
    IsRequest = BooleanField(default=False)
    QualityMet = BooleanField(default=False)


class SeriesFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)


class MovieQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class EpisodeQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)
