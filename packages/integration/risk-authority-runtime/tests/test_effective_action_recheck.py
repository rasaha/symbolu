"""F1 hardening — the current action is re-checked against the effective scope.

A non-empty governance-narrowed effective scope is NOT sufficient for GRANT: the
composition must also confirm the *specific* action Risk Authority authorized is
still inside the effective scope (``CurrentAction ∈ EffectiveScope``). These
tests reproduce the audit finding and pin the re-check to Risk Authority's own
reference matcher so it can never drift looser than RA itself.
"""

from __future__ import annotations

import pytest

from ugence_actiongate_provider.core import (
    ActionGateConstraint,
    ActionGateDecision,
    ActionGateOutcome,
)
from ugence_decision_authority.decisions.status import DecisionOutcome

from ugence_risk_authority_runtime import (
    ActionGatePolicyAdapter,
    DecisionAuthorityGovernanceAdapter,
    FinalDisposition,
    GovernanceRestrictions,
    GovernanceVetoResult,
    ReasonCode,
    RiskAuthorityCompositionEngine,
    VetoDisposition,
    effective_scope_authorizes,
)

DA = DecisionAuthorityGovernanceAdapter()
AG = ActionGatePolicyAdapter()
ENGINE = RiskAuthorityCompositionEngine()

ADVANCE = DA.to_veto(DecisionOutcome.ADVANCE)
AG_ALLOW = AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW))


def _no_veto_with(restrictions: GovernanceRestrictions) -> GovernanceVetoResult:
    """An ActionGate NO_VETO carrying an arbitrary tightening restriction.

    Production adapters emit only amount/expiry/approval restrictions, but the
    engine must remain correct for any set-narrowing restriction a future
    governance source could contribute — so we exercise the set dimensions here.
    """

    return GovernanceVetoResult(
        source="actiongate",
        disposition=VetoDisposition.NO_VETO,
        restrictions=restrictions,
    )


# --- Case A — audit reproduction: set narrowed to exclude the current action ---


def test_case_a_effective_set_excludes_current_action_denies(ra):
    # RA allow = {crm.read, refund.prepare}; action = refund.prepare → RA ALLOW.
    ra_result = ra.enforce(action=ra.action(action_type="refund.prepare"))
    assert ra_result.authorized
    # Governance narrows tools_allow to {crm.read} — non-empty, but excludes the action.
    narrowed = _no_veto_with(
        GovernanceRestrictions(allow_intersections={"tools_allow": frozenset({"crm.read"})})
    )
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=narrowed
    )
    assert result.effective_constraints.tools_allow == ("crm.read",)  # non-empty
    assert result.final_disposition is FinalDisposition.DENY
    assert not result.executable
    assert ReasonCode.EFFECTIVE_SCOPE_ACTION_MISMATCH.value in result.reason_codes


# --- Case B — allowed member retained: action stays inside effective scope -----


def test_case_b_effective_set_retains_current_action_grants(ra):
    ra_result = ra.enforce(action=ra.action(action_type="refund.prepare"))
    retained = _no_veto_with(
        GovernanceRestrictions(allow_intersections={"tools_allow": frozenset({"refund.prepare"})})
    )
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=retained
    )
    assert result.effective_constraints.tools_allow == ("refund.prepare",)
    assert result.final_disposition is FinalDisposition.GRANT
    assert result.executable


# --- Case C — deny-union adds the current action's tool ------------------------


def test_case_c_deny_union_of_current_action_denies(ra):
    ra_result = ra.enforce(action=ra.action(action_type="refund.prepare"))
    denied = _no_veto_with(
        GovernanceRestrictions(deny_unions={"tools_deny": frozenset({"refund.prepare"})})
    )
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=denied
    )
    assert "refund.prepare" in result.effective_constraints.tools_deny
    assert result.final_disposition is FinalDisposition.DENY
    assert ReasonCode.EFFECTIVE_SCOPE_ACTION_MISMATCH.value in result.reason_codes


# --- Case D — amount ceiling (production-reachable via AG constraints) ----------


