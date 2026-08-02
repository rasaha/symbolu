"""Acceptance tests 32-39: governance-chain reconstruction + replay determinism."""
from __future__ import annotations

import dataclasses

import pytest

from cg_helpers import (
    LOW_CLAIMS,
    T0,
    claim_inputs_for,
    drive_to_shadow_complete,
    make_evidence,
    make_payload,
    revision_of,
)
from ugence_code_governance import CodeGovernanceService, MergeMethod, RiskTier
from ugence_code_governance.models.enums import (
    ActionClearanceStatus,
    ExecutionStatus,
    ReconstructionState,
)


def _change(service, **kw):
    return service.ingest_change_event(make_payload(**kw), tenant_id="acme",
                                       captured_at=T0, delivery_id=kw.get("head_sha", "d"))


# 32. complete chain reconstructs successfully
def test_complete_chain_reconstructs(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    result = service.reconstruct_chain("acme", rid)
    assert result.state is ReconstructionState.COMPLETE
    assert result.is_complete


# 33. missing evidence ref -> incomplete
def test_missing_evidence_ref_incomplete(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain_id = service.get_workflow("acme", rid).chain_id
    chain = service.get_governance_chain("acme", chain_id)
    # corrupt the chain to reference a non-existent evidence id
    broken = dataclasses.replace(chain, evidence_refs=chain.evidence_refs + ("missing-evidence",))
    service._chain_repo._items[("acme", chain_id)] = broken  # inject for test
    result = service._reconstruction.reconstruct("acme", chain_id)
    assert result.state is ReconstructionState.INCOMPLETE


# 34. modified record -> integrity failure
def test_modified_record_integrity_failure(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain_id = service.get_workflow("acme", rid).chain_id
    chain = service.get_governance_chain("acme", chain_id)
    # tamper an evidence record's payload without updating its digest
    eid = chain.evidence_refs[0]
    ev = service._evidence_repo.get("acme", eid)
    tampered = dataclasses.replace(ev, normalized_payload={"result": "TAMPERED"})
    service._evidence_repo._items[("acme", eid)] = tampered
    result = service._reconstruction.reconstruct("acme", chain_id)
    assert result.state is ReconstructionState.INTEGRITY_FAILURE


def test_manifest_fingerprint_mismatch_integrity_failure(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain_id = service.get_workflow("acme", rid).chain_id
    chain = service.get_governance_chain("acme", chain_id)
    broken = dataclasses.replace(chain, claim_manifest_fingerprint="not-the-real-fingerprint")
    service._chain_repo._items[("acme", chain_id)] = broken
    result = service._reconstruction.reconstruct("acme", chain_id)
    assert result.state is ReconstructionState.INTEGRITY_FAILURE


# 35. tenant mismatch -> fail closed
def test_tenant_mismatch_fails_closed(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain_id = service.get_workflow("acme", rid).chain_id
    # reconstruct under the wrong tenant
    result = service._reconstruction.reconstruct("globex", chain_id)
    assert result.state in (ReconstructionState.INCOMPLETE, ReconstructionState.TENANT_MISMATCH)
    assert not result.is_complete


# 36. old-head chain remains historical but stale
def test_old_head_chain_is_stale(service: CodeGovernanceService):
    change_a = _change(service, head_sha="head-A")
    rid_a = drive_to_shadow_complete(service, change_a)
    # new head supersedes
    _change(service, head_sha="head-B")
    result = service.reconstruct_chain("acme", rid_a)
    assert result.state is ReconstructionState.STALE
    # but the chain is still fully reconstructable (all links verified)
    assert len(result.verified_links) >= 8


# 37. deterministic replay preserves fingerprints
def test_deterministic_replay_preserves_fingerprints():
    def run():
        svc = CodeGovernanceService()
        change = svc.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
        rid = drive_to_shadow_complete(svc, change)
        return svc.get_workflow("acme", rid)
    a, b = run(), run()
    assert a.change_fingerprint == b.change_fingerprint
    assert a.claim_manifest_fingerprint == b.claim_manifest_fingerprint
    assert a.tap_request_fingerprints == b.tap_request_fingerprints
    assert a.tap_result_fingerprints == b.tap_result_fingerprints
    assert a.prepared_action_fingerprint == b.prepared_action_fingerprint
    assert a.action_request_fingerprint == b.action_request_fingerprint
    assert a.action_result_fingerprint == b.action_result_fingerprint
    assert a.state == b.state


# 38. Action Clearance is explicitly not evaluated
def test_action_clearance_not_evaluated(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain = service.get_governance_chain("acme", service.get_workflow("acme", rid).chain_id)
    assert chain.action_clearance_status is ActionClearanceStatus.NOT_EVALUATED
    assert chain.action_clearance_status.value == "ACTION_CLEARANCE_NOT_EVALUATED"


# 39. execution is explicitly disabled
def test_execution_explicitly_disabled(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    chain = service.get_governance_chain("acme", service.get_workflow("acme", rid).chain_id)
    assert chain.execution_status is ExecutionStatus.DISABLED
    assert service.execution_status() == "DISABLED"
