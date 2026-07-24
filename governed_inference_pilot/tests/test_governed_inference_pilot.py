"""Phase 25 test suite. Locks the pilot's headline claims as assertions. Deterministic; no live calls;
no external actions. Consumes prior components read-only; touches no prior artifact.
"""
from dataclasses import asdict

import pytest

from governed_inference_pilot import (schema, contracts, dispositions, reason_codes, audit, replay,
                                      dataset, orchestrator, baselines, fault_injection, evaluate,
                                      mvc_study, human_review, model_execution, evidence_binding,
                                      action_extraction)
from governed_inference_pilot.viewer import render

CASES = [asdict(c) for c in dataset.all_cases()]


# ---- schema / contracts -------------------------------------------------------------------------

def test_schema_versions():
    assert schema.SCHEMA_VERSION == "gip_request_v1"
    r = schema.GovernedRequest(request_id="r", user_prompt="p")
    assert r.execution_mode == "fixture" and r.timestamp == 0.0


def test_contract_fail_closed_on_missing_field():
    res = contracts.validate("request__execution_gate", {"request_id": "r"})
    assert not res.ok and res.fail_closed and "GIP.MISSING_FIELD" in res.reason_codes


def test_contract_unknown_vocab_fail_closed():
    res = contracts.validate("evidence_assurance__assertion_gate", {"evidence_state": "BOGUS"})
    assert not res.ok and "GIP.UNKNOWN_VOCAB" in res.reason_codes


def test_semantic_loss_detected():
    assert contracts.semantic_loss_check({"exceptions": ["x"]}, {"exceptions": []}, ["exceptions"])


# ---- dispositions -------------------------------------------------------------------------------

def test_action_block_outranks_assertion_allow():
    final, _ = dispositions.reconcile([("assertion_gate", "WOULD_ALLOW"),
                                       ("action_gate", "WOULD_BLOCK_ACTION")])
    assert final == "WOULD_BLOCK_ACTION"


def test_unknown_local_disposition_maps_indeterminate():
    assert dispositions.map_stage("assertion_gate", "NONSENSE") == "INDETERMINATE"


def test_reason_codes_not_rewritten():
    assert reason_codes.namespace("evidence_assurance", ["EA.STALE"]) == ["EA.STALE"]


# ---- audit / replay -----------------------------------------------------------------------------

def test_audit_complete_and_signature():
    t = orchestrator.run_case(CASES[0])
    assert t.audit_complete() and len(t.replay_signature) == 64


def test_replay_deterministic_on_all_cases():
    for c in CASES:
        t1 = orchestrator.run_case(c)
        t2 = orchestrator.run_case(c)
        assert replay.self_replay(t1).deterministic
        assert t1.replay_signature == t2.replay_signature, c["case_id"]


def test_replay_detects_disposition_drift():
    import copy
    t = orchestrator.run_case(CASES[0])
    c = copy.deepcopy(t)
    if c.events:
        c.events[0].disposition = "CHANGED"; c.events[0].shadow_outcome = "WOULD_ALLOW"
        c.finalize(c.final_shadow_disposition)
    assert not replay.compare(t, c, "exact").deterministic


def test_redacted_view_hides_internals():
    t = orchestrator.run_case(CASES[0])
    v = t.view(internal=False)
    assert all(e["source_repr"] == "<redacted>" for e in v["events"])


# ---- pipeline behavior --------------------------------------------------------------------------

def test_full_stack_zero_unsafe_escape():
    unsafe = sum(1 for c in CASES
                 if baselines.BASELINES["J_full"](c) in c["unacceptable_finals"])
    assert unsafe == 0


def test_no_governance_leaks():
    unsafe = sum(1 for c in CASES
                 if baselines.BASELINES["A_no_governance"](c) in c["unacceptable_finals"])
    assert unsafe > 100


def test_full_stack_no_false_block_on_clean():
    fb = sum(1 for c in CASES if c["partition"].startswith("CLEAN")
             and baselines.BASELINES["J_full"](c) not in ("WOULD_ALLOW", "WOULD_QUALIFY"))
    assert fb == 0


def test_execution_ineligible_unavailable():
    c = next(c for c in CASES if c["partition"] == "EXECUTION_INELIGIBLE")
    assert orchestrator.run_case(c).final_shadow_disposition == "EXECUTION_UNAVAILABLE"


def test_model_selection_conflict_unavailable():
    c = next(c for c in CASES if c["partition"] == "MODEL_SELECTION_CONFLICT")
    assert orchestrator.run_case(c).final_shadow_disposition == "EXECUTION_UNAVAILABLE"


def test_contract_failure_is_contract_error():
    c = next(c for c in CASES if c["partition"] == "CONTRACT_OR_METADATA_FAILURE")
    assert orchestrator.run_case(c).final_shadow_disposition == "CONTRACT_ERROR"


def test_action_policy_failure_blocks_action():
    c = next(c for c in CASES if c["partition"] == "ACTION_POLICY_FAILURE")
    assert orchestrator.run_case(c).final_shadow_disposition == "WOULD_BLOCK_ACTION"


def test_adversarial_composition_withheld():
    for c in CASES:
        if c["partition"] == "ADVERSARIAL_COMPOSITION":
            assert orchestrator.run_case(c).final_shadow_disposition not in ("WOULD_ALLOW", "WOULD_QUALIFY")


# ---- fault injection ----------------------------------------------------------------------------

def test_all_faults_fail_closed():
    clean = [c for c in CASES if c["partition"].startswith("CLEAN")]
    res = fault_injection.sweep(clean)
    assert all(s["unsafe_fallback"] == 0 for s in res.values())
    assert all(s["auditable_rate"] == 1.0 for s in res.values())


# ---- fixtures / extraction / binding ------------------------------------------------------------

def test_no_live_execution():
    r = model_execution.execute("m", "p", "out", {"provider": "a", "family": "L"})
    assert r.execution_occurred is False and r.mode == "fixture"


def test_action_not_inferred_from_advice():
    assert not action_extraction.extract("You should consider the policy.", None).found


def test_binder_flags_missing_provenance():
    b = evidence_binding.bind(["x is not approved unless certified."],
                              {"evidence_state": "VERIFIED", "provenance_present": False})
    assert "BIND.MISSING_PROVENANCE" in b.reason_codes


def test_no_external_action_field():
    """The envelope/trace never contains an executed-action result."""
    t = orchestrator.run_case(next(c for c in CASES if c["partition"] == "ACTION_POLICY_FAILURE"))
    assert not any("executed" in str(e.transformed_repr).lower() for e in t.events)


# ---- mvc / viewer -------------------------------------------------------------------------------

def test_evidence_assurance_mandatory():
    r = mvc_study.run()
    assert r["classification"]["evidence_assurance"] == "mandatory_core"


def test_viewer_renders():
    html = render.render_html(orchestrator.run_case(CASES[0]))
    assert "Final:" in html and "No governed action was performed" in html


def test_corpus_and_partitions():
    assert dataset.DATASET_VERSION == "gip_corpus_v1"
    assert len(CASES) == 384
    assert {c["partition"] for c in CASES} == set(dataset.PARTITIONS)
