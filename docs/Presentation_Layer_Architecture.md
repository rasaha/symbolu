# Presentation Layer Architecture

## Overview

This document describes the complete data flow from ontological engine training through RAG storage to the presentation layer for query responses.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMPLETE ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   STEP 1: TRAINING              STEP 2: RAG EXPORT        STEP 3: QUERY    │
│   ─────────────────             ────────────────          ─────────────    │
│                                                                             │
│   train_v2.py                   export_to_rag.py          rag_query.py     │
│        │                              │                        │           │
│        ▼                              ▼                        ▼           │
│   ┌─────────┐                   ┌───────────┐            ┌───────────┐     │
│   │ Model   │                   │ Vector DB │◄───────────│  Query    │     │
│   │ .pt     │                   │ Graph DB  │            │  Engine   │     │
│   └────┬────┘                   └───────────┘            └─────┬─────┘     │
│        │                                                       │           │
│        ▼                                                       ▼           │
│   ┌─────────┐                                           ┌───────────┐      │
│   │Training │                                           │Presentation│     │
│   │Data JSON│───────────────────────────────────────────│  Layer    │     │
│   └─────────┘                                           └───────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Ontological Engine Training

### Script: `symbolu/ontological/train_v2.py`

Trains the UnifiedOntologicalEngineV2 model with inter-layer Bhava relationships based on Vedic Drishti patterns.

### Command
```bash
python -m symbolu.ontological.train_v2
```

### What It Does

1. **Initializes the Model**
   - Creates `UnifiedOntologicalEngineV2` with 156D output (12D ontological + 144D Bhava)
   - Loads Vedic Drishti aspect patterns as initial weights

2. **Trains on Domain Data**
   - Processes texts across 12 ontological layers
   - Learns layer classification with evidential uncertainty
   - Optimizes inter-layer Bhava relationships
   - Trains Drishti attention patterns

3. **Captures Training Data**
   - Extracts learned Drishti pattern deviations
   - Records relationship statistics
   - Saves test results with ontological analysis

### Outputs

| File | Description |
|------|-------------|
| `checkpoints/unified_v2_best.pt` | Trained model weights |
| `data/training_drishti_data.json` | Training artifacts and test results |

### Training Data JSON Structure
```json
{
  "config": {
    "epochs": 20,
    "best_val_acc": 0.895,
    "final_coherence": 0.571
  },
  "test_results": [
    {
      "text": "What is consciousness?",
      "dominant_layer": "O5_COGNITION",
      "confidence": 0.87,
      "coherence": 0.62,
      "strongest_relationships": [...]
    }
  ],
  "final_drishti": {
    "learned_aspect_matrix": [[...]],
    "significant_deviations": [...]
  },
  "final_relationship_stats": {
    "pattern_distribution": {...},
    "strongest_relationships": [...]
  }
}
```

---

## Step 2: Export to RAG Storage

### Script: `symbolu/ontological/export_to_rag.py`

Exports training data and model analyses to RAG-compatible formats for both Vector DB and Graph DB.

### Command
```bash
python -m symbolu.ontological.export_to_rag
```

### What It Does

1. **Creates RAG Schema**
   - Defines 156D vector index configuration
   - Specifies metadata fields for filtering
   - Defines graph schema for relationships

2. **Loads Training Data**
   - Reads `data/training_drishti_data.json`
   - Indexes test results as documents
   - Extracts learned Drishti patterns

3. **Analyzes Sample Texts** (if model exists)
   - Loads trained model checkpoint
   - Analyzes sample texts to create 156D vectors
   - Indexes with full ontological metadata

4. **Exports to Multiple Formats**
   - Vector DB format (Pinecone/Weaviate)
   - Graph DB format (Neo4j)
   - Complete knowledge base (JSON)

### Outputs

| File | Purpose | Use With |
|------|---------|----------|
| `data/rag/schema.json` | RAG schema definition | Database setup |
| `data/rag/knowledge_base.json` | Complete knowledge | Reference/Backup |
| `data/rag/vector_export.json` | 156D vectors + metadata | Pinecone/Weaviate |
| `data/rag/graph_export.json` | Nodes + edges | Neo4j |
| `data/rag/learned_drishti.json` | Pattern deviations | Analysis |
| `data/rag/relationship_stats.json` | Training statistics | Monitoring |
| `data/rag/training_history.json` | Per-epoch metrics | Debugging |

