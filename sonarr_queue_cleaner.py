import os.path

from pyarr import RadarrAPI, SonarrAPI

client = SonarrAPI(host_url="http://localhost:8990", api_key="14bd6a57791246059815f25113aa3c83")


def get_queue(
    page=1,
    page_size=20,
    sort_direction="ascending",
    sort_key="timeLeft",
    include_unknown_movie_items=True,
):
    params = {
        "page": page,
        "pageSize": page_size,
        "sortDirection": sort_direction,
        "sortKey": sort_key,
        "includeUnknownMovieItems": include_unknown_movie_items,
    }
    path = "/api/v3/queue"
    res = client.request_get(path, params=params)
    return res


def _get_bad_queue_entries():
    queue = get_queue().get("records", [])
    _path_filter = set()
    filtered_queue = filter(
        lambda x: x.get("status") == "completed"
        and x.get("trackedDownloadState") == "importPending"
        and x.get("trackedDownloadStatus") == "warning"
        and (y := x.get("outputPath"))
        and y not in _path_filter
        and not _path_filter.add(y),
        queue,
    )



_get_bad_queue_entries()
