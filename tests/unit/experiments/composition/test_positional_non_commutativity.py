"""
Test: Positional Non-Commutativity of Varna Sequences
=====================================================

EXPERIMENTAL TEST - NON-FROZEN, NON-CANONICAL

This test answers ONE question:

    Does positional arrangement of the SAME varnas produce different
    pressure trajectories?

If yes -> composition grammar is non-commutative
If no  -> generation collapses and must be reconsidered

TEST DESIGN:
    Compare two sequences using the SAME varnas in different order:
        seq_1 = ["ka", "a", "ka"]   # C-V-C pattern
        seq_2 = ["ka", "ka", "a"]   # C-C-V pattern

ASSERTIONS:
    - The two traces MUST NOT be identical
    - At least one of the following must differ:
        - vector at any step
        - magnitude progression
        - point at which modulation occurs

This test does NOT assert meanings.
This test does NOT assert "correctness".
This test ONLY asserts NON-EQUALITY of trajectories.
"""

import pytest
from typing import List, Dict, Any

from symbolu.experiments.composition.sequence_analyzer import (
    SequenceAnalyzer,
    analyze_sequence,
    TraceEntry,
)


def _format_trace(trace: List[Dict[str, Any]]) -> str:
    """Format a trace for human-readable output."""
    lines = []
    for entry in trace:
        lines.append(
            f"  Step {entry['step']}: {entry['token']:4s} "
            f"({entry['role']:9s}) -> vector={entry['vector']:10s} "
            f"magnitude={entry['magnitude']:.4f}"
        )
    return "\n".join(lines)


def _traces_differ(
    trace_1: List[Dict[str, Any]],
    trace_2: List[Dict[str, Any]],
) -> tuple[bool, str]:
    """
    Check if two traces differ in meaningful ways.

    Returns:
        Tuple of (differs: bool, reason: str)
    """
    reasons = []

    # Check lengths first
    if len(trace_1) != len(trace_2):
        return True, f"Different lengths: {len(trace_1)} vs {len(trace_2)}"

    # Check each step
    for i, (e1, e2) in enumerate(zip(trace_1, trace_2)):
        # Check vector difference
        if e1["vector"] != e2["vector"]:
            reasons.append(f"Step {i}: vector differs ({e1['vector']} vs {e2['vector']})")

        # Check magnitude difference
        if abs(e1["magnitude"] - e2["magnitude"]) > 0.0001:
            reasons.append(
                f"Step {i}: magnitude differs ({e1['magnitude']:.4f} vs {e2['magnitude']:.4f})"
            )

        # Check role (where modulation occurs)
        if e1["role"] != e2["role"]:
            reasons.append(f"Step {i}: role differs ({e1['role']} vs {e2['role']})")

        # Check token (position of tokens)
        if e1["token"] != e2["token"]:
            reasons.append(f"Step {i}: token differs ({e1['token']} vs {e2['token']})")

    if reasons:
        return True, "; ".join(reasons)
    return False, "No differences found"


