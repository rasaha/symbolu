# FP8 (vLLM) vs INT4 (KIVI route-B) throughput — GPU runbook

Status (this session): **harness landed CPU-side**, four-cell composition documented, JSON + Markdown deliverables waiting for one GPU pod execution. Pairs with `RUNPOD_TRACK_D_E_RUNBOOK.md` (quality eval) and `run_v10.sh` (CTM+ Phase 4 throughput); reuses the same model load, same prompts, same hardware sizing.

This runbook closes the "we are silent on throughput vs FP8 KV" gap in `PHASE4_GPU_FINDINGS.md` §19 + the VC brief.

## Why four cells, not two

vLLM's FP8 KV path (`--kv-cache-dtype fp8`) and the route-B INT4 KIVI path live in **different inference stacks** — vLLM with PagedAttention + continuous batching, HF transformers with `DynamicCache`. A naive "INT4 HF tokens/sec vs FP8 vLLM tokens/sec" headline conflates the algorithm cost with the stack cost, and the stack cost is well-known to dominate (vLLM ≈ 2-5× HF on the same model). To answer "is the route-B INT4 algorithm cost actually competitive with FP8?" we need four numbers:

| Cell | Stack | KV layer | Purpose |
|------|-------|---------|---------|
| **A** | vLLM 0.7+ | FP16 (auto)   | Stack-baseline upper-bound throughput |
| **B** | vLLM 0.7+ | **FP8**       | The competitor's real throughput |
| **C** | HF transformers | FP16 (DynamicCache) | Route-B stack-baseline |
| **D** | HF transformers | **INT4 KIVI** (route-B) | The shipping algorithm's real throughput |

The honest comparisons are:

* **`B vs A`** (FP8 vs FP16 in vLLM): the hardware tensor-core FP8 overhead. Expected near-zero per the vLLM 0.7+ release notes.
* **`D vs C`** (INT4 KIVI vs FP16 in HF): the route-B algorithm cost. The number we are currently silent on.
* **`D vs B`** (INT4-on-HF vs FP8-on-vLLM): the headline gap. Decomposes into `(D/C) × (C/A) × (A/B)`. If `D/C` is in the 0.4-0.8 range and `C/A` is in the 0.2-0.5 range, the FP8 throughput gap is dominated by the **stack** difference, which closes once a route-A `cache_kv` hook moves INT4 into vLLM — see §5 / `ROUTE_A_VLLM_CACHE_KV_PLAN.md`.

If `D/C` is dramatically below 0.5 even with the stack normalized, the algorithm-side overhead is significant and a Marlin-style fused unpack-attend kernel (PHASE4_GPU_FINDINGS §20.6 sketch) becomes the blocker.

## Pod spec

Same as `RUNPOD_TRACK_D_E_RUNBOOK.md` §1. A100 40 GB minimum. For FP8 cells, A100 or H100 — **FP8 KV on T4 / V100 is not supported by vLLM and will silently fall back to FP16** at the kernel layer; check `engine.cache_config.cache_dtype` in the engine log.

PyTorch ≥ 2.5 + cu124. vLLM 0.7.3 ships with FP8 KV support on Ampere+. Verify:

```bash
python -c "import vllm; print('vllm', vllm.__version__)"
# vLLM 0.7.3 (or 0.7.x)
```

## 1. Cells A and B — vLLM FP16 baseline + FP8

Both reuse the §13.3 `run_streaming.py` harness with the new `--kv-cache-dtype` flag. No CTM+ flags (we're measuring KV-quantization, not eviction; the §13.3 CTM+ run is a separate axis).

```bash
cd /workspace/symbolu/CTM_plus/Bench

mkdir -p bench_out/fp8_int4_throughput/{vllm_fp16,vllm_fp8,hf_fp16,hf_int4}

# Cell A — vLLM with stock FP16 KV (the upper-bound throughput).
python -m ctm_bench.scripts.run_streaming \
    --model Qwen/Qwen2.5-7B-Instruct \
    --workload chat_32k --seed 42 \
    --gpu-memory-utilization 0.26 --swap-space-gb 16 \
    --arrival-rate 6.0 --arrival-alpha 1.5 \
    --max-requests 30 --max-wall-seconds 60 \
    --max-decode-tokens 2048 \
    --prompt-length-choices "8000,16000,24000,30000" \
    --output-dir bench_out/fp8_int4_throughput/vllm_fp16 \
    2>&1 | tee bench_out/fp8_int4_throughput/vllm_fp16/run.log

# Cell B — vLLM with FP8 KV (the competitor).
python -m ctm_bench.scripts.run_streaming \
    --model Qwen/Qwen2.5-7B-Instruct \
    --workload chat_32k --seed 42 \
    --gpu-memory-utilization 0.26 --swap-space-gb 16 \
    --arrival-rate 6.0 --arrival-alpha 1.5 \
    --max-requests 30 --max-wall-seconds 60 \
    --max-decode-tokens 2048 \
    --prompt-length-choices "8000,16000,24000,30000" \
    --kv-cache-dtype fp8 \
    --output-dir bench_out/fp8_int4_throughput/vllm_fp8 \
    2>&1 | tee bench_out/fp8_int4_throughput/vllm_fp8/run.log
```

Read `tokens_per_second` out of each cell's `streaming_summary.json`. Expected: B is within ~5% of A (FP8 runs on tensor cores; overhead is dispatch only).

**Decision tree (B / A ratio):**

| B / A | Interpretation |
|---|---|
| ≥ 0.95 | FP8 is throughput-free vs FP16 in vLLM — matches the published claim. |
| 0.85-0.95 | Modest FP8 dispatch overhead. Still partner-shareable. |
| < 0.85 | Investigate: the model may not have FP8 KV kernels compiled in, or the workload is dispatch-bound. |

## 2. Cells C and D — HF baseline + INT4 KIVI

The new `track_e_throughput.py` script. Same model, same hardware, prompt lengths chosen to overlap the vLLM cells' workload (chat_32k uses 8k-30k prompts; HF can't batch them, so we measure each prefill+decode separately and pick prefill points that represent the workload).

