"""
LCM Unit Tests

Tests for the Low-Context Mapper engine validating:
1. Task type detection
2. Complexity scoring
3. Numeric extraction
4. Entropy regime classification
5. Engine decision
6. Key term extraction
"""

import pytest
from symbolu.mechanical.lcm.lcm_engine import LCMEngine, get_lcm_engine
from symbolu.mechanical.lcm.models import LCMInput, LowContextMap


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def engine() -> LCMEngine:
    """Create a fresh LCM engine for each test."""
    return LCMEngine(complexity_threshold=7)


@pytest.fixture
def basic_input() -> LCMInput:
    """Create a basic LCM input for testing."""
    return LCMInput(
        text="Sort this list alphabetically",
        domain="task",
        aspect_probs={
            "Execution": 0.6,
            "Form": 0.2,
            "Cognition": 0.1,
            "Identity": 0.1,
        },
        anchor_scores={
            "Needs": 0.5,
            "Exchange": 0.3,
            "Challenge": 0.2,
        },
        H_D=0.5,
        H_G=0.3,
        H_K=0.4,
        tier="lower",
        flow_mode="outer_only",
    )


# =============================================================================
# TASK TYPE DETECTION TESTS
# =============================================================================


class TestTaskTypeDetection:
    """Tests for task type detection."""

    def test_sort_detected_as_action(self, engine: LCMEngine) -> None:
        """'Sort this list' should be detected as action."""
        result = engine.detect_task_type("Sort this list")
        assert result == "action"

    def test_arrange_detected_as_action(self, engine: LCMEngine) -> None:
        """'Arrange the items' should be detected as action."""
        result = engine.detect_task_type("Arrange the items by size")
        assert result == "action"

    def test_order_detected_as_action(self, engine: LCMEngine) -> None:
        """'Order by name' should be detected as action."""
        result = engine.detect_task_type("Order these by name")
        assert result == "action"

    def test_numeric_query_detected_as_math(self, engine: LCMEngine) -> None:
        """'What is 25?' should be detected as math."""
        result = engine.detect_task_type("What is 25?")
        assert result == "math"

    def test_arithmetic_detected_as_math(self, engine: LCMEngine) -> None:
        """'Add 5 and 7' should be detected as math."""
        result = engine.detect_task_type("Add 5 and 7")
        assert result == "math"

    def test_py_file_detected_as_code(self, engine: LCMEngine) -> None:
        """'Open myfile.py' should be detected as code."""
        result = engine.detect_task_type("Open myfile.py")
        assert result == "code"

    def test_json_file_detected_as_code(self, engine: LCMEngine) -> None:
        """'Parse config.json' should be detected as code."""
        result = engine.detect_task_type("Parse config.json")
        assert result == "code"

    def test_function_keyword_detected_as_code(self, engine: LCMEngine) -> None:
        """'Write a function that...' should be detected as code."""
        result = engine.detect_task_type("Write a function that adds numbers")
        assert result == "code"

    def test_class_keyword_detected_as_code(self, engine: LCMEngine) -> None:
        """'Create a class for...' should be detected as code."""
        result = engine.detect_task_type("Create a class for users")
        assert result == "code"

    def test_variable_keyword_detected_as_code(self, engine: LCMEngine) -> None:
        """'Define a variable...' should be detected as code."""
        result = engine.detect_task_type("Define a variable called counter")
        assert result == "code"

    def test_what_is_detected_as_lookup(self, engine: LCMEngine) -> None:
        """'What is the capital?' should be detected as lookup."""
        result = engine.detect_task_type("What is the capital of France?")
        assert result == "lookup"

    def test_where_is_detected_as_lookup(self, engine: LCMEngine) -> None:
        """'Where is the config?' should be detected as lookup."""
        result = engine.detect_task_type("Where is the config file?")
        assert result == "lookup"

    def test_lookup_keyword_detected(self, engine: LCMEngine) -> None:
        """'Lookup the value' should be detected as lookup."""
        result = engine.detect_task_type("Lookup the value in the table")
        assert result == "lookup"

    def test_generic_fallback(self, engine: LCMEngine) -> None:
        """Unclassifiable text should return generic."""
        result = engine.detect_task_type("Hello world")
        assert result == "generic"

    def test_empty_text_returns_generic(self, engine: LCMEngine) -> None:
        """Empty text should return generic."""
        result = engine.detect_task_type("")
        assert result == "generic"


