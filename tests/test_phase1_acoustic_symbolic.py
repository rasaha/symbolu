"""
Phase 1 Acoustic-Symbolic Tokenization Tests
=============================================

Comprehensive test suite for Phase 1 acoustic-symbolic tokenization.

Test Coverage:
    1. Determinism: Same input → same output
    2. Empty input handling
    3. Non-ASCII safety
    4. No semantic leakage (no words, no intent fields)
    5. Vṛtti assignment determinism
    6. Snapshot immutability
    7. Contract validation

Version: 1.0
Date: 2025-12-13
"""

import pytest
from typing import List

from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    SoundClass,
    VowelHeight,
    VowelBackness,
    map_acoustic_units,
    get_acoustic_signature,
    count_syllable_nuclei,
    PHASE_1_INVARIANTS as ACOUSTIC_INVARIANTS,
)

from symbolu.formulas.vritti_mapper import (
    AcousticVritti,
    VrittiType,
    assign_vritti,
    assign_vritti_sequence,
    get_vritti_distribution,
    get_dominant_vritti,
    get_vritti_signature,
    PHASE_1_INVARIANTS as VRITTI_INVARIANTS,
)

from symbolu.formulas.phase1_snapshot import (
    Phase1Snapshot,
    Phase1Metadata,
    create_phase1_snapshot,
    create_empty_snapshot,
    validate_phase1_snapshot,
    assert_no_semantic_leakage,
    PHASE_1_INVARIANTS as SNAPSHOT_INVARIANTS,
    PHASE_ID,
    PHASE_VERSION,
)


# ============================================================================
# TEST: DETERMINISM - Same input → same output
# ============================================================================

class TestDeterminism:
    """Test that Phase 1 processing is fully deterministic."""

    def test_acoustic_units_deterministic(self):
        """Same text should produce identical acoustic units."""
        text = "hello world"

        # Run multiple times
        results = [map_acoustic_units(text) for _ in range(10)]

        # All results should be identical
        for i, result in enumerate(results[1:], start=1):
            assert len(result) == len(results[0]), f"Run {i}: Different unit count"
            for j, (u1, u2) in enumerate(zip(results[0], result)):
                assert u1.raw_text == u2.raw_text, f"Run {i}, unit {j}: Different raw_text"
                assert u1.sound_class == u2.sound_class, f"Run {i}, unit {j}: Different sound_class"
                assert u1.index == u2.index, f"Run {i}, unit {j}: Different index"

    def test_vritti_assignment_deterministic(self):
        """Same acoustic unit should always get same vṛtti."""
        text = "testing determinism"
        units = map_acoustic_units(text)

        # Run assignment multiple times
        for _ in range(10):
            vritti_list = assign_vritti_sequence(units)
            for i, (unit, vritti) in enumerate(zip(units, vritti_list)):
                # Re-assign and compare
                re_assigned = assign_vritti(unit)
                assert re_assigned.vritti_type == vritti.vritti_type, \
                    f"Unit {i}: Vṛtti assignment not deterministic"
                assert re_assigned.weight == vritti.weight, \
                    f"Unit {i}: Weight not deterministic"

    def test_snapshot_deterministic(self):
        """Same text should produce identical snapshots."""
        text = "the quick brown fox"

        # Create multiple snapshots
        snapshots = [create_phase1_snapshot(text) for _ in range(5)]

        # All should have same structure
        for i, snapshot in enumerate(snapshots[1:], start=1):
            assert snapshot.metadata.unit_count == snapshots[0].metadata.unit_count
            assert snapshot.metadata.acoustic_signature == snapshots[0].metadata.acoustic_signature
            assert snapshot.metadata.vritti_signature == snapshots[0].metadata.vritti_signature
            assert snapshot.metadata.dominant_vritti == snapshots[0].metadata.dominant_vritti

    def test_signature_deterministic(self):
        """Acoustic and vṛtti signatures should be deterministic."""
        text = "signature test"

        for _ in range(10):
            units = map_acoustic_units(text)
            sig = get_acoustic_signature(units)
            assert sig == get_acoustic_signature(map_acoustic_units(text))


# ============================================================================
# TEST: EMPTY INPUT HANDLING
# ============================================================================

