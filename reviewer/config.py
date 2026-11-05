"""Load reviewer settings from .ai-review.yml (all keys optional)."""

import fnmatch
import os
from dataclasses import dataclass, field

import yaml

DEFAULT_IGNORE = [
    "*.lock", "package-lock.json", "yarn.lock", "poetry.lock",
    "*.min.js", "*.map", "*.svg", "*.png", "*.jpg", "*.pdf",
    "dist/*", "build/*", "vendor/*",
]

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-4o-mini",
    "mock": "mock",
}

SEVERITY_RANK = {"minor": 1, "major": 2, "critical": 3}


@dataclass
class Config:
    provider: str = "gemini"
    model: str = ""
    max_files: int = 20
    max_patch_chars: int = 12000          # cost guard: truncate huge diffs
    max_comments_per_file: int = 5        # noise guard
    min_severity: str = "minor"
    ignore: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE))
    rules: list[str] = field(default_factory=list)  # team-specific rules

    def __post_init__(self):
        self.provider = self.provider.lower()
        if not self.model:
            self.model = DEFAULT_MODELS.get(self.provider, "")
        if self.min_severity not in SEVERITY_RANK:
            self.min_severity = "minor"

    def is_ignored(self, path: str) -> bool:
        name = os.path.basename(path)
        return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in self.ignore)


def load_config(path: str = ".ai-review.yml") -> Config:
    data: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    extra_ignore = data.pop("ignore", [])
    known = {k: v for k, v in data.items() if k in Config.__dataclass_fields__}
    cfg = Config(**known)
    cfg.ignore.extend(extra_ignore)
    # env overrides (handy for CI experiments)
    if os.getenv("AI_REVIEW_PROVIDER"):
        cfg = Config(**{**known, "provider": os.environ["AI_REVIEW_PROVIDER"], "model": os.getenv("AI_REVIEW_MODEL", "")})
        cfg.ignore.extend(extra_ignore)
    return cfg
