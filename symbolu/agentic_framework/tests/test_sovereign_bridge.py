"""
Tests for the Sovereign State Bridge (V11.0.0).

Validates that 32D Sovereign State tensor signals are correctly
converted into ConfidenceSignals and SafetyContract-compatible
coherence state for the agentic framework.
"""

import pytest

from symbolu.agentic_framework.sovereign_bridge import (
    signals_from_sovereign_state,
    coherence_from_sovereign_state,
    SovereignCoherenceState,
    _vritti_to_confidence,
    _kosha_to_budget,
    _guna_to_stability,
    _extract_slices,
    VRITTI_FACT,
    VRITTI_ERROR,
    VRITTI_VOID,
    GUNA_LUCIDITY,
    GUNA_ACTIVITY,
    GUNA_VELOCITY,
    GUNA_ACCEL,
    GUNA_STABLE,
    KOSHA_MATERIAL,
    KOSHA_INTELLECTUAL,
    KOSHA_BLISSFUL,
)
from symbolu.agentic_framework.confidence_gate import (
    ConfidenceSignals,
    ConfidenceGate,
    ConfidenceAggregator,
    merge_signals,
    signals_from_critique,
    create_confidence_gate,
)
from symbolu.agentic_framework.safety_contract import (
    SafetyContractEvaluator,
)


# =============================================================================
# Helper: Create 32D state vectors with specific control plane values
# =============================================================================

def make_state(
    bhava=None,
    kosha=None,
    vritti=None,
    guna=None,
    reserved=None,
):
    """Build a 32-float state list with specified slices."""
    state = [0.0] * 32
    if bhava:
        for i, v in enumerate(bhava):
            state[i] = v
    if kosha:
        for i, v in enumerate(kosha):
            state[12 + i] = v
    if vritti:
        for i, v in enumerate(vritti):
            state[17 + i] = v
    if guna:
        for i, v in enumerate(guna):
            state[22 + i] = v
    if reserved:
        for i, v in enumerate(reserved):
            state[28 + i] = v
    return state


# =============================================================================
# Test: Slice Extraction
# =============================================================================

class TestExtractSlices:
    def test_extracts_correct_slices(self):
        state = make_state(
            kosha=[0.1, 0.2, 0.3, 0.4, 0.5],
            vritti=[0.6, 0.1, 0.1, 0.1, 0.1],
            guna=[0.8, 0.2, 0.3, 0.1, 0.0, 0.9],
        )
        kosha, vritti, guna = _extract_slices(state)
        assert kosha == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert vritti == [0.6, 0.1, 0.1, 0.1, 0.1]
        assert guna == [0.8, 0.2, 0.3, 0.1, 0.0, 0.9]

    def test_rejects_short_state(self):
        with pytest.raises(ValueError, match="must have >= 28"):
            _extract_slices([0.0] * 20)


# =============================================================================
# Test: Vritti → Confidence
# =============================================================================

class TestVrittiToConfidence:
    def test_high_fact_gives_high_quality(self):
        """FACT-dominant state should produce high quality and correctness."""
        vritti = [0.8, 0.05, 0.05, 0.05, 0.05]  # FACT dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['quality_score'] > 0.7
        assert signals['correctness_score'] > 0.7
        assert signals['prediction_reversal_risk'] < 0.2
        assert signals['coherence_score'] > 0.8

    def test_high_error_gives_low_quality(self):
        """ERROR-dominant state should flag high reversal risk."""
        vritti = [0.05, 0.8, 0.05, 0.05, 0.05]  # ERROR dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['quality_score'] < 0.3
        assert signals['correctness_score'] < 0.1
        assert signals['prediction_reversal_risk'] > 0.7
        assert signals['coherence_score'] < 0.3

    def test_void_signals_emptiness(self):
        """VOID-dominant state should produce low coherence."""
        vritti = [0.05, 0.05, 0.05, 0.8, 0.05]  # VOID dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['coherence_score'] < 0.3

    def test_all_bounded_zero_one(self):
        """All output values should be in [0, 1]."""
        for dominant in range(5):
            vritti = [0.04] * 5
            vritti[dominant] = 0.84
            signals = _vritti_to_confidence(vritti)
            for key, val in signals.items():
                assert 0.0 <= val <= 1.0, f"{key}={val} out of bounds for dominant={dominant}"


# =============================================================================
# Test: Kosha → Budget
# =============================================================================

class TestKoshaToBudget:
    def test_material_dominant_low_complexity(self):
        """Surface-level processing should be low complexity."""
        kosha = [0.8, 0.1, 0.05, 0.03, 0.02]  # MATERIAL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['action_complexity'] < 0.3

    def test_intellectual_dominant_high_complexity(self):
        """Deep reasoning should be high complexity."""
        kosha = [0.02, 0.03, 0.05, 0.8, 0.1]  # INTELLECTUAL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['action_complexity'] > 0.5

    def test_blissful_gives_completeness(self):
        """Integration sheath should boost completeness."""
        kosha = [0.02, 0.03, 0.05, 0.1, 0.8]  # BLISSFUL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['completeness_score'] > 0.4


# =============================================================================
# Test: Guna → Stability
# =============================================================================

