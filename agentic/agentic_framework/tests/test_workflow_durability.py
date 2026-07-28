"""
Tests for H18 — Durable Workflow State, Checkpointing & Recovery.

Covers the required scenarios and all 10 evidence requirements:
1. Process-loss recovery (suspend, checkpoint, destroy, restore, event, complete).
2. Equivalent outcome (checkpointed == uninterrupted).
3. No duplicate execution (completed work not re-run).
4. Cross-restart event idempotency.
5. Atomic event recovery (no partially-applied state).
6. Concurrency protection (stale writer conflict).
7. Corruption protection (fail closed).
8. Safe in-flight handling (no unsafe replay).
9. Unchanged lower layers (full regression green — separate).
10. Complete reconstruction (one lifecycle trace).
"""

import dataclasses
import os
import tempfile

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
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
    Goal,
    GoalStatus,
    StaticDecomposer,
    WorkflowEngine,
    WorkflowStatus,
    WaitCondition,
    WorkflowEvent,
    EventType,
    # H18
    DurableWorkflowEngine,
    InMemoryCheckpointStore,
    FileCheckpointStore,
    WorkflowCheckpoint,
    CheckpointSerializer,
    CheckpointIntegrityValidator,
    WorkflowRestorer,
    RecoveryError,
    CheckpointConflict,
    EventOutcome,
    AssignmentRecoveryStatus,
    FaultInjector,
    FaultPoint,
    canonical_json,
)
from agentic.agentic_framework.workflow_durability import _snapshot_workflow_body


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("w", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))
    return r


def _goals():
    return [
        Goal("collect", "collect", required_capabilities=frozenset({"do"}), expected_outputs=("data",), priority=1),
        Goal("finalize", "finalize", required_capabilities=frozenset({"do"}), dependencies=("collect",),
             expected_outputs=("result",), priority=2),
    ]


def _wait():
    return WaitCondition("w1", "finalize", event_type=EventType.APPROVAL_RECEIVED, match=(("doc", "D1"),))


def _event(ts=2, **kw):
    return WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=ts, **kw)


def _det_budget(rb):
    d = rb.usage.to_dict()
    d.pop("elapsed_time", None)  # wall-clock, nondeterministic (H11 semantics)
    return d


def _suspended(store, *, memory=None, budget=None, ctx=None):
    d = DurableWorkflowEngine(_registry(), store)
    wf = d.create_workflow("wf", StaticDecomposer().decompose("m", _goals()),
                           memory or WorkingMemory(), run_budget=budget or RunBudget(RunBudgetLimits()),
                           assumption_context=ctx, wait_conditions=[_wait()])
    return d, wf


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
class TestSerialization:
    def test_deterministic_serialization(self):
        store = InMemoryCheckpointStore()
        _d, wf = _suspended(store)
        assert canonical_json(_snapshot_workflow_body(wf)) == canonical_json(_snapshot_workflow_body(wf))

    def test_checkpoint_digest_round_trip(self):
        store = InMemoryCheckpointStore()
        _d, wf = _suspended(store)
        cp = store.load_latest("wf")
        assert cp.integrity_digest == cp.compute_digest()
        text = CheckpointSerializer().dumps(cp)
        back = CheckpointSerializer().loads(text)
        assert back.compute_digest() == cp.integrity_digest


# ---------------------------------------------------------------------------
# Evidence 1 & 3: process-loss recovery, no duplicate execution
# ---------------------------------------------------------------------------
class TestProcessLossRecovery:
    def test_suspend_destroy_restore_resume(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        assert wf.status == WorkflowStatus.WAITING
        assert wf.tree.lookup("collect").status == GoalStatus.COMPLETED
        del d, wf  # destroy the original runtime

        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        assert wf2.status == WorkflowStatus.WAITING
        assert wf2.tree.lookup("collect").status == GoalStatus.COMPLETED  # preserved
        res = d2.deliver(wf2, _event())
        assert res.outcome == EventOutcome.EVENT_APPLIED
        assert wf2.status == WorkflowStatus.COMPLETED
        assert wf2.tree.lookup("finalize").status == GoalStatus.COMPLETED

    def test_completed_work_not_rerun(self):
        counter = {"collect": 0}

        def worker(c, m):
            if c.goal_id == "collect":
                counter["collect"] += 1
            return WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})

        reg = CapabilityRegistry()
        reg.register(AgentProfile("w", capabilities=frozenset({"do"}), trust_level=5), ScriptedWorker(worker))
        store = InMemoryCheckpointStore()
        d = DurableWorkflowEngine(reg, store)
        d.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                          run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wait()])
        assert counter["collect"] == 1
        # A fresh registry for the restored runtime; collect must not run again.
        reg2 = CapabilityRegistry()
        reg2.register(AgentProfile("w", capabilities=frozenset({"do"}), trust_level=5), ScriptedWorker(worker))
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=reg2)
        d2.deliver(wf2, _event())
        assert counter["collect"] == 1  # not re-run


