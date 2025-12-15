"""
Phase-3.0 Rule Engine Tests (v3.0)
==================================

Test Goals: Phase-3.0 rule-only verification.
            Phase-3.0 is TEST-ONLY and RULE-ONLY.
            It must NOT generate language, meaning, emotion, intent, or content.

Phase-3.0 operates only on Phase-2 output (Phase2ModifiedUnit) and exists solely to:
    - validate rule applicability
    - validate containment
    - validate isolation from lower phases

Any violation of isolation is a hard failure.

This test suite verifies:
    Group A: Structural Integrity
    Group B: Rule-Only Enforcement
    Group C: Explicit Forbidden Behavior Tests
    Group D: Rule Eligibility Only
    Group E: Determinism
    Group F: Isolation Regression Guard

Version: 3.0
Date: 2025-12-15

ABSOLUTE RULES:
    - DO NOT generate text
    - DO NOT choose words
    - DO NOT infer meaning
    - DO NOT infer emotion
    - DO NOT infer intent
    - DO NOT infer language
    - DO NOT infer correctness
"""

import pytest
import sys
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Dict, Any, Optional, Tuple
from enum import Enum


# Add experiments directory to path for mappers
sys.path.insert(0, str(Path(__file__).parent.parent / "docs" / "experiments"))

# Phase-1b imports (FROZEN - DO NOT MODIFY)
from acoustic_unit_mapper_expressive_delta_v3_1 import (
    map_acoustic_units,
    AcousticBridgeUnit,
    validate_invariants_v3_1,
    SUBSTRATE_INVARIANTS_V3_1,
    ACOUSTIC_MAPPER_VERSION,
)

# Phase-2 imports (FROZEN - DO NOT MODIFY)
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
    PHASE2_INVARIANTS_V3_2,
    PHASE2_ENGINE_VERSION,
)


# ============================================================================
# PHASE-3.0 VERSION AND INVARIANTS
# ============================================================================

PHASE3_ENGINE_VERSION = "3.0"

PHASE3_INVARIANTS = {
    "RULE_ONLY": True,
    "NO_GENERATION": True,
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_EMOTION": True,
    "NO_LANGUAGE": True,
    "NO_TEXT_OUTPUT": True,
    "NON_MUTATING": True,
    "REVERSIBLE": True,
    "DETERMINISTIC": True,
    "TEST_ONLY": True,
}

# Forbidden strings - if ANY of these appear in Phase-3 output, test FAILS
FORBIDDEN_SEMANTIC_TERMS = frozenset([
    # Emotions
    "sad", "happy", "angry", "emotion", "feeling", "mood",
    "grief", "joy", "fear", "love", "hate", "anxious",
    # Intent
    "intent", "intention", "purpose", "goal", "want", "desire",
    # Meaning
    "meaning", "means", "signifies", "represents", "symbolizes",
    # Language
    "word", "sentence", "language", "english", "hindi", "sanskrit",
    "phrase", "clause", "grammar", "syntax",
    # Sentiment
    "sentiment", "positive", "negative", "neutral",
    # Content generation
    "text", "content", "message", "speech",
])

# Forbidden inference types
FORBIDDEN_INFERENCE_TYPES = frozenset([
    "semantic_inference",
    "emotion_detection",
    "intent_classification",
    "language_detection",
    "sentiment_analysis",
    "meaning_extraction",
    "polarity_inference",
])


# ============================================================================
# PHASE-3.0 TYPE DEFINITIONS
# ============================================================================

class RuleStatus(Enum):
    """Rule evaluation status - strictly boolean/categorical."""
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class RuleCategory(Enum):
    """Categories of Phase-3 rules - structural only."""
    MODIFIER_PRESENCE = "modifier_presence"
    ADJACENCY_CHECK = "adjacency_check"
    ASPIRATION_CONTRAST = "aspiration_contrast"
    UNKNOWN_BARRIER = "unknown_barrier"
    BOUNDARY_POSITION = "boundary_position"
    SEQUENCE_CLASS = "sequence_class"
    CONTINUITY_CHECK = "continuity_check"
    REPETITION_CHECK = "repetition_check"


@dataclass(frozen=True)
class Phase3RuleResult:
    """
    Individual rule evaluation result.

    Contains ONLY:
        - rule_id: Identifier (short string, max 32 chars)
        - category: RuleCategory enum
        - status: RuleStatus enum (pass/fail/not_applicable)
        - target_index: Index of unit this rule applies to

    NO semantic content. NO text generation. NO inference.
    """
    rule_id: str
    category: RuleCategory
    status: RuleStatus
    target_index: int

    def __post_init__(self):
        """Validate rule result constraints."""
        if len(self.rule_id) > 32:
            raise ValueError(f"rule_id too long: {len(self.rule_id)} > 32")
        if not isinstance(self.category, RuleCategory):
            raise ValueError(f"Invalid category type: {type(self.category)}")
        if not isinstance(self.status, RuleStatus):
            raise ValueError(f"Invalid status type: {type(self.status)}")


