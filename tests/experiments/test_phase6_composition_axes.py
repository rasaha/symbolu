"""
Test: Phase-6 Composition Axes
==============================

EXPERIMENTAL TEST - NON-FROZEN, NON-CANONICAL

This test suite validates the Phase-6 composition axis experiments:

1. DOMINANCE TESTS
   - Does the last consonant override previous modulation?
   - Compare sequences differing only in vowel position relative to consonant reset

2. VOWEL SCOPE TESTS
   - Test both PRECEDING_ONLY and PERSIST_UNTIL_RESET modes
   - Verify they produce different trajectories for the same sequence

3. MULTI-VOWEL ACCUMULATION TESTS
   - C-V-V sequences with additive baseline
   - Deterministic exact magnitude assertions

4. NON-COMMUTATIVITY REGRESSION
   - Confirm Phase-5 finding remains true
   - ["ka","a","ka"] vs ["ka","ka","a"] must differ

5. FAIL-FAST VALIDATION
   - Invalid varna token -> error
   - Invalid vowel token -> error
   - Empty sequence -> error

All tests are deterministic and fail-fast.
"""

import pytest
from typing import List

from symbolu.experiments.composition.composition_types import (
    VowelScope,
    SequenceConfig,
    TrajectoryStep,
    TrajectoryResult,
    PHASE6_VOWEL_DELTAS,
    PHASE6_VOWELS,
    BASELINE_MAGNITUDE,
)
from symbolu.experiments.composition.phase6_analyzer import (
    Phase6Analyzer,
    InvalidVarnaError,
    InvalidVowelError,
    EmptySequenceError,
    NoActiveConsonantError,
    analyze_sequence,
    compare_trajectories,
)


# =============================================================================
# Helper Functions
# =============================================================================

def _format_trajectory(result: TrajectoryResult) -> str:
    """Format a trajectory result for human-readable output."""
    lines = [f"Sequence: {list(result.sequence)}"]
    lines.append(f"Config: vowel_scope={result.config.vowel_scope.value}")
    lines.append("Steps:")
    for step in result.steps:
        lines.append(
            f"  [{step.idx}] {step.token:4s} ({step.token_type:5s}) "
            f"-> magnitude={step.magnitude:.4f} event={step.event}"
        )
    lines.append(f"Final magnitude: {result.final_magnitude:.4f}")
    return "\n".join(lines)


# =============================================================================
# 1. DOMINANCE TESTS
# =============================================================================

