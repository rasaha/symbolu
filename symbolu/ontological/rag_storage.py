#!/usr/bin/env python3
"""
RAG Storage for Ontological Engine Data
========================================

Structures ontological analysis data for storage and retrieval
in a RAG (Retrieval-Augmented Generation) database.

Data Types:
1. Document Analysis - Text analyzed with ontological vectors
2. Relationship Knowledge - Inter-layer Bhava relationships
3. Pattern Knowledge - Vedic Drishti patterns
4. Training Artifacts - Learned model patterns

Storage Schema:
- Vector Store: 156D embeddings (12D onto + 144D bhava)
- Metadata: Layer, coherence, relationships, Bhava meanings
- Graph Store: Relationship matrices as edges

Usage:
    from symbolu.ontological.rag_storage import OntologicalRAGStorage

    storage = OntologicalRAGStorage()

    # Index a document
    doc_id = storage.index_document(
        text="What is consciousness?",
        analysis=engine.analyze("What is consciousness?")
    )

    # Query by ontological similarity
    results = storage.query_by_ontology(
        query_text="nature of awareness",
        top_k=5
    )

    # Query by relationship pattern
    results = storage.query_by_relationship(
        from_layer="O5_COGNITION",
        to_layer="O8_PURPOSE",
        bhava="Sukha"
    )
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX
from symbolu.ontological.bhava_relationships import (
    BHAVA_SIGNIFICANCES,
    ASPECT_STRENGTH_MATRIX,
    get_relationship_meaning,
)


@dataclass
class OntologicalDocument:
    """A document with its ontological analysis for RAG storage."""

    # Core identifiers
    doc_id: str
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Classification
    dominant_layer: str = ""
    confidence: float = 0.0
    certainty_level: str = "unknown"

    # Vectors for similarity search
    ontological_vector: List[float] = field(default_factory=list)  # 12D
    bhava_vector: List[float] = field(default_factory=list)  # 144D
    full_vector: List[float] = field(default_factory=list)  # 156D

    # Coherence and uncertainty
    coherence: float = 0.0
    uncertainty: float = 0.0

    # Relationships (top 5)
    strongest_relationships: List[Dict[str, Any]] = field(default_factory=list)

    # Task scores
    reasoning_score: float = 0.0
    creativity_score: float = 0.0

    # Full relationship matrix (12x12)
    relationship_matrix: List[List[float]] = field(default_factory=list)

    # Metadata for filtering
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_analysis(
        cls,
        doc_id: str,
        text: str,
        analysis: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> "OntologicalDocument":
        """Create from engine.analyze() output."""
        return cls(
            doc_id=doc_id,
            text=text,
            dominant_layer=analysis.get("dominant_layer", ""),
            confidence=analysis.get("confidence", 0.0),
            certainty_level=analysis.get("certainty_level", "unknown"),
            ontological_vector=analysis.get("ontological_vector", []),
            bhava_vector=analysis.get("bhava_vector", []),
            full_vector=analysis.get("full_156d_vector", []),
            coherence=analysis.get("coherence", 0.0),
            uncertainty=analysis.get("uncertainty", 0.0),
            strongest_relationships=analysis.get("strongest_relationships", []),
            reasoning_score=analysis.get("reasoning_score", 0.0),
            creativity_score=analysis.get("creativity_score", 0.0),
            relationship_matrix=analysis.get("relationship_matrix", []),
            metadata=metadata or {},
        )


@dataclass
class RelationshipEdge:
    """A single inter-layer relationship for graph storage."""

    from_layer: str
    from_layer_idx: int
    to_layer: str
    to_layer_idx: int
    strength: float
    pattern_type: str  # Conjunction, Opposition, Trine, etc.
    bhava_name: str
    bhava_meaning: str
    interpretation: str
    aspect_strength: float  # Vedic aspect weight

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrishtiPattern:
    """A Vedic Drishti pattern for knowledge storage."""

    pattern_name: str
    distances: List[int]
    strength: float
    meaning: str
    description: str
    examples: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OntologicalRAGStorage:
    """
    RAG storage manager for ontological data.

    Provides methods to:
    1. Index documents with ontological analysis
    2. Store relationship knowledge (144 edges)
    3. Store Drishti patterns (7 pattern types)
    4. Query by vector similarity
    5. Query by relationship patterns
    6. Export for vector databases
    """

    def __init__(self, storage_dir: str = "data/rag"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory indices (for demo - replace with actual DB)
        self.documents: Dict[str, OntologicalDocument] = {}
        self.relationships: List[RelationshipEdge] = []
        self.patterns: List[DrishtiPattern] = []

        # Initialize knowledge base
        self._init_relationship_knowledge()
        self._init_drishti_patterns()

    def _init_relationship_knowledge(self):
        """Initialize all 144 relationship edges with Vedic meanings."""
        for from_idx in range(12):
            for to_idx in range(12):
                meaning = get_relationship_meaning(from_idx, to_idx)
                aspect_strength = ASPECT_STRENGTH_MATRIX[from_idx][to_idx]

                # Determine pattern type
                diff = abs(from_idx - to_idx)
                circular_diff = min(diff, 12 - diff)

                if circular_diff == 0:
                    pattern_type = "Conjunction"
                elif circular_diff == 6:
                    pattern_type = "Opposition"
                elif circular_diff in [4, 8]:
                    pattern_type = "Trine"
                elif circular_diff in [1, 11]:
                    pattern_type = "Adjacent"
                elif circular_diff in [3, 9]:
                    pattern_type = "Square"
                elif circular_diff in [2, 10]:
                    pattern_type = "Sextile"
                else:
                    pattern_type = "Quincunx"

                edge = RelationshipEdge(
                    from_layer=LAYER_NAMES[from_idx],
                    from_layer_idx=from_idx,
                    to_layer=LAYER_NAMES[to_idx],
                    to_layer_idx=to_idx,
                    strength=0.0,  # Will be filled from analysis
                    pattern_type=pattern_type,
                    bhava_name=meaning["relationship_bhava"]["name"],
                    bhava_meaning=meaning["relationship_bhava"]["meaning"],
                    interpretation=meaning["interpretation"],
                    aspect_strength=aspect_strength,
                )
                self.relationships.append(edge)

    def _init_drishti_patterns(self):
        """Initialize the 7 Drishti pattern types."""
        patterns_data = [
            {
                "pattern_name": "Conjunction",
                "distances": [0],
                "strength": 1.0,
                "meaning": "Same layer, self-reference",
                "description": "The strongest aspect - same layer relating to itself. "
                               "Represents identity, foundation, and self-awareness.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O1_POTENTIAL", "bhava": "Tanu (Self)"},
                    {"from": "O7_REASONING", "to": "O7_REASONING", "bhava": "Tanu (Self)"},
                ]
            },
            {
                "pattern_name": "Opposition",
                "distances": [6],
                "strength": 1.0,
                "meaning": "Complementary, full aspect",
                "description": "Full aspect strength - layers 6 apart are complementary. "
                               "Like the 7th house in astrology, represents partnership and balance.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O7_REASONING", "bhava": "Kalatra (Spouse)"},
                    {"from": "O5_COGNITION", "to": "O11_INTEGRATION", "bhava": "Kalatra (Spouse)"},
                ]
            },
            {
                "pattern_name": "Trine",
                "distances": [4, 8],
                "strength": 0.9,
                "meaning": "Harmonious, flowing",
                "description": "Highly harmonious relationships - energy flows easily. "
                               "Like 5th and 9th houses, represents creativity and wisdom.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O5_COGNITION", "bhava": "Putra (Children)"},
                    {"from": "O3_EXECUTION", "to": "O11_INTEGRATION", "bhava": "Dharma (Fortune)"},
                ]
            },
            {
                "pattern_name": "Adjacent",
                "distances": [1, 11],
                "strength": 0.8,
                "meaning": "Resource flow, immediate connection",
                "description": "Adjacent layers share resources and influence directly. "
                               "Like 2nd and 12th houses, represents accumulation and release.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O2_IDENTITY", "bhava": "Dhana (Wealth)"},
                    {"from": "O6_AGENCY", "to": "O7_REASONING", "bhava": "Dhana (Wealth)"},
                ]
            },
            {
                "pattern_name": "Square",
                "distances": [3, 9],
                "strength": 0.75,
                "meaning": "Action/tension, growth through challenge",
                "description": "Creates dynamic tension that drives action. "
                               "Like 4th and 10th houses, represents foundation and achievement.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O4_STRUCTURE", "bhava": "Sukha (Happiness)"},
                    {"from": "O4_STRUCTURE", "to": "O1_POTENTIAL", "bhava": "Karma (Action)"},
                ]
            },
            {
                "pattern_name": "Sextile",
                "distances": [2, 10],
                "strength": 0.7,
                "meaning": "Opportunity, cooperative",
                "description": "Cooperative relationship that creates opportunities. "
                               "Like 3rd and 11th houses, represents effort and gains.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O3_EXECUTION", "bhava": "Sahaja (Siblings)"},
                    {"from": "O2_IDENTITY", "to": "O12_ABSOLVING", "bhava": "Labha (Gains)"},
                ]
            },
            {
                "pattern_name": "Quincunx",
                "distances": [5, 7],
                "strength": 0.5,
                "meaning": "Adjustment needed, indirect",
                "description": "Requires adjustment and adaptation. "
                               "Like 6th and 8th houses, represents service and transformation.",
                "examples": [
                    {"from": "O1_POTENTIAL", "to": "O6_AGENCY", "bhava": "Ripu (Enemies)"},
                    {"from": "O5_COGNITION", "to": "O12_ABSOLVING", "bhava": "Randhra (Mystery)"},
                ]
            },
        ]

        for p in patterns_data:
            self.patterns.append(DrishtiPattern(**p))

    def index_document(
        self,
        doc_id: str,
        text: str,
        analysis: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> OntologicalDocument:
        """
        Index a document with its ontological analysis.

        Args:
            doc_id: Unique document identifier
            text: Original text
            analysis: Output from engine.analyze()
            metadata: Additional metadata

        Returns:
            OntologicalDocument ready for storage
        """
        doc = OntologicalDocument.from_analysis(doc_id, text, analysis, metadata)
        self.documents[doc_id] = doc
        return doc

    def get_document(self, doc_id: str) -> Optional[OntologicalDocument]:
        """Retrieve a document by ID."""
        return self.documents.get(doc_id)

    def query_by_layer(
        self,
        layer: str,
        min_confidence: float = 0.0
    ) -> List[OntologicalDocument]:
        """Query documents by dominant ontological layer."""
        return [
            doc for doc in self.documents.values()
            if doc.dominant_layer == layer and doc.confidence >= min_confidence
        ]

    def query_by_coherence(
        self,
        min_coherence: float = 0.5
    ) -> List[OntologicalDocument]:
        """Query documents with high coherence scores."""
        return [
            doc for doc in self.documents.values()
            if doc.coherence >= min_coherence
        ]

    def get_relationship_knowledge(
        self,
        from_layer: Optional[str] = None,
        to_layer: Optional[str] = None,
        pattern_type: Optional[str] = None,
        bhava_name: Optional[str] = None,
    ) -> List[RelationshipEdge]:
        """
        Query relationship knowledge base.

        Args:
            from_layer: Filter by source layer
            to_layer: Filter by target layer
            pattern_type: Filter by Drishti pattern (Conjunction, Trine, etc.)
            bhava_name: Filter by Bhava name (Tanu, Dhana, etc.)

        Returns:
            List of matching relationship edges
        """
        results = self.relationships

        if from_layer:
            results = [r for r in results if r.from_layer == from_layer]
        if to_layer:
            results = [r for r in results if r.to_layer == to_layer]
        if pattern_type:
            results = [r for r in results if r.pattern_type == pattern_type]
        if bhava_name:
            results = [r for r in results if r.bhava_name == bhava_name]

        return results

    def get_drishti_pattern(self, pattern_name: str) -> Optional[DrishtiPattern]:
        """Get a specific Drishti pattern by name."""
        for p in self.patterns:
            if p.pattern_name == pattern_name:
                return p
        return None

    def export_for_vector_db(self) -> Dict[str, Any]:
        """
        Export data formatted for vector databases (Pinecone, Weaviate, etc.)

        Returns:
            Dict with vectors, metadata, and graph edges
        """
        vectors = []
        for doc in self.documents.values():
            vectors.append({
                "id": doc.doc_id,
                "values": doc.full_vector,  # 156D vector
                "metadata": {
                    "text": doc.text[:500],  # Truncate for storage
                    "dominant_layer": doc.dominant_layer,
                    "confidence": doc.confidence,
                    "coherence": doc.coherence,
                    "uncertainty": doc.uncertainty,
                    "certainty_level": doc.certainty_level,
                    "reasoning_score": doc.reasoning_score,
                    "creativity_score": doc.creativity_score,
                    "top_relationship": doc.strongest_relationships[0] if doc.strongest_relationships else None,
                    **doc.metadata,
                }
            })

        return {
            "vectors": vectors,
            "namespace": "ontological",
            "dimension": 156,
        }

    def export_for_graph_db(self) -> Dict[str, Any]:
        """
        Export data formatted for graph databases (Neo4j, etc.)

        Returns:
            Dict with nodes (layers) and edges (relationships)
        """
        # Layer nodes
        nodes = []
        for idx, name in enumerate(LAYER_NAMES):
            bhava = BHAVA_SIGNIFICANCES[idx + 1]
            nodes.append({
                "id": name,
                "index": idx,
                "bhava_name": bhava["name"],
                "bhava_meaning": bhava["meaning"],
                "description": bhava["description"],
            })

        # Relationship edges
        edges = [r.to_dict() for r in self.relationships]

        return {
            "nodes": nodes,
            "edges": edges,
            "node_type": "OntologicalLayer",
            "edge_type": "BHAVA_RELATIONSHIP",
        }

    def export_knowledge_base(self, output_path: str = "data/rag/knowledge_base.json"):
        """Export complete knowledge base to JSON."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "metadata": {
                "type": "ontological_knowledge_base",
                "version": "2.0",
                "architecture": "inter-layer-bhava",
                "vector_dimension": 156,
                "ontological_dimension": 12,
                "bhava_dimension": 144,
                "timestamp": datetime.now().isoformat(),
            },
            "drishti_patterns": [p.to_dict() for p in self.patterns],
            "relationships": [r.to_dict() for r in self.relationships],
            "bhava_significances": [
                {"number": i, **BHAVA_SIGNIFICANCES[i]}
                for i in range(1, 13)
            ],
            "layer_names": LAYER_NAMES,
            "aspect_matrix": ASPECT_STRENGTH_MATRIX,
            "documents": [doc.to_dict() for doc in self.documents.values()],
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Knowledge base exported to: {output_file}")
        return data

    def save(self, output_path: str = "data/rag/storage.json"):
        """Save current storage state."""
        self.export_knowledge_base(output_path)

    def load(self, input_path: str = "data/rag/storage.json"):
        """Load storage state from file."""
        input_file = Path(input_path)
        if not input_file.exists():
            print(f"No storage file found at {input_file}")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Load documents
        for doc_data in data.get("documents", []):
            doc = OntologicalDocument(**doc_data)
            self.documents[doc.doc_id] = doc

        print(f"Loaded {len(self.documents)} documents from {input_file}")


