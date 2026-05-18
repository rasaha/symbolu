"""§20.1 cells A/B — clean vLLM decode-throughput measurement.

Run once with ``--kv-cache-dtype auto`` (cell A = FP16 baseline) and
once with ``--kv-cache-dtype fp8`` (cell B = FP8 KV). The output JSON
carries a ``tokens_per_second`` field at the path
``compose_throughput_comparison.py`` reads, so the composer works
unchanged afterward.

Why this exists instead of ``run_streaming.py`` for cells A/B
--------------------------------------------------------------

``run_streaming.py`` is the §13.3 harness — it measures **swap events
under KV pressure** on the ``chat_32k`` workload. That workload has
two properties fatal to a throughput comparison:

* It is **prefill-bound**: 8k-30k-token prompts mean a 60s budget is
  ~45s prefill, ~15s generation.
* Its synthetic filler prompts trigger **early EOS** — the model sees
  garbage and stops after ~3 tokens, so ``decode_tokens`` collapses to
  single digits and ``decode_tokens / wall`` is noise.

This script fixes both: modest fixed-length prompts (prefill is cheap)
and ``ignore_eos=True`` so every request generates exactly
``--decode-tokens`` tokens — the decode path is actually exercised.
The headline ``tokens_per_second`` is then a real aggregate decode
throughput, and the FP8/FP16 ratio is the partner-relevant signal.

CLI
---

  python -m ctm_bench.scripts.vllm_throughput_cell \\
      --kv-cache-dtype auto \\
      --output bench_out/fp8_int4_throughput/vllm_fp16/streaming_summary.json

  python -m ctm_bench.scripts.vllm_throughput_cell \\
      --kv-cache-dtype fp8 \\
      --output bench_out/fp8_int4_throughput/vllm_fp8/streaming_summary.json

Requires vLLM (the venv-vllm environment; see
``FP8_INT4_THROUGHPUT_RUNBOOK.md``). vLLM 0.7.3 is the validated
version — its ``AsyncEngineArgs`` / tokenizer API match the repo's
expectations, and it supports ``kv_cache_dtype='fp8'`` on Ampere+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Sequence


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="vllm_throughput_cell",
        description=(
            "Clean vLLM decode-throughput measurement for §20.1 "
            "cells A (FP16) / B (FP8). ignore_eos=True forces a full "
            "decode so the number is real."
        ),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--kv-cache-dtype", default="auto",
        choices=["auto", "fp8", "fp8_e4m3", "fp8_e5m2"],
        help="'auto' = FP16 (cell A); 'fp8' = FP8 KV (cell B).",
    )
    parser.add_argument(
        "--output", required=True,
        help=(
            "Output JSON path. Use "
            "bench_out/fp8_int4_throughput/vllm_fp16/streaming_summary.json "
            "for cell A and .../vllm_fp8/... for cell B so the "
            "composer's default paths pick them up."
        ),
    )
    parser.add_argument(
        "--num-prompts", type=int, default=32,
        help="Concurrent prompts in the timed batch. 32 is a stable "
             "aggregate; raise for a bigger batch.",
    )
    parser.add_argument(
        "--prompt-tokens", type=int, default=1024,
        help="Prompt length in tokens. Kept modest so prefill is "
             "cheap and decode dominates the timing.",
    )
    parser.add_argument(
        "--decode-tokens", type=int, default=256,
        help="Tokens generated per prompt (forced via ignore_eos).",
    )
    parser.add_argument(
        "--gpu-memory-utilization", type=float, default=0.5,
        help="vLLM GPU memory fraction. 0.5 fits Qwen2.5-7B (14 GB "
             "weights) on a 40 GB card; raise on 80 GB if you want a "
             "bigger KV cache.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    # vLLM import is deferred so `--help` works on a box without vLLM.
    try:
        from vllm import LLM, SamplingParams  # type: ignore
    except ImportError:
        raise SystemExit(
            "vLLM not installed. This script runs in the venv-vllm "
            "environment — `pip install 'vllm==0.7.3'`. See "
            "FP8_INT4_THROUGHPUT_RUNBOOK.md."
        )

    print(
        f"Loading {args.model} (kv_cache_dtype={args.kv_cache_dtype}, "
        f"gpu_mem={args.gpu_memory_utilization})...",
        flush=True,
    )
    llm = LLM(
        model=args.model,
        kv_cache_dtype=args.kv_cache_dtype,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.prompt_tokens + args.decode_tokens + 128,
        enforce_eager=True,
        seed=args.seed,
    )

    # Build a prompt of exactly --prompt-tokens tokens by repeating a
    # neutral passage and truncating. Repeated text is fine for a
    # throughput measurement — we time forward passes, not quality.
    tok = llm.get_tokenizer()
    text = (
        "The history of artificial intelligence began in antiquity "
        "with myths and stories of artificial beings. "
    )
    while len(tok(text)["input_ids"]) < args.prompt_tokens:
        text += text
    prompt_ids = tok(text)["input_ids"][: args.prompt_tokens]
    prompt = tok.decode(prompt_ids)
    prompts = [prompt] * args.num_prompts

    # ignore_eos=True is the critical knob — without it, the model
    # EOS-es out after a few tokens and the decode path is never
    # measured. With it, every request generates exactly
    # --decode-tokens tokens.
    sp = SamplingParams(
        temperature=0.0,
        max_tokens=args.decode_tokens,
        ignore_eos=True,
        seed=args.seed,
    )

    # Warmup (untimed) — loads CUDA kernels, warms the scheduler.
    print("Warmup...", flush=True)
    llm.generate(prompts[:2], sp, use_tqdm=False)

    # Timed batch.
    print(f"Timed run: {args.num_prompts} prompts x {args.decode_tokens} "
          f"decode tokens...", flush=True)
    t0 = time.perf_counter()
    outs = llm.generate(prompts, sp, use_tqdm=False)
    elapsed = time.perf_counter() - t0

    n_decode = sum(len(o.outputs[0].token_ids) for o in outs)
    tps = n_decode / elapsed if elapsed > 0 else 0.0

    result = {
        "cell": "vllm",
        "model_id": args.model,
        "kv_cache_dtype": args.kv_cache_dtype,
        "num_prompts": args.num_prompts,
        "prompt_tokens": args.prompt_tokens,
        "decode_tokens_per_prompt": args.decode_tokens,
        "n_decode_tokens": n_decode,
        "wall_clock_seconds": elapsed,
        # `tokens_per_second` is the field compose_throughput_comparison
        # reads for cells A/B — keep the name exactly this.
        "tokens_per_second": tps,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print()
    print(json.dumps(result, indent=2))
    print()
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
