#!/usr/bin/env python3
# Phase 6K.3 — tensor-level round-trip diagnostic for int4_packed K/V path.
#
# Monkey-patches flash_attn_with_int4_kvcache to capture all incoming
# tensors, reports their shapes/layouts vs the reader's expectations,
# performs a pure-Python dequant of K[0..s_curr-1] and V[0..s_curr-1],
# and checks for NaN/Inf and OOB-zero invariants.
#
# Run:
#   PHASE6E_FUSED_WRITER=0 python phase6k3_tensor_diagnostic.py 2>&1 | tee /tmp/phase6k3.log

import os
import sys
import math
import torch
import numpy as np


READER_EXPECT = {
    # All shapes are (B, S_max, ...) layouts. The reader's indexing
    # formulas are from int4_packed_load.h lines 213-217 (K scale) and
    # 384-385 (V scale).
    'k_packed_int4':       '(B, S_max,        H_kv, kPackedBytesPerToken=D/2)',
    'k_packed_scale':      '(B, S_max/G,      H_kv, D)            # READER: global_g * H_kv * D + bidh * D + d',
    'k_packed_xmin':       '(B, S_max/G,      H_kv, D)            # READER: same as scale',
    'k_packed_protect_bf16': '(B, S_max,       H_kv, n_protect)   # READER: global_t * H_kv * n_protect + bidh * n_protect + slot',
    'k_packed_protect_slot': '(H_kv,           D) int8            # READER: indexed by d only',
    'v_packed_int4':       '(B, S_max,        H_kv, D/2)',
    'v_packed_scale':      '(B, S_max,        H_kv, kVGroupsPerToken=D/Gv)  # READER: global_t * H_kv * kVGroups + bidh * kVGroups + g',
    'v_packed_xmin':       '(B, S_max,        H_kv, kVGroupsPerToken)',
}


def dump_tensor(name, t):
    """Pretty-print a tensor's shape and a couple of summary stats."""
    if t is None:
        print(f"  {name:30s} None")
        return
    if not torch.is_tensor(t):
        print(f"  {name:30s} {type(t).__name__} = {t!r}")
        return
    s = list(t.shape)
    dtype = str(t.dtype).split('.')[-1]
    dev = str(t.device)
    n_nan = torch.isnan(t).sum().item() if t.is_floating_point() else 0
    n_inf = torch.isinf(t).sum().item() if t.is_floating_point() else 0
    if t.is_floating_point():
        t_min = t.float().min().item() if t.numel() else 0.0
        t_max = t.float().max().item() if t.numel() else 0.0
        t_abs_mean = t.float().abs().mean().item() if t.numel() else 0.0
        stats = f"min={t_min:+.3e} max={t_max:+.3e} |mean|={t_abs_mean:.3e} nan={n_nan} inf={n_inf}"
    else:
        t_min = t.min().item() if t.numel() else 0
        t_max = t.max().item() if t.numel() else 0
        stats = f"min={t_min} max={t_max}"
    contig = "C" if t.is_contiguous() else "NC"
    print(f"  {name:30s} {s!s:30s} {dtype:8s} {dev:7s} [{contig}] {stats}")


CAPTURE = {"first_call": True, "decode_calls": 0}


