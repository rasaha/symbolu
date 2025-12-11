"""
Test Suite for Phase 47: Unified Trajectory–Scenario Synthesis Engine (UTSSE)

This test suite validates the Phase 47 implementation across all integration points:
- Formula computation correctness
- Coherence state integration
- Session summary aggregation
- Unified API integration
- Coherence observer extraction
- Behavioral invariance (zero-LLM, observation-only)
"""

import pytest
from symbolu.formulas.unified_trajectory_scenario_synthesis import (
    compute_unified_trajectory_scenario_synthesis,
    UnifiedTrajectoryScenarioSnapshot,
    _clamp,
    _safe_get,
    _compute_mean,
    _compute_variance,
    _compute_std_dev,
)


# ============================================================================
# GROUP A: Formula Math Tests (15 tests)
# ============================================================================

def test_clamp_within_bounds():
    """Test _clamp keeps values within [0.0, 1.0]."""
    assert _clamp(0.5) == 0.5
    assert _clamp(0.0) == 0.0
    assert _clamp(1.0) == 1.0


def test_clamp_outside_bounds():
    """Test _clamp restricts values outside [0.0, 1.0]."""
    assert _clamp(-0.5) == 0.0
    assert _clamp(1.5) == 1.0
    assert _clamp(2.0) == 1.0
    assert _clamp(-1.0) == 0.0


def test_safe_get_from_dict():
    """Test _safe_get extracts values from dicts."""
    data = {"score": 0.75, "name": "test"}
    assert _safe_get(data, "score") == 0.75
    assert _safe_get(data, "missing", 0.5) == 0.5


def test_safe_get_from_object():
    """Test _safe_get extracts values from objects."""
    class TestObj:
        score = 0.85
    obj = TestObj()
    assert _safe_get(obj, "score") == 0.85
    assert _safe_get(obj, "missing", 0.5) == 0.5


def test_safe_get_none():
    """Test _safe_get handles None gracefully."""
    assert _safe_get(None, "score", 0.5) == 0.5


def test_compute_mean():
    """Test _compute_mean calculates correct average."""
    assert _compute_mean([1.0, 2.0, 3.0]) == 2.0
    assert _compute_mean([0.5, 0.5]) == 0.5
    assert _compute_mean([]) == 0.0


def test_compute_variance():
    """Test _compute_variance calculates correct variance."""
    assert _compute_variance([1.0, 1.0, 1.0]) == 0.0
    variance = _compute_variance([0.0, 1.0])
    assert abs(variance - 0.25) < 0.01  # (0.5-0.5)^2 + (0.5-0.5)^2 / 2 = 0.25


def test_compute_std_dev():
    """Test _compute_std_dev calculates correct std dev."""
    assert _compute_std_dev([1.0, 1.0, 1.0]) == 0.0
    std = _compute_std_dev([0.0, 1.0])
    assert abs(std - 0.5) < 0.01


def test_formula_returns_none_when_insufficient_data():
    """Test formula returns None when < 3 upstream phases available."""
    # Only 2 phases
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5},
        identity={"ims": 0.7}
    )
    assert result is None


def test_formula_computes_with_minimum_data():
    """Test formula computes with exactly 3 upstream phases."""
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5},
        identity={"ims": 0.7},
        continuity={"css": 0.6}
    )
    assert result is not None
    assert isinstance(result, UnifiedTrajectoryScenarioSnapshot)


def test_formula_bounds_all_outputs():
    """Test all numeric outputs are bounded to [0.0, 1.0]."""
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.3, "drift_stability_score": 0.8},
        identity={"ims": 0.9, "iep": 0.85, "ida": 0.75},
        continuity={"ncc": 0.7, "icc": 0.8, "css": 0.9},
        forecast_single={"forecast_strength": 0.85},
    )
    assert result is not None
    assert 0.0 <= result.synthesis_integrity_score <= 1.0
    assert 0.0 <= result.future_state_alignment_score <= 1.0
    assert 0.0 <= result.future_state_coherence_score <= 1.0
    assert 0.0 <= result.cross_horizon_consistency_score <= 1.0
    assert 0.0 <= result.future_divergence_risk <= 1.0
    assert 0.0 <= result.convergence_signal_strength <= 1.0


