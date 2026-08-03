# Five-Seed Holdout Stability & Failure-Mode Validation — Pre-Registration

**Date:** 2026-08-03 · Frozen commit `3b521f0f` · Gates: [`ACCEPTANCE_GATES.json`](ACCEPTANCE_GATES.json) ·
Config: [`FROZEN_CONFIG.json`](FROZEN_CONFIG.json)

> **Written and committed BEFORE seed-3 training.** The architecture and every gate below are frozen.
> No architecture tuning or threshold change is permitted after viewing seeds 3–7. A verifier
> (`verify_preregistration.py`) fails if `ACCEPTANCE_GATES.json` changes after this commit.

## Question

Does the Phase-free bounded-slot **S** architecture reliably learn beyond-window single-fact retrieval
across **five previously unobserved seeds (3,4,5,6,7)**, while remaining causally dependent on its slot
mechanism and preserving acceptable LM quality and bounded-state behavior?

## Holdout policy

- **Primary verdict set:** seeds **3,4,5,6,7** (new holdout).
- **Previously observed (frozen, reported separately):** seeds 0,1,2 (S 0.075/0.250/0.200).
- **Combined 0–7:** supplementary/descriptive only. The formal pass/fail comes from seeds 3–7.

## Frozen arms & config

A (window), **A+ (window, param-matched to S — PRIMARY control)**, **S (window+slots, no Phase)**.
d128/h4/L4/window64/slots32/keydim64, ~2e6 params, N160, batch16, **1200 steps**, AdamW lr2e-3 wd0.01,
warmup60, clip1.0, fp32, 4 threads. Reuses the frozen `neural_slots_only` harness (no model logic forked).
Parameter match required: `|params(S) − params(A+)| / params(S) ≤ 0.0005`.

## Gates (all pre-registered; see the JSON for exact numbers)

- **Forming seed:** S needle@d96 ≥ 0.075 AND S−A+ ≥ 0.050 AND ≥ chance+0.050.
- **Primary stability:** ≥ 4/5 form; mean(S−A+) ≥ 0.080; median(S−A+) ≥ 0.050; S>A+ in ≥ 4/5.
- **Causal (every forming seed):** slots_off AND randomized_address each drop needle@d96 ≥ 0.050 absolute,
  cut the gain ≥ 50%, and land ≤ max(A+ + 0.030, 0.050). No averaging away a failed seed.
- **PPL quality:** mean PPL(S)@256 ≤ 1.20 × mean PPL(A+); ≤ 2/5 seeds exceed A+ PPL by > 25%.
- **Parameter control:** S must beat **A+** (else `PARAMETER_BUDGET_EXPLAINS_GAIN`).
- **Context distance:** d96 primary; no material d16 regression (S < A+ by > 0.05); ≥ 3 forming seeds keep
  positive S−A+ at d220.
- **Complexity:** no N×N; streaming state bytes constant across N∈{16,64,160,256,512}.

## Non-gates (reported, not required this phase)

Relational tasks (binding/supersession/source/multi-hop): `SUPPORTED / EMERGING / AT_CHANCE / REGRESSED`.
`EMERGING` predefined = above chance in ≥ 4/5 AND mean improvement over A+ ≥ 0.050. No single-seed promotion.

## Execution discipline

Exactly 1200 steps per arm; no metric-based early stopping; no per-seed LR tuning; frozen final checkpoint
evaluated. Any crash reruns the **entire paired set A+A++S** for that seed. Immutable per-seed artifacts.
Never write into `experiments/phase_lc/results/`; never modify `abc.json`. Phase absent (AST + runtime).

## Final classifications & readiness

`FIVE_SEED_STABLE` / `STABLE_RETRIEVAL_WITH_QUALITY_REGRESSION` / `PARTIALLY_STABLE` / `UNSTABLE` /
`NOT_CAUSALLY_ATTRIBUTED` / `PARAMETER_BUDGET_EXPLAINS_GAIN` / `RESOURCE_BLOCKED` / `INVALID_EXPERIMENT`.
`READY_FOR_KDA_VALIDATION` only if `FIVE_SEED_STABLE` or `STABLE_RETRIEVAL_WITH_QUALITY_REGRESSION`
(regression isolated). This readiness means only that the Phase-free slot is stable enough to **preserve**
while KDA is evaluated independently — **not** ready for composition, packaging, production, or general
memory claims.
