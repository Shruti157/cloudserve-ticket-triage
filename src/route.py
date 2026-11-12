"""Routing: one pure function (A5).

Two properties are load-bearing and both are structural rather than tested
into existence.

It is pure. No file is read, no clock is consulted, no provider is called.
A5 is checked by running the same ticket twice and confirming the decision
does not change, and a function that reads the kill switch itself can decide
differently at two moments for identical inputs. The switch is therefore read
once per ticket at the pipeline edge and passed in as an argument.

It reads no customer attribute. Not tier, not region, not fluency, and not
the customer's name. The signature below cannot see them. That makes the
fairness claim about routing structural: there is no path by which routing
can treat an enterprise customer differently from a standard one. It does not
make the whole system fair — retrieval and generation still see the ticket
text, and that is where the audit in evaluation/fairness.py looks.
"""

from __future__ import annotations

from .config import NEVER_AUTO_RESPOND
from .models import Classification, Passage, RouteDecision


def decide(
    classification: Classification,
    passages: list[Passage],
    *,
    threshold: float,
    kill_switch_active: bool = False,
) -> RouteDecision:
    """Decide between answering and escalating. Deterministic by construction."""
    if kill_switch_active:
        return RouteDecision(
            action="escalate",
            reason=(
                "Automatic answering is switched off. The ticket has been queued "
                "for an agent with its classification and sources attached."
            ),
            threshold_applied=threshold,
            rule_fired="kill_switch",
        )

    if classification.intent in NEVER_AUTO_RESPOND:
        return RouteDecision(
            action="escalate",
            reason=(
                f"Tickets classified as {classification.intent.replace('_', ' ')} are "
                f"always handled by a person, however confident the classifier is. "
                f"{classification.note}".strip()
            ),
            threshold_applied=threshold,
            rule_fired="never_auto_respond",
        )

    if not passages:
        return RouteDecision(
            action="escalate",
            reason=(
                "No documentation passage was close enough to this question to "
                "support an answer, so there is nothing the system could say "
                "that it could also evidence."
            ),
            threshold_applied=threshold,
            rule_fired="no_supporting_source",
        )

    if classification.confidence < threshold:
        return RouteDecision(
            action="escalate",
            reason=(
                f"The classifier was {classification.confidence:.0%} sure this is a "
                f"{classification.intent.replace('_', ' ')}, below the {threshold:.0%} "
                f"bar for answering without review."
            ),
            threshold_applied=threshold,
            rule_fired="below_confidence_threshold",
        )

    return RouteDecision(
        action="auto_respond",
        reason=(
            f"Classified as {classification.intent.replace('_', ' ')} with "
            f"{classification.confidence:.0%} confidence, at or above the "
            f"{threshold:.0%} bar, and "
            f"{len(passages)} supporting documentation "
            f"{'passage' if len(passages) == 1 else 'passages'} "
            f"({', '.join(p.doc_id for p in passages)}) were found."
        ),
        threshold_applied=threshold,
        rule_fired="",
    )
