# Typed Graph LLM Implementation Specification

## Document Information

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Draft |
| Domain | Symbol-U / Soulpi Implementation |

---

## 1. Implementation Overview

This document provides detailed implementation specifications for the Typed Graph LLM architecture, including code structures, algorithms, and integration patterns.

---

## 2. Module Structure

### 2.1 Package Layout

```
symbolu/
├── ppv/                           # PPV subsystem (implemented)
│   ├── __init__.py
│   ├── ppv_contract_v1.py         # PPV data structures
│   └── ppv_builder_v1.py          # PPV construction
├── graph/                         # Typed graph subsystem (new)
│   ├── __init__.py
│   ├── graph_schema_v1.py         # Node/Edge schemas
│   ├── graph_store_v1.py          # Graph storage
│   ├── graph_query_v1.py          # Query interface
│   └── graph_verifier_v1.py       # Constraint verification
├── ontology/                      # Ontology layer subsystem (new)
│   ├── __init__.py
│   ├── ontology_layers_v1.py      # Layer definitions
│   ├── ontology_mapping_v1.py     # PPV-to-semantic mapping
│   └── ontology_traverse_v1.py    # Layer traversal
├── reasoning/                     # Reasoning engine (new)
│   ├── __init__.py
│   ├── inference_engine_v1.py     # Graph-based inference
│   ├── constraint_solver_v1.py    # Constraint satisfaction
│   └── reasoning_trace_v1.py      # Explanation generation
└── mechanical/pipeline/           # Existing pipeline
    ├── p10_acoustic/
    │   └── p10_ppv_envelope.py    # PPV envelope (implemented)
    └── p11_controller/            # Phase-11 controller (implemented)
```

### 2.2 Dependency Graph

```
ppv_contract_v1 ─────────────────────────────────┐
      │                                          │
      ▼                                          │
ppv_builder_v1                                   │
      │                                          │
      ▼                                          │
p10_ppv_envelope ────► graph_schema_v1 ◄────────┘
                              │
                              ▼
                       graph_store_v1
                              │
                              ▼
                       graph_query_v1
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ontology_layers_v1  inference_engine_v1  reasoning_trace_v1
              │               │
              ▼               ▼
    ontology_mapping_v1  constraint_solver_v1
```

---

## 3. Core Implementation

### 3.1 Graph Schema (graph_schema_v1.py)

