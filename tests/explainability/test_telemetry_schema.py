"""
Tests for the Phase Quad Explanation Telemetry system.

All tests are stdlib-only (no torch required) since the telemetry
schema, logger, audit trail, policy engine, and explainer are
all pure-Python dataclass/dict systems.
"""

import json
import os
import tempfile
import unittest

from symbolu.mechanical.logging.telemetry_schema import (
    AttentionProvenance,
    ConfidenceBand,
    EscalationLevel,
    ExplanationTelemetry,
    PathAttribution,
    PolicyDecision,
    PolicyOutcome,
    ProvenanceBlock,
    StabilityBadge,
    StabilityMetrics,
    confidence_to_band,
    stability_to_badge,
)


class TestTelemetrySchema(unittest.TestCase):
    """Test the core data contracts."""

    def test_default_telemetry(self):
        """Default ExplanationTelemetry has sensible zero-values."""
        t = ExplanationTelemetry()
        self.assertEqual(t.routing.local_ratio, 0.0)
        self.assertEqual(t.stability.stability_badge, StabilityBadge.GREEN)
        self.assertEqual(t.policy.policy_outcome, PolicyOutcome.ALLOWED)

    def test_to_dict_round_trip(self):
        """to_dict produces a JSON-serializable structure."""
        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.72, quad_ratio=0.28),
            stability=StabilityMetrics(
                r_k_mean=0.45,
                phase_drift_mean=0.02,
                stability_badge=StabilityBadge.GREEN,
            ),
            policy=PolicyDecision(
                confidence_band=ConfidenceBand.HIGH,
                confidence_score=0.85,
                policy_outcome=PolicyOutcome.ALLOWED,
            ),
            response_id="test-001",
        )

        d = t.to_dict()
        self.assertEqual(d["routing"]["local_ratio"], 0.72)
        self.assertEqual(d["stability"]["stability_badge"], "green")
        self.assertEqual(d["policy"]["confidence_band"], "high")

        # JSON serializable
        json_str = t.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["response_id"], "test-001")

    def test_to_flat_dict(self):
        """Flat dict uses dot-notation keys."""
        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.5, quad_ratio=0.3),
        )
        flat = t.to_flat_dict()
        self.assertIn("routing.local_ratio", flat)
        self.assertEqual(flat["routing.local_ratio"], 0.5)

    def test_summary(self):
        """Summary produces a human-readable string."""
        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.72, phase_ratio=0.0, quad_ratio=0.28),
            stability=StabilityMetrics(stability_badge=StabilityBadge.GREEN),
            policy=PolicyDecision(
                confidence_band=ConfidenceBand.HIGH,
                confidence_score=0.85,
                policy_outcome=PolicyOutcome.ALLOWED,
            ),
        )
        s = t.summary()
        self.assertIn("72%", s)
        self.assertIn("28%", s)
        self.assertIn("HIGH", s)
        self.assertIn("GREEN", s)
        self.assertIn("ALLOWED", s)

    def test_provenance_block(self):
        """ProvenanceBlock stores contributing block info."""
        p = ProvenanceBlock(block_id=42, weight=0.8, distance=10, source_label="policy doc")
        self.assertEqual(p.block_id, 42)
        self.assertEqual(p.source_label, "policy doc")


class TestConfidenceBanding(unittest.TestCase):
    """Test confidence_to_band mapping."""

    def test_high(self):
        self.assertEqual(confidence_to_band(0.9), ConfidenceBand.HIGH)
        self.assertEqual(confidence_to_band(0.75), ConfidenceBand.HIGH)

    def test_medium(self):
        self.assertEqual(confidence_to_band(0.6), ConfidenceBand.MEDIUM)

    def test_low(self):
        self.assertEqual(confidence_to_band(0.3), ConfidenceBand.LOW)

    def test_very_low(self):
        self.assertEqual(confidence_to_band(0.1), ConfidenceBand.VERY_LOW)


