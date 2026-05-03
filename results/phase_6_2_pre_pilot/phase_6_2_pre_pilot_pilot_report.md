# §6.2 Pilot Report

Adapter: `RealisticNoiseAdapter`
Scenes: 21  ·  Predictors per scene: 4

## Headline result — paired A0 vs A3 (forecast XY error)

- N paired: **21**
- A3 wins: **5**  ·  A0 wins: 0  ·  ties: 16
- Win rate: **1.000**  (95% Wilson CI: 0.566–1.000)
- One-sided sign-test p-value: **0.0312**

## Per-failure-class breakdown

| failure_type | N | A3 wins | A0 wins | win_rate | p-value | attribution_hit |
|---|---:|---:|---:|---:|---:|---:|
| camera_degradation | 5 | 5 | 0 | 1.000 | 0.0312 | 1.000 |
| constant_bias_sanity | 5 | 0 | 0 | 0.500 | 1.0000 | 0.000 |
| gps_multipath | 6 | 0 | 0 | 0.500 | 1.0000 | 0.000 |
| map_misalignment | 5 | 0 | 0 | 0.500 | 1.0000 | 0.000 |

## Lemma-1 negative control

- `constant_bias_sanity` max BCVF total observed in A3: **0.000000**
- Negative-control gate (PASS): BCVF must not fire on Lemma-1 benign scenes.

## Fleet summary highlights

- Total episodes: 21
- Total simulator steps: 8400
- Argmax-flips per step (mean): 0.0019
- Argmax-flips per step (p99): 0.0100
- Near-vetoes detected: 0
- V2 state flips detected: 0

## Scope caveats

- This pilot ran the dataset returned by the supplied adapter. Numerical results are valid for that adapter's data; external-validity claims (e.g., real automotive sensor data) require executing the same runner against an adapter that loads a real dataset.
- Mode A (open-loop forecast comparison) was used. Mode B (closed-loop simulator) is a follow-on per the pilot plan.
- N paired = number of scenes — small N inflates the sign-test p-value. The headline bar is win-rate Wilson-CI lower bound > 0.5; the strict §6.1 protocol requires N ≥ 21 with p < 0.05 on a responsive failure class for a positive result.
