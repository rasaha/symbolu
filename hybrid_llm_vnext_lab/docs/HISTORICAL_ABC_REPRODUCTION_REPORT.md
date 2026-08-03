# Historical A/B/C Reproduction — Report

**Date:** 2026-08-03 · Run `repro_abc_run1` (torch 2.13.0, CPU fp32, 4 threads, seeds 0,1,2, 1200 steps,
wall 73 min). Data: [`../artifacts/historical_abc_reproduction.json`](../artifacts/historical_abc_reproduction.json) ·
result [`../artifacts/repro_abc_run1_results.json`](../artifacts/repro_abc_run1_results.json) ·
manifest [`../artifacts/repro_abc_run1_manifest.json`](../artifacts/repro_abc_run1_manifest.json)

## Classification: `EXACT_REPRODUCTION`

The saved historical A/B/C study (`experiments/phase_lc/results/abc.json`, 1200 steps, batch 16, 3 seeds)
reproduces **exactly**, including the causal ablation pattern. The frozen artifact was **never written**
(sha256 `b31989a3…` identical before and after; launcher used a unique tag and refused any `abc*` tag).

## needle@d96 (primary metric; chance ≈ 0.02)

| arm | seed0 | seed1 | seed2 | historical |
|---|---|---|---|---|
| A | 0.025 | 0.000 | 0.017 | 0.025 / 0.000 / 0.017 |
| B | 0.000 | 0.000 | 0.008 | 0.000 / 0.000 / 0.008 |
| **C** | **0.467** | 0.000 | 0.000 | **0.467** / 0.000 / 0.000 |

## PPL@256

| arm | reproduced | historical |
|---|---|---|
| A | 128.4 / 108.4 / 118.0 | 128.45 / 108.43 / 117.98 |
| B | 62.4 / 59.3 / 96.5 | 62.45 / 59.34 / 96.50 |
| C | 87.3 / 83.0 / 79.7 | 87.28 / 83.02 / 79.71 |

Parameter counts match exactly (A 2000392, B 1999752, C 2000492). `no_nxn_check` = `{phase: false, slots:
false}` for every record. vocab 1291, corpus 55,547 tokens.

## The causal signature reproduces exactly (C seed0)

| ablation | reproduced | historical |
|---|---|---|
| baseline | 0.467 | 0.4667 |
| **slots_off** | **0.017** | 0.0167 |
| randomized_address | 0.050 | 0.050 |
| **phase_off** | **0.475** (unchanged) | 0.475 |

Reading (identical to the audit's C6/Q7): the forming-seed circuit reaches 0.467; **slots-off collapses
it to 0.017**; randomized addresses collapse it to 0.050; **phase-off leaves it at 0.475** — the learned
addressable **slot** memory, not Phase, carries the capability.

## Acceptance

Meets every `must_match_exactly` and `primary_causal_pattern` condition in
[`../experiments/reproduce_legacy_slots/REPRODUCTION_ACCEPTANCE.json`](../experiments/reproduce_legacy_slots/REPRODUCTION_ACCEPTANCE.json)
within the pre-registered tolerances; per-seed values are essentially identical because torch 2.13.0
matches the historical 2.13 with the same seeds, thread count, and (parity-proven) code. The report's
prose-only "1800-step → 1.00" figure was **not** a target and was not reproduced.

## Consequence for maturity

- **Historical neural slots: `HISTORICAL_RESULT_ONLY` → `EXACT_REPRODUCTION`.**
- Combined with the neural `EXACT_PARITY` (incubated == historical) and the slots-only
  `PROVISIONALLY_SUPPORTED` result, the bounded-slot capability is now an **honestly executed neural
  result**, no longer historical-only or mechanically-reproduced-only.
