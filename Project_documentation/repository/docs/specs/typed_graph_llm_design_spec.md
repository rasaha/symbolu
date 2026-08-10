# Typed Graph LLM Design Specification

## Document Information

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Draft |
| Domain | Symbol-U / Soulpi Architecture |

---

## 1. Executive Summary

This specification defines a **Typed Graph LLM** architecture that integrates:
- **Phonemic Propensity Vectors (PPV)** for structural acoustic signals
- **Ontological layer mapping** for semantic organization
- **Graph-based knowledge representation** for reasoning
- **RAG (Retrieval-Augmented Generation)** for dynamic knowledge updates

The architecture preserves Symbol-U's core safety guarantees (GOVERNED mode, verifier-provable outputs) while enabling richer semantic and acoustic integration.

---

## 2. Architecture Overview

### 2.1 System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│  (User interfaces, API endpoints, rendering surfaces)            │
├─────────────────────────────────────────────────────────────────┤
│                    REASONING LAYER                               │
│  (Graph traversal, inference engine, constraint satisfaction)    │
├─────────────────────────────────────────────────────────────────┤
│                    SEMANTIC LAYER                                │
│  (Ontological mapping, concept relations, meaning structures)    │
├─────────────────────────────────────────────────────────────────┤
│                    ACOUSTIC LAYER                                │
│  (PPV vectors, phonemic features, prosodic patterns)             │
├─────────────────────────────────────────────────────────────────┤
│                    KNOWLEDGE LAYER                               │
│  (RAG database, vector embeddings, graph store)                  │
├─────────────────────────────────────────────────────────────────┤
│                    VERIFICATION LAYER                            │
│  (Deterministic checks, safety boundaries, ledger recording)     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Design Principles

1. **Determinism First**: All operations produce identical outputs for identical inputs
2. **Type Safety**: Strong typing at every layer boundary
3. **Verifiable Outputs**: All generated content passes verifier checks
4. **Separation of Concerns**: Acoustic signals distinct from semantic meaning
5. **Fail-Closed Safety**: GOVERNED mode blocks unverified outputs

---

## 3. Typed Graph Architecture

### 3.1 Node Types

The graph consists of strongly-typed nodes representing different knowledge entities:

```
NodeType ::=
    | ConceptNode          -- Abstract concepts (e.g., "emotion", "color")
    | PhonemeNode          -- Phonemic units with PPV features
    | LexemeNode           -- Word-level representations
    | OntologyNode         -- Ontological category markers
    | PropensityNode       -- PPV dimension values
    | RelationNode         -- Edge type definitions
    | ConstraintNode       -- Validation constraints
```

#### 3.1.1 ConceptNode Schema

```python
@dataclass(frozen=True)
class ConceptNode:
    """Represents an abstract concept in the knowledge graph."""
    node_id: str                    # Unique identifier (hash-based)
    concept_label: str              # Human-readable label
    ontology_layer: int             # 0-6 (see Ontology Layers)
    feature_vector: Tuple[int, ...]  # Fixed-length numeric features
    parent_concepts: Tuple[str, ...] # Parent node IDs
    child_concepts: Tuple[str, ...]  # Child node IDs
    ppv_correlation: Tuple[float, ...] # Correlation with PPV dimensions
```

#### 3.1.2 PhonemeNode Schema

```python
@dataclass(frozen=True)
class PhonemeNode:
    """Represents a phoneme with acoustic propensity features."""
    node_id: str                    # Unique identifier
    phoneme_id: str                 # IPA symbol or internal ID
    ppv_features: Tuple[int, ...]   # 8-dimensional PPV features (0-7)
    articulation_class: str         # Consonant/Vowel/Glide classification
    sonority_rank: int              # 0-10 sonority scale
    adjacency_affinity: Tuple[str, ...] # Compatible adjacent phonemes
```

### 3.2 Edge Types

Edges define relationships between nodes with semantic typing:

```
EdgeType ::=
    | IS_A                  -- Ontological inheritance
    | HAS_PART              -- Compositional relationship
    | CORRELATES_WITH       -- Statistical association
    | TRIGGERS              -- Causal relationship
    | CONSTRAINS            -- Validation constraint
    | ACOUSTIC_MAPS_TO      -- PPV to semantic mapping
    | TEMPORAL_PRECEDES     -- Sequence ordering
```

#### 3.2.1 Edge Schema

```python
@dataclass(frozen=True)
class TypedEdge:
    """Strongly-typed edge in the knowledge graph."""
    edge_id: str                    # Unique identifier
    source_node_id: str             # Source node
    target_node_id: str             # Target node
    edge_type: EdgeType             # Relationship type
    weight: float                   # Relationship strength (0.0-1.0)
    metadata: Tuple[Tuple[str, str], ...]  # Key-value metadata pairs
    version: str                    # Schema version
```

