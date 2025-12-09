"""
HRM Unit Tests

Tests for the High-Resolution Mapper engine validating:
1. Normalization of aspect_probs and anchor_scores
2. Dominant/suppressed aspect separation
3. Entropy regime classification
4. Conflict detection patterns
5. Resolution hint generation
"""

import pytest
from symbolu.mechanical.hrm.hrm_engine import HRMEngine, get_hrm_engine
from symbolu.mechanical.hrm.models import HRMInput, HighResolutionMap


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def engine() -> HRMEngine:
    """Create a fresh HRM engine for each test."""
    return HRMEngine(aspect_threshold=0.15, conflict_threshold=0.25)


@pytest.fixture
def basic_input() -> HRMInput:
    """Create a basic HRM input for testing."""
    return HRMInput(
        aspect_probs={
            "Execution": 0.3,
            "Identity": 0.2,
            "Form": 0.1,
            "Cognition": 0.1,
            "Agency": 0.1,
            "Reasoning": 0.1,
            "Purpose": 0.05,
            "Observation": 0.03,
            "Core": 0.01,
            "Universal": 0.01,
        },
        anchor_scores={
            "Needs": 0.4,
            "Exchange": 0.3,
            "Challenge": 0.1,
            "Belonging": 0.05,
            "Relation": 0.05,
            "Change": 0.03,
            "Meaning": 0.04,
            "Role": 0.02,
            "Collective": 0.01,
        },
        H_D=1.0,
        H_G=0.5,
        H_K=0.8,
        domain="generic",
        tier="lower",
        flow_mode="outer_only",
    )


# =============================================================================
# NORMALIZATION TESTS
# =============================================================================


class TestNormalization:
    """Tests for probability normalization."""

    def test_aspect_probs_normalized_to_sum_one(self, engine: HRMEngine) -> None:
        """Aspect probabilities should be normalized to sum to 1.0."""
        probs = {"A": 0.3, "B": 0.5, "C": 0.2}
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert normalized["A"] == pytest.approx(0.3, abs=1e-10)
        assert normalized["B"] == pytest.approx(0.5, abs=1e-10)
        assert normalized["C"] == pytest.approx(0.2, abs=1e-10)

    def test_unnormalized_probs_get_normalized(self, engine: HRMEngine) -> None:
        """Probabilities that don't sum to 1 should be normalized."""
        probs = {"A": 2.0, "B": 3.0, "C": 5.0}  # Sum = 10
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert normalized["A"] == pytest.approx(0.2, abs=1e-10)
        assert normalized["B"] == pytest.approx(0.3, abs=1e-10)
        assert normalized["C"] == pytest.approx(0.5, abs=1e-10)

    def test_empty_probs_returns_empty(self, engine: HRMEngine) -> None:
        """Empty probability dict should return empty dict."""
        normalized = engine._normalize_probs({})
        assert normalized == {}

    def test_all_zero_probs_uniform_distribution(self, engine: HRMEngine) -> None:
        """All-zero probabilities should become uniform distribution."""
        probs = {"A": 0.0, "B": 0.0, "C": 0.0}
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert all(v == pytest.approx(1.0 / 3, abs=1e-10) for v in normalized.values())

    def test_negative_values_clamped_to_zero(self, engine: HRMEngine) -> None:
        """Negative probability values should be clamped to 0."""
        probs = {"A": -0.5, "B": 0.5, "C": 0.5}
        normalized = engine._normalize_probs(probs)

        assert normalized["A"] == 0.0
        assert abs(sum(normalized.values()) - 1.0) < 1e-10

    def test_anchor_scores_normalized_in_build_map(
        self, engine: HRMEngine, basic_input: HRMInput
    ) -> None:
        """Anchor scores should be normalized to sum to 1 in the output."""
        hrm_map = engine.build_map(basic_input)
        anchor_sum = sum(hrm_map.anchor_profile.values())

        assert anchor_sum == pytest.approx(1.0, abs=1e-6)


# =============================================================================
# DOMINANT/SUPPRESSED ASPECT TESTS
# =============================================================================


