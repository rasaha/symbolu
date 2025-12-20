"""
Phase 15: Interaction Mode Layer v1.0 Tests

Comprehensive test suite for Phase 15 interaction modes.
Tests are organized into 4 groups:

GROUP A — Mode Resolution (8 tests)
    Tests for resolve_interaction_mode() function

GROUP B — Policy Behavior (8 tests)
    Tests for compute_policy_flags() with interaction modes

GROUP C — Unified API + Adapter (4 tests)
    Tests for unified API and DILchat adapter integration

GROUP D — Behavioral Invariance (4 tests)
    Tests for backward compatibility and determinism

Design Principles:
    - All tests are deterministic
    - Tests verify zero-LLM behavior
    - Tests ensure no routing/mapper changes
    - Tests verify backward compatibility
"""

import pytest
from symbolu.policy.interaction_modes import (
    InteractionMode,
    resolve_interaction_mode,
    get_mode_name,
    is_mode_valid,
    _parse_interaction_mode,
)
from symbolu.policy.policy_engine import compute_policy_flags
from symbolu.policy.domain_profiles import get_domain_profile, DOMAIN_PROFILES
from symbolu.adapter.dilchat_adapter import build_dilchat_response, _build_hints


# ==============================================================================
# GROUP A — Mode Resolution (8 tests)
# ==============================================================================


class TestGroupA_ModeResolution:
    """Tests for resolve_interaction_mode() function."""

    def test_admin_override_takes_priority(self):
        """Admin override should take highest priority."""
        profile = {"interaction_mode_default": InteractionMode.ANALYTICS_ONLY}

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override="smart_insight",
            admin_override="deep_adaptive",
        )

        assert result == InteractionMode.DEEP_ADAPTIVE

    def test_user_override_takes_second_priority(self):
        """User override should take priority over domain default."""
        profile = {"interaction_mode_default": InteractionMode.ANALYTICS_ONLY}

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override="smart_insight",
            admin_override=None,
        )

        assert result == InteractionMode.SMART_INSIGHT

    def test_domain_default_used_when_no_override(self):
        """Domain default should be used when no overrides provided."""
        profile = {"interaction_mode_default": InteractionMode.SMART_INSIGHT}

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override=None,
            admin_override=None,
        )

        assert result == InteractionMode.SMART_INSIGHT

    def test_invalid_admin_override_falls_through(self):
        """Invalid admin override should fall through to user override."""
        profile = {"interaction_mode_default": InteractionMode.ANALYTICS_ONLY}

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override="smart_insight",
            admin_override="invalid_mode",
        )

        assert result == InteractionMode.SMART_INSIGHT

    def test_invalid_user_override_falls_through(self):
        """Invalid user override should fall through to domain default."""
        profile = {"interaction_mode_default": InteractionMode.DEEP_ADAPTIVE}

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override="invalid_mode",
            admin_override=None,
        )

        assert result == InteractionMode.DEEP_ADAPTIVE

    def test_all_invalid_falls_to_analytics_only(self):
        """All invalid/missing should fallback to ANALYTICS_ONLY."""
        profile = {}  # No default set

        result = resolve_interaction_mode(
            domain_profile=profile,
            user_override="invalid",
            admin_override="also_invalid",
        )

        assert result == InteractionMode.ANALYTICS_ONLY

    def test_deterministic_output_repeated_calls(self):
        """Same input should produce same output on repeated calls."""
        profile = {"interaction_mode_default": InteractionMode.SMART_INSIGHT}

        results = []
        for _ in range(10):
            result = resolve_interaction_mode(
                domain_profile=profile,
                user_override="deep_adaptive",
                admin_override=None,
            )
            results.append(result)

        # All results should be identical
        assert all(r == InteractionMode.DEEP_ADAPTIVE for r in results)

    def test_case_insensitive_string_parsing(self):
        """String parsing should be case-insensitive."""
        profile = {"interaction_mode_default": InteractionMode.ANALYTICS_ONLY}

        # Test various case combinations
        result_lower = resolve_interaction_mode(profile, user_override="deep_adaptive")
        result_upper = resolve_interaction_mode(profile, user_override="DEEP_ADAPTIVE")
        result_mixed = resolve_interaction_mode(profile, user_override="Deep_Adaptive")

        assert result_lower == InteractionMode.DEEP_ADAPTIVE
        assert result_upper == InteractionMode.DEEP_ADAPTIVE
        assert result_mixed == InteractionMode.DEEP_ADAPTIVE


# ==============================================================================
# GROUP B — Policy Behavior (8 tests)
# ==============================================================================


