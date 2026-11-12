"""Compare chunking configurations and pick the relevance floor from data.

Run: python -m scripts.tune_retrieval

Measures, over the 500 development tickets:
  hit rate   - share of answerable tickets whose expected doc appears in top-k
  abstain    - share of answerable tickets for which nothing clears the floor
               (the cost of the "return nothing" decision, stated not defended)
  noise      - share of unanswerable tickets for which something clears the
               floor anyway (the cost of setting the floor too low)

Writes evaluation/results/retrieval_tuning.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import ROOT
from src.ingest import load_corpus, load_tickets
from src.retrieval import LexicalIndex


def evaluate(index: LexicalIndex, tickets, top_k: int, min_score: float) -> dict:
    hits = answerable = abstains = noise = unanswerable = 0
    for ticket in tickets:
        labels = ticket.raw.get("labels", {})
        expected = set(labels.get("expected_doc_ids") or [])
        passages = index.search(ticket.text, top_k=top_k, min_score=min_score)
        got = {p.doc_id for p in passages}
        if labels.get("answerable_from_docs") and expected:
            answerable += 1
            if expected & got:
                hits += 1
            if not passages:
                abstains += 1
        else:
            unanswerable += 1
            if passages:
                noise += 1
    return {
        "top_k": top_k,
        "min_score": min_score,
        "answerable": answerable,
        "hit_rate": round(100 * hits / max(1, answerable), 1),
        "abstain_rate_on_answerable": round(100 * abstains / max(1, answerable), 1),
        "noise_rate_on_unanswerable": round(100 * noise / max(1, unanswerable), 1),
    }


def main() -> None:
    tickets = load_tickets(ROOT / "data" / "development_tickets.json")
    articles = load_corpus(ROOT / "data" / "documentation.json")

    report = {"ticket_count": len(tickets), "configurations": []}
    for strategy in ("section", "document"):
        index = LexicalIndex(articles, strategy=strategy)
        for top_k in (1, 3, 5):
            for min_score in (0.0, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
                row = evaluate(index, tickets, top_k, min_score)
                row["strategy"] = strategy
                row["chunks"] = len(index)
                report["configurations"].append(row)
                print(
                    f"{strategy:9s} k={top_k} floor={min_score:.2f}  "
                    f"hit={row['hit_rate']:5.1f}%  "
                    f"abstain={row['abstain_rate_on_answerable']:5.1f}%  "
                    f"noise={row['noise_rate_on_unanswerable']:5.1f}%"
                )

    out = ROOT / "evaluation" / "results" / "retrieval_tuning.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
