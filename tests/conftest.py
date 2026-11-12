"""Shared fixtures.

The suite runs without an API key and without a network. A fake client stands
in for the provider, which is what makes the tests runnable in CI on a fork
with no secrets — and incidentally makes the outage tests honest, because a
suite that needs the provider cannot test losing it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import ROOT, load_config
from src.decision_log import DecisionLog
from src.ingest import load_corpus
from src.llm import Completion, LLMClient, ModelUnavailable
from src.pipeline import Pipeline
from src.retrieval import LexicalIndex


class FakeClient:
    """Stands in for LLMClient. Returns canned JSON, or raises on demand.

    Replies are keyed on which prompt arrived rather than on call order,
    because a ticket that escalates never reaches generation and a positional
    queue would then hand the next ticket a generation reply to a
    classification request. That is a property of the fake, not of the system.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        raises: Exception | None = None,
        *,
        classify: str | None = None,
        generate: str | None = None,
    ):
        self.responses = list(responses or [])
        self.by_stage = {"classification": classify, "generation": generate}
        self.raises = raises
        self.calls_made = 0
        self.cache_hits = 0
        self.tokens_used = 0
        self.failures = 0
        self.seen: list[list[dict[str, str]]] = []

    def complete(self, messages, **kwargs) -> Completion:
        self.seen.append(messages)
        if self.raises is not None:
            self.failures += 1
            raise self.raises
        self.calls_made += 1
        self.tokens_used += 100
        stage = (
            "classification"
            if "triage classifier" in messages[0]["content"]
            else "generation"
        )
        text = self.by_stage.get(stage) or (self.responses.pop(0) if self.responses else "{}")
        return Completion(text=text, tokens=100, cached=False, model="fake")

    def stats(self):
        return {
            "llm_calls": self.calls_made,
            "cache_hits": self.cache_hits,
            "tokens_used": self.tokens_used,
            "failures": self.failures,
        }


@pytest.fixture(scope="session")
def articles() -> list[dict]:
    return load_corpus(ROOT / "data" / "documentation.json")


@pytest.fixture(scope="session")
def index(articles) -> LexicalIndex:
    return LexicalIndex(articles, strategy="section")


@pytest.fixture
def config(tmp_path):
    cfg = load_config()
    return type(cfg)(
        provider="groq",
        api_key="test-key-not-real",
        model_name="test-model",
        retrieval_backend="lexical",
        database_path=tmp_path / "decisions.db",
        cache_path=tmp_path / "cache.sqlite",
        corpus_path=ROOT / "data" / "documentation.json",
        confidence_threshold=0.75,
        retrieval_top_k=3,
        retrieval_min_score=0.45,
        kill_switch_path=tmp_path / "KILL_SWITCH",
    )


@pytest.fixture
def make_pipeline(config, index):
    def _make(client):
        return Pipeline(
            config=config,
            index=index,
            client=client,
            decisions=DecisionLog(config.database_path, run_id="test-run"),
        )

    return _make


@pytest.fixture(scope="session")
def dev_tickets() -> list[dict]:
    return json.loads((ROOT / "data" / "development_tickets.json").read_text())


CLASSIFY_OK = json.dumps(
    {
        "intent": "authentication_failure",
        "urgency": "high",
        "confidence": 0.93,
        "alternatives": [{"intent": "account_access", "confidence": 0.2}],
        "reason": "Invalid credentials on login.",
    }
)
