# Quad Generative Regularization — Final Technical Report

**Study:** CPU-only falsification of Quad-native training regularization (v1.3)
**Date:** 2026-07-22 · **Compute:** CPU-only, 4 threads · **Benchmark:** MQAR
**Overall 3-seed verdict:** **MIXED** (mechanism **LIMITED**, generalization **ABSENT**, economics **NOT_MEASURED**)

> This experiment evaluates **Quad-native training regularization**. It does not implement or
> test USE phase or synchronization mechanisms.

---

## 1. Exact Quad mechanism implemented

The authentic Quad generative score of the canonical `BindingCacheQuadQuery`:

```
S^Q_{i,j} = ( W_q · LN_q(h_i) ) · ( W_k · LN_m(h_j) ) / sqrt(d_h)      (causal: j ≤ i)
```

per head `[B,H,N,N]`, causally masked, candidate-comparable, consumed generatively
(softmax/Top-K over candidate keys). This study uses the **phase-free separable core**
(`memory_state := hidden states`), the exact subset identified by the Phase-0 compatibility
gate. The deployed model is a 2-layer causal transformer whose attention *is* this Quad
scorer; the score tensor `S^Q` is exposed for the training-only auxiliary loss.

## 2. Source paths and version identifiers

- Authoritative code: `symbolu/phase_transformer.py:3507` (`BindingCacheQuadQuery`), mirror
  `symbolu_core/phase_transformer.py:3507`.
- Authoritative spec: `docs/PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md` V11.0, §4 "Path 2 — Quad
  Proposal" (declares the class canonical, "Status: Production").
- Repo commit at study start: `8fb8170`. Full trace: `QUAD_TRACEABILITY.md`.

## 3. Is Quad separable from phase? — YES

The scoring is pure scaled dot product; it contains no phase/Kuramoto/phasor operation. Phase,
in production, only supplies the memory tensor (K/V source) and a selection-only salience bias.
Feeding hidden states as the memory tensor yields a complete, valid Quad score with zero phase
code. (Compatibility gate Q1; corroborated by the phase-free `QuadraticBindingHead` control in
`resonant_model/heads.py`.)

## 4. Does Quad natively expose the required relational score? — YES

`S^Q[b,h,i,j]` is a native, causal (`j ≤ i`), candidate-comparable query×key matrix, returned
pre-softmax by `get_proposals`. No transformation is required; the auxiliary objective
(Option B) normalizes it over the causally-visible candidate keys exactly as Quad does
internally. Compatibility gate: all four questions YES → the experiment proceeded.

## 5. Files created

Self-contained package `quad_generative_regularization/` (no production code modified):
`qgr/quad_model.py`, `qgr/mqar.py`, `qgr/losses.py`, `qgr/train.py`, `qgr/metrics.py`,
`qgr/experiment.py`, `qgr/plotting.py`, `qgr/__init__.py`; `tests/` (6 files); `run_screen.py`;
`configs/frozen.json`; docs `QUAD_TRACEABILITY.md`, `PILOT_RECORD.md`, `README.md`, this report;
`RESULTS/` (results.json, results.csv, plots/, screen_run.log).

## 6. Tests and pass/fail counts

**21 / 21 passing** (spec §22 items 1-19), covering: deterministic MQAR generation; key/value/
query labels; query→earlier-key positive; negative-candidate construction; all candidates
precede the query; train/val/test disjointness; strict causal masking; no future-token leakage;
future-shuffle invariance; Quad score shape; candidate filtering; aux loss lower when correct
key preferred; nonzero aux gradient into shared params; zero aux contribution at λ=0; **A vs D0
bit-identical equivalence**; inference invariance with aux disabled; identical base architecture
across arms; deterministic repeat under a seed; tiny-overfit for Arms A/C/D.

## 7. Frozen experiment configuration

Model: 2 layers, hidden 96, 4 heads, ff 384, context 64, dropout 0, vocab 32, ~236k params (235,776)
(identical across arms). MQAR base: num_kv 4, num_queries 2, 1 relation system (baseline
capability boundary — baseline solves kv≤3 and overfits kv=4 but cannot learn kv=4 from
streaming data in-budget; `PILOT_RECORD.md`). Training: 2500 steps, batch 32, AdamW lr 4e-3
(warmup 50), grad-clip 1.0, shared across arms. Auxiliary: Option B classification, **λ=1.0,
τ=1.0** (frozen in the pilot). Screen seeds: {0,1,2}. Full config: `configs/frozen.json`.

## 8. Results — every arm and seed (equal-token)

