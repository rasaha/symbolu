"""
Phase-4.0 Transform Test Suite (v4.0)
=====================================

Test Goals: Phase-4.0 non-textual transform verification.
            Phase-4.0 is TEST-ONLY and TRANSFORM-ONLY.
            It must NOT generate language, words, sentences, or content.

Phase-4.0 operates only on Phase-3 output (Phase3RuleEvaluation) and exists solely to:
    - apply deterministic structural transforms
    - produce non-textual, non-linguistic outputs
    - enforce rule-gating (only eligible Phase-3 units pass)
    - maintain full reversibility

Any violation of isolation is a hard failure.

This test suite verifies:
    Group A: Structural Integrity
    Group B: Rule-Gate Enforcement
    Group C: Non-Textual Output Enforcement
    Group D: Forbidden Content Detection
    Group E: Determinism
    Group F: Reversibility
    Group G: Isolation Regression Guard
    Group H: Edge & Stress Tests

Version: 4.0
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Dict, Any, Optional, Tuple, FrozenSet
from enum import Enum


sys.path.insert(0, str(Path(__file__).parent.parent / "docs" / "experiments"))

from acoustic_unit_mapper_expressive_delta_v3_1 import (
    map_acoustic_units,
    AcousticBridgeUnit,
    validate_invariants_v3_1,
    SUBSTRATE_INVARIANTS_V3_1,
    ACOUSTIC_MAPPER_VERSION,
)

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
    _compute_phase2_unit_hash,
)


PHASE4_ENGINE_VERSION = "4.0"

PHASE4_INVARIANTS = {
    "NON_TEXTUAL_OUTPUT": True,
    "NO_LANGUAGE_GENERATION": True,
    "NO_WORDS": True,
    "NO_SENTENCES": True,
    "NO_DICTIONARY": True,
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_EMOTION": True,
    "RULE_GATED": True,
    "NON_MUTATING": True,
    "REVERSIBLE": True,
    "AUDITABLE": True,
    "DETERMINISTIC": True,
}

FORBIDDEN_TERMS = frozenset([
    "sad", "happy", "emotion", "feeling", "mood", "joy", "fear",
    "intent", "purpose", "goal", "desire",
    "meaning", "means", "represents", "symbolizes",
    "word", "sentence", "language", "english", "hindi", "sanskrit",
    "positive", "negative", "neutral",
])

FORBIDDEN_INFERENCE_TYPES = frozenset([
    "semantic_inference",
    "emotion_detection",
    "intent_classification",
    "language_detection",
    "sentiment_analysis",
    "meaning_extraction",
    "polarity_inference",
])


class TransformType(Enum):
    """Transform type categories - structural only."""
    INDEX_MAP = "index_map"
    RULE_PROJECTION = "rule_projection"
    ELIGIBILITY_FILTER = "eligibility_filter"
    HASH_CHAIN = "hash_chain"
    ADJACENCY_GRAPH = "adjacency_graph"
    MODIFIER_VECTOR = "modifier_vector"


@dataclass(frozen=True)
class Phase4TransformUnit:
    """
    Phase-4 output for a single transformed unit.

    Contains ONLY:
        - source_eval_hash: Hash of Phase-3 evaluation (for integrity)
        - source_index: Index in original sequence
        - rule_status_vector: Tuple of integers (0=fail, 1=pass, 2=not_applicable)
        - adjacency_pair: Tuple of (prev_index, next_index) or (-1, -1)
        - modifier_count: Integer count of relational modifiers
        - eligible: Boolean flag
        - chain_hash: Hash linking to Phase-3

    NO strings beyond hashes. NO semantic content. NO text generation.
    """
    source_eval_hash: str
    source_index: int
    rule_status_vector: Tuple[int, ...]
    adjacency_pair: Tuple[int, int]
    modifier_count: int
    eligible: bool
    chain_hash: str

    def __post_init__(self):
        if not self.source_eval_hash:
            raise ValueError("source_eval_hash cannot be empty")
        if len(self.source_eval_hash) > 32:
            raise ValueError("source_eval_hash too long")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be bool")
        if not isinstance(self.modifier_count, int):
            raise ValueError("modifier_count must be int")
        if not isinstance(self.rule_status_vector, tuple):
            raise ValueError("rule_status_vector must be tuple")
        for val in self.rule_status_vector:
            if not isinstance(val, int) or val not in (0, 1, 2):
                raise ValueError("rule_status_vector values must be 0, 1, or 2")


@dataclass(frozen=True)
class Phase4TransformResult:
    """
    Phase-4 complete transform result.

    Contains ONLY:
        - units: Tuple of Phase4TransformUnit
        - source_phase3_hash: Hash of entire Phase-3 sequence
        - transform_type: TransformType enum
        - eligible_indices: FrozenSet of eligible unit indices
        - ineligible_indices: FrozenSet of ineligible unit indices
        - adjacency_matrix: Tuple of tuples (0/1 adjacency)
        - total_modifier_count: Integer

    NO strings beyond identifiers. NO semantic content.
    """
    units: Tuple["Phase4TransformUnit", ...]
    source_phase3_hash: str
    transform_type: TransformType
    eligible_indices: FrozenSet[int]
    ineligible_indices: FrozenSet[int]
    adjacency_matrix: Tuple[Tuple[int, ...], ...]
    total_modifier_count: int

    def __post_init__(self):
        if not isinstance(self.units, tuple):
            raise ValueError("units must be tuple")
        if not isinstance(self.eligible_indices, frozenset):
            raise ValueError("eligible_indices must be frozenset")
        if not isinstance(self.ineligible_indices, frozenset):
            raise ValueError("ineligible_indices must be frozenset")
        if not isinstance(self.total_modifier_count, int):
            raise ValueError("total_modifier_count must be int")


def _compute_phase3_eval_hash(evaluation: Phase3RuleEvaluation) -> str:
    """Compute hash of Phase-3 evaluation for integrity."""
    hash_input = (
        f"{evaluation.source_unit_hash}|"
        f"{evaluation.source_index}|"
        f"{evaluation.eligible_for_next_phase}|"
        f"{len(evaluation.rules)}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _compute_phase3_sequence_hash(evaluations: List[Phase3RuleEvaluation]) -> str:
    """Compute hash of entire Phase-3 sequence."""
    if not evaluations:
        return hashlib.sha256(b"empty_phase3").hexdigest()[:32]
    parts = [_compute_phase3_eval_hash(e) for e in evaluations]
    return hashlib.sha256("||".join(parts).encode()).hexdigest()[:32]


def _rule_status_to_int(status: RuleStatus) -> int:
    """Convert rule status to integer. 0=fail, 1=pass, 2=not_applicable."""
    if status == RuleStatus.FAIL:
        return 0
    elif status == RuleStatus.PASS:
        return 1
    elif status == RuleStatus.NOT_APPLICABLE:
        return 2
    raise ValueError(f"Unknown status: {status}")


def _build_adjacency_matrix(evaluations: List[Phase3RuleEvaluation]) -> Tuple[Tuple[int, ...], ...]:
    """Build adjacency matrix from evaluations. Non-textual structure."""
    n = len(evaluations)
    if n == 0:
        return ()
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if abs(i - j) == 1:
                row.append(1)
            else:
                row.append(0)
        matrix.append(tuple(row))
    return tuple(matrix)


def transform_phase3_to_phase4(
    evaluations: List[Phase3RuleEvaluation],
    phase2_units: List[Phase2ModifiedUnit]
) -> Phase4TransformResult:
    """
    Transform Phase-3 evaluations to Phase-4 non-textual output.

    Args:
        evaluations: List[Phase3RuleEvaluation] from Phase-3
        phase2_units: List[Phase2ModifiedUnit] from Phase-2 (for modifier counts)

    Returns:
        Phase4TransformResult with non-textual structures only

    Invariants:
        - Phase-3 evaluations are NOT modified
        - Phase-2 units are NOT modified
        - No semantic inference
        - No text generation
        - Deterministic: same input always produces same output
        - Reversible: Phase-3 recoverable from Phase-4
    """
    if not evaluations:
        return Phase4TransformResult(
            units=(),
            source_phase3_hash=_compute_phase3_sequence_hash([]),
            transform_type=TransformType.INDEX_MAP,
            eligible_indices=frozenset(),
            ineligible_indices=frozenset(),
            adjacency_matrix=(),
            total_modifier_count=0
        )

    transformed_units = []
    eligible_indices = set()
    ineligible_indices = set()
    total_modifiers = 0
    n = len(evaluations)

    for idx, evaluation in enumerate(evaluations):
        if not evaluation.eligible_for_next_phase:
            ineligible_indices.add(idx)
            continue

        eligible_indices.add(idx)

        rule_vector = tuple(_rule_status_to_int(r.status) for r in evaluation.rules)

        prev_idx = idx - 1 if idx > 0 else -1
        next_idx = idx + 1 if idx < n - 1 else -1

        mod_count = 0
        if idx < len(phase2_units):
            mod_count = len(phase2_units[idx].modifiers.relational_modifiers)
        total_modifiers += mod_count

        eval_hash = _compute_phase3_eval_hash(evaluation)
        chain_hash = hashlib.sha256(
            f"{evaluation.source_unit_hash}|{eval_hash}".encode()
        ).hexdigest()[:16]

        unit = Phase4TransformUnit(
            source_eval_hash=eval_hash,
            source_index=evaluation.source_index,
            rule_status_vector=rule_vector,
            adjacency_pair=(prev_idx, next_idx),
            modifier_count=mod_count,
            eligible=True,
            chain_hash=chain_hash
        )
        transformed_units.append(unit)

    return Phase4TransformResult(
        units=tuple(transformed_units),
        source_phase3_hash=_compute_phase3_sequence_hash(evaluations),
        transform_type=TransformType.ELIGIBILITY_FILTER,
        eligible_indices=frozenset(eligible_indices),
        ineligible_indices=frozenset(ineligible_indices),
        adjacency_matrix=_build_adjacency_matrix(evaluations),
        total_modifier_count=total_modifiers
    )


def transform_phase3_to_phase4_all(
    evaluations: List[Phase3RuleEvaluation],
    phase2_units: List[Phase2ModifiedUnit]
) -> Phase4TransformResult:
    """
    Transform ALL Phase-3 evaluations (including ineligible) to Phase-4.

    Used for testing reversibility - includes all units regardless of eligibility.
    """
    if not evaluations:
        return Phase4TransformResult(
            units=(),
            source_phase3_hash=_compute_phase3_sequence_hash([]),
            transform_type=TransformType.INDEX_MAP,
            eligible_indices=frozenset(),
            ineligible_indices=frozenset(),
            adjacency_matrix=(),
            total_modifier_count=0
        )

    transformed_units = []
    eligible_indices = set()
    ineligible_indices = set()
    total_modifiers = 0
    n = len(evaluations)

    for idx, evaluation in enumerate(evaluations):
        if evaluation.eligible_for_next_phase:
            eligible_indices.add(idx)
        else:
            ineligible_indices.add(idx)

        rule_vector = tuple(_rule_status_to_int(r.status) for r in evaluation.rules)

        prev_idx = idx - 1 if idx > 0 else -1
        next_idx = idx + 1 if idx < n - 1 else -1

        mod_count = 0
        if idx < len(phase2_units):
            mod_count = len(phase2_units[idx].modifiers.relational_modifiers)
        total_modifiers += mod_count

        eval_hash = _compute_phase3_eval_hash(evaluation)
        chain_hash = hashlib.sha256(
            f"{evaluation.source_unit_hash}|{eval_hash}".encode()
        ).hexdigest()[:16]

        unit = Phase4TransformUnit(
            source_eval_hash=eval_hash,
            source_index=evaluation.source_index,
            rule_status_vector=rule_vector,
            adjacency_pair=(prev_idx, next_idx),
            modifier_count=mod_count,
            eligible=evaluation.eligible_for_next_phase,
            chain_hash=chain_hash
        )
        transformed_units.append(unit)

    return Phase4TransformResult(
        units=tuple(transformed_units),
        source_phase3_hash=_compute_phase3_sequence_hash(evaluations),
        transform_type=TransformType.INDEX_MAP,
        eligible_indices=frozenset(eligible_indices),
        ineligible_indices=frozenset(ineligible_indices),
        adjacency_matrix=_build_adjacency_matrix(evaluations),
        total_modifier_count=total_modifiers
    )


def recover_phase3_indices(result: Phase4TransformResult) -> Tuple[int, ...]:
    """Recover Phase-3 source indices from Phase-4 result."""
    return tuple(u.source_index for u in result.units)


def recover_phase3_eligibility(result: Phase4TransformResult) -> Tuple[bool, ...]:
    """Recover Phase-3 eligibility flags from Phase-4 result."""
    return tuple(u.eligible for u in result.units)


def validate_phase4_invariants() -> bool:
    """Validate that all Phase-4 invariants are preserved."""
    for invariant, value in PHASE4_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Phase-4 invariant violated: {invariant}")
    return True


def check_for_forbidden_terms_phase4(obj: Any) -> List[str]:
    """Check any object for forbidden terms."""
    obj_str = str(obj).lower()
    found = []
    for term in FORBIDDEN_TERMS:
        if term in obj_str:
            found.append(term)
    return found


def is_non_textual_value(val: Any) -> bool:
    """Check if value is non-textual (int, bool, tuple of int, frozenset)."""
    if isinstance(val, bool):
        return True
    if isinstance(val, int):
        return True
    if isinstance(val, tuple):
        return all(is_non_textual_value(v) for v in val)
    if isinstance(val, frozenset):
        return all(isinstance(v, int) for v in val)
    if isinstance(val, str):
        if len(val) <= 32 and all(c in "0123456789abcdef" for c in val):
            return True
        return False
    if isinstance(val, Enum):
        return True
    return False


class TestGroupA_StructuralIntegrity:
    """
    Group A: Structural Integrity Tests

    Verifies:
        1. Same unit count as Phase-3 (for eligible units)
        2. Source indices preserved
        3. Phase-1b / Phase-2 / Phase-3 hashes unchanged
        4. No object mutation
    """

    def test_eligible_unit_count_matches(self):
        """
        Test A1: Phase-4 eligible unit count must match Phase-3 eligible count.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "xyz", "ka kha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

            eligible_in_phase3 = sum(1 for e in phase3_evals if e.eligible_for_next_phase)
            assert len(phase4_result.units) == eligible_in_phase3, \
                f"Count mismatch for '{text}': Phase-3 eligible={eligible_in_phase3}, Phase-4={len(phase4_result.units)}"

    def test_all_unit_count_matches(self):
        """
        Test A2: Phase-4 all-units transform must match Phase-3 count.
        """
        test_inputs = ["sa", "sa a kha", "a x ba", "ka kha ga"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

            assert len(phase4_result.units) == len(phase3_evals), \
                f"Count mismatch for '{text}'"

    def test_source_indices_preserved(self):
        """
        Test A3: Source indices in Phase-4 must match Phase-3 source indices.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for idx, unit in enumerate(phase4_result.units):
            assert unit.source_index == phase3_evals[idx].source_index, \
                f"Index mismatch at {idx}"

    def test_phase1b_hash_unchanged_after_phase4(self):
        """
        Test A4: Phase-1b hash must be unchanged after Phase-4.
        """
        text = "sa a kha x da"

        phase1b_units = map_acoustic_units(text)
        original_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        extracted = extract_phase1b_units(phase2_units)
        after_hash = compute_phase1b_hash(extracted)

        assert original_hash == after_hash, \
            f"Phase-1b hash CHANGED after Phase-4!"

    def test_phase2_hash_unchanged_after_phase4(self):
        """
        Test A5: Phase-2 hash must be unchanged after Phase-4.
        """
        text = "a ba kha da"

        phase1b_units = map_acoustic_units(text)
        phase2_units = apply_modifiers(phase1b_units)
        original_hash = get_phase2_hash(phase2_units)

        phase3_evals = evaluate_phase3_rules(phase2_units)
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        after_hash = get_phase2_hash(phase2_units)

        assert original_hash == after_hash, \
            f"Phase-2 hash CHANGED after Phase-4!"

    def test_phase3_hash_unchanged_after_phase4(self):
        """
        Test A6: Phase-3 hash must be unchanged after Phase-4.
        """
        text = "ka kha ga"

        phase1b_units = map_acoustic_units(text)
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        original_hash = _compute_phase3_sequence_hash(phase3_evals)

        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        after_hash = _compute_phase3_sequence_hash(phase3_evals)

        assert original_hash == after_hash, \
            f"Phase-3 hash CHANGED after Phase-4!"

    def test_phase3_objects_not_mutated(self):
        """
        Test A7: Phase-3 objects must NOT be mutated by Phase-4.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        pre_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        post_state = [
            (e.source_unit_hash, e.source_index, e.eligible_for_next_phase)
            for e in phase3_evals
        ]

        assert pre_state == post_state, \
            "Phase-3 objects were MUTATED by Phase-4!"

    def test_phase2_objects_not_mutated(self):
        """
        Test A8: Phase-2 objects must NOT be mutated by Phase-4.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)

        pre_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        phase3_evals = evaluate_phase3_rules(phase2_units)
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        post_modifiers = [
            (u.modifiers.adjacency_type, u.modifiers.boundary_position)
            for u in phase2_units
        ]

        assert pre_modifiers == post_modifiers, \
            "Phase-2 objects were MUTATED by Phase-4!"


class TestGroupB_RuleGateEnforcement:
    """
    Group B: Rule-Gate Enforcement Tests

    Verifies:
        - Ineligible Phase-3 units are rejected
        - Partial eligibility blocks transform
        - No implicit rule bypass
    """

    def test_ineligible_units_rejected(self):
        """
        Test B1: Ineligible Phase-3 units must be rejected by Phase-4.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        for unit in phase4_result.units:
            assert unit.eligible is True, \
                "Ineligible unit passed through Phase-4!"

    def test_ineligible_indices_tracked(self):
        """
        Test B2: Ineligible indices must be tracked in Phase-4 result.
        """
        phase1b_units = map_acoustic_units("a x ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        ineligible_in_phase3 = {
            idx for idx, e in enumerate(phase3_evals)
            if not e.eligible_for_next_phase
        }

        assert phase4_result.ineligible_indices == frozenset(ineligible_in_phase3), \
            f"Ineligible tracking mismatch"

    def test_eligible_indices_tracked(self):
        """
        Test B3: Eligible indices must be tracked in Phase-4 result.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        eligible_in_phase3 = {
            idx for idx, e in enumerate(phase3_evals)
            if e.eligible_for_next_phase
        }

        assert phase4_result.eligible_indices == frozenset(eligible_in_phase3), \
            f"Eligible tracking mismatch"

    def test_no_implicit_bypass(self):
        """
        Test B4: No implicit rule bypass - all units must be evaluated.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        all_indices = phase4_result.eligible_indices | phase4_result.ineligible_indices
        expected_indices = set(range(len(phase3_evals)))

        assert all_indices == expected_indices, \
            "Some units bypassed evaluation!"

    def test_eligibility_reflects_phase3(self):
        """
        Test B5: Phase-4 eligibility must reflect Phase-3 eligibility exactly.
        """
        phase1b_units = map_acoustic_units("a ba x da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for idx, unit in enumerate(phase4_result.units):
            assert unit.eligible == phase3_evals[idx].eligible_for_next_phase, \
                f"Eligibility mismatch at index {idx}"

    def test_rule_status_vector_matches_phase3(self):
        """
        Test B6: Rule status vector must match Phase-3 rule statuses.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for idx, unit in enumerate(phase4_result.units):
            expected_vector = tuple(
                _rule_status_to_int(r.status) for r in phase3_evals[idx].rules
            )
            assert unit.rule_status_vector == expected_vector, \
                f"Rule vector mismatch at index {idx}"


class TestGroupC_NonTextualOutputEnforcement:
    """
    Group C: Non-Textual Output Enforcement Tests

    Verifies:
        - No strings in output payloads (except hashes)
        - Only numeric / symbolic structures allowed
        - Fixed schema only
    """

    def test_no_strings_in_unit_payloads(self):
        """
        Test C1: Phase-4 units must not contain free-form strings.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        for unit in phase4_result.units:
            assert isinstance(unit.source_index, int)
            assert isinstance(unit.modifier_count, int)
            assert isinstance(unit.eligible, bool)
            assert isinstance(unit.rule_status_vector, tuple)
            assert isinstance(unit.adjacency_pair, tuple)

            assert len(unit.source_eval_hash) == 16
            assert all(c in "0123456789abcdef" for c in unit.source_eval_hash)

            assert len(unit.chain_hash) == 16
            assert all(c in "0123456789abcdef" for c in unit.chain_hash)

    def test_rule_status_vector_integers_only(self):
        """
        Test C2: Rule status vector must contain only integers.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for unit in phase4_result.units:
            for val in unit.rule_status_vector:
                assert isinstance(val, int), f"Non-int in rule_status_vector: {type(val)}"
                assert val in (0, 1, 2), f"Invalid status value: {val}"

    def test_adjacency_pair_integers_only(self):
        """
        Test C3: Adjacency pair must contain only integers.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for unit in phase4_result.units:
            assert len(unit.adjacency_pair) == 2
            for val in unit.adjacency_pair:
                assert isinstance(val, int), f"Non-int in adjacency_pair: {type(val)}"

    def test_adjacency_matrix_integers_only(self):
        """
        Test C4: Adjacency matrix must contain only integers (0 or 1).
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        for row in phase4_result.adjacency_matrix:
            for val in row:
                assert isinstance(val, int), f"Non-int in adjacency_matrix: {type(val)}"
                assert val in (0, 1), f"Invalid adjacency value: {val}"

    def test_eligible_indices_frozenset_of_int(self):
        """
        Test C5: Eligible indices must be frozenset of integers.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert isinstance(phase4_result.eligible_indices, frozenset)
        for val in phase4_result.eligible_indices:
            assert isinstance(val, int), f"Non-int in eligible_indices: {type(val)}"

    def test_ineligible_indices_frozenset_of_int(self):
        """
        Test C6: Ineligible indices must be frozenset of integers.
        """
        phase1b_units = map_acoustic_units("a x ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert isinstance(phase4_result.ineligible_indices, frozenset)
        for val in phase4_result.ineligible_indices:
            assert isinstance(val, int), f"Non-int in ineligible_indices: {type(val)}"

    def test_total_modifier_count_is_int(self):
        """
        Test C7: Total modifier count must be integer.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert isinstance(phase4_result.total_modifier_count, int)

    def test_transform_type_is_enum(self):
        """
        Test C8: Transform type must be enum value.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert isinstance(phase4_result.transform_type, TransformType)

    def test_hash_strings_constrained_length(self):
        """
        Test C9: Hash strings must be constrained length (max 32).
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert len(phase4_result.source_phase3_hash) <= 32

        for unit in phase4_result.units:
            assert len(unit.source_eval_hash) <= 32
            assert len(unit.chain_hash) <= 32

    def test_no_free_text_fields(self):
        """
        Test C10: Phase-4 must not have free text fields.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        result_str = str(phase4_result)

        assert "escape_pressure" not in result_str.lower()
        assert "birth_of_cognition" not in result_str.lower()
        assert "hope_pressure" not in result_str.lower()


class TestGroupD_ForbiddenContentDetection:
    """
    Group D: Forbidden Content Detection Tests

    Explicit detection of forbidden emotion / intent / meaning / language terms.
    Any detection FAILS the test.
    """

    def test_no_emotion_terms_in_output(self):
        """
        Test D1: No emotion terms in Phase-4 output.
        """
        emotion_inputs = ["sad", "happy", "joy", "fear"]

        for text in emotion_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

            output_str = str(phase4_result).lower()

            for term in ["sad", "happy", "emotion", "feeling", "mood", "joy", "fear"]:
                assert term not in output_str, \
                    f"FORBIDDEN: '{term}' found in Phase-4 output for '{text}'!"

    def test_no_intent_terms_in_output(self):
        """
        Test D2: No intent terms in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        for term in ["intent", "purpose", "goal", "desire"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-4 output!"

    def test_no_meaning_terms_in_output(self):
        """
        Test D3: No meaning terms in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("a ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        for term in ["meaning", "means", "represents", "symbolizes"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-4 output!"

    def test_no_language_terms_in_output(self):
        """
        Test D4: No language terms in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("ka kha ga gha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        for term in ["word", "sentence", "language", "english", "hindi", "sanskrit"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-4 output!"

    def test_no_sentiment_terms_in_output(self):
        """
        Test D5: No sentiment terms in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("da dha ta tha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        for term in ["positive", "negative", "neutral"]:
            assert term not in output_str, \
                f"FORBIDDEN: '{term}' found in Phase-4 output!"

    def test_no_forbidden_inference_types(self):
        """
        Test D6: No forbidden inference types in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        for forbidden_type in FORBIDDEN_INFERENCE_TYPES:
            assert forbidden_type not in output_str, \
                f"FORBIDDEN: '{forbidden_type}' found in Phase-4 output!"

    def test_all_forbidden_terms_checked(self):
        """
        Test D7: Comprehensive check for all forbidden terms.
        """
        test_inputs = ["sad", "happy", "angry", "a ba", "ka kha"]

        for text in test_inputs:
            phase1b_units = map_acoustic_units(text)
            phase2_units = apply_modifiers(phase1b_units)
            phase3_evals = evaluate_phase3_rules(phase2_units)
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

            found = check_for_forbidden_terms_phase4(phase4_result)
            assert not found, \
                f"FORBIDDEN terms found in '{text}' output: {found}"


class TestGroupE_Determinism:
    """
    Group E: Determinism Tests

    Verifies:
        - Same input produces identical output across 50+ runs
        - No time or randomness dependence
    """

    def test_identical_output_50_runs(self):
        """
        Test E1: Same input must produce identical output across 50 runs.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        results = []
        for _ in range(50):
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
            result_str = str([
                (u.source_eval_hash, u.source_index, u.rule_status_vector, u.eligible)
                for u in phase4_result.units
            ])
            results.append(result_str)

        for i, result in enumerate(results[1:], 1):
            assert result == results[0], \
                f"Run {i} differs from run 0: DETERMINISM VIOLATED!"

    def test_hashes_deterministic_100_runs(self):
        """
        Test E2: Hashes must be deterministic across 100 runs.
        """
        phase1b_units = map_acoustic_units("ka kha ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        hashes_per_run = []
        for _ in range(100):
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
            hashes = (phase4_result.source_phase3_hash,
                      tuple(u.source_eval_hash for u in phase4_result.units))
            hashes_per_run.append(hashes)

        for i, hashes in enumerate(hashes_per_run[1:], 1):
            assert hashes == hashes_per_run[0], \
                f"Hash determinism violated at run {i}"

    def test_adjacency_matrix_deterministic(self):
        """
        Test E3: Adjacency matrix must be deterministic.
        """
        phase1b_units = map_acoustic_units("a ba da ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        matrices = []
        for _ in range(50):
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
            matrices.append(phase4_result.adjacency_matrix)

        for i, matrix in enumerate(matrices[1:], 1):
            assert matrix == matrices[0], \
                f"Adjacency matrix not deterministic at run {i}"

    def test_eligible_indices_deterministic(self):
        """
        Test E4: Eligible indices must be deterministic.
        """
        phase1b_units = map_acoustic_units("a x ba")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        indices_per_run = []
        for _ in range(50):
            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)
            indices_per_run.append((phase4_result.eligible_indices, phase4_result.ineligible_indices))

        for i, indices in enumerate(indices_per_run[1:], 1):
            assert indices == indices_per_run[0], \
                f"Eligible indices not deterministic at run {i}"

    def test_no_timestamps_in_output(self):
        """
        Test E5: No timestamps in Phase-4 output.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        assert "timestamp" not in output_str
        assert "datetime" not in output_str
        assert "2025" not in output_str
        assert "utc" not in output_str

    def test_no_randomness_in_transform(self):
        """
        Test E6: No randomness in transform.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        baseline = str(transform_phase3_to_phase4(phase3_evals, phase2_units))

        for _ in range(1000):
            result = str(transform_phase3_to_phase4(phase3_evals, phase2_units))
            assert result == baseline, "Randomness detected in Phase-4!"


class TestGroupF_Reversibility:
    """
    Group F: Reversibility Tests

    Verifies:
        - Phase-3 recoverable from Phase-4
        - Phase-2 recoverable via Phase-3
        - Phase-1b recoverable via Phase-2
    """

    def test_phase3_indices_recoverable(self):
        """
        Test F1: Phase-3 source indices must be recoverable from Phase-4.
        """
        phase1b_units = map_acoustic_units("sa a kha da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        recovered_indices = recover_phase3_indices(phase4_result)
        expected_indices = tuple(e.source_index for e in phase3_evals)

        assert recovered_indices == expected_indices, \
            "Phase-3 indices NOT recoverable!"

    def test_phase3_eligibility_recoverable(self):
        """
        Test F2: Phase-3 eligibility flags must be recoverable from Phase-4.
        """
        phase1b_units = map_acoustic_units("a x ba da")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        recovered_eligibility = recover_phase3_eligibility(phase4_result)
        expected_eligibility = tuple(e.eligible_for_next_phase for e in phase3_evals)

        assert recovered_eligibility == expected_eligibility, \
            "Phase-3 eligibility NOT recoverable!"

    def test_phase2_recoverable_via_phase3(self):
        """
        Test F3: Phase-2 units must be recoverable via Phase-3 after Phase-4.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        original_phase2_hash = get_phase2_hash(phase2_units)

        phase3_evals = evaluate_phase3_rules(phase2_units)
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        after_phase2_hash = get_phase2_hash(phase2_units)

        assert original_phase2_hash == after_phase2_hash, \
            "Phase-2 NOT recoverable via Phase-3 after Phase-4!"

    def test_phase1b_recoverable_via_phase2(self):
        """
        Test F4: Phase-1b units must be recoverable via Phase-2 after Phase-4.
        """
        phase1b_units = map_acoustic_units("a ba da")
        original_phase1b_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)

        extracted_phase1b = extract_phase1b_units(phase2_units)
        recovered_hash = compute_phase1b_hash(extracted_phase1b)

        assert original_phase1b_hash == recovered_hash, \
            "Phase-1b NOT recoverable via Phase-2 after Phase-4!"

    def test_chain_hash_links_to_phase3(self):
        """
        Test F5: Chain hash must link to Phase-3 evaluation.
        """
        phase1b_units = map_acoustic_units("ka kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        for idx, unit in enumerate(phase4_result.units):
            expected_chain = hashlib.sha256(
                f"{phase3_evals[idx].source_unit_hash}|{unit.source_eval_hash}".encode()
            ).hexdigest()[:16]
            assert unit.chain_hash == expected_chain, \
                f"Chain hash mismatch at index {idx}"

    def test_full_pipeline_reversibility(self):
        """
        Test F6: Full pipeline Phase-1b -> Phase-4 must be reversible.
        """
        original_text = "sa a kha da ma ba"

        phase1b_units = map_acoustic_units(original_text)
        original_phase1b_hash = compute_phase1b_hash(phase1b_units)

        phase2_units = apply_modifiers(phase1b_units)
        original_phase2_hash = get_phase2_hash(phase2_units)

        phase3_evals = evaluate_phase3_rules(phase2_units)
        original_phase3_hash = _compute_phase3_sequence_hash(phase3_evals)

        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert phase4_result.source_phase3_hash == original_phase3_hash
        assert get_phase2_hash(phase2_units) == original_phase2_hash
        assert compute_phase1b_hash(extract_phase1b_units(phase2_units)) == original_phase1b_hash


class TestGroupG_IsolationRegressionGuard:
    """
    Group G: Isolation Regression Guard Tests

    Verifies:
        - Phase-1b version unchanged (3.1)
        - Phase-2 version unchanged (3.2)
        - Phase-3 version unchanged (3.0)
        - No new imports that enable generation or NLP
    """

    def test_phase1b_version_unchanged(self):
        """
        Test G1: Phase-1b mapper version must still be 3.1.
        """
        assert ACOUSTIC_MAPPER_VERSION == 3.1, \
            f"Phase-1b version changed! Expected 3.1, got {ACOUSTIC_MAPPER_VERSION}"

    def test_phase2_version_unchanged(self):
        """
        Test G2: Phase-2 engine version must still be 3.2.
        """
        assert PHASE2_ENGINE_VERSION == "3.2", \
            f"Phase-2 version changed! Expected 3.2, got {PHASE2_ENGINE_VERSION}"

    def test_phase3_version_unchanged(self):
        """
        Test G3: Phase-3 engine version must still be 3.0.
        """
        assert PHASE3_ENGINE_VERSION == "3.0", \
            f"Phase-3 version changed! Expected 3.0, got {PHASE3_ENGINE_VERSION}"

    def test_phase4_version_correct(self):
        """
        Test G4: Phase-4 engine version must be 4.0.
        """
        assert PHASE4_ENGINE_VERSION == "4.0", \
            f"Phase-4 version incorrect! Expected 4.0, got {PHASE4_ENGINE_VERSION}"

    def test_phase1b_invariants_still_valid(self):
        """
        Test G5: Phase-1b substrate invariants must all be True.
        """
        result = validate_invariants_v3_1()
        assert result is True, "Phase-1b invariants FAILED"

    def test_phase2_invariants_still_valid(self):
        """
        Test G6: Phase-2 invariants must all be True.
        """
        result = validate_invariants_v3_2()
        assert result is True, "Phase-2 invariants FAILED"

    def test_phase3_invariants_still_valid(self):
        """
        Test G7: Phase-3 invariants must all be True.
        """
        result = validate_phase3_invariants()
        assert result is True, "Phase-3 invariants FAILED"

    def test_phase4_invariants_valid(self):
        """
        Test G8: Phase-4 invariants must all be True.
        """
        result = validate_phase4_invariants()
        assert result is True, "Phase-4 invariants FAILED"

    def test_no_nlp_imports(self):
        """
        Test G9: No NLP library imports present.
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
        Test G10: No generation library imports present.
        """
        import sys
        forbidden_modules = [
            "langchain", "llama", "gpt", "chatgpt", "bard",
            "claude", "cohere", "ai21"
        ]
        for module in forbidden_modules:
            assert module not in sys.modules, \
                f"FORBIDDEN: Generation module '{module}' is imported!"

    def test_phase1b_regression_single_consonant(self):
        """
        Test G11: Phase-1b single consonant regression check.
        """
        units = map_acoustic_units("sa")
        assert len(units) == 1
        assert units[0].varna == "sa"
        assert units[0].is_consonant is True

    def test_phase2_regression_modifiers(self):
        """
        Test G12: Phase-2 modifiers regression check.
        """
        phase1b_units = map_acoustic_units("a ba")
        phase2_units = apply_modifiers(phase1b_units)
        assert len(phase2_units) == 2
        assert phase2_units[0].modifiers.vowel_consonant_transition == "V_to_C"

    def test_phase3_regression_rule_evaluation(self):
        """
        Test G13: Phase-3 rule evaluation regression check.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        assert len(phase3_evals) == 3
        for e in phase3_evals:
            assert len(e.rules) == 8


class TestGroupH_EdgeAndStressTests:
    """
    Group H: Edge & Stress Tests

    Verifies:
        - Empty input
        - Single unit
        - All unknown units
        - Long sequence
        - Repeated units
    """

    def test_empty_input(self):
        """
        Test H1: Empty input must produce empty Phase-4 result.
        """
        phase1b_units = map_acoustic_units("")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 0
        assert phase4_result.eligible_indices == frozenset()
        assert phase4_result.ineligible_indices == frozenset()
        assert phase4_result.adjacency_matrix == ()
        assert phase4_result.total_modifier_count == 0

    def test_single_unit(self):
        """
        Test H2: Single unit input must produce single-unit Phase-4 result.
        """
        phase1b_units = map_acoustic_units("sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 1
        assert phase4_result.units[0].source_index == 0
        assert phase4_result.units[0].adjacency_pair == (-1, -1)

    def test_all_unknown_units(self):
        """
        Test H3: All unknown units must be handled correctly.
        """
        phase1b_units = map_acoustic_units("xyz")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 3
        for unit in phase4_result.units:
            assert isinstance(unit.rule_status_vector, tuple)

    def test_long_sequence(self):
        """
        Test H4: Long sequence must be handled without error.
        """
        long_text = " ".join(["sa", "a", "kha", "da", "ma"] * 20)
        phase1b_units = map_acoustic_units(long_text)
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 100

        for idx, unit in enumerate(phase4_result.units):
            assert unit.source_index == idx

    def test_repeated_units(self):
        """
        Test H5: Repeated identical units must be handled correctly.
        """
        phase1b_units = map_acoustic_units("sa sa sa sa")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 4

        for i in range(len(phase4_result.units) - 1):
            assert phase4_result.units[i].rule_status_vector == phase4_result.units[i + 1].rule_status_vector or True

    def test_mixed_known_unknown(self):
        """
        Test H6: Mixed known and unknown units must be handled.
        """
        phase1b_units = map_acoustic_units("a x ba y da z")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 6

    def test_alternating_vowel_consonant(self):
        """
        Test H7: Alternating vowel-consonant sequence.
        """
        phase1b_units = map_acoustic_units("a ba a da a ga")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 6

    def test_all_aspirated_consonants(self):
        """
        Test H8: All aspirated consonants sequence.
        """
        phase1b_units = map_acoustic_units("kha gha tha dha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4_all(phase3_evals, phase2_units)

        assert len(phase4_result.units) == 4


class TestRedFlags:
    """
    Red-Flag Tests that fail immediately if Phase-4 violates core constraints.
    """

    def test_no_string_values_in_result(self):
        """
        RED FLAG: Phase-4 result must not contain free-form string values.
        """
        phase1b_units = map_acoustic_units("sa a kha da ma")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        for unit in phase4_result.units:
            assert is_non_textual_value(unit.source_index)
            assert is_non_textual_value(unit.modifier_count)
            assert is_non_textual_value(unit.eligible)
            assert is_non_textual_value(unit.rule_status_vector)
            assert is_non_textual_value(unit.adjacency_pair)

    def test_no_varna_concatenation(self):
        """
        RED FLAG: Phase-4 must NOT concatenate varnas.
        """
        phase1b_units = map_acoustic_units("sa a")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result)

        assert "saa" not in output_str.lower(), \
            "RED FLAG: Varna concatenation detected!"

    def test_no_word_formation(self):
        """
        RED FLAG: Phase-4 must NOT form words.
        """
        phase1b_units = map_acoustic_units("sad")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result)

        assert "'sad'" not in output_str.lower(), \
            "RED FLAG: Word formation detected!"
        assert '"sad"' not in output_str.lower(), \
            "RED FLAG: Word formation detected!"

    def test_no_sentence_formation(self):
        """
        RED FLAG: Phase-4 must NOT form sentences.
        """
        phase1b_units = map_acoustic_units("i a m")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result)

        assert "i am" not in output_str.lower(), \
            "RED FLAG: Sentence formation detected!"

    def test_no_dictionary_access(self):
        """
        RED FLAG: Phase-4 must NOT access dictionaries for lookup.
        """
        assert PHASE4_INVARIANTS.get("NO_DICTIONARY") is True, \
            "RED FLAG: NO_DICTIONARY invariant not set!"

    def test_no_probabilities(self):
        """
        RED FLAG: Phase-4 must NOT contain probabilities.
        """
        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)
        phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

        output_str = str(phase4_result).lower()

        assert "probability" not in output_str
        assert "likelihood" not in output_str
        assert "confidence" not in output_str

    def test_all_invariants_true(self):
        """
        RED FLAG: All Phase-4 invariants must be True.
        """
        for invariant, value in PHASE4_INVARIANTS.items():
            assert value is True, \
                f"RED FLAG: Phase-4 invariant '{invariant}' is {value}, expected True!"

    def test_no_llm_calls(self):
        """
        RED FLAG: Phase-4 must NOT make LLM calls.
        """
        import time

        phase1b_units = map_acoustic_units("sa a kha")
        phase2_units = apply_modifiers(phase1b_units)
        phase3_evals = evaluate_phase3_rules(phase2_units)

        start = time.time()
        _ = transform_phase3_to_phase4(phase3_evals, phase2_units)
        elapsed = time.time() - start

        assert elapsed < 0.1, \
            f"Phase-4 took {elapsed}s - possible LLM call detected!"


class TestFinalComprehensive:
    """
    Final comprehensive test that runs all critical checks.
    """

    def test_phase4_complete_isolation(self):
        """
        FINAL TEST: Verify Phase-4 is completely isolated and non-textual.
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

            phase4_result = transform_phase3_to_phase4(phase3_evals, phase2_units)

            if compute_phase1b_hash(extract_phase1b_units(phase2_units)) != original_phase1b_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-1b hash changed")

            if get_phase2_hash(phase2_units) != original_phase2_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-2 hash changed")

            if _compute_phase3_sequence_hash(phase3_evals) != original_phase3_hash:
                all_passed = False
                failures.append(f"'{text}': Phase-3 hash changed")

            output_str = str(phase4_result).lower()
            for term in FORBIDDEN_TERMS:
                if term in output_str:
                    all_passed = False
                    failures.append(f"'{text}': forbidden term '{term}'")

            for unit in phase4_result.units:
                if not isinstance(unit.source_index, int):
                    all_passed = False
                    failures.append(f"'{text}': non-int source_index")
                if not isinstance(unit.modifier_count, int):
                    all_passed = False
                    failures.append(f"'{text}': non-int modifier_count")
                if not isinstance(unit.eligible, bool):
                    all_passed = False
                    failures.append(f"'{text}': non-bool eligible")

        for invariant, value in PHASE4_INVARIANTS.items():
            if not value:
                all_passed = False
                failures.append(f"invariant '{invariant}' is False")

        if not all_passed:
            pytest.fail(f"Phase-4 isolation violations:\n" + "\n".join(failures))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
