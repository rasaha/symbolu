# §20.4 long-context decode-stability — diagnostic sprint runbook

Status (this session): **harness + driver landed CPU-side, tests green.**
Waiting for one GPU pod execution. Pairs with `RUNPOD_TRACK_D_E_RUNBOOK.md`
(quality eval) and reuses the §20.4 `track_e_long_context.py` needle harness.

## Why this sprint

The §20.4 GPU run found INT4 KV-cache long-context decode degrades — needle
retrieval collapsed from baseline ~100% to ~11% at 16k, and a sink-FP16 run
(`sink_size=16`) only partially recovered it (22% → 56%). Throughput (§20.1)
is a *known* blocker — the fused Marlin kernel — and is **not** the current
gating risk. The gating risk is whether INT4 long-context is salvageable at
all.

This sprint isolates the failure mode with three bounded experiments, all on
the **same 16k needle-in-haystack setup** so the only moving part per cell is
the knob under test:

| Cell group | Knob | Cells | Question |
|------------|------|-------|----------|
| 1. Sink sweep | `sink_size ∈ {0,4,16,32,64,128}` | 6 | Does protecting more attention-sink tokens at FP16 close the gap? |
| 2. K/V ablation | `quantize_k` / `quantize_v` | 2 | Is the failure in the K channel, the V channel, or both? |
| 3. INT5 | `bits=5` | 1 | Does one extra bit of headroom close the gap? |

It is **not** a benchmark expansion: no new models, no new context lengths,
no route-A, no Marlin kernel. Nine cells, one model, one context length.

## One command

Run from `CTM_plus/Bench/` inside the **venv-hf** environment (transformers
≥ 5, torch 2.5.1+cu124), on an A100 40 GB pod:

```bash
cd /workspace/symbolu/CTM_plus/Bench
bash scripts/diagnostic_sprint_long_context.sh
```

Overrides via environment variables (all optional):

```bash
MODEL=Qwen/Qwen2.5-7B-Instruct \
DTYPE=float16 DEVICE=auto \
OUTDIR=bench_out/diag_sprint \
CTX=16000 DEPTHS=0.1,0.5,0.9 SAMPLES=3 DECODE_TOKENS=64 \
  bash scripts/diagnostic_sprint_long_context.sh
```

Wall time ≈ 15–20 min on an A100 40 GB (the model reloads once per cell — nine
loads; this keeps each cell a clean process and is the simplest correct form).
Output: nine JSONs in `bench_out/diag_sprint/` —
`sink_{0,4,16,32,64,128}.json`, `k_only.json`, `v_only.json`, `int5.json`.

## What each cell runs

Every cell calls `track_e_long_context.py` with the fixed 16k needle setup:
`--context-lengths 16000 --needle-depths 0.1,0.5,0.9 --needle-samples 3
--needle-decode-tokens 64 --skip-perplexity`. Perplexity is skipped on
purpose — the §20.4 story is the **perplexity-vs-decode divergence**, and this
sprint is the decode side. Drop `--skip-perplexity` in the driver's `COMMON`
array if you also want the 16k perplexity number.

* **Cell group 1 — sink sweep.** Adds `--sink-size N` for each N. The first N
  token positions pass through at FP16; positions `[N:]` are INT4.
* **Cell group 2 — K/V ablation.** `--no-quantize-v` is K-only INT4 (V passes
  through at FP16); `--no-quantize-k` is V-only INT4 (K passes through at
  FP16). Both at the base config (`sink_size=0`) so the channel is the only
  variable. The toggle is implemented in `INT4PerChannelCache` — the disabled
  channel's tensor is returned as the FP16 source; the kvstore still
  round-trips both internally, so the **memory footprint reported for a K-only
  or V-only cell is the fully-quantized lower bound, not the true half-FP16
  footprint.** Memory is a secondary signal here; the K/V decision is read off
  needle success + stutter, not memory.
* **Cell group 3 — INT5.** `--bits 5`, base config. INT5 quantizes to a wider
  range; storage stays at the 4-bit pack layout (heap unchanged) so this cell
  measures the *quality* headroom of one extra bit, not a memory number.

## What is logged

Per needle trial (`needle_rows[]` in each JSON), the §20.4.v2 schema:

* `correct` — needle retrieval success (the answer code appears in the decoded
  window; whitespace-tolerant substring match — this is the contains-answer
  score).
* `first_stutter_position` — token index where the decode first starts to loop
  (consecutive-token repeat or an immediately repeating bigram); `-1` = no
  stutter in the decoded window.
* `repeated_token_rate` — `1 − unique/total` over the decoded tokens; catches
  AB-AB loops a consecutive-only check misses.
* `decode_entropy_mean` / `decode_entropy_min` — next-token distribution
  entropy (nats) across decode steps.
* `decode_entropy_collapsed` — heuristic flag, `True` when mean entropy <
  `0.30` nats (degenerate-loop signature; tune the threshold against observed
  runs — it is `_ENTROPY_COLLAPSE_NATS` in `track_e_long_context.py`).
* `cache_fp16_bytes` / `cache_compressed_bytes` / `cache_compression_ratio` —
  memory footprint (see the K/V-ablation caveat above).
* `decode_tokens_per_s` — secondary throughput/latency signal.

Per context length (`deltas.per_context_length[]`), aggregated for the INT4
cache: `int4_needle_accuracy`, `int4_first_stutter_earliest`,
`int4_stutter_trial_rate`, `int4_repeated_token_rate_mean`,
`int4_decode_entropy_mean`, `int4_entropy_collapse_rate`,
`int4_decode_tokens_per_s_mean`, `int4_cache_compression_ratio`. The harness
also prints an `int4 decode:` line under each cell's needle summary.

## Decision rule

Pre-decided so the sprint has a terminal state:

* **Sink sweep or INT5 closes the gap** (INT4 needle accuracy back within
  noise of baseline, no entropy collapse, no early stutter) → **INT4 is
  viable** for long context with that config; promote the winning
  `sink_size` / `bits` into the §18.3 ship config.
* **K-only / V-only isolates the failure** (one channel's ablation cell is
  healthy, the other is not) → pursue **adaptive precision** around the
  failing channel (e.g. K at FP16 / higher bits, V at INT4, or vice versa).
* **Nothing closes the gap** → **FP8 becomes the long-context default**, and
  INT4 is scoped to short/medium context only. Update the Honest Validation
  Status in the VC brief and `PHASE4_GPU_FINDINGS.md` §20.4 accordingly.

## Out of scope (do not start here)

Route-A vLLM `cache_kv` integration and the fused Marlin unpack-attend kernel
are explicitly **not** part of this sprint. They are the §20.1 throughput
track; this sprint only resolves the §20.4 long-context stability question.
