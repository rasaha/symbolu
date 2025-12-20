"""
Phase 40 - Cross-Horizon Resonance Alignment Tests

Test suite for P40 following the TESTING.md policy:
    - Exactly one test per invariant
    - Each test must declare which invariant it proves

INVARIANTS TESTED:
    - INV-P40-1: Observer-only (no influence on any authoritative phase)
    - INV-P40-2: Deterministic (same inputs -> same outputs)
    - INV-P40-3: No forecast mutation (Phase 39 values are never changed)
    - INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
    - INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
"""

import copy
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from symbolu.mechanical.pipeline.p40_cross_horizon_alignment import (
    P40_VERSION,
    CrossHorizonAlignment,
    BAND_ALIGNED_THRESHOLD,
    BAND_STRAINED_THRESHOLD,
    DOMINANT_HORIZON_THRESHOLD,
    compute_divergence_index,
    compute_alignment_score,
    determine_dominant_horizon,
    resolve_cross_horizon_alignment,
    maybe_run_p40,
    run_p40_directly,
    is_p40_disabled,
    has_p40_alignment,
    get_p40_alignment,
    get_alignment_score,
    get_alignment_band,
    get_divergence_index,
    get_dominant_horizon,
    get_p40_version,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockP39:
    """Mock P39 multi-horizon forecast for testing."""

    short_term_score: float = 0.8
    medium_term_score: float = 0.7
    long_term_score: float = 0.6


@dataclass
class MockP19:
    """Mock P19 drift fusion report for testing."""

    drift_fusion_index: float = 0.3


@dataclass
class MockP18:
    """Mock P18 temporal entropy report for testing."""

    delta_entropy: float = 0.1


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""

    p39_multi_horizon: Optional[MockP39] = None
    p19: Optional[MockP19] = None
    p18: Optional[MockP18] = None
    p40_cross_horizon_alignment: Optional[CrossHorizonAlignment] = None
    _p40_disabled: bool = False

    # Upstream authoritative phases that P40 MUST NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p10_acoustic: Optional[Any] = None


# ============================================================================
# INVARIANT TESTS - One test per invariant as required by TESTING.md
# ============================================================================


# Proves INV-P40-1: Observer-only (no influence on any authoritative phase)
def test_inv_p40_1_observer_only_no_upstream_modification():
    """
    Invariant: INV-P40-1
    Proves that P40 does not modify any upstream authoritative phase envelopes.

    P40 must be observer-only: it reads from P39, P18, P19 but must never
    modify P6 regime, P7 discourse, semantic frame, lexical frame, or acoustics.
    It also must never modify the P39 forecast itself.
    """
    ctx = MockPipelineContext(
        p39_multi_horizon=MockP39(
            short_term_score=0.8,
            medium_term_score=0.7,
            long_term_score=0.6,
        ),
        p19=MockP19(drift_fusion_index=0.3),
        p18=MockP18(delta_entropy=0.1),
        p6_regime="test_regime",
        p7_discourse_envelope="test_discourse",
        semantic_frame="test_semantic",
        lexical_frame="test_lexical",
        p10_acoustic="test_acoustic",
    )

    # Store original values
    original_p6 = ctx.p6_regime
    original_p7 = ctx.p7_discourse_envelope
    original_semantic = ctx.semantic_frame
    original_lexical = ctx.lexical_frame
    original_acoustic = ctx.p10_acoustic
    original_p39 = copy.deepcopy(ctx.p39_multi_horizon)

    # Run P40
    result = maybe_run_p40(ctx)

    # Verify P40 ran successfully
    assert result is not None
    assert ctx.p40_cross_horizon_alignment is not None

    # Verify NO upstream phases were modified (INV-P40-1)
    assert ctx.p6_regime == original_p6, "P40 modified P6 regime"
    assert ctx.p7_discourse_envelope == original_p7, "P40 modified P7 discourse"
    assert ctx.semantic_frame == original_semantic, "P40 modified semantic frame"
    assert ctx.lexical_frame == original_lexical, "P40 modified lexical frame"
    assert ctx.p10_acoustic == original_acoustic, "P40 modified P10 acoustic"

    # Verify P39 was not modified (part of INV-P40-1 and INV-P40-3)
    assert ctx.p39_multi_horizon.short_term_score == original_p39.short_term_score
    assert ctx.p39_multi_horizon.medium_term_score == original_p39.medium_term_score
    assert ctx.p39_multi_horizon.long_term_score == original_p39.long_term_score

    # Verify observer_only flag is True
    assert result.observer_only is True


# Proves INV-P40-2: Deterministic (same inputs -> same outputs)
def test_inv_p40_2_deterministic_same_inputs_same_outputs():
    """
    Invariant: INV-P40-2
    Proves that identical inputs always produce identical outputs.

    P40 uses only deterministic math with fixed formulas. No LLM calls,
    no randomness, no external state dependencies.
    """
    inputs = {
        "short_term_score": 0.8,
        "medium_term_score": 0.65,
        "long_term_score": 0.5,
    }

    # Run 10 times and collect results
    results = []
    for _ in range(10):
        result = run_p40_directly(**inputs)
        results.append(result)

    # All results must be identical
    first = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result.alignment_score == first.alignment_score, (
            f"Run {i} alignment_score differs from run 1"
        )
        assert result.alignment_band == first.alignment_band, (
            f"Run {i} alignment_band differs from run 1"
        )
        assert result.divergence_index == first.divergence_index, (
            f"Run {i} divergence_index differs from run 1"
        )
        assert result.dominant_horizon == first.dominant_horizon, (
            f"Run {i} dominant_horizon differs from run 1"
        )


# Proves INV-P40-3: No forecast mutation (Phase 39 values are never changed)
def test_inv_p40_3_no_forecast_mutation():
    """
    Invariant: INV-P40-3
    Proves that Phase 39 forecast values are never modified by P40.

    P40 reads P39 horizon scores to compute alignment metrics, but it must
    never modify the P39 output in any way. The P39 values must remain
    exactly as they were before P40 ran.
    """
    # Create original P39 values
    original_short = 0.75
    original_medium = 0.60
    original_long = 0.45

    ctx = MockPipelineContext(
        p39_multi_horizon=MockP39(
            short_term_score=original_short,
            medium_term_score=original_medium,
            long_term_score=original_long,
        ),
    )

    # Run P40
    result = maybe_run_p40(ctx)

    # Verify P40 ran
    assert result is not None

    # Verify P39 values are UNCHANGED (INV-P40-3)
    assert ctx.p39_multi_horizon.short_term_score == original_short, (
        "P40 mutated P39 short_term_score"
    )
    assert ctx.p39_multi_horizon.medium_term_score == original_medium, (
        "P40 mutated P39 medium_term_score"
    )
    assert ctx.p39_multi_horizon.long_term_score == original_long, (
        "P40 mutated P39 long_term_score"
    )

    # Also verify the values stored in P40 output match the original inputs
    assert result.short_term_score == original_short
    assert result.medium_term_score == original_medium
    assert result.long_term_score == original_long


# Proves INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
def test_inv_p40_4_alignment_monotonicity():
    """
    Invariant: INV-P40-4
    Proves that greater divergence always results in lower alignment_score.

    The formula is: alignment_score = 1.0 - divergence_index
    This guarantees a strictly monotonic inverse relationship.
    """
    test_cases = [
        # (short, medium, long) -> expected divergence order
        # Lower divergence should give higher alignment_score
        (0.8, 0.8, 0.8),    # Zero divergence (0.0)
        (0.8, 0.75, 0.7),   # Small divergence (0.1)
        (0.8, 0.6, 0.5),    # Medium divergence (0.3)
        (0.9, 0.5, 0.4),    # Large divergence (0.5)
        (1.0, 0.5, 0.0),    # Maximum divergence (1.0)
    ]

    results = []
    for short, medium, long in test_cases:
        result = run_p40_directly(
            short_term_score=short,
            medium_term_score=medium,
            long_term_score=long,
        )
        results.append(result)

    # Verify monotonicity: as divergence increases, alignment decreases
    for i in range(len(results) - 1):
        current = results[i]
        next_result = results[i + 1]

        # If divergence increased, alignment must have decreased (or stayed same if equal)
        if next_result.divergence_index > current.divergence_index:
            assert next_result.alignment_score < current.alignment_score, (
                f"INV-P40-4 violated: divergence increased from {current.divergence_index} "
                f"to {next_result.divergence_index}, but alignment_score did not decrease "
                f"(was {current.alignment_score}, now {next_result.alignment_score})"
            )

    # Also verify the formula holds exactly: alignment_score = 1.0 - divergence_index
    for result in results:
        expected_alignment = 1.0 - result.divergence_index
        assert abs(result.alignment_score - expected_alignment) < 1e-9, (
            f"Alignment formula violated: expected {expected_alignment}, "
            f"got {result.alignment_score}"
        )


# Proves INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
def test_inv_p40_5_absence_safe():
    """
    Invariant: INV-P40-5
    Proves that missing optional inputs (P18, P19) do not improve alignment.

    P40's core computation only uses P39 horizon scores. The optional
    P18/P19 inputs are stored for observability but do not affect the
    alignment calculation. Therefore, their absence cannot inflate
    alignment scores.
    """
    # Test with P39 scores only (P18/P19 missing)
    result_without_optionals = run_p40_directly(
        short_term_score=0.8,
        medium_term_score=0.7,
        long_term_score=0.6,
        drift_fusion_index=None,  # Missing
        temporal_entropy_diff=None,  # Missing
    )

    # Test with same P39 scores plus optional inputs
    result_with_optionals = run_p40_directly(
        short_term_score=0.8,
        medium_term_score=0.7,
        long_term_score=0.6,
        drift_fusion_index=0.3,  # Present
        temporal_entropy_diff=0.1,  # Present
    )

    # Core alignment metrics must be identical regardless of optional inputs
    # (INV-P40-5: absence does not inflate, presence does not deflate)
    assert result_without_optionals.alignment_score == result_with_optionals.alignment_score, (
        "Alignment score changed based on optional inputs"
    )
    assert result_without_optionals.divergence_index == result_with_optionals.divergence_index, (
        "Divergence index changed based on optional inputs"
    )
    assert result_without_optionals.alignment_band == result_with_optionals.alignment_band, (
        "Alignment band changed based on optional inputs"
    )
    assert result_without_optionals.dominant_horizon == result_with_optionals.dominant_horizon, (
        "Dominant horizon changed based on optional inputs"
    )

    # Verify that missing P39 required inputs returns None (graceful degradation)
    result_missing_required = run_p40_directly(
        short_term_score=None,  # Missing required input
        medium_term_score=0.7,
        long_term_score=0.6,
    )
    assert result_missing_required is None, (
        "P40 should return None when required P39 inputs are missing"
    )


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
