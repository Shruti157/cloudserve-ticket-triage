"""Report the rate limits this account actually has, per model.

The published free-tier table and the limits a given key is issued are not the
same thing, and the limit that binds a run is not always the one named in the
429 text. This asks the provider directly: one near-empty request per model,
printing every x-ratelimit header that comes back.

Run it before tuning anything. Knowing whether requests-per-day,
tokens-per-minute or tokens-per-day binds tells you whether a slow run is a
code problem or an arithmetic one.

    python -m scripts.probe_limits
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]


def probe(model: str, key: str) -> dict[str, str]:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30,
    )
    found = {
        name.lower(): value
        for name, value in response.headers.items()
        if "ratelimit" in name.lower() or "retry" in name.lower()
    }
    found["status"] = str(response.status_code)
    if response.status_code >= 400:
        found["body"] = response.text[:400]
    return found


def main() -> None:
    load_dotenv(dotenv_path=".env")
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY is not set; copy .env.example to .env and fill it in.")

    for model in MODELS:
        print(f"\n=== {model}")
        for name, value in sorted(probe(model, key).items()):
            print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
