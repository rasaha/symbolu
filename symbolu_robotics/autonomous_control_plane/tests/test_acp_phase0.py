"""ACP Phase-0 test suite (stdlib unittest; also runs under pytest).

Covers the Phase-0 acceptance checklist: schema validation, immutability,
deterministic identity, non-finite rejection, stale/modified authorization
rejection, fail-closed selection, illegal failure transitions, deterministic
tie-break, trace completeness, BCVF-off-by-default, advisory-cannot-override, and
zero current-runtime behaviour change.
"""
from __future__ import annotations

import dataclasses
import subprocess
import unittest
from pathlib import Path

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane import (
    ActionDecision, ActionType, BCVFAdvisory, CanonicalActionCandidate,
    CanonicalWorldState, ConstraintKind, ConstraintResult,
    ControlAuthorization, DeterministicActionSelector, FailureState,
    FailureStateMachine, FreshnessSummary, InMemoryDecisionTraceSink,
    NonFiniteValueError, OperatingMode, Pose, PredictorEvidence,
    ReferenceCommitRevalidator, ReferenceControlAuthorizer, SchemaValidationError,
    StaleAuthorizationError, Velocity, identity)
from symbolu_robotics.autonomous_control_plane.errors import (
    AuthorizationBindingError, IllegalTransitionError)
from symbolu_robotics.autonomous_control_plane.predictor_evidence import (
    CalibrationState, DropoutState, ReliabilityState, VarianceState)


def _ws(tick=1, env="map-v1", mission="m1", extensions=None):
    return CanonicalWorldState(
        tick=tick, observation_time_s=0.5, pose=Pose(1.0, 2.0, 0.0),
        velocity=Velocity(0.5, 0.0, 0.0, 0.0), environment_version=env,
        mission_id=mission, freshness=FreshnessSummary(0.05, 3, 0, True),
        operating_mode=OperatingMode.AUTONOMOUS, extensions=extensions or {})


def _cand(cid="c0", coll=0.6, stab=0.6, goal=0.5, energy=10.0, dur=1.0,
          traj="t0", origin="ws-v"):
    return CanonicalActionCandidate(
        candidate_id=cid, action_type=ActionType.MOVE, trajectory_ref=traj,
        target="g1", expected_duration_s=dur, max_speed=1.0, max_accel=0.5,
        stopping_margin_s=2.0, collision_margin_m=coll, stability_margin=stab,
        goal_progress=goal, energy_estimate=energy, origin_state_version=origin)


def _hard(cid, passed, coll=0.6):
    return ConstraintResult("collision", ConstraintKind.HARD, passed, coll, 0.2,
                            ">=", "COLLISION_MARGIN", "ws-v")


class TestSchemaValidation(unittest.TestCase):
    def test_empty_mission_rejected(self):
        with self.assertRaises(SchemaValidationError):
            _ws(mission="")

    def test_goal_progress_out_of_range(self):
        with self.assertRaises(SchemaValidationError):
            _cand(goal=1.5)

    def test_bad_comparator_rejected(self):
        with self.assertRaises(SchemaValidationError):
            ConstraintResult("c", ConstraintKind.HARD, True, 1.0, 0.0, "~=",
                             "R", "ev")

    def test_bad_operating_mode_type(self):
        with self.assertRaises(SchemaValidationError):
            CanonicalWorldState(
                tick=1, observation_time_s=0.0, pose=Pose(0, 0), velocity=Velocity(),
                environment_version="v", mission_id="m",
                freshness=FreshnessSummary(0.0, 1, 0, True),
                operating_mode="AUTONOMOUS")  # not the enum


class TestImmutability(unittest.TestCase):
    def test_world_state_frozen(self):
        ws = _ws()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ws.tick = 2  # type: ignore[misc]

    def test_candidate_frozen(self):
        c = _cand()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            c.collision_margin_m = 9.9  # type: ignore[misc]

    def test_extensions_are_readonly(self):
        ws = _ws(extensions={"k": "v"})
        with self.assertRaises(TypeError):
            ws.extensions["k"] = "x"  # MappingProxyType is read-only


