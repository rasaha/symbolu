# Gated Coherence Transformer (GCT) — Design Specification

**Version:** 1.0
**Date:** March 2026
**Status:** Implemented (v1, no lambda_mirror)
**Files:** `symbolu/phase_transformer.py`, `train_unified_llm_clean.py`

---

## 1. Overview

GCT (Gated Coherence Transformer) augments standard O(n²) softmax attention with
**pre-softmax coherence gating** and **lambda_ladder band insulation**, routing each
head at each position between full attention and local-window attention based on
temporal stability signals.

### Core Contribution

> Pre-softmax temporal stability routing that does NOT require computing QK^T to decide.

The routing decision uses only **output deltas** and **residual deltas** from the
current layer — no attention matrices needed. This preserves FlashAttention/SDPA
compatibility on the full attention path.

### Architecture Summary

```
Input tokens → Embedding → [GCT Block × L] → LM Head → Logits

Each GCT Block:
  x → QKV Projection → Full Attention (O(n²), SDPA/Flash)  → O_full
                      → Local Window Attention (O(n·w))     → O_local
                      → Coherence Score → Routing Gate (π)
                      → Lambda_ladder (Λ)
                      → Blend: O = (1 - π·Λ)·O_full + (π·Λ)·O_local
                      → Output Projection → LayerNorm(residual + output)
  x → FeedForward → x_out
```

---

## 2. Algorithmic Specification

### 2.1 Full Attention (Baseline)

Standard O(n²) causal softmax attention, using SDPA/FlashAttention when available:

```
O_full[ℓ,h,t] = Softmax(Q[ℓ,h,t] · K[ℓ,h,1:t]^T / √d + M) · V[ℓ,h,1:t]
```

### 2.2 Local-Window Attention (Coarse Path)

Same softmax primitive, but over a sliding window of size `w`:

```
W(t) = {max(1, t-w+1), ..., t}

O_local[ℓ,h,t] = Softmax(Q[ℓ,h,t] · K[ℓ,h,W(t)]^T / √d + M_W) · V[ℓ,h,W(t)]
```

Compute: O(n·w) per layer instead of O(n²). Both paths share the same QKV projections.

### 2.3 Coherence Score (FlashAttention-Compatible)

No attention KL divergence — uses only output and residual deltas:

```
ΔO_rel(t) = ||O(t) - O(t-1)|| / (||O(t-1)|| + ε)     [per head]
ΔR_rel(t) = ||R(t) - R(t-1)|| / (||R(t-1)|| + ε)     [shared across heads]

C_raw(t) = exp(-γ · ΔO_rel(t)) · exp(-δ · ΔR_rel(t))   ∈ (0, 1]
```

EMA smoothing (causal):
```
Ĉ(t) = β · Ĉ(t-1) + (1 - β) · C_raw(t)
```

Bootstrap: `Ĉ(0) = 0.5` (neutral).

**Why no attention KL:** Computing attention KL requires materializing the full
attention matrix, which breaks FlashAttention. Output deltas and residual deltas
are sufficient stability signals and are always available.

### 2.4 Routing Gate (Pre-Softmax)

```
π[ℓ,h,t] = σ(α_b · (Ĉ[ℓ,h,t] - τ[b,h]))
```

Where:
- `b` = frequency band of head `h` (equal partition: global/mid/local)
- `τ[b,h]` = per-band learnable threshold
- `α_b` = per-band learnable sharpness

**Band assignment:** Equal partition of H heads into `num_bands` groups.
- Band 0 (global): `τ` initialized high (0.7) — rarely routes to local
- Band K (local): `τ` initialized low (0.3) — often routes to local

**Semantics:** High coherence (stable region) → high π → route to local (save compute).
Low coherence (unstable region) → low π → use full attention (be careful).

### 2.5 Lambda_Ladder Band Insulation (Corrected Sign)

Prevents band collapse: when heads in different bands produce too-similar outputs,
force full attention to preserve band specialization.