### 3.3 Graph Constraints

The typed graph enforces structural invariants:

1. **Acyclic Ontology**: IS_A edges form a DAG (no cycles)
2. **PPV Boundedness**: All PPV values in range [0, 7]
3. **Hash Stability**: Node/edge IDs are deterministic SHA-256 hashes
4. **Referential Integrity**: All edge endpoints must exist
5. **Layer Consistency**: Nodes only connect to adjacent ontology layers

---

## 4. Phonemic Propensity Integration

### 4.1 PPV as Structural Signal

PPV provides **structural acoustic signals**, not emotional meaning:

| PPV Dimension | Signal Type | Range |
|--------------|-------------|-------|
| EDGE_TENSION | Articulatory effort | 0-7 |
| EDGE_RELEASE | Release characteristics | 0-7 |
| ONSET_SHARPNESS | Attack profile | 0-7 |
| SONORITY_LIFT | Sonority trajectory | 0-7 |
| CONTINUITY | Flow maintenance | 0-7 |
| DISCONTINUITY | Interruption markers | 0-7 |
| RHYTHMIC_IMPULSE | Temporal patterning | 0-7 |
| STABILITY_PRESSURE | Articulatory stability | 0-7 |

### 4.2 PPV-to-Semantic Mapping

PPV values map to semantic concepts through **learned correlations**, not hard-coded rules:

```python
@dataclass(frozen=True)
class PPVSemanticMapping:
    """Maps PPV patterns to semantic concept correlations."""
    ppv_pattern: Tuple[int, ...]    # 8-dimensional pattern
    pattern_hash: str               # Deterministic hash
    concept_correlations: Tuple[Tuple[str, float], ...]  # (concept_id, weight)
    confidence: float               # Mapping confidence (0.0-1.0)
    source: str                     # Mapping source (empirical/theoretical)
```

### 4.3 Emotional Propensity vs. Structural Signal

**Critical Distinction**:
- PPV captures **phonemic structural patterns** (acoustic features)
- Emotional inference is **downstream interpretation** (semantic layer)
- Symbol-U does NOT claim PPV = emotion; PPV informs emotion-relevant patterns

```
PPV (Structural) → Ontology Mapping → Semantic Concepts → Emotional Categories
      ↑                   ↑                  ↑                    ↑
   Numeric only     Graph traversal    Type-checked      Application-level
   Deterministic    Verifiable         Bounded           User-interpreted
```

---

## 5. Ontological Layer Architecture

### 5.1 Seven-Layer Ontology Model

```
Layer 6: PHENOMENAL      -- Subjective experience concepts
Layer 5: INTENTIONAL     -- Goal/purpose representations
Layer 4: EVALUATIVE      -- Value judgments, preferences
Layer 3: AFFECTIVE       -- Emotion categories (joy, fear, etc.)
Layer 2: PERCEPTUAL      -- Sensory pattern recognition
Layer 1: ACOUSTIC        -- Phonemic/prosodic features
Layer 0: PHYSICAL        -- Raw signal characteristics
```

### 5.2 Layer Transition Rules

Concepts propagate between layers through typed transitions:

```python
LAYER_TRANSITIONS: Dict[int, Tuple[int, ...]] = {
    0: (1,),           # Physical → Acoustic only
    1: (0, 2),         # Acoustic ↔ Physical, Perceptual
    2: (1, 3),         # Perceptual ↔ Acoustic, Affective
    3: (2, 4),         # Affective ↔ Perceptual, Evaluative
    4: (3, 5),         # Evaluative ↔ Affective, Intentional
    5: (4, 6),         # Intentional ↔ Evaluative, Phenomenal
    6: (5,),           # Phenomenal → Intentional only
}
```

### 5.3 PPV Integration Points

PPV enters at Layer 1 (Acoustic) and influences higher layers through graph traversal:

```
PPVVector → PhonemeNode (L1) → PerceptualPattern (L2) → AffectiveCategory (L3)
                ↓
         Deterministic        Graph-based           Typed mapping
         Hash-stable          Verifiable            Bounded values
```

---

## 6. Comparison: Symbol-U vs. ChatGPT Approach

### 6.1 Architecture Comparison

