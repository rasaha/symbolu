"""RA-8 neutral contracts — evidence only, no authority (spec §12–§14, §28, §31)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_decision_authority.execution.status import BusinessOutcome, Finality, ReconciliationStatus

from ugence_risk_authority_execution_assurance import (
    DA_STATUS_TO_OUTCOME,
    EffectAssuranceAssessment,
    EffectFinality,
    EffectObservation,
    EffectReconciliationOutcome,
    ExecutionCorrelation,
    effect_finality_of,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _obs(**kw) -> EffectObservation:
    base = dict(
        schema_version="1",
        observation_id="o1",
        tenant_id="t1",
        workflow_instance_id="wf1",
        envelope_id="env",
        authorized_action_digest="pf1",
        attempt_id="a1",
        external_request_id="ext1",
        business_outcome=BusinessOutcome.SUCCEEDED,
        finality=Finality.FINAL,
    )
    base.update(kw)
    return EffectObservation(**base)


def test_correlation_digest_is_deterministic_and_replay_safe():
    c1 = ExecutionCorrelation(
        tenant_id="t1", workflow_instance_id="wf1", envelope_id="env",
        authorized_action_digest="pf1", correlation_id="c1", attempt_id="a1",
    )
    c2 = ExecutionCorrelation(
        tenant_id="t1", workflow_instance_id="wf1", envelope_id="env",
        authorized_action_digest="pf1", correlation_id="c1", attempt_id="a1",
    )
    assert c1.correlation_digest == c2.correlation_digest
    # A different envelope changes the binding digest (no cross-envelope collision).
    c3 = ExecutionCorrelation(
        tenant_id="t1", workflow_instance_id="wf1", envelope_id="OTHER",
        authorized_action_digest="pf1", correlation_id="c1", attempt_id="a1",
    )
    assert c3.correlation_digest != c1.correlation_digest


def test_correlation_binding_errors_fail_closed():
    c = ExecutionCorrelation(
        tenant_id="", workflow_instance_id="wf1", envelope_id="env",
        authorized_action_digest="pf1", correlation_id="c1", attempt_id="a1",
    )
    assert "missing tenant_id" in c.binding_errors()


def test_observation_binding_errors_and_effect_finality():
    ok = _obs()
    assert ok.binding_errors() == ()
    assert ok.effect_finality is EffectFinality.FINAL
    partial = _obs(business_outcome=BusinessOutcome.PARTIALLY_SUCCEEDED, finality=Finality.NON_FINAL)
    assert partial.effect_finality is EffectFinality.PARTIAL
    pending = _obs(business_outcome=BusinessOutcome.UNKNOWN, finality=Finality.UNKNOWN)
    assert pending.effect_finality is EffectFinality.PENDING


def test_observation_malformed_business_outcome_flagged():
    bad = _obs(business_outcome="SUCCEEDED")  # str, not enum
    assert "business_outcome is not a BusinessOutcome" in bad.binding_errors()


def test_effect_finality_of_never_fabricates_final():
    assert effect_finality_of(BusinessOutcome.SUCCEEDED, Finality.UNKNOWN) is EffectFinality.PENDING
    assert effect_finality_of(BusinessOutcome.SUCCEEDED, "FINAL") is EffectFinality.PENDING  # type: ignore[arg-type]


def test_da_status_map_covers_all_da_statuses():
    for status in ReconciliationStatus:
        assert status in DA_STATUS_TO_OUTCOME
    assert DA_STATUS_TO_OUTCOME[ReconciliationStatus.RECONCILED] is EffectReconciliationOutcome.MATCHED
    assert DA_STATUS_TO_OUTCOME[ReconciliationStatus.COMPENSATION_REQUIRED] is EffectReconciliationOutcome.MISMATCH


def test_outcome_materiality():
    material = {
        EffectReconciliationOutcome.MISMATCH,
        EffectReconciliationOutcome.CONFLICTED,
        EffectReconciliationOutcome.MANUAL_REVIEW,
    }
    for o in EffectReconciliationOutcome:
        assert o.is_material is (o in material)
    # MATCHED / UNKNOWN / UNVERIFIABLE / PARTIAL are never material.
    assert not EffectReconciliationOutcome.MATCHED.is_material
    assert not EffectReconciliationOutcome.UNVERIFIABLE.is_material


def test_no_outcome_names_authority():
    banned = {"ALLOW", "GRANT", "AUTHORIZED"}
    assert {o.value for o in EffectReconciliationOutcome}.isdisjoint(banned)


def test_assessment_has_no_authority_fields():
    a = EffectAssuranceAssessment(
        assessment_id="a1", tenant_id="t1", workflow_instance_id="wf1", envelope_id="env",
        authorized_action_digest="pf1", attempt_id="at1",
        outcome=EffectReconciliationOutcome.MISMATCH, finality=EffectFinality.FINAL, produced_at=NOW,
    )
    fields = set(vars(a).keys())
    for banned in ("scope", "token", "grant", "allow", "authorization", "credential", "capability"):
        assert not any(banned in f.lower() for f in fields), f"authority-ish field {banned}"
    assert a.is_material
