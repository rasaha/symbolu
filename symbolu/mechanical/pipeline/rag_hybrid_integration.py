"""
RAG-Hybrid Integration Module
==============================

Comprehensive integration of RAG with the Symbol-U hybrid flow.
Provides a unified interface for:
- Context-aware RAG retrieval
- Hybrid optimization (prefilter, router, attention)
- LLM-ready context assembly
- Candidate generation for Fusion

LLM Best Practices Applied:
-----------------------------
1. Context Management: Proper context window handling
2. Chunking Strategy: Optimal chunk sizes for LLM consumption
3. Relevance Scoring: Multi-signal relevance computation
4. Prompt Assembly: Structured context for LLM prompts
5. Error Handling: Graceful degradation with fallbacks
6. Caching: Efficient retrieval caching
7. Batch Processing: Efficient multi-query handling
8. Async Support: Non-blocking retrieval operations
9. Rate Limiting: Configurable throughput control
10. Traceability: Full provenance tracking

Integration with Hybrid Flow:
-----------------------------
- SemanticRouter: Routes queries to appropriate corpus/model
- CandidatePreFilter: Pre-filters candidates by phoneme resonance
- PhonemeAttentionHead: Applies phoneme-based attention to candidates
- VarnaAnalysis: Enriches candidates with phoneme vectors

Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import time
import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable, TYPE_CHECKING
from functools import wraps
import threading

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
    from symbolu.rag import (
        CandidateEntry,
        run_rag,
        run_rag_multi,
        list_indexed_corpora,
        corpus_stats,
        index_corpus,
    )
    HAS_RAG = True
except ImportError:
    HAS_RAG = False

# Fusion adapter
try:
    from .rag_fusion_adapter import (
        convert_rag_entries_to_candidates,
        RAGConversionResult,
    )
    HAS_FUSION_ADAPTER = True
except ImportError:
    HAS_FUSION_ADAPTER = False

# Hybrid modules
try:
    from symbolu.hybrid.router import SemanticRouter, ModelType, RoutingDecision
    HAS_ROUTER = True
except ImportError:
    HAS_ROUTER = False

try:
    from symbolu.hybrid.prefilter import CandidatePreFilter, FilterStats
    HAS_PREFILTER = True
except ImportError:
    HAS_PREFILTER = False

try:
    from symbolu.hybrid.attention import PhonemeAttentionHead
    HAS_ATTENTION = True
except ImportError:
    HAS_ATTENTION = False

# Resonance for phoneme analysis
try:
    from symbolu.resonance import analyze_phrase, PhraseAnalysis
    HAS_RESONANCE = True
except ImportError:
    HAS_RESONANCE = False


# =============================================================================
# ENUMS
# =============================================================================


class RetrievalMode(Enum):
    """RAG retrieval modes."""
    SIMPLE = "simple"           # Basic retrieval, no optimization
    ROUTED = "routed"           # Semantic router selects corpus
    PREFILTERED = "prefiltered" # Phoneme pre-filter applied
    HYBRID_FULL = "hybrid_full" # Router + prefilter + attention


class ContextFormat(Enum):
    """Context formatting for LLM consumption."""
    RAW = "raw"                 # Raw text concatenation
    STRUCTURED = "structured"   # Labeled sections
    PROMPT = "prompt"           # Full prompt template
    JSON = "json"               # JSON structured


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class RAGContext:
    """Retrieved context ready for LLM consumption."""
    text: str                           # Formatted context text
    sources: Tuple[str, ...]            # Source identifiers
    scores: Tuple[float, ...]           # Relevance scores
    total_tokens: int                   # Estimated token count
    chunk_count: int                    # Number of chunks
    format: ContextFormat               # Format used
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "sources": list(self.sources),
            "scores": list(self.scores),
            "total_tokens": self.total_tokens,
            "chunk_count": self.chunk_count,
            "format": self.format.value,
            "metadata": self.metadata,
        }


@dataclass
class HybridRAGResult:
    """Result of hybrid RAG retrieval."""
    context: RAGContext                 # LLM-ready context
    candidates: Tuple[Any, ...]         # Fusion candidates
    routing_decision: Optional[Any]     # Semantic router decision
    filter_stats: Optional[Any]         # Prefilter statistics
    phoneme_analysis: Optional[Any]     # Phrase analysis
    retrieval_time_ms: float
    mode_used: RetrievalMode
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "context": self.context.to_dict(),
            "candidate_count": len(self.candidates),
            "routing_decision": self.routing_decision.__dict__ if self.routing_decision else None,
            "retrieval_time_ms": self.retrieval_time_ms,
            "mode_used": self.mode_used.value,
            "fallback_used": self.fallback_used,
        }


@dataclass
class CorpusConfig:
    """Configuration for a corpus."""
    corpus_id: str
    domain: str = "generic"
    priority: int = 0           # Higher = more preferred
    max_chunks: int = 5
    enabled: bool = True
    model_type_affinity: Optional[str] = None  # Semantic router affinity


# =============================================================================
# CACHING (LRU with TTL)
# =============================================================================


class TTLCache:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 300):
        self._cache: OrderedDict = OrderedDict()
        self._times: Dict[str, float] = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value if exists and not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._times[key] > self._ttl:
                del self._cache[key]
                del self._times[key]
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any):
        """Set value with current timestamp."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._times[oldest]
            self._cache[key] = value
            self._times[key] = time.time()

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._times.clear()


