# Phase 1.5 Summary — §3 BCVF LLM Characterization

**Classification:** `PASS`

**Winner tuple:** `T=0.1, beta=200.0, delta=0.5`


## Grid counts

- Primary: 87 cells (87 pass)
- Sensitivity: 1701 cells (1701 pass)
- Ablation: 45 cells
- Full-V spot check: 21 cells (21 pass)


## §3.4.4 Ablation — empirical Lemma-1 confirmation

| cost_order | linear_drift pass/total |
|---|---|
| ZEROTH | 0/15 |
| FIRST | 0/15 |
| SECOND | 15/15 |

**Expected per §2.8.3/§2.6.4:** `SECOND` should pass all cells (Lemma-1-respecting); `FIRST` should fail on `drift_rate > 0` cells (confirming the Lemma-1 violation warning is empirical); `ZEROTH` fails when the gate is open.


## §3.4.2 Primary grid — per-family pass rate at V1 defaults

| Family | Pass rate | Notes |
|---|---|---|
| baseline | 3/3 = 100.00% | — |
| constant_bias | 18/18 = 100.00% | — |
| linear_drift | 15/15 = 100.00% | — |
| accelerating | 18/18 = 100.00% | hit_rate=1.00, margin_mean=2.00 |
| noise_floor | 15/15 = 100.00% | — |
| outlier | 3/3 = 100.00% | hit_rate=1.00, margin_mean=2.00 |
| eos_truncation | 15/15 = 100.00% | hit_rate=1.00, margin_mean=2.00 |

## §3.4.5 Full-V spot check (winner at V=32000)

| Family | Pass rate |
|---|---|
| baseline | 3/3 = 100.00% |
| constant_bias | 3/3 = 100.00% |
| linear_drift | 3/3 = 100.00% |
| accelerating | 3/3 = 100.00% |
| noise_floor | 3/3 = 100.00% |
| outlier | 3/3 = 100.00% |
| eos_truncation | 3/3 = 100.00% |


## §3.9.2 Tiebreaker candidates

27 configurations pass the sensitivity grid. Top 5 by Euclidean distance to V1 defaults:

| rank | T | beta | delta |
|---|---|---|---|
| 1 | 0.1 | 200.0 | 0.5 |
| 2 | 0.05 | 200.0 | 0.5 |
| 3 | 0.1 | 200.0 | 0.25 |
| 4 | 0.1 | 100.0 | 0.5 |
| 5 | 0.05 | 200.0 | 0.25 |


## Recommendation

`UNLOCK §4 AT (T=0.1, β=200.0, δ=0.5)` — §3.4.1–§3.4.5 all green, §2.6 invariances empirically confirmed via §3.4.4 ablation, §3.5 thresholds met, §3.6 alignment met.
