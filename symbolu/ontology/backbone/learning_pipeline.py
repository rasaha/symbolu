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

from .cross_domain_config import (
    get_cross_domain_config,
    CrossDomainConfig,
)
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

class MatchType(Enum):
    """How the match was determined."""
    CAUSAL_CHAIN = "causal_chain"      # Matched on causal sequence (PRIMARY)
    STRUCTURAL = "structural"           # Matched on 10D similarity (FALLBACK)
    PATTERN_TYPE = "pattern_type"       # Matched on pattern type (DISAMBIGUATION)


@dataclass
class RetrievalResult:
    """Result of cross-domain retrieval."""
    experiential: ExperientialObject
    similarity: float
    source_domain: str
    is_cross_domain: bool
    match_type: MatchType = MatchType.STRUCTURAL
    chain_overlap: float = 0.0  # How much causal chain overlaps (0-1)


def _compute_chain_similarity(chain1: Optional[List[str]], chain2: Optional[List[str]]) -> float:
    """
    Compute similarity between two causal chains.

    Uses longest common subsequence to find structural overlap.
    Returns 0-1 score where 1 = identical sequence.
    """
    if not chain1 or not chain2:
        return 0.0

    # Normalize to lowercase
    c1 = [s.lower() for s in chain1]
    c2 = [s.lower() for s in chain2]

    # Find longest common subsequence
    m, n = len(c1), len(c2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if c1[i-1] == c2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs_length = dp[m][n]
    max_length = max(m, n)

    return lcs_length / max_length if max_length > 0 else 0.0


def _extract_causal_chain_from_text(text: str) -> List[str]:
    """
    Extract implicit causal chain from text using event tags.

    Returns list of event types in order of occurrence.
    """
    from .mirror_pairs import tag_events

    events = tag_events(text)
    return [e.event_type.value for e in events]


def retrieve_similar(
    query: str,
    current_domain: Optional[str] = None,
    top_k: int = 5,
    min_similarity: float = 0.1,  # Lowered from 0.5 to allow more cross-domain matches
    cross_domain_only: bool = False,
    store: Optional[ExperientialStore] = None,
    query_chain: Optional[List[str]] = None,
    config: Optional[CrossDomainConfig] = None,
) -> List[RetrievalResult]:
    """
    Retrieve similar experientials using learning hierarchy:

    1. CAUSAL CHAINS (PRIMARY): Match on sequence structure
    2. 10D SIMILARITY (FALLBACK): Match on structural encoding
    3. PATTERN TYPE (DISAMBIGUATION): Resolve overlapping chains

    This is where cross-domain learning happens:
    - Causal chains are domain-agnostic (polarization → conflict → split)
    - Same chain applies to cells, companies, nations
    - 10D provides fallback when chains aren't explicit

    ADMIN CONTROL:
    - Cross-domain config (JSON) controls which pairs are allowed
    - Blocked pairs are excluded from results
    - Counters track where learning is blocked/succeeds

    Args:
        query: Query text to find similar patterns for
        current_domain: Current domain (for cross-domain filtering)
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold
        cross_domain_only: If True, exclude results from current_domain
        store: ExperientialStore to search (defaults to global)
        query_chain: Optional explicit causal chain for query
        config: Optional CrossDomainConfig (uses global if not provided)

    Returns:
        List of RetrievalResult sorted by match quality

    Example:
        >>> results = retrieve_similar(
        ...     query="My startup co-founders are disagreeing",
        ...     current_domain="business",
        ...     cross_domain_only=True
        ... )
        >>> for r in results:
        ...     print(f"[{r.match_type.value}] {r.source_domain}: {r.similarity:.2f}")
    """
    if store is None:
        store = get_experiential_store()

    # Get admin-level cross-domain config
    if config is None:
        config = get_cross_domain_config()

    # ==========================================================================
    # STEP 1: Extract query's causal chain (if not provided)
    # ==========================================================================
    if query_chain is None:
        query_chain = _extract_causal_chain_from_text(query)

    # Encode query to 10D (for fallback matching)
    query_vector = encode_10d(query)

    # ==========================================================================
    # STEP 2: Get candidates from store
    # ==========================================================================
    if cross_domain_only and current_domain:
        raw_results = store.get_cross_domain(
            problem_vector=query_vector,
            exclude_domain=current_domain,
            top_k=top_k * 3,  # Get more candidates for chain filtering
        )
    else:
        raw_results = store.search(
            problem_vector=query_vector,
            min_similarity=min_similarity * 0.5,  # Lower threshold, will re-rank
            top_k=top_k * 3,
        )

    # ==========================================================================
    # STEP 3: Score using LEARNING HIERARCHY
    #         1. Causal Chain (PRIMARY) - weight 0.6
    #         2. 10D Similarity (FALLBACK) - weight 0.3
    #         3. Pattern Type (DISAMBIGUATION) - weight 0.1
    # ==========================================================================
    CHAIN_WEIGHT = 0.6
    STRUCTURAL_WEIGHT = 0.3
    PATTERN_WEIGHT = 0.1

    scored_results = []

    for exp, structural_score in raw_results:
        # Get experiential's causal chain
        exp_chain = None
        if exp.causal_chain:
            exp_chain = exp.causal_chain.steps

        # =======================================================================
        # ADMIN CHECK: Is this domain pair allowed?
        # =======================================================================
        is_cross = current_domain is not None and exp.source_domain != current_domain

        if is_cross and current_domain:
            # Check admin config for this domain pair
            if not config.is_pair_allowed(current_domain, exp.source_domain):
                # Blocked by admin - skip this result (counter already recorded)
                continue

            # Get thresholds for this pair (may be custom)
            thresholds = config.get_thresholds(current_domain, exp.source_domain)
            pair_min_structural = thresholds["structural"]
            pair_min_causal = thresholds["causal"]
            pair_min_combined = thresholds["combined"]
        else:
            # Same domain or no domain specified - use relaxed defaults
            pair_min_structural = min_similarity
            pair_min_causal = 0.1  # Lowered from 0.3
            pair_min_combined = min_similarity

        # Compute chain similarity (PRIMARY)
        chain_sim = _compute_chain_similarity(query_chain, exp_chain)

        # Determine match type
        if chain_sim >= 0.5:
            match_type = MatchType.CAUSAL_CHAIN
        elif structural_score >= min_similarity:
            match_type = MatchType.STRUCTURAL
        else:
            match_type = MatchType.PATTERN_TYPE

        # Pattern type bonus (for disambiguation)
        pattern_bonus = 0.0
        # Could add pattern type matching here if query has expected pattern

        # Compute final score using hierarchy weights
        final_score = (
            chain_sim * CHAIN_WEIGHT +
            structural_score * STRUCTURAL_WEIGHT +
            pattern_bonus * PATTERN_WEIGHT
        )

        # =======================================================================
        # THRESHOLD CHECK: Does this meet the pair-specific thresholds?
        # =======================================================================
        if is_cross and current_domain:
            # For cross-domain, check against pair-specific thresholds
            threshold_met = (
                chain_sim >= pair_min_causal or
                structural_score >= pair_min_structural or
                final_score >= pair_min_combined
            )
            if not threshold_met:
                # Record threshold failure for admin visibility
                config.record_transfer_result(
                    current_domain, exp.source_domain,
                    success=False, threshold_met=False
                )
                continue
            else:
                # Record success
                config.record_transfer_result(
                    current_domain, exp.source_domain,
                    success=True, threshold_met=True
                )
        else:
            # Skip if below default threshold
            if final_score < min_similarity * 0.5:
                continue

        scored_results.append(RetrievalResult(
            experiential=exp,
            similarity=final_score,
            source_domain=exp.source_domain,
            is_cross_domain=is_cross,
            match_type=match_type,
            chain_overlap=chain_sim,
        ))

    # ==========================================================================
    # STEP 4: Sort by score and return top_k
    # ==========================================================================
    scored_results.sort(key=lambda r: r.similarity, reverse=True)

    return scored_results[:top_k]


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
    "MatchType",
    "RetrievalResult",
    "BatchLearningResult",
    # Learning functions
    "learn_from_event",
    "learn_batch",
    # Retrieval functions
    "retrieve_similar",
]