In-distribution MQAR exact-match accuracy (val, 2500 steps):

| seed | Arm A | Arm C | Arm D |
|-----:|------:|------:|------:|
| 0 | 0.261 | 0.997 | 0.993 |
| 1 | 0.241 | **0.250** | 0.985 |
| 2 | 0.255 | 1.000 | 0.992 |
| **mean ± sd** | **0.252 ± 0.008** | **0.749 ± 0.353** | **0.990 ± 0.003** |

Final validation task loss (mean): A 1.570 · C 0.508 · D 0.043.
Steps to 0.80 accuracy: A **never** (all seeds); C 250 (seeds 0,2), **never** (seed 1); D
500–750 (**all** seeds). CPU time/step: A 12.9 ms · C 13.9 ms · D 10.9 ms (shared-CPU noise;
aux overhead is small — see §13).

**Headline:** both auxiliary arms lift the baseline off its chance-level plateau (0.25 → ~0.99),
but they differ in **reliability**: Arm D solves the task on **all three seeds** (σ=0.003),
whereas Arm C **collapses to chance on seed 1** (σ=0.353). When C succeeds (seeds 0,2) it ties
D. Arm D's mean exceeds C's mean **only because of C's single-seed collapse**, not a per-seed
accuracy advantage.

## 9. Arm C vs Arm D comparison (the primary scientific question)

Per-seed, when both train successfully (seeds 0, 2), **C and D are statistically
indistinguishable** on in-distribution accuracy (C 0.997/1.000 vs D 0.993/0.992). Arm D does
**not** repeatably beat Arm C on the primary metric. Therefore, on peak capability, the data do
**not** demonstrate a Quad-specific advantage over generic relational supervision.

The one respect in which D differs from C is **robustness**: D never failed a seed; C failed
1/3. This is a genuine but secondary signal (reliability, not peak accuracy), and three seeds
are too few to establish it as a repeatable effect. It is reported as an observation, not a
supported claim.

## 10. Evidence that auxiliary gradients reached the shared model

Gradient diagnostics (separate task vs aux backward on a fixed minibatch, shared params only):
Arm D's auxiliary gradient norm is **nonzero across all seeds and checkpoints**
(`grad_reaches_shared = True`); aux/task norm ratio ≈ 0.37 early, decaying as the score
saturates; gradient cosine small-positive. Mechanistic confirmation on the Quad score itself
(test split, mean over seeds):

