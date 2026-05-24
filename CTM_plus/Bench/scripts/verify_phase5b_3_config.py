#!/usr/bin/env python3
"""verify_phase5b_3_config.py — Phase 5B.3a acceptance.

Validates init-time installation via:
  enable_int4_protected_backend()
  LLM(model=..., kv_cache_dtype="int4_protected")

Five gates:
  1. enable_int4_protected_backend() runs without error.
  2. LLM(kv_cache_dtype="int4_protected") constructs successfully —
     i.e., CacheConfig validation accepts the dtype.
  3. model_runner.attn_backend IS Int4ProtectedAttentionBackend
     (init-time selection routed through our class).
  4. All 28 Attention.impl instances are Int4ProtectedAttentionImpl
     WITHOUT any post-init swap call (clean init-time selection).
  5. Generation produces bit-equal output to stock vLLM (delegate
     path unchanged).

Phase 5B.3a leaves memory layout untouched (block shape + byte cost
still bf16). Memory savings come in Phase 5B.4.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _find_inner_model(llm):
    return llm.llm_engine.model_executor.driver_worker.model_runner.model


def _find_model_runner(llm):
    return llm.llm_engine.model_executor.driver_worker.model_runner


def main() -> int:
    try:
        import torch
        from vllm import LLM, SamplingParams
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    from kv_policy.phase5b_backend_install import (
        enable_int4_protected_backend,
        disable_int4_protected_backend,
        is_int4_protected_enabled,
        Int4ProtectedAttentionBackend,
        Int4ProtectedAttentionImpl,
        count_int4_protected_impls,
    )

    prompt = (
        "The secret code is XYZ123. Repeat the secret code in the next "
        "sentence.\nThe secret code is"
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=32)

    print("=" * 70)
    print("Phase 5B.3a — init-time backend install verify")
    print("=" * 70)

    # ---- Stock vLLM baseline (no install) ------------------------
    print()
    print("[stock baseline — no install, kv_cache_dtype=auto]")
    llm_stock = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
    )
    out = llm_stock.generate([prompt], sampling)
    stock_text = out[0].outputs[0].text
    print(f"  stock output: {stock_text!r}")
    del llm_stock
    import gc; gc.collect(); torch.cuda.empty_cache()

    # ---- Test 1: enable_int4_protected_backend() runs ----------
    print()
    print("[Phase 5B.3a install — enable_int4_protected_backend()]")
    try:
        enable_int4_protected_backend()
        test1 = True
        test1_msg = "PASS"
    except Exception as e:
        test1 = False
        test1_msg = f"FAIL: enable raised {type(e).__name__}: {e}"
        print(f"  {test1_msg}")
        return 1
    assert is_int4_protected_enabled(), "is_int4_protected_enabled() lied"

    # ---- Test 2: LLM(kv_cache_dtype="int4_protected") ----------
    print()
    print("[LLM(kv_cache_dtype='int4_protected')]")
    try:
        llm = LLM(
            model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
            gpu_memory_utilization=0.3, enforce_eager=True,
            kv_cache_dtype="int4_protected",
        )
        test2 = True
        test2_msg = "PASS"
    except Exception as e:
        test2 = False
        test2_msg = f"FAIL: LLM construction raised {type(e).__name__}: {e}"
        print(f"  {test2_msg}")
        return 1

    # ---- Test 3: model_runner.attn_backend is our class --------
    mr = _find_model_runner(llm)
    backend_cls = mr.attn_backend
    print(f"  model_runner.attn_backend: {backend_cls}")
    test3 = backend_cls is Int4ProtectedAttentionBackend
    test3_msg = ("PASS" if test3
                 else f"FAIL: attn_backend is {backend_cls}, expected Int4ProtectedAttentionBackend")
    if not test3:
        print(f"  {test3_msg}")

    # ---- Test 4: all 28 Attention.impl are our subclass --------
    model = mr.model
    n_ours, n_total = count_int4_protected_impls(model)
    print(f"  Attention impls: {n_ours}/{n_total} are Int4ProtectedAttentionImpl")
    test4 = (n_ours == n_total and n_total > 0)
    test4_msg = ("PASS" if test4
                 else f"FAIL: only {n_ours}/{n_total} impls are our subclass — "
                      f"init-time selection didn't propagate to per-layer impls")

    # ---- Test 5: generation is bit-equal to stock --------------
    out = llm.generate([prompt], sampling)
    install_text = out[0].outputs[0].text
    print(f"  install output: {install_text!r}")
    test5 = (install_text == stock_text)
    test5_msg = ("PASS" if test5
                 else "FAIL: install output differs from stock — delegate broken?")

    # Cleanup — disable patches so a future LLM() with kv_cache_dtype="auto"
    # is unaffected.
    disable_int4_protected_backend()

    # ---- Summary ----------------------------------------------
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    results = [
        ("enable_int4_protected runs            ", test1_msg),
        ("LLM(kv_cache_dtype='int4_protected')  ", test2_msg),
        ("model_runner.attn_backend is our class", test3_msg),
        ("all 28 impls are Int4ProtectedAttentionImpl", test4_msg),
        ("generation matches stock              ", test5_msg),
    ]
    all_ok = all(m.startswith("PASS") for _, m in results)
    for name, status in results:
        print(f"  [{status.split(':')[0]}] {name}: {status}")
    print()
    if all_ok:
        print("Phase 5B.3a: GREEN")
        return 0
    print("Phase 5B.3a: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
