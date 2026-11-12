"""A1, A9, A10, A12: the harness takes paths, produces a report, and the API runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evaluation import fairness, metrics
from evaluation.harness import main, render_markdown
from src.models import TicketOutcome


def _tickets(n: int) -> list[dict]:
    channels = ["email", "chat", "docs_comment", "forum"]
    return [
        {
            "ticket_id": f"SYN-{i:04d}",
            "channel": channels[i % 4],
            "subject": "" if channels[i % 4] == "chat" else "Cannot sign in",
            "body": "I cannot sign in to the console, it reports invalid credentials.",
            "received_at": "2026-11-12T09:00:00Z",
            "customer_tier": ["standard", "business", "enterprise"][i % 3],
            "customer_region": "europe",
            "language_fluency": "fluent" if i % 4 else "non_fluent",
            "labels": {
                "intent": "authentication_failure",
                "urgency": "high",
                "expected_route": "auto_respond",
                "answerable_from_docs": True,
                "expected_doc_ids": ["DOC-AUTH-001"],
                "must_not_auto_respond": False,
            },
        }
        for i in range(n)
    ]


def test_the_harness_takes_an_input_and_an_output_path_it_has_never_seen(tmp_path, monkeypatch):
    """The gate points this at a file that does not exist today."""
    monkeypatch.setenv("GROQ_API_KEY", "")  # no network, so every ticket degrades
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/decisions.db")
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.sqlite"))

    unseen = tmp_path / "a_file_the_author_never_saw.json"
    unseen.write_text(json.dumps(_tickets(6)))
    output = tmp_path / "out"

    assert main(["--input", str(unseen), "--output", str(output)]) == 0

    report = json.loads((output / "metrics_report.json").read_text())
    assert report["run"]["tickets_in_file"] == 6
    assert report["volume"]["tickets_processed"] == 6
    assert (output / "per_ticket_outcomes.json").exists()
    assert (output / "metrics_report.md").exists()


def test_the_report_contains_every_group_the_build_specification_names(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/d.db")
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "c.sqlite"))
    source = tmp_path / "in.json"
    source.write_text(json.dumps(_tickets(4)))
    output = tmp_path / "out"
    main(["--input", str(source), "--output", str(output)])

    report = json.loads((output / "metrics_report.json").read_text())
    assert {"volume", "business", "technical", "governance"} <= set(report)
    assert {"tickets_processed", "answered_automatically", "escalated", "blocked_by_guardrails"} <= set(
        report["volume"]
    )
    assert "first_contact_resolution_pct" in report["business"]
    assert "median_time_to_first_reply_minutes" in report["business"]
    assert "escalation_rate_pct" in report["business"]
    assert "latency_seconds" in report["technical"]
    assert "p95" in report["technical"]["latency_seconds"]
    assert "decisions_logged" in report["governance"]
    assert "guardrail_activations" in report["governance"]
    assert "private_data_detections" in report["governance"]


def test_a_run_with_no_credentials_completes_rather_than_refusing(tmp_path, monkeypatch):
    """A11: the provider being gone is a degraded run, not a failed start."""
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/d.db")
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "c.sqlite"))
    source = tmp_path / "in.json"
    source.write_text(json.dumps(_tickets(5)))
    output = tmp_path / "out"

    assert main(["--input", str(source), "--output", str(output)]) == 0
    report = json.loads((output / "metrics_report.json").read_text())
    assert report["volume"]["tickets_processed"] == 5
    assert report["volume"]["escalated"] == 5
    assert report["governance"]["decision_log_coverage_complete"]


def test_a_missing_input_file_reports_a_sentence_and_a_non_zero_exit(tmp_path):
    assert main(["--input", str(tmp_path / "nope.json"), "--output", str(tmp_path / "o")]) == 1


def test_an_empty_input_file_is_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/d.db")
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "c.sqlite"))
    source = tmp_path / "empty.json"
    source.write_text("[]")
    assert main(["--input", str(source), "--output", str(tmp_path / "o")]) == 0


# --------------------------------------------------------------------- metrics


def _outcome(**kwargs) -> TicketOutcome:
    base = dict(
        ticket_id="T",
        channel="email",
        customer_tier="standard",
        customer_region="europe",
        language_fluency="fluent",
        intent="billing_query",
        urgency="low",
        confidence=0.9,
        action="auto_respond",
        reason="r",
        response_sent=True,
        latency_s=1.0,
    )
    base.update(kwargs)
    return TicketOutcome(**base)


def test_satisfaction_and_hallucination_are_left_unmeasured_with_a_reason():
    assert "satisfaction_proxy" in metrics.NOT_MEASURABLE_AUTOMATICALLY
    assert "hallucination_rate_pct" in metrics.NOT_MEASURABLE_AUTOMATICALLY
    for reason in metrics.NOT_MEASURABLE_AUTOMATICALLY.values():
        assert len(reason) > 40


def test_business_metrics_report_both_mean_and_median():
    outcomes = [_outcome(ticket_id=str(i), latency_s=float(i)) for i in range(1, 11)]
    result = metrics.business(outcomes)
    assert result["mean_time_to_first_reply_minutes"] is not None
    assert result["median_time_to_first_reply_minutes"] is not None
    assert result["first_contact_resolution_pct"] == 100.0
    assert result["escalation_rate_pct"] == 0.0


def test_classification_report_is_per_class_not_only_overall():
    outcomes = [
        _outcome(ticket_id="a", intent="billing_query"),
        _outcome(ticket_id="b", intent="rate_limit"),
    ]
    truth = {"a": {"intent": "billing_query"}, "b": {"intent": "billing_query"}}
    report = metrics.classification_report(outcomes, truth)
    assert report["available"]
    assert "billing_query" in report["per_class"]
    assert report["per_class"]["billing_query"]["recall_pct"] == 50.0
    assert report["top_confusions"]


def test_metrics_work_on_a_file_with_no_labels():
    outcomes = [_outcome(ticket_id="a")]
    assert metrics.classification_report(outcomes, {})["available"] is False
    assert metrics.calibration(outcomes, {})["available"] is False


def test_fairness_audit_reports_intervals_and_segments_each_stage():
    outcomes = [
        _outcome(ticket_id=str(i), language_fluency="fluent" if i % 2 else "non_fluent")
        for i in range(40)
    ]
    report = fairness.audit(outcomes, {})
    assert "language_fluency" in report["segments"]
    row = next(iter(report["segments"]["language_fluency"].values()))
    assert {"retrieval_found_a_source", "routing_chose_to_answer", "guardrail_blocked"} <= set(row)
    assert row["answered_automatically"]["ci95"][0] <= row["answered_automatically"]["rate_pct"]


def test_wilson_interval_is_wider_for_a_smaller_sample():
    narrow = fairness.wilson_interval(80, 100)
    wide = fairness.wilson_interval(8, 10)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_the_markdown_report_states_what_was_not_measured():
    report = {
        "run": {
            "run_id": "r", "system_version": "1", "model": "m", "provider": "p",
            "tickets_in_file": 1, "input_file": "f", "wall_clock_seconds": 1.0,
            "tokens_per_ticket": 1.0,
        },
        "volume": {
            "tickets_processed": 1, "answered_automatically": 1, "escalated": 0,
            "blocked_by_guardrails": 0, "degraded": 0,
        },
        "business": metrics.business([_outcome()]),
        "technical": metrics.technical([_outcome()], {}, {"accuracy_pct": None, "checked": 0}),
        "governance": metrics.governance(
            [_outcome()],
            {"total_decisions": 4, "tickets_with_decisions": 1, "coverage_complete": True,
             "by_stage": {}},
            {},
        ),
        "calibration": {"available": False},
        "fairness": fairness.audit([_outcome()], {}),
        "not_measured_automatically": metrics.NOT_MEASURABLE_AUTOMATICALLY,
    }
    text = render_markdown(report)
    assert "Not measured here" in text
    assert "hallucination_rate_pct" in text


# ------------------------------------------------------------------------- API


@pytest.fixture(scope="module")
def api_client():
    from src.api import app

    with TestClient(app) as client:
        yield client


def test_health_reports_the_corpus_is_loaded(api_client):
    body = api_client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["corpus_chunks"] > 29
    assert body["automatic_answering_enabled"] in (True, False)


def test_the_metrics_endpoint_serves_prometheus_text(api_client):
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert "cloudserve_tickets_total" in response.text


def test_the_ticket_endpoint_accepts_a_minimal_body(api_client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    response = api_client.post("/ticket", json={"body": "I cannot sign in", "channel": "chat"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] in ("auto_respond", "escalate", "blocked")
    assert "guardrails" in payload
    assert payload["reason"]
