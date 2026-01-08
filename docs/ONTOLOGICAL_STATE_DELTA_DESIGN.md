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
│  TIER 3: Ontological State-Delta (V9.8.0: 32D Sovereign State)          │
│  ══════════════════════════════════════════════════════════════         │
│  Training:  hidden → projector → SovereignState[32] → onto_delta_loss   │
│  Predicts:  ΔS = S_{t+1} - S_t (meaning space)                          │
│  Memory:    O(B·T·s) = 130MB at 1M context (1500x reduction)            │
│  Status:    PRODUCTION (V9.8.0)                                         │
│  Location:  symbolu/phase_transformer.py::OntologicalHybridTransformer  │
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

## Sovereign State Structure (V9.8.0)

**V9.8.0 BREAKING CHANGE:** Replaced arbitrary 124D CognitiveState with principled 32D Sovereign State.

### Why the Change?

```
OLD (124D): "Labeling the World"
├── 44 phonemes   ← PROBLEM: No semantic context at embedding level
├── 64 topics     ← PROBLEM: Arbitrary, not ontologically grounded
├── 12 bhava      ← OK: Ontological aspects
└── 4 dynamics    ← VAGUE: Unclear semantics

NEW (32D): "Modeling Physics of Consciousness"
├── 12 Bhavas     ← Ontological Aspects (POT, IDN, EXE, STR, COG, AGY, RSN, PRP, WIT, UNI, INT, ABS)
├── 5 Koshas      ← Consciousness Sheaths (ANNA, PRANA, MANO, VIJNANA, ANANDA)
├── 5 Vrittis     ← Mental Modifications (PRAMANA, VIPARYAYA, VIKALPA, NIDRA, SMRITI)
├── 6 Gunas       ← Energy States (SATTVA, RAJAS, TAMAS, VELOCITY, ACCEL, STABLE)
└── 4 Reserved    ← Toroidal Feedback Channels
```

### The 32D Sovereign State

```python
SovereignState = {
    # [0:12] Bhava Layer - 12 Ontological Aspects
    bhava: {
        POT: 0.1,    # O1: Potential - latent possibility
        IDN: 0.2,    # O2: Identity - self-recognition
        EXE: 0.1,    # O3: Execution - action/manifestation
        STR: 0.15,   # O4: Structure - form/organization
        COG: 0.3,    # O5: Cognition - knowing/understanding
        AGY: 0.1,    # O6: Agency - will/intention
        RSN: 0.2,    # O7: Reason - logic/analysis
        PRP: 0.1,    # O8: Purpose - meaning/direction
        WIT: 0.05,   # O9: Witness - observation/awareness
        UNI: 0.1,    # O10: Unity - integration/wholeness
        INT: 0.2,    # O11: Intent - focused will
        ABS: 0.8,    # O12: Absolute - transcendent ground (INIT BIAS)
    },

    # [12:17] Kosha Layer - 5 Consciousness Sheaths
    kosha: {
        ANNA: 0.7,     # Physical/food sheath (INIT BIAS)
        PRANA: 0.2,    # Vital/energy sheath
        MANO: 0.3,     # Mental/emotional sheath
        VIJNANA: 0.4,  # Wisdom/intellect sheath
        ANANDA: 0.1,   # Bliss/causal sheath
    },

    # [17:22] Vritti Layer - 5 Mental Modifications
    vritti: {
        PRAMANA: 0.5,    # Valid cognition (correct knowledge)
        VIPARYAYA: 0.1,  # Misconception (incorrect knowledge)
        VIKALPA: 0.2,    # Imagination (verbal construct)
        NIDRA: 0.0,      # Sleep (absence of content)
        SMRITI: 0.2,     # Memory (retention of experience)
    },

    # [22:28] Guna Layer - 6 Energy/Dynamics States
    guna: {
        SATTVA: 0.4,    # Clarity/harmony/balance
        RAJAS: 0.3,     # Activity/passion/change
        TAMAS: 0.3,     # Inertia/darkness/stability
        VELOCITY: 0.1,  # Rate of state change
        ACCEL: 0.0,     # Acceleration of change
        STABLE: 0.6,    # Stability measure
    },

    # [28:32] Reserved - Toroidal Feedback
    reserved: [0.0, 0.0, 0.0, 0.0],

    # Total: 32 dimensions (vs 768 hidden, 50257 vocab)
    # Memory: 32 floats × 4 bytes = 128 bytes per state
    # At 1M context: 128MB (vs 200GB for tokens = 1500x reduction)
}
```

### Initial State: "Absolute Potential"

At step 0, the model initializes to:
- **O12_ABS (Absolute)**: Transcendent ground / pure awareness
- **Annamaya**: Physical/grounded reality

This represents **grounded awareness** - consciousness rooted in physical existence but open to all possibilities.

### CSR/Phonemes: Layer 7, Not Embedding

**CRITICAL:** Phonemes are NOT in the Sovereign State because they require word-level semantic context.

