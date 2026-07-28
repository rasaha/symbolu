"""
Tests for H21 — Deterministic Parallel Goal Execution.

Covers the 24 required scenarios (numbered in the docstrings below) plus the
budget-coordinator concurrency invariant.  Every test is deterministic: where
real threads are used, correctness is asserted on the *committed* state and the
peak concurrency, never on wall-clock timing.

The regression requirement (scenario 24 — all H10–H19 tests pass unchanged) is
verified by running the full ``agentic/agentic_framework/tests`` suite; it is
not re-encoded here.
"""

import threading
import time

import pytest

from agentic.agentic_framework import (
    WorkingMemory,
    RunBudget,
    RunBudgetLimits,
    AgentProfile,
    CapabilityRegistry,
    ScriptedWorker,
    WorkerResult,
    Goal,
    GoalStatus,
    StaticDecomposer,
    # H13
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
)
from agentic.agentic_framework.parallel_execution import (
    # vocabulary
    GoalConcurrency,
    GoalOutcome,
    FailurePolicy,
    MemoryConflictPolicy,
    InFlightStatus,
    ParallelEvent,
    SideEffectClass,
    # policy / footprint
    ConcurrencyPolicy,
    GoalExecutionFootprint,
    footprint_from_goal,
    FootprintConflictDetector,
    # budget
    BudgetEstimate,
    BudgetLedgerEntry,
    SharedBudgetCoordinator,
    # execution
    MemoryView,
    ParallelGoalContext,
    ProposedMemoryWrite,
    ProposedAssumptionTransition,
    GoalExecutionResult,
    CoordinatedParallelWorker,
    # scheduling / review
    StaticReviewGate,
    ParallelGoalScheduler,
    # join
    DeterministicJoiner,
    # backends
    SynchronousBackend,
    ThreadPoolBackend,
    # trace
    ParallelExecutionTrace,
    # durability / recovery
    WaveCheckpoint,
    InMemoryWaveStore,
    WaveRecoveryPlanner,
    # executor
    ParallelHierarchyStatus,
    ParallelHierarchyExecutor,
    derive_execution_state,
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def prof(agent_id, caps=(), perms=(), trust=0, supported=()):
    return AgentProfile(
        agent_id=agent_id,
        capabilities=frozenset(caps),
        permissions=frozenset(perms),
        supported_goals=frozenset(supported),
        trust_level=trust,
    )


def goal(gid, *, caps=(), scope=(), produces=(), requires=(), deps=(),
         priority=0, mandatory=True, assumptions=()):
    return Goal(
        goal_id=gid,
        description=gid,
        required_capabilities=frozenset(caps),
        authority_scope=frozenset(scope),
        produced_memory=tuple(produces),
        required_memory=tuple(requires),
        dependencies=tuple(deps),
        priority=priority,
        mandatory=mandatory,
        assumptions=tuple(assumptions),
        expected_outputs=tuple(produces),
    )


def fp(gid, *, concurrency=GoalConcurrency.PARALLEL_SAFE, reads=(), writes=(),
       assumption_writes=(), assumption_reads=(), agent=None, groups=(),
       resources=None, side_effect=SideEffectClass.DETERMINISTIC):
    return GoalExecutionFootprint(
        goal_id=gid,
        read_memory_keys=frozenset(reads),
        write_memory_keys=frozenset(writes),
        assumption_reads=frozenset(assumption_reads),
        assumption_writes=frozenset(assumption_writes),
        owned_resources=frozenset(resources) if resources is not None else frozenset({gid}),
        assigned_agent=agent,
        exclusive_groups=frozenset(groups),
        side_effect_class=side_effect,
        concurrency=concurrency,
    )


def registry(*specs):
    """specs: (agent_id, caps, worker_result_or_worker, perms)."""
    reg = CapabilityRegistry()
    for spec in specs:
        agent_id, caps, worker = spec[0], spec[1], spec[2]
        perms = spec[3] if len(spec) > 3 else ()
        if isinstance(worker, WorkerResult):
            worker = ScriptedWorker(worker)
        reg.register(prof(agent_id, caps=caps, perms=perms), worker)
    return reg


class BudgetConsumingWorker:
    """Deterministic ParallelWorker that spends its isolated per-goal budget."""

    def __init__(self, outputs_by_goal, *, model_calls=1, prompt=10, completion=5, cost=0.0):
        self.outputs_by_goal = outputs_by_goal
        self.model_calls = model_calls
        self.prompt = prompt
        self.completion = completion
        self.cost = cost

    def run(self, context):
        b = context.isolated_budget
        outcome = GoalOutcome.SUCCEEDED
        used = BudgetLedgerEntry()
        if b is not None:
            for _ in range(self.model_calls):
                r = b.reserve(model_calls=1)
                if not r.ok:
                    outcome = GoalOutcome.BLOCKED
                    break
                b.record_usage(prompt_tokens=self.prompt, completion_tokens=self.completion, cost=self.cost)
            used = BudgetLedgerEntry.from_budget(b)
        writes = []
        if outcome == GoalOutcome.SUCCEEDED:
            for k, v in self.outputs_by_goal.get(context.goal.goal_id, {}).items():
                writes.append(ProposedMemoryWrite(
                    key=k, value=v, provenance="bcw",
                    expected_version=context.memory_view.version_of(k),
                ))
        res = GoalExecutionResult(
            goal_id=context.goal.goal_id, wave_id=context.wave_id, agent_id="bcw",
            outcome=outcome, proposed_memory_writes=writes, budget_usage=used,
        )
        return res.with_digest()


class ReversedSyncBackend:
    """Runs units in *reverse* order (to flip completion order) but keys the
    results by goal id, so the joiner still commits in stable order."""

    def execute(self, units, *, concurrency_limit, cancellation_token):
        results = {}
        for unit in reversed(units):
            results[unit.goal_id] = unit.worker.run(unit.context)
        return results


def make_assumptions(*ids, state=AssumptionState.VALID):
    reg = AssumptionRegistry()
    for aid in ids:
        reg.add(PlanAssumption(assumption_id=aid, description=aid, state=state))
    return AssumptionContext(registry=reg, graph=AssumptionDependencyGraph())


# ===========================================================================
# 1. Independent parallel execution
# ===========================================================================
def test_1_independent_parallel_execution():
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
    ]
    plan = StaticDecomposer().decompose("m1", goals)
    mem = WorkingMemory()
    fps = {g.goal_id: footprint_from_goal(g, concurrency=GoalConcurrency.PARALLEL_SAFE) for g in goals}
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, backend=ThreadPoolBackend())
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert res.completed_goals == ["A", "B"]
    assert len(res.waves) == 1
    assert set(res.waves[0].ordered_goal_ids) == {"A", "B"}
    assert mem.peek("a_out").value == "A"
    assert mem.peek("b_out").value == "B"


