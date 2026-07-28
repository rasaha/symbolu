"""
Tests for H17 — Event-Driven Execution & Long-Lived Workflows.

Required scenarios:
- Wait (workflow suspends correctly).
- Resume (correct event resumes workflow).
- Wrong event (workflow remains waiting).
- Timeout (transitions deterministically).
- Memory update (event updates WorkingMemory).
- Assumption update (events affect H13).
- Hierarchical resume (only affected subtree resumes).
- Budget preservation (waiting consumes no budget; resume shares one budget).
- Trace reconstruction (entire lifecycle reconstructs).
- Determinism (identical event streams → identical histories).

Evidence requirements:
1. Same event sequence always produces the same workflow history.
2. Waiting does not consume execution budget.
3. Resume continues from preserved state rather than restarting.
4. Events update WorkingMemory and assumptions before execution resumes.
5. Only the affected subtree resumes after an event.
6. All H10–H16 guarantees remain unchanged.
"""

import pytest

from agentic.agentic_framework import (
    WorkingMemory,
    MemoryWrite,
    RunBudget,
    RunBudgetLimits,
    AgentProfile,
    CapabilityRegistry,
    ScriptedWorker,
    WorkerResult,
    # H13
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
    # H15
    Goal,
    GoalStatus,
    StaticDecomposer,
    # H17
    WorkflowEngine,
    WorkflowStatus,
    WaitCondition,
    WaitKind,
    WorkflowEvent,
    EventType,
    format_workflow_trace,
)


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("worker", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))
    return r


def _linear_goals():
    return [
        Goal("collect", "collect", required_capabilities=frozenset({"do"}), expected_outputs=("data",), priority=1),
        Goal("approve", "approve", required_capabilities=frozenset({"do"}), dependencies=("collect",), expected_outputs=("approved",), priority=2),
        Goal("finalize", "finalize", required_capabilities=frozenset({"do"}), dependencies=("approve",), expected_outputs=("result",), priority=3),
    ]


def _approval_wait():
    return WaitCondition("wait_appr", "approve", kind=WaitKind.WAIT_FOR_APPROVAL,
                         event_type=EventType.APPROVAL_RECEIVED, match=(("doc", "D1"),))


def _suspended_workflow(memory=None, budget=None, ctx=None, waits=None):
    eng = WorkflowEngine(_registry())
    wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", _linear_goals()),
                             memory or WorkingMemory(), run_budget=budget, assumption_context=ctx,
                             wait_conditions=waits or [_approval_wait()])
    eng.start(wf)
    return eng, wf


# ---------------------------------------------------------------------------
# Wait / suspend
# ---------------------------------------------------------------------------
class TestWait:
    def test_workflow_suspends_at_wait(self):
        eng, wf = _suspended_workflow()
        assert wf.status == WorkflowStatus.WAITING
        assert wf.current_goal == "approve"
        # Work before the wait completed; the gated goal did not run.
        assert wf.tree.lookup("collect").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("approve").status == GoalStatus.BLOCKED
        assert [wc.condition_id for wc in wf.waiting_conditions] == ["wait_appr"]

    def test_suspension_recorded_in_trace(self):
        eng, wf = _suspended_workflow()
        kinds = [e.kind for e in wf.trace.entries]
        assert "STARTED" in kinds and "SUSPENDED" in kinds


