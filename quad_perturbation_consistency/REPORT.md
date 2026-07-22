# Same-Head Perturbation-Consistency for Quad Retrieval — Technical Report

**Study:** independent falsification track (CPU-only). Separate package; reuses the prior
`quad_generative_regularization` (`qgr`) package **read-only**. No production code or previous
research package was modified.
**Date:** 2026-07-22 · Frozen bounded geometry (α=4) · λ frozen on disjoint pilot seeds ·
10 confirmatory seeds · Data: `RESULTS/`.

**Verdict:** **NULL NOT REJECTED — perturbation-consistency provides no net generalization
benefit over the task-only baseline (BD-A).** Both guardrails hold; the hypothesis is falsified.

> Scope discipline (as in the prior studies): this evaluates a **training-time Quad-native
> regularizer**. No USE/phase/synchronization, no entropy/temperature/normalization penalties, no
> architecture or inference change, no retrieval labels, no cross-head/-layer sync, no routing, no
> teacher forcing. The consistency term is read from the model's own forward-path Quad score and
> adds no inference operation (λ=0 is bit-identical to BD-A — `tests/test_equivalence.py`).

---

## 1. Hypothesis and null

**Hypothesis (H1, to be falsified):** generalization is governed not by *which* key Quad
retrieves but by *how invariant* the learned retrieval function is under benign perturbations; a
same-head consistency objective (no labels) should therefore improve generalization beyond BD-A.

**Null (H0):** task-only learning already discovers the best retrieval organization; any explicit
consistency objective does not improve (or reduces) generalization vs BD-A.

We attempted to reject H0. **We could not.** On the clean generalization comparison BD-Sync is if
anything slightly *worse* than BD-A, and — decisively — BD-Sync achieved a large increase in the
very quantity H1 nominates as causal (retrieval invariance) with **no** generalization payoff.

## 2. Method (deliverable 2 — see `qpc/`)

Each step takes the standard batch (view **O**) and builds one semantically-equivalent view **P**
that changes only irrelevant surface factors (pair/distractor order, distractor position,
additional irrelevant distractors, query order, a leading positional shift); every key→value
association and query→answer is preserved. For each head *h* and query, the head's candidate
distribution (softmax of `S^Q` over the candidate keys) on O is matched to its distribution on P
via **symmetric Jensen-Shannon divergence** with a **stop-gradient** target and a **small fixed
coefficient** λ; alignment is by **token identity** (no retrieval labels). `L = L_task(O) + λ·JS`.
BD-Sync is a *pure add-on* to BD-A (bit-identical at λ=0).

## 3. Experimental design (deliverable 1 — see `DESIGN.md`)

Five arms, all bounded, benchmark = **BD-A**:

| Arm | Definition | Role |
|---|---|---|
| **BD-A** | task-only | benchmark (prior best generalizer) |
| **BD-D** | + Quad auxiliary (retrieval labels) | existing auxiliary baseline |
| **BD-Sync** | + λ·same-head JS consistency (full) | proposed |
| **BD-Sync-Early** | consistency only first 10% of steps | schedule variant |
| **BD-Shuffled** | same machinery, key alignment randomly permuted | generic-regularization control |

λ frozen at **0.3** by a pilot on **disjoint** seeds (100–101), chosen as the *most favorable*
health-clean value (highest mean-hard) — the method's best honest shot (`PILOT_RECORD.md`).
Confirmatory seeds: 0–9.

## 4. Benchmark results (deliverable 3) — 10 seeds, mean ± sd

| arm | in-dist | mean-hard | longer context | higher distractor | two systems |
|---|---:|---:|---:|---:|---:|
| BD-A | 0.850 ± 0.300 | 0.574 ± 0.202 | 0.770 | 0.473 | 0.478 |
| BD-D | 0.996 ± 0.009 | 0.185 ± 0.165 | 0.094 | 0.217 | 0.244 |
| **BD-Sync** | **1.000 ± 0.000** | 0.657 ± 0.021 | 0.871 | 0.549 | 0.550 |
| BD-Sync-Early | 1.000 ± 0.000 | 0.670 ± 0.021 | 0.893 | 0.556 | 0.561 |
| BD-Shuffled | 1.000 ± 0.000 | 0.645 ± 0.059 | 0.905 | 0.507 | 0.523 |

