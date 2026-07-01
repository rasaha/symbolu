# B0_1_RESULT — Operator-Aware Probe Calibration (measured)

> **SYNTHETIC CALIBRATION ONLY.** From actual execution of `run_b0_1.py`. **No semantics · no real data · no L2 `F` · no decoder · no PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically halted; D₀′ remains structural-only. Extends B.0 with an Option-A operator-product probe; measures whether it detects non-commutative product signal that bag/bigram miss.

Probes compared (all judged by ΔR² vs within-seq shuffle null, p95): **bag**, **bigram**, **operator_matched** (given the generative family), **operator_mismatched** (a different random family). REPEATS=20, K=40, N=300.

## 1. Detection on HARD non-commutative product signal (effect=1, noise=1)
| probe | detect rate | median ΔR² |
|---|---|---|
| bag | 0.00 | 0.0000 |
| bigram | 0.05 | -0.1032 |
| operator_matched | 1.00 | 0.5139 |
| operator_mismatched | 0.15 | -0.0118 |

## 2. False-positive rate (no order signal present)
| probe | bag-null (conf=1,eff=0) | pure-noise (eff=0) |
|---|---|---|
| bag | 0.00 | 0.00 |
| bigram | 0.00 | 0.00 |
| operator_matched | 0.00 | 0.05 |
| operator_mismatched | 0.00 | 0.05 |

## 3. Operator-matched calibration curve (product signal) -> MDE
| effect | detect rate | median ΔR² |
|---|---|---|
| 0.00 | 0.05 | -0.0122 |
| 0.10 | 0.25 | 0.0012 |
| 0.20 | 0.70 | 0.0346 |
| 0.30 | 0.90 | 0.0806 |
| 0.50 | 1.00 | 0.2051 |
| 0.80 | 1.00 | 0.4014 |

- **Minimum detectable effect (operator-matched, rate ≥ 0.80): 0.30**

## 4. Operator-matched noise robustness (product, effect=1)
| noise | detect rate | median ΔR² |
|---|---|---|
| 0.5 | 1.00 | 0.8172 |
| 1.0 | 1.00 | 0.5139 |
| 2.0 | 1.00 | 0.2051 |
| 4.0 | 0.85 | 0.0559 |

## 5. Operator-matched confound robustness (product, effect=0.6)
| confound | detect rate | median ΔR² |
|---|---|---|
| 0.0 | 1.00 | 0.2721 |
| 1.0 | 1.00 | 0.1589 |
| 2.0 | 1.00 | 0.0700 |
| 4.0 | 1.00 | 0.0216 |

## 6. Shuffle destroys order signal (operator-matched)
- intact sequences: detected=True, ΔR²=0.5471
- order-shuffled (y kept): detected=False, ΔR²=0.0987

## Interpretation (binding)
- **Operator-aware (matched) probe lifts the B.0 power limit:** it detects the non-commutative product signal that **bag (~0)** and **bigram (~0.05 in B.0)** miss, while keeping FPR controlled, collapsing under shuffle, and degrading sensibly with noise/confounding.
- **Identifiability nuance:** the **mismatched** operator probe (wrong family) is much weaker than matched — an operator-aware probe needs approximately-correct operators; operator-awareness alone is not sufficient. (Forward-looking instrument design note; **no semantic implication**.)
- Synthetic instrument calibration only; **no semantic validation, no real-world result, no PASS/FAIL/⊥ for Symbol-U.** A′ halted; D₀′ structural-only.

> structure, not validated meaning.

## Reproducibility metadata

| field | value |
|---|---|
| git_hash | bae437cb4dd7e2bdd0f5c2b79c75f50da06919cf |
| python | 3.11.15 |
| platform | Linux-6.18.5-x86_64-with-glibc2.39 |
| numpy | 2.4.6 |
| seed | 2000 |
| runtime_s | 35.327 |

Config:
```json
{
  "version": 1,
  "repeats": 20,
  "k_shuffle": 40,
  "n_ref": 300,
  "base_seed": 1000,
  "min_delta_r2": 0.01,
  "shuffle_pctl": 95.0,
  "n_units": 5,
  "op_dim": 3,
  "len_min": 3,
  "len_max": 6,
  "effect_grid": [
    0.0,
    0.1,
    0.2,
    0.3,
    0.5,
    0.8
  ],
  "sample_grid": [
    100,
    200,
    400,
    800
  ],
  "noise_grid": [
    0.5,
    1.0,
    2.0,
    4.0
  ],
  "confound_grid": [
    0.0,
    1.0,
    2.0,
    4.0
  ]
}
```

| output | sha256 |
|---|---|
| report_body | 5b585960995c24df88d97c22776140ee3034da093b2ed65cdeeadd096e932bff |