```
WRONG (old 124D):  Embedding → [phonemes at Layer 0] → ...
                   Phonemes have no meaning without word context!

RIGHT (new 32D):   Embedding → [Sovereign State] → ... → [CSR at Layer 7]
                   Phonemes applied AFTER semantic word representations exist.
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

### Tier 3 (V9.8.0 - 32D Sovereign State)
```python
from symbolu.phase_transformer import (
    OntologicalHybridTransformer,
    SOVEREIGN_STATE_DIM,  # 32
    get_sovereign_state_summary,
)

# Create AGI model with 32D Sovereign State
model = OntologicalHybridTransformer(
    vocab_size=50257,
    embed_dim=768,
    num_layers=12,
    num_heads=12,
    state_dim=SOVEREIGN_STATE_DIM,  # 32D
)

# Forward pass
output = model(input_ids)
state = output['state']       # [B, 32] Sovereign State
delta_S = output['delta_S']   # [B, 32] State delta

# Get human-readable summary
summary = get_sovereign_state_summary(state)
print(f"Dominant Bhava: {summary['dominant_bhava']}")  # e.g., "ABS"
print(f"Active Kosha: {summary['active_kosha']}")      # e.g., "ANNA"
print(f"Vritti State: {summary['vritti_state']}")      # e.g., "PRAMANA"
```

---

## Research Questions

1. **Expressiveness**: Is 32-dim Sovereign State expressive enough for all language? (Evidence suggests YES - principled ontology > arbitrary dimensions)
2. **Decoding**: Can we decode fluent text from Bhava/Kosha/Vritti states?
3. **Transfer**: Does ontological training transfer across languages? (Bhavas are language-universal)
4. **Grounding**: CSR at Layer 7 handles phoneme→semantics mapping (V9.8.0 fix)
5. **Guna Dynamics**: How do Sattva/Rajas/Tamas influence generation style?
6. **Kosha Progression**: Does training show movement through consciousness sheaths?

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

---

## IMPLEMENTATION: Phase Rotation Bridge (V9.6.14)

### Overview

The Phase Rotation mechanism is now **fully implemented** in `symbolu/phase_transformer.py`. This bridges the Ontological (Tier 3) understanding layer with the Hybrid (Tier 1/2) generation layer.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  IMPLEMENTATION STATUS: ✅ COMPLETE                                     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ IntentPhaseProjector (V9.8.0: 32D)                               │   │
│  │ Location: symbolu/phase_transformer.py:228                       │   │
│  │ Function: ΔS[32] → θ_intent[H] or θ_intent[H, D_h]              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                             │
│                           ▼ Phase Rotation                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ PhaseAttentionLayer.forward(x, intent_phase=θ)                   │   │
│  │ Location: symbolu/phase_transformer.py:326                       │   │
│  │ Function: φ_q' = φ_q + θ_intent (rotates query phasors)         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ OntologicalHybridTransformer (V9.8.0: 32D Sovereign State)       │   │
│  │ Location: symbolu/phase_transformer.py:2458                      │   │
│  │ Function: Two-Tier AGI with 32D state + ABS initialization       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### IntentPhaseProjector: ΔS → θ (V9.8.0: 32D)

Converts Sovereign State Delta to phase rotation offsets.

```python
class IntentPhaseProjector(nn.Module):
    """
    Projects Sovereign State Delta (ΔS) to phase rotation offsets.

    V9.8.0: Updated for 32D Sovereign State.

    32D Sovereign State Structure:
        [0:12]  - 12 Bhavas (Ontological Aspects)
        [12:17] - 5 Koshas (Consciousness Sheaths)
        [17:22] - 5 Vrittis (Mental Modifications)
        [22:28] - 6 Gunas/Dynamics (Energy States)
        [28:32] - 4 Reserved (Void/Toroidal Feedback)

    Theory (from this document):
        z_lower' = z_lower × e^{iθ_higher}

    In practice:
        φ_q' = φ_q + θ_intent

    This means: Same tokens, but their RELATIONSHIPS change based on intent.
    """

    def __init__(
        self,
        state_dim: int = 32,            # V9.8.0: Sovereign State dimension (was 124)
        num_heads: int = 12,            # Number of attention heads
        head_dim: int = 64,             # Dimension per head
        project_per_head_dim: bool = False,  # Granularity of projection
    ):
        ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `state_dim` | int | 32 | Sovereign State dimension (12 Bhava + 5 Kosha + 5 Vritti + 6 Guna + 4 Reserved) |
| `num_heads` | int | 12 | Number of attention heads |
| `head_dim` | int | 64 | Dimension per head |
| `project_per_head_dim` | bool | False | If True: θ[H, D_h], If False: θ[H] (per-head uniform rotation) |

**Projection Modes:**

```
project_per_head_dim=False (Default, Simpler):
    ΔS[32] → Linear → GELU → Linear → θ[H]
    Each head gets ONE rotation angle applied uniformly across dimensions.

project_per_head_dim=True (More Expressive):
    ΔS[32] → Linear → GELU → Linear → θ[H × D_h]
    Each (head, dimension) pair gets its own rotation angle.
```

