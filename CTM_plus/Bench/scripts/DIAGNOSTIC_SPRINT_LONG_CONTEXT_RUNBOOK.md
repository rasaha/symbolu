# §20.4 long-context decode-stability — diagnostic sprint runbook

Status: **round 1 ran 2026-05-17** — see `PHASE4_GPU_FINDINGS.md` §20.4.1.
It isolated the failure: the **K channel** is the long-context INT4 blocker;
V-INT4 is quality-neutral (96% needle at 16k, within noise of baseline). This
runbook now drives the **extended (round-2) sprint** — the same harness plus
the §20.4.1 follow-on cells: a fixed INT5 cell and a K-bit adaptive-precision
ladder. Pairs with `RUNPOD_TRACK_D_E_RUNBOOK.md`; reuses
`track_e_long_context.py`.

## Why round 2

Round 1 answered "which channel breaks?" (K). Round 2 answers **"how few bits
can K take while staying long-context-safe?"** — the path to recovering the
full 3–4× compression instead of the ~1.6× that V-INT4-only delivers. It also
re-runs INT5 properly: round 1's INT5 cell was corrupt (the 4-bit packer
mangled 5-bit values); the store now keeps >4-bit channels in int8, so INT5 is
a real measurement.

All cells use the **same 16k needle-in-haystack setup** — the only moving part
per cell is the knob under test:

| Cell group | Knob | Cells | Question |
|------------|------|-------|----------|
| 1. Sink sweep | `--sink-size ∈ {0,4,16,32,64,128}` | 6 | Does protecting attention-sink tokens at FP16 close the gap? |
| 2. K/V ablation | `--no-quantize-k` / `--no-quantize-v` | 2 | Is the failure in the K channel, the V channel, or both? |
| 3. INT5 | `--bits 5` (both channels) | 1 | Does one extra bit on both channels close the gap? |
| 4. K-bit ladder | `--k-bits {8,6,5} --v-bits 4` | 3 | How few bits can K take with V fixed at INT4? |

Twelve cells, one model, one context length. No new models, no route-A, no
Marlin kernel.

## One command

Run from `CTM_plus/Bench/` inside the **venv-hf** environment (transformers
≥ 5, torch 2.5.1+cu124), on an A100 40 GB pod:

```bash
cd /workspace/symbolu/CTM_plus/Bench
bash scripts/diagnostic_sprint_long_context.sh
```

Overrides via environment variables (all optional):

```bash
MODEL=Qwen/Qwen2.5-7B-Instruct DTYPE=float16 DEVICE=auto \
OUTDIR=bench_out/diag_sprint \
CTX=16000 DEPTHS=0.1,0.5,0.9 SAMPLES=8 DECODE_TOKENS=64 \
  bash scripts/diagnostic_sprint_long_context.sh
```

`SAMPLES=8` gives n=24 trials/cell (3 depths × 8) — enough to separate the
cells at the gap sizes seen in round 1; `SAMPLES=3` (n=9) is too noisy to
read. Wall time ≈ 25–35 min on an A100 (model reloads once per cell — twelve
loads; each cell is a clean process). Output: twelve JSONs in
`bench_out/diag_sprint/` — `sink_{0,4,16,32,64,128}.json`, `k_only.json`,
`v_only.json`, `int5.json`, `adaptive_k{8,6,5}v4.json`.

## What each cell runs

Every cell calls `track_e_long_context.py` with the fixed 16k needle setup:
`--context-lengths 16000 --needle-depths 0.1,0.5,0.9 --needle-samples 8
--needle-decode-tokens 64 --skip-perplexity`.

* **Cell group 1 — sink sweep.** `--sink-size N`: the first N token positions
  pass through at FP16, positions `[N:]` are INT4.
* **Cell group 2 — K/V ablation.** `--no-quantize-v` is K-only INT4 (V at
  FP16); `--no-quantize-k` is V-only INT4 (K at FP16). Base config,
  `sink_size=0`.
* **Cell group 3 — INT5.** `--bits 5` on both channels. Now a real
  measurement: the store stores >4-bit channels as int8 (unpacked) rather
  than corrupting them in the 4-bit nibble packer.
* **Cell group 4 — K-bit ladder.** `--k-bits {8,6,5} --v-bits 4`: K quantized
  at 8/6/5 bits, V fixed at INT4. This is the §20.4.1 adaptive-precision
  config — V stays at the quality-neutral INT4, K climbs in precision until
  it is long-context-safe. The lowest K-bits that holds needle accuracy
  within noise of baseline is the recommended ship config.

## What is logged

Per needle trial (`needle_rows[]`, schema `§20.4.v2`): `correct` (retrieval
success), `first_stutter_position`, `repeated_token_rate`,
`decode_entropy_mean`/`min`, `decode_entropy_collapsed`, `cache_*_bytes` +
`cache_compression_ratio`, `decode_tokens_per_s`. Per context length
(`deltas.per_context_length[]`): `int4_needle_accuracy`,
`int4_first_stutter_earliest`, `int4_stutter_trial_rate`,
`int4_repeated_token_rate_mean`, `int4_decode_entropy_mean`,
`int4_entropy_collapse_rate`, `int4_cache_compression_ratio`. The harness
prints an `int4 decode:` line under each cell.

## Decision rule

The ladder finds the **quality floor** for K. Memory is a separate axis: the
store has no sub-byte packer above 4 bits, so any K in {5,6,7,8} is stored as
int8 — the *actual heap* is the same regardless of K-bits; only the *quality*
differs.

Actual-heap compression, anchored on the established full-INT4 number (~3.2×,
both channels 4-bit, §18.3) and ~5 effective bits/element per channel after
group + asymmetric scale overhead:

| Config | Actual heap compression |
|---|---|
| Full INT4 (K4 / V4) — RED for long context | ~3.2× |
| V-INT4 + K-INT8 (also K-INT5/6/7 — all int8-stored) | ~2.3× |
| V-INT4 + K-FP16 (§20.4.1 fallback) | ~1.5× |
| INT5 both channels (both int8-stored) | ~1.8× |

* **A K-bit-ladder cell holds** (needle accuracy within noise of the 100%
  baseline, no early stutter) → V-INT4 + K-INT{that} is the ship config,
  **~2.3× actual heap today**. A lower quality floor does not reduce today's
  heap (K stays int8 either way) but it justifies building a sub-byte K
  packer as a follow-on — that is what would lift ~2.3× toward ~3×.
* **No ladder cell holds below K=8** → ship V-INT4 + K-FP16 (~1.5×); K-class
  INT4 compression is unsolved and the next step is a K-specific outlier
  scheme, not just more bits.
* **INT5-both holds** → uniform but weaker on memory than adaptive K8/V4
  (~1.8× vs ~2.3×), because it loses V's efficient 4-bit-packed path.

## Out of scope

Route-A vLLM `cache_kv` integration and the fused Marlin kernel are the §20.1
throughput track — not part of this sprint.
