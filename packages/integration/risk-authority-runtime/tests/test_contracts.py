"""Contract-shape guarantees (RA-4.5 §14, §16) and the F-D non-goal (§13, #1397).

* Governance results cannot express ALLOW or carry authorization scope.
* The governed decision is immutable and JSON-serializable.
* The governed decision wraps — never re-mints — the signed RA envelope.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
    RiskAuthorityCompositionEngine,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)

DA = DecisionAuthorityGovernanceAdapter(source_version="da-1.0.0")
AG = ActionGatePolicyAdapter(source_version="ag-policy-1")
ENGINE = RiskAuthorityCompositionEngine()

RA_SCOPE = Scope(tools_allow=("crm.read",), max_transaction_minor_units=500000)


def _grant():
    ra = RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW,
        scope=RA_SCOPE,
        envelope_id="rae_000001",
        source_version="ra-0.1.0",
    )
    return ENGINE.compose(
        risk_authority=ra,
        decision_authority=DA.to_veto(DecisionOutcome.ADVANCE),
        actiongate=AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)),
        correlation_id="corr-42",
    )


def test_veto_disposition_has_no_allow_member():
    # Governance can never express ALLOW — only NO_VETO/HOLD/DENY/ERROR.
    assert "ALLOW" not in {d.value for d in VetoDisposition}


def test_veto_result_carries_no_scope_attribute():
    veto = DA.to_veto(DecisionOutcome.ADVANCE)
    assert not hasattr(veto, "scope")
    # Its strongest positive is NO_VETO.
    assert veto.disposition is VetoDisposition.NO_VETO


def test_governed_decision_is_json_serializable():
    decision = _grant()
    payload = decision.to_dict()
    text = json.dumps(payload)  # must not raise
    restored = json.loads(text)
    assert restored["final_disposition"] == "GRANT"
    assert restored["executable"] is True
    assert restored["correlation_id"] == "corr-42"
    assert restored["source_versions"]["risk_authority"] == "ra-0.1.0"


def test_governed_decision_preserves_all_source_provenance():
    decision = _grant()
    d = decision.to_dict()
    assert set(d["source_versions"]) == {"risk_authority", "decision_authority", "actiongate"}
    assert d["risk_authority_result"]["disposition"] == "ALLOW"
    assert d["decision_authority_result"]["source"] == "decision_authority"
    assert d["actiongate_result"]["source"] == "actiongate"
    assert d["effective_constraints"]["max_amount_minor_units"] == 500000


def test_governed_decision_is_immutable():
    decision = _grant()
    with pytest.raises(Exception):
        decision.final_disposition = "GRANT"  # type: ignore[misc]


def test_governed_decision_references_envelope_without_reminting():
    decision = _grant()
    # References the RA envelope by id; carries no signature of its own.
    assert decision.risk_authority_result.envelope_id == "rae_000001"
    assert not hasattr(decision, "signature")
    assert "signature" not in decision.to_dict()


def test_f_d_allowed_region_recorded_as_obligation_not_jurisdiction_enforcement():
    """F-D (#1397): an ActionGate allowed_region is recorded as a governance
    obligation only — it is NOT mapped onto RA jurisdiction enforcement, and it
    never appears as an effective jurisdiction the composition claims to enforce.
    """

    ra = RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW,
        scope=Scope(tools_allow=("crm.read",), jurisdictions=("US",)),
    )
    ag_dec = ActionGateDecision(
        outcome=ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
        constraints=(ActionGateConstraint(type="allowed_region", value="EU"),),
    )
    decision = ENGINE.compose(
        risk_authority=ra,
        decision_authority=DA.to_veto(DecisionOutcome.ADVANCE),
        actiongate=AG.to_veto(ag_dec),
    )
    eff = decision.effective_constraints
    # Jurisdiction stays exactly RA's — the AG region did NOT alter it.
    assert set(eff.jurisdictions) == {"US"}
    # The region is preserved as an obligation for audit, not enforcement.
    obligation_types = {t for t, _ in eff.obligations}
    assert "allowed_region" in obligation_types