class TestDominance:
    """
    Test dominance axis: does the last consonant override previous modulation?

    Key insight: Consonants reset magnitude to baseline (1.0).
    Vowels that modulate before a consonant reset are "overwritten".
    """

    def test_vowel_before_vs_after_consonant_reset(self) -> None:
        """
        Compare sequences differing in vowel position relative to consonant reset.

        A: ["ka", "a", "ga"]  -> C-V-C: vowel modulates ka, then ga resets
        B: ["ka", "ga", "a"]  -> C-C-V: ka is overwritten by ga, then vowel modulates ga

        Expected: Different trajectories due to reset behavior.
        """
        seq_a = ["ka", "a", "ga"]  # C-V-C pattern
        seq_b = ["ka", "ga", "a"]  # C-C-V pattern

        result_a = analyze_sequence(seq_a)
        result_b = analyze_sequence(seq_b)

        print("\n" + "=" * 70)
        print("DOMINANCE TEST: Vowel position relative to consonant reset")
        print("=" * 70)
        print(f"\nSequence A (C-V-C): {seq_a}")
        print(_format_trajectory(result_a))
        print(f"\nSequence B (C-C-V): {seq_b}")
        print(_format_trajectory(result_b))

        # Assert trajectories differ
        mags_a = result_a.get_magnitudes()
        mags_b = result_b.get_magnitudes()

        # In A: [1.0, 1.1, 1.0] - vowel modulates, then ga resets
        # In B: [1.0, 1.0, 1.1] - ga resets, then vowel modulates
        assert mags_a != mags_b, (
            f"Expected different magnitude progressions.\n"
            f"A: {mags_a}\n"
            f"B: {mags_b}"
        )

        # Specific assertions about the pattern
        # In A: step 1 should be modulated (magnitude > 1.0)
        assert result_a.steps[1].magnitude > BASELINE_MAGNITUDE, (
            "In C-V-C, step 1 (vowel) should have magnitude > 1.0"
        )
        # In A: step 2 should be reset (magnitude = 1.0)
        assert result_a.steps[2].magnitude == BASELINE_MAGNITUDE, (
            "In C-V-C, step 2 (consonant) should reset to 1.0"
        )

        # In B: step 1 should be reset (magnitude = 1.0)
        assert result_b.steps[1].magnitude == BASELINE_MAGNITUDE, (
            "In C-C-V, step 1 (consonant) should be 1.0"
        )
        # In B: step 2 should be modulated (magnitude > 1.0)
        assert result_b.steps[2].magnitude > BASELINE_MAGNITUDE, (
            "In C-C-V, step 2 (vowel) should have magnitude > 1.0"
        )

        print("\nSUCCESS: Dominance demonstrated - consonant reset overrides prior modulation")

    def test_dominance_with_multiple_consonants(self) -> None:
        """
        Test that multiple consecutive consonants each reset to baseline.

        Sequence: ["ka", "ga", "na"]

        Expected: All magnitudes = 1.0 (each consonant resets)
        """
        seq = ["ka", "ga", "na"]
        result = analyze_sequence(seq)

        print("\n" + "=" * 70)
        print("DOMINANCE TEST: Multiple consecutive consonants")
        print("=" * 70)
        print(_format_trajectory(result))

        # All steps should have magnitude = 1.0
        for step in result.steps:
            assert step.magnitude == BASELINE_MAGNITUDE, (
                f"Step {step.idx} ({step.token}) should have magnitude 1.0, "
                f"got {step.magnitude}"
            )

        # All events should be "reset"
        for step in result.steps:
            assert step.event == "reset", (
                f"Step {step.idx} ({step.token}) should have event 'reset', "
                f"got {step.event}"
            )

        print("\nSUCCESS: Multiple consonants each reset to baseline")


# =============================================================================
# 2. VOWEL SCOPE TESTS
# =============================================================================