# ---------------------------------------------------------------------------
# Resume / wrong event
# ---------------------------------------------------------------------------
class TestResume:
    def test_correct_event_resumes(self):
        eng, wf = _suspended_workflow()
        eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.tree.lookup("approve").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("finalize").status == GoalStatus.COMPLETED

    def test_wrong_event_stays_waiting(self):
        eng, wf = _suspended_workflow()
        eng.deliver(WorkflowEvent("bad", EventType.FILE_UPLOADED, {"file": "x"}, timestamp=1))
        assert wf.status == WorkflowStatus.WAITING
        assert wf.tree.lookup("approve").status == GoalStatus.BLOCKED

    def test_event_payload_mismatch_stays_waiting(self):
        eng, wf = _suspended_workflow()
        # Right type, wrong payload (doc != D1).
        eng.deliver(WorkflowEvent("e", EventType.APPROVAL_RECEIVED, {"doc": "OTHER"}, timestamp=1))
        assert wf.status == WorkflowStatus.WAITING

    def test_resume_continues_from_preserved_state(self):
        # 'collect' ran once, before the wait; it must NOT re-run on resume.
        counter = {"collect": 0}

        def worker(contract, memory):
            if contract.goal_id == "collect":
                counter["collect"] += 1
            return WorkerResult(success=True, outputs={k: "ok" for k in contract.expected_outputs})

        reg = CapabilityRegistry()
        reg.register(AgentProfile("worker", capabilities=frozenset({"do"}), trust_level=5), ScriptedWorker(worker))
        eng = WorkflowEngine(reg)
        wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", _linear_goals()),
                                 WorkingMemory(), wait_conditions=[_approval_wait()])
        eng.start(wf)
        eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
        assert counter["collect"] == 1  # not restarted


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------
class TestTimeout:
    def test_timeout_fail_transitions_deterministically(self):
        eng = WorkflowEngine(_registry())
        wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", [
            Goal("a", "a", required_capabilities=frozenset({"do"}), expected_outputs=("x",))]),
            WorkingMemory(), wait_conditions=[WaitCondition("wt", "a", kind=WaitKind.WAIT_FOR_TIMER,
                                                            event_type=EventType.TIMEOUT, on_timeout="fail")])
        eng.start(wf)
        assert wf.status == WorkflowStatus.WAITING
        eng.fire_timeout(wf, "wt", timestamp=5)
        assert wf.tree.lookup("a").status == GoalStatus.FAILED
        assert wf.status == WorkflowStatus.FAILED

    def test_timeout_satisfy_proceeds(self):
        eng = WorkflowEngine(_registry())
        wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", [
            Goal("a", "a", required_capabilities=frozenset({"do"}), expected_outputs=("x",))]),
            WorkingMemory(), wait_conditions=[WaitCondition("wt", "a", kind=WaitKind.WAIT_FOR_TIMER, on_timeout="satisfy")])
        eng.start(wf)
        eng.fire_timeout(wf, "wt", timestamp=5)
        assert wf.tree.lookup("a").status == GoalStatus.COMPLETED
        assert wf.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Memory / assumption updates from events
# ---------------------------------------------------------------------------
class TestStateUpdates:
    def test_event_updates_working_memory_before_resume(self):
        mem = WorkingMemory()
        eng, wf = _suspended_workflow(memory=mem)
        eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2,
                                  memory_writes=[MemoryWrite("approval_note", "signed by manager")]))
        # Memory written by the event, versioned + traceable.
        assert mem.peek("approval_note").value == "signed by manager"
        assert mem.peek("approval_note").producing_step == "event:e1"

    def test_event_updates_assumptions_before_resume(self):
        ctx = AssumptionContext(
            AssumptionRegistry([PlanAssumption("signed_off", "signed", "authorization")]),
            AssumptionDependencyGraph())
        ctx.registry.get("signed_off").transition(AssumptionState.INVALID, timestamp=0)  # gate 'approve'
        goals = [
            Goal("collect", "c", required_capabilities=frozenset({"do"}), expected_outputs=("d",), priority=1),
            Goal("approve", "a", required_capabilities=frozenset({"do"}), dependencies=("collect",),
                 assumptions=("signed_off",), expected_outputs=("ap",), priority=2),
        ]
        eng = WorkflowEngine(_registry())
        wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", goals), WorkingMemory(),
                                 assumption_context=ctx,
                                 wait_conditions=[WaitCondition("w", "approve", event_type=EventType.APPROVAL_RECEIVED)])
        eng.start(wf)
        assert wf.status == WorkflowStatus.WAITING  # gated by wait (assumption still INVALID)
        eng.deliver(WorkflowEvent("e", EventType.APPROVAL_RECEIVED, {}, timestamp=1,
                                  assumption_signals={"signed_off": AssumptionState.SATISFIED}))
        # The event satisfied the assumption via H13, then execution resumed.
        assert ctx.registry.get("signed_off").state == AssumptionState.SATISFIED
        assert wf.tree.lookup("approve").status == GoalStatus.COMPLETED


