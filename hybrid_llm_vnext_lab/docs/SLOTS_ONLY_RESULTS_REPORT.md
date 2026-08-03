# Slots-Only (S) Neural Attribution — Results

**Date:** 2026-08-03 · Run `sarm_1200_run1` (torch 2.13.0, CPU fp32, 4 threads, seeds 0,1,2, 1200 steps).
Data: [`../artifacts/slots_only_results_sarm_1200_run1.json`](../artifacts/slots_only_results_sarm_1200_run1.json) ·
[`../artifacts/slots_only_analysis_sarm_1200_run1.json`](../artifacts/slots_only_analysis_sarm_1200_run1.json)

## Verdict: `PROVISIONALLY_SUPPORTED` — and the phase's core question answered

> **Can bounded slots learn the beyond-window retrieval capability with NO Phase present during
> training?  → YES (H4 = Phase-independence confirmed).**

Phase is absent from the S arm at initialization, forward, backprop, evaluation, parameter count, and
every import (AST-enforced). The S arm nonetheless learns beyond-window single-fact retrieval, and the
capability is causally attributable to the slots.

## Primary result — needle@d96 (beyond window=64; chance ≈ 0.02)

| seed | A (window) | A+ (window, param-matched) | **S (window+slots, no Phase)** |
|---|---|---|---|
| 0 | 0.025 | 0.025 | **0.075** |
| 1 | 0.000 | 0.000 | **0.250** |
| 2 | 0.017 | 0.017 | **0.200** |
| **mean** | 0.014 | 0.014 | **0.175** |

- **S − A = S − A+ = +0.161.** Because A+ (window-only, matched to S's exact param count) equals A, the
  gain is from **slot structure, not extra parameters**.
- **S beats A in all 3 seeds** (0.075, 0.250, 0.200 all > A and > chance). This is **more consistent
  across seeds** than the historical *with-Phase* C arm, which formed in only 1/3 seeds (0.467/0/0).
- **Magnitude is lower** than the historical with-Phase C peak (0.250 vs 0.467). Honest reading: Phase is
  **not necessary** for the capability, but may help optimization reach a stronger single-seed circuit.

## Causal ablations (needle@d96)

On the forming seed (seed 1, baseline 0.250):

| ablation | value | reading |
|---|---|---|
| baseline | 0.250 | — |
| slots_off (`zero`) | 0.017 | **collapses** (H2 ✓) |
| randomized_address (`rand_keys`) | 0.000 | **collapses** (H3 ✓) |
| shuffle_values | 0.000 | collapses |
| write_gate_zero | 0.017 | collapses (no writes → no memory) |
| slot_keys_randomized | 0.117 | partial (still above A) |

Per-seed consistency (baseline → slots_off): seed0 0.075→0.025, seed1 0.250→0.017, seed2 0.200→0.017 —
**slots-off collapses the gain in all three seeds.** The capability depends on slot content, slot
addresses, and the write gate.

## Relational tasks (H5) — still open (honest negative)

| task | S mean | chance |
|---|---|---|
| binding k=2 | 0.061 | 0.02 |
| supersession (current) | 0.044 | 0.02 |
| source attribution | 0.100 | ~0.083 |
| multi-hop | 0.058 | 0.02 |

All near chance. **H5 is NOT promoted** — the discrete metadata mechanics working in the stdlib reference
is a *different* question from a trained model learning relational binding, and the trained S model does
**not** demonstrate it at this scale.

## Classification

- **Slots-only arm: `PROVISIONALLY_SUPPORTED`** (H1 S>A every seed; H2 slots-off collapses; H3 address
  collapses; H4 Phase-independence = YES). **`READY_FOR_FIVE_SEED_VALIDATION`.**
- The A / A+ arms reproduce the historical A baseline **exactly** (params 2000392; ppl256 128.4/108.4/118.0
  vs historical 128.45/108.43/117.98; needle 0.025/0.000/0.017) — confirming the pipeline fidelity.

## What this does and does not establish

- **Does:** slots learn beyond-window single-fact retrieval **without Phase**, causally (not from
  parameters), reproducibly across 3 seeds at ~2M params / 1200 steps.
- **Does not:** establish relational memory (binding/supersession/source/multi-hop), five-seed stability,
  meaningful-scale training, production decode, or that the magnitude matches the with-Phase circuit.

The five-seed stability phase is now **authorized** (READY_FOR_FIVE_SEED_VALIDATION); it is not run here.
