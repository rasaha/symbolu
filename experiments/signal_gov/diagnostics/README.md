# Diagnostic D1 — Signal-Survival Ladder

The **decisive** diagnostic from `AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md` §2. A
**read-only** probe study that localizes *where* the predictive-uncertainty signal —
which works at the logit level (raw next-token entropy AUROC ≈ **0.857** on the fooled
subset) — is destroyed on the way to the 32-D "CG entropy" (AUROC ≈ **0.46**,
anti-predictive). It **retrains nothing**, touches **no product path**, and makes
**no success claim**. Its only output is a *localization verdict* that selects R1/R2.

## What it does

For each scenario in the fabrication probe set (`falsification/scenarios.py`, 10
surface-matched safe/unsafe twins) it runs **one** forward pass through the CG wrapper
and caches:

- `last_token_logits` → **raw predictive entropy** (rung a, the ceiling),
- `all_layer_hidden` (last token, every layer) → **final hidden** (rung b) + D2 reuse,
- `state32` → the **32-D sovereign state** (rungs c, d, e).

Then, on the **fooled subset** (verbalized confidence ≥ τ, where the text baseline is
useless by construction), it reports AUROC for:

| Rung | Signal | Instrument |
|---|---|---|
| **a** | raw next-token predictive entropy | `features.predictive_entropy` — the **ceiling** |
| **b** | linear probe on the **final hidden state** | group-LOO ridge probe (`probes.py`) |
| **c** | linear probe on the **32-D state** | group-LOO ridge probe |
| **d** | `entropy_from_sovereign_state` | the bridge (state-spread "CG entropy") |
| **e** | vritti / coherence / jepa / internal_risk | the bridge governance read-outs |

## How the probe stays honest (small N, huge D)

A linear classifier on `D=4096 ≫ N≈12` separates any labelling perfectly **in-sample**
(AUROC 1.0, meaningless). So the probe (`probes.py`) reports **out-of-fold** scores
only, via **leave-one-twin-pair-out** cross-validation (both surface-matched twins are
held out together, so the probe can't memorise the pair). It is L2-regularised
least-squares (ridge) in dual/linear-kernel form — O(N³), no convergence knob — and the
headline AUROC is the **median over a fixed α grid** (per-α values are printed, so the
verdict is visibly not α-cherry-picked).

## The localization verdict (pre-registered)

Walk the rungs in pipeline order; the rung where AUROC collapses toward chance is the
fault (thresholds in `ladder.py`: `ceiling_floor=0.65`, `chance_band=0.62`,
`drop_delta=0.12`):

- **a→b drop** (`LOCALIZE_HIDDEN_NONLINEAR`): the final hidden doesn't *linearly* carry
  it → run **D2** (layerwise) before retraining; point the projector at the right depth.
- **b→c drop** (`LOCALIZE_PROJECTION`): the hidden recovers it but the **4096→32
  projection** does not → the bottleneck is the fault. **Selects R1 + R2** (+ R6/D3).
- **c→d drop** (`LOCALIZE_ENTROPY_DEFINITION`): the **32-D state** recovers it but
  `entropy_from_sovereign_state` does not → the **read-out/metric** is wrong (state-spread
  entropy ≠ predictive entropy). **Selects R1** (learned read-out regressing predictive
  entropy) **+ R2**. The projector itself is *not* implicated.
- **no collapse** (`SIGNAL_SURVIVES_TO_STATE`): unexpected vs priors → no retrain implied
  by D1; fit weights and run the §4 powered replication. Not a success claim.

`LOCALIZE_PROJECTION` vs `LOCALIZE_ENTROPY_DEFINITION` is exactly the fork the plan calls
for — *projection* (fix with training/dimension) vs *entropy definition* (fix the
read-out). Both point at R1+R2; the emphasis differs (see `D1_FINDINGS.md`).

## Run it

```bash
make signal-gov-d1-test     # torch-free: probe honesty + every verdict branch + mock cache
make signal-gov-d1-mock     # torch-free plumbing run (LABEL-BLIND mock; no result)
# GPU + trained CG head — the real localization:
export CG_STATE_DICT=/workspace/checkpoints_unified/final_model.pt
make signal-gov-d1          # -> runs/d1/d1_report.md (the verdict), d1_result.json, d1_cache.npz
# offline replay of a saved forward pass (metric-identical, no model):
python -m experiments.signal_gov.diagnostics.run --from-cache runs/d1/d1_cache.npz --out runs/d1_replay
```

`d1_cache.npz` is reusable for D2–D6 (it already stores every layer's last-token hidden).

## Offline follow-ups on the D1 cache (no GPU, no torch, no model)

These consume `runs/d1/d1_cache.npz` and add **no** forward pass — they re-read what D1
already cached. Run them after `make signal-gov-d1` (set `D1_CACHE` if the npz is
elsewhere):

| Diagnostic | What it reads | What it adds over D1 | Command |
|---|---|---|---|
| **D4 — vritti / component collapse** (`d4_vritti.py`) | cached 32-D `state32` | per-component distribution entropy (Bhava one-hot vs Vritti uniform), twin separation vs spread, best single-dim AUROC | `make signal-gov-d4` |
| **D5 — entropy-definition correlation** (`d5_entropy_def.py`) | cached `raw_entropy`, `cg_entropy` | Pearson/Spearman of predictive entropy vs `entropy_from_sovereign_state` → corroborates D1's (c)→(d) rung (near-zero ⇒ wrong object, not undertrained) | `make signal-gov-d5` |

```bash
make signal-gov-d1                      # GPU: produces runs/d1/d1_cache.npz
make signal-gov-d4                      # CPU offline -> runs/d4/d4_report.md
make signal-gov-d5                      # CPU offline -> runs/d5/d5_report.md
make signal-gov-diag-test               # torch-free tests for D1 + D4 + D5
```

D4 explains *why* a D1 rung-(e) read-out is dead (collapsed vs diluted vs twin-blind);
D5 sharpens *whether* a low CG-entropy AUROC is the metric (different object) or upstream
(projection). Neither retrains anything or ranks CG against a baseline.

## Isolation

This subpackage **imports** `Scenario`, `oracle`, `features`, `metrics`,
`cg_checkpoint`, and the fabrication scenarios, but **modifies none of them** and is
wired into **no** product path. `enable_cg_state_signals` stays `False` regardless of
what D1 finds — only the §4 promotion gate (see `D1_FINDINGS.md`) can change that.