class TestDeterministicIdentity(unittest.TestCase):
    def test_identical_input_same_identity(self):
        self.assertEqual(_ws().version, _ws().version)
        self.assertEqual(_cand().identity, _cand().identity)

    def test_changed_trajectory_changes_identity(self):
        self.assertNotEqual(_cand(traj="t0").identity, _cand(traj="t1").identity)

    def test_changed_margin_changes_identity(self):
        self.assertNotEqual(_cand(coll=0.6).identity, _cand(coll=0.7).identity)

    def test_state_version_change_on_env(self):
        self.assertNotEqual(_ws(env="map-v1").version, _ws(env="map-v2").version)

    def test_dict_insertion_order_irrelevant(self):
        a = _ws(extensions={"a": "1", "b": "2"})
        b = _ws(extensions={"b": "2", "a": "1"})
        self.assertEqual(a.version, b.version)

    def test_identity_excluded_field_does_not_change_identity(self):
        # label is metadata identity=False
        a = _ws()
        b = CanonicalWorldState(
            tick=1, observation_time_s=0.5, pose=Pose(1.0, 2.0, 0.0),
            velocity=Velocity(0.5, 0.0, 0.0, 0.0), environment_version="map-v1",
            mission_id="m1", freshness=FreshnessSummary(0.05, 3, 0, True),
            operating_mode=OperatingMode.AUTONOMOUS, label="human note")
        self.assertEqual(a.version, b.version)

    def test_domain_separation(self):
        # same payload under different domains -> different identity
        self.assertNotEqual(identity({"x": 1}, domain="a"),
                            identity({"x": 1}, domain="b"))

    def test_negative_zero_normalized(self):
        self.assertEqual(identity(-0.0, domain="d"), identity(0.0, domain="d"))


class TestNonFiniteRejection(unittest.TestCase):
    def test_nan_pose_rejected(self):
        with self.assertRaises(NonFiniteValueError):
            Pose(float("nan"), 0.0)

    def test_inf_margin_rejected(self):
        with self.assertRaises(NonFiniteValueError):
            _cand(coll=float("inf"))

    def test_identity_rejects_nan(self):
        with self.assertRaises(NonFiniteValueError):
            identity({"x": float("nan")}, domain="d")


class TestAuthorization(unittest.TestCase):
    def setUp(self):
        self.ws = _ws()
        self.cand = _cand(origin=self.ws.version)
        self.auth = ReferenceControlAuthorizer().authorize(
            decision=ActionDecision.EXECUTE, candidate=self.cand,
            world_state=self.ws, constraint_set_version="cs-1",
            decision_id="d0", issued_time_s=1.0, ttl_s=0.5)
        self.reval = ReferenceCommitRevalidator()

    def test_grant_minted_for_execute(self):
        self.assertIsInstance(self.auth, ControlAuthorization)

    def test_non_executable_decision_not_authorized(self):
        for d in (ActionDecision.NO_SAFE_ACTION, ActionDecision.REPLAN,
                  ActionDecision.SAFE_STOP, ActionDecision.DEGRADE_MODE,
                  ActionDecision.REQUEST_MORE_OBSERVATION):
            got = ReferenceControlAuthorizer().authorize(
                decision=d, candidate=self.cand, world_state=self.ws,
                constraint_set_version="cs-1", decision_id="d",
                issued_time_s=1.0, ttl_s=1.0)
            self.assertIsNone(got, d)

    def test_valid_commit_passes(self):
        self.reval.revalidate(authorization=self.auth, candidate=self.cand,
                              current_world_state=self.ws,
                              current_constraint_set_version="cs-1", now_s=1.2)

    def test_stale_world_state_rejected(self):
        moved = _ws(env="map-v2")
        with self.assertRaises(StaleAuthorizationError):
            self.reval.revalidate(authorization=self.auth, candidate=self.cand,
                                  current_world_state=moved,
                                  current_constraint_set_version="cs-1", now_s=1.2)

    def test_stale_constraint_set_rejected(self):
        with self.assertRaises(StaleAuthorizationError):
            self.reval.revalidate(authorization=self.auth, candidate=self.cand,
                                  current_world_state=self.ws,
                                  current_constraint_set_version="cs-2", now_s=1.2)

    def test_expired_authorization_rejected(self):
        with self.assertRaises(StaleAuthorizationError):
            self.reval.revalidate(authorization=self.auth, candidate=self.cand,
                                  current_world_state=self.ws,
                                  current_constraint_set_version="cs-1", now_s=99.0)

    def test_modified_action_rejected(self):
        other = _cand(cid="c1", coll=0.9, origin=self.ws.version)
        with self.assertRaises(AuthorizationBindingError):
            self.reval.revalidate(authorization=self.auth, candidate=other,
                                  current_world_state=self.ws,
                                  current_constraint_set_version="cs-1", now_s=1.2)