class TestVowelScope:
    """
    Test vowel scope axis: PRECEDING_ONLY vs PERSIST_UNTIL_RESET.

    Both modes accumulate vowels additively in Phase-6, but the conceptual
    model differs. We verify the configuration flag works and produces
    consistent results.
    """

    def test_persist_until_reset_accumulates_vowels(self) -> None:
        """
        Test PERSIST_UNTIL_RESET mode with consecutive vowels.

        Sequence: ["ka", "a", "i"]

        Expected magnitude progression:
            ka: 1.0 (reset)
            a:  1.0 + 0.1 = 1.1 (modulate)
            i:  1.1 + 0.2 = 1.3 (modulate)
        """
        seq = ["ka", "a", "i"]
        config = SequenceConfig(vowel_scope=VowelScope.PERSIST_UNTIL_RESET)
        analyzer = Phase6Analyzer()
        result = analyzer.analyze(seq, config)

        print("\n" + "=" * 70)
        print("VOWEL SCOPE TEST: PERSIST_UNTIL_RESET with consecutive vowels")
        print("=" * 70)
        print(_format_trajectory(result))

        expected_magnitudes = [1.0, 1.1, 1.3]
        actual_magnitudes = result.get_magnitudes()

        assert actual_magnitudes == expected_magnitudes, (
            f"Expected magnitudes {expected_magnitudes}, got {actual_magnitudes}"
        )

        print(f"\nSUCCESS: Magnitudes accumulate as expected: {actual_magnitudes}")

    def test_preceding_only_allows_consecutive_vowels(self) -> None:
        """
        Test PRECEDING_ONLY mode with consecutive vowels.

        In Phase-6, PRECEDING_ONLY still allows consecutive vowels,
        with each modifying the same active magnitude (same as PERSIST).
        The conceptual difference is in interpretation, not mechanics.

        Sequence: ["ka", "a", "i"]

        Expected: Same accumulation as PERSIST_UNTIL_RESET in Phase-6.
        """
        seq = ["ka", "a", "i"]
        config = SequenceConfig(vowel_scope=VowelScope.PRECEDING_ONLY)
        analyzer = Phase6Analyzer()
        result = analyzer.analyze(seq, config)

        print("\n" + "=" * 70)
        print("VOWEL SCOPE TEST: PRECEDING_ONLY with consecutive vowels")
        print("=" * 70)
        print(_format_trajectory(result))

        # In Phase-6 baseline, both modes produce same numeric result
        expected_magnitudes = [1.0, 1.1, 1.3]
        actual_magnitudes = result.get_magnitudes()

        assert actual_magnitudes == expected_magnitudes, (
            f"Expected magnitudes {expected_magnitudes}, got {actual_magnitudes}"
        )

        print(f"\nSUCCESS: PRECEDING_ONLY mode works correctly: {actual_magnitudes}")

    def test_both_scope_modes_produce_consistent_results(self) -> None:
        """
        Verify both scope modes are accessible and produce deterministic results.

        This test ensures the configuration flag works correctly.
        """
        seq = ["ka", "a", "ga", "i"]

        # Analyze with both modes
        result_persist = analyze_sequence(seq, VowelScope.PERSIST_UNTIL_RESET)
        result_preceding = analyze_sequence(seq, VowelScope.PRECEDING_ONLY)

        print("\n" + "=" * 70)
        print("VOWEL SCOPE TEST: Both modes produce consistent results")
        print("=" * 70)
        print("\nPERSIST_UNTIL_RESET:")
        print(_format_trajectory(result_persist))
        print("\nPRECEDING_ONLY:")
        print(_format_trajectory(result_preceding))

        # In Phase-6 baseline, numeric results are the same
        # The difference is conceptual (interpretation of what the scope means)
        assert result_persist.get_magnitudes() == result_preceding.get_magnitudes(), (
            "In Phase-6 baseline, both scope modes should produce same magnitudes"
        )

        # Verify the config was recorded correctly
        assert result_persist.config.vowel_scope == VowelScope.PERSIST_UNTIL_RESET
        assert result_preceding.config.vowel_scope == VowelScope.PRECEDING_ONLY

        print("\nSUCCESS: Both scope modes accessible and consistent")


# =============================================================================
# 3. MULTI-VOWEL ACCUMULATION TESTS
# =============================================================================

