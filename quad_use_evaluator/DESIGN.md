# Experimental Design — Universal Semantic Evaluator (USE) as a Read-Only Failure Predictor

**Track:** independent falsification study (CPU-only). Separate package; reuses the prior
`quad_generative_regularization` (`qgr`) package **read-only**. No production code, no Quad, no
model architecture, and no inference pipeline is modified.

## 1. Research question and null

> Can a Universal Semantic Evaluator (USE) predict reasoning failures **after** inference, using
> only the model's own internal computation, better than standard confidence measures?

**Null (H0):** internal semantic-coherence measurements contain **no additional predictive
information beyond standard model-confidence measures**. We attempt to **falsify** H0; we reject
it only if USE shows statistically significant *and reproducible* improvement over confidence
baselines across multiple datasets.

## 2. USE is the U1–U5 peer-to-peer coherence algorithm, as a detached observer

USE is **not** a classifier, verifier, retrieval module, or second LLM. The model completes
inference exactly as today; only afterwards does USE read frozen internal states. The core is the
original U1–U5 phase-coherence dynamics, converted to read-only:

```
internal channels  ->  explicit phase extraction  ->  U1 pairwise phase correlation
   ->  U2 global coherence  ->  U3 peer coherence gradient  ->  U4 counterfactual correction
   demand (NOT applied to the model)  ->  U5 convergence diagnostics  ->  predict correctness
```

* **U1** `C_ij = (1/W) Σ_k cos(φ_i(t-k) − φ_j(t-k))` — windowed pairwise phase coherence.
* **U2** `C_total = Σ_{i<j} w_ij C_ij` — global coherence (uniform weights; learned weights are a
  separately-tested extension, not the core).
* **U3** `∂C_total/∂φ_i = −Σ_j w_ij sin(φ_i−φ_j)` — per-channel coherence gradient.
* **U4** counterfactual demand `Δφ_i = α(−Σ_j w_ij sin(φ_i−φ_j))` — computed, **never applied to
  the model** (read-only).
* **U5** run the peer update on a *detached* copy of the completed inference's instantaneous
  phases; record convergence diagnostics.

**USE-native signal set** per query (the falsifiable proposition — correct answers should begin
closer to a stable peer-coherent state, need less correction, and converge more cleanly):

```
S_USE = { C_windowed, R_initial, R_final, ΔR, E_correction, D_max, D_mean, T_conv, R_unresolved }
```

`C_windowed` = U1/U2 temporal phase-locking; `R_initial/R_final` = instantaneous global coherence
before/after detached relaxation; `E_correction = Σ_i(Δφ_i)²`; `D_*` = per-channel correction
demand; `T_conv` = iterations to converge; `R_unresolved = 1 − R_final`.

## 3. The model, correctness label, and datasets (MQAR-scoped)

Consistent with the prior program (and CPU feasibility, no external references), the **model** is
the frozen **bounded task-only Quad transformer (BD-A)** — the prior best generalizer, on which
Quad retrieval is causally necessary — evaluated on MQAR. Per **query**, correctness is exact:
`failure = (argmax logits ≠ target)`. Ground truth forms the label **only**; USE and baselines
never see it. Evaluation conditions (the required dataset families, MQAR analogs):

| condition | mapping to required families |
|---|---|
| `in_distribution` | in-distribution |
| `long_context` | long-context / previous Quad OOD |
| `distractor_robust` | distractor robustness |
| `multi_relation` | multi-relation reasoning |
| `long_and_hard` | reasoning stress / confident-error (hallucination-style, ground truth known) |

Three model seeds provide the reproducibility grid; conditions with adequate class balance are
pooled for the omnibus test (in-distribution has ~0 failures and is reported but not tested).

## 4. Phase extraction (preregistered, non-learned; compared separately)

Transformer channels are vectors; USE is phase-based. Three fixed mappings, no learning:

* **A complex_pair** `φ = atan2(z[1], z[0])`.
* **B reference_projection** `φ = atan2(u2·z, u1·z)` with fixed orthonormal `u1,u2` per dim.
* **C temporal_change** phase from the direction of each channel's change across tokens.

Not silently chosen — all three are evaluated and ablated.

## 5. Channels

Explicitly-defined internal pathways, one vector per token position: per-head Quad-retrieval
outputs (head-wise / Quad-only), value vectors (value-space), residual streams and layer outputs
(layer-wise / residual), attention and feed-forward outputs, and their unions (full-network).
Per-head quantities are recomputed read-only from captured residuals and the frozen attention
module (no model forward, no modification).

## 6. Baselines (USE must beat these)

token probability, average log-probability, output entropy, margin, sequence confidence,
attention entropy, and a random classifier. Univariate and as an L2-logistic combo.

## 7. Prediction, evaluation, and statistics

USE predicts failure without ground truth. Combined predictors use **cross-validated out-of-fold**
probabilities (no leakage). Metrics: AUROC, AUPRC, precision/recall/F1, Brier, ECE, reliability
diagrams, with bootstrap 95% CIs. Significance: the **DeLong test** on the same samples for
correlated ROC curves — (i) best-USE vs the baseline combo, and (ii) the **incremental** value of
USE on top of baselines (`baseline+USE` vs `baseline`), per condition, pooled, and per seed.

**Guard against high-dimensional artifacts.** The incremental test is run both with *all* USE
features and with a *parsimonious* set (baselines + only the single best USE group). Null-rejection
requires **both** to be significant, so a ~270-feature logistic overfit alone cannot reject H0.

## 8. Ablation

Channel-set ablation (head-wise / layer-wise / Quad-only / value / residual / full), phase-mapping
ablation, and per-signal ablation (single-signal AUROC + leave-one-out) — which internal
representations and which U1–U5 signals carry predictive information, and which are redundant.

## 9. Success criterion / verdict

Reject H0 **only if** USE adds statistically significant incremental predictive value over the
confidence baselines (both full and parsimonious incremental) in **a majority of usable
conditions**, in the **pooled** omnibus, and **reproducibly across seeds**. Otherwise conclude USE
provides no practical value as an inference-time evaluator. **Future control systems (re-ranking,
self-correction, reflection, retrieval) are explicitly out of scope and not implemented.**
