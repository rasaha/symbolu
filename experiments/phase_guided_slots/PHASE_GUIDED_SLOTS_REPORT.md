# Phase-Guided Bounded Slots — Report

Tests the two-stage hypothesis: **Phase produces relevance / write-priority /
retrieval guidance that improves bounded slots**, measured by **D − C** and the
causal control **D − D-no-guidance**. 3 seeds, CPU, early stopping. Raw:
`results/raw/`, `results/aggregate.json`, `results/resources.json`.

## 1. Frozen baseline
Commit `7345394`; 98/98 lightweight_phase tests pass; **FREEZE OK**; torch 2.13
CPU (4 cores / 15 GiB). Frozen `LightweightPhaseAttention` and frozen
`BoundedBindingSlots` are **unmodified**; `GuidedBoundedSlots` is a new module.
`EXPERIMENT_MANIFEST.json` records the exact configuration.

## 2. Exact C and D architecture
- **Stage 1 (Phase relevance):** frozen Phase → global state g_t; guidance head
  `[h_t; g_t]` → `r_write` (write gate), `k_guide` (write key), `p_retain`
  (retention priority).
- **Stage 2 (bounded memory):** `GuidedBoundedSlots` — streaming writes
  (gate `r_write`, key = local ⊕ `k_guide`, retention `p_retain`,
  capacity-pressured eviction keeps highest-retention slots), bounded Top-K read,
  relational readout over selected slots.
- **C** = guidance head sees `h` only (no Phase). **D** = sees `[h; g]`. The only
  difference is whether Phase's global signal enters slot writes/reads/retention.

## 3. No-quadratic proof
All arms pass the frozen shape audit (no two-sequence-axis tensor). Peak
intermediate element count is **linear in N** (A/C = 64·N, D = 96·N; measured
{64,128,256}). Persistent state bounded and constant in N: Phase 192 numel,
slots 1176 numel. Slots are O(N·M·D) compute, O(M·D) state; no `[B,N,M,D]`.

## 4. Answer accuracy (mean ± std, 3 seeds) and decisive deltas

| arm | 1× pressure (8 cand / 8 slots) | 3× pressure (24 cand / 8 slots) |
|---|---|---|
| A (local only) | 0.06 ± 0.02 | 0.05 ± 0.00 |
| **C (slots, no Phase)** | **0.97 ± 0.01** | **1.00 ± 0.00** |
| **D (Phase-guided slots)** | 0.83 ± 0.11 | **0.24 ± 0.22** |
| D-no-guidance | 0.98 ± 0.01 | 0.98 ± 0.01 |
| D-random | 0.25 ± 0.20 | 0.14 ± 0.08 |

| delta | 1× | 3× |
|---|---|---|
| **D − C** (Phase-guidance value) | −0.14 | **−0.75** |
| **D − D-no-guidance** (causal) | −0.15 | **−0.74** |
| C − A (slot value) | +0.91 | +0.94 |

## 5. Write-worthiness (Stage 1)
Write-F1 ≈ 0.00 for C and D; even with Phase's global state, the guidance head
does not learn to flag the topic fact. Because content-addressed reads retrieve
the queried fact regardless, selective writing is never necessary and the
relevance signal is not learned. **Phase does not deliver a useful write /
retention / retrieval relevance signal at tested scale.**

## 6. Interpretation (each stage)
- **Slots alone (C) are robust to pressure.** C = 0.97 → 1.00 as pressure rises;
  the distinctive queried fact survives eviction / is found among Top-K even at
  3× (and, in the single-seed probe, 8×) over-subscription. The hypothesized
  "Phase helps under pressure" opportunity never materializes — slots handle
  pressure on their own.
- **Phase guidance actively harms (D).** Adding Phase's lossy global state to the
  slot write-keys and read-query corrupts the precise content-addressing slots
  rely on. Harm grows with pressure (D − C: −0.14 at 1×, −0.75 at 3×).
- **The Phase signal is the cause, not Phase computation.** D-no-guidance keeps
  the Phase module but zeroes the guidance → recovers C-level accuracy (0.98).
  D-random (any perturbation of matching keys/query) is catastrophic (0.14–0.25),
  confirming the mechanism is corruption of content addressing.

## 7. Resource measurements
| arm | params | phase state | slot state | latency (128) | tok/s |
|---|---|---|---|---|---|
| A | 306,386 | 0 | 0 | 1.0 ms | 126,233 |
| C | 306,386 | 0 | 1176 | 18.8 ms | 6,791 |
| D | 361,874 | 192 | 1176 | 21.7 ms | 5,898 |

D is **slower** than C (extra Phase pass) for a capability **loss**.

## 8. Failure modes
- Phase's global state is a lossy running average; injected into slot keys/queries
  it degrades exact match. The frozen slot loop's Python write path also bounds
  throughput (~6k tok/s).
- Slot pressure at this scale does not stress C (content-match reads are robust),
  so the guidance hypothesis has no window to demonstrate value.

## 9. Findings, separated
- **Implemented:** two-stage Phase-guided-slot architecture; 7 arms; topic-
  conditioned slot-pressure task with write-worthiness labels; no-quadratic +
  resource + ablation harness. Frozen Phase and frozen slots untouched.
- **Tested:** 3-seed A/C/D/D-no-guid/D-random at 1×/3× pressure; write-F1; causal
  guidance ablations; no-quadratic and bounded-state proofs; resources.
- **Demonstrated:** C ≫ A (slots are the capability); C robust to pressure;
  **D < C and worsening with pressure**; D-no-guidance ≈ C (Phase signal is the
  cause); D-random catastrophic; Phase yields no useful write/relevance signal.
- **Unsupported (falsified at tested scale):** Phase-guided slots (D > C); Phase
  as a relevance / write-priority / retrieval-guidance mechanism.
- **Deferred:** larger models / real corpora; 8K–32K context; slot budgets 16/32/
  64 and pressures 4×–8× across seeds; multi-hop relational readout; staged
  training (A–E) — though the causal ablations already localize the negative
  result to the Phase signal, not the training schedule.

## 10. Evidence-tier verdict
**Phase guidance for bounded relational memory: DECORATIVE-TO-HARMFUL —
NOT SUPPORTED / FALSIFIED AT TESTED SCALE.** The two-stage strategy (Phase selects
relevant evidence, slots preserve/retrieve it) is **not supported**: bounded slots
alone are strictly better and robust to slot pressure, and Phase guidance degrades
them, causally (D-no-guidance recovers, D-random confirms). No universal claim is
drawn from this micro-scale run.
