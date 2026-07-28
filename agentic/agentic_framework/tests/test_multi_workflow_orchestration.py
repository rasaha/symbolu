"""
Tests for H22 — Multi-Workflow Orchestration.

Covers the 43 required scenarios. Scenarios 42–43 (H10–H19 + H21 unchanged;
zero incremental regressions) are verified by running the full
``agentic/agentic_framework/tests`` suite, not re-encoded here.

Determinism: every test asserts on committed portfolio state, selection order,
and trace events — never on wall-clock timing.
"""

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
    StaticDecomposer,
)
from agentic.agentic_framework.parallel_execution import (
    footprint_from_goal,
    GoalConcurrency,
    BudgetEstimate,
    BudgetLedgerEntry,
    GoalExecutionResult,
    GoalOutcome,
    ProposedMemoryWrite,
    StaticReviewGate,
)
from agentic.agentic_framework.multi_workflow_orchestration import (
    PortfolioStatus,
    PortfolioWorkflowStatus,
    WorkflowPriority,
    priority_rank,
    BudgetAllocationPolicy,
    DependencyType,
    DependencyFailurePolicy,
    ResourceAccessMode,
    DeadlockPolicy,
    CancellationScope,
    InFlightWorkflowStatus,
    PortfolioEvent,
    PortfolioConcurrencyPolicy,
    SchedulingPolicy,
    WorkflowDependency,
    DependencyGraph,
    WorkflowResourceClaim,
    ResourceLedger,
    WorkflowOutputRef,
    PortfolioBudgetCoordinator,
    H21WorkflowController,
    PortfolioWorkflowEntry,
    WorkflowPortfolio,
    PortfolioCheckpoint,
    InMemoryPortfolioStore,
    PortfolioScheduler,
)
from agentic.agentic_framework.workflow_durability import RecoveryError, CheckpointConflict


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _callable_worker():
    """A ScriptedWorker that fills each contract's expected outputs with the
    goal id — works for any chain of goals."""
    return ScriptedWorker(
        lambda contract, memory: WorkerResult(
            success=True, outputs={k: contract.goal_id for k in contract.expected_outputs}
        )
    )


class PortfolioBudgetWorker:
    """H21 ParallelWorker that consumes its isolated per-goal budget (so the
    workflow — and thus the portfolio — accrues real usage)."""

    def __init__(self, model_calls=1, prompt=10, completion=5):
        self.model_calls = model_calls
        self.prompt = prompt
        self.completion = completion

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
                b.record_usage(prompt_tokens=self.prompt, completion_tokens=self.completion)
            used = BudgetLedgerEntry.from_budget(b)
        writes = []
        if outcome == GoalOutcome.SUCCEEDED:
            writes = [ProposedMemoryWrite(key=k, value=context.goal.goal_id, provenance="w",
                                          expected_version=context.memory_view.version_of(k))
                      for k in context.goal.produced_memory]
        return GoalExecutionResult(
            goal_id=context.goal.goal_id, wave_id=context.wave_id, agent_id="w",
            outcome=outcome, proposed_memory_writes=writes, budget_usage=used,
        ).with_digest()


def build_workflow(wid, *, chain=1, succeed=True, gate=None, run_budget=None, worker=None):
    """Build an H21WorkflowController with a `chain`-length sequential goal
    chain.  Each goal g{i} produces key '{wid}_o{i}'."""
    reg = CapabilityRegistry()
    if worker is None:
        if succeed:
            worker = _callable_worker()
        else:
            worker = ScriptedWorker(WorkerResult(success=False, detail="boom"))
    reg.register(AgentProfile(agent_id=f"ag_{wid}", capabilities=frozenset({"c"})), worker)
    goals = []
    for i in range(chain):
        deps = (f"{wid}_g{i-1}",) if i > 0 else ()
        goals.append(Goal(
            goal_id=f"{wid}_g{i}", description=f"{wid}-{i}",
            required_capabilities=frozenset({"c"}),
            produced_memory=(f"{wid}_o{i}",), expected_outputs=(f"{wid}_o{i}",),
            dependencies=deps,
        ))
    plan = StaticDecomposer().decompose(wid, goals)
    mem = WorkingMemory()
    fps = {g.goal_id: footprint_from_goal(g, concurrency=GoalConcurrency.PARALLEL_SAFE) for g in goals}
    # Pass the H21 ParallelWorker only when it is a PortfolioBudgetWorker;
    # otherwise let the controller use its CoordinatedParallelWorker over the
    # registered ScriptedWorker.
    h21_worker = worker if isinstance(worker, PortfolioBudgetWorker) else None
    return H21WorkflowController(
        wid, plan, mem, reg, footprints=fps, review_gate=gate, run_budget=run_budget,
        worker=h21_worker,
    )


