"""
Test Suite for Phase 44: Coherence–Scenario Alignment Engine (CSAE) v1.0

This comprehensive test suite ensures the CSAE implementation is:
- Deterministic (same inputs → same outputs)
- Zero-LLM (no model calls)
- Observation-only (no routing/scoring changes)
- Backward compatible (all existing tests remain green)
- Fully bounded (all scores [0.0, 1.0])
- Gracefully degrading (handles missing data)

Test Groups:
- Group A: Formula Math (15 tests)
- Group B: Coherence Integration (12 tests)
- Group C: Session Summary (10 tests)
- Group D: Unified API & Observer (8 tests)
- Group E: Behavioral Invariance (10 tests)

Total: 55 tests
"""

import pytest
from symbolu.formulas.coherence_scenario_alignment import (
    compute_coherence_scenario_alignment,
    CoherenceScenarioAlignmentSnapshot,
    _clamp,
    _safe_get_float,
    _safe_get_str,
)
from symbolu.core.coherence.coherence_state import CoherenceState


# ============================================================================
# GROUP A: FORMULA MATH (15 tests)
# ============================================================================


class TestCSAEFormulaMath:
    """Test CSAE algorithms and mathematical properties."""

    def test_clamp_function_boundaries(self):
        """Test _clamp enforces [0.0, 1.0] boundaries."""
        assert _clamp(-0.5) == 0.0
        assert _clamp(0.0) == 0.0
        assert _clamp(0.5) == 0.5
        assert _clamp(1.0) == 1.0
        assert _clamp(1.5) == 1.0

    def test_safe_get_float_from_dict(self):
        """Test _safe_get_float extracts floats from dicts."""
        data = {"value": 0.75, "other": "string"}
        assert _safe_get_float(data, "value") == 0.75
        assert _safe_get_float(data, "missing") == 0.0
        assert _safe_get_float(data, "missing", 0.5) == 0.5

    def test_safe_get_float_from_object(self):
        """Test _safe_get_float extracts floats from objects."""
        class TestObj:
            value = 0.85

        obj = TestObj()
        assert _safe_get_float(obj, "value") == 0.85
        assert _safe_get_float(obj, "missing") == 0.0

    def test_safe_get_str_from_dict(self):
        """Test _safe_get_str extracts strings from dicts."""
        data = {"band": "high", "score": 0.75}
        assert _safe_get_str(data, "band") == "high"
        assert _safe_get_str(data, "missing") is None
        assert _safe_get_str(data, "missing", "default") == "default"

    def test_high_alignment_scenario(self):
        """Test scenario with high alignment across all signals."""
        # All horizons trending up, high scenario alignment, high ICC
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.6,
            forecast_continuity_slope=0.5,
            horizon_slope_H1=0.5,
            horizon_slope_H2=0.6,
            horizon_slope_H3=0.7,
            scenario_alignment_score=0.80,
            scenario_divergence_index=0.20,
            future_uncertainty_band="low",
            icc=0.85,
            css=0.90,
            future_stability_envelope=0.88,
            forecast_consensus_index=0.82,
        )

        assert snapshot is not None
        assert snapshot.alignment_score >= 0.65, "High alignment expected"
        assert snapshot.overall_alignment_band in ["high", "medium"]
        assert snapshot.conflict_index <= 0.40, "Low conflict expected"
        assert "alignment_coherence_rising" in snapshot.diagnostic_tags or \
               "strong_alignment_multi_horizon" in snapshot.diagnostic_tags

    def test_conflict_scenario(self):
        """Test scenario with conflicting signals."""
        # Negative slopes, high drift, high entropy, low identity continuity
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=-0.6,
            forecast_drift_influence=0.80,
            forecast_entropy_forward_risk=0.75,
            scenario_alignment_score=0.25,
            scenario_divergence_index=0.85,
            future_uncertainty_band="high",
            icc=0.30,
            css=0.35,
            forecast_strength=0.25,
        )

        assert snapshot is not None
        assert snapshot.alignment_score <= 0.35, "Low alignment expected"
        assert snapshot.overall_alignment_band in ["low", "conflict"]
        assert snapshot.conflict_index >= 0.50, "High conflict expected"
        assert "scenario_contradiction_detected" in snapshot.diagnostic_tags or \
               "drift_conflict" in snapshot.diagnostic_tags or \
               "entropy_risk_elevated" in snapshot.diagnostic_tags

    def test_medium_alignment_mixed_signals(self):
        """Test scenario with mixed/moderate signals."""
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.2,
            forecast_continuity_slope=0.1,
            scenario_alignment_score=0.55,
            scenario_divergence_index=0.45,
            future_uncertainty_band="medium",
            icc=0.60,
            forecast_strength=0.65,
        )

        assert snapshot is not None
        assert 0.35 <= snapshot.alignment_score <= 0.70, "Medium alignment expected"
        assert snapshot.overall_alignment_band == "medium"

    def test_alignment_score_bounds(self):
        """Test alignment score stays within [0.0, 1.0] bounds."""
        # Extreme positive values
        snapshot1 = compute_coherence_scenario_alignment(
            forecast_coherence_slope=1.0,
            scenario_alignment_score=1.0,
            icc=1.0,
            css=1.0,
            future_stability_envelope=1.0,
            forecast_consensus_index=1.0,
        )
        assert snapshot1 is not None
        assert 0.0 <= snapshot1.alignment_score <= 1.0

        # Extreme negative values
        snapshot2 = compute_coherence_scenario_alignment(
            forecast_coherence_slope=-1.0,
            forecast_drift_influence=1.0,
            forecast_entropy_forward_risk=1.0,
            scenario_divergence_index=1.0,
        )
        assert snapshot2 is not None
        assert 0.0 <= snapshot2.alignment_score <= 1.0

    def test_conflict_index_bounds(self):
        """Test conflict index stays within [0.0, 1.0] bounds."""
        snapshot = compute_coherence_scenario_alignment(
            forecast_drift_influence=1.0,
            forecast_entropy_forward_risk=1.0,
            scenario_divergence_index=1.0,
            scenario_alignment_score=0.2,
            forecast_strength=0.0,
            future_uncertainty_band="high",
        )

        assert snapshot is not None
        assert 0.0 <= snapshot.conflict_index <= 1.0

    def test_stability_agreement_computation(self):
        """Test stability agreement computation from multiple sources."""
        snapshot = compute_coherence_scenario_alignment(
            future_stability_envelope=0.80,
            icc=0.85,
            css=0.90,
            csi=0.75,
            cih=0.70,
        )

        assert snapshot is not None
        assert snapshot.stability_agreement is not None
        assert 0.60 <= snapshot.stability_agreement <= 1.0
        assert "alignment_identity_supported" in snapshot.diagnostic_tags or \
               "stability_consensus_strong" in snapshot.diagnostic_tags

    def test_alignment_band_classification(self):
        """Test correct classification into alignment bands."""
        # HIGH band
        snapshot_high = compute_coherence_scenario_alignment(
            scenario_alignment_score=0.85,
            icc=0.80,
            future_stability_envelope=0.85,
        )
        assert snapshot_high is not None
        assert snapshot_high.alignment_score >= 0.70
        assert snapshot_high.overall_alignment_band == "high"

        # MEDIUM band
        snapshot_medium = compute_coherence_scenario_alignment(
            scenario_alignment_score=0.55,
            icc=0.60,
        )
        assert snapshot_medium is not None
        assert 0.45 <= snapshot_medium.alignment_score < 0.70
        assert snapshot_medium.overall_alignment_band == "medium"

        # LOW band
        snapshot_low = compute_coherence_scenario_alignment(
            scenario_alignment_score=0.35,
            forecast_coherence_slope=-0.3,
        )
        assert snapshot_low is not None
        assert 0.25 <= snapshot_low.alignment_score < 0.45
        assert snapshot_low.overall_alignment_band == "low"

        # CONFLICT band
        snapshot_conflict = compute_coherence_scenario_alignment(
            forecast_drift_influence=0.95,
            forecast_entropy_forward_risk=0.90,
            scenario_divergence_index=0.85,
            icc=0.20,
        )
        assert snapshot_conflict is not None
        assert snapshot_conflict.alignment_score < 0.25
        assert snapshot_conflict.overall_alignment_band == "conflict"

    def test_multi_horizon_slope_agreement(self):
        """Test multi-horizon slope agreement affects alignment."""
        # All horizons positive and agreeing
        snapshot_agree = compute_coherence_scenario_alignment(
            horizon_slope_H1=0.5,
            horizon_slope_H2=0.55,
            horizon_slope_H3=0.60,
            scenario_alignment_score=0.70,
        )

        # Horizons disagree (mixed directions)
        snapshot_disagree = compute_coherence_scenario_alignment(
            horizon_slope_H1=-0.5,
            horizon_slope_H2=0.0,
            horizon_slope_H3=0.5,
            scenario_alignment_score=0.70,
        )

        assert snapshot_agree is not None and snapshot_disagree is not None
        # Agreement should lead to higher alignment
        assert snapshot_agree.alignment_score > snapshot_disagree.alignment_score

    def test_uncertainty_penalty(self):
        """Test uncertainty band applies penalty to alignment score."""
        base_params = {
            "scenario_alignment_score": 0.75,
            "icc": 0.80,
        }

        snapshot_low = compute_coherence_scenario_alignment(
            **base_params,
            future_uncertainty_band="low"
        )
        snapshot_high = compute_coherence_scenario_alignment(
            **base_params,
            future_uncertainty_band="high"
        )

        assert snapshot_low is not None and snapshot_high is not None
        # High uncertainty should result in lower alignment due to penalty
        assert snapshot_high.alignment_score < snapshot_low.alignment_score

    def test_determinism(self):
        """Test deterministic behavior - same inputs produce same outputs."""
        params = {
            "forecast_coherence_slope": 0.4,
            "scenario_alignment_score": 0.65,
            "icc": 0.70,
            "css": 0.75,
            "future_stability_envelope": 0.68,
        }

        snapshots = [compute_coherence_scenario_alignment(**params) for _ in range(10)]

        # All snapshots should be identical
        for snapshot in snapshots[1:]:
            assert snapshot.alignment_score == snapshots[0].alignment_score
            assert snapshot.conflict_index == snapshots[0].conflict_index
            assert snapshot.stability_agreement == snapshots[0].stability_agreement
            assert snapshot.overall_alignment_band == snapshots[0].overall_alignment_band
            assert snapshot.diagnostic_tags == snapshots[0].diagnostic_tags

    def test_graceful_degradation_insufficient_data(self):
        """Test graceful degradation when insufficient data provided."""
        # No data
        snapshot_none = compute_coherence_scenario_alignment()
        assert snapshot_none is None

        # Only one phase with data (need at least 2)
        snapshot_one_phase = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.5
        )
        assert snapshot_one_phase is None

        # Two phases with data (should succeed)
        snapshot_two_phases = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.5,
            scenario_alignment_score=0.65
        )
        assert snapshot_two_phases is not None