```bash
cd /workspace/symbolu/CTM_plus/Bench

# Cell C+D — both caches at once (the script loads the model once
# and runs both baseline and INT4 cells in sequence).
python -m ctm_bench.scripts.track_e_throughput \
    --model Qwen/Qwen2.5-7B-Instruct \
    --device cuda --dtype float16 \
    --prefill-lengths 512,2048,8192,32768 \
    --decode-tokens 128 \
    --trials 5 --warmup 2 \
    --output bench_out/track_e_audit_followups/int4_throughput_hf.json \
    2>&1 | tee bench_out/fp8_int4_throughput/hf_int4/run.log
```

Wall time: ~5 min on A100 40 GB for 4 prefill lengths × 5 trials × 2 caches at decode=128. Cost: ~$0.07 spot.

The 32768 prefill length is the §20.4 long-context cell (KV memory pressure is where KV compression actually pays off). If 32k OOMs at FP16 (~14 GB weights + ~16 GB KV at 32k for Qwen2.5-7B), drop it for cell C; INT4 should still fit.

**What's in `int4_throughput_hf.json`:**

```json
{
  "model_id": "Qwen/Qwen2.5-7B-Instruct",
  "config": {
    "quant": "int4-per-channel",
    "k_group_size": 32, "v_group_size": 32, "asymmetric": true, "bits": 4,
    "sink_size": 0,
    "prefill_lengths": [512, 2048, 8192, 32768],
    "decode_tokens": 128, "trials": 5, "warmup": 2
  },
  "cells": [
    {"cache_type": "baseline", "prefill_tokens": 512, ..., "decode_tokens_per_sec": <num>},
    ...
  ],
  "aggregates": {
    "baseline@prefill=512": {"best_decode_tokens_per_sec": ..., ...},
    "int4-per-channel@prefill=512": {...},
    "int4_vs_baseline": {
      "prefill=512": {
        "int4_vs_baseline_decode_tps_ratio": 0.xx,
        "int4_decode_overhead_pct": +xx.x
      }, ...
    }
  }
}
```

**Decision tree (D / C ratio at prefill=2048, the steady-state cell):**

| D / C | Interpretation | Next step |
|---|---|---|
| ≥ 0.80 | Route-B INT4 is throughput-competitive in HF. The FP8 gap is dominated by the HF↔vLLM stack difference. **Route-A integration alone closes it.** | Land the route-A `cache_kv` hook per `ROUTE_A_VLLM_CACHE_KV_PLAN.md`. |
| 0.50-0.80 | Route-B INT4 has measurable overhead but it's in the "fixable with a kernel" range. The route-A integration would close some of the gap; a Marlin-style fused kernel closes the rest. | Both route-A and the kernel sketch in PHASE4_GPU_FINDINGS §20.6 are needed. |
| < 0.50 | The pure-PyTorch unpack-and-dequantize path is the dominant cost. **Marlin-style kernel is the actual blocker**, not route-A. | Reprioritize: kernel work first, route-A second. |

## 3. Compose the partner-shareable comparison

After all four cells, run the reader script (to be landed alongside this runbook in a follow-up commit; for now the JSON files contain everything):

```bash
# Compose the four numbers manually until the reader script lands.
echo "Cell A (vLLM FP16):   $(jq .tokens_per_second bench_out/fp8_int4_throughput/vllm_fp16/streaming_summary.json) tok/s"
echo "Cell B (vLLM FP8):    $(jq .tokens_per_second bench_out/fp8_int4_throughput/vllm_fp8/streaming_summary.json) tok/s"
echo "Cell C (HF FP16):     $(jq '.aggregates."baseline@prefill=2048".best_decode_tokens_per_sec' bench_out/track_e_audit_followups/int4_throughput_hf.json) tok/s (decode-only, prefill=2048)"
echo "Cell D (HF INT4):     $(jq '.aggregates."int4-per-channel@prefill=2048".best_decode_tokens_per_sec' bench_out/track_e_audit_followups/int4_throughput_hf.json) tok/s (decode-only, prefill=2048)"
```