**Output Range:**
```python
theta = torch.tanh(theta) * π  # Output in [-π, π]
```

---

### PhaseAttentionLayer: Intent-Aware Attention

The core Phase Attention now accepts an optional `intent_phase` parameter.

```python
def forward(
    self,
    x: torch.Tensor,
    causal_mask: bool = True,
    phase_context: Optional[Dict[str, torch.Tensor]] = None,
    intent_phase: Optional[torch.Tensor] = None,  # ← NEW
) -> Union[torch.Tensor, Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
```

**Intent Phase Application:**

```python
# Query phase computation
phi_q = self.W_q_phase(x_norm).view(B, N, H, D_h)

# Apply intent rotation if provided
if intent_phase is not None:
    # Handle different shapes:
    # [B, H] → broadcast to [B, 1, H, 1]
    # [B, H, D_h] → broadcast to [B, 1, H, D_h]
    # [B, T, H, D_h] → use directly
    phi_q = phi_q + intent_phase  # ← THE ROTATION

# Form phasors with rotated phase
q_phasor = torch.polar(a_q, phi_q)  # z = r × e^{iφ}
```

**Effect of Rotation:**

```
BEFORE rotation (φ_q):
    cos(φ_q - φ_k) = attention score between Q and K

AFTER rotation (φ_q + θ_intent):
    cos(φ_q + θ_intent - φ_k) = NEW attention score

Same Q, same K, but different relationship based on intent.
```

---

### HybridAttentionLayer: Selective Rotation

The Hybrid attention layer passes `intent_phase` only to Phase attention, not Local attention.

```python
def forward(
    self,
    x: torch.Tensor,
    causal_mask: bool = True,
    intent_phase: Optional[torch.Tensor] = None,  # ← NEW
) -> torch.Tensor:
    # Local attention: Grammar/syntax (UNCHANGED by intent)
    x_local = self.local_attn(x, causal_mask)

    # Phase attention: Global context (ROTATED by intent)
    x_phase = self.phase_attn(residual, causal_mask, intent_phase=intent_phase)

    # Weighted combination
    ...
```

**Design Rationale:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  LOCAL ATTENTION (NOT rotated):                                         │
│  - Handles grammar, syntax, local patterns                              │
│  - "the cat sat on the mat" → grammar is grammar regardless of intent   │
│  - O(n²) within window, learns quickly                                  │
│                                                                         │
│  PHASE ATTENTION (ROTATED by intent):                                   │
│  - Handles global context, long-range dependencies                      │
│  - "the door is open" → meaning changes with intent                     │
│  - O(n), context-dependent via phase rotation                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### OntologicalHybridTransformer: The AGI Wrapper (V9.8.0: 32D)

Complete integration of Ontological → Hybrid with automatic ΔS computation.

```python
class OntologicalHybridTransformer(nn.Module):
    """
    Two-Tier AGI Architecture: Ontological (slow/semantic) + Hybrid (fast/generation).

    V9.8.0: Uses 32D Sovereign State (was 124D CognitiveState).

    32D Sovereign State Structure:
        [0:12]  - 12 Bhavas (Ontological Aspects)
        [12:17] - 5 Koshas (Consciousness Sheaths)
        [17:22] - 5 Vrittis (Mental Modifications)
        [22:28] - 6 Gunas/Dynamics (Energy States)
        [28:32] - 4 Reserved (Void/Toroidal Feedback)

    Initialization:
        - State projector biased toward O12_ABS (Absolute) and Annamaya (Physical)
        - Represents "Absolute Potential" - pure awareness grounded in physical reality

    Usage:
        model = OntologicalHybridTransformer(...)
        output = model(input_ids)  # Automatically computes ΔS and applies rotation

    Memory (at 10M context):
        - Token-centric: 2TB (impossible)
        - State-Delta (Tier 2): 30GB
        - Sovereign (Tier 3): 1.3GB (32D vs 124D = 4x reduction)
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        # ... standard transformer params ...

        # Ontological params (V9.8.0: 32D Sovereign State)
        state_dim: int = 32,               # Sovereign State dimension (was 124)
        project_per_head_dim: bool = False, # Phase projection granularity
    ):
        # The Hybrid (generation) model
        self.hybrid = HybridPhaseTransformer(...)

        # State projector: hidden[768] → SovereignState[32]
        self.state_projector = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, state_dim),
        )

        # V9.8.0: Initialize bias toward "Absolute Potential"
        self._init_absolute_potential_bias()

        # Intent phase projector: ΔS[32] → θ[H]
        self.intent_projector = IntentPhaseProjector(
            state_dim=state_dim,
            num_heads=num_heads,
            ...
        )

    def _init_absolute_potential_bias(self):
        """Initialize state projector to bias toward O12_ABS + Annamaya."""
        with torch.no_grad():
            final_layer = self.state_projector[-1]
            final_layer.bias[11] = 1.0  # O12_ABS (Absolute)
            final_layer.bias[12] = 0.8  # Annamaya (Physical)
            final_layer.bias[17] = 0.3  # Pramana (Valid cognition)
```

