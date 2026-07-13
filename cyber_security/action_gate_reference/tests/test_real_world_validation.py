"""Regression test for the real-world validation harness.

Asserts that, run against the REAL gate/token/gateway, every injected attack is detected and
every happy path commits — with the expected error code at the expected detection point.
"""

from __future__ import annotations

import pathlib
import sys

_RWV = pathlib.Path(__file__).resolve().parents[1] / "real_world_validation"
if str(_RWV) not in sys.path:
    sys.path.insert(0, str(_RWV))

import real_world_validation as RWV   # noqa: E402

RESULT = RWV.run()
BY = {(r["workflow"], r["scenario"]): r for r in RESULT["records"]}


def test_five_workflows_and_happy_paths():
    assert RESULT["summary"]["n_workflows"] == 5
    assert RESULT["summary"]["all_happy_paths_ok"] is True


def test_every_attack_detected():
    attacks = [r for r in RESULT["records"] if r["kind"] == "attack"]
    assert attacks and all(r["detected"] for r in attacks)
    assert RESULT["summary"]["all_attacks_detected"] is True


def test_no_attack_reached_completed_execution():
    # a detected attack never yields a COMPLETED execution
    for r in RESULT["records"]:
        if r["kind"] == "attack":
            assert "COMPLETED" not in str(r["observed"])
            assert r["observed"] != "ALLOWED"


def test_expected_detection_codes_and_points():
    expect = {
        ("github_coding_agent", "replay_duplicate_execution"): ("COMMIT", "E_NONCE_REPLAY"),
        ("github_coding_agent", "target_substitution"): ("COMMIT", "E_ACTION_HASH_MISMATCH"),
        ("kubernetes_deployment", "approval_reuse_cross_action"): ("DECISION", "DENY"),
        ("kubernetes_deployment", "stale_state_at_decision"): ("DECISION", "REQUEST_MORE_EVIDENCE"),
        ("kubernetes_deployment", "toctou_state_drift"): ("COMMIT", "E_STALE_STATE"),
        ("erp_purchase_approval", "policy_update_after_approval"): ("COMMIT", "E_POLICY_MISMATCH"),
        ("erp_purchase_approval", "privilege_tamper_at_commit"): ("COMMIT", "E_ACTION_HASH_MISMATCH"),
        ("erp_purchase_approval", "approval_nonce_replay"): ("DECISION", "DENY"),
        ("database_schema_migration", "over_scope_blast_radius"): ("DECISION", "ESCALATE_TO_HUMAN"),
        ("database_schema_migration", "argument_expansion_at_commit"): ("COMMIT", "E_ACTION_HASH_MISMATCH"),
        ("multi_agent_pipeline", "cross_step_replay"): ("COMMIT", "E_NONCE_REPLAY"),
        ("multi_agent_pipeline", "cross_agent_action_confusion"): ("COMMIT", "E_ACTION_HASH_MISMATCH"),
    }
    for key, (point, code) in expect.items():
        r = BY[key]
        assert r["detection_point"] == point, (key, r["detection_point"])
        assert r["observed"] == code, (key, r["observed"])


def test_all_twelve_failure_types_present():
    # the eight requested failure families are all exercised at least once
    scenarios = {r["scenario"] for r in RESULT["records"]}
    for needed in ("replay_duplicate_execution", "approval_reuse_cross_action",
                   "target_substitution", "stale_state_at_decision", "toctou_state_drift",
                   "policy_update_after_approval", "privilege_tamper_at_commit",
                   "argument_expansion_at_commit"):
        assert needed in scenarios, needed
