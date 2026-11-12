"""Induce each failure condition in A11 and record what the system did.

Run: python -m scripts.induce_failures

Every case below is induced against tickets the response cache has never
seen. That matters more than it sounds: an outage test run over tickets the
cache already holds is answered from the cache, the run looks healthy, and
the test proves nothing. Each case therefore uses its own unique ticket text.

Writes evaluation/results/resilience.json.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from src.config import ROOT, load_config
from src.decision_log import DecisionLog
from src.ingest import load_corpus, normalise_ticket
from src.llm import LLMClient, ModelUnavailable
from src.pipeline import Pipeline
from src.retrieval import LexicalIndex

MARKER = uuid.uuid4().hex[:8]


def _ticket(body: str, **kwargs):
    return normalise_ticket(
        {
            "ticket_id": kwargs.pop("ticket_id", f"RESILIENCE-{MARKER}"),
            "channel": "email",
            "subject": "",
            "body": body,
            **kwargs,
        }
    )


class DeadProvider(LLMClient):
    """A client whose endpoint does not exist. The real socket error path."""

    def __init__(self, config):
        super().__init__(config)
        self.endpoint = "http://127.0.0.1:9/v1/chat/completions"
        self.config = type(config)(**{**config.__dict__, "max_attempts": 1})


class SlowProvider(LLMClient):
    def complete(self, *args, **kwargs):
        raise ModelUnavailable(str(requests.Timeout("Read timed out after 60s")))


class RateLimitedProvider(LLMClient):
    def complete(self, *args, **kwargs):
        raise ModelUnavailable("Gave up after 4 attempts: rate limited (429)")


def make_pipeline(config, index, client, tmp: Path) -> Pipeline:
    return Pipeline(
        config=config,
        index=index,
        client=client,
        decisions=DecisionLog(tmp / f"resilience-{uuid.uuid4().hex[:6]}.db", run_id="resilience"),
    )


def main() -> None:
    config = load_config()
    index = LexicalIndex(load_corpus(config.corpus_path), strategy="section")
    tmp = ROOT / "storage" / "resilience"
    tmp.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []

    def record(name: str, condition: str, outcomes, started: float, expectation: str) -> None:
        cases.append(
            {
                "case": name,
                "condition_induced": condition,
                "expectation": expectation,
                "tickets": len(outcomes),
                "crashed": False,
                "actions": sorted({o.action for o in outcomes}),
                "all_escalated_or_answered": all(
                    o.action in ("auto_respond", "escalate", "blocked") for o in outcomes
                ),
                "every_ticket_has_a_reason": all(o.reason for o in outcomes),
                "degraded_flagged": sum(1 for o in outcomes if o.degraded),
                "confidences": sorted({o.confidence for o in outcomes}),
                "seconds": round(time.time() - started, 2),
                "example_reason": outcomes[0].reason[:200] if outcomes else "",
            }
        )
        print(f"  {name:28s} {cases[-1]['actions']}  {cases[-1]['seconds']}s")

    print("Inducing each A11 condition against uncached tickets...\n")

    # 1. The provider is disconnected entirely.
    started = time.time()
    pipeline = make_pipeline(config, index, DeadProvider(config), tmp)
    outcomes = [
        pipeline.process(_ticket(f"login fails {MARKER} case1 n{i}", ticket_id=f"R1-{MARKER}-{i}"))
        for i in range(3)
    ]
    record(
        "provider disconnected",
        "The model endpoint points at a closed port; the socket is refused.",
        outcomes,
        started,
        "Every ticket escalates with confidence 0.0 and the run continues.",
    )

    # 2. The provider times out.
    started = time.time()
    pipeline = make_pipeline(config, index, SlowProvider(config), tmp)
    outcomes = [
        pipeline.process(_ticket(f"webhook fails {MARKER} case2 n{i}", ticket_id=f"R2-{MARKER}-{i}"))
        for i in range(3)
    ]
    record(
        "provider timeout",
        "Every call raises a read timeout after the configured 60 seconds.",
        outcomes,
        started,
        "Same as an outage: escalate, flag degraded, continue.",
    )

    # 3. Rate limiting that does not clear.
    started = time.time()
    pipeline = make_pipeline(config, index, RateLimitedProvider(config), tmp)
    outcomes = [
        pipeline.process(_ticket(f"rate limit {MARKER} case3 n{i}", ticket_id=f"R3-{MARKER}-{i}"))
        for i in range(3)
    ]
    record(
        "rate limited after retries",
        "429 on every attempt, backoff exhausted.",
        outcomes,
        started,
        "Escalate rather than crash; the allowance is not burned further.",
    )

    # 4. Retrieval finds nothing. Real client, genuinely unanswerable question.
    started = time.time()
    pipeline = make_pipeline(config, index, LLMClient(config), tmp)
    outcomes = [
        pipeline.process(
            _ticket(
                f"zzzz qqqq {MARKER} vvvv xxxx jjjj kkkk",
                ticket_id=f"R4-{MARKER}",
            )
        )
    ]
    record(
        "no retrieval hit",
        "A query with no lexical overlap with any article.",
        outcomes,
        started,
        "Retrieval returns nothing and routing escalates with a readable reason.",
    )

    # 5. Malformed input.
    started = time.time()
    pipeline = make_pipeline(config, index, LLMClient(config), tmp)
    malformed = [
        {},
        {"ticket_id": f"R5-{MARKER}-a", "body": None, "channel": None},
        {"ticket_id": f"R5-{MARKER}-b", "body": "", "subject": ""},
        {"ticket_id": f"R5-{MARKER}-c", "body": "\x00\x07\ufeff \u202e control chars"},
        {"ticket_id": f"R5-{MARKER}-d", "channel": "carrier_pigeon", "body": "x" * 30000},
        {"ticket_id": f"R5-{MARKER}-e", "body": {"nested": "object where a string belongs"}},
    ]
    outcomes = [pipeline.process(normalise_ticket(r, i)) for i, r in enumerate(malformed)]
    record(
        "malformed input",
        "Empty, null, nested, oversized and control-character bodies.",
        outcomes,
        started,
        "Each produces a decision; none raises.",
    )

    # 6. The corpus is missing. This one must fail loudly rather than quietly.
    corpus_case: dict[str, Any] = {
        "case": "corpus missing",
        "condition_induced": "data/documentation.json is absent.",
        "expectation": (
            "This is the one condition that must NOT degrade. An empty index "
            "would process every ticket, escalate all of them for want of a "
            "passage, and report a completed run — a failure that looks like "
            "success. A named exception is raised at startup instead."
        ),
    }
    try:
        load_corpus(ROOT / "data" / "this_file_does_not_exist.json")
        corpus_case["raised"] = False
        corpus_case["result"] = "FAILED: no exception was raised"
    except Exception as exc:
        corpus_case["raised"] = True
        corpus_case["exception"] = type(exc).__name__
        corpus_case["message"] = str(exc)
        corpus_case["result"] = "correct: refused to start with an empty index"
    cases.append(corpus_case)
    print(f"  {'corpus missing':28s} {corpus_case['result']}")

    report = {
        "marker": MARKER,
        "note": (
            "Each case uses ticket text containing a run-unique marker, so the "
            "response cache cannot serve a previous answer and make an outage "
            "look like a healthy run."
        ),
        "cases": cases,
        "all_conditions_survived": all(
            c.get("all_escalated_or_answered", True) and not c.get("crashed", False)
            for c in cases
        ),
    }
    out = ROOT / "evaluation" / "results" / "resilience.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nAll conditions survived: {report['all_conditions_survived']}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
