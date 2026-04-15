# Hard-Probes Feature Port: Design Document

## Executive Summary

This document specifies the integration of selected features from
`scripts/phase_probes/hard_probes/train_hard_probes.py` into the two
production training paths:

- **`mistral_cg`** — frozen Mistral backbone + Conscious Generation modules
  (Stages 0–8), wrapped by `MistralCGWrapper`
  (`symbolu_training/training/unified/mistral_wrapper.py`).
- **`mistral_hybrid`** — frozen Mistral backbone + trainable Phase attention
  layers, wrapped by `MistralHybridWrapper`
  (`symbolu_training/training/unified/mistral_hybrid_wrapper.py`).

The features selected are those that address **concrete failure modes** in
each target pipeline, not speculative enhancements. Research-only benchmark
harnesses from `train_hard_probes.py` are deliberately excluded.

### Priority Table

| Priority | Target          | Feature                                                  | Status in Repo               |
|----------|-----------------|----------------------------------------------------------|------------------------------|
| P0-1     | `mistral_cg`    | VICReg anti-collapse on Sovereign State projector        | Loss exists, not wired to CG |
| P0-2     | `mistral_hybrid`| Phase warmstart curve                                    | Absent in unified            |
| P1-1     | `mistral_cg`    | LSTB / CSR bridge supervision                            | Partial (lambda only)        |
| P1-2     | `mistral_hybrid`| Phase write-gate + multi-channel phase memory            | Absent in unified            |
| P2-1     | Both            | `LayerInfluenceDiagnostics`                              | Absent in unified            |
| P2-2     | `mistral_cg`    | Kosha gyroscopic loss (enabled-by-default for CG)        | Exists, off-by-default       |

This document is written **one priority at a time**. Later priorities will
be appended as sibling top-level sections (§2, §3, …).

---

## §1 P0-1 — VICReg Anti-Collapse on Sovereign State Projector (`mistral_cg`)

### 1.1 Problem Statement

The `mistral_cg` pipeline projects the pooled hidden state of a frozen
Mistral-7B backbone down to a **32-dimensional Sovereign State** vector
(`mistral_wrapper.py:103, :305`). This 32D vector is the architectural
bottleneck through which every downstream Conscious-Generation signal flows:
Bhava (12D slice), Kosha routing, Vritti token loss, CSR token loss, Guna
token loss, and the Stage 8 Perspective Synthesizer.

A 32D latent projected from 4096D input with only a handful of trainable
auxiliary losses pulling on it is the textbook setting for **representational
collapse**: the projector learns to map any input to a narrow cone (or a
single point), every downstream auxiliary loss plateaus at a trivial
solution, and LM perplexity appears to train normally because the main
cross-entropy path still flows through the frozen backbone and lm_head.

The failure is **silent**: LM loss goes down, CG lambda losses go down, but
the 32D state carries no information and the CG signals are fitting noise.
There is currently no mechanism in the unified training loop that prevents
this.

### 1.2 Current State in Repository

The building block already exists but is **not wired into the CG path**:

- **`VICRegLoss`** is fully implemented at
  `symbolu_training/jepa/losses.py:23`. It exposes a standard
  variance–invariance–covariance regularizer (Bardes et al.) with
  configurable `sim_coeff`, `std_coeff`, `cov_coeff`, and `var_threshold`.
- It is **imported** into the unified training loop at
  `symbolu_training/training/unified/train.py:236`, and a config weight
  `jepa_vicreg_weight` exists at
  `symbolu_training/training/unified/config.py:886`.
- However, a targeted `grep` of `mistral_wrapper.py` (the CG wrapper) and
  of the CG loss block at `train.py:4931+` returns **zero VICReg
  references**. VICReg is active only in the JEPA-pretraining code path,
  not on the Sovereign State projector used by `mistral_cg`.

The CG forward pass already exposes the attach point — the Sovereign State
is returned in the forward dict as `outputs['state']`, and the CG loss block
already extracts it:

```python
# symbolu_training/training/unified/train.py:4998–5000
if isinstance(outputs, dict):
    _cg_hidden = outputs.get('last_hidden_state', None)
    _cg_sov_state = outputs.get('state', None)
```

Everything needed to add a VICReg term on `_cg_sov_state` is in place; the
term itself is not computed.

### 1.3 Design Approach

**Goal:** add a variance + covariance regularization term on the 32D
Sovereign State vector produced by `MistralCGWrapper`, summed into the
total training loss with a configurable weight, active only when
`enable_conscious_generation=True`.

**Unary vs binary VICReg.** The existing `VICRegLoss.forward(x, y)` takes
two tensors because JEPA compares predicted vs target representations and
uses the invariance (MSE) term. Anti-collapse on a single Sovereign State
vector is a **unary** problem — only the variance and covariance terms
apply. Three options were considered:

| Option | Approach                                                       | Verdict |
|--------|----------------------------------------------------------------|---------|
| A      | Call `VICRegLoss(x, x.detach())` and accept MSE=0              | Rejected — confusing semantics at call site, pointless compute |
| B      | Add a `compute_collapse_only(x)` method on `VICRegLoss`        | **Chosen** — minimal surface area, single source of truth for the math |
| C      | New `AntiCollapseLoss` class in a new file                     | Rejected — duplicates math, more files to maintain |

**Chosen design (Option B):** extend `VICRegLoss` with one method that
returns variance + covariance only. No new class, no new file, no change
to existing `forward()` signature, so the JEPA path is unaffected.

```python
# symbolu_training/jepa/losses.py  (addition to existing VICRegLoss class)

def compute_collapse_only(
    self,
    x: torch.Tensor,
    return_components: bool = False,
) -> torch.Tensor:
    """Variance + covariance regularization for a single representation.

    Used for anti-collapse on latent projections (e.g. the 32D Sovereign
    State) where there is no paired target. Omits the invariance term.

    Args:
        x: [B, D] representation to regularize.
        return_components: if True, return dict with individual terms.
    """
    batch_size, num_features = x.shape

    std_x = torch.sqrt(x.var(dim=0) + 1e-4)
    std_loss = torch.mean(F.relu(self.var_threshold - std_x))

    x_centered = x - x.mean(dim=0)
    cov_x = (x_centered.T @ x_centered) / (batch_size - 1)
    cov_loss = self._off_diagonal(cov_x).pow(2).sum() / num_features

    total = self.std_coeff * std_loss + self.cov_coeff * cov_loss
    if return_components:
        return {'total': total, 'variance': std_loss, 'covariance': cov_loss}
    return total
```

### 1.4 Integration Points

**Three files touched:**

1. `symbolu_training/jepa/losses.py` — add `compute_collapse_only` method
   (shown above).
2. `symbolu_training/training/unified/config.py` — add two config fields
   alongside the existing CG lambda block (`~:998–1043`):
   ```python
   lambda_sovereign_anticollapse: float = 0.0  # VICReg var+cov on 32D state
   anticollapse_warmup_steps: int = 1000       # Linear ramp-in from 0
   ```
3. `symbolu_training/training/unified/train.py` — inside the existing CG
   loss block (`:4931+`), after `_cg_sov_state` is extracted at `:5000`,
   add the regularization term.

**Sketch of the call site** (conceptual; not a literal patch):

```python
# symbolu_training/training/unified/train.py — inside CG block, after line ~5000

if config.lambda_sovereign_anticollapse > 0 and _cg_sov_state is not None:
    # Linear warmup so the term does not dominate early optimization
    _ac_scale = min(
        1.0,
        max(0, global_step - resume_step) / max(1, config.anticollapse_warmup_steps),
    )
    _ac_weight = config.lambda_sovereign_anticollapse * _ac_scale

    if _ac_weight > 0:
        _ac_result = sovereign_anticollapse_loss.compute_collapse_only(
            _cg_sov_state, return_components=True,
        )
        _ac_loss = _ac_result['total']
        if torch.isfinite(_ac_loss):
            loss = loss + _ac_weight * _ac_loss
            metrics['cg_anticollapse_loss']  = _ac_loss.item()
            metrics['cg_anticollapse_var']   = _ac_result['variance'].item()
            metrics['cg_anticollapse_cov']   = _ac_result['covariance'].item()
            metrics['cg_anticollapse_scale'] = _ac_scale
```

`sovereign_anticollapse_loss` is a single `VICRegLoss(...)` instance created
once at trainer setup (near where other CG losses are instantiated, around
`train.py:2098` where `KoshaGyroscopicLoss` is constructed), with
coefficients chosen for collapse prevention (variance-dominant):
`sim_coeff=0.0, std_coeff=25.0, cov_coeff=1.0, var_threshold=1.0`.

### 1.5 Configuration Interface

**New CLI flags** (argparse block around `train.py:10218`):

```
--lambda_sovereign_anticollapse FLOAT   (default: 0.0)
    VICReg variance+covariance regularization weight on the 32D
    Sovereign State projector. Recommended: 0.01–0.05 for mistral_cg.
    Leave at 0.0 for non-CG training paths.

--anticollapse_warmup_steps INT         (default: 1000)
    Linear warmup steps for the anti-collapse term.
```

**Recommended setting for `scripts/train_mistral_cg.sh`:**
```bash
LAMBDA_ANTICOLLAPSE=0.02
# ... in the python train_unified_llm.py invocation:
    --lambda_sovereign_anticollapse "$LAMBDA_ANTICOLLAPSE" \
    --anticollapse_warmup_steps 1000 \
```

### 1.6 Risks and Mitigations

| Risk                                                         | Likelihood | Mitigation |
|--------------------------------------------------------------|------------|------------|
| Variance term dominates early training, destabilizing LM loss| Medium     | Linear warmup (`anticollapse_warmup_steps`); variance-only hinge already clips at threshold |
| Covariance term penalizes legitimate correlations between related Bhava dimensions | Low–Medium | Default weight kept small (`0.02`); `var_threshold=1.0` is standard VICReg setting, not aggressive |
| Small batch sizes produce noisy variance estimates           | Medium     | Document minimum effective batch size (≥16 recommended); warn at runtime if per-GPU batch < 8 |
| Active when user runs a non-CG pipeline by mistake           | Low        | Default is `0.0`; term is a no-op unless explicitly enabled; only documented in `train_mistral_cg.sh` |
| Interaction with existing `jepa_vicreg_weight` path          | Low        | Different config name, different code path, different call site — no collision |

### 1.7 Success Criteria

The port is considered successful if **all** of the following hold on a
1000-step `wikitext2` run of `scripts/train_mistral_cg.sh --dataset wikitext2
--max-steps 1000` with `--lambda_sovereign_anticollapse 0.02`:

1. **LM loss curve is within ±2% of baseline** (no anti-collapse) at step
   1000 — i.e. the new term does not degrade language modeling quality.
2. **Mean variance of the 32D Sovereign State is ≥ 0.8** across the eval
   set at step 1000, measured as
   `state.var(dim=0).mean()` over a full eval pass. Baseline runs should
   be spot-checked to confirm the collapse failure mode actually exists
   before claiming this metric moved.
3. **Off-diagonal covariance Frobenius norm decreases** monotonically from
   step 100 to step 1000 (logged metric: `cg_anticollapse_cov`).
4. **`cg_ont_loss`, `cg_kosha_routing_loss`, `cg_vritti_token_loss` curves
   are unchanged or improved** — the anti-collapse term should stabilize
   downstream CG losses, not fight them.
5. **No NaN/Inf** in `cg_anticollapse_*` metrics over the full run.

If criterion (2) is not achievable because the baseline already has healthy
state variance, the feature is **optional** rather than critical — document
this finding and leave the flag off by default. The cheap pre-work of
measuring baseline variance should be done **before** merging.

### 1.8 Rollout Plan

1. **Measure baseline collapse.** Before any code changes, run a
   100-step `train_mistral_cg.sh --smoke-test` equivalent and log
   `state.var(dim=0).mean()` and off-diagonal covariance norm. This
   establishes whether the failure mode is real for the current
   configuration. If the Sovereign State already has healthy statistics,
   downgrade this ticket from P0 to P2 and revisit only when a regression
   is observed.
2. **Implement** the three-file change (§1.4). Keep the patch under 80
   lines of added code total.
3. **Unit test.** Add a test in `symbolu_training/jepa/tests/test_jepa.py`
   that constructs a `VICRegLoss`, passes a collapsed input
   (`torch.zeros(32, 32)`) and a healthy input
   (`torch.randn(32, 32)`), and asserts `compute_collapse_only` returns a
   larger value for the collapsed case.
4. **Smoke test.** Run `scripts/train_mistral_cg.sh --smoke-test` with
   `--lambda_sovereign_anticollapse 0.02` and confirm no crash, no NaN,
   metrics are emitted.
5. **1K-step WikiText-2 run.** Evaluate against success criteria §1.7.
6. **Default flip.** Only after the 1K-step run passes, change
   `scripts/train_mistral_cg.sh` to pass `--lambda_sovereign_anticollapse
   0.02` by default. Keep the underlying config default at `0.0` so
   non-CG pipelines are unaffected.

### 1.9 Out of Scope (for P0-1)

- Applying VICReg to the Bhava slice (`state[:, BHAVA_SLICE]`) specifically
  — the full 32D state is the right level of granularity for the first
  iteration. Bhava-specific regularization can be added in a follow-up if
  measurements show the 12D Bhava slice collapsing independently.
- Replacing or deprecating the existing `jepa_vicreg_weight` path. That
  path is for JEPA pretraining and is orthogonal to CG.
- Applying anti-collapse to the `mistral_hybrid` path. The hybrid wrapper
  does not use a Sovereign State projector, so this feature is
  CG-specific.

---

---

## §2 P0-2 — Phase Warmstart Curve (`mistral_hybrid`)

### 2.1 Problem Statement

`MistralHybridWrapper` attaches `num_phase_layers` trainable attention
blocks on top of a frozen Mistral-7B backbone
(`mistral_hybrid_wrapper.py:101–138`). The later blocks (`i >= local_layers`)
are `HybridTransformerBlock` instances that blend local attention with
**Phase attention**, the O(n) long-range mechanism that is the whole point
of the hybrid architecture.

Phase attention maintains a rolling phase-coherent memory across the
sequence. At **initialization**, this memory contains garbage — the phase
projections are random and carry no meaningful temporal signal. Nonetheless
the Phase branch of every `HybridTransformerBlock` contributes to the
block's output from step 0, which means the frozen-backbone signal is
immediately corrupted by random phase-branch output before the phase
parameters have learned anything.

The symptoms observed in practice on `train_hybrid_7b.py`-style runs:

