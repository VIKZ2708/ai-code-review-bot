"""Core review logic: prompt the LLM per file, then validate and filter its output."""

import json
import re
from dataclasses import dataclass

from .config import SEVERITY_RANK, Config
from .diff_parser import FileDiff
from .llm import complete

SYSTEM_PROMPT = """You are a senior software engineer reviewing a pull request.
You receive one file's diff. Lines are prefixed with the NEW file line number:
  '  42 + code'  = line added by this PR (you may comment on these)
  '  43   code'  = unchanged context (do NOT comment)
  '     - code'  = removed line (do NOT comment)

Find real problems only: bugs, security issues, performance problems, error handling
gaps, and clear maintainability issues. Do not comment on formatting or personal style.
If the change looks fine, return an empty list. Never invent line numbers.

Severity: critical = security hole, data loss or crash; major = likely bug or serious
perf issue; minor = worthwhile improvement.

Respond with JSON only:
{"comments": [{"line": <int>, "severity": "critical|major|minor",
  "category": "bug|security|performance|error-handling|maintainability",
  "comment": "<what is wrong and why, 1-2 sentences>",
  "suggestion": "<concrete fix or null>"}],
 "summary": "<one sentence about this file>"}"""


@dataclass
class ReviewComment:
    path: str
    line: int
    severity: str
    category: str
    comment: str
    suggestion: str | None = None

    def body(self) -> str:
        text = f"**[{self.severity.upper()}] {self.category}** — {self.comment}"
        if self.suggestion:
            text += f"\n\n💡 {self.suggestion}"
        return text


def build_user_prompt(diff: FileDiff, cfg: Config) -> str:
    prompt = f"File: {diff.path}\n\n```diff\n{diff.annotated[: cfg.max_patch_chars]}\n```"
    if len(diff.annotated) > cfg.max_patch_chars:
        prompt += "\n(diff truncated for length)"
    if cfg.rules:
        prompt += "\n\nTeam rules to enforce:\n" + "\n".join(f"- {r}" for r in cfg.rules)
    return prompt


def parse_response(raw: str) -> dict:
    """Parse model JSON, tolerating ```json fences or stray prose."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {"comments": [], "summary": ""}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"comments": [], "summary": ""}


def validate(data: dict, diff: FileDiff, cfg: Config) -> list[ReviewComment]:
    """Drop hallucinated lines, unknown severities, and low-severity noise."""
    min_rank = SEVERITY_RANK[cfg.min_severity]
    out: list[ReviewComment] = []
    for c in data.get("comments") or []:
        try:
            line = int(c.get("line"))
        except (TypeError, ValueError):
            continue
        sev = str(c.get("severity", "")).lower()
        if line not in diff.added_lines or sev not in SEVERITY_RANK:
            continue
        if SEVERITY_RANK[sev] < min_rank or not c.get("comment"):
            continue
        out.append(ReviewComment(
            path=diff.path, line=line, severity=sev,
            category=str(c.get("category", "general")),
            comment=str(c["comment"]).strip(),
            suggestion=(str(c["suggestion"]).strip() if c.get("suggestion") else None),
        ))
    out.sort(key=lambda c: (-SEVERITY_RANK[c.severity], c.line))
    return out[: cfg.max_comments_per_file]


def review_file(diff: FileDiff, cfg: Config) -> tuple[list[ReviewComment], str]:
    raw = complete(cfg.provider, cfg.model, SYSTEM_PROMPT, build_user_prompt(diff, cfg))
    data = parse_response(raw)
    return validate(data, diff, cfg), str(data.get("summary", ""))
