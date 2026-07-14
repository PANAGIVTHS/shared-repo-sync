# shared-repo-sync

Private automation repository for keeping selected shared course repositories in sync under `ACrispyCookie`.

## How it works

- Repository pairs are listed in `repos.json`.
- The scheduled GitHub Actions workflow from `templates/sync.yml` runs `scripts/sync_repos.py`.
- The script performs an exact Git mirror sync for each configured repository.

## Required secret

The workflow expects a repository secret named `REPO_SYNC_TOKEN`.

The token must be able to create any missing destination mirror repositories and then push to them. For personal repositories under `ACrispyCookie`, use a token that can create repositories for the authenticated user. For organization-owned destinations, the token must be allowed to create repositories in that organization.

For public source repositories, the token only needs destination-side create/write access. For private source repositories, it also needs read access to the source repositories. If a mirror includes `.github/workflows/*`, the token also needs workflow permission.

## Destination repository creation

Before each mirror sync, `scripts/sync_repos.py` checks whether the configured `destination` repository exists through the GitHub API. If GitHub returns 404, the script creates the destination repository and then performs the normal `git push --mirror`.

Each entry in `repos.json` may set:

```json
"private": true
```

If omitted, newly created destination repositories default to public (`false`).

## Installing the workflow

The current stored GitHub token on this machine cannot push files under `.github/workflows/` because it lacks the `workflow` scope. After using a token with `workflow` scope, copy `templates/sync.yml` to `.github/workflows/sync.yml` and push it.
