"""The shapes that move between pipeline stages.

Plain dataclasses rather than pydantic models: these never cross a network
boundary, and the API layer converts at its own edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Ticket:
    """One ticket, normalised, whatever channel it arrived on (A2).

    `body` is the original customer text and is never rewritten. `text` is the
    searchable form used by retrieval and classification. Keeping both means a
    downstream citation check can quote the customer accurately while retrieval
    works on something cleaner.
    """

    ticket_id: str
    channel: str
    subject: str
    body: str
    received_at: str
    customer_id: str = ""
    customer_name: str = ""
    customer_tier: str = "standard"
    customer_region: str = "unknown"
    language_fluency: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def text(self) -> str:
        parts = [p for p in (self.subject.strip(), self.body.strip()) if p]
        return "\n\n".join(parts)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(frozen=True)
class Passage:
    """A retrieved chunk. `doc_id` resolves to a real article in the corpus (A4)."""

    doc_id: str
    chunk_id: str
    title: str
    category: str
    text: str
    score: float


@dataclass(frozen=True)
class Classification:
    intent: str
    urgency: str
    confidence: float
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    source: str = "model"  # model | fallback | rule
    note: str = ""


@dataclass(frozen=True)
class RouteDecision:
    action: str  # auto_respond | escalate
    reason: str
    threshold_applied: float
    rule_fired: str = ""


@dataclass(frozen=True)
class GuardrailFinding:
    name: str
    status: str  # pass | block | not_applicable
    detail: str = ""


@dataclass(frozen=True)
class GeneratedResponse:
    body: str
    citations: list[str] = field(default_factory=list)
    answered: bool = True
    note: str = ""


@dataclass
class TicketOutcome:
    """Everything one ticket produced. Written to evaluation/results/ per ticket."""

    ticket_id: str
    channel: str
    customer_tier: str
    customer_region: str
    language_fluency: str
    intent: str
    urgency: str
    confidence: float
    action: str  # auto_respond | escalate | blocked
    reason: str
    retrieved_doc_ids: list[str] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    guardrails: list[dict[str, str]] = field(default_factory=list)
    response_sent: bool = False
    response_text: str = ""
    latency_s: float = 0.0
    # Of that latency, the part spent waiting on the free-tier token allowance.
    # Reported separately so the system's own cost can be read off.
    throttle_s: float = 0.0
    tokens_used: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    degraded: bool = False
    errors: list[str] = field(default_factory=list)
    ticket_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
