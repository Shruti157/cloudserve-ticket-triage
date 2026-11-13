"""Metrics, calculated by the code at the end of the run (A10).

Two of the Evaluation Framework's measures are deliberately left empty here.
Customer satisfaction and hallucination rate both require human judgement —
the framework asks for fifty responses assessed by two independent people with
an agreement rate — and an automated harness that fills those cells produces
something that looks like a measurement and is not. They are reported as null
with the reason attached, and the sampled single-assessor figures are in the
report where their limitations can be stated.

Everything else is computed from the run's own outcomes and, where labels are
present in the input file, from those labels. The harness runs unchanged
against a file with no labels; the sections that need them are simply absent.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable

from src.config import INTENT_CLASSES, NEVER_AUTO_RESPOND
from src.models import TicketOutcome

# CloudServe's current position, from the Project Brief and the Evaluation
# Framework. Reported beside every achieved figure so a number never appears
# without the thing it is supposed to improve on.
BASELINE = {
    "first_contact_resolution_pct": 42.0,
    "mean_time_to_first_reply_minutes": 600.0,
    "escalation_rate_pct": 58.0,
    "satisfaction": 3.2,
}
TARGET = {
    "first_contact_resolution_pct": 60.0,
    "mean_time_to_first_reply_minutes": 5.0,
    "escalation_rate_pct": 30.0,
    "satisfaction": 4.0,
    "classification_precision_pct": 85.0,
    "citation_accuracy_pct": 95.0,
    "hallucination_rate_pct": 5.0,
    "latency_p95_s": 3.0,
}

NOT_MEASURABLE_AUTOMATICALLY = {
    "satisfaction_proxy": (
        "Requires human review against a rubric. The framework asks for two "
        "independent assessors; this project has one. The sampled figure and "
        "its limitations are in the report rather than here, because a number "
        "produced automatically would imply a method that was not used."
    ),
    "hallucination_rate_pct": (
        "Requires human judgement over at least fifty responses by two "
        "assessors. The automated proxy that comes closest is "
        "citation_accuracy_pct, which is reported above and measures a "
        "narrower thing: whether each citation quotes the passage it names."
    ),
    "repeat_contact_rate_pct": (
        "Needs a week of subsequent traffic from the same customers. A single "
        "evaluation run over a static file cannot observe it."
    ),
}


def _pct(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return round(ordered[index], 3)


def volume(outcomes: list[TicketOutcome]) -> dict[str, Any]:
    blocked = [o for o in outcomes if o.action == "blocked"]
    answered = [o for o in outcomes if o.response_sent]
    escalated = [o for o in outcomes if not o.response_sent]
    return {
        "tickets_processed": len(outcomes),
        "answered_automatically": len(answered),
        "escalated": len(escalated),
        "blocked_by_guardrails": len(blocked),
        "degraded": sum(1 for o in outcomes if o.degraded),
        "by_channel": dict(sorted(_count(o.channel for o in outcomes).items())),
    }


def business(outcomes: list[TicketOutcome]) -> dict[str, Any]:
    """Business outcomes, which lead the report rather than trail it.

    First contact resolution is counted as a ticket answered automatically
    with no human involvement. That is the system's own definition and it is
    an upper bound on the real figure: a reply that is sent and does not solve
    the problem counts here and would not count at CloudServe. The report says
    so where the figure appears.
    """
    answered = [o for o in outcomes if o.response_sent]
    reply_minutes = [o.latency_s / 60.0 for o in answered]
    return {
        "first_contact_resolution_pct": _pct(len(answered), len(outcomes)),
        "first_contact_resolution_baseline_pct": BASELINE["first_contact_resolution_pct"],
        "first_contact_resolution_target_pct": TARGET["first_contact_resolution_pct"],
        "escalation_rate_pct": _pct(len(outcomes) - len(answered), len(outcomes)),
        "escalation_rate_baseline_pct": BASELINE["escalation_rate_pct"],
        "escalation_rate_target_pct": TARGET["escalation_rate_pct"],
        "mean_time_to_first_reply_minutes": (
            round(statistics.mean(reply_minutes), 3) if reply_minutes else None
        ),
        "median_time_to_first_reply_minutes": (
            round(statistics.median(reply_minutes), 3) if reply_minutes else None
        ),
        "mean_time_to_first_reply_baseline_minutes": BASELINE["mean_time_to_first_reply_minutes"],
        "note": (
            "Time to first reply is the system's own processing latency. It "
            "excludes the queueing a production deployment would add and is "
            "therefore a floor, not a forecast."
        ),
    }


def classification_report(
    outcomes: list[TicketOutcome], truth: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Per-class precision and recall, plus the confusion pairs that matter.

    Written out rather than imported from scikit-learn: the only thing needed
    is this table, and a 60-megabyte dependency for it would be paid for by
    every person who installs the project from the README.
    """
    pairs = [
        (truth[o.ticket_id]["intent"], o.intent)
        for o in outcomes
        if o.ticket_id in truth and truth[o.ticket_id].get("intent")
    ]
    if not pairs:
        return {"available": False, "reason": "The input file carries no intent labels."}

    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    confusions: dict[tuple[str, str], int] = defaultdict(int)
    for actual, predicted in pairs:
        if actual == predicted:
            tp[actual] += 1
        else:
            fp[predicted] += 1
            fn[actual] += 1
            confusions[(actual, predicted)] += 1

    per_class = {}
    for label in INTENT_CLASSES:
        support = tp[label] + fn[label]
        if not support and not fp[label]:
            continue
        precision = _pct(tp[label], tp[label] + fp[label])
        recall = _pct(tp[label], support)
        per_class[label] = {
            "support": support,
            "precision_pct": precision,
            "recall_pct": recall,
            "f1_pct": round(
                2 * precision * recall / (precision + recall), 1
            ) if precision + recall else 0.0,
        }

    correct = sum(1 for a, p in pairs if a == p)
    weighted_precision = (
        sum(v["precision_pct"] * v["support"] for v in per_class.values())
        / max(1, sum(v["support"] for v in per_class.values()))
    )
    return {
        "available": True,
        "labelled_tickets": len(pairs),
        "accuracy_pct": _pct(correct, len(pairs)),
        "weighted_precision_pct": round(weighted_precision, 1),
        "macro_precision_pct": round(
            sum(v["precision_pct"] for v in per_class.values()) / max(1, len(per_class)), 1
        ),
        "macro_recall_pct": round(
            sum(v["recall_pct"] for v in per_class.values()) / max(1, len(per_class)), 1
        ),
        "target_precision_pct": TARGET["classification_precision_pct"],
        "per_class": dict(sorted(per_class.items())),
        "top_confusions": [
            {"actual": a, "predicted": p, "count": n}
            for (a, p), n in sorted(confusions.items(), key=lambda kv: -kv[1])[:10]
        ],
    }