# ---------------------------------------------------------------------------
# Evidence 2: equivalent outcome
# ---------------------------------------------------------------------------
class TestEquivalence:
    def test_checkpointed_equals_uninterrupted(self):
        # Uninterrupted (plain H17).
        eng = WorkflowEngine(_registry())
        wu = eng.create_workflow("u", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                                 run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wait()])
        eng.start(wu)
        eng.deliver(_event(), to=wu)

        # Checkpointed + restored.
        store = InMemoryCheckpointStore()
        d, _wf = _suspended(store)
        d2, wc = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        d2.deliver(wc, _event())

        assert wu.status == wc.status
        assert {n.goal.goal_id: n.status for n in wu.tree.nodes()} == {n.goal.goal_id: n.status for n in wc.tree.nodes()}
        assert _det_budget(wu.run_budget) == _det_budget(wc.run_budget)
        assert sorted(wu.memory.keys()) == sorted(wc.memory.keys())


# ---------------------------------------------------------------------------
# Evidence 4: cross-restart idempotency
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_duplicate_before_restart_ignored(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        assert d.deliver(wf, _event()).outcome == EventOutcome.EVENT_APPLIED
        assert d.deliver(wf, _event(ts=3)).outcome == EventOutcome.DUPLICATE_EVENT_IGNORED

    def test_duplicate_after_restart_ignored(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        d.deliver(wf, _event())          # applied + checkpointed
        del d, wf
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        # The event id was persisted in the checkpoint → still a duplicate.
        assert d2.deliver(wf2, _event(ts=9)).outcome == EventOutcome.DUPLICATE_EVENT_IGNORED


# ---------------------------------------------------------------------------
# Evidence 5: atomic event recovery
# ---------------------------------------------------------------------------
class TestAtomicity:
    def test_failure_before_commit_leaves_no_partial_state(self):
        store = InMemoryCheckpointStore()
        fault = FaultInjector(FaultPoint.BEFORE_COMMIT)
        d = DurableWorkflowEngine(_registry(), store, fault=fault)
        wf = d.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                               run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wait()])
        pre_latest = store.latest_id("wf")
        with pytest.raises(FaultInjector.InjectedFault):
            d.deliver(wf, _event(memory_writes=[MemoryWrite("note", "x")]))
        # Durable state did not advance.
        assert store.latest_id("wf") == pre_latest
        # Restore from durable state → event was NOT applied, safe to retry.
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        assert wf2.memory.peek("note") is None
        res = d2.deliver(wf2, _event(memory_writes=[MemoryWrite("note", "x")]))
        assert res.outcome == EventOutcome.EVENT_APPLIED
        assert wf2.status == WorkflowStatus.COMPLETED
        assert wf2.memory.peek("note").value == "x"

    @pytest.mark.parametrize("point", [
        FaultPoint.BEFORE_SERIALIZE, FaultPoint.AFTER_SERIALIZE,
        FaultPoint.AFTER_EVENT_EFFECTS, FaultPoint.BEFORE_COMMIT,
    ])
    def test_fault_points_recover_to_valid_state(self, point):
        store = InMemoryCheckpointStore()
        # Reach WAITING cleanly first (no fault during create).
        d0 = DurableWorkflowEngine(_registry(), store)
        d0.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                           run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wait()])
        pre_latest = store.latest_id("wf")
        # Now arm a fault during event delivery.
        d, wf = DurableWorkflowEngine.restore(store, "wf", registry=_registry(),
                                              fault=FaultInjector(point))
        with pytest.raises(FaultInjector.InjectedFault):
            d.deliver(wf, _event())
        # Durable state never advanced past the pre-event checkpoint.
        assert store.latest_id("wf") == pre_latest
        # A clean retry from durable state completes.
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        d2.deliver(wf2, _event())
        assert wf2.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Evidence 6: concurrency protection
