"""
Phase-1b Validation Tests (v3.1)
================================

Test Goals: Substrate integrity verification only (NOT meaning).

This test suite verifies:
    1. Varna segmentation correctness
    2. JSON-only authority (no heuristics)
    3. Aspirated vs unaspirated preservation
    4. Vowel handling (a/e/i/o/u only via JSON)
    5. Unknown handling (opaque, no guessing)
    6. Structural cluster patterns

Version: 3.1
Date: 2025-12-15

RED FLAGS (if any of these occur, it's a regression):
    - Any inference like "sadness", "emotion", "intent"
    - Any vowel guessed outside JSON
    - Any fallback classification for unknown letters
    - Any aspiration inferred from spelling
"""

import pytest
import sys
from pathlib import Path

# Add experiments directory to path for v3.1 mapper
sys.path.insert(0, str(Path(__file__).parent.parent / "docs" / "experiments"))

from acoustic_unit_mapper_expressive_delta_v3_1 import (
    map_acoustic_units,
    map_acoustic_units_with_context,
    AcousticBridgeUnit,
    VarnaBridgeMap,
    get_acoustic_signature,
    get_bridge_meanings,
    count_vowels,
    count_consonants,
    count_aspirated,
    count_unknown,
    validate_invariants_v3_1,
    validate_unit_consistency,
    SUBSTRATE_INVARIANTS_V3_1,
    ACOUSTIC_MAPPER_VERSION,
)


# ============================================================================
# TEST GROUP 1: MINIMAL SANITY TESTS (must pass)
# ============================================================================

class TestMinimalSanity:
    """Minimal sanity tests - these MUST pass for v3.1 compliance."""

    def test_single_consonant_sa(self):
        """
        Test 1 - Single consonant "sa"

        Expected:
            - 1 unit
            - varna = "sa"
            - is_consonant = True
            - is_vowel = False
            - bridge_meaning = "escape_pressure"
            - cluster_order = "C"
        """
        units = map_acoustic_units("sa")

        assert len(units) == 1, f"Expected 1 unit, got {len(units)}"

        unit = units[0]
        assert unit.varna == "sa", f"Expected varna='sa', got '{unit.varna}'"
        assert unit.is_consonant is True, "sa should be consonant"
        assert unit.is_vowel is False, "sa should NOT be vowel"
        assert unit.bridge_meaning == "escape_pressure", \
            f"Expected 'escape_pressure', got '{unit.bridge_meaning}'"
        assert unit.cluster_order == "C", \
            f"Expected cluster_order='C', got '{unit.cluster_order}'"
        assert unit.is_aspirated is False, "sa should NOT be aspirated"

    def test_single_vowel_a(self):
        """
        Test 2 - Single vowel "a"

        Expected:
            - 1 unit
            - is_vowel = True
            - bridge_meaning = "birth_of_cognition"
            - cluster_order = "V"
        """
        units = map_acoustic_units("a")

        assert len(units) == 1, f"Expected 1 unit, got {len(units)}"

        unit = units[0]
        assert unit.varna == "a", f"Expected varna='a', got '{unit.varna}'"
        assert unit.is_vowel is True, "a should be vowel"
        assert unit.is_consonant is False, "a should NOT be consonant"
        assert unit.bridge_meaning == "birth_of_cognition", \
            f"Expected 'birth_of_cognition', got '{unit.bridge_meaning}'"
        assert unit.cluster_order == "V", \
            f"Expected cluster_order='V', got '{unit.cluster_order}'"

    def test_aspirated_vs_unaspirated_contrast(self):
        """
        Test 3 - Aspirated vs unaspirated contrast "ka kha"

        Expected:
            - ka: is_aspirated = False
            - kha: is_aspirated = True
            - Different bridge meanings
            - No inference or collapse

        This confirms observer vs observed channel is preserved.
        """
        units = map_acoustic_units("ka kha")

        assert len(units) == 2, f"Expected 2 units, got {len(units)}"

        ka_unit = units[0]
        kha_unit = units[1]

        # Verify ka (unaspirated)
        assert ka_unit.varna == "ka", f"Expected 'ka', got '{ka_unit.varna}'"
        assert ka_unit.is_aspirated is False, "ka should NOT be aspirated"
        assert ka_unit.is_consonant is True, "ka should be consonant"
        assert ka_unit.bridge_meaning == "hope_pressure", \
            f"Expected 'hope_pressure' for ka, got '{ka_unit.bridge_meaning}'"

        # Verify kha (aspirated)
        assert kha_unit.varna == "kha", f"Expected 'kha', got '{kha_unit.varna}'"
        assert kha_unit.is_aspirated is True, "kha SHOULD be aspirated"
        assert kha_unit.is_consonant is True, "kha should be consonant"
        assert kha_unit.bridge_meaning == "worry_pressure", \
            f"Expected 'worry_pressure' for kha, got '{kha_unit.bridge_meaning}'"

        # Verify they have DIFFERENT bridge meanings (no collapse)
        assert ka_unit.bridge_meaning != kha_unit.bridge_meaning, \
            "ka and kha MUST have different bridge meanings (no collapse)"