def technical(
    outcomes: list[TicketOutcome], truth: dict[str, dict[str, Any]], citation_checks: dict[str, Any]
) -> dict[str, Any]:
    latencies = [o.latency_s for o in outcomes]
    # Latency with the free-tier wait removed. The target of three seconds is
    # a statement about the system; time spent queueing behind a token
    # allowance is a statement about the tier it was run on, and a single
    # number that mixes them cannot be acted on by either audience.
    working = [max(0.0, o.latency_s - o.throttle_s) for o in outcomes]
    live = [
        max(0.0, o.latency_s - o.throttle_s) for o in outcomes if o.llm_calls and not o.cache_hits
    ]
    report: dict[str, Any] = {
        "classification": classification_report(outcomes, truth),
        "latency_seconds": {
            "mean": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "median": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3) if latencies else 0.0,
            "target_p95": TARGET["latency_p95_s"],
            "excluding_free_tier_wait": {
                "median": round(statistics.median(working), 3) if working else 0.0,
                "p95": _percentile(working, 0.95),
            },
            "live_calls_only_excluding_wait": {
                "tickets": len(live),
                "median": round(statistics.median(live), 3) if live else None,
                "p95": _percentile(live, 0.95) if live else None,
            },
            "note": (
                "Three figures, because they answer different questions. The "
                "first is what a customer on this free tier would experience. "
                "The second removes the token-allowance wait. The third counts "
                "only tickets answered by a live call, excluding cache hits, "
                "and is the one to compare against the three second target."
            ),
        },
        "citation_accuracy_pct": citation_checks.get("accuracy_pct"),
        "citation_target_pct": TARGET["citation_accuracy_pct"],
        "citations_checked": citation_checks.get("checked", 0),
    }

    labelled = [o for o in outcomes if o.ticket_id in truth]
    answerable = [
        o
        for o in labelled
        if truth[o.ticket_id].get("answerable_from_docs")
        and truth[o.ticket_id].get("expected_doc_ids")
    ]
    if answerable:
        hits = sum(
            1
            for o in answerable
            if set(truth[o.ticket_id]["expected_doc_ids"]) & set(o.retrieved_doc_ids)
        )
        abstains = sum(1 for o in answerable if not o.retrieved_doc_ids)
        report["retrieval"] = {
            "answerable_tickets": len(answerable),
            "hit_rate_pct": _pct(hits, len(answerable)),
            "abstain_rate_on_answerable_pct": _pct(abstains, len(answerable)),
        }
        unanswerable = [
            o for o in labelled if not truth[o.ticket_id].get("answerable_from_docs")
        ]
        if unanswerable:
            report["retrieval"]["correct_abstain_on_unanswerable_pct"] = _pct(
                sum(1 for o in unanswerable if not o.retrieved_doc_ids), len(unanswerable)
            )

    routed = [o for o in labelled if truth[o.ticket_id].get("expected_route")]
    if routed:
        agree = sum(
            1
            for o in routed
            if (o.action == "auto_respond") == (truth[o.ticket_id]["expected_route"] == "auto_respond")
        )
        over = sum(
            1
            for o in routed
            if o.action == "auto_respond" and truth[o.ticket_id]["expected_route"] == "escalate"
        )
        under = sum(
            1
            for o in routed
            if o.action != "auto_respond" and truth[o.ticket_id]["expected_route"] == "auto_respond"
        )
        report["routing"] = {
            "agreement_with_expected_route_pct": _pct(agree, len(routed)),
            "answered_when_a_human_was_expected": over,
            "escalated_when_an_answer_was_expected": under,
            "note": (
                "The two error columns are not interchangeable. Answering when "
                "a human was expected reaches a customer; escalating when an "
                "answer was expected costs agent time."
            ),
        }
    return report


