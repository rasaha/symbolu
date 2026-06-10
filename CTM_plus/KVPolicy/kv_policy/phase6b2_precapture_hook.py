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
# Phase 6K.16c — real per-sequence id extraction (for prefix caching).
#
# Only the execute_model wrap sees model_input, which carries the real
# vLLM seq ids. We extract them in ATTENTION-ROW ORDER and stash an
# ordered list on attn_metadata; the write/read paths consult it (with a
# count-check fallback to block-local). vLLM 0.7.3 V0 default has no
# chunked prefill, so a step is all-prefill OR all-decode — one ordered
# list per step is sufficient.
#
# Source preference (defensive — the consumer count-checks, so a wrong
# guess degrades to block-local, never corrupts):
#   1. model_input.sampling_metadata.seq_groups[*].seq_ids  (flattened)
#   2. model_input.request_ids_to_seq_ids (dict; values flattened)
# Returns None when neither is available/usable.
# ---------------------------------------------------------------------- #


def extract_real_seq_ids(model_input: Any) -> Optional[List[int]]:
    """Ordered real seq ids for this step's attention rows, or None."""
    # 1. sampling_metadata.seq_groups — the canonical V0 per-group order.
    sm = getattr(model_input, "sampling_metadata", None)
    seq_groups = getattr(sm, "seq_groups", None) if sm is not None else None
    if seq_groups:
        out: List[int] = []
        ok = True
        for g in seq_groups:
            sids = getattr(g, "seq_ids", None)
            if sids is None:
                ok = False
                break
            out.extend(int(s) for s in sids)
        if ok and out:
            return out
    # 2. request_ids_to_seq_ids fallback (ordered dict of lists).
    r2s = getattr(model_input, "request_ids_to_seq_ids", None)
    if isinstance(r2s, dict) and r2s:
        out = []
        for sids in r2s.values():
            try:
                out.extend(int(s) for s in sids)
            except TypeError:
                out.append(int(sids))
        if out:
            return out
    return None


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
    impls: Optional[List[Any]] = None,
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
    # 6K.16c: prefer the STABLE real-seq-id stash (set by _wrapped above);
    # else 6K.16b block-local (backing-skip) / legacy [:,0]. MUST match
    # the write/read-path derivations exactly — the pool counters synced
    # below are keyed by these ids.
    from kv_policy.phase5b_4c_paged_writer import (
        block_local_seq_ids_enabled as _bl_ids,
        resolve_decode_seq_ids as _resolve_ids,
    )
    _primary_w = writers[0] if writers else None
    seq_ids = _resolve_ids(
        attn_metadata, block_tables,
        getattr(dec_meta, "seq_lens_tensor", None),
        int(_primary_w.BS) if _primary_w is not None else 32,
        block_local=(_primary_w is not None and _bl_ids(_primary_w)),
    )

    # The hook fires from `worker.execute_model` -> our wrap, which
    # runs OUTSIDE vLLM's `@torch.inference_mode()` decorator (that
    # decorator sits on `model_runner.execute_model`, downstream of
    # our wrap). The writer's pool tensors were allocated INSIDE
    # inference_mode during the first forward pass and so carry the
    # "inference tensor" attribute. PyTorch rejects in-place writes
    # to inference tensors outside inference_mode (see
    # https://github.com/pytorch/rfcs/pull/17), so we enter inference_
    # mode explicitly here for the pool mutations + the device tensor
    # build. The wrapped original_fn re-enters inference_mode on its
    # own; the nested context is a no-op there.
    with torch.inference_mode():
        # Phase 6K.14: GC first. Free slots held by sequences that are no
        # longer in the running set (completed or recompute-preempted)
        # BEFORE allocating slots for this step. The decode batch in vLLM
        # V0 is exactly the running set, so any assigned slot whose seq_id
        # is absent from `seq_ids` has finished. Without this, the
        # ensure_seq_state loop below leaks one slot per distinct seq_id
        # across decode waves until the pool exhausts ("slot pool
        # exhausted" at high B — the Phase 6K.13 finding). gc_completed_
        # slots self-gates on $PHASE6K14_EVICT_ON_DECODE. This is the
        # graph/hook path; the eager self-resolve path mirrors it.
        _active_set = set(seq_ids)
        for w in writers:
            if w._allocated:
                w.gc_completed_slots(_active_set)

        # Step 1: ensure SeqState exists on EVERY writer for each
        # seq_id. All writers see seq_ids in the same order; each
        # writer's _free_slots is popped in the same order; so the
        # _slot_map mappings align deterministically.
        from kv_policy.phase5b_4c_paged_writer import is_pad_seq_id as _is_pad
        for sid in seq_ids:
            if _is_pad(sid):
                continue   # contract B2: pads never create SeqStates
            for w in writers:
                if w._allocated:
                    w.ensure_seq_state(sid, device)

        # Step 2: resolve slot_idx_list once. All writers have the
        # same mapping after step 1 (verified by Day 1's CPU tests).
        primary = writers[0] if writers else None
        if primary is None or not primary._allocated:
            # Defensive: nothing to resolve. Caller will fall back to
            # self-resolve.
            return {}
        slot_idx_list = primary.slot_indices_for(seq_ids)

        # Step 3: sync every writer's pool counters once (sentinel-
        # gated; only fires on slots whose decode-side state is still
        # pristine).
        for w in writers:
            if w._allocated:
                w._sync_pool_counters_from_states(slot_idx_list)

        # Step 4: build the device tensor once.
        slot_idx_t = torch.tensor(
            slot_idx_list,
            dtype=torch.long,
            device=device,
        )

        # Phase 6B.3 (Option X) Step 5: populate each impl's persistent
        # _phase5b_slot_idx_buf with the resolved slot indices. The
        # buffer's address was used by the captured graph at capture
        # time (engine init), so each replay needs the values fresh.
        # vLLM doesn't repopulate this buffer for us — it's our
        # internal state.
        #
        # For non-captured shapes (eager fallback), the dispatch fork
        # will ALSO populate the buffer; this duplicate write is
        # harmless (same value).
        if impls:
            B = len(slot_idx_list)
            for impl in impls:
                buf = getattr(impl, "_phase5b_slot_idx_buf", None)
                if buf is None:
                    continue
                # Buffer may not have been sized yet (impl hasn't seen
                # a forward call). _ensure_index_bufs grows it on demand
                # at dispatch time; here we skip and let the dispatch
                # fork allocate on first eager call.
                if buf.numel() < B:
                    continue
                buf[:B].copy_(slot_idx_t, non_blocking=True)

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
    install_time_impls     — list of Int4ProtectedAttentionImpl refs (Phase
                             6B.3 Option X). Hook populates each impl's
                             _phase5b_slot_idx_buf at production replay
                             time so captured graphs read the right values.
    stash_call_count       — incremented per hook invocation (for verification)
    skipped_step_count     — incremented when a step is not pure-decode (no-op)
    _teardowns             — LIFO closure list reverting the monkey-patch
    _torn_down             — idempotency flag
    """

    enabled: bool
    hook_target_name: str
    install_time_writers: List[Any] = field(default_factory=list)
    install_time_impls:   List[Any] = field(default_factory=list)
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


def _collect_impls(model: Any) -> List[Any]:
    """Phase 6B.3 (Option X) — walk model.named_modules() and collect
    every Int4ProtectedAttentionImpl instance reference. Returns
    list in named_modules() iteration order (== layer 0..N).

    Hook needs impl refs (not just writer refs) so it can populate
    each impl's _phase5b_slot_idx_buf persistent buffer at production
    replay time. The captured graph recorded its slot_idx_t reads
    against that buffer's address; vLLM doesn't repopulate it for us.
    """
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    impls: List[Any] = []
    for _, sub in model.named_modules():
        impl = getattr(sub, "impl", None)
        if isinstance(impl, Int4ProtectedAttentionImpl):
            impls.append(impl)
    return impls


def install_int4_protected_precapture_hook(
    model_runner: Any,
    writers: List[Any],
    *,
    impls: Optional[List[Any]] = None,
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
        install_time_impls=list(impls) if impls else [],
    )

    def _trace_counters(w, sids):
        """Host-side snapshot of the layer-0 writer's per-seq tail state."""
        out = {}
        for sid in sids:
            slot = w._slot_map.get(sid)
            if slot is None:
                out[str(sid)] = None
                continue
            st = w._seq_states.get(sid)
            out[str(sid)] = {
                "slot": slot,
                "state_ints": [st.k_stage_count, st.k_stage_block_id]
                if st is not None else None,
                "pool": [int(w._k_stage_count_pool[slot]),
                         int(w._k_stage_block_id_pool[slot]),
                         int(w._seq_pos_pool[slot])],
            }
        return out

    def _trace_dump(record):
        import json as _json
        from kv_policy.phase5b_4c_paged_writer import rt_path
        p = rt_path()
        if not p:
            return
        try:
            with open(p, "a") as f:
                f.write(_json.dumps(record) + "\n")
        except Exception as _e:
            logger.warning("replay-trace write failed: %s", _e)

    def _wrapped(model_input, kv_caches, *args, **kwargs):
        attn_metadata = getattr(model_input, "attn_metadata", None)
        # ---- 6K.16d replay-trace (env-gated; never breaks the forward) ----
        from kv_policy.phase5b_4c_paged_writer import (
            rt_path as _rt_path, rt_drain_events as _rt_drain,
            rt_tensor_sig as _rt_sig, is_pad_seq_id as _rt_is_pad,
        )
        _tracing = bool(_rt_path())
        _t_pre = None

        def _trace_w0():
            # TRACE-ONLY lazy writer resolution: in eager mode the factory
            # collects writers before any forward has created them, so
            # install_time_writers is empty — fall back to the impls'
            # lazily-created writers. Does NOT affect production resolve.
            w = next((w for w in handle.install_time_writers
                      if w._allocated), None)
            if w is not None:
                return w
            for impl in (handle.install_time_impls or []):
                cand = getattr(impl, "_phase5b_paged_writer", None)
                if cand is not None and getattr(cand, "_allocated", False):
                    return cand
            return None

        if _tracing:
            try:
                handle.trace_step = getattr(handle, "trace_step", -1) + 1
                w0 = _trace_w0()
                dec = getattr(attn_metadata, "decode_metadata", None) \
                    if attn_metadata is not None else None
                _t_pre = {
                    "step": handle.trace_step, "phase": "pre",
                    "is_decode": _is_pure_decode_step(attn_metadata),
                    "stash_calls": handle.stash_call_count,
                    "attn_meta_id": id(attn_metadata),
                    "alloc_events": _rt_drain(),
                }
                if w0 is not None:
                    _t_pre["pool_ids"] = {
                        "k_stage_pool": id(w0._k_stage_pool),
                        "count_pool": id(w0._k_stage_count_pool),
                        "block_pool": id(w0._k_stage_block_id_pool),
                    }
                    _t_pre["live_sids"] = list(w0._slot_map.keys())
                    _t_pre["counters_presync"] = _trace_counters(
                        w0, list(w0._slot_map.keys()))
                if dec is not None and getattr(dec, "block_tables", None) \
                        is not None and dec.block_tables.numel() > 0:
                    _t_pre["seq_lens"] = dec.seq_lens_tensor.cpu().tolist()
                    _t_pre["seq_lens_id"] = id(dec.seq_lens_tensor)
                    _t_pre["bt_id"] = id(dec.block_tables)
                    _bt = dec.block_tables.cpu()
                    _t_pre["bt_tail"] = [
                        r[max(0, (int(s) - 1) // 32 - 1):(int(s) - 1) // 32 + 1]
                        .tolist()
                        for r, s in zip(_bt, _t_pre["seq_lens"])]
                _sm = getattr(attn_metadata, "slot_mapping", None)
                if _sm is not None and _sm.numel() <= 64:
                    _t_pre["slot_mapping"] = _sm.cpu().tolist()
            except Exception as _e:
                logger.warning("replay-trace pre failed: %s", _e)
                _t_pre = None
        # Phase 6K.16c: stash real seq ids in attention-row order on EVERY
        # step (prefill OR decode), so the write/read paths can use stable
        # identity under prefix caching. Decode -> _int4_real_seq_ids;
        # prefill -> _int4_real_seq_ids_prefill (one per prompt segment).
        # Best-effort; the consumers count-check and fall back to
        # block-local. Skipped silently when extraction yields nothing.
        if attn_metadata is not None:
            try:
                from kv_policy.phase5b_4c_paged_writer import (
                    _REAL_SEQ_IDS_ATTR, _REAL_SEQ_IDS_PREFILL_ATTR,
                )
                real_ids = extract_real_seq_ids(model_input)
                is_dec = _is_pure_decode_step(attn_metadata)
                if real_ids is not None:
                    setattr(attn_metadata,
                            _REAL_SEQ_IDS_ATTR if is_dec
                            else _REAL_SEQ_IDS_PREFILL_ATTR,
                            real_ids)
                if os.environ.get("INT4_PROTECTED_PREFIX_DEBUG", "").strip() \
                        in ("1", "true", "yes"):
                    n = None if real_ids is None else len(real_ids)
                    head = None if real_ids is None else real_ids[:6]
                    logger.warning("[6K.16c-dbg] %s step: extract -> count=%s "
                                   "head=%s", "decode" if is_dec else "prefill",
                                   n, head)
            except Exception as _e:  # never break the forward over this
                logger.warning("6K.16c seq-id stash skipped: %s", _e)
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
                    impls=handle.install_time_impls or None,
                )
                handle.stash_call_count += 1
            else:
                handle.skipped_step_count += 1
        else:
            handle.skipped_step_count += 1
        if _t_pre is not None:
            # post-sync counter view + the stash's resolved ids/slots.
            try:
                w0 = _trace_w0()
                if w0 is not None:
                    _t_pre["counters_postsync"] = _trace_counters(
                        w0, list(w0._slot_map.keys()))
                stash = read_stash(attn_metadata) or {}
                _t_pre["stash_seq_ids"] = stash.get("seq_ids")
                _sit = stash.get("slot_idx_t")
                _t_pre["stash_slot_idx_id"] = id(_sit) if _sit is not None else None
                _impl0 = (handle.install_time_impls or [None])[0]
                if _impl0 is not None:
                    _b = getattr(_impl0, "_phase5b_slot_idx_buf", None)
                    _t_pre["impl0_slot_buf_id"] = id(_b) if _b is not None else None
                    if _b is not None and _b.numel() <= 64:
                        _t_pre["impl0_slot_buf"] = _b.cpu().tolist()
            except Exception as _e:
                logger.warning("replay-trace stash-view failed: %s", _e)
            _trace_dump(_t_pre)
        _out = original_fn(model_input, kv_caches, *args, **kwargs)
        if _t_pre is not None:
            try:
                import torch as _torch
                _torch.cuda.synchronize()
                w0 = _trace_w0()
                rec = {"step": _t_pre["step"], "phase": "post"}
                if w0 is not None:
                    sids = [s for s in w0._slot_map.keys()
                            if not _rt_is_pad(s)]
                    rec["counters_post"] = _trace_counters(w0, sids)
                    rec["stage_sig"] = {}
                    for sid in sids:
                        slot = w0._slot_map.get(sid)
                        if slot is not None:
                            rec["stage_sig"][str(sid)] = _rt_sig(
                                w0._k_stage_pool[slot])
                    # crossing detection: a seq whose count dropped to 0
                    # this step finalized block X (its PRE block id) — dump
                    # the finalized block's bytes (S1-style, layer 0).
                    # v4: the replayed READ's transient output — the spliced
                    # view (graph-pool memory, stable address, refreshed by
                    # every replay). Slice each live row's LAST block (the
                    # tail) — comparable across eager-one and graphs-batched.
                    _impl0 = (handle.install_time_impls or [None])[0]
                    refs = getattr(_impl0, "_rt_read_refs", None) \
                        if _impl0 is not None else None
                    if refs is not None:
                        try:
                            BSr = refs["BS"]
                            csl = refs["cache_seqlens"]
                            rec["read_cache_seqlens"] = \
                                csl.cpu().tolist()[:8]
                            sit = refs.get("slot_idx")
                            rec["read_slot_idx"] = (
                                sit.cpu().tolist()[:8] if sit is not None
                                else None)
                            ki, ks = refs["k_int4"], refs["k_scale"]

                            def _psig(t, sl=None):
                                # Per-field guard: a shape surprise on a v5
                                # field must not wipe the v4 view_tail data.
                                try:
                                    if t is None:
                                        return None
                                    x = t if sl is None else t[sl]
                                    return _rt_sig(
                                        x.float() if x.is_floating_point()
                                        else x)
                                except Exception:
                                    return None

                            kp = refs.get("k_protect_bf16")
                            ps = refs.get("protect_slot")
                            bk = refs.get("bf16_k")
                            vk = refs.get("v_kernel")
                            ou = refs.get("out")
                            rec["view_tail"] = {}
                            for row, s in enumerate(
                                    rec["read_cache_seqlens"]):
                                if row >= ki.shape[0] or s <= 0:
                                    continue
                                lb = (int(s) - 1) // BSr
                                a, b2 = lb * BSr, (lb + 1) * BSr
                                if b2 <= ki.shape[1]:
                                    ent = {
                                        "last_block": lb,
                                        "k_int4": _rt_sig(
                                            ki[row, a:b2].float()),
                                        "k_scale": _rt_sig(ks[row, lb]
                                                           if ks.dim() == 4
                                                           else ks[row]),
                                        # v5: the unobserved kernel surface.
                                        # protect_bf16/protect_slot = the
                                        # protected-channel overlay; bf16_k =
                                        # the positional bf16 K backing/stub;
                                        # v_kernel = the V the kernel read;
                                        # out = the per-row attention result
                                        # (the integral screen).
                                        "k_protect_bf16": _psig(
                                            kp, row if kp is not None
                                            else None),
                                        "protect_slot": _psig(
                                            ps, row if ps is not None
                                            else None),
                                        "bf16_k": _psig(
                                            bk, (row, slice(a, b2))
                                            if (bk is not None
                                                and bk.dim() >= 2
                                                and b2 <= bk.shape[1])
                                            else (row if bk is not None
                                                  else None)),
                                        "v_kernel": _psig(
                                            vk, (row, slice(a, b2))
                                            if (vk is not None
                                                and vk.dim() >= 2
                                                and b2 <= vk.shape[1])
                                            else (row if vk is not None
                                                  else None)),
                                        "out": _psig(
                                            ou, row if ou is not None
                                            else None),
                                    }
                                    rec["view_tail"][str(row)] = ent
                        except Exception as _e2:
                            rec["view_tail_error"] = str(_e2)[:80]
                    pre_c = _t_pre.get("counters_postsync") or {}
                    kvc = kv_caches[0] if kv_caches is not None and len(
                        kv_caches) > 0 else None
                    if kvc is not None and kvc.numel() > 0:
                        rec["finalized"] = {}
                        for sid in sids:
                            a = pre_c.get(str(sid))
                            b = rec["counters_post"].get(str(sid))
                            if (a and b and a["pool"][0] > 0
                                    and b["pool"][0] == 0):
                                X = a["pool"][1]
                                if X >= 0:
                                    rec["finalized"][str(sid)] = {
                                        "block": X,
                                        "packed_k": _rt_sig(
                                            kvc[0, X, :, :, :w0.D // 2]),
                                        "k_scale": _rt_sig(w0.k_scale_ext[X]),
                                    }
            except Exception as _e:
                logger.warning("replay-trace post failed: %s", _e)
                rec = {"step": _t_pre["step"], "phase": "post", "error": str(_e)}
            _trace_dump(rec)
        return _out

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
    impls   = _collect_impls(model)   # Phase 6B.3 Option X — hook
                                       # populates impl persistent buffers

    model_runner = _resolve_model_runner(llm)
    hook = install_int4_protected_precapture_hook(
        model_runner, writers, impls=impls,
    )

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
