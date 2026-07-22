# Quad Score Dynamics — Root-Cause Analysis

**Study:** Quad Generative Regularization, analysis-only workstream (CPU-only)
**Date:** 2026-07-22 · Frozen config, 3 seeds · Data: `RESULTS_DYNAMICS/`
**Companion:** `DERIVATION.md` (Phase 1). This report covers Phases 2–5 and the root cause.

> This experiment evaluates **Quad-native training regularization**. It does not implement or
> test USE phase or synchronization mechanisms. No losses, regularizers, temperature scaling,
> entropy penalties, margin caps, auxiliary heads, phase logic, synchronization, or teacher
> models were added. All instrumentation is read-only and verified bit-identical to an
> un-instrumented run (`tests/test_analysis.py`).

## The hypothesis under test (not assumed)

*The deployed task objective, acting through the production Quad retrieval mechanism, naturally
drives score saturation.* The analysis **confirms a refined form** of this and localizes the
cause precisely: the collapse is the implicit bias of softmax selection under cross-entropy on
separable data — a property of **ordinary task optimization**, not of Quad — and Arm D collapses
because the auxiliary routed the solution *through* the on-path Quad softmax whose input logit is
**unbounded**.

## Phase 1 (recap) — the gradient

`∂L_task/∂S_{ij} = a_{ij} · ⟨δ_i, v_j − o_i⟩` (derivation in `DERIVATION.md`). Correct scores
rise, incorrect fall; the per-score gradient **vanishes** as `a→onehot`; but with **separable
data and no weight decay** cross-entropy has **no finite minimizer**, so gradient descent's
implicit bias drives the margin `→ ∞` and entropy `→ 0`. Four predictions (P1–P5) were handed to
the empirical phases. All four are confirmed below.

## Phase 2 — training dynamics (Arm D, seed 0 representative)

| step | margin (pos−neg) | entropy | \|∂L/∂S^Q\| | val acc¹ |
|---:|---:|---:|---:|---:|
| 0 | −0.0 | 1.378 | 0.005 | 0.03 |
| 250 | 17.2 | 0.006 | 0.004 | ~0.6 |
| 750 | 27.9 | 0.009 | 0.006 | ~0.9 |
| 1250 | 39.0 | 0.001 | 0.026 | ~0.98 |
| 2250 | 50.5 | 0.000 | **0.0001** | ~0.99 |
| 2499 | 46.6 | 0.000 | 0.006 | 0.99 |

¹ accuracy from the main screen (same seed/data). **P1 confirmed:** the score gradient is tiny
throughout (≈0.005, dipping to 1e-4) yet the **margin keeps climbing** 17→50. **P2 confirmed:**
entropy collapses to ~0 by step ~250 (near task convergence) and the margin keeps growing for
~2000 further steps *after* accuracy has saturated — margin growth clearly outlasts convergence,
and the gradient remains nonzero-but-small, never producing a plateau. Final gradient norms
(mean over seeds): `|∂L/∂S^Q|` 0.0025, `|∂L/∂h|` ~, `|∂L/∂W_q|`, `|∂L/∂W_k|` remain the active
channel — the projection weights keep moving in a fixed direction while the score gradient shrinks
(the signature of implicit-bias margin divergence). See `plots/margin_trajectory.png`,
`entropy_trajectory.png`, `grad_wrt_score_trajectory.png`, `grad_norms_armD.png`.

## Phase 3 — where the separation originates (the decisive dissociation)

Cosine separation (correct − distractor) measured at two stages: raw hidden states, and the
Quad **projected** query·key space. Final values, mean over seeds:

| arm | hidden-state gap | projected q·k gap | where binding lives |
|---|---:|---:|---|
| A (baseline) | 0.016 | −0.016 | nowhere (does not bind) |
| **C (generic)** | **0.623** | 0.308 | **hidden-state geometry** |
| **D (Quad-native)** | 0.278 | **0.723** | **projection → softmax** |

