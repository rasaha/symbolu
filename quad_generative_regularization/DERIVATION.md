# Phase 1 — Mathematical Analysis of the Task-Loss Gradient on the Quad Score

Analysis-only. No losses, regularizers, temperature scaling, or architecture changes are
introduced. This derives `∂L_task/∂S^Q` for the authentic Quad retrieval and states the
predictions the empirical instrumentation (Phases 2–5) then tests.

## 1. Setup and notation

For a query position `i` (one head; the argument is per-head and sums trivially), let the
causally-visible candidate keys be `j ∈ C_i`. The authentic Quad score, attention weights, and
attended value are

```
S_{ij} = ⟨ W_q·LN(h_i),  W_k·LN(h_j) ⟩ / √d_h          (the Quad logit)
a_{ij} = softmax_j(S_{ij}) = e^{S_{ij}} / Σ_{k∈C_i} e^{S_{ik}}
o_i    = Σ_{j∈C_i} a_{ij} v_j ,     v_j = W_v·LN(h_j)
```

`o_i` propagates through the residual/FFN/final-norm/vocab-head to the cross-entropy loss `L`.
Write the upstream gradient into the attended output as the vector `δ_i ≡ ∂L/∂o_i ∈ ℝ^{d_h}`.

## 2. Gradient of the task loss w.r.t. the Quad score

Using the softmax Jacobian `∂a_{im}/∂S_{ij} = a_{im}(δ_{mj} − a_{ij})` and `∂o_i/∂a_{im} = v_m`:

```
∂L/∂S_{ij} = Σ_m (∂L/∂o_i)·v_m · a_{im}(δ_{mj} − a_{ij})
           = a_{ij} ⟨δ_i, v_j⟩ − a_{ij} Σ_m a_{im} ⟨δ_i, v_m⟩
```

which collapses (since `Σ_m a_{im} v_m = o_i`) to the exact, compact form

```
┌─────────────────────────────────────────────────────────┐
│   ∂L_task/∂S_{ij} = a_{ij} · ⟨ δ_i , v_j − o_i ⟩          │   (★)
└─────────────────────────────────────────────────────────┘
```

The gradient on a Quad logit is the **attention weight** `a_{ij}` times the **alignment**
`⟨δ_i, v_j − o_i⟩` between the upstream error direction and how much candidate `j`'s value
deviates from the currently attended output. The gradient-descent update is
`ΔS_{ij} ∝ −a_{ij}⟨δ_i, v_j − o_i⟩`.

## 3. Why correct scores rise and incorrect scores fall

Moving `o_i` toward the correct value `v_{j⁺}` reduces the loss, so the loss-reducing direction
`−δ_i` is positively aligned with `v_{j⁺} − o_i`, i.e. `⟨δ_i, v_{j⁺} − o_i⟩ < 0`. By (★),
`ΔS_{ij⁺} = −a_{ij⁺}⟨δ_i, v_{j⁺}−o_i⟩ > 0` — **the correct score increases**. For a distractor
`j⁻`, moving `o_i` toward `v_{j⁻}` raises the loss, so `⟨δ_i, v_{j⁻}−o_i⟩ > 0` and
`ΔS_{ij⁻} < 0` — **the incorrect score decreases**. This is intrinsic to (★); it needs no
auxiliary term. Any softmax-retrieval-then-copy module trained by task CE separates its logits.

## 4. Do the score gradients vanish?

From (★), `|∂L/∂S_{ij}| = a_{ij} · |⟨δ_i, v_j − o_i⟩|`. As the retrieval saturates toward a hard
selection `a_{i·} → onehot(j⁺)`:

- **correct key**: `a_{ij⁺} → 1` but `o_i → v_{j⁺}` so `v_{j⁺} − o_i → 0`; the alignment factor
  vanishes → `∂L/∂S_{ij⁺} → 0`.