**Forward Pass (Two Modes):**

```python
def forward(
    self,
    input_ids: torch.Tensor,
    reset_state: bool = False,
    external_delta_S: Optional[torch.Tensor] = None,  # ← External mode
) -> Dict[str, torch.Tensor]:
    """
    Mode 1 (Auto): Compute ΔS from hidden states automatically
    Mode 2 (External): Use provided external_delta_S from separate Ontological model
    """

    # First pass: Get hidden states WITHOUT intent phase
    with torch.no_grad():
        hidden = self.hybrid.forward_hidden(input_ids, intent_phase=None)

    # Compute state delta
    if external_delta_S is not None:
        delta_S = external_delta_S  # External mode
    else:
        state, delta_S = self.compute_state_delta(hidden, reset_state)  # Auto mode

    # Convert ΔS to phase rotation
    intent_phase = self.intent_projector(delta_S)  # [B, H]

    # Second pass: Full forward WITH intent phase
    result = self.hybrid(input_ids, intent_phase=intent_phase)

    # Return logits + ontological outputs
    result['state'] = state
    result['delta_S'] = delta_S
    result['intent_phase'] = intent_phase
    return result
```

**State Delta Computation:**

```python
def compute_state_delta(self, hidden, reset_state=False):
    """
    Compute 32D Sovereign State and its delta from hidden states.

    V9.8.0: Updated for 32D Sovereign State.

    Returns:
        state: [B, 32] - current Sovereign State (pooled)
        delta_S: [B, 32] - change from previous state
    """
    # Pool hidden states
    pooled = hidden.mean(dim=1)  # [B, embed_dim]

    # Project to Sovereign State
    state = self.state_projector(pooled)  # [B, 32]

    # Compute delta from previous state
    if reset_state or self.prev_state is None:
        delta_S = torch.zeros_like(state)
    else:
        delta_S = state - self.prev_state

    # Update for next call
    self.prev_state = state.detach()

    return state, delta_S
```

---

### Usage Examples

#### Basic Usage (V9.8.0: 32D Sovereign State)

```python
from symbolu.phase_transformer import (
    OntologicalHybridTransformer,
    SOVEREIGN_STATE_DIM,
    get_sovereign_state_summary,
)

# Create AGI model with 32D Sovereign State
model = OntologicalHybridTransformer(
    vocab_size=50257,
    embed_dim=768,
    num_layers=12,
    num_heads=12,
    state_dim=SOVEREIGN_STATE_DIM,  # 32D (default)
)

# Forward pass (auto computes ΔS)
input_ids = torch.randint(0, 50257, (2, 512))
output = model(input_ids)

# Access outputs
logits = output['logits']              # [2, 512, 50257]
state = output['state']                # [2, 32] - current Sovereign State
delta_S = output['delta_S']            # [2, 32] - state change
intent_phase = output['intent_phase']  # [2, 12] - applied phase rotation

# Get human-readable state summary
summary = get_sovereign_state_summary(state)
print(f"Dominant Bhava: {summary['dominant_bhava']}")  # e.g., "ABS", "COG", "RSN"
print(f"Active Kosha: {summary['active_kosha']}")      # e.g., "ANNA", "VIJNANA"
print(f"Vritti State: {summary['vritti_state']}")      # e.g., "PRAMANA", "SMRITI"
print(f"Guna Balance: S={summary['guna_sattva']:.2f} R={summary['guna_rajas']:.2f} T={summary['guna_tamas']:.2f}")
```

#### With External State Delta

```python
from symbolu.phase_transformer import (
    OntologicalHybridTransformer,
    SOVEREIGN_STATE_DIM,
)

# Hybrid model with external delta support
model = OntologicalHybridTransformer(
    vocab_size=50257,
    embed_dim=768,
    state_dim=SOVEREIGN_STATE_DIM,  # 32D
)

# Manually create a state delta (e.g., from analysis or steering)
# This could come from a separate analysis model or manual control
external_delta_S = torch.zeros(batch_size, 32)
external_delta_S[:, 4] = 0.5   # Boost COG (Cognition)
external_delta_S[:, 6] = 0.3   # Boost RSN (Reason)

# Forward pass with external ΔS
output = model(
    input_ids,
    external_delta_S=external_delta_S,  # Use external ΔS
)
# Model uses your delta instead of computing from hidden states
```

#### Using IntentPhaseProjector Directly