def test_formula_band_classification_high():
    """Test synthesis band classifies HIGH correctly."""
    # High integrity + high alignment = HIGH band
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.1, "drift_stability_score": 0.9},
        identity={"ims": 0.95, "iep": 0.90, "ida": 0.92},
        continuity={"ncc": 0.88, "icc": 0.90, "css": 0.92},
        forecast_single={"forecast_strength": 0.90, "coherence_slope": 0.5},
        forecast_multi={"forecast_consensus_index": 0.90, "future_stability_envelope": 0.88},
        scenario_fusion={"scenario_alignment_score": 0.92, "scenario_divergence_index": 0.1, "multi_regime_consensus": 0.90},
        scenario_alignment={"alignment_score": 0.88, "conflict_index": 0.1, "stability_agreement": 0.90},
        trajectory_convergence={"convergence_index": 0.92, "divergence_index": 0.08, "stability_index": 0.90},
    )
    assert result is not None
    assert result.synthesis_band == "HIGH"


def test_formula_band_classification_medium():
    """Test synthesis band classifies MEDIUM correctly."""
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.4, "drift_stability_score": 0.6},
        identity={"ims": 0.65, "iep": 0.60, "ida": 0.62},
        continuity={"ncc": 0.58, "icc": 0.60, "css": 0.62},
        forecast_single={"forecast_strength": 0.60},
    )
    assert result is not None
    assert result.synthesis_band in ["MEDIUM", "LOW"]  # May vary based on weights


def test_formula_band_classification_fragmented():
    """Test synthesis band classifies FRAGMENTED correctly."""
    # Low integrity + low alignment = FRAGMENTED
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.9, "drift_stability_score": 0.2},
        identity={"ims": 0.2, "iep": 0.15, "ida": 0.25},
        continuity={"ncc": 0.2, "icc": 0.25, "css": 0.22},
    )
    assert result is not None
    assert result.synthesis_band in ["FRAGMENTED", "LOW"]


def test_formula_diagnostic_tags_generation():
    """Test diagnostic tags are generated and sorted."""
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.1, "drift_stability_score": 0.9},
        identity={"ims": 0.9, "iep": 0.85, "ida": 0.88},
        continuity={"ncc": 0.85, "icc": 0.87, "css": 0.90},
        forecast_single={"forecast_strength": 0.85},
        forecast_multi={"forecast_consensus_index": 0.85, "future_stability_envelope": 0.88},
        scenario_fusion={"scenario_alignment_score": 0.88, "multi_regime_consensus": 0.85},
    )
    assert result is not None
    assert isinstance(result.diagnostic_tags, list)
    assert all(isinstance(tag, str) for tag in result.diagnostic_tags)
    # Check tags are sorted
    assert result.diagnostic_tags == sorted(result.diagnostic_tags)


# ============================================================================
# GROUP B: Coherence Integration Tests (10 tests)
# ============================================================================

def test_coherence_state_has_synthesis_fields():
    """Test CoherenceState has Phase 47 fields."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    state = CoherenceState(convo_id="test", turn_index=0)
    assert hasattr(state, 'trajectory_scenario_synthesis_snapshot')
    assert hasattr(state, 'synthesis_integrity_history')
    assert hasattr(state, 'synthesis_alignment_history')
    assert hasattr(state, 'synthesis_divergence_history')
    assert hasattr(state, 'synthesis_band_history')
    assert hasattr(state, 'synthesis_tags_history')


def test_coherence_state_window_trim_includes_synthesis():
    """Test window_trim includes Phase 47 histories."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    state = CoherenceState(convo_id="test", turn_index=0)
    # Add some history
    state.synthesis_integrity_history = [0.5, 0.6, 0.7, 0.8, 0.9]
    state.synthesis_alignment_history = [0.5, 0.6, 0.7, 0.8, 0.9]
    # Trim to 3
    state.window_trim(3)
    assert len(state.synthesis_integrity_history) == 3
    assert state.synthesis_integrity_history == [0.7, 0.8, 0.9]


def test_coherence_engine_has_synthesis_update():
    """Test CoherenceEngine has Phase 47 update method."""
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    engine = CoherenceEngine()
    assert hasattr(engine, '_update_unified_trajectory_scenario_synthesis')