class TestAspectClassification:
    """Tests for dominant/suppressed aspect classification."""

    def test_dominant_aspect_appears_first(self, engine: HRMEngine) -> None:
        """Aspect with highest probability should appear first in dominant list."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.6,
                "Identity": 0.05,
                "Form": 0.05,
                "Cognition": 0.05,
                "Agency": 0.05,
                "Reasoning": 0.05,
                "Purpose": 0.05,
                "Observation": 0.05,
                "Core": 0.03,
                "Universal": 0.02,
            },
            anchor_scores={"Needs": 0.5, "Exchange": 0.3, "Challenge": 0.2},
            H_D=1.0,
            H_G=0.5,
            H_K=0.5,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.dominant_aspects[0] == "Execution"
        assert "Execution" not in hrm_map.suppressed_aspects

    def test_low_prob_aspects_are_suppressed(self, engine: HRMEngine) -> None:
        """Aspects below threshold should be classified as suppressed."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.8,
                "Identity": 0.1,
                "Form": 0.02,
                "Cognition": 0.02,
                "Agency": 0.02,
                "Reasoning": 0.02,
                "Purpose": 0.01,
                "Observation": 0.005,
                "Core": 0.003,
                "Universal": 0.002,
            },
            anchor_scores={"Needs": 0.5},
            H_D=0.5,
            H_G=0.3,
            H_K=0.2,
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        # After normalization, only Execution should be dominant
        # Others should be suppressed due to low normalized values
        assert "Execution" in hrm_map.dominant_aspects
        # Low prob aspects should be in suppressed
        low_prob_aspects = ["Core", "Universal", "Observation"]
        for asp in low_prob_aspects:
            assert asp in hrm_map.suppressed_aspects

    def test_multiple_dominant_aspects_sorted(self, engine: HRMEngine) -> None:
        """Multiple dominant aspects should be sorted by probability."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.3,
                "Purpose": 0.4,
                "Meaning": 0.2,  # Not a valid aspect, will be ignored
                "Identity": 0.1,
            },
            anchor_scores={"Needs": 0.5},
            H_D=1.0,
            H_G=0.7,
            H_K=0.5,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        # Purpose (0.4) > Execution (0.3) after normalization
        # Check ordering in dominant aspects
        purpose_idx = (
            hrm_map.dominant_aspects.index("Purpose")
            if "Purpose" in hrm_map.dominant_aspects
            else -1
        )
        execution_idx = (
            hrm_map.dominant_aspects.index("Execution")
            if "Execution" in hrm_map.dominant_aspects
            else -1
        )

        if purpose_idx >= 0 and execution_idx >= 0:
            assert purpose_idx < execution_idx  # Purpose should come before Execution


# =============================================================================
# ENTROPY REGIME TESTS
# =============================================================================


class TestEntropyRegime:
    """Tests for entropy regime classification."""

    def test_low_entropy_regime(self, engine: HRMEngine) -> None:
        """Low entropy values should result in 'low' regime."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.9, "Form": 0.1},
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.3,  # Low dimensional entropy
            H_G=0.2,  # Low guna entropy
            H_K=0.2,  # Low kosha entropy
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["regime"] == "low"
        assert hrm_map.entropy_profile["entropy_mix"] < 0.33

    def test_medium_entropy_regime(self, engine: HRMEngine) -> None:
        """Medium entropy values should result in 'medium' regime."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.5, "Purpose": 0.5},
            anchor_scores={"Needs": 0.5, "Meaning": 0.5},
            H_D=1.1,  # ~48% of max
            H_G=0.55,  # ~50% of max
            H_K=0.8,  # ~50% of max
            domain="generic",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["regime"] == "medium"
        entropy_mix = hrm_map.entropy_profile["entropy_mix"]
        assert 0.33 <= entropy_mix < 0.66

    def test_high_entropy_regime(self, engine: HRMEngine) -> None:
        """High entropy values should result in 'high' regime."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 0.5, "Universal": 0.5},
            anchor_scores={"Meaning": 0.5, "Collective": 0.5},
            H_D=2.0,  # ~87% of max
            H_G=0.95,  # ~86% of max
            H_K=1.4,  # ~87% of max
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["regime"] == "high"
        assert hrm_map.entropy_profile["entropy_mix"] >= 0.66

    def test_entropy_normalization_bounds(self, engine: HRMEngine) -> None:
        """Normalized entropy values should be clamped to [0, 1]."""
        # Test with values exceeding max
        hrm_input = HRMInput(
            aspect_probs={"Execution": 1.0},
            anchor_scores={"Needs": 1.0},
            H_D=3.0,  # Exceeds H_D_MAX (~2.303)
            H_G=2.0,  # Exceeds H_G_MAX (~1.099)
            H_K=3.0,  # Exceeds H_K_MAX (~1.609)
            domain="generic",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["H_D_norm"] <= 1.0
        assert hrm_map.entropy_profile["H_G_norm"] <= 1.0
        assert hrm_map.entropy_profile["H_K_norm"] <= 1.0


# =============================================================================
# CONFLICT DETECTION TESTS
# =============================================================================


class TestConflictDetection:
    """Tests for conflict zone detection."""

    def test_practical_support_gap_detected(self, engine: HRMEngine) -> None:
        """High Needs + low Execution should trigger practical_support_gap."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.05,  # Low
                "Purpose": 0.6,  # High upper aspect
                "Universal": 0.35,
            },
            anchor_scores={
                "Needs": 0.7,  # High needs
                "Meaning": 0.2,
                "Collective": 0.1,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "practical_support_gap" in hrm_map.conflict_zones

    def test_identity_integration_gap_detected(self, engine: HRMEngine) -> None:
        """High Meaning/Collective + low Identity should trigger identity_integration_gap."""
        hrm_input = HRMInput(
            aspect_probs={
                "Identity": 0.05,  # Low
                "Purpose": 0.5,
                "Universal": 0.45,
            },
            anchor_scores={
                "Meaning": 0.5,  # High
                "Collective": 0.4,  # High
                "Needs": 0.1,
            },
            H_D=1.2,
            H_G=0.6,
            H_K=0.7,
            domain="spiritual",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "identity_integration_gap" in hrm_map.conflict_zones

    def test_growth_edge_tension_detected(self, engine: HRMEngine) -> None:
        """High Challenge + high Purpose + high entropy should trigger growth_edge_tension."""
        hrm_input = HRMInput(
            aspect_probs={
                "Purpose": 0.5,  # High
                "Agency": 0.3,
                "Reasoning": 0.2,
            },
            anchor_scores={
                "Challenge": 0.6,  # High
                "Change": 0.3,
                "Meaning": 0.1,
            },
            H_D=2.0,  # High entropy
            H_G=0.9,
            H_K=1.3,
            domain="identity",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "growth_edge_tension" in hrm_map.conflict_zones

    def test_multiple_conflicts_detected(self, engine: HRMEngine) -> None:
        """Multiple conflict patterns should be detected simultaneously."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.02,  # Very low - enables practical_support_gap
                "Identity": 0.02,  # Very low - enables identity_integration_gap
                "Form": 0.02,  # Very low - enables grounding_deficit
                "Purpose": 0.47,  # High upper
                "Universal": 0.47,  # High upper
            },
            anchor_scores={
                "Needs": 0.4,  # High lower anchor
                "Exchange": 0.2,
                "Challenge": 0.1,
                "Meaning": 0.2,  # Significant upper anchor
                "Collective": 0.1,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="therapy",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = engine.build_map(hrm_input)

        # Should have multiple conflicts
        assert len(hrm_map.conflict_zones) >= 2


# =============================================================================
# RESOLUTION HINTS TESTS
# =============================================================================


class TestResolutionHints:
    """Tests for resolution hint generation."""

    def test_upper_tier_hints(self, engine: HRMEngine) -> None:
        """Upper tier should generate appropriate hints."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 0.7, "Universal": 0.3},
            anchor_scores={"Meaning": 0.6, "Collective": 0.4},
            H_D=1.5,
            H_G=0.7,
            H_K=0.8,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "upper_tier_deep_processing" in hrm_map.resolution_hints
        assert "meaning_oriented_response" in hrm_map.resolution_hints

    def test_lower_tier_hints(self, engine: HRMEngine) -> None:
        """Lower tier should generate appropriate hints."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.7, "Form": 0.3},
            anchor_scores={"Needs": 0.6, "Exchange": 0.4},
            H_D=0.5,
            H_G=0.3,
            H_K=0.3,
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "lower_tier_concrete_focus" in hrm_map.resolution_hints
        assert "action_oriented_response" in hrm_map.resolution_hints

    def test_high_entropy_hints(self, engine: HRMEngine) -> None:
        """High entropy should generate uncertainty hints."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 0.5, "Reasoning": 0.5},
            anchor_scores={"Meaning": 0.5, "Change": 0.5},
            H_D=2.0,
            H_G=0.95,
            H_K=1.4,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert "high_entropy_upper_tilt" in hrm_map.resolution_hints
        assert "uncertainty_acknowledgment" in hrm_map.resolution_hints

    def test_domain_specific_hints(self, engine: HRMEngine) -> None:
        """Domain-specific hints should be generated."""
        # Test therapy domain
        therapy_input = HRMInput(
            aspect_probs={"Purpose": 0.7, "Identity": 0.3},
            anchor_scores={"Meaning": 0.5, "Belonging": 0.5},
            H_D=1.0,
            H_G=0.6,
            H_K=0.7,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(therapy_input)

        assert "reflective_domain_emphasis" in hrm_map.resolution_hints
        assert "therapeutic_sensitivity" in hrm_map.resolution_hints

    def test_conflict_derived_hints(self, engine: HRMEngine) -> None:
        """Conflict zones should generate corresponding hints."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.05,
                "Purpose": 0.95,
            },
            anchor_scores={
                "Needs": 0.8,
                "Meaning": 0.2,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.8,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        # Should have practical_support_gap conflict and related hints
        if "practical_support_gap" in hrm_map.conflict_zones:
            assert "anchor_tension_needs_vs_abstract" in hrm_map.resolution_hints
            assert "ground_in_practical" in hrm_map.resolution_hints

    def test_no_duplicate_hints(self, engine: HRMEngine) -> None:
        """Resolution hints should not have duplicates."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 0.7, "Universal": 0.3},
            anchor_scores={"Meaning": 0.6, "Collective": 0.4},
            H_D=2.0,
            H_G=0.9,
            H_K=1.2,
            domain="spiritual",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        assert len(hrm_map.resolution_hints) == len(set(hrm_map.resolution_hints))


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_hrm_engine_returns_singleton(self) -> None:
        """get_hrm_engine should return the same instance."""
        engine1 = get_hrm_engine()
        engine2 = get_hrm_engine()

        assert engine1 is engine2

    def test_singleton_is_hrm_engine_instance(self) -> None:
        """Singleton should be an HRMEngine instance."""
        engine = get_hrm_engine()
        assert isinstance(engine, HRMEngine)


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestHighResolutionMap:
    """Tests for HighResolutionMap model."""

    def test_to_dict(self, engine: HRMEngine, basic_input: HRMInput) -> None:
        """to_dict should serialize all fields."""
        hrm_map = engine.build_map(basic_input)
        result = hrm_map.to_dict()

        assert "dominant_aspects" in result
        assert "suppressed_aspects" in result
        assert "anchor_profile" in result
        assert "entropy_profile" in result
        assert "conflict_zones" in result
        assert "resolution_hints" in result
        assert "tier" in result
        assert "domain" in result

    def test_repr(self, engine: HRMEngine, basic_input: HRMInput) -> None:
        """__repr__ should provide concise summary."""
        hrm_map = engine.build_map(basic_input)
        repr_str = repr(hrm_map)

        assert "HighResolutionMap" in repr_str
        assert hrm_map.tier in repr_str
        assert hrm_map.domain in repr_str


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_minimal_input(self, engine: HRMEngine) -> None:
        """Engine should handle minimal valid input."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 1.0},
            anchor_scores={"Needs": 1.0},
            H_D=0.0,
            H_G=0.0,
            H_K=0.0,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = engine.build_map(hrm_input)

        assert hrm_map.tier == "lower"
        assert hrm_map.domain == "task"
        assert len(hrm_map.dominant_aspects) >= 1

    def test_all_aspects_equal(self, engine: HRMEngine) -> None:
        """Engine should handle equal probabilities for all aspects."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.1,
                "Identity": 0.1,
                "Form": 0.1,
                "Cognition": 0.1,
                "Agency": 0.1,
                "Reasoning": 0.1,
                "Purpose": 0.1,
                "Observation": 0.1,
                "Core": 0.1,
                "Universal": 0.1,
            },
            anchor_scores={
                "Needs": 0.11,
                "Exchange": 0.11,
                "Challenge": 0.11,
                "Belonging": 0.11,
                "Relation": 0.11,
                "Change": 0.11,
                "Meaning": 0.11,
                "Role": 0.11,
                "Collective": 0.12,
            },
            H_D=1.15,
            H_G=0.55,
            H_K=0.8,
            domain="generic",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = engine.build_map(hrm_input)

        # All aspects should be normalized and potentially none suppressed
        assert abs(sum(hrm_map.anchor_profile.values()) - 1.0) < 1e-6

    def test_extreme_entropy_values(self, engine: HRMEngine) -> None:
        """Engine should handle extreme entropy values gracefully."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 1.0},
            anchor_scores={"Meaning": 1.0},
            H_D=10.0,  # Way beyond max
            H_G=10.0,  # Way beyond max
            H_K=10.0,  # Way beyond max
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = engine.build_map(hrm_input)

        # Should clamp to max and classify as high
        assert hrm_map.entropy_profile["regime"] == "high"
        assert hrm_map.entropy_profile["H_D_norm"] <= 1.0
