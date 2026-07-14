"""ACP V2.2 Integrated AI Control Plane invariants + compatibility tests.

Runs under stdlib unittest AND pytest. Exercises the full Context Minimization
(real) -> deterministic reader -> ActionGate (real) -> ACP (real) pipeline,
proving the §10 invariants, the §6 identity chain, and the shadow-safety
properties — all offline, deterministic, with no cluster mutation and no change
to the frozen algorithm/runtime/core.
"""
from __future__ import annotations

import logging
import unittest

logging.disable(logging.CRITICAL)

from robotics_reliability_bench.acp_control_plane.context_pipeline import (
    DeterministicReader,
    build_enterprise_context,
    run_minimization,
)
from robotics_reliability_bench.acp_control_plane.corpus import build_corpus
from robotics_reliability_bench.acp_control_plane.end_to_end_harness import (
    BoundedControlPlaneSink,
    ControlPlaneHarness,
    EndToEndClass,
)
from robotics_reliability_bench.acp_k8s_integrated.harness import CommitDrift


def _op(**kw):
    b = dict(cluster="ref-cp", namespace="protected", deployment="web",
             k8s_verb="SCALE", current_replicas=1, desired_replicas=2,
             resource_version="1001", generation=1, available_replicas=1,
             readiness_plasticity=0.80, seconds_since_last_action=600.0,
             dependency_healthy=True, freeze_active=False,
             active_rollback_watches=0, rollback_ref="", compliant_manifest=True)
    b.update(kw)
    return b


def _h():
    return ControlPlaneHarness(enabled=True)


def _run(h, sc, reduction=None):
    return h.evaluate(
        sc.op, scenario_id=sc.scenario_id,
        target_reduction=sc.target_reduction if reduction is None else reduction,
        n_filler=sc.n_filler, n_history=sc.n_history, n_redundant=sc.n_redundant,
        stale=sc.stale, malformed_field=sc.malformed_field,
        freshness_s=sc.freshness_s, ag_overrides=sc.ag_overrides,
        acp_manifest_digest_override=sc.acp_manifest_digest_override,
        commit_drift=sc.commit_drift, stack_op_override=sc.stack_op_override)


class TestRealContextMinimization(unittest.TestCase):
    def test_real_compression_preserves_both_layers(self):
        ctx = build_enterprise_context(_op(), context_id="c", n_filler=10,
                                       n_history=6, n_redundant=4)
        mr = run_minimization(ctx, 0.6)
        self.assertGreater(mr.compression_ratio, 0.3)
        self.assertTrue(mr.protected_preserved)
        self.assertTrue(mr.actiongate_spans_preserved)
        self.assertTrue(mr.acp_spans_preserved)
        self.assertTrue(mr.decision_invariant)

    def test_compression_deterministic(self):
        ctx = build_enterprise_context(_op(), context_id="c")
        a = run_minimization(ctx, 0.6)
        b = run_minimization(ctx, 0.6)
        self.assertEqual(a.surviving_ids, b.surviving_ids)

    def test_reader_reconstructs_exact_operation(self):
        ctx = build_enterprise_context(_op(), context_id="c")
        mr = run_minimization(ctx, 0.6)
        rr = DeterministicReader().read(mr, ctx)
        self.assertTrue(rr.ok)
        self.assertEqual(rr.op_facts, _op())

    def test_malformed_context_reader_fails_closed(self):
        ctx = build_enterprise_context(_op(), context_id="c",
                                       malformed_field="resource_version")
        mr = run_minimization(ctx, 0.5)
        rr = DeterministicReader().read(mr, ctx)
        self.assertFalse(rr.ok)
        self.assertEqual(rr.reason, "INSUFFICIENT_CONTEXT")


class TestDownstreamInvariance(unittest.TestCase):
    """Compression never changes the downstream decision (§10 I1/I2)."""

    def test_compressed_equals_uncompressed_downstream(self):
        h = _h()
        for sc in build_corpus():
            comp = _run(h, sc, sc.target_reduction)
            full = _run(h, sc, 0.0)
            self.assertEqual(comp.record.authorization_outcome,
                             full.record.authorization_outcome, sc.scenario_id)
            self.assertEqual(comp.record.acp_recommendation,
                             full.record.acp_recommendation, sc.scenario_id)
            self.assertEqual(comp.end_to_end_class, full.end_to_end_class,
                             sc.scenario_id)
            self.assertEqual(comp.record.actiongate_action_hash,
                             full.record.actiongate_action_hash, sc.scenario_id)