### Vector Export Structure
```json
{
  "vectors": [
    {
      "id": "doc_001",
      "values": [0.12, 0.05, ...],  // 156D
      "metadata": {
        "text": "What is consciousness?",
        "dominant_layer": "O5_COGNITION",
        "confidence": 0.87,
        "coherence": 0.62
      }
    }
  ],
  "namespace": "ontological",
  "dimension": 156
}
```

### Graph Export Structure
```json
{
  "nodes": [
    {
      "id": "O1_POTENTIAL",
      "index": 0,
      "bhava_name": "Tanu",
      "bhava_meaning": "Body/Self"
    }
  ],
  "edges": [
    {
      "from_layer": "O5_COGNITION",
      "to_layer": "O8_PURPOSE",
      "bhava_name": "Sukha",
      "pattern_type": "Square",
      "interpretation": "Cognition's Happiness in Purpose",
      "strength": 0.75
    }
  ]
}
```

---

## Step 3: RAG Query Engine

### Script: `symbolu/ontological/rag_query.py`

Central coordinator that handles queries from the presentation layer, retrieves from RAG storage, and returns ontological context.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                              │
│                    (API / CLI / Web UI)                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ query("What is consciousness?")
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RAGQueryEngine                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  Methods:                                                           │
│  • query(text) → QueryResult                                        │
│  • get_rag_context(text) → str                                     │
│  • search_similar(vector) → List[Document]                         │
│  • get_relationship_context(layer) → List[Relationship]            │
└─────────────────────────────────────────────────────────────────────┘
          │                   │                   │
          │ analyze           │ search            │ traverse
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Ontological    │ │  Vector Index   │ │  Graph Index    │
│  Engine V2      │ │  (156D cosine)  │ │  (Relationships)│
│  ─────────────  │ │  ─────────────  │ │  ─────────────  │
│  Text → 156D    │ │  Pinecone /     │ │  Neo4j /        │
│  + Analysis     │ │  In-memory      │ │  In-memory      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Usage

```python
from symbolu.ontological.rag_query import RAGQueryEngine

# Initialize engine
engine = RAGQueryEngine()
engine.load_model("checkpoints/unified_v2_best.pt")
engine.load_knowledge_base("data/rag/knowledge_base.json")

# Full query with all context
result = engine.query("What is consciousness?")

# Access results
print(result.query_layer)           # "O5_COGNITION"
print(result.query_confidence)      # 0.87
print(result.similar_documents)     # List of similar docs from Vector DB
print(result.query_relationships)   # List of relationships from Graph DB
print(result.rag_context)           # Formatted context for LLM

# Simple context string for LLM augmentation
context = engine.get_rag_context("What is consciousness?")
```

### Query Flow

```
1. USER QUERY
   "What is consciousness?"
            │
            ▼
2. ONTOLOGICAL ANALYSIS (Engine V2)
   ├── Encode text → 384D embedding
   ├── MLP backbone → 128D hidden
   ├── Evidential layer → 12D probs + uncertainty
   ├── Bhava engine → 144D relationships + coherence
   └── Output: 156D vector + metadata
            │
            ▼
3. VECTOR SEARCH (Hybrid: Vector DB)
   ├── Cosine similarity on 156D vectors
   ├── Retrieve top-k similar documents
   └── Return with metadata (layer, confidence, coherence)
            │
            ▼
4. GRAPH TRAVERSAL (Hybrid: Graph DB)
   ├── Find relationships FROM dominant layer
   ├── Find relationships TO dominant layer
   ├── Get Bhava significances
   └── Return relationship context
            │
            ▼
5. CONTEXT FORMATTING
   ├── Combine vector results + graph results
   ├── Format as RAG context string
   └── Return QueryResult to presentation layer
```

### QueryResult Structure

```python
@dataclass
class QueryResult:
    # Query analysis
    query_text: str
    query_layer: str              # "O5_COGNITION"
    query_confidence: float       # 0.87
    query_coherence: float        # 0.62
    query_vector: List[float]     # 156D

    # Vector DB results
    similar_documents: List[Dict]

    # Graph DB results
    query_relationships: List[Dict]
    relevant_bhavas: List[Dict]

    # Combined context for LLM
    rag_context: str
```