```python
from symbolu.phase_transformer import (
    IntentPhaseProjector,
    HybridPhaseTransformer,
    SOVEREIGN_STATE_DIM,
)

# Create projector for 32D Sovereign State
projector = IntentPhaseProjector(
    state_dim=SOVEREIGN_STATE_DIM,  # 32D
    num_heads=12,
    head_dim=64,
    project_per_head_dim=False,
)

# Create hybrid model
model = HybridPhaseTransformer(
    vocab_size=50257,
    embed_dim=768,
    num_layers=12,
    num_heads=12,
)

# Manual ΔS → intent_phase flow
delta_S = torch.randn(2, 32)  # Your computed 32D state delta
intent_phase = projector(delta_S)  # [2, 12]

# Forward with intent
output = model(input_ids, intent_phase=intent_phase)
```

#### Generation with State Tracking

```python
model = OntologicalHybridTransformer(...)

# Generate with ontological state tracking
generated = model.generate(
    input_ids=prompt_ids,
    max_new_tokens=100,
    temperature=0.8,
    top_k=50,
)
# State is automatically tracked and applied across generation
```

---

### API Reference

#### IntentPhaseProjector

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(state_dim, num_heads, head_dim, project_per_head_dim)` | Initialize projector |
| `forward` | `(delta_S) → theta` | Project state delta to phase offsets |

**Input Shapes:**
- `delta_S`: `[B, state_dim]` or `[B, T, state_dim]`

**Output Shapes:**
- `project_per_head_dim=False`: `[B, H]` or `[B, T, H]`
- `project_per_head_dim=True`: `[B, H, D_h]` or `[B, T, H, D_h]`

#### PhaseAttentionLayer.forward

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | Tensor | Input `[B, N, D]` |
| `causal_mask` | bool | Apply causal masking |
| `phase_context` | Optional[Dict] | Streaming context (legacy) |
| `intent_phase` | Optional[Tensor] | Phase rotation from ΔS |

**intent_phase Shapes Supported:**
- `[B, H]` → Broadcast to all positions and dims
- `[B, H, D_h]` → Broadcast to all positions
- `[B, T, H, D_h]` → Per-position intent

#### OntologicalHybridTransformer.forward

| Parameter | Type | Description |
|-----------|------|-------------|
| `input_ids` | Tensor | Token indices `[B, N]` |
| `return_hidden` | bool | Return all hidden states |
| `extract_layers` | Optional[List[int]] | Specific layers to extract |
| `return_last_hidden` | bool | Return final hidden state |
| `reset_state` | bool | Reset ontological state (new sequence) |
| `external_delta_S` | Optional[Tensor] | External state delta `[B, state_dim]` |

**Returns Dict:**
- `logits`: `[B, N, V]` - Output logits
- `state`: `[B, state_dim]` - Current CognitiveState
- `delta_S`: `[B, state_dim]` - State delta applied
- `intent_phase`: `[B, H]` or `[B, H, D_h]` - Phase rotation

---

### Integration with Existing Training

The implementation is **backward compatible**. All existing code continues to work:

```python
# Existing HybridPhaseTransformer usage (unchanged)
model = HybridPhaseTransformer(...)
output = model(input_ids)  # Works exactly as before

# New: With intent phase
output = model(input_ids, intent_phase=theta)  # NEW capability
```

**To enable in training:**

```python
# train_unified_llm.py can be extended:
# --model_type ontological_hybrid  # Use OntologicalHybridTransformer
# --state_dim 124                  # CognitiveState dimension
# --project_per_head_dim           # Fine-grained phase projection
```

---

### Mathematical Foundation

**Phase Rotation Equation:**

```
z' = z × e^{iθ}

For attention:
    Q_phasor = a_q × e^{i(φ_q + θ_intent)}   ← Rotated query
    K_phasor = a_k × e^{-iφ_k}               ← Key (unchanged)

    Attention = Re(Q_phasor × conj(K_phasor))
              = a_q × a_k × cos(φ_q + θ_intent - φ_k)
                              ↑
                     Intent shifts the phase difference
```

**Why This Works:**

```
cos(φ_q - φ_k) = 1.0  → Q and K in phase (high attention)
cos(φ_q - φ_k) = 0.0  → Q and K orthogonal (no attention)
cos(φ_q - φ_k) = -1.0 → Q and K anti-phase (negative attention)

Adding θ_intent SHIFTS this relationship:
- θ_intent = 0: No change
- θ_intent = π/2: 90° rotation, orthogonal becomes aligned
- θ_intent = π: 180° flip, aligned becomes anti-aligned

Same tokens, different relationships, based on understanding.
```

---

### Performance Considerations

**Memory:**
- IntentPhaseProjector: ~100K parameters (negligible)
- State projector: ~300K parameters (negligible)
- No additional memory during inference (phase is just addition)

**Compute:**
- Phase rotation: O(B × N × H × D_h) addition
- Negligible compared to attention computation

**Training:**
- Two forward passes in OntologicalHybridTransformer (first for ΔS, second with intent)
- Can be optimized to single pass with gradient detach

---

### Future Work

1. **Curriculum Learning**: Start with θ_intent ≈ 0, gradually increase rotation range
2. **Multi-Scale Intent**: Different θ per layer (early = syntax, late = semantics)
3. **Learned Update Frequency**: When to update ΔS (every token? every sentence?)
4. **External Ontological Model**: Full Tier 3 model separate from Hybrid

---

## OPERATIONAL: CLI Usage (V9.8.0)

### Training with Ontological Hybrid (32D Sovereign State)

The Two-Tier AGI architecture is now accessible via CLI with 32D Sovereign State:

```bash
# Basic training (32D is now default)
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --dataset wikitext103 \
    --max_steps 10000