- **Early-step LM loss spike** — the hybrid wrapper's loss is higher than
  a frozen-backbone-only baseline for the first several hundred steps
  because the phase correction is actively harmful.
- **Slow recovery** — the adapter gate
  (`mistral_hybrid_wrapper.py:161`, `sigmoid(-2) ≈ 0.12`) is a constant
  multiplicative cap, not a training-time curve, so it cannot distinguish
  "phase layers are still warming up" from "phase layers have converged".
- **Fragile combinations** — small learning rate changes or batch size
  changes tip the early curve from "recovers" to "diverges" because the
  only thing keeping early-step loss finite is the frozen `adapter_gate`
  scalar.

The `train_hard_probes.py` pipeline solves this with a **phase warmstart
sigmoid curve** that multiplies the phase branch's contribution by an
`alpha(step)` that ramps from ≈0 at step 0 to ≈1 well after training is
underway. This gives the phase projections time to learn a useful
representation before they are allowed to influence the residual stream.

### 2.2 Current State in Repository

Unlike P0-1, the **mechanism is fully implemented** in the core phase
transformer — it just isn't wired into `MistralHybridWrapper`:

- **`PhaseAttentionLayer`** carries per-instance warmstart state at
  `symbolu/phase_transformer.py:2088–2094`:
  ```python
  self.phase_warmstart_enabled = False
  self._warmstart_steps = 10000
  self._warmstart_tau = 2000.0
  self._warmstart_apply_inference = False
  self._current_step = 0
  self._diag_warmstart_alpha = None
  ```
- **The sigmoid curve is computed inside the forward pass** at
  `phase_transformer.py:2270–2272`:
  ```python
  if self.phase_warmstart_enabled:
      _warmstart_alpha = 1.0 / (
          1.0 + math.exp(-(_ws_s - self._warmstart_steps)
                         / max(self._warmstart_tau, 1.0))
      )
  ```
  The sigmoid is centered at `_warmstart_steps` (alpha = 0.5 at that step)
  with steepness `_warmstart_tau`.
- **`HybridPhaseTransformer.set_global_step(step)`** at
  `phase_transformer.py:6963–6972` walks all `PhaseAttentionLayer`
  submodules and updates `_current_step`. This is the canonical way to
  advance the warmstart curve once per training step.
- **`HybridPhaseTransformer.__init__`** at
  `phase_transformer.py:6940–6947` contains the wiring pattern that
  enables warmstart on every phase attention submodule after construction.

The gap:

- **`MistralHybridWrapper` bypasses `HybridPhaseTransformer` entirely** —
  it constructs `LocalTransformerBlock` and `HybridTransformerBlock`
  directly (`mistral_hybrid_wrapper.py:115–138`). None of the three
  warmstart wiring paths above are touched.
- **No warmstart references in the unified pipeline** — verified by
  `grep -r 'phase_warmstart\|warmstart_tau\|warmstart_steps'` across
  `symbolu_training/training/unified/`: zero matches.
- **The training loop never calls `set_global_step`** on any model —
  verified by grep for `set_global_step` in `train.py`.

So this is a **wiring task**, not an implementation task. All the core
mechanics live in `symbolu/phase_transformer.py`; we just need to expose
them through `MistralHybridWrapper` and the unified CLI.

### 2.3 Design Approach

**Four-part integration:**

1. Add warmstart fields to `MistralHybridWrapper.__init__`.
2. After `self.phase_blocks` is constructed, walk every
   `HybridTransformerBlock` and set warmstart attributes on its inner
   `PhaseAttentionLayer` submodules. Local-only blocks
   (`i < local_layers`) are skipped because `LocalTransformerBlock` does
   not have a phase branch.
3. Add a `set_global_step(step)` method on `MistralHybridWrapper` that
   mirrors `HybridPhaseTransformer.set_global_step` — walks the model
   once, updates `_current_step` on every `PhaseAttentionLayer`.
4. Call `model.set_global_step(global_step)` once per optimizer step in
   `symbolu_training/training/unified/train.py` before the forward pass,
   guarded so it is a no-op when the model does not expose the method.

**Why not inherit from `HybridPhaseTransformer`?** Because
`MistralHybridWrapper` owns the frozen backbone + adapter + output norm
+ `adapter_gate` + `phase_output_proj` — it is a wrapper, not a
transformer. Inheriting would drag in `HybridPhaseTransformer`'s token
embeddings, lm_head, and RoPE cache, none of which the wrapper uses.
Mirroring the wiring code is cheaper and clearer.

**Why walk submodules instead of constructor injection?** Because
`HybridTransformerBlock.__init__` does not currently accept warmstart
kwargs. Adding them would change the constructor signature and ripple
through every caller. The submodule walk is a three-line no-op when
warmstart is disabled and a five-line setup when enabled.

### 2.4 Integration Points

**Four files touched:**

1. **`symbolu_training/training/unified/mistral_hybrid_wrapper.py`** —
   add `__init__` kwargs, post-construction wiring, and `set_global_step`.
2. **`symbolu_training/training/unified/config.py`** — add three config
   fields in the hybrid block:
   ```python
   phase_warmstart: bool = False
   phase_warmstart_steps: int = 10000
   phase_warmstart_tau: float = 2000.0
   ```
3. **`symbolu_training/training/unified/train.py`** —
   - add the three argparse flags alongside the other `mistral_hybrid`
     args;
   - thread them into the `MistralHybridWrapper(...)` constructor call
     in `model_factory.py`;
   - call `model.set_global_step(global_step)` once per optimizer step,
     guarded by `hasattr(model, 'set_global_step')`.
4. **`symbolu_training/training/unified/model_factory.py`** — forward
   the three config fields from `UnifiedConfig` into the wrapper's
   constructor.

### 2.5 Wrapper Changes (Sketch)

```python
# symbolu_training/training/unified/mistral_hybrid_wrapper.py

class MistralHybridWrapper(nn.Module):
    def __init__(
        self,
        ...,
        # Phase warmstart (V10.13 curve ported from HybridPhaseTransformer)
        phase_warmstart: bool = False,
        phase_warmstart_steps: int = 10000,
        phase_warmstart_tau: float = 2000.0,
        phase_warmstart_apply_inference: bool = False,
        ...,
    ):
        super().__init__()
        ...
        # ── Trainable Phase attention layers (existing code) ────────
        self.phase_blocks = nn.ModuleList()
        for i in range(num_phase_layers):
            ...  # existing LocalTransformerBlock / HybridTransformerBlock construction

        # ── Phase warmstart wiring (new) ────────────────────────────
        self.phase_warmstart_enabled = phase_warmstart
        if phase_warmstart:
            from symbolu.phase_transformer import PhaseAttentionLayer
            _n_wired = 0
            for block in self.phase_blocks:
                for sub in block.modules():
                    if isinstance(sub, PhaseAttentionLayer):
                        sub.phase_warmstart_enabled = True
                        sub._warmstart_steps = phase_warmstart_steps
                        sub._warmstart_tau = phase_warmstart_tau
                        sub._warmstart_apply_inference = phase_warmstart_apply_inference
                        _n_wired += 1
            print(
                f"  Phase Warm-Start: ENABLED on {_n_wired} PhaseAttentionLayer(s) "
                f"(steps={phase_warmstart_steps}, tau={phase_warmstart_tau})"
            )
        ...

    def set_global_step(self, step: int) -> None:
        """Advance the phase warmstart curve for all phase attention layers.

        No-op if warmstart is disabled. Call once per optimizer step from
        the training loop, before the forward pass.
        """
        if not self.phase_warmstart_enabled:
            return
        from symbolu.phase_transformer import PhaseAttentionLayer
        for sub in self.modules():
            if isinstance(sub, PhaseAttentionLayer):
                sub._current_step = step
```

### 2.6 Training Loop Changes (Sketch)

```python
# symbolu_training/training/unified/train.py  — inside the main loop,
# at the top of each optimizer step, BEFORE the forward pass

if hasattr(model, 'set_global_step'):
    model.set_global_step(global_step)
```

One line, guarded by `hasattr`, so it is a no-op for any model that does
not opt in (including `mistral_cg`, `ontological_hybrid`, and every other
`--model_type`). The `HybridPhaseTransformer` path already has a
`set_global_step` method, so turning this on means **both** `mistral_hybrid`
and the non-Mistral hybrid transformer automatically benefit.

### 2.7 Configuration Interface

**New CLI flags** (argparse block in `train.py`, near existing
`mistral_hybrid` args around `:10057`):

```
--phase_warmstart                             (default: False)
    Enable phase warmstart curve on mistral_hybrid / ontological
    hybrid paths. Multiplies each PhaseAttentionLayer's phase-branch
    output by sigmoid((step - warmstart_steps) / warmstart_tau), so
    the phase branch is dampened early and activated gradually.

--phase_warmstart_steps INT                   (default: 10000)
    Step at which the warmstart sigmoid reaches alpha = 0.5.
    Recommended: ~5-10% of total training steps.

--phase_warmstart_tau FLOAT                   (default: 2000.0)
    Sigmoid steepness. Smaller = sharper transition.
    Recommended: roughly warmstart_steps / 5.
```

**Recommended setting for `train_hybrid_7b.py`-style 50K-step runs:**

```bash
--phase_warmstart
--phase_warmstart_steps 5000
--phase_warmstart_tau 1000.0
```

At these settings the curve is ≈0.01 at step 0, 0.12 at step 2500, 0.50
at step 5000, 0.88 at step 7500, and 0.99 at step 10000 — i.e. the
phase branch is effectively silent for the first ~2000 steps, warming
up fast thereafter, fully active by step 10K out of 50K total.

### 2.8 Risks and Mitigations

| Risk                                                             | Likelihood | Mitigation |
|------------------------------------------------------------------|------------|------------|
| Warmstart curve too slow → phase layers never get enough signal  | Low–Medium | Defaults chosen so alpha ≥ 0.5 by step 10K; tau/steps are both CLI-tunable |
| Warmstart curve too fast → defeats the purpose, early-step spike remains | Low | Log the alpha value at steps 0, 1K, 5K, 10K so operators see the curve |
| Inference-time behavior silently changes when model reloaded     | Low        | `phase_warmstart_apply_inference` defaults to `False`; warmstart alpha is always 1.0 at eval unless explicitly opted in |
| `set_global_step` is forgotten in the training loop              | Medium     | Guarded by `hasattr` so absent method is a no-op; enable a startup assertion when `phase_warmstart=True` that prints a warning if `_current_step` is still 0 after step 10 |
| Checkpoint resume restarts the curve at step 0                   | Medium     | `global_step` is already persisted in checkpoints; `set_global_step` is called every step in the loop so resume picks up the correct value on the first step after reload |
| Interaction with `adapter_gate` (existing constant cap)          | Low        | Warmstart multiplies the phase contribution *inside* the block; `adapter_gate` multiplies the block output. Both apply — the net early-step scaling is `sigmoid(-2) * warmstart_alpha ≈ 0.12 * 0.01 ≈ 0.0012`. This is fine; if anything it is extra safety |

### 2.9 Success Criteria

Evaluated on a 10K-step `train_hybrid_7b.py`-style run (FineWeb, bf16,
`num_phase_layers=4`, `local_layers=2`) with
`--phase_warmstart --phase_warmstart_steps 2000 --phase_warmstart_tau 500`:

1. **Early-step LM loss curve is monotonically non-increasing** after
   step 100, i.e. no early-step spike relative to the frozen-backbone-only
   baseline.
2. **Logged `phase_warmstart_alpha` metric** reaches 0.5 within 10% of
   `phase_warmstart_steps` and ≥0.95 by step `2 * phase_warmstart_steps`.
   Requires adding a one-line metric emission in the wrapper's forward
   or a periodic probe.
3. **Final LM loss at step 10K is within 1%** of a baseline run with
   warmstart disabled — i.e. warmstart does not slow down convergence
   to the final perplexity, it just improves the early-step trajectory.
4. **Baseline verification**: before claiming criterion (1), run a
   disabled-warmstart control and confirm the early-step spike actually
   exists. If it does not, this feature is optional — document the
   finding and leave the flag off by default.
5. **No NaN/Inf** in phase-attention outputs during the first 1000
   steps, where historically the combination of random phase projections
   and large effective learning rate is most fragile.

### 2.10 Rollout Plan

1. **Baseline measurement.** Before any code change, run 1K steps of
   the current `mistral_hybrid` path, log per-step LM loss, and confirm
   the early-step spike exists. Save curve for comparison.
2. **Implement** the four-file change (§2.4). Target patch size:
   ~40 lines added to `mistral_hybrid_wrapper.py`, ~15 lines of config
   plumbing, ~3 lines in the training loop, ~5 lines in `model_factory.py`.
3. **Unit test.** Add a test in `tests/` that constructs a
   `MistralHybridWrapper` with a synthetic backbone stub, enables
   warmstart, calls `set_global_step(0)` and `set_global_step(10000)`,
   asserts the `_current_step` is propagated to every
   `PhaseAttentionLayer`, and asserts the diagnostic
   `_diag_warmstart_alpha` attribute changes between the two steps.
4. **Smoke test.** 100-step synthetic run with warmstart enabled and
   `phase_warmstart_steps=50, phase_warmstart_tau=10`. Confirm no NaN,
   no crash, `phase_warmstart_alpha` crosses 0.5 at step 50.
5. **10K-step FineWeb run.** Evaluate against success criteria §2.9.
6. **Default flip.** If criterion (3) holds, change the default in
   `train_hybrid_7b.py` to pass `--phase_warmstart` by default with
   `warmstart_steps = total_steps // 10`. Leave the config default at
   `phase_warmstart=False` so other model types are unaffected.

### 2.11 Out of Scope (for P0-2)

- `phase_write_gate` and `phase_channels` — separate P1-2 port. They
  share the CLI heritage of warmstart but attach to different mechanisms
  (memory write gating and multi-channel phase memory). Keeping them
  separate preserves the ability to isolate which change moved the
  metric.
- Exposing warmstart through the non-Mistral hybrid path
  (`train_hybrid_7b.py` with `HybridPhaseTransformer` directly). That
  path already has `set_global_step`; the change to `train.py` at §2.6
  will automatically activate it for that model too, but verifying the
  end-to-end curve on the non-Mistral path is a separate validation.
- Curve shapes other than sigmoid. The existing implementation at
  `phase_transformer.py:2270` hard-codes the sigmoid. Linear/cosine/step
  curves could be added later if the sigmoid turns out to be wrong, but
  changing the curve is an orthogonal decision and not blocking.
- Per-layer warmstart schedules (e.g. later phase layers warm up after
  earlier ones). Architecturally interesting; not justified by any
  observed failure mode.

