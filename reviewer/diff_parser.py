"""Parse GitHub PR patches into a line-numbered view the LLM can reference.

GitHub only accepts inline review comments on lines that appear in the diff,
so we track exactly which new-file line numbers were added by the PR.
"""

import re
from dataclasses import dataclass, field

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileDiff:
    path: str
    annotated: str
    added_lines: set[int] = field(default_factory=set)


def annotate_patch(patch: str) -> tuple[str, set[int]]:
    """Return (annotated_text, added_line_numbers).

    Added lines are shown as '  42 + code', context as '  43   code',
    removed lines as '     - code' (no new-file line number).
    """
    out: list[str] = []
    added: set[int] = set()
    new_line: int | None = None

    for raw in patch.splitlines():
        m = HUNK_RE.match(raw)
        if m:
            new_line = int(m.group(3))
            out.append(raw)
            continue
        if new_line is None or raw.startswith("\\"):
            continue  # preamble or "\ No newline at end of file"
        if raw.startswith("+"):
            out.append(f"{new_line:>5} + {raw[1:]}")
            added.add(new_line)
            new_line += 1
        elif raw.startswith("-"):
            out.append(f"      - {raw[1:]}")
        else:
            out.append(f"{new_line:>5}   {raw[1:]}")
            new_line += 1

    return "\n".join(out), added


def parse_file(path: str, patch: str) -> FileDiff:
    annotated, added = annotate_patch(patch)
    return FileDiff(path=path, annotated=annotated, added_lines=added)
