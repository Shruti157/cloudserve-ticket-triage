"""Ingest: four channels into one ticket shape (A2).

The four channels differ in which fields they populate rather than in their
schema. Chat tickets carry an empty subject, forum posts carry markup and
quoted replies, documentation comments are short and often lack a greeting.
The normalisation is therefore about absent and malformed fields, not about
per-channel parsing, and the code is written so that a channel it has never
seen produces a ticket rather than an exception.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import CHANNELS
from .models import Ticket

_QUOTED_LINE = re.compile(r"^\s*(>|On .{0,80} wrote:)", re.MULTILINE)
_SIGNATURE = re.compile(r"\n--\s*\n.*\Z", re.DOTALL)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_RUN = re.compile(r"\n{3,}")


class CorpusMissingError(RuntimeError):
    """Raised when the documentation corpus is absent or empty.

    Chroma's get_or_create_collection returns an empty collection rather than
    complaining, so a missing corpus would otherwise surface as a completed run
    in which every ticket escalated for want of a supporting passage. A failure
    that looks like success is the hardest kind to catch on someone else's
    machine, so this is named and raised loudly instead.
    """


def clean_text(value: Any) -> str:
    """Make any field safe to index and safe to show, without losing meaning."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    # Normalise so that visually identical characters compare equal; NFKC also
    # folds the full-width and smart-quote variants that arrive from chat.
    value = unicodedata.normalize("NFKC", value)
    value = _CONTROL.sub(" ", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _WHITESPACE.sub(" ", value)
    value = _BLANK_RUN.sub("\n\n", value)
    return value.strip()


def _strip_reply_furniture(body: str) -> str:
    """Drop quoted history and signatures, which retrieve badly and cost tokens."""
    body = _SIGNATURE.sub("", body)
    match = _QUOTED_LINE.search(body)
    if match and match.start() > 0:
        body = body[: match.start()]
    return body.strip()


def normalise_ticket(record: dict[str, Any], index: int = 0) -> Ticket:
    """One raw record to one Ticket. Never raises on a malformed record."""
    if not isinstance(record, dict):
        record = {"body": str(record)}

    ticket_id = clean_text(record.get("ticket_id")) or f"UNKNOWN-{index:05d}"

    channel = clean_text(record.get("channel")).lower()
    if channel not in CHANNELS:
        # An unrecognised channel is normalised rather than rejected; the
        # downstream stages read `channel` only for reporting.
        channel = channel or "unknown"

    subject = clean_text(record.get("subject"))
    body = clean_text(record.get("body"))
    if channel in ("email", "forum"):
        body = _strip_reply_furniture(body) or body

    # A ticket whose body is empty but whose subject is not is still answerable;
    # promoting the subject keeps it in the pipeline rather than dropping it.
    if not body and subject:
        body = subject

    return Ticket(
        ticket_id=ticket_id,
        channel=channel,
        subject=subject,
        body=body,
        received_at=clean_text(record.get("received_at")),
        customer_id=clean_text(record.get("customer_id")),
        customer_name=clean_text(record.get("customer_name")),
        customer_tier=clean_text(record.get("customer_tier")).lower() or "unknown",
        customer_region=clean_text(record.get("customer_region")).lower() or "unknown",
        language_fluency=clean_text(record.get("language_fluency")).lower() or "unknown",
        raw=record if isinstance(record, dict) else {},
    )


def normalise_all(records: Iterable[dict[str, Any]]) -> list[Ticket]:
    return [normalise_ticket(r, i) for i, r in enumerate(records)]


def load_tickets(path: str | Path) -> list[Ticket]:
    """Load a ticket file of any size. Accepts a JSON array or JSON lines."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Ticket file not found: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]

    if isinstance(data, dict):
        # Tolerate {"tickets": [...]} as well as a bare array.
        for key in ("tickets", "data", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    return normalise_all(data)


def load_corpus(path: str | Path) -> list[dict[str, Any]]:
    """Load the documentation corpus, failing loudly if it is not really there."""
    path = Path(path)
    if not path.exists():
        raise CorpusMissingError(
            f"The documentation corpus is missing at {path}. Every answer this "
            f"system produces is grounded in it, so a run without it would "
            f"escalate every ticket and still report success. Restore "
            f"data/documentation.json from the project pack and run again."
        )
    articles = json.loads(path.read_text(encoding="utf-8"))
    if not articles:
        raise CorpusMissingError(f"The documentation corpus at {path} is empty.")
    return articles


def iter_batches(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