The raw means are **confounded by convergence**: BD-A's low mean and huge sd come from **two
seeds (6, 9) where the bounded task-only model failed to learn the task** (in-dist 0.262 / 0.237).
The clean generalization question requires conditioning on both arms having learned the task.

### 4.1 Convergence reliability (a training effect, not a generalization effect)

| arm | seeds reaching in-dist ≥ 0.95 |
|---|:--:|
| BD-A | **8 / 10** |
| BD-D | 10 / 10 |
| BD-Sync | 10 / 10 |
| BD-Sync-Early | 10 / 10 |
| BD-Shuffled | 10 / 10 |

Every arm that adds *any* auxiliary term — **including the semantically-scrambled BD-Shuffled and
the label-based BD-D** — converged on all 10 seeds; task-only BD-A failed on 2. So the extra
gradient signal **stabilizes optimization**, but this is **generic** (the shuffled control does it
too), not a property of *semantic* consistency.

### 4.2 Clean generalization — converged subset (8 seeds where both arms learned)

| arm vs BD-A | mean Δ | median Δ | seeds +/− | Wilcoxon p (greater) | bootstrap 95% CI |
|---|---:|---:|:--:|---:|---:|
| **BD-Sync** | **−0.016** | **−0.024** | **1 / 7** | **0.926** | [−0.031, +0.003] |
| BD-Sync-Early | −0.001 | −0.005 | 3 / 5 | 0.691 | [−0.017, +0.018] |
| BD-Shuffled | −0.019 | +0.006 | 5 / 3 | 0.371 | [−0.075, +0.021] |
| BD-D | −0.474 | −0.552 | 0 / 8 | 1.000 | [−0.563, −0.339] |

On the clean comparison **BD-Sync is worse than BD-A on 7 of 8 seeds** (median −0.024). It does
not beat BD-A; if anything it slightly regresses.

## 5. Statistical significance (deliverable 7)

Full 10-seed paired test (mean-hard, BD-Sync vs BD-A): mean Δ = **+0.083**, **median Δ = −0.016**,
seeds +/− = **3/7**, one-sided **Wilcoxon p = 0.539** (not significant), paired-t one-sided
p = 0.122, bootstrap 95% CI **[−0.023, +0.228] (includes 0)**. The positive *mean* is an artifact
of the two BD-A-non-converged seeds (Δ = +0.465, +0.496); the rank-based Wilcoxon and the negative
median correctly reflect that BD-Sync does not improve the typical seed. **Pre-registered decision
(Wilcoxon p<0.05 AND CI excludes 0 AND mean Δ≥0.02 AND guardrails): NOT MET → H0 not rejected.**

**Shuffled-pair control (the key semantic test).** BD-Shuffled's mean Δ vs BD-A (+0.071) is
statistically indistinguishable from BD-Sync's (+0.083), and both are non-significant. Whatever
tiny mean effect exists is **reproduced by the semantically-scrambled control**, so it is **not
attributable to semantic consistency** — it is generic regularization / optimization stabilization.

## 6. Progressive perturbation analysis (deliverable 4) — `plots/progressive_*.png`

Perturbation stability (1 − JS/logC; higher = more invariant) across the escalating progression:

| arm | original | small shift | distractor permute | +distractors | longer context | multi-system |
|---|---:|---:|---:|---:|---:|---:|
| BD-A | 1.000 | 0.951 | 0.976 | 0.976 | 0.942 | 0.945 |
| **BD-Sync** | 1.000 | **0.988** | **0.999** | **0.995** | **0.986** | **0.983** |
| BD-Sync-Early | 1.000 | 0.959 | 0.991 | 0.990 | 0.956 | 0.953 |
| BD-Shuffled | 1.000 | 0.955 | 1.000 | 1.000 | 0.955 | 0.955 |
| BD-D | 1.000 | 0.990 | 0.999 | 0.999 | 0.991 | 0.981 |

