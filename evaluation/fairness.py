"""The fairness audit, run per pipeline stage rather than only at the end.

Auditing only the final outcome describes a gap without saying who caused it.
A difference in resolution rate is a fairness problem when the system creates
it and an ordinary fact when the groups send different tickets, and the two
are separated by looking at each stage on its own. So retrieval, routing and
generation are each segmented, not just the outcome.

Routing is segmented even though the router cannot see a customer attribute.
That is the point: if the routing column shows a gap, it arrived through the
ticket text, and the explanation is upstream.

Small segments get a Wilson interval, because several of these groups are
small enough that a point estimate on its own overstates what was found.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from src.models import TicketOutcome

SEGMENTS: dict[str, Callable[[TicketOutcome], str]] = {
    "customer_tier": lambda o: o.customer_tier,
    "language_fluency": lambda o: o.language_fluency,
    "customer_region": lambda o: o.customer_region,
    "channel": lambda o: o.channel,
    # Boundaries are the quartiles measured on the development set, not round
    # numbers: these tickets run 28 to 276 characters, so a "long ticket" bucket
    # starting at 500 would have been empty and would have reported no variation.
    "ticket_length": lambda o: (
        "short (<140 chars)" if o.ticket_length < 140
        else "medium (140-181)" if o.ticket_length <= 181
        else "long (182+)"
    ),
}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a proportion, as a percentage."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denom
    return (round(100 * max(0.0, centre - spread), 1), round(100 * min(1.0, centre + spread), 1))


def _rate(outcomes: list[TicketOutcome], predicate: Callable[[TicketOutcome], bool]) -> dict:
    hits = sum(1 for o in outcomes if predicate(o))
    low, high = wilson_interval(hits, len(outcomes))
    return {
        "n": len(outcomes),
        "rate_pct": round(100 * hits / len(outcomes), 1) if outcomes else 0.0,
        "ci95": [low, high],
    }


def audit(
    outcomes: list[TicketOutcome], truth: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    truth = truth or {}
    report: dict[str, Any] = {"segments": {}, "findings": []}

    for name, key in SEGMENTS.items():
        groups: dict[str, list[TicketOutcome]] = {}
        for outcome in outcomes:
            groups.setdefault(key(outcome), []).append(outcome)

        rows = {}
        for group, items in sorted(groups.items()):
            row = {
                # Outcome
                "answered_automatically": _rate(items, lambda o: o.response_sent),
                # Per stage, so a gap can be attributed
                "retrieval_found_a_source": _rate(items, lambda o: bool(o.retrieved_doc_ids)),
                "routing_chose_to_answer": _rate(
                    items, lambda o: o.action in ("auto_respond", "blocked")
                ),
                "guardrail_blocked": _rate(items, lambda o: o.action == "blocked"),
                "mean_confidence": round(
                    sum(o.confidence for o in items) / max(1, len(items)), 3
                ),
            }
            if truth:
                labelled = [o for o in items if o.ticket_id in truth]
                if labelled:
                    row["classification_correct"] = _rate(
                        labelled, lambda o: truth[o.ticket_id].get("intent") == o.intent
                    )
                answerable = [
                    o
                    for o in labelled
                    if truth[o.ticket_id].get("expected_doc_ids")
                    and truth[o.ticket_id].get("answerable_from_docs")
                ]
                if answerable:
                    row["retrieval_hit"] = _rate(
                        answerable,
                        lambda o: bool(
                            set(truth[o.ticket_id]["expected_doc_ids"]) & set(o.retrieved_doc_ids)
                        ),
                    )
            rows[group] = row

        report["segments"][name] = rows
        report["findings"].extend(_findings(name, rows))

    report["largest_variation_pct_points"] = max(
        (f["spread_pct_points"] for f in report["findings"]), default=0.0
    )
    report["condition_under_five_points"] = report["largest_variation_pct_points"] < 5.0
    report["note"] = (
        "The condition in the Evaluation Framework is under five percentage "
        "points of variation. Where a gap exceeds it, the per-stage columns "
        "say which stage produced it, and the confidence intervals say whether "
        "the segment is large enough for the point estimate to mean anything."
    )
    return report


def _findings(dimension: str, rows: dict[str, dict]) -> list[dict[str, Any]]:
    out = []
    measures = {
        m
        for row in rows.values()
        for m, v in row.items()
        if isinstance(v, dict) and "rate_pct" in v
    }
    for measure in sorted(measures):
        values = {
            group: row[measure]
            for group, row in rows.items()
            if isinstance(row.get(measure), dict) and row[measure]["n"] >= 5
        }
        if len(values) < 2:
            continue
        best = max(values.items(), key=lambda kv: kv[1]["rate_pct"])
        worst = min(values.items(), key=lambda kv: kv[1]["rate_pct"])
        spread = round(best[1]["rate_pct"] - worst[1]["rate_pct"], 1)
        # Overlapping intervals mean the gap is not distinguishable from noise
        # at these sample sizes, which is worth saying rather than hiding.
        separated = worst[1]["ci95"][1] < best[1]["ci95"][0]
        out.append(
            {
                "dimension": dimension,
                "measure": measure,
                "best_group": best[0],
                "best_pct": best[1]["rate_pct"],
                "worst_group": worst[0],
                "worst_pct": worst[1]["rate_pct"],
                "spread_pct_points": spread,
                "exceeds_five_point_condition": spread >= 5.0,
                "intervals_separated": separated,
            }
        )
    return out
