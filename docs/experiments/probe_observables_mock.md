# §11 Ketu Observable Probe Report

- **Benchmark:** `mock`
- **Questions probed:** 48
- **Observables tested:** 11

## Verdict summary

| Observable | AUC | Classification | Mean(correct) | Mean(wrong) |
|---|---|---|---|---|
| `bcvf_total_cost` | 0.500 | **UNCORRELATED** | 2.0000 | 2.0000 |
| `bcvf_source_0_cost` | 0.500 | **UNCORRELATED** | 2.0000 | 2.0000 |
| `source_0_entropy` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `source_disagreement_fraction` | 0.500 | **UNCORRELATED** | 0.6000 | 0.6000 |
| `bcvf_per_step_max` | 0.500 | **UNCORRELATED** | 2.0000 | 2.0000 |
| `bcvf_source_0_per_step_max` | 0.500 | **UNCORRELATED** | 2.0000 | 2.0000 |
| `coherence_anchored_bcvf` | 0.333 | **ANTI_CORRELATED** | 0.3333 | 0.3810 |
| `coherence_anchored_bcvf_per_step` | 0.333 | **ANTI_CORRELATED** | 0.3333 | 0.3810 |
| `uncertainty_gated_bcvf_per_step_max` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `layer_instability_max` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `coherence_anchored_layer_bcvf_per_step` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |

## Per-observable detail

### `bcvf_total_cost`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 2.0000
- **Mean scalar when wrong:** 2.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_source_0_cost`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 2.0000
- **Mean scalar when wrong:** 2.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_0_entropy`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_disagreement_fraction`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.6000
- **Mean scalar when wrong:** 0.6000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 2.0000
- **Mean scalar when wrong:** 2.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_source_0_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 2.0000
- **Mean scalar when wrong:** 2.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `coherence_anchored_bcvf`

- **AUC:** 0.333  (higher AUC = observable predicts correctness better)
- **Pearson r:** -0.052
- **Spearman ρ:** -0.301
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.3333
- **Mean scalar when wrong:** 0.3810
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`ANTI_CORRELATED`**

**Recommendation:** AUC=0.333 < 0.45 — observable has signal with the WRONG sign. A conventional trust-shaped attractor on this would ACTIVELY HURT accuracy. Options: flip the observable's sign, reject it, or verify with a larger N.

### `coherence_anchored_bcvf_per_step`

- **AUC:** 0.333  (higher AUC = observable predicts correctness better)
- **Pearson r:** -0.052
- **Spearman ρ:** -0.301
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.3333
- **Mean scalar when wrong:** 0.3810
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`ANTI_CORRELATED`**

**Recommendation:** AUC=0.333 < 0.45 — observable has signal with the WRONG sign. A conventional trust-shaped attractor on this would ACTIVELY HURT accuracy. Options: flip the observable's sign, reject it, or verify with a larger N.

### `uncertainty_gated_bcvf_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `layer_instability_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `coherence_anchored_layer_bcvf_per_step`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 96 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.


## Discipline — what this report means

§11 Observable Discipline (per §10.V1's falsification lesson): before building a Rahu attractor on top of any Ketu observable, the observable must be probed on a held-out benchmark subset to confirm it is truth-correlated. The AUC bands used here:

- `AUC ≥ 0.60` → **TRUTH_CORRELATED** — worth a Rahu attractor.
- `0.45 ≤ AUC < 0.60` → **UNCORRELATED** — a Rahu built on this converges to conventional blend at best.
- `AUC < 0.45` → **ANTI_CORRELATED** — signal is present with the WRONG sign. A Rahu on this would actively hurt accuracy (V1's failure mode).
- `n<40` → **NULL** — too few datapoints; expand N.

