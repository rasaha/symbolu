"""RELEASE GATE — the native vocabulary is a waypoint, not a second opinion.

A vNext tier reaches a caller through two hops: ``core.TIER_TO_NATIVE`` and then
``mapping.result._OUTCOME_MAP``. If those two tables disagree with
``vnext.NEUTRAL_OUTCOME_V2``, the evaluator decides one thing and the caller is
told another — and nothing else in the suite would notice, because each table is
individually self-consistent.

So the composition is asserted directly, for every tier, plus the expiry
semantics the MAJOR change exists to deliver.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest)

from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import (
    TIER_TO_NATIVE, ActionGateEngine, ActionGateOutcome)
from ugence_actiongate_provider.mapping.result import _OUTCOME_MAP
from ugence_actiongate_provider.vnext import (
    NEUTRAL_OUTCOME_V2, ActionGatePolicy, ActionGateTier, is_expired)

AUTHORIZING = {ActionGovernanceOutcome.AUTHORIZED,
               ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS}


def _p(**kw):
    p = build_actiongate_provider(ActionGateEngine(**kw))
    p.initialize()
    return p


# --- composition -----------------------------------------------------------

@pytest.mark.parametrize("tier", list(ActionGateTier))
def test_composition_reproduces_the_v2_table(tier):
    native = TIER_TO_NATIVE[tier]
    neutral = _OUTCOME_MAP[native]
    assert neutral.value == NEUTRAL_OUTCOME_V2[tier], (
        f"{tier} -> {native} -> {neutral} but V2 says {NEUTRAL_OUTCOME_V2[tier]}")


def test_every_tier_and_every_native_outcome_is_mapped():
    assert set(TIER_TO_NATIVE) == set(ActionGateTier)
    assert set(_OUTCOME_MAP) == set(ActionGateOutcome)


def test_only_authorizing_tiers_reach_authorizing_neutral_outcomes():
    for tier, native in TIER_TO_NATIVE.items():
        authorizing = _OUTCOME_MAP[native] in AUTHORIZING
        expected = tier in (ActionGateTier.AUTHORIZED,
                            ActionGateTier.AUTHORIZED_WITH_CONSTRAINTS)
        assert authorizing is expected, f"{tier} -> {native}"


# --- the delivered behaviour ----------------------------------------------

def test_expired_authorization_reaches_the_caller_as_expired():
    r = _p().authorize(ActionGovernanceRequest("OK", authorization_expired=True))
    assert r.outcome is ActionGovernanceOutcome.EXPIRED
    assert r.outcome not in AUTHORIZING
    assert "AUTHORIZATION_EXPIRED" in r.reason_codes


def test_expired_outranks_a_permissive_policy():
    """Expiry is not a policy question and no policy may override it."""
    r = _p().authorize(ActionGovernanceRequest("ANYTHING", authorization_expired=True))
    assert r.outcome is ActionGovernanceOutcome.EXPIRED


def test_expired_outranks_a_constrained_rule():
    from ugence_actiongate_provider.core import ActionGateConstraint, ConstrainedRule
    rule = ConstrainedRule(constraints=(ActionGateConstraint("maximum_amount", "10"),),
                           obligations=())
    r = _p(constrained={"C": rule}).authorize(
        ActionGovernanceRequest("C", authorization_expired=True))
    assert r.outcome is ActionGovernanceOutcome.EXPIRED
    assert r.constraints == (), "an expired authorization must carry no constraints"


def test_expired_carries_no_authority_basis():
    r = _p().authorize(ActionGovernanceRequest("OK", authorization_expired=True))
    assert r.authority_basis == ""


def test_unexpired_request_is_unaffected():
    r = _p().authorize(ActionGovernanceRequest("OK", authorization_expired=False))
    assert r.outcome is ActionGovernanceOutcome.AUTHORIZED


# --- inclusive boundary ----------------------------------------------------

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_the_boundary_instant_is_expired_not_valid():
    """The one-instant disagreement this change closes."""
    assert is_expired(_NOW, _NOW) is True
    assert is_expired(_NOW, _NOW + timedelta(microseconds=1)) is False
    assert is_expired(_NOW, _NOW - timedelta(microseconds=1)) is True


def test_absent_expiry_never_expires():
    assert is_expired(_NOW, None) is False


def test_control_plane_adapter_uses_the_inclusive_boundary():
    """The adapter is where the boundary is actually computed."""
    from types import SimpleNamespace

    from ugence_governance_provider_framework.adapters import (
        ActionGovernanceControlPlaneAdapter)

    adapter = ActionGovernanceControlPlaneAdapter(
        build_actiongate_provider(ActionGateEngine()), clock=lambda: _NOW)
    cer = SimpleNamespace(cer_id="cer-1", correlation_id="c", expires_at=_NOW,
                          policy_context=SimpleNamespace(policy_refs=()))
    req = SimpleNamespace(action_type="ACT", requested_parameters={}, created_by="u",
                          authority_ref="auth", target_system="SYS", decision_id="d1",
                          idempotency_key="", action_request_id="areq")
    resp = adapter.authorize(req, cer)
    assert resp.outcome.value == "EXPIRED", (
        "a CER expiring exactly now must be treated as expired")


def test_timezone_mismatch_raises_rather_than_guessing():
    naive = datetime(2024, 1, 1)
    with pytest.raises(TypeError):
        is_expired(_NOW, naive)


# --- dimensions still reach the caller through the full stack --------------

def test_a_dimension_denial_survives_the_whole_stack():
    policy = ActionGatePolicy(policy_id="t", policy_version="1",
                              principal_allowlist=frozenset({"alice"}))
    p = _p(policy=policy)
    good = p.authorize(ActionGovernanceRequest("ACT", actor="alice"))
    bad = p.authorize(ActionGovernanceRequest("ACT", actor="mallory"))
    assert good.outcome is ActionGovernanceOutcome.AUTHORIZED
    assert bad.outcome is ActionGovernanceOutcome.DENIED
    assert "PRINCIPAL_UNRECOGNIZED" in bad.reason_codes
    assert good.fingerprint != bad.fingerprint


def test_trace_id_distinguishes_requests_the_old_one_could_not():
    """The audit's exact pair had identical trace ids and fingerprints."""
    p = _p()
    a = p.authorize(ActionGovernanceRequest(
        "ACT", actor="alice", authority_context="delegated:analyst",
        target_resource="prod", risk_context={"score": "low"}))
    b = p.authorize(ActionGovernanceRequest(
        "ACT", actor="mallory", authority_context="", target_resource="prod",
        risk_context={"score": "critical"}, evidence_refs=("e",), decision_refs=("d",)))
    assert a.provider_trace_id != b.provider_trace_id
    assert a.fingerprint != b.fingerprint
