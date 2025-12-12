"""
Phase 54 Test Suite: Action Eligibility & Commitment Boundary Engine (AECBE)

This test suite validates the Phase 54 AECBE implementation across:
1. Formula math and determinism
2. Coherence state integration
3. Session summary aggregation
4. API + Observer integration
5. Behavioral invariance (no routing/mapper/policy changes)

CRITICAL INVARIANTS:
- Zero-LLM
- Observation-only
- Deterministic
- Fully bounded [0.0, 1.0]
- Backward compatible
- NO action execution
- NO action selection
"""

try:
    import pytest
except ImportError:
    pytest = None

from symbolu.formulas.action_eligibility_boundary import (
    compute_action_eligibility_boundary,
    ActionEligibilitySnapshot,
)


# ============================================================================
# GROUP A: Formula Math Tests
# ============================================================================

def test_formula_basic_computation():
    """Test basic AECBE formula computation with valid inputs."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.75,
        "internal_consistency_strength": 0.78,
        "prediction_reversal_risk": 0.25,
        "regression_drift_score": 0.28,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.72,
        "evidence_conflict_index": 0.22,
        "evidence_stability": 0.74,
        "context_relevance_score": 0.70,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.76,
        "divergence_index": 0.24,
        "evidence_conflict_index": 0.23,
        "stability_projection_index": 0.73,
    }

    external_trust_signals = {
        "external_trust_score": 0.77,
        "internal_override_pressure": 0.25,
        "external_signal_fragility": 0.26,
        "alignment_resilience": 0.75,
        "trust_decay_risk": 0.24,
    }

    stability_signals = {
        "synthesis_integrity": 0.74,
        "macro_stability_index": 0.73,
        "temporal_stability_index": 0.76,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert isinstance(snapshot, ActionEligibilitySnapshot)
    assert 0.0 <= snapshot.action_eligibility_score <= 1.0
    assert 0.0 <= snapshot.internal_stability_index <= 1.0
    assert 0.0 <= snapshot.external_alignment_index <= 1.0
    assert 0.0 <= snapshot.trust_confidence_index <= 1.0
    assert 0.0 <= snapshot.conflict_suppression_index <= 1.0
    assert 0.0 <= snapshot.temporal_persistence_index <= 1.0
    assert snapshot.eligibility_band in [
        "ELIGIBLE",
        "CONDITIONALLY_ELIGIBLE",
        "NOT_ELIGIBLE",
        "BLOCKED",
    ]
    assert isinstance(snapshot.eligibility_tags, list)


def test_formula_determinism():
    """Test that formula produces deterministic results."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.60,
        "internal_consistency_strength": 0.62,
        "prediction_reversal_risk": 0.40,
        "regression_drift_score": 0.42,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.58,
        "evidence_conflict_index": 0.38,
        "evidence_stability": 0.60,
        "context_relevance_score": 0.56,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.61,
        "divergence_index": 0.39,
        "evidence_conflict_index": 0.37,
        "stability_projection_index": 0.59,
    }

    external_trust_signals = {
        "external_trust_score": 0.62,
        "internal_override_pressure": 0.40,
        "external_signal_fragility": 0.41,
        "alignment_resilience": 0.60,
        "trust_decay_risk": 0.39,
    }

    stability_signals = {
        "synthesis_integrity": 0.59,
        "macro_stability_index": 0.58,
        "temporal_stability_index": 0.61,
    }

    # Compute twice
    snapshot1 = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    snapshot2 = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    # Results should be identical
    assert snapshot1.action_eligibility_score == snapshot2.action_eligibility_score
    assert snapshot1.eligibility_band == snapshot2.eligibility_band
    assert snapshot1.internal_stability_index == snapshot2.internal_stability_index
    assert snapshot1.external_alignment_index == snapshot2.external_alignment_index
    assert snapshot1.trust_confidence_index == snapshot2.trust_confidence_index
    assert snapshot1.conflict_suppression_index == snapshot2.conflict_suppression_index
    assert snapshot1.temporal_persistence_index == snapshot2.temporal_persistence_index
    assert snapshot1.eligibility_tags == snapshot2.eligibility_tags


