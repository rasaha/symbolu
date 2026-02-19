# Spanda-Softmax Hybrid: Design Evaluation

**Version:** 0.3.0 (Evaluation Only -- No Implementation)
**Date:** 2026-02-19
**Status:** Design evaluation. Not approved for implementation.

---

## 1. Premise

Softmax works. You do not throw it away. You add Spanda where it adds
structure -- not where it replaces stability.

- **Spanda** handles semantic continuity (explicit state trajectory).
- **Softmax** handles uncertainty and competition (probabilistic emission).

The hybrid merges both without breaking either.

---

## 2. Core Architecture

### 2.1 Current Emission Path (What Exists)

All six transformer variants in `symbolu/phase_transformer.py` use the same
emission pattern:

```
h_t = Transformer(x_<=t)          # hidden state from backbone
z_y = (W_lm * h_t) * logit_scale  # linear projection + scaling
p(y) = softmax(z_y)               # token probabilities
```

Where `logit_scale = 1 / sqrt(sqrt(embed_dim))` (~0.19 for d=768).

Relevant locations:
- `lm_head`: lines 3560, 5193, 5827, 6147, 7077, 7233
- `logit_scale`: lines 3564, 5196, 5830, 6150, 7080, 7236
- `logits = self.lm_head(x) * self.logit_scale`: lines 3814, 5243, 5985, 6372, 7156, 7296

### 2.2 Proposed Spanda Emission Path

Introduce an explicit semantic state vector Psi that evolves continuously:

```
h_t = Transformer(x_<=t)              # unchanged backbone
Delta_Psi_t = f_theta(h_t)            # MLP computes state update
Psi_{t+1} = LN(gamma * Psi_t + Delta_Psi_t)  # bounded leaky integration

z_y = -||Psi_{t+1} - A[y]||^2         # distance to token anchors
p(y|Psi_{t+1}) = softmax(z_y)         # softmax preserved
```

Where `A[y]` are projected token anchors in R^d_psi (see Section 3.4),
`gamma` is a decay factor (default 0.99), and `LN` is LayerNorm.

### 2.3 What Changes, What Stays

| Component | Current | Hybrid | Changed? |
|-----------|---------|--------|----------|
| Transformer backbone | O(n) phase / O(n^2) standard | Same | No |
| 32D Sovereign State | Bhava/Kosha/Vritti/Guna planes | Same, orthogonal to Psi | No |
| Logit computation | `h_t^T W_y` (linear) | `-\|\|Psi - A[y]\|\|^2` (geometric) | **Yes** |
| Softmax | `softmax(z_y)` | `softmax(z_y)` | No |
| Cross-entropy loss | `F.cross_entropy(logits, labels)` | Same | No |
| Weight tying | `lm_head.weight = token_embed.weight` | Replaced by anchor table | **Yes** |

---

## 3. Codebase Integration Analysis

### 3.1 Where Psi State Fits

The codebase already has an explicit state mechanism:
`OntologicalBindingCacheTransformer.compute_state_delta()` at line 4034.

```python
state = self.state_projector(pooled)      # h -> S[32]
delta_S = state - self.prev_state         # delta
delta_bhava = bhava - self.prev_bhava     # bhava-only delta for phase rotation
```

This is structurally identical to the Spanda update rule:

```
Psi_{t+1} = Psi_t + Delta_Psi_t
```

**Key difference:** The existing 32D Sovereign State feeds *attention
modulation* (phase rotation). Spanda's Psi would feed *token emission*.
These are orthogonal concerns and can coexist cleanly:

- `S[32]` -> phase rotation (attention modulation, via Bhava delta)
- `Psi[d]` -> emission geometry (token prediction, via anchor distance)

### 3.2 What the Psi State Module Would Look Like

**Critical constraint:** Psi must be computed per-sequence, per-timestep,
with no shared mutable state across batch elements. A `register_buffer`
approach (storing `prev_psi` on the module) breaks:
- Batched training (state leaks between unrelated sequences in a batch).
- DDP (each GPU process has inconsistent implicit state).
- Teacher forcing (all timesteps are computed in parallel; a single
  `prev_psi` per model is conceptually wrong).