---

## Step 4: Presentation Layer Integration

### How to Integrate

The presentation layer (API, CLI, or Web UI) interacts with `RAGQueryEngine`:

```python
# In your API endpoint or CLI handler
from symbolu.ontological.rag_query import create_query_engine

# Initialize once at startup
rag_engine = create_query_engine(
    model_path="checkpoints/unified_v2_best.pt",
    kb_path="data/rag/knowledge_base.json"
)

# Handle user query
def handle_query(user_input: str) -> dict:
    result = rag_engine.query(user_input, top_k=5)

    return {
        "layer": result.query_layer,
        "confidence": result.query_confidence,
        "similar_docs": result.similar_documents,
        "relationships": result.query_relationships,
        "context": result.rag_context
    }

# For LLM augmentation
def augment_llm_prompt(user_input: str) -> str:
    context = rag_engine.get_rag_context(user_input)
    return f"""Given this ontological context:
{context}

User Question: {user_input}

Please provide an answer informed by the ontological relationships above."""
```

### Example RAG Context Output

```
=== ONTOLOGICAL CONTEXT ===
Query Layer: O5_COGNITION
Confidence: 87.2%
Coherence: 0.62
Bhava: Putra - Children/Creativity

=== SIMILAR DOCUMENTS ===
1. [O5_COGNITION] The nature of awareness involves both subjective...
   Similarity: 0.89
2. [O8_PURPOSE] Understanding consciousness requires examining...
   Similarity: 0.76

=== RELATIONSHIP CONTEXT ===
  → O8_PURPOSE: Sukha (Square)
    Cognition's Happiness in Purpose
  ← O1_POTENTIAL: Tanu (Trine)
    Potential's Self-expression through Cognition

=== ACTIVE RELATIONSHIPS IN QUERY ===
  O5_COGNITION → O8_PURPOSE: 0.82
    Deep philosophical inquiry into meaning
```

---

## Complete Workflow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMPLETE WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. TRAIN MODEL                                                             │
│     $ python -m symbolu.ontological.train_v2                               │
│                                                                             │
│     Outputs:                                                                │
│     • checkpoints/unified_v2_best.pt (model)                               │
│     • data/training_drishti_data.json (training artifacts)                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  2. EXPORT TO RAG                                                           │
│     $ python -m symbolu.ontological.export_to_rag                          │
│                                                                             │
│     Outputs:                                                                │
│     • data/rag/knowledge_base.json (complete KB)                           │
│     • data/rag/vector_export.json (for Pinecone/Weaviate)                  │
│     • data/rag/graph_export.json (for Neo4j)                               │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  3. QUERY VIA RAG ENGINE                                                    │
│     from symbolu.ontological.rag_query import RAGQueryEngine               │
│                                                                             │
│     engine = RAGQueryEngine()                                              │
│     engine.load_model("checkpoints/unified_v2_best.pt")                    │
│     engine.load_knowledge_base("data/rag/knowledge_base.json")             │
│                                                                             │
│     result = engine.query("What is consciousness?")                        │
│     context = engine.get_rag_context("What is consciousness?")             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  4. PRESENTATION LAYER                                                      │
│     Use result.rag_context to augment LLM prompts                          │
│     Display result.similar_documents for related content                   │
│     Show result.query_relationships for ontological reasoning              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Alternative: SymbolU12 LLM Architecture

In addition to the MiniLM-based approach, Symbol-U provides a full 12-layer ontological transformer (SymbolU12_LLM) for native language generation.

### Architecture Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MiniLM V2 vs SymbolU12 LLM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MiniLM V2 (UnifiedOntologicalEngineV2)                                    │
│  ─────────────────────────────────────                                      │
│  • Uses pre-trained MiniLM encoder (384D)                                  │
│  • Adds evidential classification + Bhava relationships                    │
│  • Output: 156D (12D onto + 144D Bhava)                                    │
│  • Best for: Classification, RAG, fine-tuning                              │
│  • Training: Fine-tune heads only                                          │
│                                                                             │
│  SymbolU12 LLM                                                              │
│  ─────────────                                                              │
│  • Full 12-layer ontological transformer                                   │
│  • Each layer has explicit cognitive function                              │
│  • Output: Token-level logits + coherence matrix                           │
│  • Best for: Generation, interpretability, research                        │
│  • Training: Full model from scratch                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12 Ontological Layers

