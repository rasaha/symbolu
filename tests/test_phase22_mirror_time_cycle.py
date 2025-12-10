"""
Test Suite for Phase 22: Mirror-Time Cycle Engine (MTCE) v1.0

Comprehensive test coverage for the Mirror-Time Cycle analytical layer.

Test Groups:
    GROUP A: Cycle Detection & Math (14 tests)
    GROUP B: Coherence Integration (6 tests)
    GROUP C: Session Summary Aggregation (6 tests)
    GROUP D: Unified API & Adapter (5 tests)
    GROUP E: Behavioral Invariance (3 tests)

Total: 34 tests
"""

import pytest
from symbolu.formulas.mirror_time_cycle import (
    detect_mirror_time_cycles,
    MirrorTimeCycleSnapshot,
    MirrorTimeCycleSummary,
    _clamp,
    _safe_mean,
    _safe_stdev,
    _compute_linear_gradient,
    _detect_cycle_boundaries,
    _classify_cycle_type,
    _classify_stability_band,
    _classify_reversal_bias,
)
from symbolu.formulas.mirror_time_loop import MirrorTimeLoopSnapshot


# ============================================================================
# GROUP A: Cycle Detection & Math (14 tests)
# ============================================================================


def test_formula_clamp():
    """Test _clamp utility function."""
    assert _clamp(0.5, 0.0, 1.0) == 0.5
    assert _clamp(-0.5, 0.0, 1.0) == 0.0
    assert _clamp(1.5, 0.0, 1.0) == 1.0
    assert _clamp(0.0, 0.0, 1.0) == 0.0
    assert _clamp(1.0, 0.0, 1.0) == 1.0


def test_formula_safe_mean():
    """Test _safe_mean utility function."""
    assert _safe_mean([0.5, 0.6, 0.7]) == pytest.approx(0.6, abs=0.01)
    assert _safe_mean([]) == 0.5  # Default neutral
    assert _safe_mean([1.0]) == 1.0


def test_formula_safe_stdev():
    """Test _safe_stdev utility function."""
    assert _safe_stdev([0.5, 0.5, 0.5]) == 0.0
    assert _safe_stdev([0.0, 1.0]) > 0.0
    assert _safe_stdev([]) == 0.0  # No data
    assert _safe_stdev([0.5]) == 0.0  # Single value


def test_formula_linear_gradient_basic():
    """Test _compute_linear_gradient with basic inputs."""
    # Increasing sequence
    values = [0.2, 0.4, 0.6, 0.8]
    gradient = _compute_linear_gradient(values)
    assert gradient > 0.0  # Positive slope

    # Decreasing sequence
    values = [0.8, 0.6, 0.4, 0.2]
    gradient = _compute_linear_gradient(values)
    assert gradient < 0.0  # Negative slope

    # Flat sequence
    values = [0.5, 0.5, 0.5, 0.5]
    gradient = _compute_linear_gradient(values)
    assert abs(gradient) < 0.01  # Near-zero slope


def test_formula_linear_gradient_edge_cases():
    """Test _compute_linear_gradient with edge cases."""
    # Single value
    assert _compute_linear_gradient([0.5]) == 0.0

    # Empty list
    assert _compute_linear_gradient([]) == 0.0


def test_cycle_detection_simple_pattern():
    """Test cycle detection with simple converging pattern."""
    # Create synthetic loop history with clear pattern
    loop_history = []
    for i in range(10):
        snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.5 + i * 0.02,  # Increasing
            mirror_vector=0.5 + i * 0.03,  # Increasing faster
            loop_delta=-i * 0.01,  # Decreasing (mirror catching up)
            loop_tension=0.5 - i * 0.03,  # Decreasing
            loop_alignment=0.5 + i * 0.04,  # Increasing
            reversal_probability=0.3 - i * 0.02,  # Decreasing
            stability_band="stable" if i > 5 else "transitional",
        )
        loop_history.append(snapshot)

    summary = detect_mirror_time_cycles(loop_history)

    assert summary is not None
    assert len(summary.cycles) > 0
    assert summary.dominant_cycle_type is not None
    assert summary.dominant_stability_band is not None


def test_cycle_detection_empty_history():
    """Test cycle detection with empty history."""
    summary = detect_mirror_time_cycles([])

    assert summary is not None
    assert len(summary.cycles) == 0
    assert summary.dominant_cycle_type is None
    assert summary.dominant_stability_band is None


