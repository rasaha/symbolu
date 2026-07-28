"""
Tests for H14 — Governed Working Memory & State Continuity.

Required scenarios:
- Memory creation (steps create records correctly).
- Retrieval (consumers receive the correct active version).
- Versioning (updates create new immutable versions).
- Cross-agent sharing (sequential agents share one WorkingMemory).
- Replanning (memory survives plan revision).
- Assumption dependency (invalid memory invalidates dependent assumptions).
- Expiration (expired records are never retrieved).
- Determinism (identical workflows → identical memory histories).
- Trace reconstruction (complete memory lifecycle reconstructs).
- Budget preservation (memory ops preserve the shared RunBudget).

Evidence requirements:
1. Same observation → different valid outcomes because of stored state.
2. Updates create new versions rather than overwriting.
3. Sequential agents share governed memory without duplication.
4. Invalidating a record propagates to dependent assumptions, history kept.
5. Every decision can identify the memory records that influenced it.
6. H10–H13 governance/budget/replanning/assumption guarantees unchanged.
"""

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    Plan,
    PlanStep,
    ObservationStatus,
    StopReason,
    ScriptedObservationBuilder,
    ReplanningRunner,
    RuleBasedReplanner,
    # H13
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
    build_assumption_aware_runner,
    # H14
    WorkingMemory,
    MemoryState,
    MemoryRecord,
    ExpirationPolicy,
    ExpirationKind,
    MemoryObservation,
    MemoryWrite,
    MemoryAwareObservationBuilder,
    MemoryAssumptionBridge,
    DeterministicSelectionPolicy,
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


# ---------------------------------------------------------------------------
# Core store
# ---------------------------------------------------------------------------
class TestMemoryCore:
    def test_create_and_retrieve(self):
        m = WorkingMemory()
        m.create("profile", {"tier": "std"}, category="profile", producing_step="collect", timestamp=0)
        rec = m.retrieve("profile", consuming_step="risk", now=1)
        assert rec.value == {"tier": "std"}
        assert rec.version == 1
        assert rec.status == MemoryState.ACTIVE
        assert "risk" in rec.consuming_steps

    def test_versioning_is_append_only(self):
        m = WorkingMemory()
        m.create("k", 1, timestamp=0)
        m.update("k", 2, timestamp=1)
        m.update("k", 3, timestamp=2)
        recs = m.records("k")
        assert [(r.version, r.status) for r in recs] == [
            (1, MemoryState.SUPERSEDED),
            (2, MemoryState.SUPERSEDED),
            (3, MemoryState.ACTIVE),
        ]
        # Older versions remain reconstructable.
        assert recs[0].value == 1 and recs[1].value == 2 and recs[2].value == 3
        # Retrieval returns the highest ACTIVE version.
        assert m.retrieve("k", now=3).value == 3

    def test_update_unknown_key_raises(self):
        m = WorkingMemory()
        with pytest.raises(KeyError):
            m.update("missing", 1)

    def test_deterministic_selection(self):
        pol = DeterministicSelectionPolicy()
        recs = [
            MemoryRecord("a#v1", "a", "g", "x", 1, confidence=0.9, status=MemoryState.SUPERSEDED),
            MemoryRecord("a#v2", "a", "g", "y", 2, confidence=0.5, status=MemoryState.ACTIVE),
            MemoryRecord("a#v3", "a", "g", "z", 3, confidence=0.5, status=MemoryState.INVALIDATED),
        ]
        # Only ACTIVE is selectable → v2.
        assert pol.select(recs).record_id == "a#v2"


# ---------------------------------------------------------------------------
# Expiration
# ---------------------------------------------------------------------------
class TestExpiration:
    def test_ttl_expired_never_retrieved(self):
        m = WorkingMemory()
        m.create("token", "abc", expiration=ExpirationPolicy(kind=ExpirationKind.TTL, ttl=5), timestamp=0)
        assert m.retrieve("token", now=4) is not None
        assert m.retrieve("token", now=6) is None
        assert m.records("token")[0].status == MemoryState.EXPIRED

    def test_on_step_expiration(self):
        m = WorkingMemory()
        m.create("scratch", "tmp", expiration=ExpirationPolicy(kind=ExpirationKind.ON_STEP, step_id="cleanup"), timestamp=0)
        m.expire_on_step("cleanup", timestamp=3)
        assert m.retrieve("scratch", now=4) is None

    def test_explicit_invalidate_never_retrieved(self):
        m = WorkingMemory()
        m.create("k", 1, timestamp=0)
        m.invalidate("k", reason="stale", timestamp=1)
        assert m.retrieve("k", now=2) is None
        assert m.records("k")[0].status == MemoryState.INVALIDATED