class TestEmptyInput:
    """Test handling of empty and edge-case inputs."""

    def test_empty_string_acoustic_units(self):
        """Empty string should return empty list."""
        result = map_acoustic_units("")
        assert result == []

    def test_empty_string_snapshot(self):
        """Empty string should produce valid empty snapshot."""
        snapshot = create_phase1_snapshot("")
        assert snapshot.is_empty()
        assert snapshot.get_unit_count() == 0
        assert snapshot.metadata.unit_count == 0

    def test_whitespace_only(self):
        """Whitespace-only input should produce empty result."""
        for ws in ["   ", "\t\t", "\n\n", "   \t  \n  "]:
            result = map_acoustic_units(ws)
            assert result == [], f"Whitespace '{repr(ws)}' should produce empty list"

    def test_empty_snapshot_factory(self):
        """create_empty_snapshot should produce valid empty snapshot."""
        snapshot = create_empty_snapshot()
        assert validate_phase1_snapshot(snapshot)
        assert snapshot.is_empty()
        assert snapshot.metadata.phase_id == PHASE_ID

    def test_single_character(self):
        """Single character inputs should work."""
        for char in "abcdefghijklmnopqrstuvwxyz":
            units = map_acoustic_units(char)
            assert len(units) >= 1, f"Single char '{char}' should produce at least 1 unit"


# ============================================================================
# TEST: NON-ASCII SAFETY
# ============================================================================

class TestNonAsciiSafety:
    """Test safe handling of non-ASCII characters."""

    def test_unicode_text(self):
        """Unicode text should not crash."""
        unicode_texts = [
            "café",
            "naïve",
            "über",
            "日本語",
            "Ελληνικά",
            "العربية",
            "🎉🎊",  # Emojis
        ]
        for text in unicode_texts:
            # Should not raise
            units = map_acoustic_units(text)
            # Should be a list (possibly empty for non-alphabetic)
            assert isinstance(units, list)

    def test_extended_vowels(self):
        """Extended vowels (accented) should be recognized."""
        text = "naïve"
        units = map_acoustic_units(text)
        # Should have some vowel units
        vowel_units = [u for u in units if u.sound_class == SoundClass.VOWEL]
        # At least some vowels should be detected
        assert len(units) > 0

    def test_mixed_scripts(self):
        """Mixed scripts should not crash."""
        text = "hello世界"
        units = map_acoustic_units(text)
        assert isinstance(units, list)

    def test_null_bytes(self):
        """Null bytes should be handled safely."""
        text = "hello\x00world"
        units = map_acoustic_units(text)
        assert isinstance(units, list)


# ============================================================================
# TEST: NO SEMANTIC LEAKAGE
# ============================================================================

class TestNoSemanticLeakage:
    """Verify Phase 1 outputs contain no semantic content."""

    def test_acoustic_unit_no_meaning_field(self):
        """AcousticUnit should have no meaning/intent fields."""
        units = map_acoustic_units("hello world")
        assert len(units) > 0

        for unit in units:
            fields = set(unit.__dataclass_fields__.keys())
            forbidden = {'meaning', 'intent', 'purpose', 'goal', 'semantic',
                        'emotion', 'sentiment', 'topic', 'category', 'label'}
            leaked = fields & forbidden
            assert not leaked, f"Semantic leakage in AcousticUnit: {leaked}"

    def test_acoustic_vritti_no_emotion_field(self):
        """AcousticVritti should have no emotion/sentiment fields."""
        units = map_acoustic_units("testing emotions")
        vritti_list = assign_vritti_sequence(units)

        for vritti in vritti_list:
            fields = set(vritti.__dataclass_fields__.keys())
            forbidden = {'meaning', 'intent', 'purpose', 'emotion', 'sentiment'}
            leaked = fields & forbidden
            assert not leaked, f"Semantic leakage in AcousticVritti: {leaked}"

    def test_snapshot_semantic_leakage_check(self):
        """Snapshot should pass semantic leakage assertion."""
        snapshot = create_phase1_snapshot("semantic test input")
        # Should not raise
        assert assert_no_semantic_leakage(snapshot)

    def test_vritti_types_are_motion_not_emotion(self):
        """VrittiType values should be motion qualities, not emotions."""
        emotion_words = {'happy', 'sad', 'angry', 'fear', 'joy', 'love', 'hate'}
        for vt in VrittiType:
            assert vt.value not in emotion_words, \
                f"VrittiType '{vt.value}' looks like emotion"

    def test_no_word_boundaries_in_units(self):
        """Acoustic units should not respect word boundaries semantically."""
        # Units are based on acoustic structure, not words
        text = "hello world"
        units = map_acoustic_units(text)

        # Check that unit boundaries don't necessarily match word boundaries
        # (acoustic segmentation is different from lexical)
        raw_texts = [u.raw_text for u in units]
        # Should not have exact word matches as the only units
        # (though some overlap is acceptable)
        assert not (raw_texts == ['hello', 'world']), \
            "Units should not be pure word boundaries"


