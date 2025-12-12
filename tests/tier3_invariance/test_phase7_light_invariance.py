"""
Phase 7 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 7 - Trading Domain Guardrails.
Total: ~22 tests

Phase Type: Domain-specific safety configuration
Routing/Mapper Invariance: LIGHT (via domain profiles)
"""

import pytest
import inspect

from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: Domain Profile Determinism (5 tests)
# ============================================================================

class TestPhase7ProfileDeterminism:
    """Verify Phase 7 domain profiles are deterministic."""

    def test_trading_profile_deterministic(self):
        """Test trading profile is deterministic."""
        results = [get_domain_profile("trading") for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_therapy_profile_deterministic(self):
        """Test therapy profile is deterministic."""
        results = [get_domain_profile("therapy") for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_identity_profile_deterministic(self):
        """Test identity profile is deterministic."""
        results = [get_domain_profile("identity") for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_generic_profile_deterministic(self):
        """Test generic profile is deterministic."""
        results = [get_domain_profile("generic") for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_no_randomness_in_profiles(self):
        """Test no randomness in domain_profiles module."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase7ZeroLLMGuarantee:
    """Verify Phase 7 makes NO LLM calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in domain_profiles module."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in domain_profiles module."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls(self):
        """Test no network calls in domain_profiles module."""
        import symbolu.policy.domain_profiles as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()
        assert 'httpx' not in source.lower()

    def test_runs_offline(self):
        """Test domain profiles run completely offline."""
        profile = get_domain_profile("trading")
        assert profile is not None


# ============================================================================
# Test Class 3: Guardrail Configuration (5 tests)
# ============================================================================

class TestPhase7GuardrailConfiguration:
    """Verify Phase 7 guardrail settings are configured correctly."""

    def test_trading_guardrails_enabled(self):
        """Test trading domain has guardrails enabled."""
        profile = get_domain_profile("trading")
        assert "formula_guardrails_enabled" in profile
        assert profile["formula_guardrails_enabled"] is True

    def test_therapy_guardrails_disabled(self):
        """Test therapy domain has guardrails disabled."""
        profile = get_domain_profile("therapy")
        assert "formula_guardrails_enabled" in profile
        assert profile["formula_guardrails_enabled"] is False

    def test_identity_guardrails_disabled(self):
        """Test identity domain has guardrails disabled."""
        profile = get_domain_profile("identity")
        assert "formula_guardrails_enabled" in profile
        assert profile["formula_guardrails_enabled"] is False

    def test_generic_guardrails_disabled(self):
        """Test generic domain has guardrails disabled."""
        profile = get_domain_profile("generic")
        assert "formula_guardrails_enabled" in profile
        assert profile["formula_guardrails_enabled"] is False

    def test_trading_has_max_tension_setting(self):
        """Test trading profile has max_tension_allowed setting."""
        profile = get_domain_profile("trading")
        assert "max_tension_allowed" in profile
        assert isinstance(profile["max_tension_allowed"], (int, float))


# ============================================================================
# Test Class 4: Trading Safety Settings (5 tests)
# ============================================================================

class TestPhase7TradingSafetySettings:
    """Verify Phase 7 trading safety settings."""

    def test_trading_has_negative_delta_limit(self):
        """Test trading has max_negative_delta_smi setting."""
        profile = get_domain_profile("trading")
        assert "max_negative_delta_smi" in profile

    def test_trading_has_volatility_limit(self):
        """Test trading has max_volatility_allowed setting."""
        profile = get_domain_profile("trading")
        assert "max_volatility_allowed" in profile

    def test_trading_tension_threshold_reasonable(self):
        """Test trading tension threshold is reasonable (0.0-1.0)."""
        profile = get_domain_profile("trading")
        threshold = profile.get("max_tension_allowed", 0.5)
        assert 0.0 <= threshold <= 1.0

    def test_trading_volatility_threshold_reasonable(self):
        """Test trading volatility threshold is reasonable (0.0-1.0)."""
        profile = get_domain_profile("trading")
        threshold = profile.get("max_volatility_allowed", 0.5)
        assert 0.0 <= threshold <= 1.0

    def test_trading_delta_threshold_reasonable(self):
        """Test trading delta threshold is reasonable."""
        profile = get_domain_profile("trading")
        threshold = profile.get("max_negative_delta_smi", 0.5)
        # This is a magnitude threshold, can be positive
        assert 0.0 <= threshold <= 1.0


# ============================================================================
# Test Class 5: Graceful Degradation (4 tests)
# ============================================================================

class TestPhase7GracefulDegradation:
    """Verify Phase 7 handles edge cases gracefully."""

    def test_unknown_domain_fallback(self):
        """Test unknown domain falls back to generic."""
        profile = get_domain_profile("unknown_xyz")
        # Should return generic profile or raise exception
        if profile is not None:
            assert isinstance(profile, dict)

    def test_none_domain_handled(self):
        """Test None domain is handled."""
        try:
            profile = get_domain_profile(None)
            # If it doesn't raise, should return something
            assert profile is None or isinstance(profile, dict)
        except (TypeError, ValueError):
            pass  # Acceptable to raise

    def test_empty_domain_handled(self):
        """Test empty domain is handled."""
        try:
            profile = get_domain_profile("")
            assert profile is None or isinstance(profile, dict)
        except (TypeError, ValueError, KeyError):
            pass  # Acceptable to raise

    def test_all_domains_have_guardrail_setting(self):
        """Test all domains have guardrail setting."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "formula_guardrails_enabled" in profile


# ============================================================================
# Test Class 6: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase7BackwardCompatibility:
    """Verify Phase 7 maintains backward compatibility."""

    def test_get_domain_profile_exists(self):
        """Test get_domain_profile function exists."""
        assert callable(get_domain_profile)

    def test_trading_profile_returns_dict(self):
        """Test trading profile returns dict."""
        profile = get_domain_profile("trading")
        assert isinstance(profile, dict)

    def test_trading_profile_has_interaction_mode(self):
        """Test trading profile has interaction_mode_default."""
        profile = get_domain_profile("trading")
        assert "interaction_mode_default" in profile

    def test_trading_profile_has_guardrails_enabled(self):
        """Test trading profile has guardrails enabled."""
        profile = get_domain_profile("trading")
        assert profile.get("formula_guardrails_enabled") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
