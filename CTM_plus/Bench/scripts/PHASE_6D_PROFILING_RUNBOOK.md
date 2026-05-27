# Phase 6D — kernel profiling runbook

> **Question this answers:** "Where exactly is the remaining 3-5×
> throughput gap between int4_protected captured and stock vLLM
> bf16?" Phase 6B (CUDA Graphs) + Phase 6C (bf16 backing pool skip)
> closed the architectural gaps. The remaining gap is in the kernel
> itself. This runbook produces the data needed to pin down which
> sub-component (int4 load, dequant, protected splice, GEMM, graph
> overhead) accounts for it.
>
> **GPU time:** ~10-15 min on an A100 pod. Two `nsys` traces + two
> `ncu` per-kernel profiles + analysis.

## Prereqs

* A100 pod with the venv-vllm + forked vllm-flash-attn already
  installed (same setup as Phase 6B/6C).
* `nsys` (Nsight Systems) — ships with CUDA Toolkit.
* `ncu` (Nsight Compute) — ships with CUDA Toolkit. Optional but
  recommended for the SM-level metric breakdown.
* About 2 GB of disk space for the `.nsys-rep` and `.ncu-rep` files.

Verify with `which nsys ncu` on the pod.

## Step 1 — Sanity-check the profiling driver

```bash
source /workspace/venv-vllm/bin/activate
cd /workspace/symbolu && git pull origin claude/phase-6b1-write-preflight-fjYee

# Verify each cell runs end-to-end without profiling:
python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell int4_captured
python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell bf16_stock
```

Expected stdout (numbers will jitter ±5%):

```
[profile cell=int4_captured] warmup run 0: 1.2s
[profile cell=int4_captured] warmup run 1: 1.0s
[profile cell=int4_captured] PROFILED run: ~1.0s  out_tok=64  agg_tps=~64
[profile cell=int4_captured] Sample output: ' 1742\n...'
```

```
[profile cell=bf16_stock] PROFILED run: ~0.3s  out_tok=64  agg_tps=~200
```

If both run, you're set.

## Step 2 — Capture nsys traces (kernel-level timeline; fast)

This is the **lightweight** pass — gives per-kernel total time for
both cells. ~2-3 min per cell.

```bash
mkdir -p bench_out/phase6d_profile && cd bench_out/phase6d_profile

# int4_captured cell
nsys profile \
    -o phase6d_int4 \
    --capture-range=nvtx \
    --nvtx-capture="phase6d_step" \
    --trace=cuda,nvtx,osrt \
    --force-overwrite=true \
    python ../../CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py \
        --cell int4_captured

# bf16_stock cell
nsys profile \
    -o phase6d_bf16 \
    --capture-range=nvtx \
    --nvtx-capture="phase6d_step" \
    --trace=cuda,nvtx,osrt \
    --force-overwrite=true \
    python ../../CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py \
        --cell bf16_stock
```

`--capture-range=nvtx --nvtx-capture="phase6d_step"` tells nsys to
only profile inside the NVTX range the driver pushes. Load + warmup
runs are skipped — the trace is just the profiled `generate()` call.

## Step 3 — Extract per-kernel summaries

```bash
nsys stats --report cuda_gpu_kern_sum --format csv phase6d_int4.nsys-rep \
    > int4_kernels.csv
nsys stats --report cuda_gpu_kern_sum --format csv phase6d_bf16.nsys-rep \
    > bf16_kernels.csv
```

These are CSVs with `Time(%), Total Time, Instances, Avg, Min, Max, StdDev, Name`.

## Step 4 — Analyze + diff

```bash
cd /workspace/symbolu
python CTM_plus/Bench/scripts/analyze_phase6d_profile.py \
    --int4-csv bench_out/phase6d_profile/int4_kernels.csv \
    --bf16-csv bench_out/phase6d_profile/bf16_kernels.csv \
    --out bench_out/phase6d_profile/kernel_diff.txt
```

Output: a side-by-side comparison of kernel time grouped into the
eight candidate buckets:

```
Bucket                 |   int4 ms |   bf16 ms |  delta ms | int4 share
----------------------------------------------------------------------
main_attn_kernel       |    XXX.X  |    YYY.Y  |   +DDD.D  |    NN.N%
packed_int4_load       |     ...   |       0   |   +...    |     ...
dequant                |     ...   |       0   |   +...    |     ...
protect_splice         |     ...   |       0   |   +...    |     ...
gemm_tc                |     ...   |     ...   |    +/-... |     ...
mem_other              |     ...   |     ...   |    +/-... |     ...
graph_overhead         |     ...   |     ...   |    +/-... |     ...
other                  |     ...   |     ...   |    +/-... |     ...
```

