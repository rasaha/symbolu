"""
TTOR v1.4 Unit Tests - Formulas Module

Comprehensive unit tests for all pure math functions in formulas.py.
Tests verify deterministic behavior, edge cases, and boundary conditions.
"""

import math
from typing import Dict

import pytest

from mechanical.pipeline.ttor.constants import (
    H_D_MAX,
    H_G_MAX,
    LOWER_ANCHORS,
    LOWER_ASPECTS,
    REFLECTIVE_DOMAIN_UPPER_BOOST,
    REFLECTIVE_DOMAINS,
    TASK_DOMAIN_LOWER_BOOST,
    TASK_DOMAINS,
    UPPER_ANCHORS,
    UPPER_ASPECTS,
)
from mechanical.pipeline.ttor.formulas import (
    anchor_boosts,
    aspect_base_scores,
    compute_conflict_score,
    compute_entropy_boosts,
    domain_modulation,
    entropy_mix,
    final_scores,
    normalize_to_unit_interval,
)


class TestAspectBaseScores:
    """Tests for aspect_base_scores function."""

    def test_empty_aspect_probs(self) -> None:
        """Empty input should return zeros."""
        lower, upper = aspect_base_scores({})
        assert lower == 0.0
        assert upper == 0.0

    def test_all_lower_aspects_full(self) -> None:
        """All lower aspects at 1.0 should give lower_base = 1.0."""
        probs = {aspect: 1.0 for aspect in LOWER_ASPECTS}
        lower, upper = aspect_base_scores(probs)
        assert lower == 1.0
        assert upper == 0.0

    def test_all_upper_aspects_full(self) -> None:
        """All upper aspects at 1.0 should give upper_base = 1.0."""
        probs = {aspect: 1.0 for aspect in UPPER_ASPECTS}
        lower, upper = aspect_base_scores(probs)
        assert lower == 0.0
        assert upper == 1.0

    def test_mixed_aspects(self) -> None:
        """Mixed aspects should compute averages correctly."""
        probs = {
            "Execution": 0.8,
            "Identity": 0.6,
            "Agency": 0.4,
            "Purpose": 0.2,
        }
        lower, upper = aspect_base_scores(probs)
        # Lower: (0.8 + 0.6) / 2 = 0.7
        assert abs(lower - 0.7) < 1e-10
        # Upper: (0.4 + 0.2) / 2 = 0.3
        assert abs(upper - 0.3) < 1e-10

    def test_partial_lower_aspects(self) -> None:
        """Partial lower aspects should average only present values."""
        probs = {"Execution": 0.6}
        lower, upper = aspect_base_scores(probs)
        assert abs(lower - 0.6) < 1e-10
        assert upper == 0.0

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        probs = {"Execution": 0.5, "Agency": 0.7}
        result1 = aspect_base_scores(probs)
        result2 = aspect_base_scores(probs)
        assert result1 == result2

    def test_all_aspects_equal(self) -> None:
        """All aspects at same value should give equal tier bases."""
        probs = {aspect: 0.5 for aspect in LOWER_ASPECTS + UPPER_ASPECTS}
        lower, upper = aspect_base_scores(probs)
        assert abs(lower - 0.5) < 1e-10
        assert abs(upper - 0.5) < 1e-10


class TestAnchorBoosts:
    """Tests for anchor_boosts function."""

    def test_empty_anchor_scores(self) -> None:
        """Empty input should return zeros."""
        lower, upper = anchor_boosts({})
        assert lower == 0.0
        assert upper == 0.0

    def test_all_lower_anchors_full(self) -> None:
        """All lower anchors at 1.0 should give lower_boost = 1.0."""
        scores = {anchor: 1.0 for anchor in LOWER_ANCHORS}
        lower, upper = anchor_boosts(scores)
        assert lower == 1.0
        assert upper == 0.0

    def test_all_upper_anchors_full(self) -> None:
        """All upper anchors at 1.0 should give upper_boost = 1.0."""
        scores = {anchor: 1.0 for anchor in UPPER_ANCHORS}
        lower, upper = anchor_boosts(scores)
        assert lower == 0.0
        assert upper == 1.0

    def test_mixed_anchors(self) -> None:
        """Mixed anchors should compute averages correctly."""
        scores = {
            "Needs": 0.9,
            "Exchange": 0.6,
            "Challenge": 0.3,
            "Belonging": 0.8,
            "Meaning": 0.4,
        }
        lower, upper = anchor_boosts(scores)
        # Lower: (0.9 + 0.6 + 0.3) / 3 = 0.6
        assert abs(lower - 0.6) < 1e-10
        # Upper: (0.8 + 0 + 0 + 0.4 + 0 + 0) / 6 = 0.2
        assert abs(upper - 0.2) < 1e-10

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        scores = {"Needs": 0.5, "Belonging": 0.7}
        result1 = anchor_boosts(scores)
        result2 = anchor_boosts(scores)
        assert result1 == result2


