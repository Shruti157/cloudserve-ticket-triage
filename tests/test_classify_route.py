"""A3 and A5: classification with a usable confidence, deterministic routing."""

from __future__ import annotations

import json

import pytest

from src.classify import apply_hard_rules, classify
from src.config import INTENT_CLASSES, NEVER_AUTO_RESPOND, URGENCY_LEVELS
from src.ingest import normalise_ticket
from src.llm import ModelUnavailable
from src.models import Classification, Passage
from src.route import decide
from tests.conftest import CLASSIFY_OK, FakeClient


def _ticket(body: str, **kwargs):
    return normalise_ticket({"ticket_id": "T-1", "channel": "email", "body": body, **kwargs})


# --------------------------------------------------------------- classification


def test_classification_produces_a_label_an_urgency_and_a_confidence():
    result = classify(_ticket("I cannot log in, invalid credentials"), FakeClient([CLASSIFY_OK]))
    assert result.intent in INTENT_CLASSES
    assert result.urgency in URGENCY_LEVELS
    assert 0.0 <= result.confidence <= 1.0
    assert result.alternatives


def test_a_label_outside_the_fixed_set_is_rejected_not_passed_on():
    bad = json.dumps({"intent": "something_invented", "urgency": "high", "confidence": 0.99})
    result = classify(_ticket("help"), FakeClient([bad]))
    assert result.intent in INTENT_CLASSES
    assert result.confidence == 0.0


def test_a_percentage_confidence_is_read_as_a_probability():
    payload = json.dumps({"intent": "billing_query", "urgency": "low", "confidence": 85})
    assert classify(_ticket("question about my invoice"), FakeClient([payload])).confidence == 0.85


def test_a_missing_confidence_is_read_as_zero_never_as_high():
    payload = json.dumps({"intent": "billing_query", "urgency": "low"})
    assert classify(_ticket("invoice question"), FakeClient([payload])).confidence == 0.0


def test_a_provider_outage_returns_a_fallback_rather_than_raising():
    result = classify(_ticket("anything"), FakeClient(raises=ModelUnavailable("provider down")))
    assert result.source == "fallback"
    assert result.confidence == 0.0


def test_unparseable_output_returns_a_fallback():
    result = classify(_ticket("anything"), FakeClient(["I am sorry, I cannot do that."]))
    assert result.confidence == 0.0


def test_a_suspected_breach_is_caught_by_rule_before_the_model_is_asked():
    client = FakeClient([CLASSIFY_OK])
    result = classify(_ticket("we think our account has been compromised"), client)
    assert result.intent == "security_incident"
    assert result.source == "rule"
    assert client.calls_made == 0


def test_a_gdpr_request_is_caught_by_rule():
    assert apply_hard_rules(_ticket("this is a GDPR subject access request")).intent == (
        "compliance_request"
    )


def test_an_empty_ticket_is_classified_with_zero_confidence():
    result = apply_hard_rules(_ticket("   "))
    assert result.confidence == 0.0


# ---------------------------------------------------------------------- routing


def _passages(n=1):
    return [
        Passage(f"DOC-AUTH-00{i}", f"DOC-AUTH-00{i}#00", "t", "authentication", "text", 0.7)
        for i in range(1, n + 1)
    ]


def test_the_same_input_always_produces_the_same_decision():
    classification = Classification("billing_query", "low", 0.88)
    passages = _passages(2)
    decisions = [decide(classification, passages, threshold=0.75) for _ in range(25)]
    assert len({(d.action, d.reason, d.rule_fired) for d in decisions}) == 1


def test_routing_reads_no_customer_attribute():
    """Structural, not statistical: the signature cannot see tier or fluency."""
    import inspect

    parameters = set(inspect.signature(decide).parameters)
    assert not parameters & {
        "ticket",
        "customer_tier",
        "customer_region",
        "language_fluency",
        "customer_name",
    }


def test_confidence_below_the_threshold_escalates():
    decision = decide(Classification("billing_query", "low", 0.4), _passages(), threshold=0.75)
    assert decision.action == "escalate"
    assert decision.rule_fired == "below_confidence_threshold"


def test_no_supporting_passage_escalates_however_confident():
    decision = decide(Classification("billing_query", "low", 1.0), [], threshold=0.75)
    assert decision.action == "escalate"
    assert decision.rule_fired == "no_supporting_source"


@pytest.mark.parametrize("intent", sorted(NEVER_AUTO_RESPOND))
def test_never_auto_respond_classes_escalate_at_full_confidence(intent):
    decision = decide(Classification(intent, "high", 1.0), _passages(3), threshold=0.75)
    assert decision.action == "escalate"
    assert decision.rule_fired == "never_auto_respond"


def test_the_kill_switch_escalates_everything():
    decision = decide(
        Classification("billing_query", "low", 1.0),
        _passages(3),
        threshold=0.75,
        kill_switch_active=True,
    )
    assert decision.action == "escalate"
    assert decision.rule_fired == "kill_switch"


def test_the_reason_is_written_for_a_support_manager():
    decision = decide(Classification("billing_query", "low", 0.4), _passages(), threshold=0.75)
    assert "40%" in decision.reason and "75%" in decision.reason
    assert "_" not in decision.reason.replace("billing query", "")
