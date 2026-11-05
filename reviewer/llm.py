"""Thin, dependency-light LLM clients (plain HTTP) with retries.

Each provider returns the raw text of the model's reply, which we ask to be JSON.
"""

import json
import os
import time

import requests


class LLMError(Exception):
    pass


def _post(url: str, headers: dict, body: dict, retries: int = 3) -> dict:
    for attempt in range(retries):
        resp = requests.post(url, headers=headers, json=body, timeout=90)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 529) and attempt < retries - 1:
            time.sleep(2 ** attempt * 2)  # 2s, 4s backoff
            continue
        raise LLMError(f"{resp.status_code}: {resp.text[:300]}")
    raise LLMError("retries exhausted")


def _key(name: str) -> str:
    key = os.getenv(name)
    if not key:
        raise LLMError(f"Missing {name} environment variable")
    return key


def _gemini(model: str, system: str, user: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    data = _post(url, {"x-goog-api-key": _key("GEMINI_API_KEY")}, body)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected Gemini response: {json.dumps(data)[:300]}") from e


def _anthropic(model: str, system: str, user: str) -> str:
    headers = {"x-api-key": _key("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"}
    body = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0.2,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = _post("https://api.anthropic.com/v1/messages", headers, body)
    return "".join(b.get("text", "") for b in data.get("content", []))


def _openai(model: str, system: str, user: str) -> str:
    headers = {"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"}
    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    data = _post("https://api.openai.com/v1/chat/completions", headers, body)
    return data["choices"][0]["message"]["content"]


def _mock(model: str, system: str, user: str) -> str:
    """Deterministic fake reviewer for tests and offline demos.

    Flags any added line containing obvious red flags.
    """
    comments = []
    for line in user.splitlines():
        parts = line.split(" + ", 1)
        if len(parts) != 2 or not parts[0].strip().isdigit():
            continue
        num, code = int(parts[0]), parts[1]
        if "password" in code.lower() and "=" in code and ('"' in code or "'" in code):
            comments.append({"line": num, "severity": "critical", "category": "security",
                             "comment": "Hardcoded secret.", "suggestion": "Read it from an environment variable."})
        elif "execute(" in code and ("f\"" in code or "%" in code or "+" in code):
            comments.append({"line": num, "severity": "critical", "category": "security",
                             "comment": "Possible SQL injection.", "suggestion": "Use parameterized queries."})
    return json.dumps({"comments": comments, "summary": "Mock review."})


PROVIDERS = {"gemini": _gemini, "anthropic": _anthropic, "openai": _openai, "mock": _mock}


def complete(provider: str, model: str, system: str, user: str) -> str:
    fn = PROVIDERS.get(provider)
    if not fn:
        raise LLMError(f"Unknown provider '{provider}'. Choose from {list(PROVIDERS)}")
    return fn(model, system, user)
