"""H5 — deterministic failure injection: every failure path is fail-safe."""
from __future__ import annotations

import pytest
from governance_providers.contracts import AssertionCoverage

from ai_hiring.validation import build_validation_env
from ai_hiring.validation.lifecycle import CaseSpec, run_lifecycle


def test_generator_timeout_fails_safe():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f1", generator_timeout=True))
    assert r.reached_stage == "generation_failed" and not r.recommendation_id


def test_generator_malformed_fails_safe():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f2", generator_malformed=True))
    assert r.reached_stage == "generation_failed"


def test_tap_timeout_blocks_readiness():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f3", tap_timeout=True))
    # provider failure → claim UNEVALUABLE → not review-ready (fail-safe)
    assert r.recommendation_status == "ASSERTION_REVIEW_REQUIRED" and not r.decision_id


def test_tap_malformed_blocks_readiness():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f4", tap_malformed=True))
    assert r.recommendation_status == "ASSERTION_REVIEW_REQUIRED"


def test_actiongate_unavailable_blocks_execution():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f5", action_unavailable=True))
    assert not r.authorized and not r.execution_status


def test_adapter_permanent_failure_fails_safe():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f6",
                                    exec_flags={"transport_fail": True, "transport_retryable": False}))
    assert r.proposal_status == "EXECUTION_FAILED" and not r.reconciliation_outcome


def test_malformed_receipt_fails_safe():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f7", exec_flags={"malformed": True}))
    assert r.proposal_status == "EXECUTION_FAILED"  # never EXECUTED


def test_unmet_obligation_blocks_execution():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="f8", action_constrained=frozenset({"ADVANCE_STAGE"}),
                                    satisfy_obligations=False))
    # authorized-with-constraints but obligations unmet → not executed
    assert r.authorized and r.proposal_status != "RECONCILED" and not r.execution_status


def test_no_failure_path_marks_false_success():
    env = build_validation_env()
    for cid, flags in [("g1", {"malformed": True}), ("g2", {"transport_fail": True, "transport_retryable": False}),
                       ("g3", {"observed_target": "rogue"})]:
        r = run_lifecycle(env, CaseSpec(case_id=cid, exec_flags=flags))
        assert r.proposal_status != "RECONCILED"