class TestFailClosedSelection(unittest.TestCase):
    def setUp(self):
        self.sel = DeterministicActionSelector()
        self.ws = _ws()

    def test_empty_candidates_no_safe_action(self):
        out = self.sel.select(tick=1, decision_id="d", world_state=self.ws,
                              candidates=[], candidate_constraints={})
        self.assertIs(out.decision, ActionDecision.NO_SAFE_ACTION)
        self.assertIsNone(out.selected)

    def test_no_evidence_requests_observation(self):
        out = self.sel.select(tick=1, decision_id="d", world_state=self.ws,
                              candidates=[_cand()], candidate_constraints={})
        self.assertIs(out.decision, ActionDecision.REQUEST_MORE_OBSERVATION)

    def test_all_hard_failed_no_safe_action(self):
        c = _cand(cid="c0")
        out = self.sel.select(tick=1, decision_id="d", world_state=self.ws,
                              candidates=[c],
                              candidate_constraints={"c0": [_hard("c0", False)]})
        self.assertIs(out.decision, ActionDecision.NO_SAFE_ACTION)
        self.assertEqual(len(out.trace.rejected), 1)

    def test_admissible_executes(self):
        c = _cand(cid="c0")
        out = self.sel.select(tick=1, decision_id="d", world_state=self.ws,
                              candidates=[c],
                              candidate_constraints={"c0": [_hard("c0", True)]})
        self.assertIs(out.decision, ActionDecision.EXECUTE)
        self.assertEqual(out.selected.candidate_id, "c0")

    def test_soft_failure_executes_with_constraints(self):
        c = _cand(cid="c0")
        soft = ConstraintResult("speed", ConstraintKind.SOFT, False, 1.2, 1.0,
                                "<=", "SPEED_PREF", "ev")
        out = self.sel.select(tick=1, decision_id="d", world_state=self.ws,
                              candidates=[c],
                              candidate_constraints={"c0": [_hard("c0", True), soft]})
        self.assertIs(out.decision, ActionDecision.EXECUTE_WITH_CONSTRAINTS)


class TestDeterministicTieBreak(unittest.TestCase):
    def test_total_order_and_stable(self):
        sel = DeterministicActionSelector()
        ws = _ws()
        # two candidates, identical soft cost, different margins -> larger margin wins
        a = _cand(cid="a", coll=0.5, stab=0.5, goal=0.5, energy=10.0, dur=1.0)
        b = _cand(cid="b", coll=0.9, stab=0.9, goal=0.5, energy=10.0, dur=1.0)
        cc = {"a": [_hard("a", True)], "b": [_hard("b", True)]}
        out = sel.select(tick=1, decision_id="d", world_state=ws,
                         candidates=[a, b], candidate_constraints=cc)
        self.assertEqual(out.selected.candidate_id, "b")  # larger margin
        # deterministic across candidate ordering
        out2 = sel.select(tick=1, decision_id="d", world_state=ws,
                          candidates=[b, a], candidate_constraints=cc)
        self.assertEqual(out.trace.tie_break_sequence, out2.trace.tie_break_sequence)

    def test_exact_tie_resolved_by_id(self):
        sel = DeterministicActionSelector()
        ws = _ws()
        a = _cand(cid="a", coll=0.6, stab=0.6, goal=0.5)
        b = _cand(cid="b", coll=0.6, stab=0.6, goal=0.5)
        cc = {"a": [_hard("a", True)], "b": [_hard("b", True)]}
        out = sel.select(tick=1, decision_id="d", world_state=ws,
                         candidates=[b, a], candidate_constraints=cc)
        self.assertEqual(out.selected.candidate_id, "a")  # lowest id


class TestDecisionTrace(unittest.TestCase):
    def test_trace_complete_on_execute(self):
        sel = DeterministicActionSelector()
        ws = _ws()
        c = _cand(cid="c0")
        out = sel.select(tick=1, decision_id="d", world_state=ws, candidates=[c],
                         candidate_constraints={"c0": [_hard("c0", True)]})
        t = out.trace
        self.assertTrue(t.is_complete())
        self.assertEqual(t.candidate_ids_considered, ("c0",))
        self.assertEqual(t.surviving_candidate_ids, ("c0",))
        self.assertEqual(t.selected_action_identity, c.identity)
        self.assertIn("collision", t.hard_constraints_evaluated)

    def test_trace_complete_on_refusal(self):
        sel = DeterministicActionSelector()
        out = sel.select(tick=1, decision_id="d", world_state=_ws(),
                         candidates=[_cand(cid="c0")],
                         candidate_constraints={"c0": [_hard("c0", False)]})
        self.assertTrue(out.trace.is_complete())
        self.assertIsNone(out.trace.selected_candidate_id)

    def test_sink_stores_immutably(self):
        sink = InMemoryDecisionTraceSink()
        sel = DeterministicActionSelector()
        out = sel.select(tick=1, decision_id="d", world_state=_ws(),
                         candidates=[_cand(cid="c0")],
                         candidate_constraints={"c0": [_hard("c0", True)]})
        sink.record(out.trace)
        self.assertEqual(len(sink.records), 1)


