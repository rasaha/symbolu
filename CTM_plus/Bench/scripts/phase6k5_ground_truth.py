#!/usr/bin/env python3
# Phase 6K.5 — bf16 ground-truth three-way localizer.
#
# 6K.4 showed (a) OOB columns steal ZERO softmax mass (masked == unmasked),
# killing the OOB theory, and (b) the kernel output is orthogonal (cos 0.0)
# to a from-scratch attention built from the captured int4 tensors. That
# leaves two suspects: the kernel misreads the tensors, OR our pure-Python
# reconstruction is itself wrong (protect overlay / layout). To break the
# tie we need GROUND TRUTH.
#
# This script hooks the writer to stash the TRUE pre-quant bf16 K/V per
# layer, then at the first decode call compares THREE attention outputs for
# the same query:
#
#   TRUE   — full bf16 K/V (the gold answer; what a correct kernel must give)
#   INT4   — our dequant of the captured int4 tensors (+ protect overlay)
#   KERNEL — the real flash_attn_with_int4_kvcache output
#
# Plus raw stats (norm / nan / inf / sample) so a zero/NaN output is obvious,
# and a direct per-channel TRUE-vs-INT4 K error so we can tell whether the
# quantization itself preserves K.
#
# Verdict logic:
#   cos(KERNEL, TRUE) ~ 1                      -> kernel is fine; bug is downstream.
#   cos(INT4, TRUE) ~ 1  but KERNEL orthogonal -> kernel MISREADS the tensors
#                                                 (layout/scale/protect indexing).
#   cos(INT4, TRUE) low                        -> quantization or OUR dequant is
#                                                 wrong; inspect K error table.
#
# Run:
#   export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
#   PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k5_ground_truth.py 2>&1 | tee /tmp/phase6k5.log

import math
import os

import torch


CAPTURE = {"first_call": True, "decode_calls": 0}
# layer_idx -> list of bf16 K / V chunks appended in sequence order.
GT = {}


# ----------------------------------------------------------------------
# int4 reconstruction (same conventions as 6K.4).
# ----------------------------------------------------------------------
def _unpack_nibbles(packed_uint8):
    lo = (packed_uint8 & 0x0F).to(torch.float32)
    hi = ((packed_uint8 >> 4) & 0x0F).to(torch.float32)
    out = torch.stack([lo, hi], dim=-1)
    return out.reshape(*packed_uint8.shape[:-1], packed_uint8.shape[-1] * 2)


