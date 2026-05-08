# Mode B Phase 4 — Trigonometric Position Scoring

**Status:** design landed (May 2026). Implementation **not
started** — estimated 5 days of code + 1 GPU-day for
calibration + validation. Authorization required to start
implementation.

**Audience:** the engineer (possibly future-me) who will
write the code. Conservative framing throughout: every
design choice is justified against either the TriAttention
paper's evidence or CTM+'s existing audit-passed framework.

## §1 Why Phase 4 instead of Phase 3 GPU validation

The Phase 2 audit-pass found that CTM+ without attention
forwarding collapses to ~LRU + access-frequency (the 0.35·attn
term zeroes out, ENTITY classification never fires). The
implicit Phase 3 fix forwards real attention into the score
at a cost of ~10–15% per-token overhead.

**TriAttention (Mao et al., arXiv:2604.04921, April 2026)
contests Phase 3's premise.** They show that:

1. Pre-RoPE Q/K vectors cluster around fixed centers that are
   model-intrinsic (stable across positions, contexts, even
   data domains). 84.7% of Qwen3-8B heads have R > 0.95.
2. From these centers, a trigonometric series in Q-K distance
   predicts attention with Pearson r ≈ 0.6–0.9 across heads
   on Qwen3, Qwen2.5, Llama3, GLM-4.7-Flash MLA.
