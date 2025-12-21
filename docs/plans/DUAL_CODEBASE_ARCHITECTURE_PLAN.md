# Dual Codebase Architecture Plan

**Status:** DRAFT - AWAITING REVIEW
**Date:** 2025-12-21
**Author:** Architecture Review

---

## Executive Summary

This plan proposes splitting Symbol-U into two parallel implementation paths:

1. **Enterprise (Symbolic)** - Current STL approach with full auditability
2. **Consumer (Pre-trained)** - LLM-based approach with learned embeddings

Both paths share governance and delivery layers but differ in how they understand and route queries.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYMBOL-U DUAL ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          ┌─────────────────┐                                │
│                          │   User Query    │                                │
│                          └────────┬────────┘                                │
│                                   │                                         │
│                    ┌──────────────┴──────────────┐                          │
│                    │      Adapter Selection      │                          │
│                    │  (enterprise vs consumer)   │                          │
│                    └──────────────┬──────────────┘                          │
│                                   │                                         │
│          ┌────────────────────────┴────────────────────────┐                │
│          │                                                 │                │
│          ▼                                                 ▼                │
│  ┌───────────────────┐                         ┌───────────────────┐        │
│  │    ENTERPRISE     │                         │     CONSUMER      │        │
│  │    (Symbolic)     │                         │   (Pre-trained)   │        │
│  ├───────────────────┤                         ├───────────────────┤        │
│  │ • Hash embeddings │                         │ • Learned embed.  │        │
│  │ • Phoneme router  │                         │ • Trained router  │        │
│  │ • Resonance filter│                         │ • Attention filter│        │
│  │ • 10D vectors     │                         │ • 768D vectors    │        │
│  │ • Zero parameters │                         │ • ~100M params    │        │
│  │ • Full audit trail│                         │ • Deterministic   │        │
│  └─────────┬─────────┘                         └─────────┬─────────┘        │
│            │                                             │                  │
│            └─────────────────────┬───────────────────────┘                  │
│                                  │                                          │
│                                  ▼                                          │
│                    ┌─────────────────────────┐                              │
│                    │    SHARED CORE LAYER    │                              │
│                    ├─────────────────────────┤                              │
│                    │ • Governance (P6-P12)   │                              │
│                    │ • Delivery (P27-P31)    │                              │
│                    │ • Observer (P34, P37)   │                              │
│                    │ • Output (P30)          │                              │
│                    │ • Schema definitions    │                              │
│                    └─────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Target Use Cases

### Enterprise Path (Symbolic)

| Sector | Requirement | Why Symbolic |
|--------|-------------|--------------|
| Healthcare | Audit trails for decisions | Explainable routing |
| Finance | Regulatory compliance | Traceable logic |
| Legal | Decision justification | Step-by-step audit |
| Government | Transparency mandates | No black box |
| Insurance | Claim decision explanation | Deterministic + auditable |

### Consumer Path (Pre-trained)

| Sector | Requirement | Why Pre-trained |
|--------|-------------|-----------------|
| Wellness apps | Natural conversation | Context-aware |
| Personal assistants | Handle novel queries | Generalization |
| Creative tools | Nuanced understanding | Semantic depth |
| Education | Adaptive responses | Context sensitivity |
| Entertainment | Engaging interactions | Richer semantics |

---

## 3. Directory Structure

