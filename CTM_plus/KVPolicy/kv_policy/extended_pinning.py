"""Phase 4A — Extended Pinning Policy (CPU prototype).

Mark KV-cache blocks as eviction-protected on top of vLLM's
standard LRU + prefix caching. Blocks matching a registered
``PinSpec`` are temporarily stashed out of the evictor's free
table at evict-time so they are never picked as victims (except
under the forced-eviction failsafe when the entire free pool is
pinned).

This is a v2 hardening feature — *not* a replacement for vLLM's
allocator. The composition is:

    vLLM LRU + vLLM prefix caching          (inherited)
        + INT4 protected sink/channel        (Tier 1 shipped)
        + Extended Pinning                   (this module — v2)

## Why pinning is different from cache-aware scheduling

Phase 3 closed with an inconclusive realized-hit signal for
cache-aware **predictive reorder**. Pinning is a **deterministic
policy** instead of a prediction:

* "These blocks stay" is a fixed rule, not an estimate.
* Benefit is structural — a shared system prompt that gets
  evicted between cohort-mate requests costs N tokens of
  recomputation per cold request; pinning prevents that.
* Failure mode is bounded — over-pinning starves the evictable
  pool; ``max_budget_blocks`` caps it.

## Scope (Phase 4A — CPU-only prototype)

In scope:
  * ``PinSpec`` — what to pin (content-based via ``token_ids``
    or position-based via ``first_n_blocks_per_request``).
  * ``PinningManager`` — tracks pinned block_ids, enforces budget.
  * ``install_extended_pinning(block_manager, pin_specs, ...)``
    — monkey-patches block_manager.allocate (to detect new
    pins at admission time) and the LRU evictor (to filter
    pinned candidates from the victim pool).
  * ``ExtendedPinningInstall`` — handle with ``stats()`` and
    ``teardown()``. Composes safely with cache_aware_install.

Out of scope (Phase 4B+):
  * Driver wiring in ``runner_vllm_streaming.py``.
  * CLI flags on ``run_streaming.py``.
  * Bench script ``bench_phase4_extended_pinning.py``.
  * GPU measurement.
  * Tier B precision promotion (would touch int4_protected).
  * VC brief edits.

## Composition contract (durable)

* Does NOT touch ``Int4ProtectedAttentionImpl``.
* Does NOT touch the forked vLLM-flash-attn kernel.
* Does NOT touch the protected-channel splice or sink mechanism.
* Composes additively with ``install_cache_aware_scheduler``
  (Phase 0-3) and ``install_prefix_hit_probe`` (Phase 3A) on
  the same ``block_manager``. Install order matters; teardown
  is LIFO. See ``test_extended_pinning.py``
  ``test_composition_with_cache_aware_install``.

## Evictor hook strategy

The wrap intercepts ``evictor.evict()`` by **stashing** pinned
blocks out of the evictor's ``free_table`` before delegating,
then restoring them after. The original evictor never sees the
pinned candidates so it picks an unpinned victim by its normal
LRU policy.

Failsafe: when the free_table is entirely pinned, the wrap
restores everything and calls ``original_evict`` anyway,
incrementing ``forced_pin_evictions``. vLLM must be able to
allocate; we can't raise.

If ``evictor.free_table`` is not a dict (different vLLM version,
unknown shape), the wrap falls back to a structural no-op —
allocates fire, pinning state still updates, but the evictor
wrap is bypassed. ``stats()['evictor_path_taken']`` reports the
fallback so operators can flag it.

See ``PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md`` for the V1/V2 path
candidates and the Phase 4C verification plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Sequence, Set, Tuple,
)


# ----------------------------------------------------------------------
# PinSpec — what to pin
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PinSpec:
    """A pinning specification.

    Exactly one of ``token_ids`` or ``first_n_blocks_per_request``
    must be set:

    * ``token_ids``: pin blocks whose physical content matches
      this token-ID prefix. The PinningManager checks new
      admissions and marks block_ids whose token-content matches.
    * ``first_n_blocks_per_request``: pin the first N blocks of
      EVERY admitted request, regardless of content. Useful when
      every request shares a system prompt of known length but
      the exact tokens vary per deployment.

    ``name`` is a human-readable label for telemetry attribution
    (``stats()['per_spec_pinned_blocks']``).
    """
    name: str
    token_ids: Optional[Tuple[int, ...]] = None
    first_n_blocks_per_request: Optional[int] = None

    def __post_init__(self):
        # Coerce sequences to tuple for hashability + immutability.
        if self.token_ids is not None and not isinstance(self.token_ids, tuple):
            object.__setattr__(self, "token_ids", tuple(self.token_ids))

        has_tokens = self.token_ids is not None
        has_first_n = self.first_n_blocks_per_request is not None

        if has_tokens and has_first_n:
            raise ValueError(
                f"PinSpec(name={self.name!r}): exactly one of "
                "token_ids / first_n_blocks_per_request may be set, "
                "not both."
            )
        if not has_tokens and not has_first_n:
            raise ValueError(
                f"PinSpec(name={self.name!r}): exactly one of "
                "token_ids / first_n_blocks_per_request must be set."
            )
        if has_tokens and len(self.token_ids) == 0:
            raise ValueError(
                f"PinSpec(name={self.name!r}): token_ids must be "
                "non-empty."
            )
        if has_first_n and self.first_n_blocks_per_request < 1:
            raise ValueError(
                f"PinSpec(name={self.name!r}): "
                "first_n_blocks_per_request must be >= 1; got "
                f"{self.first_n_blocks_per_request}."
            )


# ----------------------------------------------------------------------
# PinningManager — block_id tracker + budget enforcement
# ----------------------------------------------------------------------


@dataclass
class PinningManager:
    """Tracks which block_ids are currently pinned and enforces
    the budget cap.

    ``max_budget_blocks=1024`` default rationale: at the canonical
    int4_protected ``block_size=32``, that's 32K tokens of pinned
    content — roughly 4% of a 24K-block cache (the Qwen-7B
    H100 ``gpu_memory_utilization=0.5`` working point). Tight
    enough to bound memory; loose enough to cover typical
    system-prompt + tool-schema cohorts.
    """

    pin_specs: List[PinSpec]
    max_budget_blocks: int
    block_size: int

    _pinned_blocks: Set[int] = field(default_factory=set)
    # block_id → set of PinSpec.name that contributed to its pinning.
    # A block may be pinned by multiple specs (e.g., a block falling
    # in both the system_prompt token-prefix and an unrelated
    # first_n_blocks rule); we track all contributors for telemetry.
    _block_to_specs: Dict[int, Set[str]] = field(default_factory=dict)
    # Counters surfaced via stats().
    _pin_budget_rejections: int = 0
    _pinned_evictions_avoided: int = 0
    _forced_pin_evictions: int = 0

    def mark_pinned(self, block_id: int, spec_name: str) -> bool:
        """Mark a block as pinned by the given spec.

        Returns True on success (added or already-pinned-by-other-
        spec), False on budget rejection.
        """
        if block_id in self._pinned_blocks:
            self._block_to_specs.setdefault(block_id, set()).add(spec_name)
            return True
        if len(self._pinned_blocks) >= self.max_budget_blocks:
            self._pin_budget_rejections += 1
            return False
        self._pinned_blocks.add(block_id)
        self._block_to_specs.setdefault(block_id, set()).add(spec_name)
        return True

    def unmark_pinned(self, block_id: int) -> None:
        """Remove a block from the pinned set (e.g., if a future
        teardown / explicit unpin caller needs it). Safe to call on
        unpinned blocks (no-op)."""
        self._pinned_blocks.discard(block_id)
        self._block_to_specs.pop(block_id, None)

    def is_pinned(self, block_id: int) -> bool:
        return block_id in self._pinned_blocks

    def pinned_block_ids(self) -> Set[int]:
        """Snapshot of the pinned set. Used by the evictor wrap."""
        return set(self._pinned_blocks)

    def consider_seq_group_for_pinning(
        self, *, tokens: Sequence[int], block_ids: Sequence[int],
    ) -> None:
        """At allocate time: evaluate the new seq's tokens + block_ids
        against the registered PinSpecs, mark matching blocks.

        Each spec evaluated independently (union over specs):
          * ``first_n_blocks_per_request``: pin block_ids[:N]
          * ``token_ids``: if the seq's prompt starts with the
            spec's token_ids, pin the first ceil(len(spec) / block_size)
            blocks of the seq's block_ids.
        """
        if not block_ids:
            return
        tokens_list = list(tokens) if tokens else []
        block_ids_list = list(block_ids)
        for spec in self.pin_specs:
            if spec.first_n_blocks_per_request is not None:
                n = spec.first_n_blocks_per_request
                for bid in block_ids_list[:n]:
                    self.mark_pinned(int(bid), spec.name)
            elif spec.token_ids is not None:
                spec_tokens = spec.token_ids
                if len(tokens_list) < len(spec_tokens):
                    continue
                # Prefix-match.
                if tuple(tokens_list[: len(spec_tokens)]) != spec_tokens:
                    continue
                n_blocks = (
                    (len(spec_tokens) + self.block_size - 1)
                    // self.block_size
                )
                for bid in block_ids_list[:n_blocks]:
                    self.mark_pinned(int(bid), spec.name)

    def record_evictions_avoided(self, n_pinned_candidates_skipped: int) -> None:
        """The evictor wrap calls this each time it stashes pinned
        candidates from the free pool."""
        if n_pinned_candidates_skipped > 0:
            self._pinned_evictions_avoided += n_pinned_candidates_skipped

    def record_forced_eviction(self) -> None:
        """The evictor wrap calls this when the entire free pool is
        pinned and a forced eviction has to happen anyway."""
        self._forced_pin_evictions += 1

    def stats(self) -> Dict[str, Any]:
        per_spec_counts: Dict[str, int] = {}
        for spec_set in self._block_to_specs.values():
            for spec_name in spec_set:
                per_spec_counts[spec_name] = (
                    per_spec_counts.get(spec_name, 0) + 1
                )
        # bf16 is 2 bytes/token; the pinned-memory-overhead figure
        # is a worst-case bound assuming each block holds bf16 K+V.
        # int4 would be ~4x lower; we report the bf16 ceiling so
        # operators sizing the budget don't under-estimate.
        bytes_per_token_bf16 = 2
        memory_overhead = (
            len(self._pinned_blocks)
            * self.block_size
            * bytes_per_token_bf16
        )
        return {
            "pinned_blocks_total": len(self._pinned_blocks),
            "pin_specs_count": len(self.pin_specs),
            "pinned_evictions_avoided": self._pinned_evictions_avoided,
            "pin_budget_rejections": self._pin_budget_rejections,
            "forced_pin_evictions": self._forced_pin_evictions,
            "pinned_memory_overhead_bytes": memory_overhead,
            "per_spec_pinned_blocks": dict(per_spec_counts),
        }


# ----------------------------------------------------------------------
# Install handle
# ----------------------------------------------------------------------


@dataclass
class ExtendedPinningInstall:
    """Handle returned by ``install_extended_pinning``.

    With ``enabled=False``, the handle is a stub with no manager,
    no teardowns. ``stats()`` returns ``{"enabled": False}``.

    With ``enabled=True``, owns the live ``PinningManager`` and
    teardown closures for the allocate + evict wraps. Callers must
    invoke ``teardown()`` on engine shutdown — LIFO with other
    installs.
    """

    enabled: bool
    pin_specs: List[PinSpec] = field(default_factory=list)
    manager: Optional[PinningManager] = None
    # Path the evictor resolution took; "no_known_path" means the
    # evictor wrap was not installed (allocate-wrap-only mode).
    evictor_path_taken: str = "no_known_path"
    _teardowns: List[Callable[[], None]] = field(default_factory=list)

    def teardown(self) -> None:
        """Revert all monkey-patches (LIFO; idempotent)."""
        for fn in reversed(self._teardowns):
            try:
                fn()
            except Exception:
                # Best-effort revert; never crash the engine.
                pass
        self._teardowns.clear()

    def stats(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        assert self.manager is not None
        s = self.manager.stats()
        s["enabled"] = True
        s["evictor_path_taken"] = self.evictor_path_taken
        return s


# ----------------------------------------------------------------------
# vLLM allocator/evictor-path resolution
# ----------------------------------------------------------------------


def _resolve_evictor(block_manager: Any) -> Tuple[Any, str]:
    """Walk the block manager to find vLLM's LRU evictor.

    Returns ``(evictor_or_none, path_string)``.

    Three documented paths (see PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md):

    * V2 property: block_manager.block_allocator.gpu_allocator.evictor
    * V2 dict:     block_manager.block_allocator._allocators[Device.GPU].evictor
    * V1 direct:   block_manager.gpu_allocator.evictor

    Failure mode: returns (None, "no_known_path") so the install
    can still complete (allocate wrap is still useful for
    measurement) but the evictor wrap is skipped.
    """
    # V2 path: block_allocator wrapper.
    ba = getattr(block_manager, "block_allocator", None)
    if ba is not None:
        # Property form.
        gpu = getattr(ba, "gpu_allocator", None)
        if gpu is not None:
            ev = getattr(gpu, "evictor", None)
            if ev is not None:
                return ev, "v2_block_allocator.gpu_allocator.evictor"
        # Dict form.
        allocators = getattr(ba, "_allocators", None)
        if isinstance(allocators, dict):
            for key, alloc in allocators.items():
                key_str = str(key).split(".")[-1].lower()
                if "gpu" in key_str:
                    ev = getattr(alloc, "evictor", None)
                    if ev is not None:
                        return ev, "v2_block_allocator._allocators[GPU].evictor"
    # V1 path: direct gpu_allocator.
    v1_gpu = getattr(block_manager, "gpu_allocator", None)
    if v1_gpu is not None:
        ev = getattr(v1_gpu, "evictor", None)
        if ev is not None:
            return ev, "v1_block_manager.gpu_allocator.evictor"
    return None, "no_known_path"


# ----------------------------------------------------------------------
# vLLM SequenceGroup interface adapters (duplicated from
# cache_aware_install + prefix_hit_probe so this module has no
# cross-install dependency).
# ----------------------------------------------------------------------


def _seq_from(seq_group: Any) -> Any:
    if hasattr(seq_group, "get_seqs"):
        seqs = seq_group.get_seqs()
        if seqs:
            return seqs[0]
    return seq_group


def _seq_id_of(seq: Any) -> Any:
    sid = getattr(seq, "seq_id", None)
    if sid is not None:
        return sid
    sid = getattr(seq, "id", None)
    if sid is not None:
        return sid
    return id(seq)


def _seq_id_from_seq_group(seq_group: Any) -> Any:
    return _seq_id_of(_seq_from(seq_group))


def _prompt_tokens_of(seq_group: Any) -> List[int]:
    seq = _seq_from(seq_group)
    get_ids = getattr(seq, "get_prompt_token_ids", None)
    if callable(get_ids):
        return list(get_ids())
    pti = getattr(seq, "prompt_token_ids", None)
    if pti is not None:
        return list(pti)
    return []


def _block_ids_for_seq(block_manager: Any, seq_id: Any) -> List[int]:
    """Extract integer block_ids from block_manager.block_tables[seq_id].
    Mirrors the V1/V2 fallback logic in cache_aware_install._block_ids_for_seq.
    """
    bt_dict = getattr(block_manager, "block_tables", None)
    if not bt_dict:
        return []
    bt = bt_dict.get(seq_id)
    if bt is None:
        return []
    physical_ids = getattr(bt, "physical_block_ids", None)
    if physical_ids is not None:
        return [int(b) for b in physical_ids if b is not None]
    blocks_attr = getattr(bt, "blocks", None)
    if blocks_attr is not None:
        return [
            int(getattr(b, "block_id", getattr(b, "block_number", b)))
            for b in blocks_attr
            if b is not None
        ]
    try:
        return [
            int(getattr(b, "block_number", getattr(b, "block_id", b)))
            for b in bt
        ]
    except TypeError:
        return []


# ----------------------------------------------------------------------
# Install — the public entry point
# ----------------------------------------------------------------------


def install_extended_pinning(
    *,
    block_manager: Any,
    pin_specs: Sequence[PinSpec],
    max_budget_blocks: int = 1024,
    enable: bool = False,
    block_size: int = 32,
) -> ExtendedPinningInstall:
    """Install extended pinning on a vLLM ``BlockSpaceManager``.

    Args:
        block_manager: a vLLM 0.7.x ``BlockSpaceManager``-like with
            ``allocate(seq_group)``, ``block_tables``, and (for the
            evictor wrap) a discoverable LRU evictor (see
            ``_resolve_evictor`` for the candidate paths).
        pin_specs: sequence of ``PinSpec`` to register.
        max_budget_blocks: hard cap on the total pinned block count.
            Default 1024 ≈ 32K tokens at block_size=32 ≈ 4% of a
            24K-block cache (Qwen-7B H100 working point). Once
            reached, new pins are rejected (counted in
            ``stats()['pin_budget_rejections']``) without removing
            existing pinned blocks.
        enable: feature flag. **Defaults to False.** When False,
            returns a no-op handle and applies zero patches.
        block_size: KV-cache block size. Used to compute how many
            blocks a token-prefix-based ``PinSpec`` covers.

    Returns:
        An ``ExtendedPinningInstall`` handle. With ``enable=False``,
        the handle is a stub. With ``enable=True``, call
        ``teardown()`` to revert the patches when the engine
        shuts down.

    Raises:
        AttributeError: if ``block_manager`` lacks ``.allocate``.
    """
    install = ExtendedPinningInstall(
        enabled=enable, pin_specs=list(pin_specs),
    )
    if not enable:
        return install

    if not hasattr(block_manager, "allocate"):
        raise AttributeError(
            "block_manager must have .allocate(seq_group); got "
            + type(block_manager).__name__
        )

    manager = PinningManager(
        pin_specs=list(pin_specs),
        max_budget_blocks=int(max_budget_blocks),
        block_size=int(block_size),
    )
    install.manager = manager

    # --- Wrap 1: block_manager.allocate — detect new pins ----------

    original_allocate = block_manager.allocate

    def _allocate_with_pinning_check(seq_group, *args, **kwargs):
        result = original_allocate(seq_group, *args, **kwargs)
        # AFTER vLLM allocates, inspect the new block_ids + tokens
        # and mark anything matching a PinSpec.
        try:
            seq_id = _seq_id_from_seq_group(seq_group)
            tokens = _prompt_tokens_of(seq_group)
            block_ids = _block_ids_for_seq(block_manager, seq_id)
            if block_ids:
                manager.consider_seq_group_for_pinning(
                    tokens=tokens, block_ids=block_ids,
                )
        except Exception:
            # Pinning is best-effort telemetry; a bug here must not
            # propagate into vLLM's scheduler loop.
            pass
        return result

    block_manager.allocate = _allocate_with_pinning_check
    install._teardowns.append(
        lambda: setattr(block_manager, "allocate", original_allocate)
    )

    # --- Wrap 2: evictor.evict — filter pinned candidates -----------

    evictor, evictor_path = _resolve_evictor(block_manager)
    install.evictor_path_taken = evictor_path

    if evictor is not None:
        original_evict = evictor.evict
        free_table = getattr(evictor, "free_table", None)

        if not isinstance(free_table, dict):
            # Evictor exists but its candidate pool isn't accessible
            # via .free_table — fall back to allocate-wrap-only mode.
            # The path string is updated so operators can see.
            install.evictor_path_taken = (
                evictor_path + "+no_free_table"
            )
        else:
            def _evict_with_pinning_filter(*args, **kwargs):
                # Stash pinned blocks out of the free_table so the
                # original evict() never sees them. Restore them
                # after the eviction completes.
                stashed: Dict[Any, Any] = {}
                for block_id in list(free_table.keys()):
                    if manager.is_pinned(int(block_id)):
                        stashed[block_id] = free_table.pop(block_id)
                try:
                    if not free_table and stashed:
                        # All free blocks are pinned. Restore + forced
                        # eviction (vLLM must be able to allocate, so
                        # we can't refuse).
                        free_table.update(stashed)
                        manager.record_forced_eviction()
                        return original_evict(*args, **kwargs)
                    # Normal eviction from the unpinned subset.
                    manager.record_evictions_avoided(len(stashed))
                    return original_evict(*args, **kwargs)
                finally:
                    # Restore stashed (pinned) blocks back into the
                    # table so future evict() calls still see them
                    # as live in the pool.
                    free_table.update(stashed)

            evictor.evict = _evict_with_pinning_filter
            install._teardowns.append(
                lambda: setattr(evictor, "evict", original_evict)
            )

    return install
