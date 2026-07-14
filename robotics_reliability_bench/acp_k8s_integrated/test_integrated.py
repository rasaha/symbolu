"""ACP V2.1 integrated ActionGate + ACP invariants + compatibility tests.

Runs under stdlib unittest AND pytest. Exercises the REAL frozen ActionGate
engine + the REAL ACP cloud adapter (frozen core + real cloud_controller) on
identity-bound Kubernetes operations, proving the §11 safety invariants, the §5
composition classes, §4 identity binding, and §8 commit revalidation — all in
shadow mode with no cluster mutation.
"""
from __future__ import annotations

import logging
import unittest

logging.disable(logging.CRITICAL)

from robotics_reliability_bench.acp_k8s_integrated.actiongate_runner import (
    run_actiongate,
)
from robotics_reliability_bench.acp_k8s_integrated.composition import (
    CompositionClass as CC,
)
from robotics_reliability_bench.acp_k8s_integrated.corpus import build_corpus
from robotics_reliability_bench.acp_k8s_integrated.harness import (
    BoundedIntegratedSink,
    CommitDrift,
    IntegratedShadowHarness,
)
from robotics_reliability_bench.acp_k8s_integrated.identity_binding import (
    KubernetesOperation,
)


def _op(**kw):
    base = dict(
        cluster="ref-cp", namespace="protected", deployment="web",
        k8s_verb="SCALE", current_replicas=1, desired_replicas=2,
        resource_version="1001", generation=1, available_replicas=1,
        readiness_plasticity=0.80, seconds_since_last_action=600.0,
        dependency_healthy=True, freeze_active=False, active_rollback_watches=0,
        rollback_ref="", compliant_manifest=True, provenance="X")
    base.update(kw)
    return KubernetesOperation(**base)


def _h():
    return IntegratedShadowHarness(enabled=True)


class TestRealActionGate(unittest.TestCase):
    """The runner drives the REAL frozen ActionGate engine to real outcomes."""

    def test_authorized_allow(self):
        r = run_actiongate(namespace="protected", name="web", k8s_verb="SCALE",
                           replicas=2, resource_version="1001")
        self.assertEqual(r.outcome, "ALLOW")
        self.assertTrue(r.is_authorized)
        self.assertEqual(r.dispositive_rules, ("K8S_DEPLOY",))
        self.assertTrue(r.action_hash)

    def test_unauthorized_namespace_denies(self):
        r = run_actiongate(namespace="default", name="web", k8s_verb="SCALE",
                           replicas=2, resource_version="1")
        self.assertEqual(r.outcome, "DENY")
        self.assertIn("namespace_scope", r.admission_violations)

    def test_missing_simulation_pending(self):
        r = run_actiongate(namespace="protected", name="web", k8s_verb="SCALE",
                           replicas=2, resource_version="1", include_simulation=False)
        self.assertEqual(r.outcome, "SIMULATE_AND_RETRY")
        self.assertTrue(r.is_pending)

    def test_delete_without_approval_escalates(self):
        r = run_actiongate(namespace="protected", name="web", k8s_verb="DELETE",
                           replicas=0, resource_version="1",
                           rollback_plan={"to": "prev"})
        self.assertEqual(r.outcome, "ESCALATE_TO_HUMAN")

    def test_action_hash_deterministic(self):
        a = run_actiongate(namespace="protected", name="web", k8s_verb="SCALE",
                           replicas=2, resource_version="1001")
        b = run_actiongate(namespace="protected", name="web", k8s_verb="SCALE",
                           replicas=2, resource_version="1001")
        self.assertEqual(a.action_hash, b.action_hash)


