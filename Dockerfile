# Pin Python to the latest supported version
# (This avoid it auto updating to a higher untested version)
FROM pypy:3.8-7.3.7

LABEL Maintainer="Draper"

# Env used by the script to determine if its inside a docker -
# if this is set to 69420 it will change the working dir for docker specific values
ENV QBITRR_DOCKER_RUNNING=69420
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY . /app

WORKDIR /app/

RUN pypy -m ensurepip --default-pip
RUN pip install -U pip wheel
RUN pip install -e .

WORKDIR /config

ENTRYPOINT ["pypy", "-m", "qBitrr.main"]