| metric (model's own Quad score) | Arm C | Arm D |
|---|---:|---:|
| correct-key score | −9.0 | **45.2** |
| incorrect-key score | −31.2 | −1.3 |
| correct−incorrect margin | 22.2 | **46.5** |
| candidate entropy | 0.076 | **0.000** |
| internal candidate-selection acc | **0.543** | **1.000** |

Arm D directly drives the model's **forward-path** Quad score to perfect internal selection
(1.000); Arm C, supervising an **off-path** relation, leaves the model's actual retrieval at
0.54 (dragged by the seed-1 failure). This mechanistically explains D's reliability: it shapes
the score the model actually uses, not a proxy.

## 11. Leakage findings

All leakage/validity checks pass: **A vs D0 bit-identical** (max param diff 0.00e+00);
**future-token shuffle invariance** of `S^Q` over `j ≤ i` (max diff 0.00e+00); **inference
identical** with aux-only objects disabled; all candidates strictly precede the query; strict
causal masking; disjoint train/val/test seeds. No causal, deterministic, or implementation
failure was detected.

## 12. Equal-token convergence results

At equal optimizer steps / examples / tokens (2500 steps): A never crosses 0.80; D crosses at
500–750 on every seed; C crosses at 250 when it trains but never on seed 1. Task loss orders
D (0.043) < C (0.508) < A (1.570). Quad-native supervision yields the fastest *and* most
reliable convergence to the answer, though generic supervision converges just as fast on the
seeds where it succeeds.

## 13. Total-cost findings

This screen is an **equal-token** comparison (capability/convergence). The equal-wall-clock
comparison (spec §23.2) is a conditional follow-up and was **not** run (the positive-signal gate
did not pass). Measured per-step times are within shared-CPU scheduling noise (A 12.9, C 13.9,
D 10.9 ms); the auxiliary loss adds one head-mean + masked cross-entropy over `[B,N,N]`, a small
overhead. **No cost-savings claim is made** (spec §30): a higher-quality/more-reliable model at
comparable per-step cost is a capability/robustness gain, not a demonstrated cost saving.
Economics: **NOT_MEASURED**.

## 14. Mechanism classification — **LIMITED**

Arm D repeatably beats Arm A (3/3 seeds, large margin), but does **not** repeatably beat Arm C
on the primary accuracy metric (they tie when C trains). Per spec §24.1: *relational auxiliary
supervision helps, but the experiment does not demonstrate a specific advantage from Quad-native
regularization.* (A robustness advantage for D is observed but not established at n=3.)

## 15. Generalization classification — **ABSENT**

Zero-shot accuracy on the three preregistered hard conditions (mean over seeds):

| condition | Arm A | Arm C | Arm D |
|---|---:|---:|---:|
| longer context (32 filler) | 0.247 | 0.723 | **0.122** |
| higher distractor (kv=8) | 0.127 | 0.391 | 0.155 |
| two relation systems | 0.148 | 0.384 | 0.183 |

Arm D does **not** improve any preregistered hard condition over Arm A — it **regresses** on
longer context (0.12 < 0.25). Quad-native supervision drives the score to a sharp, near-
deterministic in-distribution selection (entropy → 0), which **overfits the training regime and
fails to generalize**. Notably, the *generic* control (C) generalizes better than D on all three
conditions. Generalization for the proposed method is **ABSENT**.

## 16. Economics classification — **NOT_MEASURED**

Equal-wall-clock not run (conditional on a positive signal). No cost-saving claim.

## 17. Overall verdict — **MIXED** (3-seed screen)

Positive-signal gate (spec §17): criteria 1 (same-direction 3/3 ✓), 2 (D−A meaningful ✓),
3 (mean D > mean C ✓ — but only via C's seed-1 collapse), 6 (aux grad reaches shared ✓) pass;
criterion 4 (improves ≥1 hard condition) **fails**. Not all criteria met → **MIXED**, not
PROMISING_SIGNAL. Consequently the five-seed confirmation and the conditional controls
(shuffled-label, etc.) were **not** triggered (protocol-correct). No validity failure exists, so
the screen is not INVALID.

**Plain statement:** Auxiliary relational supervision — whether generic (C) or Quad-native (D) —
lets a small transformer learn a binding task its task-loss-only baseline cannot (0.25 → ~0.99).
Quad-native supervision is the more *reliable* of the two (0/3 vs 1/3 seed failures) and shapes
the model's actual retrieval to perfect internal selection, but it shows **no peak-accuracy
advantage over generic relational supervision** and **generalizes worse** to harder retrieval
conditions. The Quad-native hypothesis is therefore **not** supported as a distinct capability
gain at this configuration; it is a reliability/optimization convenience whose sharpness costs
out-of-distribution robustness.

## 18. The single most justified next experiment

**Add a temperature/entropy floor (or early-stop the aux at ~25% of training, spec §21.4) to the
Quad-native objective and re-run the three preregistered hard conditions.** Rationale: the data
localize D's failure precisely — D achieves perfect in-distribution internal selection
(entropy → 0, margin 46) but regresses out-of-distribution because the score is driven too
sharp. The generic control C, with a softer relation, generalizes better. The highest-value,
most-targeted follow-up is to test whether a **less saturated** Quad-native signal (higher τ, an
entropy regularizer on `S^Q`, or an early-only aux schedule) recovers C-level (or better)
generalization while keeping D's reliability — directly probing whether the Quad-native
advantage is real once its over-sharpening is controlled. This must be pre-registered before
running, since τ was frozen in this study.

---

## Limitations

- **Three seeds** — the screen is a signal detector, not a confirmation; C's seed-1 collapse
  and D's robustness edge both need ≥5 seeds to establish. The gate correctly withheld the
  5-seed confirmation.
- **Single frozen configuration** at the spec-recommended hidden size 96. An **exploratory**
  (not preregistered) observation at hidden 64 showed D *out-performing* C — the C-vs-D relation
  is capacity-dependent. This was deliberately **not** adopted as the headline config to avoid
  results-driven redefinition of success (`PILOT_RECORD.md` §5).
- **Baseline at capability boundary** — Arm A sits at chance on the base task (it solves easier
  kv≤3 and overfits kv=4); the study measures capability *unlock*, not speed-up on an already-
  learnable baseline. Valid (tiny-overfit passes) but a specific regime.
- **Phase-free reduction** — Quad is instantiated with `memory_state := hidden states`, the
  separable core. Results speak to that reduction, not to Quad coupled to a phase memory.
- **CPU/small scale** — no claim transfers to GPU or large models; per spec §30, GPU work is not
  recommended, since the CPU screen did not demonstrate a repeatable Quad-specific advantage
  beyond generic relational supervision.
