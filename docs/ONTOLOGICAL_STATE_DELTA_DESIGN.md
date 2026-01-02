# Ontological State-Delta Training: Design Document

## Executive Summary

A paradigm shift from token-centric to meaning-centric training, enabling theoretically unlimited context with interpretable representations.

**One-sentence summary:**
> Traditional LLMs learn what word to say next; state-delta training learns how understanding itself should change.

---

## Architecture Evolution

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  GENERATION 1: Flat Bhava (Original)                                    │
│  ════════════════════════════════════                                   │
│  - 12 ontological layers treated equally                                │
│  - Real-valued embeddings                                               │
│  - 144D relationship matrix (12×12)                                     │
│  - Vedic aspect patterns (Drishti)                                      │
│  - Status: PRODUCTION                                                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GENERATION 2: Hierarchical Complex Bhava (NEW)                         │
│  ══════════════════════════════════════════════                         │
│  - 3-tier hierarchy (Intent → Abstract → Concrete)                      │
│  - Complex-valued embeddings: z = r × e^{iθ}                           │
│  - Phase rotation for top-down context setting                          │
│  - Higher layers ORIENT lower layers via phase                          │
│  - Status: EXPERIMENTAL                                                 │
│  - Location: symbolu/ontological/hierarchical_complex_bhava.py          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## NEW: Hierarchical Complex Phase Rotation

### The Core Insight (from Neuroscience)

Consciousness isn't just about "turning parts of the brain on or off" (Gating) or "making them louder" (Weighting). It is about **SYNCHRONIZATION and PHASE-ALIGNMENT**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   THREE APPROACHES TO STATE MODULATION                                  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │ A. WEIGHTED (Additive)                                           │  │
│   │    state = Σ wₖ × zₖ                                             │  │
│   │    ⚠️ Signal DILUTES over long context                           │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │ B. GATING (Multiplicative)                                       │  │
│   │    state = σ(higher) × lower                                     │  │
│   │    ⚠️ Too BINARY for nuanced state deltas                        │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │ C. PHASE ROTATION (Orientation) ← THE WINNER                     │  │
│   │    z_lower' = z_lower × e^{iθ_higher}                            │  │
│   │    ✓ Matches Phase-Amplitude Coupling in EEG                     │  │
│   │    ✓ Same weights, different context via rotation                │  │
│   │    ✓ Scales to unlimited context (orient, not search)            │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Complex-Valued State Representation

Each Bhava layer is now represented as a **complex number**:

```
z = r × e^{iθ}

Where:
  r = magnitude = INTENSITY/CERTAINTY of the state
  θ = phase = QUALITY/MODE of being
```

**State transitions become complex multiplication:**
```
z_new = z_old × Δz
      = (r₁e^{iθ₁}) × (r₂e^{iθ₂})
      = r₁r₂ × e^{i(θ₁+θ₂)}

This means:
  - Phase ADDS → states compose naturally
  - Magnitude MULTIPLIES → certainty propagates
  - Unit circle (|z|=1) → pure states
```