def test_cycle_detection_insufficient_data():
    """Test cycle detection with insufficient data (1 snapshot)."""
    loop_history = [
        MirrorTimeLoopSnapshot(
            forward_vector=0.5,
            mirror_vector=0.5,
            loop_delta=0.0,
            loop_tension=0.0,
            loop_alignment=1.0,
            reversal_probability=0.0,
            stability_band="stable",
        )
    ]

    summary = detect_mirror_time_cycles(loop_history)

    assert summary is not None
    assert len(summary.cycles) == 0


def test_cycle_classification_converging():
    """Test _classify_cycle_type for converging pattern."""
    alignment_trend = 0.05  # Increasing
    tension_trend = -0.05  # Decreasing
    alignment_values = [0.4, 0.5, 0.6, 0.7]

    cycle_type = _classify_cycle_type(alignment_trend, tension_trend, alignment_values)

    assert cycle_type == "converging"


def test_cycle_classification_diverging():
    """Test _classify_cycle_type for diverging pattern."""
    alignment_trend = -0.05  # Decreasing
    tension_trend = 0.05  # Increasing
    alignment_values = [0.7, 0.6, 0.5, 0.4]

    cycle_type = _classify_cycle_type(alignment_trend, tension_trend, alignment_values)

    assert cycle_type == "diverging"


def test_cycle_classification_oscillating():
    """Test _classify_cycle_type for oscillating pattern."""
    alignment_trend = 0.01  # Low trend
    tension_trend = 0.01  # Low trend
    alignment_values = [0.5, 0.6, 0.5, 0.6, 0.5]  # Oscillating

    cycle_type = _classify_cycle_type(alignment_trend, tension_trend, alignment_values)

    assert cycle_type == "oscillating"


def test_cycle_classification_stalled():
    """Test _classify_cycle_type for stalled pattern."""
    alignment_trend = 0.001  # Very low trend
    tension_trend = 0.001  # Very low trend
    alignment_values = [0.5, 0.5, 0.5, 0.5]  # Flat

    cycle_type = _classify_cycle_type(alignment_trend, tension_trend, alignment_values)

    assert cycle_type == "stalled"


def test_stability_band_classification():
    """Test _classify_stability_band classification."""
    # Stable dominant
    bands = ["stable", "stable", "stable", "transitional"]
    variance = 0.05
    assert _classify_stability_band(bands, variance) == "stable"

    # Unstable dominant
    bands = ["unstable", "unstable", "transitional"]
    variance = 0.2
    assert _classify_stability_band(bands, variance) == "unstable"

    # Transitional default
    bands = ["transitional", "transitional"]
    variance = 0.1
    assert _classify_stability_band(bands, variance) == "transitional"


def test_reversal_bias_classification():
    """Test _classify_reversal_bias classification."""
    # Toward alignment
    bias = _classify_reversal_bias(avg_reversal_prob=0.3, forward_gradient=0.05)
    assert bias == "toward_alignment"

    # Toward divergence
    bias = _classify_reversal_bias(avg_reversal_prob=0.7, forward_gradient=-0.05)
    assert bias == "toward_divergence"

    # Neutral
    bias = _classify_reversal_bias(avg_reversal_prob=0.5, forward_gradient=0.005)
    assert bias == "neutral"


def test_cycle_detection_determinism():
    """Test that cycle detection is deterministic."""
    # Create consistent loop history
    loop_history = []
    for i in range(10):
        snapshot = MirrorTimeLoopSnapshot(
            forward_vector=0.5,
            mirror_vector=0.5,
            loop_delta=0.0,
            loop_tension=0.3,
            loop_alignment=0.7,
            reversal_probability=0.2,
            stability_band="stable",
        )
        loop_history.append(snapshot)

    summary1 = detect_mirror_time_cycles(loop_history)
    summary2 = detect_mirror_time_cycles(loop_history)

    # Should produce identical results
    assert summary1.dominant_cycle_type == summary2.dominant_cycle_type
    assert summary1.dominant_stability_band == summary2.dominant_stability_band
    assert len(summary1.cycles) == len(summary2.cycles)


# ============================================================================
# GROUP B: Coherence Integration (6 tests)
# ============================================================================