# =============================================================================
# COMPLEXITY SCORING TESTS
# =============================================================================


class TestComplexityScoring:
    """Tests for complexity scoring."""

    def test_short_text_low_complexity(self, engine: LCMEngine) -> None:
        """Short texts should have complexity < 0.3."""
        # 2 tokens
        complexity = engine.compute_complexity("Sort list")
        assert complexity < 0.3

    def test_medium_text_medium_complexity(self, engine: LCMEngine) -> None:
        """Medium texts should have complexity between 0.3 and 0.7."""
        # 4 tokens = 4/7 ~ 0.57
        complexity = engine.compute_complexity("Sort this list alphabetically")
        assert 0.3 <= complexity <= 0.7

    def test_long_text_capped_at_one(self, engine: LCMEngine) -> None:
        """Long texts should have complexity capped at 1.0."""
        # 10+ tokens should be capped
        complexity = engine.compute_complexity(
            "This is a very long sentence with many many words in it"
        )
        assert complexity == 1.0

    def test_exactly_threshold_equals_one(self, engine: LCMEngine) -> None:
        """Text with exactly threshold tokens should have complexity = 1.0."""
        # 7 tokens
        complexity = engine.compute_complexity("One two three four five six seven")
        assert complexity == 1.0

    def test_empty_text_zero_complexity(self, engine: LCMEngine) -> None:
        """Empty text should have complexity 0."""
        complexity = engine.compute_complexity("")
        assert complexity == 0.0

    def test_custom_threshold(self) -> None:
        """Custom threshold should affect complexity calculation."""
        engine = LCMEngine(complexity_threshold=10)
        # 5 tokens = 5/10 = 0.5
        complexity = engine.compute_complexity("One two three four five")
        assert complexity == pytest.approx(0.5, abs=0.01)


# =============================================================================
# NUMERIC EXTRACTION TESTS
# =============================================================================


class TestNumericExtraction:
    """Tests for numeric feature extraction."""

    def test_extract_two_numbers(self, engine: LCMEngine) -> None:
        """'Add 5 and 7' should extract count=2, max=7."""
        result = engine.extract_numeric_features("Add 5 and 7")
        assert result["count"] == 2
        assert result["max"] == 7
        assert result["min"] == 5
        assert result["sum"] == 12

    def test_extract_single_number(self, engine: LCMEngine) -> None:
        """'What is 25?' should extract count=1."""
        result = engine.extract_numeric_features("What is 25?")
        assert result["count"] == 1
        assert result["max"] == 25
        assert result["min"] == 25
        assert result["sum"] == 25

    def test_extract_float_numbers(self, engine: LCMEngine) -> None:
        """Should extract float numbers correctly."""
        result = engine.extract_numeric_features("Calculate 3.14 times 2.5")
        assert result["count"] == 2
        assert result["max"] == pytest.approx(3.14, abs=0.01)
        assert result["min"] == pytest.approx(2.5, abs=0.01)

    def test_no_numbers_returns_count_zero(self, engine: LCMEngine) -> None:
        """Text without numbers should return count=0."""
        result = engine.extract_numeric_features("Sort this list")
        assert result["count"] == 0
        assert "max" not in result
        assert "min" not in result
        assert "sum" not in result

    def test_mixed_integers_and_floats(self, engine: LCMEngine) -> None:
        """Should handle mixed integer and float numbers."""
        result = engine.extract_numeric_features("Add 10 and 2.5 and 7")
        assert result["count"] == 3
        assert result["max"] == 10
        assert result["min"] == pytest.approx(2.5, abs=0.01)
        assert result["sum"] == pytest.approx(19.5, abs=0.01)


