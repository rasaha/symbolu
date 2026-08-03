# Confirmatory replication — results

**Primary verdict (mechanical): `CONFIRMATORY_REPLICATION_FAILED`.**
`SLOT_FORMATION_NOT_REPLICATED` · `KDA_READINESS = KDA_VALIDATION_BLOCKED`.

All 15 runs (A+/B0/CR1 × fresh seeds 13–17) completed at the frozen 1200-step budget. Source of
truth: `experiments/bindingslots_confirmatory/results/aggregate_result.json`.

## needle@d96 (chance ≈ 0.02)

| seed | A+ | B0 | **CR1** | CR1 forms | causal clean | retention |
|---|---|---|---|---|---|---|
| 13 | 0.000 | 0.000 | **0.000** | ✗ | — | FORMED_THEN_COLLAPSED |
| 14 | 0.000 | 0.000 | **0.000** | ✗ | — | FORMED_THEN_COLLAPSED |
| 15 | 0.000 | 0.000 | **1.000** | ✓ | ✓ | FORMED_AND_RETAINED |
| 16 | 0.008 | 0.000 | **1.000** | ✓ | **✗** | FORMED_AND_RETAINED |
| 17 | 0.000 | 0.000 | **1.000** | ✓ | ✓ | FORMED_AND_RETAINED |
| **formed** | **0/5** | **0/5** | **3/5** | | | |

## Gate-by-gate

| gate | condition | result |
|---|---|---|
| **C1** | CR1 forms ≥ 4/5 | **FAIL — 3/5** |
| C2 | CR1 formation > B0 | PASS (3 > 0) |
| **C3** | CR1 wins vs A+ ≥ 4/5 | **FAIL — 3/5** |
| C4 | mean(CR1−A+) d96 ≥ 0.080 | PASS (0.598) |
| C5 | median(CR1−A+) d96 ≥ 0.050 | PASS (0.992) |
| C6 | quality (ppl ≤ 1.20×A+) | PASS (135.6 ≤ 1.20×142.1; 0/5 exceed) |
| C7 | distance (d16 / d220) | PASS (d16 ok; d220 forming-positive 3) |
| C8 | slots-off collapse every forming seed | PASS |
| **C9** | randomized-address collapse every forming seed | **FAIL — seed 16** |
| C10 | integrity + parameter match | PASS |
| C11 | no protocol deviation | PASS |

**Two independent scientific failures:** formation reliability (C1/C3) and causal cleanliness (C9).
Either alone is disqualifying; a higher mean margin (0.598) with < 4/5 formed does **not** pass —
C1 is mandatory and cannot be traded for margin.

## Comparison to the merged Stage B (seeds 8–12)

| | merged Stage B | this confirmatory |
|---|---|---|
| CR1 formation | 4/5 | **3/5** |
| B0 formation | 3/5 | **0/5** |
| A+ formation | 0/5 | 0/5 |
| retention collapse (FORMED_THEN_COLLAPSED) | 1/5 (seed 9) | **2/5 (seeds 13, 14)** |
| causally-unclean former | 0 | **1 (seed 16)** |

The merged 4/5 holdout result **did not independently replicate**. Formation reliability fell to 3/5,
the post-scaffold retention-collapse mode recurred on 2/5 fresh seeds, and one of the three formers
was not cleanly slot-causal. The unscaffolded baseline B0 also fell to 0/5 — the whole system is less
reliable in this environment — but that does not rescue CR1: even against a 0/5 baseline, CR1 fails
its own ≥4/5 formation bar and its causal gate.

## Quality & distance (passing, but not decisive)

- Quality: mean CR1 ppl@256 **135.55** ≤ 1.20 × A+ **142.10**; 0/5 exceed A+ by > 25 %.
- Distance: no d16 material regression; all 3 formed-and-retained seeds keep positive CR1−A+ at
  d220. Formation, when it retains, is distance-robust — but reliability, not distance, is the
  failing axis.