```python
"""
Graph Schema - Typed Node and Edge Definitions
===============================================

Hard Constraints:
    - All dataclasses frozen (immutable)
    - All IDs are deterministic hashes
    - No free-form string fields without validation
    - All numeric values bounded
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import Tuple, Optional, Dict, Any

# =============================================================================
# Version
# =============================================================================

GRAPH_SCHEMA_VERSION = "1.0.0"

# =============================================================================
# Edge Types
# =============================================================================

@unique
class EdgeType(str, Enum):
    """Strongly-typed edge relationship types."""
    IS_A = "is_a"
    HAS_PART = "has_part"
    CORRELATES_WITH = "correlates_with"
    TRIGGERS = "triggers"
    CONSTRAINS = "constrains"
    ACOUSTIC_MAPS_TO = "acoustic_maps_to"
    TEMPORAL_PRECEDES = "temporal_precedes"

# =============================================================================
# Node Types
# =============================================================================

@unique
class NodeType(str, Enum):
    """Strongly-typed node categories."""
    CONCEPT = "concept"
    PHONEME = "phoneme"
    LEXEME = "lexeme"
    ONTOLOGY = "ontology"
    PROPENSITY = "propensity"
    RELATION = "relation"
    CONSTRAINT = "constraint"

# =============================================================================
# Base Node
# =============================================================================

@dataclass(frozen=True)
class GraphNode:
    """Base class for all graph nodes."""
    node_id: str
    node_type: NodeType
    version: str = GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate base node invariants."""
        if not isinstance(self.node_id, str) or len(self.node_id) != 64:
            raise ValueError(f"node_id must be 64-char hex, got {len(self.node_id)}")
        try:
            int(self.node_id, 16)
        except ValueError:
            raise ValueError("node_id must be valid hex")
        if not isinstance(self.node_type, NodeType):
            raise ValueError(f"node_type must be NodeType, got {type(self.node_type)}")

# =============================================================================
# Concept Node
# =============================================================================

@dataclass(frozen=True)
class ConceptNode(GraphNode):
    """Node representing an abstract concept."""
    concept_label: str
    ontology_layer: int
    feature_vector: Tuple[int, ...]
    parent_ids: Tuple[str, ...]
    child_ids: Tuple[str, ...]
    ppv_correlation: Tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate concept node invariants."""
        super().__post_init__()
        if self.node_type != NodeType.CONCEPT:
            raise ValueError("ConceptNode must have node_type=CONCEPT")
        if not 0 <= self.ontology_layer <= 6:
            raise ValueError(f"ontology_layer must be 0-6, got {self.ontology_layer}")
        if len(self.ppv_correlation) != 8:
            raise ValueError(f"ppv_correlation must have 8 elements")
        for corr in self.ppv_correlation:
            if not -1.0 <= corr <= 1.0:
                raise ValueError(f"ppv_correlation values must be [-1.0, 1.0]")

# =============================================================================
# Phoneme Node
# =============================================================================

@dataclass(frozen=True)
class PhonemeNode(GraphNode):
    """Node representing a phoneme with PPV features."""
    phoneme_id: str
    ppv_features: Tuple[int, ...]
    articulation_class: str
    sonority_rank: int
    adjacency_affinity: Tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate phoneme node invariants."""
        super().__post_init__()
        if self.node_type != NodeType.PHONEME:
            raise ValueError("PhonemeNode must have node_type=PHONEME")
        if len(self.ppv_features) != 8:
            raise ValueError(f"ppv_features must have 8 elements")
        for val in self.ppv_features:
            if not 0 <= val <= 7:
                raise ValueError(f"ppv_features values must be 0-7")
        if not 0 <= self.sonority_rank <= 10:
            raise ValueError(f"sonority_rank must be 0-10")

# =============================================================================
# Typed Edge
# =============================================================================

@dataclass(frozen=True)
class TypedEdge:
    """Strongly-typed edge between nodes."""
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    weight: float
    metadata: Tuple[Tuple[str, str], ...]
    version: str = GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate edge invariants."""
        if not isinstance(self.edge_id, str) or len(self.edge_id) != 64:
            raise ValueError(f"edge_id must be 64-char hex")
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"weight must be 0.0-1.0, got {self.weight}")

# =============================================================================
# Hash Computation
# =============================================================================

def compute_node_hash(
    node_type: NodeType,
    content: str,
    version: str = GRAPH_SCHEMA_VERSION,
) -> str:
    """Compute deterministic node hash."""
    hash_input = f"node:{node_type.value}|content:{content}|v:{version}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

def compute_edge_hash(
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    version: str = GRAPH_SCHEMA_VERSION,
) -> str:
    """Compute deterministic edge hash."""
    hash_input = f"edge:{source_id}|{target_id}|{edge_type.value}|v:{version}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
```

### 3.2 Graph Store (graph_store_v1.py)

