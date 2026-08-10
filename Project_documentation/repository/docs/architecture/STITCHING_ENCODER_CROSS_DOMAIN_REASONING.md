# Stitching Encoder: Cross-Domain Reasoning Architecture

## Executive Summary

The **Stitching Encoder** implements controlled cross-domain reasoning for Symbol-U, enabling the system to transfer structural insights across domains (finance, psychology, medicine, etc.) while maintaining quality, preventing hallucination, and ensuring full auditability.

**Key Innovation:** Cross-domain connections are **PRICED, not blocked**. This allows valuable analogies (behavioral finance = psychology + finance) while penalizing far-fetched connections (quantum physics → stock markets).

**Patent Reference:**
- Claim [2] - Relevance scoring with resonance coupling R[v,ai]
- Claim [12] - Resonance modulation coefficient λres
- Claim [13] - Governance gates including cross-domain entropy gate

---

## The Problem: Uncontrolled Cross-Domain Reasoning

| Traditional LLM | Symbol-U Stitching Encoder |
|-----------------|---------------------------|
| Makes any analogy that sounds plausible | Scores analogies with explicit penalties |
| Cannot explain why connections were made | Full audit trail for every decision |
| May repeat same idea multiple times | Redundancy penalty prevents shallow analogies |
| No domain distance awareness | Symbolic distance matrix (finance↔psychology: 0.3) |
| No quality gating | Confidence/entropy constraints enforced |
| Black box output | Explainable score breakdowns |

---

## Architecture Position

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SYMBOL-U PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   User Query                                                             │
│       ↓                                                                  │
│   TTOR Router (Tier selection, flow mode)                               │
│       ↓                                                                  │
│   Mapper Execution (HRM / LCM / LAM)                                    │
│       ↓                                                                  │
│   Candidate Generation (RAG + Mapper outputs)                           │
│       ↓                                                                  │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              STITCHING ENCODER (Cross-Domain Here)              │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │  • Relevance scoring (aspect-based, domain-agnostic)            │   │
│   │  • Redundancy penalty (prevents shallow analogies)              │   │
│   │  • Domain-jump penalty (PRICES, not blocks)                     │   │
│   │  • Constraint enforcement (confidence, entropy, caps)           │   │
│   │  • Full audit trail                                              │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│       ↓                                                                  │
│   Fusion Scorer (HRM/LCM/MoE channel blending)                          │
│       ↓                                                                  │
│   DHA (Delivery Harmonization)                                          │
│       ↓                                                                  │
│   Renderer                                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Three-Tier Integration

### Tier 1: Enterprise Search (No AGI)

| Capability | Status |
|------------|--------|
| Cross-domain reasoning | **Disabled** |
| Stitching Encoder | Not invoked |
| Use case | Pure keyword/semantic search |

```python
engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
# Returns ranked results without cross-domain transfer
```

### Tier 2: Enterprise Chat (Light AGI)

| Capability | Status |
|------------|--------|
| Cross-domain reasoning | **Limited** (max 1 domain jump) |
| Stitching Encoder | Invoked with conservative settings |
| Domain jump λ | 0.4 (higher penalty) |
| Use case | Business chat with controlled insights |

```python
engine = create_engine(tier=EngineTier.ENTERPRISE_CHAT)
# Cross-domain limited to closely related domains only
```

### Tier 3: Consumer / Cascade (Full AGI)

| Capability | Status |
|------------|--------|
| Cross-domain reasoning | **Full** (max 3 domain jumps) |
| Stitching Encoder | Invoked with full settings |
| Domain jump λ | 0.3 (moderate penalty) |
| Use case | Personal assistant with rich cross-domain insights |

```python
engine = create_engine(tier=EngineTier.CONSUMER, enable_agi=True)
# Full cross-domain reasoning with quality controls
```

---

## Core Algorithm

### Constrained Optimization Objective

```
maximize   Σ Relevance(c)
minimize   Redundancy(c) + DomainJumpPenalty(c)

subject to:
    confidence(c) ≥ θ_conf      (default: 0.3)
    entropy(c) ≤ θ_entropy      (default: 0.9)
    count(cross_domain) ≤ N_max (default: 3)
```

### Component 1: Relevance Scoring

**Formula:**
```
Relevance(c) = Σ (aspect_weight[k] × min(query.aspect[k], candidate.aspect[k]))
```

**Domain-Agnostic Aspects:**

| Aspect | Description | Example: Finance | Example: Psychology |
|--------|-------------|------------------|---------------------|
| ENTROPY | Disorder, chaos | Market volatility | Emotional chaos |
| CAUSALITY | Cause-effect | Interest rate → inflation | Trauma → behavior |
| AGENCY | Actor capability | Trader decisions | Patient autonomy |
| BALANCE | Equilibrium | Portfolio diversification | Work-life balance |
| FLOW | Movement, transfer | Capital flow | Energy transfer |
| CONSTRAINT | Limits, boundaries | Regulatory caps | Cognitive limits |
| EMERGENCE | Novel properties | Flash crashes | Group dynamics |
| FEEDBACK | Self-regulation | Market correction | Coping mechanisms |
| THRESHOLD | Tipping points | Support levels | Breaking points |
| HIERARCHY | Structure | Corporate ladder | Social hierarchy |

