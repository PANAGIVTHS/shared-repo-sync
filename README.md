# shared-repo-sync

Private automation repository for keeping selected shared course repositories in sync under `ACrispyCookie`.

## How it works

- Repository pairs are listed in `repos.json`.
- The scheduled GitHub Actions workflow from `templates/sync.yml` runs `scripts/sync_repos.py`.
- The script performs an exact Git mirror sync for each configured repository.

## Required secret

The workflow expects a repository secret named `REPO_SYNC_TOKEN` with permission to push to the destination repositories.

For public source repositories, the token only needs write access to the destination repositories. For private source repositories, it also needs read access to the source repositories.

## Installing the workflow

The current stored GitHub token on this machine cannot push files under `.github/workflows/` because it lacks the `workflow` scope. After using a token with `workflow` scope, copy `templates/sync.yml` to `.github/workflows/sync.yml` and push it.
