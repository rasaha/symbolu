"""
Phase 5 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 5 - Formula UI Behavior.
Total: ~22 tests

Phase Type: UI/Display layer
Routing/Mapper Invariance: SKIP (display layer, post-routing)
"""

import pytest
import inspect

from symbolu.policy.policy_engine import _refine_policy_with_formulas
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# Test Class 1: Refinement Determinism (5 tests)
# ============================================================================

class TestPhase5RefinementDeterminism:
    """Verify Phase 5 policy refinements are deterministic."""

    def test_refinement_deterministic(self):
        """Test policy refinement is deterministic."""
        flags = {"allow_deep_reflection": False, "prefer_arc_mode": False}
        unified = {
            "coherence": {
                "coherence_score_v2": 0.7,
                "resonance_index": 0.75,
                "tension_index": 0.3,
                "arc_alignment_index": 0.65,
            }
        }
        profile = get_domain_profile("therapy")
        results = [_refine_policy_with_formulas(flags.copy(), unified, profile) for _ in range(10)]
        assert all(r["allow_deep_reflection"] == results[0]["allow_deep_reflection"] for r in results)

    def test_no_refinement_when_disabled(self):
        """Test no refinement when formula_ui_mode is 'none'."""
        flags = {"allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9}}
        profile = {"formula_ui_mode": "none"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert result["allow_deep_reflection"] is False

    def test_refinement_enabled_for_therapy(self):
        """Test refinement enabled for therapy domain."""
        profile = get_domain_profile("therapy")
        assert profile["formula_ui_mode"] == "light"

    def test_refinement_disabled_for_trading(self):
        """Test refinement disabled for trading domain."""
        profile = get_domain_profile("trading")
        assert profile["formula_ui_mode"] == "none"

    def test_no_randomness_in_refinement(self):
        """Test no randomness in refinement logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._refine_policy_with_formulas)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase5ZeroLLMGuarantee:
    """Verify Phase 5 makes NO LLM calls."""

    def test_no_anthropic_in_refinement(self):
        """Test no Anthropic imports in refinement logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._refine_policy_with_formulas)
        assert 'anthropic' not in source.lower()

    def test_no_openai_in_refinement(self):
        """Test no OpenAI imports in refinement logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._refine_policy_with_formulas)
        assert 'openai' not in source.lower()

    def test_no_network_in_refinement(self):
        """Test no network calls in refinement logic."""
        import symbolu.policy.policy_engine as module
        source = inspect.getsource(module._refine_policy_with_formulas)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test refinement runs offline."""
        flags = {"allow_deep_reflection": False}
        unified = {"coherence": {}}
        profile = {"formula_ui_mode": "none"}
        result = _refine_policy_with_formulas(flags, unified, profile)
        assert result is not None


# ============================================================================
# Test Class 3: Graceful Degradation (5 tests)
# ============================================================================

class TestPhase5GracefulDegradation:
    """Verify Phase 5 handles edge cases gracefully."""

    def test_missing_metrics_no_change(self):
        """Test missing metrics causes no change."""
        flags = {"allow_deep_reflection": False, "prefer_arc_mode": False}
        unified = {"coherence": {}}  # No metrics
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert result["allow_deep_reflection"] is False

    def test_partial_metrics_handled(self):
        """Test partial metrics are handled gracefully."""
        flags = {"allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.8}}  # Only resonance
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert isinstance(result, dict)

    def test_empty_flags_dict(self):
        """Test empty flags dict is handled."""
        flags = {}
        unified = {"coherence": {}}
        profile = {"formula_ui_mode": "none"}
        result = _refine_policy_with_formulas(flags, unified, profile)
        assert isinstance(result, dict)

    def test_missing_coherence_block(self):
        """Test missing coherence block is handled."""
        flags = {"allow_deep_reflection": False}
        unified = {}  # No coherence block
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert isinstance(result, dict)

    def test_none_formula_ui_mode(self):
        """Test None formula_ui_mode is handled as 'none'."""
        flags = {"allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9}}
        profile = {}  # Missing formula_ui_mode
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        # Should treat missing as 'none' and return unchanged
        assert result["allow_deep_reflection"] is False


# ============================================================================
# Test Class 4: Safety Invariance (4 tests)
# ============================================================================

class TestPhase5SafetyInvariance:
    """Verify Phase 5 never modifies safety flags."""

    def test_needs_grounding_never_modified(self):
        """Test needs_grounding is never modified by refinement."""
        flags = {"needs_grounding": True, "allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9, "tension_index": 0.1, "arc_alignment_index": 0.9}}
        profile = get_domain_profile("therapy")
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        # needs_grounding should be unchanged
        assert result.get("needs_grounding") == flags.get("needs_grounding")

    def test_coherence_warning_never_modified(self):
        """Test coherence_warning is never modified."""
        flags = {"coherence_warning": True, "allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9}}
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert result.get("coherence_warning") == flags.get("coherence_warning")

    def test_stability_status_never_modified(self):
        """Test stability_status is never modified."""
        flags = {"stability_status": "fragmented", "allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9}}
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert result.get("stability_status") == flags.get("stability_status")

    def test_recommended_mapper_never_modified(self):
        """Test recommended_mapper is never modified."""
        flags = {"recommended_mapper": "LCM", "allow_deep_reflection": False}
        unified = {"coherence": {"resonance_index": 0.9}}
        profile = {"formula_ui_mode": "light"}
        result = _refine_policy_with_formulas(flags.copy(), unified, profile)
        assert result.get("recommended_mapper") == flags.get("recommended_mapper")


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase5BackwardCompatibility:
    """Verify Phase 5 maintains backward compatibility."""

    def test_refine_function_exists(self):
        """Test _refine_policy_with_formulas function exists."""
        assert callable(_refine_policy_with_formulas)

    def test_returns_dict(self):
        """Test function returns a dict."""
        flags = {}
        unified = {}
        profile = {"formula_ui_mode": "none"}
        result = _refine_policy_with_formulas(flags, unified, profile)
        assert isinstance(result, dict)

    def test_therapy_profile_has_formula_settings(self):
        """Test therapy profile has formula UI settings."""
        profile = get_domain_profile("therapy")
        assert "formula_ui_mode" in profile
        assert "min_resonance_for_reflection" in profile
        assert "max_tension_for_reflection" in profile

    def test_trading_unchanged_by_phase5(self):
        """Test trading domain is unchanged by Phase 5."""
        profile = get_domain_profile("trading")
        assert profile["formula_ui_mode"] == "none"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
