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
    Upgrade = BooleanField(default=False)
    CustomFormatScore = IntegerField(null=True)
    MinCustomFormatScore = IntegerField(null=True)
    CustomFormatMet = BooleanField(default=False)
    Reason = TextField(null=True)
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)
    # Profile switching state tracking
    LastProfileSwitchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    CurrentProfileId = IntegerField(null=True)
    OriginalProfileId = IntegerField(null=True)


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
    # Profile switching state tracking
    LastProfileSwitchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    CurrentProfileId = IntegerField(null=True)
    OriginalProfileId = IntegerField(null=True)


class SeriesFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    MinCustomFormatScore = IntegerField(null=True)
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)


class MovieQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class EpisodeQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class AlbumFilesModel(Model):
    Title = CharField()
    Monitored = BooleanField()
    ForeignAlbumId = CharField()
    ReleaseDate = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    EntryId = IntegerField(unique=True)
    Searched = BooleanField(default=False)
    AlbumFileId = IntegerField()
    IsRequest = BooleanField(default=False)
    QualityMet = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    CustomFormatScore = IntegerField(null=True)
    MinCustomFormatScore = IntegerField(null=True)
    CustomFormatMet = BooleanField(default=False)
    Reason = TextField(null=True)
    ArtistId = IntegerField(null=False)
    ArtistTitle = TextField(null=True)
    # Profile switching state tracking
    LastProfileSwitchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    CurrentProfileId = IntegerField(null=True)
    OriginalProfileId = IntegerField(null=True)


class TrackFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    AlbumId = IntegerField(null=False)
    TrackNumber = IntegerField(null=True)
    Title = TextField(null=True)
    Duration = IntegerField(null=True)  # Duration in seconds
    HasFile = BooleanField(default=False)
    TrackFileId = IntegerField(null=True)
    Monitored = BooleanField(default=False)


class ArtistFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    Searched = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    MinCustomFormatScore = IntegerField(null=True)
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)


class AlbumQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)


class TorrentLibrary(Model):
    Hash = TextField(null=False)
    Category = TextField(null=False)
    AllowedSeeding = BooleanField(default=False)
    Imported = BooleanField(default=False)
    AllowedStalled = BooleanField(default=False)
    FreeSpacePaused = BooleanField(default=False)
