# D1 — Findings template, R1/R2 selection, and the §4 promotion test

D1 is a **localization** diagnostic. This file (1) records the verdict once the GPU run
produces it, and (2) pre-commits the *minimal* training change each verdict selects and
the held-out promotion test that gates CG's return to product positioning. Pre-writing
the R-plan keeps the decision rule honest: we do not get to redesign the fix after
seeing which rung dropped.

> **Status before the run:** not executed on a real checkpoint here. D1 needs a GPU +
> trained CG state-dict (`make signal-gov-d1`). The torch-free `make signal-gov-d1-mock`
> validates the pipeline only (the mock is LABEL-BLIND and yields `NO_CEILING`). Fill the
> table below from `runs/d1/d1_result.json` after the live run.

## Verdict (fill from the live run)

| Rung | Signal | AUROC (fooled subset) |
|---|---|---|
| a | raw predictive entropy [ceiling] | `____` (expect ≈ 0.857) |
| b | linear probe on final hidden | `____` |
| c | linear probe on 32-D state | `____` |
| d | entropy_from_sovereign_state | `____` (prior ≈ 0.457) |
| e | vritti / coherence / jepa / internal_risk | `____` |

**Verdict:** `____` (`LOCALIZE_PROJECTION` | `LOCALIZE_ENTROPY_DEFINITION` |
`LOCALIZE_HIDDEN_NONLINEAR` | `SIGNAL_SURVIVES_TO_STATE`)

The two expected outcomes and what each *means*:

- **`LOCALIZE_PROJECTION`** (b ≈ 0.85, c ≪ 0.85): the `SovereignStateProjector`'s
  4096→32 semantic-categorical bottleneck (Bhava-12 softmax + Vritti-5 softmax + Guna-6
  sigmoid + reserved), trained on LM + CG-internal losses that *never reward preserving
  predictive uncertainty*, compresses the signal away. Consistent with the step-500
  mode-collapse diagnostics (Bhava one-hot).
- **`LOCALIZE_ENTROPY_DEFINITION`** (c ≈ 0.85, d ≪ 0.85): the information *survives* the
  projection (the 32-D state is linearly separable on the fooled subset) but
  `entropy_from_sovereign_state` measures the **spread of the semantic state** (a Guna
  profile), which is a *different object* from next-token predictive uncertainty. "CG
  entropy" was never predictive entropy.

---

## R1/R2 — the minimal training change (selected by the verdict)

Sequencing is **R1 + R2 first** (preserve the working signal *and* train
discriminativeness), then re-run the falsification conditionally before anything else.

### R1 — Raw-entropy-preservation (auxiliary loss) — *cheapest, highest-value*

Add a small read-out head `h: state(32) → ℝ` (or supervise one reserved state dim) and
an auxiliary loss that **regresses the true next-token predictive entropy** computed
from the frozen backbone's own logits at each position:

```
H_pred = predictive_entropy(backbone_logits)          # the label, free from the same forward
L_R1   = MSE( h(state), stop_grad(H_pred) )            # or Huber; normalized to [0,1]
L_total = L_LM + L_CG_internal + λ1 · L_R1
```

- **If `LOCALIZE_PROJECTION`:** R1 *forces the signal through the bottleneck* — the
  projector must keep a predictive-uncertainty-carrying direction to minimise `L_R1`.
  Pair with **R6** (anti-collapse: entropy reg on Bhava, earlier gate unfreeze, higher
  CG-loss weight) so the regularised state isn't just preserving noise, and consider
  **D3** (re-fit probes at 32 vs 64 vs 128-D; widen only if 128 ≫ 32).
- **If `LOCALIZE_ENTROPY_DEFINITION`:** R1 *replaces* the hand-defined state-spread
  entropy as the governance read-out — at inference, use `h(state)` (a learned predictive
  entropy) rather than `entropy_from_sovereign_state`. The projector is left as-is.

R1 alone, if it succeeds, would mostly **re-derive the cheap signal through a 32-D
detour** — which §4 explicitly says is *not* promotion. R1 is necessary (don't lose the
signal) but not sufficient. Hence R2.

### R2 — Contrastive safe-vs-confident-unsafe — *the key objective*

Using the surface-matched twins, a contrastive/triplet loss that pushes the state (and
the governance read-outs) of **unsafe twins away from their safe twins**:

```
L_R2 = max(0, m − d(state_unsafe_twin, state_safe_twin)) + pull_within_class
L_total += λ2 · L_R2
```

This supplies the missing **governance-discriminative** axis — the state is currently
trained only to be LM-coherent, never to separate the safe/unsafe governance axis. R2 is
what lets CG catch what raw entropy *misses* (a hidden-state fabrication/injection
signature), the only thing that satisfies §4's "marginal value over raw entropy".

### Not yet

R3 (fabrication/hallucinated-permission supervision), R4 (escalation calibration), R5
(vritti: supervise or remove — it is dead in every run), R6 (anti-collapse, only
alongside R1/R2). Revisit after R1+R2 and a conditional re-falsification, per the plan.

---

## §4 — The promotion gate (held-out, powered)

CG re-enters product positioning **iff**, on a **held-out, powered (N ≥ 150), paired
confident-unsafe benchmark**, the CG-derived governance signal **beats**

> risk taxonomy + verbalized confidence + **raw next-token entropy**

on the **fooled-subset conditional AUROC**, with **all three** holding:

1. **DeLong p < 0.05, replicated** on a second independent draw (use `delong.py`);
2. **Marginal value over raw entropy specifically** — CG must catch what predictive
   entropy *misses*, not re-derive it through a 32-D detour (R1-only does not qualify);
3. **Operational lift** — higher `catch@budget` at equal-or-lower `over_block_rate`, not
   just AUROC.

Concretely, the promotion run is the existing falsification harness on a **held-out**
draw, comparing C3+raw-entropy vs C4(CG) and reporting the DeLong test + catch@budget at
equal over-block. Until all three hold, `SignalConfig.enable_cg_state_signals` stays
`False` and CG stays research-only. The product ships raw entropy + the governance
control plane regardless (plan §6).
