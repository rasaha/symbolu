"""Phase 2.4.1c — native-kernel-routed vLLM decode with PACKED-K HBM path.

Extends Phase 5A by replacing the in-register quant path (Phase 4) with
the new packed-K HBM kernel (Phase 2.4.1b). The kernel reads packed
INT4 K + scales + xmins + protect-bf16 sidecars directly from HBM
instead of computing them in-register from BF16 K.

V0 implementation (correctness-first):
  - The Phase 5A FP16 K sidecar stays allocated and is the SOURCE OF
    TRUTH for K. At every decode step we re-pack the full max_seqlen-
    padded K via `pack_k_for_phase2_4` and pass the resulting 5
    packed tensors to the kernel via the Phase 2.4.1a kwargs.
  - V is still BF16 in the sidecar (V is not packed in Phase 2.4 —
    that's Phase 2.6).
  - Cost: O(S) repack per decode -> O(S^2) end-to-end. Roughly
    2-4x slower than Phase 5A. Acceptable for end-to-end smoke; not
    for production. v2 (Phase 2.4.1d) does incremental per-group
    repack for O(1) decode.

V0 numerical equivalence to Phase 5A:
  - The kernel dispatches to the packed path when
    `params.is_int4kv_packed = true` (Phase 2.4.1b dispatch). The
    `protect_mask` arg is still passed for safety but ignored on
    the packed path.
  - Phase 2.4.1b verify: cosine vs Phase 5A reference = 0.9999792.
    So Phase 2.4.1c output should match Phase 5A decode quality
    end-to-end modulo the same drift.

V1 constraints inherited from Phase 5A (documented; not bugs):
  - Batch = 1 only.
  - `manager.reset()` between sequences.
  - max_seqlen known upfront for sidecar allocation.
  - max_seqlen MUST be a multiple of group_size_k (=32). Caller
    asserts; default 4096 is fine.

Usage (drop-in replacement for install_phase5a_native):

    from kv_policy.phase2_4_native_install import install_phase2_4_packed
    manager, teardown = install_phase2_4_packed(
        model, protect_fraction=0.04, max_seqlen=4096,
    )
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

from kv_policy.phase5a_native_install import (
    Phase5ANativeCache,
    Phase5ANativeManager,
    _looks_like_attention,
    _reshape_kv_2d_to_3d,
    _detect_num_kv_heads,
)
from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Cache: Phase 5A's FP16 sidecar + cached packed tensors from last repack.
# ----------------------------------------------------------------------

class Phase2_4PackedCache(Phase5ANativeCache):
    """Extends Phase 5A's cache with a packed-K sidecar refreshed on
    each prefill/decode call via pack_k_for_phase2_4.

    The FP16 K buffer (k_fp16) is the source of truth — packing reads
    from it. V stays BF16 in v_fp16 (Phase 2.4 doesn't pack V).
    """

    def __init__(self) -> None:
        super().__init__()
        # Cached packed tensors from the most recent repack. None until
        # the first prefill triggers a pack.
        self.packed: Optional[Dict[str, Any]] = None

    def repack(self, protect_fraction: float, group_size: int = 32) -> None:
        """Repack the FULL k_fp16 buffer (zeros included past s_curr).

        Trimming to s_curr would require padding to a multiple of
        group_size; zero-padded positions past s_curr are within the
        typical K range so don't significantly bias per-group scale.
        The kernel's cache_seqlens arg ensures attention only reads
        valid positions.

        max_seqlen MUST be a multiple of group_size (validated at install).
        """
        if self.k_fp16 is None or self.max_seqlen is None:
            return
        if self.max_seqlen % group_size != 0:
            raise RuntimeError(
                f"max_seqlen={self.max_seqlen} must be a multiple of "
                f"group_size={group_size} for Phase 2.4.1c v0"
            )
        # Pack the entire pre-allocated buffer. The pack function
        # handles (1, S, H, D) shape.
        self.packed = pack_k_for_phase2_4(
            self.k_fp16, group_size=group_size,
            protect_fraction=protect_fraction,
        )

    def reset(self) -> None:
        super().reset()
        self.packed = None


# ----------------------------------------------------------------------
# Manager: same API as Phase 5A's, just uses Phase2_4PackedCache.
# ----------------------------------------------------------------------

class Phase2_4PackedManager(Phase5ANativeManager):
    """Phase 5A manager + Phase2_4PackedCache subclass."""

    def get_or_create(self, module_id: int) -> Phase2_4PackedCache:
        cache = self._caches.get(module_id)
        if cache is None:
            cache = Phase2_4PackedCache()
            self._caches[module_id] = cache
        return cache  # type: ignore[return-value]

    def stats(self) -> Dict[str, Any]:
        s = super().stats()
        s["installer"] = "phase2_4_packed"
        return s


# ----------------------------------------------------------------------
# Wrapper: same shape as Phase 5A's, decode passes packed kwargs.
# ----------------------------------------------------------------------

def _wrap_attention_forward_packed(
    module: Any,
    *,
    manager: Phase2_4PackedManager,
    query_arg_index: int,
    key_arg_index: int,
    value_arg_index: int,
    num_kv_heads_hint: Optional[int],
    teardown_list: List[Callable[[], None]],
) -> None:
    """Replace module.forward with a packed-K decode bypass.

    Prefill: same as Phase 5A — append to sidecar, freeze protect mask,
    then ALSO trigger an initial repack so the first decode step has
    packed K ready.

    Decode (T == 1): append to sidecar, repack the full K buffer,
    call flash_attn_with_int4_kvcache with the new packed kwargs.
    The kernel dispatches to the Phase 2.4.1b packed path.
    """
    try:
        from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            f"Phase 2.4.1c install needs vllm.vllm_flash_attn: {e}"
        )

    original_forward = module.forward
    module_id = id(module)

    def wrapped_forward(*args, **kwargs):
        # Bail on missing/wrong-shape K, V.
        if (key_arg_index >= len(args) or value_arg_index >= len(args)
                or query_arg_index >= len(args)
                or not isinstance(args[key_arg_index], torch.Tensor)
                or not isinstance(args[value_arg_index], torch.Tensor)
                or args[key_arg_index].ndim not in (2, 3)
                or args[value_arg_index].ndim not in (2, 3)):
            manager._stats["fallback_calls"] += 1
            return original_forward(*args, **kwargs)

        key   = args[key_arg_index]
        value = args[value_arg_index]
        was_2d = (key.ndim == 2)

        if was_2d:
            if num_kv_heads_hint is None:
                manager._stats["fallback_calls"] += 1
                return original_forward(*args, **kwargs)
            k_3d = _reshape_kv_2d_to_3d(key,   num_kv_heads_hint)
            v_3d = _reshape_kv_2d_to_3d(value, num_kv_heads_hint)
            if k_3d is None or v_3d is None:
                manager._stats["fallback_calls"] += 1
                return original_forward(*args, **kwargs)
        else:
            k_3d, v_3d = key, value

        T = k_3d.shape[0]
        if T < 1:
            return original_forward(*args, **kwargs)

        cache = manager.get_or_create(module_id)

        if T > 1:
            # Prefill: append, freeze mask, initial repack, stock fwd.
            try:
                cache.append(k_3d, v_3d, manager.max_seqlen)
                cache.compute_protect_mask(manager.protect_fraction)
                cache.repack(manager.protect_fraction)
                manager._stats["prefill_calls"] += 1
            except Exception:
                logger.exception(
                    "Phase 2.4.1c prefill failed on %s",
                    type(module).__name__,
                )
                manager._stats["fallback_calls"] += 1
            return original_forward(*args, **kwargs)

        # Decode (T == 1): packed-K bypass.
        try:
            cache.append(k_3d, v_3d, manager.max_seqlen)
            if not cache.mask_frozen:
                logger.warning(
                    "Phase 2.4.1c decode without frozen mask on %s; "
                    "falling back to stock", type(module).__name__,
                )
                manager._stats["fallback_calls"] += 1
                return original_forward(*args, **kwargs)
            # V0: repack the full K buffer (O(S) per step).
            cache.repack(manager.protect_fraction)
            if cache.packed is None:
                manager._stats["fallback_calls"] += 1
                return original_forward(*args, **kwargs)

            query = args[query_arg_index]
            if not isinstance(query, torch.Tensor):
                manager._stats["fallback_calls"] += 1
                return original_forward(*args, **kwargs)
            out_dtype = query.dtype
            query_was_2d = (query.ndim == 2)
            D = cache.head_dim
            if query_was_2d:
                if query.shape[-1] % D != 0:
                    manager._stats["fallback_calls"] += 1
                    return original_forward(*args, **kwargs)
                H_q = query.shape[-1] // D
                if query.shape[0] != 1:
                    manager._stats["fallback_calls"] += 1
                    return original_forward(*args, **kwargs)
                q_kernel = query.reshape(1, 1, H_q, D)
            else:
                if query.shape[0] != 1:
                    manager._stats["fallback_calls"] += 1
                    return original_forward(*args, **kwargs)
                H_q = query.shape[1]
                q_kernel = query.unsqueeze(0)

            if q_kernel.dtype != cache.dtype:
                q_kernel = q_kernel.to(cache.dtype)
            q_kernel = q_kernel.contiguous()

            cache_seqlens = torch.tensor(
                [cache.s_curr], dtype=torch.int32, device=q_kernel.device,
            )

            packed = cache.packed
            out = flash_attn_with_int4_kvcache(
                q_kernel,
                cache.k_fp16,
                cache.v_fp16,
                cache_seqlens=cache_seqlens,
                # Phase 4 args kept for Phase 5A reference compatibility
                # (kernel ignores on the packed path):
                protect_mask=cache.protect_mask,
                n_protect=cache.n_protect,
                # Phase 2.4.1c packed kwargs (Phase 2.4.1a plumbing,
                # consumed by Phase 2.4.1b kernel):
                k_packed_int4=packed["k_int4"].contiguous(),
                k_packed_scale=packed["k_scale"].contiguous(),
                k_packed_xmin=packed["k_xmin"].contiguous(),
                k_packed_protect_bf16=packed["k_protect_bf16"].contiguous(),
                k_packed_protect_slot=packed["protect_slot"].contiguous(),
                packed_group_size=packed["group_size"],
                packed_n_protect=packed["n_protect"],
                causal=False,
            )
            out = out.squeeze(1)
            if out.dtype != out_dtype:
                out = out.to(out_dtype)
            if query_was_2d:
                out = out.reshape(1, H_q * D)
            manager._stats["decode_calls"] += 1
            return out

        except Exception:
            logger.exception(
                "Phase 2.4.1c decode failed on %s; falling back",
                type(module).__name__,
            )
            manager._stats["fallback_calls"] += 1
            return original_forward(*args, **kwargs)

    module.forward = wrapped_forward
    teardown_list.append(lambda: setattr(module, "forward", original_forward))


# ----------------------------------------------------------------------
# Top-level install.
# ----------------------------------------------------------------------

def install_phase2_4_packed(
    model: Any,
    *,
    protect_fraction: float = 0.04,
    max_seqlen: int = 4096,
    num_kv_heads: Optional[int] = None,
    query_arg_index: int = 0,
    key_arg_index:   int = 1,
    value_arg_index: int = 2,
) -> Tuple[Phase2_4PackedManager, Callable[[], None]]:
    """Install Phase 2.4.1c packed-K kernel routing on every attention
    module in `model`.

    Returns (manager, teardown). Drop-in replacement for
    install_phase5a_native — same API, packed-K kernel underneath.

    max_seqlen MUST be a multiple of group_size_k (=32). Default 4096
    is fine. Qwen2.5-7B with max_model_len 4096 works out of the box.
    """
    if torch is None:
        raise RuntimeError("Phase 2.4.1c install requires torch")

    if max_seqlen % 32 != 0:
        raise ValueError(
            f"max_seqlen={max_seqlen} must be a multiple of group_size_k=32"
        )

    resolved_num_kv_heads = num_kv_heads or _detect_num_kv_heads(model)

    manager = Phase2_4PackedManager(
        protect_fraction=protect_fraction,
        max_seqlen=max_seqlen,
    )
    teardown_list: List[Callable[[], None]] = []

    n_wrapped = 0
    if hasattr(model, "named_modules"):
        for _name, sub in model.named_modules():
            if not _looks_like_attention(sub):
                continue
            _wrap_attention_forward_packed(
                sub,
                manager=manager,
                query_arg_index=query_arg_index,
                key_arg_index=key_arg_index,
                value_arg_index=value_arg_index,
                num_kv_heads_hint=resolved_num_kv_heads,
                teardown_list=teardown_list,
            )
            n_wrapped += 1

    if n_wrapped == 0:
        raise ValueError(
            "install_phase2_4_packed found no attention modules on the "
            "model. The leaf-attention heuristic missed — either the "
            "model arg is wrong, or this vLLM version names its "
            "attention class differently."
        )

    logger.info(
        "Phase 2.4.1c installed: %d attention modules wrapped "
        "(protect_fraction=%.2f, max_seqlen=%d, num_kv_heads=%s)",
        n_wrapped, protect_fraction, max_seqlen, resolved_num_kv_heads,
    )

    def teardown() -> None:
        for revert in reversed(teardown_list):
            revert()
        teardown_list.clear()

    return manager, teardown