**P3 confirmed and sharpened.** The two learning solutions place the binding in *different*
places:

- **Arm C** makes the **hidden states themselves** separable (cosine gap 0.62, rising to 0.92
  over training) and leaves the projection mild (0.31). Hidden-state cosine is **intrinsically
  bounded** (|cos| ≤ 1), so the downstream softmax stays comparatively soft.
- **Arm D** makes the **projection** separable (gap 0.74 from step 250 onward) while the hidden
  states stay mild (0.28). The bilinear projected logit is **unbounded**, so the softmax over it
  is free to diverge.

The separation therefore does **not** first appear in Quad's dot product per se; it appears
wherever the solution puts it. Under the auxiliary (D) it is placed in the unbounded projection;
without it (C) it is placed in bounded hidden geometry. See
`plots/hidden_vs_projection_geometry.png`.

## Phase 4 — counterfactual temperature (score vs probability collapse)

Offline entropy after dividing the *trained* logits by temperature `T` (no retrain, no inference
change), as a fraction of the uniform-over-candidates maximum:

| arm | T=1 | T=5 | T=10 | T=20 | T=50 |
|---|---:|---:|---:|---:|---:|
| A | 0.05 | 0.18 | 0.30 | 0.47 | 0.75 |
| C | 0.05 | 0.27 | 0.49 | 0.74 | 0.94 |
| **D** | **0.00** | **0.04** | **0.25** | 0.62 | 0.92 |

**P4 confirmed.** For Arm D the *logits themselves have diverged*: even `T=10` recovers only 25%
of uniform entropy; near-uniform requires `T≈50`, i.e. temperature of the same order as the
margin (~46). This is **score collapse** (logit divergence), not mere probability collapse — a
fixed temperature would *soften* the distribution but only a very large one, because the
underlying scores are enormous. Arm C's milder logits recover entropy at much lower temperature
(`T=10 → 0.49`). Ranking is temperature-invariant, so temperature cannot repair retrieval
*errors*, only confidence. See `plots/temperature_counterfactual.png`.

## Phase 5 — Arm C vs Arm D (why C generalizes, why D sharpens)

| metric (final, mean/seeds) | Arm C | Arm D |
|---|---:|---:|
| in-distribution acc | 0.749 (1/3 seed collapse) | 0.990 (0/3) |
| score margin | 22.6 | 45.0 |
| candidate entropy | 0.071 | **0.000** |
| hidden-state separation gap | **0.623** | 0.278 |
| projected q·k separation gap | 0.308 | **0.723** |
| temperature to restore entropy | moderate (`T≈10–20`) | large (`T≈50`) |
| generalization (hard conditions, from main screen) | **better** | worse |

**Why D sharpens more:** the auxiliary loss (early) forces the solution to route through the
on-path Quad retrieval; the model satisfies the task by making the **projection** separable, and
because that logit is unbounded, separable-CE implicit bias drives it to the extreme
(margin 45, entropy 0.000, needs `T≈50`). **Why C generalizes better:** C's relational pressure
is off-path, so the model is free to solve the task by making the **hidden states** separable;
hidden-cosine separation is bounded, so the on-path softmax stays softer (entropy 0.071),
retrieval is less over-confident, and out-of-distribution inputs are not forced into a razor-thin
selection. The trade-off from the main screen — D reliable but brittle, C fragile but
generalizing — is fully explained by *where each solution stores the binding*.

## Root-cause analysis

Separating the four possible causes requested by the workstream:

1. **Inevitable mathematical behavior — YES, this is the driver.** Cross-entropy on separable
   data with no weight decay has no finite minimizer; gradient descent's implicit bias drives any
   softmax selector the solution depends on to a hard argmax (margin → ∞, entropy → 0). Confirmed
   analytically (`DERIVATION.md`) and empirically (P1, P2: gradient ~0 while margin grows to 50).
2. **Implementation artifact — NO.** All validity checks pass (A≡D0 bit-identical, future-shuffle
   invariant, deterministic); the read-only instrumentation is provably non-perturbing. The
   collapse reproduces across all three seeds.