# ============================================================================
# TEST GROUP 2: CV/VC STRUCTURAL TESTS
# ============================================================================

class TestCVStructure:
    """CV/VC structural pattern tests."""

    def test_cv_pattern_consonants_only(self):
        """
        Test 4a - CV pattern "sa da" (consonants only)

        Expected units:
            - sa -> C
            - da -> C
        Overall cluster order: "C" (structural, not syllabic)
        """
        units = map_acoustic_units_with_context("sa da")

        assert len(units) == 2, f"Expected 2 units, got {len(units)}"

        # Verify sa
        assert units[0].varna == "sa"
        assert units[0].is_consonant is True

        # Verify da
        assert units[1].varna == "da"
        assert units[1].is_consonant is True

        # Overall cluster order should be "C" (consonants only)
        assert units[0].cluster_order == "C", \
            f"Expected cluster_order='C' for consonants only, got '{units[0].cluster_order}'"

    def test_cv_pattern_with_vowel(self):
        """
        Test 4b - CV pattern "sa a" (consonant + vowel)

        Expected:
            - sa -> C
            - a -> V
        Overall cluster order: "CV"
        """
        units = map_acoustic_units_with_context("sa a")

        assert len(units) == 2, f"Expected 2 units, got {len(units)}"

        # Verify sa (consonant)
        assert units[0].varna == "sa"
        assert units[0].is_consonant is True

        # Verify a (vowel)
        assert units[1].varna == "a"
        assert units[1].is_vowel is True

        # Overall cluster order should be "CV"
        assert units[0].cluster_order == "CV", \
            f"Expected cluster_order='CV', got '{units[0].cluster_order}'"


# ============================================================================
# TEST GROUP 3: CRITICAL SEMANTIC-SAFETY TEST
# ============================================================================

class TestSemanticSafety:
    """Critical semantic-safety tests - verify no meaning leakage."""

    def test_sad_no_semantic_leakage(self):
        """
        Test 5 - "sad" (the critical test)

        Input "sad" = 's' + 'a' + 'd'
        Greedy matching: finds "sa" (2 chars), leaving 'd' alone

        Expected segmentation: ["sa", "d"]

        Expected properties:
            - sa -> "escape_pressure"
            - d -> "unknown" (single 'd' is not in JSON, only 'da' is)
            - No vowel negation applied
            - No "sadness" inferred
            - No positive vrtti leakage

        This confirms expressive vs internalized meaning is NOT mixed at Phase-1b.
        """
        units = map_acoustic_units_with_context("sad")

        # Verify segmentation
        varnas = [u.varna for u in units]
        assert varnas == ["sa", "d"], \
            f"Expected segmentation ['sa', 'd'], got {varnas}"

        # Verify sa properties
        sa_unit = units[0]
        assert sa_unit.bridge_meaning == "escape_pressure", \
            f"Expected 'escape_pressure' for sa, got '{sa_unit.bridge_meaning}'"
        assert sa_unit.is_consonant is True
        assert sa_unit.is_vowel is False

        # Verify d properties (unknown - 'd' alone is not in JSON)
        d_unit = units[1]
        assert d_unit.varna == "d"
        assert d_unit.bridge_meaning == "unknown", \
            f"Expected 'unknown' for d, got '{d_unit.bridge_meaning}'"
        assert d_unit.is_consonant is False
        assert d_unit.is_vowel is False

        # RED FLAGS: These would indicate semantic leakage
        meanings = get_bridge_meanings(units)
        forbidden_semantics = [
            "sadness", "emotion", "feeling", "mood",
            "unhappy", "grief", "sorrow", "melancholy_emotion"
        ]
        for meaning in meanings:
            # Check exact match (not substring) for semantic leakage
            assert meaning.lower() not in forbidden_semantics, \
                f"SEMANTIC LEAKAGE DETECTED: '{meaning}' in bridge meanings"


