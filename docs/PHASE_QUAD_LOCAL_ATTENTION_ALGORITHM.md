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

## How to Read This Document (Plain English Guide)

Imagine you're building a brain that reads text one word at a time and needs to understand what it's reading. A normal AI brain (a standard transformer) does this by having every word look at every other word to figure out what's important — but that gets extremely expensive when texts get long (cost grows as the square of the text length).

This architecture solves that problem by splitting the "paying attention" job into **three specialists**, each with a different talent:

1. **Phase** — The **diary keeper**. It reads each word and writes a compressed summary into a running journal. It never forgets, and it does this cheaply by just adding to a running total (not comparing every word to every other word).

2. **Quad** — The **librarian**. When the model needs to recall something specific, Quad searches through Phase's journal and pulls out the most relevant entries. It doesn't read the whole journal — just the top-k most promising entries.

3. **Local** — The **proofreader**. It looks at just the nearby words (like the last 256) with full precision to get grammar, word order, and syntax right. "The cat sat on the..." — Local knows the next word should be "mat" because it sees the exact recent context.

The sections below describe each specialist in mathematical detail. Here's the plain-English roadmap of how they connect:

> **Section 1** (Architecture) shows the big picture — how the three paths fit together.
> **Section 2** (Math) explains the trick that makes Phase so cheap — using angles on a circle instead of comparing every pair of words.
> **Section 3** (Phase) details how the diary keeper writes its journal.
> **Section 4** (Quad) details how the librarian searches that journal.
> **Section 5** (Local) details how the proofreader checks nearby words.
> **Section 6** (Fusion) explains how their answers are combined.
> **Section 7** (FFN) is the "thinking step" after attention — a simple neural net that transforms the combined signal.
> **Section 8** (Block) shows one complete layer: all three paths + fusion + thinking.
> **Section 9** (Model) stacks many blocks and adds the input/output wiring.
> **Sections 10–15** cover training tricks, control systems, long-document handling, and health monitoring.
> **Sections 16–18** cover cost analysis, safety rules, and tuning knobs.

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

> **In Plain English — What Section 1 told us:**
> The model has three workers. Local handles nearby words (like a proofreader), Phase keeps a running journal of everything seen so far (like a diary keeper), and Quad searches that journal when the model needs to remember something specific (like a librarian). The critical discovery was that these three must have *separate, protected jobs*. When Phase and Quad were allowed to share the same workspace, Phase became useless — it added nothing. But when each had its own exclusive role (Phase only writes, Quad only reads), Phase became essential. This is the architectural foundation everything else builds on.

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

> **In Plain English — What Section 2 told us:**
> Normal attention works like a room full of people where *everyone* shakes hands with *everyone else* to see who's relevant — that's expensive (n-squared comparisons). Phase attention instead gives each word an **angle** (like a direction on a compass) and a **loudness** (amplitude). Two words "pay attention" to each other when their compass needles point the same way — `cos(angle_A - angle_B)` is high when angles are similar, low when they're different. The mathematical trick (Euler's formula) lets us compute this with a simple running total instead of pairwise comparisons. Think of it like this: instead of asking "how similar is word 5 to words 1, 2, 3, 4?" individually, we keep a single summary vector that accumulates all past words, and word 5 just checks against that one summary. That's the O(n) magic.

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

> **In Plain English — What Section 3 told us:**
> Phase is the diary keeper. Here's what it actually does step by step: (1) It takes each word and converts it into two things: an **angle** (phase — "what kind of thing is this?") and a **loudness** (amplitude — "how important is this?"). (2) It wraps the angle into the range [-180, +180] degrees so it can't drift off to infinity. (3) Each of the model's 12 "attention heads" starts at a different angle on the compass (like 12 people facing 12 different directions) so they don't all learn the same thing. (4) It forms a complex number from the angle and loudness (like an arrow with a direction and length), multiplies it by the word's content, and adds it to a running total. This running total IS the memory — it's a compressed summary of everything seen so far.
>
> The **decay** option controls how quickly old memories fade. With decay=1.0, the model never forgets (infinite memory). With decay=0.95, memories from 20+ words ago are mostly gone. The "learned decay" option lets each head choose its own forgetting speed — some heads remember 2 words back (syntax), others remember 2,000 words back (plot of a story).
>
> **How this connects to the next section:** Phase has now produced a `memory_state` — a compressed journal of everything seen so far. But this journal is compressed, lossy. You can't look up a specific fact from 500 words ago with precision. That's Quad's job.

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

