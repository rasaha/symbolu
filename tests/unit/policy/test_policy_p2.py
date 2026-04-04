"""
Policy Phase P2 — Simulation & Consolidation Tests

Tests for:
- P2-A: Parameterized thresholds produce identical defaults
- P2-B: Simulation path works with default and alternate profiles
- P2-C: Comparison output shows changed flags accurately
- P2-D: Session/trading guardrail simulation stable and serializable
- P2-E: Insight-window status metadata testable
- P2-F: Backward compatibility preserved
- P2-G: No regressions in P0/P1 behavior
"""

import json
import unittest
from unittest.mock import MagicMock

from agentic.policy.profile_schema import (
    DomainProfile,
    ProfileRegistry,
    get_profile_registry,
)
from agentic.policy.interaction_modes import InteractionMode
from agentic.policy.policy_engine import compute_policy_flags
from agentic.policy.session_policy import SessionPolicyFlags, compute_session_policy_flags
from agentic.policy.trading_guardrail_engine import (
    TradingGuardrailFlags,
    compute_trading_guardrails,
)
from agentic.policy.policy_simulation import (
    simulate_policy,
    simulate_session_policy,
    simulate_trading_guardrails,
    compare_policy,
    compare_session_policy,
    SIM_VERSION,
)
from agentic.policy.policy_service import PolicyService


# =============================================================================
# Helpers
# =============================================================================


def _make_unified(
    coherence_score: float = 0.70,
    persona_drift: float = 0.30,
    mapper_volatility: float = 0.20,
    temporal_arc: float = 0.80,
    normalized_entropy: float = 0.40,
) -> dict:
    return {
        "coherence": {
            "coherence_score": coherence_score,
            "persona_drift_score": persona_drift,
            "mapper_volatility_score": mapper_volatility,
            "temporal_arc_score": temporal_arc,
        },
        "entropy": {"normalized_entropy": normalized_entropy},
    }