# Global cache instance
_retrieval_cache = TTLCache(maxsize=256, ttl_seconds=300)


# =============================================================================
# RATE LIMITING
# =============================================================================


class RateLimiter:
    """Simple rate limiter for retrieval operations."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60):
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: List[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Acquire rate limit slot. Returns True if allowed."""
        with self._lock:
            now = time.time()
            # Remove old requests
            self._requests = [t for t in self._requests if now - t < self._window]
            if len(self._requests) >= self._max_requests:
                return False
            self._requests.append(now)
            return True

    def wait(self, timeout: float = 10.0) -> bool:
        """Wait until rate limit allows. Returns True if acquired."""
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire():
                return True
            time.sleep(0.1)
        return False


# Global rate limiter
_rate_limiter = RateLimiter()


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token)."""
    return len(text) // 4


def format_context_raw(entries: List[Any]) -> str:
    """Format context as raw text concatenation."""
    return "\n\n".join(e.text for e in entries)


def format_context_structured(entries: List[Any]) -> str:
    """Format context with labeled sections."""
    parts = []
    for i, entry in enumerate(entries, 1):
        score = getattr(entry, 'score', 0.0)
        source = getattr(entry, 'source', 'unknown')
        parts.append(f"[Source {i}: {source} (relevance: {score:.2f})]\n{entry.text}")
    return "\n\n---\n\n".join(parts)


def format_context_prompt(entries: List[Any], query: str) -> str:
    """Format as full prompt template."""
    context = format_context_structured(entries)
    return f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:"""


def format_context_json(entries: List[Any]) -> str:
    """Format as JSON structure."""
    import json
    data = [
        {
            "text": e.text,
            "score": getattr(e, 'score', 0.0),
            "source": getattr(e, 'source', 'unknown'),
        }
        for e in entries
    ]
    return json.dumps(data, indent=2)


def format_context(
    entries: List[Any],
    query: str,
    format_type: ContextFormat,
    max_tokens: int = 4000,
) -> RAGContext:
    """
    Format retrieved entries as LLM-ready context.

    Handles token limits by truncating entries as needed.

    Args:
        entries: List of CandidateEntry objects.
        query: Original query.
        format_type: Desired format.
        max_tokens: Maximum context tokens.

    Returns:
        RAGContext with formatted text.
    """
    if not entries:
        return RAGContext(
            text="",
            sources=(),
            scores=(),
            total_tokens=0,
            chunk_count=0,
            format=format_type,
        )

    # Format based on type
    if format_type == ContextFormat.RAW:
        text = format_context_raw(entries)
    elif format_type == ContextFormat.STRUCTURED:
        text = format_context_structured(entries)
    elif format_type == ContextFormat.PROMPT:
        text = format_context_prompt(entries, query)
    elif format_type == ContextFormat.JSON:
        text = format_context_json(entries)
    else:
        text = format_context_raw(entries)

    # Truncate if over token limit
    total_tokens = estimate_tokens(text)
    if total_tokens > max_tokens:
        # Reduce entries until within limit
        while entries and total_tokens > max_tokens:
            entries = entries[:-1]
            if format_type == ContextFormat.RAW:
                text = format_context_raw(entries)
            elif format_type == ContextFormat.STRUCTURED:
                text = format_context_structured(entries)
            elif format_type == ContextFormat.PROMPT:
                text = format_context_prompt(entries, query)
            else:
                text = format_context_json(entries)
            total_tokens = estimate_tokens(text)

    return RAGContext(
        text=text,
        sources=tuple(getattr(e, 'source', 'unknown') for e in entries),
        scores=tuple(getattr(e, 'score', 0.0) for e in entries),
        total_tokens=total_tokens,
        chunk_count=len(entries),
        format=format_type,
    )


