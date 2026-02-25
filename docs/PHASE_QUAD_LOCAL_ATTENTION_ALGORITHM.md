# Phase-Quad Local Attention Model — Complete Algorithm Specification

**Version**: V11.0 (Binding Cache Architecture)
**Status**: Production — validated by diagnostic probe experiments
**Reference**: `symbolu/phase_transformer.py` (canonical implementation)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Mathematical Foundations](#2-mathematical-foundations)
3. [Path 1 — Phase Attention (O(n) Global Memory)](#3-path-1--phase-attention-on-global-memory)
4. [Path 2 — Quad Proposal (O(n·k) Associative Retrieval)](#4-path-2--quad-proposal-onk-associative-retrieval)
5. [Path 3 — Local Window Attention (O(n·w) Syntax)](#5-path-3--local-window-attention-onw-syntax)
6. [Three-Path Fusion](#6-three-path-fusion)
7. [Feed-Forward Network](#7-feed-forward-network)
8. [Full Forward Pass (Per Block)](#8-full-forward-pass-per-block)
9. [Full Model Architecture](#9-full-model-architecture)
10. [Phase Diversity Regularization](#10-phase-diversity-regularization)
11. [Parallel EMA Scan (Optimized Accumulation)](#11-parallel-ema-scan-optimized-accumulation)
12. [Ontological Control Plane](#12-ontological-control-plane)
13. [Dual-Channel Attention (V10.3.8)](#13-dual-channel-attention-v1038)
14. [Chunk-Persistent State (V10.2)](#14-chunk-persistent-state-v102)
15. [Diagnostic & Health Monitoring](#15-diagnostic--health-monitoring)
16. [Complexity Analysis](#16-complexity-analysis)
17. [Invariants & Contracts](#17-invariants--contracts)
18. [Hyperparameter Reference](#18-hyperparameter-reference)

---

## 1. Architecture Overview

The Phase-Quad Local Attention model is a three-path transformer architecture where each path has an **exclusive, non-competing role**:

```
Input x [B, N, D]
    │
    ├──────────────────── Local Attention ──────────────────── local_out [B, N, D]
    │                      O(n·w) direct token-to-token          │
    │                      syntax / grammar patterns              │
    │                                                             │
    ├──── Phase State ────► memory_state [B, N, D] ──┐            │
    │      O(n) cumsum       global compression       │           │
    │      state accumulator                          │           │
    │                                                 │           │
    │                    Quad Query ◄──────────────────┘           │
    │                      O(n·k) Top-K retrieval                 │
    │                      queries memory_state ──── mem_out [B, N, D]
    │                                                             │
    │                                          ┌──────────────────┘
    │                                          │
    └───────── x + (local_out + mem_out) ──────┘
                         │
                    Feed-Forward
                         │
                      output
```

**Critical Design Principle** (validated by probe experiments):
- Phase and Quad must have **non-competing roles**
- When mixed (sharing Q/K/V), Phase becomes **decorative** (~0% ablation drop)
- When protected (exclusive roles), Phase is **essential** (-50% to -54% ablation drop)
- Phase **writes** to memory state (accumulator)
- Quad **reads** from memory state (querier)
- Local provides **uncompressed** token-level detail

---

## 2. Mathematical Foundations

### 2.1 Core Innovation: Phase Synchronization

Traditional attention:
```
Attn(Q, K, V) = softmax(QK^T / √d) · V         [O(n²)]
```

Phase attention replaces the QK^T dot-product with a phase-amplitude interaction:
```
Attn(i, j) = aᵢ · aⱼ · cos(φᵢ − φⱼ)            [O(n)]
```

where:
- `φᵢ, φⱼ` are **learned phases** (angles on the unit circle)
- `aᵢ, aⱼ` are **learned amplitudes** (non-negative gates)
- `cos(φᵢ − φⱼ)` is the **selectivity kernel** (high when phases align)

### 2.2 Euler's Formula Implementation

The cos(φ_q − φ_k) interaction is computed via complex phasors:

```
e^(iφ) = cos(φ) + i·sin(φ)

cos(φ_q − φ_k) = Re(e^(iφ_q) · e^(-iφ_k))
```

Implemented as:
```
Q_phasor = a_q · exp(i · φ_q)          # Query phasor
K_phasor = a_k · exp(-i · φ_k)         # Key phasor (conjugate)
KV       = K_phasor · V_complex         # Key-Value product
State_t  = Σ_{j≤t} KV_j               # O(n) causal cumsum
Out      = Re(Q_phasor · State_t) / Z  # Readout with normalization
```

### 2.3 Mean-Field Approximation

The O(n) complexity arises from the Kuramoto mean-field approximation:

```
Σⱼ sin(φᵢ − φⱼ) ≈ N · sin(φᵢ − φ_mean)
```

Instead of computing all O(n²) pairwise interactions, we accumulate into a global state and query it.

---

## 3. Path 1 — Phase Attention (O(n) Global Memory)

**Class**: `BindingCachePhaseState`
**File**: `symbolu/phase_transformer.py:2601`
**Role**: Accumulate key-value pairs into a persistent memory state

### 3.1 Algorithm

```
INPUT:  x [B, N, D], optional intent_phase [B, H] or [B, H, D_h]
OUTPUT: memory_state [B, N, D]

1. NORMALIZE:
   x_norm = LayerNorm(x)

2. PROJECT PHASE & AMPLITUDE (Key-side only):
   φ_k_raw = W_k_phase(x_norm)  →  reshape to [B, N, H, D_h]
   a_k     = σ(W_k_amp(x_norm)) →  reshape to [B, N, H, D_h]

3. BOUNDED PHASE PARAMETRIZATION:
   φ_k = π · sin(φ_k_raw)       # Constrains to [-π, π] on S¹ manifold

4. APPLY PER-HEAD PHASE OFFSETS (fixed at init):
   φ_k = φ_k + offset_k[h]     # offset_k[h] = 2πh/H for h ∈ [0, H-1]

5. OPTIONAL INTENT ROTATION:
   if intent_phase is not None:
       φ_k = φ_k + θ_SRK       # SRK (Master) rotates storage phase

6. PROJECT VALUES:
   v = W_v(x_norm) → reshape to [B, N, H, D_h]

7. FORM COMPLEX PHASORS:
   k_phasor = polar(a_k, −φ_k)     # [B, N, H, D_h] complex
   v_complex = complex(v, 0)         # Real-only complex wrapper

8. ACCUMULATE STATE (causal, O(n)):
   kv = k_phasor ⊙ v_complex         # Element-wise product

   if decay_γ == 1.0:
       memory_state = cumsum(kv, dim=1)    # Infinite memory
   else:
       memory_state = EMA_scan(kv, γ)      # Exponential decay
       # S_t = γ · S_{t-1} + kv_t
       # Effective memory ≈ 1/(1−γ) tokens

9. PROJECT TO REAL OUTPUT:
   memory_state_real = Re(memory_state) → reshape to [B, N, D]

RETURN memory_state_real
```

### 3.2 Decay Options

| Mode | Formula | Memory Horizon | Use Case |
|------|---------|---------------|----------|
| `γ = 1.0` (default) | `S_t = S_{t-1} + kv_t` | Infinite | Long-range dependencies |
| `γ = 0.95` (fixed) | `S_t = 0.95·S_{t-1} + kv_t` | ~20 tokens | Local grammar focus |
| `learned_decay=True` | `γ_h = 0.5 + 0.5·σ(logit_h)` | 2–2048 per head | Adaptive (Mamba/S4-style) |

Learned decay initialization (log-space timescale):
```
timescale_h = exp(linspace(ln(2), ln(2048), H))
γ_h = 1 − 1/timescale_h
logit_h = logit(2·γ_h − 1)    # Inverse sigmoid for initialization
```

### 3.3 Phase Spread Initialization

Each head gets a unique rotational offset to **shatter phase collapse** at initialization:
```
offset_h = 2π · h / H    for h = 0, 1, ..., H-1
```

These are **fixed** (non-learnable) buffers that diversify the phase manifold each head explores.

---

## 4. Path 2 — Quad Proposal (O(n·k) Associative Retrieval)

**Class**: `BindingCacheQuadQuery`
**File**: `symbolu/phase_transformer.py:2891`
**Role**: Query Phase's memory state via Top-K cache retrieval

### 4.1 Standard Mode Algorithm

```
INPUT:  x [B, N, D], memory_state [B, N, D],
        optional binding_salience [B, N]
OUTPUT: mem_out [B, N, D]

1. NORMALIZE INPUTS:
   x_norm   = LayerNorm_q(x)
   mem_norm = LayerNorm_mem(memory_state)

2. PROJECT Q/K/V:
   Q = W_q(x_norm)       → [B, H, N, D_h]    # From input ("what am I looking for?")
   K = W_k(mem_norm)     → [B, H, N, D_h]    # From memory ("what can I retrieve?")
   V = W_v(mem_norm)     → [B, H, N, D_h]    # From memory (content)

3. COMPUTE SCORES:
   scores = (Q · K^T) / √D_h    → [B, H, N, N]

4. APPLY CAUSAL MASK:
   scores[i, j] = −∞  where j > i

5. TOP-K SELECTION (reduces O(n²) to O(n·k)):
   if binding_salience provided:
       selection_scores = scores + salience[B, 1, 1, N]    # Bias selection
   else:
       selection_scores = scores

   top_indices = topk(selection_scores, k=K, dim=-1)       # [B, H, N, k]
   top_scores  = gather(scores, top_indices)                 # ORIGINAL scores (unbiased)

   NOTE: Salience affects WHICH positions are selected,
         NOT HOW they are weighted (pure attention math preserved)

6. ATTENTION OVER TOP-K:
   attn = softmax(top_scores, dim=-1)    # [B, H, N, k]
   attn = dropout(attn)

7. GATHER AND WEIGHT VALUES:
   top_V = gather(V, top_indices)         # [B, H, N, k, D_h]
   out = einsum('bhqk,bhqkd→bhqd', attn, top_V)

8. OUTPUT PROJECTION:
   mem_out = W_out(reshape(out)) → [B, N, D]

RETURN mem_out
```

### 4.2 Proposal Mode (V10.4)

In proposal mode, Quad acts as a **proposer** and Phase acts as an **integrator**:

```
1. Generate proposals (no softmax):
   proposals [B, N, K, D], scores [B, N, K] = quad.get_proposals(x, memory_state)

2. Optional interference-aware rescoring (V10.5)

3. Phase integrates proposals:
   mem_out = phase.integrate_proposals(x, memory_state, proposals, scores)
```

Conditional skip optimization:
```
confidence = phase.compute_confidence(memory_state)
if confidence > threshold:
    skip quad entirely (Phase alone is sufficient)
```

### 4.3 Cache Health Metrics

| Metric | Healthy | Unhealthy | Action |
|--------|---------|-----------|--------|
| `cache_hit_rate` | `k/N` | — | Informational |
| `cache_key_cosine_mean` | < 0.85 | ≥ 0.85 | Redundancy building |
| `cache_key_cosine_max` | < 0.95 | ≥ 0.95 | Slot collision |

---

## 5. Path 3 — Local Window Attention (O(n·w) Syntax)

**Class**: `LocalWindowAttention`
**File**: `symbolu/phase_transformer.py:3162`
**Role**: Direct token-to-token attention within a sliding window

### 5.1 Algorithm

```
INPUT:  x [B, N, D]
OUTPUT: local_out [B, N, D]

1. DYNAMIC WINDOW SIZE:
   W = min(window_size, max(1, N // 2))
   # Ensures local attention stays local for long sequences
   # while covering half the sequence for short ones

2. NORMALIZE:
   x_norm = LayerNorm(x)

3. PROJECT Q/K/V:
   Q = W_q(x_norm) → [B, H, N, D_h]
   K = W_k(x_norm) → [B, H, N, D_h]
   V = W_v(x_norm) → [B, H, N, D_h]

4. COMPUTE SCORES:
   scores = (Q · K^T) / √D_h   → [B, H, N, N]

5. CREATE WINDOWED CAUSAL MASK:
   For position i, j:
     MASK(i, j) = TRUE  if j > i           (future: causal)
                  TRUE  if (i − j) ≥ W     (too far in past: window)
                  FALSE otherwise           (attend)

   scores = masked_fill(scores, MASK, −∞)

6. SOFTMAX AND ATTEND:
   attn = softmax(scores, dim=-1)
   attn = dropout(attn)
   out = attn · V    → [B, H, N, D_h]

7. OUTPUT PROJECTION:
   local_out = W_out(reshape(out)) → [B, N, D]

RETURN local_out
```

### 5.2 Backend Selection (Full LocalAttention — V10.2.2)

The full `LocalAttention` class (line 4535) supports multiple backends:

| Backend | Implementation | Complexity | Requirements |
|---------|---------------|------------|--------------|
| `flash` | FlashAttention sliding window | O(n·w) kernel-level | `flash-attn` package |
| `sdpa` | PyTorch 2.0 SDPA | O(n·w) with mask | PyTorch ≥ 2.0 |
| `unfold` | Manual unfold (chunked) | O(n·w) true | Always available |

GQA (Grouped Query Attention) support:
- `n_kv_heads = num_heads`: Standard MHA
- `n_kv_heads < num_heads`: GQA (e.g., 8 KV heads for 32 Q heads)
- `n_kv_heads = 1`: Multi-Query Attention (MQA)

---

## 6. Three-Path Fusion

### 6.1 Binding Cache Block (Protected Architecture)

```
attn_out = local_out + mem_out     # Additive combination
x = x + attn_out                   # Residual connection
```

Key design: **no gating** between paths — each path contributes its exclusive signal.

### 6.2 Why Not Gated Fusion?

Empirical finding from diagnostic probes:
- **Additive**: Phase maintains -50% ablation sensitivity (ESSENTIAL)
- **Competing/gated**: Phase drops to ~0% sensitivity (DECORATIVE)

The three paths are complementary, not alternatives:
- **Local**: "the → cat" (syntax, high-frequency)
- **Phase**: Compressed memory of entire past (global, O(n))
- **Quad**: Precise retrieval from that memory (targeted, O(n·k))

---

## 7. Feed-Forward Network

Standard pre-norm FFN with GELU activation:

```
INPUT:  x [B, N, D]
OUTPUT: x + FFN(LayerNorm(x))

FFN(x) = dropout(W₂(GELU(W₁(LayerNorm(x))))) + x
    W₁: D → 4D    (expansion)
    W₂: 4D → D    (projection)
```

---

## 8. Full Forward Pass (Per Block)

**Class**: `BindingCacheBlock`
**File**: `symbolu/phase_transformer.py:3249`

```
ALGORITHM: BindingCacheBlock.forward(x, intent_phase, binding_salience, enable_slots_read)

1. VALIDATE CONTROL SIGNALS (V10.6.6):
   assert_control_shape(intent_phase)       # Must be [B, H] or [B, H, D_h]
   assert_control_shape(binding_salience)    # Must be [B, N] (per-position)

2. LOCAL ATTENTION (always active):
   local_out = local_attn(x)                # O(n·w) syntax

3. PHASE WRITE (always active — deterministic EQ_TOKEN pattern):
   memory_state = phase_state(x, intent_phase)   # O(n) accumulation

4. QUAD READ (conditionally gated by enable_slots_read):
   if not enable_slots_read:
       attn_out = local_out                  # Skip retrieval
   elif proposal_mode:
       confidence = phase.compute_confidence(memory_state)
       proposals, scores = quad.get_proposals(x, memory_state, binding_salience)
       mem_out = phase.integrate_proposals(x, memory_state, proposals, scores)
       attn_out = local_out + mem_out
   else:
       mem_out = quad_query(x, memory_state, binding_salience)  # O(n·k)
       attn_out = local_out + mem_out

5. RESIDUAL + FFN:
   x = x + attn_out
   x = x + FFN(LayerNorm(x))

RETURN x
```

---

## 9. Full Model Architecture

**Class**: `BindingCacheTransformer`
**File**: `symbolu/phase_transformer.py:3489`

```
ALGORITHM: BindingCacheTransformer.forward(input_ids, labels, intent_phase, binding_salience)

1. EMBEDDINGS:
   pos = arange(N)
   x = dropout(token_embed(input_ids) + pos_embed(pos))

2. TRANSFORMER BLOCKS (× L layers):
   for block in blocks:
       x = block(x, intent_phase, binding_salience, enable_slots_read)

3. OUTPUT:
   hidden = LayerNorm(x)
   logits = lm_head(hidden) × logit_scale

   logit_scale = 1 / √(√D)    # Milder than 1/√D to prevent overconfident early logits

4. OPTIONAL LOSS:
   if labels provided:
       loss = cross_entropy(logits[:, :-1], labels[:, 1:])

RETURN logits, loss
```

### 9.1 Weight Initialization

```
Linear weights:  N(0, 0.02)
Embedding weights: N(0, 0.02)
Phase projection weights: U(−π, π)     # Uniform for gradient diversity
Phase offsets: 2πh/H                    # Fixed, non-learnable
Decay logits: logit(2γ − 1)            # Log-space timescale init
```

### 9.2 Embedding Tying

When `tie_embeddings=True`:
```
lm_head.weight = token_embed.weight    # Shared parameters
```

When `tie_embeddings=False` (e.g., Sanskrit/CSR injection):
```
lm_head.weight ← copy(token_embed.weight)   # Initial alignment, then diverge
```

---

## 10. Phase Diversity Regularization

### 10.1 Problem: Phase Collapse

Without regularization, phases collapse to `cos(φ_q − φ_k) ≈ 1` everywhere, turning phase attention into a scalar gain with no selectivity.

### 10.2 Uniformity Loss

Two-stage pooling (correct formulation):

```
Step 1: Pool over D_h to get per-head phasor
   z[b,n,h] = mean_d exp(i · φ[b,n,h,d])

Step 2: Pool over samples
   L_uniform = |mean_{b,n} z[b,n,h]|²

If phases uniform → E[e^{iφ}] ≈ 0 → loss small
If phases collapsed → |E[e^{iφ}]| large → loss large
```

### 10.3 Entropy Proxy (Mean Resultant Length)

```
R = |E[z]| where z = mean_d exp(i·φ)

R → 0: Uniform distribution (high entropy, healthy)
R → 1: Collapsed distribution (low entropy, unhealthy)
```

### 10.4 Combined Training Loss

```
L_diversity = λ_uniform · L_uniform + λ_entropy · R

Recommended schedule:
   Start:  λ = 0.001  (gentle regularization)
   Ramp:   λ → 0.01   (over training)
```

### 10.5 Phase Capture Protocol

```python
# Enable capture before forward pass
enable_phase_diversity_capture(model, True)

# Forward pass (captures φ_k tensors)
output = model(input_ids)

# Compute diversity loss
diversity_loss, metrics = compute_model_phase_diversity_loss(model)

# Add to training loss
total_loss = lm_loss + diversity_loss

# Disable capture after use
enable_phase_diversity_capture(model, False)
```

---

## 11. Parallel EMA Scan (Optimized Accumulation)

**Function**: `parallel_ema_scan`
**File**: `symbolu/phase_transformer.py:695`

Computes `S_t = γ · S_{t-1} + x_t` in O(N/chunk_size) loop iterations instead of O(N).

### 11.1 Algorithm

```
INPUT:  x [B, N, H, D], γ (scalar or [H]), chunk_size=64
OUTPUT: S [B, N, H, D]

1. SAFETY CHECK:
   if min(γ) < 0.9:
       use SEQUENTIAL path (stable but slow)
   else:
       use VECTORIZED path (fast, 32× fewer iterations)

VECTORIZED PATH (when γ ≥ 0.9):

2. PRECOMPUTE POWERS:
   powers[t] = γ^t  for t ∈ [0, chunk_size)

3. FOR EACH CHUNK c:
   x_chunk = x[:, c·C : (c+1)·C]     # [B, C, H, D]

   # Contribution from previous state:
   state_powers[t] = γ^(t+1)          # [C]
   state_contrib = state × state_powers

   # Contribution from chunk inputs:
   # S[i] = γ^(i+1) · S_prev + Σ_{j=0}^{i} γ^(i−j) · x[j]
   x_scaled = x_chunk × γ^(−t)        # Rescale inputs
   x_cumsum = cumsum(x_scaled, dim=1)  # Prefix sums
   input_contrib = x_cumsum × γ^t     # Scale back

   S[c·C : (c+1)·C] = state_contrib + input_contrib
   state = S[(c+1)·C − 1]             # Carry forward

4. RETURN S
```

### 11.2 Numerical Stability

```
For γ = 0.5, t = 63: γ^(-63) = 2^63 ≈ 9.2×10^18   (OVERFLOW)
For γ = 0.9, t = 63: γ^(-63) ≈ 1.7×10^4            (SAFE)

Threshold: SAFE_GAMMA_THRESHOLD = 0.9
Below threshold → sequential loop (correct but slow)
Above threshold → vectorized path (fast, stable)
```

---

## 12. Ontological Control Plane

### 12.1 OntoControl Interface (V10.6.4)

```
OntoControl {
    binding_salience: [B, N]         # Per-position gating for Top-K selection
    intent_phase: [B, H] or [B, H, D_h]   # Phase rotation
    enable_slots_read: bool          # Gate retrieval without affecting storage
    source: str                      # "ontology", "csr", "kosha", etc.
}
```

### 12.2 Binding Salience Flow

```
OntologicalBindingAnnotator:
   hidden_states [B, N, D] ──┐
   sovereign_state [B, 32] ──┤──► salience [B, N]
   kosha_activations [B, 5] ─┤      │
   csr_mask [B, N] ──────────┘      │
                                     ▼
                        BindingCacheQuadQuery
                        (biases Top-K selection
                         without modifying attention math)
```

### 12.3 No-Write Contract (V10.6.2)

Control signals must satisfy:

| Signal | Valid Shapes | Invalid Shapes |
|--------|-------------|---------------|
| `intent_phase` | `[B, H]`, `[B, H, D_h]`, `[H]`, `[]` | `[B, N, D]`, `[B, N]` |
| `binding_salience` | `[B, N]` (special case) | `[B, N, D]` |
| `s_align` (alignment) | `[H]`, `[]`, `[B, H]` | `[B, N]` (leaks structure) |

**Invariant**: Control signals must be low-dimensional and broadcastable. They must **never** contain `d_model` or vary across token positions (except `binding_salience`).

---

## 13. Dual-Channel Attention (V10.3.8)

### 13.1 Problem

Legacy mode collapses content and intent into a single cosine:
```
score = cos(φ_q + θ_intent − φ_k)
```
Risk: Intent can dominate, destroying content selectivity.

### 13.2 Solution: Separate Channels

```
s_content = cos(φ_q − φ_k)                    # What matches (content)
s_align   = cos(θ_JEPA − θ_SRK)               # Are we aligned (intent)
score     = s_content · (1 + α · s_align)      # Modulated combination
```

Where:
- `θ_JEPA` = Sensor prediction (Query side: "What am I looking for?")
- `θ_SRK` = Master understanding (Key side: "What do I understand?")
- `α` = alignment authority (default 0.1, controls intent influence)

### 13.3 Natural Separation in Protected Architecture

The Binding Cache architecture **already** implements dual-channel naturally:
- `BindingCachePhaseState` handles Key phasor (backward, `-iφ_k`) → **SRK influences storage**
- `BindingCacheQuadQuery` handles Query projection (forward) → **JEPA influences retrieval**

---

## 14. Chunk-Persistent State (V10.2)

### 14.1 Problem

Without state persistence across chunks, Phase resets at chunk boundaries and becomes decorative (no long-range temporal memory).

### 14.2 Algorithm

```
CHUNK PROCESSING:

for chunk_idx in range(num_chunks):
    chunk = sequence[chunk_idx * C : (chunk_idx + 1) * C]

    if chunk_idx == 0:
        prev_state = None
        prev_norm_state = None
    else:
        prev_state = final_state          # From previous chunk
        prev_norm_state = final_norm_state

    output, state_dict = phase_attn(
        chunk,
        prev_state=prev_state,
        prev_norm_state=prev_norm_state,
        return_state=True,
    )

    final_state = state_dict['final_state']           # [B, 1, H, D_h] complex
    final_norm_state = state_dict['final_norm_state']  # [B, 1, H, D_h] real
    memory_state = state_dict['memory_state']          # [B, N, H, D_h] for Local cross-attn
```

### 14.3 State Continuation Math

For cumsum (γ = 1.0):
```
global_state_t = prev_state + Σ_{j≤t} KV_j
```

For EMA (γ < 1.0):
```
global_state_t = γ^(t+1) · prev_state + Σ_{j≤t} γ^(t-j) · KV_j
```

**Critical**: Do NOT detach `prev_state` — gradients must flow through time.

---

## 15. Diagnostic & Health Monitoring

### 15.1 Health Dashboard (V9.9.12c)

Read-only diagnostics with no effect on training:

| Metric | Formula | Healthy Range | Meaning |
|--------|---------|--------------|---------|
| `R_k` | `\|mean_{b,n} z_k\|` where `z_k = mean_d exp(iφ_k)` | 0.0 – 0.3 | Key phase collapse (0 = uniform) |
| `R_q` | Same for query phases | 0.0 – 0.3 | Query phase collapse |
| `amp_phase_corr` | Pearson(`\|z\|`, `a_k`) | < 0.5 | Amplitude compensating for collapse |
| `head_redundancy` | Mean pairwise cosine of per-head z̄ | < 0.5 | Heads converged to same manifold |
| `phase_drift_mean` | `mean(\|Δφ_k(t)\|)` | 0.01 – 0.5 | Small but non-zero = using phase as state |
| `phase_drift_std` | `std(\|Δφ_k(t)\|)` | < 2× mean | Stable dynamics |

### 15.2 Phase Health Protocol

```python
# Enable capture (no gradients, read-only)
enable_health_diagnostics_capture(model, True)

# Forward pass
output = model(input_ids)

# Compute health metrics
health = compute_phase_health_dashboard(model)
# Returns: R_k, R_q, amp_phase_corr, head_redundancy, phase_drift_*

# Disable capture
enable_health_diagnostics_capture(model, False)
```

---

## 16. Complexity Analysis

### 16.1 Per-Layer Complexity

| Path | Time | Space | Description |
|------|------|-------|-------------|
| Phase | O(n · D) | O(n · H · D_h) | Complex cumsum/EMA |
| Quad (Top-K) | O(n · k · D_h) | O(n · k · D_h) | Top-K cache retrieval |
| Quad (Full) | O(n² · D_h) | O(n² · H) | Full attention fallback |
| Local | O(n · w · D_h) | O(n · w) | Sliding window |
| FFN | O(n · D · D_ff) | O(n · D_ff) | Standard FFN |

### 16.2 Total Complexity

```
Combined per-layer: O(n · (D + k·D_h + w·D_h + D·D_ff))

Typical values:
   D = 768, H = 12, D_h = 64, k = 64, w = 256, D_ff = 3072

Phase:  O(n · 768)           ≈ O(768n)
Quad:   O(n · 64 · 64)       ≈ O(4,096n)
Local:  O(n · 256 · 64)      ≈ O(16,384n)
FFN:    O(n · 768 · 3072)    ≈ O(2,359,296n)

Total: O(n · ~2.4M)  vs  standard transformer: O(n² · D + n · D · D_ff)
```

For n > ~3,000 tokens, Phase-Quad-Local is cheaper than standard attention.

### 16.3 Memory Comparison

| Component | Standard | Phase-Quad-Local |
|-----------|----------|-----------------|
| Attention maps | O(n² · H) | O(n · k · H) |
| KV cache (inference) | O(n · H · D_h) | O(H · D_h) (Phase state) |
| Peak memory | O(n²) | O(n · max(k, w)) |

---

## 17. Invariants & Contracts

### 17.1 Architectural Invariants

```
INV-1:  Phase writes ONLY to memory_state (no attention output)
INV-2:  Quad reads ONLY from memory_state (no direct token access)
INV-3:  Local has NO access to memory_state (direct token-to-token only)
INV-4:  Control signals are low-dimensional (no d_model dimension)
INV-5:  Binding salience biases selection, NOT attention weights
INV-6:  Phase WRITE is always active (deterministic EQ_TOKEN pattern)
INV-7:  Phase state MUST persist across chunks for temporal continuity
INV-8:  Gradients MUST flow through prev_state (no detach)
```

### 17.2 Version Contracts

| Contract | Version | Enforcement |
|----------|---------|-------------|
| No-write control shape | V10.6.2 | `assert_control_shape()` — hard-fail |
| Alignment signal shape | V10.6.3 | `assert_alignment_signal_shape()` — hard-fail |
| OntoControl interface | V10.6.4 | `OntoControl.validate()` |
| Forward-pass enforcement | V10.6.6 | Block and Transformer level |

---

## 18. Hyperparameter Reference

### 18.1 Model Dimensions

| Parameter | Small | Medium | Large | 7B |
|-----------|-------|--------|-------|-----|
| `embed_dim` | 768 | 1024 | 2048 | 4096 |
| `num_heads` | 12 | 16 | 32 | 32 |
| `num_layers` | 12 | 24 | 24 | 32 |
| `ff_dim` | 3072 | 4096 | 8192 | 11008 |
| `max_seq_len` | 8192 | 8192 | 8192 | 8192 |

### 18.2 Phase Attention

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `decay_gamma` | 1.0 | (0, 1] | 1.0 = infinite memory |
| `learned_decay` | False | bool | Per-head Mamba/S4-style |
| `bounded_phase` | True | bool | **Mandatory** for stability |
| `cosine_mode` | "standard" | standard/shifted/complex | "shifted" if training plateaus |

### 18.3 Quad Query

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `top_k` | 64 | [16, 256] | Per-head cache size |
| `use_cache` | True | bool | False = full O(n²) |
| `proposal_mode` | False | bool | V10.4: Quad proposes, Phase integrates |
| `confidence_threshold` | 0.7 | [0, 1] | Skip quad when confident |

### 18.4 Local Attention

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `local_window_size` | 256 | [64, 1024] | Actual = min(this, N//2) |
| `backend` | "auto" | auto/flash/sdpa/unfold | FlashAttention preferred |
| `n_kv_heads` | num_heads | [1, num_heads] | GQA support |

### 18.5 Training

| Parameter | Default | Notes |
|-----------|---------|-------|
| `dropout` | 0.1 | Throughout model |
| `logit_scale` | 1/√(√D) | Milder than 1/√D |
| `λ_uniform` | 0.001 | Phase uniformity loss |
| `λ_entropy` | 0.001 | Phase entropy proxy loss |
| `tie_embeddings` | True | False for Sanskrit/CSR |

---

## Appendix A: 32D Sovereign State Mapping

The Sovereign State is a principled 32-dimensional vector organized into three planes:

```
PHASE PLANE (12D → phase rotation):
  [0:12]   12 Bhavas — WHAT mode of being
           POT, IDN, EXE, STR, COG, AGY, RSN, PRP, WIT, UNI, INT, ABS

CONTROL PLANE (16D → CTM+/Sentinel/Governor):
  [12:17]  5 Koshas — HOW DEEP to process
           Material, Vital, Mental, Intellectual, Blissful
  [17:22]  5 Vrittis — HOW RELIABLE is this
           Fact, Error, Imagination, Void, Memory
  [22:28]  6 Gunas/Dynamics — WHAT ENERGY dynamics
           Lucidity, Activity, Stability, Velocity, Accel, Stable

LEARNING PLANE (4D → training-time feedback):
  [28:32]  4 Reserved — scratch/JEPA/toroidal feedback
```

**Critical separation (V11.0)**: Only Bhavas touch phase rotation. Koshas/Vrittis/Gunas are control/learning signals routed to CTM+/Governor, **not** to the phase attention kernel.

---

## Appendix B: Cosine Mode Comparison

| Mode | Range | Formula | Pros | Cons |
|------|-------|---------|------|------|
| `standard` | [-1, +1] | cos(φ_q − φ_k) | Original, symmetric | Destructive interference |
| `shifted` | [0, 2] | 1 + cos(φ_q − φ_k) | Positive signal, no cancellation | Less selective |
| `complex` | ℂ → ℝ | W·[Re, Im]^T | Asymmetric ("the→cat" ≠ "cat→the") | +memory, extra projection |

---

## Appendix C: Comparison with Other Architectures

| Feature | Standard Transformer | Mamba/S4 | RWKV | Phase-Quad-Local |
|---------|---------------------|----------|------|-----------------|
| Global attention | O(n²) softmax | O(n) SSM | O(n) linear | O(n) phase cumsum |
| Local syntax | Implicit | Implicit | Implicit | **Explicit** O(n·w) window |
| Associative retrieval | Implicit | None | None | **Explicit** O(n·k) Top-K |
| State persistence | KV cache | Recurrent state | Recurrent state | Complex phasor state |
| Selectivity mechanism | Softmax | Selection gates | Token shift | cos(φ_q − φ_k) phase sync |
| Per-head memory span | All same | Learned | Learned decay | Learned (2–2048 tokens) |
| Interpretability | Attention maps | Opaque | Opaque | Phase angles, R_k metrics |

---

*Document generated from codebase analysis of `symbolu/phase_transformer.py` (7,696 lines),
`symbolu/hp_quad.py`, `symbolu/reflective_phase_quad.py`, and `symbolu/rlm_phase_quad.py`.*