---

---

## §3 P1-1 — LSTB / CSR Bridge Supervision (`mistral_cg`)

### 3.0 Recommendation Up Front

P1-1 as originally scoped in the executive summary is **two distinct
sub-tasks** that share only the name "bridge supervision". They have
different mechanisms, different attach points, different failure modes,
and different urgency. This section treats them separately:

- **§3A — LSTB (Latent Semantic Token Bridge) Wiring.** Gives the 32D
  Sovereign State a causal prediction target via `PhaseJEPAPredictor`.
  **Primary, recommended.** Ship as P1-1. Full-depth design below.
- **§3B — CSR Phonemic Grounding.** Upgrades the existing `L_csr`
  contrastive loss with a phonemic-similarity target via the hard-probes
  `csr_phoneme_provider`. **Secondary, optional.** Treat as a P3
  follow-up, conditional on §3A's baseline measurements showing that the
  Sovereign State still lacks symbolic grounding after §3A is active.

The two sub-tasks can ship independently with zero interaction. An
implementer needing to execute P1-1 should read §3A in full and may
skim or skip §3B.

### 3.1 Scope and Correction of Earlier Framing

The feature comparison that motivated this design document (see the
executive summary) claimed that `lambda_csr_token` is "a weight on
nothing" — that porting the LSTB infrastructure would give it "a real
training signal instead of a weak proxy." **That claim is wrong in one
direction and right in another, and the distinction matters enough to
correct explicitly before proceeding.**

What is wrong:

- `lambda_csr_token` is **not** a dangling weight. It drives a real
  InfoNCE contrastive loss inside
  `PrimitiveAuxiliaryLosses.forward()` at
  `symbolu_training/training/conscious_generation/losses/primitive_auxiliary.py:27`.
  The loss extracts column 3 of the Token Evaluation Tensor `T`,
  identifies the correct token's score, and computes softmax
  cross-entropy against shortlist negatives. Gradients flow back through
  the scorer that produced `T`.
- The existing `L_csr` loss is not "a weak proxy for phoneme structure".
  It is a perfectly functional shortlist-scoring loss that does what
  shortlist-scoring losses do: it teaches the scorer to rank the correct
  token higher than incorrect candidates on column 3 of `T`.

What is right:

- Nothing in the existing `L_csr` loss **forces** column 3 of `T` to
  correlate with actual phoneme structure. Column 3 learns whatever it
  needs to learn to minimize the InfoNCE objective, which — given enough
  capacity in the scorer — can be achieved by any arbitrary ranking
  function that happens to separate correct from incorrect tokens.
  Phonemic grounding is a *property we would like* column 3 to have; it
  is not currently a *property we train for*.
- The original comparison also conflated "bridge" in two different
  senses. LSTB refers to a **latent bridge** — a temporal prediction
  loss on the 32D Sovereign State. The CSR bridge refers to a
  **symbolic bridge** — an ARPABET → 10D resonance-vector decomposition
  used to ground token-level phonemic reasoning. These share the word
  "bridge" and a `--test-*-bridge` CLI flag in `train_hard_probes.py`,
  nothing else.

The corrected framing is therefore:

- **§3A is about giving the 32D Sovereign State a *temporal* target** —
  addressing a real gap (P0-1's anti-collapse term prevents degenerate
  states but provides no positive learning signal for the projector).
- **§3B is about giving `L_csr` a *symbolic* target** — a quality
  upgrade on an already-working loss, conditional on evidence that the
  upgrade is needed.

### 3.2 Current State in Repository

Shared inventory of the relevant modules, so both sub-tasks can
reference this section rather than re-enumerating.

**Already implemented and available for wiring:**

- **`SovereignStateProjector`** at
  `symbolu_training/jepa/state_projector.py:43`. An MLP projector from
  `hidden_dim → 32` with per-plane normalization (softmax on the 12D
  Bhava slice, sigmoid on the 5D Kosha slice, etc.). Already instantiated
  by `MistralCGWrapper` at `mistral_wrapper.py:103` and applied at
  `:305` to the pooled hidden state via
  `state = self.state_projector(pooled)` where
  `pooled = hidden.mean(dim=1)`. Output is shape `[B, 32]` — **one
  state per sequence, not per-token**.
- **`PhaseJEPAPredictor`** at
  `symbolu_training/jepa/predictor.py:43`. Takes a context state of
  shape `[B, T, 32]` (or `[B, 32]`) and predicts `k`-step deltas in the
  Sovereign State space using complex-phasor attention. Supports
  `prediction_steps` up to `k_steps` configurable at construction. The
  `VrittiValidatedPredictor` subclass at `:304` adds a Vritti-gated
  variant that skips updates when the Vritti classifier reports low
  cognitive reliability. **Zero references in
  `symbolu_training/training/unified/`** (verified by grep) — present in
  the JEPA package, not wired into the CG training loop.
- **`VICRegLoss`** at `symbolu_training/jepa/losses.py:23`. Already
  scheduled for the unary anti-collapse use in §1 (P0-1). For §3A it
  is used in its **binary** mode: `VICRegLoss(x_pred, y_target)` with
  nonzero invariance (MSE) coefficient, which is its canonical JEPA
  form.
- **`JEPAPredictionLoss`** and **`CompositeJEPALoss`** — also in
  `symbolu_training/jepa/losses.py`. Wrap `VICRegLoss` + MSE +
  orthogonality regularization into a single callable with
  `vicreg_weight` and `ortho_weight` parameters. Already imported by
  the hard-probes `latent_bridge.py` benchmark at
  `scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/latent_bridge.py:35`.
- **`PrimitiveAuxiliaryLosses`** at
  `symbolu_training/training/conscious_generation/losses/primitive_auxiliary.py:27`.
  Hosts the existing `L_csr` (and `L_jepa`, `L_vritti`, `L_guna`)
  contrastive losses. Already wired into the CG loss block in the
  training loop at `symbolu_training/training/unified/train.py:5218`.

**Present in `train_hard_probes.py` but not packaged for reuse:**

- **`csr_phoneme_provider`** — referenced in the hard-probes CSR bridge
  benchmark at
  `scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/csr_bridge.py:62–78`.
  Provides `CSREmbeddingProvider`, `VarnaCSRBridge`,
  `ARPABET_TO_VARNA`, and `SANSKRIT_VOWEL_CALIBRATION`. The module
  itself lives inside the `hard_probes_lib` tree and is not exposed as
  an importable utility from the unified pipeline.

**CG forward-pass contract (relevant to both sub-tasks):**

- `MistralCGWrapper.forward()` at `mistral_wrapper.py:346` returns a
  dict with `'state': [B, 32]`, `'delta_S': [B, 32]`, and
  `'delta_bhava': [B, 12]`. The state is **pooled across the sequence**
  — per-token state is not currently available through the forward
  dict. Any design that needs a trajectory must either (a) modify the
  wrapper to expose per-token state, or (b) reconstruct the trajectory
  from `last_hidden_state` (which is already returned when
  `return_last_hidden=True`) by applying the projector externally.
- The CG loss block in `train.py:4931+` extracts the pooled state at
  `:5000` via `_cg_sov_state = outputs.get('state', None)`. This is
  the natural attach point for the §1 (P0-1) unary anti-collapse term.
  A trajectory-based JEPA loss (§3A) needs either a different attach
  point that provides per-token state, or a new forward flag that adds
  per-token state to the output dict.

**What is absent:**

- No references to `PhaseJEPAPredictor`, `JEPAPredictionLoss`, or
  `CompositeJEPALoss` anywhere in `symbolu_training/training/unified/`.
- No phoneme-based grounding loss anywhere in
  `symbolu_training/training/conscious_generation/`.
- No mechanism in the CG forward pass to expose per-token Sovereign
  State, nor any call site that consumes one.

---

## §3A — LSTB (Latent Semantic Token Bridge) Wiring

*Primary sub-task of P1-1. Ships standalone. Depends on §1 (P0-1) being
correctly in place; does not depend on §3B.*

### 3A.1 Problem Statement

After §1 (P0-1: VICReg unary anti-collapse on the pooled Sovereign
State) is in place, the 32D state projector has **one** training signal
that acts directly on its output: a regularizer that says "don't
collapse, keep your dimensions varied and decorrelated." That is a
necessary guardrail, but it is not a **learning target**. Anti-collapse
only tells the projector what *not* to do; it does not tell the
projector what the state *should represent*.

The projector is indirectly pulled by downstream CG auxiliary losses —
`lambda_ont`, `lambda_kosha_routing`, `lambda_bliss_token`,
`lambda_vritti_token`, `lambda_csr_token`, `lambda_guna_token` — but
those gradients arrive through long loss paths that go through the
Token Evaluation Tensor, shortlist scoring, integrated softmax, and
contrastive targets. Each of those auxiliaries is computed at a single
pooled state per sequence, provides a weak signal relative to the LM
cross-entropy path, and has no notion of **temporal structure** in the
sequence of states that the projector produces as a sequence is
consumed.

The specific gap:

- **The 32D Sovereign State has no causal prediction target.** Nothing
  in the current training loop asks the projector to produce a state
  at position `t` that is *predictable* from its own past
  `state_{<t}`. The projector is free to produce a state trajectory
  that is temporally incoherent — every step lives on its own, with
  no continuity constraint.
- **Temporal incoherence silently degrades every downstream CG module
  that reads the state across a sequence.** Stage 8's Perspective
  Synthesizer, the Kosha router, and the Vritti classifier all consume
  the Sovereign State as if it carries stable meaning across token
  positions. If the trajectory is in fact a random walk (or worse, a
  step function), those modules fit noise — and they will converge to
  losses that *look* reasonable on average, even though the underlying
  representation has no structure.
- **This failure is not caught by P0-1.** VICReg's variance term only
  asks that each of the 32 dimensions has non-trivial variance across
  the *batch*, not across *time*. A projector that produces the same
  state for every token in a sequence (but different states across
  sequences) passes P0-1 trivially and fails §3A completely.

The symptom to watch for — which operators will only notice if they
measure it — is a combination of (a) healthy `cg_anticollapse_*`
metrics from P0-1, (b) healthy `cg_ont_loss` / `cg_kosha_routing_loss`
/ `cg_vritti_token_loss` curves, and (c) Stage 8 Perspective
Synthesizer outputs that show no meaningful temporal structure when
probed with a diagnostic like per-token state cosine similarity. The
loop runs, the losses go down, and the 32D bottleneck is still
carrying nothing useful across time.

LSTB (Latent Semantic Token Bridge) solves this by adding a
**predictive self-supervision loss** on the Sovereign State trajectory:
given the state at positions `≤ t`, predict the state at `t + k`, and
penalize the distance between prediction and the (detached) target.
This gives the projector a positive learning signal that directly
rewards temporal coherence.

---

### 3A.2 Design Approach

Five design decisions drive the implementation. Each is stated with the
options considered, the choice, and the justification — so future
readers can see which decisions are load-bearing and which are
incidental.

#### Decision 1: How to produce the per-token Sovereign State trajectory

`MistralCGWrapper.compute_state_delta` currently produces **one pooled
state per sequence** at `mistral_wrapper.py:301–305`:

```python
pooled = hidden.mean(dim=1)              # [B, D_mistral]
state = self.state_projector(pooled)     # [B, 32]
```

A JEPA-style predictor needs a **trajectory** `[B, T, 32]` — one state
per token position. Options considered:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | Apply the projector per-token: `state_traj = self.state_projector(hidden)` → `[B, T, 32]` | **Chosen** |
| B | Sliding-window pool: project over overlapping chunks of `K` tokens | Rejected — introduces a window hyperparameter, breaks causality on the right boundary, adds edge-case bugs |
| C | Reconstruct trajectory externally in the training loop from `last_hidden_state` | Rejected — scatters the projector usage across two call sites, invites drift when the projector changes |

`SovereignStateProjector` is an MLP with per-plane activations applied
on the last dimension. It handles arbitrary leading dimensions cleanly
— applying it to `[B, T, D]` returns `[B, T, 32]` with no code change
to the projector itself. The only change needed is a new forward-path
option on `MistralCGWrapper` that computes and exposes the trajectory
when LSTB is enabled.

**Cost.** For a typical CG run (B=4, T=1024, D_mistral=4096), the
per-token projection adds roughly `B × T × D_mistral × 32 ≈ 500 MFLOPs`
per forward. The frozen Mistral backbone consumes on the order of
`200+ TFLOPs` per forward at the same batch size. The extra cost is
well under 1% and not a deciding factor.

**Contract change on `MistralCGWrapper.forward`:** add an optional
parameter `return_state_trajectory: bool = False`. When `True`, the
forward dict gains an additional key `'state_trajectory': [B, T, 32]`.
The existing pooled `'state': [B, 32]` key is unchanged, preserving
backwards compatibility for §1 (P0-1), every existing CG auxiliary
loss, and Stage 8. The new key is computed only when the flag is set
so non-LSTB runs pay nothing.

#### Decision 2: JEPA target construction (context vs. target, same projector vs. EMA)

Three canonical JEPA recipes were considered:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | **Same projector, stop-gradient on target.** Context = `state_traj[:, :-k]`. Target = `state_traj[:, k:].detach()`. One projector, one code path. | **Chosen** |
| B | **EMA target encoder.** Maintain an exponential-moving-average copy of `SovereignStateProjector` and use it to produce targets. | Rejected for v1 — adds EMA state to checkpoints, doubles projector memory, adds a decay hyperparameter |
| C | **Separate target projector** (fresh init, different params). | Rejected — adds a second trainable module with no clear supervision signal for it |

Option A is the minimum viable JEPA. It is what `CompositeJEPALoss`
and `JEPAPredictionLoss` already expect at their call sites in the
hard-probes `latent_bridge.py` benchmark
(`scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/latent_bridge.py:362`).
Upgrading to Option B is a mechanical follow-up if and only if the
1K-step measurement (§3A.6) shows that Option A plateaus at a
non-useful prediction MSE. **Do not ship Option B speculatively.**

**Stop-gradient correctness.** The target tensor is produced by the
same projector instance as the context, but passed through `.detach()`
before entering the loss. This means:

- The projector **does** receive gradient from the loss through the
  context path (positions `[:, :-k]`).
- The projector **does not** receive gradient from the loss through
  the target path (positions `[:, k:]`). Those gradients are blocked
  by the detach.
- The predictor (`PhaseJEPAPredictor`) receives gradient normally
  through its own parameters, pulled toward making the prediction
  match the detached target.

