"""Phase 5A — native-kernel-routed vLLM decode (BF16-backed KV cache).

Installs a wrapper on each Attention.forward in a running vLLM model so
that DECODE routes through `flash_attn_with_int4_kvcache` with a static
top-`protect_fraction` K-channel mask, while PREFILL runs through stock
vLLM attention unchanged. The protect mask is computed once per
(layer, sequence) at end of prefill from the accumulated K's per-
channel magnitudes.

SCOPE — this is the routing+quality proof phase. NOT a memory-savings
phase:

  - HBM K/V remain BF16 (vLLM's main paged cache, unchanged).
  - The wrapper maintains a PARALLEL FP16 sidecar K/V buffer per layer
    so the kernel has a contiguous (B, S_kv, H_kv, D) tensor to read
    from. This adds ~2× KV memory at Phase 5A. The sidecar is a
    measurement-time cost — it does not enter the v1 ship claim.
  - Real HBM INT4 storage + block-manager integration is Phase 2.4 /
    later phases. Phase 5A unblocks REAL-DATA QUALITY tests on the
    native kernel path before we sink engineer-days into Phase 2.4.

V1 constraints (documented; not bugs):
  - Batch = 1 only. Manager state is process-global, no per-sequence
    slot mapping. Calling with batch > 1 will silently corrupt the
    sidecar.
  - One concurrent sequence per process. `manager.reset()` clears state
    between sequences.
  - No prefix caching. Sidecar is per-process, not shared.
  - max_seqlen must be known up front for sidecar preallocation.

Decision rule from Phase 6.4 GREEN (commit 1e4dfb5): default
protect_fraction = 0.04. 0.08 is the safe-mode alternative for
workloads where decode quality issues appear downstream.

Usage:

    from vllm import LLM, SamplingParams
    from kv_policy.phase5a_native_install import install_phase5a_native

    llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=32768)
    manager, teardown = install_phase5a_native(
        llm.llm_engine.model_executor.driver_worker.model_runner.model,
        protect_fraction=0.04,
        max_seqlen=32768,
    )
    outputs = llm.generate(["Hello world"], SamplingParams(max_tokens=32))
    manager.reset()  # before the next prompt
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Per-layer sidecar cache.
# ----------------------------------------------------------------------

class Phase5ANativeCache:
    """Per-layer parallel FP16 K/V buffer + frozen protect mask.

    Storage is (1, max_seqlen, num_kv_heads, head_dim) — the exact shape
    `flash_attn_with_int4_kvcache` expects for k_cache/v_cache. No
    contiguous() needed on the decode hot path.

    Allocated lazily on first append (we don't know num_kv_heads/
    head_dim until we see the first K tensor).
    """

    def __init__(self) -> None:
        self.k_fp16: Optional["torch.Tensor"] = None
        self.v_fp16: Optional["torch.Tensor"] = None
        self.num_kv_heads: Optional[int] = None
        self.head_dim:     Optional[int] = None
        self.max_seqlen:   Optional[int] = None
        self.dtype:        Optional["torch.dtype"] = None
        self.device:       Optional["torch.device"] = None
        self.s_curr: int = 0
        self.protect_mask: Optional["torch.Tensor"] = None  # (1, H_kv, D) int8
        self.mask_frozen: bool = False
        self.n_protect: int = 0

    def _ensure_alloc(
        self, k: "torch.Tensor", max_seqlen: int,
    ) -> None:
        if self.k_fp16 is not None:
            return
        if k.ndim != 3:
            raise ValueError(
                f"Phase5A cache expects 3-D K of shape (T, H_kv, D); "
                f"got {tuple(k.shape)}"
            )
        T, H_kv, D = k.shape
        self.num_kv_heads = H_kv
        self.head_dim     = D
        self.max_seqlen   = max_seqlen
        self.dtype        = k.dtype
        self.device       = k.device
        # (1, max_seqlen, H_kv, D) — kernel-ready layout.
        self.k_fp16 = torch.zeros(
            (1, max_seqlen, H_kv, D), dtype=k.dtype, device=k.device,
        )
        self.v_fp16 = torch.zeros(
            (1, max_seqlen, H_kv, D), dtype=k.dtype, device=k.device,
        )

    def append(self, k_new: "torch.Tensor", v_new: "torch.Tensor",
               max_seqlen: int) -> None:
        """Append new K/V tokens. k_new, v_new shape (T, H_kv, D)."""
        self._ensure_alloc(k_new, max_seqlen)
        T = k_new.shape[0]
        if self.s_curr + T > self.max_seqlen:
            raise RuntimeError(
                f"Phase5A cache overflow: s_curr={self.s_curr} + "
                f"T={T} > max_seqlen={self.max_seqlen}"
            )
        self.k_fp16[0, self.s_curr:self.s_curr + T, :, :] = k_new
        self.v_fp16[0, self.s_curr:self.s_curr + T, :, :] = v_new
        self.s_curr += T

    def compute_protect_mask(self, protect_fraction: float) -> None:
        """Freeze the per-(H_kv, D) protect mask from current cache.

        Called once at end of prefill (the §20.4.3 static-mask policy).
        Idempotent on subsequent calls (returns early if frozen).

        Top-`protect_fraction` channels by per-channel max-abs across
        the accumulated seq dim, per kv_head. Same selection rule as
        `kv_policy.int4_per_channel_hf_cache._select_outlier_mask`.
        """
        if self.mask_frozen:
            return
        if self.s_curr <= 0 or self.k_fp16 is None:
            return  # nothing to compute from yet
        k_active = self.k_fp16[0, :self.s_curr, :, :]  # (s_curr, H_kv, D)
        # Per-(H_kv, D) magnitude: max-abs over seq axis.
        ch_mag = k_active.float().abs().amax(dim=0)    # (H_kv, D)
        H_kv, D = ch_mag.shape
        n_protect = max(1, int(round(D * protect_fraction)))
        _, topk_idx = ch_mag.topk(n_protect, dim=-1)    # (H_kv, n_protect)
        mask = torch.zeros((1, H_kv, D), dtype=torch.int8, device=ch_mag.device)
        mask.scatter_(-1, topk_idx.unsqueeze(0), 1)
        self.protect_mask = mask
        self.mask_frozen = True
        self.n_protect = n_protect

    def reset(self) -> None:
        """Clear state between sequences. Keeps the allocated buffers."""
        self.s_curr = 0
        self.protect_mask = None
        self.mask_frozen = False
        self.n_protect = 0


# ----------------------------------------------------------------------
# Manager.
# ----------------------------------------------------------------------

class Phase5ANativeManager:
    """Owns per-layer Phase5ANativeCache and per-install configuration.

    State is keyed by `id(module)` (Python object identity) so multiple
    attention modules in the same model get distinct caches.
    """

    def __init__(
        self,
        *,
        protect_fraction: float = 0.04,
        max_seqlen: int = 32768,
    ) -> None:
        if not (0.0 <= protect_fraction < 1.0):
            raise ValueError(
                f"protect_fraction must be in [0, 1); got {protect_fraction}"
            )
        self.protect_fraction = float(protect_fraction)
        self.max_seqlen = int(max_seqlen)
        self._caches: Dict[int, Phase5ANativeCache] = {}
        self._stats: Dict[str, int] = {
            "prefill_calls": 0,
            "decode_calls":  0,
            "fallback_calls": 0,
        }

    def get_or_create(self, module_id: int) -> Phase5ANativeCache:
        cache = self._caches.get(module_id)
        if cache is None:
            cache = Phase5ANativeCache()
            self._caches[module_id] = cache
        return cache

    def reset(self) -> None:
        """Clear per-sequence state on all caches between requests."""
        for c in self._caches.values():
            c.reset()
        # Don't touch stats; they're cumulative.

    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "num_layers_wrapped": len(self._caches),
            "protect_fraction":   self.protect_fraction,
            "max_seqlen":         self.max_seqlen,
        }


# ----------------------------------------------------------------------
# Attention-module detection (verbatim from 6c.3A).
# ----------------------------------------------------------------------

def _looks_like_attention(module: Any) -> bool:
    """LEAF attention check for Phase 5A.

    vLLM's Qwen2 (and most model implementations) have TWO levels of
    attention class:

      - `Qwen2Attention` (outer, model-specific) — forward signature
        (positions, hidden_states, kv_cache, attn_metadata). Holds the
        Q/K/V projections + RoPE; calls `self.attn(...)` internally.

      - `Attention` (inner, vllm.attention.layer.Attention) — forward
        signature (query, key, value, kv_cache, attn_metadata). The
        leaf — actually dispatches to the attention backend kernel.

    Both class names end in "Attention". The 6c.3A install wrapped
    BOTH on purpose (it replaced the entire attention pipeline with a
    Triton kernel). Phase 5A only wants to swap the KERNEL CALL inside
    the leaf — wrapping the outer module would mis-interpret the
    (positions, hidden_states, ...) args as (query, key, value, ...)
    and bail out cleanly via the shape guard, but each bail-out counts
    as a fallback and inflates the gate.

    This function returns True ONLY for leaf attention modules — those
    with NO sub-attention descendants.
    """
    cls_name = type(module).__name__
    if not cls_name.endswith("Attention"):
        return False
    if not callable(getattr(module, "forward", None)):
        return False
    # Check for any descendant Attention module.
    for sub in module.modules():
        if sub is module:
            continue
        sub_cls = type(sub).__name__
        if sub_cls.endswith("Attention") and callable(getattr(sub, "forward", None)):
            return False  # has a child Attention => NOT a leaf
    return True


def _reshape_kv_2d_to_3d(
    kv: "torch.Tensor", num_kv_heads: int,
) -> Optional["torch.Tensor"]:
    """Reshape a 2-D (T, H_kv * D) tensor to (T, H_kv, D), or None on
    mismatch."""
    if kv.ndim != 2:
        return None
    T, hd = kv.shape
    if hd % num_kv_heads != 0:
        return None
    D = hd // num_kv_heads
    return kv.reshape(T, num_kv_heads, D)


# ----------------------------------------------------------------------
# The wrapper.
# ----------------------------------------------------------------------

def _wrap_attention_forward(
    module: Any,
    *,
    manager: Phase5ANativeManager,
    query_arg_index: int,
    key_arg_index: int,
    value_arg_index: int,
    num_kv_heads_hint: Optional[int],
    teardown_list: List[Callable[[], None]],
) -> None:
    """Replace module.forward.

      - Prefill (T > 1): append K/V to the layer's sidecar, compute
        protect mask, then call ORIGINAL forward unchanged (vLLM's
        stock prefill attention runs on the BF16 K/V).
      - Decode (T == 1): append K/V to sidecar, call
        flash_attn_with_int4_kvcache, return its output instead of
        invoking the original forward. vLLM's PagedAttention is
        bypassed for THIS layer's decode call.

    The wrapper fails-OPEN: any unexpected condition (missing kernel,
    shape mismatch, kv heads unknown, etc.) falls through to the
    original forward. Stats are recorded so misbehavior is visible.
    """
    # Lazy import — we need vLLM installed, but the module file should
    # be importable without it for tests.
    try:
        from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Phase 5A install requires vllm.vllm_flash_attn with the "
            "Phase 2.3/3/4/2.5 patches applied. flash_attn_with_int4_kvcache "
            f"could not be imported: {e}"
        )

    original_forward = module.forward
    module_id = id(module)

    def wrapped_forward(*args, **kwargs):
        # Bail out cleanly on missing/wrong-shape K, V.
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

        # Reshape K/V to 3-D for cache + kernel.
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
            # ---- Prefill: sidecar append, freeze mask, stock forward ----
            try:
                cache.append(k_3d, v_3d, manager.max_seqlen)
                cache.compute_protect_mask(manager.protect_fraction)
                manager._stats["prefill_calls"] += 1
            except Exception:
                logger.exception("Phase5A prefill sidecar failed on %s",
                                 type(module).__name__)
                manager._stats["fallback_calls"] += 1
            return original_forward(*args, **kwargs)

        # ---- Decode (T == 1): native kernel bypass ----
        try:
            cache.append(k_3d, v_3d, manager.max_seqlen)
            if not cache.mask_frozen:
                # No prefill seen for this cache — fall back. Shouldn't
                # happen in normal usage but the guard is cheap.
                logger.warning(
                    "Phase5A decode without frozen protect mask on %s; "
                    "falling back to stock attention.",
                    type(module).__name__,
                )
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
                # (1, H_q*D) -> (1, 1, H_q, D)  [B, S_q, H_q, D]
                q_kernel = query.reshape(1, 1, H_q, D)
            else:
                if query.shape[0] != 1:
                    manager._stats["fallback_calls"] += 1
                    return original_forward(*args, **kwargs)
                # (1, H_q, D) -> (1, 1, H_q, D)
                H_q = query.shape[1]
                q_kernel = query.unsqueeze(0)

            # Kernel wants FP16 or BF16; match cache dtype.
            if q_kernel.dtype != cache.dtype:
                q_kernel = q_kernel.to(cache.dtype)
            q_kernel = q_kernel.contiguous()

            cache_seqlens = torch.tensor(
                [cache.s_curr], dtype=torch.int32, device=q_kernel.device,
            )

            out = flash_attn_with_int4_kvcache(
                q_kernel,
                cache.k_fp16,
                cache.v_fp16,
                cache_seqlens=cache_seqlens,
                protect_mask=cache.protect_mask,
                n_protect=cache.n_protect,
                causal=False,  # single-token decode; causal is moot
            )
            # out shape: (1, 1, H_q, D)
            out = out.squeeze(1)  # (1, H_q, D)
            if out.dtype != out_dtype:
                out = out.to(out_dtype)
            if query_was_2d:
                out = out.reshape(1, H_q * D)
            manager._stats["decode_calls"] += 1
            return out

        except Exception:
            logger.exception(
                "Phase5A decode bypass failed on %s; falling back to "
                "stock attention. (Cache may be partially populated; "
                "subsequent decodes' correctness is not guaranteed for "
                "this sequence.)",
                type(module).__name__,
            )
            manager._stats["fallback_calls"] += 1
            return original_forward(*args, **kwargs)

    module.forward = wrapped_forward
    teardown_list.append(lambda: setattr(module, "forward", original_forward))


# ----------------------------------------------------------------------
# Optional: introspect num_kv_heads from a vLLM model.
# ----------------------------------------------------------------------

def _detect_num_kv_heads(model: Any) -> Optional[int]:
    """Best-effort introspection. Walks the model looking for a config
    with `num_key_value_heads` (HF/vLLM standard). Returns None if it
    can't find one — caller must then pass num_kv_heads explicitly."""
    cfg = getattr(model, "config", None)
    if cfg is not None:
        for name in ("num_key_value_heads", "num_kv_heads"):
            v = getattr(cfg, name, None)
            if isinstance(v, int) and v > 0:
                return v
    return None


