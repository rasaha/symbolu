"""End-to-end production path → the sole machine-authority envelope (Phase 12, 29).

Proves the full trusted chain and its fail-closed complement:

    raw evidence → admitted → assured → trusted controls → RA → signed envelope

and that a DENY (forged-PASS) case can NEVER reach envelope issuance — the RA
state machine forbids the transition, so no authority is minted.
"""

from __future__ import annotations

import pytest

from risk_authority.api.schemas import DecisionRequest, IssueEnvelopeRequest
from risk_authority.domain.enums import RiskRecommendation
from risk_authority.domain.errors import RiskAuthorityError

import ra5_scenario as C


def _run_to_evaluation(runtime, records, mapping, conditions=()):
    C.create_case(runtime)
    return runtime.submit_evidence_and_evaluate(
        C.TENANT, "rdc_prod_1", records, control_evidence=mapping, conditions=conditions
    )


def test_full_trusted_chain_mints_and_verifies_envelope():
    runtime = C.build_runtime()
    records, mapping = C.full_evidence_and_map()
    evaluation = _run_to_evaluation(runtime, records, mapping, conditions=("context_minimization",))
    assert evaluation.recommendation in (
        RiskRecommendation.ALLOW,
        RiskRecommendation.ALLOW_WITH_CONDITIONS,
    )

    decision = runtime.issue_decision(
        C.TENANT,
        "rdc_prod_1",
        evaluation,
        DecisionRequest(principal_id=C.PRINCIPAL, requested_scope=C.FINANCE_SCOPE),
    )
    assert decision.grants_authority

    envelope = runtime.issue_envelope(
        C.TENANT,
        "rdc_prod_1",
        IssueEnvelopeRequest(
            decision_id=decision.decision_id,
            audience="finance-agent-runtime",
            session_id="sess_1",
            nonce="nonce_1",
        ),
    )
    verification = runtime.verify_envelope(C.TENANT, envelope.envelope_id)
    assert verification.valid, verification.reasons


def test_forged_pass_case_cannot_reach_envelope_issuance():
    runtime = C.build_runtime()
    # No evidence ⇒ DENY. The case transitions to DENIED, never APPROVED /
    # CONDITIONAL, so envelope issuance is an illegal transition — fail closed.
    evaluation = _run_to_evaluation(runtime, (), None)
    assert evaluation.recommendation is RiskRecommendation.DENY

    decision = runtime.issue_decision(
        C.TENANT,
        "rdc_prod_1",
        evaluation,
        DecisionRequest(principal_id=C.PRINCIPAL, requested_scope=C.FINANCE_SCOPE),
    )
    assert not decision.grants_authority
    with pytest.raises(RiskAuthorityError):
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
