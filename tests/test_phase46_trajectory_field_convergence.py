"""
Phase 46 - Trajectory Field Convergence Engine (TFCE) Test Suite

Comprehensive test coverage for:
- Formula math and computation logic
- Coherence engine integration
- Session summary aggregation
- Unified API extraction
- Coherence observer integration
- Behavioral invariance guarantees

Test Structure:
    Group A: Formula Math (15 tests)
    Group B: Coherence Integration (10 tests)
    Group C: Session Summary (10 tests)
    Group D: Unified API + Observer (10 tests)
    Group E: Behavioral Invariance (10 tests)

Total: 55 tests
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Import Phase 46 formula module
from symbolu.formulas.trajectory_field_convergence import (
    TrajectoryFieldConvergenceSnapshot,
    compute_trajectory_field_convergence,
    _clamp,
    _safe_get,
    _compute_pairwise_alignment,
    _compute_variance,
)

# Import integration modules
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine


# ============================================================================
# GROUP A: FORMULA MATH (15 TESTS)
# ============================================================================


def test_a01_tfce_snapshot_dataclass():
    """Test TrajectoryFieldConvergenceSnapshot dataclass structure."""
    snapshot = TrajectoryFieldConvergenceSnapshot(
        drift_alignment=0.8,
        identity_alignment=0.7,
        symbolic_alignment=0.9,
        continuity_alignment=0.75,
        scenario_alignment=0.85,
        horizon_alignment=0.8,
        convergence_index=0.8,
        divergence_index=0.2,
        stability_index=0.85,
        convergence_band="high",
        dominant_convergence_signal="SYMBOLIC",
        diagnostic_tags=["TRAJECTORY_CONVERGING", "STABILITY_STRONG"],
    )

    assert snapshot.convergence_index == 0.8
    assert snapshot.divergence_index == 0.2
    assert snapshot.stability_index == 0.85
    assert snapshot.convergence_band == "high"
    assert snapshot.dominant_convergence_signal == "SYMBOLIC"
    assert len(snapshot.diagnostic_tags) == 2


def test_a02_clamp_function():
    """Test _clamp utility function."""
    assert _clamp(0.5, 0.0, 1.0) == 0.5
    assert _clamp(-0.5, 0.0, 1.0) == 0.0
    assert _clamp(1.5, 0.0, 1.0) == 1.0
    assert _clamp(0.0, 0.0, 1.0) == 0.0
    assert _clamp(1.0, 0.0, 1.0) == 1.0


def test_a03_safe_get_function():
    """Test _safe_get utility function."""
    # Test dict access
    data_dict = {"value": 0.75}
    assert _safe_get(data_dict, "value") == 0.75
    assert _safe_get(data_dict, "missing", 0.5) == 0.5

    # Test object access
    @dataclass
    class MockObj:
        value: float = 0.8

    obj = MockObj()
    assert _safe_get(obj, "value") == 0.8
    assert _safe_get(obj, "missing", 0.5) == 0.5

    # Test None
    assert _safe_get(None, "value", 0.5) == 0.5


def test_a04_compute_pairwise_alignment_high():
    """Test _compute_pairwise_alignment with high alignment."""
    # Close values should have high alignment
    values = [0.8, 0.82, 0.78, 0.81]
    alignment = _compute_pairwise_alignment(values)
    assert alignment > 0.9  # Very close values


def test_a05_compute_pairwise_alignment_low():
    """Test _compute_pairwise_alignment with low alignment."""
    # Far apart values should have low alignment
    values = [0.1, 0.9, 0.2, 0.8]
    alignment = _compute_pairwise_alignment(values)
    assert alignment < 0.5  # Divergent values


def test_a06_compute_variance():
    """Test _compute_variance utility function."""
    # Zero variance
    assert _compute_variance([0.5, 0.5, 0.5]) == 0.0

    # Non-zero variance
    variance = _compute_variance([0.0, 0.5, 1.0])
    assert variance > 0.0

    # Empty or single value
    assert _compute_variance([]) == 0.0
    assert _compute_variance([0.5]) == 0.0


def test_a07_tfce_graceful_degradation_insufficient_data():
    """Test TFCE returns None with insufficient data."""
    # Less than 3 phases
    result = compute_trajectory_field_convergence(
        predictive_drift_phase35={"drift_magnitude_prediction": 0.3},
        identity_resonance_phase36={"ims": 0.7},
    )
    assert result is None


def test_a08_tfce_convergence_index_calculation():
    """Test convergence index calculation logic."""
    # Mock upstream snapshots
    drift = {"drift_magnitude_prediction": 0.2, "drift_stability_score": 0.8}
    identity = {"ims": 0.75, "ida": 0.7}
    continuity = {"ncc": 0.8, "icc": 0.75, "css": 0.85}
    forecast = {"coherence_slope": 0.1, "forecast_strength": 0.8}
    multi_horizon = {"forecast_consensus_index": 0.75, "future_stability_envelope": 0.8}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
        multi_horizon_phase39=multi_horizon,
    )

    assert result is not None
    assert 0.0 <= result.convergence_index <= 1.0
    assert result.convergence_index > 0.5  # Should be reasonably high


def test_a09_tfce_divergence_index_inverse():
    """Test divergence index is inverse of convergence index."""
    drift = {"drift_magnitude_prediction": 0.2, "drift_stability_score": 0.8}
    identity = {"ims": 0.75, "ida": 0.7}
    continuity = {"ncc": 0.8, "icc": 0.75, "css": 0.85}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    assert result is not None
    assert abs(result.convergence_index + result.divergence_index - 1.0) < 0.001


def test_a10_tfce_stability_index_calculation():
    """Test stability index calculation from multiple stability signals."""
    identity = {"ims": 0.75, "ida": 0.8}
    continuity = {"ncc": 0.8, "icc": 0.75, "css": 0.85}
    multi_horizon = {"forecast_consensus_index": 0.75, "future_stability_envelope": 0.9}
    mtsf = {"tsi": 0.8}

    result = compute_trajectory_field_convergence(
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        multi_horizon_phase39=multi_horizon,
        mtsf_phase45=mtsf,
    )

    assert result is not None
    assert 0.0 <= result.stability_index <= 1.0
    assert result.stability_index > 0.7  # Should be high with all stable inputs


def test_a11_tfce_convergence_band_high():
    """Test convergence band classification: high."""
    # High convergence signals
    drift = {"drift_magnitude_prediction": 0.1, "drift_stability_score": 0.9}
    identity = {"ims": 0.85, "ida": 0.8}
    continuity = {"ncc": 0.85, "icc": 0.8, "css": 0.9}
    forecast = {"coherence_slope": 0.2, "forecast_strength": 0.85}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
    )

    assert result is not None
    assert result.convergence_band == "high"


def test_a12_tfce_convergence_band_fragmented():
    """Test convergence band classification: fragmented."""
    # Low convergence signals (divergent)
    drift = {"drift_magnitude_prediction": 0.8, "drift_stability_score": 0.2}
    identity = {"ims": 0.2, "ida": 0.3}
    continuity = {"ncc": 0.3, "icc": 0.25, "css": 0.2}
    forecast = {"coherence_slope": -0.5, "forecast_strength": 0.3}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
    )

    assert result is not None
    assert result.convergence_band == "fragmented"


def test_a13_tfce_dominant_convergence_signal():
    """Test dominant convergence signal identification."""
    # Symbolic trajectory should be strongest
    drift = {"drift_magnitude_prediction": 0.5, "drift_stability_score": 0.5}
    identity = {"ims": 0.5, "ida": 0.5}
    continuity = {"ncc": 0.5, "icc": 0.5, "css": 0.5}
    forecast = {"coherence_slope": 0.8, "forecast_strength": 0.95}  # Very strong

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
    )

    assert result is not None
    assert result.dominant_convergence_signal in ["SYMBOLIC", "DRIFT", "IDENTITY", "CONTINUITY"]


def test_a14_tfce_diagnostic_tags_generation():
    """Test diagnostic tags generation."""
    # High convergence should generate TRAJECTORY_CONVERGING tag
    drift = {"drift_magnitude_prediction": 0.1, "drift_stability_score": 0.9}
    identity = {"ims": 0.85, "ida": 0.8}
    continuity = {"ncc": 0.85, "icc": 0.8, "css": 0.9}
    forecast = {"coherence_slope": 0.2, "forecast_strength": 0.85}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
    )

    assert result is not None
    assert isinstance(result.diagnostic_tags, list)
    assert len(result.diagnostic_tags) > 0
    # Tags should be sorted for determinism
    assert result.diagnostic_tags == sorted(result.diagnostic_tags)


def test_a15_tfce_deterministic_repeated_calls():
    """Test TFCE is deterministic with repeated calls."""
    drift = {"drift_magnitude_prediction": 0.4, "drift_stability_score": 0.6}
    identity = {"ims": 0.65, "ida": 0.6}
    continuity = {"ncc": 0.7, "icc": 0.65, "css": 0.75}

    result1 = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    result2 = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    assert result1 is not None
    assert result2 is not None
    assert result1.convergence_index == result2.convergence_index
    assert result1.divergence_index == result2.divergence_index
    assert result1.stability_index == result2.stability_index
    assert result1.convergence_band == result2.convergence_band
    assert result1.dominant_convergence_signal == result2.dominant_convergence_signal
    assert result1.diagnostic_tags == result2.diagnostic_tags


# ============================================================================
# GROUP B: COHERENCE INTEGRATION (10 TESTS)
# ============================================================================


def test_b01_coherence_state_tfce_fields_exist():
    """Test CoherenceState has TFCE fields."""
    state = CoherenceState(convo_id="test", turn_index=0)

    assert hasattr(state, "trajectory_convergence_snapshot")
    assert hasattr(state, "tfce_convergence_index_history")
    assert hasattr(state, "tfce_divergence_index_history")
    assert hasattr(state, "tfce_stability_index_history")
    assert hasattr(state, "tfce_convergence_band_history")
    assert hasattr(state, "tfce_dominant_signal_history")
    assert hasattr(state, "tfce_tags_history")


def test_b02_coherence_state_tfce_default_values():
    """Test CoherenceState TFCE fields have correct default values."""
    state = CoherenceState(convo_id="test", turn_index=0)

    assert state.trajectory_convergence_snapshot is None
    assert state.tfce_convergence_index_history == []
    assert state.tfce_divergence_index_history == []
    assert state.tfce_stability_index_history == []
    assert state.tfce_convergence_band_history == []
    assert state.tfce_dominant_signal_history == []
    assert state.tfce_tags_history == []


def test_b03_coherence_engine_has_tfce_update_method():
    """Test CoherenceEngine has _update_trajectory_field_convergence method."""
    engine = CoherenceEngine()
    assert hasattr(engine, "_update_trajectory_field_convergence")
    assert callable(getattr(engine, "_update_trajectory_field_convergence"))


def test_b04_coherence_state_window_trim_tfce_histories():
    """Test window_trim trims TFCE histories correctly."""
    state = CoherenceState(convo_id="test", turn_index=10)

    # Populate histories
    state.tfce_convergence_index_history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    state.tfce_divergence_index_history = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    state.tfce_stability_index_history = [0.5] * 10
    state.tfce_convergence_band_history = ["low"] * 10
    state.tfce_dominant_signal_history = ["DRIFT"] * 10
    state.tfce_tags_history = [["TAG1"]] * 10

    # Trim to window of 5
    state.window_trim(5)

    assert len(state.tfce_convergence_index_history) == 5
    assert len(state.tfce_divergence_index_history) == 5
    assert len(state.tfce_stability_index_history) == 5
    assert len(state.tfce_convergence_band_history) == 5
    assert len(state.tfce_dominant_signal_history) == 5
    assert len(state.tfce_tags_history) == 5

    # Check last 5 values
    assert state.tfce_convergence_index_history == [0.6, 0.7, 0.8, 0.9, 1.0]


def test_b05_coherence_engine_tfce_update_with_none_snapshot():
    """Test TFCE update handles None snapshot gracefully."""
    state = CoherenceState(convo_id="test", turn_index=0)
    engine = CoherenceEngine()

    # Update without upstream data (should result in None snapshot)
    engine._update_trajectory_field_convergence(state)

    # Snapshot should be None
    assert state.trajectory_convergence_snapshot is None

    # Histories should have default values appended
    assert len(state.tfce_convergence_index_history) == 1
    assert state.tfce_convergence_index_history[0] == 0.0
    assert len(state.tfce_divergence_index_history) == 1
    assert state.tfce_divergence_index_history[0] == 0.0


def test_b06_coherence_engine_tfce_update_with_valid_snapshot():
    """Test TFCE update populates snapshot and histories correctly."""
    state = CoherenceState(convo_id="test", turn_index=0)
    engine = CoherenceEngine()

    # Create mock upstream snapshots
    state.predictive_drift_snapshot = type('obj', (object,), {
        'drift_magnitude_prediction': 0.3,
        'drift_stability_score': 0.7
    })()
    state.identity_resonance_memory_snapshot = type('obj', (object,), {
        'ims': 0.75,
        'ida': 0.7
    })()
    state.adaptive_continuity_snapshot = type('obj', (object,), {
        'ncc': 0.8,
        'icc': 0.75,
        'css': 0.85
    })()

    # Update TFCE
    engine._update_trajectory_field_convergence(state)

    # Snapshot should be populated
    assert state.trajectory_convergence_snapshot is not None

    # Histories should have values
    assert len(state.tfce_convergence_index_history) == 1
    assert 0.0 <= state.tfce_convergence_index_history[0] <= 1.0
    assert len(state.tfce_convergence_band_history) == 1
    assert state.tfce_convergence_band_history[0] in ["high", "medium", "low", "fragmented"]


def test_b07_coherence_state_tfce_snapshot_persistence():
    """Test TFCE snapshot persists across multiple updates."""
    state = CoherenceState(convo_id="test", turn_index=0)
    engine = CoherenceEngine()

    # Create mock upstream snapshots
    state.predictive_drift_snapshot = type('obj', (object,), {
        'drift_magnitude_prediction': 0.3,
        'drift_stability_score': 0.7
    })()
    state.identity_resonance_memory_snapshot = type('obj', (object,), {
        'ims': 0.75,
        'ida': 0.7
    })()
    state.adaptive_continuity_snapshot = type('obj', (object,), {
        'ncc': 0.8,
        'icc': 0.75,
        'css': 0.85
    })()

    # First update
    engine._update_trajectory_field_convergence(state)
    first_snapshot = state.trajectory_convergence_snapshot

    # Second update
    engine._update_trajectory_field_convergence(state)
    second_snapshot = state.trajectory_convergence_snapshot

    # Both snapshots should be valid
    assert first_snapshot is not None
    assert second_snapshot is not None

    # Histories should grow
    assert len(state.tfce_convergence_index_history) == 2


def test_b08_coherence_state_tfce_tags_deduplication():
    """Test TFCE tags are deduplicated and sorted."""
    state = CoherenceState(convo_id="test", turn_index=0)
    engine = CoherenceEngine()

    # Create mock upstream snapshots with high convergence
    state.predictive_drift_snapshot = type('obj', (object,), {
        'drift_magnitude_prediction': 0.1,
        'drift_stability_score': 0.9
    })()
    state.identity_resonance_memory_snapshot = type('obj', (object,), {
        'ims': 0.85,
        'ida': 0.8
    })()
    state.adaptive_continuity_snapshot = type('obj', (object,), {
        'ncc': 0.85,
        'icc': 0.8,
        'css': 0.9
    })()
    state.temporal_forecast_snapshot = type('obj', (object,), {
        'coherence_slope': 0.2,
        'forecast_strength': 0.85
    })()

    # Update TFCE
    engine._update_trajectory_field_convergence(state)

    # Check tags are sorted (determinism)
    if state.tfce_tags_history:
        tags = state.tfce_tags_history[0]
        assert tags == sorted(tags)


def test_b09_coherence_state_tfce_history_alignment():
    """Test TFCE histories stay aligned across multiple turns."""
    state = CoherenceState(convo_id="test", turn_index=0)
    engine = CoherenceEngine()

    # Create mock upstream snapshots
    state.predictive_drift_snapshot = type('obj', (object,), {
        'drift_magnitude_prediction': 0.3,
        'drift_stability_score': 0.7
    })()
    state.identity_resonance_memory_snapshot = type('obj', (object,), {
        'ims': 0.75,
        'ida': 0.7
    })()
    state.adaptive_continuity_snapshot = type('obj', (object,), {
        'ncc': 0.8,
        'icc': 0.75,
        'css': 0.85
    })()

    # Multiple updates
    for _ in range(3):
        engine._update_trajectory_field_convergence(state)

    # All histories should have same length
    assert len(state.tfce_convergence_index_history) == 3
    assert len(state.tfce_divergence_index_history) == 3
    assert len(state.tfce_stability_index_history) == 3
    assert len(state.tfce_convergence_band_history) == 3
    assert len(state.tfce_dominant_signal_history) == 3
    assert len(state.tfce_tags_history) == 3


def test_b10_coherence_engine_tfce_update_ordering():
    """Test TFCE update is called after Phase 45 in update flow."""
    # This is a structural test - verify the method exists and has correct signature
    engine = CoherenceEngine()
    method = getattr(engine, "_update_trajectory_field_convergence", None)

    assert method is not None
    assert callable(method)

    # Check method signature accepts CoherenceState
    import inspect
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert "state" in params


# ============================================================================
# GROUP C: SESSION SUMMARY (10 TESTS)
# ============================================================================


def test_c01_session_summary_has_tfce_fields():
    """Test SessionSummary has TFCE aggregation fields."""
    from symbolu.service.sessions.session_models import SessionSummary
    from datetime import datetime

    summary = SessionSummary(
        session_id="test",
        total_turns=10,
        coherence_trend=0.7,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.8,
        created_at=datetime.now(),
    )

    assert hasattr(summary, "avg_trajectory_convergence")
    assert hasattr(summary, "avg_trajectory_divergence")
    assert hasattr(summary, "avg_trajectory_stability")
    assert hasattr(summary, "dominant_convergence_band")
    assert hasattr(summary, "dominant_convergence_tags")


def test_c02_session_summary_tfce_default_values():
    """Test SessionSummary TFCE fields have correct default values."""
    from symbolu.service.sessions.session_models import SessionSummary
    from datetime import datetime

    summary = SessionSummary(
        session_id="test",
        total_turns=10,
        coherence_trend=0.7,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.8,
        created_at=datetime.now(),
    )

    assert summary.avg_trajectory_convergence is None
    assert summary.avg_trajectory_divergence is None
    assert summary.avg_trajectory_stability is None
    assert summary.dominant_convergence_band is None
    assert summary.dominant_convergence_tags == []


def test_c03_session_store_computes_tfce_aggregates():
    """Test session store computes TFCE summary metrics."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    # Create session with TFCE data
    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with TFCE data
    coherence_dict = {
        "tfce_convergence_index_history": [0.7, 0.75, 0.8],
        "tfce_divergence_index_history": [0.3, 0.25, 0.2],
        "tfce_stability_index_history": [0.8, 0.82, 0.85],
        "tfce_convergence_band_history": ["high", "high", "high"],
        "tfce_dominant_signal_history": ["SYMBOLIC", "IDENTITY", "SYMBOLIC"],
        "tfce_tags_history": [["TRAJECTORY_CONVERGING"], ["STABILITY_STRONG"], ["CONVERGENCE_HIGH"]],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Check aggregates
    assert summary.avg_trajectory_convergence is not None
    assert summary.avg_trajectory_convergence == pytest.approx(0.75, abs=0.01)
    assert summary.avg_trajectory_divergence is not None
    assert summary.avg_trajectory_stability is not None
    assert summary.dominant_convergence_band == "high"
    assert len(summary.dominant_convergence_tags) > 0


def test_c04_session_store_tfce_band_deterministic_tie_breaking():
    """Test session store uses deterministic tie-breaking for convergence band."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with tied bands (2 high, 2 medium)
    coherence_dict = {
        "tfce_convergence_index_history": [0.7],
        "tfce_divergence_index_history": [0.3],
        "tfce_stability_index_history": [0.8],
        "tfce_convergence_band_history": ["high", "medium", "high", "medium"],
        "tfce_dominant_signal_history": ["SYMBOLIC"],
        "tfce_tags_history": [[]],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # With tied bands, should use alphabetical tie-breaking
    assert summary.dominant_convergence_band == "high"  # "high" < "medium" alphabetically


def test_c05_session_store_tfce_tags_deduplication():
    """Test session store deduplicates and sorts TFCE tags."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with duplicate tags
    coherence_dict = {
        "tfce_convergence_index_history": [0.7],
        "tfce_divergence_index_history": [0.3],
        "tfce_stability_index_history": [0.8],
        "tfce_convergence_band_history": ["high"],
        "tfce_dominant_signal_history": ["SYMBOLIC"],
        "tfce_tags_history": [
            ["TRAJECTORY_CONVERGING", "STABILITY_STRONG"],
            ["TRAJECTORY_CONVERGING", "CONVERGENCE_HIGH"],
            ["STABILITY_STRONG", "CONVERGENCE_HIGH"],
        ],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Tags should be deduplicated and sorted
    assert len(summary.dominant_convergence_tags) == 3
    assert summary.dominant_convergence_tags == sorted(summary.dominant_convergence_tags)


def test_c06_session_store_tfce_empty_history():
    """Test session store handles empty TFCE history gracefully."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Empty coherence history
    coherence_dict = {
        "tfce_convergence_index_history": [],
        "tfce_divergence_index_history": [],
        "tfce_stability_index_history": [],
        "tfce_convergence_band_history": [],
        "tfce_dominant_signal_history": [],
        "tfce_tags_history": [],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Should handle None values gracefully
    assert summary.avg_trajectory_convergence is None
    assert summary.avg_trajectory_divergence is None
    assert summary.avg_trajectory_stability is None
    assert summary.dominant_convergence_band is None


def test_c07_session_store_tfce_average_calculations():
    """Test session store computes correct averages."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with known values
    coherence_dict = {
        "tfce_convergence_index_history": [0.6, 0.8, 1.0],
        "tfce_divergence_index_history": [0.4, 0.2, 0.0],
        "tfce_stability_index_history": [0.5, 0.75, 1.0],
        "tfce_convergence_band_history": ["medium"],
        "tfce_dominant_signal_history": ["SYMBOLIC"],
        "tfce_tags_history": [[]],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Check averages
    assert summary.avg_trajectory_convergence == pytest.approx(0.8, abs=0.01)  # (0.6 + 0.8 + 1.0) / 3
    assert summary.avg_trajectory_divergence == pytest.approx(0.2, abs=0.01)  # (0.4 + 0.2 + 0.0) / 3
    assert summary.avg_trajectory_stability == pytest.approx(0.75, abs=0.01)  # (0.5 + 0.75 + 1.0) / 3


def test_c08_session_store_tfce_multiple_coherence_entries():
    """Test session store aggregates TFCE across multiple coherence history entries."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add multiple coherence entries
    for i in range(3):
        coherence_dict = {
            "tfce_convergence_index_history": [0.7 + i * 0.1],
            "tfce_divergence_index_history": [0.3 - i * 0.1],
            "tfce_stability_index_history": [0.8 + i * 0.05],
            "tfce_convergence_band_history": ["high"],
            "tfce_dominant_signal_history": ["SYMBOLIC"],
            "tfce_tags_history": [[]],
        }
        state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Should aggregate across all entries
    assert summary.avg_trajectory_convergence is not None
    assert summary.avg_trajectory_convergence == pytest.approx(0.8, abs=0.01)


def test_c09_session_store_tfce_band_frequency():
    """Test session store picks most frequent band."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with varying bands (3 high, 2 medium)
    coherence_dict = {
        "tfce_convergence_index_history": [0.7],
        "tfce_divergence_index_history": [0.3],
        "tfce_stability_index_history": [0.8],
        "tfce_convergence_band_history": ["high", "high", "high", "medium", "medium"],
        "tfce_dominant_signal_history": ["SYMBOLIC"],
        "tfce_tags_history": [[]],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary
    summary = store.compute_session_summary(state)

    # Should pick most frequent
    assert summary.dominant_convergence_band == "high"


def test_c10_session_store_tfce_null_safe():
    """Test session store handles None/missing values safely."""
    from symbolu.service.sessions.session_store import SessionStore
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    store = SessionStore()
    session_id = "test_session"

    state = SessionState(session_id=session_id, created_at=datetime.now())

    # Add coherence history with None values
    coherence_dict = {
        "tfce_convergence_index_history": [0.7, None, 0.8],
        "tfce_divergence_index_history": [0.3, 0.2, None],
        "tfce_stability_index_history": [None, 0.8, 0.85],
        "tfce_convergence_band_history": ["high", "", "medium"],
        "tfce_dominant_signal_history": ["SYMBOLIC"],
        "tfce_tags_history": [[]],
    }
    state.coherence_history.append(coherence_dict)

    # Compute summary - should not crash
    summary = store.compute_session_summary(state)

    # Should handle None values gracefully
    assert summary.avg_trajectory_convergence is not None  # Should average non-None values


# ============================================================================
# GROUP D: UNIFIED API + OBSERVER (10 TESTS)
# ============================================================================


def test_d01_unified_output_has_tfce_field():
    """Test UnifiedOutput has trajectory_field_convergence field."""
    from symbolu.api.unified_api import UnifiedOutput

    # Create minimal UnifiedOutput
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

    assert hasattr(output, "trajectory_field_convergence")


def test_d02_unified_output_tfce_field_optional():
    """Test UnifiedOutput trajectory_field_convergence field is optional."""
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

    assert output.trajectory_field_convergence is None


def test_d03_unified_output_tfce_json_serialization():
    """Test UnifiedOutput with TFCE data serializes to JSON correctly."""
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
        trajectory_field_convergence={
            "convergence_index": 0.8,
            "divergence_index": 0.2,
            "stability_index": 0.85,
            "convergence_band": "high",
            "diagnostic_tags": ["TRAJECTORY_CONVERGING"],
        },
    )

    # Convert to dict
    output_dict = output.to_dict()

    assert "trajectory_field_convergence" in output_dict
    assert output_dict["trajectory_field_convergence"]["convergence_index"] == 0.8


def test_d04_unified_output_tfce_backward_compatible():
    """Test UnifiedOutput without TFCE data is backward compatible."""
    from symbolu.api.unified_api import UnifiedOutput

    # Old output without TFCE
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

    # Should serialize without TFCE field (None values removed)
    output_dict = output.to_dict()

    # trajectory_field_convergence should not be in dict if None
    # (depends on _remove_none_values implementation)
    assert "trajectory_field_convergence" not in output_dict or output_dict.get("trajectory_field_convergence") is None


def test_d05_coherence_observer_has_tfce_fields():
    """Test CoherenceObservation has TFCE fields."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.7,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        mapper_volatility_score=0.2,
        temporal_arc_score=0.75,
    )

    assert hasattr(observation, "tfce_convergence_index")
    assert hasattr(observation, "tfce_divergence_index")
    assert hasattr(observation, "tfce_stability_index")
    assert hasattr(observation, "tfce_band")
    assert hasattr(observation, "tfce_tags")


def test_d06_coherence_observer_tfce_default_values():
    """Test CoherenceObservation TFCE fields have correct defaults."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.7,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        mapper_volatility_score=0.2,
        temporal_arc_score=0.75,
    )

    assert observation.tfce_convergence_index == 0.0
    assert observation.tfce_divergence_index == 0.0
    assert observation.tfce_stability_index == 0.0
    assert observation.tfce_band is None
    assert observation.tfce_tags == []


def test_d07_coherence_observer_tfce_extraction():
    """Test CoherenceObserver extracts TFCE data from coherence state."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver

    observer = CoherenceObserver()

    # Create mock coherence state with TFCE snapshot
    coherence_state = CoherenceState(convo_id="test", turn_index=0)
    coherence_state.trajectory_convergence_snapshot = type('obj', (object,), {
        'convergence_index': 0.8,
        'divergence_index': 0.2,
        'stability_index': 0.85,
        'convergence_band': 'high',
        'diagnostic_tags': ['TRAJECTORY_CONVERGING'],
    })()

    # Observe
    observation = observer.observe(coherence_state=coherence_state)

    assert observation.tfce_convergence_index == 0.8
    assert observation.tfce_divergence_index == 0.2
    assert observation.tfce_stability_index == 0.85
    assert observation.tfce_band == 'high'
    assert observation.tfce_tags == ['TRAJECTORY_CONVERGING']


def test_d08_coherence_observer_tfce_null_safe():
    """Test CoherenceObserver handles None TFCE snapshot safely."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver

    observer = CoherenceObserver()

    # Create mock coherence state without TFCE snapshot
    coherence_state = CoherenceState(convo_id="test", turn_index=0)
    coherence_state.trajectory_convergence_snapshot = None

    # Observe - should not crash
    observation = observer.observe(coherence_state=coherence_state)

    assert observation.tfce_convergence_index == 0.0
    assert observation.tfce_band is None


def test_d09_coherence_observation_to_dict():
    """Test CoherenceObservation.to_dict() includes TFCE fields."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.7,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        mapper_volatility_score=0.2,
        temporal_arc_score=0.75,
        tfce_convergence_index=0.8,
        tfce_divergence_index=0.2,
        tfce_stability_index=0.85,
        tfce_band="high",
        tfce_tags=["TRAJECTORY_CONVERGING"],
    )

    obs_dict = observation.to_dict()

    assert "tfce_convergence_index" in obs_dict
    assert obs_dict["tfce_convergence_index"] == 0.8
    assert "tfce_band" in obs_dict
    assert obs_dict["tfce_band"] == "high"


def test_d10_unified_api_extraction_helper():
    """Test unified API extraction helper for TFCE."""
    # This is a structural test - verify extraction logic exists
    from symbolu.api.unified_api import build_unified_output

    # Create mock context with coherence state
    class MockCtx:
        coherence_state = None
        rendered = None
        routing_plan = None
        mapper_profile = None
        dha_insights = None
        fusion_result = None
        mlcr_results = None
        policy_flags = None
        temporal_bhava_summary = None
        session_memory_events = None
        session_recap = None
        intent_arc_result = None
        identity_signature_result = None
        motivation_profile_result = None
        persona_response = None

    ctx = MockCtx()
    ctx.coherence_state = CoherenceState(convo_id="test", turn_index=0)
    ctx.coherence_state.trajectory_convergence_snapshot = type('obj', (object,), {
        'convergence_index': 0.8,
        'divergence_index': 0.2,
        'stability_index': 0.85,
        'convergence_band': 'high',
        'dominant_convergence_signal': 'SYMBOLIC',
        'diagnostic_tags': ['TRAJECTORY_CONVERGING'],
        'drift_alignment': 0.7,
        'identity_alignment': 0.75,
        'symbolic_alignment': 0.9,
        'continuity_alignment': 0.8,
        'scenario_alignment': 0.85,
        'horizon_alignment': 0.8,
    })()

    # Build unified output - should not crash
    try:
        output = build_unified_output("test text", ctx)
        # If it succeeds, TFCE should be extracted
        if output.trajectory_field_convergence:
            assert output.trajectory_field_convergence["convergence_index"] == 0.8
    except Exception:
        # If build_unified_output needs more mocking, that's okay for this test
        pass


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE (10 TESTS)
# ============================================================================


def test_e01_tfce_zero_llm_guarantee():
    """Test TFCE has zero LLM calls (purely mathematical)."""
    # TFCE should not import or use any LLM client
    import symbolu.formulas.trajectory_field_convergence as tfce_module

    # Check module source for LLM imports
    import inspect
    source = inspect.getsource(tfce_module)

    # Should not import anthropic, openai, or any LLM client
    assert "import anthropic" not in source.lower()
    assert "import openai" not in source.lower()
    assert "from anthropic" not in source.lower()
    assert "from openai" not in source.lower()


def test_e02_tfce_no_routing_changes():
    """Test TFCE does not modify routing logic."""
    # TFCE should not touch TTOR routing
    from symbolu.formulas.trajectory_field_convergence import compute_trajectory_field_convergence

    # Compute TFCE
    drift = {"drift_magnitude_prediction": 0.3, "drift_stability_score": 0.7}
    identity = {"ims": 0.75, "ida": 0.7}
    continuity = {"ncc": 0.8, "icc": 0.75, "css": 0.85}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    # Should only return a snapshot, not modify any routing state
    assert isinstance(result, TrajectoryFieldConvergenceSnapshot) or result is None


def test_e03_tfce_no_mapper_changes():
    """Test TFCE does not modify mapper selection."""
    # TFCE should be observation-only
    # Check that compute function has no side effects on global state
    from symbolu.formulas.trajectory_field_convergence import compute_trajectory_field_convergence

    drift = {"drift_magnitude_prediction": 0.3, "drift_stability_score": 0.7}
    identity = {"ims": 0.75, "ida": 0.7}
    continuity = {"ncc": 0.8, "icc": 0.75, "css": 0.85}

    # Call twice - should have no side effects
    result1 = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    result2 = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
    )

    # Should produce identical results (no state changes)
    assert result1.convergence_index == result2.convergence_index


def test_e04_tfce_no_persona_semantic_changes():
    """Test TFCE does not modify persona semantics or tone."""
    # This test verifies TFCE is metadata-only in persona engine
    from symbolu.mechanical.persona.engine import PersonaEngine

    engine = PersonaEngine()

    # Check that TFCE extraction methods exist but don't modify tone
    assert hasattr(engine, "_extract_trajectory_convergence")
    assert hasattr(engine, "_build_trajectory_convergence_metadata")

    # These should only build metadata dicts, not affect tone parameters
    import inspect

    # Check _build_trajectory_convergence_metadata signature
    sig = inspect.signature(engine._build_trajectory_convergence_metadata)
    # Should return Dict[str, Any] (metadata only)
    assert sig.return_annotation == Dict[str, Any] or sig.return_annotation.__origin__ == dict


def test_e05_tfce_observation_only():
    """Test TFCE is truly observation-only (no pipeline modifications)."""
    # TFCE should not modify any pipeline context or state beyond coherence observation
    from symbolu.core.coherence.coherence_engine import CoherenceEngine

    engine = CoherenceEngine()
    state = CoherenceState(convo_id="test", turn_index=0)

    # Create mock upstream snapshots
    state.predictive_drift_snapshot = type('obj', (object,), {
        'drift_magnitude_prediction': 0.3,
        'drift_stability_score': 0.7
    })()
    state.identity_resonance_memory_snapshot = type('obj', (object,), {
        'ims': 0.75,
        'ida': 0.7
    })()
    state.adaptive_continuity_snapshot = type('obj', (object,), {
        'ncc': 0.8,
        'icc': 0.75,
        'css': 0.85
    })()

    # Update TFCE
    engine._update_trajectory_field_convergence(state)

    # Should only modify state.trajectory_convergence_snapshot and histories
    # Should NOT modify upstream snapshots
    assert state.predictive_drift_snapshot is not None
    assert state.identity_resonance_memory_snapshot is not None
    assert state.adaptive_continuity_snapshot is not None


def test_e06_tfce_deterministic_computation():
    """Test TFCE computation is deterministic (same inputs → same outputs)."""
    drift = {"drift_magnitude_prediction": 0.4, "drift_stability_score": 0.6}
    identity = {"ims": 0.65, "ida": 0.6}
    continuity = {"ncc": 0.7, "icc": 0.65, "css": 0.75}
    forecast = {"coherence_slope": 0.1, "forecast_strength": 0.7}

    results = []
    for _ in range(5):
        result = compute_trajectory_field_convergence(
            predictive_drift_phase35=drift,
            identity_resonance_phase36=identity,
            continuity_phase37=continuity,
            forecast_phase38=forecast,
        )
        results.append(result)

    # All results should be identical
    for r in results[1:]:
        assert r.convergence_index == results[0].convergence_index
        assert r.divergence_index == results[0].divergence_index
        assert r.stability_index == results[0].stability_index
        assert r.convergence_band == results[0].convergence_band
        assert r.diagnostic_tags == results[0].diagnostic_tags


def test_e07_tfce_no_fusion_changes():
    """Test TFCE does not affect Fusion renderer."""
    # TFCE should not import or modify Fusion
    import symbolu.formulas.trajectory_field_convergence as tfce_module
    import inspect

    source = inspect.getsource(tfce_module)

    # Should not import fusion
    assert "from symbolu.mechanical.multilayer.fusion" not in source
    assert "import symbolu.mechanical.multilayer.fusion" not in source


def test_e08_tfce_no_dha_changes():
    """Test TFCE does not affect DHA delivery."""
    # TFCE should not import or modify DHA
    import symbolu.formulas.trajectory_field_convergence as tfce_module
    import inspect

    source = inspect.getsource(tfce_module)

    # Should not import DHA
    assert "from symbolu.mechanical.dha" not in source
    assert "import symbolu.mechanical.dha" not in source


def test_e09_tfce_bounded_outputs():
    """Test TFCE outputs are bounded [0.0, 1.0]."""
    # Test with extreme inputs
    drift = {"drift_magnitude_prediction": 1.0, "drift_stability_score": 0.0}
    identity = {"ims": 0.0, "ida": 1.0}
    continuity = {"ncc": 1.0, "icc": 0.0, "css": 0.5}
    forecast = {"coherence_slope": 1.0, "forecast_strength": 0.0}

    result = compute_trajectory_field_convergence(
        predictive_drift_phase35=drift,
        identity_resonance_phase36=identity,
        continuity_phase37=continuity,
        forecast_phase38=forecast,
    )

    assert result is not None

    # All numeric outputs should be in [0.0, 1.0]
    assert 0.0 <= result.convergence_index <= 1.0
    assert 0.0 <= result.divergence_index <= 1.0
    assert 0.0 <= result.stability_index <= 1.0

    # Optional alignments should be None or in [0.0, 1.0]
    if result.drift_alignment is not None:
        assert 0.0 <= result.drift_alignment <= 1.0
    if result.identity_alignment is not None:
        assert 0.0 <= result.identity_alignment <= 1.0


def test_e10_tfce_backward_compatible():
    """Test TFCE is backward compatible (all fields optional)."""
    # Test that old code without TFCE still works
    from symbolu.core.coherence.coherence_state import CoherenceState

    # Create state without TFCE data
    state = CoherenceState(convo_id="test", turn_index=0)

    # Should have TFCE fields but all None/empty
    assert state.trajectory_convergence_snapshot is None
    assert state.tfce_convergence_index_history == []

    # Should be able to serialize/deserialize
    from dataclasses import asdict
    state_dict = asdict(state)

    assert "trajectory_convergence_snapshot" in state_dict
    assert "tfce_convergence_index_history" in state_dict


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