def create_rag_schema() -> Dict[str, Any]:
    """
    Create a RAG database schema for ontological data.

    Returns schema for:
    - Vector index (156D embeddings)
    - Metadata fields
    - Graph relationships
    """
    return {
        "vector_index": {
            "name": "ontological_vectors",
            "dimension": 156,
            "metric": "cosine",
            "description": "12D ontological + 144D bhava relationship vectors",
        },
        "metadata_fields": [
            {"name": "text", "type": "text", "description": "Original text"},
            {"name": "dominant_layer", "type": "keyword", "filterable": True},
            {"name": "confidence", "type": "float", "filterable": True},
            {"name": "coherence", "type": "float", "filterable": True},
            {"name": "uncertainty", "type": "float", "filterable": True},
            {"name": "certainty_level", "type": "keyword", "filterable": True},
            {"name": "reasoning_score", "type": "float"},
            {"name": "creativity_score", "type": "float"},
            {"name": "top_relationship_from", "type": "keyword", "filterable": True},
            {"name": "top_relationship_to", "type": "keyword", "filterable": True},
            {"name": "top_relationship_bhava", "type": "keyword", "filterable": True},
        ],
        "graph_schema": {
            "nodes": {
                "OntologicalLayer": {
                    "properties": ["name", "index", "bhava_name", "bhava_meaning"]
                }
            },
            "edges": {
                "BHAVA_RELATIONSHIP": {
                    "from": "OntologicalLayer",
                    "to": "OntologicalLayer",
                    "properties": [
                        "strength", "pattern_type", "bhava_name",
                        "bhava_meaning", "interpretation", "aspect_strength"
                    ]
                }
            }
        }
    }


if __name__ == "__main__":
    # Demo usage
    storage = OntologicalRAGStorage()

    print("=" * 60)
    print("RAG STORAGE SCHEMA")
    print("=" * 60)

    schema = create_rag_schema()
    print(json.dumps(schema, indent=2))

    print("\n" + "=" * 60)
    print("DRISHTI PATTERNS IN KNOWLEDGE BASE")
    print("=" * 60)

    for pattern in storage.patterns:
        print(f"\n{pattern.pattern_name}:")
        print(f"  Distances: {pattern.distances}")
        print(f"  Strength: {pattern.strength}")
        print(f"  Meaning: {pattern.meaning}")

    print("\n" + "=" * 60)
    print("RELATIONSHIP KNOWLEDGE")
    print("=" * 60)

    # Example: Get all Trine relationships
    trines = storage.get_relationship_knowledge(pattern_type="Trine")
    print(f"\nTrine relationships: {len(trines)}")
    for r in trines[:3]:
        print(f"  {r.from_layer} → {r.to_layer}: {r.bhava_name} ({r.interpretation})")

    # Export knowledge base
    storage.export_knowledge_base()

    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
