"""
Tests for Safety Contract Component

Tests the fail-closed action gating system:
- SafetyContract frozen dataclass
- SafetyContractEvaluator with 6 preconditions
- SafetyGate orchestration
- Factory functions for evaluators
"""

import pytest

from agentic.agentic_framework.safety_contract import (
    SafetyContract,
    SafetyContractEvaluator,
    SafetyGate,
    create_default_evaluator,
    create_strict_evaluator,
    create_permissive_evaluator,
)
from agentic.agentic_framework.coherence_tracker import (
    CoherenceMetrics,
    create_initial_state,
)
from agentic.agentic_framework.goal_decomposition import GoalState


class TestSafetyContract:
    """Tests for SafetyContract frozen dataclass."""

    def test_safety_contract_creation(self):
        """Test basic SafetyContract creation."""
        contract = SafetyContract(
            eligible=True,
            internal_consistency=0.9,
            goal_alignment=0.85,
            prediction_reversal_risk=0.1,
            identity_stability=0.95,
        )
        assert contract.eligible is True
        assert contract.internal_consistency == 0.9
        assert contract.prediction_reversal_risk == 0.1

    def test_safety_contract_immutable(self):
        """Test that SafetyContract is immutable (frozen)."""
        contract = SafetyContract()
        with pytest.raises(Exception):  # FrozenInstanceError
            contract.eligible = True

    def test_safety_contract_defaults(self):
        """Test SafetyContract default values."""
        contract = SafetyContract()
        assert contract.eligible is False  # Fail-closed default
        assert contract.satisfied_preconditions == ()
        assert contract.violated_preconditions == ()
        assert contract.prediction_reversal_risk == 1.0  # Worst case default

    def test_safety_contract_with_reasons(self):
        """Test SafetyContract with blocking reasons."""
        contract = SafetyContract(
            eligible=False,
            blocking_reasons=("Low consistency", "High reversal risk"),
        )
        assert contract.eligible is False
        assert len(contract.blocking_reasons) == 2

    def test_safety_contract_to_dict(self):
        """Test SafetyContract serialization."""
        contract = SafetyContract(
            eligible=True,
            internal_consistency=0.9,
            goal_alignment=0.85,
        )
        d = contract.to_dict()

        assert d["eligible"] is True
        assert d["internal_consistency"] == 0.9
        assert "evaluation_timestamp" in d

    def test_is_action_forbidden(self):
        """Test forbidden action check."""
        contract = SafetyContract()

        assert contract.is_action_forbidden("destructive_file_operations") is True
        assert contract.is_action_forbidden("safe_read_operation") is False

    def test_get_rejection_summary(self):
        """Test rejection summary generation."""
        contract = SafetyContract(
            eligible=False,
            blocking_reasons=("Reason 1", "Reason 2"),
        )

        summary = contract.get_rejection_summary()

        assert "denied" in summary.lower()
        assert "Reason 1" in summary


class TestSafetyContractEvaluator:
    """Tests for SafetyContractEvaluator."""

    def test_evaluator_creation(self):
        """Test SafetyContractEvaluator creation."""
        evaluator = SafetyContractEvaluator()
        assert evaluator.consistency_threshold == 0.60
        assert evaluator.alignment_threshold == 0.60

    def test_evaluator_custom_thresholds(self):
        """Test SafetyContractEvaluator with custom thresholds."""
        evaluator = SafetyContractEvaluator(
            consistency_threshold=0.8,
            alignment_threshold=0.7,
            reversal_risk_threshold=0.2,
            stability_threshold=0.85,
        )
        assert evaluator.consistency_threshold == 0.8
        assert evaluator.reversal_risk_threshold == 0.2

    def test_evaluate_safe_state(self):
        """Test evaluation of safe state."""
        evaluator = SafetyContractEvaluator()

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        contract = evaluator.evaluate(state, goal)

        assert contract.eligible is True
        assert len(contract.violated_preconditions) == 0

    def test_evaluate_unsafe_low_consistency(self):
        """Test blocking when consistency is too low."""
        evaluator = SafetyContractEvaluator(consistency_threshold=0.8)

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.5,  # Below threshold
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.7,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        contract = evaluator.evaluate(state, goal)

        assert contract.eligible is False
        assert any("consistency" in r.lower() for r in contract.blocking_reasons)

    def test_evaluate_unsafe_high_reversal_risk(self):
        """Test blocking when reversal risk is too high."""
        evaluator = SafetyContractEvaluator(reversal_risk_threshold=0.3)

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.6,  # Above threshold
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.8,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        contract = evaluator.evaluate(state, goal)

        assert contract.eligible is False
        assert any("reversal" in r.lower() for r in contract.blocking_reasons)

    def test_evaluate_no_goal_state(self):
        """Test that missing goal state blocks."""
        evaluator = SafetyContractEvaluator()

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )

        contract = evaluator.evaluate(state, goal_state=None)

        assert contract.eligible is False
        assert any("goal" in r.lower() for r in contract.blocking_reasons)

    def test_evaluate_inform_agency_blocks(self):
        """Test that INFORM agency blocks actions."""
        evaluator = SafetyContractEvaluator()

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="informational",
            reasoning_strategy="Direct",
            agency_level="INFORM",  # Should block
        )

        contract = evaluator.evaluate(state, goal)

        assert contract.eligible is False
        assert any("agency" in r.lower() for r in contract.blocking_reasons)


