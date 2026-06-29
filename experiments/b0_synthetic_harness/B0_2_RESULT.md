# B0_2_RESULT — Operator Mismatch / Identifiability Calibration (measured)

> **SYNTHETIC CALIBRATION ONLY.** From actual execution of `run_b0_2.py`. **No semantics · no real data · no L2 `F` · no decoder · no PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically halted; D₀′ remains structural-only. Quantifies how operator-product probe power degrades as the probe family `{N_i}` departs from the true generative family `{M_i}`. All on the hard non-commutative product signal.

REPEATS=20, K=40, N=300. Detection = ΔR²(bag+order over bag) > shuffle-null p95 and > 0.01.

## 1. Probe-family regime comparison (product signal, effect=1, noise=1)
| probe family | detect rate | median ΔR² |
|---|---|---|
| exact (N=M) | 1.00 | 0.5070 |
| gauge (N=S M Sᵀ, s0'=S s0) | 1.00 | 0.5070 |
| perturb ε=0.2 | 1.00 | 0.4345 |
| random orthogonal | 0.00 | -0.0106 |
| abelian (commuting diag) | 0.00 | -0.0143 |
| baseline: bag | 0.00 | 0.0000 |
| baseline: bigram | 0.00 | -0.0821 |

## 2. Perturbation sweep  N_i = polar(M_i + ε·noise)
| ε | detect rate | median ΔR² |
|---|---|---|
| 0.00 | 1.00 | 0.5070 |
| 0.05 | 1.00 | 0.5022 |
| 0.10 | 1.00 | 0.4846 |
| 0.20 | 1.00 | 0.4345 |
| 0.40 | 0.90 | 0.2592 |
| 0.80 | 0.25 | -0.0106 |
| 1.50 | 0.00 | -0.0130 |

- **Mismatch threshold (power < 0.80 first at): ε = 0.80**

## 3. Partial inventory corruption  (fraction of N_i replaced by random)
| corruption frac | detect rate | median ΔR² |
|---|---|---|
| 0.0 | 1.00 | 0.5070 |
| 0.2 | 0.95 | 0.0922 |
| 0.4 | 0.25 | -0.0001 |
| 0.6 | 0.15 | -0.0102 |
| 0.8 | 0.10 | -0.0139 |
| 1.0 | 0.10 | -0.0089 |

- **Corruption threshold (power < 0.80 first at): frac = 0.4**

## Interpretation (binding)
- **Exact and gauge-equivalent probes detect equally** — the automaton gauge `N=S M Sᵀ`, `s0'=S s0` maps features to `S·(true features)`, an invertible linear map, so the linear probe is gauge-invariant (gauge-compatible features succeed, as expected).
- **Power degrades smoothly with perturbation ε** and with **partial corruption fraction**, with explicit thresholds above; **random** and **abelian** probes fail/weak, and **bag/bigram** baselines fail — confirming the B.0.1 identifiability caveat quantitatively: operator-awareness helps only with approximately-correct, non-abelian operators.
- **Abelian probe operators cannot detect non-commutative product signal** (their ordered product is count-only / order-blind) — a clean failure mode.
- Synthetic instrument calibration only; **no semantic validation, no real-world result, no PASS/FAIL/⊥ for Symbol-U.** A′ halted; D₀′ structural-only.

> structure, not validated meaning.
