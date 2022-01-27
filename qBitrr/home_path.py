import pathlib

from jaraco.docker import is_docker

if is_docker():
    ON_DOCKER = True
    HOME_PATH = pathlib.Path("/config")
    HOME_PATH.mkdir(parents=True, exist_ok=True)
else:
    ON_DOCKER = False
    HOME_PATH = pathlib.Path().home()