def entry(wid, controller, **kw):
    return PortfolioWorkflowEntry(workflow_id=wid, controller=controller, **kw)


def selection_order(result):
    return [e.workflow_id for e in result.trace.entries if e.event == PortfolioEvent.WORKFLOW_SELECTED]


# ===========================================================================
# 1. Multiple workflows register
# ===========================================================================
def test_1_multiple_registration():
    pf = WorkflowPortfolio("P")
    for wid in ("A", "B", "C"):
        pf.register(entry(wid, build_workflow(wid)))
    assert [e.workflow_id for e in pf.ordered_entries()] == ["A", "B", "C"]
    assert [e.registration_sequence for e in pf.ordered_entries()] == [0, 1, 2]


# ===========================================================================
# 2. Duplicate registration is idempotent
# ===========================================================================
def test_2_duplicate_registration_idempotent():
    pf = WorkflowPortfolio("P")
    e1 = pf.register(entry("A", build_workflow("A")))
    e2 = pf.register(entry("A", build_workflow("A")))
    assert e1 is e2
    assert len(pf.ordered_entries()) == 1


# ===========================================================================
# 3. Stable selection order
# ===========================================================================
def _priority_portfolio():
    pf = WorkflowPortfolio("P", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1))
    pf.register(entry("B", build_workflow("B"), priority=WorkflowPriority.NORMAL))
    pf.register(entry("A", build_workflow("A"), priority=WorkflowPriority.CRITICAL))
    pf.register(entry("C", build_workflow("C"), priority=WorkflowPriority.LOW))
    return pf


def test_3_stable_selection_order():
    r1 = PortfolioScheduler(_priority_portfolio()).run()
    r2 = PortfolioScheduler(_priority_portfolio()).run()
    assert selection_order(r1) == selection_order(r2)


# ===========================================================================
# 4. Higher priority runs first
# ===========================================================================
def test_4_higher_priority_first():
    res = PortfolioScheduler(_priority_portfolio()).run()
    assert selection_order(res) == ["A", "B", "C"]  # CRITICAL, NORMAL, LOW


# ===========================================================================
# 5. Priority does not bypass a hard dependency
# ===========================================================================
def test_5_priority_does_not_bypass_dependency():
    pf = WorkflowPortfolio("P", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1))
    pf.register(entry("low", build_workflow("low"), priority=WorkflowPriority.LOW))
    pf.register(entry("hi", build_workflow("hi"), priority=WorkflowPriority.CRITICAL))
    # Critical 'hi' depends on low-priority 'low' completing.
    pf.add_dependency(WorkflowDependency("hi", "low", DependencyType.REQUIRES_COMPLETION))
    res = PortfolioScheduler(pf).run()
    order = selection_order(res)
    assert order.index("low") < order.index("hi")  # dependency wins over priority
    assert res.workflow_status == {"low": "COMPLETED", "hi": "COMPLETED"}


# ===========================================================================
# 6. Equal-priority fairness
# ===========================================================================
def test_6_equal_priority_fairness():
    pf = WorkflowPortfolio("P", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1))
    # Two equal-priority multi-quantum workflows.
    pf.register(entry("X", build_workflow("X", chain=2), priority=WorkflowPriority.NORMAL))
    pf.register(entry("Y", build_workflow("Y", chain=2), priority=WorkflowPriority.NORMAL))
    res = PortfolioScheduler(pf).run()
    order = selection_order(res)
    # Fair scheduling interleaves rather than draining one workflow first.
    assert order[:2] == ["X", "Y"] or order[:2] == ["Y", "X"]
    assert order != ["X", "X", "Y", "Y"]
    assert res.status == PortfolioStatus.COMPLETED


