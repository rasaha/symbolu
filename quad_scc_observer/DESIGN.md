# Experimental Design — SCC as Four Independent, Falsifiable Hypotheses

**Track:** independent falsification study (CPU-only). Separate package; reuses `qgr`,
`quad_use_evaluator` (`use`), and `quad_perturbation_consistency` (`qpc`) **read-only**. Nothing
in Quad production code, the MQAR benchmark, the model, or any previous package is modified.

## 1. Objective and null

Determine whether a proposed Semantic Coherence Controller (SCC) contains **independent**
predictive information about model correctness **beyond confidence, entailment, and
evidence-grounding baselines**. Not to prove SCC — to test whether *any* component adds measurable
value once stronger baselines are present.

**Null (H0):** SCC components carry no predictive information about correctness beyond confidence,
entailment, and grounding. Each component must independently justify its existence.

## 2. SCC as four separate hypotheses (not a controller)

We do **not** start from a weighted controller. We test four independent hypotheses; a composite
is considered only after independent evaluation.

* **S — semantic similarity** contributes predictive information.
* **R — relational preservation** contributes predictive information.
* **E — evidence support** contributes predictive information.
* **T — inference stability** contributes predictive information.

## 3. Setting: model, claim, evidence (MQAR closed world)

Model = frozen bounded task-only Quad transformer (**BD-A**), the prior best generalizer on which
Quad retrieval is causally necessary. A **claim** is the model's answer to a query — the
proposition *query-key k_q binds to predicted value v_pred*. **Evidence** is the context bindings.
Per query, correctness is exact (`failure = v_pred ≠ v_true`); ground truth is used for labelling
only. Conditions: `in_distribution`, `long_context`, `distractor_robust`, `multi_relation`,
`long_and_hard`. Three model seeds. In-distribution has ~0 failures (reported, not tested).

## 4. Components (read-only)

* **S** (representation-based, cosine as a *feature* not truth): query↔retrieved-key match,
  hidden↔predicted-value alignment, pred↔attention-retrieved-value agreement, hidden↔context-value.
* **R** (structural relational): key present, predicted value is a real context value,
  pred==attention-retrieved value (relational consistency), key uniqueness, candidate count.
* **E** (closed-world evidence): adjacency binding support (does the context contain k_q→v_pred),
  value/key presence, retrieved-binding, support count. *Open-world evidence is deliberately not
  implemented*: it would require external grounding/retrieval, which is a categorically different
  (grounded-verification) problem; substituting retrieval would conflate it with intrinsic
  coherence. We separate the two by restricting E to the context.
* **T** (inference stability): reuse the perturbation machinery to make M semantically-equivalent
  views (reorder, extra distractors, positional shift) and measure prediction flip-rate, mean/std
  of the probability on the original answer, and answer entropy across views. Observer only — no
  retraining, no regularization.

## 5. Baselines (SCC must add value beyond these)

* **A confidence** (reused from the USE package): token prob, log-prob, entropy, margin, sequence
  confidence, attention entropy.
* **B entailment proxy**: attention-support mass on the retrieved key + pred/retrieval agreement
  (documented to overlap with confidence and grounding in the closed world).
* **C grounding**: the symbolic evidence verifier (adjacency + presence). In a closed world this is
  a **near-oracle** for correctness — that is the point of separating grounded verification from
  intrinsic coherence.

## 6. Arms

Confidence; +entailment; +grounding; +grounding+{S,R,E,T} each; intrinsic-only S+R+T; confidence+
S+R+T; full SCC (S+R+E+T); +grounding+full SCC. **The full SCC is not assumed best.**

## 7. Prediction, metrics, statistics

Out-of-fold logistic combos (no leakage). Metrics: AUROC, AUPRC, precision/recall/F1, Brier, ECE,
reliability — never calibration without discrimination. **DeLong tests** on the same samples for
the incremental value of each term over three bases: confidence, confidence+entailment (the
intrinsic bar, no evidence lookup), and confidence+entailment+grounding. Pre-registered practical
significance **ΔAUROC ≥ 0.005**; statistical significance alone is insufficient. Per condition,
pooled, and per seed (reproducibility).

## 8. Redundancy analysis

For each SCC feature: oriented univariate AUROC and maximum |correlation| with confidence,
entailment, and grounding features — documenting overlaps (e.g. *E identical to grounding*, *T is
augmentation-ensemble confidence*, *R is task-difficulty*).

## 9. Success criteria and verdict

A term **survives** only if its increment over the relevant base is statistically significant AND
practically meaningful (ΔAUROC ≥ 0.005) AND reproducible across seeds AND holds in a majority of
conditions (guarding against cross-condition pooling artifacts — e.g. a feature that is constant
within a condition can only separate conditions, not instances). Final verdict is exactly one of:
`SCC_ADDS_INDEPENDENT_SIGNAL`, `GROUNDING_ONLY`, `ENTAILMENT_REDESCRIPTION`, `CONFIDENCE_DOMINATES`,
`CONDITION_SPECIFIC_ONLY`, `NO_PRACTICAL_INCREMENT`, `INCONCLUSIVE`. Conclusions are not softened;
if SCC partly succeeds we state which components succeed, which fail, and *what the surviving
signal actually is*. **No inference-time control system is built** (explicit future scope).
