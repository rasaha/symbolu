"""
Consumer Engine
===============

Full capability engine combining STL + 768D embeddings + cascading LLM.

Architecture:
    Query
      ↓
    STL (10D) ──────────────┐
      ↓                     │
    Confidence Check        │
      ↓                     ↓
    ┌─────────────┐    ┌─────────────┐
    │ HIGH (≥80%) │    │ LOW (<80%)  │
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

Benefits:
    - 85% of queries skip 768D computation
    - Most queries use cost-effective 7B
    - Edge cases get full 175B capability
    - STL provides audit trail for all queries
"""

import time
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

from symbolu.engine.base import BaseEngine, EngineResult, EngineCapability
from symbolu.hybrid.router import SemanticRouter, ModelType, RoutingDecision
from symbolu.hybrid.vocabulary import CustomVocabulary
from symbolu.resonance import analyze_phrase


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
    Consumer Engine: STL + 768D + Cascading LLM.

    Example:
        engine = ConsumerEngine()

        # Simple query - uses STL → 7B (skips 768D)
        result = engine.generate("Write a poem")
        print(result.model_used)  # "creative-7b"

        # Complex query - uses STL + 768D → 175B
        result = engine.generate("Analyze the socioeconomic implications...")
        print(result.model_used)  # "general-175b"

        # Check what was used
        print(result.stl_signal)       # STL routing details
        print(result.semantic_signal)  # 768D usage (if any)
    """

    def __init__(
        self,
        vocabulary: Optional[CustomVocabulary] = None,
        stl_confidence_threshold: float = 0.8,
        cascade_threshold: float = 0.8,
        embedder: Optional[SemanticEmbedder] = None,
    ):
        """
        Initialize Consumer Engine.

        Args:
            vocabulary: Optional custom vocabulary
            stl_confidence_threshold: STL confidence to skip 768D
            cascade_threshold: Combined confidence to use 7B vs 175B
            embedder: 768D embedder (stub if not provided)
        """
        self.router = SemanticRouter(
            vocabulary=vocabulary,
            confidence_threshold=0.3,  # Low threshold - we use our own cascading
        )
        self.vocabulary = vocabulary
        self.stl_confidence_threshold = stl_confidence_threshold
        self.cascade_threshold = cascade_threshold

        # 768D embedder
        self.embedder = embedder or SemanticEmbedder()

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
    ) -> EngineResult:
        """
        Generate response using cascading STL → 768D → LLM.

        Flow:
            1. STL analysis (always, ~100μs)
            2. If high confidence: skip to 7B
            3. If low confidence: compute 768D, combine signals
            4. If combined high: use 7B
            5. If combined low: use 175B fallback

        Args:
            query: Input query/prompt
            context: Optional generation context

        Returns:
            EngineResult with response and full audit trail
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

        semantic_signal = None
        used_768d = False
        final_confidence = decision.confidence

        # Step 2: Check if we need 768D augmentation
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

        # Step 3: Select model based on final confidence
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

        # Step 4: Generate response
        gen_start = time.perf_counter()

        generation_context = {
            "intent": decision.model_type.value,
            "confidence": final_confidence,
            "used_768d": used_768d,
            **(context or {}),
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
