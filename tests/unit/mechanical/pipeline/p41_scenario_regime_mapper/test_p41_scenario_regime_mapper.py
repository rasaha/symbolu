"""
Phase 41 - Coherence-Regime Scenario Mapper Tests

Test suite for P41 following the TESTING.md policy:
    - Exactly one test per invariant
    - Each test must declare which invariant it proves

INVARIANTS TESTED:
    - INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
    - INV-P41-2: Deterministic (same inputs -> same outputs)
    - INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
    - INV-P41-4: Monotonic consistency (lower coherence / alignment cannot yield "better" regimes)
    - INV-P41-5: Absence-safe (missing optional inputs degrade confidence, never improve it)
"""

import copy
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from symbolu.mechanical.pipeline.p41_scenario_regime_mapper import (
    P41_VERSION,
    ScenarioRegimeMap,
    STABLE_COHERENCE_THRESHOLD,
    STABLE_ALIGNMENT_THRESHOLD,
    STABLE_DRIFT_MAX_THRESHOLD,
    STRAINED_COHERENCE_THRESHOLD,
    STRAINED_ALIGNMENT_THRESHOLD,
    STRAINED_DRIFT_MAX_THRESHOLD,
    DIVERGENT_ALIGNMENT_THRESHOLD,
    DIVERGENT_DRIFT_THRESHOLD,
    resolve_scenario_regime,
    maybe_run_p41,
    run_p41_directly,
    is_p41_disabled,
    has_p41_scenario_map,
    get_p41_scenario_map,
    get_scenario_regime,
    get_regime_confidence,
    get_p41_version,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""

    coherence_v3_quality: Optional[float] = 0.75
    coherence_score_v3: Optional[float] = 0.75
    coherence_fused: Optional[float] = 0.75


@dataclass
class MockP40:
    """Mock P40 cross-horizon alignment for testing."""

    alignment_score: float = 0.75
    alignment_band: str = "aligned"
    divergence_index: float = 0.2
    dominant_horizon: str = "none"
    observer_only: bool = True


@dataclass
class MockP19:
    """Mock P19 drift fusion report for testing."""

    drift_fusion_index: float = 0.25
    drift_risk_band: str = "low"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""

    coherence_state: Optional[MockCoherenceState] = None
    p40_cross_horizon_alignment: Optional[MockP40] = None
    p19: Optional[MockP19] = None
    p41_scenario_regime_map: Optional[ScenarioRegimeMap] = None
    _p41_disabled: bool = False

    # Upstream authoritative phases that P41 MUST NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p10_acoustic: Optional[Any] = None
    p32: Optional[Any] = None


# ============================================================================
# INVARIANT TESTS - One test per invariant as required by TESTING.md
# ============================================================================


# Proves INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
def test_inv_p41_1_observer_only_no_upstream_modification():
    """
    Invariant: INV-P41-1
    Proves that P41 does not modify any upstream authoritative phase envelopes.

    P41 must be observer-only: it reads from coherence_state, P19, P40 but must
    never modify P6 regime, P7 discourse, semantic frame, lexical frame, acoustics,
    or P32 insight gating. It also must never modify the source inputs themselves.

    P41 answers one question only:
    "Given coherence, drift, and horizon alignment, which scenario regimes are plausible?"

    It maps signals -> scenario labels, NOT decisions.
    """
    ctx = MockPipelineContext(
        coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
        p40_cross_horizon_alignment=MockP40(alignment_score=0.8),
        p19=MockP19(drift_fusion_index=0.2),
        p6_regime="test_regime",
        p7_discourse_envelope="test_discourse",
        semantic_frame="test_semantic",
        lexical_frame="test_lexical",
        p10_acoustic="test_acoustic",
        p32="test_p32_gating",
    )

    # Store original values
    original_p6 = ctx.p6_regime
    original_p7 = ctx.p7_discourse_envelope
    original_semantic = ctx.semantic_frame
    original_lexical = ctx.lexical_frame
    original_acoustic = ctx.p10_acoustic
    original_p32 = ctx.p32
    original_coherence_state = copy.deepcopy(ctx.coherence_state)
    original_p40 = copy.deepcopy(ctx.p40_cross_horizon_alignment)
    original_p19 = copy.deepcopy(ctx.p19)

    # Run P41
    result = maybe_run_p41(ctx)

    # Verify P41 ran successfully
    assert result is not None
    assert ctx.p41_scenario_regime_map is not None

    # Verify NO upstream phases were modified (INV-P41-1)
    assert ctx.p6_regime == original_p6, "P41 modified P6 regime"
    assert ctx.p7_discourse_envelope == original_p7, "P41 modified P7 discourse"
    assert ctx.semantic_frame == original_semantic, "P41 modified semantic frame"
    assert ctx.lexical_frame == original_lexical, "P41 modified lexical frame"
    assert ctx.p10_acoustic == original_acoustic, "P41 modified P10 acoustic"
    assert ctx.p32 == original_p32, "P41 modified P32 insight gating"

    # Verify input sources were not modified
    assert ctx.coherence_state.coherence_v3_quality == original_coherence_state.coherence_v3_quality
    assert ctx.p40_cross_horizon_alignment.alignment_score == original_p40.alignment_score
    assert ctx.p19.drift_fusion_index == original_p19.drift_fusion_index

    # Verify observer_only flag is True
    assert result.observer_only is True


# Proves INV-P41-2: Deterministic (same inputs -> same outputs)
def test_inv_p41_2_deterministic_same_inputs_same_outputs():
    """
    Invariant: INV-P41-2
    Proves that identical inputs always produce identical outputs.

    P41 uses only deterministic math with fixed formulas. No LLM calls,
    no randomness, no external state dependencies.
    """
    inputs = {
        "coherence_v3_quality": 0.8,
        "alignment_score": 0.75,
        "drift_fusion_index": 0.25,
    }

    # Run 10 times and collect results
    results = []
    for _ in range(10):
        result = run_p41_directly(**inputs)
        results.append(result)

    # All results must be identical
    first = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result.scenario_regime == first.scenario_regime, (
            f"Run {i} scenario_regime differs from run 1"
        )
        assert result.confidence == first.confidence, (
            f"Run {i} confidence differs from run 1"
        )
        assert result.supporting_signals == first.supporting_signals, (
            f"Run {i} supporting_signals differs from run 1"
        )
        assert result.coherence_v3_quality == first.coherence_v3_quality, (
            f"Run {i} coherence_v3_quality differs from run 1"
        )
        assert result.alignment_score == first.alignment_score, (
            f"Run {i} alignment_score differs from run 1"
        )
        assert result.drift_fusion_index == first.drift_fusion_index, (
            f"Run {i} drift_fusion_index differs from run 1"
        )


# Proves INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
def test_inv_p41_3_scenario_labels_only():
    """
    Invariant: INV-P41-3
    Proves that P41 outputs only scenario labels, not probabilities or forecasts.

    The output is a ScenarioRegimeMap with:
    - scenario_regime: One of exactly 4 discrete labels
    - confidence: A simple weighted score, NOT a probability distribution
    - supporting_signals: String tags only, no interpretation text

    P41 does NOT:
    - Output probability distributions over scenarios
    - Forecast future states
    - Optimize or recommend actions
    - Provide reasoning chains
    """
    # Test that output is one of exactly 4 discrete labels
    valid_regimes = {
        "stable_continuity",
        "strained_transition",
        "divergent_instability",
        "ambiguous_mixed",
    }

    # Test various inputs to ensure we only get valid labels
    test_cases = [
        {"coherence_v3_quality": 0.9, "alignment_score": 0.9, "drift_fusion_index": 0.1},
        {"coherence_v3_quality": 0.6, "alignment_score": 0.5, "drift_fusion_index": 0.4},
        {"coherence_v3_quality": 0.3, "alignment_score": 0.3, "drift_fusion_index": 0.8},
        {"coherence_v3_quality": 0.5, "alignment_score": 0.5, "drift_fusion_index": 0.5},
    ]

    for inputs in test_cases:
        result = run_p41_directly(**inputs)
        assert result is not None

        # Verify scenario_regime is one of exactly 4 labels
        assert result.scenario_regime in valid_regimes, (
            f"Invalid scenario_regime: {result.scenario_regime}"
        )

        # Verify confidence is a single scalar, not a distribution
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

        # Verify supporting_signals are string tags only
        assert isinstance(result.supporting_signals, tuple)
        for signal in result.supporting_signals:
            assert isinstance(signal, str)
            # Signals should be simple tags, not interpretation text
            assert len(signal) < 50, "Signal too long - should be a tag, not text"
            assert " " not in signal or signal.count(" ") < 3, (
                "Signal has too many spaces - should be a tag, not prose"
            )


# Proves INV-P41-4: Monotonic consistency (lower coherence / alignment cannot yield "better" regimes)
def test_inv_p41_4_monotonic_consistency():
    """
    Invariant: INV-P41-4
    Proves that lower coherence / alignment cannot yield "better" regimes.

    The regime ordering from best to worst is:
    1. stable_continuity (best)
    2. strained_transition
    3. ambiguous_mixed
    4. divergent_instability (worst)

    Decreasing coherence or alignment (or increasing drift) should never
    result in moving to a "better" regime.
    """
    # Define regime ordering (lower index = better)
    regime_order = {
        "stable_continuity": 0,
        "strained_transition": 1,
        "ambiguous_mixed": 2,
        "divergent_instability": 3,
    }

    # Test decreasing coherence (alignment and drift constant)
    coherence_sequence = [0.9, 0.7, 0.5, 0.3]
    prev_regime_rank = -1
    for cq in coherence_sequence:
        result = run_p41_directly(
            coherence_v3_quality=cq,
            alignment_score=0.6,
            drift_fusion_index=0.4,
        )
        current_rank = regime_order[result.scenario_regime]
        assert current_rank >= prev_regime_rank, (
            f"INV-P41-4 violated: coherence decreased from previous to {cq}, "
            f"but regime improved from rank {prev_regime_rank} to {current_rank}"
        )
        prev_regime_rank = current_rank

    # Test decreasing alignment (coherence and drift constant)
    alignment_sequence = [0.9, 0.6, 0.4, 0.2]
    prev_regime_rank = -1
    for al in alignment_sequence:
        result = run_p41_directly(
            coherence_v3_quality=0.6,
            alignment_score=al,
            drift_fusion_index=0.4,
        )
        current_rank = regime_order[result.scenario_regime]
        assert current_rank >= prev_regime_rank, (
            f"INV-P41-4 violated: alignment decreased from previous to {al}, "
            f"but regime improved from rank {prev_regime_rank} to {current_rank}"
        )
        prev_regime_rank = current_rank

    # Test increasing drift (coherence and alignment constant)
    drift_sequence = [0.1, 0.4, 0.6, 0.8]
    prev_regime_rank = -1
    for dfi in drift_sequence:
        result = run_p41_directly(
            coherence_v3_quality=0.6,
            alignment_score=0.6,
            drift_fusion_index=dfi,
        )
        current_rank = regime_order[result.scenario_regime]
        assert current_rank >= prev_regime_rank, (
            f"INV-P41-4 violated: drift increased from previous to {dfi}, "
            f"but regime improved from rank {prev_regime_rank} to {current_rank}"
        )
        prev_regime_rank = current_rank


# Proves INV-P41-5: Absence-safe (missing optional inputs degrade confidence, never improve it)
def test_inv_p41_5_absence_safe():
    """
    Invariant: INV-P41-5
    Proves that missing optional inputs degrade confidence, never improve it.

    Missing inputs are handled with neutral defaults (0.5) and an absence
    penalty is applied to confidence. This ensures that:
    1. Missing inputs cannot inflate the regime classification to "better" regimes
    2. Missing inputs reduce confidence, never increase it
    3. All inputs missing returns None (graceful degradation)
    """
    # Test with all inputs present
    result_all_present = run_p41_directly(
        coherence_v3_quality=0.7,
        alignment_score=0.7,
        drift_fusion_index=0.3,
    )

    # Test with coherence missing (should use default 0.5)
    result_cq_missing = run_p41_directly(
        coherence_v3_quality=None,
        alignment_score=0.7,
        drift_fusion_index=0.3,
    )

    # Test with alignment missing (should use default 0.5)
    result_al_missing = run_p41_directly(
        coherence_v3_quality=0.7,
        alignment_score=None,
        drift_fusion_index=0.3,
    )

    # Test with drift missing (should use default 0.5)
    result_dfi_missing = run_p41_directly(
        coherence_v3_quality=0.7,
        alignment_score=0.7,
        drift_fusion_index=None,
    )

    # Verify all results are valid (not None)
    assert result_all_present is not None
    assert result_cq_missing is not None
    assert result_al_missing is not None
    assert result_dfi_missing is not None

    # Verify that missing inputs resulted in absence penalty signal
    assert "absence_penalty" in result_cq_missing.supporting_signals
    assert "absence_penalty" in result_al_missing.supporting_signals
    assert "absence_penalty" in result_dfi_missing.supporting_signals

    # Verify confidence is degraded when inputs are missing
    # (absence penalty reduces confidence by 10% per missing input)
    assert result_cq_missing.confidence < result_all_present.confidence, (
        "Missing coherence should reduce confidence"
    )
    assert result_al_missing.confidence < result_all_present.confidence, (
        "Missing alignment should reduce confidence"
    )
    # Note: Missing drift uses neutral 0.5, but original was 0.3
    # The formula includes (1-drift), so neutral drift may actually reduce confidence
    # Still, the absence penalty should apply

    # Test that ALL inputs missing returns None (graceful degradation)
    result_all_missing = run_p41_directly(
        coherence_v3_quality=None,
        alignment_score=None,
        drift_fusion_index=None,
    )
    assert result_all_missing is None, (
        "P41 should return None when all inputs are missing"
    )

    # Verify that missing inputs default to neutral (0.5), not favorable values
    # Check via context extraction - absent coherence should not yield stable_continuity
    ctx_missing_cq = MockPipelineContext(
        coherence_state=None,  # Missing coherence state
        p40_cross_horizon_alignment=MockP40(alignment_score=0.9),
        p19=MockP19(drift_fusion_index=0.1),
    )
    result_ctx_missing = maybe_run_p41(ctx_missing_cq)
    assert result_ctx_missing is not None
    # With neutral coherence (0.5) instead of high (0.9), should not get stable_continuity
    # even with high alignment and low drift, because coherence threshold is 0.75
    assert result_ctx_missing.scenario_regime != "stable_continuity" or (
        result_ctx_missing.coherence_v3_quality >= STABLE_COHERENCE_THRESHOLD
    ), "Absent coherence should not inflate to stable_continuity"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
