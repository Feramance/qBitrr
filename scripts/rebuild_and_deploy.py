#!/usr/bin/env python3
"""
Rebuild and deploy qBitrr (for use after git pull / sync).
Cross-platform: runs on Windows, Linux, and macOS without bash.

Supports: Docker Compose deploy, or native make syncenv only.
Set DEPLOY_MODE=docker (default if docker-compose.yml present) or DEPLOY_MODE=native.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(repo_root)

    print(f"[rebuild-and-deploy] Working in {repo_root}")

    deploy_mode = os.environ.get("DEPLOY_MODE", "").strip().lower()
    if not deploy_mode:
        deploy_mode = "docker" if os.path.isfile("docker-compose.yml") else "native"

    if deploy_mode == "docker":
        print("[rebuild-and-deploy] Rebuilding and deploying with Docker Compose...")
        for cmd in [
            ["docker", "compose", "build", "--no-cache"],
            ["docker", "compose", "up", "-d"],
        ]:
            ret = subprocess.run(cmd)
            if ret.returncode != 0:
                return ret.returncode
        print("[rebuild-and-deploy] Done. Container status:")
        subprocess.run(["docker", "compose", "ps"])
    elif deploy_mode == "native":
        print("[rebuild-and-deploy] Syncing environment and building WebUI (make syncenv)...")
        ret = subprocess.run(["make", "syncenv"])
        if ret.returncode != 0:
            return ret.returncode
        print(
            "[rebuild-and-deploy] Done. Restart qBitrr manually if needed "
            "(e.g. systemctl restart qbitrr)."
        )
    else:
        print(
            f"[rebuild-and-deploy] Unknown DEPLOY_MODE={deploy_mode}. Use 'docker' or 'native'.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
