"""
RAG-Fusion Adapter Module
==========================

Bridges RAG retrieval output to the Fusion engine candidate format.
Converts CandidateEntry from RAG to Candidate for Fusion with
proper channel score computation based on relevance and metadata.

Integration Points:
    - RAG CandidateEntry → Fusion Candidate
    - Phoneme analysis for channel score modulation
    - Domain-aware scoring
    - Hybrid optimization integration

LLM Best Practices Applied:
    - Graceful degradation when modules unavailable
    - Deterministic scoring without LLM calls
    - Caching for repeated queries
    - Batch processing support
    - Comprehensive error handling

Version: 1.0.0
"""

from __future__ import annotations

import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from functools import lru_cache

if TYPE_CHECKING:
    from symbolu.rag import CandidateEntry
    from symbolu.mechanical.fusion.schemas.candidate import Candidate

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"

# =============================================================================
# OPTIONAL IMPORTS (graceful degradation)
# =============================================================================

# RAG module
try:
    from symbolu.rag import CandidateEntry, run_rag, run_rag_multi, list_indexed_corpora
    HAS_RAG = True
except ImportError:
    HAS_RAG = False
    CandidateEntry = None

# Fusion Candidate
try:
    from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource
    HAS_FUSION = True
except ImportError:
    HAS_FUSION = False
    Candidate = None
    CandidateSource = None

# Resonance for phoneme analysis
try:
    from symbolu.resonance import analyze_phrase, analyze_word
    HAS_RESONANCE = True
except ImportError:
    HAS_RESONANCE = False

# Hybrid router for semantic routing
try:
    from symbolu.hybrid.router import SemanticRouter, ModelType
    HAS_ROUTER = True
except ImportError:
    HAS_ROUTER = False

# Hybrid prefilter
try:
    from symbolu.hybrid.prefilter import CandidatePreFilter
    HAS_PREFILTER = True
except ImportError:
    HAS_PREFILTER = False


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class RAGChannelScores:
    """Channel scores derived from RAG candidate."""
    hrm: float  # High-resolution meaning channel
    lcm: float  # Low-context (practical) channel
    moe: float  # Mixture-of-experts (domain) channel
    rag: float  # RAG-specific relevance channel


@dataclass(frozen=True)
class RAGConversionResult:
    """Result of converting RAG candidates to Fusion candidates."""
    candidates: Tuple[Any, ...]  # Fusion Candidate objects
    source_count: int
    converted_count: int
    phoneme_enhanced: bool
    router_applied: bool
    prefilter_applied: bool
    stats: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CHANNEL SCORE COMPUTATION
# =============================================================================


def compute_rag_channel_scores(
    entry: "CandidateEntry",
    query: str,
    domain: str = "generic",
) -> RAGChannelScores:
    """
    Compute channel scores from RAG CandidateEntry.

    Channel scores are computed based on:
    - RAG relevance score (primary signal)
    - Text complexity (for HRM/LCM balance)
    - Domain matching (for MoE)
    - Phoneme analysis (if available)

    Args:
        entry: RAG CandidateEntry with relevance score.
        query: Original query for context.
        domain: Domain classification.

    Returns:
        RAGChannelScores with computed channel values.
    """
    # Base RAG score from retrieval
    rag_score = entry.score

    # Compute text complexity for HRM/LCM balance
    text = entry.text
    word_count = len(text.split())
    avg_word_length = sum(len(w) for w in text.split()) / max(word_count, 1)

    # Higher complexity → higher HRM, lower LCM
    complexity = min(1.0, (avg_word_length - 4) / 6)  # Normalized 4-10 char range

    # HRM score: higher for complex, abstract content
    hrm_score = 0.4 + rag_score * 0.3 + complexity * 0.2

    # LCM score: higher for simple, practical content
    lcm_score = 0.5 + rag_score * 0.3 - complexity * 0.2

    # MoE score: domain matching
    moe_score = 0.4
    domain_keywords = {
        "medical": ["health", "disease", "treatment", "patient", "symptom"],
        "legal": ["law", "court", "contract", "legal", "rights"],
        "financial": ["money", "invest", "market", "finance", "stock"],
        "code": ["function", "code", "program", "api", "class"],
        "math": ["equation", "formula", "calculate", "number", "math"],
    }

    text_lower = text.lower()
    for dom, keywords in domain_keywords.items():
        if dom == domain.lower():
            for kw in keywords:
                if kw in text_lower:
                    moe_score += 0.1
                    break
            break

    # Apply phoneme analysis boost if available
    if HAS_RESONANCE:
        try:
            analysis = analyze_phrase(text[:200])  # Limit for performance
            if analysis.words:
                # Higher harmony → slightly boost all scores
                harmony = analysis.overall_harmony
                hrm_score = min(1.0, hrm_score * (1 + harmony * 0.1))
                lcm_score = min(1.0, lcm_score * (1 + harmony * 0.05))
        except Exception:
            pass

    return RAGChannelScores(
        hrm=max(0.0, min(1.0, hrm_score)),
        lcm=max(0.0, min(1.0, lcm_score)),
        moe=max(0.0, min(1.0, moe_score)),
        rag=rag_score,
    )


