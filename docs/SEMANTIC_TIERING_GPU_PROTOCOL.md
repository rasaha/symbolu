# GPU Experiment Protocol — Semantic-Importance KV Tiering

**Status:** experiment design (pre-registration). **Prereq:** GPU pod (A100/H100), a
validated model from the portfolio, the existing read-skip stack.
**Companion:** `ndol/sim/semantic_tiering.py` is the *synthetic* mechanism study; this
protocol puts *real* numbers behind it — specifically it measures the one unknown that
synthetic study could not: **does a model's semantic-coherence score predict which KV the
model actually needs better than attention magnitude does?**

> **The single decision this resolves.** Keep, blend, or drop the idea of selecting hot KV by
> a semantic-coherence signal (SCC `C_i`, `S=cosine`) instead of / on top of attention
> magnitude (the read-skip / H2O / Quest baseline). **Pre-registered: if coherence adds no
> predictive power beyond attention (Exp A) AND does not improve quality-at-budget (Exp B)
> across ≥2 models, the hypothesis is dropped and not claimed.**

---

## 1. The two competing signals (per KV block, per layer)

Both are computed at decode time, per block `b` (the read-skip block granularity).

- **Attention magnitude (baseline)** — *already in the stack.* The decode-attention mass per
  block that `readskip_select.select_retained_blocks` ranks on (`block_score`, EMA-smoothed).
- **Semantic coherence (the candidate)** — must be **genuinely different from attention**, not
  a re-derivation of it. Test several candidates (which one works is itself open):
  1. `cos(v_b, c_t)` — cosine of the block's value-centroid to the running context
     representation `c_t` (EMA of value/hidden states). SCC's `S[i,j]` form. *Primary.*
  2. `cos(k_b, c_t)` — same on keys (pre-RoPE, per KVQuant practice).
  3. `‖v_b‖` — value-norm importance (a known cheap proxy; include as a sanity comparator).
  4. context-entropy / self-similarity of the block.
- **SCC blend** — `C_b = α·attn(b) + β·coh(b)` (extend with R/E/P terms if available). Tune
  `(α,β)` on a held-out split; report the blend, not just the tuned point.

## 2. Ground truth — what KV the model *actually* needs

The decisive reference is **leave-one-block-out (LOO) importance**: mask block `b`, re-run the
decode step, measure the change in output. This is expensive (one forward per block), so:

- `true_importance(b)` = KL(full-attention next-token dist ‖ dist with block `b` masked), or
  Δlogit of the argmax token. Higher = more truly needed.
- **Sampling:** rank all blocks by attention + coherence first; LOO only a **stratified sample**
  (e.g., 200 blocks/prompt spanning the score range + all sink/recent + all "disagreement"
  blocks where attention and coherence disagree most). Disagreement blocks are the experiment —
  they're where the signals' predictive power separates.

## 3. Experiment A — signal predictivity (the `w_sem` measurement)

Per (model, layer, prompt), over the LOO sample:
- `ρ_attn = Spearman(attention, true_importance)`
- `ρ_coh  = Spearman(coherence, true_importance)`
- **Incremental power (the honest metric):** partial correlation `ρ(coh, true_importance | attn)`
  — does coherence predict importance *after controlling for attention*? Equivalently, does a
  2-feature model (attn, coh) beat attn-only in held-out R²? **This is the real `w_sem`.**
- **Needle recall:** among blocks with high `true_importance` but low `attention`, what fraction
  are in the top-budget by `coherence` vs by `attention`? (Mirrors the synthetic needle metric.)

**Decision rule A:** coherence is useful iff partial correlation `> 0.1` (and significant) **and**
its needle recall meaningfully exceeds attention's, on ≥2 models. Otherwise `w_sem ≈ 0` → drop.

## 4. Experiment B — downstream quality at fixed KV budget (the decision-relevant test)

Decode the *same* prompts under each selector at matched budgets (sink+recent pinned, identical
across arms):

