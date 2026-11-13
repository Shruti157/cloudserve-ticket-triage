"""The pipeline: six components, called in order, by an ordinary function.

The Project Brief illustrates a LangGraph state machine. This is an explicit
pipeline instead, and the reasoning is in docs/architecture.md (ADR-001): the
flow has no dynamic branching, no cycles and no agent that decides what to do
next, so a graph framework would add a runtime and a vocabulary without
removing a decision. The condition under which that would change is recorded
in the ADR.

Everything below is written so that one ticket cannot stop a run. Each stage
catches its own failures and produces a defined, logged, escalating outcome,
and `process_ticket` has a final catch so that an exception nobody anticipated
still yields an escalation rather than a traceback (A11).
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any

from . import classify as classify_mod
from . import killswitch, route
from .config import Config
from .decision_log import DecisionLog
from .generate import ESCALATION_TEXT, GENERATION_MAX_PASSAGES, generate
from .llm import LLMClient
from .models import (
    Classification,
    GeneratedResponse,
    GuardrailFinding,
    Passage,
    Ticket,
    TicketOutcome,
)
from .prompts import load_prompt
from .retrieval import LexicalIndex
from .validate import blocked_by, run_guardrails

# Read from the prompt files rather than written here. A literal drifts the
# moment a prompt is edited, and a decision log that names the wrong version
# is worse than one that names none: it invites reproduction against text that
# never produced the decision.
CLASSIFY_VERSION = load_prompt("PR-01").label
GENERATE_VERSION = load_prompt("PR-02").label

log = logging.getLogger(__name__)

REQUIREMENTS = {
    "classification": ["FR-02", "FR-03"],
    "retrieval": ["FR-04"],
    "routing": ["FR-07", "NFR-05"],
    "generation": ["FR-05", "FR-06"],
    "validation": ["FR-08", "FR-09", "NFR-02"],
}


@dataclass
class Pipeline:
    config: Config
    index: LexicalIndex
    client: LLMClient
    decisions: DecisionLog

    def process(self, ticket: Ticket) -> TicketOutcome:
        started = time.perf_counter()
        calls_before = self.client.calls_made + self.client.cache_hits
        cache_before = self.client.cache_hits
        tokens_before = self.client.tokens_used
        throttle_before = self.client.throttle_seconds
        outcome = TicketOutcome(
            ticket_id=ticket.ticket_id,
            channel=ticket.channel,
            customer_tier=ticket.customer_tier,
            customer_region=ticket.customer_region,
            language_fluency=ticket.language_fluency,
            intent="unclear_request",
            urgency="medium",
            confidence=0.0,
            action="escalate",
            reason="",
            ticket_length=len(ticket.text),
        )

        try:
            self._run_stages(ticket, outcome)
        except Exception as exc:  # noqa: BLE001 - the run must not stop
            log.exception("Unhandled failure on %s", ticket.ticket_id)
            outcome.action = "escalate"
            outcome.degraded = True
            outcome.response_sent = False
            outcome.response_text = ESCALATION_TEXT
            outcome.reason = (
                "The ticket could not be processed automatically and has been "
                "passed to an agent."
            )
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
            self.decisions.record(
                ticket_id=ticket.ticket_id,
                stage="routing",
                input_summary=ticket.text[:500],
                action_taken="escalate",
                reason=outcome.reason + f" Internal error: {type(exc).__name__}.",
                threshold_applied=self.config.confidence_threshold,
                requirement_ids=REQUIREMENTS["routing"] + ["NFR-06"],
                guardrail_results={"unhandled_error": "block"},
            )
            log.debug(traceback.format_exc())

        outcome.latency_s = round(time.perf_counter() - started, 3)
        outcome.throttle_s = round(self.client.throttle_seconds - throttle_before, 3)
        outcome.llm_calls = (self.client.calls_made + self.client.cache_hits) - calls_before
        outcome.cache_hits = self.client.cache_hits - cache_before
        outcome.tokens_used = self.client.tokens_used - tokens_before
        return outcome

    # ------------------------------------------------------------------ stages

    def _run_stages(self, ticket: Ticket, outcome: TicketOutcome) -> None:
        switch = killswitch.read(self.config.kill_switch_path)

        classification = classify_mod.classify(ticket, self.client)
        outcome.intent = classification.intent
        outcome.urgency = classification.urgency
        outcome.confidence = classification.confidence
        if classification.source == "fallback":
            outcome.degraded = True
            outcome.errors.append("classification_fallback")

        self.decisions.record(
            ticket_id=ticket.ticket_id,
            stage="classification",
            input_summary=ticket.text[:500],
            model={"name": self.config.model_name, "version": classification.source},
            prediction={"value": classification.intent, "confidence": classification.confidence},
            alternatives=classification.alternatives,
            action_taken="classified",
            reason=classification.note or f"Urgency assessed as {classification.urgency}.",
            prompt_version=CLASSIFY_VERSION if classification.source == "model" else "rule",
            requirement_ids=REQUIREMENTS["classification"],
        )

        passages = self._retrieve(ticket, outcome)

        decision = route.decide(
            classification,
            passages,
            threshold=self.config.confidence_threshold,
            kill_switch_active=switch.active,
        )
        self.decisions.record(
            ticket_id=ticket.ticket_id,
            stage="routing",
            input_summary=ticket.text[:500],
            prediction={"value": decision.action, "confidence": classification.confidence},
            sources_used=[{"doc_id": p.doc_id, "score": p.score} for p in passages],
            threshold_applied=decision.threshold_applied,
            action_taken=decision.action,
            reason=decision.reason + (f" [{switch.reason}]" if switch.active else ""),
            requirement_ids=REQUIREMENTS["routing"],
        )
        outcome.action = decision.action
        outcome.reason = decision.reason

        if decision.action == "escalate":
            # No draft is produced where a draft could never be sent. That
            # alone took the measured calls per ticket from 2.0 to about 1.4.
            outcome.response_sent = False
            outcome.response_text = ESCALATION_TEXT
            return

        # Generation and the grounding check see exactly the same passages, so
        # the model can never be blocked for failing to quote something it was
        # not shown. Retrieval still records all of them.
        grounding_passages = passages[:GENERATION_MAX_PASSAGES]
        response, claims = generate(ticket, classification, grounding_passages, self.client)
        if not response.answered:
            outcome.degraded = outcome.degraded or bool(response.note)
            outcome.action = "escalate"
            outcome.reason = (
                "The system could not produce an answer it was able to evidence, "
                "so the ticket was passed to an agent. " + response.note
            ).strip()
            outcome.response_sent = False
            outcome.response_text = ESCALATION_TEXT
            self.decisions.record(
                ticket_id=ticket.ticket_id,
                stage="generation",
                input_summary=ticket.text[:500],
                model={"name": self.config.model_name, "version": "PR-02"},
                sources_used=[{"doc_id": p.doc_id, "score": p.score} for p in passages],
                action_taken="escalate",
                reason=outcome.reason,
                prompt_version=GENERATE_VERSION,
                requirement_ids=REQUIREMENTS["generation"],
            )
            return

        self.decisions.record(
            ticket_id=ticket.ticket_id,
            stage="generation",
            input_summary=ticket.text[:500],
            model={"name": self.config.model_name, "version": "PR-02"},
            sources_used=[{"doc_id": c["doc_id"], "score": 0.0} for c in claims],
            action_taken="drafted",
            reason=f"Drafted a reply citing {len(claims)} passage(s).",
            prompt_version=GENERATE_VERSION,
            requirement_ids=REQUIREMENTS["generation"],
        )

        self._validate(ticket, classification, response, claims, grounding_passages, outcome)

    def _retrieve(self, ticket: Ticket, outcome: TicketOutcome) -> list[Passage]:
        try:
            passages = self.index.search(
                ticket.text,
                top_k=self.config.retrieval_top_k,
                min_score=self.config.retrieval_min_score,
            )
        except Exception as exc:  # noqa: BLE001 - degrade, do not stop
            log.warning("Retrieval failed for %s: %s", ticket.ticket_id, exc)
            outcome.degraded = True
            outcome.errors.append(f"retrieval_error: {type(exc).__name__}")
            passages = []

        outcome.retrieved_doc_ids = [p.doc_id for p in passages]
        outcome.retrieval_scores = [p.score for p in passages]
        self.decisions.record(
            ticket_id=ticket.ticket_id,
            stage="retrieval",
            input_summary=ticket.text[:500],
            sources_used=[{"doc_id": p.doc_id, "score": p.score} for p in passages],
            threshold_applied=self.config.retrieval_min_score,
            action_taken="retrieved" if passages else "no_source_above_threshold",
            reason=(
                f"{len(passages)} passage(s) cleared the {self.config.retrieval_min_score:.2f} "
                f"relevance floor."
                if passages
                else "Nothing in the documentation was close enough to this question "
                "to support an answer."
            ),
            requirement_ids=REQUIREMENTS["retrieval"],
        )
        return passages

    def _validate(
        self,
        ticket: Ticket,
        classification: Classification,
        response: GeneratedResponse,
        claims: list[dict[str, str]],
        passages: list[Passage],
        outcome: TicketOutcome,
    ) -> None:
        findings: list[GuardrailFinding] = run_guardrails(
            ticket,
            classification,
            response,
            claims,
            passages,
            self.config.confidence_threshold,
        )
        outcome.guardrails = [
            {"name": f.name, "status": f.status, "detail": f.detail} for f in findings
        ]
        blocks = blocked_by(findings)

        if blocks:
            outcome.action = "blocked"
            outcome.response_sent = False
            outcome.response_text = ESCALATION_TEXT
            outcome.citations = []
            outcome.reason = (
                "The drafted reply was blocked before it could be sent and the "
                "ticket was escalated. " + " ".join(f.detail for f in blocks)
            )
        else:
            outcome.action = "auto_respond"
            outcome.response_sent = True
            outcome.response_text = response.body
            outcome.citations = sorted({c["doc_id"] for c in claims})

        self.decisions.record(
            ticket_id=ticket.ticket_id,
            stage="validation",
            input_summary=ticket.text[:500],
            prediction={"value": outcome.action, "confidence": classification.confidence},
            sources_used=[{"doc_id": p.doc_id, "score": p.score} for p in passages],
            threshold_applied=self.config.confidence_threshold,
            action_taken="block" if blocks else "auto_respond",
            reason=outcome.reason if blocks else "All guardrails passed; the reply was sent.",
            guardrail_results={f.name: f.status for f in findings},
            prompt_version=GENERATE_VERSION,
            requirement_ids=REQUIREMENTS["validation"],
        )


def build_pipeline(
    config: Config,
    *,
    articles: list[dict[str, Any]],
    run_id: str | None = None,
    client: LLMClient | None = None,
) -> Pipeline:
    from .retrieval import build_index

    return Pipeline(
        config=config,
        index=build_index(articles, backend=config.retrieval_backend, strategy="section"),
        client=client or LLMClient(config),
        decisions=DecisionLog(config.database_path, run_id=run_id),
    )
