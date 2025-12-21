# Symbol-U Architecture Plan: Enterprise vs Consumer

**Status:** DRAFT - AWAITING DECISION
**Date:** 2025-12-21
**Author:** Architecture Review

---

## Executive Summary

This document presents two architectural approaches for supporting both Enterprise (symbolic/auditable) and Consumer (pre-trained/semantic) use cases:

| Approach | Description | Recommendation |
|----------|-------------|----------------|
| **Option A: Dual Codebase** | Two separate orchestrators, shared core | Higher maintenance, cleaner separation |
| **Option B: Single Codebase + Providers** | One orchestrator, pluggable providers | Lower maintenance, recommended |

**Strategic Recommendation:** Start with **Single Codebase + Pluggable Providers**, plan for split only if business demands it at scale.

---

## PART I: STRATEGIC ANALYSIS

---

## 1. The Two Approaches

### Option A: Dual Codebase

```
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL CODEBASE APPROACH                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  symbolu-enterprise/              symbolu-consumer/             │
│  ├── orchestrator.py              ├── orchestrator.py           │
│  ├── governance/                  ├── governance/      DUPLICATE│
│  ├── delivery/                    ├── delivery/        DUPLICATE│
│  ├── resonance/                   ├── embeddings/               │
│  └── rag/                         └── rag/                      │
│                                                                 │
│  Two orchestrators = 2x maintenance                             │
│  Two governance copies = sync issues                            │
│  Two delivery copies = divergence risk                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Option B: Single Codebase + Pluggable Providers

```
┌─────────────────────────────────────────────────────────────────┐
│                 SINGLE CODEBASE APPROACH                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  symbolu/                                                       │
│  ├── orchestrator.py          # ONE orchestrator                │
│  ├── config.py                # Selects provider mode           │
│  ├── governance/              # ONE governance layer            │
│  ├── delivery/                # ONE delivery layer              │
│  └── providers/               # Pluggable implementations       │
│      ├── embedding/                                             │
│      │   ├── hash_provider.py      # Enterprise                 │
│      │   └── learned_provider.py   # Consumer                   │
│      ├── routing/                                               │
│      │   ├── phoneme_router.py     # Enterprise                 │
│      │   └── trained_router.py     # Consumer                   │
│      └── filtering/                                             │
│          ├── resonance_filter.py   # Enterprise                 │
│          └── attention_filter.py   # Consumer                   │
│                                                                 │
│  Config switches provider, not orchestrator                     │
│  Governance doesn't care how you routed                         │
│  Single codebase = single maintenance                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Comparison Matrix

| Aspect | Dual Codebase | Single + Providers |
|--------|--------------|-------------------|
| Orchestrators | 2 | 1 |
| Governance copies | 2 | 1 |
| Delivery copies | 2 | 1 |
| New files | 85-115 | ~30 |
| Timeline | 10 weeks | 4-5 weeks |
| Change governance | Update both | Update once |
| Testing burden | 2x | 1x + provider tests |
| Maintenance | High | Low |
| Switching modes | Restart with different app | Config flag |
| Enterprise "clean build" | Yes | No (but code is locked) |
| Codebase divergence | Possible | Impossible |

---

## 3. Why Single Codebase Is Technically Better

### Governance Doesn't Care About Provider Implementation

```python
# Governance sees the same inputs regardless of provider
def run_governance(routing_decision, candidates, user_context):
    # Doesn't matter if routing came from phonemes or neural net
    regime = p6_select_regime(routing_decision.model_type)
    discourse = p7_select_discourse(regime, user_context)
    return GovernanceEnvelope(regime, discourse, ...)
```

