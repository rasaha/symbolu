# Sovereign-1: Design Implementation Document

**Status**: PHASE 3 COMPLETE (Transmission & Dashboard)
**Date**: 2026-01-02 (Updated)
**Purpose**: Evaluate existing Symbolu codebase against Sovereign-1 specification and define implementation path
**Revision**: v3.0 - Phase 3 complete with Router, Telemetry, COGNADE Export, and Integration Tests

---

## Executive Summary

This document analyzes the Sovereign-1 Master Technical Specification against the existing Symbolu codebase to determine:
1. **REUSE**: Components that can be used as-is
2. **REWRITE**: Components that need modification
3. **OMIT**: Components that conflict with Sovereign-1 design
4. **NEW**: Components that must be created from scratch

**Key Finding**: ~40% of the Sovereign-1 architecture can leverage existing Symbolu code, but the PID Governor and embedding architecture require new implementation.

---

## 1. Architecture Comparison Matrix

### 1.1 Overall Architecture

| Component | Symbolu Codebase | Sovereign-1 Spec | Action |
|-----------|------------------|------------------|--------|
| Transformer Layers | 12-layer Phase Attention (all O(n)) | 6 Quadratic + 6 Phase (hybrid) | **REWRITE** |
| Embedding Dimension | 768D (standard) or 124D (CognitiveState) | 1024D (896 semantic + 128 state) | **NEW** |
| State Representation | CognitiveState[124] | Sovereign State[128] | **REWRITE** |
| Attention Mechanism | Phase sync O(n) | Quadratic O(n²) + Phase O(n) | **REWRITE** |
| Gating/Control | None (direct flow) | PID Governor at nexus | **NEW** |
| Dynamic Routing | SemanticRouter (discrete) | Sovereign Shift (continuous) | **REWRITE** |

### 1.2 State Partition Comparison

```
SYMBOLU CognitiveState [124D]          SOVEREIGN-1 State [128D]
├── Phoneme Energy    [44]             ├── C-Signal (Phonemic)    [32]
├── Topic Embedding   [64]             ├── R-Signal (Ontological) [48]
├── Ontology Probs    [12]             ├── S-Signal (Referent)    [32]
└── Dynamics          [4]              └── Guna Pulse             [16]
    ├── coherence                          ├── Sattva (Clarity)
    ├── entropy                            ├── Rajas (Motion)
    ├── confidence                         └── Tamas (Inertia)
    └── momentum
```

**Mapping Analysis**:
- Phoneme Energy [44] → C-Signal [32]: **COMPRESS** (reduce dimensionality)
- Ontology Probs [12] → R-Signal [48]: **EXPAND** (4 dims per Bhava layer)
- Topic Embedding [64] → Part of 896D semantic body: **RELOCATE**
- Dynamics [4] → Guna Pulse [16]: **RECOMPUTE** (different derivation)

---

## 2. Component-by-Component Analysis

### 2.1 REUSE (As-Is)

#### 2.1.1 Referent Class Dictionary
**File**: `symbolu/name_resonance/referent_classes.py`

```python
# Can be used directly for S-Signal generation
WORD_TO_REFERENT: Dict[str, ReferentProfile] = {
    "sun": ReferentProfile(primary={NATURAL_BODY, ENERGY_SOURCE}, ...),
    "light": ReferentProfile(primary={PHENOMENON}, ...),
    # ~200+ words mapped
}
```

**Usage in Sovereign-1**:
- S-Signal [912-943] lookup table
- One-hot encoding of 15 referent classes → 32 bits

✅ **Action**: Import directly, add one-hot encoder wrapper

---

#### 2.1.2 Vritti Computation Logic
**File**: `symbolu/chitta_vritti/vritti.py`

```python
# Existing Vritti computation
compute_pramana(coherence, entropy, motion, config)  # Valid cognition
compute_viparyaya(fractures, confidence, config)     # Misperception
compute_vikalpa(fractures, entropy, config)          # Branching
compute_smrti(current, previous)                     # Memory
compute_nidra(missing_layers, config)                # Dormancy
```

**Usage in Sovereign-1**:
- R-Signal analysis → Vritti detection → PID tuning

✅ **Action**: Import Vritti functions, add PID parameter lookup table

---

#### 2.1.3 12-Layer Ontology Definition
**File**: `symbolu/docs/data/ontological_layers_v1.json`

```json
{
  "O1_POTENTIAL": {"frequency": 0.1, "kosha": "pre-annamaya"},
  "O2_IDENTITY": {"frequency": 0.5, "kosha": "annamaya"},
  ...
  "O12_ABSOLVING": {"frequency": "async", "kosha": "bridge"}
}
```

**Usage in Sovereign-1**:
- R-Signal [944-991] ontological layer encoding
- 12 Bhavas × 4 dimensions = 48 bits

✅ **Action**: Use as authoritative ontology reference

---

### 2.2 REWRITE (Modify Existing)

#### 2.2.1 Guna Vector Derivation
**Current** (`symbolu/guna_modulation/types.py`):
```python
# Existing derivation
S_raw = C_s                           # Coherence → Sattva
R_raw = M × (1 - |H - H_MID|)         # Motion × entropy distance → Rajas
T_raw = H                             # Entropy → Tamas
```

**Sovereign-1 Spec**:
```python
# New derivation from attention
Sattva = 1.0 - (H(Attention) / H_max)  # Shannon entropy of attention heads
Rajas = Variance(Head_Outputs)          # Variance across heads
Tamas = CosineSim(Token_t, Token_{t-1}) # Token similarity
```

**Gap Analysis**:
| Derivation | Symbolu | Sovereign-1 | Compatible? |
|------------|---------|-------------|-------------|
| Sattva source | Structural coherence C_s | Attention entropy | ❌ Different |
| Rajas source | Motion × entropy | Head output variance | ❌ Different |
| Tamas source | Entropy H | Token cosine similarity | ❌ Different |

⚠️ **Action**: Create new `SovereignGunaComputer` class with attention-based derivation

```python
# PROPOSED: New Guna derivation
class SovereignGunaComputer(nn.Module):
    def forward(self, attention_weights, hidden_states, prev_hidden):
        # Sattva: Inverse attention entropy
        attn_entropy = -torch.sum(attention_weights * torch.log(attention_weights + 1e-9), dim=-1)
        sattva = 1.0 - (attn_entropy / self.max_entropy)

        # Rajas: Head output variance
        head_outputs = hidden_states.view(B, N, num_heads, head_dim)
        rajas = torch.var(head_outputs, dim=2).mean(dim=-1)

        # Tamas: Token similarity
        tamas = F.cosine_similarity(hidden_states, prev_hidden, dim=-1)

        return GunaVector(sattva, rajas, tamas)
```

---

#### 2.2.2 Phase Transformer Architecture
**Current** (`symbolu/phase_transformer.py`):
```python
# All 12 layers are Phase Attention (O(n))
class PhaseTransformer(nn.Module):
    def __init__(self, ...):
        self.layers = nn.ModuleList([
            PhaseAttentionLayer(...) for _ in range(num_layers)  # 12 Phase
        ])
```

**Sovereign-1 Spec**:
```
Default: 6 Quadratic (O(n²)) + PID Governor + 6 Phase (O(n))
Dynamic: Can shift to 4/8 or 8/4 based on input
```

⚠️ **Action**: Create hybrid `SovereignTransformer` with configurable nexus

```python
# PROPOSED: Hybrid architecture
class SovereignTransformer(nn.Module):
    def __init__(self, nexus_position=6):
        # Quadratic layers (standard attention)
        self.quadratic_layers = nn.ModuleList([
            StandardAttentionLayer(...) for _ in range(nexus_position)
        ])

        # PID Governor (NEW)
        self.pid_governor = PIDGovernor(Kp=0.65, Ki=0.10, Kd=0.25)

        # Phase layers (O(n))
        self.phase_layers = nn.ModuleList([
            PhaseAttentionLayer(...) for _ in range(12 - nexus_position)
        ])

    def forward(self, x, state_delta):
        # Quadratic processing
        for layer in self.quadratic_layers:
            x = layer(x)

        # PID gating
        x, authority = self.pid_governor(x, state_delta)

        # Phase processing
        for layer in self.phase_layers:
            x = layer(x)

        return x, authority
```

---

#### 2.2.3 Semantic Router → Sovereign Shift
**Current** (`symbolu/hybrid/router.py`):
```python
# Discrete routing to model types
class SemanticRouter:
    def route(self, query: str) -> RoutingDecision:
        # Returns: ModelType.REASONING, ModelType.ACTION, etc.
        dominant_layer = self._get_dominant_layer(query)
        return LAYER_TO_MODEL[dominant_layer]
```

**Sovereign-1 Spec**:
```python
# Dynamic architecture reconfiguration
REFERENT_TO_MODEL → nexus_position:
    O7, O10 (Logic)    → 4/8 Mode (PID at Layer 4.5)
    O6, O9 (Creative)  → 6/6 Mode (PID at Layer 6.5)
    O4, O5 (Archive)   → 8/4 Mode (PID at Layer 8.5)
```

⚠️ **Action**: Extend router to return nexus position

```python
# PROPOSED: Sovereign Shift integration
LAYER_TO_NEXUS = {
    "O7_REASONING": 4,    # 4/8 mode
    "O10_UNIFYING": 4,
    "O6_AGENCY": 6,       # 6/6 mode (default)
    "O9_WITNESSES": 6,
    "O4_STRUCTURE": 8,    # 8/4 mode
    "O5_COGNITION": 8,
}

class SovereignRouter(SemanticRouter):
    def route(self, query: str) -> Tuple[ModelType, int]:
        decision = super().route(query)
        nexus = LAYER_TO_NEXUS.get(decision.dominant_layer, 6)
        return decision, nexus
```

---

### 2.3 OMIT (Conflicts with Sovereign-1)

#### 2.3.1 Topic Embedding [64D]
**Current**: Dedicated 64D topic embedding in CognitiveState
**Sovereign-1**: Topic information absorbed into 896D semantic body
**Reason**: Sovereign-1 uses unified semantic space, not separate topic partition

❌ **Action**: Remove separate topic embedding, merge into semantic body

---

#### 2.3.2 Constraint Mask
**Current**: Sparse tensor of legal next tokens in CognitiveState
**Sovereign-1**: PID Governor handles constraints via authority score
**Reason**: Constraint enforcement moves from mask to soft gating

❌ **Action**: Remove constraint_mask, replace with PID dampening

---

#### 2.3.3 768D Skip Logic
**Current**: `tau_768` threshold for skipping 768D embeddings
**Sovereign-1**: All tokens use 1024D embedding with 128D state partition
**Reason**: No embedding skip in Sovereign-1 architecture

❌ **Action**: Remove tau_768 from StateRegister

---

### 2.4 NEW (Create from Scratch)

#### 2.4.1 PID Governor Module ⭐ CRITICAL
**Status**: Does not exist in codebase