```python
"""
Graph Store - In-Memory Typed Graph Storage
============================================

Provides append-only storage with integrity verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Set

from symbolu.graph.graph_schema_v1 import (
    GraphNode,
    TypedEdge,
    EdgeType,
    NodeType,
)

# =============================================================================
# Version
# =============================================================================

GRAPH_STORE_VERSION = "1.0.0"

# =============================================================================
# Graph Store
# =============================================================================

@dataclass
class TypedGraphStore:
    """
    In-memory typed graph store.

    Invariants:
        - Append-only (no deletion in GOVERNED mode)
        - Referential integrity enforced
        - Deterministic ordering
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, TypedEdge] = {}
        self._edges_by_source: Dict[str, Set[str]] = {}
        self._edges_by_target: Dict[str, Set[str]] = {}
        self._edges_by_type: Dict[EdgeType, Set[str]] = {t: set() for t in EdgeType}

    def add_node(self, node: GraphNode) -> str:
        """
        Add a node to the graph.

        Returns:
            The node_id of the added node.

        Raises:
            ValueError: If node with same ID already exists.
        """
        if node.node_id in self._nodes:
            raise ValueError(f"Node {node.node_id[:16]}... already exists")
        self._nodes[node.node_id] = node
        return node.node_id

    def add_edge(self, edge: TypedEdge) -> str:
        """
        Add an edge to the graph.

        Returns:
            The edge_id of the added edge.

        Raises:
            ValueError: If referential integrity violated.
        """
        # Check referential integrity
        if edge.source_node_id not in self._nodes:
            raise ValueError(f"Source node {edge.source_node_id[:16]}... not found")
        if edge.target_node_id not in self._nodes:
            raise ValueError(f"Target node {edge.target_node_id[:16]}... not found")

        if edge.edge_id in self._edges:
            raise ValueError(f"Edge {edge.edge_id[:16]}... already exists")

        # Add edge
        self._edges[edge.edge_id] = edge

        # Update indices
        if edge.source_node_id not in self._edges_by_source:
            self._edges_by_source[edge.source_node_id] = set()
        self._edges_by_source[edge.source_node_id].add(edge.edge_id)

        if edge.target_node_id not in self._edges_by_target:
            self._edges_by_target[edge.target_node_id] = set()
        self._edges_by_target[edge.target_node_id].add(edge.edge_id)

        self._edges_by_type[edge.edge_type].add(edge.edge_id)

        return edge.edge_id

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[TypedEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    def get_outgoing_edges(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
    ) -> Tuple[TypedEdge, ...]:
        """Get all outgoing edges from a node, optionally filtered by type."""
        edge_ids = self._edges_by_source.get(node_id, set())
        edges = [self._edges[eid] for eid in edge_ids]
        if edge_type is not None:
            edges = [e for e in edges if e.edge_type == edge_type]
        return tuple(sorted(edges, key=lambda e: e.edge_id))

    def get_incoming_edges(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
    ) -> Tuple[TypedEdge, ...]:
        """Get all incoming edges to a node, optionally filtered by type."""
        edge_ids = self._edges_by_target.get(node_id, set())
        edges = [self._edges[eid] for eid in edge_ids]
        if edge_type is not None:
            edges = [e for e in edges if e.edge_type == edge_type]
        return tuple(sorted(edges, key=lambda e: e.edge_id))

    def node_count(self) -> int:
        """Return total node count."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return total edge count."""
        return len(self._edges)
```

### 3.3 Ontology Mapping (ontology_mapping_v1.py)

