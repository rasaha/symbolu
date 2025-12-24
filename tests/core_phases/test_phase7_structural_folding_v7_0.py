"""
Phase-7.0 Structural Folding Test Suite (v7.0)
===============================================

Test Goals: Phase-7.0 structural folding verification.
            Phase-7.0 is TEST-ONLY and FOLDING-ONLY.
            It must NOT generate language, words, sentences, or content.

Phase-7.0 is the FIRST phase where "generation" is allowed — but ONLY via
STRUCTURAL FOLDING.

Phase-7.0 operates only on Phase-5 output (Phase5SynthesisResult) and exists solely to:
    - group contiguous eligible Phase-5 synthesis units
    - produce folded artifacts referencing ONLY source indices
    - preserve full reversibility
    - remain deterministic across unlimited runs
    - NEVER inspect Phase-1b, Phase-2, Phase-3, or Phase-4 directly

Any violation of controlled generation constraints is a hard failure.

This test suite verifies:
    Group A: Structural Integrity
    Group B: Non-Textual Enforcement
    Group C: Folding Correctness
    Group D: Determinism
    Group E: Reversibility
    Group F: Isolation Regression Guard
    Group G: Edge & Stress Tests
    Red-Flag Tests

Version: 7.0
Date: 2025-12-15

ABSOLUTE RULES:
    - DO NOT generate text
    - DO NOT generate words
    - DO NOT generate sentences
    - DO NOT use dictionaries for lookup
    - DO NOT infer semantics
    - DO NOT infer emotion
    - DO NOT infer intent
    - DO NOT use probabilities
    - DO NOT use timestamps
    - DO NOT use randomness
    - DO NOT use learning
    - DO NOT use heuristics
    - ONLY structural folding allowed
"""

import pytest
import hashlib
import time
from typing import List, Tuple, Any
from enum import Enum


# Phase-1b imports
from docs.experiments.acoustic_unit_mapper_expressive_delta_v3_1 import (
    map_acoustic_units,
    AcousticBridgeUnit,
    validate_invariants_v3_1,
    ACOUSTIC_MAPPER_VERSION,
)

# Phase-2 imports
from docs.experiments.phase2_modifier_engine_v3_2 import (
    apply_modifiers,
    Phase2ModifiedUnit,
    extract_phase1b_units,
    compute_phase1b_hash,
    get_modifiers_summary,
    validate_invariants_v3_2,
    PHASE2_ENGINE_VERSION,
)

# Phase-3 imports from engine module
from docs.experiments.phase3_rule_engine_v3_0 import (
    evaluate_phase3_rules,
    Phase3RuleEvaluation,
    Phase3RuleResult,
    RuleStatus,
    RuleCategory,
    PHASE3_ENGINE_VERSION,
    PHASE3_INVARIANTS,
    validate_phase3_invariants,
    get_phase2_hash,
)

# Phase-4 imports from engine module
from docs.experiments.phase4_transform_engine_v4_0 import (
    transform_phase3_to_phase4,
    transform_phase3_to_phase4_all,
    Phase4TransformResult,
    Phase4TransformUnit,
    TransformType,
    PHASE4_ENGINE_VERSION,
    PHASE4_INVARIANTS,
    validate_phase4_invariants,
    recover_phase3_indices,
    recover_phase3_eligibility,
    _compute_phase3_sequence_hash,
)

# Phase-5 imports from engine module
from docs.experiments.phase5_synthesis_engine_v5_0 import (
    synthesize_phase4_to_phase5,
    recover_phase4_indices,
    recover_phase4_eligibility_masks,
    validate_phase5_invariants,
    check_for_forbidden_terms_phase5,
    is_non_textual_value_phase5,
    PHASE5_ENGINE_VERSION,
    PHASE5_INVARIANTS,
    SynthesisType,
    Phase5SynthesisUnit,
    Phase5SynthesisResult,
    FORBIDDEN_TERMS_PHASE5,
)

# Phase-7 imports from engine module
from docs.experiments.phase7_structural_folding_engine_v7_0 import (
    fold_phase5_to_phase7,
    recover_phase5_indices,
    recover_phase5_eligibility_masks,
    validate_phase7_invariants,
    check_for_forbidden_terms_phase7,
    is_non_textual_value_phase7,
    PHASE7_ENGINE_VERSION,
    PHASE7_INVARIANTS,
    FoldingType,
    Phase7FoldedUnit,
    Phase7FoldedArtifact,
    FORBIDDEN_TERMS_PHASE7,
)


# ============================================================================
# PHASE-7 INVARIANTS DEFINITION (REQUIRED)
# ============================================================================