# ----------------------------------------------------------------------
# Top-level install.
# ----------------------------------------------------------------------

def install_phase5a_native(
    model: Any,
    *,
    protect_fraction: float = 0.04,
    max_seqlen: int = 32768,
    num_kv_heads: Optional[int] = None,
    query_arg_index: int = 0,
    key_arg_index:   int = 1,
    value_arg_index: int = 2,
) -> Tuple[Phase5ANativeManager, Callable[[], None]]:
    """Install Phase 5A native-kernel routing on every attention module
    in `model`.

    Returns (manager, teardown). Call teardown() to restore the
    original forwards. Call manager.reset() between sequences.

    Per Phase 6.4 decision (commit 1e4dfb5):
      - protect_fraction default = 0.04
      - protect_fraction = 0.08 is the safe-mode alternative

    `max_seqlen` sizes the sidecar K/V buffer (FP16 (1, max_seqlen,
    H_kv, D) per layer). For Qwen2.5-7B at max_seqlen=32768 with 28
    layers, 4 kv heads, 128 head_dim, this is 28 * 1 * 32768 * 4 * 128
    * 2 bytes * 2 (K+V) ≈ ~3.7 GB. That's the v1 sidecar cost; Phase
    2.4 removes it by storing INT4 in vLLM's native paged cache.

    `num_kv_heads` is needed when vLLM hands the wrapper a 2-D (T, H *
    D) K/V tensor. Auto-detected from `model.config.num_key_value_heads`
    if not passed.
    """
    if torch is None:
        raise RuntimeError("Phase 5A install requires torch")

    resolved_num_kv_heads = num_kv_heads or _detect_num_kv_heads(model)

    manager = Phase5ANativeManager(
        protect_fraction=protect_fraction,
        max_seqlen=max_seqlen,
    )
    teardown_list: List[Callable[[], None]] = []

    n_wrapped = 0
    if hasattr(model, "named_modules"):
        for _name, sub in model.named_modules():
            if not _looks_like_attention(sub):
                continue
            _wrap_attention_forward(
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
            "install_phase5a_native found no attention modules on the "
            "model. The class-name heuristic (endswith 'Attention') "
            "missed — either the model argument is wrong, or this vLLM "
            "version names its attention class differently."
        )

    logger.info(
        "Phase 5A installed: %d attention modules wrapped "
        "(protect_fraction=%.2f, max_seqlen=%d, num_kv_heads=%s)",
        n_wrapped, protect_fraction, max_seqlen, resolved_num_kv_heads,
    )

    def teardown() -> None:
        for revert in reversed(teardown_list):
            revert()
        teardown_list.clear()
        # Stats and cache buffers stay alive until manager is GC'd —
        # caller can still inspect manager.stats() after teardown.

    return manager, teardown
