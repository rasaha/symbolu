"""Cache-aware scheduler vLLM 0.7.3 integration — Phase 1 (PR-1).

Three monkey-patches that wire the Phase 0 ``CacheAwareScheduler``
into a vLLM ``Scheduler`` + ``BlockSpaceManager`` pair:

  1. ``Scheduler.schedule`` — reorder ``self.waiting`` deque by
     predicted cache-hit rate before delegating to the original.
  2. ``BlockSpaceManager.allocate`` — measure realized cache hits
     (via the radix tree, BEFORE inserting the new prefix) and
     sync the tree with the freshly-allocated blocks.
  3. ``BlockSpaceManager.free`` — capture block_ids about to be
     freed, then evict them from the tree.

Feature flag off by default: ``enable=False`` returns a no-op
handle and applies zero patches. With ``enable=True`` the wraps are
installed and a ``CacheAwareInstall`` handle is returned with a
``teardown()`` method for LIFO revert.

Composition contract — Phase 1 explicitly does NOT touch:
  * ``Int4ProtectedAttentionImpl`` (orthogonal layer)
  * The forked ``vllm-flash-attn`` kernel (orthogonal layer)
  * Any eviction-scoring algorithm (Phase 4 retirement stands)

This module imports ``cache_aware_scheduler`` from the same
package and accepts vLLM ``scheduler`` / ``block_manager``
objects opaquely. CPU tests in
``Bench/tests/test_cache_aware_install.py`` exercise the wraps
against mock objects that match the vLLM 0.7.3 interface shape.

Design reference: ``Bench/scripts/V2_CACHE_REUSE_DESIGN.md`` +
``Bench/scripts/V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .cache_aware_scheduler import (
    CacheAwareScheduler,
    PendingRequest,
    PrefixRadixTree,
)


# ----------------------------------------------------------------------
# Handle
# ----------------------------------------------------------------------


@dataclass
class CacheAwareInstall:
    """Handle returned by ``install_cache_aware_scheduler``.

    With ``enabled=False`` (the default off path), the handle is a
    stub with no tree, no scheduler, no teardowns. Stats return
    ``{"enabled": False}``.

    With ``enabled=True``, the handle owns the live
    ``PrefixRadixTree``, the ``CacheAwareScheduler``, and the
    teardown closures for the three monkey-patches. Callers must
    invoke ``teardown()`` to revert the wraps when the engine
    shuts down — typically from the streaming runner's finally
    block (PR-2 wiring).
    """

    enabled: bool
    tree: Optional[PrefixRadixTree] = None
    cas: Optional[CacheAwareScheduler] = None
    _teardowns: List[Callable[[], None]] = field(default_factory=list)
    # Per-request predicted hits captured at schedule time, used
    # later to compute prediction_accuracy in stats(). Bounded by
    # active-request count; cleaned by .free's wrap.
    _predicted_hits_per_request: Dict[str, int] = field(default_factory=dict)
    _predicted_hits_total: int = 0
    _realized_hits_total: int = 0

    def teardown(self) -> None:
        """Revert all monkey-patches (LIFO). Safe to call multiple
        times — second call is a no-op."""
        for fn in reversed(self._teardowns):
            try:
                fn()
            except Exception:
                # Best-effort revert; never crash the engine.
                pass
        self._teardowns.clear()

    def stats(self) -> Dict[str, Any]:
        """Telemetry dict suitable for inclusion in
        ``streaming_summary.json`` (PR-2 plumbing).

        Returns ``{"enabled": False}`` when the install was a no-op.
        Otherwise includes admissions count, reorder count,
        predicted vs realized hit totals, and prediction accuracy.
        """
        if not self.enabled:
            return {"enabled": False}
        s = self.cas.stats() if self.cas is not None else {}
        predicted = self._predicted_hits_total
        realized = self._realized_hits_total
        accuracy = (realized / predicted) if predicted > 0 else 0.0
        return {
            "enabled": True,
            "admissions": s.get("admissions", 0),
            "reordered_count": s.get("reordered_count", 0),
            "starvation_overrides": s.get("starvation_overrides", 0),
            "predicted_hit_tokens_total": predicted,
            "realized_hit_tokens_total": realized,
            "prediction_accuracy": accuracy,
            "tree_inserts": s.get("tree_inserts", 0),
            "tree_evictions": s.get("tree_evictions", 0),
            "tree_tracked_tokens": s.get("tree_tracked_tokens", 0),
        }


# ----------------------------------------------------------------------
# Helpers — vLLM 0.7.3 interface adapters
# ----------------------------------------------------------------------


def _seq_from(seq_group: Any) -> Any:
    """Return the first ``Sequence`` of a ``SequenceGroup``."""
    if hasattr(seq_group, "get_seqs"):
        seqs = seq_group.get_seqs()
        if seqs:
            return seqs[0]
    return seq_group  # fallback: object IS the seq


def _tokens_of(seq_group: Any) -> List[int]:
    """Extract the prompt token ids of ``seq_group``'s first sequence."""
    seq = _seq_from(seq_group)
    if hasattr(seq, "get_prompt_token_ids"):
        return list(seq.get_prompt_token_ids())
    if hasattr(seq, "prompt_token_ids"):
        return list(seq.prompt_token_ids)
    return []