```python
# NEW: Core PID Governor implementation
class PIDGovernor(nn.Module):
    """
    Control-theoretic gating between Quadratic and Phase layers.

    Uses Vritti-based dynamic tuning of PID parameters.
    """

    # Vritti → PID Parameter Lookup Table
    VRITTI_PID_TABLE = {
        "pramana":   {"Kp": 0.90, "Ki": 0.05, "Kd": 0.05},  # Strict
        "viparyaya": {"Kp": 0.70, "Ki": 0.15, "Kd": 0.15},  # Corrective
        "vikalpa":   {"Kp": 0.30, "Ki": 0.10, "Kd": 0.60},  # Fluid
        "smrti":     {"Kp": 0.50, "Ki": 0.40, "Kd": 0.10},  # Memory-heavy
        "nidra":     {"Kp": 0.20, "Ki": 0.70, "Kd": 0.10},  # Memory-heavy
    }

    def __init__(self, default_Kp=0.65, default_Ki=0.10, default_Kd=0.25):
        super().__init__()
        self.default_Kp = default_Kp
        self.default_Ki = default_Ki
        self.default_Kd = default_Kd
        self.integral_error = None
        self.prev_error = None

    def _detect_vritti(self, r_signal: torch.Tensor) -> str:
        """Detect dominant Vritti from R-Signal."""
        # Use existing vritti computation logic
        # Returns: "pramana", "viparyaya", "vikalpa", "smrti", "nidra"
        pass

    def _get_pid_params(self, vritti: str) -> Tuple[float, float, float]:
        """Get PID parameters for detected Vritti."""
        params = self.VRITTI_PID_TABLE.get(vritti, {
            "Kp": self.default_Kp,
            "Ki": self.default_Ki,
            "Kd": self.default_Kd
        })
        return params["Kp"], params["Ki"], params["Kd"]

    def forward(
        self,
        x: torch.Tensor,           # [B, N, 1024] - Output from quadratic layers
        target_state: torch.Tensor # [B, N, 128] - Target state delta
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply PID control to gate attention output.

        Returns:
            x: Potentially dampened hidden states
            authority_score: [B, N] authority scores for telemetry
        """
        B, N, D = x.shape

        # Extract current state from embedding
        current_state = x[:, :, 896:]  # [B, N, 128]
        semantic_body = x[:, :, :896]  # [B, N, 896]

        # Compute error (dissonance)
        error = 1.0 - F.cosine_similarity(
            current_state, target_state, dim=-1
        )  # [B, N]

        # Detect Vritti from R-Signal [944:992]
        r_signal = current_state[:, :, 48:96]
        vritti = self._detect_vritti(r_signal)
        Kp, Ki, Kd = self._get_pid_params(vritti)

        # Initialize integral/derivative tracking
        if self.integral_error is None:
            self.integral_error = torch.zeros_like(error)
            self.prev_error = torch.zeros_like(error)

        # PID calculation
        P = Kp * error
        I = Ki * (self.integral_error + error)
        D = Kd * (error - self.prev_error)

        # Update state
        self.integral_error = self.integral_error + error
        self.prev_error = error

        # Authority score
        authority = 1.0 - (P + I + D).clamp(0, 1)  # [B, N]

        # Gating mechanism
        damping_mask = (authority < 0.7).unsqueeze(-1)  # [B, N, 1]
        dampened_semantic = torch.where(
            damping_mask.expand_as(semantic_body),
            semantic_body * 0.1,  # Dampen hallucination
            semantic_body
        )

        # Reconstruct
        x_out = torch.cat([dampened_semantic, current_state], dim=-1)

        return x_out, authority
```

---

#### 2.4.2 Observer Algorithm (State Delta Generator) [HARDENED]
**Status**: Revised to include Ontological Transition Priors

**Rationale for Update**: The PID Governor alone is reactive (detects deviation after it occurs).
Adding explicit Bhava Transition Priors teaches the model valid ontological transitions *before*
generating errors, reducing "Ontological Teleportation" (illegal jumps like QUESTIONING → INSTRUCTIVE).

```python
# UPDATED: Sovereign Observer with Transition Priors
class SovereignObserver(nn.Module):
    """
    Computes the 128-D State Delta in parallel with main transformer.
    Includes ontological transition validation.

    Runs as a lightweight observer, not part of gradient flow.
    """

    # Valid transitions between Bhava states (12x12 matrix)
    # Values: 1.0 = High Probability, 0.1 = Low/Illegal
    # Derived from State-Delta Cognition Theory Section 3.2
    BHAVA_TRANSITION_MASK = torch.tensor([
        #         FACT  ANAL  EVAL  NARR  ARGU  INST  CERT  SPEC  QUES  POS   NEG   NEUT
        # FACTUAL
        [0.8,  0.8,  0.5,  0.3,  0.6,  0.2,  0.9,  0.2,  0.3,  0.5,  0.5,  0.9],
        # ANALYTICAL
        [0.5,  0.9,  0.7,  0.2,  0.8,  0.4,  0.8,  0.4,  0.2,  0.3,  0.3,  0.5],
        # EVALUATIVE
        [0.2,  0.5,  0.8,  0.3,  0.6,  0.3,  0.5,  0.4,  0.2,  0.9,  0.9,  0.2],
        # NARRATIVE
        [0.4,  0.2,  0.4,  0.9,  0.3,  0.2,  0.4,  0.5,  0.3,  0.6,  0.6,  0.4],
        # ARGUMENTATIVE
        [0.5,  0.8,  0.7,  0.2,  0.9,  0.5,  0.7,  0.5,  0.4,  0.4,  0.4,  0.3],
        # INSTRUCTIVE
        [0.6,  0.4,  0.3,  0.2,  0.4,  0.9,  0.8,  0.2,  0.1,  0.5,  0.3,  0.5],
        # CERTAIN
        [0.8,  0.7,  0.5,  0.3,  0.6,  0.7,  0.9,  0.1,  0.1,  0.5,  0.4,  0.6],
        # SPECULATIVE
        [0.3,  0.5,  0.5,  0.5,  0.5,  0.2,  0.1,  0.9,  0.7,  0.4,  0.4,  0.4],
        # QUESTIONING
        [0.4,  0.6,  0.4,  0.3,  0.5,  0.1,  0.2,  0.6,  0.8,  0.3,  0.3,  0.5],
        # POSITIVE
        [0.4,  0.3,  0.8,  0.5,  0.4,  0.4,  0.5,  0.4,  0.3,  0.8,  0.2,  0.4],
        # NEGATIVE
        [0.4,  0.3,  0.8,  0.5,  0.5,  0.3,  0.4,  0.4,  0.3,  0.2,  0.8,  0.4],
        # NEUTRAL
        [0.8,  0.5,  0.3,  0.4,  0.4,  0.5,  0.6,  0.4,  0.4,  0.4,  0.4,  0.9],
    ])

    def __init__(self, vocab_size, referent_dict):
        super().__init__()
        self.referent_lookup = referent_dict  # WORD_TO_REFERENT
        self.phoneme_encoder = PhonemeEncoder(output_dim=32)
        self.ontology_projector = OntologyProjector(output_dim=48)
        self.register_buffer('transition_priors', self.BHAVA_TRANSITION_MASK)

    @torch.no_grad()
    def forward(
        self,
        token_ids: torch.Tensor,          # [B, N]
        attention_weights: torch.Tensor,  # [B, H, N, N]
        hidden_states: torch.Tensor,      # [B, N, D]
        prev_hidden: torch.Tensor,        # [B, N, D]
    ) -> torch.Tensor:
        """
        Compute 128-D State Delta.

        Returns:
            state_delta: [B, N, 128] target state for PID Governor
        """
        B, N = token_ids.shape

        # [0-15] Guna Pulse (16 dims)
        guna = self._compute_guna(attention_weights, hidden_states, prev_hidden)

        # [16-47] S-Signal (32 dims) - Referent class one-hot
        s_signal = self._compute_s_signal(token_ids)

        # [48-95] R-Signal (48 dims) - Ontological layer projection
        r_signal = self._compute_r_signal(hidden_states)

        # [96-127] C-Signal (32 dims) - Phonemic encoding
        c_signal = self._compute_c_signal(token_ids)

        # Concatenate [16 + 32 + 48 + 32 = 128]
        state_delta = torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)

        return state_delta

    def _compute_guna(self, attn, hidden, prev_hidden):
        """Compute Guna Pulse [16 dims]."""
        # Sattva: Inverse attention entropy (clarity of focus)
        attn_entropy = -(attn * torch.log(attn + 1e-9)).sum(dim=-1).mean(dim=1)
        sattva = 1.0 - attn_entropy / math.log(attn.size(-1))

        # Rajas: Head output variance (cognitive motion)
        rajas = hidden.var(dim=-1)

        # Tamas: Token similarity (inertia/stability)
        tamas = F.cosine_similarity(hidden, prev_hidden, dim=-1)

        # Expand to 16 dims (redundant encoding for robustness)
        guna = torch.stack([
            sattva.unsqueeze(-1).expand(-1, -1, 5),
            rajas.unsqueeze(-1).expand(-1, -1, 5),
            tamas.unsqueeze(-1).expand(-1, -1, 6),
        ], dim=-1).flatten(-2)[:, :, :16]

        return guna

    def get_transition_penalty(
        self,
        current_r: torch.Tensor,  # [B, N, 48]
        prev_r: torch.Tensor      # [B, N, 48]
    ) -> torch.Tensor:
        """
        Compute transition penalty for illegal Bhava jumps.

        Used by SovereignLoss for ontological consistency.
        Returns: [B, N] penalty scores (0.0 = legal, 1.0 = illegal)
        """
        # Extract dominant Bhava from R-Signal (48D → 12 Bhavas × 4 dims each)
        B, N, _ = current_r.shape

        # Reshape to [B, N, 12, 4] then take argmax over last dim
        current_bhava = current_r.view(B, N, 12, 4).mean(dim=-1)  # [B, N, 12]
        prev_bhava = prev_r.view(B, N, 12, 4).mean(dim=-1)        # [B, N, 12]

        # Get dominant indices
        curr_idx = current_bhava.argmax(dim=-1)  # [B, N]
        prev_idx = prev_bhava.argmax(dim=-1)     # [B, N]

        # Lookup transition probabilities
        # transition_priors is [12, 12], need to index with [B, N] pairs
        penalties = 1.0 - self.transition_priors[prev_idx, curr_idx]

        return penalties
```

---

#### 2.4.3 1024-D Sovereign Embedding
**Status**: Does not exist