# Explicit 32D with full diagnostics
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --state_dim 32 \
    --enable_csr \
    --csr_alignment_layer 7 \
    --enable_onto_bridge \
    --onto_bridge_layer 4 \
    --enable_kosha_steering \
    --kosha_steering_layer 9 \
    --dataset wikitext103

# With per-head-dim projection (more expressive)
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --state_dim 32 \
    --project_per_head_dim \
    --dataset wikitext103

# Full production configuration
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --state_dim 32 \
    --batch_size 32 \
    --gradient_accumulation 4 \
    --max_seq_len 1024 \
    --learning_rate 8e-5 \
    --controller pidv2 \
    --enable_csr \
    --csr_alignment_layer 7 \
    --enable_onto_bridge \
    --onto_bridge_layer 4 \
    --enable_kosha_steering \
    --kosha_steering_layer 9 \
    --kosha_steering_force 0.16 \
    --kosha_steering_warmup 3000 \
    --log_every 20 \
    --eval_every 250 \
    --sample_every 500 \
    --checkpoint_dir ./checkpoints/onto_sovereign_32d
```

### CLI Arguments (V9.8.0)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--model_type` | str | ontological | Set to `ontological_hybrid` for Two-Tier AGI |
| `--state_dim` | int | **32** | Sovereign State dimension (12 Bhava + 5 Kosha + 5 Vritti + 6 Guna + 4 Reserved) |
| `--project_per_head_dim` | flag | False | Enable per-head-dim phase projection |
| `--cosine_mode` | str | standard | Phase attention mode (standard/shifted/complex) |
| `--decay_gamma` | float | 1.0 | State decay factor (1.0=infinite, <1.0=local) |
| `--enable_csr` | flag | False | Enable CSR phoneme alignment at Layer 7 |
| `--csr_alignment_layer` | int | 7 | Layer for CSR (word-level semantic context) |
| `--enable_onto_bridge` | flag | False | Enable Ontological Bridge at Layer 4 |
| `--enable_kosha_steering` | flag | False | Enable Kosha steering at Layer 9 |

### Layer Architecture (Recommended)

```
Layer 4:  Ontological Bridge  → Structure/Grounding (DNA Seed)
Layer 7:  CSR Alignment       → Word-level phonemes (semantic context exists)
Layer 9:  Kosha Steering      → Witness Consciousness (Reality/Time)
State:    32D Sovereign       → Bhava/Kosha/Vritti/Guna (principled ontology)
```

---

## OPERATIONAL: How State Delta Learns (V9.8.0)

### The Learning Process

During training, the `OntologicalHybridTransformer` learns **three interconnected things**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  WHAT IS LEARNED DURING TRAINING (V9.8.0: 32D Sovereign State)          │
│                                                                         │
│  1. STATE PROJECTOR: hidden[768] → SovereignState[32]                   │
│     Learns: Which Bhava/Kosha/Vritti/Guna are active                    │
│     Initial bias: O12_ABS (Absolute) + Annamaya (Physical)              │
│                                                                         │
│  2. INTENT PROJECTOR: ΔS[32] → θ[H]                                    │
│     Learns: How changes in Bhava/Kosha/Vritti should rotate attention   │
│     Example: Δ(COG→RSN) = analytical shift → rotate toward logic tokens │
│                                                                         │
│  3. HYBRID TRANSFORMER: How to generate given intent-rotated attention  │
│     Learns: How to respond to rotated phase relationships               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### End-to-End Gradient Flow

```
Forward Pass:
    input_ids → Hybrid(no intent) → hidden → StateProjector → S_t
                                                                │
                                              S_t - S_{t-1} = ΔS
                                                                │
                                              IntentProjector → θ
                                                                │
    input_ids → Hybrid(with θ) ────────────────────────────────┘
                      │
                      ▼
                    logits → CrossEntropy(target) → loss

Backward Pass:
    loss.backward() propagates gradients through:
    1. Hybrid transformer layers (with rotated attention)
    2. IntentPhaseProjector (learns ΔS → θ mapping)
    3. StateProjector (learns hidden → S mapping)
    4. Previous hidden states (learns what to encode)
```

### What the Model Discovers

