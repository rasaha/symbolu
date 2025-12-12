"""
Phase 11 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 11 - Coherence v3 Activation.
Total: ~22 tests

Phase Type: Policy layer activation
Routing/Mapper Invariance: LIGHT (v3 may inform policy, not routing)
"""

import pytest
import inspect

from symbolu.policy.policy_engine import _get_active_coherence_score, compute_policy_flags
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: v3 Activation Determinism (5 tests)
# ============================================================================

class TestPhase11ActivationDeterminism:
    """Verify Phase 11 v3 activation is deterministic."""

    def test_v3_selection_deterministic(self):
        """Test v3 score selection is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.7,
                "coherence_v3_quality": 0.8,
            }
        }
        profile = get_domain_profile("therapy")
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert len(set(results)) == 1
        assert results[0] == 0.7  # Should select v3

    def test_v3_cascade_deterministic(self):
        """Test v3 > v2 > v1 cascade is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.7,
                "coherence_v3_quality": 0.9,
            }
        }
        profile = {"use_coherence_v3": True, "use_coherence_v2": True, "min_v3_quality_for_activation": 0.4}
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert all(r == 0.7 for r in results)

    def test_domain_activation_deterministic(self):
        """Test domain-based v3 activation is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.7,
                "coherence_v3_quality": 0.8,
            }
        }
        # Therapy should use v3
        profile_therapy = get_domain_profile("therapy")
        results_therapy = [_get_active_coherence_score(unified, profile_therapy) for _ in range(5)]
        assert len(set(results_therapy)) == 1

        # Trading should use v1
        profile_trading = get_domain_profile("trading")
        results_trading = [_get_active_coherence_score(unified, profile_trading) for _ in range(5)]
        assert len(set(results_trading)) == 1

    def test_quality_threshold_deterministic(self):
        """Test quality threshold check is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.7,
                "coherence_v3_quality": 0.3,  # Below therapy threshold of 0.4
            }
        }
        profile = get_domain_profile("therapy")
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert len(set(results)) == 1
        assert results[0] == 0.6  # Should fall back to v2

    def test_no_randomness_in_activation(self):
        """Test no randomness in v3 activation logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._get_active_coherence_score)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase11ZeroLLMGuarantee:
    """Verify Phase 11 makes NO LLM calls."""

    def test_no_anthropic_in_v3_logic(self):
        """Test no Anthropic imports in v3 activation logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._get_active_coherence_score)
        assert 'anthropic' not in source.lower()

    def test_no_openai_in_v3_logic(self):
        """Test no OpenAI imports in v3 activation logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._get_active_coherence_score)
        assert 'openai' not in source.lower()

    def test_no_network_in_v3_logic(self):
        """Test no network calls in v3 activation logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._get_active_coherence_score)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test v3 activation runs completely offline."""
        unified = {"coherence": {"coherence_score": 0.5}}
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result is not None


# ============================================================================
# Test Class 3: Domain Activation (5 tests)
# ============================================================================

class TestPhase11DomainActivation:
    """Verify Phase 11 domain-specific activation."""

    def test_therapy_domain_v3_enabled(self):
        """Test therapy domain has v3 enabled."""
        profile = get_domain_profile("therapy")
        assert profile["use_coherence_v3"] is True

    def test_identity_domain_v3_enabled(self):
        """Test identity domain has v3 enabled."""
        profile = get_domain_profile("identity")
        assert profile["use_coherence_v3"] is True

    def test_trading_domain_v3_disabled(self):
        """Test trading domain has v3 disabled."""
        profile = get_domain_profile("trading")
        assert profile["use_coherence_v3"] is False

    def test_generic_domain_v3_disabled(self):
        """Test generic domain has v3 disabled."""
        profile = get_domain_profile("generic")
        assert profile["use_coherence_v3"] is False

    def test_v3_uses_correct_score(self):
        """Test v3 activation uses the correct v3 score."""
        unified = {
            "coherence": {
                "coherence_score": 0.3,
                "coherence_score_v2": 0.5,
                "coherence_score_v3": 0.9,
                "coherence_v3_quality": 0.95,
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.9


# ============================================================================
# Test Class 4: Graceful Degradation (4 tests)
# ============================================================================

class TestPhase11GracefulDegradation:
    """Verify Phase 11 handles edge cases gracefully."""

    def test_missing_v3_score_falls_back(self):
        """Test missing v3 score falls back to v2."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                # No v3 score
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6

    def test_missing_v3_quality_prevents_v3(self):
        """Test missing v3 quality prevents v3 usage."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.9,
                # No quality score
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6  # Falls back to v2

    def test_v3_quality_below_threshold_falls_back(self):
        """Test v3 quality below threshold falls back."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.9,
                "coherence_v3_quality": 0.1,  # Way below threshold
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6  # Falls back to v2

    def test_empty_coherence_block(self):
        """Test empty coherence block returns default."""
        unified = {"coherence": {}}
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result == 1.0  # Default


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase11BackwardCompatibility:
    """Verify Phase 11 maintains backward compatibility."""

    def test_v1_behavior_preserved(self):
        """Test v1-only behavior is preserved for v3-disabled domains."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.9,
                "coherence_v3_quality": 0.95,
            }
        }
        profile = get_domain_profile("trading")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.5  # Uses v1, ignores v2 and v3

    def test_v2_behavior_preserved(self):
        """Test v2 behavior preserved when v3 unavailable."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                # No v3
            }
        }
        profile = {"use_coherence_v2": True, "use_coherence_v3": True}
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6

    def test_profiles_have_v3_settings(self):
        """Test all profiles have v3 settings."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "use_coherence_v3" in profile
            assert "min_v3_quality_for_activation" in profile

    def test_policy_flags_includes_v3(self):
        """Test compute_policy_flags works with v3."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.7,
                "coherence_v3_quality": 0.8,
            }
        }
        flags = compute_policy_flags(unified, "therapy")
        assert "needs_grounding" in flags


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
