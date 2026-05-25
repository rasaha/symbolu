#!/usr/bin/env python3
"""verify_phase5b_4c_3_char_diff.py — stock-vs-int4 character diff.

Runs a small prompt corpus through BOTH stock vLLM (kv_cache_dtype=auto)
and our int4_protected backend, then reports per-prompt and aggregate
character-level similarity metrics.

Why: the 5B.4c.3 E2E smoke matched stock char-for-char on a single
needle prompt. This script generalizes to a diverse corpus to give a
robust ship-quality signal:

  - factual_recall:  short Q&A with embedded needle
  - completion:      finish a known phrase
  - arithmetic:      small math fact
  - code:            language-specific syntax (Python)
  - creative:        open-ended generation (high-variance baseline)

Per-prompt metrics:
  - common_prefix_chars: how many leading chars match
  - common_prefix_ratio: as fraction of shorter output
  - edit_distance: full Levenshtein distance
  - edit_ratio: 1 - dist / max(len_a, len_b)
  - first_divergence: char index + ±20 char context window

Aggregate:
  - mean / min common_prefix_ratio across prompts
  - mean / min edit_ratio across prompts
  - count of prompts where int4 was character-identical to stock

Gates (informational; not hard pass/fail):
  - mean common_prefix_ratio >= 0.50  (the int4 output mostly matches
    the stock output's prefix on average across diverse prompts)
  - count(identical) >= 1  (at least one prompt produces a perfect
    char-for-char match — high confidence on greedy decode determinism)

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_3_char_diff.py
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


PROMPTS: List[Dict[str, str]] = [
    {
        "id": "factual_recall",
        "prompt": (
            "The secret code is XYZ123. Repeat the secret code in the next "
            "sentence.\nThe secret code is"
        ),
    },
    {
        "id": "completion",
        "prompt": "Roses are red, violets are",
    },
    {
        "id": "arithmetic",
        "prompt": "Q: What is 7 times 8?\nA:",
    },
    {
        "id": "code",
        "prompt": "Write a one-line Python function that adds two numbers:\n```python\ndef add(a, b):",
    },
    {
        "id": "creative",
        "prompt": "Once upon a time, in a small village by the sea, there lived a baker who",
    },
]


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance. O(len(a) * len(b)). Both outputs are short
    (<= 64 chars in our config) so this is fine."""
    la, lb = len(a), len(b)
    if la == 0: return lb
    if lb == 0: return la
    # Rolling rows.
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,            # deletion
                curr[j - 1] + 1,        # insertion
                prev[j - 1] + cost,     # sub
            )
        prev = curr
    return prev[lb]


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            return n
        n += 1
    return n


def _first_divergence_context(a: str, b: str, ctx: int = 20):
    """Return (idx, a_around, b_around) for the first character difference."""
    n = _common_prefix(a, b)
    if n == max(len(a), len(b)) and len(a) == len(b):
        return None
    lo = max(0, n - ctx)
    hi_a = min(len(a), n + ctx + 1)
    hi_b = min(len(b), n + ctx + 1)
    return n, a[lo:hi_a], b[lo:hi_b]


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.workers[0].model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    raise RuntimeError("Could not locate the inner nn.Module.")


def _gen_stock(prompts: List[str], args) -> List[str]:
    import torch
    from vllm import LLM, SamplingParams
    print("[1/2] Generating stock vLLM outputs...")
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    outs = llm.generate(prompts, sampling)
    texts = [o.outputs[0].text for o in outs]
    del llm; gc.collect(); torch.cuda.empty_cache()
    return texts