# ===========================================================================
# 7. Priority aging prevents starvation
# ===========================================================================
def test_7_priority_aging_prevents_starvation():
    pf = WorkflowPortfolio(
        "P",
        concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1),
        scheduling_policy=SchedulingPolicy(aging_increment=100, aging_cap=300),
    )
    # A long HIGH-priority workflow would otherwise starve the LOW one.
    pf.register(entry("hi", build_workflow("hi", chain=10), priority=WorkflowPriority.HIGH))
    pf.register(entry("lo", build_workflow("lo", chain=1), priority=WorkflowPriority.LOW))
    res = PortfolioScheduler(pf).run()
    order = selection_order(res)
    # Aging lets 'lo' run before 'hi' has drained all 10 of its quanta.
    hi_count_before_lo = order.index("lo")
    assert hi_count_before_lo < 10
    assert any(e.event == PortfolioEvent.PRIORITY_AGED and e.workflow_id == "lo"
               for e in res.trace.entries)
    assert res.status == PortfolioStatus.COMPLETED


# ===========================================================================
# 8. Blocked workflows do not accumulate runnable age
# ===========================================================================
def test_8_blocked_no_runnable_age():
    pf = WorkflowPortfolio("P", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1))
    pf.register(entry("A", build_workflow("A", chain=3), priority=WorkflowPriority.HIGH))
    pf.register(entry("B", build_workflow("B", chain=1), priority=WorkflowPriority.NORMAL))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_COMPLETION))
    sched = PortfolioScheduler(pf)
    # Run a couple of rounds while A works and B waits on the dependency.
    sched.run_round()
    sched.run_round()
    # B is WAITING_FOR_DEPENDENCY and must not have accrued runnable age.
    assert pf.entries["B"].age == 0


# ===========================================================================
# 9. Portfolio concurrency limit enforced
# ===========================================================================
def test_9_concurrency_limit_enforced():
    pf = WorkflowPortfolio("P", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=2))
    for wid in ("A", "B", "C", "D"):
        pf.register(entry(wid, build_workflow(wid)))
    sched = PortfolioScheduler(pf)
    sched.run_round()
    selected_round0 = [e.workflow_id for e in pf.trace.entries
                       if e.event == PortfolioEvent.WORKFLOW_SELECTED and e.detail.get("round") == 0]
    assert len(selected_round0) == 2  # never more than the limit per round


# ===========================================================================
# 10. H21 wave execution remains bounded inside each workflow
# ===========================================================================
def test_10_h21_waves_bounded_within_workflow():
    # Each quantum advances exactly one bounded H21 wave; with max_wave_size=1
    # a workflow of 3 independent goals commits one goal per quantum.
    from agentic.agentic_framework.parallel_execution import ConcurrencyPolicy
    reg = CapabilityRegistry()
    reg.register(AgentProfile(agent_id="w", capabilities=frozenset({"c"})), _callable_worker())
    goals = [Goal(goal_id=f"g{i}", description="g", required_capabilities=frozenset({"c"}),
                  produced_memory=(f"o{i}",), expected_outputs=(f"o{i}",)) for i in range(3)]
    plan = StaticDecomposer().decompose("w", goals)
    mem = WorkingMemory()
    fps = {g.goal_id: footprint_from_goal(g, concurrency=GoalConcurrency.PARALLEL_SAFE) for g in goals}
    ctrl = H21WorkflowController("w", plan, mem, reg, footprints=fps,
                                 concurrency_policy=ConcurrencyPolicy(max_concurrent_goals=1, max_wave_size=1))
    qr = ctrl.advance_quantum()
    assert len(qr.committed_goals) == 1   # H21 wave bounded to one goal
    assert not qr.terminal                # two goals remain for later quanta


# ===========================================================================
# 11. Shared portfolio budget cannot be oversubscribed
# ===========================================================================
def test_11_portfolio_budget_no_oversubscription():
    budget = RunBudget(RunBudgetLimits(max_model_calls=2))
    pf = WorkflowPortfolio("P", portfolio_budget=budget,
                           concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=4))
    for wid in ("A", "B", "C", "D"):
        pf.register(entry(wid, build_workflow(wid, worker=PortfolioBudgetWorker(),
                                              run_budget=RunBudget(RunBudgetLimits(max_model_calls=100))),
                          budget_estimate=BudgetEstimate(model_calls=1, iterations=0, handoffs=0)))
    res = PortfolioScheduler(pf).run()
    # Only 2 model-calls of portfolio budget → exactly 2 workflows run; usage
    # never exceeds the limit.
    assert budget.usage.model_calls == 2
    completed = [w for w, s in res.workflow_status.items() if s == "COMPLETED"]
    waiting = [w for w, s in res.workflow_status.items() if s == "WAITING_FOR_BUDGET"]
    assert len(completed) == 2 and len(waiting) == 2