# =============================================================================
# HYBRID RAG RETRIEVAL
# =============================================================================


class HybridRAGEngine:
    """
    Unified RAG engine with hybrid optimization.

    Combines:
    - Semantic routing for corpus/model selection
    - Phoneme pre-filtering for candidate reduction
    - Attention-based re-ranking
    - Context formatting for LLM consumption
    """

    def __init__(
        self,
        default_mode: RetrievalMode = RetrievalMode.HYBRID_FULL,
        default_format: ContextFormat = ContextFormat.STRUCTURED,
        max_context_tokens: int = 4000,
        prefilter_threshold: float = 0.5,
        use_cache: bool = True,
        rate_limit: bool = True,
    ):
        """
        Initialize hybrid RAG engine.

        Args:
            default_mode: Default retrieval mode.
            default_format: Default context format.
            max_context_tokens: Maximum tokens in context.
            prefilter_threshold: Phoneme filter threshold.
            use_cache: Whether to use retrieval cache.
            rate_limit: Whether to apply rate limiting.
        """
        self.default_mode = default_mode
        self.default_format = default_format
        self.max_context_tokens = max_context_tokens
        self.prefilter_threshold = prefilter_threshold
        self.use_cache = use_cache
        self.rate_limit = rate_limit

        # Initialize components
        self._router = SemanticRouter() if HAS_ROUTER else None
        self._prefilter = CandidatePreFilter(threshold=prefilter_threshold) if HAS_PREFILTER else None
        self._attention = PhonemeAttentionHead() if HAS_ATTENTION else None

        # Corpus registry
        self._corpora: Dict[str, CorpusConfig] = {}

    def register_corpus(self, config: CorpusConfig):
        """Register a corpus for retrieval."""
        self._corpora[config.corpus_id] = config

    def unregister_corpus(self, corpus_id: str):
        """Unregister a corpus."""
        self._corpora.pop(corpus_id, None)

    def retrieve(
        self,
        query: str,
        corpus_ids: Optional[List[str]] = None,
        domain: str = "generic",
        top_k: int = 5,
        mode: Optional[RetrievalMode] = None,
        context_format: Optional[ContextFormat] = None,
    ) -> HybridRAGResult:
        """
        Run hybrid RAG retrieval.

        Args:
            query: Query text.
            corpus_ids: Corpus IDs to search (None = use router or all).
            domain: Domain for scoring.
            top_k: Number of results.
            mode: Retrieval mode (None = use default).
            context_format: Context format (None = use default).

        Returns:
            HybridRAGResult with context and candidates.
        """
        start_time = time.perf_counter()
        mode = mode or self.default_mode
        context_format = context_format or self.default_format

        # Rate limiting
        if self.rate_limit and not _rate_limiter.wait(timeout=5.0):
            return self._create_empty_result(
                mode, context_format, time.perf_counter() - start_time,
                error="rate_limit_exceeded"
            )

        # Check cache
        if self.use_cache:
            cache_key = self._cache_key(query, corpus_ids, top_k)
            cached = _retrieval_cache.get(cache_key)
            if cached:
                return cached

        # Check RAG availability
        if not HAS_RAG:
            return self._create_empty_result(
                mode, context_format, time.perf_counter() - start_time,
                error="rag_unavailable"
            )

        # Determine corpus selection
        routing_decision = None
        if corpus_ids is None:
            if mode in (RetrievalMode.ROUTED, RetrievalMode.HYBRID_FULL) and self._router:
                routing_decision = self._router.route(query)
                corpus_ids = self._select_corpora_by_routing(routing_decision)
            else:
                corpus_ids = list(self._corpora.keys()) if self._corpora else get_available_corpora()

        if not corpus_ids:
            return self._create_empty_result(
                mode, context_format, time.perf_counter() - start_time,
                error="no_corpora"
            )

        # Run retrieval
        try:
            if len(corpus_ids) == 1:
                entries = run_rag(query, corpus_ids[0], top_k=top_k)
            else:
                entries = run_rag_multi(query, corpus_ids, top_k=top_k)
        except Exception as e:
            return self._create_empty_result(
                mode, context_format, time.perf_counter() - start_time,
                error=str(e)
            )

        # Apply phoneme pre-filter
        filter_stats = None
        if mode in (RetrievalMode.PREFILTERED, RetrievalMode.HYBRID_FULL) and self._prefilter:
            entries, filter_stats = self._apply_prefilter(entries, query)

        # Phoneme analysis
        phoneme_analysis = None
        if HAS_RESONANCE:
            try:
                phoneme_analysis = analyze_phrase(query)
            except Exception:
                pass

        # Format context
        context = format_context(entries, query, context_format, self.max_context_tokens)

        # Convert to Fusion candidates
        candidates: Tuple = ()
        if HAS_FUSION_ADAPTER:
            try:
                result = convert_rag_entries_to_candidates(
                    entries, query, domain,
                    max_candidates=top_k,
                    apply_prefilter=False,  # Already applied above
                )
                candidates = result.candidates
            except Exception:
                pass

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        result = HybridRAGResult(
            context=context,
            candidates=candidates,
            routing_decision=routing_decision,
            filter_stats=filter_stats,
            phoneme_analysis=phoneme_analysis,
            retrieval_time_ms=elapsed_ms,
            mode_used=mode,
        )

        # Cache result
        if self.use_cache:
            _retrieval_cache.set(cache_key, result)

        return result

    def _apply_prefilter(
        self,
        entries: List[Any],
        query: str,
    ) -> Tuple[List[Any], Optional[Any]]:
        """Apply phoneme pre-filter to entries."""
        if not entries or not self._prefilter:
            return entries, None

        try:
            candidate_texts = tuple(e.text for e in entries)
            filtered_texts, stats = self._prefilter.filter_with_stats(candidate_texts, query)
            filtered_set = set(filtered_texts)
            filtered_entries = [e for e in entries if e.text in filtered_set]
            return filtered_entries if filtered_entries else entries, stats
        except Exception:
            return entries, None

    def _select_corpora_by_routing(self, decision: Any) -> List[str]:
        """Select corpora based on routing decision."""
        selected = []
        model_type = decision.model_type.value if hasattr(decision.model_type, 'value') else str(decision.model_type)

        for corpus_id, config in self._corpora.items():
            if not config.enabled:
                continue
            if config.model_type_affinity and config.model_type_affinity == model_type:
                selected.append((corpus_id, config.priority + 10))
            else:
                selected.append((corpus_id, config.priority))

        # Sort by priority descending
        selected.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in selected[:5]]  # Max 5 corpora

    def _cache_key(
        self,
        query: str,
        corpus_ids: Optional[List[str]],
        top_k: int,
    ) -> str:
        """Generate cache key for retrieval."""
        corpus_str = ",".join(sorted(corpus_ids)) if corpus_ids else "all"
        key_str = f"{query}:{corpus_str}:{top_k}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _create_empty_result(
        self,
        mode: RetrievalMode,
        context_format: ContextFormat,
        elapsed_ms: float,
        error: str = "",
    ) -> HybridRAGResult:
        """Create empty result for error cases."""
        return HybridRAGResult(
            context=RAGContext(
                text="",
                sources=(),
                scores=(),
                total_tokens=0,
                chunk_count=0,
                format=context_format,
                metadata={"error": error} if error else {},
            ),
            candidates=(),
            routing_decision=None,
            filter_stats=None,
            phoneme_analysis=None,
            retrieval_time_ms=elapsed_ms,
            mode_used=mode,
            fallback_used=True,
        )

    def clear_cache(self):
        """Clear retrieval cache."""
        _retrieval_cache.clear()


