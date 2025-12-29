# Ontological State-Delta Training: Design Document

## Executive Summary

A paradigm shift from token-centric to meaning-centric training, enabling theoretically unlimited context with interpretable representations.

**One-sentence summary:**
> Traditional LLMs learn what word to say next; state-delta training learns how understanding itself should change.

---

## Three-Tier Model Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  TIER 1: Token-Centric (Standard LLM)                                   │
│  ════════════════════════════════════                                   │
│  Training:  hidden → LM_head[50K] → cross_entropy                       │
│  Predicts:  P(token_{t+1} | context)                                    │
│  Memory:    O(B·T·V) = 200GB at 1M context                              │
│  Status:    PRODUCTION (loss_type: cross_entropy, contrastive, infonce) │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  TIER 2: State-Delta (Current Implementation)                           │
│  ════════════════════════════════════════════                           │
│  Training:  hidden → delta_predictor[768] → state_delta_loss            │
│  Predicts:  ΔH = H_{t+1} - H_t (hidden space)                           │
│  Memory:    O(B·T·d) = 3GB at 1M context (65x reduction)                │
│  Status:    PRODUCTION (loss_type: state_delta)                         │
│  Location:  symbolu/phase_transformer.py::StateDeltaPredictor           │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  TIER 3: Ontological State-Delta (EXPERIMENTAL)                         │
│  ══════════════════════════════════════════════                         │
│  Training:  hidden → projector → CognitiveState[124] → onto_delta_loss  │
│  Predicts:  ΔS = S_{t+1} - S_t (meaning space)                          │
│  Memory:    O(B·T·s) = 500MB at 1M context (400x reduction)             │
│  Status:    EXPERIMENTAL                                                │
│  Location:  symbolu/experimental/cognitive_state.py                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Memory Comparison

| Context | Tier 1 (Tokens) | Tier 2 (Hidden) | Tier 3 (Ontological) |
|---------|-----------------|-----------------|----------------------|
| 100K    | 20 GB           | 300 MB          | 50 MB                |
| 500K    | 100 GB          | 1.5 GB          | 250 MB               |
| 1M      | 200 GB          | 3 GB            | 500 MB               |
| 5M      | 1 TB            | 15 GB           | 2.5 GB               |
| 10M     | 2 TB            | 30 GB           | 5 GB                 |
| 100M    | 20 TB           | 300 GB          | 50 GB                |

---

## Cognitive State Structure

```python
CognitiveState = {
    # Phonemic layer (44 dims) - acoustic energy distribution
    phoneme_energy: [h:0.1, ə:0.2, l:0.05, ...],

    # Topic layer (64 dims) - domain/subject embedding
    topic_embedding: [business:0.8, tech:0.1, ...],

    # Ontological layer (12 dims) - Bhava state probabilities
    ontology_probs: [ANALYTICAL:0.6, EVALUATIVE:0.3, NEGATIVE:0.1, ...],

    # Dynamics layer (4 dims)
    coherence: 0.85,      # Phase alignment
    entropy: 0.6,         # Uncertainty level
    confidence: 0.5,      # Belief strength
    momentum: 0.3,        # Rate of meaning change

    # Total: 124 dimensions (vs 768 hidden, 50257 vocab)
}
```

---

## Information Flow

