# Experimental Design — Same-Head Perturbation-Consistency for Quad Retrieval

**Track:** independent falsification study (CPU-only). Separate package; reuses the prior
`quad_generative_regularization` (`qgr`) package **read-only**. No production code or previous
research package is modified.

## 1. Hypothesis under test (to be *falsified*, not validated)

> The problem is not *which* key Quad retrieves; it is *how invariant* the learned retrieval
> function is under benign perturbations.

Operationalised research question:

> Can a **same-head perturbation-consistency objective, using no retrieval labels**, improve
> Quad generalization **beyond the task-only bounded baseline (BD-A)**?

**Null hypothesis (H0):** task-only learning already discovers the best retrieval organization,
and any explicit consistency objective reduces (or does not improve) generalization vs BD-A.

We attempt to **reject H0**. We reject it only if the new method shows a *statistically
significant* improvement over BD-A while satisfying both guardrails. Otherwise H0 stands.

## 2. What we inherit (unchanged) from prior work

* **Model.** `QuadTransformer` (2 layers, 4 heads, hidden 96). Attention *is* the authentic
  Quad generative scorer `S^Q_{i,j} = (W_q·LN(h_i))·(W_k·LN(h_j))/√d_h`, causally masked. The
  **bounded** geometry (L2-normalise projected q/k, fixed non-learnable α=4) is used for every
  arm — it is the regime in which BD-A is the strongest generalizer.
* **Task / benchmark.** Deterministic MQAR. Frozen config: `num_kv=4, num_queries=2`,
  vocab 32, 2500 steps, AdamW lr 4e-3. Benchmark suite (identical to prior studies):
  in-distribution, longer-context (+32 distractors), higher-distractor (num_kv=8), two-systems
  (2 relation systems), and the seq-length curve.
* **Baselines (produced by the unmodified prior package):**
  * **BD-A** — bounded, task-only. *This is the benchmark.* (Prior best generalizer.)
  * **BD-D** — bounded + Quad-native auxiliary (explicit retrieval labels). Near-perfect
    retrieval selection, worst OOD generalization.
* **Read-only causal tools** (`qgr.causal`) for the Guardrail-1 ablation.

## 3. The consistency objective (BD-Sync)

For each training step we take the standard batch (view **O**) and build **one**
semantically-equivalent view **P** that changes only irrelevant surface factors — distractor /
pair order, distractor position, additional irrelevant distractors, query order, and a leading
positional shift. Every key→value association and every query→answer is preserved.

For each attention head *h* and each query, the head produces a distribution over the candidate
keys (softmax of `S^Q` restricted+renormalised to the candidate set). The objective penalises
the **symmetric Jensen-Shannon divergence** between head *h*'s candidate distribution on view O
and on view P, aligned by **token identity** (canonical sort of candidate keys / queries):

```
L_consistency = mean_{b,h,q}  JS( p^O_{b,h,q} ,  stopgrad( p^P_{b,h,q} ) )
L_total       = L_task(view O)  +  λ · L_consistency
```

Honoured constraints (and deliberately excluded items):

* **same-head only** — head *h*(O) vs head *h*(P); never cross-head or cross-layer.
* **symmetric JSD** — the divergence is symmetric JS (not KL/L2).
* **stop-gradient (default) or EMA self-target** — one side detached; EMA variant available.
* **small fixed coefficient** — a single λ, frozen by a disjoint-seed pilot.
* **no retrieval labels** — the cross-view correspondence is the augmentation's own bookkeeping
  (which surface position holds which key/query *token*), exactly like image-augmentation
  consistency. *Which key is correct is never used by the loss.*
* **behavioural, not correctness** — the loss regularises stability of the distribution, not
  whether it points at the right key.
* **No** retrieval labels, cross-head/-layer sync, entropy penalties, temperature/normalisation
  changes, architecture changes, inference-time changes, USE/phase, routing, or teacher forcing.
  The consistency term is read from the model's own forward-path `S^Q` and adds **no** inference
  operation (a λ=0 run is **bit-identical** to BD-A — verified in `tests/test_equivalence.py`).

## 4. Experimental arms

| Arm | Definition | Role |
|---|---|---|
| **BD-A** | bounded, task-only | **benchmark** (prior best generalizer) |
| **BD-D** | bounded + Quad auxiliary (retrieval labels) | existing auxiliary baseline |
| **BD-Sync** | BD-A + λ·same-head JS consistency (full duration) | proposed method |
| **BD-Sync-Early** | consistency active only first 10% of steps, then hard-off | schedule variant |
| **BD-Shuffled** | same machinery, key-identity alignment randomly permuted | generic-regularization control |

**Shuffled-pair control.** The control keeps every tensor, shape, and penalty scale identical
but replaces the true token-identity alignment with a random permutation of the key axis. If
BD-Sync's effect were mere generic regularization, BD-Shuffled would reproduce it. If the effect
requires *semantic* consistency, BD-Shuffled will not (and may degrade attention).

## 5. Evaluation (same suite as prior studies) + reported diagnostics

Benchmark accuracy: in-distribution, longer-context, higher-distractor, two-systems, seq-length
curve. Additionally reported per arm/seed: attention entropy, head diversity, head
specialization, perturbation stability, retrieval stability, selection accuracy (diagnostic
only), and the Guardrail-1 causal attention ablation.

## 6. Progressive perturbation analysis

Degradation curves over a progression — original → small positional perturbation → distractor
permutation → additional distractors → longer context → multiple simultaneous relation systems
— measuring how attention consistency (same-head JS) and accuracy degrade. H1 predicts BD-Sync
degrades more slowly than BD-A.

## 7. Guardrails (a run is invalid if either fails)

* **G1 — Quad causal necessity.** Zeroing the attention (Quad retrieval) output must collapse
  in-distribution accuracy to chance (≤ ~1.5× chance). If BD-Sync no longer depends on Quad, the
  comparison is meaningless.
* **G2 — attention health.** Reject entropy collapse, (near-)uniform attention, head collapse,
  or loss of specialization (pre-registered thresholds in `qpc/health.py`).

## 8. Statistics

Paired over seeds (arms share seeds). Primary: one-sided Wilcoxon signed-rank (method > BD-A) on
mean-hard generalization; also two-sided Wilcoxon, paired t, and a seeded paired bootstrap 95%
CI, plus per-condition tests. **Reject H0** iff one-sided Wilcoxon p<0.05 **and** the bootstrap
CI excludes 0 **and** mean Δ ≥ 0.02, **and** both guardrails hold. λ is frozen on **disjoint**
pilot seeds (100–101); confirmatory seeds are 0–7 (extendable).

## 9. Success criterion

The new method succeeds only if it (a) **significantly exceeds BD-A** generalization, (b)
**preserves Quad's causal role** (G1), and (c) **satisfies both guardrails**. If it cannot
outperform BD-A, the conclusion is that perturbation-consistency provides **no net benefit over
task-only learning** and H0 is not rejected.
