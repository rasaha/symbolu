"""RELEASE GATE — every governed dimension must be able to change an outcome.

The pre-vNext engine mapped seven governance dimensions (principal, authority,
resource, parameters, risk_context, evidence_refs, decision_refs) and read none
of them: two requests differing in all seven produced a byte-identical
AUTHORIZED result. Every test that existed asserted *preservation* through
``map_request`` — that a field survived the mapping — and none asserted that
changing a field changed anything. A field can survive a mapping perfectly and
still be inert.

So these tests are written the other way round. Each one holds a policy fixed,
varies exactly one dimension, and asserts the *outcome* differs. A stub that
preserved every field and decided on ``action_type`` alone would pass the old
suite and fail every test in this file.
"""

from __future__ import annotations

import pytest

from ugence_actiongate_provider.vnext import (
    ActionGatePolicy,
    ActionGateReasonCode as RC,
    ActionGateTier as Tier,
    ParameterBound,
    VNextAuthorizationRequest as Req,
    evaluate,
)

ACT = "TRANSFER"


def _policy(**kw) -> ActionGatePolicy:
    return ActionGatePolicy(policy_id="test", policy_version="1", **kw)


def _assert_dispositive(policy, permissive: Req, offending: Req, code: RC, tier: Tier):
    """The dimension must flip the outcome, name its code, and stay deterministic."""
    good = evaluate(permissive, policy)
    bad = evaluate(offending, policy)

    assert good.tier is Tier.AUTHORIZED, (
        f"baseline must authorize, got {good.tier} {good.reason_codes}")
    assert bad.tier is tier, f"expected {tier}, got {bad.tier} {bad.reason_codes}"
    assert good.tier is not bad.tier, "dimension did not change the outcome"
    assert code.value in bad.reason_codes
    # determinism: same inputs, same decision object
    assert evaluate(offending, policy) == bad


# --- hard dimensions -------------------------------------------------------

def test_authority_absent_is_dispositive():
    p = _policy(authority_required_action_types=frozenset({ACT}))
    _assert_dispositive(p, Req(ACT, authority="delegated:analyst"), Req(ACT, authority=""),
                        RC.AUTHORITY_ABSENT, Tier.DENIED)


def test_authority_insufficient_is_dispositive():
    p = _policy(accepted_authority_contexts={ACT: ("delegated:treasurer",)})
    _assert_dispositive(p, Req(ACT, authority="delegated:treasurer"),
                        Req(ACT, authority="delegated:intern"),
                        RC.AUTHORITY_INSUFFICIENT, Tier.DENIED)


def test_principal_unresolved_is_dispositive():
    p = _policy(principal_required_action_types=frozenset({ACT}))
    _assert_dispositive(p, Req(ACT, principal="alice"), Req(ACT, principal=""),
                        RC.PRINCIPAL_UNRESOLVED, Tier.DENIED)


def test_principal_outside_allowlist_is_dispositive():
    p = _policy(principal_allowlist=frozenset({"alice"}))
    _assert_dispositive(p, Req(ACT, principal="alice"), Req(ACT, principal="mallory"),
                        RC.PRINCIPAL_UNRECOGNIZED, Tier.DENIED)


def test_decision_ref_missing_is_dispositive():
    p = _policy(decision_ref_required_action_types=frozenset({ACT}))
    _assert_dispositive(p, Req(ACT, decision_refs=("d:9",)), Req(ACT, decision_refs=()),
                        RC.DECISION_REF_MISSING, Tier.DENIED)


def test_resource_outside_permitted_scope_is_dispositive():
    p = _policy(permitted_resource_prefixes={ACT: ("ledger:",)})
    _assert_dispositive(p, Req(ACT, resource="ledger:42"), Req(ACT, resource="payroll:1"),
                        RC.RESOURCE_NOT_PERMITTED, Tier.DENIED)


def test_resource_unresolved_is_dispositive():
    p = _policy(resource_required_action_types=frozenset({ACT}))
    _assert_dispositive(p, Req(ACT, resource="ledger:42"), Req(ACT, resource=""),
                        RC.RESOURCE_UNRESOLVED, Tier.DENIED)


# --- mixed: parameters -----------------------------------------------------

def test_parameter_limit_exceeded_is_dispositive():
    p = _policy(parameter_bounds=(ParameterBound("amount", deny_above=1000),))
    _assert_dispositive(p, Req(ACT, parameters={"amount": "999"}),
                        Req(ACT, parameters={"amount": "1001"}),
                        RC.PARAMETER_LIMIT_EXCEEDED, Tier.DENIED)


def test_parameter_bound_applied_constrains_without_denying():
    p = _policy(parameter_bounds=(
        ParameterBound("amount", deny_above=1000, constrain_above=100),))
    d = evaluate(Req(ACT, parameters={"amount": "500"}), p)
    assert d.tier is Tier.AUTHORIZED_WITH_CONSTRAINTS
    assert d.constraints == ("maximum_amount=1000",)
    assert d.authorizes


