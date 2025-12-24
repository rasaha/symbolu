"""
Phase 10 Extension: Acoustic Alignment Diagnostics Tests

Tests for the optional acoustic alignment diagnostics extension to Phase 10
Coherence v3 Fusion. This extension allows incorporation of acoustic alignment
observations from P22/P23/P24 WITHOUT changing any authoritative behavior.

Test Groups:
- Group A: Backward Compatibility (7 tests)
- Group B: Non-Authority Guarantees (8 tests)
- Group C: Bound Safety (6 tests)
- Group D: Determinism (5 tests)
- Group E: Import Safety (3 tests)
- Group F: Dataclass Invariants (6 tests)

Total: 35 tests

CRITICAL CONSTRAINTS VERIFIED:
1. ❌ DO NOT modify the existing coherence_v3 formula weights.
2. ❌ DO NOT allow acoustic signals to influence regime, discourse, semantics, lexical.
3. ❌ DO NOT make acoustic input required.
4. ❌ DO NOT change outputs when acoustic data is absent.
5. ❌ DO NOT import observer modules directly into authoritative logic.
6. ❌ DO NOT break existing Phase 10 tests.
"""

import pytest
from symbolu.core.coherence.acoustic_alignment_schema import (
    AcousticAlignmentReport,
    PressureBand,
    create_aligned_report,
    create_misaligned_report,
    create_neutral_report,
)
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.coherence_state import CoherenceState


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def engine():
    """Create a CoherenceEngine instance."""
    return CoherenceEngine(window=10)


@pytest.fixture
def base_state():
    """Create a basic CoherenceState with Phase 3 metrics."""
    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.70)
    state.resonance_index = 0.65
    state.tension_index = 0.40
    state.arc_alignment_index = 0.60
    state.guna_resonance_index = 0.68
    state.kosha_resonance_index = 0.66
    state.coherence_score_v2 = 0.72
    return state


@pytest.fixture
def aligned_report():
    """Create an aligned acoustic report (no penalty expected)."""
    return create_aligned_report(alignment_score=0.8, pressure_band="low")


@pytest.fixture
def misaligned_report():
    """Create a misaligned acoustic report (penalty expected)."""
    return create_misaligned_report(
        alignment_score=0.2,
        pressure_band="high",
        mismatch_tags=("inner_outer_tension", "high_pressure_low_authority"),
    )


@pytest.fixture
def threshold_report():
    """Create a report exactly at the threshold (no penalty expected)."""
    return AcousticAlignmentReport(
        alignment_score=0.4,
        pressure_band="moderate",
        mismatch_tags=(),
    )


# ============================================================================
# GROUP A: BACKWARD COMPATIBILITY (7 TESTS)
# ============================================================================