# ===========================================================================
# 2. Dependency barrier
# ===========================================================================
def test_2_dependency_barrier():
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
        ("wc", ("cc",), WorkerResult(success=True, outputs={"c_out": "C"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
        goal("C", caps=("cc",), produces=("c_out",), deps=("A", "B")),
    ]
    plan = StaticDecomposer().decompose("m2", goals)
    mem = WorkingMemory()
    fps = {g: fp(g) for g in ("A", "B", "C")}
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, backend=ThreadPoolBackend())
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    # C is only dispatched after A and B have durably joined → its own wave.
    wave_of = {}
    for i, w in enumerate(res.waves):
        for g in w.ordered_goal_ids:
            wave_of[g] = i
    assert wave_of["A"] == wave_of["B"] == 0
    assert wave_of["C"] == 1
    # DEPENDENCY_BARRIER_RELEASED for C fired only after wave 0's join.
    released = [e for e in res.trace.entries if e.event == ParallelEvent.DEPENDENCY_BARRIER_RELEASED]
    assert any(e.goal_id == "C" for e in released)


# ===========================================================================
# 3. Stable scheduling
# ===========================================================================
def _run_indep(backend):
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
        ("wc", ("cc",), WorkerResult(success=True, outputs={"c_out": "C"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",), priority=1),
        goal("B", caps=("cb",), produces=("b_out",), priority=0),
        goal("C", caps=("cc",), produces=("c_out",), priority=2),
    ]
    plan = StaticDecomposer().decompose("m3", goals)
    mem = WorkingMemory()
    fps = {g: fp(g) for g in ("A", "B", "C")}
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, backend=backend)
    return ex.run(plan), mem


def test_3_stable_scheduling():
    r1, _ = _run_indep(SynchronousBackend())
    r2, _ = _run_indep(SynchronousBackend())
    assert r1.waves[0].ordered_goal_ids == r2.waves[0].ordered_goal_ids
    # Ordered by priority: B(0) < A(1) < C(2).
    assert r1.waves[0].ordered_goal_ids == ("B", "A", "C")


# ===========================================================================
# 4. Completion-order independence
# ===========================================================================
def test_4_completion_order_independence():
    forward, mem_f = _run_indep(SynchronousBackend())
    reversed_res, mem_r = _run_indep(ReversedSyncBackend())
    # Committed logical order is the wave's stable order regardless of the
    # order workers actually finished in.
    assert forward.waves[0].result_order == reversed_res.waves[0].result_order == ["B", "A", "C"]
    assert mem_f.snapshot()["keys"].keys() == mem_r.snapshot()["keys"].keys()
    for k in ("a_out", "b_out", "c_out"):
        assert mem_f.peek(k).value == mem_r.peek(k).value


# ===========================================================================
# 5. Concurrency limit
# ===========================================================================
class _PeakTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = 0
        self.peak = 0


class PeakWorker:
    def __init__(self, tracker, hold=0.02):
        self.t = tracker
        self.hold = hold

    def run(self, context):
        with self.t.lock:
            self.t.current += 1
            self.t.peak = max(self.t.peak, self.t.current)
        time.sleep(self.hold)
        with self.t.lock:
            self.t.current -= 1
        return GoalExecutionResult(
            goal_id=context.goal.goal_id, wave_id=context.wave_id, agent_id="p",
            outcome=GoalOutcome.SUCCEEDED,
        ).with_digest()


def test_5_concurrency_limit():
    tracker = _PeakTracker()
    reg = registry(("w", ("c",), WorkerResult(success=True)))
    goals = [goal(f"G{i}", caps=("c",)) for i in range(6)]
    plan = StaticDecomposer().decompose("m5", goals)
    mem = WorkingMemory()
    fps = {g.goal_id: fp(g.goal_id) for g in goals}
    ex = ParallelHierarchyExecutor(
        reg, mem, footprints=fps, backend=ThreadPoolBackend(),
        concurrency_policy=ConcurrencyPolicy(max_concurrent_goals=2),
        worker=PeakWorker(tracker),
    )
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    # All 6 in one wave, but never more than 2 executing at once.
    assert len(res.waves) == 1
    assert len(res.waves[0].ordered_goal_ids) == 6
    assert tracker.peak <= 2
    assert tracker.peak == 2  # the limit is actually exercised


# ===========================================================================
# 6. Shared budget reservation (no oversubscription under concurrency)
# ===========================================================================
def test_6_shared_budget_no_oversubscription():
    budget = RunBudget(RunBudgetLimits(max_model_calls=5))
    coord = SharedBudgetCoordinator(budget)
    oks = []
    oks_lock = threading.Lock()

    def worker(i):
        ok, _res = coord.reserve_wave({f"g{i}": BudgetEstimate(model_calls=1, iterations=0, handoffs=0)})
        with oks_lock:
            oks.append(ok)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly 5 reservations of 1 model-call fit into a budget of 5.
    assert sum(1 for o in oks if o) == 5
    # And the reserved pool never exceeded the limit.
    assert coord.snapshot()["reserved"]["model_calls"] == 5.0


# ===========================================================================
# 7. Budget exhaustion prevents unsafe partial dispatch
# ===========================================================================
def test_7_budget_exhaustion_no_partial_dispatch():
    reg = registry(("w", ("c",), WorkerResult(success=True, outputs={})))
    goals = [goal(f"G{i}", caps=("c",), produces=(f"o{i}",)) for i in range(4)]
    plan = StaticDecomposer().decompose("m7", goals)
    mem = WorkingMemory()
    fps = {g.goal_id: fp(g.goal_id, writes=(f"o{i}",)) for i, g in enumerate(goals)}
    budget = RunBudget(RunBudgetLimits(max_model_calls=2))
    ex = ParallelHierarchyExecutor(
        reg, mem, footprints=fps, run_budget=budget,
        estimates={g.goal_id: BudgetEstimate(model_calls=1, iterations=0, handoffs=0) for g in goals},
        concurrency_policy=ConcurrencyPolicy(max_concurrent_goals=4),
    )
    res = ex.run(plan)
    # 4 goals need 4 model-calls but only 2 remain → the whole wave is blocked,
    # nothing is dispatched or committed.
    assert res.status == ParallelHierarchyStatus.BUDGET_EXHAUSTED
    assert res.completed_goals == []
    assert mem.keys() == []


# ===========================================================================
# 8. Memory conflict detected deterministically (join safety net)
# ===========================================================================
def test_8_memory_conflict_detected():
    mem = WorkingMemory()
    joiner = DeterministicJoiner(mem, conflict_policy=MemoryConflictPolicy.REJECT)
    trace = ParallelExecutionTrace()
    # Two results both writing "k" with the same expected base version 0.
    r1 = GoalExecutionResult("A", "w", "wa", GoalOutcome.SUCCEEDED,
                             proposed_memory_writes=[ProposedMemoryWrite("k", "A", expected_version=0)]).with_digest()
    r2 = GoalExecutionResult("B", "w", "wb", GoalOutcome.SUCCEEDED,
                             proposed_memory_writes=[ProposedMemoryWrite("k", "B", expected_version=0)]).with_digest()
    goals = [goal("A", produces=("k",)), goal("B", produces=("k",))]
    plan = StaticDecomposer().decompose("m8", goals)
    tree = plan.tree
    from agentic.agentic_framework.parallel_execution import ExecutionWave
    wave = ExecutionWave(wave_id="w", workflow_id="wf", ordered_goal_ids=("A", "B"),
                         concurrency_limit=2, created_logical_sequence=0)
    report = joiner.join(wave, {"A": r1, "B": r2}, {}, tree, trace=trace)
    # A commits first (v1); B's expected_version 0 now conflicts → rejected.
    assert report.committed == ["A"]
    assert "B" in report.memory_conflicts and "B" in report.failed
    assert mem.peek("k").value == "A"  # never last-writer-wins
    assert any(e.event == ParallelEvent.MEMORY_CONFLICT_DETECTED for e in trace.entries)


# ===========================================================================
# 9. Assumption conflict — no race-based winner
# ===========================================================================
def test_9_assumption_conflict_no_winner():
    ctx = make_assumptions("X", state=AssumptionState.VALID)
    mem = WorkingMemory()
    joiner = DeterministicJoiner(mem, assumption_context=ctx)
    trace = ParallelExecutionTrace()
    r1 = GoalExecutionResult("A", "w", "wa", GoalOutcome.SUCCEEDED,
                             proposed_assumption_transitions=[
                                 ProposedAssumptionTransition("X", AssumptionState.SATISFIED, expected_prior_state=AssumptionState.VALID)]).with_digest()
    r2 = GoalExecutionResult("B", "w", "wb", GoalOutcome.SUCCEEDED,
                             proposed_assumption_transitions=[
                                 ProposedAssumptionTransition("X", AssumptionState.INVALID, expected_prior_state=AssumptionState.VALID)]).with_digest()
    goals = [goal("A"), goal("B")]
    plan = StaticDecomposer().decompose("m9", goals)
    from agentic.agentic_framework.parallel_execution import ExecutionWave
    wave = ExecutionWave(wave_id="w", workflow_id="wf", ordered_goal_ids=("A", "B"),
                         concurrency_limit=2, created_logical_sequence=0)
    report = joiner.join(wave, {"A": r1, "B": r2}, {}, plan.tree, trace=trace)
    assert "X" in report.assumption_conflicts
    # Neither transition wins — the assumption stays at its prior state.
    assert ctx.registry.get("X").state == AssumptionState.VALID
    assert set(report.failed) == {"A", "B"}
    assert any(e.event == ParallelEvent.ASSUMPTION_CONFLICT_DETECTED for e in trace.entries)


# ===========================================================================
# 10. Serial-only goal executes alone
# ===========================================================================
def test_10_serial_only_executes_alone():
    reg = registry(("w", ("c",), WorkerResult(success=True)))
    goals = [
        goal("S", caps=("c",), priority=0),
        goal("P", caps=("c",), priority=1),
    ]
    plan = StaticDecomposer().decompose("m10", goals)
    mem = WorkingMemory()
    fps = {
        "S": fp("S", concurrency=GoalConcurrency.SERIAL_ONLY),
        "P": fp("P", concurrency=GoalConcurrency.PARALLEL_SAFE),
    }
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps)
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    # S sorts first and runs in a wave by itself.
    assert res.waves[0].ordered_goal_ids == ("S",)


# ===========================================================================
# 11. Exclusive group never overlaps
# ===========================================================================
def test_11_exclusive_group():
    reg = registry(("w", ("c",), WorkerResult(success=True)))
    goals = [goal("G1", caps=("c",), priority=0), goal("G2", caps=("c",), priority=1)]
    plan = StaticDecomposer().decompose("m11", goals)
    mem = WorkingMemory()
    fps = {
        "G1": fp("G1", concurrency=GoalConcurrency.EXCLUSIVE_GROUP, groups=("grp",)),
        "G2": fp("G2", concurrency=GoalConcurrency.EXCLUSIVE_GROUP, groups=("grp",)),
    }
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps)
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    for w in res.waves:
        assert not ({"G1", "G2"} <= set(w.ordered_goal_ids))  # never together


