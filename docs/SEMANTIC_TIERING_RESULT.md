# Semantic KV-Tiering — Negative Result (Exp-A)

**Status: CLOSED — hypothesis REJECTED** across the full pre-registered protocol
(2 models × 3 layers × 3 prompts = **18 valid configs**), 2026-06-13.
**Harness:** `ndol/experiments/loo_importance.py`. **Protocol:** `docs/SEMANTIC_TIERING_GPU_PROTOCOL.md`.

> A durable negative, in the spirit of `CTM_plus/TURBOQUANT_RETIREMENT.md`: written so the
> next person does not re-run this dead end.

## Hypothesis
A **semantic-coherence** signal (SCC `S` = cosine of a KV block's mean value-vector to the running
context centroid) predicts which KV blocks the model actually needs **better than attention
magnitude** — which would enable *semantic-importance KV tiering* distinct from the
attention-based read-skip already shipped. Inverse also tested: **distinctiveness = −coherence**.

## Method
Ground truth = **multi-position leave-one-block-out (LOO) importance**: mask a KV block, sum the
KL of the next-token distribution over the last ≤64 prediction positions (causal). Compare how
well **attention / coherence / distinctiveness / rank-blends** rank the truly-important blocks
(recall of the top-15% important set), plus partial Spearman `(coherence | attention)`. A
validity gate rejects degenerate runs (masking-not-applied, too-few-positives, collinear/flat
signals). Decision Rule A pre-registered.

## Results (recall of important blocks; attention = baseline)

**Qwen2.5-7B-Instruct** (4096 ctx, block 32, 128 LOO/seed):

| seed | layer | attn | coh | dist | sccD | partial |
|---|---|---|---|---|---|---|
| 0 | −1 | 0.47 | 0.00 | 0.32 | 0.26 | −0.22 |
| 0 | 15 | 0.32 | 0.11 | 0.21 | 0.26 | −0.07 |
| 0 | 8  | 0.37 | 0.05 | 0.37 | 0.47 | −0.22 |
| 1 | −1 | 0.47 | 0.05 | 0.37 | 0.53 | −0.24 |
| 1 | 15 | 0.37 | 0.16 | 0.47 | 0.32 | −0.12 |
| 1 | 8  | 0.47 | 0.00 | 0.37 | 0.47 | −0.16 |
| 2 | −1 | 0.53 | 0.11 | 0.42 | 0.42 | −0.10 |
| 2 | 15 | 0.42 | 0.11 | 0.37 | 0.42 | −0.14 |
| 2 | 8  | 0.37 | 0.11 | 0.42 | 0.42 | −0.10 |
| **mean** | | **0.42** | **0.08** | 0.37 | 0.42 | **−0.15** |

→ coherence **anti-predictive** (negative partial in all 9); distinctiveness real (0.37) but **< attention**; blend ties (Δ=0.00).

**Phi-3.5-mini-instruct** (same config):

| seed | layer | attn | coh | dist | sccD | partial |
|---|---|---|---|---|---|---|
| 0 | −1 | 0.42 | 0.16 | 0.11 | 0.26 | +0.24 |
| 0 | 15 | 0.42 | 0.21 | 0.11 | 0.32 | +0.02 |
| 0 | 8  | 0.47 | 0.11 | 0.11 | 0.11 | +0.23 |
| 1 | −1 | 0.32 | 0.26 | 0.21 | 0.37 | −0.06 |
| 1 | 15 | 0.37 | 0.05 | 0.21 | 0.42 | −0.08 |
| 1 | 8  | 0.42 | 0.16 | 0.26 | 0.42 | +0.02 |
| 2 | −1 | 0.32 | 0.26 | 0.11 | 0.26 | +0.19 |
| 2 | 15 | 0.53 | 0.11 | 0.16 | 0.32 | −0.02 |
| 2 | 8  | 0.42 | 0.21 | 0.11 | 0.32 | +0.21 |
| **mean** | | **0.41** | 0.17 | 0.15 | 0.37 | +0.08 |

→ attention beats every alternative (best-alt 0.37, Δ=−0.04); coherence weakly +partial but low recall; distinctiveness ≈ coherence.

## Verdict: DROP

**Across both models / all 18 valid configs, attention magnitude is the best single
KV-importance signal. No coherence-derived signal (coherence, distinctiveness, or blend) beats
it on either model.**

The decisive evidence is the **cross-model inconsistency**: on Qwen, *distinctiveness* ≫ coherence
("important = distinctive," partial −0.15); on Phi, this *flips* (coherence weakly positive,
distinctiveness lower). The importance↔coherence relationship is **model-dependent**, so there is
no robust, general semantic lever to exploit. A real signal would replicate; it doesn't.

## Implications
- **Semantic-importance KV tiering is not a viable differentiator.** Attention-magnitude read-skip
  (already shipped) is the correct selector — it is hard to beat because it directly captures
  what the model uses.
- This was the **last live novelty hypothesis** in the NDOL exploration. Combined with the W1
  (read-skip is approximate, not exact) and W3 (NAND tiering hardware-capped ~1.14×) findings,
  **no new moat emerged.** The bankable KV asset remains **int4_protected quantization**
  (~1.8× density, measured, quality-preserving) + attention read-skip.

## Caveats / what was NOT tested
- Only the `cos_value` coherence signal (centroid cosine). `value_norm` and `cos_key` modes, and a
  *learned* probe over richer features, were not swept — but the prior is now strongly negative.
- Needle-haystack workload at 4096 ctx; longer contexts blocked by `output_attentions` memory.
- A trained selector could in principle find a signal these hand-crafted ones miss; that is a
  larger effort and is not justified given a model-dependent (non-replicating) effect here.