```
Δ_band[ℓ,t] = 1 - mean_{b1≠b2} cos_sim(mean_{h∈b1}(O_h), mean_{h∈b2}(O_h))
```

**Corrected sign logic** (low divergence = collapse risk):
```
Λ[ℓ,t] = exp(-κ · max(0, τ_collapse - Δ_band[ℓ,t]))    ∈ (0, 1]
```

- When `Δ_band < τ_collapse` (bands too similar): `Λ ↓` → more full attention
- When `Δ_band ≥ τ_collapse` (bands well-separated): `Λ = 1` → no suppression

### 2.6 Effective Routing

```
π*[ℓ,h,t] = π[ℓ,h,t] · Λ[ℓ,t]
```

### 2.7 Final Blended Output

**Training (soft blend):**
```
O[ℓ,h,t] = (1 - π*[ℓ,h,t]) · O_full[ℓ,h,t] + π*[ℓ,h,t] · O_local[ℓ,h,t]
```

**Inference (hard route):**
```
O[ℓ,h,t] = O_local  if π* > θ
            O_full   otherwise
```

### 2.8 Compact Form

```
O = (1 - π·Λ) · Softmax(QK^T_{1:t}/√d + M) · V_{1:t}
  + (π·Λ)     · Softmax(QK^T_{W(t)}/√d + M) · V_{W(t)}

where π = σ(α_b · (Ĉ - τ_b))
  and Λ = exp(-κ · max(0, τ_collapse - Δ_band))
```

---

## 3. Phased Training Schedule

To avoid doubling FLOP cost for the entire training run:

| Phase | Steps | Behavior | Cost |
|-------|-------|----------|------|
| **Phase 1: Warmup** | `[0, gct_warmup_steps)` | Full attention only. Coherence predictors observe but don't route. | 1× baseline |
| **Phase 2: Anneal** | `[warmup, warmup + anneal)` | π* linearly scaled by schedule weight (0→1). Soft blend gradually engaged. | 1× → 2× |
| **Phase 3: Full** | `[warmup + anneal, ∞)` | Full gated operation. Both paths computed, routing fully active. | ~2× attention |

The schedule weight multiplies π* directly:
```
π*_effective = π* · schedule_weight(step)
```

---

## 4. Default Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `gct_window_size` | 128 | Local window size (code: 128, prose: 256) |
| `gct_coherence_gamma` | 5.0 | Output delta sensitivity |
| `gct_coherence_delta` | 3.0 | Residual delta sensitivity |
| `gct_ema_decay` | 0.9 | EMA smoothing for coherence scores |
| `gct_num_bands` | 3 | Frequency bands (global/mid/local) |
| `gct_alpha_sharpness` | 10.0 | Sigmoid sharpness for routing |
| `gct_hard_route_threshold` | 0.5 | θ for hard routing (inference) |
| `gct_kappa` | 3.0 | λ_ladder suppression strength |
| `gct_tau_ladder` | 0.15 | Collapse detection threshold |
| `gct_warmup_steps` | 500 | Phase 1 duration |
| `gct_anneal_steps` | 2000 | Phase 2 duration |

---

## 5. Implementation Classes

All in `symbolu/phase_transformer.py`:

| Class | Purpose |
|-------|---------|
| `GCTConfig` | Dataclass with all GCT hyperparameters |
| `GCTCoherenceModule` | Computes coherence from output/residual deltas |
| `GCTRoutingGate` | Pre-softmax routing: σ(α(Ĉ - τ)) with band assignment |
| `GCTLadderInsulation` | Lambda_ladder: band collapse prevention |
| `GCTAttentionLayer` | Full attention + local attention + gating + blend |
| `GCTTransformerBlock` | GCTAttentionLayer + FeedForward |
| `GCTTransformer` | Full model: Embeddings + GCTBlocks + LM Head |

### Training Script Integration (`train_unified_llm_clean.py`)

- `model_type="gct"` in argparser choices
- `UnifiedTrainingConfig` has all `gct_*` fields
- Model creation block after `standard` type
- Dedicated forward pass branch (returns `gct_metrics`)
- Training step counter updated each iteration via `model.set_training_step()`
- GCT metrics logged to console and TensorBoard

