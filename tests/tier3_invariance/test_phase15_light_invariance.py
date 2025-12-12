"""
Phase 15 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 15 - Interaction Modes.
Total: ~22 tests

Phase Type: Policy configuration
Routing/Mapper Invariance: SKIP (policy layer, mode selection)
"""

import pytest
import inspect

from symbolu.policy.interaction_modes import (
    InteractionMode,
    resolve_interaction_mode,
    is_mode_valid,
)
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: Mode Resolution Determinism (5 tests)
# ============================================================================

class TestPhase15ModeDeterminism:
    """Verify Phase 15 mode resolution is deterministic."""

    def test_mode_resolution_deterministic(self):
        """Test mode resolution is deterministic."""
        profile = get_domain_profile("therapy")
        results = [resolve_interaction_mode(profile, None, None) for _ in range(10)]
        assert len(set(r.value for r in results)) == 1

    def test_admin_override_deterministic(self):
        """Test admin override is deterministic."""
        profile = get_domain_profile("therapy")
        results = [resolve_interaction_mode(profile, None, "analytics_only") for _ in range(10)]
        assert all(r == InteractionMode.ANALYTICS_ONLY for r in results)

    def test_user_override_deterministic(self):
        """Test user override is deterministic."""
        profile = get_domain_profile("therapy")
        results = [resolve_interaction_mode(profile, "deep_adaptive", None) for _ in range(10)]
        assert all(r == InteractionMode.DEEP_ADAPTIVE for r in results)

    def test_mode_validation_deterministic(self):
        """Test mode validation is deterministic."""
        results = [is_mode_valid("smart_insight") for _ in range(10)]
        assert all(r is True for r in results)

    def test_no_randomness_in_modes(self):
        """Test no randomness in interaction modes module."""
        import symbolu.policy.interaction_modes as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase15ZeroLLMGuarantee:
    """Verify Phase 15 makes NO LLM calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in interaction modes."""
        import symbolu.policy.interaction_modes as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in interaction modes."""
        import symbolu.policy.interaction_modes as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls(self):
        """Test no network calls in interaction modes."""
        import symbolu.policy.interaction_modes as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test mode resolution runs offline."""
        profile = get_domain_profile("generic")
        result = resolve_interaction_mode(profile, None, None)
        assert result is not None


# ============================================================================
# Test Class 3: Mode Priority (5 tests)
# ============================================================================

class TestPhase15ModePriority:
    """Verify Phase 15 mode priority cascade."""

    def test_admin_override_highest_priority(self):
        """Test admin override takes highest priority."""
        profile = get_domain_profile("therapy")  # Default: smart_insight
        result = resolve_interaction_mode(profile, "deep_adaptive", "analytics_only")
        assert result == InteractionMode.ANALYTICS_ONLY  # Admin wins

    def test_user_override_second_priority(self):
        """Test user override takes second priority."""
        profile = get_domain_profile("therapy")  # Default: smart_insight
        result = resolve_interaction_mode(profile, "deep_adaptive", None)
        assert result == InteractionMode.DEEP_ADAPTIVE  # User wins over default

    def test_domain_default_fallback(self):
        """Test domain default is used when no overrides."""
        profile = get_domain_profile("therapy")
        result = resolve_interaction_mode(profile, None, None)
        assert result == InteractionMode.SMART_INSIGHT  # Therapy default

    def test_invalid_admin_override_ignored(self):
        """Test invalid admin override is ignored."""
        profile = get_domain_profile("therapy")
        result = resolve_interaction_mode(profile, None, "invalid_mode_xyz")
        assert result == InteractionMode.SMART_INSIGHT  # Falls to default

    def test_invalid_user_override_ignored(self):
        """Test invalid user override is ignored."""
        profile = get_domain_profile("therapy")
        result = resolve_interaction_mode(profile, "invalid_mode_xyz", None)
        assert result == InteractionMode.SMART_INSIGHT  # Falls to default


# ============================================================================
# Test Class 4: Graceful Degradation (4 tests)
# ============================================================================

class TestPhase15GracefulDegradation:
    """Verify Phase 15 handles edge cases gracefully."""

    def test_none_overrides_use_default(self):
        """Test None overrides use domain default."""
        profile = get_domain_profile("trading")
        result = resolve_interaction_mode(profile, None, None)
        assert result == InteractionMode.ANALYTICS_ONLY

    def test_empty_string_ignored(self):
        """Test empty string overrides are ignored."""
        profile = get_domain_profile("therapy")
        result = resolve_interaction_mode(profile, "", "")
        assert result == InteractionMode.SMART_INSIGHT  # Default

    def test_mode_validation_various_formats(self):
        """Test mode validation works with various formats."""
        # Valid modes should return True
        assert is_mode_valid("smart_insight") is True
        assert is_mode_valid("analytics_only") is True
        assert is_mode_valid("deep_adaptive") is True

    def test_validate_unknown_returns_false(self):
        """Test validating unknown mode returns False."""
        result = is_mode_valid("unknown_mode_xyz")
        assert result is False


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase15BackwardCompatibility:
    """Verify Phase 15 maintains backward compatibility."""

    def test_all_modes_exist(self):
        """Test all expected modes exist."""
        assert hasattr(InteractionMode, 'ANALYTICS_ONLY')
        assert hasattr(InteractionMode, 'SMART_INSIGHT')
        assert hasattr(InteractionMode, 'DEEP_ADAPTIVE')

    def test_mode_values_stable(self):
        """Test mode values are stable."""
        assert InteractionMode.ANALYTICS_ONLY.value == "analytics_only"
        assert InteractionMode.SMART_INSIGHT.value == "smart_insight"
        assert InteractionMode.DEEP_ADAPTIVE.value == "deep_adaptive"

    def test_profiles_have_mode_default(self):
        """Test all profiles have interaction_mode_default."""
        for domain in ["trading", "therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "interaction_mode_default" in profile

    def test_resolve_function_signature(self):
        """Test resolve_interaction_mode signature."""
        sig = inspect.signature(resolve_interaction_mode)
        params = list(sig.parameters.keys())
        assert "domain_profile" in params
        assert "user_override" in params
        assert "admin_override" in params


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
