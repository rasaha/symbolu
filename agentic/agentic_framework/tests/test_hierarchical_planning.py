"""
Tests for H15 — Hierarchical Planning & Goal Decomposition.

Required scenarios:
- Deterministic decomposition (same mission → identical goal tree).
- Dependency resolution (dependents blocked; completion releases successors).
- Coordinator integration (READY goals delegated through H16 unmodified).
- Localized replanning (failure affects only one subtree).
- Memory sharing (sibling goals share WorkingMemory).
- Assumption propagation (child assumption invalidation propagates via H13).
- Budget preservation (whole hierarchy consumes one RunBudget).
- Trace reconstruction (full hierarchy reconstructs deterministically).
- Goal completion (mission completes only when required goals complete).

Evidence requirements:
1. Same mission always decomposes into the same hierarchy.
2. Completing one goal deterministically unblocks dependent goals.
3. H16 coordinates execution without modification.
4. A subtree failure replans only that subtree unless parent assumptions fail.
5. All goals share the existing WorkingMemory and RunBudget.
6. The full parent–child execution history is reconstructable.
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
    MissionStatus,
    # H13
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
    # H15
    Goal,
    GoalStatus,
    GoalTree,
    HierarchyStatus,
    StaticDecomposer,
    RuleBasedDecomposer,
    HierarchyExecutor,
    format_goal_tree,
    format_hierarchy_trace,
)


def _build_worker():
    def w(contract, memory):
        return WorkerResult(success=True, outputs={k: "ok" for k in contract.expected_outputs})
    return ScriptedWorker(w)


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("builder", capabilities=frozenset({"build"}), trust_level=5), _build_worker())
    r.register(AgentProfile("deployer", capabilities=frozenset({"deploy"}), trust_level=5), _build_worker())
    return r


def _api_ui_deploy():
    return [
        Goal("build_api", "build API", required_capabilities=frozenset({"build"}), expected_outputs=("api",), priority=1),
        Goal("build_ui", "build UI", required_capabilities=frozenset({"build"}), expected_outputs=("ui",), priority=2),
        Goal("deploy", "deploy", required_capabilities=frozenset({"deploy"}),
             dependencies=("build_api", "build_ui"), required_memory=("api", "ui"),
             expected_outputs=("release",), priority=3),
    ]


# ---------------------------------------------------------------------------
# Goal tree
# ---------------------------------------------------------------------------
class TestGoalTree:
    def test_acyclic_enforced(self):
        with pytest.raises(ValueError):
            StaticDecomposer().decompose("m", [
                Goal("a", "a", dependencies=("b",)),
                Goal("b", "b", dependencies=("a",)),
            ])

    def test_parent_child_and_subtree(self):
        tree = GoalTree()
        tree.add_goal(Goal("root", "root", children=()))
        tree.add_child("root", Goal("c1", "c1"))
        tree.add_child("root", Goal("c2", "c2"))
        assert tree.lookup("root").goal.children == ("c1", "c2")
        assert tree.subtree("root") == {"root", "c1", "c2"}
        assert [n.goal.goal_id for n in tree.children_of("root")] == ["c1", "c2"]

    def test_dependency_graph(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        assert set(plan.tree.successors("build_api")) == {"deploy"}
        assert plan.tree.predecessors("deploy") == ("build_api", "build_ui")


# ---------------------------------------------------------------------------
# Deterministic decomposition
# ---------------------------------------------------------------------------
class TestDeterministicDecomposition:
    def test_same_mission_same_tree(self):
        t1 = StaticDecomposer().decompose("m", _api_ui_deploy()).tree.to_dict()
        t2 = StaticDecomposer().decompose("m", _api_ui_deploy()).tree.to_dict()
        assert t1 == t2

    def test_rule_based_decomposer_deterministic(self):
        rules = lambda spec: _api_ui_deploy()
        d = RuleBasedDecomposer(rules)
        assert d.decompose("m", None).tree.to_dict() == d.decompose("m", None).tree.to_dict()


# ---------------------------------------------------------------------------
# Dependency resolution & execution
# ---------------------------------------------------------------------------
class TestDependencyResolution:
    def test_dependents_blocked_until_release(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        assert res.status == HierarchyStatus.MISSION_COMPLETED
        # deploy ran only after both builds — wave 0 builds, wave 1 deploy.
        assert res.trace.waves[0].ready_goals == ["build_api", "build_ui"]
        assert res.trace.waves[1].ready_goals == ["deploy"]

    def test_completion_releases_successor(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        # 'deploy' appears in wave 0's released list once its deps complete.
        assert "deploy" in res.trace.waves[0].released

    def test_only_ready_goals_execute(self):
        # 'deploy' must never be delegated before its predecessors complete.
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        # In every wave, any executed goal had all deps already completed.
        completed_so_far = set()
        for w in res.trace.waves:
            for gid in w.ready_goals:
                node = plan.tree.lookup(gid)
                assert set(node.goal.dependencies).issubset(completed_so_far)
            completed_so_far.update(w.completed)


# ---------------------------------------------------------------------------
# Coordinator integration (H16 unmodified)
# ---------------------------------------------------------------------------
class TestCoordinatorIntegration:
    def test_ready_goals_delegated_via_h16(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        # Each goal was assigned to a capability-matched H16 worker.
        assert plan.tree.lookup("build_api").assigned_agent == "builder"
        assert plan.tree.lookup("deploy").assigned_agent == "deployer"

    def test_capability_and_authority_still_enforced(self):
        # No agent has the 'deploy' capability → deploy cannot be delegated.
        reg = CapabilityRegistry()
        reg.register(AgentProfile("builder", capabilities=frozenset({"build"})), _build_worker())
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(reg, WorkingMemory()).run(plan)
        assert res.status == HierarchyStatus.MISSION_FAILED
        assert plan.tree.lookup("build_api").status == GoalStatus.COMPLETED
        assert plan.tree.lookup("deploy").status in (GoalStatus.FAILED, GoalStatus.BLOCKED)


# ---------------------------------------------------------------------------
# Localized replanning
# ---------------------------------------------------------------------------
class TestLocalizedReplanning:
    def _reg_ui_fails(self):
        def w(contract, memory):
            if contract.goal_id == "build_ui":
                return WorkerResult(success=False, detail="ui broke")
            return WorkerResult(success=True, outputs={k: "ok" for k in contract.expected_outputs})
        r = CapabilityRegistry()
        r.register(AgentProfile("builder", capabilities=frozenset({"build"}), trust_level=5), ScriptedWorker(w))
        r.register(AgentProfile("deployer", capabilities=frozenset({"deploy"}), trust_level=5), _build_worker())
        return r

    def test_failure_replans_only_affected_subtree(self):
        def replan(tree, gid):
            if gid == "build_ui":
                return [Goal("build_ui_fallback", "UI fallback",
                             required_capabilities=frozenset({"build"}), expected_outputs=("ui",))]
            return []
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(self._reg_ui_fails(), WorkingMemory(), subtree_replanner=replan).run(plan)
        assert res.status == HierarchyStatus.MISSION_COMPLETED
        # The UI subtree was re-decomposed; the API subtree was untouched.
        assert plan.tree.lookup("build_ui").status == GoalStatus.ABORTED
        assert plan.tree.lookup("build_ui_fallback").status == GoalStatus.COMPLETED
        assert plan.tree.lookup("build_api").status == GoalStatus.COMPLETED
        # build_api has no replan-related history — the replan was localized.
        assert not any("replan" in t.reason for t in plan.tree.lookup("build_api").history)
        assert res.trace.waves[0].replanned == ["build_ui"]

    def test_unreplanned_failure_blocks_only_dependents(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(self._reg_ui_fails(), WorkingMemory()).run(plan)  # no replanner
        # build_api still completes; only deploy (dependent) is blocked.
        assert plan.tree.lookup("build_api").status == GoalStatus.COMPLETED
        assert plan.tree.lookup("build_ui").status == GoalStatus.FAILED
        assert plan.tree.lookup("deploy").status == GoalStatus.BLOCKED
        assert res.status == HierarchyStatus.MISSION_FAILED


# ---------------------------------------------------------------------------
# Memory sharing
# ---------------------------------------------------------------------------
class TestMemorySharing:
    def test_siblings_share_working_memory(self):
        mem = WorkingMemory()
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        HierarchyExecutor(_registry(), mem).run(plan)
        # Every goal's outputs landed in the ONE shared store.
        assert mem.peek("api").value == "ok"
        assert mem.peek("ui").value == "ok"
        assert mem.peek("release").value == "ok"


# ---------------------------------------------------------------------------
# Assumption propagation (H13)
# ---------------------------------------------------------------------------
class TestAssumptionPropagation:
    def test_invalid_child_assumption_blocks_subtree(self):
        goals = [
            Goal("train", "train", required_capabilities=frozenset({"build"}),
                 assumptions=("dataset_ok",), expected_outputs=("model",), priority=1),
            Goal("report", "report", required_capabilities=frozenset({"build"}),
                 expected_outputs=("rep",), priority=2),
        ]
        ctx = AssumptionContext(
            AssumptionRegistry([PlanAssumption("dataset_ok", "dataset valid", "data")]),
            AssumptionDependencyGraph(),
        )
        ctx.registry.get("dataset_ok").transition(AssumptionState.INVALID, timestamp=0)
        plan = StaticDecomposer().decompose("m", goals)
        res = HierarchyExecutor(_registry(), WorkingMemory(), assumption_context=ctx).run(plan)
        assert plan.tree.lookup("train").status == GoalStatus.BLOCKED   # assumption invalid
        assert plan.tree.lookup("report").status == GoalStatus.COMPLETED  # unaffected sibling
        assert res.status == HierarchyStatus.MISSION_FAILED

    def test_inherited_assumption_blocks_child(self):
        # Parent assumption invalidation blocks a child (inheritance).
        goals = [
            Goal("parent", "parent", assumptions=("infra_ok",), children=("child",)),
            Goal("child", "child", parent="parent", required_capabilities=frozenset({"build"}), expected_outputs=("x",)),
        ]
        ctx = AssumptionContext(
            AssumptionRegistry([PlanAssumption("infra_ok", "infra", "resource")]),
            AssumptionDependencyGraph(),
        )
        ctx.registry.get("infra_ok").transition(AssumptionState.INVALID, timestamp=0)
        plan = StaticDecomposer().decompose("m", goals)
        res = HierarchyExecutor(_registry(), WorkingMemory(), assumption_context=ctx).run(plan)
        assert plan.tree.lookup("child").status == GoalStatus.BLOCKED


# ---------------------------------------------------------------------------
# Budget preservation
# ---------------------------------------------------------------------------
class TestBudgetPreservation:
    def test_whole_hierarchy_shares_one_budget(self):
        budget = RunBudget(RunBudgetLimits())
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        HierarchyExecutor(_registry(), WorkingMemory(), run_budget=budget).run(plan)
        # Three delegations (one per goal), all on the same budget.
        assert budget.usage.handoffs == 3

    def test_budget_exhaustion_stops_hierarchy(self):
        budget = RunBudget(RunBudgetLimits(max_handoffs=2))
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory(), run_budget=budget).run(plan)
        assert res.status == HierarchyStatus.BUDGET_EXHAUSTED
        assert budget.usage.handoffs == 2


# ---------------------------------------------------------------------------
# Trace reconstruction, determinism, completion
# ---------------------------------------------------------------------------
class TestTraceAndCompletion:
    def test_full_hierarchy_reconstructs(self):
        plan = StaticDecomposer().decompose("m", _api_ui_deploy())
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        d = res.to_dict()
        assert d["status"] == HierarchyStatus.MISSION_COMPLETED
        assert set(d["completed_goals"]) == {"build_api", "build_ui", "deploy"}
        # Every goal node carries its append-only status history.
        deploy = plan.tree.lookup("deploy")
        states = [t.to_status for t in deploy.history]
        assert states[-1] == GoalStatus.COMPLETED
        assert GoalStatus.EXECUTING in states
        assert "Goal tree" in format_goal_tree(plan.tree)
        assert "Hierarchy" in format_hierarchy_trace(res)

    def test_same_mission_identical_execution(self):
        def run():
            plan = StaticDecomposer().decompose("m", _api_ui_deploy())
            res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
            return res.trace.to_list()
        assert run() == run()

    def test_mission_completes_only_when_required_goals_done(self):
        # An optional goal may fail without failing the mission.
        goals = [
            Goal("core", "core work", required_capabilities=frozenset({"build"}), expected_outputs=("c",), priority=1),
            Goal("nice_to_have", "optional", required_capabilities=frozenset({"missing_cap"}),
                 expected_outputs=("n",), mandatory=False, priority=2),
        ]
        plan = StaticDecomposer().decompose("m", goals)
        res = HierarchyExecutor(_registry(), WorkingMemory()).run(plan)
        # The optional goal has no qualified worker → fails, but mission completes.
        assert plan.tree.lookup("core").status == GoalStatus.COMPLETED
        assert res.status == HierarchyStatus.MISSION_COMPLETED


# ---------------------------------------------------------------------------
# Evidence 1 (headline)
# ---------------------------------------------------------------------------
class TestEvidence:
    def test_evidence1_same_mission_same_hierarchy(self):
        a = StaticDecomposer().decompose("mission", _api_ui_deploy()).tree.to_dict()
        b = StaticDecomposer().decompose("mission", _api_ui_deploy()).tree.to_dict()
        assert a == b
