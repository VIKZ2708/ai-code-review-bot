"""Measure reviewer quality on known-bad (and one known-good) diffs.

    python -m evals.run_evals --provider gemini

Recall    = planted issues the bot caught (within +/-1 line)
False pos = comments on the clean case, where nothing is wrong
"""

import argparse
import json
import pathlib
import sys

from reviewer.config import Config
from reviewer.diff_parser import parse_file
from reviewer.review import review_file

CASES = pathlib.Path(__file__).parent / "cases"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--model", default="")
    ap.add_argument("--min-recall", type=float, default=0.0, help="fail below this recall")
    args = ap.parse_args()
    cfg = Config(provider=args.provider, model=args.model)

    expected = caught = false_pos = 0
    print(f"{'case':<20} {'expected':>8} {'caught':>7} {'comments':>9}")
    for path in sorted(CASES.glob("*.json")):
        case = json.loads(path.read_text())
        diff = parse_file(case["filename"], case["patch"])
        comments, _ = review_file(diff, cfg)
        hits = sum(any(abs(c.line - e["line"]) <= 1 for c in comments) for e in case["expect"])
        expected += len(case["expect"])
        caught += hits
        if not case["expect"]:
            false_pos += len(comments)
        print(f"{path.stem:<20} {len(case['expect']):>8} {hits:>7} {len(comments):>9}")

    recall = caught / expected if expected else 1.0
    print(f"\nRecall: {caught}/{expected} = {recall:.0%}   False positives on clean code: {false_pos}")
    if recall < args.min_recall:
        sys.exit(f"Recall {recall:.0%} is below the required {args.min_recall:.0%}")


if __name__ == "__main__":
    main()
