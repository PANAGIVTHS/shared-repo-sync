#!/usr/bin/env python3
"""Sync configured Git repositories exactly from source to destination."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


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


@dataclass(frozen=True)
class GitHubResponse:
    status: int
    payload: dict[str, object]
    text: str


def github_request(method: str, url: str, token: str, data: str | None = None) -> GitHubResponse:
    body = data.encode() if data is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urlopen(request) as response:
            text = response.read().decode()
            payload = json.loads(text) if text else {}
            return GitHubResponse(response.status, payload, text)
    except HTTPError as exc:
        text = exc.read().decode()
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            payload = {}
        return GitHubResponse(exc.code, payload, text)


def destination_owner_repo(destination: str) -> tuple[str, str]:
    parsed = urlparse(destination)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"Only https://github.com/... destinations are supported, got: {destination}")
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Destination must look like https://github.com/OWNER/REPO.git, got: {destination}")
    return parts[0], parts[1]


def ensure_destination_repository(destination: str, token: str, private: bool) -> None:
    owner, repo = destination_owner_repo(destination)
    api_repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    existing = github_request("GET", api_repo_url, token)
    if existing.status == 200:
        print(f"Destination repository exists: {owner}/{repo}", flush=True)
        return
    if existing.status != 404:
        raise RuntimeError(f"Could not check destination repository {owner}/{repo}: HTTP {existing.status} {existing.text}")

    user = github_request("GET", "https://api.github.com/user", token)
    if user.status != 200:
        raise RuntimeError(f"Could not identify authenticated GitHub user: HTTP {user.status} {user.text}")
    login = str(user.payload.get("login", ""))
    create_url = "https://api.github.com/user/repos" if owner.lower() == login.lower() else f"https://api.github.com/orgs/{owner}/repos"
    payload = json.dumps({"name": repo, "private": private})

    print(f"Destination repository missing; creating {owner}/{repo}", flush=True)
    created = github_request("POST", create_url, token, payload)
    if created.status in (201, 202):
        print(f"Created destination repository: {owner}/{repo}", flush=True)
        return
    if created.status == 422:
        recheck = github_request("GET", api_repo_url, token)
        if recheck.status == 200:
            print(f"Destination repository exists after create race: {owner}/{repo}", flush=True)
            return
    raise RuntimeError(f"Could not create destination repository {owner}/{repo}: HTTP {created.status} {created.text}")


def sync_repo(repo: dict[str, object], token: str) -> None:
    name = str(repo["name"])
    source = str(repo["source"])
    destination = str(repo["destination"])
    use_lfs = bool(repo.get("lfs", False))
    private = bool(repo.get("private", False))

    print(f"::group::Sync {name}", flush=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"sync-{name}-"))
    try:
        bare = workdir / "repo.git"
        ensure_destination_repository(destination, token, private)
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
