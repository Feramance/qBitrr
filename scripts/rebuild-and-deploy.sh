#!/usr/bin/env bash
# Rebuild and deploy qBitrr (for use after git pull / sync).
# Supports: Docker Compose deploy, or native make syncenv only.
# Set DEPLOY_MODE=docker (default if docker-compose.yml present) or DEPLOY_MODE=native.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[rebuild-and-deploy] Working in $REPO_ROOT"

# Default: use docker if docker-compose.yml exists
if [ -z "${DEPLOY_MODE}" ]; then
  if [ -f "docker-compose.yml" ]; then
    DEPLOY_MODE=docker
  else
    DEPLOY_MODE=native
  fi
fi

case "${DEPLOY_MODE}" in
  docker)
    echo "[rebuild-and-deploy] Rebuilding and deploying with Docker Compose..."
    docker compose build --no-cache
    docker compose up -d
    echo "[rebuild-and-deploy] Done. Container status:"
    docker compose ps
    ;;
  native)
    echo "[rebuild-and-deploy] Syncing environment and building WebUI (make syncenv)..."
    make syncenv
    echo "[rebuild-and-deploy] Done. Restart qBitrr manually if needed (e.g. systemctl restart qbitrr)."
    ;;
  *)
    echo "[rebuild-and-deploy] Unknown DEPLOY_MODE=${DEPLOY_MODE}. Use 'docker' or 'native'." >&2
    exit 1
    ;;
esac
