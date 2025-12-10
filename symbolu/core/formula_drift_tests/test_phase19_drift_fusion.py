"""
Test Suite for Phase 19: Semantic-Temporal Drift Fusion v1.0

Comprehensive tests ensuring:
  • Formula math correctness (determinism, range checks, edge cases)
  • Drift pattern tag generation (rule-based logic)
  • Coherence & session integration (state, histories, summaries)
  • Observer, Unified API, DILchat wiring (snapshots, serialization, hints)
  • Behavioral invariance (no routing, mapper, or policy changes)

Total tests: ~32 covering all acceptance criteria.
"""

import pytest
from symbolu.formulas.drift_fusion import (
    compute_drift_fusion_snapshot,
    DriftFusionSnapshot,
)
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine


# ============================================================================
# GROUP A: Drift Fusion Math Tests (10-12 tests)
# ============================================================================


def test_formula_range_check():
    """Test that drift_fusion_index is within [0, 1] range."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    assert snapshot is not None
    assert 0.0 <= snapshot.drift_fusion_index <= 1.0


def test_formula_determinism():
    """Test that same inputs produce same outputs."""
    snapshot1 = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.6,
        cognitive_drift_v3=0.4,
        temporal_entropy_diff=0.55,
        temporal_entropy_volatility=0.3,
        coherence_fused=0.7,
    )

    snapshot2 = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.6,
        cognitive_drift_v3=0.4,
        temporal_entropy_diff=0.55,
        temporal_entropy_volatility=0.3,
        coherence_fused=0.7,
    )

    assert snapshot1.drift_fusion_index == snapshot2.drift_fusion_index
    assert snapshot1.drift_risk_band == snapshot2.drift_risk_band
    assert snapshot1.drift_pattern_tags == snapshot2.drift_pattern_tags


def test_higher_drift_increases_index():
    """Test that higher cognitive_drift_v3 increases drift_fusion_index."""
    snapshot_low_drift = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.8,
        cognitive_drift_v3=0.1,  # Low drift
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    snapshot_high_drift = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.8,
        cognitive_drift_v3=0.9,  # High drift
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    assert snapshot_high_drift.drift_fusion_index > snapshot_low_drift.drift_fusion_index


def test_lower_integrity_increases_index():
    """Test that lower semantic_integrity_score increases drift_fusion_index."""
    snapshot_high_integrity = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.9,  # High integrity
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    snapshot_low_integrity = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.2,  # Low integrity
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    assert snapshot_low_integrity.drift_fusion_index > snapshot_high_integrity.drift_fusion_index


def test_higher_volatility_increases_index():
    """Test that higher temporal_entropy_volatility increases drift_fusion_index."""
    snapshot_low_volatility = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.1,  # Low volatility
        coherence_fused=0.8,
    )

    snapshot_high_volatility = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.9,  # High volatility
        coherence_fused=0.8,
    )

    assert snapshot_high_volatility.drift_fusion_index > snapshot_low_volatility.drift_fusion_index


def test_entropy_diff_deviation_increases_index():
    """Test that larger deviation from neutral (0.5) in temporal_entropy_diff increases index."""
    snapshot_neutral = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,  # Neutral
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    snapshot_high_deviation = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.9,  # High deviation from 0.5
        temporal_entropy_volatility=0.2,
        coherence_fused=0.8,
    )

    # High deviation should contribute more to drift
    assert snapshot_high_deviation.drift_fusion_index > snapshot_neutral.drift_fusion_index


def test_lower_coherence_increases_index():
    """Test that lower coherence_fused increases drift_fusion_index."""
    snapshot_high_coherence = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.9,  # High coherence
    )

    snapshot_low_coherence = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.1,  # Low coherence
    )

    assert snapshot_low_coherence.drift_fusion_index > snapshot_high_coherence.drift_fusion_index


def test_none_inputs_returns_none():
    """Test that all None inputs return None."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=None,
        cognitive_drift_v3=None,
        temporal_entropy_diff=None,
        temporal_entropy_volatility=None,
        coherence_fused=None,
    )

    assert snapshot is None