```
symbolu/
├── core/                           # SHARED - used by both paths
│   ├── __init__.py
│   ├── governance/                 # P6-P12 governance phases
│   │   ├── p6_regime_selection.py
│   │   ├── p7_discourse_act.py
│   │   ├── p10_acoustic/
│   │   ├── p11b_controller/
│   │   └── p12_consistency/
│   ├── delivery/                   # P27-P31 delivery phases
│   │   ├── p27_persona/
│   │   ├── p28_dha/
│   │   ├── p29_expression/
│   │   ├── p30_verification/
│   │   └── p31_output/
│   ├── observer/                   # P34, P37 observer phases
│   │   ├── p34_identity_harmonics/
│   │   └── p37_continuity/
│   ├── schemas/                    # Shared type definitions
│   │   ├── query.py
│   │   ├── response.py
│   │   ├── routing.py
│   │   └── candidate.py
│   └── interfaces/                 # Abstract base classes
│       ├── embedding_provider.py
│       ├── router_provider.py
│       └── filter_provider.py
│
├── enterprise/                     # ENTERPRISE - symbolic implementation
│   ├── __init__.py
│   ├── embeddings/
│   │   ├── hash_encoder.py         # Current hash-based 256D
│   │   └── phoneme_encoder.py      # Current phoneme 10D
│   ├── routing/
│   │   ├── semantic_router.py      # Phoneme-based routing
│   │   └── layer_mapping.py        # LAYER_TO_MODEL explicit map
│   ├── filtering/
│   │   ├── resonance_filter.py     # Phoneme resonance prefilter
│   │   └── harmony_scorer.py       # Harmony/dissonance scoring
│   ├── resonance/                  # Phoneme analysis engine
│   │   ├── engine.py
│   │   ├── phoneme_map.py
│   │   └── types.py
│   └── rag/
│       ├── retriever.py            # Hash-based retrieval
│       └── indexer.py
│
├── consumer/                       # CONSUMER - pre-trained implementation
│   ├── __init__.py
│   ├── embeddings/
│   │   ├── learned_encoder.py      # Pre-trained 768D encoder
│   │   └── model_loader.py         # Load trained weights
│   ├── routing/
│   │   ├── trained_router.py       # Learned classifier
│   │   └── model_loader.py
│   ├── filtering/
│   │   ├── attention_filter.py     # Learned attention prefilter
│   │   └── similarity_scorer.py    # Embedding similarity
│   ├── models/                     # Trained model weights
│   │   ├── encoder.pt              # Embedding model
│   │   └── router.pt               # Router classifier
│   └── rag/
│       ├── retriever.py            # Learned embedding retrieval
│       └── indexer.py
│
├── adapters/                       # ADAPTERS - unified interface
│   ├── __init__.py
│   ├── base_adapter.py             # Abstract adapter interface
│   ├── enterprise_adapter.py       # Wires enterprise components
│   ├── consumer_adapter.py         # Wires consumer components
│   └── factory.py                  # Adapter factory
│
├── training/                       # TRAINING - consumer model training
│   ├── __init__.py
│   ├── data/
│   │   ├── prepare_pairs.py        # Generate training pairs
│   │   ├── query_intent.jsonl      # Query → Intent labels
│   │   └── similar_queries.jsonl   # Paraphrase pairs
│   ├── scripts/
│   │   ├── train_encoder.py        # Train embedding model
│   │   ├── train_router.py         # Train router classifier
│   │   └── evaluate.py             # Evaluate models
│   └── config/
│       ├── encoder_config.yaml
│       └── router_config.yaml
│
└── tests/
    ├── unit/
    │   ├── core/                   # Shared core tests
    │   ├── enterprise/             # Enterprise-specific tests
    │   └── consumer/               # Consumer-specific tests
    ├── integration/
    │   ├── enterprise/             # Enterprise integration tests
    │   └── consumer/               # Consumer integration tests
    └── parity/                     # Interface parity tests
        └── test_adapter_parity.py  # Both paths produce same structure
```

---

## 4. Interface Contracts

### 4.1 Embedding Provider Interface

```python
# symbolu/core/interfaces/embedding_provider.py

from abc import ABC, abstractmethod
from typing import List, Tuple

class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Convert text to embedding vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed multiple texts."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension."""
        pass

    @abstractmethod
    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute similarity between two vectors."""
        pass
```

### 4.2 Router Provider Interface

```python
# symbolu/core/interfaces/router_provider.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

class ModelType(Enum):
    REASONING = "reasoning"
    RELATIONSHIP = "relationship"
    ACTION = "action"
    CREATIVE = "creative"
    REFLECTIVE = "reflective"
    GENERAL = "general"

@dataclass
class RoutingDecision:
    model_type: ModelType
    confidence: float
    dominant_layer: str
    layer_scores: Tuple[Tuple[str, float], ...]
    trace: dict  # Implementation-specific trace info

class RouterProvider(ABC):
    """Abstract interface for query routing."""

    @abstractmethod
    def route(self, query: str) -> RoutingDecision:
        """Route query to appropriate model type."""
        pass

    @abstractmethod
    def route_batch(self, queries: List[str]) -> List[RoutingDecision]:
        """Batch route multiple queries."""
        pass
```

