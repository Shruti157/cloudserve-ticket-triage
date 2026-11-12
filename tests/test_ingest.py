"""A2: all four channels normalise into one representation."""

from __future__ import annotations

import json

import pytest

from src.config import CHANNELS, ROOT
from src.ingest import (
    CorpusMissingError,
    load_corpus,
    load_tickets,
    normalise_ticket,
)


def test_every_channel_in_the_development_set_normalises(dev_tickets):
    tickets = [normalise_ticket(r, i) for i, r in enumerate(dev_tickets)]
    seen = {t.channel for t in tickets}
    assert seen == set(CHANNELS), f"expected all four channels, saw {seen}"
    assert all(t.ticket_id for t in tickets)
    assert all(isinstance(t.text, str) for t in tickets)


@pytest.mark.parametrize("channel", CHANNELS)
def test_one_ticket_per_channel_keeps_its_text_and_channel(dev_tickets, channel):
    raw = next(r for r in dev_tickets if r["channel"] == channel)
    ticket = normalise_ticket(raw)
    assert ticket.channel == channel
    assert ticket.body
    assert ticket.text.strip()


def test_chat_tickets_have_an_empty_subject_and_still_produce_text(dev_tickets):
    raw = next(r for r in dev_tickets if r["channel"] == "chat")
    ticket = normalise_ticket(raw)
    assert ticket.subject == ""
    assert ticket.text == ticket.body


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"ticket_id": "X"},
        {"ticket_id": "X", "body": None, "subject": None},
        {"ticket_id": "X", "body": "", "subject": "Only a subject"},
        {"ticket_id": "X", "channel": "carrier_pigeon", "body": "hello"},
        {"ticket_id": "X", "body": "caf\u00e9 \u2014 \ufeff weird \x00 control \x07 chars"},
        {"ticket_id": "X", "body": "x" * 50000},
        "not even a dict",
    ],
)
def test_malformed_records_never_raise(record):
    ticket = normalise_ticket(record, 7)
    assert ticket.ticket_id
    assert isinstance(ticket.text, str)


def test_empty_body_with_a_subject_is_not_dropped():
    ticket = normalise_ticket({"ticket_id": "X", "subject": "Cannot log in", "body": ""})
    assert not ticket.is_empty
    assert "Cannot log in" in ticket.text


def test_a_genuinely_empty_ticket_is_flagged_rather_than_guessed_at():
    assert normalise_ticket({"ticket_id": "X", "body": "   "}).is_empty


def test_quoted_reply_history_is_dropped_from_email():
    body = "Please help with login.\n\nOn 1 Jan 2026 support wrote:\n> have you tried resetting"
    ticket = normalise_ticket({"ticket_id": "X", "channel": "email", "body": body})
    assert "Please help with login" in ticket.text
    assert "have you tried resetting" not in ticket.text


def test_json_lines_and_wrapped_arrays_both_load(tmp_path):
    rows = [{"ticket_id": "A", "channel": "email", "body": "one"}]
    lines = tmp_path / "lines.json"
    lines.write_text("\n".join(json.dumps(r) for r in rows))
    assert len(load_tickets(lines)) == 1

    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"tickets": rows}))
    assert len(load_tickets(wrapped)) == 1


def test_missing_corpus_raises_a_named_error_rather_than_returning_empty(tmp_path):
    with pytest.raises(CorpusMissingError) as exc:
        load_corpus(tmp_path / "nope.json")
    assert "documentation" in str(exc.value).lower()


def test_the_real_corpus_is_present_and_committed():
    articles = load_corpus(ROOT / "data" / "documentation.json")
    assert len(articles) == 29
