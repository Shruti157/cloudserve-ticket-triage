"""Compare the candidate models on a stratified sample, then pick one.

Run: python -m scripts.compare_models [--sample 24]

Model choice on this project is a capacity decision as much as a quality one.
Groq meters a **tokens per day** budget *per model*, it is not reported in any
`x-ratelimit-*` header, and the only place it appears is the body of a 429.
For `openai/gpt-oss-20b` that budget is 200,000 tokens a day, so a model
costing 2,000 tokens a ticket cannot finish a 120-ticket run inside it.

So this measures accuracy and cost together and writes both.

Writes evaluation/results/model_comparison.json.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import replace

from src.classify import classify
from src.config import ROOT, load_config
from src.ingest import load_tickets
from src.llm import LLMClient, ModelUnavailable

CANDIDATES = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]

# A ticket-a-day budget is the figure that decides whether a model is usable,
# so it is computed rather than left as a token count nobody converts.
TOKENS_PER_DAY = 200_000
HIDDEN_SET_SIZE = 120


def stratified_sample(tickets, n: int):
    """Spread the sample across intents so one common class cannot dominate."""
    by_intent: dict[str, list] = {}
    for ticket in tickets:
        by_intent.setdefault(ticket.raw["labels"]["intent"], []).append(ticket)
    rng = random.Random(20261113)
    for group in by_intent.values():
        rng.shuffle(group)

    picked, i = [], 0
    while len(picked) < n:
        added = False
        for intent in sorted(by_intent):
            if i < len(by_intent[intent]) and len(picked) < n:
                picked.append(by_intent[intent][i])
                added = True
        if not added:
            break
        i += 1
    return picked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=24)
    args = parser.parse_args()

    base = load_config()
    tickets = stratified_sample(load_tickets(ROOT / "data" / "development_tickets.json"), args.sample)
    print(f"{len(tickets)} tickets, stratified across "
          f"{len({t.raw['labels']['intent'] for t in tickets})} intents\n")

    results = []
    for model in CANDIDATES:
        config = replace(base, model_name=model, max_attempts=2)
        client = LLMClient(config)
        correct = usable = 0
        started = time.time()
        error = ""
        for ticket in tickets:
            try:
                result = classify(ticket, client)
            except ModelUnavailable as exc:
                error = str(exc)[:160]
                break
            if result.source == "model":
                usable += 1
            if result.intent == ticket.raw["labels"]["intent"]:
                correct += 1

        attempted = max(1, usable or len(tickets))
        tokens_per_call = client.tokens_used / max(1, client.calls_made)
        # Two calls a ticket on an answered ticket, roughly 1.4 averaged over
        # the escalations that never reach generation.
        tokens_per_ticket = tokens_per_call * 1.4
        # A model whose daily budget is already spent returns fallbacks, and
        # its accuracy then measures the throttle rather than the model. Such
        # a row is kept — removing it would hide why it could not be measured
        # — but it is marked and excluded from the choice.
        comparable = usable == len(tickets)
        row = {
            "model": model,
            "tickets_attempted": len(tickets),
            "returned_a_usable_label": usable,
            "comparable": comparable,
            "caveat": (
                ""
                if comparable
                else f"Not comparable: only {usable} of {len(tickets)} tickets got a "
                f"real answer; the rest hit the provider's daily token budget and "
                f"fell back. The accuracy below measures the throttle, not the model."
            ),
            "accuracy_pct": round(100 * correct / len(tickets), 1),
            "tokens_per_call": round(tokens_per_call),
            "estimated_tokens_per_ticket": round(tokens_per_ticket),
            "estimated_tickets_per_day_on_free_tier": (
                int(TOKENS_PER_DAY / tokens_per_ticket) if tokens_per_ticket else None
            ),
            "can_run_the_hidden_set_in_one_day": (
                tokens_per_ticket * HIDDEN_SET_SIZE < TOKENS_PER_DAY
                if tokens_per_ticket else False
            ),
            "seconds": round(time.time() - started, 1),
            "error": error,
        }
        results.append(row)
        print(
            f"{model:30s} acc {row['accuracy_pct']:5.1f}%  "
            f"{row['tokens_per_call']:5d} tok/call  "
            f"~{row['estimated_tickets_per_day_on_free_tier']} tickets/day  "
            f"hidden set in one day: {row['can_run_the_hidden_set_in_one_day']}"
            + ("" if row["comparable"] else f"  [NOT COMPARABLE: {usable}/{len(tickets)} real]")
        )

    viable = [
        r
        for r in results
        if r["can_run_the_hidden_set_in_one_day"] and not r["error"] and r["comparable"]
    ]
    chosen = max(viable, key=lambda r: r["accuracy_pct"]) if viable else None

    report = {
        "sample_size": len(tickets),
        "sampling": "stratified by intent, seed 20261113",
        "tokens_per_day_budget": TOKENS_PER_DAY,
        "hidden_set_size_assumed": HIDDEN_SET_SIZE,
        "results": results,
        "chosen": chosen["model"] if chosen else None,
        "rationale": (
            "Chosen as the most accurate model that can process the hidden set "
            "inside one day's free token budget. Accuracy alone would not be "
            "the right criterion: a model that cannot finish the run fails the "
            "gate regardless of how well it classifies."
            if chosen
            else "No candidate could complete the hidden set within one day's budget."
        ),
    }
    out = ROOT / "evaluation" / "results" / "model_comparison.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nChosen: {report['chosen']}\nWrote {out}")


if __name__ == "__main__":
    main()
