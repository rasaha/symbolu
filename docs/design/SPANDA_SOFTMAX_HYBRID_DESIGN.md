# Spanda-Softmax Hybrid: Design Evaluation

**Version:** 0.4.1 (Evaluation Only -- No Implementation)
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
Psi_raw = gamma * Psi_t + Delta_Psi_t # leaky integration
Psi_{t+1} = Psi_raw / max(1, ||Psi_raw|| / c)  # norm clamping (preserves direction + magnitude up to c)

z_y = -||Psi_{t+1} - A[y]||^2         # distance to token anchors
p(y|Psi_{t+1}) = softmax(z_y / tau)   # softmax preserved, tau = temperature
```

Where `A[y]` are projected token anchors in R^d_psi (see Section 3.5),
`gamma` is a decay factor (default 0.99, tunable -- see Section 8.4),
`c` is the norm clamp ceiling (default `sqrt(d_psi)`), and `tau` is the
emission temperature (see Section 3.4).

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
        self.norm_clamp_c = math.sqrt(psi_dim)  # max allowed ||Psi||

    def _norm_clamp(self, psi):
        """Clamp Psi norm to ceiling c, preserving direction and magnitude below c."""
        # psi / max(1, ||psi|| / c)  -- identity when ||psi|| <= c, scales down otherwise
        norms = psi.norm(dim=-1, keepdim=True)  # [B, 1, 1] or [B, T, 1]
        scale = torch.clamp(norms / self.norm_clamp_c, min=1.0)
        return psi / scale

    def forward(self, h):
        # h: [B, T, D] -- full sequence of hidden states
        delta = self.delta_mlp(h)              # [B, T, psi_dim]

        # Leaky cumulative sum (bounded integrator)
        # Psi_t = gamma * Psi_{t-1} + Delta_t, then norm-clamped
        psi = torch.zeros_like(delta[:, :1, :])  # [B, 1, psi_dim]
        psi_seq = []
        for t in range(delta.size(1)):
            psi = self.decay_gamma * psi + delta[:, t:t+1, :]
            psi = self._norm_clamp(psi)
            psi_seq.append(psi)
        psi = torch.cat(psi_seq, dim=1)        # [B, T, psi_dim]

        return psi, delta   # psi: [B, T, psi_dim], delta: [B, T, psi_dim]
```

**Why norm clamping instead of LayerNorm:** LayerNorm normalizes variance
across dimensions at every step, destroying the absolute magnitude of Psi.
Since emission uses distance `||Psi - A||^2` (which depends on both
direction *and* magnitude), LN effectively collapses the emission to
`Psi^T A[y]` -- a disguised dot-product head. Norm clamping preserves
magnitude information up to a ceiling `c`, preventing drift while keeping
the distance-based emission geometrically meaningful. See Section 6.1 for
the full rationale and alternatives.

**Training:** The leaky cumsum can be parallelized via associative scan
(see Section 6.4 for scan optimization plan). For typical sequence lengths
(T <= 512), the sequential loop is fast enough since the bottleneck is the
backbone.

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
    def __init__(self, vocab_size, psi_dim):
        super().__init__()
        self.anchors = nn.Parameter(torch.randn(vocab_size, psi_dim))
        # Learnable temperature, log-parameterized to stay positive
        self.log_temperature = nn.Parameter(
            torch.tensor(math.log(psi_dim / 30.0))
        )

    def forward(self, psi):
        # psi: [B, T, psi_dim], anchors: [V, psi_dim]
        #
        # We need: logits_y = -||Psi - A[y]||^2 / tau
        # Expand:  (-||Psi||^2 + 2*Psi^T*A[y] - ||A[y]||^2) / tau
        #
        # This avoids allocating the [B, T, V, psi_dim] diff tensor,
        # which would blow GPU RAM at scale (e.g., V=50k, psi_dim=256
        # -> 50GB per batch element per timestep).

        tau = self.log_temperature.exp()

        # Normalize anchors to unit norm (eliminates anchor norm drift)
        anchors = F.normalize(self.anchors, dim=-1)         # [V, psi_dim]

        anchor_norm_sq = torch.ones(anchors.size(0),
                                    device=anchors.device)   # [V] = 1.0
        psi_norm_sq = (psi ** 2).sum(dim=-1, keepdim=True)  # [B, T, 1]
        dot = psi @ anchors.T                                # [B, T, V]

        logits = (2 * dot - anchor_norm_sq - psi_norm_sq) / tau
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

