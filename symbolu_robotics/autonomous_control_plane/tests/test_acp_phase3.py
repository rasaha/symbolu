"""ACP Phase-3 live-path invariants + compatibility (stdlib unittest / pytest).

Exercises the disabled-by-default shadow hook around the REAL deliberative
TaskPlanner, the production-shaped live-path adapter, and the real
TrajectoryValidator. Proves the milestone §10 safety invariants + the §4 hook
compatibility guarantees.
"""
from __future__ import annotations

import unittest

import numpy as np

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane.safety_adapters.live_planner_adapter import (
    LivePathStatus, plan_to_trajectory_candidate)
from symbolu_robotics.autonomous_control_plane.safety_adapters.shadow_planner_hook import (
    BoundedShadowSink, InstrumentedTaskPlanner, ShadowPlannerHook)
from symbolu_robotics.autonomous_control_plane.safety_adapters.trajectory_adapter import (
    TrajectoryValidatorAdapter)
from symbolu_robotics.core.chitta_vritti import compute_vritti
from symbolu_robotics.core.types import ActuatorCommand, Goal, Plan
from symbolu_robotics.tiers.deliberative import TaskPlanner, WorldModel


def _ws(env="v1"):
    return acp.CanonicalWorldState(
        tick=1, observation_time_s=0.1, pose=acp.Pose(0, 0), velocity=acp.Velocity(),
        environment_version=env, mission_id="m",
        freshness=acp.FreshnessSummary(0.01, 1, 0, True),
        operating_mode=acp.OperatingMode.AUTONOMOUS)


def _cmd_plan(vel):
    return Plan(actions=[ActuatorCommand(target_velocities=np.array(vel, dtype=float),
                                         control_mode="velocity")], estimated_duration=0.5)


def _hook(enabled=True):
    return ShadowPlannerHook(sink=BoundedShadowSink(), enabled=enabled,
                             validator_adapter=TrajectoryValidatorAdapter())


class LivePathAdapter(unittest.TestCase):
    def test_missing_trajectory_fails_closed(self):
        r = plan_to_trajectory_candidate(action_id="a", plan=Plan(actions=[]),
                                         world_version="v", q0=np.zeros(6),
                                         planner_provenance="p")
        self.assertIs(r.status, LivePathStatus.MISSING_TRAJECTORY)

    def test_gripper_unsupported(self):
        plan = Plan(actions=[ActuatorCommand(gripper_position=0.0, gripper_force=30.0)])
        r = plan_to_trajectory_candidate(action_id="a", plan=plan, world_version="v",
                                         q0=np.zeros(6), planner_provenance="p")
        self.assertIs(r.status, LivePathStatus.UNSUPPORTED_COMMAND)

    def test_dimension_mismatch(self):
        r = plan_to_trajectory_candidate(action_id="a", plan=_cmd_plan([0.5, 0, 0]),
                                         world_version="v", q0=np.zeros(6),
                                         planner_provenance="p")
        self.assertIs(r.status, LivePathStatus.DIMENSION_MISMATCH)

    def test_nonfinite(self):
        r = plan_to_trajectory_candidate(action_id="a",
                                         plan=_cmd_plan([float("nan"), 0, 0, 0, 0, 0]),
                                         world_version="v", q0=np.zeros(6),
                                         planner_provenance="p")
        self.assertIs(r.status, LivePathStatus.NONFINITE)

    def test_identity_mismatch(self):
        r = plan_to_trajectory_candidate(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                                         world_version="v1", q0=np.zeros(6),
                                         planner_provenance="p", expected_state_version="v2")
        self.assertIs(r.status, LivePathStatus.IDENTITY_MISMATCH)


