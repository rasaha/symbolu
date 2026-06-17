# CG Pilot Report — <DATE> (TEMPLATE)

Fill from `runs/cg_pilot/results.json`, `metrics.csv`, `signal_importance.csv`. This is a
**directional, underpowered pilot**, not a confirmatory result — keep the disclaimers.

- **Checkpoint:** `<CG_CHECKPOINT>`  ·  **CG head trained?** `<yes/no/unknown>`
- **Mode:** `real_cg`  ·  **Quantize:** `<4bit|8bit|none>`  ·  **Provenance:** `<meta.feature_provenance>`
- **Scenarios:** `pilot_30_50.jsonl`  ·  **N = <n>** (unsafe `<pos>`, safe `<neg>`)
- **Category balance:** injection `<x>` · destructive `<y>` · ambiguous `<z>`
- **Seeds / re-runs:** `<list>`  ·  **GPU:** `<type>`

## Ablation (the headline table)

| Config | AUROC | AUROC 95% CI | AUPRC | catch@10% | over-block@10% |
|---|---|---|---|---|---|
| C1 approval only | <> | [<>, <>] | <> | <> | <> |
| C2 + risk taxonomy | <> | [<>, <>] | <> | <> | <> |
| C3 + text confidence | <> | [<>, <>] | <> | <> | <> |
| **C4 + CG internal signals** | <> | [<>, <>] | <> | <> | <> |

- Ablation ordering C4 ≥ C3 ≥ C2 ≥ C1: `<PASS/FAIL>`
- **C4 − C3 AUROC gap:** `<Δ>`  ·  catch@10% gain (C4−C3): `<Δ pts>`

## C4 vs C3 (DeLong)

- AUROC(C4)=`<>`, AUROC(C3)=`<>`, Δ=`<>`, DeLong p=`<p or nan>`

## Signal ablation (standalone AUROC, higher = riskier)

| Signal | Standalone AUROC |
|---|---|
| entropy | <> |
| coherence (inv) | <> |
| vritti_risk | <> |
| jepa_disagreement | <> |
| risk_norm | <> |
| text_confidence (inv) | <> |

## Power & significance (REQUIRED — keep)

> ⚠️ **N=`<n>` is small; this pilot is UNDERPOWERED.** Bootstrap CIs are wide and the DeLong
> test cannot confirm an effect at this N. A non-significant/borderline p is NOT evidence of
> no effect; a significant one needs replication at the 400–600 full run. <If the CG head is
> untrained, add: the 32-D state is not meaningful — this run validates plumbing, not signal
> quality.>

## Read (directional only)

- Direction: `<encouraging / inconclusive / discouraging>` per CG_PILOT_RUNBOOK.md §8.
- Next: `<proceed to powered full run / expand N / investigate checkpoint>`.

## What this does NOT claim

- Not evidence that model-internal signals improve governance (underpowered pilot).
- Not a benchmark result; the injection third may be fixture-derived.
- No confirmatory p-value at this N.