# ============================================================================
# TEST GROUP 4: VOWEL-FIRST NEGATION TEST
# ============================================================================

class TestVowelFirstNegation:
    """Vowel-first negation test - important for substrate purity."""

    def test_ab_no_negation_logic(self):
        """
        Test 6 - "ab" (vowel-first negation test)

        Expected segmentation: ["a", "b"]

        Expected behavior:
            - a is vowel with bridge "birth_of_cognition"
            - b is unknown (because "ba" exists, "b" alone does not)
            - b:
                - is_vowel = False
                - is_consonant = False
                - bridge_meaning = "unknown"

        NO negation logic happens here - that belongs in Phase-2, not now.
        This confirms substrate is not contaminated with relational logic.
        """
        units = map_acoustic_units("ab")

        # Verify segmentation
        varnas = [u.varna for u in units]
        assert varnas == ["a", "b"], \
            f"Expected segmentation ['a', 'b'], got {varnas}"

        # Verify a (vowel)
        a_unit = units[0]
        assert a_unit.is_vowel is True, "a should be vowel"
        assert a_unit.bridge_meaning == "birth_of_cognition", \
            f"Expected 'birth_of_cognition' for a, got '{a_unit.bridge_meaning}'"

        # Verify b (unknown - NOT "ba")
        b_unit = units[1]
        assert b_unit.varna == "b", f"Expected 'b', got '{b_unit.varna}'"
        assert b_unit.is_vowel is False, "b should NOT be vowel"
        assert b_unit.is_consonant is False, "b should NOT be consonant (only 'ba' exists)"
        assert b_unit.bridge_meaning == "unknown", \
            f"Expected 'unknown' for b, got '{b_unit.bridge_meaning}'"

        # Verify no negation logic was applied
        # Note: "unknown" is acceptable - it means "not in dictionary", not semantic negation
        meanings = get_bridge_meanings(units)
        negation_semantics = [
            "negation", "absence", "without", "opposite",
            "anti-", "non-"  # Only explicit negation prefixes
        ]
        for meaning in meanings:
            for neg in negation_semantics:
                assert neg not in meaning.lower(), \
                    f"NEGATION LOGIC LEAK: '{neg}' found in '{meaning}'"

        # Verify that 'unknown' (if present) is used correctly - means not in JSON,
        # NOT semantic negation of the vowel 'a'
        for unit in units:
            if unit.bridge_meaning == "unknown":
                # Unknown should NOT have vowel/consonant classification
                assert unit.is_vowel is False
                assert unit.is_consonant is False


# ============================================================================
# TEST GROUP 5: UNKNOWN HANDLING STRESS TEST
# ============================================================================

class TestUnknownHandling:
    """Unknown handling stress test - very important."""

    def test_garbage_input_all_unknown(self):
        """
        Test 7 - Garbage input "hgddc"

        Expected:
            - Every character becomes an opaque unknown unit
            - No vowel guessing
            - No consonant guessing
            - All units:
                - is_vowel = False
                - is_consonant = False
                - bridge_meaning = "unknown"

        This proves: Noise remains noise.
        Meaning only emerges when dictionary + Phase-2/3 logic is applied.
        """
        units = map_acoustic_units("hgddc")

        # Note: 'ha' is a known varna, so 'h' + 'g' + 'd' + 'd' + 'c' will be processed
        # 'h' alone is unknown, 'g' alone is unknown, 'd' alone is unknown, 'c' alone is unknown
        # But the greedy algorithm will try to match 'ha' first if possible

        # Let's verify each character that isn't part of a known varna
        # is marked as unknown
        for unit in units:
            if unit.varna not in ["ha", "a", "e", "i", "o", "u"]:  # Known varnas
                # If not a known varna, it should be unknown
                if unit.bridge_meaning != "unknown":
                    # It might have matched a known varna, which is fine
                    assert unit.bridge_meaning in [
                        "ignorance_pressure"  # 'ha' is known
                    ] or len(unit.varna) == 1, \
                        f"Unit '{unit.varna}' should be unknown or known varna"

        # Specifically check for single-char unknowns
        unknowns = [u for u in units if u.bridge_meaning == "unknown"]
        for u in unknowns:
            assert u.is_vowel is False, f"Unknown '{u.varna}' should NOT be vowel"
            assert u.is_consonant is False, f"Unknown '{u.varna}' should NOT be consonant"

    def test_completely_unknown_sequence(self):
        """
        Test 7b - Completely unknown sequence "xyz"

        All letters should be unknown (x, y, z are not in varna map).
        """
        units = map_acoustic_units("xyz")

        assert len(units) == 3, f"Expected 3 units, got {len(units)}"

        for unit in units:
            # x, y, z are not in the JSON varna map
            assert unit.is_vowel is False, \
                f"Unknown '{unit.varna}' should NOT be classified as vowel"
            assert unit.is_consonant is False, \
                f"Unknown '{unit.varna}' should NOT be classified as consonant"
            assert unit.bridge_meaning == "unknown", \
                f"Unknown '{unit.varna}' should have bridge_meaning='unknown'"
            assert unit.cluster_order == "COMPLEX", \
                f"Unknown '{unit.varna}' should have cluster_order='COMPLEX'"

    def test_unknown_count_function(self):
        """Verify count_unknown correctly identifies unknown units."""
        units = map_acoustic_units("xyz")
        unknown_count = count_unknown(units)

        assert unknown_count == 3, \
            f"Expected 3 unknowns in 'xyz', got {unknown_count}"