### The Only Difference Is Embedding + Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Query: "How do atoms bond?"                                    │
│                                                                 │
│  ENTERPRISE PATH:                    CONSUMER PATH:             │
│  phoneme_embed() → 10D               learned_embed() → 768D     │
│  phoneme_route() → REASONING         trained_route() → REASONING│
│         │                                   │                   │
│         └───────────────┬───────────────────┘                   │
│                         │                                       │
│                         ▼                                       │
│              SAME governance (P6-P12)                           │
│              SAME delivery (P27-P31)                            │
│              SAME output structure                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Why Enterprise Clients Might Prefer Dual Codebase

| Concern | Single + License | Dual Codebase |
|---------|------------------|---------------|
| "Is consumer code in my deployment?" | Yes (but locked) | No |
| Security audit complexity | Higher | Lower |
| SLA commitment | Shared roadmap | Dedicated roadmap |
| Perception | "Consumer + extras" | "Built for enterprise" |
| Pricing negotiation | "Why pay more for same code?" | "Different product" |

### Real-World Enterprise Deployment Patterns

Enterprise clients often deploy both:

```
┌─────────────────────────────────────────────────────────────────┐
│                  ENTERPRISE CLIENT REALITY                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Deployment A: Customer-Facing Web App                          │
│  ─────────────────────────────────────                          │
│  • LLM-powered (pre-trained providers)                          │
│  • Public web                                                   │
│  • Consumer license                                             │
│                                                                 │
│  Deployment B: Internal Compliance Tools                        │
│  ────────────────────────────────────────                       │
│  • Search-focused (symbolic providers)                          │
│  • Intranet                                                     │
│  • Enterprise license                                           │
│                                                                 │
│  SAME CLIENT → TWO DEPLOYMENTS → TWO LICENSES                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Licensing Model (Applies to Both Approaches)

```
┌─────────────────────────────────────────────────────────────────┐
│                       LICENSING TIERS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────┐    ┌─────────────────────────┐     │
│  │   Enterprise License    │    │   Consumer License      │     │
│  ├─────────────────────────┤    ├─────────────────────────┤     │
│  │ • Symbolic providers    │    │ • Learned providers     │     │
│  │ • Full audit logging    │    │ • No audit requirement  │     │
│  │ • Compliance APIs       │    │ • Simpler APIs          │     │
│  │ • Trace export          │    │ • Self-service          │     │
│  │ • SLA support           │    │ • Community support     │     │
│  │ • Dedicated success     │    │ • Documentation         │     │
│  └─────────────────────────┘    └─────────────────────────┘     │
│                                                                 │
│  License key controls which providers are available             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```python
# License key determines available providers
config = SymboluConfig(
    license_key="ENT-XXXX-XXXX",  # Enterprise license
)
# → Only symbolic providers available
# → Audit logging enabled
# → Compliance APIs unlocked

config = SymboluConfig(
    license_key="CON-XXXX-XXXX",  # Consumer license
)
# → Only learned providers available
# → Lighter weight APIs
```

---

## 6. Strategic Decision Matrix: Company Stage