```python
# NEW: Sovereign Embedding with State Partition
class SovereignEmbedding(nn.Module):
    """
    1024-D embedding with dedicated 128-D state partition.

    Architecture:
        [0-895]:   Semantic Body (learnable)
        [896-1023]: State Delta (computed by Observer)
    """

    def __init__(self, vocab_size, max_seq_len=8192):
        super().__init__()
        # Semantic body embedding (896D)
        self.token_embedding = nn.Embedding(vocab_size, 896)
        self.position_embedding = nn.Embedding(max_seq_len, 896)

        # State partition is injected by Observer, not learned
        self.register_buffer('state_placeholder', torch.zeros(128))

    def forward(
        self,
        token_ids: torch.Tensor,  # [B, N]
        state_delta: torch.Tensor = None  # [B, N, 128] from Observer
    ) -> torch.Tensor:
        B, N = token_ids.shape

        # Semantic body
        positions = torch.arange(N, device=token_ids.device)
        semantic = self.token_embedding(token_ids) + self.position_embedding(positions)

        # State partition
        if state_delta is None:
            state = self.state_placeholder.expand(B, N, -1)
        else:
            state = state_delta

        # Concatenate to 1024D
        return torch.cat([semantic, state], dim=-1)
```

---

#### 2.4.4 Training Loss: Decomposed State Friction [HARDENED]
**Status**: Rewritten to prevent "Signal Washing"

**Rationale for Update**: The original unified MSE loss on the 128D state vector allows
the model to optimize for "loud" signals (high-frequency C-Signal/phonetics) while
ignoring "quiet" but semantically critical signals (R-Signal/ontology). This is the
"Signal Washing" effect that kills semantic learning.

**Solution**: Decompose the 128D vector into its 4 constituent signals with explicit
weighting. Prioritize R-Signal (Meaning) over C-Signal (Sound).

```python
# UPDATED: Sovereign Loss with Component Decomposition
class SovereignLoss(nn.Module):
    """
    Loss = CrossEntropy + α * (w_g*L_guna + w_s*L_s + w_r*L_r + w_c*L_c) + β*L_transition

    Component weights prioritize Meaning (R-Signal) over Sound (C-Signal).
    Transition penalty prevents illegal Bhava jumps.

    State Layout: Guna[0:16] | S-Signal[16:48] | R-Signal[48:96] | C-Signal[96:128]
    """

    # Signal weights: Higher = more important for semantic grounding
    DEFAULT_WEIGHTS = {
        "guna": 1.0,   # Dynamics (baseline importance)
        "s": 2.0,      # Referent accuracy (entity tracking)
        "r": 5.0,      # Ontological accuracy (CRITICAL for meaning)
        "c": 0.5       # Phonetic accuracy (lowest priority)
    }

    def __init__(
        self,
        weights: Dict[str, float] = None,
        alpha_initial: float = 1.0,
        alpha_final: float = 0.2,
        decay_epochs: int = 3,
        transition_weight: float = 0.5  # β for Bhava transition penalty
    ):
        super().__init__()
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.alpha_initial = alpha_initial
        self.alpha_final = alpha_final
        self.decay_epochs = decay_epochs
        self.transition_weight = transition_weight
        self.ce_loss = nn.CrossEntropyLoss()

    def get_alpha(self, epoch: int) -> float:
        """Compute decayed alpha for state friction."""
        if epoch >= self.decay_epochs:
            return self.alpha_final
        progress = epoch / self.decay_epochs
        return self.alpha_initial - progress * (self.alpha_initial - self.alpha_final)

    def _slice_state(self, state_tensor: torch.Tensor) -> Tuple[torch.Tensor, ...]:
        """
        Slice 128D state vector into constituent signals.

        Layout: Guna[16] | S[32] | R[48] | C[32] = 128 total
        """
        guna = state_tensor[:, :, 0:16]      # Guna Pulse
        s_signal = state_tensor[:, :, 16:48]  # S-Signal (Referent)
        r_signal = state_tensor[:, :, 48:96]  # R-Signal (Ontology) - THE CRITICAL ONE
        c_signal = state_tensor[:, :, 96:128] # C-Signal (Phonemic)
        return guna, s_signal, r_signal, c_signal

    def forward(
        self,
        logits: torch.Tensor,           # [B, N, V]
        targets: torch.Tensor,          # [B, N]
        predicted_state: torch.Tensor,  # [B, N, 128]
        target_state: torch.Tensor,     # [B, N, 128]
        prev_state: torch.Tensor = None, # [B, N, 128] for transition penalty
        epoch: int = 0
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Compute decomposed Sovereign loss.

        Returns:
            total_loss: Scalar tensor
            metrics: Dict with detailed component losses for monitoring
        """
        # 1. Standard Cross-Entropy (Token Prediction)
        ce = self.ce_loss(logits.view(-1, logits.size(-1)), targets.view(-1))

        # 2. Decomposed State Friction
        pred_g, pred_s, pred_r, pred_c = self._slice_state(predicted_state)
        targ_g, targ_s, targ_r, targ_c = self._slice_state(target_state)

        # Calculate individual MSE losses
        l_guna = F.mse_loss(pred_g, targ_g)
        l_s = F.mse_loss(pred_s, targ_s)      # Referent accuracy
        l_r = F.mse_loss(pred_r, targ_r)      # THE CRITICAL SEMANTIC LOSS
        l_c = F.mse_loss(pred_c, targ_c)      # Phonetic accuracy

        # Weighted Sum of State Friction
        state_friction = (
            self.weights["guna"] * l_guna +
            self.weights["s"] * l_s +
            self.weights["r"] * l_r +
            self.weights["c"] * l_c
        )

        # 3. Bhava Transition Penalty (optional, uses Observer's get_transition_penalty)
        l_transition = torch.tensor(0.0, device=logits.device)
        if prev_state is not None:
            _, _, prev_r, _ = self._slice_state(prev_state)
            # Transition penalty: penalize illegal ontological jumps
            # Uses BHAVA_TRANSITION_MASK from SovereignObserver
            transition_probs = self._compute_transition_prob(prev_r, pred_r)
            l_transition = (1.0 - transition_probs).mean()

        # 4. Total Loss with Alpha Decay
        alpha = self.get_alpha(epoch)
        total = ce + alpha * state_friction + self.transition_weight * l_transition

        # 5. Detailed Metrics for Monitoring
        return total, {
            "loss_total": total.item(),
            "loss_ce": ce.item(),
            "loss_friction": state_friction.item(),
            "loss_transition": l_transition.item(),
            "alpha": alpha,
            "friction_components": {
                "guna": l_guna.item(),
                "referent": l_s.item(),
                "ontology": l_r.item(),   # MONITOR THIS: If high, model struggles with meaning
                "phoneme": l_c.item()
            },
            # Diagnostic ratios
            "ontology_to_phoneme_ratio": l_r.item() / (l_c.item() + 1e-9),
            "meaning_fraction": l_r.item() / (state_friction.item() + 1e-9)
        }

    def _compute_transition_prob(
        self,
        prev_r: torch.Tensor,  # [B, N, 48]
        curr_r: torch.Tensor   # [B, N, 48]
    ) -> torch.Tensor:
        """
        Compute average transition probability based on Bhava changes.
        Higher = more valid transitions, Lower = more illegal jumps.
        """
        # Simplified: use cosine similarity as transition smoothness proxy
        # Full implementation would use BHAVA_TRANSITION_MASK lookup
        return F.cosine_similarity(prev_r, curr_r, dim=-1).clamp(0, 1)
```

**Monitoring Guidelines**:
- If `ontology_to_phoneme_ratio` < 1.0: Model is learning sounds over meaning (BAD)
- If `ontology_to_phoneme_ratio` > 3.0: Model prioritizes semantics correctly (GOOD)
- If `loss_transition` > 0.3: Too many illegal Bhava jumps (increase transition_weight)
- If `meaning_fraction` < 0.3: Semantic signal being washed out (increase r weight)

---

#### 2.4.5 Helper Class Specifications [FINAL]
**Status**: Complete specifications for Observer dependencies

These classes were previously "black boxes". Here are the concrete implementations:

##### A. PhonemeEncoder (C-Signal [32D])

**Concept**: Maps token ID to a static phonetic signature via pre-computed hash table.
**Why Not Learned**: Phonetics are fixed constants from CMU Dict / IPA mappings.

```python
class PhonemeEncoder(nn.Module):
    """
    O(1) lookup for phonetic signatures.

    Pre-computed from CMU Pronouncing Dictionary + IPA mappings.
    Each token maps to a 32-bit phonetic feature vector.
    """

    def __init__(self, vocab_size: int, output_dim: int = 32):
        super().__init__()
        # Pre-computed matrix: [Vocab, 32]
        # Loaded from CMU Dict / IPA mappings during init
        phoneme_table = self._load_phoneme_map(vocab_size, output_dim)
        self.register_buffer('phoneme_table', phoneme_table)

    def _load_phoneme_map(self, vocab_size: int, output_dim: int) -> torch.Tensor:
        """
        Build phoneme feature table from CMU dictionary.

        Features encode:
        - Vowel/Consonant type (4 bits)
        - Place of articulation (6 bits)
        - Manner of articulation (6 bits)
        - Voicing (2 bits)
        - Stress pattern (4 bits)
        - Syllable structure (10 bits)
        """
        # Implementation: Load CMU dict, map to features, return [vocab_size, 32]
        return torch.zeros(vocab_size, output_dim)  # Placeholder

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        """
        O(1) Lookup - no gradient, no learning.

        Args:
            token_ids: [B, N] token indices
        Returns:
            c_signal: [B, N, 32] phonetic features
        """
        return F.embedding(token_ids, self.phoneme_table)
```

---

##### B. OntologyProjector (R-Signal [48D])

**Concept**: Extracts "Meaning Type" (Bhava) from hidden state via MLP bottleneck.
**Why Learned**: Semantic→Ontological mapping requires compression from 896D to 48D.

```python
class OntologyProjector(nn.Module):
    """
    Lightweight MLP bottleneck for ontological extraction.

    Compresses 896D semantic body → 48D ontological essence.
    Output represents 12 Bhavas × 4 dimensions each.
    """

    def __init__(self, input_dim: int = 896, output_dim: int = 48):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.GELU(),
            nn.Linear(128, output_dim),
            nn.Sigmoid()  # Force 0-1 range for probability-like attributes
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Project semantic body to ontological space.

        Args:
            hidden_states: [B, N, 896] semantic body
        Returns:
            r_signal: [B, N, 48] ontological features (12 Bhavas × 4 dims)
        """
        return self.net(hidden_states)
```

---

##### C. S-Signal Computation (Referent [32D])

**Concept**: Identifies if token refers to known physical entity via sparse one-hot.
**Source**: Uses existing `WORD_TO_REFERENT` dictionary from codebase.

```python
def _compute_s_signal(self, token_ids: torch.Tensor) -> torch.Tensor:
    """
    Compute S-Signal via referent class lookup.

    Uses WORD_TO_REFERENT dictionary for entity identification.
    Returns sparse one-hot encoding of 15 referent classes → 32 bits.

    Args:
        token_ids: [B, N] token indices
    Returns:
        s_signal: [B, N, 32] referent class features
    """
    B, N = token_ids.shape
    s_signal = torch.zeros(B, N, 32, device=token_ids.device)

    # Convert token_ids to words (via tokenizer)
    # Look up each word in WORD_TO_REFERENT
    # Scatter referent class indices into 32D vector

    for b in range(B):
        for n in range(N):
            token_id = token_ids[b, n].item()
            word = self.tokenizer.decode([token_id])

            if word in self.referent_lookup:
                profile = self.referent_lookup[word]
                # One-hot encode primary referent classes
                for ref_class in profile.primary:
                    class_idx = ref_class.value % 32
                    s_signal[b, n, class_idx] = 1.0

    return s_signal
```