def _seq_id_of(seq: Any) -> Any:
    """Best-effort sequence id resolution.

    vLLM 0.7.3's ``Sequence`` has ``seq_id`` (int). Some mocks
    use ``id``. Fall back to Python's ``id()`` for objects with
    neither attribute.
    """
    sid = getattr(seq, "seq_id", None)
    if sid is not None:
        return sid
    sid = getattr(seq, "id", None)
    if sid is not None:
        return sid
    return id(seq)


def _seq_id_from_seq_group(seq_group: Any) -> Any:
    return _seq_id_of(_seq_from(seq_group))


def _request_id_of(seq_group: Any) -> str:
    rid = getattr(seq_group, "request_id", None)
    if rid is not None:
        return str(rid)
    return f"_anon_{id(seq_group)}"


def _arrival_time_of(seq_group: Any) -> float:
    """Try multiple attribute paths; fall back to ``time.monotonic()``.

    vLLM 0.7.3 surfaces arrival via ``seq_group.metrics.arrival_time``;
    older mocks may use ``seq_group.arrival_time`` directly.
    """
    m = getattr(seq_group, "metrics", None)
    if m is not None:
        t = getattr(m, "arrival_time", None)
        if t is not None:
            return float(t)
    t = getattr(seq_group, "arrival_time", None)
    if t is not None:
        return float(t)
    return time.monotonic()


def _block_ids_for_seq(block_manager: Any, seq_id: Any) -> List[int]:
    """Extract integer block_ids from ``block_manager.block_tables[seq_id]``.

    vLLM 0.7.3 has two ``block_tables`` layouts:

    * **V1 block manager:** ``Dict[seq_id, List[PhysicalTokenBlock]]``;
      each ``PhysicalTokenBlock`` has a ``.block_number`` attribute.
      Direct iteration over the list works.
    * **V2 block manager (default in V0 engine + 0.7.3 paths):**
      ``Dict[seq_id, BlockTable]``. ``BlockTable`` is a wrapper
      object that exposes ``.physical_block_ids`` →
      ``List[Optional[int]]`` (the canonical accessor) and
      ``.blocks`` → ``List[Block]``. It is NOT directly iterable
      — iterating it raises ``TypeError``.

    Mock tests historically used ``List[MockPhysicalTokenBlock]``
    (V1-shape). The runtime crash on a real H100 pod surfaced the
    V1-only assumption (PR-2 GPU smoke initial run); this helper
    now handles both shapes plus the mocks.

    Returns ``List[int]``.
    """
    bt_dict = getattr(block_manager, "block_tables", None)
    if not bt_dict:
        return []
    bt = bt_dict.get(seq_id)
    if bt is None:
        return []
    # V2 block manager: canonical accessor.
    physical_ids = getattr(bt, "physical_block_ids", None)
    if physical_ids is not None:
        return [int(b) for b in physical_ids if b is not None]
    # V2 block manager: alternate accessor exposing the underlying
    # Block objects (whose ``.block_id`` is the integer index).
    blocks_attr = getattr(bt, "blocks", None)
    if blocks_attr is not None:
        return [
            int(getattr(b, "block_id", getattr(b, "block_number", b)))
            for b in blocks_attr
            if b is not None
        ]
    # V1 block manager / mock test path: bt is iterable, elements
    # carry either .block_number (vLLM) or .block_id (mock variants).
    try:
        return [
            int(getattr(b, "block_number", getattr(b, "block_id", b)))
            for b in bt
        ]
    except TypeError:
        # Neither a V2 wrapper nor an iterable — unknown shape;
        # return empty so the wrap stays a structural no-op
        # rather than crashing the engine loop.
        return []


# ----------------------------------------------------------------------
# Install — the public entry point
# ----------------------------------------------------------------------