# ===========================================================================
# 12. Per-agent concurrency limit
# ===========================================================================
def test_12_per_agent_concurrency_limit():
    reg = registry(("w", ("c",), WorkerResult(success=True)))
    goals = [goal("G1", caps=("c",), priority=0), goal("G2", caps=("c",), priority=1)]
    plan = StaticDecomposer().decompose("m12", goals)
    mem = WorkingMemory()
    fps = {
        "G1": fp("G1", agent="w"),
        "G2": fp("G2", agent="w"),
    }
    ex = ParallelHierarchyExecutor(
        reg, mem, footprints=fps,
        concurrency_policy=ConcurrencyPolicy(max_concurrent_goals=4, max_concurrent_per_agent=1),
    )
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    # Both bound to the same agent; the per-agent cap forces separate waves.
    for w in res.waves:
        assert len(w.ordered_goal_ids) == 1


# ===========================================================================
# 13. Authority enforcement (independent H16 authorization)
# ===========================================================================
def test_13_authority_enforced_per_worker():
    # Agent lacks the required permission → authorization denies the goal.
    reg = CapabilityRegistry()
    reg.register(prof("w", caps=("c",), perms=()), ScriptedWorker(WorkerResult(success=True, outputs={"o": "X"})))
    goals = [goal("A", caps=("c",), scope=("write",), produces=("o",))]
    plan = StaticDecomposer().decompose("m13", goals)
    mem = WorkingMemory()
    fps = {"A": fp("A")}
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps)
    res = ex.run(plan)
    assert res.status == ParallelHierarchyStatus.MISSION_FAILED
    assert res.failed_goals == ["A"]
    assert mem.keys() == []  # nothing committed for the unauthorized goal

    # With the permission, it is authorized and commits (fresh plan/tree).
    reg2 = CapabilityRegistry()
    reg2.register(prof("w", caps=("c",), perms=("write",)), ScriptedWorker(WorkerResult(success=True, outputs={"o": "X"})))
    mem2 = WorkingMemory()
    plan2 = StaticDecomposer().decompose("m13b", [goal("A", caps=("c",), scope=("write",), produces=("o",))])
    res2 = ParallelHierarchyExecutor(reg2, mem2, footprints=fps).run(plan2)
    assert res2.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert mem2.peek("o").value == "X"


