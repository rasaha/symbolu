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

## §3B — CSR Phonemic Grounding for `L_csr`

*Secondary sub-task of P1-1. P3 priority. Gated on §3A.6 baseline
measurements. Written at half the depth of §3A — anywhere a decision
depends on §3A's outcome, this section defers rather than
pre-deciding.*

### 3B.1 Problem Statement

Per §3.1, the earlier framing that `lambda_csr_token` was a "dangling
weight" is wrong. The weight drives a real InfoNCE contrastive loss
inside `PrimitiveAuxiliaryLosses.forward()` at
`symbolu_training/training/conscious_generation/losses/primitive_auxiliary.py:27`.
That loss takes the scorer's output column for CSR (index 3 of the
Token Evaluation Tensor `T`), identifies the correct token's score
within a shortlist, and computes softmax cross-entropy against the
negative candidates. Gradients flow back through whatever scorer
produced column 3. This is a perfectly functional contrastive ranking
loss.

What the existing loss does not do is **ground column 3 in actual
phoneme structure**. Nothing in the training signal forces the scorer
to produce a CSR column that correlates with the phonemic properties
of the candidate tokens. Column 3 learns whatever it needs to learn
to minimize InfoNCE on the shortlist — which, given enough scorer
capacity, can be satisfied by any arbitrary ranking function that
happens to separate correct from incorrect tokens. That function may
or may not resemble phonemic similarity; the training signal has no
opinion on the matter.

The doctrinal context matters here. `SovereignStateProjector` at
`symbolu_training/jepa/state_projector.py:13–14` comments:

> Note: Manomaya (Mental Plane) is handled by CSR (phonemic/resonance),
> which operates outside the 32D state as a separate scoring
> primitive.