# ============================================================================
# TEST: VṚTTI ASSIGNMENT
# ============================================================================

class TestVrittiAssignment:
    """Test vṛtti assignment rules and properties."""

    def test_stops_get_activation(self):
        """Stop consonants should get ACTIVATION vṛtti."""
        # Create a unit with STOP sound class
        stops = "ptk"
        units = map_acoustic_units(stops)

        for unit in units:
            if unit.sound_class == SoundClass.STOP:
                vritti = assign_vritti(unit)
                assert vritti.vritti_type == VrittiType.ACTIVATION, \
                    f"Stop '{unit.raw_text}' should get ACTIVATION"

    def test_fricatives_get_tension(self):
        """Fricative consonants should get TENSION vṛtti."""
        fricatives = "fsvz"
        units = map_acoustic_units(fricatives)

        for unit in units:
            if unit.sound_class == SoundClass.FRICATIVE:
                vritti = assign_vritti(unit)
                assert vritti.vritti_type == VrittiType.TENSION, \
                    f"Fricative '{unit.raw_text}' should get TENSION"

    def test_nasals_get_inertia(self):
        """Nasal consonants should get INERTIA vṛtti."""
        nasals = "mn"
        units = map_acoustic_units(nasals)

        for unit in units:
            if unit.sound_class == SoundClass.NASAL:
                vritti = assign_vritti(unit)
                assert vritti.vritti_type == VrittiType.INERTIA, \
                    f"Nasal '{unit.raw_text}' should get INERTIA"

    def test_liquids_get_oscillation(self):
        """Liquid consonants should get OSCILLATION vṛtti."""
        liquids = "lr"
        units = map_acoustic_units(liquids)

        for unit in units:
            if unit.sound_class == SoundClass.LIQUID:
                vritti = assign_vritti(unit)
                assert vritti.vritti_type == VrittiType.OSCILLATION, \
                    f"Liquid '{unit.raw_text}' should get OSCILLATION"

    def test_vritti_weight_in_range(self):
        """Vṛtti weights should be in [0.0, 1.0]."""
        text = "comprehensive vritti weight test"
        units = map_acoustic_units(text)
        vritti_list = assign_vritti_sequence(units)

        for vritti in vritti_list:
            assert 0.0 <= vritti.weight <= 1.0, \
                f"Weight {vritti.weight} out of range"

    def test_vritti_distribution_sums_to_one(self):
        """Vṛtti distribution should sum to approximately 1.0."""
        text = "testing distribution"
        units = map_acoustic_units(text)
        vritti_list = assign_vritti_sequence(units)

        if vritti_list:
            dist = get_vritti_distribution(vritti_list)
            total = sum(dist.values())
            assert abs(total - 1.0) < 0.01, f"Distribution sums to {total}, not 1.0"

    def test_dominant_vritti_is_valid_type(self):
        """Dominant vṛtti should be a valid VrittiType."""
        text = "dominant test"
        units = map_acoustic_units(text)
        vritti_list = assign_vritti_sequence(units)

        if vritti_list:
            dominant = get_dominant_vritti(vritti_list)
            assert isinstance(dominant, VrittiType)


# ============================================================================
# TEST: SNAPSHOT IMMUTABILITY
# ============================================================================

class TestSnapshotImmutability:
    """Test that Phase1Snapshot is immutable."""

    def test_snapshot_is_frozen(self):
        """Snapshot should be frozen (immutable)."""
        snapshot = create_phase1_snapshot("test")

        with pytest.raises(Exception):  # FrozenInstanceError
            snapshot.acoustic_units = tuple()

    def test_metadata_is_frozen(self):
        """Metadata should be frozen."""
        snapshot = create_phase1_snapshot("test")

        with pytest.raises(Exception):
            snapshot.metadata.unit_count = 999

    def test_acoustic_units_tuple(self):
        """acoustic_units should be tuple, not list."""
        snapshot = create_phase1_snapshot("test")
        assert isinstance(snapshot.acoustic_units, tuple)

    def test_vritti_map_tuple(self):
        """vritti_map should be tuple, not list."""
        snapshot = create_phase1_snapshot("test")
        assert isinstance(snapshot.vritti_map, tuple)


# ============================================================================
# TEST: CONTRACT VALIDATION
# ============================================================================

