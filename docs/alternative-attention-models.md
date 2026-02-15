# Alternative Attention Models for Phase-Quad

## Architecture Reference for Normalization Variants, Cognitive Modes, and Production Deployment

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Core Insight: Normalization as Cognitive Lens](#2-the-core-insight-normalization-as-cognitive-lens)
3. [Normalization Variants — Complete Reference](#3-normalization-variants--complete-reference)
   - 3.1 [Softmax (Dense Baseline)](#31-softmax-dense-baseline)
   - 3.2 [Sparsemax (Euclidean Projection)](#32-sparsemax-euclidean-projection)
   - 3.3 [Entmax (Tsallis Regularization)](#33-entmax-tsallis-regularization)
   - 3.4 [Top-M Softmax (Production Variant)](#34-top-m-softmax-production-variant)
   - 3.5 [Kernel Attention — ELU](#35-kernel-attention--elu)
   - 3.6 [Kernel Attention — RBF](#36-kernel-attention--rbf)
4. [Cognitive Reasoning Modes](#4-cognitive-reasoning-modes)
   - 4.1 [Generation (Forward Construction)](#41-generation-forward-construction)
   - 4.2 [Critique (Verification / Auditing)](#42-critique-verification--auditing)
   - 4.3 [Summarization (Compression)](#43-summarization-compression)
5. [Task-Normalization Mapping](#5-task-normalization-mapping)
6. [Learned Temperature Control](#6-learned-temperature-control)
7. [Phase-Quad Integration Architecture](#7-phase-quad-integration-architecture)
   - 7.1 [Integration Paths](#71-integration-paths)
   - 7.2 [BCVF Hybrid Mode](#72-bcvf-hybrid-mode)
   - 7.3 [The Full Pipeline](#73-the-full-pipeline)
8. [Per-Head Normalization Mixing (Future)](#8-per-head-normalization-mixing-future)
9. [Configuration Reference](#9-configuration-reference)
10. [Evaluation and Diagnostics](#10-evaluation-and-diagnostics)
11. [Production Recommendations](#11-production-recommendations)

---

## 1. Executive Summary

Phase-Quad's proposal attention mechanism supports **seven normalization variants** that control how attention weight is distributed across retrieved proposals. These are not just training hyperparameters — they are **cognitive lenses** that fundamentally change how the model reasons about evidence.

| Metaphor | Normalization | Behavior |
|----------|---------------|----------|
| Democratic parliament | Softmax | Every proposal gets a voice |
| Merit-based council | Entmax | Weak proposals are silenced |
| Executive committee | Top-M Softmax | Fixed-size board of top proposals |
| Continuous parliament | Kernel (ELU/RBF) | No voting — continuous influence |

The key architectural insight: **different reasoning tasks demand different governance models**. Generation needs broad context (softmax). Critique needs sharp focus (entmax/top-M). Summarization needs moderate filtering (entmax with temperature). Phase-Quad's architecture supports switching between these modes.

---

## 2. The Core Insight: Normalization as Cognitive Lens

Standard transformer attention uses softmax normalization, which distributes nonzero weight to every key. This is a **dense** attention pattern — no proposal is fully ignored.

Sparse alternatives change this fundamentally:

```
Softmax:    [0.25, 0.20, 0.18, 0.15, 0.12, 0.05, 0.03, 0.02]  ← all nonzero
Entmax 1.3: [0.35, 0.28, 0.22, 0.15, 0.00, 0.00, 0.00, 0.00]  ← exact zeros
Top-M (4):  [0.32, 0.30, 0.22, 0.16, 0.00, 0.00, 0.00, 0.00]  ← fixed 4 active
```

This matters for Phase-Quad because the QuadRetriever returns K=64 proposals per patch, but typically only a subset are genuinely useful. The normalization controls **how aggressively** the model prunes irrelevant proposals.

**Why this is not a training trick**: The choice of normalization determines the model's **inductive bias** about evidence:

- **Dense**: "Consider everything, weigh carefully" (generative, exploratory)
- **Adaptive sparse**: "Let the input determine what matters" (analytical)
- **Fixed sparse**: "Always focus on the best N" (decisive, production-stable)

---

## 3. Normalization Variants — Complete Reference

### 3.1 Softmax (Dense Baseline)

```
AttentionNormType.SOFTMAX → "softmax"
```

**Mathematical definition:**

```
softmax(z)_i = exp(z_i) / Σ_j exp(z_j)
```

**Properties:**
- Output: strictly positive, sums to 1
- Sparsity: zero (all weights nonzero)
- Gradient: smooth everywhere
- Complexity: O(n)

**When to use:**
- Baseline comparisons
- Tasks requiring broad context integration
- Creative generation where ambiguity tolerance is high

**Phase-Quad context:**
Standard softmax is the original `CrossAttentionToProposals` behavior. All 64 proposals contribute to the output, even irrelevant ones. This creates noise when the QuadRetriever returns low-quality matches.

**Code:**
```python
# Direct
F.softmax(scores, dim=-1)

# Via config
AlternativeAttentionConfig(enabled=True, norm_type="softmax")
```

---

### 3.2 Sparsemax (Euclidean Projection)

```
AttentionNormType.SPARSEMAX → "sparsemax"
```

**Mathematical definition:**

```
sparsemax(z) = argmin_p ||p - z||^2  subject to  p ∈ Δ^n
```

where Δ^n is the probability simplex. This is the Euclidean projection of the logits onto the simplex.

**Properties:**
- Output: non-negative, sums to 1, exact zeros
- Sparsity: aggressive, input-dependent
- Gradient: piecewise linear (gradient discontinuities at zero boundaries)
- Complexity: O(n log n) due to sorting
- Equivalent to: entmax with alpha=2.0

**When to use:**
- Research into maximum-sparsity attention
- When you want the strongest possible proposal filtering
- Not recommended for production (gradient kinks can cause training instability)

**Risks:**
- Gradient discontinuities at the zero boundary can cause oscillatory training
- May be too aggressive for Phase-Quad (drops too many proposals)
- Sorting operation is less GPU-friendly than softmax

**Code:**
```python
from symbolu.vision.attention_normalizations import sparsemax
w = sparsemax(scores, dim=-1)
```

---

### 3.3 Entmax (Tsallis Regularization)

```
AttentionNormType.ENTMAX15 → "entmax15"     (alpha=1.5, fixed)
AttentionNormType.ENTMAX_ALPHA → "entmax"    (alpha configurable)
```

**Mathematical definition:**

```
entmax_α(z) = argmax_p  p·z + H_α^T(p)  subject to  p ∈ Δ^n
```

where H_α^T is the Tsallis entropy:

```
H_α^T(p) = (1 / α(α-1)) Σ_i (p_i - p_i^α)    (α ≠ 1)
```

**Interpolation between softmax and sparsemax:**
- α = 1.0: recovers softmax (dense, smooth)
- α = 1.5: standard entmax15 (moderate sparsity)
- α = 2.0: recovers sparsemax (maximum sparsity)

**Recommended alpha values for Phase-Quad:**

| Alpha | Sparsity | Gradient Quality | Use Case |
|-------|----------|-----------------|----------|
| 1.2 | Very mild | Excellent | Generation, broad context |
| 1.25 | Mild | Very good | Summarization, moderate filtering |
| 1.3 | Moderate | Good | **Recommended default** for Phase-Quad |
| 1.5 | Strong | Acceptable | High-sparsity research |
| 1.75 | Very strong | Marginal | Extreme filtering only |

**Why alpha=1.3 for Phase-Quad:**
Phase-Quad's QuadRetriever already performs coarse filtering (retrieving K=64 from thousands). Entmax at α=1.3 provides a second layer of soft filtering that zeros out the ~20-30% of retrieved proposals that are noise, while preserving smooth gradients for training stability.

**Properties:**
- Output: non-negative, sums to 1, exact zeros (for α > 1)
- Sparsity: input-dependent (adapts to input distribution)
- Gradient: smoother than sparsemax, approaches softmax smoothness as α→1
- Complexity: O(n × n_iter) due to bisection solver (~50 iterations)
- Key advantage: **automatic sparsity discovery** — the model learns which proposals to ignore

**Bisection solver details:**
The entmax solution requires finding a threshold τ via bisection:
```
p_i = max(0, [(α-1)z_i - τ]^(1/(α-1)))    normalized to sum to 1
```
Default: 50 bisection iterations (`_entmax_bisect`). Converges to machine precision.

**Code:**
```python
from symbolu.vision.attention_normalizations import entmax, entmax15

# Standard entmax15
w = entmax15(scores, dim=-1)

# Custom alpha (recommended: 1.3)
w = entmax(scores, alpha=1.3, dim=-1)

# Via config
AlternativeAttentionConfig(enabled=True, norm_type="entmax", entmax_alpha=1.3)
```

---

### 3.4 Top-M Softmax (Production Variant)

```
AttentionNormType.TOP_M_SOFTMAX → "top_m_softmax"
```

**Mathematical definition:**

```
top_m_softmax(z, M) = softmax(mask_M(z))

where mask_M(z)_i = z_i  if i ∈ top-M indices of z
                    -∞    otherwise
```

Keep the top M logits, mask the rest to -∞, then apply standard softmax over the M survivors.

**Properties:**
- Output: non-negative, sums to 1, exactly (n - M) zeros
- Sparsity: **deterministic** — always exactly M nonzero weights
- Gradient: smooth (standard softmax over M elements)
- Complexity: O(n log M) for top-k selection + O(M) for softmax
- No exotic solvers, no bisection, no sorting

**Why this is the production recommendation:**

| Property | Entmax | Top-M Softmax |
|----------|--------|---------------|
| Sparsity pattern | Input-dependent | Fixed (always M) |
| Gradient quality | Good (α < 1.5) | Excellent (softmax) |
| Compute | Bisection solver | Native PyTorch topk |
| Debugging | Hard (why did this zero?) | Easy (top M by score) |
| Memory prediction | Variable | Fixed |
| Auditing | Complex | Trivial |

**Phase-Quad synergy:**
Phase-Quad already has three layers of filtering before normalization:
1. **QuadRetriever**: retrieves K=64 from thousands (coarse ranking)
2. **BCVF**: filters for consistency (backward/forward/circular verification)
3. **ConfidenceGate**: reliability-weighted integration

Top-M softmax adds a fourth, deterministic layer. Since the QuadRetriever already ranks proposals, taking the top M is a natural "hard prune" that leverages the existing ranking. Automatic sparsity discovery (entmax) is less critical when you already have a good ranker.

**Choosing M:**
- Default: M=24 from K=64 proposals (keep top ~37%)
- Aggressive: M=8 (keep top ~12%)
- Conservative: M=32 (keep top 50%)
- Rule of thumb: M ≈ K/3 to K/2 balances selectivity with coverage

**Code:**
```python
from symbolu.vision.attention_normalizations import top_m_softmax

w = top_m_softmax(scores, m=24, dim=-1)

# Via config (recommended production setup)
AlternativeAttentionConfig(
    enabled=True,
    norm_type="top_m_softmax",
    top_m=24,
    mix_with_bcvf=True,
    learn_temperature=True,
)
```

---

### 3.5 Kernel Attention — ELU

```
AttentionNormType.KERNEL_ELU → "kernel_elu"
```

**Mathematical definition:**

Linear attention replaces softmax(QK^T)V with φ(Q)·(φ(K)^T·V), where φ is a positive feature map.

ELU kernel: `φ(x) = ELU(x) + 1`

```
Attention(Q,K,V) = φ(Q) · (φ(K)^T · V) / (φ(Q) · φ(K)^T · 1)
```

**Properties:**
- Complexity: O(n·d) instead of O(n^2) — linear in sequence length
- No explicit attention weights (no sparsity in the traditional sense)
- Smooth gradients everywhere
- Approximation quality: moderate (worst for very peaked attention patterns)

**When to use:**
- Very long proposal sequences (K >> 64)
- Latency-sensitive inference
- Research into softmax-free attention mechanisms

**Limitations:**
- Cannot produce sparse patterns (fundamentally dense)
- Quality degrades when true attention is very peaked
- Not directly comparable to softmax/entmax in sparsity metrics

**Code:**
```python
AlternativeAttentionConfig(enabled=True, norm_type="kernel_elu")
```

---

### 3.6 Kernel Attention — RBF

```
AttentionNormType.KERNEL_RBF → "kernel_rbf"
```

**Mathematical definition:**

Uses random Fourier features (Rahimi & Recht, 2007) to approximate the RBF kernel:

```
k(x, y) = exp(-||x - y||^2 / 2)
```

via random projections:

```
φ(x) = (1/√m) [sin(w_1·x + b_1), cos(w_1·x + b_1), ...]
```

where w_i ~ N(0, I), b_i ~ Uniform(0, 2π).

**Properties:**
- Complexity: O(n·m) where m = num_features (default 256)
- Better approximation quality than ELU for Gaussian-like attention
- Random projection matrix is fixed after initialization
- More parameters than ELU kernel

**When to use:**
- When ELU kernel quality is insufficient
- Research into kernel approximation quality
- When you need better approximation of softmax without O(n^2) cost

**Code:**
```python
AlternativeAttentionConfig(enabled=True, norm_type="kernel_rbf")
```

---

## 4. Cognitive Reasoning Modes

The choice of normalization is fundamentally a choice about **how the model reasons**. Different tasks require different reasoning modes.

### 4.1 Generation (Forward Construction)

**What the model needs:**
- Broad context integration across many proposals
- Tolerance for ambiguity — multiple valid continuations exist
- Smooth blending of ideas from diverse sources
- Low brittleness — no abrupt commitment to single hypotheses

**Cognitive profile:** Democratic, inclusive, exploratory.

**Best normalization:** Dense attention

| Variant | Suitability | Why |
|---------|------------|-----|
| **Softmax** | Best | Maximum context breadth, smooth blending |
| Entmax α≈1.2 | Good | Very mild filtering, mostly dense |
| Entmax α≈1.3 | Acceptable | May drop useful secondary context |
| Top-M (M=48+) | Acceptable | Conservative pruning preserves breadth |
| Top-M (M=8) | Risky | Too aggressive for generation |
| Sparsemax | Poor | Drops too many alternatives |

**Risk of excessive sparsity in generation:**
- Overcommitment to single proposals early in sequence
- Reduced stylistic richness (fewer source influences)
- Narrow continuation paths leading to repetitive output
- Abrupt reasoning jumps from missing transitional context

**Configuration for generation mode:**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="softmax",           # Dense attention
    learn_temperature=True,         # Let model control sharpness
    logit_temperature_init=1.0,
)
```

---

### 4.2 Critique (Verification / Auditing)

**What the model needs:**
- Sharp focus on inconsistencies
- Active suppression of noise and irrelevant evidence
- Clear comparison between competing hypotheses
- Decisive rejection of weak evidence

**Cognitive profile:** Focused, decisive, discriminating.

**Best normalization:** Concentrated, sparse attention

| Variant | Suitability | Why |
|---------|------------|-----|
| Softmax | Weak | Smears error across alternatives, false tolerance |
| Entmax α≈1.3 | Best | Adaptive sparsity matches evidence quality |
| **Top-M (M=8-16)** | Strong | Deterministic focus on strongest evidence |
| Top-M (M=32+) | Moderate | May be too permissive for critique |
| Sparsemax | Acceptable | Very sharp but gradient concerns |

**Why sparse attention improves critique:**
- Sharpens contrast between correct vs incorrect proposals
- Reduces hallucinated supporting evidence (noise gets zero weight)
- Improves consistency scoring by focusing on relevant comparisons
- Aligns naturally with BCVF consistency filtering and ConfidenceGate

**Risk of dense attention in critique:**
- Error tolerance: weak arguments get nonzero weight, survive into output
- False confidence: noise contributes to seemingly-supported conclusions
- Diluted error signals: inconsistencies get averaged away

**Configuration for critique mode:**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="top_m_softmax",     # Deterministic sparsity
    top_m=12,                       # Aggressive focus
    mix_with_bcvf=True,             # Leverage consistency filtering
    learn_temperature=True,
    logit_temperature_init=0.8,     # Start slightly sharp
)
```

---

### 4.3 Summarization (Compression)

**What the model needs:**
- Identify key signal-carrying proposals
- Compress structural information
- Preserve major themes while dropping noise
- Avoid overfitting to a single detail

**Cognitive profile:** Balanced, selective but not narrow.

**Best normalization:** Moderately sparse

| Variant | Suitability | Why |
|---------|------------|-----|
| Softmax | Okay | Includes irrelevant details |
| Entmax α≈1.25 | Best | Drops noise, preserves structure |
| **Entmax α≈1.3** | Best | Good balance of selectivity and coverage |
| Top-M (M=16-24) | Good | Predictable compression ratio |
| Top-M (M=8) | Narrow | Misses secondary themes |
| Sparsemax | Too aggressive | Collapses to single thread |

**The summarization trade-off:**
```
Too sparse → misses nuance, collapses multi-threaded content
Too dense  → includes irrelevant details, fails to compress
Sweet spot → drops noise while keeping salient structural blocks
```

**Temperature's role in summarization:**
Learned temperature is particularly valuable for summarization because it allows the model to **dynamically adjust compression ratio**. During training, the temperature learns to be:
- Cooler (T < 1) for structured, well-separated content
- Warmer (T > 1) for ambiguous, interleaved content

**Configuration for summarization mode:**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="entmax",             # Adaptive sparsity
    entmax_alpha=1.25,              # Moderate filtering
    learn_temperature=True,
    logit_temperature_init=1.0,
    mix_with_bcvf=True,
)
```

---

## 5. Task-Normalization Mapping

### Decision Matrix

| Task | Softmax | Entmax 1.25 | Entmax 1.3 | Top-M (M=24) | Top-M (M=8) | Sparsemax |
|------|---------|-------------|------------|---------------|--------------|-----------|
| **Generate** | **Best** | Good | Okay | Okay | Risky | Poor |
| **Critique** | Weak | Okay | **Best** | Strong | **Best** | Okay |
| **Summarize** | Okay | **Best** | **Best** | Good | Narrow | Poor |
| **Retrieval** | Weak | Good | **Best** | **Best** | Strong | Okay |
| **Classification** | Okay | Good | **Best** | **Best** | Good | Okay |
| **Reconstruction** | Good | Good | Good | Okay | Risky | Poor |

### Governance Metaphors

| Normalization | Governance Model | Decision Style |
|---------------|-----------------|----------------|
| Softmax | Democratic parliament | Every member votes, majority rules |
| Entmax (mild) | Weighted council | Members with weak positions abstain |
| Entmax (strong) | Merit-based senate | Only qualified members participate |
| Top-M Softmax | Executive committee | Fixed-size board of top-ranked members |
| Sparsemax | Emergency tribunal | Minimal quorum, decisive action |
| Kernel | Continuous field | No discrete votes, continuous influence |

### Reasoning Characteristics

```
                    Context Breadth
                         ↑
                Softmax  |  Kernel ELU
                    ●    |    ●
                         |
   Entmax 1.2  ●         |
                         |
   Entmax 1.3    ●       |
                         |
   Top-M (24)      ●     |
                         |
   Top-M (8)         ●   |
                         |
   Sparsemax           ● |
                         +────────────→  Selectivity
```

---

## 6. Learned Temperature Control

### The Problem

Attention logit scale drifts during training as Q/K weight magnitudes change. This means a fixed normalization function (even entmax) operates in different regimes at different training stages:

```
Early training:  logits ∈ [-1, 1]     → mild sparsity
Late training:   logits ∈ [-10, 10]   → aggressive sparsity (same alpha!)
```

The **effective sparsity changes** even though the normalization function is unchanged.

### The Solution

A learned temperature T divides logits before normalization:

```
attention_weights = normalize(logits / T)
```

where T is a trainable scalar (stored as log_temperature for numerical stability).

### Implementation Details

```python
# Stored as log for unconstrained optimization
self.log_temperature = nn.Parameter(torch.tensor(math.log(temperature_init)))

# Applied before normalization, clamped for safety
temperature = self.log_temperature.exp().clamp(
    self.TEMPERATURE_MIN,   # 0.05 — prevents near-argmax (gradient vanishing)
    self.TEMPERATURE_MAX    # 10.0 — prevents near-uniform (no selectivity)
)
attn_scores = raw_scores / temperature
```

### Temperature Regimes

| Temperature | Regime | Effect | Risk |
|------------|--------|--------|------|
| T < 0.05 | Near-argmax | One-hot attention | Gradient vanishing |
| T ≈ 0.5 | Sharp | Strong selectivity | May drop useful context |
| T = 1.0 | Neutral | Standard behavior | None |
| T ≈ 2.0 | Warm | Broad attention | Reduced selectivity |
| T > 10.0 | Near-uniform | All equal weight | No discrimination |

### Temperature + Normalization Interaction

Temperature and normalization interact multiplicatively:

```
Effective sharpness = (1/T) × normalization_sharpness(α)
```

For entmax: lower temperature increases effective alpha.
For top-M: lower temperature makes the softmax over survivors sharper.
For softmax: lower temperature approaches argmax.

This means `top_m_softmax + learned_temperature` gives you **two orthogonal controls**:
- M controls **how many** proposals survive
- T controls **how sharply** weight is distributed among survivors

---

## 7. Phase-Quad Integration Architecture

### 7.1 Integration Paths

The block supports four mutually exclusive proposal integration paths:

```
┌─────────────────────────────────────────────┐
│            PhaseQuadDiTBlock                │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     Proposal Integration             │    │
│  │                                      │    │
│  │  Path 1: alt_attention + BCVF        │    │
│  │    → PhaseQuadAttentionVariant       │    │
│  │    → Learned mix(BCVF, alt_attn)     │    │
│  │                                      │    │
│  │  Path 2: alt_attention (standalone)  │    │
│  │    → AlternativeAttentionToProposals │    │
│  │                                      │    │
│  │  Path 3: BCVF + softmax (original)   │    │
│  │    → HybridBCVFCrossAttention        │    │
│  │                                      │    │
│  │  Path 4: softmax only (baseline)     │    │
│  │    → CrossAttentionToProposals       │    │
│  └─────────────────────────────────────┘    │
│                                             │
└─────────────────────────────────────────────┘
```

Selection priority (in `_build_proposal_mixer`):
1. `alt_attention.enabled + mix_with_bcvf` → Path 1
2. `alt_attention.enabled` → Path 2
3. `use_bcvf` → Path 3
4. Default → Path 4

### 7.2 BCVF Hybrid Mode

The recommended production path combines BCVF consistency filtering with alternative attention via a **learned mixing ratio**:

```
output = σ(mix_ratio) × bcvf_output + (1 - σ(mix_ratio)) × alt_attn_output
```

where `mix_ratio` is a learned scalar parameter (initialized at 0.5).

**Why mix rather than replace:**
- BCVF captures **consistency** (do proposals agree with each other?)
- Alternative attention captures **relevance** (which proposals are most useful?)
- These are complementary signals — consistency ≠ relevance

### 7.3 The Full Pipeline

For the production configuration (`top_m_softmax + BCVF`), the proposal integration pipeline is:

```
QuadRetriever (K=64 proposals)
    │
    ├──→ BCVF Path
    │    ├── Backward verification
    │    ├── Forward verification
    │    ├── Circular consistency
    │    └── Vritti reliability scoring
    │         → bcvf_output [B, N, D]
    │
    ├──→ Alternative Attention Path
    │    ├── Q/K/V projection
    │    ├── Scaled dot-product: logits = QK^T / √d
    │    ├── Score bias: logits += scale × retrieval_scores
    │    ├── Temperature: logits /= T (learned)
    │    ├── Top-M mask: keep top 24, mask rest to -∞
    │    ├── Softmax over 24 survivors
    │    └── Weighted sum of values
    │         → attn_output [B, N, D]
    │
    └──→ Learned Mix
         output = σ(mix) × bcvf + (1 - σ(mix)) × attn
              → final [B, N, D]
```

**Four layers of filtering:**
1. QuadRetriever: coarse ranking (K=64 from thousands)
2. BCVF: consistency verification
3. Top-M: hard prune to best M
4. Temperature-controlled softmax: smooth weighting among survivors

---

## 8. Per-Head Normalization Mixing (Future)

The most architecturally powerful extension: allow each attention head to use a **different normalization strategy**.

### Motivation

Multi-head attention already learns specialized roles. Different heads attend to different subspaces. If different subspaces benefit from different reasoning modes, then per-head normalization provides a richer inductive bias.

### Proposed Design

```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="mixed",
    head_norm_types=[
        "top_m_softmax",    # Head 0: sharp specialist (M=8)
        "top_m_softmax",    # Head 1: broad context (M=32)
        "entmax",           # Head 2: adaptive sparsity
        "softmax",          # Head 3: dense fallback
    ],
    head_top_m=[8, 32, None, None],
    head_entmax_alpha=[None, None, 1.3, None],
)
```

### Expected Benefits

| Head Role | Normalization | Cognitive Mode |
|-----------|---------------|----------------|
| Detail head | Top-M (M=8) | Sharp focus on best matches |
| Context head | Top-M (M=32) | Broad integration |
| Adaptive head | Entmax 1.3 | Input-dependent filtering |
| Safety head | Softmax | Never drops anything |

### Implementation Notes

- Overhead: negligible (normalization is <1% of attention FLOPs)
- The normalization function is applied per-head after the Q·K^T matmul
- Temperature can also be per-head (one learned scalar per head)
- Backward pass: each head normalizes independently, gradients are independent

### Dynamic Mode Switching (Advanced)

Beyond per-head mixing: condition the normalization on **task mode**:

```
If task == "generate": use softmax (all heads)
If task == "critique": use top_m_softmax M=12 (all heads)
If task == "summarize": use entmax 1.25 (all heads)
```

This requires a task-mode signal (could be a special token, a conditioning embedding, or derived from the input distribution).

---

## 9. Configuration Reference

### AlternativeAttentionConfig

```python
@dataclass
class AlternativeAttentionConfig:
    enabled: bool = False           # Enable alternative attention (off by default)
    norm_type: str = "entmax"       # Normalization variant (string key)
    entmax_alpha: float = 1.3       # Alpha for entmax variants
    score_bias_scale: float = 0.5   # Retrieval score bias strength
    mix_with_bcvf: bool = True      # Combine with BCVF consistency filtering
    bcvf_mix_ratio: float = 0.5     # Initial BCVF vs attention mix
    logit_temperature_init: float = 1.0  # Initial temperature
    learn_temperature: bool = True  # Whether temperature is trainable
    top_m: int = 24                 # Top-M count for top_m_softmax
```

### Valid norm_type values

| String | Enum | Description |
|--------|------|-------------|
| `"softmax"` | `SOFTMAX` | Standard softmax (dense baseline) |
| `"sparsemax"` | `SPARSEMAX` | Euclidean projection (aggressive sparse) |
| `"entmax15"` | `ENTMAX15` | Entmax alpha=1.5 (literature standard) |
| `"entmax"` | `ENTMAX_ALPHA` | Entmax with configurable alpha |
| `"top_m_softmax"` | `TOP_M_SOFTMAX` | Top-M mask + softmax (production) |
| `"kernel_elu"` | `KERNEL_ELU` | Linear attention, ELU+1 kernel |
| `"kernel_rbf"` | `KERNEL_RBF` | Linear attention, random RBF features |

### Preset Configurations

**Production (recommended):**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="top_m_softmax",
    top_m=24,
    mix_with_bcvf=True,
    learn_temperature=True,
)
```

**Research / Exploration:**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="entmax",
    entmax_alpha=1.3,
    mix_with_bcvf=True,
    learn_temperature=True,
)
```

**Baseline (dense control):**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="softmax",
    mix_with_bcvf=True,
)
```

**Maximum Sparsity (research only):**
```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="sparsemax",
    mix_with_bcvf=True,
    learn_temperature=True,
    logit_temperature_init=0.5,     # Start sharp
)
```

---

## 10. Evaluation and Diagnostics

### AttentionNormEvaluator

Compare all variants on the same input:

```python
from symbolu.vision.attention_eval import AttentionNormEvaluator

evaluator = AttentionNormEvaluator(
    embed_dim=768,
    num_heads=12,
    topk=64,
)

report = evaluator.compare_all(x, proposals, scores)
print(evaluator.format_comparison_table(report))
```

**Output includes per-variant:**
- Sparsity ratio (fraction of zero weights)
- Entropy and normalized entropy
- Top-1 and top-5 mass (attention concentration)
- Gini coefficient (inequality of weight distribution)
- Forward time (ms)
- Output norm
- Cosine similarity to softmax baseline

### Sparsity Metrics

Available via `module.get_sparsity_metrics()` after each forward pass:

| Metric | Key | Description |
|--------|-----|-------------|
| Sparsity | `attn/sparsity` | Fraction of exactly-zero weights |
| Entropy | `attn/entropy` | Shannon entropy of weight distribution |
| Normalized entropy | `attn/normalized_entropy` | Entropy / log(K) ∈ [0, 1] |
| Top-1 mass | `attn/top1_mass` | Weight on the single best proposal |
| Top-5 mass | `attn/top5_mass` | Weight on the top 5 proposals |
| Gini coefficient | `attn/gini` | Inequality: 0=uniform, 1=one-hot |
| Temperature | `attn/temperature` | Current learned temperature value |
| Logit std | `attn/logit_std` | Standard deviation of raw logits |
| Logit range | `attn/logit_range` | Max - min of raw logits |
| Logit mean | `attn/logit_mean` | Mean raw logit value |

### Standalone Score Analysis

For analyzing QuadRetriever scores without building attention modules:

```python
from symbolu.vision.attention_eval import compare_normalizations_on_scores

# scores: [B, N, K] raw retrieval scores
results = compare_normalizations_on_scores(scores, dim=-1)
# Returns: {"softmax": {...}, "sparsemax": {...}, "entmax13": {...},
#           "entmax15": {...}, "entmax125": {...}, "entmax175": {...},
#           "top_m_softmax": {...}}
```

---

## 11. Production Recommendations

### For Phase-Quad Image Generation

**Primary recommendation: Top-M Softmax + BCVF + Learned Temperature**

```python
AlternativeAttentionConfig(
    enabled=True,
    norm_type="top_m_softmax",
    top_m=24,                       # Keep top 24 of 64 proposals
    mix_with_bcvf=True,             # BCVF consistency filtering
    bcvf_mix_ratio=0.5,             # Equal weight initially
    learn_temperature=True,          # Model controls sharpness
    logit_temperature_init=1.0,     # Start neutral
)
```

**Why:**
- Deterministic sparsity for predictable compute and debugging
- Smooth softmax gradients for stable training
- Learned temperature adapts sharpness to training stage
- BCVF hybrid captures both relevance and consistency
- Hardware-friendly (native PyTorch operations)

### Hyperparameter Search Strategy

Run these four configs in parallel:

| Run | Config | What it tests |
|-----|--------|---------------|
| A | Top-M (M=24) + BCVF | Conservative production |
| B | Top-M (M=16) + BCVF | Aggressive pruning |
| C | Entmax (α=1.3) + BCVF | Adaptive sparsity |
| D | Softmax + BCVF | Dense baseline |

**Metrics to watch:**
- FID/IS (generation quality)
- Sparsity ratio (should stabilize, not drift)
- Temperature trajectory (should converge)
- BCVF mix ratio (which signal dominates?)
- Training loss variance (stability indicator)

### When to Use What

| Scenario | Recommendation | Rationale |
|----------|---------------|-----------|
| First production deploy | Top-M (M=24) | Predictable, debuggable |
| A/B testing phase | Entmax 1.3 vs Top-M 24 | Compare adaptive vs fixed |
| Maximum quality, any cost | Per-head mixed | Research frontier |
| Latency-constrained inference | Top-M (M=8) | Minimum compute |
| Research exploration | All variants via evaluator | Find optimal operating point |

---

## File Reference

| File | Contents |
|------|----------|
| `symbolu/vision/attention_normalizations.py` | All normalization functions, modules, metrics |
| `symbolu/vision/alternative_attention.py` | `AlternativeAttentionToProposals`, `PhaseQuadAttentionVariant` |
| `symbolu/vision/attention_eval.py` | `AttentionNormEvaluator`, comparison utilities |
| `symbolu/vision/config.py` | `AlternativeAttentionConfig` dataclass |
| `symbolu/vision/phase_quad_dit_block.py` | Block integration, `_build_proposal_mixer` routing |
| `tests/test_alternative_attention.py` | 77 tests covering all variants |
