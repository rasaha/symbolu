"""
Phase-7.0 Structural Folding Engine (v7.0)
==========================================

Phase-7.0 performs structural folding over Phase-5 output to produce
higher-order non-textual artifacts while preserving:
    - determinism
    - non-textual output
    - eligibility gating
    - reversibility
    - non-mutation of prior phase objects
    - isolation (Phase-7 sees only Phase-5)

This module is:
    - TEST-ONLY
    - CONTROLLED GENERATION (structural folding only)
    - NON-TEXTUAL
    - DETERMINISTIC
    - REVERSIBLE
    - ISOLATED

It operates ONLY on Phase-5 output (Phase5SynthesisResult).

ABSOLUTE RULES:
    - NO TEXT OUTPUT: No words, sentences, language strings, or labels
    - Only hex hashes (<=32 chars) or Enum values allowed as strings
    - NO SEMANTICS: No meaning, intent, emotion, sentiment inference
    - NO DICTIONARIES / NLP / LLM: No lookups, NLP libraries, LLM calls, embeddings
    - NO RANDOMNESS / TIME: No random, UUID, datetime, system time, non-deterministic sets
    - NON-MUTATING: Must not modify Phase-5 objects (or any upstream objects)
    - REVERSIBLE: Must allow recovery of Phase-5 indices, eligibility masks
    - STRUCTURAL FOLDING ONLY: Generate only index groupings and structural projections

Version: 7.0
"""

import hashlib
from dataclasses import dataclass
from typing import Tuple, List, Any
from enum import Enum


__all__ = [
    "PHASE7_ENGINE_VERSION",
    "PHASE7_INVARIANTS",
    "FORBIDDEN_TERMS_PHASE7",
    "FoldingType",
    "Phase7FoldedUnit",
    "Phase7FoldedArtifact",
    "fold_phase5_to_phase7",
    "recover_phase5_indices",
    "recover_phase5_eligibility_masks",
    "unfold_to_phase5_projection",
    "validate_phase7_invariants",
    "check_for_forbidden_terms_phase7",
    "is_non_textual_value_phase7",
]


PHASE7_ENGINE_VERSION = "7.0"

