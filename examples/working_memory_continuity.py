#!/usr/bin/env python3
"""
Governed Working Memory & State Continuity (H14)
================================================

Run-scoped governed memory that autonomous workflows use to retain, update,
retrieve, and expire execution state across iterations, replanning, and agent
handoffs. State continuity — not long-term learning.

Demonstrates:

  1. The SAME observation produces DIFFERENT valid outcomes because of
     previously stored workflow state (customer tier).
  2. Updates create NEW immutable versions — history is never lost.
  3. Sequential agents share ONE WorkingMemory (no copies).
  4. Invalidating a memory record propagates to a dependent H13 assumption,
     preserving history.

No API key, no GPU — deterministic mock adapters and scripted observations.
All execution runs under the shared H11 RunBudget.

Run:
    python examples/working_memory_continuity.py
"""

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    Plan,
    PlanStep,
    ObservationStatus,
    ScriptedObservationBuilder,
    ReplanningRunner,
    RuleBasedReplanner,
    # H13
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    build_assumption_aware_runner,
    # H14
    WorkingMemory,
    MemoryObservation,
    MemoryWrite,
    MemoryAwareObservationBuilder,
    MemoryAssumptionBridge,
    format_working_memory,
    format_memory_trace,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _agent():
    a = build_agent(
        adapter=MockLLMAdapter(default_response="ok"),
        use_llm_for_decomposition=False,
        max_revisions=0,
    )
    a.safety_gate = SafetyGate(SafetyContractEvaluator(0.0, 0.0, 1.0, 0.0))
    return a


def demo_state_drives_outcome():
    print("=" * 66)
    print("Same observation, different STORED STATE → different outcome")
    print("=" * 66)

    def run(tier):
        mem = WorkingMemory()
        mem.create("customer_tier", tier, category="profile", timestamp=0)

        plan = Plan.from_steps("assess an application", [
            PlanStep("assess", "assess risk", "assess"),
            PlanStep("decide", "decide", "decide", metadata={"memory": {"requires": ["customer_tier"]}}),
        ])

        # The revision branch is chosen by reading working memory.
        def repair(pl, obs):
            rec = mem.peek("customer_tier")
            branch = "manual_review" if rec and rec.value == "premium" else "auto_reject"
            return [PlanStep(branch, branch, "do " + branch)] + list(pl.future)

        # Identical observation stream in both runs: step 0 reports high risk.
        obs = [
            MemoryObservation(status=ObservationStatus.FAILURE, summary="risk score high", goal_progress=0.0),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        builder = MemoryAwareObservationBuilder(mem, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder,
                             replanner=RuleBasedReplanner(repair), max_iterations=6).run(plan.goal, plan)
        return [s.step_id for s in r.plan.completed_steps()], mem

    premium_path, _ = run("premium")
    standard_path, _ = run("standard")
    print(f"\n  premium customer → {premium_path}")
    print(f"  standard customer → {standard_path}")
    print(f"\n  same observation, different stored tier → different execution: "
          f"{premium_path != standard_path}")


def demo_versioning():
    print("\n" + "=" * 66)
    print("Updates create new versions — history is never lost")
    print("=" * 66)
    m = WorkingMemory()
    m.create("risk_score", 0.8, category="score", producing_step="v1_model", timestamp=0)
    m.update("risk_score", 0.5, producing_step="v2_model", timestamp=1)
    m.update("risk_score", 0.3, producing_step="v3_model", timestamp=2)
    print("\n  retrieve() returns the current active version:",
          m.retrieve("risk_score", now=3).value)
    print("\n" + format_working_memory(m))


def demo_cross_agent():
    print("\n" + "=" * 66)
    print("Sequential agents share ONE WorkingMemory (no copies)")
    print("=" * 66)
    shared = WorkingMemory()

    # Agent A produces a dataset.
    plan_a = Plan.from_steps("gather", [
        PlanStep("gather", "gather data", "do", metadata={"memory": {"produces": ["dataset"]}})])
    ba = MemoryAwareObservationBuilder(shared, ScriptedObservationBuilder([
        MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0,
                          memory_writes=[MemoryWrite("dataset", {"rows": 1000})])]))
    ReplanningRunner(_agent(), observation_builder=ba, max_iterations=3).run("gather", plan_a)

    # Agent B consumes it, produces a report — same store.
    plan_b = Plan.from_steps("report", [
        PlanStep("report", "write report", "do",
                 metadata={"memory": {"requires": ["dataset"], "produces": ["report"]}})])
    bb = MemoryAwareObservationBuilder(shared, ScriptedObservationBuilder([
        MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0,
                          memory_writes=[MemoryWrite("report", "summary.pdf")])]))
    ReplanningRunner(_agent(), observation_builder=bb, max_iterations=3).run("report", plan_b)

    ds = shared.peek("dataset")
    print(f"\n  dataset produced by '{ds.producing_step}', consumed by {ds.consuming_steps}")
    print(f"  report now in the SAME store: {shared.peek('report').value}")
    print(f"  keys held by the one shared memory: {shared.keys()}")


def demo_assumption_bridge():
    print("\n" + "=" * 66)
    print("Invalid memory propagates to a dependent assumption (H13)")
    print("=" * 66)
    plan = Plan.from_steps("g", [
        PlanStep("health_check", "check source", "do"),
        PlanStep("train", "train model", "do", metadata={"assumptions": ["dataset_valid"]}),
    ])
    ctx = AssumptionContext(
        AssumptionRegistry([PlanAssumption("dataset_valid", "dataset is valid", "data",
                                           mandatory=True, recoverable=False)]),
        AssumptionDependencyGraph.from_plan(plan),
    )
    mem = WorkingMemory()
    mem.create("dataset", {"rows": 1000}, timestamp=0)
    MemoryAssumptionBridge(mem, ctx, links={"dataset": ["dataset_valid"]})

    obs = [MemoryObservation(status=ObservationStatus.SUCCESS, summary="source corrupted",
                             goal_progress=0.3, memory_invalidations=["dataset"])]
    builder = MemoryAwareObservationBuilder(mem, ScriptedObservationBuilder(obs))
    r = build_assumption_aware_runner(_agent(), ctx, observation_builder=builder).run("g", plan)

    print(f"\n  memory 'dataset' state:   {mem.records('dataset')[0].status}")
    print(f"  assumption 'dataset_valid': {ctx.registry.get('dataset_valid').state}")
    print(f"  workflow outcome:         {r.stop_reason}")
    print(f"  assumption history kept:  "
          f"{[(t.from_state, t.to_state) for t in ctx.registry.get('dataset_valid').history]}")
    print("\n" + format_memory_trace(mem))


def main():
    demo_state_drives_outcome()
    demo_versioning()
    demo_cross_agent()
    demo_assumption_bridge()
    print(
        "\nKey properties demonstrated:\n"
        "  • Stored workflow state changes execution outcomes.\n"
        "  • Updates version; prior records remain reconstructable.\n"
        "  • Sequential agents share one governed memory, no duplication.\n"
        "  • Memory invalidation propagates to assumptions, history preserved.\n"
        "  • Every read is traced, and all execution stays under one RunBudget."
    )


if __name__ == "__main__":
    main()