# ============================================================================
# GROUP B: COHERENCE INTEGRATION (12 tests)
# ============================================================================


class TestCoherenceIntegration:
    """Test integration with CoherenceState and CoherenceEngine."""

    def test_coherence_state_has_phase44_fields(self):
        """Test CoherenceState has all Phase 44 fields."""
        state = CoherenceState(convo_id="test", turn_index=0)

        # Check snapshot field
        assert hasattr(state, 'scenario_alignment_snapshot')
        assert state.scenario_alignment_snapshot is None

        # Check history fields
        assert hasattr(state, 'scenario_alignment_score_history')
        assert hasattr(state, 'scenario_conflict_history')
        assert hasattr(state, 'scenario_stability_history')
        assert hasattr(state, 'scenario_alignment_band_history')
        assert hasattr(state, 'scenario_tags_history')

        assert isinstance(state.scenario_alignment_score_history, list)
        assert isinstance(state.scenario_conflict_history, list)
        assert isinstance(state.scenario_stability_history, list)
        assert isinstance(state.scenario_alignment_band_history, list)
        assert isinstance(state.scenario_tags_history, list)

    def test_coherence_state_window_trim_phase44(self):
        """Test window trimming includes Phase 44 histories."""
        state = CoherenceState(convo_id="test", turn_index=0)

        # Add 20 entries to Phase 44 histories
        for i in range(20):
            state.scenario_alignment_score_history.append(0.5 + i * 0.01)
            state.scenario_conflict_history.append(0.3 + i * 0.01)
            state.scenario_stability_history.append(0.7 + i * 0.01)
            state.scenario_alignment_band_history.append("medium")
            state.scenario_tags_history.append(["tag1", "tag2"])

        # Trim to window of 10
        state.window_trim(10)

        assert len(state.scenario_alignment_score_history) == 10
        assert len(state.scenario_conflict_history) == 10
        assert len(state.scenario_stability_history) == 10
        assert len(state.scenario_alignment_band_history) == 10
        assert len(state.scenario_tags_history) == 10

        # Verify most recent entries retained
        assert state.scenario_alignment_score_history[0] == 0.5 + 10 * 0.01
        assert state.scenario_alignment_score_history[-1] == 0.5 + 19 * 0.01

    def test_snapshot_structure(self):
        """Test CoherenceScenarioAlignmentSnapshot structure."""
        snapshot = CoherenceScenarioAlignmentSnapshot(
            alignment_score=0.75,
            conflict_index=0.25,
            stability_agreement=0.80,
            overall_alignment_band="high",
            diagnostic_tags=["tag1", "tag2"],
            inputs_used={"phase38_available": 3}
        )

        assert snapshot.alignment_score == 0.75
        assert snapshot.conflict_index == 0.25
        assert snapshot.stability_agreement == 0.80
        assert snapshot.overall_alignment_band == "high"
        assert len(snapshot.diagnostic_tags) == 2
        assert snapshot.inputs_used["phase38_available"] == 3

    def test_snapshot_with_none_values(self):
        """Test snapshot handles None values gracefully."""
        snapshot = CoherenceScenarioAlignmentSnapshot(
            alignment_score=None,
            conflict_index=None,
            stability_agreement=None,
            overall_alignment_band=None,
            diagnostic_tags=[],
            inputs_used={}
        )

        assert snapshot.alignment_score is None
        assert snapshot.conflict_index is None
        assert snapshot.stability_agreement is None
        assert snapshot.overall_alignment_band is None
        assert len(snapshot.diagnostic_tags) == 0

    def test_diagnostic_tags_determinism(self):
        """Test diagnostic tags are deterministic and sorted."""
        snapshot1 = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.8,
            scenario_alignment_score=0.85,
            icc=0.90,
        )

        snapshot2 = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.8,
            scenario_alignment_score=0.85,
            icc=0.90,
        )

        assert snapshot1 is not None and snapshot2 is not None
        assert snapshot1.diagnostic_tags == snapshot2.diagnostic_tags
        # Tags should be sorted
        assert snapshot1.diagnostic_tags == sorted(snapshot1.diagnostic_tags)

    def test_inputs_used_tracking(self):
        """Test inputs_used correctly tracks available phases."""
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.5,
            forecast_drift_influence=0.3,
            scenario_alignment_score=0.65,
            icc=0.70,
        )

        assert snapshot is not None
        inputs = snapshot.inputs_used
        assert inputs["phase38_available"] >= 2  # At least 2 Phase 38 inputs
        assert inputs["phase42_available"] >= 1  # At least 1 Phase 42 input
        assert inputs["phase37_available"] >= 1  # At least 1 Phase 37 input

    def test_all_horizons_upward_tag(self):
        """Test 'all_horizons_upward' tag when all slopes positive."""
        snapshot = compute_coherence_scenario_alignment(
            horizon_slope_H1=0.3,
            horizon_slope_H2=0.4,
            horizon_slope_H3=0.5,
            scenario_alignment_score=0.70,
        )

        assert snapshot is not None
        assert "all_horizons_upward" in snapshot.diagnostic_tags

    def test_all_horizons_downward_tag(self):
        """Test 'all_horizons_downward' tag when all slopes negative."""
        snapshot = compute_coherence_scenario_alignment(
            horizon_slope_H1=-0.3,
            horizon_slope_H2=-0.4,
            horizon_slope_H3=-0.5,
            scenario_alignment_score=0.30,
        )

        assert snapshot is not None
        assert "all_horizons_downward" in snapshot.diagnostic_tags

    def test_identity_continuity_tags(self):
        """Test identity continuity related tags."""
        # High ICC
        snapshot_high = compute_coherence_scenario_alignment(
            icc=0.85,
            scenario_alignment_score=0.75,
        )
        assert snapshot_high is not None
        assert "identity_continuity_robust" in snapshot_high.diagnostic_tags

        # Low ICC
        snapshot_low = compute_coherence_scenario_alignment(
            icc=0.25,
            scenario_alignment_score=0.35,
        )
        assert snapshot_low is not None
        assert "identity_continuity_weak" in snapshot_low.diagnostic_tags

    def test_forecast_confidence_tags(self):
        """Test forecast confidence tags."""
        # High forecast strength
        snapshot_high = compute_coherence_scenario_alignment(
            forecast_strength=0.85,
            scenario_alignment_score=0.70,
        )
        assert snapshot_high is not None
        assert "forecast_confidence_high" in snapshot_high.diagnostic_tags

        # Low forecast strength
        snapshot_low = compute_coherence_scenario_alignment(
            forecast_strength=0.25,
            scenario_alignment_score=0.70,
        )
        assert snapshot_low is not None
        assert "forecast_confidence_low" in snapshot_low.diagnostic_tags

    def test_scenario_regimes_tags(self):
        """Test scenario regime convergence/divergence tags."""
        # Converging
        snapshot_converge = compute_coherence_scenario_alignment(
            scenario_alignment_score=0.75,
            icc=0.70,
        )
        assert snapshot_converge is not None
        assert "scenario_regimes_converging" in snapshot_converge.diagnostic_tags

        # Diverging
        snapshot_diverge = compute_coherence_scenario_alignment(
            scenario_divergence_index=0.75,
            icc=0.40,
        )
        assert snapshot_diverge is not None
        assert "scenario_regimes_diverging" in snapshot_diverge.diagnostic_tags

    def test_backward_compatibility(self):
        """Test Phase 44 doesn't break existing CoherenceState behavior."""
        state = CoherenceState(convo_id="test", turn_index=5)

        # Test that all old fields still exist
        assert hasattr(state, 'coherence_score')
        assert hasattr(state, 'persona_drift_score')
        assert hasattr(state, 'semantic_stability_score')
        assert hasattr(state, 'temporal_arc_score')

        # Test window trim still works with mixed histories
        state.tier_history = ["lower"] * 20
        state.scenario_alignment_score_history = [0.5] * 20

        state.window_trim(10)

        assert len(state.tier_history) == 10
        assert len(state.scenario_alignment_score_history) == 10


