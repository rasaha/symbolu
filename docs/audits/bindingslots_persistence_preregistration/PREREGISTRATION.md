# BindingSlots Shortcut-Path Isolation & Persistence Phase — Pre-registration

> **PREREGISTRATION ONLY · NO TRAINING STARTED · KDA VALIDATION REMAINS BLOCKED**

Follow-up to the functional-routing Stage-1 screen (`ROUTING_PURITY_NOT_RESOLVED`). This document set
freezes the next experiment's arms, seeds, gates, instrumentation, and evidence rules **before** any
training. No training is run in this phase; it requires separate explicit authorization
(`TRAINING_AUTHORIZATION_GATE.md`).

## Scientific question (frozen)

Can an address-specific routing circuit that forms during the scaffold remain **causally
address-dependent through step 1200** after the scaffold is withdrawn or reduced? The experiment
distinguishes **formation**, **retention**, **causal cleanliness**, and **shortcut dependence**. Raw
needle performance is not sufficient evidence of functional routing.

## Six-arm matrix (frozen)

`A+` (window-only control, required by the same-seed relative causal threshold) · `R0` (frozen CR1) ·
`O1` (correct-slot reproduction anchor) · `O1R` (standing residual, λ_addr = 0.01 for steps
601–1200) · `H1` (routing-parameter consolidation, 0.1× LR on the frozen addressing group during
600–900) · `H2` (functional teacher of the step-600 address-conditioned slot-read distribution).
**No O2/O3/H3/C1.** See `ARM_DEFINITIONS.md` and the frozen JSON in
`experiments/bindingslots_persistence/`.

## Seeds (frozen)

Reserved Stage-2 seeds **23–27**, proven fresh, non-replaceable on outcome. Planned matrix: 6 × 5 =
**30 runs — none started in this phase.**

## Checkpoints (frozen)

`0/60/120/300/600/700/900/1200`. Step **700** (curriculum handoff) is **diagnostic only** and
**proven non-invasive** (`DIAGNOSTIC_NON_INTERFERENCE.md`; report
`results/diagnostic_noninterference.json`). Primary comparison: **routing quality at step 600 vs
retained at step 1200.**

## Advancement gate (frozen)

A seed is `CLEAN_STABLE` only if, at step 1200, all hold vs the **same-seed A+**: needle formation;
correct-slot prob ≥ 0.50; rank ≤ 5; margin ≥ 3.0; slots-off collapse; randomized-address collapse;
quality; distance. An arm advances only when `clean_stable ≥ 4/5` **and** `> R0` **and** all mandatory
gates pass. **Raw 5/5 needle cannot compensate for causal impurity.** See
`CAUSAL_AND_ADVANCEMENT_GATES.md`.

## Integrity

`verify_persistence_prereg.py` → **52 checks, 0 failures →
`BINDINGSLOTS_PERSISTENCE_PREREGISTRATION_VERIFIED`.** Frozen `abc.json` `b31989a3…` unchanged; all
frozen source hashes (incl. `interventions.py`/`stabilize.py` swapped at runtime, and the O1 source)
verified; no training-result files exist. See `HISTORICAL artifact protection` in the PR body.

## What this phase does NOT do

No training, model init for experiments, checkpoint generation, evaluation, arm selection, coefficient
sweeps, seed replacement, best-checkpoint selection, KDA validation, Phase/MLA/packaging, or PR merge.
`LIMITATIONS_AND_NONCLAIMS.md` lists the non-claims.