This is the standard JEPA recipe and avoids the degenerate solution
where the projector learns to produce a trivial (e.g., constant) state
that is trivially predictable.

#### Decision 3: Predictor ownership and instantiation

`PhaseJEPAPredictor` is a standalone `nn.Module` with ~100K parameters
for a 32D state (default `hidden_dim=128, num_heads=4,
prediction_steps=k`). It needs to live **somewhere** in the model
graph so the optimizer sees its parameters and checkpointing picks it
up.

The existing CG module suite follows a **dict pattern** visible at
`train.py:5183` (`model.conscious_gen['kosha_routing_loss']`) and
`:5197` (`model.conscious_gen['bliss_coherence_loss']`), where
`model.conscious_gen` is a plain dict of named sub-modules attached
during `model_factory.build_mistral_cg(...)`. The LSTB predictor and
loss fit this pattern directly:

```python
model.conscious_gen['jepa_predictor'] = PhaseJEPAPredictor(...)
model.conscious_gen['jepa_loss']      = JEPAPredictionLoss(...)
```

The predictor is constructed inside `model_factory.py` at the same
site that constructs the existing CG modules. The parameter count is
small enough that it does not require special-case handling for
optimizer groups, gradient clipping, or mixed precision — it
inherits the same treatment as every other trainable CG module.

**Why not put it on `MistralCGWrapper` directly?** Because
`MistralCGWrapper` already bundles the backbone, state projector,
intent projector, and phase adapter. Adding the JEPA predictor there
would blur the boundary between "representation-producing modules"
(which the wrapper owns) and "auxiliary training signals" (which
`model.conscious_gen` owns). Keeping the predictor in
`model.conscious_gen` preserves that boundary.

#### Decision 4: Loss composition (roll our own vs. reuse `JEPAPredictionLoss`)

`JEPAPredictionLoss` at `symbolu_training/jepa/losses.py:192` already
wraps three terms:

- **MSE invariance** between predicted and detached target state.
- **VICReg regularization** on the predicted state (the binary form
  of `VICRegLoss`, with nonzero invariance coefficient).
- **Orthogonality regularization** on the predictor's learned
  projection weights, preventing the predictor from collapsing to a
  low-rank mapping.

It exposes `vicreg_weight` and `ortho_weight` as construction-time
hyperparameters. The hard-probes `latent_bridge.py` benchmark already
instantiates it as
`JEPAPredictionLoss(vicreg_weight=0.5, ortho_weight=0.05)` at line
364, which is the recommended starting configuration.

**Verdict: reuse `JEPAPredictionLoss` as-is.** Rolling a custom
MSE + VICReg combination in the training loop would duplicate code
that already exists, fork the source of truth for the math, and make
future changes to JEPA defaults require two-site updates. The only
cost of reuse is that the ortho term operates on the predictor's
internal projection weights — which the predictor already exposes
because that is its documented interface. No wrapping or adapter code
is needed.

#### Decision 5: `k_steps` value for v1

`PhaseJEPAPredictor` supports multi-step autoregressive prediction via
`prediction_steps`. The value matters because:

- **Small `k` (e.g. `k=1`)** gives the predictor an easy target
  (next-position state) and produces a dense training signal — every
  token position except the last contributes a prediction loss.
- **Large `k` (e.g. `k=4, 8`)** gives the predictor a harder target
  that forces it to model longer-horizon dynamics, but the signal is
  sparser and the autoregressive rollout accumulates error.

For v1, **start with `k_steps = 1`**. Rationale:

1. It is the densest, lowest-variance training signal available.
2. It is the minimum that tests whether the projector can produce a
   trajectory with any temporal structure at all — if `k=1` does not
   reduce MSE meaningfully below a trivial baseline (see §3A.6), then
   `k>1` will fail harder.
3. It avoids an autoregressive rollout loop in the critical path,
   keeping the forward cost of the JEPA loss at `O(B × T × 32)`
   rather than `O(k × B × T × 32)`.
4. `k_steps` is exposed as a config flag (§3A.4), so upgrading to
   `k=2` or larger is a one-line change once v1 is measured.

**Causal correctness of `k=1` in `PhaseJEPAPredictor`.** The
predictor's `_phase_attention` implementation at `predictor.py:257`
accumulates state via `torch.cumsum(kv, dim=1)`. Cumsum along the time
dimension is **causal by construction**: the output at position `t`
depends only on inputs at positions `≤ t`. No explicit causal mask
is required. This was verified against
`symbolu_training/jepa/predictor.py:255–257` before committing this
design. The mechanism works because the model is structurally
prevented from peeking at future tokens, not because of an attention
mask that could be forgotten.

---

### 3A.3 Integration Points

Four files are touched. The changes are small and localized — the
hard work is in the preceding design section, not here. Every line
number in this section is a **reference into the current code**, not
a target for the new code.

The sketches below are illustrative, not literal patches. An
implementer should read the surrounding code before transcribing.

#### File 1: `symbolu_training/training/unified/mistral_wrapper.py`

**Two changes.** One new forward-path option, one new output-dict key.
No breaking changes to the existing signature or to any caller that
does not opt in.

**Change 1a — add `return_state_trajectory` to `forward`:**

The forward signature currently ends with `**kwargs` at line 356, so
the new parameter can be inserted before it without affecting any
existing caller. Place it next to `return_last_hidden` for
discoverability:

```python
# mistral_wrapper.py — forward signature (line 346)
def forward(
    self,
    input_ids: torch.Tensor,
    attention_mask: Optional[torch.Tensor] = None,
    labels: Optional[torch.Tensor] = None,
    return_hidden: bool = False,
    extract_layers: Optional[List[int]] = None,
    return_last_hidden: bool = False,
    return_state_trajectory: bool = False,   # NEW — LSTB (§3A)
    reset_state: bool = False,
    return_decorr_loss: bool = False,
    **kwargs,
) -> Dict[str, torch.Tensor]:
```

**Change 1b — compute the trajectory and add it to the result dict:**

The existing pooled path at line 390 is unchanged. The new trajectory
is computed from the raw backbone `hidden` — the same input the
pooled path uses — and added to the result dict only when the flag
is set. Insert after the pooled `state` is assembled and before the
result dict is returned (between lines 462 and 474, alongside the
existing `return_last_hidden` branch at line 470):

```python
# mistral_wrapper.py — inside forward, after existing result dict is built

if return_state_trajectory and _use_state:
    # Per-token Sovereign State trajectory for LSTB.
    # Projects each token's hidden state through the same projector
    # used by compute_state_delta, preserving semantic consistency
    # with the pooled 'state' field.
    #
    # Cost: O(B × T × D_mistral × 32) — ≪ 1% of Mistral backbone
    # forward cost at typical batch sizes. Only computed when LSTB
    # is enabled; non-LSTB runs pay nothing.
    result['state_trajectory'] = self.state_projector(hidden)
```

**Rationale for the conditional on `_use_state`.** The existing
ablation path (`_use_state = False` → state is zeroed at line 393)
sets the pooled `state` to zeros to isolate the contribution of the
state projector. The trajectory field should follow the same ablation
semantics — if `_use_state` is false, omit the trajectory entirely
rather than producing a real one that contradicts the ablation. The
LSTB loss in `train.py` will then see `'state_trajectory' not in
outputs` and skip the loss computation (see File 4 below).

**No changes** to `compute_state_delta` at line 291. The pooled state
computation stays exactly as-is, so every existing caller — P0-1
anti-collapse, Stage 8 Perspective Synthesizer, Kosha router, Vritti
classifier — is untouched.

#### File 2: `symbolu_training/training/unified/model_factory.py`

Construct the `PhaseJEPAPredictor` and `JEPAPredictionLoss` and attach
them to `model.conscious_gen` alongside the existing CG modules.

The existing CG module suite is built inside
`build_mistral_cg(...)` (or equivalent — the actual function name
should be confirmed against current `model_factory.py`; the relevant
region is near the `_p3_losses.append(f"L_csr=...")` reference at
line 853). The pattern in that file attaches each CG sub-module to
`model.conscious_gen[name]` as a plain dict assignment.

**Sketch of the addition:**

```python
# model_factory.py — inside build_mistral_cg() or equivalent

if config.lambda_lstb > 0:
    from symbolu_training.jepa.predictor import PhaseJEPAPredictor
    from symbolu_training.jepa.losses import JEPAPredictionLoss

    model.conscious_gen['jepa_predictor'] = PhaseJEPAPredictor(
        state_dim=32,
        hidden_dim=config.lstb_hidden_dim,
        num_heads=config.lstb_num_heads,
        prediction_steps=config.lstb_k_steps,
        cosine_mode='complex',
        dropout=0.1,
    ).to(device)

    model.conscious_gen['jepa_loss'] = JEPAPredictionLoss(
        vicreg_weight=config.lstb_vicreg_weight,
        ortho_weight=config.lstb_ortho_weight,
    ).to(device)

    print(
        f"  LSTB enabled: k={config.lstb_k_steps}, "
        f"hidden={config.lstb_hidden_dim}, "
        f"vicreg={config.lstb_vicreg_weight}, "
        f"ortho={config.lstb_ortho_weight}"
    )
```

**Parameter budget.** With the default `state_dim=32, hidden_dim=128,
num_heads=4`, `PhaseJEPAPredictor` instantiates with roughly 100K
parameters. `JEPAPredictionLoss` has no trainable parameters of its
own (it is a wrapper around `VICRegLoss` and MSE). Both modules are
moved to `device` on construction and inherit the same optimizer
group, gradient clipping, and mixed-precision treatment as every
other module in `model.conscious_gen`.

**Optimizer visibility.** `model.conscious_gen` is iterated by the
existing optimizer setup code when collecting trainable parameters
(this is how `kosha_routing_loss`, `bliss_coherence_loss`,
`primitive_aux_losses`, etc. are all picked up today). The LSTB
predictor inherits this behavior automatically — no special-case
optimizer setup is required.

#### File 3: `symbolu_training/training/unified/config.py`

Five new config fields, placed in the CG block alongside the existing
lambda weights around lines 998–1043. All default to values that make
the feature **off** by default, so every existing run is unaffected.

```python
# config.py — inside the CG config block

# LSTB (§3A) — Latent Semantic Token Bridge
lambda_lstb: float = 0.0                  # Weight for JEPA prediction loss on state trajectory
lstb_k_steps: int = 1                     # Prediction lookahead (1 = next-position)
lstb_vicreg_weight: float = 0.5           # VICReg weight inside JEPAPredictionLoss
lstb_ortho_weight: float = 0.05           # Orthogonality weight inside JEPAPredictionLoss
lstb_hidden_dim: int = 128                # Predictor hidden dimension
lstb_num_heads: int = 4                   # Predictor phase attention heads
```

Corresponding argparse flags are added in `train.py` near the existing
CG flag block around line 10218:

```python
# train.py — argparse additions
parser.add_argument("--lambda_lstb", type=float, default=0.0,
    help="LSTB JEPA prediction loss weight on per-token Sovereign "
         "State trajectory. Recommended: 0.05 for mistral_cg. "
         "0.0 disables the feature entirely.")
parser.add_argument("--lstb_k_steps", type=int, default=1,
    help="LSTB prediction lookahead. Default 1 (next-position). "
         "Values > 1 enable autoregressive rollout.")
parser.add_argument("--lstb_vicreg_weight", type=float, default=0.5)
parser.add_argument("--lstb_ortho_weight", type=float, default=0.05)
parser.add_argument("--lstb_hidden_dim", type=int, default=128)
parser.add_argument("--lstb_num_heads", type=int, default=4)
```

The config fields are threaded into the `UnifiedConfig` constructor
call at `train.py:11189+` alongside the existing CG lambdas, matching
the pattern already used for `lambda_csr_token`, `lambda_vritti_token`,
etc.

#### File 4: `symbolu_training/training/unified/train.py`

Two changes. One in the forward call site to request the trajectory,
one in the CG loss block to consume it.

**Change 4a — request the trajectory in the CG forward call.**

The CG forward call site lives near line 4994 where the existing code
checks `'last_hidden_state'` and `'state'` in the outputs. The call
that produces `outputs` is upstream of that check, near line 3112
where `_need_hidden` is computed. The forward call itself already
passes `return_last_hidden=True` conditionally; add
`return_state_trajectory=True` next to it when LSTB is enabled:

```python
# train.py — wherever the CG forward call is constructed
_need_state_traj = (
    config.enable_conscious_generation
    and config.lambda_lstb > 0
)

outputs = model(
    input_ids=x,
    labels=y,
    return_last_hidden=_need_hidden,
    return_state_trajectory=_need_state_traj,   # NEW
    ...
)
```

The exact call site should be located by grepping for
`return_last_hidden` inside `train.py` and inserting the new kwarg
adjacent to every occurrence that serves the CG path.

**Change 4b — compute the LSTB loss inside the CG loss block.**

Inside the existing CG loss block at `train.py:4931+`, after
`_cg_sov_state = outputs.get('state', None)` at line 5000, add the
LSTB prediction loss. The loss must be placed **after** the existing
CG auxiliary losses so that its metrics appear grouped with the other
CG diagnostics, but the exact ordering does not affect correctness
because all CG auxiliaries contribute additively to `loss`:

```python
# train.py — inside CG loss block, after _cg_sov_state extraction

if config.lambda_lstb > 0:
    _cg_state_traj = outputs.get('state_trajectory', None)
    if (_cg_state_traj is not None
        and 'jepa_predictor' in model.conscious_gen
        and 'jepa_loss'      in model.conscious_gen):

        _k = config.lstb_k_steps
        _B, _T, _D = _cg_state_traj.shape

        # Need at least k+1 positions to form a (context, target) pair
        if _T > _k:
            # Context: positions [0 .. T-k-1]  (gradient flows through projector)
            # Target:  positions [k .. T-1]    (stop-gradient — standard JEPA)
            _lstb_context = _cg_state_traj[:, :-_k, :]
            _lstb_target  = _cg_state_traj[:,  _k:, :].detach()

            _lstb_predictor = model.conscious_gen['jepa_predictor']
            _lstb_loss_fn   = model.conscious_gen['jepa_loss']

            # Predict k-step state (causal by construction — see §3A.2 decision 5)
            _lstb_s_pred, _lstb_deltas = _lstb_predictor(
                _lstb_context, k_steps=_k,
            )

            # Compute composite loss (MSE + VICReg + ortho)
            _lstb_loss_result = _lstb_loss_fn(
                s_pred=_lstb_s_pred,
                s_target=_lstb_target,
                predictor_weight=_lstb_predictor.W_v.weight,  # for ortho term
            )
            _lstb_loss = _lstb_loss_result['loss']

            if torch.isfinite(_lstb_loss):
                loss = loss + config.lambda_lstb * _lstb_loss
                metrics['cg_lstb_loss']       = _lstb_loss.item()
                metrics['cg_lstb_mse']        = _lstb_loss_result['mse'].item()
                metrics['cg_lstb_vicreg']     = _lstb_loss_result['vicreg'].item()
                metrics['cg_lstb_ortho']      = _lstb_loss_result['ortho'].item()
                metrics['cg_lstb_target_var'] = _lstb_target.var(dim=0).mean().item()
```