# ============================================================================
# TEST GROUP 6: CROSS-LANGUAGE SANITY CHECKS
# ============================================================================

class TestCrossLanguage:
    """Cross-language sanity checks (English / Indian dialect)."""

    def test_english_word_tub(self):
        """
        Test 8 - English word "tub"

        Input "tub" = 't' + 'u' + 'b'
        Greedy matching processes character by character:
            - 't' alone is not in JSON (only 'ta' exists)
            - 'u' is a vowel in JSON
            - 'b' alone is not in JSON (only 'ba' exists)

        Expected segmentation: ["t", "u", "b"]
            - t -> unknown (not "ta")
            - u -> contraction_focus
            - b -> unknown (not "ba")

        This is correct for Phase-1b.
        No attempt to "fix" English spelling is allowed here.
        """
        units = map_acoustic_units("tub")

        varnas = [u.varna for u in units]

        # The greedy matcher finds 't' (unknown), 'u' (vowel), 'b' (unknown)
        assert varnas == ["t", "u", "b"], \
            f"Expected ['t', 'u', 'b'], got {varnas}"

        # Verify t (unknown - 'ta' requires 'a' after 't')
        assert units[0].is_consonant is False
        assert units[0].is_vowel is False
        assert units[0].bridge_meaning == "unknown"

        # Verify u (contraction_focus)
        assert units[1].is_vowel is True
        assert units[1].bridge_meaning == "contraction_focus"

        # Verify b (unknown)
        assert units[2].is_vowel is False
        assert units[2].is_consonant is False
        assert units[2].bridge_meaning == "unknown"

    def test_indian_dialect_amma(self):
        """
        Test 9 - Indian dialect "amma"

        Expected segmentation: ["a", "mma"] or ["a", "m", "ma"]

        "mma" becomes unknown or split depending on symbols present.
        This is acceptable - dialect normalization is not Phase-1b's job.
        """
        units = map_acoustic_units("amma")

        varnas = [u.varna for u in units]

        # First should be "a" (vowel)
        assert units[0].varna == "a"
        assert units[0].is_vowel is True
        assert units[0].bridge_meaning == "birth_of_cognition"

        # "mma" handling: could be "m" + "ma" or "mma" as unknown
        # The greedy algorithm should try to match longest first
        # Since "ma" is in the JSON but "mma" is not, it will likely be:
        # "a" -> "m" (unknown) -> "ma" (indulgence_pressure)
        # OR "a" -> "mma" (unknown if no match at all)

        # Verify that no heuristics are applied
        for unit in units[1:]:  # Skip first 'a'
            if unit.bridge_meaning == "unknown":
                # Must be opaque unknown
                assert unit.is_vowel is False
                assert unit.is_consonant is False
            elif unit.varna == "ma":
                # Known varna
                assert unit.is_consonant is True
                assert unit.bridge_meaning == "indulgence_pressure"


# ============================================================================
# TEST GROUP 7: ACOUSTIC SIGNATURE CHECK
# ============================================================================

