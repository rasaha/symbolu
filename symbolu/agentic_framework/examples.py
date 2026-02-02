"""
Agentic LLM Framework - Example Usage

This module provides comprehensive examples of using the Agentic LLM Framework
with different LLM providers and configurations.

Examples:
1. Basic usage with OpenAI
2. Basic usage with Claude
3. Basic usage with Gemini
4. Custom critic configuration
5. Multi-turn conversation
6. Handling safety blocks
7. Session management
8. Memory and coherence inspection
"""

from __future__ import annotations

from typing import Optional


# =============================================================================
# Example 1: Basic Usage with OpenAI
# =============================================================================

def example_openai_basic():
    """
    Basic example using OpenAI GPT-4.

    Prerequisites:
        pip install openai
        export OPENAI_API_KEY="sk-..."
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import OpenAIAdapter

    # Create OpenAI adapter
    llm = OpenAIAdapter(
        model="gpt-4",
        temperature=0.7,
        max_tokens=1024,
    )

    # Create agent
    agent = AgenticLLMWrapper(llm)

    # Start new session
    session_id = agent.new_session()
    print(f"Started session: {session_id}")

    # Run a query
    result = agent.run("What is the capital of France?")

    # Print results
    print(f"\nResponse: {result.response}")
    print(f"Quality Score: {result.quality_score:.2f}")
    print(f"Revision Count: {result.revision_count}")
    print(f"Coherence: {result.coherence['overall']:.2f}")
    print(f"Safety Eligible: {not result.actions_blocked}")


# =============================================================================
# Example 2: Basic Usage with Claude
# =============================================================================

def example_claude_basic():
    """
    Basic example using Anthropic Claude.

    Prerequisites:
        pip install anthropic
        export ANTHROPIC_API_KEY="sk-ant-..."
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import AnthropicAdapter

    # Create Claude adapter
    llm = AnthropicAdapter(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
    )

    # Create agent
    agent = AgenticLLMWrapper(llm)
    agent.new_session()

    # Run a query
    result = agent.run("Explain quantum computing in simple terms.")

    print(f"Response: {result.response[:200]}...")
    print(f"Quality: {result.quality_score:.2f}")


# =============================================================================
# Example 3: Basic Usage with Gemini
# =============================================================================

def example_gemini_basic():
    """
    Basic example using Google Gemini.

    Prerequisites:
        pip install google-generativeai
        export GOOGLE_API_KEY="..."
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import GeminiAdapter

    # Create Gemini adapter
    llm = GeminiAdapter(model="gemini-pro")

    # Create agent
    agent = AgenticLLMWrapper(llm)
    agent.new_session()

    # Run a query
    result = agent.run("Write a haiku about programming.")

    print(f"Response: {result.response}")


# =============================================================================
# Example 4: Custom Critic Configuration
# =============================================================================

def example_custom_critic():
    """
    Example with custom quality critic configuration.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.reflective_loop import (
        RuleBasedCritic,
        LLMBasedCritic,
        HybridCritic,
    )
    from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

    # Mock LLM for demonstration
    llm = MockLLMAdapter(
        responses={
            "capital": "The capital of France is Paris.",
            "explain": "Quantum computing uses quantum mechanics to process information.",
        }
    )

    # Option 1: Rule-based critic (fast, no API calls)
    rule_critic = RuleBasedCritic(
        min_length=30,
        target_length=300,
    )

    agent_rule = AgenticLLMWrapper(
        llm,
        critic=rule_critic,
        max_revisions=2,
        quality_threshold=0.75,
    )

    # Option 2: LLM-based critic (uses another LLM call)
    llm_critic = LLMBasedCritic(llm)

    agent_llm = AgenticLLMWrapper(
        llm,
        critic=llm_critic,
        max_revisions=3,
    )

    # Option 3: Hybrid critic (rule-based first, LLM if needed)
    hybrid_critic = HybridCritic(llm, use_llm_threshold=0.8)

    agent_hybrid = AgenticLLMWrapper(
        llm,
        critic=hybrid_critic,
    )

    # Test each
    for name, agent in [("Rule", agent_rule), ("Hybrid", agent_hybrid)]:
        agent.new_session()
        result = agent.run("What is the capital of France?")
        print(f"{name} Critic - Quality: {result.quality_score:.2f}, Revisions: {result.revision_count}")


