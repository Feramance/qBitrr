"""Per-Arr-type database update handlers (split from Arr.db_update_single_series)."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from qBitrr.arss._shared import *

if TYPE_CHECKING:
    from qBitrr.arss.arr import Arr


def db_update_single_series(
    arr: Arr,
    db_entry: JsonObject = None,
    request: bool = False,
    series: bool = False,
    artist: bool = False,
) -> None:
    if not (
        arr.search_missing
        or arr.do_upgrade_search
        or arr.quality_unmet_search
        or arr.custom_format_unmet_search
    ):
        return
    try:
        searched = False
        if arr.type == "sonarr":
            if not series:
                arr.model_file: EpisodeFilesModel
                episodeData = arr.model_file.get_or_none(
                    (arr.model_file.EntryId == db_entry["id"])
                    & (arr.model_file.ArrInstance == arr._name)
                )
                episode = with_retry(
                    lambda: arr.client.episode.get(item_id=db_entry["id"]),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )

                # Validate episode object has required fields
                if not episode or not isinstance(episode, dict):
                    arr.logger.warning(
                        "Invalid episode object returned from API for episode ID %s: %s",
                        db_entry.get("id"),
                        type(episode).__name__,
                    )
                    return

                required_fields = [
                    "id",
                    "seriesId",
                    "seasonNumber",
                    "episodeNumber",
                    "title",
                    "airDateUtc",
                    "episodeFileId",
                ]
                missing_fields = [field for field in required_fields if field not in episode]
                if missing_fields:
                    arr.logger.warning(
                        "Episode %s missing required fields %s. Episode data: %s",
                        db_entry.get("id"),
                        missing_fields,
                        episode,
                    )
                    return

                if episode.get("monitored", True) or arr.search_unmonitored:
                    series_info = episode.get("series") or {}
                    if isinstance(series_info, dict):
                        quality_profile_id = series_info.get("qualityProfileId")
                    else:
                        quality_profile_id = getattr(series_info, "qualityProfileId", None)
                    if not quality_profile_id:
                        quality_profile_id = db_entry.get("qualityProfileId")
                    minCustomFormat = (
                        getattr(episodeData, "MinCustomFormatScore", 0) if episodeData else 0
                    )
                    if not minCustomFormat:
                        if quality_profile_id:
                            profile = (
                                with_retry(
                                    lambda qpid=quality_profile_id: arr.client.quality_profile.get(
                                        item_id=qpid
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_ARR_RETRY_EXCEPTIONS,
                                )
                                or {}
                            )
                            minCustomFormat = profile.get("minFormatScore") or 0
                        else:
                            arr.logger.warning(
                                "Episode %s missing qualityProfileId; defaulting custom format threshold to 0",
                                episode.get("id"),
                            )
                            minCustomFormat = 0
                    episode_file = episode.get("episodeFile") or {}
                    if isinstance(episode_file, dict):
                        episode_file_id = episode_file.get("id")
                    else:
                        episode_file_id = getattr(episode_file, "id", None)
                    has_file = bool(episode.get("hasFile"))
                    episode_data_file_id = (
                        getattr(episodeData, "EpisodeFileId", None) if episodeData else None
                    )
                    if has_file and episode_file_id:
                        if episode_data_file_id and episode_file_id == episode_data_file_id:
                            customFormat = getattr(episodeData, "CustomFormatScore", 0)
                        else:
                            file_info = (
                                with_retry(
                                    lambda efid=episode_file_id: arr.client.episode_file.get(
                                        item_id=efid
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_ARR_RETRY_EXCEPTIONS,
                                )
                                or {}
                            )
                            customFormat = file_info.get("customFormatScore") or 0
                    else:
                        customFormat = 0

                    QualityUnmet = (
                        episode["episodeFile"]["qualityCutoffNotMet"]
                        if "episodeFile" in episode
                        else False
                    )
                    if (
                        episode.get("hasFile", False)
                        and not (arr.quality_unmet_search and QualityUnmet)
                        and not (arr.custom_format_unmet_search and customFormat < minCustomFormat)
                    ):
                        searched = True
                        arr.model_queue.update(Completed=True).where(
                            (arr.model_queue.EntryId == episode["id"])
                            & (arr.model_queue.ArrInstance == arr._name)
                        ).execute()

                    if arr.use_temp_for_missing:
                        data = None
                        profile_switch_timestamp = None
                        original_profile_for_db = None
                        current_profile_for_db = None
                        # Only apply temp profiles for truly missing content (no file)
                        # Do NOT apply for quality/custom format unmet or upgrade searches
                        has_file = episode.get("hasFile", False)

                        arr.logger.trace(
                            "Temp quality profile check for '%s': searched=%s, has_file=%s, current_profile_id=%s, keep_temp=%s",
                            db_entry.get("title", "Unknown"),
                            searched,
                            has_file,
                            quality_profile_id,
                            arr.keep_temp_profile,
                        )
                        if (
                            searched
                            and quality_profile_id in arr.main_quality_profile_ids.keys()
                            and not arr.keep_temp_profile
                        ):
                            new_profile_id = arr.main_quality_profile_ids.get(quality_profile_id)
                            if new_profile_id is None:
                                arr.logger.warning(
                                    f"Profile ID {quality_profile_id} not found in current temp→main mappings. "
                                    "Config may have changed. Skipping profile upgrade."
                                )
                            else:
                                data: JsonObject = {"qualityProfileId": new_profile_id}
                                arr.logger.info(
                                    "Upgrading quality profile for '%s': temp profile (ID:%s) → main profile (ID:%s) [Episode searched, reverting to main]",
                                    db_entry.get("title", "Unknown"),
                                    quality_profile_id,
                                    new_profile_id,
                                )
                                profile_switch_timestamp = datetime.now()
                                original_profile_for_db = None
                                current_profile_for_db = None
                        elif (
                            not searched
                            and not has_file
                            and quality_profile_id in arr.temp_quality_profile_ids.keys()
                        ):
                            new_profile_id = arr.temp_quality_profile_ids[quality_profile_id]
                            data: JsonObject = {"qualityProfileId": new_profile_id}
                            arr.logger.info(
                                "Downgrading quality profile for '%s': main profile (ID:%s) → temp profile (ID:%s) [Episode not searched yet]",
                                db_entry.get("title", "Unknown"),
                                quality_profile_id,
                                new_profile_id,
                            )
                            # Downgrading to temp - track original and switch time
                            profile_switch_timestamp = datetime.now()
                            original_profile_for_db = quality_profile_id
                            current_profile_for_db = new_profile_id
                        else:
                            arr.logger.trace(
                                "No quality profile change for '%s': searched=%s, profile_id=%s (in_temps=%s, in_mains=%s)",
                                db_entry.get("title", "Unknown"),
                                searched,
                                quality_profile_id,
                                quality_profile_id in arr.temp_quality_profile_ids.values(),
                                quality_profile_id in arr.temp_quality_profile_ids.keys(),
                            )
                        if data:
                            profile_update_success = arr._retry_profile_switch_update(
                                lambda: arr.client.episode.update(
                                    item_id=episode["id"], data=data
                                ),
                                "episode",
                            )

                            # If profile update failed, don't track the change
                            if not profile_update_success:
                                profile_switch_timestamp = None
                                original_profile_for_db = None
                                current_profile_for_db = None

                    EntryId = episode.get("id")
                    SeriesTitle = episode.get("series", {}).get("title")
                    SeasonNumber = episode.get("seasonNumber")
                    Title = episode.get("title")
                    SeriesId = episode.get("seriesId")
                    EpisodeFileId = episode.get("episodeFileId")
                    EpisodeNumber = episode.get("episodeNumber")
                    AbsoluteEpisodeNumber = (
                        episode.get("absoluteEpisodeNumber")
                        if "absoluteEpisodeNumber" in episode
                        else None
                    )
                    SceneAbsoluteEpisodeNumber = (
                        episode.get("sceneAbsoluteEpisodeNumber")
                        if "sceneAbsoluteEpisodeNumber" in episode
                        else None
                    )
                    AirDateUtc = episode.get("airDateUtc")
                    Monitored = episode.get("monitored", True)
                    QualityMet = not QualityUnmet if db_entry["hasFile"] else False
                    customFormatMet = customFormat >= minCustomFormat

                    if not episode.get("hasFile", False):
                        # Episode is missing a file - always mark as Missing
                        reason = "Missing"
                    elif arr.quality_unmet_search and QualityUnmet:
                        reason = "Quality"
                    elif arr.custom_format_unmet_search and not customFormatMet:
                        reason = "CustomFormat"
                    elif arr.do_upgrade_search:
                        reason = "Upgrade"
                    elif searched:
                        # Episode has file and search is complete
                        reason = "Not being searched"
                    else:
                        reason = "Not being searched"

                    to_update = {
                        arr.model_file.Monitored: Monitored,
                        arr.model_file.Title: Title,
                        arr.model_file.AirDateUtc: AirDateUtc,
                        arr.model_file.SceneAbsoluteEpisodeNumber: SceneAbsoluteEpisodeNumber,
                        arr.model_file.AbsoluteEpisodeNumber: AbsoluteEpisodeNumber,
                        arr.model_file.EpisodeNumber: EpisodeNumber,
                        arr.model_file.EpisodeFileId: EpisodeFileId,
                        arr.model_file.SeriesId: SeriesId,
                        arr.model_file.SeriesTitle: SeriesTitle,
                        arr.model_file.SeasonNumber: SeasonNumber,
                        arr.model_file.QualityMet: QualityMet,
                        arr.model_file.Upgrade: False,
                        arr.model_file.Searched: searched,
                        arr.model_file.MinCustomFormatScore: minCustomFormat,
                        arr.model_file.CustomFormatScore: customFormat,
                        arr.model_file.CustomFormatMet: customFormatMet,
                        arr.model_file.Reason: reason,
                    }

                    # Add profile tracking fields if temp profile feature is enabled
                    if arr.use_temp_for_missing and profile_switch_timestamp is not None:
                        to_update[arr.model_file.LastProfileSwitchTime] = profile_switch_timestamp
                        to_update[arr.model_file.OriginalProfileId] = original_profile_for_db
                        to_update[arr.model_file.CurrentProfileId] = current_profile_for_db

                    arr.logger.debug(
                        "Updating database entry | %s | S%02dE%03d [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                        SeriesTitle.ljust(60, "."),
                        SeasonNumber,
                        EpisodeNumber,
                        str(searched).ljust(5),
                        str(False).ljust(5),
                        str(QualityMet).ljust(5),
                        str(customFormatMet).ljust(5),
                    )

                    if request:
                        to_update[arr.model_file.IsRequest] = request

                    db_commands = arr.model_file.insert(
                        EntryId=EntryId,
                        Title=Title,
                        SeriesId=SeriesId,
                        EpisodeFileId=EpisodeFileId,
                        EpisodeNumber=EpisodeNumber,
                        AbsoluteEpisodeNumber=AbsoluteEpisodeNumber,
                        SceneAbsoluteEpisodeNumber=SceneAbsoluteEpisodeNumber,
                        AirDateUtc=AirDateUtc,
                        Monitored=Monitored,
                        SeriesTitle=SeriesTitle,
                        SeasonNumber=SeasonNumber,
                        Searched=searched,
                        IsRequest=request,
                        QualityMet=QualityMet,
                        Upgrade=False,
                        MinCustomFormatScore=minCustomFormat,
                        CustomFormatScore=customFormat,
                        CustomFormatMet=customFormatMet,
                        Reason=reason,
                        ArrInstance=arr._name,
                    ).on_conflict(
                        conflict_target=[arr.model_file.EntryId, arr.model_file.ArrInstance],
                        update=to_update,
                    )
                    db_commands.execute()
                else:
                    db_commands = arr.model_file.delete().where(
                        (arr.model_file.EntryId == episode["id"])
                        & (arr.model_file.ArrInstance == arr._name)
                    )
                    db_commands.execute()
            else:
                arr.series_file_model: SeriesFilesModel
                EntryId = db_entry["id"]
                seriesData = arr.series_file_model.get_or_none(
                    (arr.series_file_model.EntryId == EntryId)
                    & (arr.series_file_model.ArrInstance == arr._name)
                )
                if db_entry["monitored"] or arr.search_unmonitored:
                    seriesMetadata = (
                        with_retry(
                            lambda eid=EntryId: arr.client.series.get(item_id=eid),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_ARR_RETRY_EXCEPTIONS,
                        )
                        or {}
                    )
                    quality_profile_id = None
                    if isinstance(seriesMetadata, dict):
                        quality_profile_id = seriesMetadata.get("qualityProfileId")
                    else:
                        quality_profile_id = getattr(seriesMetadata, "qualityProfileId", None)
                    if not seriesData:
                        if quality_profile_id:
                            profile = (
                                with_retry(
                                    lambda qpid=quality_profile_id: arr.client.quality_profile.get(
                                        item_id=qpid
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_ARR_RETRY_EXCEPTIONS,
                                )
                                or {}
                            )
                            minCustomFormat = profile.get("minFormatScore") or 0
                        else:
                            arr.logger.warning(
                                "Series %s (%s) missing qualityProfileId; "
                                "defaulting custom format score to 0",
                                db_entry.get("title"),
                                EntryId,
                            )
                            minCustomFormat = 0
                    else:
                        minCustomFormat = getattr(seriesData, "MinCustomFormatScore", 0)
                    episodeCount = 0
                    episodeFileCount = 0
                    totalEpisodeCount = 0
                    monitoredEpisodeCount = 0
                    seasons = seriesMetadata.get("seasons")
                    for season in seasons or ():
                        sdict = dict(season)
                        if sdict.get("seasonNumber") == 0:
                            statistics = sdict.get("statistics") or {}
                            monitoredEpisodeCount = monitoredEpisodeCount + (
                                statistics.get("episodeCount") or 0
                            )
                            totalEpisodeCount = totalEpisodeCount + (
                                statistics.get("totalEpisodeCount") or 0
                            )
                            episodeFileCount = episodeFileCount + (
                                statistics.get("episodeFileCount") or 0
                            )
                        else:
                            statistics = sdict.get("statistics") or {}
                            episodeCount = episodeCount + (statistics.get("episodeCount") or 0)
                            totalEpisodeCount = totalEpisodeCount + (
                                statistics.get("totalEpisodeCount") or 0
                            )
                            episodeFileCount = episodeFileCount + (
                                statistics.get("episodeFileCount") or 0
                            )
                    if arr.search_specials:
                        searched = totalEpisodeCount == episodeFileCount
                    else:
                        searched = (episodeCount + monitoredEpisodeCount) == episodeFileCount
                    # Sonarr series-level temp profile logic
                    # NOTE: Sonarr only supports quality profiles at the series level (not episode level).
                    # Individual episodes inherit the series profile. This is intentional and correct.
                    # If ANY episodes are missing, the entire series uses temp profile to maximize
                    # the chance of finding missing content (priority #1).
                    if arr.use_temp_for_missing:
                        profile_changed = False
                        try:
                            quality_profile_id = db_entry.get("qualityProfileId")
                            if (
                                searched
                                and quality_profile_id in arr.main_quality_profile_ids.keys()
                                and not arr.keep_temp_profile
                            ):
                                new_main_id = arr.main_quality_profile_ids[quality_profile_id]
                                db_entry["qualityProfileId"] = new_main_id
                                profile_changed = True
                                arr.logger.debug(
                                    "Updating quality profile for %s to %s",
                                    db_entry["title"],
                                    new_main_id,
                                )
                            elif (
                                not searched
                                and quality_profile_id in arr.temp_quality_profile_ids.keys()
                            ):
                                new_temp_id = arr.temp_quality_profile_ids[quality_profile_id]
                                db_entry["qualityProfileId"] = new_temp_id
                                profile_changed = True
                                arr.logger.debug(
                                    "Updating quality profile for %s to %s",
                                    db_entry["title"],
                                    new_temp_id,
                                )
                        except KeyError:
                            arr.logger.warning(
                                "Check quality profile settings for %s", db_entry["title"]
                            )
                        if profile_changed:
                            arr._retry_profile_switch_update(
                                lambda: arr.client.series.update(data=db_entry),
                                "series",
                            )

                    Title = seriesMetadata.get("title")
                    Monitored = db_entry["monitored"]

                    # Get quality profile info
                    qualityProfileName = None
                    if quality_profile_id:
                        try:
                            if quality_profile_id not in arr._quality_profile_cache:
                                profile = arr.client.quality_profile.get(
                                    item_id=quality_profile_id
                                )
                                arr._quality_profile_cache[quality_profile_id] = profile
                            qualityProfileName = arr._quality_profile_cache[
                                quality_profile_id
                            ].get("name")
                        except Exception:
                            pass

                    to_update = {
                        arr.series_file_model.Monitored: Monitored,
                        arr.series_file_model.Title: Title,
                        arr.series_file_model.Searched: searched,
                        arr.series_file_model.Upgrade: False,
                        arr.series_file_model.MinCustomFormatScore: minCustomFormat,
                        arr.series_file_model.QualityProfileId: quality_profile_id,
                        arr.series_file_model.QualityProfileName: qualityProfileName,
                    }

                    arr.logger.debug(
                        "Updating database entry | %s [Searched:%s][Upgrade:%s]",
                        Title.ljust(60, "."),
                        str(searched).ljust(5),
                        str(False).ljust(5),
                    )

                    db_commands = arr.series_file_model.insert(
                        EntryId=EntryId,
                        Title=Title,
                        Searched=searched,
                        Monitored=Monitored,
                        Upgrade=False,
                        MinCustomFormatScore=minCustomFormat,
                        QualityProfileId=quality_profile_id,
                        QualityProfileName=qualityProfileName,
                        ArrInstance=arr._name,
                    ).on_conflict(
                        conflict_target=[
                            arr.series_file_model.EntryId,
                            arr.series_file_model.ArrInstance,
                        ],
                        update=to_update,
                    )
                    db_commands.execute()

                    # Note: Episodes are now handled separately in db_update()
                    # No need to recursively process episodes here to avoid duplication
                else:
                    db_commands = arr.series_file_model.delete().where(
                        (arr.series_file_model.EntryId == EntryId)
                        & (arr.series_file_model.ArrInstance == arr._name)
                    )
                    db_commands.execute()

        elif arr.type == "radarr":
            arr.model_file: MoviesFilesModel
            searched = False
            movieData = arr.model_file.get_or_none(
                (arr.model_file.EntryId == db_entry["id"])
                & (arr.model_file.ArrInstance == arr._name)
            )
            if arr.minimum_availability_check(db_entry) and (
                db_entry["monitored"] or arr.search_unmonitored
            ):
                _retry_exc = (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                )
                if movieData:
                    if not movieData.MinCustomFormatScore:
                        profile = (
                            with_retry(
                                lambda: arr.client.quality_profile.get(
                                    item_id=db_entry["qualityProfileId"]
                                ),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_retry_exc,
                            )
                            or {}
                        )
                        minCustomFormat = profile.get("minFormatScore", 0)
                    else:
                        minCustomFormat = movieData.MinCustomFormatScore
                    if db_entry["hasFile"]:
                        if db_entry["movieFile"]["id"] != movieData.MovieFileId:
                            customFormat = with_retry(
                                lambda: arr.client.movie_file.get(
                                    item_id=db_entry["movieFile"]["id"]
                                ),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_retry_exc,
                            )["customFormatScore"]
                        else:
                            customFormat = movieData.CustomFormatScore
                    else:
                        customFormat = 0
                else:
                    profile = (
                        with_retry(
                            lambda: arr.client.quality_profile.get(
                                item_id=db_entry["qualityProfileId"]
                            ),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_retry_exc,
                        )
                        or {}
                    )
                    minCustomFormat = profile.get("minFormatScore", 0)
                    if db_entry["hasFile"]:
                        customFormat = with_retry(
                            lambda: arr.client.movie_file.get(item_id=db_entry["movieFile"]["id"]),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_retry_exc,
                        ).get("customFormatScore", 0)
                    else:
                        customFormat = 0
                QualityUnmet = (
                    db_entry["movieFile"]["qualityCutoffNotMet"]
                    if "movieFile" in db_entry
                    else False
                )
                if (
                    db_entry["hasFile"]
                    and not (arr.quality_unmet_search and QualityUnmet)
                    and not (arr.custom_format_unmet_search and customFormat < minCustomFormat)
                ):
                    searched = True
                    arr.model_queue.update(Completed=True).where(
                        (arr.model_queue.EntryId == db_entry["id"])
                        & (arr.model_queue.ArrInstance == arr._name)
                    ).execute()

                profile_switch_timestamp = None
                original_profile_for_db = None
                current_profile_for_db = None

                if arr.use_temp_for_missing:
                    quality_profile_id = db_entry.get("qualityProfileId")
                    has_file = db_entry.get("hasFile", False)
                    profile_update_needed = False
                    if (
                        searched
                        and quality_profile_id in arr.main_quality_profile_ids.keys()
                        and not arr.keep_temp_profile
                    ):
                        new_main_id = arr.main_quality_profile_ids[quality_profile_id]
                        db_entry["qualityProfileId"] = new_main_id
                        profile_update_needed = True
                        arr.logger.debug(
                            "Updating quality profile for %s to %s",
                            db_entry["title"],
                            new_main_id,
                        )
                        profile_switch_timestamp = datetime.now()
                        original_profile_for_db = None
                        current_profile_for_db = None
                    elif (
                        not searched
                        and not has_file
                        and quality_profile_id in arr.temp_quality_profile_ids.keys()
                    ):
                        new_temp_id = arr.temp_quality_profile_ids[quality_profile_id]
                        db_entry["qualityProfileId"] = new_temp_id
                        profile_update_needed = True
                        arr.logger.debug(
                            "Updating quality profile for %s to %s",
                            db_entry["title"],
                            new_temp_id,
                        )
                        profile_switch_timestamp = datetime.now()
                        original_profile_for_db = quality_profile_id
                        current_profile_for_db = new_temp_id

                    if profile_update_needed:
                        profile_update_success = arr._retry_profile_switch_update(
                            lambda: arr.client.movie.update(data=db_entry),
                            "movie",
                        )

                        if not profile_update_success:
                            profile_switch_timestamp = None
                            original_profile_for_db = None
                            current_profile_for_db = None

                title = db_entry["title"]
                monitored = db_entry["monitored"]
                tmdbId = db_entry["tmdbId"]
                year = db_entry["year"]
                entryId = db_entry["id"]
                movieFileId = db_entry["movieFileId"]
                qualityMet = not QualityUnmet if db_entry["hasFile"] else False
                customFormatMet = customFormat >= minCustomFormat

                # Get quality profile info
                qualityProfileId = db_entry.get("qualityProfileId")
                qualityProfileName = None
                if qualityProfileId:
                    try:
                        if qualityProfileId not in arr._quality_profile_cache:
                            profile = arr.client.quality_profile.get(item_id=qualityProfileId)
                            arr._quality_profile_cache[qualityProfileId] = profile
                        qualityProfileName = arr._quality_profile_cache[qualityProfileId].get(
                            "name"
                        )
                    except Exception:
                        pass

                if not db_entry["hasFile"]:
                    # Movie is missing a file - always mark as Missing
                    reason = "Missing"
                elif arr.quality_unmet_search and QualityUnmet:
                    reason = "Quality"
                elif arr.custom_format_unmet_search and not customFormatMet:
                    reason = "CustomFormat"
                elif arr.do_upgrade_search:
                    reason = "Upgrade"
                elif searched:
                    # Movie has file and search is complete
                    reason = "Not being searched"
                else:
                    reason = "Not being searched"

                to_update = {
                    arr.model_file.MovieFileId: movieFileId,
                    arr.model_file.Monitored: monitored,
                    arr.model_file.QualityMet: qualityMet,
                    arr.model_file.Searched: searched,
                    arr.model_file.Upgrade: False,
                    arr.model_file.MinCustomFormatScore: minCustomFormat,
                    arr.model_file.CustomFormatScore: customFormat,
                    arr.model_file.CustomFormatMet: customFormatMet,
                    arr.model_file.Reason: reason,
                    arr.model_file.QualityProfileId: qualityProfileId,
                    arr.model_file.QualityProfileName: qualityProfileName,
                }

                # Add profile tracking fields if temp profile feature is enabled
                if arr.use_temp_for_missing and profile_switch_timestamp is not None:
                    to_update[arr.model_file.LastProfileSwitchTime] = profile_switch_timestamp
                    to_update[arr.model_file.OriginalProfileId] = original_profile_for_db
                    to_update[arr.model_file.CurrentProfileId] = current_profile_for_db

                if request:
                    to_update[arr.model_file.IsRequest] = request

                arr.logger.debug(
                    "Updating database entry | %s [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                    title.ljust(60, "."),
                    str(searched).ljust(5),
                    str(False).ljust(5),
                    str(qualityMet).ljust(5),
                    str(customFormatMet).ljust(5),
                )

                db_commands = arr.model_file.insert(
                    Title=title,
                    Monitored=monitored,
                    TmdbId=tmdbId,
                    Year=year,
                    EntryId=entryId,
                    Searched=searched,
                    MovieFileId=movieFileId,
                    IsRequest=request,
                    QualityMet=qualityMet,
                    Upgrade=False,
                    MinCustomFormatScore=minCustomFormat,
                    CustomFormatScore=customFormat,
                    CustomFormatMet=customFormatMet,
                    Reason=reason,
                    QualityProfileId=qualityProfileId,
                    QualityProfileName=qualityProfileName,
                    ArrInstance=arr._name,
                ).on_conflict(
                    conflict_target=[arr.model_file.EntryId, arr.model_file.ArrInstance],
                    update=to_update,
                )
                db_commands.execute()
            else:
                db_commands = arr.model_file.delete().where(
                    (arr.model_file.EntryId == db_entry["id"])
                    & (arr.model_file.ArrInstance == arr._name)
                )
                db_commands.execute()
        elif arr.type == "lidarr":
            if not artist:
                # Album handling
                arr.model_file: AlbumFilesModel
                searched = False
                albumData = arr.model_file.get_or_none(
                    (arr.model_file.EntryId == db_entry["id"])
                    & (arr.model_file.ArrInstance == arr._name)
                )
                if db_entry["monitored"] or arr.search_unmonitored:
                    _retry_exc = (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    )
                    if albumData:
                        if not albumData.MinCustomFormatScore:
                            try:
                                profile_id = db_entry["profileId"]
                                if profile_id in arr._invalid_quality_profiles:
                                    minCustomFormat = 0
                                elif profile_id in arr._quality_profile_cache:
                                    minCustomFormat = arr._quality_profile_cache[profile_id].get(
                                        "minFormatScore", 0
                                    )
                                else:
                                    try:
                                        profile = with_retry(
                                            lambda pid=profile_id: arr.client.quality_profile.get(
                                                item_id=pid
                                            ),
                                            retries=5,
                                            backoff=0.5,
                                            max_backoff=5,
                                            exceptions=_retry_exc,
                                        )
                                        arr._quality_profile_cache[profile_id] = profile
                                        minCustomFormat = profile.get("minFormatScore", 0)
                                    except PyarrResourceNotFound:
                                        arr._invalid_quality_profiles.add(profile_id)
                                        arr.logger.warning(
                                            "Quality profile %s not found for album %s, defaulting to 0",
                                            db_entry.get("profileId"),
                                            db_entry.get("title", "Unknown"),
                                        )
                                        minCustomFormat = 0
                            except Exception:
                                minCustomFormat = 0
                        else:
                            minCustomFormat = albumData.MinCustomFormatScore
                        if db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100:
                            albumFileId = db_entry.get("statistics", {}).get("sizeOnDisk", 0)
                            if albumFileId != albumData.AlbumFileId:
                                customFormat = 0  # Lidarr may not have customFormatScore
                            else:
                                customFormat = albumData.CustomFormatScore
                        else:
                            customFormat = 0
                    else:
                        try:
                            profile_id = db_entry["profileId"]
                            if profile_id in arr._invalid_quality_profiles:
                                minCustomFormat = 0
                            elif profile_id in arr._quality_profile_cache:
                                minCustomFormat = arr._quality_profile_cache[profile_id].get(
                                    "minFormatScore", 0
                                )
                            else:
                                try:
                                    profile = with_retry(
                                        lambda pid=profile_id: arr.client.quality_profile.get(
                                            item_id=pid
                                        ),
                                        retries=5,
                                        backoff=0.5,
                                        max_backoff=5,
                                        exceptions=_retry_exc,
                                    )
                                    arr._quality_profile_cache[profile_id] = profile
                                    minCustomFormat = profile.get("minFormatScore", 0)
                                except PyarrResourceNotFound:
                                    arr._invalid_quality_profiles.add(profile_id)
                                    arr.logger.warning(
                                        "Quality profile %s not found for album %s, defaulting to 0",
                                        db_entry.get("profileId"),
                                        db_entry.get("title", "Unknown"),
                                    )
                                    minCustomFormat = 0
                        except Exception:
                            minCustomFormat = 0
                        if db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100:
                            customFormat = 0  # Lidarr may not have customFormatScore
                        else:
                            customFormat = 0

                    # Determine if album has all tracks
                    hasAllTracks = db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100

                    # Check if quality cutoff is met for Lidarr
                    # Unlike Sonarr/Radarr which have a qualityCutoffNotMet boolean field,
                    # Lidarr requires us to check the track file quality against the profile cutoff
                    QualityUnmet = False
                    if hasAllTracks:
                        try:
                            # Get the artist's quality profile to find the cutoff
                            artist_id = db_entry.get("artistId")
                            artist_data = arr.client.artist.get(item_id=artist_id)
                            profile_id = artist_data.get("qualityProfileId")

                            if profile_id:
                                # Get or use cached profile
                                if profile_id in arr._quality_profile_cache:
                                    profile = arr._quality_profile_cache[profile_id]
                                else:
                                    profile = arr.client.quality_profile.get(item_id=profile_id)
                                    arr._quality_profile_cache[profile_id] = profile

                                cutoff_quality_id = profile.get("cutoff")
                                upgrade_allowed = profile.get("upgradeAllowed", False)

                                if cutoff_quality_id and upgrade_allowed:
                                    # Resolve album track-file ids first, then query track files by ids.
                                    album_id = db_entry.get("id")
                                    track_files = []
                                    if album_id:
                                        tracks = arr.client.track.get(album_id=album_id) or []
                                        track_file_ids = sorted(
                                            {
                                                int(track_file_id)
                                                for track in tracks
                                                if isinstance(track, dict)
                                                and (track_file_id := track.get("trackFileId"))
                                            }
                                        )
                                        if track_file_ids:
                                            track_files = (
                                                arr.client.track_file.get(
                                                    track_file_ids=track_file_ids
                                                )
                                                or []
                                            )

                                    if track_files:
                                        # Check if any track file's quality is below the cutoff.
                                        for track_file in track_files:
                                            if not isinstance(track_file, dict):
                                                continue
                                            file_quality = track_file.get("quality", {}).get(
                                                "quality", {}
                                            )
                                            file_quality_id = file_quality.get("id", 0)

                                            if file_quality_id < cutoff_quality_id:
                                                QualityUnmet = True
                                                arr.logger.trace(
                                                    "Album '%s' has quality below cutoff: %s (ID: %d) < cutoff (ID: %d)",
                                                    db_entry.get("title", "Unknown"),
                                                    file_quality.get("name", "Unknown"),
                                                    file_quality_id,
                                                    cutoff_quality_id,
                                                )
                                                break
                        except Exception as e:
                            arr.logger.trace(
                                "Could not determine quality cutoff status for album '%s': %s",
                                db_entry.get("title", "Unknown"),
                                str(e),
                            )
                            # Default to False if we can't determine
                            QualityUnmet = False

                    if (
                        hasAllTracks
                        and not (arr.quality_unmet_search and QualityUnmet)
                        and not (arr.custom_format_unmet_search and customFormat < minCustomFormat)
                    ):
                        searched = True
                        arr.model_queue.update(Completed=True).where(
                            (arr.model_queue.EntryId == db_entry["id"])
                            & (arr.model_queue.ArrInstance == arr._name)
                        ).execute()

                    # Note: Lidarr quality profiles are set at artist level, not album level.
                    # Temp profile logic for Lidarr is handled in artist processing below.

                    title = db_entry.get("title", "Unknown Album")
                    monitored = db_entry.get("monitored", False)
                    # Handle artist field which can be an object or might not exist
                    artist_obj = db_entry.get("artist", {})
                    if isinstance(artist_obj, dict):
                        # Try multiple possible field names for artist name
                        artistName = (
                            artist_obj.get("artistName")
                            or artist_obj.get("name")
                            or artist_obj.get("title")
                            or "Unknown Artist"
                        )
                    else:
                        artistName = "Unknown Artist"
                    artistId = db_entry.get("artistId", 0)
                    foreignAlbumId = db_entry.get("foreignAlbumId", "")
                    releaseDate = db_entry.get("releaseDate")
                    entryId = db_entry.get("id", 0)
                    albumFileId = 1 if hasAllTracks else 0  # Use 1/0 to indicate presence
                    qualityMet = not QualityUnmet if hasAllTracks else False
                    customFormatMet = customFormat >= minCustomFormat

                    # Get quality profile info from artist (Lidarr albums inherit from artist)
                    qualityProfileId = None
                    qualityProfileName = None
                    try:
                        artist_id = db_entry.get("artistId")
                        if artist_id:
                            # Try to get from already-fetched artist data if available
                            artist_data = arr.client.artist.get(item_id=artist_id)
                            qualityProfileId = artist_data.get("qualityProfileId")
                            if qualityProfileId:
                                # Fetch quality profile from cache or API
                                if qualityProfileId not in arr._quality_profile_cache:
                                    profile = arr.client.quality_profile.get(
                                        item_id=qualityProfileId
                                    )
                                    arr._quality_profile_cache[qualityProfileId] = profile
                                qualityProfileName = arr._quality_profile_cache[
                                    qualityProfileId
                                ].get("name")
                    except Exception:
                        pass

                    if not hasAllTracks:
                        # Album is missing tracks - always mark as Missing
                        reason = "Missing"
                    elif arr.quality_unmet_search and QualityUnmet:
                        reason = "Quality"
                    elif arr.custom_format_unmet_search and not customFormatMet:
                        reason = "CustomFormat"
                    elif arr.do_upgrade_search:
                        reason = "Upgrade"
                    elif searched:
                        # Album is complete and not being searched
                        reason = "Not being searched"
                    else:
                        reason = "Not being searched"

                    to_update = {
                        arr.model_file.AlbumFileId: albumFileId,
                        arr.model_file.Monitored: monitored,
                        arr.model_file.QualityMet: qualityMet,
                        arr.model_file.Searched: searched,
                        arr.model_file.Upgrade: False,
                        arr.model_file.MinCustomFormatScore: minCustomFormat,
                        arr.model_file.CustomFormatScore: customFormat,
                        arr.model_file.CustomFormatMet: customFormatMet,
                        arr.model_file.Reason: reason,
                        arr.model_file.ArtistTitle: artistName,
                        arr.model_file.ArtistId: artistId,
                        arr.model_file.ForeignAlbumId: foreignAlbumId,
                        arr.model_file.ReleaseDate: releaseDate,
                        arr.model_file.QualityProfileId: qualityProfileId,
                        arr.model_file.QualityProfileName: qualityProfileName,
                    }

                    if request:
                        to_update[arr.model_file.IsRequest] = request

                    arr.logger.debug(
                        "Updating database entry | %s - %s [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                        artistName.ljust(30, "."),
                        title.ljust(30, "."),
                        str(searched).ljust(5),
                        str(False).ljust(5),
                        str(qualityMet).ljust(5),
                        str(customFormatMet).ljust(5),
                    )

                    db_commands = arr.model_file.insert(
                        Title=title,
                        Monitored=monitored,
                        ArtistTitle=artistName,
                        ArtistId=artistId,
                        ForeignAlbumId=foreignAlbumId,
                        ReleaseDate=releaseDate,
                        EntryId=entryId,
                        Searched=searched,
                        AlbumFileId=albumFileId,
                        IsRequest=request,
                        QualityMet=qualityMet,
                        Upgrade=False,
                        MinCustomFormatScore=minCustomFormat,
                        CustomFormatScore=customFormat,
                        CustomFormatMet=customFormatMet,
                        Reason=reason,
                        QualityProfileId=qualityProfileId,
                        QualityProfileName=qualityProfileName,
                        ArrInstance=arr._name,
                    ).on_conflict(
                        conflict_target=[arr.model_file.EntryId, arr.model_file.ArrInstance],
                        update=to_update,
                    )
                    db_commands.execute()

                    # Store tracks for this album (Lidarr only)
                    if arr.track_file_model:
                        try:
                            # Fetch tracks for this album via the track API
                            # Tracks are NOT in the media field, they're a separate endpoint
                            tracks = arr.client.track.get(album_id=entryId)
                            arr.logger.debug(
                                f"Fetched {len(tracks) if isinstance(tracks, list) else 0} tracks for album {entryId}"
                            )

                            if tracks and isinstance(tracks, list):
                                # First, delete existing tracks for this album
                                arr.track_file_model.delete().where(
                                    (arr.track_file_model.AlbumId == entryId)
                                    & (arr.track_file_model.ArrInstance == arr._name)
                                ).execute()

                                # Insert new tracks
                                track_insert_count = 0
                                for track in tracks:
                                    # Get monitored status from track or default to album's monitored status
                                    track_monitored = track.get(
                                        "monitored", db_entry.get("monitored", False)
                                    )

                                    arr.track_file_model.insert(
                                        EntryId=track.get("id"),
                                        AlbumId=entryId,
                                        TrackNumber=track.get("trackNumber", ""),
                                        Title=track.get("title", ""),
                                        Duration=_lidarr_track_duration_seconds(
                                            track.get("duration", 0)
                                        ),
                                        HasFile=track.get("hasFile", False),
                                        TrackFileId=track.get("trackFileId", 0),
                                        Monitored=track_monitored,
                                        ArrInstance=arr._name,
                                    ).execute()
                                    track_insert_count += 1

                                if track_insert_count > 0:
                                    arr.logger.info(
                                        f"Stored {track_insert_count} tracks for album {entryId} ({title})"
                                    )
                            else:
                                arr.logger.debug(f"No tracks found for album {entryId} ({title})")
                        except Exception as e:
                            arr.logger.warning(
                                f"Could not fetch tracks for album {entryId} ({title}): {e}"
                            )
                else:
                    db_commands = arr.model_file.delete().where(
                        (arr.model_file.EntryId == db_entry["id"])
                        & (arr.model_file.ArrInstance == arr._name)
                    )
                    db_commands.execute()
                    # Also delete tracks for this album (Lidarr only)
                    if arr.track_file_model:
                        arr.track_file_model.delete().where(
                            (arr.track_file_model.AlbumId == db_entry["id"])
                            & (arr.track_file_model.ArrInstance == arr._name)
                        ).execute()
            else:
                # Artist handling
                arr.artists_file_model: ArtistFilesModel
                EntryId = db_entry["id"]
                artistData = arr.artists_file_model.get_or_none(
                    (arr.artists_file_model.EntryId == EntryId)
                    & (arr.artists_file_model.ArrInstance == arr._name)
                )
                if db_entry["monitored"] or arr.search_unmonitored:
                    _retry_exc = (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    )
                    artistMetadata = (
                        with_retry(
                            lambda eid=EntryId: arr.client.artist.get(item_id=eid),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_retry_exc,
                        )
                        or {}
                    )
                    quality_profile_id = None
                    if isinstance(artistMetadata, dict):
                        quality_profile_id = artistMetadata.get("qualityProfileId")
                    else:
                        quality_profile_id = getattr(artistMetadata, "qualityProfileId", None)
                    if not artistData:
                        if quality_profile_id:
                            profile = (
                                with_retry(
                                    lambda qpid=quality_profile_id: arr.client.quality_profile.get(
                                        item_id=qpid
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_retry_exc,
                                )
                                or {}
                            )
                            minCustomFormat = profile.get("minFormatScore") or 0
                        else:
                            arr.logger.warning(
                                "Artist %s (%s) missing qualityProfileId; "
                                "defaulting custom format score to 0",
                                db_entry.get("artistName"),
                                EntryId,
                            )
                            minCustomFormat = 0
                    else:
                        minCustomFormat = getattr(artistData, "MinCustomFormatScore", 0)
                    # Calculate if artist is fully searched based on album statistics
                    statistics = artistMetadata.get("statistics", {})
                    albumCount = statistics.get("albumCount", 0)
                    statistics.get("totalAlbumCount", 0)
                    # Check if there's any album with files (sizeOnDisk > 0)
                    sizeOnDisk = statistics.get("sizeOnDisk", 0)
                    # Artist is considered searched if it has albums and at least some have files
                    searched = albumCount > 0 and sizeOnDisk > 0

                    profile_switch_timestamp = None
                    original_profile_for_db = None
                    current_profile_for_db = None
                    if arr.use_temp_for_missing and quality_profile_id:
                        profile_update_needed = False
                        if (
                            searched
                            and quality_profile_id in arr.main_quality_profile_ids.keys()
                            and not arr.keep_temp_profile
                        ):
                            old_profile_id = quality_profile_id
                            main_profile_id = arr.main_quality_profile_ids[quality_profile_id]
                            artistMetadata["qualityProfileId"] = main_profile_id
                            profile_update_needed = True
                            quality_profile_id = main_profile_id
                            profile_switch_timestamp = datetime.now()
                            arr.logger.debug(
                                "Upgrading artist '%s' from temp profile (ID:%s) to main profile (ID:%s) [Has files]",
                                artistMetadata.get("artistName", "Unknown"),
                                old_profile_id,
                                main_profile_id,
                            )
                        elif (
                            not searched
                            and sizeOnDisk == 0
                            and quality_profile_id in arr.temp_quality_profile_ids.keys()
                        ):
                            old_profile_id = quality_profile_id
                            temp_profile_id = arr.temp_quality_profile_ids[quality_profile_id]
                            artistMetadata["qualityProfileId"] = temp_profile_id
                            profile_update_needed = True
                            profile_switch_timestamp = datetime.now()
                            original_profile_for_db = old_profile_id
                            current_profile_for_db = temp_profile_id
                            quality_profile_id = temp_profile_id
                            arr.logger.debug(
                                "Downgrading artist '%s' from main profile (ID:%s) to temp profile (ID:%s) [No files yet]",
                                artistMetadata.get("artistName", "Unknown"),
                                old_profile_id,
                                temp_profile_id,
                            )
                        if profile_update_needed:
                            profile_update_success = arr._retry_profile_switch_update(
                                lambda: arr.client.artist.update(data=artistMetadata),
                                "artist",
                            )
                            if not profile_update_success:
                                profile_switch_timestamp = None
                                original_profile_for_db = None
                                current_profile_for_db = None

                    Title = artistMetadata.get("artistName")
                    Monitored = db_entry["monitored"]

                    to_update = {
                        arr.artists_file_model.Monitored: Monitored,
                        arr.artists_file_model.Title: Title,
                        arr.artists_file_model.Searched: searched,
                        arr.artists_file_model.Upgrade: False,
                        arr.artists_file_model.MinCustomFormatScore: minCustomFormat,
                    }
                    if arr.use_temp_for_missing and profile_switch_timestamp is not None:
                        to_update[arr.artists_file_model.LastProfileSwitchTime] = (
                            profile_switch_timestamp
                        )
                        to_update[arr.artists_file_model.OriginalProfileId] = (
                            original_profile_for_db
                        )
                        to_update[arr.artists_file_model.CurrentProfileId] = current_profile_for_db

                    arr.logger.debug(
                        "Updating database entry | %s [Searched:%s][Upgrade:%s]",
                        Title.ljust(60, "."),
                        str(searched).ljust(5),
                        str(False).ljust(5),
                    )

                    db_commands = arr.artists_file_model.insert(
                        EntryId=EntryId,
                        Title=Title,
                        Searched=searched,
                        Monitored=Monitored,
                        Upgrade=False,
                        MinCustomFormatScore=minCustomFormat,
                        ArrInstance=arr._name,
                    ).on_conflict(
                        conflict_target=[
                            arr.artists_file_model.EntryId,
                            arr.artists_file_model.ArrInstance,
                        ],
                        update=to_update,
                    )
                    db_commands.execute()

                    # Note: Albums are now handled separately in db_update()
                    # No need to recursively process albums here to avoid duplication
                else:
                    db_commands = arr.artists_file_model.delete().where(
                        (arr.artists_file_model.EntryId == EntryId)
                        & (arr.artists_file_model.ArrInstance == arr._name)
                    )
                    db_commands.execute()

        refresh_rollups_after_db_update(arr, db_entry, series=series, artist=artist)

    except requests.exceptions.ConnectionError as e:
        arr.logger.debug(
            "Max retries exceeded for %s [%s][%s]",
            arr._name,
            db_entry["id"],
            db_entry["title"],
            exc_info=e,
        )
        raise DelayLoopException(length=300, error_type=arr._name)
    except JSONDecodeError:
        if arr.type == "sonarr":
            if arr.series_search:
                arr.logger.warning(
                    "Error getting series info: [%s][%s]", db_entry["id"], db_entry["title"]
                )
            else:
                arr.logger.warning(
                    "Error getting episode info: [%s][%s]", db_entry["id"], db_entry["title"]
                )
        elif arr.type == "radarr":
            arr.logger.warning(
                "Error getting movie info: [%s][%s]", db_entry["id"], db_entry["path"]
            )
    except Exception as e:
        if isinstance(e, (OperationalError, sqlite3.DatabaseError)):
            raise
        arr.logger.error(e, exc_info=sys.exc_info())
