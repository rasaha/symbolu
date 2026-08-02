"""Governance-boundary checks (section 24, checks 39-46)."""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.decisions import (
    RuntimeDirective,
    directive_for,
    permits_execution,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
)
from ugence_agent_runtime.governance.noop import NoopGovernanceHook
from ugence_agent_runtime.models.workflow import WorkflowStatus

from art_fakes import DispositionHook, RecordingProvider


def _run(disposition):
    hook = DispositionHook(disposition)
    p = RecordingProvider("p")
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    register_provider(rt, p)
    wf = WorkflowDefinition(workflow_id="wf", tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),))
    inst = rt.start_workflow(wf)
    return inst, p, hook


def test_clear_permits_continuation():  # check 39
    inst, p, _ = _run(GovernanceDisposition.CLEAR)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


def test_hold_prevents_continuation():  # check 40
    inst, p, _ = _run(GovernanceDisposition.HOLD)
    assert inst.status is WorkflowStatus.WAITING
    assert p.calls == []


def test_block_prevents_execution():  # check 41
    inst, p, _ = _run(GovernanceDisposition.BLOCK)
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []


def test_escalate_pauses():  # check 42
    inst, p, _ = _run(GovernanceDisposition.ESCALATE)
    assert inst.status is WorkflowStatus.PAUSED
    assert p.calls == []


def test_runtime_cannot_broaden_disposition():  # check 43
    # An unknown / non-CLEAR disposition never becomes CONTINUE.
    for disp in (GovernanceDisposition.HOLD, GovernanceDisposition.BLOCK, GovernanceDisposition.ESCALATE):
        ev = GovernanceEvaluation(disposition=disp)
        assert directive_for(ev) is not RuntimeDirective.CONTINUE
        assert permits_execution(ev) is False
    # A missing evaluation fails closed (never CONTINUE).
    assert directive_for(None) is RuntimeDirective.STOP


def test_governance_reference_preserved():  # check 44
    inst, p, hook = _run(GovernanceDisposition.CLEAR)
    assert inst.task("t").governance_reference == hook.reference


def test_evaluation_time_is_caller_controlled():  # check 45
    ticks = iter([11.0, 22.0, 33.0])
    rt = create_runtime(AgentRuntimeConfig(governance_hook=DispositionHook(GovernanceDisposition.CLEAR), clock=lambda: next(ticks)))
    register_provider(rt, RecordingProvider("p"))
    hook = rt.config.governance_hook
    wf = WorkflowDefinition(workflow_id="wf", tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),))
    rt.start_workflow(wf)
    # The runtime supplied the clock value as evaluation_time (11.0), not the hook.
    assert hook.evaluation_times == [11.0]


def test_no_concrete_governance_package_required():  # check 46
    # The default hook is the neutral no-op; the core requires no concrete adapter.
    cfg = AgentRuntimeConfig()
    assert isinstance(cfg.governance_hook, NoopGovernanceHook)
    ev = cfg.governance_hook.evaluate.__self__.evaluate  # attribute exists
    assert callable(ev)
