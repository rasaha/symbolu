#!/usr/bin/env python3
"""verify_phase5b_2_backend.py — Phase 5B.2 acceptance.

Validates the Int4ProtectedAttentionImpl install:

  Test 1 — Install attaches to all 28 Attention layers on Qwen2.5-7B.
    Gate: count_int4_protected_impls(model) returns (28, 28).

  Test 2 — Generation works through the swapped impls.
    Since v0 is pure delegate, output should match stock vLLM BIT-FOR-BIT.
    Gate: install output == stock output (string equality on greedy decode).

  Test 3 — Teardown restores the original FlashAttentionImpl.
    Gate: count_int4_protected_impls(model) returns (0, 28) after teardown.

  Test 4 — Manager stats reflect what happened.
    Gate: stats['swapped_impls'] == 28; no skipped / fallback_forward.

Each test failure dumps actionable detail. PASS on all four = Phase 5B.2
GREEN.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            pass
    raise RuntimeError("Could not locate inner nn.Module")


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
        install_int4_protected_backend,
        count_int4_protected_impls,
        Int4ProtectedAttentionImpl,
    )

    prompt = (
        "The secret code is XYZ123. Repeat the secret code in the next "
        "sentence.\nThe secret code is"
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=32)

    print("=" * 70)
    print("Phase 5B.2 — Int4ProtectedAttentionImpl install verify")
    print("=" * 70)

    # ---- Stock vLLM baseline (no install) ------------------------
    print()
    print("[stock baseline]")
    llm_stock = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
    )
    out = llm_stock.generate([prompt], sampling)
    stock_text = out[0].outputs[0].text
    print(f"  stock output: {stock_text!r}")
    del llm_stock
    import gc; gc.collect(); torch.cuda.empty_cache()

    # ---- Install + verify --------------------------------------
    print()
    print("[Phase 5B.2 install]")
    llm = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
    )
    model = _find_inner_model(llm)

    # PRE-install state.
    n_pre_ours, n_pre_total = count_int4_protected_impls(model)
    print(f"  pre-install: int4_protected={n_pre_ours}, total_FA_impl={n_pre_total}")

    manager, teardown = install_int4_protected_backend(model)
    print(f"  manager stats: {manager.stats()}")

    # ---- Test 1: install count ---------------------------------
    n_post_ours, n_post_total = count_int4_protected_impls(model)
    print(f"  post-install: int4_protected={n_post_ours}, total_FA_impl={n_post_total}")
    test1 = (n_post_ours == n_post_total and n_post_total > 0)
    test1_msg = ("PASS" if test1
                 else f"FAIL: not all FA impls swapped ({n_post_ours}/{n_post_total})")

    # ---- Test 2: generation matches stock ----------------------
    out = llm.generate([prompt], sampling)
    install_text = out[0].outputs[0].text
    print(f"  install output: {install_text!r}")
    test2 = (install_text == stock_text)
    test2_msg = ("PASS" if test2
                 else "FAIL: install output differs from stock — delegate broken")

    # ---- Test 4: stats sanity (run before teardown) ------------
    stats = manager.stats()
    test4 = (
        stats["swapped_impls"] == n_post_total
        and stats["skipped_not_FA_impl"] == 0
        and stats["skipped_no_impl_attr"] == 0
    )
    test4_msg = "PASS" if test4 else f"FAIL: stats inconsistent: {stats}"

    # ---- Test 3: teardown restores ------------------------------
    teardown()
    n_after_teardown_ours, n_after_teardown_total = count_int4_protected_impls(model)
    print(f"  after teardown: int4_protected={n_after_teardown_ours}, "
          f"total_FA_impl={n_after_teardown_total}")
    test3 = (n_after_teardown_ours == 0 and n_after_teardown_total > 0)
    test3_msg = ("PASS" if test3
                 else f"FAIL: teardown left {n_after_teardown_ours} subclassed impls")

    # ---- Summary ----------------------------------------------
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    results = [
        ("install count       ", test1_msg),
        ("generation matches stock", test2_msg),
        ("teardown restores   ", test3_msg),
        ("manager stats sane  ", test4_msg),
    ]
    for name, status in results:
        print(f"  [{status.split(':')[0]}] {name}: {status}")

    all_ok = all(s.startswith("PASS") for _, s in results)
    print()
    if all_ok:
        print("Phase 5B.2: GREEN")
        return 0
    print("Phase 5B.2: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
