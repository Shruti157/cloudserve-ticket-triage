"""Model client: pacing, caching, retries and a typed failure.

Three things here exist because of how the free tier actually behaves rather
than how it is documented.

First, the binding limit on Groq is tokens per minute, not requests per day.
The headers on a live account report 1,000 requests a day and 8,000 tokens a
minute, continuously refilling. That makes the per-minute bucket a floor on
wall-clock time rather than a ceiling on volume, so the pacer below spends
time deliberately instead of discovering a 429.

Second, gpt-oss models bill hidden reasoning as output tokens and return it in
a separate `reasoning` field. Reasoning effort is therefore set per task:
classification pays for it, generation does not, because the grounding
guardrail checks generation output regardless of how it was produced.

Third, every response is cached by content, model and prompt version from the
first call, because the set gets run several times.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import Config

log = logging.getLogger(__name__)

_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}


class ModelUnavailable(Exception):
    """The provider could not be reached or would not answer.

    Every caller handles this and returns a defined fallback. Nothing in the
    pipeline lets it propagate, because A11 is checked by disconnecting the
    provider entirely and watching the run continue.
    """


@dataclass
class Completion:
    text: str
    tokens: int
    cached: bool
    model: str


class _TokenPacer:
    """Spends the per-minute token allowance evenly instead of in bursts."""

    def __init__(self, tokens_per_minute: int) -> None:
        self.capacity = max(1, tokens_per_minute)
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, estimated: int) -> None:
        want = min(float(estimated), float(self.capacity))
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    float(self.capacity),
                    self._tokens + (now - self._last) * self.capacity / 60.0,
                )
                self._last = now
                if self._tokens >= want:
                    self._tokens -= want
                    return
                wait = (want - self._tokens) * 60.0 / self.capacity
            time.sleep(min(wait, 20.0))

    def refund(self, tokens: int) -> None:
        with self._lock:
            self._tokens = min(float(self.capacity), self._tokens + float(tokens))


class _ResponseCache:
    """Content-addressed cache. Keyed by model, prompt version and messages."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS completions ("
            " key TEXT PRIMARY KEY, text TEXT, tokens INTEGER, model TEXT, created_at REAL)"
        )
        self._conn.commit()
        self._lock = threading.Lock()

    @staticmethod
    def key(model: str, prompt_version: str, messages: list[dict[str, str]], extra: str) -> str:
        blob = json.dumps(
            {"m": model, "v": prompt_version, "msgs": messages, "x": extra},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> tuple[str, int, str] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT text, tokens, model FROM completions WHERE key = ?", (key,)
            ).fetchone()
        return row if row else None

    def put(self, key: str, text: str, tokens: int, model: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO completions VALUES (?,?,?,?,?)",
                (key, text, tokens, model, time.time()),
            )
            self._conn.commit()


class LLMClient:
    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self.config = config
        self.endpoint = _ENDPOINTS.get(config.provider, _ENDPOINTS["groq"])
        self._session = session or requests.Session()
        self._pacer = _TokenPacer(config.tokens_per_minute)
        self._cache = _ResponseCache(config.cache_path)
        self.calls_made = 0
        self.cache_hits = 0
        self.tokens_used = 0
        self.failures = 0

    @staticmethod
    def estimate_tokens(messages: list[dict[str, str]], max_tokens: int) -> int:
        chars = sum(len(m.get("content", "")) for m in messages)
        return int(chars / 3.6) + max_tokens + 40

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str,
        max_tokens: int = 700,
        temperature: float = 0.0,
        reasoning_effort: str = "low",
        use_cache: bool = True,
    ) -> Completion:
        """One completion, or ModelUnavailable. Never returns partial nonsense."""
        model = self.config.model_name
        key = self._cache.key(model, prompt_version, messages, f"{temperature}:{reasoning_effort}")

        if use_cache:
            hit = self._cache.get(key)
            if hit is not None:
                self.cache_hits += 1
                return Completion(text=hit[0], tokens=hit[1], cached=True, model=hit[2])

        if not self.config.has_credentials:
            raise ModelUnavailable(
                "No API key configured. Set GROQ_API_KEY in .env (see .env.example)."
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if "gpt-oss" in model:
            payload["reasoning_effort"] = reasoning_effort

        estimate = self.estimate_tokens(messages, max_tokens)
        last_error = "unknown"

        for attempt in range(1, self.config.max_attempts + 1):
            self._pacer.acquire(estimate)
            try:
                response = self._session.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.config.request_timeout_s,
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._pacer.refund(estimate)
                self._backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = float(response.headers.get("retry-after", 0) or 0)
                log.warning("Rate limited; waiting %.1fs", max(retry_after, 2.0))
                time.sleep(max(retry_after, 2.0) + attempt)
                last_error = "rate limited (429)"
                continue

            if response.status_code >= 500:
                last_error = f"provider error {response.status_code}"
                self._backoff(attempt)
                continue

            if response.status_code >= 400:
                # 400/401/404 will not improve with another attempt.
                raise ModelUnavailable(
                    f"Provider rejected the request ({response.status_code}): "
                    f"{response.text[:200]}"
                )

            try:
                body = response.json()
                choice = body["choices"][0]["message"]
                text = (choice.get("content") or "").strip()
                tokens = int(body.get("usage", {}).get("total_tokens", estimate))
            except (ValueError, KeyError, IndexError) as exc:
                last_error = f"unparseable response: {exc}"
                self._backoff(attempt)
                continue

            if not text:
                # gpt-oss spent the whole budget on hidden reasoning and emitted
                # nothing. Retrying with more room is cheaper than failing.
                last_error = "empty completion (reasoning consumed the budget)"
                payload["max_tokens"] = min(int(payload["max_tokens"] * 2), 2048)
                payload["reasoning_effort"] = "low"
                self.tokens_used += tokens
                continue

            self.calls_made += 1
            self.tokens_used += tokens
            if use_cache:
                self._cache.put(key, text, tokens, model)
            return Completion(text=text, tokens=tokens, cached=False, model=model)

        self.failures += 1
        raise ModelUnavailable(f"Gave up after {self.config.max_attempts} attempts: {last_error}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(2.0 ** attempt, 16.0))

    def stats(self) -> dict[str, int]:
        return {
            "llm_calls": self.calls_made,
            "cache_hits": self.cache_hits,
            "tokens_used": self.tokens_used,
            "failures": self.failures,
        }


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a completion.

    Models wrap JSON in prose and fences often enough that a bare json.loads is
    a reliability bug rather than a style choice.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = -1
    raise ValueError(f"No JSON object in completion: {text[:160]!r}")