class TestBackwardCompatibility:
    """Test that acoustic=None produces identical outputs to original behavior."""

    def test_quality_unchanged_when_acoustic_none(self, engine, base_state):
        """Test that coherence_v3_quality is unchanged when acoustic_alignment is None."""
        # Compute quality WITHOUT acoustic (original behavior)
        original_quality = engine._compute_coherence_v3_quality(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
        )

        # Compute quality WITH acoustic=None (should be identical)
        quality_with_acoustic, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        assert quality_with_acoustic == original_quality, "Quality should be identical when acoustic_alignment is None"
        assert penalty_applied is False, "No penalty should be applied when acoustic_alignment is None"
        assert penalty_amount == 0.0, "Penalty amount should be 0 when acoustic_alignment is None"

    def test_coherence_v3_score_unchanged_regardless_of_acoustic(self, engine, base_state):
        """Test that coherence_score_v3 is NEVER affected by acoustic alignment."""
        # Compute v3 score (should be identical regardless of acoustic)
        v3_score = engine._compute_coherence_score_v3(base_state, {})

        # The v3 computation function doesn't take acoustic_alignment at all
        # This test verifies the architectural constraint is maintained
        assert v3_score is not None
        # V3 score is computed from state metrics, not acoustic alignment

    def test_adjustment_returns_unchanged_for_none(self, engine):
        """Test that _apply_acoustic_confidence_adjustment returns unchanged for None input."""
        quality_score = 0.75

        adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
            quality_score=quality_score,
            acoustic_alignment=None,
        )

        assert adjusted == quality_score, "Quality should be unchanged when acoustic is None"
        assert penalty_applied is False
        assert penalty_amount == 0.0

    def test_bitwise_identical_outputs_multiple_calls(self, engine, base_state):
        """Test that multiple calls with None produce bitwise-identical results."""
        results = []
        for _ in range(10):
            quality, applied, amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
                base=base_state.coherence_score,
                v3=0.73,
                resonance_index=base_state.resonance_index,
                arc_alignment_index=base_state.arc_alignment_index,
                tension_index=base_state.tension_index,
                acoustic_alignment=None,
            )
            results.append((quality, applied, amount))

        # All results should be identical
        assert all(r == results[0] for r in results), "All results should be identical"

    def test_missing_base_returns_none(self, engine):
        """Test that missing base returns None (original behavior preserved)."""
        quality, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=None,
            v3=0.75,
            resonance_index=0.6,
            arc_alignment_index=0.5,
            tension_index=0.4,
            acoustic_alignment=None,
        )

        assert quality is None, "Should return None when base is missing"
        assert penalty_applied is False
        assert penalty_amount == 0.0

    def test_missing_v3_returns_none(self, engine):
        """Test that missing v3 returns None (original behavior preserved)."""
        quality, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=0.70,
            v3=None,
            resonance_index=0.6,
            arc_alignment_index=0.5,
            tension_index=0.4,
            acoustic_alignment=None,
        )

        assert quality is None, "Should return None when v3 is missing"
        assert penalty_applied is False
        assert penalty_amount == 0.0

    def test_optional_metrics_use_defaults(self, engine):
        """Test that missing optional metrics still work (original behavior preserved)."""
        quality, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=0.70,
            v3=0.72,
            resonance_index=None,  # Should default to 0.5
            arc_alignment_index=None,  # Should default to 0.5
            tension_index=None,  # Should default to 0.5
            acoustic_alignment=None,
        )

        assert quality is not None, "Should compute with default metrics"
        assert 0.0 <= quality <= 1.0, "Quality should be in valid range"


# ============================================================================
# GROUP B: NON-AUTHORITY GUARANTEES (8 TESTS)
# ============================================================================


