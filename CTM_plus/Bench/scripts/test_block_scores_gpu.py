#!/usr/bin/env python3
"""GPU correctness gate for Step 1 — kernel-emitted read-skip block scores.

Self-contained (no vLLM): build a ProtectedKINT4Cache, append random K/V, then
compare ProtectedKINT4Cache.block_attention_scores the TWO ways —
  use_kernel=False  -> the torch reconstruction (the reference), and
  use_kernel=True   -> the fused Triton pass (fused_protected_k_block_scores).
They must agree. What actually matters for read-skip is the SELECTION (top-budget
blocks), so we check both the numeric max-diff AND the top-k block overlap.

The math is already proven equal in numpy on CPU
(`python kv_policy/int4_fused_attention_kernel.py`); this gate confirms the Triton
implementation matches on the real int4 buffers. Run on the pod:

  python Bench/scripts/test_block_scores_gpu.py            # needs CUDA + Triton

Pass => flip INT4_READSKIP_KERNEL_SCORES=1 on the --ab / sweep runs.
"""
from __future__ import annotations

import sys


def main() -> int:
    import numpy as np
    try:
        import torch
    except ImportError:
        print("test_block_scores_gpu: torch not available (CPU box) — SKIP")
        return 0
    if not torch.cuda.is_available():
        print("test_block_scores_gpu: no CUDA — SKIP (run on the pod)")
        return 0
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    dev = "cuda"
    H_kv, D, G = 4, 128, 7          # Qwen2.5-7B-ish (4 KV heads, head_dim 128, GQA 7)
    H_q = H_kv * G
    bs = 32                          # read-skip block size
    torch.manual_seed(0)
    ok = True
    for s in (200, 2000, 8000, 16000):
        cache = ProtectedKINT4Cache(
            max_seq_len=s + 16, protect_fraction=0.04,
            k_group_size=1, v_group_size=32, asymmetric=True, bits=4)
        k = torch.randn(s, H_kv, D, device=dev, dtype=torch.float16)
        v = torch.randn(s, H_kv, D, device=dev, dtype=torch.float16)
        cache.append(k, v)
        cache.freeze_protect_mask()
        q = torch.randn(H_q, D, device=dev, dtype=torch.float16)

        ref = np.array(cache.block_attention_scores(q, bs, use_kernel=False))
        ker = np.array(cache.block_attention_scores(q, bs, use_kernel=True))
        if ref.shape != ker.shape:
            print(f"s={s}: SHAPE MISMATCH ref={ref.shape} ker={ker.shape}")
            ok = False
            continue
        maxdiff = float(np.abs(ref - ker).max())
        # Selection agreement: do the two rank the same top blocks? (what read-skip uses)
        topn = min(8, ref.shape[0])
        top_ref = set(np.argsort(ref)[-topn:])
        top_ker = set(np.argsort(ker)[-topn:])
        overlap = len(top_ref & top_ker)
        mass = float(ref.sum())  # ~ H_kv (each head's probs sum to 1)
        good = maxdiff < 5e-3 and overlap == topn
        ok = ok and good
        print(f"s={s:>6}: maxdiff={maxdiff:.2e}  top{topn}_overlap={overlap}/{topn}  "
              f"sum(ref)={mass:.3f}  {'OK' if good else 'FAIL'}")

    print("block-scores GPU gate:", "PASS (kernel == torch)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    # repo layout: make kv_policy importable when run from CTM_plus/.
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    kvp = os.path.normpath(os.path.join(here, "..", "..", "KVPolicy"))
    if kvp not in sys.path:
        sys.path.insert(0, kvp)
    raise SystemExit(main())
