# Hybrid Phase-Quad Transformer Architecture

**As-Implemented Reference** | March 2026 | Based on `phase_transformer.py` + `train.py`

This document describes the **HybridPhaseTransformer** architecture as actually implemented and trained — not the ontological hybrid model, not aspirational designs, but the code that runs.

---

## 1. Architecture Overview

The HybridPhaseTransformer is a language model that combines three attention mechanisms at different abstraction levels, plus an associative slot memory:

```
Input Tokens
    │
    ▼
┌─────────────────────────────────┐
│  Token Embedding + Position Emb │  [B, N, D]
│  + Dropout                      │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  Layers 0..(L-1): Local Only    │  O(n·w) sliding window attention
│  (LocalTransformerBlock)        │  Fast syntax/bigram learning
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  Layers L..(N-1): Hybrid        │  Phase → Local cross-attention
│  (HybridTransformerBlock)       │  + SlotMemory read/write per layer
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  LayerNorm → LM Head × logit_s │  [B, N, vocab_size]
└─────────────────────────────────┘
```

**Default configuration** (46M params):
- `embed_dim`: 768
- `num_layers`: 12
- `num_heads`: 12
- `local_layers`: 4 (layers 0-3 are local-only)
- `window_size`: 256
- `max_seq_len`: 8192
- Tied embeddings (`lm_head.weight = token_embed.weight`)
- Learnable `logit_scale` (initialized to 1.0)

---

## 2. The Three Attention Mechanisms

### 2.1 Local Attention (Layers 0 through `local_layers-1`)

Standard sliding-window causal attention. Each token attends only to tokens within `window_size` positions behind it.

- **Complexity**: O(n · w) where w = window_size
- **What it learns**: Bigrams, local syntax, short-range patterns
- **Implementation**: `LocalTransformerBlock` → `LocalAttention` → FlashAttention or manual SDPA
- **GQA support**: Optional grouped-query attention via `n_kv_heads`

Each block: `x = LocalAttention(x) → FFN(x)` with pre-norm residuals.

### 2.2 Phase Attention (Inside Hybrid layers)

O(n) linear attention using complex-valued phasors. This is the core innovation — causal attention without quadratic cost.

**Mathematical model**:
```
Q = a_q · e^(iφ_q)          # Query phasor: amplitude × phase angle
K = a_k · e^(-iφ_k)         # Key phasor: conjugated

State_t = Σ_{s≤t} (K_s · V_s)   # Cumulative state via parallel scan
Output_t = Re(Q_t · State_t) / Normalizer_t
```

**Key details**:
- Amplitudes: `a = 0.05 + 0.95 · sigmoid(raw)` (floor prevents gradient death)
- Phase offsets: Per-head learnable offsets prevent all heads converging
- Normalizer: `(a_q · cumsum(a_k)).clamp(min=0.1).detach()` — detached to prevent gradient explosion through division
- Decay: Optional per-head learned decay `γ` via parallel EMA scan
- Bounded phase mode: `φ = π · sin(φ_raw)` constrains to [-π, π]
- Phase warm-start: `α = sigmoid((step - center) / τ)` dampens writes during early training

**Three cosine readout modes**:
1. **Standard**: `cos(φ_q - φ_k)` range [-1, +1]
2. **Shifted**: Adds amplitude-only term, range [0, 2], eliminates negative cancellation
3. **Complex**: Uses both real and imaginary parts, projects through learned layer

**State for chunking**: Returns `final_state` (last cumulative state) for chunk-to-chunk persistence.

### 2.3 Protected Phase Mode (How Local + Phase Combine)

In the default **Protected Phase** mode, the hybrid layers execute serially:

```
Input x
    │
    ├──→ PhaseAttention(x) ──→ memory_state [B, N, H, D_h]
    │                              │
    │                              ▼
    └──→ LocalAttention(x, K=memory_state, V=memory_state)
                                   │
                                   ▼
                          residual + local_output
```

Phase runs first and produces a `memory_state` — the cumulative O(n) state at each position. Local attention then **cross-attends** to this phase memory instead of the input tokens. This means:

