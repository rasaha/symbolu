#!/usr/bin/env python3
"""
Agentic LLM Framework - Validation Script

This script validates all components of the Agentic LLM Framework.
It can be run without any API keys using mock adapters.

Usage:
    python -m symbolu.agentic_framework.validate           # Run all validations
    python -m symbolu.agentic_framework.validate --quick   # Quick validation
    python -m symbolu.agentic_framework.validate --verbose # Verbose output

Alternatively, run pytest directly:
    pytest symbolu/agentic_framework/tests/ -v
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Tuple, List


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_result(name: str, passed: bool, message: str = "") -> None:
    """Print a test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if message and not passed:
        print(f"         {message}")


def validate_imports() -> Tuple[bool, str]:
    """Validate all imports work correctly."""
    try:
        from symbolu.agentic_framework import AgenticLLMWrapper
        from symbolu.agentic_framework.goal_decomposition import (
            GoalState, ActionItem, decompose_goal_simple
        )
        from symbolu.agentic_framework.memory_store import MemoryStore, TurnSnapshot
        from symbolu.agentic_framework.reflective_loop import (
            RuleBasedCritic, ReflectiveGenerator, QualityCritique
        )
        from symbolu.agentic_framework.coherence_tracker import (
            CoherenceEngine, CoherenceMetrics
        )
        from symbolu.agentic_framework.safety_contract import (
            SafetyGate, SafetyContract, create_default_evaluator
        )
        from symbolu.agentic_framework.llm_adapters import (
            MockLLMAdapter, SequentialMockAdapter, MockEmbeddingAdapter
        )
        return True, ""
    except ImportError as e:
        return False, str(e)