### 3.4 Temperature and Logit Scale Calibration

The current model uses `logit_scale = 1 / sqrt(sqrt(embed_dim))` (~0.19 for
d=768). The anchor emission replaces this with a temperature parameter `tau`
that divides the squared-distance logits. These must be calibrated to produce
logits in a comparable range, otherwise perplexity comparisons are meaningless.

**The calibration problem:** Anchor emission logits are:

```
z_y = (-||Psi||^2 + 2*Psi^T*A[y] - ||A[y]||^2) / tau
```

The magnitude of `z_y` depends on:
- `||Psi||`: controlled by norm clamping (max `c = sqrt(d_psi)`).
- `||A[y]||`: controlled by anchor normalization policy (see below).
- `d_psi`: higher dimensions -> larger norms and dot products.

If anchors and Psi have uncontrolled norms, logit scale drifts during
training, making loss comparisons across runs unreliable.

**v0.1 default: unit-norm anchors + calibrated temperature.**

1. **Normalize anchors to unit norm** at every forward pass:
   ```python
   anchors_normed = F.normalize(self.anchors, dim=-1)  # ||A[y]|| = 1 for all y
   ```
   This eliminates `||A[y]||^2` variation. The `||A[y]||^2` term becomes
   a constant (1.0) across all vocabulary items.

2. **Temperature** `tau` is set to produce logits in a range comparable to
   the existing linear head. With unit-norm anchors and Psi norm-clamped
   to `c = sqrt(d_psi)`:
   - Max `||Psi||^2` = `d_psi` (e.g., 256).
   - Max `|Psi^T A[y]|` ~ `sqrt(d_psi)` (for unit-norm A, norm-clamped Psi).
   - Max `|z_y|` before temperature ~ `2*sqrt(d_psi) + d_psi + 1`.
   - For d_psi=256: max ~289. Standard logits are O(10-50).
   - Therefore `tau = d_psi / target_logit_range`. With target ~30:
     `tau ~= d_psi / 30 ~= 8.5`.

   In practice, **initialize `tau` as a learnable scalar** (log-parameterized
   to stay positive), initialized to `d_psi / 30`:
   ```python
   self.log_temperature = nn.Parameter(torch.tensor(math.log(psi_dim / 30.0)))
   # In forward: tau = self.log_temperature.exp()
   ```

   A learnable temperature lets the model calibrate its own logit scale
   during training. The initialization ensures reasonable logits from step 1.

3. **Monitoring:** Log `tau` value, mean logit magnitude, and logit
   standard deviation during training. If tau diverges (grows > 100 or
   shrinks < 0.1), the anchor/Psi geometry is miscalibrated.

### 3.5 Weight Tying Consideration

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

### 6.1 State Drift and Norm Management

Psi accumulates: `Psi_{t+1} = gamma * Psi_t + Delta_Psi_t`. Without
constraint, `||Psi||` can grow unboundedly, pushing all logits toward zero
(since distances grow quadratically).

**v0.1 default: bounded integrator (leaky + norm clamping).** Drift must
be prevented structurally in the update rule, not only via loss penalties.
Loss-based mitigation (L_step, L_smooth) requires careful weight tuning
and can fail silently on long sequences. Structural bounds are robust.

The default v0.1 update rule is:

```
Psi_raw = gamma * Psi_t + Delta_Psi_t
Psi_{t+1} = Psi_raw / max(1, ||Psi_raw|| / c)
```

With `gamma = 0.99` (tunable, see Section 8.4) and `c = sqrt(d_psi)`.

