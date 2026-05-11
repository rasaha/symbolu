# TriAttention — paper notes for CTM+ comparison

**Citation:**
Mao W., Lin X., Huang W., Xie Y., Fu T., Zhuang B., Han S., Chen Y.
"TriAttention: Efficient Long Reasoning with Trigonometric KV Compression."
arXiv:2604.04921 (April 2026). MIT, NVIDIA, ZJU.
https://arxiv.org/abs/2604.04921 ·
https://github.com/WeianMao/triattention

This file is **notes + summary** for the CTM+ Phase-4 design. It
captures the mechanism, the key results, and the implications
for the CTM+ roadmap. The full paper text is not redistributed
here (CTM+'s repo is not the right home for that); this is fair-
use commentary + verbatim abstract for audit traceability.

## Abstract (verbatim)

> Extended reasoning in large language models (LLMs) creates
> severe KV cache memory bottlenecks. Leading KV cache
> compression methods estimate KV importance using attention
> scores from recent post-RoPE queries. However, queries rotate
> with position during RoPE, making representative queries very
> few, leading to poor top-key selection and unstable reasoning.
> To avoid this issue, we turn to the pre-RoPE space, where we
> observe that Q and K vectors are highly concentrated around
> fixed non-zero centers and remain stable across positions —
> Q/K concentration. We show that this concentration causes
> queries to preferentially attend to keys at specific distances
> (e.g., nearest keys), with the centers determining which
> distances are preferred via a trigonometric series. Based on
> this, we propose TriAttention to estimate key importance by
> leveraging these centers. Via the trigonometric series, we
> use the distance preference characterized by these centers
> to score keys according to their positions, and also leverage
> Q/K norms as an additional signal for importance estimation.
> On AIME25 with 32K-token generation, TriAttention matches
> Full Attention reasoning accuracy while achieving 2.5×
> higher throughput or 10.7× KV memory reduction, whereas
> leading baselines achieve only about half the accuracy at
> the same efficiency.

## Mechanism, in brief

1. **Empirical observation.** Pre-RoPE Q/K vectors cluster
   tightly around fixed centers across heads, layers, and
   architectures. Quantified by Mean Resultant Length
   `R = ‖E[q]‖ / E[‖q‖]`. Qwen3-8B: 84.7% of heads have
   R > 0.95. GLM-4.7-Flash MLA: 96.6% of heads.

2. **Mechanistic consequence.** When Q/K concentrate, the RoPE
   attention logit reduces to a trigonometric series in Q-K
   distance Δ:
   `logit(q,k) ≈ Σ_f ‖E[q_f]‖·‖E[k_f]‖·cos(ω_f·Δ + φ_f)`
   where ω_f are RoPE's geometric frequencies and φ_f is the
   phase difference between Q and K centers in band f.
   **Attention preferences over distance are predictable from
   the centers alone**, no attention scores needed.

3. **Reconstruction quality.** Pearson r ≈ 0.6–0.9 between
   predicted and actual attention across all heads on Qwen3,
   Qwen2.5, Llama3 (mean > 0.5).

4. **TriAttention scoring.**
   - `S_trig(k, Δ) = Σ_f ‖E[q_f]‖·‖k_f‖·cos(ω_f·Δ + φ_f)` ·
     captures distance preference using **the actual key's**
     pre-RoPE vector and **the calibrated Q center**.
   - `S_norm(k) = Σ_f (E[‖q_f‖] - ‖E[q_f]‖)·‖k_f‖` ·
     norm-based complement, weighted by `(1 - R_f)` so it
     contributes only when concentration is weak.
   - Final: `S(k, Δ) = S_trig + S_norm`, averaged over
     future offsets `Δ ∈ {1, 2, 4, ..., 2^16}`.

5. **GQA handling.** Per-query-head scoring →
   z-score-normalize per head → max-aggregate.

6. **Window-based pruning.** Every 128 generated tokens,
   re-score and prune to budget B (top-B retained).

7. **Pre-calibration.** One-time offline pass on a
   calibration dataset (50k–960k tokens; quality-robust
   per Table F — Google HTML works as well as ShareGPT
   chat data). Statistics saved per model.

## Headline results (verbatim from paper tables)

**AIME25 at fixed KV budget = 2048 tokens (Qwen3-8B):**

| Method | Accuracy |
|---|---:|
| Full Attention | 40.8% |
| SnapKV | 20.0% |
| R-KV | 17.5% |
| **TriAttention** | **32.9%** |

**MATH 500 at fixed KV budget = 512 tokens (Qwen3-8B):**

| Method | Accuracy |
|---|---:|
| Full Attention | 69.6% |
| SnapKV | 49.2% |
| R-KV | 46.4% |
| **TriAttention** | **56.0%** |

**Throughput (Qwen3-8B, A100 80GB) at matched accuracy:**

| Benchmark | Full Attention | TriAttention | Speedup |
|---|---:|---:|---:|
| MATH 500 | 222.8 tok/s @ 69.6% | 1405.2 tok/s @ 68.4% | **6.3×** |
| AIME24 | 222.8 tok/s @ 57.1% | 413.9 tok/s @ 54.6% | **1.9×** |
| AIME25 | 222.8 tok/s @ 40.8% | 563.5 tok/s @ 40.8% | **2.5×** |

**LongBench (16 subtasks, Qwen3-8B, 50% KV budget):** TriAttention
average 48.1, wins 11/16 subtasks. Best baseline (Ada-KV+SnapKV)
45.6.

**RULER (4K context):** TriAttention 66.1, +10.5 over SnapKV.

## Implications for CTM+ Phase-4

The audit pass on Phase 2 surfaced that CTM+ without real
attention degenerates to ~LRU + access-frequency. The
implicit Phase-3 fix was to forward real attention into the
score, paying ~10–15% per-token overhead. **TriAttention's
results contest the premise**: their static signal (no
attention computation) beats attention-based methods on
both reasoning and general long-context benchmarks.

### Where CTM+ and TriAttention compose (orthogonal)

* **S3-FIFO admission.** TriAttention is eviction-only.
  CTM+'s admission policy keeps one-shot scans (RAG) out of
  the working set — the −100% slow-tier-reads headline.
  Independent of which scoring policy decides eviction.
* **Online recency.** TriAttention's score is essentially
  static per (key, future-distance). For agentic workloads
  with Markov-dwell on hot blocks, recency is the signal
  TriAttention's static analysis won't capture.
* **Access-frequency.** Counter-based, cheap; signals
  block reuse independently.
* **Block-level integration.** vLLM-friendly; no change.

### Where CTM+ and TriAttention substitute (competitive)

* **Phase 3 attention forwarding** is competitively redundant
  with TriAttention's trig score. Their AIME25 wins against
  attention-based SnapKV (32.9% vs 20.0%) are direct evidence
  the trig signal matches or beats real attention as a
  scoring source — at much lower runtime cost.
* **Position-class system** (SINK / ENTITY / RECENT / FILLER)
  may be redundant once the trig score is in place. SINK
  behaviour emerges naturally from the centers (initial
  positions encoded in the centers' frequency-space
  signature); ENTITY classification is approximately what
  S_trig produces continuously.

### Recommended Phase 4 score formula

```
score = 0.30 · S_trig(distance preference, calibrated centers)
      + 0.25 · recency
      + 0.15 · access_frequency
      + 0.30 · S_norm(key magnitude with R-weighting)

Plus:
  - S3-FIFO admission                  (KEEP — TriAttention has none)
  - Per-model offline calibration      (NEW — Q/K centers)
  - Block-level aggregation            (KEEP — vLLM-friendly)
  - Window-based pruning every 128     (NEW — TriAttention's β)
```

The 0.35·attn term from CTM+'s pre-Phase-3 formula is gone.
Replaced by 0.30·S_trig + 0.30·S_norm, both backed by
TriAttention's empirical evidence.

### Detailed Phase 4 design

See `Bench/scripts/MODE_B_PHASE4_DESIGN.md`.

## What Phase 4 does NOT inherit from TriAttention

* **Per-token granularity.** Their scoring is per-key.
  CTM+ aggregates per-block (block_size=16). Block-level
  fits vLLM's PagedAttention with much less per-eviction
  overhead. We sum S_trig contributions over a block's
  positions.
* **Future-offset averaging over 17 offsets.** Their
  `D = {1, 2, 4, ..., 2^16}` set of offsets adds compute.
  For chat/RAG/agentic (CTM+'s target workloads), 4–8
  offsets may suffice. Tunable.
* **Reasoning-task focus.** Phase 4 must validate on
  CTM+'s canonical workloads (chat/RAG/agentic) plus
  reasoning, not just AIME.

## Open questions for the partner conversation

1. **Does the trig signal generalize to bursty
   chat/RAG?** TriAttention shows LongBench wins (general
   long-context) but the production workload partners run
   may differ in attention-pattern shape from the AIME math
   reasoning that drives the headline 10.7× number.
2. **Does the 1-hour calibration step block partner
   onboarding?** TriAttention says calibration is robust
   (HTML-quality data works). For partners running custom
   fine-tunes, calibration is per-model — adds an
   onboarding step CTM+ today doesn't require.
3. **Is the 2.5× / 10.7× claim achievable on CTM+'s
   workloads?** AIME generates 32K tokens of CoT; chat
   workloads decode 100–500 tokens per request. The
   memory-pressure regime is fundamentally different; the
   speedup may not transfer.

These three are validation questions Phase 4 + the four-cell
experiment must answer before claiming the trig signal as
a CTM+ headline.
