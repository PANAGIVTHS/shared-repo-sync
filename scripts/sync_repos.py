#!/usr/bin/env python3
"""Sync configured Git repositories exactly from source to destination."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(mask_token(part) for part in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def mask_token(value: str) -> str:
    token = os.environ.get("REPO_SYNC_TOKEN", "")
    if token:
        value = value.replace(token, "***")
    return value


def with_token(url: str, token: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"Only https://github.com/... destinations are supported, got: {url}")
    return urlunparse(parsed._replace(netloc=f"x-access-token:{token}@{parsed.netloc}"))


def sync_repo(repo: dict[str, object], token: str) -> None:
    name = str(repo["name"])
    source = str(repo["source"])
    destination = str(repo["destination"])
    use_lfs = bool(repo.get("lfs", False))

    print(f"::group::Sync {name}", flush=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"sync-{name}-"))
    try:
        bare = workdir / "repo.git"
        run(["git", "clone", "--mirror", source, str(bare)])
        if use_lfs:
            run(["git", "lfs", "fetch", "--all"], cwd=bare)
        run(["git", "remote", "set-url", "--push", "origin", with_token(destination, token)], cwd=bare)
        run(["git", "fetch", "-p", "origin"], cwd=bare)
        run(["git", "push", "--mirror"], cwd=bare)
        if use_lfs:
            run(["git", "lfs", "push", "--all", with_token(destination, token)], cwd=bare)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        print("::endgroup::", flush=True)


def main() -> int:
    token = os.environ.get("REPO_SYNC_TOKEN")
    if not token:
        print("REPO_SYNC_TOKEN is required", file=sys.stderr)
        return 2

    config_path = Path(os.environ.get("REPO_SYNC_CONFIG", "repos.json"))
    config = json.loads(config_path.read_text())
    repos = config.get("repositories", [])
    if not repos:
        print("No repositories configured")
        return 0

    for repo in repos:
        sync_repo(repo, token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