def _make_session_summary(**kwargs) -> MagicMock:
    defaults = dict(
        coherence_score=0.75,
        persona_drift_score=0.25,
        semantic_stability_score=0.70,
        temporal_arc_score=0.65,
        mapper_volatility_score=0.20,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_trading_summary(**kwargs) -> MagicMock:
    defaults = dict(
        coherence_score=0.50,
        mapper_volatility_score=0.65,
        persona_drift_score=0.50,
        tension_corridor=0.75,
        resonance_index=0.40,
        delta_smi=-0.15,
        max_tension_allowed=0.70,
        max_negative_delta_smi=0.12,
        max_volatility_allowed=0.60,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# =============================================================================
# P2-A: Parameterized defaults produce identical behavior
# =============================================================================


class TestParameterizedDefaults(unittest.TestCase):
    """Verify that parameterization with default values matches old behavior."""

    def test_policy_flags_identical_with_defaults(self):
        """Policy flags are the same with profile defaults as with old hardcoded values."""
        unified = _make_unified(coherence_score=0.50, persona_drift=0.60)
        flags = compute_policy_flags(unified, domain="trading")
        # These should match pre-P2 behavior exactly
        self.assertTrue(flags["needs_grounding"])
        self.assertEqual(flags["interaction_mode"], "analytics_only")

    def test_stability_status_stable(self):
        """Stable classification uses parameterized defaults correctly."""
        unified = _make_unified(coherence_score=0.80, persona_drift=0.20)
        flags = compute_policy_flags(unified, domain="trading")
        self.assertEqual(flags["stability_status"], "stable")

    def test_stability_status_recovering(self):
        """Recovering classification uses parameterized defaults correctly."""
        unified = _make_unified(coherence_score=0.50, persona_drift=0.50, temporal_arc=0.70)
        flags = compute_policy_flags(unified, domain="trading")
        self.assertEqual(flags["stability_status"], "recovering")

    def test_stability_status_fragmented(self):
        """Fragmented classification uses parameterized defaults correctly."""
        unified = _make_unified(coherence_score=0.40, persona_drift=0.70, temporal_arc=0.30)
        flags = compute_policy_flags(unified, domain="trading")
        self.assertEqual(flags["stability_status"], "fragmented")

    def test_session_policy_default_thresholds(self):
        """Session policy with None thresholds matches old behavior."""
        summary = _make_session_summary(coherence_score=0.80)
        flags = compute_session_policy_flags(summary, thresholds=None)
        self.assertTrue(flags.session_is_stable)
        self.assertFalse(flags.session_is_fragmented)

    def test_trading_guardrails_default_thresholds(self):
        """Trading guardrails with None thresholds matches old behavior."""
        summary = _make_trading_summary()
        flags = compute_trading_guardrails(summary, None, None, None, None, thresholds=None)
        self.assertTrue(flags.high_tension_risk)
        self.assertTrue(flags.recommend_no_action)

    def test_new_profile_fields_have_defaults(self):
        """New P2 threshold fields exist on all built-in profiles with sane defaults."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_profile_registry().get(domain)
            self.assertEqual(profile.deep_reflection_max_drift, 0.65)
            self.assertEqual(profile.session_coherence_stable, 0.70)
            self.assertEqual(profile.trading_resonance_floor, 0.45)
            self.assertEqual(profile.coherence_warning_margin, 0.10)

    def test_profile_round_trip_with_new_fields(self):
        """DomainProfile to_dict/from_dict round-trips new P2 fields."""
        profile = get_profile_registry().get("trading")
        d = profile.to_dict()
        restored = DomainProfile.from_dict(d)
        self.assertEqual(restored.deep_reflection_max_drift, 0.65)
        self.assertEqual(restored.session_coherence_stable, 0.70)
        self.assertEqual(restored.trading_drift_floor, 0.45)

    def test_profile_json_round_trip_with_new_fields(self):
        """JSON round-trip preserves new P2 fields."""
        profile = get_profile_registry().get("trading")
        json_str = profile.to_json()
        restored = DomainProfile.from_json(json_str)
        self.assertEqual(restored.stability_coherence_stable, profile.stability_coherence_stable)
        self.assertEqual(restored.concrete_entropy_ceiling, profile.concrete_entropy_ceiling)


# =============================================================================
# P2-B: Simulation with alternate profiles
# =============================================================================


class TestSimulatePolicy(unittest.TestCase):
    """Test policy simulation under default and alternate profiles."""

    def test_simulate_default_profile(self):
        """simulate_policy without custom profile uses registry default."""
        result = simulate_policy(_make_unified(), domain="trading")
        self.assertIn("flags", result)
        self.assertEqual(result["profile_id"], "trading")
        self.assertEqual(result["sim_version"], SIM_VERSION)

    def test_simulate_custom_profile(self):
        """simulate_policy with custom profile uses it."""
        custom = DomainProfile(
            profile_id="custom_trading",
            profile_version="2.0.0",
            min_coherence=0.30,  # much more lenient
        )
        unified = _make_unified(coherence_score=0.35)
        result = simulate_policy(unified, domain="trading", profile=custom)
        self.assertEqual(result["profile_id"], "custom_trading")
        # With min_coherence=0.30, coherence 0.35 should NOT trigger grounding
        self.assertFalse(result["flags"]["needs_grounding"])

    def test_simulate_does_not_pollute_registry(self):
        """Temp registration is cleaned up after simulation."""
        custom = DomainProfile(profile_id="ephemeral")
        simulate_policy(_make_unified(), domain="trading", profile=custom)
        registry = get_profile_registry()
        # The __sim__ key should not persist
        self.assertNotIn("__sim__ephemeral", registry.all_profiles())

    def test_simulate_deterministic(self):
        """Same inputs produce same simulation output."""
        u = _make_unified()
        r1 = simulate_policy(u, domain="trading")
        r2 = simulate_policy(u, domain="trading")
        self.assertEqual(r1["flags"], r2["flags"])


class TestSimulateSessionPolicy(unittest.TestCase):
    """Test session policy simulation with threshold overrides."""

    def test_default_matches_direct_call(self):
        """Simulation with no overrides matches direct compute."""
        summary = _make_session_summary()
        sim = simulate_session_policy(summary)
        direct = compute_session_policy_flags(summary)
        self.assertEqual(sim["flags"], direct.to_dict())

    def test_custom_thresholds_change_result(self):
        """Custom thresholds can make stable session become fragmented."""
        summary = _make_session_summary(coherence_score=0.65)
        # Default: 0.65 >= 0.45 → recovering (not stable, not fragmented)
        default = simulate_session_policy(summary)
        self.assertFalse(default["flags"]["session_is_fragmented"])

        # Raise threshold so 0.65 < 0.70 → recovering,
        # but raise recovering threshold too: 0.65 < 0.70 → fragmented
        custom = simulate_session_policy(
            summary,
            thresholds={"session_coherence_stable": 0.90, "session_coherence_recovering": 0.70},
        )
        self.assertTrue(custom["flags"]["session_is_fragmented"])

    def test_profile_based_thresholds(self):
        """Profile-extracted thresholds work in session simulation."""
        profile = DomainProfile(
            profile_id="strict",
            session_coherence_stable=0.90,
        )
        summary = _make_session_summary(coherence_score=0.80)
        result = simulate_session_policy(summary, profile=profile)
        # 0.80 < 0.90 → not stable
        self.assertFalse(result["flags"]["session_is_stable"])

    def test_serializable_output(self):
        """Simulation output is JSON-serializable."""
        result = simulate_session_policy(_make_session_summary())
        json.dumps(result)  # should not raise


class TestSimulateTradingGuardrails(unittest.TestCase):
    """Test trading guardrail simulation."""

    def test_default_matches_direct_call(self):
        """Simulation with no overrides matches direct compute."""
        summary = _make_trading_summary()
        sim = simulate_trading_guardrails(summary)
        direct = compute_trading_guardrails(summary, None, None, None, None)
        self.assertEqual(sim["flags"], direct.to_dict())

    def test_custom_thresholds_suppress_risk(self):
        """Loosening thresholds can suppress risk flags."""
        summary = _make_trading_summary(
            resonance_index=0.40,  # normally below 0.45 → triggers risk
        )
        # Default: resonance 0.40 < 0.45 → high_tension_risk
        default = simulate_trading_guardrails(summary)
        self.assertTrue(default["flags"]["high_tension_risk"])

        # Lower floor so 0.40 >= 0.35 → no risk
        custom = simulate_trading_guardrails(
            summary,
            thresholds={"trading_resonance_floor": 0.35},
        )
        self.assertFalse(custom["flags"]["high_tension_risk"])

    def test_serializable_output(self):
        """Simulation output is JSON-serializable."""
        result = simulate_trading_guardrails(_make_trading_summary())
        json.dumps(result)  # should not raise


# =============================================================================
# P2-C: Comparison outputs
# =============================================================================


class TestComparePolicy(unittest.TestCase):
    """Test policy comparison between baseline and candidate."""

    def test_identical_profiles_no_changes(self):
        """Same profile produces is_identical=True."""
        baseline_profile = get_profile_registry().get("trading")
        result = compare_policy(
            _make_unified(),
            domain="trading",
            candidate_profile=baseline_profile,
        )
        self.assertTrue(result["is_identical"])
        self.assertEqual(result["changed_flags"], [])

    def test_different_profiles_show_changes(self):
        """Different profile surfaces changed flags with correct direction."""
        candidate = DomainProfile(
            profile_id="lenient_trading",
            min_coherence=0.20,  # much more lenient than trading's 0.55
        )
        # coherence 0.45: below trading min (0.55) but above candidate min (0.20)
        unified = _make_unified(coherence_score=0.45)
        result = compare_policy(unified, domain="trading", candidate_profile=candidate)
        self.assertFalse(result["is_identical"])
        self.assertIn("needs_grounding", result["changed_flags"])
        # Verify the actual flag values differ in the expected direction
        self.assertTrue(
            result["baseline"]["flags"]["needs_grounding"],
            "Baseline (min_coherence=0.55): 0.45 < 0.55 → needs_grounding=True",
        )
        self.assertFalse(
            result["candidate"]["flags"]["needs_grounding"],
            "Candidate (min_coherence=0.20): 0.45 >= 0.20 → needs_grounding=False",
        )

    def test_comparison_has_both_results_with_real_flags(self):
        """Comparison includes baseline and candidate with real policy flags."""
        candidate = DomainProfile(profile_id="alt")
        result = compare_policy(_make_unified(), domain="trading", candidate_profile=candidate)
        self.assertIn("baseline", result)
        self.assertIn("candidate", result)
        # Verify both contain real policy flag keys, not empty dicts
        for key in ("needs_grounding", "stability_status", "interaction_mode"):
            self.assertIn(key, result["baseline"]["flags"])
            self.assertIn(key, result["candidate"]["flags"])

    def test_comparison_serializable(self):
        """Comparison output is JSON-serializable."""
        candidate = DomainProfile(profile_id="alt")
        result = compare_policy(_make_unified(), domain="trading", candidate_profile=candidate)
        json.dumps(result)  # should not raise


class TestCompareSessionPolicy(unittest.TestCase):
    """Test session policy comparison."""

    def test_identical_thresholds_no_changes(self):
        """Same thresholds produce is_identical=True."""
        summary = _make_session_summary()
        result = compare_session_policy(summary)
        self.assertTrue(result["is_identical"])

    def test_different_thresholds_show_changes(self):
        """Different thresholds surface changed flags."""
        summary = _make_session_summary(coherence_score=0.65)
        result = compare_session_policy(
            summary,
            candidate_thresholds={"session_coherence_stable": 0.60},
        )
        # 0.65 >= 0.60 → stable in candidate, but 0.65 < 0.70 → recovering in baseline
        self.assertFalse(result["is_identical"])
        self.assertIn("session_is_stable", result["changed_flags"])


# =============================================================================
# P2-D: PolicyService simulation methods
# =============================================================================


class TestPolicyServiceSimulation(unittest.TestCase):
    """Test PolicyService P2 simulation methods."""

    def setUp(self):
        self.svc = PolicyService()

    def test_simulate_policy_method(self):
        """PolicyService.simulate_policy() works."""
        result = self.svc.simulate_policy(_make_unified(), domain="trading")
        self.assertIn("flags", result)
        self.assertEqual(result["sim_version"], SIM_VERSION)

    def test_compare_policy_method(self):
        """PolicyService.compare_policy() returns structured comparison."""
        candidate = DomainProfile(
            profile_id="lenient",
            min_coherence=0.20,
        )
        # coherence 0.45: triggers grounding under trading (0.55) but not lenient (0.20)
        result = self.svc.compare_policy(
            _make_unified(coherence_score=0.45),
            domain="trading", candidate_profile=candidate,
        )
        self.assertIn("changed_flags", result)
        self.assertIn("needs_grounding", result["changed_flags"])
        self.assertFalse(result["is_identical"])

    def test_simulate_session_policy_method(self):
        """PolicyService.simulate_session_policy() works."""
        result = self.svc.simulate_session_policy(_make_session_summary())
        self.assertIn("flags", result)

    def test_simulate_trading_guardrails_method(self):
        """PolicyService.simulate_trading_guardrails() works."""
        result = self.svc.simulate_trading_guardrails(_make_trading_summary())
        self.assertIn("flags", result)

    def test_compute_policy_includes_profile_metadata(self):
        """compute_policy() now includes profile_id and profile_version."""
        result = self.svc.compute_policy(_make_unified(), domain="trading")
        self.assertEqual(result["profile_id"], "trading")
        self.assertIn("profile_version", result)


# =============================================================================
# P2-E: Insight-window status metadata
# =============================================================================


class TestInsightWindowStatus(unittest.TestCase):
    """Test insight-window operational metadata."""

    def test_policy_engine_status_dict(self):
        """insight_window_gating.INSIGHT_WINDOW_STATUS is well-formed."""
        from agentic.policy.insight_window_gating import INSIGHT_WINDOW_STATUS
        self.assertEqual(INSIGHT_WINDOW_STATUS["path"], "policy_engine")
        self.assertEqual(INSIGHT_WINDOW_STATUS["schema"], "InsightWindowResult")
        self.assertEqual(INSIGHT_WINDOW_STATUS["status"], "active")
        self.assertTrue(INSIGHT_WINDOW_STATUS["canonical"])
        self.assertTrue(INSIGHT_WINDOW_STATUS["consolidation_target"])

    def test_pipeline_native_status_dict(self):
        """insight_window.INSIGHT_WINDOW_STATUS is well-formed."""
        from agentic.policy.insight_window import INSIGHT_WINDOW_STATUS
        self.assertEqual(INSIGHT_WINDOW_STATUS["path"], "pipeline_native")
        self.assertEqual(INSIGHT_WINDOW_STATUS["schema"], "InsightWindowEnvelope")
        self.assertEqual(INSIGHT_WINDOW_STATUS["status"], "active")
        self.assertTrue(INSIGHT_WINDOW_STATUS["canonical"])

    def test_both_paths_different(self):
        """The two systems have different paths and schemas."""
        from agentic.policy.insight_window_gating import INSIGHT_WINDOW_STATUS as pe
        from agentic.policy.insight_window import INSIGHT_WINDOW_STATUS as pn
        self.assertNotEqual(pe["path"], pn["path"])
        self.assertNotEqual(pe["schema"], pn["schema"])

    def test_status_metadata_serializable(self):
        """Status dicts are JSON-serializable."""
        from agentic.policy.insight_window_gating import INSIGHT_WINDOW_STATUS as pe
        from agentic.policy.insight_window import INSIGHT_WINDOW_STATUS as pn
        json.dumps(pe)
        json.dumps(pn)


# =============================================================================
# P2-F: Registry enhancements
# =============================================================================


class TestRegistryEnhancements(unittest.TestCase):
    """Test ProfileRegistry P2 additions."""

    def test_register_with_domain_id_override(self):
        """register() accepts domain_id override."""
        registry = get_profile_registry()
        profile = DomainProfile(profile_id="original_id")
        registry.register(profile, domain_id="custom_key")
        self.assertIs(registry.get("custom_key"), profile)
        registry.unregister("custom_key")

    def test_unregister_existing(self):
        """unregister() removes a registered profile."""
        registry = get_profile_registry()
        profile = DomainProfile(profile_id="temp")
        registry.register(profile, domain_id="temp_key")
        self.assertTrue(registry.unregister("temp_key"))
        # Should now fall back to generic
        result = registry.get("temp_key")
        self.assertEqual(result.profile_id, "generic")

    def test_unregister_nonexistent(self):
        """unregister() returns False for unknown key."""
        registry = get_profile_registry()
        self.assertFalse(registry.unregister("nonexistent_key_xyz"))


# =============================================================================
# P2-G: Backward compatibility / P0+P1 regression
# =============================================================================


class TestP2BackwardCompat(unittest.TestCase):
    """Ensure P0 and P1 functionality is not broken by P2."""

    def test_version_at_least_1_3(self):
        """Package version is at least 1.3.0 after P2."""
        from agentic.policy import __version__
        major, minor, patch = (int(x) for x in __version__.split("."))
        self.assertGreaterEqual((major, minor), (1, 3))

    def test_p0_exports_present(self):
        from agentic.policy import DomainProfile, ProfileRegistry, get_profile_registry
        self.assertIsNotNone(DomainProfile)

    def test_p1_exports_present(self):
        from agentic.policy import PolicyService, get_policy_service, P1_VERSION
        self.assertIsNotNone(PolicyService)

    def test_p2_exports_present(self):
        from agentic.policy import (
            simulate_policy, compare_policy, SIM_VERSION,
            simulate_session_policy, simulate_trading_guardrails,
            compare_session_policy,
        )
        self.assertIsNotNone(simulate_policy)

    def test_facade_markers_unchanged(self):
        from agentic.policy.governance_binding import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "provisional")

    def test_insight_window_path_markers_unchanged(self):
        from agentic.policy.insight_window_gating import _INSIGHT_WINDOW_PATH
        self.assertEqual(_INSIGHT_WINDOW_PATH, "policy_engine")
        from agentic.policy.insight_window import _INSIGHT_WINDOW_PATH as pn
        self.assertEqual(pn, "pipeline_native")

    def test_direct_policy_engine_still_works(self):
        """Direct call to compute_policy_flags still works without changes."""
        flags = compute_policy_flags(_make_unified(), domain="trading")
        self.assertIn("needs_grounding", flags)
        self.assertIn("interaction_mode", flags)

    def test_direct_session_policy_still_works(self):
        """Direct call without thresholds still works."""
        result = compute_session_policy_flags(_make_session_summary())
        self.assertIsInstance(result, SessionPolicyFlags)

    def test_direct_trading_guardrails_still_works(self):
        """Direct call without thresholds still works."""
        result = compute_trading_guardrails(
            _make_trading_summary(), None, None, None, None
        )
        self.assertIsInstance(result, TradingGuardrailFlags)


if __name__ == "__main__":
    unittest.main()
