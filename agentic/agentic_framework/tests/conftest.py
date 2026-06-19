"""
Pytest Configuration for Agentic Framework Tests

Provides fixtures and configuration for the test suite.
"""

import asyncio

import pytest

from agentic.agentic_framework.llm_adapters import (
    MockLLMAdapter,
    SequentialMockAdapter,
    MockEmbeddingAdapter,
)
from agentic.agentic_framework.reflective_loop import RuleBasedCritic


# ---------------------------------------------------------------------------
# Minimal async-test runner (scoped to this directory).
#
# Several gateway-integration tests here use ``@pytest.mark.asyncio`` async test
# functions. The repo does not depend on pytest-asyncio, so without a runner those
# tests error with "async def functions are not natively supported" (a test-infra
# failure, not a product failure). This tiny hook runs coroutine test functions in a
# fresh event loop — no new dependency — so the domain-policy / shadow-AI integration
# tests (and the trust parity scenarios that rely on them) run reliably.
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: run an async test in a fresh event loop (local runner)")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    testfn = pyfuncitem.obj
    if asyncio.iscoroutinefunction(testfn):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            kwargs = {name: pyfuncitem.funcargs[name]
                      for name in pyfuncitem._fixtureinfo.argnames}
            loop.run_until_complete(testfn(**kwargs))
        finally:
            loop.close()
            # Leave a FRESH, open loop installed (not None): sibling tests use the
            # `asyncio.get_event_loop()` pattern, which on Python 3.11 raises once
            # set_event_loop() has been called with None. Restoring a usable loop keeps
            # those run_async helpers working — i.e., this hook must not pollute them.
            asyncio.set_event_loop(asyncio.new_event_loop())
        return True
    return None


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
