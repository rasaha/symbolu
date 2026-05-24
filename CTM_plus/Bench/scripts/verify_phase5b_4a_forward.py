#!/usr/bin/env python3
"""verify_phase5b_4a_forward.py — Phase 5B.4a acceptance.

5B.4a: Int4ProtectedAttentionImpl.forward is now a FULL REPLICATION of
FlashAttentionImpl.forward (with kv_cache_dtype="int4_protected" mapped
to "auto" at the reshape_and_cache_flash call site). Same code paths,
same output — but every call site is in our hands now, ready for 5B.4b
(shape shrink) and 5B.4c (read/write path replacement).

Gates:
  1. Install path still works (5B.3a gates 1-4 still pass).
  2. Generation BIT-EQUAL to stock baseline (verifies the replication
     didn't drift from FA forward).
  3. The forward is NOT a delegate — verified by inspecting the marker
     attribute (_phase5b_backend_marker == "5B.4a").

If all pass: 5B.4a GREEN. We now own the full attention forward and
can start modifying call sites without breaking the bit-equal gate.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


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
    print("Phase 5B.4a — forward replication verify")
    print("=" * 70)

    # ---- Stock baseline -----------------------------------------
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

    # ---- Phase 5B.4a install ------------------------------------
    print()
    print("[Phase 5B.4a install]")
    enable_int4_protected_backend()
    llm = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
        kv_cache_dtype="int4_protected",
    )
    mr = _find_model_runner(llm)
    model = mr.model

    # Sanity: marker shows we're in 5B.4a, not 5B.2/3a.
    sample_impl = None
    for _, sub in model.named_modules():
        if (hasattr(sub, "impl")
                and isinstance(sub.impl, Int4ProtectedAttentionImpl)):
            sample_impl = sub.impl
            break
    marker = getattr(sample_impl, "_phase5b_backend_marker", None)
    print(f"  sample impl marker: {marker!r}")
    test_marker = (marker == "5B.4a")

    # Confirm install paths still work.
    n_ours, n_total = count_int4_protected_impls(model)
    print(f"  impls: {n_ours}/{n_total} are Int4ProtectedAttentionImpl")
    test_install = (n_ours == n_total and n_total > 0)
    test_backend = (mr.attn_backend is Int4ProtectedAttentionBackend)

    # ---- Generate ----------------------------------------------
    out = llm.generate([prompt], sampling)
    install_text = out[0].outputs[0].text
    print(f"  install output: {install_text!r}")
    test_match = (install_text == stock_text)

    disable_int4_protected_backend()

    # ---- Summary -----------------------------------------------
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    results = [
        ("backend is Int4ProtectedAttentionBackend", test_backend),
        ("all impls are Int4ProtectedAttentionImpl ", test_install),
        ("impl marker == '5B.4a'                   ", test_marker),
        ("generation BIT-EQUAL to stock            ", test_match),
    ]
    all_ok = all(ok for _, ok in results)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print()
    if all_ok:
        print("Phase 5B.4a: GREEN")
        print("  (full forward replication; ready for 5B.4b shape shrink.)")
        return 0
    print("Phase 5B.4a: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
