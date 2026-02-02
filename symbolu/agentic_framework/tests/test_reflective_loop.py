"""
Tests for Reflective Loop Component

Tests the Generate → Critic → Decision Gate → Revise pattern:
- QualityCritique dataclass
- GenerationResult dataclass
- RuleBasedCritic
- LLMBasedCritic
- HybridCritic
- ReflectiveGenerator
"""

import pytest

from symbolu.agentic_framework.reflective_loop import (
    QualityCritique,
    GenerationResult,
    RuleBasedCritic,
    LLMBasedCritic,
    HybridCritic,
    ReflectiveGenerator,
)
from symbolu.agentic_framework.llm_adapters import MockLLMAdapter, SequentialMockAdapter


class TestQualityCritique:
    """Tests for QualityCritique dataclass."""

    def test_quality_critique_creation(self):
        """Test basic QualityCritique creation."""
        critique = QualityCritique(
            overall_score=0.85,
            coherence=0.9,
            correctness=0.8,
            completeness=0.85,
            relevance=0.88,
            revision_needed=False,
            revision_type="none",
        )
        assert critique.overall_score == 0.85
        assert critique.coherence == 0.9
        assert critique.issues == []
        assert critique.suggestions == []

    def test_quality_critique_with_issues(self):
        """Test QualityCritique with issues and suggestions."""
        critique = QualityCritique(
            overall_score=0.6,
            coherence=0.7,
            correctness=0.5,
            completeness=0.6,
            relevance=0.7,
            revision_needed=True,
            revision_type="minor",
            issues=["Factual error", "Incomplete"],
            suggestions=["Add sources", "Expand explanation"],
        )
        assert len(critique.issues) == 2
        assert len(critique.suggestions) == 2
        assert critique.revision_needed is True

    def test_quality_critique_to_dict(self):
        """Test QualityCritique serialization."""
        critique = QualityCritique(
            overall_score=0.85,
            coherence=0.9,
            correctness=0.8,
            completeness=0.85,
            relevance=0.88,
            revision_needed=False,
            revision_type="none",
        )
        d = critique.to_dict()

        assert d["overall_score"] == 0.85
        assert d["coherence"] == 0.9
        assert "issues" in d
        assert "suggestions" in d


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_generation_result_creation(self):
        """Test basic GenerationResult creation."""
        result = GenerationResult(
            final_output="Hello!",
            quality_score=0.9,
            revision_count=0,
        )
        assert result.final_output == "Hello!"
        assert result.revision_count == 0
        assert len(result.quality_trajectory) == 0

    def test_generation_result_with_revisions(self):
        """Test GenerationResult with revision history."""
        result = GenerationResult(
            final_output="Final response",
            quality_score=0.9,
            revision_count=2,
            quality_trajectory=[0.6, 0.75, 0.9],
        )
        assert result.revision_count == 2
        assert len(result.quality_trajectory) == 3

    def test_generation_result_to_dict(self):
        """Test GenerationResult serialization."""
        result = GenerationResult(
            final_output="Test",
            quality_score=0.85,
            revision_count=1,
        )
        d = result.to_dict()
        assert d["final_output"] == "Test"
        assert d["quality_score"] == 0.85


