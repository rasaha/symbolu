"""
Patent Formula Alignment Tags - Drift Test Suite
=================================================

Comprehensive tests for Phase 6 patent formula tagging system.

These tests verify that:
- All implemented formulas have correct tags
- Patent-only formulas have correct tags
- No new formulas appear without tags
- Tags never drift (canonical snapshot protection)

Test Categories:
1. Tag presence tests: Verify all formulas are tagged
2. Tag correctness tests: Verify tags match expected values
3. Snapshot tests: Verify tags never drift from canonical snapshot

Version: 1.0 (Phase 6)
Date: 2025-12-10
"""

import pytest
from symbolu_core.formulas.patent_tags import PATENT_FORMULA_TAGS, get_formula_tag


# =============================================================================
# CANONICAL SNAPSHOT
# =============================================================================

# This is the canonical snapshot of expected patent formula tags.
# NEVER modify this without explicit approval and understanding of impact.
# Any drift from this snapshot indicates either:
# - A new formula was added (requires tag assignment)
# - A tag was accidentally modified (requires investigation)
# - A formula was removed (requires documentation update)

EXPECTED_TAGS = {
    # Phase 1: Temporal Resonance Formulas
    "smi": "phase1_temporal",
    "delta_smi": "phase1_temporal",

    # Phase 1: Temporal Geometry Formulas
    "bhava_gap": "phase1_temporal",
    "tension_corridor": "phase1_temporal",

    # Phase 3: Derived Metrics
    "resonance_index": "phase3_derived",
    "tension_index": "phase3_derived",
    "arc_alignment_index": "phase3_derived",

    # Patent-only formulas (not yet implemented)
    "guna_kosha_vrtti": "patent_only",
    "hope_greed_harmonic": "patent_only",
    "cognitive_arc_equation": "patent_only",
}


# =============================================================================
# 1. TAG PRESENCE TESTS
# =============================================================================


class TestTagPresence:
    """Test that all expected formulas have tags."""

    def test_all_phase1_formulas_have_tags(self):
        """Test that all Phase 1 formulas have tags."""
        phase1_formulas = ["smi", "delta_smi", "bhava_gap", "tension_corridor"]

        for formula in phase1_formulas:
            assert formula in PATENT_FORMULA_TAGS, (
                f"Phase 1 formula '{formula}' missing from PATENT_FORMULA_TAGS"
            )

    def test_all_phase3_formulas_have_tags(self):
        """Test that all Phase 3 derived metrics have tags."""
        phase3_formulas = ["resonance_index", "tension_index", "arc_alignment_index"]

        for formula in phase3_formulas:
            assert formula in PATENT_FORMULA_TAGS, (
                f"Phase 3 formula '{formula}' missing from PATENT_FORMULA_TAGS"
            )

    def test_all_patent_only_formulas_have_tags(self):
        """Test that all patent-only formulas have tags."""
        patent_only_formulas = [
            "guna_kosha_vrtti",
            "hope_greed_harmonic",
            "cognitive_arc_equation",
        ]

        for formula in patent_only_formulas:
            assert formula in PATENT_FORMULA_TAGS, (
                f"Patent-only formula '{formula}' missing from PATENT_FORMULA_TAGS"
            )

    def test_no_missing_tags(self):
        """Test that PATENT_FORMULA_TAGS has no None or empty tags."""
        for formula_name, tag in PATENT_FORMULA_TAGS.items():
            assert tag is not None, f"Formula '{formula_name}' has None tag"
            assert tag != "", f"Formula '{formula_name}' has empty tag"
            assert isinstance(tag, str), f"Formula '{formula_name}' tag is not a string: {type(tag)}"


# =============================================================================
# 2. TAG CORRECTNESS TESTS
# =============================================================================


