"""The decision log (A8).

SQLite, one row per decision, written at the moment the decision is taken
rather than assembled at the end of the run. The difference matters: a log
built from a summary at the end is missing exactly the tickets that crashed,
and those are the ones an audit is about.

The schema is the Governance Framework's minimum record. Two of its fields are
easy to leave out and are the ones that answer the question asked after an
incident — `prompt_version` and `requirement_ids` together say whether the
behaviour was intended.

The database is gitignored because `input_summary` carries the ticket subject
and body, and committing it to a public repository would republish the course
ticket sets in another form. The per-ticket outcomes in evaluation/results/
carry no ticket text and are committed instead.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id      TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    ticket_id        TEXT NOT NULL,
    stage            TEXT NOT NULL,
    input_summary    TEXT,
    model_name       TEXT,
    model_version    TEXT,
    prediction_value TEXT,
    prediction_conf  REAL,
    alternatives     TEXT,
    sources_used     TEXT,
    threshold_applied REAL,
    action_taken     TEXT,
    reason           TEXT,
    guardrail_results TEXT,
    prompt_version   TEXT,
    requirement_ids  TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_ticket ON decisions(ticket_id);
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id);
"""

STAGES = ("classification", "retrieval", "routing", "generation", "validation")


class DecisionLog:
    def __init__(self, path: str | Path, run_id: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()

    def record(
        self,
        *,
        ticket_id: str,
        stage: str,
        input_summary: str,
        action_taken: str,
        reason: str,
        model: dict[str, str] | None = None,
        prediction: dict[str, Any] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        sources_used: list[dict[str, Any]] | None = None,
        threshold_applied: float | None = None,
        guardrail_results: dict[str, str] | None = None,
        prompt_version: str = "",
        requirement_ids: list[str] | None = None,
    ) -> str:
        decision_id = f"{self.run_id}:{ticket_id}:{stage}:{uuid.uuid4().hex[:8]}"
        prediction = prediction or {}
        model = model or {}
        row = (
            decision_id,
            self.run_id,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ticket_id,
            stage,
            input_summary[:2000],
            model.get("name", ""),
            model.get("version", ""),
            str(prediction.get("value", "")),
            float(prediction.get("confidence") or 0.0),
            json.dumps(alternatives or []),
            json.dumps(sources_used or []),
            threshold_applied,
            action_taken,
            reason,
            json.dumps(guardrail_results or {}),
            prompt_version,
            json.dumps(requirement_ids or []),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO decisions VALUES (" + ",".join("?" * len(row)) + ")", row
            )
            self._conn.commit()
        return decision_id

    def reconcile(self, tickets_processed: int) -> dict[str, Any]:
        """Count logged decisions against tickets processed. They must match.

        A gap means some path takes a decision without recording it, and that
        is the path on which something will eventually go wrong unobserved.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT stage, COUNT(*), COUNT(DISTINCT ticket_id) FROM decisions "
                "WHERE run_id = ? GROUP BY stage",
                (self.run_id,),
            ).fetchall()
            distinct = self._conn.execute(
                "SELECT COUNT(DISTINCT ticket_id) FROM decisions WHERE run_id = ?",
                (self.run_id,),
            ).fetchone()[0]
            total = self._conn.execute(
                "SELECT COUNT(*) FROM decisions WHERE run_id = ?", (self.run_id,)
            ).fetchone()[0]

        by_stage = {stage: {"decisions": n, "tickets": t} for stage, n, t in rows}
        # Routing is the stage that must cover every ticket exactly once: it is
        # the decision on whether a customer hears from a machine or a person.
        routed = by_stage.get("routing", {}).get("tickets", 0)
        return {
            "run_id": self.run_id,
            "tickets_processed": tickets_processed,
            "tickets_with_decisions": distinct,
            "total_decisions": total,
            "by_stage": by_stage,
            "routing_decisions_cover_all_tickets": routed == tickets_processed,
            "coverage_complete": distinct == tickets_processed and routed == tickets_processed,
        }

    def fetch(self, ticket_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT * FROM decisions WHERE ticket_id = ? ORDER BY timestamp", (ticket_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def guardrail_activation_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._lock:
            rows = self._conn.execute(
                "SELECT guardrail_results FROM decisions WHERE run_id = ? AND stage = 'validation'",
                (self.run_id,),
            ).fetchall()
        for (blob,) in rows:
            for name, status in json.loads(blob or "{}").items():
                if status == "block":
                    counts[name] = counts.get(name, 0) + 1
        return counts

    def close(self) -> None:
        with self._lock:
            self._conn.close()