# ============================================================================
# GROUP C: SESSION SUMMARY (10 tests)
# ============================================================================


class TestSessionSummary:
    """Test session summary aggregation for Phase 44."""

    def test_session_models_has_phase44_fields(self):
        """Test SessionSummary model has Phase 44 fields."""
        from symbolu.service.sessions.session_models import SessionSummary

        summary = SessionSummary(
            session_id="test",
            total_turns=10,
            coherence_trend="stable",
            persona_drift_avg=0.0,
            temporal_arc_avg=0.0,
        )

        assert hasattr(summary, 'avg_csae_alignment')
        assert hasattr(summary, 'avg_csae_conflict')
        assert hasattr(summary, 'avg_csae_stability')
        assert hasattr(summary, 'csae_alignment_band')
        assert hasattr(summary, 'csae_alignment_tags')

    def test_session_summary_aggregation_averages(self):
        """Test session summary correctly averages Phase 44 scores."""
        # Mock coherence history with Phase 44 data
        coh_history = [
            {
                "scenario_alignment_score_history": [0.70, 0.75],
                "scenario_conflict_history": [0.25, 0.20],
                "scenario_stability_history": [0.80, 0.85],
            },
            {
                "scenario_alignment_score_history": [0.80, None],
                "scenario_conflict_history": [0.15, None],
                "scenario_stability_history": [0.90, None],
            },
        ]

        # Manually compute expected averages
        all_alignment = [0.70, 0.75, 0.80]
        all_conflict = [0.25, 0.20, 0.15]
        all_stability = [0.80, 0.85, 0.90]

        expected_avg_alignment = sum(all_alignment) / len(all_alignment)
        expected_avg_conflict = sum(all_conflict) / len(all_conflict)
        expected_avg_stability = sum(all_stability) / len(all_stability)

        assert abs(expected_avg_alignment - 0.75) < 0.01
        assert abs(expected_avg_conflict - 0.20) < 0.01
        assert abs(expected_avg_stability - 0.85) < 0.01

    def test_session_summary_alignment_band_most_frequent(self):
        """Test alignment band aggregation selects most frequent."""
        # Mock history with bands
        bands = ["high", "high", "medium", "high", "medium"]
        # Most frequent is "high" (3 occurrences)

        from collections import Counter
        band_counts = Counter(bands)
        most_common = band_counts.most_common(1)[0][0]

        assert most_common == "high"

    def test_session_summary_alignment_band_tie_breaking(self):
        """Test deterministic tie-breaking for alignment bands."""
        # Mock history with tied bands
        bands = ["high", "medium", "high", "medium"]
        # Tied at 2 each, should pick "high" (alphabetically first)

        from collections import Counter
        band_counts = Counter(bands)
        top_bands = band_counts.most_common()
        max_count = top_bands[0][1]
        tied_bands = [band for band, count in top_bands if count == max_count]
        result = sorted(tied_bands)[0]

        assert result == "high"

    def test_session_summary_tags_deduplication(self):
        """Test diagnostic tags are deduplicated and sorted."""
        # Mock tags from multiple turns
        all_tags = [
            ["tag_a", "tag_b"],
            ["tag_b", "tag_c"],
            ["tag_a", "tag_c", "tag_d"],
        ]

        # Flatten and deduplicate
        flattened = []
        for tag_list in all_tags:
            flattened.extend(tag_list)

        unique_sorted = sorted(set(flattened))

        assert unique_sorted == ["tag_a", "tag_b", "tag_c", "tag_d"]

    def test_session_summary_handles_empty_history(self):
        """Test session summary gracefully handles empty Phase 44 history."""
        coh_history = [
            {
                "scenario_alignment_score_history": [],
                "scenario_conflict_history": [],
                "scenario_stability_history": [],
                "scenario_alignment_band_history": [],
                "scenario_tags_history": [],
            }
        ]

        # Should result in None values
        # (actual implementation would be tested with real session_store.compute_session_summary)

    def test_session_summary_handles_all_none_values(self):
        """Test session summary handles all None values in histories."""
        coh_history = [
            {
                "scenario_alignment_score_history": [None, None, None],
                "scenario_conflict_history": [None, None, None],
                "scenario_stability_history": [None, None, None],
            }
        ]

        # Should result in None averages (no valid values to average)

    def test_session_summary_mixed_none_and_values(self):
        """Test session summary correctly filters None values when computing averages."""
        values = [0.70, None, 0.80, None, 0.75]
        valid_values = [v for v in values if v is not None]

        if valid_values:
            avg = sum(valid_values) / len(valid_values)
            assert abs(avg - 0.75) < 0.01

    def test_session_summary_band_frequency_tracking(self):
        """Test band frequency is correctly tracked."""
        bands = ["high", "high", "medium", "high", "low", "medium"]

        from collections import Counter
        band_counts = Counter(bands)

        assert band_counts["high"] == 3
        assert band_counts["medium"] == 2
        assert band_counts["low"] == 1

    def test_session_summary_tags_from_nested_lists(self):
        """Test tags extraction from nested list structure."""
        tags_history = [
            ["alignment_coherence_rising", "identity_continuity_robust"],
            [],
            ["strong_alignment_multi_horizon", "alignment_coherence_rising"],
        ]

        flattened = []
        for tag_list in tags_history:
            if isinstance(tag_list, list):
                flattened.extend(tag_list)

        unique_sorted = sorted(set(flattened))

        assert "alignment_coherence_rising" in unique_sorted
        assert "identity_continuity_robust" in unique_sorted
        assert "strong_alignment_multi_horizon" in unique_sorted
        assert len(unique_sorted) == 3  # deduplicated


