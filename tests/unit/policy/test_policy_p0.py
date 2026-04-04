"""
Policy Phase P0 — Foundation Tests

Tests for the Policy Phase P0 implementation:
- P0-A: DomainProfile schema, ProfileRegistry, backward compat, JSON round-trip
- P0-B: GovernanceService.check_layer_visibility() RBAC enforcement
- P0-C: Facade status markers
- P0-D: Insight-window integration path markers
"""

import json
import unittest
from unittest.mock import patch

from agentic.policy.profile_schema import (
    DomainProfile,
    ProfileRegistry,
    get_profile_registry,
)
from agentic.policy.domain_profiles import (
    get_domain_profile,
    get_all_domain_names,
    is_domain_supported,
    DOMAIN_PROFILES,
)
from agentic.policy.interaction_modes import InteractionMode


# =============================================================================
# P0-A: Domain Profile Schema & Registry
# =============================================================================


class TestDomainProfileSchema(unittest.TestCase):
    """Test DomainProfile typed schema."""

    def test_profile_attribute_access(self):
        """DomainProfile supports typed attribute access."""
        profile = get_domain_profile("trading")
        self.assertEqual(profile.min_coherence, 0.55)
        self.assertEqual(profile.style, "precise")
        self.assertFalse(profile.allow_lam)
        self.assertEqual(
            profile.interaction_mode_default,
            InteractionMode.ANALYTICS_ONLY,
        )

    def test_profile_dict_access(self):
        """DomainProfile supports dict-style access for backward compat."""
        profile = get_domain_profile("trading")
        self.assertEqual(profile["min_coherence"], 0.55)
        self.assertEqual(profile["style"], "precise")
        self.assertFalse(profile["allow_lam"])

    def test_profile_get_with_default(self):
        """DomainProfile.get() works with defaults."""
        profile = get_domain_profile("trading")
        self.assertEqual(profile.get("min_coherence"), 0.55)
        self.assertEqual(profile.get("nonexistent_key", "fallback"), "fallback")
        self.assertIsNone(profile.get("nonexistent_key"))

    def test_profile_prefer_mappers_returns_list(self):
        """profile['prefer_mappers'] returns a list for backward compat."""
        profile = get_domain_profile("trading")
        mappers = profile["prefer_mappers"]
        self.assertIsInstance(mappers, list)
        self.assertIn("LCM", mappers)
        self.assertIn("HRM", mappers)

    def test_profile_is_frozen(self):
        """DomainProfile is immutable (frozen dataclass)."""
        profile = get_domain_profile("trading")
        with self.assertRaises(AttributeError):
            profile.min_coherence = 0.99

    def test_profile_has_version_metadata(self):
        """DomainProfile includes version metadata."""
        profile = get_domain_profile("trading")
        self.assertEqual(profile.profile_id, "trading")
        self.assertEqual(profile.profile_version, "1.0.0")

    def test_profile_contains_check(self):
        """'key in profile' works."""
        profile = get_domain_profile("trading")
        self.assertIn("min_coherence", profile)
        self.assertNotIn("nonexistent_key", profile)

    def test_keyerror_on_missing_key(self):
        """profile['missing'] raises KeyError."""
        profile = get_domain_profile("trading")
        with self.assertRaises(KeyError):
            _ = profile["this_key_does_not_exist"]