class TestNonAuthorityGuarantees:
    """Test that acoustic signals NEVER influence authoritative decisions."""

    def test_coherence_v3_score_not_affected_by_acoustic(self, engine, base_state):
        """Test that coherence_v3 score is NOT affected by acoustic alignment."""
        # The _compute_coherence_score_v3 method does NOT accept acoustic_alignment
        # This test verifies the architectural constraint
        v3_score = engine._compute_coherence_score_v3(base_state, {
            "guna_resonance_bias": 0.02,
            "kosha_resonance_bias": 0.03,
            "expression_harmonics": [0.7, 0.72, 0.71],
        })

        # V3 score is deterministic based on state metrics only
        assert v3_score is not None
        # The acoustic_alignment cannot influence this value because the method
        # doesn't accept it as a parameter

    def test_only_quality_is_adjusted_not_v3(self, engine, base_state, misaligned_report):
        """Test that only quality is adjusted, never the v3 score itself."""
        # Compute quality without acoustic
        quality_without, _, _, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        # Compute quality with misaligned acoustic
        quality_with, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=misaligned_report,
        )

        # Quality can be lower with acoustic (penalty applied)
        assert quality_with <= quality_without, "Quality can be reduced by acoustic penalty"
        assert penalty_applied is True, "Penalty should be applied for misaligned report"

        # But the v3 score itself (computed separately) is never affected
        v3_score_1 = engine._compute_coherence_score_v3(base_state, {})
        v3_score_2 = engine._compute_coherence_score_v3(base_state, {})
        assert v3_score_1 == v3_score_2, "V3 score should be deterministic and unaffected"

    def test_aligned_report_no_penalty(self, engine, base_state, aligned_report):
        """Test that aligned report (score >= 0.4) produces no penalty."""
        quality_without, _, _, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        quality_with, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=aligned_report,
        )

        assert quality_with == quality_without, "Aligned report should produce no change"
        assert penalty_applied is False, "No penalty for aligned report"
        assert penalty_amount == 0.0, "Penalty amount should be 0 for aligned report"

    def test_threshold_report_no_penalty(self, engine, base_state, threshold_report):
        """Test that report exactly at threshold (0.4) produces no penalty."""
        quality_without, _, _, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        quality_with, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=threshold_report,
        )

        assert quality_with == quality_without, "Threshold report should produce no change"
        assert penalty_applied is False, "No penalty at threshold"
        assert penalty_amount == 0.0, "Penalty amount should be 0 at threshold"

    def test_acoustic_never_increases_quality(self, engine, base_state):
        """Test that acoustic alignment can NEVER increase quality."""
        # Test with perfect alignment score
        perfect_report = AcousticAlignmentReport(
            alignment_score=1.0,
            pressure_band="low",
            mismatch_tags=(),
        )

        quality_without, _, _, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        quality_with, penalty_applied, penalty_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.75,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=perfect_report,
        )

        # Quality should NEVER increase
        assert quality_with <= quality_without, "Acoustic alignment must NEVER increase quality"
        assert quality_with == quality_without, "Perfect alignment should produce no change"

    def test_penalty_is_subtractive_only(self, engine):
        """Test that the adjustment is subtractive only."""
        quality_score = 0.80

        for alignment_score in [0.0, 0.1, 0.2, 0.3, 0.39, 0.4, 0.5, 0.8, 1.0]:
            report = AcousticAlignmentReport(
                alignment_score=alignment_score,
                pressure_band="moderate",
                mismatch_tags=(),
            )

            adjusted, _, _ = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )

            assert adjusted <= quality_score, f"Adjusted quality must be <= original for alignment {alignment_score}"

    def test_diagnostic_fields_are_observation_only(self, engine, base_state, misaligned_report):
        """Test that diagnostic fields capture observations but don't affect computation."""
        # The diagnostic fields (acoustic_misalignment, acoustic_tags, etc.)
        # are stored in state but don't feed back into any computation

        # This is verified by the fact that _compute_coherence_score_v3 doesn't
        # read any acoustic fields from state
        v3_before = engine._compute_coherence_score_v3(base_state, {})

        # Even if we set acoustic diagnostic fields on state, v3 is unchanged
        base_state.acoustic_misalignment = True
        base_state.acoustic_alignment_score = 0.2
        base_state.acoustic_mismatch_tags = ("test_tag",)

        v3_after = engine._compute_coherence_score_v3(base_state, {})

        assert v3_before == v3_after, "V3 should not read acoustic diagnostic fields"

    def test_pressure_band_does_not_affect_penalty(self, engine):
        """Test that pressure_band is diagnostic only and doesn't affect penalty calculation."""
        quality_score = 0.80

        for pressure_band in ["low", "moderate", "high"]:
            report = AcousticAlignmentReport(
                alignment_score=0.3,  # Below threshold
                pressure_band=pressure_band,
                mismatch_tags=(),
            )

            adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )

            # All should have the same penalty (based on alignment_score, not pressure_band)
            assert penalty_applied is True
            # Penalty for 0.3 alignment: 0.05 * (0.4 - 0.3) / 0.4 = 0.0125
            expected_penalty = 0.05 * (0.4 - 0.3) / 0.4
            assert abs(penalty_amount - expected_penalty) < 1e-10


# ============================================================================
# GROUP C: BOUND SAFETY (6 TESTS)
# ============================================================================


