# SCC Observer — Technical Report

**Study:** independent falsification track (CPU-only). Separate package; reuses `qgr`,
`quad_use_evaluator` (`use`), and `quad_perturbation_consistency` (`qpc`) **read-only**. No Quad
production code, MQAR benchmark, model, training/inference pipeline, or previous package modified.
**Date:** 2026-07-22 · Frozen bounded BD-A model, 3 seeds (in-dist acc 1.000) · 5 conditions,
~46k queries, M=4 perturbation views · Data: `RESULTS/scc_results.json`.

**Verdict:** **`SCC_ADDS_INDEPENDENT_SIGNAL` — but through exactly one of the four components (T,
inference stability), and that signal is best understood as test-time-augmentation robustness, not
intrinsic single-pass coherence. S contributes nothing, E is grounded verification re-described,
and R decomposes into task difficulty plus a grounding-like feature.**

> Read-only discipline (tested): inference is bit-identical with and without observation. T runs M
> extra ordinary forward passes on semantically-equivalent views; nothing is retrained or
> regularized. No inference-time control system is built (explicit future scope).

---

## 1. Objective and null

Does SCC carry **independent** predictive information about correctness **beyond confidence,
entailment, and evidence-grounding**? SCC is treated as four separate hypotheses (S, R, E, T);
each must independently justify its existence. **Null:** no component adds predictive value beyond
those baselines. We attempted to reject it component-by-component.

## 2. Design (deliverable 1 — see `DESIGN.md`)

Model = frozen bounded task-only Quad transformer (BD-A). A **claim** is the answer to a query
(`k_q → v_pred`); evidence is the context bindings; correctness is exact (label only). Conditions:
in_distribution (skipped — 0 failures), long_context, distractor_robust, multi_relation,
long_and_hard. Combined predictors use out-of-fold logistic (no leakage); increments tested with
DeLong on the same samples; pre-registered practical threshold **ΔAUROC ≥ 0.005**.

## 3. Component & baseline definitions (deliverables 2–3 — see `scc/`)

S (representation cosines), R (structural relational), E (closed-world symbolic evidence), T
(prediction stability over M semantically-equivalent views). Baselines: A confidence (reused),
B entailment proxy, C grounding (symbolic evidence verifier — a **closed-world near-oracle**).

## 4. Predictive performance (deliverable 4) — AUROC

| condition (fail%) | confidence | conf+ground | intrinsic S+R+T | conf+S+R+T | full SCC (S+R+E+T) |
|---|---:|---:|---:|---:|---:|
| long_context (6.5%) | 0.944 | 1.000 | 0.968 | 0.989 | 1.000 |
| distractor_robust (45%) | 0.914 | 1.000 | 0.781 | 0.949 | 1.000 |
| multi_relation (44%) | 0.831 | 0.904 | 0.739 | 0.897 | 0.976 |
| long_and_hard (49%) | 0.902 | 1.000 | 0.823 | 0.947 | 1.000 |
| **pooled** | **0.824** | 0.964 | 0.837 | 0.924 | 0.996 |

`conf+ground` and every arm containing E/grounding reach ~1.0 because **closed-world grounded
verification is a near-oracle** — it recomputes the answer from the evidence. That is verification,
not coherence, and it is why "beating grounding" is not the meaningful bar for the intrinsic terms.

## 5. Statistical significance (deliverable 5) — incremental DeLong, pooled

| term added | over confidence | over conf+entail (intrinsic bar) | over conf+entail+grounding |
|---|---:|---:|---:|
| S | −0.001 (ns) | +0.001 (ns) | +0.002 (ns) |
| R | +0.074 *** | +0.072 *** | +0.032 *** |
| E | +0.140 *** | +0.139 *** | +0.001 (ns) |
| **T** | **+0.047 *** | **+0.047 *** | +0.004 (ns) |

Per-condition and per-seed (the reproducibility that decides survival):

* **T survives in ALL 4 conditions and ALL 3 seeds** over confidence+entailment (+0.019 to +0.042
  per condition; +0.041/+0.041/+0.054 per seed). This is a genuine, reproducible, per-instance
  increment.
* **R survives in 3/4 conditions and 3/3 seeds** over confidence+entailment — but see §7: its
  signal is not independent relational coherence.
* **S** survives 0/3 seeds — dead.
* **E** adds massively over confidence but **+0.001 (ns) over grounding** — it *is* grounding.

## 6. Calibration (deliverable 6) — pooled

| predictor | AUROC | Brier | ECE |
|---|---:|---:|---:|
| confidence | 0.824 | 0.163 | 0.040 |
| conf+ground+T | 0.968 | 0.044 | 0.008 |
| conf + S+R+T (intrinsic) | 0.924 | 0.109 | 0.018 |
| conf+ground+full SCC | 0.997 | 0.022 | 0.004 |

Discrimination and calibration improve together when T (and the grounding oracle) are added — this
is not a calibrated-but-uninformative case. The intrinsic (conf+S+R+T) predictor genuinely raises
AUROC 0.824 → 0.924 and lowers Brier 0.163 → 0.109, **almost entirely via T** (see ablation).

## 7. Ablation & redundancy (deliverable 7) — what each term actually is

