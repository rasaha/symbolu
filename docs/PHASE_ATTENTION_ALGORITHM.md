# Phase Attention: Mathematical Algorithm

## Overview

Phase Attention is a novel O(n) attention mechanism that uses complex-valued phasors to compute attention scores. Unlike standard O(n²) softmax attention, Phase Attention achieves linear complexity while preserving expressive power through phase-amplitude decomposition.

**Key Innovation:** Attention scores are computed as cosine similarities in phase space, enabling O(n) cumulative sum operations instead of O(n²) pairwise comparisons.

---

## Mathematical Foundation

### 1. Euler's Formula and Phasors

The fundamental building block is Euler's formula:

$$e^{i\phi} = \cos(\phi) + i\sin(\phi)$$

A **phasor** is a complex number represented in polar form:

$$z = a \cdot e^{i\phi}$$

where:
- $a$ = magnitude (amplitude) ∈ [0, 1]
- $\phi$ = phase (angle) ∈ [-π, π]

### 2. Attention as Phase Synchronization

Standard attention computes:
$$\text{Attn}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d}}\right) V$$

Phase Attention reformulates this as **phase synchronization**:

$$\text{Attn}(i, j) = a_i \cdot a_j \cdot \cos(\phi_i - \phi_j)$$

**Interpretation:**
- High attention when phases are aligned ($\phi_i \approx \phi_j$): $\cos(0) = 1$
- Zero attention when orthogonal ($|\phi_i - \phi_j| = \pi/2$): $\cos(\pm\pi/2) = 0$
- Negative attention when anti-aligned ($|\phi_i - \phi_j| = \pi$): $\cos(\pi) = -1$

### 3. Phasor Formulation

Using Euler's formula, the cosine can be extracted from complex multiplication:

$$\cos(\phi_q - \phi_k) = \text{Re}\left(e^{i\phi_q} \cdot e^{-i\phi_k}\right)$$

This leads to the phasor representation:

$$Q = a_q \cdot e^{i\phi_q} \quad \text{(Query phasor)}$$
$$K = a_k \cdot e^{-i\phi_k} \quad \text{(Key phasor, conjugate)}$$

The negative sign on the Key phase creates the conjugate, enabling the cosine extraction.

---

## Algorithm: O(n) Linear Attention

### Step 1: Phase-Amplitude Projection

Given input $x \in \mathbb{R}^{B \times N \times D}$:

```
φ_q = W_q^φ(x)     # Query phases:     [B, N, H, D_h]
a_q = σ(W_q^a(x))  # Query amplitudes: [B, N, H, D_h], sigmoid for [0,1]

φ_k = W_k^φ(x)     # Key phases:       [B, N, H, D_h]
a_k = σ(W_k^a(x))  # Key amplitudes:   [B, N, H, D_h]

V = W_v(x)         # Values:           [B, N, H, D_h]
```

**Key insight:** Query and Key have **separate** phase/amplitude projections. This allows asymmetric attention patterns (e.g., "the" → "cat" ≠ "cat" → "the").

### Step 2: Form Complex Phasors

Using `torch.polar(magnitude, angle)`:

$$Q_{\text{phasor}} = \texttt{polar}(a_q, \phi_q) = a_q \cdot e^{i\phi_q}$$
$$K_{\text{phasor}} = \texttt{polar}(a_k, -\phi_k) = a_k \cdot e^{-i\phi_k}$$

The negative phase on K creates the conjugate effect.

### Step 3: O(n) State Accumulation

The magic of linear complexity comes from **cumulative sums**:

$$KV_t = K_t \cdot V_t \quad \text{(complex × real)}$$
$$\text{State}_t = \sum_{j \leq t} KV_j = \texttt{cumsum}(KV)$$

This is O(n) instead of O(n²) because we accumulate a running state.

### Step 4: Readout via Synchronization

$$\text{Output}_t = \text{Re}(Q_t \cdot \text{State}_t)$$

Expanding:
$$= \text{Re}\left(a_{q,t} e^{i\phi_{q,t}} \cdot \sum_{j \leq t} a_{k,j} e^{-i\phi_{k,j}} V_j\right)$$
$$= \sum_{j \leq t} a_{q,t} \cdot a_{k,j} \cdot \cos(\phi_{q,t} - \phi_{k,j}) \cdot V_j$$

This is exactly the phase-amplitude attention formula!

### Step 5: Normalization

To prevent magnitude explosion:

$$\text{Norm}_t = a_{q,t} \cdot \sum_{j \leq t} a_{k,j} + \epsilon$$
$$\text{Output}_t = \frac{\text{Re}(Q_t \cdot \text{State}_t)}{\text{Norm}_t}$$

The normalizer uses cumulative sums of amplitudes, maintaining O(n) complexity.

---

## Cosine Mode Variants

### Standard Mode: $\cos(\phi_q - \phi_k)$

**Range:** [-1, +1]

$$\text{Output}_t = \frac{\text{Re}(Q_t \cdot \text{State}_t)}{\text{Norm}_t}$$

**Properties:**
- Can have destructive interference (negative cancellation)
- Original implementation

