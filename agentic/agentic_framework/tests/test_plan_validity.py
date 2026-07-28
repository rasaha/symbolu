"""
Tests for H13 — Plan Validity & Assumption Tracking.

Required scenarios:
- No change (observation does not affect assumptions → plan continues).
- Assumption invalidated (only dependent future steps become invalid).
- Multiple assumptions fail (correct dependency analysis).
- Partial validity (only part of the remaining plan revised; work preserved).
- Mandatory failure (critical unrecoverable assumption → abort).
- New assumption (observation introduces a required assumption → plan updates).
- Budget preservation (multiple evaluations share one RunBudget, no reset).
- Trace reconstruction (assumption lifecycle reconstructs correctly).
- Determinism (identical observations → identical validity decisions).

Evidence requirements:
1. Two identical observations → different decisions depending on assumptions.
2. Observations that do not invalidate assumptions do not trigger replanning.
3. Only the affected portion of a plan is reconsidered.
4. Every assumption transition is deterministic and reconstructable.
5. Governance/budget guarantees from H10–H12 remain unchanged.
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
    ReplanDecision,
    StopReason,
    ScriptedObservationBuilder,
    # H13
    PlanAssumption,
    AssumptionState,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionObservation,
    AssumptionContext,
    AssumptionAwareReplanPolicy,
    PlanValidity,
    PlanValidityEvaluator,
    RuleBasedAssumptionEvaluator,
    build_assumption_aware_runner,
    format_validity_trace,
    format_assumptions,
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
    return Plan.from_steps(
        "goal",
        [
            PlanStep("download", "download data", "do download", metadata={"assumptions": ["db"]}),
            PlanStep("train", "train model", "do train", metadata={"assumptions": ["data"]}),
            PlanStep("report", "generate report", "do report", metadata={"assumptions": ["approval"]}),
        ],
    )


def _context(plan, *, approval_mandatory=True):
    reg = AssumptionRegistry([
        PlanAssumption("db", "database reachable", "resource"),
        PlanAssumption("data", "dataset available", "data"),
        PlanAssumption("approval", "stakeholder approval", "authorization", mandatory=approval_mandatory),
    ])
    return AssumptionContext(reg, AssumptionDependencyGraph.from_plan(plan))


def _run(observations, plan, context, **kw):
    return build_assumption_aware_runner(
        _agent(), context,
        observation_builder=ScriptedObservationBuilder(observations),
        **kw,
    ).run("goal", plan)


# ---------------------------------------------------------------------------
# Assumption model
# ---------------------------------------------------------------------------
class TestAssumptionModel:
    def test_transitions_are_append_only(self):
        a = PlanAssumption("db", "database", "resource")
        assert a.state == AssumptionState.VALID
        a.transition(AssumptionState.INVALID, reason="down", timestamp=1.0)
        a.transition(AssumptionState.SATISFIED, reason="restored", timestamp=2.0)
        assert a.state == AssumptionState.SATISFIED
        assert len(a.history) == 2
        assert a.history[0].from_state == AssumptionState.VALID
        assert a.history[0].to_state == AssumptionState.INVALID
        assert a.history[1].to_state == AssumptionState.SATISFIED
        assert a.last_validated_at == 2.0

    def test_registry_is_append_only(self):
        reg = AssumptionRegistry([PlanAssumption("a", "A", "x")])
        with pytest.raises(ValueError):
            reg.add(PlanAssumption("a", "dup", "x"))

    def test_dependency_graph_from_metadata(self):
        plan = _plan()
        g = AssumptionDependencyGraph.from_plan(plan)
        assert g.assumptions_for_step("train") == {"data"}
        assert g.steps_depending_on("data") == {"train"}


# ---------------------------------------------------------------------------
# Validity evaluator (unit, deterministic)
# ---------------------------------------------------------------------------
class TestValidityEvaluator:
    def test_all_valid_is_plan_valid(self):
        plan = _plan()
        ctx = _context(plan)
        res = PlanValidityEvaluator().evaluate(plan, ctx.registry, ctx.graph)
        assert res.validity == PlanValidity.PLAN_VALID

    def test_failed_assumption_only_completed_dep_is_valid(self):
        plan = _plan()
        ctx = _context(plan)
        # Complete 'download' (which depends on db); then db fails.
        plan.mark_executed(plan.future[0], "completed")
        ctx.registry.get("db").transition(AssumptionState.INVALID, timestamp=1.0)
        res = PlanValidityEvaluator().evaluate(plan, ctx.registry, ctx.graph)
        # No FUTURE step depends on db → still valid (selective).
        assert res.validity == PlanValidity.PLAN_VALID

    def test_failed_assumption_future_dep_is_partial(self):
        plan = _plan()
        ctx = _context(plan)
        ctx.registry.get("data").transition(AssumptionState.INVALID, timestamp=1.0)
        res = PlanValidityEvaluator().evaluate(plan, ctx.registry, ctx.graph)
        assert res.validity == PlanValidity.PLAN_PARTIALLY_VALID
        assert [s.step_id for s in res.affected_steps] == ["train"]

    def test_mandatory_unrecoverable_is_impossible(self):
        plan = _plan()
        ctx = _context(plan)
        ctx.registry.get("approval").recoverable = False
        ctx.registry.get("approval").transition(AssumptionState.INVALID, timestamp=1.0)
        res = PlanValidityEvaluator().evaluate(plan, ctx.registry, ctx.graph)
        assert res.validity == PlanValidity.PLAN_IMPOSSIBLE


# ---------------------------------------------------------------------------
# Required scenarios (end-to-end)
# ---------------------------------------------------------------------------
class TestNoChange:
    def test_observation_not_affecting_assumptions_continues(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        r = _run(obs, plan, _context(plan))
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert r.revision_count == 0


class TestAssumptionInvalidated:
    def test_only_dependent_future_steps_become_invalid(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        r = _run(obs, plan, ctx)
        entry0 = ctx.trace.entries[0]
        assert entry0.validity == PlanValidity.PLAN_PARTIALLY_VALID
        assert entry0.affected_steps == ["train"]   # only the dependent step
        assert entry0.decision == ReplanDecision.REVISE
        assert r.revision_count == 1


class TestMultipleAssumptions:
    def test_several_failures_dependency_analysis(self):
        obs = [
            AssumptionObservation(
                status=ObservationStatus.SUCCESS,
                assumption_signals={"data": AssumptionState.INVALID, "approval": AssumptionState.INVALID},
                goal_progress=0.3,
            ),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan, approval_mandatory=False)  # both recoverable
        r = _run(obs, plan, ctx)
        entry0 = ctx.trace.entries[0]
        # Both future steps (train←data, report←approval) affected → invalid.
        assert entry0.validity == PlanValidity.PLAN_INVALID
        assert set(entry0.affected_steps) == {"train", "report"}
        assert set(entry0.evaluation["changed"].keys()) == {"data", "approval"}


class TestPartialValidity:
    def test_completed_work_preserved_on_partial_revision(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),  # download ok
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"approval": AssumptionState.INVALID}, goal_progress=0.5),  # train ok, approval fails
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),  # satisfy
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),  # report
        ]
        plan = _plan()
        ctx = _context(plan, approval_mandatory=False)
        r = _run(obs, plan, ctx)
        # download + train completed BEFORE approval failed — preserved.
        completed = [s.step_id for s in r.plan.completed_steps()]
        assert "download" in completed and "train" in completed
        # Only 'report' (approval-dependent) was reconsidered.
        assert ctx.trace.entries[1].affected_steps == ["report"]


class TestMandatoryFailure:
    def test_unrecoverable_mandatory_aborts(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"approval": AssumptionState.INVALID}, goal_progress=0.3),
        ]
        plan = _plan()
        ctx = _context(plan)
        ctx.registry.get("approval").recoverable = False
        r = _run(obs, plan, ctx)
        assert r.stop_reason == StopReason.GOAL_IMPOSSIBLE
        assert ctx.trace.entries[0].decision == ReplanDecision.ABORT


class TestNewAssumption:
    def test_introduced_assumption_updates_plan(self):
        new_a = PlanAssumption("mfa", "multi-factor auth", "authorization",
                               mandatory=True, state=AssumptionState.UNKNOWN,
                               metadata={"steps": ["report"]})
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, introduces=[new_a], goal_progress=0.5),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        r = _run(obs, plan, ctx)
        assert r.revision_count == 1
        assert "satisfy_mfa" in [s.step_id for s in r.plan.inserted_steps()]
        assert ctx.registry.has("mfa")


# ---------------------------------------------------------------------------
# Budget preservation
# ---------------------------------------------------------------------------
class TestBudgetPreservation:
    def test_evaluations_share_one_budget_no_reset(self):
        new_a = PlanAssumption("mfa", "mfa", "auth", mandatory=True,
                               state=AssumptionState.UNKNOWN, metadata={"steps": ["report"]})
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.2),
            AssumptionObservation(status=ObservationStatus.SUCCESS, introduces=[new_a], goal_progress=0.4),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan, approval_mandatory=False)
        budget = RunBudget(RunBudgetLimits())
        r = _run(obs, plan, ctx, run_budget=budget)
        assert budget.usage.iterations == r.iterations
        assert budget.usage.model_calls == r.iterations   # cumulative, one per step
        assert r.run_budget is budget

    def test_budget_bound_still_enforced(self):
        obs = [AssumptionObservation(status=ObservationStatus.PARTIAL, summary=f"p{i}", goal_progress=i * 0.1) for i in range(10)]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(10)])
        ctx = AssumptionContext(AssumptionRegistry(), AssumptionDependencyGraph.from_plan(plan))
        budget = RunBudget(RunBudgetLimits(max_iterations=2))
        r = _run(obs, plan, ctx, run_budget=budget)
        assert r.stop_reason == StopReason.BUDGET_EXHAUSTED
        assert budget.usage.iterations == 2


# ---------------------------------------------------------------------------
# Trace reconstruction + determinism
# ---------------------------------------------------------------------------
class TestTraceReconstruction:
    def test_assumption_lifecycle_reconstructs(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"data": AssumptionState.INVALID},
                                  summary="dataset gone", goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        _run(obs, plan, ctx)
        # First entry captures observation → evaluation → transition → validity → decision.
        e0 = ctx.trace.entries[0]
        assert e0.evaluation["changed"] == {"data": AssumptionState.INVALID}
        assert e0.transitions[0]["from_state"] == AssumptionState.VALID
        assert e0.transitions[0]["to_state"] == AssumptionState.INVALID
        assert e0.validity == PlanValidity.PLAN_PARTIALLY_VALID
        assert e0.decision == ReplanDecision.REVISE
        # The assumption's own append-only history captures the invalidation
        # (and any later re-confirmation) as ordered transitions.
        data_hist = ctx.registry.get("data").history
        assert data_hist[0].from_state == AssumptionState.VALID
        assert data_hist[0].to_state == AssumptionState.INVALID
        assert "Plan validity trace" in format_validity_trace(ctx)
        assert "database reachable" in format_assumptions(ctx.registry)

    def test_deterministic_identical_observations_identical_decisions(self):
        def obs():
            return [
                AssumptionObservation(status=ObservationStatus.SUCCESS,
                                      assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.3),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ]
        p1, c1 = _plan(), None
        c1 = _context(p1)
        r1 = _run(obs(), p1, c1)
        p2 = _plan(); c2 = _context(p2)
        r2 = _run(obs(), p2, c2)
        assert [e.decision for e in c1.trace.entries] == [e.decision for e in c2.trace.entries]
        assert r1.stop_reason == r2.stop_reason


# ---------------------------------------------------------------------------
# Evidence requirements
# ---------------------------------------------------------------------------
class TestEvidence:
    def test_evidence1_same_observation_different_assumptions_different_decisions(self):
        def obs():
            return [
                AssumptionObservation(status=ObservationStatus.SUCCESS,
                                      assumption_signals={"approval": AssumptionState.INVALID}, goal_progress=0.3),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
                AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ]
        # Run X: approval recoverable → REVISE.
        px = _plan(); cx = _context(px); cx.registry.get("approval").recoverable = True
        _run(obs(), px, cx)
        # Run Y: approval unrecoverable → ABORT.
        py = _plan(); cy = _context(py); cy.registry.get("approval").recoverable = False
        _run(obs(), py, cy)
        assert cx.trace.entries[0].decision == ReplanDecision.REVISE
        assert cy.trace.entries[0].decision == ReplanDecision.ABORT

    def test_evidence2_non_invalidating_observation_no_replan(self):
        # A CONSTRAINT observation whose constraint maps to no assumption.
        obs = [
            AssumptionObservation(status=ObservationStatus.CONSTRAINT,
                                  new_constraints=["cosmetic_note"], goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        r = _run(obs, plan, ctx)
        # Base replanning would REVISE on a constraint; assumption-aware does not.
        assert r.revision_count == 0
        assert ctx.trace.entries[0].decision == ReplanDecision.CONTINUE

    def test_evidence3_only_affected_portion_reconsidered(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        r = _run(obs, plan, ctx)
        # 'report' (approval) was never affected and stayed in the plan untouched.
        assert ctx.trace.entries[0].affected_steps == ["train"]
        assert "report" in [s.step_id for s in r.plan.completed_steps()]

    def test_evidence4_transitions_deterministic_and_reconstructable(self):
        obs = [
            AssumptionObservation(status=ObservationStatus.SUCCESS,
                                  assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.3),
            AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        plan = _plan()
        ctx = _context(plan)
        _run(obs, plan, ctx)
        hist = ctx.registry.get("data").history
        # The invalidation is the first, deterministic, reconstructable transition.
        assert (hist[0].from_state, hist[0].to_state) == (AssumptionState.VALID, AssumptionState.INVALID)
        assert hist[0].timestamp == 0.0  # iteration index of the observation

    def test_evidence5_pure_deterministic_evaluator(self):
        plan = _plan()
        ctx = _context(plan)
        obs = AssumptionObservation(status=ObservationStatus.SUCCESS,
                                    assumption_signals={"data": AssumptionState.INVALID})
        ev = RuleBasedAssumptionEvaluator()
        e1 = ev.evaluate(obs, plan.future[1], ctx.registry, ctx.graph)
        e2 = ev.evaluate(obs, plan.future[1], ctx.registry, ctx.graph)
        assert e1.changed == e2.changed == {"data": AssumptionState.INVALID}