Drop the four numbers into `PHASE4_GPU_FINDINGS.md` §20.1 (template populated, awaiting GPU run). Also update the "Honest Validation Status" table in `INVESTOR_PITCH.md` and `CTM_PLUS_PCAM_FSCS_VC_BRIEF.md` — likely the right row reads:

> **Route-B INT4 KIVI: D/C tokens/sec ratio vs FP16 HF baseline. vLLM FP8 KV: B/A ratio (the production competitor). Route-A integration will close the stack gap; a fused unpack-attend kernel closes the remaining algorithmic overhead.**

Honest framing options for the partner-shareable headline:
* **Strong (if D/A ≥ 0.85):** "Route-B INT4 KIVI matches the FP8 KV throughput on Qwen2.5-7B once the stack delta closes via route-A." (Predicate: D/A ≥ 0.85 AND D/C ≥ 0.85.)
* **Conditional (if 0.5 ≤ D/C < 0.85):** "Route-B INT4 KIVI has a XX% throughput cost vs FP16 in HF. Route-A integration removes the stack delta; closing the remaining gap to FP8 needs a fused kernel — sketch in PHASE4_GPU_FINDINGS §20.6."
* **Honest negative (if D/C < 0.5):** "Pure-PyTorch INT4 KIVI is XX% slower than FP16 HF — the unpack-then-attend round trip dominates. FP8's hardware-tensor-core advantage isn't closeable without a Marlin-style fused kernel."

## 4. Combined CTM+ Phase 4 × KV compression cells (optional, +$0.05)

If time permits, add two more cells to the sweep at the existing §13.3 cost:

```bash
# Cell A' — vLLM FP16 + CTM+ Phase 4 (already measured in §13.3; sanity check).
# Cell B' — vLLM FP8 + CTM+ Phase 4 (the COMBINED route-A operating point projection).
python -m ctm_bench.scripts.run_streaming \
    --model Qwen/Qwen2.5-7B-Instruct \
    --workload chat_32k --seed 42 \
    --gpu-memory-utilization 0.26 --swap-space-gb 16 \
    --arrival-rate 6.0 --arrival-alpha 1.5 \
    --max-requests 30 --max-wall-seconds 60 \
    --max-decode-tokens 2048 \
    --prompt-length-choices "8000,16000,24000,30000" \
    --kv-cache-dtype fp8 \
    --ctm-plus \
    --phase4-trig-calibration <path> \
    --phase4-cython-evictor --phase4-fast-hooks \
    --output-dir bench_out/fp8_int4_throughput/vllm_fp8_ctm \
    2>&1 | tee bench_out/fp8_int4_throughput/vllm_fp8_ctm/run.log
```

This validates the FP8 path doesn't break the CTM+ install; we then have one cell that is **strictly the kind of cell route-A would produce on launch** (vLLM + KV compression + CTM+ Phase 4 — minus the INT4-vs-FP8 algorithm-axis difference).

## 5. Cost summary

| Cells | Wall | Cost |
|---|---|---|
| A, B (vLLM FP16/FP8, 60s each) | ~3 min | ~$0.04 |
| C, D (HF FP16/INT4, ~5 min) | ~5 min | ~$0.07 |
| Optional A' (skip; measured already) | — | $0 |
| Optional B' (FP8 + CTM+) | ~1 min | ~$0.02 |
| **Total** | **~10 min** | **~$0.15** |

## 6. After the run — landing the deliverable

1. Copy `streaming_summary.json` files to `bench_out/track_e_audit_followups/` with descriptive names (`vllm_fp16_throughput.json`, `vllm_fp8_throughput.json`).
2. The HF cell already lands its JSON at `bench_out/track_e_audit_followups/int4_throughput_hf.json`.
3. Fill in `PHASE4_GPU_FINDINGS.md` §20.1 — the template has placeholder values; replace with measured.
4. Update the "Honest Validation Status" tables in `INVESTOR_PITCH.md` + `CTM_PLUS_PCAM_FSCS_VC_BRIEF.md` per the framing options above.
5. Commit and push.

## Troubleshooting

* **`vllm.config.ValidationError: kv_cache_dtype=fp8 is unsupported`:** the pod's GPU is older than Ampere or vLLM is < 0.6. Upgrade vLLM, or skip cell B and note the GPU constraint in the writeup.
* **Cell C OOMs at prefill=32768:** drop the 32k cell for FP16; INT4 should still fit. Note the asymmetry in the writeup — it IS the §20.4 long-context-pressure result.
* **`int4_throughput_hf.json` shows `decode_tokens_per_sec = 0`:** prefill or decode timing hit zero milliseconds (only possible on the dry-run fake model). On real GPU this should be 30-150 tok/s for Qwen2.5-7B.
* **Cells A and B disagree on `n_requests_completed`:** FP8 should let more requests complete in the 60s wall (more KV capacity → less swap-pressure). If A completes more, investigate — FP8 might have a kernel-init regression specific to this pod.
