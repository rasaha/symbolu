"""
Consumer Engine
===============

Full capability engine combining STL + 768D embeddings + cascading LLM + AGI.

Architecture:
    Query
      ↓
    STL (10D) ──────────────┐
      ↓                     │
    Query Type Check        │ (PROBLEM vs INFORMATION)
      ↓                     │
    AGI Context (if PROBLEM)│ (Event tagging, 10D encoding, balance check)
      ↓                     │
    Confidence Check        │
      ↓                     ↓
    ┌─────────────┐    ┌─────────────┐
    │ HIGH (≥60%) │    │ LOW (<60%)  │
    └─────────────┘    └─────────────┘
          ↓                   ↓
    Skip 768D            768D Embedding
          ↓                   ↓
    7B Specialist       Combined Signal
          ↓                   ↓
    Response            Confidence Check
                             ↓
                   ┌─────────┴─────────┐
                   ↓                   ↓
               HIGH                  LOW
                   ↓                   ↓
               7B Model            175B Fallback
                   ↓                   ↓
               Response            Response
                             ↓
                   Cross-Domain Retrieval (AGI, PROBLEM only)
                             ↓
                   Persona Tracking (AGI)
                             ↓
                   Insights Available (AGI)

Cost Optimization Levers:
    - stl_confidence_threshold: Lower to skip 768D more (default: 0.6)
    - cascade_threshold: Lower to use 7B more (default: 0.6)
    - agi_for_problems_only: Only run AGI for PROBLEM queries (default: True)
    - vocabulary: Add custom terms to boost confidence
"""

import time
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, asdict

from symbolu_core.engine.base import BaseEngine, EngineResult, EngineCapability
from symbolu_core.engine.agi_context import AGIContext, AGILevel, AGISignal
from symbolu_core.engine.query_type import classify_query_type, QueryType
from symbolu_core.hybrid.router import SemanticRouter, ModelType, RoutingDecision
from symbolu_core.hybrid.vocabulary import CustomVocabulary
from symbolu_core.resonance import analyze_phrase
from agentic.ontology.backbone import InsightMode


@dataclass
class SemanticEmbedding:
    """768D semantic embedding result."""
    vector: Tuple[float, ...]
    confidence_boost: float
    tokens: List[str]


class SemanticEmbedder:
    """
    768D semantic embedding provider.

    This is a stub - replace with actual embedding model
    (e.g., sentence-transformers, OpenAI embeddings).
    """

    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim

    def embed(self, query: str) -> SemanticEmbedding:
        """
        Generate 768D embedding for query.

        Stub implementation - returns dummy values.
        Replace with actual embedding model.
        """
        # Stub: Use hash-based pseudo-embedding
        import hashlib
        hash_bytes = hashlib.sha256(query.encode()).digest()

        # Generate pseudo-random vector from hash
        vector = tuple(
            (b / 255.0) for b in (hash_bytes * 24)[:self.embedding_dim]
        )

        # Stub confidence boost
        confidence_boost = 0.1

        return SemanticEmbedding(
            vector=vector,
            confidence_boost=confidence_boost,
            tokens=query.split(),
        )


