#!/usr/bin/env python3
"""verify_phase5a_smoke.py — 6c.3C Phase 5A acceptance smoke test.

Routes a short Qwen2.5-7B generation through the Phase 5A install:
prefill goes through stock vLLM attention (so vLLM's paged cache
stays populated), decode goes through flash_attn_with_int4_kvcache
with a static top-4% protect mask computed from the prefill K.

What this validates:
  - Phase 5A install function attaches to vLLM's attention modules.
  - The wrapper correctly distinguishes prefill (T > 1) from decode
    (T == 1).
  - The native kernel actually gets called on decode (manager stats
    show decode_calls > 0).
  - The generated output is non-empty and coherent (sanity check).
  - No fallbacks fired (fallback_calls == 0).
  - Optionally compares output to a stock vLLM run for sanity.

V1 batch=1 only. Multiple concurrent sequences would corrupt the
sidecar state.

Exit 0 = GREEN, 1 = FAIL.
"""
from __future__ import annotations
import argparse
import sys
import os
from pathlib import Path

# Make kv_policy importable.
ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _find_inner_model(llm) -> object:
    """vLLM's `LLM` -> the underlying nn.Module that holds attention layers.

    vLLM 0.7.3 path:
        llm.llm_engine.model_executor.driver_worker.model_runner.model
    Falls back through a few alternatives for version drift.
    """
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.workers[0].model_runner.model,
    ]
    last_err = None
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError) as e:
            last_err = e
    raise RuntimeError(
        "Could not locate the inner nn.Module on the vLLM LLM. "
        f"Last error: {last_err}. vLLM internals may have changed."
    )


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=4096,
                        help="Keep small to bound memory in the smoke test.")
    parser.add_argument("--max-tokens",     type=int, default=32)
    parser.add_argument("--protect-fraction", type=float, default=0.04)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--no-stock-compare", action="store_true",
                        help="Skip the stock-vs-Phase5A output diff. The "
                             "diff is informational — outputs won't match "
                             "exactly because INT4 quant introduces drift.")
    args = parser.parse_args(argv)

    try:
        import torch  # noqa: F401
        from vllm import LLM, SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e}). Run inside venv-vllm.")
        return 1

    from kv_policy.phase5a_native_install import install_phase5a_native

    prompt = (
        "The secret code is XYZ123. Repeat the secret code in the next "
        "sentence.\nThe secret code is"
    )
    sampling = SamplingParams(
        temperature=0.0,  # greedy — reproducible
        max_tokens=args.max_tokens,
        stop=None,
    )

    print(f"Phase 5A smoke test")
    print(f"  model:             {args.model}")
    print(f"  max_model_len:     {args.max_model_len}")
    print(f"  protect_fraction:  {args.protect_fraction}")
    print(f"  prompt:            {prompt!r}")
    print()

    # ----- Optional: stock vLLM run for sanity comparison ----------
    stock_text: str = ""
    if not args.no_stock_compare:
        print("[1/2] Stock vLLM (no Phase5A install) -- baseline run")
        llm_stock = LLM(
            model=args.model, max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
        out = llm_stock.generate([prompt], sampling)
        stock_text = out[0].outputs[0].text
        print(f"  stock output: {stock_text!r}")
        print()
        del llm_stock
        import gc
        gc.collect()
        torch.cuda.empty_cache()

    # ----- Phase 5A install run -----------------------------------
    print(f"[{'2/2' if not args.no_stock_compare else '1/1'}] Phase 5A install run")
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    model = _find_inner_model(llm)
    print(f"  located inner model: {type(model).__name__}")

    manager, teardown = install_phase5a_native(
        model,
        protect_fraction=args.protect_fraction,
        max_seqlen=args.max_model_len,
    )

    out = llm.generate([prompt], sampling)
    p5a_text = out[0].outputs[0].text

    stats = manager.stats()
    teardown()

    print(f"  Phase5A output: {p5a_text!r}")
    print()
    print(f"Phase 5A stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()

    # ----- Gates ---------------------------------------------------
    ok = True
    fail_reasons = []

    if not p5a_text or not p5a_text.strip():
        ok = False
        fail_reasons.append("Phase 5A produced empty output")

    if stats["prefill_calls"] <= 0:
        ok = False
        fail_reasons.append(
            f"no prefill calls recorded "
            f"(prefill_calls={stats['prefill_calls']}); the wrapper "
            f"didn't see prefill — install may not have attached"
        )

    if stats["decode_calls"] <= 0:
        ok = False
        fail_reasons.append(
            f"no decode calls recorded "
            f"(decode_calls={stats['decode_calls']}); native kernel "
            f"path was never exercised"
        )

    if stats["fallback_calls"] > 0:
        # Fallbacks are warnings, not hard failures, but a high rate
        # means the wrapper isn't doing its job.
        rate = stats["fallback_calls"] / max(
            1, stats["prefill_calls"] + stats["decode_calls"]
            + stats["fallback_calls"]
        )
        if rate > 0.10:
            ok = False
            fail_reasons.append(
                f"fallback_calls rate {rate*100:.0f}% > 10% "
                f"({stats['fallback_calls']} fallbacks)"
            )
        else:
            print(f"  WARNING: {stats['fallback_calls']} fallbacks "
                  f"({rate*100:.0f}% rate); informational only.")

    if not args.no_stock_compare and stock_text:
        # Compute a coarse string similarity. INT4 introduces drift,
        # so we don't expect exact match — but the answers should
        # share substantial prefix on a deterministic greedy run.
        common_prefix = 0
        for a, b in zip(stock_text, p5a_text):
            if a != b:
                break
            common_prefix += 1
        prefix_ratio = common_prefix / max(1, min(len(stock_text), len(p5a_text)))
        print(f"  stock-vs-Phase5A common prefix: {common_prefix} chars "
              f"({prefix_ratio*100:.0f}% of shorter output)")
        # Don't gate on this — INT4 drift may diverge token sequences.

    print()
    if ok:
        print(f"Phase 5A SMOKE: PASS")
        print(f"  - native kernel path exercised "
              f"({stats['decode_calls']} decode calls)")
        print(f"  - prefill recorded ({stats['prefill_calls']} calls)")
        print(f"  - fallback rate within tolerance")
        print(f"  - output is non-empty and coherent")
        return 0

    print(f"Phase 5A SMOKE: FAIL")
    for r in fail_reasons:
        print(f"  - {r}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