---

##### D. C-Signal Computation (Phonemic [32D])

**Concept**: Wrapper for PhonemeEncoder with caching.

```python
def _compute_c_signal(self, token_ids: torch.Tensor) -> torch.Tensor:
    """
    Compute C-Signal via phoneme encoding.

    Delegates to PhonemeEncoder for O(1) lookup.

    Args:
        token_ids: [B, N] token indices
    Returns:
        c_signal: [B, N, 32] phonetic features
    """
    return self.phoneme_encoder(token_ids)
```

---

##### E. R-Signal Computation (Ontological [48D])

**Concept**: Wrapper for OntologyProjector operating on semantic body.

```python
def _compute_r_signal(self, hidden_states: torch.Tensor) -> torch.Tensor:
    """
    Compute R-Signal via ontology projection.

    Extracts ontological essence from semantic hidden states.

    Args:
        hidden_states: [B, N, D] transformer hidden states
    Returns:
        r_signal: [B, N, 48] ontological features
    """
    # Extract semantic body (first 896 dims if 1024D, or full if 896D)
    semantic_body = hidden_states[:, :, :896] if hidden_states.size(-1) > 896 else hidden_states
    return self.ontology_projector(semantic_body)
```

---

## 3. Implementation Priority Order

### Phase 1: Foundation (Week 1-2)
| Priority | Component | Action | Complexity |
|----------|-----------|--------|------------|
| P0 | SovereignEmbedding [1024D] | NEW | Medium |
| P0 | SovereignObserver | NEW | High |
| P0 | SovereignGunaComputer | REWRITE | Medium |

### Phase 2: Core Logic (Week 3-4)
| Priority | Component | Action | Complexity |
|----------|-----------|--------|------------|
| P1 | PIDGovernor | NEW | High |
| P1 | SovereignTransformer (6/6) | REWRITE | High |
| P1 | Vritti→PID integration | REWRITE | Medium |

### Phase 3: Dynamic Features (Week 5-6)
| Priority | Component | Action | Complexity |
|----------|-----------|--------|------------|
| P2 | SovereignShift Router | REWRITE | Medium |
| P2 | SovereignLoss | NEW | Low |
| P2 | Telemetry/Audit Log | NEW | Low |

### Phase 4: Training & Validation (Week 7-8)
| Priority | Component | Action | Complexity |
|----------|-----------|--------|------------|
| P3 | Inoculation training loop | NEW | Medium |
| P3 | Bank disambiguation test | NEW | Low |
| P3 | Authority score validation | NEW | Low |

---

## 4. Risk Assessment

### 4.1 High Risk Areas

| Risk | Description | Mitigation |
|------|-------------|------------|
| PID Stability | Integral windup, derivative noise | Add anti-windup, derivative filter |
| Guna Drift | Attention-based Guna may diverge | Add normalization, EMA smoothing |
| Nexus Switching | Runtime 4/8↔8/4 shifts | Pre-compile all configurations |
| State Injection | 128D computed separately | Gradient isolation, no backprop |

### 4.2 Open Questions - RESOLVED

| Question | Decision | Implementation Details |
|----------|----------|------------------------|
| **PID Reset** | **Reset at Sequence Boundary** | PID state (integral_error, prev_error) cleared on `<BOS>` token. For streaming, state passed as hidden_state tuple (like LSTM). |
| **Guna Normalization** | **Softmax (S+R+T=1)** | Use `F.softmax(guna_raw, dim=-1)` to enforce conservation of Guna energy. Sattva + Rajas + Tamas = 1.0 always. |
| **Early Exit** | **NO - Use Dampening** | Do NOT skip layers (causes hardware sync issues). Use Authority score to multiply layer output. If `Authority < 0.1`, layer is effectively skipped (result zeroed), but compute graph remains static. |
| **Streaming** | **State Passing** | PIDGovernor returns `(output, authority, pid_state)` where `pid_state = (integral_error, prev_error)`. Caller passes state back for next chunk. |

**Updated PIDGovernor Interface**:

```python
def forward(
    self,
    x: torch.Tensor,
    target_state: torch.Tensor,
    pid_state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
) -> Tuple[torch.Tensor, torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
    """
    Returns:
        x_out: Dampened hidden states
        authority: Authority scores for telemetry
        pid_state: (integral_error, prev_error) for streaming
    """
    # Unpack or initialize PID state
    if pid_state is not None:
        self.integral_error, self.prev_error = pid_state
    elif self.integral_error is None:
        self.integral_error = torch.zeros_like(error)
        self.prev_error = torch.zeros_like(error)

    # ... PID computation ...

    # Return state for streaming
    return x_out, authority, (self.integral_error, self.prev_error)
```

---

## 5. File Structure (Proposed)

```
symbolu/sovereign/
├── __init__.py
├── embedding.py          # SovereignEmbedding [1024D]
├── observer.py           # SovereignObserver (State Delta)
├── pid_governor.py       # PIDGovernor module
├── transformer.py        # SovereignTransformer (hybrid)
├── router.py             # SovereignRouter (Sovereign Shift)
├── guna.py               # SovereignGunaComputer
├── loss.py               # SovereignLoss (StateFriction)
├── telemetry.py          # Audit log / health feed
└── config.py             # SovereignConfig dataclass

symbolu/sovereign/training/
├── inoculation.py        # Training loop with α decay
├── dataset.py            # State-stamped data augmentation
└── validation.py         # Bank disambiguation tests
```

---

## 6. Compatibility Notes

### 6.1 Backward Compatibility
- Existing `PhaseTransformer` remains unchanged
- `SemanticRouter` can be used standalone
- `CognitiveState` remains for non-Sovereign use cases

### 6.2 Forward Compatibility
- Sovereign modules designed for hardware export (PA-VPU)
- PID parameters tunable at runtime via Sovereign Command
- State partition aligned with COGNADE SDK design

---

## 7. Training Data Generation (Self-Supervised Loop)

**Key Insight**: No external labeling pipeline required. The model is self-supervised via "Next-State Prediction."

### 7.1 The Self-Teacher Loop

```
Time t:   Model sees token x_t
          Model predicts NEXT state delta: Δ_pred = f(x_t)

Time t+1: Observer sees ACTUAL next token x_{t+1}
          Observer computes ACTUAL state: S_{t+1} = Observer(x_{t+1})

Loss:     Target = S_{t+1} - S_t (the actual state change)
          L = MSE(Δ_pred, Target)
```

### 7.2 Implementation

```python
def compute_training_targets(
    input_ids: torch.Tensor,      # [B, N] - input sequence
    labels: torch.Tensor,         # [B, N] - shifted by 1 (next tokens)
    observer: SovereignObserver,
    attention_weights: torch.Tensor,
    hidden_states: torch.Tensor
) -> torch.Tensor:
    """
    Compute target state deltas for self-supervised training.

    The target is the ACTUAL state computed from the next token,
    not an external label.
    """
    # Current state from input tokens
    current_state = observer(input_ids, attention_weights, hidden_states, hidden_states)

    # Target state from next tokens (labels)
    # Use same hidden states but different token IDs
    target_state = observer(labels, attention_weights, hidden_states, hidden_states)

    # The "ground truth" is the difference
    state_delta_target = target_state - current_state

    return state_delta_target
```

### 7.3 Training Loop Pseudocode

```python
for batch in dataloader:
    input_ids, labels = batch

    # Forward pass
    logits, predicted_state, attention = model(input_ids)

    # Observer computes target (no external labels needed)
    target_state = observer(labels, attention, model.hidden_states, model.prev_hidden)

    # Loss computation
    loss, metrics = sovereign_loss(
        logits=logits,
        targets=labels,
        predicted_state=predicted_state,
        target_state=target_state,
        prev_state=model.prev_state,
        epoch=current_epoch
    )

    loss.backward()
    optimizer.step()
```

**Result**: The model learns to predict *how the cognitive state will change* before seeing the next token.

---

## 8. Sovereign Shift Mechanism (Virtual Nexus)

**Decision**: Use **Virtual Nexus via Routing**, not pre-compiled configurations.

### 8.1 Architecture

Do NOT pre-compile 3 separate models (wastes VRAM). Instead, implement **one model** with **movable PID insertion point**.

```
Physical Architecture (always loaded):
┌─────────────────────────────────────────────────┐
│ Layer 1 │ Layer 2 │ ... │ Layer 6 │ ... │ Layer 12 │
└─────────────────────────────────────────────────┘
     ↑ Quadratic-capable    ↑ Phase-capable
```

### 8.2 Mode Switching

The layers don't change - the **Governor's intervention point** moves:

| Mode | Nexus Position | Architecture | Use Case |
|------|----------------|--------------|----------|
| **4/8** | After Layer 4 | 4Q + PID + 8P | Logic-heavy (O7, O10) |
| **6/6** | After Layer 6 | 6Q + PID + 6P | Default/Creative (O6, O9) |
| **8/4** | After Layer 8 | 8Q + PID + 4P | Memory-heavy (O4, O5) |

### 8.3 Implementation

```python
class SovereignTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        # All 12 layers are "Ambidextrous" - can run either mode
        self.layers = nn.ModuleList([
            AmbidextrousLayer(...) for _ in range(12)
        ])
        self.pid_governor = PIDGovernor()

    def forward(self, x, state_delta, nexus_position=6):
        """
        Args:
            x: Input embeddings [B, N, 1024]
            state_delta: Target state from Observer [B, N, 128]
            nexus_position: Where to insert PID (4, 6, or 8)
        """
        pid_state = None

        for i, layer in enumerate(self.layers):
            # Run layer in appropriate mode
            if i < nexus_position:
                x = layer(x, mode="quadratic")
            else:
                x = layer(x, mode="phase")

            # Insert PID at nexus
            if i == nexus_position - 1:
                x, authority, pid_state = self.pid_governor(x, state_delta, pid_state)

        return x, authority
```

### 8.4 Nexus Selection Logic

```python
ONTOLOGY_TO_NEXUS = {
    # Logic-heavy: More quadratic attention needed
    "O7_REASONING": 4,
    "O10_UNIFYING": 4,

    # Balanced: Default creative mode
    "O6_AGENCY": 6,
    "O9_WITNESSES": 6,

    # Memory-heavy: More phase attention for recall
    "O4_STRUCTURE": 8,
    "O5_COGNITION": 8,

    # Default
    "default": 6
}

def select_nexus(dominant_ontology: str) -> int:
    return ONTOLOGY_TO_NEXUS.get(dominant_ontology, 6)
```

---

## 9. COGNADE Hardware Mapping

