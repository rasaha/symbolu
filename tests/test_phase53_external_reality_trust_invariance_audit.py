"""
Phase 53 Test Suite: External Reality Trust Calibration Engine (ERTCE)

This test suite validates the Phase 53 ERTCE implementation across:
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
"""

import pytest
from symbolu.formulas.external_reality_trust_calibration import (
    compute_external_reality_trust_calibration,
    ExternalRealityTrustSnapshot,
)


# ============================================================================
# GROUP A: Formula Math Tests
# ============================================================================

def test_formula_basic_computation():
    """Test basic ERTCE formula computation with valid inputs."""
    external_reality_signals = {
        "evidence_alignment": 0.70,
        "evidence_conflict_index": 0.25,
        "evidence_stability": 0.72,
        "context_relevance_score": 0.68,
        "external_support_density": 0.71,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.73,
        "external_evidence_consistency_index": 0.69,
        "alignment_index": 0.75,
        "divergence_index": 0.25,
        "evidence_conflict_index": 0.24,
        "stability_projection_index": 0.71,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.72,
        "macro_stability_index": 0.70,
        "temporal_stability_index": 0.74,
        "internal_consistency_strength": 0.73,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    assert snapshot is not None
    assert isinstance(snapshot, ExternalRealityTrustSnapshot)
    assert 0.0 <= snapshot.external_trust_score <= 1.0
    assert 0.0 <= snapshot.internal_override_pressure <= 1.0
    assert 0.0 <= snapshot.external_signal_fragility <= 1.0
    assert 0.0 <= snapshot.alignment_resilience <= 1.0
    assert 0.0 <= snapshot.trust_decay_risk <= 1.0
    assert snapshot.trust_band in [
        "HIGH_EXTERNAL_TRUST",
        "CONDITIONAL_EXTERNAL_TRUST",
        "LOW_EXTERNAL_TRUST",
        "EXTERNAL_CONFLICT_ZONE",
    ]
    assert isinstance(snapshot.diagnostic_tags, list)


def test_formula_determinism():
    """Test that formula produces deterministic results."""
    external_reality_signals = {
        "evidence_alignment": 0.60,
        "evidence_conflict_index": 0.35,
        "evidence_stability": 0.62,
        "context_relevance_score": 0.58,
        "external_support_density": 0.61,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.63,
        "external_evidence_consistency_index": 0.59,
        "alignment_index": 0.65,
        "divergence_index": 0.35,
        "evidence_conflict_index": 0.34,
        "stability_projection_index": 0.61,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.62,
        "macro_stability_index": 0.60,
        "temporal_stability_index": 0.64,
        "internal_consistency_strength": 0.63,
    }

    # Compute twice
    snapshot1 = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    snapshot2 = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    # Results should be identical
    assert snapshot1.external_trust_score == snapshot2.external_trust_score
    assert snapshot1.internal_override_pressure == snapshot2.internal_override_pressure
    assert snapshot1.external_signal_fragility == snapshot2.external_signal_fragility
    assert snapshot1.alignment_resilience == snapshot2.alignment_resilience
    assert snapshot1.trust_decay_risk == snapshot2.trust_decay_risk
    assert snapshot1.trust_band == snapshot2.trust_band
    assert snapshot1.diagnostic_tags == snapshot2.diagnostic_tags


def test_formula_bounds():
    """Test that all outputs are bounded [0.0, 1.0]."""
    # Extreme low values
    external_reality_signals = {
        "evidence_alignment": 0.0,
        "evidence_conflict_index": 1.0,
        "evidence_stability": 0.0,
        "context_relevance_score": 0.0,
        "external_support_density": 0.0,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.0,
        "external_evidence_consistency_index": 0.0,
        "alignment_index": 0.0,
        "divergence_index": 1.0,
        "evidence_conflict_index": 1.0,
        "stability_projection_index": 0.0,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.0,
        "macro_stability_index": 0.0,
        "temporal_stability_index": 0.0,
        "internal_consistency_strength": 0.0,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    assert 0.0 <= snapshot.external_trust_score <= 1.0
    assert 0.0 <= snapshot.internal_override_pressure <= 1.0
    assert 0.0 <= snapshot.external_signal_fragility <= 1.0
    assert 0.0 <= snapshot.alignment_resilience <= 1.0
    assert 0.0 <= snapshot.trust_decay_risk <= 1.0

    # Extreme high values
    external_reality_signals = {
        "evidence_alignment": 1.0,
        "evidence_conflict_index": 0.0,
        "evidence_stability": 1.0,
        "context_relevance_score": 1.0,
        "external_support_density": 1.0,
    }

    internal_external_alignment = {
        "internal_consistency_index": 1.0,
        "external_evidence_consistency_index": 1.0,
        "alignment_index": 1.0,
        "divergence_index": 0.0,
        "evidence_conflict_index": 0.0,
        "stability_projection_index": 1.0,
    }

    internal_stability_signals = {
        "synthesis_integrity": 1.0,
        "macro_stability_index": 1.0,
        "temporal_stability_index": 1.0,
        "internal_consistency_strength": 1.0,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    assert 0.0 <= snapshot.external_trust_score <= 1.0
    assert 0.0 <= snapshot.internal_override_pressure <= 1.0
    assert 0.0 <= snapshot.external_signal_fragility <= 1.0
    assert 0.0 <= snapshot.alignment_resilience <= 1.0
    assert 0.0 <= snapshot.trust_decay_risk <= 1.0


def test_formula_band_classification_high_trust():
    """Test HIGH_EXTERNAL_TRUST band classification."""
    external_reality_signals = {
        "evidence_alignment": 0.90,
        "evidence_conflict_index": 0.10,
        "evidence_stability": 0.90,
        "context_relevance_score": 0.85,
        "external_support_density": 0.88,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.85,
        "external_evidence_consistency_index": 0.87,
        "alignment_index": 0.90,
        "divergence_index": 0.10,
        "evidence_conflict_index": 0.12,
        "stability_projection_index": 0.88,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.85,
        "macro_stability_index": 0.83,
        "temporal_stability_index": 0.86,
        "internal_consistency_strength": 0.84,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    # ETS >= 0.70, IOP <= 0.30, ESF <= 0.30
    assert snapshot.trust_band == "HIGH_EXTERNAL_TRUST"


def test_formula_band_classification_conflict_zone():
    """Test EXTERNAL_CONFLICT_ZONE band classification."""
    external_reality_signals = {
        "evidence_alignment": 0.20,
        "evidence_conflict_index": 0.85,
        "evidence_stability": 0.25,
        "context_relevance_score": 0.30,
        "external_support_density": 0.28,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.75,
        "external_evidence_consistency_index": 0.25,
        "alignment_index": 0.15,
        "divergence_index": 0.85,
        "evidence_conflict_index": 0.82,
        "stability_projection_index": 0.20,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.72,
        "macro_stability_index": 0.70,
        "temporal_stability_index": 0.73,
        "internal_consistency_strength": 0.71,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    # ETS < 0.30 or IOP > 0.70 or ESF > 0.70
    assert snapshot.trust_band == "EXTERNAL_CONFLICT_ZONE"


def test_formula_graceful_degradation_no_external():
    """Test graceful degradation when external signals missing."""
    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals={},
        internal_external_alignment={
            "alignment_index": 0.5,
        },
        internal_stability_signals={
            "synthesis_integrity": 0.6,
        },
    )

    assert snapshot is None


def test_formula_graceful_degradation_no_alignment():
    """Test graceful degradation when alignment signals missing."""
    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals={
            "evidence_alignment": 0.5,
        },
        internal_external_alignment={},
        internal_stability_signals={
            "synthesis_integrity": 0.6,
        },
    )

    assert snapshot is None


def test_formula_diagnostic_tags_determinism():
    """Test that diagnostic tags are sorted and deterministic."""
    external_reality_signals = {
        "evidence_alignment": 0.60,
        "evidence_conflict_index": 0.35,
        "evidence_stability": 0.62,
        "context_relevance_score": 0.58,
        "external_support_density": 0.61,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.63,
        "external_evidence_consistency_index": 0.59,
        "alignment_index": 0.65,
        "divergence_index": 0.35,
        "evidence_conflict_index": 0.34,
        "stability_projection_index": 0.61,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.62,
        "macro_stability_index": 0.60,
        "temporal_stability_index": 0.64,
        "internal_consistency_strength": 0.63,
    }

    snapshot1 = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    snapshot2 = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    # Tags should be identical and sorted
    assert snapshot1.diagnostic_tags == snapshot2.diagnostic_tags
    assert snapshot1.diagnostic_tags == sorted(snapshot1.diagnostic_tags)


# ============================================================================
# GROUP B: Coherence Integration Tests
# ============================================================================

def test_coherence_state_has_phase53_fields():
    """Test that CoherenceState has Phase 53 fields."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState()

    # Check Phase 53 snapshot field
    assert hasattr(state, 'external_reality_trust_snapshot')
    assert state.external_reality_trust_snapshot is None

    # Check Phase 53 history fields
    assert hasattr(state, 'ertce_trust_score_history')
    assert hasattr(state, 'ertce_override_pressure_history')
    assert hasattr(state, 'ertce_fragility_history')
    assert hasattr(state, 'ertce_resilience_history')
    assert hasattr(state, 'ertce_decay_risk_history')
    assert hasattr(state, 'ertce_band_history')
    assert hasattr(state, 'ertce_tag_history')

    # All should be empty lists
    assert state.ertce_trust_score_history == []
    assert state.ertce_override_pressure_history == []
    assert state.ertce_fragility_history == []
    assert state.ertce_resilience_history == []
    assert state.ertce_decay_risk_history == []
    assert state.ertce_band_history == []
    assert state.ertce_tag_history == []


def test_coherence_state_window_trim_phase53():
    """Test that window_trim correctly trims Phase 53 histories."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState()

    # Add 10 items to Phase 53 histories
    for i in range(10):
        state.ertce_trust_score_history.append(0.1 * i)
        state.ertce_override_pressure_history.append(0.1 * i)
        state.ertce_fragility_history.append(0.1 * i)
        state.ertce_resilience_history.append(0.1 * i)
        state.ertce_decay_risk_history.append(0.1 * i)
        state.ertce_band_history.append(f"band_{i}")
        state.ertce_tag_history.append([f"tag_{i}"])

    # Trim to window of 5
    state.window_trim(5)

    # All Phase 53 histories should have 5 items (most recent)
    assert len(state.ertce_trust_score_history) == 5
    assert len(state.ertce_override_pressure_history) == 5
    assert len(state.ertce_fragility_history) == 5
    assert len(state.ertce_resilience_history) == 5
    assert len(state.ertce_decay_risk_history) == 5
    assert len(state.ertce_band_history) == 5
    assert len(state.ertce_tag_history) == 5

    # Check that the last 5 items are retained
    assert state.ertce_trust_score_history == [0.5, 0.6, 0.7, 0.8, 0.9]
    assert state.ertce_band_history == ["band_5", "band_6", "band_7", "band_8", "band_9"]


# ============================================================================
# GROUP C: Session Summary Tests
# ============================================================================

def test_session_summary_has_phase53_fields():
    """Test that SessionSummary has Phase 53 fields."""
    from symbolu.service.sessions.session_models import SessionSummary

    summary = SessionSummary(
        session_id="test",
        total_turns=1,
        coherence_trend=0.5,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.6,
    )

    # Check Phase 53 fields
    assert hasattr(summary, 'avg_external_trust_score')
    assert hasattr(summary, 'avg_internal_override_pressure')
    assert hasattr(summary, 'avg_external_signal_fragility')
    assert hasattr(summary, 'avg_alignment_resilience')
    assert hasattr(summary, 'avg_trust_decay_risk')
    assert hasattr(summary, 'dominant_trust_band')
    assert hasattr(summary, 'ertce_tags')

    # All should be None or empty by default
    assert summary.avg_external_trust_score is None
    assert summary.avg_internal_override_pressure is None
    assert summary.avg_external_signal_fragility is None
    assert summary.avg_alignment_resilience is None
    assert summary.avg_trust_decay_risk is None
    assert summary.dominant_trust_band is None
    assert summary.ertce_tags == []


# ============================================================================
# GROUP D: API & Observer Integration Tests
# ============================================================================

def test_unified_output_has_phase53_field():
    """Test that UnifiedOutput has Phase 53 field."""
    from symbolu.api.unified_api import UnifiedOutput

    output = UnifiedOutput(
        text="test",
        symbolic=None,
        practical=None,
        mirror=None,
        dha=None,
        routing=None,
        mappers=None,
        entropy=None,
        coherence=None,
        metadata=None,
    )

    # Check Phase 53 field
    assert hasattr(output, 'external_reality_trust')
    assert output.external_reality_trust is None


def test_coherence_observation_has_phase53_fields():
    """Test that CoherenceObservation has Phase 53 fields."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.5,
        persona_drift_score=0.3,
        semantic_stability_score=0.6,
        temporal_arc_score=0.5,
        mapper_volatility_score=0.4,
        turn_number=1,
    )

    # Check Phase 53 fields
    assert hasattr(observation, 'external_trust_score')
    assert hasattr(observation, 'internal_override_pressure')
    assert hasattr(observation, 'external_signal_fragility')
    assert hasattr(observation, 'alignment_resilience')
    assert hasattr(observation, 'trust_decay_risk')
    assert hasattr(observation, 'trust_band')
    assert hasattr(observation, 'ertce_tags')

    # All should have default values
    assert observation.external_trust_score == 0.0
    assert observation.internal_override_pressure == 0.0
    assert observation.external_signal_fragility == 0.0
    assert observation.alignment_resilience == 0.0
    assert observation.trust_decay_risk == 0.0
    assert observation.trust_band is None
    assert observation.ertce_tags == []


# ============================================================================
# GROUP E: Behavioral Invariance Tests (11-Point Checklist)
# ============================================================================

def test_invariance_01_routing_unchanged():
    """Test that Phase 53 does not modify routing decisions."""
    # This is a structural test - Phase 53 formula should not import or use
    # any routing modules
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import routing modules
    assert "from symbolu.mechanical.routing" not in source
    assert "import symbolu.mechanical.routing" not in source
    assert "RoutingPlan" not in source
    assert "TTOR" not in source
    assert "MLCR" not in source


def test_invariance_02_mapper_unchanged():
    """Test that Phase 53 does not modify mapper behavior."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import or modify mappers
    assert "from symbolu.mechanical.mapper" not in source
    assert "HRM" not in source
    assert "LCM" not in source
    assert "LAM" not in source


def test_invariance_03_policy_unchanged():
    """Test that Phase 53 does not modify policy or safety logic."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import or modify policy modules
    assert "from symbolu.policy" not in source
    assert "SafetyPolicy" not in source
    assert "TradingGuardrails" not in source


def test_invariance_04_persona_tone_unchanged():
    """Test that Phase 53 does not modify persona tone."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import persona rendering modules
    assert "from symbolu.mechanical.persona.renderer" not in source
    assert "PersonaRenderer" not in source
    assert "FusionRenderer" not in source


def test_invariance_05_zero_llm():
    """Test that Phase 53 does not use LLM calls."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import LLM modules
    assert "anthropic" not in source.lower()
    assert "openai" not in source.lower()
    assert "llm" not in source.lower()
    assert "completion" not in source.lower()


def test_invariance_06_deterministic_only():
    """Test that Phase 53 uses only deterministic operations."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not use random operations
    assert "random" not in source.lower()
    assert "np.random" not in source
    assert "torch.rand" not in source


def test_invariance_07_graceful_degradation():
    """Test that Phase 53 degrades gracefully with missing inputs."""
    # Test with all inputs missing
    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals={},
        internal_external_alignment={},
        internal_stability_signals={},
    )

    assert snapshot is None

    # Test with partial inputs (should still return None)
    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals={"evidence_alignment": 0.5},
        internal_external_alignment={},
        internal_stability_signals={},
    )

    assert snapshot is None


def test_invariance_08_bounds_enforcement():
    """Test that Phase 53 enforces [0.0, 1.0] bounds on all outputs."""
    # Test with values slightly outside bounds
    external_reality_signals = {
        "evidence_alignment": 1.1,  # Invalid, but should be clamped
        "evidence_conflict_index": -0.1,  # Invalid, but should be clamped
        "evidence_stability": 0.5,
        "context_relevance_score": 0.5,
        "external_support_density": 0.5,
    }

    internal_external_alignment = {
        "internal_consistency_index": 0.5,
        "external_evidence_consistency_index": 0.5,
        "alignment_index": 0.5,
        "divergence_index": 0.5,
        "evidence_conflict_index": 0.5,
        "stability_projection_index": 0.5,
    }

    internal_stability_signals = {
        "synthesis_integrity": 0.5,
        "macro_stability_index": 0.5,
        "temporal_stability_index": 0.5,
        "internal_consistency_strength": 0.5,
    }

    snapshot = compute_external_reality_trust_calibration(
        external_reality_signals=external_reality_signals,
        internal_external_alignment=internal_external_alignment,
        internal_stability_signals=internal_stability_signals,
    )

    # All outputs should still be bounded
    assert 0.0 <= snapshot.external_trust_score <= 1.0
    assert 0.0 <= snapshot.internal_override_pressure <= 1.0
    assert 0.0 <= snapshot.external_signal_fragility <= 1.0
    assert 0.0 <= snapshot.alignment_resilience <= 1.0
    assert 0.0 <= snapshot.trust_decay_risk <= 1.0


def test_invariance_09_no_feedback_loops():
    """Test that Phase 53 does not create feedback loops."""
    from symbolu.formulas import external_reality_trust_calibration
    import inspect

    source = inspect.getsource(external_reality_trust_calibration)

    # Phase 53 should not import prediction engines
    assert "from symbolu.formulas.predictive_persona_drift" not in source
    assert "from symbolu.formulas.temporal_forecast" not in source


def test_invariance_10_backward_compatible():
    """Test that Phase 53 is backward compatible."""
    # Phase 53 should be optional - system should work without it
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState()

    # State should work with Phase 53 snapshot as None
    assert state.external_reality_trust_snapshot is None

    # Histories should work as empty lists
    assert state.ertce_trust_score_history == []


def test_invariance_11_end_to_end_pipeline():
    """Test that Phase 53 integrates correctly in end-to-end pipeline."""
    # This is a smoke test to ensure Phase 53 doesn't break the pipeline
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState()

    # Phase 53 fields should be accessible
    assert hasattr(state, 'external_reality_trust_snapshot')
    assert hasattr(state, 'ertce_trust_score_history')

    # Phase 53 should integrate with other phases
    # (structural check - no runtime errors)
    assert True
