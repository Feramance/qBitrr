import qBitrr.logger  # noqa

try:
    import requests
    import ujson

    requests.models.complexjson = ujson
except ImportError:
    pass