class TestGroupB_PolicyBehavior:
    """Tests for compute_policy_flags() with interaction modes."""

    @pytest.fixture
    def base_unified_output(self):
        """Base unified output for testing."""
        return {
            "coherence": {
                "coherence_score": 0.75,
                "persona_drift_score": 0.30,
                "mapper_volatility_score": 0.25,
                "temporal_arc_score": 0.80,
                "resonance_index": 0.70,
                "tension_index": 0.40,
                "arc_alignment_index": 0.65,
            },
            "entropy": {"normalized_entropy": 0.40},
            "formulas": {
                "vritti_momentum": 0.72,
                "arc_tension_harmonizer": 0.65,
            },
        }

    def test_mode_1_analytics_only_produces_original_behavior(self, base_unified_output):
        """ANALYTICS_ONLY mode should produce Phase 1-12 behavior only."""
        flags = compute_policy_flags(
            unified=base_unified_output,
            domain="trading",  # Trading defaults to ANALYTICS_ONLY
        )

        # Should have interaction_mode field
        assert flags["interaction_mode"] == "analytics_only"

        # Should NOT have VMF/ATH hint flags
        assert "vmf_emotional_momentum" not in flags
        assert "ath_arc_tension_state" not in flags

    def test_mode_2_smart_insight_activates_phase5_refinements(self, base_unified_output):
        """SMART_INSIGHT mode should activate Phase 5 refinements."""
        flags = compute_policy_flags(
            unified=base_unified_output,
            domain="therapy",  # Therapy defaults to SMART_INSIGHT
        )

        assert flags["interaction_mode"] == "smart_insight"

        # Should have formula refinement applied (Phase 5)
        # With high resonance and low tension, allow_deep_reflection should be True
        assert flags["allow_deep_reflection"] is True

        # Should NOT have VMF/ATH hints (those are only for DEEP_ADAPTIVE)
        assert "vmf_emotional_momentum" not in flags
        assert "ath_arc_tension_state" not in flags

    def test_mode_3_deep_adaptive_activates_vmf_ath_hints(self, base_unified_output):
        """DEEP_ADAPTIVE mode should activate VMF/ATH hint flags."""
        flags = compute_policy_flags(
            unified=base_unified_output,
            domain="therapy",
            admin_mode_override="deep_adaptive",
        )

        assert flags["interaction_mode"] == "deep_adaptive"

        # Should have VMF/ATH hint flags
        assert "vmf_emotional_momentum" in flags
        assert "ath_arc_tension_state" in flags

        # With vritti_momentum=0.72 (>= 0.65), should be "rising"
        assert flags["vmf_emotional_momentum"] == "rising"

        # With arc_tension_harmonizer=0.65 (>= 0.40, < 0.70), should be "building"
        assert flags["ath_arc_tension_state"] == "building"

    def test_no_routing_mappers_affected_in_any_mode(self, base_unified_output):
        """No mode should affect routing or mapper recommendations."""
        modes = [None, "analytics_only", "smart_insight", "deep_adaptive"]
        mapper_results = []

        for mode in modes:
            flags = compute_policy_flags(
                unified=base_unified_output,
                domain="therapy",
                admin_mode_override=mode,
            )
            mapper_results.append(flags["recommended_mapper"])

        # All modes should produce the same mapper recommendation
        assert len(set(mapper_results)) == 1

    def test_mode_override_via_user_parameter(self, base_unified_output):
        """User override should change mode from domain default."""
        # Trading defaults to ANALYTICS_ONLY
        flags = compute_policy_flags(
            unified=base_unified_output,
            domain="trading",
            user_mode_override="smart_insight",
        )

        assert flags["interaction_mode"] == "smart_insight"

    def test_mode_override_via_admin_parameter(self, base_unified_output):
        """Admin override should take priority over user override."""
        flags = compute_policy_flags(
            unified=base_unified_output,
            domain="trading",
            user_mode_override="smart_insight",
            admin_mode_override="deep_adaptive",
        )

        assert flags["interaction_mode"] == "deep_adaptive"

    def test_deep_adaptive_missing_formulas_handles_gracefully(self):
        """DEEP_ADAPTIVE should handle missing formula data gracefully."""
        unified = {
            "coherence": {
                "coherence_score": 0.75,
                "persona_drift_score": 0.30,
                "mapper_volatility_score": 0.25,
                "temporal_arc_score": 0.80,
            },
            "entropy": {"normalized_entropy": 0.40},
            # No formulas field
        }

        flags = compute_policy_flags(
            unified=unified,
            domain="therapy",
            admin_mode_override="deep_adaptive",
        )

        assert flags["interaction_mode"] == "deep_adaptive"
        assert flags["vmf_emotional_momentum"] is None
        assert flags["ath_arc_tension_state"] is None

    def test_vmf_ath_thresholds_correct(self, base_unified_output):
        """VMF/ATH thresholds should match specification."""
        # Test falling VMF (< 0.35)
        unified_falling = base_unified_output.copy()
        unified_falling["formulas"] = {
            "vritti_momentum": 0.30,
            "arc_tension_harmonizer": 0.30,
        }

        flags = compute_policy_flags(
            unified=unified_falling,
            domain="therapy",
            admin_mode_override="deep_adaptive",
        )

        assert flags["vmf_emotional_momentum"] == "falling"
        assert flags["ath_arc_tension_state"] == "releasing"

        # Test stable VMF (0.35 <= x < 0.65)
        unified_stable = base_unified_output.copy()
        unified_stable["formulas"] = {
            "vritti_momentum": 0.50,
            "arc_tension_harmonizer": 0.75,
        }

        flags = compute_policy_flags(
            unified=unified_stable,
            domain="therapy",
            admin_mode_override="deep_adaptive",
        )

        assert flags["vmf_emotional_momentum"] == "stable"
        assert flags["ath_arc_tension_state"] == "harmonized"


