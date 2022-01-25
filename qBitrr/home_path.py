import os
import pathlib

env_var = os.getenv("QBITRR_DOCKER_RUNNING")

if env_var == "69420":
    ON_DOCKER = True
    HOME_PATH = pathlib.Path("/config")
    HOME_PATH.mkdir(parents=True, exist_ok=True)
else:
    ON_DOCKER = False
    HOME_PATH = pathlib.Path().home()
