#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBUI_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${WEBUI_DIR}"

NEED_INSTALL=false
if [ ! -d "node_modules" ]; then
  NEED_INSTALL=true
elif [ ! -d "node_modules/@types/node" ] || [ ! -d "node_modules/vite" ]; then
  NEED_INSTALL=true
fi

if [ "$NEED_INSTALL" = true ]; then
  echo "[pre-commit] Installing webui dependencies"
  npm install --prefer-offline
fi

echo "[pre-commit] Building webui bundle"
npm run build
