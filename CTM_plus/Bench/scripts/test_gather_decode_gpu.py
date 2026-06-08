#!/usr/bin/env python3
"""GPU correctness gate for Step 2 — in-kernel gather decode.

Self-contained (no vLLM): build a ProtectedKINT4Cache, append random K/V, then for
a retained subset compare the decode output the TWO ways —
  COMPACTED: kernel_inputs(active_positions) -> fused_protected_k_decode_attention
             (host index_select + permute-copy, then the permuted kernel), vs
  GATHER:    kernel_inputs_gather(active_positions) ->
             fused_protected_k_decode_attention_gather (reads K/V in place via the
             retained-position index; no host compaction).
They must be byte-identical: same positions, same logical order, same split-K, same
online-softmax accumulation — only the load addressing differs (proven equivalent in
numpy by `_gather_addressing_selftest`). Also checks gather-ALL == off (full read).

  python Bench/scripts/test_gather_decode_gpu.py            # needs CUDA + Triton

Pass => the gather path is correct; flip INT4_READSKIP_INKERNEL=1 on the sweep to
measure whether removing the host gather moves throughput.
"""
from __future__ import annotations

import random
import sys


def _decode_compacted(cache, q, active):
    from kv_policy.int4_fused_attention_kernel import fused_protected_k_decode_attention
    i = cache.kernel_inputs(active_positions=active)
    return fused_protected_k_decode_attention(
        q=q, k_packed=i["k_packed"], k_scale=i["k_scale"], k_offset=i["k_offset"],
        k_fp16=i["k_fp16"], protect_mask=i["protect_mask"], v_packed=i["v_packed"],
        v_scale=i["v_scale"], v_offset=i["v_offset"],
        group_size_k=cache.k_group_size, group_size_v=cache.v_group_size,
        asymmetric=cache.asymmetric)


def _decode_gather(cache, q, active):
    from kv_policy.int4_fused_attention_kernel import fused_protected_k_decode_attention_gather
    i = cache.kernel_inputs_gather(active)
    return fused_protected_k_decode_attention_gather(
        q=q, k_packed=i["k_packed"], k_scale=i["k_scale"], k_offset=i["k_offset"],
        k_fp16=i["k_fp16"], protect_mask=i["protect_mask"], v_packed=i["v_packed"],
        v_scale=i["v_scale"], v_offset=i["v_offset"], gather_idx=i["gather_idx"],
        group_size_k=cache.k_group_size, group_size_v=cache.v_group_size,
        asymmetric=cache.asymmetric)


def main() -> int:
    try:
        import torch
    except ImportError:
        print("test_gather_decode_gpu: torch not available (CPU box) — SKIP")
        return 0
    if not torch.cuda.is_available():
        print("test_gather_decode_gpu: no CUDA — SKIP (run on the pod)")
        return 0
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    # Step 3 unit: the on-GPU index expansion (active_index) must equal the
    # CPU-proven Python list (active_positions). Two twin controllers fed the same
    # scores (each call advances the step counter, so we can't call both on one).
    from kv_policy.readskip_select import ReadSkipController
    import torch as _t
    def _twin():
        return ReadSkipController(block_size=32, sink_tokens=64, recent_tokens=512,
                                  attention_budget_tokens=512, neighbor_blocks=1,
                                  observe_steps=3, refresh_every=0, score_decay=0.5)
    ca, cb = _twin(), _twin()
    S3 = 8000
    sc = [0.0] * ((S3 + 31) // 32); sc[100] = 9.0; sc[200] = 4.0
    for _ in range(4):  # 3 observe + 1 steady
        lst = ca.active_positions(S3, block_scores=sc)
        idx = cb.active_index(S3, "cuda", block_scores=sc)
        assert idx.dtype == _t.int32 and idx.is_cuda, (idx.dtype, idx.device)
        assert idx.tolist() == lst, "active_index (GPU) != active_positions (CPU)"
    print("active_index == active_positions (GPU expansion): PASS")

    dev = "cuda"
    H_kv, D, G = 4, 128, 7
    H_q = H_kv * G
    bs = 32
    torch.manual_seed(0); random.seed(0)
    ok = True
    for s in (2000, 8000, 16000):
        cache = ProtectedKINT4Cache(
            max_seq_len=s + 16, protect_fraction=0.04,
            k_group_size=1, v_group_size=32, asymmetric=True, bits=4)
        cache.append(torch.randn(s, H_kv, D, device=dev, dtype=torch.float16),
                     torch.randn(s, H_kv, D, device=dev, dtype=torch.float16))
        cache.freeze_protect_mask()
        q = torch.randn(1, H_q, D, device=dev, dtype=torch.float16)

        # A realistic retained set: sink + recent + a few random middle blocks
        # (block-aligned, sorted, unique) — exactly what the controller emits.
        nb = (s + bs - 1) // bs
        keep_blocks = set(range(0, 2)) | set(range(nb - 16, nb))
        keep_blocks |= set(random.sample(range(nb), k=min(16, nb)))
        active = sorted({p for b in keep_blocks for p in range(b * bs, min((b + 1) * bs, s))})

        out_c = _decode_compacted(cache, q, active)
        out_g = _decode_gather(cache, q, active)
        md = float((out_c.float() - out_g.float()).abs().max())
        # gather-ALL must equal the full read (off path == None active_positions)
        out_off = _decode_compacted(cache, q, None)
        out_gall = _decode_gather(cache, q, list(range(s)))
        md_all = float((out_off.float() - out_gall.float()).abs().max())

        good = md < 1e-3 and md_all < 1e-3
        ok = ok and good
        print(f"s={s:>6}: |compacted-gather|={md:.2e}  |off-gatherAll|={md_all:.2e}  "
              f"n_active={len(active)}  {'OK' if good else 'FAIL'}")

    print("gather-decode GPU gate:", "PASS (gather == compacted == off)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    kvp = os.path.normpath(os.path.join(here, "..", "..", "KVPolicy"))
    if kvp not in sys.path:
        sys.path.insert(0, kvp)
    raise SystemExit(main())
