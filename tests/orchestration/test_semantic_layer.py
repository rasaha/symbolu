"""
Tests for the semantic layer.

Verifies:
- Keyword-based intent parsing (NO LLM)
- Semantic vector generation
- Mechanical constraint translation
"""

import pytest
from symbolu.orchestration.semantic_layer import (
    SemanticDimension,
    SemanticVector,
    ParsedIntent,
    IntentParser,
    ResponseProjector,
    parse_intent,
    intent_to_constraints,
    SEMANTIC_KEYWORDS,
)


class TestSemanticVector:
    """Tests for SemanticVector dataclass."""

    def test_default_values(self):
        """Default vector is all zeros."""
        v = SemanticVector()
        assert v.energy == 0.0
        assert v.duration == 0.0
        assert v.complexity == 0.0
        assert v.direction == 0.0
        assert v.stability == 0.0
        assert v.rhythm == 0.0

    def test_clamping_positive(self):
        """Values above 1.0 are clamped."""
        v = SemanticVector(energy=2.0, duration=1.5)
        assert v.energy == 1.0
        assert v.duration == 1.0

    def test_clamping_negative(self):
        """Values below -1.0 are clamped."""
        v = SemanticVector(energy=-2.0, direction=-1.5)
        assert v.energy == -1.0
        assert v.direction == -1.0

    def test_to_dict(self):
        """Conversion to dictionary works."""
        v = SemanticVector(energy=0.5, duration=-0.3)
        d = v.to_dict()
        assert d["energy"] == 0.5
        assert d["duration"] == -0.3
        assert len(d) == 6

    def test_from_dict(self):
        """Creation from dictionary works."""
        d = {"energy": 0.7, "complexity": -0.4}
        v = SemanticVector.from_dict(d)
        assert v.energy == 0.7
        assert v.complexity == -0.4
        assert v.duration == 0.0  # Default

    def test_from_dict_missing_keys(self):
        """Missing keys default to 0.0."""
        v = SemanticVector.from_dict({})
        assert v.energy == 0.0


class TestIntentParser:
    """Tests for keyword-based intent parsing."""

    def test_single_keyword_energy_low(self):
        """Single calm keyword produces negative energy."""
        result = parse_intent("something calm")
        assert result.semantic_vector.energy < 0
        assert "calm" in result.keywords_matched

    def test_single_keyword_energy_high(self):
        """Single energetic keyword produces positive energy."""
        result = parse_intent("something energetic")
        assert result.semantic_vector.energy > 0
        assert "energetic" in result.keywords_matched

    def test_multiple_keywords_same_dimension(self):
        """Multiple keywords in same dimension are averaged."""
        result = parse_intent("calm and gentle and peaceful")
        # All negative energy keywords
        assert result.semantic_vector.energy < 0
        assert len(result.keywords_matched) == 3

    def test_multiple_keywords_different_dimensions(self):
        """Keywords from different dimensions set different values."""
        result = parse_intent("calm but complex")
        assert result.semantic_vector.energy < 0  # calm
        assert result.semantic_vector.complexity > 0  # complex

    def test_no_keywords(self):
        """No matched keywords produces zero vector."""
        result = parse_intent("something xyz")
        assert result.semantic_vector.energy == 0.0
        assert result.keywords_matched == []
        assert result.confidence == 0.1  # Low confidence

    def test_confidence_scales_with_keywords(self):
        """Confidence increases with more keywords."""
        result1 = parse_intent("calm")
        result2 = parse_intent("calm gentle peaceful soothing")
        assert result2.confidence > result1.confidence

    def test_confidence_max_cap(self):
        """Confidence is capped at 1.0."""
        result = parse_intent("calm gentle soft peaceful relaxing soothing quiet subtle")
        assert result.confidence <= 1.0

    def test_case_insensitive(self):
        """Keyword matching is case insensitive."""
        result = parse_intent("CALM and ENERGETIC")
        # Both should match
        assert len(result.keywords_matched) >= 2

    def test_direction_keywords(self):
        """Direction keywords work correctly."""
        rising = parse_intent("rising building")
        falling = parse_intent("falling settling")
        assert rising.semantic_vector.direction > 0
        assert falling.semantic_vector.direction < 0

    def test_duration_keywords(self):
        """Duration keywords work correctly."""
        short = parse_intent("short brief")
        long = parse_intent("long extended")
        assert short.semantic_vector.duration < 0
        assert long.semantic_vector.duration > 0

    def test_original_text_preserved(self):
        """Original text is preserved in result."""
        text = "something calm and gentle"
        result = parse_intent(text)
        assert result.original_text == text

    def test_custom_keywords(self):
        """Custom keywords can be added."""
        parser = IntentParser(custom_keywords={
            "mystical": (SemanticDimension.COMPLEXITY, 0.9)
        })
        result = parser.parse("something mystical")
        assert "mystical" in result.keywords_matched
        assert result.semantic_vector.complexity > 0