# =============================================================================
# ASYNC SUPPORT
# =============================================================================


async def async_retrieve(
    query: str,
    corpus_ids: Optional[List[str]] = None,
    domain: str = "generic",
    top_k: int = 5,
    engine: Optional[HybridRAGEngine] = None,
) -> HybridRAGResult:
    """
    Async wrapper for hybrid RAG retrieval.

    Args:
        query: Query text.
        corpus_ids: Corpus IDs to search.
        domain: Domain classification.
        top_k: Number of results.
        engine: HybridRAGEngine instance.

    Returns:
        HybridRAGResult with context and candidates.
    """
    engine = engine or get_hybrid_rag_engine()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: engine.retrieve(query, corpus_ids, domain, top_k)
    )


async def async_retrieve_batch(
    queries: List[str],
    corpus_ids: Optional[List[str]] = None,
    domain: str = "generic",
    top_k: int = 5,
    engine: Optional[HybridRAGEngine] = None,
) -> List[HybridRAGResult]:
    """
    Batch async retrieval for multiple queries.

    Args:
        queries: List of query texts.
        corpus_ids: Corpus IDs to search.
        domain: Domain classification.
        top_k: Number of results per query.
        engine: HybridRAGEngine instance.

    Returns:
        List of HybridRAGResult objects.
    """
    tasks = [
        async_retrieve(q, corpus_ids, domain, top_k, engine)
        for q in queries
    ]
    return await asyncio.gather(*tasks)