def test_case_d_amount_above_effective_ceiling_denies(ra):
    # RA cap $5,000; action $4,000 (RA ALLOW); AG tightens to $3,000.
    ra_result = ra.enforce(
        action=ra.action(action_type="refund.prepare", amount_minor_units=400000)
    )
    assert ra_result.authorized
    ag = AG.to_veto(
        ActionGateDecision(
            outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
            constraints=(ActionGateConstraint(type="maximum_amount", value="300000"),),
        )
    )
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=ag
    )
    assert result.effective_constraints.max_amount_minor_units == 300000
    assert result.final_disposition is FinalDisposition.DENY
    assert not result.executable
    assert ReasonCode.EFFECTIVE_SCOPE_ACTION_MISMATCH.value in result.reason_codes


def test_case_d_amount_within_effective_ceiling_grants(ra):
    # Same tightening, but the action ($2,500) is within the $3,000 effective cap.
    ra_result = ra.enforce(
        action=ra.action(action_type="refund.prepare", amount_minor_units=250000)
    )
    ag = AG.to_veto(
        ActionGateDecision(
            outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
            constraints=(ActionGateConstraint(type="maximum_amount", value="300000"),),
        )
    )
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=ag
    )
    assert result.effective_constraints.max_amount_minor_units == 300000
    assert result.final_disposition is FinalDisposition.GRANT
    assert result.executable


# --- Fail-closed — a matcher error must never fall through to GRANT ------------


class _ExplodingAction:
    """An action whose attribute access raises a non-AttributeError."""

    @property
    def purpose(self):  # noqa: D401
        raise ValueError("boom")


def test_recheck_error_fails_closed(ra):
    ra_result = ra.enforce(action=ra.action(action_type="refund.prepare"))
    result = ENGINE.compose(
        risk_authority=ra_result,
        decision_authority=ADVANCE,
        actiongate=AG_ALLOW,
        action=_ExplodingAction(),
    )
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE
    assert not result.executable
    assert ReasonCode.EFFECTIVE_SCOPE_RECHECK_ERROR.value in result.reason_codes


# --- Differential — the mirror agrees with RA's own reference gate -------------


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # canonical in-scope action
        {"action_type": "crm.read"},
        {"action_type": "refund.prepare", "amount_minor_units": 400000},
        {"purpose": "NOT_A_PURPOSE"},
        {"action_type": "refund.execute"},  # explicitly denied tool
        {"action_type": "unknown.tool"},
        {"destination": "https://evil.example"},
        {"data_classes": ("HEALTH_DATA",)},  # denied data class
        {"data_classes": ("UNLISTED",)},
        {"action_type": "refund.prepare", "amount_minor_units": 600000},  # over ceiling
    ],
)
def test_recheck_matches_reference_gate_when_effective_equals_ra(ra, overrides):
    """With no governance narrowing, effective scope == RA scope, so the F1
    re-check must return exactly what Risk Authority's reference gate decided."""

    action = ra.action(**overrides)
    ra_result = ra.enforce(action=action)
    ra_authorized = ra_result.authorized  # RA's own verdict for this action

    # No restrictions → effective scope mirrors the RA scope on every dimension.
    result = ENGINE.compose(
        risk_authority=ra_result, decision_authority=ADVANCE, actiongate=AG_ALLOW
    )
    if ra_authorized:
        # Mirror agrees the action is inside the (equal) effective scope.
        assert effective_scope_authorizes(result.effective_constraints, action)
        assert result.final_disposition is FinalDisposition.GRANT
    else:
        # RA already denied; composition stays non-executable regardless.
        assert result.final_disposition is not FinalDisposition.GRANT
        assert not result.executable


# --- Invariant — final executable ⇒ action inside effective scope --------------


def test_executable_implies_action_inside_effective_scope(ra):
    for amount, cap in [(400000, "300000"), (250000, "300000"), (100000, None)]:
        action = ra.action(action_type="refund.prepare", amount_minor_units=amount)
        ra_result = ra.enforce(action=action)
        ag = (
            AG_ALLOW
            if cap is None
            else AG.to_veto(
                ActionGateDecision(
                    outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
                    constraints=(ActionGateConstraint(type="maximum_amount", value=cap),),
                )
            )
        )
        result = ENGINE.compose(
            risk_authority=ra_result, decision_authority=ADVANCE, actiongate=ag
        )
        if result.executable:
            # The strengthened guarantee: execution ⇒ action ∈ effective scope.
            assert effective_scope_authorizes(result.effective_constraints, action)