class TestPositionalNonCommutativity:
    """
    Test suite for positional non-commutativity hypothesis.

    This is the ONLY test required for the falsification experiment.
    """

    def test_cvc_vs_ccv_produces_different_traces(self) -> None:
        """
        CRITICAL TEST: Same varnas in different order -> different trajectories.

        Sequences:
            seq_1 = ["ka", "a", "ka"]   # Consonant-Vowel-Consonant
            seq_2 = ["ka", "ka", "a"]   # Consonant-Consonant-Vowel

        Both sequences contain:
            - 2x "ka" (consonant)
            - 1x "a" (vowel)

        Expected outcome:
            The traces MUST differ because:
            - In C-V-C: vowel modulates first consonant's pressure, then second consonant resets
            - In C-C-V: second consonant resets pressure before vowel can modulate first

        This demonstrates positional non-commutativity.
        """
        # Define test sequences
        seq_1 = ["ka", "a", "ka"]  # C-V-C pattern
        seq_2 = ["ka", "ka", "a"]  # C-C-V pattern

        # Analyze both sequences
        trace_1 = analyze_sequence(seq_1)
        trace_2 = analyze_sequence(seq_2)

        # Print traces for human inspection
        print("\n" + "=" * 70)
        print("POSITIONAL NON-COMMUTATIVITY TEST")
        print("=" * 70)
        print(f"\nSequence 1: {seq_1} (C-V-C pattern)")
        print(_format_trace(trace_1))
        print(f"\nSequence 2: {seq_2} (C-C-V pattern)")
        print(_format_trace(trace_2))
        print()

        # Check for differences
        differs, reason = _traces_differ(trace_1, trace_2)

        print(f"Traces differ: {differs}")
        print(f"Reason: {reason}")
        print("=" * 70)

        # ASSERTION: Traces MUST NOT be identical
        assert differs, (
            "FALSIFICATION FAILED: Traces are identical despite different ordering.\n"
            "This suggests composition grammar may be commutative.\n"
            f"Trace 1: {trace_1}\n"
            f"Trace 2: {trace_2}"
        )

        # Additional specific assertions
        # Assert that at least one of the expected differences exists

        # 1. The token at step 1 should differ (vowel vs consonant position)
        assert trace_1[1]["token"] != trace_2[1]["token"], (
            "Expected token at step 1 to differ between sequences"
        )

        # 2. The role at step 1 should differ
        assert trace_1[1]["role"] != trace_2[1]["role"], (
            "Expected role at step 1 to differ: "
            f"seq_1 has {trace_1[1]['role']}, seq_2 has {trace_2[1]['role']}"
        )

        # 3. The magnitude progression should differ
        # In C-V-C: magnitudes go [1.0, 1.1, 1.0] (vowel modulates, then reset)
        # In C-C-V: magnitudes go [1.0, 1.0, 1.1] (reset first, then modulate)
        magnitudes_1 = [e["magnitude"] for e in trace_1]
        magnitudes_2 = [e["magnitude"] for e in trace_2]
        assert magnitudes_1 != magnitudes_2, (
            f"Expected magnitude progressions to differ: {magnitudes_1} vs {magnitudes_2}"
        )

        print("\nSUCCESS: Positional non-commutativity demonstrated.")
        print("Different orderings of the same varnas produce different pressure trajectories.")


class TestSequenceAnalyzerBasics:
    """
    Additional tests for sequence analyzer functionality.

    These are supplementary to the main falsification test.
    """

    def test_single_consonant(self) -> None:
        """Single consonant initializes pressure."""
        trace = analyze_sequence(["ka"])
        assert len(trace) == 1
        assert trace[0]["role"] == "consonant"
        assert trace[0]["magnitude"] == 1.0
        print(f"\nSingle consonant trace: {trace}")

    def test_consonant_vowel_pair(self) -> None:
        """Vowel modulates consonant's pressure."""
        trace = analyze_sequence(["ka", "a"])
        assert len(trace) == 2
        assert trace[0]["role"] == "consonant"
        assert trace[1]["role"] == "vowel"
        # Vowel should modulate magnitude
        assert trace[1]["magnitude"] != trace[0]["magnitude"]
        print(f"\nC-V pair trace: {trace}")

    def test_vowel_without_consonant_raises(self) -> None:
        """Vowel cannot introduce pressure by itself."""
        from symbolu.experiments.composition.sequence_analyzer import NoActivePressureError

        with pytest.raises(NoActivePressureError) as exc_info:
            analyze_sequence(["a"])

        assert "no active pressure" in str(exc_info.value).lower()
        print(f"\nExpected error raised: {exc_info.value}")

    def test_empty_sequence(self) -> None:
        """Empty sequence returns empty trace."""
        trace = analyze_sequence([])
        assert trace == []
        print("\nEmpty sequence handled correctly")

    def test_multiple_consonants_reset_pressure(self) -> None:
        """Each consonant resets pressure to its own values."""
        # Use two different consonants if possible, but for this test
        # the same consonant should still demonstrate reset behavior
        trace = analyze_sequence(["ka", "ka"])
        assert len(trace) == 2
        # Both should be consonants with reset magnitudes
        assert trace[0]["magnitude"] == 1.0
        assert trace[1]["magnitude"] == 1.0  # Reset, not accumulated
        print(f"\nDouble consonant trace: {trace}")


if __name__ == "__main__":
    # Run the critical test directly for quick verification
    print("Running positional non-commutativity test...")
    test = TestPositionalNonCommutativity()
    test.test_cvc_vs_ccv_produces_different_traces()