```
INPUT: "The company reported strong revenue growth, but..."
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHONEME PERCEPTION                                              │
│ Not tokenization — acoustic/meaning pattern detection           │
│ Detects: contrast marker ("but"), business domain, rhetorical   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ CURRENT STATE Sₜ                                                │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ topic:      financial_performance                           │ │
│ │ sentiment:  positive                                        │ │
│ │ ontology:   analytical/descriptive                          │ │
│ │ coherence:  0.85                                            │ │
│ │ entropy:    0.3 (low uncertainty)                           │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE ATTENTION Φ                                               │
│ O(n) smooth memory evolution — not token-pair comparison        │
│ Integrates: earlier "revenue", long-range context, tone         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STATE DELTA ΔSₜ  ← THIS IS WHAT IS LEARNED                      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ sentiment:   positive → cautious (shift)                    │ │
│ │ entropy:     0.3 → 0.6 (uncertainty introduced)             │ │
│ │ constraint:  next must explain downside                     │ │
│ │ ontology:    moves toward risk_assessment                   │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ NEXT STATE Sₜ₊₁                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ topic:      financial_performance                           │ │
│ │ sentiment:  mixed/cautious                                  │ │
│ │ ontology:   analytical + risk_assessment                    │ │
│ │ coherence:  0.85 (maintained)                               │ │
│ │ entropy:    0.6 (higher)                                    │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ TOKEN PROJECTION (only if output needed)                        │
│ Constraint mask → only "costs", "margins", "headwinds" legal    │
│ No 50K softmax. Sparse, cheap, constrained.                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Loss Functions

### Tier 1 (Token-Centric)
```
L = -log P(token_{t+1} | tokens_{0:t})
```

### Tier 2 (State-Delta)
```
L = MSE(ΔH_pred, ΔH_actual) + λ_coherence + λ_entropy + λ_constraint
```

### Tier 3 (Ontological)
```
L = MSE(ΔS_pred, ΔS_actual)                    # State prediction
  + λ₁ · OntologyTransitionLoss(S_t, S_{t+1})  # Bhava transition validity
  + λ₂ · CoherenceDrift(S_t, S_{t+1})          # Phase alignment
  + λ₃ · EntropyMismatch(S_{t+1})              # Uncertainty calibration
  + λ₄ · ConstraintViolation(S_{t+1})          # Illegal meaning jumps
```

---

## Why This Works

### 1. Phonemes are Universal
| Language   | Tokens        | Phonemes    |
|------------|---------------|-------------|
| English    | ~50K tokens   | ~44 phonemes|
| Mandarin   | ~20K chars    | ~35 phonemes|
| All human  | Millions      | ~600 total  |

### 2. Constraints Reduce Search Space
```
Full vocabulary:      50,257 tokens
Phonemically legal:   ~1,000 tokens  (phonotactic constraints)
Ontologically valid:  ~100 tokens    (meaning constraints)
Contextually likely:  ~10 tokens     (state constraints)

Cross-entropy wastes 99.98% of computation on impossible tokens.
```

### 3. Matches Human Cognition
**Humans do NOT:**
- Compute probabilities over all possible words
- Reconsider entire vocabulary each moment

**Humans DO:**
- Update understanding continuously
- Narrow what can be said based on context
- Speak as a projection of understanding

---

## File Structure

```
symbolu/
├── phase_transformer.py          # Tier 1 & 2 (PRODUCTION)
│   ├── PhaseTransformer
│   ├── HybridPhaseTransformer
│   └── StateDeltaPredictor       # Tier 2
│
├── experimental/                 # Tier 3 (EXPERIMENTAL)
│   ├── __init__.py
│   ├── cognitive_state.py        # CognitiveState, StateDelta
│   │   ├── CognitiveState
│   │   ├── StateDelta
│   │   ├── StateProjector
│   │   ├── OntologicalDeltaPredictor
│   │   └── ConstraintMaskGenerator
│   └── ontological_trainer.py    # Training loop for Tier 3
│
└── train.py                      # Supports Tier 1 & 2
    └── --loss_type state_delta   # Tier 2 training
```

---

## Usage

### Tier 2 (Production - State Delta)
```bash
python train.py \
    --loss_type state_delta \
    --max_seq_len 10000000 \
    --model_type hybrid
```

### Tier 3 (Experimental - Ontological)
```python
from symbolu.experimental.cognitive_state import (
    StateProjector,
    OntologicalDeltaPredictor,
)

# Project hidden states to cognitive states
projector = StateProjector(hidden_dim=768)
cognitive_states = projector(hidden_states)  # [B, T, 124]

# Predict ontological deltas
predictor = OntologicalDeltaPredictor(state_dim=124)
loss, metrics = predictor.compute_loss(cognitive_states)
```

---

## Research Questions

1. **Expressiveness**: Is 124-dim cognitive state expressive enough for all language?
2. **Decoding**: Can we decode fluent text from Bhava states?
3. **Transfer**: Does ontological training transfer across languages?
4. **Grounding**: How do we learn the phoneme→ontology mapping?

---

## The Vision

```
Current LLMs:    tokens ──────────────────────────────> tokens
                          (learn surface patterns)

State-Delta:     tokens → hidden ────────────> hidden → tokens
                               (learn hidden dynamics)

Ontological:     tokens → phonemes → MEANING → MEANING → phonemes → tokens
                                    (learn how understanding changes)
                                          ↑
                                    THE PARADIGM SHIFT
```

**Tokens are no longer the thing being learned. State change is the thing being learned.**