```python
"""
Ontology Mapping - PPV to Semantic Layer Mapping
=================================================

Maps PPV vectors to ontology layer concepts through typed correlations.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from symbolu.ppv.ppv_contract_v1 import PPVVector, PPVDim

# =============================================================================
# Version
# =============================================================================

ONTOLOGY_MAPPING_VERSION = "1.0.0"

# =============================================================================
# Ontology Layers
# =============================================================================

ONTOLOGY_LAYERS: Dict[int, str] = {
    0: "PHYSICAL",
    1: "ACOUSTIC",
    2: "PERCEPTUAL",
    3: "AFFECTIVE",
    4: "EVALUATIVE",
    5: "INTENTIONAL",
    6: "PHENOMENAL",
}

# =============================================================================
# PPV-to-Layer Mapping Tables
# =============================================================================

# Which PPV dimensions are most relevant for each layer
PPV_LAYER_RELEVANCE: Dict[int, Tuple[PPVDim, ...]] = {
    0: (),  # Physical: no PPV mapping (raw signals)
    1: (    # Acoustic: all PPV dims relevant
        PPVDim.EDGE_TENSION,
        PPVDim.EDGE_RELEASE,
        PPVDim.ONSET_SHARPNESS,
        PPVDim.SONORITY_LIFT,
        PPVDim.CONTINUITY,
        PPVDim.DISCONTINUITY,
        PPVDim.RHYTHMIC_IMPULSE,
        PPVDim.STABILITY_PRESSURE,
    ),
    2: (    # Perceptual: pattern-related dims
        PPVDim.ONSET_SHARPNESS,
        PPVDim.SONORITY_LIFT,
        PPVDim.RHYTHMIC_IMPULSE,
    ),
    3: (    # Affective: tension/release related
        PPVDim.EDGE_TENSION,
        PPVDim.EDGE_RELEASE,
        PPVDim.STABILITY_PRESSURE,
    ),
    4: (    # Evaluative: continuity patterns
        PPVDim.CONTINUITY,
        PPVDim.DISCONTINUITY,
    ),
    5: (    # Intentional: impulse/stability
        PPVDim.RHYTHMIC_IMPULSE,
        PPVDim.STABILITY_PRESSURE,
    ),
    6: (),  # Phenomenal: no direct PPV (high-level interpretation)
}

# =============================================================================
# PPV Semantic Mapping
# =============================================================================

@dataclass(frozen=True)
class PPVSemanticMapping:
    """Maps a PPV pattern to semantic concept correlations."""
    ppv_pattern_hash: str
    target_layer: int
    concept_correlations: Tuple[Tuple[str, float], ...]
    confidence: float
    mapping_version: str = ONTOLOGY_MAPPING_VERSION

    def __post_init__(self) -> None:
        """Validate mapping invariants."""
        if not 0 <= self.target_layer <= 6:
            raise ValueError(f"target_layer must be 0-6, got {self.target_layer}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        for concept_id, weight in self.concept_correlations:
            if not -1.0 <= weight <= 1.0:
                raise ValueError(f"correlation weight must be [-1.0, 1.0]")

# =============================================================================
# Mapping Functions
# =============================================================================

def compute_ppv_layer_score(
    ppv: PPVVector,
    target_layer: int,
) -> float:
    """
    Compute PPV relevance score for a target ontology layer.

    Args:
        ppv: The PPV vector to score.
        target_layer: The ontology layer (0-6).

    Returns:
        Normalized score (0.0-1.0) indicating PPV relevance for layer.
    """
    relevant_dims = PPV_LAYER_RELEVANCE.get(target_layer, ())
    if not relevant_dims:
        return 0.0

    # Get indices of relevant dimensions
    all_dims = tuple(PPVDim)
    dim_indices = [all_dims.index(d) for d in relevant_dims]

    # Compute average of relevant dimension values
    relevant_values = [ppv.values[i] for i in dim_indices]
    avg_value = sum(relevant_values) / len(relevant_values)

    # Normalize to 0.0-1.0 (PPV values are 0-7)
    return avg_value / 7.0

def map_ppv_to_layer(
    ppv: PPVVector,
    target_layer: int,
    concept_table: Dict[str, Tuple[float, ...]],
) -> Tuple[Tuple[str, float], ...]:
    """
    Map PPV to concept correlations at a target layer.

    Args:
        ppv: The PPV vector.
        target_layer: Target ontology layer.
        concept_table: Mapping of concept_id -> ppv_correlation_weights.

    Returns:
        Tuple of (concept_id, correlation_score) sorted by score descending.
    """
    results = []
    for concept_id, weights in concept_table.items():
        if len(weights) != 8:
            continue
        # Compute dot product of PPV values with concept weights
        score = sum(v * w for v, w in zip(ppv.values, weights))
        # Normalize
        max_score = 7.0 * 8  # Max possible dot product
        normalized = score / max_score if max_score > 0 else 0.0
        results.append((concept_id, normalized))

    return tuple(sorted(results, key=lambda x: -x[1]))
```

### 3.4 Inference Engine (inference_engine_v1.py)

