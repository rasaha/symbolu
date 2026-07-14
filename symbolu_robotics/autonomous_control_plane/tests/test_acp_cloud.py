"""ACP V2 cloud-adapter invariants + cross-domain reuse (stdlib unittest / pytest).

Proves (a) the cloud adapter reuses the FROZEN ACP core unchanged, (b) the §13
safety invariants of the ActionGate x ACP composition, (c) fail-closed behaviour
on every degraded-evidence path, and (d) the shadow adapter never actuates and is
OFF by default. Consumes the repository's REAL ``cloud_controller`` readiness /
policy / safety logic through the evaluator.
"""
from __future__ import annotations

import unittest

from symbolu_robotics.autonomous_control_plane.action_selection import (
    LexicographicActionSelector,
    filter_admissible,
)
from symbolu_robotics.autonomous_control_plane.constraints import ConstraintKind
from symbolu_robotics.autonomous_control_plane.envelopes import ActionDecision
from symbolu_robotics.autonomous_control_plane.cloud import (
    AuthorizationVerdict,
    CloudActionCandidate,
    CloudConstraintEvaluator,
    CloudOperation,
    CloudRecommendation,
    CloudShadowAdapter,
    CloudValidity,
    CloudWorldState,
    CombinedOutcome,
    compose,
    cloud_recommendation,
    is_permissive,
)

NOW = 1_000_000.0


def _ws(**kw):
    base = dict(
        cluster="gke", namespace="default", deployment="demo-app",
        resource_version="1", generation=1, desired_replicas=3,
        current_replicas=3, available_replicas=3, readiness_plasticity=0.80,
        active_rollback_watches=0, seconds_since_last_action=600.0,
        dependency_healthy=True, freeze_active=False, observation_time_s=NOW)
    base.update(kw)
    return CloudWorldState(**base)


def _c(version, **kw):
    base = dict(
        candidate_id="c1", operation=CloudOperation.SCALE, namespace="default",
        deployment="demo-app", current_replicas=3, desired_replicas=4,
        manifest_digest="", rollback_ref="", rollout_strategy="RollingUpdate",
        max_unavailable=1, max_surge=1, timeout_s=60.0, origin_state_version=version)
    base.update(kw)
    return CloudActionCandidate(**base)


class TestCloudEnvelopeIdentity(unittest.TestCase):
    def test_domain_separated_identity(self):
        ws = _ws()
        c = _c(ws.version)
        # state and candidate identities are domain-separated (never collide).
        self.assertNotEqual(ws.version, c.identity)

    def test_identity_is_deterministic(self):
        self.assertEqual(_ws().version, _ws().version)

    def test_blast_radius(self):
        ws = _ws()
        self.assertEqual(_c(ws.version, desired_replicas=7).blast_radius, 4)  # |7-3|
        d = _c(ws.version, operation=CloudOperation.DELETE, current_replicas=5,
               desired_replicas=0, rollback_ref="rb")
        self.assertEqual(d.blast_radius, 5)
        self.assertTrue(d.is_destructive)


class TestRealModuleEvaluator(unittest.TestCase):
    """The evaluator drives HARD results from the REAL cloud_controller logic."""

    def test_healthy_all_hard_pass(self):
        ws = _ws()
        ev, res = CloudConstraintEvaluator().evaluate(
            _c(ws.version), ws, now_s=NOW, freshness_s=2.0)
        self.assertIs(ev.validity, CloudValidity.VALID)
        self.assertTrue(all(r.kind is ConstraintKind.HARD for r in res))
        self.assertFalse(any(r.blocks_admissibility for r in res))

    def test_real_readiness_blocks_recent_action(self):
        # Real ReadinessChecker: action 30s ago < 120s threshold => NOT_READY.
        ws = _ws(seconds_since_last_action=30.0)
        ev, res = CloudConstraintEvaluator().evaluate(
            _c(ws.version), ws, now_s=NOW, freshness_s=2.0)
        self.assertFalse(ev.readiness_ok)
        self.assertTrue(any(r.constraint_id == "READINESS_OK"
                            and not r.passed for r in res))

    def test_real_safetybounds_blocks_excessive_scale(self):
        # Real SafetyBounds +50% bound: 3 -> 90 is way over.
        ws = _ws()
        _, res = CloudConstraintEvaluator().evaluate(
            _c(ws.version, desired_replicas=90), ws, now_s=NOW, freshness_s=2.0)
        self.assertTrue(any(r.constraint_id == "BLAST_RADIUS_WITHIN_BOUND"
                            and not r.passed for r in res))

    def test_real_policy_blocks_over_max(self):
        ws = _ws()
        _, res = CloudConstraintEvaluator(
        ).evaluate(_c(ws.version, desired_replicas=200), ws, now_s=NOW,
                   freshness_s=2.0)
        self.assertTrue(any(r.constraint_id == "REPLICA_WITHIN_LIMIT"
                            and not r.passed for r in res))


