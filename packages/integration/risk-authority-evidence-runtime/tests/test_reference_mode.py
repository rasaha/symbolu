"""Reference/conformance mode preservation + schema fail-closed (Phase 21, 12).

Reference mode (no production ports) must remain independently usable: the
RA-1→RA-4 caller-asserted control path still works there. Production mode never
silently falls back to it, and it is documented as conformance-only. Also proves
that a malformed/unsupported evidence schema cannot even be constructed —
fail-closed at the contract boundary (§9).
"""

from __future__ import annotations

import dataclasses
from datetime import timezone

import pytest

from risk_authority.api.schemas import (
    ControlResultInput,
    CreateCaseRequest,
    EvaluateRequest,
)
from risk_authority.api.dependencies import RiskAuthorityApplication
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain.enums import RiskClass, RiskRecommendation
from risk_authority.integrations import InMemoryWorkflowIRSource

import ra5_scenario as C


def _reference_app() -> RiskAuthorityApplication:
    source = InMemoryWorkflowIRSource()
    source.register(C.build_workflow())
    key = SigningKeyRecord(C.KEY_ID, SigningKey.from_seed(bytes(range(32))))
    app = RiskAuthorityApplication(
        workflow_source=source, key_record=key, clock=lambda: C.FIXED_NOW
    )  # production_mode defaults False ⇒ reference mode.
    app.authority.add_grant(C.build_grant())
    return app


def test_reference_mode_caller_asserted_pass_still_works():
    app = _reference_app()
    app.create_case(
        CreateCaseRequest(
            tenant_id=C.TENANT, case_id="rdc_ref", subject_id=C.ACTOR, model_id=C.MODEL,
            purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
            tools=("crm.read",), autonomy_level=2, data_classes=("CUSTOMER_PII",),
            workflow_ir_id="finance-ai-risk", inherent_risk=RiskClass.HIGH,
            residual_risk=RiskClass.MEDIUM,
        )
    )
    evaluation = app.evaluate(
        C.TENANT,
        "rdc_ref",
        EvaluateRequest(
            control_results=tuple(
                ControlResultInput(c, "PASS") for c in C.REQUIRED_CONTROLS
            )
        ),
    )
    # Reference mode is explicitly permitted to trust caller-asserted PASS.
    assert evaluation.recommendation is RiskRecommendation.ALLOW


def test_production_and_reference_are_distinct_modes():
    ref = _reference_app()
    assert ref._production_mode is False
    prod = C.build_runtime().application
    assert prod._production_mode is True


def test_unsupported_evidence_schema_cannot_be_constructed():
    good = C.make_evidence("ev1")
    with pytest.raises(ValueError):
        dataclasses.replace(good, schema_version="totally-unknown-schema")


def test_impossible_timestamp_window_rejected():
    good = C.make_evidence("ev1")
    # valid_until before observed_at is a negative freshness window — rejected.
    with pytest.raises(ValueError):
        dataclasses.replace(
            good, valid_until=good.created_at.replace(year=2000, tzinfo=timezone.utc)
        )


def test_empty_required_identifier_rejected():
    good = C.make_evidence("ev1")
    with pytest.raises(ValueError):
        dataclasses.replace(good, evidence_id="")