# ===========================================================================
# 12. Workflow maximum allocation enforced
# ===========================================================================
def test_12_workflow_max_allocation_enforced():
    budget = RunBudget(RunBudgetLimits(max_model_calls=100))
    pf = WorkflowPortfolio("P", portfolio_budget=budget)
    # 'A' needs 3 quanta but is capped at 2 model-calls of allocation.
    pf.register(entry("A", build_workflow("A", chain=3, worker=PortfolioBudgetWorker(),
                                          run_budget=RunBudget(RunBudgetLimits(max_model_calls=100))),
                      budget_estimate=BudgetEstimate(model_calls=1, iterations=0, handoffs=0),
                      max_allocation=BudgetEstimate(model_calls=2, iterations=0, handoffs=0)))
    res = PortfolioScheduler(pf).run()
    assert res.workflow_status["A"] == "FAILED"        # cannot finish within cap
    assert pf.budget.allocated("A")["model_calls"] <= 2.0  # never exceeded the cap


# ===========================================================================
# 13. Budget reservations reconcile after a committed quantum
# ===========================================================================
def test_13_budget_reconcile_after_quantum():
    budget = RunBudget(RunBudgetLimits(max_model_calls=100))
    pf = WorkflowPortfolio("P", portfolio_budget=budget)
    pf.register(entry("A", build_workflow("A", chain=2, worker=PortfolioBudgetWorker(),
                                          run_budget=RunBudget(RunBudgetLimits(max_model_calls=100))),
                      budget_estimate=BudgetEstimate(model_calls=1, iterations=0, handoffs=0)))
    PortfolioScheduler(pf).run()
    # Two quanta each consuming one model-call → reconciled to 2; no reservation leak.
    assert budget.usage.model_calls == 2
    assert pf.budget.snapshot()["reserved"]["model_calls"] == 0.0


# ===========================================================================
# 14. Insufficient budget → WAITING_FOR_BUDGET
# ===========================================================================
def test_14_insufficient_budget_waits():
    budget = RunBudget(RunBudgetLimits(max_model_calls=0))
    pf = WorkflowPortfolio("P", portfolio_budget=budget)
    pf.register(entry("A", build_workflow("A", worker=PortfolioBudgetWorker(),
                                          run_budget=RunBudget(RunBudgetLimits(max_model_calls=100))),
                      budget_estimate=BudgetEstimate(model_calls=1, iterations=0, handoffs=0)))
    res = PortfolioScheduler(pf).run()
    assert res.workflow_status["A"] == "WAITING_FOR_BUDGET"
    assert any(e.event == PortfolioEvent.WORKFLOW_WAITING_FOR_BUDGET for e in res.trace.entries)


# ===========================================================================
# 15. REQUIRES_COMPLETION dependency
# ===========================================================================
def test_15_requires_completion():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A")))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_COMPLETION))
    res = PortfolioScheduler(pf).run()
    order = selection_order(res)
    assert order.index("A") < order.index("B")
    assert res.status == PortfolioStatus.COMPLETED


# ===========================================================================
# 16. REQUIRES_SUCCESS dependency
# ===========================================================================
def test_16_requires_success():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", succeed=False)))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS))
    res = PortfolioScheduler(pf).run()
    # A fails → B's REQUIRES_SUCCESS dependency fails → B blocked (default policy).
    assert res.workflow_status["A"] == "FAILED"
    assert res.workflow_status["B"] == "BLOCKED"


# ===========================================================================
# 17. Milestone dependency
# ===========================================================================
def test_17_milestone_dependency():
    a = build_workflow("A", chain=2)
    pf = WorkflowPortfolio("P")
    ea = entry("A", a, milestone_keys={"M1": "A_o0"})  # milestone = first goal's output
    pf.register(ea)
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_MILESTONE, milestone="M1"))
    res = PortfolioScheduler(pf).run()
    assert res.status == PortfolioStatus.COMPLETED
    assert a.milestone_reached("A_o0")
    assert res.workflow_status["B"] == "COMPLETED"