class Phase3Invariants(unittest.TestCase):
    def test_validator_failed_trajectory_never_admissible(self):
        h = _hook()
        rec = h.observe(action_id="vel", plan=_cmd_plan([10, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), now_s=1.0)
        self.assertFalse(rec.acp_admissible)
        self.assertEqual(rec.acp_decision, acp.ActionDecision.NO_SAFE_ACTION.value)

    def test_missing_trajectory_no_execute(self):
        h = _hook()
        rec = h.observe(action_id="empty", plan=Plan(actions=[]), world_state=_ws(),
                        q0=np.zeros(6), now_s=1.0)
        self.assertNotEqual(rec.acp_decision, acp.ActionDecision.EXECUTE.value)

    def test_stale_state_no_execute(self):
        h = _hook()
        rec = h.observe(action_id="stale", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), freshness_s=5.0, now_s=1.0)
        self.assertFalse(rec.acp_admissible)

    def test_commit_state_change_invalidates(self):
        h = _hook()
        h.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]), world_state=_ws(),
                  q0=np.zeros(6), now_s=1.0)
        cand = h._last["candidate"]
        res = h.commit_revalidate(candidate=cand, current_world_state=_ws("v2"),
                                  now_s=1.0, evidence_time_s=1.0)
        self.assertFalse(res["revalidated"])

    def test_commit_modified_trajectory_invalidates(self):
        h = _hook()
        h.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]), world_state=_ws(),
                  q0=np.zeros(6), now_s=1.0)
        cand = h._last["candidate"]
        other = acp.CanonicalActionCandidate(
            candidate_id=cand.candidate_id, action_type=acp.ActionType.MANIPULATE,
            trajectory_ref="MODIFIED", target="", expected_duration_s=1.0, max_speed=0.0,
            max_accel=0.0, stopping_margin_s=0.0, collision_margin_m=0.0,
            stability_margin=0.0, goal_progress=0.5, energy_estimate=0.0,
            origin_state_version=_ws().version)
        res = h.commit_revalidate(candidate=other, current_world_state=_ws(),
                                  now_s=1.0, evidence_time_s=1.0)
        self.assertFalse(res["revalidated"])

    def test_deterministic_reruns(self):
        h1, h2 = _hook(), _hook()
        r1 = h1.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), now_s=1.0)
        r2 = h2.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), now_s=1.0)
        self.assertEqual(r1.content_dict(), r2.content_dict())


class Phase3HookCompatibility(unittest.TestCase):
    def _live_planner(self, hook):
        tp = TaskPlanner()
        tp.push_goal(Goal(description="move to location",
                          target_pose=np.array([0.5, 0, 0.3]), priority=0.7))
        s12 = np.full(12, 0.5)
        return (InstrumentedTaskPlanner(tp, hook), s12, WorldModel(),
                compute_vritti(s12)[0])

    def test_hook_off_returns_none_no_record(self):
        h = _hook(enabled=False)
        rec = h.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6))
        self.assertIsNone(rec)
        self.assertEqual(len(h.sink.records), 0)

    def test_hook_off_vs_on_identical_plan(self):
        h = _hook(enabled=False)
        inst, s12, world, vritti = self._live_planner(h)
        ctx = dict(action_id="a", world_state=_ws(), q0=np.zeros(6))
        p_off = inst.plan(s12, world, vritti, shadow_context=ctx)
        h.enabled = True
        p_on = inst.plan(s12, world, vritti, shadow_context=ctx)
        self.assertTrue(np.array_equal(p_off.actions[0].target_velocities,
                                       p_on.actions[0].target_velocities))
        self.assertEqual(p_off.estimated_duration, p_on.estimated_duration)

    def test_hook_exception_contained(self):
        # a validator that raises must not escape observe; plan still returns.
        h = _hook()
        h._adapter._validator.validate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
        rec = h.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), now_s=1.0)
        # trajectory validation raised inside -> adapter returns EVALUATOR_FAILED,
        # which the hook records without propagating.
        self.assertFalse(rec.acp_admissible)

    def test_instrumented_planner_delegates_and_propagates_planner_error(self):
        class Boom:
            def plan(self, *a, **k):
                raise ValueError("planner failed")
            attr = 42
        h = _hook()
        inst = InstrumentedTaskPlanner(Boom(), h)
        self.assertEqual(inst.attr, 42)  # delegation
        with self.assertRaises(ValueError):  # planner exception unchanged
            inst.plan(shadow_context=dict(action_id="a", world_state=_ws(), q0=np.zeros(6)))

    def test_bounded_sink_cannot_grow_unbounded(self):
        sink = BoundedShadowSink(maxlen=3)
        from symbolu_robotics.autonomous_control_plane.safety_adapters.shadow_planner_hook import ShadowRecord3
        for i in range(10):
            sink.append(ShadowRecord3(
                action_id=str(i), world_state_identity="w", candidate_identity=None,
                planner_provenance="p", live_status="X", physical_validity=None,
                is_safe=None, acp_decision="NO_SAFE_ACTION", acp_admissible=False,
                dispositive_reasons=(), safety_score=None, ttc_s=None,
                adapter_latency_us=0.0, validator_latency_us=0.0,
                total_shadow_latency_us=0.0, shadow_error=False))
        self.assertEqual(len(sink.records), 3)   # capped
        self.assertEqual(sink.dropped, 7)        # evictions counted
        self.assertEqual(sink.seen, 10)

    def test_no_actuation_records_shadow_only(self):
        h = _hook()
        rec = h.observe(action_id="a", plan=_cmd_plan([0.5, 0, 0, 0, 0, 0]),
                        world_state=_ws(), q0=np.zeros(6), now_s=1.0)
        self.assertTrue(rec.shadow_only)
        self.assertTrue(all(r.shadow_only for r in h.sink.records))


if __name__ == "__main__":
    unittest.main()
