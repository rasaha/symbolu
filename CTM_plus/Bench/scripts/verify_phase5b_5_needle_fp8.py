#!/usr/bin/env python3
"""verify_phase5b_5_needle_fp8.py — direct fp8 needle measurement.

VC-brief audit Tier A R1: replaces the brief's inferred
"fp8 ~12% needle" framing with a direct measurement on the
same 15-prompt needle test that int4_protected passes 15/15 on.

Mirrors the prompt-building logic of `verify_phase5b_5_needle.py`
(same FILLER_SENTENCES, same _build_prompt, same length buckets,
same needle-code shape). The only delta is the backend: this script
runs vLLM with ``kv_cache_dtype="fp8"`` and reports the fp8
retrieval rate.

Gate: this script does NOT impose a pass/fail threshold. The
result IS the measurement — partner-facing claim becomes "fp8
needle: X/15 on Qwen-7B at our test config" without speculation
about what value of X represents passing.

Usage:

    python Bench/scripts/verify_phase5b_5_needle_fp8.py \\
        --model Qwen/Qwen2.5-7B-Instruct \\
        --gpu-memory-utilization 0.5 --max-model-len 4096 \\
        --num-needles 5 --lengths 200,600,1200 \\
        --seed 42 \\
        --output-dir bench_out/VC_BRIEF_TIER_A/r1_fp8_needle_qwen7b
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import string
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# Reuse the canonical filler corpus + prompt builders from the
# sibling script so the fp8 measurement is apples-to-apples with
# the int4_protected needle pass rate.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from verify_phase5b_5_needle import (
    FILLER_SENTENCES,           # noqa: F401  -- imported for parity / docs
    _make_needle,
    _build_prompt,
)


def _gen_fp8(prompts: List[str], args) -> List[str]:
    import torch
    from vllm import LLM, SamplingParams
    print("[1/1] vLLM kv_cache_dtype=fp8 ...")
    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        kv_cache_dtype="fp8",
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    outs = llm.generate(prompts, sampling)
    texts = [o.outputs[0].text for o in outs]
    del llm
    gc.collect()
    torch.cuda.empty_cache()
    return texts


def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--block-size", type=int, default=16,
                        help="vLLM block size; fp8 path uses 16 by default.")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--num-needles", type=int, default=5,
                        help="needle prompts per length bucket")
    parser.add_argument("--lengths", default="200,600,1200",
                        help="comma-separated filler-token-budget values")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default=None,
                        help="if set, writes summary.json + per_trial.json here")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    if not lengths:
        print("FAIL: --lengths must list at least one value")
        return 1

    # Build the trial matrix: num_needles codes per length bucket.
    trials: List[Dict] = []
    for length in lengths:
        for _ in range(args.num_needles):
            needle = _make_needle(rng)
            prompt = _build_prompt(needle, length, rng)
            trials.append({"length": length, "needle": needle, "prompt": prompt})

    prompts = [t["prompt"] for t in trials]

    try:
        texts = _gen_fp8(prompts, args)
    except Exception as exc:
        print(f"FAIL: fp8 generation raised: {exc!r}")
        return 1

    # Per-trial: needle hit = the code appears in the model's answer.
    per_trial: List[Dict] = []
    for t, text in zip(trials, texts):
        hit = t["needle"] in text
        per_trial.append({
            "length": t["length"],
            "needle": t["needle"],
            "answer_text": text.strip(),
            "hit": hit,
        })

    total = len(per_trial)
    hits = sum(1 for r in per_trial if r["hit"])
    per_bucket: Dict[int, Tuple[int, int]] = {}
    for r in per_trial:
        b = r["length"]
        hits_b, total_b = per_bucket.get(b, (0, 0))
        per_bucket[b] = (hits_b + (1 if r["hit"] else 0), total_b + 1)

    print()
    print(f"==== fp8 needle measurement, model={args.model} ====")
    print(f"  overall: {hits}/{total} ({100.0 * hits / total:.1f}%)")
    for b in sorted(per_bucket):
        h, n = per_bucket[b]
        print(f"  {b}-filler-tokens bucket: {h}/{n}")
    print()
    print("(No pass/fail threshold imposed. The number IS the result.)")

    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        summary = {
            "model": args.model,
            "kv_cache_dtype": "fp8",
            "seed": args.seed,
            "lengths": lengths,
            "num_needles_per_bucket": args.num_needles,
            "total_trials": total,
            "hits": hits,
            "hit_rate": hits / total if total else 0.0,
            "per_bucket": {
                str(b): {"hits": h, "total": n}
                for b, (h, n) in per_bucket.items()
            },
            "passes": hits,  # mirrors verify_phase5b_5_needle.py field name
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        (out / "per_trial.json").write_text(json.dumps(per_trial, indent=2))
        print(f"Wrote {out}/summary.json + {out}/per_trial.json")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
