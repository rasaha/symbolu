"""
10D Ontological RAG Integration
===============================

Integrates the 10D backbone with RAG retrieval for
ontology-aware cross-domain knowledge retrieval.

Instead of (or in addition to) embedding-based similarity,
this uses structural 10D similarity to find related content
across domains.

Key Features:
    - 10D-based retrieval alongside embedding retrieval
    - Domain-specific dimension weighting
    - Cross-domain bridge discovery
    - Structural explanation of why results match
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import json
import hashlib

from .encoder import DimensionalVector, Dimension, encode_10d, encode_batch
from .similarity import (
    compute_similarity,
    find_similar,
    structural_similarity,
    weighted_similarity,
    SimilarityResult,
)
from .extractors import (
    ProjectionDirection,
    detect_projection_direction,
    extract_all_with_direction,
)


class RetrievalMode(Enum):
    """Mode for 10D retrieval."""
    STRUCTURAL = "structural"      # Pure 10D structural similarity
    WEIGHTED = "weighted"          # Domain-weighted 10D similarity
    HYBRID = "hybrid"              # Combine 10D with embedding scores
    DIRECTIONAL = "directional"    # Consider projection direction


@dataclass
class DomainWeights:
    """
    Domain-specific dimension weights for retrieval.

    Different domains prioritize different dimensions:
    - Science: Intellect (6D), Mind (4D), Witness (8D)
    - History: Action (1D), Mind (4D), Body (3D)
    - Literature: Soul (7D), Ego (5D), Identification (2D)
    - Finance: Intellect (6D), Action (1D), Witness (8D)
    - Matchmaking: Soul (7D), Mind (4D), Ego (5D)
    """
    weights: Dict[Dimension, float]
    domain_name: str

    @classmethod
    def uniform(cls) -> "DomainWeights":
        """All dimensions equally weighted."""
        return cls(
            weights={dim: 1.0 for dim in Dimension},
            domain_name="uniform"
        )

    @classmethod
    def for_domain(cls, domain: str) -> "DomainWeights":
        """Get predefined weights for common domains."""
        presets = {
            "history": {
                Dimension.ACTION: 2.0,
                Dimension.IDENTIFICATION: 1.5,
                Dimension.BODY: 1.5,  # Geography
                Dimension.MIND: 2.0,  # Time/sequence
                Dimension.EGO: 1.5,   # Leaders/decisions
                Dimension.INTELLECT: 1.0,
                Dimension.SOUL: 0.5,
                Dimension.WITNESS: 0.5,
                Dimension.SINGULARITY: 0.5,
                Dimension.ABSOLUTE: 0.3,
            },
            "science": {
                Dimension.ACTION: 1.0,
                Dimension.IDENTIFICATION: 1.0,
                Dimension.BODY: 1.5,  # Physical
                Dimension.MIND: 1.5,  # Process
                Dimension.EGO: 0.5,
                Dimension.INTELLECT: 2.5,  # Laws/theories
                Dimension.SOUL: 0.5,
                Dimension.WITNESS: 2.0,  # Probability
                Dimension.SINGULARITY: 1.5,  # Unification
                Dimension.ABSOLUTE: 0.5,
            },
            "literature": {
                Dimension.ACTION: 1.5,
                Dimension.IDENTIFICATION: 2.0,  # Characters
                Dimension.BODY: 1.0,
                Dimension.MIND: 1.5,  # Memory/time
                Dimension.EGO: 2.0,   # Choices/agency
                Dimension.INTELLECT: 1.0,
                Dimension.SOUL: 2.5,  # Themes/transformation
                Dimension.WITNESS: 1.5,  # Perspective
                Dimension.SINGULARITY: 1.0,
                Dimension.ABSOLUTE: 1.0,
            },
            "finance": {
                Dimension.ACTION: 2.0,  # Transactions
                Dimension.IDENTIFICATION: 1.5,  # Entities
                Dimension.BODY: 0.5,
                Dimension.MIND: 1.5,  # Time value
                Dimension.EGO: 1.5,   # Decisions
                Dimension.INTELLECT: 2.0,  # Laws/formulas
                Dimension.SOUL: 0.5,
                Dimension.WITNESS: 2.5,  # Risk/probability
                Dimension.SINGULARITY: 1.0,
                Dimension.ABSOLUTE: 0.3,
            },
            "biology": {
                Dimension.ACTION: 1.5,
                Dimension.IDENTIFICATION: 1.5,  # Species/classification
                Dimension.BODY: 2.5,  # Physical form
                Dimension.MIND: 1.5,  # Process
                Dimension.EGO: 0.5,
                Dimension.INTELLECT: 2.0,  # Laws
                Dimension.SOUL: 1.5,  # Evolution/transformation
                Dimension.WITNESS: 1.0,
                Dimension.SINGULARITY: 1.0,
                Dimension.ABSOLUTE: 0.3,
            },
            "matchmaking": {
                Dimension.ACTION: 0.5,
                Dimension.IDENTIFICATION: 1.0,  # Who they are
                Dimension.BODY: 0.3,  # Less emphasis on physical
                Dimension.MIND: 2.5,  # Mental compatibility
                Dimension.EGO: 2.0,   # Will/choice alignment
                Dimension.INTELLECT: 1.5,  # Shared values
                Dimension.SOUL: 3.0,  # Deep connection
                Dimension.WITNESS: 1.5,  # Awareness/perspective
                Dimension.SINGULARITY: 2.0,  # Unity potential
                Dimension.ABSOLUTE: 1.0,
            },
        }

        domain_lower = domain.lower()
        if domain_lower in presets:
            return cls(weights=presets[domain_lower], domain_name=domain)

        # Default to uniform
        return cls.uniform()


@dataclass
class OntologicalDocument:
    """
    Document with 10D ontological encoding.

    Stores both the content and its pre-computed 10D vector
    for efficient retrieval.
    """
    doc_id: str
    content: str
    domain: str
    vector: DimensionalVector
    direction: ProjectionDirection
    direction_strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "domain": self.domain,
            "vector": self.vector.to_dict(),
            "direction": self.direction.value,
            "direction_strength": self.direction_strength,
            "metadata": self.metadata,
        }

    @classmethod
    def from_content(
        cls,
        doc_id: str,
        content: str,
        domain: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "OntologicalDocument":
        """Create document with automatic encoding."""
        vector = encode_10d(content)
        direction, strength, _ = detect_projection_direction(content)
        return cls(
            doc_id=doc_id,
            content=content,
            domain=domain,
            vector=vector,
            direction=direction,
            direction_strength=strength,
            metadata=metadata or {},
        )


@dataclass
class OntologicalRetrievalResult:
    """
    Result from ontological retrieval.

    Includes structural explanation of why the result matches.
    """
    document: OntologicalDocument
    similarity_score: float
    similarity_result: SimilarityResult
    cross_domain: bool  # True if query and result are from different domains
    structural_bridge: str  # Explanation of structural connection

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.document.doc_id,
            "domain": self.document.domain,
            "content_preview": self.document.content[:200],
            "similarity_score": self.similarity_score,
            "cross_domain": self.cross_domain,
            "structural_bridge": self.structural_bridge,
            "shared_dimensions": [
                d[0] for d in self.similarity_result.dominant_shared
            ],
        }


class OntologicalRAGIndex:
    """
    10D ontological index for RAG retrieval.

    Stores documents with their 10D encodings and provides
    structural similarity-based retrieval.
    """

    def __init__(self):
        self._documents: Dict[str, OntologicalDocument] = {}
        self._by_domain: Dict[str, Set[str]] = {}  # domain -> doc_ids
        self._vectors: Dict[str, DimensionalVector] = {}

    def add_document(self, doc: OntologicalDocument) -> None:
        """Add document to index."""
        self._documents[doc.doc_id] = doc
        self._vectors[doc.doc_id] = doc.vector

        if doc.domain not in self._by_domain:
            self._by_domain[doc.domain] = set()
        self._by_domain[doc.domain].add(doc.doc_id)

    def add_content(
        self,
        doc_id: str,
        content: str,
        domain: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OntologicalDocument:
        """Add content with automatic encoding."""
        doc = OntologicalDocument.from_content(doc_id, content, domain, metadata)
        self.add_document(doc)
        return doc

    def bulk_add(
        self,
        items: List[Tuple[str, str, str]],  # (doc_id, content, domain)
    ) -> List[OntologicalDocument]:
        """Bulk add documents."""
        docs = []
        for doc_id, content, domain in items:
            doc = self.add_content(doc_id, content, domain)
            docs.append(doc)
        return docs

    @property
    def size(self) -> int:
        """Number of documents in index."""
        return len(self._documents)

    @property
    def domains(self) -> List[str]:
        """List of domains in index."""
        return list(self._by_domain.keys())

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        mode: RetrievalMode = RetrievalMode.STRUCTURAL,
        query_domain: Optional[str] = None,
        target_domains: Optional[List[str]] = None,
        cross_domain_only: bool = False,
        domain_weights: Optional[DomainWeights] = None,
    ) -> List[OntologicalRetrievalResult]:
        """
        Retrieve documents by 10D structural similarity.

        Args:
            query: Query text
            top_k: Number of results
            mode: Retrieval mode
            query_domain: Domain of query (for cross-domain detection)
            target_domains: Limit search to these domains
            cross_domain_only: Only return cross-domain matches
            domain_weights: Custom dimension weights

        Returns:
            List of OntologicalRetrievalResult sorted by score
        """
        query_vec = encode_10d(query)

        # Filter candidates by domain if specified
        candidate_ids = set(self._documents.keys())
        if target_domains:
            candidate_ids = set()
            for domain in target_domains:
                candidate_ids.update(self._by_domain.get(domain, set()))

        if cross_domain_only and query_domain:
            # Exclude documents from query domain
            exclude = self._by_domain.get(query_domain, set())
            candidate_ids -= exclude

        if not candidate_ids:
            return []

        # Compute similarities
        results = []
        for doc_id in candidate_ids:
            doc = self._documents[doc_id]

            # Choose similarity method based on mode
            if mode == RetrievalMode.WEIGHTED and domain_weights:
                score = weighted_similarity(query_vec, doc.vector, domain_weights.weights)
                sim_result = compute_similarity(query_vec, doc.vector, "weighted")
            else:
                sim_result = compute_similarity(query_vec, doc.vector, "structural")
                score = sim_result.score

            # Determine if cross-domain
            is_cross_domain = query_domain and doc.domain != query_domain

            # Build structural bridge explanation
            bridge = self._build_structural_bridge(sim_result, query_domain, doc.domain)

            results.append(OntologicalRetrievalResult(
                document=doc,
                similarity_score=score,
                similarity_result=sim_result,
                cross_domain=is_cross_domain,
                structural_bridge=bridge,
            ))

        # Sort by score and return top_k
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:top_k]

    def _build_structural_bridge(
        self,
        sim: SimilarityResult,
        query_domain: Optional[str],
        doc_domain: str
    ) -> str:
        """Build explanation of structural connection."""
        parts = []

        if sim.dominant_shared:
            dims = [d[0] for d in sim.dominant_shared[:3]]
            parts.append(f"Shared structure in: {', '.join(dims)}")

        if query_domain and query_domain != doc_domain:
            parts.append(f"Cross-domain link: {query_domain} <-> {doc_domain}")

        if not parts:
            parts.append("Weak structural connection")

        return " | ".join(parts)

    def find_cross_domain_bridges(
        self,
        min_similarity: float = 0.6,
        max_results: int = 20
    ) -> List[Tuple[OntologicalDocument, OntologicalDocument, SimilarityResult]]:
        """
        Find structural bridges between documents in different domains.

        Returns:
            List of (doc1, doc2, similarity) tuples for cross-domain matches
        """
        bridges = []
        domains = list(self._by_domain.keys())

        for i, domain1 in enumerate(domains):
            for domain2 in domains[i + 1:]:
                for doc_id1 in self._by_domain[domain1]:
                    doc1 = self._documents[doc_id1]
                    for doc_id2 in self._by_domain[domain2]:
                        doc2 = self._documents[doc_id2]

                        sim = compute_similarity(doc1.vector, doc2.vector, "structural")
                        if sim.score >= min_similarity:
                            bridges.append((doc1, doc2, sim))

        # Sort by similarity
        bridges.sort(key=lambda x: x[2].score, reverse=True)
        return bridges[:max_results]

    def export_index(self) -> Dict[str, Any]:
        """Export index to dictionary for serialization."""
        return {
            "documents": [doc.to_dict() for doc in self._documents.values()],
            "domains": list(self._by_domain.keys()),
            "size": self.size,
        }


# =============================================================================
# Integration with existing RAG system
# =============================================================================

def create_ontological_index_from_rag(
    rag_entries: List[Dict[str, Any]]
) -> OntologicalRAGIndex:
    """
    Create 10D index from existing RAG entries.

    Args:
        rag_entries: List of RAG entries with 'id', 'content', 'corpus_id'

    Returns:
        Populated OntologicalRAGIndex
    """
    index = OntologicalRAGIndex()

    for entry in rag_entries:
        doc_id = entry.get("id", entry.get("doc_id", ""))
        content = entry.get("content", entry.get("text", ""))
        domain = entry.get("corpus_id", entry.get("domain", "unknown"))
        metadata = entry.get("metadata", {})

        if doc_id and content:
            index.add_content(doc_id, content, domain, metadata)

    return index


def hybrid_retrieve(
    query: str,
    ontological_index: OntologicalRAGIndex,
    embedding_results: List[Dict[str, Any]],
    ontological_weight: float = 0.4,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval combining 10D structural and embedding similarity.

    Args:
        query: Query text
        ontological_index: 10D index
        embedding_results: Results from embedding-based retrieval
        ontological_weight: Weight for 10D scores (0.0-1.0)
        top_k: Number of results

    Returns:
        Re-ranked results with combined scores
    """
    # Get 10D results
    onto_results = ontological_index.retrieve(query, top_k=top_k * 2)
    onto_scores = {r.document.doc_id: r.similarity_score for r in onto_results}
    onto_bridges = {r.document.doc_id: r.structural_bridge for r in onto_results}

    # Combine scores
    combined = []
    embedding_weight = 1.0 - ontological_weight

    for emb_result in embedding_results:
        doc_id = emb_result.get("id", emb_result.get("doc_id", ""))
        emb_score = emb_result.get("score", emb_result.get("similarity", 0.5))

        onto_score = onto_scores.get(doc_id, 0.0)
        combined_score = (emb_score * embedding_weight) + (onto_score * ontological_weight)

        combined.append({
            **emb_result,
            "combined_score": combined_score,
            "embedding_score": emb_score,
            "ontological_score": onto_score,
            "structural_bridge": onto_bridges.get(doc_id, ""),
        })

    # Sort by combined score
    combined.sort(key=lambda x: x["combined_score"], reverse=True)
    return combined[:top_k]


# Singleton index for global use
_global_index: Optional[OntologicalRAGIndex] = None


def get_global_index() -> OntologicalRAGIndex:
    """Get or create global ontological index."""
    global _global_index
    if _global_index is None:
        _global_index = OntologicalRAGIndex()
    return _global_index