The correct approach computes Psi as a parallel cumulative sum over the
sequence dimension:

```python
class SpandaState(nn.Module):
    def __init__(self, embed_dim, psi_dim=256, decay_gamma=0.99):
        super().__init__()
        self.delta_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, psi_dim),
        )
        self.decay_gamma = decay_gamma
        self.psi_norm = nn.LayerNorm(psi_dim)

    def forward(self, h):
        # h: [B, T, D] -- full sequence of hidden states
        delta = self.delta_mlp(h)              # [B, T, psi_dim]

        # Leaky cumulative sum (bounded integrator)
        # For pure cumsum: psi = torch.cumsum(delta, dim=1)
        # With decay: Psi_t = gamma * Psi_{t-1} + Delta_t
        # Implemented as sequential scan (T is typically small vs B*D)
        psi = torch.zeros_like(delta[:, :1, :])  # [B, 1, psi_dim]
        psi_seq = []
        for t in range(delta.size(1)):
            psi = self.decay_gamma * psi + delta[:, t:t+1, :]
            psi_seq.append(psi)
        psi = torch.cat(psi_seq, dim=1)        # [B, T, psi_dim]

        # LayerNorm prevents drift without tuning regularizer weights
        psi = self.psi_norm(psi)

        return psi, delta   # psi: [B, T, psi_dim], delta: [B, T, psi_dim]
```

**Training:** The leaky cumsum can be parallelized via a linear scan
(associative scan) if T is large. For typical sequence lengths, the
sequential loop is fast enough since the bottleneck is the backbone.

**Inference:** During autoregressive generation, pass `h: [B, 1, D]`
per step and maintain `prev_psi` externally in a generation cache
(same pattern as KV-cache), not as module state.

This mirrors the existing `compute_state_delta()` pattern at line 4034,
but corrects the statefulness to be per-sequence rather than per-model.

### 3.3 What the Anchor Emission Would Replace

Current `lm_head`:
```python
self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)  # line 5827
logits = self.lm_head(x) * self.logit_scale                  # line 5985
```

Anchor emission (algebraic matmul form):
```python
class AnchorEmission(nn.Module):
    def __init__(self, vocab_size, psi_dim, temperature=1.0):
        super().__init__()
        self.anchors = nn.Parameter(torch.randn(vocab_size, psi_dim))
        self.temperature = temperature
        # Precomputed for efficiency; updated each forward pass
        self.register_buffer('_anchor_norm_sq', None, persistent=False)

    def forward(self, psi):
        # psi: [B, T, psi_dim], anchors: [V, psi_dim]
        #
        # We need: logits_y = -||Psi - A[y]||^2
        # Expand:  -||Psi||^2 + 2*Psi^T*A[y] - ||A[y]||^2
        #
        # This avoids allocating the [B, T, V, psi_dim] diff tensor,
        # which would blow GPU RAM at scale (e.g., V=50k, psi_dim=256
        # -> 50GB per batch element per timestep).

        anchor_norm_sq = (self.anchors ** 2).sum(dim=-1)  # [V]
        psi_norm_sq = (psi ** 2).sum(dim=-1, keepdim=True)  # [B, T, 1]
        dot = psi @ self.anchors.T                         # [B, T, V] (fast GEMM)

        logits = (2 * dot - anchor_norm_sq - psi_norm_sq) / self.temperature
        return logits  # [B, T, V]
```

**Why not the naive form?** The naive `psi.unsqueeze(2) - anchors`
allocates a `[B, T, V, psi_dim]` tensor. For V=50k and psi_dim=256,
that's ~50GB per batch element -- completely impractical. The algebraic
expansion uses a `[B, T, V]` matmul (standard GEMM, same as `lm_head`)
plus two cheap norm computations.

**Compute cost:** O(V * d_psi) per token -- same order as the current
`nn.Linear(embed_dim, vocab_size)` which is also O(V * embed_dim). If
d_psi < embed_dim, it's actually cheaper. Memory cost is also identical.

### 3.4 Weight Tying Consideration