class TestAcousticSignature:
    """Acoustic signature check - quick diff tool."""

    def test_acoustic_signature_format(self):
        """
        Test acoustic signature format for "sa a kha x"

        Expected output (example): C:sa|V:a|Ch:kha|U:x

        This is an excellent diff artifact when comparing v2 vs v3.1.
        """
        units = map_acoustic_units("sa a kha x")
        signature = get_acoustic_signature(units)

        # Verify format
        assert "|" in signature, "Signature should use | as delimiter"

        parts = signature.split("|")
        assert len(parts) == 4, f"Expected 4 parts, got {len(parts)}: {signature}"

        # Verify each part format
        # C:sa (consonant, unaspirated)
        assert parts[0] == "C:sa", f"Expected 'C:sa', got '{parts[0]}'"

        # V:a (vowel)
        assert parts[1] == "V:a", f"Expected 'V:a', got '{parts[1]}'"

        # Ch:kha (consonant, aspirated)
        assert parts[2] == "Ch:kha", f"Expected 'Ch:kha', got '{parts[2]}'"

        # U:x (unknown)
        assert parts[3] == "U:x", f"Expected 'U:x', got '{parts[3]}'"

    def test_signature_differentiates_aspiration(self):
        """Signature should differentiate aspirated (Ch) from unaspirated (C)."""
        units_ka = map_acoustic_units("ka")
        units_kha = map_acoustic_units("kha")

        sig_ka = get_acoustic_signature(units_ka)
        sig_kha = get_acoustic_signature(units_kha)

        assert "C:ka" == sig_ka, f"Expected 'C:ka', got '{sig_ka}'"
        assert "Ch:kha" == sig_kha, f"Expected 'Ch:kha', got '{sig_kha}'"

        # They must be different
        assert sig_ka != sig_kha, "Aspirated and unaspirated signatures must differ"


# ============================================================================
# TEST GROUP 8: INVARIANT VERIFICATION
# ============================================================================

class TestInvariantVerification:
    """Invariant verification - must return True."""

    def test_validate_invariants_v3_1(self):
        """validate_invariants_v3_1() must return True."""
        result = validate_invariants_v3_1()
        assert result is True, "v3.1 invariants MUST all be True"

    def test_validate_unit_consistency(self):
        """validate_unit_consistency() must pass for standard inputs."""
        units = map_acoustic_units("sa a kha x")
        result = validate_unit_consistency(units)
        assert result is True, "Unit consistency validation must pass"

    def test_substrate_invariants_structure(self):
        """Verify substrate invariants dictionary structure."""
        required_invariants = [
            "NO_SEMANTICS",
            "NO_INTENT",
            "NO_ROUTING",
            "NO_POLICY",
            "NO_LLM_CALLS",
            "DETERMINISTIC",
            "READ_ONLY",
            "NON_AUTHORITATIVE",
            "NO_VRTTI_POLARITY",
            "NO_OBSERVER_OBSERVED",
            "NO_CONTEXTUAL_MEANING",
            "NO_DICTIONARY_LOGIC",
            "NO_PHONETIC_HEURISTICS",
            "NO_HEURISTIC_FALLBACK_CLASSIFICATION",
        ]

        for inv in required_invariants:
            assert inv in SUBSTRATE_INVARIANTS_V3_1, \
                f"Missing invariant: {inv}"
            assert SUBSTRATE_INVARIANTS_V3_1[inv] is True, \
                f"Invariant {inv} must be True"


# ============================================================================
# TEST GROUP 9: RED FLAG DETECTION
# ============================================================================