### Usage

```bash
# Train GCT (small, default settings)
python train_unified_llm_clean.py --model_type gct --model_size small \
    --dataset wikitext103 --max_steps 10000

# Train GCT with larger window for prose
python train_unified_llm_clean.py --model_type gct --model_size small \
    --gct_window_size 256 --gct_warmup_steps 1000 --gct_anneal_steps 3000

# Compare with standard baseline
python train_unified_llm_clean.py --model_type standard --model_size small \
    --dataset wikitext103 --max_steps 10000
```

---

## 6. Design Decisions

### 6.1 No Attention KL (FlashAttention Compatibility)

**Decision:** Remove attention KL from coherence computation entirely.

**Rationale:** Attention KL requires materializing the full N×N attention matrix,
which breaks SDPA/FlashAttention — the primary production accelerator. Output deltas
and residual deltas are sufficient stability signals. This dramatically increases
adoptability.

### 6.2 Corrected λ_ladder Sign Logic

**Decision:** λ_ladder activates when inter-band divergence is LOW (collapse risk),
not when it's HIGH.

**Rationale:** The conceptual model states hidden-state regions prevent collapse.
Collapse = bands becoming indistinguishable = LOW divergence. When bands are too
similar (divergence < threshold), λ_ladder suppresses routing to coarse path,
forcing full attention to preserve band specialization.

```
Λ = exp(-κ · max(0, τ_collapse - Δ_band))   # Corrected
```

### 6.3 No λ_mirror for v1

**Decision:** Omit λ_mirror regularizer from initial implementation.

**Rationale:**
- Complicates training without proven benefit
- Increases review skepticism
- Not required for core contribution (coherence gating)
- Can be added later as an optional regularizer

### 6.4 Phased Training Schedule

**Decision:** Three-phase schedule (warmup → anneal → full).

**Rationale:** Avoids 2× FLOP cost during entire training run. Phase 1 lets coherence
predictors stabilize before they influence routing. Phase 2 gradually introduces
routing to prevent training instability.

### 6.5 Shared QKV Projections

**Decision:** Full and local paths share the same Q, K, V projections.

**Rationale:** No parameter duplication. The local path is just the full path with
a different mask extent. During training, QKV are computed once and used by both
paths.

---

## 7. Metrics (Logged)

| Metric | Description |
|--------|-------------|
| `gct_mean_pi_star` | Mean effective routing probability (0=all full, 1=all local) |
| `gct_frac_local_routed` | Fraction of head-positions routed to local (π* > 0.5) |
| `gct_mean_lambda_ladder` | Mean ladder insulation (1=no suppression, <1=collapse protection active) |
| `gct_mean_coherence` | Mean raw coherence score (high=stable, low=turbulent) |
| `gct_schedule_weight` | Training schedule weight (0=Phase 1, 0-1=Phase 2, 1=Phase 3) |

---

## 8. Future Work

- **λ_mirror regularizer** (v2): Temporal reversal consistency loss for global coherence
- **Per-layer band assignment** learning: Let the model learn which heads belong to which band
- **Adaptive window sizing**: Window size varies by layer depth or coherence level
- **Inference kernel**: Fused CUDA kernel for hard routing (skip local-window computation entirely when full attention is selected)
- **Multi-resolution coarse paths**: Different window sizes for different bands

---

## 9. Theoretical Foundation

The GCT model builds on the FSCS (Frequency-Selective Compute Scaling) principle:

1. **Not all tokens need the same compute.** Stable, predictable regions can use
   cheaper local attention without quality loss.

2. **The routing decision should be pre-softmax.** If you need to compute QK^T
   to decide whether to compute QK^T, you've already paid the cost.

3. **Band insulation prevents collapse.** Different heads should specialize for
   different frequency ranges. Without insulation, all heads converge to the same
   behavior (mode collapse of the routing mechanism).

The GCT contribution is the combination of these three principles into a clean
drop-in modification of standard quadratic softmax attention.
