"""Phase 6B.2 — pre-capture seq_id resolution hook.

Installs a wrap on ``ModelRunner.execute_model`` that resolves
``seq_id -> slot_idx_t`` ONCE per step BEFORE the captured forward
runs, then stashes the result on ``attn_metadata`` for the per-layer
``Int4ProtectedAttentionImpl.forward`` dispatch fork to read.

This closes the one remaining pre-capture host-sync that Phase 6B.1
left exempt inside ``write_decode_batched``
(``slot_idx_t.cpu().tolist()`` + ``_sync_pool_counters_from_states``).
With the hook installed, the dispatch fork bypasses self-resolution
entirely; the captured region is host-sync-free.

Backward-compat: when this hook is NOT installed (CPU tests; pre-
hook deployments; PHASE6B2_INSTALL_HOOK=0), the dispatch fork falls
back to Phase 6B.1's self-resolution path. Strictly additive.

Install pattern mirrors ``swap_telemetry.install_swap_in_latency_probe``
(TIER5A.4 precedent): setattr-based bound-method substitution + LIFO
teardown closures + inert handle on resolver failure.

See `Bench/scripts/PHASE_6B2_PRECAPTURE_HOOK_DESIGN.md` for the
design + acceptance gate (G_HOOK).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

logger = logging.getLogger(__name__)


# Stash key on attn_metadata. The dispatch fork reads this exact
# attribute name. Namespaced to avoid collisions with anything vLLM
# may add later.
STASH_ATTR = "_int4_protected_precapture"

# Hook version embedded in the stash payload. Future 6B.x bumps can
# detect stale stashes (e.g., if a hot reload swaps the impl class but
# not the hook); for now the version is informational.
HOOK_VERSION = "6B.2_v1"

# Env override: PHASE6B2_INSTALL_HOOK=0 forces install to return an
# inert handle. Used by the GPU smoke to capture a "hook-off"
# reference cell from the same process tree where the "hook-on" cell
# runs. Same bisection-primitive pattern as 6B.1's
# PHASE6B1_USE_DECODE_BATCHED.
_HOOK_ENABLED_ENV = "PHASE6B2_INSTALL_HOOK"


# Module-level fallback stash dict for slot-class attn_metadata that
# refuses setattr. Keyed by id(attn_metadata); the dispatch fork
# checks this dict if the attribute is missing. Memory footprint is
# bounded because entries are dropped at the end of each step (see
# ``read_stash`` cleanup).
_FALLBACK_STASH: Dict[int, Dict[str, Any]] = {}


def _hook_enabled() -> bool:
    """Returns True iff the hook should install. Honors env override."""
    raw = os.environ.get(_HOOK_ENABLED_ENV, "1").strip()
    return raw not in ("0", "false", "False", "no", "No")


# ---------------------------------------------------------------------- #
# Stash helpers — read by the dispatch fork; written by the hook
# ---------------------------------------------------------------------- #


def write_stash(attn_metadata: Any, payload: Dict[str, Any]) -> bool:
    """Write the pre-capture payload onto attn_metadata.

    Tries setattr first; on AttributeError (slot-class metadata),
    falls back to a module-level dict keyed by id(attn_metadata).
    Returns True iff the stash is reachable from read_stash.
    """
    try:
        setattr(attn_metadata, STASH_ATTR, payload)
        return True
    except AttributeError:
        # Slot-class metadata. Fall back to the module-level dict.
        _FALLBACK_STASH[id(attn_metadata)] = payload
        return True
    except TypeError:
        # Defensive: some metadata classes raise TypeError on setattr.
        _FALLBACK_STASH[id(attn_metadata)] = payload
        return True


def read_stash(attn_metadata: Any) -> Optional[Dict[str, Any]]:
    """Return the pre-capture payload if present, else None.

    Checks the namespaced attribute first; falls back to the
    module-level dict. Read-only — does NOT clear the stash.
    """
    payload = getattr(attn_metadata, STASH_ATTR, None)
    if payload is not None:
        return payload
    return _FALLBACK_STASH.get(id(attn_metadata))


def clear_stash(attn_metadata: Any) -> None:
    """Drop any pre-capture payload associated with attn_metadata.

    Called by the hook's teardown to avoid retaining device tensors
    across hook lifecycles. Idempotent.
    """
    try:
        if hasattr(attn_metadata, STASH_ATTR):
            delattr(attn_metadata, STASH_ATTR)
    except (AttributeError, TypeError):
        pass
    _FALLBACK_STASH.pop(id(attn_metadata), None)


# ---------------------------------------------------------------------- #
# Pure-decode-step predicate (matches _is_pure_decode_write from
# phase5b_backend_install, but checks the step-level shape instead
# of per-impl call shape).
# ---------------------------------------------------------------------- #


def _is_pure_decode_step(attn_metadata: Any) -> bool:
    """Returns True iff THIS step is a pure decode (one new token per
    active seq, no prefill rows). Same gating logic as 6B.1's
    `_is_pure_decode_write` but without the T_total check (the hook
    runs before the impl knows T_total)."""
    if attn_metadata is None:
        return False
    dec_meta = getattr(attn_metadata, "decode_metadata", None)
    if dec_meta is None:
        return False
    block_tables = getattr(dec_meta, "block_tables", None)
    if block_tables is None:
        return False
    if hasattr(block_tables, "numel"):
        if block_tables.numel() == 0:
            return False
    elif len(block_tables) == 0:
        return False
    max_decode_q = getattr(dec_meta, "max_decode_query_len", None)
    if max_decode_q is not None and max_decode_q > 1:
        return False
    pre_meta = getattr(attn_metadata, "prefill_metadata", None)
    if pre_meta is not None:
        n_prefill_q = getattr(pre_meta, "num_prefill_tokens", None)
        if n_prefill_q is None:
            qsl = getattr(pre_meta, "query_start_loc", None)
            if qsl is not None:
                qsl_len = qsl.numel() if hasattr(qsl, "numel") else len(qsl)
                if qsl_len > 0:
                    last = qsl[-1]
                    n_prefill_q = int(last.item()) if hasattr(last, "item") else int(last)
        if n_prefill_q is not None and n_prefill_q > 0:
            return False
    return True


# ---------------------------------------------------------------------- #
# Resolution — called by the hook before delegating to original
# execute_model. Computes slot_idx_t + syncs all writers' pool
# counters in one Python pass.
# ---------------------------------------------------------------------- #


def _resolve_and_stash(
    attn_metadata: Any,
    writers: List[Any],
    device: Any,
) -> Dict[str, Any]:
    """Resolve seq_id -> slot_idx_t and stash the result on
    attn_metadata. Idempotent on re-entry: if the stash already has
    a slot_idx_t, returns it unchanged.

    Steps:
      1. Read seq_ids from decode_metadata.block_tables[:, 0]
         (one CPU sync; pre-capture-hoistable; matches the read
         path's existing CAPTURE-EXEMPT sync at line 387-390 of
         phase5b_backend_install.py).
      2. Ensure SeqState exists for each seq_id on EVERY writer
         (one pass; writers process seq_ids in the same order so
         their _slot_maps align deterministically).
      3. Resolve slot_idx_list once (using writer[0]; all writers
         have aligned _slot_maps after step 2).
      4. Sync every writer's pool counters from its SeqState ints
         (was inside write_decode_batched in 6B.1; now hoisted).
      5. Stash payload on attn_metadata.
    """
    if torch is None:
        raise RuntimeError("Int4ProtectedPrecaptureHook requires torch")

    # Re-entry guard: a step that fires execute_model multiple times
    # (e.g., chunked-prefill intra-step) shouldn't re-resolve. Same
    # slot_idx_t is reused.
    existing = read_stash(attn_metadata)
    if existing is not None and "slot_idx_t" in existing:
        return existing

    dec_meta = attn_metadata.decode_metadata
    block_tables = dec_meta.block_tables
    # One coalesced host sync per step. Pre-capture-hoistable; the
    # captured region never sees it.
    seq_ids = block_tables[:, 0].cpu().tolist()

    # Step 1: ensure SeqState exists on EVERY writer for each seq_id.
    # All writers see seq_ids in the same order; each writer's
    # _free_slots is popped in the same order; so the _slot_map
    # mappings align deterministically.
    for sid in seq_ids:
        for w in writers:
            if w._allocated:
                w.ensure_seq_state(sid, device)

    # Step 2: resolve slot_idx_list once. All writers have the same
    # mapping after step 1 (verified by Day 1's CPU tests).
    primary = writers[0] if writers else None
    if primary is None or not primary._allocated:
        # Defensive: nothing to resolve. Caller will fall back to
        # self-resolve.
        return {}
    slot_idx_list = primary.slot_indices_for(seq_ids)

    # Step 3: sync every writer's pool counters once.
    for w in writers:
        if w._allocated:
            w._sync_pool_counters_from_states(slot_idx_list)

    # Step 4: build the device tensor once.
    slot_idx_t = torch.tensor(
        slot_idx_list,
        dtype=torch.long,
        device=device,
    )

    payload: Dict[str, Any] = {
        "slot_idx_t":   slot_idx_t,
        "seq_ids":      list(seq_ids),
        "hook_version": HOOK_VERSION,
    }
    write_stash(attn_metadata, payload)
    return payload


# ---------------------------------------------------------------------- #
# Handle dataclass
# ---------------------------------------------------------------------- #


@dataclass
class Int4ProtectedPrecaptureHook:
    """Handle returned by install_int4_protected_precapture_hook.

    enabled                — True iff the wrap is live on a target
    hook_target_name       — "execute_model" on success; descriptive on inert
    install_time_writers   — list of writer references the hook orchestrates
    stash_call_count       — incremented per hook invocation (for verification)
    skipped_step_count     — incremented when a step is not pure-decode (no-op)
    _teardowns             — LIFO closure list reverting the monkey-patch
    _torn_down             — idempotency flag
    """

    enabled: bool
    hook_target_name: str
    install_time_writers: List[Any] = field(default_factory=list)
    stash_call_count: int = 0
    skipped_step_count: int = 0
    _teardowns: List[Callable[[], None]] = field(default_factory=list)
    _torn_down: bool = False

    def teardown(self) -> None:
        """Revert the wrap in LIFO order. Idempotent."""
        if self._torn_down:
            return
        while self._teardowns:
            fn = self._teardowns.pop()
            try:
                fn()
            except Exception as exc:
                logger.warning(
                    "phase6b2_precapture_hook teardown closure failed: %s",
                    exc,
                )
        self.install_time_writers.clear()
        self._torn_down = True


# ---------------------------------------------------------------------- #
# Install — wrap ModelRunner.execute_model
# ---------------------------------------------------------------------- #


def _collect_writers(model: Any) -> List[Any]:
    """Walk model.named_modules() and collect every
    Int4ProtectedAttentionImpl's PagedKVWriter reference. Returns
    list in named_modules() iteration order (== layer 0..N).
    """
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    writers: List[Any] = []
    for _, sub in model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None:
            writers.append(w)
    return writers


def install_int4_protected_precapture_hook(
    model_runner: Any,
    writers: List[Any],
    *,
    enable: bool = True,
) -> Int4ProtectedPrecaptureHook:
    """Wrap ``model_runner.execute_model`` to stash a pre-resolved
    ``slot_idx_t`` on ``attn_metadata`` before the captured forward
    runs.

    Args:
      model_runner: object exposing ``.execute_model`` as a callable
        attribute. In vLLM 0.7.3 V0, located at
        ``llm.llm_engine.model_executor.driver_worker.model_runner``.
      writers: list of PagedKVWriter references (one per attention
        layer). Typically built via ``_collect_writers(model)``.
      enable: when False (or env PHASE6B2_INSTALL_HOOK=0), returns
        an inert handle with no monkey-patching. Used by the GPU
        smoke's hook-off cell.

    Returns:
      Int4ProtectedPrecaptureHook handle. ``teardown()`` reverts.

    Resolver behavior:
      * If ``enable=False`` or env override → inert (no wrap).
      * If ``model_runner`` lacks ``execute_model`` → inert with
        ``hook_target_name='no_execute_model_attr'``.
      * If wrap setattr fails (read-only class attr; slot conflict)
        → inert with ``hook_target_name='setattr_failed'``.
      * Otherwise → wrap installed; ``hook_target_name='execute_model'``.
    """
    if torch is None:
        raise RuntimeError("install_int4_protected_precapture_hook requires torch")

    if not enable or not _hook_enabled():
        return Int4ProtectedPrecaptureHook(
            enabled=False,
            hook_target_name="disabled",
        )

    if not hasattr(model_runner, "execute_model"):
        return Int4ProtectedPrecaptureHook(
            enabled=False,
            hook_target_name="no_execute_model_attr",
        )

    original_fn = getattr(model_runner, "execute_model")
    if not callable(original_fn):
        return Int4ProtectedPrecaptureHook(
            enabled=False,
            hook_target_name="not_callable",
        )

    handle = Int4ProtectedPrecaptureHook(
        enabled=True,
        hook_target_name="execute_model",
        install_time_writers=list(writers),
    )

    def _wrapped(model_input, kv_caches, *args, **kwargs):
        attn_metadata = getattr(model_input, "attn_metadata", None)
        if _is_pure_decode_step(attn_metadata):
            # Walk writers list ONCE per step to determine the right
            # device. All writers share the same kv_cache device.
            device = None
            for w in handle.install_time_writers:
                if w._allocated:
                    device = w._k_stage_pool.device
                    break
            if device is not None:
                _resolve_and_stash(
                    attn_metadata,
                    handle.install_time_writers,
                    device,
                )
                handle.stash_call_count += 1
            else:
                handle.skipped_step_count += 1
        else:
            handle.skipped_step_count += 1
        return original_fn(model_input, kv_caches, *args, **kwargs)

    try:
        _wrapped.__name__ = getattr(original_fn, "__name__", "execute_model")
    except (AttributeError, TypeError):
        pass

    try:
        setattr(model_runner, "execute_model", _wrapped)
    except (AttributeError, TypeError) as exc:
        logger.warning(
            "phase6b2_precapture_hook: cannot setattr execute_model on %s: %s",
            type(model_runner).__name__, exc,
        )
        return Int4ProtectedPrecaptureHook(
            enabled=False,
            hook_target_name="setattr_failed",
        )

    def _revert() -> None:
        try:
            setattr(model_runner, "execute_model", original_fn)
        except (AttributeError, TypeError) as exc:
            logger.warning(
                "phase6b2_precapture_hook revert failed: %s", exc,
            )

    handle._teardowns.append(_revert)
    logger.info(
        "phase6b2_precapture_hook installed: %d writers tracked",
        len(handle.install_time_writers),
    )
    return handle


def install_int4_protected_with_precapture_hook(
    llm: Any,
) -> Tuple[Any, "Int4ProtectedPrecaptureHook", Callable[[], None]]:
    """One-call install: backend swap (Phase 5B.2) + pre-capture hook
    (Phase 6B.2) in one shot.

    Returns:
      (backend_manager, hook_handle, combined_teardown).

    The combined_teardown reverts both in LIFO order (hook first,
    then backend swap), matching the TIER5A install lifecycle.
    """
    if torch is None:
        raise RuntimeError("install_int4_protected_with_precapture_hook requires torch")

    from kv_policy.phase5b_backend_install import install_int4_protected_backend

    model = _resolve_inner_model(llm)
    backend_manager, backend_teardown = install_int4_protected_backend(model)

    # Force lazy_alloc on every writer so writers exist and counters
    # are populated. Sentinel: a no-op forward might NOT trigger
    # lazy_alloc on every writer; the hook handles the fast path by
    # only orchestrating allocated writers (see ``_resolve_and_stash``).
    writers = _collect_writers(model)

    model_runner = _resolve_model_runner(llm)
    hook = install_int4_protected_precapture_hook(model_runner, writers)

    def combined_teardown() -> None:
        # LIFO: hook first (depends on backend), then backend.
        hook.teardown()
        backend_teardown()

    return backend_manager, hook, combined_teardown


def _resolve_inner_model(llm: Any) -> Any:
    """Walk Int4ProtectedLLM -> inner model. Mirrors the heuristic in
    audit_phase6_b_pre4_pointer_stability.py + diagnose_phase6_b_pre5_
    write_state.py."""
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    raise RuntimeError(
        "phase6b2_precapture_hook: cannot locate inner model via known accessors"
    )


def _resolve_model_runner(llm: Any) -> Any:
    """Walk Int4ProtectedLLM -> ModelRunner. The model_runner is the
    object that owns execute_model in vLLM 0.7.3 V0."""
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
    ]
    for fn in candidates:
        try:
            mr = fn(llm)
            if mr is not None and hasattr(mr, "execute_model"):
                return mr
        except (AttributeError, IndexError):
            continue
    raise RuntimeError(
        "phase6b2_precapture_hook: cannot locate ModelRunner with execute_model"
    )