**Guards in the sketch.** Four defensive conditions are present for
specific reasons, each of which would produce a silent failure if
omitted:

| Guard | What it protects against |
|-------|-------------------------|
| `_cg_state_traj is not None` | Ablation mode (`_use_state=False` in the wrapper) omits the trajectory; this check preserves ablation semantics |
| `'jepa_predictor' in model.conscious_gen` | Handles the case where `lambda_lstb > 0` was set after construction (e.g. via CLI override) but the model was built without LSTB. Explicit skip, not a crash |
| `_T > _k` | Handles short sequences at the start of training where `T ≤ k` would produce empty tensors |
| `torch.isfinite(_lstb_loss)` | Matches the defensive pattern used by every other CG auxiliary loss in this block — NaN in one auxiliary should not poison the whole step |

The exact field names on `_lstb_loss_result` (`'mse'`, `'vicreg'`,
`'ortho'`) should be confirmed against `JEPAPredictionLoss.forward`'s
return dict; if the keys differ, adjust the metric emission
accordingly without changing the loss computation.

#### Patch-size budget

Approximate line counts for the full change:

| File | Lines added |
|------|-------------|
| `mistral_wrapper.py` | ~8 (signature + trajectory branch) |
| `model_factory.py` | ~20 (predictor + loss construction, guarded) |
| `config.py` | ~8 (config fields) |
| `train.py` | ~40 (argparse + forward kwarg + loss block) |
| **Total** | **~76 lines** |

No existing code is modified beyond inserting new branches. No
existing function signatures are changed in a way that breaks
backward compatibility. No files outside the unified training
package are touched.

---

### 3A.4 Configuration Interface

This subsection specifies the user-facing contract for LSTB — what
flags exist, what they mean, what values are supported, and what the
recommended configurations are for the scenarios operators will
actually run. The argparse definitions are sketched in §3A.3; this
section is about the **contract**, not the parser code.

#### 3A.4.1 Flag reference

Six flags total. Five are tunable hyperparameters; one
(`--lambda_lstb`) is the master enable/disable.

| Flag | Type | Default | Valid range | Meaning |
|------|------|---------|-------------|---------|
| `--lambda_lstb` | float | `0.0` | `[0.0, 1.0]` | Master weight on the composite JEPA prediction loss. `0.0` disables LSTB entirely (no predictor constructed, no trajectory computed, zero compute cost). Values above `0.1` are not recommended for v1 without a reason — the LM cross-entropy path should remain dominant. |
| `--lstb_k_steps` | int | `1` | `{1, 2, 3, 4}` | Prediction lookahead. `1` means "predict the next-position state" (default, recommended). `> 1` enables autoregressive rollout inside `PhaseJEPAPredictor`; useful only if `k=1` measurements plateau and longer-horizon structure is needed. |
| `--lstb_vicreg_weight` | float | `0.5` | `[0.0, 10.0]` | Weight of the VICReg term inside `JEPAPredictionLoss`. `0.0` reduces the loss to pure MSE; higher values push harder against predictor collapse. The default matches the hard-probes `latent_bridge.py:364` benchmark. |
| `--lstb_ortho_weight` | float | `0.05` | `[0.0, 1.0]` | Weight of the orthogonality term on the predictor's learned projection matrices. Prevents the predictor from collapsing to a low-rank mapping. The default matches the hard-probes benchmark. |
| `--lstb_hidden_dim` | int | `128` | `{32, 64, 128, 256}` | Hidden dimension inside `PhaseJEPAPredictor`'s delta MLP. Larger values increase capacity at roughly linear cost; `128` is the default and is ~100K params total. |
| `--lstb_num_heads` | int | `4` | `{1, 2, 4, 8}` | Number of phase attention heads. Must evenly divide `state_dim=32`. The default of `4` gives `head_dim=8`. |

