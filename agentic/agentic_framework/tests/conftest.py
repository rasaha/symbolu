"""
Pytest Configuration for Agentic Framework Tests

Provides fixtures and configuration for the test suite.
"""

import pytest

from agentic.agentic_framework.llm_adapters import (
    MockLLMAdapter,
    SequentialMockAdapter,
    MockEmbeddingAdapter,
)
from agentic.agentic_framework.reflective_loop import RuleBasedCritic


@pytest.fixture
def mock_llm():
    """Provide a basic mock LLM adapter."""
    return MockLLMAdapter(
        default_response="This is a mock response with sufficient content."
    )


@pytest.fixture
def sequential_llm():
    """Provide a sequential mock LLM adapter."""
    return SequentialMockAdapter([
        "First response",
        "Second response",
        "Third response",
    ])


@pytest.fixture
def mock_embedder():
    """Provide a mock embedding adapter."""
    return MockEmbeddingAdapter(dimension=128)


@pytest.fixture
def rule_critic():
    """Provide a rule-based critic."""
    return RuleBasedCritic(min_length=10, target_length=100)


@pytest.fixture
def conversation_llm():
    """Provide an LLM for conversation testing."""
    return SequentialMockAdapter([
        "Hello! I'm happy to help you today.",
        "Python is a high-level programming language known for its readability.",
        "Yes, Python is excellent for beginners due to its simple syntax.",
        "You can learn Python through online tutorials, courses, or books.",
        "Some popular Python applications include web development, data science, and automation.",
    ])
