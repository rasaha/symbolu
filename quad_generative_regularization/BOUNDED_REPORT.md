# Bounded Quad Retrieval Geometry — Technical Report

**Study:** Quad Generative Regularization, bounded-geometry experiment (CPU-only)
**Date:** 2026-07-22 · Frozen config, α=4, 3 seeds · Data: `RESULTS_BOUNDED/`
**Outcome category:** **BINDING_RETAINED_GENERALIZATION_LIMITED**

> This experiment evaluates **Quad-native training regularization**. It does not implement or
> test USE phase or synchronization mechanisms. No entropy/margin/confidence penalties, learnable
> temperature, auxiliary heads, phase logic, synchronization, or teacher models were added — the
> only architectural change is L2-normalization of the authentic projected Quad query/key plus a
> fixed non-learnable scale α.

## Hypothesis under test (not assumed)

*Bounding the magnitude of the Quad retrieval score (|S^Q| ≤ α) prevents unlimited margin growth
while preserving the early binding advantage of Quad-native supervision and improving
generalization.*

**Verdict:** bounding **does** prevent unlimited margin growth and **does** preserve reliable
in-distribution binding, but it **does not** improve generalization for Quad-native supervision.
The generalization gain that bounding can produce appears **only when the auxiliary is absent**
(Arm BD-A), and the mechanism shows why: the failure is caused by *routing binding through the
Quad retrieval selector*, which the auxiliary enforces regardless of the bound.

## Bounded formulation and frozen scale

`S^Q_bounded_{i,j} = α·⟨q̂_i,k̂_j⟩ ∈ [−α,α]`, `q̂=q/(‖q‖+ε)`, `k̂=k/(‖k‖+ε)`, ε=1e-6, per head;
same causal mask and candidate softmax after. Fixed non-learnable **α=4** (scale pilot in
`BOUNDED_PILOT_RECORD.md`: α=2→acc .965/entropy .82, α=4→1.0/.15, α=8→1.0/.008; α=8 re-collapses,
α=4 is the lowest scale that reliably reaches 100% with entropy well above zero). 10 numerical/
correctness tests pass (`tests/test_bounded.py`): `‖q̂‖,‖k̂‖≈1`, `|S^Q|≤α+δ`, causal mask
unchanged, near-zero-vector safety (no NaN/Inf), gradient flow to `W_q,W_k` and shared params,
deterministic inference, no aux after the BD-D10 cutoff, and production code unmodified.

## Arms

Reused frozen: **A** (unbounded, task-only), **C** (generic off-path), **D-full** (unbounded +
aux), **D-10** (unbounded + early-only aux). New bounded (α=4, identical everything else):
**BD-A** (task-only), **BD-D** (+ full aux), **BD-D10** (+ early-only 10% aux).

## Results — in-distribution (3 seeds)

| arm | acc mean (min) | entropy | margin | internal select acc |
|---|---|---:|---:|---:|
| A | 0.252 (0.241) | — | — | ~chance |
| C | 0.749 (0.250) | 0.076 | 22.2 | 0.543 |
| D-full | 0.990 (0.985) | 0.000 | 46.5 | 1.000 |
| D-10 | 0.981 (0.974) | 0.001 | 49.3 | ~1.0 |
| **BD-A** | **1.000 (1.000)** | **1.272** | **0.00** | **0.290** |
| **BD-D** | **0.997 (0.991)** | 0.171 | 4.63 | 1.000 |
| **BD-D10** | **0.995 (0.986)** | 0.385 | 3.55 | 1.000 |

All bounded arms reach ≥95% on **every** seed (criteria 1–2 met), keep entropy **well above**
D-full's ~0 (criterion 3), and keep the margin **finite/bounded** (criterion 4). Bounding also
**changes baseline learnability**: BD-A (bounded, task-only) reaches 100% where the unbounded
baseline A was stuck at chance (0.25) — normalized (cosine) retrieval is markedly easier to train.

## Results — preregistered hard conditions (mean ± sd, 3 seeds)

| condition | A | C | D-full | D-10 | **BD-A** | **BD-D** | **BD-D10** |
|---|---:|---:|---:|---:|---:|---:|---:|
| longer context | 0.247 | 0.723 | 0.122 | 0.155 | **0.926** | 0.004 | 0.020 |
| higher distractor | 0.127 | 0.391 | 0.155 | 0.181 | **0.570** | 0.138 | 0.232 |
| two systems | 0.148 | 0.384 | 0.183 | 0.192 | **0.559** | 0.206 | 0.273 |

Two findings dominate:

1. **BD-A (bounded, no auxiliary) generalizes best of every arm by a wide margin** — 0.93 / 0.57 /
   0.56, far above the previous best (Arm C: 0.72 / 0.39 / 0.38) and above every Quad-supervised
   arm.
2. **BD-D and BD-D10 (bounded + auxiliary) generalize poorly** — BD-D collapses to 0.004 on longer
   context; both remain far below Arm C on all three conditions. The bound did not rescue
   generalization for the Quad-native supervised arms.

## Decision criteria (spec §10) for BD-D / BD-D10

| criterion | BD-D | BD-D10 |
|---|:--:|:--:|
| 1. ≥95% in-dist all seeds | ✅ | ✅ |
| 2. no seed collapse | ✅ | ✅ |
| 3. entropy meaningfully > D-full | ✅ | ✅ |
| 4. finite, stable margin | ✅ | ✅ |
| 5. improves ≥2 hard conditions over D-full | ❌ (0) | ⚠️ (2, small; regresses longer-context) |
| 6. not materially worse than Arm C on hard conditions | ❌ | ❌ (much worse) |
| 7. gradient flow through deployed Quad | ✅ | ✅ |

