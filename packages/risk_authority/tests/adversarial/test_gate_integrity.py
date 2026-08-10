"""Regression battery for the decision-issuance authority boundary.

These cases target two ways a valid, signed envelope could otherwise be minted
without the governance gate the module advertises actually holding:

* a caller substituting an ALLOW evaluation for a case whose required controls
  failed (the non-compensatory gate must not be caller-overridable);
* an out-of-order / pre-evaluation decision call surviving because the state
  guard runs only after the artifact is persisted;
* an envelope minted from a decision whose own validity window has elapsed.

Each test fails against the pre-fix implementation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from risk_authority.api import (
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
    IssueEnvelopeRequest,
)
from risk_authority.domain.enums import (
    RiskCaseState,
    RiskClass,
    RiskOutcome,
    RiskRecommendation,
)
from risk_authority.domain.errors import RiskAuthorityError
from risk_authority.services.risk_engine import RiskEvaluation

from tests.scenario import (
    ACTOR,
    FINANCE_SCOPE,
    FIXED_NOW,
    MODEL,
    PRINCIPAL,
    TENANT,
    build_application,
)

_ALL_CONTROLS = (
    "MODEL_PROVENANCE_VALID",
    "HUMAN_OVERSIGHT_VALID",
    "BIAS_EVALUATION_CURRENT",
)


def _create(app, case_id="rdc_g"):
    app.create_case(
        CreateCaseRequest(
            tenant_id=TENANT, case_id=case_id, subject_id=ACTOR, model_id=MODEL,
            purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
            tools=("crm.read", "refund.prepare"), autonomy_level=2,
            data_classes=("CUSTOMER_PII",), workflow_ir_id="finance-ai-risk",
            inherent_risk=RiskClass.HIGH, residual_risk=RiskClass.MEDIUM,
        )
    )


def test_forged_allow_cannot_bypass_failed_control():
    """A required control that FAILs must govern even if the caller hands the
    facade a fabricated ALLOW evaluation (non-compensatory, fail-closed)."""

    app = build_application()
    _create(app)
    # The engine sees a hard FAIL and (correctly) recommends DENY.
    real = app.evaluate(
        TENANT, "rdc_g",
        EvaluateRequest(control_results=(
            ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
            ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
            ControlResultInput("BIAS_EVALUATION_CURRENT", "FAIL"),
        )),
    )
    assert real.recommendation is RiskRecommendation.DENY

    # A malicious/buggy caller discards it and forges an ALLOW.
    forged = RiskEvaluation(
        recommendation=RiskRecommendation.ALLOW,
        applicable_rules=("FIN-12",),
        required_controls=_ALL_CONTROLS,
        failed_controls=(),
        conditions=(),
        trace=("forged",),
        workflow_ir_digest=real.workflow_ir_digest,
    )
    decision = app.issue_decision(
        TENANT, "rdc_g", forged,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    # The binding decision is re-derived from persisted controls -> DENY.
    assert decision.outcome is RiskOutcome.DENY
    assert not decision.grants_authority
    assert app.cases.get(TENANT, "rdc_g").state is RiskCaseState.DENIED

    # And no envelope can be minted from a non-granting decision.
    with pytest.raises(RiskAuthorityError):
        app.issue_envelope(
            TENANT, "rdc_g",
            IssueEnvelopeRequest(decision_id=decision.decision_id,
                                 audience="rt", session_id="s", nonce="n"),
        )


def test_issue_decision_requires_authority_review_state():
    """A decision cannot be issued before the case reaches AUTHORITY_REVIEW, and
    the guard must run before anything is persisted."""

    app = build_application()
    _create(app)  # case is CONTROLS_RESOLVED, evaluate() has not run
    forged = RiskEvaluation(
        recommendation=RiskRecommendation.ALLOW, applicable_rules=(),
        required_controls=(), failed_controls=(), conditions=(), trace=(),
    )
    with pytest.raises(RiskAuthorityError):
        app.issue_decision(
            TENANT, "rdc_g", forged,
            DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
        )
    # Nothing was persisted by the rejected call.
    assert app.decisions.get(TENANT, "risk_dec_000001") is None
    assert app.cases.get(TENANT, "rdc_g").state is RiskCaseState.CONTROLS_RESOLVED


def test_expired_decision_cannot_issue_envelope():
    """An envelope may not be minted from a decision whose window has elapsed."""

    app = build_application()
    _create(app)
    evaluation = app.evaluate(
        TENANT, "rdc_g",
        EvaluateRequest(control_results=tuple(
            ControlResultInput(c, "PASS") for c in _ALL_CONTROLS
        )),
    )
    decision = app.issue_decision(
        TENANT, "rdc_g", evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    assert decision.grants_authority
    # Advance the clock past the 1-hour decision TTL.
    app._clock = lambda: FIXED_NOW + timedelta(hours=5)
    with pytest.raises(RiskAuthorityError):
        app.issue_envelope(
            TENANT, "rdc_g",
            IssueEnvelopeRequest(decision_id=decision.decision_id,
                                 audience="rt", session_id="s", nonce="n"),
        )
