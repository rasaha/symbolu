#!/usr/bin/env python3
"""
RAG Query Engine - Ontological Retrieval Coordinator
=====================================================

Coordinates queries between the presentation layer and RAG storage backends.
This is the central engine that:
1. Analyzes user queries with UnifiedOntologicalEngineV2
2. Retrieves similar documents from Vector DB (156D similarity)
3. Fetches relationship context from Graph DB
4. Combines results for RAG-augmented responses

Architecture:
─────────────────────────────────────────────────────────────────────
                    Presentation Layer (API/CLI)
                              │
                              ▼
                    ┌─────────────────────┐
                    │   RAGQueryEngine    │  ← THIS MODULE
                    │   (Coordinator)     │
                    └─────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
  │  Ontological  │   │  Vector DB    │   │   Graph DB    │
  │  Engine V2    │   │  (Pinecone)   │   │   (Neo4j)     │
  │  (Analysis)   │   │  (Similarity) │   │  (Relations)  │
  └───────────────┘   └───────────────┘   └───────────────┘
─────────────────────────────────────────────────────────────────────

Usage:
    from symbolu.ontological.rag_query import RAGQueryEngine

    # Initialize with trained model
    engine = RAGQueryEngine()
    engine.load_model("checkpoints/unified_v2_best.pt")
    engine.load_knowledge_base("data/rag/knowledge_base.json")

    # Query with ontological context
    result = engine.query("What is consciousness?")
    print(result["similar_documents"])
    print(result["ontological_context"])
    print(result["relationship_context"])

    # For LLM augmentation
    context = engine.get_rag_context("What is consciousness?", top_k=5)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

# Check for PyTorch
try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX
from symbolu.ontological.bhava_relationships import (
    BHAVA_SIGNIFICANCES,
    ASPECT_STRENGTH_MATRIX,
    get_relationship_meaning,
)


@dataclass
class QueryResult:
    """Result from a RAG query with ontological context."""

    # Query analysis
    query_text: str
    query_layer: str
    query_confidence: float
    query_coherence: float
    query_vector: List[float]  # 156D

    # Similar documents
    similar_documents: List[Dict[str, Any]] = field(default_factory=list)

    # Relationship context
    query_relationships: List[Dict[str, Any]] = field(default_factory=list)
    relevant_bhavas: List[Dict[str, Any]] = field(default_factory=list)

    # Combined context for LLM
    rag_context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_text": self.query_text,
            "query_layer": self.query_layer,
            "query_confidence": self.query_confidence,
            "query_coherence": self.query_coherence,
            "similar_documents": self.similar_documents,
            "query_relationships": self.query_relationships,
            "relevant_bhavas": self.relevant_bhavas,
            "rag_context": self.rag_context,
        }


class RAGQueryEngine:
    """
    Central coordinator for ontological RAG queries.

    Combines:
    - UnifiedOntologicalEngineV2 for query analysis
    - Vector similarity search for document retrieval
    - Graph traversal for relationship context
    """

    def __init__(self):
        self.engine = None
        self.knowledge_base: Dict[str, Any] = {}
        self.documents: List[Dict[str, Any]] = []
        self.relationships: List[Dict[str, Any]] = []
        self.drishti_patterns: List[Dict[str, Any]] = []

        # Vector index (simple in-memory for now)
        self._doc_vectors: Optional[np.ndarray] = None
        self._doc_ids: List[str] = []

    def load_model(self, model_path: str = "checkpoints/unified_v2_best.pt") -> bool:
        """Load trained ontological engine."""
        if not PYTORCH_AVAILABLE:
            print("PyTorch not available")
            return False

        from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2

        model_file = Path(model_path)
        if not model_file.exists():
            print(f"Model not found at: {model_file}")
            return False

        self.engine = UnifiedOntologicalEngineV2()
        self.engine.load_state_dict(torch.load(model_file, map_location="cpu"))
        self.engine.eval()
        print(f"Loaded model from: {model_file}")
        return True

    def load_knowledge_base(self, kb_path: str = "data/rag/knowledge_base.json") -> bool:
        """Load knowledge base with documents and relationships."""
        kb_file = Path(kb_path)
        if not kb_file.exists():
            print(f"Knowledge base not found at: {kb_file}")
            return False

        with open(kb_file, "r", encoding="utf-8") as f:
            self.knowledge_base = json.load(f)

        # Extract components
        self.documents = self.knowledge_base.get("documents", [])
        self.relationships = self.knowledge_base.get("relationships", [])
        self.drishti_patterns = self.knowledge_base.get("drishti_patterns", [])

        # Build vector index
        self._build_vector_index()

        print(f"Loaded knowledge base: {len(self.documents)} documents, "
              f"{len(self.relationships)} relationships")
        return True

    def _build_vector_index(self):
        """Build in-memory vector index for similarity search."""
        if not self.documents:
            return

        vectors = []
        doc_ids = []

        for doc in self.documents:
            full_vector = doc.get("full_vector", [])
            if full_vector and len(full_vector) == 156:
                vectors.append(full_vector)
                doc_ids.append(doc.get("doc_id", ""))

        if vectors:
            self._doc_vectors = np.array(vectors)
            self._doc_ids = doc_ids
            print(f"Built vector index: {len(vectors)} vectors × 156D")

    def _cosine_similarity(self, query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and all documents."""
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
        doc_norms = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-8)
        return np.dot(doc_norms, query_norm)

    def analyze_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze query text with ontological engine."""
        if self.engine is None:
            # Return minimal analysis without model
            return {
                "dominant_layer": "UNKNOWN",
                "confidence": 0.0,
                "coherence": 0.0,
                "ontological_vector": [0.0] * 12,
                "bhava_vector": [0.0] * 144,
                "full_vector": [0.0] * 156,
                "strongest_relationships": [],
            }

        return self.engine.analyze(query_text)

    def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity."""
        if self._doc_vectors is None or len(self._doc_vectors) == 0:
            return []

        query_vec = np.array(query_vector)
        similarities = self._cosine_similarity(query_vec, self._doc_vectors)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            sim = float(similarities[idx])
            if sim >= min_similarity:
                doc_id = self._doc_ids[idx]
                doc = next((d for d in self.documents if d.get("doc_id") == doc_id), None)
                if doc:
                    results.append({
                        "doc_id": doc_id,
                        "text": doc.get("text", ""),
                        "similarity": sim,
                        "dominant_layer": doc.get("dominant_layer", ""),
                        "confidence": doc.get("confidence", 0),
                        "coherence": doc.get("coherence", 0),
                    })

        return results

    def get_relationship_context(
        self,
        dominant_layer: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get relevant relationships for a layer from the graph."""
        relevant = []

        for rel in self.relationships:
            # Relationships FROM this layer
            if rel.get("from_layer") == dominant_layer:
                relevant.append({
                    "direction": "outgoing",
                    "from_layer": rel.get("from_layer"),
                    "to_layer": rel.get("to_layer"),
                    "bhava_name": rel.get("bhava_name"),
                    "pattern_type": rel.get("pattern_type"),
                    "interpretation": rel.get("interpretation"),
                    "strength": rel.get("strength", 0),
                })
            # Relationships TO this layer
            elif rel.get("to_layer") == dominant_layer:
                relevant.append({
                    "direction": "incoming",
                    "from_layer": rel.get("from_layer"),
                    "to_layer": rel.get("to_layer"),
                    "bhava_name": rel.get("bhava_name"),
                    "pattern_type": rel.get("pattern_type"),
                    "interpretation": rel.get("interpretation"),
                    "strength": rel.get("strength", 0),
                })

        # Sort by strength and return top_k
        relevant.sort(key=lambda x: x.get("strength", 0), reverse=True)
        return relevant[:top_k]

    def get_bhava_context(self, layer_idx: int) -> Dict[str, Any]:
        """Get Bhava significance for a layer."""
        if 1 <= layer_idx <= 12:
            bhava = BHAVA_SIGNIFICANCES[layer_idx]
            return {
                "bhava_number": layer_idx,
                "name": bhava["name"],
                "meaning": bhava["meaning"],
                "description": bhava["description"],
            }
        return {}

    def format_rag_context(
        self,
        query_analysis: Dict[str, Any],
        similar_docs: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """Format retrieval results as context for LLM augmentation."""
        lines = []

        # Query ontological context
        lines.append("=== ONTOLOGICAL CONTEXT ===")
        lines.append(f"Query Layer: {query_analysis['dominant_layer']}")
        lines.append(f"Confidence: {query_analysis['confidence']:.1%}")
        lines.append(f"Coherence: {query_analysis.get('coherence', 0):.2f}")

        # Bhava meaning
        layer_idx = LAYER_INDEX.get(query_analysis['dominant_layer'], 0)
        if layer_idx > 0:
            bhava = BHAVA_SIGNIFICANCES[layer_idx]
            lines.append(f"Bhava: {bhava['name']} - {bhava['meaning']}")

        # Similar documents
        if similar_docs:
            lines.append("\n=== SIMILAR DOCUMENTS ===")
            for i, doc in enumerate(similar_docs[:3], 1):
                lines.append(f"{i}. [{doc['dominant_layer']}] {doc['text'][:100]}...")
                lines.append(f"   Similarity: {doc['similarity']:.2f}")

        # Relationship context
        if relationships:
            lines.append("\n=== RELATIONSHIP CONTEXT ===")
            for rel in relationships[:5]:
                direction = "→" if rel["direction"] == "outgoing" else "←"
                other = rel["to_layer"] if rel["direction"] == "outgoing" else rel["from_layer"]
                lines.append(f"  {direction} {other}: {rel['bhava_name']} ({rel['pattern_type']})")
                lines.append(f"    {rel['interpretation']}")

        # Strongest relationships from query
        strongest = query_analysis.get("strongest_relationships", [])
        if strongest:
            lines.append("\n=== ACTIVE RELATIONSHIPS IN QUERY ===")
            for rel in strongest[:3]:
                lines.append(f"  {rel['from_layer']} → {rel['to_layer']}: {rel.get('strength', 0):.2f}")
                if rel.get("bhava_interpretation"):
                    lines.append(f"    {rel['bhava_interpretation']}")

        return "\n".join(lines)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        include_relationships: bool = True,
    ) -> QueryResult:
        """
        Execute a full RAG query with ontological context.

        This is the main entry point for the presentation layer.

        Args:
            query_text: The user's query
            top_k: Number of similar documents to retrieve
            include_relationships: Whether to include graph relationships

        Returns:
            QueryResult with all context for RAG augmentation
        """
        # 1. Analyze query with ontological engine
        analysis = self.analyze_query(query_text)

        # 2. Search for similar documents (Vector DB)
        similar_docs = self.search_similar(
            query_vector=analysis.get("full_vector", analysis.get("full_156d_vector", [])),
            top_k=top_k,
        )

        # 3. Get relationship context (Graph DB)
        relationships = []
        if include_relationships:
            relationships = self.get_relationship_context(
                dominant_layer=analysis["dominant_layer"],
                top_k=top_k,
            )

        # 4. Get Bhava context
        layer_idx = LAYER_INDEX.get(analysis["dominant_layer"], 0)
        bhava_context = self.get_bhava_context(layer_idx)

        # 5. Format combined context for LLM
        rag_context = self.format_rag_context(analysis, similar_docs, relationships)

        return QueryResult(
            query_text=query_text,
            query_layer=analysis["dominant_layer"],
            query_confidence=analysis["confidence"],
            query_coherence=analysis.get("coherence", 0),
            query_vector=analysis.get("full_vector", analysis.get("full_156d_vector", [])),
            similar_documents=similar_docs,
            query_relationships=relationships,
            relevant_bhavas=[bhava_context] if bhava_context else [],
            rag_context=rag_context,
        )

    def get_rag_context(self, query_text: str, top_k: int = 5) -> str:
        """
        Convenience method to get just the formatted RAG context string.

        Use this to augment LLM prompts with ontological context.

        Example:
            context = engine.get_rag_context("What is consciousness?")
            prompt = f"Given this context:\\n{context}\\n\\nAnswer: {query}"
        """
        result = self.query(query_text, top_k=top_k)
        return result.rag_context


def create_query_engine(
    model_path: str = "checkpoints/unified_v2_best.pt",
    kb_path: str = "data/rag/knowledge_base.json",
) -> RAGQueryEngine:
    """Factory function to create and initialize a RAG query engine."""
    engine = RAGQueryEngine()
    engine.load_model(model_path)
    engine.load_knowledge_base(kb_path)
    return engine


if __name__ == "__main__":
    print("=" * 70)
    print("   RAG QUERY ENGINE - DEMO")
    print("=" * 70)

    # Create engine
    engine = RAGQueryEngine()

    # Try to load model and knowledge base
    model_loaded = engine.load_model()
    kb_loaded = engine.load_knowledge_base()

    if not model_loaded:
        print("\nNo trained model found. Run training first:")
        print("  python -m symbolu.ontological.train_v2")

    if not kb_loaded:
        print("\nNo knowledge base found. Run export first:")
        print("  python -m symbolu.ontological.export_to_rag")

    if model_loaded:
        # Demo queries
        test_queries = [
            "What is consciousness?",
            "Calculate the area of a circle",
            "The sunset paints dreams across the sky",
        ]

        print("\n" + "=" * 70)
        print("   SAMPLE QUERIES")
        print("=" * 70)

        for query in test_queries:
            print(f"\n>>> {query}")
            result = engine.query(query)
            print(f"    Layer: {result.query_layer} ({result.query_confidence:.1%})")
            print(f"    Coherence: {result.query_coherence:.2f}")
            print(f"    Similar docs: {len(result.similar_documents)}")
            print(f"    Relationships: {len(result.query_relationships)}")

        # Show full context for first query
        print("\n" + "=" * 70)
        print("   FULL RAG CONTEXT (for LLM augmentation)")
        print("=" * 70)

        result = engine.query(test_queries[0])
        print(result.rag_context)

    print("\n" + "=" * 70)
    print("   ARCHITECTURE")
    print("=" * 70)
    print("""
┌─────────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                              │
│                    (API / CLI / Web UI)                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RAGQueryEngine                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  • query(text) → QueryResult                                        │
│  • get_rag_context(text) → str (for LLM prompts)                   │
│  • search_similar(vector) → documents                               │
│  • get_relationship_context(layer) → relationships                  │
└─────────────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Ontological    │ │  Vector Index   │ │  Graph Index    │
│  Engine V2      │ │  (156D cosine)  │ │  (Relationships)│
│  ─────────────  │ │  ─────────────  │ │  ─────────────  │
│  Text → 156D    │ │  In-memory /    │ │  In-memory /    │
│  + Analysis     │ │  Pinecone       │ │  Neo4j          │
└─────────────────┘ └─────────────────┘ └─────────────────┘
""")