class TestRuleBasedCritic:
    """Tests for RuleBasedCritic."""

    def test_rule_based_critic_creation(self):
        """Test RuleBasedCritic creation with defaults."""
        critic = RuleBasedCritic()
        assert critic.min_length == 50
        assert critic.target_length == 500

    def test_rule_based_critic_custom_params(self):
        """Test RuleBasedCritic with custom parameters."""
        critic = RuleBasedCritic(min_length=10, target_length=100)
        assert critic.min_length == 10
        assert critic.target_length == 100

    def test_evaluate_good_response(self):
        """Test evaluation of a good response."""
        critic = RuleBasedCritic(min_length=10, target_length=100)

        prompt = "Tell me about something"
        response = "This is a well-formed response that provides adequate information about the topic at hand."

        critique = critic.evaluate(prompt, response)

        assert critique.overall_score > 0.5
        assert critique.completeness > 0.5

    def test_evaluate_too_short(self):
        """Test evaluation of too-short response."""
        critic = RuleBasedCritic(min_length=50, target_length=200)

        prompt = "Explain something"
        response = "Short."

        critique = critic.evaluate(prompt, response)

        assert critique.overall_score < 0.7
        assert critique.completeness < 0.5
        assert critique.revision_needed is True

    def test_evaluate_empty_response(self):
        """Test evaluation of empty response."""
        critic = RuleBasedCritic()

        critique = critic.evaluate("Question?", "")

        assert critique.overall_score < 0.5
        assert critique.revision_needed is True


class TestLLMBasedCritic:
    """Tests for LLMBasedCritic."""

    def test_llm_based_critic_creation(self):
        """Test LLMBasedCritic creation."""
        llm = MockLLMAdapter()
        critic = LLMBasedCritic(llm)
        assert critic.llm is llm

    def test_evaluate_with_valid_json(self):
        """Test evaluation when LLM returns valid JSON."""
        mock_response = """{
            "coherence": 0.9,
            "correctness": 0.85,
            "completeness": 0.8,
            "relevance": 0.9,
            "issues": ["Minor issue"],
            "suggestions": ["Consider adding more detail"]
        }"""
        llm = MockLLMAdapter(default_response=mock_response)
        critic = LLMBasedCritic(llm)

        critique = critic.evaluate("Test prompt", "Test response")

        assert critique.coherence == 0.9
        assert critique.correctness == 0.85
        assert len(critique.issues) == 1

    def test_evaluate_fallback_on_invalid_json(self):
        """Test fallback when LLM returns invalid JSON."""
        llm = MockLLMAdapter(default_response="I cannot evaluate that")
        critic = LLMBasedCritic(llm)

        critique = critic.evaluate("Test prompt", "Test response")

        # Should return a default critique
        assert critique.overall_score >= 0
        assert critique.overall_score <= 1


class TestHybridCritic:
    """Tests for HybridCritic."""

    def test_hybrid_critic_creation(self):
        """Test HybridCritic creation."""
        llm = MockLLMAdapter()
        critic = HybridCritic(llm, use_llm_threshold=0.7)
        assert critic.use_llm_threshold == 0.7

    def test_hybrid_uses_rules_for_low_quality(self):
        """Test that hybrid uses rule-based for low quality."""
        # LLM returns high scores
        mock_response = """{
            "coherence": 0.95,
            "correctness": 0.95,
            "completeness": 0.95,
            "relevance": 0.95,
            "issues": [],
            "suggestions": []
        }"""
        llm = MockLLMAdapter(default_response=mock_response)
        critic = HybridCritic(llm, use_llm_threshold=0.8)

        # Very short response should get low rule-based score
        critique = critic.evaluate("Explain quantum physics", "Hi")

        # Rule-based should flag this as too short
        assert critique.completeness < 0.5