**Single enable flag convention.** `--lambda_lstb` is both the weight
and the master switch. There is intentionally **no** separate
`--enable_lstb` flag: it would be redundant and invite
inconsistent states ("enabled but weight is zero", "disabled but
weight is nonzero"). The `lambda_lstb > 0` check at construction time
and in the loss block ensures that the feature's compute cost is
strictly zero when disabled.

**Flags that do not exist and will not be added for v1.** For
completeness, the following are deliberate non-features — if an
operator asks about them, the answer is "not in v1, see §3A.8":

- `--lstb_target_encoder ema` — deferred EMA target encoder (§3A.2
  Decision 2, Option B).
- `--lstb_per_layer_schedule` — per-layer predictor schedules.
- `--lstb_vritti_gated` — the `VrittiValidatedPredictor` subclass.
- `--lstb_benchmark` — no standalone benchmark harness; LSTB is a
  training loss, not a research probe.

#### 3A.4.2 Recommended configurations

Three named configurations, each tied to a scenario. Operators should
pick the one that matches their scenario and resist the temptation to
tune before measuring.

**Configuration A — `off` (default).**
All existing runs, all non-CG runs, and every model type other than
`mistral_cg`. Zero code change from today:

```bash
--lambda_lstb 0.0
```

No other LSTB flags need to be set. The predictor is not constructed,
the trajectory is not computed, and the forward-dict contract is
unchanged from today.

**Configuration B — `v1` (recommended starting point for CG runs).**
The configuration that the §3A.6 success criteria are measured
against. This is what `scripts/train_mistral_cg.sh` should pass by
default **after** P0-1 is in place and validated:

```bash
--lambda_lstb 0.05
--lstb_k_steps 1
--lstb_vicreg_weight 0.5
--lstb_ortho_weight 0.05
--lstb_hidden_dim 128
--lstb_num_heads 4
```

Rationale for `lambda_lstb=0.05`: consistent with the weight envelope
of the existing CG auxiliaries (`lambda_ont=0.01`,
`lambda_kosha_routing=0.01`, `lambda_bliss_token=0.01`,
`lambda_plausibility_token=0.005`, etc. — see
`scripts/train_mistral_cg.sh` lines 60–66). LSTB is a stronger signal
than the token-level auxiliaries because it trains the projector
directly rather than through a shortlist scorer, so `0.05` puts it at
roughly 5× the individual token-level weights — enough to matter, not
enough to dominate.

**Configuration C — `stress-test` (for operators investigating
plateau).**
Use only after Configuration B has been run for at least 1000 steps
and the `cg_lstb_mse` metric has plateaued at a level the operator
considers too high. Increases capacity and signal strength:

```bash
--lambda_lstb 0.1
--lstb_k_steps 2
--lstb_hidden_dim 256
# VICReg and ortho weights unchanged from v1
```

Do **not** start here. Do not use these values for routine runs. If
Configuration C succeeds where Configuration B plateaus, file the
result and consider whether to raise the v1 defaults — but do not
change the config defaults in this design document until that
measurement is in hand.

#### 3A.4.3 Integration with `scripts/train_mistral_cg.sh`

The existing training script at `scripts/train_mistral_cg.sh:60–66`
defines CG lambda weights as shell variables:

```bash
LAMBDA_ONT=0.01
LAMBDA_KOSHA=0.01
LAMBDA_BLISS=0.01
LAMBDA_PLAUSIBILITY=0.005
LAMBDA_CSR=0.005
LAMBDA_VRITTI=0.005
LAMBDA_GUNA=0.005
```

and passes them to `python train_unified_llm.py` around lines 214–220.
The LSTB integration follows the same pattern — add the shell
variable near the existing block, pass it through to the Python
invocation near the existing `--lambda_*` flags:

```bash
# Near line 66, alongside the existing CG lambdas
LAMBDA_LSTB=0.05

# Near line 220, alongside the existing --lambda_* flags
    --lambda_lstb "$LAMBDA_LSTB" \
    --lstb_k_steps 1 \
```

The five tunable LSTB sub-flags (`--lstb_k_steps`,
`--lstb_vicreg_weight`, `--lstb_ortho_weight`, `--lstb_hidden_dim`,
`--lstb_num_heads`) **should not** be exposed as shell variables in
the script. They are fixed at the v1 defaults. An operator who wants
to change them should do so directly on the Python command line, not
by editing the script — this preserves the script as a "known-good
configuration" rather than a tuning playground.

**Smoke test mode** (`--smoke-test` in the shell script) already
overrides `MAX_STEPS=10` and sets `EXTRA_ARGS="--no_save --quiet"` at
lines 148–158. The LSTB shell variable should **not** be gated out
in smoke mode — LSTB adds negligible cost, and exercising its code
path in the smoke test is exactly what makes the smoke test useful as
a regression guard. Leave `LAMBDA_LSTB=0.05` active during the smoke
test so that a broken LSTB integration fails loudly on the ten-step
run.

#### 3A.4.4 Interaction with P0-1 flags

LSTB and P0-1 anti-collapse are complementary, not competing. They
should both be enabled on any production `mistral_cg` run. The full
set of new flags introduced by P0-1 + P1-1 on a standard CG run is:

```bash
# P0-1 — unary anti-collapse on pooled state (§1)
--lambda_sovereign_anticollapse 0.02
--anticollapse_warmup_steps 1000

# P1-1 — LSTB latent bridge on per-token trajectory (§3A)
--lambda_lstb 0.05
--lstb_k_steps 1
```

**Key contract between the two:**

- P0-1's `--lambda_sovereign_anticollapse` operates on the **pooled**
  `outputs['state']` `[B, 32]`. Its VICReg term uses
  `compute_collapse_only(x)` (unary, no target).
- P1-1's `--lambda_lstb` operates on the **per-token**
  `outputs['state_trajectory']` `[B, T, 32]`. Its VICReg term is
  inside `JEPAPredictionLoss` and uses the binary form
  `VICRegLoss(x_pred, y_target)` with nonzero invariance.

These are different inputs, different VICReg coefficients, different
attach points, and they pull the projector toward different
properties. **Neither subsumes the other.** If the two VICReg terms
ever produce numerically identical losses in a diagnostic, that is a
**bug** to investigate, not an optimization opportunity to exploit.

The detailed interaction analysis (when to dial one down, how to
attribute a regression to one or the other) lives in §3A.5 (Risks
and Mitigations, including the interaction risk table).

#### 3A.4.5 Forbidden configurations

Three flag combinations are explicitly **not supported** and should
produce a startup error, not a silent misbehavior:

1. `--lambda_lstb > 0` without `--enable_conscious_generation`.
   LSTB is CG-specific. Setting `lambda_lstb > 0` on a
   non-CG model type (`hybrid`, `ontological`, `mistral_hybrid`,
   etc.) should raise a clear error at argparse-validation time.
2. `--lambda_lstb > 0` with `--model_type` ≠ `mistral_cg` **and**
   `ontological_hybrid`. The latter is grandfathered in because
   `OntologicalHybridTransformer` also has a `SovereignStateProjector`
   and could in principle support LSTB, but that extension is out of
   scope for v1 (§3A.8). For v1, LSTB is `mistral_cg`-only.
3. `--lstb_k_steps >= seq_len`. If the requested lookahead is longer
   than the sequence length, no (context, target) pair can be
   formed. Raise a clear startup error instead of silently producing
   zero loss every step.

These checks live in the argparse validation block at `train.py` near
line 11189 where other cross-flag validation already happens (e.g.
the existing checks on `enable_conscious_generation` + CG sub-flag
consistency). A failure of any of these checks should abort startup
with a message naming the flag and the violated contract.

---

### 3A.5 Risks and Mitigations

LSTB has more failure modes than §1 (P0-1) or §2 (P0-2) because it
introduces a new **trainable module** (the JEPA predictor), a new
**training signal path** (stop-gradient JEPA loss), and a new
**forward-pass contract** (per-token state trajectory). Each of
those surfaces invites its own class of bug.

This section enumerates the risks worth naming explicitly, what
causes each to trigger, how to mitigate at design time, and — the
part most often missing from risk tables — **how an operator
actually detects the risk at runtime**. A mitigation that cannot be
verified by a metric is a mitigation that will drift.

#### 3A.5.1 Risk register

Ten named risks, grouped by category. Likelihood and severity are
relative to a v1 run with Configuration B from §3A.4.2
(`lambda_lstb=0.05, k=1`).

**Category A — Correctness risks (bugs that produce silently wrong
training):**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R1 | **Stop-gradient leaked on target.** `_lstb_target` is not actually detached (e.g. future refactor removes the `.detach()` at the call site). Projector learns the degenerate "constant state" solution because the target gradient pulls it toward being trivially predictable. | Medium (easy to regress on refactor) | **High** — silent training corruption, LM loss appears fine while 32D bottleneck collapses | Explicit `.detach()` call at the sketch in §3A.3 (File 4, Change 4b). Add a runtime assertion in the LSTB loss block: `assert not _lstb_target.requires_grad, "LSTB target must be detached"` | `cg_anticollapse_var` (P0-1 metric) drops sharply below baseline while `cg_lstb_mse` simultaneously collapses toward zero — both at the same step |
| R2 | **Non-causal predictor.** A future refactor of `PhaseJEPAPredictor._phase_attention` replaces `torch.cumsum(dim=1)` with a non-causal operation (e.g. a full self-attention). The predictor peeks at future tokens, MSE drops to near-zero, and the loss becomes meaningless. | Low (would require a conscious change to the predictor internals) | **High** — silent metric collapse, downstream decisions based on false success | Pin the causal-by-construction invariant in the design (§3A.2 Decision 5). Add a unit test in `symbolu_training/jepa/tests/test_jepa.py` that constructs a predictor, feeds a sequence with position `t+1` corrupted, and asserts the prediction for position `t` is unchanged | Unit test failure on refactor; at runtime, `cg_lstb_mse` approaches zero within the first 100 steps (suspiciously fast) |
| R3 | **Target / context shape mismatch.** The call site at File 4 Change 4b slices `state_traj[:, :-k]` and `state_traj[:, k:]` but a future change to `k_steps` handling in the predictor produces an off-by-one on the returned shape. MSE is computed on misaligned positions. | Low–Medium | Medium — training runs but optimizes the wrong objective | Runtime shape assertion before the loss call: `assert _lstb_s_pred.shape == _lstb_target.shape` | Assertion failure at step 0; or, if the assertion is missed, `cg_lstb_mse` is flat and suspiciously high across all steps |
| R4 | **Non-finite loss under `bfloat16` training.** `PhaseJEPAPredictor._phase_attention` at `predictor.py:244–249` casts inputs to `float32` for `torch.polar`, but the surrounding training loop runs in `bfloat16`. A mixed-precision bug at the boundary could produce NaN/Inf in the JEPA loss. | Low (the cast is already in place) | Medium — single-step crash, not corruption | The `torch.isfinite(_lstb_loss)` guard at File 4 Change 4b silently drops non-finite loss contributions, matching every other CG auxiliary. Emit a `cg_lstb_nonfinite_count` metric when the guard triggers | `cg_lstb_nonfinite_count > 0` in the per-step metrics; also visible as a step-level warning log |

**Category B — Signal quality risks (loss trains cleanly but carries
no useful information):**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R5 | **Predictor underfits due to 32D bottleneck.** The Sovereign State is only 32-dimensional. `PhaseJEPAPredictor` with `hidden_dim=128` may be over-parameterized relative to the prediction target, or conversely the target may be too low-entropy for the prediction loss to have meaningful dynamic range. Result: `cg_lstb_mse` plateaus at near-zero immediately, the loss contributes nothing. | Medium (unknown until measured) | Medium — feature is effectively off, but does not actively harm training | Measure `cg_lstb_mse` against a trivial-baseline predictor (identity: `s_pred = s_context`) at step 0 and at step 1000. If the learned predictor does not beat the baseline by a measurable margin (§3A.6 success criterion 2), downgrade LSTB to optional | `cg_lstb_mse / cg_lstb_identity_baseline_mse > 0.9` at step 1000 — i.e. the learned predictor is barely better than "predict current state unchanged" |
| R6 | **Predictor overfits the 32D space, ignores temporal structure.** With only 32 dimensions to predict, a high-capacity predictor can memorize a per-position mapping without learning actual sequence dynamics. The MSE looks great but the trained predictor fails to generalize across different sequences. | Low (the predictor is ~100K params, the dataset is large) | Medium | Validate at eval time on held-out sequences. Emit `cg_lstb_eval_mse` on a small eval subset during periodic eval. A large gap between train MSE and eval MSE indicates memorization | `cg_lstb_eval_mse / cg_lstb_mse > 2.0` — more than 2× gap between train and eval MSE |

**Category C — Interaction risks (LSTB works correctly in isolation
but interferes with other training signals):**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R7 | **Gradient interference with LM cross-entropy.** The per-token projection applied to `hidden` flows gradients back through the state projector, and from there into — nothing, since the Mistral backbone is frozen. **But** the projector is also used by existing CG auxiliaries that compute against the pooled `state`. Adding a new training signal to the projector changes the projector's update trajectory, which changes the pooled state, which changes every CG auxiliary that reads it. If `lambda_lstb` is too high, the projector is dragged toward "good JEPA target" at the expense of "good input to every other CG auxiliary." | Medium (directly controlled by `lambda_lstb`) | Medium — observable LM/CG auxiliary regression | v1 weight of `0.05` is chosen to keep LSTB subordinate to the LM cross-entropy path and approximately peer with the existing token-level auxiliaries. Success criterion 4 in §3A.6 requires that CG auxiliary losses be unchanged-or-improved, not merely "LM loss unchanged" | Any of `cg_ont_loss`, `cg_kosha_routing_loss`, `cg_vritti_token_loss`, `cg_L_csr` regresses by > 5% from a disabled-LSTB baseline at step 1000 |
| R8 | **Interaction with P0-1 anti-collapse.** Both terms push against projector collapse but operate on different inputs (pooled vs per-token) and in different VICReg modes (unary vs binary). If misconfigured, one term can dominate and make the other vestigial — or worse, they can pull in subtly different directions. | Medium | Medium | Treat P0-1 and P1-1 as a **linked pair** when tuning. If one is dialed up or down, re-measure the other. Emit both `cg_anticollapse_var` (P0-1, pooled) and `cg_lstb_target_var` (P1-1, per-token) at every metric-emit step so the operator can see both health curves side-by-side. See §3A.4.4 for the contract | `cg_anticollapse_var` and `cg_lstb_target_var` diverge — one healthy, the other collapsing |
| R9 | **CG curriculum stage interaction.** The existing CG curriculum (`cg_stage_manager` at `train.py:4934`) overrides CG lambda weights on a per-step schedule. If an early stage sets the CG auxiliaries to zero but the curriculum does not know about `lambda_lstb`, LSTB keeps training while every other CG signal is off — producing a projector pulled only by LSTB + P0-1 for a stage where no other CG module is learning. | Medium (depends on how the curriculum manager is written) | Low–Medium | Add `lambda_lstb` to the set of fields the curriculum manager can override. If the curriculum is written as a dict of overrides, simply ensure `lambda_lstb` is in the set of supported keys. Worst case, document that operators must set `lambda_lstb=0` manually during stages that zero out other CG auxiliaries | Stage transition in the curriculum log without a corresponding change in `cg_lstb_loss` magnitude |

**Category D — Operational risks (the feature works but is hard to
operate):**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R10 | **Checkpoint resume does not restore the predictor.** `PhaseJEPAPredictor` is attached to `model.conscious_gen['jepa_predictor']`. If the existing checkpoint save/load path at `symbolu_training/training/unified/checkpointing.py` does not iterate `model.conscious_gen` recursively, the predictor's parameters are silently initialized fresh on resume — but the surrounding training state (global_step, optimizer state, other CG modules) all resume normally. Result: LSTB loss spikes on the first step after resume as the freshly-initialized predictor scrambles to catch up. | Medium–High (depends on existing checkpointing behavior) | Medium — observable one-step spike, not silent corruption | Before shipping, **verify** that checkpointing iterates `model.conscious_gen` recursively. The existing CG modules (`kosha_routing_loss`, `bliss_coherence_loss`, etc.) have ~millions of params collectively, so if they resume correctly today, LSTB will too. If the check shows otherwise, it is a pre-existing bug affecting every CG module and must be fixed in the checkpointing code, not in LSTB | `cg_lstb_loss` on the first step after checkpoint resume is > 2× the value from the step immediately before the save |

#### 3A.5.2 Risk categories explicitly **not** covered

For completeness — these categories were considered and judged not
worth a row in the register above:

- **Compute cost.** The per-token projection adds <1% to forward
  cost (§3A.2 Decision 1). Predictor cost is O(B × T × 32) for
  attention and O(B × T × 32 × 128) for the delta MLP — both
  negligible. Memory for the new `state_trajectory` tensor is
  `B × T × 32 × 2 bytes` under bf16, ≈256KB per batch for `B=4,
  T=1024`. Not a risk.
- **Tokenizer / data pipeline interaction.** LSTB does not touch
  the tokenizer, the dataset, or the data loader. It operates
  entirely on per-token hidden states that are already produced by
  the forward pass. No data-pipeline risk surface.
- **Multi-GPU / DDP.** `PhaseJEPAPredictor` is a standard
  `nn.Module` with parameters that inherit the DDP wrapping of the
  surrounding model. No explicit synchronization is needed.
- **Interaction with §3B (CSR phonemic grounding).** §3B operates
  on column 3 of `T` (the Token Evaluation Tensor); §3A operates on
  `outputs['state_trajectory']`. These are disjoint tensors. No
  interaction surface. If §3B is shipped after §3A, the v1
  measurements from §3A do not need to be re-run.

#### 3A.5.3 Pre-flight mitigation checklist

Before running any `--lambda_lstb > 0` experiment, verify:

1. **P0-1 is already shipped and healthy.** LSTB's success criteria
   (§3A.6) assume `cg_anticollapse_*` metrics are available and
   within the healthy band defined in §1.7. Do not run LSTB on a
   build where P0-1 is not yet in place or is known to be broken.
2. **Checkpointing round-trips the predictor.** Construct a CG model
   with `--lambda_lstb 0.05`, save a checkpoint, reload it, and
   verify `model.conscious_gen['jepa_predictor'].state_dict()`
   matches exactly before and after the round-trip. This catches
   R10 at the cheapest possible moment.
3. **Identity baseline MSE is measured.** Run 100 steps with
   `--lambda_lstb 0.05` and log both `cg_lstb_mse` and a
   trivial-identity-baseline MSE (where the "prediction" is the
   context state unchanged). This establishes the reference that
   R5 and §3A.6 success criterion 2 measure against.
4. **Stop-gradient assertion is in place.** The runtime assertion
   from R1 (`assert not _lstb_target.requires_grad`) is
   non-negotiable for v1. It costs nothing and catches the single
   most expensive silent-failure mode.

All four checks should pass before the operator proceeds to the
§3A.7 rollout plan.

---

### 3A.6 Success Criteria

Success criteria are pass/fail gates, not aspirations. A feature that
cannot be shown to satisfy every gate on a **named evaluation run
against a named baseline** does not ship by default — it stays behind
a flag while the failure is investigated.

This section specifies (3A.6.1) the named evaluation run, (3A.6.2)
the named baseline it is compared against, (3A.6.3) the primary
gates, (3A.6.4) the diagnostic metrics that must be logged regardless
of gate outcome, and (3A.6.5) the downgrade path for when a gate
fails.

#### 3A.6.1 Named evaluation run

**Command.** Operators running the §3A.7 rollout step "1K-step
WikiText-2 measurement" must execute exactly this command, with only
`--checkpoint_dir` and output paths varying:

```bash
./scripts/train_mistral_cg.sh \
    --dataset wikitext2 \
    --max-steps 1000 \
    --lambda_sovereign_anticollapse 0.02 \
    --anticollapse_warmup_steps 1000 \
    --lambda_lstb 0.05 \
    --lstb_k_steps 1 \
    --checkpoint-dir checkpoints_lstb_v1
```

The `--lambda_sovereign_anticollapse` and
`--anticollapse_warmup_steps` flags are included because P0-1 is a
hard prerequisite for LSTB (§3A.5.3, pre-flight check 1). All other
LSTB sub-flags use their v1 defaults (`lstb_vicreg_weight=0.5`,
`lstb_ortho_weight=0.05`, `lstb_hidden_dim=128`, `lstb_num_heads=4`)
and do not appear on the command line.

**Environment.** Any single GPU with ≥24GB VRAM (A100, 4090, 3090).
4-bit Mistral quantization is the default and should be kept for this
measurement — changing quantization changes the numerical baseline
and invalidates comparison against runs with different precision.

**Runtime.** 1000 steps at batch 4 × grad accum 8 (`effective_batch =
32`) takes roughly 30–60 minutes on an A100. The smoke-test command
(10 steps) must succeed before this measurement is attempted.

#### 3A.6.2 Named baseline

Every gate is evaluated as a **delta** against a specific baseline
run, not against an absolute threshold. The baseline is:

```bash
./scripts/train_mistral_cg.sh \
    --dataset wikitext2 \
    --max-steps 1000 \
    --lambda_sovereign_anticollapse 0.02 \
    --anticollapse_warmup_steps 1000 \
    --lambda_lstb 0.0 \
    --checkpoint-dir checkpoints_lstb_baseline
```

The baseline run is **identical** to the evaluation run except that
`--lambda_lstb=0.0` (disabled). This isolates LSTB as the only
variable. Both runs share the same random seed, the same data, the
same LR schedule, and the same P0-1 configuration.

Run the baseline **first**, persist the full per-step metric log,
and only then run the evaluation. Do not compare against historical
runs from different dates, different code revisions, or different
configurations — the gates below are precise enough that small
unrelated changes invalidate the comparison.

#### 3A.6.3 Primary gates

Seven numbered gates. LSTB ships by default in
`scripts/train_mistral_cg.sh` only if **all seven** pass. Each gate
is stated as a pass condition; the operator records the observed
value and a pass/fail verdict.

**Gate 1 — LM loss is not degraded.**

> **Pass condition:** `lm_loss` at step 1000 on the evaluation run is
> within ±1% of `lm_loss` at step 1000 on the baseline run.

This is the LM-quality floor. LSTB is an auxiliary signal; it cannot
be shipped if it measurably degrades the primary language modeling
objective. A ±1% tolerance is chosen to absorb noise from sources
that are not LSTB (dropout, batch ordering, quantization-induced
nondeterminism) while still rejecting any real regression.

**Gate 2 — Learned predictor beats the identity baseline.**

> **Pass condition:** `cg_lstb_mse / cg_lstb_identity_baseline_mse
> < 0.7` at step 1000 on the evaluation run.

This is the "LSTB is doing something" gate, and it directly
addresses R5 from §3A.5 (predictor underfits the 32D bottleneck).
The identity baseline is a trivial "prediction equals context"
computation that is done on the same batch as the learned prediction
and logged as a diagnostic metric alongside `cg_lstb_mse`. If the
learned predictor cannot beat trivial self-prediction by at least
30%, LSTB is not learning temporal structure — it is burning FLOPs
to reproduce what a one-line tensor copy would produce.

**Gate 3 — P0-1 anti-collapse metrics remain healthy.**

> **Pass condition:** `cg_anticollapse_var` at step 1000 on the
> evaluation run is ≥ 95% of the same metric on the baseline run.

This directly addresses R8 (interaction with P0-1). P0-1's variance
metric is the health signal for the pooled Sovereign State. If LSTB
is correctly complementary — not competing — the pooled state should
remain at least as varied as it was without LSTB. A drop below 95%
of baseline indicates that LSTB is dragging the projector away from
P0-1's guard rail.

**Gate 4 — CG auxiliary losses are unchanged or improved.**

> **Pass condition:** For each of `cg_ont_loss`,
> `cg_kosha_routing_loss`, `cg_bliss_loss`, `cg_L_csr`,
> `cg_L_vritti`, `cg_L_guna`, the value at step 1000 on the
> evaluation run is within [-∞, +5%] of the baseline — that is, the
> loss may decrease freely but may not increase by more than 5%.

This addresses R7 (gradient interference with CG auxiliaries).
Asymmetric tolerance is deliberate: improvements are good (and
expected, since a better-trained projector should produce better
inputs to downstream CG modules), regressions are not. A 5% ceiling
on regressions catches real interference while absorbing noise.

**Gate 5 — No silent non-finite loss spikes.**

> **Pass condition:** `cg_lstb_nonfinite_count` is zero for every
> step in the evaluation run.

This addresses R4 (non-finite loss under `bfloat16`). The
`torch.isfinite` guard from §3A.3 File 4 Change 4b is permitted to
catch occasional NaN without failing the run, but any occurrence
during the v1 evaluation run is a hard stop: the root cause must be
diagnosed before shipping. Production-grade code should not rely on
the guard as a steady-state fallback.

**Gate 6 — Train/eval MSE gap is bounded.**

> **Pass condition:** `cg_lstb_eval_mse / cg_lstb_mse < 2.0` at step
> 1000, measured on a held-out WikiText-2 validation subset.

This addresses R6 (predictor memorizes per-position mapping instead
of learning sequence dynamics). A memorizing predictor shows a large
train-vs-eval gap; a genuinely learning predictor shows a gap near
1.0. The 2.0 ceiling is loose enough to absorb normal
train-vs-eval drift and tight enough to catch real memorization.
Requires emitting `cg_lstb_eval_mse` during periodic eval, which is
a new diagnostic that does not currently exist — adding it is part
of the File 4 patch.

**Gate 7 — Checkpoint round-trip preserves the predictor.**

> **Pass condition:** Save a checkpoint at step 500 of the
> evaluation run, load it into a fresh process, and verify that
> `model.conscious_gen['jepa_predictor'].state_dict()` matches
> exactly (bitwise) before and after the round-trip.

This addresses R10 (checkpoint resume does not restore the
predictor). The gate is a one-off manual verification, not a
continuous metric, but it must be performed at least once during the
rollout plan and the result recorded. If the check fails, LSTB is
blocked until checkpointing is fixed — but note that the fix likely
lives in `symbolu_training/training/unified/checkpointing.py`, not
in LSTB code, since the same bug would affect every other CG
module.

#### 3A.6.4 Required diagnostic metrics

Gates 1–7 are pass/fail. The following metrics must be **emitted on
every logging step** regardless of gate outcome, because they are
the raw signal operators use to diagnose a failure:

- `cg_lstb_loss` — total LSTB loss (MSE + VICReg + ortho).
- `cg_lstb_mse` — the raw MSE invariance term.
- `cg_lstb_vicreg` — the VICReg component.
- `cg_lstb_ortho` — the orthogonality component.
- `cg_lstb_identity_baseline_mse` — MSE of the trivial "predict
  current state unchanged" baseline, computed on the same batch.
- `cg_lstb_target_var` — variance of the (detached) target state
  across the batch, dimension-averaged. The per-token analog of
  P0-1's `cg_anticollapse_var`.
- `cg_lstb_nonfinite_count` — count of non-finite loss occurrences
  since the last log step. Should be zero; nonzero is Gate 5 failure.
- `cg_lstb_eval_mse` — train/eval MSE on the held-out subset, emitted
  during periodic eval (not every step).

These metrics are added as part of the File 4 training-loop change
in §3A.3 and are visible in whatever metric backend the operator is
using (TensorBoard, Weights & Biases, stdout JSON).

#### 3A.6.5 Failure mode decision tree

If any gate fails, do **not** re-tune in place. Instead, follow the
decision tree below to choose between "investigate the failure" and
"downgrade LSTB".

```
Gate 1 fails (LM loss regressed > 1%)?
    → Investigate R7. Lower lambda_lstb to 0.02, re-run. If Gate 1
      passes at 0.02 but Gate 2 also drops below 0.7, LSTB cannot
      be simultaneously non-regressive and effective at these
      hyperparameters — downgrade to optional.

Gate 2 fails (predictor does not beat identity by 30%)?
    → Investigate R5. Run Configuration C (§3A.4.2 stress-test)
      once. If Configuration C passes Gate 2 and still passes
      Gate 1, file the result and consider raising the v1 defaults.
      If Configuration C also fails Gate 2, downgrade LSTB to
      optional — the 32D state does not contain enough temporal
      structure for JEPA prediction to be a useful signal on this
      workload.

Gate 3 fails (P0-1 variance dropped > 5%)?
    → Investigate R8. This is the "linked pair" divergence. First
      re-run with lambda_lstb=0.02 and lambda_sovereign_anticollapse
      held constant. If Gate 3 still fails, the projector is being
      pulled by LSTB's VICReg (inside JEPAPredictionLoss) against
      P0-1's VICReg on pooled state — lower lstb_vicreg_weight from
      0.5 to 0.25 and re-run. Do not ship until Gate 3 passes.

Gate 4 fails (a CG auxiliary regressed > 5%)?
    → Investigate R7 and R9. Check whether the curriculum manager
      is overriding lambda_lstb on the stage where the regression
      appears. If not, lower lambda_lstb to 0.02 and re-run.

Gate 5 fails (any non-finite loss)?
    → Hard stop. Do not re-run. Attach a debugger, catch the
      non-finite step, and investigate the root cause in
      PhaseJEPAPredictor._phase_attention. The torch.polar float32
      cast at predictor.py:244-249 is the first place to look.

Gate 6 fails (train/eval MSE gap > 2x)?
    → Investigate R6. Lower lstb_hidden_dim from 128 to 64 (less
      memorization capacity) and re-run. If Gate 6 still fails,
      the predictor is overfitting — downgrade to optional.

Gate 7 fails (checkpoint round-trip is not bitwise-identical)?
    → Stop shipping LSTB. Fix the checkpointing bug in
      symbolu_training/training/unified/checkpointing.py (this is a
      pre-existing bug affecting every CG module, not an LSTB bug)
      and re-run the gate.
```

**Downgrade semantics.** "Downgrade LSTB to optional" means: keep
the code, keep the config flags, but do **not** add `--lambda_lstb
0.05` to `scripts/train_mistral_cg.sh` by default. LSTB remains
available for operators who want to experiment with it, but it is
not part of the default mistral_cg training configuration. This is
the same posture that P0-1 takes in §1.7 if the baseline does not
exhibit the collapse failure mode.

A downgrade is not a failure of the design — it is a finding that
LSTB, at v1 defaults, does not meaningfully improve the current
training configuration. The design stays in the document as
reference; the flags stay in the code as entry points; the default
stays off until a future experiment shows the downgrade can be
reversed.

---

### 3A.7 Rollout Plan

Seven sequential phases. Each phase produces a named artifact and a
go/no-go gate that unlocks the next phase. **Phases must not be
skipped, reordered, or run in parallel** — each one catches a class
of failure that later phases are blind to.

The rollout is deliberately conservative. LSTB touches the projector
that every other CG module reads, so a broken rollout would not
produce a localized failure — it would produce a diffuse regression
across every CG auxiliary, which is the hardest kind of failure to
attribute. Sequential phases keep attribution cheap.

#### 3A.7.1 Phase 0 — Prerequisites

**Inputs:** an up-to-date `main` with P0-1 already merged and the
four pre-flight checks from §3A.5.3 completed.

**Actions:**

1. **Verify P0-1 is shipped and healthy.** Run
   `./scripts/train_mistral_cg.sh --dataset wikitext2 --max-steps 200
   --lambda_sovereign_anticollapse 0.02`. Confirm `cg_anticollapse_*`
   metrics appear in the log and that the §1.7 success criteria are
   met on this short run. If P0-1 is absent or broken, stop here
   and fix P0-1 first.
2. **Locate `build_mistral_cg` in `model_factory.py`.** The
   function name may have drifted since this design was written —
   the important thing is to find the site where the existing CG
   modules (`kosha_routing_loss`, `bliss_coherence_loss`,
   `primitive_aux_losses`) are constructed. This is the target for
   §3A.3 File 2.
3. **Locate the CG loss block in `train.py`.** The current design
   references line 4931 as the start of the CG block and line 5000
   as the `_cg_sov_state` extraction site. Confirm these line
   numbers are still approximately correct by searching for
   `enable_conscious_generation and hasattr(model, 'conscious_gen')`
   — that string should match the block opening.
4. **Confirm `PhaseJEPAPredictor` exports.** Verify that
   `from symbolu_training.jepa.predictor import PhaseJEPAPredictor`
   and `from symbolu_training.jepa.losses import
   JEPAPredictionLoss` both succeed in an interactive Python
   session. These imports are the load-bearing dependency; if
   either fails, stop and investigate packaging.

**Artifact:** a short note (file or commit message) recording the
exact file paths and line numbers used in Phases 1–6. The line
numbers in this design document will drift; the rollout note is the
source of truth for the specific commit being shipped.

**Gate:** all four actions produce the expected output. No code has
been modified yet.

#### 3A.7.2 Phase 1 — Implementation

**Inputs:** the Phase 0 rollout note and §3A.3 (Integration Points).

**Actions:** apply the four-file patch described in §3A.3, in the
order:

1. **`config.py`** first. Add the six config fields. This is the
   safest first edit because nothing else depends on it and the
   fields default to off.
2. **`mistral_wrapper.py`** second. Add the
   `return_state_trajectory` kwarg and the guarded trajectory
   branch. Do **not** touch `compute_state_delta`. Run the CG
   smoke test (`./scripts/train_mistral_cg.sh --smoke-test`) after
   this edit to confirm the wrapper still constructs and forwards
   without the new flag set.
3. **`model_factory.py`** third. Add the `PhaseJEPAPredictor` and
   `JEPAPredictionLoss` construction, guarded by `config.lambda_lstb
   > 0`. Run the smoke test again with `--lambda_lstb 0.0` to
   confirm nothing changes when LSTB is off.
4. **`train.py`** last. Add the argparse flags, the
   `_need_state_traj` branch at the forward call site, and the
   LSTB loss block inside the CG loss region. This is the largest
   patch and the one most likely to need iteration — which is why
   it comes last, when every other file is already known-good.

**Artifact:** a single commit (or small commit series) on a feature
branch named `lstb-v1`. The commit message should reference this
design document by filename.

**Gate:**
- Project builds with no import errors.
- `./scripts/train_mistral_cg.sh --smoke-test` succeeds with the
  default configuration (no LSTB flags set).
- `./scripts/train_mistral_cg.sh --smoke-test` with
  `--lambda_lstb 0.0` explicitly set also succeeds (redundant but
  exercises the flag parsing path).

#### 3A.7.3 Phase 2 — Unit and integration tests

**Inputs:** the Phase 1 commit.

**Actions:**

1. **Add a unit test for `PhaseJEPAPredictor` causality.** File:
   `symbolu_training/jepa/tests/test_jepa.py`. The test constructs
   a predictor with `state_dim=32, k_steps=1`, feeds a sequence
   `[B=2, T=8, D=32]`, records the prediction at position 3, then
   perturbs position 4 (a future position relative to 3) and
   re-predicts. Assert that the prediction at position 3 is
   **bitwise identical** before and after the perturbation. This
   is the R2 regression guard from §3A.5.
2. **Add a unit test for stop-gradient correctness.** Same file.
   Construct a predictor + projector, forward a synthetic sequence,
   compute the LSTB loss, and assert that
   `projector.state_dict()` parameters have nonzero gradients on
   the context slice and zero gradients on the target slice after
   `loss.backward()`. This is the R1 regression guard.
3. **Add an integration test for checkpoint round-trip.** File:
   `tests/integration/test_mistral_cg_lstb_checkpoint.py` (new
   file, if no similar test exists). Build a CG model with
   `lambda_lstb=0.05`, save a checkpoint, reload into a fresh
   model instance, and assert that
   `model.conscious_gen['jepa_predictor'].state_dict()` is
   bitwise-identical before and after. This is the Gate 7
   pre-check from §3A.6.

**Artifact:** a follow-up commit on `lstb-v1` adding the three
tests. All three must pass on first run.

**Gate:** all three new tests pass locally. Full existing test
suite still passes (no regressions in unrelated tests).

#### 3A.7.4 Phase 3 — Smoke test

**Inputs:** the Phase 2 commit.

**Actions:**

1. Run `./scripts/train_mistral_cg.sh --smoke-test --lambda_lstb
   0.05 --lstb_k_steps 1`. This executes 10 steps on synthetic data
   with LSTB active.
2. Verify the expected metrics appear in the log:
   `cg_lstb_loss`, `cg_lstb_mse`, `cg_lstb_vicreg`,
   `cg_lstb_ortho`, `cg_lstb_target_var`,
   `cg_lstb_identity_baseline_mse`, `cg_lstb_nonfinite_count`.
3. Confirm `cg_lstb_nonfinite_count == 0` across all 10 steps.
4. Confirm the run completes without crashing or producing a
   Python exception.

**Artifact:** a log file from the smoke test, saved with the
filename `smoke_lstb_v1_<date>.log` attached to the rollout note
from Phase 0.

**Gate:** smoke test completes cleanly, all expected metrics are
present, no non-finite loss occurrences. If any of these fail, stop
and return to Phase 1 — do **not** attempt to debug on a real
training run.

#### 3A.7.5 Phase 4 — Baseline measurement

**Inputs:** the Phase 2 commit (not yet touching defaults).

**Actions:**

1. Run the **baseline** command from §3A.6.2 — identical to the
   evaluation command but with `--lambda_lstb 0.0`. This takes
   30–60 minutes on an A100.
2. Persist the full per-step metric log to
   `metrics_lstb_baseline_<date>.jsonl` (or the equivalent in the
   metric backend being used).
3. Verify that `cg_anticollapse_*` metrics are healthy throughout —
   this is the P0-1 health baseline that Gate 3 is measured
   against.
4. Record the following specific values at step 1000 to the
   rollout note:
   - `lm_loss` (for Gate 1 comparison)
   - `cg_anticollapse_var` (for Gate 3 comparison)
   - `cg_ont_loss`, `cg_kosha_routing_loss`, `cg_bliss_loss`,
     `cg_L_csr`, `cg_L_vritti`, `cg_L_guna` (for Gate 4 comparison)

**Artifact:** the baseline metrics log + the rollout note's "Phase 4
baseline values" block.

**Gate:** baseline run completes cleanly. `cg_anticollapse_var` is
healthy (see §1.7 criterion 2). The seven values needed for Gates
1, 3, and 4 are recorded.

**This phase is non-optional even if P0-1 was verified healthy in
Phase 0.** The Phase 0 check was a 200-step smoke; Phase 4 is the
full 1000-step baseline that Gate comparisons are measured against.

#### 3A.7.6 Phase 5 — Evaluation measurement

**Inputs:** the Phase 4 baseline metrics and the Phase 2 commit.

**Actions:**

1. Run the **evaluation** command from §3A.6.1 — identical to the
   baseline but with `--lambda_lstb 0.05`. Same seed, same data,
   same LR schedule.
2. Persist the full per-step metric log to
   `metrics_lstb_eval_<date>.jsonl`.
3. At step 500, pause the run (or save a mid-run checkpoint without
   stopping) and perform the Gate 7 checkpoint round-trip check
   manually: load the step-500 checkpoint in a fresh Python process,
   extract `model.conscious_gen['jepa_predictor'].state_dict()`,
   and compare bitwise against the same dict from the running
   process. Record pass/fail.
4. Let the run complete to step 1000.
5. Record the same seven values as Phase 4 (plus the LSTB-specific
   metrics) at step 1000.

**Artifact:** the evaluation metrics log + the rollout note's
"Phase 5 evaluation values" block + the Gate 7 pass/fail record.

**Gate:** evaluation run completes cleanly. No non-finite loss
occurrences (this is a soft check — Gate 5 is the hard check at
Phase 6).

#### 3A.7.7 Phase 6 — Gate evaluation

**Inputs:** the Phase 4 baseline values and the Phase 5 evaluation
values.

**Actions:**

1. Open a fresh section of the rollout note titled "Gate evaluation".
2. For each of Gates 1–7 from §3A.6.3, compute the pass condition
   from the recorded values and record **pass** or **fail** with
   the observed value and the threshold. Do not round, do not
   summarize — record the raw numbers.
3. Identify the first failing gate (if any) and consult the §3A.6.5
   decision tree for the next action.

**Artifact:** the completed gate evaluation block in the rollout
note. Seven pass/fail verdicts with raw numbers.

**Gate:** this phase has no gate — it is pure evaluation. The
outcome determines which branch of Phase 7 runs.

#### 3A.7.8 Phase 7 — Decision

**Inputs:** the Phase 6 gate evaluation.

**Branch A — all seven gates pass.**

1. Update `scripts/train_mistral_cg.sh` to pass `--lambda_lstb
   0.05 --lstb_k_steps 1` by default (the §3A.4.3 integration).
2. Add a commit to `lstb-v1` documenting the gate evaluation
   results. Reference the rollout note.
3. Merge `lstb-v1` to `main`.
4. File a follow-up ticket to monitor `cg_lstb_*` metrics on the
   next production run for drift.

**Branch B — one or more gates fail.**

1. Consult §3A.6.5 for the failing gate's investigation path.
2. If the decision tree recommends re-running with different
   hyperparameters (e.g., `lambda_lstb=0.02`, `lstb_vicreg_weight=0.25`),
   return to Phase 5 with the new values. **Do not modify Phase 4
   baseline** — the baseline is unchanged, only the evaluation run
   is re-run.
3. If the decision tree recommends downgrading:
   - Keep the Phase 2 commit merged (code and flags stay).
   - Do **not** add `--lambda_lstb` to
     `scripts/train_mistral_cg.sh`.
   - File a finding note recording which gate failed and why, so
     that a future operator considering LSTB can see the historical
     measurement rather than repeating it.
   - Mark LSTB as "available but not default" in the project's
     feature status document (if one exists).
4. If the decision tree recommends a hard stop (Gate 5 or Gate 7):
   - Revert the Phase 2 commit.
   - Do not merge `lstb-v1`.
   - File a bug against the root cause (bf16 / polar cast for
     Gate 5, checkpointing for Gate 7).
   - LSTB cannot be shipped until the root cause is fixed, **but**
     the fix is not LSTB work — it is pre-existing infrastructure
     work.

#### 3A.7.9 Post-ship follow-ups (Branch A only)

These are optional experiments that can be filed as follow-up
tickets. None of them are required for v1, and all of them are
explicitly out of scope for this design document (§3A.8).

1. **Configuration C stress-test.** Run the §3A.4.2 Configuration C
   for 1K steps and compare against v1. If Configuration C
   produces meaningfully lower `cg_lstb_mse` without regressing
   Gates 1, 3, or 4, file a result and consider raising the v1
   defaults in a follow-up design revision.
2. **Multi-step lookahead.** Try `--lstb_k_steps 2` for 1K steps.
   Record whether the multi-step rollout in
   `PhaseJEPAPredictor.forward` produces meaningful signal on the
   32D state or plateaus at the same MSE as `k=1`.
3. **EMA target encoder.** Add an EMA copy of
   `SovereignStateProjector` and use it to produce targets in the
   LSTB loss block. Measure whether the EMA target unlocks
   improvement that the same-projector stop-gradient target could
   not. This is a 2–3 day experiment, not a single-run measurement.
4. **`VrittiValidatedPredictor` substitution.** Swap
   `PhaseJEPAPredictor` for `VrittiValidatedPredictor` in
   `model_factory.py` and measure whether Vritti gating changes
   the training curve. Requires the Vritti classifier to be
   producing meaningful signals, which itself depends on the v1
   CG run being healthy.
5. **Ontological hybrid path.** Extend LSTB to the
   `ontological_hybrid` model type (which also has a
   `SovereignStateProjector`). Requires checking whether the
   forward path of `OntologicalHybridTransformer` exposes a
   per-token projection surface analogous to
   `MistralCGWrapper.return_state_trajectory`.

Each of these is a research-grade experiment, not a routine
rollout. File them as tickets; do not run them opportunistically.

#### 3A.7.10 Rollback path

At any phase up through Phase 7 Branch B, rollback is a single
action: **do not merge `lstb-v1` to `main`**. Because LSTB is
entirely additive (no existing file signatures are modified, no
defaults are changed until Phase 7 Branch A), rollback does not
require reverting anything. The branch can be left open indefinitely
as a reference, or deleted after the finding note is filed.

If LSTB **has** been merged and a regression is discovered in
production, rollback is: set `LAMBDA_LSTB=0.0` in
`scripts/train_mistral_cg.sh` and force a redeploy. No code revert
is needed because the flag is the master switch. A full code revert
is only required if the R1 or R2 correctness risks turn out to have
been triggered and the code in `mistral_wrapper.py` or `train.py`
is producing silent corruption even when the flag is zero — which
should be impossible by design, but is the reason the master-switch
behavior is tested in Phase 1.

---

### 3A.8 Out of Scope

Out-of-scope items are grouped into three categories by intent:
**deferred** (plausible follow-ups with a measurement path),
**hard limits** (things LSTB will not do even if asked), and
**non-goals** (clarifications about what LSTB is not claiming to be).

Each item here has been considered at least briefly during the design.
Readers encountering one of these items in a review or a feature
request should be able to cite this section rather than re-arguing
the scope.

#### 3A.8.1 Deferred — plausible follow-ups, not shipped in v1

These are the items already listed in §3A.7.9 as post-ship
experiments, re-stated here with the explicit reason each one is
deferred. Every item is a valid future experiment with a clear
measurement path, but none of them is justified by any evidence
currently in hand.

- **Multi-step lookahead (`k_steps > 1`).** `PhaseJEPAPredictor`
  supports autoregressive rollout up to `k` steps, but v1 ships with
  `k=1` only. Reason: §3A.2 Decision 5 — `k=1` is the densest signal,
  the lowest-variance training target, and the minimum sufficient
  test of whether the projector can produce temporal structure at
  all. Raising `k` before `k=1` is measured would conflate two
  independent questions ("is LSTB useful?" and "is longer-horizon
  prediction useful?") into one.
- **EMA target encoder.** §3A.2 Decision 2 Option B. Maintain an
  exponential-moving-average copy of `SovereignStateProjector` and
  use it to produce prediction targets. Reason: the same-projector
  stop-gradient recipe (Option A) is simpler, adds no checkpoint
  state, adds no decay hyperparameter, and is sufficient for v1
  according to the hard-probes benchmark that already uses it.
  Upgrade is justified only if Option A plateaus.
- **`VrittiValidatedPredictor` substitution.** The subclass at
  `predictor.py:304` adds Vritti-gated updates that skip prediction
  when the Vritti classifier reports low cognitive reliability.
  Reason: it is a gating mechanism on top of the base predictor, not
  a replacement, and gating is only useful if (a) the base predictor
  is already producing meaningful signal and (b) the Vritti
  classifier is itself healthy. Neither is true in a v1 run — both
  are brand-new signals on the same commit.
- **Ontological hybrid path extension.** `OntologicalHybridTransformer`
  (the non-Mistral hybrid path) also has a `SovereignStateProjector`
  and could in principle support LSTB identically. Reason: extending
  to a second model type doubles the test surface and the rollout
  effort with no additional learning, because both paths share the
  same projector and the same predictor code. Ship on `mistral_cg`
  first, port to `ontological_hybrid` second if v1 succeeds.
- **Configuration C stress-test as default.** The higher-capacity
  configuration from §3A.4.2 (`lambda_lstb=0.1, k=2, hidden_dim=256`)
  is deferred because it trades off against Gate 1 (LM loss floor)
  and Gate 7 (gradient interference) more aggressively than v1. Use
  only as a plateau investigation tool, not as a default.
- **Per-stage predictor schedules.** A hypothetical design where
  the predictor is active only during certain CG curriculum stages
  (e.g., enabled in Stage 4+ once the pooled state is trained).
  Reason: adds a scheduling contract between LSTB and
  `cg_stage_manager` that v1 does not need — v1 simply lets the
  curriculum manager override `lambda_lstb` per-stage
  (§3A.5 R9), which is strictly more flexible than a hard-coded
  schedule.

#### 3A.8.2 Hard limits — will not be done even if asked

These are items that LSTB v1 actively refuses to do. They are not
"deferred" — they are architecturally out of the feature's job
description, and adding them would turn LSTB into a different
feature.

- **No modification to `SovereignStateProjector`.** The projector's
  architecture — MLP layers, per-plane activations (softmax on
  Bhava, sigmoid on Kosha, etc.), component-wise normalization — is
  untouched. LSTB consumes the projector's output; it does not
  redesign the projector. If a future finding shows that the
  projector architecture is wrong, that is a separate design
  effort, not an LSTB revision.
- **No modification to `compute_state_delta`.** The pooled state
  path at `mistral_wrapper.py:291` is load-bearing for §1 (P0-1),
  Stage 8 Perspective Synthesizer, and every existing CG auxiliary.
  LSTB adds a new trajectory path alongside it but does not touch
  the pooled path itself. A future design that wants to unify the
  two paths is a separate effort.
- **No modification to `PrimitiveAuxiliaryLosses` or the Token
  Evaluation Tensor `T`.** `L_jepa`, `L_csr`, `L_vritti`, `L_guna`
  all stay exactly as they are. LSTB does not replace them, augment
  them, or reinterpret them. In particular, LSTB does **not**
  address the CSR phonemic grounding gap — that is §3B's job,
  shipped independently.
- **No gradient flow to the frozen Mistral backbone.** `MistralCGWrapper`
  sets `requires_grad=False` on the backbone at
  `mistral_hybrid_wrapper.py:86` (the analogous line exists in the
  CG wrapper). LSTB's per-token projection runs on the backbone's
  output `hidden` tensor, which already has `requires_grad=False`
  flowing into the projector. Gradients reaching backbone
  parameters from the LSTB loss would be a bug, not a feature. The
  frozen-backbone contract is a hard limit that LSTB explicitly
  preserves.
- **No inference-time footprint.** `PhaseJEPAPredictor` is a
  training-only module. It is constructed inside
  `model.conscious_gen` but is not exercised during generation.
  Checkpoints saved with LSTB enabled are fully compatible with
  inference-time loading paths that do not instantiate the
  predictor — the predictor weights are simply ignored.
  Inference-time latency, memory, and output shape are all
  unchanged.
- **No dataset, tokenizer, or data-pipeline changes.** LSTB operates
  entirely on tensors that already flow through the training loop.
  No new vocabulary entries, no new tokenizer behavior, no new
  dataset fields, no new preprocessing. The WikiText-2 evaluation
  run in §3A.6.1 uses the unchanged existing data pipeline.
- **No new model_type.** LSTB ships as a flag on the existing
  `mistral_cg` model type. It does **not** introduce a new
  `--model_type mistral_cg_lstb` or similar. The model type
  taxonomy stays at its current size; LSTB is a trainable
  sub-module, not a new architecture.

#### 3A.8.3 Non-goals — clarifications about what LSTB is not

These are not limits or deferrals; they are clarifications of the
feature's claim. Someone reading "LSTB is a latent bridge" might
reasonably infer capabilities that LSTB does not actually provide.
This subsection preempts those inferences.

- **LSTB is not a semantic quality metric.** `cg_lstb_mse` measures
  latent-space distance between predicted and target Sovereign
  State vectors. It does **not** measure whether the predicted
  state is semantically correct, whether it corresponds to a valid
  ontological state, or whether it would produce good generations
  downstream. MSE is a training signal, not an evaluation metric.
- **LSTB is not a downstream inference conditioner.** The predicted
  state `_lstb_s_pred` is used **only** as input to the MSE loss
  and is then discarded. It is not fed back into the model as a
  conditioning signal, not used to modify `adapted_hidden`, and not
  available to Stage 8 Perspective Synthesizer. If a future design
  wants to condition inference on predicted states, that is a
  different feature — probably closer to the "Phase 3 causal
  conditioning" mode referenced by the `--lstb-phase 3` flag in
  `train_hard_probes.py` — and is deferred indefinitely.
- **LSTB is not a replacement for the CG auxiliary losses.** It
  augments them with a self-supervised temporal target. `L_ont`,
  `L_kosha_routing`, `L_vritti`, and friends are still the primary
  ways the Sovereign State is connected to the language modeling
  task. LSTB's job is to make the projector's output *temporally
  coherent*, not to make it *correct* in the sense that downstream
  CG losses define correctness.
- **LSTB is not a research benchmark.** The hard-probes
  `latent_bridge.py` benchmark at
  `scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/latent_bridge.py`
  is a research probe: it measures R² of state prediction on
  synthetic data, ablates individual JEPA components, tests VICReg
  health, and runs an ontology alignment check. LSTB v1 is a
  **training loss**. It does not port the benchmark harness, does
  not emit the benchmark's metrics, and does not replicate its
  ablation study. If research-grade measurement is needed,
  operators should continue to use the hard-probes benchmark on
  the same model checkpoints — the two tools are complementary, not
  redundant.
- **LSTB is not an answer to "does the 32D state carry meaning?"**
  It is specifically an answer to "does the 32D state carry
  **temporally coherent** meaning?" A projector that produces a
  state with no semantic content but smooth temporal trajectories
  will pass every LSTB gate and still be useless for downstream
  reasoning. The CG auxiliary losses are the signals that test
  semantic content; LSTB is the signal that tests temporal
  coherence. **Both are necessary, neither is sufficient, and this
  design document does not claim LSTB is enough on its own.**

---

*End of §3A. §3B (CSR phonemic grounding, half depth) follows next.*
