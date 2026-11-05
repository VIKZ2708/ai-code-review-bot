"""Minimal GitHub REST client for reading PR files and posting a review."""

import requests

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get_pr(self, number: int) -> dict:
        r = self.s.get(f"{API}/repos/{self.repo}/pulls/{number}", timeout=30)
        r.raise_for_status()
        return r.json()

    def get_pr_files(self, number: int) -> list[dict]:
        files, page = [], 1
        while True:
            r = self.s.get(f"{API}/repos/{self.repo}/pulls/{number}/files",
                           params={"per_page": 100, "page": page}, timeout=30)
            r.raise_for_status()
            batch = r.json()
            files.extend(batch)
            if len(batch) < 100:
                return files
            page += 1

    def post_review(self, number: int, commit_id: str, body: str, comments: list[dict]) -> None:
        """Post one review with inline comments; fall back to a plain comment on 422."""
        payload = {"commit_id": commit_id, "body": body, "event": "COMMENT", "comments": comments}
        r = self.s.post(f"{API}/repos/{self.repo}/pulls/{number}/reviews", json=payload, timeout=30)
        if r.status_code == 422 and comments:
            # A line GitHub rejected: still deliver the feedback as one comment.
            fallback = body + "\n\n" + "\n\n".join(
                f"`{c['path']}:{c['line']}` {c['body']}" for c in comments)
            r = self.s.post(f"{API}/repos/{self.repo}/issues/{number}/comments",
                            json={"body": fallback}, timeout=30)
        r.raise_for_status()