**The bucket with the biggest positive `delta ms` IS the Phase 6D
priority target.** Paste the report and I'll tell you what to do
about it.

## Step 5 (optional, more detail) — ncu per-kernel SM/memory metrics

If the nsys analysis points at the `main_attn_kernel` bucket (most
likely), `ncu` gives the SM-level breakdown: tensor core util, memory
throughput, occupancy, stall reasons.

```bash
# Profile ONE invocation of the main attention kernel per cell.
# --launch-skip / --launch-count limits ncu to a single kernel sample
# (ncu is very slow otherwise — it re-runs the kernel multiple times
# to capture metrics).

ncu --nvtx --nvtx-include "phase6d_step/" \
    --section ComputeWorkloadAnalysis \
    --section MemoryWorkloadAnalysis \
    --section SchedulerStats \
    --section Occupancy \
    --section SpeedOfLight \
    --section LaunchStats \
    --section InstructionStats \
    --section WarpStateStats \
    --kernel-name regex:'flash|fwd_kernel|int4' \
    --launch-skip 30 --launch-count 5 \
    --export bench_out/phase6d_profile/phase6d_int4_ncu \
    --force-overwrite \
    python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py \
        --cell int4_captured

ncu --nvtx --nvtx-include "phase6d_step/" \
    --section ComputeWorkloadAnalysis --section MemoryWorkloadAnalysis \
    --section SchedulerStats --section Occupancy --section SpeedOfLight \
    --section LaunchStats --section InstructionStats --section WarpStateStats \
    --kernel-name regex:'flash|fwd_kernel' \
    --launch-skip 30 --launch-count 5 \
    --export bench_out/phase6d_profile/phase6d_bf16_ncu \
    --force-overwrite \
    python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py \
        --cell bf16_stock
```

Extract human-readable CSVs:

```bash
ncu --import bench_out/phase6d_profile/phase6d_int4_ncu.ncu-rep \
    --print-summary all \
    --csv > bench_out/phase6d_profile/int4_ncu_summary.csv
ncu --import bench_out/phase6d_profile/phase6d_bf16_ncu.ncu-rep \
    --print-summary all \
    --csv > bench_out/phase6d_profile/bf16_ncu_summary.csv
```

## Step 6 — Send me the data

Paste:
1. The output of `analyze_phase6d_profile.py` (Step 4).
2. If you ran the ncu step: `head -100` of both `int4_ncu_summary.csv` and `bf16_ncu_summary.csv`.

Or just push the whole `bench_out/phase6d_profile/` dir to the
branch (excluding the `.nsys-rep` / `.ncu-rep` files which can be
large; the CSVs and the `kernel_diff.txt` are what we need):

```bash
cd /workspace/symbolu
echo "*.nsys-rep" >> bench_out/phase6d_profile/.gitignore
echo "*.ncu-rep" >> bench_out/phase6d_profile/.gitignore
git add bench_out/phase6d_profile/
git commit -m "Phase 6D — kernel profile artifacts (Qwen-7B + A100)"
git push origin claude/phase-6b1-write-preflight-fjYee
```

I'll then write up the Phase 6D finding mapping the data to the eight
candidate bottleneck buckets and recommend the optimization target.

## What the eight buckets mean

| Bucket | What it captures | Phase 6D action if dominant |
|---|---|---|
| `main_attn_kernel` | The entire flash_attn `fwd_kvcache_int4` kernel (int4 load + dequant + protect splice + Q@K + softmax + P@V are all inside) | ncu drill-down needed to split further |
| `packed_int4_load` | Time spent in `int4_packed_load_K_block` / `int4_packed_load_V_block` (if nsys can see device functions — usually not, so this is empty unless ncu) | Optimize the HBM layout / strides |
| `dequant` | `int4_quant_dequant_K_block_inplace` (older Phase 2.5 path; should be 0 in our packed-mode cells) | Confirms we're on the right path |
| `protect_splice` | Python-side splice work in `_splice_k_partial_tail_batched_unconditional` + the quantization helpers | Optimize the splice op chain |
| `gemm_tc` | Tensor-core GEMM kernels outside the main attn (model linear layers) | Should net out — common to both |
| `mem_other` | scatters / gathers in our writer (Phase 6B/6C residue) | If still significant, more dead bandwidth |
| `kv_write` | `reshape_and_cache_flash` and similar — kv_cache write | Should be tiny |
| `graph_overhead` | memcpy / memset / NCCL — graph machinery | If bigger than ~5% of total, dig in |