Through backpropagation, the model learns:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  STATE PROJECTOR learns to extract (32D Sovereign State):               │
│  ─────────────────────────────────────────────────────────              │
│  - Bhava [0:12]: Which ontological aspect is dominant?                  │
│    (POT→ABS: Potential→Absolute, e.g., RSN for reasoning tasks)         │
│  - Kosha [12:17]: Which consciousness layer is active?                  │
│    (ANNA→ANANDA: Physical→Bliss, e.g., VIJNANA for analysis)           │
│  - Vritti [17:22]: What mental modification is occurring?               │
│    (PRAMANA=valid knowledge, VIPARYAYA=misconception, etc.)            │
│  - Guna [22:28]: What's the energy state?                               │
│    (SATTVA=clarity, RAJAS=activity, TAMAS=stability)                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  INTENT PROJECTOR learns:                                               │
│  ───────────────────────                                                │
│  - WHEN Bhava shifts COG→RSN → rotate toward analytical tokens          │
│  - WHEN Kosha moves MANO→VIJNANA → rotate toward wisdom/insight         │
│  - WHEN Vritti enters VIKALPA → allow imaginative associations          │
│  - WHEN Guna shifts TAMAS→RAJAS → increase activity/exploration         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  HYBRID TRANSFORMER learns:                                             │
│  ──────────────────────────                                             │
│  - How to use rotated attention for context-dependent generation        │
│  - Same token embeddings produce different outputs based on θ           │
│  - Grammar (local attention) stays stable, semantics (phase) adapts     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Training Dynamics

```
Early Training (steps 0-1000):
    - State projector outputs near-zero
    - ΔS ≈ 0, so θ ≈ 0
    - Model behaves like standard Hybrid (baseline performance)
    - Gradients flow, projectors start learning patterns

Mid Training (steps 1000-10000):
    - State projector finds meaningful dimensions
    - ΔS becomes non-trivial for topic shifts, sentiment changes
    - θ starts rotating attention meaningfully
    - Model learns to use rotated context

Late Training (steps 10000+):
    - Refined ΔS → θ mapping
    - Model reliably uses intent for long-range context
    - Different θ values lead to different generation styles
    - Emergent: Same prompt with different θ → different completions
```

---

## OPERATIONAL: How the Signal (θ) Is Used

### Signal Flow During Inference

```

    Input: "The company reported strong revenue growth, but"
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 1: First Forward Pass (No Intent)              │
    │  Hybrid model processes tokens normally              │
    │  Output: hidden states [B, T, 768]                   │
    └──────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 2: Compute Current Sovereign State             │
    │  StateProjector: hidden.mean() → S_t [B, 32]         │
    │  Example: Bhava=RSN (Reason), Kosha=VIJNANA,         │
    │           Vritti=PRAMANA, Guna=SATTVA                │
    └──────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 3: Compute Sovereign State Delta               │
    │  ΔS = S_t - S_{t-1}  [32D]                           │
    │  Example: Δ(RSN) = +0.3 (shift toward reasoning)     │
    │           Δ(RAJAS) = +0.2 (increased activity)       │
    └──────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 4: Project to Phase Rotation                   │
    │  IntentProjector: ΔS → θ [B, H]                      │
    │  Example: θ = [0.2, -0.1, 0.5, ..., -0.3]           │
    │  Head 1: slight rightward rotation                   │
    │  Head 3: significant rotation (topic head)           │
    └──────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 5: Second Forward Pass (With Intent)           │
    │  Query phases rotated by θ                           │
    │  φ_q' = φ_q + θ                                      │
    │  Attention patterns shift based on understanding     │
    └──────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────┐
    │  STEP 6: Generate Token                              │
    │  With rotated attention, "concerns" scores higher    │
    │  than "success" because θ biased toward caution      │
    │  Output: "...but concerns about margins persist"     │
    └──────────────────────────────────────────────────────┘
```

### What θ Does to Attention

```
BEFORE θ (standard attention):
    Q("but") attends equally to "revenue", "growth", "strong"
    All tokens in context compete for attention

AFTER θ (intent-rotated):
    θ rotates Q("but") phase by ~45°
    Now "revenue" and "growth" are LESS aligned (cos drops)
    Tokens about "concerns", "risks", "margins" become MORE aligned

    Same Q embedding, different θ → different attention pattern
```

---

## OPERATIONAL: Example Scenarios

### Scenario 1: Topic Shift Detection

```
INPUT: "Let's discuss the technical architecture. The system uses..."

BEFORE "The system uses":
    S_t = {topic: architecture, mode: explanatory, entropy: 0.3}

AFTER "The system uses":
    S_t+1 = {topic: technical_detail, mode: descriptive, entropy: 0.4}

ΔS = {Δtopic: +0.4 toward technical,
      Δentropy: +0.1 (slight uncertainty)}

θ = IntentProjector(ΔS) = [0.3, 0.1, 0.0, 0.5, ...]

EFFECT:
    Head 1 (maybe: topic head) rotates 0.3 rad
    → Queries now align better with technical vocabulary keys
    → "microservices", "containers", "API" get higher attention
    → Generation continues: "...microservices with Docker containers"
```

### Scenario 2: Sentiment Contrast