**S — fails.** Best feature AUROC 0.512 (chance). Its one non-trivial feature (`S_vpred_vretr_cos`)
has correlation **0.98 with the entailment proxy** — where S is not chance, it is entailment.

**E — grounded verification re-described.** `E_adjacency_support`/`E_support_count` AUROC 0.935
with **correlation 1.00 to grounding**; incremental over grounding **+0.001 (ns)**. In a closed
world E and grounding are the same symbolic binding check — a near-oracle, not coherence.

**R — task difficulty + grounding, not relational coherence.** Its strongest feature,
`R_num_candidates` (AUROC 0.633), is **constant within every condition** — it can only separate
conditions of different difficulty, a pooling artifact. Its per-condition signal comes from
`R_pred_is_ctx_value` (**correlation 1.00 with grounding** — a weak evidence check) and a
multi_relation-specific term; over the full baseline (incl. grounding) R adds nothing except in
multi_relation (+0.072). R is **not** an independent relational-coherence signal.

**T — real, reproducible, but it is augmentation-ensemble stability.** `T_prob_mean` (0.774),
`T_flip_rate` (0.744), `T_prob_std` (0.743) each carry signal with **only ~0.29 correlation to
single-view confidence**, so T adds beyond the confidence baseline. Mechanistically, however, T is
computed by running the model on M reordered/augmented copies and measuring how stable the answer /
its probability is — i.e. **test-time-augmentation ensembled confidence and behavioural
robustness**, not an intrinsic property of a single completed inference. It genuinely predicts
failure (a confidently-wrong answer that flips under benign reordering is more likely wrong), and
it is independent of the *implemented* single-view baselines — but a TTA-confidence baseline (M-view
averaged entropy) would likely absorb most of it.

## 8. Failure-case analysis (deliverable 8)

* **Where T wins over confidence:** confidently-wrong answers that are *unstable* — the single-view
  probability is high (confidence says "correct") but the answer flips across reorderings (T says
  "unreliable"). These are exactly the high-confidence errors confidence alone misses.
* **Where nothing intrinsic helps:** long_context has only 6.5% failures and confidence already
  reaches 0.944; the intrinsic terms add little headroom.
* **Where grounding trivially wins:** every single-relation condition — the symbolic verifier
  reconstructs the binding and hits AUROC 1.0. This dominates but is verification, not coherence.
* **S false alarms:** S is near-chance, so as a gate it would abstain/flag essentially at random.

## 9. Mechanistic interpretation (deliverable 9)

Three distinct signals are conflated by the SCC framing, and this study separates them:

1. **Grounded verification (E, C).** With machine-checkable evidence, checking the claim against
   the context is a near-oracle. This is the strongest predictor by far — and it is not coherence;
   it is looking up the answer. It also requires the evidence to be available and parseable (the
   closed-world premise); the open-world version needs external grounding and is out of scope.
2. **Confidence, measured robustly (T).** Perturbation stability is the model's own confidence
   sampled over augmentations. It adds over single-view confidence because a single softmax
   underestimates the volatility of some high-confidence errors. Real and reproducible, but a form
   of confidence, not a new semantic quantity.
3. **Intrinsic representation coherence (S, and the coherence part of R).** This is the actual
   "semantic coherence" hypothesis — and it is **at chance** (S 0.51; R's independent part null).
   The USE study reached the same conclusion for phase coherence; here embedding/relational
   coherence fares no better.

This corrects a prediction from the prior design review, which expected T to be at chance: T in
fact carries a modest, reproducible signal — but as ensemble-confidence/robustness, exactly the
component that is *not* intrinsic coherence. The intrinsic-coherence hypotheses (S, and R's
coherence component) remain falsified.

## 10. Recommendation (deliverable 10)

**Do not advance an "intrinsic semantic coherence" evaluator (S, R) — those components carry no
independent signal.** The two things that predict correctness here are (a) **grounded verification**
(near-oracle, but that is answer-checking against evidence, a different and well-understood problem
that needs available evidence) and (b) **prediction stability under perturbation (T)**, a real,
reproducible, modest increment over single-view confidence that is mechanistically test-time
augmentation.

If a post-inference failure flag is wanted, the evidence supports exactly one *coherence-adjacent*
lever worth pursuing as a **separate** future track: **T as a test-time-augmentation stability
score**, benchmarked honestly against a **TTA-confidence baseline** (M-view averaged entropy), a
domain-calibrated three-way (accept / verify / abstain) policy, and cost accounting for the M extra
inferences. S, R (beyond difficulty), and E-as-coherence should be dropped. E-as-verification is
useful only where external, parseable evidence exists — i.e. it is grounding, and should be
labelled as such, not as SCC coherence.

**Bottom line:** SCC is not a unified coherence controller. One of its four components (T) adds
independent predictive value, but as robust confidence rather than semantic coherence; the genuine
intrinsic-coherence claims (S, R) are falsified, and E is a re-description of grounded verification.

## Reproduction

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q
OMP_NUM_THREADS=4 python run_scc.py --threads 4 --seeds 0 1 2 --n-batches 30 --M 4
python summarize_results.py
```

Artifacts: `RESULTS/scc_results.json` (arms, per-condition/per-seed increments, redundancy,
calibration, verdict) and `plots/` (arms by condition, incremental ΔAUROC, term-alone, reliability).
Deterministic given the seeds.