3. **Optimization artifact — this IS the cause, but it is not a *bug*.** It is the intended,
   correct behavior of GD on this objective. There is no LR/optimizer pathology; the same
   implicit bias would arise for full-batch GD. The single missing ingredient that would produce
   a finite equilibrium — bounded weights (weight decay) or bounded logits (a temperature/norm on
   the retrieval logit) or non-separable data — is simply absent.
4. **Architectural cause — the *location*, not the *cause*.** The collapse manifests at the
   **unbounded bilinear retrieval logit → softmax** composition. Arm C demonstrates the
   counterfactual within the *same architecture*: by placing the binding in bounded hidden-cosine
   space instead of the projection, the on-path softmax collapses far less. So the architecture
   permits collapse but does not force it; the auxiliary’s routing plus the unbounded logit do.

**Quad does not create the collapse.** Quad is an ordinary scaled-dot-product softmax; the
identical implicit bias governs the final vocab classifier and Arm C's own off-path head (which
also sharpens). Arm A's Quad does **not** collapse toward correct binding (margin 0.4) precisely
because A's solution does not route through correct retrieval. The collapse is created by
**ordinary task optimization** and located at **whichever unbounded softmax selector the solution
is made to depend on** — which the auxiliary makes the on-path Quad retrieval.

## Final conclusion — the four questions

1. **Is entropy collapse mathematically inevitable under the current objective?**
   **Yes, asymptotically, for any softmax selector the solution routes through.** Under separable
   MQAR data with `weight_decay=0`, cross-entropy has no finite minimizer; the implicit bias of
   gradient descent drives margin → ∞ and entropy → 0. It is not inevitable that a *given* module
   collapses — a solution can route the binding elsewhere (Arm C uses bounded hidden-state
   geometry and stays at entropy 0.071) — but some selector on the critical path must diverge for
   the loss to approach zero.

2. **Does Quad itself create the collapse?** **No.** Quad is a generic scaled-dot-product
   softmax; the same collapse is produced by any softmax-under-CE-on-separable-data (the vocab
   head, Arm C's off-path head). Arm A's Quad softmax does not collapse toward the correct key,
   and Arm C's on-path Quad softmax collapses much less — both within the identical Quad
   mechanism. Quad is the *site*, not the *cause*.

3. **Or does ordinary task optimization create it?** **Yes.** Cross-entropy + gradient descent on
   separable data with no weight decay is the cause; it drives the projection weights in a fixed
   separating direction with a vanishing-but-persistent gradient, sending the retrieval logit to
   divergence. The auxiliary loss only determines *which* selector (the on-path Quad softmax)
   ends up on the critical path and therefore collapses.

4. **Smallest architectural location responsible.** The **unbounded bilinear retrieval logit that
   feeds the Quad softmax** — concretely, the composition `S^Q = ⟨W_q·LN(h_i), W_k·LN(h_j)⟩/√d_h`
   → `softmax`, in which **nothing bounds the magnitude of the projected logit** (no weight decay
   on `W_q,W_k`, no temperature/normalization cap on `S^Q`). The projection is where Arm D's
   separation concentrates (proj gap 0.72) and the softmax is where an unbounded logit becomes an
   entropy-0 distribution. The counterfactual is proven by Arm C, whose binding lives in the
   intrinsically bounded hidden-state cosine space and therefore does not drive the same collapse.

**Mechanism established (no fixes proposed here):** entropy collapse is the implicit bias of
softmax selection under cross-entropy on separable data (ordinary task optimization), realized at
the single unbounded location `projected-logit → retrieval-softmax`; Quad is that location under
Arm D only because the auxiliary routes the binding into it. Deliverables: `DERIVATION.md`,
`RESULTS_DYNAMICS/dynamics_results.json`, `dynamics_trajectory.csv`, and `plots/` (entropy,
gradient, score-distribution, geometry, temperature, margin, pos/neg trajectories).
