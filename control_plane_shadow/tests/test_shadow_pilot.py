"""Shadow-pilot integration tests (Phase 16). Run without live credentials; SHADOW/MOCK only.
Cover adapter mappings, source preservation, vocabulary, assertion/action separation, eligibility
invariant, fallback, TAP/ActionGate dispositions, indeterminate propagation, action suppression,
raw/governed access rules, version mismatch, partial degradation, telemetry/audit failure, trace
completeness, audit-chain integrity, no live calls, no real actions, data-flow guard, and
information-loss/provenance retention.
"""
import pytest

from control_plane_shadow import vocabulary as V
from control_plane_shadow import versioning as VER
from control_plane_shadow.adapters.action_gate_adapter import ActionGateAdapter
from control_plane_shadow.adapters.action_runtime_adapter import ActionRuntimeAdapter
from control_plane_shadow.adapters.execution_gate_adapter import ExecutionGateAdapter
from control_plane_shadow.adapters.model_policy_adapter import ModelPolicyAdapter
from control_plane_shadow.adapters.provider_runtime_adapter import ProviderRuntimeAdapter
from control_plane_shadow.adapters.tap_adapter import TAPAssertionAdapter
from control_plane_shadow.orchestrator import ShadowOrchestrator
from control_plane_shadow.traces.v1.dataset import all_traces, Trace


# --- vocabulary + mappings -------------------------------------------------

def test_no_forbidden_collapses():
    for src, canon in list(V.TAP_MAP.items()) + list(V.ACTION_MAP.items()):
        for bad_src, bad_dst in V.FORBIDDEN_COLLAPSES:
            assert not (src == bad_src and canon.value == bad_dst), (src, canon)

def test_exec_map_is_identity():
    assert all(k == v.value for k, v in V.EXEC_MAP.items())

def test_assertion_and_action_vocab_disjoint_where_required():
    # QUALIFY only in assertions; APPROVE/CONSTRAIN only in actions
    a = {d.value for d in V.AssertionDisposition}
    x = {d.value for d in V.ActionDisposition}
    assert "QUALIFY" in a and "QUALIFY" not in x
    assert "APPROVE" in x and "APPROVE" not in a
    assert "CONSTRAIN" in x and "CONSTRAIN" not in a

def test_provenance_keeps_source_term():
    p = V.provenance("TAP", "CONFLICTED", V.map_tap("CONFLICTED"))
    assert p["source_term"] == "CONFLICTED" and p["canonical"] == "ESCALATE"


# --- real adapters: mapping + source preservation + determinism ------------

def test_execution_gate_adapter_real_and_preserves_source():
    eg = ExecutionGateAdapter()
    env = {"request_id": "r", "trace_id": "t", "required_capabilities": [], "context_tokens": 1000}
    specs = [{"provider": "p", "model_id": "m_small_local", "family": "f"}]
    res, elig = eg.evaluate(specs, env, now=1000.0)
    assert res.source_output and res.canonical["eligible_set"] == ["m_small_local"]
    assert eg.health().determinism == "deterministic" and eg.health().live_call_risk is False

def test_model_policy_selection_within_eligible():
    mp = ModelPolicyAdapter()
    ids = list(mp.registry["models"])
    task = {"task_id": "t", "task_class": "reasoning", "required_caps": {"reasoning": 1.0},
            "input_tokens_k": 8, "business_priority": "balanced",
            "utility_weights": {"quality": 1.0, "cost": 0.45, "latency": 0.35},
            "acceptable_quality_threshold": 0.6, "hard_constraints": {}}
    elig = ids[:3]
    r = mp.select(task, elig, "eg1")
    assert r.canonical["selected_candidate"] in elig

def test_tap_adapter_real_dispositions_and_semantic_gap():
    t = TAPAssertionAdapter()
    seen = {t.govern(cid).canonical["assertion_disposition"] for cid in t.case_ids()}
    assert {"ALLOW", "QUALIFY", "ESCALATE", "REJECT"} <= seen
    r = t.govern("E4D01")
    assert any("SEMANTIC GAP" in l for l in r.information_loss)
    assert r.source_output["gov_status"]  # source preserved

def test_actiongate_adapter_real_dispositions():
    a = ActionGateAdapter()
    assert a.authorize("DB_DELETE").canonical["action_disposition"] == "DENY"
    assert a.authorize("DB_DELETE").canonical["hard_safety_block"] is True
    assert a.authorize("SECRET_READ").canonical["action_disposition"] == "APPROVE"
    assert a.authorize("DEPLOY").canonical["action_disposition"] == "INDETERMINATE"
    happy = a.authorize("KEY_ROTATE", with_approval=True, with_evidence=True)
    assert happy.canonical["action_disposition"] == "ALLOW"
    assert a.health().real_action_risk is False

def test_actiongate_indeterminate_not_deny():
    a = ActionGateAdapter()
    assert a.authorize("DEPLOY").canonical["action_disposition"] == "INDETERMINATE"  # not DENY

def test_adapters_are_deterministic():
    a = ActionGateAdapter()
    r1 = a.authorize("KEY_ROTATE", with_approval=True, with_evidence=True)
    r2 = a.authorize("KEY_ROTATE", with_approval=True, with_evidence=True)
    assert r1.canonical["action_hash"] == r2.canonical["action_hash"]


# --- no live calls / no real actions ---------------------------------------

def test_no_adapter_has_live_or_action_risk():
    for A in (ExecutionGateAdapter(), ModelPolicyAdapter(), TAPAssertionAdapter(),
              ActionGateAdapter(), ProviderRuntimeAdapter(), ActionRuntimeAdapter()):
        h = A.health()
        assert h.live_call_risk is False and h.real_action_risk is False, A.component