# =============================================================================
# RAG → FUSION CANDIDATE CONVERSION
# =============================================================================


def convert_rag_entry_to_candidate(
    entry: "CandidateEntry",
    query: str,
    domain: str = "generic",
    source_label: str = "rag",
) -> Optional[Any]:
    """
    Convert a RAG CandidateEntry to a Fusion Candidate.

    Args:
        entry: RAG CandidateEntry object.
        query: Original query text.
        domain: Domain classification.
        source_label: Label for candidate source.

    Returns:
        Fusion Candidate object, or None if conversion fails.
    """
    if not HAS_FUSION or Candidate is None:
        return None

    # Compute channel scores
    channel_scores = compute_rag_channel_scores(entry, query, domain)

    # Generate unique ID from content hash
    content_hash = hashlib.md5(entry.text.encode()).hexdigest()[:8]
    candidate_id = f"rag_{source_label}_{content_hash}"

    # Build candidate
    try:
        candidate = Candidate(
            id=candidate_id,
            text=entry.text,
            source=CandidateSource.RAG,
            channel_scores={
                "hrm": channel_scores.hrm,
                "lcm": channel_scores.lcm,
                "moe": channel_scores.moe,
                "rag": channel_scores.rag,
            },
            domain=domain,
            relevance_score=entry.score,
            confidence=entry.score * 0.9,  # Slightly reduced confidence
            metadata={
                "rag_source": entry.source,
                "rag_metadata": entry.metadata,
            },
        )
        return candidate
    except Exception:
        return None


def convert_rag_entries_to_candidates(
    entries: List["CandidateEntry"],
    query: str,
    domain: str = "generic",
    max_candidates: int = 10,
    apply_prefilter: bool = True,
    prefilter_threshold: float = 0.5,
) -> RAGConversionResult:
    """
    Convert a list of RAG CandidateEntries to Fusion Candidates.

    Applies optional hybrid optimizations:
    - Pre-filter by phoneme resonance (if enabled)
    - Semantic routing for channel score adjustment

    Args:
        entries: List of RAG CandidateEntry objects.
        query: Original query text.
        domain: Domain classification.
        max_candidates: Maximum candidates to return.
        apply_prefilter: Whether to apply phoneme pre-filter.
        prefilter_threshold: Threshold for phoneme pre-filter.

    Returns:
        RAGConversionResult with converted candidates and stats.
    """
    if not entries:
        return RAGConversionResult(
            candidates=(),
            source_count=0,
            converted_count=0,
            phoneme_enhanced=False,
            router_applied=False,
            prefilter_applied=False,
            stats={"error": "no_entries"},
        )

    source_count = len(entries)
    prefilter_applied = False
    router_applied = False
    phoneme_enhanced = HAS_RESONANCE

    # Apply phoneme pre-filter if available and enabled
    filtered_entries = entries
    if apply_prefilter and HAS_PREFILTER:
        try:
            prefilter = CandidatePreFilter(threshold=prefilter_threshold)
            candidate_texts = tuple(e.text for e in entries)
            passed_texts = prefilter.filter(candidate_texts, query)
            passed_set = set(passed_texts)
            filtered_entries = [e for e in entries if e.text in passed_set]
            prefilter_applied = True
        except Exception:
            filtered_entries = entries

    # Apply semantic router for context if available
    router_context = None
    if HAS_ROUTER:
        try:
            router = SemanticRouter()
            decision = router.route(query)
            router_context = {
                "model_type": decision.model_type.value,
                "dominant_layer": decision.dominant_layer,
                "confidence": decision.confidence,
            }
            router_applied = True
        except Exception:
            pass

    # Convert entries to candidates
    candidates = []
    for entry in filtered_entries[:max_candidates]:
        candidate = convert_rag_entry_to_candidate(
            entry, query, domain, entry.source
        )
        if candidate:
            candidates.append(candidate)

    # Compute stats
    stats = {
        "source_count": source_count,
        "after_prefilter": len(filtered_entries),
        "converted": len(candidates),
        "prefilter_reduction": 1 - (len(filtered_entries) / source_count) if source_count > 0 else 0,
        "router_context": router_context,
    }

    return RAGConversionResult(
        candidates=tuple(candidates),
        source_count=source_count,
        converted_count=len(candidates),
        phoneme_enhanced=phoneme_enhanced,
        router_applied=router_applied,
        prefilter_applied=prefilter_applied,
        stats=stats,
    )


