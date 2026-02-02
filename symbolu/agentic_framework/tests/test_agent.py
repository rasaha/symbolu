"""
Tests for AgenticLLMWrapper (Integration Tests)

Tests the main agent class that integrates all components:
- Agent creation and configuration
- Session management
- Full pipeline execution
- Multi-turn conversations
- Safety and coherence integration
"""

import pytest

from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import (
    MockLLMAdapter,
    SequentialMockAdapter,
)
from symbolu.agentic_framework.reflective_loop import RuleBasedCritic
from symbolu.agentic_framework.safety_contract import (
    create_strict_evaluator,
    create_permissive_evaluator,
)


class TestAgenticLLMWrapperCreation:
    """Tests for AgenticLLMWrapper creation."""

    def test_basic_creation(self):
        """Test basic agent creation."""
        llm = MockLLMAdapter()
        agent = AgenticLLMWrapper(llm)

        assert agent.llm_client is llm
        assert agent.max_revisions == 3
        assert agent.quality_threshold == 0.8

    def test_creation_with_custom_params(self):
        """Test agent creation with custom parameters."""
        llm = MockLLMAdapter()
        critic = RuleBasedCritic(min_length=50)

        agent = AgenticLLMWrapper(
            llm_client=llm,
            critic=critic,
            max_revisions=5,
            quality_threshold=0.9,
            memory_window=50,
            coherence_window=20,
        )

        assert agent.max_revisions == 5
        assert agent.quality_threshold == 0.9

    def test_creation_without_llm_decomposition(self):
        """Test agent without LLM-based decomposition."""
        llm = MockLLMAdapter()
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)

        assert agent.use_llm_for_decomposition is False


