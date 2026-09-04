"""Phase G — prerequisites scenarios 26–38 and the state machine, on both adapters."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_governance_contracts.api import ExecutionBusinessOutcome, IdempotencyDisposition

from ugence_execution_reservation import (
    ContractViolation,
    IllegalTransitionError,
    ReconciledOutcome,
    ReservationResult,
    ReservationState,
    ReservationNotFoundError,
    StoreUnavailableError,
)

from _fixtures import (
    ACTFP, AUTHZ, STORE_KINDS, T0, clear_result, key, make_store, receipt_for, ts,
)

TTL = 300


@pytest.fixture(params=STORE_KINDS)
def store(request, tmp_path):
    s = make_store(request.param, tmp_path)
    yield s
    s.close()


@pytest.fixture
def issued(store):
    r = receipt_for(clear_result())
    store.put_receipt(r)
    return r


def reserve(store, r, *, k=None, as_of=T0, authz=AUTHZ, fp=ACTFP, ttl=TTL):
    return store.reserve_once(k or key(), r.receipt_id, authz, fp, ttl, as_of=as_of)


def dispatched(store, r, *, as_of=T0):
    out = reserve(store, r, as_of=as_of)
    assert out.is_acquired
    return store.mark_dispatched(out.reservation.reservation_id, "dispatch-1",
                                 dispatch_deadline=as_of + timedelta(minutes=5), as_of=as_of)


# --------------------------------------------------------------------------- #
# 26–28: acquire, second caller, retry
# --------------------------------------------------------------------------- #
def test_26_first_reserve_once_acquires(store, issued):
    out = reserve(store, issued)
    assert out.result is ReservationResult.ACQUIRED and out.is_acquired
    res = out.reservation
    assert res.state is ReservationState.RESERVED and res.generation == 1
    assert res.lease_expires_at == T0 + timedelta(seconds=TTL)
    assert res.clearance_receipt_ref == issued.receipt_id
    assert store.get_head(key()) == res and store.get_reservation(res.reservation_id) == res
    assert out.resolution.disposition is IdempotencyDisposition.FIRST
    ev = store.reservation_events(res.reservation_id)
    assert [e.event_type for e in ev] == ["RESERVED"] and ev[0].to_state is ReservationState.RESERVED


def test_27_28_second_caller_and_retry_see_the_same_reservation(store, issued):
    first = reserve(store, issued)
    second = reserve(store, issued, as_of=ts(seconds=1))
    assert second.result is ReservationResult.ALREADY_RESERVED
    assert second.reservation.reservation_id == first.reservation.reservation_id
    assert second.resolution.disposition is IdempotencyDisposition.DUPLICATE
    assert second.resolution.duplicate_of == first.reservation.reservation_id
    assert len(store.reservation_events(first.reservation.reservation_id)) == 1  # no new row


# --------------------------------------------------------------------------- #
# 29–31: receipt validation, no TOCTOU
# --------------------------------------------------------------------------- #
def test_29_expired_receipt_is_refused_at_reservation(store, issued):
    out = reserve(store, issued, as_of=issued.body.valid_until)
    assert out.result is ReservationResult.EXPIRED_CLEARANCE and out.reservation is None
    assert out.resolution is None and store.get_head(key()) is None


def test_30_action_fingerprint_mismatch_is_invalid_receipt(store, issued):
    assert reserve(store, issued, fp="FP-OTHER").result is ReservationResult.INVALID_RECEIPT
    assert reserve(store, issued, k=key(fp="FP-OTHER"), fp="FP-OTHER").result is ReservationResult.INVALID_RECEIPT
    assert store.get_head(key()) is None


def test_31_target_and_operation_and_tenant_binding(store, issued):
    assert reserve(store, issued, k=key(target="target-2")).result is ReservationResult.INVALID_RECEIPT
    assert reserve(store, issued, k=key(operation="merge")).result is ReservationResult.INVALID_RECEIPT
    assert reserve(store, issued, k=key(tenant="other")).result is ReservationResult.INVALID_RECEIPT
    assert reserve(store, issued, authz="authz-2").result is ReservationResult.INVALID_RECEIPT


def test_missing_superseded_revoked_and_not_clear_receipts(store, issued):
    out = store.reserve_once(key(), "acr_missing", AUTHZ, ACTFP, TTL, as_of=T0)
    assert out.result is ReservationResult.INVALID_RECEIPT
    newer = receipt_for(clear_result(evaluation_time=ts(minutes=1)))
    store.put_receipt(newer)
    store.supersede_receipt(issued.receipt_id, "fresher", newer.receipt_id, occurred_at=ts(minutes=1))
    assert reserve(store, issued, as_of=ts(minutes=2)).result is ReservationResult.INVALID_RECEIPT
    store.revoke_receipt(newer.receipt_id, "authorization revoked", "ev-1", occurred_at=ts(minutes=2))
    assert reserve(store, newer, as_of=ts(minutes=3)).result is ReservationResult.STALE_AUTHORIZATION
    from _fixtures import blocked_result
    blocked = receipt_for(blocked_result())
    store.put_receipt(blocked)
    assert reserve(store, blocked).result is ReservationResult.INVALID_RECEIPT


def test_a_reissued_receipt_does_not_mint_a_new_key(store, issued):
    first = reserve(store, issued)
    newer = receipt_for(clear_result(evaluation_time=ts(minutes=1)))
    store.put_receipt(newer)
    out = reserve(store, newer, as_of=ts(minutes=1))
    assert out.result is ReservationResult.ALREADY_RESERVED
    assert out.reservation.reservation_id == first.reservation.reservation_id


# --------------------------------------------------------------------------- #
# 32–35: dispatch, uncertainty, reconciliation
# --------------------------------------------------------------------------- #
def test_32_dispatch_timeout_is_uncertain_and_reservation_stays(store, issued):
    res = dispatched(store, issued)
    assert res.state is ReservationState.DISPATCHED and res.dispatch_validity is not None
    assert reserve(store, issued, as_of=ts(minutes=1)).result is ReservationResult.ALREADY_DISPATCHED
    unc = store.mark_outcome_uncertain(res.reservation_id, as_of=res.dispatch_deadline)
    assert unc.state is ReservationState.OUTCOME_UNCERTAIN
    assert store.mark_outcome_uncertain(res.reservation_id, as_of=ts(minutes=6)) == unc  # idempotent
    assert reserve(store, issued, as_of=ts(minutes=6)).result is ReservationResult.ALREADY_DISPATCHED


def test_33_uncertain_and_dispatched_can_never_be_released(store, issued):
    res = dispatched(store, issued)
    with pytest.raises(IllegalTransitionError):
        store.release(res.reservation_id, as_of=ts(minutes=1))
    store.mark_outcome_uncertain(res.reservation_id, as_of=ts(minutes=5))
    with pytest.raises(IllegalTransitionError):
        store.release(res.reservation_id, as_of=ts(minutes=6))
    assert store.get_reservation(res.reservation_id).state is ReservationState.OUTCOME_UNCERTAIN


def test_34_reconciled_failure_permits_a_controlled_retry_with_a_new_generation(store, issued):
    res = dispatched(store, issued)
    store.mark_outcome_uncertain(res.reservation_id, as_of=ts(minutes=5))
    rec = store.record_reconciliation(res.reservation_id, "recon-1", ReconciledOutcome.FAILURE, as_of=ts(minutes=7))
    assert rec.state is ReservationState.RECONCILED_FAILURE
    out = reserve(store, issued, as_of=ts(minutes=8))
    assert out.result is ReservationResult.ACQUIRED
    assert out.reservation.generation == 2 and out.reservation.reservation_id != res.reservation_id
    assert store.get_head(key()) == out.reservation
    assert store.get_reservation(res.reservation_id).state is ReservationState.RECONCILED_FAILURE


def test_35_reconciled_success_is_permanent(store, issued):
    res = dispatched(store, issued)
    store.record_observation(res.reservation_id, "obs-1", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(minutes=1))
    rec = store.record_reconciliation(res.reservation_id, "recon-1", ReconciledOutcome.SUCCESS, as_of=ts(minutes=2))
    assert rec.state is ReservationState.RECONCILED_SUCCESS
    for minute in (3, 60, 60 * 24 * 365):
        out = reserve(store, issued, as_of=ts(minutes=minute))
        assert out.result in (ReservationResult.ALREADY_COMPLETED, ReservationResult.EXPIRED_CLEARANCE)
    late = store.record_reconciliation(res.reservation_id, "recon-2", ReconciledOutcome.FAILURE, as_of=ts(minutes=3))
    assert late.state is ReservationState.RECONCILED_SUCCESS  # never downgraded
    with pytest.raises(IllegalTransitionError):
        store.release(res.reservation_id, as_of=ts(minutes=4))
    assert store.reservation_events(res.reservation_id)[-1].event_type == "RECONCILIATION_LATE"


# --------------------------------------------------------------------------- #
# 36–37: observations
# --------------------------------------------------------------------------- #
def test_36_duplicate_observation_is_a_no_op(store, issued):
    res = dispatched(store, issued)
    a = store.record_observation(res.reservation_id, "obs-1", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(minutes=1))
    b = store.record_observation(res.reservation_id, "obs-1", ExecutionBusinessOutcome.FAILED, as_of=ts(minutes=2))
    assert a == b and a.state is ReservationState.OBSERVED_SUCCESS
    assert len([e for e in store.reservation_events(res.reservation_id) if e.event_type.startswith("OBSERV")]) == 1


def test_37_out_of_order_observations_converge_and_never_downgrade(store, issued, tmp_path):
    res = dispatched(store, issued)
    store.record_observation(res.reservation_id, "obs-ok", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(minutes=1))
    late = store.record_observation(res.reservation_id, "obs-timeout", ExecutionBusinessOutcome.UNKNOWN, as_of=ts(minutes=2))
    assert late.state is ReservationState.OBSERVED_SUCCESS
    assert store.reservation_events(res.reservation_id)[-1].event_type == "OBSERVATION_LATE"
    # The reverse order reaches the same state.
    other = make_store("memory")
    r2 = receipt_for(clear_result()); other.put_receipt(r2)
    res2 = dispatched(other, r2)
    other.record_observation(res2.reservation_id, "obs-timeout", ExecutionBusinessOutcome.UNKNOWN, as_of=ts(minutes=1))
    end = other.record_observation(res2.reservation_id, "obs-ok", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(minutes=2))
    assert end.state is ReservationState.OBSERVED_SUCCESS


def test_observation_requires_a_dispatch(store, issued):
    out = reserve(store, issued)
    with pytest.raises(IllegalTransitionError):
        store.record_observation(out.reservation.reservation_id, "obs-1", ExecutionBusinessOutcome.SUCCEEDED, as_of=ts(minutes=1))
    with pytest.raises(IllegalTransitionError):
        store.record_reconciliation(out.reservation.reservation_id, "r", ReconciledOutcome.SUCCESS, as_of=ts(minutes=1))


# --------------------------------------------------------------------------- #
# 38: outage
# --------------------------------------------------------------------------- #
def test_38_store_unavailable_fails_closed(store, issued):
    store.close()
    with pytest.raises(StoreUnavailableError):
        reserve(store, issued)
    with pytest.raises(StoreUnavailableError):
        store.get_head(key())


# --------------------------------------------------------------------------- #
# Leases, abandonment, release, inputs
# --------------------------------------------------------------------------- #
def test_abandoned_pre_dispatch_reservation_is_released_then_reacquired(store, issued):
    first = reserve(store, issued)
    lapsed = ts(seconds=TTL)
    assert first.reservation.is_abandoned_at(lapsed)
    with pytest.raises(IllegalTransitionError):
        store.mark_dispatched(first.reservation.reservation_id, "d", dispatch_deadline=ts(seconds=TTL + 60), as_of=lapsed)
    out = reserve(store, issued, as_of=lapsed)
    assert out.is_acquired and out.reservation.generation == 2
    assert store.get_reservation(first.reservation.reservation_id).state is ReservationState.RELEASED
    assert store.reservation_events(first.reservation.reservation_id)[-1].event_type == "RELEASED_ABANDONED"


def test_lease_renewal_only_extends_a_live_reservation(store, issued):
    out = reserve(store, issued)
    rid = out.reservation.reservation_id
    renewed = store.renew_lease(rid, lease_expires_at=ts(seconds=TTL * 2), as_of=ts(seconds=10))
    assert renewed.lease_expires_at == ts(seconds=TTL * 2)
    with pytest.raises(IllegalTransitionError):
        store.renew_lease(rid, lease_expires_at=ts(seconds=TTL), as_of=ts(seconds=11))  # shorter
    assert not renewed.is_abandoned_at(ts(seconds=TTL + 1))


def test_voluntary_release_before_dispatch_frees_the_key(store, issued):
    out = reserve(store, issued)
    rel = store.release(out.reservation.reservation_id, as_of=ts(seconds=5))
    assert rel.state is ReservationState.RELEASED
    assert store.release(out.reservation.reservation_id, as_of=ts(seconds=6)) == rel
    assert reserve(store, issued, as_of=ts(seconds=7)).is_acquired


def test_inputs_are_validated(store, issued):
    from datetime import datetime
    with pytest.raises(ContractViolation):
        store.reserve_once(key(), issued.receipt_id, AUTHZ, ACTFP, TTL, as_of=datetime(2026, 1, 1))
    with pytest.raises(ContractViolation):
        store.reserve_once(key(), issued.receipt_id, AUTHZ, ACTFP, 0, as_of=T0)
    with pytest.raises(ReservationNotFoundError):
        store.release("rsv_missing", as_of=T0)
    out = reserve(store, issued)
    with pytest.raises(ContractViolation):
        store.mark_dispatched(out.reservation.reservation_id, " ", dispatch_deadline=ts(minutes=1), as_of=T0)
    with pytest.raises(IllegalTransitionError):
        store.mark_dispatched(out.reservation.reservation_id, "d", dispatch_deadline=T0, as_of=T0)


def test_records_round_trip_through_storage(store, issued):
    res = dispatched(store, issued)
    got = store.get_reservation(res.reservation_id)
    assert got == res and got.to_dict() == res.to_dict()
    assert got.execution_key == key() and got.lease == res.lease
