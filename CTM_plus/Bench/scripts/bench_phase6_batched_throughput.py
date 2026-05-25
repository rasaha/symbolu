#!/usr/bin/env python3
"""bench_phase6_batched_throughput.py — measure Option A's batched-kernel gain.

Phase 6 v2 Option A (commit 446f7f4) replaces per-seq kernel calls in
multi-decode with a SINGLE batched kernel call across all sequences in
the forward. This bench measures the actual throughput improvement
across B = {1, 2, 4, 8} batch sizes against the same int4_protected
backend.

Methodology:
  - One Int4ProtectedLLM instance reused across all B runs (avoid
    model-load overhead in measurements).
  - For each B, submit B identical prompts via llm.generate([p]*B).
  - Measure wall time + per-prompt latency + aggregate output tok/s.
  - Compare to the serialized baseline (run each prompt independently
    with B=1).

Reports:
  - B / wall_s_total / per_prompt_s / total_output_tok / agg_tok/s
  - Speedup vs B=1 baseline:
      * latency speedup: should be ~constant (B=1 latency unchanged).
      * throughput speedup: should approach B× as B grows.

This is the bench that validates Option A's design hypothesis: "B
sequences in 1 batched kernel call ≈ B× the throughput of B sequential
calls". With CUDA-launch overhead amortized, decode_tps should rise
nearly linearly with B until B saturates the kernel.

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_batched_throughput.py
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


# A modest-length prompt that exercises both prefill and decode overhead.
# Same prompt repeated B times — identical workload per seq, easy to
# interpret the timing.
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


def _reset_all_seq_states(model):
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    with torch.inference_mode():
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    w.reset_sequence("all")


def _bench_one_B(llm, model, B: int, sampling, n_runs: int = 3) -> Dict[str, Any]:
    """Run [PROMPT] * B through one llm.generate, time it."""
    import torch
    prompts = [PROMPT] * B
    times = []
    out_lens = []
    last_text = None
    for _ in range(n_runs):
        _reset_all_seq_states(model)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs)
        out_lens.append(n_out)
        last_text = outs[0].outputs[0].text
    # Median.
    times.sort()
    median_t = times[len(times) // 2]
    median_out = out_lens[len(out_lens) // 2]
    return {
        "B":               B,
        "wall_s":          median_t,
        "n_output_tokens": median_out,
        "per_prompt_s":    median_t,                        # serial run-equivalent
        "agg_tps":         median_out / median_t if median_t > 0 else 0.0,
        "sample_output":   last_text[:80],
    }


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--batch-sizes",            default="1,2,4,8",
                        help="comma-separated B values")
    parser.add_argument("--n-runs",                 type=int,   default=3,
                        help="runs per B (median reported)")
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
    print("=" * 78)
    print("Phase 6 v2 Option A — batched throughput")
    print("=" * 78)
    print(f"  model:         {args.model}")
    print(f"  max_tokens:    {args.max_tokens}")
    print(f"  batch_sizes:   {batch_sizes}")
    print(f"  n_runs per B:  {args.n_runs} (median)")
    print(f"  prompt length: ~{len(PROMPT)} chars")
    print()

    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    print("Loading int4_protected LLM (one-time)...")
    llm = Int4ProtectedLLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    model = _find_inner_model(llm)
    print(f"  loaded.")
    print()

    # Warm up.
    print("Warmup (B=1 single run)...")
    llm.generate([PROMPT], sampling)
    _reset_all_seq_states(model)
    print()

    results: List[Dict[str, Any]] = []
    for B in batch_sizes:
        print(f"Running B={B} (×{args.n_runs} runs)...")
        r = _bench_one_B(llm, model, B, sampling, n_runs=args.n_runs)
        print(f"  B={B}: wall {r['wall_s']:.3f}s   "
              f"n_out_total={r['n_output_tokens']}   "
              f"agg_tps={r['agg_tps']:.1f}")
        results.append(r)

    print()
    print("=" * 78)
    print("Results — int4_protected batched throughput")
    print("=" * 78)
    print(f"  {'B':>3} | {'wall_s':>8} | {'out_tok':>8} | {'tot_tps':>9} | "
          f"{'per_seq_s':>10} | {'per_seq_tps':>12} | {'tps_speedup':>12}")
    print("  " + "-" * 78)
    base = results[0]
    base_tps = base["agg_tps"]
    base_per_seq_tps = base["agg_tps"] / base["B"]
    for r in results:
        per_seq_s = r["wall_s"]            # serialized would be B × wall_s_B1
        per_seq_tps = r["agg_tps"] / r["B"]
        # Speedup vs B=1: how does aggregate throughput scale?
        speedup = r["agg_tps"] / base_tps if base_tps > 0 else 0.0
        print(f"  {r['B']:>3} | {r['wall_s']:>8.3f} | {r['n_output_tokens']:>8d} | "
              f"{r['agg_tps']:>9.1f} | {per_seq_s:>10.3f} | "
              f"{per_seq_tps:>12.1f} | {speedup:>11.2f}×")

    # Sample output check (sanity).
    print()
    print(f"Sample output (B={results[0]['B']}, prompt 0): "
          f"{results[0]['sample_output']!r}")

    print()
    print("Reading:")
    print("  - agg_tps   = total output tok/s in the batched call (all B seqs).")
    print("  - per_seq_tps = agg_tps / B (per-sequence decode rate).")
    print("  - tps_speedup = agg_tps(B) / agg_tps(1).")
    print("  - Ideal Option A scales agg_tps linearly with B until kernel")
    print("    saturates. per_seq_tps stays constant (or grows) if so.")
    print("  - If per_seq_tps DROPS with B, kernel/launch overhead per layer")
    print("    isn't amortizing — could mean the Python loop for splice is")
    print("    becoming the bottleneck, or the bf16-backing stack is too slow.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