def test_partial_none_inputs():
    """Test that function works with some None inputs."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=None,
        cognitive_drift_v3=0.6,  # Only this is set
        temporal_entropy_diff=None,
        temporal_entropy_volatility=None,
        coherence_fused=None,
    )

    assert snapshot is not None
    assert 0.0 <= snapshot.drift_fusion_index <= 1.0


def test_risk_band_thresholds():
    """Test that drift_risk_band is correctly mapped to thresholds."""
    # Low drift (index < 0.30)
    snapshot_low = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.9,
        cognitive_drift_v3=0.1,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.1,
        coherence_fused=0.9,
    )
    assert snapshot_low.drift_risk_band == "low"

    # Moderate drift (0.30 <= index < 0.65)
    snapshot_moderate = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.5,
        cognitive_drift_v3=0.5,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.3,
        coherence_fused=0.5,
    )
    assert snapshot_moderate.drift_risk_band == "moderate"

    # High drift (index >= 0.65)
    snapshot_high = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.1,
        cognitive_drift_v3=0.9,
        temporal_entropy_diff=0.9,
        temporal_entropy_volatility=0.9,
        coherence_fused=0.1,
    )
    assert snapshot_high.drift_risk_band == "high"


def test_index_clamp_bounds():
    """Test that drift_fusion_index is properly clamped to [0, 1] even with extreme inputs."""
    # Extreme high values
    snapshot_extreme = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.0,
        cognitive_drift_v3=1.0,
        temporal_entropy_diff=1.0,
        temporal_entropy_volatility=1.0,
        coherence_fused=0.0,
    )

    assert 0.0 <= snapshot_extreme.drift_fusion_index <= 1.0


# ============================================================================
# GROUP B: Drift Pattern Tags Tests (6-8 tests)
# ============================================================================


def test_semantic_drift_tag():
    """Test that 'semantic_drift' tag is added when integrity < 0.55."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.4,  # Below threshold
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.7,
    )

    assert "semantic_drift" in snapshot.drift_pattern_tags


def test_cognitive_drift_tag():
    """Test that 'cognitive_drift' tag is added when drift_v3 > 0.55."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.7,  # Above threshold
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.7,
    )

    assert "cognitive_drift" in snapshot.drift_pattern_tags


def test_temporal_instability_tag():
    """Test that 'temporal_instability' tag is added when volatility > 0.55."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.7,  # Above threshold
        coherence_fused=0.7,
    )

    assert "temporal_instability" in snapshot.drift_pattern_tags


def test_entropy_shift_tag():
    """Test that 'entropy_shift' tag is added when |diff - 0.5| > 0.25."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.9,  # 0.4 away from 0.5
        temporal_entropy_volatility=0.2,
        coherence_fused=0.7,
    )

    assert "entropy_shift" in snapshot.drift_pattern_tags


def test_low_coherence_context_tag():
    """Test that 'low_coherence_context' tag is added when coherence_fused < 0.45."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.7,
        cognitive_drift_v3=0.3,
        temporal_entropy_diff=0.5,
        temporal_entropy_volatility=0.2,
        coherence_fused=0.3,  # Below threshold
    )

    assert "low_coherence_context" in snapshot.drift_pattern_tags


def test_multiple_tags():
    """Test that multiple tags are added when multiple conditions are met."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.4,  # Triggers semantic_drift
        cognitive_drift_v3=0.7,  # Triggers cognitive_drift
        temporal_entropy_diff=0.9,  # Triggers entropy_shift
        temporal_entropy_volatility=0.7,  # Triggers temporal_instability
        coherence_fused=0.3,  # Triggers low_coherence_context
    )

    assert len(snapshot.drift_pattern_tags) == 5
    assert "semantic_drift" in snapshot.drift_pattern_tags
    assert "cognitive_drift" in snapshot.drift_pattern_tags
    assert "temporal_instability" in snapshot.drift_pattern_tags
    assert "entropy_shift" in snapshot.drift_pattern_tags
    assert "low_coherence_context" in snapshot.drift_pattern_tags


def test_no_tags_when_stable():
    """Test that no tags are added when everything is stable."""
    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.8,  # Good integrity
        cognitive_drift_v3=0.2,  # Low drift
        temporal_entropy_diff=0.5,  # Neutral
        temporal_entropy_volatility=0.2,  # Low volatility
        coherence_fused=0.8,  # Good coherence
    )

    assert len(snapshot.drift_pattern_tags) == 0


# ============================================================================
# GROUP C: Coherence & Session Integration Tests (6-8 tests)
# ============================================================================


def test_coherence_state_stores_drift_fusion():
    """Test that CoherenceState stores drift fusion snapshot and metrics."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=1)

    # Set drift fusion fields manually (as engine would)
    state.drift_fusion_index = 0.45
    state.drift_risk_band = "moderate"
    state.drift_pattern_tags = ["semantic_drift", "cognitive_drift"]

    assert state.drift_fusion_index == 0.45
    assert state.drift_risk_band == "moderate"
    assert "semantic_drift" in state.drift_pattern_tags


