# Symbolu Architecture Master Specification

## Document Information

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Consolidated |
| Date | 2025-12-16 |
| Domain | Symbol-U / Soulpi Complete Architecture |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Typed Graph LLM Architecture](#3-typed-graph-llm-architecture)
4. [PPV Integration with Emotional Propensity](#4-ppv-integration-with-emotional-propensity)
5. [Ontological Layer Semantics Mapping](#5-ontological-layer-semantics-mapping)
6. [RAG Database Update Strategies](#6-rag-database-update-strategies)
7. [Reasoning Generation Mechanisms](#7-reasoning-generation-mechanisms)
8. [Technical Comparison: Symbol-U vs ChatGPT](#8-technical-comparison-symbol-u-vs-chatgpt)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Cross-Reference Index](#10-cross-reference-index)

---

## 1. Executive Summary

This master specification consolidates the complete Symbol-U (Soulpi) architecture, integrating:

- **Typed Graph LLM**: Explicit knowledge representation with verifiable outputs
- **PPV (Phonemic Propensity Vectors)**: 8-dimensional acoustic-structural signals
- **Ontological Layers**: 7-tier semantic organization (Physical → Phenomenal)
- **RAG Integration**: Retrieval-augmented generation with deterministic updates
- **Reasoning Engine**: Graph-based inference with explainable traces

### Core Design Philosophy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SYMBOL-U ARCHITECTURE PILLARS                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   DETERMINISM          VERIFIABILITY         SAFETY-FIRST               │
│   ──────────────       ──────────────        ──────────────             │
│   Same input →         All outputs           GOVERNED mode              │
│   Same output          verifier-checked      fail-closed                │
│                                                                          │
│   TYPE-SAFETY          SEPARATION            AUDITABILITY               │
│   ──────────────       ──────────────        ──────────────             │
│   Strong typing        Acoustic ≠            Complete ledger            │
│   at all layers        Semantic              trail                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Related Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Typed Graph LLM Design | `typed_graph_llm_design_spec.md` | Architecture design |
| Typed Graph LLM Implementation | `typed_graph_llm_implementation_spec.md` | Code structures |
| RAG & Reasoning | `rag_database_reasoning_spec.md` | Knowledge management |
| Phase-2 Modifier Layer | `phase2_modifier_layer_spec_v3_2.md` | Acoustic processing |

---

## 2. Architecture Overview

### 2.1 System Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 7: APPLICATION                                                     │
│   ├── User Interfaces                                                    │
│   ├── API Endpoints                                                      │
│   └── Rendering Surfaces                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 6: REASONING                                                       │
│   ├── Inference Engine (graph traversal)                                 │
│   ├── Constraint Solver                                                  │
│   └── Reasoning Trace Generator                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 5: SEMANTIC                                                        │
│   ├── Ontology Mapping (7 layers)                                        │
│   ├── Concept Relations                                                  │
│   └── Meaning Structures                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: ACOUSTIC                                                        │
│   ├── PPV Vectors (8 dimensions)                                         │
│   ├── Phonemic Features                                                  │
│   └── Prosodic Patterns                                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: KNOWLEDGE                                                       │
│   ├── RAG Database                                                       │
│   ├── Vector Embeddings                                                  │
│   └── Typed Graph Store                                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: VERIFICATION                                                    │
│   ├── Deterministic Checks                                               │
│   ├── Safety Boundaries                                                  │
│   └── Ledger Recording                                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: PIPELINE                                                        │
│   ├── Phase-10 Acoustic Envelope                                         │
│   ├── Phase-11 Template Controller                                       │
│   └── Phase-11B.1 Collision-Free Routing                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Input Artifact
     │
     ▼
┌──────────────────┐
│ Phase-10: PPV    │ ─── Compute 8-dimensional PPV vector
│ Envelope         │     (deterministic acoustic features)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Phase-11B.1:     │ ─── SubBand routing (L0-L2, M0-M2, H0-H1)
│ Routing          │     Collision-free template selection
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Typed Graph      │ ─── Knowledge lookup
│ Query            │     Ontology traversal
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ RAG Retrieval    │ ─── Multi-modal knowledge retrieval
│ + Reasoning      │     Chain/Tree/Graph of thought
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Verification     │ ─── GOVERNED: block if unverified
│ + Ledger         │     Record all operations
└────────┬─────────┘
         │
         ▼
Verified Output
```

---

## 3. Typed Graph LLM Architecture

### 3.1 Node Type Hierarchy

```python
NodeType ::=
    | ConceptNode      # Abstract concepts with PPV correlations
    | PhonemeNode      # Phonemic units with 8-dim PPV features
    | LexemeNode       # Word-level representations
    | OntologyNode     # Layer markers (0-6)
    | PropensityNode   # PPV dimension values
    | RelationNode     # Edge type definitions
    | ConstraintNode   # Validation constraints
```

### 3.2 Edge Type Hierarchy

```python
EdgeType ::=
    | IS_A              # Ontological inheritance
    | HAS_PART          # Compositional relationship
    | CORRELATES_WITH   # Statistical association
    | TRIGGERS          # Causal relationship
    | CONSTRAINS        # Validation constraint
    | ACOUSTIC_MAPS_TO  # PPV → semantic mapping
    | TEMPORAL_PRECEDES # Sequence ordering
```

### 3.3 Graph Constraints

| Constraint | Description | Enforcement |
|------------|-------------|-------------|
| Acyclic Ontology | IS_A edges form DAG | Pre-commit validation |
| PPV Boundedness | All values [0, 7] | Schema validation |
| Hash Stability | IDs are SHA-256 | Deterministic computation |
| Referential Integrity | Edge endpoints exist | Add-time check |
| Layer Consistency | Adjacent layers only | Schema constraint |

### 3.4 Schema Definitions

```python
@dataclass(frozen=True)
class ConceptNode:
    """Abstract concept in knowledge graph."""
    node_id: str                    # 64-char SHA-256 hex
    concept_label: str              # Human-readable label
    ontology_layer: int             # 0-6 (Physical → Phenomenal)
    feature_vector: Tuple[int, ...]  # Numeric features
    parent_ids: Tuple[str, ...]     # Parent concept IDs
    child_ids: Tuple[str, ...]      # Child concept IDs
    ppv_correlation: Tuple[float, ...] # 8-dim correlation [-1.0, 1.0]

@dataclass(frozen=True)
class PhonemeNode:
    """Phoneme with PPV features."""
    node_id: str
    phoneme_id: str                 # IPA symbol
    ppv_features: Tuple[int, ...]   # 8 values (0-7 each)
    articulation_class: str         # Consonant/Vowel/Glide
    sonority_rank: int              # 0-10
    adjacency_affinity: Tuple[str, ...]  # Compatible neighbors

@dataclass(frozen=True)
class TypedEdge:
    """Strongly-typed edge."""
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    weight: float                   # 0.0-1.0
    metadata: Tuple[Tuple[str, str], ...]
```

---

## 4. PPV Integration with Emotional Propensity

### 4.1 PPV as Structural Signal (NOT Emotion)

**Critical Distinction**:

```
PPV → Structural acoustic patterns (NUMERIC)
   ↓
Ontology Mapping → Semantic concepts (TYPED)
   ↓
Downstream Interpretation → Emotional categories (APPLICATION)
```

PPV captures **phonemic structural patterns**, not emotions directly:

| PPV Dimension | Acoustic Signal | Value Range |
|---------------|-----------------|-------------|
| EDGE_TENSION | Articulatory effort | 0-7 |
| EDGE_RELEASE | Release characteristics | 0-7 |
| ONSET_SHARPNESS | Attack profile | 0-7 |
| SONORITY_LIFT | Sonority trajectory | 0-7 |
| CONTINUITY | Flow maintenance | 0-7 |
| DISCONTINUITY | Interruption markers | 0-7 |
| RHYTHMIC_IMPULSE | Temporal patterning | 0-7 |
| STABILITY_PRESSURE | Articulatory stability | 0-7 |

### 4.2 PPV-to-Semantic Mapping

PPV values correlate with semantic concepts through **learned mappings**:

```python
@dataclass(frozen=True)
class PPVSemanticMapping:
    """Maps PPV patterns to semantic correlations."""
    ppv_pattern: Tuple[int, ...]    # 8-dimensional pattern
    pattern_hash: str               # Deterministic hash
    concept_correlations: Tuple[Tuple[str, float], ...]
    confidence: float               # 0.0-1.0
    source: str                     # "empirical" or "theoretical"
```

### 4.3 Emotional Propensity Derivation

Emotional propensity is a **downstream interpretation**, not direct PPV output:

```
                           ┌─────────────────────────────────────┐
                           │  EMOTIONAL PROPENSITY DERIVATION    │
                           └─────────────────────────────────────┘

PPV Vector ──────┐
(8 dimensions)   │
                 ▼
          ┌──────────────────┐
          │  Layer 1:        │ ─── Direct PPV features
          │  ACOUSTIC        │     (tension, release, etc.)
          └────────┬─────────┘
                   │
                   ▼ Graph traversal
          ┌──────────────────┐
          │  Layer 2:        │ ─── Perceptual patterns
          │  PERCEPTUAL      │     (rhythm, contour, etc.)
          └────────┬─────────┘
                   │
                   ▼ Inference
          ┌──────────────────┐
          │  Layer 3:        │ ─── Affect categories
          │  AFFECTIVE       │     (joy, fear, anger, etc.)
          └────────┬─────────┘
                   │
                   ▼ Application interpretation
          ┌──────────────────────────────────────────────────────┐
          │  EMOTIONAL PROPENSITY                                 │
          │  ──────────────────                                   │
          │  • Derived, not computed                              │
          │  • Context-dependent                                  │
          │  • User-interpreted                                   │
          │  • NOT claimed as ground truth                        │
          └──────────────────────────────────────────────────────┘
```

### 4.4 PPV Dimension Relevance by Layer

| Layer | Relevant PPV Dimensions |
|-------|------------------------|
| 0: Physical | (none - raw signals) |
| 1: Acoustic | ALL 8 dimensions |
| 2: Perceptual | onset_sharpness, sonority_lift, rhythmic_impulse |
| 3: Affective | edge_tension, edge_release, stability_pressure |
| 4: Evaluative | continuity, discontinuity |
| 5: Intentional | rhythmic_impulse, stability_pressure |
| 6: Phenomenal | (none - high-level interpretation) |

---

## 5. Ontological Layer Semantics Mapping

### 5.1 Seven-Layer Ontology Model

```
Layer 6: PHENOMENAL      ─── Subjective experience concepts
         │
         ▼
Layer 5: INTENTIONAL     ─── Goal/purpose representations
         │
         ▼
Layer 4: EVALUATIVE      ─── Value judgments, preferences
         │
         ▼
Layer 3: AFFECTIVE       ─── Emotion categories (joy, fear, etc.)
         │
         ▼
Layer 2: PERCEPTUAL      ─── Sensory pattern recognition
         │
         ▼
Layer 1: ACOUSTIC        ─── Phonemic/prosodic features
         │
         ▼
Layer 0: PHYSICAL        ─── Raw signal characteristics
```

### 5.2 Layer Transition Rules

Concepts propagate between **adjacent layers only**:

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

### 5.3 Mapping Semantics

Each ontological layer has specific semantic content:

| Layer | Semantic Content | Example Concepts |
|-------|------------------|------------------|
| Physical | Signal properties | frequency, amplitude, duration |
| Acoustic | Phoneme features | voiced, fricative, plosive |
| Perceptual | Pattern recognition | rhythm, contour, salience |
| Affective | Emotion categories | joy, sadness, anger, fear |
| Evaluative | Value judgments | good/bad, desirable/undesirable |
| Intentional | Goals/purposes | seeking, avoiding, expressing |
| Phenomenal | Experience qualities | vivid, faint, clear, confused |

### 5.4 PPV Integration Points

PPV enters at Layer 1 (Acoustic) and propagates upward:

```python
def propagate_ppv_influence(
    ppv_node_id: str,
    target_layer: int,
    graph: TypedGraphStore,
    engine: InferenceEngine,
) -> Tuple[Tuple[str, float], ...]:
    """
    Propagate PPV influence through ontology layers.

    Returns concept IDs at target layer with influence scores.
    """
    # BFS from PPV node to target layer
    result = engine.find_path(ppv_node_id, target_layer, max_depth=5)

    if result is None:
        return ()

    # Return (concept_id, confidence) pairs
    return tuple(
        (node_id, result.total_confidence)
        for node_id in result.result_node_ids
    )
```

---

## 6. RAG Database Update Strategies

### 6.1 Update Type Matrix

| Update Type | Frequency | Validation | Reindex Scope |
|-------------|-----------|------------|---------------|
| **Batch Ingest** | Periodic (daily/weekly) | Full validation | Full reindex |
| **Incremental** | Real-time | Standard validation | Affected chunks |
| **Delta Merge** | On-demand | Diff validation | Changed content |
| **Graph Extension** | Event-driven | Schema validation | New nodes/edges |
| **PPV Enhancement** | Batch | PPV invariant check | PPV index only |

### 6.2 Ingestion Pipeline

```
Document ─────────────────────────────────────────────────────────►
    │
    ├─► STAGE 1: INGEST
    │      Accept raw document
    │
    ├─► STAGE 2: VALIDATE
    │      Schema check, forbidden patterns
    │
    ├─► STAGE 3: CHUNK
    │      Split into embeddable chunks (512 tokens, 64 overlap)
    │
    ├─► STAGE 4: EMBED
    │      Generate vector embeddings
    │
    ├─► STAGE 5: INDEX
    │      Add to vector store + graph store
    │
    ├─► STAGE 6: VERIFY
    │      Confirm successful indexing
    │
    └─► STAGE 7: COMMIT
           Finalize, record in ledger
```

### 6.3 Incremental Update Strategy

```python
class IncrementalUpdateHandler:
    """Minimal reindexing for incremental updates."""

    def apply_update(self, update: IncrementalUpdate) -> PipelineResult:
        if update.update_type == "append":
            # Only index NEW chunks (avoid full reindex)
            return self._handle_append(update)

        elif update.update_type == "replace":
            # Reindex AFFECTED chunks only
            return self._handle_replace(update)

        elif update.update_type == "delete":
            # Soft delete with tombstone
            return self._handle_delete(update)
```

### 6.4 PPV-Enhanced Indexing

Documents can be enhanced with PPV for acoustic-aware retrieval:

```python
class PPVEnhancedIndexer:
    """Index with PPV enhancement for acoustic retrieval."""

    def index_with_ppv(
        self,
        chunk: DocumentChunk,
        ppv_context: Optional[Dict[str, Any]] = None,
    ) -> IndexResult:
        # Attempt PPV extraction from text
        ppv = self._extract_ppv_from_text(chunk.content, ppv_context)

        if ppv is not None:
            # Store PPV alongside embedding
            # Add PPV-concept correlations to graph
            # Tag with ontology layer markers
            return self._index_with_ppv_enhancement(chunk, ppv)
        else:
            return self._index_standard(chunk)
```

### 6.5 Consistency Guarantees

All updates are **atomic** across stores:

```python
def apply_atomic_update(
    vector_updates: Tuple[VectorUpdate, ...],
    graph_updates: Tuple[GraphUpdate, ...],
) -> AtomicUpdateResult:
    """All-or-nothing update to both stores."""

    vector_txn = vector_store.begin_transaction()
    graph_txn = graph_store.begin_transaction()

    try:
        for update in vector_updates:
            vector_txn.apply(update)
        for update in graph_updates:
            graph_txn.apply(update)

        vector_txn.commit()
        graph_txn.commit()
        return AtomicUpdateResult(success=True)

    except Exception:
        vector_txn.rollback()
        graph_txn.rollback()
        return AtomicUpdateResult(success=False)
```

---

## 7. Reasoning Generation Mechanisms

### 7.1 Reasoning Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Chain-of-Thought** | Sequential reasoning steps | Simple inference |
| **Tree-of-Thought** | Branching exploration | Multiple hypotheses |
| **Graph-of-Thought** | Multi-path fusion | Complex reasoning |

### 7.2 Reasoning Pipeline

```
Query
  │
  ├─► RETRIEVAL
  │     Multi-modal search (vector, graph, keyword, PPV)
  │
  ├─► CONTEXT ASSEMBLY
  │     Build context graph from retrieved items
  │
  ├─► INFERENCE
  │     Graph traversal through ontology layers
  │
  ├─► GENERATION
  │     Template-bound output generation
  │
  └─► VERIFICATION
        Claim verification, source attribution
```

### 7.3 Reasoning Trace Schema

```python
@dataclass(frozen=True)
class ReasoningStep:
    """Single step in reasoning chain."""
    step_id: str
    step_index: int
    step_type: str  # "retrieve", "infer", "combine", "conclude"
    input_ids: Tuple[str, ...]
    output_id: str
    confidence: float
    explanation: str
    source_refs: Tuple[str, ...]

@dataclass(frozen=True)
class ReasoningTrace:
    """Complete reasoning trace."""
    trace_id: str
    query: str
    steps: Tuple[ReasoningStep, ...]
    final_conclusion: str
    total_confidence: float
    sources_used: Tuple[str, ...]
    trace_hash: str
```

### 7.4 Chain-of-Thought Implementation

```python
def chain_of_thought(query: str, max_steps: int) -> ReasoningTrace:
    """
    Sequential reasoning:
    1. Retrieve relevant context
    2. Extract key facts from each document
    3. Build inference chain through graph
    4. Derive conclusion with source attribution
    """
    steps = []
    sources_used = []

    # Step 1: Retrieve
    retrieval = retriever.retrieve(query, top_k=5)
    for result in retrieval.results:
        sources_used.append(result.doc_id)

    steps.append(ReasoningStep(
        step_type="retrieve",
        explanation=f"Retrieved {len(retrieval.results)} documents",
        source_refs=tuple(r.doc_id for r in retrieval.results),
        ...
    ))

    # Step 2: Extract facts
    facts = []
    for result in retrieval.results[:3]:
        doc = get_document(result.doc_id)
        extracted = extract_facts(doc, query)
        facts.extend(extracted)

        steps.append(ReasoningStep(
            step_type="extract",
            explanation=f"Extracted {len(extracted)} facts",
            ...
        ))

    # Step 3: Graph inference
    if facts:
        inference_result = run_inference(facts, query)
        steps.append(ReasoningStep(
            step_type="infer",
            explanation=inference_result.explanation,
            ...
        ))

    # Step 4: Conclude
    conclusion = derive_conclusion(query, facts, steps)
    steps.append(ReasoningStep(
        step_type="conclude",
        explanation=conclusion.text,
        ...
    ))

    return ReasoningTrace(
        query=query,
        steps=tuple(steps),
        final_conclusion=conclusion.text,
        total_confidence=conclusion.confidence,
        sources_used=tuple(sources_used),
        ...
    )
```

### 7.5 Claim Verification

All claims must be verified against sources:

```python
def verify_claim(
    claim: str,
    sources: Tuple[str, ...],
) -> VerificationResult:
    """
    Verify claim against provided sources.

    GOVERNED mode requires:
    - All claims have source attribution
    - Claims are consistent with sources
    - No hallucinated facts
    """
    evidence = []
    for source_id in sources:
        doc = get_document(source_id)
        support = find_support(claim, doc)
        if support:
            evidence.append((source_id, support))

    support_level = len(evidence) / len(sources)

    return VerificationResult(
        claim=claim,
        verified=support_level > 0.5,
        support_level=support_level,
        evidence=tuple(evidence),
    )
```

---

## 8. Technical Comparison: Symbol-U vs ChatGPT

### 8.1 Architecture Comparison

| Aspect | Symbol-U (Typed Graph) | ChatGPT (Transformer) |
|--------|------------------------|----------------------|
| **Knowledge** | Explicit typed graph | Implicit in weights |
| **Verifiability** | Full verifier pipeline | Black-box outputs |
| **Determinism** | Guaranteed | Non-deterministic (temperature) |
| **PPV Integration** | First-class numeric artifact | Would require fine-tuning |
| **Safety Mode** | GOVERNED (fail-closed) | Guardrails (soft filters) |
| **Ontology** | Explicit 7-layer structure | Emergent from training |
| **Auditability** | Complete ledger trail | Limited logging |
| **RAG** | Typed, verified retrieval | Standard retrieval |

### 8.2 Strengths Comparison

**Symbol-U Strengths**:
- Provably safe outputs in GOVERNED mode
- Deterministic, reproducible results
- Explicit knowledge structure
- Fine-grained PPV integration
- Full audit trail
- Verifiable reasoning traces

**ChatGPT Strengths**:
- Broader knowledge coverage
- Natural language fluency
- Transfer learning capability
- Rapid prototyping
- Large-scale pre-training
- Conversational adaptability

### 8.3 Hybrid Approach

For optimal results, combine approaches:

```
ChatGPT (Generation)     Symbol-U Verifier     GOVERNED Output
         │                       │                    │
         ▼                       ▼                    ▼
    Draft content          Safety checks        Verified result
    Fluent text            PPV validation       Ledger recorded
    Creative ideas         Source attribution   Template-bound
```

---

## 9. Implementation Roadmap

### 9.1 Module Structure

```
symbolu/
├── ppv/                           # PPV subsystem (IMPLEMENTED)
│   ├── ppv_contract_v1.py
│   └── ppv_builder_v1.py
├── graph/                         # Typed graph (NEW)
│   ├── graph_schema_v1.py
│   ├── graph_store_v1.py
│   ├── graph_query_v1.py
│   └── graph_verifier_v1.py
├── ontology/                      # Ontology layers (NEW)
│   ├── ontology_layers_v1.py
│   ├── ontology_mapping_v1.py
│   └── ontology_traverse_v1.py
├── reasoning/                     # Reasoning engine (NEW)
│   ├── inference_engine_v1.py
│   ├── constraint_solver_v1.py
│   └── reasoning_trace_v1.py
├── rag/                           # RAG integration (NEW)
│   ├── rag_pipeline_v1.py
│   ├── rag_retriever_v1.py
│   └── rag_update_v1.py
└── mechanical/pipeline/           # Existing pipeline
    ├── p10_acoustic/
    └── p11b_controller/
```

### 9.2 Phased Implementation

| Phase | Components | Dependencies |
|-------|------------|--------------|
| 1 | Graph Schema, Store | None |
| 2 | Ontology Layers, Mapping | Graph Schema |
| 3 | Inference Engine | Graph Store, Ontology |
| 4 | RAG Pipeline | Inference Engine |
| 5 | Reasoning Generation | RAG, Inference |
| 6 | Verification Integration | All |

---

## 10. Cross-Reference Index

### Documents

| Topic | Primary Document | Section |
|-------|------------------|---------|
| Graph node schemas | `typed_graph_llm_design_spec.md` | §3.1 |
| Graph edge schemas | `typed_graph_llm_design_spec.md` | §3.2 |
| PPV dimensions | `typed_graph_llm_design_spec.md` | §4.1 |
| Ontology layers | `typed_graph_llm_design_spec.md` | §5.1 |
| Graph implementation | `typed_graph_llm_implementation_spec.md` | §3.1-3.4 |
| RAG ingestion | `rag_database_reasoning_spec.md` | §3.2 |
| RAG retrieval | `rag_database_reasoning_spec.md` | §4.1 |
| Reasoning traces | `rag_database_reasoning_spec.md` | §5.2 |
| Phase-2 modifiers | `phase2_modifier_layer_spec_v3_2.md` | §3.2 |

### Key Concepts

| Concept | Definition Location |
|---------|---------------------|
| PPV (Phonemic Propensity Vector) | This document §4 |
| GOVERNED mode | This document §2.1 |
| Ontological layer | This document §5.1 |
| RoutingKey | `phase11b1_routing.py` |
| SubBand signature | `phase11b1_routing.py` |
| ConceptNode | `typed_graph_llm_design_spec.md` §3.1.1 |
| ReasoningTrace | `rag_database_reasoning_spec.md` §5.2 |

### APIs

| API | Location | Purpose |
|-----|----------|---------|
| `execute_phase11b1()` | `phase11b1_routing.py` | Collision-free routing |
| `InferenceEngine.find_path()` | `typed_graph_llm_implementation_spec.md` | Graph traversal |
| `RAGIngestionPipeline.ingest_document()` | `rag_database_reasoning_spec.md` | Document ingestion |
| `ReasoningGenerator.generate_reasoning()` | `rag_database_reasoning_spec.md` | Reasoning traces |

---

*Symbolu Architecture Master Specification - Consolidated reference for Typed Graph LLM, PPV, Ontology, RAG, and Reasoning.*
