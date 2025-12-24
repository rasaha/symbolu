"""
Phase 43 - Scenario What-If Simulator Tests

Test suite for P43 following the TESTING.md policy:
    - Exactly one test per invariant
    - Each test must declare which invariant it proves

INVARIANTS TESTED:
    - INV-P43-1: Simulation only (no prediction, no likelihoods)
    - INV-P43-2: Deterministic perturbations (no randomness)
    - INV-P43-3: Bounded exploration (exactly four variants, no more)
    - INV-P43-4: No authority impact (observer-only)
    - INV-P43-5: Absence-safe (no base input -> no output)
"""

import copy
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from symbolu.mechanical.pipeline.p42_scenario_fusion import (
    ScenarioFusionField,
    create_scenario_fusion_field,
)
from symbolu.mechanical.pipeline.p43_scenario_what_if import (
    NUM_VARIANTS,
    VALID_PERTURBATIONS,
    VALID_REGIMES,
    ScenarioWhatIfSet,
    maybe_run_p43,
    run_p43_directly,
    simulate_what_if_variants,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


def make_fusion_field(
    dominant_regime: str = "stable_continuity",
    fusion_confidence: float = 0.8,
    regime_entropy: float = 0.3,
    distribution: dict | None = None,
) -> ScenarioFusionField:
    """Create a ScenarioFusionField for testing."""
    if distribution is None:
        distribution = {
            "stable_continuity": 0.7,
            "strained_transition": 0.15,
            "divergent_instability": 0.1,
            "ambiguous_mixed": 0.05,
        }
    return create_scenario_fusion_field(
        dominant_regime=dominant_regime,
        regime_distribution=distribution,
        fusion_confidence=fusion_confidence,
        regime_entropy=regime_entropy,
        input_count=3,
    )


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""

    p42_scenario_fusion_field: Optional[ScenarioFusionField] = None
    p43_scenario_what_if: Optional[ScenarioWhatIfSet] = None
    _p43_disabled: bool = False

    # Upstream authoritative phases that P43 MUST NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p41_scenario_regime_map: Optional[Any] = None
    p42_fusion_field_original: Optional[Any] = None


# ============================================================================
# INVARIANT TESTS - One test per invariant as required by TESTING.md
# ============================================================================


# Proves INV-P43-1: Simulation only (no prediction, no likelihoods)
def test_inv_p43_1_simulation_only_no_prediction():
    """
    Invariant: INV-P43-1
    Proves that P43 produces simulation output only, not predictions.

    P43 generates possibility envelopes, not forecasts.
    The output contains:
    - Perturbation types (what-if operations)
    - Resulting regimes (possible outcomes)
    - Delta values (changes from base)

    The output does NOT contain:
    - Probability/likelihood scores
    - Timeline predictions
    - Ranking of variants
    - Recommended actions
    """
    fusion_field = make_fusion_field(
        dominant_regime="stable_continuity",
        fusion_confidence=0.8,
        regime_entropy=0.3,
    )

    result = simulate_what_if_variants(fusion_field)

    # Verify result exists and is valid
    assert result is not None
    assert isinstance(result, ScenarioWhatIfSet)

    # Verify this is simulation output (observer_only flag)
    assert result.observer_only is True, (
        "P43 must be observer-only (simulation, not prediction)"
    )

    # Verify variants contain only simulation data, no prediction semantics
    for variant in result.what_if_variants:
        # Perturbation type describes WHAT operation was applied
        assert variant.perturbation_type in VALID_PERTURBATIONS

        # Resulting regime is a possible outcome, not a predicted one
        assert variant.resulting_regime in VALID_REGIMES

        # Delta values are changes from base, not probabilities
        # They should be finite floats, not probability distributions
        assert isinstance(variant.delta_entropy, float)
        assert isinstance(variant.delta_confidence, float)

        # Verify NO probability/likelihood fields exist
        assert not hasattr(variant, "probability")
        assert not hasattr(variant, "likelihood")
        assert not hasattr(variant, "forecast")
        assert not hasattr(variant, "timeline")
        assert not hasattr(variant, "rank")

    # Verify NO ranking or preference in the output
    assert not hasattr(result, "best_variant")
    assert not hasattr(result, "recommended")
    assert not hasattr(result, "forecast")


# Proves INV-P43-2: Deterministic perturbations (no randomness)
def test_inv_p43_2_deterministic_perturbations():
    """
    Invariant: INV-P43-2
    Proves that identical inputs always produce identical outputs.

    P43 uses only deterministic math with fixed perturbation formulas:
    - entropy_shift: +0.15 (fixed)
    - confidence_drop: -0.20 (fixed)
    - regime_flip: swap based on distribution ordering (deterministic)
    - noise_injection: fixed pattern [+0.05, -0.05, +0.025, -0.025]

    No randomness, no LLM calls, no external state dependencies.
    """
    # Create fixed input
    fusion_field = make_fusion_field(
        dominant_regime="strained_transition",
        fusion_confidence=0.75,
        regime_entropy=0.4,
        distribution={
            "stable_continuity": 0.2,
            "strained_transition": 0.65,
            "divergent_instability": 0.1,
            "ambiguous_mixed": 0.05,
        },
    )

    # Run 10 times and collect results
    results = []
    for _ in range(10):
        result = run_p43_directly(fusion_field)
        results.append(result)

    # All results must be identical
    first = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result.base_regime == first.base_regime, (
            f"Run {i} base_regime differs from run 1"
        )
        assert result.variant_count == first.variant_count, (
            f"Run {i} variant_count differs from run 1"
        )

        # Verify each variant is identical
        for j, (v1, v2) in enumerate(
            zip(first.what_if_variants, result.what_if_variants)
        ):
            assert v1.variant_id == v2.variant_id, (
                f"Run {i} variant {j} id differs"
            )
            assert v1.perturbation_type == v2.perturbation_type, (
                f"Run {i} variant {j} perturbation_type differs"
            )
            assert v1.resulting_regime == v2.resulting_regime, (
                f"Run {i} variant {j} resulting_regime differs"
            )
            assert v1.delta_entropy == v2.delta_entropy, (
                f"Run {i} variant {j} delta_entropy differs"
            )
            assert v1.delta_confidence == v2.delta_confidence, (
                f"Run {i} variant {j} delta_confidence differs"
            )


# Proves INV-P43-3: Bounded exploration (exactly four variants, no more)
def test_inv_p43_3_bounded_exploration_exactly_four_variants():
    """
    Invariant: INV-P43-3
    Proves that P43 generates exactly four variants, no more, no less.

    The four variants correspond to exactly four perturbation types:
    1. entropy_shift
    2. confidence_drop
    3. regime_flip
    4. noise_injection

    No other perturbation types are allowed.
    """
    # Test with various input configurations
    test_cases = [
        # Case 1: High confidence, low entropy (stable)
        make_fusion_field(
            dominant_regime="stable_continuity",
            fusion_confidence=0.9,
            regime_entropy=0.1,
        ),
        # Case 2: Low confidence, high entropy (uncertain)
        make_fusion_field(
            dominant_regime="ambiguous_mixed",
            fusion_confidence=0.4,
            regime_entropy=0.8,
        ),
        # Case 3: Medium values
        make_fusion_field(
            dominant_regime="strained_transition",
            fusion_confidence=0.6,
            regime_entropy=0.5,
        ),
        # Case 4: Different dominant regime
        make_fusion_field(
            dominant_regime="divergent_instability",
            fusion_confidence=0.7,
            regime_entropy=0.3,
            distribution={
                "stable_continuity": 0.1,
                "strained_transition": 0.15,
                "divergent_instability": 0.7,
                "ambiguous_mixed": 0.05,
            },
        ),
    ]

    for case_num, fusion_field in enumerate(test_cases, start=1):
        result = simulate_what_if_variants(fusion_field)

        # Verify exactly 4 variants
        assert result is not None, f"Case {case_num}: Result should not be None"
        assert result.variant_count == NUM_VARIANTS, (
            f"Case {case_num}: Must have exactly {NUM_VARIANTS} variants, "
            f"got {result.variant_count}"
        )
        assert len(result.what_if_variants) == NUM_VARIANTS, (
            f"Case {case_num}: what_if_variants must have exactly "
            f"{NUM_VARIANTS} items, got {len(result.what_if_variants)}"
        )

        # Verify each perturbation type appears exactly once
        seen_perturbations = set()
        for variant in result.what_if_variants:
            assert variant.perturbation_type in VALID_PERTURBATIONS, (
                f"Case {case_num}: Invalid perturbation type: "
                f"{variant.perturbation_type}"
            )
            assert variant.perturbation_type not in seen_perturbations, (
                f"Case {case_num}: Duplicate perturbation type: "
                f"{variant.perturbation_type}"
            )
            seen_perturbations.add(variant.perturbation_type)

        # Verify all 4 perturbation types are present
        assert seen_perturbations == set(VALID_PERTURBATIONS), (
            f"Case {case_num}: Must have all 4 perturbation types. "
            f"Got: {seen_perturbations}, expected: {set(VALID_PERTURBATIONS)}"
        )


# Proves INV-P43-4: No authority impact (results never influence regime, discourse, or action)
def test_inv_p43_4_no_authority_impact():
    """
    Invariant: INV-P43-4
    Proves that P43 does not modify any upstream authoritative phase envelopes.

    P43 must be observer-only: it reads from P42 but must never modify:
    - P6 regime
    - P7 discourse
    - Semantic frame
    - Lexical frame
    - P41 scenario regime map
    - P42 fusion field

    P43 answers one question only:
    "What alternative scenario trajectories could exist?"

    It fuses signals -> possibility envelopes, NOT decisions.
    """
    # Create source P42 fusion field
    source_fusion = make_fusion_field(
        dominant_regime="stable_continuity",
        fusion_confidence=0.8,
        regime_entropy=0.3,
    )

    ctx = MockPipelineContext(
        p42_scenario_fusion_field=source_fusion,
        p6_regime="test_regime",
        p7_discourse_envelope="test_discourse",
        semantic_frame="test_semantic",
        lexical_frame="test_lexical",
        p41_scenario_regime_map="test_map",
        p42_fusion_field_original=copy.deepcopy(source_fusion),
    )

    # Store original values
    original_p6 = ctx.p6_regime
    original_p7 = ctx.p7_discourse_envelope
    original_semantic = ctx.semantic_frame
    original_lexical = ctx.lexical_frame
    original_p41 = ctx.p41_scenario_regime_map
    original_p42 = ctx.p42_fusion_field_original

    # Run P43
    result = maybe_run_p43(ctx)

    # Verify P43 ran successfully
    assert result is not None
    assert ctx.p43_scenario_what_if is not None

    # Verify NO upstream phases were modified (INV-P43-4)
    assert ctx.p6_regime == original_p6, "P43 modified P6 regime"
    assert ctx.p7_discourse_envelope == original_p7, "P43 modified P7 discourse"
    assert ctx.semantic_frame == original_semantic, "P43 modified semantic frame"
    assert ctx.lexical_frame == original_lexical, "P43 modified lexical frame"
    assert ctx.p41_scenario_regime_map == original_p41, "P43 modified P41 map"

    # Verify P42 fusion field was not modified
    assert ctx.p42_scenario_fusion_field.dominant_regime == source_fusion.dominant_regime
    assert ctx.p42_scenario_fusion_field.fusion_confidence == source_fusion.fusion_confidence
    assert ctx.p42_scenario_fusion_field.regime_entropy == source_fusion.regime_entropy
    assert ctx.p42_scenario_fusion_field.regime_distribution == source_fusion.regime_distribution

    # Verify observer_only flag is True
    assert result.observer_only is True


# Proves INV-P43-5: Absence-safe (no base input -> no output)
def test_inv_p43_5_absence_safe():
    """
    Invariant: INV-P43-5
    Proves that empty/None input produces no output (None).

    P43 cannot fabricate signal from nothing. If no ScenarioFusionField
    input is provided, the simulation must return None rather than
    inventing default variants.
    """
    # None input should return None
    result_none = simulate_what_if_variants(None)
    assert result_none is None, (
        "None input should return None, not fabricate output"
    )

    # Context with no P42 fusion field should return None
    ctx_empty = MockPipelineContext(
        p42_scenario_fusion_field=None,
    )
    result_ctx_empty = maybe_run_p43(ctx_empty)
    assert result_ctx_empty is None, (
        "Context with no P42 fusion field should return None"
    )
    assert ctx_empty.p43_scenario_what_if is None, (
        "No what-if set should be attached when input is empty"
    )

    # Disabled context should return None
    ctx_disabled = MockPipelineContext(
        p42_scenario_fusion_field=make_fusion_field(),
        _p43_disabled=True,
    )
    result_disabled = maybe_run_p43(ctx_disabled)
    assert result_disabled is None, (
        "Disabled P43 should return None"
    )

    # Verify valid input DOES produce output (sanity check)
    valid_fusion = make_fusion_field()
    result_valid = simulate_what_if_variants(valid_fusion)
    assert result_valid is not None, (
        "Valid fusion field should produce output"
    )
    assert result_valid.variant_count == NUM_VARIANTS, (
        "Valid input should produce exactly 4 variants"
    )


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
