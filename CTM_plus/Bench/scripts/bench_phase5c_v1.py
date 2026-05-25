#!/usr/bin/env python3
"""bench_phase5c_v1.py — v1 performance + memory benchmark.

Compares three KV-cache backends on the SAME prompt corpus + SamplingParams:

  - bf16        — stock vLLM (kv_cache_dtype="auto")
  - fp8         — vLLM's built-in FP8 E4M3 cache (kv_cache_dtype="fp8")
  - int4_proto  — our backend (kv_cache_dtype="int4_protected", block_size=32)

All three are run SERIALIZED (one prompt per llm.generate call) for apples-to-
apples per-sequence latency comparison. int4_protected enforces batch=1 in v1,
so we serialize bf16/fp8 too to keep the comparison fair.

For each backend, reports:
  - load time (engine init)
  - KV reserve GB + # cuda blocks + max-concurrency (from cache_config)
  - per-prompt wall time + decode tok/s
  - aggregate input/output tok/s
  - per-token bytes (memory efficiency)

Final table summarizes all three side-by-side.

Memory comparison context:
  - bf16:        ~57 KB/token across all layers (D=128, H_kv=4, 28 layers, K+V)
  - fp8:         ~28 KB/token (vLLM's E4M3, halves bf16)
  - int4_proto:  ~14 KB/token paged-only + ~5 KB external sidecars ≈ ~19 KB
                 effective per-equivalent-token at same vLLM reserve

The "concurrency" metric is the real ship-story number: how many max_model_len
sequences can a single GPU hold in KV cache.

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase5c_v1.py

To skip a backend:
  --skip bf16,fp8
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


# 6 prompts at 3 length tiers x 2 each.
PROMPTS = [
    # Short ~ 20 tokens.
    "The capital of France is",
    "Tell me a one-sentence fact about water.",
    # Medium ~ 100-200 tokens.
    (
        "Below is a short paragraph about a small fictional town. "
        "After it, answer the question.\n\n"
        "Greendell is nestled between two rivers and has a population "
        "of just over four thousand. Its main industries are pottery, "
        "honey production, and the seasonal wool trade. The annual "
        "harvest festival in early autumn draws visitors from across "
        "the region. The oldest building in town is a stone library "
        "founded in 1742.\n\n"
        "Question: What year was the oldest building in Greendell founded?\n"
        "Answer:"
    ),
    (
        "Read carefully and answer.\n\n"
        "The expedition departed from Port Calva on the third of June, "
        "carrying enough supplies for ninety days. The crew of twelve "
        "included a botanist, a cartographer, two engineers, six sailors, "
        "the captain, and the ship's doctor. Their goal was to chart "
        "the unexplored coastline north of the Bramble Straits.\n\n"
        "Question: How many engineers were on the expedition?\n"
        "Answer:"
    ),
    # Long ~ 500-700 tokens.
    (
        "You are an assistant that summarizes briefly.\n\n"
        + " ".join([
            "The forest path was overgrown with thick brambles and "
            "fallen branches that had not been cleared in many years. "
            "Old stone markers along the way bore inscriptions in a "
            "language no one in the village still spoke fluently. "
            "Streams crossed the path at irregular intervals, some "
            "narrow enough to step over and others wide enough to "
            "require a careful crossing on slick rocks. Wild herbs "
            "grew thick along the southern slopes, releasing their "
            "fragrance whenever a foot brushed past. Birds called "
            "from the canopy above, their songs distinct from the "
            "ones heard in the lower valleys.",
        ] * 5)
        + "\n\nSummarize the above in one sentence.\nSummary:"
    ),
    (
        "Read the technical specification and answer briefly.\n\n"
        + " ".join([
            "The Model 7B inference accelerator features a peak "
            "throughput of three hundred tokens per second on a "
            "single device, with a memory bandwidth of nine hundred "
            "gigabytes per second. It supports mixed precision "
            "computation including bfloat16 and INT4 quantization "
            "modes. The on-chip cache is divided into ninety-six "
            "tiles each holding sixteen kilobytes of weight data. "
            "Power draw under typical workloads averages two hundred "
            "and fifty watts, with a maximum sustained draw of three "
            "hundred and twenty watts.",
        ] * 5)
        + "\n\nQuestion: What is the peak token throughput?\n"
        "Answer:"
    ),
]


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


def _gpu_kv_stats(llm) -> Dict[str, Any]:
    """Capture KV-cache geometry: num_blocks, block_size, max_concurrency."""
    try:
        cc = llm.llm_engine.cache_config
        num_gpu = getattr(cc, "num_gpu_blocks", None)
        block_size = getattr(cc, "block_size", None)
        kv_dtype = getattr(cc, "cache_dtype", None)
    except AttributeError:
        return {"num_gpu_blocks": None, "block_size": None,
                "kv_dtype": None}
    return {
        "num_gpu_blocks": num_gpu,
        "block_size":     block_size,
        "kv_dtype":       kv_dtype,
    }


def _bench(
    name: str, llm, prompts: List[str], sampling, *,
    reset_per_prompt_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Time SERIALIZED generation: one prompt per llm.generate call."""
    import torch
    times: List[float] = []
    input_toks: List[int] = []
    output_toks: List[int] = []
    texts: List[str] = []

    for i, p in enumerate(prompts, 1):
        if reset_per_prompt_fn is not None:
            reset_per_prompt_fn()
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        out = llm.generate([p], sampling)
        torch.cuda.synchronize()
        dt = time.perf_counter() - t0

        result = out[0]
        n_in  = len(result.prompt_token_ids)
        n_out = len(result.outputs[0].token_ids)
        times.append(dt)
        input_toks.append(n_in)
        output_toks.append(n_out)
        texts.append(result.outputs[0].text)
        print(f"  [{name}] prompt {i}/{len(prompts)}: "
              f"in={n_in:4d}  out={n_out:3d}  t={dt:6.3f}s  "
              f"dec_tps={n_out/dt:6.1f}")

    total_in  = sum(input_toks)
    total_out = sum(output_toks)
    total_t   = sum(times)
    return {
        "name":             name,
        "n_prompts":        len(prompts),
        "input_toks_total": total_in,
        "output_toks_total": total_out,
        "wall_s_total":     total_t,
        "decode_tps":       total_out / total_t if total_t > 0 else 0.0,
        "throughput_tps":   (total_in + total_out) / total_t if total_t > 0 else 0.0,
        "per_prompt_t":     times,
        "texts":            texts,
    }


