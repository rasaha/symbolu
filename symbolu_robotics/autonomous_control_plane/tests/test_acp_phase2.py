"""ACP Phase-2 physical-safety invariants (stdlib unittest; also under pytest).

Covers the milestone §9 safety invariants using the REAL TrajectoryValidator
adapter. These tests import numpy + the safety module (via the adapter), so they
live with the ACP tests but exercise the integration layer, not the stdlib core.
"""
from __future__ import annotations

import unittest

import numpy as np

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane.physical_evidence import PhysicalValidity
from symbolu_robotics.autonomous_control_plane.safety_adapters.trajectory_adapter import (
    TrajectoryValidatorAdapter)
from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint

WSV = "wsv-1"


def _cand(cid, action_type=acp.ActionType.MANIPULATE, abstract=None):
    meta = {} if abstract is None else {"abstract_safety": repr(abstract)}
    return acp.CanonicalActionCandidate(
        candidate_id=cid, action_type=action_type, trajectory_ref=cid, target="",
        expected_duration_s=1.0, max_speed=0.0, max_accel=0.0, stopping_margin_s=0.0,
        collision_margin_m=0.0, stability_margin=0.0, goal_progress=0.5,
        energy_estimate=0.0, origin_state_version=WSV, metadata=meta)


def _pts(rows):
    # dt = 0.1 s (matches the corpus); SAFE gives 0.5 rad/s, well under the
    # 1.8 rad/s effective limit, while VEL_BREACH gives 10 rad/s.
    return [TrajectoryPoint(timestamp=i * 0.1, positions=np.array(r))
            for i, r in enumerate(rows)]


def _ws(env="v1"):
    return acp.CanonicalWorldState(
        tick=1, observation_time_s=0.1, pose=acp.Pose(0, 0), velocity=acp.Velocity(),
        environment_version=env, mission_id="m",
        freshness=acp.FreshnessSummary(0.01, 1, 0, True),
        operating_mode=acp.OperatingMode.AUTONOMOUS)


SAFE = [[0.0] * 6, [0.05, 0, 0, 0, 0, 0], [0.10, 0, 0, 0, 0, 0]]
VEL_BREACH = [[0.0] * 6, [1.0, 0, 0, 0, 0, 0]]   # 1 rad / 10 ms