This provides:
- **Leaky integration** (`gamma < 1`): exponential forgetting prevents
  unbounded accumulation. Information half-life ~69 steps at gamma=0.99.
- **Norm clamping**: caps `||Psi||` at ceiling `c` while preserving both
  direction and magnitude for `||Psi|| <= c`. This is *not* normalization
  -- Psi can have any magnitude up to `c`, preserving the magnitude channel
  that distance-based emission requires.

Together they make Psi structurally bounded regardless of sequence length,
while preserving the geometric properties needed for distance-based emission.

**Why NOT LayerNorm:** LayerNorm normalizes variance across dimensions at
every step, which destroys absolute magnitude information. Since emission
computes `-||Psi - A||^2` (distance depends on both direction and
magnitude), applying LN every step forces `||Psi||` to a near-constant
value. This reduces the emission to approximately `Psi^T A[y]` -- a
disguised dot-product head, erasing the geometric advantage. The magnitude
channel carries information (e.g., "how committed" the model is to the
current trajectory region) that distance-based emission can exploit but
LN would destroy.

**Optional weak norm penalty:** As an alternative or supplement to norm
clamping, a soft L2 penalty on Psi norm can be added:

```
L_norm = lambda_norm * ||Psi||^2
```

This gently discourages large norms without hard truncation. Suggested
`lambda_norm = 1e-5`. This is an ablation-stage addition, not a v0.1
default.

**L_step and L_smooth are optional additions** (see Section 4.2) that
provide gradient-level smoothness incentives. They should be added only
after the base hybrid is confirmed working with cross-entropy alone.

**Alternative mitigations** (not default, available for ablation):
- Hard clamp: `Psi = tanh(Psi)` (matching the RESERVED_RANGE constraint
  in `SovereignStateProjector._apply_constraints()`, line 199).
- L2 projection to sphere: `Psi = Psi / ||Psi||` (loses magnitude info,
  explicitly not recommended -- collapses back to dot-product).
- RMSNorm: preserves mean shift better than LayerNorm but still destroys
  absolute scale. Not recommended for v0.1 but available for ablation.

### 6.2 Anchor Collapse

If anchors are learnable and unconstrained, they can collapse to a single
point, making all tokens equidistant and emission uniform. This is the
geometric analogue of mode collapse.

**v0.1 default: unit-norm anchors.** The simplest and most robust
mitigation is to normalize anchors to unit norm at every forward pass
(already specified in Section 3.3 and 3.4). This:
- Prevents norm explosion (anchors cannot drift to arbitrary scale).
- Prevents norm collapse (anchors cannot shrink to zero).
- Forces all differentiation into angular structure (direction on the
  unit hypersphere), which is well-behaved for gradient descent.

This alone prevents the most dangerous failure mode (all anchors
converging to the same point with the same norm).

**Phase 2: VICReg-style decorrelation (optional, for ablation).**

If unit-norm anchors alone are insufficient (detected via the anchor
geometry diagnostics in Section 9.3), add explicit decorrelation:

```python
def anchor_decorrelation_loss(anchors_normed, eps=1e-4):
    """VICReg-inspired variance + covariance regularization on anchors.

    anchors_normed: [V, psi_dim], assumed unit-norm (from forward pass).
    Computed on a random subsample of S anchors to keep cost O(S^2 * d).
    """
    S = min(1024, anchors_normed.size(0))
    idx = torch.randperm(anchors_normed.size(0))[:S]
    A = anchors_normed[idx]  # [S, d]

    # Variance term: each dimension should have non-trivial variance
    # across anchors. Penalize dimensions with std < eps.
    std = A.std(dim=0)  # [d]
    L_var = torch.clamp(eps - std, min=0).sum()

    # Covariance term: off-diagonal correlations between dimensions
    # should be small. Encourages diverse anchor directions.
    A_centered = A - A.mean(dim=0)
    cov = (A_centered.T @ A_centered) / (S - 1)  # [d, d]
    # Zero out diagonal (we only penalize off-diagonal)
    off_diag = cov - torch.diag(cov.diag())
    L_cov = (off_diag ** 2).sum() / A.size(1)

    return L_var + L_cov
```

