# Phase 6M — Throughput-tax attribution plan

> **Status: PLAN (no implementation).** Scope = *rerun the existing Phase 6D
> profiling at the Phase 6L saturation operating point, classify the tax, and
> recommend ONE optimization path.* The optimization itself is a separate,
> later, **funded** phase, gated on these findings. This plan changes no kernel,
> layout, scheduler, or quantization code.

## 0. Why this exists

Phase 6L demonstrated the capacity win (net **1.83× seq/GB**, 2.02× raw live)
but quantified a throughput cost at saturation (mml=8K, B=128, gen=512):

| | bf16 | protected | ratio |
|---|---:|---:|---:|
| aggregate tok/s | 597.3 | 130.4 | **0.22×** |
| per-user tok/s (agg ÷ live) | ~10.3 | ~1.1 | **~0.11× (≈9× slower/user)** |

Decomposing: each protected decode **step** is ~9× slower than bf16's while
doing ~2× the sequences → the int4 decode path is **~4–5× slower per
sequence-token**, and `0.22× aggregate = ~2× concurrency ÷ ~9× step-time`.

We do **not** yet know *which* part of the int4 decode path causes this at the
saturated operating point. **Attribution before optimization.**

## 1. Scope

**In scope**
- Re-run the **existing** Phase 6D profiling tooling at the Phase 6L
  operating point (high B, long context, long gen).
- Classify the int4-vs-bf16 gap into the existing 8 buckets.
- Output: bandwidth-vs-compute verdict + the dominant tax bucket + **one**
  recommended optimization path (A–E).

**Out of scope (explicitly)**
- Any kernel / sidecar-layout / protected-path / scheduler change.
- A new profiling harness (the 6D tooling already exists — reuse it).
- int8-V, `n_protect` reduction, predicted-/symmetric- xmin — all **RED** for
  Qwen-7B (Phase 6G.2, track CLOSED). Not revisited here.

## 2. What already exists (reuse, do not rebuild)

| Tool | Role |
|---|---|
| `bench_phase6_d_profile_gpu.py` | Loads one cell (`int4_captured` / `int4_eager` / `bf16_stock`), warms up, NVTX-wraps the profiled `generate()`. Takes `--batch-size`, `--max-model-len`, `--max-tokens`, `--gpu-memory-utilization`, `--n-warmup-runs`. Emits for **nsys**, **ncu**, or a built-in **torch.profiler** CSV fallback (`--torch-profile-csv`, same schema nsys produces). |
| `analyze_phase6d_profile.py` | Reads two kernel CSVs (int4 vs bf16) and maps every kernel to one of 8 buckets, then reports the **biggest absolute int4-vs-bf16 delta** bucket = the priority target. |

**The 8 buckets** (from `analyze_phase6d_profile.py::BUCKET_MAP`):
`main_attn_kernel` (the fused int4 flash-attn kernel — opaque to nsys),
`packed_int4_load`, `dequant`, `protect_splice`, `gemm_tc`, `kv_write`,
`mem_other` (Python-side splice/sidecar prep), `graph_overhead`, `model_other`,
`sampling`, `other`.

**Prior 6D result (the baseline to beat):** at **B=8, mml=4096, gen=8**, the gap
was ~3.3× and **~73–83% lived inside the fused int4 kernel** (`main_attn_kernel`)
after Phase 6C removed the dead bf16-backing bandwidth. Phase 6M asks: **does
that kernel-dominated attribution still hold at saturation, or do
`graph_overhead` / scheduler churn / long-context KV reads grow?**

## 3. The operating-point gap to close

| param | prior 6D run | Phase 6L saturation | 6M target |
|---|---:|---:|---:|
| batch `B` | 8 | 128 | **128** |
| `max_model_len` | 4096 | 8192 | **8192** |
| generated tokens | 8 | 512 | **512** |
| `gpu_memory_utilization` | 0.5 | 0.5 | **0.5** |
| context fill | short prompt (~100 tok) | ~0.95×mml | **see §7 caveat** |

## 4. Procedure

**M.1 — bucket pass (both cells), nsys (or torch.profiler fallback).**
Profile `int4_captured` and `bf16_stock` at the 6M target config; dump the
`cuda_gpu_kern_sum` CSVs; run the analyzer. Output = the bucket diff.

**M.2 — graph-capture isolation.** Add an `int4_eager` cell (driver already
supports it via `PHASE6B3_FORCE_EAGER`). `int4_eager` − `int4_captured`
isolates how much of the tax is launch/graph overhead vs in-kernel work.

**M.3 — (conditional) ncu deep-dive.** *Only if* `main_attn_kernel` dominates
the M.1 diff: run ncu on the fused kernel with `SpeedOfLight` +
`MemoryWorkloadAnalysis` + `ComputeWorkloadAnalysis` (nsys cannot split the
fused kernel; ncu can). This yields **bandwidth-bound vs compute-bound** and the
internal split (int4-load vs dequant vs splice vs GEMM).

**M.4 — size the non-kernel gap.** Compare the profiled-step **wall time** (the
driver prints `agg_tps`/elapsed) to the **Σ kernel time** from the CSV. A large
residual = scheduler/preemption/launch gap, not kernel — points at path E.

## 5. Decision tree (bucket → recommended path)