# ===========================================================================
# 14. Isolated failure
# ===========================================================================
def test_14_isolated_failure():
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=False, detail="boom")),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
    ]
    plan = StaticDecomposer().decompose("m14", goals)
    mem = WorkingMemory()
    fps = {"A": fp("A", writes=("a_out",)), "B": fp("B", writes=("b_out",))}
    ex = ParallelHierarchyExecutor(
        reg, mem, footprints=fps,
        concurrency_policy=ConcurrencyPolicy(failure_policy=FailurePolicy.ISOLATE_FAILURE),
    )
    res = ex.run(plan)
    # Independent A commits; only B fails.
    assert "A" in res.completed_goals
    assert res.failed_goals == ["B"]
    assert mem.peek("a_out").value == "A"
    assert mem.peek("b_out") is None


# ===========================================================================
# 15. Fail-fast cancellation
# ===========================================================================
def test_15_fail_fast_cancellation():
    reg = registry(
        ("wf", ("cf",), WorkerResult(success=False, detail="boom")),
        ("wx", ("cx",), WorkerResult(success=True, outputs={"x_out": "X"})),
        ("wy", ("cy",), WorkerResult(success=True, outputs={"y_out": "Y"})),
    )
    goals = [
        goal("F", caps=("cf",), priority=0),           # fails first
        goal("X", caps=("cx",), produces=("x_out",), priority=1),
        goal("Y", caps=("cy",), produces=("y_out",), priority=2),
    ]
    plan = StaticDecomposer().decompose("m15", goals)
    mem = WorkingMemory()
    fps = {"F": fp("F"), "X": fp("X", writes=("x_out",)), "Y": fp("Y", writes=("y_out",))}
    ex = ParallelHierarchyExecutor(
        reg, mem, footprints=fps, backend=SynchronousBackend(),
        concurrency_policy=ConcurrencyPolicy(failure_policy=FailurePolicy.FAIL_FAST),
    )
    res = ex.run(plan)
    w0 = res.waves[0]
    assert "F" in w0.failed_goal_ids
    # F failing cancels the not-yet-started X and Y (scoped to this wave).
    assert set(w0.cancelled_goal_ids) == {"X", "Y"}
    assert any(e.event == ParallelEvent.GOAL_CANCEL_REQUESTED for e in res.trace.entries)