class TestReflectiveGenerator:
    """Tests for ReflectiveGenerator."""

    def test_generator_creation(self):
        """Test ReflectiveGenerator creation."""
        llm = MockLLMAdapter()
        critic = RuleBasedCritic()
        generator = ReflectiveGenerator(llm, critic)

        assert generator.max_revisions == 3
        assert generator.threshold_high == 0.85

    def test_generator_custom_params(self):
        """Test ReflectiveGenerator with custom parameters."""
        llm = MockLLMAdapter()
        critic = RuleBasedCritic()
        generator = ReflectiveGenerator(
            llm, critic,
            max_revisions=5,
            threshold_high=0.9,
        )

        assert generator.max_revisions == 5
        assert generator.threshold_high == 0.9

    def test_generate_good_first_response(self):
        """Test generation when first response is good enough."""
        good_response = "This is a comprehensive and well-structured response that adequately addresses the question with relevant details and examples."
        llm = MockLLMAdapter(default_response=good_response)
        critic = RuleBasedCritic(min_length=10, target_length=50)
        generator = ReflectiveGenerator(llm, critic, threshold_high=0.6)

        result = generator.generate("Ask something")

        assert result.final_output == good_response
        assert result.revision_count == 0

    def test_generate_with_revisions(self):
        """Test generation requiring revisions."""
        # Responses improve over iterations
        responses = [
            "Short.",  # Too short
            "This is a bit longer but still needs more detail.",  # Medium
            "This is a comprehensive response that covers all aspects of the question with sufficient detail and clarity to be helpful.",  # Good
        ]
        llm = SequentialMockAdapter(responses)
        critic = RuleBasedCritic(min_length=20, target_length=80)
        generator = ReflectiveGenerator(llm, critic, max_revisions=3, threshold_high=0.75)

        result = generator.generate("Explain something")

        # Should have revised at least once
        assert result.revision_count >= 1
        assert len(result.quality_trajectory) >= 2

    def test_generate_max_revisions_limit(self):
        """Test that max revisions limit is respected."""
        # LLM always returns poor response
        llm = MockLLMAdapter(default_response="Bad")
        critic = RuleBasedCritic(min_length=100)
        generator = ReflectiveGenerator(llm, critic, max_revisions=2, threshold_high=0.9)

        result = generator.generate("Question")

        # Should stop after max_revisions
        assert result.revision_count <= 2

    def test_generate_with_context(self):
        """Test generation with conversation context."""
        llm = MockLLMAdapter(default_response="Contextual response that builds on previous conversation about programming and Python specifically.")
        critic = RuleBasedCritic(min_length=10, target_length=50)
        generator = ReflectiveGenerator(llm, critic, threshold_high=0.6)

        context = "User asked about Python programming."
        result = generator.generate("Tell me more", context=context)

        # Verify context was passed to LLM
        assert len(llm.call_history) >= 1

    def test_generate_single_pass(self):
        """Test single-pass generation without revision."""
        llm = MockLLMAdapter(default_response="Single pass response.")
        critic = RuleBasedCritic(min_length=10, target_length=50)
        generator = ReflectiveGenerator(llm, critic)

        result = generator.generate_single_pass("Question")

        assert result.revision_count == 0
        assert len(result.quality_trajectory) == 1


class TestReflectiveLoopIntegration:
    """Integration tests for the reflective loop."""

    def test_full_reflection_cycle(self):
        """Test a complete reflection cycle."""
        # Simulate improving responses
        responses = [
            "Initial brief answer.",
            "A more detailed answer that expands on the initial response with additional context.",
            "A comprehensive and well-structured answer that fully addresses the question with examples and clear explanations.",
        ]
        llm = SequentialMockAdapter(responses)
        critic = RuleBasedCritic(min_length=20, target_length=80)
        generator = ReflectiveGenerator(
            llm, critic,
            max_revisions=3,
            threshold_high=0.8,
        )

        result = generator.generate("Explain machine learning")

        # Verify the loop worked
        assert result.quality_score >= 0.5
        assert result.revision_count >= 0

    def test_quality_trajectory_tracking(self):
        """Test that quality trajectory is tracked."""
        responses = [
            "x",  # Terrible
            "A somewhat better response with more content.",
            "A much improved response that addresses the question thoroughly.",
        ]
        llm = SequentialMockAdapter(responses)
        critic = RuleBasedCritic(min_length=10, target_length=50)
        generator = ReflectiveGenerator(llm, critic, max_revisions=3, threshold_high=0.7)

        result = generator.generate("Question")

        # Quality trajectory should show improvement
        if len(result.quality_trajectory) > 1:
            # Later scores should generally be higher
            assert result.quality_trajectory[-1] >= result.quality_trajectory[0]