# ===========================================================================
# 18. Output dependency uses a durable WorkflowOutputRef
# ===========================================================================
def test_18_output_dependency_durable_ref():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A"), output_keys={"A_o0": "O"}))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_OUTPUT, output_name="O"))
    res = PortfolioScheduler(pf).run()
    assert res.status == PortfolioStatus.COMPLETED
    ref = pf.outputs[("A", "O")]
    assert isinstance(ref, WorkflowOutputRef) and ref.available and ref.digest
    assert res.workflow_status["B"] == "COMPLETED"


# ===========================================================================
# 19. Dependency cycles are rejected
# ===========================================================================
def test_19_dependency_cycle_rejected():
    g = DependencyGraph()
    g.add(WorkflowDependency("B", "A"))
    g.add(WorkflowDependency("C", "B"))
    with pytest.raises(ValueError):
        g.add(WorkflowDependency("A", "C"))  # closes a cycle A→C→B→A


# ===========================================================================
# 20. Dependency failure blocks or cancels per policy
# ===========================================================================
def test_20_dependency_failure_policies():
    # BLOCK_DEPENDENT
    pf = WorkflowPortfolio("P", scheduling_policy=SchedulingPolicy(
        dependency_failure_policy=DependencyFailurePolicy.BLOCK_DEPENDENT))
    pf.register(entry("A", build_workflow("A", succeed=False)))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS))
    res = PortfolioScheduler(pf).run()
    assert res.workflow_status["B"] == "BLOCKED"

    # CANCEL_DEPENDENT
    pf2 = WorkflowPortfolio("P2", scheduling_policy=SchedulingPolicy(
        dependency_failure_policy=DependencyFailurePolicy.CANCEL_DEPENDENT))
    pf2.register(entry("A", build_workflow("A", succeed=False)))
    pf2.register(entry("B", build_workflow("B")))
    pf2.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS))
    res2 = PortfolioScheduler(pf2).run()
    assert res2.workflow_status["B"] == "CANCELLED"


# ===========================================================================
# 21. Independent workflows continue after one fails
# ===========================================================================
def test_21_failure_isolation():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", succeed=False)))
    pf.register(entry("B", build_workflow("B")))
    res = PortfolioScheduler(pf).run()
    assert res.workflow_status["A"] == "FAILED"
    assert res.workflow_status["B"] == "COMPLETED"
    assert res.status == PortfolioStatus.COMPLETED  # portfolio not failed (isolated)


# ===========================================================================
# 22–26. Resource contention + atomic acquisition
# ===========================================================================
def _claim(rk, wid, mode):
    return WorkflowResourceClaim(resource_key=rk, workflow_id=wid, access_mode=mode)


def test_22_read_read_coexist():
    led = ResourceLedger()
    assert led.try_acquire("A", [_claim("R", "A", ResourceAccessMode.READ)])
    assert led.try_acquire("B", [_claim("R", "B", ResourceAccessMode.READ)])


def test_23_write_conflicts_read_and_write():
    led = ResourceLedger()
    assert led.try_acquire("A", [_claim("R", "A", ResourceAccessMode.WRITE)])
    assert not led.try_acquire("B", [_claim("R", "B", ResourceAccessMode.READ)])
    assert not led.try_acquire("C", [_claim("R", "C", ResourceAccessMode.WRITE)])


def test_24_exclusive_blocks_all():
    led = ResourceLedger()
    assert led.try_acquire("A", [_claim("R", "A", ResourceAccessMode.EXCLUSIVE)])
    assert not led.try_acquire("B", [_claim("R", "B", ResourceAccessMode.READ)])


def test_25_unknown_fails_closed():
    led = ResourceLedger()
    assert led.try_acquire("A", [_claim("R", "A", ResourceAccessMode.UNKNOWN)])
    assert not led.try_acquire("B", [_claim("R", "B", ResourceAccessMode.READ)])
    # And UNKNOWN cannot join an existing READ either.
    led2 = ResourceLedger()
    assert led2.try_acquire("A", [_claim("R", "A", ResourceAccessMode.READ)])
    assert not led2.try_acquire("B", [_claim("R", "B", ResourceAccessMode.UNKNOWN)])