class TestConstraintTranslation:
    """Tests for semantic-to-mechanical constraint translation."""

    def test_low_energy_magnitude_constraint(self):
        """Low energy translates to low magnitude constraint."""
        constraints = intent_to_constraints("calm peaceful")
        assert "final_magnitude" in constraints
        # Should constrain to lower magnitude
        assert "1.0" in constraints["final_magnitude"]

    def test_high_energy_magnitude_constraint(self):
        """High energy translates to higher magnitude constraint."""
        constraints = intent_to_constraints("energetic powerful")
        assert "final_magnitude" in constraints
        assert ">=" in constraints["final_magnitude"]

    def test_short_duration_steps_constraint(self):
        """Short duration translates to fewer steps."""
        constraints = intent_to_constraints("short brief")
        assert "len(steps)" in constraints
        assert "<=" in constraints["len(steps)"]

    def test_long_duration_steps_constraint(self):
        """Long duration translates to more steps."""
        constraints = intent_to_constraints("long extended")
        assert "len(steps)" in constraints
        assert ">=" in constraints["len(steps)"]

    def test_simple_complexity_template(self):
        """Simple complexity suggests CV template."""
        constraints = intent_to_constraints("simple basic")
        assert "template starts_with" in constraints or len(constraints) > 0

    def test_falling_direction_monotonic(self):
        """Falling direction suggests monotonic decreasing."""
        constraints = intent_to_constraints("falling settling")
        # Should have monotonic constraint
        monotonic_key = "monotonic_decreasing(steps[].magnitude)"
        assert monotonic_key in constraints

    def test_rising_direction_monotonic(self):
        """Rising direction suggests monotonic increasing."""
        constraints = intent_to_constraints("rising building")
        monotonic_key = "monotonic_increasing(steps[].magnitude)"
        assert monotonic_key in constraints

    def test_no_constraints_for_neutral(self):
        """Neutral input produces minimal constraints."""
        constraints = intent_to_constraints("something")
        # Should be empty or minimal
        assert len(constraints) <= 1


class TestResponseProjector:
    """Tests for projecting outputs back to semantic space."""

    def test_project_empty_sequences(self):
        """Projecting empty sequences returns count 0."""
        projector = ResponseProjector()
        result = projector.project(tuple(), None, None)
        assert result["aggregate"]["count"] == 0

    def test_project_single_sequence(self):
        """Projecting single sequence works."""
        projector = ResponseProjector()
        sequences = (("ka", "a", "ga"),)
        result = projector.project(sequences, None, None)
        assert result["aggregate"]["count"] == 1
        assert result["aggregate"]["avg_length"] == 3

    def test_project_multiple_sequences(self):
        """Projecting multiple sequences averages correctly."""
        projector = ResponseProjector()
        sequences = (
            ("ka", "a"),  # length 2
            ("ba", "i", "ta", "u"),  # length 4
        )
        result = projector.project(sequences, None, None)
        assert result["aggregate"]["count"] == 2
        assert result["aggregate"]["avg_length"] == 3.0  # (2+4)/2

    def test_intent_match_calculation(self):
        """Intent match is calculated when intent provided."""
        projector = ResponseProjector()
        sequences = (("ka", "a"),)
        intent = parse_intent("calm gentle")  # Has energy dimension
        result = projector.project(sequences, None, intent)
        assert "intent_match" in result
        assert result["intent_match"] is not None
        assert "overall_match" in result["intent_match"]

    def test_no_intent_match_without_intent(self):
        """No intent match when no intent provided."""
        projector = ResponseProjector()
        sequences = (("ka", "a"),)
        result = projector.project(sequences, None, None)
        assert result["intent_match"] is None


class TestKeywordCoverage:
    """Tests verifying keyword dictionary coverage."""

    def test_energy_keywords_exist(self):
        """Energy dimension has both positive and negative keywords."""
        energy_kws = [
            kw for kw, (dim, val) in SEMANTIC_KEYWORDS.items()
            if dim == SemanticDimension.ENERGY
        ]
        assert len(energy_kws) >= 4
        # Check both poles
        positive = [kw for kw, (dim, val) in SEMANTIC_KEYWORDS.items()
                   if dim == SemanticDimension.ENERGY and val > 0]
        negative = [kw for kw, (dim, val) in SEMANTIC_KEYWORDS.items()
                   if dim == SemanticDimension.ENERGY and val < 0]
        assert len(positive) >= 2
        assert len(negative) >= 2

    def test_all_dimensions_covered(self):
        """All semantic dimensions have keywords."""
        covered_dims = set()
        for kw, (dim, val) in SEMANTIC_KEYWORDS.items():
            covered_dims.add(dim)

        for dim in SemanticDimension:
            assert dim in covered_dims, f"Missing keywords for {dim}"

    def test_keyword_values_in_range(self):
        """All keyword values are in [-1, 1]."""
        for kw, (dim, val) in SEMANTIC_KEYWORDS.items():
            assert -1.0 <= val <= 1.0, f"Keyword {kw} has out-of-range value {val}"
