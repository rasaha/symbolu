"""
Tests for Local Critic module.

Tests the cheaper reflection implementation using local models.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from symbolu.agentic_framework.local_critic import (
    LocalInferenceBackend,
    OllamaBackend,
    TransformersBackend,
    LlamaCppBackend,
    LocalCritic,
    CostAwareCriticSelector,
    SelectionStrategy,
    CriticType,
    CRITIC_COSTS,
    LOCAL_CRITIC_PROMPT,
    MINIMAL_CRITIC_PROMPT,
    create_ollama_critic,
    create_cost_aware_critic,
)
from symbolu.agentic_framework.reflective_loop import (
    QualityCritique,
    RuleBasedCritic,
)


# =============================================================================
# Mock Backend for Testing
# =============================================================================


class MockLocalBackend(LocalInferenceBackend):
    """Mock backend for testing without actual model."""

    def __init__(self, responses: list = None, available: bool = True):
        self.responses = responses or [
            '{"coherence": 0.8, "correctness": 0.7, "completeness": 0.75, "relevance": 0.85}'
        ]
        self._response_idx = 0
        self._available = available
        self.calls = []

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens})
        response = self.responses[self._response_idx % len(self.responses)]
        self._response_idx += 1
        return response

    def is_available(self) -> bool:
        return self._available

    @property
    def model_name(self) -> str:
        return "mock:test"


# =============================================================================
# OllamaBackend Tests
# =============================================================================


class TestOllamaBackend:
    """Tests for Ollama backend."""

    def test_init_defaults(self):
        backend = OllamaBackend()
        assert backend.model == "phi3:mini"
        assert backend.host == "http://localhost:11434"
        assert backend.timeout == 30.0

    def test_init_custom(self):
        backend = OllamaBackend(
            model="llama3.2:3b",
            host="http://custom:8080",
            timeout=60.0,
        )
        assert backend.model == "llama3.2:3b"
        assert backend.host == "http://custom:8080"
        assert backend.timeout == 60.0

    def test_model_name(self):
        backend = OllamaBackend(model="phi3:mini")
        assert backend.model_name == "ollama:phi3:mini"

    @patch("urllib.request.urlopen")
    def test_is_available_true(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models": [{"name": "phi3:mini"}]}'
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        backend = OllamaBackend(model="phi3:mini")
        assert backend.is_available() is True

    @patch("urllib.request.urlopen")
    def test_is_available_model_not_found(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models": [{"name": "other:model"}]}'
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        backend = OllamaBackend(model="phi3:mini")
        assert backend.is_available() is False

    @patch("urllib.request.urlopen")
    def test_is_available_connection_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        backend = OllamaBackend()
        assert backend.is_available() is False


# =============================================================================
# TransformersBackend Tests
# =============================================================================


class TestTransformersBackend:
    """Tests for HuggingFace Transformers backend."""

    def test_init_defaults(self):
        backend = TransformersBackend()
        assert backend.model_id == "microsoft/phi-3-mini-4k-instruct"
        assert backend.device == "auto"

    def test_model_name(self):
        backend = TransformersBackend(model_id="meta-llama/Llama-3.2-3B")
        assert backend.model_name == "transformers:meta-llama/Llama-3.2-3B"

    def test_is_available_without_transformers(self):
        backend = TransformersBackend()
        # Will check if transformers is importable
        available = backend.is_available()
        # Just ensure it returns a boolean
        assert isinstance(available, bool)


# =============================================================================
# LlamaCppBackend Tests
# =============================================================================


class TestLlamaCppBackend:
    """Tests for llama.cpp backend."""

    def test_init(self):
        backend = LlamaCppBackend(
            model_path="/path/to/model.gguf",
            n_ctx=4096,
            n_gpu_layers=32,
        )
        assert backend.model_path == "/path/to/model.gguf"
        assert backend.n_ctx == 4096
        assert backend.n_gpu_layers == 32

    def test_model_name(self):
        backend = LlamaCppBackend(model_path="/models/phi-3-mini-Q4.gguf")
        assert backend.model_name == "llama.cpp:phi-3-mini-Q4.gguf"

    def test_is_available_no_file(self):
        backend = LlamaCppBackend(model_path="/nonexistent/model.gguf")
        # Should be False (file doesn't exist)
        assert backend.is_available() is False


# =============================================================================
# LocalCritic Tests
# =============================================================================


class TestLocalCritic:
    """Tests for LocalCritic implementation."""

    def test_evaluate_success(self):
        backend = MockLocalBackend(responses=[
            '{"coherence": 0.9, "correctness": 0.8, "completeness": 0.85, "relevance": 0.9}'
        ])
        critic = LocalCritic(backend=backend)

        critique = critic.evaluate(
            prompt="What is Python?",
            response="Python is a programming language...",
        )

        assert isinstance(critique, QualityCritique)
        assert critique.coherence == 0.9
        assert critique.correctness == 0.8
        assert critique.completeness == 0.85
        assert critique.relevance == 0.9
        assert 0.85 < critique.overall_score < 0.9

    def test_evaluate_with_issues(self):
        backend = MockLocalBackend(responses=[
            '{"coherence": 0.4, "correctness": 0.3, "completeness": 0.2, "relevance": 0.5, "issues": ["Too short"], "suggestions": ["Add more detail"]}'
        ])
        critic = LocalCritic(backend=backend)

        critique = critic.evaluate("Explain X", "X is Y.")

        assert critique.overall_score < 0.5
        assert critique.revision_needed is True
        assert critique.revision_type == "major"
        assert "Too short" in critique.issues
        assert "Add more detail" in critique.suggestions

    def test_evaluate_truncates_long_response(self):
        backend = MockLocalBackend()
        critic = LocalCritic(backend=backend, max_response_length=100)

        long_response = "A" * 500
        critic.evaluate("test", long_response)

        # Check that the prompt was truncated
        call = backend.calls[0]
        assert "A" * 100 in call["prompt"]
        assert "A" * 500 not in call["prompt"]

    def test_evaluate_fallback_to_rules(self):
        backend = MockLocalBackend(available=True)
        backend.generate = Mock(side_effect=Exception("Model failed"))

        critic = LocalCritic(backend=backend, fallback_to_rules=True)
        critique = critic.evaluate("What is X?", "X is a thing that does Y.")

        # Should still return a critique from rule-based fallback
        assert isinstance(critique, QualityCritique)
        assert critique.overall_score > 0

    def test_evaluate_no_fallback_returns_default(self):
        backend = MockLocalBackend()
        backend.generate = Mock(side_effect=Exception("Model failed"))

        critic = LocalCritic(backend=backend, fallback_to_rules=False)
        critique = critic.evaluate("test", "response")

        # Should return default moderate scores
        assert critique.overall_score == 0.6
        assert "Local evaluation failed" in critique.issues[0]

    def test_parse_malformed_json(self):
        backend = MockLocalBackend(responses=[
            "coherence: 0.7, correctness: 0.8"  # Not valid JSON
        ])
        critic = LocalCritic(backend=backend)

        # Should extract scores even from malformed output
        critique = critic.evaluate("test", "response")
        assert critique.coherence == 0.7
        assert critique.correctness == 0.8

    def test_minimal_prompt_mode(self):
        backend = MockLocalBackend()
        critic = LocalCritic(backend=backend, use_minimal_prompt=True)

        critic.evaluate("What is X?", "X is Y.")

        call = backend.calls[0]
        # Minimal prompt should be shorter
        assert len(call["prompt"]) < 500


# =============================================================================
# CostAwareCriticSelector Tests
# =============================================================================


class TestCostAwareCriticSelector:
    """Tests for cost-aware critic selection."""

    def test_init_with_defaults(self):
        selector = CostAwareCriticSelector()
        assert selector.rule_critic is not None
        assert selector.strategy is not None

    def test_select_rule_for_simple(self):
        selector = CostAwareCriticSelector()

        # Simple prompt/response should use rules
        critique, critic_type = selector.evaluate(
            prompt="Hi",
            response="Hello!",
        )

        assert critic_type == CriticType.RULE_BASED
        assert isinstance(critique, QualityCritique)

    def test_select_local_for_medium_complexity(self):
        backend = MockLocalBackend()
        local_critic = LocalCritic(backend=backend)

        selector = CostAwareCriticSelector(
            local_critic=local_critic,
            strategy=SelectionStrategy(
                complexity_threshold_local=0.1,  # Lower threshold
            ),
        )

        # Medium complexity should prefer local
        critique, critic_type = selector.evaluate(
            prompt="Explain how machine learning algorithms work",
            response="Machine learning algorithms are... " * 50,
        )

        assert critic_type == CriticType.LOCAL

    def test_force_critic_type(self):
        backend = MockLocalBackend()
        local_critic = LocalCritic(backend=backend)

        selector = CostAwareCriticSelector(local_critic=local_critic)

        # Force local even for simple query
        critique, critic_type = selector.evaluate(
            prompt="Hi",
            response="Hello!",
            force_type=CriticType.LOCAL,
        )

        assert critic_type == CriticType.LOCAL

    def test_falls_back_when_local_unavailable(self):
        backend = MockLocalBackend(available=False)
        local_critic = LocalCritic(backend=backend)

        selector = CostAwareCriticSelector(
            local_critic=local_critic,
            strategy=SelectionStrategy(complexity_threshold_local=0.0),
        )

        critique, critic_type = selector.evaluate(
            prompt="Complex question about algorithms",
            response="Detailed technical response...",
        )

        # Should fall back to rules when local unavailable
        assert critic_type == CriticType.RULE_BASED

    def test_respects_budget_constraints(self):
        api_critic = Mock(spec=RuleBasedCritic)

        selector = CostAwareCriticSelector(
            api_critic=api_critic,
            strategy=SelectionStrategy(
                complexity_threshold_api=0.5,
                max_cost_per_eval=0.001,  # Very low budget
            ),
        )

        critique, critic_type = selector.evaluate(
            prompt="Very complex technical question",
            response="Detailed response " * 100,
        )

        # Should not use expensive API due to budget
        assert critic_type != CriticType.API

    def test_usage_stats_tracking(self):
        selector = CostAwareCriticSelector()

        # Run several evaluations
        for _ in range(5):
            selector.evaluate("test", "response")

        stats = selector.get_usage_stats()
        assert stats["rule_based"]["count"] == 5
        assert stats["rule_based"]["total_time_ms"] > 0

    def test_complexity_estimation(self):
        selector = CostAwareCriticSelector()

        # Simple
        simple = selector._estimate_complexity("Hi", "Hello!")
        assert simple < 0.3

        # Code content
        code = selector._estimate_complexity(
            "Write code",
            "```python\ndef foo():\n    return 42\n```",
        )
        assert code > simple

        # Long technical content
        technical = selector._estimate_complexity(
            "Explain algorithms",
            "The algorithm works by... " * 100 + "O(n log n) complexity",
        )
        assert technical > code


# =============================================================================
# SelectionStrategy Tests
# =============================================================================


class TestSelectionStrategy:
    """Tests for selection strategy configuration."""

    def test_defaults(self):
        strategy = SelectionStrategy()
        assert strategy.complexity_threshold_local == 0.3
        assert strategy.complexity_threshold_api == 0.7
        assert strategy.max_cost_per_eval == 0.05
        assert strategy.min_quality == 0.6

    def test_custom_thresholds(self):
        strategy = SelectionStrategy(
            complexity_threshold_local=0.2,
            complexity_threshold_api=0.8,
            max_cost_per_eval=0.10,
        )
        assert strategy.complexity_threshold_local == 0.2
        assert strategy.complexity_threshold_api == 0.8
        assert strategy.max_cost_per_eval == 0.10


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_ollama_critic(self):
        critic = create_ollama_critic(
            model="llama3.2:3b",
            host="http://localhost:11434",
        )
        assert isinstance(critic, LocalCritic)
        assert isinstance(critic.backend, OllamaBackend)
        assert critic.backend.model == "llama3.2:3b"

    def test_create_cost_aware_critic(self):
        selector = create_cost_aware_critic(local_model="phi3:mini")
        assert isinstance(selector, CostAwareCriticSelector)
        assert selector.local_critic is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestLocalCriticIntegration:
    """Integration tests for local critic with reflective loop."""

    def test_with_reflective_generator(self):
        from symbolu.agentic_framework.reflective_loop import ReflectiveGenerator
        from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

        backend = MockLocalBackend(responses=[
            '{"coherence": 0.9, "correctness": 0.9, "completeness": 0.9, "relevance": 0.9}'
        ])
        local_critic = LocalCritic(backend=backend)

        llm = SequentialMockAdapter(responses=["This is a test response."], loop=True)
        generator = ReflectiveGenerator(
            llm_client=llm,
            critic=local_critic,
            threshold_high=0.85,
        )

        result = generator.generate("Test prompt")

        assert result.final_output == "This is a test response."
        assert result.quality_score >= 0.85  # Should pass threshold
        assert result.revision_count == 0  # No revision needed

    def test_cost_aware_with_reflective_generator(self):
        from symbolu.agentic_framework.reflective_loop import ReflectiveGenerator
        from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

        # Create cost-aware selector that tracks usage
        backend = MockLocalBackend()
        local_critic = LocalCritic(backend=backend)
        selector = CostAwareCriticSelector(local_critic=local_critic)

        # The selector's evaluate returns (critique, type), but ReflectiveGenerator
        # expects just critique. We need a wrapper.
        class CostAwareCriticWrapper:
            def __init__(self, selector):
                self.selector = selector

            def evaluate(self, prompt, response, goal_state=None):
                critique, _ = self.selector.evaluate(prompt, response, goal_state)
                return critique

        llm = SequentialMockAdapter(responses=["Response one", "Response two"], loop=True)
        generator = ReflectiveGenerator(
            llm_client=llm,
            critic=CostAwareCriticWrapper(selector),
        )

        result = generator.generate("Test prompt")
        assert result.final_output is not None

        # Check that stats were tracked
        stats = selector.get_usage_stats()
        assert stats["rule_based"]["count"] > 0 or stats["local"]["count"] > 0