class TestCompositionClasses(unittest.TestCase):
    """All corpus scenarios produce their expected composition class."""

    def test_corpus_matches_expected(self):
        h = _h()
        for sc in build_corpus():
            r = h.evaluate(sc.op, scenario_id=sc.scenario_id,
                           freshness_s=sc.freshness_s, ag_overrides=sc.ag_overrides,
                           acp_manifest_digest_override=sc.acp_manifest_digest_override,
                           commit_drift=sc.commit_drift,
                           inject_shadow_error=sc.inject_shadow_error)
            self.assertEqual(r.composition.composition_class, sc.expected_class,
                             f"{sc.scenario_id}: {r.composition.composition_class}")

    def test_all_eight_classes_present(self):
        h = _h()
        seen = set()
        for sc in build_corpus():
            r = h.evaluate(sc.op, scenario_id=sc.scenario_id,
                           freshness_s=sc.freshness_s, ag_overrides=sc.ag_overrides,
                           acp_manifest_digest_override=sc.acp_manifest_digest_override,
                           commit_drift=sc.commit_drift,
                           inject_shadow_error=sc.inject_shadow_error)
            seen.add(r.composition.composition_class)
        self.assertEqual(seen, set(CC))


class TestSafetyInvariants(unittest.TestCase):
    def test_actiongate_denial_never_overridden(self):
        # authorized-DENY (out-of-scope ns) even when operationally perfect
        r = _h().evaluate(_op(namespace="sandbox"), scenario_id="d")
        self.assertEqual(r.composition.composition_class,
                         CC.BLOCKED_BY_AUTHORIZATION)
        self.assertFalse(r.composition.hypothetically_eligible)

    def test_acp_never_grants_authorization(self):
        # ACP safe but gate pending (missing sim) -> not eligible
        r = _h().evaluate(_op(), scenario_id="p",
                          ag_overrides={"include_simulation": False})
        self.assertFalse(r.composition.hypothetically_eligible)
        self.assertEqual(r.composition.composition_class, CC.REQUEST_MORE_EVIDENCE)

    def test_acp_hold_holds_even_when_authorized(self):
        r = _h().evaluate(_op(freeze_active=True), scenario_id="f")
        self.assertEqual(r.composition.composition_class,
                         CC.HELD_BY_OPERATIONAL_SAFETY)
        self.assertTrue(r.actiongate.is_authorized)

    def test_eligible_requires_both_layers(self):
        r = _h().evaluate(_op(), scenario_id="ok")
        self.assertTrue(r.composition.hypothetically_eligible)
        self.assertTrue(r.actiongate.is_authorized)
        self.assertEqual(r.record.acp_recommendation, "PROCEED")


class TestIdentityBinding(unittest.TestCase):
    def test_normal_operations_are_bound(self):
        r = _h().evaluate(_op(), scenario_id="b")
        self.assertTrue(r.record.identity_bound)
        self.assertEqual(r.record.identity_reason, "BOUND")
        self.assertIsNotNone(r.record.composition_identity)

    def test_divergent_patch_is_mismatch(self):
        r = _h().evaluate(_op(), scenario_id="m",
                          acp_manifest_digest_override="sha256:DIFF")
        self.assertEqual(r.composition.composition_class,
                         CC.COMPOSITION_IDENTITY_MISMATCH)
        self.assertFalse(r.composition.hypothetically_eligible)

    def test_bound_layers_reference_distinct_but_linked_ids(self):
        # schemas NOT merged: action_hash != candidate_identity, but linked.
        r = _h().evaluate(_op(), scenario_id="link")
        self.assertNotEqual(r.record.actiongate_action_hash,
                            r.record.acp_candidate_identity)
        self.assertIsNotNone(r.record.composition_identity)


class TestCommitRevalidation(unittest.TestCase):
    def test_state_drift_rejected_by_both(self):
        r = _h().evaluate(_op(), scenario_id="sd",
                          commit_drift=CommitDrift(new_resource_version="9"))
        cr = r.record.commit_revalidation
        self.assertFalse(cr["still_valid"])
        self.assertTrue(cr["actiongate_rejects"])
        self.assertTrue(cr["acp_rejects"])

    def test_patch_mutation_rejected_by_both(self):
        r = _h().evaluate(_op(), scenario_id="pm",
                          commit_drift=CommitDrift(mutated_manifest_digest="sha:x"))
        cr = r.record.commit_revalidation
        self.assertTrue(cr["actiongate_rejects"])
        self.assertTrue(cr["acp_rejects"])

    def test_policy_version_drift_rejected_by_actiongate(self):
        r = _h().evaluate(_op(), scenario_id="pv",
                          commit_drift=CommitDrift(new_policy_version="9.9.9+x:y"))
        cr = r.record.commit_revalidation
        self.assertTrue(cr["actiongate_rejects"])

    def test_no_drift_still_valid(self):
        r = _h().evaluate(_op(), scenario_id="nd", commit_drift=CommitDrift())
        self.assertTrue(r.record.commit_revalidation["still_valid"])


