"""The PRIOR_CONSUMPTION signal: the ratified state mapping, Level-1 provenance, and
an end-to-end run through the real Action Clearance evaluator."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_action_clearance import (
    ClearancePolicy,
    ClearanceReasonCode,
    ClearanceStatus,
    ConsumptionStatus,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    evaluate_clearance,
)
from ugence_governance_contracts.api import ExecutionBusinessOutcome

from ugence_execution_reservation import (
    ADAPTER_ID,
    ReconciledOutcome,
    ReservationState,
    SOURCE_KIND,
    __version__,
    consumption_status_for,
)

from _fixtures import ACTFP, AUTHZ, STORE_KINDS, T0, clear_result, happy_signals, key, make_store, receipt_for, request, ts


@pytest.fixture(params=STORE_KINDS)
def store(request, tmp_path):
    s = make_store(request.param, tmp_path)
    yield s
    s.close()


@pytest.mark.parametrize("state,expected", [
    (None, ConsumptionStatus.UNUSED),
    (ReservationState.AVAILABLE, ConsumptionStatus.UNUSED),
    (ReservationState.RELEASED, ConsumptionStatus.UNUSED),
    (ReservationState.RECONCILED_FAILURE, ConsumptionStatus.UNUSED),
    (ReservationState.RESERVED, ConsumptionStatus.RESERVED),
    (ReservationState.DISPATCHED, ConsumptionStatus.RESERVED),
    (ReservationState.OBSERVED_FAILURE, ConsumptionStatus.RESERVED),
    (ReservationState.OUTCOME_UNCERTAIN, ConsumptionStatus.RESERVED),
    (ReservationState.OBSERVED_SUCCESS, ConsumptionStatus.CONSUMED),
    (ReservationState.RECONCILED_SUCCESS, ConsumptionStatus.CONSUMED),
])
def test_ratified_mapping(state, expected):
    assert consumption_status_for(state) is expected


def test_signal_shape_and_level_one_provenance(store):
    sig = store.consumption_signal(key(), as_of=T0, freshness_s=30)
    assert sig.signal_type is SignalType.PRIOR_CONSUMPTION and sig.status is SignalStatus.PRESENT
    assert sig.value == {"state": "UNUSED"}
    assert sig.tenant_id == key().tenant_id and sig.subject_ref == key().target_ref
    assert sig.authorization_ref == AUTHZ and sig.action_fingerprint == ACTFP
    assert sig.captured_at == T0 and sig.valid_until == T0 + timedelta(seconds=30)
    assert sig.trust_level is SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION
    assert sig.provenance.adapter_id == ADAPTER_ID and sig.provenance.adapter_version == __version__
    assert sig.source_kind == SOURCE_KIND
    assert sig.integrity_digest == sig.content_fingerprint


def test_signal_tracks_the_head_and_reports_abandonment(store):
    r = receipt_for(clear_result()); store.put_receipt(r)
    out = store.reserve_once(key(), r.receipt_id, AUTHZ, ACTFP, 60, as_of=T0)
    sig = store.consumption_signal(key(), as_of=ts(seconds=1))
    assert sig.value == {"state": "RESERVED", "reservation_id": out.reservation.reservation_id}
    assert store.consumption_signal(key(), as_of=ts(seconds=60)).value["state"] == "UNUSED"  # lease lapsed
    store.mark_dispatched(out.reservation.reservation_id, "d-1", dispatch_deadline=ts(minutes=5), as_of=ts(seconds=5))
    store.record_observation(out.reservation.reservation_id, "o-1", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(seconds=6))
    assert store.consumption_signal(key(), as_of=ts(minutes=1)).value["state"] == "CONSUMED"


def test_unavailable_store_reports_unknown_twice_over(store):
    store.close()
    sig = store.consumption_signal(key(), as_of=T0)
    assert sig.status is SignalStatus.UNKNOWN and sig.value == {"state": "UNKNOWN"}


def _policy_with_consumption(**kw):
    return ClearancePolicy(policy_id="p", policy_version="v1",
                           required_signal_types=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY,
                                                  SignalType.PRIOR_CONSUMPTION), **kw)


def test_end_to_end_through_the_action_clearance_evaluator(store):
    r = receipt_for(clear_result()); store.put_receipt(r)
    policy = _policy_with_consumption()

    def evaluate(as_of):
        sig = store.consumption_signal(key(), as_of=as_of)
        return evaluate_clearance(request(happy_signals(captured_at=as_of) + [sig], evaluation_time=as_of), policy)

    fresh = evaluate(T0)
    assert fresh.status is ClearanceStatus.CLEAR, fresh.reason_codes

    out = store.reserve_once(key(), r.receipt_id, AUTHZ, ACTFP, 300, as_of=T0)
    held = evaluate(ts(seconds=1))
    assert held.status is ClearanceStatus.HOLD
    assert ClearanceReasonCode.CONSUMPTION_RESERVED.value in held.reason_codes

    store.mark_dispatched(out.reservation.reservation_id, "d-1", dispatch_deadline=ts(minutes=5), as_of=ts(seconds=2))
    store.record_observation(out.reservation.reservation_id, "o-1", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(seconds=3))
    store.record_reconciliation(out.reservation.reservation_id, "rc-1", ReconciledOutcome.SUCCESS, as_of=ts(seconds=4))
    blocked = evaluate(ts(seconds=5))
    assert blocked.status is ClearanceStatus.BLOCK
    assert ClearanceReasonCode.ALREADY_CONSUMED.value in blocked.reason_codes

    store.close()
    closed = evaluate(ts(seconds=6))
    assert closed.status is not ClearanceStatus.CLEAR  # UNKNOWN fails closed
