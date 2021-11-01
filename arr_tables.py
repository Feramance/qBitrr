from peewee import BooleanField, DateTimeField, IntegerField, Model, TextField


class CommandsModel(Model):
    Id = IntegerField()
    Name = TextField()
    Body = TextField()
    Priority = IntegerField()
    Status = IntegerField()
    QueuedAt = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    StartedAt = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    EndedAt = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    Duration = TextField()
    Exception = TextField()
    Trigger = TextField()


class MoviesModel(Model):
    Id = IntegerField()
    ImdbId = IntegerField()
    Title = TextField()
    TitleSlug = TextField()
    SortTitle = TextField()
    CleanTitle = TextField()
    Status = IntegerField()
    Overview = TextField()
    Images = TextField()
    Path = TextField()
    Monitored = BooleanField()
    ProfileId = IntegerField()
    LastInfoSync = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    LastDiskSync = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    Runtime = IntegerField()
    InCinemas = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    Year = IntegerField()
    Added = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    Ratings = TextField()
    Genres = TextField()
    Tags = TextField()
    Certification = TextField()
    AddOptions = TextField()
    MovieFileId = IntegerField()
    TmdbId = IntegerField()
    Website = TextField()
    PhysicalRelease = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])
    YouTubeTrailerId = TextField()
    Studio = TextField()
    MinimumAvailability = IntegerField()
    HasPreDBEntry = IntegerField()
    SecondaryYear = IntegerField()
    Collection = TextField()
    Recommendations = TextField()
    OriginalTitle = IntegerField()
    DigitalRelease = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])


class EpisodesModel(Model):

    Id = IntegerField(null=False, primary_key=True)
    SeriesId = IntegerField(null=False)
    SeasonNumber = IntegerField(null=False)
    EpisodeNumber = IntegerField(null=False)

    Title = TextField()
    Overview = TextField()

    EpisodeFileId = IntegerField()
    AbsoluteEpisodeNumber = IntegerField()
    SceneAbsoluteEpisodeNumber = IntegerField()
    SceneEpisodeNumber = IntegerField()
    SceneSeasonNumber = IntegerField()
    Monitored = BooleanField()

    AirDateUtc = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])

    AirDate = TextField()
    Ratings = TextField()
    Images = TextField()
    UnverifiedSceneNumbering = BooleanField(null=False, default=False)
    LastSearchTime = DateTimeField(formats=["%Y-%m-%d %H:%M:%S.%f"])

    AiredAfterSeasonNumber = IntegerField()
    AiredBeforeSeasonNumber = IntegerField()
    AiredBeforeEpisodeNumber = IntegerField()