class TestEntropyMix:
    """Tests for entropy_mix function."""

    def test_zero_entropy(self) -> None:
        """Zero entropy should give minimal values."""
        norm, ratio = entropy_mix(0.0, 0.0)
        assert norm == 0.0
        assert ratio == pytest.approx(0.0, abs=1e-8)

    def test_max_dimensional_entropy(self) -> None:
        """Maximum H_D should contribute to normalized entropy."""
        norm, ratio = entropy_mix(H_D_MAX, 0.0)
        # 0.6 * 1.0 + 0.4 * 0.0 = 0.6
        assert abs(norm - 0.6) < 1e-10
        # ratio = 0 / (1 + epsilon) ≈ 0
        assert ratio == pytest.approx(0.0, abs=1e-8)

    def test_max_guna_entropy(self) -> None:
        """Maximum H_G should contribute to normalized entropy."""
        norm, ratio = entropy_mix(0.0, H_G_MAX)
        # 0.6 * 0.0 + 0.4 * 1.0 = 0.4
        assert abs(norm - 0.4) < 1e-10
        # ratio = 1 / (0 + 1 + epsilon) ≈ 1
        assert ratio == pytest.approx(1.0, abs=1e-6)

    def test_max_both_entropies(self) -> None:
        """Both at maximum should give max normalized entropy."""
        norm, ratio = entropy_mix(H_D_MAX, H_G_MAX)
        # 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        assert abs(norm - 1.0) < 1e-10
        # ratio = 1 / (1 + 1 + epsilon) = 0.5
        assert ratio == pytest.approx(0.5, abs=1e-6)

    def test_partial_entropies(self) -> None:
        """Partial entropy values should compute correctly."""
        # H_D at 50%, H_G at 50%
        norm, ratio = entropy_mix(H_D_MAX * 0.5, H_G_MAX * 0.5)
        # 0.6 * 0.5 + 0.4 * 0.5 = 0.5
        assert abs(norm - 0.5) < 1e-10
        # ratio = 0.5 / (0.5 + 0.5 + epsilon) = 0.5
        assert ratio == pytest.approx(0.5, abs=1e-6)

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        result1 = entropy_mix(1.0, 0.5)
        result2 = entropy_mix(1.0, 0.5)
        assert result1 == result2


class TestDomainModulation:
    """Tests for domain_modulation function."""

    def test_task_domains_boost_lower(self) -> None:
        """Task domains should boost lower tier."""
        for domain in TASK_DOMAINS:
            lower_mod, upper_mod = domain_modulation(domain)
            assert lower_mod == TASK_DOMAIN_LOWER_BOOST
            assert upper_mod == 0.0

    def test_reflective_domains_boost_upper(self) -> None:
        """Reflective domains should boost upper tier."""
        for domain in REFLECTIVE_DOMAINS:
            lower_mod, upper_mod = domain_modulation(domain)
            assert lower_mod == 0.0
            assert upper_mod == REFLECTIVE_DOMAIN_UPPER_BOOST

    def test_generic_domain_no_modulation(self) -> None:
        """Generic domain should have no modulation."""
        lower_mod, upper_mod = domain_modulation("generic")
        assert lower_mod == 0.0
        assert upper_mod == 0.0

    def test_unknown_domain_no_modulation(self) -> None:
        """Unknown domains should have no modulation."""
        lower_mod, upper_mod = domain_modulation("unknown_domain_xyz")
        assert lower_mod == 0.0
        assert upper_mod == 0.0

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        result1 = domain_modulation("code")
        result2 = domain_modulation("code")
        assert result1 == result2


