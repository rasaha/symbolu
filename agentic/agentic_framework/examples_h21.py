"""
H21 — Deterministic Parallel Goal Execution: runnable example.

Run directly::

    python -m agentic.agentic_framework.examples_h21

Demonstrates:

* two independent goals executing concurrently in one wave;
* a dependent goal released only after the wave durably joins;
* identical committed state under the synchronous and threaded backends
  (the determinism guarantee).

Everything is deterministic and in-process — no API keys, no GPU, no network.
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
    # H21
    ConcurrencyPolicy,
    GoalConcurrency,
    footprint_from_goal,
    ParallelHierarchyExecutor,
    SynchronousBackend,
    ThreadPoolBackend,
    format_parallel_trace,
    format_execution_wave,
)


def _build():
    """A 3-goal mission: A ∥ B independent, C depends on both."""
    registry = CapabilityRegistry()
    registry.register(
        AgentProfile(agent_id="analyst", capabilities=frozenset({"analyze"})),
        ScriptedWorker(WorkerResult(success=True, outputs={"analysis": "OK"})),
    )
    registry.register(
        AgentProfile(agent_id="fetcher", capabilities=frozenset({"fetch"})),
        ScriptedWorker(WorkerResult(success=True, outputs={"data": "rows"})),
    )
    registry.register(
        AgentProfile(agent_id="writer", capabilities=frozenset({"write"})),
        ScriptedWorker(WorkerResult(success=True, outputs={"report": "done"})),
    )
    goals = [
        Goal(goal_id="analyze", description="analyze inputs",
             required_capabilities=frozenset({"analyze"}),
             produced_memory=("analysis",), expected_outputs=("analysis",)),
        Goal(goal_id="fetch", description="fetch data",
             required_capabilities=frozenset({"fetch"}),
             produced_memory=("data",), expected_outputs=("data",)),
        Goal(goal_id="report", description="write report",
             required_capabilities=frozenset({"write"}),
             required_memory=("analysis", "data"),
             produced_memory=("report",), expected_outputs=("report",),
             dependencies=("analyze", "fetch")),
    ]
    plan = StaticDecomposer().decompose("demo", goals)
    footprints = {
        "analyze": footprint_from_goal(goals[0], concurrency=GoalConcurrency.PARALLEL_SAFE),
        "fetch": footprint_from_goal(goals[1], concurrency=GoalConcurrency.PARALLEL_SAFE),
        "report": footprint_from_goal(goals[2], concurrency=GoalConcurrency.PARALLEL_SAFE),
    }
    return registry, plan, footprints


def run(backend) -> WorkingMemory:
    registry, plan, footprints = _build()
    memory = WorkingMemory()
    budget = RunBudget(RunBudgetLimits(max_model_calls=10))
    executor = ParallelHierarchyExecutor(
        registry, memory, run_budget=budget, footprints=footprints,
        concurrency_policy=ConcurrencyPolicy(max_concurrent_goals=4),
        backend=backend, workflow_id="demo-wf",
    )
    result = executor.run(plan)
    print(f"\n### backend = {backend.__class__.__name__}")
    print(f"status            : {result.status}")
    print(f"completed goals   : {result.completed_goals}")
    for wave in result.waves:
        print(format_execution_wave(wave))
    print(format_parallel_trace(result))
    return memory


def main() -> None:
    seq_mem = run(SynchronousBackend())
    par_mem = run(ThreadPoolBackend())

    def state(m):
        return {k: m.peek(k).value for k in sorted(m.keys())}

    print("\n### Determinism check (sequential == parallel)")
    print("sequential:", state(seq_mem))
    print("parallel  :", state(par_mem))
    assert state(seq_mem) == state(par_mem), "backends diverged!"
    print("OK — committed state is identical regardless of execution backend.")


if __name__ == "__main__":
    main()
