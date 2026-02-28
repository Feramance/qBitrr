#!/usr/bin/env bash
# Install the post-merge hook so that 'git pull' triggers rebuild and deploy.
# Run once from repo root: bash scripts/install-post-merge-hook.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SRC="$REPO_ROOT/scripts/post-merge.hook"
HOOK_DST="$REPO_ROOT/.git/hooks/post-merge"

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "Not a git repo: $REPO_ROOT" >&2
  exit 1
fi

if [ ! -f "$HOOK_SRC" ]; then
  echo "Hook template missing: $HOOK_SRC" >&2
  exit 1
fi

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "Installed post-merge hook at .git/hooks/post-merge"
echo "After 'git pull', qBitrr will rebuild and deploy (Docker or native per DEPLOY_MODE)."
echo "Hook uses Python script when available (any OS), else bash script."