### Shifted Mode: $1 + \cos(\phi_q - \phi_k)$

**Range:** [0, 2]

$$\text{Output}_t = \frac{a_{q,t} \cdot \text{AV}_t + \text{Re}(Q_t \cdot \text{State}_t)}{2 \cdot \text{Norm}_t}$$

where $\text{AV}_t = \sum_{j \leq t} a_{k,j} \cdot V_j$

**Properties:**
- Eliminates negative cancellation
- Guarantees positive signal flow
- Use when training plateaus due to signal collapse

### Complex Mode: $\cos + i\sin$

$$\text{Real}_t = \frac{\text{Re}(Q_t \cdot \text{State}_t)}{\text{Norm}_t}$$
$$\text{Imag}_t = \frac{\text{Im}(Q_t \cdot \text{State}_t)}{\text{Norm}_t}$$
$$\text{Output}_t = W_{\text{proj}}([\text{Real}_t; \text{Imag}_t])$$

**Properties:**
- Real part (cos): Symmetric interaction
- Imaginary part (sin): Asymmetric/directional
- $\sin(\phi_q - \phi_k) \neq \sin(\phi_k - \phi_q)$ encodes ordering
- Most expressive but slightly higher memory

---

## Intent Phase Rotation (Ontological Bridge)

### Motivation

Same tokens should relate differently based on semantic intent:
- "The door is open" + Intent="enter" → Opportunity
- "The door is open" + Intent="secure" → Problem

### Mechanism

The **IntentPhaseProjector** converts Sovereign State Delta to phase offsets:

$$\theta_{\text{intent}} = \tanh(W_{\text{proj}}(\Delta S)) \cdot \pi$$

where $\Delta S \in \mathbb{R}^{32}$ is the change in the 32D Sovereign State.

This intent phase **rotates** the Query phasors:

$$\phi'_q = \phi_q + \theta_{\text{intent}}$$

### Effect on Attention