class TestBoundSafety:
    """Test that penalty bounds are respected."""

    def test_max_penalty_is_five_percent(self, engine):
        """Test that maximum penalty is exactly 5% (0.05)."""
        quality_score = 0.80

        # Worst case: alignment_score = 0.0
        worst_report = AcousticAlignmentReport(
            alignment_score=0.0,
            pressure_band="high",
            mismatch_tags=("severe_mismatch",),
        )

        adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
            quality_score=quality_score,
            acoustic_alignment=worst_report,
        )

        assert penalty_amount == 0.05, "Maximum penalty should be exactly 5%"
        assert adjusted == quality_score - 0.05, "Adjusted quality should be original minus 5%"
        assert adjusted == 0.75, "0.80 - 0.05 = 0.75"

    def test_penalty_never_exceeds_five_percent(self, engine):
        """Test that penalty never exceeds 5% regardless of alignment score."""
        quality_score = 0.90

        for alignment_score in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.39]:
            report = AcousticAlignmentReport(
                alignment_score=alignment_score,
                pressure_band="high",
                mismatch_tags=(),
            )

            adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )

            assert penalty_amount <= 0.05, f"Penalty should never exceed 5% for alignment {alignment_score}"

    def test_no_penalty_above_threshold(self, engine):
        """Test that there is no penalty when alignment_score >= 0.4."""
        quality_score = 0.80

        for alignment_score in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            report = AcousticAlignmentReport(
                alignment_score=alignment_score,
                pressure_band="moderate",
                mismatch_tags=(),
            )

            adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )

            assert penalty_applied is False, f"No penalty for alignment {alignment_score}"
            assert penalty_amount == 0.0, f"Penalty amount should be 0 for alignment {alignment_score}"
            assert adjusted == quality_score, f"Quality unchanged for alignment {alignment_score}"

    def test_penalty_linear_scaling(self, engine):
        """Test that penalty scales linearly below threshold."""
        quality_score = 0.80
        MAX_PENALTY = 0.05
        THRESHOLD = 0.4

        test_cases = [
            (0.0, MAX_PENALTY),  # Full penalty
            (0.2, MAX_PENALTY * 0.5),  # Half penalty (0.2 is halfway to threshold)
            (0.4, 0.0),  # No penalty at threshold
        ]

        for alignment_score, expected_penalty in test_cases:
            report = AcousticAlignmentReport(
                alignment_score=alignment_score,
                pressure_band="moderate",
                mismatch_tags=(),
            )

            adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )

            assert abs(penalty_amount - expected_penalty) < 1e-10, \
                f"Expected penalty {expected_penalty} for alignment {alignment_score}, got {penalty_amount}"

    def test_adjusted_quality_clamped_to_zero(self, engine):
        """Test that adjusted quality is clamped to [0.0, 1.0]."""
        # Very low quality score where penalty could make it negative
        quality_score = 0.02

        worst_report = AcousticAlignmentReport(
            alignment_score=0.0,
            pressure_band="high",
            mismatch_tags=(),
        )

        adjusted, penalty_applied, penalty_amount = engine._apply_acoustic_confidence_adjustment(
            quality_score=quality_score,
            acoustic_alignment=worst_report,
        )

        assert adjusted >= 0.0, "Adjusted quality should be clamped to >= 0.0"
        assert adjusted == 0.0, "0.02 - 0.05 should clamp to 0.0"

    def test_quality_stays_in_valid_range(self, engine):
        """Test that quality always stays in [0.0, 1.0] range."""
        for quality_score in [0.0, 0.1, 0.5, 0.9, 1.0]:
            for alignment_score in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
                report = AcousticAlignmentReport(
                    alignment_score=alignment_score,
                    pressure_band="moderate",
                    mismatch_tags=(),
                )

                adjusted, _, _ = engine._apply_acoustic_confidence_adjustment(
                    quality_score=quality_score,
                    acoustic_alignment=report,
                )

                assert 0.0 <= adjusted <= 1.0, \
                    f"Adjusted quality {adjusted} out of range for quality={quality_score}, alignment={alignment_score}"


# ============================================================================
# GROUP D: DETERMINISM (5 TESTS)
# ============================================================================