PHASE7_INVARIANTS = {
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

FORBIDDEN_TERMS_PHASE7 = frozenset([
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
    # Time/Randomness
    "timestamp", "datetime", "random", "uuid",
])


class FoldingType(Enum):
    """Folding type categories - structural only."""
    STRUCTURAL_FOLD = "structural_fold"
    INDEX_CHAIN = "index_chain"


@dataclass(frozen=True)
class Phase7FoldedUnit:
    """
    Phase-7 folded unit for a group of contiguous eligible Phase-5 units.

    Contains ONLY:
        - source_phase5_indices: Tuple of Phase-5 synthesis unit indices in this fold
        - aggregated_fold_vector: Tuple of ints (0, 1, or 2) - aggregated rule vectors
        - fold_adjacency: Tuple of ints (0 or 1) - OR-combined adjacency signatures
        - eligibility_chain: Tuple of bools - eligibility for each Phase-5 unit in fold
        - unit_hash: 16-32 char hex hash

    NO free-form strings. NO semantic content. NO text generation.
    """
    source_phase5_indices: Tuple[int, ...]
    aggregated_fold_vector: Tuple[int, ...]
    fold_adjacency: Tuple[int, ...]
    eligibility_chain: Tuple[bool, ...]
    unit_hash: str

    def __post_init__(self):
        # Validate source_phase5_indices
        if not isinstance(self.source_phase5_indices, tuple):
            raise ValueError("source_phase5_indices must be tuple")
        for idx in self.source_phase5_indices:
            if not isinstance(idx, int):
                raise ValueError("source_phase5_indices must contain only ints")

        # Validate aggregated_fold_vector
        if not isinstance(self.aggregated_fold_vector, tuple):
            raise ValueError("aggregated_fold_vector must be tuple")
        for val in self.aggregated_fold_vector:
            if not isinstance(val, int) or val not in (0, 1, 2):
                raise ValueError("aggregated_fold_vector values must be 0, 1, or 2")

        # Validate fold_adjacency
        if not isinstance(self.fold_adjacency, tuple):
            raise ValueError("fold_adjacency must be tuple")
        for val in self.fold_adjacency:
            if not isinstance(val, int) or val not in (0, 1):
                raise ValueError("fold_adjacency values must be 0 or 1")

        # Validate eligibility_chain
        if not isinstance(self.eligibility_chain, tuple):
            raise ValueError("eligibility_chain must be tuple")
        for val in self.eligibility_chain:
            if not isinstance(val, bool):
                raise ValueError("eligibility_chain values must be bool")

        # Validate unit_hash
        if not isinstance(self.unit_hash, str):
            raise ValueError("unit_hash must be str")
        if not (16 <= len(self.unit_hash) <= 32):
            raise ValueError("unit_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.unit_hash):
            raise ValueError("unit_hash must be hex")

        # Validate lengths match
        if len(self.eligibility_chain) != len(self.source_phase5_indices):
            raise ValueError("eligibility_chain length must match source_phase5_indices length")


@dataclass(frozen=True)
class Phase7FoldedArtifact:
    """
    Phase-7 complete folding result.

    Contains ONLY:
        - folded_units: Tuple of Phase7FoldedUnit
        - fold_graph: Tuple of tuples (0/1 fold-to-fold adjacency matrix)
        - folding_hash: 16-32 char hex hash
        - source_phase5_hashes: Tuple of Phase-5 source hashes
        - folding_type: FoldingType enum
        - reversible: bool - True if Phase-5 data recoverable
        - eligible: bool - True if folding was successful

    NO free-form strings. NO semantic content.
    """
    folded_units: Tuple["Phase7FoldedUnit", ...]
    fold_graph: Tuple[Tuple[int, ...], ...]
    folding_hash: str
    source_phase5_hashes: Tuple[str, ...]
    folding_type: FoldingType
    reversible: bool
    eligible: bool

    def __post_init__(self):
        # Validate folded_units
        if not isinstance(self.folded_units, tuple):
            raise ValueError("folded_units must be tuple")

        # Validate fold_graph
        if not isinstance(self.fold_graph, tuple):
            raise ValueError("fold_graph must be tuple")
        for row in self.fold_graph:
            if not isinstance(row, tuple):
                raise ValueError("fold_graph rows must be tuples")
            for val in row:
                if not isinstance(val, int) or val not in (0, 1):
                    raise ValueError("fold_graph values must be 0 or 1")

        # Validate folding_hash
        if not isinstance(self.folding_hash, str):
            raise ValueError("folding_hash must be str")
        if not (16 <= len(self.folding_hash) <= 32):
            raise ValueError("folding_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.folding_hash):
            raise ValueError("folding_hash must be hex")

        # Validate source_phase5_hashes
        if not isinstance(self.source_phase5_hashes, tuple):
            raise ValueError("source_phase5_hashes must be tuple")
        for h in self.source_phase5_hashes:
            if not isinstance(h, str):
                raise ValueError("source_phase5_hashes must contain only strings")
            if not (16 <= len(h) <= 32):
                raise ValueError("source_phase5_hashes entries must be 16-32 chars")
            if not all(c in "0123456789abcdef" for c in h):
                raise ValueError("source_phase5_hashes entries must be hex")

        # Validate folding_type
        if not isinstance(self.folding_type, FoldingType):
            raise ValueError("folding_type must be FoldingType enum")

        # Validate reversible and eligible
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be bool")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be bool")


def _compute_fold_unit_hash(
    source_phase5_indices: Tuple[int, ...],
    aggregated_fold_vector: Tuple[int, ...],
    fold_adjacency: Tuple[int, ...],
    eligibility_chain: Tuple[bool, ...],
    source_phase5_hash: str
) -> str:
    """Compute deterministic hash for a fold unit."""
    hash_input = (
        f"{source_phase5_indices}|"
        f"{aggregated_fold_vector}|"
        f"{fold_adjacency}|"
        f"{eligibility_chain}|"
        f"{source_phase5_hash}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _compute_folding_hash(
    source_phase5_hashes: Tuple[str, ...],
    unit_hashes: Tuple[str, ...],
    fold_graph: Tuple[Tuple[int, ...], ...]
) -> str:
    """Compute deterministic hash for entire folding result."""
    # Join unit hashes with separator
    unit_hash_str = "||".join(unit_hashes)
    # Join source hashes with separator
    source_hash_str = "||".join(source_phase5_hashes)
    hash_input = f"{unit_hash_str}||{source_hash_str}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def _is_phase5_unit_eligible(phase5_unit) -> bool:
    """
    Check if a Phase-5 synthesis unit is eligible for folding.

    A Phase-5 unit is eligible iff:
        - any(unit.eligibility_mask) is True
        - len(unit.source_indices) == len(unit.eligibility_mask)
    """
    if not hasattr(phase5_unit, 'eligibility_mask') or not hasattr(phase5_unit, 'source_indices'):
        return False
    if len(phase5_unit.source_indices) != len(phase5_unit.eligibility_mask):
        return False
    return any(phase5_unit.eligibility_mask)


def _get_phase5_unit_index_range(phase5_unit) -> Tuple[int, int]:
    """Get min and max source indices from a Phase-5 unit."""
    if not phase5_unit.source_indices:
        return (-1, -1)
    return (min(phase5_unit.source_indices), max(phase5_unit.source_indices))


def _are_units_contiguous(unit_a, unit_b) -> bool:
    """
    Check if two Phase-5 units are fold-contiguous.

    Two Phase-5 synthesis units U_i and U_{i+1} are fold-contiguous iff:
        1. Both are eligible (checked before calling)
        2. Their index ranges touch: max(U_i.source_indices) + 1 == min(U_{i+1}.source_indices)
    """
    _, max_a = _get_phase5_unit_index_range(unit_a)
    min_b, _ = _get_phase5_unit_index_range(unit_b)

    if max_a == -1 or min_b == -1:
        return False

    return max_a + 1 == min_b


def _aggregate_rule_vectors_phase7(rule_vectors: List[Tuple[int, ...]]) -> Tuple[int, ...]:
    """
    Aggregate rule vectors using the Phase-7 operator.

    Per-position aggregation where ordering is: 0 < 2 < 1 (fail dominates, pass weakest, n/a middle)
    This means min() with special ordering:
        - 0 (FAIL) is lowest, always wins
        - 2 (N/A) is middle
        - 1 (PASS) is highest, only survives if all are 1
    """
    if not rule_vectors:
        return ()

    # Check all vectors have same length
    vector_len = len(rule_vectors[0])
    for vec in rule_vectors:
        if len(vec) != vector_len:
            return ()

    # Define custom ordering: 0 < 2 < 1
    def priority_value(v: int) -> int:
        if v == 0:
            return 0  # Lowest priority (FAIL dominates)
        elif v == 2:
            return 1  # Middle priority (N/A)
        else:  # v == 1
            return 2  # Highest priority (PASS only if all pass)

    aggregated = []
    for pos in range(vector_len):
        # Find the value with minimum priority (0 < 2 < 1)
        values_at_pos = [vec[pos] for vec in rule_vectors]
        min_priority_val = min(values_at_pos, key=priority_value)
        aggregated.append(min_priority_val)

    return tuple(aggregated)


def _or_combine_adjacency_signatures(signatures: List[Tuple[int, ...]]) -> Tuple[int, ...]:
    """
    OR-combine binary adjacency signatures across units.

    Per-position OR: 1 if any signature has 1 at that position, else 0.
    """
    if not signatures:
        return ()

    # Find max length (in case of mismatched lengths)
    max_len = max(len(sig) for sig in signatures)
    if max_len == 0:
        return ()

    combined = []
    for pos in range(max_len):
        # OR across all signatures at this position
        or_val = 0
        for sig in signatures:
            if pos < len(sig) and sig[pos] == 1:
                or_val = 1
                break
        combined.append(or_val)

    return tuple(combined)


def _build_fold_groups(
    eligible_indices: List[int],
    phase5_units: Tuple
) -> List[List[int]]:
    """
    Build groups of contiguous eligible Phase-5 unit indices.

    Uses single-pass fold segmentation.
    """
    if not eligible_indices:
        return []

    groups = []
    current_group = [eligible_indices[0]]

    for idx in eligible_indices[1:]:
        prev_idx = current_group[-1]
        prev_unit = phase5_units[prev_idx]
        curr_unit = phase5_units[idx]

        if _are_units_contiguous(prev_unit, curr_unit):
            # Contiguous - add to current group
            current_group.append(idx)
        else:
            # Gap - emit current group and start new one
            groups.append(current_group)
            current_group = [idx]

    # Don't forget the last group
    if current_group:
        groups.append(current_group)

    return groups


def _build_fold_graph(
    folded_units: List["Phase7FoldedUnit"],
    phase5_units: Tuple
) -> Tuple[Tuple[int, ...], ...]:
    """
    Build fold-to-fold adjacency graph.

    Folds are adjacent iff their folded index ranges touch.
    """
    n_folds = len(folded_units)
    if n_folds == 0:
        return ()

    # Get the overall source index range for each fold
    fold_ranges = []
    for fold_unit in folded_units:
        # Get all source_indices from all Phase-5 units in this fold
        all_indices = []
        for p5_idx in fold_unit.source_phase5_indices:
            all_indices.extend(phase5_units[p5_idx].source_indices)
        if all_indices:
            fold_ranges.append((min(all_indices), max(all_indices)))
        else:
            fold_ranges.append((-1, -1))

    matrix = []
    for i in range(n_folds):
        row = []
        for j in range(n_folds):
            if i == j:
                row.append(0)  # No self-loops
            else:
                # Check if fold i's max + 1 == fold j's min
                _, max_i = fold_ranges[i]
                min_j, _ = fold_ranges[j]
                if max_i != -1 and min_j != -1 and max_i + 1 == min_j:
                    row.append(1)
                elif min_j != -1 and max_i != -1:
                    # Also check reverse
                    _, max_j = fold_ranges[j]
                    if max_j + 1 == fold_ranges[i][0]:
                        row.append(1)
                    else:
                        row.append(0)
                else:
                    row.append(0)
        matrix.append(tuple(row))

    return tuple(matrix)


def fold_phase5_to_phase7(phase5_result) -> Phase7FoldedArtifact:
    """
    Fold Phase-5 result into Phase-7 structural artifact.

    Args:
        phase5_result: Phase5SynthesisResult from Phase-5

    Returns:
        Phase7FoldedArtifact with structural folds only

    Invariants:
        - Phase-5 result is NOT modified
        - No semantic inference
        - No text generation
        - Deterministic: same input always produces same output
        - Reversible: Phase-5 indices and eligibility recoverable
        - Controlled generation: only structural folding
    """
    # Handle empty or ineligible Phase-5 result
    if phase5_result is None:
        empty_hash = hashlib.sha256(b"empty_phase7_null").hexdigest()[:32]
        return Phase7FoldedArtifact(
            folded_units=(),
            fold_graph=(),
            folding_hash=empty_hash,
            source_phase5_hashes=(),
            folding_type=FoldingType.INDEX_CHAIN,
            reversible=True,
            eligible=False
        )

    # Check if Phase-5 result is eligible
    if not getattr(phase5_result, 'eligible', False):
        source_hash = getattr(phase5_result, 'synthesis_hash', '')
        if not source_hash or len(source_hash) < 16:
            source_hash = hashlib.sha256(b"ineligible_source").hexdigest()[:32]
        empty_hash = hashlib.sha256(f"empty_phase7_{source_hash}".encode()).hexdigest()[:32]
        return Phase7FoldedArtifact(
            folded_units=(),
            fold_graph=(),
            folding_hash=empty_hash,
            source_phase5_hashes=(source_hash,) if source_hash else (),
            folding_type=FoldingType.INDEX_CHAIN,
            reversible=True,
            eligible=False
        )

    # Get Phase-5 synthesis units
    synthesis_units = getattr(phase5_result, 'synthesis_units', ())
    if not synthesis_units:
        source_hash = phase5_result.synthesis_hash
        empty_hash = hashlib.sha256(f"empty_phase7_no_units_{source_hash}".encode()).hexdigest()[:32]
        return Phase7FoldedArtifact(
            folded_units=(),
            fold_graph=(),
            folding_hash=empty_hash,
            source_phase5_hashes=(source_hash,),
            folding_type=FoldingType.INDEX_CHAIN,
            reversible=True,
            eligible=False
        )

    # Step 1: Identify eligible Phase-5 units
    eligible_phase5_indices = []
    for idx, unit in enumerate(synthesis_units):
        if _is_phase5_unit_eligible(unit):
            eligible_phase5_indices.append(idx)

    if not eligible_phase5_indices:
        source_hash = phase5_result.synthesis_hash
        empty_hash = hashlib.sha256(f"empty_phase7_no_eligible_{source_hash}".encode()).hexdigest()[:32]
        return Phase7FoldedArtifact(
            folded_units=(),
            fold_graph=(),
            folding_hash=empty_hash,
            source_phase5_hashes=(source_hash,),
            folding_type=FoldingType.INDEX_CHAIN,
            reversible=True,
            eligible=False
        )

    # Step 2: Build fold groups (contiguous eligible Phase-5 units)
    fold_groups = _build_fold_groups(eligible_phase5_indices, synthesis_units)

    # Step 3: Create Phase7FoldedUnit for each group
    folded_units = []
    source_phase5_hash = phase5_result.synthesis_hash

    for group_indices in fold_groups:
        # Gather data from Phase-5 units in this group
        rule_vectors = []
        adjacency_signatures = []
        eligibility_chain = []

        for p5_idx in group_indices:
            p5_unit = synthesis_units[p5_idx]
            rule_vectors.append(p5_unit.aggregated_rule_vector)
            adjacency_signatures.append(p5_unit.adjacency_signature)
            # Mark this Phase-5 unit as eligible (it passed the eligibility check)
            eligibility_chain.append(True)

        # Aggregate rule vectors
        aggregated_vector = _aggregate_rule_vectors_phase7(rule_vectors)

        # OR-combine adjacency signatures
        combined_adjacency = _or_combine_adjacency_signatures(adjacency_signatures)

        # Compute unit hash
        unit_hash = _compute_fold_unit_hash(
            tuple(group_indices),
            aggregated_vector,
            combined_adjacency,
            tuple(eligibility_chain),
            source_phase5_hash
        )

        # Create fold unit
        fold_unit = Phase7FoldedUnit(
            source_phase5_indices=tuple(group_indices),
            aggregated_fold_vector=aggregated_vector,
            fold_adjacency=combined_adjacency,
            eligibility_chain=tuple(eligibility_chain),
            unit_hash=unit_hash
        )
        folded_units.append(fold_unit)

    # Step 4: Build fold graph
    fold_graph = _build_fold_graph(folded_units, synthesis_units)

    # Step 5: Compute folding hash
    unit_hashes = tuple(u.unit_hash for u in folded_units)
    folding_hash = _compute_folding_hash(
        (source_phase5_hash,),
        unit_hashes,
        fold_graph
    )

    # Step 6: Determine folding type
    if len(folded_units) == 1:
        folding_type = FoldingType.STRUCTURAL_FOLD
    else:
        folding_type = FoldingType.INDEX_CHAIN

    # Step 7: Check reversibility
    # Reversible if all folds have strictly increasing indices and masks align
    reversible = True
    for fold_unit in folded_units:
        indices = fold_unit.source_phase5_indices
        if len(indices) > 1:
            for i in range(len(indices) - 1):
                if indices[i] >= indices[i + 1]:
                    reversible = False
                    break
        if not reversible:
            break
        # Check mask alignment
        if len(fold_unit.eligibility_chain) != len(fold_unit.source_phase5_indices):
            reversible = False
            break

    return Phase7FoldedArtifact(
        folded_units=tuple(folded_units),
        fold_graph=fold_graph,
        folding_hash=folding_hash,
        source_phase5_hashes=(source_phase5_hash,),
        folding_type=folding_type,
        reversible=reversible,
        eligible=True
    )


def recover_phase5_indices(fold_result: Phase7FoldedArtifact) -> Tuple[int, ...]:
    """
    Recover Phase-5 source indices from Phase-7 result.

    Returns all source Phase-5 indices from all folded units, flattened and sorted.
    """
    indices = []
    for unit in fold_result.folded_units:
        indices.extend(unit.source_phase5_indices)
    return tuple(sorted(indices))


def recover_phase5_eligibility_masks(fold_result: Phase7FoldedArtifact) -> Tuple[Tuple[bool, ...], ...]:
    """
    Recover Phase-5 eligibility chains from Phase-7 result.

    Returns tuple of eligibility chains, one per folded unit.
    """
    return tuple(unit.eligibility_chain for unit in fold_result.folded_units)


def unfold_to_phase5_projection(fold_result: Phase7FoldedArtifact) -> Tuple[Tuple[int, bool], ...]:
    """
    Unfold to Phase-5 projection.

    Emits only (index, eligible_bit) pairs, no other content.
    This is sufficient to prove reversibility without reconstructing Phase-5 objects.
    """
    projection = []
    for unit in fold_result.folded_units:
        for idx, eligible in zip(unit.source_phase5_indices, unit.eligibility_chain):
            projection.append((idx, eligible))
    return tuple(projection)


def validate_phase7_invariants() -> bool:
    """Validate that all Phase-7 invariants are preserved."""
    for invariant, value in PHASE7_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Phase-7 invariant violated: {invariant}")
    return True


def check_for_forbidden_terms_phase7(obj: Any) -> List[str]:
    """Check any object for forbidden terms."""
    obj_str = str(obj).lower()
    found = []
    for term in FORBIDDEN_TERMS_PHASE7:
        if term in obj_str:
            found.append(term)
    return found


def is_non_textual_value_phase7(val: Any) -> bool:
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
        return all(is_non_textual_value_phase7(v) for v in val)
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