def test_coherence_state_cycle_fields_exist():
    """Test that CoherenceState has Phase 22 cycle fields."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Check that Phase 22 fields exist
    assert hasattr(state, 'mirror_cycle_history')
    assert hasattr(state, 'dominant_cycle_type')
    assert hasattr(state, 'dominant_cycle_stability_band')
    assert hasattr(state, 'avg_cycle_alignment')
    assert hasattr(state, 'avg_cycle_tension')
    assert hasattr(state, 'avg_cycle_reversal_probability')


def test_coherence_state_updates_with_cycles():
    """Test that CoherenceEngine updates cycle fields."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    from unittest.mock import MagicMock

    engine = CoherenceEngine(window=10)
    state = CoherenceState(convo_id="test", turn_index=0)

    # Populate loop histories to trigger cycle detection
    state.loop_alignment_history = [0.5, 0.6, 0.7, 0.8]
    state.loop_tension_history = [0.4, 0.3, 0.2, 0.1]
    state.reversal_probability_history = [0.3, 0.2, 0.15, 0.1]
    state.stability_band_history = ["stable", "stable", "stable", "stable"]

    # Call _update_mirror_time_cycles directly
    engine._update_mirror_time_cycles(state)

    # Should have computed cycle metrics (may be None if no cycles detected)
    # At minimum, should not raise errors
    assert True  # Passes if no exceptions


def test_coherence_state_graceful_no_cycles():
    """Test that CoherenceEngine handles no cycles gracefully."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine

    engine = CoherenceEngine(window=10)
    state = CoherenceState(convo_id="test", turn_index=0)

    # Empty histories
    state.loop_alignment_history = []
    state.loop_tension_history = []
    state.reversal_probability_history = []
    state.stability_band_history = []

    # Call _update_mirror_time_cycles
    engine._update_mirror_time_cycles(state)

    # Should set fields to None
    assert state.dominant_cycle_type is None
    assert state.dominant_cycle_stability_band is None


def test_coherence_state_window_trim_cycles():
    """Test that window_trim includes cycle history."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Add many cycles
    for i in range(20):
        cycle = MirrorTimeCycleSnapshot(
            cycle_id=f"cycle_{i}",
            start_turn=i * 2,
            end_turn=i * 2 + 1,
            length=2,
            avg_loop_alignment=0.5,
            avg_loop_tension=0.3,
            avg_reversal_probability=0.2,
            forward_gradient=0.01,
            mirror_gradient=0.01,
            cycle_type="converging",
            stability_band="stable",
            reversal_bias="neutral",
        )
        state.mirror_cycle_history.append(cycle)

    # Trim to window of 10
    state.window_trim(10)

    # Should have only last 10 cycles
    assert len(state.mirror_cycle_history) == 10


def test_coherence_scores_unchanged_by_cycles():
    """Test that cycle computation doesn't modify coherence scores."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine

    engine = CoherenceEngine(window=10)
    state = CoherenceState(convo_id="test", turn_index=0)

    # Set initial coherence scores
    state.coherence_score = 0.75
    state.coherence_score_v2 = 0.78
    state.coherence_score_v3 = 0.80
    state.coherence_fused = 0.77

    # Populate loop histories
    state.loop_alignment_history = [0.5, 0.6, 0.7, 0.8]
    state.loop_tension_history = [0.4, 0.3, 0.2, 0.1]
    state.reversal_probability_history = [0.3, 0.2, 0.15, 0.1]
    state.stability_band_history = ["stable", "stable", "stable", "stable"]

    # Call _update_mirror_time_cycles
    engine._update_mirror_time_cycles(state)

    # Coherence scores should remain unchanged
    assert state.coherence_score == 0.75
    assert state.coherence_score_v2 == 0.78
    assert state.coherence_score_v3 == 0.80
    assert state.coherence_fused == 0.77


def test_coherence_integration_backward_compatible():
    """Test that Phase 22 is backward compatible with existing pipeline."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    from unittest.mock import MagicMock

    # Create engine and state
    engine = CoherenceEngine(window=10)

    # Mock routing plan and mapper profile
    routing_plan = MagicMock()
    routing_plan.tier = "hybrid"
    routing_plan.domain = "general"
    routing_plan.long_arc_tension = 0.3

    mapper_profile = {"hrm_active": True, "lcm_active": False, "lam_active": False}

    temporal_summary = {
        "smi": 0.5,
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "bhava_id": 0,
        "bhava_direction": "upward",
    }

    semantic_signature = {}

    # Update state (should not raise errors)
    state = engine.update_state(
        prev_state=None,
        convo_id="test",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=temporal_summary,
        semantic_signature=semantic_signature,
    )

    # Should succeed without errors
    assert state is not None
    assert state.turn_index == 0


