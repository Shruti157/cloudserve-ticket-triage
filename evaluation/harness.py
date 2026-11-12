"""The unattended evaluation run (A9, A10).

    python -m evaluation.harness --input data/validation_tickets.json \
                                 --output evaluation/results/

Both paths are arguments. Neither is defaulted to a file in this repository,
because after submission this is pointed at a ticket file that does not exist
yet, and a harness that only works against its author's copy of the data
cannot be run at all.

The run is count-agnostic: it processes whatever is in the file, whether that
is one ticket or a thousand. The pack gives the hidden set as 100 in four
places and 120 in four others, so the harness simply does not care.

Nothing here intervenes. A ticket that fails is logged, escalated and counted,
and the loop continues; progress is printed to stderr so a throttled run can
be told apart from a hung one.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import __version__
from src.config import load_config
from src.ingest import load_corpus, load_tickets
from src.llm import LLMClient
from src.models import TicketOutcome
from src.pipeline import build_pipeline
from src.validate import _normalise_for_quote

from . import fairness, metrics

log = logging.getLogger("harness")


def check_citations(outcomes: list[TicketOutcome], index) -> dict[str, Any]:
    """Does each citation on a sent reply resolve to text in the corpus?

    This runs after the fact and independently of the guardrail, so that the
    reported figure is not simply the guardrail marking its own homework.
    """
    by_doc = {}
    for chunk in index.chunks:
        by_doc.setdefault(chunk.doc_id, "")
        by_doc[chunk.doc_id] += " " + _normalise_for_quote(chunk.text)

    checked = resolved = 0
    for outcome in outcomes:
        if not outcome.response_sent:
            continue
        for doc_id in outcome.citations:
            checked += 1
            if doc_id in by_doc and doc_id in outcome.retrieved_doc_ids:
                resolved += 1
    return {
        "checked": checked,
        "resolved": resolved,
        "accuracy_pct": round(100 * resolved / checked, 1) if checked else None,
        "note": (
            "A citation counts as accurate when the document exists in the "
            "corpus and was actually retrieved for that ticket. Whether the "
            "quoted span matches is enforced separately by the grounding "
            "guardrail, which blocks before sending."
        ),
    }


def build_truth(tickets) -> dict[str, dict[str, Any]]:
    """Labels, when the input file has them. The hidden set may not."""
    truth = {}
    for ticket in tickets:
        labels = ticket.raw.get("labels")
        if isinstance(labels, dict) and labels:
            truth[ticket.ticket_id] = labels
    return truth


def run(input_path: Path, output_dir: Path, limit: int | None = None) -> dict[str, Any]:
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    tickets = load_tickets(input_path)
    if limit:
        tickets = tickets[:limit]
    articles = load_corpus(config.corpus_path)

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)

    client = LLMClient(config)
    pipeline = build_pipeline(config, articles=articles, run_id=run_id, client=client)

    log.info(
        "Run %s: %d tickets from %s, %d corpus chunks, model %s, threshold %.2f",
        run_id,
        len(tickets),
        input_path,
        len(pipeline.index),
        config.model_name,
        config.confidence_threshold,
    )
    if not config.has_credentials:
        log.warning(
            "No API key is configured. The run will complete, but every ticket "
            "will escalate through the classifier's fallback path. This is the "
            "degraded mode required by A11, not a working evaluation."
        )

    started = time.time()
    outcomes: list[TicketOutcome] = []
    for i, ticket in enumerate(tickets, start=1):
        outcomes.append(pipeline.process(ticket))
        if i % 10 == 0 or i == len(tickets):
            elapsed = time.time() - started
            rate = i / max(elapsed, 1e-6)
            log.info(
                "%d/%d processed (%.1f/min, ~%.0fs remaining)",
                i,
                len(tickets),
                rate * 60,
                (len(tickets) - i) / max(rate, 1e-6),
            )
    wall_clock = time.time() - started

    truth = build_truth(tickets)
    reconciliation = pipeline.decisions.reconcile(len(outcomes))
    citations = check_citations(outcomes, pipeline.index)

    report: dict[str, Any] = {
        "run": {
            "run_id": run_id,
            "system_version": __version__,
            "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input_file": str(input_path),
            "tickets_in_file": len(tickets),
            "labels_present": bool(truth),
            "model": config.model_name,
            "provider": config.provider,
            "retrieval_backend": config.retrieval_backend,
            "confidence_threshold": config.confidence_threshold,
            "retrieval_min_score": config.retrieval_min_score,
            "retrieval_top_k": config.retrieval_top_k,
            "wall_clock_seconds": round(wall_clock, 1),
            "unattended": True,
            "model_calls": client.stats(),
            "tokens_per_ticket": round(client.tokens_used / max(1, len(outcomes)), 1),
        },
        "volume": metrics.volume(outcomes),
        "business": metrics.business(outcomes),
        "technical": metrics.technical(outcomes, truth, citations),
        "governance": metrics.governance(outcomes, reconciliation, truth),
        "calibration": metrics.calibration(outcomes, truth),
        "fairness": fairness.audit(outcomes, truth),
        "not_measured_automatically": metrics.NOT_MEASURABLE_AUTOMATICALLY,
    }

    (output_dir / "metrics_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Per-ticket outcomes carry no ticket subject or body, so they are safe to
    # commit; the response text is dropped for the same reason.
    per_ticket = []
    for outcome in outcomes:
        row = outcome.to_dict()
        row["response_text"] = ""
        row["response_chars"] = len(outcome.response_text)
        per_ticket.append(row)
    (output_dir / "per_ticket_outcomes.json").write_text(
        json.dumps(per_ticket, indent=2), encoding="utf-8"
    )

    (output_dir / "metrics_report.md").write_text(render_markdown(report), encoding="utf-8")
    pipeline.decisions.close()

    print(render_markdown(report))
    log.info("Wrote %s", output_dir / "metrics_report.json")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """A readable summary beside the JSON, because the JSON is for machines."""
    run = report["run"]
    volume = report["volume"]
    business = report["business"]
    technical = report["technical"]
    governance = report["governance"]
    lines = [
        f"# Evaluation run {run['run_id']}",
        "",
        f"System v{run['system_version']} · model `{run['model']}` via {run['provider']} · "
        f"{run['tickets_in_file']} tickets from `{run['input_file']}` · "
        f"{run['wall_clock_seconds']}s wall clock · "
        f"{run['tokens_per_ticket']} tokens/ticket.",
        "",
        "## Volume",
        "",
        f"| Measure | Count |",
        f"|---|---|",
        f"| Tickets processed | {volume['tickets_processed']} |",
        f"| Answered automatically | {volume['answered_automatically']} |",
        f"| Escalated | {volume['escalated']} |",
        f"| Blocked by a guardrail | {volume['blocked_by_guardrails']} |",
        f"| Processed in a degraded mode | {volume['degraded']} |",
        "",
        "## Business outcomes",
        "",
        "| Measure | Baseline | Target | This run |",
        "|---|---|---|---|",
        f"| First contact resolution | {business['first_contact_resolution_baseline_pct']}% "
        f"| {business['first_contact_resolution_target_pct']}% "
        f"| {business['first_contact_resolution_pct']}% |",
        f"| Escalation rate | {business['escalation_rate_baseline_pct']}% "
        f"| ≤{business['escalation_rate_target_pct']}% "
        f"| {business['escalation_rate_pct']}% |",
        f"| Mean time to first reply | 8–12 hrs | <5 min "
        f"| {business['mean_time_to_first_reply_minutes']} min |",
        f"| Median time to first reply | — | — "
        f"| {business['median_time_to_first_reply_minutes']} min |",
        "",
        "## Technical",
        "",
        "| Measure | Target | This run |",
        "|---|---|---|",
    ]
    classification = technical["classification"]
    if classification.get("available"):
        lines.append(
            f"| Classification precision (weighted) | 85% "
            f"| {classification['weighted_precision_pct']}% |"
        )
        lines.append(f"| Classification accuracy | — | {classification['accuracy_pct']}% |")
    if "retrieval" in technical:
        lines.append(f"| Retrieval hit rate | — | {technical['retrieval']['hit_rate_pct']}% |")
    lines += [
        f"| Citation accuracy | 95% | {technical['citation_accuracy_pct']}% "
        f"({technical['citations_checked']} checked) |",
        f"| Latency p95 | <3 s | {technical['latency_seconds']['p95']} s |",
        f"| Latency median | — | {technical['latency_seconds']['median']} s |",
        "",
        "## Governance",
        "",
        f"- Decisions logged: **{governance['decisions_logged']}** across "
        f"{governance['tickets_with_decisions']} tickets. Coverage complete: "
        f"**{governance['decision_log_coverage_complete']}**.",
        f"- Guardrail activations: "
        f"{governance['guardrail_activations'] or 'none'}.",
        f"- Private data detections in outbound text: "
        f"**{governance['private_data_detections']}**.",
        f"- Tickets auto-answered that must never be: "
        f"**{governance['must_not_auto_respond_breaches']}**.",
    ]
    calibration = report["calibration"]
    if calibration.get("available"):
        lines += [
            "",
            "## Confidence calibration",
            "",
            "| Band | Tickets | Stated | Observed | Gap |",
            "|---|---|---|---|---|",
        ]
        for band in calibration["bands"]:
            lines.append(
                f"| {band['band']} | {band['tickets']} | {band['stated_confidence_pct']}% "
                f"| {band['observed_accuracy_pct']}% | {band['gap_pct_points']} pts |"
            )
        lines.append("")
        lines.append(
            f"Largest gap **{calibration['largest_gap_pct_points']} points**; the governance "
            f"condition of five points is "
            f"{'met' if calibration['within_five_points'] else 'not met'}."
        )

    breaches = [f for f in report["fairness"]["findings"] if f["exceeds_five_point_condition"]]
    lines += [
        "",
        "## Fairness",
        "",
        f"Largest variation across any segment and measure: "
        f"**{report['fairness']['largest_variation_pct_points']} percentage points**.",
        "",
    ]
    if breaches:
        lines += ["| Dimension | Measure | Best | Worst | Spread | Beyond noise? |", "|---|---|---|---|---|---|"]
        for finding in sorted(breaches, key=lambda f: -f["spread_pct_points"])[:10]:
            lines.append(
                f"| {finding['dimension']} | {finding['measure']} "
                f"| {finding['best_group']} {finding['best_pct']}% "
                f"| {finding['worst_group']} {finding['worst_pct']}% "
                f"| {finding['spread_pct_points']} pts "
                f"| {'yes' if finding['intervals_separated'] else 'no, intervals overlap'} |"
            )
    else:
        lines.append("No segment exceeded the five point condition.")

    lines += [
        "",
        "## Not measured here, and why",
        "",
    ]
    for name, reason in report["not_measured_automatically"].items():
        lines.append(f"- **{name}** — {reason}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.harness",
        description="Process a ticket file end to end, unattended, and write a metrics report.",
    )
    parser.add_argument("--input", required=True, help="Path to a ticket JSON file.")
    parser.add_argument("--output", required=True, help="Directory for the report files.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only the first N tickets (smoke tests)."
    )
    args = parser.parse_args(argv)

    try:
        run(Path(args.input), Path(args.output), limit=args.limit)
    except Exception as exc:  # noqa: BLE001 - the operator needs a sentence, not a trace
        log.error("The run could not start: %s", exc)
        logging.getLogger().debug("", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
