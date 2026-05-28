#!/usr/bin/env python3
# Phase 6K.4 — attention-level localizer for the int4_packed garbage bug.
#
# 6K.3 proved the writer's (nibble, scale, xmin) triple is self-consistent and
# the layouts are correct, yet decode is garbage. This script answers the next
# question DIRECTLY, from the exact tensors the kernel receives, with NO kernel
# rebuild required:
#
#   Is the corruption caused by out-of-bounds (t >= cache_seqlens) columns
#   getting non-zero softmax weight because their attention SCORE is ~0
#   (exp(0)=1) rather than -inf?
#
# It reconstructs K (int4 dequant + protect overlay) and V (int4 dequant) for
# ALL S_max positions from the captured tensors, then computes the decode
# attention TWO ways for the first decode call:
#
#   (a) MASKED   — scores for positions >= s_curr set to -inf  (CORRECT kernel)
#   (b) UNMASKED — all S_max positions included                (kernel w/o the
#                  length mask in the score step)
#
# and compares both against the REAL kernel output. The headline number is
# `oob_softmax_mass`: the fraction of softmax weight landing on t >= s_curr
# when scores are not masked. If that's large and kernel ~= UNMASKED while
# MASKED is coherent, the bug is the kernel's score-mask control flow for the
# int4_packed path — NOT the writer, and NOT "non-zero OOB K" (which is already
# ~0; see 6K.3).
#
# Run:
#   export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
#   PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k4_attention_localizer.py 2>&1 | tee /tmp/phase6k4.log

import math
import os

import torch


CAPTURE = {"first_call": True, "decode_calls": 0}


def _unpack_nibbles(packed_uint8):
    """(..., D/2) uint8 -> (..., D) float nibbles. Even d = low nibble of
    byte d/2, odd d = high nibble — matches the writer's pack:
        packed = (q[..., 0::2] & 0xF) | ((q[..., 1::2] & 0xF) << 4)
    """
    lo = (packed_uint8 & 0x0F).to(torch.float32)
    hi = ((packed_uint8 >> 4) & 0x0F).to(torch.float32)
    out = torch.stack([lo, hi], dim=-1)               # (..., D/2, 2)
    return out.reshape(*packed_uint8.shape[:-1], packed_uint8.shape[-1] * 2)