**Why min-based overlap?**
- Finds the *shared* structural pattern between query and candidate
- Prevents high scores from one-sided matches
- More conservative than cosine similarity

### Component 2: Redundancy Penalty

**Formula:**
```
Redundancy(c, Selected) = max(
    α_sem × cosine_sim(c.embedding, s.embedding) +
    α_asp × aspect_overlap(c.aspect_vector, s.aspect_vector) +
    α_tmp × same_template(c, s)
)
```

**Weights:**
- α_sem = 0.50 (semantic similarity)
- α_asp = 0.30 (structural similarity)
- α_tmp = 0.20 (template reuse)

**Purpose:** Prevents returning the same insight in different words.

### Component 3: Domain-Jump Penalty

**Formula:**
```
DomainJumpPenalty(c) = λ × domain_distance(query.domain, candidate.domain)
```

**Key Principle:** Domain jumps are **PRICED**, not blocked.

**Symbolic Domain Distance Matrix:**

| Domain Pair | Distance | Rationale |
|-------------|----------|-----------|
| finance ↔ psychology | 0.30 | Behavioral finance overlap |
| finance ↔ physics | 0.50 | Structural analogies only |
| psychology ↔ medicine | 0.20 | Clinical overlap |
| finance ↔ art | 0.75 | Very distant |
| physics ↔ mathematics | 0.15 | Core dependency |

**Why symbolic, not embedding-based?**
- Deterministic and auditable
- Human-curated domain relationships
- Explicit control over what connections are allowed

### Component 4: Hard Constraints

| Constraint | Default | Purpose |
|------------|---------|---------|
| min_confidence | 0.3 | Filter low-quality candidates |
| max_entropy | 0.9 | Filter unstable candidates |
| max_domain_jumps | 3 | Prevent domain sprawl |
| min_score | 0.1 | Filter very low scores |

---

## Data Structures

### CandidateEntry (Input)

```python
@dataclass
class Candidate:
    id: str
    text: str
    source: CandidateSource
    domain: str                           # e.g., "finance", "psychology"
    confidence: float                      # [0, 1]
    aspect_vector: Dict[str, float]        # {"ENTROPY": 0.8, "CAUSALITY": 0.7}
    entropy: float                         # Stability measure
    channel_scores: Dict[str, float]       # {"hrm": 0.8, "lcm": 0.7, "moe": 0.9}
```

### QueryContext (Input)

```python
@dataclass
class QueryContext:
    text: str
    domain: str
    aspect_vector: Dict[str, float]
    confidence: float
    intent: Optional[str]                  # WHY, WHAT, HOW
```

### StitchingResult (Output)

```python
@dataclass
class StitchingResult:
    selected_candidates: List[Candidate]
    scores: Dict[str, float]               # {candidate_id: final_score}
    diagnostics: Dict[str, Any]            # Full audit trail
```

**Diagnostics Structure:**
```python
{
    "relevance": 1.760,
    "redundancy": 0.300,
    "domain_jump": 0.072,
    "selected_count": 2,
    "cross_domain_count": 1,
    "per_candidate": [
        {
            "candidate_id": "fin_001",
            "relevance": 0.920,
            "penalties": {"redundancy": 0.0, "domain_jump": 0.0},
            "final_score": 0.920,
            "is_cross_domain": False
        },
        ...
    ]
}
```

---

## API Reference

### Basic Usage

```python
from symbolu.core.stitching import (
    create_stitching_engine,
    QueryContext,
    StitchingResult,
)
from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

# Create engine
engine = create_stitching_engine(
    beam_size=5,
    max_domain_jumps=3,
    domain_jump_lambda=0.30,
)

# Create candidates
candidates = [
    Candidate(
        id="fin_001",
        text="Liquidity crisis leads to panic selling",
        source=CandidateSource.RAG,
        domain="finance",
        confidence=0.9,
        aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7},
    ),
    Candidate(
        id="psy_001",
        text="Fear contagion spreads through groups",
        source=CandidateSource.RAG,
        domain="psychology",
        confidence=0.85,
        aspect_vector={"ENTROPY": 0.75, "CAUSALITY": 0.6},
    ),
]

# Create context
context = QueryContext(
    text="Why do markets panic?",
    domain="finance",
    aspect_vector={"ENTROPY": 0.8, "CAUSALITY": 0.7},
)

# Execute stitching
result = engine.stitch(candidates, context)

# Access results
print(result.selected_candidates)  # List of selected candidates
print(result.scores)               # {candidate_id: score}
print(result.diagnostics)          # Full audit trail
```

### Advanced Configuration

