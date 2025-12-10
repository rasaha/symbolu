"""
Phase 12: Coherence v3 Quality Integration Tests

Tests the complete integration of v3 quality gating across:
- PolicyEngine (quality-based v3 selection)
- UnifiedOutput API (v3 quality in coherence block)
- DILchat adapter (v3 confidence hints)
- Domain profiles (quality thresholds)

Verifies:
- Policy gating: v3 used only when quality >= threshold
- Invariance: trading/generic unchanged
- Unified API wiring: v3 quality present
- DILchat hints: v3 confidence hints for therapy/identity only
"""

import pytest
from symbolu.policy.policy_engine import compute_policy_flags, _get_active_coherence_score
from symbolu.policy.domain_profiles import get_domain_profile
from symbolu.adapter.dilchat_adapter import build_dilchat_response


class TestPhase12PolicyGating:
    """Test v3 quality gating in PolicyEngine."""

    def test_therapy_high_quality_uses_v3(self):
        """Test that therapy domain uses v3 when quality is high."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.65,  # High quality (> 0.40 therapy threshold)
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("therapy")
        active_coherence = _get_active_coherence_score(unified, profile)

        assert active_coherence == 0.82, "Should use v3 when quality is high"

    def test_therapy_low_quality_falls_back_to_v2(self):
        """Test that therapy domain falls back to v2 when quality is low."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.20,  # Low quality (< 0.40 therapy threshold)
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("therapy")
        active_coherence = _get_active_coherence_score(unified, profile)

        assert active_coherence == 0.7, "Should fall back to v2 when quality is low"

    def test_identity_quality_threshold_is_stricter(self):
        """Test that identity domain has stricter threshold than therapy."""
        # Quality = 0.42 (between therapy 0.40 and identity 0.45 thresholds)
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.42,
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        therapy_profile = get_domain_profile("therapy")
        identity_profile = get_domain_profile("identity")

        # Therapy should use v3 (0.42 >= 0.40)
        therapy_coherence = _get_active_coherence_score(unified, therapy_profile)
        assert therapy_coherence == 0.82, "Therapy should use v3 with quality 0.42"

        # Identity should fall back to v2 (0.42 < 0.45)
        identity_coherence = _get_active_coherence_score(unified, identity_profile)
        assert identity_coherence == 0.7, "Identity should fall back to v2 with quality 0.42"

    def test_trading_never_uses_v3(self):
        """Test that trading domain never uses v3 regardless of quality."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # Very high quality
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("trading")
        active_coherence = _get_active_coherence_score(unified, profile)

        # Trading should use v1 (v3 disabled in profile)
        assert active_coherence == 0.6, "Trading should never use v3"

    def test_generic_never_uses_v3(self):
        """Test that generic domain never uses v3 regardless of quality."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # Very high quality
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("generic")
        active_coherence = _get_active_coherence_score(unified, profile)

        # Generic should use v1 (v3 disabled in profile)
        assert active_coherence == 0.6, "Generic should never use v3"

    def test_missing_v3_quality_prevents_v3_usage(self):
        """Test that missing quality prevents v3 usage even if v3 is available."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": None,  # Missing quality
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("therapy")
        active_coherence = _get_active_coherence_score(unified, profile)

        assert active_coherence == 0.7, "Should fall back to v2 when quality is missing"

    def test_policy_flags_respect_quality_gated_v3(self):
        """Test that policy flags use quality-gated v3 score."""
        # High quality v3
        unified_high_quality = {
            "coherence": {
                "coherence_score": 0.6,  # Would fail min_coherence (0.45)
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.80,  # Passes min_coherence
                "coherence_v3_quality": 0.65,  # High quality
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        flags_high_quality = compute_policy_flags(unified_high_quality, "therapy")
        # Should NOT need grounding (v3 score 0.80 >= 0.45)
        assert not flags_high_quality["needs_grounding"], \
            "Should not need grounding when quality-gated v3 passes threshold"

        # Low quality v3
        unified_low_quality = {
            "coherence": {
                "coherence_score": 0.6,  # Would fail min_coherence (0.45)
                "coherence_score_v2": 0.42,  # Also fails
                "coherence_score_v3": 0.80,  # High but not used
                "coherence_v3_quality": 0.20,  # Low quality (below threshold)
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        flags_low_quality = compute_policy_flags(unified_low_quality, "therapy")
        # Should need grounding (v2 score 0.42 < 0.45, v3 not used due to low quality)
        assert flags_low_quality["needs_grounding"], \
            "Should need grounding when quality-gated v3 falls back to low v2"


class TestPhase12DILchatHints:
    """Test v3 confidence hints in DILchat adapter."""

    def test_therapy_high_quality_gets_high_confidence_hint(self):
        """Test that therapy with high quality gets V3_CONFIDENCE_HIGH hint."""
        unified = {
            "text": "Let's explore your feelings...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.75,  # High quality
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "therapy"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "therapy")

        # Check for V3_CONFIDENCE_HIGH hint
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_HIGH" in hint_codes, \
            "Should have V3_CONFIDENCE_HIGH hint for high quality"

    def test_therapy_medium_quality_gets_medium_confidence_hint(self):
        """Test that therapy with medium quality gets V3_CONFIDENCE_MEDIUM hint."""
        unified = {
            "text": "Let's explore your feelings...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.55,  # Medium quality
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "therapy"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "therapy")

        # Check for V3_CONFIDENCE_MEDIUM hint
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_MEDIUM" in hint_codes, \
            "Should have V3_CONFIDENCE_MEDIUM hint for medium quality"

    def test_therapy_low_quality_gets_low_confidence_hint(self):
        """Test that therapy with low quality gets V3_CONFIDENCE_LOW hint."""
        unified = {
            "text": "Let's explore your feelings...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.25,  # Low quality
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "therapy"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "therapy")

        # Check for V3_CONFIDENCE_LOW hint
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_LOW" in hint_codes, \
            "Should have V3_CONFIDENCE_LOW hint for low quality"

    def test_identity_domain_gets_v3_confidence_hints(self):
        """Test that identity domain also gets v3 confidence hints."""
        unified = {
            "text": "Tell me about your identity...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.80,  # High quality
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "identity"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "identity")

        # Check for V3_CONFIDENCE_HIGH hint
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_HIGH" in hint_codes, \
            "Identity domain should also get v3 confidence hints"

    def test_trading_domain_no_v3_hints(self):
        """Test that trading domain never gets v3 confidence hints."""
        unified = {
            "text": "Market analysis...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # Very high quality (doesn't matter)
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "trading"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "trading")

        # Check that NO v3 confidence hints are present
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_HIGH" not in hint_codes, \
            "Trading should not have v3 confidence hints"
        assert "V3_CONFIDENCE_MEDIUM" not in hint_codes
        assert "V3_CONFIDENCE_LOW" not in hint_codes

    def test_generic_domain_no_v3_hints(self):
        """Test that generic domain never gets v3 confidence hints."""
        unified = {
            "text": "General response...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # Very high quality (doesn't matter)
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "generic"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "generic")

        # Check that NO v3 confidence hints are present
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_HIGH" not in hint_codes, \
            "Generic should not have v3 confidence hints"
        assert "V3_CONFIDENCE_MEDIUM" not in hint_codes
        assert "V3_CONFIDENCE_LOW" not in hint_codes

    def test_missing_v3_quality_no_hints(self):
        """Test that missing v3 quality does not produce hints."""
        unified = {
            "text": "Let's explore...",
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": None,  # Missing
                "persona_drift_score": 0.3,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
            "metadata": {"domain": "therapy"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable", "needs_grounding": False}
        response = build_dilchat_response(unified, policy_flags, "therapy")

        # Check that NO v3 confidence hints are present
        hint_codes = [h.code for h in response.hints]
        assert "V3_CONFIDENCE_HIGH" not in hint_codes
        assert "V3_CONFIDENCE_MEDIUM" not in hint_codes
        assert "V3_CONFIDENCE_LOW" not in hint_codes


class TestPhase12Invariants:
    """Test that Phase 12 does not break existing behavior."""

    def test_trading_behavior_unchanged(self):
        """Test that trading behavior is identical to pre-Phase-12."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # High quality (irrelevant for trading)
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("trading")
        flags = compute_policy_flags(unified, "trading")

        # Trading should use v1 only (not v2 or v3)
        active_coherence = _get_active_coherence_score(unified, profile)
        assert active_coherence == 0.6, "Trading should use v1 (unchanged behavior)"

        # Policy flags should be based on v1
        assert not flags["needs_grounding"], "Should not need grounding (v1 coherence is 0.6 >= 0.55)"

    def test_generic_behavior_unchanged(self):
        """Test that generic behavior is identical to pre-Phase-12."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.7,
                "coherence_score_v3": 0.82,
                "coherence_v3_quality": 0.95,  # High quality (irrelevant for generic)
                "persona_drift_score": 0.3,
                "mapper_volatility_score": 0.2,
                "temporal_arc_score": 0.7,
            },
            "entropy": {"normalized_entropy": 0.4},
        }

        profile = get_domain_profile("generic")
        flags = compute_policy_flags(unified, "generic")

        # Generic should use v1 only (not v2 or v3)
        active_coherence = _get_active_coherence_score(unified, profile)
        assert active_coherence == 0.5, "Generic should use v1 (unchanged behavior)"

        # Policy flags should be based on v1
        assert not flags["needs_grounding"], "Should not need grounding (v1 coherence is 0.5 >= 0.40)"


class TestPhase12DomainProfiles:
    """Test domain profile quality thresholds."""

    def test_therapy_has_quality_threshold(self):
        """Test that therapy has min_v3_quality_for_activation."""
        profile = get_domain_profile("therapy")
        assert profile["min_v3_quality_for_activation"] == 0.40, \
            "Therapy should have quality threshold of 0.40"

    def test_identity_has_quality_threshold(self):
        """Test that identity has min_v3_quality_for_activation."""
        profile = get_domain_profile("identity")
        assert profile["min_v3_quality_for_activation"] == 0.45, \
            "Identity should have quality threshold of 0.45"

    def test_trading_has_no_quality_threshold(self):
        """Test that trading has no quality threshold (v3 disabled)."""
        profile = get_domain_profile("trading")
        assert profile["min_v3_quality_for_activation"] is None, \
            "Trading should have no quality threshold (v3 disabled)"

    def test_generic_has_no_quality_threshold(self):
        """Test that generic has no quality threshold (v3 disabled)."""
        profile = get_domain_profile("generic")
        assert profile["min_v3_quality_for_activation"] is None, \
            "Generic should have no quality threshold (v3 disabled)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
