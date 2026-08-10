"""Duplicate control results must fail closed.

A required control that has *any* non-satisfying result must fail even when a
later (or earlier) PASS is submitted for the same control id. Otherwise a caller
could mask a FAIL by appending a PASS — defeating the non-compensatory gate.
These tests fail against a last-wins implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.api import (
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
)
from risk_authority.domain.controls import (
    ControlResult,
    required_controls_satisfied,
    unsatisfied_controls,
)
from risk_authority.domain.enums import ControlStatus, RiskClass, RiskOutcome

from tests.scenario import (
    ACTOR,
    FINANCE_SCOPE,
    MODEL,
    PRINCIPAL,
    TENANT,
    build_application,
)

NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _r(control_id: str, status: ControlStatus) -> ControlResult:
    return ControlResult(control_id=control_id, status=status, evaluated_at=NOW)


@pytest.mark.parametrize(
    "dupes",
    [
        (ControlStatus.PASS, ControlStatus.FAIL),   # PASS then FAIL
        (ControlStatus.FAIL, ControlStatus.PASS),   # FAIL then PASS (the mask attempt)
        (ControlStatus.PASS, ControlStatus.UNKNOWN),
        (ControlStatus.PASS, ControlStatus.PASS, ControlStatus.FAIL),
    ],
)
def test_duplicate_results_cannot_mask_failure(dupes):
    required = ("C1",)
    results = tuple(_r("C1", s) for s in dupes)
    assert not required_controls_satisfied(required, results, NOW)
    failed = unsatisfied_controls(required, results, NOW)
    assert failed and failed[0][0] == "C1"
    # The reported status is a genuinely non-satisfying one.
    assert failed[0][1] not in (ControlStatus.PASS, ControlStatus.NOT_APPLICABLE)


def test_all_pass_duplicates_still_satisfy():
    # Sanity: duplicates that are all satisfying do not spuriously fail.
    required = ("C1",)
    results = (_r("C1", ControlStatus.PASS), _r("C1", ControlStatus.NOT_APPLICABLE))
    assert required_controls_satisfied(required, results, NOW)
    assert unsatisfied_controls(required, results, NOW) == ()


def test_facade_duplicate_control_fail_is_not_masked():
    """End-to-end: submitting a duplicate PASS after a FAIL for a required
    control must still produce a DENY decision through the facade."""

    app = build_application()
    app.create_case(
        CreateCaseRequest(
            tenant_id=TENANT, case_id="rdc_dup", subject_id=ACTOR, model_id=MODEL,
            purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
            tools=("crm.read", "refund.prepare"), autonomy_level=2,
            data_classes=("CUSTOMER_PII",), workflow_ir_id="finance-ai-risk",
            inherent_risk=RiskClass.HIGH, residual_risk=RiskClass.MEDIUM,
        )
    )
    evaluation = app.evaluate(
        TENANT, "rdc_dup",
        EvaluateRequest(control_results=(
            ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
            ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
            # BIAS_EVALUATION_CURRENT arrives FAIL, then a masking PASS duplicate.
            ControlResultInput("BIAS_EVALUATION_CURRENT", "FAIL"),
            ControlResultInput("BIAS_EVALUATION_CURRENT", "PASS"),
        )),
    )
    decision = app.issue_decision(
        TENANT, "rdc_dup", evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    assert decision.outcome is RiskOutcome.DENY
    assert not decision.grants_authority