def test_action_runtime_never_executes_even_in_enforcement():
    ax = ActionRuntimeAdapter()
    r = ax.execute("KEY_ROTATE", mode="ENFORCEMENT")
    assert r.canonical["executed"] is False and r.canonical["execution_outcome"] == "NOT_ATTEMPTED"

def test_provider_no_live_call_and_error_normalized():
    p = ProviderRuntimeAdapter()
    assert p.health().live_call_risk is False
    fail = p.call("m1", outcome="FAILURE", raw_error="HTTP 500 secret-leak")
    assert fail.reason_codes == ["RUNTIME.PROVIDER_EXECUTION_FAILED"]
    assert "secret-leak" not in str(fail.canonical)  # raw not propagated


# --- orchestrator over the trace dataset -----------------------------------

@pytest.mark.parametrize("tr", all_traces(), ids=lambda t: t.trace_id)
def test_trace_matches_expected_terminal(tr):
    r = ShadowOrchestrator().run(tr)
    assert r.shadow_outcome == tr.expected_terminal, (tr.trace_class, r.reason_codes)
    assert r.real_action_executed is False

def test_all_traces_no_real_action_and_no_unsafe_transition():
    o = ShadowOrchestrator()
    for tr in all_traces():
        r = o.run(tr)
        assert r.real_action_executed is False
        assert r.unsafe_transitions == [], (tr.trace_id, r.unsafe_transitions)

def test_selection_eligibility_consistency_all_traces():
    o = ShadowOrchestrator()
    for tr in all_traces():
        r = o.run(tr)
        if r.selected is not None:
            eg = ExecutionGateAdapter()
            _, elig = eg.evaluate(tr.candidate_specs, tr.envelope, now=1_000_000.0)
            ids = [s["model_id"] for s, _ in elig]
            if ids:  # selected must be within eligible (or a fallback within eligible)
                assert r.selected in ids, (tr.trace_id, r.selected, ids)

def test_fallback_reenters_eligibility():
    tr = next(t for t in all_traces() if t.trace_id == "T08")
    r = ShadowOrchestrator().run(tr)
    assert r.shadow_outcome == "ASSERTION_DELIVERED"  # recovered via fallback

def test_assertion_reject_blocks_action():
    tr = next(t for t in all_traces() if t.trace_id == "T03")
    r = ShadowOrchestrator().run(tr)
    assert r.shadow_outcome == "ASSERTION_REJECTED" and r.action_disposition is None

def test_action_denied_never_executes():
    tr = next(t for t in all_traces() if t.trace_id == "T11")
    r = ShadowOrchestrator().run(tr)
    assert r.shadow_outcome == "ACTION_DENIED" and r.real_action_executed is False


# --- partial degradation ---------------------------------------------------

def test_tap_unavailable_fails_closed():
    tr = next(t for t in all_traces() if t.trace_id == "T18")
    assert ShadowOrchestrator().run(tr).shadow_outcome == "GOVERNANCE_UNAVAILABLE"

def test_actiongate_unavailable_fails_closed_for_action():
    tr = next(t for t in all_traces() if t.trace_id == "T19")
    assert ShadowOrchestrator().run(tr).shadow_outcome == "GOVERNANCE_UNAVAILABLE"

def test_telemetry_unavailable_degrades_not_blocks():
    tr = next(t for t in all_traces() if t.trace_id == "T20")
    assert ShadowOrchestrator().run(tr).shadow_outcome == "ASSERTION_DELIVERED"

def test_audit_failure_terminal():
    tr = next(t for t in all_traces() if t.trace_id == "T21")
    assert ShadowOrchestrator().run(tr).shadow_outcome == "AUDIT_FAILURE"


# --- version mismatch ------------------------------------------------------

def test_version_backward_and_forward():
    assert VER.check("envelope", "1").ok
    assert VER.check("envelope", "2").kind == "FORWARD_INCOMPATIBLE"
    assert VER.check("envelope", None).kind == "MISSING"

def test_registry_and_policy_mismatch_traces():
    o = ShadowOrchestrator()
    assert o.run(next(t for t in all_traces() if t.trace_id == "T16")).shadow_outcome == "REJECTED"
    assert o.run(next(t for t in all_traces() if t.trace_id == "T17")).shadow_outcome == "REJECTED"
    assert o.run(next(t for t in all_traces() if t.trace_id == "T25")).shadow_outcome == "REJECTED"

def test_data_flow_guard():
    tr = next(t for t in all_traces() if t.trace_id == "T24")
    r = ShadowOrchestrator().run(tr)
    assert r.shadow_outcome == "REJECTED" and "POLICY.DATA_FLOW_NOT_APPROVED" in r.reason_codes


# --- audit / trace completeness / determinism ------------------------------

def test_trace_completeness_and_audit_ok_for_nominal():
    o = ShadowOrchestrator()
    for tr in all_traces():
        if tr.audit_unavailable:
            continue
        r = o.run(tr)
        assert r.audit_ok and r.trace_complete, (tr.trace_id,)

def test_deterministic_replay_all_traces():
    for tr in all_traces():
        r1 = ShadowOrchestrator().run(tr)
        r2 = ShadowOrchestrator().run(tr)
        assert r1.shadow_outcome == r2.shadow_outcome and r1.selected == r2.selected

def test_information_loss_and_provenance_recorded():
    t = TAPAssertionAdapter().govern("E4D01")
    assert t.information_loss and t.provenance and t.source_version