$$\cos(\phi'_q - \phi_k) = \cos(\phi_q + \theta_{\text{intent}} - \phi_k)$$

**Same tokens, different relationships based on understanding.**

| θ_intent | Effect |
|----------|--------|
| 0 | No change |
| π/2 | 90° rotation, orthogonal becomes aligned |
| π | 180° flip, aligned becomes anti-aligned |

---

## State Decay for Memory Horizon

### Motivation

Control the effective memory window without changing complexity.

### Mechanism

Instead of exact cumsum:
$$\text{State}_t = \sum_{j \leq t} KV_j$$

Use exponential decay:
$$\text{State}_t = \gamma \cdot \text{State}_{t-1} + KV_t$$

where $\gamma \in (0, 1]$ is the decay factor.

### Effective Memory Window

| γ | Effective Memory |
|---|------------------|
| 1.0 | Infinite (standard cumsum) |
| 0.95 | ~20 tokens |
| 0.9 | ~10 tokens |
| 0.8 | ~5 tokens |

This forces Phase Attention to focus on local patterns when combined with standard local attention in the Hybrid architecture.

---

## Hybrid Architecture

### Design

```
┌─────────────────────────────────────────────────────────────────┐
│  HYBRID ATTENTION LAYER                                         │
│                                                                 │
│  Input x ────┬────► Local Attention (O(n²) within window)      │
│              │       - Fast pattern learning                    │
│              │       - Syntax, grammar                          │
│              │       - Window size: 256-512                     │
│              │                                                  │
│              └────► Phase Attention (O(n) global)              │
│                      - Long-range dependencies                  │
│                      - Semantic context                         │
│                      - Intent-rotatable                         │
│                                                                 │
│  Output = α_local × LocalAttn(x) + α_phase × PhaseAttn(x)      │
└─────────────────────────────────────────────────────────────────┘
```

### Why Hybrid?

| Component | Complexity | Learns | Rotated by Intent? |
|-----------|------------|--------|-------------------|
| Local Attention | O(n²) within window | Grammar, syntax | No |
| Phase Attention | O(n) global | Semantics, context | Yes |

Grammar is grammar regardless of intent. But meaning changes with intent.

---

## Implementation Reference

### File Locations

| Component | Location |
|-----------|----------|
| `PhaseAttentionLayer` | `symbolu/phase_transformer.py:333` |
| `HybridAttentionLayer` | `symbolu/phase_transformer.py:1637` |
| `HybridPhaseTransformer` | `symbolu/phase_transformer.py:2145` |
| `IntentPhaseProjector` | `symbolu/phase_transformer.py:228` |
| `OntologicalHybridTransformer` | `symbolu/phase_transformer.py:2458` |

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cosine_mode` | "standard" | Interaction kernel: standard/shifted/complex |
| `decay_gamma` | 1.0 | State decay (1.0=infinite, <1.0=local focus) |
| `alpha_local` | 0.8 | Weight for local attention |
| `alpha_phase` | 0.2 | Weight for phase attention |
| `window_size` | 256 | Local attention window |

### CLI Arguments

```bash
python train_unified_llm.py \
    --model_type hybrid \
    --cosine_mode shifted \
    --decay_gamma 0.95 \
    --window_size 512
```

---

## Complexity Analysis

### Standard Attention
$$O(n^2 \cdot d)$$

- Computes all pairwise scores
- Memory: O(n²) for attention matrix

### Phase Attention
$$O(n \cdot d)$$

- Cumsum over sequence: O(n)
- Per-position projection: O(d)
- No attention matrix stored

### Memory Comparison

| Sequence Length | Standard Attn | Phase Attn |
|-----------------|---------------|------------|
| 1K | 4 MB | 4 KB |
| 8K | 256 MB | 32 KB |
| 32K | 4 GB | 128 KB |
| 128K | 64 GB | 512 KB |
| 1M | 4 TB | 4 MB |

---

## Mathematical Properties

### 1. Causal by Construction

Cumsum is inherently causal: position $t$ only sees positions $\leq t$.

### 2. Position Invariance

Phase attention is position-invariant (no positional encoding baked in). Position information must come from:
- Rotary Position Embeddings (RoPE)
- Learned positional embeddings
- The local attention component in Hybrid

### 3. Gradient Flow

- Amplitudes $a \in [0, 1]$ via sigmoid: bounded, stable
- Phases $\phi \in [-\pi, \pi]$: uniform initialization for diversity
- Cosine is smooth: well-behaved gradients

### 4. Expressive Power

**Theorem (informal):** Phase attention can approximate any causal attention pattern given sufficient capacity in the phase/amplitude projections.

**Intuition:** The phase space is high-dimensional ($H \times D_h$), and the cosine function can encode arbitrary similarity patterns through learned phase assignments.

---

## Comparison with Related Work

| Method | Complexity | Mechanism | Long-Range |
|--------|------------|-----------|------------|
| Standard Attention | O(n²) | Softmax(QK^T) | Yes |
| Linear Attention | O(n) | φ(Q)φ(K)^T | Limited |
| Mamba/S4 | O(n) | State space | Yes |
| RetNet | O(n) | Retention | Yes |
| **Phase Attention** | O(n) | Complex phasors | Yes |

**Key difference:** Phase Attention uses complex-valued phasors with explicit phase-amplitude decomposition, providing interpretable attention through phase synchronization.

---

## Appendix: PyTorch Implementation Sketch

```python
import torch
import torch.nn as nn

class PhaseAttention(nn.Module):
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        self.head_dim = embed_dim // num_heads
        self.num_heads = num_heads

        # Separate Q/K phase and amplitude projections
        self.W_q_phase = nn.Linear(embed_dim, embed_dim)
        self.W_q_amp = nn.Linear(embed_dim, embed_dim)
        self.W_k_phase = nn.Linear(embed_dim, embed_dim)
        self.W_k_amp = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)
        self.W_out = nn.Linear(embed_dim, embed_dim)

        # Initialize phases uniformly in [-π, π]
        nn.init.uniform_(self.W_q_phase.weight, -3.14159, 3.14159)
        nn.init.uniform_(self.W_k_phase.weight, -3.14159, 3.14159)

    def forward(self, x, intent_phase=None):
        B, N, D = x.shape
        H, Dh = self.num_heads, self.head_dim

        # 1. Project to phase and amplitude
        phi_q = self.W_q_phase(x).view(B, N, H, Dh)
        a_q = torch.sigmoid(self.W_q_amp(x)).view(B, N, H, Dh)
        phi_k = self.W_k_phase(x).view(B, N, H, Dh)
        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, H, Dh)
        v = self.W_v(x).view(B, N, H, Dh)

        # 2. Apply intent rotation (if provided)
        if intent_phase is not None:
            phi_q = phi_q + intent_phase

        # 3. Form complex phasors
        q_phasor = torch.polar(a_q, phi_q)       # a_q * e^(i*phi_q)
        k_phasor = torch.polar(a_k, -phi_k)      # a_k * e^(-i*phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))

        # 4. O(n) state accumulation
        kv = k_phasor * v_complex
        state = torch.cumsum(kv, dim=1)          # O(n)

        # 5. Readout
        qk_product = q_phasor * state
        normalizer = a_q * torch.cumsum(a_k, dim=1) + 1e-6
        output = qk_product.real / normalizer

        # 6. Reshape and project
        output = output.reshape(B, N, D)
        return self.W_out(output)
```

---

## Version History

| Version | Changes |
|---------|---------|
| V9.6.11 | Decoupled Q/K projections, high-capacity phase/amplitude |
| V9.6.12 | Cosine mode variants (standard/shifted/complex) |
| V9.6.13 | State decay for memory horizon control |
| V9.8.0 | Intent phase rotation bridge to 32D Sovereign State |

---

## References

1. **Euler's Formula:** $e^{i\phi} = \cos(\phi) + i\sin(\phi)$
2. **Phase-Amplitude Coupling in Neuroscience:** Theta-gamma coupling in hippocampus
3. **Linear Attention:** Katharopoulos et al., "Transformers are RNNs"
4. **State Space Models:** Gu et al., "Efficiently Modeling Long Sequences with Structured State Spaces"
5. **Complex-Valued Networks:** Trabelsi et al., "Deep Complex Networks"
