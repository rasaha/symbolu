"""Phase 5B.2 — Int4ProtectedAttentionImpl skeleton + post-init install.

Sets up the impl-layer surface where Phase 5B.4 will insert real
packed-K kernel calls. v0 here is a thin DELEGATING subclass — behavior
is unchanged vs stock vLLM/FlashAttention. The goal of 5B.2 is to prove
we can swap in a custom impl class without breaking generation.

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

        # Sentinel for verify scripts to check.
        _phase5b_backend_marker = "5B.2"

        def forward(self, *args, **kwargs):
            # Pure delegate. Phase 5B.4 inserts real packed-K behavior here.
            return super().forward(*args, **kwargs)

else:

    class Int4ProtectedAttentionImpl:  # type: ignore[no-redef]
        """Placeholder for environments without vLLM. Raises on use."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "Int4ProtectedAttentionImpl requires vllm.attention.backends.flash_attn"
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