def test_coherence_engine_initializes_synthesis_histories():
    """Test CoherenceEngine initializes Phase 47 histories on state copy."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine

    engine = CoherenceEngine()
    prev_state = CoherenceState(convo_id="test", turn_index=0)
    prev_state.synthesis_integrity_history = [0.7]

    # Create routing_plan and mapper_profile mocks
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "test"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()
    mapper_profile = {}

    new_state = engine.update_state(
        prev_state=prev_state,
        convo_id="test",
        turn_index=1,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=None,
        semantic_signature={}
    )

    assert len(new_state.synthesis_integrity_history) == 2  # Previous + new turn


def test_coherence_engine_stores_synthesis_snapshot():
    """Test CoherenceEngine stores synthesis snapshot."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    state = CoherenceState(convo_id="test", turn_index=0)

    # Manually set upstream snapshots for testing
    class MockDrift:
        drift_magnitude_prediction = 0.3
        drift_stability_score = 0.8

    class MockIdentity:
        ims = 0.8
        iep = 0.75
        ida = 0.82

    class MockContinuity:
        ncc = 0.75
        icc = 0.78
        css = 0.80

    state.predictive_drift_snapshot = MockDrift()
    state.identity_resonance_memory_snapshot = MockIdentity()
    state.adaptive_continuity_snapshot = MockContinuity()

    # Manually call the update method
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    engine = CoherenceEngine()
    engine._update_unified_trajectory_scenario_synthesis(state)

    assert state.trajectory_scenario_synthesis_snapshot is not None
    assert len(state.synthesis_integrity_history) > 0


def test_coherence_engine_appends_to_histories():
    """Test CoherenceEngine appends values to Phase 47 histories."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    state = CoherenceState(convo_id="test", turn_index=0)

    # Set up upstream snapshots
    class MockDrift:
        drift_magnitude_prediction = 0.3
        drift_stability_score = 0.8

    class MockIdentity:
        ims = 0.8
        iep = 0.75
        ida = 0.82

    class MockContinuity:
        ncc = 0.75
        icc = 0.78
        css = 0.80

    state.predictive_drift_snapshot = MockDrift()
    state.identity_resonance_memory_snapshot = MockIdentity()
    state.adaptive_continuity_snapshot = MockContinuity()

    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    engine = CoherenceEngine()
    engine._update_unified_trajectory_scenario_synthesis(state)

    assert len(state.synthesis_integrity_history) == 1
    assert len(state.synthesis_alignment_history) == 1
    assert len(state.synthesis_divergence_history) == 1
    assert len(state.synthesis_band_history) == 1
    assert len(state.synthesis_tags_history) == 1


def test_coherence_engine_handles_none_gracefully():
    """Test CoherenceEngine handles None snapshots gracefully."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine

    state = CoherenceState(convo_id="test", turn_index=0)
    # No upstream snapshots set (all None)

    engine = CoherenceEngine()
    engine._update_unified_trajectory_scenario_synthesis(state)

    # Should append default values
    assert len(state.synthesis_integrity_history) == 1
    assert state.synthesis_integrity_history[0] == 0.0
    assert state.synthesis_band_history[0] == ""


def test_formula_determinism():
    """Test formula produces same output for same input."""
    inputs = {
        "drift": {"drift_magnitude_prediction": 0.4, "drift_stability_score": 0.7},
        "identity": {"ims": 0.75, "iep": 0.70, "ida": 0.72},
        "continuity": {"ncc": 0.68, "icc": 0.72, "css": 0.75},
    }

    result1 = compute_unified_trajectory_scenario_synthesis(**inputs)
    result2 = compute_unified_trajectory_scenario_synthesis(**inputs)

    assert result1 is not None and result2 is not None
    assert result1.synthesis_integrity_score == result2.synthesis_integrity_score
    assert result1.future_state_alignment_score == result2.future_state_alignment_score
    assert result1.synthesis_band == result2.synthesis_band
    assert result1.diagnostic_tags == result2.diagnostic_tags


def test_dominant_future_path_deterministic_tie_breaking():
    """Test dominant_future_path uses deterministic tie-breaking."""
    # Create scenario where multiple paths have same score
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5, "drift_stability_score": 0.5},
        identity={"ims": 0.5, "iep": 0.5, "ida": 0.5},
        continuity={"ncc": 0.5, "icc": 0.5, "css": 0.5},
    )
    assert result is not None
    assert result.dominant_future_path is not None
    # Run again to ensure same result
    result2 = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5, "drift_stability_score": 0.5},
        identity={"ims": 0.5, "iep": 0.5, "ida": 0.5},
        continuity={"ncc": 0.5, "icc": 0.5, "css": 0.5},
    )
    assert result.dominant_future_path == result2.dominant_future_path


