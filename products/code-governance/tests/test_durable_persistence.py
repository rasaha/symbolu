"""MVP 1C acceptance tests — durable shadow persistence, restart-safe recovery,
integrity-verified reconstruction, and offline-verifiable audit bundles.

Boundaries under test: append-only immutability, atomic stage transactions with
rollback, hash-linked record/event integrity, tenant isolation, data
minimization, execution-stays-disabled, and backward compatibility with the
in-memory service.
"""
from __future__ import annotations

import sqlite3

import pytest
from cg_durable_helpers import (
    drive_full_1b_durable,
    drive_partial,
    durable_service,
    temp_db_path,
)
from cg_helpers import T0

from ugence_code_governance import (
    CodeGovernanceService,
    PersistenceMode,
    RecoveryStatus,
    STORE_CLASSIFICATION,
    STORE_SCHEMA_VERSION,
)
from ugence_code_governance.persistence import (
    DurableShadowStore,
    DurableStoreConfig,
    RecordType,
    open_durable_store,
    reconstruct_from_store,
    recover_workflow,
)
from ugence_code_governance.persistence.durable_reconstruction import (
    DurableReconstructionState,
)
from ugence_code_governance.persistence.envelope import RecordEnvelope, WorkflowEventRecord
from ugence_code_governance.persistence.errors import (
    EventChainError,
    InjectedFailure,
    IntegrityFailure,
    ProhibitedFieldError,
    RecordCollisionError,
    SchemaIncompatibleError,
)
from ugence_code_governance.persistence.schema import GENESIS, WorkflowEventType
from ugence_code_governance.persistence.serialization import serialize


# --- fixtures / low-level builders -----------------------------------------
def _env(store, record_id="r1", record_type=RecordType.EVIDENCE_RECORD, tenant="acme",
         payload=None, prev=None):
    return RecordEnvelope.build(
        record_id=record_id, record_type=record_type.value, tenant_id=tenant,
        workflow_id="wf", workflow_revision_id="rev", created_at=T0,
        payload=payload or {"k": "v"}, previous_record_fingerprint=prev)


def _event(store, tenant="acme", to_state="S1", event_id="rev:S1", prev=GENESIS, records=()):
    return WorkflowEventRecord.build(
        event_id=event_id, tenant_id=tenant, workflow_id="wf", workflow_revision_id="rev",
        previous_event_fingerprint=prev, from_state="INIT", to_state=to_state,
        event_type=WorkflowEventType.STAGE_COMMITTED.value,
        referenced_record_ids=records, occurred_at=T0)


# --- 1. store + schema ------------------------------------------------------
def test_store_opens_with_expected_meta():
    store = open_durable_store()
    meta = store.store_meta()
    assert meta["schema_version"] == STORE_SCHEMA_VERSION
    assert meta["classification"] == STORE_CLASSIFICATION
    hc = store.health_check()
    assert hc["ok"] and hc["record_count"] == 0
    store.close()


def test_schema_incompatible_store_rejected_on_reopen():
    path = temp_db_path()
    open_durable_store(path).close()
    conn = sqlite3.connect(path)
    conn.execute("UPDATE store_meta SET value='code_governance.shadow_store.v999' "
                 "WHERE key='schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(SchemaIncompatibleError):
        open_durable_store(path)


def test_store_classification_is_reference_not_enforcement():
    assert STORE_CLASSIFICATION == "DURABLE_SHADOW_REFERENCE"
    assert DurableShadowStore.classification == "DURABLE_SHADOW_REFERENCE"


# --- 2. immutable, append-only records --------------------------------------
def test_records_table_is_append_only():
    store = open_durable_store()
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store)], event=_event(store, records=("r1",)),
                       current_state="S1")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("UPDATE records SET record_type='X'")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("DELETE FROM records")
    store.close()


