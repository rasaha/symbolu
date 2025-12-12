"""
Phase 4 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 4 - Coherence v2 Integration.
Total: ~22 tests

Phase Type: Coherence scoring foundation
Routing/Mapper Invariance: SKIP (coherence layer, pre-routing)
"""

import pytest
import inspect

from symbolu.policy.policy_engine import _get_active_coherence_score
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: Formula Determinism (5 tests)
# ============================================================================

class TestPhase4FormulaDeterminism:
    """Verify Phase 4 coherence v2 is deterministic."""

    def test_v2_score_selection_deterministic(self):
        """Test v2 score selection is deterministic."""
        unified = {
            "coherence": {
                "coherence_score": 0.6,
                "coherence_score_v2": 0.75,
            }
        }
        profile = get_domain_profile("therapy")
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert len(set(results)) == 1

    def test_v1_fallback_deterministic(self):
        """Test v1 fallback is deterministic."""
        unified = {"coherence": {"coherence_score": 0.6}}
        profile = get_domain_profile("trading")
        results = [_get_active_coherence_score(unified, profile) for _ in range(10)]
        assert len(set(results)) == 1

    def test_domain_profile_deterministic(self):
        """Test domain profile retrieval is deterministic."""
        results = [get_domain_profile("therapy") for _ in range(10)]
        assert all(r["min_coherence"] == results[0]["min_coherence"] for r in results)

    def test_cascade_logic_deterministic(self):
        """Test v3 > v2 > v1 cascade is deterministic."""
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

    def test_no_randomness_in_profiles(self):
        """Test no randomness in domain profiles."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase4ZeroLLMGuarantee:
    """Verify Phase 4 makes NO LLM calls."""

    def test_no_anthropic_imports_policy(self):
        """Test no Anthropic imports in policy_engine."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports_policy(self):
        """Test no OpenAI imports in policy_engine."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls_profiles(self):
        """Test no network calls in domain_profiles."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test coherence selection runs offline."""
        unified = {"coherence": {"coherence_score": 0.5}}
        profile = get_domain_profile("generic")
        result = _get_active_coherence_score(unified, profile)
        assert result is not None


# ============================================================================
# Test Class 3: Graceful Degradation (5 tests)
# ============================================================================

class TestPhase4GracefulDegradation:
    """Verify Phase 4 handles edge cases gracefully."""

    def test_missing_v2_falls_back_to_v1(self):
        """Test missing v2 falls back to v1."""
        unified = {"coherence": {"coherence_score": 0.6}}
        profile = {"use_coherence_v2": True, "use_coherence_v3": False}
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6

    def test_missing_coherence_block(self):
        """Test missing coherence block returns default."""
        unified = {}
        profile = get_domain_profile("generic")
        result = _get_active_coherence_score(unified, profile)
        assert result == 1.0  # Default

    def test_unknown_domain_uses_generic(self):
        """Test unknown domain uses generic profile."""
        profile = get_domain_profile("unknown_domain_xyz")
        assert profile["style"] == "neutral"  # Generic profile

    def test_empty_unified_dict(self):
        """Test empty unified dict is handled."""
        unified = {"coherence": {}}
        profile = get_domain_profile("generic")
        result = _get_active_coherence_score(unified, profile)
        assert isinstance(result, float)

    def test_v3_quality_below_threshold(self):
        """Test v3 quality below threshold falls back."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v2": 0.6,
                "coherence_score_v3": 0.8,
                "coherence_v3_quality": 0.1,  # Below threshold
            }
        }
        profile = {"use_coherence_v2": True, "use_coherence_v3": True, "min_v3_quality_for_activation": 0.4}
        result = _get_active_coherence_score(unified, profile)
        assert result == 0.6  # Falls back to v2


# ============================================================================
# Test Class 4: Range Bounds (4 tests)
# ============================================================================

class TestPhase4RangeBounds:
    """Verify Phase 4 outputs are within expected ranges."""

    def test_active_score_bounded(self):
        """Test active coherence score is bounded."""
        unified = {"coherence": {"coherence_score": 0.5}}
        profile = get_domain_profile("generic")
        result = _get_active_coherence_score(unified, profile)
        assert 0.0 <= result <= 1.0

    def test_domain_thresholds_valid(self):
        """Test domain thresholds are in valid ranges."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert 0.0 <= profile["min_coherence"] <= 1.0
            assert 0.0 <= profile["max_persona_drift"] <= 1.0

    def test_v2_selection_bounded(self):
        """Test v2 selection returns bounded value."""
        unified = {"coherence": {"coherence_score": 0.5, "coherence_score_v2": 0.75}}
        profile = {"use_coherence_v2": True, "use_coherence_v3": False}
        result = _get_active_coherence_score(unified, profile)
        assert 0.0 <= result <= 1.0

    def test_v3_selection_bounded(self):
        """Test v3 selection returns bounded value."""
        unified = {
            "coherence": {
                "coherence_score": 0.5,
                "coherence_score_v3": 0.85,
                "coherence_v3_quality": 0.9,
            }
        }
        profile = {"use_coherence_v3": True, "min_v3_quality_for_activation": 0.4}
        result = _get_active_coherence_score(unified, profile)
        assert 0.0 <= result <= 1.0


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase4BackwardCompatibility:
    """Verify Phase 4 maintains backward compatibility."""

    def test_domain_profiles_have_required_keys(self):
        """Test domain profiles have all required keys."""
        required = ["min_coherence", "max_persona_drift", "prefer_mappers", "style"]
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            for key in required:
                assert key in profile, f"Missing {key} in {domain}"

    def test_v2_flag_exists_in_profiles(self):
        """Test use_coherence_v2 flag exists in profiles."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "use_coherence_v2" in profile

    def test_v3_flag_exists_in_profiles(self):
        """Test use_coherence_v3 flag exists in profiles."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "use_coherence_v3" in profile

    def test_get_domain_profile_callable(self):
        """Test get_domain_profile is callable."""
        assert callable(get_domain_profile)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
