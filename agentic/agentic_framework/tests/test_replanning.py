"""
Tests for H12 — Observation-Driven Replanning.

Covers the required scenarios:
- No replanning (observation confirms plan).
- Successful replanning (observation invalidates next step).
- Tool-failure recovery (alternative path inserted).
- Constraint change (future adapts, completed work preserved).
- Budget preservation (multiple replans, one shared RunBudget, no reset).
- Trace reconstruction (every revision reconstructable).
- Stagnation (repeated identical observations terminate deterministically).
- Goal completion (remaining plan discarded, terminate immediately).

Plus the 5 evidence requirements:
1. Identical goals + different observations → different subsequent plans.
2. Completed work is never rewritten.
3. Every plan revision is traceable and deterministic.
4. The runtime remains governed by the existing RunBudget.
5. Governance guarantees from prior phases remain unchanged.
"""

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    TerminationReason,
    Plan,
    PlanStep,
    PlanObservation,
    PlanStepState,
    ObservationStatus,
    ReplanDecision,
    StopReason,
    ReplanningRunner,
    DeterministicReplanPolicy,
    RuleBasedReplanner,
    ScriptedObservationBuilder,
    StagnationConfig,
    StagnationDetector,
    format_replanning_trace,
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


def _plan(goal="reach goal"):
    return Plan.from_steps(
        goal,
        [
            PlanStep("s1", "gather", "do gather"),
            PlanStep("s2", "process", "do process"),
            PlanStep("s3", "finish", "do finish"),
        ],
    )


def _run(observations, *, replanner=None, plan=None, goal="reach goal", **kw):
    return ReplanningRunner(
        _agent(),
        observation_builder=ScriptedObservationBuilder(observations),
        replanner=replanner,
        max_iterations=kw.pop("max_iterations", 12),
        **kw,
    ).run(goal, plan or _plan(goal))


def _insert_on_constraint(step_id="extra"):
    def strat(plan, obs):
        if obs.new_constraints:
            return [PlanStep(step_id, "handle", "handle " + obs.new_constraints[0])] + list(plan.future)
        return list(plan.future)
    return RuleBasedReplanner(strat)


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------
class TestPlanModel:
    def test_next_step_respects_dependencies(self):
        plan = Plan.from_steps(
            "g",
            [
                PlanStep("a", "a", "do a"),
                PlanStep("b", "b", "do b", dependencies=["a"]),
            ],
        )
        # b depends on a (not yet completed) -> next is a.
        assert plan.next_step().step_id == "a"
        plan.mark_executed(plan.future[0], PlanStepState.COMPLETED)
        assert plan.next_step().step_id == "b"

    def test_history_is_append_only_on_revision(self):
        plan = _plan()
        plan.mark_executed(plan.future[0], PlanStepState.COMPLETED)  # s1 done
        plan.apply_revision([PlanStep("x", "x", "do x")])  # drop s2,s3; insert x
        completed = [s.step_id for s in plan.completed_steps()]
        removed = [s.step_id for s in plan.removed_steps()]
        assert completed == ["s1"]              # completed preserved
        assert set(removed) == {"s2", "s3"}     # dropped -> removed history
        assert [s.step_id for s in plan.future] == ["x"]
        assert plan.inserted_steps()[0].step_id == "x"


# ---------------------------------------------------------------------------
# Required scenarios
# ---------------------------------------------------------------------------
class TestNoReplanning:
    def test_observation_confirms_plan_unchanged(self):
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs)
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert r.revision_count == 0
        assert [s.step_id for s in r.plan.completed_steps()] == ["s1", "s2", "s3"]
        assert all(d == ReplanDecision.CONTINUE for d, _ in r.decisions[:-1])


class TestSuccessfulReplanning:
    def test_observation_invalidates_next_step(self):
        # A constraint at step 1 forces a revised future; run still succeeds.
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c"], goal_progress=0.3),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs, replanner=_insert_on_constraint())
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert r.revision_count == 1
        assert "extra" in [s.step_id for s in r.plan.completed_steps()]


class TestToolFailureRecovery:
    def test_failure_inserts_alternative_and_completes(self):
        def recover(plan, obs):
            if obs.status == ObservationStatus.FAILURE:
                return [PlanStep("s1_alt", "alt", "do alt")] + list(plan.future)
            return list(plan.future)

        obs = [
            PlanObservation(status=ObservationStatus.FAILURE, summary="tool error", goal_progress=0.0),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs, replanner=RuleBasedReplanner(recover))
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert "s1" in [s.step_id for s in r.plan.failed_steps()]     # failure recorded
        assert "s1_alt" in [s.step_id for s in r.plan.inserted_steps()]  # alternative inserted