3. Scoring keys via this trig series — **without computing
   real attention** — beats attention-based methods on both
   reasoning (AIME25: 32.9% vs SnapKV's 20.0% at fixed
   2048-token budget) and general long-context (LongBench:
   wins 11/16 subtasks vs Ada-KV+SnapKV's 9/16).

If Phase 3 is solving a problem TriAttention's static signal
already eliminates, Phase 3 GPU validation is wasted spend.
**Phase 4 incorporates the trig signal into CTM+'s scoring
formula and re-asks the experimental question.**

See `papers/triattention_notes.md` for the full mechanism +
results summary.

## §2 Phase 4 score formula

```
S_phase4(block) = 0.30 · S_trig
                + 0.25 · S_recency
                + 0.15 · S_freq
                + 0.30 · S_norm

  where
    S_trig    = trigonometric distance preference
                using calibrated Q centers + key's pre-RoPE
                vector (per-block aggregated)
    S_recency = exp(-α · age) — KEEP from CTM+ Phase 2
    S_freq    = log-saturated access count — KEEP
    S_norm    = TriAttention's norm-based complement,
                weighted by (1 - R_f)
```

Removed: `0.35 · attn` (the term Phase 3 was meant to populate).
Removed: `0.30 · position-class` (subsumed by S_trig + the
SINK pin from prefill).

Kept: S3-FIFO admission policy. **CTM+'s admission win on
RAG is independent of which scoring policy decides eviction;
TriAttention has no admission policy.**

## §3 Per-block aggregation of S_trig

TriAttention scores per-token. CTM+ scores per-block (block
size 16 default). Block-level integration with vLLM's
PagedAttention is materially cheaper per eviction than
per-token.

For a block holding positions `[p, p+1, ..., p+block_size-1]`,
the per-block S_trig is the sum over the block's positions:

```
S_trig(block, future_offset Δ_future) =
    Σ_{p ∈ block} Σ_f ‖E[q_f]‖ · ‖k_f(p)‖ · cos(ω_f·(Δ_future - p) + φ_f(p))
```

Average over a small set of future offsets (Phase 4 default:
`{1, 2, 4, 8, 16}` — 5 offsets, vs TriAttention's 17). The
reduced set is justified for chat/RAG/agentic workloads where
average decode horizon is 100–500 tokens, not AIME's 32K
tokens. **Tunable per workload.**

## §4 Calibration pipeline

One-time, per model. Output: `q_centers.{model_name}.npz`
checkpointed in `bench_out/calibration/`.

```python
def calibrate_q_centers(model, calibration_data, num_layers, num_heads):
    """Collect pre-RoPE Q statistics per (layer, head, frequency_band).

    Returns:
        E_q[layer, head, band] — complex-valued mean Q vector
        E_q_norm[layer, head, band] — mean Q magnitude
        R[layer, head, band] — Mean Resultant Length
    """
    # Hook every Attention layer's pre-RoPE Q projection.
    # Run forward passes on calibration_data (50k–200k tokens).
    # Accumulate per-(layer, head, band) statistics.
    # Save as numpy archive.
```

**TriAttention shows calibration is data-quality-robust:**
HTML scrape and ShareGPT chat both yield ~46% AIME24 accuracy
post-calibration. CTM+ Phase 4 can therefore use **a single
fixed calibration corpus across deployments** without
worrying about per-partner re-calibration.

**Calibration cost:** ~1 GPU-hour per model (load + forward
pass over 200k tokens). One-time, cached.

## §5 GQA / MLA handling

TriAttention's normalize-then-aggregate for GQA:

```
for query head g in 1..G:
    S_g(block) = compute_score_using(Q_centers[head=g], block)
    S_g_zscore(block) = (S_g(block) - mean_g) / std_g

S_final(block) = max_g S_g_zscore(block)
```

**Phase 4 inherits this directly.** vLLM's GQA / MLA
handling exposes the per-query-head structure already; we
loop over query heads in the score function.

## §6 Window-based pruning trigger

CTM+ today scores at every potential eviction event (vLLM's
allocator-driven). TriAttention triggers pruning every 128
generated tokens — much less frequent.

**Phase 4 default: every 128 tokens** (matching TriAttention).
The cache is allowed to grow above the budget between trigger
windows; at the trigger, we score all keys, retain top-B,
evict the rest. The lazy approach amortises scoring cost
across many evictions.

This matches the audit-pass discipline: instrument and time
the pruning trigger so partner-facing diligence has the
"how often does CTM+ pay scoring cost" answer.

## §7 What Phase 4 will and will NOT validate

### Will validate (after GPU run + four-cell sweep)

* Whether TriAttention's static trig signal generalises from
  reasoning workloads (their headline) to CTM+'s chat / RAG /
  agentic canonical workloads.
* Whether the trig signal alone (no real attention) produces
  better scoring than CTM+'s pre-Phase-3 recency+frequency.
* Whether real attention forwarding (Phase 3) adds anything
  over the trig signal — the optional Phase 3 cell answers
  this.
* Per-component runtime cost: the timing instrumentation
  shipped in commit `7b5df3f` already captures `evict_p99_us`,
  `attn_capture_total_seconds`, `tokens_per_second`. Adds
  S_trig compute time as a new component.

### Will NOT validate

* **CTM+'s simulator headlines on real attention.** The
  simulators (Mode A, KVSimulator, replay) all use synthetic
  attention. Phase 4 produces real-model evidence on chat/RAG/
  agentic but the link to those headlines is calibration not
  reproduction.
* **Phase 4 generalisation to fine-tuned models partners run.**
  Calibration is per-model; partners running custom variants
  need a one-time calibration pass. Documented as Phase-4
  onboarding cost.
* **Production-scale latency.** A100-spot single-cell
  measurements aren't production-grade workloads (sustained
  load on H100s/H200s in real serving stacks).

## §8 Implementation scope

| Component | Effort | CPU-testable? |
|---|---:|---|
| Calibration pipeline (collect Q/K statistics offline) | 1 day | Math testable; full run needs GPU |
| Per-head per-band stats accumulator + .npz checkpoint | 0.5 day | Yes |
| `S_trig` score function (per-block aggregated) | 0.5 day | Yes |
| `S_norm` with `(1 - R_f)` weighting | 0.5 day | Yes |
| Future-offset averaging over `D = {1, 2, 4, 8, 16}` | 0.25 day | Yes |
| GQA z-score normalize + max aggregation | 0.5 day | Yes |
| Window-based pruning trigger (every 128 tokens) | 0.5 day | Yes |
| Calibration cache load/save (.npz) | 0.5 day | Yes |
| Streaming runner integration: `--phase4-trig` CLI flag | 0.5 day | Yes |
| Tests + docs | 1 day | Yes |
| **Total code** | **~5–6 days** | Mostly yes |
| GPU calibration sweep (per model) | 1 GPU-hour | No |
| GPU four-cell experiment (LRU / Phase 2 / Phase 4 / Phase 3) | 1 GPU-day, ~$1 | No |

## §9 Four-cell experiment plan

After Phase 4 implementation lands and a GPU pod is available:

| Cell | Purpose | Flags |
|---|---|---|
| LRU + prefix caching | apples-to-apples vLLM-native baseline | `--enable-prefix-caching` |
| CTM+ Phase 2 | recency + frequency only (audit-finding-acknowledged baseline) | `--ctm-plus` |
| **CTM+ Phase 4** | **trig + recency + freq + S3-FIFO** (the new headline) | `--ctm-plus --phase4-trig` |
| CTM+ Phase 3 | optional ablation: real attention forwarding | `--ctm-plus --phase3-attention` |

Run each cell on the v4 hyperparameter regime that Phase 1
proved engages swap (`GPU_MEM_UTIL=0.26`, `arrival_rate=6/sec`,
`max_decode_tokens=2048`, prompt-length-choices weighted long).

**Decision tree:**
* If Phase 4 ≈ Phase 3 in `swap_out_blocks` and `tokens/sec`:
  drop Phase 3 (cheaper), Phase 4 is the production policy.
* If Phase 4 < Phase 3 (Phase 3 produces better cache outcomes
  despite the overhead): real attention is irreplaceable for
  CTM+'s workloads. Phase 4 doesn't replace Phase 3, but the
  trig signal can still augment.
* If Phase 4 ≈ Phase 2 (no win over recency+frequency
  alone): TriAttention's trig signal doesn't generalise to
  CTM+'s workloads. Defer the trig score; revisit if a partner
  workload looks more like AIME than chat.
* If Phase 4 < Phase 2 (worse than the ablation): the
  calibration is broken or the per-block aggregation is
  wrong. Diagnose with the timing + sample-recorded
  metadata.

## §10 Honest scope statement (audit-pass discipline)

**Phase 4 is not a replacement for Phase 3 — it is a
substitute hypothesis.** The audit-pass discipline that
caught Phase 2's HIGH finding catches this too: we don't
ship Phase 4 numbers as "CTM+ wins on a real model" until
the four-cell experiment runs and the comparison is in
the canonical record.

**TriAttention's evidence is empirical (their AIME +
LongBench results). It is not a mathematical guarantee
that the trig signal beats attention forwarding on any
workload.** The four-cell experiment is the discipline
check.