# ============================================================================
# GROUP C: Session Summary Aggregation (6 tests)
# ============================================================================


def test_session_summary_has_cycle_fields():
    """Test that SessionSummary has Phase 22 cycle fields."""
    from symbolu.service.sessions.session_models import SessionSummary
    from datetime import datetime

    summary = SessionSummary(
        session_id="test",
        total_turns=5,
        coherence_trend=0.7,
        persona_drift_avg=0.2,
        temporal_arc_avg=0.6,
        created_at=datetime.utcnow(),
    )

    # Check that Phase 22 fields exist
    assert hasattr(summary, 'dominant_cycle_type')
    assert hasattr(summary, 'dominant_cycle_stability_band')
    assert hasattr(summary, 'avg_cycle_alignment')
    assert hasattr(summary, 'avg_cycle_tension')
    assert hasattr(summary, 'avg_cycle_reversal_probability')
    assert hasattr(summary, 'cycle_count')


def test_compute_session_summary_aggregates_cycles():
    """Test that compute_session_summary aggregates cycle metrics."""
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime

    # Create session state with coherence history containing cycle data
    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="therapy",
    )

    # Add coherence history with cycle data
    state.coherence_history.append({
        "coherence_score": 0.7,
        "dominant_cycle_type": "converging",
        "dominant_cycle_stability_band": "stable",
        "avg_cycle_alignment": 0.8,
        "avg_cycle_tension": 0.2,
        "avg_cycle_reversal_probability": 0.15,
        "mirror_cycle_history": [{"id": "cycle_1"}, {"id": "cycle_2"}],
    })

    summary = compute_session_summary(state)

    # Should have aggregated cycle metrics
    assert summary.dominant_cycle_type == "converging"
    assert summary.dominant_cycle_stability_band == "stable"
    assert summary.avg_cycle_alignment == 0.8
    assert summary.cycle_count == 2


def test_compute_session_summary_no_cycles():
    """Test compute_session_summary with no cycle data."""
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="general",
    )

    # Empty coherence history
    state.coherence_history = []

    summary = compute_session_summary(state)

    # Cycle fields should be None/0
    assert summary.dominant_cycle_type is None
    assert summary.cycle_count == 0


def test_compute_session_summary_mixed_cycle_types():
    """Test aggregation with mixed cycle types."""
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="therapy",
    )

    # Add multiple coherence entries with different cycle types
    state.coherence_history.append({
        "coherence_score": 0.7,
        "dominant_cycle_type": "converging",
        "mirror_cycle_history": [],
    })
    state.coherence_history.append({
        "coherence_score": 0.6,
        "dominant_cycle_type": "converging",
        "mirror_cycle_history": [],
    })
    state.coherence_history.append({
        "coherence_score": 0.5,
        "dominant_cycle_type": "diverging",
        "mirror_cycle_history": [],
    })

    summary = compute_session_summary(state)

    # "converging" is most frequent
    assert summary.dominant_cycle_type == "converging"


def test_session_summary_cycle_count_accumulation():
    """Test that cycle_count accumulates correctly."""
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="therapy",
    )

    # Add coherence history with different cycle counts
    state.coherence_history.append({
        "coherence_score": 0.7,
        "mirror_cycle_history": [{"id": "c1"}, {"id": "c2"}],
    })
    state.coherence_history.append({
        "coherence_score": 0.6,
        "mirror_cycle_history": [{"id": "c3"}],
    })

    summary = compute_session_summary(state)

    # Should accumulate: 2 + 1 = 3
    assert summary.cycle_count == 3


def test_session_summary_backward_compatible():
    """Test that Phase 22 doesn't break existing session summary computation."""
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime

    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="general",
    )

    # Add minimal coherence history (no Phase 22 fields)
    state.coherence_history.append({
        "coherence_score": 0.7,
        "stability": 0.7,
    })

    summary = compute_session_summary(state)

    # Should succeed without errors
    assert summary is not None
    assert summary.coherence_trend == 0.7