| Layer | Name         | Function          | Description                        |
|-------|--------------|-------------------|------------------------------------|
| 1     | Potential    | Dormant           | Token activation based on relevance|
| 2     | Identity     | Tagging           | POS, NER, syntax role assignment   |
| 3     | Execution    | Action            | N-gram patterns, local attention   |
| 4     | Structure    | Forming           | Phrase boundaries, clause structure|
| 5     | Cognition    | Perception        | Semantic understanding, concepts   |
| 6     | Agency       | Direction         | Goal-directed attention            |
| 7     | Reasoning    | Discrimination    | Logical inference, contradictions  |
| 8     | Purpose      | Meaning           | Intent recognition, pragmatics     |
| 9     | Witness      | Meta-Observation  | Confidence estimation, self-aware  |
| 10    | Unifying     | Coherence         | C'[i,j] = C[i,j] × S[i,j]          |
| 11    | Integration  | Resolution        | Conflict resolution, belief revision|
| 12    | Absolving    | Termination       | Completion decision, EOS           |

### Usage with Engine Factory

```python
from symbolu.ontological.engine_factory import (
    create_ontological_engine,
    OntologicalEngineType,
)

# Create MiniLM-based engine (default, recommended for RAG)
engine_v2 = create_ontological_engine(OntologicalEngineType.MINILM_V2)

# Create SymbolU12 LLM engine (for generation/interpretability)
engine_llm = create_ontological_engine(OntologicalEngineType.SYMBOLU12_LLM)

# Both provide consistent interface
result = engine_v2.analyze("What is consciousness?")
result = engine_llm.analyze("What is consciousness?")

# Both return same structure
print(result["dominant_layer"])     # "O5_COGNITION"
print(result["confidence"])         # 0.87
print(result["coherence"])          # 0.62
```

### Key Features of SymbolU12 LLM

1. **Witness Layer (Layer 9)**: Enables hallucination detection
   ```python
   if outputs['witness_confidence'] < 0.5:
       print("Low confidence - may be hallucinating")
   ```

2. **Coherence Matrix (Layer 10)**: Ensures discourse consistency
   ```python
   # C'[i,j] = C[i,j] × S[i,j]
   coherence = outputs['global_coherence']
   violations = outputs['violations']
   ```

3. **Holistic Termination (Layer 12)**: Not just EOS prediction
   ```python
   if outputs['completion'].mean() > 0.9:
       print("Response is semantically complete")
   ```

---

## File Reference

| Script | Purpose | Run Command |
|--------|---------|-------------|
| `train_v2.py` | Train MiniLM-based model | `python -m symbolu.ontological.train_v2` |
| `export_to_rag.py` | Export to RAG formats | `python -m symbolu.ontological.export_to_rag` |
| `rag_query.py` | Query RAG for context | Import and use `RAGQueryEngine` |
| `rag_storage.py` | RAG storage classes | Used internally by export |
| `unified_engine.py` | MiniLM-based engine | Used by training and query |
| `symbolu12_llm.py` | Full 12-layer LLM | Alternative for generation |
| `engine_factory.py` | Engine factory | Unified interface for both engines |
| `bhava_relationships.py` | Vedic Drishti patterns | Used by all modules |

---

## Database Options

### Vector Database (for similarity search)
- **Pinecone**: Cloud-native, scalable
- **Weaviate**: Self-hosted, hybrid search
- **In-memory**: Built into RAGQueryEngine (for development)

### Graph Database (for relationship traversal)
- **Neo4j**: Industry standard, Cypher queries
- **In-memory**: Built into RAGQueryEngine (for development)

### Recommended Hybrid Setup
1. Use Vector DB for semantic similarity (find relevant documents)
2. Use Graph DB for ontological reasoning (understand relationships)
3. Use `knowledge_base.json` for complete reference data