def validate_goal_decomposition() -> Tuple[bool, str]:
    """Validate goal decomposition component."""
    try:
        from symbolu.agentic_framework.goal_decomposition import (
            GoalState, ActionItem, decompose_goal_simple
        )

        # Test ActionItem
        action = ActionItem("a0", "Test action", "generate")
        assert action.status == "pending"

        # Test GoalState
        goal = GoalState(
            purpose="Test purpose",
            purpose_type="informational",
            reasoning_strategy="Direct response",
            actions=[action],
        )
        assert goal.purpose == "Test purpose"
        assert not goal.is_complete()

        # Test simple decomposition
        goal = decompose_goal_simple("What is the capital of France?")
        assert goal.purpose_type == "informational"
        assert goal.agency_level == "INFORM"

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_memory_store() -> Tuple[bool, str]:
    """Validate memory store component."""
    try:
        from symbolu.agentic_framework.memory_store import (
            MemoryStore, TurnSnapshot, AgentMemory, create_memory, create_turn_snapshot
        )

        # Create memory using factory function
        memory = create_memory("test-session")
        store = MemoryStore()

        # Add turns using factory functions
        turn1 = create_turn_snapshot(1, "Q1", "A1", quality_score=0.8)
        turn2 = create_turn_snapshot(2, "Q2", "A2", quality_score=0.9)

        memory = store.append_turn(memory, turn1)
        memory = store.append_turn(memory, turn2)

        assert memory.get_turn_count() == 2
        assert abs(memory.get_average_quality() - 0.85) < 0.01

        # Test summary retrieval
        summary = store.get_summary_for_llm(memory, max_turns=1)
        assert "Q2" in summary or "A2" in summary

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_reflective_loop() -> Tuple[bool, str]:
    """Validate reflective loop component."""
    try:
        from symbolu.agentic_framework.reflective_loop import (
            RuleBasedCritic, ReflectiveGenerator, QualityCritique
        )
        from symbolu.agentic_framework.llm_adapters import MockLLMAdapter

        # Test critic (uses evaluate() method, not critique())
        critic = RuleBasedCritic(min_length=10, target_length=50)
        critique = critic.evaluate(
            "Test prompt",
            "This is a test response with some content.",
        )
        assert 0 <= critique.overall_score <= 1

        # Test generator
        llm = MockLLMAdapter(default_response="A good response with content.")
        generator = ReflectiveGenerator(llm, critic, threshold_high=0.5)
        result = generator.generate("Test query")
        assert result.final_output is not None

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_coherence_tracker() -> Tuple[bool, str]:
    """Validate coherence tracker component."""
    try:
        from symbolu.agentic_framework.coherence_tracker import (
            CoherenceEngine, CoherenceMetrics, create_initial_state
        )
        from symbolu.agentic_framework.memory_store import create_turn_snapshot

        engine = CoherenceEngine(window=10)

        # Create initial state
        state = create_initial_state("test")

        # Update with some turns (uses functional pattern)
        turn1 = create_turn_snapshot(1, "Prompt 1", "Response 1", quality_score=0.8)
        turn2 = create_turn_snapshot(2, "Prompt 2", "Response 2", quality_score=0.85)

        state = engine.update(state, turn1)
        state = engine.update(state, turn2)

        assert state.current_turn == 2
        assert state.current_metrics is not None
        assert 0 <= state.current_metrics.overall_coherence <= 1

        # Test intervention check
        should_intervene, reason = engine.should_intervene(state)
        assert isinstance(should_intervene, bool)

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_safety_contract() -> Tuple[bool, str]:
    """Validate safety contract component."""
    try:
        from symbolu.agentic_framework.safety_contract import (
            SafetyGate, SafetyContract, create_default_evaluator
        )
        from symbolu.agentic_framework.coherence_tracker import (
            create_initial_state, CoherenceMetrics
        )
        from symbolu.agentic_framework.goal_decomposition import GoalState

        gate = SafetyGate()

        # Test with good coherence state
        good_state = create_initial_state("test-good")
        # Manually set good metrics
        good_state.current_metrics = CoherenceMetrics(
            internal_consistency=0.9,
            prediction_reversal_risk=0.1,
            volatility_index=0.1,
            goal_alignment=0.85,
            factual_alignment=0.9,
            identity_stability=0.95,
            drift_magnitude=0.0,
            drift_direction="stable",
            overall_coherence=0.9,
        )
        # Need goal state with FULL or CONFIRM agency
        goal_state = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Direct",
            agency_level="FULL",
        )

        contract, allowed = gate.check(good_state, goal_state)
        assert contract.eligible is True

        # Test with poor coherence state
        poor_state = create_initial_state("test-poor")
        poor_state.current_metrics = CoherenceMetrics(
            internal_consistency=0.2,
            prediction_reversal_risk=0.9,
            volatility_index=0.8,
            goal_alignment=0.2,
            factual_alignment=0.3,
            identity_stability=0.3,
            drift_magnitude=0.5,
            drift_direction="degrading",
            overall_coherence=0.3,
        )

        contract, allowed = gate.check(poor_state, goal_state)
        assert contract.eligible is False

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_llm_adapters() -> Tuple[bool, str]:
    """Validate LLM adapters."""
    try:
        from symbolu.agentic_framework.llm_adapters import (
            MockLLMAdapter, SequentialMockAdapter, MockEmbeddingAdapter
        )

        # Test MockLLMAdapter
        mock = MockLLMAdapter(default_response="Hello")
        assert mock.call("test") == "Hello"

        # Test SequentialMockAdapter
        seq = SequentialMockAdapter(["A", "B", "C"])
        assert seq.call("1") == "A"
        assert seq.call("2") == "B"

        # Test MockEmbeddingAdapter
        emb = MockEmbeddingAdapter(dimension=64)
        embedding = emb.embed("test")
        assert len(embedding) == 64

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_agent_integration() -> Tuple[bool, str]:
    """Validate full agent integration."""
    try:
        from symbolu.agentic_framework import AgenticLLMWrapper
        from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

        # Create agent
        llm = SequentialMockAdapter([
            "Python is a programming language.",
            "It was created by Guido van Rossum.",
            "Yes, Python is great for beginners.",
        ])
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session("integration-test")

        # Run conversation
        r1 = agent.run("What is Python?")
        assert r1.response is not None
        assert r1.quality_score >= 0

        r2 = agent.run("Who created it?")
        assert r2.response is not None

        r3 = agent.run("Is it good for beginners?")
        assert r3.response is not None

        # Check session
        summary = agent.get_session_summary()
        assert summary["turn_count"] == 3

        # Check history
        history = agent.export_conversation()
        assert len(history) == 3

        return True, ""
    except Exception as e:
        return False, str(e)


