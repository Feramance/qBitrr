from peewee import BooleanField, CharField, DateTimeField, IntegerField, Model, TextField


class FilesQueued(Model):
    EntryId = IntegerField(primary_key=True, null=False, unique=True)
    ArrInstance = CharField(null=True, default="")


class MoviesFilesModel(Model):
    Title = CharField()
    Monitored = BooleanField()
    TmdbId = IntegerField()
    Year = IntegerField()
    ArrInstance = CharField(null=True, default="")
    EntryId = IntegerField(primary_key=True)
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
    ArrInstance = CharField(null=True, default="")
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
    # Quality profile from Arr API (inherited from series)
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)
    # Profile switching state tracking
    LastProfileSwitchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    CurrentProfileId = IntegerField(null=True)
    OriginalProfileId = IntegerField(null=True)


class SeriesFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    ArrInstance = CharField(null=True, default="")
    Searched = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    MinCustomFormatScore = IntegerField(null=True)
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)


class MovieQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)
    ArrInstance = CharField(null=True, default="")


class EpisodeQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)
    ArrInstance = CharField(null=True, default="")


class AlbumFilesModel(Model):
    Title = CharField()
    Monitored = BooleanField()
    ForeignAlbumId = CharField()
    ReleaseDate = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    EntryId = IntegerField(primary_key=True)
    ArrInstance = CharField(null=True, default="")
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
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)
    # Profile switching state tracking
    LastProfileSwitchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"], null=True)
    CurrentProfileId = IntegerField(null=True)
    OriginalProfileId = IntegerField(null=True)


class TrackFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    AlbumId = IntegerField(null=False)
    TrackNumber = IntegerField(null=True)
    Title = TextField(null=True)
    ArrInstance = CharField(null=True, default="")
    Duration = IntegerField(null=True)  # Duration in seconds
    HasFile = BooleanField(default=False)
    TrackFileId = IntegerField(null=True)
    Monitored = BooleanField(default=False)


class ArtistFilesModel(Model):
    EntryId = IntegerField(primary_key=True)
    Title = TextField(null=True)
    Monitored = BooleanField(null=True)
    ArrInstance = CharField(null=True, default="")
    Searched = BooleanField(default=False)
    Upgrade = BooleanField(default=False)
    MinCustomFormatScore = IntegerField(null=True)
    # Quality profile from Arr API
    QualityProfileId = IntegerField(null=True)
    QualityProfileName = TextField(null=True)


class AlbumQueueModel(Model):
    EntryId = IntegerField(unique=True)
    Completed = BooleanField(default=False)
    ArrInstance = CharField(null=True, default="")


class TorrentLibrary(Model):
    Hash = TextField(null=False)
    Category = TextField(null=False)
    QbitInstance = TextField(
        null=False, default="default"
    )  # Multi-qBit v3.0: Track which instance
    ArrInstance = CharField(null=True, default="")
    AllowedSeeding = BooleanField(default=False)
    Imported = BooleanField(default=False)
    AllowedStalled = BooleanField(default=False)
    FreeSpacePaused = BooleanField(default=False)

    class Meta:
        # Multi-qBit v3.0: Compound unique constraint (same hash can exist on different instances)
        indexes = ((("Hash", "QbitInstance"), True),)  # Unique constraint on (Hash, QbitInstance)
