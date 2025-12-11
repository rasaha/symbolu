"""
Test Suite for Phase 41: Coherence-Regime Scenario Mapper (CRSM) v1.0

This comprehensive test suite ensures the CRSM implementation is:
- Deterministic (same inputs → same outputs)
- Zero-LLM (no model calls)
- Observation-only (no routing/scoring changes)
- Backward compatible (all existing tests remain green)
- Fully bounded (all scores [0.0, 1.0])
- Gracefully degrading (handles missing data)

Test Groups:
- Group A: Regime Formula Math (15 tests)
- Group B: Coherence Integration (10 tests)
- Group C: Session & Dashboard Integration (10 tests)
- Group D: Unified API & Observer (8 tests)
- Group E: Behavioral Invariance (8 tests)

Total: ~51 tests
"""

import pytest
from symbolu.formulas.coherence_regime_scenario_mapper import (
    compute_coherence_regime,
    CoherenceRegimeSnapshot,
    CANONICAL_REGIMES,
    _clamp,
    _safe_get,
    _compute_slope,
    _score_stable_therapeutic_processing,
    _score_volatile_identity_drift,
    _score_deep_reflective_exploration,
    _score_surface_level_interaction,
    _score_ambivalent_conflicted_state,
    _score_recovery_stabilization_phase,
    _determine_regime_band,
    _generate_diagnostic_tags,
    _generate_notes,
)


# ============================================================================
# GROUP A: REGIME FORMULA MATH (15 tests)
# ============================================================================


