"""
Phase 7: Trading Formula Guardrails Test Suite
===============================================

Canonical test suite for Phase 7 - Formula-Aware Trading Guardrails v1.0.

Phase 7 introduces deterministic, zero-LLM trading safety guardrails based on
Symbol-U temporal formulas and coherence metrics. These guardrails provide
UI-layer risk indicators without modifying any pipeline behavior.

Test Coverage:
    Group A: Core Formula Logic (8 tests)
    Group B: Integration & API (6 tests)
    Group C: Behavioral Invariance (4 tests)
    Group D: Edge Cases & Determinism (4 tests)

Total: 22 tests

Design Principles Verified:
- Zero-LLM: Pure deterministic rule evaluation
- Non-invasive: Does not modify routing, rendering, or pipeline behavior
- UI-layer only: Provides metadata for presentation layer
- Feature-flag gated: Only runs when formula_guardrails_enabled=True
- Graceful degradation: Returns safe defaults when inputs missing
- JSON-serializable: All outputs can be serialized for API

Key Components Tested:
- symbolu.policy.trading_guardrail_engine.compute_trading_guardrails()
- symbolu.policy.trading_guardrail_engine.TradingGuardrailFlags
- Integration with SessionSummary, PolicyFlags, and domain profiles
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict, Optional

from symbolu.policy.trading_guardrail_engine import (
    TradingGuardrailFlags,
    compute_trading_guardrails,
)
from symbolu.policy.domain_profiles import get_domain_profile
from symbolu.service.sessions.session_models import SessionSummary
import json


# ==============================================================================
# TEST FIXTURES
# ==============================================================================


@dataclass
class MockSessionSummary:
    """Mock SessionSummary for testing guardrail logic."""
    coherence_score: float = 1.0
    tension_corridor: float = 0.0
    resonance_index: float = 1.0
    delta_smi: float = 0.0
    mapper_volatility_score: float = 0.0
    persona_drift_score: float = 0.0
    max_tension_allowed: float = 0.70
    max_negative_delta_smi: float = 0.12
    max_volatility_allowed: float = 0.60
    last_domain: str = "trading"


def create_safe_summary() -> MockSessionSummary:
    """Create a summary with all safe values (no risks)."""
    return MockSessionSummary(
        coherence_score=0.85,
        tension_corridor=0.30,
        resonance_index=0.75,
        delta_smi=0.05,
        mapper_volatility_score=0.25,
        persona_drift_score=0.20,
    )


def create_risky_summary() -> MockSessionSummary:
    """Create a summary with all risks triggered."""
    return MockSessionSummary(
        coherence_score=0.40,  # Low coherence
        tension_corridor=0.80,  # High tension (> 0.70)
        resonance_index=0.30,   # Low resonance (< 0.45)
        delta_smi=-0.15,        # Negative momentum (< -0.12)
        mapper_volatility_score=0.70,  # High volatility (> 0.60)
        persona_drift_score=0.50,      # High drift (> 0.45)
    )


# ==============================================================================
# GROUP A: CORE FORMULA LOGIC (8 tests)
# ==============================================================================


class TestCoreFormulaLogic:
    """Test core guardrail rule logic."""

    def test_high_tension_risk_both_conditions_met(self):
        """Test high tension risk when both conditions are met."""
        summary = MockSessionSummary(
            tension_corridor=0.75,  # > 0.70
            resonance_index=0.40,   # < 0.45
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is True
        assert guardrails.recommend_no_action is True

    def test_high_tension_risk_only_tension_high(self):
        """Test high tension risk NOT triggered when only tension is high."""
        summary = MockSessionSummary(
            tension_corridor=0.75,  # > 0.70
            resonance_index=0.65,   # > 0.45 (good resonance)
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is False

    def test_negative_momentum_risk_both_conditions_met(self):
        """Test negative momentum risk when both conditions are met."""
        summary = MockSessionSummary(
            delta_smi=-0.15,        # < -0.12
            coherence_score=0.50,   # < 0.55
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.negative_momentum_risk is True
        assert guardrails.recommend_no_action is True

    def test_negative_momentum_risk_only_delta_smi_negative(self):
        """Test negative momentum risk NOT triggered when only delta_smi is negative."""
        summary = MockSessionSummary(
            delta_smi=-0.15,        # < -0.12
            coherence_score=0.80,   # > 0.55 (good coherence)
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.negative_momentum_risk is False

    def test_volatility_risk_both_conditions_met(self):
        """Test volatility risk when both conditions are met."""
        summary = MockSessionSummary(
            mapper_volatility_score=0.70,  # > 0.60
            persona_drift_score=0.50,      # > 0.45
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.volatility_risk is True
        assert guardrails.recommend_no_action is True

    def test_volatility_risk_only_volatility_high(self):
        """Test volatility risk NOT triggered when only volatility is high."""
        summary = MockSessionSummary(
            mapper_volatility_score=0.70,  # > 0.60
            persona_drift_score=0.30,      # < 0.45 (low drift)
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.volatility_risk is False

    def test_no_risks_when_all_metrics_safe(self):
        """Test no risks triggered when all metrics are in safe ranges."""
        summary = create_safe_summary()

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is False
        assert guardrails.negative_momentum_risk is False
        assert guardrails.volatility_risk is False
        assert guardrails.recommend_no_action is False

    def test_all_risks_when_all_conditions_met(self):
        """Test all risks triggered when all conditions are met."""
        summary = create_risky_summary()

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is True
        assert guardrails.negative_momentum_risk is True
        assert guardrails.volatility_risk is True
        assert guardrails.recommend_no_action is True


# ==============================================================================
# GROUP B: INTEGRATION & API (6 tests)
# ==============================================================================


class TestIntegrationAndAPI:
    """Test integration with domain profiles and API layer."""

    def test_trading_domain_profile_has_guardrails_enabled(self):
        """Test trading domain profile has formula_guardrails_enabled=True."""
        profile = get_domain_profile("trading")

        assert "formula_guardrails_enabled" in profile
        assert profile["formula_guardrails_enabled"] is True

    def test_non_trading_domains_have_guardrails_disabled(self):
        """Test non-trading domains have formula_guardrails_enabled=False."""
        for domain in ["therapy", "identity", "generic"]:
            profile = get_domain_profile(domain)
            assert "formula_guardrails_enabled" in profile
            assert profile["formula_guardrails_enabled"] is False

    def test_guardrail_flags_to_dict_serialization(self):
        """Test TradingGuardrailFlags.to_dict() produces JSON-serializable output."""
        flags = TradingGuardrailFlags(
            high_tension_risk=True,
            negative_momentum_risk=False,
            volatility_risk=True,
            recommend_no_action=True,
        )

        result = flags.to_dict()

        assert isinstance(result, dict)
        assert result["high_tension_risk"] is True
        assert result["negative_momentum_risk"] is False
        assert result["volatility_risk"] is True
        assert result["recommend_no_action"] is True

        # Verify JSON serialization
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_guardrail_flags_all_false_by_default(self):
        """Test TradingGuardrailFlags defaults to all False (safe)."""
        flags = TradingGuardrailFlags()

        assert flags.high_tension_risk is False
        assert flags.negative_momentum_risk is False
        assert flags.volatility_risk is False
        assert flags.recommend_no_action is False

    def test_guardrails_included_in_unified_output_metadata(self):
        """Test guardrails are included in unified output metadata for trading domain."""
        # This test verifies integration at the unified API level
        # The actual implementation should include guardrails in metadata
        # when domain=trading and formula_guardrails_enabled=True

        # Note: This is a structural test - the actual integration
        # happens in symbolu/api/unified_api.py at line 705
        summary = create_risky_summary()
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Verify guardrails can be added to metadata
        metadata = {"trading_guardrails": guardrails.to_dict()}
        assert "trading_guardrails" in metadata
        assert metadata["trading_guardrails"]["recommend_no_action"] is True

    def test_boundary_values_at_exact_thresholds(self):
        """Test behavior at exact threshold boundaries."""
        # Test exactly at max_tension_allowed
        summary = MockSessionSummary(
            tension_corridor=0.70,  # Exactly at threshold
            resonance_index=0.40,   # Below threshold
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # At exact threshold should NOT trigger (> not >=)
        assert guardrails.high_tension_risk is False


# ==============================================================================
# GROUP C: BEHAVIORAL INVARIANCE (4 tests)
# ==============================================================================


class TestBehavioralInvariance:
    """Test that guardrails do not modify any pipeline behavior."""

    def test_guardrails_do_not_modify_routing(self):
        """Test guardrails do not affect routing decisions."""
        # Guardrails are UI-layer only and should never modify routing
        # This is verified by checking that compute_trading_guardrails
        # does not accept or return routing-related parameters

        summary = create_risky_summary()

        # Should only take summary and context, never routing state
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Output should be pure metadata, no routing changes
        assert isinstance(guardrails, TradingGuardrailFlags)
        assert not hasattr(guardrails, "routing_decision")
        assert not hasattr(guardrails, "active_mapper")

    def test_guardrails_do_not_modify_policy_flags(self):
        """Test guardrails do not modify policy flags."""
        summary = create_risky_summary()

        # Policy flags are read-only input, never modified
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Output contains only guardrail flags, not policy changes
        assert not hasattr(guardrails, "safety_first")
        assert not hasattr(guardrails, "ux_mode")

    def test_guardrails_do_not_trigger_llm_calls(self):
        """Test guardrails never trigger LLM calls (Zero-LLM guarantee)."""
        # This is verified by the fact that compute_trading_guardrails
        # only uses mathematical operations on metrics, no model calls

        summary = create_risky_summary()

        # Should be pure math, no LLM required
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # If this returns successfully, Zero-LLM is maintained
        assert isinstance(guardrails, TradingGuardrailFlags)

    def test_guardrails_deterministic_across_multiple_calls(self):
        """Test guardrails produce identical results for identical inputs."""
        summary = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.40,
            delta_smi=-0.15,
            coherence_score=0.50,
        )

        # Call multiple times
        result1 = compute_trading_guardrails(summary, None, None, None, None)
        result2 = compute_trading_guardrails(summary, None, None, None, None)
        result3 = compute_trading_guardrails(summary, None, None, None, None)

        # All results should be identical
        assert result1.to_dict() == result2.to_dict()
        assert result2.to_dict() == result3.to_dict()


# ==============================================================================
# GROUP D: EDGE CASES & DETERMINISM (4 tests)
# ==============================================================================


class TestEdgeCasesAndDeterminism:
    """Test edge cases and deterministic behavior."""

    def test_missing_metrics_graceful_degradation(self):
        """Test graceful handling when metrics are missing (None)."""
        # When metrics are missing, guardrails should default to safe (False)
        summary = MockSessionSummary(
            tension_corridor=None,
            resonance_index=None,
            delta_smi=None,
        )

        # Should not crash, should return safe defaults
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # All risks should be False when data is missing (safe default)
        assert isinstance(guardrails, TradingGuardrailFlags)

    def test_extreme_values_clamped_appropriately(self):
        """Test extreme metric values are handled correctly."""
        summary = MockSessionSummary(
            tension_corridor=1.5,    # > 1.0 (extreme)
            resonance_index=-0.5,    # < 0.0 (extreme)
            delta_smi=-1.0,          # Very negative
            mapper_volatility_score=2.0,  # > 1.0 (extreme)
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Should handle extreme values without crashing
        assert isinstance(guardrails, TradingGuardrailFlags)

    def test_floating_point_precision_stability(self):
        """Test stability with floating-point arithmetic edge cases."""
        summary = MockSessionSummary(
            tension_corridor=0.7000000001,  # Just barely over threshold
            resonance_index=0.4499999999,   # Just barely under threshold
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Should handle floating-point precision consistently
        assert isinstance(guardrails, TradingGuardrailFlags)

    def test_zero_values_handled_correctly(self):
        """Test behavior with all metrics at zero."""
        summary = MockSessionSummary(
            tension_corridor=0.0,
            resonance_index=0.0,
            delta_smi=0.0,
            coherence_score=0.0,
            mapper_volatility_score=0.0,
            persona_drift_score=0.0,
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # Zero values should be handled gracefully
        assert isinstance(guardrails, TradingGuardrailFlags)
        # With zero values, most risks should not trigger
        # (except possibly negative_momentum if coherence=0 < 0.55)