# ---------------------------------------------------------------------------
# Runtime integration (memory-aware observation builder)
# ---------------------------------------------------------------------------
def _produce_consume_plan():
    return Plan.from_steps(
        "g",
        [
            PlanStep("collect", "collect", "do", metadata={"memory": {"produces": ["profile"]}}),
            PlanStep("risk", "risk", "do", metadata={"memory": {"requires": ["profile"]}}),
            PlanStep("finish", "finish", "do"),
        ],
    )


class TestRuntimeIntegration:
    def test_step_produces_and_consumer_reads(self):
        m = WorkingMemory()
        obs = [
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                              memory_writes=[MemoryWrite("profile", {"tier": "premium"}, category="profile")]),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder, max_iterations=6).run("g", _produce_consume_plan())
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert m.peek("profile").value == {"tier": "premium"}
        assert "risk" in m.records("profile")[0].consuming_steps

    def test_evidence5_decision_identifies_influencing_records(self):
        m = WorkingMemory()
        obs = [
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                              memory_writes=[MemoryWrite("profile", {"tier": "std"})]),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder, max_iterations=6).run("g", _produce_consume_plan())
        # The 'risk' step's decision trace records the memory it read.
        assert r.trace[1]["observation"]["memory_reads"] == ["profile#v1"]


# ---------------------------------------------------------------------------
# Cross-agent sharing
# ---------------------------------------------------------------------------
class TestCrossAgent:
    def test_sequential_agents_share_one_memory(self):
        shared = WorkingMemory()
        plan_a = Plan.from_steps("a", [PlanStep("produce", "produce", "do", metadata={"memory": {"produces": ["dataset"]}})])
        plan_b = Plan.from_steps("b", [PlanStep("consume", "consume", "do", metadata={"memory": {"requires": ["dataset"]}})])

        ba = MemoryAwareObservationBuilder(shared, ScriptedObservationBuilder([
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0,
                              memory_writes=[MemoryWrite("dataset", [1, 2, 3])])]))
        bb = MemoryAwareObservationBuilder(shared, ScriptedObservationBuilder([
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0)]))

        ReplanningRunner(_agent(), observation_builder=ba, max_iterations=3).run("a", plan_a)
        ReplanningRunner(_agent(), observation_builder=bb, max_iterations=3).run("b", plan_b)

        # One store, no copies: produced by A, consumed by B.
        rec = shared.peek("dataset")
        assert rec.value == [1, 2, 3]
        assert rec.producing_step == "produce"
        assert "consume" in shared.records("dataset")[0].consuming_steps


# ---------------------------------------------------------------------------
# Replanning survival
# ---------------------------------------------------------------------------
class TestReplanningSurvival:
    def test_memory_survives_plan_revision(self):
        m = WorkingMemory()
        plan = Plan.from_steps("g", [
            PlanStep("a", "a", "do", metadata={"memory": {"produces": ["shared_state"]}}),
            PlanStep("b", "b", "do"),
            PlanStep("c", "c", "do"),
        ])
        # Step 0 produces shared_state; step 1 triggers a revision.
        obs = [
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                              memory_writes=[MemoryWrite("shared_state", {"v": 1})]),
            MemoryObservation(status=ObservationStatus.FAILURE, summary="need alt", goal_progress=0.3),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]

        def repair(pl, ob):
            return [PlanStep("b_alt", "alt", "do")] + list(pl.future)

        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder,
                             replanner=RuleBasedReplanner(repair), max_iterations=8).run("g", plan)
        # The revision happened, but memory produced before it survived intact.
        assert r.revision_count == 1
        assert m.peek("shared_state").value == {"v": 1}
        assert m.records("shared_state")[0].status == MemoryState.ACTIVE


# ---------------------------------------------------------------------------
# Assumption dependency (H13 bridge)
# ---------------------------------------------------------------------------
class TestAssumptionDependency:
    def test_invalid_memory_invalidates_dependent_assumption(self):
        # 'check' invalidates the supporting memory; 'use' depends on the
        # assumption backed by that memory.
        plan = Plan.from_steps("g", [
            PlanStep("check", "check", "do"),
            PlanStep("use", "use", "do", metadata={"assumptions": ["data_ok"]}),
        ])
        ctx = AssumptionContext(
            AssumptionRegistry([PlanAssumption("data_ok", "data valid", "data", mandatory=True, recoverable=False)]),
            AssumptionDependencyGraph.from_plan(plan),
        )
        m = WorkingMemory()
        m.create("dataset", "d", timestamp=0)
        MemoryAssumptionBridge(m, ctx, links={"dataset": ["data_ok"]})

        obs = [MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                                 memory_invalidations=["dataset"])]
        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = build_assumption_aware_runner(_agent(), ctx, observation_builder=builder).run("g", plan)

        assert m.records("dataset")[0].status == MemoryState.INVALIDATED
        assert ctx.registry.get("data_ok").state == AssumptionState.INVALID
        assert r.stop_reason == StopReason.GOAL_IMPOSSIBLE
        # History preserved on both sides.
        assert m.records("dataset")[0].value == "d"
        assert len(ctx.registry.get("data_ok").history) == 1