def install_cache_aware_scheduler(
    *,
    scheduler: Any,
    block_manager: Any,
    enable: bool = False,
    block_size: int = 32,
    max_starvation_seconds: float = 30.0,
    tree_max_tokens: int = 1_000_000,
) -> CacheAwareInstall:
    """Install cache-aware admission scheduling on a vLLM Scheduler.

    Args:
        scheduler: A vLLM ``Scheduler``-like object with a
            ``waiting`` ``Deque[SequenceGroup]`` attribute and a
            ``schedule()`` method. Tests pass a mock; real
            integration passes ``engine.engine.scheduler`` from
            an ``AsyncLLMEngine``.
        block_manager: A vLLM ``BlockSpaceManager``-like object
            with ``allocate(seq_group)``, ``free(seq)``, and
            ``block_tables`` (``Dict[seq_id, List[block_id_like]]``).
        enable: feature flag. **Defaults to False.** When False,
            returns a no-op handle and applies zero patches.
        block_size: KV-cache block size. ``int4_protected`` forces
            32; stock vLLM defaults to 16.
        max_starvation_seconds: fairness guard. Any request older
            than this in ``waiting`` is admitted next regardless
            of predicted hit. Default 30s.
        tree_max_tokens: ``PrefixRadixTree`` memory budget.

    Returns:
        A ``CacheAwareInstall`` handle. With ``enable=False``, the
        handle is a stub. With ``enable=True``, call ``teardown()``
        to revert the patches when the engine shuts down.

    Raises:
        AttributeError: if the provided objects lack the required
            interface (caller bug; not a runtime guard).
    """
    if not enable:
        return CacheAwareInstall(enabled=False)

    if not hasattr(scheduler, "waiting") or not hasattr(scheduler, "schedule"):
        raise AttributeError(
            "scheduler must have .waiting (deque-like) and .schedule() "
            "method; got " + type(scheduler).__name__
        )
    if not hasattr(block_manager, "allocate") or not hasattr(block_manager, "free"):
        raise AttributeError(
            "block_manager must have .allocate(seq_group) and .free(seq) "
            "methods; got " + type(block_manager).__name__
        )

    tree = PrefixRadixTree(max_tokens=tree_max_tokens)
    cas = CacheAwareScheduler(
        tree,
        block_size=block_size,
        max_starvation_seconds=max_starvation_seconds,
    )
    install = CacheAwareInstall(enabled=True, tree=tree, cas=cas)

    # --- Wrap 1: Scheduler.schedule reorders waiting -----------------

    original_schedule = scheduler.schedule

    def _schedule_with_reorder(*args, **kwargs):
        waiting = scheduler.waiting
        n = len(waiting)
        if n > 1:
            pending: List[PendingRequest] = []
            for sg in waiting:
                pending.append(
                    PendingRequest(
                        request_id=_request_id_of(sg),
                        tokens=_tokens_of(sg),
                        arrival_time=_arrival_time_of(sg),
                    )
                )
            ordered_pending = cas.order_admissions(pending)
            # Re-pack into the deque in the new order, preserving
            # SequenceGroup object identity (critical for vLLM's
            # internal references and abort_request).
            by_id = {_request_id_of(sg): sg for sg in waiting}
            waiting.clear()
            for req in ordered_pending:
                sg = by_id.get(req.request_id)
                if sg is not None:
                    waiting.append(sg)
                # Capture per-request predicted hit for later
                # realized-hit attribution (used in stats()).
                if req.request_id not in install._predicted_hits_per_request:
                    phit = cas.predictor.predict_cache_hit(req.tokens)
                    install._predicted_hits_per_request[req.request_id] = phit
                    install._predicted_hits_total += phit
        return original_schedule(*args, **kwargs)

    scheduler.schedule = _schedule_with_reorder
    install._teardowns.append(
        lambda: setattr(scheduler, "schedule", original_schedule)
    )

    # --- Wrap 2: BlockSpaceManager.allocate updates tree --------------

    original_allocate = block_manager.allocate

    def _allocate_with_tree_update(seq_group, *args, **kwargs):
        tokens = _tokens_of(seq_group)
        # Realized hit measurement: query the tree BEFORE the
        # insert — this gives the matched prefix length, which
        # equals the count of tokens that will hit the prefix
        # cache for this admission. Block-aligned per the
        # predictor's contract.
        if tokens:
            realized_match = tree.query(tokens)
            realized_hit = (realized_match // block_size) * block_size
        else:
            realized_hit = 0
        install._realized_hits_total += realized_hit
        # Delegate to the original allocate(). vLLM writes the
        # block_table entry as a side-effect.
        result = original_allocate(seq_group, *args, **kwargs)
        # Sync tree with the freshly-allocated blocks.
        seq_id = _seq_id_from_seq_group(seq_group)
        block_ids = _block_ids_for_seq(block_manager, seq_id)
        if block_ids and tokens:
            tree.insert(tokens, block_ids=block_ids)
        return result

    block_manager.allocate = _allocate_with_tree_update
    install._teardowns.append(
        lambda: setattr(block_manager, "allocate", original_allocate)
    )

    # --- Wrap 3: BlockSpaceManager.free evicts from tree --------------

    original_free = block_manager.free

    def _free_with_tree_evict(seq_or_seq_group, *args, **kwargs):
        # vLLM 0.7.3's free() can be called with a Sequence or a
        # SequenceGroup depending on the call site. Detect both.
        if hasattr(seq_or_seq_group, "get_prompt_token_ids"):
            seq = seq_or_seq_group
            request_id_for_cleanup = None
        else:
            seq = _seq_from(seq_or_seq_group)
            request_id_for_cleanup = _request_id_of(seq_or_seq_group)
        seq_id = _seq_id_of(seq)
        # Snapshot block_ids BEFORE the free — post-free they're
        # gone from block_tables.
        block_ids_freed = _block_ids_for_seq(block_manager, seq_id)
        result = original_free(seq_or_seq_group, *args, **kwargs)
        if block_ids_freed:
            tree.evict(block_ids_freed)
        # Drop per-request prediction cache to bound memory.
        if request_id_for_cleanup is not None:
            install._predicted_hits_per_request.pop(
                request_id_for_cleanup, None,
            )
        return result

    block_manager.free = _free_with_tree_evict
    install._teardowns.append(
        lambda: setattr(block_manager, "free", original_free)
    )

    return install