def test_26_atomic_multi_resource_no_partial():
    led = ResourceLedger()
    led.try_acquire("B", [_claim("R2", "B", ResourceAccessMode.WRITE)])
    # A wants both R1 and R2; R2 is blocked → A gets NEITHER (no partial claim).
    ok = led.try_acquire("A", [_claim("R1", "A", ResourceAccessMode.WRITE),
                               _claim("R2", "A", ResourceAccessMode.WRITE)])
    assert ok is False
    assert "A" not in led.holders("R1")
    assert "A" not in led.holders("R2")


# ===========================================================================
# 27–28. Deadlock detection + policy
# ===========================================================================
def _deadlock_scheduler():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A"),
                      resource_claims=(_claim("R2", "A", ResourceAccessMode.EXCLUSIVE),)))
    pf.register(entry("B", build_workflow("B"),
                      resource_claims=(_claim("R1", "B", ResourceAccessMode.EXCLUSIVE),)))
    sched = PortfolioScheduler(pf)
    # Manufacture a hold-and-wait cycle: A holds R1, B holds R2, each wants the
    # other's resource.
    pf.resources.try_acquire("A", [_claim("R1", "A", ResourceAccessMode.EXCLUSIVE)])
    pf.resources.try_acquire("B", [_claim("R2", "B", ResourceAccessMode.EXCLUSIVE)])
    return pf, sched


def test_27_deadlock_detected():
    pf, sched = _deadlock_scheduler()
    waiters = pf.ordered_entries()
    graph = sched._wait_for_graph(waiters)
    cycle = sched._find_cycle(graph)
    assert cycle is not None and set(cycle) >= {"A", "B"}


def test_28_deadlock_pauses_youngest():
    pf, sched = _deadlock_scheduler()  # default policy = PAUSE_YOUNGEST
    sched._resolve_deadlock(["A", "B", "A"])
    # B has the higher registration sequence → it is the youngest and is paused.
    assert pf.entries["B"].status == PortfolioWorkflowStatus.PAUSED
    assert pf.entries["A"].status != PortfolioWorkflowStatus.PAUSED


# ===========================================================================
# 29. Paused workflow resumes from a safe boundary
# ===========================================================================
def test_29_pause_resume():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", chain=2)))
    sched = PortfolioScheduler(pf)
    sched.pause("A")
    sched.run_round()
    assert pf.entries["A"].status == PortfolioWorkflowStatus.PAUSED
    assert not any(e.event == PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED for e in pf.trace.entries)
    sched.resume("A")
    res = sched.run()
    assert res.workflow_status["A"] == "COMPLETED"


# ===========================================================================
# 30. One workflow waiting for review does not block others
# ===========================================================================
def test_30_review_does_not_block_others():
    gate = StaticReviewGate(review_required=frozenset({"A_g0"}))
    a = build_workflow("A", gate=gate)
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", a))
    pf.register(entry("B", build_workflow("B")))                       # independent
    pf.register(entry("C", build_workflow("C")))
    pf.add_dependency(WorkflowDependency("C", "A", DependencyType.REQUIRES_COMPLETION))
    sched = PortfolioScheduler(pf)
    res = sched.run()
    assert res.workflow_status["B"] == "COMPLETED"                     # unrelated advances
    assert res.workflow_status["A"] == "WAITING_FOR_REVIEW"            # A held
    assert res.workflow_status["C"] in ("WAITING_FOR_DEPENDENCY", "BLOCKED")  # C blocked

    # Approve A → A and C complete.
    gate.approve("A_g0")
    sched.notify_review_ready("A")
    res2 = sched.run()
    assert res2.workflow_status["A"] == "COMPLETED"
    assert res2.workflow_status["C"] == "COMPLETED"


# ===========================================================================
# 31. Dependency on human approval blocked until durable resolution
# ===========================================================================
def test_31_review_decision_dependency():
    pf = WorkflowPortfolio("P")
    ea = entry("A", build_workflow("A"))
    pf.register(ea)
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_REVIEW_DECISION, review_key="d1"))
    sched = PortfolioScheduler(pf)
    res = sched.run()
    # A completes but the human decision 'd1' is not yet recorded → B waits.
    assert res.workflow_status["A"] == "COMPLETED"
    assert res.workflow_status["B"] in ("WAITING_FOR_DEPENDENCY", "REGISTERED")
    # Durable human resolution arrives → B proceeds.
    ea.review_decisions["d1"] = True
    res2 = sched.run()
    assert res2.workflow_status["B"] == "COMPLETED"