### 4.3 Filter Provider Interface

```python
# symbolu/core/interfaces/filter_provider.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class FilterResult:
    filtered_texts: Tuple[str, ...]
    scores: Tuple[float, ...]
    stats: dict  # Implementation-specific stats

class FilterProvider(ABC):
    """Abstract interface for candidate filtering."""

    @abstractmethod
    def filter(
        self,
        candidates: Tuple[str, ...],
        query: str,
        top_k: int = 10,
    ) -> FilterResult:
        """Filter candidates by relevance to query."""
        pass
```

### 4.4 Unified Adapter Interface

```python
# symbolu/adapters/base_adapter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProcessResult:
    """Unified result from query processing."""
    response_text: str
    routing_decision: RoutingDecision
    retrieved_candidates: Tuple[str, ...]
    governance_envelope: dict  # P6-P12 outputs
    delivery_envelope: dict    # P27-P31 outputs
    trace: dict                # Full processing trace
    implementation: str        # "enterprise" or "consumer"

class BaseAdapter(ABC):
    """Abstract adapter interface - same for both paths."""

    @abstractmethod
    def process_query(
        self,
        query: str,
        user_context: Optional[dict] = None,
        corpus_ids: Optional[List[str]] = None,
    ) -> ProcessResult:
        """Process a query through the full pipeline."""
        pass

    @abstractmethod
    def get_implementation_name(self) -> str:
        """Return 'enterprise' or 'consumer'."""
        pass
```

---

## 5. Implementation Phases

### Phase 1: Refactor Core (Week 1-2)

**Goal:** Extract shared components into `core/`

| Task | Files Affected | Effort |
|------|----------------|--------|
| Create interface definitions | New `core/interfaces/*.py` | 1 day |
| Move governance phases to core | `p6`, `p7`, `p10-p12` | 2 days |
| Move delivery phases to core | `p27-p31` | 2 days |
| Move observer phases to core | `p34`, `p37` | 1 day |
| Create shared schemas | `core/schemas/*.py` | 1 day |
| Update imports throughout | All files | 2 days |

**Deliverable:** All shared code in `core/`, existing functionality unchanged.

### Phase 2: Create Enterprise Path (Week 3)

**Goal:** Wrap existing symbolic code in enterprise adapter

| Task | Files Affected | Effort |
|------|----------------|--------|
| Move resonance engine | `enterprise/resonance/` | 1 day |
| Move hash encoder | `enterprise/embeddings/` | 0.5 days |
| Move phoneme router | `enterprise/routing/` | 0.5 days |
| Move resonance filter | `enterprise/filtering/` | 0.5 days |
| Implement enterprise adapter | `adapters/enterprise_adapter.py` | 1 day |
| Create enterprise tests | `tests/unit/enterprise/` | 1 day |

**Deliverable:** Enterprise path functional, all existing tests pass.

### Phase 3: Create Consumer Scaffolding (Week 4)

**Goal:** Create consumer path structure with placeholder implementations

| Task | Files Affected | Effort |
|------|----------------|--------|
| Create learned encoder stub | `consumer/embeddings/` | 0.5 days |
| Create trained router stub | `consumer/routing/` | 0.5 days |
| Create attention filter stub | `consumer/filtering/` | 0.5 days |
| Implement consumer adapter | `adapters/consumer_adapter.py` | 1 day |
| Create adapter factory | `adapters/factory.py` | 0.5 days |
| Create parity tests | `tests/parity/` | 1 day |

**Deliverable:** Consumer path compiles, returns placeholder results, interface parity verified.

### Phase 4: Training Data Preparation (Week 5-6)

**Goal:** Prepare training data for consumer models

| Task | Files Affected | Effort |
|------|----------------|--------|
| Design training data schema | `training/data/` | 1 day |
| Generate query-intent pairs | Script + manual labeling | 3 days |
| Generate paraphrase pairs | Script + augmentation | 2 days |
| Create data validation | `training/scripts/validate.py` | 1 day |
| Document data requirements | `training/README.md` | 0.5 days |

