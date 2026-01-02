# Sovereign-1: Design Implementation Document

**Status**: DRAFT - For Final Review
**Date**: 2026-01-02
**Purpose**: Evaluate existing Symbolu codebase against Sovereign-1 specification and define implementation path

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

#### 2.4.2 Observer Algorithm (State Delta Generator)
**Status**: Partially exists, needs adaptation

```python
# NEW: Observer Algorithm for State Delta computation
class SovereignObserver(nn.Module):
    """
    Computes the 128-D State Delta in parallel with main transformer.

    Runs as a lightweight observer, not part of gradient flow.
    """

    def __init__(self, vocab_size, referent_dict):
        super().__init__()
        self.referent_lookup = referent_dict  # WORD_TO_REFERENT
        self.phoneme_encoder = PhonemeEncoder(output_dim=32)
        self.ontology_projector = OntologyProjector(output_dim=48)

    @torch.no_grad()
    def forward(
        self,
        token_ids: torch.Tensor,      # [B, N]
        attention_weights: torch.Tensor,  # [B, H, N, N]
        hidden_states: torch.Tensor,  # [B, N, D]
        prev_hidden: torch.Tensor,    # [B, N, D]
    ) -> torch.Tensor:
        """
        Compute 128-D State Delta.

        Returns:
            state_delta: [B, N, 128] target state for PID Governor
        """
        B, N = token_ids.shape

        # [896-911] Guna Pulse (16 dims)
        guna = self._compute_guna(attention_weights, hidden_states, prev_hidden)

        # [912-943] S-Signal (32 dims) - Referent class one-hot
        s_signal = self._compute_s_signal(token_ids)

        # [944-991] R-Signal (48 dims) - Ontological layer projection
        r_signal = self._compute_r_signal(hidden_states)

        # [992-1023] C-Signal (32 dims) - Phonemic encoding
        c_signal = self._compute_c_signal(token_ids)

        # Concatenate
        state_delta = torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)

        return state_delta

    def _compute_guna(self, attn, hidden, prev_hidden):
        """Compute Guna Pulse [16 dims]."""
        # Sattva: Inverse attention entropy
        attn_entropy = -(attn * torch.log(attn + 1e-9)).sum(dim=-1).mean(dim=1)
        sattva = 1.0 - attn_entropy / math.log(attn.size(-1))

        # Rajas: Head output variance
        rajas = hidden.var(dim=-1)

        # Tamas: Token similarity
        tamas = F.cosine_similarity(hidden, prev_hidden, dim=-1)

        # Expand to 16 dims (redundant encoding for robustness)
        guna = torch.stack([
            sattva.unsqueeze(-1).expand(-1, -1, 5),
            rajas.unsqueeze(-1).expand(-1, -1, 5),
            tamas.unsqueeze(-1).expand(-1, -1, 6),
        ], dim=-1).flatten(-2)[:, :, :16]

        return guna
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

#### 2.4.4 Training Loss: State Friction
**Status**: Partially exists, needs modification

```python
# NEW: Sovereign Loss Function
class SovereignLoss(nn.Module):
    """
    Loss = CrossEntropy + α × StateFriction

    α decays from 1.0 (Epoch 1) to 0.2 (Epoch 3+)
    """

    def __init__(self, alpha_initial=1.0, alpha_final=0.2, decay_epochs=3):
        super().__init__()
        self.alpha_initial = alpha_initial
        self.alpha_final = alpha_final
        self.decay_epochs = decay_epochs
        self.ce_loss = nn.CrossEntropyLoss()

    def get_alpha(self, epoch: int) -> float:
        """Compute decayed alpha."""
        if epoch >= self.decay_epochs:
            return self.alpha_final
        progress = epoch / self.decay_epochs
        return self.alpha_initial - progress * (self.alpha_initial - self.alpha_final)

    def forward(
        self,
        logits: torch.Tensor,           # [B, N, V]
        targets: torch.Tensor,          # [B, N]
        predicted_state: torch.Tensor,  # [B, N, 128]
        target_state: torch.Tensor,     # [B, N, 128]
        epoch: int = 0
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        # Cross-entropy
        ce = self.ce_loss(logits.view(-1, logits.size(-1)), targets.view(-1))

        # State friction (MSE on state delta)
        state_friction = F.mse_loss(predicted_state, target_state)

        # Decayed combination
        alpha = self.get_alpha(epoch)
        total = ce + alpha * state_friction

        return total, {
            "ce_loss": ce.item(),
            "state_friction": state_friction.item(),
            "alpha": alpha,
            "total_loss": total.item()
        }
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

### 4.2 Open Questions for Review

1. **PID Reset**: Should integral/derivative error reset at sequence boundaries?
2. **Guna Normalization**: Hard sigmoid vs softmax for S+R+T=1 constraint?
3. **Early Exit**: Should low-authority tokens skip Phase layers entirely?
4. **Streaming**: How does PID state persist across chunks?

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
- State partition aligned with COHERA SDK design

---

## 7. Approval Checklist

Before implementation begins, confirm:

- [ ] 128-D partition layout approved (Guna[16] + S[32] + R[48] + C[32])
- [ ] PID parameters approved (default Kp=0.65, Ki=0.10, Kd=0.25)
- [ ] Vritti→PID lookup table approved
- [ ] Authority threshold approved (0.7)
- [ ] α decay schedule approved (1.0 → 0.2 over 3 epochs)
- [ ] Nexus positions approved (4/8, 6/6, 8/4)

---

**Document Status**: Ready for Final Review
**Next Step**: Obtain approval on open questions, then begin Phase 1 implementation

---

*Generated by Claude Code | Symbolu Sovereign-1 Design Implementation*