# ==============================================================================
# GROUP C — Unified API + Adapter (4 tests)
# ==============================================================================


class TestGroupC_UnifiedApiAdapter:
    """Tests for unified API and DILchat adapter integration."""

    def test_mode_reflected_in_unified_output(self):
        """Interaction mode should be reflected in unified output."""
        # This tests the data model; actual extraction depends on context
        from symbolu.api.unified_api import UnifiedOutput

        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
            interaction_mode="smart_insight",
        )

        output_dict = output.to_dict()
        assert output_dict["interaction_mode"] == "smart_insight"

    def test_mode_reflected_in_adapter_hints(self):
        """Mode should produce correct DILchat hints."""
        policy_flags = {
            "stability_status": "stable",
            "needs_grounding": False,
            "allow_deep_reflection": True,
            "prefer_concrete": False,
            "prefer_arc_mode": False,
            "coherence_warning": False,
            "interaction_mode": "smart_insight",
        }

        hints = _build_hints(policy_flags, domain="therapy")

        # Should have HINT_SELF_REFLECTION_ALLOWED for SMART_INSIGHT
        hint_codes = [h.code for h in hints]
        assert "HINT_SELF_REFLECTION_ALLOWED" in hint_codes

    def test_correct_fallback_when_mode_missing(self):
        """Adapter should handle missing mode gracefully."""
        policy_flags = {
            "stability_status": "stable",
            "needs_grounding": False,
            "allow_deep_reflection": True,
            "prefer_concrete": False,
            "prefer_arc_mode": False,
            "coherence_warning": False,
            # No interaction_mode
        }

        hints = _build_hints(policy_flags, domain="therapy")

        # Should not crash, and should not have mode hints
        hint_codes = [h.code for h in hints]
        assert "HINT_STABLE_NEUTRAL" not in hint_codes
        assert "HINT_SELF_REFLECTION_ALLOWED" not in hint_codes
        assert "HINT_DEEP_ADAPTIVE_ACTIVE" not in hint_codes

    def test_deterministic_adapter_responses(self):
        """Adapter should produce deterministic responses."""
        unified = {
            "text": "Test response",
            "coherence": {"coherence_score": 0.75},
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "stability_status": "stable",
            "needs_grounding": False,
            "allow_deep_reflection": True,
            "prefer_concrete": False,
            "prefer_arc_mode": False,
            "coherence_warning": False,
            "recommended_style": "reflective",
            "recommended_mapper": "HRM",
            "interaction_mode": "deep_adaptive",
            "vmf_emotional_momentum": "rising",
            "ath_arc_tension_state": "harmonized",
        }

        results = []
        for _ in range(5):
            response = build_dilchat_response(unified, policy_flags, "therapy")
            results.append(len(response.hints))

        # All results should be identical
        assert len(set(results)) == 1


# ==============================================================================
# GROUP D — Behavioral Invariance (4 tests)
# ==============================================================================