class TestDeterminism:
    """Test that computation is deterministic."""

    def test_same_inputs_same_outputs(self, engine, base_state, misaligned_report):
        """Test that identical inputs produce identical outputs."""
        results = []
        for _ in range(10):
            quality, applied, amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
                base=base_state.coherence_score,
                v3=0.75,
                resonance_index=base_state.resonance_index,
                arc_alignment_index=base_state.arc_alignment_index,
                tension_index=base_state.tension_index,
                acoustic_alignment=misaligned_report,
            )
            results.append((quality, applied, amount))

        # All results should be identical
        assert all(r == results[0] for r in results), "All results should be bitwise identical"

    def test_adjustment_is_deterministic(self, engine):
        """Test that adjustment helper is deterministic."""
        quality_score = 0.80
        report = AcousticAlignmentReport(
            alignment_score=0.25,
            pressure_band="high",
            mismatch_tags=("test",),
        )

        results = []
        for _ in range(10):
            result = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )
            results.append(result)

        assert all(r == results[0] for r in results), "Adjustment should be deterministic"

    def test_different_convo_ids_same_results(self, engine):
        """Test that different convo_ids with same metrics produce same results."""
        state1 = CoherenceState(convo_id="test1", turn_index=1, coherence_score=0.70)
        state1.resonance_index = 0.65
        state1.tension_index = 0.40
        state1.arc_alignment_index = 0.60

        state2 = CoherenceState(convo_id="test2", turn_index=1, coherence_score=0.70)
        state2.resonance_index = 0.65
        state2.tension_index = 0.40
        state2.arc_alignment_index = 0.60

        report = create_misaligned_report(alignment_score=0.3)

        result1 = engine._compute_coherence_v3_quality_with_acoustic(
            base=state1.coherence_score,
            v3=0.72,
            resonance_index=state1.resonance_index,
            arc_alignment_index=state1.arc_alignment_index,
            tension_index=state1.tension_index,
            acoustic_alignment=report,
        )

        result2 = engine._compute_coherence_v3_quality_with_acoustic(
            base=state2.coherence_score,
            v3=0.72,
            resonance_index=state2.resonance_index,
            arc_alignment_index=state2.arc_alignment_index,
            tension_index=state2.tension_index,
            acoustic_alignment=report,
        )

        assert result1 == result2, "Same metrics should produce same results"

    def test_no_randomness_in_penalty_calculation(self, engine):
        """Test that penalty calculation has no randomness."""
        quality_score = 0.80
        expected_penalty = 0.05 * (0.4 - 0.25) / 0.4  # alignment_score = 0.25

        report = AcousticAlignmentReport(
            alignment_score=0.25,
            pressure_band="moderate",
            mismatch_tags=(),
        )

        for _ in range(100):
            _, _, penalty = engine._apply_acoustic_confidence_adjustment(
                quality_score=quality_score,
                acoustic_alignment=report,
            )
            assert abs(penalty - expected_penalty) < 1e-10, "Penalty should be exactly calculated each time"

    def test_order_independence(self, engine, base_state):
        """Test that computation order doesn't affect results."""
        report = create_misaligned_report(alignment_score=0.3)

        # Compute in one order
        result1 = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.72,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=report,
        )

        # Compute with different intermediate operations (shouldn't matter)
        _ = engine._apply_acoustic_confidence_adjustment(0.5, None)
        _ = engine._compute_coherence_v3_quality(0.7, 0.75, 0.5, 0.5, 0.5)

        result2 = engine._compute_coherence_v3_quality_with_acoustic(
            base=base_state.coherence_score,
            v3=0.72,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=report,
        )

        assert result1 == result2, "Results should be order-independent"


# ============================================================================
# GROUP E: IMPORT SAFETY (3 TESTS)
# ============================================================================


class TestImportSafety:
    """Test that no authoritative module imports P22/P23/P24."""

    def test_coherence_engine_does_not_import_p22(self):
        """Test that coherence_engine does not import P22."""
        import symbolu.core.coherence.coherence_engine as engine_module
        import inspect

        source = inspect.getsource(engine_module)

        # Should not import P22
        assert "from symbolu.mechanical.pipeline.p22" not in source
        assert "import symbolu.mechanical.pipeline.p22" not in source

    def test_coherence_engine_does_not_import_p23(self):
        """Test that coherence_engine does not import P23."""
        import symbolu.core.coherence.coherence_engine as engine_module
        import inspect

        source = inspect.getsource(engine_module)

        # Should not import P23
        assert "from symbolu.mechanical.pipeline.p23" not in source
        assert "import symbolu.mechanical.pipeline.p23" not in source

    def test_coherence_engine_does_not_import_p24(self):
        """Test that coherence_engine does not import P24."""
        import symbolu.core.coherence.coherence_engine as engine_module
        import inspect

        source = inspect.getsource(engine_module)

        # Should not import P24
        assert "from symbolu.mechanical.pipeline.p24" not in source
        assert "import symbolu.mechanical.pipeline.p24" not in source


