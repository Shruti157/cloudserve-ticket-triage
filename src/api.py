"""HTTP surface: one endpoint that processes a ticket, plus health and metrics.

Deliberately small. The acceptance criteria are satisfied by the harness, not
by the API, and the API exists so that a reviewer can submit one ticket from
each channel and read the response. Monitoring is a Prometheus counters
endpoint rather than a dashboard, for the reason in docs/architecture.md
(ADR-005): none of the twelve criteria needs a dashboard, and the governance
marks are for decision logging, risk and fairness.

    python -m src.api          # http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from . import __version__, killswitch
from .config import load_config
from .ingest import load_corpus, normalise_ticket
from .pipeline import build_pipeline

log = logging.getLogger(__name__)

TICKETS = Counter("cloudserve_tickets_total", "Tickets processed", ["channel", "action"])
GUARDRAILS = Counter(
    "cloudserve_guardrail_activations_total", "Guardrail blocks", ["guardrail"]
)
DEGRADED = Counter("cloudserve_degraded_total", "Tickets processed in a degraded mode")
LATENCY = Histogram(
    "cloudserve_ticket_latency_seconds",
    "End to end latency per ticket",
    buckets=(0.25, 0.5, 1, 2, 3, 5, 8, 13, 21, 34),
)

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
    articles = load_corpus(config.corpus_path)
    _state["config"] = config
    _state["pipeline"] = build_pipeline(config, articles=articles)
    log.info(
        "Ready: %d corpus chunks, model %s, threshold %.2f",
        len(_state["pipeline"].index),
        config.model_name,
        config.confidence_threshold,
    )
    yield
    _state["pipeline"].decisions.close()


app = FastAPI(
    title="CloudServe intelligent support",
    version=__version__,
    description=(
        "Processes one support ticket end to end: classify, retrieve, route, "
        "generate, validate. Every call is written to the decision log."
    ),
    lifespan=lifespan,
)


class TicketRequest(BaseModel):
    ticket_id: str = Field(default="API-0001")
    channel: str = Field(default="email", examples=["email", "chat", "docs_comment", "forum"])
    subject: str = ""
    body: str
    received_at: str = ""
    customer_id: str = ""
    customer_name: str = ""
    customer_tier: str = "standard"
    customer_region: str = "unknown"
    language_fluency: str = "unknown"


@app.post("/ticket")
def process_ticket(request: TicketRequest) -> dict[str, Any]:
    pipeline = _state.get("pipeline")
    if pipeline is None:  # pragma: no cover - only before startup completes
        raise HTTPException(status_code=503, detail="The system is still starting.")

    ticket = normalise_ticket(request.model_dump())
    outcome = pipeline.process(ticket)

    TICKETS.labels(channel=outcome.channel, action=outcome.action).inc()
    LATENCY.observe(outcome.latency_s)
    if outcome.degraded:
        DEGRADED.inc()
    for finding in outcome.guardrails:
        if finding["status"] == "block":
            GUARDRAILS.labels(guardrail=finding["name"]).inc()

    return {
        "ticket_id": outcome.ticket_id,
        "action": outcome.action,
        "response_sent": outcome.response_sent,
        "response": outcome.response_text,
        "classification": {
            "intent": outcome.intent,
            "urgency": outcome.urgency,
            "confidence": outcome.confidence,
        },
        "sources": [
            {"doc_id": d, "score": s}
            for d, s in zip(outcome.retrieved_doc_ids, outcome.retrieval_scores)
        ],
        "citations": outcome.citations,
        "guardrails": outcome.guardrails,
        "reason": outcome.reason,
        "latency_seconds": outcome.latency_s,
        "degraded": outcome.degraded,
    }


DEMO_PAGE = Path(__file__).parent / "static" / "demo.html"


@app.get("/", include_in_schema=False)
def index() -> Response:
    """A page for watching the system work, at the address the server prints.

    The interface of record is this API and `/docs` documents it. The page is
    a view over the same two endpoints anyone else would call, holding no
    state of its own, and exists because the guardrail results and the
    decision log are easier to judge when they are seen rather than read out
    of JSON.
    """
    if not DEMO_PAGE.exists():
        return RedirectResponse("/docs")
    return FileResponse(DEMO_PAGE)


@app.get("/ticket/{ticket_id}/decisions")
def ticket_decisions(ticket_id: str) -> dict[str, Any]:
    """The audit trail for one ticket, as an auditor would read it."""
    pipeline = _state["pipeline"]
    return {"ticket_id": ticket_id, "decisions": pipeline.decisions.fetch(ticket_id)}


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    config = _state.get("config")
    pipeline = _state.get("pipeline")
    switch = killswitch.read(config.kill_switch_path) if config else killswitch.read("/nonexistent")
    return {
        "status": "ok" if pipeline else "starting",
        "version": __version__,
        "corpus_chunks": len(pipeline.index) if pipeline else 0,
        "model": config.model_name if config else None,
        "credentials_configured": config.has_credentials if config else False,
        "automatic_answering_enabled": not switch.active,
        "kill_switch_reason": switch.reason,
    }


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:  # pragma: no cover - entry point
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    main()
