"""Phase 5B.2/5B.3 — Int4Protected attention backend + impl.

5B.2 v0: post-init class-swap install (KEPT as fallback).
5B.3a v0: init-time selection via CacheConfig + get_attn_backend hooks.

Behavior is still pure DELEGATE at this phase — Phase 5B.4 will insert
real packed-K kernel calls. The goal of 5B.2/5B.3a is to prove we can
plug into vLLM's attention pipeline at the right places (impl class +
backend class + config validation) without breaking generation.

Scope clarification vs the design doc:
  - Design doc Phase 5B.2 envisioned "register a new attention backend
    with vLLM's backend selection". The probe at commit 946dcd5
    revealed that `kv_cache_dtype="int4_protected"` is rejected by
    `CacheConfig` validation. Patching that validation is more invasive
    than the 5B.2 skeleton needs. Moved to Phase 5C.
  - 5B.2 instead: subclass `FlashAttentionImpl`, install via post-init
    class swap on each layer's `.impl` instance. Gets us the same
    surface for Phase 5B.4 work without touching CacheConfig.

Probe evidence (commit 946dcd5):
  - vLLM 0.7.3 FA backend: `vllm.attention.backends.flash_attn.FlashAttentionImpl`
  - Each leaf Attention layer has `.impl: FlashAttentionImpl` (28 instances on Qwen2.5-7B)
  - FlashAttentionImpl MRO: [FlashAttentionImpl, AttentionImpl, ABC, Generic, object]
  - No `__slots__` apparent → instance-level `__class__` swap is safe.

Install pattern: same shape as Phase 5A's wrap_attention_forward, but
operates on `module.impl` not `module.forward`. RAII-style teardown.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

# vLLM imports may be unavailable in some test environments — guard them.
try:
    from vllm.attention.backends.flash_attn import (
        FlashAttentionBackend,
        FlashAttentionImpl,
    )
    _VLLM_FA_AVAILABLE = True
except ImportError:  # pragma: no cover
    FlashAttentionBackend = None  # type: ignore
    FlashAttentionImpl = None  # type: ignore
    _VLLM_FA_AVAILABLE = False

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Int4ProtectedAttentionImpl — subclass with delegated forward.
# ----------------------------------------------------------------------

if _VLLM_FA_AVAILABLE:

    class Int4ProtectedAttentionImpl(FlashAttentionImpl):
        """Phase 5B.2 skeleton subclass of FlashAttentionImpl.

        v0 forward: pure delegate. Phase 5B.4 will replace the delegate
        with a packed-K kernel call (using PartialGroupQuantizer for
        cache writes and the Phase 2.4.1b packed kernel for reads).

        We do NOT override __init__ — that lets the install function
        do an in-place class swap on existing FA-impl instances, which
        preserves all the state (head_size, num_heads, scale, etc.)
        that the engine wired up at init time.
        """

        # Sentinel for verify scripts to check. Bumped each sub-sub-phase.
        _phase5b_backend_marker = "5B.4b"

        def forward(
            self,
            layer,
            query,
            key,
            value,
            kv_cache,
            attn_metadata,
            output=None,
        ):
            """Phase 5B.4a: REPLICATE FlashAttentionImpl.forward in our
            subclass. Same code paths, same output, but we control every
            call site. This sets up the surface for Phase 5B.4b (shape
            shrink) and 5B.4c (read/write path replacement).

            The replication MUST stay bit-equivalent to FlashAttentionImpl.
            Verified by verify_phase5b_4a_forward.py (output == stock
            generation, char-for-char on greedy decode).

            We import the helper functions from FA at call time to avoid
            ImportError at module-load time if vLLM is missing.
            """
            # Lazy imports — these are private to vllm.attention.backends.flash_attn
            # and may not exist in all vLLM versions. ImportError here means
            # we should fall back to super().forward(), which will hit the
            # 5B.3a-style kv_cache_dtype swap path.
            try:
                from vllm.attention.backends.flash_attn import (
                    AttentionType,
                    flash_attn_varlen_func,
                    flash_attn_with_kvcache,
                    get_num_prefill_decode_query_kv_tokens,
                    get_seq_len_block_table_args,
                    _get_query_key_seq_metadata,
                    _get_causal_option,
                )
            except ImportError:
                # Fallback: delegate with dtype swap (5B.3a behavior).
                saved = getattr(self, "kv_cache_dtype", None)
                if saved == "int4_protected":
                    self.kv_cache_dtype = "auto"
                    try:
                        return super().forward(
                            layer, query, key, value, kv_cache,
                            attn_metadata, output,
                        )
                    finally:
                        self.kv_cache_dtype = saved
                return super().forward(
                    layer, query, key, value, kv_cache,
                    attn_metadata, output,
                )

            # ---- Header validations (copied verbatim from FA forward) ----
            assert layer._k_scale_float == 1.0 and layer._v_scale_float == 1.0, (
                "key/v_scale is not supported in FlashAttention.")
            assert output is not None, "Output tensor must be provided."

            attn_type = self.attn_type
            if (attn_type == AttentionType.ENCODER
                    and (not attn_metadata.is_all_encoder_attn_metadata_set)):
                raise AttributeError("Encoder attention requires setting "
                                     "encoder metadata attributes.")
            elif (attn_type == AttentionType.ENCODER_DECODER
                  and (not attn_metadata.is_all_cross_attn_metadata_set)):
                raise AttributeError("Encoder/decoder cross-attention "
                                     "requires setting cross-attention "
                                     "metadata attributes.")

            # ---- Extract per-impl params ----
            kv_cache_dtype: str = self.kv_cache_dtype
            softmax_scale: float = self.scale
            window_size = self.sliding_window
            alibi_slopes = self.alibi_slopes
            logits_soft_cap = self.logits_soft_cap

            # 5B.4a: swap "int4_protected" -> "auto" before
            # reshape_and_cache_flash, which is a compiled C++ op that
            # rejects unknown dtype strings. The cache LAYOUT is still
            # stock bf16 in this sub-sub-phase, so "auto" is correct.
            # Phase 5B.4c will REPLACE this call entirely, not swap.
            if kv_cache_dtype == "int4_protected":
                kv_cache_dtype = "auto"

            # ---- Cache write (5B.4c will replace this with PartialGroupQuantizer) ----
            if kv_cache.numel() > 0:
                key_cache = kv_cache[0]
                value_cache = kv_cache[1]
                if (attn_type != AttentionType.ENCODER) and (key is not None) and (
                        value is not None):
                    if attn_type == AttentionType.ENCODER_DECODER:
                        updated_slot_mapping = attn_metadata.cross_slot_mapping
                    else:
                        updated_slot_mapping = attn_metadata.slot_mapping
                    torch.ops._C_cache_ops.reshape_and_cache_flash(
                        key, value, kv_cache[0], kv_cache[1],
                        updated_slot_mapping.flatten(),
                        kv_cache_dtype,
                        layer._k_scale, layer._v_scale,
                    )

            # ---- Token routing ----
            (num_prefill_query_tokens, num_prefill_kv_tokens,
             num_decode_query_tokens) = \
                get_num_prefill_decode_query_kv_tokens(attn_metadata, attn_type)
            decode_query = query[num_prefill_query_tokens:]
            decode_output = output[num_prefill_query_tokens:]
            query = query[:num_prefill_query_tokens]
            prefill_output = output[:num_prefill_query_tokens]
            assert query.shape[0] == num_prefill_query_tokens
            assert decode_query.shape[0] == num_decode_query_tokens

            # ---- Prefill attention (5B.4c will replace inner kernel call) ----
            if prefill_meta := attn_metadata.prefill_metadata:
                if (kv_cache.numel() == 0 or prefill_meta.block_tables is None
                        or prefill_meta.block_tables.numel() == 0):
                    # Normal varlen attention (no paged cache yet).
                    q_seq_start_loc, q_seq_len, k_seq_start_loc, k_seq_len = \
                        _get_query_key_seq_metadata(prefill_meta, True, attn_type)
                    key = key[:num_prefill_kv_tokens]
                    value = value[:num_prefill_kv_tokens]
                    flash_attn_varlen_func(
                        q=query, k=key, v=value,
                        cu_seqlens_q=q_seq_start_loc,
                        cu_seqlens_k=k_seq_start_loc,
                        max_seqlen_q=q_seq_len,
                        max_seqlen_k=k_seq_len,
                        softmax_scale=softmax_scale,
                        causal=_get_causal_option(attn_type),
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        softcap=logits_soft_cap,
                        out=prefill_output,
                        fa_version=self.vllm_flash_attn_version,
                    )
                else:
                    # Prefix-enabled attention (Q current, K/V from cache).
                    assert attn_type == AttentionType.DECODER, (
                        "Only decoder-only models support prefix caching")
                    assert prefill_meta.seq_lens is not None
                    max_seq_len = max(prefill_meta.seq_lens)
                    flash_attn_varlen_func(
                        q=query, k=key_cache, v=value_cache,
                        cu_seqlens_q=prefill_meta.query_start_loc,
                        max_seqlen_q=prefill_meta.max_query_len,
                        seqused_k=prefill_meta.seq_lens_tensor,
                        max_seqlen_k=max_seq_len,
                        softmax_scale=softmax_scale,
                        causal=True,
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        block_table=prefill_meta.block_tables,
                        softcap=logits_soft_cap,
                        out=prefill_output,
                        fa_version=self.vllm_flash_attn_version,
                    )

            # ---- Decode attention (5B.4c will replace inner kernel call) ----
            if decode_meta := attn_metadata.decode_metadata:
                assert decode_meta.max_decode_query_len is not None
                if decode_meta.max_decode_query_len > 1:
                    # Speculative-decode-style varlen path.
                    assert attn_type == AttentionType.DECODER, (
                        "Only decoder-only models support max_decode_query_len > 1")
                    flash_attn_varlen_func(
                        q=decode_query, k=key_cache, v=value_cache,
                        cu_seqlens_q=decode_meta.query_start_loc,
                        max_seqlen_q=decode_meta.max_decode_query_len,
                        seqused_k=decode_meta.seq_lens_tensor,
                        max_seqlen_k=decode_meta.max_decode_seq_len,
                        softmax_scale=softmax_scale,
                        causal=True,
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        softcap=logits_soft_cap,
                        block_table=decode_meta.block_tables,
                        out=decode_output,
                        fa_version=self.vllm_flash_attn_version,
                    )
                else:
                    # Standard decode path (the common case).
                    seq_lens_arg, _, block_tables_arg = (
                        get_seq_len_block_table_args(decode_meta, False, attn_type)
                    )
                    flash_attn_with_kvcache(
                        q=decode_query.unsqueeze(1),
                        k_cache=key_cache, v_cache=value_cache,
                        block_table=block_tables_arg,
                        cache_seqlens=seq_lens_arg,
                        softmax_scale=softmax_scale,
                        causal=True,
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        softcap=logits_soft_cap,
                        out=decode_output.unsqueeze(1),
                        fa_version=self.vllm_flash_attn_version,
                    )
            return output

else:

    class Int4ProtectedAttentionImpl:  # type: ignore[no-redef]
        """Placeholder for environments without vLLM. Raises on use."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "Int4ProtectedAttentionImpl requires vllm.attention.backends.flash_attn"
            )