# =============================================================================
# Example 5: Multi-Turn Conversation
# =============================================================================

def example_multi_turn():
    """
    Example of multi-turn conversation with memory.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

    # Mock LLM that returns different responses
    llm = SequentialMockAdapter([
        "The capital of France is Paris, known as the City of Light.",
        "Paris has approximately 2.1 million people in the city proper, and about 12 million in the metropolitan area.",
        "The Eiffel Tower, completed in 1889, is 330 meters tall and was the world's tallest structure for 41 years.",
    ])

    # Create agent
    agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
    agent.new_session()

    # Multi-turn conversation
    questions = [
        "What is the capital of France?",
        "What's its population?",
        "Tell me about the Eiffel Tower.",
    ]

    for i, question in enumerate(questions):
        print(f"\n--- Turn {i + 1} ---")
        print(f"User: {question}")

        result = agent.run(question)

        print(f"Assistant: {result.response}")
        print(f"Quality: {result.quality_score:.2f}")
        print(f"Coherence: {result.coherence['overall']:.2f}")
        print(f"Goal Alignment: {result.coherence['goal_alignment']:.2f}")

    # Print session summary
    print("\n--- Session Summary ---")
    summary = agent.get_session_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")


# =============================================================================
# Example 6: Handling Safety Blocks
# =============================================================================

def example_safety_handling():
    """
    Example of handling safety contract blocks.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.safety_contract import (
        SafetyContractEvaluator,
        create_strict_evaluator,
    )
    from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

    # Mock LLM
    llm = MockLLMAdapter(default_response="I can help with that.")

    # Create agent with strict safety
    strict_evaluator = create_strict_evaluator()
    agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
    agent.safety_gate.evaluator = strict_evaluator

    agent.new_session()

    # Run query
    result = agent.run("Help me with something.")

    if result.actions_blocked:
        print("Actions were blocked!")
        print(f"Reasons: {result.blocking_reasons}")
        print(f"\nResponse (still provided): {result.response}")

        # Check specific metrics
        contract = result.safety_contract
        print(f"\nContract details:")
        print(f"  Internal consistency: {contract.internal_consistency:.2f}")
        print(f"  Goal alignment: {contract.goal_alignment:.2f}")
        print(f"  Reversal risk: {contract.prediction_reversal_risk:.2f}")
        print(f"  Identity stability: {contract.identity_stability:.2f}")
    else:
        print("Actions allowed!")
        print(f"Executed: {result.actions_executed}")


# =============================================================================
# Example 7: Session Management
# =============================================================================

def example_session_management():
    """
    Example of managing multiple sessions.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

    llm = MockLLMAdapter(default_response="Hello!")

    agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)

    # Session 1
    session1 = agent.new_session("session-001")
    agent.run("First message in session 1")
    agent.run("Second message in session 1")

    summary1 = agent.get_session_summary()
    print(f"Session 1 ({session1}): {summary1['turn_count']} turns")

    # Session 2 (new session)
    session2 = agent.new_session("session-002")
    agent.run("First message in session 2")

    summary2 = agent.get_session_summary()
    print(f"Session 2 ({session2}): {summary2['turn_count']} turns")

    # Export conversation
    history = agent.export_conversation()
    print(f"\nSession 2 history: {len(history)} turns")


# =============================================================================
# Example 8: Memory and Coherence Inspection
# =============================================================================

def example_inspection():
    """
    Example of inspecting memory and coherence state.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

    llm = SequentialMockAdapter([
        "Python is a high-level programming language.",
        "Yes, Python uses dynamic typing.",
        "Actually, Python can be used for web development too.",
    ])

    agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
    agent.new_session()

    # Run some queries
    agent.run("What is Python?")
    agent.run("Is Python dynamically typed?")
    agent.run("Can Python be used for web development?")

    # Inspect memory
    print("--- Memory Inspection ---")
    memory = agent.memory
    print(f"Session ID: {memory.session_id}")
    print(f"Turn count: {memory.get_turn_count()}")
    print(f"Average quality: {memory.get_average_quality():.2f}")

    print("\nRecent turns:")
    for turn in memory.get_recent_turns(n=3):
        print(f"  Turn {turn.turn_id}: {turn.user_input[:30]}...")

    # Inspect coherence
    print("\n--- Coherence Inspection ---")
    coherence = agent.coherence_state
    print(f"Current turn: {coherence.current_turn}")
    print(f"Overall coherence: {coherence.current_metrics.overall_coherence:.2f}")
    print(f"Internal consistency: {coherence.current_metrics.internal_consistency:.2f}")
    print(f"Goal alignment: {coherence.current_metrics.goal_alignment:.2f}")
    print(f"Drift direction: {coherence.current_metrics.drift_direction}")

    # Check intervention need
    engine = agent.coherence_engine
    should_intervene, reason = engine.should_intervene(coherence)
    print(f"\nIntervention needed: {should_intervene}")
    print(f"Reason: {reason}")