> **In Plain English — What Section 4 told us:**
> Quad is the librarian. Phase wrote a journal, but it's compressed — you can't just look up "what was the character's name from paragraph 3?" directly. Quad fixes this by doing a focused search. Here's how: (1) It takes the current word and asks "what am I looking for?" (a query). (2) It takes Phase's memory and asks "what's stored here?" (keys and values). (3) It computes a relevance score between the query and every memory entry. (4) Instead of looking at ALL entries (which would be expensive), it picks only the top-k most relevant ones (like a librarian pulling the 64 most relevant books from a library of thousands). (5) It does a precise weighted average over just those top-k entries. This reduces cost from n-squared to n-times-k.
>
> There's a clever detail: **binding salience**. The system can tell Quad "these words are more important" (like highlighting key sentences in a textbook). This biases *which* entries get selected for the top-k, but it does NOT change *how* the attention math works on those entries. The selection is biased, but the weighting is pure — this prevents the control system from injecting arbitrary content into the attention.
>
> In **proposal mode**, Quad doesn't blend the results itself — instead it hands Phase a list of candidates ("I found these 64 possibilities") and Phase picks which ones to integrate. If Phase is already confident about what it knows, Quad is skipped entirely to save computation.
>
> **How this connects to the next section:** Phase and Quad handle global memory (the whole document). But neither is great at fine-grained local patterns like "the → cat" or "is → running" — that requires exact token-level detail from nearby words. That's Local's job.

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