**Deliverable:** 10K+ labeled query-intent pairs, 50K+ paraphrase pairs.

### Phase 5: Train Consumer Models (Week 7-8)

**Goal:** Train and evaluate embedding encoder and router classifier

| Task | Files Affected | Effort |
|------|----------------|--------|
| Implement encoder training | `training/scripts/train_encoder.py` | 2 days |
| Implement router training | `training/scripts/train_router.py` | 2 days |
| Train encoder model | GPU time + iteration | 2 days |
| Train router model | GPU time + iteration | 1 day |
| Evaluate and tune | `training/scripts/evaluate.py` | 2 days |
| Export models | `consumer/models/*.pt` | 0.5 days |

**Deliverable:** Trained encoder (768D) and router classifier with >90% accuracy.

### Phase 6: Integrate Consumer Models (Week 9)

**Goal:** Replace stubs with trained models

| Task | Files Affected | Effort |
|------|----------------|--------|
| Implement model loading | `consumer/embeddings/model_loader.py` | 1 day |
| Implement learned encoder | `consumer/embeddings/learned_encoder.py` | 1 day |
| Implement trained router | `consumer/routing/trained_router.py` | 1 day |
| Implement attention filter | `consumer/filtering/attention_filter.py` | 1 day |
| Full integration tests | `tests/integration/consumer/` | 1 day |

**Deliverable:** Fully functional consumer path with trained models.

### Phase 7: Comparison Testing (Week 10)

**Goal:** Compare enterprise vs consumer performance

| Task | Files Affected | Effort |
|------|----------------|--------|
| Create comparison test suite | `tests/comparison/` | 2 days |
| Run side-by-side evaluation | Script | 1 day |
| Document differences | `docs/comparison_report.md` | 1 day |
| Performance benchmarks | `benchmarks/` | 1 day |

**Deliverable:** Comparison report showing tradeoffs between paths.

---

## 6. Training Data Specification

### 6.1 Query-Intent Pairs (for Router)

```jsonl
{"query": "Calculate the gravitational force between two planets", "intent": "REASONING", "domain": "physics"}
{"query": "I feel overwhelmed by my workload", "intent": "RELATIONSHIP", "domain": "emotional"}
{"query": "Book a flight to New York", "intent": "ACTION", "domain": "travel"}
{"query": "Write a poem about the ocean", "intent": "CREATIVE", "domain": "creative"}
{"query": "What does this code do?", "intent": "REASONING", "domain": "technical"}
```

**Target:** 10,000-50,000 labeled pairs
**Source:**
- Existing RAG corpus metadata
- Synthetic generation from templates
- Manual labeling of edge cases

### 6.2 Similar Query Pairs (for Embeddings)

```jsonl
{"query_a": "How do atoms bond?", "query_b": "What is chemical bonding?", "similar": true}
{"query_a": "How do atoms bond?", "query_b": "Best pizza recipe", "similar": false}
{"query_a": "Newton's laws of motion", "query_b": "Force equals mass times acceleration", "similar": true}
```

**Target:** 50,000-100,000 pairs
**Source:**
- Paraphrase mining from RAG corpus
- Back-translation augmentation
- Synthetic negative sampling

---

## 7. Model Specifications

### 7.1 Embedding Encoder

| Property | Value |
|----------|-------|
| Architecture | Sentence-BERT (distilbert-base) |
| Output dimension | 768 |
| Training objective | Contrastive (CosineSimilarityLoss) |
| Batch size | 32 |
| Learning rate | 2e-5 |
| Epochs | 3-5 |
| Model size | ~66M parameters |

### 7.2 Router Classifier

| Property | Value |
|----------|-------|
| Architecture | Linear classifier on encoder output |
| Input dimension | 768 |
| Output classes | 6 (ModelType enum) |
| Training objective | CrossEntropyLoss |
| Batch size | 64 |
| Learning rate | 1e-4 |
| Epochs | 10 |
| Model size | ~5K parameters |

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# Enterprise unit test example
def test_phoneme_router_deterministic():
    router = PhonemeRouter()
    result1 = router.route("quantum physics")
    result2 = router.route("quantum physics")
    assert result1.model_type == result2.model_type

