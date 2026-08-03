"""Expiry semantics + idempotency / replay classification.

* expiry = injected_now + expiry_seconds, deterministic under an injected clock;
* missing expiry stays missing; zero/negative follow the live semantics;
* the idempotency key is preserved through request mapping; repeated identical
  requests are deterministic (same fingerprint) — but ActionGate provides NO durable
  replay protection (classification: IDEMPOTENCY_KEY_PRESERVED + DETERMINISTIC_REPEAT_ONLY).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_governance_provider_framework.api import ActionGovernanceRequest

from ugence_actiongate_provider.client import InProcessActionGateClient
from ugence_actiongate_provider.core import ActionGateEngine, ConstrainedRule
from ugence_actiongate_provider.mapping import map_request, map_result
from ugence_actiongate_provider.core import ActionGateDecision, ActionGateOutcome
from ugence_actiongate_provider.provider import ActionGateProvider

FIXED = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _clocked(engine):
    p = ActionGateProvider(InProcessActionGateClient(engine), clock=lambda: FIXED)
    p.initialize()
    return p


def test_expiry_is_now_plus_seconds_deterministic():
    rule = ConstrainedRule(constraints=(), obligations=(), expiry_seconds=3600)
    r = _clocked(ActionGateEngine(constrained={"C": rule})).authorize(ActionGovernanceRequest("C"))
    assert r.expiry == FIXED + timedelta(seconds=3600)
    assert r.expiry.tzinfo is not None  # timezone preserved


def test_missing_expiry_stays_missing():
    r = _clocked(ActionGateEngine()).authorize(ActionGovernanceRequest("OK"))
    assert r.expiry is None


def test_zero_and_negative_expiry_follow_live_semantics():
    zero = map_result(ActionGateDecision(ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
                                         expiry_seconds=0), now=FIXED)
    neg = map_result(ActionGateDecision(ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
                                        expiry_seconds=-60), now=FIXED)
    assert zero.expiry == FIXED               # now + 0
    assert neg.expiry == FIXED - timedelta(seconds=60)  # now + (-60): already expired


def test_idempotency_key_preserved_in_request_mapping():
    n = map_request(ActionGovernanceRequest("ACT", idempotency_key="idem-123"))
    assert n.idempotency_key == "idem-123"


def test_repeated_identical_requests_are_deterministic():
    rule = ConstrainedRule(constraints=(), obligations=(), expiry_seconds=60)
    p = _clocked(ActionGateEngine(constrained={"C": rule}))
    a = p.authorize(ActionGovernanceRequest("C", idempotency_key="k"))
    b = p.authorize(ActionGovernanceRequest("C", idempotency_key="k"))
    assert a.fingerprint == b.fingerprint and a.outcome is b.outcome
    assert a.expiry == b.expiry


def test_no_duplicate_registration_side_effect():
    # Building two providers does not register anything global; each is independent.
    p1 = _clocked(ActionGateEngine())
    p2 = _clocked(ActionGateEngine())
    assert p1 is not p2
    assert p1.descriptor().provider_id == p2.descriptor().provider_id == "actiongate"