| Dominant signal in the diff | Recommended path |
|---|---|
| `main_attn_kernel` + ncu **memory-bound** | **A** — fused-kernel internals: int4 KV-read / dequant bandwidth (vectorized loads, load scale/xmin once per tile, shared-mem reuse) |
| `main_attn_kernel` + ncu **compute-bound** | **A** — dequant / splice compute (warp-level dequant, reduce divergence) |
| `mem_other` (Python-side sidecar/splice prep) | **B** — sidecar layout / coalescing (cheapest if it's outside the kernel) |
| `protect_splice` | **C** — inline protected-K into the KV layout (Option D, reframed as throughput, not memory) |
| `graph_overhead`, or `int4_eager ≈ int4_captured` | **D** — CUDA-graph capture of the decode path (aligns with the existing write-path-capture bet: VC brief projects ~2× aggregate) |
| Wall-time ≫ Σ kernel time (M.4 residual) | **E** — scheduler / serving-mode split (route latency-sensitive traffic; the Phase 6L (b) "batch/offline vs interactive" lever — **no kernel work**) |

The plan stays **agnostic**: the measured buckets pick the path, not a prior.
Note the bottleneck likely **shifts with operating point** (launch-bound at
low-B → graph; bandwidth/compute-bound at saturation → kernel), which is exactly
why we re-profile at B=128 rather than reuse the B=8 result.

## 6. Deliverables

1. `bench_out/phase6m_attribution/phase6d_kernel_diff_saturation.txt` — the
   analyzer's bucket diff at the 6M config.
2. `PHASE_6M_ATTRIBUTION_FINDINGS.md` — one page: bandwidth-vs-compute verdict,
   the dominant bucket with its measured share, and the **single** recommended
   path (A–E) with its evidence. **No optimization implemented.**

## 7. Known limitations / decision points (read before running)

1. **Short hardcoded prompt (the one real gap).** The 6D driver fills only
   ~100 tokens of context, so at B=128 it reproduces **high concurrency** but
   **not long-context KV pressure**. The per-token int4 KV-read/dequant tax
   *scales with context length*, so a short-context profile **under-attributes**
   `packed_int4_load` / `dequant` relative to Phase 6L. Plan:
   - **M.1 as-is** is still valid for the *fixed* per-token overheads
     (`graph_overhead`, `protect_splice`, dequant **compute**, Python-side
     `mem_other`) at high B — run it first, it's free.
   - If M.1/M.3 implicate the **context-scaling** KV-read path, a **one-line**
     driver tweak (fill the prompt to ~0.95×mml, as `phase6k14` does) is the
     minimal follow-up — **flagged here, not done in this plan.**
2. **nsys can't split the fused kernel.** `main_attn_kernel` is one opaque
   kernel under nsys; use ncu (M.3) for the internal split + bandwidth/compute.
3. **Scheduler/preemption is not kernel time.** It shows as a wall-clock gap
   (M.4), not in `cuda_gpu_kern_sum`. Size it by wall − Σ kernel.
4. **torch.profiler is the no-nsys fallback.** If nsys isn't on the pod, use
   `--torch-profile-csv` (driver writes the same CSV schema the analyzer reads).

## 8. Cost & gate

- **~1 pod session.** nsys + analyze: minutes per cell. ncu (M.3, only if
  triggered): heavier — one kernel, one launch.
- **Gate:** a GREEN attribution earns a recorded finding + **one** recommended
  path. It does **not** authorize the optimization — that is the Phase 6L (b)
  funding decision (accept the cost as a batch/offline density play, **or** fund
  the recommended path for interactive serving).

## 9. Commands (copy-paste; pod, venv active)

```bash
cd /workspace/symbolu
source /workspace/venv-vllm/bin/activate
OUT=CTM_plus/Bench/bench_out/phase6m_attribution; mkdir -p "$OUT"
CFG="--max-model-len 8192 --batch-size 128 --max-tokens 512 --gpu-memory-utilization 0.5"

# ---- M.1: nsys bucket pass (preferred) ----
for CELL in int4_captured bf16_stock; do
  nsys profile -o "$OUT/phase6d_${CELL}" --capture-range=nvtx --nvtx-capture=phase6d_step \
      python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell $CELL $CFG
  nsys stats --report cuda_gpu_kern_sum --format csv \
      "$OUT/phase6d_${CELL}.nsys-rep" > "$OUT/${CELL}_kernels.csv"
done
python CTM_plus/Bench/scripts/analyze_phase6d_profile.py \
    --int4-csv "$OUT/int4_captured_kernels.csv" \
    --bf16-csv "$OUT/bf16_stock_kernels.csv" \
    --out "$OUT/phase6d_kernel_diff_saturation.txt"
cat "$OUT/phase6d_kernel_diff_saturation.txt"

# ---- M.1 (fallback if nsys absent): torch.profiler ----
# python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell int4_captured $CFG \
#     --torch-profile-csv "$OUT/int4_captured_kernels.csv"
# python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell bf16_stock $CFG --bf16-eager \
#     --torch-profile-csv "$OUT/bf16_stock_kernels.csv"
# (then the same analyze_phase6d_profile.py call)

# ---- M.2: graph-capture isolation (eager vs captured) ----
# python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell int4_eager $CFG \
#     --torch-profile-csv "$OUT/int4_eager_kernels.csv"

# ---- M.3: ncu deep-dive (ONLY if main_attn_kernel dominates M.1) ----
# ncu --nvtx --nvtx-include "phase6d_step/" \
#     --section SpeedOfLight --section MemoryWorkloadAnalysis \
#     --section ComputeWorkloadAnalysis --section Occupancy --section LaunchStats \
#     --export "$OUT/phase6d_int4_ncu" --force-overwrite \
#     python CTM_plus/Bench/scripts/bench_phase6_d_profile_gpu.py --cell int4_captured $CFG
```