# Consumer unit test example
def test_trained_router_deterministic():
    router = TrainedRouter(temperature=0)
    result1 = router.route("quantum physics")
    result2 = router.route("quantum physics")
    assert result1.model_type == result2.model_type
```

### 8.2 Parity Tests

```python
# Verify both adapters produce same output structure
def test_adapter_output_parity():
    enterprise = EnterpriseAdapter()
    consumer = ConsumerAdapter()

    query = "How do atoms bond?"

    result_e = enterprise.process_query(query)
    result_c = consumer.process_query(query)

    # Same structure
    assert hasattr(result_e, 'routing_decision')
    assert hasattr(result_c, 'routing_decision')
    assert type(result_e.routing_decision) == type(result_c.routing_decision)

    # Same governance envelope structure
    assert result_e.governance_envelope.keys() == result_c.governance_envelope.keys()
```

### 8.3 Integration Tests

```python
# Full pipeline test
def test_enterprise_full_pipeline():
    adapter = get_adapter("enterprise")
    result = adapter.process_query(
        "I'm feeling anxious about my exam",
        user_context={"session_id": "test"},
    )

    # Verify routing
    assert result.routing_decision.model_type in ModelType

    # Verify governance applied
    assert "p6_regime" in result.governance_envelope

    # Verify delivery applied
    assert "p27_persona" in result.delivery_envelope
```

---

## 9. Migration Path

### For Existing Deployments

```python
# Before refactor
from symbolu.hybrid.router import SemanticRouter
router = SemanticRouter()
result = router.route(query)

# After refactor (enterprise path)
from symbolu.adapters import get_adapter
adapter = get_adapter("enterprise")
result = adapter.process_query(query)

# Or use consumer path
adapter = get_adapter("consumer")
result = adapter.process_query(query)
```

### Backward Compatibility

```python
# Compatibility shim (temporary)
from symbolu.adapters import get_adapter

# Old API preserved
class SemanticRouter:
    def __init__(self):
        self._adapter = get_adapter("enterprise")

    def route(self, query: str):
        result = self._adapter.process_query(query)
        return result.routing_decision
```

---

## 10. Success Criteria

### Phase 1-3 (Refactor)
- [ ] All existing tests pass
- [ ] No functionality regression
- [ ] Clear separation of enterprise/consumer/core

### Phase 4-6 (Training)
- [ ] Encoder achieves >85% similarity accuracy
- [ ] Router achieves >90% intent classification accuracy
- [ ] Models are deterministic (temp=0)

### Phase 7 (Comparison)
- [ ] Consumer path handles novel queries better
- [ ] Enterprise path maintains full auditability
- [ ] Both paths produce valid governance/delivery envelopes

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Training data insufficient | Medium | High | Start with synthetic generation, iterate |
| Model accuracy too low | Medium | High | Use larger base model, more training data |
| Interface mismatch | Low | Medium | Parity tests catch early |
| Performance regression | Low | Medium | Benchmark throughout |
| Scope creep | Medium | Medium | Strict phase gates |

---

## 12. Open Questions

1. **Embedding model choice:** DistilBERT vs MiniLM vs custom?
2. **Training infrastructure:** Local GPU vs cloud training?
3. **Model versioning:** How to handle model updates?
4. **A/B testing:** How to compare paths in production?
5. **Fallback strategy:** What if consumer model fails?

---

## 13. Appendix: File Count Estimates

| Directory | New Files | Modified Files |
|-----------|-----------|----------------|
| `core/` | 20-25 | 0 (new) |
| `enterprise/` | 15-20 | 0 (new) |
| `consumer/` | 15-20 | 0 (new) |
| `adapters/` | 5 | 0 (new) |
| `training/` | 10-15 | 0 (new) |
| `tests/` | 20-30 | 10-15 (existing) |
| **Total** | **85-115** | **10-15** |

---

## Approval

- [ ] **Architecture Review:** _______________
- [ ] **Implementation Lead:** _______________
- [ ] **Date:** _______________

---

*Document Version: 1.0 DRAFT*
*Last Updated: 2025-12-21*