# ===========================================================================
# 32–34. Cancellation scopes
# ===========================================================================
def test_32_workflow_only_cancellation():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", chain=3)))
    pf.register(entry("B", build_workflow("B")))
    sched = PortfolioScheduler(pf)
    sched.cancel("A", scope=CancellationScope.WORKFLOW_ONLY, reason="stop A")
    res = sched.run()
    assert res.workflow_status["A"] == "CANCELLED"
    assert res.workflow_status["B"] == "COMPLETED"


def test_33_dependent_subgraph_cancellation():
    pf = WorkflowPortfolio("P")
    for wid in ("A", "B", "C", "D"):
        pf.register(entry(wid, build_workflow(wid)))
    pf.add_dependency(WorkflowDependency("B", "A"))
    pf.add_dependency(WorkflowDependency("C", "B"))
    sched = PortfolioScheduler(pf)
    sched.cancel("A", scope=CancellationScope.DEPENDENT_SUBGRAPH, reason="kill chain")
    res = sched.run()
    assert res.workflow_status["A"] == "CANCELLED"
    assert res.workflow_status["B"] == "CANCELLED"
    assert res.workflow_status["C"] == "CANCELLED"
    assert res.workflow_status["D"] == "COMPLETED"  # independent survives


def test_34_portfolio_all_cancellation_idempotent():
    pf = WorkflowPortfolio("P")
    for wid in ("A", "B"):
        pf.register(entry(wid, build_workflow(wid)))
    sched = PortfolioScheduler(pf)
    sched.cancel("A", scope=CancellationScope.PORTFOLIO_ALL, reason="halt")
    sched.cancel("A", scope=CancellationScope.PORTFOLIO_ALL, reason="halt")  # idempotent
    assert pf.entries["A"].status == "CANCELLED"
    assert pf.entries["B"].status == "CANCELLED"


# ===========================================================================
# 35. Cross-workflow mutable memory not shared directly
# ===========================================================================
def test_35_memory_isolation():
    a = build_workflow("A")
    b = build_workflow("B")
    assert a.memory is not b.memory
    PortfolioScheduler(_two_workflow_portfolio(a, b)).run()
    # A's committed keys live only in A's memory namespace, never B's.
    assert "A_o0" in a.memory.keys()
    assert "A_o0" not in b.memory.keys()


def _two_workflow_portfolio(a, b):
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", a))
    pf.register(entry("B", b))
    return pf


# ===========================================================================
# 36. Portfolio checkpoint restores priorities, budgets, deps, claims, fairness
# ===========================================================================
def test_36_checkpoint_body():
    budget = RunBudget(RunBudgetLimits(max_model_calls=100))
    store = InMemoryPortfolioStore()
    pf = WorkflowPortfolio("P", portfolio_budget=budget)
    pf.register(entry("A", build_workflow("A", chain=2), priority=WorkflowPriority.HIGH,
                      resource_claims=(_claim("R", "A", ResourceAccessMode.READ),)))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A"))
    PortfolioScheduler(pf, store=store).run()
    cp = store.load_latest("P")
    cp.validate()
    body = cp.body
    assert body["workflows"][0]["priority"] == "HIGH"
    assert body["dependencies"] and body["dependencies"][0]["predecessor"] == "A"
    assert "budget" in body and body["budget"]["budget"] is not None
    assert any("age" in w and "deficit" in w for w in body["workflows"])       # fairness state
    assert body["workflows"][0]["resource_claims"]                             # claims persisted


# ===========================================================================
# 37. Committed workflow quantum not repeated after restart
# ===========================================================================
def test_37_committed_quantum_not_repeated():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", chain=2)))
    sched = PortfolioScheduler(pf)
    res = sched.run()
    assert res.workflow_status["A"] == "COMPLETED"
    committed = [e for e in res.trace.entries if e.event == PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED]
    # Re-running after completion repeats no work (all terminal → 0 new quanta).
    res2 = sched.run()
    committed2 = [e for e in res2.trace.entries if e.event == PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED]
    assert len(committed2) == len(committed)  # nothing new committed on restart