class TestComputeEntropyBoosts:
    """Tests for compute_entropy_boosts function."""

    def test_zero_entropy_favors_lower(self) -> None:
        """Zero entropy should favor lower tier."""
        lower_boost, upper_boost = compute_entropy_boosts(0.0, 0.0)
        # lower_boost = (1 - 0) * 0.5 = 0.5
        assert abs(lower_boost - 0.5) < 1e-10
        # upper_boost = 0 * 0.5 + 0 * 0.3 = 0
        assert upper_boost == 0.0

    def test_high_entropy_favors_upper(self) -> None:
        """High entropy should favor upper tier."""
        lower_boost, upper_boost = compute_entropy_boosts(1.0, 0.5)
        # lower_boost = (1 - 1) * 0.5 = 0
        assert lower_boost == 0.0
        # upper_boost = 1 * 0.5 + 0.5 * 0.3 = 0.65
        assert abs(upper_boost - 0.65) < 1e-10

    def test_balanced_entropy(self) -> None:
        """Balanced entropy should give moderate boosts."""
        lower_boost, upper_boost = compute_entropy_boosts(0.5, 0.5)
        # lower_boost = (1 - 0.5) * 0.5 = 0.25
        assert abs(lower_boost - 0.25) < 1e-10
        # upper_boost = 0.5 * 0.5 + 0.5 * 0.3 = 0.4
        assert abs(upper_boost - 0.4) < 1e-10

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        result1 = compute_entropy_boosts(0.7, 0.3)
        result2 = compute_entropy_boosts(0.7, 0.3)
        assert result1 == result2


class TestFinalScores:
    """Tests for final_scores function."""

    def test_all_zeros(self) -> None:
        """All zero inputs should give zero outputs."""
        lower, upper = final_scores(0, 0, 0, 0, 0, 0, 0, 0)
        assert lower == 0.0
        assert upper == 0.0

    def test_only_aspect_bases(self) -> None:
        """Only aspect bases should contribute with ASPECT_WEIGHT."""
        lower, upper = final_scores(
            lower_base=1.0,
            upper_base=0.5,
            lower_anchor_boost=0,
            upper_anchor_boost=0,
            lower_entropy_boost=0,
            upper_entropy_boost=0,
            lower_domain_mod=0,
            upper_domain_mod=0,
        )
        # ASPECT_WEIGHT = 0.5
        assert abs(lower - 0.5) < 1e-10
        assert abs(upper - 0.25) < 1e-10

    def test_only_anchor_boosts(self) -> None:
        """Only anchor boosts should contribute with ANCHOR_WEIGHT."""
        lower, upper = final_scores(
            lower_base=0,
            upper_base=0,
            lower_anchor_boost=1.0,
            upper_anchor_boost=0.5,
            lower_entropy_boost=0,
            upper_entropy_boost=0,
            lower_domain_mod=0,
            upper_domain_mod=0,
        )
        # ANCHOR_WEIGHT = 0.3
        assert abs(lower - 0.3) < 1e-10
        assert abs(upper - 0.15) < 1e-10

    def test_domain_modulation_additive(self) -> None:
        """Domain modulation should be additive (not weighted)."""
        lower, upper = final_scores(
            lower_base=0,
            upper_base=0,
            lower_anchor_boost=0,
            upper_anchor_boost=0,
            lower_entropy_boost=0,
            upper_entropy_boost=0,
            lower_domain_mod=0.1,
            upper_domain_mod=0.2,
        )
        assert abs(lower - 0.1) < 1e-10
        assert abs(upper - 0.2) < 1e-10

    def test_combined_components(self) -> None:
        """All components should combine correctly."""
        lower, upper = final_scores(
            lower_base=0.8,
            upper_base=0.4,
            lower_anchor_boost=0.6,
            upper_anchor_boost=0.8,
            lower_entropy_boost=0.3,
            upper_entropy_boost=0.5,
            lower_domain_mod=0.1,
            upper_domain_mod=0.0,
        )
        # lower = 0.5*0.8 + 0.3*0.6 + 0.2*0.3 + 0.1 = 0.4 + 0.18 + 0.06 + 0.1 = 0.74
        expected_lower = 0.5 * 0.8 + 0.3 * 0.6 + 0.2 * 0.3 + 0.1
        assert abs(lower - expected_lower) < 1e-10
        # upper = 0.5*0.4 + 0.3*0.8 + 0.2*0.5 + 0.0 = 0.2 + 0.24 + 0.1 + 0 = 0.54
        expected_upper = 0.5 * 0.4 + 0.3 * 0.8 + 0.2 * 0.5 + 0.0
        assert abs(upper - expected_upper) < 1e-10

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        result1 = final_scores(0.5, 0.5, 0.3, 0.3, 0.2, 0.2, 0.1, 0.1)
        result2 = final_scores(0.5, 0.5, 0.3, 0.3, 0.2, 0.2, 0.1, 0.1)
        assert result1 == result2