**If Phase 4 wins**, the diligence story strengthens: CTM+
becomes "a workload-conditional optimization combining
TriAttention-style scoring with S3-FIFO admission and
online recency tracking, the only stack with all three."
**If Phase 4 loses**, the diligence story still holds —
we've added one more independent simulator-equivalent test
and documented it.

## §11 Decision log

* **Removed `0.35 · attn`** from the score formula.
  TriAttention's evidence makes this term contestable.
  Phase 3 attention forwarding becomes optional ablation.
* **Removed `0.30 · position-class`.** SINK behaviour is
  encoded in the trig score's center-derived distance
  preference. ENTITY classification is approximated by
  S_trig's continuous output.
* **Kept `S3-FIFO` admission.** TriAttention has no
  admission policy. RAG's −100% slow-tier-reads headline
  comes from CTM+'s admission, not its scoring.
* **Reduced future-offset count from 17 to 5.** Justified
  by CTM+'s shorter decode horizons (chat/RAG/agentic
  decode 100–500 tokens vs AIME's 32K). Tunable per
  workload if validation surfaces a need.
* **Calibration corpus = single fixed dataset across
  deployments.** TriAttention's data-quality-robust result
  (Google HTML works) makes per-partner calibration
  unnecessary. Onboarding: drop in the model, run one-time
  calibration script, ship.

## §12 Open questions for implementation

1. **Frequency-band selection.** TriAttention uses
   "dominant" bands — top-K by `E[‖q_f‖]·E[‖k_f‖]` — for
   visualization. Phase 4 score formula sums over all
   bands; should we restrict to dominant for compute
   reduction?
2. **Per-head budget.** TriAttention mentions "head-specific
   budgets" as future work. Phase 4 default: uniform budget
   across heads. Per-head adaptive budgeting is a follow-up.
3. **Calibration on a fine-tuned variant.** If a partner
   runs Qwen2.5-7B-Code (custom fine-tune), do we need to
   re-calibrate? TriAttention's robustness suggests no, but
   we should validate before claiming "zero per-partner
   onboarding cost."
4. **Block-level vs token-level for vLLM.** Phase 4 inherits
   CTM+'s block-level granularity. For very small blocks
   (block_size=4), per-token approaches the per-block; for
   large (block_size=64), block-level diverges. Confirm
   block_size=16 (vLLM default) behaves correctly.

These questions inform the implementation prompt. The
design itself is fixed enough to start coding once
authorization arrives.