### The 3-Tier Bhava Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  LEVEL 3: TRANSCENDENT/INTENT (Sets the Context)                        │
│  ═════════════════════════════════════════════════                      │
│  Layers 9-11: O10_UNIFYING, O11_INTEGRATION, O12_ABSOLVING              │
│  Bhava: Karma (Action), Labha (Gains), Moksha (Liberation)              │
│                                                                         │
│  → Extracts dominant phase θ₃                                           │
│  → This phase ROTATES Level 2                                           │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LEVEL 2: ABSTRACT/RELATIONAL (Mediates)                                │
│  ════════════════════════════════════════                               │
│  Layers 5-8: O6_AGENCY, O7_REASONING, O8_PURPOSE, O9_WITNESSES          │
│  Bhava: Ripu (Obstacles), Kalatra (Partnership),                        │
│         Randhra (Transformation), Dharma (Wisdom)                       │
│                                                                         │
│  → Receives rotation from Level 3: z₂' = z₂ × e^{iθ₃}                  │
│  → Extracts its own phase θ₂'                                           │
│  → This phase ROTATES Level 1                                           │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LEVEL 1: CONCRETE/SENSORY (Receives Context)                           │
│  ═════════════════════════════════════════════                          │
│  Layers 0-4: O1_POTENTIAL, O2_IDENTITY, O3_EXECUTION,                   │
│              O4_STRUCTURE, O5_COGNITION                                 │
│  Bhava: Tanu (Self), Dhana (Wealth), Sahaja (Effort),                   │
│         Sukha (Happiness), Putra (Intelligence)                         │
│                                                                         │
│  → Receives rotation from Level 2': z₁' = z₁ × e^{iθ₂'}                │
│  → Final state carries context from BOTH higher levels                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Magic: Context-Dependent Interpretation

```
EXAMPLE: Same sensory input, different meaning

Input: "The door is open"

┌─────────────────────────────────────────────────────────────────────────┐
│  SCENARIO A: Intent = "Enter building"                                  │
│  ─────────────────────────────────────                                  │
│  Level 3 phase θ₃ = 0° (aligned with entry)                             │
│  Level 1 ("door open") rotated by θ₃                                    │
│  → Interpretation: OPPORTUNITY, proceed through                         │
├─────────────────────────────────────────────────────────────────────────┤
│  SCENARIO B: Intent = "Secure building"                                 │
│  ─────────────────────────────────────                                  │
│  Level 3 phase θ₃ = 180° (security mode)                                │
│  Level 1 ("door open") rotated by θ₃                                    │
│  → Interpretation: PROBLEM, need to close/investigate                   │
└─────────────────────────────────────────────────────────────────────────┘

SAME z₁ (raw perception) + DIFFERENT θ₃ (intent) = DIFFERENT z₁' (meaning)

This is how consciousness works: same signal, context-dependent meaning.
```

### Why This Wins for Long Context (131K+)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  WEIGHTED ATTENTION:                                                    │
│  → Signal DILUTES over 131K context                                     │
│  → "Everyone talking, nobody heard"                                     │
│                                                                         │
│  GATING ATTENTION:                                                      │
│  → Must IGNORE 99% of context to focus                                  │
│  → "Picking one voice, losing the room"                                 │
│                                                                         │
│  PHASE ROTATION:                                                        │
│  → ORIENT into the right state, context resonates                       │
│  → "Tuning to the right frequency, all information available"           │
│  → 131K context always present, phase determines what's in sync         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

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

---

## Usage: Hierarchical Complex Bhava

### Basic Usage

```python
from symbolu.ontological.hierarchical_complex_bhava import (
    HierarchicalComplexBhava,
    HierarchicalBhavaUnifyingLayer,
)

# Standalone hierarchical Bhava
bhava = HierarchicalComplexBhava(embed_dim=64)

# Forward pass with ontological probabilities
ontological_probs = torch.softmax(torch.randn(B, 12), dim=-1)
output = bhava(ontological_probs)

# Outputs:
# - bhava_complex: [B, 12, embed_dim, 2] hierarchically-oriented states
# - relationship_matrix: [B, 12, 12] inter-layer relationships
# - coherence: [B] overall phase coherence
# - level_coherences: [B, 3] per-level coherence
# - level_phases: [B, 3, embed_dim] dominant phase per level
```

### Drop-in Replacement for BhavaUnifyingLayer

```python
# In SymbolU12LLMWithBhava, replace:
#   self.unifying_layer = BhavaUnifyingLayer(config)
# With:
#   self.unifying_layer = HierarchicalBhavaUnifyingLayer(config)

# All existing code continues to work with enhanced hierarchical processing
```

### Accessing Level States

```python
output = bhava(ontological_probs)

# Level 3 (Intent): Sets the global context
level_3_state = output['level_3_state']  # [B, 3, embed_dim, 2]

# Level 2 (Abstract): Rotated by Level 3
level_2_state = output['level_2_state']  # [B, 4, embed_dim, 2]

# Level 1 (Concrete): Rotated by Level 2 (carries both contexts)
level_1_state = output['level_1_state']  # [B, 5, embed_dim, 2]

# Phase coherence per level
coh_1, coh_2, coh_3 = output['level_coherences'].unbind(dim=1)
```

### Train with Hierarchical Bhava

```bash
# Use train_unified_llm.py with ontological model
python train_unified_llm.py \
    --model_type ontological \
    --model_size small \
    --dataset wikitext103 \
    --max_steps 10000 \
    --checkpoint_dir checkpoints_hierarchical
```

---

## File Structure (Updated)

```
symbolu/
├── phase_transformer.py              # Phase Attention (O(n))
├── ontological/
│   ├── symbolu12_bhava.py            # Gen 1: Flat Bhava (PRODUCTION)
│   ├── bhava_relationships.py        # Vedic relationship logic
│   ├── hierarchical_complex_bhava.py # Gen 2: Hierarchical Complex (EXPERIMENTAL)
│   └── types.py                      # Layer names, indices
│
├── train_unified_llm.py              # Supports all architectures
├── train_7b.py                       # Pure Phase 7B (no Bhava)
│
└── docs/
    ├── STATE_DELTA_COGNITION_THEORY.md
    └── ONTOLOGICAL_STATE_DELTA_DESIGN.md (this file)
```
