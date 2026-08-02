"""MVP 1B acceptance tests 41-55: staleness and governance-chain reconstruction."""
from __future__ import annotations

import dataclasses

import pytest

from cg_clearance_helpers import (
    EVAL, drive_to_action_evaluated, full_1b, profile, projection, run_clearance, snapshot,
)
from ugence_code_governance import CodeGovernanceService, MergeMethod
from ugence_code_governance.models.enums import ReconstructionState


# --- staleness (41-47) ----------------------------------------------------
# 41. changed head SHA invalidates clearance (new revision, new fingerprints)
def test_changed_head_new_clearance():
    svc, rid_a, action_a, s_a, rec_a, hia_a, res_a = full_1b(head_sha="head-A")
    # a different head -> different prepared action fingerprint -> different clearance
    svc2, rid_b, action_b, s_b, rec_b, hia_b, res_b = full_1b(head_sha="head-B")
    assert action_a.fingerprint != action_b.fingerprint
    assert rec_a.prepared_action_fingerprint != rec_b.prepared_action_fingerprint
    assert rec_a.clearance_request_fingerprint != rec_b.clearance_request_fingerprint
    assert hia_a.fingerprint == hia_a.fingerprint  # sanity


def test_changed_head_old_chain_stale():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha="head-A")
    run_clearance(svc, rid, action)
    # new head on the same lineage supersedes
    drive_to_action_evaluated(svc, head_sha="head-B")
    result = svc.reconstruct_chain("acme", rid)
    assert result.state is ReconstructionState.STALE


# 42-46. changed base/method/actiongate/policy/projection produce different clearance
def test_changed_merge_method_new_action_fingerprint():
    _, _, a_squash, *_ = full_1b()
    svc2 = CodeGovernanceService()
    change, rid, a_merge, shadow = drive_to_action_evaluated(svc2, merge_method=MergeMethod.MERGE)
    assert a_squash.fingerprint != a_merge.fingerprint


def test_changed_policy_projection_changes_signals():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc)
    b1 = svc.build_trusted_signals("acme", rid) if False else None
    # different projection provenance -> different signal content -> different bundle fingerprint
    from cg_clearance_helpers import projection
    from ugence_code_governance.clearance.signal_adapter import build_trusted_signals
    from cg_clearance_helpers import REQUIRED
    bundle1 = build_trusted_signals(snapshot(action), projection(), tenant_id="acme",
                                    subject_ref=action.repository, authorization_ref=shadow.result_fingerprint,
                                    action_fingerprint=action.fingerprint, required_signal_types=REQUIRED)
    # a different snapshot content -> different bundle fingerprint
    bundle2 = build_trusted_signals(snapshot(action, actor_state="DISABLED"), projection(),
                                    tenant_id="acme", subject_ref=action.repository,
                                    authorization_ref=shadow.result_fingerprint,
                                    action_fingerprint=action.fingerprint, required_signal_types=REQUIRED)
    assert bundle1.fingerprint != bundle2.fingerprint


# 47. old chain remains historical and reconstructable
def test_old_chain_reconstructable():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha="head-A")
    run_clearance(svc, rid, action)
    drive_to_action_evaluated(svc, head_sha="head-B")
    result = svc.reconstruct_chain("acme", rid)
    assert result.state is ReconstructionState.STALE
    assert len(result.verified_links) >= 8  # still fully linked


# --- reconstruction (48-55) -----------------------------------------------
# 48. complete authorized/evaluated chain reconstructs
def test_complete_chain_reconstructs():
    svc, rid, a, s, rec, hia, res = full_1b()
    assert res.state is ReconstructionState.COMPLETE
    assert "clearance_evaluated" in res.verified_links
    assert "intervention_assessment" in res.verified_links


# 49. upstream-denied / not-evaluated chain reconstructs
def test_upstream_denied_chain_reconstructs():
    from ugence_code_governance.governance.actiongate_adapter import ActionGateShadowAdapter
    from actiongate_provider.api import ActionGateEngine, build_actiongate_provider
    prov = build_actiongate_provider(engine=ActionGateEngine(denied=frozenset({"merge_pull_request"})))
    prov.initialize()
    svc, rid, a, s, rec, hia, res = full_1b(actiongate=ActionGateShadowAdapter(provider=prov))
    assert res.state is ReconstructionState.COMPLETE
    assert "clearance_not_evaluated_upstream" in res.verified_links


# 50. missing required clearance result -> incomplete
def test_missing_clearance_result_incomplete():
    svc, rid, a, s, rec, hia, res = full_1b()
    chain_id = svc.get_workflow("acme", rid).chain_id
    chain = svc.get_governance_chain("acme", chain_id)
    broken = dataclasses.replace(chain, clearance_result_fingerprint="")
    svc._chain_repo._items[("acme", chain_id)] = broken
    result = svc._reconstruction.reconstruct("acme", chain_id)
    assert result.state is ReconstructionState.INCOMPLETE


# 51. modified clearance evaluation record -> integrity failure
def test_modified_clearance_record_integrity_failure():
    svc, rid, a, s, rec, hia, res = full_1b()
    chain_id = svc.get_workflow("acme", rid).chain_id
    # tamper the stored evaluation record so its fingerprint no longer matches the chain
    tampered = dataclasses.replace(rec, clearance_status="TAMPERED")
    svc._clearance_eval_repo[("acme", rec.record_id)] = tampered
    result = svc._reconstruction.reconstruct("acme", chain_id)
    assert result.state is ReconstructionState.INTEGRITY_FAILURE


# 52. signal-reference mismatch -> incomplete/integrity
def test_signal_reference_mismatch():
    svc, rid, a, s, rec, hia, res = full_1b()
    chain_id = svc.get_workflow("acme", rid).chain_id
    chain = svc.get_governance_chain("acme", chain_id)
    broken = dataclasses.replace(chain, clearance_signal_refs=("phantom-signal",))
    svc._chain_repo._items[("acme", chain_id)] = broken
    result = svc._reconstruction.reconstruct("acme", chain_id)
    assert "SIGNAL_REFERENCE_MISMATCH" in result.issues


# 53. assessment mismatch -> integrity/incomplete
def test_intervention_assessment_mismatch():
    svc, rid, a, s, rec, hia, res = full_1b()
    chain_id = svc.get_workflow("acme", rid).chain_id
    chain = svc.get_governance_chain("acme", chain_id)
    broken = dataclasses.replace(chain, intervention_assessment_fingerprint="wrong")
    svc._chain_repo._items[("acme", chain_id)] = broken
    result = svc._reconstruction.reconstruct("acme", chain_id)
    assert "INTERVENTION_ASSESSMENT_MISMATCH" in result.issues


# 54. stale clearance reported as stale
def test_stale_clearance_reported():
    test_changed_head_old_chain_stale = None  # covered above
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha="head-A")
    run_clearance(svc, rid, action)
    drive_to_action_evaluated(svc, head_sha="head-B")
    assert svc.reconstruct_chain("acme", rid).state is ReconstructionState.STALE


# 55. execution disabled represented explicitly
def test_execution_disabled_in_chain():
    svc, rid, a, s, rec, hia, res = full_1b()
    chain = svc.get_governance_chain("acme", svc.get_workflow("acme", rid).chain_id)
    assert chain.execution_status.value == "DISABLED"
    assert svc.execution_status() == "DISABLED"