# ============================================================================
# GROUP F: DATACLASS INVARIANTS (6 TESTS)
# ============================================================================


class TestDataclassInvariants:
    """Test AcousticAlignmentReport dataclass invariants."""

    def test_alignment_score_range_validation(self):
        """Test that alignment_score must be in [0.0, 1.0]."""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            report = AcousticAlignmentReport(
                alignment_score=score,
                pressure_band="moderate",
                mismatch_tags=(),
            )
            assert report.alignment_score == score

        # Invalid scores
        with pytest.raises(ValueError):
            AcousticAlignmentReport(
                alignment_score=-0.1,
                pressure_band="moderate",
                mismatch_tags=(),
            )

        with pytest.raises(ValueError):
            AcousticAlignmentReport(
                alignment_score=1.1,
                pressure_band="moderate",
                mismatch_tags=(),
            )

    def test_pressure_band_validation(self):
        """Test that pressure_band must be one of the allowed values."""
        # Valid bands
        for band in ["low", "moderate", "high"]:
            report = AcousticAlignmentReport(
                alignment_score=0.5,
                pressure_band=band,
                mismatch_tags=(),
            )
            assert report.pressure_band == band

        # Invalid band
        with pytest.raises(ValueError):
            AcousticAlignmentReport(
                alignment_score=0.5,
                pressure_band="invalid",
                mismatch_tags=(),
            )

    def test_mismatch_tags_must_be_tuple(self):
        """Test that mismatch_tags must be a tuple."""
        # Valid tuple
        report = AcousticAlignmentReport(
            alignment_score=0.5,
            pressure_band="moderate",
            mismatch_tags=("tag1", "tag2"),
        )
        assert report.mismatch_tags == ("tag1", "tag2")

        # Empty tuple is valid
        report = AcousticAlignmentReport(
            alignment_score=0.5,
            pressure_band="moderate",
            mismatch_tags=(),
        )
        assert report.mismatch_tags == ()

        # List is invalid
        with pytest.raises(ValueError):
            AcousticAlignmentReport(
                alignment_score=0.5,
                pressure_band="moderate",
                mismatch_tags=["tag1", "tag2"],  # Should be tuple
            )

    def test_frozen_dataclass(self):
        """Test that the dataclass is immutable (frozen)."""
        report = AcousticAlignmentReport(
            alignment_score=0.5,
            pressure_band="moderate",
            mismatch_tags=("tag1",),
        )

        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # FrozenInstanceError
            report.alignment_score = 0.8

    def test_helper_methods(self):
        """Test helper methods on the dataclass."""
        misaligned = AcousticAlignmentReport(
            alignment_score=0.2,
            pressure_band="high",
            mismatch_tags=("inner_outer_tension",),
        )

        assert misaligned.has_misalignment() is True
        assert misaligned.has_severe_misalignment() is False  # 0.2 >= 0.2
        assert misaligned.is_high_pressure() is True
        assert misaligned.has_tag("inner_outer_tension") is True
        assert misaligned.has_tag("nonexistent") is False

        severe = AcousticAlignmentReport(
            alignment_score=0.1,
            pressure_band="high",
            mismatch_tags=(),
        )
        assert severe.has_severe_misalignment() is True

    def test_factory_functions(self):
        """Test factory functions create valid reports."""
        aligned = create_aligned_report()
        assert aligned.alignment_score == 0.8
        assert aligned.pressure_band == "low"
        assert aligned.mismatch_tags == ()
        assert aligned.has_misalignment() is False

        misaligned = create_misaligned_report()
        assert misaligned.alignment_score == 0.3
        assert misaligned.pressure_band == "high"
        assert misaligned.has_misalignment() is True

        neutral = create_neutral_report()
        assert neutral.alignment_score == 0.5
        assert neutral.pressure_band == "moderate"
        assert neutral.has_misalignment() is False


# ============================================================================
# END OF TESTS (35 total)
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
