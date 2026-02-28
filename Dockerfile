# Frontend build stage
FROM node:25-bookworm AS webui-build
WORKDIR /src
COPY webui/package*.json webui/.npmrc webui/
RUN cd webui && npm ci
COPY webui webui
RUN mkdir -p qBitrr/static && cd webui && npm run build

FROM python:3.12-slim

LABEL Name="qBitrr"
LABEL Maintainer="feramance"
LABEL Version="5.9.1"
LABEL org.opencontainers.image.source=https://github.com/feramance/qbitrr

# Install tini so PID 1 forwards SIGTERM to Python (enables graceful shutdown and DB checkpoint)
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Env used by the script to determine if it's inside a docker -
# if this is set to 69420 it will change the working dir for docker specific values
ENV QBITRR_DOCKER_RUNNING=69420
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1

RUN pip install --no-cache-dir --quiet -U pip wheel
WORKDIR /app
COPY . /app
COPY --from=webui-build /src/qBitrr/static/ /app/qBitrr/static/
RUN rm -rf qBitrr2.egg-info *.egg-info && pip install --no-cache-dir --quiet ".[fast]"

RUN groupadd -r qbitrr && useradd -r -g qbitrr -d /config -s /sbin/nologin qbitrr \
    && mkdir -p /config && chown -R qbitrr:qbitrr /config /app
USER qbitrr

WORKDIR /config

EXPOSE 6969

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "qBitrr.main"]
