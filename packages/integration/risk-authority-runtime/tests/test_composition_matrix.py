"""Core veto matrix (RA-4.5 §3 truth table, §17 test plan).

Engine-level composition over direct Risk Authority results, so each row isolates
the composition rule from RA integration (the adversarial suite exercises the
real RA enforcement path). Proves the corrected precedence:

    RA DENY absorbing > DA REJECT > AG DENY/UNKNOWN > DA HOLD/DEFER > GRANT
"""

from __future__ import annotations

import pytest

from ugence_actiongate_provider.core import (
    ActionGateConstraint,
    ActionGateDecision,
    ActionGateOutcome,
)
from ugence_decision_authority.decisions.status import DecisionOutcome

from risk_authority.domain import Scope

from ugence_risk_authority_runtime import (
    ActionGatePolicyAdapter,
    DecisionAuthorityGovernanceAdapter,
    FinalDisposition,
    RiskAuthorityCompositionEngine,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
)

DA = DecisionAuthorityGovernanceAdapter()
AG = ActionGatePolicyAdapter()
ENGINE = RiskAuthorityCompositionEngine()

RA_SCOPE = Scope(
    purposes=("CUSTOMER_REFUND_REVIEW",),
    tools_allow=("crm.read", "refund.prepare"),
    max_transaction_minor_units=500000,
)


def ra_allow() -> RiskAuthorityMachineResult:
    return RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW,
        envelope_id="rae_000001",
        scope=RA_SCOPE,
    )


def ra_deny() -> RiskAuthorityMachineResult:
    return RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.DENY, envelope_id="rae_000001"
    )


def ag_decision(outcome: ActionGateOutcome, **kw) -> ActionGateDecision:
    return ActionGateDecision(outcome=outcome, **kw)


def compose(ra, da_outcome, ag_dec):
    return ENGINE.compose(
        risk_authority=ra,
        decision_authority=DA.to_veto(da_outcome),
        actiongate=AG.to_veto(ag_dec),
    )


@pytest.mark.parametrize(
    "ra_factory, da, ag_outcome, expected",
    [
        # RA DENY is absorbing regardless of permissive governance.
        (ra_deny, DecisionOutcome.ADVANCE, ActionGateOutcome.ALLOW, FinalDisposition.DENY),
        # Organizational veto.
        (ra_allow, DecisionOutcome.REJECT, ActionGateOutcome.ALLOW, FinalDisposition.DENY),
        # Governance holds are non-executable.
        (ra_allow, DecisionOutcome.HOLD, ActionGateOutcome.ALLOW, FinalDisposition.HOLD_NON_EXECUTABLE),
        (ra_allow, DecisionOutcome.DEFER, ActionGateOutcome.ALLOW, FinalDisposition.HOLD_NON_EXECUTABLE),
        # Action-policy veto.
        (ra_allow, DecisionOutcome.ADVANCE, ActionGateOutcome.DENY, FinalDisposition.DENY),
        # UNKNOWN never authorizes.
        (ra_allow, DecisionOutcome.ADVANCE, ActionGateOutcome.UNKNOWN, FinalDisposition.DENY),
        # The single all-clear path.
        (ra_allow, DecisionOutcome.ADVANCE, ActionGateOutcome.ALLOW, FinalDisposition.GRANT),
    ],
)
def test_core_veto_matrix(ra_factory, da, ag_outcome, expected):
    result = compose(ra_factory(), da, ag_decision(ag_outcome))
    assert result.final_disposition is expected
    assert result.executable is (expected is FinalDisposition.GRANT)


def test_allow_with_constraints_grants_and_tightens():
    ag_dec = ag_decision(
        ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
        constraints=(ActionGateConstraint(type="maximum_amount", value="300000"),),
    )
    result = compose(ra_allow(), DecisionOutcome.ADVANCE, ag_dec)
    assert result.final_disposition is FinalDisposition.GRANT
    # RA cap $5,000 tightened to AG's $3,000.
    assert result.effective_constraints.max_amount_minor_units == 300000


def test_reject_beats_actiongate_allow_and_hold():
    # DA REJECT dominates any AG outcome (precedence).
    for ag_outcome in ActionGateOutcome:
        result = compose(ra_allow(), DecisionOutcome.REJECT, ag_decision(ag_outcome))
        assert result.final_disposition is FinalDisposition.DENY


def test_actiongate_deny_beats_decision_authority_hold():
    # AG DENY (terminal) outranks DA HOLD (non-terminal) — plan §3 precedence.
    result = compose(ra_allow(), DecisionOutcome.HOLD, ag_decision(ActionGateOutcome.DENY))
    assert result.final_disposition is FinalDisposition.DENY


def test_grant_records_effective_scope_within_ra():
    result = compose(ra_allow(), DecisionOutcome.ADVANCE, ag_decision(ActionGateOutcome.ALLOW))
    eff = result.effective_constraints
    assert set(eff.tools_allow) <= set(RA_SCOPE.tools_allow)
    assert eff.max_amount_minor_units == RA_SCOPE.max_transaction_minor_units
