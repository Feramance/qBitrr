import pathlib

from jaraco.docker import is_docker

from qBitrr.env_config import ENVIRO_CONFIG

if (
    ENVIRO_CONFIG.overrides.data_path is None
    or not (p := pathlib.Path(ENVIRO_CONFIG.overrides.data_path)).exists()
):
    if is_docker():
        ON_DOCKER = True
        HOME_PATH = pathlib.Path("/config")
        HOME_PATH.mkdir(parents=True, exist_ok=True)
    else:
        ON_DOCKER = False
        HOME_PATH = pathlib.Path().home()
else:
    HOME_PATH = p
