"""Phase E — prerequisites scenarios 11–18 (receipt persistence) and the derived
lifecycle reads of 19–23 and 25, on both adapters."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from ugence_action_clearance import ClearanceReceiptBody, ClearanceStatus

from ugence_execution_reservation import (
    ClearanceReceipt,
    PutReceiptResult,
    ReceiptIntegrityError,
    ReceiptLifecycleState,
    RevocationResult,
    SupersessionResult,
    verify_receipt_body,
)

from _fixtures import STORE_KINDS, T0, blocked_result, clear_result, make_store, receipt_for, ts


@pytest.fixture(params=STORE_KINDS)
def store(request, tmp_path):
    s = make_store(request.param, tmp_path)
    yield s
    s.close()


def test_11_first_put_creates_and_issues(store):
    r = receipt_for(clear_result())
    assert store.put_receipt(r) is PutReceiptResult.CREATED
    events = store.receipt_events(r.receipt_id)
    assert [e.event_type for e in events] == [ReceiptLifecycleState.ISSUED]
    assert events[0].sequence == 0 and events[0].owner == "workflow_service"
    assert store.lifecycle_state_at(r.receipt_id, T0) is ReceiptLifecycleState.ISSUED


def test_12_identical_put_is_idempotent(store):
    r = receipt_for(clear_result())
    store.put_receipt(r)
    assert store.put_receipt(r) is PutReceiptResult.ALREADY_EXISTS_IDENTICAL
    assert len(store.receipt_events(r.receipt_id)) == 1  # no second ISSUED


def test_13_same_id_different_record_conflicts(store):
    result = clear_result()
    store.put_receipt(receipt_for(result))
    other = receipt_for(result, workflow_id="wf-different")  # same body, different record
    assert store.put_receipt(other) is PutReceiptResult.CONFLICT_DIFFERENT_BODY
    assert store.get_receipt(other.receipt_id).workflow_id == ""  # nothing written


def test_14_mutating_the_body_is_rejected(store):
    r = receipt_for(clear_result())
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.body.clearance_status = ClearanceStatus.BLOCK  # type: ignore[misc]
    tampered = ClearanceReceiptBody(**{**r.body.__dict__, "obligations": ()})
    with pytest.raises(ReceiptIntegrityError):
        verify_receipt_body(tampered)
    with pytest.raises(ReceiptIntegrityError):
        store.put_receipt(ClearanceReceipt(**{**r.__dict__, "body": tampered}))


def test_15_retrieval_is_byte_identical(store):
    r = receipt_for(clear_result())
    store.put_receipt(r)
    got = store.get_receipt(r.receipt_id)
    assert got == r
    assert got.canonical_bytes() == r.canonical_bytes()
    assert store.get_receipt_by_result_fingerprint(r.body.result_fingerprint) == r
    assert store.get_receipt("acr_missing") is None


def test_17_supersession_links_old_to_new_and_leaves_bodies_untouched(store):
    old = receipt_for(clear_result())
    new = receipt_for(clear_result(evaluation_time=ts(minutes=10)))
    assert old.lineage_key == new.lineage_key and old.receipt_id != new.receipt_id
    store.put_receipt(old)
    assert store.supersede_receipt(old.receipt_id, "fresher", new.receipt_id, occurred_at=ts(minutes=10)) \
        is SupersessionResult.SUCCESSOR_NOT_FOUND
    store.put_receipt(new)
    assert store.supersede_receipt(old.receipt_id, "fresher", new.receipt_id, occurred_at=ts(minutes=10)) \
        is SupersessionResult.SUPERSEDED
    assert store.supersede_receipt(old.receipt_id, "again", new.receipt_id, occurred_at=ts(minutes=11)) \
        is SupersessionResult.ALREADY_SUPERSEDED
    ev = store.receipt_events(old.receipt_id)[-1]
    assert ev.event_type is ReceiptLifecycleState.SUPERSEDED and ev.ref == new.receipt_id
    assert store.get_receipt(old.receipt_id).canonical_bytes() == old.canonical_bytes()
    assert store.lifecycle_state_at(old.receipt_id, ts(minutes=12)) is ReceiptLifecycleState.SUPERSEDED
    assert store.lifecycle_state_at(new.receipt_id, ts(minutes=12)) is ReceiptLifecycleState.ISSUED
    assert len(store.list_receipts_for_authorization(old.tenant_id, old.authorization_ref)) == 2


def test_18_revocation_appends_and_never_rewrites(store):
    r = receipt_for(clear_result())
    store.put_receipt(r)
    assert store.revoke_receipt(r.receipt_id, "authorization revoked", "authz-event-9",
                                occurred_at=ts(minutes=5)) is RevocationResult.REVOKED
    assert store.revoke_receipt(r.receipt_id, "again", "x", occurred_at=ts(minutes=6)) \
        is RevocationResult.ALREADY_REVOKED
    assert store.revoke_receipt("acr_missing", "x", "x", occurred_at=ts()) is RevocationResult.NOT_FOUND
    assert store.get_receipt(r.receipt_id).canonical_bytes() == r.canonical_bytes()
    assert store.lifecycle_state_at(r.receipt_id, ts(minutes=7)) is ReceiptLifecycleState.REVOKED


def test_19_20_derived_expiry_is_half_open(store):
    r = receipt_for(clear_result())
    store.put_receipt(r)
    vu = r.body.valid_until
    assert store.lifecycle_state_at(r.receipt_id, vu - timedelta(microseconds=1)) is ReceiptLifecycleState.ISSUED
    assert store.lifecycle_state_at(r.receipt_id, vu) is ReceiptLifecycleState.EXPIRED  # boundary = expired
    assert not store.receipt_events(r.receipt_id)[-1].event_type is ReceiptLifecycleState.EXPIRED  # derived, not stored


def test_23_changed_action_fingerprint_is_a_new_lineage(store):
    old = receipt_for(clear_result())
    new = receipt_for(clear_result(fp="ACTION-FP-002"))
    store.put_receipt(old); store.put_receipt(new)
    assert old.lineage_key != new.lineage_key
    assert store.supersede_receipt(old.receipt_id, "changed action", new.receipt_id, occurred_at=ts()) \
        is SupersessionResult.LINEAGE_MISMATCH
    assert store.lifecycle_state_at(old.receipt_id, ts()) is ReceiptLifecycleState.ISSUED


def test_25_lifecycle_events_are_sequence_ordered_and_precedence_is_fixed(store):
    r = receipt_for(clear_result())
    new = receipt_for(clear_result(evaluation_time=ts(minutes=1)))
    store.put_receipt(r); store.put_receipt(new)
    store.supersede_receipt(r.receipt_id, "fresher", new.receipt_id, occurred_at=ts(minutes=1))
    store.revoke_receipt(r.receipt_id, "upstream", "u-1", occurred_at=ts(minutes=2))
    assert store.invalidate_receipt(r.receipt_id, "chain broken", occurred_at=ts(minutes=3))
    events = store.receipt_events(r.receipt_id)
    assert [e.sequence for e in events] == [0, 1, 2, 3]
    assert [e.event_type.value for e in events] == ["ISSUED", "SUPERSEDED", "REVOKED", "INVALIDATED"]
    assert store.lifecycle_state_at(r.receipt_id, ts(minutes=4)) is ReceiptLifecycleState.INVALIDATED


def test_non_clear_results_are_recorded_but_never_issued(store):
    r = receipt_for(blocked_result())
    assert not r.is_clear
    assert store.put_receipt(r) is PutReceiptResult.CREATED
    assert store.receipt_events(r.receipt_id) == ()
    assert store.lifecycle_state_at(r.receipt_id, T0) is None
