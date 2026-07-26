# Phase + Binding Validation — Report (v1.7)

**Question B:** Do bounded binding slots improve precise relational retrieval
beyond Phase alone? **Measured by C − B.**
**Question C:** Does Phase remain useful after binding slots are present?
**Measured by C − C-no-Phase.**

Numbers from `results/aggregate.json`, `results/tables.md`,
`results/ablations.json`, `results/resources.json`. 3 seeds, CPU, early stopping.

## Accuracy (mean ± std) and decisive deltas

| task | A | B | C | C-no-Phase | **C − B** | **C − C-no-Phase** |
|---|---|---|---|---|---|---|
| distant_fact | 0.03 | 0.07 | **1.00±0.00** | 0.92±0.06 | **+0.93** | +0.08 |
| supersession | 0.06 | 0.06 | **0.96±0.03** | 0.91±0.06 | **+0.90** | +0.04 |
| source_attr | 0.03 | 0.02 | 0.60±0.07 | 0.79±0.17 | **+0.58** | **−0.19** |
| multi_candidate | 0.00 | 0.03 | 0.23±0.10 | 0.30±0.09 | +0.20 | −0.07 |
| entity_binding | 0.04 | 0.03 | 0.22±0.07 | 0.18±0.06 | +0.19 | +0.04 |
| insufficient | 0.96 | 1.00 | 0.96 | 0.91 | −0.04 | +0.04 |
| lm | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |

## Question B — C − B (binding-slot contribution given Phase)

**Large and consistent.** Slots add +0.93 (distant), +0.90 (supersession),
+0.58 (source), +0.20 (multi-candidate), +0.19 (entity-binding). Bounded binding
slots provide the relational/version/source capability that neither local nor
Phase supply. **SUPPORTED — PROVEN AT TESTED SCALE.**

## Question C — C − C-no-Phase (is Phase load-bearing with slots present)

**Small and mixed.** Phase adds a slight margin on some tasks (distant +0.08,
supersession +0.04, binding +0.04) but is **negative** on others (source −0.19,
multi-candidate −0.07). Net effect ≈ 0 and inconsistent.

Phase ablations **inside arm C** confirm this causally:

| Phase ablation (arm C) | distant | binding | source |
|---|---|---|---|
| baseline | 1.00 | 0.30 | 0.70 |
| Phase disabled | 1.00 | 0.30 | 0.70 |
| Phase weights randomized | 1.00 | 0.27 | 0.70 |
| Phase capacity reduced | 0.97 | 0.30 | 0.70 |

Corrupting Phase inside C changes essentially nothing. **Phase is decorative once
slots are present — NOT SUPPORTED as load-bearing.**

## Slot causal ablations (arm C) — slots ARE load-bearing

| slot ablation | binding | source | supersession |
|---|---|---|---|
| baseline | 0.30 | 0.70 | 0.93 |
| slots disabled | 0.03 | 0.00 | 0.10 |
| slot keys randomized | 0.17 | 0.10 | 0.23 |
| slot values shuffled | 0.07 | 0.00 | 0.03 |
| Top-K = 1 | 0.27 | 0.70 | 0.93 |

Disabling slots, randomizing their content-addressing keys, or shuffling their
values **collapses** every relational capability. Top-K=1 is nearly sufficient
here (single-fact-per-query tasks). **Slots are strongly load-bearing.**

## Capacity boundary (not unlimited binding)

`entity_binding` (multiple *similar* entities, near-duplicate names) tops out at
**0.22** for C with high value-swap confusion — the capacity/collision boundary of
16 slots with cross-position entity→value binding at this model scale. Single-fact
relational tasks (distant, supersession) are solved (≈0.93–1.00); many-similar-
entity binding is not. This is reported as a limit, not overcome.

## Resource cost

C: 443,912 params; bounded state (Phase 384 + slots 6272 numel/seq, both O(1) in
N); latency **248 ms / 256 tokens (1,032 tok/s)** vs A's 2.9 ms (89k tok/s) —
~85× slower. Scaling is **linear** (exponent 1.01), but the constant is large
because the frozen slot module writes token-by-token in a Python loop. Capability
is real; throughput at this implementation is a deployment concern.

## Findings, separated

- **Implemented:** bounded binding slots as a third additive path (frozen module,
  unmodified); slot + Phase causal ablations; resource/no-quadratic measurement.
- **Tested:** 3-seed C/C-no-Phase accuracy; Phase-in-C and slot-in-C ablations;
  bounded-state and linear-scaling proofs.
- **Demonstrated:** C ≫ B (slots add large relational capability); slots causally
  load-bearing; Phase causally decorative inside C; a concrete capacity boundary
  on many-similar-entity binding.
- **Unsupported:** Phase as load-bearing inside C (C ≈ C-no-Phase, ablation-neutral,
  negative on source).
- **Deferred:** slot capacity sweep (8/16/32/64 × entities/facts/versions/
  conflicts), version/timestamp/confidence metadata tasks, contradiction and
  multi-hop batteries, throughput optimization of the slot write loop.

## Verdicts

- **Question B (C − B): SUPPORTED — PROVEN AT TESTED SCALE.** Bounded slots add
  strong, causally-verified relational precision.
- **Question C (C − C-no-Phase): NOT SUPPORTED.** Phase is decorative once slots
  are present (small, mixed, sometimes negative; ablation-neutral).
- **Deployment (Configuration D-style resource question): ARCHITECTURALLY
  PLAUSIBLE but not deployment-ready** at the measured 1,032 tok/s (slot write
  loop), despite bounded state and linear scaling.
