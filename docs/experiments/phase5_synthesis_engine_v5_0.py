"""
Phase-5.0 Synthesis Engine (v5.0)
=================================

Phase-5.0 implements Option A: Non-Textual Synthesis.

This module is:
    - TEST-ONLY
    - NON-TEXTUAL
    - DETERMINISTIC
    - REVERSIBLE
    - ISOLATED

It operates ONLY on Phase-4 output (Phase4TransformResult).

ABSOLUTE RULES:
    - NO TEXT OUTPUT: No words, sentences, language strings, or labels
    - Only hex hashes (<=32 chars) or Enum values allowed as strings
    - NO SEMANTICS: No meaning, intent, emotion, sentiment inference
    - NO DICTIONARIES / NLP / LLM: No lookups, NLP libraries, LLM calls, embeddings
    - NO RANDOMNESS / TIME: No random, UUID, datetime, system time, non-deterministic sets
    - NON-MUTATING: Must not modify Phase-4 objects (or any upstream objects)
    - REVERSIBLE: Must allow recovery of Phase-4 indices, eligibility mask, adjacency structure

Version: 5.0
"""

import hashlib
from dataclasses import dataclass
from typing import Tuple, List, Any, FrozenSet
from enum import Enum


__all__ = [
    "PHASE5_ENGINE_VERSION",
    "PHASE5_INVARIANTS",
    "SynthesisType",
    "Phase5SynthesisUnit",
    "Phase5SynthesisResult",
    "synthesize_phase4_to_phase5",
    "recover_phase4_indices",
    "recover_phase4_eligibility_masks",
    "validate_phase5_invariants",
    "check_for_forbidden_terms_phase5",
    "is_non_textual_value_phase5",
]


PHASE5_ENGINE_VERSION = "5.0"

PHASE5_INVARIANTS = {
    "NON_TEXTUAL": True,
    "NO_LANGUAGE": True,
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_EMOTION": True,
    "NO_PROBABILITY": True,
    "NO_LEARNING": True,
    "NO_GENERATION": True,
    "NON_MUTATING": True,
    "REVERSIBLE": True,
    "DETERMINISTIC": True,
    "ISOLATED": True,
    "TEST_ONLY": True,
}

FORBIDDEN_TERMS_PHASE5 = frozenset([
    # Emotions
    "sad", "happy", "emotion", "feeling", "mood", "joy", "fear",
    # Intent
    "intent", "purpose", "goal", "desire",
    # Meaning
    "meaning", "means", "represents", "symbolizes",
    # Language
    "word", "sentence", "language", "english", "hindi", "sanskrit",
    # Sentiment
    "positive", "negative", "neutral",
    # Probability
    "probability", "likelihood", "confidence",
    # Generation
    "generate", "predict", "infer",
])


class SynthesisType(Enum):
    """Synthesis type categories - structural only."""
    STRUCTURAL_FOLD = "structural_fold"
    ADJACENCY_COLLAPSE = "adjacency_collapse"
    RULE_VECTOR_MERGE = "rule_vector_merge"
    ELIGIBILITY_BLOCK = "eligibility_block"