```python
"""
Inference Engine - Graph-Based Reasoning
==========================================

Provides deterministic graph traversal and inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional, List, Set

from symbolu.graph.graph_schema_v1 import (
    GraphNode,
    TypedEdge,
    EdgeType,
    ConceptNode,
)
from symbolu.graph.graph_store_v1 import TypedGraphStore

# =============================================================================
# Version
# =============================================================================

INFERENCE_ENGINE_VERSION = "1.0.0"

# =============================================================================
# Inference Result
# =============================================================================

@dataclass(frozen=True)
class InferenceStep:
    """Single step in an inference chain."""
    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    confidence: float
    step_index: int

@dataclass(frozen=True)
class InferenceResult:
    """Result of graph-based inference."""
    query_node_id: str
    result_node_ids: Tuple[str, ...]
    inference_path: Tuple[InferenceStep, ...]
    total_confidence: float
    inference_version: str = INFERENCE_ENGINE_VERSION

# =============================================================================
# Inference Engine
# =============================================================================

class InferenceEngine:
    """
    Deterministic graph-based inference engine.

    Provides:
        - Path finding through typed edges
        - Confidence propagation
        - Cycle detection
        - Deterministic ordering
    """

    def __init__(self, graph: TypedGraphStore) -> None:
        self._graph = graph

    def find_path(
        self,
        start_node_id: str,
        target_layer: int,
        max_depth: int = 5,
    ) -> Optional[InferenceResult]:
        """
        Find inference path from start node to target ontology layer.

        Args:
            start_node_id: Starting node ID.
            target_layer: Target ontology layer (0-6).
            max_depth: Maximum path depth.

        Returns:
            InferenceResult if path found, None otherwise.
        """
        start_node = self._graph.get_node(start_node_id)
        if start_node is None:
            return None

        # BFS with deterministic ordering
        visited: Set[str] = set()
        queue: List[Tuple[str, List[InferenceStep], float]] = [
            (start_node_id, [], 1.0)
        ]

        results: List[Tuple[str, List[InferenceStep], float]] = []

        while queue:
            current_id, path, confidence = queue.pop(0)

            if current_id in visited:
                continue
            visited.add(current_id)

            if len(path) >= max_depth:
                continue

            # Check if we reached target layer
            current_node = self._graph.get_node(current_id)
            if isinstance(current_node, ConceptNode):
                if current_node.ontology_layer == target_layer:
                    results.append((current_id, path, confidence))
                    continue

            # Expand neighbors (deterministic order)
            edges = self._graph.get_outgoing_edges(current_id)
            for edge in edges:
                if edge.target_node_id not in visited:
                    new_step = InferenceStep(
                        from_node_id=current_id,
                        to_node_id=edge.target_node_id,
                        edge_type=edge.edge_type,
                        confidence=edge.weight,
                        step_index=len(path),
                    )
                    new_path = path + [new_step]
                    new_confidence = confidence * edge.weight
                    queue.append((edge.target_node_id, new_path, new_confidence))

        if not results:
            return None

        # Return highest confidence result
        results.sort(key=lambda x: -x[2])
        best_id, best_path, best_conf = results[0]

        return InferenceResult(
            query_node_id=start_node_id,
            result_node_ids=tuple(r[0] for r in results),
            inference_path=tuple(best_path),
            total_confidence=best_conf,
        )

    def propagate_ppv_influence(
        self,
        ppv_node_id: str,
        target_layer: int,
    ) -> Tuple[Tuple[str, float], ...]:
        """
        Propagate PPV influence through graph to target layer.

        Returns concept IDs at target layer with influence scores.
        """
        result = self.find_path(ppv_node_id, target_layer)
        if result is None:
            return ()

        # Collect all reached concepts with confidence
        concept_scores: List[Tuple[str, float]] = []
        for node_id in result.result_node_ids:
            node = self._graph.get_node(node_id)
            if isinstance(node, ConceptNode):
                concept_scores.append((node_id, result.total_confidence))

        return tuple(sorted(concept_scores, key=lambda x: -x[1]))
```

---

## 4. Integration with Existing Pipeline

### 4.1 Phase-10 to Graph Integration

```python
def phase10_to_graph_nodes(
    envelope: Phase10Envelope,
    graph: TypedGraphStore,
) -> Tuple[str, ...]:
    """
    Convert Phase10Envelope to graph nodes.

    Creates:
        - PhonemeNodes for each phoneme in source
        - PropensityNode for PPV (if present)
        - Edges connecting phonemes to PPV

    Returns:
        Tuple of created node IDs.
    """
    created_ids = []

    # Create PPV propensity node if present
    if envelope.has_ppv:
        ppv = envelope.ppv
        ppv_node = PropensityNode(
            node_id=compute_node_hash(NodeType.PROPENSITY, ppv.ppv_hash),
            node_type=NodeType.PROPENSITY,
            ppv_values=ppv.values,
            ppv_aggregate=ppv.aggregate,
            source_spans=ppv.source_unit_span_ids,
        )
        graph.add_node(ppv_node)
        created_ids.append(ppv_node.node_id)

    return tuple(created_ids)
```

### 4.2 Phase-11 Template Enhancement

PPV-aware templates integrate graph-derived concepts:

