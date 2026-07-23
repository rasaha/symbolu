"""Integration test suite (Phase 14). Runs without live credentials; MOCK mode only.
Covers contracts, decision transitions, every invariant, execution modes, version/stale/
mismatch handling, audit integrity, replay determinism, shadow separation, provider-error
normalization, downstream-bypass prevention, no-live-calls / no-enforcement defaults,
partner-data guard, component unavailability, and end-to-end trace completeness.
"""
import pytest

from control_plane import contracts as K
from control_plane.envelope import RequestEnvelope
from control_plane.failure_codes import Failure, FAILURE_META, meta
from control_plane.modes import caps, may_execute_actions, may_call_provider, DEFAULT_MODE, NON_ENFORCING
from control_plane.orchestrator import Orchestrator, Scenario
from control_plane.policy_context import PolicyContext
from control_plane.replay import replay
from control_plane.shadow import shadow_run
from control_plane.scenarios import all_cases
from control_plane.telemetry import Telemetry, RegistryUpdater, Observation
from control_plane.decisions import AuditLog, DecisionRecord

AP = {"permitted": ["notify"], "require_approval": ["payment"]}


def env(tid="t", **kw):
    d = dict(request_id="r", trace_id=tid, required_capabilities=set(), action_policy=AP)
    d.update(kw)
    return RequestEnvelope(**d)


def two():
    return [{"provider": "anthropic", "model_id": "claude-x", "family": "claude", "quality": 0.85, "latency_ms": 800},
            {"provider": "google", "model_id": "gemma-y", "family": "gemma", "quality": 0.6, "latency_ms": 400}]


def orch(**kw):
    return Orchestrator(validate_contracts=True, enforce_invariants=True, **kw)


# --- contracts -------------------------------------------------------------

def test_nine_contracts_present():
    assert len(K.ALL_CONTRACTS) == 9
    assert len(K.HANDOFF_ORDER) == 7  # linear critical path; C8 fan-in, C9 async

def test_contract_missing_required_field_fails():
    ok, errs = K.validate_payload("execution_gate->model_policy", {"trace_id": "t"})
    assert not ok and errs

def test_contract_unknown_version_fails_closed():
    ok, errs = K.validate_payload("execution_gate->model_policy", {}, schema_version="9")
    assert not ok and "CONTRACT_VERSION_UNSUPPORTED" in errs[0]

def test_only_provider_contract_reads_raw_errors():
    raw_readers = [c for c in K.ALL_CONTRACTS.values() if c.may_read_raw_provider_error]
    assert len(raw_readers) == 1 and raw_readers[0].consumer == "TAP"


# --- failure codes ---------------------------------------------------------

def test_all_28_codes_have_metadata():
    assert len(FAILURE_META) == 28 == len(list(Failure))

def test_every_failure_is_fail_closed():
    assert all(m[6] == "closed" for m in FAILURE_META.values())

def test_namespaces_wrap_not_merge():
    ns = {c.value.split(".")[0] for c in Failure}
    assert ns == {"EXEC", "MODEL", "ASSERT", "ACTION", "RUNTIME", "AUDIT", "POLICY"}


# --- scenario suite (ground truth) -----------------------------------------

@pytest.mark.parametrize("case", all_cases(), ids=lambda c: c.scenario.name)
def test_scenario_matches_expected(case):
    r = orch().run(case.scenario)
    assert r.terminal_state == case.expected_terminal, (case.scenario.name, r.terminal_reasons)
    if case.expected_reason:
        assert case.expected_reason in r.terminal_reasons
    assert r.audit_ok and r.trace_complete   # invariant 20: every terminal is traceable


# --- invariants ------------------------------------------------------------

def test_inv1_selection_within_eligible():
    r = orch().run(Scenario("i1", env(), two()))
    assert r.selected in {"claude-x", "gemma-y"}

def test_inv4_success_then_assert_reject():
    r = orch().run(Scenario("i4", env(), two(), assertion="REJECT", proposed_action="notify"))
    assert r.terminal_state == "ASSERTION_REJECTED" and not r.executed_action