# ===========================================================================
# 16. Localized replanning (only the affected subtree)
# ===========================================================================
def test_16_localized_replanning():
    calls = {"n": 0}

    def replanner(tree, failed_goal_id):
        calls["n"] += 1
        # Replace the failed leaf with a single leaf that will succeed.
        return [goal(f"{failed_goal_id}_r", caps=("cok",), produces=("f_out",))]

    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wfail", ("cf",), WorkerResult(success=False, detail="boom")),
        ("wok", ("cok",), WorkerResult(success=True, outputs={"f_out": "R"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("F", caps=("cf",), produces=("f_out",)),
    ]
    plan = StaticDecomposer().decompose("m16", goals)
    mem = WorkingMemory()
    fps = {"A": fp("A", writes=("a_out",)), "F": fp("F", writes=("f_out",))}
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, subtree_replanner=replanner)
    res = ex.run(plan)
    assert calls["n"] == 1                       # exactly one localized replan
    assert res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert mem.peek("a_out").value == "A"        # sibling untouched
    assert mem.peek("f_out").value == "R"        # replacement committed
    assert tree_status(res.tree, "F") == GoalStatus.ABORTED


def tree_status(tree, gid):
    return tree.lookup(gid).status


# ===========================================================================
# 17. Human review coexistence
# ===========================================================================
def test_17_human_review_coexistence():
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
        ("wc", ("cc",), WorkerResult(success=True, outputs={"c_out": "C"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
        goal("C", caps=("cc",), produces=("c_out",), deps=("A",)),
    ]
    plan = StaticDecomposer().decompose("m17", goals)
    mem = WorkingMemory()
    fps = {g: fp(g) for g in ("A", "B", "C")}
    gate = StaticReviewGate(review_required=frozenset({"A"}))
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, review_gate=gate)

    res1 = ex.run(plan)
    # B proceeds; A held for review; C blocked (depends on A); workflow runnable.
    assert res1.status == ParallelHierarchyStatus.WAITING_FOR_REVIEW
    assert "B" in res1.completed_goals
    assert "A" in res1.review_goals
    assert "C" not in res1.completed_goals
    view = derive_execution_state(res1.tree, review_held=frozenset({"A"}))
    assert "A" in view["waiting_review"]
    assert "B" in view["completed"]

    # Operator approves A → continue: A then C complete.
    gate.approve("A")
    res2 = ex.run(plan)
    assert res2.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert set(res2.completed_goals) == {"A", "B", "C"}


def test_17b_review_rejection_only_affects_subtree():
    reg = registry(
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",), mandatory=False),
        goal("B", caps=("cb",), produces=("b_out",)),
        goal("C", caps=("ca",), produces=("c_out",), deps=("A",), mandatory=False),
    ]
    plan = StaticDecomposer().decompose("m17b", goals)
    mem = WorkingMemory()
    fps = {g: fp(g) for g in ("A", "B", "C")}
    gate = StaticReviewGate(review_required=frozenset({"A"}), rejected={"A": "not allowed"})
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, review_gate=gate)
    res = ex.run(plan)
    # A rejected → A fails, C (dependent) blocked; independent B still commits.
    assert "B" in res.completed_goals
    assert "A" in res.failed_goals
    assert mem.peek("b_out").value == "B"


# ===========================================================================
# 18/19/20/21. Checkpoint + recovery
# ===========================================================================
def _run_with_checkpoints():
    reg = registry(
        ("wa", ("ca",), WorkerResult(success=True, outputs={"a_out": "A"})),
        ("wb", ("cb",), WorkerResult(success=True, outputs={"b_out": "B"})),
    )
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
    ]
    plan = StaticDecomposer().decompose("mrec", goals)
    mem = WorkingMemory()
    fps = {"A": fp("A", writes=("a_out",)), "B": fp("B", writes=("b_out",))}
    store = InMemoryWaveStore()
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, checkpoint_store=store, workflow_id="wfrec")
    res = ex.run(plan)
    return res, store, fps