class TestTagCorrectness:
    """Test that formula tags have correct values."""

    def test_phase1_temporal_formulas_have_correct_tags(self):
        """Test that Phase 1 temporal formulas are tagged as 'phase1_temporal'."""
        phase1_temporal = ["smi", "delta_smi", "bhava_gap", "tension_corridor"]

        for formula in phase1_temporal:
            tag = PATENT_FORMULA_TAGS[formula]
            assert tag == "phase1_temporal", (
                f"Phase 1 formula '{formula}' has incorrect tag: {tag}"
            )

    def test_phase3_derived_formulas_have_correct_tags(self):
        """Test that Phase 3 derived metrics are tagged as 'phase3_derived'."""
        phase3_derived = ["resonance_index", "tension_index", "arc_alignment_index"]

        for formula in phase3_derived:
            tag = PATENT_FORMULA_TAGS[formula]
            assert tag == "phase3_derived", (
                f"Phase 3 formula '{formula}' has incorrect tag: {tag}"
            )

    def test_patent_only_formulas_have_correct_tags(self):
        """Test that patent-only formulas are tagged as 'patent_only'."""
        patent_only = [
            "guna_kosha_vrtti",
            "hope_greed_harmonic",
            "cognitive_arc_equation",
        ]

        for formula in patent_only:
            tag = PATENT_FORMULA_TAGS[formula]
            assert tag == "patent_only", (
                f"Patent-only formula '{formula}' has incorrect tag: {tag}"
            )

    def test_tag_format_validity(self):
        """Test that all tags follow the correct format."""
        valid_tag_patterns = {
            "phase1_temporal",
            "phase3_derived",
            "phase7_behavioral",  # Future
            "phase8_kosha_guna",  # Future
            "patent_only",
        }

        for formula_name, tag in PATENT_FORMULA_TAGS.items():
            # Check if tag matches any valid pattern or is a phase{N}_{category} format
            is_valid = (
                tag in valid_tag_patterns or
                (tag.startswith("phase") and "_" in tag)
            )

            assert is_valid, (
                f"Formula '{formula_name}' has invalid tag format: {tag}\n"
                f"Expected format: 'phase{{N}}_{{category}}' or 'patent_only'"
            )


# =============================================================================
# 3. SNAPSHOT DRIFT TESTS
# =============================================================================


class TestSnapshotDrift:
    """Test that PATENT_FORMULA_TAGS never drifts from canonical snapshot."""

    def test_tags_match_canonical_snapshot(self):
        """
        Test that PATENT_FORMULA_TAGS exactly matches EXPECTED_TAGS snapshot.

        This is the primary drift guard for Phase 6. Any change to formula tags
        will cause this test to fail, requiring explicit acknowledgment.
        """
        assert PATENT_FORMULA_TAGS == EXPECTED_TAGS, (
            "PATENT_FORMULA_TAGS has drifted from canonical snapshot!\n\n"
            f"Expected tags:\n{EXPECTED_TAGS}\n\n"
            f"Actual tags:\n{PATENT_FORMULA_TAGS}\n\n"
            "If this is intentional:\n"
            "1. Update EXPECTED_TAGS in test_patent_alignment_tags.py\n"
            "2. Update docs/patent_formula_coverage_matrix.md\n"
            "3. Document the change in commit message"
        )

    def test_no_new_formulas_without_tags(self):
        """Test that no formulas appear in code without corresponding tags."""
        # This test ensures that any new formula implementation gets tagged
        # For now, we verify that all expected formulas are present

        expected_count = len(EXPECTED_TAGS)
        actual_count = len(PATENT_FORMULA_TAGS)

        assert actual_count == expected_count, (
            f"Formula count mismatch! Expected {expected_count}, got {actual_count}\n"
            "If you added a new formula:\n"
            "1. Add it to PATENT_FORMULA_TAGS in symbolu/formulas/patent_tags.py\n"
            "2. Add it to EXPECTED_TAGS in this test file\n"
            "3. Update docs/patent_formula_coverage_matrix.md"
        )

    def test_no_tag_removals(self):
        """Test that no tags were removed from the canonical snapshot."""
        missing_formulas = set(EXPECTED_TAGS.keys()) - set(PATENT_FORMULA_TAGS.keys())

        assert len(missing_formulas) == 0, (
            f"Formulas removed from PATENT_FORMULA_TAGS: {missing_formulas}\n"
            "If this is intentional (formula deprecated):\n"
            "1. Remove from EXPECTED_TAGS in this test file\n"
            "2. Update docs/patent_formula_coverage_matrix.md\n"
            "3. Document the removal in commit message"
        )

    def test_no_unexpected_tag_additions(self):
        """Test that no new tags were added without updating the snapshot."""
        extra_formulas = set(PATENT_FORMULA_TAGS.keys()) - set(EXPECTED_TAGS.keys())

        assert len(extra_formulas) == 0, (
            f"New formulas added to PATENT_FORMULA_TAGS without snapshot update: {extra_formulas}\n"
            "To add a new formula:\n"
            "1. Add to EXPECTED_TAGS in this test file\n"
            "2. Update docs/patent_formula_coverage_matrix.md\n"
            "3. Document the addition in commit message"
        )


