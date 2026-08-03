# Legacy Bounded-Slot Reproduction — Report

**Date:** 2026-08-03 · Protocol: [`../experiments/reproduce_legacy_slots/REPRODUCTION_PROTOCOL.md`](../experiments/reproduce_legacy_slots/REPRODUCTION_PROTOCOL.md)

## Reproduction classification: `RESOURCE_BLOCKED` (neural) + `REPRODUCED` (discrete mechanics)

- **Neural reproduction** of the phase_lc A/B/C training run is **`RESOURCE_BLOCKED`**: PyTorch
  and NumPy are not installed in this environment. The exact original parameters are pinned
  (`config.json`), and `run.py` executes the reproduction in one command in a torch-enabled
  environment. **No neural result is fabricated.**
- **Discrete-mechanics reproduction** of the slot behaviour **passed here**: the stdlib
  reference reproduces single-fact retrieval, multi-fact retrieval, supersession/stale
  suppression, source attribution, distractor resistance, capacity/eviction, long-delay recall,
  reset, and chunk-boundary retention — deterministically, with the bounded-state and no-`[N,N]`
  invariants enforced (36 lab tests pass).

## Saved historical baseline (target for the neural run) — from `experiments/phase_lc/results/abc.json`

Primary metric: **needle@d96** (single-fact retrieval beyond the window of 64), n=120, 3 seeds,
1200 steps, batch 16.

| Arm / ablation | seed 0 | seed 1 | seed 2 | mean |
|---|---|---|---|---|
| **C baseline (window+phase+slots)** | **0.467** | 0.000 | 0.000 | 0.156 |
| C slots-off (`ablate='zero'`) | 0.017 | 0.000 | 0.042 | 0.019 |
| C rand-address (`ablate='rand_keys'`) | 0.050 | 0.000 | 0.008 | 0.019 |
| C phase-off (`ablate_phase=True`) | 0.475 | 0.000 | 0.000 | 0.158 |
| A (window only) | — | — | — | 0.014 |
| B (window+phase) | — | — | — | 0.003 |

PPL@256 means: A 118.3 · B 72.8 · C 83.3. Bounded state (C): 16,896 floats (slots 16,384 +
phase 512), independent of N; `no_nxn_check` = both false.

## Reading of the baseline (the causal signature)

Seed 0 forms an addressable-memory circuit that reaches **0.467** on beyond-window single-fact
recall (chance ≈ 0.02). Turning **slots off collapses it to 0.017**; **randomizing slot
addresses collapses it to 0.050**; turning **Phase off leaves it at 0.475**. That is clean
causal evidence that **the learned addressable slot memory — not Phase — carries the
capability**, at single-fact scope, forming in **1 of 3 seeds**.

## What the neural run must reproduce

Not merely "one good seed," but the **pattern**: seed-0 circuit forms; slots-off and rand-keys
collapse it; phase-off preserves it; seeds 1–2 remain near chance. `compare.py` encodes exactly
this pattern check and emits the reproduction classification. The report's prose-only
"1800-step → 1.00" figure is **excluded** (NOT_FOUND as an artifact).

## Next step

After neural `STATISTICAL_REPRODUCTION`, run the pre-registered ≥5-seed stability experiment
([`../experiments/multis_seed_slots/PRE_REGISTRATION.md`](../experiments/multis_seed_slots/PRE_REGISTRATION.md))
against the merged audit thresholds. Slots advance from `WORKING_BUT_UNSTABLE` only if the
worst-of-5 and relational-binding bars are met.