class TestDomainProfileSerialization(unittest.TestCase):
    """Test DomainProfile serialization/deserialization."""

    def test_to_dict_round_trip(self):
        """DomainProfile survives dict round-trip."""
        original = get_domain_profile("therapy")
        d = original.to_dict()
        restored = DomainProfile.from_dict(d)
        self.assertEqual(restored.min_coherence, original.min_coherence)
        self.assertEqual(restored.style, original.style)
        self.assertEqual(restored.profile_id, original.profile_id)
        self.assertEqual(
            restored.interaction_mode_default,
            original.interaction_mode_default,
        )

    def test_to_json_round_trip(self):
        """DomainProfile survives JSON round-trip."""
        original = get_domain_profile("identity")
        json_str = original.to_json()
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed["profile_id"], "identity")
        # Round-trip
        restored = DomainProfile.from_json(json_str)
        self.assertEqual(restored.min_coherence, original.min_coherence)
        self.assertEqual(restored.allow_lam, original.allow_lam)

    def test_from_dict_handles_interaction_mode_string(self):
        """from_dict converts interaction_mode_default string to enum."""
        d = {
            "profile_id": "test",
            "interaction_mode_default": "smart_insight",
        }
        profile = DomainProfile.from_dict(d)
        self.assertEqual(
            profile.interaction_mode_default,
            InteractionMode.SMART_INSIGHT,
        )

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict silently ignores unknown keys."""
        d = {
            "profile_id": "test",
            "min_coherence": 0.60,
            "unknown_future_field": True,
        }
        profile = DomainProfile.from_dict(d)
        self.assertEqual(profile.min_coherence, 0.60)

    def test_from_dict_uses_defaults_for_missing_fields(self):
        """from_dict uses schema defaults for missing fields."""
        d = {"profile_id": "minimal"}
        profile = DomainProfile.from_dict(d)
        self.assertEqual(profile.min_coherence, 0.40)  # default
        self.assertEqual(profile.style, "neutral")  # default
        self.assertFalse(profile.allow_lam)  # default


class TestProfileRegistry(unittest.TestCase):
    """Test ProfileRegistry singleton and loading."""

    def setUp(self):
        """Reset registry to defaults before each test."""
        get_profile_registry().reset()

    def test_builtin_profiles_present(self):
        """Registry has all four built-in profiles."""
        registry = get_profile_registry()
        self.assertTrue(registry.is_domain_supported("trading"))
        self.assertTrue(registry.is_domain_supported("therapy"))
        self.assertTrue(registry.is_domain_supported("identity"))
        self.assertFalse(registry.is_domain_supported("generic"))

    def test_unknown_domain_falls_back_to_generic(self):
        """Unknown domains fall back to generic profile."""
        profile = get_profile_registry().get("totally_unknown")
        self.assertEqual(profile.profile_id, "generic")
        self.assertEqual(profile.min_coherence, 0.40)

    def test_register_custom_profile(self):
        """Custom profiles can be registered."""
        registry = get_profile_registry()
        custom = DomainProfile(
            profile_id="custom_finance",
            min_coherence=0.60,
            style="precise",
        )
        registry.register(custom)
        result = registry.get("custom_finance")
        self.assertEqual(result.min_coherence, 0.60)

    def test_load_from_dict(self):
        """Profiles can be loaded from raw dicts."""
        registry = get_profile_registry()
        profile = registry.load_from_dict("test_domain", {
            "min_coherence": 0.75,
            "style": "cautious",
        })
        self.assertEqual(profile.min_coherence, 0.75)
        self.assertEqual(profile.profile_id, "test_domain")
        # Verify it's in the registry
        self.assertEqual(registry.get("test_domain").min_coherence, 0.75)

    def test_load_from_json(self):
        """Profiles can be loaded from JSON strings."""
        registry = get_profile_registry()
        json_str = json.dumps({
            "profile_id": "json_domain",
            "min_coherence": 0.80,
            "interaction_mode_default": "deep_adaptive",
        })
        profile = registry.load_from_json(json_str)
        self.assertEqual(profile.min_coherence, 0.80)
        self.assertEqual(
            profile.interaction_mode_default,
            InteractionMode.DEEP_ADAPTIVE,
        )

    def test_reset_clears_custom_profiles(self):
        """reset() removes custom profiles and restores built-ins."""
        registry = get_profile_registry()
        registry.register(DomainProfile(profile_id="temp"))
        self.assertTrue(registry.is_domain_supported("temp"))
        registry.reset()
        self.assertFalse(registry.is_domain_supported("temp"))
        self.assertTrue(registry.is_domain_supported("trading"))

    def test_all_profiles_returns_copy(self):
        """all_profiles() returns all registered profiles."""
        profiles = get_profile_registry().all_profiles()
        self.assertIn("trading", profiles)
        self.assertIn("therapy", profiles)
        self.assertIn("identity", profiles)
        self.assertIn("generic", profiles)


class TestBackwardCompatibility(unittest.TestCase):
    """Verify backward compatibility with existing consumers."""

    def test_get_domain_profile_returns_domain_profile(self):
        """get_domain_profile now returns DomainProfile, not raw dict."""
        profile = get_domain_profile("trading")
        self.assertIsInstance(profile, DomainProfile)

    def test_dict_access_pattern_works(self):
        """Existing profile['key'] access pattern still works."""
        profile = get_domain_profile("trading")
        # All keys accessed by policy_engine.py
        _ = profile["min_coherence"]
        _ = profile["max_persona_drift"]
        _ = profile["max_mapper_volatility"]
        _ = profile["allow_lam"]
        _ = profile["prefer_mappers"]
        _ = profile["style"]
        _ = profile.get("use_coherence_v2", False)
        _ = profile.get("use_coherence_v3", False)
        _ = profile.get("formula_ui_mode", "none")
        _ = profile.get("min_resonance_for_reflection", 0.50)
        _ = profile.get("max_tension_for_reflection", 0.75)
        _ = profile.get("min_v3_quality_for_activation")
        _ = profile.get("interaction_mode_default")

    def test_legacy_domain_profiles_dict_exists(self):
        """DOMAIN_PROFILES legacy dict is still available."""
        self.assertIn("trading", DOMAIN_PROFILES)
        self.assertIn("therapy", DOMAIN_PROFILES)
        self.assertIn("generic", DOMAIN_PROFILES)
        # Legacy dict values are plain dicts
        self.assertIsInstance(DOMAIN_PROFILES["trading"], dict)

    def test_legacy_dict_values_match(self):
        """DOMAIN_PROFILES values match registry profiles."""
        for domain in ("trading", "therapy", "identity", "generic"):
            legacy = DOMAIN_PROFILES[domain]
            profile = get_domain_profile(domain)
            self.assertEqual(legacy["min_coherence"], profile.min_coherence)
            self.assertEqual(legacy["style"], profile.style)

    def test_get_all_domain_names(self):
        """get_all_domain_names() returns expected domains."""
        names = get_all_domain_names()
        self.assertIn("trading", names)
        self.assertIn("therapy", names)
        self.assertIn("identity", names)
        self.assertNotIn("generic", names)

    def test_is_domain_supported(self):
        """is_domain_supported() returns correct results."""
        self.assertTrue(is_domain_supported("trading"))
        self.assertTrue(is_domain_supported("therapy"))
        self.assertFalse(is_domain_supported("unknown"))
        self.assertFalse(is_domain_supported("generic"))

    def test_profile_values_deterministic(self):
        """Same domain always returns same profile values."""
        p1 = get_domain_profile("trading")
        p2 = get_domain_profile("trading")
        self.assertEqual(p1.min_coherence, p2.min_coherence)
        self.assertEqual(p1.style, p2.style)
        self.assertEqual(p1["prefer_mappers"], p2["prefer_mappers"])

    def test_trading_profile_values(self):
        """Trading profile has expected exact values (regression test)."""
        p = get_domain_profile("trading")
        self.assertEqual(p.min_coherence, 0.55)
        self.assertEqual(p.max_persona_drift, 0.40)
        self.assertEqual(p.max_mapper_volatility, 0.45)
        self.assertEqual(p["prefer_mappers"], ["LCM", "HRM"])
        self.assertFalse(p.allow_lam)
        self.assertEqual(p.style, "precise")
        self.assertFalse(p.use_coherence_v2)
        self.assertTrue(p.formula_guardrails_enabled)
        self.assertEqual(
            p.interaction_mode_default, InteractionMode.ANALYTICS_ONLY
        )

    def test_therapy_profile_values(self):
        """Therapy profile has expected exact values (regression test)."""
        p = get_domain_profile("therapy")
        self.assertEqual(p.min_coherence, 0.45)
        self.assertTrue(p.allow_lam)
        self.assertTrue(p.use_coherence_v2)
        self.assertTrue(p.use_coherence_v3)
        self.assertEqual(p.min_v3_quality_for_activation, 0.40)
        self.assertEqual(p.formula_ui_mode, "light")
        self.assertEqual(
            p.interaction_mode_default, InteractionMode.SMART_INSIGHT
        )


# =============================================================================
# P0-B: Layer Visibility / RBAC Wiring
# =============================================================================


class TestLayerVisibilityWiring(unittest.TestCase):
    """Test GovernanceService.check_layer_visibility() RBAC enforcement."""

    def setUp(self):
        from agentic.agentic_framework.governance_service import GovernanceService
        self.service = GovernanceService()

    def test_end_user_sees_standard_layers(self):
        """End user can see standard (non-gated) layers."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        result = self.service.check_layer_visibility(
            role_id="end_user",
            artifact_id="art-001",
            span_id="span-001",
            projected_layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.IDENTITY,
                OntologicalLayer.COGNITION,
            ),
        )
        self.assertEqual(result["decision"], "allowed")
        self.assertIsNone(result["error"])
        effective = set(result["effective_layers"])
        self.assertIn("EXECUTION", effective)
        self.assertIn("IDENTITY", effective)
        self.assertIn("COGNITION", effective)

    def test_end_user_denied_absolving(self):
        """End user is denied access to ABSOLVING (gated layer)."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        result = self.service.check_layer_visibility(
            role_id="end_user",
            artifact_id="art-002",
            span_id="span-002",
            projected_layers=(OntologicalLayer.ABSOLVING,),
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )
        self.assertEqual(result["decision"], "denied")

    def test_auditor_allowed_absolving(self):
        """Auditor can access ABSOLVING (gated layer)."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        result = self.service.check_layer_visibility(
            role_id="auditor",
            artifact_id="art-003",
            span_id="span-003",
            projected_layers=(OntologicalLayer.ABSOLVING,),
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )
        self.assertEqual(result["decision"], "allowed")
        self.assertIn("ABSOLVING", result["effective_layers"])

    def test_unknown_role_fail_closed(self):
        """Unknown role triggers fail-closed deny."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        result = self.service.check_layer_visibility(
            role_id="hacker",
            artifact_id="art-004",
            span_id="span-004",
            projected_layers=(OntologicalLayer.EXECUTION,),
        )
        self.assertEqual(result["decision"], "denied")
        self.assertIsNotNone(result["error"])

    def test_decision_hash_is_deterministic(self):
        """Same inputs produce same decision hash."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        args = dict(
            role_id="developer",
            artifact_id="art-005",
            span_id="span-005",
            projected_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.COGNITION),
        )
        r1 = self.service.check_layer_visibility(**args)
        r2 = self.service.check_layer_visibility(**args)
        self.assertEqual(r1["decision_hash"], r2["decision_hash"])
        self.assertTrue(len(r1["decision_hash"]) > 0)

    def test_visibility_log_populated(self):
        """Layer visibility checks are logged."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        self.service.check_layer_visibility(
            role_id="end_user",
            artifact_id="art-006",
            span_id="span-006",
            projected_layers=(OntologicalLayer.EXECUTION,),
        )
        self.assertTrue(len(self.service._visibility_log) > 0)
        entry = self.service._visibility_log[-1]
        self.assertEqual(entry["event_type"], "layer_visibility_check")
        self.assertEqual(entry["role_id"], "end_user")

    def test_system_role_allowed_absolving(self):
        """System role can access ABSOLVING."""
        from agentic.ontology.layers.ontology_layer import OntologicalLayer
        result = self.service.check_layer_visibility(
            role_id="system",
            artifact_id="art-007",
            span_id="span-007",
            projected_layers=(OntologicalLayer.ABSOLVING, OntologicalLayer.EXECUTION),
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )
        self.assertEqual(result["decision"], "allowed")
        self.assertIn("ABSOLVING", result["effective_layers"])


# =============================================================================
# P0-C: Facade Status
# =============================================================================


class TestFacadeStatus(unittest.TestCase):
    """Test that facade modules have explicit status markers."""

    def test_governance_binding_is_provisional(self):
        from agentic.policy.governance_binding import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")

    def test_preferences_is_provisional(self):
        from agentic.policy.preferences import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")

    def test_licensing_is_provisional(self):
        from agentic.policy.licensing import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")


# =============================================================================
# P0-D: Insight Window Path Markers
# =============================================================================


class TestInsightWindowPathMarkers(unittest.TestCase):
    """Test that insight window systems have explicit path markers."""

    def test_policy_engine_path_marker(self):
        """insight_window_gating.py is marked as policy_engine path."""
        from agentic.policy.insight_window_gating import _INSIGHT_WINDOW_PATH
        self.assertEqual(_INSIGHT_WINDOW_PATH, "policy_engine")

    def test_pipeline_native_path_marker(self):
        """insight_window/ package is marked as pipeline_native path."""
        from agentic.policy.insight_window import _INSIGHT_WINDOW_PATH
        self.assertEqual(_INSIGHT_WINDOW_PATH, "pipeline_native")

    def test_both_paths_different(self):
        """The two insight window systems have distinct path markers."""
        from agentic.policy.insight_window_gating import (
            _INSIGHT_WINDOW_PATH as policy_path,
        )
        from agentic.policy.insight_window import (
            _INSIGHT_WINDOW_PATH as pipeline_path,
        )
        self.assertNotEqual(policy_path, pipeline_path)


# =============================================================================
# Regression: Policy Engine Still Works
# =============================================================================


class TestPolicyEngineRegression(unittest.TestCase):
    """Verify policy engine still works with DomainProfile instead of raw dict."""

    def test_compute_policy_flags_still_works(self):
        """compute_policy_flags produces valid output with new profile type."""
        from agentic.policy.policy_engine import compute_policy_flags

        unified = {
            "coherence": {
                "coherence_score": 0.70,
                "persona_drift_score": 0.30,
                "mapper_volatility_score": 0.25,
                "temporal_arc_score": 0.65,
            },
            "entropy": {"normalized_entropy": 0.35},
        }
        flags = compute_policy_flags(unified, "trading")
        self.assertIn("needs_grounding", flags)
        self.assertIn("stability_status", flags)
        self.assertIn("interaction_mode", flags)
        self.assertEqual(flags["interaction_mode"], "analytics_only")

    def test_compute_policy_flags_therapy(self):
        """Therapy domain policy flags work with new profile type."""
        from agentic.policy.policy_engine import compute_policy_flags

        unified = {
            "coherence": {
                "coherence_score": 0.50,
                "coherence_score_v2": 0.55,
                "persona_drift_score": 0.40,
                "mapper_volatility_score": 0.35,
                "temporal_arc_score": 0.60,
            },
            "entropy": {"normalized_entropy": 0.40},
        }
        flags = compute_policy_flags(unified, "therapy")
        self.assertEqual(flags["interaction_mode"], "smart_insight")

    def test_unknown_domain_fallback(self):
        """Unknown domain falls back to generic profile in policy engine."""
        from agentic.policy.policy_engine import compute_policy_flags

        unified = {
            "coherence": {
                "coherence_score": 0.70,
                "persona_drift_score": 0.30,
                "mapper_volatility_score": 0.25,
                "temporal_arc_score": 0.65,
            },
            "entropy": {"normalized_entropy": 0.35},
        }
        flags = compute_policy_flags(unified, "totally_unknown_domain")
        self.assertIn("needs_grounding", flags)
        self.assertEqual(flags["interaction_mode"], "analytics_only")


if __name__ == "__main__":
    unittest.main()
