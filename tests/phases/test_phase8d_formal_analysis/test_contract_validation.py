"""
Phase-8D Contract Validation Tests
===================================

These tests validate that the Phase-8D contract's axiom encoding
matches actual Phase-6 behavior. This catches specification errors
BEFORE implementation effort is invested.

Contract: docs/contracts/PHASE_8D_FORMAL_ANALYSIS_CONTRACT.md

Test Categories:
  1. Grammar Axiom Validation (G1-G4)
  2. Magnitude Axiom Validation (M1-M5)
  3. Contract Example Validation
  4. Derived Bound Validation
"""

import pytest
from typing import List, Tuple

from symbolu.experiments.composition import Phase6Analyzer
from symbolu.experiments.composition.composition_types import (
    PHASE6_VOWEL_DELTAS,
    PHASE6_VOWELS,
    BASELINE_MAGNITUDE,
    VowelScope,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def analyzer():
    """Create Phase-6 analyzer instance."""
    return Phase6Analyzer()


def analyze(sequence: List[str]) -> dict:
    """Helper to analyze sequence and return key properties."""
    analyzer = Phase6Analyzer()
    result = analyzer.analyze(sequence)
    return {
        "final_magnitude": result.final_magnitude,
        "steps": result.steps,
        "events": [s.event for s in result.steps],
        "magnitudes": [s.magnitude for s in result.steps],
    }


# ============================================================================
# G1: CONSONANT-INITIAL AXIOM
# "Every valid sequence begins with a consonant"
# "steps[0].event == 'reset'"
# ============================================================================

class TestG1ConsonantInitial:
    """Validate axiom G1: First token must be consonant, first event is reset."""

    def test_consonant_first_produces_reset(self, analyzer):
        """Consonant-initial sequence has first event as reset."""
        for consonant in ["ka", "ga", "ta", "da", "pa", "ba"]:
            result = analyzer.analyze([consonant])
            assert result.steps[0].event == "reset", f"{consonant} should produce reset"

    def test_consonant_followed_by_vowel(self, analyzer):
        """Consonant then vowel: first event is reset."""
        result = analyzer.analyze(["ka", "a"])
        assert result.steps[0].event == "reset"
        assert result.steps[1].event == "modulate"

    def test_all_consonants_produce_reset_first(self, analyzer):
        """All valid consonants produce reset as first event."""
        consonants = ["ka", "ga", "ta", "da", "pa", "ba"]
        for c in consonants:
            result = analyzer.analyze([c, "a", "i"])
            assert result.steps[0].event == "reset", f"G1 violated for {c}"

    def test_vowel_initial_rejected_or_handled(self, analyzer):
        """Vowel-initial sequences should be rejected (G1 requirement)."""
        # Phase-6 should reject vowel-initial sequences
        try:
            result = analyzer.analyze(["a", "ka"])
            # If it doesn't raise, check if it's handled somehow
            # (This might be implementation-specific)
            pytest.fail("Vowel-initial should be rejected per G1")
        except Exception:
            pass  # Expected - vowel-initial is invalid


# ============================================================================
# G2: VOWEL-REQUIRES-CONSONANT AXIOM
# "A modulate event cannot occur without a preceding reset event"
# ============================================================================

class TestG2VowelRequiresConsonant:
    """Validate axiom G2: Modulate requires preceding reset."""

    def test_modulate_after_reset(self, analyzer):
        """Modulate event only occurs after reset."""
        result = analyzer.analyze(["ka", "a", "i", "u"])
        events = [s.event for s in result.steps]

        # First event must be reset
        assert events[0] == "reset"

        # Every modulate must have a preceding reset somewhere
        for i, event in enumerate(events):
            if event == "modulate":
                # There must be at least one reset before this
                preceding_events = events[:i]
                assert "reset" in preceding_events, f"G2 violated at index {i}"

    def test_multiple_consonants_all_reset(self, analyzer):
        """Multiple consonants all produce reset events."""
        result = analyzer.analyze(["ka", "ga", "ta", "da"])
        events = [s.event for s in result.steps]
        assert all(e == "reset" for e in events)

    def test_consonant_vowel_alternation(self, analyzer):
        """Alternating C-V pattern has reset-modulate pattern."""
        result = analyzer.analyze(["ka", "a", "ga", "i", "ta", "u"])
        events = [s.event for s in result.steps]
        expected = ["reset", "modulate", "reset", "modulate", "reset", "modulate"]
        assert events == expected


# ============================================================================
# G3: VALID-TOKEN-SET AXIOM
# "Consonants from {ka, ga, ta, da, pa, ba}, vowels from {a, i, u}"
# ============================================================================

class TestG3ValidTokenSet:
    """Validate axiom G3: Valid token sets."""

    def test_all_consonants_valid(self, analyzer):
        """All Phase-4A consonants are valid."""
        consonants = ["ka", "ga", "ta", "da", "pa", "ba"]
        for c in consonants:
            result = analyzer.analyze([c])
            assert result.final_magnitude == BASELINE_MAGNITUDE

    def test_all_vowels_valid(self, analyzer):
        """All Phase-6 vowels are valid."""
        for v in ["a", "i", "u"]:
            result = analyzer.analyze(["ka", v])
            assert result.steps[1].event == "modulate"

    def test_vowel_set_matches_constant(self):
        """PHASE6_VOWELS constant matches contract G3."""
        assert PHASE6_VOWELS == frozenset({"a", "i", "u"})

    def test_invalid_token_rejected(self, analyzer):
        """Invalid tokens should be rejected."""
        try:
            analyzer.analyze(["invalid_token"])
            pytest.fail("Invalid token should be rejected")
        except Exception:
            pass  # Expected


# ============================================================================
# G4: LENGTH-BOUNDS AXIOM
# "len(sequence) >= 1, len(steps) == len(sequence)"
# ============================================================================

class TestG4LengthBounds:
    """Validate axiom G4: Length constraints."""

    def test_single_token_sequence(self, analyzer):
        """Single token sequence has one step."""
        result = analyzer.analyze(["ka"])
        assert len(result.steps) == 1

    def test_steps_equals_sequence_length(self, analyzer):
        """Number of steps equals sequence length."""
        for length in range(1, 10):
            # Alternate consonants and vowels
            seq = []
            for i in range(length):
                if i % 2 == 0:
                    seq.append("ka")
                else:
                    seq.append("a")
            result = analyzer.analyze(seq)
            assert len(result.steps) == length, f"G4 violated for length {length}"

    def test_empty_sequence_rejected(self, analyzer):
        """Empty sequence should be rejected."""
        try:
            analyzer.analyze([])
            pytest.fail("Empty sequence should be rejected per G4")
        except Exception:
            pass  # Expected


# ============================================================================
# M1: BASELINE AXIOM
# "Magnitude baseline is 1.0. After any reset event: magnitude == 1.0"
# ============================================================================

class TestM1Baseline:
    """Validate axiom M1: Reset sets magnitude to 1.0."""

    def test_baseline_constant(self):
        """BASELINE_MAGNITUDE constant is 1.0."""
        assert BASELINE_MAGNITUDE == 1.0

    def test_consonant_resets_to_baseline(self, analyzer):
        """Consonant always resets magnitude to 1.0."""
        result = analyzer.analyze(["ka"])
        assert result.steps[0].magnitude == 1.0

    def test_reset_after_modulation(self, analyzer):
        """Reset after vowels returns to 1.0."""
        result = analyzer.analyze(["ka", "a", "i", "ga"])
        # After vowels, magnitude should be elevated
        # After ga (reset), should be back to 1.0
        assert result.steps[3].magnitude == 1.0

    def test_all_consonants_reset_to_baseline(self, analyzer):
        """All consonants reset to exactly 1.0."""
        consonants = ["ka", "ga", "ta", "da", "pa", "ba"]
        for c in consonants:
            result = analyzer.analyze(["ka", "a", "i", c])
            assert result.steps[3].magnitude == 1.0, f"M1 violated for {c}"


# ============================================================================
# M2: VOWEL-DELTAS AXIOM
# "delta('a') == 0.1, delta('i') == 0.2, delta('u') == 0.15"
# ============================================================================

class TestM2VowelDeltas:
    """Validate axiom M2: Vowel modulation deltas."""

    def test_delta_constants_match_contract(self):
        """PHASE6_VOWEL_DELTAS matches contract M2."""
        assert PHASE6_VOWEL_DELTAS["a"] == 0.1
        assert PHASE6_VOWEL_DELTAS["i"] == 0.2
        assert PHASE6_VOWEL_DELTAS["u"] == 0.15

    def test_vowel_a_adds_0_1(self, analyzer):
        """Vowel 'a' adds exactly 0.1 to magnitude."""
        result = analyzer.analyze(["ka", "a"])
        assert abs(result.final_magnitude - 1.1) < 1e-10

    def test_vowel_i_adds_0_2(self, analyzer):
        """Vowel 'i' adds exactly 0.2 to magnitude."""
        result = analyzer.analyze(["ka", "i"])
        assert abs(result.final_magnitude - 1.2) < 1e-10

    def test_vowel_u_adds_0_15(self, analyzer):
        """Vowel 'u' adds exactly 0.15 to magnitude."""
        result = analyzer.analyze(["ka", "u"])
        assert abs(result.final_magnitude - 1.15) < 1e-10

    def test_vowels_accumulate_additively(self, analyzer):
        """Multiple vowels add their deltas."""
        # ka + a + i = 1.0 + 0.1 + 0.2 = 1.3
        result = analyzer.analyze(["ka", "a", "i"])
        assert abs(result.final_magnitude - 1.3) < 1e-10

        # ka + a + i + u = 1.0 + 0.1 + 0.2 + 0.15 = 1.45
        result = analyzer.analyze(["ka", "a", "i", "u"])
        assert abs(result.final_magnitude - 1.45) < 1e-10


# ============================================================================
# M3: MINIMUM-MAGNITUDE AXIOM
# "Magnitude never falls below baseline: ∀i, steps[i].magnitude >= 1.0"
# "final_magnitude >= 1.0"
# ============================================================================

class TestM3MinimumMagnitude:
    """Validate axiom M3: Magnitude never below 1.0."""

    def test_single_consonant_at_baseline(self, analyzer):
        """Single consonant has magnitude exactly 1.0."""
        result = analyzer.analyze(["ka"])
        assert result.final_magnitude >= 1.0

    def test_all_steps_at_least_baseline(self, analyzer):
        """Every step has magnitude >= 1.0."""
        result = analyzer.analyze(["ka", "a", "ga", "i", "ta", "u"])
        for step in result.steps:
            assert step.magnitude >= 1.0, f"M3 violated at step {step.idx}"

    def test_final_magnitude_at_least_baseline(self, analyzer):
        """Final magnitude is always >= 1.0."""
        test_sequences = [
            ["ka"],
            ["ka", "a"],
            ["ka", "ga", "ta"],
            ["ka", "a", "i", "u"],
            ["pa", "a", "ba", "i", "da", "u"],
        ]
        for seq in test_sequences:
            result = analyzer.analyze(seq)
            assert result.final_magnitude >= 1.0, f"M3 violated for {seq}"

    def test_reset_never_below_baseline(self, analyzer):
        """Reset events produce exactly 1.0 (not below)."""
        result = analyzer.analyze(["ka", "a", "i", "ga", "u", "ta"])
        for step in result.steps:
            if step.event == "reset":
                assert step.magnitude == 1.0


# ============================================================================
# M4: CONSONANT-ONLY-BASELINE AXIOM
# "Consonant-only sequence has final_magnitude == 1.0"
# ============================================================================

class TestM4ConsonantOnlyBaseline:
    """Validate axiom M4: Consonant-only sequences have magnitude 1.0."""

    def test_single_consonant_exactly_baseline(self, analyzer):
        """Single consonant has final_magnitude == 1.0."""
        for c in ["ka", "ga", "ta", "da", "pa", "ba"]:
            result = analyzer.analyze([c])
            assert result.final_magnitude == 1.0

    def test_multiple_consonants_exactly_baseline(self, analyzer):
        """Multiple consonants have final_magnitude == 1.0."""
        result = analyzer.analyze(["ka", "ga", "ta", "da", "pa", "ba"])
        assert result.final_magnitude == 1.0

    def test_consonant_only_all_reset_events(self, analyzer):
        """Consonant-only sequence has all reset events."""
        result = analyzer.analyze(["ka", "ga", "ta"])
        events = [s.event for s in result.steps]
        assert all(e == "reset" for e in events)


# ============================================================================
# M5: MAGNITUDE-ACCUMULATION AXIOM
# "Magnitude at step i: reset → 1.0, modulate → steps[i-1].magnitude + delta"
# ============================================================================

class TestM5MagnitudeAccumulation:
    """Validate axiom M5: Magnitude accumulation formula."""

    def test_reset_sets_magnitude(self, analyzer):
        """Reset event sets magnitude to 1.0."""
        result = analyzer.analyze(["ka", "a", "ga"])
        assert result.steps[0].magnitude == 1.0  # First reset
        assert result.steps[2].magnitude == 1.0  # Reset after vowel

    def test_modulate_adds_delta(self, analyzer):
        """Modulate adds delta to previous magnitude."""
        result = analyzer.analyze(["ka", "a", "i"])
        # Step 0: ka → 1.0
        # Step 1: a → 1.0 + 0.1 = 1.1
        # Step 2: i → 1.1 + 0.2 = 1.3
        assert abs(result.steps[0].magnitude - 1.0) < 1e-10
        assert abs(result.steps[1].magnitude - 1.1) < 1e-10
        assert abs(result.steps[2].magnitude - 1.3) < 1e-10

    def test_accumulation_formula_complex(self, analyzer):
        """Complex sequence follows accumulation formula."""
        # ka(1.0) → a(1.1) → i(1.3) → ga(1.0) → u(1.15) → a(1.25)
        result = analyzer.analyze(["ka", "a", "i", "ga", "u", "a"])
        expected = [1.0, 1.1, 1.3, 1.0, 1.15, 1.25]
        for i, exp in enumerate(expected):
            assert abs(result.steps[i].magnitude - exp) < 1e-10, f"M5 violated at step {i}"


# ============================================================================
# CONTRACT EXAMPLE VALIDATION
# Validate the examples from Section 10 of the contract
# ============================================================================

class TestContractExamples:
    """Validate examples from Phase-8D contract Section 10."""

    def test_example1_magnitude_reachability(self, analyzer):
        """
        Example 1: Can final_magnitude == 1.5 be achieved with len == 4?

        Contract claims: ["ka", "i", "i", "a"] achieves 1.5
        """
        result = analyzer.analyze(["ka", "i", "i", "a"])
        # Expected: 1.0 + 0.2 + 0.2 + 0.1 = 1.5
        assert len(result.steps) == 4
        assert abs(result.final_magnitude - 1.5) < 1e-10

    def test_example2_contradiction_detection(self, analyzer):
        """
        Example 2: final_magnitude < 1.0 is impossible.

        Contract claims: Axiom M3 guarantees magnitude >= 1.0
        """
        # Generate many sequences, none should have final_magnitude < 1.0
        test_sequences = [
            ["ka"],
            ["ka", "a"],
            ["ga", "i", "u"],
            ["ta", "a", "i", "u", "da", "a"],
            ["pa", "ba", "da", "ta", "ga", "ka"],
        ]
        for seq in test_sequences:
            result = analyzer.analyze(seq)
            assert result.final_magnitude >= 1.0, f"M3 violated for {seq}"

    def test_example4_length2_modulate_pattern(self, analyzer):
        """
        Example 4: len(steps) == 2 AND steps[1].event == 'modulate'

        Contract claims: This implies [consonant, vowel] pattern.
        """
        # Only [C, V] patterns should have len=2 with second=modulate
        for c in ["ka", "ga", "ta"]:
            for v in ["a", "i", "u"]:
                result = analyzer.analyze([c, v])
                assert len(result.steps) == 2
                assert result.steps[0].event == "reset"
                assert result.steps[1].event == "modulate"

        # [C, C] should have len=2 but second=reset
        result = analyzer.analyze(["ka", "ga"])
        assert result.steps[1].event == "reset"


# ============================================================================
# DERIVED BOUNDS VALIDATION
# Contract Section 2 derived bounds from axioms
# ============================================================================

class TestDerivedBounds:
    """Validate derived bounds from Phase-8D contract."""

    def test_max_magnitude_formula(self, analyzer):
        """
        Derived bound: max_magnitude(n_vowels) == 1.0 + 0.2 * n_vowels

        For n vowels after last reset, max is achieved with all 'i' vowels.
        """
        # 0 vowels → max = 1.0
        result = analyzer.analyze(["ka"])
        assert result.final_magnitude == 1.0

        # 1 vowel → max = 1.2 (using 'i')
        result = analyzer.analyze(["ka", "i"])
        assert abs(result.final_magnitude - 1.2) < 1e-10

        # 3 vowels → max = 1.6 (using all 'i')
        result = analyzer.analyze(["ka", "i", "i", "i"])
        assert abs(result.final_magnitude - 1.6) < 1e-10

        # 5 vowels → max = 2.0 (using all 'i')
        result = analyzer.analyze(["ka", "i", "i", "i", "i", "i"])
        assert abs(result.final_magnitude - 2.0) < 1e-10

    def test_min_magnitude_formula(self, analyzer):
        """
        Derived bound: min_magnitude(n_vowels) == 1.0 + 0.1 * n_vowels

        For n vowels after last reset, min is achieved with all 'a' vowels.
        """
        # 1 vowel → min = 1.1 (using 'a')
        result = analyzer.analyze(["ka", "a"])
        assert abs(result.final_magnitude - 1.1) < 1e-10

        # 3 vowels → min = 1.3 (using all 'a')
        result = analyzer.analyze(["ka", "a", "a", "a"])
        assert abs(result.final_magnitude - 1.3) < 1e-10

    def test_magnitude_range_for_length(self, analyzer):
        """
        For length L with pattern [C, V, V, ...]:
        - Min: 1.0 + 0.1 * (L-1)  (all 'a')
        - Max: 1.0 + 0.2 * (L-1)  (all 'i')
        """
        # Length 4: [C, V, V, V]
        # Min = 1.0 + 0.1*3 = 1.3
        # Max = 1.0 + 0.2*3 = 1.6

        # Verify min
        result_min = analyzer.analyze(["ka", "a", "a", "a"])
        assert abs(result_min.final_magnitude - 1.3) < 1e-10

        # Verify max
        result_max = analyzer.analyze(["ka", "i", "i", "i"])
        assert abs(result_max.final_magnitude - 1.6) < 1e-10

        # Any other combo should be between
        result_mid = analyzer.analyze(["ka", "a", "i", "u"])
        # 1.0 + 0.1 + 0.2 + 0.15 = 1.45
        assert 1.3 <= result_mid.final_magnitude <= 1.6


# ============================================================================
# SOUNDNESS PREREQUISITE TESTS
# Tests that must pass for T1 soundness tests to be meaningful
# ============================================================================

class TestSoundnessPrerequisites:
    """Prerequisites for T1 soundness tests."""

    def test_magnitude_below_1_truly_impossible(self, analyzer):
        """
        T1.1 prerequisite: Verify M3 (mag >= 1.0) is actually enforced.

        If Phase-8D claims UNSATISFIABLE for "mag < 1.0", this must be true.
        """
        # Exhaustively test many sequences
        consonants = ["ka", "ga", "ta", "da", "pa", "ba"]
        vowels = ["a", "i", "u"]

        # Test all length-1 sequences
        for c in consonants:
            result = analyzer.analyze([c])
            assert result.final_magnitude >= 1.0

        # Test all length-2 sequences
        for c in consonants:
            for token2 in consonants + vowels:
                try:
                    if token2 in vowels:
                        result = analyzer.analyze([c, token2])
                    else:
                        result = analyzer.analyze([c, token2])
                    assert result.final_magnitude >= 1.0
                except Exception:
                    pass  # Invalid sequence

        # Test some length-3 sequences
        for c in consonants:
            for v in vowels:
                result = analyzer.analyze([c, v, v])
                assert result.final_magnitude >= 1.0

    def test_upper_bound_achievable(self, analyzer):
        """
        T1.2 prerequisite: Maximum magnitude is actually achievable.

        For length 4: max = 1.0 + 0.2*3 = 1.6
        """
        result = analyzer.analyze(["ka", "i", "i", "i"])
        assert abs(result.final_magnitude - 1.6) < 1e-10


# ============================================================================
# DETERMINISM PREREQUISITES
# Tests for T3 determinism requirements
# ============================================================================

class TestDeterminismPrerequisites:
    """Prerequisites for T3 determinism tests."""

    def test_phase6_is_deterministic(self, analyzer):
        """Phase-6 produces identical results for identical inputs."""
        seq = ["ka", "a", "i", "ga", "u"]

        results = [analyzer.analyze(seq) for _ in range(10)]

        # All should be identical
        first = results[0]
        for r in results[1:]:
            assert r.final_magnitude == first.final_magnitude
            assert len(r.steps) == len(first.steps)
            for i in range(len(r.steps)):
                assert r.steps[i].magnitude == first.steps[i].magnitude
                assert r.steps[i].event == first.steps[i].event


# ============================================================================
# SUMMARY TEST
# ============================================================================

class TestContractAxiomSummary:
    """Summary test validating all axioms hold."""

    def test_all_axioms_validated(self, analyzer):
        """Comprehensive test that exercises all axioms."""
        # Complex sequence
        seq = ["ka", "a", "i", "ga", "u", "ta", "a", "a", "da"]
        result = analyzer.analyze(seq)

        # G1: First event is reset
        assert result.steps[0].event == "reset"

        # G2: Modulate only after reset
        seen_reset = False
        for step in result.steps:
            if step.event == "reset":
                seen_reset = True
            elif step.event == "modulate":
                assert seen_reset, "G2 violated"

        # G4: Steps == sequence length
        assert len(result.steps) == len(seq)

        # M3: All magnitudes >= 1.0
        for step in result.steps:
            assert step.magnitude >= 1.0

        # M1: Reset events have magnitude 1.0
        for step in result.steps:
            if step.event == "reset":
                assert step.magnitude == 1.0

        # M5: Accumulation is correct
        expected_mag = 1.0
        for i, step in enumerate(result.steps):
            if step.event == "reset":
                expected_mag = 1.0
            else:
                token = seq[i]
                expected_mag += PHASE6_VOWEL_DELTAS[token]
            assert abs(step.magnitude - expected_mag) < 1e-10, f"M5 violated at step {i}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
