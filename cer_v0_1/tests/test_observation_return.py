"""Observation-return tests (deliverable 15): the loop is not a one-way waterfall."""
from __future__ import annotations

from cer_v0_1 import control_plane as cp
from cer_v0_1 import spec
from cer_v0_1.actuation import ActuationRequest
from cer_v0_1.observation import GovernedExecutionResult, observe_and_reflect
from cer_v0_1.producers.langgraph_adapter import LangGraphCERAdapter
from cer_v0_1.producers.ugence import UgenceCERProducer

NOW = "2026-01-01T00:10:00.000Z"


def _req(**over):
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95,
          "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    op.update(over.pop("operational", {}))
    d = dict(cluster="fixture", namespace="protected", deployment="web", from_replicas=10,
             to_replicas=12, principal="agent:web-ops", permissions=("deploy",),
             delegator_id="sre", resource_version="1001", state_hash="sha-256:" + "ab" * 32,
             as_of="2026-01-01T00:09:30.000Z", operational=op, policy_version="1.0.0+abc",
             policy_digest="pd", correlation_id="protected/web", attach_evidence=True)
    d.update(over)
    return ActuationRequest(**d)


def test_result_returns_to_both_runtimes():
    req = _req()
    for producer, name in ((UgenceCERProducer(), "ugence"), (LangGraphCERAdapter(), "langgraph")):
        cer = producer.propose(req)
        result = cp.run_control_plane(cer, now=NOW, auto_evidence=True)
        obs = observe_and_reflect(name, GovernedExecutionResult.from_cp(result))
        # governance ended at eligibility; the runtime received the result and reflected
        assert obs["observed_cer_digest"] == spec.action_digest(cer)
        assert obs["runtime"] == name
        assert obs["next_step"]  # runtime decides what happens next


def test_eligible_result_triggers_execute_and_observe():
    result = cp.run_control_plane(UgenceCERProducer().propose(_req()), now=NOW, auto_evidence=True)
    obs = observe_and_reflect("ugence", GovernedExecutionResult.from_cp(result))
    assert result.eligible
    assert obs["next_step"] == "await_execution_result_then_verify"


def test_held_result_triggers_backoff_reobserve():
    result = cp.run_control_plane(
        UgenceCERProducer().propose(_req(operational={"freeze_active": True})),
        now=NOW, auto_evidence=True)
    obs = observe_and_reflect("ugence", GovernedExecutionResult.from_cp(result))
    assert result.combined_outcome == "HELD_BY_ACP"
    assert obs["next_step"] == "backoff_and_reobserve"


def test_runtime_owns_memory_update():
    result = cp.run_control_plane(UgenceCERProducer().propose(_req()), now=NOW, auto_evidence=True)
    obs = observe_and_reflect("ugence", GovernedExecutionResult.from_cp(result))
    # the memory update is produced by the runtime side, not the control plane
    assert obs["memory_update"]["last_action_digest"] == result.cer_digest