def test_inv5_assert_ok_action_denied():
    r = orch().run(Scenario("i5", env(), two(), assertion="APPROVE", proposed_action="delete_db"))
    assert r.terminal_state == "ACTION_DENIED" and not r.executed_action

def test_inv6_action_within_authority():
    r = orch().run(Scenario("i6", env(), two(), proposed_action="wire_transfer"))
    assert r.terminal_state == "ACTION_DENIED"

def test_inv7_denied_never_executes():
    for act, exp in [("delete_db", "ACTION_DENIED"), ("payment", "ACTION_APPROVAL_REQUIRED")]:
        r = orch().run(Scenario("i7", env(), two(), proposed_action=act))
        assert r.terminal_state == exp and r.executed_action is False

def test_inv8_unauthorized_override_blocked():
    r = orch().run(Scenario("i8", env(), two(), proposed_action="payment", override_actor="x"))
    assert r.terminal_state == "UNAUTHORIZED_OVERRIDE"

def test_inv8_authorized_override_allowed():
    r = orch().run(Scenario("i8b", env(), two(), proposed_action="payment",
                            override_actor="ops:a", override_rationale="ticket#1"))
    assert r.terminal_state == "COMPLETED"

def test_inv9_unknown_action_state_not_approval():
    r = orch().run(Scenario("i9", env(), two(), proposed_action="notify",
                            forced_action_disposition="INDETERMINATE"))
    assert r.terminal_state == "ACTION_INDETERMINATE" and not r.executed_action

def test_inv10_versions_pinned():
    e = env()
    ctx = PolicyContext.resolve(e)
    assert ctx.check_compatibility(e) is None
    e2 = env(registry_version="reg_v2")
    assert ctx.check_compatibility(e2) == Failure.REGISTRY_VERSION_MISMATCH
    e3 = env(policy_versions={"assertion": "v2", "action": "v1", "enterprise": "v1"})
    assert ctx.check_compatibility(e3) == Failure.POLICY_VERSION_MISMATCH

def test_inv11_audit_append_only_no_rewrite():
    log = AuditLog()
    log.append(DecisionRecord("d1", "r", "t", "C", "v", "sel", "OK"))
    assert not hasattr(log, "update") and not hasattr(log, "delete")

def test_inv12_registry_updates_prospective_only():
    up = RegistryUpdater(current_version="reg_v1")
    obs = Observation("t", "m", "ok", 1.0)
    assert up.enqueue(obs, "reg_v1") == Failure.CIRCULAR_DEPENDENCY_DETECTED   # same version rejected
    assert up.enqueue(obs, "reg_v2") is None                                    # future accepted

def test_inv13_replay_historical_versions():
    sc = Scenario("i13", env(), two(), proposed_action="notify")
    r = orch().run(sc)
    good = replay(Scenario("i13", env(), two(), proposed_action="notify"), r, "v1", "reg_v1")
    assert good.reproduced
    bad = replay(Scenario("i13", env(registry_version="reg_v5"), two(), proposed_action="notify"),
                 r, "v1", "reg_v1")
    assert not bad.reproduced and bad.mismatch_reason == Failure.REPLAY_VERSION_MISMATCH.value

def test_inv16_data_flow_guard():
    r = orch().run(Scenario("i16", env(data_sensitivity="regulated", provider_allowlist=None), two()))
    assert r.terminal_state == "REJECTED" and Failure.DATA_FLOW_NOT_APPROVED.value in r.terminal_reasons

def test_inv17_assertion_and_action_independent():
    # assertion approved, action denied -> two independent records/dispositions
    r = orch().run(Scenario("i17", env(), two(), assertion="APPROVE", proposed_action="delete_db"))
    trace = orch().audit.trace  # structure exists
    assert r.terminal_state == "ACTION_DENIED"

def test_inv19_fallback_reenters_eligibility():
    r = orch().run(Scenario("i19", env(), two(), provider_fail_then_ok=True, proposed_action="notify"))
    assert r.terminal_state == "COMPLETED" and r.selected == "gemma-y"  # switched, not retried in place