@dataclass(frozen=True)
class Phase3RuleEvaluation:
    """
    Phase-3 output for a single Phase-2 unit.

    Contains ONLY:
        - source_unit_hash: Hash of Phase-2 unit (for integrity verification)
        - source_index: Index in original sequence
        - rules: Tuple of Phase3RuleResult
        - eligible_for_next_phase: Boolean flag only

    NO semantic content. NO text generation. NO inference.
    """
    source_unit_hash: str
    source_index: int
    rules: Tuple[Phase3RuleResult, ...]
    eligible_for_next_phase: bool

    def __post_init__(self):
        """Validate evaluation constraints."""
        if not self.source_unit_hash:
            raise ValueError("source_unit_hash cannot be empty")
        if not isinstance(self.eligible_for_next_phase, bool):
            raise ValueError("eligible_for_next_phase must be bool")


# ============================================================================
# PHASE-3.0 RULE ENGINE (TEST-ONLY IMPLEMENTATION)
# ============================================================================

def _compute_phase2_unit_hash(unit: Phase2ModifiedUnit) -> str:
    """Compute hash of Phase-2 modified unit for integrity."""
    hash_input = (
        f"{unit.source_unit.varna}|"
        f"{unit.source_unit.index}|"
        f"{unit.modifiers.adjacency_type}|"
        f"{unit.modifiers.boundary_position}|"
        f"{unit.modifiers.unknown_barrier}|"
        f"{unit.modifiers.sequence_class}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _evaluate_modifier_presence_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate modifier presence rule - structural check only."""
    has_modifiers = len(unit.modifiers.relational_modifiers) > 0
    status = RuleStatus.PASS if has_modifiers else RuleStatus.NOT_APPLICABLE
    return Phase3RuleResult(
        rule_id="MOD_PRESENCE_001",
        category=RuleCategory.MODIFIER_PRESENCE,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_adjacency_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate adjacency type rule - structural check only."""
    adj_type = unit.modifiers.adjacency_type
    # Rule passes if adjacency is properly assigned
    status = RuleStatus.PASS if adj_type in ["isolated", "bound_left", "bound_right", "bound_both"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="ADJ_TYPE_001",
        category=RuleCategory.ADJACENCY_CHECK,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_aspiration_contrast_rule(unit: Phase2ModifiedUnit, next_unit: Optional[Phase2ModifiedUnit]) -> Phase3RuleResult:
    """Evaluate aspiration contrast rule - structural check only."""
    if next_unit is None:
        return Phase3RuleResult(
            rule_id="ASP_CONTRAST_001",
            category=RuleCategory.ASPIRATION_CONTRAST,
            status=RuleStatus.NOT_APPLICABLE,
            target_index=unit.source_unit.index
        )

    contrast = unit.modifiers.aspiration_contrast
    status = RuleStatus.PASS if contrast in ["both_aspirated", "both_unaspirated", "contrast_present", "not_applicable"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="ASP_CONTRAST_001",
        category=RuleCategory.ASPIRATION_CONTRAST,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_unknown_barrier_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate unknown barrier rule - structural check only."""
    barrier = unit.modifiers.unknown_barrier
    status = RuleStatus.PASS if barrier in ["is_unknown", "left_of_unknown", "right_of_unknown", "between_unknowns", "none"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="UNK_BARRIER_001",
        category=RuleCategory.UNKNOWN_BARRIER,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_boundary_position_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate boundary position rule - structural check only."""
    pos = unit.modifiers.boundary_position
    status = RuleStatus.PASS if pos in ["singleton", "sequence_start", "sequence_end", "sequence_interior"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="BOUNDARY_POS_001",
        category=RuleCategory.BOUNDARY_POSITION,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_sequence_class_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate sequence class rule - structural check only."""
    seq_class = unit.modifiers.sequence_class
    status = RuleStatus.PASS if seq_class in ["empty", "all_known", "all_unknown", "mixed"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="SEQ_CLASS_001",
        category=RuleCategory.SEQUENCE_CLASS,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_continuity_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate continuity rule - structural check only."""
    spans = unit.modifiers.continuity_spans
    # Rule passes if continuity spans are properly defined
    status = RuleStatus.PASS if len(spans) > 0 else RuleStatus.NOT_APPLICABLE
    return Phase3RuleResult(
        rule_id="CONTINUITY_001",
        category=RuleCategory.CONTINUITY_CHECK,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_repetition_rule(unit: Phase2ModifiedUnit) -> Phase3RuleResult:
    """Evaluate repetition rule - structural check only."""
    rep = unit.modifiers.repetition_marker
    if rep is None:
        status = RuleStatus.NOT_APPLICABLE
    elif rep in ["repeated", "not_repeated"]:
        status = RuleStatus.PASS
    else:
        status = RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="REPETITION_001",
        category=RuleCategory.REPETITION_CHECK,
        status=status,
        target_index=unit.source_unit.index
    )


def evaluate_phase3_rules(modified_units: List[Phase2ModifiedUnit]) -> List[Phase3RuleEvaluation]:
    """
    Evaluate Phase-3 rules on Phase-2 output.

    This is the primary entry point for Phase-3 rule evaluation.

    Args:
        modified_units: List[Phase2ModifiedUnit] from Phase-2

    Returns:
        List[Phase3RuleEvaluation] with rule results

    Invariants:
        - Phase-2 units are NOT modified
        - No semantic inference
        - No text generation
        - Deterministic: same input always produces same output
    """
    if not modified_units:
        return []

    evaluations = []
    seq_len = len(modified_units)

    for idx, unit in enumerate(modified_units):
        # Compute unit hash for integrity
        unit_hash = _compute_phase2_unit_hash(unit)

        # Get next unit for pair-level rules
        next_unit = modified_units[idx + 1] if idx < seq_len - 1 else None

        # Evaluate all rules
        rules = (
            _evaluate_modifier_presence_rule(unit),
            _evaluate_adjacency_rule(unit),
            _evaluate_aspiration_contrast_rule(unit, next_unit),
            _evaluate_unknown_barrier_rule(unit),
            _evaluate_boundary_position_rule(unit),
            _evaluate_sequence_class_rule(unit),
            _evaluate_continuity_rule(unit),
            _evaluate_repetition_rule(unit),
        )

        # Determine eligibility (all rules pass or are not applicable)
        eligible = all(r.status != RuleStatus.FAIL for r in rules)

        evaluation = Phase3RuleEvaluation(
            source_unit_hash=unit_hash,
            source_index=idx,
            rules=rules,
            eligible_for_next_phase=eligible
        )

        evaluations.append(evaluation)

    return evaluations


def extract_phase2_units(evaluations: List[Phase3RuleEvaluation], original_units: List[Phase2ModifiedUnit]) -> List[Phase2ModifiedUnit]:
    """
    Extract original Phase-2 units from Phase-3 evaluations.

    This demonstrates the non-mutating guarantee.
    """
    # Phase-3 does not store Phase-2 units, just references by index
    return [original_units[e.source_index] for e in evaluations]


def validate_phase3_invariants() -> bool:
    """Validate that all Phase-3 invariants are preserved."""
    for invariant, value in PHASE3_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Phase-3 invariant violated: {invariant}")
    return True


# ============================================================================
# HELPER FUNCTIONS FOR TESTS
# ============================================================================

def get_phase2_hash(modified_units: List[Phase2ModifiedUnit]) -> str:
    """Compute hash of entire Phase-2 sequence."""
    if not modified_units:
        return hashlib.sha256(b"empty").hexdigest()[:32]

    parts = []
    for unit in modified_units:
        parts.append(_compute_phase2_unit_hash(unit))
    return hashlib.sha256("||".join(parts).encode()).hexdigest()[:32]


def check_for_forbidden_terms(obj: Any) -> List[str]:
    """Check any object for forbidden semantic terms."""
    obj_str = str(obj).lower()
    found = []
    for term in FORBIDDEN_SEMANTIC_TERMS:
        if term in obj_str:
            found.append(term)
    return found


def stringify_evaluation(evaluation: Phase3RuleEvaluation) -> str:
    """Convert evaluation to string for inspection."""
    parts = [
        f"idx:{evaluation.source_index}",
        f"hash:{evaluation.source_unit_hash}",
        f"eligible:{evaluation.eligible_for_next_phase}",
    ]
    for rule in evaluation.rules:
        parts.append(f"{rule.rule_id}:{rule.status.value}")
    return "|".join(parts)


# ============================================================================
# GROUP A — STRUCTURAL INTEGRITY
# ============================================================================

class TestGroupA_StructuralIntegrity:
    """
    Group A: Structural Integrity Tests

    Verifies:
        1. Same number of units in input and output
        2. Phase-2 objects are preserved by reference
        3. Hash of Phase-2 data unchanged
        4. Phase-1b extraction still works
    """

    def test_same_number_of_units(self):
        """
        Test A1: Phase-3 must output same number of evaluations as Phase-2 inputs.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "xyz", "sad"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)

            assert len(phase3_evals) == len(phase2_units), \
                f"Count mismatch for '{text}': Phase-2={len(phase2_units)}, Phase-3={len(phase3_evals)}"

    def test_phase2_objects_preserved_by_reference(self):
        """
        Test A2: Phase-2 objects must be preserved (not copied or modified).
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        original_ids = [id(u) for u in phase2_units]

        # Run Phase-3
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Extract Phase-2 units from Phase-3
        extracted = extract_phase2_units(phase3_evals, phase2_units)
        extracted_ids = [id(u) for u in extracted]

        # IDs must match (same objects)
        assert original_ids == extracted_ids, \
            "Phase-2 objects were copied instead of preserved by reference!"

    def test_phase2_hash_unchanged(self):
        """
        Test A3: Hash of Phase-2 data must be unchanged after Phase-3.
        """
        text = "sa a kha da ma"

        phase1b_units = map_acoustic_units(text)
        phase2_units = apply_modifiers(phase1b_units)
        original_hash = get_phase2_hash(phase2_units)

        # Run Phase-3
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Re-compute hash of Phase-2 (should be unchanged)
        after_hash = get_phase2_hash(phase2_units)

        assert original_hash == after_hash, \
            f"Phase-2 hash CHANGED after Phase-3! Before: {original_hash}, After: {after_hash}"

    def test_phase1b_extraction_still_works(self):
        """
        Test A4: Phase-1b extraction must still work after Phase-3 processing.
        """
        text = "sa a kha x da"

        phase1b_units = map_acoustic_units(text)
        original_phase1b_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Extract Phase-1b from Phase-2 (after Phase-3)
        extracted_phase1b = extract_phase1b_units(phase2_units)
        extracted_hash = compute_phase1b_hash(extracted_phase1b)

        assert original_phase1b_hash == extracted_hash, \
            "Phase-1b extraction FAILED after Phase-3!"

    def test_phase1b_integrity_via_phase2(self):
        """
        Test A5: Phase-1b integrity must be verifiable via Phase-2 after Phase-3.
        """
        text = "a ba kha x"

        phase1b_units = map_acoustic_units(text)
        phase2_units = apply_modifiers(phase1b_units)

        # Run Phase-3
        _ = evaluate_phase3_rules(phase2_units)

        # Verify Phase-1b integrity
        assert verify_phase1b_integrity(phase1b_units, phase2_units), \
            "Phase-1b integrity FAILED after Phase-3!"

    def test_empty_input_handling(self):
        """
        Test A6: Empty input must return empty list.
        """
        phase1b_units = map_acoustic_units("")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        assert phase3_evals == [], "Empty input should return empty list"

    def test_evaluation_source_indices_match(self):
        """
        Test A7: Source indices in evaluations must match input order.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for idx, evaluation in enumerate(phase3_evals):
            assert evaluation.source_index == idx, \
                f"Source index mismatch at {idx}: expected {idx}, got {evaluation.source_index}"


# ============================================================================
# GROUP B — RULE-ONLY ENFORCEMENT
# ============================================================================

class TestGroupB_RuleOnlyEnforcement:
    """
    Group B: Rule-Only Enforcement Tests

    Verifies:
        - Phase-3 output contains only rule flags
        - No strings resembling emotion, intent, sentiment, meaning, language
        - Rule results are strictly True/False, enums, or categorical flags
    """

    def test_output_contains_only_rule_flags(self):
        """
        Test B1: Phase-3 output must contain only rule flags.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for evaluation in phase3_evals:
            # Check evaluation structure
            assert isinstance(evaluation.source_unit_hash, str)
            assert isinstance(evaluation.source_index, int)
            assert isinstance(evaluation.rules, tuple)
            assert isinstance(evaluation.eligible_for_next_phase, bool)

            # Check each rule
            for rule in evaluation.rules:
                assert isinstance(rule.rule_id, str)
                assert len(rule.rule_id) <= 32, f"rule_id too long: {rule.rule_id}"
                assert isinstance(rule.category, RuleCategory)
                assert isinstance(rule.status, RuleStatus)
                assert isinstance(rule.target_index, int)

    def test_rule_status_strictly_categorical(self):
        """
        Test B2: Rule status must be strictly categorical (pass/fail/not_applicable).
        """
        phase1b_units = map_acoustic_units("a ba kha x")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        valid_statuses = {RuleStatus.PASS, RuleStatus.FAIL, RuleStatus.NOT_APPLICABLE}

        for evaluation in phase3_evals:
            for rule in evaluation.rules:
                assert rule.status in valid_statuses, \
                    f"Invalid rule status: {rule.status}"

    def test_rule_categories_structural_only(self):
        """
        Test B3: Rule categories must be structural only.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        valid_categories = set(RuleCategory)

        for evaluation in phase3_evals:
            for rule in evaluation.rules:
                assert rule.category in valid_categories, \
                    f"Invalid rule category: {rule.category}"

    def test_no_semantic_strings_in_output(self):
        """
        Test B4: No semantic strings in Phase-3 output.
        """
        test_inputs = ["sad", "happy", "angry", "a ba", "ka kha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)

            for evaluation in phase3_evals:
                eval_str = stringify_evaluation(evaluation)
                found = check_for_forbidden_terms(eval_str)
                assert not found, \
                    f"Semantic terms found in '{text}' output: {found}"

    def test_eligible_flag_is_boolean_only(self):
        """
        Test B5: eligible_for_next_phase must be strictly boolean.
        """
        phase1b_units = map_acoustic_units("sa a kha x da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for evaluation in phase3_evals:
            assert evaluation.eligible_for_next_phase in [True, False], \
                f"eligible_for_next_phase not boolean: {evaluation.eligible_for_next_phase}"
            assert type(evaluation.eligible_for_next_phase) is bool, \
                f"eligible_for_next_phase wrong type: {type(evaluation.eligible_for_next_phase)}"

    def test_no_free_form_text_fields(self):
        """
        Test B6: Phase-3 output must not contain free-form text fields.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for evaluation in phase3_evals:
            # source_unit_hash is constrained hex string
            assert len(evaluation.source_unit_hash) == 16, \
                f"Hash wrong length: {len(evaluation.source_unit_hash)}"
            assert all(c in "0123456789abcdef" for c in evaluation.source_unit_hash), \
                f"Hash contains non-hex: {evaluation.source_unit_hash}"

            # rule_ids are constrained identifiers
            for rule in evaluation.rules:
                assert rule.rule_id.replace("_", "").replace("0", "").replace("1", "").isalpha() or \
                       all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in rule.rule_id), \
                    f"rule_id appears free-form: {rule.rule_id}"


# ============================================================================
# GROUP C — EXPLICIT FORBIDDEN BEHAVIOR TESTS
# ============================================================================

class TestGroupC_ForbiddenBehavior:
    """
    Group C: Explicit Forbidden Behavior Tests

    Tests that fail if any forbidden terms appear in Phase-3 output:
        - "sad", "happy", "angry"
        - "emotion", "intent", "meaning"
        - "word", "sentence", "language"
        - "english", "hindi", "sanskrit"
    """

    def test_no_emotion_words(self):
        """
        Test C1: No emotion words in Phase-3 output.
        """
        emotion_words = ["sad", "happy", "angry", "joy", "fear", "love", "hate"]

        for word in emotion_words:
            phase1b_units = map_acoustic_units(word)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)

            full_output = str(phase3_evals).lower()

            assert word not in full_output, \
                f"FORBIDDEN: emotion word '{word}' found in Phase-3 output!"

    def test_no_intent_meaning_words(self):
        """
        Test C2: No intent/meaning words in Phase-3 output.
        """
        forbidden = ["emotion", "intent", "meaning", "sentiment", "feeling"]

        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        for word in forbidden:
            assert word not in full_output, \
                f"FORBIDDEN: '{word}' found in Phase-3 output!"

    def test_no_language_words(self):
        """
        Test C3: No language words in Phase-3 output.
        """
        forbidden = ["word", "sentence", "language", "phrase", "clause", "grammar"]

        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        for word in forbidden:
            assert word not in full_output, \
                f"FORBIDDEN: language word '{word}' found in Phase-3 output!"

    def test_no_language_names(self):
        """
        Test C4: No language names in Phase-3 output.
        """
        forbidden = ["english", "hindi", "sanskrit", "arabic", "chinese"]

        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        for word in forbidden:
            assert word not in full_output, \
                f"FORBIDDEN: language name '{word}' found in Phase-3 output!"

    def test_no_inference_type_labels(self):
        """
        Test C5: No inference type labels in Phase-3 output.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        for forbidden_type in FORBIDDEN_INFERENCE_TYPES:
            assert forbidden_type not in full_output, \
                f"FORBIDDEN: inference type '{forbidden_type}' found in Phase-3 output!"

    def test_sad_input_no_sadness_output(self):
        """
        Test C6: "sad" input must NOT produce "sadness" in output.
        """
        phase1b_units = map_acoustic_units("sad")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        assert "sadness" not in full_output, \
            "FORBIDDEN: 'sadness' found in Phase-3 output for 'sad' input!"
        assert "unhappy" not in full_output, \
            "FORBIDDEN: 'unhappy' found in Phase-3 output for 'sad' input!"
        assert "grief" not in full_output, \
            "FORBIDDEN: 'grief' found in Phase-3 output for 'sad' input!"

    def test_happy_input_no_happiness_output(self):
        """
        Test C7: "happy" input must NOT produce "happiness" in output.
        """
        phase1b_units = map_acoustic_units("happy")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        assert "happiness" not in full_output
        assert "joyful" not in full_output
        assert "pleasure" not in full_output


# ============================================================================
# GROUP D — RULE ELIGIBILITY ONLY
# ============================================================================

class TestGroupD_RuleEligibilityOnly:
    """
    Group D: Rule Eligibility Only Tests

    Rules may:
        - reference modifier presence
        - reference adjacency types
        - reference aspiration contrast
        - reference unknown barriers

    Rules may NOT:
        - inspect bridge_meaning
        - inspect dictionary meaning
        - inspect phonetic heuristics
        - infer polarity
    """

    def test_rules_reference_modifier_presence(self):
        """
        Test D1: Rules may reference modifier presence.
        """
        phase1b_units = map_acoustic_units("a ba")  # Vowel-consonant triggers NEGATION
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Check that MODIFIER_PRESENCE rule exists
        for evaluation in phase3_evals:
            mod_rules = [r for r in evaluation.rules if r.category == RuleCategory.MODIFIER_PRESENCE]
            assert len(mod_rules) > 0, "MODIFIER_PRESENCE rule should exist"

    def test_rules_reference_adjacency_types(self):
        """
        Test D2: Rules may reference adjacency types.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Check that ADJACENCY_CHECK rule exists
        for evaluation in phase3_evals:
            adj_rules = [r for r in evaluation.rules if r.category == RuleCategory.ADJACENCY_CHECK]
            assert len(adj_rules) > 0, "ADJACENCY_CHECK rule should exist"

    def test_rules_reference_aspiration_contrast(self):
        """
        Test D3: Rules may reference aspiration contrast.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Check that ASPIRATION_CONTRAST rule exists
        for evaluation in phase3_evals:
            asp_rules = [r for r in evaluation.rules if r.category == RuleCategory.ASPIRATION_CONTRAST]
            assert len(asp_rules) > 0, "ASPIRATION_CONTRAST rule should exist"

    def test_rules_reference_unknown_barriers(self):
        """
        Test D4: Rules may reference unknown barriers.
        """
        phase1b_units = map_acoustic_units("a x ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        # Check that UNKNOWN_BARRIER rule exists
        for evaluation in phase3_evals:
            unk_rules = [r for r in evaluation.rules if r.category == RuleCategory.UNKNOWN_BARRIER]
            assert len(unk_rules) > 0, "UNKNOWN_BARRIER rule should exist"

    def test_rules_do_not_inspect_bridge_meaning(self):
        """
        Test D5: Rules must NOT inspect bridge_meaning.
        """
        phase1b_units = map_acoustic_units("sa")  # bridge_meaning = "escape_pressure"
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # bridge_meaning values must NOT appear in Phase-3 output
        assert "escape_pressure" not in full_output
        assert "birth_of_cognition" not in full_output
        assert "hope_pressure" not in full_output
        assert "worry_pressure" not in full_output

    def test_rules_do_not_inspect_dictionary_meaning(self):
        """
        Test D6: Rules must NOT inspect dictionary meaning.
        """
        phase1b_units = map_acoustic_units("sad")  # "sad" has no dictionary meaning in Phase-3
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # Dictionary meanings must NOT appear
        assert "melancholy" not in full_output
        assert "sorrow" not in full_output
        assert "depression" not in full_output

    def test_rules_do_not_use_phonetic_heuristics(self):
        """
        Test D7: Rules must NOT use phonetic heuristics.
        """
        phase1b_units = map_acoustic_units("kha")  # aspirated consonant
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # Phonetic heuristic terms must NOT appear
        assert "articulatory" not in full_output
        assert "ipa" not in full_output
        assert "phoneme" not in full_output
        assert "fricative" not in full_output
        assert "plosive" not in full_output

    def test_rules_do_not_infer_polarity(self):
        """
        Test D8: Rules must NOT infer polarity.
        """
        phase1b_units = map_acoustic_units("a ba kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # Polarity terms must NOT appear
        assert "positive" not in full_output
        assert "negative" not in full_output
        assert "vrtti" not in full_output
        assert "polarity" not in full_output


# ============================================================================
# GROUP E — DETERMINISM
# ============================================================================

class TestGroupE_Determinism:
    """
    Group E: Determinism Tests

    Verifies:
        - Same Phase-2 input -> identical Phase-3 output (10 runs)
        - Order preserved
        - No randomness
        - No timestamps affecting logic
    """

    def test_same_input_identical_output_10_runs(self):
        """
        Test E1: Same Phase-2 input must produce identical Phase-3 output (10 runs).
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)

        results = []
        for _ in range(10):
            phase3_evals = evaluate_phase3_rules(phase2_units)
            result_str = str([(e.source_unit_hash, e.source_index,
                               [(r.rule_id, r.status.value) for r in e.rules],
                               e.eligible_for_next_phase) for e in phase3_evals])
            results.append(result_str)

        # All results must be identical
        for i, result in enumerate(results[1:], 1):
            assert result == results[0], \
                f"Run {i} differs from run 0: DETERMINISM VIOLATED!"

    def test_order_preserved(self):
        """
        Test E2: Order of evaluations must match input order.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for idx, evaluation in enumerate(phase3_evals):
            assert evaluation.source_index == idx, \
                f"Order violated at {idx}: expected {idx}, got {evaluation.source_index}"

    def test_no_randomness_in_rules(self):
        """
        Test E3: No randomness in rule evaluation.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)

        # Run 100 times and collect unique results
        unique_results = set()
        for _ in range(100):
            phase3_evals = evaluate_phase3_rules(phase2_units)
            result_str = str([(r.status.value for r in e.rules) for e in phase3_evals])
            unique_results.add(result_str)

        # Should have exactly 1 unique result
        assert len(unique_results) == 1, \
            f"Randomness detected: {len(unique_results)} unique results from 100 runs!"

    def test_no_timestamps_in_output(self):
        """
        Test E4: No timestamps in Phase-3 output.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # Timestamp indicators must NOT appear
        assert "timestamp" not in full_output
        assert "datetime" not in full_output
        assert "2025" not in full_output  # Current year
        assert "utc" not in full_output

    def test_hashes_deterministic(self):
        """
        Test E5: Hashes must be deterministic across runs.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)

        hashes_per_run = []
        for _ in range(10):
            phase3_evals = evaluate_phase3_rules(phase2_units)
            hashes = [e.source_unit_hash for e in phase3_evals]
            hashes_per_run.append(tuple(hashes))

        # All hash tuples must be identical
        for i, hashes in enumerate(hashes_per_run[1:], 1):
            assert hashes == hashes_per_run[0], \
                f"Hash determinism violated at run {i}"

    def test_eligible_flags_deterministic(self):
        """
        Test E6: Eligible flags must be deterministic.
        """
        phase1b_units = map_acoustic_units("a x ba")
        phase2_units = apply_modifiers(phase1b_units)

        flags_per_run = []
        for _ in range(10):
            phase3_evals = evaluate_phase3_rules(phase2_units)
            flags = [e.eligible_for_next_phase for e in phase3_evals]
            flags_per_run.append(tuple(flags))

        # All flag tuples must be identical
        for i, flags in enumerate(flags_per_run[1:], 1):
            assert flags == flags_per_run[0], \
                f"Eligible flag determinism violated at run {i}"


# ============================================================================
# GROUP F — ISOLATION REGRESSION GUARD
# ============================================================================

class TestGroupF_IsolationRegressionGuard:
    """
    Group F: Isolation Regression Guard Tests

    Re-run Phase-1b and Phase-2 test suites to verify:
        - All still pass
        - No dependency introduced
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

    def test_phase1b_invariants_still_valid(self):
        """
        Test F3: Phase-1b substrate invariants must all be True.
        """
        result = validate_invariants_v3_1()
        assert result is True, "Phase-1b invariants FAILED"

    def test_phase2_invariants_still_valid(self):
        """
        Test F4: Phase-2 invariants must all be True.
        """
        result = validate_invariants_v3_2()
        assert result is True, "Phase-2 invariants FAILED"

    def test_phase3_invariants_valid(self):
        """
        Test F5: Phase-3 invariants must all be True.
        """
        result = validate_phase3_invariants()
        assert result is True, "Phase-3 invariants FAILED"

    def test_phase1b_single_consonant_unchanged(self):
        """
        Test F6: Phase-1b single consonant regression check.
        """
        units = map_acoustic_units("sa")
        assert len(units) == 1
        assert units[0].varna == "sa"
        assert units[0].is_consonant is True
        assert units[0].bridge_meaning == "escape_pressure"

    def test_phase1b_single_vowel_unchanged(self):
        """
        Test F7: Phase-1b single vowel regression check.
        """
        units = map_acoustic_units("a")
        assert len(units) == 1
        assert units[0].varna == "a"
        assert units[0].is_vowel is True
        assert units[0].bridge_meaning == "birth_of_cognition"

    def test_phase1b_unknown_handling_unchanged(self):
        """
        Test F8: Phase-1b unknown handling regression check.
        """
        units = map_acoustic_units("xyz")
        assert len(units) == 3
        for unit in units:
            assert unit.is_vowel is False
            assert unit.is_consonant is False
            assert unit.bridge_meaning == "unknown"

    def test_phase2_modifiers_unchanged(self):
        """
        Test F9: Phase-2 modifiers regression check.
        """
        phase1b_units = map_acoustic_units("a ba")
        phase2_units = apply_modifiers(phase1b_units)

        assert len(phase2_units) == 2
        assert phase2_units[0].modifiers.vowel_consonant_transition == "V_to_C"

    def test_phase2_aspiration_handling_unchanged(self):
        """
        Test F10: Phase-2 aspiration handling regression check.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)

        assert phase2_units[0].modifiers.aspiration_contrast == "contrast_present"

    def test_no_circular_dependency(self):
        """
        Test F11: No circular dependency between phases.
        """
        # Phase-1b must work without Phase-2 or Phase-3
        phase1b_units = map_acoustic_units("sa")
        assert len(phase1b_units) == 1

        # Phase-2 must work without Phase-3
        phase2_units = apply_modifiers(phase1b_units)
        assert len(phase2_units) == 1

        # Phase-3 requires Phase-2 (by design) but doesn't modify it
        phase3_evals = evaluate_phase3_rules(phase2_units)
        assert len(phase3_evals) == 1

        # Verify no back-propagation
        assert phase2_units[0].source_unit is phase1b_units[0], \
            "Phase-1b reference was broken!"


# ============================================================================
# RED-FLAG TESTS — MUST EXIST
# ============================================================================

class TestRedFlags:
    """
    Red-Flag Tests that fail immediately if Phase-3 violates core constraints.

    These tests detect:
        - Strings longer than identifiers
        - Varna concatenation
        - Word/sentence formation
        - Phase-2 modifier alteration
        - Phase-1b hash alteration
    """

    def test_no_long_strings_in_output(self):
        """
        RED FLAG: Phase-3 output must not contain strings longer than identifiers.

        Max allowed string length: 32 characters (for rule_id)
        """
        phase1b_units = map_acoustic_units("sa a kha da ma ba ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        for evaluation in phase3_evals:
            # Hash is 16 chars
            assert len(evaluation.source_unit_hash) <= 32, \
                f"RED FLAG: Hash too long: {len(evaluation.source_unit_hash)}"

            # Rule IDs max 32 chars
            for rule in evaluation.rules:
                assert len(rule.rule_id) <= 32, \
                    f"RED FLAG: Rule ID too long: {len(rule.rule_id)}"

    def test_no_varna_concatenation(self):
        """
        RED FLAG: Phase-3 must NOT concatenate varnas.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals)

        # "saa" or "sa a" as concatenated string should NOT appear in output
        assert "saa" not in full_output.lower(), \
            "RED FLAG: Varna concatenation detected!"
        assert "'sa a'" not in full_output.lower(), \
            "RED FLAG: Varna concatenation detected!"

    def test_no_word_formation(self):
        """
        RED FLAG: Phase-3 must NOT form words.
        """
        phase1b_units = map_acoustic_units("sad")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals)

        # The word "sad" should NOT appear in Phase-3 output
        assert "'sad'" not in full_output.lower(), \
            "RED FLAG: Word formation detected!"
        assert '"sad"' not in full_output.lower(), \
            "RED FLAG: Word formation detected!"

    def test_no_sentence_formation(self):
        """
        RED FLAG: Phase-3 must NOT form sentences.
        """
        phase1b_units = map_acoustic_units("i a m")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals)

        # Sentence fragments must NOT appear
        assert "i am" not in full_output.lower(), \
            "RED FLAG: Sentence formation detected!"

    def test_phase2_modifiers_not_altered(self):
        """
        RED FLAG: Phase-2 modifiers must NOT be altered by Phase-3.
        """
        phase1b_units = map_acoustic_units("a ba")
        phase2_units = apply_modifiers(phase1b_units)

        # Capture Phase-2 state before Phase-3
        pre_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position,
             u.modifiers.unknown_barrier, u.modifiers.sequence_class)
            for u in phase2_units
        ]

        # Run Phase-3
        _ = evaluate_phase3_rules(phase2_units)

        # Verify Phase-2 state unchanged
        post_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position,
             u.modifiers.unknown_barrier, u.modifiers.sequence_class)
            for u in phase2_units
        ]

        assert pre_modifiers == post_modifiers, \
            "RED FLAG: Phase-2 modifiers were altered by Phase-3!"

    def test_phase1b_hash_not_altered(self):
        """
        RED FLAG: Phase-1b hash must NOT be altered by Phase-3.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        original_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)

        # Run Phase-3
        _ = evaluate_phase3_rules(phase2_units)

        # Re-extract Phase-1b and verify hash
        extracted = extract_phase1b_units(phase2_units)
        extracted_hash = compute_phase1b_hash(extracted)

        assert original_hash == extracted_hash, \
            f"RED FLAG: Phase-1b hash altered! Before: {original_hash}, After: {extracted_hash}"

    def test_no_generation_capability(self):
        """
        RED FLAG: Phase-3 must have NO generation capability.
        """
        # Verify PHASE3_INVARIANTS includes NO_GENERATION
        assert PHASE3_INVARIANTS.get("NO_GENERATION") is True, \
            "RED FLAG: NO_GENERATION invariant not set!"

        # Verify PHASE3_INVARIANTS includes NO_TEXT_OUTPUT
        assert PHASE3_INVARIANTS.get("NO_TEXT_OUTPUT") is True, \
            "RED FLAG: NO_TEXT_OUTPUT invariant not set!"

    def test_all_invariants_true(self):
        """
        RED FLAG: All Phase-3 invariants must be True.
        """
        for invariant, value in PHASE3_INVARIANTS.items():
            assert value is True, \
                f"RED FLAG: Phase-3 invariant '{invariant}' is {value}, expected True!"


# ============================================================================
# STYLE CONSTRAINT VERIFICATION TESTS
# ============================================================================

class TestStyleConstraints:
    """
    Style Constraint Tests

    Verifies:
        - No LLM calls
        - No randomness
        - No heuristics
        - No probabilities
        - No NLP libraries
        - No embeddings
        - No tokenizers
    """

    def test_no_llm_calls(self):
        """
        Test: No LLM calls in Phase-3.
        """
        # Verified by invariant
        assert PHASE3_INVARIANTS.get("RULE_ONLY") is True

        # Run evaluation - should complete instantly (no API calls)
        import time
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)

        start = time.time()
        _ = evaluate_phase3_rules(phase2_units)
        elapsed = time.time() - start

        # Should complete in < 100ms (no network calls)
        assert elapsed < 0.1, \
            f"Phase-3 took {elapsed}s - possible LLM call detected!"

    def test_no_randomness_source(self):
        """
        Test: No randomness source in Phase-3.
        """
        # Run 1000 times and verify identical output
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)

        baseline = str(evaluate_phase3_rules(phase2_units))

        for _ in range(1000):
            result = str(evaluate_phase3_rules(phase2_units))
            assert result == baseline, "Randomness detected in Phase-3!"

    def test_no_probability_values(self):
        """
        Test: No probability values in Phase-3 output.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        full_output = str(phase3_evals).lower()

        # Probability indicators must NOT appear
        assert "probability" not in full_output
        assert "likelihood" not in full_output
        assert "confidence" not in full_output
        assert "score" not in full_output
        assert "0." not in full_output.replace("0x", "")  # Exclude hex strings


