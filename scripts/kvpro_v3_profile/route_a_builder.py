#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part A: Route-A packed-input builder, from the PRODUCTION writer contract.

Builds the writer's `view` dict (the exact packed KV the decode read path consumes) from fp K/V + the
frozen protect mask, using the in-repo authoritative spec `phase6f_read_fusion` (which mirrors
phase5b_4c_paged_writer.get_packed_view + _splice_k_partial_tail). NOT a simplified layout — every field
below is produced with the writer's own quant/pack. The paged layout is PADDED to n_blocks*BS (as the real
cache allocates full BS-token blocks) with seqlens / partial-tail metadata, so the read_fusion dequant
references (which require S == n_blocks*BS) consume it directly.

Field provenance (source: phase5b_4c_paged_writer.py _lazy_alloc / get_packed_view_batched, and
phase6f_read_fusion.py):
  k_int4  (1,S,H,D/2) uint8   packed unsigned nibbles (low=even d, high=odd d)   [RF.pack_nibbles]
  v_int4  (1,S,H,D/2) uint8   packed V nibbles                                   [RF.pack_nibbles]
  k_scale (1,n_blocks,H,D)    per-BLOCK K scale = (amax-amin)/15                  [RF.quantize_k_block]
  k_xmin  (1,n_blocks,H,D)    per-BLOCK K xmin                                    [RF.quantize_k_block]
  v_scale (1,S,H,v_n_groups)  per-TOKEN per-group V scale = (amax-amin)/15        [writer V pack]
  v_xmin  (1,S,H,v_n_groups)  per-TOKEN per-group V xmin                          [writer V pack]
  k_protect_bf16 (1,S,H,n_protect)  protected-K sidecar values                    [k_protect_ext]
  protect_slot (H,D) int8     slot in [0,n_protect) or -1                         [_build_protect_tables]
  block_table (1,n_blocks) int32; seqlens (1,) int32; active_in_last_block int    [decode_meta.block_tables]
  group_size=BS; v_group_size; H_kv=H; D; v_n_groups                              [writer geometry]
