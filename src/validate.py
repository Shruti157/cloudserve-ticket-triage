"""Guardrails (A7).

Five checks run on every generated response, in the pipeline and not only in
the tests. There is no flag, no environment variable and no configuration key
that disables any of them, and `run_guardrails` takes no parameter that could
weaken it. A guardrail a run can switch off does not satisfy A7, and one that
only warns is not a guardrail.

Each check returns pass, block or not_applicable, and every result is recorded
whether or not it blocked, because the question asked after an incident is
what the system checked, not only what it caught.

A blocked response is never redacted and sent. It is escalated with the
finding attached, because redaction assumes the detector found everything.
"""

from __future__ import annotations

import re
import unicodedata

from .models import Classification, GeneratedResponse, GuardrailFinding, Passage, Ticket

# --- Private data -----------------------------------------------------------
# Patterns are deliberately broad. A false positive costs one escalation; a
# false negative is a governance condition failed.
_PII_PATTERNS: tuple[tuple[str, str], ...] = (
    ("email_address", r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"),
    ("api_key_or_token", r"\b(?:sk|pk|gsk|rk|ghp|xox[baprs])[-_][A-Za-z0-9_-]{8,}\b"),
    ("bearer_token", r"\b[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ("payment_card", r"\b(?:\d[ -]?){13,19}\b"),
    ("other_customer_id", r"\bCUST-\d{3,}\b"),
    ("phone_number", r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]\d{3,4}(?:[\s.-]\d{3,4})?(?!\d)"),
    ("postal_address", r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr)\b"),
    ("national_id", r"\b\d{3}-\d{2}-\d{4}\b"),
)
_PII = tuple((name, re.compile(pattern)) for name, pattern in _PII_PATTERNS)

# --- Commitments the system may not make ------------------------------------
_COMMITMENT = re.compile(
    r"\b("
    r"refund(?:ed|ing)?|credit(?:ed)? your account|compensat\w+|reimburs\w+|"
    r"waive[ds]?\s+(?:the\s+)?(?:fee|charge)|"
    r"(?:i|we)\s+(?:have\s+)?(?:already\s+)?(?:escalated|raised a ticket|opened a case)|"
    r"(?:i|we)\s+(?:will|'ll|shall)\s+(?:fix|resolve|deploy|call|phone|ring|refund|"
    r"credit|compensate|contact you|get back to you|follow up)|"
    r"guarantee\w*|"
    r"(?:within|in)\s+(?:the\s+next\s+)?\d+\s*(?:hours?|days?|weeks?|business days?)|"
    r"by (?:tomorrow|monday|tuesday|wednesday|thursday|friday|the end of the (?:day|week))"
    r")\b",
    re.IGNORECASE,
)

# --- Instruction integrity ---------------------------------------------------
_INJECTION_IN_TICKET = re.compile(
    r"("
    r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instruction|prompt|rule|direction)s?|"
    r"disregard\s+(?:your|the|all)\s+(?:instruction|rule|prompt|guideline)s?|"
    r"you\s+are\s+now\s+(?:a|an)\s+|"
    r"act\s+as\s+(?:if\s+you\s+are\s+)?(?:a|an|the)\s+|"
    r"(?:reveal|print|repeat|show|output)\s+(?:your|the)\s+"
    r"(?:system\s+)?(?:prompt|instructions?|rules)|"
    r"\bdeveloper\s+mode\b|\bjailbreak\b|"
    r"</?(?:system|instruction)>|\[/?(?:SYSTEM|INST)\]"
    r")",
    re.IGNORECASE,
)
# Signs the instructions leaked into the customer-facing text.
_LEAKED_SCAFFOLDING = re.compile(
    r"(<<<TICKET|<<<END TICKET|--- PASSAGE \d|\[SYSTEM\]|"
    r"You are a triage classifier|You write support replies for CloudServe|"
    r"reference passages supplied below|Hard rules\.)",
    re.IGNORECASE,
)

_WORD = re.compile(r"[a-z0-9]+")


def _normalise_for_quote(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return " ".join(_WORD.findall(text))


def check_private_data(response_text: str, passages: list[Passage]) -> GuardrailFinding:
    """Block if the outbound text carries identifying data.

    Anything that appears verbatim in a retrieved passage is exempt: the
    documentation is already published, so repeating it back is not a
    disclosure. Everything else is treated as a disclosure, including data the
    customer themselves supplied, because the reply may be read by somebody
    other than the person who wrote the ticket.
    """
    if not response_text:
        return GuardrailFinding("private_data", "not_applicable", "No outbound text.")

    corpus = " ".join(p.text for p in passages)
    found: list[str] = []
    for name, pattern in _PII:
        for match in pattern.finditer(response_text):
            value = match.group(0).strip()
            if value and value in corpus:
                continue
            if name == "payment_card" and not _looks_like_card(value):
                continue
            found.append(f"{name}: {value[:24]}")

    if found:
        return GuardrailFinding(
            "private_data",
            "block",
            "Identifying data in the outbound reply: " + "; ".join(sorted(set(found))[:5]),
        )
    return GuardrailFinding("private_data", "pass", "No identifying data detected.")


def _looks_like_card(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 13 <= len(digits) <= 19:
        return False
    total, even = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if even:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        even = not even
    return total % 10 == 0


def check_grounding(
    response: GeneratedResponse,
    claims: list[dict[str, str]],
    passages: list[Passage],
) -> GuardrailFinding:
    """Block unless every citation quotes a retrieved passage verbatim.

    Naming a document that exists is not evidence. The quote is compared after
    whitespace, case and punctuation are normalised, so the model is held to
    the words and not to the typography.
    """
    if not response.answered or not response.body:
        return GuardrailFinding("grounding", "not_applicable", "No answer was drafted.")

    if not claims:
        return GuardrailFinding(
            "grounding", "block", "The reply makes claims but carries no citation."
        )

    retrieved = {p.doc_id: _normalise_for_quote(p.text) for p in passages}
    problems: list[str] = []
    for claim in claims:
        doc_id = claim["doc_id"]
        if doc_id not in retrieved:
            problems.append(f"{doc_id} was cited but never retrieved for this ticket")
            continue
        quote = _normalise_for_quote(claim.get("quote", ""))
        if len(quote.split()) < 6:
            problems.append(f"{doc_id} is cited with a quote too short to verify")
        elif quote not in retrieved[doc_id]:
            problems.append(f"the span attributed to {doc_id} is not in that passage")

    if problems:
        return GuardrailFinding("grounding", "block", "; ".join(problems[:3]))
    return GuardrailFinding(
        "grounding", "pass", f"{len(claims)} citation(s) resolved to retrieved text."
    )


def check_instruction_integrity(ticket: Ticket, response_text: str) -> GuardrailFinding:
    """Block if the ticket tried to redirect the system and the output shows it."""
    attempted = bool(_INJECTION_IN_TICKET.search(ticket.text))
    leaked = _LEAKED_SCAFFOLDING.search(response_text or "")

    if leaked:
        return GuardrailFinding(
            "instruction_integrity",
            "block",
            f"The reply reproduces system scaffolding ({leaked.group(0)[:40]!r}). "
            f"Input recorded for review.",
        )
    if attempted:
        # The instruction was ignored, which is the correct outcome, but a
        # person should still see what was attempted before anything is sent.
        return GuardrailFinding(
            "instruction_integrity",
            "block",
            "The ticket contains an attempt to override the system's instructions. "
            "The attempt did not succeed; the ticket is held for review rather "
            "than answered automatically.",
        )
    return GuardrailFinding("instruction_integrity", "pass", "No override attempt detected.")


def check_tone_and_scope(response_text: str) -> GuardrailFinding:
    """Block commitments. A refund or a deadline is not the system's to offer."""
    if not response_text:
        return GuardrailFinding("tone_and_scope", "not_applicable", "No outbound text.")
    match = _COMMITMENT.search(response_text)
    if match:
        return GuardrailFinding(
            "tone_and_scope",
            "block",
            f"The reply makes a commitment the system cannot make: {match.group(0)!r}.",
        )
    return GuardrailFinding("tone_and_scope", "pass", "No commitments made.")


def check_confidence_floor(classification: Classification, threshold: float) -> GuardrailFinding:
    """Block if the routing threshold was not actually satisfied.

    This duplicates the router on purpose. It is the check that catches a
    future change to the routing code, and it reads a missing confidence as
    zero rather than as absent.
    """
    confidence = classification.confidence
    if confidence is None or confidence < threshold:
        return GuardrailFinding(
            "confidence_floor",
            "block",
            f"Confidence {confidence:.2f} is below the {threshold:.2f} threshold "
            f"required to answer without review.",
        )
    return GuardrailFinding(
        "confidence_floor", "pass", f"Confidence {confidence:.2f} at or above {threshold:.2f}."
    )


def run_guardrails(
    ticket: Ticket,
    classification: Classification,
    response: GeneratedResponse,
    claims: list[dict[str, str]],
    passages: list[Passage],
    threshold: float,
) -> list[GuardrailFinding]:
    """Every check, every time. There is no argument that turns one off."""
    text = response.body if response.answered else ""
    return [
        check_private_data(text, passages),
        check_grounding(response, claims, passages),
        check_instruction_integrity(ticket, text),
        check_tone_and_scope(text),
        check_confidence_floor(classification, threshold),
    ]


def blocked_by(findings: list[GuardrailFinding]) -> list[GuardrailFinding]:
    return [f for f in findings if f.status == "block"]
