# Phase-Guided Bounded Slots — Report

Tests the two-stage hypothesis: **Phase produces relevance / write-priority /
retrieval guidance that improves bounded slots**, measured by **D − C** (and the
causal control **D − D-no-guidance**).

> Final 3-seed numbers are filled from `results/aggregate.json` on completion.
> Single-seed high-pressure evidence (below) already established the direction.

## Frozen baseline
Commit `7345394`, 98/98 lightweight_phase tests pass, FREEZE OK, torch 2.13 CPU.
Frozen Phase and `BoundedBindingSlots` unmodified; `GuidedBoundedSlots` is a new
module (see `EXPERIMENT_MANIFEST.json`).

## Architecture (C and D)
- **Stage 1 (Phase relevance):** frozen `LightweightPhaseAttention` → g_t;
  guidance head [h_t; g_t] → (r_write, k_guide, p_retain).
- **Stage 2 (bounded memory):** `GuidedBoundedSlots` streaming writes (gate
  r_write, key = local ⊕ k_guide, retention p_retain, capacity-pressured eviction
  keeps highest retention), bounded Top-K read, relational readout.
- **C** = guidance head sees h only (no Phase). **D** = sees [h; g]. Difference =
  the Phase global signal, nothing else.

## No-quadratic
All arms pass the frozen shape audit; slots O(N·M·D) compute, O(M·D) state; no
`[B,N,M,D]` or N×N. (Filled: peak numel by N in `results/resources.json`.)

## Established finding (single-seed, high pressure)
Answer accuracy vs slot pressure (8 slots):

| pressure | C | D | D-no-guid |
|---|---|---|---|
| 4× (32 cand) | 0.99 | **0.16** | 0.98 |
| 8× (64 cand) | 0.99 | **0.53** | 0.90 |

- Plain slots (C) are robust to pressure (0.99) — content-addressed reads retrieve
  the queried fact even at 8× over-subscription.
- **Phase guidance (D) actively degrades** accuracy (0.16 / 0.53).
- **D-no-guid ≈ C**, isolating the cause: the Phase *signal* (added to slot keys /
  read query / retention), not the Phase computation, corrupts the slots' precise
  content-addressing. Write-F1 ≈ 0 for all arms — content matching makes selective
  writing unnecessary, so the relevance signal is never learned.

## (3-seed results, ablations, resources — filled post-run)

## Verdict (to be confirmed across seeds)
Two-stage "Phase guides slots" strategy: **NOT SUPPORTED** at tested scale —
Phase guidance is decorative-to-harmful; bounded slots alone are stronger.