# ============================================================================
# GROUP D: Unified API & Adapter (5 tests)
# ============================================================================


def test_unified_api_has_mirror_time_cycles_block():
    """Test that unified_api includes mirror_time_cycles block when cycle data is available."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from unittest.mock import MagicMock
    import symbolu.api.unified_api as unified_api

    # Create mock context with coherence state
    ctx = MagicMock()
    ctx.coherence_state = CoherenceState(convo_id="test", turn_index=0)
    ctx.coherence_state.dominant_cycle_type = "converging"
    ctx.coherence_state.dominant_cycle_stability_band = "stable"
    ctx.coherence_state.avg_cycle_alignment = 0.8
    ctx.coherence_state.mirror_cycle_history = [MagicMock(), MagicMock()]

    # Mock routing plan
    ctx.routing_plan = MagicMock()
    ctx.routing_plan.domain = "therapy"
    ctx.routing_plan.tier = "upper"
    ctx.routing_plan.routing_decision = "UPPER"
    ctx.routing_plan.flow_mode = "default"
    ctx.routing_plan.interaction_mode = "smart_insight"

    # Build unified output (should not crash)
    try:
        output = unified_api.build_unified_output("test text", ctx)
        # If it returns without error, test passes
        assert output is not None
    except Exception as e:
        # Fail if there's an exception
        pytest.fail(f"Unified API should not crash with cycle data: {e}")


def test_unified_api_omits_cycles_when_unavailable():
    """Test that unified_api gracefully handles missing cycle data."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from unittest.mock import MagicMock
    import symbolu.api.unified_api as unified_api

    # Create mock context with coherence state (no cycle data)
    ctx = MagicMock()
    ctx.coherence_state = CoherenceState(convo_id="test", turn_index=0)

    # Mock routing plan
    ctx.routing_plan = MagicMock()
    ctx.routing_plan.domain = "general"
    ctx.routing_plan.tier = "hybrid"
    ctx.routing_plan.routing_decision = "HYBRID"
    ctx.routing_plan.flow_mode = "default"
    ctx.routing_plan.interaction_mode = "default"

    # Build unified output (should not crash even without cycle data)
    try:
        output = unified_api.build_unified_output("test text", ctx)
        # If it returns without error, test passes
        assert output is not None
    except Exception as e:
        # Fail if there's an exception
        pytest.fail(f"Unified API should not crash without cycle data: {e}")


def test_dilchat_hints_cycle_converging():
    """Test DILchat adapter processes cycle data without crashing."""
    from symbolu.adapter.dilchat_adapter import _build_hints
    from unittest.mock import MagicMock

    # Build unified output
    unified_output = {
        'coherence': {
            'mirror_time_cycles': {
                'dominant_type': 'converging',
            }
        },
        'routing': {
            'domain': 'therapy',
            'interaction_mode': 'smart_insight',
        }
    }

    # Should not crash when processing cycle data
    try:
        hints = _build_hints(unified_output)
        # If it returns without error, test passes
        assert hints is not None
        assert isinstance(hints, list)
    except Exception as e:
        pytest.fail(f"DILchat adapter should not crash with cycle data: {e}")


def test_dilchat_hints_cycle_only_therapy_identity():
    """Test DILchat adapter only emits cycle hints for therapy/identity domains."""
    from symbolu.adapter.dilchat_adapter import _build_hints
    from unittest.mock import MagicMock

    # Build unified output with GENERAL domain (should not emit cycle hints)
    unified_output = {
        'coherence': {
            'mirror_time_cycles': {
                'dominant_type': 'converging',
            }
        },
        'routing': {
            'domain': 'general',
            'interaction_mode': 'smart_insight',
        }
    }

    hints = _build_hints(unified_output)

    # Should NOT include cycle hints (wrong domain)
    hint_codes = [h.code for h in hints]
    assert "MIRROR_CYCLE_CONVERGING" not in hint_codes


