# Confirmatory replication — method

This is the single independent confirmatory replication required after the merged
slot-formation-stabilization result (PR #1319, `PROVISIONALLY_STABILIZED`). It re-runs the **exact
frozen CR1 intervention** on **five previously-unused seeds (13–17)** with **no tuning** and applies
the **merged Stage B classifier** unchanged.

## Design

- **Arms:** `A+` (window-only parameter/architecture control), `B0` (unscaffolded frozen S
  baseline), `CR1` (frozen intervention). All three are in the frozen Stage B matrix; A+ is the
  reference against which the frozen classifier defines formation, margins, causal collapse, and the
  quality gate.
- **Seeds:** 13, 14, 15, 16, 17 — next five integers after the highest previously-used BindingSlots
  training seed (12), outcome-independent, proven uncontaminated.
- **Budget:** exactly 1200 steps per arm/seed; checkpoints 0/60/120/300/600/900/1200; the classifier
  uses only the step-1200 evaluation (no best-checkpoint selection).

## Frozen intervention (CR1)

- **Curriculum** (boundaries 300/700/1200; final 500 steps original ABC_MIX).
- **Temporary write-read alignment** (λ 0.10 → 0 by step 600; label-free; zero during all
  evaluation; no inference-time op or parameter).
- Architecture, optimizer (AdamW lr 2e-3, wd 0.01, warmup 60, clip 1.0), tokenizer, corpus, task
  generator, output head, slot read/write equations — **all unchanged**. Slot arm 2 000 104 params;
  A+ control 2 000 392; architecture signature `6e8672bd…`.

## Harness

`run_confirmatory.py` calls the frozen `stabilize.run_arm` unchanged (idempotent/resumable, one JSON
per (arm, seed)); `classify_confirmatory.py` imports the frozen Stage B per-seed rules
(`classify_stage_b.py`, sha256 `3ca1e75f…`) and applies gates C1..C11 over seeds 13–17. Retention
trajectories are categorized by the frozen `retention.py`.

## Gates (frozen thresholds)

Formation `d96 ≥ 0.075 ∧ (CR1−A+) ≥ 0.050 ∧ d96 ≥ 0.07`. Aggregate: ≥4/5 form, CR1>B0 formation,
≥4/5 wins vs A+, mean(CR1−A+) ≥ 0.080, median ≥ 0.050, quality (ppl ≤ 1.20×A+), distance (d16/d220),
and **slots-off + randomized-address collapse on every forming seed** (never averaged). See
`docs/audits/bindingslots_confirmatory_replication/CLASSIFIER_SPEC.md` and `CAUSAL_GATE_SPEC.md`.

## Integrity

`verify_confirmatory_prereg.py` (30 torch-free checks) verifies every frozen hash before training and
in CI; the frozen `abc.json` (`b31989a3…`) is recorded before and after; the lab verifier (81) and
historical-artifact protection (8) remain green. The preregistration commit was **pushed before any
training**.

## Environment

Python 3.11.15, torch 2.2.2+cu121, CPU, fp32, threads=4. The merged run used a different torch
build; the frozen protocol pins the optimizer/schedule, not the torch build, and the seeds are new —
recorded as a documented environment factor, not a protocol change.