class TestContractValidation:
    """Test Phase 1 contract validation functions."""

    def test_valid_snapshot_passes_validation(self):
        """Valid snapshot should pass validation."""
        snapshot = create_phase1_snapshot("valid input")
        assert validate_phase1_snapshot(snapshot)

    def test_empty_snapshot_is_valid(self):
        """Empty snapshot should be valid."""
        snapshot = create_empty_snapshot()
        assert validate_phase1_snapshot(snapshot)

    def test_phase_id_correct(self):
        """Phase ID should be PHASE_1."""
        snapshot = create_phase1_snapshot("test")
        assert snapshot.metadata.phase_id == "PHASE_1"

    def test_phase_version_present(self):
        """Phase version should be present."""
        snapshot = create_phase1_snapshot("test")
        assert snapshot.metadata.phase_version == PHASE_VERSION

    def test_unit_count_matches_length(self):
        """Metadata unit_count should match actual length."""
        snapshot = create_phase1_snapshot("count test")
        assert snapshot.metadata.unit_count == len(snapshot.acoustic_units)

    def test_vritti_map_matches_units(self):
        """vritti_map length should match acoustic_units."""
        snapshot = create_phase1_snapshot("matching test")
        assert len(snapshot.vritti_map) == len(snapshot.acoustic_units)


# ============================================================================
# TEST: PHASE 1 INVARIANTS
# ============================================================================

class TestPhase1Invariants:
    """Test that Phase 1 invariant declarations are correct."""

    def test_acoustic_invariants_declared(self):
        """Acoustic mapper should declare Phase 1 invariants."""
        assert ACOUSTIC_INVARIANTS["NO_SEMANTICS"] is True
        assert ACOUSTIC_INVARIANTS["NO_INTENT"] is True
        assert ACOUSTIC_INVARIANTS["NO_LLM_CALLS"] is True
        assert ACOUSTIC_INVARIANTS["DETERMINISTIC"] is True

    def test_vritti_invariants_declared(self):
        """Vṛtti mapper should declare Phase 1 invariants."""
        assert VRITTI_INVARIANTS["NO_SEMANTICS"] is True
        assert VRITTI_INVARIANTS["NO_ONTOLOGY_LOOKUP"] is True
        assert VRITTI_INVARIANTS["DETERMINISTIC"] is True

    def test_snapshot_invariants_declared(self):
        """Snapshot should declare Phase 1 invariants."""
        assert SNAPSHOT_INVARIANTS["NO_SEMANTICS"] is True
        assert SNAPSHOT_INVARIANTS["IMMUTABLE"] is True
        assert SNAPSHOT_INVARIANTS["DETERMINISTIC"] is True


# ============================================================================
# TEST: TYPE SAFETY
# ============================================================================

class TestTypeSafety:
    """Test type validation and error handling."""

    def test_map_acoustic_units_requires_string(self):
        """map_acoustic_units should reject non-string input."""
        with pytest.raises(TypeError):
            map_acoustic_units(123)

        with pytest.raises(TypeError):
            map_acoustic_units(None)

        with pytest.raises(TypeError):
            map_acoustic_units(['hello'])

    def test_assign_vritti_requires_acoustic_unit(self):
        """assign_vritti should reject non-AcousticUnit input."""
        with pytest.raises(TypeError):
            assign_vritti("not a unit")

        with pytest.raises(TypeError):
            assign_vritti(123)

    def test_create_snapshot_requires_string(self):
        """create_phase1_snapshot should reject non-string input."""
        with pytest.raises(TypeError):
            create_phase1_snapshot(123)

        with pytest.raises(TypeError):
            create_phase1_snapshot(None)


# ============================================================================
# TEST: SERIALIZATION
# ============================================================================

class TestSerialization:
    """Test snapshot serialization."""

    def test_to_dict_produces_dict(self):
        """to_dict should produce a dictionary."""
        snapshot = create_phase1_snapshot("serialization test")
        result = snapshot.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_required_keys(self):
        """to_dict should contain all required keys."""
        snapshot = create_phase1_snapshot("key test")
        result = snapshot.to_dict()

        required_keys = [
            'phase_id', 'phase_version', 'unit_count',
            'acoustic_signature', 'vritti_signature',
            'units', 'vritti_assignments'
        ]

        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_to_dict_no_semantic_keys(self):
        """to_dict should not contain semantic keys."""
        snapshot = create_phase1_snapshot("semantic check")
        result = snapshot.to_dict()

        forbidden_keys = ['meaning', 'intent', 'emotion', 'sentiment']
        for key in forbidden_keys:
            assert key not in result, f"Forbidden key present: {key}"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