# =============================================================================
# RAG RETRIEVAL WITH CONVERSION
# =============================================================================


def retrieve_and_convert(
    query: str,
    corpus_id: str,
    domain: str = "generic",
    top_k: int = 5,
    apply_prefilter: bool = True,
) -> RAGConversionResult:
    """
    Run RAG retrieval and convert results to Fusion candidates.

    This is the main integration function that combines RAG retrieval
    with candidate conversion and hybrid optimization.

    Args:
        query: Query text.
        corpus_id: Corpus to search.
        domain: Domain classification.
        top_k: Number of results to retrieve.
        apply_prefilter: Whether to apply phoneme pre-filter.

    Returns:
        RAGConversionResult with Fusion candidates.
    """
    if not HAS_RAG:
        return RAGConversionResult(
            candidates=(),
            source_count=0,
            converted_count=0,
            phoneme_enhanced=False,
            router_applied=False,
            prefilter_applied=False,
            stats={"error": "rag_module_unavailable"},
        )

    try:
        # Run RAG retrieval
        entries = run_rag(query, corpus_id, top_k=top_k)

        # Convert to Fusion candidates
        return convert_rag_entries_to_candidates(
            entries, query, domain, max_candidates=top_k,
            apply_prefilter=apply_prefilter,
        )
    except Exception as e:
        return RAGConversionResult(
            candidates=(),
            source_count=0,
            converted_count=0,
            phoneme_enhanced=False,
            router_applied=False,
            prefilter_applied=False,
            stats={"error": str(e)},
        )


def retrieve_multi_and_convert(
    query: str,
    corpus_ids: List[str],
    domain: str = "generic",
    top_k: int = 5,
    apply_prefilter: bool = True,
) -> RAGConversionResult:
    """
    Run multi-corpus RAG retrieval and convert results to Fusion candidates.

    Args:
        query: Query text.
        corpus_ids: List of corpus IDs to search.
        domain: Domain classification.
        top_k: Total number of results to retrieve.
        apply_prefilter: Whether to apply phoneme pre-filter.

    Returns:
        RAGConversionResult with Fusion candidates from all corpora.
    """
    if not HAS_RAG:
        return RAGConversionResult(
            candidates=(),
            source_count=0,
            converted_count=0,
            phoneme_enhanced=False,
            router_applied=False,
            prefilter_applied=False,
            stats={"error": "rag_module_unavailable"},
        )

    try:
        # Run multi-corpus RAG retrieval
        entries = run_rag_multi(query, corpus_ids, top_k=top_k)

        # Convert to Fusion candidates
        return convert_rag_entries_to_candidates(
            entries, query, domain, max_candidates=top_k,
            apply_prefilter=apply_prefilter,
        )
    except Exception as e:
        return RAGConversionResult(
            candidates=(),
            source_count=0,
            converted_count=0,
            phoneme_enhanced=False,
            router_applied=False,
            prefilter_applied=False,
            stats={"error": str(e)},
        )


# =============================================================================
# CORPUS MANAGEMENT
# =============================================================================


def get_available_corpora() -> List[str]:
    """Get list of available indexed corpora."""
    if not HAS_RAG:
        return []
    try:
        return list_indexed_corpora()
    except Exception:
        return []


# =============================================================================
# CACHING
# =============================================================================


@lru_cache(maxsize=128)
def _cached_retrieve(query: str, corpus_id: str, top_k: int) -> Tuple[str, ...]:
    """Cached RAG retrieval for repeated queries."""
    if not HAS_RAG:
        return ()
    try:
        entries = run_rag(query, corpus_id, top_k=top_k)
        return tuple(e.text for e in entries)
    except Exception:
        return ()


def clear_cache():
    """Clear the retrieval cache."""
    _cached_retrieve.cache_clear()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "HAS_RAG",
    "HAS_FUSION",
    "HAS_RESONANCE",
    "HAS_ROUTER",
    "HAS_PREFILTER",
    "RAGChannelScores",
    "RAGConversionResult",
    "compute_rag_channel_scores",
    "convert_rag_entry_to_candidate",
    "convert_rag_entries_to_candidates",
    "retrieve_and_convert",
    "retrieve_multi_and_convert",
    "get_available_corpora",
    "clear_cache",
]
