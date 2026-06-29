# B0_RESULT — Synthetic Harness Calibration (measured)

> **SYNTHETIC CALIBRATION ONLY.** Generated from actual execution of `experiments/b0_synthetic_harness/run_b0.py`. **No semantics · no real-world data · no L2 `F` · no decoder · no PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically halted; D₀′ remains structural-only. This measures whether the probe/baseline/⊥ machinery detects PLANTED synthetic order signal and returns null on planted-null data — instrument readiness, not a finding about Symbol-U.

Probe: ridge OOF R²; order statistic = ΔR²(bag+bigram over bag) vs a within-sequence shuffle null (p95); detect iff ΔR²>null-p95 and ΔR²>0.01. REPEATS=20, K_shuffle=40, N_ref=300.

## 1. Decision confusion across regimes
| regime | order present | detect rate | label counts |
|---|---|---|---|
| null_bag (confound=1, effect=0) | False | 0.00 | CORRECT_NULL=20 |
| order (effect=1) | True | 1.00 | DETECTED_PLANTED_SIGNAL=20 |
| weak (effect=0.2) | True | 0.00 | AMBIGUOUS=19, FALSE_NEGATIVE=1 |
| confounded (confound=1.5,eff=0.4) | True | 0.50 | DETECTED_PLANTED_SIGNAL=10, FALSE_NEGATIVE=10 |
| pure_noise (effect=0) | False | 0.00 | CORRECT_NULL=20 |

## 2. Operating point (effect=0.5 for TPR; effect=0 for FPR)
- **TPR** (order present, effect=0.5): **1.00**
- **FNR**: **0.00**
- **FPR** (mean of bag-null and pure-noise): **0.00** (bag-null 0.00, pure-noise 0.00)
  - target FPR by construction ≈ 0.05 (1 - p95)

## 3. Calibration curve (detection rate vs effect size)
| effect | detect rate | median ΔR² |
|---|---|---|
| 0.00 | 0.00 | -0.1140 |
| 0.10 | 0.00 | -0.1041 |
| 0.20 | 0.00 | -0.0733 |
| 0.30 | 0.25 | -0.0311 |
| 0.50 | 1.00 | 0.0997 |
| 0.80 | 1.00 | 0.3194 |

- **Minimum detectable effect (detection rate ≥ 0.80): 0.50**

## 4. Sample-size sweep (effect=0.3)
| N | detect rate | median ΔR² |
|---|---|---|
| 100 | 0.05 | -0.2637 |
| 200 | 0.15 | -0.0628 |
| 400 | 0.50 | 0.0100 |
| 800 | 1.00 | 0.0430 |

## 5. Noise sweep (effect=0.5)
| noise | detect rate | median ΔR² |
|---|---|---|
| 0.5 | 1.00 | 0.4458 |
| 1.0 | 1.00 | 0.0997 |
| 2.0 | 0.00 | -0.0539 |
| 4.0 | 0.00 | -0.1003 |

## 6. Confounding sweep (effect=0.4)
| confound (bag weight) | detect rate | median ΔR² |
|---|---|---|
| 0.0 | 0.75 | 0.0292 |
| 1.0 | 0.70 | 0.0166 |
| 2.0 | 0.40 | 0.0069 |
| 4.0 | 0.00 | 0.0020 |

## 7. Probe power limit — HARD case (full non-commutative product)
- order_kind='product' (effect=1): detect rate **0.05**, median ΔR² -0.1228
- The linear bigram probe under-detects a pure non-commutative operator-product signal (it cannot linearly represent the full ordered product). Calibration of matched (bigram) order signal above does NOT extend to arbitrary non-commutative structure — a documented power limit for any future linear order probe.

## Interpretation (binding)
- Synthetic instrument calibration only; **no semantic validation, no real-world result, no PASS/FAIL/⊥ for Symbol-U**. A′ remains canonically halted; D₀′ remains structural-only.
- The harness detects matched planted order signal above an effect/sample/noise-dependent threshold and returns null on planted-null/noise data at the designed false-positive rate; it under-detects non-commutative-product signal a linear probe cannot represent.

> structure, not validated meaning.