class TestFailClosed(unittest.TestCase):
    def test_stale_fails_closed(self):
        ws = _ws()
        ev, res = CloudConstraintEvaluator().evaluate(
            _c(ws.version), ws, now_s=NOW, freshness_s=999.0)
        self.assertIs(ev.validity, CloudValidity.STALE)
        self.assertTrue(any(r.blocks_admissibility for r in res))

    def test_missing_state_fails_closed(self):
        ev, res = CloudConstraintEvaluator().evaluate(
            _c("x"), None, now_s=NOW, freshness_s=2.0)
        self.assertIs(ev.validity, CloudValidity.MISSING)
        self.assertTrue(any(r.blocks_admissibility for r in res))

    def test_binding_mismatch_fails_closed(self):
        ws = _ws()
        ev, res = CloudConstraintEvaluator().evaluate(
            _c("wrong-version"), ws, now_s=NOW, freshness_s=2.0)
        self.assertIs(ev.validity, CloudValidity.MISSING)
        self.assertTrue(any(r.blocks_admissibility for r in res))

    def test_evaluator_exception_fails_closed(self):
        # A candidate whose real-module call raises must fail closed, not pass.
        class Boom(CloudConstraintEvaluator):
            def _evaluate_valid(self, *a, **k):
                raise RuntimeError("boom")
        ws = _ws()
        ev, res = Boom().evaluate(_c(ws.version), ws, now_s=NOW, freshness_s=2.0)
        self.assertIs(ev.validity, CloudValidity.EVALUATOR_FAILED)
        self.assertTrue(any(r.blocks_admissibility for r in res))


class TestFrozenCoreReuse(unittest.TestCase):
    """The frozen selector + filter run UNCHANGED on cloud envelopes."""

    def test_frozen_selector_executes_on_cloud(self):
        ws = _ws()
        c = _c(ws.version)
        _, res = CloudConstraintEvaluator().evaluate(
            c, ws, now_s=NOW, freshness_s=2.0)
        sel = LexicographicActionSelector(sort_key=lambda cc: (cc.blast_radius,))
        out = sel.select(tick=0, decision_id="d", world_state=ws,
                         candidates=[c], candidate_constraints={c.candidate_id: res})
        self.assertIs(out.decision, ActionDecision.EXECUTE)
        self.assertEqual(out.trace.world_state_identity, ws.version)
        self.assertEqual(out.trace.selected_action_identity, c.identity)

    def test_filter_admissible_fail_closed_no_evidence(self):
        ws = _ws()
        c = _c(ws.version)
        adm = filter_admissible([c], {})  # no hard evidence
        self.assertEqual(adm.admissible, ())
        self.assertEqual(adm.rejected[0].reason_code, "NO_HARD_EVIDENCE")


class TestComposition(unittest.TestCase):
    """§13 ActionGate x ACP composition invariants."""

    def test_deny_never_overridden(self):
        r = compose(AuthorizationVerdict.DENY, CloudRecommendation.PROCEED)
        self.assertIs(r.combined, CombinedOutcome.BLOCKED_BY_AUTHORIZATION)
        self.assertFalse(r.would_proceed)

    def test_acp_hold_never_proceeds(self):
        for v in (AuthorizationVerdict.ALLOW,
                  AuthorizationVerdict.ALLOW_WITH_CONSTRAINTS):
            r = compose(v, CloudRecommendation.HOLD)
            self.assertIs(r.combined, CombinedOutcome.HELD_BY_ACP)
            self.assertFalse(r.would_proceed)
            self.assertTrue(r.acp_was_decisive)

    def test_proceed_requires_both(self):
        r = compose(AuthorizationVerdict.ALLOW, CloudRecommendation.PROCEED)
        self.assertIs(r.combined, CombinedOutcome.PROCEED)
        self.assertTrue(r.would_proceed)

    def test_pending_gate_states(self):
        for v in (AuthorizationVerdict.REQUEST_MORE_EVIDENCE,
                  AuthorizationVerdict.SIMULATE_AND_RETRY,
                  AuthorizationVerdict.ESCALATE_TO_HUMAN):
            r = compose(v, CloudRecommendation.PROCEED)
            self.assertIs(r.combined, CombinedOutcome.PENDING_AUTHORIZATION)
            self.assertFalse(r.would_proceed)

    def test_outcome_mapping_total(self):
        for d in ActionDecision:
            rec = cloud_recommendation(d)
            self.assertIsInstance(rec, CloudRecommendation)
        self.assertTrue(is_permissive(CloudRecommendation.PROCEED))
        self.assertFalse(is_permissive(CloudRecommendation.HOLD))