def governance(
    outcomes: list[TicketOutcome],
    reconciliation: dict[str, Any],
    truth: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    activations: dict[str, int] = defaultdict(int)
    checks_run: dict[str, int] = defaultdict(int)
    for outcome in outcomes:
        for finding in outcome.guardrails:
            checks_run[finding["name"]] += 1
            if finding["status"] == "block":
                activations[finding["name"]] += 1

    # The governance condition that is pass or fail rather than a target: a
    # class the dataset marks must_not_auto_respond must never be answered.
    breaches = [
        o.ticket_id
        for o in outcomes
        if o.response_sent
        and (
            o.intent in NEVER_AUTO_RESPOND
            or truth.get(o.ticket_id, {}).get("must_not_auto_respond")
        )
    ]

    return {
        "decisions_logged": reconciliation["total_decisions"],
        "tickets_with_decisions": reconciliation["tickets_with_decisions"],
        "decision_log_coverage_complete": reconciliation["coverage_complete"],
        "decisions_by_stage": reconciliation["by_stage"],
        "guardrail_checks_run": dict(sorted(checks_run.items())),
        "guardrail_activations": dict(sorted(activations.items())),
        "private_data_detections": activations.get("private_data", 0),
        "must_not_auto_respond_breaches": len(breaches),
        "must_not_auto_respond_breach_ids": breaches[:20],
    }


def calibration(outcomes: list[TicketOutcome], truth: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Stated confidence against observed accuracy, per band.

    This is the check that decides whether the routing threshold is a safety
    control or decoration, and it is the one most often skipped. A threshold
    on a miscalibrated score is not made safer by raising it.
    """
    rows = [
        (o.confidence, truth[o.ticket_id]["intent"] == o.intent)
        for o in outcomes
        if o.ticket_id in truth and truth[o.ticket_id].get("intent")
    ]
    if not rows:
        return {"available": False, "reason": "The input file carries no intent labels."}

    bands = []
    worst_gap = 0.0
    for i in range(5):
        low, high = i / 5, (i + 1) / 5
        group = [r for r in rows if low <= r[0] < high or (i == 4 and r[0] == 1.0)]
        if not group:
            continue
        stated = round(100 * sum(c for c, _ in group) / len(group), 1)
        observed = round(100 * sum(1 for _, ok in group if ok) / len(group), 1)
        worst_gap = max(worst_gap, abs(stated - observed))
        bands.append(
            {
                "band": f"{low:.1f}-{high:.1f}",
                "tickets": len(group),
                "stated_confidence_pct": stated,
                "observed_accuracy_pct": observed,
                "gap_pct_points": round(stated - observed, 1),
            }
        )
    return {
        "available": True,
        "bands": bands,
        "largest_gap_pct_points": round(worst_gap, 1),
        "within_five_points": worst_gap <= 5.0,
        "condition": "Governance condition: stated confidence within five points of observed.",
    }


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(counts)