class TestConstraintChange:
    def test_future_adapts_completed_preserved(self):
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),          # s1 clean
            PlanObservation(status=ObservationStatus.CONSTRAINT, new_constraints=["auth"], goal_progress=0.4),  # s2 -> constraint
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs, replanner=_insert_on_constraint("auth_step"))
        assert r.revision_count == 1
        # s1 completed BEFORE the revision — must remain completed & untouched.
        s1 = next(s for s in r.plan.completed_steps() if s.step_id == "s1")
        assert s1.state == PlanStepState.COMPLETED
        assert "auth_step" in [s.step_id for s in r.plan.inserted_steps()]


class TestGoalCompletion:
    def test_completion_discards_remaining_plan(self):
        obs = [PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0)]
        r = _run(obs)
        assert r.stop_reason == StopReason.GOAL_COMPLETED
        assert r.done is True
        assert r.iterations == 1  # terminated immediately
        # Remaining steps were discarded (never executed).
        assert [s.step_id for s in r.plan.pending_steps()] == ["s2", "s3"]
        assert [s.step_id for s in r.plan.completed_steps()] == ["s1"]


class TestAbort:
    def test_impossible_observation_aborts(self):
        obs = [PlanObservation(status=ObservationStatus.IMPOSSIBLE, summary="cannot")]
        r = _run(obs)
        assert r.stop_reason == StopReason.GOAL_IMPOSSIBLE
        assert r.done is False


# ---------------------------------------------------------------------------
# Stagnation
# ---------------------------------------------------------------------------
class TestStagnation:
    def test_repeated_identical_observation_terminates(self):
        same = [
            PlanObservation(status=ObservationStatus.PARTIAL, summary="stuck", goal_progress=0.2)
            for _ in range(8)
        ]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(8)])
        r = _run(same, plan=plan, goal="g", stagnation=StagnationConfig(max_repeated_observations=3))
        assert r.stop_reason == StopReason.STAGNATION_DETECTED

    def test_repeated_failures_terminate(self):
        fails = [
            PlanObservation(status=ObservationStatus.FAILURE, summary=f"err{i}", goal_progress=0.0)
            for i in range(6)
        ]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(6)])
        # Distinct summaries so it is the FAILURE streak (not identical-obs) that trips.
        r = _run(fails, plan=plan, goal="g",
                 replanner=RuleBasedReplanner(lambda p, o: list(p.future)),
                 stagnation=StagnationConfig(max_repeated_observations=99, max_consecutive_failures=3))
        assert r.stop_reason == StopReason.REPEATED_FAILURES

    def test_no_progress_terminates(self):
        flat = [
            PlanObservation(status=ObservationStatus.PARTIAL, summary=f"s{i}", goal_progress=0.2)
            for i in range(8)
        ]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(8)])
        r = _run(flat, plan=plan, goal="g",
                 stagnation=StagnationConfig(max_repeated_observations=99, max_no_progress=3))
        assert r.stop_reason == StopReason.NO_PROGRESS

    def test_stagnation_detector_unit(self):
        det = StagnationDetector(StagnationConfig(max_repeated_observations=2))
        o = PlanObservation(status=ObservationStatus.PARTIAL, summary="x", goal_progress=0.1)
        assert det.observe(o) is None
        assert det.observe(o) == StopReason.STAGNATION_DETECTED


# ---------------------------------------------------------------------------
# Budget preservation (H11 integration)
# ---------------------------------------------------------------------------
class TestBudgetPreservation:
    def test_multiple_replans_share_one_budget_no_reset(self):
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c1"], goal_progress=0.2),
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c2"], goal_progress=0.4),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]

        def ins(plan, o):
            if o.new_constraints:
                return [PlanStep("ins_" + o.new_constraints[0], "x", "do x")] + list(plan.future)
            return list(plan.future)

        budget = RunBudget(RunBudgetLimits())
        r = ReplanningRunner(
            _agent(),
            observation_builder=ScriptedObservationBuilder(obs),
            replanner=RuleBasedReplanner(ins),
            run_budget=budget,
            max_iterations=12,
        ).run("g", _plan("g"))

        assert r.revision_count == 2
        # One model call per executed step, all cumulative on the SAME budget.
        assert budget.usage.iterations == r.iterations
        assert budget.usage.model_calls == r.iterations
        assert r.run_budget is budget

    def test_budget_exhaustion_stops_replanning(self):
        obs = [PlanObservation(status=ObservationStatus.PARTIAL, summary=f"p{i}", goal_progress=i * 0.1) for i in range(10)]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(10)])
        budget = RunBudget(RunBudgetLimits(max_model_calls=3))
        r = ReplanningRunner(
            _agent(),
            observation_builder=ScriptedObservationBuilder(obs),
            run_budget=budget,
            max_iterations=10,
        ).run("g", plan)
        assert r.stop_reason == StopReason.BUDGET_EXHAUSTED
        assert budget.usage.model_calls == 3
        assert budget.termination_reason == TerminationReason.MODEL_CALL_LIMIT