def install_patch():
    """Monkey-patch flash_attn_with_int4_kvcache to dump first call."""
    from vllm import vllm_flash_attn
    real_fn = vllm_flash_attn.flash_attn_with_int4_kvcache

    def wrapped(*args, **kwargs):
        CAPTURE["decode_calls"] += 1
        # Capture only the first decode call to keep output manageable.
        if CAPTURE["first_call"]:
            CAPTURE["first_call"] = False
            print("\n" + "=" * 80)
            print(f"flash_attn_with_int4_kvcache CALL #1 (capturing)")
            print("=" * 80)
            print("\n--- positional args ---")
            for i, a in enumerate(args):
                dump_tensor(f"args[{i}]", a)
            print("\n--- keyword args ---")
            for k in sorted(kwargs.keys()):
                dump_tensor(k, kwargs[k])

            # Layout analysis
            print("\n" + "-" * 80)
            print("READER EXPECTED LAYOUTS (from int4_packed_load.h):")
            print("-" * 80)
            for name, layout in READER_EXPECT.items():
                t = kwargs.get(name)
                got = list(t.shape) if torch.is_tensor(t) else "MISSING"
                print(f"  {name:28s} got={got!s:35s} expect={layout}")

            # Pure-Python K dequant for token 0, head 0
            print("\n" + "-" * 80)
            print("K DEQUANT ROUND-TRIP (token=0, head=0, first 4 dims):")
            print("-" * 80)
            try:
                k_int4    = kwargs['k_packed_int4']
                k_scale   = kwargs['k_packed_scale']
                k_xmin    = kwargs['k_packed_xmin']
                k_group_size = kwargs.get('packed_group_size', 32)
                # Layout assumption: (B, S_max, H_kv, D/2) for k_int4,
                # (B, S_max/G, H_kv, D) for scale/xmin.
                B, S_max = k_int4.shape[0], k_int4.shape[1]
                H_kv = k_int4.shape[2]
                pbytes = k_int4.shape[3]
                D = pbytes * 2
                n_groups = S_max // k_group_size
                print(f"  Inferred B={B} S_max={S_max} H_kv={H_kv} D={D} G={k_group_size} n_groups={n_groups}")
                if list(k_scale.shape) != [B, n_groups, H_kv, D]:
                    print(f"  !! K SCALE SHAPE MISMATCH: got {list(k_scale.shape)}, expected [B={B}, n_groups={n_groups}, H_kv={H_kv}, D={D}]")
                if list(k_xmin.shape) != [B, n_groups, H_kv, D]:
                    print(f"  !! K XMIN SHAPE MISMATCH:  got {list(k_xmin.shape)}, expected [B={B}, n_groups={n_groups}, H_kv={H_kv}, D={D}]")

                # Dequant K[batch=0, token=0, head=0, d=0..3]
                # group_idx = token // G = 0
                # scale[0, 0, 0, d] = k_scale[0, 0, 0, d]
                # nibble = k_int4[0, 0, 0, d/2] (low 4 bits if d even, high 4 if d odd)
                # x = nibble * scale + xmin
                for d in range(min(8, D)):
                    byte = int(k_int4[0, 0, 0, d // 2].item())
                    nibble = (byte & 0x0F) if (d % 2 == 0) else ((byte >> 4) & 0x0F)
                    s = float(k_scale[0, 0, 0, d].item())
                    x = float(k_xmin[0, 0, 0, d].item())
                    val = nibble * s + x
                    print(f"  K[t=0, h=0, d={d}]: nibble={nibble:2d} scale={s:+.4e} xmin={x:+.4e}  ->  K={val:+.4f}")

                # Check OOB invariant: K[t=10, h=0, d=0] should be 0 if s_curr=8
                cache_seqlens = kwargs.get('cache_seqlens')
                if cache_seqlens is not None:
                    s_curr = int(cache_seqlens[0].item())
                    print(f"\n  cache_seqlens[0] = s_curr = {s_curr}")
                    if s_curr < 32:
                        # Check tokens past s_curr — they should be zero-quantized
                        # OR scales should be zero for groups past s_curr / G.
                        oob_token = s_curr + 2
                        oob_group = oob_token // k_group_size
                        if oob_group >= n_groups:
                            print(f"  oob_group {oob_group} >= n_groups {n_groups}, skipping OOB check")
                        else:
                            oob_byte = int(k_int4[0, oob_token, 0, 0].item())
                            oob_scale = float(k_scale[0, oob_group, 0, 0].item())
                            oob_xmin = float(k_xmin[0, oob_group, 0, 0].item())
                            print(f"  OOB CHECK at t={oob_token} (s_curr={s_curr}):")
                            print(f"    k_int4[0, {oob_token}, 0, 0] = {oob_byte} (expect 0)")
                            print(f"    k_scale[0, {oob_group}, 0, 0] = {oob_scale:+.4e} (expect 0)")
                            print(f"    k_xmin[0, {oob_group}, 0, 0] = {oob_xmin:+.4e} (expect 0)")
            except Exception as e:
                print(f"  Dequant trace FAILED: {type(e).__name__}: {e}")
                import traceback; traceback.print_exc()

            print("\n" + "-" * 80)
            print("V DEQUANT ROUND-TRIP (token=0, head=0, first 4 dims):")
            print("-" * 80)
            try:
                v_int4 = kwargs.get('v_packed_int4')
                v_scale = kwargs.get('v_packed_scale')
                v_xmin = kwargs.get('v_packed_xmin')
                v_group_size = kwargs.get('v_packed_group_size', 32)
                if v_int4 is None:
                    print("  v_packed_int4 is None — V is BF16, not int4. Skipping.")
                else:
                    B, S_max = v_int4.shape[0], v_int4.shape[1]
                    H_kv = v_int4.shape[2]
                    pbytes = v_int4.shape[3]
                    D = pbytes * 2
                    n_vgroups_per_token = D // v_group_size
                    print(f"  Inferred B={B} S_max={S_max} H_kv={H_kv} D={D} Gv={v_group_size} kVGroupsPerToken={n_vgroups_per_token}")
                    if list(v_scale.shape) != [B, S_max, H_kv, n_vgroups_per_token]:
                        print(f"  !! V SCALE SHAPE MISMATCH: got {list(v_scale.shape)}, expected [B={B}, S_max={S_max}, H_kv={H_kv}, kVGroups={n_vgroups_per_token}]")
                    if list(v_xmin.shape) != [B, S_max, H_kv, n_vgroups_per_token]:
                        print(f"  !! V XMIN SHAPE MISMATCH:  got {list(v_xmin.shape)}, expected [B={B}, S_max={S_max}, H_kv={H_kv}, kVGroups={n_vgroups_per_token}]")
                    for d in range(min(8, D)):
                        byte = int(v_int4[0, 0, 0, d // 2].item())
                        nibble = (byte & 0x0F) if (d % 2 == 0) else ((byte >> 4) & 0x0F)
                        g = d // v_group_size
                        s = float(v_scale[0, 0, 0, g].item())
                        x = float(v_xmin[0, 0, 0, g].item())
                        val = nibble * s + x
                        print(f"  V[t=0, h=0, d={d}, g={g}]: nibble={nibble:2d} scale={s:+.4e} xmin={x:+.4e}  ->  V={val:+.4f}")
            except Exception as e:
                print(f"  Dequant trace FAILED: {type(e).__name__}: {e}")

            print("=" * 80 + "\n", flush=True)

        return real_fn(*args, **kwargs)

    vllm_flash_attn.flash_attn_with_int4_kvcache = wrapped
    # Also patch the alias used elsewhere
    from vllm.vllm_flash_attn import flash_attn_interface
    flash_attn_interface.flash_attn_with_int4_kvcache = wrapped
    print("[patch] flash_attn_with_int4_kvcache wrapped.", flush=True)


def main():
    install_patch()

    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    print("\n[run] Loading Qwen2.5-7B-Instruct (eager, no CUDA graph)...", flush=True)
    llm = Int4ProtectedLLM(
        model='Qwen/Qwen2.5-7B-Instruct',
        max_model_len=8192,
        gpu_memory_utilization=0.5,
        max_num_seqs=8,
        enforce_eager=True,  # eager mode keeps things simple to inspect
    )
    sp = SamplingParams(temperature=0.0, max_tokens=4)
    print("\n[run] Calling generate() with N=8 prompt (will dump first decode call)...", flush=True)
    out = llm.generate(['List three primary colors and their names.'], sp)
    print(f"\n[run] Output text: {out[0].outputs[0].text!r}")
    print(f"[run] Total decode kernel calls: {CAPTURE['decode_calls']}")


if __name__ == '__main__':
    main()