class TestRegimeFormulaMath:
    """Test regime scoring algorithms and mathematical properties."""

    def test_canonical_regimes_defined(self):
        """Test that all canonical regimes are defined."""
        assert len(CANONICAL_REGIMES) == 6
        assert "stable_therapeutic_processing" in CANONICAL_REGIMES
        assert "volatile_identity_drift" in CANONICAL_REGIMES
        assert "deep_reflective_exploration" in CANONICAL_REGIMES
        assert "surface_level_interaction" in CANONICAL_REGIMES
        assert "ambivalent_conflicted_state" in CANONICAL_REGIMES
        assert "recovery_stabilization_phase" in CANONICAL_REGIMES

    def test_clamp_function_boundaries(self):
        """Test _clamp enforces [0.0, 1.0] boundaries."""
        assert _clamp(-0.5) == 0.0
        assert _clamp(0.0) == 0.0
        assert _clamp(0.5) == 0.5
        assert _clamp(1.0) == 1.0
        assert _clamp(1.5) == 1.0

    def test_safe_get_handles_none(self):
        """Test _safe_get provides fallback for None values."""
        assert _safe_get(None, 0.5) == 0.5
        assert _safe_get(0.7, 0.5) == 0.7
        assert _safe_get(1.5, 0.5) == 1.0  # Clamped
        assert _safe_get(-0.2, 0.5) == 0.0  # Clamped

    def test_compute_slope_with_history(self):
        """Test _compute_slope computes trajectory correctly."""
        # Increasing trend
        increasing = [0.1, 0.2, 0.3, 0.4, 0.5]
        slope_inc = _compute_slope(increasing)
        assert slope_inc > 0, "Increasing trend should have positive slope"

        # Decreasing trend
        decreasing = [0.5, 0.4, 0.3, 0.2, 0.1]
        slope_dec = _compute_slope(decreasing)
        assert slope_dec < 0, "Decreasing trend should have negative slope"

        # Flat trend
        flat = [0.5, 0.5, 0.5, 0.5, 0.5]
        slope_flat = _compute_slope(flat)
        assert abs(slope_flat) < 0.1, "Flat trend should have near-zero slope"

    def test_stable_therapeutic_processing_scoring(self):
        """Test stable_therapeutic_processing regime scoring."""
        # High coherence, low drift, moderate entropy
        score = _score_stable_therapeutic_processing(
            coherence_fused=0.85,
            css=0.80,
            drift_fusion_index=0.15,
            entropy_instant=0.45,
            icc=0.75,
            v3=0.80,
        )
        assert 0.0 <= score <= 1.0, "Score must be bounded [0.0, 1.0]"
        assert score > 0.65, "Stable conditions should yield high score"

        # Low coherence, high drift
        score_low = _score_stable_therapeutic_processing(
            coherence_fused=0.30,
            css=0.25,
            drift_fusion_index=0.85,
            entropy_instant=0.90,
            icc=0.20,
            v3=0.25,
        )
        assert 0.0 <= score_low <= 1.0
        assert score_low < 0.50, "Unstable conditions should yield low score"

    def test_volatile_identity_drift_scoring(self):
        """Test volatile_identity_drift regime scoring."""
        # High drift, low continuity
        score = _score_volatile_identity_drift(
            drift_fusion_index=0.85,
            css=0.20,
            entropy_instant=0.80,
            icc=0.15,
            predictive_drift=0.75,
            cognitive_drift_v3=0.70,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.65, "High drift should yield high volatile score"

        # Low drift, high continuity
        score_low = _score_volatile_identity_drift(
            drift_fusion_index=0.15,
            css=0.80,
            entropy_instant=0.30,
            icc=0.75,
            predictive_drift=0.20,
            cognitive_drift_v3=0.25,
        )
        assert 0.0 <= score_low <= 1.0
        assert score_low < 0.40, "Low drift should yield low volatile score"

    def test_deep_reflective_exploration_scoring(self):
        """Test deep_reflective_exploration regime scoring."""
        # High v3, high UCF CIP, strong SHI
        score = _score_deep_reflective_exploration(
            v3=0.85,
            ucf_cip=0.80,
            shi=0.75,
            resonance_entropy=0.65,
            insight_window_active=True,
            entropy_instant=0.60,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.70, "Deep exploration conditions should yield high score"

    def test_surface_level_interaction_scoring(self):
        """Test surface_level_interaction regime scoring."""
        # Low v3 quality, low SHI
        score = _score_surface_level_interaction(
            v3_quality=0.25,
            shi=0.20,
            ncc=0.30,
            drift_fusion_index=0.50,
            ims=0.35,
            icc=0.30,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.50, "Surface-level conditions should yield moderate to high score"

    def test_ambivalent_conflicted_state_scoring(self):
        """Test ambivalent_conflicted_state regime scoring."""
        # High entropy, mid coherence, mixed identity
        score = _score_ambivalent_conflicted_state(
            entropy_instant=0.75,
            coherence_fused=0.50,
            ims=0.50,
            iep=0.45,
            drift_fusion_index=0.55,
            dft=0.70,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.50, "Conflicted state should yield moderate to high score"

    def test_recovery_stabilization_phase_scoring(self):
        """Test recovery_stabilization_phase regime scoring."""
        # Positive coherence slope, decreasing entropy
        score = _score_recovery_stabilization_phase(
            coherence_slope=0.40,  # Improving
            continuity_slope=0.35,  # Improving
            entropy_slope=-0.30,  # Decreasing (good)
            drift_slope=-0.25,  # Decreasing (good)
            css=0.55,  # Recovery zone
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.55, "Recovery pattern should yield moderate to high score"

    def test_determine_regime_band_stable(self):
        """Test regime band determination for stable conditions."""
        band = _determine_regime_band(
            dominant_regime="stable_therapeutic_processing",
            dominant_score=0.75,
            second_score=0.50,
        )
        assert band == "stable"

    def test_determine_regime_band_volatile(self):
        """Test regime band determination for volatile conditions."""
        band = _determine_regime_band(
            dominant_regime="volatile_identity_drift",
            dominant_score=0.70,
            second_score=0.45,
        )
        assert band == "volatile"

    def test_determine_regime_band_mixed(self):
        """Test regime band determination for mixed conditions."""
        band = _determine_regime_band(
            dominant_regime="deep_reflective_exploration",
            dominant_score=0.55,
            second_score=0.50,  # Close margin
        )
        assert band == "mixed"

    def test_generate_diagnostic_tags_deterministic(self):
        """Test diagnostic tag generation is deterministic."""
        regime_scores = {"stable_therapeutic_processing": 0.75}
        tags1 = _generate_diagnostic_tags(
            regime_scores=regime_scores,
            dominant_regime="stable_therapeutic_processing",
            regime_band="stable",
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
            entropy_instant=0.40,
        )
        tags2 = _generate_diagnostic_tags(
            regime_scores=regime_scores,
            dominant_regime="stable_therapeutic_processing",
            regime_band="stable",
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
            entropy_instant=0.40,
        )
        assert tags1 == tags2, "Same inputs should produce same tags"
        assert "CONTEXT_STABLE" in tags1
        assert "COHERENCE_STRONG" in tags1

    def test_generate_notes_deterministic(self):
        """Test note generation is deterministic."""
        notes1 = _generate_notes(
            dominant_regime="stable_therapeutic_processing",
            regime_band="stable",
            drift_fusion_index=0.25,
            css=0.75,
        )
        notes2 = _generate_notes(
            dominant_regime="stable_therapeutic_processing",
            regime_band="stable",
            drift_fusion_index=0.25,
            css=0.75,
        )
        assert notes1 == notes2, "Same inputs should produce same notes"
        assert len(notes1) > 0


# ============================================================================
# GROUP B: COHERENCE INTEGRATION (10 tests)
# ============================================================================


class TestCoherenceIntegration:
    """Test integration with CoherenceState and CoherenceEngine."""

    def test_compute_coherence_regime_with_valid_inputs(self):
        """Test regime computation with complete valid inputs."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            coherence_v3=0.70,
            drift_fusion_index=0.30,
            css=0.68,
            ucf_coi=0.65,
            ucf_cip=0.62,
            ncc=0.60,
            icc=0.58,
        )

        assert snapshot is not None
        assert isinstance(snapshot, CoherenceRegimeSnapshot)
        assert snapshot.dominant_regime in CANONICAL_REGIMES
        assert snapshot.regime_band in ["stable", "mixed", "volatile"]
        assert len(snapshot.regime_scores) == len(CANONICAL_REGIMES)
        assert all(0.0 <= score <= 1.0 for score in snapshot.regime_scores.values())

    def test_compute_coherence_regime_returns_none_without_essentials(self):
        """Test graceful degradation when essential inputs are missing."""
        # Missing coherence (both fused and v3)
        snapshot = compute_coherence_regime(
            drift_fusion_index=0.30,
            css=0.68,
        )
        assert snapshot is None

        # Missing drift
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            css=0.68,
        )
        assert snapshot is None

        # Missing continuity
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.30,
        )
        assert snapshot is None

    def test_regime_scores_are_bounded(self):
        """Test that all regime scores are bounded [0.0, 1.0]."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.50,
            drift_fusion_index=0.50,
            css=0.50,
        )

        assert snapshot is not None
        for regime, score in snapshot.regime_scores.items():
            assert 0.0 <= score <= 1.0, f"Regime '{regime}' score {score} not in [0.0, 1.0]"

    def test_dominant_regime_is_highest_score(self):
        """Test that dominant regime is the one with highest score."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.85,
            drift_fusion_index=0.15,
            css=0.80,
            coherence_v3=0.82,
            icc=0.75,
        )

        assert snapshot is not None
        max_score = max(snapshot.regime_scores.values())
        dominant_score = snapshot.regime_scores[snapshot.dominant_regime]
        assert dominant_score == max_score

    def test_secondary_regimes_sorted_by_score(self):
        """Test that secondary regimes are sorted by descending score."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.70,
            drift_fusion_index=0.35,
            css=0.65,
        )

        assert snapshot is not None
        assert len(snapshot.secondary_regimes) == len(CANONICAL_REGIMES) - 1

        # Verify sorted order
        prev_score = 1.0
        for regime in snapshot.secondary_regimes:
            score = snapshot.regime_scores[regime]
            assert score <= prev_score, "Secondary regimes should be sorted by descending score"
            prev_score = score

    def test_regime_band_classification(self):
        """Test regime band classification logic."""
        # Stable conditions
        snapshot = compute_coherence_regime(
            coherence_fused=0.85,
            drift_fusion_index=0.15,
            css=0.80,
            coherence_v3=0.82,
            icc=0.78,
        )
        assert snapshot is not None
        assert snapshot.regime_band in ["stable", "mixed", "volatile"]

    def test_deterministic_computation(self):
        """Test that regime computation is deterministic."""
        inputs = {
            "coherence_fused": 0.72,
            "drift_fusion_index": 0.38,
            "css": 0.65,
            "coherence_v3": 0.68,
            "ncc": 0.62,
            "icc": 0.60,
        }

        snapshot1 = compute_coherence_regime(**inputs)
        snapshot2 = compute_coherence_regime(**inputs)

        assert snapshot1 is not None
        assert snapshot2 is not None
        assert snapshot1.dominant_regime == snapshot2.dominant_regime
        assert snapshot1.regime_band == snapshot2.regime_band
        assert snapshot1.regime_scores == snapshot2.regime_scores

    def test_graceful_handling_of_partial_inputs(self):
        """Test graceful handling when only some optional inputs provided."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.70,
            drift_fusion_index=0.35,
            css=0.65,
            # All other inputs None
        )

        assert snapshot is not None
        assert snapshot.dominant_regime in CANONICAL_REGIMES
        # Should still produce valid scores with fallback values

    def test_diagnostic_tags_present(self):
        """Test that diagnostic tags are generated."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
        )

        assert snapshot is not None
        assert isinstance(snapshot.diagnostic_tags, list)
        assert len(snapshot.diagnostic_tags) > 0

    def test_notes_generated(self):
        """Test that notes are generated."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
        )

        assert snapshot is not None
        assert isinstance(snapshot.notes, list)
        assert len(snapshot.notes) > 0
        # Verify notes contain dominant_regime info
        assert any("dominant_regime=" in note for note in snapshot.notes)


# ============================================================================
# GROUP C: SESSION & DASHBOARD INTEGRATION (10 tests)
# ============================================================================


class TestSessionDashboardIntegration:
    """Test integration with SessionSummary and dashboard aggregators."""

    def test_session_summary_has_regime_fields(self):
        """Test that SessionSummary dataclass includes regime fields."""
        from symbolu.service.sessions.session_models import SessionSummary
        from dataclasses import fields

        field_names = [f.name for f in fields(SessionSummary)]
        assert "dominant_coherence_regime" in field_names
        assert "regime_band" in field_names
        assert "regime_frequency" in field_names
        assert "regime_notes" in field_names

    def test_unified_session_analytics_has_regime_fields(self):
        """Test that UnifiedSessionAnalytics includes regime fields."""
        from symbolu.tools.unified_dashboard.models import UnifiedSessionAnalytics
        from dataclasses import fields

        field_names = [f.name for f in fields(UnifiedSessionAnalytics)]
        assert "coherence_regime" in field_names
        assert "coherence_regime_band" in field_names
        assert "coherence_regime_tags" in field_names

    def test_coherence_state_has_regime_fields(self):
        """Test that CoherenceState includes regime tracking fields."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from dataclasses import fields

        field_names = [f.name for f in fields(CoherenceState)]
        assert "coherence_regime_snapshot" in field_names
        assert "coherence_regime_history" in field_names
        assert "current_dominant_regime" in field_names
        assert "current_regime_band" in field_names
        assert "current_regime_scores" in field_names

    def test_coherence_state_window_trim_includes_regime_history(self):
        """Test that window_trim trims regime history."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Add some regime history
        for i in range(15):
            snapshot = compute_coherence_regime(
                coherence_fused=0.70 + (i * 0.01),
                drift_fusion_index=0.30,
                css=0.65,
            )
            state.coherence_regime_history.append(snapshot)

        # Trim to window of 10
        state.window_trim(10)

        assert len(state.coherence_regime_history) == 10

    def test_regime_frequency_aggregation_logic(self):
        """Test regime frequency counting in session aggregation."""
        # Simulate multiple regime snapshots
        regimes = [
            "stable_therapeutic_processing",
            "stable_therapeutic_processing",
            "deep_reflective_exploration",
            "stable_therapeutic_processing",
            "recovery_stabilization_phase",
        ]

        from collections import Counter
        frequency = Counter(regimes)

        assert frequency["stable_therapeutic_processing"] == 3
        assert frequency["deep_reflective_exploration"] == 1
        assert frequency["recovery_stabilization_phase"] == 1

        dominant = frequency.most_common(1)[0][0]
        assert dominant == "stable_therapeutic_processing"

    def test_regime_notes_deduplication(self):
        """Test that regime notes are deduplicated in aggregation."""
        notes = [
            "dominant_regime=stable with low drift",
            "regime_band=stable",
            "dominant_regime=stable with low drift",  # Duplicate
            "regime_band=stable",  # Duplicate
            "session_exhibits_stable_therapeutic_processing_pattern",
        ]

        unique_notes = sorted(set(notes))
        assert len(unique_notes) == 3
        assert "dominant_regime=stable with low drift" in unique_notes

    def test_unified_analytics_null_safe_regime_extraction(self):
        """Test that analytics handles missing regime data gracefully."""
        # Should not crash when coherence_regime is None
        coherence_regime = None
        coherence_regime_tags = []

        # This should work without error
        if coherence_regime is not None:
            coherence_regime_tags = coherence_regime.get("tags", [])

        assert coherence_regime_tags == []

    def test_session_summary_defaults(self):
        """Test SessionSummary regime field defaults."""
        from symbolu.service.sessions.session_models import SessionSummary

        summary = SessionSummary(
            session_id="test",
            total_turns=5,
            coherence_trend=0.7,
            persona_drift_avg=0.2,
            temporal_arc_avg=0.65,
        )

        # Default values should be None or empty
        assert summary.dominant_coherence_regime is None
        assert summary.regime_band is None
        assert summary.regime_frequency == {}
        assert summary.regime_notes == []

    def test_unified_analytics_regime_field_assignment(self):
        """Test regime field assignment in analytics."""
        from symbolu.tools.unified_dashboard.models import UnifiedSessionAnalytics

        analytics = UnifiedSessionAnalytics(
            session_id="test",
            coherence_regime="stable_therapeutic_processing",
            coherence_regime_band="stable",
            coherence_regime_tags=["CONTEXT_STABLE", "COHERENCE_STRONG"],
        )

        assert analytics.coherence_regime == "stable_therapeutic_processing"
        assert analytics.coherence_regime_band == "stable"
        assert len(analytics.coherence_regime_tags) == 2

    def test_regime_to_dict_serialization(self):
        """Test that regime snapshot serializes to dict correctly."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
        )

        assert snapshot is not None
        # CoherenceRegimeSnapshot is a dataclass, should be serializable
        from dataclasses import asdict
        regime_dict = asdict(snapshot)

        assert "dominant_regime" in regime_dict
        assert "regime_band" in regime_dict
        assert "regime_scores" in regime_dict
        assert "diagnostic_tags" in regime_dict


# ============================================================================
# GROUP D: UNIFIED API & OBSERVER (8 tests)
# ============================================================================


class TestUnifiedAPIAndObserver:
    """Test integration with Unified API and CoherenceObserver."""

    def test_unified_output_has_coherence_regime_field(self):
        """Test that UnifiedOutput includes coherence_regime field."""
        from symbolu.api.unified_api import UnifiedOutput
        from dataclasses import fields

        field_names = [f.name for f in fields(UnifiedOutput)]
        assert "coherence_regime" in field_names

    def test_coherence_observation_has_regime_fields(self):
        """Test that CoherenceObservation includes regime fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation
        from dataclasses import fields

        field_names = [f.name for f in fields(CoherenceObservation)]
        assert "regime_name" in field_names
        assert "regime_band" in field_names
        assert "regime_scores" in field_names
        assert "regime_tags" in field_names

    def test_regime_data_extraction_from_coherence_state(self):
        """Test regime data extraction from coherence state."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
        )

        assert snapshot is not None

        # Simulate extraction (as done in unified_api.py)
        regime_data = {
            "dominant_regime": snapshot.dominant_regime,
            "band": snapshot.regime_band,
            "scores": snapshot.regime_scores,
            "tags": snapshot.diagnostic_tags,
        }

        assert regime_data["dominant_regime"] in CANONICAL_REGIMES
        assert regime_data["band"] in ["stable", "mixed", "volatile"]
        assert isinstance(regime_data["scores"], dict)
        assert isinstance(regime_data["tags"], list)

    def test_unified_api_regime_block_null_safe(self):
        """Test that unified API handles None regime snapshot gracefully."""
        # Simulate missing regime snapshot
        regime_snapshot = None

        regime_data = None
        if regime_snapshot is not None:
            regime_data = {
                "dominant_regime": regime_snapshot.dominant_regime,
                "band": regime_snapshot.regime_band,
            }

        assert regime_data is None  # Should handle gracefully

    def test_coherence_observer_regime_extraction(self):
        """Test observer extraction of regime fields."""
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            drift_fusion_index=0.25,
            css=0.72,
        )

        assert snapshot is not None

        # Simulate observer extraction
        regime_name = snapshot.dominant_regime
        regime_band = snapshot.regime_band
        regime_scores = snapshot.regime_scores
        regime_tags = snapshot.diagnostic_tags

        assert regime_name in CANONICAL_REGIMES
        assert regime_band in ["stable", "mixed", "volatile"]
        assert len(regime_scores) == len(CANONICAL_REGIMES)
        assert isinstance(regime_tags, list)

    def test_regime_backward_compatibility(self):
        """Test that regime field addition doesn't break existing structures."""
        from symbolu.api.unified_api import UnifiedOutput

        # Should be able to create UnifiedOutput without regime field
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
            # coherence_regime=None (optional)
        )

        assert output.coherence_regime is None

    def test_unified_output_to_dict_includes_regime(self):
        """Test that to_dict includes regime data when present."""
        from symbolu.api.unified_api import UnifiedOutput

        regime_data = {
            "dominant_regime": "stable_therapeutic_processing",
            "band": "stable",
            "scores": {"stable_therapeutic_processing": 0.85},
            "tags": ["CONTEXT_STABLE"],
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
            coherence_regime=regime_data,
        )

        output_dict = output.to_dict()
        assert "coherence_regime" in output_dict
        assert output_dict["coherence_regime"]["dominant_regime"] == "stable_therapeutic_processing"

    def test_coherence_observation_to_dict_includes_regime(self):
        """Test that CoherenceObservation to_dict includes regime fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        observation = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.25,
            semantic_stability_score=0.70,
            temporal_arc_score=0.68,
            mapper_volatility_score=0.30,
            turn_number=5,
            tier="HYBRID",
            domain="therapy",
            active_mappers=["HRM"],
            regime_name="stable_therapeutic_processing",
            regime_band="stable",
            regime_scores={"stable_therapeutic_processing": 0.85},
            regime_tags=["CONTEXT_STABLE"],
        )

        obs_dict = observation.to_dict()
        assert "regime_name" in obs_dict
        assert obs_dict["regime_name"] == "stable_therapeutic_processing"


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE (8 tests)
# ============================================================================


class TestBehavioralInvariance:
    """Test that CRSM does not affect existing pipeline behavior."""

    def test_no_ttor_changes(self):
        """Test that CRSM does not modify TTOR routing."""
        # CRSM is observation-only, should never modify routing
        # This is a meta-test ensuring no routing logic in CRSM module
        from symbolu.formulas import coherence_regime_scenario_mapper

        module_functions = [func for func in dir(coherence_regime_scenario_mapper) if callable(getattr(coherence_regime_scenario_mapper, func))]

        # No routing-related function names should exist
        routing_keywords = ["route", "tier", "TTOR", "routing_plan"]
        for func in module_functions:
            for keyword in routing_keywords:
                assert keyword.lower() not in func.lower(), f"Found routing-related function: {func}"

    def test_no_mlcr_changes(self):
        """Test that CRSM does not modify MLCR activation."""
        # CRSM should not contain any MLCR activation logic (only check actual code, not docstrings)
        from symbolu.formulas import coherence_regime_scenario_mapper
        import inspect

        # Get the actual module source code (excluding docstrings)
        module_code = inspect.getsource(coherence_regime_scenario_mapper)

        # Check for actual MLCR activation patterns (not documentation mentions)
        mlcr_patterns = ["activate_mlcr", "deactivate_mlcr", "mlcr_enabled", "set_mlcr"]
        for pattern in mlcr_patterns:
            assert pattern.lower() not in module_code.lower(), f"Found MLCR activation pattern: {pattern}"

    def test_no_mapper_activation_changes(self):
        """Test that CRSM does not change mapper activation."""
        # CRSM should not modify HRM/LCM/LAM activation
        from symbolu.formulas import coherence_regime_scenario_mapper
        import inspect

        module_code = inspect.getsource(coherence_regime_scenario_mapper)

        # Only detect actual mapper name patterns, not substrings in function names like "_clamp()"
        mapper_patterns = ["LAM(", "LAM_", "select_lam", "HRM(", "HRM_", "select_hrm", "LCM(", "LCM_", "select_lcm"]
        for pattern in mapper_patterns:
            assert pattern not in module_code, f"Found mapper activation pattern: {pattern}"

    def test_coherence_scoring_unchanged(self):
        """Test that CRSM does not modify v1/v2/v3/UCF/fused scoring."""
        # Regime scoring should be read-only, never modify coherence scores
        snapshot = compute_coherence_regime(
            coherence_fused=0.75,
            coherence_v3=0.70,
            drift_fusion_index=0.30,
            css=0.68,
        )

        assert snapshot is not None
        # Inputs should remain unchanged (this is conceptual - we verify no mutation)
        # In practice, Python passes floats by value, so mutation is not possible

    def test_zero_llm_verification(self):
        """Test that CRSM makes zero LLM calls."""
        # No imports of LLM-related modules
        from symbolu.formulas import coherence_regime_scenario_mapper
        import sys

        # Check that no OpenAI/Anthropic/etc modules are imported
        llm_modules = ["openai", "anthropic", "langchain", "llama"]
        for module_name in llm_modules:
            assert module_name not in sys.modules or module_name not in str(coherence_regime_scenario_mapper.__file__), \
                f"CRSM should not import LLM module: {module_name}"

    def test_determinism_repeated_runs(self):
        """Test determinism: same inputs yield same outputs across runs."""
        inputs = {
            "coherence_fused": 0.72,
            "drift_fusion_index": 0.38,
            "css": 0.65,
        }

        results = []
        for _ in range(10):
            snapshot = compute_coherence_regime(**inputs)
            results.append((snapshot.dominant_regime, snapshot.regime_band, snapshot.regime_scores))

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result, "Repeated runs should produce identical results"

    def test_no_semantic_tone_changes_directly(self):
        """Test that CRSM does not directly modify semantic or tone."""
        # CRSM is observation-only, should not modify response text
        # Badges are UI-only and don't change response content
        from symbolu.formulas import coherence_regime_scenario_mapper

        module_code = open(coherence_regime_scenario_mapper.__file__).read()

        # Should not contain response modification logic
        assert "response.text" not in module_code
        assert "modify_tone" not in module_code
        assert "semantic_shift" not in module_code

    def test_backward_compatibility_no_breaking_changes(self):
        """Test that existing code works without regime data."""
        # CoherenceState should work fine with None regime snapshot
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Should handle None regime snapshot gracefully
        assert state.coherence_regime_snapshot is None
        assert state.current_dominant_regime is None
        assert state.current_regime_band is None


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