- **distractors**: the prefactor `a_{ij⁻} → 0` → `∂L/∂S_{ij⁻} → 0`.

So the per-element gradient **w.r.t. the score vanishes** as the softmax approaches one-hot — it
approaches zero but never reaches it in finite steps. (Prediction P1: `|∂L/∂S^Q|` decays toward
~0 while the margin is still growing.)

## 5. Must entropy approach zero? Are margins bounded?

Vanishing *score* gradients do **not** imply a fixed margin, because the margin
`S_{ij⁺} − S_{ij⁻}` is produced by the projection parameters `W_q, W_k` through the bilinear
`S_{ij}`, and their gradient direction stays consistent even as its magnitude shrinks:

```
∂L/∂W = Σ_{i,j} (∂L/∂S_{ij}) · ∂S_{ij}/∂W
```

The MQAR training data is **separable** (the model attains ~100% train accuracy, and the tiny-
overfit test confirms zero achievable loss), and there is **no weight decay** (`weight_decay=0`).
Under these two conditions, cross-entropy has **no finite minimizer**: `L` decreases
monotonically as `‖W‖ → ∞` along the separating direction. This is the standard implicit bias of
gradient descent on separable data (logistic/softmax regression → the max-margin direction with
weights, and therefore logits, diverging; loss `→ 0` only as margin `→ ∞`). The bilinear Quad
score inherits this: minimizing separable CE drives

- `a_{ij⁺} → 1`, hence **entropy `H_i = −Σ_j a_{ij} log a_{ij} → 0`**, and
- the logit margin `S_{ij⁺} − S_{ij⁻} → ∞`, **theoretically unbounded**,

with the gradient shrinking roughly like `1/margin` (logarithmically slow divergence). Entropy
collapse is therefore the **asymptotically forced** behavior of this objective, not a transient.

## 6. Does cross-entropy alone predict infinite margin growth?

**Yes — conditionally.** Ordinary cross-entropy predicts:

| regime | prediction |
|---|---|
| separable data, no weight decay (this study) | **infinite margin growth / entropy → 0** (no finite equilibrium) |
| non-separable data | finite equilibrium (residual errors balance the push) |
| any data + weight decay > 0 | finite equilibrium (bounded ‖W‖ caps the margin) |

So the behavior is **objective-and-data-determined, not Quad-specific**: it is the generic
implicit bias of softmax selection under CE on separable data. It manifests in *whatever module
the solution is forced to route through* — the final vocab classifier, an attention softmax, or
the off-path Arm-C head. The module collapses iff the task solution must make it a hard selector.

## 7. Predictions handed to the empirical phases

- **P1 (Phase 2):** `|∂L/∂S^Q|` decays toward ~0 *while* the margin keeps rising and entropy
  keeps falling — collapse continues after the score gradient becomes small and after accuracy
  saturates.
- **P2 (Phase 2):** entropy collapse begins around/after task convergence, and margin growth
  outlasts accuracy saturation (no plateau in margin).
- **P3 (Phase 3):** separation is amplified by the projection: the pos−neg cosine gap is larger
  in the projected `q·k` space than in raw hidden-state space; the softmax then exponentiates it.
- **P4 (Phase 4):** because the *logits* diverge (margin → tens of nats), only a very large
  offline temperature (`T ~ margin`) restores entropy — temperature *softens* but reveals the
  logits have already diverged (**score collapse**, not mere probability collapse); ranking is
  temperature-invariant, so temperature cannot repair retrieval errors.
- **P5 (Phase 5):** Arm D routes the solution through the on-path Quad softmax (aux forces it),
  so that softmax must go hard → maximal collapse; Arm C routes relational pressure to an
  off-path head, leaving the on-path Quad softmax under weaker pressure → higher residual entropy
  and softer retrieval, hence better OOD generalization.

The empirical results (`RESULTS_DYNAMICS/`, `SCORE_DYNAMICS_REPORT.md`) test each prediction.