# =============================================================================
# ENTROPY REGIME CLASSIFICATION TESTS
# =============================================================================


class TestEntropyRegimeClassification:
    """Tests for entropy regime classification."""

    def test_low_entropy_regime(self, engine: LCMEngine) -> None:
        """Low entropy values should return 'low'."""
        # H_D = 0.3 -> 0.3/2.3 ~ 0.13
        # H_G = 0.2 -> 0.2/1.1 ~ 0.18
        # mix = 0.7*0.13 + 0.3*0.18 ~ 0.145 < 0.33
        result = engine.classify_entropy_regime(H_D=0.3, H_G=0.2)
        assert result == "low"

    def test_medium_entropy_regime(self, engine: LCMEngine) -> None:
        """Medium entropy values should return 'medium'."""
        # H_D = 1.1 -> 1.1/2.3 ~ 0.48
        # H_G = 0.55 -> 0.55/1.1 ~ 0.5
        # mix = 0.7*0.48 + 0.3*0.5 ~ 0.486 (medium)
        result = engine.classify_entropy_regime(H_D=1.1, H_G=0.55)
        assert result == "medium"

    def test_high_entropy_regime(self, engine: LCMEngine) -> None:
        """High entropy values should return 'high'."""
        # H_D = 2.0 -> 2.0/2.3 ~ 0.87
        # H_G = 0.95 -> 0.95/1.1 ~ 0.86
        # mix = 0.7*0.87 + 0.3*0.86 ~ 0.867 >= 0.66
        result = engine.classify_entropy_regime(H_D=2.0, H_G=0.95)
        assert result == "high"

    def test_zero_entropy_is_low(self, engine: LCMEngine) -> None:
        """Zero entropy should return 'low'."""
        result = engine.classify_entropy_regime(H_D=0.0, H_G=0.0)
        assert result == "low"

    def test_exceeding_max_entropy_clamped(self, engine: LCMEngine) -> None:
        """Values exceeding max should be clamped and return 'high'."""
        result = engine.classify_entropy_regime(H_D=10.0, H_G=10.0)
        assert result == "high"


# =============================================================================
# ENGINE DECISION TESTS
# =============================================================================


class TestEngineDecision:
    """Tests for engine recommendation."""

    def test_math_low_complexity_returns_renderer(self, engine: LCMEngine) -> None:
        """Math + low complexity should return 'renderer_only'."""
        result = engine.choose_engine(task_type="math", complexity_score=0.2)
        assert result == "renderer_only"

    def test_math_high_complexity_returns_persona(self, engine: LCMEngine) -> None:
        """Math + high complexity should return 'persona'."""
        result = engine.choose_engine(task_type="math", complexity_score=0.5)
        assert result == "persona"

    def test_code_returns_fusion(self, engine: LCMEngine) -> None:
        """Code task should return 'fusion'."""
        result = engine.choose_engine(task_type="code", complexity_score=0.5)
        assert result == "fusion"

    def test_lookup_returns_fusion(self, engine: LCMEngine) -> None:
        """Lookup task should return 'fusion'."""
        result = engine.choose_engine(task_type="lookup", complexity_score=0.3)
        assert result == "fusion"

    def test_action_returns_fusion(self, engine: LCMEngine) -> None:
        """Action task should return 'fusion'."""
        result = engine.choose_engine(task_type="action", complexity_score=0.4)
        assert result == "fusion"

    def test_generic_returns_persona(self, engine: LCMEngine) -> None:
        """Generic task should return 'persona'."""
        result = engine.choose_engine(task_type="generic", complexity_score=0.5)
        assert result == "persona"


# =============================================================================
# KEY TERM EXTRACTION TESTS
# =============================================================================