# ---------------------------------------------------------------------------
# Trace reconstruction
# ---------------------------------------------------------------------------
class TestTraceReconstruction:
    def test_every_revision_is_reconstructable(self):
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c"], goal_progress=0.3),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs, replanner=_insert_on_constraint())
        # One trace entry per executed step; the revision entry carries
        # before/after plans, the observation, and the decision reason.
        assert len(r.trace) == r.iterations
        rev_entries = [t for t in r.trace if t["revised"]]
        assert len(rev_entries) == 1
        entry = rev_entries[0]
        assert entry["decision"] == ReplanDecision.REVISE
        assert entry["observation"]["new_constraints"] == ["c"]
        assert "extra" in entry["plan_after"]["pending"]
        assert "extra" not in entry["plan_before"]["pending"]
        # format helper renders without error.
        assert "Replanning trace" in format_replanning_trace(r)


# ---------------------------------------------------------------------------
# Evidence requirements
# ---------------------------------------------------------------------------
class TestEvidence:
    def _adaptive_strategy(self):
        def strat(plan, obs):
            if obs.new_constraints:
                return [PlanStep("extra", "x", "extra " + obs.new_constraints[0])] + list(plan.future)
            return list(plan.future)
        return RuleBasedReplanner(strat)

    def test_evidence1_same_goal_different_observations_different_plans(self):
        # Run A: no constraints -> no revision.
        run_a = _run(
            [
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.5),
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ],
            replanner=self._adaptive_strategy(),
            goal="identical goal",
        )
        # Run B: same goal, a constraint appears -> revised plan.
        run_b = _run(
            [
                PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["x"], goal_progress=0.5),
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ],
            replanner=self._adaptive_strategy(),
            goal="identical goal",
        )
        path_a = [s.step_id for s in run_a.plan.completed_steps()]
        path_b = [s.step_id for s in run_b.plan.completed_steps()]
        assert path_a != path_b                 # different subsequent plans
        assert "extra" in path_b and "extra" not in path_a
        assert run_a.revision_count == 0 and run_b.revision_count == 1

    def test_evidence2_completed_work_never_rewritten(self):
        obs = [
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.3),
            PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c"], goal_progress=0.5),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
            PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
        ]
        r = _run(obs, replanner=_insert_on_constraint())
        # Capture the completed step objects; they must stay COMPLETED and
        # keep their original observation after later revisions.
        s1 = next(s for s in r.plan.history if s.step_id == "s1")
        assert s1.state == PlanStepState.COMPLETED
        assert s1.observation is not None
        # The revision happened at s2, AFTER s1 completed — s1 unaffected.
        assert r.revision_count == 1

    def test_evidence3_revisions_deterministic(self):
        # Same inputs twice -> identical decisions and plan outcome.
        def make_obs():
            return [
                PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["c"], goal_progress=0.3),
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
                PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
            ]
        r1 = _run(make_obs(), replanner=_insert_on_constraint())
        r2 = _run(make_obs(), replanner=_insert_on_constraint())
        assert r1.decisions == r2.decisions
        assert [s.step_id for s in r1.plan.completed_steps()] == [s.step_id for s in r2.plan.completed_steps()]
        assert r1.stop_reason == r2.stop_reason

    def test_evidence4_runtime_governed_by_run_budget(self):
        obs = [PlanObservation(status=ObservationStatus.PARTIAL, summary=f"p{i}", goal_progress=i * 0.05) for i in range(10)]
        plan = Plan.from_steps("g", [PlanStep(f"s{i}", "x", "do x") for i in range(10)])
        budget = RunBudget(RunBudgetLimits(max_iterations=2))
        r = ReplanningRunner(
            _agent(),
            observation_builder=ScriptedObservationBuilder(obs),
            run_budget=budget,
            max_iterations=10,
        ).run("g", plan)
        # The shared budget — not the replanner — stopped execution.
        assert r.stop_reason == StopReason.BUDGET_EXHAUSTED
        assert budget.usage.iterations == 2

    def test_evidence5_decision_policy_pure_deterministic(self):
        policy = DeterministicReplanPolicy()
        plan = _plan()
        # Same observation -> same decision, always.
        o = PlanObservation(status=ObservationStatus.FAILURE, goal_progress=0.0)
        d1 = policy.decide("g", plan, o)
        d2 = policy.decide("g", plan, o)
        assert d1 == d2 == (ReplanDecision.REVISE, "observation status=failure")