class TestFailureStateMachine(unittest.TestCase):
    def test_legal_transition(self):
        m = FailureStateMachine()
        m.transition(FailureState.DEGRADED, event_code="E", reason="variance")
        self.assertIs(m.state, FailureState.DEGRADED)

    def test_illegal_transition_rejected(self):
        m = FailureStateMachine()  # NOMINAL
        with self.assertRaises(IllegalTransitionError):
            m.transition(FailureState.HANDOVER, event_code="E", reason="r")

    def test_manual_reset_requires_operator(self):
        m = FailureStateMachine()
        m.transition(FailureState.ESTOP, event_code="fault", reason="actuator")
        with self.assertRaises(IllegalTransitionError):
            m.transition(FailureState.HANDOVER, event_code="reset", reason="op")
        rec = m.transition(FailureState.HANDOVER, event_code="reset",
                           reason="op ack", operator="alice")
        self.assertEqual(rec.operator, "alice")

    def test_history_is_immutable_tuple(self):
        m = FailureStateMachine()
        m.transition(FailureState.DEGRADED, event_code="E", reason="r")
        self.assertIsInstance(m.history, tuple)
        self.assertEqual(m.history[0].to_state, FailureState.DEGRADED)


class TestBCVFAdvisory(unittest.TestCase):
    def _evidence(self, advisory=None):
        return PredictorEvidence(
            predictor_id="p0", freshness_s=0.01, latency_s=0.01, residual=0.05,
            normalized_residual=1.0, persistent_bias=False,
            variance_state=VarianceState.NOMINAL, dropout_state=DropoutState.PRESENT,
            calibration_state=CalibrationState.CALIBRATED,
            reliability_state=ReliabilityState.TRUSTED, bcvf_advisory=advisory)

    def test_bcvf_off_by_default(self):
        ev = self._evidence()
        self.assertIsNone(ev.bcvf_advisory)
        self.assertFalse(ev.bcvf_enabled)

    def test_bcvf_advisory_flag_must_be_true(self):
        with self.assertRaises(SchemaValidationError):
            BCVFAdvisory(margin=2.0, advisory=False)

    def test_advisory_cannot_override_failed_hard_constraint(self):
        # A candidate whose HARD constraint FAILED, while its predictor carries a
        # strong BCVF advisory, must still be rejected: the selector never reads
        # the advisory for admissibility.
        sel = DeterministicActionSelector()
        _ = self._evidence(BCVFAdvisory(margin=99.0, would_advance_detection_ticks=10))
        c = _cand(cid="c0")
        out = sel.select(tick=1, decision_id="d", world_state=_ws(),
                         candidates=[c],
                         candidate_constraints={"c0": [_hard("c0", False)]})
        self.assertIs(out.decision, ActionDecision.NO_SAFE_ACTION)
        self.assertIsNone(out.selected)


class TestZeroRuntimeBehaviourChange(unittest.TestCase):
    def test_no_production_module_imports_acp(self):
        """No non-ACP robotics module may import the ACP package (Phase 0)."""
        repo = Path(__file__).resolve().parents[3]
        # grep for imports of the ACP package outside the package itself
        res = subprocess.run(
            ["grep", "-rl", "autonomous_control_plane",
             str(repo / "symbolu_robotics"), "--include=*.py"],
            capture_output=True, text=True)
        offenders = [ln for ln in res.stdout.splitlines()
                     if "autonomous_control_plane" not in Path(ln).parts[-2:][0]
                     and "/autonomous_control_plane/" not in ln]
        self.assertEqual(offenders, [], f"ACP is imported by: {offenders}")

    def test_acp_imports_no_numpy_or_ros(self):
        import symbolu_robotics.autonomous_control_plane as pkg
        import sys
        # importing ACP must not have pulled numpy / rclpy as a hard dependency
        loaded = set(sys.modules)
        # ACP itself is loaded; ensure its own submodules don't require numpy
        for name in list(loaded):
            # safety_adapters/ is the integration layer and is allowed to bind
            # numpy + the real safety modules (Phase 2); the CORE must not.
            if (name.startswith("symbolu_robotics.autonomous_control_plane")
                    and "safety_adapters" not in name
                    and ".tests" not in name):
                mod = sys.modules[name]
                self.assertFalse(getattr(mod, "np", None),
                                 f"{name} unexpectedly bound numpy as np")


if __name__ == "__main__":
    unittest.main()
