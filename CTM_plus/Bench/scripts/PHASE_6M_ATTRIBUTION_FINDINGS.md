# Phase 6M — Throughput-tax attribution: PRELIMINARY findings

> **Status: PRELIMINARY — attribution only, no optimization implemented.**
> Profiled with `torch.profiler` (on this pod `nsys` CPU sampling is blocked —
> Paranoid Level 4 — and `ncu` GPU counters are blocked — `ERR_NVGPUCTRPERM`).
> Short context (the 6D driver's built-in prompt), B=128, gen=128, mml=8192,
> gpu_util=0.5. Both `captured` and `eager` int4 cells profiled. A long-context
> re-profile would sharpen the exact percentages; the **qualitative finding is
> robust across both modes**. Companion to `PHASE_6M_THROUGHPUT_ATTRIBUTION_PLAN.md`.

## TL;DR

At the Phase 6L saturation batch (B=128), the int4_protected decode-throughput
tax is the **eager KV gather/scatter + host syncs — the int4 read/write
*orchestration* — NOT the attention or dequant kernel** (which is **2–6%**). The
path is **host/dispatch/sync-bound at short context** (GPU idle **58–77%**). CUDA
graphs are **~neutral at the real long-context saturation** (the short-context
"eager is faster" was an artifact — see 6M.3 in Finding 2). **Leading recommended
path: de-eager + de-sync the int4 KV orchestration — gated on the long-context
bucket profile.**

## Operating point & method

- Qwen2.5-7B-Instruct, A100-80GB, vLLM 0.7.3 V0, gpu_util=0.5.
- B=128, gen=128, mml=8192 (the 6D driver's short built-in prompt → high
  concurrency but **not** long-context KV pressure — see Caveats).
- Tooling (existing, unmodified): `bench_phase6_d_profile_gpu.py --torch-profile-csv`
  → `analyze_phase6d_profile.py`.
- Cells: `int4_captured`, `int4_eager`, `bf16_stock` (`--bf16-eager`).
- `nsys` CPU sampling blocked (Paranoid 4); `ncu` blocked (`ERR_NVGPUCTRPERM`) →
  no within-kernel bandwidth-vs-compute split this run (not needed — see below).

## Headline numbers

| | int4 captured | int4 eager | bf16 (eager ref) |
|---|---:|---:|---:|
| `agg_tps` | 147.1 | **223.4** | 2602 |
| profiled wall | 22.6 s | 14.9 s | 1.28 s |
| GPU self-CUDA time | 9.57 s | 3.47 s | 1.04 s |
| **GPU-busy %** (CUDA ÷ wall) | 42% | **23%** | 82% |
| int4 attention kernel | ~2% | ~6% | — |

*(bf16 here is short-context-fast and eager — a kernel-mix reference, not the real
long-context baseline; Phase 6L's bf16 was 597 tok/s.)*

## Attribution (int4 GPU time, self-CUDA)

- **Gather/scatter** (`aten::index` + `index_elementwise` + `index_put`): **~28–47%**
  — the eager paged gather of int4 KV + sidecars + protected channels.
- **Host syncs**: **107,520 `.item()` + 132,608 DtoH memcpy** per profiled run →
  the GPU stalls on Python; GPU-busy only 23–42%.
- `nonzero` / `unique` / `sort` / `bitwise_and`: per-layer slot management + nibble unpack.
- **int4 attention kernel** (`fwd_kvcache_int4` / `flash_fwd`): **2–6%**.
- `graph_overhead` (memcpy/memset): ~2%.
- GEMMs (~14–47%): the model's linear layers — shared with bf16, **not** the tax.

## Two findings

**1. Bottleneck = eager KV orchestration + host syncs, not the kernel.** The
"paged gather + tail splice + pool bookkeeping" (the int4 read/write orchestration)
is implemented as 100k+ small eager aten ops with host syncs; at B=128 × 28 layers
it dominates. The fused attention + in-kernel dequant are already cheap (2–6%). The
path is host/dispatch/sync-bound, serialized by the per-layer `.item()`/`nonzero`.

**2. CUDA graphs are ~neutral at the real operating point** (graph capture is
*not* a throughput lever for protected). At **short** context, captured (147) <
eager (223) — the captured path wastes ~4.5 s on a static-shape `index_elementwise`
gather over a near-empty KV. But the **6M.3 long-context check** (mml=8192, B=128,
gen=512, `ENFORCE_EAGER=1`) shows that advantage **evaporates**: protected **eager
125.5 ≈ captured 130.4** tok/s (eager marginally *slower*) — at full context the
static gather does real work, so there's no penalty. Consequences:
- the "write-path CUDA-graph capture → ~2× throughput" projection is **not
  supported** — graphs are neither a 2× win nor a regression at saturation;
- **there is no free eager win** — the 0.22× headline holds in both modes;
- graph-safety (a "6P") is therefore **low priority** — launch/graph is not the
  saturation bottleneck.

## Recommended path (one)

**De-eager + de-sync the int4 KV orchestration:** collapse the per-layer
gather/scatter/splice/pool-bookkeeping into a few fused custom ops with **no
`.item()`/`nonzero` host syncs**. This lever (a) cuts the dominant gather cost and
(b) frees the GPU from host-stall idle. It is **NOT** "fuse the dequant" (kernel
is 2–6%), **NOT** "optimize the attention kernel," and **NOT** graph capture
(neutral at saturation, per 6M.3).

**Confidence: leading hypothesis, NOT yet confirmed at the operating point.** The
58–77% host-idle is a **short-context** measurement; at full context the GPU does
more genuine KV-read/dequant work, so the host-sync *share* is likely smaller and
the gather/dequant *share* larger. **The gating measurement before any 6N/6O
investment is the long-context bucket profile** (see Next) — the `.item()`×107k /
`nonzero`×25k syncs are real in both modes, but how much they cost *at saturation*
is unmeasured. (The interim "run eager" win is **withdrawn** — 6M.3 shows eager
does not help at long-context saturation.)

## What this revises

- "Fuse dequant into attention" (ChatGPT #1): already fused; kernel is 2–6%.
- Prior B=8 finding "~73–83% in the int4 kernel": at saturation (B=128) the
  bottleneck **shifted** to the orchestration.
- Codebase projection "graphs unlock ~2× throughput": **not supported** — graphs
  are ~neutral at saturation (neither a 2× win nor the short-context regression).

## Caveats

- **Short context** (plan §7): bf16 here is short-context-fast; the
  kernel/dequant buckets scale with context, so the exact %s shift at real
  long-context saturation. The eager-op/sync tax is context-independent and the
  100k+ `.item()`/memcpy syncs are unambiguous across both modes.
- **captured-vs-eager** torch.profiler asymmetry handled by profiling both modes.
- Absolute bucket ms are inflated by parent/child double-counting; the verdict
  uses self-CUDA % and wall-vs-GPU, which are not.
- `ncu` blocked → no within-kernel bandwidth-vs-compute. Not needed: the kernel
  is 2–6%, so its internal split is moot for the verdict.

## Gate

A GREEN attribution earns this finding + **one** recommended path. It does **NOT**
authorize the optimization — that remains the Phase 6L (b) funding decision
(accept the cost as a batch/offline density play, **or** fund the de-eager/de-sync
work for interactive serving). **No optimization implemented.**

## Raw artifacts & reproduction

```
CTM_plus/Bench/bench_out/phase6m_attribution/
  int4_captured_kernels.csv   int4_eager_kernels.csv   bf16_stock_kernels.csv
  phase6d_kernel_diff_saturation.txt
```
```bash
OUT=CTM_plus/Bench/bench_out/phase6m_attribution; mkdir -p "$OUT"
CFG="--max-model-len 8192 --batch-size 128 --max-tokens 128 --gpu-memory-utilization 0.5 --n-warmup-runs 1"
for CELL in int4_captured int4_eager; do
  python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell $CELL $CFG \
      --torch-profile-csv "$OUT/${CELL}_kernels.csv"
done
python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell bf16_stock $CFG --bf16-eager \
    --torch-profile-csv "$OUT/bf16_stock_kernels.csv"
python CTM_plus/Bench/scripts/analyze_phase6d_profile.py \
    --int4-csv "$OUT/int4_captured_kernels.csv" --bf16-csv "$OUT/bf16_stock_kernels.csv" \
    --out "$OUT/phase6d_kernel_diff_saturation.txt"
```

## Next (to firm up from PRELIMINARY → final)

1. **Long-context bucket profile — THE gating measurement.** A 1-line driver
   tweak to fill the profiled prompt to ~0.95×mml, then re-run M.1 at mml=8192.
   This is the decision input: does the orchestration (syncs + gather) still
   dominate at saturation, or does genuine KV-read/dequant work? The 6N/6O
   investment should be gated on this — short-context alone is not enough.
2. ✅ **Eager at saturation (6M.3 — DONE):** `ENFORCE_EAGER=1` Phase 6L at mml=8192
   → protected **125.5 ≈ captured 130.4**. Eager does **not** help; graphs are
   neutral. (Eager-win hypothesis withdrawn.)
3. **ncu within-kernel split**: not needed (kernel is 2–6%); blocked on this pod
   anyway (`ERR_NVGPUCTRPERM`).