class TestGunaToStability:
    def test_high_lucidity_stable(self):
        """Sattva-dominant (clear, balanced) should be stable."""
        guna = [0.9, 0.1, 0.3, 0.1, 0.0, 0.8]  # High lucidity, high stable
        signals = _guna_to_stability(guna, delta_norm=0.1)
        assert signals['session_stability'] > 0.6
        assert signals['volatility_index'] < 0.3
        assert signals['identity_stability'] > 0.6

    def test_high_activity_volatile(self):
        """Rajas-dominant (turbulent, dynamic) should be volatile."""
        guna = [0.1, 0.9, 0.1, 0.7, 0.5, 0.1]  # High activity, high velocity
        signals = _guna_to_stability(guna, delta_norm=0.8)
        assert signals['volatility_index'] > 0.5
        assert signals['session_stability'] < 0.4

    def test_delta_norm_increases_volatility(self):
        """Large state changes should increase volatility."""
        guna = [0.5, 0.3, 0.3, 0.3, 0.1, 0.5]
        low_delta = _guna_to_stability(guna, delta_norm=0.0)
        high_delta = _guna_to_stability(guna, delta_norm=2.0)
        assert high_delta['volatility_index'] > low_delta['volatility_index']


# =============================================================================
# Test: Full Pipeline — signals_from_sovereign_state
# =============================================================================

class TestSignalsFromSovereignState:
    def test_returns_confidence_signals(self):
        """Should return a valid ConfidenceSignals dataclass."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        signals = signals_from_sovereign_state(state)
        assert isinstance(signals, ConfidenceSignals)

    def test_merges_with_other_sources(self):
        """Should merge cleanly with signals from other sources."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        sovereign_signals = signals_from_sovereign_state(state)

        # Simulate signals from a QualityCritique
        other_signals = ConfidenceSignals(
            relevance_score=0.9,
            goal_alignment=0.8,
        )

        merged = merge_signals(sovereign_signals, other_signals)
        # Sovereign should provide quality_score (non-default)
        assert merged.quality_score != 0.5
        # Other source should provide relevance (not derivable from state)
        assert merged.relevance_score == 0.9

    def test_feeds_into_confidence_gate(self):
        """Should produce a valid ConfidenceGateDecision."""
        state = make_state(
            vritti=[0.7, 0.05, 0.1, 0.1, 0.05],
            kosha=[0.2, 0.1, 0.3, 0.3, 0.1],
            guna=[0.7, 0.2, 0.3, 0.1, 0.05, 0.8],
        )
        signals = signals_from_sovereign_state(state)
        gate = create_confidence_gate()
        decision = gate.evaluate(signals)
        assert decision.confidence.overall >= 0.0
        assert decision.confidence.overall <= 1.0

    def test_high_error_triggers_escalation(self):
        """ERROR-dominant Vritti should cause escalation."""
        state = make_state(
            vritti=[0.05, 0.8, 0.05, 0.05, 0.05],  # ERROR dominant
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.2, 0.8, 0.1, 0.7, 0.5, 0.1],  # Also unstable
        )
        signals = signals_from_sovereign_state(state)
        gate = create_confidence_gate()
        decision = gate.evaluate(signals)
        # Should have low confidence
        assert decision.confidence.overall < 0.6


# =============================================================================
# Test: Full Pipeline — coherence_from_sovereign_state + SafetyContract
# =============================================================================

class TestCoherenceFromSovereignState:
    def test_returns_coherence_state(self):
        """Should return SovereignCoherenceState with current_metrics."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        coherence = coherence_from_sovereign_state(state)
        assert isinstance(coherence, SovereignCoherenceState)
        assert coherence.current_metrics is coherence  # Self-referential

    def test_feeds_into_safety_evaluator(self):
        """Should work with SafetyContractEvaluator.evaluate()."""
        # Stable state: high FACT, high LUCIDITY, high STABLE
        state = make_state(
            vritti=[0.8, 0.05, 0.05, 0.05, 0.05],
            guna=[0.8, 0.1, 0.3, 0.1, 0.0, 0.9],
        )
        coherence = coherence_from_sovereign_state(state)
        evaluator = SafetyContractEvaluator(
            consistency_threshold=0.5,
            stability_threshold=0.5,
            reversal_risk_threshold=0.4,
            alignment_threshold=0.0,  # Can't derive goal alignment from state
        )
        # SafetyContractEvaluator requires goal_state with agency_level for precondition 6
        class _GoalStub:
            agency_level = "FULL"
        contract = evaluator.evaluate(coherence, goal_state=_GoalStub())
        # Should pass: high consistency, low reversal risk, high stability
        assert contract.eligible is True

    def test_unstable_state_blocks_contract(self):
        """ERROR + high activity should fail safety contract."""
        state = make_state(
            vritti=[0.05, 0.8, 0.05, 0.05, 0.05],  # ERROR dominant
            guna=[0.1, 0.9, 0.1, 0.8, 0.6, 0.1],   # Volatile
        )
        coherence = coherence_from_sovereign_state(state, delta_S=[1.0] * 32)
        evaluator = SafetyContractEvaluator()
        contract = evaluator.evaluate(coherence)
        assert contract.eligible is False
        assert len(contract.violated_preconditions) > 0
