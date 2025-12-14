"""
Phase 44: Coherence-Scenario Alignment Engine Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no UI tests, no redundancy

INVARIANTS:
    INV-P44-1: Measurement only (no ranking, no preference, no selection)
    INV-P44-2: Deterministic math only (no randomness, no learned parameters)
    INV-P44-3: Variant isolation (variants do not influence base alignment)
    INV-P44-4: No authority influence (output never affects regime, discourse, policy)
    INV-P44-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass
from typing import Tuple

import pytest

from symbolu.mechanical.pipeline.p44_coherence_scenario_alignment import (
    run_p44_directly,
    maybe_run_p44,
    CoherenceScenarioAlignmentReport,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockScenarioVariant:
    """Mock ScenarioVariant for testing."""

    variant_id: str
    perturbation_type: str
    resulting_regime: str
    delta_entropy: float
    delta_confidence: float


@dataclass
class MockScenarioFusionField:
    """Mock ScenarioFusionField for testing."""

    dominant_regime: str
    fusion_confidence: float
    regime_entropy: float
    observer_only: bool = True


@dataclass
class MockScenarioWhatIfSet:
    """Mock ScenarioWhatIfSet for testing."""

    base_regime: str
    what_if_variants: Tuple[MockScenarioVariant, ...]
    variant_count: int
    observer_only: bool = True


class MockContext:
    """Mock PipelineContext for testing."""

    def __init__(self):
        self.coherence_v3_quality = None
        self.p42_scenario_fusion_field = None
        self.p43_scenario_what_if = None
        self.p44_coherence_scenario_alignment = None
        self._p44_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P44-1: Measurement only (no ranking, no preference, no selection)
def test_measurement_only_no_ranking_or_preference():
    """
    Invariant: INV-P44-1
    Proves that P44 produces alignment measurements without any ranking,
    preference ordering, or selection between variants.

    The output contains individual variant scores but no 'best' variant,
    no ordering, and no selection recommendation.
    """
    # Create variants with different delta values
    variants = (
        MockScenarioVariant(
            variant_id="v1",
            perturbation_type="entropy_shift",
            resulting_regime="stable_continuity",
            delta_entropy=0.05,
            delta_confidence=0.05,
        ),
        MockScenarioVariant(
            variant_id="v2",
            perturbation_type="confidence_drop",
            resulting_regime="strained_transition",
            delta_entropy=0.10,
            delta_confidence=0.10,
        ),
        MockScenarioVariant(
            variant_id="v3",
            perturbation_type="regime_flip",
            resulting_regime="divergent_instability",
            delta_entropy=0.15,
            delta_confidence=0.15,
        ),
        MockScenarioVariant(
            variant_id="v4",
            perturbation_type="noise_injection",
            resulting_regime="ambiguous_mixed",
            delta_entropy=0.02,
            delta_confidence=0.02,
        ),
    )

    report = run_p44_directly(
        coherence_v3_quality=0.75,
        scenario_fusion_confidence=0.80,
        what_if_variants=variants,
    )

    assert report is not None

    # Verify: No ranking attributes exist
    assert not hasattr(report, "ranked_variants")
    assert not hasattr(report, "best_variant")
    assert not hasattr(report, "preferred_variant")
    assert not hasattr(report, "selected_variant")
    assert not hasattr(report, "variant_ranking")

    # Verify: variant_alignment is a flat dict, not an ordered structure
    assert isinstance(report.variant_alignment, dict)
    assert all(isinstance(k, str) for k in report.variant_alignment.keys())
    assert all(isinstance(v, float) for v in report.variant_alignment.values())

    # Verify: All variants have individual scores (measurement only)
    assert len(report.variant_alignment) == 4
    for v in variants:
        assert v.variant_id in report.variant_alignment


# Proves INV-P44-2: Deterministic math only (no randomness, no learned parameters)
def test_deterministic_computation():
    """
    Invariant: INV-P44-2
    Proves that P44 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness.
    """
    variants = (
        MockScenarioVariant(
            variant_id="v1",
            perturbation_type="entropy_shift",
            resulting_regime="stable_continuity",
            delta_entropy=0.10,
            delta_confidence=0.05,
        ),
    )

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p44_directly(
            coherence_v3_quality=0.65,
            scenario_fusion_confidence=0.70,
            what_if_variants=variants,
        )
        results.append(result)

    # Verify: All results are identical
    first_result = results[0]
    for result in results[1:]:
        assert result.base_alignment_score == first_result.base_alignment_score
        assert result.alignment_band == first_result.alignment_band
        assert result.variant_alignment == first_result.variant_alignment
        assert result.observer_only == first_result.observer_only


# Proves INV-P44-3: Variant isolation (variants do not influence base alignment)
def test_variant_isolation_from_base_alignment():
    """
    Invariant: INV-P44-3
    Proves that variants do not influence the base alignment score or band.
    The same coherence_v3_quality and fusion_confidence must produce
    the same base_alignment_score regardless of variant content.
    """
    coherence_v3_quality = 0.72
    scenario_fusion_confidence = 0.68

    # Test 1: No variants
    report_no_variants = run_p44_directly(
        coherence_v3_quality=coherence_v3_quality,
        scenario_fusion_confidence=scenario_fusion_confidence,
        what_if_variants=None,
    )

    # Test 2: Mild variants (small deltas)
    mild_variants = (
        MockScenarioVariant(
            variant_id="mild",
            perturbation_type="noise_injection",
            resulting_regime="stable_continuity",
            delta_entropy=0.01,
            delta_confidence=0.01,
        ),
    )
    report_mild = run_p44_directly(
        coherence_v3_quality=coherence_v3_quality,
        scenario_fusion_confidence=scenario_fusion_confidence,
        what_if_variants=mild_variants,
    )

    # Test 3: Extreme variants (large deltas)
    extreme_variants = (
        MockScenarioVariant(
            variant_id="extreme",
            perturbation_type="regime_flip",
            resulting_regime="divergent_instability",
            delta_entropy=0.50,
            delta_confidence=0.50,
        ),
    )
    report_extreme = run_p44_directly(
        coherence_v3_quality=coherence_v3_quality,
        scenario_fusion_confidence=scenario_fusion_confidence,
        what_if_variants=extreme_variants,
    )

    # Verify: Base alignment score is IDENTICAL regardless of variants
    assert report_no_variants.base_alignment_score == report_mild.base_alignment_score
    assert report_mild.base_alignment_score == report_extreme.base_alignment_score

    # Verify: Alignment band is IDENTICAL regardless of variants
    assert report_no_variants.alignment_band == report_mild.alignment_band
    assert report_mild.alignment_band == report_extreme.alignment_band


# Proves INV-P44-4: No authority influence (output never affects regime, discourse, policy)
def test_observer_only_no_authority_influence():
    """
    Invariant: INV-P44-4
    Proves that P44 output is observer-only and cannot influence
    authority phases (regime, discourse, policy).

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing authority state
    ctx = MockContext()
    ctx.coherence_v3_quality = 0.80
    ctx.p42_scenario_fusion_field = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        fusion_confidence=0.75,
        regime_entropy=0.20,
    )

    # Capture pre-existing state
    pre_coherence = ctx.coherence_v3_quality
    pre_fusion_field = ctx.p42_scenario_fusion_field

    # Run P44
    result = maybe_run_p44(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P44 did NOT modify any input state
    assert ctx.coherence_v3_quality == pre_coherence
    assert ctx.p42_scenario_fusion_field is pre_fusion_field

    # Verify: Output attached only to designated field
    assert ctx.p44_coherence_scenario_alignment is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        CoherenceScenarioAlignmentReport(
            base_alignment_score=0.70,
            variant_alignment={},
            alignment_band="aligned",
            observer_only=False,  # type: ignore
        )


# Proves INV-P44-5: Absence-safe (missing inputs -> no output)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P44-5
    Proves that P44 returns None (no output) when required inputs are missing,
    without fabricating data or raising errors.
    """
    # Test 1: Missing coherence_v3_quality
    result_no_coherence = run_p44_directly(
        coherence_v3_quality=None,
        scenario_fusion_confidence=0.75,
    )
    assert result_no_coherence is None

    # Test 2: Missing scenario_fusion_confidence
    result_no_fusion = run_p44_directly(
        coherence_v3_quality=0.80,
        scenario_fusion_confidence=None,
    )
    assert result_no_fusion is None

    # Test 3: Both missing
    result_both_missing = run_p44_directly(
        coherence_v3_quality=None,
        scenario_fusion_confidence=None,
    )
    assert result_both_missing is None

    # Test 4: Context-based integration with missing inputs
    ctx_missing_coherence = MockContext()
    ctx_missing_coherence.p42_scenario_fusion_field = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        fusion_confidence=0.75,
        regime_entropy=0.20,
    )
    # coherence_v3_quality is None by default
    result_ctx_no_coherence = maybe_run_p44(ctx_missing_coherence)
    assert result_ctx_no_coherence is None

    # Test 5: Context with missing fusion field
    ctx_missing_fusion = MockContext()
    ctx_missing_fusion.coherence_v3_quality = 0.80
    # p42_scenario_fusion_field is None by default
    result_ctx_no_fusion = maybe_run_p44(ctx_missing_fusion)
    assert result_ctx_no_fusion is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)