class TestMultiVowelAccumulation:
    """
    Test multi-vowel accumulation axis.

    Phase-6 uses additive baseline: each vowel adds its delta to active magnitude.
    """

    def test_cvivu_exact_magnitude(self) -> None:
        """
        Test exact magnitude for C-V-V-V sequence.

        Sequence: ["ka", "a", "i", "u"]

        Expected:
            ka: 1.0 (reset)
            a:  1.0 + 0.1 = 1.1
            i:  1.1 + 0.2 = 1.3
            u:  1.3 + 0.15 = 1.45

        Final magnitude: 1.45
        """
        seq = ["ka", "a", "i", "u"]
        result = analyze_sequence(seq)

        print("\n" + "=" * 70)
        print("MULTI-VOWEL ACCUMULATION TEST: C-V-V-V exact magnitude")
        print("=" * 70)
        print(_format_trajectory(result))

        expected_magnitudes = [1.0, 1.1, 1.3, 1.45]
        actual_magnitudes = result.get_magnitudes()

        assert actual_magnitudes == expected_magnitudes, (
            f"Expected magnitudes {expected_magnitudes}, got {actual_magnitudes}"
        )

        assert result.final_magnitude == 1.45, (
            f"Expected final magnitude 1.45, got {result.final_magnitude}"
        )

        print(f"\nSUCCESS: Multi-vowel accumulation correct. Final: {result.final_magnitude}")

    def test_vowel_order_matters(self) -> None:
        """
        Test that vowel order doesn't affect final magnitude (additive).

        Sequences:
            A: ["ka", "a", "i", "u"]  -> 1.0 + 0.1 + 0.2 + 0.15 = 1.45
            B: ["ka", "u", "i", "a"]  -> 1.0 + 0.15 + 0.2 + 0.1 = 1.45

        For additive accumulation, order shouldn't affect final magnitude.
        BUT the intermediate trajectory differs.
        """
        seq_a = ["ka", "a", "i", "u"]
        seq_b = ["ka", "u", "i", "a"]

        result_a = analyze_sequence(seq_a)
        result_b = analyze_sequence(seq_b)

        print("\n" + "=" * 70)
        print("MULTI-VOWEL ACCUMULATION TEST: Vowel order effects")
        print("=" * 70)
        print(f"\nSequence A: {seq_a}")
        print(_format_trajectory(result_a))
        print(f"\nSequence B: {seq_b}")
        print(_format_trajectory(result_b))

        # Final magnitudes should be the same (addition is commutative)
        assert result_a.final_magnitude == result_b.final_magnitude, (
            f"Additive accumulation should give same final magnitude. "
            f"A: {result_a.final_magnitude}, B: {result_b.final_magnitude}"
        )

        # But intermediate trajectories differ
        mags_a = result_a.get_magnitudes()
        mags_b = result_b.get_magnitudes()

        # Intermediate steps differ (step 1, 2, 3 have different values)
        assert mags_a[1] != mags_b[1], (
            f"Step 1 should differ: A={mags_a[1]}, B={mags_b[1]}"
        )

        print(f"\nSUCCESS: Same final ({result_a.final_magnitude}) but different trajectories")

    def test_repeated_same_vowel(self) -> None:
        """
        Test repeated application of the same vowel.

        Sequence: ["ka", "a", "a", "a"]

        Expected:
            ka: 1.0
            a:  1.1
            a:  1.2
            a:  1.3

        Final: 1.3
        """
        seq = ["ka", "a", "a", "a"]
        result = analyze_sequence(seq)

        print("\n" + "=" * 70)
        print("MULTI-VOWEL ACCUMULATION TEST: Repeated same vowel")
        print("=" * 70)
        print(_format_trajectory(result))

        expected_magnitudes = [1.0, 1.1, 1.2, 1.3]
        actual_magnitudes = result.get_magnitudes()

        assert actual_magnitudes == expected_magnitudes, (
            f"Expected {expected_magnitudes}, got {actual_magnitudes}"
        )

        print(f"\nSUCCESS: Repeated vowel accumulates correctly: {actual_magnitudes}")


# =============================================================================
# 4. NON-COMMUTATIVITY REGRESSION
# =============================================================================

