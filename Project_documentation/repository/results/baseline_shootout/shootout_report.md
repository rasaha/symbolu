# Apples-to-apples Baseline Shootout

N = 10 seeds per cell  ·  4 arbitrators (BCVF, EKF, MajorityVote, Anchor) × 7 characterization families.

## Headline — failure families (attribution hit rate)

| family | Anchor | BCVF | EKF | MajorityVote |
|---|---:|---:|---:|---:|
| `accelerating` | 0.00 | 1.00 | 1.00 | 1.00 |
| `outlier` | 0.00 | 1.00 | 0.00 | 1.00 |
| `sensor_dropout` | 0.00 | 1.00 | 1.00 | 1.00 |

## Consensus XY error (median, m) — all families

| family | Anchor | BCVF | EKF | MajorityVote |
|---|---:|---:|---:|---:|
| `accelerating` | 0.000 | 0.486 | 0.073 | 0.017 |
| `baseline` | 0.000 | 0.000 | 0.000 | 0.000 |
| `constant_bias` | 0.000 | 0.167 | 0.167 | 0.167 |
| `linear_drift` | 0.000 | 0.041 | 0.041 | 0.041 |
| `noise_floor` | 0.012 | 0.007 | 0.007 | 0.007 |
| `outlier` | 4.043 | 0.446 | 3.930 | 0.013 |
| `sensor_dropout` | 4.043 | 0.256 | 3.930 | 3.440 |

## False attribution (median max-attribution on benign families)

| family | Anchor | BCVF | EKF | MajorityVote |
|---|---:|---:|---:|---:|
| `baseline` | 0.000 | 0.000 | 0.394 | 0.000 |
| `constant_bias` | 0.000 | 0.000 | 1.115 | 16.667 |
| `linear_drift` | 0.000 | 0.000 | 0.541 | 4.083 |
| `noise_floor` | 0.000 | 0.133 | 0.389 | 0.537 |

## Per-tick wall time (median µs)

| family | Anchor | BCVF | EKF | MajorityVote |
|---|---:|---:|---:|---:|
| `accelerating` | 0.0 | 3.7 | 69.3 | 28.4 |
| `baseline` | 0.0 | 3.9 | 70.8 | 27.4 |
| `constant_bias` | 0.0 | 3.7 | 71.0 | 27.3 |
| `linear_drift` | 0.0 | 3.6 | 69.0 | 28.6 |
| `noise_floor` | 0.0 | 3.8 | 69.6 | 28.6 |
| `outlier` | 0.0 | 3.7 | 56.2 | 30.3 |
| `sensor_dropout` | 0.0 | 3.6 | 55.8 | 28.3 |

## Reading the table

* **Failure families** (`accelerating`, `outlier`, `sensor_dropout`): hit rate = fraction of seeds where the arbitrator ranked the *injected* outlier predictor in the top half of attribution scores. 1.0 = perfect attribution; 0.0 = the arbitrator never identified the outlier.
* **Benign families** (`baseline`, `constant_bias`, `linear_drift`, `noise_floor`): false attribution = median max-across-predictors attribution score. Smaller is better; the Lemma-1 invariance says BCVF should produce ~0 here.
* **Anchor**: never assigns attribution (always returns zero). Always-trust-anchor's hit rate is therefore 0.0 by construction — it's the floor the other three must beat.