CSR is **architecturally positioned** as the phonemic/resonance signal
— the Mental Plane that sits outside the 32D Sovereign State precisely
because it operates on symbolic phonemic structure rather than on
pooled hidden states. The existing `L_csr` loss trains the CSR column
without reference to that symbolic structure, so the doctrinal claim
("CSR is phonemic") and the training reality ("CSR is whatever the
scorer learned to rank") are quietly disconnected.

The hard-probes CSR bridge provides a concrete mechanism to close
that gap. At
`scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/csr_bridge.py:62–78`,
the `CSREmbeddingProvider` / `VarnaCSRBridge` / `ARPABET_TO_VARNA` /
`SANSKRIT_VOWEL_CALIBRATION` modules decompose words into ARPABET
phonemes, map phonemes to Varna classes, and produce 10D resonance
vectors per token. That decomposition is the "actual phonemic
structure" that the existing `L_csr` loss currently has no opinion
about.

§3B proposes to wire that decomposition into `PrimitiveAuxiliaryLosses`
as an **optional auxiliary target for column 3** — not to replace the
InfoNCE loss, but to augment it with a phonemic alignment term that
pulls column 3 toward correlating with the phonemic similarity of the
shortlist candidates.

**Why this is P3 and not P1.** The existing `L_csr` contributes
normally to CG training and there is no evidence that the lack of
phonemic grounding is causing downstream harm. No operator has
reported a CG training failure that was root-caused to "column 3 of
T is not phonemically grounded." The value of §3B is therefore
**latent**: it is a quality upgrade that might matter if and when a
future measurement shows that symbolic CSR matters for downstream
reasoning, interpretability, or generalization. Until such a
measurement exists, §3B is a design option on the shelf, not a
shipping feature.

**Who would want §3B.** Three plausible stakeholders, in decreasing
order of likelihood:

1. An operator debugging an interpretability probe who wants the CSR
   column to mean what the doctrine says it means (phonemic
   resonance), not whatever the scorer invented.
2. A researcher running the hard-probes `test_csr_bridge` benchmark
   on a trained CG model and finding that the model's CSR column
   fails the phonemic correlation check in the benchmark.
3. A future extension of the Manomaya plane that assumes column 3
   carries real phonemic information and breaks quietly when it
   does not.

None of these stakeholders currently has an open ticket. §3B's job
is to make sure that when one of them does, the design is ready to
ship rather than requiring a fresh investigation.

**Complication: BPE tokens are not phonemes.** Mistral uses
byte-pair-encoded subword tokens. Many Mistral tokens are valid
English words, but many others are sub-word fragments, punctuation,
or whitespace. ARPABET decomposition works cleanly on words and
degrades gracefully on common fragments, but it has no meaningful
output for punctuation or rare byte sequences. This means phonemic
grounding is **partial** — it can provide a training signal on the
subset of tokens that have meaningful phonemic decompositions, but
cannot cover the full vocabulary. §3B's design must acknowledge this
and skip the phonemic target for tokens where the decomposition is
unavailable or ill-defined, rather than corrupting the signal with
garbage phonemes for the long tail.

The rest of §3B describes a design that, when shipped, adds this
phonemic alignment term to `L_csr`, gates it behind a dedicated flag,
and measures whether enabling it improves a named phonemic
correlation probe without regressing any existing CG metric. It does
**not** claim that §3B is necessary, useful, or ready to ship — those
questions are explicitly deferred to the measurements in §3A.6 and
any future follow-up investigation.

---

### 3B.2 Design Approach

Four design decisions drive the implementation. Fewer than §3A.2
because §3B is a simpler feature — it adds one new auxiliary term
to an already-wired loss, rather than introducing a new trainable
module with its own forward-pass contract.

#### Decision 1: Where to host the phoneme provider

The hard-probes `csr_phoneme_provider` lives at
`scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/csr_bridge.py:62–78`.
That file is inside a research tree that is not packaged for import
from the unified pipeline. Two options:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | Port the provider into `symbolu_training/training/conscious_generation/providers/csr_phoneme.py` as a reusable module | **Chosen** |
| B | Import directly from `hard_probes_lib.benchmarks.csr_bridge` | Rejected — `hard_probes_lib` is a research tree, imports from production code would create a dependency inversion |

Option A copies only the minimum surface needed: `ARPABET_TO_VARNA`,
`SANSKRIT_VOWEL_CALIBRATION`, `simple_text_to_phonemes`, and the
10D resonance vector generator. The benchmarks built on top of these
(the `run_csr_bridge_benchmark_integration` harness, the ablation
studies) **stay in hard-probes** — §3B ports the primitives, not the
research tools.

The new module exposes a single public function:

```python
def get_phonemic_embedding(token_ids: List[int], tokenizer) -> torch.Tensor:
    """Return [N, 10] phonemic resonance vectors for the given tokens.

    Tokens without meaningful phonemic decomposition get a zero row
    AND a mask entry of 0 in the returned mask.

    Returns:
        vectors: [N, 10] float tensor
        mask:    [N]     bool tensor, True where the decomposition is valid
    """
```

#### Decision 2: Phonemic target shape and loss form

The existing `L_csr` loss takes column 3 of the Token Evaluation
Tensor `T` and trains it to rank the correct token highest among
shortlist candidates via InfoNCE. The phonemic grounding must hook
into that same column without disrupting the ranking semantics.
Three options:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | **Cosine-similarity target on column 3.** For each (target, candidate) pair, compute `cos_sim(phon_target, phon_candidate)` as an auxiliary regression target, and add `MSE(T[..., 3], cos_sim_matrix)` as a new term | **Chosen** |
| B | **Replace column 3 with a phonemic dot product.** Feed the 10D phonemic vectors through a learned projection to produce column 3 directly | Rejected — invasive, replaces a working loss instead of augmenting it |
| C | **Soft-label KL divergence.** Produce a soft distribution over candidates from phonemic similarity, compare against `softmax(T[..., 3])` via KL | Deferred — more principled but requires more careful temperature tuning, defer to follow-up |

Option A is the minimum change. It says "column 3 should roughly
correlate with phonemic similarity," not "column 3 should equal
phonemic similarity." The new term is an **auxiliary regression
pressure** on top of the existing InfoNCE ranking pressure; the
two coexist and are both useful.

**Composition with the existing `L_csr` term:**

```text
L_csr_total = L_csr_infonce                         # existing, unchanged
            + lambda_csr_phonemic * L_csr_phonemic  # new, additive
```

where `L_csr_phonemic = MSE(T[..., 3], cos_sim_matrix)` masked to
positions where the phonemic decomposition is valid (see Decision 3).
Neither term replaces the other. The existing `lambda_csr_token`
weight is unchanged; the new `lambda_csr_phonemic` weight is
separate and defaults to 0.

#### Decision 3: Missing-decomposition handling

Not every Mistral BPE token has a meaningful phonemic decomposition
(§3B.1 BPE complication). Three options for tokens where the
provider returns a zero row:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | **Skip the phonemic term for invalid tokens** — mask the MSE contribution to zero for any (target, candidate) pair where either side has an invalid decomposition | **Chosen** |
| B | Use a neutral default vector for invalid tokens | Rejected — pollutes the signal with a spurious similarity baseline |
| C | Filter invalid tokens out of the batch entirely | Rejected — reduces the effective batch size in a non-transparent way |

Option A preserves the existing loss structure: the InfoNCE term
still runs on the full shortlist, only the **phonemic regression
term** is masked out for tokens where the ground truth is missing.
This means the phonemic signal is strictly additive — it can only
improve training on tokens where phonemic decomposition is well-
defined, and is a no-op on tokens where it is not.

The provider's returned `mask` (from Decision 1) is the input to
the masking logic. The masked MSE is computed as:

```python
# valid_mask: [B, K] — True where BOTH target and candidate have
# valid phonemic decompositions
masked_mse = ((T[..., 3] - cos_sim_matrix) ** 2 * valid_mask).sum() \
           / valid_mask.sum().clamp(min=1.0)
```

The `.clamp(min=1.0)` guards against the degenerate case where a
batch contains zero valid pairs — which should be rare but produces
a silent NaN otherwise.

#### Decision 4: Caching strategy (precompute vs on-the-fly)

ARPABET decomposition is a string-processing operation that is not
vectorizable on GPU. Doing it per-forward-pass would serialize
through a Python loop and crater throughput. Since the vocabulary
is fixed at model construction time, the phonemic table can be
precomputed once and consulted by ID lookup thereafter.

**Chosen: precompute a `[vocab_size, 10]` phonemic table at model
construction time** and store it as a buffer (not a parameter —
phonemic embeddings are not trainable) on the
`PrimitiveAuxiliaryLosses` module. Also precompute a
`[vocab_size]` boolean mask of which token IDs have valid
decompositions.

**Budget.** Mistral's vocabulary is ~32,000 tokens. The phonemic
table is `32000 × 10 × 4 bytes = 1.28 MB` in float32. The validity
mask is `32000 × 1 bit = 4 KB`. Both are negligible relative to
every other tensor in the training loop.

**Construction site.** The table is built once inside
`PrimitiveAuxiliaryLosses.__init__` when `lambda_csr_phonemic > 0`,
using the model's tokenizer (passed in at construction time). The
tokenizer reference is already available inside `model_factory.py`
where `PrimitiveAuxiliaryLosses` is constructed — no new plumbing
is needed.

**Fallback when construction fails.** If the phoneme provider
raises an exception (e.g., missing `cmudict` dependency,
tokenizer vocabulary mismatch), log a warning and set
`lambda_csr_phonemic = 0.0` for the rest of the run. Phonemic
grounding is an optional quality upgrade; a broken provider should
not crash the training run.

---

### 3B.3 Integration Points

Five files touched. §3B's integration is narrower than §3A's
because it does **not** touch `mistral_wrapper.py` — the phonemic
term operates on the Token Evaluation Tensor `T` that already
flows through the CG loss block at `train.py:5218`, where
`PrimitiveAuxiliaryLosses.forward()` is called. No new
forward-pass contract is needed.

Sketches below are illustrative, not literal patches.

#### File 1: `symbolu_training/training/conscious_generation/providers/csr_phoneme.py` (NEW)

Port the phoneme provider primitives from
`scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/csr_bridge.py:62–180`.
Copy only what is strictly needed:

- `ARPABET_TO_VARNA` — dict mapping ARPABET phonemes to Varna classes.
- `SANSKRIT_VOWEL_CALIBRATION` — calibration constants for vowel
  resonance weighting.
- `simple_text_to_phonemes(text: str) -> List[str]` — the fallback
  word-level decomposition function at `csr_bridge.py:165`.
- A new `arpabet_to_10d_vector(phonemes: List[str]) -> np.ndarray`
  helper that produces the 10D resonance vector. In the hard-probes
  benchmark this logic is inline in `test_ontology_alignment`; in
  the port it is extracted into a named function for reuse.

The public surface is a single function:

```python
# csr_phoneme.py

def build_phonemic_table(
    tokenizer,
    vocab_size: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Precompute a [vocab_size, 10] phonemic table and validity mask.

    For each token id in [0, vocab_size), decode to text, run the
    ARPABET decomposition, and produce a 10D resonance vector.
    Tokens with no valid decomposition get a zero row and mask[i]=False.

    Returns:
        table:  [vocab_size, 10] float32 tensor
        mask:   [vocab_size]     bool tensor
    """
```

The function is called exactly once per model instance, at
`PrimitiveAuxiliaryLosses.__init__` time. It is not called during
training forward/backward passes. **Python-loop cost is acceptable
here** because it runs once at startup, not per step.

Fallback semantics: if any internal step raises (missing `cmudict`,
tokenizer decode failure, ARPABET lookup failure for a byte that
happens to occur in the vocab), the function catches the exception
per-token, emits a single summary warning at the end ("N tokens out
of V had invalid decompositions — phonemic grounding will skip
them"), and returns the table with zeros in the affected rows and
`False` in the mask.

**Estimated size:** ~100 lines, most of which is the ARPABET dict
literal copied from the hard-probes source.

#### File 2: `symbolu_training/training/conscious_generation/losses/primitive_auxiliary.py`

Three changes to `PrimitiveAuxiliaryLosses`: add constructor
parameters, register the phonemic table as a buffer, and extend the
`forward()` method with the masked-MSE term.

**Change 2a — constructor parameters:**

```python
# primitive_auxiliary.py — PrimitiveAuxiliaryLosses.__init__ (line ~50)

def __init__(
    self,
    loss_type: str = "infonce",
    margin: float = 0.1,
    temperature: float = 0.1,
    primitive_indices: Optional[Dict[str, int]] = None,
    # NEW — §3B phonemic grounding
    tokenizer: Optional[object] = None,
    vocab_size: Optional[int] = None,
    lambda_csr_phonemic: float = 0.0,
):
    super().__init__()
    ...  # existing init

    # Phonemic grounding table (§3B)
    self.lambda_csr_phonemic = lambda_csr_phonemic
    if lambda_csr_phonemic > 0 and tokenizer is not None and vocab_size is not None:
        try:
            from symbolu_training.training.conscious_generation.providers.csr_phoneme import (
                build_phonemic_table,
            )
            table, mask = build_phonemic_table(tokenizer, vocab_size)
            self.register_buffer('phonemic_table', table)  # [V, 10]
            self.register_buffer('phonemic_valid', mask)   # [V]
        except Exception as e:
            import warnings
            warnings.warn(
                f"Failed to build phonemic table: {e}. "
                f"Disabling lambda_csr_phonemic for this run."
            )
            self.lambda_csr_phonemic = 0.0
```

The buffers (not parameters) ensure the phonemic table is moved to
the correct device with the model, serialized into checkpoints, and
excluded from the optimizer's parameter list. `register_buffer` is
the standard PyTorch mechanism for this.

**Change 2b — `forward()` extension:**

Inside the existing `PrimitiveAuxiliaryLosses.forward()` method
(`primitive_auxiliary.py:63`), after the existing InfoNCE losses
are computed and stored in the result dict, add the phonemic
regression term:

```python
# primitive_auxiliary.py — forward() method, after existing loss computation

if self.lambda_csr_phonemic > 0 and hasattr(self, 'phonemic_table'):
    # Fetch phonemic vectors for target and candidate tokens
    # target_ids: [...], candidate_ids: [..., K]
    _phon_target = self.phonemic_table[target_ids]                  # [..., 10]
    _phon_cand   = self.phonemic_table[candidate_ids]               # [..., K, 10]
    _valid_target = self.phonemic_valid[target_ids]                 # [...]
    _valid_cand   = self.phonemic_valid[candidate_ids]              # [..., K]

    # Cosine similarity between target and each candidate, per-position
    _phon_target_exp = _phon_target.unsqueeze(-2)                   # [..., 1, 10]
    _cos_sim = F.cosine_similarity(
        _phon_target_exp, _phon_cand, dim=-1,
    )                                                                # [..., K]

    # Masked regression: only contribute where BOTH sides are valid
    _valid_pair = _valid_target.unsqueeze(-1) & _valid_cand         # [..., K]
    _csr_col = T[..., self.primitive_indices['csr']]                # [..., K]
    _sq_err = (_csr_col - _cos_sim) ** 2                            # [..., K]
    _masked_sum = (_sq_err * _valid_pair.float()).sum()
    _mask_count = _valid_pair.float().sum().clamp(min=1.0)

    result['L_csr_phonemic'] = _masked_sum / _mask_count
```

The result dict now has both `L_csr` (the existing InfoNCE term)
and `L_csr_phonemic` (the new masked regression term). The caller
in `train.py` consumes both independently with separate weights.

**Estimated size:** ~50 lines added.

#### File 3: `symbolu_training/training/unified/config.py`

One new field, placed alongside the existing CG lambda block at
`config.py:~1042` (where `lambda_csr_token` lives):

```python
lambda_csr_phonemic: float = 0.0   # §3B — masked phonemic regression on L_csr
```

**Estimated size:** ~1 line.

#### File 4: `symbolu_training/training/unified/model_factory.py`

Thread `tokenizer`, `vocab_size`, and `lambda_csr_phonemic` into
the existing `PrimitiveAuxiliaryLosses` construction site. The
tokenizer is already available in `model_factory.py` because it is
loaded alongside the Mistral backbone for the CG path.

```python
# model_factory.py — where PrimitiveAuxiliaryLosses is currently constructed

model.conscious_gen['primitive_aux_losses'] = PrimitiveAuxiliaryLosses(
    loss_type="infonce",
    temperature=0.1,
    # NEW — §3B
    tokenizer=tokenizer,
    vocab_size=tokenizer.vocab_size,
    lambda_csr_phonemic=config.lambda_csr_phonemic,
)
```

The exact construction site should be located by searching for
`PrimitiveAuxiliaryLosses(` in `model_factory.py`. There should be
exactly one occurrence.

**Estimated size:** ~5 lines modified (3 new kwargs added to
existing constructor call).

#### File 5: `symbolu_training/training/unified/train.py`

Two changes. One argparse flag, one loss-block addition.

**Change 5a — argparse flag:**

```python
# train.py — near the existing lambda_csr_token flag at ~:10297

parser.add_argument("--lambda_csr_phonemic", type=float, default=0.0,
    help="Weight for masked phonemic MSE term on the CSR column of T. "
         "Augments L_csr with ARPABET-derived phonemic grounding. "
         "0.0 disables. Recommended: 0.005 (matches existing token-level "
         "auxiliary envelope). See §3B of HARD_PROBES_FEATURE_PORT_DESIGN.md.")
```

Thread into the `UnifiedConfig` constructor at `train.py:11189+`
alongside `lambda_csr_token=args.lambda_csr_token`.

**Change 5b — loss-block addition:**

Inside the existing CG loss block, at the site where
`primitive_aux_losses` is called (around `train.py:5218`), the
existing code already loops over primitive lambdas. The new
`L_csr_phonemic` key must be consumed with its own weight —
separate from the existing `_cg_prim_lambdas` dict because it uses
a different config field:

```python
# train.py — after the existing _cg_prim_lambdas loop

# §3B — phonemic grounding term
if config.lambda_csr_phonemic > 0 and 'L_csr_phonemic' in _cg_pa_result:
    _phon_loss = _cg_pa_result['L_csr_phonemic']
    if torch.isfinite(_phon_loss):
        loss = loss + config.lambda_csr_phonemic * _phon_loss
        metrics['cg_L_csr_phonemic'] = _phon_loss.item()
```

The guard structure matches every other CG auxiliary — key
presence check, finite check, additive contribution. No new
defensive patterns are introduced.

**Estimated size:** ~15 lines added.

#### Patch-size budget

| File | Lines added / modified |
|------|-----------------------|
| `csr_phoneme.py` (new) | ~100 (mostly ARPABET dict literal) |
| `primitive_auxiliary.py` | ~50 |
| `config.py` | ~1 |
| `model_factory.py` | ~5 |
| `train.py` | ~15 |
| **Total** | **~170 lines** |

Larger than §3A's ~76 lines because of the new provider file, but
the footprint inside existing files is smaller (§3A adds ~40 lines
to `train.py` alone; §3B adds ~15). The new file is self-contained
and has zero runtime cost on non-§3B runs (it is not imported unless
`lambda_csr_phonemic > 0`).

---

### 3B.4 Configuration Interface

§3B introduces **one** new flag. Unlike §3A, which ships with a
recommended default configuration for production CG runs, §3B ships
with the feature **off by default even after merge**, because §3B is
P3 and no measurement currently justifies enabling it.

#### 3B.4.1 Flag reference

| Flag | Type | Default | Valid range | Meaning |
|------|------|---------|-------------|---------|
| `--lambda_csr_phonemic` | float | `0.0` | `[0.0, 0.1]` | Weight for the masked phonemic MSE term on column 3 of the Token Evaluation Tensor. `0.0` disables the feature entirely (no provider import, no buffer allocation, no compute cost). Recommended experimental starting point: `0.005` — matches the envelope of the existing token-level CG auxiliaries (`lambda_csr_token=0.005`, `lambda_vritti_token=0.005`). |

That is the complete new flag surface for §3B. The underlying
tuning knobs (VICReg analogs, temperature, decomposition fallback
behavior) are **not** exposed as flags — they are fixed inside the
ported `csr_phoneme.py` provider with values that match the
hard-probes source, so behavior is reproducible by reference.

**Why no `--csr_phonemic_*` sub-flags.** §3A ships five tunable
sub-flags because LSTB introduces a new trainable module whose
capacity and loss composition matter at training time. §3B does
not — the phonemic table is a fixed lookup, the regression target
is a fixed cosine similarity, and there is nothing meaningful to
tune besides the scalar weight. Adding sub-flags would invite
bike-shedding on values that cannot be measured independently of
the master weight.

#### 3B.4.2 Recommended configurations

Two named configurations. **There is no v1 production
configuration** for §3B — unlike §3A, which has a Configuration B
recommended for default shipping, §3B stays off by default even
after merge.

**Configuration A — `off` (default, and also the shipping default).**

```bash
--lambda_csr_phonemic 0.0
```

Every production CG run uses this, including runs with §3A LSTB
enabled. §3B adds nothing unless an operator explicitly turns it on
with evidence that it is needed.

**Configuration B — `experimental` (for operators investigating CSR
interpretability).**

```bash
--lambda_csr_phonemic 0.005
```

Use this when running the phonemic correlation probe from §3B.6,
or when investigating why the hard-probes
`test_csr_bridge` benchmark reports a phonemic correlation failure
on a trained CG model, or when prototyping a future feature that
depends on column 3 of `T` carrying phonemic information.

Rationale for `0.005`: peers with the existing token-level
auxiliaries (`lambda_csr_token=0.005`, `lambda_vritti_token=0.005`,
etc. at `train_mistral_cg.sh:60–66`). The phonemic regression term
is a quality upgrade on an auxiliary loss, not a primary training
signal, so the weight sits at the same magnitude as the loss it
augments. A weight noticeably higher than `lambda_csr_token` would
invert the signal hierarchy — phonemic alignment dominating the
ranking objective is not what §3B is trying to produce.

**No stress-test configuration.** §3A has a Configuration C for
plateau investigation. §3B does not, because §3B does not have a
plateau mode — it is either helping the phonemic correlation
probe in §3B.6 or it is not, and cranking the weight higher does
not add dimensionality to the question.

#### 3B.4.3 Integration with `scripts/train_mistral_cg.sh`

**Do not add `--lambda_csr_phonemic` to the shell script by
default.** This is the single most important contract in §3B.4.

The shell script represents the "known-good production
configuration" for mistral_cg. §3B is P3 and has not been shown to
improve any measured property of production training runs. Adding
it to the default script would (a) invite every operator running
the script to spend cognitive budget on a flag they do not need,
(b) trigger the phonemic table construction at every model
initialization (~1.28 MB buffer + tokenizer iteration), and (c)
implicitly commit the project to maintaining the phonemic
infrastructure at production-grade quality even though no
production use case requires it.

The correct usage for an operator who wants to experiment with
phonemic grounding is:

```bash
./scripts/train_mistral_cg.sh \
    --dataset wikitext2 \
    --max-steps 1000 \
    --lambda_csr_phonemic 0.005
```

The shell script's argument pass-through already handles unknown
flags by forwarding them to the Python invocation (see the
`$EXTRA_ARGS` handling at `train_mistral_cg.sh:~160`). No script
edit is needed for §3B to be usable — which is exactly the point.
§3B is available without being default.

If, in a future rollout, §3B.6 measurements justify enabling it by
default, that is a **separate design revision** that re-evaluates
this subsection. This document does not pre-authorize that
revision.

#### 3B.4.4 Interaction with P0-1 and §3A

**Disjoint tensor paths. No interaction expected.** Stated
precisely:

- **P0-1** operates on `outputs['state']` — the pooled 32D
  Sovereign State. Uses unary VICReg for anti-collapse.
- **§3A** operates on `outputs['state_trajectory']` — the per-token
  32D Sovereign State trajectory. Uses binary VICReg inside
  `JEPAPredictionLoss` for temporal prediction.
- **§3B** operates on `T[..., 3]` — column 3 of the Token Evaluation
  Tensor. Uses masked MSE against a cosine similarity target
  derived from a fixed phonemic lookup table.

These are three disjoint tensors produced by three different
components of the forward pass. P0-1 and §3A both pull on the
`SovereignStateProjector`; §3B pulls on the scorer that produces
`T` (whatever module that is in the current CG architecture —
`integrated_scorer` per `train.py:4985`). The scorer and the state
projector are different modules, so §3B's gradients reach neither
P0-1's nor §3A's optimization target.

**Operational consequence:** enabling `--lambda_csr_phonemic` does
not invalidate any §3A or P0-1 success criteria. If §3A has been
measured successful with Configuration B and an operator later
enables §3B experimentally, there is **no need to re-run §3A's
§3A.6 gates** — the tensors §3A depends on are unchanged.

**Small print.** If in some future architecture revision the CSR
scorer and the state projector come to share a subnetwork (e.g.,
the projector's output is fed into the scorer), this contract
breaks and §3B.4.4 must be revised. The current architecture at
design time (2026-04) does not have this coupling — `T` is
produced from `adapted_hidden` and candidate embeddings, not from
the Sovereign State.

#### 3B.4.5 Warnings and forbidden configurations

Two warnings and one forbidden configuration.

**Warning 1 — Phonemic grounding without the base InfoNCE.**

```bash
--lambda_csr_token 0.0 --lambda_csr_phonemic 0.005
```

This configuration is not forbidden but is unusual: it trains
column 3 of `T` via phonemic regression only, with no contrastive
ranking signal. Column 3 will converge to something that
approximates phonemic similarity but has no reason to rank correct
tokens above incorrect ones on the actual LM objective. Emit a
startup warning naming the combination: *"lambda_csr_phonemic > 0
without lambda_csr_token > 0: phonemic regression will train the
CSR column without a ranking objective. This is a research
configuration; ensure it is intentional."*

**Warning 2 — Phonemic grounding without a tokenizer.**

If `PrimitiveAuxiliaryLosses` is constructed without a `tokenizer`
reference but `lambda_csr_phonemic > 0` is set, the constructor's
fallback logic (§3B.3 File 2 Change 2a) catches the case, warns
once, and sets `self.lambda_csr_phonemic = 0.0` for the run. This
is a warning, not a forbidden configuration, because operators
running non-Mistral CG paths may legitimately lack a tokenizer
reference at that call site and should see training continue with
phonemic grounding silently disabled rather than crashed.

**Forbidden — Phonemic grounding without CG enabled.**

```bash
--lambda_csr_phonemic 0.005   # without --enable_conscious_generation
```

Produces a startup error. `PrimitiveAuxiliaryLosses` is only
instantiated on the CG path, so `lambda_csr_phonemic > 0` on a
non-CG run has nowhere to attach. The check lives in the same
validation block as §3A's forbidden configurations
(§3A.4.5, `train.py:~11189`).

---

### 3B.5 Risks and Mitigations

§3B has fewer risks than §3A because it is a smaller feature: no
trainable module, no new forward-pass contract, no interaction
with the 32D state projector (§3B.4.4). The risks that remain are
concentrated in two areas — **fidelity of the phonemic table** and
**numeric alignment between scorer output and cosine target**.

Seven named risks, grouped by the same four-category schema as
§3A.5 for structural symmetry. Likelihood and severity are relative
to a run with Configuration B from §3B.4.2 (`lambda_csr_phonemic =
0.005`).

#### 3B.5.1 Risk register

**Category A — Correctness risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R1 | **Phonemic table contains wrong values.** ARPABET decomposition silently fails on some token class (e.g., contractions, hyphenated words), and the resulting 10D vector is a misleading approximation instead of a zero row. Feature trains column 3 to approximate garbage for that token class. | Medium (language-specific edge cases are hard to unit-test exhaustively) | Medium — silent quality degradation on the affected subset | Unit test in `symbolu_training/training/conscious_generation/providers/tests/test_csr_phoneme.py` covering a curated list of 50+ tokens (common words, contractions, punctuation, sub-word fragments, rare bytes) with expected outputs or expected mask-false. Any regression in decomposition logic shows up as a test failure | `cg_L_csr_phonemic` does not decrease monotonically; or a spot-check of the phonemic table's valid rows shows unexpected similarity between dissimilar words |
| R2 | **Mask polarity inverted.** `_valid_pair = _valid_target.unsqueeze(-1) & _valid_cand` is written incorrectly as `| ~` or similar, masking out valid pairs. Feature silently degrades into a no-op that still emits `cg_L_csr_phonemic` metrics at plausible-looking values. | Low (one-line bug, easy to spot in review) | Medium — silent no-op, waste of the feature | Unit test that builds a table with one invalid token, computes the masked MSE on a batch that includes that token, and asserts the masked sum divides by the exact count of valid pairs | `cg_L_csr_phonemic` is numerically stuck at `0` or at the initial MSE with no gradient flow |
| R3 | **Cosine similarity dim confusion.** `F.cosine_similarity(_phon_target_exp, _phon_cand, dim=-1)` uses the wrong dim, producing the wrong reduction. The resulting `_cos_sim` has shape `[..., 10]` instead of `[..., K]`, and the subsequent MSE silently broadcasts against `T[..., 3]` without an error. | Low | Medium | Runtime shape assertion immediately after the cosine similarity call: `assert _cos_sim.shape == _csr_col.shape` | Assertion failure at step 0; or, if the assertion is missed, `cg_L_csr_phonemic` is implausibly large and does not change across training steps |

**Category B — Signal quality risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R4 | **Low phonemic coverage on the Mistral vocabulary.** BPE fragmentation means many tokens are sub-word pieces for which ARPABET decomposition is undefined. If <10% of tokens in the vocabulary have `mask=True`, the phonemic signal trains column 3 on a sparse subset of the distribution that may not reflect real training usage. | High (unknown until measured) | Medium — feature works on the valid subset but is effectively off in aggregate | Log the valid-fraction at startup: `print(f"Phonemic table valid rows: {mask.sum()}/{V} ({100*mask.float().mean():.1f}%)")`. A valid fraction below 10% is a red flag and should trigger investigation before running long experiments | Startup log shows valid fraction below 10%; or the per-step `cg_L_csr_phonemic_valid_count` metric (emitted per batch) shows that most batches have <10 valid pairs |
| R5 | **ARPABET similarity does not match the CG doctrine's notion of "phonemic resonance."** `ARPABET_TO_VARNA` in the hard-probes source is a handcrafted mapping that encodes one interpretation of Sanskrit Varna classes; the doctrine at `state_projector.py:13` refers to "phonemic/resonance" without specifying an operational definition. The cosine similarity target may train column 3 toward a notion of phonemic similarity that is not what the architecture was designed to represent. | Medium | Medium — feature trains something, but the something may not be the right thing | This is a **design-time unresolved question**, not a runtime risk. The hard-probes mapping is the only concrete operationalization currently in the codebase, so it is what §3B ports. If a better operationalization emerges (linguistic corpus study, learned phonemic embedding, etc.), §3B's provider is the right place to swap it in | §3B.6 correlation probe fails to show a measurable improvement; or the hard-probes `test_csr_bridge` benchmark continues to report low phonemic correlation on §3B-enabled runs |

**Category C — Interaction risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R6 | **Phonemic regression pulls column 3 away from the InfoNCE ranking objective.** If `lambda_csr_phonemic` is too high, the MSE target dominates the cross-entropy ranking target, column 3 becomes a phonemic similarity scalar instead of a ranking scalar, and the existing `L_csr` InfoNCE loss regresses measurably. | Medium (directly controlled by the weight) | Medium — observable `cg_L_csr` (InfoNCE) regression | §3B.4.2 experimental weight of `0.005` is chosen to peer with the existing `lambda_csr_token` envelope, not to dominate it. §3B.6 success criterion requires that `cg_L_csr` (the existing InfoNCE term) not regress by more than 5% | `cg_L_csr` (InfoNCE) regresses by > 5% from the disabled-§3B baseline after 1000 steps |
| R7 | **Numeric range mismatch between scorer output and cosine target.** Column 3 of `T` is produced by a bilinear scorer whose output range is not bounded to `[-1, 1]`. The cosine similarity target is bounded to `[-1, 1]`. The MSE is dominated by the scale mismatch rather than by any meaningful alignment, and the feature trains column 3 to be small rather than to be phonemically aligned. | Medium (depends on the scorer's output distribution, which we have not measured) | Medium — silent quality degradation | **Runtime diagnostic**: log `T[..., 3].mean()`, `T[..., 3].std()`, `T[..., 3].min()`, `T[..., 3].max()` at the first step when `lambda_csr_phonemic > 0`. If the scorer's column 3 range is significantly outside `[-1, 1]`, insert a `torch.tanh` normalization before the MSE (trivial one-line change). This is a measurement question that should be answered before running the full experiment | `T[..., 3]` statistics at step 0 show the scorer's column 3 range is incompatible with the cosine target; or `cg_L_csr_phonemic` is dominated by a constant offset rather than by alignment |

**Category D — Operational risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R8 | **Missing `cmudict` or ARPABET dependency.** The phoneme provider depends on a phonetic dictionary (typically `cmudict` via NLTK). If the dependency is not installed in the training environment, `build_phonemic_table` raises at construction time, the fallback at §3B.3 File 2 Change 2a catches the exception, warns once, and silently disables the feature. An operator who set `lambda_csr_phonemic=0.005` expecting to run the experiment sees no phonemic training and no obvious error. | Medium | Low — explicit warning is emitted, but operators who miss log lines will not notice | The fallback warning message must be explicit: **"PHONEMIC GROUNDING DISABLED — failed to build phonemic table: {exception}. Install cmudict/nltk data to enable."** The warning should appear as a clearly-labeled line at startup, not buried in info-level logs | Startup log contains the "PHONEMIC GROUNDING DISABLED" warning; `cg_L_csr_phonemic` metric is absent from the per-step log entirely |

#### 3B.5.2 Risk categories explicitly not covered

Stated for symmetry with §3A.5.2, so future readers can cite this
section rather than re-raising the concerns:

- **Compute cost.** The phonemic table lookup is `O(B × K)` index
  operations plus one cosine similarity and one masked MSE, all on
  tensors whose largest dimension is `K ≤ 32` (shortlist size).
  Memory for the buffers is ~1.3 MB for Mistral. Not a risk.
- **Multi-GPU / DDP.** The phonemic table and validity mask are
  registered as `nn.Module` buffers and inherit DDP synchronization
  automatically. No explicit handling needed.
- **Dataset interaction.** §3B reads only token ids and does not
  touch the data pipeline. No risk surface.
- **§3A interaction.** Already covered in §3B.4.4 — disjoint
  tensor paths, no measurable interaction. Not re-enumerated here.
- **Checkpoint resume.** The phonemic table and validity mask are
  buffers, not parameters, and are serialized alongside the rest
  of the `PrimitiveAuxiliaryLosses` state dict. Resume correctness
  is inherited from the existing CG checkpointing path. No separate
  gate needed (unlike §3A R10 which is a genuine risk because
  LSTB's predictor is a trainable module with its own parameters).

#### 3B.5.3 Pre-flight mitigation checklist

Smaller than §3A.5.3 because §3B has fewer dependencies. Before
running any `--lambda_csr_phonemic > 0` experiment, verify:

1. **§3A (LSTB) has been measured and shipped.** §3B is P3 and
   gated on §3A's measurements (§3.0, §3B.4.3). Do not run §3B
   experiments on a build where §3A's Phase 6 gate evaluation has
   not been completed — the concurrent changes make attribution
   impossible.
2. **`cmudict` / ARPABET dependency is installed.** Run the
   phoneme provider's startup path in isolation
   (`python -c "from symbolu_training.training.conscious_generation.providers.csr_phoneme import build_phonemic_table; ..."`)
   and confirm no warning is emitted.
3. **Phonemic coverage fraction is measured.** Run the provider on
   the Mistral tokenizer and record the valid fraction. If it is
   below 10%, stop and investigate (R4) — the feature cannot
   produce meaningful signal on a near-empty subset.
4. **Scorer column 3 range is measured.** Run 10 steps of the
   baseline (no phonemic grounding) and log `T[..., 3]` statistics.
   If the range is significantly outside `[-1, 1]`, either apply a
   `torch.tanh` normalization inside the MSE computation or adjust
   the target range (R7) before running the full experiment.

All four checks should pass before the operator proceeds to §3B.6
success criteria and §3B.7 rollout.

---

### 3B.6 Success Criteria

§3B's success criteria are structured identically to §3A.6 (named
run, named baseline, numbered gates, decision path) but are
shorter and have a **different verdict space**. §3A.6 asks "should
we ship by default?"; §3B.6 asks "has the feature demonstrated its
claimed value on a named probe?" — because §3B ships off-by-default
even after merge (§3B.4.3), the decision path does not include a
"flip the default" branch.

#### 3B.6.1 Named evaluation run

```bash
./scripts/train_mistral_cg.sh \
    --dataset wikitext2 \
    --max-steps 1000 \
    --lambda_sovereign_anticollapse 0.02 \
    --anticollapse_warmup_steps 1000 \
    --lambda_lstb 0.05 \
    --lstb_k_steps 1 \
    --lambda_csr_phonemic 0.005 \
    --checkpoint-dir checkpoints_csr_phon_v1
```

The P0-1 and §3A flags are included because §3B is measured on
top of a fully-shipped P0-1 + §3A stack (§3B.5.3 pre-flight
check 1). The baseline and evaluation runs must have identical
P0-1 and §3A configurations — the only variable is
`--lambda_csr_phonemic`.

**Hardware / runtime / dataset:** same as §3A.6.1 (single GPU
≥24GB, 4-bit Mistral, ≈30–60 min on A100).

#### 3B.6.2 Named baseline

```bash
./scripts/train_mistral_cg.sh \
    --dataset wikitext2 \
    --max-steps 1000 \
    --lambda_sovereign_anticollapse 0.02 \
    --anticollapse_warmup_steps 1000 \
    --lambda_lstb 0.05 \
    --lstb_k_steps 1 \
    --lambda_csr_phonemic 0.0 \
    --checkpoint-dir checkpoints_csr_phon_baseline
```

Same seed, same data, same schedule. Run first, persist the
per-step metric log, then run the evaluation.

#### 3B.6.3 The phonemic correlation probe

§3B introduces one new measurement that does not exist in the
current training loop: a **phonemic correlation probe** that runs
at the end of training and computes a scalar statistic for the
gates below.

**Probe procedure:**

1. Take a fixed, held-out eval batch of `N = 512` token sequences
   from the WikiText-2 validation split.
2. Run the trained model in eval mode and extract the Token
   Evaluation Tensor `T` for each position, specifically column
   3 (CSR).
3. For each (position, candidate) pair in the batch, also compute
   the cosine similarity of the candidate against the target token
   using the model's own `phonemic_table` buffer. This produces a
   per-pair reference similarity `r`.
4. Compute the **Pearson correlation** between `T[..., 3]` and `r`
   across all valid pairs in the batch (pairs where the phonemic
   validity mask is `True` on both sides).
5. Emit the scalar `cg_csr_phonemic_correlation` as the probe
   output.

**On the baseline run** (`lambda_csr_phonemic=0.0`) the probe is
computed on a model where column 3 has been trained only by
InfoNCE. There is no training signal pulling column 3 toward
phonemic similarity, so the expected correlation is close to zero
(but may be non-zero by accident).

**On the evaluation run** (`lambda_csr_phonemic=0.005`) the probe
is computed on a model where column 3 has been trained against the
cosine similarity target. A meaningful improvement in correlation
is the primary success signal.

**Implementation note.** The probe is small enough to include
inline in `train.py` at the end of the training run (triggered by
end-of-training hook or final eval pass). It does **not** need to
be a standalone script, because reproducing the measurement from
saved checkpoints is straightforward if needed later.

#### 3B.6.4 Primary gates

Five gates. The feature is considered to have **demonstrated its
claimed value** if all five pass. Gates are evaluated as deltas
against the §3B.6.2 baseline unless stated otherwise.

**Gate 1 — LM loss is not degraded.**

> **Pass condition:** `lm_loss` at step 1000 on the evaluation run
> is within ±1% of the baseline.

Same as §3A.6.3 Gate 1. Identical rationale — §3B is an auxiliary
signal on an auxiliary loss; it cannot be shown to demonstrate
value if the LM floor regresses.

**Gate 2 — The phonemic correlation probe improves measurably.**

> **Pass condition:** `cg_csr_phonemic_correlation` on the
> evaluation run is both (a) **≥ 0.3** in absolute terms, and
> (b) **≥ baseline correlation + 0.2**.

This is the central gate. Clause (a) ensures the correlation is
high enough to be useful (a Pearson r below ~0.3 is typically
interpreted as a weak relationship at best). Clause (b) ensures
the improvement is attributable to §3B and not to whatever
accidental correlation the baseline already had — this protects
against the case where the scorer's column 3 happens to correlate
with phonemic similarity by chance because of shared upstream
features.

Both clauses must hold. If only (a) holds, §3B did not actually
move the needle — the baseline was already phonemically aligned.
If only (b) holds, §3B moved the needle but to a level that is
still too weak to be useful.

**Gate 3 — The existing InfoNCE term does not regress.**

> **Pass condition:** `cg_L_csr` (the existing InfoNCE loss) at
> step 1000 on the evaluation run is within `[-∞, +5%]` of the
> baseline value.

Addresses R6 (phonemic regression pulls column 3 away from the
InfoNCE ranking objective). Asymmetric tolerance: improvements
are welcome (and plausible if phonemic grounding happens to
provide useful inductive bias for ranking), regressions above 5%
are rejected.

**Gate 4 — Phonemic MSE decreases monotonically.**

> **Pass condition:** `cg_L_csr_phonemic` at step 1000 is at most
> 50% of its value at step 100.

The internal-consistency check: if the feature is turned on and
producing real gradients, the MSE it is computing against its own
target should decrease. Monotonicity is not strictly required
(small fluctuations are normal), but the factor-of-two reduction
between step 100 and step 1000 is a sanity floor. Failure here
means either the gradients are not flowing, the target is
numerically broken (R7), or the valid-pair count is too sparse
to accumulate signal (R4).

**Gate 5 — No silent non-finite losses.**

> **Pass condition:** `cg_L_csr_phonemic` is finite at every step,
> and `cg_L_csr_phonemic_nonfinite_count` (if emitted by the
> defensive guard) is zero.

Same posture as §3A.6 Gate 5. A single non-finite step is a hard
stop: diagnose the root cause before shipping.

#### 3B.6.5 Required diagnostic metrics

Six metrics that must be emitted on every logging step regardless
of gate outcome:

- `cg_L_csr_phonemic` — the masked MSE value.
- `cg_L_csr_phonemic_valid_count` — number of valid (target,
  candidate) pairs in the batch that contributed to the loss.
  Zero or near-zero indicates R4 (low coverage).
- `cg_L_csr_phonemic_mean_sim` — mean of the cosine similarity
  target over valid pairs, diagnostic for whether the target
  itself has dynamic range.
- `cg_L_csr` — the existing InfoNCE loss, for Gate 3 comparison.
- `cg_csr_col3_mean` / `cg_csr_col3_std` — running statistics of
  the scorer's column 3 output, diagnostic for R7 (numeric range
  mismatch).
- `cg_csr_phonemic_correlation` — emitted once, at end of training,
  as the primary Gate 2 measurement.

#### 3B.6.6 Decision table

Because §3B ships off-by-default and the verdict space is
narrower than §3A's, the failure-mode decision collapses from a
tree into a simple table:

| Gates passing | Verdict |
|---------------|---------|
| **All five pass** | §3B has demonstrated its claimed value. Document the result in a finding note. **Do not** change the default in `train_mistral_cg.sh` — the P3 posture is preserved (§3B.4.3), but operators who want phonemic grounding can now cite the measurement when enabling it. |
| **Gate 1 fails** (LM loss regressed) | Investigate R6 with lower `lambda_csr_phonemic`. If 0.002 still fails Gate 1, §3B cannot be non-regressive at any meaningful weight on this workload. Mark as "unshippable on mistral_cg v1" in the finding note. |
| **Gate 2 fails**, clause (a) — correlation < 0.3 | The feature is training something but the something is not strong phonemic alignment. Investigate R4 (low coverage) or R5 (wrong operationalization). File the finding; §3B remains off-by-default with no further action required. |
| **Gate 2 fails**, clause (b) — correlation did not improve over baseline by 0.2 | The InfoNCE baseline was already phonemically aligned by accident, or §3B's gradients are not reaching column 3. Investigate R2 (mask polarity) and R7 (scale mismatch). Re-run with the diagnostic fix; if still fails, file finding. |
| **Gate 3 fails** (InfoNCE regressed) | Weight is too high. Re-run with `lambda_csr_phonemic=0.002`, one iteration only. If Gate 3 still fails at 0.002, the tension between the two terms is intrinsic; file finding and leave off. |
| **Gate 4 fails** (MSE does not decrease) | Investigate R4 (coverage), R7 (scale), or the startup diagnostic for the scorer's column 3 range. This is a debuggable failure, not a design failure. |
| **Gate 5 fails** (non-finite loss) | Hard stop. Same posture as §3A.6 Gate 5 — attach a debugger, do not re-run. |

**Downgrade semantics.** Note that §3B has no "ship by default"
upside even when all gates pass. The verdict on success is
"measurement recorded in finding note, §3B remains a documented
experimental option." Operators who want phonemic grounding on a
subsequent run can cite the finding. Operators who do not want it
are unaffected. This is the intended posture for a P3 feature.

---

### 3B.7 Rollout Plan

Five phases instead of §3A.7's seven. The reduction comes from
(a) §3B being gated on §3A already shipped (Phase 0 is lighter),
(b) no new trainable module to stress-test (Phase 2 is smaller),
and (c) the verdict space being narrower (Phase 6 and Phase 7 from
§3A.7 collapse into a single gate-evaluation-plus-decision phase).

Sequential execution is still required: phases must not be
skipped, reordered, or run in parallel. The sequencing discipline
from §3A.7 applies here for the same reason — §3B touches
`PrimitiveAuxiliaryLosses`, which every CG auxiliary reads from,
and a broken rollout would produce a diffuse regression across the
CG auxiliary stack.

#### 3B.7.1 Phase 0 — Prerequisites

**Inputs:** an up-to-date `main` with both P0-1 (§1) and §3A LSTB
merged and measured.

**Actions:**

1. **Verify §3A is shipped and §3A.6 was completed.** Open the
   §3A.7 rollout note and confirm that Phase 6 gate evaluation was
   performed. It does not matter for §3B whether §3A passed all
   seven gates or was downgraded — §3B only requires that §3A's
   measurements exist, so that the shared baseline for §3B.6 is
   well-defined.
2. **Verify `cmudict` / ARPABET dependencies.** Run:
   ```bash
   python -c "import nltk; from nltk.corpus import cmudict; \
              print(len(cmudict.dict()))"
   ```
   If this fails, install the dependency (`python -m nltk.downloader
   cmudict`) and retry. Do not proceed until the import succeeds in
   the same environment that will run training.
3. **Locate `PrimitiveAuxiliaryLosses` construction site in
   `model_factory.py`.** Same pattern as §3A.7.1 Action 2 — line
   numbers will drift, the rollout note is the source of truth.
4. **Confirm tokenizer is available at the construction site.**
   `model_factory.py` already loads the tokenizer for the
   `mistral_cg` path; verify by searching for `tokenizer=` or
   `AutoTokenizer` in the function that builds the CG model.

**Artifact:** a short rollout note recording the §3A rollout note
reference, the `cmudict` vocabulary size, and the exact file/line
numbers used in Phases 1–5.

**Gate:** all four actions produce expected output. No code
modified yet.

#### 3B.7.2 Phase 1 — Implementation

**Inputs:** the Phase 0 rollout note and §3B.3 (Integration Points).

**Actions:** apply the five-file patch in this order:

1. **`csr_phoneme.py`** (new) first. Self-contained, zero
   dependencies on existing CG code. Smoke-test it in isolation by
   importing it in an interactive Python session and calling
   `build_phonemic_table(tokenizer, tokenizer.vocab_size)` directly.
   Record the valid-row count — this is the first measurement of
   R4 (low phonemic coverage).
2. **`config.py`** second. One field, defaults to off, cannot
   break anything.
3. **`primitive_auxiliary.py`** third. Constructor + `forward()`
   changes. Verify by instantiating `PrimitiveAuxiliaryLosses`
   directly with a tokenizer and `lambda_csr_phonemic=0.0` and
   confirming the buffers are not registered (since the lambda is
   zero).
4. **`model_factory.py`** fourth. Thread the new kwargs into the
   construction call.
5. **`train.py`** last. Argparse flag + loss block addition.

**Artifact:** a single commit (or small commit series) on a
feature branch `csr-phonemic-v1`.

**Gate:** project builds with no import errors.
`./scripts/train_mistral_cg.sh --smoke-test` succeeds with no
`--lambda_csr_phonemic` flag set. The isolated Phase 1 Action 1
smoke test shows a **valid-row count ≥ 10% of vocab size** — if
below 10%, stop here and investigate R4 before writing tests.

#### 3B.7.3 Phase 2 — Unit tests and coverage verification

**Inputs:** the Phase 1 commit.

**Actions:**

1. **Add a unit test for the phoneme provider.** File:
   `symbolu_training/training/conscious_generation/providers/tests/test_csr_phoneme.py`.
   The test constructs a mock tokenizer with a hand-picked list of
   50 tokens (common words, contractions, punctuation, sub-word
   fragments, rare byte sequences), runs `build_phonemic_table`,
   and asserts:
   - All 50 tokens produce either a valid vector or `mask=False`.
   - Known-similar word pairs (e.g., `cat`/`bat`) have cosine
     similarity above a threshold.
   - Known-dissimilar pairs (`cat`/`xyz`) have cosine similarity
     below a threshold.
   This is the R1 regression guard.
2. **Add a unit test for mask polarity.** Construct a table with
   one invalid token, run `PrimitiveAuxiliaryLosses.forward()` on
   a batch that includes it, and assert that the masked MSE
   divides by exactly the count of valid pairs — not the total
   batch size, not zero. This is the R2 regression guard.
3. **Add a unit test for shape correctness.** Feed a known-shape
   `T` tensor and assert that `_cos_sim.shape == _csr_col.shape`
   after the cosine similarity computation. This is the R3
   regression guard.
4. **Coverage verification.** Run the provider on the actual
   Mistral tokenizer (not the mock one) and record:
   - Total vocabulary size.
   - Valid-row count.
   - Percentage of valid rows.
   - A sample of 10 tokens with valid decompositions and 10
     without, so the rollout note contains concrete examples.

**Artifact:** the three new unit tests + the coverage verification
block in the rollout note.

**Gate:** all three tests pass first-run. Coverage verification
shows ≥ 10% valid rows. Existing test suite still passes.

#### 3B.7.4 Phase 3 — Smoke test and diagnostic measurement

**Inputs:** the Phase 2 commit.

**Actions:**

1. Run `./scripts/train_mistral_cg.sh --smoke-test
   --lambda_csr_phonemic 0.005`. Confirm:
   - No crash.
   - Expected metrics appear:
     `cg_L_csr_phonemic`, `cg_L_csr_phonemic_valid_count`,
     `cg_L_csr_phonemic_mean_sim`, `cg_csr_col3_mean`,
     `cg_csr_col3_std`.
   - `cg_L_csr_phonemic_valid_count` is non-zero — if zero, R4 has
     triggered and the smoke test batches happen to contain no
     valid token pairs (very unlikely but possible).
2. **Diagnostic measurement for R7 (numeric range mismatch).**
   At step 0 of the smoke test, record `cg_csr_col3_mean`,
   `cg_csr_col3_std`, `cg_csr_col3_min`, and `cg_csr_col3_max`.
   If the range is significantly outside `[-1, 1]`, this is the
   signal that the scorer's column 3 needs a `torch.tanh`
   normalization before the MSE. If so, apply the normalization
   as a one-line fix in `primitive_auxiliary.py` and **return to
   Phase 1** — do not proceed to measurement with the raw range.

**Artifact:** a saved smoke-test log with the diagnostic values,
attached to the rollout note.

**Gate:** smoke test completes cleanly, all metrics present,
non-finite count is zero, R7 diagnostic confirms scorer range is
compatible with the cosine target (or the tanh fix has been
applied and Phase 1 re-validated).

#### 3B.7.5 Phase 4 — Measurement (baseline + evaluation paired)

**Inputs:** the Phase 3 commit.

**Actions:**

1. Run the **baseline** command from §3B.6.2 (with
   `--lambda_csr_phonemic 0.0`). Persist the full metric log to
   `metrics_csr_phon_baseline_<date>.jsonl`. Record the seven
   values needed for Gates 1, 2, 3, 4, 5 at step 1000.
2. Immediately afterward, run the **evaluation** command from
   §3B.6.1 (with `--lambda_csr_phonemic 0.005`). Same seed, same
   data, same schedule. Persist to
   `metrics_csr_phon_eval_<date>.jsonl`.
3. **Execute the phonemic correlation probe** (§3B.6.3) on both
   runs' final checkpoints. Record both baseline and evaluation
   correlation scalars in the rollout note.

Unlike §3A.7 which separates baseline and evaluation into Phases
4 and 5, §3B.7 combines them into Phase 4 because the two runs
are paired and have no intermediate decision point — there is no
"run the baseline, then decide whether the evaluation is worth
running" branch, because both runs are always needed for Gate 2.

**Artifact:** both metric logs + rollout note with recorded
baseline and evaluation values + two correlation probe scalars.

**Gate:** both runs complete cleanly. Non-finite loss count is
zero on both runs.

#### 3B.7.6 Phase 5 — Gate evaluation and decision

**Inputs:** the Phase 4 recorded values.

**Actions:**

1. Compute each of Gates 1–5 from §3B.6.4 against the recorded
   values. Write pass/fail with the raw numbers into the rollout
   note.
2. Consult the §3B.6.6 decision table to determine the verdict
   for the gate pass pattern.
3. File a **finding note** in the repository's design document
   tree (or wherever findings are tracked). The finding note
   must contain:
   - The rollout note reference.
   - The five gate outcomes with raw numbers.
   - The decision table verdict.
   - The date of the measurement and the commit hash used.
4. **Do not modify `scripts/train_mistral_cg.sh`** under any
   verdict. §3B ships off-by-default regardless of outcome
   (§3B.4.3). The code and flag are now available; the finding
   note lets future operators cite the measurement when deciding
   whether to enable the flag.
5. Merge `csr-phonemic-v1` to `main` if and only if:
   - Gates 1 and 5 both pass (the LM floor and non-finite hard
     stop — these are blockers).
   - The finding note has been filed.
   Other gate outcomes do not block the merge, because §3B is
   additive and the flag stays off. A failed Gate 2 or Gate 3 is
   a useful finding for future operators; it does not indicate
   broken code that must be kept out of `main`.

**Artifact:** completed rollout note + finding note + (if gates
1 and 5 pass) merged branch.

**Gate:** none — this is the terminal phase.

#### 3B.7.7 Post-measurement follow-ups

Unlike §3A.7.9, which lists five named follow-up experiments, §3B
has only one follow-up worth naming:

- **Alternative phonemic operationalization.** R5 from §3B.5 is a
  design-time unresolved question: ARPABET-derived cosine
  similarity may not be what the CG doctrine actually means by
  "phonemic resonance." A future follow-up could replace the
  `arpabet_to_10d_vector` helper with a learned phonemic
  embedding, a linguistic corpus similarity, or a Sanskrit-specific
  Varna mapping refinement. The provider module is the right place
  to swap this in; the rest of §3B's integration is unchanged.

All other experiments (soft-label KL divergence from §3B.2 Decision
2 Option C, per-plane phonemic grounding, multi-lingual extension)
are explicitly out of scope (§3B.8) and not tracked as follow-ups.

#### 3B.7.8 Rollback path

Trivial. §3B is entirely additive and off-by-default.

- **Unmerged rollback:** do not merge `csr-phonemic-v1`.
- **Merged rollback:** there is nothing to roll back. Operators who
  do not pass `--lambda_csr_phonemic` see no change. If a future
  issue is traced to the phoneme provider, set
  `lambda_csr_phonemic=0.0` in the affected run (which is the
  default, so no action needed) and the issue disappears.
- **Code revert** is only needed if the Phase 2 unit tests or the
  defensive guards in `forward()` turn out to produce
  side effects even when `lambda_csr_phonemic=0.0` — which should
  be impossible by design (the guards are gated on
  `self.lambda_csr_phonemic > 0`) and is the reason the
  master-switch behavior is tested in Phase 1 Action 3 and Phase 3.

---

### 3B.8 Out of Scope

Three categories matching §3A.8's structure: deferred, hard
limits, non-goals. Shorter because §3B is a smaller feature with
a narrower surface, so the potential for scope creep is smaller
to begin with.

#### 3B.8.1 Deferred — plausible follow-ups

These items have a clear measurement path but are not justified
by any evidence in hand and are deliberately **not** part of v1.

- **Soft-label KL divergence loss form.** §3B.2 Decision 2
  Option C — replace the cosine-similarity MSE with a soft
  distribution over candidates and use KL divergence between
  `softmax(T[..., 3])` and the phonemic distribution. More
  principled but requires temperature tuning; the regression MSE
  form is sufficient for v1 and is what the hard-probes
  benchmark already uses.
- **Alternative phonemic operationalization** (R5 in §3B.5). The
  single named follow-up from §3B.7.7. ARPABET cosine similarity
  is the only concrete operationalization currently in the
  codebase; if a future investigation shows it is the wrong
  answer, the fix is in the `csr_phoneme.py` provider, not in
  the rest of §3B's integration. Candidates include learned
  phonemic embeddings, linguistic-corpus-derived similarity,
  Sanskrit Varna mapping refinement, or a composite of several.
- **Per-plane phonemic grounding.** Instead of a single 10D
  resonance vector per token, produce separate phonemic signals
  for different Koshas or Varna classes and train different
  columns of `T` against each. Architecturally cleaner but
  roughly doubles the design surface; out of scope until the
  single-column version has been measured.
- **Multi-lingual phonemic extension.** ARPABET covers English
  phonemes. For a multi-lingual Mistral training run, the
  phonemic table would need IPA (International Phonetic Alphabet)
  or language-specific decomposition. Out of scope until
  §3B demonstrates value on English WikiText-2.
- **Vocabulary-level shortlist comparison.** Instead of comparing
  against the per-batch shortlist `K`, compute cosine similarity
  against the full vocabulary `V` at a sampled subset. Gives a
  denser training signal at the cost of a larger tensor
  operation. Out of scope — the per-batch shortlist is what the
  existing `L_csr` loss uses, and §3B should match its envelope
  for fair comparison.

#### 3B.8.2 Hard limits — will not be done even if asked

These items turn §3B into a different feature and are not on any
roadmap.

- **No modification to `SovereignStateProjector`, `compute_state_delta`,
  or the 32D Sovereign State.** §3B operates on the CSR column of
  `T`, which is architecturally outside the 32D state
  (`state_projector.py:13–14` — CSR is the Manomaya Plane,
  intentionally separated from the five planes of the Sovereign
  State). Modifying any of those would mean ignoring the doctrinal
  boundary that §3B's very existence is designed to respect.
- **No modification to the `PrimitiveAuxiliaryLosses` InfoNCE
  contract.** The existing `L_csr` contrastive loss stays exactly
  as it is. §3B adds an additive term and a validity-masked
  regression; it does not reinterpret, replace, or restructure
  the existing ranking loss.
- **No new trainable parameters in the phoneme provider.** The
  `[vocab_size, 10]` phonemic table is a **fixed lookup**,
  registered as a buffer (not a parameter). There is no "learned
  phonemic embedding" in v1 — that is 3B.8.1's deferred
  follow-up, and it lives in a different module. The v1 provider
  is deterministic: given the same tokenizer and the same
  `csr_phoneme.py` source, it produces bitwise-identical tables.
- **No gradient flow to the frozen Mistral backbone.** The
  phonemic table is a static buffer; the cosine similarity is a
  comparison, not a projection; the MSE gradient flows only
  through the scorer that produces column 3 of `T`. No path
  exists from §3B's loss to the backbone parameters, and none
  will be added.
- **No inference-time footprint.** The phonemic table is a
  non-trainable buffer that is loaded into memory at model
  construction time regardless of training vs inference, but
  **it is not accessed during generation** — the loss is a
  training-only operation. Inference latency, memory-after-init,
  and output shape are unchanged. (The 1.3 MB buffer is present
  in inference memory but not used; callers who care can strip
  the buffer from the state dict before deployment.)
- **No changes to the tokenizer.** §3B reads from the tokenizer
  at construction time to build the phonemic table. It does not
  modify the tokenizer, register new tokens, or alter vocabulary
  behavior. Any tokenizer upgrade or replacement is handled
  entirely outside §3B.
- **No new `model_type`.** §3B is a flag on `mistral_cg`. It
  does not introduce `mistral_cg_phonemic` or any variant.
- **No port of the hard-probes CSR bridge benchmark harness.**
  `scripts/phase_probes/hard_probes/hard_probes_lib/benchmarks/csr_bridge.py`
  stays where it is. §3B ports the **primitives** (ARPABET
  decomposition, 10D resonance vector) but not the benchmark
  runner, the ablation study, or the research metrics. Research
  tools stay in the research tree.

#### 3B.8.3 Non-goals — clarifications about what §3B is not

Preempts misreadings of the feature name.

- **§3B is not a phonemic model.** It does not understand
  phonology, articulation, or linguistic structure. It computes a
  cosine similarity between fixed 10D vectors derived from a
  handcrafted ARPABET-to-Varna mapping. Anything beyond "cosine
  similarity of handcrafted vectors" is out of scope for v1.
- **§3B is not a replacement for the existing `L_csr` InfoNCE
  loss.** It augments the existing loss with a phonemic alignment
  term. Both losses pull on column 3 of `T` simultaneously. If
  the two objectives ever appear to be in tension (a §3B.6 Gate 3
  failure mode), the resolution is to lower `lambda_csr_phonemic`,
  not to disable `lambda_csr_token`.
- **§3B is not a general-purpose token embedding.** The 10D
  phonemic vectors are only used as targets for column 3 of `T`
  and are not exposed to any other module. A future extension
  that wants to use phonemic embeddings for a different purpose
  should construct its own provider, not reuse §3B's buffer.
- **§3B is not an answer to "does CSR work?"** It is only an
  answer to "does column 3 of `T` correlate with
  ARPABET-derived cosine similarity?" The CG doctrine's claim
  that CSR handles the Manomaya plane involves much more than
  phonemic similarity (resonance vectors, Sanskrit calibration,
  symbolic entropy modulation — see the 40-line file docstring
  at `csr_bridge.py:1–50`). §3B addresses the narrowest provable
  slice of that claim. Full CSR validation is research work that
  belongs in the hard-probes benchmark harness, not in the
  production training loop.
- **§3B is not a benchmark.** The hard-probes
  `test_csr_bridge` harness is the research tool; §3B v1 is a
  training loss. They are complementary: §3B provides the
  production training signal that the hard-probes harness can
  then measure on trained checkpoints. Neither replaces the
  other.
- **§3B is not priority P1 work.** Despite being numbered as
  part of P1-1, §3B is **P3** (§3.0 recommendation). The
  numbering reflects the umbrella origin of the feature pair
  (both §3A and §3B came out of the original P1-1 "LSTB / CSR
  bridge supervision" recommendation), not their current
  priority. An operator reading this document for P1 shipping
  decisions should read §3A and skip §3B.

---

**End of §3 (P1-1: LSTB / CSR Bridge Supervision).**

---

## §4 P1-2 — Phase Write-Gate + Multi-Channel Phase Memory (`mistral_hybrid`)

### 4.1 Problem Statement

After §2 (P0-2: phase warmstart curve) is in place, the phase branch
of each `HybridTransformerBlock` in `MistralHybridWrapper` has a
training curve that ramps from near-silent to fully active during
the first ~10K steps. That fixes the *temporal* instability of the
phase branch — it does not fix the *capacity* and *selectivity*
limitations of the phase memory itself.

Two specific limitations remain:

1. **Single-channel phase memory can only specialize at one
   timescale.** The `PhaseAttentionLayer` maintains a rolling
   phase-coherent state via `parallel_ema_scan` with a learned
   per-head decay parameter. With `phase_channels=1` (the default),
   all phase heads share the same EMA-state tensor and differ only
   in their per-head decay parameters — which are initialized from
   the same distribution and converge toward similar values. The
   result is that a 4-layer hybrid stack with 32 phase heads
   effectively operates at **one dominant memory horizon** rather
   than mixing short-term and long-term phase signals.
2. **Unconditional writes corrupt long-range phase memory on noisy
   tokens.** Every token contributes to the phase state
   accumulation unconditionally — the `kv_complex` tensor is
   scanned in full via `torch.cumsum` (phase_transformer.py:2425).
   On corpora with significant noise (FineWeb, Common Crawl, any
   web-scale dataset), a large fraction of tokens are punctuation,
   whitespace, URLs, or boilerplate that carry no useful long-range
   signal. These tokens still update the phase state, pulling the
   memory toward a running average of noise rather than a signal-
   selective representation.

The hard-probes `train_hard_probes.py` pipeline solves both
limitations simultaneously with two compositional mechanisms:

- **`phase_channels > 1`** — allocates `C` independent EMA-state
  slots per head, each with its own per-channel-per-head decay
  parameter spread **logarithmically across timescales** `[2.0,
  2048.0]`. Channel 0 learns short-term memory (~2 tokens),
  channel `C-1` learns long-term memory (~2048 tokens), and the
  readout combines them via a learned `channel_agg` weight vector.
  This gives the phase stack explicit multi-horizon capacity
  without adding new attention heads.
- **`phase_write_gate`** — adds a learned per-channel-per-head
  write gate `g_t = sigmoid(W_g @ x_t)` that multiplies `kv_complex`
  before state accumulation. Tokens with low gate values are
  excluded from the phase memory update, so the memory stays
  selective even on noisy corpora. The gate is initialized with
  `bias=2.0` so `sigmoid(2) ≈ 0.88` — training starts close to
  the unmodified "all writes active" behavior and the gates
  differentiate as training proceeds.

Both mechanisms compose naturally with the phase warmstart curve
from §2. In fact, the composition order inside `PhaseAttentionLayer`
is deliberate:

```text
1. Compute kv_complex from attention (unchanged)
2. Compute write gate sigmoid(W_g @ x)           ← §4 phase_write_gate
3. Expand kv_complex to C channels               ← §4 phase_channels
4. Multiply by gate                               ← §4 phase_write_gate
5. Multiply by warmstart_alpha                   ← §2 phase_warmstart
6. Run parallel_ema_scan with per-channel decay  ← §4 phase_channels
```

Write gating is applied **before** warmstart dampening, so the
write gate's bias-toward-open initialization means early training
sees `warmstart_alpha × 0.88` rather than `warmstart_alpha × 1.0`
— a slightly gentler phase contribution in the first steps. This
is a feature, not a bug: the composition is conservative by
construction.

### 4.2 Current State in Repository

Like §2 (P0-2), this is a **wiring task**, not an implementation
task. All mechanics already exist in `symbolu/phase_transformer.py`;
they just are not exposed through `MistralHybridWrapper` or the
unified CLI.

**Already implemented in the core:**

- **`PhaseAttentionLayer` constructor** at
  `symbolu/phase_transformer.py:1964–1965` accepts both
  `phase_channels: int = 1` and `phase_write_gate: bool = False`.
- **Multi-channel state structure** is built at
  `phase_transformer.py:2051–2070`:
  - Per-channel-per-head decay via
    `channel_decay_logit` parameter of shape `[C*H]`, spread
    logarithmically over `[2.0, 2048.0]` via `torch.linspace` on
    log-scale.
  - Per-channel aggregation weights via `channel_agg` parameter
    of shape `[C]`, initialized uniform so all channels contribute
    equally at start.
- **Write gate projection** is built at
  `phase_transformer.py:2072–2080`:
  - `write_gate_proj: Linear(embed_dim → C*H)` with
    `bias=2.0` initialization.
  - Zero-weight initialization so the gate starts as a constant
    `sigmoid(2)` regardless of input, and differentiates only
    when training moves the weights off zero.
- **Forward-path integration** at `phase_transformer.py:2427–2463`:
  - Write gate applied before channel expansion.
  - Multi-channel `kv_complex` expansion via
    `unsqueeze(2).expand(B, N, C, H, D_h)`.
  - Folded to `[B, N, C*H, D_h]` for `parallel_ema_scan` — each
    channel-head pair is treated as an independent "virtual head"
    by the scan, preserving the O(n) complexity.
- **Diagnostic capture flags** at `phase_transformer.py:2082–2086`:
  - `_diag_phase_gate_mean`, `_diag_phase_gate_std` — gate
    statistics per step.
  - `_diag_phase_state_norm_per_channel` — per-channel state
    magnitudes, for detecting channel imbalance.
  - `_diag_phase_attn_mass` — per-channel attention mass.
- **`HybridTransformerBlock` constructor** at
  `phase_transformer.py:6241–6258` accepts both kwargs and forwards
  them to its inner `HybridAttentionLayer` at `:6283–6284`, which in
  turn forwards to the inner `PhaseAttentionLayer`.
- **`HybridPhaseTransformer`** (the non-Mistral hybrid path) wires
  all of this up at `phase_transformer.py:6737–6826`. It is the
  reference implementation — its usage pattern is the model for
  what `MistralHybridWrapper` should do.

**The gap:**

- **`MistralHybridWrapper` bypasses `HybridPhaseTransformer`
  entirely.** It constructs `LocalTransformerBlock` and
  `HybridTransformerBlock` directly at
  `symbolu_training/training/unified/mistral_hybrid_wrapper.py:115–138`.
  The constructor calls to `HybridTransformerBlock(...)` at line
  `128` do **not** pass `phase_channels` or `phase_write_gate`, so
  both default to the `phase_channels=1, phase_write_gate=False`
  legacy single-channel, unconditional-write behavior.
- **The unified config has zero references** to either flag.
  Verified by grep: `phase_channels` and `phase_write_gate` do
  not appear in any file under `symbolu_training/training/unified/`.
- **The unified CLI has no argparse flags** for either feature.

So the gap is: `MistralHybridWrapper` cannot enable either feature
even on the command line, because the kwargs are not threaded
through the constructor. The constructor-injection fix is a pure
plumbing task — unlike §2's P0-2 which needed a post-construction
submodule walk, P1-2's kwargs are already accepted by
`HybridTransformerBlock.__init__` at construction time.

**A note on composition with §2.** §2 (P0-2) is a **post-construction
submodule walk** that sets `.phase_warmstart_enabled = True` on
every `PhaseAttentionLayer` after the blocks are built. §4 (P1-2)
is **constructor injection** at the `HybridTransformerBlock` call
site. The two approaches do not interact: §2's walk runs after §4's
construction, and both end up setting attributes on the same
`PhaseAttentionLayer` instances without conflict. Both features can
be enabled simultaneously on the same run with no ordering concerns
in the wrapper code.

---

### 4.3 Design Approach

Three design decisions. Smaller than §3A's five and §2's (implicit)
because P1-2 is a constructor-injection task on already-complete
primitives — most of the design effort was done by whoever built
the core phase attention layer, and §4 just consumes it correctly.

#### Decision 1: Where the kwargs thread through the wrapper

Two options for how `phase_channels` and `phase_write_gate` reach
the inner `PhaseAttentionLayer`:

| Option | Approach | Verdict |
|--------|----------|---------|
| A | **Constructor kwargs on `MistralHybridWrapper.__init__`** that are passed to `HybridTransformerBlock(...)` at the block construction site | **Chosen** |
| B | Post-construction walk of `PhaseAttentionLayer` submodules (same pattern as §2 warmstart) | Rejected — the kwargs are **structural** (they allocate `write_gate_proj` and `channel_decay_logit` parameters), not runtime state. Trying to set them post-construction would require creating the parameters later, which cannot be done without restructuring the already-built block |

Option A is strictly simpler because `HybridTransformerBlock`
already accepts these kwargs at construction time. The wrapper
just needs to pass them through.

#### Decision 2: `LocalTransformerBlock` handling

The first `local_layers` blocks in `MistralHybridWrapper` are
`LocalTransformerBlock` instances (local attention only, no phase
branch). Later blocks (`i >= local_layers`) are
`HybridTransformerBlock` with both local and phase attention.
Should `phase_channels` and `phase_write_gate` be passed to
`LocalTransformerBlock` too?

**No.** `LocalTransformerBlock` has no phase attention, so
`phase_channels` and `phase_write_gate` have nowhere to attach
inside it. Passing them would either (a) error out if the
constructor doesn't accept them, or (b) silently discard them.
Neither is desirable.

**Conditional pass:** the wrapper's construction loop conditionally
passes the phase kwargs only to `HybridTransformerBlock` (the
`else` branch at `mistral_hybrid_wrapper.py:126–138`). The
`LocalTransformerBlock` branch at `:117–125` is unchanged. This
mirrors how the existing `alpha_local`, `alpha_phase`, and
`learned_decay` kwargs are already scoped — they only apply to
hybrid blocks, and the local blocks ignore them.

#### Decision 3: Default values for the new kwargs

What should `phase_channels` and `phase_write_gate` default to
inside the `MistralHybridWrapper` constructor?

- `phase_channels=1` (default). Matches the core
  `PhaseAttentionLayer` default at `phase_transformer.py:1964`, so
  the wrapper's behavior when the new kwargs are not set is
  **bit-for-bit identical** to the current behavior. No silent
  change to existing runs.
- `phase_write_gate=False` (default). Same rationale. Existing
  checkpoints that were trained without the gate can be loaded
  into a wrapper with the default, and the resulting model has
  the same parameter count and forward-pass semantics as before.

**Checkpoint compatibility note.** When `phase_channels` is set
to `> 1`, the `channel_decay_logit` parameter is allocated with
shape `[C*H]` — different from the `decay_logit` shape of `[H]`
that a single-channel model uses. This means:

- Checkpoints saved with `phase_channels=1` **cannot** be loaded
  into a model built with `phase_channels=4` via strict
  `load_state_dict()` — the shapes do not match.
- Checkpoints saved with `phase_channels=4` **cannot** be loaded
  into a model built with `phase_channels=1` for the same reason.

The wrapper does not attempt to bridge this — the `phase_channels`
value at checkpoint load time must match the value at checkpoint
save time. If operators need to change the value mid-training,
they must start a fresh run. This is documented as a §4.6 risk and
is the standard behavior for any architectural hyperparameter.

### 4.4 Integration Points

**Four files touched.** Sketches below are illustrative, not
literal patches.

#### File 1: `symbolu_training/training/unified/mistral_hybrid_wrapper.py`

Two changes. Constructor signature and construction loop.

**Change 1a — add kwargs to `__init__`:**

Place next to the existing phase-related kwargs like `alpha_phase`
and `learned_decay`:

```python
# mistral_hybrid_wrapper.py — __init__ signature (line ~55)
def __init__(
    self,
    ...,
    alpha_local: float = 0.8,
    alpha_phase: float = 0.2,
    decay_gamma: float = 0.99,
    learned_decay: bool = True,
    protected_phase: bool = True,
    phase_adapter_hidden: int = 1024,
    # V10.12 — Multi-channel phase memory + selective write gating (§4)
    phase_channels: int = 1,
    phase_write_gate: bool = False,
    ...,
):
```

**Change 1b — thread kwargs into the `HybridTransformerBlock`
construction call:**

At the existing loop at `mistral_hybrid_wrapper.py:115–138`, the
`else` branch constructs `HybridTransformerBlock`. Add the new
kwargs to that call:

```python
# mistral_hybrid_wrapper.py — inside the phase_blocks construction loop
for i in range(num_phase_layers):
    if i < local_layers:
        # Local-only branch (unchanged)
        self.phase_blocks.append(
            LocalTransformerBlock(
                phase_config,
                window_size=window_size,
                backend=local_backend,
            )
        )
    else:
        # Hybrid branch — threaded with new kwargs
        self.phase_blocks.append(
            HybridTransformerBlock(
                phase_config,
                window_size=window_size,
                local_backend=local_backend,
                alpha_local=alpha_local,
                alpha_phase=alpha_phase,
                learned_decay=learned_decay,
                protected_phase=protected_phase,
                # NEW — §4
                phase_channels=phase_channels,
                phase_write_gate=phase_write_gate,
            )
        )
```

**Diagnostic logging at construction time:** emit a startup line
when either feature is enabled, so operators see confirmation in
the log:

```python
# mistral_hybrid_wrapper.py — after the phase_blocks loop
if phase_channels > 1 or phase_write_gate:
    _n_hybrid = num_phase_layers - local_layers
    print(
        f"  Phase channels: {phase_channels} "
        f"({'multi-horizon' if phase_channels > 1 else 'single'})"
    )
    print(
        f"  Phase write gate: "
        f"{'ENABLED' if phase_write_gate else 'disabled'}"
    )
    print(
        f"  Wired across {_n_hybrid} HybridTransformerBlock(s)"
    )
```

No other changes inside the wrapper. `compute_state_delta`, Stage 8
Perspective Synthesizer, adapter gate, and the output norm are all
unchanged. This matches the §2 non-interference guarantee — P1-2
does not touch anything §2 or P0-1 depends on.

#### File 2: `symbolu_training/training/unified/config.py`

Two new config fields in the hybrid-specific block:

```python
# config.py — inside the mistral_hybrid config section
phase_channels: int = 1          # §4 — multi-channel phase memory (1=legacy)
phase_write_gate: bool = False   # §4 — selective write gate on phase memory
```

#### File 3: `symbolu_training/training/unified/model_factory.py`

Thread the two config fields into the `MistralHybridWrapper`
construction call. The construction site should be located by
searching for `MistralHybridWrapper(` in `model_factory.py`; there
should be exactly one occurrence.

```python
# model_factory.py — where MistralHybridWrapper is constructed

model = MistralHybridWrapper(
    model_name=config.mistral_model_name,
    quantize=config.mistral_quantize,
    num_phase_layers=config.num_phase_layers,
    local_layers=config.local_layers,
    ...,
    # NEW — §4
    phase_channels=config.phase_channels,
    phase_write_gate=config.phase_write_gate,
)
```

#### File 4: `symbolu_training/training/unified/train.py`

Two argparse flags, threaded into `UnifiedConfig` at the existing
CG/hybrid config construction site:

```python
# train.py — near the existing mistral_hybrid argparse block
parser.add_argument("--phase_channels", type=int, default=1,
    help="Number of independent phase memory channels in "
         "mistral_hybrid. 1 = legacy single-channel. "
         "Recommended: 4 for multi-horizon memory. "
         "See §4 of HARD_PROBES_FEATURE_PORT_DESIGN.md.")
parser.add_argument("--phase_write_gate", action="store_true",
    help="Enable selective write gating on phase memory in "
         "mistral_hybrid. Reduces noise corruption of long-range "
         "phase state. See §4 of HARD_PROBES_FEATURE_PORT_DESIGN.md.")
```

Threaded into `UnifiedConfig` alongside the §2 phase warmstart
flags:

```python
# train.py — UnifiedConfig construction
config = UnifiedConfig(
    ...,
    phase_warmstart=args.phase_warmstart,
    phase_warmstart_steps=args.phase_warmstart_steps,
    phase_warmstart_tau=args.phase_warmstart_tau,
    # NEW — §4
    phase_channels=args.phase_channels,
    phase_write_gate=args.phase_write_gate,
)
```

**This is also the natural place for the §2 wiring to live** —
both §2 and §4 flags are `mistral_hybrid`-specific, both are
constructor-time configuration, and both need to be threaded
through `model_factory.py` → `MistralHybridWrapper.__init__`.
If §2 has already shipped, the §4 additions slot in adjacent to
the existing wiring.

#### Patch-size budget

| File | Lines added / modified |
|------|-----------------------|
| `mistral_hybrid_wrapper.py` | ~15 (signature + block construction + diagnostic print) |
| `config.py` | ~2 (two new fields) |
| `model_factory.py` | ~5 (two new kwargs in the construction call) |
| `train.py` | ~10 (argparse + UnifiedConfig threading) |
| **Total** | **~32 lines** |

Smaller than §2's ~60 lines because there is no post-construction
submodule walk and no `set_global_step` method to add. This is the
smallest patch in the document.

---

### 4.5 Configuration Interface

Two new flags. Both default to off; both must be explicitly set
by the operator to enable the feature. Unlike §3A LSTB which has
a recommended default configuration for shipping, P1-2 ships
with a recommended configuration for enabling — but the feature
stays off by default in `scripts/train_hybrid_7b.py` until
measurements justify the default flip.

#### 4.5.1 Flag reference

| Flag | Type | Default | Valid range | Meaning |
|------|------|---------|-------------|---------|
| `--phase_channels` | int | `1` | `{1, 2, 4, 8}` | Number of independent phase memory channels in `mistral_hybrid`. `1` is the legacy single-channel behavior (bit-for-bit identical to non-§4 runs). `4` is the recommended multi-horizon starting point — four channels with logarithmically-spaced decay timescales covering ~2 to ~2048 tokens. Values above 8 inflate memory cost without evidence of benefit. |
| `--phase_write_gate` | action | `False` | bool | Enables the learned per-channel-per-head write gate on phase memory. When set, adds a `write_gate_proj` Linear layer to each `HybridTransformerBlock` and multiplies `kv_complex` by `sigmoid(W_g @ x)` before state accumulation. Gate initializes with `bias=2.0` (near-open) so training starts close to the unmodified write behavior. |

**Why no `--phase_channel_agg_mode` or similar sub-flags.** The
core implementation at `phase_transformer.py:2054–2070` hard-codes
the channel decay initialization (logarithmic spread over
`[2.0, 2048.0]`) and the channel aggregation (uniform-initialized
learned weights). These are exposed as parameters inside the model
and become trainable once `phase_channels > 1`. There is no
meaningful CLI knob — operators who want to tune the initialization
should edit `phase_transformer.py` directly, not expose a shell
flag.

#### 4.5.2 Recommended configurations

Three named configurations.

**Configuration A — `off` (default).**

```bash
--phase_channels 1
# --phase_write_gate not set
```

All existing `mistral_hybrid` runs. Zero code change from today.
The new argparse flags exist but are defaulted off, and
`mistral_hybrid_wrapper.py` constructs blocks with the legacy
single-channel unconditional-write behavior.

**Configuration B — `v1` (recommended for multi-horizon experiments).**

```bash
--phase_channels 4
--phase_write_gate
```

The §4.7 success criteria are measured against this configuration.
Rationale for the values:

- `phase_channels=4`: the smallest value that spans the full decay
  range meaningfully. With `linspace` on log scale over `[2.0,
  2048.0]`, four channels get timescales approximately `[2.0,
  22.6, 255.8, 2048.0]` — short/medium/long/very-long. Three
  channels would collapse short and medium; two would lose the
  medium horizon entirely.
- `phase_write_gate`: enabled unconditionally alongside
  `phase_channels=4`. The two features compose naturally and the
  hard-probes reference configuration at
  `train_hard_probes.py:9588–9602` enables them together.

**Configuration C — `channels-only` (ablation).**

```bash
--phase_channels 4
# --phase_write_gate not set
```

Use this only for attribution — to isolate the contribution of
multi-channel memory from the contribution of write gating. Not
a production configuration. If §4.7 Gate 2 fails on Configuration
B, running Configuration C and comparing against a
`--phase_write_gate`-only configuration tells the operator which
of the two mechanisms is carrying the improvement (or which is
failing).

#### 4.5.3 Integration with `train_hybrid_7b.py`

`train_hybrid_7b.py` at the repo root is the established training
script for `mistral_hybrid` / `HybridPhaseTransformer` runs. Unlike
`train_mistral_cg.sh` which is a wrapper around
`train_unified_llm.py`, `train_hybrid_7b.py` is a Python script
that directly constructs the training loop.

**For §4 v1 (after success criteria pass):** add the two flags to
`train_hybrid_7b.py`'s argparse block and pass them through to the
model construction. Do not change defaults — the script's current
behavior stays bit-for-bit identical unless the operator explicitly
sets the flags on the command line. Default flip (adding
`--phase_channels 4 --phase_write_gate` to the script's default
invocation) is a **separate decision** made after §4.7 measurements,
not as part of §4's initial implementation.

**For §4 smoke-test coverage:** unlike `train_mistral_cg.sh` which
has a `--smoke-test` mode, `train_hybrid_7b.py` does not currently
have one. §4 smoke-testing uses a short-step configuration
(`--max_steps 100`) on synthetic or small WikiText-2 data.

#### 4.5.4 Interaction with §2 (P0-2 phase warmstart)

§2 and §4 are both `mistral_hybrid`-specific and compose naturally.
Stated precisely:

- **§2** adds `--phase_warmstart`, `--phase_warmstart_steps`,
  `--phase_warmstart_tau` to the CLI. These set attributes on
  `PhaseAttentionLayer` instances post-construction.
- **§4** adds `--phase_channels`, `--phase_write_gate` to the CLI.
  These are constructor kwargs that allocate parameters at block
  construction time.

Enabling both simultaneously is the recommended production
configuration once both features have passed their respective
success criteria. The composition order inside
`PhaseAttentionLayer` is:

```text
1. Write gate applied to kv_complex        ← §4 phase_write_gate
2. Channel expansion                        ← §4 phase_channels
3. Warmstart alpha dampening                ← §2 phase_warmstart
4. EMA scan with per-channel decay          ← §4 phase_channels
```

Documented at `phase_transformer.py:2434–2463`. Operators do not
need to worry about this ordering — it is fixed inside the forward
pass and both features compose correctly regardless of the order
the CLI flags are parsed.

**Recommended combined configuration:**

```bash
python train_hybrid_7b.py \
    --phase_warmstart \
    --phase_warmstart_steps 5000 \
    --phase_warmstart_tau 1000.0 \
    --phase_channels 4 \
    --phase_write_gate
```

#### 4.5.5 Forbidden configurations

Two flag combinations produce a startup error rather than silent
misbehavior:

1. **`--phase_channels > 1` with `--model_type` ≠ `mistral_hybrid`
   and `≠ hybrid`.** The feature is hybrid-specific. Setting it on
   `mistral_cg`, `ontological`, or other non-hybrid model types has
   nowhere to attach. The `hybrid` model type (non-Mistral
   `HybridPhaseTransformer`) is permitted because it already wires
   up `phase_channels` in its own construction path at
   `phase_transformer.py:6737+`.
2. **`--phase_write_gate` without a hybrid model type.** Same
   rationale. The `write_gate_proj` parameter is only constructed
   inside `PhaseAttentionLayer`, which only exists in hybrid
   blocks.

These checks live in the argparse validation block at
`train.py:~11189` alongside the §2 and §3A validation.

### 4.6 Risks and Mitigations

Fewer risks than §3A because P1-2 is a constructor-injection task
on existing primitives. Six named risks in four categories, each
with the §3A.5-style detection signal.

#### 4.6.1 Risk register

**Category A — Correctness risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R1 | **Kwargs not passed to the correct block.** The construction loop passes `phase_channels` to `LocalTransformerBlock` by mistake, or forgets to pass it to `HybridTransformerBlock`. Silent: the feature runs without the expected capacity. | Low (simple loop, caught by review) | Medium | Explicit unit test that constructs a `MistralHybridWrapper` with `phase_channels=4` and asserts that every `HybridTransformerBlock` instance has a `PhaseAttentionLayer.channel_decay_logit` parameter of shape `[4*H]`, and that every `LocalTransformerBlock` does not | Parameter count at startup does not match the expected count for `phase_channels > 1` |
| R2 | **Checkpoint load with mismatched `phase_channels`.** Operator loads a checkpoint saved with `phase_channels=1` into a model built with `phase_channels=4`. `load_state_dict` raises a shape mismatch error on `channel_decay_logit`. | Medium (operators who experiment with different values) | Low — the error is loud, not silent | Explicit error message at checkpoint load time: *"phase_channels mismatch: checkpoint has [H]-shaped decay but model expects [C*H]-shaped decay. Either build the model with the same phase_channels value used at save time, or start a fresh training run."* The standard PyTorch error is sufficient but can be improved with an explicit pre-check | `RuntimeError: size mismatch` on `channel_decay_logit` at checkpoint load |

**Category B — Signal quality risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R3 | **Multi-channel memory collapses to single-channel behavior.** All four channel decay logits converge to the same value during training, or `channel_agg` converges to `[1, 0, 0, 0]`, effectively reducing the stack to a single channel. Feature is enabled but not producing multi-horizon behavior. | Medium (unknown until measured — depends on whether the task actually benefits from multi-horizon memory) | Medium — feature works but delivers no capacity improvement | Emit the `_diag_phase_state_norm_per_channel` metric at every logging step. If one channel's norm dominates by more than 10× the others at step 1000, the feature has collapsed. Also log `channel_agg.softmax()` to confirm learned aggregation weights have non-trivial dynamic range | Per-channel state norm ratio > 10× at step 1000; or `channel_agg.softmax()` has entropy < 0.5 (in a 4-channel setup, uniform entropy = 2.0) |
| R4 | **Write gate learns to close entirely.** `sigmoid(W_g @ x)` converges toward zero for all tokens, effectively masking all writes to phase memory. Phase state decays to zero and the phase branch becomes inert. | Low (the bias=2.0 initialization starts far from this failure mode) | Medium — phase branch silently becomes a no-op | Emit `_diag_phase_gate_mean` and `_diag_phase_gate_std` at every logging step. Mean below 0.3 or std below 0.05 indicates gate collapse | `_diag_phase_gate_mean < 0.3` at step 1000; phase state L2 norm approaches zero |

**Category C — Interaction risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R5 | **Memory cost scales with `phase_channels`.** Each additional channel multiplies the state tensor size by `C`. For a 4-phase-layer stack with `phase_channels=4`, the state memory is 4× the baseline. On an A100-80GB with `batch=2`, this can push the total memory budget over the limit. | Medium (A100-80GB with batch=2 is the current default per `train_hybrid_7b.py:8–15`, and 4× state memory is ~128 MB for typical configs, well within budget — but `batch=4` or `seq_len=2048` scenarios could tip over) | Medium — OOM crash, clearly observable | Document the memory scaling in the CLI `--help`. Provide a pre-flight memory estimation heuristic: `extra_memory_mb = phase_channels × num_phase_layers × batch × seq_len × num_heads × head_dim × 4 (complex) × 4 bytes / 1024^2`. For B=2, T=1024, H=32, D_h=128, C=4, L=2: ~128 MB — negligible on A100. For B=4, T=2048, C=8, L=4: ~2 GB — potentially significant | OOM on model construction or first forward pass |

**Category D — Operational risks:**

| # | Risk | Likelihood | Severity | Mitigation | Detection signal |
|---|------|------------|----------|------------|------------------|
| R6 | **Diagnostic capture flags are disabled by default.** The `_diag_phase_gate_mean`, `_diag_phase_state_norm_per_channel`, and `_diag_phase_attn_mass` attributes exist at `phase_transformer.py:2082–2086` but are not emitted to the training metric backend unless the training loop explicitly reads them. Without this wiring, R3 and R4 are invisible to operators. | High (the flags are currently captured but not logged) | Medium — mitigations for R3/R4 cannot function without the metrics | The §4 rollout plan explicitly includes **adding metric emission for the diagnostic flags** as part of the File 4 (train.py) patch — not as a follow-up. If the diagnostics are not wired, the feature ships blind | `cg_phase_gate_mean` and `cg_phase_channel_norms` metrics are absent from the training log |

#### 4.6.2 Pre-flight mitigation checklist

Before running any `--phase_channels > 1` or `--phase_write_gate`
experiment:

1. **§2 (P0-2) is shipped and healthy.** Same prerequisite as §3A
   — both §2 and §4 touch `PhaseAttentionLayer` instances in the
   same wrapper, and running them concurrently with §2 unshipped
   makes attribution impossible.
2. **Diagnostic metrics are wired.** Verify that the training log
   emits `cg_phase_gate_mean`, `cg_phase_gate_std`, and
   `cg_phase_channel_norms` (or equivalent names). If these
   metrics do not appear in a smoke test run, the File 4 diagnostic
   wiring from the §4.4 patch is incomplete — stop and fix before
   continuing.
3. **Memory pre-flight.** Compute the expected extra memory cost
   from the R5 heuristic. If `extra_memory > 10%` of the GPU
   budget, either reduce `phase_channels` or reduce batch size
   before running the full measurement.
4. **Checkpoint compatibility plan.** Decide at rollout time
   whether the experiment run will start from a fresh init or
   resume from an existing checkpoint. If resume, the existing
   checkpoint must have been saved with the same `phase_channels`
   value, or the run must start fresh (R2).

---

### 4.7 Success Criteria

P1-2 ships by default in `train_hybrid_7b.py` only if all named
gates pass on a 10K-step FineWeb measurement against a matched
baseline. Structure matches §3A.6 (named run, named baseline,
numbered gates, decision table).

#### 4.7.1 Named evaluation run

```bash
python train_hybrid_7b.py \
    --dataset fineweb \
    --max_steps 10000 \
    --batch_size 1 \
    --gradient_accumulation 8 \
    --phase_warmstart \
    --phase_warmstart_steps 2000 \
    --phase_warmstart_tau 500.0 \
    --phase_channels 4 \
    --phase_write_gate
```

§2 (P0-2) phase warmstart is included because §4 is measured on
top of a §2-shipped stack. The warmstart flag values match §2's
§2.9 success criteria run so the two measurements are directly
comparable.

**Hardware:** A100-80GB or equivalent. `batch=1` with gradient
accumulation of 8 gives `effective_batch=8`, matching the default
`train_hybrid_7b.py` single-GPU configuration.

**Runtime:** 10K steps at this batch size takes ~4–8 hours on an
A100. This is the longest success-criteria run in the document.
The length is justified because the multi-channel memory
specialization (R3) is a slow process — channel decay parameters
that are initialized logarithmically need many thousands of steps
to differentiate through training, and a shorter run cannot
distinguish "still converging" from "collapsed."

#### 4.7.2 Named baseline

```bash
python train_hybrid_7b.py \
    --dataset fineweb \
    --max_steps 10000 \
    --batch_size 1 \
    --gradient_accumulation 8 \
    --phase_warmstart \
    --phase_warmstart_steps 2000 \
    --phase_warmstart_tau 500.0 \
    --phase_channels 1
    # --phase_write_gate intentionally not set
```

Identical to the evaluation run except for the §4 flags. Same
seed, same data, same schedule.

#### 4.7.3 Primary gates

Six numbered gates. Pass condition for each is stated as a delta
against the §4.7.2 baseline.

**Gate 1 — LM loss is not degraded.**

> **Pass condition:** `lm_loss` at step 10000 on the evaluation
> run is within ±1% of the baseline.

Same LM floor as every other priority. P1-2 is an auxiliary
capacity upgrade; if it regresses the primary objective, it does
not ship.

**Gate 2 — LM loss is meaningfully improved, OR validation
perplexity improves.**

> **Pass condition:** At least one of the following holds at
> step 10000:
> - `lm_loss` is **at least 1% lower** than the baseline, OR
> - `val_ppl` on a WikiText-2 validation subset is **at least 2%
>   lower** than the baseline.

This is the "feature actually improved something" gate. The ±1%
LM floor tolerance from Gate 1 admits the case where §4 has no
effect (neither positive nor negative), which means shipping by
default would be unjustified churn. Gate 2 requires a measurable
improvement to justify enabling the feature. Two acceptance
channels (train loss OR validation perplexity) because some
capacity improvements are visible on validation but not on training
loss (and vice versa).

**Gate 3 — Multi-channel memory does not collapse.**

> **Pass condition:** At step 10000, the ratio of the largest
> per-channel state norm to the smallest is at most 10×:
> `max(cg_phase_channel_norms) / min(cg_phase_channel_norms) <= 10`.

Directly addresses R3 (multi-channel collapse). Requires that the
`_diag_phase_state_norm_per_channel` diagnostic be wired per §4.6
R6. If the ratio exceeds 10×, one channel has swallowed the
signal and multi-channel memory has collapsed to single-channel
behavior.

**Gate 4 — Write gate is selective, not degenerate.**

> **Pass condition:** At step 10000:
> - `cg_phase_gate_mean ∈ [0.3, 0.9]`, AND
> - `cg_phase_gate_std ≥ 0.1`.

Directly addresses R4 (write gate collapse). A healthy gate sits
in the middle of its range (not stuck at 0 or 1) and shows
non-trivial variance across tokens (not constant). A gate mean
near the `sigmoid(2) ≈ 0.88` initialization would mean the gate
never learned to differentiate, which is a softer failure than
"collapsed to zero" but still means the feature is not producing
selectivity.

**Gate 5 — Channel aggregation has non-trivial entropy.**

> **Pass condition:** `softmax(channel_agg)` entropy at step
> 10000 is at least 80% of uniform entropy. For `phase_channels=4`,
> uniform entropy is `log(4) ≈ 1.386`, and the gate requires
> entropy `≥ 1.11`.

Complements Gate 3 by catching the case where channel norms are
balanced but `channel_agg` has learned to weight only one of them.
If the learned aggregation collapses to a one-hot vector, the
readout uses only one channel regardless of how well the others
trained.

**Gate 6 — Memory budget respected.**

> **Pass condition:** Peak GPU memory during training does not
> exceed 110% of the §4.7.2 baseline.

Addresses R5 (memory scaling). If the feature pushes peak memory
over 110% of baseline on the standard configuration, operators
using non-default batch sizes or sequence lengths are likely to
hit OOM. The 10% headroom is deliberate — it gives some cushion
without turning the gate into a free pass.

#### 4.7.4 Required diagnostic metrics

Five metrics that must be emitted on every logging step (all
require the §4.6 R6 wiring patch in `train.py`):

- `cg_phase_gate_mean` — mean of the write gate sigmoid output.
- `cg_phase_gate_std` — standard deviation of write gate across
  tokens.
- `cg_phase_channel_norms` — per-channel state L2 norm (list of
  `C` values, emitted as a tensor or a dict).
- `cg_phase_channel_agg` — `softmax(channel_agg)` values (list
  of `C` values).
- `cg_phase_attn_mass_per_channel` — per-channel attention mass,
  diagnostic for which channels are actually contributing to the
  forward output.

Plus the standard gates-1/2 metrics that already exist:
`lm_loss`, `val_ppl`, `peak_memory_mb`.

#### 4.7.5 Decision table

| Gates passing | Verdict |
|---------------|---------|
| **All six pass** | Add `--phase_channels 4 --phase_write_gate` to `train_hybrid_7b.py`'s default argparse block. Merge `phase-mcmem-v1` to `main`. File finding note. |
| **Gate 1 fails** (LM regression) | Investigate R1 (kwargs not threaded) and R3/R4 (channel or gate collapse degrading training). If R1 is ruled out, downgrade to optional and file finding. Do not ship by default. |
| **Gate 2 fails** (no improvement) | Run Configuration C ablation from §4.5.2 to isolate which mechanism (channels or write gate) is inert. If channels alone show no improvement, log as "multi-channel capacity not useful on this workload." If write gate alone shows no improvement, log as "write gating not useful." Downgrade to optional. |
| **Gate 3 or Gate 5 fails** (channel collapse) | Investigate whether training steps were sufficient for channel differentiation (may need longer run). Re-run at 20K steps if resources permit. If collapse persists at 20K, downgrade to optional — the multi-horizon hypothesis does not hold for this workload. |
| **Gate 4 fails** (gate collapse) | Lower gate bias initialization from `2.0` to `1.0` and re-run. The lower init makes early-training gate values slightly more selective and may prevent the gate from sitting frozen near its initialization. |
| **Gate 6 fails** (memory regression) | Reduce `phase_channels` from 4 to 2. Re-run. If Gate 6 fails at `phase_channels=2`, the memory cost is intrinsic and operators must reduce batch size. Document the memory trade-off in the finding note. |

### 4.8 Rollout Plan

Six phases. Simpler than §3A's seven because P1-2 does not need
a separate "gate evaluation" phase — the gate computation is fast
enough to fold into the decision phase.

#### 4.8.1 Phase 0 — Prerequisites

**Actions:**

1. **Verify §2 (P0-2) is shipped and healthy.** Same prerequisite
   as §3A — both §2 and §4 touch `PhaseAttentionLayer` in the
   same wrapper, and running §4 on a build where §2 is not yet
   in place or is known-broken makes attribution impossible.
2. **Locate `MistralHybridWrapper.__init__` and the block
   construction loop in `mistral_hybrid_wrapper.py`.** Line
   numbers will drift — the rollout note is the source of truth.
3. **Verify `_diag_phase_*` capture flags exist.** Open
   `phase_transformer.py:2082–2086` and confirm the attributes
   are still in place. The §4 rollout depends on reading them;
   if a future refactor has moved or removed them, the §4
   diagnostic wiring cannot work and must be redesigned before
   continuing.

**Artifact:** rollout note recording file/line references.

**Gate:** all three actions succeed.

#### 4.8.2 Phase 1 — Implementation

Apply the four-file patch from §4.4 in order:

1. `config.py` — two new fields.
2. `mistral_hybrid_wrapper.py` — constructor kwargs + block
   construction + diagnostic print.
3. `model_factory.py` — thread fields into wrapper constructor.
4. `train.py` — argparse flags + `UnifiedConfig` threading +
   **metric emission wiring for the `_diag_phase_*` flags
   (critical — R6)**.

The metric wiring in File 4 must walk `model.modules()` for
`PhaseAttentionLayer` instances, extract the diagnostic
attributes, and emit them as `cg_phase_*` metrics at every
logging step. This is the §4.6 R6 mitigation and is the only
file-4 work beyond the argparse plumbing.

**Gate:** smoke test with `--phase_channels 4 --phase_write_gate`
completes 100 steps on synthetic data, all five diagnostic
metrics appear in the log, no NaN/Inf.

#### 4.8.3 Phase 2 — Unit tests

Three tests:

1. **R1 regression guard.** Construct `MistralHybridWrapper(
   phase_channels=4, phase_write_gate=True)`. Walk
   `model.modules()` for `PhaseAttentionLayer` and assert
   `channel_decay_logit.shape == (4*num_heads,)` and
   `write_gate_proj is not None`. Walk for
   `LocalTransformerBlock` (the `i < local_layers` branch) and
   assert those do NOT have `channel_decay_logit`.
2. **Diagnostic wiring test.** Construct the wrapper, run a
   forward pass with synthetic input, and assert that
   `_diag_phase_gate_mean` is not `None` after the forward.
3. **Checkpoint compatibility test.** Save a checkpoint with
   `phase_channels=1`, attempt to load into a model built with
   `phase_channels=4`, and assert that `load_state_dict(strict=True)`
   raises a clear error. Then repeat in the opposite direction.
   This locks in R2's expected failure mode.

**Gate:** all three tests pass.

#### 4.8.4 Phase 3 — Smoke test and diagnostic verification

Run a 200-step synthetic test with
`--phase_channels 4 --phase_write_gate --phase_warmstart
--phase_warmstart_steps 50 --phase_warmstart_tau 10`. Verify:

1. All five diagnostic metrics appear in the log.
2. `cg_phase_gate_mean` starts near `sigmoid(2) ≈ 0.88` and
   either stays there or drifts measurably.
3. `cg_phase_channel_norms` are approximately equal at step 0
   (uniform initialization) and diverge slightly by step 200.
4. No NaN/Inf in any metric.
5. Peak GPU memory is within 10% of a baseline run with
   `--phase_channels 1`.

**Gate:** all five checks pass.

#### 4.8.5 Phase 4 — Baseline + evaluation measurement

Run the §4.7.2 baseline first, then the §4.7.1 evaluation run.
Both runs save per-step metric logs. 10K steps each, ~4–8 hours
per run on an A100.

Unlike §3A.7 which separates baseline and evaluation into two
phases with a gate in between, §4.8 combines them into a single
phase because:

- The baseline run is not itself a gate for the evaluation run.
- The baseline-vs-evaluation comparison is done only at the end,
  after both runs complete.
- Running them sequentially on the same GPU is the most
  resource-efficient path.

**Gate:** both runs complete cleanly, all diagnostic metrics
present, no NaN/Inf.

#### 4.8.6 Phase 5 — Gate evaluation and decision

Compute Gates 1–6 from §4.7.3 against the recorded values. File
a finding note with:

- The rollout note reference.
- Per-gate pass/fail with raw numbers.
- The §4.7.5 decision table verdict.
- Peak memory values for both runs.
- The `channel_agg.softmax()` values at step 10000 for the
  evaluation run (diagnostic for understanding channel
  specialization).

**Branch A — all six gates pass:** add
`--phase_channels 4 --phase_write_gate` to
`train_hybrid_7b.py`'s default argparse block. Merge
`phase-mcmem-v1` to `main`.

**Branch B — some gates fail:** consult the §4.7.5 decision
table. Re-run specific configurations as needed, file finding
note, do not change defaults if the decision is downgrade.

#### 4.8.7 Rollback path

Trivial. §4 is entirely additive and defaults to off.

- **Unmerged rollback:** do not merge `phase-mcmem-v1`.
- **Merged rollback:** set `--phase_channels 1` (the default) on
  affected runs, or remove the flags from the script. No code
  revert needed.
- **Full code revert** only if the master-switch behavior is
  broken — i.e., if `phase_channels=1, phase_write_gate=False`
  runs produce different results from a pre-§4 build. This
  should be impossible by design and is the reason Phase 1's
  smoke test includes a run with the defaults.

---

### 4.9 Out of Scope

Three categories matching §3A.8's structure: deferred, hard
limits, non-goals.

#### 4.9.1 Deferred — plausible follow-ups with a measurement path

- **`phase_channels > 4`.** The core supports arbitrary `C`. The
  v1 success criteria use `C=4` because that is the smallest
  value that spans the logarithmic decay range meaningfully. `C=8`
  would roughly double memory and compute cost for a 2× finer
  decay grid; the benefit is unclear without the `C=4` baseline
  measurement. Defer until `C=4` is measured.
- **Per-layer `phase_channels`.** A hypothetical design where
  early phase layers use `C=1` and later layers use `C=4` or
  more, reflecting the intuition that early layers handle
  short-range structure and later layers handle long-range
  structure. Architecturally plausible but not supported by the
  current `HybridTransformerBlock` constructor — would require
  threading a per-layer list instead of a scalar. Out of scope
  until the uniform-`C` version is measured and found wanting.
- **Adaptive channel count.** A design that starts with `C=1` and
  grows channels during training once the single-channel signal
  plateaus. Requires checkpoint-format changes (channel count as
  dynamic state) and training-loop instrumentation to detect
  plateau. Deferred.
- **Learned channel initialization.** Instead of the hardcoded
  logarithmic spread over `[2.0, 2048.0]` at
  `phase_transformer.py:2057`, make the initialization
  itself learnable from data or expose the min/max timescales
  as CLI flags. Not blocking anything, not justified by any
  measurement.
- **Write gate temperature / sharpness.** Exposing a `tau`
  parameter on `sigmoid(W_g @ x / tau)` to control gate
  sharpness. The hard-probes source uses unit temperature; §4
  matches. Deferred because no evidence exists that temperature
  matters.
- **Gate loss regularization.** Adding a regularization term that
  pushes gate values toward a target mean (e.g., to prevent R4
  gate collapse proactively instead of reactively). Interesting
  but would require a new loss hyperparameter, which v1 is
  deliberately avoiding.
- **Non-Mistral hybrid path extension.** `HybridPhaseTransformer`
  (the non-Mistral hybrid at `phase_transformer.py:6737+`)
  already wires up `phase_channels` and `phase_write_gate` in
  its own construction path. The §4 rollout adds the flags to
  the unified CLI, so `HybridPhaseTransformer` automatically
  benefits when the model type is `hybrid` instead of
  `mistral_hybrid` — **this is already in scope** because the
  CLI flags reach both model factories. The only thing out of
  scope is adding a separate success-criteria measurement for the
  non-Mistral hybrid path; that would be a follow-up if anyone
  is actively developing the non-Mistral path.

#### 4.9.2 Hard limits — will not be done even if asked

- **No modification to `PhaseAttentionLayer` internals.** The
  forward-path composition order at `phase_transformer.py:2434–2463`
  (write gate → channel expansion → warmstart → EMA scan) is
  deliberate and correct. §4 does not reorder any of those
  steps, skip any of them, or add new steps. Changes to the
  composition order would affect every caller of
  `PhaseAttentionLayer`, including the non-Mistral hybrid path,
  and must be a separate design effort.
- **No modification to `HybridTransformerBlock` or
  `HybridAttentionLayer`.** They already accept and forward the
  kwargs; §4 does not touch their implementations. If a future
  finding shows that the forwarding logic is wrong, that is a
  core-phase-transformer bug, not a §4 issue.
- **No gradient flow to the frozen Mistral backbone.** Same
  contract as §2 and §3A — the write gate and multi-channel
  parameters are part of the trainable phase layers only. The
  backbone stays frozen.
- **No new `model_type`.** §4 is two flags on `mistral_hybrid`.
  No `mistral_hybrid_multichannel` or similar variant.
- **No change to `LocalTransformerBlock`.** Local blocks have
  no phase attention and no multi-channel concept. §4 does not
  expand the local attention mechanism to have channels.
- **No runtime modification of `phase_channels` after
  construction.** Once the model is built with `phase_channels=C`,
  that value is fixed for the lifetime of the model. §4 does
  not support dynamic channel count changes mid-training. Future
  extensions that want this should add it to the deferred
  "adaptive channel count" item in §4.9.1.

#### 4.9.3 Non-goals — clarifications

- **§4 is not a new attention mechanism.** It is a capacity
  expansion of the existing phase attention. The attention math
  is unchanged — what changes is how many independent EMA-state
  slots each head maintains and whether writes to those slots
  are gated.
- **§4 is not a solution to LM perplexity on its own.** §4.7
  Gate 2 requires a measurable improvement on at least one of
  training loss or validation perplexity, but the improvement
  may be modest (1–2%). §4 is a capacity upgrade, not a
  breakthrough — expected gains are on the order of "a useful
  small improvement" rather than "a step change." If §4.7
  measurements show no improvement at all, §4 downgrades to
  optional and the hypothesis that multi-horizon phase memory
  matters for this workload is falsified.
- **§4 is not a replacement for §2 (phase warmstart).** §2 fixes
  early-training stability; §4 expands capacity for the
  stable-training regime. Both should be enabled together.
  Disabling §2 while enabling §4 is not a supported
  configuration — the phase branch would spike early training
  while simultaneously running with 4× more memory state to
  thrash through.
- **§4 is not tuned.** The defaults (`C=4`, logarithmic decay
  spread over `[2.0, 2048.0]`, gate `bias=2.0`, uniform
  `channel_agg` init) are all inherited from the hard-probes
  source without modification. If §4.7 measurements suggest
  different values work better, that is a separate tuning
  effort on top of the shipped v1.
- **§4 is not a research benchmark.** The hard-probes
  `train_hard_probes.py` pipeline has the full research
  harness for testing phase memory hypotheses — ablations,
  per-channel analyses, comparison against alternative memory
  mechanisms. §4 is the production wiring of the two specific
  primitives that hard-probes has validated. Operators who want
  research-grade measurement should continue to use
  `train_hard_probes.py`, not `train_hybrid_7b.py`, for that
  purpose.

---

**End of §4 (P1-2: Phase Write-Gate + Multi-Channel Phase Memory).**

---

## §5 Closing Notes — P2 Rescoping and Final Priority Table

### 5.1 P2-1 Rescoped: `LayerInfluenceDiagnostics` — Dropped

The original recommendation to port `LayerInfluenceDiagnostics` from
`train_hard_probes.py:1898` to both `mistral_cg` and `mistral_hybrid`
is **withdrawn** after closer investigation.

**Reason:** `LayerInfluenceDiagnostics` computes pseudo-phase metrics
from hidden-state heuristics (`hidden_states[..., :num_heads * 4]`
treated as a phase signal) and classifies layers as
CONSTRUCTIVE / NEUTRAL / DESTRUCTIVE. This was designed for the
hard-probes SRK architecture's named intervention points (DNA Bridge,
CSR Alignment, Witness Arbitrator, Synthesis Gate) — not for
standard transformer layers.

For `mistral_hybrid`, the native `_diag_phase_*` diagnostics at
`symbolu/phase_transformer.py:2082–2086` already measure the **real**
phase signal — complex phasors, per-channel state norms, write gate
activations, warmstart alpha. These are strictly more accurate than
LID's hidden-state proxy. Porting LID would add a second, weaker
diagnostic that operators would have to learn to distrust.

For `mistral_cg`, the architecture has no stack of phase-learning
layers for LID to operate on. The frozen Mistral backbone does
standard attention; the CG modules are single intervention points,
not a stack. LID's per-layer analysis is conceptually mismatched.

**Where the real diagnostic work lives:** §4.6 R6 already identifies
the critical gap — the native `_diag_phase_*` capture flags exist
but are **not wired to the training metric backend**. The §4.8.2
Phase 1 rollout plan explicitly includes wiring these metrics to the
log as part of the `train.py` patch for P1-2. That work addresses
the real observability gap and is strictly more valuable than porting
LID.

**What could be salvaged (optional follow-up, not tracked):** LID's
visual report format (the `get_influence_bar()` ASCII bar rendering
and the CONSTRUCTIVE/NEUTRAL/DESTRUCTIVE classification framework)
is a useful UX pattern. A future follow-up could build a small
~50-line wrapper in `symbolu_training/training/unified/diagnostics.py`
that reads the native `_diag_phase_*` metrics and pretty-prints them
with a bar-chart summary at every logging interval. This is cosmetic,
not functional, and does not block any priority.

### 5.2 P2-2 Rescoped: Kosha Gyroscopic Loss for CG — 5-Line Fix

The original recommendation to port the Kosha Gyroscopic Loss from
`train_hard_probes.py` to the CG path is **rescoped** from a full
design section to a 5-line validation task.

**Reason:** `KoshaGyroscopicLoss` is **already fully implemented and
integrated** in the unified training pipeline:

- Class: `symbolu_training/losses/kosha_gyroscope.py:307`
- Import: `train.py:291`
- Construction: `train.py:2098–2134` (~40 lines of config threading
  with Harmonic Pentad, Three-Stage Hybrid Logic, Dynamic Weight
  Scheduler, PID authority control, Reflexive Domain Morph)
- Loss computation: `train.py:4327–4372`
- Checkpointing: `train.py:7981`, `checkpointing.py:38, 111, 464`
- Curriculum integration: `train.py:2187–2188`
- CLI flag: `train.py:9364` — `--enable_kosha_gyroscope`
- Config: `config.py:329` + ~20 gyroscope-specific config params

There is nothing to port from hard_probes. The hard_probes version
at `train_hard_probes.py:1087` is an older, simpler variant. The
unified pipeline's version is more mature.

**The only code gap:** at `train.py:4339`, the Kosha state extraction
is hardcoded to `ontological` and `ontological_hybrid` model types:

```python
if config.model_type in ("ontological", "ontological_hybrid"):
    sovereign_state = outputs.get('state', None) ...
    kosha_states_for_gyro = sovereign_state[:, KOSHA_SLICE].unsqueeze(1)
```

`mistral_cg` also produces `outputs['state']` with the same 32D
Sovereign State (including `KOSHA_SLICE` at `[12:17]`), but the
extraction code does not include it. The fix is:

```python
if config.model_type in ("ontological", "ontological_hybrid", "mistral_cg"):
```

**Validation task (not a design section):**

1. Apply the 5-line `model_type` branch addition at `train.py:4339`.
2. Run `./scripts/train_mistral_cg.sh --smoke-test
   --enable_kosha_gyroscope` and confirm:
   - No crash.
   - `gyroscope_loss` metric appears in the log.
   - The gyroscope's curriculum controller initializes without
     conflicting with `cg_stage_manager`.
3. Run a 200-step WikiText-2 test with both
   `--enable_conscious_generation` and `--enable_kosha_gyroscope`
   and confirm that `cg_ont_loss`, `cg_kosha_routing_loss`, and
   `gyroscope_loss` all decrease without interference.
4. If the smoke test passes, add `--enable_kosha_gyroscope` to
   `scripts/train_mistral_cg.sh` alongside the existing CG flags.

**Interaction risks to verify during the smoke test:**

- **Double Kosha signal:** the CG path already trains the Kosha
  slice via `lambda_kosha_routing` (shortlist routing loss). The
  Kosha Gyroscope pushes on the same Kosha slice `[12:17]` via
  homeostatic bounds. These are complementary
  (`lambda_kosha_routing` = ranking signal, gyroscope = regulatory
  bounds) but the composition must be verified empirically. If the
  gyroscope clamps Kosha values to a narrow band while
  `lambda_kosha_routing` pushes them outside that band, the two
  losses will fight and training will oscillate. The smoke test's
  200-step run is the minimum needed to detect this.
- **Curriculum conflict:** both `cg_stage_manager` and
  `kosha_curriculum_controller` manage training schedules. If they
  both override the same parameters at different phases, training
  could oscillate or stall. Verify that `kosha_curriculum_controller`
  operates on gyroscope-specific parameters and does not touch the
  CG lambda weights.
- **Sovereign State load:** P0-1's VICReg anti-collapse and §3A's
  LSTB prediction both pull on the Sovereign State. Adding a third
  signal (Kosha Gyroscope's homeostatic bounds on the `[12:17]`
  slice) adds a third constraint. The smoke test should confirm
  that `cg_anticollapse_var` remains healthy when the gyroscope
  is active.

**Ship criteria:** smoke test passes (no crash, metrics present, no
oscillation) + 200-step measurement shows no regression on existing
CG auxiliaries. If the smoke test reveals a curriculum conflict or
a double-Kosha-signal oscillation, file a finding note and leave
`--enable_kosha_gyroscope` off by default for CG until the conflict
is resolved.

### 5.3 Revised Priority Table

The final priority table after rescoping P2-1 and P2-2:

| Priority | Target | Feature | Section | Status |
|----------|--------|---------|---------|--------|
| **P0-1** | `mistral_cg` | VICReg anti-collapse on Sovereign State projector | §1 | Full design |
| **P0-2** | `mistral_hybrid` | Phase warmstart curve | §2 | Full design |
| **P1-1a** | `mistral_cg` | LSTB latent bridge (temporal prediction target) | §3A | Full design |
| **P1-1b** | `mistral_cg` | CSR phonemic grounding (P3, deferred) | §3B | Half-depth design |
| **P1-2** | `mistral_hybrid` | Phase write-gate + multi-channel memory | §4 | Full design |
| ~~P2-1~~ | ~~Both~~ | ~~`LayerInfluenceDiagnostics`~~ | §5.1 | **Dropped** — redundant with native `_diag_phase_*` diagnostics; real work is §4.6 R6 metric wiring |
| ~~P2-2~~ | ~~`mistral_cg`~~ | ~~Kosha gyroscopic loss~~ | §5.2 | **Rescoped** — already fully integrated, needs only a 5-line `model_type` branch + smoke test validation |

### 5.4 Summary of Deliverables

This design document specifies **four full-design features** and
**one half-depth design option**, totaling five features that
require code changes:

| Feature | Patch size | New trainable params | Key mechanism |
|---------|-----------|---------------------|---------------|
| P0-1 VICReg anti-collapse | ~80 lines | 0 | Unary VICReg on pooled 32D state |
| P0-2 Phase warmstart | ~60 lines | 0 | Sigmoid alpha curve on phase branch |
| P1-1a LSTB latent bridge | ~76 lines | ~100K | `PhaseJEPAPredictor` + JEPA loss on per-token state trajectory |
| P1-1b CSR phonemic grounding | ~170 lines | 0 | Precomputed `[V, 10]` ARPABET table + masked MSE on `T` column 3 |
| P1-2 Phase write-gate + channels | ~32 lines | ~10K–50K | `write_gate_proj` + `channel_decay_logit` + `channel_agg` per hybrid block |

Plus one **validation task** (P2-2 Kosha Gyroscope 5-line branch,
no design section) and one **dropped feature** (P2-1 LID, replaced
by §4.6 R6 metric wiring).

**Recommended implementation order:**

1. **P0-1 + P0-2** (parallel — independent features on independent
   targets). P0-1 addresses silent collapse in CG; P0-2 addresses
   early-step instability in hybrid. Both are ~60–80 line patches
   with no trainable modules.
2. **P2-2 validation** (immediately after P0-1 — the 5-line
   `model_type` branch can be added in the same commit as P0-1,
   since both touch the CG loss block in `train.py`).
3. **P1-2** (after P0-2 — depends on the hybrid wrapper having the
   phase warmstart wiring in place first, since §4 and §2 compose).
4. **P1-1a** (after P0-1 — depends on the Sovereign State projector
   having anti-collapse regularization, since LSTB builds on it).
5. **P1-1b** (only after P1-1a measurements are complete — P3
   priority, gated on P1-1a results per §3.0).

Each feature ships on its own branch, with its own success criteria,
and rolls back independently. No feature depends on another feature
being enabled at the same time — they are complementary, not
compositionally required.

### 5.5 Critical Re-evaluation — Do These Features Actually Need to Exist?

After the design document was completed, a second-pass critical
evaluation was performed to verify whether the **claimed failure
modes actually exist** in the current codebase, and whether the
proposed features are genuinely needed or already addressed by
existing mechanisms. This section amends the priority table
accordingly.

The evaluation is **deliberately harsh** — the question is not
"would this feature be architecturally elegant?" but "does the
existing codebase already prevent the failure mode this feature
claims to fix?"

#### P0-1 (VICReg anti-collapse on Sovereign State) — DEMOTE to optional

**The design doc claims:** The 32D Sovereign State projector is
vulnerable to representational collapse because it's a low-dimensional
bottleneck with weak supervision. VICReg is needed to prevent the
projector from mapping all inputs to a narrow cone.

**What the code actually does:** `SovereignStateProjector` at
`symbolu_training/jepa/state_projector.py:168` applies **per-plane
normalization constraints** to every output:

- **Bhava [0:12]:** `torch.softmax(bhava, dim=-1)` — forces one
  value to dominate, prevents all-zero, guarantees the output
  sums to 1.0.
- **Koshas [12:17]:** `torch.sigmoid(kosha)` — each dimension
  independently maps to `(0, 1)`.
- **Vrittis [17:22]:** `torch.softmax(vritti, dim=-1)` — same as
  Bhava.
- **Gunas [22:28]:** `torch.sigmoid(guna)` — same as Koshas.
- **Reserved [28:32]:** `torch.tanh(reserved)` — bounded to
  `(-1, 1)`.

These constraints **partially prevent collapse**: softmax and sigmoid
prevent all-zero output and guarantee bounded, non-degenerate values.
However, they do NOT prevent **constant-collapse** — a degenerate
projector that ignores its input and produces the same softmax
distribution for every sequence would pass through the constraints
unchanged.

**What already guards against constant-collapse:** The 6 CG auxiliary
losses (`lambda_ont`, `lambda_kosha_routing`, `lambda_bliss_token`,
`lambda_plausibility_token`, `lambda_csr_token`, `lambda_vritti_token`,
`lambda_guna_token`) each produce gradients that depend on the input
tokens. For the projector to produce a constant output, ALL 6 losses
would need to produce gradients that push toward constant output,
which requires all 6 scoring paths to be simultaneously degenerate.
This is possible in theory but unlikely in practice.

**Verdict: DEMOTE to optional.** The per-plane constraints provide
structural protection against zero-collapse, and the diversity of CG
losses provides indirect protection against constant-collapse. VICReg
would add explicit variance enforcement — a belt-and-suspenders
improvement, not a fix for an active failure mode. **Only implement
if baseline measurements (§1.8 step 1) show state variance below a
concerning threshold.** If baseline variance is healthy, skip this
feature entirely.

#### P0-2 (Phase warmstart curve for mistral_hybrid) — DEMOTE to optional

**The design doc claims:** Phase attention contributes random output
from step 0, corrupting the frozen backbone's signal and causing
an early-step LM loss spike. A sigmoid warmstart curve dampens
the phase contribution during early training.

**What the code already does:** `MistralHybridWrapper` has **three
layers of early-step protection** that the design doc acknowledges
but undervalues:

1. **`adapter_gate = nn.Parameter(torch.tensor([-2.0]))`** at
   `mistral_hybrid_wrapper.py:161` — `sigmoid(-2) ≈ 0.12`, so only
   12% of the adapter output reaches the residual stream.
2. **`nn.init.zeros_(self.phase_output_proj[-1].weight)`** at `:150`
   — the final linear layer of the output projection is
   zero-initialized.
3. **`nn.init.zeros_(self.phase_output_proj[-1].bias)`** at `:151`
   — the final linear layer's bias is also zero.

At step 0, the net contribution of the phase branch is:

```text
adapted_hidden = hidden + sigmoid(-2) × (0_weight × phase_output + 0_bias)
               = hidden + 0.12 × 0
               = hidden
```

The phase contribution is **literally zero at initialization**,
regardless of how noisy the phase attention's internal activations
are. The phase branch only starts contributing to the residual
stream as the optimizer moves `phase_output_proj` away from zero
— which happens gradually, governed by the learning rate, and is
itself an **implicit gradient-driven warmstart**.

The explicit sigmoid warmstart from §2 would add a **4th dampening
factor** on top of the three that already exist. At early steps,
it would multiply `0.12 × 0 × warmstart_alpha ≈ 0` — dampening
something that is already zero.

**Verdict: DEMOTE to optional.** The existing three-layer
initialization (`adapter_gate` + zero-weight + zero-bias) already
provides effective warmstart. Phase blocks receive near-zero
gradient in early steps because the output projection is zero and
the gate is small. An explicit sigmoid schedule is a marginal
stability improvement, not a fix for an active failure mode. **Only
implement if a baseline measurement shows an actual early-step LM
loss spike.** If the existing initialization already produces a
smooth loss curve, skip this feature.

#### P1-1a (LSTB latent bridge for mistral_cg) — DEMOTE to experimental

**The design doc claims:** The 32D Sovereign State has no causal
prediction target and the trajectory is temporally incoherent. LSTB
adds a JEPA-style prediction loss to reward temporal coherence.

**What the code already provides:** The `SovereignStateProjector`
runs on the frozen Mistral backbone's hidden states. These hidden
states are already locally correlated by the transformer's
self-attention mechanism — consecutive token positions produce
similar hidden representations because they attend to overlapping
context windows. This means the per-token Sovereign State trajectory
is likely to be locally coherent **by construction**, not because of
any explicit training signal but because the backbone's outputs are
correlated.

Additionally, `PhaseJEPAPredictor` uses complex-phasor attention
with multi-step autoregressive rollout — a sophisticated mechanism
designed for rich latent-space dynamics. For a 32D state trajectory
that is already locally correlated, a simple 1-layer MLP predictor
would likely serve the same purpose at a fraction of the complexity.

**What raises real concern:** The §3A design is careful about the
"verify first" discipline (§3A.6 Gate 2 requires beating an
identity baseline by 30%), and the rollout plan includes baseline
measurement. This discipline is correct — but the feature should
not have been positioned as P1 if the failure mode is unproven.

**Verdict: DEMOTE to experimental.** The claimed failure mode
(temporal incoherence) is hypothetical, not demonstrated. The
backbone provides implicit local coherence, and the CG auxiliary
losses already train the projector through 6+ diverse paths. **Do
not implement until a baseline measurement proves the trajectory is
actually incoherent.** If the identity-baseline comparison (§3A.6
Gate 2) shows the trajectory is already smooth, this feature adds
compute and complexity without benefit.

#### P1-1b (CSR phonemic grounding) — DROP from active list

**The design doc itself flags this as P3.** It should not appear on
a priority list at all. The design is in the document as a
reference for future operators; it is not a shipping feature.

**Verdict: DROP from the priority table.** Retain the §3B design
text as reference documentation but remove P1-1b from any list of
features to implement.

#### P1-2 (Phase write-gate + multi-channel for mistral_hybrid) — DEMOTE to experimental

**The design doc claims:** Single-channel phase memory can only
specialize at one timescale, and unconditional writes corrupt
long-range memory on noisy tokens.

**What the code already provides:** `PhaseAttentionLayer` at
`symbolu/phase_transformer.py:2015` implements `learned_decay=True`
with **per-head** decay parameters. With 32 heads and learned
decay, each head can independently learn a different timescale.
Additionally, the EMA scan's exponential decay inherently suppresses
noisy tokens: a token's contribution to memory decays exponentially
with distance, so noisy tokens far in the past contribute near-zero
to the current state.

The multi-channel mechanism provides a stronger inductive bias
(logarithmic initialization across explicit timescale bands), but
the existing per-head learned decay already addresses the core
problem. Whether the stronger inductive bias actually produces
measurably better results is an empirical question.

**Verdict: DEMOTE to experimental.** The existing per-head learned
decay provides multi-timescale capacity. Write gating may be
redundant with EMA's inherent noise suppression. **Do not implement
until a measurement shows that per-head decay is insufficient** —
specifically, that the per-head decay parameters converge to
similar values despite the task requiring multi-horizon memory.

#### P2-2 (Kosha gyroscopic loss 5-line fix) — DROP

**Already rescoped to a 5-line fix in §5.2.** However, even the
5-line fix is not justified:

The Kosha Gyroscope is a sophisticated subsystem with ~20 config
parameters, a PID authority controller, three-stage hybrid logic,
domain morphing, and its own curriculum integration — all designed
and tuned for the `ontological` / `ontological_hybrid` model types
which have different training dynamics. Adding `"mistral_cg"` to a
model-type check does not validate that the gyroscope's
hyperparameters are appropriate for the CG path. At minimum, the
floor/ceiling thresholds, engagement PPL curves, and authority
controller dynamics would need CG-specific tuning.

**Verdict: DROP.** Either invest in full CG-specific gyroscope
tuning (a substantial effort, not a 5-line patch) or leave the
gyroscope on the model types it was designed for. A 5-line patch
that enables a 20-parameter subsystem without retuning is a
liability.

### 5.6 Revised Priority Table (Post Re-evaluation)

| Priority | Feature | Original verdict | Revised verdict | Key finding |
|----------|---------|-----------------|-----------------|-------------|
| ~~P0-1~~ | VICReg anti-collapse | Full design, recommended | **OPTIONAL** — implement only if baseline shows low state variance | Per-plane softmax/sigmoid + diverse CG losses already provide meaningful collapse protection |
| ~~P0-2~~ | Phase warmstart curve | Full design, recommended | **OPTIONAL** — implement only if baseline shows early-step LM spike | Three-layer init (adapter_gate + zero-weight + zero-bias) already produces zero phase contribution at step 0 |
| ~~P1-1a~~ | LSTB latent bridge | Full design, recommended | **EXPERIMENTAL** — implement only after proving temporal incoherence exists | Backbone provides implicit local coherence; 6 CG losses already train the projector; JEPA predictor may be over-engineered for a 32D trajectory |
| ~~P1-1b~~ | CSR phonemic grounding | Half-depth, P3 | **DROPPED** — retain design text as reference only | Already flagged as P3 in the original design; no place on an active priority list |
| ~~P1-2~~ | Phase write-gate + multi-channel | Full design, recommended | **EXPERIMENTAL** — implement only after proving per-head decay is insufficient | Per-head `learned_decay=True` with 32 heads already provides multi-timescale capacity; EMA inherently suppresses noise |
| ~~P2-2~~ | Kosha gyroscopic loss | 5-line fix | **DROPPED** — either invest in full CG tuning or skip | 5-line patch of a 20-param system designed for a different model type is a liability |

### 5.7 What Should Actually Ship

**None of the features have demonstrated a failure mode that
currently exists in the codebase.** Every feature in this document
addresses a hypothetical problem that *might* exist but has not been
measured.

The honest recommendation is:

1. **Run baseline measurements first.** Before implementing any
   feature, run the existing `mistral_cg` and `mistral_hybrid`
   pipelines for 1000 steps and measure:
   - **For P0-1:** `outputs['state'].var(dim=0).mean()` across
     batches. If > 0.5, skip P0-1.
   - **For P0-2:** Per-step LM loss curve. If smooth and
     monotonically decreasing after step 50, skip P0-2.
   - **For P1-1a:** Per-token state cosine similarity between
     adjacent positions. If > 0.8, the trajectory is already
     coherent — skip P1-1a.
   - **For P1-2:** Per-head decay parameter values after 1000
     steps. If they span at least a 10× range (e.g., some heads
     at 0.97, others at 0.999), the existing mechanism is working
     — skip P1-2.

2. **Implement only the features whose baseline measurements
   reveal a real problem.** This may be zero features, one
   feature, or all four. The design document provides the
   implementation plan for each; the baseline measurements
   determine which plans to execute.

3. **The design document remains valuable as reference.** Even if
   no features ship, the document serves as:
   - A record of what was considered and why it was deferred.
   - Ready-to-execute implementation plans for each feature,
     available whenever a future training run reveals the failure
     mode.
   - A precedent for "measure first, implement second" discipline
     in future feature proposals.

**The single most productive next step is not implementing any
feature — it is running the four baseline measurements above.**
The results determine everything else.

---

---

## §6 The Real Fix — Gradient Routing Imbalance in the Sovereign State Projector

### 6.1 Finding: The Problem Is Gradient Imbalance, Not Collapse

A targeted investigation of gradient flow through the `mistral_cg`
training path revealed that the 32D Sovereign State projector
(`SovereignStateProjector` at
`symbolu_training/jepa/state_projector.py:43`) does not have a
collapse problem. It has a **gradient routing imbalance problem**
where the Bhava plane receives ~100× stronger training signal than
the governance planes.

Two gradient paths reach the projector:

**Path A — Stage 8 → LM Cross-Entropy (STRONG):**

```text
state_projector → state [B, 32]
  → state[:, BHAVA_SLICE] → bhava_seq [B, T, 12]
  → bhava_matrix [B, 12, 12]  (outer product)
  → PerspectiveSynthesizer (mistral_wrapper.py:428–443)
  → conditioned adapted_hidden [B, T, D]
  → logits via frozen lm_head
  → LM cross-entropy loss (~4 nats)
  → full-strength gradient back through state_projector
```

No `.detach()` on the state during the forward pass — verified by
exhaustive search of `mistral_wrapper.py` and the CG loss block in
`train.py:4931–5250`. The Bhava slice `[0:12]` receives **direct,
full-strength gradient** from the primary LM objective every step.

**Path B — CG Auxiliary Losses (WEAK):**

```text
state → Kosha [12:17] → KoshaDomainRouter → lambda_kosha (0.01)
state → Guna  [22:28] → BlissTokenGate    → lambda_bliss (0.01)
state → concat(hidden, state) → Primitive Scorers:
    → JEPA scorer   → lambda_plausibility (0.005)
    → CSR scorer    → lambda_csr          (0.005)
    → Vritti scorer → lambda_vritti       (0.005)
    → Guna scorer   → lambda_guna         (0.005)
```

Total effective weight from all CG auxiliary losses: **~0.046**.
Against an LM loss of ~4 nats, the governance planes receive
approximately **1.15%** of the effective gradient signal.

**The resulting asymmetry:**

| Plane | Dims | Gradient source | Effective magnitude |
|-------|------|----------------|---------------------|
| Bhava (identity) | [0:12] | Path A: full LM loss via Stage 8 | **~4.0** |
| Kosha (governance) | [12:17] | Path B: `lambda_kosha` | 0.01 |
| Vritti (cognitive) | [17:22] | Path B: `lambda_vritti` | 0.005 |
| Guna (energetic) | [22:28] | Path B: `lambda_guna` + `lambda_bliss` | 0.015 |
| Reserved (learning) | [28:32] | Path B: indirect | ~0.005 |

The Bhava slice is well-trained because Stage 8 feeds it into the
LM loss path. The governance planes are **starved** — they receive
real gradient, but at ~1% the magnitude of the Bhava gradient. The
projector learns a good 12D Bhava representation and a barely-
trained 20D governance representation.

**Why VICReg is the wrong fix:** VICReg says "make all 32 dimensions
have non-trivial variance." But variance is not the problem — the
Bhava slice has plenty of variance because it gets strong gradient.
The governance planes may have low variance, but that is a
**symptom** of weak training signal, not structural collapse.
Enforcing variance on under-trained planes produces high-variance
noise, not meaningful representations. The right fix addresses the
root cause (gradient magnitude imbalance), not the symptom
(low variance).

**Why this finding supersedes §1 (P0-1).** The entire §1 design
(VICReg anti-collapse) was predicated on the assumption that the
projector's 32D bottleneck is vulnerable to representational
collapse. The investigation shows the bottleneck is **not
collapsing** — it is being trained lopsidedly. The per-plane
normalization (softmax on Bhava, sigmoid on Kosha, etc.) prevents
zero-collapse structurally, and Stage 8 provides strong gradient
that keeps the Bhava slice active. The problem is that the 20D
governance portion of the state receives ~1% the gradient of the
12D identity portion. §1's VICReg proposal does not address this.

---

### 6.2 Fix 1 — Boost CG Lambda Weights (Zero Code, Config Only)

**Cost:** zero code change. Edit 7 lines in
`scripts/train_mistral_cg.sh:60–66`.

**Mechanism:** increase the CG auxiliary lambda weights so the
governance planes receive a meaningful fraction of the total gradient.
The current total (~0.046) is ~1.15% of the LM loss; the proposed
total (~0.13) is ~3.25% — a 3× boost that brings the governance
signal into the range where the optimizer can realistically move the
projector's weights on those planes.

**Current configuration** (`scripts/train_mistral_cg.sh:60–66`):

```bash
LAMBDA_ONT=0.01            # ontological structure loss
LAMBDA_KOSHA=0.01          # governance routing agreement
LAMBDA_BLISS=0.01          # coherence gating
LAMBDA_PLAUSIBILITY=0.005  # JEPA plausibility
LAMBDA_CSR=0.005           # CSR resonance
LAMBDA_VRITTI=0.005        # cognitive mode
LAMBDA_GUNA=0.005          # energetic quality
# Total ≈ 0.046
```

**Proposed configuration:**

```bash
LAMBDA_ONT=0.02            # 2× — direct projector gradient
LAMBDA_KOSHA=0.03          # 3× — strongest governance signal
LAMBDA_BLISS=0.03          # 3× — Guna-plane driver
LAMBDA_PLAUSIBILITY=0.015  # 3× — JEPA plausibility
LAMBDA_CSR=0.015           # 3× — CSR resonance
LAMBDA_VRITTI=0.015        # 3× — cognitive mode
LAMBDA_GUNA=0.015          # 3× — energetic quality
# Total ≈ 0.13
```

**Rationale for the multipliers:**

- `lambda_kosha_routing` and `lambda_bliss_token` get the largest
  boost (3×) because they directly train the Kosha and Guna planes
  respectively. These are the planes most starved by the current
  weights.
- `lambda_ont` gets a 2× boost (not 3×) because it trains the
  token projector (`_cg_projector`), not the state projector
  directly. Its gradient reaches the state projector only
  indirectly through shared embedding space. Boosting it too
  aggressively risks dominating the LM signal on the token path.
- The four primitive scorers (`plausibility`, `csr`, `vritti`,
  `guna`) all get 3× because they each produce input-dependent
  gradient through the `concat(hidden, state)` path in
  `PrimitiveAuxiliaryLosses`.

**Validation plan:**

1. Run 1000 steps of
   `./scripts/train_mistral_cg.sh --dataset wikitext2 --max-steps 1000`
   with the **current** lambdas. Record `lm_loss` at step 1000
   and all `cg_*` metrics.
2. Run 1000 steps with the **proposed** lambdas. Same seed, same
   data.
3. **Pass condition:**
   - `lm_loss` at step 1000 within ±2% of baseline. (Wider
     tolerance than §1's ±1% because we are deliberately
     increasing auxiliary loss contribution; a small LM increase
     may be acceptable if governance metrics improve.)
   - At least 3 of the 6 `cg_*` auxiliary losses decrease by
     ≥10% relative to baseline — indicating the governance
     planes are learning faster.
   - No NaN/Inf.
4. If the pass condition is met, update
   `scripts/train_mistral_cg.sh` with the proposed values.
5. If `lm_loss` regresses > 2%, try an intermediate boost (2×
   instead of 3×): total ~0.09 instead of ~0.13. If that also
   regresses, the LM path is sensitive to auxiliary gradient
   noise and a different approach (Fix 2: curriculum) is needed.

**Why this is the highest-ROI fix:** it is the only intervention in
this document that addresses the **measured root cause** (gradient
magnitude imbalance) with **zero code risk** (config change only).
Every other fix in this document either addresses a hypothetical
problem or requires code changes with integration risks. Fix 1
changes numbers that operators already tune — the only novel
contribution of §6 is the specific numbers and the gradient-flow
analysis that justifies them.

---

*6.3 (Fix 2: Lambda Curriculum) follows next.*
