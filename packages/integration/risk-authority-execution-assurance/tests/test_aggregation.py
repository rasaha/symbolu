"""Safe non-compensatory aggregation — the M-1 closure (spec §6/D-C, §13, §17).

These tests operate directly on Decision Authority ``ExecutionRecord`` objects (the
reused type) and assert the ratified invariant: a material unfavorable effect can
never be masked by a later favorable one absent an explicit finality/version
supersession of the SAME effect identity. No last-writer-wins.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_decision_authority.execution.execution_record import ExecutionRecord
from ugence_decision_authority.execution.status import BusinessOutcome, Finality, OutcomeSource

from ugence_risk_authority_execution_assurance import (
    EffectFinality,
    EffectReasonCode,
    EffectReconciliationOutcome,
    safe_aggregate,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
EXPECTED = {"target": "i-123"}


def rec(
    rid: str,
    outcome: BusinessOutcome,
    finality: Finality,
    *,
    external_result_id: str = "",
    params=None,
) -> ExecutionRecord:
    r = ExecutionRecord(
        execution_record_id=rid,
        execution_intent_id="exi1",
        execution_attempt_id="exa1",
        tenant_id="t1",
        external_system="cloud",
        external_request_id="ext-1",
        external_result_id=external_result_id,
        business_outcome=outcome,
        observed_parameters=dict(params if params is not None else EXPECTED),
        observed_at=NOW,
        source=OutcomeSource.EXTERNAL_CALLBACK,
        finality=finality,
    )
    return r.model_copy(update={"content_hash": r.compute_hash()})


# ---------------------------------------------------------------- MATCHED ----
def test_single_matching_final_is_matched():
    out = safe_aggregate(
        [rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1")],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    assert out.finality is EffectFinality.FINAL
    assert not out.compensation_recommended


def test_duplicate_identical_final_observations_collapse_to_matched():
    # Same effect identity observed twice, identical FINAL SUCCEEDED → idempotent.
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MATCHED


# ------------------------------------------------------- M-1 favorable-mask ----
def test_final_failed_then_final_succeeded_is_not_matched():
    # THE M-1 CASE: DA latest-wins would call this RECONCILED. Aggregation must not.
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e-fail"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e-ok"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is not EffectReconciliationOutcome.MATCHED
    assert out.outcome.is_material
    assert out.outcome is EffectReconciliationOutcome.CONFLICTED
    assert EffectReasonCode.FAVORABLE_MASK_BLOCKED in out.reason_codes
    assert out.compensation_recommended


def test_final_succeeded_then_final_failed_is_not_matched():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e-ok"),
            rec("r2", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e-fail"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is not EffectReconciliationOutcome.MATCHED
    assert out.outcome.is_material


def test_lone_final_failed_is_mismatch():
    out = safe_aggregate(
        [rec("r1", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e-fail")],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
    assert EffectReasonCode.OUTCOME_FAILED in out.reason_codes
    assert out.compensation_recommended


def test_final_failed_cannot_be_masked_by_later_pending_success():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e-fail"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.NON_FINAL, external_result_id="e-ok"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MISMATCH


# --------------------------------------------- explicit finality supersession ----
def test_partial_then_final_matched_supersedes_same_identity():
    # PARTIAL → FINAL of the SAME identity is the ONLY legitimate supersession.
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.PARTIALLY_SUCCEEDED, Finality.NON_FINAL, external_result_id="e1"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MATCHED


def test_pending_then_final_mismatch_same_identity():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.UNKNOWN, Finality.NON_FINAL, external_result_id="e1"),
            rec("r2", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e1"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MISMATCH


def test_supersession_does_not_cross_identities():
    # A FINAL failed on identity A is NOT superseded by a FINAL success on identity B.
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="A"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="B"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is not EffectReconciliationOutcome.MATCHED


# --------------------------------------------------- conflicting observers ----
def test_two_conflicting_final_observers_conflicted():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="prov"),
            rec("r2", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="ledger"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.CONFLICTED


def test_same_identity_contradicting_finals_conflicted():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1"),
            rec("r2", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e1"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.CONFLICTED


# -------------------------------------------------------- duplicate effect ----
def test_two_distinct_successful_effects_is_manual_review():
    out = safe_aggregate(
        [
            rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1"),
            rec("r2", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e2"),
        ],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MANUAL_REVIEW
    assert EffectReasonCode.DUPLICATE_EFFECT in out.reason_codes
    assert out.outcome.is_material


# ---------------------------------------------------------- partial/pending ----
def test_partial_within_policy_is_partial_not_mismatch():
    out = safe_aggregate(
        [rec("r1", BusinessOutcome.PARTIALLY_SUCCEEDED, Finality.NON_FINAL, external_result_id="e1")],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.PARTIAL
    assert out.finality is EffectFinality.PARTIAL
    assert not out.outcome.is_material  # no signal yet


def test_pending_unknown_is_unknown_never_matched():
    out = safe_aggregate(
        [rec("r1", BusinessOutcome.UNKNOWN, Finality.UNKNOWN, external_result_id="")],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.UNKNOWN
    assert out.outcome is not EffectReconciliationOutcome.MATCHED


def test_no_records_is_unknown():
    out = safe_aggregate([], expected_parameters=EXPECTED)
    assert out.outcome is EffectReconciliationOutcome.UNKNOWN
    assert EffectReasonCode.NO_OBSERVATION in out.reason_codes


# ------------------------------------------------------------ param mismatch ----
def test_final_success_with_param_mismatch_is_mismatch():
    out = safe_aggregate(
        [rec("r1", BusinessOutcome.SUCCEEDED, Finality.FINAL, external_result_id="e1",
             params={"target": "i-999"})],
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
    assert EffectReasonCode.PARAMETER_MISMATCH in out.reason_codes


# ------------------------------------------------- malformed hardening (§29) ----
@pytest.mark.parametrize("bad", [None, True, False, 1, 0, "MATCHED", (), [], {}, object()])
def test_malformed_records_never_become_matched(bad):
    out = safe_aggregate([bad], expected_parameters=EXPECTED)  # type: ignore[list-item]
    assert out.outcome is not EffectReconciliationOutcome.MATCHED
    assert out.outcome is EffectReconciliationOutcome.UNKNOWN


def test_malformed_record_dropped_but_valid_failed_dominates():
    out = safe_aggregate(
        [object(), rec("r1", BusinessOutcome.FAILED, Finality.FINAL, external_result_id="e1")],  # type: ignore[list-item]
        expected_parameters=EXPECTED,
    )
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