| Aspect | Symbol-U (Typed Graph) | ChatGPT (Transformer) |
|--------|----------------------|----------------------|
| **Knowledge Representation** | Explicit typed graph | Implicit in weights |
| **Verifiability** | Full verifier pipeline | Black-box outputs |
| **Determinism** | Guaranteed (same input→same output) | Non-deterministic (temperature) |
| **PPV Integration** | First-class numeric artifact | Would require fine-tuning |
| **Safety Mode** | GOVERNED (fail-closed) | Guardrails (soft filters) |
| **Ontology** | Explicit layer structure | Emergent from training |
| **Auditability** | Complete ledger trail | Limited logging |

### 6.2 Strengths and Trade-offs

**Symbol-U Typed Graph Strengths**:
- Provably safe outputs in GOVERNED mode
- Deterministic, reproducible results
- Explicit knowledge structure
- Fine-grained PPV integration
- Full audit trail

**ChatGPT Transformer Strengths**:
- Broader knowledge coverage
- Natural language fluency
- Transfer learning capability
- Rapid prototyping
- Large-scale pre-training

### 6.3 Hybrid Approach

For optimal results, combine approaches:

```
ChatGPT (Generation) → Symbol-U Verifier → GOVERNED Output
         ↓                    ↓                   ↓
   Draft content        Safety checks        Verified result
   Fluent text          PPV validation       Ledger recorded
```

---

## 7. Technical Specifications

### 7.1 Data Types

```python
# Core types for typed graph
NodeID = NewType('NodeID', str)      # 64-char hex hash
EdgeID = NewType('EdgeID', str)      # 64-char hex hash
LayerID = NewType('LayerID', int)    # 0-6
PPVValue = NewType('PPVValue', int)  # 0-7

# Composite types
PPVTuple = Tuple[PPVValue, PPVValue, PPVValue, PPVValue,
                 PPVValue, PPVValue, PPVValue, PPVValue]
ConceptID = NewType('ConceptID', str)
OntologyPath = Tuple[LayerID, ...]
```

### 7.2 Hash Computation

All identifiers use deterministic SHA-256:

```python
def compute_node_hash(
    node_type: str,
    node_content: str,
    version: str = "1.0",
) -> str:
    """Compute deterministic node hash."""
    hash_input = f"node:{node_type}|content:{node_content}|v:{version}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
```

### 7.3 Graph Query Interface

```python
class TypedGraphQuery:
    """Query interface for typed knowledge graph."""

    def get_node(self, node_id: NodeID) -> Optional[Node]: ...
    def get_edges(self, source_id: NodeID, edge_type: EdgeType) -> Tuple[TypedEdge, ...]: ...
    def traverse(self, start: NodeID, path: OntologyPath) -> Tuple[Node, ...]: ...
    def ppv_correlates(self, ppv: PPVVector, layer: LayerID) -> Tuple[Tuple[ConceptID, float], ...]: ...
```

---

## 8. Security and Safety

### 8.1 GOVERNED Mode Guarantees

In GOVERNED mode, the typed graph enforces:

1. **No free-form string generation** from PPV
2. **Template-bound outputs** with numeric-only PPV slots
3. **Verifier validation** before any output release
4. **Ledger recording** of all operations
5. **Fail-closed behavior** on any validation failure

### 8.2 Constraint Verification

```python
def verify_graph_constraints(graph: TypedGraph) -> VerificationReport:
    """Verify all graph invariants."""
    checks = [
        check_acyclic_ontology(graph),
        check_ppv_bounds(graph),
        check_hash_stability(graph),
        check_referential_integrity(graph),
        check_layer_consistency(graph),
    ]
    return VerificationReport(
        passed=all(c.passed for c in checks),
        checks=tuple(checks),
    )
```

---

## 9. Future Extensions

### 9.1 Planned Enhancements

1. **Temporal Graph**: Add time-series PPV evolution tracking
2. **Multi-modal PPV**: Extend to visual/tactile modalities
3. **Federated Graphs**: Cross-repository knowledge sharing
4. **Incremental Updates**: Delta-based graph modifications
5. **Confidence Propagation**: Uncertainty through graph layers

### 9.2 Research Directions

- PPV-semantic correlation studies
- Ontology layer optimization
- Graph compression techniques
- Real-time PPV streaming

---

## 10. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **PPV** | Phonemic Propensity Vector - 8-dimensional numeric structural signal |
| **GOVERNED Mode** | Safety mode where outputs are blocked if verification fails |
| **Typed Graph** | Knowledge representation with strongly-typed nodes and edges |
| **Ontology Layer** | Hierarchical semantic organization level (0-6) |
| **Verifier** | Component that validates outputs against safety constraints |

### B. References

- Symbol-U Phase-10/11 Architecture
- PPV Contract v1.0 Specification
- Ontological Semantics Literature
- Graph Database Best Practices

---

*Document generated for Symbol-U/Soulpi architecture comparison and design reference.*
