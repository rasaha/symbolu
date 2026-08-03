# Slots-Only (S) Neural Attribution — Pre-Registration

**Date:** 2026-08-03 · Machine-readable: [`config.json`](config.json)

## The question this phase answers

Historical evaluation-time Phase-off proved only that the *trained C checkpoint* did not need
Phase **at inference**. It did **not** prove Phase had no effect on **optimization/representation
learning during training**. The **S arm** (sliding window + bounded slots, **no Phase anywhere** —
init, forward, backprop, eval, parameter count, or imports) is the decisive Phase-independent
slot-learning test.

## Hypotheses (pre-registered)

- **H1 — single-fact retrieval:** S outperforms A at needle@d96.
- **H2 — slot causality:** disabling S's slots removes the improvement.
- **H3 — address causality:** randomizing slot addresses removes/materially reduces it.
- **H4 — Phase independence:** S can learn the slot capability with no Phase path during training.
- **H5 — relational capability:** binding / supersession / source / multi-hop remain **open**; report
  even when negative. **Do not** promote H5 merely because the discrete metadata mechanics work
  (those are the stdlib-reference mechanics, a different question from learned behavior).

## Design

Matched A / S / A+ (see `config.json`): identical skeleton, tokenizer, corpus, data order,
optimizer, tokens, steps, batch, seq-len, eval protocol, seeds. FFN width auto-tuned per arm to the
same 2e6 total (parameter mismatch target < 0.05%). **Seeds 0,1,2** this phase (feasibility +
causal independence, not final robustness). A+ = window-only matched to S's exact param count (the
added-parameter control): **do not claim architectural benefit if S only beats an
under-parameterized A** — under this protocol A is already param-matched, and A+ confirms it.

## Ablations

Native (incubated class): `slots_off`, `randomized_address`, `shuffle_values`. Extended (wrapper,
no class edit): `write_gate_zero`, `slot_keys_randomized`. Records whether the learned capability
depends on slot content, addresses, write gate, or merely extra parameters.

## Decision (this phase — feasibility, not five-seed)

- **S − A materially positive at needle@d96 AND slots-off collapses it AND rand-address reduces it**
  → `PROVISIONALLY_SUPPORTED`, and (since Phase is absent) **H4 answered YES**.
- **S ≈ A, or ablations don't collapse** → `NOT_SUPPORTED` (slots don't learn it without Phase at
  this scale) or `WORKING_BUT_UNSTABLE` if it forms in a subset of seeds like the historical run.
- Relational (H5) reported as-is; near-chance is the expected honest outcome at this scale.

The five-seed stability phase is authorized **only** when this phase classifies the result
`READY_FOR_FIVE_SEED_VALIDATION` (i.e. S−A positive, causally attributed, Phase-independent).
