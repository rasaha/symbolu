"""
Phase 52 Test Suite: Internal–External Reality Cross-Verification Engine (IER-CVE)

This test suite validates the Phase 52 IER-CVE implementation across:
1. Formula math and determinism
2. Coherence state integration
3. Session summary aggregation
4. API + Observer + Persona metadata
5. Behavioral invariance (no routing/mapper/policy changes)
"""

import pytest
from symbolu.formulas.internal_external_reality_cve import (
    compute_internal_external_reality_cve,
    InternalExternalRealityCVESnapshot,
)


# ============================================================================
# GROUP 1: Formula Math Tests
# ============================================================================

def test_formula_basic_computation():
    """Test basic IER-CVE formula computation with valid inputs."""
    internal_signals = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
        "continuity_stability": 0.75,
        "forecast_strength": 0.7,
        "future_stability_envelope": 0.65,
        "resonance_alignment_index": 0.7,
        "scenario_alignment": 0.68,
        "alignment_score": 0.72,
        "convergence_index": 0.71,
        "synthesis_integrity": 0.73,
        "macro_stability_index": 0.69,
        "temporal_stability_index": 0.74,
        "internal_consistency_strength": 0.76,
    }

    external_rag_validation = {
        "evidence_alignment": 0.70,
        "evidence_conflict_index": 0.25,
        "evidence_stability": 0.72,
        "context_relevance_score": 0.68,
        "external_support_density": 0.71,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    assert snapshot is not None
    assert isinstance(snapshot, InternalExternalRealityCVESnapshot)
    assert 0.0 <= snapshot.internal_consistency_index <= 1.0
    assert 0.0 <= snapshot.external_evidence_consistency_index <= 1.0
    assert 0.0 <= snapshot.alignment_index <= 1.0
    assert 0.0 <= snapshot.divergence_index <= 1.0
    assert 0.0 <= snapshot.evidence_conflict_index <= 1.0
    assert 0.0 <= snapshot.stability_projection_index <= 1.0
    assert snapshot.band in ["high_alignment", "medium_alignment", "low_alignment", "conflict"]
    assert isinstance(snapshot.diagnostic_tags, list)


def test_formula_determinism():
    """Test that formula produces deterministic results."""
    internal_signals = {
        "drift_magnitude": 0.3,
        "identity_drift_anchoring": 0.7,
        "continuity_stability": 0.65,
        "forecast_strength": 0.6,
        "future_stability_envelope": 0.55,
    }

    external_rag_validation = {
        "evidence_alignment": 0.60,
        "evidence_conflict_index": 0.35,
        "evidence_stability": 0.62,
        "context_relevance_score": 0.58,
        "external_support_density": 0.61,
    }

    # Compute twice
    snapshot1 = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    snapshot2 = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    # Results should be identical
    assert snapshot1.internal_consistency_index == snapshot2.internal_consistency_index
    assert snapshot1.external_evidence_consistency_index == snapshot2.external_evidence_consistency_index
    assert snapshot1.alignment_index == snapshot2.alignment_index
    assert snapshot1.divergence_index == snapshot2.divergence_index
    assert snapshot1.evidence_conflict_index == snapshot2.evidence_conflict_index
    assert snapshot1.stability_projection_index == snapshot2.stability_projection_index
    assert snapshot1.band == snapshot2.band
    assert snapshot1.diagnostic_tags == snapshot2.diagnostic_tags


def test_formula_graceful_degradation_no_external():
    """Test graceful degradation when external RAG validation is missing."""
    internal_signals = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
        "continuity_stability": 0.75,
        "forecast_strength": 0.7,
    }

    external_rag_validation = {}

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    # Should return None when external validation is missing
    assert snapshot is None


