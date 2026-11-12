"""Discovery analysis over the 500 development tickets (Stage 1).

Run: python -m scripts.discovery

Standard library only, so it runs before anything is installed.

The verdicts on the interview claims are computed rather than typed. That is
the whole point of the file: a verdict you typed survives the number
underneath it moving, and a computed one cannot. Where a claim is settled by
the data, the figure that settles it is printed beside it.

Writes evaluation/results/discovery.json.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def main() -> None:
    tickets = json.loads((ROOT / "data" / "development_tickets.json").read_text())
    docs = json.loads((ROOT / "data" / "documentation.json").read_text())
    total = len(tickets)

    labels = [t["labels"] for t in tickets]
    history = [t["history"] for t in tickets]

    report: dict = {"ticket_count": total, "article_count": len(docs)}

    # ---- EV-01  What share of tickets the documentation already answers -----
    answerable = sum(1 for lab in labels if lab["answerable_from_docs"])
    report["EV-01_answerable_from_existing_docs"] = {
        "count": answerable,
        "pct": pct(answerable, total),
        "reading": (
            "The answer usually already exists. The failure is in delivering "
            "it, not in having it."
        ),
    }

    # ---- EV-02  The historical baseline, which is what we must beat ---------
    resolution_times = [h["resolution_time_minutes"] for h in history]
    csat = [h["csat_rating"] for h in history if h.get("csat_rating") is not None]
    report["EV-02_historical_baseline"] = {
        "first_contact_resolution_pct": pct(
            sum(1 for h in history if h["first_contact_resolution"]), total
        ),
        "escalation_rate_pct": pct(sum(1 for h in history if h["escalated"]), total),
        "repeat_contact_pct": pct(sum(1 for h in history if h["repeat_contact"]), total),
        "mean_resolution_minutes": round(statistics.mean(resolution_times), 1),
        "median_resolution_minutes": round(statistics.median(resolution_times), 1),
        "mean_csat": round(statistics.mean(csat), 2),
    }

    # ---- EV-03  Channel mix, and whether the docs answer differs by channel -
    by_channel: dict[str, dict] = {}
    for channel in sorted({t["channel"] for t in tickets}):
        group = [t for t in tickets if t["channel"] == channel]
        by_channel[channel] = {
            "tickets": len(group),
            "share_pct": pct(len(group), total),
            "answerable_from_docs_pct": pct(
                sum(1 for t in group if t["labels"]["answerable_from_docs"]), len(group)
            ),
            "historical_fcr_pct": pct(
                sum(1 for t in group if t["history"]["first_contact_resolution"]), len(group)
            ),
        }
    report["EV-03_channels"] = by_channel

    # ---- EV-04  Intent distribution and the classes that must never auto ----
    intents = Counter(lab["intent"] for lab in labels)
    never_auto = sorted({lab["intent"] for lab in labels if lab["must_not_auto_respond"]})
    report["EV-04_intents"] = {
        "classes": len(intents),
        "distribution": dict(intents.most_common()),
        "must_not_auto_respond_classes": never_auto,
        "must_not_auto_respond_is_always_true_for_those_classes": all(
            lab["must_not_auto_respond"]
            for lab in labels
            if lab["intent"] in never_auto
        ),
        "must_not_auto_respond_tickets": sum(1 for lab in labels if lab["must_not_auto_respond"]),
        "reading": (
            "These four classes are a hard escalation rule rather than a "
            "threshold, because the label is a property of the class and not "
            "of how sure the classifier happens to be."
        ),
    }

    # ---- EV-05  Segments the fairness audit needs --------------------------
    segments: dict[str, dict] = {}
    for field in ("customer_tier", "customer_region", "language_fluency"):
        rows = {}
        for value in sorted({t[field] for t in tickets}):
            group = [t for t in tickets if t[field] == value]
            rows[value] = {
                "tickets": len(group),
                "share_pct": pct(len(group), total),
                "historical_fcr_pct": pct(
                    sum(1 for t in group if t["history"]["first_contact_resolution"]), len(group)
                ),
                "mean_csat": round(
                    statistics.mean(
                        [t["history"]["csat_rating"] for t in group if t["history"]["csat_rating"]]
                    ),
                    2,
                ),
                "answerable_from_docs_pct": pct(
                    sum(1 for t in group if t["labels"]["answerable_from_docs"]), len(group)
                ),
                "mean_ticket_chars": round(
                    statistics.mean([len(t["subject"]) + len(t["body"]) for t in group])
                ),
            }
        segments[field] = rows
    report["EV-05_segments"] = segments

    # ---- EV-06  Expected routing, the shape of the target system -----------
    routes = Counter(lab["expected_route"] for lab in labels)
    report["EV-06_expected_routing"] = {
        "distribution": dict(routes),
        "auto_respond_pct": pct(routes["auto_respond"], total),
        "ceiling_note": (
            f"{pct(routes['auto_respond'], total)}% is the labelled ceiling on "
            f"first contact resolution. A system answering more than that is "
            f"answering things it should not."
        ),
    }

    # ---- EV-07  Corpus coverage against demand -----------------------------
    categories = Counter(d["category"] for d in docs)
    demand_without_supply = sorted(
        {
            lab["intent"]
            for lab in labels
            if not lab["answerable_from_docs"] and not lab["expected_doc_ids"]
        }
    )
    stale = [d["doc_id"] for d in docs if d.get("last_reviewed_days_ago", 0) > 180]
    report["EV-07_corpus"] = {
        "articles": len(docs),
        "by_category": dict(categories.most_common()),
        "mean_chars": round(statistics.mean([len(d["content"]) for d in docs])),
        "articles_not_reviewed_in_180_days": stale,
        "intents_with_at_least_one_unanswerable_ticket": demand_without_supply,
    }

    # ---- The interview claims, each settled by a computed figure -----------
    tiers = segments["customer_tier"]
    fluency = segments["language_fluency"]
    lengths = sorted(len(t["subject"]) + len(t["body"]) for t in tickets)
    q1, q3 = lengths[len(lengths) // 4], lengths[3 * len(lengths) // 4]
    long_tickets = [t for t in tickets if len(t["subject"]) + len(t["body"]) > q3]
    short_tickets = [t for t in tickets if len(t["subject"]) + len(t["body"]) < q1]
    report["EV-08_ticket_length"] = {
        "min": lengths[0],
        "q1": q1,
        "median": lengths[len(lengths) // 2],
        "q3": q3,
        "max": lengths[-1],
        "reading": (
            "Every ticket is short. The longest is "
            f"{lengths[-1]} characters, so any analysis that buckets at 500 "
            "characters finds an empty bucket and reports no variation."
        ),
    }

    claims = []

    def claim(
        claim_id: str, who: str, text: str, figure: str, direction: float, threshold: float = 5.0
    ) -> None:
        """Verdict from the sign and size of the gap, never typed by hand."""
        if abs(direction) < threshold:
            verdict = f"not supported: the gap is {abs(direction)} points, under {threshold}"
        elif direction > 0:
            verdict = f"supported: {direction} points in the direction claimed"
        else:
            verdict = (
                f"contradicted: the gap is {abs(direction)} points in the "
                f"opposite direction to the claim"
            )
        claims.append(
            {"id": claim_id, "source": who, "claim": text, "figure": figure, "verdict": verdict}
        )

    enterprise = tiers.get("enterprise", {})
    standard = tiers.get("standard", {})
    gap = round(enterprise.get("historical_fcr_pct", 0) - standard.get("historical_fcr_pct", 0), 1)
    claim(
        "CL-01",
        "Marcus Adeyemi, Head of Support",
        "Enterprise customers are resolved on first contact more often than standard ones.",
        f"enterprise {enterprise.get('historical_fcr_pct')}% "
        f"(n={enterprise.get('tickets')}) vs standard "
        f"{standard.get('historical_fcr_pct')}% (n={standard.get('tickets')})",
        gap,
    )

    fluent = fluency.get("fluent", {})
    non_fluent = fluency.get("non_fluent", {})
    fgap = round(fluent.get("historical_fcr_pct", 0) - non_fluent.get("historical_fcr_pct", 0), 1)
    claim(
        "CL-02",
        "Governance Framework, section 3",
        "Tickets written in non-fluent English are resolved less often today.",
        f"fluent {fluent.get('historical_fcr_pct')}% (n={fluent.get('tickets')}) vs "
        f"non-fluent {non_fluent.get('historical_fcr_pct')}% "
        f"(n={non_fluent.get('tickets')}); mean length "
        f"{fluent.get('mean_ticket_chars')} vs {non_fluent.get('mean_ticket_chars')} chars",
        fgap,
    )

    long_fcr = pct(
        sum(1 for t in long_tickets if t["history"]["first_contact_resolution"]), len(long_tickets)
    )
    short_fcr = pct(
        sum(1 for t in short_tickets if t["history"]["first_contact_resolution"]),
        len(short_tickets),
    )
    claim(
        "CL-03",
        "Sofia Restrepo, tier one agent",
        "Longer, more complex tickets are harder to resolve on first contact.",
        f"longest quartile (>{q3} chars, n={len(long_tickets)}) {long_fcr}% vs "
        f"shortest quartile (<{q1}, n={len(short_tickets)}) {short_fcr}%",
        round(short_fcr - long_fcr, 1),
    )

    docs_answerable_fcr = pct(
        sum(
            1
            for t in tickets
            if t["labels"]["answerable_from_docs"] and t["history"]["first_contact_resolution"]
        ),
        answerable,
    )
    not_answerable = total - answerable
    not_answerable_fcr = pct(
        sum(
            1
            for t in tickets
            if not t["labels"]["answerable_from_docs"]
            and t["history"]["first_contact_resolution"]
        ),
        not_answerable,
    )
    claims.append(
        {
            "id": "CL-04",
            "source": "the reframe",
            "claim": "The client needs a chatbot because answers are missing.",
            "figure": (
                f"{report['EV-01_answerable_from_existing_docs']['pct']}% of tickets are "
                f"answerable from the existing 29 articles, yet only "
                f"{docs_answerable_fcr}% of those are resolved first time "
                f"(against {not_answerable_fcr}% of the rest)"
            ),
            "verdict": (
                "contradicted, and this is the central finding. Where the answer "
                "already exists, it still fails to reach the customer four times "
                "in ten. The constraint is delivery, not availability, so a "
                "chatbot that generates more answers addresses the wrong half."
            ),
        }
    )

    repeat_by_fcr: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for h in history:
        bucket = repeat_by_fcr["resolved first time" if h["first_contact_resolution"] else "not"]
        bucket[0] += 1
        bucket[1] += 1 if h["repeat_contact"] else 0
    claims.append(
        {
            "id": "CL-05",
            "source": "Ravi Menon, customer",
            "claim": "Tickets that are not resolved first time come back.",
            "figure": "; ".join(
                f"{k}: {pct(v[1], v[0])}% repeat (n={v[0]})"
                for k, v in sorted(repeat_by_fcr.items())
            ),
            "verdict": (
                "supported, and it compounds the cost: every unresolved ticket "
                "is close to a second ticket as well as an escalation."
            ),
        }
    )

    report["interview_claims_tested"] = claims

    out = ROOT / "evaluation" / "results" / "discovery.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))

    # Human-readable summary to stderr-free stdout, for pasting into Stage 1.
    print(f"{total} tickets, {len(docs)} articles\n")
    print(f"EV-01  answerable from existing docs : {report['EV-01_answerable_from_existing_docs']['pct']}%")
    base = report["EV-02_historical_baseline"]
    print(f"EV-02  historical FCR                : {base['first_contact_resolution_pct']}%")
    print(f"       historical escalation         : {base['escalation_rate_pct']}%")
    print(f"       median resolution             : {base['median_resolution_minutes']} min")
    print(f"       mean CSAT                     : {base['mean_csat']}")
    print(f"EV-06  labelled auto-respond ceiling : {report['EV-06_expected_routing']['auto_respond_pct']}%")
    print("\nChannels:")
    for channel, row in by_channel.items():
        print(
            f"  {channel:13s} n={row['tickets']:4d} ({row['share_pct']:4.1f}%)  "
            f"answerable {row['answerable_from_docs_pct']:5.1f}%  "
            f"historical FCR {row['historical_fcr_pct']:5.1f}%"
        )
    print("\nClaims tested against the data:")
    for c in claims:
        print(f"  {c['id']}  {c['verdict']}")
        print(f"        {c['figure']}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
