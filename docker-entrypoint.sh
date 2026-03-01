#!/bin/sh
set -e
# Default to 1000:1000 when PUID/PGID are not set (e.g. docker run without -e)
export PUID="${PUID:-1000}"
export PGID="${PGID:-1000}"

# When running as root, ensure /config is owned by PUID:PGID so the app can write
# (mounted volumes often appear as root-owned; this restores writability)
if [ "$(id -u)" = "0" ] && [ "${PUID}" != "0" ]; then
    chown -R "${PUID}:${PGID}" /config 2>/dev/null || true
fi

# Run the container CMD as the specified user (tini + python)
exec gosu "${PUID}:${PGID}" /usr/bin/tini -- "$@"
