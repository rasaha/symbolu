"""kv_policy.int4_protected — Phase 5C clean API surface.

ONE-IMPORT setup for the int4_protected KV-cache backend. Importing
this submodule registers the backend with vLLM so the standard
`LLM(kv_cache_dtype="int4_protected", block_size=32)` construction
JUST WORKS — no post-construction install step required.

For the typical use case:

  ```python
  import kv_policy.int4_protected   # registers the backend
  from vllm import LLM, SamplingParams

  llm = LLM(
      model="Qwen/Qwen2.5-7B-Instruct",
      kv_cache_dtype="int4_protected",
      block_size=32,                # required: kernel kInt4GroupSize=32
      max_model_len=4096,
  )
  out = llm.generate(["Hello"], SamplingParams(temperature=0.0, max_tokens=32))
  ```

For one-liner convenience, use `Int4ProtectedLLM`:

  ```python
  from kv_policy.int4_protected import Int4ProtectedLLM

  llm = Int4ProtectedLLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=4096)
  ```

Constraints (v1):
  - block_size MUST equal 32 (kernel kInt4GroupSize is a compile-time
    constexpr). Int4ProtectedLLM enforces this default.
  - batch=1 v1 — only one sequence in flight at a time. Multi-batch
    is Phase 5B.6.
  - Qwen2.5-7B is the calibrated model. Other models need their own
    protect_mask calibration via calibrate_phase5b_protect_mask.py.
  - $PROTECT_MASK_PATH must point to the calibrated mask artifact
    (default `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`).

What this module does on import:
  1. Calls `enable_int4_protected_backend()` which patches:
     - CacheConfig._verify_cache_dtype (accepts "int4_protected")
     - current_platform.get_attn_backend_cls (routes to our backend)
     - STR_DTYPE_TO_TORCH_DTYPE (maps to torch.uint8)
  2. Layer-index assignment happens lazily on first forward via each
     Attention layer's `.layer_name` attribute (parsed for an integer
     in `model.layers.<N>.self_attn.attn` format).

For advanced users who want explicit layer-idx assignment (rare),
the legacy `install_int4_protected_backend(model)` function is still
available — it walks named_modules and pre-assigns indices.

Memory accounting (Qwen2.5-7B, max_model_len=4096, gpu_mem_util=0.5):
  - vLLM paged uint8 cache:   24 GB (2x token capacity vs stock bf16)
  - External sidecars:        ~4.2 GB (K_scale, K_xmin, K_protect,
                              V_scale, V_xmin per layer)
  - BF16 K/V backing:         ~224 MB (~1% overhead, small-S kernel
                              workaround; deferred Phase 6 polish)
  - Total:                    ~28.4 GB to hold ~898K concurrent slots
                              vs stock 24 GB / 223K = 4x capacity at
                              +18% memory.

See KERNEL_6C3C_RESUME.md for the full architecture trace and
KERNEL_6C3C_PHASE5B4C_DESIGN.md for the locked design.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from kv_policy.phase5b_backend_install import (
    enable_int4_protected_backend,
    install_int4_protected_backend,
    is_int4_protected_enabled,
    Int4ProtectedAttentionImpl,
    Int4ProtectedAttentionBackend,
    count_int4_protected_impls,
)

logger = logging.getLogger(__name__)


# Phase 5C: auto-register on import. Idempotent (enable is no-op if
# already enabled). The 'enabled' state lives at module level inside
# phase5b_backend_install; calling enable a second time is cheap.
enable_int4_protected_backend()


# ----------------------------------------------------------------------
# Int4ProtectedLLM — convenience factory.
# ----------------------------------------------------------------------

# Required block_size constraint from the kernel's compile-time
# kInt4GroupSize=32 constexpr.
_REQUIRED_BLOCK_SIZE = 32


def Int4ProtectedLLM(
    model: str,
    *,
    block_size: int = _REQUIRED_BLOCK_SIZE,
    kv_cache_dtype: str = "int4_protected",
    max_model_len: int = 4096,
    gpu_memory_utilization: float = 0.5,
    enforce_eager: bool = True,
    **kwargs: Any,
):
    """Phase 5C one-step factory: returns a configured `vllm.LLM` ready
    to generate through the int4_protected backend.

    All standard `vllm.LLM(...)` kwargs are forwarded via **kwargs. The
    block_size and kv_cache_dtype defaults are enforced to keep callers
    from accidentally hitting the kernel's compile-time constraint.

    Args:
        model: HF model id / local path (must have a calibrated
            protect_mask at $PROTECT_MASK_PATH; v1 calibrated for
            Qwen2.5-7B).
        block_size: Must be 32 (kernel kInt4GroupSize). Raises if not.
        kv_cache_dtype: "int4_protected" (default). Override only for
            testing — passing "auto" returns a stock LLM via this
            factory (also useful for side-by-side reference runs).
        max_model_len, gpu_memory_utilization, enforce_eager: forwarded
            to LLM with v1-recommended defaults.
        **kwargs: anything else accepted by `vllm.LLM`.

    Raises:
        ValueError: if block_size != 32 and kv_cache_dtype is the
            int4_protected variant.
        ImportError: if vllm isn't importable in this env.

    Returns:
        A `vllm.LLM` instance. The Attention layers' impl class is
        already `Int4ProtectedAttentionImpl` via the engine-init
        backend selector; layer indices auto-resolve from
        `layer.layer_name` on first forward.
    """
    if kv_cache_dtype == "int4_protected" and block_size != _REQUIRED_BLOCK_SIZE:
        raise ValueError(
            f"int4_protected requires block_size={_REQUIRED_BLOCK_SIZE} "
            f"(kernel kInt4GroupSize is a compile-time constexpr). "
            f"Got block_size={block_size}."
        )

    # Lazy import so the kv_policy package remains importable in
    # environments without vLLM (eg. CPU-only dev).
    try:
        from vllm import LLM
    except ImportError as e:
        raise ImportError(
            "Int4ProtectedLLM requires vllm to be installed. "
            f"Original error: {e}"
        )

    if kv_cache_dtype == "int4_protected" and not is_int4_protected_enabled():
        # Belt and suspenders — the module-level enable already ran on
        # import, but in pathological reload scenarios call it again.
        enable_int4_protected_backend()

    return LLM(
        model=model,
        block_size=block_size,
        kv_cache_dtype=kv_cache_dtype,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=enforce_eager,
        **kwargs,
    )


# ----------------------------------------------------------------------
# Diagnostics — useful for verify scripts and notebook smoke tests.
# ----------------------------------------------------------------------

def get_backend_info(llm: Any) -> dict:
    """Snapshot of the int4_protected backend state on a constructed
    LLM. Useful for verify scripts and debugging.

    Returns:
        dict with keys:
          - marker:           "5B.4c.3" (the impl's _phase5b_backend_marker)
          - layers_swapped:   how many Attention layers use our impl
          - layers_total:     total leaf Attention layers
          - call_stats:       current call counts (write/decode/fallbacks)
          - backend_enabled:  bool — is the module-level patch active
    """
    model = _find_inner_model(llm)
    n_ours, n_total = count_int4_protected_impls(model)
    return {
        "marker":          getattr(Int4ProtectedAttentionImpl, "_phase5b_backend_marker", "?"),
        "layers_swapped":  n_ours,
        "layers_total":    n_total,
        "call_stats":      Int4ProtectedAttentionImpl.get_call_stats(),
        "backend_enabled": is_int4_protected_enabled(),
    }


def _find_inner_model(llm: Any) -> Any:
    """Locate the inner nn.Module inside a vLLM LLM. Robust to minor
    vLLM API drift across 0.7.x patch versions."""
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.workers[0].model_runner.model,
    ]
    last_err: Optional[Exception] = None
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError) as e:
            last_err = e
    raise RuntimeError(f"Could not locate inner nn.Module. Last error: {last_err}")


# Public surface — what users see in `from kv_policy.int4_protected import *`.
__all__ = [
    "Int4ProtectedLLM",
    "get_backend_info",
    # Legacy / advanced:
    "enable_int4_protected_backend",
    "install_int4_protected_backend",
    "is_int4_protected_enabled",
    "Int4ProtectedAttentionImpl",
    "Int4ProtectedAttentionBackend",
]
