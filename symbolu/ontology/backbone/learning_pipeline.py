"""
Event Learning Pipeline
=======================

Connects the validation gates to the experiential store for cross-domain learning.

Architecture:
    Input Event
         │
         ▼
    ┌─────────────────┐
    │ SEMANTIC GATE   │  ← Boolean: Pass/Block
    │ (pre-filter)    │     "Is this logically possible?"
    └────────┬────────┘
             │ Pass
             ▼
    ┌─────────────────┐
    │ 10D ENCODING    │  ← Continuous: The learning target
    │ (structure)     │     This is what transfers across domains
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ PHONEME GATE    │  ← Boolean: Store/Discard
    │ (post-validate) │     "Is this universally encoded?"
    └────────┬────────┘
             │ Pass
             ▼
    ┌─────────────────┐
    │ PATTERN STORE   │  ← Validated universal patterns
    │ (experiential)  │     Ready for cross-domain retrieval
    └─────────────────┘

Key insight:
- Binary gates (semantic, phoneme) are for VALIDATION
- Continuous 10D space is for LEARNING and TRANSFER
- Transparency is for USERS (which gate flagged)
- 10D similarity is for CROSS-DOMAIN matching
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Any, Dict
from enum import Enum

from .phoneme_validator import (
    validate_event,
    ValidationReport,
    ValidationResult,
)
from .experiential import (
    ExperientialObject,
    ExperientialStore,
    get_experiential_store,
    create_experiential,
    PatternType,
    CausalChain,
)
from .encoder import DimensionalVector, encode_10d
from .similarity import structural_similarity


class LearningOutcome(Enum):
    """Outcome of the learning pipeline."""
    STORED = "stored"                    # Passed both gates, stored
    BLOCKED_SEMANTIC = "blocked_semantic"  # Failed semantic gate
    BLOCKED_PHONEME = "blocked_phoneme"   # Failed phoneme gate
    BLOCKED_BOTH = "blocked_both"         # Failed both gates


@dataclass
class LearningResult:
    """
    Result of attempting to learn from an event.

    Transparent about:
    - Whether it was stored
    - Which gate blocked it (if any)
    - The 10D encoding (even if blocked)
    - The validation report
    """
    outcome: LearningOutcome
    stored: bool
    experiential_id: Optional[str]  # ID if stored, None if blocked

    # The 10D encoding (learning target) - available even if blocked
    vector_10d: DimensionalVector

    # Validation details (transparency)
    validation_report: ValidationReport
    blocked_by: str  # 'none', 'semantic', 'phoneme', 'both'
    block_reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "stored": self.stored,
            "experiential_id": self.experiential_id,
            "vector_10d": self.vector_10d.to_dict(),
            "blocked_by": self.blocked_by,
            "block_reason": self.block_reason,
            "validation": self.validation_report.to_dict(),
        }


def learn_from_event(
    content: str,
    domain: str,
    pattern_name: Optional[str] = None,
    insight: Optional[str] = None,
    causal_steps: Optional[List[str]] = None,
    transferable_to: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    reference: Optional[str] = None,
    store: Optional[ExperientialStore] = None,
    alignment_threshold: float = 0.5,
) -> LearningResult:
    """
    The learning pipeline: validate and store an event as experiential knowledge.

    Pipeline:
    1. SEMANTIC GATE: Check for logical contradictions (pre-filter)
    2. 10D ENCODING: Encode to structural representation (learning target)
    3. PHONEME GATE: Validate sound-meaning alignment (post-validate)
    4. STORE: If both gates pass, store in experiential store

    Args:
        content: The event text to learn from
        domain: Source domain (e.g., "history", "biology", "finance")
        pattern_name: Optional name for the pattern
        insight: Optional insight extracted from the event
        causal_steps: Optional causal chain steps
        transferable_to: Optional list of target domains
        tags: Optional tags for indexing
        reference: Optional source reference
        store: ExperientialStore to use (defaults to global)
        alignment_threshold: Threshold for phoneme validation

    Returns:
        LearningResult with outcome, 10D encoding, and validation details

    Example:
        >>> result = learn_from_event(
        ...     content="The empire was shattered by internal conflict",
        ...     domain="history",
        ...     pattern_name="bifurcation_from_conflict",
        ...     insight="Internal division leads to structural collapse"
        ... )
        >>> if result.stored:
        ...     print(f"Learned: {result.experiential_id}")
        ... else:
        ...     print(f"Blocked by: {result.blocked_by}")
    """
    if store is None:
        store = get_experiential_store()

    # ==========================================================================
    # Run validation (includes both SEMANTIC and PHONEME gates)
    # ==========================================================================
    validation = validate_event(
        event_text=content,
        alignment_threshold=alignment_threshold,
    )

    # The 10D encoding is available in the validation report
    vector_10d = validation.event_vector

    # ==========================================================================
    # Determine outcome based on which gate(s) blocked
    # ==========================================================================
    if validation.is_universal:
        # Both gates passed - store the experiential
        outcome = LearningOutcome.STORED
        blocked_by = "none"
        block_reason = None

        # Create and store the experiential
        exp = create_experiential(
            content=content,
            domain=domain,
            pattern_name=pattern_name or _infer_pattern_name(validation),
            insight=insight or _infer_insight(validation),
            causal_steps=causal_steps,
            transferable_to=transferable_to,
            tags=tags,
            reference=reference,
        )
        store.add(exp)
        experiential_id = exp.experiential_id

    else:
        # One or both gates blocked - determine which
        experiential_id = None
        blocked_by = validation.flagged_by
        block_reason = validation.anomaly_reason

        if blocked_by == "semantic":
            outcome = LearningOutcome.BLOCKED_SEMANTIC
        elif blocked_by == "phoneme":
            outcome = LearningOutcome.BLOCKED_PHONEME
        else:  # "both"
            outcome = LearningOutcome.BLOCKED_BOTH

    return LearningResult(
        outcome=outcome,
        stored=(outcome == LearningOutcome.STORED),
        experiential_id=experiential_id,
        vector_10d=vector_10d,
        validation_report=validation,
        blocked_by=blocked_by,
        block_reason=block_reason,
    )


def _infer_pattern_name(validation: ValidationReport) -> str:
    """Infer a pattern name from the validation report."""
    if validation.tagged_events:
        # Use the first event type as the pattern
        event_types = [e.event_type.value for e in validation.tagged_events]
        return "_".join(event_types[:2])
    return "unknown_pattern"


def _infer_insight(validation: ValidationReport) -> str:
    """Infer an insight from the validation report."""
    if validation.tagged_events:
        event_types = [e.event_type.value for e in validation.tagged_events]
        return f"Pattern involving: {', '.join(event_types)}"
    return "Validated universal pattern"


# =============================================================================
# Cross-Domain Retrieval
# =============================================================================

@dataclass
class RetrievalResult:
    """Result of cross-domain retrieval."""
    experiential: ExperientialObject
    similarity: float
    source_domain: str
    is_cross_domain: bool


def retrieve_similar(
    query: str,
    current_domain: Optional[str] = None,
    top_k: int = 5,
    min_similarity: float = 0.5,
    cross_domain_only: bool = False,
    store: Optional[ExperientialStore] = None,
) -> List[RetrievalResult]:
    """
    Retrieve similar experientials by 10D structural similarity.

    This is where cross-domain learning happens:
    - Query is encoded to 10D
    - Store is searched by 10D similarity
    - Results ranked by structural match, not domain

    Args:
        query: Query text to find similar patterns for
        current_domain: Current domain (for cross-domain filtering)
        top_k: Number of results to return
        min_similarity: Minimum 10D similarity threshold
        cross_domain_only: If True, exclude results from current_domain
        store: ExperientialStore to search (defaults to global)

    Returns:
        List of RetrievalResult sorted by similarity

    Example:
        >>> results = retrieve_similar(
        ...     query="My startup co-founders are disagreeing",
        ...     current_domain="business",
        ...     cross_domain_only=True
        ... )
        >>> for r in results:
        ...     print(f"[{r.source_domain}] {r.similarity:.2f}: {r.experiential.insight}")
    """
    if store is None:
        store = get_experiential_store()

    # Encode query to 10D
    query_vector = encode_10d(query)

    # Search by 10D similarity
    if cross_domain_only and current_domain:
        raw_results = store.get_cross_domain(
            problem_vector=query_vector,
            exclude_domain=current_domain,
            top_k=top_k,
        )
    else:
        raw_results = store.search(
            problem_vector=query_vector,
            min_similarity=min_similarity,
            top_k=top_k,
        )

    # Convert to RetrievalResult
    results = []
    for exp, score in raw_results:
        is_cross = current_domain is not None and exp.source_domain != current_domain
        results.append(RetrievalResult(
            experiential=exp,
            similarity=score,
            source_domain=exp.source_domain,
            is_cross_domain=is_cross,
        ))

    return results


# =============================================================================
# Batch Learning
# =============================================================================

@dataclass
class BatchLearningResult:
    """Result of batch learning."""
    total: int
    stored: int
    blocked_semantic: int
    blocked_phoneme: int
    blocked_both: int
    results: List[LearningResult]


def learn_batch(
    items: List[Dict[str, Any]],
    store: Optional[ExperientialStore] = None,
) -> BatchLearningResult:
    """
    Learn from a batch of events.

    Args:
        items: List of dicts with 'content', 'domain', and optional fields
        store: ExperientialStore to use

    Returns:
        BatchLearningResult with counts and individual results

    Example:
        >>> items = [
        ...     {"content": "The empire collapsed", "domain": "history"},
        ...     {"content": "The cell divided", "domain": "biology"},
        ... ]
        >>> result = learn_batch(items)
        >>> print(f"Stored: {result.stored}/{result.total}")
    """
    if store is None:
        store = get_experiential_store()

    results = []
    counts = {
        LearningOutcome.STORED: 0,
        LearningOutcome.BLOCKED_SEMANTIC: 0,
        LearningOutcome.BLOCKED_PHONEME: 0,
        LearningOutcome.BLOCKED_BOTH: 0,
    }

    for item in items:
        result = learn_from_event(
            content=item["content"],
            domain=item["domain"],
            pattern_name=item.get("pattern_name"),
            insight=item.get("insight"),
            causal_steps=item.get("causal_steps"),
            transferable_to=item.get("transferable_to"),
            tags=item.get("tags"),
            reference=item.get("reference"),
            store=store,
        )
        results.append(result)
        counts[result.outcome] += 1

    return BatchLearningResult(
        total=len(items),
        stored=counts[LearningOutcome.STORED],
        blocked_semantic=counts[LearningOutcome.BLOCKED_SEMANTIC],
        blocked_phoneme=counts[LearningOutcome.BLOCKED_PHONEME],
        blocked_both=counts[LearningOutcome.BLOCKED_BOTH],
        results=results,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Outcomes
    "LearningOutcome",
    "LearningResult",
    "RetrievalResult",
    "BatchLearningResult",
    # Learning functions
    "learn_from_event",
    "learn_batch",
    # Retrieval functions
    "retrieve_similar",
]
