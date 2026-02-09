# Unified SymbolU LLM Architecture: The Cognitive Substrate

## Executive Summary

SymbolU12 is a unified cognitive architecture that combines Phase Attention Transformer with Ontological State-Delta cognition. Unlike standard LLMs that predict tokens, SymbolU operates on **meaning structures** - predicting how understanding evolves rather than what word comes next.

**Key Innovation**: Internal cognition (State-Delta) and external expression (Phase Attention) work synergistically, creating a substrate for general intelligence.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Three-Tier Model Hierarchy](#2-three-tier-model-hierarchy)
3. [CognitiveState: The 124-Dimensional Meaning Vector](#3-cognitivestate-the-124-dimensional-meaning-vector)
4. [Phase Attention Transformer](#4-phase-attention-transformer)
5. [Version Integration (v2.6/v2.7/v2.8)](#5-version-integration)
6. [Chitta-Vritti: The Five Cognitive Modes](#6-chitta-vritti-the-five-cognitive-modes)
7. [Bidirectional Guna Flow](#7-bidirectional-guna-flow)
8. [Vritti-Modulated Attention](#8-vritti-modulated-attention)
9. [Holographic Retrieval (Hybrid RAG)](#9-holographic-retrieval)
10. [R[v,a] Coupling Matrix Analysis](#10-rva-coupling-matrix)
11. [Training Architecture](#11-training-architecture)
12. [Tuning Guidelines](#12-tuning-guidelines)
13. [Sparse R[v,a] Natural Affinities](#13-sparse-rva-natural-affinities)
14. [DHA Post-Validation Architecture](#14-dha-post-validation-architecture)
15. [Interpretable RLHF: Chitta Gradient](#15-interpretable-rlhf-chitta-gradient)
16. [Complete Bhava→Vritti→Steering→Validation Loop](#16-complete-loop)
17. [DHA Expression Controller](#17-dha-expression-controller)

---

## 1. Architecture Overview

### The Core Insight

```
Traditional LLM:  P(token_{t+1} | context)      → "What word next?"
SymbolU:          P(ΔS_{t+1} | S_t, context)    → "How should understanding change?"
```

### System Diagram (V11.0.0)

```
                         ┌─────────────────────────────────────┐
                         │        Input Tokens                 │
                         └──────────────┬──────────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────────────┐
                         │   OntologicalHybridTransformer      │
                         │     Phase Attention (O(n) memory)   │
                         │   + SovereignStateProjector (32D)   │
                         └──────────────┬──────────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────────────┐
                         │    compute_state_delta() → 3-tuple  │
                         │  ┌────────────────────────────────┐ │
                         │  │ state[32D]  delta_S[32D]       │ │
                         │  │ delta_bhava[12D]               │ │
                         │  └────────────────────────────────┘ │
                         └──────────────┬──────────────────────┘
                                        │
              ┌─────────────────────────┼──────────────────────────┐
              │                         │                          │
              ▼                         ▼                          ▼
    ┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
    │ PHASE PLANE      │   │ CONTROL PLANE        │   │ LEARNING PLANE       │
    │ Bhava[0:12]      │   │ Kosha[12:17]         │   │ Reserved[28:32]      │
    │                  │   │ Vritti[17:22]        │   │                      │
    │ ΔBhava → θ       │   │ Guna[22:28]          │   │ JEPA feedback        │
    │ (12D → phase     │   │                      │   │ (training-time only) │
    │  rotation)       │   │ (metacognitive       │   └──────────────────────┘
    └────────┬─────────┘   │  governance)         │
             │             └──────────┬───────────┘
             │                        │
             ▼                        ▼
    ┌──────────────────┐   ┌──────────────────────┐
    │IntentPhaseProj   │   │ Sovereign Bridge     │
    │ θ = Proj(ΔBhava) │   │ (sovereign_bridge.py)│
    │ z' = z × e^{iθ}  │   │                      │
    │ → attention mod   │   │ Vritti → Confidence  │
    └──────────────────┘   │ Kosha  → Budget      │
                           │ Guna   → Stability   │
                           └──────────┬───────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                                    ▼
          ┌──────────────────┐              ┌──────────────────────┐
          │ ConfidenceGate   │              │ SafetyContract       │
          │  → Escalation    │              │  → eligible=T/F      │
          │  → Budget        │              │  → preconditions     │
          │  → Execution     │              │  → fail-closed       │
          └──────────────────┘              └──────────────────────┘
```

---

## 2. Three-Tier Model Hierarchy

### Tier 1: Token-Centric (Standard LLM)
```
Loss: Cross-Entropy on vocabulary distribution
Memory: O(B·T·V) → 200GB at 1M context (V=50257)
Interpretability: Low (tokens are surface, not meaning)
```

### Tier 2: State-Delta (Hidden Space)
```
Loss: MSE on hidden state differences (ΔH = H_{t+1} - H_t)
Memory: O(B·T·d) → 3GB at 1M context (d=768)
Interpretability: Medium (hidden dynamics, but opaque)
Reduction: 65x from Tier 1
```

### Tier 3: Ontological State-Delta (V11.0.0 — 32D Sovereign State)
```
Loss: Structured loss on SovereignState deltas (SRKLoss: B1+U2+S8)
Memory: O(B·T·s) → 130MB at 1M context (s=32)
Interpretability: HIGH (Bhava aspects, Kosha sheaths, Vritti modes, Guna dynamics)
Reduction: 1500x from Tier 1

V11.0.0 Three-Plane Separation:
  Phase Plane:    Bhava[0:12]  → ΔBhava → IntentPhaseProjector → θ → attention
  Control Plane:  Kosha[12:17] + Vritti[17:22] + Guna[22:28] → Sovereign Bridge → Agentic
  Learning Plane: Reserved[28:32] → JEPA training-time feedback only
```

> **NOTE:** The 124D CognitiveState (phoneme[44]+topic[64]+ontology[12]+dynamics[4]) described
> in Section 3 below is the **legacy V2.x architecture**. It was replaced by the 32D Sovereign
> State in V9.8.0 and further refined in V11.0.0. Section 3 is retained for historical context
> only. See `docs/ONTOLOGICAL_STATE_DELTA_DESIGN.md` for the current architecture.

### Memory Comparison at Scale

| Context Length | Tier 1 (Tokens) | Tier 2 (Hidden) | Tier 3 (Ontological) |
|----------------|-----------------|-----------------|----------------------|
| 1K             | 200 MB          | 3 MB            | 0.5 MB               |
| 128K           | 25.6 GB         | 384 MB          | 64 MB                |
| 1M             | 200 GB          | 3 GB            | 600 MB               |
| 10M            | 2 TB            | 30 GB           | 6 GB                 |

---

## 3. CognitiveState: The 124-Dimensional Meaning Vector

### Structure

```python
CognitiveState [124 dimensions]:
├── phoneme_energy [44]     # IPA phoneme activation patterns
│   └── Cross-lingual sound structure
│
├── topic_embedding [64]    # L2-normalized topic vector
│   └── "What domain are we in?"
│   └── Enables semantic retrieval
│
├── ontology_probs [12]     # Softmax over 12 Bhava states
│   └── "What type of meaning?"
│   ├── FACTUAL (0)         # निर्णयात्मक
│   ├── ANALYTICAL (1)      # विश्लेषणात्मक
│   ├── EVALUATIVE (2)      # मूल्यांकनात्मक
│   ├── NARRATIVE (3)       # वर्णनात्मक
│   ├── ARGUMENTATIVE (4)   # तार्किक
│   ├── INSTRUCTIVE (5)     # निर्देशात्मक
│   ├── CERTAIN (6)         # निश्चयात्मक
│   ├── SPECULATIVE (7)     # अनुमानात्मक
│   ├── QUESTIONING (8)     # प्रश्नार्थक
│   ├── EMOTIVE (9)         # भावात्मक
│   ├── PERFORMATIVE (10)   # क्रियात्मक
│   └── METALINGUISTIC (11) # मेटाभाषिक
│
└── dynamics [4]            # Temporal evolution signals
    ├── coherence           # Cross-layer agreement [0,1]
    ├── entropy             # Ontological uncertainty [0,1]
    ├── confidence          # Prediction certainty [0,1]
    └── momentum            # State change rate [0,1]
```

### Extraction from Hidden States

```python
class StateProjector(nn.Module):
    def __init__(self, hidden_dim=768, state_dim=124):
        self.phoneme_proj = nn.Linear(hidden_dim, 44)
        self.topic_proj = nn.Linear(hidden_dim, 64)
        self.ontology_proj = nn.Linear(hidden_dim, 12)
        self.dynamics_proj = nn.Linear(hidden_dim, 4)

    def forward(self, hidden):
        phoneme = F.softmax(self.phoneme_proj(hidden), dim=-1)
        topic = F.normalize(self.topic_proj(hidden), p=2, dim=-1)
        ontology = F.softmax(self.ontology_proj(hidden), dim=-1)
        dynamics = torch.sigmoid(self.dynamics_proj(hidden))
        return torch.cat([phoneme, topic, ontology, dynamics], dim=-1)
```

---

## 4. Phase Attention Transformer

### Key Properties

- **O(n) Memory Scaling**: Linear, not quadratic
- **Phase Encoding**: Learned positional phases for long-range dependencies
- **Validated on LRA**: Pathfinder 100%, ListOps 84%

### Architecture

```
Input → Embedding → [Phase Attention Block] × L → LayerNorm → Output

Phase Attention Block:
├── Phase-Encoded Multi-Head Attention
│   └── phases[h] = learnable per-head frequencies
├── Vritti Modulation (optional)
│   └── Cognitive mode shapes attention patterns
├── Feed-Forward Network
└── Residual + LayerNorm
```

### Phase Attention Mechanism

```python
def phase_attention(Q, K, V, phases):
    # phases: learned frequencies for each head
    positions = torch.arange(T)
    phase_bias = torch.cos(phases * positions)

    # Standard attention with phase modulation
    scores = (Q @ K.T) / sqrt(d_k) + phase_bias
    weights = softmax(scores)
    return weights @ V
```

---

## 5. Version Integration

### v2.6: Guna Entropy Modulation (Stateless)

```python
GunaVector = [Sattva, Rajas, Tamas]  # Cognitive qualities

# From entropy:
def compute_guna(entropy_H, motion_M):
    S = exp(-entropy_H / τ)           # Sattva: clarity
    R = motion_M                       # Rajas: activity
    T = 1 - S - R                      # Tamas: inertia
    return normalize([S, R, T])
```

### v2.7: State Evolution Layer (Bounded Temporal)

```python
# Temporal state evolution with bounded memory
θ_{t+1} = (1 - α) * θ_t + α * θ*_t

# Where:
# θ_t = current state embedding
# θ*_t = target from current input
# α = learning rate (0.3-0.5)

# Bounded window (default: 3 turns)
# Decay rate: 0.4 per turn
```

### v2.8: Chitta-Vritti (Five Cognitive Modes)

See Section 6 for detailed breakdown.

### Integration Flow

```
Input
  │
  ▼
Hidden States ──────────────────────────────────────┐
  │                                                 │
  ├──► StateProjector ──► CognitiveState [124]     │
  │                              │                  │
  │                              ▼                  │
  │                    Chitta-Vritti (v2.8)        │
  │                         │                       │
  │                         ▼                       │
  │                    Vritti [5]                   │
  │                         │                       │
  │    ┌────────────────────┼────────────────────┐  │
  │    │                    │                    │  │
  │    ▼                    ▼                    ▼  │
  │  Guna Mapper      Attention Mod        Score   │
  │  (v2.6)           (See Sec 8)          Penalty │
  │    │                    │                       │
  │    ▼                    │                       │
  │  Guna [3]               │                       │
  │    │                    │                       │
  │    ▼                    │                       │
  │  Attention Bias ◄───────┘                       │
  │    │                                            │
  └────┴────────────────────────────────────────────┘
       │
       ▼
  Modified Attention → Token Generation
```

---

## 6. Chitta-Vritti: The Five Cognitive Modes

### Definition

From Yoga Sutras (YS 1.6): "प्रमाणविपर्ययविकल्पनिद्रास्मृतयः"

| Mode | Sanskrit | Meaning | Trigger |
|------|----------|---------|---------|
| **Pramāṇa** | प्रमाण | Valid cognition | Low entropy, high coherence |
| **Viparyaya** | विपर्यय | Error/Opposition | Negative similarity to prior |
| **Vikalpa** | विकल्प | Branching/Fantasy | High variance across layers |
| **Smṛti** | स्मृति | Memory/Staleness | Low state change (stuck) |
| **Nidrā** | निद्रा | Absence/Sleep | Low confidence |

### Differentiable Computation

```python
class DifferentiableChittaVritti(nn.Module):
    def forward(self, phoneme, topic, ontology, dynamics, prev_state=None):
        # Extract signals
        entropy = dynamics[..., 1]
        coherence = self._compute_coherence(phoneme, topic, ontology)

        # Compute raw vritti scores
        pramana = (1 - entropy) * coherence
        viparyaya = self._compute_opposition(topic, prev_state)
        vikalpa = self._compute_branching(ontology)
        smrti = self._compute_staleness(dynamics, prev_state)
        nidra = 1 - dynamics[..., 2]  # 1 - confidence

        # Normalize to probability distribution
        vritti = F.softmax(torch.stack([
            pramana, viparyaya, vikalpa, smrti, nidra
        ], dim=-1), dim=-1)

        return vritti  # [B, T, 5]
```

### Score Penalties (Threshold-Based)

```python
CONFIG = {
    'penalty_viparyaya': 0.25,    # Opposition detected
    'penalty_vikalpa': 0.15,       # Branching detected
    'penalty_smrti': 0.15,         # Staleness detected
    'penalty_nidra': 0.20,         # Absence detected

    # Activation thresholds
    'viparyaya_activation': 0.1,
    'vikalpa_activation': 0.15,
    'smrti_activation': 0.2,
    'nidra_activation': 0.25,
}

def compute_score(vritti, config):
    score = 1.0
    if vritti['viparyaya'] > config['viparyaya_activation']:
        score -= config['penalty_viparyaya']
    if vritti['vikalpa'] > config['vikalpa_activation']:
        score -= config['penalty_vikalpa']
    # ... etc
    return max(0, score)
```

---

## 7. Bidirectional Guna Flow

### The Key Insight

Previous versions had only **bottom-up** flow (observation → Guna).
v2.8 adds **top-down** flow (Guna → attention bias).

```
           ┌─────────────────────────────────────────────┐
           │                                             │
           │  ┌─────────────────────────────────────┐   │
           │  │         TOP-DOWN CONTROL             │   │
           │  │  Guna → Attention Bias               │   │
           │  │                                      │   │
           │  │  Sattva high → Sharpen attention     │   │
           │  │  Rajas high → Broaden exploration    │   │
           │  │  Tamas high → Dampen (inertia)       │   │
           │  └──────────────────┬──────────────────┘   │
           │                     │                       │
           │                     ▼                       │
Ontology ──┼──► Guna Mapper ──► Guna [3] ──► Attn Bias   │
           │        ▲                                    │
           │        │                                    │
           │  ┌─────┴───────────────────────────────┐   │
           │  │         BOTTOM-UP OBSERVATION        │   │
           │  │  Ontology → Guna                     │   │
           │  │                                      │   │
           │  │  BHAVA_TO_GUNA mapping:              │   │
           │  │  FACTUAL → [0.8, 0.1, 0.1] (Sattva)  │   │
           │  │  NARRATIVE → [0.3, 0.5, 0.2] (Rajas) │   │
           │  │  SPECULATIVE → [0.2, 0.6, 0.2]       │   │
           │  └─────────────────────────────────────┘   │
           │                                             │
           └─────────────────────────────────────────────┘
```

### Implementation

```python
class BidirectionalGunaMapper(nn.Module):
    # Static mapping: Bhava state → Guna tendency
    BHAVA_TO_GUNA = torch.tensor([
        # [Sattva, Rajas, Tamas]
        [0.8, 0.1, 0.1],  # FACTUAL - clarity
        [0.6, 0.3, 0.1],  # ANALYTICAL - clarity + activity
        [0.5, 0.3, 0.2],  # EVALUATIVE - balanced
        [0.3, 0.5, 0.2],  # NARRATIVE - activity
        [0.4, 0.5, 0.1],  # ARGUMENTATIVE - activity
        [0.6, 0.3, 0.1],  # INSTRUCTIVE - clarity
        [0.7, 0.2, 0.1],  # CERTAIN - high clarity
        [0.2, 0.6, 0.2],  # SPECULATIVE - high activity
        [0.3, 0.5, 0.2],  # QUESTIONING - activity
        [0.2, 0.4, 0.4],  # EMOTIVE - mixed
        [0.3, 0.6, 0.1],  # PERFORMATIVE - activity
        [0.5, 0.4, 0.1],  # METALINGUISTIC - balanced
    ])

    def forward(self, ontology_probs, num_heads):
        # Bottom-up: ontology → guna
        guna = ontology_probs @ self.BHAVA_TO_GUNA

        # Top-down: guna → attention bias
        # Sattva: sharpen (focus on key positions)
        # Rajas: broaden (explore more positions)
        # Tamas: dampen (reduce attention magnitude)

        S, R, T = guna[..., 0:1], guna[..., 1:2], guna[..., 2:3]

        # Compute per-head attention bias
        attention_scale = S - T  # Clarity vs inertia
        attention_spread = R     # Exploration

        return guna, attention_scale, attention_spread
```

---

## 8. Vritti-Modulated Attention

### The Key Insight

**BEFORE**: Chitta-Vritti was post-processing (after token generation)
**AFTER**: Chitta-Vritti modulates attention weights directly

### Modulation Rules

| Vritti Mode | Attention Effect | Reasoning |
|-------------|------------------|-----------|
| **Pramāṇa** | Sharpen (focus) | Valid cognition needs precision |
| **Viparyaya** | Suppress error | Reduce influence of contradictory |
| **Vikalpa** | Broaden | Branching needs wider context |
| **Smṛti** | Extend context | Memory retrieval needs history |
| **Nidrā** | Dampen all | Absence = low confidence |

### Implementation

```python
class VrittiModulatedAttention(nn.Module):
    def forward(self, attention_weights, vritti):
        """
        Modulate attention based on cognitive mode.

        Args:
            attention_weights: [B, H, T, T] raw attention
            vritti: [B, T, 5] cognitive mode distribution
        """
        B, H, T, _ = attention_weights.shape

        # Extract dominant mode influence
        pramana = vritti[..., 0]      # [B, T]
        viparyaya = vritti[..., 1]
        vikalpa = vritti[..., 2]
        smrti = vritti[..., 3]
        nidra = vritti[..., 4]

        # Compute modulation factors
        # Pramana: sharpen (increase attention peak)
        sharpen = 1 + pramana.unsqueeze(1).unsqueeze(-1) * 0.5

        # Vikalpa: broaden (flatten attention)
        broaden = 1 - vikalpa.unsqueeze(1).unsqueeze(-1) * 0.3

        # Smrti: extend context window
        # (implemented via position-weighted boost)

        # Nidra: dampen all
        dampen = 1 - nidra.unsqueeze(1).unsqueeze(-1) * 0.5

        # Apply modulation (before softmax renormalization)
        modulated = attention_weights * sharpen * broaden * dampen

        return F.softmax(modulated, dim=-1)
```

### Integration Point

```
Hidden States
     │
     ▼
Multi-Head Attention
     │
     ├──► Q, K, V projections
     │
     ▼
Attention Scores (Q @ K.T / sqrt(d))
     │
     ├──► VrittiModulatedAttention ◄── Vritti [5]
     │
     ▼
Modulated Attention Weights
     │
     ▼
Output (Weights @ V)
```

---

## 9. Holographic Retrieval (Hybrid RAG)

### The Problem

Two edge cases break traditional RAG:
1. **Proper Noun Problem**: "Jijñāsā" (specific term) needs exact match
2. **Conceptual Gap Problem**: "metabolism" should find "ATP synthesis"

### The Solution: Dynamic Alpha

Use **query entropy** to dynamically weight between Token and State-Delta retrieval.

```
Query Entropy (from CognitiveState.dynamics.entropy)
                │
                ▼
        ┌───────────────────┐
        │   LOW (<0.3)      │ → Token RAG 80%, State 20%
        │   Specific query  │   (exact matches matter)
        ├───────────────────┤
        │   MID (0.3-0.7)   │ → Interpolated weights
        │   Balanced        │
        ├───────────────────┤
        │   HIGH (>0.7)     │ → Token RAG 20%, State 80%
        │   Exploratory     │   (meaning matters)
        └───────────────────┘
```

### Architecture

```
                      Query
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
     Token RAG              State-Delta RAG
     (256D hash)            (124D cognitive)
            │                       │
            ▼                       ▼
     Lexical Match          Meaning Match
     - Keywords             - Topic similarity
     - Exact phrases        - Ontology pattern
                            - Entropy alignment
            │                       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   Dynamic Alpha       │
            │   Fusion              │
            │                       │
            │   α = f(entropy)      │
            │   score = α·token +   │
            │          (1-α)·state  │
            └───────────────────────┘
                        │
                        ▼
                CandidateEntry[]
```

### Configuration

```python
HybridRAGConfig(
    mode=FusionMode.DYNAMIC_ALPHA,

    # Entropy thresholds
    entropy_low_threshold=0.3,    # Below = specific
    entropy_high_threshold=0.7,   # Above = exploratory

    # Weight extremes
    token_weight_at_low_entropy=0.8,
    state_weight_at_low_entropy=0.2,
    token_weight_at_high_entropy=0.2,
    state_weight_at_high_entropy=0.8,
)
```

---

## 10. R[v,a] Coupling Matrix

### Definition

The R[v,a] matrix (5×12) captures how each Vritti mode relates to each Bhava state.

```
           Bhava States (12)
         0   1   2   3   4   5   6   7   8   9  10  11
       ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    0  │ ● │   │   │   │   │   │ ● │   │   │   │   │   │ Pramāṇa
    1  │   │   │   │   │ ● │   │   │   │   │ ● │   │   │ Viparyaya
V   2  │   │   │   │   │   │   │   │ ● │ ● │   │   │   │ Vikalpa
r   3  │ ● │   │   │ ● │   │   │   │   │   │   │   │   │ Smṛti
i   4  │   │   │   │   │   │   │   │   │   │   │   │ ● │ Nidrā
t       └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
t
i       ● = Strong coupling
```

### Interpretation

| Pattern | Meaning |
|---------|---------|
| **Diagonal-ish** | Aligned, coherent understanding |
| **Dense off-diagonal** | Complex reasoning, cross-mode synthesis |
| **Sparse** | Simple, single-mode cognition |

### Analysis Method

```python
def analyze_coupling(R_matrix):
    """Analyze R[v,a] coupling structure."""
    # Compute diagonality (how aligned is cognition?)
    diag_strength = torch.diagonal(R_matrix[:5, :5]).sum()
    total = R_matrix.sum()
    diagonality = diag_strength / total

    # Compute density (how distributed is coupling?)
    nonzero = (R_matrix > 0.1).sum()
    density = nonzero / R_matrix.numel()

    # Interpretation
    if diagonality > 0.6:
        return "ALIGNED: Coherent single-mode understanding"
    elif density > 0.5:
        return "SYNTHESIS: Complex multi-mode reasoning"
    else:
        return "SPARSE: Simple cognition"
```

---

## 11. Training Architecture

### Loss Function

```python
def compute_unified_loss(outputs, targets, config):
    """
    Combined loss for unified SymbolU12 training.

    L = λ₁·L_token + λ₂·L_state + λ₃·L_coherence
    """
    # Token prediction loss (standard LM)
    L_token = F.cross_entropy(outputs['logits'], targets['tokens'])

    # State-delta loss (meaning evolution)
    state_deltas_pred = outputs['cognitive_states'][:, 1:] - \
                        outputs['cognitive_states'][:, :-1]
    state_deltas_true = targets['state_deltas']
    L_state = F.mse_loss(state_deltas_pred, state_deltas_true)

    # Coherence loss (cross-layer agreement)
    L_coherence = compute_coherence_loss(outputs)

    # Weighted combination
    loss = (
        config.lambda_token * L_token +
        config.lambda_state * L_state +
        config.lambda_coherence * L_coherence
    )

    return loss, {
        'token_loss': L_token.item(),
        'state_loss': L_state.item(),
        'coherence_loss': L_coherence.item(),
    }
```

### Training Phases

```
Phase 1: Pre-training (Token-centric)
├── Focus: L_token with frozen state projector
├── Duration: Until PPL < 50
└── Purpose: Learn surface patterns

Phase 2: State-Delta Training
├── Focus: L_state with fine-tuned projector
├── Duration: Until state_loss < 0.1
└── Purpose: Learn meaning dynamics

Phase 3: Unified Training
├── Focus: All losses jointly
├── Weights: λ_token=0.5, λ_state=0.3, λ_coherence=0.2
└── Purpose: Synergistic integration

Phase 4: Vritti Calibration
├── Focus: Chitta-Vritti threshold tuning
├── Method: Validation-based threshold search
└── Purpose: Domain-specific adaptation
```

### Recommended Hyperparameters

```python
UnifiedSymbolU12Config(
    # Model architecture
    hidden_dim=768,
    num_layers=12,
    num_heads=12,
    state_dim=124,

    # Training
    learning_rate=3e-4,
    weight_decay=0.01,
    gradient_accumulation=2,
    max_seq_length=131072,

    # Loss weights
    lambda_token=0.5,
    lambda_state=0.3,
    lambda_coherence=0.2,

    # Vritti thresholds
    fast_path_entropy_threshold=0.1,
    viparyaya_activation_threshold=0.1,
    vikalpa_activation_threshold=0.15,
)
```

---

## 12. Tuning Guidelines

### Domain Adaptation

| Domain | Recommended Adjustments |
|--------|------------------------|
| **Scientific** | Lower vikalpa_threshold (allow branching), Higher pramana weight |
| **Creative** | Higher entropy thresholds, Lower coherence penalty |
| **Legal/Medical** | Stricter viparyaya detection, Lower fast-path threshold |
| **Conversational** | Higher smrti window, Faster decay rate |

### Consumer vs Enterprise Config

```python
# Consumer: More tolerant, faster
CONSUMER = {
    'fast_path_entropy_threshold': 0.15,
    'penalty_viparyaya': 0.20,
    'penalty_vikalpa': 0.10,
    'smrti_decay_rate': 0.5,
}

# Enterprise: Stricter, slower decay
ENTERPRISE = {
    'fast_path_entropy_threshold': 0.08,
    'penalty_viparyaya': 0.35,
    'penalty_vikalpa': 0.20,
    'smrti_decay_rate': 0.2,
}
```

### Debugging Cognitive Behavior

```python
def diagnose_cognitive_state(state, vritti):
    """Diagnose unusual cognitive patterns."""
    issues = []

    if vritti['viparyaya'] > 0.5:
        issues.append("HIGH OPPOSITION: Check for contradictory context")

    if vritti['vikalpa'] > 0.4 and vritti['pramana'] < 0.2:
        issues.append("EXCESSIVE BRANCHING: Consider constraining context")

    if vritti['smrti'] > 0.5:
        issues.append("STALENESS: Model may be stuck, reset state window")

    if vritti['nidra'] > 0.6:
        issues.append("LOW CONFIDENCE: Check input quality or context")

    entropy = state.dynamics[1]
    if entropy > 0.8:
        issues.append("HIGH ENTROPY: Consider more specific prompting")

    return issues
```

### Monitoring Metrics

| Metric | Healthy Range | Alert If |
|--------|---------------|----------|
| Pramāṇa dominant | >50% turns | <30% |
| Coherence | >0.85 | <0.7 |
| Entropy | 0.2-0.6 | >0.8 consistently |
| State Δ magnitude | 0.1-0.5 | <0.05 (stuck) or >1.0 (unstable) |
| R[v,a] diagonality | >0.4 | <0.2 (chaotic coupling) |

---

## 13. Sparse R[v,a] Natural Affinities

### The Key Insight

Not all Vrittis map to all Bhavas. The relationship is **sparse by nature** - derived from philosophical foundations, not learned heuristically.

```
"Pramāṇa cannot naturally arise from EMOTIVE context;
 Nidrā cannot be the cognitive mode for FACTUAL output."
```

### Sparse Affinity Matrix

The R[v,a] coupling is not dense (5×12 = 60 connections). Only ~25 natural affinities exist:

```
                        Bhava States (12)
                 FACT ANAL EVAL NARR ARGU INST CERT SPEC QUES EMOT PERF META
              ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
   Pramāṇa    │ ●● │  ● │    │    │    │ ●● │ ●● │    │    │    │    │    │
   Viparyaya  │    │    │    │    │ ●● │    │    │  ● │    │    │    │    │
   Vikalpa    │    │    │    │  ● │    │    │    │ ●● │ ●● │    │    │    │
   Smṛti      │  ● │    │  ● │ ●● │    │    │    │    │    │    │    │    │
   Nidrā      │    │    │    │    │    │    │    │    │    │ ●● │    │  ● │
              └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘

   ●● = Strong affinity (0.8+)     ● = Moderate affinity (0.5-0.7)
   Empty = Weak/No affinity (<0.3)
```

### Natural Groupings

| Vritti | Primary Bhavas | Reasoning |
|--------|---------------|-----------|
| **Pramāṇa** (Valid Knowledge) | FACTUAL, CERTAIN, INSTRUCTIVE, ANALYTICAL | Clear, authoritative, verifiable |
| **Viparyaya** (Error/Opposition) | ARGUMENTATIVE, SPECULATIVE | Challenging assumptions, counterpoints |
| **Vikalpa** (Branching/Fantasy) | SPECULATIVE, QUESTIONING, NARRATIVE | Exploring possibilities, hypotheticals |
| **Smṛti** (Memory) | NARRATIVE, FACTUAL, EVALUATIVE | Drawing on past knowledge, judgment |
| **Nidrā** (Absence/Sleep) | EMOTIVE, METALINGUISTIC | Disengaged cognition, meta-level |

### Implementation

```python
# In VrittiOntologyCoupling (unified_symbolu12.py)
semantic_priors = torch.tensor([
    # FACT ANAL EVAL NARR ARGU INST CERT SPEC QUES EMOT PERF META
    [0.9, 0.6, 0.2, 0.1, 0.1, 0.8, 0.9, 0.1, 0.1, 0.1, 0.3, 0.2],  # Pramāṇa
    [0.1, 0.1, 0.2, 0.1, 0.8, 0.1, 0.1, 0.5, 0.2, 0.2, 0.1, 0.1],  # Viparyaya
    [0.1, 0.2, 0.2, 0.5, 0.1, 0.1, 0.1, 0.8, 0.8, 0.2, 0.3, 0.2],  # Vikalpa
    [0.6, 0.2, 0.6, 0.8, 0.1, 0.3, 0.3, 0.1, 0.1, 0.3, 0.2, 0.1],  # Smṛti
    [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.8, 0.2, 0.5],  # Nidrā
])
```

### Why Sparse?

1. **Philosophical Coherence**: Yoga Sutras define Vrittis with specific cognitive domains
2. **Training Efficiency**: Fewer parameters to learn, faster convergence
3. **Interpretability**: Clear "this shouldn't happen" signals
4. **Error Detection**: Dense coupling in sparse regions indicates model confusion

---

## 14. DHA Post-Validation Architecture

### Pre-Steering vs Post-Validation

A critical distinction in the SymbolU architecture:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GENERATION PIPELINE                              │
│                                                                         │
│  ┌─────────────────┐                      ┌─────────────────┐          │
│  │  PRE-STEERING   │                      │ POST-VALIDATION │          │
│  │  (DURING gen)   │                      │  (AFTER gen)    │          │
│  │                 │                      │                 │          │
│  │ VrittiModulated │──► Generation ──────►│  DHA Validator  │          │
│  │   Attention     │                      │                 │          │
│  │                 │                      │                 │          │
│  │ BidirectionalGuna                      │ Chitta Gradient │          │
│  │   Mapper        │                      │   (Loss fn)     │          │
│  └─────────────────┘                      └─────────────────┘          │
│         ▲                                          │                    │
│         │                                          │                    │
│         │        ┌──────────────────────┐          │                    │
│         └────────│  Threshold Updates   │◄─────────┘                    │
│                  │  (Learning Loop)     │                               │
│                  └──────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Each Does

| Component | When | What | Adjusts |
|-----------|------|------|---------|
| **VrittiModulatedAttention** | DURING | Shapes attention patterns | How model "thinks" |
| **BidirectionalGunaMapper** | DURING | Converts Bhava→Guna→Bias | What model "focuses on" |
| **DHAValidator** | AFTER | Checks if steering worked | Thresholds for next time |
| **CognitiveLossFunction** | AFTER | Gradient from diagnosis | Model weights |

### DHA as Diagnostic Post-Validator

The DHA (Dynamic Heuristic Adjustment) doesn't steer - it **validates** that steering worked:

```python
class DHAValidator:
    """
    Post-generation diagnostic that:
    1. Checks if Vritti matched expectations
    2. Checks if output Bhava was appropriate
    3. Diagnoses specific failure modes
    4. Recommends threshold adjustments
    """

    def diagnose(self, input_bhava, actual_vritti, output_bhava, human_rating):
        # What Vritti SHOULD have been based on input Bhava
        expected_vritti = input_bhava @ BHAVA_TO_IDEAL_VRITTI

        # Compare actual vs expected
        vritti_distance = cosine_distance(actual_vritti, expected_vritti)

        # Check if output Bhava is a healthy transition
        bhava_aligned = output_bhava in HEALTHY_TRANSITIONS[input_bhava]

        # Diagnose failure type
        return CognitiveDiagnosis(...)
```

### Diagnostic Types

| Diagnosis | Meaning | Recommendation |
|-----------|---------|----------------|
| **VALIDATED** | Everything worked | None needed |
| **OVER_HEDGED** | Viparyaya when Pramāṇa expected | Decrease viparyaya_threshold |
| **OVER_CONFIDENT** | Pramāṇa when Viparyaya expected | Increase viparyaya_threshold |
| **STUCK** | Smṛti too high, not progressing | Decrease smrti_decay_rate |
| **DISENGAGED** | Nidrā high inappropriately | Check input quality |
| **TRANSITION_ERROR** | Unhealthy Bhava transition | Review transition logic |

### The Learning Loop

```
1. Human provides rating (0-1)
2. DHAValidator diagnoses what went wrong
3. CognitiveLossFunction computes gradient
4. Model weights update
5. Thresholds adjust for domain
6. Next generation uses updated steering
```

---

## 15. Interpretable RLHF: Chitta Gradient

### Traditional RLHF vs Chitta Gradient

| Aspect | OpenAI RLHF | SymbolU Chitta Gradient |
|--------|-------------|-------------------------|
| **Reward Model** | Black-box neural network | Explicit Bhava/Vritti distances |
| **Gradient Source** | Opaque reward → policy gradient | Dist(actual, ideal) → interpretable gradient |
| **Debugging** | "Reward was low" | "Viparyaya when Pramāṇa expected" |
| **Human Feedback** | Preference pairs | Rating + cognitive diagnosis |
| **What Improves** | Vague "alignment" | Specific R[v,a] entries, thresholds |

### The Chitta Gradient Formula

```
L_cognitive = α·Dist(Vritti_actual, Vritti_ideal)
            + β·Dist(Bhava_out, Bhava_target)
            + γ·TransitionPenalty

Where:
- α = 0.4 (Vritti alignment weight)
- β = 0.4 (Bhava alignment weight)
- γ = 0.2 (Transition quality weight)
```

### Visual: Gradient Flow

```
Human Rating: 0.3 (bad)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                   DHAValidator                             │
│                                                            │
│  Input Bhava: QUESTIONING ────────────────────────────┐   │
│                                                        │   │
│  Expected Vritti: Vikalpa (0.8)                       │   │
│  Actual Vritti:   Pramāṇa (0.7)  ←── MISMATCH         │   │
│                                                        │   │
│  Expected Output: FACTUAL/ANALYTICAL                  │   │
│  Actual Output:   CERTAIN         ←── OK              │   │
│                                                        │   │
│  Diagnosis: OVER_CONFIDENT                            │   │
│  → "Pramāṇa=0.7 when Vikalpa expected"               │   │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                CognitiveLossFunction                       │
│                                                            │
│  vritti_loss = KL(actual, expected) = 0.85                │
│  bhava_loss  = 0.0 (transition was OK)                    │
│  transition_loss = 0.0                                    │
│                                                            │
│  total_loss = 0.4*0.85 + 0.4*0.0 + 0.2*0.0               │
│             = 0.34                                         │
│                                                            │
│  Scale by rating: 0.34 * (2.0 - 0.3) = 0.578             │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                   Gradient Updates                         │
│                                                            │
│  1. R[v,a] entry for QUESTIONING→Vikalpa increases       │
│  2. VrittiModulatedAttention learns to broaden more      │
│  3. vikalpa_activation_threshold decreases                │
└───────────────────────────────────────────────────────────┘
```

### Healthy Bhava Transitions

Not all Bhava→Bhava transitions make sense. The model learns:

```python
HEALTHY_TRANSITIONS = {
    8: [0, 1, 5, 6],   # QUESTIONING → FACTUAL, ANALYTICAL, INSTRUCTIVE, CERTAIN
    7: [0, 1, 6, 7],   # SPECULATIVE → FACTUAL/CERTAIN or stay speculative
    0: [0, 1, 2, 5],   # FACTUAL → deepen to ANALYTICAL or EVALUATIVE
    4: [0, 4, 1],      # ARGUMENTATIVE → FACTUAL (resolution) or continue
    3: [3, 0, 2],      # NARRATIVE → continue or conclude with FACTUAL
}
```

**Examples:**
- ✓ QUESTIONING → FACTUAL (question answered)
- ✓ SPECULATIVE → CERTAIN (hypothesis confirmed)
- ✗ FACTUAL → EMOTIVE (inappropriate escalation)
- ✗ QUESTIONING → EMOTIVE (evasion instead of answer)

### Implementation

```python
from symbolu.experimental import CognitiveLossFunction, DHAValidator

# During training
loss_fn = CognitiveLossFunction(alpha=0.4, beta=0.4, gamma=0.2)

loss_dict = loss_fn(
    vritti_actual=model_output['vritti'],
    bhava_input=input_state['ontology'],
    bhava_output=output_state['ontology'],
    human_rating=0.8,  # 0-1 scale
)

loss_dict['total_loss'].backward()

# For diagnosis
validator = DHAValidator()
diagnosis = validator.diagnose(
    input_bhava=input_state['ontology'],
    actual_vritti=model_output['vritti'],
    output_bhava=output_state['ontology'],
    human_rating=0.3,
)
print(diagnosis.message)  # "Over-confident: Pramāṇa=0.7 when Vikalpa expected"
print(diagnosis.recommended_adjustment)  # "Increase vikalpa_activation_threshold"
```

---

## 16. Complete Bhava→Vritti→Steering→Validation Loop {#16-complete-loop}

### The Full Cognitive Pipeline

This section ties together all components into a single coherent flow:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            COMPLETE COGNITIVE LOOP                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INPUT                                                                      │
│    │                                                                        │
│    ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. PERCEPTION: Extract CognitiveState                              │   │
│  │     Input Tokens → StateProjector → [Phoneme, Topic, Ontology, Dyn] │   │
│  │                                            │                         │   │
│  │                                            ▼                         │   │
│  │                                    Input Bhava [12]                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. VRITTI COMPUTATION: Which cognitive mode?                        │   │
│  │                                                                      │   │
│  │     Input Bhava → DifferentiableChittaVritti → Vritti [5]           │   │
│  │                                                                      │   │
│  │     Example: QUESTIONING → [0.1, 0.1, 0.8, 0.0, 0.0]                │   │
│  │                            (High Vikalpa = branching)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. PRE-STEERING: Shape generation before it happens                 │   │
│  │                                                                      │   │
│  │     ├─ BidirectionalGunaMapper: Bhava → Guna → Attention Bias       │   │
│  │     │                                                                │   │
│  │     └─ VrittiModulatedAttention: Vritti → Attention Patterns        │   │
│  │           • Pramāṇa high → Sharpen focus                            │   │
│  │           • Vikalpa high → Broaden exploration                      │   │
│  │           • Smṛti high → Extend context window                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. GENERATION: Produce output with steered attention                │   │
│  │                                                                      │   │
│  │     Phase Attention Transformer → Output Tokens                     │   │
│  │     (Using modulated attention patterns)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  5. OUTPUT PERCEPTION: Extract output CognitiveState                 │   │
│  │                                                                      │   │
│  │     Output Tokens → StateProjector → Output Bhava [12]              │   │
│  │     Also capture: Actual Vritti during generation [5]               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  6. POST-VALIDATION: Did steering work?                              │   │
│  │                                                                      │   │
│  │     DHAValidator.diagnose(                                          │   │
│  │         input_bhava,                                                │   │
│  │         actual_vritti,                                              │   │
│  │         output_bhava,                                               │   │
│  │         human_rating                                                │   │
│  │     )                                                               │   │
│  │                                                                      │   │
│  │     → CognitiveDiagnosis: VALIDATED / OVER_HEDGED / STUCK / etc.   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  7. LEARNING: Update from diagnosis                                  │   │
│  │                                                                      │   │
│  │     CognitiveLossFunction(                                          │   │
│  │         vritti_actual, bhava_input, bhava_output, human_rating      │   │
│  │     )                                                               │   │
│  │                                                                      │   │
│  │     Gradients update:                                               │   │
│  │     • R[v,a] coupling matrix entries                                │   │
│  │     • VrittiModulatedAttention parameters                           │   │
│  │     • Activation thresholds                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│                                    NEXT GENERATION                          │
│                                  (with updated model)                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Worked Example

**Scenario**: User asks "What causes rain?"

```
Step 1: PERCEPTION
  Input: "What causes rain?"
  Bhava: [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.8, 0.0, 0.0, 0.0]
         (QUESTIONING = 0.8)

Step 2: VRITTI COMPUTATION
  From sparse R[v,a]: QUESTIONING → Vikalpa
  Vritti: [0.1, 0.1, 0.7, 0.1, 0.0]
          (Vikalpa = 0.7 = exploring possibilities)

Step 3: PRE-STEERING
  • BidirectionalGunaMapper: QUESTIONING → Rajas-dominant
    → Attention explores wider context
  • VrittiModulatedAttention: Vikalpa high
    → Broadens attention, considers multiple explanations

Step 4: GENERATION
  Output: "Rain is caused by water vapor condensing in clouds..."
  (Factual explanation, properly steered)

Step 5: OUTPUT PERCEPTION
  Output Bhava: [0.7, 0.2, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                (FACTUAL = 0.7, ANALYTICAL = 0.2)
  Actual Vritti: [0.6, 0.0, 0.2, 0.1, 0.1]
                 (Pramāṇa = 0.6, shifted during answer)

Step 6: POST-VALIDATION
  Expected Vritti: Vikalpa (0.7)
  Actual Vritti: Pramāṇa (0.6) ← Shifted to deliver answer

  Check transition: QUESTIONING → FACTUAL
  Is [0] in HEALTHY_TRANSITIONS[8]? YES ✓

  Diagnosis: VALIDATED
  "Chain validated: QUESTIONING → Vikalpa/Pramāṇa → FACTUAL"

Step 7: LEARNING
  Human rating: 0.9 (good answer)
  Loss is low (0.12)
  Small gradient update, model reinforced
```

### Failure Example

**Scenario**: User asks "What causes rain?" but model responds emotionally

```
Step 5: OUTPUT PERCEPTION
  Output: "Rain makes me feel so peaceful and calm..."
  Output Bhava: [0.1, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.0]
                (EMOTIVE = 0.8)

Step 6: POST-VALIDATION
  Check transition: QUESTIONING → EMOTIVE
  Is [9] in HEALTHY_TRANSITIONS[8]? NO ✗

  Diagnosis: TRANSITION_ERROR
  "Unhealthy transition: QUESTIONING → EMOTIVE"
  "Expected: FACTUAL, ANALYTICAL, INSTRUCTIVE, or CERTAIN"

Step 7: LEARNING
  Human rating: 0.2 (didn't answer question)
  High transition penalty (1.0)
  Strong gradient update:
  • Decrease EMOTIVE weight when input is QUESTIONING
  • Increase FACTUAL weight for question-answering
```

### Summary: Why This Architecture?

1. **Interpretable**: Every component has explicit meaning
2. **Steerable**: Pre-steering shapes generation, post-validation confirms
3. **Learnable**: Chitta Gradient provides interpretable loss
4. **Diagnosable**: Clear failure modes with specific recommendations
5. **Grounded**: Philosophy-derived constraints (sparse R[v,a])

---

## 17. DHA Expression Controller {#17-dha-expression-controller}

### The Key Insight

The system needs two distinct modulation layers:
- **Understanding Modulation**: How the model processes input (Vritti on content)
- **Expression Modulation**: How the model delivers output (Vritti on user state)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNDERSTANDING vs EXPRESSION                          │
│                                                                         │
│   UNDERSTANDING (Content-Centric)         EXPRESSION (User-Centric)    │
│   ───────────────────────────────         ─────────────────────────    │
│                                                                         │
│   "What cognitive mode for                "How should I deliver        │
│    THIS CONTENT?"                          to THIS USER?"              │
│                                                                         │
│   Input → Chitta-Vritti → Vritti          User History → Accumulated  │
│           (on content)                     Vritti → Expression Style   │
│                                                                         │
│   Same framework, different targets                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### No New Framework - Reuse v2.7 + v2.8

Instead of duplicating Chitta-Vritti, we apply existing components differently:

| Component | Understanding Use | Expression Use |
|-----------|-------------------|----------------|
| **Chitta-Vritti (v2.8)** | Content → Vritti | Content → Vritti (same) |
| **State Evolution (v2.7)** | State tracking | **User Vritti tracking** |
| **Guna Mapper** | Attention bias | **Expression style** |

### User State Tracking

Apply v2.7 temporal evolution to track USER Vritti across turns:

```python
# v2.7 State Evolution applied to User Vritti
user_vritti_{t+1} = (1 - α) · user_vritti_t + α · content_vritti_t

# Example: 3-turn conversation
Turn 1: Content Vritti = [0.1, 0.6, 0.2, 0.1, 0.0]  # User skeptical (Viparyaya)
        User Vritti    = [0.1, 0.6, 0.2, 0.1, 0.0]  # First turn, same as content

Turn 2: Content Vritti = [0.2, 0.5, 0.2, 0.1, 0.0]  # Still skeptical
        User Vritti    = [0.14, 0.56, 0.2, 0.1, 0.0] # Accumulated (α=0.4)

Turn 3: Content Vritti = [0.7, 0.1, 0.1, 0.1, 0.0]  # User becoming receptive
        User Vritti    = [0.36, 0.38, 0.16, 0.1, 0.0] # History still shows caution
```

### Expression Modulation

The DHA Expression Modulator uses accumulated User Vritti to adjust delivery:

```
User Vritti Analysis:
├── High Viparyaya (resistance) → Dampen delta, gentle delivery
├── High Vikalpa (confusion) → Smooth transitions, step-by-step
├── High Pramāṇa (readiness) → Direct delivery, full information
└── High Nidrā (disengagement) → Reserved, re-engage first
```

### Google's Three Axes

| Axis | User Signal | Modulation |
|------|-------------|------------|
| **Ego State** | Resistance level | Vocabulary & Authority (Parent/Adult/Child) |
| **Information Density** | Confusion level | Dilute with metaphors vs raw data |
| **Pacing** | Readiness level | Bodha (conclusion) vs Anumāna (step-by-step) |

### Implementation

```python
from symbolu.experimental import DHAExpressionController

# Create controller (uses v2.7 decay rate)
controller = DHAExpressionController(decay_rate=0.4)

# Each turn: update and modulate
for turn in conversation:
    # Get content Vritti from current input (v2.8)
    content_vritti = chitta_vritti(input_bhava)

    # Get raw understanding
    state_delta = model.understand(input)

    # Modulate for user-appropriate expression
    result = controller(state_delta, content_vritti)

    # Use modulated delta for generation
    output = model.generate(result['communication_delta'])

    # Access delivery guidance
    print(result['style'])              # SATTVIC / RAJASIC / TAMASIC
    print(result['delivery_guidance'])  # Human-readable guidance
```

### Expression Styles

| Style | Trigger | Delivery |
|-------|---------|----------|
| **SATTVIC** | High resistance OR confusion | Gentle, nurturing, non-confrontational |
| **RAJASIC** | High readiness, low resistance | Direct, confident, expert-level |
| **TAMASIC** | Low engagement | Reserved, minimal, re-engagement focus |

### Complete Flow with Expression

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  UNDERSTANDING + EXPRESSION PIPELINE                    │
│                                                                         │
│  Input                                                                  │
│    │                                                                    │
│    ├──► Content Bhava → Chitta-Vritti → Content Vritti                 │
│    │                                          │                         │
│    │                                          ├──► Pre-Steering         │
│    │                                          │    (VrittiModulated     │
│    │                                          │     Attention)          │
│    │                                          │                         │
│    │                                          └──► UserStateTracker     │
│    │                                               (v2.7 evolution)     │
│    │                                                    │               │
│    ▼                                                    ▼               │
│  Generation ─────────────────────────────────► User Vritti              │
│    │                                                    │               │
│    ▼                                                    ▼               │
│  State-Delta (raw understanding)              DHAExpressionModulator   │
│    │                                                    │               │
│    └──────────────────────┬─────────────────────────────┘               │
│                           ▼                                             │
│                  Communication-Delta                                    │
│                  (user-optimized)                                       │
│                           │                                             │
│                           ▼                                             │
│                    Token Rendering                                      │
│                           │                                             │
│                           ▼                                             │
│                       Output                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Single-Turn vs Multi-Turn

| Scenario | User Vritti | Expression Modulation |
|----------|-------------|----------------------|
| **Single-turn** | = Content Vritti | Based on current input only |
| **Multi-turn, consistent** | ≈ Content Vritti | History reinforces current |
| **Multi-turn, evolving** | ≠ Content Vritti | History provides context |

**Key**: Multi-turn is where expression modulation adds value. The system remembers that the user was skeptical even if current input seems neutral.

---

## Appendix: File Reference

| Component | File Path |
|-----------|-----------|
| StateProjector | `symbolu/experimental/cognitive_state.py` |
| DifferentiableChittaVritti | `symbolu/experimental/unified_symbolu12.py` |
| BidirectionalGunaMapper | `symbolu/experimental/unified_symbolu12.py` |
| VrittiModulatedAttention | `symbolu/experimental/unified_symbolu12.py` |
| VrittiOntologyCoupling | `symbolu/experimental/unified_symbolu12.py` |
| HybridRAGEngine | `symbolu/experimental/hybrid_rag_integration.py` |
| StateTrajectoryIndex | `symbolu/experimental/state_retrieval.py` |
| ChittaVrittiResult | `symbolu/chitta_vritti/types.py` |
| GunaModulation | `symbolu/guna_modulation/` |
| **CognitiveLossFunction** | `symbolu/experimental/cognitive_loss.py` |
| **DHAValidator** | `symbolu/experimental/cognitive_loss.py` |
| **BHAVA_TO_IDEAL_VRITTI** | `symbolu/experimental/cognitive_loss.py` |
| **HEALTHY_TRANSITIONS** | `symbolu/experimental/cognitive_loss.py` |
| **UserStateTracker** | `symbolu/experimental/dha_expression.py` |
| **DHAExpressionModulator** | `symbolu/experimental/dha_expression.py` |
| **DHAExpressionController** | `symbolu/experimental/dha_expression.py` |
| Training Script | `scripts/train_symbolu12.py` |

---

## Version History

- **v2.6**: Guna Entropy Modulation (stateless)
- **v2.7**: State Evolution Layer (bounded temporal)
- **v2.8**: Chitta-Vritti integration (5 cognitive modes)
- **v2.9**: Bidirectional Guna + Vritti-Modulated Attention
- **v3.0**: Holographic Retrieval (Dynamic Alpha RAG)
- **v3.1**: Sparse R[v,a] Natural Affinities (philosophy-derived)
- **v3.2**: DHA Post-Validation Architecture
- **v3.3**: Interpretable RLHF (Chitta Gradient Loss Function)
- **v3.4**: DHA Expression Controller (user-aware delivery modulation)

---

*This document is intended for developers who need to understand the SymbolU12 architecture for analysis, tuning, and extension. For theoretical foundations, see `docs/STATE_DELTA_COGNITION_THEORY.md`.*
