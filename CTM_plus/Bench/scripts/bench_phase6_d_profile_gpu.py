"""Phase 6D — kernel profiling driver for int4_protected vs stock bf16.

Goal: pin down WHERE the remaining 3-5x throughput gap lives. After
Phase 6C eliminated the dead bf16 backing pool, int4_protected
captured is still ~3.3x slower than stock vLLM bf16 at B=8 (174 vs
573 tok/s). 17-27% of the gap was the dead bandwidth. The remaining
73-83% is in the int4 kernel itself.

This driver produces controlled, NVTX-annotated workloads that can be
profiled with Nsight Systems (nsys) for per-kernel timing and Nsight
Compute (ncu) for per-kernel SM/memory/tensor-core utilization.

Methodology:
  * Load the LLM once (one cell per invocation: int4_captured or bf16_stock)
  * Drive a fixed deterministic prefill (so KV cache state is set)
  * Burn a small number of warmup decode steps
  * Wrap the TARGET decode step in NVTX ranges:
      - "phase6d_step"          — the entire decode step
      - "phase6d_step.layer_K"  — per-layer attention forward (informational)
  * Print sync-fenced wall time for the target step
  * Exit cleanly

Run patterns:

  # 1. Plain run (just to verify the harness):
  python bench_phase6_d_profile_gpu.py --cell int4_captured
  python bench_phase6_d_profile_gpu.py --cell bf16_stock

  # 2. nsys trace (per-kernel timeline; lightweight; good first pass):
  nsys profile -o phase6d_int4 --capture-range=nvtx --nvtx-capture=phase6d_step \
      python bench_phase6_d_profile_gpu.py --cell int4_captured
  nsys profile -o phase6d_bf16 --capture-range=nvtx --nvtx-capture=phase6d_step \
      python bench_phase6_d_profile_gpu.py --cell bf16_stock

  # Then dump kernel summary:
  nsys stats --report cuda_gpu_kern_sum --format csv phase6d_int4.nsys-rep > int4_kernels.csv
  nsys stats --report cuda_gpu_kern_sum --format csv phase6d_bf16.nsys-rep > bf16_kernels.csv

  # 3. ncu kernel-level metrics (heavier; one launch at a time):
  ncu --nvtx --nvtx-include "phase6d_step/" \
      --section ComputeWorkloadAnalysis --section MemoryWorkloadAnalysis \
      --section SchedulerStats --section Occupancy --section SpeedOfLight \
      --section LaunchStats --section InstructionStats \
      --export phase6d_int4_ncu --force-overwrite \
      python bench_phase6_d_profile_gpu.py --cell int4_captured

  ncu --nvtx --nvtx-include "phase6d_step/" \
      [same sections] --export phase6d_bf16_ncu --force-overwrite \
      python bench_phase6_d_profile_gpu.py --cell bf16_stock

Then run analyze_phase6d_profile.py to diff and report.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break


CELL_INT4_CAPTURED = "int4_captured"
CELL_INT4_EAGER    = "int4_eager"
CELL_BF16_STOCK    = "bf16_stock"

# Same prompt as bench_phase6_b4 so the workload is comparable.
PROMPT = (
    "Below is a paragraph about a small fictional town. After it, "
    "answer the question concisely.\n\n"
    "Greendell is nestled between two rivers and has a population of "
    "just over four thousand. Its main industries are pottery, honey "
    "production, and the seasonal wool trade. The annual harvest "
    "festival in early autumn draws visitors from across the region. "
    "The oldest building in town is a stone library founded in 1742.\n\n"
    "Question: What year was the oldest building in Greendell founded?\n"
    "Answer:"
)


def _load_llm(cell, model, max_model_len, gpu_memory_utilization):
    import torch
    from vllm import LLM

    if cell == CELL_BF16_STOCK:
        # Stock vLLM, bf16 KV cache, default graphs ON.
        llm = LLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype="bfloat16",
        )
        torch.cuda.synchronize()
        return llm, None, None, None

    # int4_protected cells.
    if cell == CELL_INT4_EAGER:
        os.environ["PHASE6B3_FORCE_EAGER"] = "1"
    else:
        os.environ.pop("PHASE6B3_FORCE_EAGER", None)

    import kv_policy.int4_protected   # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook,
    )

    llm = Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
    )
    torch.cuda.synchronize()

    # Discover inner model + writers for the hook.
    inner = None
    for fn in (
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ):
        try:
            inner = fn(llm)
            if inner is not None and hasattr(inner, "named_modules"):
                break
        except (AttributeError, IndexError):
            continue

    model_runner = (
        llm.llm_engine.model_executor.driver_worker.model_runner
    )

    writers, impls = [], []
    for _, sub in inner.named_modules():
        impl = getattr(sub, "impl", None)
        if isinstance(impl, Int4ProtectedAttentionImpl):
            impls.append(impl)
            w = getattr(impl, "_phase5b_paged_writer", None)
            if w is not None:
                writers.append(w)

    hook = install_int4_protected_precapture_hook(
        model_runner, writers, impls=impls,
    )
    return llm, inner, impls, hook


def _reset_writers(inner):
    if inner is None:
        return
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    for _, sub in inner.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None and getattr(w, "_allocated", False):
            w.reset_sequence("all")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cell", required=True,
                   choices=[CELL_INT4_CAPTURED, CELL_INT4_EAGER, CELL_BF16_STOCK])
    p.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len",  type=int,   default=4096)
    p.add_argument("--max-tokens",     type=int,   default=8,
                   help="Tokens to generate per pass. The TARGET (last) decode step "
                        "is what's wrapped in NVTX; earlier tokens are warmup.")
    p.add_argument("--batch-size",     type=int,   default=8,
                   help="B for the workload. Default 8 matches the Phase 6B.4 gate row.")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    p.add_argument("--n-warmup-runs",  type=int,   default=2,
                   help="Number of full generate() calls before the profiled one. "
                        "Pre-warms vLLM's compiled kernels + the CUDA graph capture pool.")
    p.add_argument("--torch-profile-csv", type=str, default=None,
                   help="If set, wraps the profiled generate() in torch.profiler and "
                        "writes a per-kernel CSV (name,total_ns,instances) to this path. "
                        "Use this when nsys is not installed on the pod.")
    p.add_argument("--torch-profile-trace", type=str, default=None,
                   help="If set (with --torch-profile-csv), also exports a Chrome "
                        "trace JSON for timeline inspection in chrome://tracing.")
    args = p.parse_args()

    import torch
    import torch.cuda.nvtx as nvtx
    from vllm import SamplingParams

    print(f"[profile cell={args.cell}] Loading {args.model}...")
    t0 = time.time()
    llm, inner, impls, hook = _load_llm(
        args.cell, args.model, args.max_model_len, args.gpu_memory_utilization,
    )
    torch.cuda.synchronize()
    print(f"[profile cell={args.cell}] Loaded in {time.time() - t0:.1f}s.")

    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    prompts = [PROMPT] * args.batch_size

    # Warmup runs (NOT profiled — these populate compiled kernels, graph
    # capture pool, etc.).
    for i in range(args.n_warmup_runs):
        _reset_writers(inner)
        torch.cuda.synchronize()
        t0 = time.time()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        print(f"[profile cell={args.cell}] warmup run {i}: "
              f"{time.time()-t0:.3f}s; out_tok={sum(len(o.outputs[0].token_ids) for o in outs)}")

    # Profiled run.
    _reset_writers(inner)
    torch.cuda.synchronize()

    if args.torch_profile_csv:
        # torch.profiler-based capture. Records every CUDA kernel launched
        # during the profiled generate() call, with name + total time.
        from torch.profiler import profile, ProfilerActivity
        with profile(
            activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
            record_shapes=False, profile_memory=False, with_stack=False,
        ) as prof:
            nvtx.range_push("phase6d_step")
            t0 = time.time()
            outs = llm.generate(prompts, sampling)
            torch.cuda.synchronize()
            elapsed = time.time() - t0
            nvtx.range_pop()

        # Write per-kernel CSV in the same format analyze_phase6d_profile.py
        # expects from nsys: header row "Time(%),Total Time,Instances,Avg,Min,Max,StdDev,Name"
        import csv as _csv
        from pathlib import Path as _Path

        def _event_device_time(e):
            """Compat shim: PyTorch renamed cuda_time_total -> device_time_total
            in newer releases. Try both, then self-* variants as a final fallback."""
            for attr in (
                "device_time_total", "cuda_time_total",
                "self_device_time_total", "self_cuda_time_total",
            ):
                v = getattr(e, attr, None)
                if v is not None:
                    return v
            return 0

        out_path = _Path(args.torch_profile_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        events = prof.key_averages()
        # Each event has name, count, device_time_total (microseconds).
        rows_out = []
        total_cuda_us = sum(_event_device_time(e) for e in events)
        for e in events:
            t_us = _event_device_time(e)
            if t_us <= 0:
                continue
            rows_out.append({
                "Time(%)":    f"{(t_us/total_cuda_us)*100:.2f}" if total_cuda_us else "0",
                "Total Time": f"{int(t_us * 1000)}",  # us -> ns
                "Instances":  str(e.count),
                "Avg":        f"{int(t_us * 1000 / max(1, e.count))}",
                "Min":        "0",
                "Max":        "0",
                "StdDev":     "0",
                "Name":       e.key,
            })
        rows_out.sort(key=lambda r: -float(r["Total Time"]))
        with out_path.open("w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=[
                "Time(%)", "Total Time", "Instances", "Avg", "Min", "Max", "StdDev", "Name"
            ])
            w.writeheader()
            for r in rows_out:
                w.writerow(r)
        print(f"[profile cell={args.cell}] wrote torch.profiler CSV: {out_path} "
              f"({len(rows_out)} kernels; total CUDA time = {total_cuda_us/1000:.1f} ms)")

        if args.torch_profile_trace:
            trace_path = _Path(args.torch_profile_trace)
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            prof.export_chrome_trace(str(trace_path))
            print(f"[profile cell={args.cell}] wrote chrome trace: {trace_path}")

        # Also print the top-20 kernels for stdout visibility. Use sort_by
        # that exists on this PyTorch version.
        try:
            print(f"\n[profile cell={args.cell}] Top kernels by CUDA time:")
            print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))
        except (TypeError, ValueError):
            try:
                print(prof.key_averages().table(sort_by="device_time_total", row_limit=20))
            except Exception as _exc:
                print(f"(table print skipped: {_exc})")
    else:
        # No-op profile mode: just NVTX-wrap, for external nsys / ncu.
        nvtx.range_push("phase6d_step")
        t0 = time.time()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        elapsed = time.time() - t0
        nvtx.range_pop()

    n_out = sum(len(o.outputs[0].token_ids) for o in outs)
    print(f"[profile cell={args.cell}] PROFILED run: {elapsed:.3f}s  out_tok={n_out}  "
          f"agg_tps={n_out / elapsed:.1f}")
    print(f"[profile cell={args.cell}] Sample output: "
          f"{outs[0].outputs[0].text[:100]!r}")

    if hook is not None:
        hook.teardown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