| arm | selector |
|---|---|
| **full** | all KV (oracle upper bound / quality reference) |
| **attention** | top-budget by attention magnitude (read-skip baseline) |
| **semantic** | top-budget by coherence |
| **SCC blend** | top-budget by `α·attn+β·coh` |
| **random+pins** | lower bound |

Sweep budget ∈ {3%, 6%, 12%, 25%, 50%}. Metrics vs **full**:
- **Needle-in-haystack** retrieval accuracy at 16K/32K/64K/100K (your existing needle harness).
- **Perplexity** on long docs (PG19 / proof-pile) vs full-attention PPL.
- **Greedy-token agreement** with full attention (your existing bit-/token-agreement metric).

Plot **quality vs budget** per selector. The decision number is the **budget to reach a fixed
quality target** (e.g., needle ≥ 0.95, or PPL within 1% of full).

**Decision rule B:** semantic/blend wins iff it reaches the quality target at a **smaller budget**
than attention (e.g., ≥15% smaller) on ≥2 models. A tie or loss → attention selection stands.

## 5. Confounds & honesty controls (read before trusting any positive)

- **Attention–coherence correlation.** High-attention tokens are often semantically central, so
  raw `ρ_coh` will look good even if coherence adds nothing. **Only the partial correlation /
  incremental-R² counts** — bake this into the analysis, not raw correlation.
- **Coherence must be cheap.** If computing `coh(b)` costs more than the read it saves, it's a
  non-starter for serving. Budget: ≤ a few % of decode-step time; report the measured overhead.
- **Proxy honesty.** LOO is the gold ground truth; any cheaper saliency proxy must be validated
  against LOO on the sample before use.
- **Layer/head heterogeneity.** Importance structure differs by layer; report per-layer, don't
  average away a signal that only helps in some layers.
- **Not exact.** This is approximate selection (same class as read-skip); the claim ceiling is
  *quality-equivalent on tested workloads*, never bit-exact (W1 is closed).
- **Pre-register** the decision rules above *before* running; don't tune the threshold to the data.

## 6. Models, workloads, scale

- **Models:** Llama-3.1-8B, Qwen2.5-7B, Mistral-7B-v0.3 (the validated portfolio).
- **Workloads:** needle-in-haystack (clear important-token structure — primary), RULER/LongBench
  subset, long-doc PPL.
- **Scale:** Exp A on ~50 prompts × stratified LOO sample (~few GPU-hours/model). Exp B on the
  needle/PPL suites you already run for int4_protected. Both ride the existing harness.

## 7. Integration with the existing stack

- **Signal injection:** add a `coherence_block_score()` next to the attention `block_score` that
  `ReadSkipController` already consumes; feed both (and the blend) into variants of
  `select_retained_blocks`. No new serving path — reuse the read-skip gather.
- **Harness:** drive Exp B through `Bench/scripts/phase9_decode_retention_harness.py` with a
  `--selector {attention,semantic,scc,random}` flag; reuse the needle/PPL/agreement reporters.
- **LOO (Exp A):** a standalone offline script that captures per-block KV and runs masked
  forwards on the sample — does not touch the serving path.

## 8. What success / failure looks like

- **Success (claimable):** partial-correlation `w_sem > 0.1` AND ≥15% smaller budget at fixed
  quality vs attention, on ≥2 models, with coherence overhead < few %. → a *measured*,
  model-robust differentiator: "we tier KV by semantic importance, not just attention magnitude,
  and it preserves quality at a smaller hot-KV budget." Then, and only then, it enters a brief.
- **Failure (drop, don't claim):** `w_sem ≈ 0` or no budget advantage. → attention-magnitude
  selection is sufficient; record the negative (like the TurboQuant retirement) and move on.

**Honest prior:** attention magnitude is a strong, hard-to-beat importance signal — much KV-
sparsity work shows it already captures most of what matters. The most likely outcome is a
**small** `w_sem` and a **blend** that is marginally better and mainly *more robust* (the
synthetic study's finding). Run it to find out; do not assume the win.