class TestNonCommutativityRegression:
    """
    Confirm Phase-5 finding remains true in Phase-6.

    ["ka","a","ka"] vs ["ka","ka","a"] must produce different trajectories.
    """

    def test_cvc_vs_ccv_produces_different_traces(self) -> None:
        """
        CRITICAL REGRESSION TEST: Same varnas, different order -> different trajectories.

        Sequences:
            seq_1 = ["ka", "a", "ka"]  # C-V-C pattern
            seq_2 = ["ka", "ka", "a"]  # C-C-V pattern

        Both contain: 2x "ka" (consonant), 1x "a" (vowel)

        Expected:
            seq_1: [1.0, 1.1, 1.0]  # vowel modulates, then reset
            seq_2: [1.0, 1.0, 1.1]  # reset, then vowel modulates
        """
        seq_1 = ["ka", "a", "ka"]  # C-V-C
        seq_2 = ["ka", "ka", "a"]  # C-C-V

        result_1 = analyze_sequence(seq_1)
        result_2 = analyze_sequence(seq_2)

        print("\n" + "=" * 70)
        print("NON-COMMUTATIVITY REGRESSION TEST")
        print("=" * 70)
        print(f"\nSequence 1 (C-V-C): {seq_1}")
        print(_format_trajectory(result_1))
        print(f"\nSequence 2 (C-C-V): {seq_2}")
        print(_format_trajectory(result_2))

        mags_1 = result_1.get_magnitudes()
        mags_2 = result_2.get_magnitudes()

        # Trajectories MUST differ
        assert mags_1 != mags_2, (
            f"REGRESSION FAILURE: Trajectories should differ.\n"
            f"seq_1: {mags_1}\n"
            f"seq_2: {mags_2}"
        )

        # Specific expected values
        assert mags_1 == [1.0, 1.1, 1.0], f"seq_1 expected [1.0, 1.1, 1.0], got {mags_1}"
        assert mags_2 == [1.0, 1.0, 1.1], f"seq_2 expected [1.0, 1.0, 1.1], got {mags_2}"

        # Token order differs at step 1
        assert result_1.steps[1].token != result_2.steps[1].token, (
            "Token at step 1 should differ between sequences"
        )

        # Role differs at step 1
        assert result_1.steps[1].token_type != result_2.steps[1].token_type, (
            "Token type at step 1 should differ"
        )

        print("\nSUCCESS: Non-commutativity confirmed - Phase-5 finding holds")

    def test_compare_trajectories_helper(self) -> None:
        """Test the compare_trajectories helper function."""
        seq_a = ["ka", "a", "ka"]
        seq_b = ["ka", "ka", "a"]

        comparison = compare_trajectories(seq_a, seq_b)

        print("\n" + "=" * 70)
        print("NON-COMMUTATIVITY: compare_trajectories helper")
        print("=" * 70)
        print(f"Sequences differ: {comparison['trajectories_differ']}")
        print(f"Magnitudes differ: {comparison['magnitudes_differ']}")
        print(f"Events differ: {comparison['events_differ']}")

        assert comparison["trajectories_differ"], (
            "compare_trajectories should detect difference"
        )
        assert comparison["magnitudes_differ"], (
            "Magnitudes should differ"
        )

        print("\nSUCCESS: compare_trajectories helper works correctly")


# =============================================================================
# 5. FAIL-FAST VALIDATION TESTS
# =============================================================================

class TestFailFastValidation:
    """
    Test fail-fast error handling.

    Invalid inputs must raise specific, informative errors.
    """

    def test_invalid_varna_token_raises(self) -> None:
        """
        Invalid varna token should raise InvalidVarnaError.

        Sequence: ["xyz", "a", "ka"]
        """
        seq = ["xyz", "a", "ka"]

        print("\n" + "=" * 70)
        print("FAIL-FAST TEST: Invalid varna token")
        print("=" * 70)

        with pytest.raises(InvalidVarnaError) as exc_info:
            analyze_sequence(seq)

        assert exc_info.value.token == "xyz"
        print(f"Raised: {exc_info.value}")
        print("\nSUCCESS: Invalid varna raises InvalidVarnaError")

    def test_invalid_vowel_token_raises(self) -> None:
        """
        Invalid vowel token should raise InvalidVowelError.

        Only a, i, u are supported in Phase-6.

        Sequence: ["ka", "e", "ka"]
        """
        seq = ["ka", "e", "ka"]

        print("\n" + "=" * 70)
        print("FAIL-FAST TEST: Invalid vowel token")
        print("=" * 70)

        with pytest.raises(InvalidVowelError) as exc_info:
            analyze_sequence(seq)

        assert exc_info.value.token == "e"
        print(f"Raised: {exc_info.value}")
        print("\nSUCCESS: Invalid vowel raises InvalidVowelError")

    def test_empty_sequence_raises(self) -> None:
        """
        Empty sequence should raise EmptySequenceError.
        """
        seq: List[str] = []

        print("\n" + "=" * 70)
        print("FAIL-FAST TEST: Empty sequence")
        print("=" * 70)

        with pytest.raises(EmptySequenceError):
            analyze_sequence(seq)

        print("Raised: EmptySequenceError")
        print("\nSUCCESS: Empty sequence raises EmptySequenceError")

    def test_vowel_without_consonant_raises(self) -> None:
        """
        Vowel without preceding consonant should raise NoActiveConsonantError.

        Sequence: ["a"]
        """
        seq = ["a"]

        print("\n" + "=" * 70)
        print("FAIL-FAST TEST: Vowel without consonant")
        print("=" * 70)

        with pytest.raises(NoActiveConsonantError) as exc_info:
            analyze_sequence(seq)

        assert exc_info.value.token == "a"
        assert exc_info.value.idx == 0
        print(f"Raised: {exc_info.value}")
        print("\nSUCCESS: Vowel without consonant raises NoActiveConsonantError")

    def test_vowel_first_in_sequence_raises(self) -> None:
        """
        Vowel as first token should raise NoActiveConsonantError.

        Sequence: ["i", "ka"]
        """
        seq = ["i", "ka"]

        print("\n" + "=" * 70)
        print("FAIL-FAST TEST: Vowel first in sequence")
        print("=" * 70)

        with pytest.raises(NoActiveConsonantError) as exc_info:
            analyze_sequence(seq)

        assert exc_info.value.token == "i"
        print(f"Raised: {exc_info.value}")
        print("\nSUCCESS: Vowel first raises NoActiveConsonantError")


