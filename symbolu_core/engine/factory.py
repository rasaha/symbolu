"""
Engine Factory
==============

Factory for creating engine instances by tier.

Cost Optimization Guide:
    1. Use tiered routing: route_query_to_tier() for automatic tier selection
    2. Configure thresholds: lower thresholds = more cost savings
    3. Use custom vocabulary: boost confidence for domain terms
    4. Enable agi_for_problems_only: skip AGI for information queries

Preset Configurations:
    - COST_OPTIMIZED: Maximum savings (aggressive thresholds)
    - BALANCED: Good balance of cost and quality
    - QUALITY_FIRST: Maximum quality (conservative thresholds)
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from symbolu_core.engine.base import BaseEngine, EngineResult
from symbolu_core.engine.enterprise_search import EnterpriseSearchEngine
from symbolu_core.engine.enterprise_chat import EnterpriseChatEngine
from symbolu_core.engine.consumer import ConsumerEngine
from symbolu_core.engine.query_type import classify_query_type, QueryType
from symbolu_core.hybrid.vocabulary import CustomVocabulary, VocabularyLoader


@dataclass
class CostPreset:
    """Preset configuration for cost optimization."""
    stl_confidence_threshold: float
    cascade_threshold: float
    agi_for_problems_only: bool
    description: str


# Preset configurations
COST_PRESETS = {
    "cost_optimized": CostPreset(
        stl_confidence_threshold=0.5,
        cascade_threshold=0.5,
        agi_for_problems_only=True,
        description="Maximum cost savings: ~70% 768D skip, ~85% 7B usage",
    ),
    "balanced": CostPreset(
        stl_confidence_threshold=0.6,
        cascade_threshold=0.6,
        agi_for_problems_only=True,
        description="Balanced: ~50% 768D skip, ~75% 7B usage",
    ),
    "quality_first": CostPreset(
        stl_confidence_threshold=0.8,
        cascade_threshold=0.8,
        agi_for_problems_only=False,
        description="Quality first: Full 768D, ~60% 7B usage, full AGI",
    ),
}


class EngineTier(Enum):
    """Available engine tiers."""

    # Enterprise Tier 1: Pure STL for search/classification
    ENTERPRISE_SEARCH = "enterprise_search"

    # Enterprise Tier 2: STL + 7B for specialized chat
    ENTERPRISE_CHAT = "enterprise_chat"

    # Consumer: STL + 768D + cascading LLM
    CONSUMER = "consumer"


def create_engine(
    tier: EngineTier = EngineTier.ENTERPRISE_SEARCH,
    vocabulary: Optional[CustomVocabulary] = None,
    vocabulary_file: Optional[str] = None,
    persona_id: Optional[str] = None,
    enable_agi: bool = True,
    preset: Optional[str] = None,
    **kwargs: Any,
) -> BaseEngine:
    """
    Create an engine instance for the specified tier.

    Args:
        tier: Which engine tier to create
        vocabulary: Pre-loaded CustomVocabulary
        vocabulary_file: Path to vocabulary JSON file
        persona_id: User/session ID for AGI persona tracking
        enable_agi: Whether to enable AGI capabilities
        preset: Cost preset ("cost_optimized", "balanced", "quality_first")
        **kwargs: Tier-specific configuration:
            - stl_confidence_threshold: Skip 768D threshold (default: 0.6)
            - cascade_threshold: 7B vs 175B threshold (default: 0.6)
            - agi_for_problems_only: Only run AGI for PROBLEM queries

    Returns:
        Configured engine instance

    Examples:
        # Enterprise Tier 1: Pure STL (no AGI)
        engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
        result = engine.classify("Deploy the cluster")

        # Enterprise Tier 2: STL + 7B + Light AGI
        engine = create_engine(
            tier=EngineTier.ENTERPRISE_CHAT,
            persona_id="user_123"
        )
        result = engine.generate("Explain quantum physics")

        # Consumer with cost optimization preset
        engine = create_engine(
            tier=EngineTier.CONSUMER,
            preset="cost_optimized",
            persona_id="user_123"
        )

        # Consumer with custom thresholds
        engine = create_engine(
            tier=EngineTier.CONSUMER,
            stl_confidence_threshold=0.5,  # More 768D skipping
            cascade_threshold=0.5,         # More 7B usage
            agi_for_problems_only=True,    # Skip AGI for info queries
        )

        # With custom vocabulary
        engine = create_engine(
            tier=EngineTier.ENTERPRISE_SEARCH,
            vocabulary_file="company_terms.json"
        )
    """
    # Load vocabulary if file path provided
    if vocabulary_file and not vocabulary:
        vocabulary = VocabularyLoader.from_file(vocabulary_file)

    # Apply preset if specified
    if preset and preset in COST_PRESETS:
        preset_config = COST_PRESETS[preset]
        kwargs.setdefault("stl_confidence_threshold", preset_config.stl_confidence_threshold)
        kwargs.setdefault("cascade_threshold", preset_config.cascade_threshold)
        kwargs.setdefault("agi_for_problems_only", preset_config.agi_for_problems_only)

    # Create appropriate engine
    if tier == EngineTier.ENTERPRISE_SEARCH:
        # No AGI for Enterprise Search
        return EnterpriseSearchEngine(
            vocabulary=vocabulary,
            confidence_threshold=kwargs.get("confidence_threshold", 0.3),
        )

    elif tier == EngineTier.ENTERPRISE_CHAT:
        # Light AGI for Enterprise Chat
        return EnterpriseChatEngine(
            vocabulary=vocabulary,
            confidence_threshold=kwargs.get("confidence_threshold", 0.3),
            model_handlers=kwargs.get("model_handlers"),
            model_names=kwargs.get("model_names"),
            persona_id=persona_id,
            enable_agi=enable_agi,
        )

    elif tier == EngineTier.CONSUMER:
        # Full AGI for Consumer (with configurable thresholds)
        return ConsumerEngine(
            vocabulary=vocabulary,
            stl_confidence_threshold=kwargs.get("stl_confidence_threshold"),
            cascade_threshold=kwargs.get("cascade_threshold"),
            embedder=kwargs.get("embedder"),
            persona_id=persona_id,
            enable_agi=enable_agi,
            agi_for_problems_only=kwargs.get("agi_for_problems_only", True),
        )

    else:
        raise ValueError(f"Unknown tier: {tier}")


# Convenience aliases
def create_search_engine(**kwargs: Any) -> EnterpriseSearchEngine:
    """Create Enterprise Search Engine (Tier 1)."""
    return create_engine(tier=EngineTier.ENTERPRISE_SEARCH, **kwargs)


def create_chat_engine(**kwargs: Any) -> EnterpriseChatEngine:
    """Create Enterprise Chat Engine (Tier 2)."""
    return create_engine(tier=EngineTier.ENTERPRISE_CHAT, **kwargs)


def create_consumer_engine(**kwargs: Any) -> ConsumerEngine:
    """Create Consumer Engine."""
    return create_engine(tier=EngineTier.CONSUMER, **kwargs)


# =============================================================================
# Smart Routing Helpers
# =============================================================================

class SmartRouter:
    """
    Automatically routes queries to the most cost-effective tier.

    Routes based on query complexity and type:
        - Classification-only → Enterprise Search (free)
        - Simple generation → Enterprise Chat (low cost)
        - Complex/problem queries → Consumer/Cascade (full capability)

    Example:
        router = SmartRouter(persona_id="user_123")

        # Automatically picks the right tier
        result = router.process("What is quantum physics?")  # → Search or Chat
        result = router.process("My startup is failing, help")  # → Consumer

        # Get routing stats
        print(router.get_stats())
    """

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        persona_id: Optional[str] = None,
        preset: str = "balanced",
        classification_only_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize SmartRouter.

        Args:
            vocabulary: Custom vocabulary for all tiers
            persona_id: User ID for persona tracking
            preset: Cost preset for Consumer tier
            classification_only_patterns: Patterns that only need classification
        """
        self.vocabulary = vocabulary
        self.persona_id = persona_id
        self.preset = preset

        # Default patterns for classification-only
        self.classification_patterns = classification_only_patterns or [
            "classify",
            "categorize",
            "what type",
            "which category",
            "route this",
            "tag this",
        ]

        # Create engines (lazy - only create when needed)
        self._search_engine: Optional[EnterpriseSearchEngine] = None
        self._chat_engine: Optional[EnterpriseChatEngine] = None
        self._consumer_engine: Optional[ConsumerEngine] = None

        # Stats tracking
        self._stats = {
            "total": 0,
            "search": 0,
            "chat": 0,
            "consumer": 0,
        }

    @property
    def search_engine(self) -> EnterpriseSearchEngine:
        """Lazy-load search engine."""
        if self._search_engine is None:
            self._search_engine = create_search_engine(vocabulary=self.vocabulary)
        return self._search_engine

    @property
    def chat_engine(self) -> EnterpriseChatEngine:
        """Lazy-load chat engine."""
        if self._chat_engine is None:
            self._chat_engine = create_chat_engine(
                vocabulary=self.vocabulary,
                persona_id=self.persona_id,
            )
        return self._chat_engine

    @property
    def consumer_engine(self) -> ConsumerEngine:
        """Lazy-load consumer engine."""
        if self._consumer_engine is None:
            self._consumer_engine = create_consumer_engine(
                vocabulary=self.vocabulary,
                persona_id=self.persona_id,
                preset=self.preset,
            )
        return self._consumer_engine

    def route_query(self, query: str) -> Tuple[EngineTier, str]:
        """
        Determine the best tier for a query.

        Returns:
            Tuple of (tier, reason)
        """
        query_lower = query.lower()

        # Check for classification-only patterns
        for pattern in self.classification_patterns:
            if pattern in query_lower:
                return EngineTier.ENTERPRISE_SEARCH, "classification pattern detected"

        # Check query type
        query_type_result = classify_query_type(query)

        if query_type_result.query_type == QueryType.PROBLEM:
            # Problem queries benefit from full capability + AGI
            return EngineTier.CONSUMER, "PROBLEM query - needs cross-domain reasoning"

        # For information queries, use chat for generation
        # Use search only if very simple/short
        if len(query.split()) <= 5 and query_type_result.confidence > 0.5:
            return EngineTier.ENTERPRISE_CHAT, "simple INFORMATION query"

        return EngineTier.ENTERPRISE_CHAT, "INFORMATION query - chat sufficient"

    def process(
        self,
        query: str,
        generate: bool = True,
        domain: Optional[str] = None,
    ) -> EngineResult:
        """
        Process query using the most cost-effective tier.

        Args:
            query: Input query
            generate: Whether to generate response (vs classify only)
            domain: Optional domain hint

        Returns:
            EngineResult from the selected tier
        """
        tier, reason = self.route_query(query)

        self._stats["total"] += 1

        if tier == EngineTier.ENTERPRISE_SEARCH:
            self._stats["search"] += 1
            result = self.search_engine.classify(query)
        elif tier == EngineTier.ENTERPRISE_CHAT:
            self._stats["chat"] += 1
            if generate:
                result = self.chat_engine.generate(query)
            else:
                result = self.chat_engine.classify(query)
        else:  # CONSUMER
            self._stats["consumer"] += 1
            if generate:
                result = self.consumer_engine.generate(query, domain=domain)
            else:
                result = self.consumer_engine.classify(query)

        # Add routing info to metadata
        if result.metadata is None:
            result.metadata = {}
        result.metadata["smart_routing"] = {
            "selected_tier": tier.value,
            "reason": reason,
        }

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total = self._stats["total"] or 1  # Avoid division by zero
        return {
            **self._stats,
            "search_pct": self._stats["search"] / total * 100,
            "chat_pct": self._stats["chat"] / total * 100,
            "consumer_pct": self._stats["consumer"] / total * 100,
            "estimated_cost_ratio": (
                self._stats["search"] * 0
                + self._stats["chat"] * 0.001
                + self._stats["consumer"] * 0.013
            ) / total if total > 0 else 0,
        }