class TestStabilityBadge(unittest.TestCase):
    """Test stability_to_badge mapping."""

    def test_green(self):
        badge = stability_to_badge(
            drift_mean=0.05,
            r_k_mean=0.5,
            head_redundancy=0.3,
            reversal_risk=0.1,
        )
        self.assertEqual(badge, StabilityBadge.GREEN)

    def test_yellow_from_drift(self):
        badge = stability_to_badge(
            drift_mean=0.0005,  # Frozen phases
            r_k_mean=0.5,
            head_redundancy=0.3,
            reversal_risk=0.1,
        )
        self.assertEqual(badge, StabilityBadge.YELLOW)

    def test_red_from_collapse(self):
        badge = stability_to_badge(
            drift_mean=0.6,     # Unstable
            r_k_mean=0.005,     # Near collapse
            head_redundancy=0.9,  # Redundant
            reversal_risk=0.8,
        )
        self.assertEqual(badge, StabilityBadge.RED)


class TestExplainabilityLogger(unittest.TestCase):
    """Test the ExplainabilityLogger."""

    def test_log_and_retrieve(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        logger = ExplainabilityLogger(max_entries=100)
        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.6),
            policy=PolicyDecision(confidence_band=ConfidenceBand.HIGH),
        )
        logger.log_telemetry(t)

        recent = logger.recent(n=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["routing"]["local_ratio"], 0.6)

    def test_aggregate_stats(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        logger = ExplainabilityLogger()

        for badge in [StabilityBadge.GREEN, StabilityBadge.GREEN, StabilityBadge.YELLOW]:
            t = ExplanationTelemetry(
                stability=StabilityMetrics(stability_badge=badge),
            )
            logger.log_telemetry(t)

        stats = logger.aggregate_stats()
        self.assertEqual(stats["total_logged"], 3)
        self.assertAlmostEqual(stats["stability_distribution"]["green"], 2 / 3, places=3)

    def test_ring_buffer_eviction(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        logger = ExplainabilityLogger(max_entries=3)
        for i in range(5):
            t = ExplanationTelemetry(response_id=f"req-{i}")
            logger.log_telemetry(t)

        recent = logger.recent(n=10)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["response_id"], "req-2")

    def test_custom_event_logging(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        logger = ExplainabilityLogger()
        logger.log("custom_step", {"key": "value"})

        events = logger.recent_events(n=5)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["step"], "custom_step")

    def test_file_output(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            logger = ExplainabilityLogger(log_file=path)
            t = ExplanationTelemetry(response_id="file-test")
            logger.log_telemetry(t)

            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["response_id"], "file-test")
        finally:
            os.unlink(path)

    def test_sink_callback(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        received = []
        logger = ExplainabilityLogger(sink=lambda d: received.append(d))
        t = ExplanationTelemetry(response_id="sink-test")
        logger.log_telemetry(t)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["response_id"], "sink-test")

    def test_clear_resets_everything(self):
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger

        logger = ExplainabilityLogger()
        logger.log_telemetry(ExplanationTelemetry())
        logger.log("event", {"x": 1})

        logger.clear()
        self.assertEqual(logger.aggregate_stats()["total_logged"], 0)
        self.assertEqual(len(logger.recent()), 0)
        self.assertEqual(len(logger.recent_events()), 0)


class TestAuditTrail(unittest.TestCase):
    """Test the AuditTrail."""

    def test_record_and_export(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()
        trail.record("response_generated", {"foo": "bar"})
        trail.record("tool_blocked", {"reason": "low_coherence"})

        entries = trail.export()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["action"], "response_generated")
        self.assertEqual(entries[1]["action"], "tool_blocked")

    def test_monotonic_sequence_ids(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()
        for i in range(5):
            trail.record("test", {"i": i})

        entries = trail.export()
        seq_ids = [e["sequence_id"] for e in entries]
        self.assertEqual(seq_ids, [1, 2, 3, 4, 5])

    def test_action_filter(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()
        trail.record("response_generated", {})
        trail.record("tool_execution_blocked", {})
        trail.record("response_generated", {})

        blocked = trail.export(action_filter="tool_execution_blocked")
        self.assertEqual(len(blocked), 1)

    def test_record_telemetry_auto_action(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()

        # Normal response
        trail.record_telemetry({"policy": {"policy_outcome": "allowed"}})
        # Blocked response
        trail.record_telemetry({"policy": {"policy_outcome": "blocked"}})
        # Verification
        trail.record_telemetry({"policy": {"verification_needed": True}})
        # Adversarial
        trail.record_telemetry({"policy": {"adversarial_drift_detected": True}})

        entries = trail.export()
        self.assertEqual(entries[0]["action"], "response_generated")
        self.assertEqual(entries[1]["action"], "tool_execution_blocked")
        self.assertEqual(entries[2]["action"], "verification_requested")
        self.assertEqual(entries[3]["action"], "adversarial_detected")

    def test_count(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()
        trail.record("a", {})
        trail.record("b", {})
        trail.record("a", {})

        self.assertEqual(trail.count(), 3)
        self.assertEqual(trail.count("a"), 2)
        self.assertEqual(trail.count("b"), 1)

    def test_export_jsonl(self):
        from symbolu.mechanical.logging.audit_trail import AuditTrail

        trail = AuditTrail()
        trail.record("test", {"value": 42})

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            count = trail.export_jsonl(path)
            self.assertEqual(count, 1)

            with open(path) as f:
                line = f.readline()
            parsed = json.loads(line)
            self.assertEqual(parsed["data"]["value"], 42)
        finally:
            os.unlink(path)


class TestEnterprisePolicyEngine(unittest.TestCase):
    """Test the enterprise policy engine."""

    def test_default_rules_loaded(self):
        from symbolu.mechanical.logging.enterprise_policy import EnterprisePolicyEngine

        engine = EnterprisePolicyEngine(load_defaults=True)
        self.assertTrue(len(engine.rules) > 0)

    def test_green_telemetry_passes(self):
        """Healthy telemetry should not trigger any violations."""
        from symbolu.mechanical.logging.enterprise_policy import EnterprisePolicyEngine

        engine = EnterprisePolicyEngine()
        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.5, quad_ratio=0.3),
            stability=StabilityMetrics(
                stability_badge=StabilityBadge.GREEN,
                reversal_risk=0.1,
                phase_drift_mean=0.05,
            ),
            policy=PolicyDecision(
                confidence_score=0.8,
                coherence_score=0.9,
                adversarial_drift_detected=False,
                prompt_injection_detected=False,
            ),
            provenance=AttentionProvenance(cache_key_cosine_max=0.7),
        )

        result = engine.evaluate(t)
        self.assertFalse(result.blocked)
        self.assertEqual(result.rules_triggered, 0)

    def test_adversarial_blocks(self):
        """Adversarial drift should trigger BLOCK."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
        )

        engine = EnterprisePolicyEngine()
        t = ExplanationTelemetry(
            policy=PolicyDecision(
                adversarial_drift_detected=True,
                coherence_score=0.8,
            ),
            stability=StabilityMetrics(stability_badge=StabilityBadge.GREEN),
            provenance=AttentionProvenance(cache_key_cosine_max=0.5),
        )

        result = engine.evaluate(t)
        self.assertTrue(result.blocked)
        self.assertEqual(result.outcome, PolicyAction.BLOCK)

    def test_regulated_domain_low_quad(self):
        """Regulated domain with low quad should trigger VERIFY."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
        )

        engine = EnterprisePolicyEngine()
        t = ExplanationTelemetry(
            routing=PathAttribution(quad_ratio=0.05),
            stability=StabilityMetrics(
                stability_badge=StabilityBadge.GREEN,
                reversal_risk=0.1,
            ),
            policy=PolicyDecision(
                coherence_score=0.8,
                adversarial_drift_detected=False,
                prompt_injection_detected=False,
            ),
            provenance=AttentionProvenance(cache_key_cosine_max=0.5),
        )

        result = engine.evaluate(t, context={"domain": "compliance"})
        self.assertTrue(result.needs_verification)
        violated_rules = [v.rule_name for v in result.violations]
        self.assertIn("regulated_grounding", violated_rules)

    def test_domain_filtering(self):
        """Rules with domain restrictions should not trigger for other domains."""
        from symbolu.mechanical.logging.enterprise_policy import EnterprisePolicyEngine

        engine = EnterprisePolicyEngine()
        t = ExplanationTelemetry(
            routing=PathAttribution(quad_ratio=0.05),
            stability=StabilityMetrics(
                stability_badge=StabilityBadge.GREEN,
                reversal_risk=0.1,
            ),
            policy=PolicyDecision(
                coherence_score=0.8,
                adversarial_drift_detected=False,
                prompt_injection_detected=False,
            ),
            provenance=AttentionProvenance(cache_key_cosine_max=0.5),
        )

        # "general" domain should NOT trigger regulated rules
        result = engine.evaluate(t, context={"domain": "general"})
        violated_rules = [v.rule_name for v in result.violations]
        self.assertNotIn("regulated_grounding", violated_rules)

    def test_custom_rule(self):
        """Custom rules can be added and evaluated."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
            PolicyRule,
        )

        engine = EnterprisePolicyEngine(load_defaults=False)
        engine.add_rule(PolicyRule(
            name="custom_test",
            description="Blocks if local_ratio > 0.9",
            condition=lambda t: t.routing.local_ratio > 0.9,
            action=PolicyAction.BLOCK,
        ))

        t = ExplanationTelemetry(
            routing=PathAttribution(local_ratio=0.95),
        )
        result = engine.evaluate(t)
        self.assertTrue(result.blocked)

    def test_rule_disable(self):
        """Disabled rules should not trigger."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
            PolicyRule,
        )

        engine = EnterprisePolicyEngine(load_defaults=False)
        engine.add_rule(PolicyRule(
            name="always_block",
            description="Always blocks",
            condition=lambda t: True,
            action=PolicyAction.BLOCK,
        ))

        engine.disable_rule("always_block")
        result = engine.evaluate(ExplanationTelemetry())
        self.assertFalse(result.blocked)

    def test_most_restrictive_wins(self):
        """When multiple rules trigger, most restrictive action wins."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
            PolicyRule,
        )

        engine = EnterprisePolicyEngine(load_defaults=False)
        engine.add_rule(PolicyRule(
            name="warn_rule",
            description="Warns",
            condition=lambda t: True,
            action=PolicyAction.WARN,
        ))
        engine.add_rule(PolicyRule(
            name="verify_rule",
            description="Verifies",
            condition=lambda t: True,
            action=PolicyAction.VERIFY,
        ))

        result = engine.evaluate(ExplanationTelemetry())
        self.assertEqual(result.outcome, PolicyAction.VERIFY)
        self.assertEqual(result.rules_triggered, 2)

    def test_low_coherence_blocks(self):
        """Very low coherence should trigger BLOCK."""
        from symbolu.mechanical.logging.enterprise_policy import (
            EnterprisePolicyEngine,
            PolicyAction,
        )

        engine = EnterprisePolicyEngine()
        t = ExplanationTelemetry(
            policy=PolicyDecision(
                coherence_score=0.2,
                adversarial_drift_detected=False,
                prompt_injection_detected=False,
            ),
            stability=StabilityMetrics(
                stability_badge=StabilityBadge.GREEN,
                reversal_risk=0.1,
            ),
            provenance=AttentionProvenance(cache_key_cosine_max=0.5),
        )

        result = engine.evaluate(t)
        self.assertTrue(result.blocked)


class TestPhaseQuadExplainer(unittest.TestCase):
    """Test the PhaseQuadExplainer with mock model objects."""

    def _make_mock_model(
        self,
        phase_health=None,
        instrumentation=None,
        proposal_metrics=None,
    ):
        """Create a mock model with configurable diagnostic methods."""

        class MockModel:
            def get_phase_health(self):
                return phase_health or {
                    "r_k_mean": 0.5,
                    "r_k_per_layer": [0.4, 0.5, 0.6],
                }

            def get_instrumentation(self):
                return instrumentation or {
                    "cache_hit_rate": 0.7,
                    "mean_alpha": 0.5,
                    "cache_key_cosine_mean": 0.3,
                    "cache_key_cosine_max": 0.6,
                }

            def get_proposal_metrics(self):
                return proposal_metrics or {
                    "confidence_mean": 0.8,
                    "skip_rate": 0.3,
                    "per_layer_confidence": [0.7, 0.8, 0.9],
                    "per_layer_skip_rate": [0.2, 0.3, 0.4],
                }

        return MockModel()

    def test_healthy_model(self):
        """Healthy model produces GREEN stability and HIGH confidence."""
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

        model = self._make_mock_model()
        explainer = PhaseQuadExplainer()

        # Provide realistic health diagnostics (drift > 0 avoids "frozen" flag)
        health = {
            "r_k_mean": 0.5,
            "r_q_mean": 0.5,
            "amp_phase_corr": 0.05,
            "head_redundancy": 0.2,
            "phase_drift_mean": 0.04,
            "phase_drift_std": 0.01,
        }
        t = explainer.explain(model, response_id="test-healthy", health_diagnostics=health)

        self.assertEqual(t.response_id, "test-healthy")
        self.assertEqual(t.stability.stability_badge, StabilityBadge.GREEN)
        self.assertGreater(t.routing.local_ratio, 0)
        self.assertGreater(t.routing.quad_ratio, 0)
        self.assertEqual(t.layer_count, 3)

    def test_with_health_diagnostics(self):
        """Pre-computed health diagnostics are incorporated."""
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

        model = self._make_mock_model()
        explainer = PhaseQuadExplainer()

        health = {
            "r_k_mean": 0.45,
            "r_q_mean": 0.5,
            "amp_phase_corr": 0.1,
            "head_redundancy": 0.2,
            "phase_drift_mean": 0.03,
            "phase_drift_std": 0.01,
        }

        t = explainer.explain(model, health_diagnostics=health)
        self.assertAlmostEqual(t.stability.r_k_mean, 0.45, places=2)
        self.assertAlmostEqual(t.stability.phase_drift_mean, 0.03, places=2)

    def test_low_confidence_model(self):
        """Low confidence model produces higher local_ratio."""
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

        model = self._make_mock_model(
            proposal_metrics={
                "confidence_mean": 0.2,
                "skip_rate": 0.1,
                "per_layer_confidence": [0.2],
                "per_layer_skip_rate": [0.1],
            }
        )
        explainer = PhaseQuadExplainer()
        t = explainer.explain(model)

        # Low confidence → more local reliance
        self.assertGreater(t.routing.local_ratio, 0.5)

    def test_ontological_state_passthrough(self):
        """Ontological state signals reach the policy decision."""
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

        model = self._make_mock_model()
        explainer = PhaseQuadExplainer()

        t = explainer.explain(
            model,
            ontological_state={
                "kosha_depth": 0.7,
                "vritti_reliability": 0.6,
                "guna_energy": 0.5,
            },
        )
        self.assertAlmostEqual(t.policy.kosha_depth, 0.7, places=2)
        self.assertAlmostEqual(t.policy.vritti_reliability, 0.6, places=2)

    def test_json_serialization(self):
        """Full telemetry round-trips through JSON."""
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer

        model = self._make_mock_model()
        explainer = PhaseQuadExplainer()
        t = explainer.explain(model, response_id="json-test")

        json_str = t.to_json()
        parsed = json.loads(json_str)

        self.assertEqual(parsed["response_id"], "json-test")
        self.assertIn("routing", parsed)
        self.assertIn("stability", parsed)
        self.assertIn("policy", parsed)
        self.assertIn("provenance", parsed)


class TestEndToEnd(unittest.TestCase):
    """End-to-end test: explainer → logger → audit → policy."""

    def test_full_pipeline(self):
        from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer
        from symbolu.mechanical.logging.explainability_logger import ExplainabilityLogger
        from symbolu.mechanical.logging.audit_trail import AuditTrail
        from symbolu.mechanical.logging.enterprise_policy import EnterprisePolicyEngine

        # 1. Mock model
        class MockModel:
            def get_phase_health(self):
                return {"r_k_mean": 0.5, "r_k_per_layer": [0.5, 0.5]}

            def get_instrumentation(self):
                return {
                    "cache_hit_rate": 0.6,
                    "mean_alpha": 0.5,
                    "cache_key_cosine_mean": 0.3,
                    "cache_key_cosine_max": 0.5,
                }

            def get_proposal_metrics(self):
                return {
                    "confidence_mean": 0.75,
                    "skip_rate": 0.2,
                    "per_layer_confidence": [0.7, 0.8],
                    "per_layer_skip_rate": [0.2, 0.2],
                }

        # 2. Explain
        explainer = PhaseQuadExplainer()
        telemetry = explainer.explain(
            MockModel(),
            response_id="e2e-001",
            coherence_score=0.85,
        )

        # 3. Log
        logger = ExplainabilityLogger()
        logger.log_telemetry(telemetry)

        # 4. Audit
        trail = AuditTrail()
        trail.record_telemetry(telemetry.to_dict())

        # 5. Policy
        engine = EnterprisePolicyEngine()
        result = engine.evaluate(telemetry)

        # Assertions: healthy model should pass
        self.assertFalse(result.blocked)
        self.assertEqual(logger.aggregate_stats()["total_logged"], 1)
        self.assertEqual(trail.count(), 1)
        self.assertEqual(telemetry.model_version, "phase_quad_v11.0.0")

        # Summary should be non-empty
        summary = telemetry.summary()
        self.assertIn("Local", summary)
        self.assertIn("Quad", summary)


if __name__ == "__main__":
    unittest.main()