**Manipulation check passes:** BD-Sync is the most perturbation-stable healthy arm at *every*
level — the objective did exactly what it was designed to do, degrading least across the whole
progression. And retrieval stability (argmax-key unchanged under perturbation) rises from BD-A's
**0.311** to BD-Sync's **0.838**. **Yet generalization did not improve.** The hypothesized causal
factor (invariance) was moved decisively in the predicted direction with no generalization benefit.

## 7. Entropy / diversity / specialization analysis (deliverable 5) — `plots/attention_health.png`

| arm | attn entropy (norm) | head diversity (JS) | specialization (sel-std) | head-mean select acc | perturb stability | retrieval stability |
|---|---:|---:|---:|---:|---:|---:|
| BD-A | 0.937 | 0.009 | 0.014 | 0.285 | 0.942 | 0.311 |
| BD-D | 0.144 | 0.001 | 0.000 | 1.000 | 0.990 | 0.998 |
| **BD-Sync** | 0.670 | **0.185** | **0.077** | 0.118 | 0.988 | 0.838 |
| BD-Sync-Early | 0.936 | 0.005 | 0.016 | 0.129 | 0.955 | 0.506 |
| BD-Shuffled | 1.000 | 0.000 | 0.020 | 0.232 | 0.954 | 0.330 |

Mechanistically informative:
* **BD-A** lives in a near-uniform, low-diversity attention regime (entropy 0.94, diversity 0.009,
  near-chance head-mean selection) yet generalizes best — matching the prior causal finding that
  BD-A binds through attention in a distributed way the head-mean selector does not capture.
* **BD-Sync** makes attention *more* structured and differentiated — it **raises** head diversity
  (0.009 → 0.185, the highest of any arm) and specialization, and lowers entropy — and yet
  generalization is unchanged/slightly worse. Making retrieval more consistent and heads more
  specialized is **not** the direction that helps.
* **BD-Shuffled** collapses candidate attention to **perfectly uniform** (entropy 1.000, diversity
  0): under a *random* key-identity target the only invariant distribution is the uniform one, so
  the model drives attention there. This is the mechanistically-expected control degeneracy and is
  why the shuffled control is the correct semantic control.
* **BD-D** is the opposite pathology: entropy collapse to a single key (0.144), diversity 0,
  selection 1.0 — the over-fit retrieval the prior work identified.

## 8. Causal verification / Guardrail 1 (deliverable 6) — `plots/causal_necessity.png`

Zeroing the Quad-retrieval (attention) output at both layers, in-distribution (chance ≈ 0.25):

| arm | clean | attn zeroed (all) | retained | collapses to chance |
|---|---:|---:|---:|:--:|
| BD-A | 0.851 | 0.063 | 0.10 | ✅ |
| BD-D | 0.996 | 0.066 | 0.07 | ✅ |
| **BD-Sync** | 1.000 | 0.060 | 0.06 | ✅ |
| BD-Sync-Early | 1.000 | 0.064 | 0.06 | ✅ |
| BD-Shuffled | 1.000 | 0.061 | 0.06 | ✅ |

**Guardrail 1 holds for every arm, BD-Sync included:** removing Quad retrieval collapses accuracy
below chance. The consistency objective does **not** move binding off the Quad retrieval — Quad
remains causally necessary, so the BD-Sync-vs-BD-A comparison is valid.

## 9. Guardrail 2 (attention health) — per-seed healthy flags

| arm | seeds healthy | note |
|---|:--:|---|
| **BD-Sync** | **10 / 10** | healthiest arm: highest diversity/specialization, entropy far from both collapse and uniform |
| BD-A | 9 / 10 | one seed flagged (near-uniform regime) — the flag reflects the bounded regime, not consistency |
| BD-Sync-Early | 2 / 10 | near-uniform/low-diversity like BD-A |
| BD-Shuffled | 0 / 10 | uniform-attention collapse (control degeneracy) |
| BD-D | 0 / 10 | entropy/head collapse (over-fit retrieval) |

BD-Sync passes Guardrail 2 on all seeds. Health flags at the pre-registered thresholds also fire
for BD-A itself (1 seed), confirming they track the near-uniform bounded regime rather than a
consistency-induced pathology; BD-Sync is strictly *further* from the flagged degeneracies than
BD-A.

