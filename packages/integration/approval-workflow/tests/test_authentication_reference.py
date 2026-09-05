"""AI-D, approver-identity ruling ID-2: the approval record carries an optional,
digest-bound ``authentication_reference`` behind ``decided_by``, and the ledger's
hash-linked decision event carries it too (identity-ADR matrix row 9).

Two things must hold at once: a record decided without a reference is byte-for-byte
what it was before the field existed, so every artifact digest and every chain that
predates AI-D still verifies; and a record decided with one cannot have its
``decided_by`` or its reference altered without the artifact digest or the event
chain saying so.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ugence_approval_workflow import (
    ApprovalRecord,
    ApprovalState,
    ArtifactIntegrityError,
    ReviewDecision,
    SqliteApprovalWorkflowStore,
)

import _fixtures as F

REFERENCE = "authn:sha256:" + "ab" * 32


def _decided(store, *, reference: str = REFERENCE):
    record = store.request_approval(F.subject(), requested_by=F.REQUESTER, required_role=F.ROLE,
                                    validity=F.window(), as_of=F.T0)
    store.present_for_decision(record.approval_id, as_of=F.T0)
    return store.decide(record.approval_id, approver=F.APPROVER, decision=ReviewDecision.GRANT,
                        as_of=F.T1, authentication_reference=reference)


# --------------------------------------------------------------------------- #
# additive: nothing that existed changes
# --------------------------------------------------------------------------- #
def test_a_record_without_a_reference_serialises_and_digests_exactly_as_before():
    record = F.granted(F.memory_store())
    assert record.authentication_reference == ""
    assert "authentication_reference" not in record.to_dict()
    # A dict written before the field existed round-trips and re-derives its digest.
    legacy = {k: v for k, v in record.to_dict().items()}
    reloaded = ApprovalRecord.from_dict(legacy)
    assert reloaded == record and reloaded.artifact_digest() == record.artifact_digest()
    assert "signature_reference" in legacy and legacy["signature_reference"] == ""


def test_a_ledger_written_before_the_field_existed_still_verifies(tmp_path):
    store = F.sqlite_store(tmp_path)
    record = F.granted(store)
    assert store.verify_chain()
    reopened = SqliteApprovalWorkflowStore(F.sqlite_path(tmp_path), F.directory())
    assert reopened.get_approval(record.approval_id) == record
    assert reopened.verify_chain()
    detail = json.loads(reopened.approval_events(record.approval_id)[-1].detail)
    assert "authentication_reference" not in detail, "absent when nothing was recorded"
    reopened.close()
    store.close()


# --------------------------------------------------------------------------- #
# recorded: in the record, in the event, in the chain
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("make", [lambda tmp: F.memory_store(), lambda tmp: F.sqlite_store(tmp)])
def test_decide_records_the_reference_on_the_record_and_leaves_signature_reference_unused(
        tmp_path, make):
    store = make(tmp_path)
    record = _decided(store)
    assert record.state is ApprovalState.GRANTED
    assert record.authentication_reference == REFERENCE
    assert record.decided_by == F.APPROVER.approver_id
    assert record.decided_authority_reference == F.APPROVER.authority_reference
    assert record.signature_reference == ""
    assert record.to_dict()["authentication_reference"] == REFERENCE
    assert ApprovalRecord.from_dict(record.to_dict()) == record
    assert store.get_approval(record.approval_id).authentication_reference == REFERENCE


def test_the_reference_is_part_of_the_hash_linked_decision_event(tmp_path):
    store = F.sqlite_store(tmp_path)
    record = _decided(store)
    events = store.approval_events(record.approval_id)
    decided = [e for e in events if e.event_type is ApprovalState.GRANTED]
    assert len(decided) == 1
    detail = json.loads(decided[0].detail)
    assert detail == {"decision": "GRANT", "role": F.ROLE, "authentication_reference": REFERENCE}
    assert store.verify_chain()
    store.close()


def test_a_blank_reference_is_recorded_as_none_and_a_non_string_is_refused(tmp_path):
    store = F.sqlite_store(tmp_path)
    record = _decided(store, reference="   ")
    assert record.authentication_reference == ""
    assert "authentication_reference" not in json.loads(
        store.approval_events(record.approval_id)[-1].detail)
    from ugence_approval_workflow import ContractViolation

    other = store.request_approval(F.subject("e" * 64), requested_by=F.REQUESTER,
                                   required_role=F.ROLE, validity=F.window(), as_of=F.T0)
    store.present_for_decision(other.approval_id, as_of=F.T0)
    with pytest.raises(ContractViolation):
        store.decide(other.approval_id, approver=F.APPROVER, decision=ReviewDecision.GRANT,
                     as_of=F.T1, authentication_reference=42)  # type: ignore[arg-type]
    store.close()


# --------------------------------------------------------------------------- #
# row 9: alteration is detected
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, before, after", [
    ("decided_by", F.APPROVER.approver_id, "someone-else"),
    ("authentication_reference", REFERENCE, "authn:sha256:" + "cd" * 32),
])
def test_altering_decided_by_or_the_reference_in_the_record_is_refused_on_read(
        tmp_path, field, before, after):
    path = F.sqlite_path(tmp_path)
    store = F.sqlite_store(tmp_path)
    record = _decided(store)
    store.close()
    raw = sqlite3.connect(path)
    changed = raw.execute(
        "UPDATE approvals SET record_json=replace(record_json, ?, ?) WHERE approval_id=?",
        (f'"{field}":"{before}"', f'"{field}":"{after}"', record.approval_id)).rowcount
    raw.commit()
    assert changed == 1
    assert after in raw.execute("SELECT record_json FROM approvals WHERE approval_id=?",
                                (record.approval_id,)).fetchone()[0]
    raw.close()
    reopened = SqliteApprovalWorkflowStore(path, F.directory())
    with pytest.raises(ArtifactIntegrityError):
        reopened.get_approval(record.approval_id)
    reopened.close()


def test_altering_the_reference_in_the_event_breaks_the_chain(tmp_path):
    path = F.sqlite_path(tmp_path)
    store = F.sqlite_store(tmp_path)
    _decided(store)
    assert store.verify_chain()
    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("UPDATE ledger_events SET detail_json=replace(detail_json, ?, ?)",
                    (REFERENCE, "authn:sha256:" + "cd" * 32))
    # Even a privileged writer that drops the guard leaves a detectable break.
    raw.execute("DROP TRIGGER ledger_events_no_update")
    raw.execute("UPDATE ledger_events SET detail_json=replace(detail_json, ?, ?)",
                (REFERENCE, "authn:sha256:" + "cd" * 32))
    raw.commit()
    raw.close()
    assert store.verify_chain() is False
    store.close()