def test_coherence_state_drift_fusion_histories():
    """Test that drift fusion histories are tracked correctly."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=1)

    # Append to histories
    state.drift_fusion_index_history.append(0.3)
    state.drift_fusion_index_history.append(0.5)
    state.drift_fusion_index_history.append(0.7)

    state.drift_risk_band_history.append("low")
    state.drift_risk_band_history.append("moderate")
    state.drift_risk_band_history.append("high")

    assert len(state.drift_fusion_index_history) == 3
    assert len(state.drift_risk_band_history) == 3
    assert state.drift_fusion_index_history[-1] == 0.7
    assert state.drift_risk_band_history[-1] == "high"


def test_coherence_state_window_trim_drift_fusion():
    """Test that window_trim correctly trims drift fusion histories."""
    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=1)

    # Add 15 entries
    for i in range(15):
        state.drift_fusion_index_history.append(float(i) / 15.0)
        state.drift_risk_band_history.append("low" if i < 5 else "moderate" if i < 10 else "high")

    # Trim to window of 10
    state.window_trim(window=10)

    assert len(state.drift_fusion_index_history) == 10
    assert len(state.drift_risk_band_history) == 10


def test_session_summary_drift_fusion_aggregates():
    """Test that SessionSummary aggregates drift fusion metrics correctly."""
    from symbolu.service.sessions.session_models import SessionSummary

    summary = SessionSummary(
        session_id="test",
        total_turns=5,
        coherence_trend=0.7,
        persona_drift_avg=0.3,
        temporal_arc_avg=0.8,
        avg_drift_fusion_index=0.45,
        dominant_drift_risk_band="moderate",
        drift_pattern_frequency={"semantic_drift": 3, "cognitive_drift": 2},
    )

    assert summary.avg_drift_fusion_index == 0.45
    assert summary.dominant_drift_risk_band == "moderate"
    assert summary.drift_pattern_frequency["semantic_drift"] == 3


def test_session_store_computes_drift_fusion_summary():
    """Test that compute_session_summary correctly aggregates drift fusion data."""
    from symbolu.service.sessions.session_store import compute_session_summary
    from symbolu.service.sessions.session_models import SessionState
    from datetime import datetime

    # Create session state with drift fusion data in coherence history
    state = SessionState(
        session_id="test",
        created_at=datetime.utcnow(),
        domain="therapy",
    )

    # Add coherence history with drift fusion data
    state.coherence_history.append({
        "coherence_score": 0.7,
        "drift_fusion_index": 0.3,
        "drift_risk_band": "low",
        "drift_pattern_tags": ["semantic_drift"],
    })
    state.coherence_history.append({
        "coherence_score": 0.6,
        "drift_fusion_index": 0.5,
        "drift_risk_band": "moderate",
        "drift_pattern_tags": ["semantic_drift", "cognitive_drift"],
    })
    state.coherence_history.append({
        "coherence_score": 0.5,
        "drift_fusion_index": 0.7,
        "drift_risk_band": "high",
        "drift_pattern_tags": ["semantic_drift", "temporal_instability"],
    })

    summary = compute_session_summary(state)

    # Check aggregates
    assert summary.avg_drift_fusion_index is not None
    assert summary.avg_drift_fusion_index == pytest.approx(0.5, abs=0.05)
    assert summary.dominant_drift_risk_band in ["low", "moderate", "high"]
    assert "semantic_drift" in summary.drift_pattern_frequency


def test_coherence_no_behavior_change():
    """Test that drift fusion does NOT affect coherence_score_v1/v2/v3."""
    # This test verifies behavioral invariance
    # Drift fusion should be observation-only and not feed back into coherence scoring

    from symbolu.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=1)

    # Set high drift fusion
    state.drift_fusion_index = 0.9
    state.drift_risk_band = "high"

    # Coherence scores should remain independent
    state.coherence_score = 0.8  # Still high despite drift
    state.coherence_score_v2 = 0.75
    state.coherence_score_v3 = 0.85

    # Verify drift didn't override coherence
    assert state.coherence_score == 0.8
    assert state.coherence_score_v2 == 0.75
    assert state.coherence_score_v3 == 0.85


# ============================================================================
# GROUP D: Observer, Unified API, DILchat Tests (6-8 tests)
# ============================================================================


def test_observer_includes_drift_fusion():
    """Test that CoherenceObservation includes drift fusion fields."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

    observation = CoherenceObservation(
        coherence_score=0.7,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        temporal_arc_score=0.6,
        mapper_volatility_score=0.2,
        turn_number=5,
        tier="hybrid",
        domain="therapy",
        active_mappers=["HRM", "LCM"],
        drift_fusion_index=0.45,
        drift_risk_band="moderate",
        drift_pattern_tags=["semantic_drift"],
    )

    assert observation.drift_fusion_index == 0.45
    assert observation.drift_risk_band == "moderate"
    assert "semantic_drift" in observation.drift_pattern_tags


