# Experimental Protocol — Perturbation-Consistent Quad Retrieval

**Track:** separate package `quad_perturbation_consistency_sync/` (imports `qgr` read-only; the prior
Quad track is unmodified). **Pre-registered before results were read.**

> This is a **falsification** study. The null hypothesis is that task-only learning (BD-A)
> already finds the best retrieval organization and any explicit consistency objective reduces
> generalization. The alternative — that same-head perturbation-consistency improves
> generalization — is rejected unless BD-Sync **strictly and significantly exceeds BD-A** while
> passing all guardrails. This study does not implement USE, phase, synchronization across heads
> or layers, routing, gating, entropy/temperature penalties, or any inference-time component.

## Architecture (frozen, identical to the bounded track)

2-layer causal transformer, hidden 96, 4 heads, ff 384, context 64, **bounded Quad**
(`|S^Q| ≤ α`, α = 4, L2-normalized projected q/k). Optimizer AdamW, lr 4e-3, warmup 50,
grad-clip 1.0, 2500 steps, batch 32. Inference path unchanged. The only new component is a
training-only consistency term.

## Data — paired MQAR

Base task: num_kv 4, num_queries 2, vocab 32 (the frozen in-distribution condition). For each
base sample `x` a semantic-equivalent perturbation `x̃` is generated that **preserves every
query→value relation** but changes irrelevant structure: pair-order permutation, positional
filler (leading pad), and inserted distractor keys. All five arms consume the **same** base `x`
stream (identical seeds/order); only the extra term differs.

**Pair-bucket correspondence (no label).** Candidate positions are mapped to a canonical pair
identity (p = the p-th smallest key token) plus one "other" bucket for distractor keys; queries
are ordered canonically by query token. This makes per-head retrieval distributions comparable
across the two differently shaped sequences **without ever marking which pair is correct**.

## Consistency objective (training-only, label-free)

Per head independently, `A_h(x)` and `A_h(x̃)` are the pair-bucket retrieval distributions.

```
L_sync = mean_h  JS( A_h(x),  stopgrad(A_h(x̃)) )
```

Symmetric JS; gradient flows through `A(x)` only. Small fixed coefficient λ_sync (frozen in the
pilot); no scheduling, no adaptive weighting, no one-hot target, no cross-head or cross-layer
term.

## Arms (5 seeds: {0,1,2,3,4})

1. **BD-A** — task loss only (the bar).
2. **BD-D** — task + labelled Quad aux (existing auxiliary baseline), same base data.
3. **BD-Sync** — task + λ_sync·L_sync.
4. **BD-Sync-Early** — BD-Sync with L_sync hard-disabled after 25% of steps.
5. **Shuffled-Pair** — BD-Sync but `x̃` paired with an *unrelated* sample (generic-regularization
   control): if it matches BD-Sync, the effect is not from semantic consistency.

## Evaluation

Same benchmarks as prior tracks — in-distribution, longer context, higher distractor density,
two relation systems — plus an OOD suite (more associations; heavier distractors). Primary
generalization score = mean accuracy over the three preregistered hard conditions.

## Additional diagnostics

Attention entropy, cross-head diversity (mean pairwise JS between head distributions), layer
diversity (JS between layer-0 and aux-layer distributions), head specialization (1 − argmax
agreement across heads), selection accuracy, and — for the progressive study — distribution
drift.

## Progressive perturbation study

Stages 0–5 of increasing perturbation (original → minor filler → pair permutation → added
distractors → longer context → multiple simultaneous relation systems). Retrieval distribution
drift (JS between base and each stage) is measured at every stage → a degradation curve locating
where retrieval begins to fail.

## Guardrails (violation ⇒ INVALID for that arm)

- **G1 causal necessity** — zeroing the attention (Quad retrieval) must still reduce accuracy to
  chance. If another pathway begins carrying binding, reject.
- **G2 attention health** — reject entropy collapse (≈0), uniform attention, head collapse, or
  synchronized identical heads (cross-head diversity ≈ 0 with identical argmax).

## Primary success criterion & decision

Success = **generalization strictly exceeding BD-A**, statistically significant (paired
sign-permutation test over 5 seeds, p < 0.05), **while** preserving causal Quad retrieval (G1)
and staying inside healthy entropy/diversity bounds (G2). Otherwise the null stands.

Decision categories (exactly one): `SYNC_OUTPERFORMS_BD_A`, `SYNC_MATCHES_BD_A`,
`SYNC_BELOW_BD_A`, `SYNC_BREAKS_BINDING`, `SYNC_COLLAPSES_ATTENTION`, `INCONCLUSIVE`.

## Statistical method

Paired per-seed differences on the generalization score; exact paired **sign-permutation test**
(2⁵ = 32 sign flips) for the p-value (no scipy dependency); effect size = mean paired difference;
per-seed win count reported alongside.