# =============================================================================
# Example 9: Production-Ready Configuration
# =============================================================================

def example_production_config():
    """
    Example of production-ready configuration.
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.reflective_loop import HybridCritic
    from symbolu.agentic_framework.safety_contract import create_default_evaluator
    from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

    # In production, use real LLM:
    # from symbolu.agentic_framework.llm_adapters import OpenAIAdapter
    # llm = OpenAIAdapter(model="gpt-4")

    llm = MockLLMAdapter(default_response="Production response.")

    # Production configuration
    agent = AgenticLLMWrapper(
        llm_client=llm,
        embedding_model=None,  # Add OpenAIEmbeddingAdapter for better retrieval
        critic=None,  # Use default RuleBasedCritic
        max_revisions=3,
        quality_threshold=0.85,
        memory_window=50,  # Longer memory
        coherence_window=20,  # More history for coherence
        use_llm_for_decomposition=True,
    )

    # Start session
    agent.new_session()

    # Process with full error handling
    try:
        result = agent.run("User query here")

        # Log metrics
        print(f"Response generated successfully")
        print(f"  Quality: {result.quality_score:.2f}")
        print(f"  Revisions: {result.revision_count}")
        print(f"  Coherence: {result.coherence['overall']:.2f}")
        print(f"  Safety: {'Approved' if not result.actions_blocked else 'Blocked'}")

        # Check for degradation
        if result.intervention_needed:
            print(f"WARNING: Intervention needed - {result.intervention_reason}")

    except Exception as e:
        print(f"Error processing query: {e}")


# =============================================================================
# Example 10: Using Different LLM for Critic
# =============================================================================

def example_separate_critic_llm():
    """
    Example using a different (cheaper/faster) LLM for the critic.

    This pattern is common in production:
    - Use GPT-4 for generation (quality)
    - Use GPT-3.5 for critic (cost savings)
    """
    from symbolu.agentic_framework import AgenticLLMWrapper
    from symbolu.agentic_framework.reflective_loop import LLMBasedCritic
    from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

    # Main LLM (expensive, high quality)
    main_llm = MockLLMAdapter(
        default_response="High-quality response from main LLM."
    )

    # Critic LLM (cheaper, faster)
    critic_llm = MockLLMAdapter(
        responses={
            "evaluate": '{"coherence": 0.9, "correctness": 0.85, "completeness": 0.8, "relevance": 0.9, "issues": [], "suggestions": []}'
        }
    )

    # Create critic using cheaper LLM
    critic = LLMBasedCritic(critic_llm)

    # Create agent
    agent = AgenticLLMWrapper(
        llm_client=main_llm,
        critic=critic,
        use_llm_for_decomposition=False,
    )

    agent.new_session()
    result = agent.run("Generate something")

    print(f"Response: {result.response}")
    print(f"Quality (from cheap critic): {result.quality_score:.2f}")


# =============================================================================
# Run Examples
# =============================================================================

def run_all_examples():
    """Run all examples that work without API keys."""
    print("=" * 60)
    print("AGENTIC LLM FRAMEWORK - EXAMPLES")
    print("=" * 60)

    print("\n\n--- Example 4: Custom Critic ---")
    example_custom_critic()

    print("\n\n--- Example 5: Multi-Turn Conversation ---")
    example_multi_turn()

    print("\n\n--- Example 6: Safety Handling ---")
    example_safety_handling()

    print("\n\n--- Example 7: Session Management ---")
    example_session_management()

    print("\n\n--- Example 8: Inspection ---")
    example_inspection()

    print("\n\n--- Example 9: Production Config ---")
    example_production_config()

    print("\n\n--- Example 10: Separate Critic LLM ---")
    example_separate_critic_llm()

    print("\n\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_examples()
