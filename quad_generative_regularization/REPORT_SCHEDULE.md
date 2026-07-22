# Early-Only Auxiliary Schedule Ablation — Report

**Study:** Quad Generative Regularization, follow-up experiment (CPU-only)
**Date:** 2026-07-22 · **Compute:** CPU-only, 4 threads · **Benchmark:** MQAR (frozen config)
**Outcome category:** **BINDING_GAIN_BUT_GENERALIZATION_NOT_RECOVERED**

> This experiment evaluates **Quad-native training regularization**. It does not implement or
> test USE phase or synchronization mechanisms.

## Hypothesis under test

*Quad-native supervision is useful for establishing associative binding early in training, but
continuing the auxiliary pressure after binding is learned causes excessive score sharpening
and poor generalization.*

The experiment tests exactly this and nothing else. No entropy regularizer, margin cap, new
representation, new auxiliary head, phase logic, synchronization, or teacher model was added.

## Design (everything frozen; only the schedule changes)

Reused, unchanged, from the completed three-seed screen (`RESULTS/results.json`):
**Arm A** (task only), **Arm C** (generic off-path relational control), **Arm D-full**
(Quad-native auxiliary throughout). Added, same frozen config, same three seeds {0,1,2}, same
Quad objective / λ=1.0 / τ=1.0 / candidate construction:

| Arm | auxiliary active for | hard cutoff step (of 2500) |
|---|---|---|
| D-10 | first 10% of steps | 250 |
| D-25 | first 25% of steps | 625 |
| D-50 | first 50% of steps | 1250 |

After the cutoff the coefficient is set **exactly to zero** (no gradual decay); training
continues on task loss only. Verified by tests (`tests/test_schedule.py`): the coefficient and
the auxiliary gradient norm are exactly zero after the cutoff, and `aux_cutoff_frac=0.0` is
bit-identical to Arm A (post-cutoff gradients come only from the task loss).

## Code changes (limited to schedule + diagnostics)

- `qgr/train.py`: `TrainConfig.aux_cutoff_frac` + `cutoff_step()`; the loop computes
  `aux_active = uses_aux and step < cutoff`, applies coefficient `λ if aux_active else 0.0`,
  logs `aux_active`/`aux_coeff` per step, and gates the task-vs-aux gradient diagnostic on
  `aux_active` (records aux-grad norm 0 after cutoff).
- `run_schedule_ablation.py`: reuse A/C/D-full, run D-10/25/50, evaluate all four conditions,
  emit machine-readable results and cutoff-marked plots, classify the outcome.
- `tests/test_schedule.py`: 4 tests (all pass). Full suite: **25/25 passing**.

## Results — in-distribution (equal-token, 3 seeds)

| Arm | acc mean ± sd | min seed | final candidate entropy | internal select acc |
|---|---|---|---|---|
| A | 0.252 ± 0.008 | 0.241 | — | — |
| C | 0.749 ± 0.353 | **0.250** (collapse) | 0.076 | 0.543 |
| D-full | 0.990 ± 0.003 | 0.985 | 0.000 | 1.000 |
| **D-10** | 0.981 ± 0.006 | 0.974 | 0.001 | 0.999 |
| **D-25** | 0.989 ± 0.008 | 0.979 | 0.000 | 1.000 |
| **D-50** | 0.985 ± 0.002 | 0.983 | 0.002 | 0.997 |

All three early-only schedules **retain D-full's in-distribution accuracy AND its across-seed
reliability** (every seed ≥ 0.97 — no collapse, unlike Arm C). Binding is established by the
auxiliary and survives its removal: **10% of training with the Quad-native aux is sufficient**.

## Results — preregistered hard conditions (mean acc, 3 seeds)

| condition | A | C | D-full | D-10 | D-25 | D-50 |
|---|---|---|---|---|---|---|
| longer context | 0.247 | **0.723** | 0.122 | 0.155 | 0.113 | 0.112 |
| higher distractor | 0.127 | **0.391** | 0.155 | 0.181 | 0.130 | 0.120 |
| two relation systems | 0.148 | **0.384** | 0.183 | 0.192 | 0.163 | 0.158 |

**No early-only schedule materially improves any hard condition over D-full** (`hard_improved =
[]` for all three). All Quad arms remain far below the generic control C on every condition.
Generalization is **not** recovered by early auxiliary removal.

## Post-cutoff dynamics (the mechanistic finding)

Tracking Arm D-10 (auxiliary OFF after step 250), with **task loss only** thereafter
(representative seed 0; cutoff marked):

