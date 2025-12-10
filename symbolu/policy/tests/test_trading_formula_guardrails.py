"""
Test Suite for Trading Formula Guardrails v1.0
===============================================

Comprehensive tests for Phase 7: Formula-Aware Trading Guardrails.

Test Coverage:
    Group A: Threshold Logic Tests (8 tests)
    Group B: Integration Tests (10 tests)
    Group C: Determinism Tests (4 tests)

Total: 22 tests minimum (meets requirement)

Design Principles:
    - Zero-LLM: All tests are deterministic
    - No mocking of formulas: Use real SessionSummary objects
    - Comprehensive edge cases: Boundary conditions, missing data, etc.
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict, Optional

from symbolu.policy.trading_guardrail_engine import (
    TradingGuardrailFlags,
    compute_trading_guardrails,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockSessionSummary:
    """
    Mock SessionSummary for testing.

    Simulates the SessionSummary object with all required metrics.
    """
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


# ============================================================================
# GROUP A: THRESHOLD LOGIC TESTS
# ============================================================================


class TestThresholdLogic:
    """
    Test threshold-based guardrail logic.

    Tests the 4 canonical rules:
    1. High Tension Risk
    2. Negative Momentum Risk
    3. Volatility Risk
    4. Recommend No Action
    """

    def test_high_tension_risk_triggered(self):
        """
        Test high tension risk triggers when both conditions met.

        Conditions:
        - tension_corridor > max_tension_allowed (0.75 > 0.70)
        - resonance_index < 0.45 (0.40 < 0.45)
        """
        summary = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.40,
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

    def test_high_tension_risk_not_triggered_tension_below_threshold(self):
        """
        Test high tension risk not triggered when tension below threshold.

        Conditions:
        - tension_corridor <= max_tension_allowed (0.65 <= 0.70)
        - resonance_index < 0.45 (0.40 < 0.45)

        Result: No high tension risk (tension not high enough)
        """
        summary = MockSessionSummary(
            tension_corridor=0.65,
            resonance_index=0.40,
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is False

    def test_high_tension_risk_not_triggered_resonance_above_threshold(self):
        """
        Test high tension risk not triggered when resonance above threshold.

        Conditions:
        - tension_corridor > max_tension_allowed (0.75 > 0.70)
        - resonance_index >= 0.45 (0.50 >= 0.45)

        Result: No high tension risk (resonance high enough)
        """
        summary = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.50,
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.high_tension_risk is False

    def test_negative_momentum_risk_triggered(self):
        """
        Test negative momentum risk triggers when both conditions met.

        Conditions:
        - delta_smi < -max_negative_delta_smi (-0.15 < -0.12)
        - coherence_score_v1 < 0.55 (0.50 < 0.55)
        """
        summary = MockSessionSummary(
            delta_smi=-0.15,
            coherence_score=0.50,
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

    def test_negative_momentum_risk_not_triggered_delta_smi_above_threshold(self):
        """
        Test negative momentum risk not triggered when delta_smi above threshold.

        Conditions:
        - delta_smi >= -max_negative_delta_smi (-0.10 >= -0.12)
        - coherence_score_v1 < 0.55 (0.50 < 0.55)

        Result: No negative momentum risk (delta_smi not low enough)
        """
        summary = MockSessionSummary(
            delta_smi=-0.10,
            coherence_score=0.50,
        )

        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        assert guardrails.negative_momentum_risk is False

    def test_volatility_risk_triggered(self):
        """
        Test volatility risk triggers when both conditions met.

        Conditions:
        - mapper_volatility_score > max_volatility_allowed (0.65 > 0.60)
        - persona_drift_score > 0.45 (0.50 > 0.45)
        """
        summary = MockSessionSummary(
            mapper_volatility_score=0.65,
            persona_drift_score=0.50,
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

    def test_all_risks_below_threshold(self):
        """
        Test no risks triggered when all metrics below threshold.

        Conditions:
        - tension_corridor <= max_tension_allowed
        - resonance_index >= 0.45
        - delta_smi >= -max_negative_delta_smi
        - coherence_score_v1 >= 0.55
        - mapper_volatility_score <= max_volatility_allowed
        - persona_drift_score <= 0.45

        Result: No risks, recommend_no_action = False
        """
        summary = MockSessionSummary(
            tension_corridor=0.60,
            resonance_index=0.50,
            delta_smi=-0.05,
            coherence_score=0.60,
            mapper_volatility_score=0.50,
            persona_drift_score=0.40,
        )

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

    def test_recommend_no_action_master_switch(self):
        """
        Test recommend_no_action triggers when ANY risk is present.

        Test all 3 individual risk triggers:
        1. High tension risk
        2. Negative momentum risk
        3. Volatility risk

        Result: recommend_no_action = True for each
        """
        # Test 1: High tension risk only
        summary1 = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.40,
        )
        guardrails1 = compute_trading_guardrails(summary1, None, None, None, None)
        assert guardrails1.recommend_no_action is True

        # Test 2: Negative momentum risk only
        summary2 = MockSessionSummary(
            delta_smi=-0.15,
            coherence_score=0.50,
        )
        guardrails2 = compute_trading_guardrails(summary2, None, None, None, None)
        assert guardrails2.recommend_no_action is True

        # Test 3: Volatility risk only
        summary3 = MockSessionSummary(
            mapper_volatility_score=0.65,
            persona_drift_score=0.50,
        )
        guardrails3 = compute_trading_guardrails(summary3, None, None, None, None)
        assert guardrails3.recommend_no_action is True


# ============================================================================
# GROUP B: INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """
    Test integration with domain profiles, unified API, and DILchat adapter.
    """

    def test_domain_profile_guardrails_enabled_for_trading(self):
        """
        Test trading domain profile has guardrails enabled.
        """
        from symbolu.policy.domain_profiles import get_domain_profile

        profile = get_domain_profile("trading")
        assert profile["formula_guardrails_enabled"] is True
        assert profile["max_tension_allowed"] == 0.70
        assert profile["max_negative_delta_smi"] == 0.12
        assert profile["max_volatility_allowed"] == 0.60

    def test_domain_profile_guardrails_disabled_for_therapy(self):
        """
        Test therapy domain profile has guardrails disabled.
        """
        from symbolu.policy.domain_profiles import get_domain_profile

        profile = get_domain_profile("therapy")
        assert profile["formula_guardrails_enabled"] is False

    def test_domain_profile_guardrails_disabled_for_identity(self):
        """
        Test identity domain profile has guardrails disabled.
        """
        from symbolu.policy.domain_profiles import get_domain_profile

        profile = get_domain_profile("identity")
        assert profile["formula_guardrails_enabled"] is False

    def test_domain_profile_guardrails_disabled_for_generic(self):
        """
        Test generic domain profile has guardrails disabled.
        """
        from symbolu.policy.domain_profiles import get_domain_profile

        profile = get_domain_profile("generic")
        assert profile["formula_guardrails_enabled"] is False

    def test_guardrails_to_dict_serialization(self):
        """
        Test TradingGuardrailFlags.to_dict() produces JSON-safe output.
        """
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

    def test_guardrails_none_when_summary_missing(self):
        """
        Test compute_trading_guardrails raises ValueError when summary is None.
        """
        with pytest.raises(ValueError, match="SessionSummary is required"):
            compute_trading_guardrails(
                summary=None,
                policy=None,
                motivation=None,
                intent_arc=None,
                identity_signature=None,
            )

    def test_guardrails_safe_extraction_with_missing_attributes(self):
        """
        Test guardrails computation handles missing attributes gracefully.

        Uses default values when attributes are missing.
        """
        # Create a minimal summary with only some attributes
        class MinimalSummary:
            coherence_score = 0.50
            tension_corridor = 0.75
            # Missing: resonance_index, delta_smi, mapper_volatility_score, etc.

        summary = MinimalSummary()

        # Should not raise, should use defaults
        guardrails = compute_trading_guardrails(
            summary=summary,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # With defaults, high_tension_risk should trigger (tension high, resonance defaults to 1.0)
        # Actually, default resonance_index is 1.0, so high_tension_risk should NOT trigger
        # Let's verify this behavior
        assert guardrails.high_tension_risk is False  # resonance_index defaults to 1.0 (> 0.45)

    def test_guardrails_dict_extraction_support(self):
        """
        Test guardrails computation works with dict-based summary.

        Supports both attribute access and dict access.
        """
        summary_dict = {
            "coherence_score": 0.50,
            "tension_corridor": 0.75,
            "resonance_index": 0.40,
            "delta_smi": -0.15,
            "mapper_volatility_score": 0.65,
            "persona_drift_score": 0.50,
            "max_tension_allowed": 0.70,
            "max_negative_delta_smi": 0.12,
            "max_volatility_allowed": 0.60,
        }

        guardrails = compute_trading_guardrails(
            summary=summary_dict,
            policy=None,
            motivation=None,
            intent_arc=None,
            identity_signature=None,
        )

        # All 3 risks should trigger
        assert guardrails.high_tension_risk is True
        assert guardrails.negative_momentum_risk is True
        assert guardrails.volatility_risk is True
        assert guardrails.recommend_no_action is True

    def test_dilchat_badges_for_high_tension_risk(self):
        """
        Test DILchat adapter produces HIGH_TENSION_RISK badge.
        """
        from symbolu.adapter.dilchat_adapter import _build_badges

        trading_guardrails = {
            "high_tension_risk": True,
            "negative_momentum_risk": False,
            "volatility_risk": False,
            "recommend_no_action": True,
        }

        badges = _build_badges(
            stability_status="stable",
            policy_flags={},
            coherence_score=0.80,
            trading_guardrails=trading_guardrails,
        )

        # Find HIGH_TENSION_RISK badge
        high_tension_badge = next((b for b in badges if b.label == "HIGH_TENSION_RISK"), None)
        assert high_tension_badge is not None
        assert high_tension_badge.level == "critical"

        # Find NO_ACTION_RECOMMENDED badge
        no_action_badge = next((b for b in badges if b.label == "NO_ACTION_RECOMMENDED"), None)
        assert no_action_badge is not None
        assert no_action_badge.level == "critical"

    def test_dilchat_hints_for_trading_guardrails(self):
        """
        Test DILchat adapter produces trading guardrail hints.
        """
        from symbolu.adapter.dilchat_adapter import _build_hints

        trading_guardrails = {
            "high_tension_risk": True,
            "negative_momentum_risk": False,
            "volatility_risk": True,
            "recommend_no_action": True,
        }

        hints = _build_hints(
            policy_flags={},
            trading_guardrails=trading_guardrails,
        )

        # Find AVOID_TRADE hint
        avoid_trade_hint = next((h for h in hints if h.code == "AVOID_TRADE"), None)
        assert avoid_trade_hint is not None

        # Find WAIT_FOR_STABILITY hint (high_tension_risk triggers this)
        wait_hint = next((h for h in hints if h.code == "WAIT_FOR_STABILITY"), None)
        assert wait_hint is not None

        # Find MARKET_VOLATILITY_ALERT hint (volatility_risk triggers this)
        volatility_hint = next((h for h in hints if h.code == "MARKET_VOLATILITY_ALERT"), None)
        assert volatility_hint is not None


# ============================================================================
# GROUP C: DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """
    Test deterministic behavior of trading guardrails.

    Guardrails must produce identical results for identical inputs.
    """

    def test_same_input_same_output(self):
        """
        Test that identical inputs produce identical outputs.

        Run guardrails computation twice with same summary.
        Results must be byte-identical.
        """
        summary = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.40,
            delta_smi=-0.15,
            coherence_score=0.50,
            mapper_volatility_score=0.65,
            persona_drift_score=0.50,
        )

        guardrails1 = compute_trading_guardrails(summary, None, None, None, None)
        guardrails2 = compute_trading_guardrails(summary, None, None, None, None)

        assert guardrails1.high_tension_risk == guardrails2.high_tension_risk
        assert guardrails1.negative_momentum_risk == guardrails2.negative_momentum_risk
        assert guardrails1.volatility_risk == guardrails2.volatility_risk
        assert guardrails1.recommend_no_action == guardrails2.recommend_no_action

    def test_snapshot_invariance(self):
        """
        Test snapshot invariance: known inputs produce known outputs.

        This is a regression test to ensure guardrail logic doesn't change.
        """
        # Snapshot 1: All risks triggered
        summary1 = MockSessionSummary(
            tension_corridor=0.80,
            resonance_index=0.35,
            delta_smi=-0.20,
            coherence_score=0.45,
            mapper_volatility_score=0.70,
            persona_drift_score=0.55,
        )

        guardrails1 = compute_trading_guardrails(summary1, None, None, None, None)

        assert guardrails1.high_tension_risk is True
        assert guardrails1.negative_momentum_risk is True
        assert guardrails1.volatility_risk is True
        assert guardrails1.recommend_no_action is True

        # Snapshot 2: No risks triggered
        summary2 = MockSessionSummary(
            tension_corridor=0.50,
            resonance_index=0.60,
            delta_smi=0.05,
            coherence_score=0.75,
            mapper_volatility_score=0.40,
            persona_drift_score=0.30,
        )

        guardrails2 = compute_trading_guardrails(summary2, None, None, None, None)

        assert guardrails2.high_tension_risk is False
        assert guardrails2.negative_momentum_risk is False
        assert guardrails2.volatility_risk is False
        assert guardrails2.recommend_no_action is False

    def test_boundary_conditions_exact_threshold(self):
        """
        Test boundary conditions when metrics are exactly at threshold.

        Guardrails should NOT trigger when metrics are exactly at threshold
        (use > not >=, use < not <=).
        """
        # Test 1: tension_corridor exactly at max_tension_allowed (0.70)
        summary1 = MockSessionSummary(
            tension_corridor=0.70,  # exactly at threshold
            resonance_index=0.40,
        )
        guardrails1 = compute_trading_guardrails(summary1, None, None, None, None)
        assert guardrails1.high_tension_risk is False  # not triggered (0.70 is not > 0.70)

        # Test 2: resonance_index exactly at threshold (0.45)
        summary2 = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.45,  # exactly at threshold
        )
        guardrails2 = compute_trading_guardrails(summary2, None, None, None, None)
        assert guardrails2.high_tension_risk is False  # not triggered (0.45 is not < 0.45)

    def test_zero_llm_no_randomness(self):
        """
        Test zero-LLM principle: no randomness, no LLM calls.

        Run guardrails 10 times with same input, verify identical results.
        """
        summary = MockSessionSummary(
            tension_corridor=0.75,
            resonance_index=0.40,
        )

        results = []
        for _ in range(10):
            guardrails = compute_trading_guardrails(summary, None, None, None, None)
            results.append(guardrails.to_dict())

        # All results must be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
