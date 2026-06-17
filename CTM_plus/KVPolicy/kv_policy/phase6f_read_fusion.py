"""Phase 6F — fused int4 read-path dequant-prep (decode-throughput recovery lever).

⚠️ HARDWARE-UNTESTED on GPU. This module does NOT measure or claim any throughput number.
The decode-throughput recovery has a **bounded ceiling (~0.27–0.30× of full precision, PROJECTED)
and NEVER reaches full-precision parity** — the GPU kernel/fusion + its measurement are pod-only.

What this file provides (CPU-validated, pod-ready):
  * `dequant_k_reference` / `dequant_v_reference` — a pure-PyTorch REFERENCE for the
    gather→splice→dequant-prep numerics of the int4 read path (the spec the kernel must match).
  * `dequant_k_fused` / `dequant_v_fused` — a single-pass FUSED variant (the host-side part of the
    "fuse the pre-kernel gather+splice+dequant-prep" lever, measured ~42–60% of the B=1 read path),
    proven **byte-equal** to the reference on CPU by `tests/test_phase6f_read_fusion_cpu.py`.
  * `fused_read_dequant_prep` — consumes the writer's `get_packed_view[_batched]` dict and returns
    kernel-ready bf16 K/V; env `PHASE6F_FUSED_READ=0` forces the reference (byte-eq harness toggle,
    mirroring Phase 6E's `PHASE6E_FUSED_WRITER`).
  * `read_prep_dispatch` — routes to the existing CUDA/Triton fused kernel on GPU (pod-only; see
    `int4_fused_attention_kernel.fused_protected_k_decode_attention`) and to the CPU host-fused prep
    otherwise. The CUDA path is the throughput lever; this host path is the oracle + CPU fallback.

Authoritative convention matched (phase5b_backend_install._splice_k_partial_tail +
phase5b_4c_paged_writer.get_packed_view*):
  K quant : scale = ((amax-amin)/15).clamp(min=1e-8);  code = round((x-xmin)/scale).clamp(0,15) uint8
            pack: byte j = (code[2j] & 0x0F) | (code[2j+1] << 4);  per-BLOCK scale/xmin (NB,H,D).
  K dequant: value = code*scale + xmin; channel (h,d) with protect_slot[h,d] >= 0 is REPLACED by
             k_protect_bf16[..., protect_slot[h,d]] (V is never protected).
  V quant : per-TOKEN, grouped over head_dim into v_n_groups; value = code*v_scale[s,h,g]+v_xmin[s,h,g].

Integration point (pod): the host-fused prep replaces the staged
`get_packed_view_batched → _splice_k_partial_tail_batched → dequant` sequence inside
`phase5b_backend_install._read_decode_packed_batched` (B=1: `_read_decode_packed_one`).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

_PROT_NONE = -1                      # protect_slot sentinel: channel is NOT protected
_FUSED_READ_ENV = "PHASE6F_FUSED_READ"


# --------------------------------------------------------------------------- #
# Nibble pack / unpack — exact inverse of the writer's pack (low nibble = even
# channel, high nibble = odd channel), UNSIGNED codes in [0, 15].
# --------------------------------------------------------------------------- #
def unpack_nibbles(packed: "torch.Tensor", D: int) -> "torch.Tensor":
    """(..., D//2) uint8 -> (..., D) uint8 codes in [0,15]. Even channels = low nibble."""
    if D % 2 != 0:
        raise ValueError(f"D={D} must be even for nibble packing")
    if packed.shape[-1] != D // 2:
        raise ValueError(f"packed last dim {packed.shape[-1]} != D//2 = {D // 2}")
    low = packed & 0x0F
    high = (packed >> 4) & 0x0F
    out = torch.empty(*packed.shape[:-1], D, dtype=torch.uint8, device=packed.device)
    out[..., 0::2] = low
    out[..., 1::2] = high
    return out


def pack_nibbles(codes: "torch.Tensor") -> "torch.Tensor":
    """(..., D) uint8 codes in [0,15] -> (..., D//2) uint8. Inverse of unpack_nibbles."""
    low = codes[..., 0::2] & 0x0F
    high = codes[..., 1::2] & 0x0F
    return (low | (high << 4)).to(torch.uint8)


def quantize_k_block(x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
    """Per-block K quant exactly as `_splice_k_partial_tail`: x (BS,H,D) f32 ->
    (codes (BS,H,D) uint8, scale (H,D), xmin (H,D)). Used by the round-trip tests."""
    xf = x.float()
    x_max = xf.amax(dim=0)
    x_min = xf.amin(dim=0)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)
    codes = ((xf - x_min.unsqueeze(0)) / scale.unsqueeze(0)).round().clamp(0, 15).to(torch.uint8)
    return codes, scale, x_min


# --------------------------------------------------------------------------- #
# K dequant — REFERENCE (staged, obviously-correct spec).
# --------------------------------------------------------------------------- #
def dequant_k_reference(
    k_codes: "torch.Tensor",       # (B, S, H, D) uint8 codes [0,15]
    k_scale: "torch.Tensor",       # (B, n_blocks, H, D) — per BLOCK
    k_xmin: "torch.Tensor",        # (B, n_blocks, H, D) — per BLOCK
    k_protect_bf16: "torch.Tensor",# (B, S, H, n_protect)
    protect_slot: "torch.Tensor",  # (H, D) int8, slot in [0,n_protect) or -1
    BS: int,
    out_dtype: "torch.dtype" = None,
) -> "torch.Tensor":
    """value = code*scale[block]+xmin[block], then protected channels overlay k_protect_bf16."""
    if out_dtype is None:
        out_dtype = k_protect_bf16.dtype
    B, S, H, D = k_codes.shape
    n_blocks = k_scale.shape[1]
    if S != n_blocks * BS:
        raise ValueError(f"S={S} != n_blocks*BS = {n_blocks * BS}")
    # Expand per-block scale/xmin to per-token by repeating each block BS times.
    block_of_tok = (torch.arange(S, device=k_codes.device) // BS).long()    # (S,)
    scale_tok = k_scale.index_select(1, block_of_tok)                       # (B, S, H, D)
    xmin_tok = k_xmin.index_select(1, block_of_tok)
    base = (k_codes.float() * scale_tok.float() + xmin_tok.float()).to(out_dtype)

    # Protect overlay: gather the protect value for each (h,d) by its slot, mask non-protected.
    slot = protect_slot.long()                                              # (H, D)
    slot_idx = slot.clamp(min=0).view(1, 1, H, D).expand(B, S, H, D)        # (B,S,H,D)
    gathered = torch.gather(k_protect_bf16.to(out_dtype), dim=3, index=slot_idx)
    mask = (slot >= 0).view(1, 1, H, D)                                     # (1,1,H,D)
    return torch.where(mask, gathered, base)


# --------------------------------------------------------------------------- #
# K dequant — FUSED (single-pass; same arithmetic, fewer intermediates).
# --------------------------------------------------------------------------- #
def dequant_k_fused(
    k_codes, k_scale, k_xmin, k_protect_bf16, protect_slot, BS, out_dtype=None,
) -> "torch.Tensor":
    """Byte-equal to dequant_k_reference; mirrors the in-register kernel fusion shape:
    repeat-expand block scale/xmin and fold the protect overlay in one masked select."""
    if out_dtype is None:
        out_dtype = k_protect_bf16.dtype
    B, S, H, D = k_codes.shape
    n_blocks = k_scale.shape[1]
    # repeat_interleave instead of index_select+arange — equivalent per-token expansion.
    scale_tok = k_scale.repeat_interleave(BS, dim=1)[:, :S]                  # (B,S,H,D)
    xmin_tok = k_xmin.repeat_interleave(BS, dim=1)[:, :S]
    out = (k_codes.float() * scale_tok.float() + xmin_tok.float()).to(out_dtype)
    slot = protect_slot.long()
    prot_hd = (slot >= 0)                                                    # (H,D) bool
    if bool(prot_hd.any()):
        slot_idx = slot.clamp(min=0).view(1, 1, H, D).expand(B, S, H, D)
        gathered = torch.gather(k_protect_bf16.to(out_dtype), 3, slot_idx)
        out = torch.where(prot_hd.view(1, 1, H, D), gathered, out)
    return out


# --------------------------------------------------------------------------- #
# V dequant — per-token grouped over head_dim (no protect).
# --------------------------------------------------------------------------- #
def dequant_v_reference(
    v_codes: "torch.Tensor",   # (B, S, H, D) uint8
    v_scale: "torch.Tensor",   # (B, S, H, v_n_groups)
    v_xmin: "torch.Tensor",    # (B, S, H, v_n_groups)
    out_dtype: "torch.dtype" = None,
) -> "torch.Tensor":
    if out_dtype is None:
        out_dtype = v_scale.dtype
    B, S, H, D = v_codes.shape
    v_n_groups = v_scale.shape[-1]
    if D % v_n_groups != 0:
        raise ValueError(f"D={D} not divisible by v_n_groups={v_n_groups}")
    gsz = D // v_n_groups
    group_of_d = (torch.arange(D, device=v_codes.device) // gsz).long()     # (D,)
    scale_d = v_scale.index_select(3, group_of_d)                           # (B,S,H,D)
    xmin_d = v_xmin.index_select(3, group_of_d)
    return (v_codes.float() * scale_d.float() + xmin_d.float()).to(out_dtype)


def dequant_v_fused(v_codes, v_scale, v_xmin, out_dtype=None) -> "torch.Tensor":
    """Byte-equal to dequant_v_reference via repeat_interleave over head_dim groups."""
    if out_dtype is None:
        out_dtype = v_scale.dtype
    B, S, H, D = v_codes.shape
    v_n_groups = v_scale.shape[-1]
    gsz = D // v_n_groups
    scale_d = v_scale.repeat_interleave(gsz, dim=3)[..., :D]
    xmin_d = v_xmin.repeat_interleave(gsz, dim=3)[..., :D]
    return (v_codes.float() * scale_d.float() + xmin_d.float()).to(out_dtype)


# --------------------------------------------------------------------------- #
# Whole-prep entry: consume get_packed_view[_batched] dict -> kernel-ready bf16.
# --------------------------------------------------------------------------- #
def _fused_read_enabled() -> bool:
    return os.environ.get(_FUSED_READ_ENV, "1") != "0"


def fused_read_dequant_prep(
    view: Dict[str, Any],
    *,
    BS: int = None,
    fused: bool = None,
    out_dtype: "torch.dtype" = None,
) -> Dict[str, "torch.Tensor"]:
    """Dequant-prep over a get_packed_view[_batched] dict. Returns {'k_bf16','v_bf16'} as
    (B,S,H,D). `view['k_int4']`/`['v_int4']` are packed (B,S,H,D/2); the rest per the writer's
    contract. `fused=None` reads the PHASE6F_FUSED_READ env; pass explicitly in tests."""
    if torch is None:  # pragma: no cover
        raise ImportError("fused_read_dequant_prep requires PyTorch")
    if fused is None:
        fused = _fused_read_enabled()
    if BS is None:
        BS = int(view["group_size"])
    k_packed = view["k_int4"]
    B, S, H, half_D = k_packed.shape
    D = half_D * 2
    k_codes = unpack_nibbles(k_packed, D)
    v_codes = unpack_nibbles(view["v_int4"], D)
    protect_slot = view["protect_slot"]

    if fused:
        k_bf16 = dequant_k_fused(k_codes, view["k_scale"], view["k_xmin"],
                                 view["k_protect_bf16"], protect_slot, BS, out_dtype)
        v_bf16 = dequant_v_fused(v_codes, view["v_scale"], view["v_xmin"], out_dtype)
    else:
        k_bf16 = dequant_k_reference(k_codes, view["k_scale"], view["k_xmin"],
                                     view["k_protect_bf16"], protect_slot, BS, out_dtype)
        v_bf16 = dequant_v_reference(v_codes, view["v_scale"], view["v_xmin"], out_dtype)
    return {"k_bf16": k_bf16, "v_bf16": v_bf16}


def read_prep_dispatch(view: Dict[str, Any], *, q_is_cuda: bool = False, **kw) -> Dict[str, Any]:
    """Route the read-prep. On CUDA the throughput-optimal path is the inline fused Triton kernel
    (`int4_fused_attention_kernel.fused_protected_k_decode_attention`, pod-only — it streams int4
    from HBM and dequants in registers, avoiding this host materialization); this function returns
    the host-fused bf16 prep as the CPU path / numerical oracle. The GPU speedup is PROJECTED
    (≤~0.30×), not measured here."""
    if q_is_cuda:
        try:
            from kv_policy.int4_fused_attention_kernel import _HAVE_TRITON
        except Exception:  # noqa: BLE001
            _HAVE_TRITON = False
        if not _HAVE_TRITON:
            # No Triton on this pod — fall back to the host-fused prep + stock kernel.
            return fused_read_dequant_prep(view, **kw)
        # Pod path: the caller should invoke the inline fused kernel directly with `view`'s
        # packed tensors; the host prep is unnecessary there. Signal that to the caller.
        return {"use_inline_kernel": True}
    return fused_read_dequant_prep(view, **kw)