def test_events_table_is_append_only():
    store = open_durable_store()
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store)], event=_event(store, records=("r1",)),
                       current_state="S1")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("UPDATE events SET to_state='X'")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("DELETE FROM events")
    store.close()


def test_put_if_absent_is_idempotent_for_identical_content():
    store = open_durable_store()
    env = _env(store)
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[env], event=_event(store, records=("r1",)), current_state="S1")
    # Re-commit the identical record + identical event: idempotent, no error.
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[env], event=_event(store, records=("r1",)), current_state="S1")
    assert store.health_check()["record_count"] == 1
    store.close()


def test_put_if_absent_collision_on_differing_content():
    store = open_durable_store()
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store, payload={"k": "v1"})],
                       event=_event(store, records=("r1",)), current_state="S1")
    with pytest.raises(RecordCollisionError):
        store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                           records=[_env(store, payload={"k": "v2"})],
                           event=_event(store, event_id="rev:S2", to_state="S2",
                                        records=("r1",)), current_state="S2")
    store.close()


# --- 3. atomic transactions + failure injection -----------------------------
@pytest.mark.parametrize("boundary", ["after_records", "after_event", "before_commit"])
def test_injected_failure_rolls_back_entire_stage(boundary):
    store = open_durable_store()
    store._inject_at = boundary
    with pytest.raises(InjectedFailure):
        store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                           records=[_env(store)], event=_event(store, records=("r1",)),
                           current_state="S1")
    # Nothing from the failed stage is visible.
    hc = store.health_check()
    assert hc["record_count"] == 0 and hc["event_count"] == 0
    assert store.get_index("acme", "rev") is None
    store.close()


def test_stage_commit_updates_index_atomically():
    store = open_durable_store()
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store)], event=_event(store, records=("r1",)),
                       current_state="S1", chain_id="c1")
    idx = store.get_index("acme", "rev")
    assert idx["current_state"] == "S1" and idx["chain_id"] == "c1"
    store.close()


# --- 4. hash-linked workflow-event journal ----------------------------------
def test_event_chain_links_from_genesis():
    store = open_durable_store()
    e1 = _event(store, event_id="rev:S1", to_state="S1", prev=GENESIS, records=("r1",))
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store, record_id="r1")], event=e1, current_state="S1")
    e2 = _event(store, event_id="rev:S2", to_state="S2",
                prev=e1.event_fingerprint, records=("r2",))
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store, record_id="r2")], event=e2, current_state="S2")
    store.verify_event_chain("acme", "wf")  # must not raise
    assert store.last_event_fingerprint("acme", "wf") == e2.event_fingerprint
    store.close()


def test_broken_previous_linkage_is_rejected():
    store = open_durable_store()
    store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                       records=[_env(store, record_id="r1")],
                       event=_event(store, records=("r1",)), current_state="S1")
    # A second event that does not link to the last event fingerprint.
    bad = _event(store, event_id="rev:S2", to_state="S2", prev="cg-shadow:wrong",
                 records=("r2",))
    with pytest.raises(EventChainError):
        store.commit_stage(tenant_id="acme", workflow_id="wf", revision_id="rev",
                           records=[_env(store, record_id="r2")], event=bad, current_state="S2")
    store.close()


# --- 5. restart-safe recovery ----------------------------------------------
def test_recovery_complete_after_full_run():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    rec = svc.resume_workflow("acme", rid)
    assert rec.status is RecoveryStatus.RECOVERED_COMPLETE
    assert rec.last_committed_state == "SHADOW_COMPLETE"
    assert rec.execution_status == "DISABLED"
    assert not rec.requires_explicit_action
    svc.close()


def test_recovery_pending_for_partial_run_survives_restart():
    path = temp_db_path()
    svc = durable_service(path)
    _, rid = drive_partial(svc, stop="claims")
    svc.close()
    # New service instance == process restart.
    svc2 = durable_service(path)
    rec = svc2.resume_workflow("acme", rid)
    assert rec.status is RecoveryStatus.RECOVERED_PENDING
    assert rec.last_committed_state == "CLAIMS_EVALUATED"
    assert rec.requires_explicit_action
    assert rec.record_count > 0 and rec.event_count > 0
    svc2.close()