def test_18_checkpoint_classifies_inflight():
    _res, store, fps = _run_with_checkpoints()
    planner = WaveRecoveryPlanner(ConcurrencyPolicy(), fps)
    joined_ckpt = store.load("wfrec::wave0::joined")
    joined_ckpt.validate()  # fail-closed integrity holds
    classes = planner.classify(joined_ckpt)
    assert classes["A"] == InFlightStatus.JOINED
    assert classes["B"] == InFlightStatus.JOINED
    # A manufactured STARTED_NO_RESULT goal is never auto-replayed (fail-closed).
    started = WaveCheckpoint(
        checkpoint_id="c1", workflow_id="wf", logical_sequence=1,
        wave={"ordered_goal_ids": ["Z"]}, concurrency_policy=ConcurrencyPolicy().to_dict(),
        reservations={}, dispatched_goal_ids=["Z"], results_not_joined={},
        joined_goal_ids=[], memory_versions={}, assumption_versions={},
        cancellation={"cancelled": False}, trace=[],
    ).with_digest()
    assert planner.classify(started)["Z"] == InFlightStatus.STARTED_NO_RESULT
    assert planner.may_replay("Z") is False


def test_19_result_available_not_joined_joins_without_reexec():
    _res, store, _fps = _run_with_checkpoints()
    produced = store.load("wfrec::wave0::results_produced")
    classes = WaveRecoveryPlanner(ConcurrencyPolicy(), _fps).classify(produced)
    assert classes["A"] == InFlightStatus.RESULT_AVAILABLE_NOT_JOINED

    # Rebuild the durable results and join them into fresh state WITHOUT
    # re-running any worker (the joiner never invokes workers).
    results = {gid: GoalExecutionResult.from_dict(d) for gid, d in produced.results_not_joined.items()}
    goals = [goal("A", caps=("ca",), produces=("a_out",)), goal("B", caps=("cb",), produces=("b_out",))]
    plan = StaticDecomposer().decompose("mrec", goals)
    mem = WorkingMemory()
    from agentic.agentic_framework.parallel_execution import ExecutionWave
    wave = ExecutionWave(wave_id="wfrec::wave0", workflow_id="wfrec",
                         ordered_goal_ids=("A", "B"), concurrency_limit=4, created_logical_sequence=0)
    report = DeterministicJoiner(mem).join(wave, results, {}, plan.tree, trace=ParallelExecutionTrace())
    assert set(report.committed) == {"A", "B"}
    assert mem.peek("a_out").value == "A" and mem.peek("b_out").value == "B"


