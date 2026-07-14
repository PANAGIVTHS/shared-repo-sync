import json
import unittest
from unittest.mock import patch

from scripts import sync_repos


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status = status
        self.payload = payload or {}
        self.text = text

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class EnsureDestinationRepositoryTests(unittest.TestCase):
    def test_existing_destination_repository_is_not_created(self):
        calls = []

        def fake_request(method, url, token, data=None):
            calls.append((method, url, data))
            return FakeResponse(200, {"full_name": "ACrispyCookie/existing"})

        with patch.object(sync_repos, "github_request", side_effect=fake_request):
            sync_repos.ensure_destination_repository(
                "https://github.com/ACrispyCookie/existing.git",
                "token",
                private=False,
            )

        self.assertEqual(
            calls,
            [("GET", "https://api.github.com/repos/ACrispyCookie/existing", None)],
        )

    def test_missing_user_destination_repository_is_created(self):
        calls = []

        def fake_request(method, url, token, data=None):
            calls.append((method, url, data))
            if method == "GET" and url.endswith("/repos/ACrispyCookie/new-repo"):
                return FakeResponse(404, {"message": "Not Found"}, "Not Found")
            if method == "GET" and url.endswith("/user"):
                return FakeResponse(200, {"login": "ACrispyCookie"})
            if method == "POST" and url.endswith("/user/repos"):
                return FakeResponse(201, {"full_name": "ACrispyCookie/new-repo"})
            self.fail(f"unexpected request: {method} {url}")

        with patch.object(sync_repos, "github_request", side_effect=fake_request):
            sync_repos.ensure_destination_repository(
                "https://github.com/ACrispyCookie/new-repo.git",
                "token",
                private=False,
            )

        self.assertEqual(calls[2][0], "POST")
        self.assertEqual(calls[2][1], "https://api.github.com/user/repos")
        self.assertEqual(json.loads(calls[2][2]), {"name": "new-repo", "private": False})

    def test_missing_org_destination_repository_is_created_under_org(self):
        calls = []

        def fake_request(method, url, token, data=None):
            calls.append((method, url, data))
            if method == "GET" and url.endswith("/repos/SomeOrg/new-repo"):
                return FakeResponse(404, {"message": "Not Found"}, "Not Found")
            if method == "GET" and url.endswith("/user"):
                return FakeResponse(200, {"login": "ACrispyCookie"})
            if method == "POST" and url.endswith("/orgs/SomeOrg/repos"):
                return FakeResponse(201, {"full_name": "SomeOrg/new-repo"})
            self.fail(f"unexpected request: {method} {url}")

        with patch.object(sync_repos, "github_request", side_effect=fake_request):
            sync_repos.ensure_destination_repository(
                "https://github.com/SomeOrg/new-repo.git",
                "token",
                private=True,
            )

        self.assertEqual(calls[2][1], "https://api.github.com/orgs/SomeOrg/repos")
        self.assertEqual(json.loads(calls[2][2]), {"name": "new-repo", "private": True})


if __name__ == "__main__":
    unittest.main()