# ---------------------------------------------------------------------------
class TestConcurrency:
    def test_stale_writer_conflict(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        parent = store.latest_id("wf")
        base = store.load(parent)
        c1 = dataclasses.replace(base, checkpoint_id="wf#c1", checkpoint_sequence=5,
                                 parent_checkpoint_id=parent).with_digest()
        c2 = dataclasses.replace(base, checkpoint_id="wf#c2", checkpoint_sequence=5,
                                 parent_checkpoint_id=parent).with_digest()
        store.compare_and_save(c1, expected_latest_id=parent)          # first wins
        with pytest.raises(CheckpointConflict):
            store.compare_and_save(c2, expected_latest_id=parent)      # stale loses


# ---------------------------------------------------------------------------
# Evidence 7: corruption protection
# ---------------------------------------------------------------------------
class TestCorruption:
    def test_tampered_content_rejected(self):
        store = InMemoryCheckpointStore()
        _d, _wf = _suspended(store)
        cp = store.load_latest("wf")
        tampered = dataclasses.replace(cp, workflow_id="TAMPERED")  # digest no longer matches
        with pytest.raises(RecoveryError) as ei:
            CheckpointIntegrityValidator().validate(tampered)
        assert ei.value.code == RecoveryError.CHECKPOINT_CORRUPT

    def test_unsupported_schema_rejected(self):
        store = InMemoryCheckpointStore()
        _d, _wf = _suspended(store)
        cp = store.load_latest("wf")
        bad = dataclasses.replace(cp, schema_version=999).with_digest()
        with pytest.raises(RecoveryError) as ei:
            CheckpointIntegrityValidator().validate(bad)
        assert ei.value.code == RecoveryError.CHECKPOINT_SCHEMA_UNSUPPORTED

    def test_dependency_unavailable(self):
        store = InMemoryCheckpointStore()
        _d, _wf = _suspended(store)
        with pytest.raises(RecoveryError) as ei:
            WorkflowRestorer().restore(store.load_latest("wf"), registry=None)
        assert ei.value.code == RecoveryError.RECOVERY_DEPENDENCY_UNAVAILABLE


# ---------------------------------------------------------------------------
# Continuity: budget / memory / assumptions
# ---------------------------------------------------------------------------
class TestContinuity:
    def test_budget_preserved(self):
        store = InMemoryCheckpointStore()
        budget = RunBudget(RunBudgetLimits())
        d, wf = _suspended(store, budget=budget)
        at_wait = _det_budget(budget)
        del d, wf
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        assert _det_budget(wf2.run_budget) == at_wait          # exact restore
        d2.deliver(wf2, _event())
        assert wf2.run_budget.usage.handoffs == 2              # continues from restored counters

    def test_memory_version_continuity(self):
        store = InMemoryCheckpointStore()
        mem = WorkingMemory()
        mem.create("k", 1, timestamp=0)
        mem.update("k", 2, timestamp=1)
        d = DurableWorkflowEngine(_registry(), store)
        d.create_workflow("wf", StaticDecomposer().decompose("m", [
            Goal("a", "a", required_capabilities=frozenset({"do"}), expected_outputs=("x",))]), mem,
            run_budget=RunBudget(RunBudgetLimits()))
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        wf2.memory.update("k", 3, timestamp=2)
        assert [r.version for r in wf2.memory.records("k")] == [1, 2, 3]  # continuous, no duplicate

    def test_assumption_continuity(self):
        ctx = AssumptionContext(AssumptionRegistry([PlanAssumption("a1", "d", "cat")]), AssumptionDependencyGraph())
        ctx.registry.get("a1").transition(AssumptionState.INVALID, timestamp=0)
        store = InMemoryCheckpointStore()
        d = DurableWorkflowEngine(_registry(), store)
        d.create_workflow("wf", StaticDecomposer().decompose("m", [
            Goal("a", "a", required_capabilities=frozenset({"do"}), expected_outputs=("x",))]), WorkingMemory(),
            assumption_context=ctx, run_budget=RunBudget(RunBudgetLimits()))
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        a = wf2.assumption_context.registry.get("a1")
        assert a.state == AssumptionState.INVALID
        assert [(t.from_state, t.to_state) for t in a.history] == [(AssumptionState.VALID, AssumptionState.INVALID)]


# ---------------------------------------------------------------------------
# Hierarchical / coordinator continuity, in-flight
# ---------------------------------------------------------------------------
class TestHierarchyAndInFlight:
    def test_completed_siblings_preserved_only_waiting_subtree_resumes(self):
        goals = [
            Goal("a1", "a1", required_capabilities=frozenset({"do"}), expected_outputs=("a",), priority=1),
            Goal("b1", "b1", required_capabilities=frozenset({"do"}), expected_outputs=("b",), priority=2),
        ]
        store = InMemoryCheckpointStore()
        d = DurableWorkflowEngine(_registry(), store)
        wf = d.create_workflow("wf", StaticDecomposer().decompose("m", goals), WorkingMemory(),
                               run_budget=RunBudget(RunBudgetLimits()),
                               wait_conditions=[WaitCondition("wa", "a1", event_type="ev_a"),
                                                WaitCondition("wb", "b1", event_type="ev_b")])
        d.deliver(wf, WorkflowEvent("ea", "ev_a", {}, timestamp=1))  # a1 done, b1 still waiting
        del d, wf
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        assert wf2.tree.lookup("a1").status == GoalStatus.COMPLETED   # completed sibling preserved
        assert wf2.tree.lookup("b1").status == GoalStatus.BLOCKED
        d2.deliver(wf2, WorkflowEvent("eb", "ev_b", {}, timestamp=2))
        assert wf2.tree.lookup("b1").status == GoalStatus.COMPLETED
        assert wf2.status == WorkflowStatus.COMPLETED

    def test_unknown_in_flight_not_replayed(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        # Simulate a checkpoint captured mid-worker: finalize EXECUTING, no result.
        wf.tree.lookup("finalize").transition(GoalStatus.EXECUTING, reason="sim")
        d.checkpoint(wf, reason="sim_inflight")
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        fin = wf2.tree.lookup("finalize")
        # Not re-run automatically; flagged for reconciliation.
        assert fin.status == GoalStatus.BLOCKED
        assert fin.history[-1].reason == AssignmentRecoveryStatus.REQUIRES_RECONCILIATION

    def test_coordinator_unchanged_assigns_after_recovery(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        del d, wf
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        d2.deliver(wf2, _event())
        # H16 assigned the post-recovery goal to a capability-matched worker.
        assert wf2.tree.lookup("finalize").assigned_agent == "w"


# ---------------------------------------------------------------------------
# Evidence 10: complete reconstruction
# ---------------------------------------------------------------------------
class TestTraceReconstruction:
    def test_single_lifecycle_reconstructs(self):
        store = InMemoryCheckpointStore()
        d, wf = _suspended(store)
        del d, wf
        d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
        d2.deliver(wf2, _event())
        kinds = [e.kind for e in wf2.trace.entries]
        # One trace spans pre-restart and post-restart as a single history.
        for k in ("STARTED", "CHECKPOINTED", "RESTORED", "EVENT", "RESUMED", "COMPLETED"):
            assert k in kinds
        # Completion precedes only the final (post-completion) checkpoint.
        assert kinds.index("COMPLETED") > kinds.index("RESUMED")
        assert kinds[-1] in ("COMPLETED", "CHECKPOINTED")
        assert wf2.status == WorkflowStatus.COMPLETED

    def test_file_store_survives_process_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileCheckpointStore(tmp)
            d = DurableWorkflowEngine(_registry(), store)
            d.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                              run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wait()])
            del d  # destroy runtime; only files remain
            d2, wf2 = DurableWorkflowEngine.restore(store, "wf", registry=_registry())
            d2.deliver(wf2, _event())
            assert wf2.status == WorkflowStatus.COMPLETED
            assert os.path.isdir(os.path.join(tmp, "wf"))