## 10. Failure-case analysis (deliverable 8)

* **The two "wins" are training rescues, not generalization gains.** The only seeds where BD-Sync
  beats BD-A by more than noise are exactly the two where BD-A failed to converge (6, 9). There,
  BD-Sync's advantage is +0.47/+0.50 — but this is the difference between "learned the task" and
  "did not," not better generalization of a learned retrieval function. The **shuffled control and
  BD-D rescue the same seeds**, proving the rescue is generic optimization stabilization.
* **Where both learn, consistency slightly hurts** (7/8 seeds negative). Pushing the retrieval to
  be more perturbation-invariant trades away a little of BD-A's distributed, high-entropy solution
  that generalizes best.
* **BD-Sync-Early ≈ BD-A** (median Δ −0.005): a brief early consistency phase neither helps nor
  hurts generalization and leaves attention in BD-A's regime — consistent with the effect being
  optimization-phase stabilization, not a durable representational change.
* **No catastrophic failure of BD-Sync**: it converged on all seeds, stayed causal, stayed healthy.
  It is *safe* but *not beneficial* for generalization.

## 11. Mechanistic interpretation (deliverable 9)

The experiment cleanly separates two things the raw means conflate:

1. **Optimization stabilization (generic).** Any auxiliary gradient — semantic, scrambled, or
   label-based — makes the bounded model converge more reliably (10/10 vs 8/10). This is not about
   retrieval organization; it is extra curvature/signal that helps the optimizer escape the ~20%
   of inits where bounded task-only stalls.
2. **Retrieval invariance (the hypothesis's lever).** BD-Sync demonstrably *increased* retrieval
   invariance a lot (retrieval stability 0.31 → 0.84; most stable arm at every progression level)
   and made heads more diverse/specialized — and this produced **no** generalization improvement,
   slightly regressing on converged seeds.

Therefore **invariance of the retrieval function is not the governing factor for generalization**
in this system, or at least it cannot be *added* by an explicit consistency objective to exceed
BD-A. This is consistent with, and sharpens, the prior program's finding: generalization tracks
*how binding is carried* (BD-A's distributed, high-entropy, near-chance-head-mean solution
generalizes best; forcing structure onto the retrieval — whether via labels (BD-D) or via
consistency (BD-Sync) — does not help and can hurt). H1 mislocates the causal variable: the
problem was never "make the retrieval more invariant."

## 12. Final recommendation (deliverable 10)

**Do not adopt perturbation-consistency, and do not use it to replace explicit Quad auxiliary
supervision on the grounds of generalization.** Neither BD-Sync nor BD-D beats the task-only
baseline BD-A on generalization; BD-D is far worse, and BD-Sync is at best neutral (slightly worse
where the task is learned) with its only measurable benefit — training reliability — being generic
(reproduced by the semantically-scrambled control). The null hypothesis stands: **task-only
learning already discovers the best-generalizing retrieval organization available to this model,
and an explicit consistency objective does not improve it.**

If a follow-up is warranted, the evidence points *away* from "shape the retrieval" objectives
altogether and toward the earlier open question — *which component should carry associative
binding* — since every intervention that pushes structure onto the Quad retrieval selector
(labels, or now invariance) fails to beat the distributed task-only solution. A separate, minor,
genuinely-supported result is that a small auxiliary gradient improves bounded-model **convergence
reliability**; if that (not generalization) is the goal, the cheapest generic regularizer suffices
— semantic consistency is unnecessary.

## Reproduction

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q                       # 19 tests (incl. λ=0 ≡ BD-A)
OMP_NUM_THREADS=4 python run_pilot.py --threads 4                  # freeze λ (disjoint seeds)
OMP_NUM_THREADS=4 python run_consistency.py --threads 4 --seeds 0 1 2 3 4 5 6 7 8 9
python summarize_results.py                                        # report tables
```

Artifacts: `RESULTS/consistency_results.json`, `consistency_results.csv`,
`supplementary_analysis.json` (converged-subset + reliability), `pilot.json`, and `plots/`
(generalization, paired-delta, progressive consistency/accuracy, attention health, causal
necessity). Deterministic given the frozen config and seeds.