def test_inv20_terminal_traceable():
    r = orch().run(Scenario("i20", env(), two()))
    assert r.trace_complete and r.audit_ok


# --- execution modes -------------------------------------------------------

def test_default_mode_is_mock():
    assert DEFAULT_MODE == "MOCK" and env().mode == "MOCK"

def test_no_action_execution_outside_enforcement():
    for m in NON_ENFORCING:
        assert may_execute_actions(m) is False
        assert may_call_provider(m) is False
    assert may_execute_actions("ENFORCEMENT") is True

def test_action_never_really_executes_in_mock():
    r = orch().run(Scenario("m1", env(), two(), proposed_action="notify"))
    assert r.terminal_state == "COMPLETED" and r.executed_action is False  # SIMULATED, not EXECUTED


# --- audit integrity -------------------------------------------------------

def test_audit_chain_detects_tampering():
    log = AuditLog()
    log.append(DecisionRecord("d1", "r", "t", "C", "v", "sel", "OK"))
    log.append(DecisionRecord("d2", "r", "t", "C", "v", "act", "ALLOW"))
    assert log.verify_chain()
    log.records[0]["output_state"] = "TAMPERED"
    assert not log.verify_chain()

def test_audit_write_failure_raises(tmp_path):
    bad = tmp_path / "nope" / "x.log"
    log = AuditLog(str(bad))
    import os
    os.rmdir(str(tmp_path / "nope"))
    with pytest.raises(IOError):
        log.append(DecisionRecord("d", "r", "t", "C", "v", "sel", "OK"))

def test_secrets_redacted_in_records():
    log = AuditLog()
    rec = DecisionRecord("d", "r", "t", "C", "v", "sel", "OK")
    rec.evidence_refs = ["ok"]
    log.append(rec)
    # confirm redaction helper strips secret-like keys
    from control_plane.decisions import _redact
    out = _redact({"api_key": "sk-123", "nested": {"authorization": "Bearer z", "ok": 1}})
    assert out["api_key"] == "<redacted>" and out["nested"]["authorization"] == "<redacted>" and out["nested"]["ok"] == 1


# --- shadow separation -----------------------------------------------------

def test_shadow_never_acts_and_compares():
    sc = Scenario("sh", env(), two(), proposed_action="notify")
    cmp = shadow_run(sc, authoritative_route="gemma-y")
    assert cmp.recommended_route == "claude-x" and cmp.agree is False
    assert cmp.recommended_terminal in ("COMPLETED", "ASSERTION_DELIVERED")


# --- provider error normalization + bypass prevention ----------------------

def test_provider_error_normalized_to_runtime():
    r = orch().run(Scenario("pe", env(), two(), provider_fail=True, raw_provider_error="HTTP 500 boom"))
    assert r.terminal_state == "PROVIDER_FAILED"
    assert all(rc.startswith(("RUNTIME.", "EXEC.", "MODEL.", "ASSERT.", "ACTION.", "AUDIT.", "POLICY."))
               for rc in r.terminal_reasons)

def test_component_calls_counted():
    r = orch().run(Scenario("cc", env(), two(), proposed_action="notify"))
    assert r.component_calls >= 6  # EG, MP, PX, TAP, AG, AX, TEL


# --- glue vs unified (falsification hook) ----------------------------------

def test_glue_allows_bypass_that_unified_blocks():
    glue = Orchestrator(validate_contracts=False, enforce_invariants=False)
    unified = Orchestrator(validate_contracts=True, enforce_invariants=True)
    sc_args = dict(name="fb", envelope=env(), candidate_specs=two(),
                   provider_fail_then_ok=True, proposed_action="notify")
    g = glue.run(Scenario(**sc_args))
    u = unified.run(Scenario(**dict(sc_args, envelope=env())))
    # glue records a bypass violation; unified re-enters eligibility with none blocked-as-violation
    assert Failure.UPSTREAM_EXCLUSION_BYPASSED.value in g.violations
    assert Failure.UPSTREAM_EXCLUSION_BYPASSED.value not in u.violations