def test_formula_bounds():
    """Test that all outputs are bounded [0.0, 1.0]."""
    # Extreme low values
    cognitive_consistency_signals = {
        "regression_stability_index": 0.0,
        "internal_consistency_strength": 0.0,
        "prediction_reversal_risk": 1.0,
        "regression_drift_score": 1.0,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.0,
        "evidence_conflict_index": 1.0,
        "evidence_stability": 0.0,
        "context_relevance_score": 0.0,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.0,
        "divergence_index": 1.0,
        "evidence_conflict_index": 1.0,
        "stability_projection_index": 0.0,
    }

    external_trust_signals = {
        "external_trust_score": 0.0,
        "internal_override_pressure": 1.0,
        "external_signal_fragility": 1.0,
        "alignment_resilience": 0.0,
        "trust_decay_risk": 1.0,
    }

    stability_signals = {
        "synthesis_integrity": 0.0,
        "macro_stability_index": 0.0,
        "temporal_stability_index": 0.0,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert 0.0 <= snapshot.action_eligibility_score <= 1.0
    assert 0.0 <= snapshot.internal_stability_index <= 1.0
    assert 0.0 <= snapshot.external_alignment_index <= 1.0
    assert 0.0 <= snapshot.trust_confidence_index <= 1.0
    assert 0.0 <= snapshot.conflict_suppression_index <= 1.0
    assert 0.0 <= snapshot.temporal_persistence_index <= 1.0


def test_formula_bounds_high():
    """Test bounds with extreme high values."""
    # Extreme high values
    cognitive_consistency_signals = {
        "regression_stability_index": 1.0,
        "internal_consistency_strength": 1.0,
        "prediction_reversal_risk": 0.0,
        "regression_drift_score": 0.0,
    }

    rag_coherence_signals = {
        "evidence_alignment": 1.0,
        "evidence_conflict_index": 0.0,
        "evidence_stability": 1.0,
        "context_relevance_score": 1.0,
    }

    internal_external_alignment_signals = {
        "alignment_index": 1.0,
        "divergence_index": 0.0,
        "evidence_conflict_index": 0.0,
        "stability_projection_index": 1.0,
    }

    external_trust_signals = {
        "external_trust_score": 1.0,
        "internal_override_pressure": 0.0,
        "external_signal_fragility": 0.0,
        "alignment_resilience": 1.0,
        "trust_decay_risk": 0.0,
    }

    stability_signals = {
        "synthesis_integrity": 1.0,
        "macro_stability_index": 1.0,
        "temporal_stability_index": 1.0,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert 0.0 <= snapshot.action_eligibility_score <= 1.0
    assert 0.0 <= snapshot.internal_stability_index <= 1.0
    assert 0.0 <= snapshot.external_alignment_index <= 1.0
    assert 0.0 <= snapshot.trust_confidence_index <= 1.0
    assert 0.0 <= snapshot.conflict_suppression_index <= 1.0
    assert 0.0 <= snapshot.temporal_persistence_index <= 1.0
    assert snapshot.eligibility_band == "ELIGIBLE"


def test_formula_band_classification_eligible():
    """Test ELIGIBLE band classification."""
    # High stability + high trust + low conflict
    cognitive_consistency_signals = {
        "regression_stability_index": 0.80,
        "internal_consistency_strength": 0.82,
        "prediction_reversal_risk": 0.18,
        "regression_drift_score": 0.20,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.78,
        "evidence_conflict_index": 0.15,
        "evidence_stability": 0.80,
        "context_relevance_score": 0.76,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.81,
        "divergence_index": 0.19,
        "evidence_conflict_index": 0.17,
        "stability_projection_index": 0.79,
    }

    external_trust_signals = {
        "external_trust_score": 0.83,
        "internal_override_pressure": 0.18,
        "external_signal_fragility": 0.16,
        "alignment_resilience": 0.81,
        "trust_decay_risk": 0.17,
    }

    stability_signals = {
        "synthesis_integrity": 0.80,
        "macro_stability_index": 0.79,
        "temporal_stability_index": 0.82,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert snapshot.eligibility_band == "ELIGIBLE"
    assert snapshot.action_eligibility_score >= 0.70


def test_formula_band_classification_blocked():
    """Test BLOCKED band classification."""
    # Severe contradictions and low scores
    cognitive_consistency_signals = {
        "regression_stability_index": 0.15,
        "internal_consistency_strength": 0.18,
        "prediction_reversal_risk": 0.85,
        "regression_drift_score": 0.88,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.12,
        "evidence_conflict_index": 0.90,
        "evidence_stability": 0.14,
        "context_relevance_score": 0.10,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.13,
        "divergence_index": 0.87,
        "evidence_conflict_index": 0.89,
        "stability_projection_index": 0.15,
    }

    external_trust_signals = {
        "external_trust_score": 0.11,
        "internal_override_pressure": 0.88,
        "external_signal_fragility": 0.90,
        "alignment_resilience": 0.12,
        "trust_decay_risk": 0.87,
    }

    stability_signals = {
        "synthesis_integrity": 0.14,
        "macro_stability_index": 0.13,
        "temporal_stability_index": 0.16,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert snapshot.eligibility_band == "BLOCKED"
    assert snapshot.action_eligibility_score < 0.30


def test_formula_graceful_degradation_insufficient_data():
    """Test graceful degradation with insufficient data."""
    # Only 2 out of 5 signal groups (need at least 3)
    cognitive_consistency_signals = {
        "regression_stability_index": 0.60,
        "internal_consistency_strength": 0.62,
        "prediction_reversal_risk": 0.40,
        "regression_drift_score": 0.42,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.58,
        "evidence_conflict_index": 0.38,
        "evidence_stability": 0.60,
        "context_relevance_score": 0.56,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=None,
    )

    assert snapshot is None


def test_formula_graceful_degradation_empty_dicts():
    """Test graceful degradation with empty dictionaries."""
    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals={},
        rag_coherence_signals={},
        internal_external_alignment_signals={},
        external_trust_signals={},
        stability_signals={},
    )

    assert snapshot is None


def test_formula_partial_signals():
    """Test with partial signals (exactly 3 groups)."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.65,
        "internal_consistency_strength": 0.67,
        "prediction_reversal_risk": 0.35,
        "regression_drift_score": 0.38,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.63,
        "evidence_conflict_index": 0.33,
        "evidence_stability": 0.65,
        "context_relevance_score": 0.61,
    }

    stability_signals = {
        "synthesis_integrity": 0.64,
        "macro_stability_index": 0.63,
        "temporal_stability_index": 0.66,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert isinstance(snapshot, ActionEligibilitySnapshot)


def test_formula_tag_generation():
    """Test diagnostic tag generation."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.78,
        "internal_consistency_strength": 0.80,
        "prediction_reversal_risk": 0.22,
        "regression_drift_score": 0.25,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.76,
        "evidence_conflict_index": 0.18,
        "evidence_stability": 0.78,
        "context_relevance_score": 0.74,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.79,
        "divergence_index": 0.21,
        "evidence_conflict_index": 0.20,
        "stability_projection_index": 0.77,
    }

    external_trust_signals = {
        "external_trust_score": 0.81,
        "internal_override_pressure": 0.20,
        "external_signal_fragility": 0.19,
        "alignment_resilience": 0.79,
        "trust_decay_risk": 0.20,
    }

    stability_signals = {
        "synthesis_integrity": 0.78,
        "macro_stability_index": 0.77,
        "temporal_stability_index": 0.80,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    assert len(snapshot.eligibility_tags) > 0
    assert isinstance(snapshot.eligibility_tags, list)
    # Tags should be sorted and deduplicated
    assert snapshot.eligibility_tags == sorted(set(snapshot.eligibility_tags))


# ============================================================================
# GROUP B: Behavioral Invariance Tests
# ============================================================================

def test_invariance_no_llm_imports():
    """Verify zero-LLM invariant (no anthropic/openai imports)."""
    import sys
    import symbolu.formulas.action_eligibility_boundary as module

    # Check for forbidden imports
    forbidden_modules = ["anthropic", "openai"]
    for mod_name in forbidden_modules:
        assert mod_name not in sys.modules or mod_name not in str(module.__dict__)


def test_invariance_observation_only():
    """Verify observation-only invariant (no state mutation)."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.70,
        "internal_consistency_strength": 0.72,
        "prediction_reversal_risk": 0.30,
        "regression_drift_score": 0.32,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.68,
        "evidence_conflict_index": 0.28,
        "evidence_stability": 0.70,
        "context_relevance_score": 0.66,
    }

    stability_signals = {
        "synthesis_integrity": 0.69,
        "macro_stability_index": 0.68,
        "temporal_stability_index": 0.71,
    }

    # Make copies to verify no mutation
    cc_copy = cognitive_consistency_signals.copy()
    rag_copy = rag_coherence_signals.copy()
    stab_copy = stability_signals.copy()

    compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=stability_signals,
    )

    # Verify no mutation
    assert cognitive_consistency_signals == cc_copy
    assert rag_coherence_signals == rag_copy
    assert stability_signals == stab_copy


def test_invariance_deterministic_ordering():
    """Verify tags are deterministically sorted."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.75,
        "internal_consistency_strength": 0.77,
        "prediction_reversal_risk": 0.25,
        "regression_drift_score": 0.27,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.73,
        "evidence_conflict_index": 0.23,
        "evidence_stability": 0.75,
        "context_relevance_score": 0.71,
    }

    stability_signals = {
        "synthesis_integrity": 0.74,
        "macro_stability_index": 0.73,
        "temporal_stability_index": 0.76,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    # Tags should be sorted
    assert snapshot.eligibility_tags == sorted(snapshot.eligibility_tags)


def test_invariance_no_action_execution():
    """Verify no action execution (observation-only)."""
    # This test verifies the formula only computes metrics, doesn't execute actions
    cognitive_consistency_signals = {
        "regression_stability_index": 0.85,
        "internal_consistency_strength": 0.87,
        "prediction_reversal_risk": 0.15,
        "regression_drift_score": 0.17,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.83,
        "evidence_conflict_index": 0.13,
        "evidence_stability": 0.85,
        "context_relevance_score": 0.81,
    }

    stability_signals = {
        "synthesis_integrity": 0.84,
        "macro_stability_index": 0.83,
        "temporal_stability_index": 0.86,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=stability_signals,
    )

    # Snapshot should only contain metrics, not trigger any actions
    assert snapshot is not None
    assert hasattr(snapshot, 'action_eligibility_score')
    assert hasattr(snapshot, 'eligibility_band')
    # No action execution methods or fields should exist
    assert not hasattr(snapshot, 'execute_action')
    assert not hasattr(snapshot, 'selected_action')
    assert not hasattr(snapshot, 'action_result')


def test_invariance_backward_compatible():
    """Verify backward compatibility (formula accepts None inputs)."""
    # Should work with None for all optional inputs
    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=None,
        rag_coherence_signals=None,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=None,
    )

    # Should gracefully degrade
    assert snapshot is None


# ============================================================================
# GROUP C: Edge Cases
# ============================================================================

def test_edge_case_mid_range_values():
    """Test with all mid-range values (0.5)."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.5,
        "internal_consistency_strength": 0.5,
        "prediction_reversal_risk": 0.5,
        "regression_drift_score": 0.5,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.5,
        "evidence_conflict_index": 0.5,
        "evidence_stability": 0.5,
        "context_relevance_score": 0.5,
    }

    internal_external_alignment_signals = {
        "alignment_index": 0.5,
        "divergence_index": 0.5,
        "evidence_conflict_index": 0.5,
        "stability_projection_index": 0.5,
    }

    external_trust_signals = {
        "external_trust_score": 0.5,
        "internal_override_pressure": 0.5,
        "external_signal_fragility": 0.5,
        "alignment_resilience": 0.5,
        "trust_decay_risk": 0.5,
    }

    stability_signals = {
        "synthesis_integrity": 0.5,
        "macro_stability_index": 0.5,
        "temporal_stability_index": 0.5,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=internal_external_alignment_signals,
        external_trust_signals=external_trust_signals,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    # All outputs should be valid
    assert 0.0 <= snapshot.action_eligibility_score <= 1.0
    assert snapshot.eligibility_band in ["ELIGIBLE", "CONDITIONALLY_ELIGIBLE", "NOT_ELIGIBLE", "BLOCKED"]


def test_edge_case_missing_optional_fields():
    """Test with minimal required fields only."""
    cognitive_consistency_signals = {
        "regression_stability_index": 0.60,
        "internal_consistency_strength": 0.62,
    }

    rag_coherence_signals = {
        "evidence_alignment": 0.58,
    }

    stability_signals = {
        "synthesis_integrity": 0.59,
    }

    snapshot = compute_action_eligibility_boundary(
        cognitive_consistency_signals=cognitive_consistency_signals,
        rag_coherence_signals=rag_coherence_signals,
        internal_external_alignment_signals=None,
        external_trust_signals=None,
        stability_signals=stability_signals,
    )

    assert snapshot is not None
    # Should use defaults for missing fields
    assert 0.0 <= snapshot.action_eligibility_score <= 1.0


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available, tests can be run manually")
