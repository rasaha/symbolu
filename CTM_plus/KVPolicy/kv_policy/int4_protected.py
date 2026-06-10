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
import os
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
#
# Phase 6K.15: gated on vllm being importable AT ALL, so this module
# imports cleanly in CPU-only dev/test envs (matching the package's
# guarded-import convention). Distinguish two failure shapes:
#   - vllm entirely absent  -> soft skip (factory raises ImportError at
#     call time anyway; nothing to register against).
#   - vllm present but the FA backend enable fails -> still raise, loudly
#     (that is a real breakage on a serving pod, not a dev env).
try:
    import vllm as _vllm_probe  # noqa: F401
    _VLLM_IMPORTABLE = True
except ImportError:
    _VLLM_IMPORTABLE = False

if _VLLM_IMPORTABLE:
    enable_int4_protected_backend()
else:
    logger.info(
        "vllm not importable; int4_protected backend not registered "
        "(CPU dev mode — Int4ProtectedLLM will raise ImportError if called)."
    )


# ----------------------------------------------------------------------
# Int4ProtectedLLM — convenience factory.
# ----------------------------------------------------------------------

# Required block_size constraint from the kernel's compile-time
# kInt4GroupSize=32 constexpr.
_REQUIRED_BLOCK_SIZE = 32


# Phase 6B.3 — env-controlled kill-switch that forces enforce_eager=True
# even when the caller defaults / passes False. Set
# PHASE6B3_FORCE_EAGER=1 to disable CUDA Graphs capture in production.
# Same bisection-primitive pattern as PHASE6B1_USE_DECODE_BATCHED and
# PHASE6B2_INSTALL_HOOK.
_FORCE_EAGER_ENV = "PHASE6B3_FORCE_EAGER"


def _resolve_enforce_eager(requested: Optional[bool]) -> bool:
    """Resolve the effective enforce_eager value, honoring the
    PHASE6B3_FORCE_EAGER env kill-switch.

    Priority order:
      1. If PHASE6B3_FORCE_EAGER=1 (or 'true', 'yes'): force True regardless.
      2. Else if caller passed an explicit value: honor it.
      3. Else: default to False (post-6B.3, captures CUDA Graphs).

    Returns the resolved bool.
    """
    raw = os.environ.get(_FORCE_EAGER_ENV, "").strip()
    if raw in ("1", "true", "True", "yes", "Yes"):
        return True
    if requested is not None:
        return requested
    return False


# Phase 6K.15 — swap-preemption guard. The paged writer's sidecars
# (k_scale/k_xmin/k_protect/v_scale/v_xmin externals + per-slot K staging)
# live OUTSIDE vLLM's paged KV tensor and are NOT migrated by the V0
# CacheEngine swap_out/swap_in path. If the scheduler swap-preempts a
# sequence, its GPU blocks round-trip through CPU but the sidecars are
# dropped/stale -> silent KV corruption on resume. Recompute-style
# preemption is safe: the KV is re-prefilled from scratch and the
# 6K.9/6K.14 evictions reset the writer's per-seq state. vLLM V0's
# DEFAULT policy picks SWAP for multi-seq groups (parallel sampling /
# beam search), so "leave it unset" is not safe — the factory forces
# preemption_mode="recompute" and refuses an explicit "swap" loudly.
# INT4_PROTECTED_ALLOW_SWAP=1 bypasses the refusal (deliberate breakage
# repro / future sidecar-migration work) with a warning.
_ALLOW_SWAP_ENV = "INT4_PROTECTED_ALLOW_SWAP"
_VALID_PREEMPTION_MODES = ("recompute", "swap")


def _allow_swap_override() -> bool:
    raw = os.environ.get(_ALLOW_SWAP_ENV, "").strip()
    return raw in ("1", "true", "True", "yes", "Yes")