- Phase must learn useful representations for local to query
- No gradient competition (they're serial, not parallel)
- Phase provides long-range context; local provides precise extraction

The phase memory is RMS-normalized before local cross-attention (prevents unbounded cumsum magnitudes).

**Legacy parallel mode** (`protected_phase=False`): Weighted blend `w_local · x_local + w_phase · x_phase` with learnable `alpha_local` and `alpha_phase`.

### 2.4 Binding Cache / Quad Query

`BindingCacheQuadQuery` provides quadratic attention that queries from Phase's memory state (not raw tokens):

```
Q: from input tokens
K, V: from Phase's memory_state

scores = Q @ K^T
proposals, scores = TopK(scores, k)    # O(n·k) instead of O(n²)
```

- **Proposal mode** (V10.4): Quad generates top-K proposals; Phase integrates them via learned gating
- **Conditional skip**: When phase confidence > threshold, quad is skipped entirely (saves compute when phase is sufficient)

---

## 3. Slot Memory (SlotMemoryGCT)

An associative key-value store with 64 learnable slots. Provides persistent memory across the training run.

### 3.1 Slot State

```python
slot_keys:  [64, key_dim]     # L2-normalized, orthogonally initialized
slot_vals:  [64, embed_dim]   # Zero-initialized
```

### 3.2 Write Path

Competitive assignment — tokens compete to write to the nearest slots:

```
1. write_keys = write_key_proj(x.detach())     # Detached from main graph
   write_vals = write_val_proj(x.detach())

2. scores = cosine_sim(write_keys, slot_keys)  # [B, N, 64]
   top_k_slots = scores.topk(write_top_k)     # Hard routing to k slots

3. gate = sigmoid(write_novelty_gate(x))       # Novelty gating [0, 1]

4. EMA update per slot:
   slot_vals[k] = (1 - η) · slot_vals[k] + η · weighted_incoming
   slot_keys[k] = L2_normalize((1 - η) · slot_keys[k] + η · incoming_keys)
   where η = write_lr × write_pressure
```

Key property: writes are **detached** from the main computation graph. The LM loss does not directly optimize what gets written — only retrieval loss does.

### 3.3 Read Path

Content-based retrieval via cosine similarity:

```
1. queries = read_query_proj(x)                    # Separate from write proj
2. scores = (queries_norm @ slot_keys_norm^T) × rd_scale   # Learnable temperature
3. attn = softmax(scores)                          # [B, N, 64]
4. retrieved = attn @ slot_vals                    # [B, N, D]
5. output = read_output_proj(retrieved)

Integration: x = x + read_warmstart_alpha × output
```

- `rd_scale`: Learnable inverse temperature (init ~22, clamped [18, 128]). Controls softmax sharpness.
- `read_warmstart_alpha`: Sigmoid ramp from 0→1 over ~100 steps. Prevents slots from corrupting early training.
- `read_H` (diagnostic): Entropy of read attention. High = uniform reads, low = sharp slot selection.

### 3.4 Retrieval Loss

The primary learning signal for slots. Tests whether retrieved content can predict the next token:

```
slot_vals → attention_retrieval → read_output_proj → retr_read_norm → lm_head → CE loss
```

- Applied only at positions **beyond the local window** (positions ≤ window_size can be predicted by local attention alone)
- Weight: `retrieval_loss_weight` (default 0.1), adaptively adjusted
- This is the ONLY gradient source for `read_output_proj` and `read_query_proj`

### 3.5 Router / Sharpness Loss

Four-term auxiliary loss for write assignment health:

| Term | Purpose |
|------|---------|
| `L_sharp` | ReLU(per_token_entropy - H_target) — prevents uniform assignment |
| `L_bal` | KL(marginal_assignment ∥ uniform) — prevents slot collapse |
| `L_gate_util` | -log(novelty_gate) — log-barrier pushing gate open |
| `L_gate_ceil` | Quadratic penalty above gate_target — prevents write churn |
| `L_ortho` | ‖K·K^T - I‖_F² — maintains orthogonal slot keys |

### 3.6 Adaptive Slot Controls

The slot memory has several self-tuning mechanisms:

- **Gate ceiling** (`_gate_target`): Adapts based on retrieval loss trend
- **Write scale** (`_wr_scale_max`): Expands when optimizer pushes against ceiling
- **Read scale** (`_read_scale_max`): Expands when attention needs sharper routing
- **Retrieval loss weight**: Scales based on ratio to LM loss
- **Retr_weight guard** (V11.2): Reduces retrieval weight if ablation shows slots hurting

### 3.7 Slot Ablation Eval

Every 200 steps, temporarily disables slot reads (forces `read_warmstart_alpha → 0`), runs a mini-eval, and reports PPL delta:

```
Delta = PPL_without_slots - PPL_with_slots
  > +1.0  →  "slots helping"
  > -1.0  →  "slots neutral"
  < -1.0  →  "slots hurting"
```

---

## 4. Learning Hierarchy

The three mechanisms learn at different stages, corresponding to different PPL regimes:

```
PPL 100+ ──→ Local attention dominates
              Learning: word frequencies, bigrams, basic syntax
              Phase: warming up via alpha ramp, building state scaffold
              Slots: bootstrapping, learning what to store

PPL 30-100 ──→ Phase starts contributing
               Learning: cross-position dependencies, coherence
               Local: refining within-window predictions
               Slots: retrieval loss falling, content improving

PPL 15-30 ──→ Phase + Local jointly effective
              Phase provides long-range context local can't see
              Slots: beginning to show measurable ablation delta

PPL <15 ──→ Slots become the marginal differentiator
            Transformer weights saturated for this param budget
            Slots provide factual recall beyond what weights can memorize
```

---

## 5. Training Pipeline

### 5.1 Optimizer Setup

**AdamW** with separate parameter groups:

| Group | LR | Weight Decay | Contents |
|-------|-----|-------------|----------|
| Main | `learning_rate` (e.g. 2e-4) | 0.01 | All non-slot parameters |
| Slot (matrices) | `learning_rate × slot_memory_lr_scale` | 0.01 | Slot projections, gate weights |
| Slot (no-WD) | `learning_rate × slot_memory_lr_scale` | 0.0 | `slot_keys_init` (zero gradient, WD would shrink pointlessly) |

Optional 8-bit optimizer via bitsandbytes.

### 5.2 Learning Rate Schedule

**Three-phase schedule**:
1. **Linear warmup**: 0 → `learning_rate` over `warmup_steps` (or until PPL < `warmup_until_ppl`)
2. **Cosine annealing**: `learning_rate` → `min_lr` over remaining steps
3. **Adaptive overrides**: `AdaptiveTrainingController` can boost or decay LR based on PPL velocity

**Adaptive warmup** (`warmup_until_ppl`): Instead of fixed step count, warmup ends when validation PPL drops below threshold. Prevents premature LR ramp on hard datasets.

### 5.3 PPL-Alpha Curriculum

Dynamically adjusts `alpha_phase` / `alpha_local` based on current PPL:

```
PPL >= ppl_high (1000):  alpha_phase = 0.8  (phase dominates)
PPL <= ppl_low  (100):   alpha_phase = 0.3  (local refines)
Between: linear interpolation
```

**Post-curriculum adaptive alpha**: After PPL settles below `ppl_low`, adjusts alpha based on slot ablation delta. If slots are helping more, phase gets more weight (slots depend on phase state).

### 5.4 Loss Function

Total loss is the sum of:

```
L_total = L_CE                           # Main cross-entropy (next token prediction)
        + L_router                       # Slot router loss (L_sharp + L_bal + L_ortho + L_gate)
        + w_retr × L_retrieval           # Slot retrieval loss
        + w_pred × L_slot_prediction     # Slot-only prediction head (V11.4)
        + L_entropy_band                 # Confidence scaler entropy band (optional)
        + L_decorrelation                # Phase-local decorrelation (optional)
```

Divided by `gradient_accumulation` before backward.

### 5.5 Gradient Management

Gradients are managed with surgical precision due to the different numerical regimes:

1. **Slot memory per-element clip** (0.01): Keys live on unit hypersphere; large gradients push off-manifold
2. **Slot scalar clip** (1.0): Learnable log-scales (`_write_log_scale`, `_read_log_scale`) need looser clip
3. **Slot norm clip**: `max_grad_norm × 0.01` as safety net after value clip
4. **Phase attention per-element clip** (0.005): `v_proj`, `W_k_fused`, `W_q_fused` — sin/cos backprop creates amplification cascades
5. **Phase attention norm clip**: `max_grad_norm × 0.05`
6. **Global norm clip**: `max_grad_norm` (typically 1.0) for all remaining parameters
7. **Gradient throttle**: Monitors raw gradient norm and temporarily reduces LR on spikes

### 5.6 Adaptive Training Controller

Monitors PPL velocity and adjusts training dynamics:

- **Slow learning** (velocity < -2%/eval): Boost LR by 1.5×
- **Unstable** (velocity > +10%/eval): Decay LR by 0.7×
- **Plateau** (< 1% improvement over 5 evals): Boost LR
- **Emergency**: Loss spike > 5% or grad norm > 100 → emergency decay 0.5×
- **Boost cooldown**: Minimum 400 steps between boosts to prevent oscillation
- **Max from base**: LR capped at `base_lr × 2.0` to prevent compounding

### 5.7 Adaptive Slot LR Controller

Three-phase proportional control for slot learning rate:

1. **Bootstrap** (Phase 1): Fixed slot LR. Waits for warmup to complete + sufficient signal history.
2. **Adaptive** (Phase 2): `LR_slot(t+1) = LR_slot(t) × e^(η × s)` where `s` is a composite health score from:
   - Write gate mean vs target (weight 0.4)
   - Retrieval loss velocity (weight 0.35)
   - Ablation delta (weight 0.25)
3. **Stabilize** (Phase 3): Freeze slot LR when scale variance drops below threshold.

### 5.8 Sovereign Phase Controller

"Nervous system" for breaking training plateaus. Monitors phase attention health:

- **Graduated response**: Proportional intervention based on entropy + variance
- **Rotation damping**: Smooth phase transitions to prevent gradient spikes
- **Hysteresis**: Entry thresholds (entropy < 0.4) different from exit thresholds (entropy > 0.55) to prevent oscillation
- **Layer-specific targeting**: Surgical interventions based on per-layer diagnostics

### 5.9 Evaluation & Checkpointing

- **Validation**: Full eval every `eval_every` steps on held-out data
- **Slot ablation**: Every 200 steps (independent clock from eval)
- **Best model**: Saved when validation PPL improves
- **Metrics logged**: PPL, alpha_phase, confidence, knowledge score, slot diagnostics, gradient health

---

## 6. GCT (Gated Coherence Transformer)

GCT is an alternative attention mode that dynamically routes between full O(n²) and local O(n·w) attention per head per position:

```
coherence = EMA(‖ΔOutput + ΔResidual‖)     # Stability signal
π = routing_gate(coherence)                  # Route probability
λ = ladder_insulation(band_assignment)       # Prevents all heads routing same way

Training:  output = (1 - π·λ) · O_full + (π·λ) · O_local    # Soft blend
Inference: output = O_local if π·λ > θ else O_full           # Hard route
```

**Three training phases**: (1) Warmup — full attention only, coherence predictors learn. (2) Anneal — soft blend gradually enabled. (3) Full — complete gated operation.

GCT is the attention mechanism inside `GCTTransformerBlock` and can be used instead of the Local+Phase hybrid. The slot memory system works with either.

---

## 7. Inference

### 7.1 Current State

The model uses standard autoregressive generation: forward pass → sample/argmax → append → repeat. No KV cache is implemented for the local attention layers.

### 7.2 Phase State Cache (V10.7)

For O(1) per-step phase attention at inference:

```python
cache = PhaseStateCache(num_layers=12, hybrid_layer_start=4)
# Stores only the final cumulative state per layer
# Each new token: state_{t+1} = γ · state_t + K_{t+1} · V_{t+1}
```

### 7.3 Slot Memory at Inference

Slot memory is naturally inference-ready — slots persist from training. At inference:
- **Read**: Same cosine-similarity lookup against learned slot keys
- **Write**: Can be disabled (slots serve as frozen knowledge store) or enabled for online adaptation

---

## 8. Key Design Principles

1. **Serial dependency, not parallel competition**: Phase → Local (Protected Phase) ensures Phase must learn useful features that Local queries. No gradient tug-of-war.

2. **Detached write path**: Slot writes are detached from the LM loss graph. Only retrieval loss shapes what gets stored. This prevents the main loss from corrupting slot content.

3. **Surgical gradient management**: Different numerical regimes (unit-sphere keys, oscillator phases, standard weights) get different clipping strategies. One-size-fits-all clipping fails here.

4. **Adaptive everything**: LR, alpha blend, slot gate ceiling, retrieval weight, read/write scales — all self-tune based on observed training signals rather than requiring manual hyperparameter sweeps.

5. **Ablation as arbiter**: The slot ablation eval (every 200 steps) is the ground truth for whether slots help. All adaptive slot controls ultimately respond to this signal.

---

## 9. File Reference

| File | What |
|------|------|
| `symbolu/phase_transformer.py` | All model classes: PhaseAttentionLayer, HybridAttentionLayer, LocalAttention, BindingCacheQuadQuery, SlotMemoryGCT, HybridPhaseTransformer, GCTTransformer |
| `symbolu/training/unified/train.py` | Training loop, loss computation, gradient management, eval, logging |
| `symbolu/training/unified/scheduling.py` | AdaptiveWarmupScheduler, PPLAlphaCurriculum |
| `symbolu/training/unified/phase_controllers.py` | SovereignPhaseController, AdaptiveTrainingController, AdaptiveSlotLRController |
| `symbolu/training/unified/losses.py` | Loss computation helpers |