"""
from __future__ import annotations

import math
import os
import sys

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "CTM_plus", "KVPolicy", "kv_policy"))     # phase6f_read_fusion
sys.path.insert(0, os.path.join(_ROOT, "experiments", "kvpro_v3_symmetric_residual"))  # protected_int8
import phase6f_read_fusion as RF     # noqa: E402  (writer's pack/quant/dequant spec)


def build_protect_tables(mask_hd: torch.Tensor):
    """Mirror phase5b_4c_paged_writer._build_protect_tables: (H,D) mask -> (protect_slot (H,D) int8 in
    [0,n_protect) or -1, n_protect, per-head sorted protected-d indices)."""
    H, D = mask_hd.shape
    m = mask_hd.to(torch.bool)
    n_protect = int(m.sum(-1).max().item()) if m.numel() else 0
    slot = torch.full((H, D), -1, dtype=torch.int8)
    prot_d = []
    for h in range(H):
        ds = torch.nonzero(m[h], as_tuple=False).flatten().tolist()      # ascending d
        for si, d in enumerate(ds):
            slot[h, d] = si
        prot_d.append(ds)
    return slot, n_protect, prot_d


def build_packed_view(K_fp, V_fp, protect_mask_hd, BS=32, v_group_size=32,
                      k_min=None, k_max=None, prot_int8=False):
    """K_fp,V_fp: (S,H,D) f32; protect_mask_hd: (H,D). Returns the writer's `view` dict (B=1), padded to
    n_blocks*BS with seqlens/partial-tail metadata. prot_int8=True stores the production INT8-restored
    protected values (needs calibrated k_min/k_max (H,D))."""
    K_fp, V_fp = K_fp.float(), V_fp.float()
    S, H, D = K_fp.shape
    if D % 2:
        raise ValueError(f"D={D} must be even")
    if D % v_group_size:
        raise ValueError(f"D={D} not divisible by v_group_size={v_group_size}")
    n_blocks = (S + BS - 1) // BS
    S_pad = n_blocks * BS
    v_n_groups = D // v_group_size

    # ---- K: per-block quant (RF.quantize_k_block == writer _splice_k_partial_tail), padded ----
    k_codes = torch.zeros(S_pad, H, D, dtype=torch.uint8)
    k_scale = torch.zeros(n_blocks, H, D)
    k_xmin = torch.zeros(n_blocks, H, D)
    for b in range(n_blocks):
        s0, s1 = b * BS, min(b * BS + BS, S)
        codes, scale, xmin = RF.quantize_k_block(K_fp[s0:s1])            # over ACTIVE tokens of the block
        k_codes[s0:s1] = codes
        k_scale[b] = scale
        k_xmin[b] = xmin
    k_int4 = RF.pack_nibbles(k_codes)                                    # (S_pad,H,D/2)

    # ---- V: per-token per-group affine /15, padded ----
    v_codes = torch.zeros(S_pad, H, D, dtype=torch.uint8)
    v_scale = torch.zeros(S_pad, H, v_n_groups)
    v_xmin = torch.zeros(S_pad, H, v_n_groups)
    vg = V_fp.view(S, H, v_n_groups, v_group_size)
    vmax, vmin = vg.amax(-1), vg.amin(-1)                               # (S,H,ng)
    vs = ((vmax - vmin) / 15.0).clamp(min=1e-8)
    vc = ((vg - vmin.unsqueeze(-1)) / vs.unsqueeze(-1)).round().clamp(0, 15).to(torch.uint8)
    v_codes[:S] = vc.reshape(S, H, D)
    v_scale[:S], v_xmin[:S] = vs, vmin
    v_int4 = RF.pack_nibbles(v_codes)

    # ---- protect: slot table + sidecar values (bf16, or production int8-restored) ----
    slot, n_protect, prot_d = build_protect_tables(protect_mask_hd)
    if prot_int8:
        if k_min is None or k_max is None:
            raise ValueError("prot_int8 builder needs calibrated k_min/k_max (H,D) — production-faithful.")
        import protected_int8 as P8                                     # noqa: E402
        prot_src, _ = P8.protected_int8_prod(K_fp, k_min, k_max)        # (S,H,D) int8-restored
    else:
        prot_src = K_fp
    k_protect = torch.zeros(S_pad, H, max(1, n_protect))
    for h in range(H):
        for si, d in enumerate(prot_d[h]):
            k_protect[:S, h, si] = prot_src[:, h, d]

    active_in_last = S - (n_blocks - 1) * BS
    return {
        "k_int4": k_int4.unsqueeze(0), "v_int4": v_int4.unsqueeze(0),           # (1,S_pad,H,D/2)
        "k_scale": k_scale.unsqueeze(0), "k_xmin": k_xmin.unsqueeze(0),         # (1,n_blocks,H,D)
        "v_scale": v_scale.unsqueeze(0), "v_xmin": v_xmin.unsqueeze(0),         # (1,S_pad,H,v_ng)
        "k_protect_bf16": k_protect.to(torch.bfloat16).unsqueeze(0),            # (1,S_pad,H,n_protect)
        "protect_slot": slot,                                                  # (H,D) int8
        "group_size": BS, "v_group_size": v_group_size, "n_protect": n_protect,
        "block_table": torch.arange(n_blocks, dtype=torch.int32).view(1, n_blocks),
        "seqlens": torch.tensor([S], dtype=torch.int32),
        "n_blocks": n_blocks, "S_real": S, "S_padded": S_pad, "active_in_last_block": active_in_last,
        "H_kv": H, "D": D, "v_n_groups": v_n_groups, "prot_int8": bool(prot_int8),
    }


def dequant_from_view(view):
    """Reconstruct (K_bf16, V_bf16) (1,S_pad,H,D) from a view via the writer's reference dequant."""
    D = view["D"]
    k_codes = RF.unpack_nibbles(view["k_int4"], D)
    v_codes = RF.unpack_nibbles(view["v_int4"], D)
    k = RF.dequant_k_reference(k_codes, view["k_scale"], view["k_xmin"],
                               view["k_protect_bf16"], view["protect_slot"], view["group_size"])
    v = RF.dequant_v_reference(v_codes, view["v_scale"], view["v_xmin"])
    return k, v


