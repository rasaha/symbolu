# Phase 8a — Eviction remeasurement scaffold

> **Status:** scaffold landed, gated behind Phase 8b green. **DO NOT
> RUN until the bridge composition cell (Day 5b) reports
> `forward_block_attention_nonzero_sum_calls > 0`.** Running 8a
> beforehand will reproduce the v5 -20% number and teach us
> nothing about the path forward — see `PHASE8_EVICTION_AUDIT.md`.

## What this scaffold is

A measurement runbook for the v5-style chat_32k workload under
FOUR configurations, executed only AFTER the Route-A + Phase 3
attention bridge is verified working end-to-end on GPU. Phase 3
(real attention forwarding) and Phase 4 (trig scoring) are mutex
in the runner (`runner_vllm_streaming.py:601-606`); they're
explicitly "competing hypotheses; run in separate cells." 8a's
four-cell layout respects that:

| Cell | Flags | Purpose |
|---|---|---|
| `lru_baseline` | `--enable-prefix-caching` | Reference point (prefix caching ON for cell-symmetry, see risk #1) |
| `ctm_plus_phase3` | `--ctm-plus --phase3-attention` | **Did the bridge close the -20% Python-dispatch tax?** Real attention reaches `forward_block_attention`. |
| `ctm_plus_phase4_trig` | `--ctm-plus --phase4-trig-calibration <path> --phase4-cython-evictor --phase4-fast-hooks` | The v5 algorithm cell, now with PER-LAYER calibration. Does the algorithm win survive the methodology fix? |
| `ctm_plus_phase4_trig_int4` | The previous row + `--int4-kv-route-a` | Combined-stack partner-relevant operating point. Phase 4 trig is v5's strongest algorithm, so the combined cell uses it. |

The script is `phase8a_remeasure.sh`. It runs three 60s chat_32k
runs and writes a `PHASE8A_REPORT.md` comparing throughput +
swap-out/decode_token across the three cells.

## Prerequisites (the script will refuse to run without them)

1. **Bridge green.** `bench_out/PHASE8B_GPU/day5b_bridge_composition.json`
   exists and reports `forward_block_attention_nonzero_sum_calls > 0`.
   This is the most important gate — see the precondition check at
   the top of `phase8a_remeasure.sh`.
2. **Per-layer calibration available.** `Bench/calibration/qwen25_7b_per_layer.json`
   exists. v5 used pooled-layer calibration (MRL=0.221, below the
   ≥0.3 method bar). 8a MUST use per-layer to be partner-credible.
   Recalibration is a separate one-shot script (~$0.05 wall) NOT
   included here — assume it's been run before 8a.
3. **Prefix-caching policy locked.** `PREFIX_CACHING_MODE` env var
   set to either `disabled` or `matched`. See "Three risks" below.

## Three risks any remeasurement must handle

These are the audit's §"Three risks for any remeasurement" items.
All three are wired into `phase8a_remeasure.sh`.

### 1. Prefix-caching disruption

**v5 finding:** CTM+ ran at 99% peak KV utilization, LRU at 57%
— not apples-to-apples (the LRU baseline benefited from prefix
caching keeping its working set small; CTM+ was forced into
sustained eviction pressure). The -11% swap_out comparison
straddled two different cache regimes.

**Runner constraint:** CTM+ FORCES `--enable-prefix-caching` ON
(see `run_streaming.py:83-86`: "CTM+'s patch installs on
PrefixCachingBlockAllocator's evictor slot"). You CANNOT disable
prefix caching on the CTM+ cells without redesigning the install.
So the audit's "PREFIX_CACHING_MODE=disabled" option was naive.

**The actual mitigation:** force `--enable-prefix-caching` ON for
the LRU baseline too, so both cells use the same cache regime.
`phase8a_remeasure.sh` does this. This is the **symmetric setup**
— both cells benefit from prefix caching equally, so the policy
becomes the only difference.

If 8a's headline number gets challenged on "but CTM+ ran at higher
KV utilization", the response is: prefix caching was symmetric
across cells; the v5 99%-vs-57% asymmetry came from elsewhere
(probably workload shape under sustained CTM+ pressure). A
follow-up matched-budget experiment can defend the number, but
that's an 8c-level deliverable.

### 2. Per-layer recalibration

The 4-signal evictor scoring relies on a calibration step that
computes per-layer scale factors. v5 used pooled-layer (one scale
across all layers); MRL came out at 0.221. The methodology
(`PHASE4_GPU_FINDINGS.md` §9.3a.i) requires MRL ≥ 0.3 for the
scores to be method-credible. Per-layer calibration landed
post-findings.

**Action required before 8a:** run the per-layer recalibration
script (separate ~$0.05 one-shot, not in `phase8a_remeasure.sh`)
and produce `Bench/calibration/qwen25_7b_per_layer.json`. The 8a
script reads this path via `--ctm-plus-per-layer-calibration`.

### 3. Window-pruning trigger logging

**v5 bug:** the trig signal only fed `window_pruning_pass`
(~45 invocations / 60s), while the main `evict()` ran
~3000× / 60s. So the trig signal influenced ~1.5% of eviction
decisions instead of ~100%. The post-v6 fix wired trig into the
main path.

**Verification in `phase8a_remeasure.sh`:** the existing
streaming-summary counters (`phase4_trig_score_computes`,
`phase4_trig_blend_evict_calls`, `phase4_trig_score_lookups`
from `runner_vllm_streaming.py:124+`) are read post-run. The
script normalizes to a per-60s rate and warns:

* < 500/60s → fix didn't land or starvation regression
* 1000-5000/60s → working as intended
* > 6000/60s → over-firing on prefill, inspect trig insertion

This is a soft warning, not a hard fail. Counters are
auto-emitted by the runner; no new flags needed.

## Reading the report

`PHASE8A_REPORT.md` reports three metrics for each cell:

* **`throughput_tokens_per_second`** — the primary headline.
  The bridged CTM+ cell answers "did the bridge close the -20%
  Python-dispatch tax?"
* **`swap_out/decode_token`** — the v5 algorithm quality number
  (CTM+ algorithm was -11.1% in v5 with pooled-layer calibration).
  Post-bridge + per-layer this should hold or improve.
* **Combined-stack delta** — the partner-relevant number.

### Decision matrix

| LRU TPS | CTM+ bridged TPS | Combined TPS | What to do |
|---|---|---|---|
| 100% | ≥ 95% | ≥ 90% | **Excellent.** Bridge closed the tax. Update VC brief with combined-stack number. |
| 100% | 85-95% | ~85% | Bridge closed PART of the tax. Investigate remaining gap (flusher cadence? per-layer cal MRL?) before VC update. |
| 100% | < 85% | < 80% | Bridge did NOT close the tax. The Python-dispatch overhead has a SECOND source we haven't identified. Do NOT update VC brief. Re-open the investigation; consider C/Cython port of `forward_block_attention` or move the flush off Python's hot path. |
| 100% | > LRU | > LRU | **Best case.** Algorithm AND integration both winning. Update VC brief with the strongest framing. |

## What this scaffold does NOT do

* It does NOT run the per-layer recalibration. That's upstream.
* It does NOT run MMLU 200q. Quality re-validation happens in
  Phase 8b Day 5a (route-A only) — the algorithm quality is
  separable from the integration measurement here.
* It does NOT validate on the full 4-model portfolio. Phase 8c
  does that, conditional on 8a being green.
* It does NOT touch the VC brief. **Per the user directive: no
  VC brief updates until post-bridge 8a numbers are measured.**

## Cost estimate

| Stage | Wall | $ at H100 |
|---|---|---|
| LRU baseline (60s) | 60s | ~$0.07 |
| CTM+ bridged (60s) | 60s | ~$0.07 |
| Combined (60s) | 60s | ~$0.07 |
| Engine startup × 3 + report | ~3 min overhead | ~$0.15 |
| **Total** | ~6 min | **~$0.36** |

## File anchors

| Symbol | File:line | Role |
|---|---|---|
| Per-layer calibration loader | `kv_policy/vllm_evictor.py:trig_scorer_from_per_layer_json` | Reads the calibration JSON |
| Trig signal rate logger | `runner_vllm_streaming.py:phase4_trig_signal_rate_per_60s` | Counter to wire alongside `--log-trig-signal-rate` |
| `--no-enable-prefix-caching` plumbing | `runner_vllm_streaming.py` (verify pass-through to `LLMEngine(enable_prefix_caching=False)`) | |
| Audit § matching the risks | `PHASE8_EVICTION_AUDIT.md` "Three risks for any remeasurement" | |
