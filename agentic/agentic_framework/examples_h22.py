"""
H22 — Multi-Workflow Orchestration: runnable reference scenarios.

Run directly::

    python -m agentic.agentic_framework.examples_h22

Scenarios (all deterministic, in-process, no external services):

* A — Priority and fairness (three workflows, equal-priority round-robin)
* B — Dependency chain (A → B → C; dependents release only after durable commit)
* C — Shared budget (workflows compete for one bounded portfolio budget)
* D — Resource contention (two workflows want the same exclusive resource)
* E — Human-review dependency (one waits for review; an unrelated one continues)
* F — Crash and restore (checkpoint mid-orchestration; committed quanta not repeated)
"""

from __future__ import annotations

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
    footprint_from_goal,
    GoalConcurrency,
    BudgetEstimate,
    StaticReviewGate,
    # H22
    WorkflowPortfolio,
    PortfolioWorkflowEntry,
    PortfolioScheduler,
    PortfolioConcurrencyPolicy,
    WorkflowPriority,
    WorkflowDependency,
    DependencyType,
    WorkflowResourceClaim,
    ResourceAccessMode,
    ResourceLedger,
    InMemoryPortfolioStore,
    PortfolioEvent,
    format_portfolio,
)


def _worker():
    return ScriptedWorker(
        lambda contract, memory: WorkerResult(
            success=True, outputs={k: contract.goal_id for k in contract.expected_outputs})
    )


class _ConsumingWorker:
    """H21 ParallelWorker that spends one model-call of its isolated budget,
    so the workflow (and portfolio) accrue real usage."""

    def run(self, context):
        from agentic.agentic_framework import (
            BudgetLedgerEntry, GoalExecutionResult, GoalOutcome, ProposedMemoryWrite,
        )
        b = context.isolated_budget
        used = BudgetLedgerEntry()
        outcome = GoalOutcome.SUCCEEDED
        if b is not None:
            r = b.reserve(model_calls=1)
            if r.ok:
                b.record_usage(prompt_tokens=10, completion_tokens=5)
            else:
                outcome = GoalOutcome.BLOCKED
            used = BudgetLedgerEntry.from_budget(b)
        writes = [ProposedMemoryWrite(key=k, value=context.goal.goal_id, provenance="w",
                                      expected_version=context.memory_view.version_of(k))
                  for k in context.goal.produced_memory] if outcome == GoalOutcome.SUCCEEDED else []
        return GoalExecutionResult(goal_id=context.goal.goal_id, wave_id=context.wave_id,
                                   agent_id="w", outcome=outcome, proposed_memory_writes=writes,
                                   budget_usage=used).with_digest()


def workflow(wid, *, chain=1, gate=None, run_budget=None, consuming=False):
    reg = CapabilityRegistry()
    reg.register(AgentProfile(agent_id=f"ag_{wid}", capabilities=frozenset({"c"})), _worker())
    goals = []
    for i in range(chain):
        deps = (f"{wid}_g{i-1}",) if i > 0 else ()
        goals.append(Goal(goal_id=f"{wid}_g{i}", description=f"{wid}-{i}",
                          required_capabilities=frozenset({"c"}),
                          produced_memory=(f"{wid}_o{i}",), expected_outputs=(f"{wid}_o{i}",),
                          dependencies=deps))
    plan = StaticDecomposer().decompose(wid, goals)
    mem = WorkingMemory()
    fps = {g.goal_id: footprint_from_goal(g, concurrency=GoalConcurrency.PARALLEL_SAFE) for g in goals}
    from agentic.agentic_framework import H21WorkflowController
    return H21WorkflowController(wid, plan, mem, reg, footprints=fps, review_gate=gate,
                                run_budget=run_budget, worker=_ConsumingWorker() if consuming else None)


def scenario_a() -> None:
    print("\n=== Scenario A — priority & fairness ===")
    pf = WorkflowPortfolio("A", concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=1))
    pf.register(PortfolioWorkflowEntry("crit", workflow("crit"), priority=WorkflowPriority.CRITICAL))
    pf.register(PortfolioWorkflowEntry("norm1", workflow("norm1", chain=2), priority=WorkflowPriority.NORMAL))
    pf.register(PortfolioWorkflowEntry("norm2", workflow("norm2", chain=2), priority=WorkflowPriority.NORMAL))
    res = PortfolioScheduler(pf).run()
    order = [e.workflow_id for e in res.trace.entries if e.event == PortfolioEvent.WORKFLOW_SELECTED]
    print("selection order:", order)                    # crit first, then norm1/norm2 interleaved
    print("status:", res.status)


