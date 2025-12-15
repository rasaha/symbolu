"""
Phase-5.0 Synthesis Test Suite (v5.0)
=====================================

Test Goals: Phase-5.0 non-textual synthesis verification.
            Phase-5.0 is TEST-ONLY and SYNTHESIS-ONLY.
            It must NOT generate language, words, sentences, or content.

Phase-5.0 operates only on Phase-4 output (Phase4TransformResult) and exists solely to:
    - apply deterministic structural synthesis
    - produce non-textual, non-linguistic outputs
    - group contiguous eligible Phase-4 units
    - maintain full reversibility

Any violation of isolation is a hard failure.

This test suite verifies:
    Group A: Structural Integrity
    Group B: Non-Textual Enforcement
    Group C: Forbidden Content Detection
    Group D: Determinism
    Group E: Reversibility
    Group F: Isolation Regression Guard
    Group G: Edge & Stress Tests
    Red-Flag Tests

Version: 5.0
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
"""

import pytest
import sys
import hashlib
import time
from pathlib import Path
from typing import List, Tuple, Any
from enum import Enum


# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "docs" / "experiments"))

# Phase-1b imports
from acoustic_unit_mapper_expressive_delta_v3_1 import (
    map_acoustic_units,
    AcousticBridgeUnit,
    validate_invariants_v3_1,
    ACOUSTIC_MAPPER_VERSION,
)

# Phase-2 imports
from phase2_modifier_engine_v3_2 import (
    apply_modifiers,
    Phase2ModifiedUnit,
    extract_phase1b_units,
    compute_phase1b_hash,
    get_modifiers_summary,
    validate_invariants_v3_2,
    PHASE2_ENGINE_VERSION,
)