# =============================================================================
# Batch Processing for Low-Confidence Queries
# =============================================================================

@dataclass
class BatchResult:
    """Result of batch processing."""
    processed: int
    deferred: int
    results: List[EngineResult]
    deferred_queries: List[str]


class BatchProcessor:
    """
    Process queries in batches, deferring low-confidence ones.

    Low-confidence queries can be:
        - Processed later in batch (lower cost)
        - Flagged for human review
        - Processed with 175B in a batch API call

    Example:
        processor = BatchProcessor(confidence_threshold=0.5)

        # Process a batch
        result = processor.process_batch([
            "Write a poem",           # High confidence → immediate
            "Analyze the xyz...",     # Low confidence → deferred
        ])

        # Handle deferred separately
        for query in result.deferred_queries:
            # Send to batch API or human review
            pass
    """

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        confidence_threshold: float = 0.5,
        preset: str = "cost_optimized",
    ):
        """
        Initialize BatchProcessor.

        Args:
            vocabulary: Custom vocabulary
            confidence_threshold: Queries below this are deferred
            preset: Cost preset for the engine
        """
        self.vocabulary = vocabulary
        self.confidence_threshold = confidence_threshold
        self.engine = create_consumer_engine(
            vocabulary=vocabulary,
            preset=preset,
        )

    def process_batch(
        self,
        queries: List[str],
        defer_low_confidence: bool = True,
    ) -> BatchResult:
        """
        Process a batch of queries.

        Args:
            queries: List of queries to process
            defer_low_confidence: Whether to defer low-confidence queries

        Returns:
            BatchResult with processed and deferred queries
        """
        results = []
        deferred = []

        for query in queries:
            # First, classify to check confidence
            decision = self.engine.router.route(query)

            if defer_low_confidence and decision.confidence < self.confidence_threshold:
                deferred.append(query)
            else:
                result = self.engine.generate(query)
                results.append(result)

        return BatchResult(
            processed=len(results),
            deferred=len(deferred),
            results=results,
            deferred_queries=deferred,
        )

    def process_deferred(
        self,
        deferred_queries: List[str],
        use_175b: bool = True,
    ) -> List[EngineResult]:
        """
        Process deferred queries (typically with 175B).

        Args:
            deferred_queries: Previously deferred queries
            use_175b: Force use of 175B model

        Returns:
            List of results
        """
        results = []

        # Create a quality-first engine for deferred queries
        quality_engine = create_consumer_engine(
            vocabulary=self.vocabulary,
            preset="quality_first",
        )

        for query in deferred_queries:
            result = quality_engine.generate(query)
            results.append(result)

        return results
