"""Entry point. Runs inside GitHub Actions, or locally:

    python -m reviewer.main --repo owner/name --pr 12 --dry-run
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .config import load_config
from .diff_parser import parse_file
from .github_client import GitHubClient
from .llm import LLMError
from .review import ReviewComment, review_file


def pr_from_event() -> tuple[str, int, str] | None:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        event = json.load(f)
    pr = event.get("pull_request")
    if not pr:
        return None
    return os.environ["GITHUB_REPOSITORY"], pr["number"], pr["head"]["sha"]


def summary_body(comments: list[ReviewComment], reviewed: int, skipped: int,
                 errors: list[str], cfg, seconds: float) -> str:
    counts = {s: sum(c.severity == s for c in comments) for s in ("critical", "major", "minor")}
    lines = [
        "## 🤖 AI Code Review",
        f"Reviewed **{reviewed}** file(s) with `{cfg.provider}/{cfg.model}` in {seconds:.1f}s"
        + (f", skipped {skipped}." if skipped else "."),
        "",
        "| Critical | Major | Minor |",
        "|---|---|---|",
        f"| {counts['critical']} | {counts['major']} | {counts['minor']} |",
    ]
    if not comments:
        lines.append("\nNo issues found. ✅")
    if errors:
        lines.append("\n<details><summary>Errors</summary>\n\n" + "\n".join(f"- {e}" for e in errors) + "\n</details>")
    lines.append("\n_Automated suggestions — a human reviewer still approves the PR._")
    return "\n".join(lines)


def run(repo: str, pr_number: int, head_sha: str | None, dry_run: bool) -> int:
    cfg = load_config()
    token = os.getenv("GITHUB_TOKEN", "")
    gh = GitHubClient(token, repo)
    if not head_sha:
        head_sha = gh.get_pr(pr_number)["head"]["sha"]

    files = gh.get_pr_files(pr_number)
    diffs, skipped = [], 0
    for f in files:
        if f.get("status") == "removed" or not f.get("patch") or cfg.is_ignored(f["filename"]):
            skipped += 1
            continue
        diffs.append(parse_file(f["filename"], f["patch"]))
    if len(diffs) > cfg.max_files:
        skipped += len(diffs) - cfg.max_files
        diffs = diffs[: cfg.max_files]

    start = time.time()
    all_comments: list[ReviewComment] = []
    errors: list[str] = []
    # Review files in parallel: latency ~ slowest file, not the sum.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(review_file, d, cfg): d for d in diffs}
        for fut, d in futures.items():
            try:
                comments, _ = fut.result()
                all_comments.extend(comments)
            except LLMError as e:
                errors.append(f"{d.path}: {e}")

    body = summary_body(all_comments, len(diffs), skipped, errors, cfg, time.time() - start)
    inline = [{"path": c.path, "line": c.line, "side": "RIGHT", "body": c.body()} for c in all_comments]

    if dry_run:
        print(body)
        for c in all_comments:
            print(f"\n{c.path}:{c.line}\n{c.body()}")
        return 0

    gh.post_review(pr_number, head_sha, body, inline)
    print(f"Posted review: {len(inline)} inline comment(s), {len(errors)} error(s).")
    return 1 if errors and not all_comments and len(errors) == len(diffs) else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="AI code review for GitHub pull requests")
    ap.add_argument("--repo", help="owner/name (defaults to the Actions event)")
    ap.add_argument("--pr", type=int, help="pull request number")
    ap.add_argument("--dry-run", action="store_true", help="print instead of posting")
    args = ap.parse_args()

    if args.repo and args.pr:
        repo, number, sha = args.repo, args.pr, None
    else:
        found = pr_from_event()
        if not found:
            sys.exit("No pull_request event found. Pass --repo and --pr to run locally.")
        repo, number, sha = found
    sys.exit(run(repo, number, sha, args.dry_run))


if __name__ == "__main__":
    main()