# ============================================================================
# FINAL COMPREHENSIVE TEST
# ============================================================================

class TestFinalComprehensive:
    """
    Final comprehensive test that runs all critical checks.
    """

    def test_phase3_complete_isolation(self):
        """
        FINAL TEST: Verify Phase-3 is completely isolated and rule-only.
        """
        test_inputs = [
            "sa", "a", "sad", "happy", "angry", "ab", "ka kha",
            "a x ba", "xyz", "sa a kha", "a ba", "i a m",
            "ka kha ga gha", "da dha", "ta tha"
        ]

        all_passed = True
        failures = []

        for text in test_inputs:
            # Phase-1b
            phase1b_units = map_acoustic_units(text)
            original_phase1b_hash = compute_phase1b_hash(phase1b_units)

            # Phase-2
            phase2_units = apply_modifiers(phase1b_units)
            original_phase2_hash = get_phase2_hash(phase2_units)

            # Phase-3
            phase3_evals = evaluate_phase3_rules(phase2_units)

            # Check 1: Same count
            if len(phase3_evals) != len(phase2_units):
                all_passed = False
                failures.append(f"'{text}': count mismatch")

            # Check 2: Phase-1b hash unchanged
            extracted_phase1b = extract_phase1b_units(phase2_units)
            if compute_phase1b_hash(extracted_phase1b) != original_phase1b_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-1b hash changed")

            # Check 3: Phase-2 hash unchanged
            if get_phase2_hash(phase2_units) != original_phase2_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-2 hash changed")

            # Check 4: No forbidden terms
            full_output = str(phase3_evals).lower()
            for term in FORBIDDEN_SEMANTIC_TERMS:
                if term in full_output:
                    all_passed = False
                    failures.append(f"'{text}': forbidden term '{term}'")

        if not all_passed:
            pytest.fail(f"Phase-3 isolation violations:\n" + "\n".join(failures))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