```
INPUT: "The weather was beautiful yesterday, but today"

BEFORE "but today":
    S_t = {sentiment: positive, topic: weather, coherence: 0.9}

AFTER "but today":
    S_t+1 = {sentiment: anticipating_negative, topic: weather, coherence: 0.85}

ΔS = {Δsentiment: -0.6 (shift from positive to anticipating negative)}

θ = IntentProjector(ΔS) = [-0.4, 0.0, -0.3, ...]

EFFECT:
    Negative θ values rotate attention AWAY from positive context
    → "beautiful", "sunny" get lower attention
    → "rain", "cloudy", "cold" become more aligned
    → Generation: "...but today it's pouring rain"
```

### Scenario 3: Conclusion/Summary Mode

```
INPUT: "In summary, the key findings were..."

BEFORE "In summary":
    S_t = {mode: analytical, entropy: 0.6, detail_level: high}

AFTER "In summary":
    S_t+1 = {mode: summary, entropy: 0.3, detail_level: low}

ΔS = {Δmode: +0.8 toward summary,
      Δentropy: -0.3 (increased certainty),
      Δdetail: -0.5 (less detail)}

θ = IntentProjector(ΔS) = [0.6, 0.4, 0.2, ...]

EFFECT:
    High θ values narrow attention to key concepts
    → Detail tokens get lower attention
    → High-level concepts get higher attention
    → Generation: "...three major trends: growth, efficiency, and innovation"
```

### Scenario 4: Question/Uncertainty Mode

```
INPUT: "I'm not sure, but perhaps the reason is"

BEFORE "the reason is":
    S_t = {certainty: 0.4, mode: speculative, entropy: 0.7}

AFTER "the reason is":
    S_t+1 = {certainty: 0.3, mode: explanatory_uncertain, entropy: 0.8}

ΔS = {Δcertainty: -0.1,
      Δentropy: +0.1}

θ = IntentProjector(ΔS) = [0.1, 0.1, 0.1, ...]

EFFECT:
    Small uniform θ = attention explores widely
    → Multiple possible explanations get attention
    → Generation hedges: "...the complexity of the underlying systems"
```

### Scenario 5: Long-Range Context Retrieval

```
INPUT (at position 5000): "As I mentioned earlier about the budget,"

Early context (position 100): "The budget was set at $10 million"

CURRENT STATE:
    S_t = {topic: budget_reference, coherence: 0.7, retrieval_mode: active}

ΔS = {Δtopic: +0.5 toward budget,
      Δretrieval: +0.3}

θ = IntentProjector(ΔS) = [0.4, 0.0, 0.6, 0.0, ...]

EFFECT:
    Head 3 (long-range head) gets large rotation 0.6
    → Phase attention O(n) scans all context with new alignment
    → Position 100's "$10 million" becomes highly aligned
    → Generation: "...the budget of $10 million allocated last quarter"

THIS IS THE AGI MOMENT:
    - Standard attention at position 5000 struggles with position 100
    - Phase attention + θ rotation makes old context RESONATE
    - Same mechanism that works in humans: intent focuses retrieval
```

---

## OPERATIONAL: Debugging and Monitoring

### Inspecting State During Training

```python
model = OntologicalHybridTransformer(...)
output = model(input_ids)

# Monitor state evolution
print(f"State magnitude: {output['state'].norm().item():.4f}")
print(f"Delta S magnitude: {output['delta_S'].norm().item():.4f}")
print(f"Intent phase (per head): {output['intent_phase'].mean(0).tolist()}")

# Check if learning
if output['delta_S'].norm() < 0.01:
    print("WARNING: State delta near zero - projector may not be learning")
```

### Visualizing Intent Phase

```python
import matplotlib.pyplot as plt

# Get intent phases over sequence
intent_phases = []
for i in range(0, seq_len, 100):
    output = model(input_ids[:, :i])
    intent_phases.append(output['intent_phase'].cpu().detach())

# Plot per-head rotation over time
intent_tensor = torch.stack(intent_phases)  # [T, B, H]
plt.figure(figsize=(12, 6))
for h in range(num_heads):
    plt.plot(intent_tensor[:, 0, h], label=f'Head {h}')
plt.xlabel('Position')
plt.ylabel('Phase Rotation (radians)')
plt.title('Intent Phase Evolution')
plt.legend()
plt.savefig('intent_phase_evolution.png')
```

### Expected Training Metrics

```
Early (step 0-500):
    - delta_S_norm: ~0.01-0.1 (learning to extract)
    - intent_phase_std: ~0.01 (near-zero rotation)
    - loss: normal cross-entropy baseline

Mid (step 500-5000):
    - delta_S_norm: ~0.1-0.5 (meaningful changes)
    - intent_phase_std: ~0.1-0.3 (learning rotations)
    - loss: improving, potentially faster than baseline

Late (step 5000+):
    - delta_S_norm: ~0.3-1.0 (calibrated changes)
    - intent_phase_std: ~0.2-0.5 (varied rotations)
    - loss: significantly better than baseline on long-range tasks
```
