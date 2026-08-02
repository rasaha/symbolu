"""Persistence and recovery checks (section 24, checks 30-38)."""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    recover_runtime,
    register_provider,
)
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.models.workflow import WorkflowStatus
from ugence_agent_runtime.persistence.checkpoints import Checkpoint
from ugence_agent_runtime.persistence.in_memory import (
    InMemoryCheckpointStore,
    InMemoryRuntimeStateStore,
)
from ugence_agent_runtime.persistence.recovery import recover_instance
from ugence_agent_runtime.runtime.errors import RecoveryError

from art_fakes import DispositionHook, RecordingProvider
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition


def _wf(*tasks):
    return WorkflowDefinition(workflow_id="wf", tasks=tuple(tasks))


def test_checkpoint_committed():  # check 30
    cs = InMemoryCheckpointStore()
    rt = create_runtime(AgentRuntimeConfig(checkpoint_store=cs))
    register_provider(rt, RecordingProvider("p"))
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", consequential=False)))
    assert cs.latest(inst.instance_id) is not None


def test_checkpoint_recovered():  # check 31, 35
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss))
    register_provider(rt, RecordingProvider("p"))
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p", consequential=False))
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.COMPLETED

    rt2 = create_runtime(AgentRuntimeConfig(state_store=ss))
    result = recover_runtime(rt2, inst.instance_id, wf)
    assert result.instance.status is WorkflowStatus.COMPLETED
    assert result.instance.task("t").status is TaskStatus.COMPLETED


def test_recovery_makes_no_provider_or_governance_call():  # checks 32, 33
    ss = InMemoryRuntimeStateStore()

    class ExplodingProvider(RecordingProvider):
        def execute(self, invocation):
            raise AssertionError("recovery must not call a provider")

    class ExplodingHook:
        def evaluate(self, *a, **k):
            raise AssertionError("recovery must not call governance")

    # First, run a workflow that HOLDs (so it is non-terminal in the store).
    hook = DispositionHook(GovernanceDisposition.HOLD)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hook))
    register_provider(rt, RecordingProvider("p"))
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p"))
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.WAITING

    # Recover in a runtime whose provider and hook would explode if called.
    rt2 = create_runtime(
        AgentRuntimeConfig(state_store=ss, governance_hook=ExplodingHook())
    )
    register_provider(rt2, ExplodingProvider("p"))
    result = recover_runtime(rt2, inst.instance_id, wf)  # must not raise
    assert result.requires_continuation is True


def test_running_state_requires_explicit_continuation():  # check 34
    # Hand-craft a checkpoint that says a task was RUNNING.
    ss = InMemoryRuntimeStateStore()
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p"))
    cp = Checkpoint.of(
        _instance_with(wf, {"t": TaskStatus.RUNNING}, WorkflowStatus.RUNNING),
        runtime_id="agent-runtime",
        runtime_version="0.1.2",
    )
    ss.save(cp)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss))
    result = recover_runtime(rt, cp.instance_id, wf)
    assert result.requires_continuation is True
    assert result.instance.task("t").status is TaskStatus.READY  # re-armed, not auto-run
    assert result.instance.status is WorkflowStatus.PAUSED


def test_cancelled_state_remains_cancelled():  # check 36
    ss = InMemoryRuntimeStateStore()
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p"))
    cp = Checkpoint.of(
        _instance_with(wf, {"t": TaskStatus.CANCELLED}, WorkflowStatus.CANCELLED),
        runtime_id="agent-runtime",
        runtime_version="0.1.2",
    )
    ss.save(cp)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss))
    result = recover_runtime(rt, cp.instance_id, wf)
    assert result.instance.status is WorkflowStatus.CANCELLED
    assert result.instance.task("t").status is TaskStatus.CANCELLED


def test_corrupted_checkpoint_fails_closed():  # check 37
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p"))
    cp = Checkpoint.of(
        _instance_with(wf, {"t": TaskStatus.COMPLETED}, WorkflowStatus.COMPLETED),
        runtime_id="agent-runtime",
        runtime_version="0.1.2",
    )
    # Tamper with the payload without recomputing the digest.
    tampered = Checkpoint.from_dict({**cp.to_dict(), "status": "RUNNING"})
    with pytest.raises(RecoveryError):
        recover_instance(tampered, wf, "agent-runtime", "0.1.2")


def test_configuration_mismatch_reported():  # check 38
    ss = InMemoryRuntimeStateStore()
    wf = _wf(TaskDefinition(task_id="t", operation="op", provider_id="p"))
    cp = Checkpoint.of(
        _instance_with(wf, {"t": TaskStatus.COMPLETED}, WorkflowStatus.COMPLETED),
        runtime_id="agent-runtime",
        runtime_version="9.9.9",  # different version
    )
    ss.save(cp)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, runtime_version="0.1.2"))
    result = recover_runtime(rt, cp.instance_id, wf)
    assert result.config_mismatch is True


# --- helper ----------------------------------------------------------------
def _instance_with(wf, statuses, wf_status):
    from ugence_agent_runtime.models.workflow import WorkflowInstance

    inst = WorkflowInstance.create("inst-x", wf, correlation_id="corr-x")
    for tid, status in statuses.items():
        inst.tasks[tid].status = status
    inst.status = wf_status
    return inst