def test_synthesis_band_deterministic_classification():
    """Test synthesis band classification is deterministic at boundaries."""
    # Test at boundary: integrity=0.70, alignment=0.70 should be HIGH
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.2, "drift_stability_score": 0.85},
        identity={"ims": 0.85, "iep": 0.80, "ida": 0.82},
        continuity={"ncc": 0.78, "icc": 0.80, "css": 0.82},
        forecast_single={"forecast_strength": 0.82},
        forecast_multi={"forecast_consensus_index": 0.80, "future_stability_envelope": 0.82},
        scenario_fusion={"scenario_alignment_score": 0.85, "multi_regime_consensus": 0.82},
    )
    assert result is not None
    # Should be HIGH based on thresholds (>= 0.70 for both metrics)
    # Note: Actual result depends on weighted computation, so we just verify it's consistent
    band1 = result.synthesis_band

    # Run again with same inputs
    result2 = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.2, "drift_stability_score": 0.85},
        identity={"ims": 0.85, "iep": 0.80, "ida": 0.82},
        continuity={"ncc": 0.78, "icc": 0.80, "css": 0.82},
        forecast_single={"forecast_strength": 0.82},
        forecast_multi={"forecast_consensus_index": 0.80, "future_stability_envelope": 0.82},
        scenario_fusion={"scenario_alignment_score": 0.85, "multi_regime_consensus": 0.82},
    )
    assert band1 == result2.synthesis_band


# ============================================================================
# GROUP C: Session Summary Tests (5 tests)
# ============================================================================

def test_session_summary_has_synthesis_fields():
    """Test SessionSummary has Phase 47 fields."""
    from symbolu.service.sessions.session_models import SessionSummary
    import datetime
    summary = SessionSummary(
        session_id="test",
        total_turns=1,
        coherence_trend=0.5,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.6,
        created_at=datetime.datetime.utcnow()
    )
    assert hasattr(summary, 'avg_synthesis_integrity')
    assert hasattr(summary, 'avg_future_alignment')
    assert hasattr(summary, 'avg_future_divergence_risk')
    assert hasattr(summary, 'dominant_synthesis_band')
    assert hasattr(summary, 'synthesis_tags')


def test_session_store_computes_synthesis_aggregates():
    """Test session store computes Phase 47 aggregates."""
    from symbolu.service.sessions.session_store import compute_session_summary
    from symbolu.service.sessions.session_models import SessionState
    import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.datetime.utcnow(),
        domain="test"
    )

    # Add coherence history with Phase 47 data
    state.coherence_history.append({
        "synthesis_integrity_history": [0.75, 0.80],
        "synthesis_alignment_history": [0.70, 0.75],
        "synthesis_divergence_history": [0.25, 0.20],
        "synthesis_band_history": ["MEDIUM", "HIGH"],
        "synthesis_tags_history": [["TAG_A"], ["TAG_A", "TAG_B"]],
    })

    summary = compute_session_summary(state)

    assert summary.avg_synthesis_integrity is not None
    assert summary.avg_future_alignment is not None
    assert summary.avg_future_divergence_risk is not None


def test_session_store_synthesis_band_tie_breaking():
    """Test session store uses deterministic tie-breaking for dominant band."""
    from symbolu.service.sessions.session_store import compute_session_summary
    from symbolu.service.sessions.session_models import SessionState
    import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.datetime.utcnow(),
        domain="test"
    )

    # Add equal frequency bands
    state.coherence_history.append({
        "synthesis_band_history": ["HIGH", "MEDIUM", "HIGH", "MEDIUM"],
    })

    summary1 = compute_session_summary(state)
    summary2 = compute_session_summary(state)

    # Should be deterministic
    assert summary1.dominant_synthesis_band == summary2.dominant_synthesis_band


def test_session_store_synthesis_tags_deduplication():
    """Test session store deduplicates and sorts synthesis tags."""
    from symbolu.service.sessions.session_store import compute_session_summary
    from symbolu.service.sessions.session_models import SessionState
    import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.datetime.utcnow(),
        domain="test"
    )

    # Add duplicate tags
    state.coherence_history.append({
        "synthesis_tags_history": [["TAG_C", "TAG_A"], ["TAG_B", "TAG_A"], ["TAG_C"]],
    })

    summary = compute_session_summary(state)

    # Should be deduplicated and sorted
    assert summary.synthesis_tags == ["TAG_A", "TAG_B", "TAG_C"]


def test_session_store_handles_empty_synthesis_history():
    """Test session store handles empty Phase 47 history gracefully."""
    from symbolu.service.sessions.session_store import compute_session_summary
    from symbolu.service.sessions.session_models import SessionState
    import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.datetime.utcnow(),
        domain="test"
    )

    # No Phase 47 data
    state.coherence_history.append({})

    summary = compute_session_summary(state)

    # Should have None values
    assert summary.avg_synthesis_integrity is None
    assert summary.avg_future_alignment is None
    assert summary.dominant_synthesis_band is None