> **In Plain English — What Section 5 told us:**
> Local is the proofreader. It does traditional attention (the kind normal transformers use) but only within a small window — say, the last 256 words. For the word at position 1000, it only looks at words 744–1000, ignoring everything before that. Within that window, it does full-precision attention: every word compares to every other word in the window. This gives it perfect knowledge of recent grammar, word order, and syntax patterns.
>
> The window size adjusts automatically — for short sequences, it covers half the text; for long sequences, it caps at the configured maximum (256 by default). Multiple computational backends are supported (FlashAttention for speed, manual implementation for compatibility).
>
> **How this connects to the next section:** We now have three outputs — Local's syntax signal, Phase's memory signal (via Quad's retrieval). How do we combine them?

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

> **In Plain English — What Section 6 told us:**
> The answer is surprisingly simple: just **add them together**. `output = local_signal + memory_signal`. No learned gating, no competition, no "choose which one matters more." Why? Because experiments showed that when you make Phase and Quad compete (via gates or learned weights), Phase always loses — the model learns to ignore it. But when you just add them, each path contributes its unique signal without interference. This is the "protected architecture" principle: each specialist does their job, and their contributions stack.
>
> Think of it like a team report: the proofreader marks grammar fixes, the diary keeper adds context from earlier chapters, and the librarian adds specific referenced facts. You don't pick one — you merge all three annotations onto the same document.
>
> **How this connects to the next section:** After combining the three attention signals, the result goes through a "thinking" step — the feed-forward network.

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

> **In Plain English — What Section 7 told us:**
> The FFN is the "thinking" step. After the three attention paths figured out *what to pay attention to*, the FFN transforms that information — it's a simple two-layer neural network that first expands the signal to 4x its size (giving it room to compute), then compresses it back down. Think of it like the model taking notes from the attention results and writing a refined summary. Every transformer in the world has this same structure. It handles the non-linear reasoning that attention alone can't do.
>
> **How this connects to the next section:** One attention step + one FFN step = one "block." The next section shows how these pieces fit together in a single block.

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

> **In Plain English — What Section 8 told us:**
> This is the complete recipe for one layer. Step by step: (1) First, check that any external control signals are valid (safety check). (2) Run Local attention on the raw input — get syntax patterns. (3) Run Phase on the raw input — build/update the memory journal. (4) Run Quad to search Phase's journal — get retrieved memories. (5) Add Local + Quad results together. (6) Add that sum back to the original input (residual connection — a skip-wire that prevents information loss). (7) Run through the FFN for non-linear processing. Output goes to the next layer.
>
> The "enable_slots_read" control is interesting: it lets the system turn OFF Quad's retrieval without stopping Phase's journaling. Phase always writes (you always want the diary updated), but sometimes you don't need to search it.
>
> **How this connects to the next section:** One block is one layer of processing. The full model stacks 12–32 of these blocks, adds word embeddings at the start and a vocabulary predictor at the end.

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

> **In Plain English — What Section 9 told us:**
> The full model: (1) Turn words into numbers (embeddings) and add position information ("this is the 5th word"). (2) Pass through 12 blocks (each doing Local + Phase + Quad + FFN). (3) At the end, project the result back to vocabulary size to predict the next word. The "logit scale" dampens the model's early confidence so it doesn't become overconfident before it's learned anything useful.
>
> Weight tying means the input word table and output word predictor share the same parameters — this is standard practice that saves memory and helps generalization. It's disabled when injecting non-standard tokens (like Sanskrit phonemes) because those would corrupt the output predictor.
>
> **How this connects to the next section:** The model structure is complete. But during training, Phase has a tendency to "collapse" — all its angles converge to the same value, making it useless. Section 10 introduces the regularization that prevents this.

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

> **In Plain English — What Section 10 told us:**
> Phase collapse is the biggest training risk. Imagine all 12 compass needles (attention heads) slowly drifting until they all point the same direction. When that happens, `cos(angle_A - angle_B) ≈ 1` for every pair of words — everything looks equally relevant, and Phase loses all selectivity. It becomes a uniform amplifier instead of a selective filter.
>
> The fix: during training, we add a penalty that measures "how spread out are the phases?" Think of it like this: if you average all the compass arrows and the result is a strong vector pointing in one direction, the phases are collapsed (penalty is high). If the average arrow is near zero (arrows cancel out because they point in all directions), phases are nicely spread (penalty is low). We compute this with complex exponentials — `exp(i*angle)` gives a unit arrow, and averaging those arrows and measuring the result length tells us how collapsed/spread the distribution is.
>
> Two penalties work together: the uniformity loss (are phases spread around the circle?) and the entropy proxy (is there enough diversity?). Start with gentle penalties (0.001) and ramp up over training.
>
> **How this connects to the next section:** Section 10 addressed a training problem. Section 11 addresses a *speed* problem — the running-total accumulation (EMA) that Phase uses can be slow if done one word at a time. The parallel scan makes it fast.

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

> **In Plain English — What Section 11 told us:**
> Phase's memory uses a "running average with decay" — each new word adds to the total, but old entries slowly fade. Computing this one word at a time in Python is painfully slow (2,048 loop iterations for a 2,048-token sequence). The parallel EMA scan is an optimization: it groups 64 words at a time and processes each group with fast vectorized math (matrix operations the GPU is good at). This turns 2,048 iterations into 32 — a 32x speedup.
>
> There's a numerical trap: the vectorized math requires computing `(1/decay)^63`, which is fine when decay is close to 1 (like 0.95) but explodes to infinity when decay is small (like 0.5). So the algorithm checks: if the decay factor is >= 0.9, use the fast vectorized path; otherwise, fall back to the safe-but-slow sequential loop.
>
> **How this connects to the next section:** Sections 3–11 covered the core attention machinery and training. Section 12 introduces the *control system* — how external signals (like "this topic is about science" or "focus on content words") can steer the attention without corrupting it.

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

> **In Plain English — What Section 12 told us:**
> The ontological control plane is how higher-level understanding steers the attention system. Think of it like a manager who tells the workers "pay more attention to scientific terms" or "this paragraph is about history." It does this through two main signals:
>
> **Binding salience** is like a highlighter pen — it marks certain words as more important (`[B, N]` — one importance score per word). This biases *which* words Quad puts in its top-k shortlist, but it does NOT change the attention math on those words. It's like telling the librarian "check the science section first" vs. "change how you read the books."
>
> **Intent phase** is a small rotation signal (`[B, H]` — one angle per attention head) that shifts what Phase considers "similar." It's like rotating everyone's compass slightly so they pay attention to different things based on the current understanding context.
>
> The **no-write contract** is a safety rule: control signals must be small and simple (a few numbers per head or per word). They must NEVER be big enough to encode arbitrary content (like a full word embedding). This prevents the control system from secretly injecting words into the attention — it can only steer, not override.
>
> **How this connects to the next section:** Section 12 showed how intent can steer attention. But a naive implementation just adds intent to the content phase — and intent can overpower content, making the model attend to what it "wants" rather than what's actually relevant. Section 13 fixes this with a two-channel design.

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

> **In Plain English — What Section 13 told us:**
> The problem: if you mix "what the words actually say" (content) with "what the model wants to find" (intent) into a single score, intent can dominate. Imagine a search engine where your *desire* for a result overrides the actual *relevance* of documents — you'd get confirmation bias.
>
> The solution: keep two separate scores. **Content score** = "how similar are these words?" (based on their actual phases). **Alignment score** = "does my intent agree with my understanding?" (based on the JEPA sensor vs. the SRK master). The final score multiplies them: `content × (1 + small_factor × alignment)`. This means content always drives the main ranking, and intent can only gently boost or suppress — it can never override.
>
> In the protected architecture (Phase writes, Quad reads), this dual-channel separation happens *naturally*: Phase controls how things are stored (the key side — SRK/Master), and Quad controls how things are searched (the query side — JEPA/Sensor). They're already separate by design.
>
> **How this connects to the next section:** All the above assumes the entire text fits in memory at once. But what about very long documents (millions of tokens)? The model has to process them in chunks. Section 14 explains how Phase's memory survives across chunk boundaries.

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

> **In Plain English — What Section 14 told us:**
> When a document is too long to fit in one pass, we split it into chunks (say, 2,048 words each). The problem: if Phase's memory resets at each chunk boundary, it can't remember anything from earlier chunks — it becomes useless for long-range understanding.
>
> The fix: at the end of each chunk, save Phase's final memory state (a single complex vector per head). When processing the next chunk, *start* Phase's accumulation from that saved state instead of from zero. It's like the diary keeper closing one notebook and opening the next one, but copying the last entry forward as a summary.
>
> For the decay version (EMA), the math is more nuanced: the old state decays exponentially as new words arrive, so the model naturally forgets the oldest information while preserving recent context.
>
> **Critical rule**: gradients must flow through the saved state. If you "detach" it (cut the gradient connection), the model can't learn to write good summaries at chunk boundaries — training breaks silently.
>
> **How this connects to the next section:** We've covered the full architecture, training, control, and long-document handling. But how do you know if the model is healthy during training? Section 15 introduces the diagnostic dashboard.

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

> **In Plain English — What Section 15 told us:**
> This is the model's health dashboard — read-only checks that don't affect training. The key metrics:
>
> - **R_k (phase collapse)**: Measures whether all the compass needles have converged to the same direction. Healthy = near 0 (diverse directions). Unhealthy = near 1 (all pointing the same way). This is the single most important metric.
> - **Amplitude-phase correlation**: If Phase is "cheating" by using amplitude to compensate for collapsed phases (making important things loud instead of distinguishing them by angle), this correlation will be high.
> - **Head redundancy**: Are the 12 attention heads learning different things, or have they all converged to the same behavior? High redundancy = wasted capacity.
> - **Phase drift**: Are the phases changing over time (token to token)? If drift is zero, Phase is frozen — it's not actually using its phase as a dynamic state variable. If drift is huge, it's unstable. Small, steady drift is ideal.
>
> These metrics are computed by capturing internal tensors during a forward pass (without gradients), computing statistics, and discarding the captures. No effect on training whatsoever.
>
> **How this connects to the next section:** We've covered *what* the model does and *how to monitor it*. Section 16 answers "how expensive is it?" — the computational cost analysis.

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

> **In Plain English — What Section 16 told us:**
> The cost breakdown reveals where computation goes. Surprisingly, the FFN (the "thinking" step) dominates — it costs about 2.4 million operations per word. Phase is the cheapest attention path at 768 ops per word (just a running total). Quad costs about 4,096 ops per word (searching 64 candidates). Local costs about 16,384 ops per word (comparing against 256 recent words).
>
> The key comparison: a standard transformer's attention costs n-squared (every word vs. every word). For a 3,000-word document, that's 9 million comparisons. Phase-Quad-Local's combined attention costs about 21,000 ops per word regardless of document length — it's linear, not quadratic. So for documents longer than ~3,000 words, this architecture is cheaper. For a 100,000-word document, it's 3,000x cheaper.
>
> Memory savings are even more dramatic: a standard transformer stores an n×n attention map (huge for long documents). This architecture stores only an n×k map for Quad (where k=64 is much smaller than n).
>
> **How this connects to the next section:** Section 17 codifies the safety rules — the invariants that must never be violated, or the architecture breaks.

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

> **In Plain English — What Section 17 told us:**
> These are the "commandments" of the architecture — rules that, if broken, cause the model to degrade silently (the most dangerous kind of bug). The 8 invariants in plain language:
>
> 1. **Phase only writes** — it builds the journal, never produces a direct output.
> 2. **Quad only reads** — it searches the journal, never writes to it.
> 3. **Local is independent** — it never touches the journal, only looks at nearby words.
> 4. **Control signals are small** — a few numbers per head, never full word embeddings.
> 5. **Salience steers selection, not weights** — it biases WHICH memories to check, not HOW to weight them.
> 6. **Phase always writes** — even when retrieval is turned off, the journal is always updated.
> 7. **Memory carries across chunks** — the journal never resets mid-document.
> 8. **Gradients flow through saved state** — the training signal must reach across chunk boundaries.
>
> These are enforced by runtime assertions that crash the training immediately if violated — better to crash loudly than to train a subtly broken model for days.
>
> **How this connects to the next section:** Section 18 is the reference table for all the knobs you can turn.

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

> **In Plain English — What Section 18 told us:**
> This is the tuning guide. The most important takeaways: (1) `bounded_phase=True` is **mandatory** — without it, phases drift to infinity and collapse. (2) Start with `decay_gamma=1.0` (infinite memory) and only reduce it if Phase is overwhelming Local. (3) `top_k=64` is a good default for Quad — larger values give better retrieval but cost more. (4) `local_window_size=256` covers about a paragraph of text — enough for syntax but not so much that it overlaps with Phase/Quad's job. (5) The diversity loss weights (0.001) should ramp up during training if phase collapse is observed.

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

> **In Plain English — Appendix A:**
> The Sovereign State is the model's "self-awareness" vector — 32 numbers that describe what the model currently "is" and "feels." Only the first 12 (Bhavas — modes of being like "cognition," "agency," "purpose") actually affect the phase rotation in attention. The remaining 20 are control/learning signals routed elsewhere. This separation is critical: you don't want the model's "nervousness level" (a Guna dynamic) to randomly rotate attention phases — only its fundamental mode of understanding (Bhavas) should do that.

---

## Appendix B: Cosine Mode Comparison

| Mode | Range | Formula | Pros | Cons |
|------|-------|---------|------|------|
| `standard` | [-1, +1] | cos(φ_q − φ_k) | Original, symmetric | Destructive interference |
| `shifted` | [0, 2] | 1 + cos(φ_q − φ_k) | Positive signal, no cancellation | Less selective |
| `complex` | ℂ → ℝ | W·[Re, Im]^T | Asymmetric ("the→cat" ≠ "cat→the") | +memory, extra projection |

---

> **In Plain English — Appendix B:**
> Three ways to compute "how similar are two words' phases": (1) **Standard** (`cos`) — ranges from -1 to +1, meaning two words can actively cancel each other out (destructive interference). Most selective but can cause signal collapse. (2) **Shifted** (`1 + cos`) — ranges from 0 to 2, so all contributions are positive. Less selective but more stable when training stalls. (3) **Complex** — uses both the cosine (symmetric: "A relates to B the same as B relates to A") and sine (asymmetric: "the → cat" is different from "cat → the") components. Most expressive but costs more memory.

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

> **In Plain English — Appendix C:**
> How does this compare to other architectures? Standard Transformers (GPT-4, etc.) do everything with one expensive O(n^2) attention mechanism — it works but scales poorly. Mamba and RWKV use a single cheap O(n) recurrence — efficient but has no dedicated retrieval or local syntax handling. Phase-Quad-Local is unique in having **three explicit specialists**: cheap global memory (Phase), targeted retrieval (Quad), and precise local syntax (Local). It's also the most interpretable — you can literally measure the phase angles and diagnose what each head is doing, which is impossible with Mamba's opaque state-space dynamics.

---

*Document generated from codebase analysis of `symbolu/phase_transformer.py` (7,696 lines),
`symbolu/hp_quad.py`, `symbolu/reflective_phase_quad.py`, and `symbolu/rlm_phase_quad.py`.*