def scenario_b() -> None:
    print("\n=== Scenario B — dependency chain A → B → C ===")
    pf = WorkflowPortfolio("B")
    pf.register(PortfolioWorkflowEntry("A", workflow("A"), output_keys={"A_o0": "outA"}))
    pf.register(PortfolioWorkflowEntry("B", workflow("B"), milestone_keys={"mB": "B_o0"}))
    pf.register(PortfolioWorkflowEntry("C", workflow("C")))
    pf.add_dependency(WorkflowDependency("B", "A", DependencyType.REQUIRES_OUTPUT, output_name="outA"))
    pf.add_dependency(WorkflowDependency("C", "B", DependencyType.REQUIRES_MILESTONE, milestone="mB"))
    res = PortfolioScheduler(pf).run()
    order = [e.workflow_id for e in res.trace.entries if e.event == PortfolioEvent.WORKFLOW_SELECTED]
    print("selection order (A before B before C):", order)
    print("durable output outA:", pf.outputs[("A", "outA")].digest[:12], "...")
    print("status:", res.status)


def scenario_c() -> None:
    print("\n=== Scenario C — shared bounded portfolio budget ===")
    budget = RunBudget(RunBudgetLimits(max_model_calls=2))
    pf = WorkflowPortfolio("C", portfolio_budget=budget,
                           concurrency_policy=PortfolioConcurrencyPolicy(max_concurrent_workflows=4))
    for wid in ("w1", "w2", "w3", "w4"):
        pf.register(PortfolioWorkflowEntry(
            wid, workflow(wid, consuming=True, run_budget=RunBudget(RunBudgetLimits(max_model_calls=100))),
            budget_estimate=BudgetEstimate(model_calls=1, iterations=0, handoffs=0)))
    res = PortfolioScheduler(pf).run()
    print("portfolio model_calls used:", budget.usage.model_calls, "(limit 2 → no oversubscription)")
    print("statuses:", res.workflow_status)  # 2 COMPLETED, 2 WAITING_FOR_BUDGET


def scenario_d() -> None:
    print("\n=== Scenario D — exclusive resource contention ===")
    led = ResourceLedger()
    a_ok = led.try_acquire("A", [WorkflowResourceClaim("gpu", "A", ResourceAccessMode.EXCLUSIVE)])
    b_ok = led.try_acquire("B", [WorkflowResourceClaim("gpu", "B", ResourceAccessMode.EXCLUSIVE)])
    print(f"A acquires gpu exclusively: {a_ok}; B blocked while A holds it: {not b_ok}")
    led.release_all("A")
    b_now = led.try_acquire("B", [WorkflowResourceClaim("gpu", "B", ResourceAccessMode.EXCLUSIVE)])
    print(f"after A releases, B acquires: {b_now}")


def scenario_e() -> None:
    print("\n=== Scenario E — human-review dependency ===")
    gate = StaticReviewGate(review_required=frozenset({"rev_g0"}))
    pf = WorkflowPortfolio("E")
    pf.register(PortfolioWorkflowEntry("rev", workflow("rev", gate=gate)))
    pf.register(PortfolioWorkflowEntry("free", workflow("free")))           # unrelated
    pf.register(PortfolioWorkflowEntry("dep", workflow("dep")))
    pf.add_dependency(WorkflowDependency("dep", "rev", DependencyType.REQUIRES_COMPLETION))
    sched = PortfolioScheduler(pf)
    res = sched.run()
    print("before approval:", res.workflow_status)     # free COMPLETED, rev WAITING_FOR_REVIEW, dep blocked
    gate.approve("rev_g0")
    sched.notify_review_ready("rev")
    res2 = sched.run()
    print("after approval :", res2.workflow_status)     # all COMPLETED


def scenario_f() -> None:
    print("\n=== Scenario F — checkpoint / restore, no repeated quanta ===")
    store = InMemoryPortfolioStore()
    pf = WorkflowPortfolio("F")
    pf.register(PortfolioWorkflowEntry("A", workflow("A", chain=2)))
    sched = PortfolioScheduler(pf, store=store)
    res = sched.run()
    committed = [e for e in res.trace.entries if e.event == PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED]
    print(f"committed quanta: {len(committed)}; latest checkpoint: {store.latest_id('F')}")
    # Restart: re-running an already-complete portfolio repeats no committed work.
    res2 = sched.run()
    committed2 = [e for e in res2.trace.entries if e.event == PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED]
    print(f"after restart, additional committed quanta: {len(committed2) - len(committed)} (expected 0)")


def main() -> None:
    scenario_a()
    scenario_b()
    scenario_c()
    scenario_d()
    scenario_e()
    scenario_f()
    print("\nAll H22 reference scenarios ran without external services.")


if __name__ == "__main__":
    main()