def _dequant_K(kw):
    k_int4 = kw["k_packed_int4"]
    k_scale = kw["k_packed_scale"].float()
    k_xmin = kw["k_packed_xmin"].float()
    G = int(kw.get("packed_group_size", 32))
    B, S, H_kv, half_D = k_int4.shape
    D = half_D * 2
    nib = _unpack_nibbles(k_int4)
    g_idx = (torch.arange(S, device=k_int4.device) // G).clamp(max=k_scale.shape[1] - 1)
    K = nib * k_scale[:, g_idx] + k_xmin[:, g_idx]
    slot = kw.get("k_packed_protect_slot")
    prot = kw.get("k_packed_protect_bf16")
    n_overlay = 0
    if slot is not None and prot is not None:
        slot = slot.long()
        prot = prot.float()
        if slot.dim() == 1:
            slot = slot.unsqueeze(0).expand(H_kv, -1)
        for h in range(H_kv):
            for d in range(D):
                s = int(slot[h, d].item())
                if s >= 0:
                    K[:, :, h, d] = prot[:, :, h, s]
                    n_overlay += 1
    return K, D, G, n_overlay


def _dequant_V(kw):
    v_int4 = kw.get("v_packed_int4")
    if v_int4 is None:
        return None
    v_scale = kw["v_packed_scale"].float()
    v_xmin = kw["v_packed_xmin"].float()
    Gv = int(kw.get("v_packed_group_size", 32))
    B, S, H_kv, half_D = v_int4.shape
    D = half_D * 2
    nib = _unpack_nibbles(v_int4)
    d_idx = (torch.arange(D, device=v_int4.device) // Gv)
    return nib * v_scale[:, :, :, d_idx] + v_xmin[:, :, :, d_idx]


def _stats(name, t):
    t = t.float()
    nan = int(torch.isnan(t).sum())
    inf = int(torch.isinf(t).sum())
    flat = t.reshape(-1)
    samp = ", ".join(f"{x:+.3f}" for x in flat[:5].tolist())
    print(f"    {name:14s} shape={tuple(t.shape)} norm={t.norm():.4f} "
          f"nan={nan} inf={inf}  [{samp} ...]")


def _cos(a, b):
    a = a.reshape(-1).float(); b = b.reshape(-1).float()
    return float(torch.dot(a, b) / (a.norm() * b.norm() + 1e-12))


def _attn(q_hd, K_shd, V_shd, scale, s_curr=None):
    """q (H_q, D); K,V (H_q, S, D). Optional length mask to s_curr."""
    scores = torch.einsum("hd,hsd->hs", q_hd, K_shd) * scale
    if s_curr is not None:
        scores = scores.clone()
        scores[:, s_curr:] = torch.finfo(scores.dtype).min
    w = torch.softmax(scores, dim=-1)
    return torch.einsum("hs,hsd->hd", w, V_shd), scores, w


def analyze(args, kwargs, kernel_out):
    q = args[0].float()
    B, Sq, H_q, D = q.shape
    s_curr = int(kwargs["cache_seqlens"][0].item())
    scale = float(kwargs.get("softmax_scale") or (1.0 / math.sqrt(D)))

    K4, Dk, G, n_overlay = _dequant_K(kwargs)          # int4 K  (B,S,H_kv,D)
    V4 = _dequant_V(kwargs)                             # int4 V
    S = K4.shape[1]; H_kv = K4.shape[2]; rep = H_q // H_kv

    print("\n" + "=" * 80)
    print("PHASE 6K.5 — bf16 GROUND-TRUTH THREE-WAY LOCALIZER")
    print("=" * 80)
    print(f"  H_q={H_q} H_kv={H_kv} rep={rep} D={D} S_max={S} s_curr={s_curr} "
          f"scale={scale:.6f} protect_overlay_dims={n_overlay}")

    # ChatGPT #1/#2: confirm we compare the real kernel out, and dump the
    # shapes/strides the kernel actually received (catches a transpose or a
    # non-contiguous view masquerading as a layout the reader misreads).
    print("\n  --- captured kernel input shapes / strides ---")
    for nm in ("k_packed_int4", "k_packed_scale", "k_packed_xmin",
               "v_packed_int4", "v_packed_scale"):
        t = kwargs.get(nm)
        if torch.is_tensor(t):
            print(f"    {nm:16s} shape={tuple(t.shape)} stride={tuple(t.stride())} "
                  f"contig={t.is_contiguous()}")
    print(f"    {'query(args0)':16s} shape={tuple(args[0].shape)} "
          f"stride={tuple(args[0].stride())} contig={args[0].is_contiguous()}")

    # ---- locate the bf16 ground truth for this layer (first call = layer 0) ----
    gt_layer, trueK, trueV = None, None, None
    for li in sorted(GT.keys()):
        kk = torch.cat([c[0] for c in GT[li]], dim=0)   # (seq_pos, H_kv, D)
        if kk.shape[0] >= s_curr:
            gt_layer = li
            trueK = kk[:s_curr].float()
            trueV = torch.cat([c[1] for c in GT[li]], dim=0)[:s_curr].float()
            break
    print(f"  ground-truth layer picked = {gt_layer} "
          f"(captured layers: {sorted(GT.keys())[:5]}{'...' if len(GT)>5 else ''})")

    qh = q[0, 0]                                        # (H_q, D)

    # ---- INT4 reconstruction attention (length-masked = correct masking) ----
    K4e = K4[0].repeat_interleave(rep, dim=1).permute(1, 0, 2)   # (H_q, S, D)
    V4e = V4[0].repeat_interleave(rep, dim=1).permute(1, 0, 2) if V4 is not None else None
    out_int4 = None
    if V4e is not None:
        out_int4, _, _ = _attn(qh, K4e, V4e, scale, s_curr=s_curr)

    # ---- TRUE bf16 attention ----
    out_true = None
    if trueK is not None and trueV is not None:
        tKe = trueK.repeat_interleave(rep, dim=1).permute(1, 0, 2)   # (H_q, s_curr, D)
        tVe = trueV.repeat_interleave(rep, dim=1).permute(1, 0, 2)
        out_true, _, _ = _attn(qh, tKe, tVe, scale, s_curr=None)

    # ---- kernel output ----
    ko = None
    if torch.is_tensor(kernel_out):
        ko = kernel_out.float().reshape(-1, D)[:H_q]

    print("\n  --- raw output stats (explains any cos=0.0) ---")
    if ko is not None: _stats("KERNEL", ko)
    if out_int4 is not None: _stats("INT4", out_int4)
    if out_true is not None: _stats("TRUE", out_true)

    # ---- per-channel K fidelity: does the quantization preserve K? ----
    if trueK is not None:
        k4_valid = K4[0, :s_curr].float()               # (s_curr, H_kv, D)
        err = (k4_valid - trueK)
        rel = err.norm() / (trueK.norm() + 1e-12)
        print("\n  --- K fidelity: INT4-dequant vs TRUE bf16 (tokens 0..s_curr-1) ---")
        print(f"    ||K_int4 - K_true|| / ||K_true|| = {float(rel):.4f}")
        # worst channels
        per_ch = err.abs().mean(dim=0)                  # (H_kv, D)
        tv, ti = per_ch.reshape(-1).topk(5)
        for v, i in zip(tv.tolist(), ti.tolist()):
            h, d = i // D, i % D
            print(f"      h={h:2d} d={d:3d}  mean|err|={v:.3f}  "
                  f"K_true[0]={trueK[0, h, d]:+.3f} K_int4[0]={k4_valid[0, h, d]:+.3f}")

    print("\n  --- pairwise cosine ---")
    if ko is not None and out_true is not None:
        print(f"    cos(KERNEL, TRUE) = {_cos(ko, out_true):+.4f}")
    if out_int4 is not None and out_true is not None:
        print(f"    cos(INT4,   TRUE) = {_cos(out_int4, out_true):+.4f}")
    if ko is not None and out_int4 is not None:
        print(f"    cos(KERNEL, INT4) = {_cos(ko, out_int4):+.4f}")

    # ChatGPT #3: GQA mapping sweep. If MY reference just uses the wrong
    # q->kv mapping, one of these will jump to ~1.0 vs the kernel and the
    # "kernel is wrong" conclusion would be a false alarm. If none do, the
    # disagreement is real (kernel misreads the data).
    if ko is not None and trueK is not None and trueV is not None:
        print("\n  --- GQA mapping sweep: cos(KERNEL, TRUE) under each map ---")
        maps = {
            "q//rep (standard)": (torch.arange(H_q, device=q.device) // rep),
            "q%H_kv (interleave)": (torch.arange(H_q, device=q.device) % H_kv),
        }
        for label, midx in maps.items():
            tKe = trueK[:, midx, :].permute(1, 0, 2)    # (H_q, s_curr, D)
            tVe = trueV[:, midx, :].permute(1, 0, 2)
            o_map, _, _ = _attn(qh, tKe, tVe, scale, s_curr=None)
            print(f"    {label:24s} cos(KERNEL,TRUE)={_cos(ko, o_map):+.4f}")

    print("\n  VERDICT:")
    c_kt = _cos(ko, out_true) if (ko is not None and out_true is not None) else None
    c_it = _cos(out_int4, out_true) if (out_int4 is not None and out_true is not None) else None
    if c_kt is not None and c_kt > 0.9:
        print("    >>> KERNEL ~= TRUE: attention is correct. Bug is downstream")
        print("        (sampling, a later layer, or only SOME calls corrupt).")
    elif c_it is not None and c_it > 0.9 and (c_kt is None or c_kt < 0.5):
        print("    >>> INT4 reconstruction ~= TRUE, but KERNEL is orthogonal.")
        print("        The quantized data FAITHFULLY represents K/V, so the writer")
        print("        is fine -- the KERNEL is MISREADING the tensors. Suspect the")
        print("        K scale/xmin index formula or the protect-slot indexing")
        print("        (e.g. (H_kv,D) laid out but read 'by d only'), which corrupts")
        print("        the dominant protected channels. Dump the kernel's first-token")
        print("        dequant K[t=0,h=0,:8] and compare to TRUE above.")
    elif c_it is not None and c_it < 0.5:
        print("    >>> INT4 reconstruction does NOT match TRUE. Either the")
        print("        quantization destroys the signal (check K fidelity table)")
        print("        or our protect overlay convention is wrong. If K-fidelity")
        print("        rel-err is large, the writer's quant/protect is the bug.")
    else:
        print("    >>> Mixed signal -- read the cosines + stats above.")
    print("=" * 80 + "\n", flush=True)


def install_hooks():
    # ---- writer hooks: stash true bf16 K/V per layer in sequence order ----
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    _orig_write = PagedKVWriter.write
    _orig_decode = PagedKVWriter.write_decode_batched

    def write(self, key, value, kv_cache, slot_mapping, *a, **k):
        try:
            GT.setdefault(self.layer_idx, []).append(
                (key.detach().float(), value.detach().float()))
        except Exception:
            pass
        return _orig_write(self, key, value, kv_cache, slot_mapping, *a, **k)

    def write_decode_batched(self, key, value, kv_cache, slot_mapping, slot_idx_t, *a, **k):
        try:
            GT.setdefault(self.layer_idx, []).append(
                (key.detach().float(), value.detach().float()))
        except Exception:
            pass
        return _orig_decode(self, key, value, kv_cache, slot_mapping, slot_idx_t, *a, **k)

    PagedKVWriter.write = write
    PagedKVWriter.write_decode_batched = write_decode_batched

    # ---- kernel wrap ----
    from vllm import vllm_flash_attn
    real_fn = vllm_flash_attn.flash_attn_with_int4_kvcache

    def wrapped(*args, **kwargs):
        CAPTURE["decode_calls"] += 1
        out = real_fn(*args, **kwargs)
        if CAPTURE["first_call"]:
            CAPTURE["first_call"] = False
            try:
                analyze(args, kwargs, out)
            except Exception as e:
                import traceback
                print(f"[6k5] analysis failed: {type(e).__name__}: {e}")
                traceback.print_exc()
        return out

    vllm_flash_attn.flash_attn_with_int4_kvcache = wrapped
    from vllm.vllm_flash_attn import flash_attn_interface
    flash_attn_interface.flash_attn_with_int4_kvcache = wrapped
    print("[patch] writer + kernel hooks installed (6K.5).", flush=True)


def main():
    install_hooks()
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    print("\n[run] Loading Qwen2.5-7B-Instruct (eager)...", flush=True)
    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct",
        max_model_len=8192, gpu_memory_utilization=0.5,
        max_num_seqs=8, enforce_eager=True,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=4)
    print("\n[run] generate() with N=8 prompt...", flush=True)
    out = llm.generate(["List three primary colors and their names."], sp)
    print(f"\n[run] Output text: {out[0].outputs[0].text!r}")
    print(f"[run] Total decode kernel calls: {CAPTURE['decode_calls']}")


if __name__ == "__main__":
    main()