class TestGroupD_BehavioralInvariance:
    """Tests for backward compatibility and determinism."""

    def test_trading_domain_unchanged(self):
        """Trading domain behavior should remain 100% unchanged."""
        unified = {
            "coherence": {
                "coherence_score": 0.50,
                "persona_drift_score": 0.45,
                "mapper_volatility_score": 0.40,
                "temporal_arc_score": 0.65,
            },
            "entropy": {"normalized_entropy": 0.50},
        }

        flags = compute_policy_flags(unified, "trading")

        # Trading should default to ANALYTICS_ONLY
        assert flags["interaction_mode"] == "analytics_only"

        # Standard policy flags should work as before
        assert "needs_grounding" in flags
        assert "stability_status" in flags
        assert "recommended_mapper" in flags

        # Trading should prefer LCM/HRM
        assert flags["recommended_mapper"] in ["LCM", "HRM"]

    def test_generic_domain_unchanged(self):
        """Generic domain behavior should remain 100% unchanged."""
        unified = {
            "coherence": {
                "coherence_score": 0.60,
                "persona_drift_score": 0.40,
                "mapper_volatility_score": 0.35,
                "temporal_arc_score": 0.70,
            },
            "entropy": {"normalized_entropy": 0.45},
        }

        flags = compute_policy_flags(unified, "generic")

        # Generic should default to ANALYTICS_ONLY
        assert flags["interaction_mode"] == "analytics_only"

        # Should not have VMF/ATH hints
        assert "vmf_emotional_momentum" not in flags
        assert "ath_arc_tension_state" not in flags

    def test_therapy_identity_compatible_with_modes(self):
        """Therapy/identity should work correctly with mode selection."""
        unified = {
            "coherence": {
                "coherence_score": 0.70,
                "persona_drift_score": 0.35,
                "mapper_volatility_score": 0.30,
                "temporal_arc_score": 0.75,
                "resonance_index": 0.65,
                "tension_index": 0.35,
                "arc_alignment_index": 0.70,
            },
            "entropy": {"normalized_entropy": 0.40},
            "formulas": {
                "vritti_momentum": 0.60,
                "arc_tension_harmonizer": 0.55,
            },
        }

        # Test therapy with default mode
        therapy_flags = compute_policy_flags(unified, "therapy")
        assert therapy_flags["interaction_mode"] == "smart_insight"

        # Test identity with default mode
        identity_flags = compute_policy_flags(unified, "identity")
        assert identity_flags["interaction_mode"] == "smart_insight"

        # Both should allow mode override
        therapy_override = compute_policy_flags(
            unified, "therapy", admin_mode_override="deep_adaptive"
        )
        assert therapy_override["interaction_mode"] == "deep_adaptive"

    def test_determinism_over_repeated_runs(self):
        """Same input should always produce same output."""
        unified = {
            "coherence": {
                "coherence_score": 0.65,
                "persona_drift_score": 0.40,
                "mapper_volatility_score": 0.35,
                "temporal_arc_score": 0.70,
                "resonance_index": 0.60,
                "tension_index": 0.45,
                "arc_alignment_index": 0.55,
            },
            "entropy": {"normalized_entropy": 0.42},
            "formulas": {
                "vritti_momentum": 0.55,
                "arc_tension_harmonizer": 0.50,
            },
        }

        # Run 20 times and collect results
        results = []
        for _ in range(20):
            flags = compute_policy_flags(
                unified,
                "therapy",
                admin_mode_override="deep_adaptive",
            )
            results.append(str(flags))

        # All results should be identical
        assert len(set(results)) == 1


# ==============================================================================
# Additional Helper Tests
# ==============================================================================


class TestHelperFunctions:
    """Tests for helper functions in interaction_modes module."""

    def test_get_mode_name(self):
        """get_mode_name should return human-readable names."""
        assert get_mode_name(InteractionMode.ANALYTICS_ONLY) == "Analytics Only"
        assert get_mode_name(InteractionMode.SMART_INSIGHT) == "Smart Insight"
        assert get_mode_name(InteractionMode.DEEP_ADAPTIVE) == "Deep Adaptive"

    def test_is_mode_valid(self):
        """is_mode_valid should correctly identify valid modes."""
        # Valid string values
        assert is_mode_valid("analytics_only") is True
        assert is_mode_valid("smart_insight") is True
        assert is_mode_valid("deep_adaptive") is True

        # Valid enum values
        assert is_mode_valid(InteractionMode.ANALYTICS_ONLY) is True

        # Invalid values
        assert is_mode_valid("invalid") is False
        assert is_mode_valid("") is False
        assert is_mode_valid(None) is False
        assert is_mode_valid(123) is False

    def test_parse_interaction_mode_handles_all_inputs(self):
        """_parse_interaction_mode should handle all input types."""
        # Enum
        assert _parse_interaction_mode(InteractionMode.SMART_INSIGHT) == InteractionMode.SMART_INSIGHT

        # String (value)
        assert _parse_interaction_mode("smart_insight") == InteractionMode.SMART_INSIGHT

        # String (name)
        assert _parse_interaction_mode("SMART_INSIGHT") == InteractionMode.SMART_INSIGHT

        # None
        assert _parse_interaction_mode(None) is None

        # Invalid
        assert _parse_interaction_mode("invalid") is None
        assert _parse_interaction_mode(123) is None


