# §11 Ketu Observable Probe Report

- **Benchmark:** `speculative-mock`
- **Questions probed:** 48
- **Observables tested:** 11

## Verdict summary

| Observable | AUC | Classification | Mean(correct) | Mean(wrong) |
|---|---|---|---|---|
| `bcvf_total_cost` | 0.500 | **UNCORRELATED** | 0.0565 | 0.0565 |
| `bcvf_source_0_cost` | 0.500 | **UNCORRELATED** | 0.0565 | 0.0565 |
| `source_0_entropy` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `source_disagreement_fraction` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `bcvf_per_step_max` | 0.500 | **UNCORRELATED** | 0.0565 | 0.0565 |
| `bcvf_source_0_per_step_max` | 0.500 | **UNCORRELATED** | 0.0565 | 0.0565 |
| `coherence_anchored_bcvf` | 1.000 | **TRUTH_CORRELATED** | 0.9501 | 0.0000 |
| `coherence_anchored_bcvf_per_step` | 0.963 | **TRUTH_CORRELATED** | 0.0000 | 0.0000 |
| `uncertainty_gated_bcvf_per_step_max` | 0.500 | **UNCORRELATED** | 0.0000 | 0.0000 |
| `layer_instability_max` | 0.500 | **UNCORRELATED** | 0.0102 | 0.0102 |
| `coherence_anchored_layer_bcvf_per_step` | 0.976 | **TRUTH_CORRELATED** | 0.0000 | 0.0000 |

## Per-observable detail

### `bcvf_total_cost`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0565
- **Mean scalar when wrong:** 0.0565
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_source_0_cost`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0565
- **Mean scalar when wrong:** 0.0565
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_0_entropy`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `source_disagreement_fraction`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0565
- **Mean scalar when wrong:** 0.0565
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `bcvf_source_0_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0565
- **Mean scalar when wrong:** 0.0565
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `coherence_anchored_bcvf`

- **AUC:** 1.000  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.997
- **Spearman ρ:** +0.817
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.9501
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`TRUTH_CORRELATED`**

**Recommendation:** AUC=1.000 — observable has signal. Worth building a Rahu attractor around. Proceed to bounded benchmark.

### `coherence_anchored_bcvf_per_step`

- **AUC:** 0.963  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.283
- **Spearman ρ:** +0.755
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`TRUTH_CORRELATED`**

**Recommendation:** AUC=0.963 — observable has signal. Worth building a Rahu attractor around. Proceed to bounded benchmark.

### `uncertainty_gated_bcvf_per_step_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `layer_instability_max`

- **AUC:** 0.500  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.000
- **Spearman ρ:** +0.000
- **Polarity:** higher = more suspicious
- **Mean scalar when correct:** 0.0102
- **Mean scalar when wrong:** 0.0102
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`UNCORRELATED`**

**Recommendation:** AUC=0.500 near 0.5 — observable is close to noise. A Rahu built on this converges to conventional-blend at best. Not worth the inference cost.

### `coherence_anchored_layer_bcvf_per_step`

- **AUC:** 0.976  (higher AUC = observable predicts correctness better)
- **Pearson r:** +0.284
- **Spearman ρ:** +0.796
- **Polarity:** higher = more trusted
- **Mean scalar when correct:** 0.0000
- **Mean scalar when wrong:** 0.0000
- **N datapoints:** 144 (from 48 questions)
- **Classification:** **`TRUTH_CORRELATED`**

**Recommendation:** AUC=0.976 — observable has signal. Worth building a Rahu attractor around. Proceed to bounded benchmark.


## Discipline — what this report means

§11 Observable Discipline (per §10.V1's falsification lesson): before building a Rahu attractor on top of any Ketu observable, the observable must be probed on a held-out benchmark subset to confirm it is truth-correlated. The AUC bands used here:

- `AUC ≥ 0.60` → **TRUTH_CORRELATED** — worth a Rahu attractor.
- `0.45 ≤ AUC < 0.60` → **UNCORRELATED** — a Rahu built on this converges to conventional blend at best.
- `AUC < 0.45` → **ANTI_CORRELATED** — signal is present with the WRONG sign. A Rahu on this would actively hurt accuracy (V1's failure mode).
- `n<40` → **NULL** — too few datapoints; expand N.