Add to total loss as `lambda_anchor * anchor_decorrelation_loss(...)` with
`lambda_anchor = 1e-3`. Enable only after Phase 1 training confirms
base hybrid works (see Section 9.4).

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

### 6.4 Sequential Bottleneck and Scan Optimization

Psi state is sequential: `Psi_{t+1} = gamma * Psi_t + Delta_t`. This
prevents full parallelization across time during training. However:
- The transformer backbone is already parallel (all of h_1..h_T computed at once).
- Only the Psi accumulation is sequential.
- This is identical to the existing `compute_state_delta()` pattern, which
  already has this constraint (lines 4070-4087).

**Performance at scale:** At T=2048, a Python for-loop over timesteps is
unacceptable. The scan adds O(T * B * d_psi) sequential work. For
T=512, d_psi=256, B=32, this is ~4M ops per step * 512 steps -- marginal.
For T=2048+, it becomes a training bottleneck.

**Scan optimization plan (by sequence length):**

| T range | Strategy | Implementation |
|---------|----------|---------------|
| T <= 512 | Python loop | Current implementation (Section 3.2). Adequate because backbone is the bottleneck. |
| 512 < T <= 2048 | Parallel associative scan | `torch.cumsum` with geometric weighting, or `torch._foreach` ops. The leaky recurrence `Psi_t = gamma * Psi_{t-1} + Delta_t` has a closed-form: `Psi_t = sum_{s=0}^{t} gamma^{t-s} * Delta_s`, which can be computed as a discounted cumsum: `Psi = discounted_cumsum(Delta, gamma)`. |
| T > 2048 | Fused CUDA scan | Custom Triton kernel or use existing implementations (e.g., `mamba_ssm.selective_scan_fn`). The recurrence is a simple first-order linear scan -- the same primitive that Mamba/S4 use, with mature fused implementations available. |

**Discounted cumsum formulation:**

```python
def discounted_cumsum(delta, gamma):
    """Parallel-friendly discounted cumulative sum.

    Psi_t = sum_{s=0}^{t} gamma^{t-s} * Delta_s

    For pure cumsum (gamma=1), this is just torch.cumsum.
    For gamma < 1, use log-space trick or associative scan.
    """
    T = delta.size(1)
    # Geometric weights: gamma^0, gamma^1, ..., gamma^{T-1}
    powers = gamma ** torch.arange(T, device=delta.device).float()
    # Multiply delta by gamma^{-t} to "undo" decay, cumsum, then re-apply
    # This is the standard parallel scan trick for first-order linear recurrences
    delta_scaled = delta / powers.unsqueeze(0).unsqueeze(-1)  # [B, T, d]
    cumsum = torch.cumsum(delta_scaled, dim=1)                # [B, T, d]
    psi = cumsum * powers.unsqueeze(0).unsqueeze(-1)          # [B, T, d]
    return psi
```

**Note on norm clamping with parallel scan:** The norm clamping step
(`Psi / max(1, ||Psi||/c)`) breaks the linear recurrence, preventing
pure parallel scan. Two options:
1. Apply norm clamping only at the output (after the full scan), not
   per-step. This is slightly less safe but enables full parallelization.
2. Keep per-step clamping with the sequential loop for T <= 512, switch
   to output-only clamping for longer sequences.

For v0.1, option 1 (output-only clamping with parallel scan) is the
recommended default for T > 512. The leaky integrator with gamma < 1
already provides the primary drift prevention; per-step clamping is a
secondary safety net.

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
effectiveness. **Spanda cannot recover information that the backbone
never captured.** Psi is a low-dimensional projection of `h_t` -- if
`h_t` lacks long-range structure (e.g., due to linear attention losing
subtle long-range interactions), Spanda cannot reconstruct it. It can
only smooth and accumulate what already exists in the hidden state
sequence.

