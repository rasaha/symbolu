# Phoneme-Transformer Hybrid Optimization Architecture

## Executive Summary

This document describes the **Symbolic Transformer Engine (STE)** - a deterministic computational system that uses 10-dimensional phoneme vectors for ontological processing.

**Core Claim**:

> Symbolu implements a transformer-class computation (contextual sequence processing with selective focus and state propagation), but replaces learned continuous operators with explicit, deterministic symbolic operators.

**Symbolu is not a language model and not a neural transformer.**

---

## Symbolic Transformer Foundations

### What "Transformer-Class" Means in Symbolu

This refers to **abstract computational roles**, not neural implementation:

| Computational Role | Description |
|-------------------|-------------|
| Tokenized sequence processing | Input broken into discrete units |
| Context accumulation | Prior state informs current processing |
| Selective focus ("attention") | Some elements weighted over others |
| State preservation across steps | Information persists through layers |

**Explicit Non-Claim**:

Symbolu does not implement neural attention, embeddings, gradients, or probability distributions.

### Tokens in Symbolu

Tokens are **varnas / phonemes** - discrete symbolic units with explicit features.

| Property | Neural Tokens | Symbolu Tokens |
|----------|---------------|----------------|
| Representation | Learned embeddings (768D+) | Defined features (10D) |
| Origin | Statistical subword splitting | Phonetic structure |
| Meaning | Emergent from training | Structural, not semantic |
| Modifiability | Frozen after training | Explicitly auditable |

> Tokens in Symbolu play the same structural role as tokens in transformers, but their representations are defined, finite, and auditable rather than learned and continuous.

### Attention as Constraint Focus

Neural attention and Symbolu "attention" serve the same abstract role but differ fundamentally:

| Aspect | Neural Attention | Symbolu Attention |
|--------|------------------|-------------------|
| Mechanism | Graded weighting (QK dot products) | Categorical elimination |
| Output | Probability distribution | Constraint-resolved candidates |
| Computation | Softmax over similarities | Validity pruning |
| Gradients | Required for learning | None |

> In Symbolu, "attention" is implemented as constraint-based focus and exclusion, not as weighted aggregation.

Symbolu's attention mechanisms include:
- **Constraint narrowing**: Eliminate impossible interpretations
- **Validity pruning**: Remove phonetically incompatible candidates
- **Mode elimination**: Exclude observation modes based on session history
- **Target feasibility checks**: Verify ontological routing targets

**Symbolu does not approximate neural attention; it replaces it with a stricter, deterministic operator.**

### Context Accumulation

Both transformers and Symbolu maintain context windows, but through different mechanisms:

| Mechanism | Neural Transformers | Symbolu |
|-----------|---------------------|---------|
| Position encoding | Learned positional embeddings | `SESSION_INFLUENCE_WINDOW` (explicit N queries) |
| Decay | Implicit in attention weights | Deterministic decay functions (`exp(-λ × age)`) |
| Recency | Causal masking | Explicit recency weighting |
| Boundaries | Fixed context length | Auditable window bounds |

> This is functionally equivalent to context accumulation, but transparent, bounded, and auditable.

### State Preservation

Residual connections in neural transformers preserve base signal across layers. Symbolu achieves the same effect symbolically:

> Base signals persist unless explicitly overridden by constraints.

| Neural Residuals | Symbolu State Preservation |
|------------------|---------------------------|
| Skip connections add input to output | Base signals retained by default |
| Learned layer normalization | Deterministic decay normalization |
| Gradient flow preservation | N/A (no gradients) |

This is **residual-equivalent behavior**, not residual connections.

### What Symbolu Does NOT Do

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXPLICIT NON-CAPABILITIES                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✗ No learning                                                  │
│  ✗ No gradient descent                                          │
│  ✗ No probability distributions                                 │
│  ✗ No interpolation between unseen states                       │
│  ✗ No semantic generalization                                   │
│  ✗ No emergent behavior from statistical patterns               │
│                                                                 │
│  Symbolu converges via enumeration, exclusion, and constraint   │
│  tightening, not statistical optimization.                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Canonical Comparison Table