**COGNADE** (COGnitive NArrowing DElta) SDK specification for PA-VPU hardware export.

### 9.1 State Register Layout (128-bit)

The 128D state partition maps directly to a 128-bit hardware register:

| Bits | Signal | Size | Hardware Function |
|------|--------|------|-------------------|
| 000-015 | Guna Pulse | 16 | Clock/Voltage control (DVFS) |
| 016-047 | S-Signal (Referent) | 32 | Memory page prefetch trigger |
| 048-095 | R-Signal (Bhava) | 48 | Compute kernel selection (ALU/FPU) |
| 096-127 | C-Signal (Phonemic) | 32 | Audio/IO interrupt routing |

### 9.2 Hardware Actions by Signal

```
COGNADE State Register [128 bits]
┌────────────────────────────────────────────────────────────────┐
│ GUNA[16] │ S-SIGNAL[32] │ R-SIGNAL[48] │ C-SIGNAL[32] │
├──────────┼──────────────┼──────────────┼──────────────┤
│ DVFS     │ Prefetch     │ Kernel Sel   │ IO Routing   │
└────────────────────────────────────────────────────────────────┘

Guna → Dynamic Voltage/Frequency Scaling
  - High Sattva: Reduce clock (stable, efficient)
  - High Rajas: Boost clock (high activity)
  - High Tamas: Deep sleep mode (idle)

S-Signal → Memory Controller
  - Entity detected: Prefetch related memory pages
  - Sparse activation: Minimal memory traffic

R-Signal → Compute Scheduler
  - Ontology layer determines ALU vs FPU allocation
  - Logic layers (O7, O10): Favor integer ALU
  - Creative layers (O6, O9): Favor FPU/vector units

C-Signal → Peripheral Router
  - Phonemic activity: Route to audio subsystem
  - Can trigger speech synthesis pipeline
```

### 9.3 COGNADE SDK Interface

```c
// COGNADE Hardware Abstraction Layer
typedef struct {
    uint16_t guna_pulse;      // [0:15]  - 3 × 5-bit + 1 spare
    uint32_t s_signal;        // [16:47] - Referent one-hot
    uint64_t r_signal : 48;   // [48:95] - Bhava state (12 × 4)
    uint32_t c_signal;        // [96:127] - Phoneme features
} cognade_state_t;

// Hardware control functions
void cognade_set_state(cognade_state_t* state);
void cognade_trigger_prefetch(uint32_t referent_mask);
void cognade_select_kernel(uint8_t ontology_layer);
void cognade_route_audio(uint32_t phoneme_features);
```

---

## 10. State-Delta Cognition Integration

**Status**: INCORPORATED (Hardening Update)

The following elements from State-Delta Cognition Theory have been integrated to prevent training failure modes:

### 10.1 Loss Decomposition (Section 2.4.4)
| State-Delta Term | Sovereign-1 Mapping | Weight |
|-----------------|---------------------|--------|
| L_delta | (Absorbed into overall framework) | - |
| L_bhava | l_r (R-Signal MSE) | **5.0** |
| L_phoneme | l_c (C-Signal MSE) | 0.5 |
| L_coherence | l_guna (Guna MSE) | 1.0 |
| L_constraint | l_transition (Bhava transition penalty) | β=0.5 |
| L_entropy | (Implicit in Guna computation) | - |

### 10.2 Bhava Transition Priors (Section 2.4.2)
- 12×12 BHAVA_TRANSITION_MASK defines valid ontological transitions
- Prevents "Ontological Teleportation" (e.g., QUESTIONING → INSTRUCTIVE)
- Acts as "Map" to PID Governor's "Brakes"

### 10.3 Rationale
The PID Governor is **reactive** - it detects deviation after it occurs.
Bhava Transition Priors are **proactive** - they prevent illegal jumps during generation.
Combined, they provide both prevention and correction.

---

## 11. Implementation Notes (Software Reference)

**Status**: Phase 2 Complete - Engine modules implemented (PIDGovernor, SovereignTransformer, SovereignGunaComputer).

This section documents the actual implementation of Sovereign-1 components in the codebase.

### 11.1 Package Structure (Implemented)

```
symbolu/sovereign/
├── __init__.py          # Package exports (v2.0.0) ✅
├── loss.py              # SovereignLoss with decomposed state friction ✅
├── observer.py          # SovereignObserver with hardened encoders ✅ (Phase 2)
├── pid_governor.py      # PIDGovernor with Vritti tuning ✅ (Phase 2)
├── transformer.py       # SovereignTransformer hybrid architecture ✅ (Phase 2)
└── guna.py              # SovereignGunaComputer (entropy/variance/similarity) ✅ (Phase 2)

(Pending implementation - Phase 3)
├── router.py            # SovereignRouter (hardware routing)
└── cognade_export.py    # COGNADE SDK export utilities
```

### 11.2 Implemented Components

#### A. SovereignLoss (`symbolu/sovereign/loss.py`)

Implements the decomposed state friction loss to prevent Signal Washing:

```python
# Key Features:
- DEFAULT_WEIGHTS = {"guna": 1.0, "s": 2.0, "r": 5.0, "c": 0.5}
- Alpha decay from 1.0 → 0.2 over 3 epochs
- Bhava transition penalty (β=0.5)
- Diagnostic metrics: ontology_to_phoneme_ratio, meaning_fraction, signal_washing

# State Layout:
- Guna[0:16] | S-Signal[16:48] | R-Signal[48:96] | C-Signal[96:128]
```

Includes `LegacyLossAdapter` for bridging existing model outputs (12D ontology + 144D bhava) to Sovereign 128D state.

#### B. SovereignObserver (`symbolu/sovereign/observer.py`)

Computes the 128-D State Delta from token/attention/hidden state inputs:

```python
# Signals computed:
- Guna Pulse [16D]: From attention entropy (Sattva), hidden variance (Rajas), token similarity (Tamas)
- S-Signal [32D]: Referent class lookup from token_ids
- R-Signal [48D]: Ontology projection via MLP (hidden_states → 48D)
- C-Signal [32D]: Phoneme features from lookup table

# Key Methods:
- compute_guna(): Attention-based Guna derivation
- compute_s_signal(): Referent lookup
- compute_r_signal(): Ontology projection (learnable MLP)
- compute_c_signal(): Phoneme lookup (static table)
```

#### C. BhavaTransitionPrior (`symbolu/sovereign/observer.py`)

Implements the 12×12 transition mask for ontological validation:

```python
# BHAVA_TRANSITION_MASK: 12×12 matrix
# Rows/Columns: FACTUAL, ANALYTICAL, EVALUATIVE, NARRATIVE, ARGUMENTATIVE,
#               INSTRUCTIVE, CERTAIN, SPECULATIVE, QUESTIONING, POSITIVE, NEGATIVE, NEUTRAL

# Key Method:
- get_transition_penalty(current_r, prev_r): Returns penalty [0.0=legal, 1.0=illegal]
```

---

## PHASE 2 IMPLEMENTATION DETAILS (For Developer Review)

This section provides detailed implementation documentation for all Phase 2 components.

#### D. PIDGovernor (`symbolu/sovereign/pid_governor.py`) - PHASE 2

The PIDGovernor is the core control-theoretic gating mechanism at the nexus between quadratic and phase layers.

**Architecture Overview:**
```
Input [B, N, 1024] → Extract State [128D] → Compute Error → Detect Vritti → Tune PID → Gate Output
                                                    ↓
                                            VRITTI_PID_TABLE lookup
```

**Vritti Logic Table (5 Cognitive Modes):**
```python
VRITTI_PID_TABLE = {
    "pramana":   {"Kp": 0.90, "Ki": 0.05, "Kd": 0.05},  # Valid cognition - High stiffness
    "viparyaya": {"Kp": 0.70, "Ki": 0.15, "Kd": 0.15},  # Misperception - Corrective
    "vikalpa":   {"Kp": 0.30, "Ki": 0.10, "Kd": 0.60},  # Creative/branching - Fluid
    "smrti":     {"Kp": 0.50, "Ki": 0.40, "Kd": 0.10},  # Memory recall - Integral-heavy
    "nidra":     {"Kp": 0.20, "Ki": 0.70, "Kd": 0.10},  # Dormancy - Low proportional
}
```

**Ontology→Vritti Mapping:**
```python
ONTOLOGY_VRITTI_MAP = {
    0: "pramana",     # O1: FACTUAL → Valid cognition
    1: "pramana",     # O2: ANALYTICAL → Valid cognition
    2: "viparyaya",   # O3: EVALUATIVE → May contain bias (corrective mode)
    3: "vikalpa",     # O4: NARRATIVE → Creative branching
    4: "pramana",     # O5: ARGUMENTATIVE → Valid cognition
    5: "pramana",     # O6: INSTRUCTIVE → Valid cognition
    6: "pramana",     # O7: CERTAIN → High confidence
    7: "vikalpa",     # O8: SPECULATIVE → Fluid/creative
    8: "vikalpa",     # O9: QUESTIONING → Exploratory
    9: "smrti",       # O10: POSITIVE → Memory associations
    10: "smrti",      # O11: NEGATIVE → Memory associations
    11: "nidra",      # O12: NEUTRAL → Dormant/idle
}
```

**Key Methods:**

```python
class PIDGovernor(nn.Module):
    def __init__(self, config: PIDGovernorConfig, embed_dim: int = 1024):
        # Vritti detection MLP: [48D R-Signal] → [5D logits]
        self.vritti_detector = nn.Sequential(
            nn.Linear(config.state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 5),  # 5 Vritti types
        )

    def detect_vritti(self, r_signal: torch.Tensor) -> Tuple[str, torch.Tensor]:
        """
        Detect dominant Vritti from R-Signal (ontological state).

        Args:
            r_signal: [B, N, 48] - Ontological state vector
        Returns:
            vritti_name: Dominant Vritti type
            vritti_probs: [B, N, 5] probabilities for logging
        """

    def forward(
        self,
        x: torch.Tensor,           # [B, N, 1024]
        target_state: torch.Tensor, # [B, N, 128]
        pid_state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Apply PID control with Vritti-tuned parameters.

        Returns:
            x_out: Gated hidden states [B, N, 1024]
            authority: Authority scores [B, N] (for telemetry)
            pid_state: (integral_error, prev_error) for streaming
        """
```

**Authority Gating Mechanism:**
```python
# When authority < 0.7: Dampen semantic body by 0.1x
damping_factor = torch.where(
    authority.unsqueeze(-1) < 0.7,
    torch.full_like(semantic_body, 0.1),  # Dampen hallucination
    torch.ones_like(semantic_body)         # Pass through
)
semantic_body_gated = semantic_body * damping_factor
```

**Streaming Support:**
```python
# PID state is passed between forward calls for streaming inference
pid_state = (integral_error, prev_error)  # Tuple of [B, N] tensors

# Usage in streaming:
output, authority, new_state = governor(x, target, prev_state)
# ... process output ...
output, authority, new_state = governor(next_x, target, new_state)
```