```
┌─────────────────────────────────────────────────────────────────┐
│                 DECISION BY COMPANY STAGE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EARLY STAGE (< 20 engineers, < $10M ARR)                       │
│  ─────────────────────────────────────────                      │
│  → SINGLE CODEBASE + PROVIDERS                                  │
│                                                                 │
│  Rationale:                                                     │
│  • Ship faster to validate both markets                         │
│  • Can't afford 2x maintenance cost                             │
│  • Need to learn what enterprise actually requires              │
│  • Lower burn rate                                              │
│  • Faster iteration on shared components                        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  GROWTH STAGE (20-100 engineers, $10M-$50M ARR)                 │
│  ──────────────────────────────────────────────                 │
│  → CONSIDER DUAL CODEBASE                                       │
│                                                                 │
│  Rationale:                                                     │
│  • Enterprise ARR justifies dedicated team                      │
│  • Enterprise clients demanding "clean" builds                  │
│  • Consumer and enterprise roadmaps diverging                   │
│  • Can afford specialized teams                                 │
│  • Pricing power from product differentiation                   │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  SCALE STAGE (100+ engineers, $50M+ ARR)                        │
│  ─────────────────────────────────────────                      │
│  → LIKELY DUAL CODEBASE                                         │
│                                                                 │
│  Rationale:                                                     │
│  • Dedicated business units per market                          │
│  • Regulatory requirements may mandate separation               │
│  • Acquisition/spin-off optionality                             │
│  • Different release cycles per product                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. The Hybrid Path (Recommended)

Start single, architect for split:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID EVOLUTION PATH                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  YEAR 1-2: Single Codebase                                      │
│  ─────────────────────────────                                  │
│  symbolu/                                                       │
│  ├── orchestrator.py          # Single                          │
│  ├── governance/              # Single                          │
│  ├── delivery/                # Single                          │
│  └── providers/               # Enterprise + Consumer           │
│                                                                 │
│  Benefits:                                                      │
│  • Validate both markets with less code                         │
│  • Learn what enterprise actually needs                         │
│  • Lower burn rate                                              │
│  • Faster iteration                                             │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  YEAR 3+: Split IF Needed                                       │
│  ─────────────────────────────                                  │
│  symbolu-enterprise/          # Fork for enterprise             │
│  ├── orchestrator.py          # Diverge                         │
│  ├── governance/              # Enterprise-specific             │
│  └── providers/symbolic/      # Enterprise only                 │
│                                                                 │
│  symbolu-consumer/            # Original continues              │
│  ├── orchestrator.py          # Consumer-focused                │
│  └── providers/learned/       # Consumer only                   │
│                                                                 │
│  Trigger conditions for split:                                  │
│  • Enterprise ARR > $5M                                         │
│  • Enterprise clients demanding clean builds                    │
│  • Roadmaps diverging significantly                             │
│  • 30+ engineers available                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Summary: Which Approach Is Better?

| Question | Answer |
|----------|--------|
| **Technically better?** | Single codebase + providers |
| **Lower maintenance?** | Single codebase + providers |
| **Faster to ship?** | Single codebase + providers |
| **Enterprise perception?** | Dual codebase (feels "dedicated") |
| **Pricing power?** | Dual codebase (harder to compare) |
| **Early stage company?** | Single codebase + providers |
| **Funded growth stage?** | Consider dual if enterprise ARR > $5M |

### Final Recommendation

**Start with Single Codebase + Pluggable Providers.** Keep architecture clean enough to split later if business demands it.

---

## PART II: TECHNICAL IMPLEMENTATION

---

## 9. Architecture Overview (Single Codebase Approach)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SINGLE CODEBASE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          ┌─────────────────┐                                │
│                          │   User Query    │                                │
│                          └────────┬────────┘                                │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌──────────────────────────────┐                         │
│                    │         Config               │                         │
│                    │  mode="enterprise"|"consumer"│                         │
│                    └──────────────┬───────────────┘                         │
│                                   │                                         │
│                                   ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      SINGLE ORCHESTRATOR                             │   │
│  │                                                                      │   │
│  │   embedding = providers.get_embedding(config.mode)                   │   │
│  │   router = providers.get_router(config.mode)                         │   │
│  │   filter = providers.get_filter(config.mode)                         │   │
│  │                                                                      │   │
│  │   vec = embedding.embed(query)         # Provider-specific           │   │
│  │   routing = router.route(query)        # Provider-specific           │   │
│  │   candidates = rag.retrieve(vec)       # Provider-specific           │   │
│  │   filtered = filter.apply(candidates)  # Provider-specific           │   │
│  │                                                                      │   │
│  │   # SAME for both modes                                              │   │
│  │   envelope = run_governance(routing, filtered)                       │   │
│  │   output = run_delivery(envelope)                                    │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                    ┌──────────────────────────────┐                         │
│                    │   PROVIDER IMPLEMENTATIONS   │                         │
│                    ├──────────────────────────────┤                         │
│                    │                              │                         │
│                    │  Enterprise:    Consumer:    │                         │
│                    │  • HashEmbed    • LearnedEmbed│                        │
│                    │  • PhonemeRoute • TrainedRoute│                        │
│                    │  • ResonanceFilter • AttentionFilter                   │
│                    │                              │                         │
│                    └──────────────────────────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Directory Structure (Single Codebase)

```
symbolu/
├── orchestrator.py                 # SINGLE orchestrator
├── config.py                       # Mode selection + licensing
│
├── providers/                      # PLUGGABLE implementations
│   ├── __init__.py
│   ├── interfaces/                 # Abstract base classes
│   │   ├── embedding_provider.py
│   │   ├── router_provider.py
│   │   └── filter_provider.py
│   ├── enterprise/                 # Enterprise implementations
│   │   ├── hash_embedding.py       # Hash-based 256D
│   │   ├── phoneme_router.py       # Symbolic routing
│   │   ├── resonance_filter.py     # Phoneme filtering
│   │   └── resonance/              # Phoneme engine
│   │       ├── engine.py
│   │       └── phoneme_map.py
│   └── consumer/                   # Consumer implementations
│       ├── learned_embedding.py    # Pre-trained 768D
│       ├── trained_router.py       # Classifier routing
│       ├── attention_filter.py     # Attention filtering
│       └── models/                 # Trained weights
│           ├── encoder.pt
│           └── router.pt
│
├── governance/                     # SINGLE governance layer
│   ├── p6_regime_selection.py
│   ├── p7_discourse_act.py
│   ├── p10_acoustic/
│   ├── p11b_controller/
│   └── p12_consistency/
│
├── delivery/                       # SINGLE delivery layer
│   ├── p27_persona/
│   ├── p28_dha/
│   ├── p29_expression/
│   ├── p30_verification/
│   └── p31_output/
│
├── observer/                       # SINGLE observer layer
│   ├── p34_identity_harmonics/
│   └── p37_continuity/
│
├── rag/                            # RAG (uses provider embeddings)
│   ├── retriever.py
│   ├── indexer.py
│   └── vectorstore/
│
├── licensing/                      # License enforcement
│   ├── validator.py
│   └── features.py
│
├── training/                       # Consumer model training
│   ├── data/
│   ├── scripts/
│   └── config/
│
└── tests/
    ├── unit/
    │   ├── providers/enterprise/
    │   ├── providers/consumer/
    │   ├── governance/
    │   └── delivery/
    └── integration/
