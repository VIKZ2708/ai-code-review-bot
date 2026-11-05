import json

from reviewer.config import Config
from reviewer.diff_parser import parse_file
from reviewer.review import parse_response, review_file, validate

DIFF = parse_file("a.py", "@@ -1,1 +1,3 @@\n x = 1\n+y = 2\n+z = 3")


def test_parse_response_handles_code_fences():
    raw = '```json\n{"comments": [], "summary": "ok"}\n```'
    assert parse_response(raw)["summary"] == "ok"


def test_parse_response_bad_json_is_empty():
    assert parse_response("not json")["comments"] == []


def test_validate_drops_hallucinated_lines_and_low_severity():
    data = {"comments": [
        {"line": 2, "severity": "major", "category": "bug", "comment": "real"},
        {"line": 99, "severity": "critical", "category": "bug", "comment": "made-up line"},
        {"line": 1, "severity": "critical", "category": "bug", "comment": "context line"},
        {"line": 3, "severity": "minor", "category": "style", "comment": "nit"},
    ]}
    out = validate(data, DIFF, Config(provider="mock", min_severity="major"))
    assert [c.line for c in out] == [2]


def test_validate_caps_and_sorts_by_severity():
    data = {"comments": [
        {"line": 2, "severity": "minor", "category": "x", "comment": "a"},
        {"line": 3, "severity": "critical", "category": "x", "comment": "b"},
    ]}
    out = validate(data, DIFF, Config(provider="mock", max_comments_per_file=1))
    assert len(out) == 1 and out[0].severity == "critical"


def test_mock_provider_end_to_end():
    diff = parse_file("s.py", '@@ -1,1 +1,2 @@\n DEBUG = False\n+DB_PASSWORD = "hunter2"')
    comments, _ = review_file(diff, Config(provider="mock"))
    assert comments and comments[0].line == 2 and comments[0].severity == "critical"
