# Universal Semantic Evaluator (USE) as a Read-Only Failure Predictor — Technical Report

**Study:** independent falsification track (CPU-only). Separate package; reuses the prior
`quad_generative_regularization` (`qgr`) package **read-only**. No production code, no Quad, no
model architecture, and no inference pipeline was modified.
**Date:** 2026-07-22 · Frozen bounded BD-A model, 3 seeds (all in-dist acc 1.000) · 5 conditions,
~46k queries · Data: `RESULTS/use_results.json`.

**Verdict:** **NULL NOT REJECTED — internal semantic-coherence (U1–U5) measurements provide no
practically meaningful predictive value beyond standard model-confidence measures.** USE is, in
fact, strictly dominated by a single free scalar (token probability / output entropy).

> Read-only discipline (verified in `tests/test_readonly_and_core.py`): inference is bit-identical
> with and without USE's capture hooks. USE never changes attention, logits, probabilities,
> retrieval, decoding, sampling, the KV path, the reasoning path, or generated tokens. The U1–U5
> peer update is computed as a *counterfactual correction demand on a detached copy* and never
> applied to the model. No retrieval, no internet, no second LLM. No inference-time control system
> was built (explicit future scope).

---

## 1. Question and null

**H1:** internal semantic-coherence signals (the U1–U5 phase-coherence dynamics run as a
post-inference observer) predict answer correctness better than standard confidence measures.
**Null (H0):** they contain no additional predictive information beyond standard confidence. We
attempted to reject H0 and **could not**; the evidence positively supports H0.

## 2. Design (deliverable 1 — see `DESIGN.md`)

Model = frozen bounded task-only Quad transformer (**BD-A**), the prior best generalizer on which
Quad retrieval is causally necessary, on MQAR. Per **query**, correctness is exact
(`failure = argmax logits ≠ target`); ground truth forms the label only. Five conditions map the
required dataset families: `in_distribution`, `long_context`, `distractor_robust` (num_kv=8),
`multi_relation` (2 systems), `long_and_hard` (confident-error / hallucination-style). Three model
seeds give the reproducibility grid. In-distribution has ~0 failures (acc 1.000) and is reported
but not tested (no class balance).

## 3. USE metric definitions (deliverable 2 — the U1–U5 algorithm, see `use/`)

Channels φ_i are internal pathways (per-head Quad outputs, values, residual/layer streams,
attention/FF outputs). Each channel vector is mapped to a scalar phase by a preregistered
non-learned mapping (complex-pair, reference-projection, temporal-change). Then:
`U1` windowed pairwise phase coherence → `U2` global coherence → `U3` peer gradient →
`U4` counterfactual correction demand (**not applied**) → `U5` detached relaxation diagnostics.
Signal set per query: `S_USE = {C_windowed, R_initial, R_final, ΔR, E_correction, D_max, D_mean,
T_conv, R_unresolved}`, computed for every (channel set × phase mapping).

## 4. Baselines (deliverable 3)

token probability, log-probability, output entropy, margin, sequence confidence, attention
entropy, random — univariate and as an L2-logistic combo. Combined predictors use cross-validated
**out-of-fold** probabilities (no leakage; verified on pure noise → AUROC 0.5).

## 5. Predictive performance across datasets (deliverable 4) — failure-detection AUROC

| condition (n, fail%) | token_prob | baseline_combo | USE best | USE all | USE Quad-only | baseline+USE |
|---|---:|---:|---:|---:|---:|---:|
| long_context (7680, 6.5%) | 0.952 | 0.953 | 0.607 | 0.652 | 0.522 | 0.937 |
| distractor_robust (7680, 43%) | 0.888 | 0.906 | 0.616 | 0.641 | 0.517 | 0.902 |
| multi_relation (15360, 44%) | 0.776 | 0.831 | 0.626 | 0.746 | 0.505 | 0.854 |
| long_and_hard (7680, 49%) | 0.878 | 0.898 | 0.581 | 0.637 | 0.518 | 0.897 |
| **pooled** | 0.817 | **0.821** | 0.593 | 0.668 | 0.515 | 0.842 |

Two facts dominate: (i) **standard confidence is a strong failure predictor** (pooled AUROC 0.82,
up to 0.95 on long-context); (ii) **USE is far weaker everywhere** (pooled best-USE 0.59, all-USE
0.67) and its **Quad-native form is at chance** (0.51). The model's own output distribution already
encodes its failure risk; the internal phase-coherence dynamics do not add to it.

## 6. Statistical significance (deliverable 5) — DeLong tests on the same samples

| pooled comparison | ΔAUROC | z | one-sided p |
|---|---:|---:|---:|
| USE best − baseline combo | **−0.228** | −64.8 | 1.000 (USE worse) |
| USE all − baseline combo | −0.152 | −44.0 | 1.000 (USE worse) |
| (baseline + all USE) − baseline | +0.022 | 15.1 | 7.7e-52 |
| **(baseline + best USE group) − baseline (parsimonious)** | **+0.0035** | 4.1 | 1.8e-05 |
| (baseline + Quad USE) − baseline | −0.002 | −3.6 | 0.9999 |

The incremental terms are **statistically significant only because N≈38k**; both are **negligible
in magnitude**. The parsimonious incremental (+0.0035 AUROC) is below the pre-registered
practical-meaning threshold (+0.005). The larger full-USE incremental (+0.022) is a
**high-dimensional artifact**: it comes almost entirely from one condition (multi_relation
+0.0224) and is *negative* in the other three (long_context −0.015, distractor −0.004,
long_and_hard −0.001); pouring 270 USE features into one logistic lets it capture a sliver that
does not survive parsimony. **Adding Quad-native USE to baselines never helps** (Δ ≤ 0 everywhere).