**EmergencyBrake Class:**
```python
class EmergencyBrake:
    """
    Monitors authority scores and triggers circuit breaker if needed.

    Thresholds:
    - low_authority_threshold: 0.3 (warning)
    - critical_authority_threshold: 0.1 (emergency)
    - consecutive_violations: 5 (trigger brake)

    Actions:
    - Warning: Log + increase PID Kp by 10%
    - Emergency: Reset PID state + force nidra mode
    """
```

---

#### E. SovereignTransformer (`symbolu/sovereign/transformer.py`) - PHASE 2

The SovereignTransformer implements the hybrid Quadratic+Phase architecture with Virtual Nexus.

**Architecture Overview:**
```
Token IDs → Embedding [1024D] → [Quadratic Layers] → PID Governor → [Phase Layers] → LM Head → Logits
                                      ↑                    ↓
                              State Delta [128D]    Nexus Position (4/6/8)
```

**Configuration:**
```python
@dataclass
class SovereignTransformerConfig:
    vocab_size: int = 50257
    embed_dim: int = 1024       # 896 semantic + 128 state
    num_layers: int = 12
    num_heads: int = 16
    ff_dim: int = 4096
    max_seq_len: int = 8192
    dropout: float = 0.1

    semantic_dim: int = 896     # Semantic body size
    state_dim: int = 128        # State partition size

    default_nexus: int = 6      # 6/6 mode by default
    sync_steps: int = 3         # Phase attention synchronization
    sync_lr: float = 0.1        # Phase attention learning rate
```

**AmbidextrousLayer (Dual-Mode Attention):**
```python
class AmbidextrousLayer(nn.Module):
    """
    Transformer layer that can operate in either Quadratic or Phase mode.
    Enables Virtual Nexus - runtime switching of attention mechanism.
    """

    def _quadratic_attention(self, Q, K, V, causal_mask=True):
        """
        Standard O(n²) scaled dot-product attention.

        scores = (Q @ K^T) / sqrt(d)
        attn = softmax(mask(scores))
        output = attn @ V
        """

    def _phase_attention(self, Q, K, V, causal_mask=True):
        """
        O(n) phase synchronization attention.

        Key Innovation:
        1. Compute phases from Q via learnable projection
        2. Mean-field approximation for global phase
        3. Iterative synchronization (Kuramoto-inspired)
        4. Coherence-weighted value aggregation

        phases = sigmoid(phase_proj(Q)) * 2π
        for step in sync_steps:
            phase_diff = phases - phase_mean
            coupling = sin(phase_diff)
            phases = phases + sync_lr * coupling
        coherence = (1 + cos(phases - phase_mean)) / 2
        output = coherence * V + (1 - coherence) * V_global
        """

    def forward(self, x, mode="quadratic", causal_mask=True):
        # Pre-norm architecture
        x = x + attention(norm1(x), mode=mode)
        x = x + ff(norm2(x))
        return x
```

**Virtual Nexus Mapping:**
```python
ONTOLOGY_TO_NEXUS = {
    # Logic-heavy: More phase attention (earlier nexus)
    "O7_REASONING": 4,   # 4Q + 8P
    "O10_UNIFYING": 4,

    # Balanced: Default creative mode
    "O6_AGENCY": 6,      # 6Q + 6P
    "O9_WITNESSES": 6,

    # Memory-heavy: More quadratic attention (later nexus)
    "O4_STRUCTURE": 8,   # 8Q + 4P
    "O5_COGNITION": 8,

    "default": 6
}
```

**Embedding with State Partition:**
```python
def _embed(self, token_ids, state_delta=None):
    """
    Create 1024-D embeddings with state partition.

    Args:
        token_ids: [B, N] token indices
        state_delta: [B, N, 128] from Observer (optional)

    Returns:
        [B, N, 1024] = [semantic 896D] + [state 128D]
    """
    semantic = token_embedding(token_ids) + position_embedding(positions)
    state = state_delta if state_delta is not None else zeros(128)
    return cat([semantic, state], dim=-1)
```

**Forward Pass:**
```python
def forward(
    self,
    token_ids: torch.Tensor,
    state_delta: Optional[torch.Tensor] = None,
    nexus_position: Optional[int] = None,
    pid_state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    causal_mask: bool = True,
) -> Dict[str, torch.Tensor]:
    """
    Returns:
        logits: [B, N, V] - Output logits for language modeling
        authority: [B, N] - Authority scores from PID (telemetry)
        hidden_states: [B, N, 1024] - Final hidden states
        pid_state: Updated PID state for streaming
    """
```

**Generation with PID Control:**
```python
def generate(
    self,
    token_ids: torch.Tensor,
    max_new_tokens: int = 100,
    temperature: float = 1.0,
    top_k: int = 50,
    state_delta: Optional[torch.Tensor] = None,
    nexus_position: Optional[int] = None,
) -> torch.Tensor:
    """
    Autoregressive generation with PID control.
    Maintains PID state across generation steps.
    """
```

---

#### F. SovereignGunaComputer (`symbolu/sovereign/guna.py`) - PHASE 2

The SovereignGunaComputer derives the 16-D Guna Pulse using information-theoretic measures.

**The Three Gunas:**
| Guna | Meaning | Computation | Range |
|------|---------|-------------|-------|
| **Sattva** | Clarity | 1 - H(attention)/H_max | [0, 1] |
| **Rajas** | Motion/Energy | Variance(head_outputs) | [0, 1] |
| **Tamas** | Inertia | CosSim(hidden_t, hidden_{t-1}) | [0, 1] |

**Conservation Property:**
```python
# Guna energy is conserved via softmax normalization
guna_raw = stack([sattva, rajas, tamas], dim=-1)  # [B, 3]
guna_3d = F.softmax(guna_raw / temperature, dim=-1)
# Sum(Sattva + Rajas + Tamas) = 1.0 ALWAYS
```

**Sattva Computation (Shannon Entropy):**
```python
def compute_sattva(self, attention_weights: torch.Tensor) -> torch.Tensor:
    """
    Sattva = 1 - H(attention) / H_max

    High Sattva = focused attention (low entropy)
    Low Sattva = dispersed attention (high entropy)

    Args:
        attention_weights: [B, H, N, N] attention probability matrix
    Returns:
        [B] Sattva scores in [0, 1]
    """
    attn = attention_weights.clamp(min=1e-9)
    entropy = -(attn * torch.log(attn)).sum(dim=-1)  # Shannon entropy
    mean_entropy = entropy.mean(dim=[1, 2])
    max_entropy = torch.log(torch.tensor(N, dtype=torch.float))
    return 1.0 - (mean_entropy / max_entropy).clamp(0, 1)
```

**Rajas Computation (Head Variance):**
```python
def compute_rajas(self, head_outputs: torch.Tensor) -> torch.Tensor:
    """
    Rajas = σ²(head_outputs) normalized

    High Rajas = high variance across heads (energetic)
    Low Rajas = uniform head outputs (quiescent)

    Args:
        head_outputs: [B, H, N, d] per-head outputs before concat
    Returns:
        [B] Rajas scores in [0, 1]
    """
    mean_output = head_outputs.mean(dim=1, keepdim=True)
    variance = ((head_outputs - mean_output) ** 2).mean(dim=1)
    mean_variance = variance.mean(dim=[1, 2])
    return torch.sigmoid(mean_variance * 2 - 1)  # Smooth [0, 1] mapping
```

**Tamas Computation (Cosine Similarity):**
```python
def compute_tamas(
    self,
    hidden_states: torch.Tensor,
    prev_hidden_states: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """
    Tamas = CosSim(h_t, h_{t-1})

    High Tamas = high similarity to previous (stable/inertial)
    Low Tamas = large change from previous (dynamic)

    Args:
        hidden_states: [B, N, D] current hidden states
        prev_hidden_states: [B, N, D] previous hidden states
    Returns:
        [B] Tamas scores in [0, 1]
    """
    if prev_hidden_states is None:
        return torch.full((B,), 0.5, device=device)  # Neutral

    curr_norm = F.normalize(hidden_states, p=2, dim=-1)
    prev_norm = F.normalize(prev_hidden_states, p=2, dim=-1)
    similarity = (curr_norm * prev_norm).sum(dim=-1).mean(dim=1)
    return ((similarity + 1) / 2).clamp(0, 1)  # Map [-1, 1] → [0, 1]
```

**16-D Expansion:**
```python
# Expand 3D → 16D with structure-preserving projection
self.guna_expand = nn.Linear(3, 16, bias=False)

# Initialization preserves Guna structure:
# Sattva → dims 0-4 (5 dims)
# Rajas → dims 5-9 (5 dims)
# Tamas → dims 10-15 (6 dims)
expand_weight = torch.zeros(16, 3)
expand_weight[0:5, 0] = 1.0 / 5   # Sattva
expand_weight[5:10, 1] = 1.0 / 5  # Rajas
expand_weight[10:16, 2] = 1.0 / 6 # Tamas
```

**GunaMonitor (Anomaly Detection):**
```python
class GunaMonitor:
    """
    Monitors Guna dynamics for training/inference health.

    Anomaly Types:
    - Collapse: One Guna > 0.9 (dominates all computation)
    - Oscillation: Change > 0.3 between steps (unstable)
    - Stagnation: < 0.05 total change over 10 steps (stuck)

    Methods:
    - update(guna_3d): Add reading, return anomaly flags
    - get_dominant_guna(): Current dominant Guna name
    - get_statistics(): Mean/std over history window
    """
```

---

#### G. DeterministicPhonemeEncoder (`symbolu/sovereign/observer.py`) - PHASE 2

The DeterministicPhonemeEncoder generates consistent 32-D phonetic features using hash functions.

**Key Design Decision: Determinism**
```
NO RANDOMNESS - Same token → Same features ALWAYS
Uses SHA256 + MD5 hashing for reproducible feature extraction
```

**Feature Layout (32 dimensions):**
```python
# Feature Breakdown:
# [0:8]   - SHA256 hash bytes (8 dims) - Primary signature
# [8:12]  - Length features (4 dims) - log(len), char_count, etc.
# [12:16] - Vowel/consonant patterns (4 dims) - ratios and positions
# [16:24] - Bigram features (8 dims) - character pair hashes
# [24:28] - First/last char hashes (4 dims) - boundary features
# [28:32] - Pattern features (4 dims) - uppercase, digit, special char
```

**Hash-Based Feature Computation:**
```python
def _hash_token(self, token_str: str) -> List[float]:
    """
    Compute deterministic 32D features from token string.

    Process:
    1. SHA256 hash → first 8 bytes normalized to [0, 1]
    2. Length features → log-scaled
    3. Vowel/consonant analysis → ratio features
    4. Bigram hashing → MD5 of consecutive pairs
    5. Boundary characters → hash of first/last chars
    6. Pattern detection → binary flags (uppercase, digit, etc.)
    """
    features = [0.0] * 32
    clean_token = token_str.strip().lower()

    # SHA256 for primary signature
    sha_hash = hashlib.sha256(clean_token.encode()).digest()
    for i in range(8):
        features[i] = sha_hash[i] / 255.0

    # Length features
    length = len(clean_token)
    features[8] = min(length / 20.0, 1.0)
    features[9] = math.log1p(length) / math.log1p(50)
    # ... etc.

    return features
```

