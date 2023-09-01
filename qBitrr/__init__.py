import contextlib
import platform

import qBitrr.logger  # noqa

with contextlib.suppress(ImportError):
    if platform.python_implementation() == "CPython":
        # Only replace complexjson on CPython
        # On PyPy it shows a SystemError when attempting to
        # decode the responses from qbittorrentapi
        import requests
        import ujson

        requests.models.complexjson = ujson