def test_20_joined_goal_never_reexecuted():
    res, store, fps = _run_with_checkpoints()
    joined = store.load("wfrec::wave0::joined")
    assert set(joined.joined_goal_ids) == {"A", "B"}
    # After a joined checkpoint, the tree's goals are terminal; a worker that
    # would explode if called proves they are not re-executed.
    class ExplodingWorker:
        def run(self, context):
            raise AssertionError(f"re-executed joined goal {context.goal.goal_id}")

    goals = [goal("A", caps=("ca",), produces=("a_out",)), goal("B", caps=("cb",), produces=("b_out",))]
    plan = StaticDecomposer().decompose("mrec", goals)
    # Simulate restore: the goals are already COMPLETED in the tree.
    for gid in joined.joined_goal_ids:
        plan.tree.lookup(gid).transition(GoalStatus.COMPLETED, reason="restored")
    reg = registry(("wa", ("ca",), WorkerResult(success=True)), ("wb", ("cb",), WorkerResult(success=True)))
    mem = WorkingMemory()
    ex = ParallelHierarchyExecutor(reg, mem, footprints=fps, worker=ExplodingWorker())
    res2 = ex.run(plan)  # must NOT raise — no ready work remains
    assert res2.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert res2.waves == []


def test_21_duplicate_recovery_idempotent():
    _res, store, _fps = _run_with_checkpoints()
    latest = store.latest_id("wfrec")
    joined = store.load("wfrec::wave0::joined")
    # Re-saving against a stale expected-latest id is refused (fail-closed).
    with pytest.raises(Exception):
        store.compare_and_save(joined, expected_latest_id="something-stale")
    # Loading the same checkpoint repeatedly is idempotent + integrity-checked.
    a = store.load(latest)
    b = store.load(latest)
    assert a.integrity_digest == b.integrity_digest == a.compute_digest()


def test_21b_corrupt_checkpoint_fails_closed():
    _res, store, _fps = _run_with_checkpoints()
    cp = store.load("wfrec::wave0::joined")
    cp.joined_goal_ids = list(cp.joined_goal_ids) + ["tampered"]  # mutate after digest
    from agentic.agentic_framework.workflow_durability import RecoveryError
    with pytest.raises(RecoveryError):
        cp.validate()


# ===========================================================================
# 22. Sequential-parallel equivalence
# ===========================================================================
def _equivalence_run(backend):
    reg = registry(
        ("wa", ("ca",), None),
        ("wb", ("cb",), None),
        ("wc", ("cc",), None),
    )
    # Replace workers with a single deterministic budget-consuming worker.
    goals = [
        goal("A", caps=("ca",), produces=("a_out",)),
        goal("B", caps=("cb",), produces=("b_out",)),
        goal("C", caps=("cc",), produces=("c_out",), deps=("A", "B")),
    ]
    plan = StaticDecomposer().decompose("meq", goals)
    mem = WorkingMemory()
    budget = RunBudget(RunBudgetLimits(max_model_calls=10, max_total_tokens=1000))
    fps = {
        "A": fp("A", writes=("a_out",)),
        "B": fp("B", writes=("b_out",)),
        "C": fp("C", writes=("c_out",), reads=("a_out", "b_out")),
    }
    worker = BudgetConsumingWorker({"A": {"a_out": "A"}, "B": {"b_out": "B"}, "C": {"c_out": "C"}})
    ex = ParallelHierarchyExecutor(
        reg, mem, run_budget=budget, footprints=fps, backend=backend, worker=worker,
        estimates={g: BudgetEstimate(model_calls=1, iterations=0, handoffs=0, prompt_tokens=10, completion_tokens=5)
                   for g in ("A", "B", "C")},
    )
    res = ex.run(plan)
    return res, mem, budget