def test_recovery_stale_when_head_superseded():
    svc = durable_service()
    change, rid = drive_partial(svc, stop="claims")
    rec = svc.resume_workflow("acme", rid, current_identity={
        "head_sha": "a-newer-head", "base_sha": change.base_sha,
        "repository": change.repository})
    assert rec.status is RecoveryStatus.RECOVERED_STALE and rec.stale
    svc.close()


def test_recovery_reference_missing_for_unknown_revision():
    svc = durable_service()
    rec = svc.resume_workflow("acme", "does-not-exist")
    assert rec.status is RecoveryStatus.REFERENCE_MISSING
    svc.close()


def test_recovery_never_enables_execution():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    rec = svc.resume_workflow("acme", rid)
    assert rec.execution_status == "DISABLED"
    assert svc.execution_status() == "DISABLED"
    svc.close()


# --- 6. tenant isolation ----------------------------------------------------
def test_cross_tenant_read_returns_nothing():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    store = svc.durable_store
    assert store.get_index("acme", rid) is not None
    assert store.get_index("intruder", rid) is None
    assert store.list_for_revision("intruder", rid) == ()
    svc.close()


def test_reconstruction_isolated_by_tenant():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    other = reconstruct_from_store(svc.durable_store, "intruder", rid)
    assert other.state is DurableReconstructionState.INCOMPLETE
    svc.close()


# --- 7. integrity-verified reconstruction -----------------------------------
def test_reconstruction_complete_with_all_links():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    result = svc.reconstruct_chain_from_store("acme", rid)
    assert result.state is DurableReconstructionState.COMPLETE
    assert result.execution_status == "DISABLED"
    assert "execution_disabled" in result.verified_links
    assert "event_chain" in result.verified_links
    svc.close()


def test_reconstruction_detects_tampered_record():
    path = temp_db_path()
    svc = durable_service(path)
    change, rid, *_ = drive_full_1b_durable(svc)
    wid = svc.get_workflow("acme", rid).workflow_id
    svc.close()
    # Attacker with raw DB access drops the guard trigger and mutates a payload.
    conn = sqlite3.connect(path)
    conn.execute("DROP TRIGGER records_no_update")
    conn.execute("UPDATE records SET canonical_payload='{\"tampered\":true}' "
                 "WHERE record_type='CLAIM_MANIFEST'")
    conn.commit()
    conn.close()
    store = open_durable_store(path)
    with pytest.raises(IntegrityFailure):
        store.verify_records("acme", wid)
    result = reconstruct_from_store(store, "acme", rid)
    assert result.state is DurableReconstructionState.INTEGRITY_FAILURE
    store.close()


def test_reconstruction_stale_against_newer_head():
    svc = durable_service()
    change, rid, *_ = drive_full_1b_durable(svc)
    result = svc.reconstruct_chain_from_store("acme", rid, current_head_sha="different-head")
    assert result.state is DurableReconstructionState.STALE
    svc.close()


# --- 8. offline-verifiable audit bundle -------------------------------------
def test_audit_bundle_exports_and_verifies_offline():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    bundle = svc.export_governance_audit_bundle("acme", rid)
    assert bundle["execution_status"] == "DISABLED"
    assert bundle["manifest"]["record_count"] > 0
    verification = CodeGovernanceService.verify_governance_audit_bundle(bundle)
    assert verification.ok, verification.issues
    svc.close()


def test_audit_bundle_export_is_deterministic():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    b1 = svc.export_governance_audit_bundle("acme", rid)
    b2 = svc.export_governance_audit_bundle("acme", rid)
    assert b1["bundle_fingerprint"] == b2["bundle_fingerprint"]
    svc.close()