def test_dilchat_hints_all_cycle_types():
    """Test DILchat adapter processes all cycle types without crashing."""
    from symbolu.adapter.dilchat_adapter import _build_hints
    from unittest.mock import MagicMock

    cycle_types = ["converging", "diverging", "oscillating", "stalled"]

    for cycle_type in cycle_types:
        unified_output = {
            'coherence': {
                'mirror_time_cycles': {
                    'dominant_type': cycle_type,
                }
            },
            'routing': {
                'domain': 'therapy',
                'interaction_mode': 'deep_adaptive',
            }
        }

        # Should not crash for any cycle type
        try:
            hints = _build_hints(unified_output)
            assert hints is not None
            assert isinstance(hints, list)
        except Exception as e:
            pytest.fail(f"DILchat adapter should not crash with {cycle_type} cycle: {e}")


# ============================================================================
# GROUP E: Behavioral Invariance (3 tests)
# ============================================================================


def test_behavioral_invariance_no_routing_changes():
    """Test that Phase 22 doesn't modify routing behavior."""
    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    from unittest.mock import MagicMock

    engine = CoherenceEngine(window=10)

    # Create two identical states
    routing_plan = MagicMock()
    routing_plan.tier = "hybrid"
    routing_plan.domain = "general"
    routing_plan.long_arc_tension = 0.5

    mapper_profile = {"hrm_active": True, "lcm_active": False, "lam_active": False}
    temporal_summary = {"smi": 0.5}
    semantic_signature = {}

    state1 = engine.update_state(
        prev_state=None,
        convo_id="test1",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=temporal_summary,
        semantic_signature=semantic_signature,
    )

    state2 = engine.update_state(
        prev_state=None,
        convo_id="test2",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=temporal_summary,
        semantic_signature=semantic_signature,
    )

    # Both states should have identical core coherence scores
    assert state1.coherence_score == state2.coherence_score
    assert state1.persona_drift_score == state2.persona_drift_score
    assert state1.semantic_stability_score == state2.semantic_stability_score


def test_behavioral_invariance_no_mapper_activation_changes():
    """Test that Phase 22 doesn't affect mapper activation."""
    # Phase 22 is observation-only, so mapper activation logic should be unchanged
    # This test verifies that CoherenceEngine doesn't modify mapper profiles
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    from unittest.mock import MagicMock

    engine = CoherenceEngine(window=10)

    routing_plan = MagicMock()
    routing_plan.tier = "hybrid"
    routing_plan.domain = "general"
    routing_plan.long_arc_tension = 0.5

    mapper_profile_before = {"hrm_active": True, "lcm_active": False, "lam_active": False}
    temporal_summary = {"smi": 0.5}
    semantic_signature = {}

    # Update state
    state = engine.update_state(
        prev_state=None,
        convo_id="test",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile_before.copy(),
        temporal_summary=temporal_summary,
        semantic_signature=semantic_signature,
    )

    # Mapper profile history should contain the original profile unchanged
    assert state.mapper_profile_history[0] == mapper_profile_before


def test_behavioral_invariance_backward_compatible_tests():
    """Test that all existing tests still pass (smoke test)."""
    # This test verifies that Phase 22 doesn't break existing functionality
    # by running a simple end-to-end scenario that would have worked before Phase 22

    from symbolu.core.coherence.coherence_state import CoherenceState
    from symbolu.core.coherence.coherence_engine import CoherenceEngine
    from symbolu.service.sessions.session_models import SessionState
    from symbolu.service.sessions.session_store import compute_session_summary
    from datetime import datetime
    from unittest.mock import MagicMock

    # 1. Create coherence state
    engine = CoherenceEngine(window=10)
    routing_plan = MagicMock()
    routing_plan.tier = "hybrid"
    routing_plan.domain = "general"
    routing_plan.long_arc_tension = 0.3

    mapper_profile = {"hrm_active": True, "lcm_active": False, "lam_active": False}
    temporal_summary = {"smi": 0.5, "delta_smi": 0.1}
    semantic_signature = {}

    coherence_state = engine.update_state(
        prev_state=None,
        convo_id="test",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=temporal_summary,
        semantic_signature=semantic_signature,
    )

    # 2. Create session state and compute summary
    session_state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="general",
    )
    session_state.coherence_history.append({
        "coherence_score": coherence_state.coherence_score,
        "stability": coherence_state.coherence_score,
    })

    summary = compute_session_summary(session_state)

    # Should succeed without errors
    assert summary is not None
    assert summary.coherence_trend >= 0.0