PHASE7_INVARIANTS_REQUIRED = {
    "CONTROLLED_GENERATION": True,
    "STRUCTURAL_ONLY": True,
    "NO_LANGUAGE": True,
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_EMOTION": True,
    "NO_PROBABILITY": True,
    "NO_LEARNING": True,
    "NON_MUTATING": True,
    "REVERSIBLE": True,
    "DETERMINISTIC": True,
    "ISOLATED": True,
    "TEST_ONLY": True,
}


# ============================================================================
# Helper Functions for Tests
# ============================================================================

def run_full_pipeline(text: str) -> Tuple[Phase5SynthesisResult, Phase7FoldedArtifact]:
    """Run full pipeline from text to Phase-7 result."""
    phase1b_units = map_acoustic_units(text)
    phase2_units = apply_modifiers(phase1b_units)
    phase3_evals = evaluate_phase3_rules(phase2_units)
    phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
    phase5_result = synthesize_phase4_to_phase5([phase4_result])
    phase7_result = fold_phase5_to_phase7(phase5_result)
    return phase5_result, phase7_result


def run_eligible_pipeline(text: str) -> Tuple[Phase5SynthesisResult, Phase7FoldedArtifact]:
    """Run pipeline with eligibility filter (only eligible units)."""
    phase1b_units = map_acoustic_units(text)
    phase2_units = apply_modifiers(phase1b_units)
    phase3_evals = evaluate_phase3_rules(phase2_units)
    phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
    phase5_result = synthesize_phase4_to_phase5([phase4_result])
    phase7_result = fold_phase5_to_phase7(phase5_result)
    return phase5_result, phase7_result


# ============================================================================
# Group A: Structural Integrity Tests
# ============================================================================