def test_audit_bundle_tamper_is_detected_offline():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    bundle = svc.export_governance_audit_bundle("acme", rid)
    # Mutate a stored payload after export; fingerprints must no longer verify.
    bundle["records"][0]["canonical_payload"] = {"tampered": True}
    verification = CodeGovernanceService.verify_governance_audit_bundle(bundle)
    assert not verification.ok
    svc.close()


def test_audit_bundle_rejects_unknown_version():
    verification = CodeGovernanceService.verify_governance_audit_bundle(
        {"manifest": {"bundle_version": "nope"}})
    assert not verification.ok


# --- 9. data minimization ---------------------------------------------------
@pytest.mark.parametrize("key", ["access_token", "api_key", "webhook_secret",
                                 "password", "ssn", "home_address"])
def test_serialize_rejects_prohibited_fields(key):
    with pytest.raises(ProhibitedFieldError):
        serialize({key: "x"})


def test_serialize_rejects_naive_datetime():
    import datetime as _dt
    with pytest.raises(ProhibitedFieldError):
        serialize({"when": _dt.datetime(2026, 1, 1)})


def test_durable_payloads_contain_no_prohibited_fields():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    banned = ("token", "secret", "password", "credential", "webhook")
    for env in svc.durable_store.list_for_revision("acme", rid):
        for key in env.canonical_payload:
            assert not any(b in key.lower() for b in banned), key
    svc.close()


# --- 10. idempotency / re-run safety ----------------------------------------
def test_reingesting_same_event_is_idempotent():
    from cg_helpers import make_payload
    svc = durable_service()
    p = make_payload(head_sha="hs-x")
    c1 = svc.ingest_change_event(p, tenant_id="acme", captured_at=T0, delivery_id="d1")
    before = svc.durable_store.health_check()["record_count"]
    c2 = svc.ingest_change_event(p, tenant_id="acme", captured_at=T0, delivery_id="d1")
    after = svc.durable_store.health_check()["record_count"]
    assert c1.fingerprint == c2.fingerprint and before == after
    svc.close()


# --- 11. execution stays disabled / boundaries ------------------------------
def test_durable_mode_keeps_execution_disabled():
    svc = durable_service()
    assert svc.execution_status() == "DISABLED"
    assert not hasattr(svc, "merge") and not hasattr(svc, "execute")
    svc.close()


def test_governance_chain_record_carries_execution_disabled_marker():
    svc = durable_service()
    _, rid, *_ = drive_full_1b_durable(svc)
    chain = next(e for e in svc.durable_store.list_for_revision("acme", rid)
                 if e.record_type == RecordType.GOVERNANCE_CHAIN.value)
    assert chain.canonical_payload["execution_status"] == "DISABLED"
    svc.close()


# --- 12. backward compatibility ---------------------------------------------
def test_in_memory_mode_has_no_durable_store():
    svc = CodeGovernanceService()
    assert svc.persistence_mode is PersistenceMode.IN_MEMORY_SHADOW
    assert svc.durable_store is None
    svc.close()  # safe no-op


def test_durable_ops_error_in_memory_mode():
    from ugence_code_governance.errors import RecordNotFoundError
    svc = CodeGovernanceService()
    with pytest.raises(RecordNotFoundError):
        svc.resume_workflow("acme", "rev")
    svc.close()


# --- 13. determinism of content-addressed fingerprints ----------------------
def test_record_and_event_fingerprints_are_content_addressed():
    s1 = DurableShadowStore(DurableStoreConfig(path=":memory:"))
    s2 = DurableShadowStore(DurableStoreConfig(path=":memory:"))
    e1 = _env(s1, payload={"a": 1, "b": [2, 3]})
    e2 = _env(s2, payload={"b": [2, 3], "a": 1})  # different key order, same content
    assert e1.payload_fingerprint == e2.payload_fingerprint
    assert e1.envelope_fingerprint == e2.envelope_fingerprint
    s1.close()
    s2.close()
