"""Fail-closed failure semantics (RA-4.5 §4, §10).

Authority-critical failures never become ALLOW. Distinguishes:

* DENY — an authoritative negative about *this* request (unknown outcome, policy
  deny) — terminal.
* ERROR_NON_EXECUTABLE — a missing / failed authority input (unavailable,
  malformed) — do-not-execute, repair/retry path.
"""

from __future__ import annotations

import pytest

from ugence_actiongate_provider.core import (
    ActionGateDecision,
    ActionGateEngine,
    ActionGateOutcome,
    ActionGateRequest,
    ActionGateTimeout,
    ActionGateUnavailable,
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
    VetoDisposition,
)

DA = DecisionAuthorityGovernanceAdapter()
AG = ActionGatePolicyAdapter()
ENGINE = RiskAuthorityCompositionEngine()

RA_SCOPE = Scope(tools_allow=("crm.read",), max_transaction_minor_units=500000)


def ra_allow():
    return RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW, scope=RA_SCOPE
    )


def ra_error():
    return RiskAuthorityMachineResult(disposition=RiskAuthorityDisposition.ERROR)


def compose(ra, da, ag):
    return ENGINE.compose(risk_authority=ra, decision_authority=da, actiongate=ag)


# --- Decision Authority failure modes -------------------------------------


def test_da_unavailable_is_error_non_executable():
    da = DA.unavailable("connection refused")
    result = compose(ra_allow(), da, AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)))
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_da_malformed_none_is_error():
    da = DA.to_veto(None)  # missing / malformed outcome
    assert da.disposition is VetoDisposition.ERROR
    result = compose(ra_allow(), da, AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)))
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_da_unknown_outcome_is_deny():
    da = DA.to_veto("SOME_FUTURE_OUTCOME")  # unrecognized string outcome
    assert da.disposition is VetoDisposition.DENY
    result = compose(ra_allow(), da, AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)))
    assert result.final_disposition is FinalDisposition.DENY


# --- ActionGate failure modes ---------------------------------------------


def test_ag_unavailable_is_error_non_executable():
    ag = AG.unavailable("engine down")
    result = compose(ra_allow(), DA.to_veto(DecisionOutcome.ADVANCE), ag)
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_ag_malformed_none_is_error():
    ag = AG.to_veto(None)
    assert ag.disposition is VetoDisposition.ERROR
    result = compose(ra_allow(), DA.to_veto(DecisionOutcome.ADVANCE), ag)
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_ag_native_timeout_translated_to_error():
    engine = ActionGateEngine(fail="timeout")
    try:
        decision = engine.evaluate(ActionGateRequest(action_type="crm.read"))
    except (ActionGateTimeout, ActionGateUnavailable) as exc:
        ag = AG.unavailable(str(exc))
    else:  # pragma: no cover
        ag = AG.to_veto(decision)
    result = compose(ra_allow(), DA.to_veto(DecisionOutcome.ADVANCE), ag)
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


# --- Risk Authority failure modes -----------------------------------------


def test_ra_error_is_error_non_executable_regardless_of_governance():
    # RA ERROR outranks everything — no authority basis exists.
    result = compose(
        ra_error(),
        DA.to_veto(DecisionOutcome.ADVANCE),
        AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)),
    )
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_ra_error_even_with_da_reject_stays_error():
    # RA could not run: we cannot even assert an authoritative DENY basis.
    result = compose(
        ra_error(),
        DA.to_veto(DecisionOutcome.REJECT),
        AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.DENY)),
    )
    assert result.final_disposition is FinalDisposition.ERROR_NON_EXECUTABLE


def test_error_is_never_allow():
    # Exhaustive: no combination with an ERROR governance input yields GRANT.
    for da in (DA.unavailable(), DA.to_veto(None)):
        for ag in (AG.unavailable(), AG.to_veto(None)):
            result = compose(ra_allow(), da, ag)
            assert result.final_disposition is not FinalDisposition.GRANT