def run_backend(
    backend: str, args, prompts: List[str], sampling,
) -> Dict[str, Any]:
    """Load + bench + tear down one backend."""
    import torch
    from vllm import LLM

    print()
    print("=" * 78)
    print(f"Backend: {backend}")
    print("=" * 78)

    reset_fn = None

    t0 = time.perf_counter()
    if backend == "bf16":
        llm = LLM(
            model=args.model,
            max_model_len=args.max_model_len,
            kv_cache_dtype="auto",
            block_size=args.block_size_default,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
    elif backend == "fp8":
        llm = LLM(
            model=args.model,
            max_model_len=args.max_model_len,
            kv_cache_dtype="fp8",
            block_size=args.block_size_default,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
    elif backend == "int4_proto":
        import kv_policy.int4_protected
        from kv_policy.int4_protected import Int4ProtectedAttentionImpl
        Int4ProtectedAttentionImpl.reset_call_stats()
        llm = LLM(
            model=args.model,
            max_model_len=args.max_model_len,
            kv_cache_dtype="int4_protected",
            block_size=32,                          # required
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )

        # int4 batch=1 v1 — reset per-prompt writer state so seq_pos
        # restarts at 0 for each new sequence.
        model = _find_inner_model(llm)

        def reset_fn():
            with torch.inference_mode():
                for _, sub in model.named_modules():
                    impl = getattr(sub, "impl", None)
                    if isinstance(impl, Int4ProtectedAttentionImpl):
                        w = getattr(impl, "_phase5b_paged_writer", None)
                        if w is not None:
                            w.reset_sequence()

    else:
        raise ValueError(f"unknown backend {backend!r}")
    load_s = time.perf_counter() - t0

    geom = _gpu_kv_stats(llm)
    print(f"  load_s={load_s:.2f}  kv_dtype={geom['kv_dtype']}  "
          f"block_size={geom['block_size']}  num_blocks={geom['num_gpu_blocks']}")

    result = _bench(backend, llm, prompts, sampling, reset_per_prompt_fn=reset_fn)
    result["load_s"]  = load_s
    result["kv_geom"] = geom

    if backend == "int4_proto":
        from kv_policy.int4_protected import Int4ProtectedAttentionImpl
        result["call_stats"] = Int4ProtectedAttentionImpl.get_call_stats()

    del llm
    gc.collect(); torch.cuda.empty_cache()
    return result


def _format_table(results: List[Dict[str, Any]], max_seqlen: int) -> str:
    cols = ["backend", "blocks", "max_concurrency", "load_s",
            "wall_s", "in_tok", "out_tok", "decode_tps", "tot_tps"]
    widths = [12, 9, 16, 8, 9, 8, 8, 11, 9]
    header = " | ".join(c.ljust(w) for c, w in zip(cols, widths))
    sep    = "-+-".join("-" * w for w in widths)
    lines  = [header, sep]
    for r in results:
        nb = r["kv_geom"]["num_gpu_blocks"]
        bs = r["kv_geom"]["block_size"]
        max_conc = (nb * bs) / max_seqlen if nb and bs else None
        vals = [
            r["name"],
            f"{nb}" if nb is not None else "?",
            f"{max_conc:5.2f}x" if max_conc is not None else "?",
            f"{r['load_s']:5.2f}",
            f"{r['wall_s_total']:6.2f}",
            f"{r['input_toks_total']:>6d}",
            f"{r['output_toks_total']:>6d}",
            f"{r['decode_tps']:8.1f}",
            f"{r['throughput_tps']:7.1f}",
        ]
        lines.append(" | ".join(v.ljust(w) for v, w in zip(vals, widths)))
    return "\n".join(lines)


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",                  default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=64)
    parser.add_argument("--block-size-default",     type=int,   default=16,
                        help="block_size for bf16/fp8 (defaults to vLLM default 16); "
                             "int4_protected always uses 32.")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--skip",                   default="",
                        help="comma-separated subset to skip (e.g. fp8,int4_proto)")
    args = parser.parse_args(argv)

    try:
        import torch
        from vllm import SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e})."); return 1

    skip = set(s.strip() for s in args.skip.split(",") if s.strip())
    backends = [b for b in ("bf16", "fp8", "int4_proto") if b not in skip]
    if not backends:
        print("FAIL: nothing to run after --skip."); return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if "int4_proto" in backends and not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}' (required for int4_proto).")
        return 1

    print("=" * 78)
    print("v1 KV-cache benchmark — BF16 / FP8 / int4_protected")
    print("=" * 78)
    print(f"  model:          {args.model}")
    print(f"  max_model_len:  {args.max_model_len}")
    print(f"  max_tokens:     {args.max_tokens}")
    print(f"  gpu_mem_util:   {args.gpu_memory_utilization}")
    print(f"  backends:       {', '.join(backends)}")
    print(f"  prompts:        {len(PROMPTS)}")
    print(f"  mode:           serialized (one prompt per llm.generate, batch=1)")
    print()

    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    results: List[Dict[str, Any]] = []
    for b in backends:
        results.append(run_backend(b, args, PROMPTS, sampling))

    print()
    print("=" * 78)
    print("Summary")
    print("=" * 78)
    print()
    print(_format_table(results, max_seqlen=args.max_model_len))

    # ----- relative-to-bf16 commentary -----
    bf16 = next((r for r in results if r["name"] == "bf16"), None)
    print()
    if bf16:
        bf_blocks = bf16["kv_geom"]["num_gpu_blocks"]
        bf_decode = bf16["decode_tps"]
        bf_total = bf16["wall_s_total"]
        print("Relative to bf16:")
        for r in results:
            if r["name"] == "bf16":
                continue
            blocks_x = (r["kv_geom"]["num_gpu_blocks"] / bf_blocks) if bf_blocks else None
            slots_x  = ((r["kv_geom"]["num_gpu_blocks"] * r["kv_geom"]["block_size"])
                        / (bf_blocks * bf16["kv_geom"]["block_size"])) if bf_blocks else None
            speed_x  = r["decode_tps"] / bf_decode if bf_decode else None
            print(f"  {r['name']:<12}: "
                  f"blocks={blocks_x:5.2f}x  "
                  f"total_slots={slots_x:5.2f}x  "
                  f"decode_tps={speed_x*100:5.1f}% of bf16")

    # ----- char-level agreement vs bf16 -----
    if bf16:
        print()
        print("Output agreement vs bf16 (per-prompt common-prefix char count):")
        for r in results:
            if r["name"] == "bf16":
                continue
            for i, (ref, this) in enumerate(zip(bf16["texts"], r["texts"])):
                cp = 0
                for a, b in zip(ref, this):
                    if a != b: break
                    cp += 1
                short = min(len(ref), len(this))
                ratio = cp / max(1, short)
                marker = " IDENTICAL" if ref == this else ""
                print(f"  {r['name']:<12} prompt {i+1}: "
                      f"{cp:4d} chars / {short:4d}  ({ratio*100:5.1f}%){marker}")

    # ----- int4 specifics -----
    int4 = next((r for r in results if r["name"] == "int4_proto"), None)
    if int4 and "call_stats" in int4:
        print()
        print("int4_protected call stats:")
        for k, v in int4["call_stats"].items():
            print(f"  {k}: {v}")

    print()
    print("Notes:")
    print("  - 'blocks' is the engine's num_gpu_blocks at gpu_memory_utilization.")
    print("  - 'max_concurrency' = (blocks * block_size) / max_model_len.")
    print("  - All runs SERIALIZED for fair per-sequence comparison (int4 is batch=1 v1).")
    print("  - bf16 / fp8 native batched throughput is much higher than these")
    print("    serialized numbers; this bench measures per-sequence latency and the")
    print("    memory/concurrency story, not multi-batch throughput.")
    print("  - int4_proto's lower decode_tps is dominated by Python overhead in the")
    print("    PagedKVWriter token loop, not kernel time — Phase 6 perf polish.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