class TestShadowAdapter(unittest.TestCase):
    def test_off_by_default(self):
        a = CloudShadowAdapter()
        ws = _ws()
        self.assertIsNone(a.observe(
            decision_id="d", world=ws, candidates=[_c(ws.version)],
            now_s=NOW, freshness_s=2.0))
        self.assertEqual(a.sink.seen, 0)

    def test_ag_allows_acp_holds_is_decisive(self):
        a = CloudShadowAdapter(enabled=True)
        ws = _ws(seconds_since_last_action=30.0)  # real readiness blocks
        r = a.observe(decision_id="d", world=ws, candidates=[_c(ws.version)],
                      now_s=NOW, freshness_s=2.0,
                      authorization=AuthorizationVerdict.ALLOW)
        self.assertIs(r.composition.combined, CombinedOutcome.HELD_BY_ACP)

    def test_ag_denies_acp_safe_is_blocked(self):
        a = CloudShadowAdapter(enabled=True)
        ws = _ws()
        r = a.observe(decision_id="d", world=ws, candidates=[_c(ws.version)],
                      now_s=NOW, freshness_s=2.0,
                      authorization=AuthorizationVerdict.DENY)
        self.assertIs(r.acp_decision, ActionDecision.EXECUTE)  # ACP found it safe
        self.assertIs(r.composition.combined,
                      CombinedOutcome.BLOCKED_BY_AUTHORIZATION)

    def test_all_records_shadow_only(self):
        a = CloudShadowAdapter(enabled=True)
        ws = _ws()
        a.observe(decision_id="d", world=ws, candidates=[_c(ws.version)],
                  now_s=NOW, freshness_s=2.0)
        self.assertTrue(all(r.shadow_only for r in a.sink.records))

    def test_exception_contained_as_shadow_error(self):
        a = CloudShadowAdapter(enabled=True)

        class BadCand:  # triggers an AttributeError inside evaluation
            candidate_id = "bad"
        r = a.observe(decision_id="d", world=_ws(), candidates=[BadCand()],
                      now_s=NOW, freshness_s=2.0)
        self.assertTrue(r.record.shadow_error)
        self.assertIs(r.cloud_recommendation, CloudRecommendation.HOLD)

    def test_bounded_sink_drops_counted(self):
        from symbolu_robotics.autonomous_control_plane.cloud.adapter import (
            BoundedCloudSink)
        a = CloudShadowAdapter(enabled=True, sink=BoundedCloudSink(maxlen=2))
        ws = _ws()
        for i in range(5):
            a.observe(decision_id=f"d{i}", world=ws, candidates=[_c(ws.version)],
                      now_s=NOW, freshness_s=2.0)
        self.assertEqual(len(a.sink.records), 2)
        self.assertEqual(a.sink.seen, 5)
        self.assertEqual(a.sink.dropped, 3)

    def test_commit_revalidation_rejects_state_drift(self):
        a = CloudShadowAdapter(enabled=True)
        ws = _ws(resource_version="1")
        drift = _ws(resource_version="2", current_replicas=5)
        c = _c(ws.version)
        ok, _ = a.commit_revalidate(
            decision_id="d", selected=c, world_at_decision=ws,
            constraint_set_version="cs", current_world=drift,
            current_constraint_set_version="cs", issued_time_s=NOW, now_s=NOW + 1)
        self.assertFalse(ok)

    def test_commit_revalidation_rejects_candidate_mutation(self):
        a = CloudShadowAdapter(enabled=True)
        ws = _ws()
        orig = _c(ws.version, operation=CloudOperation.ROLLOUT,
                  manifest_digest="sha:a", rollback_ref="r")
        mutated = _c(ws.version, operation=CloudOperation.ROLLOUT,
                     manifest_digest="sha:TAMPERED", rollback_ref="r")
        ok, _ = a.commit_revalidate(
            decision_id="d", selected=orig, world_at_decision=ws,
            constraint_set_version="cs", current_world=ws,
            current_constraint_set_version="cs", issued_time_s=NOW, now_s=NOW + 1,
            current_candidate=mutated)
        self.assertFalse(ok)

    def test_deterministic_rerun(self):
        def sig():
            a = CloudShadowAdapter(enabled=True)
            ws = _ws()
            r = a.observe(decision_id="d", world=ws, candidates=[_c(ws.version)],
                          now_s=NOW, freshness_s=2.0,
                          authorization=AuthorizationVerdict.ALLOW)
            return r.record.content_dict()
        self.assertEqual(sig(), sig())


class TestNoActuation(unittest.TestCase):
    def test_no_k8s_client_imported_by_cloud_adapter(self):
        import symbolu_robotics.autonomous_control_plane.cloud.adapter as mod
        src = mod.__file__
        with open(src) as fh:
            text = fh.read()
        # The shadow adapter must not import the kubernetes client.
        self.assertNotIn("import kubernetes", text)
        self.assertNotIn("from kubernetes", text)


if __name__ == "__main__":
    unittest.main()