def _resolve_preemption_mode(requested: Optional[str]) -> str:
    """Resolve the effective vLLM ``preemption_mode`` for int4_protected.

    Priority order:
      1. None (caller didn't choose): force "recompute" — vLLM's dynamic
         default may pick SWAP, which corrupts the non-migrated sidecars.
      2. "recompute": honored.
      3. "swap": REFUSED (RuntimeError) unless INT4_PROTECTED_ALLOW_SWAP
         is set, in which case it is honored with a loud warning.
      4. Anything else: ValueError (fail fast with the valid options).

    Returns the resolved mode string to pass to vllm.LLM.
    """
    if requested is None:
        return "recompute"
    mode = requested.strip().lower()
    if mode not in _VALID_PREEMPTION_MODES:
        raise ValueError(
            f"preemption_mode={requested!r} is not valid; expected one of "
            f"{_VALID_PREEMPTION_MODES} (int4_protected default: 'recompute')."
        )
    if mode == "swap":
        if _allow_swap_override():
            logger.warning(
                "int4_protected: preemption_mode='swap' allowed by "
                "%s=1 — the paged writer's sidecars are NOT migrated on "
                "swap; any swap-preempted sequence WILL resume with "
                "corrupted KV. This is for breakage repro / migration "
                "development only.", _ALLOW_SWAP_ENV,
            )
            return "swap"
        raise RuntimeError(
            "int4_protected does not support preemption_mode='swap': the "
            "quantization sidecars (scales/xmin/protect/staging) live "
            "outside vLLM's paged KV tensor and are not migrated by "
            "CacheEngine swap_out/swap_in, so swapped sequences resume "
            "with corrupted KV. Use preemption_mode='recompute' (the "
            "factory default), or set " + _ALLOW_SWAP_ENV + "=1 to bypass "
            "this guard for deliberate breakage reproduction."
        )
    return "recompute"


# Phase 6K.16 — prefix-caching guard (factory side). The storage layer is
# APC-compatible by construction (block-local quantization: group_size ==
# block_size == 32, sidecars keyed by global block_id so shared blocks
# carry their scales/xmin/protect with them), but the prefill-with-context
# ATTENTION path is not: it would read the int4-packed paged cache as bf16.
# The backend ALSO refuses at the exact branch (phase5b_backend_install);
# this factory check just fails at init instead of on the first cache-hit
# request. Same env escape hatch as the backend-side guard.
# Full implementation plan: Bench/scripts/PHASE6K16_PREFIX_CACHING_PLAN.md
_ALLOW_PREFIX_CACHING_ENV = "INT4_PROTECTED_ALLOW_PREFIX_CACHING"


def _allow_prefix_caching_override() -> bool:
    raw = os.environ.get(_ALLOW_PREFIX_CACHING_ENV, "").strip()
    return raw in ("1", "true", "True", "yes", "Yes")


def _resolve_prefix_caching(requested: Optional[bool]) -> bool:
    """Resolve the effective ``enable_prefix_caching`` for int4_protected.

    Priority order:
      1. None / False (caller didn't opt in): False — explicit, so the
         engine arg is self-documenting in init logs.
      2. True: REFUSED (RuntimeError) unless INT4_PROTECTED_ALLOW_PREFIX_
         CACHING is set, in which case honored with a loud warning (the
         backend's prefix-prefill branch then runs UNSUPPORTED math).
    """
    if not requested:
        return False
    if _allow_prefix_caching_override():
        logger.warning(
            "int4_protected: enable_prefix_caching=True allowed by %s=1 — "
            "routing prefix prefill through the Tier-1 dequant-context path "
            "(phase6k16_prefix_prefill). Implemented + CPU-verified, NOT yet "
            "GPU-gate-validated: run Bench/scripts/phase6k16_prefix_gates.py.",
            _ALLOW_PREFIX_CACHING_ENV,
        )
        return True
    raise RuntimeError(
        "int4_protected: enable_prefix_caching=True is gated. The Tier-1 "
        "dequant-context prefill path is IMPLEMENTED (cached blocks are "
        "dequantized, protect channels exact) but not GPU-validated yet — "
        "set " + _ALLOW_PREFIX_CACHING_ENV + "=1 to enable it, then run "
        "Bench/scripts/phase6k16_prefix_gates.py (GATE-HITS / GATE-AGREEMENT "
        "/ GATE-NEEDLE). Plan + flip-the-default criteria: "
        "PHASE6K16_PREFIX_CACHING_PLAN.md."
    )


