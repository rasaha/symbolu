"""End-to-end production path → a non-executable RiskDecision (Phase 4 boundary).

Proves the full trusted chain and its fail-closed complements:

    raw evidence → admitted → assured → trusted controls → RA → RiskDecision  [STOP]

Since defect-(h) containment, production Risk Authority integration STOPS at a
non-executable ``RiskDecision``: envelope issuance and action authorization are
Phase 5 and fail closed in production mode (the reference issuer / ActionGate are
never production enforcement). A DENY (forged-PASS) case still can never even mint
a decision — the RA state machine forbids the transition.
"""

from __future__ import annotations

import pytest

from risk_authority.api.schemas import (
    AuthorizeActionRequest,
    DecisionRequest,
    IssueEnvelopeRequest,
)
from risk_authority.domain.enums import RiskRecommendation
from risk_authority.domain.errors import ProductionContainmentError, RiskAuthorityError

import ra5_scenario as C


def _run_to_evaluation(runtime, records, mapping, conditions=()):
    C.create_case(runtime)
    return runtime.submit_evidence_and_evaluate(
        C.TENANT, "rdc_prod_1", records, control_evidence=mapping, conditions=conditions
    )


def test_full_trusted_chain_mints_non_executable_decision_and_contains_envelope():
    runtime = C.build_runtime()
    records, mapping = C.full_evidence_and_map()
    evaluation = _run_to_evaluation(runtime, records, mapping, conditions=("context_minimization",))
    assert evaluation.recommendation in (
        RiskRecommendation.ALLOW,
        RiskRecommendation.ALLOW_WITH_CONDITIONS,
    )

    # The trusted chain mints a valid binding RiskDecision — and STOPS there.
    decision = runtime.issue_decision(
        C.TENANT,
        "rdc_prod_1",
        evaluation,
        DecisionRequest(principal_id=C.PRINCIPAL, requested_scope=C.FINANCE_SCOPE),
    )
    assert decision.grants_authority

    # Phase-5 containment: production envelope issuance fails closed (no signed
    # execution-authority artifact is minted through the reference issuer).
    with pytest.raises(ProductionContainmentError):
        runtime.issue_envelope(
            C.TENANT,
            "rdc_prod_1",
            IssueEnvelopeRequest(
                decision_id=decision.decision_id,
                audience="finance-agent-runtime",
                session_id="sess_1",
                nonce="nonce_1",
            ),
        )

    # Phase-5 containment: production action authorization fails closed (the
    # reference ActionGate is never production enforcement).
    with pytest.raises(ProductionContainmentError):
        runtime.authorize_action(AuthorizeActionRequest(
            envelope_id="e", tenant_id=C.TENANT, actor_id=C.ACTOR, model_id=C.MODEL,
            session_id="sess_1", action_type="crm.read", target_id="txn",
            purpose="CUSTOMER_REFUND_REVIEW", destination="internal://finance"))


def test_forged_pass_case_cannot_reach_envelope_issuance():
    runtime = C.build_runtime()
    # No evidence ⇒ DENY. With the L-1 transition gating, a case whose required
    # evidence was never admitted is NEVER represented as evidence-complete, so it
    # cannot reach AUTHORITY_REVIEW — issue_decision itself fails closed (a strictly
    # stronger guarantee than before: no non-authority decision is even minted).
    evaluation = _run_to_evaluation(runtime, (), None)
    assert evaluation.recommendation is RiskRecommendation.DENY

    with pytest.raises(RiskAuthorityError):
        runtime.issue_decision(
            C.TENANT,
            "rdc_prod_1",
            evaluation,
            DecisionRequest(principal_id=C.PRINCIPAL, requested_scope=C.FINANCE_SCOPE),
        )


def test_freshness_monotonicity_result_not_outliving_evidence():
    # The trusted result's validity is clamped to its backing evidence (§7.1).
    from datetime import timedelta

    runtime = C.build_runtime()
    short = C.make_evidence(
        "ev_model_provenance_valid", valid_until=C.FIXED_NOW + timedelta(hours=1)
    )
    others = (
        C.make_evidence("ev_human_oversight_valid", valid_until=C.FIXED_NOW + timedelta(hours=10)),
        C.make_evidence("ev_bias_evaluation_current", valid_until=C.FIXED_NOW + timedelta(hours=10)),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    C.create_case(runtime)
    runtime.submit_evidence_and_evaluate(
        C.TENANT, "rdc_prod_1", (short,) + others, control_evidence=mapping
    )
    trusted = {t.control_id: t for t in runtime.trusted_controls(C.TENANT, "rdc_prod_1")}
    mp = trusted["MODEL_PROVENANCE_VALID"]
    assert mp.valid_until == C.FIXED_NOW + timedelta(hours=1)