class TestSafetyGate:
    """Tests for SafetyGate orchestration."""

    def test_safety_gate_creation(self):
        """Test SafetyGate creation."""
        gate = SafetyGate()
        assert gate.evaluator is not None

    def test_safety_gate_custom_evaluator(self):
        """Test SafetyGate with custom evaluator."""
        evaluator = SafetyContractEvaluator(consistency_threshold=0.9)
        gate = SafetyGate(evaluator=evaluator)
        assert gate.evaluator.consistency_threshold == 0.9

    def test_check_safe_action(self):
        """Test checking a safe action."""
        gate = SafetyGate()

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        contract, allowed = gate.check(state, goal)

        assert contract.eligible is True

    def test_check_filters_actions(self):
        """Test that check filters allowed actions."""
        gate = SafetyGate()

        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        action_types = ["read_file", "destructive_file_operations", "compute"]
        contract, allowed = gate.check(state, goal, action_types)

        # Destructive should be filtered out
        assert "read_file" in allowed
        assert "compute" in allowed
        assert "destructive_file_operations" not in allowed

    def test_gate_reset(self):
        """Test resetting gate state."""
        gate = SafetyGate()
        gate._recent_blocked = True
        gate._blocked_count = 5

        gate.reset()

        assert gate._recent_blocked is False
        assert gate._blocked_count == 0


class TestFactoryFunctions:
    """Tests for evaluator factory functions."""

    def test_create_default_evaluator(self):
        """Test default evaluator creation."""
        evaluator = create_default_evaluator()

        assert evaluator.consistency_threshold == 0.60
        assert evaluator.alignment_threshold == 0.60

    def test_create_strict_evaluator(self):
        """Test strict evaluator creation."""
        evaluator = create_strict_evaluator()

        # Strict should have higher thresholds
        assert evaluator.consistency_threshold >= 0.7
        assert evaluator.alignment_threshold >= 0.7

    def test_create_permissive_evaluator(self):
        """Test permissive evaluator creation."""
        evaluator = create_permissive_evaluator()

        # Permissive should have lower thresholds
        assert evaluator.consistency_threshold <= 0.55
        assert evaluator.alignment_threshold <= 0.55

    def test_strict_vs_permissive(self):
        """Test that strict is stricter than permissive."""
        strict = create_strict_evaluator()
        permissive = create_permissive_evaluator()

        assert strict.consistency_threshold > permissive.consistency_threshold
        assert strict.alignment_threshold > permissive.alignment_threshold


class TestSafetyContractIntegration:
    """Integration tests for safety contract system."""

    def test_full_safety_check_flow(self):
        """Test complete safety check flow."""
        gate = SafetyGate()

        # Simulate good coherence state
        state = create_initial_state("test")
        state.current_metrics = CoherenceMetrics(
            internal_consistency=0.88,
            prediction_reversal_risk=0.15,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.87,
            identity_stability=0.92,
            drift_magnitude=0.05,
            drift_direction="stable",
            overall_coherence=0.88,
        )

        goal = GoalState(
            purpose="Help user with programming",
            purpose_type="task",
            reasoning_strategy="Direct assistance",
            agency_level="CONFIRM",
        )

        # Check safety
        contract, allowed = gate.check(state, goal)

        # Verify contract
        assert contract.internal_consistency == 0.88
        assert contract.goal_alignment == 0.85
        assert contract.eligible is True

    def test_degrading_conversation_blocks(self):
        """Test that degrading conversation eventually blocks."""
        strict_gate = SafetyGate(evaluator=create_strict_evaluator())

        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        # Good state
        good_state = create_initial_state("test")
        good_state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.9,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )
        contract1, _ = strict_gate.check(good_state, goal)
        assert contract1.eligible is True

        # Degraded state
        bad_state = create_initial_state("test")
        bad_state.current_metrics = CoherenceMetrics(
            internal_consistency=0.4,
            prediction_reversal_risk=0.8,
            volatility_index=0.7,
            goal_alignment=0.3,
            factual_alignment=0.4,
            identity_stability=0.5,
            drift_magnitude=0.5,
            drift_direction="degrading",
            overall_coherence=0.4,
        )
        contract2, _ = strict_gate.check(bad_state, goal)
        assert contract2.eligible is False
