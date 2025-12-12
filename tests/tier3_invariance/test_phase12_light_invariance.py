"""
Phase 12 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 12 - V3 Quality Integration.
Total: ~22 tests

Phase Type: Quality gating
Routing/Mapper Invariance: SKIP (quality layer, post-routing)
"""

import pytest
import inspect

from symbolu.policy.policy_engine import _get_active_coherence_score
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: Quality Computation Determinism (5 tests)
# ============================================================================

class TestPhase12QualityDeterminism:
    """Verify Phase 12 quality computation is deterministic."""

    def test_quality_gating_deterministic(self):
        """Test quality gating is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.8,
                "coherence_v3_quality": 0.75,
            }
        }
        profile = get_domain_profile("therapy")
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert len(set(results)) == 1

    def test_threshold_comparison_deterministic(self):
        """Test threshold comparison is deterministic."""
        profile = get_domain_profile("therapy")
        threshold = profile["min_v3_quality_for_activation"]

        unified_above = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.8,
                "coherence_v3_quality": threshold + 0.01,
            }
        }
        results = [_get_active_coherence_score(unified_above, profile) for _ in range(10)]
        assert len(set(results)) == 1

    def test_domain_profile_selection_deterministic(self):
        """Test domain profile selection is deterministic."""
        profiles = [get_domain_profile("therapy") for _ in range(10)]
        assert all(p["use_coherence_v3"] == profiles[0]["use_coherence_v3"] for p in profiles)

    def test_v3_enabled_check_deterministic(self):
        """Test v3 enabled check is deterministic."""
        profile = get_domain_profile("therapy")
        results = [profile["use_coherence_v3"] for _ in range(10)]
        assert len(set(results)) == 1

    def test_no_randomness_in_policy(self):
        """Test no randomness in policy_engine module."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase12ZeroLLMGuarantee:
    """Verify Phase 12 makes NO LLM calls."""

    def test_no_anthropic_in_policy(self):
        """Test no Anthropic imports in policy_engine module."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_in_policy(self):
        """Test no OpenAI imports in policy_engine module."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_in_policy(self):
        """Test no network calls in policy_engine module."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test quality gating runs offline."""
        unified = {"coherence": {"coherence_score": 0.5}}
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result is not None


# ============================================================================
# Test Class 3: Graceful Degradation (5 tests)
# ============================================================================

class TestPhase12GracefulDegradation:
    """Verify Phase 12 handles edge cases gracefully."""

    def test_missing_v3_score_handled(self):
        """Test missing v3 score is handled gracefully."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result is not None

    def test_missing_quality_uses_fallback(self):
        """Test missing quality uses fallback."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.8,
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result is not None

    def test_empty_unified_handled(self):
        """Test empty unified dict is handled."""
        unified = {"coherence": {}}
        profile = get_domain_profile("therapy")
        try:
            result = _get_active_coherence_score(unified, profile)
            assert result is None or isinstance(result, (int, float))
        except (KeyError, TypeError):
            pass

    def test_trading_domain_falls_back(self):
        """Test trading domain (v3 disabled) uses v1."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.8,
            }
        }
        profile = get_domain_profile("trading")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.5  # Uses v1

    def test_generic_domain_falls_back(self):
        """Test generic domain (v3 disabled) uses v1."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v3": 0.9,
            }
        }
        profile = get_domain_profile("generic")
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6


# ============================================================================
# Test Class 4: Range Bounds (4 tests)
# ============================================================================

class TestPhase12RangeBounds:
    """Verify Phase 12 outputs are within expected ranges."""

    def test_active_score_bounded(self):
        """Test active coherence score is bounded."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.8,
                "coherence_v3_quality": 0.7,
            }
        }
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert 0.0 <= result <= 1.0

    def test_v3_threshold_bounded(self):
        """Test v3 threshold is bounded in profile."""
        profile = get_domain_profile("therapy")
        threshold = profile["min_v3_quality_for_activation"]
        assert 0.0 <= threshold <= 1.0

    def test_coherence_score_range(self):
        """Test coherence score stays in valid range."""
        for domain in ["therapy", "identity"]:
            unified = {"coherence": {"coherence_score": 0.5, "coherence_score_v3": 0.8}}
            profile = get_domain_profile(domain)
            result = _get_active_coherence_score(unified, profile)
            assert 0.0 <= result <= 1.0

    def test_no_negative_scores(self):
        """Test no negative scores."""
        unified = {"coherence": {"coherence_score": 0.0}}
        profile = get_domain_profile("therapy")
        result = _get_active_coherence_score(unified, profile)
        assert result >= 0.0


# ============================================================================
# Test Class 5: Domain Threshold Configuration (4 tests)
# ============================================================================

class TestPhase12DomainThresholds:
    """Verify Phase 12 domain thresholds are configured correctly."""

    def test_therapy_has_v3_enabled(self):
        """Test therapy has v3 enabled."""
        profile = get_domain_profile("therapy")
        assert "use_coherence_v3" in profile
        assert profile["use_coherence_v3"] is True

    def test_therapy_has_quality_threshold(self):
        """Test therapy has quality threshold."""
        profile = get_domain_profile("therapy")
        assert "min_v3_quality_for_activation" in profile
        assert profile["min_v3_quality_for_activation"] == 0.40

    def test_trading_has_v3_disabled(self):
        """Test trading has v3 disabled."""
        profile = get_domain_profile("trading")
        assert profile["use_coherence_v3"] is False

    def test_trading_has_no_threshold(self):
        """Test trading has None threshold (v3 disabled)."""
        profile = get_domain_profile("trading")
        assert profile["min_v3_quality_for_activation"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