def validate_multi_turn_coherence() -> Tuple[bool, str]:
    """Validate coherence tracking across multiple turns."""
    try:
        from symbolu.agentic_framework import AgenticLLMWrapper
        from symbolu.agentic_framework.llm_adapters import SequentialMockAdapter

        llm = SequentialMockAdapter([
            "Machine learning is a subset of AI.",
            "Deep learning uses neural networks.",
            "TensorFlow and PyTorch are popular frameworks.",
        ])
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()

        results = []
        for _ in range(3):
            result = agent.run("Question about ML")
            results.append(result)

        # All should have coherence metrics
        for result in results:
            assert "overall" in result.coherence
            assert result.coherence["overall"] >= 0

        return True, ""
    except Exception as e:
        return False, str(e)


def run_validation(verbose: bool = False) -> Tuple[int, int, List[str]]:
    """
    Run all validation checks.

    Returns:
        Tuple of (passed_count, failed_count, failed_names)
    """
    validations = [
        ("Imports", validate_imports),
        ("Goal Decomposition", validate_goal_decomposition),
        ("Memory Store", validate_memory_store),
        ("Reflective Loop", validate_reflective_loop),
        ("Coherence Tracker", validate_coherence_tracker),
        ("Safety Contract", validate_safety_contract),
        ("LLM Adapters", validate_llm_adapters),
        ("Agent Integration", validate_agent_integration),
        ("Multi-Turn Coherence", validate_multi_turn_coherence),
    ]

    passed = 0
    failed = 0
    failed_names = []

    print_header("AGENTIC LLM FRAMEWORK VALIDATION")
    print(f"\nRunning {len(validations)} validation checks...\n")

    for name, validator in validations:
        start = time.time()
        success, message = validator()
        elapsed = time.time() - start

        if success:
            passed += 1
            print_result(name, True)
            if verbose:
                print(f"         ({elapsed:.3f}s)")
        else:
            failed += 1
            failed_names.append(name)
            print_result(name, False, message)

    return passed, failed, failed_names


def run_quick_validation() -> bool:
    """Run a quick validation of core functionality."""
    print_header("QUICK VALIDATION")

    try:
        # Import check
        from symbolu.agentic_framework import AgenticLLMWrapper
        from symbolu.agentic_framework.llm_adapters import MockLLMAdapter
        print("  ✓ Imports successful")

        # Quick run
        llm = MockLLMAdapter(default_response="Test response.")
        agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
        agent.new_session()
        result = agent.run("Test query")

        assert result.response is not None
        print("  ✓ Agent run successful")
        print("  ✓ All quick checks passed!")
        return True
    except Exception as e:
        print(f"  ✗ Quick validation failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate the Agentic LLM Framework"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick validation only"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--pytest", "-p",
        action="store_true",
        help="Run full pytest suite"
    )

    args = parser.parse_args()

    if args.pytest:
        # Run pytest
        import subprocess
        result = subprocess.run(
            ["pytest", "symbolu/agentic_framework/tests/", "-v"],
            cwd="/home/user/symbolu"
        )
        sys.exit(result.returncode)

    if args.quick:
        success = run_quick_validation()
        sys.exit(0 if success else 1)

    # Full validation
    passed, failed, failed_names = run_validation(verbose=args.verbose)

    # Summary
    print_header("SUMMARY")
    print(f"\n  Total:  {passed + failed}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    if failed > 0:
        print(f"\n  Failed validations:")
        for name in failed_names:
            print(f"    - {name}")
        print()
        sys.exit(1)
    else:
        print("\n  All validations passed! ✓")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