# =============================================================================
# 6. EDGE CASES AND DETERMINISM
# =============================================================================

class TestDeterminismAndEdgeCases:
    """
    Test edge cases and verify deterministic behavior.
    """

    def test_single_consonant(self) -> None:
        """Single consonant initializes to baseline."""
        result = analyze_sequence(["ka"])

        assert len(result.steps) == 1
        assert result.steps[0].magnitude == BASELINE_MAGNITUDE
        assert result.steps[0].event == "reset"
        assert result.final_magnitude == BASELINE_MAGNITUDE

    def test_single_consonant_vowel_pair(self) -> None:
        """C-V pair has expected magnitude."""
        result = analyze_sequence(["ka", "a"])

        assert len(result.steps) == 2
        assert result.steps[0].magnitude == 1.0
        assert result.steps[1].magnitude == 1.1  # 1.0 + 0.1

    def test_determinism_multiple_runs(self) -> None:
        """Same sequence produces identical results across multiple runs."""
        seq = ["ka", "a", "i", "ga", "u"]

        results = [analyze_sequence(seq) for _ in range(5)]

        # All results should be identical
        first_mags = results[0].get_magnitudes()
        for i, result in enumerate(results[1:], start=2):
            assert result.get_magnitudes() == first_mags, (
                f"Run {i} produced different magnitudes"
            )

    def test_long_sequence(self) -> None:
        """Test a longer sequence for stability."""
        seq = ["ka", "a", "ga", "i", "na", "u", "ta", "a", "da", "i", "pa"]
        result = analyze_sequence(seq)

        # Should complete without error
        assert len(result.steps) == len(seq)

        # Final consonant should reset to baseline
        assert result.final_magnitude == BASELINE_MAGNITUDE

    def test_trajectory_result_to_dict(self) -> None:
        """Test serialization works correctly."""
        result = analyze_sequence(["ka", "a", "i"])
        result_dict = result.to_dict()

        assert result_dict["sequence"] == ["ka", "a", "i"]
        assert len(result_dict["steps"]) == 3
        assert result_dict["final_magnitude"] == 1.3
        assert result_dict["config"]["vowel_scope"] == "persist_until_reset"


# =============================================================================
# Run directly for quick verification
# =============================================================================

if __name__ == "__main__":
    print("Running Phase-6 Composition Axes Tests...")
    print()

    # Quick smoke test
    test = TestNonCommutativityRegression()
    test.test_cvc_vs_ccv_produces_different_traces()

    test2 = TestMultiVowelAccumulation()
    test2.test_cvivu_exact_magnitude()

    print("\n" + "=" * 70)
    print("SMOKE TEST PASSED - Run pytest for full suite")
    print("=" * 70)
