# §6.6a Architectural Decision Gate — Dynamic Predictor Exclusion

**Verdict: REJECTED.** V1 stays the V2 default. §6.1 runs under V1 architecture.

## Setup

- **Scenario:** `S3_map_error_accel`, M = 4 SE(2) predictors, M4 = failing anchor
- **Seeds:** 72–92 (N = 21 paired, matches V1 validation seed set)
- **V1 config (control):** T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor pairing
- **Exclusion config (treatment):** V1 + `exclusion_enabled=True`, `r=1.5`, `T_exclude=20` (2 s), `T_reinstate=20`

Implementation landed at commit `c3a6a0c`. All 8 invariant tests pass; 192 total tests
in the autonomy suite pass (excluding 2 pre-existing environment-specific timing tests).

## Results summary

| Variant | Cat | Cat % | Rescues vs A0 | Losses vs A0 | Mean \|y\| | Std \|y\| | Sign test p |
|---|---|---|---|---|---|---|---|
| A0 baseline | 5 | 23.8 % | — | — | 4.305 | 8.006 | — |
| V1 | 3 | 14.3 % | 3 | 1 | 1.786 | 5.761 | **0.0072** |
| Exclusion | 3 | 14.3 % | 3 | 1 | 1.790 | 4.842 | **0.1892** |

## Promotion-gate evaluation (all 6 conditions required)

| # | Condition | V1 | Exclusion | Status |
|---|---|---|---|---|
| 1 | Sign test p ≤ V1's 0.0072 | 0.0072 | **0.1892** | ❌ **FAIL** |
| 2 | Catastrophe count ≤ V1's 3/21 | 3 | 3 | ✅ pass |
| 3 | Mean \|y\| ≤ V1's 1.79 + SE (1.26) | 1.786 | 1.790 | ✅ pass |
| 4 | Std \|y\| ≤ V1's 5.76 + SE (0.91) | 5.76 | 4.84 | ✅ pass (tighter) |
| 5 | A0 rescue set {72, 75, 78, 82, 85} all <2 m | seeds 78, 82 at 5.66 / 4.24 under V1; exclusion increased both | seeds 78, 82 at 7.79 / 6.47 (worse than V1) | ❌ **FAIL** |
| 6 | No new catastrophes on V1-rescued seeds | — | seed 73: V1 0.08 → Exclusion **20.80** | ❌ **FAIL** |

Any single condition regressing rejects exclusion under the strict multi-metric gate.

## Seed-by-seed (seeds 72-92)

| Seed | A0 | V1 | Exclusion | Δ vs V1 | Notes |
|---|---|---|---|---|---|
| 72 | 19.18 | 0.05 | 0.09 | +0.04 | rescue-vs-A0 |
| 73 | 0.06 | 0.08 | **20.80** | +20.72 | **LOST-vs-A0, BROKE-vs-V1** |
| 74 | 0.05 | 0.05 | 0.10 | +0.05 | — |
| 75 | 21.71 | 0.31 | 0.24 | −0.07 | rescue-vs-A0 |
| 76 | 0.05 | 0.00 | 0.00 | +0.00 | — |
| 77 | 0.08 | 0.04 | 0.07 | +0.04 | — |
| 78 | 11.56 | 5.66 | 7.79 | +2.13 | both-fail; exclusion worse |
| 79 | 0.10 | 0.05 | 0.01 | −0.03 | — |
| 80 | 0.12 | 0.14 | 0.11 | −0.03 | — |
| 81 | 0.03 | 26.09 | **0.04** | −26.05 | **fixed-V1** |
| 82 | 22.45 | 4.24 | 6.47 | +2.23 | both-fail; exclusion worse |
| 83 | 0.03 | 0.21 | 0.03 | −0.18 | — |
| 84 | 0.18 | 0.05 | 0.02 | −0.04 | — |
| 85 | 13.93 | 0.18 | 0.98 | +0.80 | rescue-vs-A0 |
| 86–92 | all < 0.4 | all < 0.4 | all < 0.4 | small | — |

## Interpretation

Exclusion **rotates the catastrophe pattern** — it fixes V1's seed-81 regression (26.09 m
→ 0.04 m) but introduces a new catastrophe at seed 73 (0.08 m → 20.80 m) and makes
seeds 78 and 82 worse than V1 without pushing them below the 2 m threshold.

Net catastrophe count is unchanged at 3/21; distribution is slightly tighter (std 4.84
vs 5.76); but the sign-test significance is erased because per-seed regressions roughly
cancel per-seed improvements at the small-magnitude level.

This is consistent with the §6.6 deep-dive finding that the catastrophe floor on
`S3_map_error_accel` is **scenario-structural at the tiny-weight-perturbation →
large-outcome-divergence level**, not an architectural fix away. Trust-weight-shaping
mechanisms rearrange which seeds fail but do not reduce the count.

## Decision

- **V2 default: unchanged.** V1 (T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor
  pairing, `exclusion_enabled=False`) remains the validated configuration.
- **§6.1 multi-scenario validation runs under V1**, not exclusion.
- **Exclusion implementation stays in the codebase** behind the `exclusion_enabled=False`
  flag. Invariant tests stay in CI. Available for §6.6b reopens if §6.1 later reveals
  scenarios where exclusion would be worth retrying per-scenario.

## Artifacts

- Implementation: `symbolu_robotics/bcvf_autonomous/mppi_planner.py`
  (`set_exclusion`, `_exclusion_*` state, exclusion block in `_rollout_all`)
- Tests: `symbolu_robotics/bcvf_autonomous/tests/test_mppi.py::test_exclusion_*` (8 tests)
- Raw runs: `/tmp/bcvf_66a_exclusion_n21/` (A0 copied from V1; A3 fresh at exclusion
  config). Evaluation script inline in the §6.6a commit diff.
- V1 reference runs: `/tmp/bcvf_t005_b400_ema_dead_noanchor_n21/`

## Next step

§6.3 non-MPPI adapter extraction is the next §6.10 priority item. §6.1 multi-scenario
validation follows §6.3 under V1 architecture.