class TestKeyTermExtraction:
    """Tests for key term extraction."""

    def test_filters_short_tokens(self, engine: LCMEngine) -> None:
        """Tokens with length <= 2 should be filtered out."""
        result = engine.extract_key_terms("I am a dog")
        assert "dog" in result
        assert "i" not in result
        assert "am" not in result
        assert "a" not in result

    def test_lowercase_conversion(self, engine: LCMEngine) -> None:
        """Tokens should be lowercased."""
        result = engine.extract_key_terms("HELLO World")
        assert "hello" in result
        assert "world" in result
        assert "HELLO" not in result
        assert "World" not in result

    def test_alphanumeric_only(self, engine: LCMEngine) -> None:
        """Only alphanumeric tokens should be extracted."""
        result = engine.extract_key_terms("Hello, world! How are you?")
        assert "hello" in result
        assert "world" in result
        assert "how" in result
        assert "are" in result
        assert "you" in result

    def test_empty_text_returns_empty(self, engine: LCMEngine) -> None:
        """Empty text should return empty list."""
        result = engine.extract_key_terms("")
        assert result == []

    def test_numeric_tokens_included(self, engine: LCMEngine) -> None:
        """Numeric tokens with length > 2 should be included."""
        result = engine.extract_key_terms("Add 123 and 456")
        assert "add" in result
        assert "123" in result
        assert "456" in result
        assert "and" in result


# =============================================================================
# BUILD MAP INTEGRATION TESTS
# =============================================================================