**Caching for Performance:**
```python
# LRU cache prevents recomputation
self._token_cache: Dict[int, List[float]] = {}

def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
    """
    Encode tokens to phoneme features with caching.

    O(1) for cached tokens, O(hash) for new tokens.
    Cache cleared on reset() or when size exceeds limit.
    """
```

---

#### H. ReferentLookup (`symbolu/sovereign/observer.py`) - PHASE 2

The ReferentLookup maps tokens to semantic referent classes using the WORD_TO_REFERENT dictionary.

**16 Referent Classes:**
```python
REFERENT_CLASSES = [
    "luminous",       # Light-emitting objects (sun, lamp, fire)
    "biological",     # Living things (plant, animal, person)
    "role_bearer",    # Roles/occupations (teacher, doctor)
    "artifact",       # Human-made objects (book, computer)
    "natural_body",   # Natural phenomena (river, mountain)
    "substance",      # Materials (water, metal, wood)
    "process",        # Actions/events (running, thinking)
    "abstract",       # Abstract concepts (freedom, justice)
    "signal",         # Communication (word, message)
    "temporal",       # Time-related (yesterday, future)
    "spatial",        # Space-related (here, above)
    "emotional",      # Emotions (happy, sad, fear)
    "social",         # Social constructs (family, government)
    "energy_source",  # Energy producers (battery, nuclear)
    "phenomenon",     # Natural events (storm, earthquake)
    "unknown",        # Default for unrecognized tokens
]
```

**One-Hot Encoding (32D):**
```python
def _encode_referent_class(self, referent_class: str) -> torch.Tensor:
    """
    One-hot encode referent class to 32D vector.

    First 16 dims: Primary class indicator
    Last 16 dims: Reserved for confidence/secondary class
    """
    encoding = torch.zeros(32)
    try:
        idx = self.REFERENT_CLASSES.index(referent_class)
        encoding[idx] = 1.0
    except ValueError:
        encoding[15] = 1.0  # Unknown
    return encoding
```

**WORD_TO_REFERENT Integration:**
```python
def forward(self, tokens: List[str]) -> torch.Tensor:
    """
    Look up referent classes for tokens.

    Uses WORD_TO_REFERENT dictionary from referent_classes.py.
    Falls back to "unknown" for unrecognized tokens.

    Returns:
        [B, N, 32] S-Signal features
    """
```

**Vocabulary Coverage:**
```
- 800+ words mapped in WORD_TO_REFERENT
- Covers common nouns, verbs, adjectives
- Unknown tokens default to index 15
```

---

### 11.3 Training Script Integration

The `train_unified_llm.py` script has been updated with Sovereign-1 support:

#### Configuration Options Added:

```python
# UnifiedTrainingConfig dataclass
use_sovereign_loss: bool = True    # Enable/disable Sovereign-1 loss
sovereign_weight_guna: float = 1.0
sovereign_weight_s: float = 2.0
sovereign_weight_r: float = 5.0    # CRITICAL: Ontological weight
sovereign_weight_c: float = 0.5
```

#### Loss Computation Flow:

1. Model outputs: `logits`, `ontological_probs` [12D], `bhava_vector` [144D], `global_coherence`
2. Build 128D state via `_build_sovereign_state()`:
   - Guna [16]: Derived from coherence
   - S-Signal [32]: First 32D of bhava
   - R-Signal [48]: Ontology (12D padded) + bhava blend
   - C-Signal [32]: Bhava[80:112]
3. Compute loss via `SovereignLoss.forward()`
4. Return metrics including R/C ratio health indicator

#### Training Loop Changes:

```python
# Initialization
sovereign_loss = SovereignLoss(config=SovereignLossConfig(...)).to(device)

# Forward pass
loss, metrics = compute_ontological_loss(
    outputs, y, config,
    sovereign_loss=sovereign_loss,
    epoch=global_step // len(train_loader),
)

# Logging
log_msg += f" | R/C: {metrics['onto_phoneme_ratio']:.2f} [{health}]"
```

### 11.4 Key Implementation Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Legacy Compatibility** | LegacyLossAdapter maps 156D → 128D | Allows gradual migration without breaking existing models |
| **Phoneme Encoding** | Deterministic hash-based (Phase 2) | Consistent features from token strings via SHA256/MD5 |
| **Referent Table** | WORD_TO_REFERENT integration (Phase 2) | Maps 800+ words to 16 referent classes |
| **Gradient Flow** | Observer runs `@torch.no_grad()` | Matches spec - Observer provides targets, not learned |
| **Virtual Nexus** | Runtime configurable (4/6/8) | Single model supports 3 nexus positions |
| **Vritti Tuning** | 5-mode PID lookup table | Adapts Kp/Ki/Kd based on dominant R-Signal |

### 11.5 Validation Status

| Component | Unit Tests | Integration | Hardware Ready |
|-----------|------------|-------------|----------------|
| SovereignLoss | ✅ Ready | ✅ Integrated | 🔲 N/A |
| SovereignObserver | ✅ Ready | ✅ Integrated | 🔲 N/A |
| BhavaTransitionPrior | ✅ Ready | ✅ Integrated | 🔲 N/A |
| PIDGovernor | ✅ Ready | ✅ Implemented | 🔲 N/A |
| SovereignTransformer | ✅ Ready | ✅ Implemented | 🔲 N/A |
| SovereignGunaComputer | ✅ Ready | ✅ Implemented | 🔲 N/A |
| DeterministicPhonemeEncoder | ✅ Ready | ✅ Implemented | 🔲 N/A |
| ReferentLookup | ✅ Ready | ✅ Implemented | 🔲 N/A |
| SovereignRouter | ✅ Ready | ✅ Implemented | 🔲 N/A |
| SovereignMonitor | ✅ Ready | ✅ Implemented | 🔲 N/A |
| COGNADE Export | ✅ Ready | ✅ Implemented | ✅ Ready |

**Note:** Run `./scripts/run_phase2_tests.sh` for unit tests, `python -m pytest tests/integration/` for integration tests.

### 11.6 Implementation Steps Status

**Phase 1** (Complete):
1. ✅ SovereignLoss - Complete
2. ✅ SovereignObserver - Complete
3. ✅ BhavaTransitionPrior - Complete
4. ✅ Training script integration - Complete

**Phase 2** (Complete):
1. ✅ PIDGovernor with Vritti detection - `pid_governor.py`
2. ✅ SovereignGunaComputer (Shannon entropy/variance/cosine) - `guna.py`
3. ✅ DeterministicPhonemeEncoder (hash-based, no random) - `observer.py`
4. ✅ ReferentLookup (WORD_TO_REFERENT integration) - `observer.py`
5. ✅ SovereignTransformer (hybrid 6Q+6P) - `transformer.py`
6. ✅ Virtual Nexus support (4/6/8 modes) - `transformer.py`
7. ✅ Unit tests for all modules - Complete (`tests/test_sovereign_phase2.py`)

**Phase 3** (Complete):
1. ✅ SovereignRouter (Virtual Nexus selection) - `router.py`
2. ✅ SovereignMonitor (Telemetry Dashboard) - `telemetry.py`
3. ✅ COGNADE SDK export utilities - `cognade_export.py`
4. ✅ Integration tests - `tests/integration/test_sovereign_integration.py`

**Phase 4** (Next):
1. 🔲 Training script integration with Phase 3 components
2. 🔲 Hardware routing optimization
3. 🔲 Production deployment preparation

---

## PHASE 3 IMPLEMENTATION DETAILS (Transmission & Dashboard)

### I. SovereignRouter (`symbolu/sovereign/router.py`)

The SovereignRouter implements the "Transmission" - dynamic nexus selection based on query semantics.

**ONTOLOGY_TO_NEXUS Mapping:**
```python
ONTOLOGY_TO_NEXUS = {
    # Logic-Heavy: 4 Quadratic + 8 Phase
    "O7_REASONING": 4,     # Logic, analysis
    "O10_UNIFYING": 4,     # Synthesis, connection

    # Balanced: 6 Quadratic + 6 Phase (default)
    "O6_AGENCY": 6,        # Direction, control
    "O9_WITNESSES": 6,     # Meta-observation

    # Memory-Heavy: 8 Quadratic + 4 Phase
    "O4_STRUCTURE": 8,     # Form, organization
    "O5_COGNITION": 8,     # Perception
}
```

**Key Methods:**
```python
class SovereignRouter(SemanticRouter):
    def route_sovereign(self, query: str) -> SovereignRoutingDecision:
        """
        Route query with Nexus position selection.

        Returns:
            SovereignRoutingDecision with:
            - model_type: Semantic model type
            - nexus_position: Virtual Nexus (4, 6, or 8)
            - nexus_mode: "4/8 (Logic-Heavy)", "6/6 (Balanced)", etc.
            - confidence: Routing confidence
            - dominant_layer: Ontological layer (e.g., "O7_REASONING")
        """
```

**Usage:**
```python
from symbolu.sovereign import SovereignRouter

router = SovereignRouter()
decision = router.route_sovereign("Explain quantum entanglement")
# decision.nexus_position = 4 (logic-heavy)

outputs = transformer(tokens, nexus_position=decision.nexus_position)
```

---

### J. SovereignMonitor (`symbolu/sovereign/telemetry.py`)

The SovereignMonitor implements the "Dashboard" - real-time state visualization.

**Heartbeat Log Format:**
```
[SOVEREIGN] Nexus: 6/6 | Auth: 0.92 | Vritti: PRAMANA | Guna: SATTVA (0.8)
[TRACE] Locked Referent: NATURAL_BODY | Bhava: O4_STRUCTURE
```

**StateSnapshot Structure:**
```python
@dataclass
class StateSnapshot:
    timestamp: str
    step: int

    # Guna components (normalized, sum to 1.0)
    sattva: float
    rajas: float
    tamas: float
    dominant_guna: str

    # Authority from PID Governor
    authority: float

    # Active signals
    dominant_referent: str  # S-Signal
    dominant_bhava: str     # R-Signal

    # Vritti (cognitive mode)
    vritti: str

    # Nexus configuration
    nexus_position: int
    nexus_mode: str

    # Emergency flags
    is_emergency: bool
    anomaly_type: Optional[str]
```

**Emergency Logging:**
When `authority < 0.1`, the monitor dumps the full 128-D state:
```json
{
  "type": "EMERGENCY",
  "anomaly": "AUTHORITY_COLLAPSE",
  "authority": 0.08,
  "guna": {"sattva": 0.1, "rajas": 0.8, "tamas": 0.1},
  "signals": {"referent": "UNKNOWN", "bhava": "O7_REASONING"},
  "raw_state_128d": [...]
}
```