class TestComputeConflictScore:
    """Tests for compute_conflict_score function."""

    def test_no_conflict_lower_only(self) -> None:
        """Single strong signal should give low conflict."""
        conflict = compute_conflict_score(1.0, 0.0)
        assert conflict == pytest.approx(0.0, abs=1e-8)

    def test_no_conflict_upper_only(self) -> None:
        """Single strong signal should give low conflict."""
        conflict = compute_conflict_score(0.0, 1.0)
        assert conflict == pytest.approx(0.0, abs=1e-8)

    def test_max_conflict_equal_signals(self) -> None:
        """Equal strong signals should give maximum conflict."""
        conflict = compute_conflict_score(1.0, 1.0)
        # 2 * min(1, 1) / (1 + 1 + epsilon) = 2 / 2 = 1
        assert conflict == pytest.approx(1.0, abs=1e-6)

    def test_partial_conflict(self) -> None:
        """Unequal signals should give partial conflict."""
        conflict = compute_conflict_score(0.8, 0.4)
        # 2 * 0.4 / (0.8 + 0.4 + epsilon) = 0.8 / 1.2 ≈ 0.667
        expected = 2 * 0.4 / (0.8 + 0.4)
        assert conflict == pytest.approx(expected, abs=1e-6)

    def test_zero_inputs(self) -> None:
        """Zero inputs should give minimal conflict."""
        conflict = compute_conflict_score(0.0, 0.0)
        assert conflict == pytest.approx(0.0, abs=1e-6)

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        result1 = compute_conflict_score(0.6, 0.4)
        result2 = compute_conflict_score(0.6, 0.4)
        assert result1 == result2


class TestNormalizeToUnitInterval:
    """Tests for normalize_to_unit_interval function."""

    def test_value_at_min(self) -> None:
        """Value at minimum should return 0."""
        assert normalize_to_unit_interval(0.0, 0.0, 1.0) == 0.0

    def test_value_at_max(self) -> None:
        """Value at maximum should return 1."""
        assert normalize_to_unit_interval(1.0, 0.0, 1.0) == 1.0

    def test_value_at_midpoint(self) -> None:
        """Value at midpoint should return 0.5."""
        assert normalize_to_unit_interval(0.5, 0.0, 1.0) == 0.5

    def test_arbitrary_range(self) -> None:
        """Arbitrary range should normalize correctly."""
        # Value 50 in range [0, 100] should give 0.5
        assert normalize_to_unit_interval(50.0, 0.0, 100.0) == 0.5
        # Value 75 in range [50, 100] should give 0.5
        assert normalize_to_unit_interval(75.0, 50.0, 100.0) == 0.5

    def test_value_below_min_clamps(self) -> None:
        """Value below minimum should clamp to 0."""
        assert normalize_to_unit_interval(-1.0, 0.0, 1.0) == 0.0

    def test_value_above_max_clamps(self) -> None:
        """Value above maximum should clamp to 1."""
        assert normalize_to_unit_interval(2.0, 0.0, 1.0) == 1.0

    def test_invalid_range_returns_zero(self) -> None:
        """Invalid range (max <= min) should return 0."""
        assert normalize_to_unit_interval(0.5, 1.0, 0.0) == 0.0
        assert normalize_to_unit_interval(0.5, 1.0, 1.0) == 0.0


class TestFormulaDeterminism:
    """Meta-tests verifying all formulas are deterministic."""

    def test_all_formulas_are_deterministic(self) -> None:
        """Run all formulas multiple times and verify consistent output."""
        # Test inputs
        aspect_probs: Dict[str, float] = {
            "Execution": 0.7,
            "Identity": 0.5,
            "Agency": 0.6,
            "Purpose": 0.4,
        }
        anchor_scores: Dict[str, float] = {
            "Needs": 0.8,
            "Exchange": 0.3,
            "Belonging": 0.5,
            "Meaning": 0.7,
        }

        # Run each formula 10 times
        for _ in range(10):
            # aspect_base_scores
            result = aspect_base_scores(aspect_probs)
            assert result == aspect_base_scores(aspect_probs)

            # anchor_boosts
            result = anchor_boosts(anchor_scores)
            assert result == anchor_boosts(anchor_scores)

            # entropy_mix
            result = entropy_mix(1.5, 0.7)
            assert result == entropy_mix(1.5, 0.7)

            # domain_modulation
            result = domain_modulation("code")
            assert result == domain_modulation("code")

            # compute_entropy_boosts
            result = compute_entropy_boosts(0.6, 0.4)
            assert result == compute_entropy_boosts(0.6, 0.4)

            # final_scores
            result = final_scores(0.5, 0.5, 0.3, 0.3, 0.2, 0.2, 0.1, 0.1)
            assert result == final_scores(0.5, 0.5, 0.3, 0.3, 0.2, 0.2, 0.1, 0.1)

            # compute_conflict_score
            result = compute_conflict_score(0.6, 0.4)
            assert result == compute_conflict_score(0.6, 0.4)