The current architecture optionally ties `lm_head.weight = token_embed.weight`
(lines 5832-5835). With anchor-based emission, weight tying takes a different
form:

- **Option A:** `anchors = token_embed.weight` (use raw embeddings as anchors).
  Simple but **dangerous**: the embedding space is optimized for *encoding*
  (input representation), not *emission* (distance-based prediction). Weight
  tying works in standard LMs because the head uses dot-product similarity
  in the same space. Anchor emission uses *distance geometry*, which imposes
  different structural requirements. Locking anchors to encoding geometry
  can cripple emission learning.
- **Option B:** `anchors = normalize(P(token_embed.weight))` where P is a
  learned low-rank projection from embed_dim to psi_dim. Preserves semantic
  initialization from embeddings while allowing emission geometry to diverge.
  Parameter cost: one `[embed_dim, psi_dim]` matrix (~200K params for
  768->256).
- **Option C:** Independent anchors. Most expressive but doubles vocabulary
  parameters (~12.8M for V=50k, psi_dim=256).

**Recommendation: Start with Option B (projected tying) as default.** It
provides semantic initialization without geometry lock-in. Option A is a
valid ablation to test whether the projection is necessary, but should not
be the default.

```python
# Option B initialization
self.anchor_proj = nn.Linear(embed_dim, psi_dim, bias=False)
# During forward:
anchors = F.normalize(self.anchor_proj(token_embed.weight), dim=-1)
```

---

## 4. What Spanda Adds That Does Not Exist Today

### 4.1 State Persistence Across Emission

Current flow: the emission *parameterization* has no explicit trajectory
state. Any temporal continuity in logits is implicit in `h_t` (which
carries context through attention). But the emission function itself --
`lm_head(h_t)` -- is a stateless linear projection applied independently
at each timestep:

```
h_1 -> logits_1     (no emission-level memory)
h_2 -> logits_2     (no emission-level trajectory)
h_3 -> logits_3
```

Note: `h_t` itself depends on all prior tokens through attention, so
there *is* temporal memory in the system. The point is that the emission
layer adds no additional trajectory structure beyond what `h_t` already
carries. Each `lm_head(h_t)` is a memoryless function of its input.

Spanda adds:

```
Psi_0 -> Psi_1 -> Psi_2 -> Psi_3
              \         \         \
            emit_1    emit_2    emit_3
```

The emission point now has memory. This is distinct from what the 32D
Sovereign State provides -- that state modulates *attention* (how the
model reads), while Psi modulates *emission* (what the model says).

### 4.2 Trajectory Smoothness

Current: no regularization on consecutive emission decisions.

Spanda adds two regularizers:

```
L_step   = alpha * ||Delta_Psi_t||^2          # penalize large jumps
L_smooth = beta  * ||Delta_Psi_t - Delta_Psi_{t-1}||^2  # penalize jerk
```

These have no analogue in the current loss landscape. The closest existing
mechanism is `KoshaGyroscopicLoss` (line 1, `losses/kosha_gyroscope.py`),
which enforces homeostatic balance on the 32D Sovereign State -- but that
operates on the *control plane*, not the emission plane.

### 4.3 Geometric Interpretability

Current: `logit_y = h^T W_y` -- meaning is encoded in dot-product similarity
between hidden state and a column of the weight matrix. Geometry is implicit.

Spanda: `logit_y = -||Psi - A[y]||^2` -- tokens are points in space, and
probability is explicitly a function of distance. You can *visualize* the
emission landscape, measure inter-token distances, identify semantic clusters
in anchor space directly.

---

## 5. What Spanda Does NOT Add

### 5.1 No Expressivity Expansion

Any function computable by `softmax(-||Psi - A||^2)` can be approximated
by a sufficiently wide linear layer + softmax. The function class is the same.

What changes is **inductive bias**: the model is biased toward smooth
trajectories and geometric token neighborhoods. This is a structural prior,
not additional capacity.

### 5.2 No Fundamental Compute Change

- One additional vector state (d_psi floats per batch element).
- One MLP for Delta_Psi (same size as existing `state_projector`).
- Emission cost remains O(V * d_psi) -- comparable to O(V * d_model).
- Softmax head is identical.