```python
def render_with_graph_context(
    vc_extraction: VCExtraction,
    ppv_metrics: PPVMetrics,
    graph: TypedGraphStore,
    engine: InferenceEngine,
) -> TemplateRenderResult:
    """
    Render template with graph-derived context.

    Enhances PPV metrics with inferred concept correlations.
    """
    # Get PPV node from graph
    if ppv_metrics.ppv_present and ppv_metrics.ppv_hash_prefix:
        # Find concept correlations at affective layer
        correlations = engine.propagate_ppv_influence(
            ppv_node_id=...,  # Look up by hash
            target_layer=3,  # Affective layer
        )
        # Include top correlations in template context
        # (Still numeric-only for GOVERNED safety)

    return render_template_with_ppv(vc_extraction, acoustic_regime, ppv_metrics)
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

```python
class TestGraphSchema:
    """Tests for graph schema invariants."""

    def test_concept_node_validation(self):
        """ConceptNode validates all invariants."""
        # Valid node
        node = ConceptNode(
            node_id="a" * 64,
            node_type=NodeType.CONCEPT,
            concept_label="test",
            ontology_layer=3,
            feature_vector=(1, 2, 3),
            parent_ids=(),
            child_ids=(),
            ppv_correlation=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
        )
        assert node.ontology_layer == 3

    def test_concept_node_rejects_invalid_layer(self):
        """ConceptNode rejects out-of-range ontology layer."""
        with pytest.raises(ValueError, match="ontology_layer must be 0-6"):
            ConceptNode(
                node_id="a" * 64,
                node_type=NodeType.CONCEPT,
                concept_label="test",
                ontology_layer=10,  # Invalid
                ...
            )

class TestInferenceEngine:
    """Tests for inference engine."""

    def test_deterministic_path_finding(self):
        """Path finding produces identical results for identical inputs."""
        # Run 100 times, verify identical results
        results = [engine.find_path(start_id, target_layer=3) for _ in range(100)]
        assert len(set(r.total_confidence for r in results)) == 1
```

### 5.2 Integration Tests

```python
class TestPipelineIntegration:
    """Tests for full pipeline integration."""

    def test_ppv_to_graph_to_template(self):
        """Full flow: PPV -> Graph -> Inference -> Template."""
        # Create PPV
        ppv = create_ppv_vector(values=(3, 4, 2, 5, 4, 2, 3, 4), ...)

        # Wrap in envelope
        envelope = create_phase10_envelope(phase10_result, ppv)

        # Add to graph
        node_ids = phase10_to_graph_nodes(envelope, graph)

        # Run inference
        result = engine.propagate_ppv_influence(node_ids[0], target_layer=3)

        # Verify deterministic
        assert result == engine.propagate_ppv_influence(node_ids[0], target_layer=3)
```

---

## 6. Performance Considerations

### 6.1 Graph Size Limits

| Component | Limit | Rationale |
|-----------|-------|-----------|
| Nodes per graph | 100,000 | Memory bounds |
| Edges per node | 1,000 | Traversal performance |
| Path depth | 10 | Inference complexity |
| PPV correlations per node | 100 | Query performance |

### 6.2 Caching Strategy

```python
class CachedInferenceEngine(InferenceEngine):
    """Inference engine with deterministic caching."""

    def __init__(self, graph: TypedGraphStore, cache_size: int = 10000):
        super().__init__(graph)
        self._cache: Dict[str, InferenceResult] = {}
        self._cache_order: List[str] = []
        self._cache_size = cache_size

    def find_path(self, start_node_id: str, target_layer: int, ...) -> ...:
        cache_key = f"{start_node_id}|{target_layer}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = super().find_path(start_node_id, target_layer, ...)

        # LRU eviction
        if len(self._cache) >= self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]

        self._cache[cache_key] = result
        self._cache_order.append(cache_key)

        return result
```

---

## 7. Deployment

### 7.1 Configuration

```python
# config/graph_config.py
GRAPH_CONFIG = {
    "max_nodes": 100_000,
    "max_edges_per_node": 1_000,
    "max_inference_depth": 10,
    "cache_size": 10_000,
    "governed_mode": True,
}
```

### 7.2 Initialization

```python
def initialize_typed_graph_system() -> Tuple[TypedGraphStore, InferenceEngine]:
    """Initialize the typed graph system."""
    graph = TypedGraphStore()
    engine = CachedInferenceEngine(graph, cache_size=GRAPH_CONFIG["cache_size"])
    return graph, engine
```

---

*Implementation specification for Symbol-U Typed Graph LLM architecture.*