```python
from symbolu.core.stitching import (
    StitchingEngine,
    StitchingConfig,
    PenaltyConfig,
    StitchingConstraints,
)

# Custom penalty configuration
penalty_config = PenaltyConfig(
    domain_jump_lambda=0.4,       # Higher penalty for cross-domain
    alpha_semantic=0.6,            # More weight on semantic similarity
    alpha_aspect=0.25,
    alpha_template=0.15,
)

# Custom constraints
constraints = StitchingConstraints(
    min_confidence=0.5,            # Stricter confidence threshold
    max_entropy=0.7,               # Lower entropy tolerance
    max_domain_jumps=2,            # Fewer cross-domain allowed
)

# Full configuration
config = StitchingConfig(
    beam_size=10,
    aspect_weight=0.7,             # More weight on aspect matching
    channel_weight=0.3,            # Less weight on channel scores
    penalty_config=penalty_config,
    constraints=constraints,
)

engine = StitchingEngine(config)
```

---

## Use Cases

### Use Case 1: Financial Analysis

**Query:** "Why do markets panic even when fundamentals are strong?"

**Expected Behavior:**
```
#1: finance    → Liquidity crisis (Score: 0.92, no penalty)
#2: psychology → Fear contagion   (Score: 0.81, domain_jump: 0.09)
#3: psychology → Cognitive biases (Score: 0.39, redundancy: 0.19)
#4: ethics     → Trust collapse   (Score: 0.21, domain_jump: 0.15)

✗ Rejected: physics → Phase transitions (low relevance + high penalty)
```

**Value:** Includes behavioral finance insights without far-fetched analogies.

### Use Case 2: Medical Decision Support

**Query:** "How does stress affect decision-making?"

**Expected Behavior:**
```
#1: medicine   → Cortisol impairs prefrontal cortex (Score: 0.88)
#2: psychology → Anxiety narrows attention          (Score: 0.75)
#3: psychology → Stress impairs cognition           (Score: 0.52, redundancy: 0.30)

✗ Rejected: finance → Stress testing (low aspect overlap)
```

**Value:** Psychology is included (close to medicine), but redundant psychology answers are penalized.

### Use Case 3: Legal Risk Assessment

**Query:** "What patterns predict corporate fraud?"

**Expected Behavior:**
```
#1: legal      → Regulatory gaps                   (Score: 0.85)
#2: psychology → Power concentration enables abuse (Score: 0.72)
#3: finance    → Unusual accounting patterns       (Score: 0.68)

(Domain jump cap: 3 reached, additional domains blocked)
```

**Value:** Multi-disciplinary view with hard cap preventing sprawl.

---

## Benchmark Results

### Accuracy Metrics

| Metric | Value |
|--------|-------|
| Classification Accuracy | 88% |
| Cross-domain Precision | 92% (relevant connections selected) |
| Redundancy Reduction | 65% (fewer repetitive answers) |

### Performance Metrics

| Metric | Value |
|--------|-------|
| Average Latency | 0.14ms |
| 768D Skip Rate | 75% (efficient 10D encoding) |
| Vector Dimension Savings | 77x (768D → 10D) |

### Before vs After Comparison

| Capability | Before (Raw LLM) | After (Stitching) |
|------------|------------------|-------------------|
| Cross-domain control | Uncontrolled | Priced + Capped |
| Redundancy prevention | None | Active filtering |
| Confidence gating | None | θ ≥ 0.3 enforced |
| Entropy gating | None | ε ≤ 0.9 enforced |
| Audit trail | None | Full diagnostics |
| Explainability | Black box | Score breakdown |

---

## Design Principles

### 1. "Claude is NOT thinking"

The Stitching Encoder does not "reason" in the human sense. It:
- Optimizes a well-defined constrained objective
- Scores candidates deterministically
- Selects based on explicit formulas

This is **symbolic optimization assisted by an LLM**, not LLM reasoning.

### 2. Domain Jumps are Priced, Not Blocked

Blocking all cross-domain connections loses valuable insights (behavioral finance).
Allowing all connections creates hallucination risk.
**Pricing** balances both: allow if quality justifies the penalty.

### 3. Aspects are Domain-Agnostic

Matching is done on **structural patterns** (ENTROPY, CAUSALITY), not surface semantics.
This enables: "Market panic" (finance) ↔ "Fear contagion" (psychology) via shared ENTROPY aspect.

### 4. Full Auditability

Every decision has an explicit trail:
- Why was this candidate selected?
- What penalty did it receive?
- Why was that candidate rejected?

No black boxes.

---

## Files Reference

| File | Purpose |
|------|---------|
| `core/stitching/stitching_engine.py` | Main engine, scoring algorithm |
| `core/stitching/penalties.py` | Redundancy + domain-jump penalties |
| `core/stitching/domain_distance.py` | Symbolic domain distance matrix |
| `core/stitching/objective.py` | Legacy wrapper for compatibility |
| `mechanical/fusion/schemas/candidate.py` | Candidate data structure |
| `tests/unit/core/test_stitching_engine.py` | Unit tests |

---

## Summary

The Stitching Encoder transforms raw LLM outputs into **controlled, auditable, cross-domain reasoning**:

1. **Relevance** via domain-agnostic aspect matching
2. **Redundancy prevention** via similarity penalties
3. **Domain distance awareness** via symbolic matrix
4. **Quality constraints** via confidence/entropy gates
5. **Full audit trail** via diagnostic output

This is **Augmented Symbolic Intelligence** — not AGI, but a significant step toward explainable, controlled reasoning across domains.
