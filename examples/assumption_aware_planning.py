#!/usr/bin/env python3
"""
Plan Validity & Assumption Tracking (H13)
=========================================

Elevates the runtime from "replan whenever something changes" to "replan only
when the reasoning behind the plan is no longer valid".

Every plan declares the assumptions it depends on (database reachable, dataset
available, stakeholder approval). After each step the runtime evaluates the
observation *against those assumptions* and decides Continue / Replan / Abort /
Complete. Two things are demonstrated:

  1. The SAME observation produces DIFFERENT decisions depending on the
     underlying assumption (recoverable → replan; unrecoverable → abort).
  2. An observation that changes NO assumption does NOT trigger replanning,
     even when it carries a new constraint.
  3. Selective invalidation: only the future steps that depend on a failed
     assumption are reconsidered; completed work is preserved.

No API key, no GPU — deterministic mock adapters and scripted observations.
All execution runs under the shared H11 RunBudget.

Run:
    python examples/assumption_aware_planning.py
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
    # H13
    PlanAssumption,
    AssumptionState,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionObservation,
    AssumptionContext,
    build_assumption_aware_runner,
    format_assumptions,
    format_validity_trace,
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


def _plan():
    # Each step declares the assumptions it depends on (via metadata).
    return Plan.from_steps(
        "produce a governed data report",
        [
            PlanStep("download", "download data", "download the dataset",
                     metadata={"assumptions": ["db_reachable"]}),
            PlanStep("train", "train model", "train the model",
                     metadata={"assumptions": ["dataset_available"]}),
            PlanStep("report", "write report", "write the report",
                     metadata={"assumptions": ["approval"]}),
        ],
    )


def _context(plan, *, approval_recoverable=True):
    reg = AssumptionRegistry([
        PlanAssumption("db_reachable", "database is reachable", "resource"),
        PlanAssumption("dataset_available", "dataset is available", "data"),
        PlanAssumption("approval", "stakeholder approval obtained", "authorization",
                       mandatory=True, recoverable=approval_recoverable),
    ])
    return AssumptionContext(reg, AssumptionDependencyGraph.from_plan(plan))


def demo_same_observation_different_assumptions():
    print("=" * 66)
    print("Same observation, different assumptions → different decisions")
    print("=" * 66)

    # The identical observation: step 1 discovers approval has been revoked.
    def observations():
        return [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"approval": AssumptionState.INVALID},
                                  summary="approval revoked", goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]

    # Case A — approval is recoverable (can be re-obtained) → REVISE.
    plan_a = _plan()
    ctx_a = _context(plan_a, approval_recoverable=True)
    run_a = build_assumption_aware_runner(
        _agent(), ctx_a, observation_builder=ScriptedObservationBuilder(observations())
    ).run(plan_a.goal, plan_a)

    # Case B — approval is a hard, unrecoverable precondition → ABORT.
    plan_b = _plan()
    ctx_b = _context(plan_b, approval_recoverable=False)
    run_b = build_assumption_aware_runner(
        _agent(), ctx_b, observation_builder=ScriptedObservationBuilder(observations())
    ).run(plan_b.goal, plan_b)

    print(f"\n  Case A (approval recoverable):   decision={ctx_a.trace.entries[0].decision}  "
          f"stop={run_a.stop_reason}")
    print(f"  Case B (approval unrecoverable): decision={ctx_b.trace.entries[0].decision}  "
          f"stop={run_b.stop_reason}")
    print("\n  → identical observation, different underlying assumption, "
          "different execution.")


def demo_non_invalidating_observation():
    print("\n" + "=" * 66)
    print("Observation that changes no assumption → NO replanning")
    print("=" * 66)

    plan = _plan()
    ctx = _context(plan)
    run = build_assumption_aware_runner(
        _agent(), ctx,
        observation_builder=ScriptedObservationBuilder([
            # A new constraint appears, but it maps to no planning assumption.
            AssumptionObservation(status=ObservationStatus.CONSTRAINT,
                                  new_constraints=["please_use_metric_units"], goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
    ).run(plan.goal, plan)

    print(f"\n  revisions: {run.revision_count}  (a plain 'observation changed' "
          "runtime would have replanned)")
    print(f"  first decision: {ctx.trace.entries[0].decision} — "
          f"{ctx.trace.entries[0].reason}")


def demo_selective_invalidation():
    print("\n" + "=" * 66)
    print("Selective invalidation — only affected future steps reconsidered")
    print("=" * 66)

    plan = _plan()
    ctx = _context(plan)
    run = build_assumption_aware_runner(
        _agent(), ctx,
        observation_builder=ScriptedObservationBuilder([
            # Step 0: dataset_available becomes invalid (only 'train' depends on it).
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"dataset_available": AssumptionState.INVALID},
                                  summary="dataset withdrawn", goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]),
        run_budget=RunBudget(RunBudgetLimits()),
    ).run(plan.goal, plan)

    e0 = ctx.trace.entries[0]
    print(f"\n  validity after step 0: {e0.validity}")
    print(f"  affected steps:        {e0.affected_steps}   "
          "('report' was untouched — its assumption held)")
    print(f"  inserted (repair):     {[s.step_id for s in run.plan.inserted_steps()]}")
    print(f"  completed:             {[s.step_id for s in run.plan.completed_steps()]}")
    print("\n" + format_validity_trace(ctx))
    print("\n" + format_assumptions(ctx.registry))


def main():
    demo_same_observation_different_assumptions()
    demo_non_invalidating_observation()
    demo_selective_invalidation()
    print(
        "\nKey properties demonstrated:\n"
        "  • The runtime reasons about ASSUMPTIONS, not raw observations.\n"
        "  • Identical observations → different decisions via assumptions.\n"
        "  • Non-invalidating observations do not trigger replanning.\n"
        "  • Only the affected portion of the plan is reconsidered.\n"
        "  • Every assumption transition is deterministic and traceable,\n"
        "    and all execution stays within the shared RunBudget."
    )


if __name__ == "__main__":
    main()