# ---------------------------------------------------------------------------
# Hierarchical (subtree) resume
# ---------------------------------------------------------------------------
class TestHierarchicalResume:
    def test_only_affected_subtree_resumes(self):
        goals = [
            Goal("a1", "a1", required_capabilities=frozenset({"do"}), expected_outputs=("a",), priority=1),
            Goal("b1", "b1", required_capabilities=frozenset({"do"}), expected_outputs=("b",), priority=2),
        ]
        eng = WorkflowEngine(_registry())
        wf = eng.create_workflow("wf", StaticDecomposer().decompose("m", goals), WorkingMemory(),
                                 wait_conditions=[WaitCondition("wa", "a1", event_type="ev_a"),
                                                  WaitCondition("wb", "b1", event_type="ev_b")])
        eng.start(wf)
        assert {wc.condition_id for wc in wf.waiting_conditions} == {"wa", "wb"}
        # ev_a resumes ONLY a1; b1 stays waiting.
        eng.deliver(WorkflowEvent("ea", "ev_a", {}, timestamp=1))
        assert wf.tree.lookup("a1").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("b1").status == GoalStatus.BLOCKED
        assert wf.status == WorkflowStatus.WAITING
        # ev_b then completes the mission.
        eng.deliver(WorkflowEvent("eb", "ev_b", {}, timestamp=2))
        assert wf.tree.lookup("b1").status == GoalStatus.COMPLETED
        assert wf.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Budget preservation
# ---------------------------------------------------------------------------
class TestBudgetPreservation:
    def test_waiting_consumes_no_budget(self):
        budget = RunBudget(RunBudgetLimits())
        eng, wf = _suspended_workflow(budget=budget)
        at_wait = budget.usage.handoffs
        assert at_wait == 1  # only 'collect' delegated before the wait
        # A wrong event keeps the workflow waiting; budget must not move.
        eng.deliver(WorkflowEvent("bad", EventType.FILE_UPLOADED, {}, timestamp=1))
        assert budget.usage.handoffs == at_wait

    def test_resume_shares_same_budget(self):
        budget = RunBudget(RunBudgetLimits())
        eng, wf = _suspended_workflow(budget=budget)
        at_wait = budget.usage.handoffs
        eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
        # approve + finalize delegated after resume, on the SAME budget.
        assert budget.usage.handoffs == at_wait + 2
        assert wf.run_budget is budget


# ---------------------------------------------------------------------------
# Trace reconstruction & determinism
# ---------------------------------------------------------------------------
class TestTraceAndDeterminism:
    def test_full_lifecycle_reconstructs(self):
        eng, wf = _suspended_workflow()
        eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
        kinds = [e.kind for e in wf.trace.entries]
        # STARTED → WAVE(s) → SUSPENDED → EVENT → RESUMED → WAVE(s) → COMPLETED
        assert kinds[0] == "STARTED"
        assert "SUSPENDED" in kinds and "EVENT" in kinds and "RESUMED" in kinds
        assert kinds[-1] == "COMPLETED"
        # Append-only workflow status history reconstructs the lifecycle.
        statuses = [t.to_status for t in wf.history]
        assert WorkflowStatus.WAITING in statuses and WorkflowStatus.RESUMED in statuses
        assert statuses[-1] == WorkflowStatus.COMPLETED
        assert "Workflow" in format_workflow_trace(wf)

    def test_identical_event_streams_identical_history(self):
        def run():
            eng, wf = _suspended_workflow()
            eng.deliver(WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
            return wf.trace.to_list(), [t.to_dict() for t in wf.history]
        assert run() == run()

    def test_event_routing_only_matching_workflow(self):
        eng = WorkflowEngine(_registry())
        wf_a = eng.create_workflow("A", StaticDecomposer().decompose("mA", _linear_goals()), WorkingMemory(),
                                   wait_conditions=[WaitCondition("wa", "approve", event_type=EventType.APPROVAL_RECEIVED, match=(("doc", "A"),))])
        wf_b = eng.create_workflow("B", StaticDecomposer().decompose("mB", _linear_goals()), WorkingMemory(),
                                   wait_conditions=[WaitCondition("wb", "approve", event_type=EventType.APPROVAL_RECEIVED, match=(("doc", "B"),))])
        eng.start(wf_a)
        eng.start(wf_b)
        # An event for doc A resumes only workflow A.
        eng.deliver(WorkflowEvent("e", EventType.APPROVAL_RECEIVED, {"doc": "A"}, timestamp=1))
        assert wf_a.status == WorkflowStatus.COMPLETED
        assert wf_b.status == WorkflowStatus.WAITING