def Int4ProtectedLLM(
    model: str,
    *,
    block_size: int = _REQUIRED_BLOCK_SIZE,
    kv_cache_dtype: str = "int4_protected",
    max_model_len: int = 4096,
    gpu_memory_utilization: float = 0.5,
    enforce_eager: Optional[bool] = None,
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
        max_model_len, gpu_memory_utilization: forwarded to LLM with
            v1-recommended defaults.
        enforce_eager: Phase 6B.3 — defaults to None (meaning "let the
            factory decide"). When None, the factory uses False (CUDA
            Graphs capture enabled). When explicit True/False, the
            caller's value is honored. The PHASE6B3_FORCE_EAGER env
            kill-switch overrides EITHER path and forces eager mode
            (used by the 6B.3 GPU smoke's eager cell + by operators
            who need to bisect a capture regression in production).
        preemption_mode (via **kwargs): Phase 6K.15 — forced to
            "recompute" for int4_protected (vLLM's dynamic default may
            pick SWAP for multi-seq groups, and the writer's sidecars
            are NOT migrated on swap -> silent KV corruption on resume).
            Passing "swap" raises unless INT4_PROTECTED_ALLOW_SWAP=1.
            NB: recompute + parallel sampling (n>1 / beam) under
            preemption pressure hits vLLM V0's single-seq recompute
            assert — a LOUD failure, never silent corruption.
        enable_prefix_caching (via **kwargs): Phase 6K.16 — forced to
            False for int4_protected; True raises unless
            INT4_PROTECTED_ALLOW_PREFIX_CACHING=1 (the prefix-prefill
            branch would read the packed cache as bf16). Plan:
            PHASE6K16_PREFIX_CACHING_PLAN.md.
        **kwargs: anything else accepted by `vllm.LLM`.

    Raises:
        ValueError: if block_size != 32 and kv_cache_dtype is the
            int4_protected variant; or if preemption_mode is not one of
            "recompute" / "swap".
        RuntimeError: if preemption_mode="swap" is requested for
            int4_protected without INT4_PROTECTED_ALLOW_SWAP=1.
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

    # Phase 6B.3 — resolve enforce_eager with env-override priority.
    effective_enforce_eager = _resolve_enforce_eager(enforce_eager)

    # Phase 6K.15 — swap-preemption guard. Only when actually running the
    # int4_protected backend: a stock run via this factory
    # (kv_cache_dtype="auto") keeps vLLM's own preemption policy.
    _requested_preemption = kwargs.pop("preemption_mode", None)
    if kv_cache_dtype == "int4_protected":
        kwargs["preemption_mode"] = _resolve_preemption_mode(_requested_preemption)
    elif _requested_preemption is not None:
        kwargs["preemption_mode"] = _requested_preemption

    # Phase 6K.16 — prefix-caching guard, same gating shape as 6K.15.
    _requested_apc = kwargs.pop("enable_prefix_caching", None)
    _apc_resolved = False
    if kv_cache_dtype == "int4_protected":
        _apc_resolved = _resolve_prefix_caching(_requested_apc)
        kwargs["enable_prefix_caching"] = _apc_resolved
        # Contract C-ID refusal is armed AFTER engine construction + hook
        # install (below) — engine init runs CUDA-graph capture WARM-UPS
        # (dummy decode batches, hook not yet installed, some outside the
        # capturing stream) where block-local placeholders are by-design.
        #
        # APC is EAGER-ONLY (measured): the captured-graph decode replay
        # corrupts cache-hit sequences' partial K-tails (degenerate output,
        # needle MISS — gates run on Llama-3.1-8B), while eager B=1/B=6
        # cells pass the contract (S1 byte-exact, warm/needle 1.000,
        # coherent texts). Until the replay path is fixed and re-gated,
        # APC forces enforce_eager=True; combining APC with CUDA graphs
        # is refused loudly. Override (dev only):
        # INT4_PROTECTED_APC_ALLOW_GRAPHS=1.
        if _apc_resolved:
            _allow_graphs = os.environ.get(
                "INT4_PROTECTED_APC_ALLOW_GRAPHS", "").strip() in (
                "1", "true", "yes")
            if not effective_enforce_eager and not _allow_graphs:
                if enforce_eager is False:
                    # Caller EXPLICITLY asked for graphs + APC: refuse.
                    raise RuntimeError(
                        "int4_protected APC is EAGER-ONLY: the captured-"
                        "graph decode replay corrupts cache-hit sequences' "
                        "partial K-tails (measured: degenerate output + "
                        "needle MISS on the graphs cell; eager cells pass "
                        "the contract). Pass enforce_eager=True (or omit "
                        "enforce_eager), or set "
                        "INT4_PROTECTED_APC_ALLOW_GRAPHS=1 for development."
                    )
                logger.warning(
                    "int4_protected: APC enabled -> forcing "
                    "enforce_eager=True (APC is eager-only; the captured "
                    "decode replay is not yet APC-safe)."
                )
                effective_enforce_eager = True
    elif _requested_apc is not None:
        kwargs["enable_prefix_caching"] = _requested_apc

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

    llm = LLM(
        model=model,
        block_size=block_size,
        kv_cache_dtype=kv_cache_dtype,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=effective_enforce_eager,
        **kwargs,
    )

    # Phase 6K.10 fix: auto-install the Phase 6B.2 precapture hook for
    # CUDA-graph mode. The hook performs the per-step SeqState->device-pool
    # sync by wrapping execute_model OUTSIDE the captured graph. Under graph
    # replay the captured decode region cannot run that host-side sync
    # (write_decode_batched only syncs on the non-capture path), so WITHOUT
    # the hook the device pools are never synced from the prefill SeqState
    # and the captured decode reads unsynced pools -> pérdida collapse
    # (phase6k10: "sync fired 0x during requests"). The hook was only ever
    # installed by bench scripts, so the PUBLIC factory's graph decode was
    # silently broken. Install it here so graph mode works out of the box.
    # Eager normally doesn't need it (write_decode_batched syncs inline) ->
    # skip. EXCEPTION (Phase 6K.16c): with prefix caching ON, the hook is
    # what stashes the stable real seq ids the eager write/read paths use,
    # so it must be installed in eager mode too.
    # Best-effort: never fail the factory on a hook-install error. A/B
    # toggle: PHASE6K10_AUTO_HOOK=0.
    _auto_hook = os.environ.get(
        "PHASE6K10_AUTO_HOOK", "1"
    ).strip().lower() not in ("0", "false", "no")
    _apc_on = bool(kwargs.get("enable_prefix_caching"))
    if (kv_cache_dtype == "int4_protected"
            and (not effective_enforce_eager or _apc_on)
            and _auto_hook):
        try:
            from kv_policy.phase6b2_precapture_hook import (
                install_int4_protected_precapture_hook,
                _collect_writers,
                _collect_impls,
                _resolve_inner_model,
                _resolve_model_runner,
            )
            _model = _resolve_inner_model(llm)
            _hook = install_int4_protected_precapture_hook(
                _resolve_model_runner(llm),
                _collect_writers(_model),
                impls=_collect_impls(_model),
            )
            # Retain a reference so the hook isn't GC'd (its teardown would
            # revert the execute_model wrap).
            setattr(llm, "_int4_protected_precapture_hook", _hook)
            logger.info(
                "Int4ProtectedLLM: precapture hook auto-installed for "
                "CUDA-graph decode."
            )
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning(
                "Int4ProtectedLLM: precapture hook auto-install FAILED "
                "(%s: %s). CUDA-graph decode may collapse; pass "
                "enforce_eager=True or install the hook manually.",
                type(e).__name__, e,
            )

    # Phase 6K.16c — ARM the contract C-ID refusal now that the engine is
    # built and the rid-stashing hook is installed: from here on, a LIVE
    # step without the rid stash under APC raises instead of silently
    # using block-local identity. (Armed even if hook install failed —
    # the resulting loud first-decode error is the correct outcome.)
    if _apc_resolved:
        from kv_policy.phase5b_4c_paged_writer import set_apc_active
        set_apc_active(True)
        logger.info("Int4ProtectedLLM: APC contract refusal armed "
                    "(post-init; capture warm-ups exempt by construction).")

    return llm


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