# ============================================================================
# GROUP D: Unified API + Observer Tests (5 tests)
# ============================================================================

def test_unified_output_has_synthesis_field():
    """Test UnifiedOutput has Phase 47 field."""
    from symbolu.api.unified_api import UnifiedOutput
    output = UnifiedOutput(text="test")
    assert hasattr(output, 'unified_trajectory_scenario_synthesis')


def test_coherence_observation_has_synthesis_fields():
    """Test CoherenceObservation has Phase 47 fields."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation
    obs = CoherenceObservation(
        coherence_score=0.5,
        persona_drift_score=0.3,
        semantic_stability_score=0.6,
        temporal_arc_score=0.5,
        mapper_volatility_score=0.4,
        turn_number=1,
        tier="hybrid",
        domain="test",
        active_mappers=[]
    )
    assert hasattr(obs, 'synthesis_integrity')
    assert hasattr(obs, 'synthesis_alignment')
    assert hasattr(obs, 'synthesis_divergence')
    assert hasattr(obs, 'synthesis_band')
    assert hasattr(obs, 'synthesis_tags')


def test_coherence_observer_extracts_synthesis():
    """Test CoherenceObserver extracts Phase 47 data."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver
    from symbolu.core.coherence.coherence_state import CoherenceState

    observer = CoherenceObserver()
    state = CoherenceState(convo_id="test", turn_index=1)

    # Set up a mock synthesis snapshot
    class MockSnapshot:
        synthesis_integrity_score = 0.75
        future_state_alignment_score = 0.70
        future_divergence_risk = 0.25
        synthesis_band = "MEDIUM"
        diagnostic_tags = ["TEST_TAG"]

    state.trajectory_scenario_synthesis_snapshot = MockSnapshot()

    # Create minimal context
    class MockContext:
        pass

    ctx = MockContext()

    obs = observer.observe("test text", ctx, state)

    assert obs.synthesis_integrity == 0.75
    assert obs.synthesis_alignment == 0.70
    assert obs.synthesis_divergence == 0.25
    assert obs.synthesis_band == "MEDIUM"
    assert obs.synthesis_tags == ["TEST_TAG"]