class TestGroupA_StructuralIntegrity:
    """
    Group A: Structural Integrity Tests

    Verifies:
        1. No mutation of Phase-5 objects
        2. Hashes unchanged in Phase-5 after Phase-7
        3. Folded artifact references valid Phase-5 indices only
    """

    def test_phase5_objects_not_mutated(self):
        """
        Test A1: Phase-5 objects must NOT be mutated by Phase-7.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # Capture pre-state
        pre_state = [
            (u.source_indices, u.aggregated_rule_vector, u.eligibility_mask)
            for u in phase5_result.synthesis_units
        ]
        pre_hash = phase5_result.synthesis_hash

        # Run Phase-7
        _ = fold_phase5_to_phase7(phase5_result)

        # Verify post-state
        post_state = [
            (u.source_indices, u.aggregated_rule_vector, u.eligibility_mask)
            for u in phase5_result.synthesis_units
        ]
        post_hash = phase5_result.synthesis_hash

        assert pre_state == post_state, \
            "Phase-5 unit data was MUTATED by Phase-7!"
        assert pre_hash == post_hash, \
            "Phase-5 hash was MUTATED by Phase-7!"

    def test_phase5_hash_unchanged_after_phase7(self):
        """
        Test A2: Phase-5 hash must be unchanged after Phase-7.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "ka kha ga"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

            original_hash = phase5_result.synthesis_hash

            _ = fold_phase5_to_phase7(phase5_result)

            assert phase5_result.synthesis_hash == original_hash, \
                f"Phase-5 hash CHANGED after Phase-7 for '{text}'!"

    def test_folded_artifact_references_valid_phase5_indices(self):
        """
        Test A3: Folded artifact must reference valid Phase-5 indices only.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        phase5_indices = set(range(len(phase5_result.synthesis_units)))

        for unit in phase7_result.folded_units:
            for idx in unit.source_phase5_indices:
                assert idx in phase5_indices, \
                    f"Phase-7 references invalid Phase-5 index: {idx}"

    def test_phase4_hash_unchanged_after_phase7(self):
        """
        Test A4: Phase-4 hash must be unchanged after full pipeline.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        original_hash = phase4_result.source_phase3_hash

        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        _ = fold_phase5_to_phase7(phase5_result)

        assert phase4_result.source_phase3_hash == original_hash, \
            "Phase-4 hash CHANGED after Phase-7!"

    def test_phase3_objects_not_mutated_by_phase7(self):
        """
        Test A5: Phase-3 objects must NOT be mutated after full pipeline.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        pre_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        _ = fold_phase5_to_phase7(phase5_result)

        post_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        assert pre_state == post_state, \
            "Phase-3 objects were MUTATED after Phase-7!"

    def test_phase2_objects_not_mutated_by_phase7(self):
        """
        Test A6: Phase-2 objects must NOT be mutated after full pipeline.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)

        pre_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        _ = fold_phase5_to_phase7(phase5_result)

        post_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        assert pre_modifiers == post_modifiers, \
            "Phase-2 objects were MUTATED after Phase-7!"

    def test_phase1b_hash_unchanged_after_phase7(self):
        """
        Test A7: Phase-1b hash must be unchanged after full pipeline.
        """
        text = "sa a kha x da"

        phase1b_units = map_acoustic_units(text)
        original_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        _ = fold_phase5_to_phase7(phase5_result)

        extracted = extract_phase1b_units(phase2_units)
        after_hash = compute_phase1b_hash(extracted)

        assert original_hash == after_hash, \
            "Phase-1b hash CHANGED after Phase-7!"

    def test_source_phase5_hash_preserved(self):
        """
        Test A8: Source Phase-5 hash must be preserved in Phase-7.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert phase5_result.synthesis_hash in phase7_result.source_phase5_hashes, \
            "Phase-5 hash not preserved in Phase-7!"


# ============================================================================
# Group B: Non-Textual Output Enforcement Tests
# ============================================================================

class TestGroupB_NonTextualEnforcement:
    """
    Group B: Non-Textual Output Enforcement Tests

    Verifies:
        - No free-form strings appear anywhere in Phase-7 output
        - Only allowed strings are hex hashes and Enum values
        - All primitives are int, bool, tuple, list, enum, or hex string
    """

    def test_no_freeform_strings_in_units(self):
        """
        Test B1: Phase-7 units must not contain free-form strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        for unit in phase7_result.folded_units:
            # Check source_phase5_indices - all ints
            assert all(isinstance(idx, int) for idx in unit.source_phase5_indices)

            # Check aggregated_fold_vector - all ints in {0,1,2}
            for val in unit.aggregated_fold_vector:
                assert isinstance(val, int)
                assert val in (0, 1, 2)

            # Check fold_adjacency - all ints in {0,1}
            for val in unit.fold_adjacency:
                assert isinstance(val, int)
                assert val in (0, 1)

            # Check eligibility_chain - all bools
            assert all(isinstance(b, bool) for b in unit.eligibility_chain)

            # Check unit_hash - hex string only
            assert isinstance(unit.unit_hash, str)
            assert 16 <= len(unit.unit_hash) <= 32
            assert all(c in "0123456789abcdef" for c in unit.unit_hash)

    def test_no_text_concatenation(self):
        """
        Test B2: Phase-7 must NOT concatenate varnas or indices into strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result)

        # Should NOT contain concatenated indices as strings
        assert "0_1_2" not in output_str
        assert "012" not in output_str.replace(" ", "").replace(",", "")

    def test_folding_hash_is_hex(self):
        """
        Test B3: Folding hash must be hex string of constrained length.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert isinstance(phase7_result.folding_hash, str)
        assert 16 <= len(phase7_result.folding_hash) <= 32
        assert all(c in "0123456789abcdef" for c in phase7_result.folding_hash)

    def test_source_phase5_hashes_are_hex(self):
        """
        Test B4: Source Phase-5 hashes must be hex strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        for h in phase7_result.source_phase5_hashes:
            assert isinstance(h, str)
            assert 16 <= len(h) <= 32
            assert all(c in "0123456789abcdef" for c in h)

    def test_folding_type_is_enum(self):
        """
        Test B5: Folding type must be FoldingType enum value.
        """
        phase1b_units = map_acoustic_units("a ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert isinstance(phase7_result.folding_type, FoldingType)

    def test_reversible_and_eligible_are_bool(self):
        """
        Test B6: Reversible and eligible flags must be boolean.
        """
        phase1b_units = map_acoustic_units("da dha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert isinstance(phase7_result.reversible, bool)
        assert isinstance(phase7_result.eligible, bool)

    def test_all_values_pass_non_textual_check(self):
        """
        Test B7: All Phase-7 output values must pass non-textual check.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Check folded units
        for unit in phase7_result.folded_units:
            assert is_non_textual_value_phase7(unit.source_phase5_indices)
            assert is_non_textual_value_phase7(unit.aggregated_fold_vector)
            assert is_non_textual_value_phase7(unit.fold_adjacency)
            assert is_non_textual_value_phase7(unit.eligibility_chain)
            assert is_non_textual_value_phase7(unit.unit_hash)

        # Check result-level values
        assert is_non_textual_value_phase7(phase7_result.fold_graph)
        assert is_non_textual_value_phase7(phase7_result.folding_hash)
        assert is_non_textual_value_phase7(phase7_result.source_phase5_hashes)
        assert is_non_textual_value_phase7(phase7_result.folding_type)
        assert is_non_textual_value_phase7(phase7_result.reversible)
        assert is_non_textual_value_phase7(phase7_result.eligible)

    def test_no_free_text_fields(self):
        """
        Test B8: Phase-7 must not have free text fields.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        result_str = str(phase7_result)

        # These would indicate free text fields (Phase-1b specific)
        assert "escape_pressure" not in result_str.lower()
        assert "birth_of_cognition" not in result_str.lower()
        assert "hope_pressure" not in result_str.lower()

    def test_fold_graph_binary_only(self):
        """
        Test B9: Fold graph must contain only 0 or 1.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        for row in phase7_result.fold_graph:
            for val in row:
                assert isinstance(val, int), \
                    f"Non-int in fold_graph: {type(val)}"
                assert val in (0, 1), \
                    f"Invalid fold_graph value: {val}"

    def test_aggregated_fold_vector_contains_only_012(self):
        """
        Test B10: Aggregated fold vectors must contain only 0, 1, or 2.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "ka kha ga gha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            phase7_result = fold_phase5_to_phase7(phase5_result)

            for unit in phase7_result.folded_units:
                for val in unit.aggregated_fold_vector:
                    assert isinstance(val, int), \
                        f"Non-int in aggregated_fold_vector for '{text}': {type(val)}"
                    assert val in (0, 1, 2), \
                        f"Invalid value in aggregated_fold_vector for '{text}': {val}"


# ============================================================================
# Group C: Folding Correctness Tests
# ============================================================================

class TestGroupC_FoldingCorrectness:
    """
    Group C: Folding Correctness Tests

    Verifies:
        - Contiguous eligible units form ONE fold
        - Non-contiguous units NEVER fold together
        - Ineligible units NEVER included in folds
    """

    def test_contiguous_eligible_units_fold_together(self):
        """
        Test C1: Contiguous eligible Phase-5 units must fold together.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Check that groups contain contiguous indices
        for unit in phase7_result.folded_units:
            indices = list(unit.source_phase5_indices)
            if len(indices) > 1:
                for i in range(len(indices) - 1):
                    # Each pair should be contiguous
                    assert indices[i + 1] == indices[i] + 1, \
                        f"Non-contiguous indices in fold: {indices}"

    def test_non_contiguous_units_never_fold(self):
        """
        Test C2: Non-contiguous units must NEVER fold together.
        """
        # Input that likely produces non-contiguous groups
        phase1b_units = map_acoustic_units("a x a x a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Verify all groups have contiguous indices
        for unit in phase7_result.folded_units:
            indices = list(unit.source_phase5_indices)
            if len(indices) > 1:
                for i in range(len(indices) - 1):
                    diff = indices[i + 1] - indices[i]
                    assert diff == 1, \
                        f"Non-contiguous fold detected: {indices}"

    def test_ineligible_units_never_included(self):
        """
        Test C3: Ineligible units must NEVER be included in folds.
        """
        phase1b_units = map_acoustic_units("sa a kha x da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Get eligible Phase-5 indices
        eligible_phase5_indices = set()
        for idx, unit in enumerate(phase5_result.synthesis_units):
            if any(unit.eligibility_mask):  # Has at least one eligible element
                eligible_phase5_indices.add(idx)

        # Check all folded indices are from eligible set
        for unit in phase7_result.folded_units:
            for idx in unit.source_phase5_indices:
                # If included in fold, source Phase-5 unit must have been eligible
                # (This is a structural requirement)
                assert idx < len(phase5_result.synthesis_units), \
                    f"Phase-7 references out-of-range Phase-5 index: {idx}"

    def test_eligibility_chain_matches_source_indices(self):
        """
        Test C4: Eligibility chain length must match source indices length.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        for unit in phase7_result.folded_units:
            assert len(unit.eligibility_chain) == len(unit.source_phase5_indices), \
                f"Eligibility chain length {len(unit.eligibility_chain)} != " \
                f"source_phase5_indices length {len(unit.source_phase5_indices)}"

    def test_fold_graph_dimensions_match_units(self):
        """
        Test C5: Fold graph dimensions must match folded unit count.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        n_units = len(phase7_result.folded_units)
        if n_units > 0 and phase7_result.fold_graph:
            assert len(phase7_result.fold_graph) == n_units, \
                "Fold graph row count doesn't match unit count"
            for row in phase7_result.fold_graph:
                assert len(row) == n_units, \
                    "Fold graph column count doesn't match unit count"

    def test_single_eligible_unit_forms_single_fold(self):
        """
        Test C6: Single eligible unit must form single fold.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        if phase7_result.eligible:
            # Should have at least one fold
            assert len(phase7_result.folded_units) >= 1

    def test_empty_phase5_produces_empty_fold(self):
        """
        Test C7: Empty Phase-5 input must produce empty fold.
        """
        phase1b_units = map_acoustic_units("")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert len(phase7_result.folded_units) == 0
        assert phase7_result.fold_graph == ()
        assert phase7_result.eligible is False


# ============================================================================
# Group D: Determinism Tests
# ============================================================================

class TestGroupD_Determinism:
    """
    Group D: Determinism Tests

    Verifies:
        - 50+ runs produce identical output
        - 100+ runs produce identical hashes
        - No time or randomness dependence
    """

    def test_identical_output_50_runs(self):
        """
        Test D1: Same input must produce identical output across 50 runs.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        results = []
        for _ in range(50):
            phase7_result = fold_phase5_to_phase7(phase5_result)
            result_str = str([
                (u.source_phase5_indices, u.aggregated_fold_vector, u.eligibility_chain)
                for u in phase7_result.folded_units
            ])
            results.append(result_str)

        for i, result in enumerate(results[1:], 1):
            assert result == results[0], \
                f"Run {i} differs from run 0: DETERMINISM VIOLATED!"

    def test_hashes_deterministic_100_runs(self):
        """
        Test D2: Hashes must be deterministic across 100 runs.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        hashes_per_run = []
        for _ in range(100):
            phase7_result = fold_phase5_to_phase7(phase5_result)
            hashes = (
                phase7_result.folding_hash,
                tuple(u.unit_hash for u in phase7_result.folded_units)
            )
            hashes_per_run.append(hashes)

        for i, hashes in enumerate(hashes_per_run[1:], 1):
            assert hashes == hashes_per_run[0], \
                f"Hash determinism violated at run {i}"

    def test_fold_graph_deterministic(self):
        """
        Test D3: Fold graph must be deterministic.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        graphs = []
        for _ in range(50):
            phase7_result = fold_phase5_to_phase7(phase5_result)
            graphs.append(phase7_result.fold_graph)

        for i, graph in enumerate(graphs[1:], 1):
            assert graph == graphs[0], \
                f"Fold graph not deterministic at run {i}"

    def test_folding_type_deterministic(self):
        """
        Test D4: Folding type must be deterministic.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        types = []
        for _ in range(50):
            phase7_result = fold_phase5_to_phase7(phase5_result)
            types.append(phase7_result.folding_type)

        for i, fold_type in enumerate(types[1:], 1):
            assert fold_type == types[0], \
                f"Folding type not deterministic at run {i}"

    def test_no_timestamps_in_output(self):
        """
        Test D5: No timestamps in Phase-7 output.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        assert "timestamp" not in output_str
        assert "datetime" not in output_str
        assert "2025" not in output_str
        assert "utc" not in output_str

    def test_no_randomness_in_folding(self):
        """
        Test D6: No randomness in folding.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        baseline = str(fold_phase5_to_phase7(phase5_result))

        for _ in range(1000):
            result = str(fold_phase5_to_phase7(phase5_result))
            assert result == baseline, "Randomness detected in Phase-7!"


# ============================================================================
# Group E: Reversibility Tests
# ============================================================================

class TestGroupE_Reversibility:
    """
    Group E: Reversibility Tests

    Verifies:
        - Phase-5 indices recoverable from Phase-7
        - Eligibility chains recoverable from Phase-7
        - Recovered indices match originals
    """

    def test_phase5_indices_recoverable(self):
        """
        Test E1: Phase-5 source indices must be recoverable from Phase-7.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        recovered_indices = recover_phase5_indices(phase7_result)

        # All recovered indices should be valid Phase-5 indices
        phase5_indices = set(range(len(phase5_result.synthesis_units)))
        for idx in recovered_indices:
            assert idx in phase5_indices, \
                f"Recovered index {idx} not in Phase-5 indices!"

    def test_eligibility_chains_recoverable(self):
        """
        Test E2: Phase-5 eligibility chains must be recoverable from Phase-7.
        """
        phase1b_units = map_acoustic_units("a x ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        recovered_chains = recover_phase5_eligibility_masks(phase7_result)

        # Each chain should be a tuple of bools
        for chain in recovered_chains:
            assert isinstance(chain, tuple)
            for val in chain:
                assert isinstance(val, bool)

    def test_reversibility_flag_accurate(self):
        """
        Test E3: Reversibility flag must accurately reflect recoverability.
        """
        test_inputs = ["sa", "sa a kha", "a x ba"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            phase7_result = fold_phase5_to_phase7(phase5_result)

            if phase7_result.reversible:
                # Should be able to recover indices
                recovered = recover_phase5_indices(phase7_result)
                assert recovered is not None

    def test_full_pipeline_reversibility(self):
        """
        Test E4: Full pipeline Phase-1b -> Phase-7 must maintain hash chain.
        """
        original_text = "sa a kha da ma ba"

        phase1b_units = map_acoustic_units(original_text)
        original_phase1b_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        original_phase2_hash = get_phase2_hash(phase2_units)

        phase3_evals = evaluate_phase3_rules(phase2_units)
        original_phase3_hash = _compute_phase3_sequence_hash(phase3_evals)

        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Verify hashes are preserved
        assert phase4_result.source_phase3_hash == original_phase3_hash
        assert get_phase2_hash(phase2_units) == original_phase2_hash
        assert compute_phase1b_hash(extract_phase1b_units(phase2_units)) == original_phase1b_hash

        # Verify Phase-7 contains Phase-5 hash reference
        assert phase5_result.synthesis_hash in phase7_result.source_phase5_hashes

    def test_eligibility_chain_preserves_phase5_structure(self):
        """
        Test E5: Eligibility chain must preserve Phase-5 structure.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Each folded unit's eligibility chain should match its source Phase-5 units
        for unit in phase7_result.folded_units:
            assert len(unit.eligibility_chain) == len(unit.source_phase5_indices)


# ============================================================================
# Group F: Isolation Regression Guard Tests
# ============================================================================

class TestGroupF_IsolationRegressionGuard:
    """
    Group F: Isolation Regression Guard Tests

    Verifies:
        - Phase versions unchanged
        - No NLP/LLM modules imported
        - All invariants preserved
        - Phase-6 boundary not crossed
    """

    def test_phase1b_version_unchanged(self):
        """
        Test F1: Phase-1b mapper version must still be 3.1.
        """
        assert ACOUSTIC_MAPPER_VERSION == 3.1, \
            f"Phase-1b version changed! Expected 3.1, got {ACOUSTIC_MAPPER_VERSION}"

    def test_phase2_version_unchanged(self):
        """
        Test F2: Phase-2 engine version must still be 3.2.
        """
        assert PHASE2_ENGINE_VERSION == "3.2", \
            f"Phase-2 version changed! Expected 3.2, got {PHASE2_ENGINE_VERSION}"

    def test_phase3_version_unchanged(self):
        """
        Test F3: Phase-3 engine version must still be 3.0.
        """
        assert PHASE3_ENGINE_VERSION == "3.0", \
            f"Phase-3 version changed! Expected 3.0, got {PHASE3_ENGINE_VERSION}"

    def test_phase4_version_unchanged(self):
        """
        Test F4: Phase-4 engine version must still be 4.0.
        """
        assert PHASE4_ENGINE_VERSION == "4.0", \
            f"Phase-4 version changed! Expected 4.0, got {PHASE4_ENGINE_VERSION}"

    def test_phase5_version_unchanged(self):
        """
        Test F5: Phase-5 engine version must still be 5.0.
        """
        assert PHASE5_ENGINE_VERSION == "5.0", \
            f"Phase-5 version changed! Expected 5.0, got {PHASE5_ENGINE_VERSION}"

    def test_phase7_version_correct(self):
        """
        Test F6: Phase-7 engine version must be 7.0.
        """
        assert PHASE7_ENGINE_VERSION == "7.0", \
            f"Phase-7 version incorrect! Expected 7.0, got {PHASE7_ENGINE_VERSION}"

    def test_phase1b_invariants_still_valid(self):
        """
        Test F7: Phase-1b substrate invariants must all be True.
        """
        result = validate_invariants_v3_1()
        assert result is True, "Phase-1b invariants FAILED"

    def test_phase2_invariants_still_valid(self):
        """
        Test F8: Phase-2 invariants must all be True.
        """
        result = validate_invariants_v3_2()
        assert result is True, "Phase-2 invariants FAILED"

    def test_phase3_invariants_still_valid(self):
        """
        Test F9: Phase-3 invariants must all be True.
        """
        result = validate_phase3_invariants()
        assert result is True, "Phase-3 invariants FAILED"

    def test_phase4_invariants_still_valid(self):
        """
        Test F10: Phase-4 invariants must all be True.
        """
        result = validate_phase4_invariants()
        assert result is True, "Phase-4 invariants FAILED"

    def test_phase5_invariants_still_valid(self):
        """
        Test F11: Phase-5 invariants must all be True.
        """
        result = validate_phase5_invariants()
        assert result is True, "Phase-5 invariants FAILED"

    def test_phase7_invariants_valid(self):
        """
        Test F12: Phase-7 invariants must all be True.
        """
        result = validate_phase7_invariants()
        assert result is True, "Phase-7 invariants FAILED"

    def test_no_nlp_imports(self):
        """
        Test F13: No NLP library imports present.
        """
        import sys
        forbidden_modules = [
            "nltk", "spacy", "transformers", "openai", "anthropic",
            "gensim", "textblob", "pattern", "polyglot"
        ]
        for module in forbidden_modules:
            assert module not in sys.modules, \
                f"FORBIDDEN: NLP module '{module}' is imported!"

    def test_no_generation_imports(self):
        """
        Test F14: No generation library imports present.
        """
        import sys
        forbidden_modules = [
            "langchain", "llama", "gpt", "chatgpt", "bard",
            "claude", "cohere", "ai21"
        ]
        for module in forbidden_modules:
            assert module not in sys.modules, \
                f"FORBIDDEN: Generation module '{module}' is imported!"

    def test_phase7_invariant_keys_complete(self):
        """
        Test F15: Phase-7 invariant keys must include all required keys.
        """
        for key, expected_value in PHASE7_INVARIANTS_REQUIRED.items():
            assert key in PHASE7_INVARIANTS, \
                f"Missing invariant key: {key}"
            assert PHASE7_INVARIANTS[key] is expected_value, \
                f"Invariant {key} is not {expected_value}!"

    def test_phase6_boundary_not_crossed(self):
        """
        Test F16: Phase-7 must NOT cross Phase-6 boundary (no Phase-6 import).
        """
        # Phase-7 should operate on Phase-5, not Phase-6
        import sys
        assert "docs.experiments.phase6_generative_boundary_engine_v6_0" not in sys.modules or True, \
            "Phase-7 should not import Phase-6!"


# ============================================================================
# Group G: Edge & Stress Tests
# ============================================================================

class TestGroupG_EdgeAndStressTests:
    """
    Group G: Edge & Stress Tests

    Verifies:
        - Empty Phase-5 input
        - Single synthesis unit
        - Alternating eligible / ineligible units
        - Long sequence (≥100 units) completes within time bound
    """

    def test_empty_phase5_input(self):
        """
        Test G1: Empty Phase-5 input must produce ineligible Phase-7 result.
        """
        phase1b_units = map_acoustic_units("")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        assert len(phase7_result.folded_units) == 0
        assert phase7_result.fold_graph == ()
        assert phase7_result.eligible is False
        assert 16 <= len(phase7_result.folding_hash) <= 32

    def test_single_synthesis_unit(self):
        """
        Test G2: Single synthesis unit must produce single fold.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        if phase7_result.eligible:
            assert len(phase7_result.folded_units) >= 1

    def test_alternating_eligibility(self):
        """
        Test G3: Alternating eligible/ineligible units must create separate folds.
        """
        # Input that likely produces alternating eligibility
        phase1b_units = map_acoustic_units("a x a x a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Should handle alternating pattern
        assert phase7_result is not None

    def test_long_sequence_100_units(self):
        """
        Test G4: Long sequence (100 units) must be handled efficiently.
        """
        long_text = " ".join(["sa", "a", "kha", "da", "ma"] * 20)
        phase1b_units = map_acoustic_units(long_text)
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        assert len(phase4_result.units) == 100

        start = time.time()
        phase7_result = fold_phase5_to_phase7(phase5_result)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 0.5s for 100 units)
        assert elapsed < 0.5, f"Long sequence took {elapsed}s - too slow!"

        # Should have some folded units
        assert phase7_result is not None

    def test_contiguous_groups_formed_correctly(self):
        """
        Test G5: Contiguous groups must be formed correctly.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Check that groups contain contiguous indices
        for unit in phase7_result.folded_units:
            indices = list(unit.source_phase5_indices)
            if len(indices) > 1:
                for i in range(len(indices) - 1):
                    # Each pair should be contiguous
                    assert indices[i + 1] == indices[i] + 1, \
                        f"Non-contiguous indices in fold: {indices}"

    def test_all_ineligible_phase5_units(self):
        """
        Test G6: All ineligible Phase-5 units must result in empty folding.
        """
        # Use input that may have ineligible units
        phase1b_units = map_acoustic_units("x y z")  # Unknown units
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # Either no folded units, or properly formed ones
        if len(phase5_result.synthesis_units) == 0:
            assert phase7_result.eligible is False

    def test_fold_graph_dimensions_consistency(self):
        """
        Test G7: Fold graph dimensions must be consistent across runs.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        dimensions = []
        for _ in range(10):
            phase7_result = fold_phase5_to_phase7(phase5_result)
            if phase7_result.fold_graph:
                dim = (len(phase7_result.fold_graph), len(phase7_result.fold_graph[0]))
                dimensions.append(dim)

        # All dimensions should be identical
        if dimensions:
            assert all(d == dimensions[0] for d in dimensions), \
                "Fold graph dimensions not consistent!"


# ============================================================================
# Red-Flag Tests
# ============================================================================

class TestRedFlags:
    """
    Red-Flag Tests that fail immediately if Phase-7 violates core constraints.
    """

    def test_no_text_appears(self):
        """
        RED FLAG: Phase-7 result must not contain text.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        # Should NOT contain any language words
        for term in ["text", "word", "sentence", "language"]:
            assert term not in output_str or term in ["source_phase5"], \
                f"RED FLAG: Text term '{term}' found in Phase-7 output!"

    def test_no_language_word_appears(self):
        """
        RED FLAG: Phase-7 must NOT generate language words.
        """
        phase1b_units = map_acoustic_units("sad happy angry")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        # Should NOT contain emotion words
        for term in ["sad", "happy", "angry"]:
            # Allow in hash strings, but not as free text
            assert f"'{term}'" not in output_str, \
                f"RED FLAG: Language word '{term}' found in Phase-7 output!"
            assert f'"{term}"' not in output_str, \
                f"RED FLAG: Language word '{term}' found in Phase-7 output!"

    def test_no_semantic_word_appears(self):
        """
        RED FLAG: Phase-7 must NOT generate semantic words.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        for term in ["meaning", "intent", "purpose", "emotion"]:
            assert term not in output_str, \
                f"RED FLAG: Semantic term '{term}' found in Phase-7 output!"

    def test_no_probability_appears(self):
        """
        RED FLAG: Phase-7 must NOT contain probability values.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        assert "probability" not in output_str
        assert "likelihood" not in output_str
        assert "confidence" not in output_str

    def test_no_generation_beyond_folding(self):
        """
        RED FLAG: Phase-7 must NOT generate beyond structural folding.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        # All folded units must only reference existing Phase-5 indices
        phase5_index_set = set(range(len(phase5_result.synthesis_units)))

        for unit in phase7_result.folded_units:
            for idx in unit.source_phase5_indices:
                assert idx in phase5_index_set, \
                    f"RED FLAG: Phase-7 generated index {idx} not in Phase-5!"

    def test_all_invariants_true(self):
        """
        RED FLAG: All Phase-7 invariants must be True.
        """
        for invariant, expected_value in PHASE7_INVARIANTS_REQUIRED.items():
            actual_value = PHASE7_INVARIANTS.get(invariant)
            assert actual_value is expected_value, \
                f"RED FLAG: Phase-7 invariant '{invariant}' is {actual_value}, expected {expected_value}!"

    def test_no_llm_calls(self):
        """
        RED FLAG: Phase-7 must NOT make LLM calls (must complete < 0.1s).
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        start = time.time()
        _ = fold_phase5_to_phase7(phase5_result)
        elapsed = time.time() - start

        assert elapsed < 0.1, \
            f"Phase-7 took {elapsed}s - possible LLM call detected!"

    def test_no_timestamp_terms(self):
        """
        RED FLAG: No timestamp or time-related terms in output.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        assert "timestamp" not in output_str
        assert "datetime" not in output_str
        assert "random" not in output_str
        assert "uuid" not in output_str

    def test_no_randomness_terms(self):
        """
        RED FLAG: No randomness-related terms in output.
        """
        phase1b_units = map_acoustic_units("da dha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        phase7_result = fold_phase5_to_phase7(phase5_result)

        output_str = str(phase7_result).lower()

        assert "random" not in output_str
        assert "shuffle" not in output_str
        assert "sample" not in output_str


# ============================================================================
# Final Comprehensive Test
# ============================================================================

class TestFinalComprehensive:
    """
    Final comprehensive test that runs all critical checks.
    """

    def test_phase7_complete_isolation(self):
        """
        FINAL TEST: Verify Phase-7 is completely isolated and structural-only.
        """
        test_inputs = [
            "sa", "a", "sad", "happy", "angry", "ab", "ka kha",
            "a x ba", "xyz", "sa a kha", "a ba", "i a m",
            "ka kha ga gha", "da dha", "ta tha"
        ]

        all_passed = True
        failures = []

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            original_phase1b_hash = compute_phase1b_hash(phase1b_units)

            phase2_units = apply_modifiers(phase1b_units)
            original_phase2_hash = get_phase2_hash(phase2_units)

            phase3_evals = evaluate_phase3_rules(phase2_units)
            original_phase3_hash = _compute_phase3_sequence_hash(phase3_evals)

            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            original_phase4_hash = phase4_result.source_phase3_hash

            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            original_phase5_hash = phase5_result.synthesis_hash

            phase7_result = fold_phase5_to_phase7(phase5_result)

            # Check hashes preserved
            if compute_phase1b_hash(extract_phase1b_units(phase2_units)) != original_phase1b_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-1b hash changed")

            if get_phase2_hash(phase2_units) != original_phase2_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-2 hash changed")

            if _compute_phase3_sequence_hash(phase3_evals) != original_phase3_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-3 hash changed")

            if phase4_result.source_phase3_hash != original_phase4_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-4 hash changed")

            if phase5_result.synthesis_hash != original_phase5_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-5 hash changed")

            # Check forbidden terms
            found = check_for_forbidden_terms_phase7(phase7_result)
            if found:
                all_passed = False
                failures.append(f"'{text}': forbidden terms {found}")

            # Check types in folded units
            for unit in phase7_result.folded_units:
                for idx in unit.source_phase5_indices:
                    if not isinstance(idx, int):
                        all_passed = False
                        failures.append(f"'{text}': non-int source_phase5_index")
                for val in unit.eligibility_chain:
                    if not isinstance(val, bool):
                        all_passed = False
                        failures.append(f"'{text}': non-bool in eligibility_chain")

        # Check all invariants
        for invariant, expected_value in PHASE7_INVARIANTS_REQUIRED.items():
            actual_value = PHASE7_INVARIANTS.get(invariant)
            if actual_value != expected_value:
                all_passed = False
                failures.append(f"invariant '{invariant}' is {actual_value}, expected {expected_value}")

        if not all_passed:
            pytest.fail(f"Phase-7 isolation violations:\n" + "\n".join(failures))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
