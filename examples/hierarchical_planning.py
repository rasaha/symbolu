#!/usr/bin/env python3
"""
Hierarchical Planning & Goal Decomposition (H15)
================================================

Decomposes a mission into an explicit, deterministic tree of goals, then feeds
READY leaf goals to the UNCHANGED H16 coordinator for governed execution. The
whole hierarchy shares one WorkingMemory (H14) and one RunBudget (H11).

    Mission → Goal Tree → Ready Goals → H16 Coordinator → Workers

Demonstrates:

  1. Deterministic decomposition + dependency release (Deploy waits for both
     Build API and Build UI).
  2. H16 is reused as-is — goals are delegated by capability/authority.
  3. Localized replanning: a failure in the Build UI subtree re-decomposes ONLY
     that subtree; Build API is untouched.
  4. One shared WorkingMemory and one shared RunBudget across the hierarchy.

No API key, no GPU — deterministic scripted workers.

Run:
    python examples/hierarchical_planning.py
"""

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
    HierarchyExecutor,
    format_goal_tree,
    format_hierarchy_trace,
)


def _worker(fail_goals=()):
    def w(contract, memory):
        if contract.goal_id in fail_goals:
            return WorkerResult(success=False, detail=f"{contract.goal_id} failed")
        return WorkerResult(success=True, outputs={k: f"{contract.goal_id}:done" for k in contract.expected_outputs})
    return ScriptedWorker(w)


def _registry(fail_goals=()):
    r = CapabilityRegistry()
    r.register(AgentProfile("build_team", role="engineering", capabilities=frozenset({"build"}), trust_level=5),
               _worker(fail_goals))
    r.register(AgentProfile("release_team", role="ops", capabilities=frozenset({"deploy"}), trust_level=5),
               _worker(fail_goals))
    return r


def _mission_goals():
    # Mission: build API + build UI (independent), then deploy (depends on both).
    return [
        Goal("build_api", "build the API service", required_capabilities=frozenset({"build"}),
             produced_memory=("api_artifact",), expected_outputs=("api_artifact",), priority=1),
        Goal("build_ui", "build the web UI", required_capabilities=frozenset({"build"}),
             produced_memory=("ui_artifact",), expected_outputs=("ui_artifact",), priority=2),
        Goal("deploy", "deploy the release", required_capabilities=frozenset({"deploy"}),
             dependencies=("build_api", "build_ui"),
             required_memory=("api_artifact", "ui_artifact"),
             produced_memory=("release",), expected_outputs=("release",), priority=3),
    ]


def demo_happy_path():
    print("=" * 66)
    print("Deterministic decomposition + dependency release + H16 execution")
    print("=" * 66)

    plan = StaticDecomposer().decompose("ship_v1", _mission_goals())
    memory = WorkingMemory()
    budget = RunBudget(RunBudgetLimits())
    result = HierarchyExecutor(_registry(), memory, run_budget=budget).run(plan)

    print(f"\n  mission status: {result.status}")
    print(f"  budget: handoffs={budget.usage.handoffs} (one shared RunBudget)")
    print(f"  shared memory keys: {memory.keys()}")
    print("\n" + format_goal_tree(plan.tree))
    print("\n" + format_hierarchy_trace(result))


def demo_localized_replanning():
    print("\n" + "=" * 66)
    print("Localized replanning — Build UI fails, only its subtree replans")
    print("=" * 66)

    def replan(tree, failed_goal_id):
        # Re-decompose ONLY the failed leaf's subtree.
        if failed_goal_id == "build_ui":
            return [Goal("build_ui_lite", "build a simpler UI",
                         required_capabilities=frozenset({"build"}),
                         produced_memory=("ui_artifact",), expected_outputs=("ui_artifact",))]
        return []

    plan = StaticDecomposer().decompose("ship_v1", _mission_goals())
    result = HierarchyExecutor(_registry(fail_goals={"build_ui"}), WorkingMemory(),
                               subtree_replanner=replan).run(plan)

    print(f"\n  mission status: {result.status}")
    print(f"  build_api : {plan.tree.lookup('build_api').status}   (untouched by the UI failure)")
    print(f"  build_ui  : {plan.tree.lookup('build_ui').status}     (replaced)")
    print(f"  build_ui_lite: {plan.tree.lookup('build_ui_lite').status}   (localized replan)")
    print(f"  deploy    : {plan.tree.lookup('deploy').status}")
    print("\n" + format_hierarchy_trace(result))


def main():
    demo_happy_path()
    demo_localized_replanning()
    print(
        "\nKey properties demonstrated:\n"
        "  • The same mission decomposes into the same deterministic goal tree.\n"
        "  • Completing a goal deterministically unblocks its dependents.\n"
        "  • The H16 coordinator executes READY goals with NO modification.\n"
        "  • A subtree failure replans only that subtree — siblings are intact.\n"
        "  • The whole hierarchy shares one WorkingMemory and one RunBudget."
    )


if __name__ == "__main__":
    main()