- **Quadratic attention** -- best long-range reasoning in h_t, so Psi
  receives the richest signal. Spanda adds trajectory structure on top
  of already-strong context.
- **Linear attention** -- efficient but may lose subtle long-range
  interactions. Spanda's leaky accumulation can *smooth* the signal
  that `h_t` does carry, providing temporal inertia at the emission
  layer. Whether this smoothing materially improves coherence is an
  empirical question, not a design guarantee.
- **Local attention** -- strong locality, weaker global coherence.
  Spanda's accumulation provides a persistent memory channel, but its
  utility depends entirely on whether local `h_t` carries enough
  signal for accumulation to be meaningful.

**The hypothesis is that emission-layer accumulation adds value as a
complementary channel -- not that it compensates for backbone
limitations.** This distinction matters: "compensation" implies Spanda
recovers lost information, which it cannot. "Complementary channel"
implies it exploits a different axis (temporal smoothness at emission)
that the backbone does not explicitly optimize. The ablation plan
(Section 9.2) is designed to test whether this complementary channel
produces measurable improvements.

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
| `decay_gamma` | 0.99 | Leaky integration; half-life ~69 tokens (see below) |
| `norm_clamp_c` | sqrt(psi_dim) | Max allowed Psi norm; ~16 for psi_dim=256 |
| `temperature` (tau) | See Section 3.5 | Emission logit scaling |
| `lambda_norm` | 1e-5 | Optional soft norm penalty (ablation only) |

**Gamma tuning guidance:** The decay factor `gamma` controls how far back
the Psi trajectory "remembers." Half-life in tokens = `ln(2) / (1 - gamma)`:

| gamma | Half-life (tokens) | Character |
|-------|-------------------|-----------|
| 0.99  | ~69  | Short-range smoothing. Psi forgets within a paragraph. |
| 0.995 | ~138 | Medium-range. Psi carries signal across paragraphs. |
| 0.999 | ~693 | Long-range. Psi retains signal across document sections. |

The default 0.99 is conservative -- it prevents state accumulation issues
but may be too short for Spanda to provide meaningful long-range memory.
**Gamma is a primary ablation variable** (see Section 9.2). If Spanda's
value proposition is emission-layer memory, higher gamma values are where
that value is most likely to manifest. The 0.99 default should be treated
as a stability baseline, not as the expected best value.

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

Comparing (5) vs (6) answers: does Spanda help more when attention is limited?
Comparing (5) vs (7) and (6) vs (8) answers: does Spanda help at all?

**Hyperparameter ablations** (on PhaseTransformer + Spanda):

9.  gamma = 0.99  (half-life ~69 tokens, stability baseline).
10. gamma = 0.995 (half-life ~138 tokens).
11. gamma = 0.999 (half-life ~693 tokens).
12. Norm clamping vs LayerNorm vs no normalization.
13. Norm clamp ceiling c: sqrt(psi_dim) vs 2*sqrt(psi_dim) vs fixed 10.0.

Gamma is the most important hyperparameter for testing the hypothesis that
emission-layer memory adds value. If only gamma=0.99 is tested, and Spanda
shows no benefit, the experiment is inconclusive -- the memory may simply
have been too short-lived to matter.

**Critical control: trivial logit smoothing baseline.**

14. Logit-smoothed baseline (no Spanda geometry):
    ```python
    z_t = W @ h_t                        # standard linear head
    z_t_smooth = gamma * z_{t-1} + z_t   # temporal smoothing on logits
    p(y) = softmax(z_t_smooth / tau)
    ```

This isolates whether temporal smoothing alone (applied directly to logits,
no geometric emission, no Psi state, no anchor space) captures the same
benefit. If experiment 14 performs comparably to the full Spanda hybrid,
then the geometric emission parameterization adds no structural value --
the benefit was entirely from temporal inertia, which can be achieved
trivially. This control is scientifically necessary: without it, positive
Spanda results cannot be attributed to geometry vs. smoothing.

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