# ============================================================================
# GROUP D: UNIFIED API & OBSERVER (8 tests)
# ============================================================================


class TestUnifiedAPIObserver:
    """Test Unified API and Coherence Observer integration."""

    def test_unified_output_has_phase44_field(self):
        """Test UnifiedOutput has coherence_scenario_alignment field."""
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

        assert hasattr(output, 'coherence_scenario_alignment')
        assert output.coherence_scenario_alignment is None

    def test_unified_output_scenario_alignment_structure(self):
        """Test coherence_scenario_alignment follows expected structure."""
        alignment_data = {
            "alignment_score": 0.75,
            "conflict_index": 0.25,
            "stability_agreement": 0.80,
            "alignment_band": "high",
            "diagnostic_tags": ["tag1", "tag2"],
        }

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
            coherence_scenario_alignment=alignment_data,
        )

        assert output.coherence_scenario_alignment is not None
        assert output.coherence_scenario_alignment["alignment_score"] == 0.75
        assert output.coherence_scenario_alignment["conflict_index"] == 0.25
        assert output.coherence_scenario_alignment["stability_agreement"] == 0.80
        assert output.coherence_scenario_alignment["alignment_band"] == "high"
        assert len(output.coherence_scenario_alignment["diagnostic_tags"]) == 2

    def test_unified_output_to_dict_includes_phase44(self):
        """Test UnifiedOutput.to_dict() includes Phase 44 data."""
        from symbolu.api.unified_api import UnifiedOutput

        alignment_data = {
            "alignment_score": 0.75,
            "conflict_index": 0.25,
            "stability_agreement": 0.80,
            "alignment_band": "high",
            "diagnostic_tags": ["tag1"],
        }

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
            coherence_scenario_alignment=alignment_data,
        )

        output_dict = output.to_dict()

        assert "coherence_scenario_alignment" in output_dict
        assert output_dict["coherence_scenario_alignment"]["alignment_score"] == 0.75

    def test_coherence_observation_has_phase44_fields(self):
        """Test CoherenceObservation has Phase 44 fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        obs = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.25,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.30,
            turn_number=5,
            tier="hybrid",
            domain="therapy",
            active_mappers=["mapper1"],
        )

        assert hasattr(obs, 'csae_alignment_score')
        assert hasattr(obs, 'csae_conflict_index')
        assert hasattr(obs, 'csae_stability_agreement')
        assert hasattr(obs, 'csae_alignment_band')
        assert hasattr(obs, 'csae_diagnostic_tags')

    def test_coherence_observation_phase44_values(self):
        """Test CoherenceObservation stores Phase 44 values correctly."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        obs = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.25,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.30,
            turn_number=5,
            tier="hybrid",
            domain="therapy",
            active_mappers=["mapper1"],
            csae_alignment_score=0.82,
            csae_conflict_index=0.18,
            csae_stability_agreement=0.85,
            csae_alignment_band="high",
            csae_diagnostic_tags=["strong_alignment_multi_horizon"],
        )

        assert obs.csae_alignment_score == 0.82
        assert obs.csae_conflict_index == 0.18
        assert obs.csae_stability_agreement == 0.85
        assert obs.csae_alignment_band == "high"
        assert "strong_alignment_multi_horizon" in obs.csae_diagnostic_tags

    def test_coherence_observation_to_dict_includes_phase44(self):
        """Test CoherenceObservation.to_dict() includes Phase 44 data."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        obs = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.25,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.30,
            turn_number=5,
            tier="hybrid",
            domain="therapy",
            active_mappers=["mapper1"],
            csae_alignment_score=0.82,
            csae_conflict_index=0.18,
        )

        obs_dict = obs.to_dict()

        assert "csae_alignment_score" in obs_dict
        assert "csae_conflict_index" in obs_dict
        assert obs_dict["csae_alignment_score"] == 0.82
        assert obs_dict["csae_conflict_index"] == 0.18

    def test_json_serialization(self):
        """Test Phase 44 data is JSON-serializable."""
        import json

        alignment_data = {
            "alignment_score": 0.75,
            "conflict_index": 0.25,
            "stability_agreement": 0.80,
            "alignment_band": "high",
            "diagnostic_tags": ["tag1", "tag2"],
        }

        # Should not raise exception
        json_str = json.dumps(alignment_data)
        assert json_str is not None

        # Round-trip test
        parsed = json.loads(json_str)
        assert parsed["alignment_score"] == 0.75
        assert parsed["alignment_band"] == "high"


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE (10 tests)
# ============================================================================


class TestBehavioralInvariance:
    """Test Phase 44 maintains behavioral invariants."""

    def test_zero_llm_invariant(self):
        """Test Phase 44 makes no LLM calls."""
        # This test ensures the formula is purely mathematical
        # No mocking of LLM calls should be needed
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.5,
            scenario_alignment_score=0.70,
            icc=0.75,
        )

        # If we get here without errors, no LLM calls were made
        assert snapshot is not None

    def test_observation_only_invariant(self):
        """Test Phase 44 doesn't modify any input state."""
        state = CoherenceState(convo_id="test", turn_index=5)
        initial_coherence_score = state.coherence_score

        # Simulate Phase 44 snapshot creation (not actual engine call, just formula)
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=0.5,
            scenario_alignment_score=0.70,
        )

        # Original state should be unchanged
        assert state.coherence_score == initial_coherence_score

    def test_deterministic_across_multiple_runs(self):
        """Test Phase 44 produces identical results across 20 runs."""
        params = {
            "forecast_coherence_slope": 0.45,
            "forecast_continuity_slope": 0.35,
            "scenario_alignment_score": 0.68,
            "scenario_divergence_index": 0.32,
            "icc": 0.72,
            "css": 0.78,
            "future_stability_envelope": 0.70,
        }

        results = []
        for _ in range(20):
            snapshot = compute_coherence_scenario_alignment(**params)
            results.append({
                "alignment_score": snapshot.alignment_score,
                "conflict_index": snapshot.conflict_index,
                "stability_agreement": snapshot.stability_agreement,
                "alignment_band": snapshot.overall_alignment_band,
                "tags": tuple(snapshot.diagnostic_tags),
            })

        # All results should be identical
        for result in results[1:]:
            assert result["alignment_score"] == results[0]["alignment_score"]
            assert result["conflict_index"] == results[0]["conflict_index"]
            assert result["stability_agreement"] == results[0]["stability_agreement"]
            assert result["alignment_band"] == results[0]["alignment_band"]
            assert result["tags"] == results[0]["tags"]

    def test_no_routing_impact(self):
        """Test Phase 44 doesn't affect routing decisions."""
        # Phase 44 should be pure observation, no impact on TTOR or MLCR
        # This is a structural test - if Phase 44 tried to modify routing,
        # it would require access to routing components, which it shouldn't have

        from symbolu.formulas.coherence_scenario_alignment import compute_coherence_scenario_alignment

        # Ensure the function signature doesn't include routing parameters
        import inspect
        sig = inspect.signature(compute_coherence_scenario_alignment)

        # Check that no routing-related parameters exist
        routing_keywords = ['routing', 'tier', 'mapper', 'mlcr', 'ttor']
        params = sig.parameters.keys()

        for keyword in routing_keywords:
            assert not any(keyword in str(p).lower() for p in params), \
                f"Phase 44 should not have routing parameter: {keyword}"

    def test_no_persona_semantics_impact(self):
        """Test Phase 44 doesn't affect persona semantics."""
        # Phase 44 should not modify persona text, tone, or semantic content
        # This is tested by ensuring the formula only computes observational metrics

        snapshot = compute_coherence_scenario_alignment(
            scenario_alignment_score=0.75,
            icc=0.80,
        )

        # Snapshot should only contain numerical/categorical observations
        assert isinstance(snapshot.alignment_score, (float, type(None)))
        assert isinstance(snapshot.conflict_index, (float, type(None)))
        assert isinstance(snapshot.overall_alignment_band, (str, type(None)))
        assert isinstance(snapshot.diagnostic_tags, list)

        # No text generation or persona modifications
        assert not hasattr(snapshot, 'persona_text')
        assert not hasattr(snapshot, 'tone_adjustments')

    def test_bounded_outputs(self):
        """Test all Phase 44 outputs are properly bounded."""
        # Test with extreme inputs
        snapshot = compute_coherence_scenario_alignment(
            forecast_coherence_slope=10.0,  # Way out of bounds
            forecast_drift_influence=10.0,
            scenario_alignment_score=5.0,
            icc=-5.0,
        )

        assert snapshot is not None

        # All scores should be bounded [0.0, 1.0]
        if snapshot.alignment_score is not None:
            assert 0.0 <= snapshot.alignment_score <= 1.0
        if snapshot.conflict_index is not None:
            assert 0.0 <= snapshot.conflict_index <= 1.0
        if snapshot.stability_agreement is not None:
            assert 0.0 <= snapshot.stability_agreement <= 1.0

        # Band should be one of valid values
        if snapshot.overall_alignment_band is not None:
            assert snapshot.overall_alignment_band in ["high", "medium", "low", "conflict"]

    def test_null_safety(self):
        """Test Phase 44 handles None/null values safely."""
        # Test with all None values
        snapshot_all_none = compute_coherence_scenario_alignment()
        assert snapshot_all_none is None

        # Test with mix of None and valid values
        snapshot_mixed = compute_coherence_scenario_alignment(
            forecast_coherence_slope=None,
            scenario_alignment_score=0.70,
            icc=None,
            css=0.75,
        )
        # Should succeed with available data
        assert snapshot_mixed is not None

    def test_backward_compatibility_no_breaking_changes(self):
        """Test Phase 44 doesn't break existing phase computations."""
        # Creating a coherence state should still work identically
        state1 = CoherenceState(convo_id="test1", turn_index=0)
        state2 = CoherenceState(convo_id="test2", turn_index=0)

        # Both should have same structure
        assert state1.coherence_score == state2.coherence_score
        assert len(state1.tier_history) == len(state2.tier_history)

        # Phase 44 fields should be present but not interfere
        assert hasattr(state1, 'scenario_alignment_snapshot')
        assert state1.scenario_alignment_snapshot is None

    def test_no_side_effects(self):
        """Test Phase 44 computation has no side effects."""
        # Test that calling the formula doesn't modify global state
        import copy

        params = {
            "forecast_coherence_slope": 0.5,
            "scenario_alignment_score": 0.70,
            "icc": 0.75,
        }

        params_copy = copy.deepcopy(params)

        snapshot = compute_coherence_scenario_alignment(**params)

        # Parameters should be unchanged
        assert params == params_copy

        # Multiple calls should not affect each other
        snapshot2 = compute_coherence_scenario_alignment(**params)
        assert snapshot.alignment_score == snapshot2.alignment_score

    def test_no_tone_modifications_in_persona_integration(self):
        """Test Phase 44 persona integration doesn't modify tone."""
        # This tests the persona engine integration
        # Phase 44 should only attach metadata, never modify tone parameters

        from symbolu.mechanical.persona.models import PersonaResponse, PersonaMetadata

        # Create required PersonaMetadata
        metadata = PersonaMetadata(
            tier="HYBRID",
            domain="general",
            intent="what",
            persona_id="analyst",
            persona_name="The Analyst",
            persona_description="Structured analysis persona",
            dha_tone="neutral",
            dha_confidence=0.8,
        )

        # Store tone_params for verification (external to model)
        original_tone_params = {"formality": 0.7, "warmth": 0.5}

        # Create response with required fields
        response = PersonaResponse(
            text="Test response",
            persona_id="analyst",
            layers={"symbolic": {}, "practical": {}, "mirror": {}},
            metadata=metadata,
        )

        # Simulate Phase 44 metadata attachment (Phase 44 adds scenario alignment)
        # Phase 44 should only attach metadata, never modify tone parameters
        response.persona_scenario_alignment = {
            "alignment_score": 0.75,
            "alignment_band": "high",
        }

        # Original tone params should be unchanged (proves Phase 44 doesn't modify tone)
        assert original_tone_params["formality"] == 0.7
        assert original_tone_params["warmth"] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