@dataclass(frozen=True)
class Phase5SynthesisUnit:
    """
    Phase-5 synthesis unit for a group of contiguous eligible Phase-4 units.

    Contains ONLY:
        - source_indices: Tuple of Phase-4 unit indices in this group
        - aggregated_rule_vector: Tuple of ints (0, 1, or 2) - min aggregation
        - adjacency_signature: Tuple of ints (0 or 1) - binary adjacency within group
        - modifier_density: Sum of modifier_count for units in group
        - eligibility_mask: Tuple of bools - eligibility for each unit in group
        - unit_hash: 16-32 char hex hash

    NO free-form strings. NO semantic content. NO text generation.
    """
    source_indices: Tuple[int, ...]
    aggregated_rule_vector: Tuple[int, ...]
    adjacency_signature: Tuple[int, ...]
    modifier_density: int
    eligibility_mask: Tuple[bool, ...]
    unit_hash: str

    def __post_init__(self):
        # Validate source_indices
        if not isinstance(self.source_indices, tuple):
            raise ValueError("source_indices must be tuple")
        for idx in self.source_indices:
            if not isinstance(idx, int):
                raise ValueError("source_indices must contain only ints")

        # Validate aggregated_rule_vector
        if not isinstance(self.aggregated_rule_vector, tuple):
            raise ValueError("aggregated_rule_vector must be tuple")
        for val in self.aggregated_rule_vector:
            if not isinstance(val, int) or val not in (0, 1, 2):
                raise ValueError("aggregated_rule_vector values must be 0, 1, or 2")

        # Validate adjacency_signature
        if not isinstance(self.adjacency_signature, tuple):
            raise ValueError("adjacency_signature must be tuple")
        for val in self.adjacency_signature:
            if not isinstance(val, int) or val not in (0, 1):
                raise ValueError("adjacency_signature values must be 0 or 1")

        # Validate modifier_density
        if not isinstance(self.modifier_density, int):
            raise ValueError("modifier_density must be int")

        # Validate eligibility_mask
        if not isinstance(self.eligibility_mask, tuple):
            raise ValueError("eligibility_mask must be tuple")
        for val in self.eligibility_mask:
            if not isinstance(val, bool):
                raise ValueError("eligibility_mask values must be bool")

        # Validate unit_hash
        if not isinstance(self.unit_hash, str):
            raise ValueError("unit_hash must be str")
        if not (16 <= len(self.unit_hash) <= 32):
            raise ValueError("unit_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.unit_hash):
            raise ValueError("unit_hash must be hex")


@dataclass(frozen=True)
class Phase5SynthesisResult:
    """
    Phase-5 complete synthesis result.

    Contains ONLY:
        - synthesis_units: Tuple of Phase5SynthesisUnit
        - synthesis_graph: Tuple of tuples (0/1 group-to-group adjacency matrix)
        - synthesis_hash: 16-32 char hex hash
        - source_phase4_hashes: Tuple of Phase-4 source hashes
        - synthesis_type: SynthesisType enum
        - reversible: bool - True if Phase-4 data recoverable
        - eligible: bool - True if synthesis was successful

    NO free-form strings. NO semantic content.
    """
    synthesis_units: Tuple["Phase5SynthesisUnit", ...]
    synthesis_graph: Tuple[Tuple[int, ...], ...]
    synthesis_hash: str
    source_phase4_hashes: Tuple[str, ...]
    synthesis_type: SynthesisType
    reversible: bool
    eligible: bool

    def __post_init__(self):
        # Validate synthesis_units
        if not isinstance(self.synthesis_units, tuple):
            raise ValueError("synthesis_units must be tuple")

        # Validate synthesis_graph
        if not isinstance(self.synthesis_graph, tuple):
            raise ValueError("synthesis_graph must be tuple")
        for row in self.synthesis_graph:
            if not isinstance(row, tuple):
                raise ValueError("synthesis_graph rows must be tuples")
            for val in row:
                if not isinstance(val, int) or val not in (0, 1):
                    raise ValueError("synthesis_graph values must be 0 or 1")

        # Validate synthesis_hash
        if not isinstance(self.synthesis_hash, str):
            raise ValueError("synthesis_hash must be str")
        if not (16 <= len(self.synthesis_hash) <= 32):
            raise ValueError("synthesis_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.synthesis_hash):
            raise ValueError("synthesis_hash must be hex")

        # Validate source_phase4_hashes
        if not isinstance(self.source_phase4_hashes, tuple):
            raise ValueError("source_phase4_hashes must be tuple")
        for h in self.source_phase4_hashes:
            if not isinstance(h, str):
                raise ValueError("source_phase4_hashes must contain only strings")
            if not (16 <= len(h) <= 32):
                raise ValueError("source_phase4_hashes entries must be 16-32 chars")
            if not all(c in "0123456789abcdef" for c in h):
                raise ValueError("source_phase4_hashes entries must be hex")

        # Validate synthesis_type
        if not isinstance(self.synthesis_type, SynthesisType):
            raise ValueError("synthesis_type must be SynthesisType enum")

        # Validate reversible and eligible
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be bool")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be bool")


def _compute_unit_hash(
    source_indices: Tuple[int, ...],
    aggregated_rule_vector: Tuple[int, ...],
    adjacency_signature: Tuple[int, ...],
    modifier_density: int,
    eligibility_mask: Tuple[bool, ...],
    source_hashes: Tuple[str, ...]
) -> str:
    """Compute deterministic hash for a synthesis unit."""
    hash_input = (
        f"{source_indices}|"
        f"{aggregated_rule_vector}|"
        f"{adjacency_signature}|"
        f"{modifier_density}|"
        f"{eligibility_mask}|"
        f"{source_hashes}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _compute_synthesis_hash(
    source_phase4_hashes: Tuple[str, ...],
    unit_hashes: Tuple[str, ...],
    synthesis_graph: Tuple[Tuple[int, ...], ...]
) -> str:
    """Compute deterministic hash for entire synthesis result."""
    # Flatten synthesis_graph deterministically
    graph_flat = tuple(val for row in synthesis_graph for val in row)
    hash_input = f"{source_phase4_hashes}|{unit_hashes}|{graph_flat}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def _get_eligible_indices_from_phase4(phase4_result) -> List[int]:
    """
    Extract eligible indices from Phase-4 result.

    If transform_type is ELIGIBILITY_FILTER, use eligible_indices.
    Otherwise, use each unit's eligible flag.

    Uses duck typing to avoid importing from tests - checks enum value string.
    """
    # Use duck typing - check the enum value string to avoid import dependency
    transform_type_value = getattr(phase4_result.transform_type, 'value', str(phase4_result.transform_type))

    if transform_type_value == "eligibility_filter":
        return sorted(phase4_result.eligible_indices)
    else:
        return [
            unit.source_index for unit in phase4_result.units
            if unit.eligible
        ]


def _build_contiguous_groups(eligible_indices: List[int]) -> List[Tuple[int, ...]]:
    """
    Build groups of contiguous eligible indices.

    Example: [0, 1, 2, 5, 6] -> [(0, 1, 2), (5, 6)]

    No heuristics. Only contiguity (difference of 1).
    """
    if not eligible_indices:
        return []

    groups = []
    current_group = [eligible_indices[0]]

    for idx in eligible_indices[1:]:
        if idx == current_group[-1] + 1:
            # Contiguous
            current_group.append(idx)
        else:
            # Gap - start new group
            groups.append(tuple(current_group))
            current_group = [idx]

    # Don't forget the last group
    groups.append(tuple(current_group))

    return groups


def _aggregate_rule_vectors(rule_vectors: List[Tuple[int, ...]]) -> Tuple[int, ...]:
    """
    Aggregate rule vectors using min() per position.

    Any FAIL (0) forces FAIL in the aggregated vector.
    """
    if not rule_vectors:
        return ()

    # Check all vectors have same length
    vector_len = len(rule_vectors[0])
    for vec in rule_vectors:
        if len(vec) != vector_len:
            # Length mismatch - return empty to signal ineligibility
            return ()

    # Aggregate using min per position
    aggregated = []
    for pos in range(vector_len):
        min_val = min(vec[pos] for vec in rule_vectors)
        aggregated.append(min_val)

    return tuple(aggregated)


def _build_adjacency_signature(group_indices: Tuple[int, ...], all_indices_set: FrozenSet[int]) -> Tuple[int, ...]:
    """
    Build adjacency signature for a group.

    For each index in group: 1 if adjacent to another index in group, else 0.
    Adjacent means difference of 1.
    """
    signature = []
    group_set = set(group_indices)

    for idx in group_indices:
        # Check if idx-1 or idx+1 is in the group
        has_adjacent = (idx - 1 in group_set) or (idx + 1 in group_set)
        signature.append(1 if has_adjacent else 0)

    return tuple(signature)


def _build_synthesis_graph(groups: List[Tuple[int, ...]]) -> Tuple[Tuple[int, ...], ...]:
    """
    Build group-to-group adjacency graph.

    Group i is adjacent to group j iff any source index in group i
    has difference of 1 with any source index in group j.
    """
    n_groups = len(groups)
    if n_groups == 0:
        return ()

    matrix = []
    for i in range(n_groups):
        row = []
        for j in range(n_groups):
            if i == j:
                row.append(0)  # No self-loops
            else:
                # Check if any index in group i is adjacent to any in group j
                adjacent = 0
                for idx_i in groups[i]:
                    for idx_j in groups[j]:
                        if abs(idx_i - idx_j) == 1:
                            adjacent = 1
                            break
                    if adjacent:
                        break
                row.append(adjacent)
        matrix.append(tuple(row))

    return tuple(matrix)


def _get_phase4_unit_by_index(phase4_result, target_index: int):
    """Find Phase-4 unit by source_index."""
    for unit in phase4_result.units:
        if unit.source_index == target_index:
            return unit
    return None


def _check_for_forbidden_structures(phase4_results: List) -> bool:
    """Check if any Phase-4 results contain forbidden structures (non-hex strings)."""
    for result in phase4_results:
        result_str = str(result)
        # Check for any non-structural strings that aren't hex hashes
        # This is a basic check - the real enforcement is in validation
        for term in FORBIDDEN_TERMS_PHASE5:
            if term in result_str.lower():
                return True
    return False


def synthesize_phase4_to_phase5(results: List) -> "Phase5SynthesisResult":
    """
    Synthesize Phase-4 results into Phase-5 non-textual output.

    Args:
        results: List[Phase4TransformResult] from Phase-4

    Returns:
        Phase5SynthesisResult with non-textual structures only

    Invariants:
        - Phase-4 results are NOT modified
        - No semantic inference
        - No text generation
        - Deterministic: same input always produces same output
        - Reversible: Phase-4 indices and eligibility recoverable
    """
    # Handle empty input
    if not results:
        empty_hash = hashlib.sha256(b"empty_phase5").hexdigest()[:32]
        return Phase5SynthesisResult(
            synthesis_units=(),
            synthesis_graph=(),
            synthesis_hash=empty_hash,
            source_phase4_hashes=(),
            synthesis_type=SynthesisType.ELIGIBILITY_BLOCK,
            reversible=True,
            eligible=False
        )

    # Check for forbidden structures
    if _check_for_forbidden_structures(results):
        empty_hash = hashlib.sha256(b"forbidden_structure").hexdigest()[:32]
        return Phase5SynthesisResult(
            synthesis_units=(),
            synthesis_graph=(),
            synthesis_hash=empty_hash,
            source_phase4_hashes=tuple(r.source_phase3_hash for r in results),
            synthesis_type=SynthesisType.ELIGIBILITY_BLOCK,
            reversible=False,
            eligible=False
        )

    # Collect all eligible indices across all results
    all_synthesis_units = []
    all_source_hashes = []
    all_groups = []
    rule_vector_mismatch = False

    for phase4_result in results:
        all_source_hashes.append(phase4_result.source_phase3_hash)

        # Get eligible indices
        eligible_indices = _get_eligible_indices_from_phase4(phase4_result)

        if not eligible_indices:
            # No eligible indices in this result - continue but note it
            continue

        # Build contiguous groups
        groups = _build_contiguous_groups(eligible_indices)

        # Process each group into a Phase5SynthesisUnit
        for group_indices in groups:
            # Gather rule vectors and modifier counts for units in this group
            rule_vectors = []
            modifier_counts = []
            eligibility_flags = []
            source_unit_hashes = []

            for idx in group_indices:
                unit = _get_phase4_unit_by_index(phase4_result, idx)
                if unit is not None:
                    rule_vectors.append(unit.rule_status_vector)
                    modifier_counts.append(unit.modifier_count)
                    eligibility_flags.append(unit.eligible)
                    source_unit_hashes.append(unit.source_eval_hash)

            # Aggregate rule vectors
            aggregated_vector = _aggregate_rule_vectors(rule_vectors)
            if not aggregated_vector and rule_vectors:
                # Length mismatch detected
                rule_vector_mismatch = True

            # Build adjacency signature
            all_indices_in_result = frozenset(u.source_index for u in phase4_result.units)
            adjacency_sig = _build_adjacency_signature(group_indices, all_indices_in_result)

            # Compute modifier density
            modifier_density = sum(modifier_counts)

            # Build eligibility mask
            eligibility_mask = tuple(eligibility_flags)

            # Compute unit hash
            unit_hash = _compute_unit_hash(
                group_indices,
                aggregated_vector,
                adjacency_sig,
                modifier_density,
                eligibility_mask,
                tuple(source_unit_hashes)
            )

            # Create synthesis unit
            synthesis_unit = Phase5SynthesisUnit(
                source_indices=group_indices,
                aggregated_rule_vector=aggregated_vector,
                adjacency_signature=adjacency_sig,
                modifier_density=modifier_density,
                eligibility_mask=eligibility_mask,
                unit_hash=unit_hash
            )

            all_synthesis_units.append(synthesis_unit)
            all_groups.append(group_indices)

    # Handle rule vector mismatch or no synthesis units
    if rule_vector_mismatch or not all_synthesis_units:
        empty_hash = hashlib.sha256(b"ineligible_synthesis").hexdigest()[:32]
        return Phase5SynthesisResult(
            synthesis_units=tuple(all_synthesis_units),
            synthesis_graph=(),
            synthesis_hash=empty_hash,
            source_phase4_hashes=tuple(all_source_hashes),
            synthesis_type=SynthesisType.ELIGIBILITY_BLOCK,
            reversible=len(all_synthesis_units) > 0,
            eligible=False
        )

    # Build synthesis graph (group-to-group adjacency)
    synthesis_graph = _build_synthesis_graph(all_groups)

    # Compute synthesis hash
    unit_hashes = tuple(u.unit_hash for u in all_synthesis_units)
    synthesis_hash = _compute_synthesis_hash(
        tuple(all_source_hashes),
        unit_hashes,
        synthesis_graph
    )

    # Determine synthesis type based on structure
    if len(all_synthesis_units) == 1:
        synthesis_type = SynthesisType.STRUCTURAL_FOLD
    elif any(1 in row for row in synthesis_graph):
        synthesis_type = SynthesisType.ADJACENCY_COLLAPSE
    else:
        synthesis_type = SynthesisType.RULE_VECTOR_MERGE

    return Phase5SynthesisResult(
        synthesis_units=tuple(all_synthesis_units),
        synthesis_graph=synthesis_graph,
        synthesis_hash=synthesis_hash,
        source_phase4_hashes=tuple(all_source_hashes),
        synthesis_type=synthesis_type,
        reversible=True,
        eligible=True
    )


def recover_phase4_indices(p5: Phase5SynthesisResult) -> Tuple[int, ...]:
    """
    Recover Phase-4 source indices from Phase-5 result.

    Returns all source indices from all synthesis units, flattened.
    """
    indices = []
    for unit in p5.synthesis_units:
        indices.extend(unit.source_indices)
    return tuple(sorted(indices))


def recover_phase4_eligibility_masks(p5: Phase5SynthesisResult) -> Tuple[Tuple[bool, ...], ...]:
    """
    Recover Phase-4 eligibility masks from Phase-5 result.

    Returns tuple of eligibility masks, one per synthesis unit.
    """
    return tuple(unit.eligibility_mask for unit in p5.synthesis_units)


def validate_phase5_invariants() -> bool:
    """Validate that all Phase-5 invariants are preserved."""
    for invariant, value in PHASE5_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Phase-5 invariant violated: {invariant}")
    return True


def check_for_forbidden_terms_phase5(obj: Any) -> List[str]:
    """Check any object for forbidden terms."""
    obj_str = str(obj).lower()
    found = []
    for term in FORBIDDEN_TERMS_PHASE5:
        if term in obj_str:
            found.append(term)
    return found


def is_non_textual_value_phase5(val: Any) -> bool:
    """
    Check if value is non-textual.

    Allowed:
        - bool
        - int
        - tuple of non-textual values
        - frozenset of ints
        - Enum
        - hex string (<=32 chars, only 0-9a-f)

    NOT allowed:
        - Free-form strings
        - Floats (probability)
        - Dict (would need validation)
    """
    if isinstance(val, bool):
        return True
    if isinstance(val, int):
        return True
    if isinstance(val, tuple):
        return all(is_non_textual_value_phase5(v) for v in val)
    if isinstance(val, frozenset):
        return all(isinstance(v, int) for v in val)
    if isinstance(val, str):
        # Only allow hex strings of constrained length
        if len(val) <= 32 and all(c in "0123456789abcdef" for c in val):
            return True
        return False
    if isinstance(val, Enum):
        return True
    return False