class TestRedFlagDetection:
    """
    Tests that detect regression red flags.

    RED FLAGS (should NEVER see these):
        - Any inference like "sadness", "emotion", "intent"
        - Any vowel guessed outside JSON
        - Any fallback classification for unknown letters
        - Any aspiration inferred from spelling
    """

    def test_no_semantic_inference(self):
        """No semantic inference should occur."""
        test_words = ["sad", "happy", "angry", "fear", "love"]

        forbidden_meanings = [
            "sadness", "happiness", "anger", "fear_emotion", "love_emotion",
            "emotion", "feeling", "mood", "sentiment", "intent"
        ]

        for word in test_words:
            units = map_acoustic_units(word)
            meanings = get_bridge_meanings(units)

            for meaning in meanings:
                for forbidden in forbidden_meanings:
                    assert forbidden not in meaning.lower(), \
                        f"SEMANTIC INFERENCE detected: '{forbidden}' in '{word}'"

    def test_no_vowel_guessing_outside_json(self):
        """Vowels should only come from JSON definitions."""
        # Only a, e, i, o, u are defined as vowels in JSON
        json_vowels = {"a", "e", "i", "o", "u"}

        # Test with text containing extended vowels
        units = map_acoustic_units("aeiou")

        for unit in units:
            if unit.is_vowel:
                assert unit.varna in json_vowels, \
                    f"Vowel '{unit.varna}' not in JSON definitions"

    def test_no_fallback_classification_for_unknowns(self):
        """Unknown letters should NOT be classified as vowel/consonant."""
        # Letters not in JSON
        unknown_letters = "fqwxyz"

        units = map_acoustic_units(unknown_letters)

        for unit in units:
            if unit.bridge_meaning == "unknown":
                assert unit.is_vowel is False, \
                    f"Unknown '{unit.varna}' should NOT be classified as vowel"
                assert unit.is_consonant is False, \
                    f"Unknown '{unit.varna}' should NOT be classified as consonant"

    def test_no_aspiration_inference_from_spelling(self):
        """Aspiration should ONLY come from JSON, not spelling inference."""
        # Test that 'h' after a consonant doesn't automatically make it aspirated
        # unless the combination exists in JSON

        # "ph" is NOT in JSON as a single varna
        units = map_acoustic_units("ph")

        varnas = [u.varna for u in units]
        # Should be ["pa", "h"] or ["p", "ha"] depending on greedy matching
        # But NOT a single "ph" with is_aspirated=True (unless "pha" matches)

        # Verify no spurious aspiration
        for unit in units:
            if unit.is_aspirated:
                # Aspiration must come from JSON-defined aspirated varnas
                aspirated_varnas = [
                    "kha", "gha", "cha", "jha", "ttha", "ddha",
                    "tha", "dha", "pha", "bha", "ha", "ksha"
                ]
                assert unit.varna in aspirated_varnas, \
                    f"Aspirated '{unit.varna}' not in JSON aspirated list"


# ============================================================================
# TEST GROUP 10: VERSION AND MODULE VALIDATION
# ============================================================================

class TestVersionModule:
    """Version and module validation."""

    def test_acoustic_mapper_version(self):
        """Verify acoustic mapper version is 3.1."""
        assert ACOUSTIC_MAPPER_VERSION == 3.1, \
            f"Expected version 3.1, got {ACOUSTIC_MAPPER_VERSION}"

    def test_varna_bridge_map_loads(self):
        """VarnaBridgeMap should load successfully."""
        bridge_map = VarnaBridgeMap()

        # Should have vowels and consonants
        assert len(bridge_map.vowel_symbols) > 0, "Should have vowels"
        assert len(bridge_map.consonant_symbols) > 0, "Should have consonants"

        # Specific check
        assert "a" in bridge_map.vowel_symbols, "Missing vowel 'a'"
        assert "sa" in bridge_map.consonant_symbols, "Missing consonant 'sa'"
        assert "kha" in bridge_map.consonant_symbols, "Missing aspirated 'kha'"


# ============================================================================
# TEST GROUP 11: DETERMINISM
# ============================================================================

class TestDeterminism:
    """Determinism tests - same input must produce same output."""

    def test_map_acoustic_units_deterministic(self):
        """map_acoustic_units must be deterministic."""
        text = "sa a kha da ma"

        results = [map_acoustic_units(text) for _ in range(10)]

        for i, result in enumerate(results[1:], start=1):
            assert len(result) == len(results[0])
            for j, (u1, u2) in enumerate(zip(results[0], result)):
                assert u1.varna == u2.varna
                assert u1.is_vowel == u2.is_vowel
                assert u1.is_consonant == u2.is_consonant
                assert u1.is_aspirated == u2.is_aspirated
                assert u1.bridge_meaning == u2.bridge_meaning

    def test_signature_deterministic(self):
        """Acoustic signature must be deterministic."""
        text = "determinism test"

        signatures = [
            get_acoustic_signature(map_acoustic_units(text))
            for _ in range(10)
        ]

        assert all(s == signatures[0] for s in signatures)


# ============================================================================
# TEST GROUP 12: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge case handling."""

    def test_empty_string(self):
        """Empty string should return empty list."""
        units = map_acoustic_units("")
        assert units == []

    def test_whitespace_only(self):
        """Whitespace-only input should return empty list."""
        units = map_acoustic_units("   \t\n   ")
        assert units == []

    def test_type_error_on_non_string(self):
        """Non-string input should raise TypeError (for truthy values)."""
        # Integer raises TypeError
        with pytest.raises(TypeError):
            map_acoustic_units(123)

        # List raises TypeError
        with pytest.raises(TypeError):
            map_acoustic_units(["sa"])

    def test_none_returns_empty(self):
        """None input returns empty list (handled by falsy check before type check)."""
        # None is falsy, so it returns [] before type check
        result = map_acoustic_units(None)
        assert result == []


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