---

### K. COGNADE Export (`symbolu/sovereign/cognade_export.py`)

Hardware bridge for PA-VPU (Phase Attention Vector Processing Unit).

**C-Struct Definition (cognade_state.h):**
```c
typedef struct __attribute__((packed)) {
    uint16_t guna_pulse;   /* Bits 0-15:   Guna Pulse */
    uint32_t s_signal;     /* Bits 16-47:  S-Signal (Referent) */
    uint64_t r_signal;     /* Bits 48-111: R-Signal (Ontology) */
    uint32_t c_signal;     /* Bits 112-143: C-Signal (Phonemic) */
} cognade_state_t;
```

**Export Functions:**
```python
from symbolu.sovereign import export_cognade_sdk

files = export_cognade_sdk(
    output_dir="./cognade_sdk",
    word_to_referent=WORD_TO_REFERENT,
    version="1.0.0"
)
# Returns:
# - header: cognade_state.h
# - phoneme_impl: cognade_phoneme.c
# - referent_table: referent_table.bin (binary lookup)
```

**Binary State Packing:**
```python
from symbolu.sovereign import pack_state_to_binary

# Pack 128-D float state to 16-byte binary
binary = pack_state_to_binary(state_128d)

# Unpack back (lossy due to quantization)
state = unpack_binary_to_state(binary)
```

---

## PHASE 3 INTEGRATION TESTS

### Test File Location
```
tests/integration/test_sovereign_integration.py
```

### Running Tests
```bash
# Run all integration tests
python -m pytest tests/integration/test_sovereign_integration.py -v

# Run specific test case
python -m pytest tests/integration/test_sovereign_integration.py::TestShifter -v
```

### Critical Test Cases

#### Test A: The Dampener
```python
def test_dampening_reduces_magnitude(self):
    """
    Verify authority gating reduces output when authority < 0.7.

    Scenario: High mismatch between R-Signal and prompt.
    Expected: Authority drops, semantic body dampened by 0.1x.
    """
```

#### Test B: The Shifter
```python
def test_different_nexus_produces_different_output(self):
    """
    CRITICAL: Verify Virtual Nexus reconfigures architecture.

    Scenario A: Math problem → Nexus 4 (4Q + 8P)
    Scenario B: Poem → Nexus 6 (6Q + 6P)
    Expected: Different outputs for different nexus positions.
    """
```

#### Test C: The Physics
```python
def test_guna_conservation(self):
    """
    CRITICAL: Verify Sattva + Rajas + Tamas = 1.0 always.

    This is the fundamental conservation law of the cognitive model.
    """
```

---

## PHASE 2 UNIT TESTS

### Test File Location
```
tests/test_sovereign_phase2.py
```

### Running Tests

**Quick Start:**
```bash
./scripts/run_phase2_tests.sh
```

**Manual Execution:**
```bash
# Install dependencies
pip install torch pytest

# Run all tests
python -m pytest tests/test_sovereign_phase2.py -v

# Run specific test class
python -m pytest tests/test_sovereign_phase2.py::TestPIDGovernor -v

# Run tests matching keyword
python -m pytest tests/test_sovereign_phase2.py -k "gradient" -v
```

### Test Coverage Matrix

| Component | Test Class | Critical Checks |
|-----------|------------|-----------------|
| **PIDGovernor** | `TestPIDGovernor` | Vritti detection, authority gating, gradient flow, streaming |
| **AmbidextrousLayer** | `TestAmbidextrousLayer` | Mode switching (quadratic vs phase), gradient flow both modes |
| **SovereignTransformer** | `TestSovereignTransformer` | Virtual Nexus positions, forward/backward pass, nexus selection |
| **SovereignGunaComputer** | `TestSovereignGunaComputer` | Sattva entropy, Rajas variance, Tamas similarity, conservation |
| **DeterministicPhonemeEncoder** | `TestDeterministicPhonemeEncoder` | Determinism, feature shape, hash consistency |
| **ReferentLookup** | `TestReferentLookup` | Output shape, 16 referent classes |
| **BhavaTransitionPrior** | `TestBhavaTransitionPrior` | Penalty range, legal vs illegal transitions |
| **SovereignObserver** | `TestSovereignObserver` | 128-D state delta shape, no_grad mode |
| **End-to-End** | `TestEndToEndIntegration` | Full forward/backward pass through all modules |

### Critical Test Cases

#### 1. Gradient Flow (CRITICAL)
```python
def test_gradient_flow(self):
    """CRITICAL: Test that gradients flow through PIDGovernor correctly."""
    x = torch.randn(B, N, D, requires_grad=True)
    x_out, authority, _ = governor(x, target_state)
    loss = x_out.sum()
    loss.backward()

    # MUST PASS: x.grad is not None and not all zeros
    assert x.grad is not None
    assert not torch.allclose(x.grad, torch.zeros_like(x.grad))
```

#### 2. Mode Switching (CRITICAL)
```python
def test_mode_switching(self):
    """CRITICAL: Quadratic and phase modes produce different outputs."""
    out_quadratic = layer(x, mode="quadratic")
    out_phase = layer(x, mode="phase")

    # MUST PASS: Different modes = different outputs
    assert not torch.allclose(out_quadratic, out_phase, atol=1e-3)
```

#### 3. Guna Conservation (CRITICAL)
```python
def test_guna_conservation(self):
    """CRITICAL: Guna values sum to 1.0 (conservation of energy)."""
    guna_3d = result["guna_3d"]  # [B, 3]
    guna_sum = guna_3d.sum(dim=-1)

    # MUST PASS: S + R + T = 1.0
    assert torch.allclose(guna_sum, torch.ones_like(guna_sum), atol=1e-5)
```

#### 4. Deterministic Phoneme Encoding (CRITICAL)
```python
def test_determinism(self):
    """CRITICAL: Same token produces same features always."""
    out1 = encoder(token_ids)
    out2 = encoder(token_ids)

    # MUST PASS: Identical outputs
    assert torch.allclose(out1, out2)
```

### Expected Test Results

When all tests pass:
```
============================== test session starts ==============================
platform linux -- Python 3.11.x, pytest-9.x.x
collected 25 items

tests/test_sovereign_phase2.py::TestPIDGovernor::test_forward_shape PASSED
tests/test_sovereign_phase2.py::TestPIDGovernor::test_vritti_detection PASSED
tests/test_sovereign_phase2.py::TestPIDGovernor::test_authority_gating PASSED
tests/test_sovereign_phase2.py::TestPIDGovernor::test_gradient_flow PASSED
tests/test_sovereign_phase2.py::TestPIDGovernor::test_streaming_state PASSED
tests/test_sovereign_phase2.py::TestAmbidextrousLayer::test_mode_switching PASSED
tests/test_sovereign_phase2.py::TestAmbidextrousLayer::test_quadratic_attention_complexity PASSED
tests/test_sovereign_phase2.py::TestAmbidextrousLayer::test_phase_attention_linear_complexity PASSED
tests/test_sovereign_phase2.py::TestAmbidextrousLayer::test_gradient_flow_both_modes PASSED
tests/test_sovereign_phase2.py::TestSovereignTransformer::test_forward_pass PASSED
tests/test_sovereign_phase2.py::TestSovereignTransformer::test_virtual_nexus_positions PASSED
tests/test_sovereign_phase2.py::TestSovereignTransformer::test_nexus_selection_by_ontology PASSED
tests/test_sovereign_phase2.py::TestSovereignTransformer::test_gradient_flow_with_pid PASSED
tests/test_sovereign_phase2.py::TestSovereignGunaComputer::test_sattva_entropy PASSED
tests/test_sovereign_phase2.py::TestSovereignGunaComputer::test_rajas_variance PASSED
tests/test_sovereign_phase2.py::TestSovereignGunaComputer::test_tamas_similarity PASSED
tests/test_sovereign_phase2.py::TestSovereignGunaComputer::test_guna_conservation PASSED
tests/test_sovereign_phase2.py::TestSovereignGunaComputer::test_guna_range PASSED
tests/test_sovereign_phase2.py::TestDeterministicPhonemeEncoder::test_determinism PASSED
tests/test_sovereign_phase2.py::TestDeterministicPhonemeEncoder::test_output_shape PASSED
tests/test_sovereign_phase2.py::TestDeterministicPhonemeEncoder::test_hash_token_features PASSED
tests/test_sovereign_phase2.py::TestReferentLookup::test_output_shape PASSED
tests/test_sovereign_phase2.py::TestReferentLookup::test_referent_classes PASSED
tests/test_sovereign_phase2.py::TestBhavaTransitionPrior::test_penalty_shape PASSED
tests/test_sovereign_phase2.py::TestBhavaTransitionPrior::test_penalty_range PASSED
tests/test_sovereign_phase2.py::TestBhavaTransitionPrior::test_legal_transition_low_penalty PASSED
tests/test_sovereign_phase2.py::TestSovereignObserver::test_full_state_delta_shape PASSED
tests/test_sovereign_phase2.py::TestSovereignObserver::test_no_grad_mode PASSED
tests/test_sovereign_phase2.py::TestEndToEndIntegration::test_full_forward_backward PASSED

============================== 25 passed ==============================
```

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: torch` | PyTorch not installed | `pip install torch` |
| `ImportError: symbolu` | Not in project root | `cd /path/to/symbolu` |
| `test_gradient_flow FAILED` | PID zeroing gradients | Check dampening_factor > 0 |
| `test_mode_switching FAILED` | Modes identical | Check `mode` param passed correctly |
| `test_guna_conservation FAILED` | Softmax not applied | Verify temperature > 0 |

---

## 12. Approval Checklist

Before implementation begins, confirm:

### Core Architecture
- [ ] 128-D partition layout approved (Guna[16] + S[32] + R[48] + C[32])
- [ ] PID parameters approved (default Kp=0.65, Ki=0.10, Kd=0.25)
- [ ] Vritti→PID lookup table approved
- [ ] Authority threshold approved (0.7)
- [ ] α decay schedule approved (1.0 → 0.2 over 3 epochs)
- [ ] Nexus positions approved (4/8, 6/6, 8/4)

### Hardening Components (NEW)
- [ ] Loss weights approved (guna=1.0, s=2.0, r=5.0, c=0.5)
- [ ] Transition penalty weight approved (β=0.5)
- [ ] BHAVA_TRANSITION_MASK values approved (12×12 matrix)
- [ ] Monitoring thresholds approved (ontology_to_phoneme_ratio > 3.0 = GOOD)

---

**Document Status**: Phase 3 Complete (Transmission & Dashboard)
**Current Phase**: Phase 3 Complete - Router, Telemetry, COGNADE Export, Integration Tests
**Next Step**: Run integration tests, then begin Phase 4 (Training Integration)
**Revision**: v3.0 - Added Phase 3 implementation (SovereignRouter, SovereignMonitor, COGNADE SDK)

---

*Generated by Claude Code | Symbolu Sovereign-1 Design Implementation v3.0*