def test_22_sequential_parallel_equivalence():
    seq_res, seq_mem, seq_budget = _equivalence_run(SynchronousBackend())
    par_res, par_mem, par_budget = _equivalence_run(ThreadPoolBackend())

    assert seq_res.status == par_res.status == ParallelHierarchyStatus.MISSION_COMPLETED
    assert seq_res.completed_goals == par_res.completed_goals
    assert seq_res.failed_goals == par_res.failed_goals
    # Memory records + versions identical.
    for k in ("a_out", "b_out", "c_out"):
        assert seq_mem.peek(k).value == par_mem.peek(k).value
        assert seq_mem.peek(k).version == par_mem.peek(k).version
    # Cumulative deterministic budget counters identical (elapsed_time is
    # wall-clock and explicitly excluded from the equivalence, per §27).
    seq_usage = {k: v for k, v in seq_budget.usage.to_dict().items() if k != "elapsed_time"}
    par_usage = {k: v for k, v in par_budget.usage.to_dict().items() if k != "elapsed_time"}
    assert seq_usage == par_usage
    assert seq_budget.usage.model_calls == 3
    assert seq_budget.usage.total_tokens == 45  # 3 goals × (10 + 5)


# ===========================================================================
# 23. Trace reconstruction
# ===========================================================================
def test_23_trace_reconstruction():
    res, _, _ = _equivalence_run(ThreadPoolBackend())
    events = [e.event for e in res.trace.entries]
    for required in (
        ParallelEvent.WAVE_CREATED,
        ParallelEvent.GOAL_SELECTED_FOR_WAVE,
        ParallelEvent.BUDGET_RESERVED,
        ParallelEvent.GOAL_DISPATCHED,
        ParallelEvent.GOAL_RESULT_PRODUCED,
        ParallelEvent.GOAL_RESULT_JOINED,
        ParallelEvent.DEPENDENCY_BARRIER_RELEASED,
        ParallelEvent.BUDGET_RECONCILED,
        ParallelEvent.WAVE_COMPLETED,
    ):
        assert required in events, f"missing trace event {required}"
    # Logical sequence numbers are strictly increasing (never wall-clock order).
    seqs = [e.seq for e in res.trace.entries]
    assert seqs == sorted(seqs)
    assert seqs == list(range(len(seqs)))


# ===========================================================================
# Extra: footprint conflict detector unit coverage
# ===========================================================================
def test_footprint_conflict_matrix():
    det = FootprintConflictDetector(ConcurrencyPolicy(exclusive_authority_scopes=frozenset({"crit"})))
    ps = lambda gid, **kw: fp(gid, concurrency=GoalConcurrency.PARALLEL_SAFE, **kw)
    # write/write
    assert not det.compatible(ps("A", writes=("k",)), ps("B", writes=("k",)))[0]
    # read/write hazard
    assert not det.compatible(ps("A", writes=("k",)), ps("B", reads=("k",)))[0]
    # assumption hazard
    assert not det.compatible(ps("A", assumption_writes=("x",)), ps("B", assumption_reads=("x",)))[0]
    # owned resource
    assert not det.compatible(ps("A", resources=("r",)), ps("B", resources=("r",)))[0]
    # exclusive authority scope
    a = GoalExecutionFootprint(goal_id="A", authority_scope=frozenset({"crit"}), concurrency=GoalConcurrency.PARALLEL_SAFE, owned_resources=frozenset({"A"}))
    b = GoalExecutionFootprint(goal_id="B", authority_scope=frozenset({"crit"}), concurrency=GoalConcurrency.PARALLEL_SAFE, owned_resources=frozenset({"B"}))
    assert not det.compatible(a, b)[0]
    # UNKNOWN can never pair
    assert not det.compatible(fp("A", concurrency=GoalConcurrency.UNKNOWN), ps("B"))[0]
    # two clean parallel-safe goals are compatible
    assert det.compatible(ps("A", writes=("k1",)), ps("B", writes=("k2",)))[0]
