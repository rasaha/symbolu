"""
Phase-4.0 Transform Engine (v4.0) - Phase-4B
=============================================

Phase-4.0 is **Phase-4B** within the composite Phase-4 of the Phase-1b → Phase-14
experimental pipeline.

Phase-4 Composite Structure:
    - Phase-4A: Ontology Lookup (frozen varna × layer interaction resolution)
    - Phase-4B: Transform Engine (this module)
    - Phase-4C: PO4 Planner Governance

This module implements non-textual transformation of Phase-3 output.

This module is:
    - TEST-ONLY
    - NON-TEXTUAL
    - DETERMINISTIC
    - NON-MUTATING
    - REVERSIBLE

It operates ONLY on Phase-3 output (Phase3RuleEvaluation).

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

CRITICAL ONTOLOGY CONSTRAINT (Phase-4 Composite Rule):
    - DO NOT load frozen ontology files directly
    - DO NOT infer polarity or manifestation values
    - DO NOT gap-fill missing ontology data
    - DO NOT interpret or smooth ontology language
    - If ontology data is needed, call Phase-4A's lookup functions

Version: 4.0
"""

import hashlib
from dataclasses import dataclass
from typing import List, Tuple, FrozenSet, Any
from enum import Enum

from .phase3_rule_engine_v3_0 import (
    Phase3RuleEvaluation,
    RuleStatus,
)


__all__ = [
    "PHASE4_ENGINE_VERSION",
    "PHASE4_INVARIANTS",
    "FORBIDDEN_TERMS",
    "FORBIDDEN_INFERENCE_TYPES",
    "TransformType",
    "Phase4TransformUnit",
    "Phase4TransformResult",
    "transform_phase3_to_phase4",
    "transform_phase3_to_phase4_all",
    "recover_phase3_indices",
    "recover_phase3_eligibility",
    "validate_phase4_invariants",
    "check_for_forbidden_terms_phase4",
    "is_non_textual_value",
    "compute_phase3_sequence_hash",
    "_compute_phase3_eval_hash",
    "_compute_phase3_sequence_hash",
    "_rule_status_to_int",
]


# ============================================================================
# PHASE-4.0 VERSION AND INVARIANTS
# ============================================================================

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
    # Phase-4 Composite Rule: NO ontology inference in Phase-4B
    "NO_ONTOLOGY_INFERENCE": True,
    "NO_DIRECT_ONTOLOGY_FILE_ACCESS": True,
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
    # Phase-4 Composite Rule: NO ontology inference in Phase-4B
    "ontology_inference",
    "manifestation_inference",
    "varna_layer_inference",
    "distortion_vector_inference",
])


# ============================================================================
# PHASE-4.0 TYPE DEFINITIONS
# ============================================================================

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


# ============================================================================
# PHASE-4.0 TRANSFORM ENGINE IMPLEMENTATION
# ============================================================================

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


# Alias for backward compatibility
compute_phase3_sequence_hash = _compute_phase3_sequence_hash


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
    phase2_units: List
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
    phase2_units: List
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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