The only new cost is the MLP for Delta_Psi, which is negligible relative
to the transformer backbone.

---

## 6. Risks and Failure Modes

### 6.1 State Drift

Psi accumulates: `Psi_{t+1} = Psi_t + Delta_Psi_t`. Without constraint,
`||Psi||` can grow unboundedly, pushing all logits toward zero (since
distances grow quadratically).

**v0.1 default: bounded integrator (leaky + LayerNorm).** Drift must be
prevented structurally in the update rule, not only via loss penalties.
Loss-based mitigation (L_step, L_smooth) requires careful weight tuning
and can fail silently on long sequences. Structural bounds are robust.

The default v0.1 update rule is:

```
Psi_{t+1} = LayerNorm(gamma * Psi_t + Delta_Psi_t)
```

With `gamma = 0.99` (matching existing `decay_gamma` at line 5794).

This provides:
- **Leaky integration** (`gamma < 1`): exponential forgetting prevents
  unbounded accumulation. Information half-life ~69 steps.
- **LayerNorm**: normalizes Psi to unit variance at each step, preventing
  norm blowup without tuning regularizer weights.

Together they make Psi structurally bounded regardless of sequence length.

**L_step and L_smooth are optional additions** (see Section 4.2) that
provide gradient-level smoothness incentives. They should be added only
after the base hybrid is confirmed working with cross-entropy alone.

**Alternative mitigations** (not default, available for ablation):
- Hard clamp: `Psi = tanh(Psi)` (matching the RESERVED_RANGE constraint
  in `SovereignStateProjector._apply_constraints()`, line 199).
- L2 projection to sphere: `Psi = Psi / ||Psi||` (loses magnitude info).

### 6.2 Anchor Collapse

If anchors are learnable and unconstrained, they can collapse to a single
point, making all tokens equidistant and emission uniform. This is the
geometric analogue of mode collapse.

**Mitigation:** Anchor decorrelation loss, similar to VICReg variance
term already used in `KoshaGyroscopicLoss` (line 13 mentions VICReg).

### 6.3 Interaction with Phase Rotation

The 32D Sovereign State already modulates attention via Bhava delta -> phase
rotation (lines 3958-3967). Adding Psi as a separate state that modulates
emission creates two interacting dynamical systems. If poorly coupled, they
could oscillate or fight.

**Mitigation:** Keep them functionally orthogonal:
- Sovereign State S[32] feeds *only* attention (phase rotation + binding annotation).
- Spanda Psi feeds *only* emission (anchor distance).
- No direct coupling losses between S and Psi.

**Gradient policy:** Both S and Psi branches backpropagate into the shared
backbone (`h_t`). True gradient isolation via `stop_gradient` on either
branch would prevent that branch from influencing backbone learning, which
is likely undesirable (the backbone should adapt to serve both consumers).

The default is: **shared backbone gradients, no cross-coupling losses.**
Only introduce `stop_gradient` if training shows oscillation between the
two dynamical systems. This is a tunable knob, not a hard architectural
constraint.

### 6.4 Sequential Bottleneck

Psi state is sequential: `Psi_{t+1}` depends on `Psi_t`. This prevents
parallelization across time during training. However:
- The transformer backbone is already parallel (all of h_1..h_T computed at once).
- Only the Psi accumulation is sequential.
- This is identical to the existing `compute_state_delta()` pattern, which
  already has this constraint (lines 4070-4087).

For training, the Psi accumulation can be computed as a cumulative sum:
`Psi_t = sum(Delta_Psi_1..t)` which is parallelizable via `torch.cumsum`.

---

## 7. Attention Agnosticism

### 7.1 Separation of Concerns

Spanda operates at the **state / emission layer**, not the attention
computation layer. The two concerns are orthogonal:

| Layer | Controls | Complexity |
|-------|----------|------------|
| Attention | How context tokens interact across the sequence | O(L^2), O(L), O(L*w) |
| Spanda | How hidden state evolves and maps to output tokens | O(d_psi) per step |

The interface is clean:

```
h_t = AnySequenceModel(x_<=t)     # attention type determines this
Delta_Psi_t = f_theta(h_t)        # Spanda consumes h_t, agnostic to source
Psi_{t+1} = Psi_t + Delta_Psi_t   # state evolution, no attention dependency
z_y = -||Psi_{t+1} - A[y]||^2     # emission, no attention dependency
```

### 7.2 Compatibility with All Existing Backbones

Every transformer variant in `phase_transformer.py` produces `h_t` through
the same interface (`x = self.norm(x)` after the block stack). Spanda
consumes that output identically regardless of how it was computed:

| Model (line) | Attention Type | Spanda Compatible? |
|--------------|---------------|-------------------|
| `PhaseTransformer` (5773) | O(L) phase sync | Yes |
| `StandardTransformer` (7188) | O(L^2) quadratic | Yes |
| `HybridPhaseTransformer` (6029) | Local + Phase | Yes |
| `LocalOnlyTransformer` (7021) | O(L*w) sliding window | Yes |
| `GroupedHybridTransformer` (5130) | Grouped hybrid | Yes |
| `BindingCacheTransformer` (3489) | Phase + Top-K | Yes |
| `OntologicalBindingCacheTransformer` (3854) | Phase + Ontological | Yes |
| `OntologicalHybridTransformer` (6692) | Ontological hybrid | Yes |

### 7.3 Performance Will Vary by Backbone

While Spanda runs on all backbones, the quality of `h_t` determines
effectiveness:

- **Quadratic attention** -- best long-range reasoning in h_t, so Psi
  receives the richest signal. Spanda adds trajectory structure on top
  of already-strong context.
- **Linear attention** -- efficient but may lose subtle long-range
  interactions. Spanda's state persistence partially compensates by
  carrying forward semantic signal that attention dropped.
- **Local attention** -- strong locality, weaker global coherence.
  Spanda becomes *more* valuable here because local attention forgets
  long context, and Psi's accumulation provides a persistent memory
  channel at the emission layer.

**Spanda cannot compensate for a weak backbone.** It adds trajectory
regularization, not missing context. But for local/linear backbones,
the persistent Psi state provides a complementary long-range channel
that the attention mechanism lacks.

### 7.4 The Strategic Research Question

The interesting experiment is not "Does Spanda work on all backbones?"
(it does trivially, by construction).

The question is:

> **Does Spanda reduce reliance on quadratic attention for long-range
> coherence?**

If Spanda + O(L) Phase backbone achieves coherence comparable to
Spanda + O(L^2) Standard backbone, that is a meaningful result: it
means trajectory-level state persistence can partially substitute for
full quadratic context.

This is testable: compare `PhaseTransformer + Spanda` vs
`StandardTransformer + Spanda` on long-range coherence benchmarks
(binding benchmark, needle-in-haystack).

---

## 8. Integration with Existing Architecture

### 8.1 Affected Models

Start with **two** models to test attention-agnosticism from day one:

1. **`PhaseTransformer`** (line 5773) -- O(L) backbone. Simplest
   architecture, cleanest baseline. Tests whether Spanda helps when
   attention is efficient but limited.
2. **`StandardTransformer`** (line 7188) -- O(L^2) backbone. Full
   quadratic attention. Tests whether Spanda adds value even when
   the backbone already has full context.

Do NOT start with `OntologicalBindingCacheTransformer` -- it has two-pass
architecture, binding annotators, and the 32D Sovereign State, all of
which add confounders.

### 8.2 Minimal Diff

The implementation would touch:

1. **New module:** `SpandaState` (MLP + accumulator, ~30 lines).
2. **New emission:** `AnchorEmission` (distance computation, ~20 lines).
3. **Modified forward:** Replace `self.lm_head(x) * self.logit_scale` with
   `self.anchor_emit(self.spanda(x))`.
4. **Modified loss:** Add `L_step` and `L_smooth` to total loss.
5. **Config:** Add `psi_dim`, `alpha`, `beta` parameters.

Estimated: ~100 lines of new code, ~20 lines of modified code.

### 8.3 Suggested Module Location

```
symbolu/
  spanda/
    __init__.py
    state.py          # SpandaState module
    emission.py       # AnchorEmission module
    regularizers.py   # L_step, L_smooth
```

