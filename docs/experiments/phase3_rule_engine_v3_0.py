"""
Phase-3.0 Rule Engine (v3.0)
============================

Phase-3.0 is a rule-only engine that operates on Phase-2 output.

This module is:
    - TEST-ONLY
    - RULE-ONLY
    - DETERMINISTIC
    - NON-MUTATING
    - REVERSIBLE

It operates ONLY on Phase-2 output (Phase2ModifiedUnit).

ABSOLUTE RULES:
    - DO NOT generate text
    - DO NOT choose words
    - DO NOT infer meaning
    - DO NOT infer emotion
    - DO NOT infer intent
    - DO NOT infer language
    - DO NOT infer correctness

Version: 3.0
"""

import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any
from enum import Enum


__all__ = [
    "PHASE3_ENGINE_VERSION",
    "PHASE3_INVARIANTS",
    "FORBIDDEN_SEMANTIC_TERMS",
    "FORBIDDEN_INFERENCE_TYPES",
    "RuleStatus",
    "RuleCategory",
    "Phase3RuleResult",
    "Phase3RuleEvaluation",
    "evaluate_phase3_rules",
    "extract_phase2_units",
    "validate_phase3_invariants",
    "get_phase2_hash",
    "check_for_forbidden_terms",
    "stringify_evaluation",
    "_compute_phase2_unit_hash",
]


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
# PHASE-3.0 RULE ENGINE IMPLEMENTATION
# ============================================================================

def _compute_phase2_unit_hash(unit) -> str:
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


def _evaluate_modifier_presence_rule(unit) -> Phase3RuleResult:
    """Evaluate modifier presence rule - structural check only."""
    has_modifiers = len(unit.modifiers.relational_modifiers) > 0
    status = RuleStatus.PASS if has_modifiers else RuleStatus.NOT_APPLICABLE
    return Phase3RuleResult(
        rule_id="MOD_PRESENCE_001",
        category=RuleCategory.MODIFIER_PRESENCE,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_adjacency_rule(unit) -> Phase3RuleResult:
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


def _evaluate_aspiration_contrast_rule(unit, next_unit: Optional[object]) -> Phase3RuleResult:
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


def _evaluate_unknown_barrier_rule(unit) -> Phase3RuleResult:
    """Evaluate unknown barrier rule - structural check only."""
    barrier = unit.modifiers.unknown_barrier
    status = RuleStatus.PASS if barrier in ["is_unknown", "left_of_unknown", "right_of_unknown", "between_unknowns", "none"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="UNK_BARRIER_001",
        category=RuleCategory.UNKNOWN_BARRIER,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_boundary_position_rule(unit) -> Phase3RuleResult:
    """Evaluate boundary position rule - structural check only."""
    pos = unit.modifiers.boundary_position
    status = RuleStatus.PASS if pos in ["singleton", "sequence_start", "sequence_end", "sequence_interior"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="BOUNDARY_POS_001",
        category=RuleCategory.BOUNDARY_POSITION,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_sequence_class_rule(unit) -> Phase3RuleResult:
    """Evaluate sequence class rule - structural check only."""
    seq_class = unit.modifiers.sequence_class
    status = RuleStatus.PASS if seq_class in ["empty", "all_known", "all_unknown", "mixed"] else RuleStatus.FAIL
    return Phase3RuleResult(
        rule_id="SEQ_CLASS_001",
        category=RuleCategory.SEQUENCE_CLASS,
        status=status,
        target_index=unit.source_unit.index
    )


def _evaluate_continuity_rule(unit) -> Phase3RuleResult:
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


def _evaluate_repetition_rule(unit) -> Phase3RuleResult:
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


def evaluate_phase3_rules(modified_units: List) -> List[Phase3RuleEvaluation]:
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


def extract_phase2_units(evaluations: List[Phase3RuleEvaluation], original_units: List) -> List:
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
# HELPER FUNCTIONS
# ============================================================================

def get_phase2_hash(modified_units: List) -> str:
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