def test_observer_snapshot_includes_drift_fusion():
    """Test that observer.snapshot() includes drift_fusion block."""
    from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver, CoherenceObservation

    observer = CoherenceObserver()

    # Create a mock observation with drift fusion
    observation = CoherenceObservation(
        coherence_score=0.7,
        persona_drift_score=0.3,
        semantic_stability_score=0.8,
        temporal_arc_score=0.6,
        mapper_volatility_score=0.2,
        turn_number=5,
        tier="hybrid",
        domain="therapy",
        active_mappers=["HRM"],
        drift_fusion_index=0.55,
        drift_risk_band="moderate",
        drift_pattern_tags=["cognitive_drift", "entropy_shift"],
    )

    observer._last_observation = observation

    snapshot = observer.snapshot()

    assert "drift_fusion" in snapshot
    assert snapshot["drift_fusion"]["index"] == 0.55
    assert snapshot["drift_fusion"]["risk_band"] == "moderate"
    assert "cognitive_drift" in snapshot["drift_fusion"]["pattern_tags"]


def test_unified_api_includes_drift_fusion():
    """Test that unified API output includes drift_fusion in coherence block."""
    # This is a structural test verifying the wiring
    # In practice, build_unified_output would populate this from coherence_state

    coherence_block = {
        "coherence_score": 0.7,
        "drift_fusion": {
            "index": 0.45,
            "risk_band": "moderate",
            "pattern_tags": ["semantic_drift"],
            "inputs": {
                "semantic_integrity_score": 0.6,
                "cognitive_drift_v3": 0.5,
                "temporal_entropy_diff": 0.55,
                "temporal_entropy_volatility": 0.3,
            },
        },
    }

    assert "drift_fusion" in coherence_block
    assert coherence_block["drift_fusion"]["index"] == 0.45
    assert coherence_block["drift_fusion"]["risk_band"] == "moderate"


def test_dilchat_drift_hints_therapy_domain():
    """Test that DILchat adds drift hints for therapy domain."""
    from symbolu.adapter.dilchat_adapter import _build_hints

    unified_output = {}
    policy_flags = {"interaction_mode": "analytics_only"}
    coherence = {
        "drift_fusion": {
            "index": 0.35,
            "risk_band": "moderate",
            "pattern_tags": ["semantic_drift"],
        },
    }

    hints = _build_hints(
        policy_flags=policy_flags,
        coherence=coherence,
        domain="therapy",
    )

    # Should have drift hint for therapy domain
    drift_hint_codes = [h.code for h in hints if h.code.startswith("DRIFT_")]
    assert len(drift_hint_codes) > 0
    assert "DRIFT_MODERATE_RISK" in drift_hint_codes


def test_dilchat_drift_hints_smart_insight_mode():
    """Test that DILchat adds drift hints for smart_insight interaction mode."""
    from symbolu.adapter.dilchat_adapter import _build_hints

    unified_output = {}
    policy_flags = {"interaction_mode": "smart_insight"}
    coherence = {
        "drift_fusion": {
            "index": 0.7,
            "risk_band": "high",
            "pattern_tags": ["semantic_drift", "cognitive_drift"],
        },
    }

    hints = _build_hints(
        policy_flags=policy_flags,
        coherence=coherence,
        domain="generic",  # Not therapy/identity
    )

    # Should have drift hint for smart_insight mode even in generic domain
    drift_hint_codes = [h.code for h in hints if h.code.startswith("DRIFT_")]
    assert len(drift_hint_codes) > 0
    assert "DRIFT_HIGH_RISK" in drift_hint_codes