Or, more conservatively, add directly to `phase_transformer.py` alongside
the existing `StateDeltaPredictor` (line 5838).

### 8.4 Training Configuration

Starting hyperparameters (from the proposal):

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `psi_dim` | 256 | Smaller than embed_dim (768), reduces emission cost |
| `R` (vritti modes) | 8 | Structured Psi decomposition (later, not v0.1) |
| `alpha` (step reg) | 1e-4 | Gentle constraint on Delta_Psi magnitude |
| `beta` (smooth reg) | 1e-4 | Gentle constraint on Delta_Psi jerk |
| `decay_gamma` | 0.99 | Leaky integration to prevent drift |

---

## 9. Evaluation Protocol

### 9.1 Metrics

Compare Spanda-Softmax hybrid vs. baselines across backbone types:

1. **Perplexity** -- primary metric, must not regress.
2. **Coherence** -- measure topic drift over long generations. Use existing
   binding benchmark infrastructure (`resonant_model/run_benchmark.py`).
3. **Repetition rate** -- Spanda's trajectory smoothness should reduce
   degenerate repetition, but could also *increase* it if over-regularized.
4. **Stability across seeds** -- run with 3+ seeds, measure variance.
5. **Psi trajectory visualization** -- plot Psi evolution over generation
   to verify smooth, interpretable trajectories.
6. **Anchor space analysis** -- visualize A[y] clusters, measure
   inter-token distances, verify semantic structure.

### 9.2 Ablation Plan

**Component ablations** (on PhaseTransformer):

1. Full hybrid (Psi state + anchor emission + regularizers).
2. Anchor emission only (no Psi state -- emit from h_t directly with distance).
3. Psi state only (accumulated state but still linear lm_head projection).
4. Regularizers only (add L_step/L_smooth to standard model, no geometric emission).

This separates the contribution of each component.

**Backbone ablations** (full hybrid on each):

5. PhaseTransformer + Spanda (O(L) + state trajectory).
6. StandardTransformer + Spanda (O(L^2) + state trajectory).
7. PhaseTransformer baseline (O(L), no Spanda).
8. StandardTransformer baseline (O(L^2), no Spanda).

Comparing (5) vs (6) answers: does Spanda compensate for reduced attention?
Comparing (5) vs (7) and (6) vs (8) answers: does Spanda help at all?

The most interesting outcome would be: (5) approaches (8) -- meaning Spanda
+ linear attention rivals quadratic attention alone for coherence.

### 9.3 Spanda-Specific Diagnostics

These diagnostics are unique to the hybrid and must be logged during
training and evaluation to catch failure modes early.

**Emission continuity vs backbone continuity:**

Measure at each timestep:
- `cosine(Psi_t, Psi_{t+1})` -- emission trajectory smoothness.
- `cosine(h_t, h_{t+1})` -- backbone hidden state smoothness.

If Spanda is working, emission continuity should be *higher* than
backbone continuity (Psi adds smoothness). If they track identically,
the Psi accumulator is adding nothing. If emission continuity is *lower*,
something is wrong (the MLP is injecting noise).

Log as time series during training. Plot distribution over sequences
at evaluation.

**Anchor geometry sanity checks:**

Compute periodically (every N training steps):
- **Anchor norm distribution:** `||A[y]||` for all y. Should be roughly
  uniform if using normalized anchors. Skew indicates collapse direction.
- **Pairwise cosine similarity histogram:** Sample ~1000 anchor pairs,
  compute `cos(A[i], A[j])`. Should be roughly uniform on [-1, 1] for
  a well-structured space. A spike near 1.0 indicates collapse.
- **Anchor collapse metric:** Mean nearest-neighbor distance among
  anchors. If this drops below a threshold (e.g., 0.01 * mean pairwise
  distance), anchors are collapsing and decorrelation intervention is
  needed.
- **Psi-anchor coverage:** What fraction of anchors are "active" (closest
  anchor to some Psi_t during a validation pass)? Dead anchors indicate
  the emission space is underutilized.

These catch anchor collapse (Section 6.2) early enough to intervene.