**Norm clamp saturation monitoring:**

When gamma is high (0.995+) and sequences are long, Psi may frequently
saturate against the norm clamp ceiling `c`. If that happens, the magnitude
channel is effectively destroyed -- Psi becomes direction-only, reducing
the emission advantage over dot-product heads.

Log at every training step:
- **Clamp saturation rate:** % of timesteps (across batch) where
  `||Psi_raw|| > c` (i.e., clamping was active). Compute as:
  ```python
  saturation_rate = (psi_raw.norm(dim=-1) > self.norm_clamp_c).float().mean()
  ```
- **Psi norm histogram:** Distribution of `||Psi||` across timesteps and
  batch elements. Should show spread across `[0, c]`, not a spike at `c`.
- **Effective magnitude entropy:** If Psi norms cluster tightly (low
  variance), the magnitude channel carries little information.

**Alert thresholds:**
- Clamp saturation > 30%: magnitude channel is being significantly
  compressed. Consider increasing `c` or decreasing `gamma`.
- Clamp saturation > 60%: Psi has effectively become direction-only.
  The geometric emission advantage over dot-product is largely nullified.
  Increase `c`, decrease `gamma`, or reconsider the norm management strategy.

This diagnostic is especially critical for the high-gamma ablations
(experiments 10-11 in Section 9.2), where saturation is most likely.

### 9.4 Regularizer Staging Protocol

Regularizers (L_step, L_smooth) should NOT be enabled in the initial
training runs. The staging order is:

1. **Phase 1:** Cross-entropy only + bounded integrator (leaky + norm clamp).
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

## 12. What This Design Actually Is

Stripped of naming and philosophy, this is:

**A first-order linear state-space model attached to the emission head.**

The core recurrence:

```
Psi_{t+1} = gamma * Psi_t + f(h_t)
```

is structurally identical to the state update in S4, Mamba, and linear
RNN augmentation -- but applied to emission rather than attention or
context mixing. The anchor-distance emission adds a geometric
parameterization on top of this state-space structure.

This framing matters because:
- It connects Spanda to a well-understood family of models (state-space
  models), not to speculative geometry.
- It identifies the genuinely novel component: applying SSM-style
  accumulation to the emission layer specifically, where standard LMs
  use a stateless linear projection.
- It clarifies what must be demonstrated: that emission-layer state
  persistence provides value that backbone-level state does not already
  capture.

**The two degrees of freedom Spanda adds over a standard linear head:**

1. **Temporal accumulation** -- Psi carries filtered history of h_t
   across timesteps. This is the primary hypothesis: does emission-layer
   memory add value?
2. **Radial confidence channel** -- With norm clamping, `||Psi||` encodes
   a scalar confidence energy that modulates all logits simultaneously
   (via the `-||Psi||^2` term in the emission). A standard dot-product
   head has no analogue of this. When `||Psi||` is small, all distances
   to anchors shrink and the distribution flattens (higher entropy). When
   `||Psi||` is large (near clamp ceiling), the distribution sharpens
   around the nearest anchors. This is a genuinely different degree of
   freedom from what standard softmax emission provides.

Whether either degree of freedom produces measurable improvement is
the empirical question this design exists to answer.

---

## 13. Summary Position

The Spanda-Softmax hybrid is a well-motivated inductive bias change. It
does not expand the function class but provides:

- Explicit state trajectory at the emission layer.
- Geometric interpretability of token prediction.
- A radial confidence channel with no dot-product analogue.
- Trajectory smoothness as a regularizable quantity.
- Attention-agnostic design: works on all 8 existing backbone variants.

The codebase is structurally ready: `compute_state_delta()` already
implements the accumulation pattern, `SovereignStateProjector` provides
the MLP template, and `KoshaGyroscopicLoss` demonstrates how to add
regularization objectives.

The implementation is minimal (~100 new lines) and non-destructive
(existing architectures unchanged). Spanda is orthogonal to attention
complexity -- it consumes `h_t` regardless of how it was computed.

There are two key research questions:

