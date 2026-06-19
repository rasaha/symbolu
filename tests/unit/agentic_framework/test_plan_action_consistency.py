"""
test_plan_action_consistency.py — deterministic heuristics for the Phase 2 observable.
"""

from __future__ import annotations

from agentic.agentic_framework.trust.decision import decide
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    ObservableType,
    TrustDecision,
    Verdict,
)
from agentic.agentic_framework.trust.plan_action_consistency import (
    PlanActionContext,
    build_plan_action_observation,
    detect_plan_action_mismatch,
)


def _kinds(ctx):
    return {v.kind for v in detect_plan_action_mismatch(ctx)}


def test_read_plan_mutating_action():
    ctx = PlanActionContext(stated_plan="Read and summarize the quarterly report",
                            proposed_action="delete_report", action_args={"id": "q3"})
    assert "read_plan_mutating_action" in _kinds(ctx)


def test_confirm_plan_executes():
    ctx = PlanActionContext(stated_plan="Ask the user to confirm before doing anything",
                            proposed_action="send_payment", action_args={"amount": 1000})
    assert "confirm_plan_executes" in _kinds(ctx)


def test_no_external_plan_external_action():
    ctx = PlanActionContext(stated_plan="Work locally, no external access",
                            proposed_action="http_post", action_args={"url": "http://x"})
    assert "no_external_plan_external_action" in _kinds(ctx)


def test_resource_mismatch_only_on_structured_targets():
    ctx = PlanActionContext(stated_plan="update the billing record",
                            proposed_action="update_record",
                            plan_targets=("billing/acme",), action_targets=("payroll/globex",))
    assert "resource_mismatch" in _kinds(ctx)
    # shared target → no mismatch
    ok = PlanActionContext(stated_plan="update billing", proposed_action="update_record",
                           plan_targets=("billing/acme",), action_targets=("billing/acme",))
    assert "resource_mismatch" not in _kinds(ok)


def test_consistent_plan_action_is_safe():
    ctx = PlanActionContext(stated_plan="Read and summarize the logs",
                            proposed_action="read_logs", action_args={"path": "/var/log"})
    assert detect_plan_action_mismatch(ctx) == []
    assert build_plan_action_observation(ctx).verdict == Verdict.SAFE


def test_empty_context_is_inert():
    assert build_plan_action_observation(PlanActionContext()) is None
    assert build_plan_action_observation(None) is None


def test_action_mutates_override():
    # explicit override fires even when the action name has no mutate keyword
    ctx = PlanActionContext(stated_plan="just read the data", proposed_action="op",
                            action_mutates=True)
    assert "read_plan_mutating_action" in _kinds(ctx)


def test_observation_is_provisional_validator_and_confirm_only():
    obs = build_plan_action_observation(
        PlanActionContext(stated_plan="read only", proposed_action="delete_all",
                          action_mutates=True))
    assert obs.otype == ObservableType.VALIDATOR
    assert obs.evidence == EvidenceStatus.PROVISIONAL
    assert obs.name == "plan_action_consistency" and obs.verdict == Verdict.UNSURE
    assert decide([obs]).decision == TrustDecision.CONFIRM


def test_heuristic_never_blocks_even_when_proven():
    # heuristic stays confirm-only: a PROVEN plan-action observation still only CONFIRMs.
    obs = build_plan_action_observation(
        PlanActionContext(stated_plan="read only", proposed_action="delete_all",
                          action_mutates=True),
        evidence=EvidenceStatus.PROVEN)
    assert decide([obs]).decision == TrustDecision.CONFIRM
