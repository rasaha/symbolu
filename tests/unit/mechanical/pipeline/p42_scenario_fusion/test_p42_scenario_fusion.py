"""
Phase 42 - Scenario Fusion Engine Tests

Test suite for P42 following the TESTING.md policy:
    - Exactly one test per invariant
    - Each test must declare which invariant it proves

INVARIANTS TESTED:
    - INV-P42-1: Observer-only (no downstream authority impact)
    - INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
    - INV-P42-3: No regime creation (cannot invent new regimes)
    - INV-P42-4: Monotonic ambiguity (more disagreement -> higher entropy)
    - INV-P42-5: Absence-safe (empty input produces no output)
"""

import copy
from dataclasses import dataclass
from typing import Any, List, Optional

import pytest

from symbolu.mechanical.pipeline.p41_scenario_regime_mapper import (
    ScenarioRegimeMap,
    create_scenario_regime_map,
)
from symbolu.mechanical.pipeline.p42_scenario_fusion import (
    P42_VERSION,
    VALID_REGIMES,
    DOMINANT_THRESHOLD,
    ScenarioFusionField,
    fuse_scenario_regimes,
    build_regime_distribution,
    compute_regime_entropy,
    maybe_run_p42,
    run_p42_directly,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


def make_scenario_map(
    regime: str = "stable_continuity",
    confidence: float = 0.8,
) -> ScenarioRegimeMap:
    """Create a ScenarioRegimeMap for testing."""
    return create_scenario_regime_map(
        scenario_regime=regime,
        confidence=confidence,
        supporting_signals=("test_signal",),
        coherence_v3_quality=0.75,
        alignment_score=0.75,
        drift_fusion_index=0.25,
    )


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""

    p41_scenario_regime_map: Optional[ScenarioRegimeMap] = None
    p41_scenario_regime_maps: Optional[List[ScenarioRegimeMap]] = None
    p42_scenario_fusion_field: Optional[ScenarioFusionField] = None
    _p42_disabled: bool = False

    # Upstream authoritative phases that P42 MUST NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p41_scenario_regime_map_original: Optional[Any] = None


# ============================================================================
# INVARIANT TESTS - One test per invariant as required by TESTING.md
# ============================================================================


# Proves INV-P42-1: Observer-only (no downstream authority impact)
def test_inv_p42_1_observer_only_no_upstream_modification():
    """
    Invariant: INV-P42-1
    Proves that P42 does not modify any upstream authoritative phase envelopes.

    P42 must be observer-only: it reads from P41 scenario maps but must
    never modify P6 regime, P7 discourse, semantic frame, lexical frame,
    or the source P41 inputs themselves.

    P42 answers one question only:
    "Across time, layers, and scenario inputs — what scenario field is emerging?"

    It fuses signals -> unified field, NOT decisions.
    """
    # Create source P41 maps
    source_maps = [
        make_scenario_map("stable_continuity", 0.8),
        make_scenario_map("stable_continuity", 0.9),
        make_scenario_map("strained_transition", 0.7),
    ]

    ctx = MockPipelineContext(
        p41_scenario_regime_map=source_maps[0],
        p41_scenario_regime_maps=source_maps,
        p6_regime="test_regime",
        p7_discourse_envelope="test_discourse",
        semantic_frame="test_semantic",
        lexical_frame="test_lexical",
        p41_scenario_regime_map_original=copy.deepcopy(source_maps[0]),
    )

    # Store original values
    original_p6 = ctx.p6_regime
    original_p7 = ctx.p7_discourse_envelope
    original_semantic = ctx.semantic_frame
    original_lexical = ctx.lexical_frame
    original_p41_map = copy.deepcopy(ctx.p41_scenario_regime_map)
    original_p41_maps = [copy.deepcopy(m) for m in ctx.p41_scenario_regime_maps]

    # Run P42
    result = maybe_run_p42(ctx)

    # Verify P42 ran successfully
    assert result is not None
    assert ctx.p42_scenario_fusion_field is not None

    # Verify NO upstream phases were modified (INV-P42-1)
    assert ctx.p6_regime == original_p6, "P42 modified P6 regime"
    assert ctx.p7_discourse_envelope == original_p7, "P42 modified P7 discourse"
    assert ctx.semantic_frame == original_semantic, "P42 modified semantic frame"
    assert ctx.lexical_frame == original_lexical, "P42 modified lexical frame"

    # Verify P41 source inputs were not modified
    assert ctx.p41_scenario_regime_map.scenario_regime == original_p41_map.scenario_regime
    assert ctx.p41_scenario_regime_map.confidence == original_p41_map.confidence
    for i, orig_map in enumerate(original_p41_maps):
        assert ctx.p41_scenario_regime_maps[i].scenario_regime == orig_map.scenario_regime
        assert ctx.p41_scenario_regime_maps[i].confidence == orig_map.confidence

    # Verify observer_only flag is True
    assert result.observer_only is True


# Proves INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
def test_inv_p42_2_deterministic_aggregation():
    """
    Invariant: INV-P42-2
    Proves that identical inputs always produce identical outputs.

    P42 uses only deterministic math with fixed formulas:
    - Distribution counting (no weighted sampling)
    - Fixed threshold for dominant selection (0.60)
    - Deterministic Shannon entropy calculation
    - No LLM calls, no randomness, no external state dependencies
    """
    # Create fixed input maps
    input_maps = [
        make_scenario_map("stable_continuity", 0.8),
        make_scenario_map("stable_continuity", 0.75),
        make_scenario_map("strained_transition", 0.7),
        make_scenario_map("ambiguous_mixed", 0.5),
    ]

    # Run 10 times and collect results
    results = []
    for _ in range(10):
        result = run_p42_directly(input_maps)
        results.append(result)

    # All results must be identical
    first = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result.dominant_regime == first.dominant_regime, (
            f"Run {i} dominant_regime differs from run 1"
        )
        assert result.fusion_confidence == first.fusion_confidence, (
            f"Run {i} fusion_confidence differs from run 1"
        )
        assert result.regime_entropy == first.regime_entropy, (
            f"Run {i} regime_entropy differs from run 1"
        )
        assert result.regime_distribution == first.regime_distribution, (
            f"Run {i} regime_distribution differs from run 1"
        )
        assert result.input_count == first.input_count, (
            f"Run {i} input_count differs from run 1"
        )


# Proves INV-P42-3: No regime creation (cannot invent new regimes)
def test_inv_p42_3_no_regime_creation():
    """
    Invariant: INV-P42-3
    Proves that P42 cannot invent new regimes.

    The output dominant_regime must be one of exactly 4 valid regimes:
    - stable_continuity
    - strained_transition
    - divergent_instability
    - ambiguous_mixed

    P42 only aggregates existing regime observations; it cannot
    create new regime labels or classifications.
    """
    valid_regimes = set(VALID_REGIMES)

    # Test various combinations of input regimes
    test_cases = [
        # All same regime -> that regime dominates
        [make_scenario_map("stable_continuity", 0.8) for _ in range(5)],
        [make_scenario_map("strained_transition", 0.7) for _ in range(5)],
        [make_scenario_map("divergent_instability", 0.6) for _ in range(5)],
        [make_scenario_map("ambiguous_mixed", 0.5) for _ in range(5)],
        # Mixed regimes -> should still output valid regime
        [
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("strained_transition", 0.7),
            make_scenario_map("divergent_instability", 0.6),
            make_scenario_map("ambiguous_mixed", 0.5),
        ],
        # Uneven distribution
        [
            make_scenario_map("stable_continuity", 0.9),
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("divergent_instability", 0.5),
        ],
    ]

    for maps in test_cases:
        result = fuse_scenario_regimes(maps)
        assert result is not None

        # Verify dominant_regime is one of exactly 4 valid labels
        assert result.dominant_regime in valid_regimes, (
            f"Invalid dominant_regime: {result.dominant_regime}"
        )

        # Verify all keys in regime_distribution are valid
        for regime_key in result.regime_distribution:
            assert regime_key in valid_regimes, (
                f"Invalid regime in distribution: {regime_key}"
            )

        # Verify distribution sums to 1.0
        dist_sum = sum(result.regime_distribution.values())
        assert abs(dist_sum - 1.0) < 0.001, (
            f"Distribution does not sum to 1.0: {dist_sum}"
        )


# Proves INV-P42-4: Monotonic ambiguity (more disagreement -> higher entropy)
def test_inv_p42_4_monotonic_ambiguity():
    """
    Invariant: INV-P42-4
    Proves that more disagreement leads to higher entropy, never lower.

    Shannon entropy is maximum when the distribution is uniform (maximum
    disagreement) and minimum when all inputs agree (one regime = 100%).

    This test verifies:
    1. Perfect agreement (all same regime) -> low entropy
    2. Uniform distribution (all different) -> high entropy
    3. Increasing disagreement cannot decrease entropy
    """
    # Case 1: Perfect agreement -> minimum entropy
    all_same = [make_scenario_map("stable_continuity", 0.8) for _ in range(4)]
    result_same = fuse_scenario_regimes(all_same)

    # Case 2: Uniform distribution -> maximum entropy
    uniform = [
        make_scenario_map("stable_continuity", 0.8),
        make_scenario_map("strained_transition", 0.7),
        make_scenario_map("divergent_instability", 0.6),
        make_scenario_map("ambiguous_mixed", 0.5),
    ]
    result_uniform = fuse_scenario_regimes(uniform)

    # Verify perfect agreement has lower entropy than uniform distribution
    assert result_same.regime_entropy < result_uniform.regime_entropy, (
        f"Perfect agreement ({result_same.regime_entropy}) should have lower entropy "
        f"than uniform distribution ({result_uniform.regime_entropy})"
    )

    # Verify perfect agreement has entropy close to 0
    assert result_same.regime_entropy < 0.01, (
        f"Perfect agreement should have near-zero entropy, got {result_same.regime_entropy}"
    )

    # Verify uniform distribution has entropy close to 1.0
    assert result_uniform.regime_entropy > 0.95, (
        f"Uniform distribution should have near-maximum entropy, got {result_uniform.regime_entropy}"
    )

    # Case 3: Progressively increasing disagreement
    # Start with 4 same, replace one at a time with different regimes
    progression = [
        # 4/4 same
        [make_scenario_map("stable_continuity", 0.8) for _ in range(4)],
        # 3/4 same
        [
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("strained_transition", 0.7),
        ],
        # 2/4 same
        [
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("strained_transition", 0.7),
            make_scenario_map("divergent_instability", 0.6),
        ],
        # All different
        [
            make_scenario_map("stable_continuity", 0.8),
            make_scenario_map("strained_transition", 0.7),
            make_scenario_map("divergent_instability", 0.6),
            make_scenario_map("ambiguous_mixed", 0.5),
        ],
    ]

    prev_entropy = -1.0
    for maps in progression:
        result = fuse_scenario_regimes(maps)
        assert result.regime_entropy >= prev_entropy, (
            f"INV-P42-4 violated: entropy decreased from {prev_entropy} to "
            f"{result.regime_entropy} as disagreement increased"
        )
        prev_entropy = result.regime_entropy


# Proves INV-P42-5: Absence-safe (empty input produces no output)
def test_inv_p42_5_absence_safe():
    """
    Invariant: INV-P42-5
    Proves that empty input produces no output (None).

    P42 cannot fabricate signal from nothing. If no ScenarioRegimeMap
    inputs are provided, the fusion must return None rather than
    inventing a default scenario field.
    """
    # Empty list should return None
    result_empty_list = fuse_scenario_regimes([])
    assert result_empty_list is None, (
        "Empty list should return None, not fabricate output"
    )

    # Empty tuple should return None
    result_empty_tuple = fuse_scenario_regimes(())
    assert result_empty_tuple is None, (
        "Empty tuple should return None, not fabricate output"
    )

    # Context with no P41 maps should return None
    ctx_empty = MockPipelineContext(
        p41_scenario_regime_map=None,
        p41_scenario_regime_maps=None,
    )
    result_ctx_empty = maybe_run_p42(ctx_empty)
    assert result_ctx_empty is None, (
        "Context with no P41 maps should return None"
    )
    assert ctx_empty.p42_scenario_fusion_field is None, (
        "No fusion field should be attached when input is empty"
    )

    # Context with empty list should return None
    ctx_empty_list = MockPipelineContext(
        p41_scenario_regime_map=None,
        p41_scenario_regime_maps=[],
    )
    result_ctx_empty_list = maybe_run_p42(ctx_empty_list)
    assert result_ctx_empty_list is None, (
        "Context with empty P41 maps list should return None"
    )

    # Verify non-empty input DOES produce output (sanity check)
    non_empty = [make_scenario_map("stable_continuity", 0.8)]
    result_non_empty = fuse_scenario_regimes(non_empty)
    assert result_non_empty is not None, (
        "Non-empty input should produce output"
    )


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
