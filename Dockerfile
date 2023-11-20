# Pin Python to the latest supported version
# (This avoid it auto updating to a higher untested version)
FROM python:3.10

LABEL Name="qBitrr"
LABEL Maintainer="Feramance"
LABEL Version="3.8.5-beta-0"

# Env used by the script to determine if its inside a docker -
# if this is set to 69420 it will change the working dir for docker specific values
ENV QBITRR_DOCKER_RUNNING=69420
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1

RUN pip install --quiet -U pip wheel
WORKDIR /app
ADD ./requirements.fast.txt /app/requirements.fast.txt
RUN pip install --quiet -r requirements.fast.txt
COPY . /app
RUN pip install --quiet .

WORKDIR /config

ENTRYPOINT ["python", "-m", "qBitrr.main"]
