#!/usr/bin/env python
"""Autofix helper that leverages OpenAI Codex-compatible models to remediate failed GitHub Actions runs."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
from openai import OpenAI


def debug(msg: str) -> None:
    print(f"[autofix] {msg}", file=sys.stderr)


def run_cmd(
    args: Iterable[str], *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess:
    debug(f"run: {' '.join(args)}")
    return subprocess.run(list(args), text=True, capture_output=capture, check=check)


def capture(args: Iterable[str]) -> str:
    result = run_cmd(args, capture=True)
    return result.stdout.strip()


def load_event(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def shorten(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    prefix = limit // 2
    suffix = limit - prefix
    return f"{text[:prefix]}\n\n… truncated …\n\n{text[-suffix:]}"


def download_logs(logs_url: str, token: str) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "autofix-bot",
    }
    debug(f"Downloading logs from {logs_url}")
    response = requests.get(logs_url, headers=headers, timeout=60)
    response.raise_for_status()

    buffer = BytesIO(response.content)
    parts: list[str] = []
    with ZipFile(buffer) as archive:
        for name in archive.namelist():
            if not name.endswith(".txt"):
                continue
            content = archive.read(name).decode("utf-8", errors="ignore")
            parts.append(f"===== {name} =====\n{content}")
    return "\n\n".join(parts)


def ensure_checkout(head_sha: str, default_branch: str) -> None:
    current = capture(["git", "rev-parse", "HEAD"])
    if current == head_sha:
        debug("Already on failing commit")
        return
    run_cmd(["git", "fetch", "origin", head_sha])
    run_cmd(["git", "checkout", head_sha])


def apply_diff(unified_diff: str) -> None:
    if not unified_diff.strip():
        raise ValueError("Model returned an empty diff")
    patch_path = Path("autofix.patch")
    patch_path.write_text(unified_diff, encoding="utf-8")
    try:
        run_cmd(["git", "apply", "--whitespace=fix", str(patch_path)])
    finally:
        patch_path.unlink(missing_ok=True)


def configure_git() -> None:
    run_cmd(["git", "config", "user.name", "github-actions[bot]"])
    run_cmd(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])


def create_branch_and_push(branch: str, base: str, message: str) -> None:
    configure_git()
    run_cmd(["git", "checkout", "-B", branch, base])
    run_cmd(["git", "add", "-A"])
    run_cmd(["git", "commit", "-m", message])
    run_cmd(["git", "push", "origin", branch])


def push_to_branch(branch: str, message: str) -> None:
    configure_git()
    run_cmd(["git", "checkout", branch])
    run_cmd(["git", "add", "-A"])
    run_cmd(["git", "commit", "-m", message])
    run_cmd(["git", "push", "origin", branch])


def create_pull_request(
    token: str,
    repository: str,
    *,
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict:
    url = f"https://api.github.com/repos/{repository}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "autofix-bot",
    }
    payload = {"title": title, "body": body, "head": head, "base": base}
    debug(f"Creating PR {head} -> {base} on {repository}")
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 201:
        raise RuntimeError(f"Failed to create PR: {response.status_code} {response.text}")
    return response.json()


@dataclass
class ModelResponse:
    summary: str
    diff: str


def query_model(
    client: OpenAI,
    *,
    model: str,
    repo: str,
    workflow_name: str,
    failure_url: str,
    logs: str,
    repo_status: str,
    recent_commits: str,
) -> ModelResponse:
    system_prompt = (
        "You are an elite software engineer assisting an automated remediation workflow. "
        "Given repository context and failing GitHub Actions logs, produce a minimal unified diff that fixes the failure. "
        "Respond ONLY with JSON containing keys 'summary' and 'diff'. "
        "'diff' must be a git-apply compatible unified diff. "
        "Do not include markdown fences or any extra commentary."
    )
    user_prompt = textwrap.dedent(
        f"""
        Repository: {repo}
        Workflow: {workflow_name}
        Failed run: {failure_url}

        Current status (git status --short):
        {repo_status}

        Recent commits:
        {recent_commits}

        Logs:
        {shorten(logs)}
        """
    )
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    raw = response.output_text.strip()
    debug(f"Model response: {raw[:200]}{'...' if len(raw) > 200 else ''}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response is not valid JSON: {exc}") from exc
    return ModelResponse(
        summary=payload.get("summary", "Automated fix"), diff=payload.get("diff", "")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Attempt to remediate a failed workflow run.")
    parser.add_argument(
        "--base", default=None, help="Fallback base branch when the event does not specify one."
    )
    parser.add_argument("--model", default=os.environ.get("AUTOFIX_MODEL", "gpt-4.1-mini"))
    args = parser.parse_args()

    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    openai_key = os.environ["OPENAI_API_KEY"]
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    event = load_event(event_path)

    workflow_run = event["workflow_run"]
    run_event = workflow_run["event"]
    head_sha = workflow_run["head_sha"]
    head_branch = workflow_run.get("head_branch")
    workflow_name = workflow_run["name"]
    failure_url = workflow_run["html_url"]
    default_branch = (
        args.base
        or workflow_run.get("repository", {}).get("default_branch")
        or os.environ.get("AUTOFIX_BASE_BRANCH")
        or "main"
    )

    ensure_checkout(head_sha, default_branch)

    logs = download_logs(workflow_run["logs_url"], token)
    status_text = capture(["git", "status", "--short"])
    commits_text = capture(["git", "log", "-5", "--oneline"])

    client = OpenAI(api_key=openai_key)
    model_response = query_model(
        client,
        model=args.model,
        repo=repo,
        workflow_name=workflow_name,
        failure_url=failure_url,
        logs=logs,
        repo_status=status_text,
        recent_commits=commits_text,
    )

    apply_diff(model_response.diff)

    summary = model_response.summary or "Automated fix"
    commit_message = f"[autofix] {summary}"

    if run_event in {"pull_request", "pull_request_target"} and head_branch:
        debug(f"Pushing fix directly to PR branch {head_branch}")
        push_to_branch(head_branch, commit_message)
        debug("Fix pushed to PR branch; workflow will re-run automatically.")
    else:
        debug("Preparing separate PR for default branch failure")
        branch_name = f"autofix/{uuid.uuid4().hex[:8]}"
        create_branch_and_push(branch_name, default_branch, commit_message)
        pr_body = textwrap.dedent(
            f"""
            ## Summary
            {summary}

            ## Details
            - Failed run: {failure_url}
            - Trigger: {run_event}

            Generated automatically by the autofix workflow.
            """
        ).strip()
        pr = create_pull_request(
            token,
            repo,
            title=f"[autofix] {summary}",
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )
        debug(f"Created PR #{pr.get('number')} -> {pr.get('html_url')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        debug(f"Autofix failed: {exc}")
        raise