1. **Does emission-layer state persistence add value?** Compared to
   a stateless linear head, does Psi accumulation improve coherence or
   stability? (Experiments 1-8 in Section 9.2.)
2. **Does geometric emission add value beyond temporal smoothing?** If
   trivial logit smoothing (experiment 14) captures the same benefit,
   then the geometry is unnecessary and temporal inertia alone explains
   any improvement. This is the most important control.

The honest prior: the probability of dramatic improvement is low. The
probability of measurable stability gains in long-form generation is
moderate. The probability that high-gamma tuning reveals a useful
secondary memory channel is non-trivial. That makes it worth testing.

**This is an evaluation document. Implementation should proceed only
after review and approval.**

---

## Appendix A: Changelog

### v0.4.1 (2026-02-19) -- Experimental Controls & Honest Framing

Addressed second-round review. Changes:

1. **Added norm clamp saturation diagnostic.** Log % timesteps where
   `||Psi||` hits clamp ceiling. Alert thresholds at 30% (magnitude
   compressed) and 60% (effectively direction-only). Critical for
   high-gamma ablations. (Section 9.3)

2. **Added trivial logit-smoothing baseline (experiment 14).** A simple
   `z_t_smooth = gamma * z_{t-1} + z_t` applied to standard linear head
   logits. If this matches Spanda, geometry adds no value -- the benefit
   is entirely from temporal inertia. This is the most important control
   experiment. (Section 9.2)

3. **Added Section 12: "What This Design Actually Is."** Honest framing:
   Spanda is a first-order linear state-space model on the emission head.
   Identifies the two genuine degrees of freedom (temporal accumulation
   and radial confidence channel). Connects to S4/Mamba family. (Section 12)

4. **Updated summary** with honest probability priors on outcomes and
   explicit framing of the two research questions (state persistence value
   vs. geometry value). (Section 13)

### v0.4.0 (2026-02-19) -- Post-Review Refinements

Addressed external architectural review. Changes:

1. **Removed mandatory LayerNorm on Psi.** LN destroys magnitude channel,
   collapsing distance-based emission back to dot-product. Replaced with
   norm clamping (`Psi / max(1, ||Psi||/c)`) which preserves both direction
   and magnitude up to ceiling `c`. (Sections 2.2, 3.2, 6.1)

2. **Made gamma a primary tunable.** Added half-life table (0.99/0.995/0.999)
   and explicit guidance that 0.99 is a stability baseline, not expected
   optimum. Added gamma to ablation plan. (Sections 8.4, 9.2)

3. **Defined anchor normalization policy.** v0.1 default: unit-norm anchors
   at every forward pass. This prevents norm drift and simplifies temperature
   calibration. (Sections 3.3, 3.4, 6.2)

4. **Added temperature/logit scale calibration.** New Section 3.4 defines
   how learnable temperature `tau` is initialized relative to psi_dim and
   anchor/Psi norm ranges. (Section 3.4)

5. **Specified anchor collapse mitigation concretely.** Added explicit
   VICReg-style loss code (variance + covariance terms) with subsample
   strategy for cost control. Unit-norm anchors are the primary defense;
   VICReg is Phase 2 addition. (Section 6.2)

6. **Weakened "compensation" claims in Section 7.3.** Spanda cannot recover
   information the backbone never captured. Reframed as "complementary
   channel" hypothesis, not compensation guarantee. (Section 7.3)

7. **Added scan optimization plan for long T.** Defined strategy by sequence
   length (Python loop for T<=512, parallel discounted cumsum for T<=2048,
   fused CUDA scan for T>2048). Documented interaction between norm clamping
   and parallel scan. (Section 6.4)

### v0.3.0 (2026-02-19) -- Initial Mature Draft

- Eliminated module-level `prev_psi`; per-sequence computation.
- Memory-safe emission via algebraic expansion.
- Honest inductive bias framing.
- Shared backbone gradients, no cross-coupling losses.
- Evaluation protocol with emission continuity diagnostics.