def _gen_int4(prompts: List[str], args) -> List[str]:
    import torch
    from vllm import LLM, SamplingParams
    from kv_policy.phase5b_backend_install import (
        enable_int4_protected_backend, install_int4_protected_backend,
        Int4ProtectedAttentionImpl,
    )

    print("[2/2] Generating int4_protected outputs...")
    enable_int4_protected_backend()
    Int4ProtectedAttentionImpl.reset_call_stats()

    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        kv_cache_dtype="int4_protected",
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    model = _find_inner_model(llm)
    install_int4_protected_backend(model)
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    # batch=1 v1 invariant: serialize prompts (one generate call each).
    # PagedKVWriter holds per-layer staging that doesn't support
    # concurrent sequences yet (Phase 5B.5+). Each iteration reuses
    # the same per-layer sidecars + bf16 backing (overwritten by
    # writer.reset_sequence implicitly via the new seq_pos counter).
    texts: List[str] = []
    for i, p in enumerate(prompts, 1):
        print(f"  int4 prompt {i}/{len(prompts)}...")
        # Reset writer state per sequence (seq_pos counter + staging).
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    w.reset_sequence()
        out = llm.generate([p], sampling)
        texts.append(out[0].outputs[0].text)

    stats = Int4ProtectedAttentionImpl.get_call_stats()
    del llm, model; gc.collect(); torch.cuda.empty_cache()
    return texts, stats


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=64)
    parser.add_argument("--block-size",             type=int,   default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    args = parser.parse_args(argv)

    if args.block_size != 32:
        print(f"FAIL: block-size must be 32 (got {args.block_size}); kernel kInt4GroupSize=32.")
        return 1

    try:
        import torch  # noqa
        from vllm import SamplingParams  # noqa
    except ImportError as e:
        print(f"FAIL: import error ({e}). Run inside venv-vllm.")
        return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'.")
        return 1

    print("=" * 78)
    print("Phase 5B.4c.3 — stock-vs-int4 character diff")
    print("=" * 78)
    print(f"  model:             {args.model}")
    print(f"  max_model_len:     {args.max_model_len}")
    print(f"  max_tokens:        {args.max_tokens}")
    print(f"  block_size:        {args.block_size}")
    print(f"  protect_mask path: {mask_path}")
    print(f"  num_prompts:       {len(PROMPTS)}")
    print()

    prompt_strs = [p["prompt"] for p in PROMPTS]

    stock_texts = _gen_stock(prompt_strs, args)
    int4_texts, call_stats = _gen_int4(prompt_strs, args)

    print()
    print("=" * 78)
    print("Per-prompt results")
    print("=" * 78)

    per_prompt: List[Dict[str, Any]] = []
    for spec, stk, i4 in zip(PROMPTS, stock_texts, int4_texts):
        pid = spec["id"]
        cp = _common_prefix(stk, i4)
        cp_ratio = cp / max(1, min(len(stk), len(i4)))
        dist = _edit_distance(stk, i4)
        max_len = max(len(stk), len(i4))
        edit_ratio = 1.0 - dist / max(1, max_len)
        identical = (stk == i4)

        per_prompt.append({
            "id": pid,
            "stock_len": len(stk),
            "int4_len":  len(i4),
            "common_prefix": cp,
            "common_prefix_ratio": cp_ratio,
            "edit_distance": dist,
            "edit_ratio": edit_ratio,
            "identical": identical,
        })

        print()
        print(f"--- {pid} ---")
        print(f"  stock : {stk!r}")
        print(f"  int4  : {i4!r}")
        print(f"  common_prefix: {cp} chars ({cp_ratio*100:.0f}% of shorter)")
        print(f"  edit_distance: {dist} (edit_ratio {edit_ratio*100:.0f}%)")
        if identical:
            print(f"  *** IDENTICAL ***")
        else:
            div = _first_divergence_context(stk, i4)
            if div is not None:
                idx, a_ctx, b_ctx = div
                print(f"  first divergence at char {idx}:")
                print(f"    stock: ...{a_ctx!r}...")
                print(f"    int4 : ...{b_ctx!r}...")

    # ----- Aggregate -----
    print()
    print("=" * 78)
    print("Aggregate (across {} prompts)".format(len(per_prompt)))
    print("=" * 78)
    mean_cp = sum(p["common_prefix_ratio"] for p in per_prompt) / len(per_prompt)
    min_cp  = min(p["common_prefix_ratio"] for p in per_prompt)
    mean_ed = sum(p["edit_ratio"]          for p in per_prompt) / len(per_prompt)
    min_ed  = min(p["edit_ratio"]          for p in per_prompt)
    n_iden  = sum(1 for p in per_prompt if p["identical"])

    print(f"  common_prefix_ratio:   mean {mean_cp*100:5.1f}%   min {min_cp*100:5.1f}%")
    print(f"  edit_ratio:            mean {mean_ed*100:5.1f}%   min {min_ed*100:5.1f}%")
    print(f"  identical outputs:     {n_iden} / {len(per_prompt)}")

    print()
    print("  int4_protected backend call stats:")
    for k, v in call_stats.items():
        print(f"    {k}: {v}")

    # ----- Informational gates -----
    print()
    print("=" * 78)
    print("Gates")
    print("=" * 78)
    gates = []
    gates.append((
        "mean_cp_ratio >= 0.50  (avg prefix overlap is meaningful)",
        mean_cp >= 0.50,
    ))
    gates.append((
        "identical_count >= 1   (at least one perfect match)",
        n_iden >= 1,
    ))
    gates.append((
        "0 packed-decode fallbacks",
        call_stats.get("decode_calls_fallback", 0) == 0,
    ))
    gates.append((
        "0 write fallbacks",
        call_stats.get("write_path_fallback", 0) == 0,
    ))

    ok = True
    for label, passed in gates:
        marker = "PASS" if passed else "FAIL"
        if not passed: ok = False
        print(f"  [{marker}] {label}")

    print()
    if ok:
        print("Phase 5B.4c.3 char-diff: GREEN")
        return 0
    print("Phase 5B.4c.3 char-diff: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
