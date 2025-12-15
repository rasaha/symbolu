"""
Phase-2 Modifier Tests (v1.0)
=============================

Test Goals: Phase-2 structural modifier verification ONLY.
            Phase-1b must remain FROZEN and UNALTERED.

This test suite verifies:
    Group A: Structural Integrity
    Group B: Vowel-First Negation
    Group C: Expressive vs Internalized (semantic non-leakage)
    Group D: Aspirated Contrast
    Group E: Unknown Blocking
    Group F: Regression Guard (Phase-1b unchanged)

Version: 1.0
Date: 2025-12-15

ABSOLUTE RULES:
    - DO NOT edit Phase-1b code
    - DO NOT edit Phase-1b tests
    - DO NOT infer semantics
    - DO NOT collapse bridge meanings
    - DO NOT re-tokenize
"""

import pytest
import sys
import hashlib
from pathlib import Path
from typing import List

# Add experiments directory to path for mappers
sys.path.insert(0, str(Path(__file__).parent.parent / "docs" / "experiments"))

# Phase-1b imports (FROZEN - DO NOT MODIFY)
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

# Phase-2 imports (NEW - under test)
from phase2_modifier_engine_v3_2 import (
    apply_modifiers,
    Phase2ModifiedUnit,
    Phase2Modifier,
    ModifierEnvelope,
    extract_phase1b_units,
    compute_phase1b_hash,
    verify_phase1b_integrity,
    get_modifiers_summary,
    validate_invariants_v3_2,
    validate_modified_unit,
    PHASE2_INVARIANTS_V3_2,
    PHASE2_ENGINE_VERSION,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_phase1b_unit_hash(units: List[AcousticBridgeUnit]) -> str:
    """Compute hash of Phase-1b units for integrity verification."""
    if not units:
        return hashlib.sha256(b"empty").hexdigest()[:32]

    hash_parts = []
    for unit in units:
        part = (
            f"{unit.varna}|{unit.index}|{unit.is_vowel}|"
            f"{unit.is_consonant}|{unit.is_aspirated}|"
            f"{unit.bridge_meaning}|{unit.cluster_order}"
        )
        hash_parts.append(part)

    combined = "||".join(hash_parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def has_modifier_type(modified_unit: Phase2ModifiedUnit, modifier_type: str) -> bool:
    """Check if a modified unit has a specific relational modifier type."""
    for mod in modified_unit.modifiers.relational_modifiers:
        if mod.modifier_type == modifier_type:
            return True
    return False


def get_modifier_triggers(modified_unit: Phase2ModifiedUnit) -> List[str]:
    """Get list of trigger strings for all relational modifiers on a unit."""
    return [mod.trigger for mod in modified_unit.modifiers.relational_modifiers]


# ============================================================================
# GROUP A — STRUCTURAL INTEGRITY
# ============================================================================

class TestGroupA_StructuralIntegrity:
    """
    Group A: Structural Integrity Tests

    Verifies:
        1. Phase-1b output hash unchanged after Phase-2
        2. Same number of base units
        3. Modifiers exist separately from base units
    """

    def test_phase1b_hash_unchanged(self):
        """
        Test A1: Phase-1b output hash must be unchanged after Phase-2 processing.

        This is the CRITICAL integrity test.
        """
        text = "sa a kha da ma"

        # Phase-1b processing
        phase1b_units = map_acoustic_units(text)
        original_hash = get_phase1b_unit_hash(phase1b_units)

        # Phase-2 processing
        modified_units = apply_modifiers(phase1b_units)

        # Extract Phase-1b units from Phase-2 output
        extracted_units = extract_phase1b_units(modified_units)
        extracted_hash = get_phase1b_unit_hash(extracted_units)

        # CRITICAL: Hash must be identical
        assert original_hash == extracted_hash, \
            f"Phase-1b hash CHANGED after Phase-2! Original: {original_hash}, After: {extracted_hash}"

    def test_same_number_of_base_units(self):
        """
        Test A2: Phase-2 must preserve the exact number of Phase-1b units.
        """
        texts = ["sa", "sa a kha", "xyz", "sad", "ab", "ka kha"]

        for text in texts:
            phase1b_units = map_acoustic_units(text)
            modified_units = apply_modifiers(phase1b_units)

            assert len(modified_units) == len(phase1b_units), \
                f"Unit count mismatch for '{text}': Phase-1b={len(phase1b_units)}, Phase-2={len(modified_units)}"

    def test_modifiers_exist_separately(self):
        """
        Test A3: Modifiers must be attached separately, not merged into base units.
        """
        phase1b_units = map_acoustic_units("sa a")
        modified_units = apply_modifiers(phase1b_units)

        for modified in modified_units:
            # source_unit must be intact
            assert hasattr(modified, 'source_unit'), "Missing source_unit attribute"
            assert hasattr(modified, 'modifiers'), "Missing modifiers attribute"

            # source_unit should match original Phase-1b unit structure
            assert hasattr(modified.source_unit, 'varna'), "source_unit missing varna"
            assert hasattr(modified.source_unit, 'bridge_meaning'), "source_unit missing bridge_meaning"

            # modifiers should be a ModifierEnvelope
            assert isinstance(modified.modifiers, ModifierEnvelope), \
                f"modifiers should be ModifierEnvelope, got {type(modified.modifiers)}"

    def test_reversibility_guarantee(self):
        """
        Test A4: Original Phase-1b units must be fully recoverable from Phase-2 output.
        """
        text = "sa a kha x da"
        phase1b_units = map_acoustic_units(text)
        modified_units = apply_modifiers(phase1b_units)

        # Use the verify_phase1b_integrity function
        assert verify_phase1b_integrity(phase1b_units, modified_units), \
            "Phase-1b integrity verification FAILED - units were modified!"

    def test_phase2_invariants_hold(self):
        """
        Test A5: All Phase-2 invariants must be True.
        """
        result = validate_invariants_v3_2()
        assert result is True, "Phase-2 invariants validation failed"

    def test_modified_unit_validation(self):
        """
        Test A6: All modified units must pass structural validation.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        modified_units = apply_modifiers(phase1b_units)

        for modified in modified_units:
            result = validate_modified_unit(modified)
            assert result is True, f"Modified unit validation failed for {modified.source_unit.varna}"


# ============================================================================
# GROUP B — VOWEL-FIRST NEGATION
# ============================================================================

class TestGroupB_VowelFirstNegation:
    """
    Group B: Vowel-First Negation Tests

    Input: "ab"

    Expected:
        - Phase-1b: ["a", "b"]
        - Phase-2:
            - Modifier: NEGATION on "b" (vowel precedes consonant-like position)
            - No change to "a"

    Note: "b" alone is unknown (only "ba" exists in JSON), so strict negation
    rule only applies when the following unit is a consonant. We test the
    principle here.
    """

    def test_ab_phase1b_unchanged(self):
        """
        Test B1: "ab" Phase-1b output must be unchanged.
        """
        units = map_acoustic_units("ab")

        assert len(units) == 2
        assert units[0].varna == "a"
        assert units[1].varna == "b"

        # Verify bridge meanings
        assert units[0].bridge_meaning == "birth_of_cognition"
        assert units[1].bridge_meaning == "unknown"  # 'b' alone is not in JSON

    def test_ab_no_phase1b_modification(self):
        """
        Test B2: Phase-2 processing must NOT modify Phase-1b units for "ab".
        """
        phase1b_units = map_acoustic_units("ab")
        original_hash = get_phase1b_unit_hash(phase1b_units)

        modified_units = apply_modifiers(phase1b_units)
        extracted_hash = get_phase1b_unit_hash(extract_phase1b_units(modified_units))

        assert original_hash == extracted_hash, "Phase-1b was modified during Phase-2!"

    def test_ab_modifiers_present(self):
        """
        Test B3: "ab" should have structural modifiers attached.
        """
        phase1b_units = map_acoustic_units("ab")
        modified_units = apply_modifiers(phase1b_units)

        # Both units should have modifiers
        for modified in modified_units:
            assert modified.modifiers is not None
            assert modified.modifiers.adjacency_type is not None
            assert modified.modifiers.boundary_position is not None

    def test_vowel_consonant_pattern_aba(self):
        """
        Test B4: "a ba" (vowel + consonant) should trigger negation modifier.

        "a" is vowel, "ba" is consonant -> NEGATION on "ba"
        """
        phase1b_units = map_acoustic_units("a ba")
        modified_units = apply_modifiers(phase1b_units)

        assert len(modified_units) == 2

        # "a" should NOT have negation
        a_unit = modified_units[0]
        assert not has_modifier_type(a_unit, "NEGATION"), \
            "Vowel 'a' should NOT have NEGATION modifier"

        # "ba" SHOULD have NEGATION (vowel precedes it)
        ba_unit = modified_units[1]
        assert has_modifier_type(ba_unit, "NEGATION"), \
            "Consonant 'ba' after vowel should have NEGATION modifier"

        # Verify trigger is correct
        triggers = get_modifier_triggers(ba_unit)
        assert "vowel_first" in triggers, \
            f"Expected 'vowel_first' trigger, got {triggers}"

    def test_vowel_consonant_transition_type(self):
        """
        Test B5: Vowel-consonant transition should be properly recorded.
        """
        phase1b_units = map_acoustic_units("a ba")
        modified_units = apply_modifiers(phase1b_units)

        # Check transition from "a" to "ba"
        a_unit = modified_units[0]
        assert a_unit.modifiers.vowel_consonant_transition == "V_to_C", \
            f"Expected V_to_C transition, got {a_unit.modifiers.vowel_consonant_transition}"


# ============================================================================
# GROUP C — EXPRESSIVE VS INTERNALIZED (No Semantic Inference)
# ============================================================================

class TestGroupC_ExpressiveInternalized:
    """
    Group C: Expressive vs Internalized Tests

    Input: "sad"

    Expected:
        - Phase-1b: ["sa", "d"]
        - Phase-2:
            - Structural modifiers only
            - NO sadness inference
            - NO emotion classification
    """

    def test_sad_phase1b_segmentation(self):
        """
        Test C1: "sad" should segment to ["sa", "d"].
        """
        units = map_acoustic_units("sad")

        varnas = [u.varna for u in units]
        assert varnas == ["sa", "d"], f"Expected ['sa', 'd'], got {varnas}"

    def test_sad_no_semantic_leakage_phase2(self):
        """
        Test C2: Phase-2 must NOT introduce semantic inference for "sad".

        FORBIDDEN inferences:
            - "sadness"
            - "emotion"
            - "feeling"
            - "mood"
        """
        phase1b_units = map_acoustic_units("sad")
        modified_units = apply_modifiers(phase1b_units)

        # Get all modifiers summary
        summary = get_modifiers_summary(modified_units)

        # Convert to string for searching
        summary_str = str(summary).lower()

        forbidden_terms = [
            "sadness", "emotion", "feeling", "mood",
            "unhappy", "grief", "sorrow", "melancholy"
        ]

        for term in forbidden_terms:
            assert term not in summary_str, \
                f"SEMANTIC LEAKAGE: '{term}' found in Phase-2 modifiers!"

    def test_sad_d_has_structural_modifier_only(self):
        """
        Test C3: The "d" unit should have structural modifiers, not semantic.
        """
        phase1b_units = map_acoustic_units("sad")
        modified_units = apply_modifiers(phase1b_units)

        d_unit = modified_units[1]  # "d" is second unit

        # Should have unknown barrier (d is unknown)
        assert d_unit.modifiers.unknown_barrier == "is_unknown", \
            f"Expected 'is_unknown' for d, got {d_unit.modifiers.unknown_barrier}"

        # Check any relational modifiers are structural, not semantic
        for mod in d_unit.modifiers.relational_modifiers:
            assert mod.modifier_type in ["NEGATION", "INVERSION", "AMPLIFICATION", "ATTENUATION", "MASK"], \
                f"Unexpected modifier type: {mod.modifier_type}"

            # Trigger should be structural
            assert mod.trigger in ["vowel_first", "aspirated", "unknown_barrier", "cluster_pattern"], \
                f"Unexpected trigger (possible semantic): {mod.trigger}"

    def test_sad_phase1b_integrity(self):
        """
        Test C4: Phase-1b units for "sad" must be unchanged after Phase-2.
        """
        phase1b_units = map_acoustic_units("sad")
        modified_units = apply_modifiers(phase1b_units)

        assert verify_phase1b_integrity(phase1b_units, modified_units), \
            "Phase-1b integrity FAILED for 'sad'"


# ============================================================================
# GROUP D — ASPIRATED CONTRAST
# ============================================================================

class TestGroupD_AspiratedContrast:
    """
    Group D: Aspirated Contrast Tests

    Input: "ka kha"

    Expected:
        - Phase-1b preserved
        - Phase-2:
            - kha marked as externally projected (aspirated)
            - ka internal (unaspirated)
            - NO semantic inference about intensity/force
    """

    def test_ka_kha_phase1b_preserved(self):
        """
        Test D1: "ka kha" Phase-1b units must be preserved.
        """
        phase1b_units = map_acoustic_units("ka kha")

        assert len(phase1b_units) == 2
        assert phase1b_units[0].varna == "ka"
        assert phase1b_units[1].varna == "kha"

        # Aspiration flags
        assert phase1b_units[0].is_aspirated is False
        assert phase1b_units[1].is_aspirated is True

    def test_ka_kha_aspiration_contrast_modifier(self):
        """
        Test D2: Aspiration contrast should be recorded as 'contrast_present'.
        """
        phase1b_units = map_acoustic_units("ka kha")
        modified_units = apply_modifiers(phase1b_units)

        # Check aspiration contrast from ka -> kha
        ka_unit = modified_units[0]
        assert ka_unit.modifiers.aspiration_contrast == "contrast_present", \
            f"Expected 'contrast_present', got {ka_unit.modifiers.aspiration_contrast}"

    def test_kha_has_mask_modifier(self):
        """
        Test D3: Aspirated "kha" should have MASK modifier (externally projected).
        """
        phase1b_units = map_acoustic_units("ka kha")
        modified_units = apply_modifiers(phase1b_units)

        kha_unit = modified_units[1]

        # kha is aspirated, should have MASK modifier
        assert has_modifier_type(kha_unit, "MASK"), \
            "Aspirated 'kha' should have MASK modifier"

        triggers = get_modifier_triggers(kha_unit)
        assert "aspirated" in triggers, \
            f"Expected 'aspirated' trigger for kha, got {triggers}"

    def test_ka_no_mask_modifier(self):
        """
        Test D4: Unaspirated "ka" should NOT have MASK modifier.
        """
        phase1b_units = map_acoustic_units("ka kha")
        modified_units = apply_modifiers(phase1b_units)

        ka_unit = modified_units[0]

        # ka is unaspirated, should NOT have MASK
        assert not has_modifier_type(ka_unit, "MASK"), \
            "Unaspirated 'ka' should NOT have MASK modifier"

    def test_ka_kha_no_semantic_inference(self):
        """
        Test D5: NO semantic inference about intensity/force/emotion.
        """
        phase1b_units = map_acoustic_units("ka kha")
        modified_units = apply_modifiers(phase1b_units)

        summary = get_modifiers_summary(modified_units)
        summary_str = str(summary).lower()

        forbidden_terms = [
            "intensity", "force", "stress", "emphasis",
            "emotion", "feeling", "observer", "observed"
        ]

        for term in forbidden_terms:
            assert term not in summary_str, \
                f"SEMANTIC LEAKAGE: '{term}' found in aspiration modifiers!"

    def test_ka_kha_phase1b_integrity(self):
        """
        Test D6: Phase-1b integrity for "ka kha".
        """
        phase1b_units = map_acoustic_units("ka kha")
        modified_units = apply_modifiers(phase1b_units)

        assert verify_phase1b_integrity(phase1b_units, modified_units), \
            "Phase-1b integrity FAILED for 'ka kha'"


# ============================================================================
# GROUP E — UNKNOWN BLOCKING
# ============================================================================

class TestGroupE_UnknownBlocking:
    """
    Group E: Unknown Blocking Tests

    Input: "a x ba"

    Expected:
        - Modifier does NOT propagate across "x" (unknown barrier)
        - Each segment is isolated by unknown
    """

    def test_a_x_ba_segmentation(self):
        """
        Test E1: "a x ba" should segment correctly with unknown in middle.
        """
        units = map_acoustic_units("a x ba")

        varnas = [u.varna for u in units]
        assert varnas == ["a", "x", "ba"], f"Expected ['a', 'x', 'ba'], got {varnas}"

        # Verify x is unknown
        assert units[1].bridge_meaning == "unknown"
        assert units[1].is_vowel is False
        assert units[1].is_consonant is False

    def test_unknown_blocks_negation_propagation(self):
        """
        Test E2: NEGATION from "a" should NOT propagate to "ba" across "x".

        Without unknown:
            "a ba" -> NEGATION on "ba"

        With unknown:
            "a x ba" -> x blocks propagation, "ba" should NOT get negation from "a"
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        # "a" is index 0
        # "x" is index 1 (unknown)
        # "ba" is index 2

        ba_unit = modified_units[2]

        # ba comes after unknown x, not directly after vowel a
        # So vowel_first negation should NOT apply
        triggers = get_modifier_triggers(ba_unit)
        assert "vowel_first" not in triggers, \
            "NEGATION should NOT propagate across unknown barrier!"

    def test_unknown_has_barrier_modifier(self):
        """
        Test E3: Unknown "x" should have barrier modifiers.
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        x_unit = modified_units[1]

        # Should be marked as unknown
        assert x_unit.modifiers.unknown_barrier == "is_unknown", \
            f"Expected 'is_unknown' for x, got {x_unit.modifiers.unknown_barrier}"

        # Should have ATTENUATION modifier for blocking
        assert has_modifier_type(x_unit, "ATTENUATION"), \
            "Unknown 'x' should have ATTENUATION (barrier) modifier"

        triggers = get_modifier_triggers(x_unit)
        assert "unknown_barrier" in triggers

    def test_units_adjacent_to_unknown_marked(self):
        """
        Test E4: Units adjacent to unknown should be marked appropriately.
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        # "a" is left of unknown
        a_unit = modified_units[0]
        assert a_unit.modifiers.unknown_barrier == "left_of_unknown", \
            f"Expected 'left_of_unknown' for a, got {a_unit.modifiers.unknown_barrier}"

        # "ba" is right of unknown
        ba_unit = modified_units[2]
        assert ba_unit.modifiers.unknown_barrier == "right_of_unknown", \
            f"Expected 'right_of_unknown' for ba, got {ba_unit.modifiers.unknown_barrier}"

    def test_sequence_class_mixed(self):
        """
        Test E5: Sequence "a x ba" should have sequence_class = "mixed".
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        # All units should have same sequence_class (it's sequence-level)
        assert modified_units[0].modifiers.sequence_class == "mixed", \
            f"Expected 'mixed', got {modified_units[0].modifiers.sequence_class}"

    def test_continuity_interrupted_by_unknown(self):
        """
        Test E6: Continuity should show interruption at unknown.
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        spans = modified_units[0].modifiers.continuity_spans

        # Should have multiple spans due to interruption
        span_types = [s.type for s in spans]
        assert "interrupted" in span_types, \
            f"Expected 'interrupted' span due to unknown, got {span_types}"

    def test_a_x_ba_phase1b_integrity(self):
        """
        Test E7: Phase-1b integrity for "a x ba".
        """
        phase1b_units = map_acoustic_units("a x ba")
        modified_units = apply_modifiers(phase1b_units)

        assert verify_phase1b_integrity(phase1b_units, modified_units), \
            "Phase-1b integrity FAILED for 'a x ba'"


# ============================================================================
# GROUP F — REGRESSION GUARD (Phase-1b Unchanged)
# ============================================================================

class TestGroupF_RegressionGuard:
    """
    Group F: Regression Guard Tests

    Re-run key Phase-1b tests to ensure they still pass.
    Phase-1b code MUST NOT be modified.
    """

    def test_phase1b_version_unchanged(self):
        """
        Test F1: Phase-1b mapper version must still be 3.1.
        """
        assert ACOUSTIC_MAPPER_VERSION == 3.1, \
            f"Phase-1b version changed! Expected 3.1, got {ACOUSTIC_MAPPER_VERSION}"

    def test_phase1b_invariants_still_valid(self):
        """
        Test F2: Phase-1b substrate invariants must all be True.
        """
        result = validate_invariants_v3_1()
        assert result is True, "Phase-1b invariants FAILED"

    def test_phase1b_single_consonant_sa(self):
        """
        Test F3: Phase-1b single consonant "sa" - regression check.
        """
        units = map_acoustic_units("sa")

        assert len(units) == 1
        assert units[0].varna == "sa"
        assert units[0].is_consonant is True
        assert units[0].bridge_meaning == "escape_pressure"

    def test_phase1b_single_vowel_a(self):
        """
        Test F4: Phase-1b single vowel "a" - regression check.
        """
        units = map_acoustic_units("a")

        assert len(units) == 1
        assert units[0].varna == "a"
        assert units[0].is_vowel is True
        assert units[0].bridge_meaning == "birth_of_cognition"

    def test_phase1b_aspirated_contrast(self):
        """
        Test F5: Phase-1b aspirated contrast "ka kha" - regression check.
        """
        units = map_acoustic_units("ka kha")

        assert len(units) == 2
        assert units[0].is_aspirated is False
        assert units[1].is_aspirated is True
        assert units[0].bridge_meaning == "hope_pressure"
        assert units[1].bridge_meaning == "worry_pressure"

    def test_phase1b_unknown_handling(self):
        """
        Test F6: Phase-1b unknown handling "xyz" - regression check.
        """
        units = map_acoustic_units("xyz")

        assert len(units) == 3
        for unit in units:
            assert unit.is_vowel is False
            assert unit.is_consonant is False
            assert unit.bridge_meaning == "unknown"
            assert unit.cluster_order == "COMPLEX"

    def test_phase1b_sad_no_semantic_inference(self):
        """
        Test F7: Phase-1b "sad" - no semantic inference regression check.
        """
        units = map_acoustic_units("sad")
        meanings = get_bridge_meanings(units)

        forbidden = ["sadness", "emotion", "feeling", "mood"]
        for meaning in meanings:
            for f in forbidden:
                assert f not in meaning.lower(), \
                    f"Phase-1b REGRESSION: semantic '{f}' found in 'sad'"

    def test_phase1b_acoustic_signature_format(self):
        """
        Test F8: Phase-1b acoustic signature format - regression check.
        """
        units = map_acoustic_units("sa a kha x")
        signature = get_acoustic_signature(units)

        expected_parts = ["C:sa", "V:a", "Ch:kha", "U:x"]
        parts = signature.split("|")

        assert parts == expected_parts, \
            f"Phase-1b signature REGRESSION: expected {expected_parts}, got {parts}"

    def test_phase1b_varna_bridge_map_loads(self):
        """
        Test F9: VarnaBridgeMap must load successfully - regression check.
        """
        bridge_map = VarnaBridgeMap()

        assert "a" in bridge_map.vowel_symbols
        assert "sa" in bridge_map.consonant_symbols
        assert "kha" in bridge_map.consonant_symbols

    def test_phase1b_determinism(self):
        """
        Test F10: Phase-1b determinism - regression check.
        """
        text = "sa a kha da ma"

        results = [map_acoustic_units(text) for _ in range(10)]

        for result in results[1:]:
            assert len(result) == len(results[0])
            for u1, u2 in zip(results[0], result):
                assert u1.varna == u2.varna
                assert u1.bridge_meaning == u2.bridge_meaning


# ============================================================================
# ADDITIONAL TESTS - EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Additional edge case tests for Phase-2."""

    def test_empty_input(self):
        """Empty input should return empty list."""
        phase1b_units = map_acoustic_units("")
        modified_units = apply_modifiers(phase1b_units)

        assert modified_units == []

    def test_single_vowel_modifiers(self):
        """Single vowel should have correct structural modifiers."""
        phase1b_units = map_acoustic_units("a")
        modified_units = apply_modifiers(phase1b_units)

        assert len(modified_units) == 1

        unit = modified_units[0]
        assert unit.modifiers.adjacency_type == "isolated"
        assert unit.modifiers.boundary_position == "singleton"
        assert unit.modifiers.sequence_class == "all_known"

    def test_all_unknown_sequence(self):
        """All unknown sequence should have sequence_class = 'all_unknown'."""
        phase1b_units = map_acoustic_units("xyz")
        modified_units = apply_modifiers(phase1b_units)

        assert modified_units[0].modifiers.sequence_class == "all_unknown"

    def test_repetition_marker(self):
        """Adjacent identical varnas should be marked as repeated."""
        # "a a" -> two vowels
        phase1b_units = map_acoustic_units("a a")
        modified_units = apply_modifiers(phase1b_units)

        assert modified_units[0].modifiers.repetition_marker == "repeated"

    def test_phase2_version_correct(self):
        """Phase-2 engine version should be 3.2."""
        assert PHASE2_ENGINE_VERSION == "3.2"


# ============================================================================
# SUMMARY TEST - FINAL VERIFICATION
# ============================================================================

class TestFinalVerification:
    """Final verification that Phase-2 is isolated and non-contaminating."""

    def test_phase2_isolated_and_non_contaminating(self):
        """
        FINAL TEST: Verify Phase-2 is isolated and non-contaminating.

        This test runs through multiple inputs and verifies:
            1. Phase-1b units are always unchanged
            2. No semantic inference occurs
            3. All modifiers are structural only
        """
        test_inputs = [
            "sa", "a", "sad", "ab", "ka kha", "a x ba", "xyz",
            "sa a kha", "a ba", "happy", "angry"
        ]

        all_passed = True
        failures = []

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            original_hash = get_phase1b_unit_hash(phase1b_units)

            modified_units = apply_modifiers(phase1b_units)
            extracted_hash = get_phase1b_unit_hash(extract_phase1b_units(modified_units))

            if original_hash != extracted_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-1b hash changed")

            # Check for semantic leakage
            summary_str = str(get_modifiers_summary(modified_units)).lower()
            forbidden = ["emotion", "feeling", "sadness", "happiness", "anger"]

            for term in forbidden:
                if term in summary_str:
                    all_passed = False
                    failures.append(f"'{text}': semantic term '{term}' found")

        if not all_passed:
            pytest.fail(f"Phase-2 contamination detected:\n" + "\n".join(failures))

        # Success message (implicit in test passing)
        # "Phase-2 is isolated and non-contaminating"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
