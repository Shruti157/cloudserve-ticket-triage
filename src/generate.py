"""Generation: an answer grounded in the retrieved passages (A6).

The citation format is the design decision here. A citation that merely names
a document is satisfied by a model that invents a reference to a real article,
and the check "does DOC-AUTH-001 exist" passes. So a citation must carry a
span of at least six words copied verbatim from the passage that was actually
retrieved, and the guardrail in validate.py verifies the copy. A model that
fabricates a reference to a real article fails that, which is the point.

Customer text and instructions are kept in separate messages and the ticket is
fenced inside markers, so that instructions arriving in a ticket are presented
to the model as data rather than as a continuation of its own system prompt.
"""

from __future__ import annotations

import logging

from .llm import LLMClient, ModelUnavailable, extract_json
from .models import Classification, GeneratedResponse, Passage, Ticket
from .prompts import load_prompt

log = logging.getLogger(__name__)

# Trimmed because the per-minute token bucket is what sets the wall-clock floor
# on a full run. Passages are already one per distinct document, so this cuts
# the tail of a long article rather than a second source.
MAX_PASSAGE_CHARS = 1600

ESCALATION_TEXT = (
    "Thanks for getting in touch. Your ticket has been passed to a support "
    "engineer, who will reply to you directly. Nothing further is needed from "
    "you in the meantime."
)


def format_passages(passages: list[Passage]) -> str:
    blocks = []
    for i, passage in enumerate(passages, start=1):
        body = passage.text[:MAX_PASSAGE_CHARS]
        blocks.append(
            f"--- PASSAGE {i} | doc_id={passage.doc_id} | relevance={passage.score:.2f} ---\n"
            f"{body}"
        )
    return "\n\n".join(blocks)


def generate(
    ticket: Ticket,
    classification: Classification,
    passages: list[Passage],
    client: LLMClient,
) -> tuple[GeneratedResponse, list[dict[str, str]]]:
    """Draft a grounded reply. Returns the response and its raw citation claims.

    Never raises. A provider failure produces an unanswered response, which the
    pipeline turns into an escalation.
    """
    if not passages:
        return (
            GeneratedResponse(
                body="",
                answered=False,
                note="No passages were retrieved, so there was nothing to ground an answer in.",
            ),
            [],
        )

    prompt = load_prompt("PR-02")
    messages = prompt.render(
        passages=format_passages(passages),
        channel=ticket.channel,
        intent=classification.intent,
        ticket_text=ticket.text[:3000],
    )

    try:
        completion = client.complete(
            messages,
            prompt_version=prompt.label,
            max_tokens=900,
            # Generation does not pay for hidden reasoning: the grounding
            # guardrail checks the output whatever process produced it, and on
            # gpt-oss that reasoning was the larger half of the token bill.
            reasoning_effort="low",
        )
        data = extract_json(completion.text)
    except (ModelUnavailable, ValueError) as exc:
        log.warning("Generation degraded for %s: %s", ticket.ticket_id, exc)
        return (
            GeneratedResponse(
                body="",
                answered=False,
                note=f"Draft could not be produced ({type(exc).__name__}: {exc}).",
            ),
            [],
        )

    claims: list[dict[str, str]] = []
    for item in data.get("citations") or []:
        if isinstance(item, dict) and item.get("doc_id"):
            claims.append(
                {"doc_id": str(item["doc_id"]).strip(), "quote": str(item.get("quote", "")).strip()}
            )

    body = str(data.get("response", "")).strip()
    answered = bool(data.get("answered")) and bool(body)

    return (
        GeneratedResponse(
            body=body,
            citations=[c["doc_id"] for c in claims],
            answered=answered,
            note=str(data.get("unsupported", ""))[:300],
        ),
        claims,
    )