class Phase2Safety(unittest.TestCase):
    def setUp(self):
        self.ad = TrajectoryValidatorAdapter()
        self.ws = _ws()

    def _eval(self, cand, rows, freshness=0.01, obstacles=None, human=None):
        return self.ad.evaluate(
            candidate=cand, trajectory_points=_pts(rows), obstacles=obstacles,
            human_position=human, world_version=self.ws.version, now_s=1.0,
            observation_time_s=1.0, freshness_s=freshness)

    def _select(self, cands, cc, sort=lambda c: (0,)):
        return acp.LexicographicActionSelector(sort).select(
            tick=1, decision_id="d", world_state=self.ws, candidates=cands,
            candidate_constraints=cc)

    def test_physically_inadmissible_never_selected(self):
        c = _cand("vel")
        _, results = self._eval(c, VEL_BREACH)
        out = self._select([c], {"vel": results})
        self.assertIsNone(out.selected)
        self.assertIs(out.decision, acp.ActionDecision.NO_SAFE_ACTION)

    def test_abstract_score_cannot_override_physical_failure(self):
        # high abstract safety, but real physical velocity breach -> rejected
        c = _cand("vel", abstract=0.99)
        _, results = self._eval(c, VEL_BREACH)
        # selector ignores metadata abstract score; only physical hard results gate
        out = self._select([c], {"vel": results})
        self.assertIsNone(out.selected)

    def test_missing_physical_evidence_no_execute(self):
        c = _cand("empty")
        ev, results = self._eval(c, [])
        self.assertIs(ev.validity, PhysicalValidity.MISSING)
        out = self._select([c], {"empty": results})
        self.assertNotEqual(out.decision, acp.ActionDecision.EXECUTE)

    def test_stale_evidence_no_execute(self):
        c = _cand("stale")
        ev, results = self._eval(c, SAFE, freshness=5.0)
        self.assertIs(ev.validity, PhysicalValidity.STALE)
        out = self._select([c], {"stale": results})
        self.assertNotEqual(out.decision, acp.ActionDecision.EXECUTE)

    def test_no_safe_survivors_yields_no_safe_action(self):
        a, b = _cand("a"), _cand("b")
        _, ra = self._eval(a, VEL_BREACH)
        _, rb = self._eval(b, [[3.5, 0, 0, 0, 0, 0]])  # position breach
        out = self._select([a, b], {"a": ra, "b": rb})
        self.assertIs(out.decision, acp.ActionDecision.NO_SAFE_ACTION)

    def test_safe_candidate_executes(self):
        c = _cand("safe")
        _, results = self._eval(c, SAFE)
        out = self._select([c], {"safe": results})
        self.assertIs(out.decision, acp.ActionDecision.EXECUTE)
        self.assertEqual(out.selected.candidate_id, "safe")

    def test_evaluator_exception_fails_closed(self):
        c = _cand("boom")

        def _raise(*a, **k):
            raise RuntimeError("safety module blew up")
        self.ad._validator.validate = _raise  # force evaluator failure
        ev, results = self._eval(c, SAFE)
        self.assertIs(ev.validity, PhysicalValidity.EVALUATOR_FAILED)
        self.assertTrue(all(not r.passed for r in results))
        out = self._select([c], {"boom": results})
        self.assertNotEqual(out.decision, acp.ActionDecision.EXECUTE)

    def test_deterministic_reruns_identical(self):
        c = _cand("safe")
        _, r1 = self._eval(c, SAFE, obstacles=[(np.array([0.5, 0, 0.3]), 0.2)])
        _, r2 = self._eval(c, SAFE, obstacles=[(np.array([0.5, 0, 0.3]), 0.2)])
        self.assertEqual([(x.constraint_id, x.passed, x.reason_code) for x in r1],
                         [(x.constraint_id, x.passed, x.reason_code) for x in r2])

    def test_evidence_binding_A_cannot_authorize_B(self):
        a, b = _cand("A"), _cand("B")
        grant = acp.ReferenceControlAuthorizer().authorize(
            decision=acp.ActionDecision.EXECUTE, candidate=a, world_state=self.ws,
            constraint_set_version="cs-1", decision_id="d", issued_time_s=1.0, ttl_s=1.0)
        with self.assertRaises(acp.errors.AuthorizationBindingError):
            acp.ReferenceCommitRevalidator().revalidate(
                authorization=grant, candidate=b, current_world_state=self.ws,
                current_constraint_set_version="cs-1", now_s=1.1)

    def test_state_change_invalidates_authorization(self):
        a = _cand("A")
        grant = acp.ReferenceControlAuthorizer().authorize(
            decision=acp.ActionDecision.EXECUTE, candidate=a, world_state=self.ws,
            constraint_set_version="cs-1", decision_id="d", issued_time_s=1.0, ttl_s=1.0)
        with self.assertRaises(acp.StaleAuthorizationError):
            acp.ReferenceCommitRevalidator().revalidate(
                authorization=grant, candidate=a, current_world_state=_ws("v2"),
                current_constraint_set_version="cs-1", now_s=1.1)


class Phase2ShadowIsolation(unittest.TestCase):
    def test_bench_zero_behavior_change_and_no_actuation(self):
        from robotics_reliability_bench.acp_shadow2.run_shadow2_bench import run
        out = run()
        self.assertTrue(out["shadow_only"])
        self.assertEqual(out["metrics"]["current_runtime_behavior_change_count"], 0)
        self.assertEqual(out["metrics"]["overall"]["acp_inadmissible_selection_count"], 0)
        self.assertEqual(out["metrics"]["deterministic_rerun_identity_pct"], 100.0)

    def test_acp_core_sources_still_stdlib_only(self):
        # The safety adapter subpackage may import numpy/safety, but the CORE
        # modules (excluding safety_adapters/) must remain stdlib-only.
        import pathlib
        import re
        pkg = pathlib.Path(acp.__file__).parent
        forbidden = re.compile(
            r"^\s*(import\s+(numpy|torch|rclpy)|from\s+(numpy|torch|rclpy|"
            r"symbolu_robotics\.(formulas|safety))\b)", re.MULTILINE)
        offenders = []
        for f in pkg.rglob("*.py"):
            if "/tests/" in str(f) or "/safety_adapters/" in str(f):
                continue
            if forbidden.search(f.read_text()):
                offenders.append(f.name)
        self.assertEqual(offenders, [], f"core imports forbidden deps: {offenders}")


if __name__ == "__main__":
    unittest.main()