# =============================================================================
# 4. HELPER FUNCTION TESTS
# =============================================================================


class TestGetFormulaTag:
    """Test the get_formula_tag() helper function."""

    def test_get_formula_tag_for_implemented_formulas(self):
        """Test that get_formula_tag returns correct tags for implemented formulas."""
        assert get_formula_tag("smi") == "phase1_temporal"
        assert get_formula_tag("delta_smi") == "phase1_temporal"
        assert get_formula_tag("resonance_index") == "phase3_derived"

    def test_get_formula_tag_for_patent_only_formulas(self):
        """Test that get_formula_tag returns 'patent_only' for unimplemented formulas."""
        assert get_formula_tag("guna_kosha_vrtti") == "patent_only"
        assert get_formula_tag("hope_greed_harmonic") == "patent_only"
        assert get_formula_tag("cognitive_arc_equation") == "patent_only"

    def test_get_formula_tag_for_unknown_formulas(self):
        """Test that get_formula_tag returns 'unknown' for non-existent formulas."""
        assert get_formula_tag("nonexistent_formula") == "unknown"
        assert get_formula_tag("fake_metric") == "unknown"
        assert get_formula_tag("") == "unknown"

    def test_get_formula_tag_case_sensitivity(self):
        """Test that get_formula_tag is case-sensitive."""
        # Correct case
        assert get_formula_tag("smi") == "phase1_temporal"

        # Wrong case (should return 'unknown')
        assert get_formula_tag("SMI") == "unknown"
        assert get_formula_tag("Smi") == "unknown"


# =============================================================================
# 5. INTEGRATION TESTS
# =============================================================================


class TestPatentTagsIntegration:
    """Test integration of patent tags with formula modules."""

    def test_all_implemented_formulas_are_phase_tagged(self):
        """Test that all implemented formulas have phase{N}_{category} tags, not 'patent_only'."""
        implemented_formulas = [
            "smi",
            "delta_smi",
            "bhava_gap",
            "tension_corridor",
            "resonance_index",
            "tension_index",
            "arc_alignment_index",
        ]

        for formula in implemented_formulas:
            tag = PATENT_FORMULA_TAGS[formula]
            assert tag != "patent_only", (
                f"Implemented formula '{formula}' incorrectly tagged as 'patent_only'"
            )
            assert tag.startswith("phase"), (
                f"Implemented formula '{formula}' should have phase tag, got: {tag}"
            )

    def test_all_patent_only_formulas_are_not_phase_tagged(self):
        """Test that patent-only formulas do NOT have phase{N}_{category} tags."""
        patent_only_formulas = [
            "guna_kosha_vrtti",
            "hope_greed_harmonic",
            "cognitive_arc_equation",
        ]

        for formula in patent_only_formulas:
            tag = PATENT_FORMULA_TAGS[formula]
            assert tag == "patent_only", (
                f"Patent-only formula '{formula}' should be tagged 'patent_only', got: {tag}"
            )
            assert not tag.startswith("phase"), (
                f"Patent-only formula '{formula}' should NOT have phase tag, got: {tag}"
            )

    def test_tag_count_matches_expected(self):
        """Test that the total number of tags matches expected count."""
        # Phase 1: 4 formulas (smi, delta_smi, bhava_gap, tension_corridor)
        # Phase 3: 3 formulas (resonance_index, tension_index, arc_alignment_index)
        # Patent-only: 3 formulas (guna_kosha_vrtti, hope_greed_harmonic, cognitive_arc_equation)
        # Total: 10 formulas
        expected_total = 10

        assert len(PATENT_FORMULA_TAGS) == expected_total, (
            f"Expected {expected_total} total formula tags, got {len(PATENT_FORMULA_TAGS)}"
        )


# =============================================================================
# Summary
# =============================================================================

"""
Patent Formula Alignment Tags Test Suite Summary
==================================================

Test Coverage:
- Tag presence tests (4 tests): Verify all formulas have tags
- Tag correctness tests (4 tests): Verify tags match expected values
- Snapshot drift tests (4 tests): Verify tags never drift
- Helper function tests (4 tests): Verify get_formula_tag() works correctly
- Integration tests (3 tests): Verify tag consistency and count

Total: 19 tests ensuring Phase 6 patent formula tags remain stable and correct.

These tests act as a drift guard for the patent formula alignment layer,
ensuring that any changes to formula tags are intentional and documented.
"""