Criterion 6 fails for both (they are far worse than C on every hard condition), and criterion 5
is unmet/marginal, so **BOUNDED_QUAD_SUPPORTED is not warranted**. Binding is retained and score
growth is bounded, but generalization is not materially improved → **BINDING_RETAINED_
GENERALIZATION_LIMITED**. (An earlier auto-classification mislabeled this SUPPORTED due to two
bugs — a `margin ≤ α` check that should be `≤ 2α`, and an omitted criterion-6 gate; both fixed in
`run_bounded.py`, and `bounded_results.json` carries the corrected outcome.)

## Mechanism — why bounding does not fix it

The **internal candidate-selection accuracy** is the key: it measures whether the model's *own
Quad retrieval* actually selects the correct key.

- **BD-A: select-acc 0.290 (≈ chance), entropy 1.272, margin 0.** The bounded task-only model
  solves MQAR **without binding through the Quad retrieval at all** — the retrieval is near-uniform
  and uninformative, and a different, more robust pathway does the copying. That non-retrieval
  solution generalizes best (0.93 longer context).
- **BD-D / BD-D10: select-acc 1.000.** The auxiliary’s entire function is to **force binding
  through the Quad retrieval** (it drives select-acc to 1.0 exactly as unbounded D-full did). Even
  bounded, that retrieval-based binding overfits the in-distribution structure and fails out of
  distribution (longer context 0.004 / 0.020).
- **C: select-acc 0.543** (off-path supervision, partial retrieval reliance) generalizes in
  between; **D-full: 1.000** (unbounded retrieval binding) generalizes worst among the learners.

So generalization tracks **how much the solution relies on the Quad retrieval selector for
binding**, not the score magnitude: bounded BD-D (margin 4.6) generalizes as poorly as unbounded
D-full (margin 46) because both bind through the retrieval (select-acc 1.0). Score magnitude is
therefore **correlated with, but not sufficient to explain, the generalization failure** (spec
§12) — the causal factor is retrieval-based binding, which the auxiliary imposes irrespective of
the bound.

## Offline temperature control (spec §9)

The unbounded D-full logits, rescaled offline by the temperature that matches the bounded scale
(`T ≈ D-full margin / α ≈ 46/4 ≈ 11.3`), reach bounded-like entropy but — being a monotonic
rescale — **preserve D-full's ranking** (`ranking_preserved = True`) and therefore cannot change
D-full's hard-condition accuracy. BD-D was **trained** bounded and has a **different** hard-
condition profile (e.g. higher-distractor 0.138 vs D-full 0.155, two-systems 0.206 vs 0.183), so
its differences from D-full are a **training-time geometric effect**, not post-hoc rescaling. This
confirms the bounded model is mechanistically distinct from temperature-scaling a diverged model —
but note the training-time effect is small and does not close the gap to C.

## Interpretation discipline (spec §12)

- **Not** claiming normalized Quad is universally superior: the tested bounded Quad-native arms
  (BD-D/BD-D10) generalize poorly.
- **Not** claiming production readiness, nor inference-cost savings (per-step time comparable;
  bounding adds only two vector norms).
- **Not** claiming entropy causes generalization: BD-D10 has higher entropy than BD-D yet both
  generalize poorly; BD-A's good generalization coincides with chance-level Quad selection, not
  merely high entropy. Entropy is a symptom, not the cause.
- Established only: removing the unbounded-logit pathway (i) **improves binding reliability /
  trainability** (BD-A, BD-D reliable on all seeds), (ii) **bounds score saturation** (margins
  finite), but (iii) **does not fix MQAR generalization** when the Quad-native auxiliary is
  present. Score magnitude is correlated with, but not sufficient to explain, the generalization
  failure.

## Final outcome — **BINDING_RETAINED_GENERALIZATION_LIMITED**

The bounded formulation preserves reliable in-distribution binding and prevents unlimited score
growth, but hard-condition improvement for the Quad-native supervised arms is small/inconsistent
and remains far below the generic control C. The bound controls magnitude; it does not fix
generalization.

## One evidence-driven next recommendation

Every result across this program now points to the same variable: **generalization is governed by
how much the task solution binds *through the Quad retrieval selector*** (select-acc), not by score
magnitude or entropy. The striking BD-A result — a bounded, task-only model that solves MQAR with
its Quad retrieval at **chance** (select-acc 0.29) yet generalizes best — is the lead to pursue.
The single most justified next experiment (pre-registered, analysis-first) is to **identify the
alternative binding pathway BD-A uses**: with a read-only causal ablation, zero out / mean-ablate
the aux-layer Quad retrieval output at inference in a trained BD-A model and measure the accuracy
drop on in-distribution and the three hard conditions, and compare to the same ablation in BD-D
and D-full. If BD-A's accuracy is largely retained under Quad-retrieval ablation while BD-D's/D-
full's collapses, that localizes the robust binding to a non-retrieval component (e.g. the
value/FFN path or per-head structure the head-mean hides) and reframes the entire question away
from "how to supervise the Quad score" toward "which component should carry associative binding."
No fix is proposed here; the mechanism (retrieval-based binding, not magnitude, drives the
generalization failure) is established first.

## Reproduction

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q            # 38 tests
OMP_NUM_THREADS=4 python run_bounded.py --threads 4     # -> RESULTS_BOUNDED/
```