| step | aux | val acc | candidate entropy | pos−neg margin |
|---:|:--:|---:|---:|---:|
| 0 | on | 0.031 | 1.380 | −0.01 |
| **250 (cutoff)** | off | 0.629 | 0.010 | 17.8 |
| 500 | off | 0.729 | 0.003 | 25.2 |
| 1000 | off | 0.947 | 0.012 | 34.1 |
| 1750 | off | 0.988 | 0.004 | 49.7 |
| 2499 | off | 0.979 | 0.000 | 52.6 |

After the auxiliary is disabled:

- **the Quad margin continues increasing** (17.8 → 52.6) — final margins across schedules are
  D-10 49.3, D-25 51.2, D-50 47.5, all ≥ D-full's 46.5;
- **candidate entropy continues collapsing** to ~0.000 (it does **not** recover or stabilize);
- **native candidate accuracy remains at ~1.000** (D-10 0.999, D-25 1.000, D-50 0.997);
- **task accuracy remains high** and keeps improving to ~0.98;
- **generalization does not improve** (hard conditions stay at D-full's level).

**Interpretation.** The over-sharpening the hypothesis attributed to *prolonged auxiliary
pressure* is in fact **driven by the task loss itself**, which flows through the model's Quad
attention softmax and keeps pushing the correct-key score apart long after the auxiliary is
removed. Even a 10% auxiliary burst followed by 90% task-only training lands at the identical
near-zero-entropy, high-margin, in-distribution-overfit state as full-duration supervision. The
auxiliary's causal role is confined to **accelerating early binding** (it gets the margin to
~17.8 and accuracy off the chance floor by step 250); it is **not** the cause of the sharpening
or of the generalization failure.

## Primary decision question (per schedule)

| criterion | D-10 | D-25 | D-50 |
|---|:--:|:--:|:--:|
| 1. retains D-full in-distribution accuracy | ✅ | ✅ | ✅ |
| 2. retains across-seed reliability | ✅ | ✅ | ✅ |
| 3. improves ≥ 2 of 3 hard conditions over D-full | ❌ | ❌ | ❌ |
| 4. avoids near-zero-entropy collapse | ❌ | ❌ | ❌ |

## Best early-only Quad arm vs Arm C

Best early-only arm: **D-10** (earliest cutoff that fully retains accuracy and reliability).

| metric | D-10 | Arm C |
|---|---|---|
| in-distribution accuracy | **0.981 ± 0.006** | 0.749 ± 0.353 |
| seed reliability (min seed) | **0.974** (0/3 collapse) | 0.250 (1/3 collapse) |
| longer context | 0.155 | **0.723** |
| higher distractor | 0.181 | **0.391** |
| two systems | 0.192 | **0.384** |
| native Quad candidate-selection acc | **0.999** | 0.543 |
| native Quad candidate entropy | 0.001 (sharp) | 0.076 |

D-10 is clearly better in-distribution and far more reliable, and it shapes the model's actual
retrieval to near-perfect internal selection; but Arm C **generalizes markedly better** on all
three hard conditions. The trade-off is unchanged from the main screen: Quad-native supervision
yields sharper, more reliable in-distribution binding at the cost of out-of-distribution
robustness — and early-only scheduling does **not** move that trade-off, because the sharpening
is task-driven.

## Outcome — **BINDING_GAIN_BUT_GENERALIZATION_NOT_RECOVERED**

Early-only scheduling **retains the primary gain** (in-distribution accuracy and reliability,
with the auxiliary needed only for the first ~10% of training) but **does not materially improve
hard-condition performance**. The specific hypothesis — that continued auxiliary pressure causes
the over-sharpening and the generalization failure — is **refuted**: the near-zero-entropy
collapse persists identically after a 10% cutoff, demonstrating it is produced by the task loss
through the Quad softmax, not by the auxiliary schedule.

**Established claim (only this):** Quad-native auxiliary supervision can act as an *early training
scaffold* for associative binding (≈10% of steps suffices to establish reliable binding that
survives auxiliary removal). Removing it early does **not** reduce the over-sharpening, which is
task-loss-driven, and therefore does not recover generalization. No inference-cost, model-size,
or production-readiness claim is made.

## One evidence-driven next recommendation

The over-sharpening is now localized to **the task loss driving the Quad attention softmax
itself**, not the auxiliary. The single most justified next experiment is therefore to
**soften the deployed Quad retrieval temperature** (train and evaluate with a fixed
`softmax(S^Q / T)` at the attention, `T > 1`, as an architectural constant — *not* an auxiliary
loss, entropy regularizer, or new head), holding everything else frozen, and re-run the three
hard conditions. Rationale: entropy collapses under task pressure because the retrieval softmax
is unconstrained; a higher deployed temperature caps how sharp the model *can* make its
retrieval, directly testing whether the in-distribution binding can be kept while restoring the
softer, better-generalizing behavior exhibited by the off-path control C. This must be
pre-registered (it changes the deployed forward path and therefore is a distinct architecture,
not a training-only regularizer) before running.
