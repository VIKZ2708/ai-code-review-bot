# AI Code Review Bot

An LLM-powered reviewer that runs on GitHub Actions. When a pull request is opened or updated, it reads the diff, asks an LLM to find real problems (bugs, security holes, performance issues), and posts **inline comments** on the exact lines, plus a summary.

Works with **Gemini** (free tier), **Claude**, or **OpenAI**.

## How it works

```
PR opened / pushed
      │
      ▼
GitHub Action ──► fetch changed files (GitHub API)
      │
      ├─ skip lock files, binaries, deleted files, ignored paths
      ├─ annotate each diff with new-file line numbers
      │
      ▼
LLM review per file (in parallel, JSON output)
      │
      ▼
validate ──► drop invented line numbers, low-severity noise, cap per file
      │
      ▼
post one review: inline comments + severity summary
```

## Design decisions

| Problem | What the bot does |
|---|---|
| LLMs invent line numbers | Every diff line is prefixed with its real line number; comments on lines the PR didn't add are dropped. |
| Unreliable output format | JSON mode where the provider supports it, plus tolerant parsing (code fences, stray text). |
| Noise / false positives | Prompt forbids style nitpicks, `min_severity` threshold, max comments per file. |
| Cost | Only the diff is sent (not whole files), huge diffs are truncated, lock files and binaries are skipped. |
| Latency | Files are reviewed in parallel; a new push cancels the in-progress review. |
| Security | The workflow runs the reviewer from the **base** branch, so a PR can't modify the bot to leak secrets. Least-privilege token permissions. |
| Reliability | Retries with backoff on rate limits; if GitHub rejects an inline comment, the feedback is posted as a regular comment instead. |
| Team standards | Custom `rules` in `.ai-review.yml` are added to the prompt. |

## Setup (5 minutes)

1. Copy `reviewer/`, `requirements.txt`, `.ai-review.yml` and `.github/workflows/ai-review.yml` into your repo.
2. Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, name `GEMINI_API_KEY`.
4. Open a pull request.

To use Claude or OpenAI instead, set `provider: anthropic` or `provider: openai` in `.ai-review.yml` and add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.

## Configuration

```yaml
provider: gemini          # gemini | anthropic | openai
model: gemini-2.5-flash   # optional override
min_severity: minor       # minor | major | critical
max_files: 20
max_comments_per_file: 5
ignore: ["docs/*"]
rules:
  - Database queries must use parameters, never string formatting.
```

## Evaluation

`evals/cases/` holds diffs with planted bugs (SQL injection, hardcoded secret, mutable default argument, resource leak, division by zero) and one clean change to catch false positives.

```bash
GEMINI_API_KEY=... python -m evals.run_evals --provider gemini
```

It reports **recall** (planted issues caught) and **false positives** on clean code. CI runs the evals offline with a mock provider; run them with a real key before changing the prompt.

## Run locally

```bash
pip install -r requirements-dev.txt
pytest -q
GITHUB_TOKEN=... GEMINI_API_KEY=... python -m reviewer.main --repo owner/name --pr 1 --dry-run
```

## Project layout

```
reviewer/
  main.py           entry point (Actions or CLI)
  diff_parser.py    line-numbered diffs, valid comment lines
  review.py         prompt, JSON parsing, validation
  llm.py            Gemini / Claude / OpenAI clients with retries
  github_client.py  PR files, posting reviews
  config.py         .ai-review.yml loading
evals/              quality benchmark
tests/              unit tests
```

## Next steps

- Send related files as context (callers, tests) for deeper reviews
- Cache reviews per commit to skip unchanged files on re-push
- Let developers reply "/ai-review ignore" to mute a comment
