#!/usr/bin/env python3
"""bench_phase6_decode_phase_profile.py — per-phase CPU+GPU timing breakdown
of the int4_protected decode read path.

After Phase 6 v2 Option D steps 1 + 2 landed, the median-of-3 throughput
bench started showing gains within noise. We're now optimizing the
read path without measurement of where time actually goes. This bench
turns on the DecodeProfiler added to phase5b_backend_install.py and
reports per-phase CPU (perf_counter) + GPU (cuda events) timings
across a complete generate() call at each B.

Reads:
  - cpu_us = Python dispatch time + implicit host syncs.
  - gpu_us = actual kernel/copy latency on device.
  - If cpu_us >> gpu_us, the phase is Python-bound (vectorize / fuse).
  - If gpu_us >> cpu_us, the phase is GPU-bound (kernel optimization).
  - If both are large, the phase is doing real work either way.

Phases instrumented:
  batched.seqids_blockids — host sync + block_ids_batched build
  batched.view_gather     — get_packed_view_batched (7 advanced-index gathers)
  batched.splice          — vectorized K partial-tail splice
  batched.bf16_backing    — get_bf16_backing_batched (stack)
  batched.kernel_prep     — protect_mask expand + V dispatch decision
  batched.kernel          — flash_attn_with_int4_kvcache call
  one.*                   — same phases for the B=1 _read_decode_packed_one path

Run on the pod:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_decode_phase_profile.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


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


def _reset_seq_states(model):
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    with torch.inference_mode():
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    w.reset_sequence("all")


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    raise RuntimeError("Could not locate inner model.")


def _bench_one_B(llm, model, B, sampling, n_runs):
    """Run one generate() call with the profiler on. Returns per-phase
    aggregates + wall time."""
    import torch
    from kv_policy import phase5b_backend_install as bi
    prompts = [PROMPT] * B

    # Aggregate across n_runs of the same B (so each phase has enough
    # samples for stable mean/total).
    bi._DECODE_PROFILER = bi.DecodeProfiler()

    wall_times = []
    n_out_total = 0
    last_text = None
    for _ in range(n_runs):
        _reset_seq_states(model)
        bi._DECODE_PROFILER.reset()    # reset between runs so summary is per-run-aggregated
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        wall_times.append(time.perf_counter() - t0)
        n_out_total += sum(len(o.outputs[0].token_ids) for o in outs)
        last_text = outs[0].outputs[0].text

    # Sync once, then materialize summary from the LAST run's profiler state.
    summary = bi._DECODE_PROFILER.summarize()
    bi._DECODE_PROFILER = None

    wall_times.sort()
    return {
        "B":           B,
        "wall_s_med":  wall_times[len(wall_times) // 2],
        "n_out_avg":   n_out_total / n_runs,
        "summary":     summary,
        "sample":      last_text[:60] if last_text else "",
    }


def _print_summary(r):
    """Print one B's per-phase breakdown."""
    B = r["B"]
    print()
    print("=" * 92)
    print(f"B={B}  median wall={r['wall_s_med']:.3f}s  avg n_out={r['n_out_avg']:.0f}  "
          f"sample={r['sample']!r}")
    print("=" * 92)
    summary = r["summary"]
    if not summary:
        print("  (no recorded phases — did the bench actually invoke the packed path?)")
        return
    rows = sorted(summary.items())
    total_cpu = sum(v["cpu_us_total"] for v in summary.values())
    total_gpu = sum(v["gpu_us_total"] for v in summary.values())
    hdr = f"  {'phase':<30} {'n':>6} {'cpu_us_mean':>12} {'gpu_us_mean':>12} {'cpu_us_total':>13} {'gpu_us_total':>13} {'cpu/gpu':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for name, v in rows:
        ratio = v["cpu_us_mean"] / max(v["gpu_us_mean"], 0.01)
        ratio_s = f"{ratio:.1f}×"
        print(f"  {name:<30} {v['n_calls']:>6} {v['cpu_us_mean']:>12.2f} "
              f"{v['gpu_us_mean']:>12.2f} {v['cpu_us_total']:>13.0f} "
              f"{v['gpu_us_total']:>13.0f} {ratio_s:>8}")
    print("  " + "-" * (len(hdr) - 2))
    print(f"  {'TOTAL':<30} {'':>6} {'':>12} {'':>12} "
          f"{total_cpu:>13.0f} {total_gpu:>13.0f}")
    print(f"  (cpu_us_total = sum of Python dispatch time over ALL calls in 1 generate)")
    print(f"  (gpu_us_total = sum of actual kernel/copy latency over ALL calls in 1 generate)")


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=64)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--batch-sizes",            default="1,2,4,8")
    parser.add_argument("--n-runs",                 type=int,   default=2,
                        help="runs per B; summary reflects the LAST run's profiler state")
    parser.add_argument("--json-out",               type=Path,  default=None,
                        help="dump per-B region summary as JSON for "
                             "analyze_phase6m7_decode_attribution.py")
    args = parser.parse_args(argv)

    try:
        import torch
        from vllm import SamplingParams
        import kv_policy.int4_protected
        from kv_policy.int4_protected import Int4ProtectedLLM
    except ImportError as e:
        print(f"FAIL: import error ({e})."); return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'."); return 1

    batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
    print("=" * 92)
    print("Phase 6 v2 Option D — decode-path phase profile")
    print("=" * 92)
    print(f"  model:         {args.model}")
    print(f"  max_tokens:    {args.max_tokens}")
    print(f"  batch_sizes:   {batch_sizes}")
    print(f"  n_runs per B:  {args.n_runs} (summary reflects last run)")
    print()

    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    print("Loading int4_protected LLM (one-time)...")
    llm = Int4ProtectedLLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    model = _find_inner_model(llm)
    print("  loaded.")

    # Warmup (no profiling).
    print("Warmup (B=1, profiling off)...")
    llm.generate([PROMPT], sampling)
    _reset_seq_states(model)

    results = []
    for B in batch_sizes:
        print(f"\nProfiling B={B} ({args.n_runs} runs)...")
        r = _bench_one_B(llm, model, B, sampling, args.n_runs)
        results.append(r)
        _print_summary(r)

    # Cross-B comparison: per-call cpu_us_mean of key phases.
    print()
    print("=" * 92)
    print("Cross-B comparison — per-call cpu_us_mean (Python dispatch time)")
    print("=" * 92)
    interesting = [
        "batched.write", "batched.seqids_blockids", "batched.view_gather",
        "batched.splice", "batched.bf16_backing", "batched.kernel_prep",
        "batched.kernel",
        "one.write", "one.view_gather", "one.splice", "one.bf16_backing",
        "one.kernel_prep", "one.kernel",
    ]
    header = "  phase                          " + "".join(f"  B={r['B']:<4}" for r in results)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for ph in interesting:
        row = f"  {ph:<30}"
        for r in results:
            v = r["summary"].get(ph)
            if v is None:
                row += "  -    "
            else:
                row += f"  {v['cpu_us_mean']:>5.1f}"
        print(row)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        # `results` records are {B, wall_s_med, n_out_avg, summary, sample} —
        # exactly the shape analyze_phase6m7_decode_attribution.load_summary reads.
        args.json_out.write_text(json.dumps(results, indent=2))
        print(f"\n[json] per-B region summary -> {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
