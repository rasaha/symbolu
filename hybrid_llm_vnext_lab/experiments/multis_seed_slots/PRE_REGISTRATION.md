# Multi-Seed Bounded-Slot Validation — Pre-Registration

**Date:** 2026-08-03 · **Status:** pre-registered; **not yet run** (`RESOURCE_BLOCKED`: no torch).
Runs **only after** neural reproduction parity is reached (`STATISTICAL_REPRODUCTION` or better).
Machine-readable: [`config.json`](config.json).

## Why pre-register

The phase_lc positive result formed in **1 of 3 seeds**. The open question is **stability**, not
existence. Pre-registering the hypotheses, seeds, metrics, thresholds, and stopping rule before
running prevents seed-cherry-picking and keeps the "working candidate" claim honest.

## Thresholds are inherited, not invented

The acceptance thresholds are those already merged in the audit:
`docs/audits/hybrid_llm/artifacts/hybrid_llm_acceptance_thresholds.json`. They are **not
silently replaced.** This pre-registration only **adds clarifications** where the merged
thresholds are ambiguous for a slots-only experiment, and those clarifications are recorded
**here, before running** (see `config.json` → `clarifications`), never after observing results.

## Hypotheses

- **H1 (single-fact stability):** with ≥5 seeds, mean needle@d96 > 0.5 **and worst-seed > 0.2**
  (the historical result failed the worst-seed bar).
- **H2 (relational):** binding (k=2) mean > 0.5 and exceeds the local baseline A by ≥ 0.3 — the
  primary go/no-go for slots as *relational* memory (historically ≈ chance).
- **H3 (causal):** slots-off and randomized-address ablations both collapse the gain; write-gate
  and erase-gate ablations degrade supersession; phase-off leaves the slot result intact.

## Design

| Field | Value |
|---|---|
| Seeds | 0,1,2,3,4 (≥5) |
| Steps / batch / model | matched to the reproduced config (1200 / 16 / d128-4L, num_slots=32) |
| Primary metric | needle@d96 mean **and worst-of-5** |
| Secondary | binding k∈{2,4,8}, supersession (current/stale), source, multihop, ppl@256 |
| Stopping rule | fixed 5×1200; **no peeking**, no metric-based early stop |
| Ablations | slots-off, randomized-address, write-gate-off, phase-off, memory-reset |

## Decision

- Meets merged T1, T2, T4 (+ T5/T6 if a relational-memory claim is made) → advance
  `WORKING_BUT_UNSTABLE` → `MULTI_SEED_VALIDATED`.
- Worst-seed needle@d96 ≤ 0.2 **or** binding k=2 ≤ chance+0.1 → stays `WORKING_BUT_UNSTABLE`;
  do **not** advance; do **not** move toward `packages/`.

A result that appears in one seed and fails the others is `WORKING_BUT_UNSTABLE`, **not
validated** — and must be labeled as such.