def _dequant_K(kw):
    """Reconstruct K[B, S, H_kv, D] from the captured packed tensors,
    including the protect overlay. Returns (K, s_curr, group_size)."""
    k_int4 = kw["k_packed_int4"]                      # (B, S, H_kv, D/2) uint8
    k_scale = kw["k_packed_scale"].float()            # (B, S/G, H_kv, D)
    k_xmin = kw["k_packed_xmin"].float()              # (B, S/G, H_kv, D)
    G = int(kw.get("packed_group_size", 32))
    B, S, H_kv, half_D = k_int4.shape
    D = half_D * 2

    nib = _unpack_nibbles(k_int4)                     # (B, S, H_kv, D)
    g_idx = (torch.arange(S, device=k_int4.device) // G)
    g_idx = g_idx.clamp(max=k_scale.shape[1] - 1)
    scale_t = k_scale[:, g_idx]                       # (B, S, H_kv, D)
    xmin_t = k_xmin[:, g_idx]                         # (B, S, H_kv, D)
    K = nib * scale_t + xmin_t                        # (B, S, H_kv, D)

    # Protect overlay: where protect_slot[h, d] = s >= 0, the true value is
    # k_packed_protect_bf16[b, t, h, s]. (Writer-consistent (H_kv, D) read.)
    slot = kw.get("k_packed_protect_slot")
    prot = kw.get("k_packed_protect_bf16")
    if slot is not None and prot is not None:
        slot = slot.long()                            # (H_kv, D)
        prot = prot.float()                           # (B, S, H_kv, n_protect)
        if slot.dim() == 1:                           # "indexed by d only" variant
            slot = slot.unsqueeze(0).expand(H_kv, -1)
        for h in range(H_kv):
            for d in range(D):
                s = int(slot[h, d].item())
                if s >= 0:
                    K[:, :, h, d] = prot[:, :, h, s]
    return K, D, G


def _dequant_V(kw):
    """Reconstruct V[B, S, H_kv, D] from captured packed tensors."""
    v_int4 = kw.get("v_packed_int4")
    if v_int4 is None:
        return None
    v_scale = kw["v_packed_scale"].float()            # (B, S, H_kv, n_vg)
    v_xmin = kw["v_packed_xmin"].float()
    Gv = int(kw.get("v_packed_group_size", 32))
    B, S, H_kv, half_D = v_int4.shape
    D = half_D * 2
    nib = _unpack_nibbles(v_int4)                     # (B, S, H_kv, D)
    d_idx = (torch.arange(D, device=v_int4.device) // Gv)
    scale_t = v_scale[:, :, :, d_idx]                 # (B, S, H_kv, D)
    xmin_t = v_xmin[:, :, :, d_idx]
    return nib * scale_t + xmin_t


def _cos(a, b):
    a = a.reshape(-1).float()
    b = b.reshape(-1).float()
    return float(torch.dot(a, b) / (a.norm() * b.norm() + 1e-12))


def analyze(args, kwargs, kernel_out):
    q = args[0].float()                               # (B, Sq, H_q, D)
    B, Sq, H_q, D = q.shape
    s_curr = int(kwargs["cache_seqlens"][0].item())
    scale = float(kwargs.get("softmax_scale") or (1.0 / math.sqrt(D)))

    K, Dk, G = _dequant_K(kwargs)                      # (B, S, H_kv, D)
    V = _dequant_V(kwargs)                             # (B, S, H_kv, D)
    S = K.shape[1]
    H_kv = K.shape[2]
    rep = H_q // H_kv                                  # GQA group size

    print("\n" + "=" * 80)
    print("PHASE 6K.4 — ATTENTION-LEVEL LOCALIZER")
    print("=" * 80)
    print(f"  B={B} Sq={Sq} H_q={H_q} H_kv={H_kv} (GQA rep={rep}) D={D}")
    print(f"  S_max={S}  s_curr(cache_seqlens)={s_curr}  "
          f"OOB columns in buffer = {S - s_curr}")
    print(f"  softmax_scale={scale:.6f}  group_size={G}")
    if V is None:
        print("  V is bf16 (no v_packed_int4); attention-output test skipped.")

    # Expand kv heads -> q heads.
    K_e = K.repeat_interleave(rep, dim=2)              # (B, S, H_q, D)
    V_e = V.repeat_interleave(rep, dim=2) if V is not None else None

    # Scores for the single decode query against all S cached positions.
    qh = q[0, 0]                                       # (H_q, D)
    kh = K_e[0].permute(1, 0, 2)                       # (H_q, S, D)
    scores = torch.einsum("hd,hsd->hs", qh, kh) * scale   # (H_q, S)

    neg_inf = torch.finfo(scores.dtype).min
    masked = scores.clone()
    masked[:, s_curr:] = neg_inf

    w_unmasked = torch.softmax(scores, dim=-1)         # (H_q, S)
    w_masked = torch.softmax(masked, dim=-1)

    oob_mass = w_unmasked[:, s_curr:].sum(dim=-1)      # (H_q,)
    print("\n  --- OOB softmax mass (UNMASKED scores; the smoking gun) ---")
    print(f"    mean over heads = {oob_mass.mean().item():.4f}")
    print(f"    max  over heads = {oob_mass.max().item():.4f}")
    print(f"    min  over heads = {oob_mass.min().item():.4f}")
    print("    (Correct attention puts 0.0 mass here. Anything large means the")
    print("     zero-score OOB columns are stealing weight -> denominator")
    print("     inflation -> attenuated output in every layer.)")

    if V_e is not None:
        vh = V_e[0].permute(1, 0, 2)                   # (H_q, S, D)
        out_masked = torch.einsum("hs,hsd->hd", w_masked, vh)     # (H_q, D)
        out_unmasked = torch.einsum("hs,hsd->hd", w_unmasked, vh)
        print("\n  --- reference attention output: MASKED vs UNMASKED ---")
        print(f"    cos(masked, unmasked)      = {_cos(out_masked, out_unmasked):.4f}")
        rel = (out_unmasked - out_masked).norm() / (out_masked.norm() + 1e-12)
        print(f"    ||unmasked-masked||/||m||  = {float(rel):.4f}")

        if torch.is_tensor(kernel_out):
            ko = kernel_out.float().reshape(H_q, D) if kernel_out.numel() == H_q * D \
                else kernel_out.float().reshape(-1, D)[:H_q]
            cm = _cos(ko, out_masked)
            cu = _cos(ko, out_unmasked)
            print("\n  --- REAL KERNEL output vs references ---")
            print(f"    cos(kernel, MASKED  ref) = {cm:.4f}   <- ~1.0 => kernel is correct")
            print(f"    cos(kernel, UNMASKED ref)= {cu:.4f}   <- ~1.0 => kernel skips score mask")
            print("\n  VERDICT:")
            if cu > cm + 0.05 and oob_mass.mean().item() > 0.05:
                print("    >>> Kernel matches the UNMASKED reference and OOB mass is")
                print("        significant. The int4_packed path is NOT masking OOB")
                print("        attention SCORES to -inf. Zeroing OOB K (6K/6K.1/6K.2)")
                print("        CANNOT fix this: K~=0 still gives score 0 and exp(0)=1.")
                print("        FIX: apply col>=actual_seqlen_k -> -inf in the SCORE step")
                print("        of the int4_packed path (unconditionally, not gated on")
                print("        the bf16 path's n_block/Is_even_MN short-seq condition).")
            elif cm > cu + 0.05:
                print("    >>> Kernel matches the MASKED reference: OOB masking is fine.")
                print("        The corruption is elsewhere (dequant math, protect")
                print("        indexing, or GQA/head mapping). Re-check those.")
            else:
                print("    >>> Inconclusive: kernel matches neither reference cleanly.")
                print("        Likely a dequant/protect/layout mismatch between this")
                print("        reference and the kernel. Inspect per-head scores.")
    print("=" * 80 + "\n", flush=True)


def install_patch():
    from vllm import vllm_flash_attn
    real_fn = vllm_flash_attn.flash_attn_with_int4_kvcache

    # Stale-build check (ChatGPT's suggestion): show the loaded .so + mtime so
    # a not-rebuilt kernel is obvious.
    try:
        import vllm.vllm_flash_attn.flash_attn_interface as fai
        so = getattr(fai, "__file__", "?")
        print(f"[patch] flash_attn_interface module: {so}")
        for cand in (so, so.replace('.py', '') + '_C.so'):
            if os.path.exists(cand):
                import time as _t
                mt = os.path.getmtime(cand)
                print(f"[patch]   {cand}  mtime={_t.ctime(mt)}")
    except Exception as e:
        print(f"[patch] (.so introspection failed: {e})")

    def wrapped(*args, **kwargs):
        CAPTURE["decode_calls"] += 1
        out = real_fn(*args, **kwargs)
        if CAPTURE["first_call"]:
            CAPTURE["first_call"] = False
            try:
                analyze(args, kwargs, out)
            except Exception as e:
                import traceback
                print(f"[6k4] analysis failed: {type(e).__name__}: {e}")
                traceback.print_exc()
        return out

    vllm_flash_attn.flash_attn_with_int4_kvcache = wrapped
    from vllm.vllm_flash_attn import flash_attn_interface
    flash_attn_interface.flash_attn_with_int4_kvcache = wrapped
    print("[patch] flash_attn_with_int4_kvcache wrapped (6K.4 localizer).", flush=True)


def main():
    install_patch()
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    print("\n[run] Loading Qwen2.5-7B-Instruct (eager, no CUDA graph)...", flush=True)
    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct",
        max_model_len=8192,
        gpu_memory_utilization=0.5,
        max_num_seqs=8,
        enforce_eager=True,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=4)
    print("\n[run] generate() with N=8 prompt (analyzes first decode call)...", flush=True)
    out = llm.generate(["List three primary colors and their names."], sp)
    print(f"\n[run] Output text: {out[0].outputs[0].text!r}")
    print(f"[run] Total decode kernel calls: {CAPTURE['decode_calls']}")


if __name__ == "__main__":
    main()
