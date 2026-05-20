#!/usr/bin/env python3
"""Four-cell decode-throughput harness for 6c.3A (model-level fused
protected-K decode bypass).

Cells (one process per cell; choose with ``--cell``):

  A — vLLM FP16 (``--kv-cache-dtype auto``). Production baseline.
  B — vLLM FP8  (``--kv-cache-dtype fp8``).  Current competitor.
  C — vLLM FP16 + route-A ``dequant_fallback``. The no-kernel route-A
      floor: every attention call dequantizes INT4→FP16 in a torch
      op, then vLLM's PagedAttention runs on the lossy FP16. vLLM's
      KV pool stays FP16 — no memory compression.
  D — vLLM FP16 + route-A ``fused_v2``. The 6c.3A bypass: prefill
      sidecars K/V into a parallel ``ProtectedKINT4Cache``; decode
      replaces vLLM's ``Attention.forward`` with the fused INT4
      kernel running over the accumulated cache. Decodes bypass
      vLLM's PagedAttention.

Honest scope (carry-through; see ``KERNEL_6C3A_DESIGN.md`` §3.6):

* Cell D is **NOT** real vLLM serving throughput. It is "fused-kernel
  decode on a vLLM-loaded model" — PagedAttention's continuous
  batching / scheduling / prefix caching / chunked prefill are
  bypassed during decode.
* Cell D does **NOT** measure INT4 memory compression. vLLM's FP16
  KV cache is still allocated; our ``ProtectedKINT4Cache`` is
  *additional* memory.
* Cell D is **batch = 1** single-sequence only. Multi-sequence
  decoding is 6c.3.2 / 6c.3C.
* Cell D's parallel cache uses ``group_size_k = 1`` (per-token K) — a
  6c.3A v1 SIMPLIFICATION, NOT the §20.4 measured group=32 config.
  If cell D quality or speed differs from §20.4 numbers, the
  per-token-K config must be isolated before any product claim.

Each run produces a JSON like ``kernel_6c_throughput.py``'s but with
``cell``, ``kv_cache_dtype``, ``kernel_backend``, ``peak_memory_gb``
fields. Aggregate with ``compose_throughput_comparison.py`` (or a
small jq script) — see KERNEL_6C3A_DESIGN.md §3.6 decision table.

CLI:

  python scripts/kernel_6c3a_throughput.py --cell A --output a.json
  python scripts/kernel_6c3a_throughput.py --cell B --output b.json
  python scripts/kernel_6c3a_throughput.py --cell C --output c.json
  python scripts/kernel_6c3a_throughput.py --cell D --output d.json

Requires vLLM (the venv-vllm environment; see
``FP8_INT4_THROUGHPUT_RUNBOOK.md``). vLLM 0.7.3 validated.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence


# Make kv_policy importable when running from CTM_plus/Bench/.
_KV = Path(__file__).resolve().parents[2] / "KVPolicy"
if str(_KV) not in sys.path:
    sys.path.insert(0, str(_KV))


CELL_LABELS = {
    "A": "vLLM FP16 (auto)",
    "B": "vLLM FP8 (--kv-cache-dtype fp8)",
    "C": "vLLM FP16 + route-A dequant_fallback (no kernel)",
    "D": "vLLM FP16 + route-A fused_v2 (6c.3A model-level fused decode bypass)",
}

CELL_KV_DTYPE = {"A": "auto", "B": "fp8", "C": "auto", "D": "auto"}
CELL_NEEDS_ROUTE_A = {"A": False, "B": False, "C": True, "D": True}
CELL_BACKEND = {"C": "dequant_fallback", "D": "fused_v2"}


# --------------------------------------------------------------------- #
# Helpers                                                               #
# --------------------------------------------------------------------- #


def _walk_to_model(llm) -> Any:
    """Walk the LLM → engine → executor → worker → runner → model path.

    Mirrors ``runner_vllm_streaming.AsyncEngineDriver._extract_model_from_engine``
    described in ``ROUTE_A_VLLM_CACHE_KV_PLAN.md`` §"discovery hook".
    Across vLLM 0.7.x the symbol names are stable; if a future
    minor changes them, this walk needs adjusting.
    """
    engine = getattr(llm, "llm_engine", llm)
    executor = getattr(engine, "model_executor", None)
    if executor is None:
        raise RuntimeError(
            "LLM.llm_engine.model_executor not found; vLLM version may "
            "have moved this symbol. See ROUTE_A_VLLM_CACHE_KV_PLAN.md "
            "§'discovery hook' for the expected path."
        )
    # Try `driver_worker` first (0.7.x classic path), fall back to
    # iterating `workers` if a multi-worker executor is in use (cell D
    # is batch=1 single-process; we only need the driver).
    worker = getattr(executor, "driver_worker", None)
    if worker is None:
        workers = getattr(executor, "workers", None)
        if workers:
            worker = workers[0]
    if worker is None:
        raise RuntimeError(
            "model_executor.driver_worker / .workers not found"
        )
    runner = getattr(worker, "model_runner", None)
    if runner is None:
        raise RuntimeError("worker.model_runner not found")
    model = getattr(runner, "model", None)
    if model is None:
        raise RuntimeError("model_runner.model not found")
    return model


def _build_fixed_prompt(tok, prompt_tokens: int) -> str:
    """Build a prompt of exactly ``prompt_tokens`` tokens by repeating
    a neutral filler. Same approach as vllm_throughput_cell.py — for
    throughput measurement we time forward passes, not quality."""
    text = (
        "The history of artificial intelligence began in antiquity with "
        "myths and stories of artificial beings. "
    )
    while len(tok(text)["input_ids"]) < prompt_tokens:
        text += text
    ids = tok(text)["input_ids"][:prompt_tokens]
    return tok.decode(ids)


def _kv_bytes_per_token_per_layer_fp16(num_kv_heads: int, head_dim: int) -> int:
    """K + V at FP16: 2 bytes/elem × 2 (K and V) × H_kv × D per token per layer."""
    return 2 * 2 * num_kv_heads * head_dim


# --------------------------------------------------------------------- #
# Main                                                                  #
# --------------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="kernel_6c3a_throughput",
        description=(
            "Four-cell decode-throughput harness for 6c.3A. One process "
            "per cell. See KERNEL_6C3A_DESIGN.md §3.6 for the decision "
            "rules on the resulting table."
        ),
    )
    parser.add_argument(
        "--cell", required=True, choices=["A", "B", "C", "D"],
        help="A=FP16, B=FP8, C=route-A dequant_fallback, "
             "D=route-A fused_v2 (6c.3A).",
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--num-prompts", type=int, default=1,
        help="6c.3A v1 requires batch=1 — cell D needs --num-prompts=1. "
             "Cells A/B/C accept larger batches; defaults to 1 for "
             "apples-to-apples.",
    )
    parser.add_argument(
        "--prompt-tokens", type=int, default=2048,
        help="Prompt length in tokens. Treat as the prefill / cached "
             "S_kv before decode starts.",
    )
    parser.add_argument(
        "--decode-tokens", type=int, default=128,
        help="Tokens generated per prompt (forced via ignore_eos).",
    )
    parser.add_argument(
        "--gpu-memory-utilization", type=float, default=0.5,
        help="vLLM GPU memory fraction.",
    )
    parser.add_argument(
        "--protect-fraction", type=float, default=0.04,
        help="Cell D only — top-fraction of K channels kept FP16 "
             "(default 0.04 — the §20.4.2 win).",
    )
    parser.add_argument(
        "--cache-max-seq-len-margin", type=int, default=128,
        help="Cell D only — extra slots on top of prompt+decode for the "
             "parallel cache's preallocation.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    cell = args.cell

    # 6c.3A v1: cell D is batch=1 only.
    if cell == "D" and args.num_prompts != 1:
        raise SystemExit(
            f"Cell D (6c.3A) is batch=1 only in v1; got --num-prompts="
            f"{args.num_prompts}. Multi-sequence is 6c.3.2 (deferred)."
        )

    # Lazy import — keeps --help / tests usable without vLLM.
    try:
        from vllm import LLM, SamplingParams  # type: ignore
    except ImportError:
        raise SystemExit(
            "vLLM not installed. This script runs in the venv-vllm "
            "environment — `pip install 'vllm==0.7.3'`. See "
            "FP8_INT4_THROUGHPUT_RUNBOOK.md."
        )
    try:
        import torch  # type: ignore
    except ImportError:
        raise SystemExit("torch not installed (should come with vLLM).")

    print("=" * 78)
    print(f"Cell {cell}: {CELL_LABELS[cell]}")
    print(f"  model        = {args.model}")
    print(f"  kv_cache_dtype = {CELL_KV_DTYPE[cell]}")
    if CELL_NEEDS_ROUTE_A[cell]:
        print(f"  route-A      = backend={CELL_BACKEND[cell]}")
    print(f"  prompt_tokens = {args.prompt_tokens}")
    print(f"  decode_tokens = {args.decode_tokens}")
    print(f"  num_prompts   = {args.num_prompts}")
    print("=" * 78)

    # Load vLLM with the cell's KV dtype.
    max_model_len = (
        args.prompt_tokens + args.decode_tokens + args.cache_max_seq_len_margin
    )
    print(f"Loading {args.model} (max_model_len={max_model_len})...", flush=True)
    torch.cuda.reset_peak_memory_stats()
    llm = LLM(
        model=args.model,
        kv_cache_dtype=CELL_KV_DTYPE[cell],
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=max_model_len,
        enforce_eager=True,    # disables CUDA graphs so route-A's
                               #  forward replacement actually fires
        seed=args.seed,
    )
    peak_after_load = torch.cuda.max_memory_allocated() / (1024 ** 3)

    # Install route-A if this cell needs it.
    manager = None
    teardown_route_a = None
    if CELL_NEEDS_ROUTE_A[cell]:
        print(f"Installing route-A (backend={CELL_BACKEND[cell]})...", flush=True)
        from kv_policy.int4_cache_kv_route_a import (
            install_int4_cache_kv_route_a,
            BACKEND_DEQUANT_FALLBACK, BACKEND_FUSED_V2,
        )
        backend = (
            BACKEND_FUSED_V2 if cell == "D" else BACKEND_DEQUANT_FALLBACK
        )
        model = _walk_to_model(llm)

        kwargs: dict = dict(
            model=model,
            k_group_size=32, v_group_size=32,   # round_trip_kv path
            asymmetric=True, bits=4,
            kernel_backend=backend,
        )
        if cell == "D":
            kwargs.update(
                max_seq_len=max_model_len,
                protect_fraction=args.protect_fraction,
                cache_k_group_size=1,           # v1 simplification
                cache_v_group_size=32,
            )
        manager, teardown_route_a = install_int4_cache_kv_route_a(**kwargs)
        print(f"route-A installed: {manager.config['scheme']}", flush=True)

    # Build prompts.
    tok = llm.get_tokenizer()
    prompt = _build_fixed_prompt(tok, args.prompt_tokens)
    prompts = [prompt] * args.num_prompts

    sp = SamplingParams(
        temperature=0.0,
        max_tokens=args.decode_tokens,
        ignore_eos=True,
        seed=args.seed,
    )

    # Warmup (untimed).
    print("Warmup...", flush=True)
    if manager is not None:
        manager.reset()
    llm.generate(prompts[:1], sp, use_tqdm=False)

    # Timed run.
    if manager is not None:
        manager.reset()
    torch.cuda.reset_peak_memory_stats()
    print(f"Timed run: {args.num_prompts} prompts × {args.decode_tokens} "
          f"decode tokens...", flush=True)
    t0 = time.perf_counter()
    outs = llm.generate(prompts, sp, use_tqdm=False)
    elapsed = time.perf_counter() - t0
    peak_during_run = torch.cuda.max_memory_allocated() / (1024 ** 3)

    n_decode = sum(len(o.outputs[0].token_ids) for o in outs)
    tps = n_decode / elapsed if elapsed > 0 else 0.0

    # KV bytes-per-token-per-layer (analytic, FP16 cell A baseline).
    try:
        cfg = llm.get_tokenizer().__class__  # noqa: F841 (unused — kept for symmetry)
        hf_cfg = getattr(llm.llm_engine, "model_config", None)
        if hf_cfg is not None:
            num_kv_heads = (
                getattr(hf_cfg, "num_key_value_heads", None)
                or getattr(hf_cfg, "num_attention_heads", None)
            )
            head_dim = getattr(hf_cfg, "head_dim", None)
            if head_dim is None and hasattr(hf_cfg, "hidden_size"):
                n_h = getattr(hf_cfg, "num_attention_heads", None)
                if n_h and n_h > 0:
                    head_dim = hf_cfg.hidden_size // n_h
        else:
            num_kv_heads = head_dim = None
    except Exception:  # noqa: BLE001
        num_kv_heads = head_dim = None
    kv_bytes_per_token_per_layer_fp16 = (
        _kv_bytes_per_token_per_layer_fp16(num_kv_heads, head_dim)
        if num_kv_heads and head_dim else None
    )

    # Cell-D extras: route-A stats + cache reach.
    extras = {}
    if manager is not None:
        extras["route_a_config"] = manager.config
        extras["route_a_stats"] = manager.stats
        if cell == "D" and manager.caches:
            first = next(iter(manager.caches.values()))
            extras["cache_seq_len_after_run"] = first.seq_len
            extras["cache_is_frozen"] = first.is_frozen

    result = {
        "cell": cell,
        "label": CELL_LABELS[cell],
        "model_id": args.model,
        "kv_cache_dtype": CELL_KV_DTYPE[cell],
        "kernel_backend": (
            CELL_BACKEND[cell] if CELL_NEEDS_ROUTE_A[cell] else None
        ),
        "num_prompts": args.num_prompts,
        "prompt_tokens": args.prompt_tokens,
        "decode_tokens_per_prompt": args.decode_tokens,
        "n_decode_tokens": n_decode,
        "wall_clock_seconds": elapsed,
        "tokens_per_second": tps,
        "peak_memory_gb_after_load": peak_after_load,
        "peak_memory_gb_during_run": peak_during_run,
        "kv_bytes_per_token_per_layer_fp16": kv_bytes_per_token_per_layer_fp16,
        "honest_scope": (
            "Cell D is fused-kernel decode on a vLLM-loaded model "
            "(PagedAttention bypassed on decode), not real vLLM "
            "serving throughput. Cell D parallel cache uses "
            "group_size_k=1 (per-token K) — a 6c.3A v1 SIMPLIFICATION, "
            "NOT the §20.4 measured group=32 config. No memory "
            "compression claim — vLLM's FP16 KV pool stays allocated."
            if cell == "D" else ""
        ),
        **extras,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print()
    print(json.dumps({
        k: v for k, v in result.items()
        if k not in ("route_a_stats", "route_a_config")  # too verbose
    }, indent=2))
    print()
    print(f"Wrote {args.output}")

    if teardown_route_a is not None:
        teardown_route_a()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