Pre-registered decision — reject H0 only if the incremental gain is significant with meaningful
magnitude (both full and parsimonious) in a majority of conditions, in the pooled omnibus, and
reproducibly across seeds. **Met in 0 of 4 conditions; pooled magnitude below threshold. H0 not
rejected.**

## 7. Calibration analysis (deliverable 6) — pooled

| predictor | AUROC | Brier | ECE |
|---|---:|---:|---:|
| baseline_combo | 0.821 | 0.163 | 0.038 |
| combined_base_use | 0.842 | 0.155 | 0.038 |
| use_all | 0.668 | 0.215 | 0.009 |
| use_quad | 0.515 | 0.234 | 0.007 |

USE's low ECE is **not** a virtue here: its probabilities sit near the base rate (uninformative but
"calibrated"). The informative predictor is the confidence combo; adding USE barely moves Brier
(0.163 → 0.155, driven by the one multi_relation condition). Reliability diagram: `plots/reliability.png`.

## 8. Ablation study (deliverable 7)

**Channel set (combined USE AUROC, pooled):** residual 0.628, layers 0.626, value_heads 0.564,
quad_heads_L1 0.542, attn_out 0.539, full 0.539, full_network 0.536, ff 0.525, quad_heads_L0 0.519,
**quad_heads 0.515 (worst, chance).** The Quad-native pathway — the specific U1–U5-on-Quad
proposition — carries the **least** predictive signal; what little exists lives in the residual/
layer stream, and even that is far below the model's own confidence.

**Phase mapping:** complex_pair 0.619 ≈ reference_projection 0.619 > temporal_change 0.583. All weak.

**Per-signal (reference-projection, full channels):** every individual U1–U5 signal is at chance
(0.50–0.51; C_windowed 0.501, R_initial 0.501, E_correction 0.502, T_conv 0.503, R_unresolved
0.508); the group AUROC is 0.498. **No single U1–U5 signal is predictive.** The all-to-all Kuramoto
relaxation converges to consensus (R_final≈1) for correct and incorrect answers alike, so the
convergence diagnostics do not separate them.

## 9. Failure-case analysis (deliverable 8) — pooled (n=38.4k, 14.3k failures)

| category | fraction |
|---|---:|
| both catch failure | 0.198 |
| confidence-only catches | **0.103** |
| USE-only catches | 0.044 |
| both miss | 0.027 |
| confidence false alarm | 0.101 |
| USE false alarm | **0.161** |

At matched operating points, **confidence catches more than twice the failures USE uniquely
catches (10.3% vs 4.4%) and raises far fewer false alarms (10.1% vs 16.1%)**. Recall on failures:
confidence 0.81 vs USE 0.65; precision 0.60 vs 0.49. USE is strictly dominated — the cases it
uniquely catches are outnumbered by the extra false alarms it introduces. The only place USE
contributes marginally is `multi_relation` (2 relation systems), where cross-channel coherence
weakly reflects cross-system confusion — but even there confidence alone (0.83) beats all-USE
(0.75), and the incremental gain is tiny.

## 10. Mechanistic interpretation (deliverable 9)

* **Confidence already contains the failure signal.** The bounded softmax retrieval spreads
  probability mass and raises output entropy exactly when it is about to answer wrongly; entropy,
  margin, and top-probability are near-sufficient failure detectors (pooled AUROC 0.82, up to 0.95).
* **Phase coherence is answer-agnostic.** Extracting a scalar phase (atan2 of two projected
  coordinates) discards the magnitude/direction structure that actually encodes the answer, and
  all-to-all Kuramoto consensus dynamics drive every completed state toward synchrony regardless of
  correctness (R_final≈1 for both classes). Hence initial coherence, correction energy, and
  convergence time do not track correctness (each ~0.50 AUROC).
* **The Quad pathway is the least informative of all** — the specific proposition that Quad-native
  peer coherence predicts correctness is falsified at chance level. Whatever faint signal exists is
  in the residual stream (0.63), consistent with the residual carrying aggregate uncertainty that
  the output entropy already summarizes better and for free.

## 11. Recommendation (deliverable 10)

**USE should NOT advance to an inference-time validation layer.** As a read-only failure predictor
it is strictly dominated by a single scalar — token probability / output entropy — that is free to
compute and already well-calibrated. The U1–U5 phase-coherence machinery adds no practically
meaningful value (parsimonious incremental +0.0035 AUROC, below threshold), adds *nothing* on the
Quad pathway it was motivated by, and *degrades* accuracy in 3 of 4 conditions when force-combined.
The null hypothesis stands: **internal semantic-coherence measurements carry no additional
predictive information beyond standard confidence.**

Consistent with the program's other negative results (explicit Quad supervision and
perturbation-consistency both failed to beat their task-only baselines), this closes the
"coherence signal predicts correctness" hypothesis at least for this model/task: if inference-time
failure flags are wanted, use the model's own output entropy. The proposed downstream control
tracks (re-ranking, self-correction, reflection, retrieval) are **not** justified by this evidence
and were, per the brief, not implemented.

## Reproduction

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q                                   # 12 tests
OMP_NUM_THREADS=4 python run_use.py --threads 4 --seeds 0 1 2 --n-batches 40   # -> RESULTS/
python summarize_results.py                                                    # report tables
```

Artifacts: `RESULTS/use_results.json` (full machine-readable record incl. per-seed, calibration,
ablation, failure analysis) and `plots/` (AUROC by condition, univariate power, channel-set
ablation, reliability). Deterministic given the seeds.
