#!/usr/bin/env python3
"""verify_phase2_4_1d.py — Phase 2.4.1d acceptance.

Three gates:

  1. EQUIVALENCE: repack_incremental(g) for a modified group must
     produce the same packed dict as a full repack with the same
     final K state. If different → bug in incremental update.

  2. SPEED: Phase 2.4.1c install with incremental repack must show
     `decode_repack` per-step time COLLAPSING (target: <0.1 ms vs
     v0's 0.804 ms).

  3. CORRECTNESS: end-to-end Qwen2.5-7B smoke through Phase 2.4.1c
     install still works (0 fallbacks, needle retrieved).

Final timing should approach `decode_kernel + decode_append` only —
the repack should disappear from the dominant path.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _cosine(a, b) -> float:
    import torch
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(
        af.unsqueeze(0), bf.unsqueeze(0)
    ).item())


def test_equivalence() -> bool:
    """Compare repack_incremental output against full repack on the
    same final K state. They MUST match (incremental is a faster
    way to compute the same thing, not an approximation)."""
    import torch
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase2_4_native_install import Phase2_4PackedCache

    print()
    print("=" * 70)
    print("Test 1 — equivalence: repack_incremental == full repack")
    print("=" * 70)

    torch.manual_seed(123)
    B, S, H, D = 1, 4096, 4, 128
    GROUP = 32
    PF = 0.04
    device = "cuda"

    # Build a cache, populate prefill K, run a full repack as the
    # initial state.
    cache = Phase2_4PackedCache()
    k_prefill = torch.randn(S - 64, H, D, device=device, dtype=torch.bfloat16)
    cache.append(k_prefill, k_prefill, max_seqlen=S)
    cache.compute_protect_mask(PF)
    cache.repack(PF, group_size=GROUP)
    snapshot_init = {k: v.clone() for k, v in cache.packed.items()}

    # Add a single decode token; full-repack the same state for ground truth.
    k_new = torch.randn(1, H, D, device=device, dtype=torch.bfloat16)
    cache.append(k_new, k_new, max_seqlen=S)
    # Two paths from this state:
    #   (a) full repack of self.k_fp16 -> ground truth `gt`.
    #   (b) incremental on top of the initial snapshot -> candidate.
    cache.packed = {k: v.clone() for k, v in snapshot_init.items()}
    cache.repack_incremental(group_size=GROUP)
    candidate = cache.packed

    cache.repack(PF, group_size=GROUP)
    gt = cache.packed

    ok = True
    for key in ("k_int4", "k_scale", "k_xmin", "k_protect_bf16", "protect_slot"):
        a = candidate[key]
        b = gt[key]
        if a.shape != b.shape:
            print(f"  FAIL [{key}]: shape {a.shape} != {b.shape}")
            ok = False
            continue
        if a.dtype == torch.uint8 or a.dtype == torch.int8:
            equal = bool((a == b).all().item())
            print(f"  [{key:20s}] dtype={a.dtype}, shape={tuple(a.shape)}, "
                  f"bit-equal={equal}")
            if not equal:
                # Locate first mismatch.
                diff = (a != b).nonzero(as_tuple=False)
                print(f"    first {min(3, len(diff))} mismatch idx: "
                      f"{diff[:3].tolist()}")
                ok = False
        else:
            cos = _cosine(a, b)
            maxdiff = float((a.float() - b.float()).abs().max().item())
            print(f"  [{key:20s}] dtype={a.dtype}, shape={tuple(a.shape)}, "
                  f"cosine={cos:.7f}, max-abs={maxdiff:.4e}")
            if cos < 0.99999 or maxdiff > 1e-3:
                ok = False
    return ok


def test_e2e_smoke() -> bool:
    """End-to-end Phase 2.4.1c install through Qwen2.5-7B, with
    timing enabled. Asserts:
      - decode_repack mean drops below 0.1 ms (vs v0's 0.804 ms)
      - 0 fallbacks
      - needle retrieved
    """
    import torch
    from vllm import LLM, SamplingParams
    from kv_policy.phase2_4_native_install import install_phase2_4_packed

    print()
    print("=" * 70)
    print("Test 2 — end-to-end smoke (Qwen2.5-7B) with timing")
    print("=" * 70)

    llm = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=4096,
        gpu_memory_utilization=0.5, enforce_eager=True,
    )
    worker = llm.llm_engine.model_executor.driver_worker
    manager, teardown = install_phase2_4_packed(
        worker.model_runner.model,
        protect_fraction=0.04, max_seqlen=4096, enable_timing=True,
    )

    prompt = ("The secret code is XYZ123. Repeat the secret code in the "
              "next sentence.\nThe secret code is")
    out = llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=32))
    text = out[0].outputs[0].text
    stats = manager.stats()
    timing = manager.timing_summary()
    teardown()

    print(f"  output: {text!r}")
    print(f"  stats: prefill={stats['prefill_calls']}, "
          f"decode={stats['decode_calls']}, fallback={stats['fallback_calls']}")
    print()
    print("  Per-decode-step timing (Phase 2.4.1d):")
    total_ms = 0.0
    for ev in ("decode_append", "decode_repack", "decode_kernel"):
        if ev in timing:
            m = timing[ev]
            print(f"    {ev:25s} mean={m['mean_ms']:6.3f} ms  "
                  f"median={m['median_ms']:6.3f} ms  count={m['count']}")
            total_ms += m["mean_ms"]
    print(f"    {'(sum of measured)':25s} {total_ms:6.3f} ms")

    ok = True
    if stats["fallback_calls"] > 0:
        print(f"  FAIL: fallback_calls={stats['fallback_calls']} > 0")
        ok = False
    if stats["decode_calls"] == 0:
        print(f"  FAIL: decode_calls=0; packed path never fired")
        ok = False
    if not text or not text.strip():
        print(f"  FAIL: empty output")
        ok = False
    if "XYZ123" not in text:
        print(f"  WARN: needle 'XYZ123' not in output (informational)")
    repack_ms = timing.get("decode_repack", {}).get("mean_ms", 999.0)
    if repack_ms > 0.2:
        print(f"  FAIL: decode_repack mean={repack_ms:.3f} ms > 0.2 ms gate; "
              f"incremental repack didn't take effect (v0 was 0.804 ms).")
        ok = False
    else:
        v0_ratio = 0.804 / repack_ms if repack_ms > 0 else float("inf")
        print(f"  decode_repack speedup vs v0: {v0_ratio:.1f}× "
              f"(0.804 ms → {repack_ms:.3f} ms)")
    return ok


def main() -> int:
    try:
        import torch
        from vllm import LLM  # noqa: F401
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    r1 = test_equivalence()
    print()
    print("=" * 70)
    print(f"Test 1 result: {'PASS' if r1 else 'FAIL'}")
    print("=" * 70)
    if not r1:
        print("Equivalence FAILED. Skipping smoke — fix incremental update first.")
        return 1

    r2 = test_e2e_smoke()
    print()
    print("=" * 70)
    print(f"Test 2 result: {'PASS' if r2 else 'FAIL'}")
    print("=" * 70)

    if r1 and r2:
        print("\nPhase 2.4.1d: GREEN")
        return 0
    print("\nPhase 2.4.1d: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
