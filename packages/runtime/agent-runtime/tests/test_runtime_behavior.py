"""Runtime behavior checks (section 24, checks 18-29)."""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    RetryPolicy,
    TaskDefinition,
    WorkflowDefinition,
    cancel_workflow,
    create_runtime,
    pause_workflow,
    register_provider,
    resume_workflow,
)
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.models.transitions import (
    check_task_transition,
    check_workflow_transition,
    is_valid_task_transition,
)
from ugence_agent_runtime.models.workflow import WorkflowStatus
from ugence_agent_runtime.providers.interfaces import ToolResult
from ugence_agent_runtime.runtime.errors import InvalidTransitionError

from art_fakes import DispositionHook, FailingProvider, RecordingProvider
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition


def _wf(*tasks):
    return WorkflowDefinition(workflow_id="wf", tasks=tuple(tasks))


def _runtime(provider=None, **cfg):
    # These tests exercise coordination, not governance. Unless a test supplies its
    # own hook, use the explicit (opt-in, test-only) AllowAll hook so consequential
    # tasks clear — the production default fails closed and is covered separately.
    cfg.setdefault("governance_hook", AllowAllGovernanceHook())
    rt = create_runtime(AgentRuntimeConfig(**cfg))
    if provider is not None:
        register_provider(rt, provider)
    return rt


def test_basic_workflow_completes():  # check 18
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t1", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED
    assert inst.task("t1").status is TaskStatus.COMPLETED


def test_task_transitions_in_dependency_order():  # check 19
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = rt.start_workflow(
        _wf(
            TaskDefinition(task_id="a", operation="a", provider_id="p"),
            TaskDefinition(task_id="b", operation="b", provider_id="p", depends_on=("a",)),
        )
    )
    assert inst.status is WorkflowStatus.COMPLETED
    assert [c.operation for c in p.calls] == ["a", "b"]


def test_invalid_transition_rejected():  # check 20
    with pytest.raises(InvalidTransitionError):
        check_task_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
    with pytest.raises(InvalidTransitionError):
        check_workflow_transition(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING)
    assert not is_valid_task_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)


def test_pause_and_resume():  # checks 21, 22
    hook = DispositionHook(GovernanceDisposition.ESCALATE)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.PAUSED  # ESCALATE paused it
    assert p.calls == []
    # switch the hook's disposition to CLEAR and resume -> completes
    hook.disposition = GovernanceDisposition.CLEAR
    resume_workflow(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


def test_explicit_pause_of_running_noop_when_terminal():  # check 21
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    # already COMPLETED; pause is a no-op, not an illegal transition
    pause_workflow(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.COMPLETED


def test_cancellation():  # check 23
    hook = DispositionHook(GovernanceDisposition.HOLD)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.WAITING
    cancel_workflow(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.CANCELLED
    assert inst.task("t").status is TaskStatus.CANCELLED


def test_timeout_classified():  # check 24
    # A clock that jumps forward between the pre- and post-execution marks makes the
    # provider call exceed its timeout. The task is non-consequential so no
    # governance evaluation consumes a clock tick, keeping the sequence explicit.
    ticks = iter([0.0, 100.0])

    def clock():
        try:
            return next(ticks)
        except StopIteration:
            return 100.0

    p = RecordingProvider("p")
    rt = _runtime(p, clock=clock, default_timeout=1.0)
    inst = rt.start_workflow(
        _wf(TaskDefinition(task_id="t", operation="op", provider_id="p", consequential=False))
    )
    assert inst.status is WorkflowStatus.FAILED
    res = rt.result(inst.instance_id)
    assert res.failures[0].category.value == "TIMEOUT"


def test_retry_then_succeed():  # check 25
    p = FailingProvider("p", retriable=True, fail_times=1)  # fail once, then succeed
    rt = _runtime(p, retry_policy=RetryPolicy(max_attempts=3))
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", max_attempts=3)))
    assert inst.status is WorkflowStatus.COMPLETED
    assert p.calls == 2


def test_retry_exhausted_classified():  # check 25/27
    p = FailingProvider("p", retriable=True)  # always fails
    rt = _runtime(p, retry_policy=RetryPolicy(max_attempts=2))
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p", max_attempts=2)))
    assert inst.status is WorkflowStatus.FAILED
    res = rt.result(inst.instance_id)
    assert res.failures[0].category.value == "RETRY_EXHAUSTED"
    assert p.calls == 2


def test_provider_success_propagated():  # check 26
    p = RecordingProvider("p", output={"answer": 42})
    rt = _runtime(p)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.task("t").result == {"answer": 42}


def test_provider_failure_classified():  # check 27
    p = FailingProvider("p", retriable=False)
    rt = _runtime(p)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.FAILED
    assert rt.result(inst.instance_id).failures[0].category.value == "PROVIDER_ERROR"


def test_missing_provider_classified():
    rt = _runtime(None)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="nope")))
    assert inst.status is WorkflowStatus.FAILED
    assert rt.result(inst.instance_id).failures[0].category.value == "PROVIDER_NOT_FOUND"


def test_completed_task_not_rerun():  # check 28
    hook = DispositionHook(GovernanceDisposition.HOLD)
    p = RecordingProvider("p")
    rt = _runtime(
        p,
        governance_hook=hook,
    )
    inst = rt.start_workflow(
        _wf(
            TaskDefinition(task_id="a", operation="a", provider_id="p", consequential=False),
            TaskDefinition(task_id="b", operation="b", provider_id="p", depends_on=("a",)),
        )
    )
    # a completed (non-consequential); b is HOLD -> WAITING
    assert inst.task("a").status is TaskStatus.COMPLETED
    assert inst.status is WorkflowStatus.WAITING
    hook.disposition = GovernanceDisposition.CLEAR
    resume_workflow(rt, inst.instance_id)
    # a executed exactly once across the whole run
    assert [c.operation for c in p.calls].count("a") == 1


def test_completed_workflow_not_restarted():  # check 29
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = rt.start_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="p")))
    assert inst.status is WorkflowStatus.COMPLETED
    with pytest.raises(Exception):
        resume_workflow(rt, inst.instance_id)