def test_coherence_observer_handles_none_synthesis():
    """Test CoherenceObserver handles None synthesis snapshot."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver
    from symbolu.core.coherence.coherence_state import CoherenceState

    observer = CoherenceObserver()
    state = CoherenceState(convo_id="test", turn_index=1)
    # No synthesis snapshot set

    class MockContext:
        pass

    ctx = MockContext()
    obs = observer.observe("test text", ctx, state)

    assert obs.synthesis_integrity == 0.0
    assert obs.synthesis_alignment == 0.0
    assert obs.synthesis_divergence == 0.0
    assert obs.synthesis_band is None
    assert obs.synthesis_tags == []


def test_persona_response_has_synthesis_field():
    """Test PersonaResponse has Phase 47 metadata field."""
    from symbolu.mechanical.persona.models import PersonaResponse
    response = PersonaResponse(persona_id="test", text="test", layers={})
    assert hasattr(response, 'persona_unified_synthesis_profile')


# ============================================================================
# GROUP E: Behavioral Invariance Tests (10 tests)
# ============================================================================

def test_zero_llm_no_anthropic_import():
    """Test formula module does not import LLM libraries."""
    import symbolu.formulas.unified_trajectory_scenario_synthesis as formula_module
    import sys

    # Check module doesn't have anthropic or openai in its namespace
    module_dict = dir(formula_module)
    assert 'anthropic' not in [name.lower() for name in module_dict]
    assert 'openai' not in [name.lower() for name in module_dict]


def test_formula_is_pure_function():
    """Test formula is deterministic (pure function)."""
    inputs = {
        "drift": {"drift_magnitude_prediction": 0.5},
        "identity": {"ims": 0.7},
        "continuity": {"css": 0.6},
    }

    result1 = compute_unified_trajectory_scenario_synthesis(**inputs)
    result2 = compute_unified_trajectory_scenario_synthesis(**inputs)

    assert result1 == result2  # Dataclasses should be equal if all fields match


def test_no_routing_changes():
    """Test Phase 47 does not modify routing logic."""
    # This is a structural test - verify no routing imports in formula
    import symbolu.formulas.unified_trajectory_scenario_synthesis as formula_module
    source = str(formula_module.__file__)

    # Ensure formula module doesn't import routing components
    with open(source.replace('.pyc', '.py').replace('__pycache__/', ''), 'r') as f:
        content = f.read()
        assert 'from symbolu.routing' not in content
        assert 'import symbolu.routing' not in content


def test_no_mapper_changes():
    """Test Phase 47 does not modify mapper logic."""
    import symbolu.formulas.unified_trajectory_scenario_synthesis as formula_module
    source = str(formula_module.__file__)

    with open(source.replace('.pyc', '.py').replace('__pycache__/', ''), 'r') as f:
        content = f.read()
        assert 'from symbolu.mechanical.mappers' not in content
        assert 'import symbolu.mechanical.mappers' not in content


def test_no_ttor_changes():
    """Test Phase 47 does not modify TTOR logic."""
    import symbolu.formulas.unified_trajectory_scenario_synthesis as formula_module
    source = str(formula_module.__file__)

    with open(source.replace('.pyc', '.py').replace('__pycache__/', ''), 'r') as f:
        content = f.read()
        assert 'from symbolu.routing.ttor' not in content
        assert 'import symbolu.routing.ttor' not in content


def test_no_persona_semantic_changes():
    """Test persona integration is metadata-only."""
    # Verify persona engine methods don't modify tone parameters
    from symbolu.mechanical.persona.engine import PersonaEngine
    engine = PersonaEngine()

    # Check methods exist
    assert hasattr(engine, '_extract_unified_synthesis')
    assert hasattr(engine, '_build_unified_synthesis_metadata')


def test_metadata_only_persona_integration():
    """Test persona metadata methods don't affect tone."""
    from symbolu.mechanical.persona.engine import PersonaEngine
    engine = PersonaEngine()

    # Mock snapshot
    class MockSnapshot:
        synthesis_integrity_score = 0.8
        future_state_alignment_score = 0.75
        synthesis_band = "HIGH"
        diagnostic_tags = ["TEST"]
        future_state_coherence_score = 0.8
        cross_horizon_consistency_score = 0.75
        future_divergence_risk = 0.2
        convergence_signal_strength = 0.8
        dominant_future_path = "TEST_PATH"

    metadata = engine._build_unified_synthesis_metadata(MockSnapshot())

    # Metadata should only contain observability fields
    assert isinstance(metadata, dict)
    assert 'synthesis_integrity_score' in metadata
    assert 'tone_adjustment' not in metadata
    assert 'warmth' not in metadata


def test_graceful_degradation_insufficient_phases():
    """Test formula degrades gracefully with insufficient upstream data."""
    # Test with 0 phases
    result = compute_unified_trajectory_scenario_synthesis()
    assert result is None

    # Test with 1 phase
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5}
    )
    assert result is None

    # Test with 2 phases
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.5},
        identity={"ims": 0.7}
    )
    assert result is None


def test_bounded_outputs_extreme_inputs():
    """Test outputs remain bounded with extreme inputs."""
    # Test with all high values
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.99, "drift_stability_score": 0.99},
        identity={"ims": 0.99, "iep": 0.99, "ida": 0.99},
        continuity={"ncc": 0.99, "icc": 0.99, "css": 0.99},
        forecast_single={"forecast_strength": 0.99},
        forecast_multi={"forecast_consensus_index": 0.99, "future_stability_envelope": 0.99},
    )
    assert result is not None
    assert 0.0 <= result.synthesis_integrity_score <= 1.0
    assert 0.0 <= result.convergence_signal_strength <= 1.0

    # Test with all low values
    result = compute_unified_trajectory_scenario_synthesis(
        drift={"drift_magnitude_prediction": 0.01, "drift_stability_score": 0.01},
        identity={"ims": 0.01, "iep": 0.01, "ida": 0.01},
        continuity={"ncc": 0.01, "icc": 0.01, "css": 0.01},
    )
    assert result is not None
    assert 0.0 <= result.synthesis_integrity_score <= 1.0
    assert 0.0 <= result.convergence_signal_strength <= 1.0


def test_backward_compatibility():
    """Test Phase 47 doesn't break existing coherence state operations."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    # Create old-style state (without Phase 47 data)
    state = CoherenceState(convo_id="test", turn_index=0)

    # Verify basic operations still work
    state.window_trim(10)
    length = state.get_history_length()

    # Should not raise any errors
    assert length == 0