class TestCorpusClasses(unittest.TestCase):
    def test_corpus_matches_expected(self):
        h = _h()
        for sc in build_corpus():
            r = _run(h, sc)
            self.assertEqual(r.end_to_end_class, sc.expected_class, sc.scenario_id)


class TestInvariants(unittest.TestCase):
    def test_actiongate_never_grants_operational_approval(self):
        import action_gate_ref.gate as g
        self.assertNotIn("ReadinessChecker", open(g.__file__).read())

    def test_acp_never_grants_authorization(self):
        # authorized-DENY namespace -> not eligible regardless of ACP safety
        r = _h().evaluate(_op(namespace="sandbox"), scenario_id="x")
        self.assertFalse(r.record.hypothetically_eligible)

    def test_all_identities_bound_on_healthy(self):
        r = _h().evaluate(_op(), scenario_id="x")
        self.assertTrue(r.record.chain_bound)
        self.assertIsNotNone(r.record.execution_identity)
        self.assertIsNotNone(r.record.context_digest)

    def test_context_to_action_mismatch_fails_closed(self):
        r = _h().evaluate(_op(), scenario_id="x",
                          stack_op_override=_op(desired_replicas=9))
        self.assertEqual(r.end_to_end_class, EndToEndClass.CONTEXT_IDENTITY_MISMATCH)
        self.assertFalse(r.record.chain_bound)
        self.assertFalse(r.record.hypothetically_eligible)

    def test_policy_update_invalidates_authorization(self):
        r = _h().evaluate(_op(), scenario_id="x",
                          commit_drift=CommitDrift(new_policy_version="9.9.9+x:y"))
        self.assertTrue(r.record.commit_revalidation["actiongate_rejects"])

    def test_resourceVersion_update_invalidates_acp(self):
        r = _h().evaluate(_op(), scenario_id="x",
                          commit_drift=CommitDrift(new_resource_version="9999"))
        self.assertTrue(r.record.commit_revalidation["acp_rejects"])

    def test_modified_manifest_invalidates_both(self):
        r = _h().evaluate(_op(), scenario_id="x",
                          commit_drift=CommitDrift(mutated_manifest_digest="sha:z"))
        cr = r.record.commit_revalidation
        self.assertTrue(cr["actiongate_rejects"])
        self.assertTrue(cr["acp_rejects"])

    def test_eligible_requires_all_layers(self):
        r = _h().evaluate(_op(), scenario_id="x")
        self.assertTrue(r.record.hypothetically_eligible)
        self.assertTrue(r.record.chain_bound)
        self.assertEqual(r.record.authorization_outcome, "ALLOW")
        self.assertEqual(r.record.acp_recommendation, "PROCEED")


class TestShadowSafety(unittest.TestCase):
    def test_off_by_default(self):
        h = ControlPlaneHarness()
        self.assertIsNone(h.evaluate(_op(), scenario_id="x"))
        self.assertEqual(h.sink.seen, 0)

    def test_no_cluster_mutation(self):
        h = _h()
        for sc in build_corpus():
            _run(h, sc)
        self.assertTrue(all(not r.cluster_mutated for r in h.sink.records))
        self.assertTrue(all(r.shadow_only for r in h.sink.records))

    def test_bounded_sink(self):
        h = ControlPlaneHarness(enabled=True, sink=BoundedControlPlaneSink(maxlen=3))
        for i in range(7):
            h.evaluate(_op(), scenario_id=f"s{i}")
        self.assertEqual(len(h.sink.records), 3)
        self.assertEqual(h.sink.dropped, 4)

    def test_deterministic_end_to_end(self):
        def sig():
            return _h().evaluate(_op(), scenario_id="x").record.content_dict()
        self.assertEqual(sig(), sig())

    def test_no_k8s_client(self):
        import robotics_reliability_bench.acp_control_plane.end_to_end_harness as m
        text = open(m.__file__).read()
        self.assertNotIn("import kubernetes", text)
        self.assertNotIn("from kubernetes", text)


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