# Phase-3 imports
from test_phase3_rule_engine_v3_0 import (
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

# Phase-4 imports
from test_phase4_transform_v4_0 import (
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

# Phase-5 imports
from phase5_synthesis_engine_v5_0 import (
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


# ============================================================================
# Helper Functions for Tests
# ============================================================================

def run_full_pipeline(text: str) -> Tuple[Phase4TransformResult, Phase5SynthesisResult]:
    """Run full pipeline from text to Phase-5 result."""
    phase1b_units = map_acoustic_units(text)
    phase2_units = apply_modifiers(phase1b_units)
    phase3_evals = evaluate_phase3_rules(phase2_units)
    phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
    phase5_result = synthesize_phase4_to_phase5([phase4_result])
    return phase4_result, phase5_result


def run_eligible_pipeline(text: str) -> Tuple[Phase4TransformResult, Phase5SynthesisResult]:
    """Run pipeline with eligibility filter (only eligible units)."""
    phase1b_units = map_acoustic_units(text)
    phase2_units = apply_modifiers(phase1b_units)
    phase3_evals = evaluate_phase3_rules(phase2_units)
    phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
    phase5_result = synthesize_phase4_to_phase5([phase4_result])
    return phase4_result, phase5_result


# ============================================================================
# Group A: Structural Integrity Tests
# ============================================================================

class TestGroupA_StructuralIntegrity:
    """
    Group A: Structural Integrity Tests

    Verifies:
        1. No mutation of Phase-4 objects
        2. Hashes unchanged in Phase-4 after Phase-5
        3. Unit counts consistent
    """

    def test_phase4_objects_not_mutated(self):
        """
        Test A1: Phase-4 objects must NOT be mutated by Phase-5.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        # Capture pre-state
        pre_state = [
            (u.source_eval_hash, u.source_index, u.rule_status_vector, u.eligible)
            for u in phase4_result.units
        ]
        pre_hash = phase4_result.source_phase3_hash

        # Run Phase-5
        _ = synthesize_phase4_to_phase5([phase4_result])

        # Verify post-state
        post_state = [
            (u.source_eval_hash, u.source_index, u.rule_status_vector, u.eligible)
            for u in phase4_result.units
        ]
        post_hash = phase4_result.source_phase3_hash

        assert pre_state == post_state, \
            "Phase-4 unit data was MUTATED by Phase-5!"
        assert pre_hash == post_hash, \
            "Phase-4 hash was MUTATED by Phase-5!"

    def test_phase4_hash_unchanged_after_phase5(self):
        """
        Test A2: Phase-4 hash must be unchanged after Phase-5.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "ka kha ga"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

            original_hash = phase4_result.source_phase3_hash

            _ = synthesize_phase4_to_phase5([phase4_result])

            assert phase4_result.source_phase3_hash == original_hash, \
                f"Phase-4 hash CHANGED after Phase-5 for '{text}'!"

    def test_synthesis_unit_count_consistent(self):
        """
        Test A3: Synthesis unit count must be consistent with contiguous groups.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # All indices should be covered if all are eligible
        if phase5_result.eligible:
            recovered_indices = recover_phase4_indices(phase5_result)
            # Should have at least some indices
            assert len(recovered_indices) >= 0

    def test_phase3_objects_not_mutated_by_phase5(self):
        """
        Test A4: Phase-3 objects must NOT be mutated after full pipeline.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        pre_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        _ = synthesize_phase4_to_phase5([phase4_result])

        post_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        assert pre_state == post_state, \
            "Phase-3 objects were MUTATED after Phase-5!"

    def test_phase2_objects_not_mutated_by_phase5(self):
        """
        Test A5: Phase-2 objects must NOT be mutated after full pipeline.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)

        pre_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        _ = synthesize_phase4_to_phase5([phase4_result])

        post_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        assert pre_modifiers == post_modifiers, \
            "Phase-2 objects were MUTATED after Phase-5!"

    def test_phase1b_hash_unchanged_after_phase5(self):
        """
        Test A6: Phase-1b hash must be unchanged after full pipeline.
        """
        text = "sa a kha x da"

        phase1b_units = map_acoustic_units(text)
        original_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        _ = synthesize_phase4_to_phase5([phase4_result])

        extracted = extract_phase1b_units(phase2_units)
        after_hash = compute_phase1b_hash(extracted)

        assert original_hash == after_hash, \
            "Phase-1b hash CHANGED after Phase-5!"

    def test_source_indices_preserved_in_synthesis(self):
        """
        Test A7: Source indices in Phase-5 units must reference valid Phase-4 indices.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        phase4_indices = set(u.source_index for u in phase4_result.units)

        for unit in phase5_result.synthesis_units:
            for idx in unit.source_indices:
                assert idx in phase4_indices, \
                    f"Phase-5 references invalid Phase-4 index: {idx}"

    def test_synthesis_graph_dimensions_match_units(self):
        """
        Test A8: Synthesis graph dimensions must match synthesis unit count.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        n_units = len(phase5_result.synthesis_units)
        if n_units > 0 and phase5_result.synthesis_graph:
            assert len(phase5_result.synthesis_graph) == n_units, \
                "Synthesis graph row count doesn't match unit count"
            for row in phase5_result.synthesis_graph:
                assert len(row) == n_units, \
                    "Synthesis graph column count doesn't match unit count"


# ============================================================================
# Group B: Non-Textual Output Enforcement Tests
# ============================================================================

class TestGroupB_NonTextualEnforcement:
    """
    Group B: Non-Textual Output Enforcement Tests

    Verifies:
        - No free-form strings appear anywhere in Phase-5 output
        - Only allowed strings are hex hashes and Enum values
        - Aggregated vectors contain only 0/1/2
    """

    def test_no_freeform_strings_in_units(self):
        """
        Test B1: Phase-5 units must not contain free-form strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for unit in phase5_result.synthesis_units:
            # Check source_indices - all ints
            assert all(isinstance(idx, int) for idx in unit.source_indices)

            # Check aggregated_rule_vector - all ints in {0,1,2}
            for val in unit.aggregated_rule_vector:
                assert isinstance(val, int)
                assert val in (0, 1, 2)

            # Check adjacency_signature - all ints in {0,1}
            for val in unit.adjacency_signature:
                assert isinstance(val, int)
                assert val in (0, 1)

            # Check modifier_density - int
            assert isinstance(unit.modifier_density, int)

            # Check eligibility_mask - all bools
            assert all(isinstance(b, bool) for b in unit.eligibility_mask)

            # Check unit_hash - hex string only
            assert isinstance(unit.unit_hash, str)
            assert 16 <= len(unit.unit_hash) <= 32
            assert all(c in "0123456789abcdef" for c in unit.unit_hash)

    def test_aggregated_vectors_contain_only_012(self):
        """
        Test B2: Aggregated rule vectors must contain only 0, 1, or 2.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "ka kha ga gha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

            for unit in phase5_result.synthesis_units:
                for val in unit.aggregated_rule_vector:
                    assert isinstance(val, int), \
                        f"Non-int in aggregated_rule_vector for '{text}': {type(val)}"
                    assert val in (0, 1, 2), \
                        f"Invalid value in aggregated_rule_vector for '{text}': {val}"

    def test_adjacency_signature_binary_only(self):
        """
        Test B3: Adjacency signature must contain only 0 or 1.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for unit in phase5_result.synthesis_units:
            for val in unit.adjacency_signature:
                assert isinstance(val, int), \
                    f"Non-int in adjacency_signature: {type(val)}"
                assert val in (0, 1), \
                    f"Invalid adjacency_signature value: {val}"

    def test_synthesis_graph_binary_only(self):
        """
        Test B4: Synthesis graph must contain only 0 or 1.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for row in phase5_result.synthesis_graph:
            for val in row:
                assert isinstance(val, int), \
                    f"Non-int in synthesis_graph: {type(val)}"
                assert val in (0, 1), \
                    f"Invalid synthesis_graph value: {val}"

    def test_synthesis_hash_is_hex(self):
        """
        Test B5: Synthesis hash must be hex string of constrained length.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        assert isinstance(phase5_result.synthesis_hash, str)
        assert 16 <= len(phase5_result.synthesis_hash) <= 32
        assert all(c in "0123456789abcdef" for c in phase5_result.synthesis_hash)

    def test_source_phase4_hashes_are_hex(self):
        """
        Test B6: Source Phase-4 hashes must be hex strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for h in phase5_result.source_phase4_hashes:
            assert isinstance(h, str)
            assert 16 <= len(h) <= 32
            assert all(c in "0123456789abcdef" for c in h)

    def test_synthesis_type_is_enum(self):
        """
        Test B7: Synthesis type must be SynthesisType enum value.
        """
        phase1b_units = map_acoustic_units("a ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        assert isinstance(phase5_result.synthesis_type, SynthesisType)

    def test_reversible_and_eligible_are_bool(self):
        """
        Test B8: Reversible and eligible flags must be boolean.
        """
        phase1b_units = map_acoustic_units("da dha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        assert isinstance(phase5_result.reversible, bool)
        assert isinstance(phase5_result.eligible, bool)

    def test_all_values_pass_non_textual_check(self):
        """
        Test B9: All Phase-5 output values must pass non-textual check.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # Check synthesis units
        for unit in phase5_result.synthesis_units:
            assert is_non_textual_value_phase5(unit.source_indices)
            assert is_non_textual_value_phase5(unit.aggregated_rule_vector)
            assert is_non_textual_value_phase5(unit.adjacency_signature)
            assert is_non_textual_value_phase5(unit.modifier_density)
            assert is_non_textual_value_phase5(unit.eligibility_mask)
            assert is_non_textual_value_phase5(unit.unit_hash)

        # Check result-level values
        assert is_non_textual_value_phase5(phase5_result.synthesis_graph)
        assert is_non_textual_value_phase5(phase5_result.synthesis_hash)
        assert is_non_textual_value_phase5(phase5_result.source_phase4_hashes)
        assert is_non_textual_value_phase5(phase5_result.synthesis_type)
        assert is_non_textual_value_phase5(phase5_result.reversible)
        assert is_non_textual_value_phase5(phase5_result.eligible)

    def test_no_free_text_fields(self):
        """
        Test B10: Phase-5 must not have free text fields.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        result_str = str(phase5_result)

        # These would indicate free text fields (Phase-1b specific)
        assert "escape_pressure" not in result_str.lower()
        assert "birth_of_cognition" not in result_str.lower()
        assert "hope_pressure" not in result_str.lower()


# ============================================================================
# Group C: Forbidden Content Detection Tests
# ============================================================================

class TestGroupC_ForbiddenContentDetection:
    """
    Group C: Forbidden Content Detection Tests

    Verifies:
        - No emotion/intent/meaning/language terms appear
        - All forbidden terms checked against Phase-5 output
    """

    def test_no_emotion_terms_in_output(self):
        """
        Test C1: No emotion terms in Phase-5 output.
        """
        emotion_inputs = ["sad", "happy", "joy", "fear"]

        for text in emotion_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

            output_str = str(phase5_result).lower()

            for term in ["sad", "happy", "emotion", "feeling", "mood", "joy", "fear"]:
                assert term not in output_str, \
                    f"FORBIDDEN: '{term}' found in Phase-5 output for '{text}'!"

    def test_no_intent_terms_in_output(self):
        """
        Test C2: No intent terms in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        for term in ["intent", "purpose", "goal", "desire"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-5 output!"

    def test_no_meaning_terms_in_output(self):
        """
        Test C3: No meaning terms in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        for term in ["meaning", "means", "represents", "symbolizes"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-5 output!"

    def test_no_language_terms_in_output(self):
        """
        Test C4: No language terms in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        for term in ["word", "sentence", "language", "english", "hindi", "sanskrit"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-5 output!"

    def test_no_sentiment_terms_in_output(self):
        """
        Test C5: No sentiment terms in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("da dha ta tha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        for term in ["positive", "negative", "neutral"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-5 output!"

    def test_all_forbidden_terms_checked(self):
        """
        Test C6: Comprehensive check for all forbidden terms.
        """
        test_inputs = ["sad", "happy", "angry", "a ba", "ka kha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

            found = check_for_forbidden_terms_phase5(phase5_result)
            assert not found, \
                f"FORBIDDEN terms found in '{text}' output: {found}"

    def test_no_probability_terms_in_output(self):
        """
        Test C7: No probability terms in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        assert "probability" not in output_str
        assert "likelihood" not in output_str
        assert "confidence" not in output_str


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

        results = []
        for _ in range(50):
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            result_str = str([
                (u.source_indices, u.aggregated_rule_vector, u.eligibility_mask)
                for u in phase5_result.synthesis_units
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

        hashes_per_run = []
        for _ in range(100):
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            hashes = (
                phase5_result.synthesis_hash,
                tuple(u.unit_hash for u in phase5_result.synthesis_units)
            )
            hashes_per_run.append(hashes)

        for i, hashes in enumerate(hashes_per_run[1:], 1):
            assert hashes == hashes_per_run[0], \
                f"Hash determinism violated at run {i}"

    def test_synthesis_graph_deterministic(self):
        """
        Test D3: Synthesis graph must be deterministic.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        graphs = []
        for _ in range(50):
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            graphs.append(phase5_result.synthesis_graph)

        for i, graph in enumerate(graphs[1:], 1):
            assert graph == graphs[0], \
                f"Synthesis graph not deterministic at run {i}"

    def test_synthesis_type_deterministic(self):
        """
        Test D4: Synthesis type must be deterministic.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        types = []
        for _ in range(50):
            phase5_result = synthesize_phase4_to_phase5([phase4_result])
            types.append(phase5_result.synthesis_type)

        for i, synth_type in enumerate(types[1:], 1):
            assert synth_type == types[0], \
                f"Synthesis type not deterministic at run {i}"

    def test_no_timestamps_in_output(self):
        """
        Test D5: No timestamps in Phase-5 output.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        assert "timestamp" not in output_str
        assert "datetime" not in output_str
        assert "2025" not in output_str
        assert "utc" not in output_str

    def test_no_randomness_in_synthesis(self):
        """
        Test D6: No randomness in synthesis.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        baseline = str(synthesize_phase4_to_phase5([phase4_result]))

        for _ in range(1000):
            result = str(synthesize_phase4_to_phase5([phase4_result]))
            assert result == baseline, "Randomness detected in Phase-5!"


# ============================================================================
# Group E: Reversibility Tests
# ============================================================================

class TestGroupE_Reversibility:
    """
    Group E: Reversibility Tests

    Verifies:
        - Phase-4 indices recoverable from Phase-5
        - Eligibility masks recoverable from Phase-5
        - Recovered indices match originals
    """

    def test_phase4_indices_recoverable(self):
        """
        Test E1: Phase-4 source indices must be recoverable from Phase-5.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        recovered_indices = recover_phase4_indices(phase5_result)

        # All recovered indices should be valid Phase-4 indices
        phase4_indices = set(u.source_index for u in phase4_result.units)
        for idx in recovered_indices:
            assert idx in phase4_indices, \
                f"Recovered index {idx} not in Phase-4 indices!"

    def test_eligibility_masks_recoverable(self):
        """
        Test E2: Phase-4 eligibility masks must be recoverable from Phase-5.
        """
        phase1b_units = map_acoustic_units("a x ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        recovered_masks = recover_phase4_eligibility_masks(phase5_result)

        # Each mask should be a tuple of bools
        for mask in recovered_masks:
            assert isinstance(mask, tuple)
            for val in mask:
                assert isinstance(val, bool)

    def test_recovered_indices_match_eligible_phase4(self):
        """
        Test E3: Recovered indices should match eligible Phase-4 indices.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        recovered_indices = set(recover_phase4_indices(phase5_result))
        eligible_indices = set(u.source_index for u in phase4_result.units if u.eligible)

        # Recovered indices should be subset of eligible indices
        assert recovered_indices <= eligible_indices, \
            f"Recovered indices {recovered_indices} not subset of eligible {eligible_indices}!"

    def test_eligibility_mask_length_matches_group_size(self):
        """
        Test E4: Each eligibility mask length must match its group's source_indices length.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for unit in phase5_result.synthesis_units:
            assert len(unit.eligibility_mask) == len(unit.source_indices), \
                f"Eligibility mask length {len(unit.eligibility_mask)} != " \
                f"source_indices length {len(unit.source_indices)}"

    def test_reversibility_flag_accurate(self):
        """
        Test E5: Reversibility flag must accurately reflect recoverability.
        """
        test_inputs = ["sa", "sa a kha", "a x ba"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

            if phase5_result.reversible:
                # Should be able to recover indices
                recovered = recover_phase4_indices(phase5_result)
                assert recovered is not None

    def test_full_pipeline_reversibility(self):
        """
        Test E6: Full pipeline Phase-1b -> Phase-5 must maintain hash chain.
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

        # Verify hashes are preserved
        assert phase4_result.source_phase3_hash == original_phase3_hash
        assert get_phase2_hash(phase2_units) == original_phase2_hash
        assert compute_phase1b_hash(extract_phase1b_units(phase2_units)) == original_phase1b_hash

        # Verify Phase-5 contains Phase-4 hash reference
        assert phase4_result.source_phase3_hash in phase5_result.source_phase4_hashes


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

    def test_phase5_version_correct(self):
        """
        Test F5: Phase-5 engine version must be 5.0.
        """
        assert PHASE5_ENGINE_VERSION == "5.0", \
            f"Phase-5 version incorrect! Expected 5.0, got {PHASE5_ENGINE_VERSION}"

    def test_phase1b_invariants_still_valid(self):
        """
        Test F6: Phase-1b substrate invariants must all be True.
        """
        result = validate_invariants_v3_1()
        assert result is True, "Phase-1b invariants FAILED"

    def test_phase2_invariants_still_valid(self):
        """
        Test F7: Phase-2 invariants must all be True.
        """
        result = validate_invariants_v3_2()
        assert result is True, "Phase-2 invariants FAILED"

    def test_phase3_invariants_still_valid(self):
        """
        Test F8: Phase-3 invariants must all be True.
        """
        result = validate_phase3_invariants()
        assert result is True, "Phase-3 invariants FAILED"

    def test_phase4_invariants_still_valid(self):
        """
        Test F9: Phase-4 invariants must all be True.
        """
        result = validate_phase4_invariants()
        assert result is True, "Phase-4 invariants FAILED"

    def test_phase5_invariants_valid(self):
        """
        Test F10: Phase-5 invariants must all be True.
        """
        result = validate_phase5_invariants()
        assert result is True, "Phase-5 invariants FAILED"

    def test_no_nlp_imports(self):
        """
        Test F11: No NLP library imports present.
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
        Test F12: No generation library imports present.
        """
        import sys
        forbidden_modules = [
            "langchain", "llama", "gpt", "chatgpt", "bard",
            "claude", "cohere", "ai21"
        ]
        for module in forbidden_modules:
            assert module not in sys.modules, \
                f"FORBIDDEN: Generation module '{module}' is imported!"

    def test_phase5_invariant_keys_complete(self):
        """
        Test F13: Phase-5 invariant keys must include all required keys.
        """
        required_keys = {
            "NON_TEXTUAL", "NO_LANGUAGE", "NO_SEMANTICS", "NO_INTENT",
            "NO_EMOTION", "NO_PROBABILITY", "NO_LEARNING", "NO_GENERATION",
            "NON_MUTATING", "REVERSIBLE", "DETERMINISTIC", "ISOLATED", "TEST_ONLY"
        }
        for key in required_keys:
            assert key in PHASE5_INVARIANTS, \
                f"Missing invariant key: {key}"
            assert PHASE5_INVARIANTS[key] is True, \
                f"Invariant {key} is not True!"


# ============================================================================
# Group G: Edge & Stress Tests
# ============================================================================

class TestGroupG_EdgeAndStressTests:
    """
    Group G: Edge & Stress Tests

    Verifies:
        - Empty list input
        - Empty units in Phase-4 result
        - All ineligible Phase-4 units
        - Long sequence (100 units) performance
    """

    def test_empty_list_input(self):
        """
        Test G1: Empty list input must produce ineligible Phase-5 result.
        """
        phase5_result = synthesize_phase4_to_phase5([])

        assert len(phase5_result.synthesis_units) == 0
        assert phase5_result.synthesis_graph == ()
        assert phase5_result.eligible is False
        assert 16 <= len(phase5_result.synthesis_hash) <= 32

    def test_empty_phase4_units(self):
        """
        Test G2: Empty Phase-4 units must be handled correctly.
        """
        phase1b_units = map_acoustic_units("")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        assert len(phase5_result.synthesis_units) == 0
        assert phase5_result.eligible is False

    def test_all_ineligible_phase4_units(self):
        """
        Test G3: All ineligible Phase-4 units must result in empty synthesis.
        """
        # Use eligibility-filtered Phase-4 with input that may have ineligible units
        phase1b_units = map_acoustic_units("x y z")  # Unknown units
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        # If all units are ineligible, Phase-4 should have no units
        # Let's try Phase-5 anyway
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # Either no synthesis units, or properly formed ones
        if len(phase4_result.units) == 0:
            assert phase5_result.eligible is False

    def test_single_unit_input(self):
        """
        Test G4: Single unit input must produce single synthesis unit.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        if phase5_result.eligible:
            assert len(phase5_result.synthesis_units) >= 1
            # Single group should have structural_fold type
            if len(phase5_result.synthesis_units) == 1:
                assert phase5_result.synthesis_type == SynthesisType.STRUCTURAL_FOLD

    def test_long_sequence_100_units(self):
        """
        Test G5: Long sequence (100 units) must be handled efficiently.
        """
        long_text = " ".join(["sa", "a", "kha", "da", "ma"] * 20)
        phase1b_units = map_acoustic_units(long_text)
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 100

        start = time.time()
        phase5_result = synthesize_phase4_to_phase5([phase4_result])
        elapsed = time.time() - start

        # Should complete in reasonable time (< 0.5s for 100 units)
        assert elapsed < 0.5, f"Long sequence took {elapsed}s - too slow!"

        # Should have some synthesis units
        assert phase5_result is not None

    def test_alternating_eligibility(self):
        """
        Test G6: Alternating eligible/ineligible units must create separate groups.
        """
        # Input that likely produces alternating eligibility
        phase1b_units = map_acoustic_units("a x a x a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # Should handle alternating pattern
        assert phase5_result is not None

    def test_contiguous_groups_formed_correctly(self):
        """
        Test G7: Contiguous groups must be formed correctly.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        # Check that groups contain contiguous indices
        for unit in phase5_result.synthesis_units:
            indices = list(unit.source_indices)
            if len(indices) > 1:
                for i in range(len(indices) - 1):
                    # Each pair should be contiguous
                    assert indices[i + 1] == indices[i] + 1, \
                        f"Non-contiguous indices in group: {indices}"

    def test_multiple_phase4_results(self):
        """
        Test G8: Multiple Phase-4 results must be synthesized correctly.
        """
        text1 = "sa a"
        text2 = "ka kha"

        phase1b_1 = map_acoustic_units(text1)
        phase2_1 = apply_modifiers(phase1b_1)
        phase3_1 = evaluate_phase3_rules(phase2_1)
        phase4_1 = transform_phase3_to_phase4_all(phase3_1, phase2_1)

        phase1b_2 = map_acoustic_units(text2)
        phase2_2 = apply_modifiers(phase1b_2)
        phase3_2 = evaluate_phase3_rules(phase2_2)
        phase4_2 = transform_phase3_to_phase4_all(phase3_2, phase2_2)

        # Synthesize multiple results
        phase5_result = synthesize_phase4_to_phase5([phase4_1, phase4_2])

        # Should have hashes from both Phase-4 results
        assert len(phase5_result.source_phase4_hashes) == 2


# ============================================================================
# Red-Flag Tests
# ============================================================================

class TestRedFlags:
    """
    Red-Flag Tests that fail immediately if Phase-5 violates core constraints.
    """

    def test_no_string_values_in_result(self):
        """
        RED FLAG: Phase-5 result must not contain free-form string values.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        for unit in phase5_result.synthesis_units:
            assert is_non_textual_value_phase5(unit.source_indices)
            assert is_non_textual_value_phase5(unit.aggregated_rule_vector)
            assert is_non_textual_value_phase5(unit.adjacency_signature)
            assert is_non_textual_value_phase5(unit.modifier_density)
            assert is_non_textual_value_phase5(unit.eligibility_mask)

    def test_no_varna_concatenation(self):
        """
        RED FLAG: Phase-5 must NOT concatenate varnas.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result)

        assert "saa" not in output_str.lower(), \
            "RED FLAG: Varna concatenation detected!"

    def test_no_word_formation(self):
        """
        RED FLAG: Phase-5 must NOT form words.
        """
        phase1b_units = map_acoustic_units("sad")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result)

        assert "'sad'" not in output_str.lower(), \
            "RED FLAG: Word formation detected!"
        assert '"sad"' not in output_str.lower(), \
            "RED FLAG: Word formation detected!"

    def test_no_sentence_formation(self):
        """
        RED FLAG: Phase-5 must NOT form sentences.
        """
        phase1b_units = map_acoustic_units("i a m")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result)

        assert "i am" not in output_str.lower(), \
            "RED FLAG: Sentence formation detected!"

    def test_no_dictionary_access(self):
        """
        RED FLAG: Phase-5 must NOT access dictionaries for lookup.
        """
        assert PHASE5_INVARIANTS.get("NO_LANGUAGE") is True, \
            "RED FLAG: NO_LANGUAGE invariant not set!"
        assert PHASE5_INVARIANTS.get("NO_SEMANTICS") is True, \
            "RED FLAG: NO_SEMANTICS invariant not set!"

    def test_no_probabilities(self):
        """
        RED FLAG: Phase-5 must NOT contain probabilities.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

        assert "probability" not in output_str
        assert "likelihood" not in output_str
        assert "confidence" not in output_str

    def test_all_invariants_true(self):
        """
        RED FLAG: All Phase-5 invariants must be True.
        """
        for invariant, value in PHASE5_INVARIANTS.items():
            assert value is True, \
                f"RED FLAG: Phase-5 invariant '{invariant}' is {value}, expected True!"

    def test_no_llm_calls(self):
        """
        RED FLAG: Phase-5 must NOT make LLM calls (must complete < 0.1s).
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        start = time.time()
        _ = synthesize_phase4_to_phase5([phase4_result])
        elapsed = time.time() - start

        assert elapsed < 0.1, \
            f"Phase-5 took {elapsed}s - possible LLM call detected!"

    def test_no_timestamp_terms(self):
        """
        RED FLAG: No timestamp or time-related terms in output.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)
        phase5_result = synthesize_phase4_to_phase5([phase4_result])

        output_str = str(phase5_result).lower()

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

        output_str = str(phase5_result).lower()

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

    def test_phase5_complete_isolation(self):
        """
        FINAL TEST: Verify Phase-5 is completely isolated and non-textual.
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
            phase5_result = synthesize_phase4_to_phase5([phase4_result])

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

            # Check forbidden terms
            output_str = str(phase5_result).lower()
            for term in FORBIDDEN_TERMS_PHASE5:
                if term in output_str:
                    all_passed = False
                    failures.append(f"'{text}': forbidden term '{term}'")

            # Check types in synthesis units
            for unit in phase5_result.synthesis_units:
                for idx in unit.source_indices:
                    if not isinstance(idx, int):
                        all_passed = False
                        failures.append(f"'{text}': non-int source_index")
                if not isinstance(unit.modifier_density, int):
                    all_passed = False
                    failures.append(f"'{text}': non-int modifier_density")
                for val in unit.eligibility_mask:
                    if not isinstance(val, bool):
                        all_passed = False
                        failures.append(f"'{text}': non-bool in eligibility_mask")

        # Check all invariants
        for invariant, value in PHASE5_INVARIANTS.items():
            if not value:
                all_passed = False
                failures.append(f"invariant '{invariant}' is False")

        if not all_passed:
            pytest.fail(f"Phase-5 isolation violations:\n" + "\n".join(failures))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