# ----------------------------------------------------------------------
# Int4ProtectedAttentionBackend — subclass of FlashAttentionBackend
# for Phase 5B.3a init-time selection.
# ----------------------------------------------------------------------

if _VLLM_FA_AVAILABLE:

    class Int4ProtectedAttentionBackend(FlashAttentionBackend):
        """Phase 5B.3a backend class. Returned by our patched
        get_attn_backend_cls when kv_cache_dtype="int4_protected".

        Inherits all of FlashAttentionBackend's methods (kv_cache_shape,
        copy_blocks, swap_blocks, etc.), but overrides get_impl_cls()
        to return Int4ProtectedAttentionImpl so each attention layer
        constructs with our impl from the start (no post-init swap
        needed).

        Phase 5B.4 will additionally override get_kv_cache_shape AND
        the byte-cost calculation for actual memory savings. v0 here
        keeps stock memory layout — only the dispatch class changes.
        """

        _phase5b_backend_marker = "5B.3a"

        @staticmethod
        def get_name() -> str:
            return "INT4_PROTECTED"

        @staticmethod
        def get_impl_cls():
            return Int4ProtectedAttentionImpl

else:

    class Int4ProtectedAttentionBackend:  # type: ignore[no-redef]
        """Placeholder when vLLM unavailable."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "Int4ProtectedAttentionBackend requires vllm.attention.backends.flash_attn"
            )


# ----------------------------------------------------------------------
# Manager — tracks swap state for teardown.
# ----------------------------------------------------------------------

class Int4ProtectedBackendManager:
    """Tracks which Attention.impl instances we swapped, for teardown.

    Each entry is (impl_instance, original_class) so we can restore
    the original class on teardown. We swap __class__ in place rather
    than substituting a different instance — instance state is preserved
    (which is critical: the engine sets up head_size, scale, num_heads,
    etc. on the original instance during init, and we want to inherit
    all of that).
    """

    def __init__(self) -> None:
        # (impl_instance, original_class) pairs.
        self.swapped: List[Tuple[Any, type]] = []
        # Per-swap stats.
        self._stats: Dict[str, int] = {
            "swapped_impls":         0,
            "skipped_not_FA_impl":   0,
            "skipped_no_impl_attr":  0,
            "fallback_forward_swap": 0,
        }

    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "installer": "phase5b_backend_skeleton",
            "phase":     "5B.2",
        }


# ----------------------------------------------------------------------
# Attention layer detection (same heuristic as Phase 5A).
# ----------------------------------------------------------------------

def _looks_like_attention(module: Any) -> bool:
    cls_name = type(module).__name__
    if not cls_name.endswith("Attention"):
        return False
    if not callable(getattr(module, "forward", None)):
        return False
    for sub in module.modules():
        if sub is module:
            continue
        sub_cls = type(sub).__name__
        if sub_cls.endswith("Attention") and callable(getattr(sub, "forward", None)):
            return False
    return True


# ----------------------------------------------------------------------
# Install — swap each leaf Attention layer's .impl class.
# ----------------------------------------------------------------------

def install_int4_protected_backend(
    model: Any,
) -> Tuple[Int4ProtectedBackendManager, Callable[[], None]]:
    """Swap each leaf Attention layer's `.impl` class from
    `FlashAttentionImpl` to `Int4ProtectedAttentionImpl`.

    Strategy: in-place `__class__` assignment on the existing impl
    instance. This:
      - Preserves all instance state (head_size, scale, num_heads, ...).
      - Changes the dispatch for forward() and any other overrides.
      - Is reversible (teardown restores the original class).

    If the in-place class swap fails (e.g., __slots__ conflict on a
    future vLLM version), the install falls back to a forward-method
    monkey-patch (same pattern as Phase 5A).

    Returns:
      (manager, teardown)
        manager.stats() reports counts of swapped vs skipped layers.
        teardown() restores all swapped __class__ assignments.

    Raises ValueError if zero layers were swappable (likely a vLLM
    version mismatch — Int4ProtectedAttentionImpl assumes
    FlashAttentionImpl as the parent).
    """
    if not _VLLM_FA_AVAILABLE:
        raise RuntimeError(
            "install_int4_protected_backend requires vllm.attention.backends.flash_attn. "
            "Are you running in venv-vllm?"
        )

    manager = Int4ProtectedBackendManager()

    # Track forward-fallback swaps separately (for teardown).
    forward_swaps: List[Tuple[Any, Callable]] = []

    for name, sub in model.named_modules():
        if not _looks_like_attention(sub):
            continue
        if not hasattr(sub, "impl"):
            manager._stats["skipped_no_impl_attr"] += 1
            logger.warning("Layer %s has no .impl attribute; skipping", name)
            continue
        impl = sub.impl
        if not isinstance(impl, FlashAttentionImpl):
            manager._stats["skipped_not_FA_impl"] += 1
            logger.warning(
                "Layer %s .impl is %s, not FlashAttentionImpl; skipping",
                name, type(impl).__name__,
            )
            continue

        original_class = impl.__class__
        try:
            impl.__class__ = Int4ProtectedAttentionImpl
            manager.swapped.append((impl, original_class))
            manager._stats["swapped_impls"] += 1
        except TypeError as e:
            # __class__ swap failed — likely __slots__ or similar.
            # Fall back to monkey-patching forward on this instance.
            logger.warning(
                "Class swap failed on layer %s (%s); falling back to "
                "forward monkey-patch.", name, e,
            )
            original_forward = impl.forward

            def _wrapped_forward(_orig=original_forward):
                def f(*a, **kw):
                    # Pure delegate at this phase.
                    return _orig(*a, **kw)
                return f
            impl.forward = _wrapped_forward()
            forward_swaps.append((impl, original_forward))
            manager._stats["fallback_forward_swap"] += 1

    if (manager._stats["swapped_impls"] == 0
            and manager._stats["fallback_forward_swap"] == 0):
        raise ValueError(
            "install_int4_protected_backend found no swappable Attention "
            f"impls. Stats: {manager.stats()}"
        )

    logger.info(
        "Phase 5B.2 installed: %d class swaps, %d forward fallbacks",
        manager._stats["swapped_impls"],
        manager._stats["fallback_forward_swap"],
    )

    def teardown() -> None:
        # Restore class-swapped impls.
        for impl, original_class in manager.swapped:
            try:
                impl.__class__ = original_class
            except TypeError as e:
                logger.warning("Teardown class restore failed on %s: %s", impl, e)
        manager.swapped.clear()
        # Restore forward-monkey-patched impls.
        for impl, original_forward in forward_swaps:
            impl.forward = original_forward
        forward_swaps.clear()

    return manager, teardown


# ----------------------------------------------------------------------
# Utility — count how many layers currently use our subclass.
# ----------------------------------------------------------------------

def count_int4_protected_impls(model: Any) -> Tuple[int, int]:
    """Returns (int4_protected_count, total_FA_impl_count). Useful for
    verify scripts to assert install / teardown took effect."""
    if not _VLLM_FA_AVAILABLE:
        return (0, 0)
    n_ours = 0
    n_total = 0
    for _, sub in model.named_modules():
        if not _looks_like_attention(sub):
            continue
        if not hasattr(sub, "impl"):
            continue
        impl = sub.impl
        if isinstance(impl, FlashAttentionImpl):
            n_total += 1
            if isinstance(impl, Int4ProtectedAttentionImpl):
                n_ours += 1
    return (n_ours, n_total)


# ----------------------------------------------------------------------
# Phase 5B.3a — init-time install via CacheConfig + backend selector
# monkey-patches. Call BEFORE LLM(...) construction.
# ----------------------------------------------------------------------

# Module-level state so enable/disable is idempotent across calls.
_INSTALLED_PATCHES: Dict[str, Any] = {}


def enable_int4_protected_backend() -> None:
    """Patch vLLM at the module level so kv_cache_dtype="int4_protected"
    is accepted by CacheConfig validation AND routed to our backend
    class at engine init. Idempotent — safe to call multiple times.

    Patches applied:
      1. CacheConfig._verify_cache_dtype: add "int4_protected" to the
         accepted list (alongside "auto" and the fp8 variants).
      2. current_platform.get_attn_backend_cls: when kv_cache_dtype
         == "int4_protected", return our backend's qualname instead
         of vLLM's default FA qualname. resolve_obj_by_qualname then
         imports our class via kv_policy.phase5b_backend_install.
      3. _cached_get_attn_backend.cache_clear() to invalidate any
         stale cache hits from before patching.

    Call BEFORE LLM(...) construction. Once patches are in place, you
    can construct an LLM with kv_cache_dtype="int4_protected" and the
    engine init will route through Int4ProtectedAttentionBackend →
    Int4ProtectedAttentionImpl per attention layer.

    See disable_int4_protected_backend() for teardown (process-level —
    rarely needed since process exit clears the patches).
    """
    if not _VLLM_FA_AVAILABLE:
        raise RuntimeError(
            "enable_int4_protected_backend requires vllm.attention.backends.flash_attn"
        )
    if _INSTALLED_PATCHES.get("phase5b_3a", False):
        return

    # --- 1. CacheConfig._verify_cache_dtype patch ---
    import vllm.config as vllm_config
    original_verify = vllm_config.CacheConfig._verify_cache_dtype
    _INSTALLED_PATCHES["original_verify_cache_dtype"] = original_verify

    def _patched_verify(self):
        # Accept "int4_protected" as a valid dtype. Falls through to the
        # original method for all other values (auto, fp8 variants, etc.).
        if getattr(self, "cache_dtype", None) == "int4_protected":
            logger.info(
                "Using int4_protected kv cache dtype (Phase 5B.3a). "
                "Routes through Int4ProtectedAttentionBackend at init."
            )
            return
        return original_verify(self)

    vllm_config.CacheConfig._verify_cache_dtype = _patched_verify

    # --- 2. current_platform.get_attn_backend_cls patch ---
    from vllm.platforms import current_platform
    original_get_cls = current_platform.get_attn_backend_cls
    _INSTALLED_PATCHES["original_get_attn_backend_cls"] = original_get_cls
    _INSTALLED_PATCHES["platform"] = current_platform

    def _patched_get_cls(*args, **kwargs):
        # The signature is (selected_backend, head_size, dtype,
        # kv_cache_dtype, block_size, use_v1, use_mla) but we accept
        # *args/**kwargs to be robust to minor signature drift.
        # kv_cache_dtype is the 4th positional arg or "kv_cache_dtype" kwarg.
        kv_dtype = kwargs.get("kv_cache_dtype")
        if kv_dtype is None and len(args) >= 4:
            kv_dtype = args[3]
        if kv_dtype == "int4_protected":
            return (
                "kv_policy.phase5b_backend_install."
                "Int4ProtectedAttentionBackend"
            )
        return original_get_cls(*args, **kwargs)

    current_platform.get_attn_backend_cls = _patched_get_cls

    # --- 3. Clear the @cache on _cached_get_attn_backend ---
    from vllm.attention import selector as sel_mod
    cached = getattr(sel_mod, "_cached_get_attn_backend", None)
    if cached is not None and hasattr(cached, "cache_clear"):
        cached.cache_clear()

    # --- 4. Extend STR_DTYPE_TO_TORCH_DTYPE to accept "int4_protected" ---
    # CacheEngine.get_cache_block_size does
    #   STR_DTYPE_TO_TORCH_DTYPE[cache_config.cache_dtype]
    # which KeyErrors on "int4_protected" without this patch.
    #
    # Phase 5B.4b: map "int4_protected" -> torch.uint8 (1 byte/elem),
    # down from bf16 (2 bytes/elem). This halves per-block bytes, which
    # doubles num_blocks at the same gpu_memory_utilization budget.
    # The reserve-line bytes don't shrink (vLLM fills the budget either
    # way), but the per-block sizing is now INT4-aware. Phase 5B.4c
    # adds the matching write/read paths so the smaller storage isn't
    # just garbage.
    import sys as _sys
    patched_dict_ids: set = set()
    patched_dicts: list = []
    for mod_name, mod in list(_sys.modules.items()):
        if mod is None or not isinstance(mod_name, str) or not mod_name.startswith("vllm"):
            continue
        d = getattr(mod, "STR_DTYPE_TO_TORCH_DTYPE", None)
        if isinstance(d, dict) and id(d) not in patched_dict_ids:
            # Always overwrite (in case we changed the mapping between
            # 5B.3a's bf16 and 5B.4b's uint8 across script reloads).
            d["int4_protected"] = torch.uint8
            logger.info(
                "Patched STR_DTYPE_TO_TORCH_DTYPE in %s: "
                "'int4_protected' -> torch.uint8 (5B.4b: half bytes/elem)",
                mod_name,
            )
            patched_dicts.append((d, "int4_protected"))
            patched_dict_ids.add(id(d))
    _INSTALLED_PATCHES["str_dtype_dicts"] = patched_dicts

    _INSTALLED_PATCHES["phase5b_3a"] = True
    logger.info(
        "Phase 5B.3a installed: kv_cache_dtype='int4_protected' accepted; "
        "backend selection patched to return Int4ProtectedAttentionBackend."
    )


def disable_int4_protected_backend() -> None:
    """Undo the patches installed by enable_int4_protected_backend().
    Process-level — clears the module-level state. Mainly useful for
    test cleanup; normal use just relies on process exit."""
    if not _INSTALLED_PATCHES.get("phase5b_3a", False):
        return

    import vllm.config as vllm_config
    vllm_config.CacheConfig._verify_cache_dtype = (
        _INSTALLED_PATCHES["original_verify_cache_dtype"]
    )

    platform = _INSTALLED_PATCHES["platform"]
    platform.get_attn_backend_cls = (
        _INSTALLED_PATCHES["original_get_attn_backend_cls"]
    )

    from vllm.attention import selector as sel_mod
    cached = getattr(sel_mod, "_cached_get_attn_backend", None)
    if cached is not None and hasattr(cached, "cache_clear"):
        cached.cache_clear()

    # Undo STR_DTYPE_TO_TORCH_DTYPE extensions.
    for d, key in _INSTALLED_PATCHES.get("str_dtype_dicts", []):
        d.pop(key, None)

    _INSTALLED_PATCHES.clear()
    logger.info("Phase 5B.3a patches removed.")


def is_int4_protected_enabled() -> bool:
    """True iff enable_int4_protected_backend() has been called and
    not since disabled. Mainly for tests."""
    return _INSTALLED_PATCHES.get("phase5b_3a", False)
