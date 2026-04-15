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

*Subsequent priorities (P0-2, P1-1, P1-2, P2-1, P2-2) will be appended to
this document as §2–§6.*