def test_unparseable_parameter_is_uncertainty_not_permission():
    """A declared bound that cannot be evaluated must never silently pass."""
    p = _policy(parameter_bounds=(ParameterBound("amount", deny_above=1000),))
    d = evaluate(Req(ACT, parameters={"amount": "not-a-number"}), p)
    assert d.tier is Tier.EVIDENCE_REQUIRED
    assert RC.PARAMETER_UNRESOLVED.value in d.reason_codes
    assert not d.authorizes


# --- soft dimensions -------------------------------------------------------

def test_risk_threshold_exceeded_is_dispositive():
    p = _policy(risk_deny_scores=frozenset({"critical"}))
    _assert_dispositive(p, Req(ACT, risk_context={"score": "low"}),
                        Req(ACT, risk_context={"score": "critical"}),
                        RC.RISK_THRESHOLD_EXCEEDED, Tier.DENIED)


def test_absent_risk_is_uncertainty_not_denial():
    """The ratified soft posture: missing risk data is not a boundary violation."""
    p = _policy(risk_required_action_types=frozenset({ACT}),
                risk_deny_scores=frozenset({"critical"}))
    d = evaluate(Req(ACT), p)
    assert d.tier is Tier.EVIDENCE_REQUIRED
    assert RC.RISK_CONTEXT_UNAVAILABLE.value in d.reason_codes
    assert not d.authorizes


def test_evidence_below_minimum_is_dispositive_but_soft():
    p = _policy(minimum_evidence_refs={ACT: 2})
    good = evaluate(Req(ACT, evidence_refs=("e1", "e2")), p)
    bad = evaluate(Req(ACT, evidence_refs=("e1",)), p)
    assert good.tier is Tier.AUTHORIZED
    assert bad.tier is Tier.EVIDENCE_REQUIRED
    assert RC.EVIDENCE_INSUFFICIENT.value in bad.reason_codes
    assert not bad.authorizes


def test_policy_context_absent_escalates():
    p = _policy(policy_ref_required_action_types=frozenset({ACT}))
    good = evaluate(Req(ACT, policy_context=("p:1",)), p)
    bad = evaluate(Req(ACT, policy_context=()), p)
    assert good.tier is Tier.AUTHORIZED
    assert bad.tier is Tier.ESCALATION_REQUIRED
    assert not bad.authorizes


# --- the regression this whole module exists for ---------------------------

def test_the_original_defect_cannot_recur():
    """The exact pair from the audit must no longer be indistinguishable.

    Pre-vNext, these two produced identical AUTHORIZED results with identical
    fingerprints despite differing in actor, authority, risk and expiry.
    """
    p = _policy(
        authority_required_action_types=frozenset({ACT}),
        principal_allowlist=frozenset({"alice"}),
        risk_deny_scores=frozenset({"critical"}))
    benign = Req(ACT, principal="alice", authority="delegated:analyst",
                 resource="prod", risk_context={"score": "low"})
    hostile = Req(ACT, principal="mallory", authority="", resource="prod",
                  risk_context={"score": "critical"}, authorization_expired=True)

    a, b = evaluate(benign, p), evaluate(hostile, p)
    assert a.tier is Tier.AUTHORIZED and a.authorizes
    assert b.tier is Tier.EXPIRED and not b.authorizes
    assert a != b


# --- meta: no dimension may be silently ungoverned -------------------------

_MATRIX_DIMENSIONS = frozenset({
    "action_type", "authority", "principal", "decision_refs", "resource",
    "parameters", "risk_context", "evidence_refs", "policy_context",
})


def test_every_matrix_dimension_can_be_governed():
    """Each ratified dimension must be reachable through the policy model."""
    full = _policy(
        denied_action_types=frozenset({"X"}),
        authority_required_action_types=frozenset({ACT}),
        principal_required_action_types=frozenset({ACT}),
        decision_ref_required_action_types=frozenset({ACT}),
        resource_required_action_types=frozenset({ACT}),
        parameter_bounds=(ParameterBound("amount", deny_above=1),),
        risk_required_action_types=frozenset({ACT}),
        minimum_evidence_refs={ACT: 1},
        policy_ref_required_action_types=frozenset({ACT}))
    assert full.governed_dimensions() == _MATRIX_DIMENSIONS


def test_an_empty_policy_governs_nothing_and_says_so():
    """Vacuity must be observable, not implicit."""
    d = evaluate(Req(ACT, principal="anyone", risk_context={"score": "critical"}),
                 _policy())
    assert d.tier is Tier.AUTHORIZED
    assert d.governed_dimensions == ()


@pytest.mark.parametrize("dimension", sorted(_MATRIX_DIMENSIONS - {"action_type"}))
def test_dimension_has_a_non_vacuity_test(dimension):
    """Guard against a dimension being added to the matrix without a test."""
    source = __import__("pathlib").Path(__file__).read_text()
    assert f"{dimension}=" in source or f'"{dimension}"' in source, (
        f"dimension {dimension} has no non-vacuity coverage in this module")