class TestBuildMap:
    """Tests for the complete build_map function."""

    def test_build_map_returns_low_context_map(
        self, engine: LCMEngine, basic_input: LCMInput
    ) -> None:
        """build_map should return a LowContextMap instance."""
        result = engine.build_map(basic_input)
        assert isinstance(result, LowContextMap)

    def test_build_map_action_task(self, engine: LCMEngine) -> None:
        """build_map for action task should detect correct type."""
        lcm_input = LCMInput(
            text="Sort this list",
            domain="task",
            aspect_probs={"Execution": 0.8},
            anchor_scores={"Needs": 0.5},
            H_D=0.3,
            H_G=0.2,
            H_K=0.2,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)

        assert result.task_type == "action"
        assert result.entropy_regime == "low"
        assert result.recommended_engine == "fusion"

    def test_build_map_math_task(self, engine: LCMEngine) -> None:
        """build_map for math task should detect correct type and engine."""
        lcm_input = LCMInput(
            text="5 3",  # Very short: 2 tokens / 7 = 0.29 < 0.3
            domain="math",
            aspect_probs={"Cognition": 0.8},
            anchor_scores={"Needs": 0.5},
            H_D=0.3,
            H_G=0.2,
            H_K=0.2,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)

        assert result.task_type == "math"
        assert result.numeric_features["count"] == 2
        # Low complexity math -> renderer_only
        assert result.recommended_engine == "renderer_only"

    def test_build_map_code_task(self, engine: LCMEngine) -> None:
        """build_map for code task should recommend fusion."""
        lcm_input = LCMInput(
            text="Fix the function in main.py",
            domain="code",
            aspect_probs={"Execution": 0.7, "Cognition": 0.3},
            anchor_scores={"Needs": 0.6, "Challenge": 0.4},
            H_D=0.5,
            H_G=0.4,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)

        assert result.task_type == "code"
        assert result.recommended_engine == "fusion"

    def test_build_map_lookup_task(self, engine: LCMEngine) -> None:
        """build_map for lookup task should work correctly."""
        lcm_input = LCMInput(
            text="Where is the config file?",
            domain="lookup",
            aspect_probs={"Execution": 0.5, "Form": 0.5},
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.4,
            H_G=0.3,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)

        assert result.task_type == "lookup"
        assert result.recommended_engine == "fusion"


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_lcm_engine_returns_singleton(self) -> None:
        """get_lcm_engine should return the same instance."""
        engine1 = get_lcm_engine()
        engine2 = get_lcm_engine()
        assert engine1 is engine2

    def test_singleton_is_lcm_engine_instance(self) -> None:
        """Singleton should be an LCMEngine instance."""
        engine = get_lcm_engine()
        assert isinstance(engine, LCMEngine)


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestLowContextMap:
    """Tests for LowContextMap model."""

    def test_to_dict(self, engine: LCMEngine, basic_input: LCMInput) -> None:
        """to_dict should serialize all fields."""
        lcm_map = engine.build_map(basic_input)
        result = lcm_map.to_dict()

        assert "task_type" in result
        assert "key_terms" in result
        assert "numeric_features" in result
        assert "complexity_score" in result
        assert "entropy_regime" in result
        assert "recommended_engine" in result

    def test_repr(self, engine: LCMEngine, basic_input: LCMInput) -> None:
        """__repr__ should provide concise summary."""
        lcm_map = engine.build_map(basic_input)
        repr_str = repr(lcm_map)

        assert "LowContextMap" in repr_str
        assert lcm_map.task_type in repr_str
        assert lcm_map.entropy_regime in repr_str
        assert lcm_map.recommended_engine in repr_str

    def test_default_values(self) -> None:
        """LowContextMap should have sensible defaults."""
        lcm_map = LowContextMap()
        assert lcm_map.task_type == "generic"
        assert lcm_map.key_terms == []
        assert lcm_map.numeric_features == {}
        assert lcm_map.complexity_score == 0.0
        assert lcm_map.entropy_regime == "low"
        assert lcm_map.recommended_engine == "fusion"


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_special_characters_in_text(self, engine: LCMEngine) -> None:
        """Engine should handle special characters gracefully."""
        lcm_input = LCMInput(
            text="@#$%^&*(){}[]|\\:\";<>,.?/~`",
            domain="generic",
            aspect_probs={"Execution": 1.0},
            anchor_scores={"Needs": 1.0},
            H_D=0.5,
            H_G=0.3,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)

        assert result.task_type == "generic"
        assert result.key_terms == []
        assert result.complexity_score == 0.0

    def test_unicode_text(self, engine: LCMEngine) -> None:
        """Engine should handle unicode text."""
        lcm_input = LCMInput(
            text="Sort these items",
            domain="task",
            aspect_probs={"Execution": 0.8},
            anchor_scores={"Needs": 0.5},
            H_D=0.3,
            H_G=0.2,
            H_K=0.2,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)
        assert result.task_type == "action"

    def test_very_long_text(self, engine: LCMEngine) -> None:
        """Engine should handle very long text."""
        long_text = " ".join(["word"] * 100)
        lcm_input = LCMInput(
            text=long_text,
            domain="generic",
            aspect_probs={"Execution": 0.5},
            anchor_scores={"Needs": 0.5},
            H_D=1.0,
            H_G=0.5,
            H_K=0.5,
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )
        result = engine.build_map(lcm_input)

        assert result.complexity_score == 1.0
        assert len(result.key_terms) == 100

    def test_empty_aspect_probs(self, engine: LCMEngine) -> None:
        """Engine should handle empty aspect_probs."""
        lcm_input = LCMInput(
            text="Sort this",
            domain="task",
            aspect_probs={},
            anchor_scores={"Needs": 0.5},
            H_D=0.3,
            H_G=0.2,
            H_K=0.2,
            tier="lower",
            flow_mode="outer_only",
        )
        result = engine.build_map(lcm_input)
        assert result.task_type == "action"

    def test_negative_entropy_clamped(self, engine: LCMEngine) -> None:
        """Negative entropy values should be clamped to 0."""
        result = engine.classify_entropy_regime(H_D=-1.0, H_G=-1.0)
        assert result == "low"


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestStatistics:
    """Tests for engine statistics."""

    def test_get_statistics(self, engine: LCMEngine) -> None:
        """get_statistics should return configuration values."""
        stats = engine.get_statistics()

        assert "complexity_threshold" in stats
        assert "entropy_low_threshold" in stats
        assert "entropy_high_threshold" in stats
        assert stats["complexity_threshold"] == 7
        assert stats["entropy_low_threshold"] == 0.33
        assert stats["entropy_high_threshold"] == 0.66