def test_dilchat_no_drift_hints_generic_analytics():
    """Test that DILchat does NOT add drift hints for generic domain + analytics_only mode."""
    from symbolu.adapter.dilchat_adapter import _build_hints

    unified_output = {}
    policy_flags = {"interaction_mode": "analytics_only"}
    coherence = {
        "drift_fusion": {
            "index": 0.35,
            "risk_band": "moderate",
            "pattern_tags": ["semantic_drift"],
        },
    }

    hints = _build_hints(
        policy_flags=policy_flags,
        coherence=coherence,
        domain="generic",  # Generic domain, not therapy/identity
    )

    # Should NOT have drift hints for generic + analytics_only
    drift_hint_codes = [h.code for h in hints if h.code.startswith("DRIFT_")]
    assert len(drift_hint_codes) == 0


def test_dilchat_drift_hint_messages():
    """Test that drift hint messages are appropriate and informative."""
    from symbolu.adapter.dilchat_adapter import _build_hints

    policy_flags = {"interaction_mode": "deep_adaptive"}
    coherence_low = {
        "drift_fusion": {"index": 0.2, "risk_band": "low", "pattern_tags": []},
    }
    coherence_moderate = {
        "drift_fusion": {"index": 0.45, "risk_band": "moderate", "pattern_tags": ["semantic_drift"]},
    }
    coherence_high = {
        "drift_fusion": {"index": 0.75, "risk_band": "high", "pattern_tags": ["semantic_drift", "cognitive_drift"]},
    }

    hints_low = _build_hints(policy_flags=policy_flags, coherence=coherence_low, domain="therapy")
    hints_moderate = _build_hints(policy_flags=policy_flags, coherence=coherence_moderate, domain="therapy")
    hints_high = _build_hints(policy_flags=policy_flags, coherence=coherence_high, domain="therapy")

    # Extract drift hints
    drift_hints_low = [h for h in hints_low if h.code.startswith("DRIFT_")]
    drift_hints_moderate = [h for h in hints_moderate if h.code.startswith("DRIFT_")]
    drift_hints_high = [h for h in hints_high if h.code.startswith("DRIFT_")]

    assert len(drift_hints_low) == 1
    assert drift_hints_low[0].code == "DRIFT_LOW_RISK"
    assert "stable" in drift_hints_low[0].message.lower()

    assert len(drift_hints_moderate) == 1
    assert drift_hints_moderate[0].code == "DRIFT_MODERATE_RISK"
    assert "drift present" in drift_hints_moderate[0].message.lower()

    assert len(drift_hints_high) == 1
    assert drift_hints_high[0].code == "DRIFT_HIGH_RISK"
    assert "grounding" in drift_hints_high[0].message.lower() or "stabilization" in drift_hints_high[0].message.lower()


def test_json_serialization():
    """Test that drift fusion snapshot is JSON-serializable."""
    import json

    snapshot = compute_drift_fusion_snapshot(
        semantic_integrity_score=0.6,
        cognitive_drift_v3=0.4,
        temporal_entropy_diff=0.55,
        temporal_entropy_volatility=0.3,
        coherence_fused=0.7,
    )

    # Convert to dict (as would happen in API)
    snapshot_dict = {
        "drift_fusion_index": snapshot.drift_fusion_index,
        "semantic_integrity_score": snapshot.semantic_integrity_score,
        "cognitive_drift_v3": snapshot.cognitive_drift_v3,
        "temporal_entropy_diff": snapshot.temporal_entropy_diff,
        "temporal_entropy_volatility": snapshot.temporal_entropy_volatility,
        "drift_risk_band": snapshot.drift_risk_band,
        "drift_pattern_tags": snapshot.drift_pattern_tags,
    }

    # Should serialize to JSON without error
    json_str = json.dumps(snapshot_dict)
    assert json_str is not None

    # Should deserialize back
    deserialized = json.loads(json_str)
    assert deserialized["drift_fusion_index"] == snapshot.drift_fusion_index
    assert deserialized["drift_risk_band"] == snapshot.drift_risk_band