### 9.4 Regularizer Staging Protocol

Regularizers (L_step, L_smooth) should NOT be enabled in the initial
training runs. The staging order is:

1. **Phase 1:** Cross-entropy only + bounded integrator (leaky + LN).
   Confirm the hybrid trains and does not regress on perplexity.
2. **Phase 2:** Add L_step (alpha=1e-4). Confirm trajectory smoothness
   improves without perplexity regression.
3. **Phase 3:** Add L_smooth (beta=1e-4). Confirm jerk reduction without
   over-smoothing (which would manifest as increased repetition).

This prevents blaming regularization for base architecture failures.

### 9.5 Dataset

Use the same training data as current Phase Transformer benchmarks
(WikiText-2/103 via `TextDataset` or `FineWebStreamingDataset`).

---

## 10. Ontology Blocks (Future, Not v0.1)

The proposal mentions structuring Psi into sub-blocks:

```
Psi = [Psi^phon, Psi^mode, Psi^ontology]
```

This aligns with the existing Sovereign State decomposition:

```
S = [S^bhava[12], S^kosha[5], S^vritti[5], S^guna[6], S^reserved[4]]
```

If Psi proves useful, a natural extension is:

```
Psi = [Psi^semantic[d1], Psi^syntactic[d2], Psi^pragmatic[d3]]
```

Where each sub-block has its own regularization characteristics. But this
is future work -- v0.1 should use a flat Psi vector.

---

## 11. What NOT To Do

1. **Do not remove softmax.** It provides stability, gradient flow, and
   calibrated probabilities. The hybrid adds to it, not replaces it.
2. **Do not jump to hyperbolic geometry.** Euclidean distance is sufficient
   for v0.1. Hyperbolic embeddings add complexity with uncertain benefit.
3. **Do not introduce lattices or CVP.** Discrete geometric structures
   are incompatible with gradient-based training. The anchor table is
   continuous and differentiable.
4. **Do not add rounding during training.** Quantization of Psi would
   destroy gradients. Keep everything continuous.
5. **Do not couple Psi with the 32D Sovereign State.** They serve different
   purposes (emission vs. attention). Keep them functionally separate.
6. **Do not start with OntologicalBindingCacheTransformer.** Too many
   moving parts. Start with PhaseTransformer + StandardTransformer.
7. **Do not store Psi as module-level mutable state.** No
   `register_buffer('prev_psi', ...)` -- Psi must be computed per-sequence
   via cumsum/scan. Module-level state breaks batched training, DDP, and
   teacher forcing (see Section 3.2).
8. **Do not compute emission via explicit diff tensor.** The naive
   `psi.unsqueeze - anchors.unsqueeze` allocates [B,T,V,d] and blows
   GPU RAM. Use the algebraic matmul form (see Section 3.3).
9. **Do not tie anchors directly to embedding weights (Option A).**
   Distance geometry has different structural requirements than dot-product
   similarity. Use projected tying (Option B) as default.
10. **Do not enable regularizers before confirming base hybrid works.**
    L_step and L_smooth should be staged in after cross-entropy-only
    training succeeds (see Section 9.4).

---

## 12. Summary Position

The Spanda-Softmax hybrid is a well-motivated inductive bias change. It
does not expand the function class but provides:

- Explicit state trajectory at the emission layer.
- Geometric interpretability of token prediction.
- Trajectory smoothness as a regularizable quantity.
- Attention-agnostic design: works on all 8 existing backbone variants.

The codebase is structurally ready: `compute_state_delta()` already
implements the accumulation pattern, `SovereignStateProjector` provides
the MLP template, and `KoshaGyroscopicLoss` demonstrates how to add
regularization objectives.

The implementation is minimal (~100 new lines) and non-destructive
(existing architectures unchanged). Spanda is orthogonal to attention
complexity -- it consumes `h_t` regardless of how it was computed.

The key research question is not compatibility but consequence:
**Does Spanda reduce reliance on quadratic attention for long-range
coherence?** The backbone ablation plan (Section 9.2, experiments 5-8)
is designed to answer this directly.

**This is an evaluation document. Implementation should proceed only
after review and approval.**
