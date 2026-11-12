"""Classification: intent, urgency and a numeric confidence (A3).

One model call over the fixed list of 22 labels rather than per-class
engineering. The interesting decisions are at the edges of that call:

A missing confidence is read as 0.0, never as high. When the provider dies the
classifier returns a defined fallback with confidence zero, which routes to a
human. The opposite convention — absent means fine — is the failure that sends
unreviewed answers during an outage.

The never-auto-respond classes are handled by rule rather than by threshold,
both before and after the model. A threshold is a statement about how sure the
model is, and a security incident the model is extremely sure about is exactly
the one that must still reach a person.
"""

from __future__ import annotations

import logging
import re

from .config import INTENT_CLASSES, NEVER_AUTO_RESPOND, URGENCY_LEVELS
from .llm import LLMClient, ModelUnavailable, extract_json
from .models import Classification, Ticket
from .prompts import load_prompt

log = logging.getLogger(__name__)

FALLBACK = Classification(
    intent="unclear_request",
    urgency="medium",
    confidence=0.0,
    alternatives=[],
    source="fallback",
    note="Classifier unavailable; routed to a human by the confidence floor.",
)

# Phrases that force an escalation regardless of what the model decides. These
# are deliberately narrow: each one names an outcome the system must never
# handle alone, not merely a topic it finds difficult.
_HARD_RULES: tuple[tuple[str, str, str], ...] = (
    (
        r"\b(breach|breached|compromis\w*|unauthoris?z?ed access|data leak|"
        r"exfiltrat\w*|ransom\w*|phish\w*)\b",
        "security_incident",
        "Possible security incident: the ticket reports a suspected compromise.",
    ),
    (
        r"\b(gdpr|hipaa|soc\s?2|iso\s?27001|dpa\b|right to be forgotten|"
        r"subject access request|data processing agreement)\b",
        "compliance_request",
        "Compliance request: the ticket invokes a regulatory obligation.",
    ),
    (
        r"\b(legal|lawyer|solicitor|sue|lawsuit|subpoena|regulator)\b",
        "compliance_request",
        "Legal exposure: the ticket raises a legal matter.",
    ),
)

_COMPILED = tuple((re.compile(p, re.IGNORECASE), label, reason) for p, label, reason in _HARD_RULES)


def apply_hard_rules(ticket: Ticket) -> Classification | None:
    """Pre-model escalation rules. Returns None when nothing fires."""
    if ticket.is_empty:
        return Classification(
            intent="unclear_request",
            urgency="low",
            confidence=0.0,
            source="rule",
            note="The ticket has no usable content.",
        )
    for pattern, label, reason in _COMPILED:
        if pattern.search(ticket.text):
            return Classification(
                intent=label,
                urgency="high" if label == "security_incident" else "medium",
                confidence=1.0,
                source="rule",
                note=reason,
            )
    return None


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if confidence > 1.0:
        # Models report 85 as often as 0.85 and the difference decides a route.
        confidence = confidence / 100.0 if confidence <= 100 else 1.0
    return max(0.0, min(1.0, confidence))


def _coerce_intent(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower().replace(" ", "_").replace("-", "_")
    return candidate if candidate in INTENT_CLASSES else None


def classify(ticket: Ticket, client: LLMClient) -> Classification:
    """Classify one ticket. Never raises."""
    rule = apply_hard_rules(ticket)
    if rule is not None:
        return rule

    prompt = load_prompt("PR-01")
    messages = prompt.render(
        intent_list="\n".join(f"- {label}" for label in INTENT_CLASSES),
        channel=ticket.channel,
        ticket_text=ticket.text[:4000],
    )

    try:
        completion = client.complete(
            messages,
            prompt_version=prompt.label,
            max_tokens=500,
            reasoning_effort="low",
        )
        data = extract_json(completion.text)
    except (ModelUnavailable, ValueError) as exc:
        log.warning("Classification degraded for %s: %s", ticket.ticket_id, exc)
        return Classification(
            intent=FALLBACK.intent,
            urgency=FALLBACK.urgency,
            confidence=0.0,
            source="fallback",
            note=f"{FALLBACK.note} ({type(exc).__name__})",
        )

    intent = _coerce_intent(data.get("intent"))
    if intent is None:
        return Classification(
            intent="unclear_request",
            urgency="medium",
            confidence=0.0,
            source="fallback",
            note=f"Model returned an unknown label {data.get('intent')!r}.",
        )

    urgency = str(data.get("urgency", "")).strip().lower()
    if urgency not in URGENCY_LEVELS:
        urgency = "medium"

    alternatives = []
    for item in data.get("alternatives") or []:
        if isinstance(item, dict):
            alt_intent = _coerce_intent(item.get("intent"))
            if alt_intent and alt_intent != intent:
                alternatives.append(
                    {"intent": alt_intent, "confidence": _coerce_confidence(item.get("confidence"))}
                )

    return Classification(
        intent=intent,
        urgency=urgency,
        confidence=_coerce_confidence(data.get("confidence")),
        alternatives=alternatives[:2],
        source="model",
        note=str(data.get("reason", ""))[:200],
    )


def is_never_auto(intent: str) -> bool:
    return intent in NEVER_AUTO_RESPOND
