# Prior-result inventory

Machine-readable: [`PRIOR_RESULT_INVENTORY.json`](./PRIOR_RESULT_INVENTORY.json).

## PR #1300 — five-seed holdout (seeds 3–7)

S formed **3/5** (seeds 4,5,6). Below the ≥4/5 bar → `PARTIALLY_STABLE`,
`NOT_READY_FOR_KDA_VALIDATION`. Formation, when present, was real, large, causally slot-dependent,
quality-preserving, distance-robust — but unreliable (~60 %).

## PR #1319 Stage A — diagnostic seeds 3/6/7

C1 (curriculum only) reached 3/3 formation but **failed the causal gate** (the multi-layer local
window did the retrieval). R1 (alignment only) 2/3, causally clean. **CR1** (curriculum + alignment)
3/3, causally clean → mechanically selected.

## PR #1319 Stage B — fresh holdout (seeds 8–12)

| seed | A+ | B0 | CR1 | CR1 forms |
|---|---|---|---|---|
| 8 | 0.000 | 0.642 | 0.992 | ✓ |
| 9 | 0.000 | 0.583 | **0.000** | ✗ (retention collapse) |
| 10 | 0.000 | 0.183 | 0.992 | ✓ |
| 11 | 0.000 | 0.000 | 1.000 | ✓ |
| 12 | 0.000 | 0.033 | 0.967 | ✓ |
| **formed** | 0/5 | 3/5 | **4/5** | |

All Stage B gates passed → `PROVISIONALLY_STABILIZED`. **Seed 9** formed then collapsed (needle
peaked 1.000 at step 300, decayed to 0.000 after λ→0 at step 600 and the curriculum handoff at step
700) — a post-scaffold retention failure, not incapacity.

## What the confirmatory phase must reproduce

CR1 forms **≥ 4/5** on **independent fresh seeds 13–17** with **clean causal collapse** on every
forming seed, beating B0 formation, under the frozen protocol with no tuning.