# --------------------------------------------------------------------------- #
# Route-A KERNEL input adapter (for 03_profile_cuda_events.sh). Converts the writer view to the Triton
# kernel's contract (int4_fused_attention_kernel.fused_protected_k_decode_attention): head-major
# (B,H_kv,S,D), SIGNED nibbles (value=nibble-8) with offset=xmin+8*scale, per-group scales. The SAME
# packed bytes are shared with the writer; only the layout + offset convention differ. Numerically
# validated on CPU against int4_fused_attention_sketch.fused_int4_attention_reference (no GPU needed).
# --------------------------------------------------------------------------- #
def make_kernel_inputs(context_len, H_kv=4, D=128, G=7, BS=32, v_group_size=32, seed=0,
                       device="cpu", prot_int8=False, protect_fraction=0.04):
    """Synthetic Route-A kernel inputs at a given context length (padded to full BS-blocks — timing does
    not need partial tails; the correctness gate covers those). Returns (kernel_kwargs, meta)."""
    torch.manual_seed(seed)
    n_blocks = (context_len + BS - 1) // BS
    S = n_blocks * BS
    H_q = H_kv * G
    K_fp, V_fp = torch.randn(S, H_kv, D), torch.randn(S, H_kv, D)
    n_protect = max(1, round(D * protect_fraction))
    mask = torch.zeros(H_kv, D, dtype=torch.int8)
    for h in range(H_kv):
        mask[h, torch.randperm(D)[:n_protect]] = 1
    kmin, kmax = torch.full((H_kv, D), -3.0), torch.full((H_kv, D), 3.0)
    view = build_packed_view(K_fp, V_fp, mask, BS, v_group_size, kmin, kmax, prot_int8)

    k_packed = view["k_int4"][0].permute(1, 0, 2).contiguous().unsqueeze(0)         # (1,H_kv,S,D/2)
    v_packed = view["v_int4"][0].permute(1, 0, 2).contiguous().unsqueeze(0)
    k_scale = view["k_scale"].to(torch.float16).contiguous()                        # (1,n_blocks,H_kv,D)
    k_offset = (view["k_xmin"] + 8.0 * view["k_scale"]).to(torch.float16).contiguous()
    v_scale = view["v_scale"].to(torch.float16).contiguous()                        # (1,S,H_kv,vng)
    v_offset = (view["v_xmin"] + 8.0 * view["v_scale"]).to(torch.float16).contiguous()
    kfp = K_fp
    if prot_int8:                                                                   # protected = int8-restored
        import protected_int8 as P8
        restored, _ = P8.protected_int8_prod(K_fp, kmin, kmax)
        kfp = torch.where(mask.to(torch.bool).unsqueeze(0).expand_as(K_fp), restored, K_fp)
    k_fp16 = kfp.permute(1, 0, 2).contiguous().unsqueeze(0).to(torch.float16)       # (1,H_kv,S,D)
    q = torch.randn(1, H_q, D)                                                      # decode single token

    kw = dict(q=q.to(torch.float16).to(device), k_packed=k_packed.to(device),
              k_scale=k_scale.to(device), k_offset=k_offset.to(device), k_fp16=k_fp16.to(device),
              protect_mask=mask.to(torch.bool).to(device), v_packed=v_packed.to(device),
              v_scale=v_scale.to(device), v_offset=v_offset.to(device),
              group_size_k=BS, group_size_v=v_group_size, asymmetric=True)
    meta = dict(S_kv=S, H_q=H_q, H_kv=H_kv, D=D, n_blocks=n_blocks, K_fp=K_fp, V_fp=V_fp, q=q, mask=mask)
    return kw, meta


def oracle_attention(kw, meta):
    """CPU oracle: run the sketch reference on the kernel inputs -> (1,H_q,D). This is what the Triton
    kernel must match numerically (validated by reference_fp_attention below)."""
    import int4_fused_attention_sketch as SK
    spec = SK.FusedAttentionSpec(B=1, H_q=meta["H_q"], H_kv=meta["H_kv"], S_q=1, S_kv=meta["S_kv"],
                                 D=meta["D"], block_size=kw["group_size_k"],
                                 group_size_k=kw["group_size_k"], group_size_v=kw["group_size_v"],
                                 asymmetric=True)
    out = SK.fused_int4_attention_reference(
        kw["q"].unsqueeze(2), kw["k_packed"], kw["k_scale"], kw["k_offset"],
        kw["v_packed"], kw["v_scale"], kw["v_offset"], spec=spec,
        k_fp16=kw["k_fp16"], k_protect_mask=kw["protect_mask"])
    return out[:, :, 0, :]                                                          # (1,H_q,D)


def reference_fp_attention(meta):
    """Ground-truth fp attention on the ORIGINAL K_fp/V_fp — the oracle's int4 output must be close."""
    q, K_fp, V_fp, H_kv = meta["q"], meta["K_fp"], meta["V_fp"], meta["H_kv"]
    H_q, D = q.shape[1], q.shape[2]
    G = H_q // H_kv
    Ke = K_fp.permute(1, 0, 2).repeat_interleave(G, dim=0)                          # (H_q,S,D)
    Ve = V_fp.permute(1, 0, 2).repeat_interleave(G, dim=0)
    logits = torch.einsum("hd,hsd->hs", q[0].float(), Ke.float()) / math.sqrt(D)
    return torch.einsum("hs,hsd->hd", torch.softmax(logits, -1), Ve.float()).unsqueeze(0)   # (1,H_q,D)