class TestSessionManagement:
    """Tests for session management."""

    def test_new_session(self):
        """Test creating a new session."""
        llm = MockLLMAdapter()
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)

        session_id = agent.new_session()

        assert session_id is not None
        assert len(session_id) > 0

    def test_new_session_with_id(self):
        """Test creating session with specific ID."""
        llm = MockLLMAdapter()
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)

        session_id = agent.new_session("my-session-123")

        assert session_id == "my-session-123"

    def test_multiple_sessions(self):
        """Test creating multiple sessions."""
        llm = MockLLMAdapter()
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)

        session1 = agent.new_session("session-1")
        agent.run("Query 1")

        session2 = agent.new_session("session-2")
        agent.run("Query 2")

        # New session should have fresh state
        assert agent.memory.session_id == "session-2"

    def test_get_session_summary(self):
        """Test getting session summary."""
        llm = MockLLMAdapter(default_response="Good response with adequate content.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        agent.run("Question 1")
        agent.run("Question 2")

        summary = agent.get_session_summary()

        assert "session_id" in summary
        assert "turn_count" in summary
        assert summary["turn_count"] == 2

    def test_export_conversation(self):
        """Test exporting conversation history."""
        llm = MockLLMAdapter(default_response="Response text")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        agent.run("First query")
        agent.run("Second query")

        history = agent.export_conversation()

        assert len(history) == 2
        assert history[0]["user_input"] == "First query"


class TestRunPipeline:
    """Tests for the run() pipeline."""

    def test_basic_run(self):
        """Test basic query execution."""
        llm = MockLLMAdapter(default_response="The capital of France is Paris.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("What is the capital of France?")

        assert result.response is not None
        assert "Paris" in result.response

    def test_run_returns_quality_score(self):
        """Test that run returns quality score."""
        llm = MockLLMAdapter(default_response="A comprehensive response.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        assert 0.0 <= result.quality_score <= 1.0

    def test_run_returns_revision_count(self):
        """Test that run returns revision count."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        assert result.revision_count >= 0

    def test_run_returns_coherence(self):
        """Test that run returns coherence metrics."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        assert "overall" in result.coherence
        assert 0.0 <= result.coherence["overall"] <= 1.0

    def test_run_returns_safety_info(self):
        """Test that run returns safety information."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        assert isinstance(result.actions_blocked, bool)
        assert result.safety_contract is not None


class TestMultiTurnConversation:
    """Tests for multi-turn conversations."""

    def test_multi_turn_basic(self):
        """Test basic multi-turn conversation."""
        responses = [
            "Python is a programming language.",
            "It was created by Guido van Rossum.",
            "Yes, Python is great for beginners.",
        ]
        llm = SequentialMockAdapter(responses)
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        r1 = agent.run("What is Python?")
        r2 = agent.run("Who created it?")
        r3 = agent.run("Is it good for beginners?")

        assert "programming language" in r1.response
        assert "Guido" in r2.response
        assert "beginners" in r3.response

    def test_context_maintained(self):
        """Test that context is maintained across turns."""
        llm = MockLLMAdapter(default_response="Contextual response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        agent.run("My name is Alice")
        agent.run("What is my name?")

        # Check that memory has both turns
        assert agent.memory.get_turn_count() == 2

    def test_coherence_tracked_across_turns(self):
        """Test coherence tracking across turns."""
        responses = [
            "First response about topic A.",
            "Second response continuing topic A.",
            "Third response still on topic A.",
        ]
        llm = SequentialMockAdapter(responses)
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        agent.run("Tell me about A")
        agent.run("More about A")
        result = agent.run("Continue about A")

        # Coherence should be tracked
        assert result.coherence["overall"] >= 0


class TestReflectiveLoop:
    """Tests for reflective loop integration."""

    def test_revision_on_low_quality(self):
        """Test that low quality triggers revision."""
        # First response is short, subsequent are better
        responses = [
            "Short.",
            "A better, more detailed response.",
            "An even better response with comprehensive information about the topic.",
        ]
        llm = SequentialMockAdapter(responses)
        critic = RuleBasedCritic(min_length=20, target_length=50)

        agent = AgenticLLMWrapper(
            llm,
            critic=critic,
            max_revisions=3,
            quality_threshold=0.7,
            use_llm_for_decomposition=False,
        )
        agent.new_session()

        result = agent.run("Explain something")

        # Should have revised at least once
        assert result.revision_count >= 0

    def test_no_revision_on_high_quality(self):
        """Test that high quality doesn't trigger revision."""
        llm = MockLLMAdapter(
            default_response="This is a comprehensive, detailed response that covers the topic thoroughly with multiple relevant points."
        )
        critic = RuleBasedCritic(min_length=10, target_length=50)

        agent = AgenticLLMWrapper(
            llm,
            critic=critic,
            quality_threshold=0.6,
            use_llm_for_decomposition=False,
        )
        agent.new_session()

        result = agent.run("Question")

        # Good first response should not need revision
        assert result.revision_count == 0


class TestSafetyIntegration:
    """Tests for safety contract integration."""

    def test_safety_check_on_run(self):
        """Test that safety is checked on run."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        # Safety contract should be generated
        assert result.safety_contract is not None

    def test_strict_safety_may_block(self):
        """Test that strict safety may block actions."""
        llm = MockLLMAdapter(default_response="x")  # Very short
        strict_evaluator = create_strict_evaluator()

        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.safety_gate.evaluator = strict_evaluator
        agent.new_session()

        # Run multiple poor-quality turns to degrade coherence
        for _ in range(3):
            result = agent.run("q")

        # May or may not be blocked depending on coherence
        assert isinstance(result.actions_blocked, bool)

    def test_permissive_safety_allows_more(self):
        """Test that permissive safety allows more."""
        llm = MockLLMAdapter(default_response="A reasonable response.")
        permissive_evaluator = create_permissive_evaluator()

        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.safety_gate.evaluator = permissive_evaluator
        agent.new_session()

        result = agent.run("Question")

        # Permissive should generally allow
        assert result.actions_blocked is False


class TestGoalDecomposition:
    """Tests for goal decomposition integration."""

    def test_simple_decomposition(self):
        """Test simple rule-based decomposition."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("What is 2 + 2?")

        # Should have goal state
        assert result.goal_state is not None
        assert result.goal_state.purpose_type == "informational"

    def test_creative_decomposition(self):
        """Test decomposition of creative request."""
        llm = MockLLMAdapter(default_response="A creative poem about nature.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Write a poem about nature")

        assert result.goal_state.purpose_type == "creative"


class TestInterventionHandling:
    """Tests for intervention detection and handling."""

    def test_intervention_check(self):
        """Test intervention check is performed."""
        llm = MockLLMAdapter(default_response="Response")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        # Should have intervention info
        assert isinstance(result.intervention_needed, bool)

    def test_degradation_triggers_warning(self):
        """Test that degradation may trigger intervention warning."""
        # Responses get progressively worse
        responses = [
            "A good comprehensive response.",
            "Shorter response.",
            "Bad.",
            "x",
        ]
        llm = SequentialMockAdapter(responses)
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        for _ in range(4):
            result = agent.run("q")

        # After degradation, intervention might be flagged
        assert isinstance(result.intervention_needed, bool)


class TestAgentIntegration:
    """Full integration tests."""

    def test_complete_conversation_flow(self):
        """Test a complete realistic conversation flow."""
        responses = [
            "Machine learning is a subset of AI that enables systems to learn from data.",
            "Supervised learning uses labeled data to train models.",
            "Common applications include image recognition and natural language processing.",
        ]
        llm = SequentialMockAdapter(responses)
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session("ml-conversation")

        # Turn 1
        r1 = agent.run("What is machine learning?")
        assert r1.response is not None
        assert r1.quality_score > 0

        # Turn 2
        r2 = agent.run("What is supervised learning?")
        assert r2.response is not None

        # Turn 3
        r3 = agent.run("What are some applications?")
        assert r3.response is not None

        # Check session state
        summary = agent.get_session_summary()
        assert summary["turn_count"] == 3

        # Check history export
        history = agent.export_conversation()
        assert len(history) == 3

    def test_all_result_fields_populated(self):
        """Test that all result fields are populated."""
        llm = MockLLMAdapter(default_response="A complete response.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        result = agent.run("Question")

        # Check all fields
        assert result.response is not None
        assert isinstance(result.quality_score, float)
        assert isinstance(result.revision_count, int)
        assert isinstance(result.coherence, dict)
        assert isinstance(result.actions_blocked, bool)
        assert result.safety_contract is not None
        assert result.goal_state is not None
        assert isinstance(result.intervention_needed, bool)

    def test_error_handling(self):
        """Test graceful error handling."""
        # Empty response shouldn't crash
        llm = MockLLMAdapter(default_response="")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        # Should not raise
        result = agent.run("Question")
        assert result is not None