```

---

## 11. Target Use Cases

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

## 12. Interface Contracts

### 12.1 Embedding Provider Interface

```python
# symbolu/providers/interfaces/embedding_provider.py

from abc import ABC, abstractmethod
from typing import List

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

### 12.2 Router Provider Interface

```python
# symbolu/providers/interfaces/router_provider.py

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

### 12.3 Filter Provider Interface

```python
# symbolu/providers/interfaces/filter_provider.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

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

### 12.4 Config and Provider Factory

```python
# symbolu/config.py

from dataclasses import dataclass
from typing import Literal

@dataclass
class SymboluConfig:
    mode: Literal["enterprise", "consumer"]
    license_key: str = ""
    audit_enabled: bool = False  # Auto-set based on mode

    def __post_init__(self):
        if self.mode == "enterprise":
            self.audit_enabled = True


# symbolu/providers/__init__.py

def get_embedding_provider(mode: str) -> EmbeddingProvider:
    if mode == "enterprise":
        from .enterprise.hash_embedding import HashEmbeddingProvider
        return HashEmbeddingProvider()
    else:
        from .consumer.learned_embedding import LearnedEmbeddingProvider
        return LearnedEmbeddingProvider()

def get_router_provider(mode: str) -> RouterProvider:
    if mode == "enterprise":
        from .enterprise.phoneme_router import PhonemeRouterProvider
        return PhonemeRouterProvider()
    else:
        from .consumer.trained_router import TrainedRouterProvider
        return TrainedRouterProvider()
```

