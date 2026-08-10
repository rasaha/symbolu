"""The non-negotiable invariants (RA-4.5 §2.1):

    FinalAuthority ≤ RiskAuthority
    FinalScope    ⊆ RiskAuthorityScope

Property-style sweep over the veto cross-product plus a range of governance
restrictions. The suite proves: composition may preserve or reduce authority;
composition may never enlarge it.
"""

from __future__ import annotations

import itertools

from ugence_actiongate_provider.core import (
    ActionGateConstraint,
    ActionGateDecision,
    ActionGateOutcome,
)
from ugence_decision_authority.decisions.status import DecisionOutcome

from risk_authority.domain import Scope, subset_violations

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
    tools_deny=("refund.execute",),
    data_allow=("CUSTOMER_PII", "TRANSACTION_DATA"),
    destinations=("internal://finance",),
    jurisdictions=("US",),
    max_autonomy_level=2,
    max_transaction_minor_units=500000,
)


def _effective_as_scope(eff) -> Scope:
    """Project the effective constraints back onto a Scope for containment checks."""

    return Scope(
        purposes=tuple(eff.purposes),
        tools_allow=tuple(eff.tools_allow),
        tools_deny=tuple(eff.tools_deny),
        data_allow=tuple(eff.data_allow),
        destinations=tuple(eff.destinations),
        jurisdictions=tuple(eff.jurisdictions),
        max_autonomy_level=eff.max_autonomy_level,
        max_transaction_minor_units=eff.max_amount_minor_units,
    )


def test_final_scope_subset_of_ra_scope_across_cross_product():
    ra = RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW, scope=RA_SCOPE
    )
    da_outcomes = list(DecisionOutcome)
    ag_decisions = [
        ActionGateDecision(outcome=ActionGateOutcome.ALLOW),
        ActionGateDecision(outcome=ActionGateOutcome.DENY),
        ActionGateDecision(outcome=ActionGateOutcome.UNKNOWN),
        ActionGateDecision(
            outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
            constraints=(ActionGateConstraint(type="maximum_amount", value="300000"),),
        ),
    ]
    for da_outcome, ag_dec in itertools.product(da_outcomes, ag_decisions):
        result = ENGINE.compose(
            risk_authority=ra,
            decision_authority=DA.to_veto(da_outcome),
            actiongate=AG.to_veto(ag_dec),
        )
        eff_scope = _effective_as_scope(result.effective_constraints)
        # FinalScope ⊆ RiskAuthorityScope on every governed dimension.
        violations = subset_violations(eff_scope, RA_SCOPE)
        assert violations == [], (da_outcome, ag_dec.outcome, violations)


def test_effective_amount_never_exceeds_ra_ceiling():
    ra = RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW, scope=RA_SCOPE
    )
    for cap in ("100000", "300000", "500000", "900000", "0"):
        ag_dec = ActionGateDecision(
            outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
            constraints=(ActionGateConstraint(type="maximum_amount", value=cap),),
        )
        result = ENGINE.compose(
            risk_authority=ra,
            decision_authority=DA.to_veto(DecisionOutcome.ADVANCE),
            actiongate=AG.to_veto(ag_dec),
        )
        eff = result.effective_constraints.max_amount_minor_units
        assert eff is not None
        assert eff <= RA_SCOPE.max_transaction_minor_units


def test_no_governance_combo_upgrades_ra_deny():
    ra_deny = RiskAuthorityMachineResult(disposition=RiskAuthorityDisposition.DENY)
    for da_outcome in DecisionOutcome:
        for ag_outcome in ActionGateOutcome:
            result = ENGINE.compose(
                risk_authority=ra_deny,
                decision_authority=DA.to_veto(da_outcome),
                actiongate=AG.to_veto(ActionGateDecision(outcome=ag_outcome)),
            )
            assert result.final_disposition is FinalDisposition.DENY


def test_grant_requires_ra_allow():
    # Only an RA ALLOW can ever produce a GRANT; DENY/ERROR never do.
    for ra_disp in (
        RiskAuthorityDisposition.DENY,
        RiskAuthorityDisposition.ERROR,
    ):
        ra = RiskAuthorityMachineResult(disposition=ra_disp, scope=RA_SCOPE)
        result = ENGINE.compose(
            risk_authority=ra,
            decision_authority=DA.to_veto(DecisionOutcome.ADVANCE),
            actiongate=AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)),
        )
        assert result.final_disposition is not FinalDisposition.GRANT