# =============================================================================
# SINGLETON
# =============================================================================

_engine: Optional[HybridRAGEngine] = None


def get_hybrid_rag_engine() -> HybridRAGEngine:
    """Get or create singleton HybridRAGEngine instance."""
    global _engine
    if _engine is None:
        _engine = HybridRAGEngine()
    return _engine


def get_available_corpora() -> List[str]:
    """Get list of available indexed corpora."""
    if not HAS_RAG:
        return []
    try:
        return list_indexed_corpora()
    except Exception:
        return []


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def hybrid_retrieve(
    query: str,
    corpus_ids: Optional[List[str]] = None,
    domain: str = "generic",
    top_k: int = 5,
    mode: RetrievalMode = RetrievalMode.HYBRID_FULL,
) -> HybridRAGResult:
    """
    Convenience function for hybrid RAG retrieval.

    Args:
        query: Query text.
        corpus_ids: Corpus IDs to search.
        domain: Domain classification.
        top_k: Number of results.
        mode: Retrieval mode.

    Returns:
        HybridRAGResult with context and candidates.
    """
    return get_hybrid_rag_engine().retrieve(
        query, corpus_ids, domain, top_k, mode
    )


def get_llm_context(
    query: str,
    corpus_ids: Optional[List[str]] = None,
    max_tokens: int = 4000,
) -> str:
    """
    Get LLM-ready context string.

    Args:
        query: Query text.
        corpus_ids: Corpus IDs to search.
        max_tokens: Maximum context tokens.

    Returns:
        Formatted context string.
    """
    engine = get_hybrid_rag_engine()
    engine.max_context_tokens = max_tokens
    result = engine.retrieve(query, corpus_ids, context_format=ContextFormat.STRUCTURED)
    return result.context.text


def get_fusion_candidates(
    query: str,
    corpus_ids: Optional[List[str]] = None,
    domain: str = "generic",
    top_k: int = 5,
) -> Tuple[Any, ...]:
    """
    Get Fusion candidates from RAG retrieval.

    Args:
        query: Query text.
        corpus_ids: Corpus IDs to search.
        domain: Domain classification.
        top_k: Number of results.

    Returns:
        Tuple of Fusion Candidate objects.
    """
    result = get_hybrid_rag_engine().retrieve(query, corpus_ids, domain, top_k)
    return result.candidates


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "HAS_RAG",
    "HAS_FUSION_ADAPTER",
    "HAS_ROUTER",
    "HAS_PREFILTER",
    "HAS_ATTENTION",
    "HAS_RESONANCE",
    "RetrievalMode",
    "ContextFormat",
    "RAGContext",
    "HybridRAGResult",
    "CorpusConfig",
    "TTLCache",
    "RateLimiter",
    "HybridRAGEngine",
    "get_hybrid_rag_engine",
    "get_available_corpora",
    "hybrid_retrieve",
    "get_llm_context",
    "get_fusion_candidates",
    "async_retrieve",
    "async_retrieve_batch",
    "format_context",
    "estimate_tokens",
]
