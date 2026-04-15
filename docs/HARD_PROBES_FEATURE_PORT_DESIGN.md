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

*3A.3 (Integration Points) follows next.*
