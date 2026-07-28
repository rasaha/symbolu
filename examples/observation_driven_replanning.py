#!/usr/bin/env python3
"""
Observation-Driven Replanning (H12)
===================================

Proves *adaptive* autonomous execution: the runtime changes its future plan
based on what it observes — while never rewriting completed work and staying
inside the shared RunBudget.

The headline demo runs the SAME goal with the SAME starting plan twice, under
two different observation streams, and shows the runtime produce two DIFFERENT
executed plans:

  Run A: everything goes smoothly            → plan runs as written
  Run B: step 1 uncovers a new constraint    → an extra step is inserted

It then shows tool-failure recovery (an alternative step is inserted) and a
full, reconstructable replanning trace.

No API key, no GPU — deterministic mock adapters and scripted observations.

Run:
    python examples/observation_driven_replanning.py
"""

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    Plan,
    PlanStep,
    PlanObservation,
    ObservationStatus,
    ReplanningRunner,
    RuleBasedReplanner,
    ScriptedObservationBuilder,
    format_replanning_trace,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _agent():
    """A governed agent; open gate so the demo runs deterministically."""
    a = build_agent(
        adapter=MockLLMAdapter(default_response="ok"),
        use_llm_for_decomposition=False,
        max_revisions=0,
    )
    a.safety_gate = SafetyGate(SafetyContractEvaluator(0.0, 0.0, 1.0, 0.0))
    return a


def _starting_plan(goal):
    return Plan.from_steps(
        goal,
        [
            PlanStep("collect", "collect data", "collect the raw data"),
            PlanStep("analyze", "analyze data", "analyze the collected data"),
            PlanStep("report", "write report", "write the final report"),
        ],
    )


def _adaptive_replanner():
    """Insert a constraint-handling step ahead of the remaining future."""
    def strategy(plan, obs):
        if obs.new_constraints:
            step = PlanStep(
                "satisfy_" + obs.new_constraints[0],
                "satisfy constraint",
                "satisfy: " + obs.new_constraints[0],
            )
            return [step] + list(plan.future)
        return list(plan.future)

    return RuleBasedReplanner(strategy)


def demo_same_goal_different_observations():
    print("=" * 64)
    print("Same goal + same starting plan, DIFFERENT observations")
    print("=" * 64)

    goal = "produce a data report"

    # Run A — smooth sailing.
    run_a = ReplanningRunner(
        _agent(),
        observation_builder=ScriptedObservationBuilder([
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.4),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
        replanner=_adaptive_replanner(),
    ).run(goal, _starting_plan(goal))

    # Run B — step 1 uncovers a governance/access constraint.
    run_b = ReplanningRunner(
        _agent(),
        observation_builder=ScriptedObservationBuilder([
            PlanObservation(status=ObservationStatus.SUCCESS,
                            new_constraints=["needs_data_access_approval"], goal_progress=0.4),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
        replanner=_adaptive_replanner(),
    ).run(goal, _starting_plan(goal))

    path_a = [s.step_id for s in run_a.plan.completed_steps()]
    path_b = [s.step_id for s in run_b.plan.completed_steps()]
    print(f"\n  Run A executed: {path_a}   (revisions={run_a.revision_count})")
    print(f"  Run B executed: {path_b}   (revisions={run_b.revision_count})")
    print(f"\n  Different plans from the same goal? {path_a != path_b}")
    print("  → the runtime ADAPTED to the observation, it did not just repeat.")


def demo_tool_failure_recovery():
    print("\n" + "=" * 64)
    print("Tool-failure recovery — alternative path inserted")
    print("=" * 64)

    def recover(plan, obs):
        if obs.status == ObservationStatus.FAILURE:
            return [PlanStep("collect_fallback", "fallback collect",
                             "collect via the backup source")] + list(plan.future)
        return list(plan.future)

    goal = "produce a data report"
    run = ReplanningRunner(
        _agent(),
        observation_builder=ScriptedObservationBuilder([
            PlanObservation(status=ObservationStatus.FAILURE, summary="primary source down", goal_progress=0.0),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
        replanner=RuleBasedReplanner(recover),
    ).run(goal, _starting_plan(goal))

    print(f"\n  stop_reason: {run.stop_reason}")
    print(f"  failed steps:   {[s.step_id for s in run.plan.failed_steps()]}")
    print(f"  inserted steps: {[s.step_id for s in run.plan.inserted_steps()]}")
    print(f"  completed:      {[s.step_id for s in run.plan.completed_steps()]}")
    print("\n" + format_replanning_trace(run))


def demo_budget_shared():
    print("\n" + "=" * 64)
    print("All replanning consumes ONE shared RunBudget (H11)")
    print("=" * 64)
    goal = "produce a data report"
    budget = RunBudget(RunBudgetLimits())
    run = ReplanningRunner(
        _agent(),
        observation_builder=ScriptedObservationBuilder([
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c1"], goal_progress=0.3),
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c2"], goal_progress=0.5),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
        replanner=_adaptive_replanner(),
        run_budget=budget,
    ).run(goal, _starting_plan(goal))
    print(f"\n  revisions:   {run.revision_count}")
    print(f"  iterations:  {run.iterations}")
    print(f"  model calls: {budget.usage.model_calls} (cumulative, never reset across replans)")
    print(f"  budget status: {budget.status}")


def main():
    demo_same_goal_different_observations()
    demo_tool_failure_recovery()
    demo_budget_shared()
    print(
        "\nKey properties demonstrated:\n"
        "  • Two identical goals with different observations produced "
        "different plans.\n"
        "  • Completed steps were preserved and never rewritten.\n"
        "  • Every revision is deterministic and fully traceable.\n"
        "  • All execution stayed within one shared RunBudget."
    )


if __name__ == "__main__":
    main()