class TestDomainProfileDefaults:
    """Tests to verify domain profile defaults are set correctly."""

    def test_trading_defaults_to_analytics_only(self):
        """Trading domain should default to ANALYTICS_ONLY."""
        profile = get_domain_profile("trading")
        assert profile["interaction_mode_default"] == InteractionMode.ANALYTICS_ONLY

    def test_generic_defaults_to_analytics_only(self):
        """Generic domain should default to ANALYTICS_ONLY."""
        profile = get_domain_profile("generic")
        assert profile["interaction_mode_default"] == InteractionMode.ANALYTICS_ONLY

    def test_therapy_defaults_to_smart_insight(self):
        """Therapy domain should default to SMART_INSIGHT."""
        profile = get_domain_profile("therapy")
        assert profile["interaction_mode_default"] == InteractionMode.SMART_INSIGHT

    def test_identity_defaults_to_smart_insight(self):
        """Identity domain should default to SMART_INSIGHT."""
        profile = get_domain_profile("identity")
        assert profile["interaction_mode_default"] == InteractionMode.SMART_INSIGHT

    def test_all_profiles_have_interaction_mode_default(self):
        """All domain profiles should have interaction_mode_default."""
        for domain_name, profile in DOMAIN_PROFILES.items():
            assert "interaction_mode_default" in profile, f"{domain_name} missing interaction_mode_default"
            assert isinstance(profile["interaction_mode_default"], InteractionMode)


class TestDeepAdaptiveHints:
    """Tests for DEEP_ADAPTIVE mode DILchat hints."""

    def test_deep_adaptive_produces_base_hint(self):
        """DEEP_ADAPTIVE mode should produce HINT_DEEP_ADAPTIVE_ACTIVE."""
        policy_flags = {
            "interaction_mode": "deep_adaptive",
            "vmf_emotional_momentum": "rising",
            "ath_arc_tension_state": "harmonized",
        }

        hints = _build_hints(policy_flags, domain="therapy")
        hint_codes = [h.code for h in hints]

        assert "HINT_DEEP_ADAPTIVE_ACTIVE" in hint_codes

    def test_vmf_momentum_hints(self):
        """VMF momentum hints should be generated correctly."""
        # Rising
        flags_rising = {"interaction_mode": "deep_adaptive", "vmf_emotional_momentum": "rising"}
        hints_rising = _build_hints(flags_rising, domain="therapy")
        assert any(h.code == "VMF_MOMENTUM_RISING" for h in hints_rising)

        # Falling
        flags_falling = {"interaction_mode": "deep_adaptive", "vmf_emotional_momentum": "falling"}
        hints_falling = _build_hints(flags_falling, domain="therapy")
        assert any(h.code == "VMF_MOMENTUM_FALLING" for h in hints_falling)

        # Stable
        flags_stable = {"interaction_mode": "deep_adaptive", "vmf_emotional_momentum": "stable"}
        hints_stable = _build_hints(flags_stable, domain="therapy")
        assert any(h.code == "VMF_MOMENTUM_STABLE" for h in hints_stable)

    def test_ath_state_hints(self):
        """ATH state hints should be generated correctly."""
        # Harmonized
        flags_harm = {"interaction_mode": "deep_adaptive", "ath_arc_tension_state": "harmonized"}
        hints_harm = _build_hints(flags_harm, domain="therapy")
        assert any(h.code == "ATH_HARMONIZED" for h in hints_harm)

        # Building
        flags_build = {"interaction_mode": "deep_adaptive", "ath_arc_tension_state": "building"}
        hints_build = _build_hints(flags_build, domain="therapy")
        assert any(h.code == "ATH_BUILDING" for h in hints_build)

        # Releasing
        flags_rel = {"interaction_mode": "deep_adaptive", "ath_arc_tension_state": "releasing"}
        hints_rel = _build_hints(flags_rel, domain="therapy")
        assert any(h.code == "ATH_RELEASING" for h in hints_rel)


# ==============================================================================
# Run tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