def test_formula_graceful_degradation_insufficient_internal():
    """Test graceful degradation when fewer than 3 internal signals."""
    internal_signals = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
    }

    external_rag_validation = {
        "evidence_alignment": 0.70,
        "evidence_conflict_index": 0.25,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    # Should return None when fewer than 3 internal signals
    assert snapshot is None


def test_formula_bounds():
    """Test that all formula outputs are bounded [0.0, 1.0]."""
    # Extreme high internal, low external
    internal_signals = {
        "drift_magnitude": 0.0,  # Inverted to 1.0
        "identity_drift_anchoring": 1.0,
        "continuity_stability": 1.0,
        "forecast_strength": 1.0,
        "future_stability_envelope": 1.0,
    }

    external_rag_validation = {
        "evidence_alignment": 0.0,
        "evidence_conflict_index": 1.0,
        "evidence_stability": 0.0,
        "context_relevance_score": 0.0,
        "external_support_density": 0.0,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    assert snapshot is not None
    assert 0.0 <= snapshot.internal_consistency_index <= 1.0
    assert 0.0 <= snapshot.external_evidence_consistency_index <= 1.0
    assert 0.0 <= snapshot.alignment_index <= 1.0
    assert 0.0 <= snapshot.divergence_index <= 1.0
    assert 0.0 <= snapshot.evidence_conflict_index <= 1.0
    assert 0.0 <= snapshot.stability_projection_index <= 1.0


def test_formula_band_classification():
    """Test band classification logic."""
    # Test high_alignment
    internal_signals = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
        "continuity_stability": 0.8,
        "forecast_strength": 0.8,
    }

    external_rag_validation = {
        "evidence_alignment": 0.80,
        "evidence_conflict_index": 0.15,
        "evidence_stability": 0.80,
        "context_relevance_score": 0.80,
        "external_support_density": 0.80,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    assert snapshot is not None
    assert snapshot.band == "high_alignment"


def test_formula_diagnostic_tags_determinism():
    """Test that diagnostic tags are deterministic (sorted and deduplicated)."""
    internal_signals = {
        "drift_magnitude": 0.1,
        "identity_drift_anchoring": 0.85,
        "continuity_stability": 0.82,
        "forecast_strength": 0.78,
        "future_stability_envelope": 0.80,
    }

    external_rag_validation = {
        "evidence_alignment": 0.82,
        "evidence_conflict_index": 0.18,
        "evidence_stability": 0.80,
        "context_relevance_score": 0.78,
        "external_support_density": 0.81,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    assert snapshot is not None
    assert isinstance(snapshot.diagnostic_tags, list)

    # Tags should be sorted
    assert snapshot.diagnostic_tags == sorted(snapshot.diagnostic_tags)

    # Tags should be unique
    assert len(snapshot.diagnostic_tags) == len(set(snapshot.diagnostic_tags))


# ============================================================================
# GROUP 2: Coherence Integration Tests
# ============================================================================

def test_coherence_state_fields_exist():
    """Test that Phase 52 fields exist in CoherenceState."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Check Phase 52 fields exist
    assert hasattr(state, 'internal_external_reality_snapshot')
    assert hasattr(state, 'ier_cve_alignment_history')
    assert hasattr(state, 'ier_cve_conflict_history')
    assert hasattr(state, 'ier_cve_stability_history')
    assert hasattr(state, 'ier_cve_band_history')
    assert hasattr(state, 'ier_cve_tag_history')

    # Initial values should be empty
    assert state.internal_external_reality_snapshot is None
    assert state.ier_cve_alignment_history == []
    assert state.ier_cve_conflict_history == []
    assert state.ier_cve_stability_history == []
    assert state.ier_cve_band_history == []
    assert state.ier_cve_tag_history == []


def test_coherence_state_window_trim():
    """Test that window_trim correctly trims Phase 52 histories."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=10,
    )

    # Populate histories
    state.ier_cve_alignment_history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    state.ier_cve_conflict_history = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    state.ier_cve_stability_history = [0.5, 0.5, 0.6, 0.6, 0.7, 0.7, 0.8, 0.8]
    state.ier_cve_band_history = ["a", "b", "c", "d", "e", "f", "g", "h"]
    state.ier_cve_tag_history = [[f"tag{i}"] for i in range(8)]

    # Trim to window of 3
    state.window_trim(window=3)

    # Check only last 3 entries remain
    assert state.ier_cve_alignment_history == [0.6, 0.7, 0.8]
    assert state.ier_cve_conflict_history == [0.3, 0.2, 0.1]
    assert state.ier_cve_stability_history == [0.7, 0.8, 0.8]
    assert state.ier_cve_band_history == ["f", "g", "h"]
    assert state.ier_cve_tag_history == [["tag5"], ["tag6"], ["tag7"]]


# ============================================================================
# GROUP 3: Session Summary Tests
# ============================================================================

def test_session_summary_fields_exist():
    """Test that Phase 52 fields exist in SessionSummary."""
    from symbolu.service.sessions.session_models import SessionSummary
    from datetime import datetime

    summary = SessionSummary(
        session_id="test_session",
        total_turns=5,
        coherence_trend=0.7,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.6,
        created_at=datetime.now(),
    )

    # Check Phase 52 fields exist
    assert hasattr(summary, 'avg_internal_external_alignment')
    assert hasattr(summary, 'avg_internal_external_conflict')
    assert hasattr(summary, 'avg_internal_external_stability')
    assert hasattr(summary, 'dominant_ier_cve_band')
    assert hasattr(summary, 'ier_cve_tags')

    # Initial values should be None/empty
    assert summary.avg_internal_external_alignment is None
    assert summary.avg_internal_external_conflict is None
    assert summary.avg_internal_external_stability is None
    assert summary.dominant_ier_cve_band is None
    assert summary.ier_cve_tags == []


# ============================================================================
# GROUP 4: API + Observer + Persona Tests
# ============================================================================

def test_unified_api_field_exists():
    """Test that Phase 52 field exists in UnifiedOutput."""
    from symbolu.api.unified_api import UnifiedOutput

    output = UnifiedOutput(
        text="test",
        symbolic={},
        practical={},
        mirror={},
        dha={},
        routing={},
        mappers={},
        entropy={},
        coherence={},
        metadata={},
    )

    # Check Phase 52 field exists
    assert hasattr(output, 'internal_external_reality_verification')
    assert output.internal_external_reality_verification is None


def test_coherence_observation_fields_exist():
    """Test that Phase 52 fields exist in CoherenceObservation."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.8,
        persona_drift_score=0.2,
        semantic_stability_score=0.7,
        temporal_arc_score=0.75,
        mapper_volatility_score=0.3,
        turn_number=1,
        tier="HYBRID",
        domain="test",
        active_mappers=["HRM"],
    )

    # Check Phase 52 fields exist
    assert hasattr(observation, 'internal_external_alignment')
    assert hasattr(observation, 'internal_external_conflict')
    assert hasattr(observation, 'internal_external_stability')
    assert hasattr(observation, 'internal_external_band')
    assert hasattr(observation, 'internal_external_tags')

    # Initial values should be 0.0/None/[]
    assert observation.internal_external_alignment == 0.0
    assert observation.internal_external_conflict == 0.0
    assert observation.internal_external_stability == 0.0
    assert observation.internal_external_band is None
    assert observation.internal_external_tags == []


def test_persona_response_field_exists():
    """Test that Phase 52 field exists in PersonaResponse."""
    from symbolu.mechanical.persona.models import PersonaResponse, PersonaMetadata

    response = PersonaResponse(
        persona_id="test",
        text="Test response",
        layers={"symbolic": {}, "practical": {}, "mirror": {}},
        metadata=PersonaMetadata(
            tier="HYBRID",
            domain="test",
            intent="how",
            persona_id="test",
            persona_name="Test",
            persona_description="Test persona",
            dha_tone="neutral",
            dha_confidence=0.8,
        ),
    )

    # Check Phase 52 field exists
    assert hasattr(response, 'persona_internal_external_alignment_profile')
    assert response.persona_internal_external_alignment_profile is None


# ============================================================================
# GROUP 5: Behavioral Invariance Tests (11-point checklist)
# ============================================================================

def test_invariant_no_routing_changes():
    """Invariant 1: IER-CVE does NOT modify routing logic."""
    # This is validated by code inspection - no imports from routing modules in IER-CVE formula
    from symbolu.formulas import internal_external_reality_cve
    import inspect

    source = inspect.getsource(internal_external_reality_cve)

    # Should NOT import routing modules
    assert "from symbolu.routing" not in source
    assert "import symbolu.routing" not in source


def test_invariant_no_mapper_changes():
    """Invariant 2: IER-CVE does NOT modify mapper logic."""
    from symbolu.formulas import internal_external_reality_cve
    import inspect

    source = inspect.getsource(internal_external_reality_cve)

    # Should NOT import mapper modules
    assert "from symbolu.mechanical.mapper" not in source
    assert "import symbolu.mechanical.mapper" not in source


def test_invariant_no_policy_changes():
    """Invariant 3: IER-CVE does NOT modify policy logic."""
    from symbolu.formulas import internal_external_reality_cve
    import inspect

    source = inspect.getsource(internal_external_reality_cve)

    # Should NOT import policy modules
    assert "from symbolu.policy" not in source
    assert "import symbolu.policy" not in source


def test_invariant_zero_llm():
    """Invariant 4: IER-CVE is zero-LLM (no LLM calls)."""
    from symbolu.formulas import internal_external_reality_cve
    import inspect
    import ast

    source = inspect.getsource(internal_external_reality_cve)

    # Parse and check imports (comments mentioning "zero-llm" are OK)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Get import names
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ''] + [alias.name for alias in node.names]
            for name in names:
                assert "openai" not in name.lower(), "IER-CVE must not import openai"
                assert "anthropic" not in name.lower(), "IER-CVE must not import anthropic"


def test_invariant_deterministic_math():
    """Invariant 5: IER-CVE uses deterministic math only."""
    from symbolu.formulas import internal_external_reality_cve
    import inspect

    source = inspect.getsource(internal_external_reality_cve)

    # Should NOT use random functions
    assert "random" not in source.lower()
    assert "shuffle" not in source.lower()


def test_invariant_bounded_outputs():
    """Invariant 6: All IER-CVE outputs are bounded [0.0, 1.0]."""
    # Test with many random inputs
    import random

    for _ in range(10):
        internal_signals = {
            f"signal_{i}": random.random() for i in range(5)
        }

        external_rag_validation = {
            f"metric_{i}": random.random() for i in range(3)
        }

        snapshot = compute_internal_external_reality_cve(
            internal_signals=internal_signals,
            external_rag_validation=external_rag_validation,
        )

        if snapshot is not None:
            assert 0.0 <= snapshot.internal_consistency_index <= 1.0
            assert 0.0 <= snapshot.external_evidence_consistency_index <= 1.0
            assert 0.0 <= snapshot.alignment_index <= 1.0
            assert 0.0 <= snapshot.divergence_index <= 1.0
            assert 0.0 <= snapshot.evidence_conflict_index <= 1.0
            assert 0.0 <= snapshot.stability_projection_index <= 1.0


def test_invariant_observation_only():
    """Invariant 7: IER-CVE is observation-only (no side effects)."""
    internal_signals_original = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
        "continuity_stability": 0.75,
        "forecast_strength": 0.7,
    }

    external_rag_validation_original = {
        "evidence_alignment": 0.70,
        "evidence_conflict_index": 0.25,
    }

    # Make copies
    internal_signals = internal_signals_original.copy()
    external_rag_validation = external_rag_validation_original.copy()

    # Compute formula
    compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    # Input dictionaries should NOT be modified
    assert internal_signals == internal_signals_original
    assert external_rag_validation == external_rag_validation_original


def test_invariant_backward_compatible():
    """Invariant 8: Phase 52 is backward-compatible (does not break existing code)."""
    # CoherenceState should still work without Phase 52 data
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Should be able to use CoherenceState without Phase 52 fields
    state.coherence_score = 0.8
    state.persona_drift_score = 0.2

    assert state.coherence_score == 0.8
    assert state.persona_drift_score == 0.2


def test_invariant_graceful_none_handling():
    """Invariant 9: IER-CVE gracefully handles None/missing data."""
    # Test with None inputs
    snapshot = compute_internal_external_reality_cve(
        internal_signals={},
        external_rag_validation={},
    )

    assert snapshot is None


def test_invariant_json_serializable():
    """Invariant 10: All IER-CVE outputs are JSON-serializable."""
    import json

    internal_signals = {
        "drift_magnitude": 0.2,
        "identity_drift_anchoring": 0.8,
        "continuity_stability": 0.75,
        "forecast_strength": 0.7,
    }

    external_rag_validation = {
        "evidence_alignment": 0.70,
        "evidence_conflict_index": 0.25,
        "evidence_stability": 0.72,
        "context_relevance_score": 0.68,
        "external_support_density": 0.71,
    }

    snapshot = compute_internal_external_reality_cve(
        internal_signals=internal_signals,
        external_rag_validation=external_rag_validation,
    )

    if snapshot is not None:
        # Convert to dict
        snapshot_dict = {
            "internal_consistency_index": snapshot.internal_consistency_index,
            "external_evidence_consistency_index": snapshot.external_evidence_consistency_index,
            "alignment_index": snapshot.alignment_index,
            "divergence_index": snapshot.divergence_index,
            "evidence_conflict_index": snapshot.evidence_conflict_index,
            "stability_projection_index": snapshot.stability_projection_index,
            "band": snapshot.band,
            "diagnostic_tags": snapshot.diagnostic_tags,
        }

        # Should be JSON-serializable
        json_str = json.dumps(snapshot_dict)
        assert isinstance(json_str, str)


def test_invariant_no_external_dependencies():
    """Invariant 11: IER-CVE has no external dependencies (only stdlib + symbolu)."""
    from symbolu.formulas import internal_external_reality_cve
    import inspect

    source = inspect.getsource(internal_external_reality_cve)

    # Should NOT import external libraries (except standard library)
    forbidden_imports = ["numpy", "pandas", "torch", "tensorflow", "sklearn", "scipy"]
    for lib in forbidden_imports:
        assert lib not in source.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