# ---------------------------------------------------------------------------
# Budget preservation & determinism
# ---------------------------------------------------------------------------
class TestBudgetAndDeterminism:
    def test_memory_ops_preserve_shared_budget(self):
        m = WorkingMemory()
        obs = [
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                              memory_writes=[MemoryWrite("x", 1)]),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        budget = RunBudget(RunBudgetLimits())
        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder, run_budget=budget,
                             max_iterations=6).run("g", _produce_consume_plan())
        # One model call per executed step; memory ops added nothing to the budget.
        assert budget.usage.model_calls == r.iterations
        assert budget.usage.iterations == r.iterations
        assert r.run_budget is budget

    def test_identical_workflows_identical_memory_history(self):
        def run():
            m = WorkingMemory()
            obs = [
                MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3,
                                  memory_writes=[MemoryWrite("k", "a")]),
                MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6,
                                  memory_writes=[MemoryWrite("k", "b")]),
                MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ]
            builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
            plan = Plan.from_steps("g", [
                PlanStep("s0", "s0", "do", metadata={"memory": {"produces": ["k"]}}),
                PlanStep("s1", "s1", "do", metadata={"memory": {"produces": ["k"]}}),
                PlanStep("s2", "s2", "do"),
            ])
            ReplanningRunner(_agent(), observation_builder=builder, max_iterations=6).run("g", plan)
            return m.trace.to_list()
        assert run() == run()


# ---------------------------------------------------------------------------
# Trace reconstruction
# ---------------------------------------------------------------------------
class TestTraceReconstruction:
    def test_memory_lifecycle_reconstructs(self):
        m = WorkingMemory()
        m.create("k", 1, producing_step="s0", timestamp=0)
        m.update("k", 2, producing_step="s1", timestamp=1)
        m.retrieve("k", consuming_step="s2", now=2)
        m.invalidate("k", reason="done", timestamp=3)
        ops = [o.op for o in m.trace.operations]
        # CREATE, then SUPERSEDE+UPDATE on the new version, READ, INVALIDATE.
        assert "CREATE" in ops and "SUPERSEDE" in ops and "UPDATE" in ops
        assert "READ" in ops and "INVALIDATE" in ops
        # Full snapshot reconstructs both versions.
        snap = m.snapshot()
        assert len(snap["keys"]["k"]["versions"]) == 2
        assert "Memory trace" in format_memory_trace(m)
        assert "Working memory" in format_working_memory(m)


# ---------------------------------------------------------------------------
# Evidence 1 & 2 (headline)
# ---------------------------------------------------------------------------
class TestEvidence:
    def _run_with_state(self, tier):
        m = WorkingMemory()
        m.create("customer_tier", tier, timestamp=0)
        plan = Plan.from_steps("g", [
            PlanStep("assess", "assess", "do"),
            PlanStep("decide", "decide", "do", metadata={"memory": {"requires": ["customer_tier"]}}),
        ])

        def repair(pl, ob):
            rec = m.peek("customer_tier")
            branch = "manual_review" if rec and rec.value == "premium" else "auto_reject"
            return [PlanStep(branch, branch, "do")] + list(pl.future)

        obs = [
            MemoryObservation(status=ObservationStatus.FAILURE, summary="risk high", goal_progress=0.0),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            MemoryObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        builder = MemoryAwareObservationBuilder(m, ScriptedObservationBuilder(obs))
        r = ReplanningRunner(_agent(), observation_builder=builder,
                             replanner=RuleBasedReplanner(repair), max_iterations=6).run("g", plan)
        return [s.step_id for s in r.plan.completed_steps()]

    def test_evidence1_same_observation_different_stored_state_different_outcome(self):
        premium = self._run_with_state("premium")
        standard = self._run_with_state("standard")
        assert premium != standard
        assert "manual_review" in premium and "auto_reject" in standard

    def test_evidence2_updates_version_not_overwrite(self):
        m = WorkingMemory()
        m.create("k", "v1", timestamp=0)
        m.update("k", "v2", timestamp=1)
        assert [r.value for r in m.records("k")] == ["v1", "v2"]   # both kept
        assert m.peek("k").value == "v2"
        assert m.records("k")[0].status == MemoryState.SUPERSEDED   # not deleted
