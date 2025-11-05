# Frontend build stage
FROM node:25-bookworm AS webui-build
WORKDIR /src
COPY webui/package*.json webui/
RUN cd webui && npm ci
COPY webui webui
RUN mkdir -p qBitrr/static && cd webui && npm run build

# Pin Python to the latest supported version we support in production
FROM python:3.14

LABEL Name="qBitrr"
LABEL Maintainer="feramance"
LABEL Version="5.4.1"
LABEL org.opencontainers.image.source=https://github.com/feramance/qbitrr

# Env used by the script to determine if it's inside a docker -
# if this is set to 69420 it will change the working dir for docker specific values
ENV QBITRR_DOCKER_RUNNING=69420
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1

RUN pip install --quiet -U pip wheel
WORKDIR /app
COPY . /app
COPY --from=webui-build /src/qBitrr/static/ /app/qBitrr/static/
RUN rm -rf qBitrr2.egg-info *.egg-info && pip install --quiet ".[fast]"

WORKDIR /config

EXPOSE 6969

ENTRYPOINT ["python", "-m", "qBitrr.main"]
