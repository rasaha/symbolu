# §11 Ketu Observable Probe Report

- **Benchmark:** `truthfulqa`
- **Questions probed:** 100
- **Observables tested:** 4

## Verdict summary

| Observable | AUC | Classification | Mean(correct) | Mean(wrong) |
|---|---|---|---|---|
| `bcvf_total_cost` | 0.495 | **UNCORRELATED** | 6.2726 | 6.2383 |
| `bcvf_source_0_cost` | 0.502 | **UNCORRELATED** | 5.6046 | 5.6176 |
| `source_0_entropy` | 0.532 | **UNCORRELATED** | 2.3178 | 2.4299 |
| `source_disagreement_fraction` | 0.498 | **UNCORRELATED** | 0.9980 | 0.9971 |

## Per-observable detail

### `bcvf_total_cost`

- **AUC:** 0.495  (higher AUC = observable predicts correctness better)
- **Pearson r:** -0.010
- **Spearman ρ:** -0.007
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 6.2726
- **Mean scalar when wrong:** 6.2383
- **N datapoints:** 521 (from 100 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.495 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_source_0_cost`

- **AUC:** 0.502  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.005
- **Spearman ρ:** +0.002
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 5.6046
- **Mean scalar when wrong:** 5.6176
- **N datapoints:** 521 (from 100 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.502 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_0_entropy`

- **AUC:** 0.532  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.045
- **Spearman ρ:** +0.044
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 2.3178
- **Mean scalar when wrong:** 2.4299
- **N datapoints:** 521 (from 100 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.532 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_disagreement_fraction`

- **AUC:** 0.498  (higher AUC = observable predicts correctness better)
- **Pearson r:** -0.015
- **Spearman ρ:** -0.015
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.9980
- **Mean scalar when wrong:** 0.9971
- **N datapoints:** 521 (from 100 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.498 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.


## Discipline — what this report means

§11 Observable Discipline (per §10.V1's falsification lesson): before building a Rahu attractor on top of any Ketu observable, the observable must be probed on a held-out benchmark subset to confirm it is truth-correlated. The AUC bands used here:

- `AUC ≥ 0.60` → **TRUTH_CORRELATED** — worth a Rahu attractor.
- `0.45 ≤ AUC < 0.60` → **UNCORRELATED** — a Rahu built on this converges to conventional blend at best.
- `AUC < 0.45` → **ANTI_CORRELATED** — signal is present with the WRONG sign. A Rahu on this would actively hurt accuracy (V1's failure mode).
- `n<40` → **NULL** — too few datapoints; expand N.
