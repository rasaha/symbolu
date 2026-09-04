"""The refusal vocabulary is closed; a record is a record, never a claim of execution beyond its mode."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_decision_authority.execution.status import BusinessOutcome, Finality

from ugence_cloud_scaling_bounded_execution import (
    RECORD_SCHEMA_VERSION,
    BoundedDispatchOutcome,
    BoundedExecutionContractError,
    BoundedExecutionRecord,
    DispatchRefusal,
    business_outcome_for,
    derive_record_id,
    finality_for,
)


def test_the_refusal_vocabulary_names_every_gate():
    values = {r.value for r in DispatchRefusal}
    for needed in ("GRANT_NOT_FOUND", "GRANT_EXPIRED", "GRANT_NOT_REDERIVED", "RESERVATION_NOT_RESERVED",
                   "LEASE_EXPIRED", "TARGET_SCOPE_MISMATCH", "ACTION_NOT_DISPATCHABLE", "EXECUTOR_INTEGRITY"):
        assert needed in values


def test_an_outcome_without_a_record_is_not_dispatched_or_applied():
    out = BoundedDispatchOutcome(dispatched_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert not out.dispatched and not out.applied and not out.replayed


def test_outcome_mapping_is_closed_and_conservative():
    assert business_outcome_for("applied") is BusinessOutcome.SUCCEEDED
    assert business_outcome_for("simulated") is BusinessOutcome.SUCCEEDED
    assert business_outcome_for("denied") is BusinessOutcome.REJECTED
    assert business_outcome_for("failed") is BusinessOutcome.FAILED
    assert business_outcome_for("duplicate") is BusinessOutcome.DUPLICATE
    assert business_outcome_for("proposed") is BusinessOutcome.UNKNOWN
    assert business_outcome_for("something-new") is BusinessOutcome.UNKNOWN
    assert finality_for("proposed", False) is Finality.UNKNOWN and finality_for("simulated", True) is Finality.FINAL


def test_a_record_cannot_claim_applied_outside_live():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    kw = dict(schema_version=RECORD_SCHEMA_VERSION, record_id=derive_record_id("t", "g", "a"), tenant_id="t", grant_id="g",
              reservation_id="r", execution_key="k", target_scope_digest="sha256:" + "a" * 64, envelope_id="e",
              authorized_action_digest="sha256:" + "b" * 64, request_digest="credreq.v1:" + "c" * 64, attempt_id="a",
              external_request_id="x", effective_mode="simulation", mode_reasons=(), ops_outcome="simulated",
              business_outcome=BusinessOutcome.SUCCEEDED, finality=Finality.FINAL, applied=True, pre_state=1,
              post_state=2, requested_magnitude=2, dispatched_at=now, observed_at=now, receipt_hash="h")
    with pytest.raises(BoundedExecutionContractError, match="LIVE"):
        BoundedExecutionRecord(**kw)
    assert BoundedExecutionRecord(**{**kw, "applied": False}).workflow_instance_id == "r"