---

## 13. Implementation Phases (Single Codebase)

### Phase 1: Refactor to Provider Pattern (Week 1-2)

**Goal:** Extract embedding/routing/filtering into provider interfaces

| Task | Files Affected | Effort |
|------|----------------|--------|
| Create provider interfaces | New `providers/interfaces/*.py` | 1 day |
| Wrap existing code as enterprise providers | `providers/enterprise/` | 2 days |
| Create config and provider factory | `config.py`, `providers/__init__.py` | 1 day |
| Update orchestrator to use providers | `orchestrator.py` | 1 day |
| Update tests | `tests/` | 2 days |

**Deliverable:** Existing functionality works via enterprise providers.

### Phase 2: Create Consumer Provider Stubs (Week 3)

**Goal:** Scaffold consumer providers with placeholder implementations

| Task | Files Affected | Effort |
|------|----------------|--------|
| Create learned embedding stub | `providers/consumer/learned_embedding.py` | 0.5 days |
| Create trained router stub | `providers/consumer/trained_router.py` | 0.5 days |
| Create attention filter stub | `providers/consumer/attention_filter.py` | 0.5 days |
| Create parity tests | `tests/parity/` | 1 day |

**Deliverable:** Consumer mode compiles, returns placeholder results.

### Phase 3: Training Data Preparation (Week 4-5)

**Goal:** Prepare training data for consumer models

| Task | Files Affected | Effort |
|------|----------------|--------|
| Design training data schema | `training/data/` | 1 day |
| Generate query-intent pairs (10K+) | Script + labeling | 3 days |
| Generate paraphrase pairs (50K+) | Script + augmentation | 2 days |
| Validate training data | `training/scripts/validate.py` | 1 day |

**Deliverable:** Training datasets ready.

### Phase 4: Train Consumer Models (Week 6-7)

**Goal:** Train embedding encoder and router classifier

| Task | Files Affected | Effort |
|------|----------------|--------|
| Train encoder model | `training/scripts/train_encoder.py` | 3 days |
| Train router classifier | `training/scripts/train_router.py` | 2 days |
| Evaluate and tune | `training/scripts/evaluate.py` | 2 days |
| Export models | `providers/consumer/models/*.pt` | 0.5 days |

**Deliverable:** Trained models with >90% accuracy.

### Phase 5: Integrate Consumer Models (Week 8)

**Goal:** Replace stubs with trained models

| Task | Files Affected | Effort |
|------|----------------|--------|
| Implement learned embedding provider | `providers/consumer/learned_embedding.py` | 1 day |
| Implement trained router provider | `providers/consumer/trained_router.py` | 1 day |
| Implement attention filter provider | `providers/consumer/attention_filter.py` | 1 day |
| Full integration tests | `tests/integration/` | 1 day |

**Deliverable:** Fully functional consumer mode.

### Phase 6: Licensing + Comparison (Week 9)

**Goal:** Add licensing enforcement and compare modes

| Task | Files Affected | Effort |
|------|----------------|--------|
| Implement license validation | `licensing/` | 1 day |
| Create comparison test suite | `tests/comparison/` | 1 day |
| Performance benchmarks | `benchmarks/` | 1 day |
| Documentation | `docs/` | 1 day |

**Deliverable:** Licensed product with comparison report.

---

## 14. Training Data Specification

### 14.1 Query-Intent Pairs (for Router)

```jsonl
{"query": "Calculate the gravitational force between two planets", "intent": "REASONING", "domain": "physics"}
{"query": "I feel overwhelmed by my workload", "intent": "RELATIONSHIP", "domain": "emotional"}
{"query": "Book a flight to New York", "intent": "ACTION", "domain": "travel"}
{"query": "Write a poem about the ocean", "intent": "CREATIVE", "domain": "creative"}
{"query": "What does this code do?", "intent": "REASONING", "domain": "technical"}
```

