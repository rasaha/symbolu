"""H22-A — bounded workflow advancement seam (task section 17, checks A–N).

These tests exercise the additive ``prepare_workflow`` / ``advance_workflow`` primitive
that lets an external orchestrator advance independent workflows one bounded quantum at
a time, WITHOUT the runtime draining any workflow to completion and WITHOUT weakening
governance, exact-action binding, canonical execution state, checkpointing, or recovery.

A quantum = at most one runtime task transition through one stable, checkpointed
boundary. The governance→exact-action→provider→transition→checkpoint chain runs entirely
within a single quantum and is never observable/preemptible from the scheduler's side.
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    WorkflowAdvanceOutcome,
    WorkflowAdvanceStop,
    advance_workflow,
    create_runtime,
    prepare_workflow,
    recover_runtime,
    register_provider,
    resume_workflow,
    start_workflow,
)
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.models.workflow import WorkflowStatus
from ugence_agent_runtime.persistence.in_memory import (
    InMemoryCheckpointStore,
    InMemoryRuntimeStateStore,
)

from art_fakes import DispositionHook, RecordingProvider
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition


# --- helpers ---------------------------------------------------------------
def _wf(workflow_id, *tasks):
    return WorkflowDefinition(workflow_id=workflow_id, tasks=tuple(tasks))


def _runtime(provider=None, **cfg):
    cfg.setdefault("governance_hook", AllowAllGovernanceHook())
    rt = create_runtime(AgentRuntimeConfig(**cfg))
    if provider is not None:
        register_provider(rt, provider)
    return rt


def _seq(*task_ids, dep_chain=True, **kw):
    """A workflow whose tasks run in registration order, chained by dependency so
    exactly one task is runnable at a time (deterministic single-quantum steps)."""
    tasks = []
    prev = None
    for tid in task_ids:
        depends_on = (prev,) if (dep_chain and prev is not None) else ()
        tasks.append(
            TaskDefinition(task_id=tid, operation=tid, provider_id="p",
                           depends_on=depends_on, **kw)
        )
        prev = tid
    return tasks


# --- A. Preparation --------------------------------------------------------
def test_prepare_does_not_invoke_governance_or_provider():
    """A prepared workflow neither evaluates governance nor invokes a provider merely
    because it was created — it stops RUNNING with no task advanced."""
    hook = DispositionHook(GovernanceDisposition.CLEAR)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2")))

    assert inst.status is WorkflowStatus.RUNNING
    assert inst.task("t1").status is TaskStatus.PENDING
    assert inst.task("t2").status is TaskStatus.PENDING
    assert hook.evaluations == []      # no governance crossed
    assert p.calls == []               # no provider invoked


def test_prepare_checkpoints_initial_running_state():
    cs = InMemoryCheckpointStore()
    rt = _runtime(RecordingProvider("p"), checkpoint_store=cs)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1")))
    cp = cs.latest(inst.instance_id)
    assert cp is not None
    assert cp.status == WorkflowStatus.RUNNING.value


# --- B. Single quantum -----------------------------------------------------
def test_single_quantum_advances_only_one_task():
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2", "t3")))

    r1 = advance_workflow(rt, inst.instance_id)
    assert isinstance(r1, WorkflowAdvanceOutcome)
    assert r1.task_id == "t1"
    assert r1.task_status == TaskStatus.COMPLETED.value
    assert r1.progressed is True
    assert r1.stop_reason == WorkflowAdvanceStop.TASK_ADVANCED.value
    assert inst.status is WorkflowStatus.RUNNING
    # ONLY one task ran — the runtime did not drain the rest.
    assert [c.operation for c in p.calls] == ["t1"]
    assert inst.task("t2").status is TaskStatus.PENDING
    assert inst.task("t3").status is TaskStatus.PENDING


def test_quanta_run_workflow_to_completion_one_at_a_time():
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2")))

    advance_workflow(rt, inst.instance_id)  # t1
    advance_workflow(rt, inst.instance_id)  # t2
    # Now no runnable task remains -> finalization quantum completes the workflow.
    rfin = advance_workflow(rt, inst.instance_id)
    assert rfin.task_id is None
    assert rfin.stop_reason == WorkflowAdvanceStop.WORKFLOW_COMPLETED.value
    assert rfin.terminal is True
    assert inst.status is WorkflowStatus.COMPLETED
    assert [c.operation for c in p.calls] == ["t1", "t2"]


# --- C. Sequential interleaving --------------------------------------------
def test_sequential_interleaving_A_B_A_B_without_draining():
    """advance(A)->A1, advance(B)->B1, advance(A)->A2, advance(B)->B2 — neither
    runtime drains the other workflow. One runtime object, two instances, isolated."""
    p = RecordingProvider("p")
    rt = _runtime(p)
    a = prepare_workflow(rt, _wf("A", *_seq("A1", "A2")))
    b = prepare_workflow(rt, _wf("B", *_seq("B1", "B2")))

    order = []
    for inst in (a, b, a, b):
        r = advance_workflow(rt, inst.instance_id)
        order.append(r.task_id)

    assert order == ["A1", "B1", "A2", "B2"]
    assert [c.operation for c in p.calls] == ["A1", "B1", "A2", "B2"]
    # Both are still RUNNING (their finalization quantum has not been requested yet):
    # bounded advancement never ran ahead.
    assert a.status is WorkflowStatus.RUNNING
    assert b.status is WorkflowStatus.RUNNING


# --- D. Existing start_workflow compatibility ------------------------------
def test_start_workflow_still_drains_to_completion():
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = start_workflow(rt, _wf("wf", *_seq("t1", "t2", "t3")))
    assert inst.status is WorkflowStatus.COMPLETED
    assert [c.operation for c in p.calls] == ["t1", "t2", "t3"]


def test_start_and_prepare_produce_identical_event_sequences():
    """start_workflow == prepare_workflow + drive-to-stable: the observable event
    stream is identical (event types, in order)."""
    def run(use_start):
        events = []
        rt = _runtime(RecordingProvider("p"), event_sink=events.append)
        wf = _wf("wf", *_seq("t1", "t2"))
        if use_start:
            inst = start_workflow(rt, wf)
        else:
            inst = prepare_workflow(rt, wf)
            while inst.status is WorkflowStatus.RUNNING:
                advance_workflow(rt, inst.instance_id)
        return [e.type for e in events]

    assert run(True) == run(False)


# --- E. Governance CLEAR ---------------------------------------------------
def test_consequential_quantum_gets_fresh_governance_before_provider():
    hook = DispositionHook(GovernanceDisposition.CLEAR)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p", consequential=True)))
    assert hook.evaluations == []          # nothing evaluated at prepare time
    r = advance_workflow(rt, inst.instance_id)
    assert hook.evaluations == [("t", "op")]  # fresh governance this quantum
    assert r.task_status == TaskStatus.COMPLETED.value
    assert len(p.calls) == 1
    assert r.execution_state_digest is not None


# --- F. HOLD ---------------------------------------------------------------
def test_hold_stops_safely_with_no_provider_call():
    cs = InMemoryCheckpointStore()
    hook = DispositionHook(GovernanceDisposition.HOLD)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook, checkpoint_store=cs)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)

    assert inst.task("t").status is TaskStatus.WAITING
    assert inst.status is WorkflowStatus.WAITING
    assert p.calls == []
    assert r.stop_reason == WorkflowAdvanceStop.WORKFLOW_WAITING.value
    assert r.waiting is True
    cp = cs.latest(inst.instance_id)
    assert cp is not None and cp.verify()


# --- G. ESCALATE -----------------------------------------------------------
def test_escalate_stops_safely_at_paused_with_no_provider_call():
    hook = DispositionHook(GovernanceDisposition.ESCALATE)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)

    assert inst.task("t").status is TaskStatus.WAITING
    assert inst.status is WorkflowStatus.PAUSED
    assert p.calls == []
    assert r.stop_reason == WorkflowAdvanceStop.WORKFLOW_PAUSED.value
    assert r.paused is True


# --- H. BLOCK --------------------------------------------------------------
def test_block_stops_safely_at_failed_with_no_provider_call():
    hook = DispositionHook(GovernanceDisposition.BLOCK)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)

    assert inst.task("t").status is TaskStatus.FAILED
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []
    assert r.stop_reason == WorkflowAdvanceStop.WORKFLOW_FAILED.value
    assert r.terminal is True


# --- I. Exact-action invariant ---------------------------------------------
def test_clear_without_exact_binding_fails_closed_through_advance():
    """A hook that returns CLEAR without binding the exact proposal must still fail
    closed under bounded advancement — the seam cannot bypass exact-action validation."""
    hook = DispositionHook(GovernanceDisposition.CLEAR, bind=False)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.FAILED
    assert p.calls == []               # never executed on an unbound CLEAR
    assert r.stop_reason == WorkflowAdvanceStop.WORKFLOW_FAILED.value


def test_advance_result_exposes_no_mutable_proposal_handle():
    """The advance result is a frozen value object referencing state by digest only —
    it hands out no mutable proposal/invocation the scheduler could tamper with."""
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)
    with pytest.raises(Exception):
        r.task_id = "mutated"          # frozen dataclass


# --- J. Checkpoint self-recoverability -------------------------------------
def test_every_bounded_checkpoint_is_self_recoverable():
    cs = InMemoryCheckpointStore()
    rt = _runtime(RecordingProvider("p"), checkpoint_store=cs)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2")))
    while inst.status is WorkflowStatus.RUNNING:
        advance_workflow(rt, inst.instance_id)
    # Every emitted checkpoint verifies and passes recovery validation.
    history = cs.history(inst.instance_id)
    assert len(history) >= 2  # at least the initial RUNNING checkpoint + a task boundary
    for cp in history:
        assert cp.verify()
        assert cp.verify_extension()
        ok, reason = cp.validate_execution_states()
        assert ok, reason


# --- K. Recovery -----------------------------------------------------------
def test_recover_partially_advanced_then_fresh_governance_on_continue():
    ss = InMemoryRuntimeStateStore()

    class ExplodingProvider(RecordingProvider):
        def execute(self, invocation):
            raise AssertionError("recovery must not call a provider")

    class ExplodingHook:
        def evaluate(self, *a, **k):
            raise AssertionError("recovery must not call governance")

    hook = DispositionHook(GovernanceDisposition.CLEAR)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook, state_store=ss)
    wf = _wf("wf", *_seq("t1", "t2"))
    inst = prepare_workflow(rt, wf)
    advance_workflow(rt, inst.instance_id)  # t1 COMPLETED, t2 still PENDING; workflow RUNNING
    iid = inst.instance_id

    # 1) Recovery itself makes no provider or governance call (would explode if it did).
    rt2 = create_runtime(AgentRuntimeConfig(
        state_store=ss, governance_hook=ExplodingHook()))
    register_provider(rt2, ExplodingProvider("p"))
    result = recover_runtime(rt2, iid, wf)  # must not raise
    assert result.requires_continuation is True
    assert result.instance.task("t1").status is TaskStatus.COMPLETED
    assert result.instance.status is WorkflowStatus.PAUSED  # non-terminal -> explicit continuation

    # 2) Explicit continuation in a fresh runtime with real deps performs FRESH governance
    #    before consequential execution — and never reruns the committed task.
    hook2 = DispositionHook(GovernanceDisposition.CLEAR)
    p2 = RecordingProvider("p")
    rt3 = _runtime(p2, governance_hook=hook2, state_store=ss)
    recovered = recover_runtime(rt3, iid, wf).instance
    resume_workflow(rt3, iid)  # PAUSED -> RUNNING -> drive to completion
    assert recovered.status is WorkflowStatus.COMPLETED
    assert hook2.evaluations == [("t2", "t2")]        # only the not-yet-run task
    assert [c.operation for c in p2.calls] == ["t2"]  # t1 NOT rerun


# --- L. Canonical execution state ------------------------------------------
def test_advanced_trajectory_is_journaled_and_digest_resolvable():
    rt = _runtime(RecordingProvider("p"))
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    r = advance_workflow(rt, inst.instance_id)
    assert r.execution_state_digest is not None
    resolved = rt.execution_state_by_digest(inst.instance_id, r.execution_state_digest)
    assert resolved is not None
    assert resolved.state_digest == r.execution_state_digest


# --- M. No repeated committed task -----------------------------------------
def test_committed_task_not_rerun_after_checkpoint_recover_continue():
    ss = InMemoryRuntimeStateStore()
    hook = DispositionHook(GovernanceDisposition.CLEAR)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook, state_store=ss)
    wf = _wf("wf", *_seq("t1", "t2"))
    inst = prepare_workflow(rt, wf)
    advance_workflow(rt, inst.instance_id)   # t1 committed + checkpointed

    rt2 = _runtime(RecordingProvider("p"),
                   governance_hook=DispositionHook(GovernanceDisposition.CLEAR),
                   state_store=ss)
    result = recover_runtime(rt2, inst.instance_id, wf)
    # A previously COMPLETED task stays COMPLETED and is never re-armed.
    assert result.instance.task("t1").status is TaskStatus.COMPLETED


# --- N. Multiple prepared instances stay isolated --------------------------
def test_one_runtime_many_instances_state_isolation():
    p = RecordingProvider("p")
    rt = _runtime(p)
    a = prepare_workflow(rt, _wf("A", *_seq("A1", "A2")))
    b = prepare_workflow(rt, _wf("B", *_seq("B1")))
    c = prepare_workflow(rt, _wf("C", *_seq("C1", "C2", "C3")))

    # Drive B fully; A and C must be untouched.
    while b.status is WorkflowStatus.RUNNING:
        advance_workflow(rt, b.instance_id)
    assert b.status is WorkflowStatus.COMPLETED
    assert a.task("A1").status is TaskStatus.PENDING
    assert a.task("A2").status is TaskStatus.PENDING
    assert all(c.task(t).status is TaskStatus.PENDING for t in ("C1", "C2", "C3"))
    assert a.instance_id != b.instance_id != c.instance_id


# --- state-machine safety: advance on non-RUNNING is a deterministic no-op --
def test_advance_terminal_workflow_is_noop():
    rt = _runtime(RecordingProvider("p"))
    inst = start_workflow(rt, _wf("wf", *_seq("t1")))
    assert inst.status is WorkflowStatus.COMPLETED
    r = advance_workflow(rt, inst.instance_id)
    assert r.progressed is False
    assert r.stop_reason == WorkflowAdvanceStop.ALREADY_TERMINAL.value
    assert r.status_before == r.status_after == WorkflowStatus.COMPLETED.value


def test_advance_waiting_requires_explicit_resume():
    """advance() never self-resolves a governance HOLD — the orchestrator must resume."""
    hook = DispositionHook(GovernanceDisposition.HOLD)
    p = RecordingProvider("p")
    rt = _runtime(p, governance_hook=hook)
    inst = prepare_workflow(rt, _wf("wf", TaskDefinition(
        task_id="t", operation="op", provider_id="p")))
    advance_workflow(rt, inst.instance_id)         # -> WAITING (HOLD)
    assert inst.status is WorkflowStatus.WAITING

    r = advance_workflow(rt, inst.instance_id)     # no-op, needs resume
    assert r.progressed is False
    assert r.stop_reason == WorkflowAdvanceStop.REQUIRES_RESUME.value
    assert p.calls == []
    # Explicit resume + fresh CLEAR then advances it.
    hook.disposition = GovernanceDisposition.CLEAR
    resume_workflow(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(p.calls) == 1


def test_advance_paused_by_explicit_pause_requires_resume():
    p = RecordingProvider("p")
    rt = _runtime(p)
    inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2")))
    rt.pause_workflow(inst.instance_id)            # RUNNING -> PAUSED
    r = advance_workflow(rt, inst.instance_id)
    assert r.progressed is False
    assert r.stop_reason == WorkflowAdvanceStop.REQUIRES_RESUME.value


def test_advance_is_deterministic_across_identical_runs():
    def run():
        rt = _runtime(RecordingProvider("p"))
        inst = prepare_workflow(rt, _wf("wf", *_seq("t1", "t2", "t3")))
        digests = []
        while inst.status is WorkflowStatus.RUNNING:
            r = advance_workflow(rt, inst.instance_id)
            digests.append((r.task_id, r.stop_reason, r.execution_state_digest))
        return digests

    assert run() == run()