class TestShadowSafety(unittest.TestCase):
    def test_off_by_default(self):
        h = IntegratedShadowHarness()
        self.assertIsNone(h.evaluate(_op(), scenario_id="x"))
        self.assertEqual(h.sink.seen, 0)

    def test_exception_contained_as_shadow_error(self):
        r = _h().evaluate(_op(), scenario_id="e", inject_shadow_error=True)
        self.assertEqual(r.composition.composition_class, CC.SHADOW_ERROR)
        self.assertTrue(r.record.shadow_error)

    def test_all_records_shadow_only_no_mutation(self):
        h = _h()
        for sc in build_corpus():
            h.evaluate(sc.op, scenario_id=sc.scenario_id, freshness_s=sc.freshness_s,
                       ag_overrides=sc.ag_overrides,
                       acp_manifest_digest_override=sc.acp_manifest_digest_override,
                       commit_drift=sc.commit_drift,
                       inject_shadow_error=sc.inject_shadow_error)
        self.assertTrue(all(r.shadow_only for r in h.sink.records))
        self.assertTrue(all(not r.cluster_mutated for r in h.sink.records))

    def test_bounded_sink_drops_counted(self):
        h = IntegratedShadowHarness(enabled=True, sink=BoundedIntegratedSink(maxlen=3))
        for i in range(7):
            h.evaluate(_op(), scenario_id=f"s{i}")
        self.assertEqual(len(h.sink.records), 3)
        self.assertEqual(h.sink.seen, 7)
        self.assertEqual(h.sink.dropped, 4)

    def test_deterministic_rerun(self):
        def sig():
            return _h().evaluate(_op(), scenario_id="d").record.content_dict()
        self.assertEqual(sig(), sig())

    def test_no_k8s_client_imported(self):
        import robotics_reliability_bench.acp_k8s_integrated.harness as m
        text = open(m.__file__).read()
        self.assertNotIn("import kubernetes", text)
        self.assertNotIn("from kubernetes", text)


class TestNoDuplicateOwnership(unittest.TestCase):
    def test_acp_side_does_not_reimplement_authorization(self):
        import robotics_reliability_bench.acp_k8s_integrated.composition as c
        import robotics_reliability_bench.acp_k8s_integrated.harness as h
        text = open(c.__file__).read() + open(h.__file__).read()
        for banned in ("build_approval", "verify_approval", "verify_token",
                       "build_token"):
            self.assertNotIn(banned, text)

    def test_actiongate_does_not_own_operational_readiness(self):
        import action_gate_ref.gate as g
        self.assertNotIn("ReadinessChecker", open(g.__file__).read())


class TestFrozenCoreUnchanged(unittest.TestCase):
    def test_v1_core_hash_unchanged(self):
        import hashlib
        import os
        base = os.path.join(os.path.dirname(__file__), "..", "..",
                            "symbolu_robotics", "autonomous_control_plane")
        core = ["errors.py", "identity.py", "world_state.py", "constraints.py",
                "envelopes.py", "authorization.py", "action_selection.py",
                "decision_trace.py", "failure_state.py", "interfaces.py"]
        h = hashlib.sha256()
        for m in core:
            with open(os.path.join(base, m), "rb") as f:
                h.update(f.read())
        self.assertEqual(h.hexdigest()[:32], "8f8660e293308cf94c983a26a2ae69c9")


if __name__ == "__main__":
    unittest.main()