**Target:** 10,000-50,000 labeled pairs

### 14.2 Similar Query Pairs (for Embeddings)

```jsonl
{"query_a": "How do atoms bond?", "query_b": "What is chemical bonding?", "similar": true}
{"query_a": "How do atoms bond?", "query_b": "Best pizza recipe", "similar": false}
```

**Target:** 50,000-100,000 pairs

---

## 15. Model Specifications

### 15.1 Embedding Encoder

| Property | Value |
|----------|-------|
| Architecture | Sentence-BERT (distilbert-base) |
| Output dimension | 768 |
| Training objective | Contrastive (CosineSimilarityLoss) |
| Model size | ~66M parameters |

### 15.2 Router Classifier

| Property | Value |
|----------|-------|
| Architecture | Linear classifier on encoder output |
| Output classes | 6 (ModelType enum) |
| Training objective | CrossEntropyLoss |
| Model size | ~5K parameters |

---

## 16. Testing Strategy

### 16.1 Provider Unit Tests

```python
def test_enterprise_embedding_deterministic():
    provider = HashEmbeddingProvider()
    vec1 = provider.embed("quantum physics")
    vec2 = provider.embed("quantum physics")
    assert vec1 == vec2

def test_consumer_embedding_deterministic():
    provider = LearnedEmbeddingProvider()
    vec1 = provider.embed("quantum physics")
    vec2 = provider.embed("quantum physics")
    assert vec1 == vec2
```

### 16.2 Mode Parity Tests

```python
def test_both_modes_produce_same_structure():
    config_e = SymboluConfig(mode="enterprise")
    config_c = SymboluConfig(mode="consumer")

    result_e = orchestrator.process("test query", config_e)
    result_c = orchestrator.process("test query", config_c)

    # Same output structure
    assert type(result_e) == type(result_c)
    assert result_e.governance_envelope.keys() == result_c.governance_envelope.keys()
```

---

## 17. Success Criteria

### Phase 1-2 (Refactor)
- [ ] All existing tests pass
- [ ] Enterprise mode produces identical results to current behavior
- [ ] Consumer mode compiles and returns valid structure

### Phase 3-5 (Training + Integration)
- [ ] Encoder achieves >85% similarity accuracy
- [ ] Router achieves >90% intent classification accuracy
- [ ] Consumer mode is deterministic (temperature=0)

### Phase 6 (Comparison)
- [ ] Consumer handles novel queries better
- [ ] Enterprise maintains full auditability
- [ ] Both produce valid governance/delivery envelopes
- [ ] License enforcement works correctly

---

## 18. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Training data insufficient | Medium | High | Start with synthetic, iterate |
| Model accuracy too low | Medium | High | Larger base model, more data |
| Provider interface too rigid | Low | Medium | Design for extension |
| Performance regression | Low | Medium | Benchmark continuously |

---

## 19. Open Questions

1. **Embedding model choice:** DistilBERT vs MiniLM vs custom?
2. **Training infrastructure:** Local GPU vs cloud?
3. **Model versioning:** How to handle model updates?
4. **Fallback strategy:** What if consumer model fails?
5. **Split trigger:** What metrics indicate we should split codebases?

---

## 20. Decision Required

Please select one approach:

- [ ] **Option A: Dual Codebase** - Two separate orchestrators, cleaner enterprise separation
- [ ] **Option B: Single Codebase + Providers** - One orchestrator, pluggable providers (recommended)

---

## Approval

- [ ] **Architecture Review:** _______________
- [ ] **Implementation Lead:** _______________
- [ ] **Date:** _______________
- [ ] **Decision:** ☐ Dual Codebase / ☐ Single Codebase + Providers

---

*Document Version: 2.0 DRAFT*
*Last Updated: 2025-12-21*