| Abstract Role | Transformer (Neural) | Symbolu (Symbolic) |
|---------------|----------------------|--------------------|
| Token | Discrete → embedding | Discrete → symbolic features |
| Context | Positional embeddings | Session influence window |
| Attention | QK dot products | Constraint focus & exclusion |
| Weighting | Softmax probabilities | Deterministic mode elimination |
| State preservation | Residual connections | Base signal retention |
| Normalization | Learned layer norms | Deterministic decay |
| Output | Distribution over tokens | Constraint-resolved candidates |
| Learning | Gradient descent | None (explicit rules) |

---

## Optimization Layer Overview

This document also describes the **Phoneme-Transformer Hybrid System** - an optimization layer that uses deterministic 10-dimensional phoneme vectors to reduce transformer computation by 80%+ for specific operations.

**Core Innovation**: Derive semantic meaning from phonetic STRUCTURE (how sounds are produced) rather than statistical USAGE (word co-occurrence in corpora). This enables:
- **Zero-parameter attention** using phoneme similarity
- **Pre-filtering** candidates before expensive inference
- **Semantic routing** to specialized sub-models

---

## Table of Contents

**Part I: Symbolic Transformer Foundations**
- [Executive Summary](#executive-summary)
- [Symbolic Transformer Foundations](#symbolic-transformer-foundations)
  - [What "Transformer-Class" Means in Symbolu](#what-transformer-class-means-in-symbolu)
  - [Tokens in Symbolu](#tokens-in-symbolu)
  - [Attention as Constraint Focus](#attention-as-constraint-focus)
  - [Context Accumulation](#context-accumulation)
  - [State Preservation](#state-preservation)
  - [What Symbolu Does NOT Do](#what-symbolu-does-not-do)
  - [Canonical Comparison Table](#canonical-comparison-table)

**Part II: Optimization Layer**
1. [Problem Statement](#1-problem-statement)
2. [Solution Architecture](#2-solution-architecture)
3. [Core Components](#3-core-components)
4. [Data Flow](#4-data-flow)
5. [Mathematical Foundations](#5-mathematical-foundations)
6. [Implementation Details](#6-implementation-details)
7. [Benchmark Results](#7-benchmark-results)
8. [Development Guide](#8-development-guide)
9. [Future Work](#9-future-work)

---

## 1. Problem Statement

### Traditional Transformer Computation

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSFORMER ATTENTION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Token → Embedding (768D) → Q, K, V Projections                │
│                                                                 │
│  Attention = softmax(QK^T / √d) × V                            │
│                                                                 │
│  Complexity: O(n² × d) where d = 64-128 per head               │
│  Parameters: Billions (learned weights)                         │
│  Memory: Gigabytes                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Challenges:**
- Massive compute for every token pair
- All parameters are learned (gradient computation required)
- No prior knowledge about word relationships
- Same compute whether words are obviously related or not

### The Opportunity

Many word relationships are **phonetically predictable**:
- "Truth" and "light" resonate (both have flowing sounds)
- "Love" and "peace" resonate (both have soft, open sounds)
- "War" and "hate" resonate (both have hard, abrupt sounds)

**Key Insight**: If we can predict which words resonate using cheap phoneme computation, we can skip expensive transformer computation for obvious cases.

---

## 2. Solution Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LAYER 1: PHONEME RESONANCE                  │   │
│  │                    (Deterministic)                       │   │
│  │                                                          │   │
│  │  Word → Phonemes → 10D Vector → Cosine Similarity       │   │
│  │                                                          │   │
│  │  Cost: O(10) per comparison                              │   │
│  │  Parameters: 0                                           │   │
│  │  Memory: Kilobytes                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LAYER 2: DECISION GATE                      │   │
│  │                                                          │   │
│  │  • Pre-filter candidates (keep top 10%)                  │   │
│  │  • Route to specialized models                           │   │
│  │  • Replace some attention heads                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LAYER 3: TRANSFORMER                        │   │
│  │              (Only When Needed)                          │   │
│  │                                                          │   │
│  │  Full attention on filtered/routed subset                │   │
│  │                                                          │   │
│  │  Cost: O(n² × d) but n is 10-100x smaller               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Package Structure

```
symbolu/
├── resonance/              # Core phoneme-to-vector engine
│   ├── __init__.py         # Public API exports
│   ├── types.py            # Immutable data structures
│   ├── phoneme_map.py      # Phoneme → 10D affinity mappings
│   ├── engine.py           # Vector computation algorithms
│   └── analyzer.py         # High-level analysis functions
│
├── hybrid/                 # Transformer optimization layer
│   ├── __init__.py         # Public API exports
│   ├── attention.py        # PhonemeAttentionHead
│   ├── prefilter.py        # CandidatePreFilter
│   ├── router.py           # SemanticRouter
│   └── benchmark.py        # Computation benchmarks
│
└── tests/
    └── resonance/
        └── test_resonance_engine.py
```

---

## 3. Core Components

### 3.1 Phoneme Resonance Engine (`symbolu/resonance/`)

#### Purpose
Convert words to 10-dimensional ontological vectors based on phoneme structure.

#### Key Types

```python
@dataclass(frozen=True)
class WordVector:
    word: str                           # Original word
    phonemes: Tuple[str, ...]           # ARPABET phonemes
    vector: Tuple[float, ...]           # 10D normalized vector
    trajectory: Tuple[float, ...]       # Prosodic shape
    dominant_layer: str                 # Strongest dimension
    dominant_score: float               # Strength (0-1)

@dataclass(frozen=True)
class ResonanceResult:
    word_a: str
    word_b: str
    similarity: float                   # Cosine similarity (0-1)
    harmonic: bool                      # similarity >= 0.7
    dissonant: bool                     # similarity <= 0.3
    shared_dimensions: Tuple[str, ...]  # High in both
    conflicting_dimensions: Tuple[str, ...]
```

#### The 10 Ontological Dimensions

| Index | Layer | Meaning | Phoneme Affinity |
|-------|-------|---------|------------------|
| 0 | O1_THINKING | Contemplation | Nasals, fricatives |
| 1 | O2_FORMING | Structure, creation | Liquids, glides |
| 2 | O3_ACTING | Action, force | Plosives |
| 3 | O4_TAGGING | Classification | Short vowels |
| 4 | O5_DIRECTING | Guidance | Fricatives, plosives |
| 5 | O6_REASONING | Logic, analysis | Fricatives |
| 6 | O7_PURPOSING | Intent, goals | Diphthongs |
| 7 | O8_META_OBSERVING | Awareness | Long vowels |
| 8 | O9_UNIFYING | Connection | Nasals, liquids |
| 9 | O10_ABSOLVING | Transcendence | Long vowels, breath |

### 3.2 Phoneme Attention Head (`symbolu/hybrid/attention.py`)

#### Purpose
Replace learned attention weights with deterministic phoneme similarity.

#### Algorithm

```python
def compute_attention(tokens):
    # 1. Convert tokens to 10D vectors
    vectors = [word_to_vector(t) for t in tokens]

    # 2. Compute pairwise cosine similarity
    for i in range(n):
        for j in range(n):
            similarity[i][j] = cosine(vectors[i], vectors[j])

    # 3. Apply softmax
    attention = softmax(similarity / temperature)

    return attention
```

#### Complexity Comparison

| Operation | Traditional | Phoneme |
|-----------|-------------|---------|
| Dimension | 64-128 | 10 |
| Multiply-adds per pair | 128-256 | 20 |
| Parameters | 3 × d × d_model | 0 |
| Gradients | Required | None |

### 3.3 Candidate Pre-Filter (`symbolu/hybrid/prefilter.py`)

#### Purpose
Filter candidate words before expensive transformer inference.

#### Use Case

```
Scenario: Word prediction with 50,000 vocabulary

Traditional:
  Run transformer on all 50,000 → 500,000ms

With Pre-Filter:
  Phoneme filter (50,000) → 500 candidates (1ms)
  Run transformer on 500 → 5,000ms

  Speedup: 100x
```

#### Implementation

```python
class CandidatePreFilter:
    def __init__(self, threshold=0.5, top_k=None):
        self.threshold = threshold
        self.top_k = top_k

    def filter(self, candidates, target):
        scores = []
        for c in candidates:
            similarity = compare_words(c, target).similarity
            if similarity >= self.threshold:
                scores.append((c, similarity))

        if self.top_k:
            scores = sorted(scores, reverse=True)[:self.top_k]

        return [c for c, s in scores]
```

### 3.4 Semantic Router (`symbolu/hybrid/router.py`)

#### Purpose
Route queries to specialized sub-models based on phoneme signature.

#### Layer → Model Mapping

| Dominant Layer | Model Type | Example Query |
|---------------|------------|---------------|
| O9_UNIFYING | RELATIONSHIP | "Love conquers all" |
| O6_REASONING | REASONING | "Calculate the sum" |
| O3_ACTING | ACTION | "Run the build" |
| O2_FORMING | CREATIVE | "Create a poem" |
| O1_THINKING | REFLECTIVE | "What is consciousness" |
| O10_ABSOLVING | TRANSCENDENT | "The meaning of existence" |

#### Savings

```
Without Routing:
  All queries → 175B parameter model

With Routing:
  70% queries → 7B specialized models
  30% queries → 175B general model

  Average parameters: 0.7 × 7B + 0.3 × 175B = 57.4B
  Reduction: 3x fewer parameters per query
```

---

## 4. Data Flow

### Word → Vector Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                     WORD → VECTOR PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  "love"                                                          │
│     │                                                            │
│     ▼                                                            │
│  ┌─────────────────────────────────────────┐                    │
│  │ 1. PHONEME EXTRACTION                    │                    │
│  │    Dictionary: "love" → (L, AH, V)       │                    │
│  │    Fallback: grapheme-to-phoneme rules   │                    │
│  └─────────────────────────────────────────┘                    │
│     │                                                            │
│     ▼                                                            │
│  (L, AH, V)                                                      │
│     │                                                            │
│     ▼                                                            │
│  ┌─────────────────────────────────────────┐                    │
│  │ 2. AFFINITY LOOKUP                       │                    │
│  │    L  → [0.3, 0.6, 0.2, 0.2, 0.3, ...]  │                    │
│  │    AH → [0.5, 0.3, 0.2, 0.3, 0.2, ...]  │                    │
│  │    V  → [0.3, 0.4, 0.3, 0.2, 0.5, ...]  │                    │
│  └─────────────────────────────────────────┘                    │
│     │                                                            │
│     ▼                                                            │
│  ┌─────────────────────────────────────────┐                    │
│  │ 3. POSITION WEIGHTING                    │                    │
│  │    Position 0: weight = 1.5              │                    │
│  │    Position 1: weight = 1.25             │                    │
│  │    Position 2+: weight = 1.0             │                    │
│  └─────────────────────────────────────────┘                    │
│     │                                                            │
│     ▼                                                            │
│  ┌─────────────────────────────────────────┐                    │
│  │ 4. ACCUMULATE & NORMALIZE                │                    │
│  │    Sum weighted affinities               │                    │
│  │    Normalize to unit vector              │                    │
│  └─────────────────────────────────────────┘                    │
│     │                                                            │
│     ▼                                                            │
│  WordVector(                                                     │
│    word="love",                                                  │
│    phonemes=("L", "AH", "V"),                                   │
│    vector=(0.33, 0.40, 0.21, ...),  # 10 dimensions             │
│    dominant_layer="O9_UNIFYING",                                 │
│    dominant_score=0.40                                           │
│  )                                                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Phrase Analysis Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                   PHRASE ANALYSIS PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  "The sky is blue"                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────┐                    │
│  │ 1. TOKENIZE & FILTER                     │                    │
│  │    Remove stop words: the, is            │                    │
│  │    Content words: [sky, blue]            │                    │
│  └─────────────────────────────────────────┘                    │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────┐                    │
│  │ 2. VECTORIZE EACH WORD                   │                    │
│  │    sky  → vec_sky  (10D)                 │                    │
│  │    blue → vec_blue (10D)                 │                    │
│  └─────────────────────────────────────────┘                    │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────┐                    │
│  │ 3. PAIRWISE RESONANCE                    │                    │
│  │    sky ↔ blue: cosine(vec_sky, vec_blue) │                    │
│  │    similarity = 0.91 → HARMONIC          │                    │
│  └─────────────────────────────────────────┘                    │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────┐                    │
│  │ 4. AGGREGATE HARMONY                     │                    │
│  │    overall_harmony = mean(similarities)  │                    │
│  │    prediction = HARMONIC/NEUTRAL/DISSONANT│                   │
│  └─────────────────────────────────────────┘                    │
│         │                                                        │
│         ▼                                                        │
│  PhraseAnalysis(                                                 │
│    phrase="The sky is blue",                                     │
│    overall_harmony=0.91,                                         │
│    prediction="HARMONIC"                                         │
│  )                                                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Mathematical Foundations

### 5.1 Cosine Similarity

The core similarity measure between word vectors:

```
                    A · B           Σ(aᵢ × bᵢ)
cos(θ) = ────────────────── = ─────────────────────
              ‖A‖ × ‖B‖       √Σaᵢ² × √Σbᵢ²
```

Properties:
- Range: [-1, 1] for general vectors, [0, 1] for our non-negative vectors
- cos(θ) = 1: identical direction (perfect resonance)
- cos(θ) = 0: orthogonal (no resonance)

### 5.2 Vector Normalization

All word vectors are normalized to unit length:

```
         v
v̂ = ─────────
       ‖v‖

where ‖v‖ = √(v₁² + v₂² + ... + v₁₀²)
```

This ensures:
- All vectors lie on the unit hypersphere
- Cosine similarity = dot product
- Magnitude doesn't affect similarity

### 5.3 Position Weighting

Initial phonemes have more perceptual impact:

```
weighted_affinity[i] = affinity[i] × position_weight[i]

position_weight = [1.5, 1.25, 1.0, 1.0, ...]
```

Rationale: The first sound of a word is most salient in perception.

### 5.4 Harmony Thresholds

```
HARMONIC:   similarity ≥ 0.7  (vectors within ~45°)
NEUTRAL:    0.3 < similarity < 0.7
DISSONANT:  similarity ≤ 0.3  (vectors > ~72° apart)
```

---

## 6. Implementation Details

### 6.1 Phoneme Dictionary

The system uses ARPABET notation with a built-in dictionary of ~200 common words:

```python
PHONEME_DICT = {
    "love": ("L", "AH", "V"),
    "truth": ("T", "R", "UW", "TH"),
    "light": ("L", "AY", "T"),
    # ...
}
```

For unknown words, grapheme-to-phoneme rules apply:

```python
GRAPHEME_RULES = {
    "a": ("AE",), "e": ("EH",), "i": ("IH",),
    "ch": ("CH",), "sh": ("SH",), "th": ("TH",),
    # ...
}
```

### 6.2 Affinity Tuning

Each phoneme has manually tuned affinities to 10 layers:

```python
# Liquids: flowing, connecting → high UNIFYING
LIQUID_AFFINITIES = {
    "L": (0.3, 0.6, 0.2, 0.2, 0.3, 0.3, 0.4, 0.3, 0.6, 0.4),
    "R": (0.3, 0.5, 0.3, 0.2, 0.4, 0.3, 0.5, 0.3, 0.5, 0.3),
}

# Plosives: forceful, abrupt → high ACTING
PLOSIVE_AFFINITIES = {
    "P": (0.1, 0.3, 0.8, 0.2, 0.6, 0.2, 0.4, 0.1, 0.1, 0.1),
    "T": (0.2, 0.4, 0.7, 0.3, 0.5, 0.3, 0.3, 0.2, 0.1, 0.1),
    # ...
}
```

### 6.3 Immutability

All data structures use `frozen=True` dataclasses:

```python
@dataclass(frozen=True)
class WordVector:
    word: str
    phonemes: Tuple[str, ...]  # Tuple, not List
    vector: Tuple[float, ...]  # Immutable
```

Benefits:
- Thread-safe
- Hashable (can be dict keys)
- Prevents accidental modification
- Enables caching

### 6.4 Caching

Phoneme vectors are cached for repeated lookups:

```python
class PhonemeAttentionHead:
    def __init__(self):
        self._cache: Dict[str, WordVector] = {}

    def _get_vector(self, token):
        if token not in self._cache:
            self._cache[token] = analyze_word(token)
        return self._cache[token]
```

---

## 7. Benchmark Results

### Test Configuration

```
Tokens: ("truth", "is", "light", "and", "love", "conquers", "darkness")
Candidates: 25 words (light, dark, love, hate, etc.)
Queries: 8 sample phrases
```

### Results

| Optimization | Traditional | Optimized | Savings | Speedup |
|--------------|-------------|-----------|---------|---------|
| **Attention Head** | 6,321 FLOPs | 1,127 FLOPs | **82.2%** | **5.6x** |
| Hybrid Layer (12 heads) | 75,264 FLOPs | 64,680 FLOPs | 14.1% | 1.2x |
| Pre-Filter* | 250ms | 251ms | -0.5% | 1.0x |
| Router* | 1.4T params | 1.4T params | 0% | 1.0x |

*Pre-filter and router require threshold tuning for actual savings.

### Scaling Projections

| Sequence Length | Traditional (FLOPs) | Phoneme (FLOPs) | Speedup |
|-----------------|---------------------|-----------------|---------|
| 10 | 12,800 | 2,300 | 5.6x |
| 100 | 1,280,000 | 230,000 | 5.6x |
| 1000 | 128,000,000 | 23,000,000 | 5.6x |
| 10000 | 12,800,000,000 | 2,300,000,000 | 5.6x |

The speedup is constant regardless of sequence length because both are O(n²).

---

## 8. Development Guide

### 8.1 Adding New Words to Dictionary

Edit `symbolu/resonance/analyzer.py`:

```python
PHONEME_DICT["newword"] = ("N", "UW", "W", "ER", "D")
```

### 8.2 Tuning Phoneme Affinities

Edit `symbolu/resonance/phoneme_map.py`:

```python
# Increase UNIFYING affinity for nasals
NASAL_AFFINITIES = {
    "M": (0.4, 0.3, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.8, 0.4),  # O9 = 0.8
    #                                                    ↑
    #                                            Increased from 0.7
}
```

### 8.3 Running Benchmarks

```python
from symbolu.hybrid.benchmark import run_demo
run_demo()
```

### 8.4 Testing

```bash
# Run resonance engine tests
python -m pytest tests/resonance/ -v

# Manual verification
python -c "
from symbolu.resonance import analyze_word, compare_phrases
print(analyze_word('love'))
print(compare_phrases('Truth is light', 'Truth is darkness'))
"
```

### 8.5 Integration with Transformers

```python
# Example: Replace 2 of 12 attention heads
class HybridTransformerLayer:
    def __init__(self):
        self.phoneme_heads = [PhonemeAttentionHead() for _ in range(2)]
        self.traditional_heads = [TraditionalHead() for _ in range(10)]

    def forward(self, tokens):
        # Phoneme heads (fast, deterministic)
        phoneme_attn = [h.compute_attention(tokens) for h in self.phoneme_heads]

        # Traditional heads (learned)
        trad_attn = [h(tokens) for h in self.traditional_heads]

        # Concatenate and project
        return concat(phoneme_attn + trad_attn)
```

---

## 9. Future Work

### 9.1 Affinity Learning

Train phoneme affinities from corpus data:

```
Objective: Find affinities such that phoneme similarity
           correlates with corpus co-occurrence.

minimize Σ (phoneme_similarity(w₁, w₂) - corpus_similarity(w₁, w₂))²
```

### 9.2 Multi-Language Support

Extend phoneme maps to other languages:
- IPA (International Phonetic Alphabet) as universal representation
- Language-specific affinity tuning

### 9.3 Hierarchical Routing

Multi-stage routing with increasing specialization:

```
Query → Phoneme Router → Domain Router → Task Router → Model
```

### 9.4 Integration with Existing Frameworks

- PyTorch attention layer drop-in replacement
- Hugging Face model wrapper
- ONNX export for inference optimization

### 9.5 Hardware Optimization

- SIMD vectorization for 10D operations
- GPU kernel for batched phoneme attention
- Quantization (10D fits in 80 bits)

---

## Appendix A: API Reference

### Resonance Engine

```python
from symbolu.resonance import (
    analyze_word,       # Word → WordVector
    analyze_phrase,     # Phrase → PhraseAnalysis
    compare_words,      # (word, word) → ResonanceResult
    compare_phrases,    # (phrase, phrase) → ComparisonResult
    quick_compare,      # (phrase, phrase) → str (human-readable)
)
```

### Hybrid Optimization

```python
from symbolu.hybrid import (
    PhonemeAttentionHead,   # Drop-in attention replacement
    CandidatePreFilter,     # Pre-filter before inference
    SemanticRouter,         # Route to specialized models
    ComputationBenchmark,   # Measure savings
)
```

---

## Appendix B: Phoneme Inventory

| Category | Phonemes | Example |
|----------|----------|---------|
| Plosives | P, B, T, D, K, G | pat, bat, tap, dap, cap, gap |
| Fricatives | F, V, TH, DH, S, Z, SH, ZH, HH | fat, vat, thin, this, sat, zap, ship, vision, hat |
| Affricates | CH, JH | chat, judge |
| Nasals | M, N, NG | mat, nat, sing |
| Liquids | L, R | lat, rat |
| Glides | W, Y | wat, yat |
| Short Vowels | IH, EH, AE, AH, UH | bit, bet, bat, but, book |
| Long Vowels | IY, EY, AA, AO, OW, UW | beat, bait, father, thought, boat, boot |
| Diphthongs | AY, AW, OY, ER | bite, bout, boy, bird |

---

## Appendix C: Example Outputs

### Word Analysis

```python
>>> from symbolu.resonance import analyze_word
>>> vec = analyze_word("love")
>>> print(f"Word: {vec.word}")
>>> print(f"Phonemes: {vec.phonemes}")
>>> print(f"Dominant: {vec.dominant_layer} ({vec.dominant_score:.2f})")

Word: love
Phonemes: ('L', 'AH', 'V')
Dominant: O9_UNIFYING (0.40)
```

### Phrase Comparison

```python
>>> from symbolu.resonance import compare_phrases
>>> result = compare_phrases("Truth is light", "Truth is darkness")
>>> print(f"A harmony: {result.analysis_a.overall_harmony:.2f}")
>>> print(f"B harmony: {result.analysis_b.overall_harmony:.2f}")
>>> print(f"Insight: {result.insight}")

A harmony: 0.99
B harmony: 1.00
Insight: Both phrases have similar phonetic harmony.
```

### Attention Computation

```python
>>> from symbolu.hybrid import PhonemeAttentionHead
>>> attn = PhonemeAttentionHead()
>>> result = attn.compute_attention(("love", "peace", "war"))
>>> print(f"FLOPs: {result.computation_flops}")
>>> print(f"Dominant layers: {result.dominant_layers}")

FLOPs: 207
Dominant layers: ('O9_UNIFYING', 'O9_UNIFYING', 'O3_ACTING')
```

---

## Terminology

This document uses **Symbolic Transformer Engine (STE)** as the canonical name for Symbolu's computational architecture. Alternative acceptable terms:
- Ontological Transformer
- Phoneme-Transformer Hybrid (for the optimization layer only)

**Do not use**: "neural transformer", "language model", "AI model"

---

*Document Version: 2.0*
*Last Updated: 2025-12-20*
*Authors: Symbol-U Development Team*

**Changelog**:
- v2.0 (2025-12-20): Added Symbolic Transformer Foundations section with explicit transformer-class framing, non-capabilities, and canonical comparison table
- v1.0 (2025-12-18): Initial optimization layer documentation