# ===========================================================================
# 38. Interrupted workflow delegates recovery to H18/H21 fail-closed semantics
# ===========================================================================
def test_38_inflight_classification():
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A", chain=3)))
    pf.register(entry("B", build_workflow("B")))
    pf.add_dependency(WorkflowDependency("B", "A"))
    sched = PortfolioScheduler(pf)
    sched.run_round()  # A advances one quantum, B waits
    classes = sched.classify_in_flight()
    assert classes["B"] == InFlightWorkflowStatus.WAITING
    # A is mid-flight (not terminal) → recovery is delegated, never assumed done.
    assert classes["A"] in (InFlightWorkflowStatus.NOT_GRANTED, InFlightWorkflowStatus.WAITING,
                            InFlightWorkflowStatus.RUNNING_NO_COMMIT)


# ===========================================================================
# 39. Repeated portfolio recovery is idempotent
# ===========================================================================
def test_39_recovery_idempotent():
    store = InMemoryPortfolioStore()
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A")))
    PortfolioScheduler(pf, store=store).run()
    latest = store.latest_id("P")
    a = store.load(latest)
    b = store.load(latest)
    assert a.integrity_digest == b.integrity_digest == a.compute_digest()
    with pytest.raises(CheckpointConflict):
        store.compare_and_save(a, expected_latest_id="stale")


# ===========================================================================
# 40. Corrupt portfolio checkpoint fails closed
# ===========================================================================
def test_40_corrupt_checkpoint_fails_closed():
    store = InMemoryPortfolioStore()
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A")))
    PortfolioScheduler(pf, store=store).run()
    # Deep-copy so the store's live checkpoint is not corrupted by the mutation.
    import copy
    cp = PortfolioCheckpoint.from_dict(copy.deepcopy(store.load_latest("P").to_dict()))
    cp.body["tampered"] = True  # mutate after the digest was computed
    with pytest.raises(RecoveryError):
        cp.validate()
    # Portfolio/workflow checkpoint disagreement also fails closed.
    cp2 = store.load_latest("P")
    with pytest.raises(RecoveryError):
        cp2.validate(workflow_digests={"A": "not-the-recorded-digest"})


# ===========================================================================
# 41. Portfolio trace reconstructs scheduling and recovery
# ===========================================================================
def test_41_trace_reconstruction():
    store = InMemoryPortfolioStore()
    pf = WorkflowPortfolio("P")
    pf.register(entry("A", build_workflow("A")))
    pf.register(entry("B", build_workflow("B")))
    res = PortfolioScheduler(pf, store=store).run()
    events = [e.event for e in res.trace.entries]
    for required in (
        PortfolioEvent.PORTFOLIO_CREATED,
        PortfolioEvent.WORKFLOW_REGISTERED,
        PortfolioEvent.WORKFLOW_SELECTED,
        PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED,
        PortfolioEvent.WORKFLOW_COMPLETED,
        PortfolioEvent.PORTFOLIO_CHECKPOINTED,
        PortfolioEvent.PORTFOLIO_COMPLETED,
    ):
        assert required in events, f"missing portfolio event {required}"
    seqs = [e.seq for e in res.trace.entries]
    assert seqs == list(range(len(seqs)))  # strictly increasing logical sequence


# ===========================================================================
# Extra unit coverage
# ===========================================================================
def test_priority_rank_and_effective_rank():
    assert priority_rank(WorkflowPriority.CRITICAL) < priority_rank(WorkflowPriority.BACKGROUND)
    e = PortfolioWorkflowEntry("w", controller=build_workflow("w"), priority=WorkflowPriority.CRITICAL)
    e.age = 1000
    assert e.effective_rank(500) == 0  # CRITICAL never ages
    e2 = PortfolioWorkflowEntry("w2", controller=build_workflow("w2"), priority=WorkflowPriority.BACKGROUND)
    e2.age = 10000
    assert e2.effective_rank(500) >= 1  # non-critical never reaches rank 0


def test_budget_coordinator_no_double_reservation():
    budget = RunBudget(RunBudgetLimits(max_model_calls=3))
    coord = PortfolioBudgetCoordinator(budget)
    est = BudgetEstimate(model_calls=1, iterations=0, handoffs=0)
    assert coord.reserve_quantum("A", est)[0]
    assert coord.reserve_quantum("B", est)[0]
    assert coord.reserve_quantum("C", est)[0]
    # 4th exceeds the portfolio budget of 3.
    ok, kind, _dim = coord.reserve_quantum("D", est)
    assert not ok and kind == "PORTFOLIO_BUDGET"
