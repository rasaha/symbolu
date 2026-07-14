"""ACP Phase-1 shadow invariants (stdlib unittest; also runs under pytest).

Covers the milestone's §9 security/safety invariants for the hard-admissibility
filter, adapters, and shadow evaluation, plus a determinism + shadow-isolation
check on the benchmark.
"""
from __future__ import annotations

import unittest

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane import (ActionDecision,
                                                       ShadowClass)


class TestInadmissibleNeverSelected(unittest.TestCase):
    def test_bcvf_attractive_but_unsafe_is_rejected(self):
        # RISKY has the most attractive scores but safety 0.3 < 0.5 floor.
        aset = acp.adapt_conflict(tick=1, conflict_id="c", env_version="v", strategies=[
            {"id": "SAFE", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.6, "priority_score": 0.5, "safety_score": 0.9},
            {"id": "RISKY", "strategy": "RESOURCE_SHARING", "forward_score": 0.95,
             "backward_score": 0.98, "priority_score": 0.9, "safety_score": 0.3}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        self.assertNotEqual(out.selected.candidate_id, "RISKY")
        self.assertNotIn("RISKY", out.trace.surviving_candidate_ids)

    def test_all_unsafe_no_stop_yields_no_safe_action(self):
        aset = acp.adapt_conflict(tick=1, conflict_id="c", env_version="v", strategies=[
            {"id": "A", "strategy": "PRIORITY_YIELD", "forward_score": 0.6,
             "backward_score": 0.7, "priority_score": 0.4, "safety_score": 0.35},
            {"id": "B", "strategy": "RESOURCE_SHARING", "forward_score": 0.7,
             "backward_score": 0.8, "priority_score": 0.5, "safety_score": 0.2}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        self.assertIs(out.decision, ActionDecision.NO_SAFE_ACTION)
        self.assertIsNone(out.selected)


class TestMissingEvidenceNeverExecutesUnsafe(unittest.TestCase):
    def test_missing_obstacle_move_not_executed(self):
        # A move with no obstacle evidence must not be selected for EXECUTE.
        aset = acp.adapt_deliberative(tick=1, mission_id="m", env_version="v", actions=[
            {"id": "move", "action": "move_to", "goal_progress": 0.9, "feasibility": 0.7}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        # only candidate is an unevaluable move -> cannot EXECUTE it
        self.assertIsNone(out.selected)
        self.assertNotEqual(out.decision, ActionDecision.EXECUTE)

    def test_safe_fallback_survives_when_motion_unevaluable(self):
        aset = acp.adapt_deliberative(tick=1, mission_id="m", env_version="v", actions=[
            {"id": "move", "action": "move_to", "goal_progress": 0.9, "feasibility": 0.7},
            {"id": "wait", "action": "wait", "goal_progress": 0.2, "feasibility": 0.7}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        self.assertEqual(out.selected.candidate_id, "wait")
        self.assertIs(out.decision, ActionDecision.EXECUTE)


class TestAdvisoryCannotOverride(unittest.TestCase):
    def test_advisory_never_read_by_selector(self):
        # The lexicographic selector consumes only constraint results + the
        # frozen sort key; a strong advisory on evidence cannot admit RISKY.
        aset = acp.adapt_conflict(tick=1, conflict_id="c", env_version="v", strategies=[
            {"id": "RISKY", "strategy": "RESOURCE_SHARING", "forward_score": 1.0,
             "backward_score": 1.0, "priority_score": 1.0, "safety_score": 0.1}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        self.assertIs(out.decision, ActionDecision.NO_SAFE_ACTION)


class TestAuthorizationInvariants(unittest.TestCase):
    def _grant(self):
        aset = acp.adapt_conflict(tick=1, conflict_id="c", env_version="v1", strategies=[
            {"id": "SAFE", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9}])
        out = acp.acp_evaluate(aset, tick=1, decision_id="d")
        grant = acp.ReferenceControlAuthorizer().authorize(
            decision=out.decision, candidate=out.selected, world_state=aset.world_state,
            constraint_set_version="cs-1", decision_id="d", issued_time_s=1.0, ttl_s=1.0)
        return aset, out.selected, grant

    def test_stale_state_invalidates(self):
        aset, cand, grant = self._grant()
        moved = acp.adapt_conflict(tick=2, conflict_id="c", env_version="v2", strategies=[
            {"id": "SAFE", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.9}])
        with self.assertRaises(acp.StaleAuthorizationError):
            acp.ReferenceCommitRevalidator().revalidate(
                authorization=grant, candidate=cand,
                current_world_state=moved.world_state,
                current_constraint_set_version="cs-1", now_s=1.2)

    def test_modified_action_invalidates(self):
        aset, cand, grant = self._grant()
        other = acp.adapt_conflict(tick=1, conflict_id="c2", env_version="v1", strategies=[
            {"id": "SAFE", "strategy": "SPATIAL_AVOIDANCE", "forward_score": 0.8,
             "backward_score": 0.7, "priority_score": 0.5, "safety_score": 0.55}])
        with self.assertRaises(acp.errors.AuthorizationBindingError):
            acp.ReferenceCommitRevalidator().revalidate(
                authorization=grant, candidate=other.candidates[0],
                current_world_state=aset.world_state,
                current_constraint_set_version="cs-1", now_s=1.2)


class TestShadowIsolationAndDeterminism(unittest.TestCase):
    def test_acp_module_sources_are_stdlib_only(self):
        # The ACP module SOURCES must not import numpy / torch / ROS / the
        # production BCVF scorer. (Note: importing ACP via the package path also
        # runs symbolu_robotics/__init__.py, which itself eagerly imports numpy +
        # BCVF — a property of the existing parent package, documented in
        # ACP_PHASE1_RESULTS.md, not of ACP's own code.)
        import pathlib
        import re
        pkg = pathlib.Path(acp.__file__).parent
        forbidden = re.compile(
            r"^\s*(import\s+(numpy|torch|rclpy)|"
            r"from\s+(numpy|torch|rclpy|symbolu_robotics\.formulas)\b)",
            re.MULTILINE)
        offenders = []
        for f in pkg.rglob("*.py"):
            if "/tests/" in str(f):
                continue
            if forbidden.search(f.read_text()):
                offenders.append(f.name)
        self.assertEqual(offenders, [], f"ACP sources import forbidden deps: {offenders}")

    def test_deterministic_rerun_identity(self):
        from robotics_reliability_bench.acp_shadow.run_shadow_bench import run
        a = run()
        b = run()
        ra = [r for r in a["records"]]
        rb = [r for r in b["records"]]
        # strip wall-clock latency, compare decision content
        for x, y in zip(ra, rb):
            x = dict(x); y = dict(y)
            x.pop("latency_us", None); y.pop("latency_us", None)
            self.assertEqual(x, y)
        self.assertEqual(a["metrics"]["deterministic_rerun_identity_pct"], 100.0)

    def test_shadow_records_are_shadow_only_and_no_actuation(self):
        from robotics_reliability_bench.acp_shadow.run_shadow_bench import run
        out = run()
        self.assertTrue(out["shadow_only"])
        for r in out["records"]:
            self.assertTrue(r["shadow_only"])
        self.assertEqual(out["metrics"]["current_runtime_behavior_change_count"], 0)

    def test_shadow_exception_is_contained(self):
        # A malformed adapter input raises inside ACP; it is a normal exception
        # the harness can catch (-> SHADOW_ERROR), never a production mutation.
        with self.assertRaises(Exception):
            acp.adapt_conflict(tick=1, conflict_id="c", env_version="v",
                               strategies=[{"id": "x"}])  # missing required keys


if __name__ == "__main__":
    unittest.main()