class LLMHandler:
    """
    Stub LLM handler for 7B/175B models.

    Replace with actual LLM API calls.
    """

    def __init__(self, model_name: str, model_size: str):
        self.model_name = model_name
        self.model_size = model_size

    def generate(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate response."""
        return f"[{self.model_name} ({self.model_size})] Response to: {query}"


class ConsumerEngine(BaseEngine):
    """
    Consumer Engine: STL + 768D + Cascading LLM + AGI.

    Example:
        engine = ConsumerEngine(persona_id="user_123")

        # Simple query - uses STL → 7B (skips 768D)
        result = engine.generate("Write a poem")
        print(result.model_used)  # "creative-7b"

        # Complex query - uses STL + 768D → 175B
        result = engine.generate("Analyze the socioeconomic implications...")
        print(result.model_used)  # "general-175b"

        # Check what was used
        print(result.stl_signal)       # STL routing details
        print(result.semantic_signal)  # 768D usage (if any)
        print(result.agi_signal)       # AGI capabilities (events, balance, cross-domain)

        # Get cross-domain insights
        insights = engine.get_insights()
    """

    # Default thresholds optimized for cost savings (based on benchmarks)
    DEFAULT_STL_CONFIDENCE_THRESHOLD = 0.6  # Skip 768D if STL confidence >= this
    DEFAULT_CASCADE_THRESHOLD = 0.6         # Use 7B if combined confidence >= this

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        stl_confidence_threshold: Optional[float] = None,
        cascade_threshold: Optional[float] = None,
        embedder: Optional[SemanticEmbedder] = None,
        persona_id: Optional[str] = None,
        enable_agi: bool = True,
        agi_for_problems_only: bool = True,
    ):
        """
        Initialize Consumer Engine.

        Args:
            vocabulary: Optional custom vocabulary for confidence boosting
            stl_confidence_threshold: STL confidence to skip 768D (default: 0.6)
                - Lower = more 768D skipping = more cost savings
                - Higher = more accuracy but more 768D compute
            cascade_threshold: Combined confidence to use 7B vs 175B (default: 0.6)
                - Lower = more 7B usage = more cost savings
                - Higher = more 175B fallback = better quality
            embedder: 768D embedder (stub if not provided)
            persona_id: User/session ID for AGI persona tracking
            enable_agi: Whether to enable AGI capabilities (default: True)
            agi_for_problems_only: Only run AGI for PROBLEM queries (default: True)
                - True = AGI skipped for INFORMATION queries = faster + cheaper
                - False = AGI always runs when enabled
        """
        self.router = SemanticRouter(
            vocabulary=vocabulary,
            confidence_threshold=0.3,  # Low threshold - we use our own cascading
        )
        self.vocabulary = vocabulary
        self.stl_confidence_threshold = (
            stl_confidence_threshold
            if stl_confidence_threshold is not None
            else self.DEFAULT_STL_CONFIDENCE_THRESHOLD
        )
        self.cascade_threshold = (
            cascade_threshold
            if cascade_threshold is not None
            else self.DEFAULT_CASCADE_THRESHOLD
        )

        # 768D embedder
        self.embedder = embedder or SemanticEmbedder()

        # AGI configuration
        self.persona_id = persona_id
        self.enable_agi = enable_agi
        self.agi_for_problems_only = agi_for_problems_only
        self.agi_context: Optional[AGIContext] = None
        if enable_agi:
            self.agi_context = AGIContext(
                persona_id=persona_id,
                level=AGILevel.FULL,
                auto_learn=True,
            )

        # Model handlers
        self.specialist_handlers: Dict[ModelType, LLMHandler] = {
            model_type: LLMHandler(f"{model_type.value}-7b", "7B")
            for model_type in ModelType
        }
        self.fallback_handler = LLMHandler("general-175b", "175B")

    @property
    def tier_name(self) -> str:
        return "consumer"

    @property
    def capabilities(self) -> Tuple[EngineCapability, ...]:
        return (
            EngineCapability.CLASSIFY,
            EngineCapability.GENERATE,
            EngineCapability.EMBED,
        )

    def classify(self, query: str) -> EngineResult:
        """Classify using STL + optional 768D augmentation."""
        start = time.perf_counter()

        # STL analysis
        decision = self.router.route(query)

        stl_signal = {
            "dominant_layer": decision.dominant_layer,
            "layer_scores": list(decision.layer_scores),
            "confidence": decision.confidence,
        }

        semantic_signal = None

        # If STL confidence is low, augment with 768D
        if decision.confidence < self.stl_confidence_threshold:
            embedding = self.embedder.embed(query)
            boosted_confidence = min(
                decision.confidence + embedding.confidence_boost,
                1.0,
            )
            semantic_signal = {
                "used": True,
                "confidence_boost": embedding.confidence_boost,
                "final_confidence": boosted_confidence,
            }
            final_confidence = boosted_confidence
        else:
            semantic_signal = {"used": False, "reason": "STL confidence sufficient"}
            final_confidence = decision.confidence

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            intent=decision.model_type.value,
            confidence=final_confidence,
            tier_used=self.tier_name,
            stl_signal=stl_signal,
            semantic_signal=semantic_signal,
            latency_ms=elapsed_ms,
        )

    def generate(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
    ) -> EngineResult:
        """
        Generate response using cascading STL → 768D → LLM + AGI.

        Flow:
            1. STL analysis (always, ~100μs)
            2. AGI processing (event tagging, 10D encoding, balance check)
            3. If high confidence: skip to 7B
            4. If low confidence: compute 768D, combine signals
            5. If combined high: use 7B
            6. If combined low: use 175B fallback
            7. Cross-domain retrieval and persona tracking (AGI)

        Args:
            query: Input query/prompt
            context: Optional generation context
            domain: Optional domain hint for AGI

        Returns:
            EngineResult with response and full audit trail including AGI signal
        """
        start = time.perf_counter()

        # Step 1: STL analysis (always runs)
        decision = self.router.route(query)
        stl_time = time.perf_counter() - start

        stl_signal = {
            "dominant_layer": decision.dominant_layer,
            "layer_scores": list(decision.layer_scores),
            "confidence": decision.confidence,
            "time_ms": stl_time * 1000,
        }

        # Step 1.5: Query type classification (for AGI gating)
        query_type_result = classify_query_type(query)
        is_problem_query = query_type_result.query_type == QueryType.PROBLEM

        # Step 2: AGI processing (if enabled AND appropriate for query type)
        agi_signal = None
        should_run_agi = (
            self.agi_context is not None
            and (not self.agi_for_problems_only or is_problem_query)
        )

        if should_run_agi:
            agi_start = time.perf_counter()
            query_ctx = self.agi_context.process_query(
                query=query,
                domain=domain,
                synthesize=False,  # Don't synthesize for basic generation
                max_matches=3,
            )
            agi_time = time.perf_counter() - agi_start

            signal = self.agi_context.to_signal()
            agi_signal = {
                "level": signal.level.value,
                "persona_id": signal.persona_id,
                "events_detected": signal.events_detected,
                "balance_score": signal.balance_score,
                "is_transferable": signal.is_transferable,
                "cross_domain_matches": signal.cross_domain_matches,
                "top_match_domain": signal.top_match_domain,
                "top_match_similarity": signal.top_match_similarity,
                "insights_available": signal.insights_available,
                "time_ms": agi_time * 1000,
                "query_type": query_type_result.query_type.value,
            }
        elif self.agi_context and self.agi_for_problems_only and not is_problem_query:
            # AGI skipped due to INFORMATION query
            agi_signal = {
                "skipped": True,
                "reason": "INFORMATION query - AGI disabled for cost savings",
                "query_type": query_type_result.query_type.value,
            }

        semantic_signal = None
        used_768d = False
        final_confidence = decision.confidence

        # Step 3: Check if we need 768D augmentation
        if decision.confidence >= self.stl_confidence_threshold:
            # HIGH STL confidence - skip 768D
            semantic_signal = {
                "used": False,
                "reason": "STL confidence sufficient",
                "stl_confidence": decision.confidence,
            }
        else:
            # LOW STL confidence - compute 768D
            embed_start = time.perf_counter()
            embedding = self.embedder.embed(query)
            embed_time = time.perf_counter() - embed_start

            used_768d = True
            final_confidence = min(
                decision.confidence + embedding.confidence_boost,
                1.0,
            )

            semantic_signal = {
                "used": True,
                "stl_confidence": decision.confidence,
                "boost": embedding.confidence_boost,
                "final_confidence": final_confidence,
                "time_ms": embed_time * 1000,
            }

        # Step 4: Select model based on final confidence
        if final_confidence >= self.cascade_threshold:
            # Use specialized 7B
            handler = self.specialist_handlers.get(
                decision.model_type,
                self.specialist_handlers[ModelType.GENERAL],
            )
            model_used = f"{decision.model_type.value}-7b"
        else:
            # Use 175B fallback
            handler = self.fallback_handler
            model_used = "general-175b"

        # Step 5: Generate response
        gen_start = time.perf_counter()

        generation_context = {
            "intent": decision.model_type.value,
            "confidence": final_confidence,
            "used_768d": used_768d,
            **(context or {}),
        }

        # Add AGI context for cross-domain reasoning
        if self.agi_context and agi_signal:
            generation_context["agi"] = {
                "events": agi_signal.get("events_detected", []),
                "cross_domain_matches": agi_signal.get("cross_domain_matches", 0),
                "top_match": agi_signal.get("top_match_domain"),
            }

        response = handler.generate(query, generation_context)

        gen_time = time.perf_counter() - gen_start
        total_time = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            intent=decision.model_type.value,
            confidence=final_confidence,
            response=response,
            tier_used=self.tier_name,
            model_used=model_used,
            stl_signal=stl_signal,
            semantic_signal=semantic_signal,
            agi_signal=agi_signal,
            latency_ms=total_time,
            metadata={
                "used_768d": used_768d,
                "generation_time_ms": gen_time * 1000,
                "cascade_decision": "7B" if model_used.endswith("-7b") else "175B",
            },
        )

    def embed(self, query: str) -> EngineResult:
        """
        Generate 768D embedding for a query.

        Args:
            query: Input text

        Returns:
            EngineResult with embedding in metadata
        """
        start = time.perf_counter()

        # Also get STL signal for comparison
        decision = self.router.route(query)
        embedding = self.embedder.embed(query)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EngineResult(
            success=True,
            tier_used=self.tier_name,
            stl_signal={
                "vector_10d": list(decision.query_analysis.words[0].vector)
                if decision.query_analysis.words else [],
                "dominant_layer": decision.dominant_layer,
            },
            semantic_signal={
                "vector_768d_sample": list(embedding.vector[:10]),  # First 10 dims
                "embedding_dim": len(embedding.vector),
            },
            latency_ms=elapsed_ms,
            metadata={
                "embedding_768d": list(embedding.vector),
            },
        )

    def get_cascade_stats(self, queries: List[str]) -> Dict[str, Any]:
        """
        Analyze cascade behavior for a batch of queries.

        Args:
            queries: List of queries to analyze

        Returns:
            Statistics about 768D usage and model selection
        """
        stats = {
            "total": len(queries),
            "skipped_768d": 0,
            "used_768d": 0,
            "used_7b": 0,
            "used_175b": 0,
        }

        for query in queries:
            decision = self.router.route(query)

            if decision.confidence >= self.stl_confidence_threshold:
                stats["skipped_768d"] += 1
                final_conf = decision.confidence
            else:
                stats["used_768d"] += 1
                embedding = self.embedder.embed(query)
                final_conf = decision.confidence + embedding.confidence_boost

            if final_conf >= self.cascade_threshold:
                stats["used_7b"] += 1
            else:
                stats["used_175b"] += 1

        # Calculate percentages
        total = stats["total"]
        return {
            **stats,
            "768d_skip_rate": stats["skipped_768d"] / total * 100,
            "7b_usage_rate": stats["used_7b"] / total * 100,
            "175b_usage_rate": stats["used_175b"] / total * 100,
        }

    # =========================================================================
    # AGI Capabilities
    # =========================================================================

    def get_insights(
        self,
        mode: InsightMode = InsightMode.NEW_POSSIBILITIES,
        current_domain: Optional[str] = None,
        max_insights: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized cross-domain insights.

        Based on persona query history, finds structurally similar
        patterns across domains the user has explored.

        Args:
            mode: Insight mode (RECENT_MEMORY, DOMAIN_RELATIVE, NEW_POSSIBILITIES)
            current_domain: Current domain context
            max_insights: Maximum insights to return

        Returns:
            List of insight dictionaries with:
                - type: Insight type (STRUCTURAL_MATCH, BRIDGE_OPPORTUNITY, etc.)
                - message: Human-readable insight
                - source_domain: Domain the insight came from
                - similarity: Structural similarity score
        """
        if not self.agi_context:
            return []

        insights = self.agi_context.get_insights(
            mode=mode,
            current_domain=current_domain,
            max_insights=max_insights,
        )

        return [
            {
                "type": insight.insight_type.value if hasattr(insight.insight_type, 'value') else str(insight.insight_type),
                "message": insight.message,
                "current_domain": insight.current_domain,
                "bridge_domain": insight.bridge_domain,
                "similarity": insight.structural_match.combined_score if insight.structural_match else 0.0,
            }
            for insight in insights
        ]

    def get_cross_domain_bridges(self) -> Dict[str, int]:
        """
        Get discovered cross-domain bridges for this persona.

        Bridges emerge from user query patterns - when a user
        explores similar structural patterns across different domains.

        Returns:
            Dict mapping "domain_a:domain_b" to bridge count
        """
        if not self.agi_context:
            return {}

        bridges = self.agi_context.get_cross_domain_bridges()
        return {
            f"{a}:{b}": count
            for (a, b), count in bridges.items()
        }

    def synthesize_reasoning(
        self,
        problem: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize cross-domain reasoning for a problem.

        Retrieves structurally similar experientials from multiple
        domains and synthesizes a unified reasoning approach.

        Args:
            problem: Problem description
            domain: Optional domain hint

        Returns:
            Dictionary with:
                - synthesis: Combined reasoning output
                - sources: List of source domains used
                - pattern: Detected structural pattern
                - recommendations: Action recommendations
        """
        if not self.agi_context:
            return {"error": "AGI not enabled"}

        query_ctx = self.agi_context.process_query(
            query=problem,
            domain=domain,
            synthesize=True,
            max_matches=5,
        )

        if not query_ctx.synthesis:
            return {
                "synthesis": None,
                "sources": [],
                "pattern": None,
                "recommendations": [],
            }

        return {
            "synthesis": query_ctx.synthesis.unified_insight,
            "sources": [r.source_domain for r in query_ctx.similar_experientials],
            "pattern": query_ctx.synthesis.detected_pattern,
            "recommendations": query_ctx.synthesis.recommendations,
            "balance_score": query_ctx.balance_score,
            "is_transferable": query_ctx.is_transferable,
        }

    def explain_last_query(self) -> str:
        """
        Get human-readable explanation of last query's balance.

        Returns explanation of how the query's 10D encoding
        maps to mirror pairs and whether insights are transferable.
        """
        if not self.agi_context:
            return "AGI not enabled"
        return self.agi_context.explain_query_balance()
