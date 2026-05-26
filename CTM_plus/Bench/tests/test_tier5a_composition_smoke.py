"""Phase TIER5A.2 — CPU composition smoke for the four install layers
that coexist with ``preemption_mode='swap'`` at install time.

The four layers (in the order the streaming runner installs them):

* ``swap_telemetry.install_swap_in_latency_probe`` — always-on
  telemetry surface; wraps ``cpu_allocator.swap_in``.
* ``prefix_hit_probe.install_prefix_hit_probe`` — wraps
  ``block_manager.allocate``.
* ``extended_pinning.install_extended_pinning`` — wraps
  ``block_manager.allocate`` AND ``evictor.evict``.
* ``cache_aware_install.install_cache_aware_scheduler``
  (measurement_only=True) — wraps ``block_manager.allocate`` AND
  ``block_manager.free``. The schedule reorder wrap is INTENTIONALLY
  skipped in measurement_only mode.

Three of the four wrap the same attribute (``block_manager.allocate``).
The composition contract this file locks:

1. Install-time coexistence — all four can install on the same
   block_manager without raising; each handle reports ``enabled``.
2. Single-call fan-out — one ``block_manager.allocate(sg)`` causes
   all three allocate-wrapping layers to record evidence (cache_aware
   tree updated, pin_manager pinned the position-spec block, probe
   counter ticked). No double-wrap of any single layer.
3. CPU-side independence — the swap_telemetry probe is independent
   of the allocate-wrap stack; ``cpu_allocator.swap_in(...)`` records
   latency without disturbing the allocate-wrappers.
4. Engine config invariance — ``engine.preemption_mode='swap'`` is
   untouched by any install. (The install layers compose with vLLM's
   preemption path; they don't read or mutate that knob.)
5. LIFO teardown discipline — after reverse-order teardown of all
   four, ``block_manager.allocate``, ``block_manager.free``,
   ``evictor.evict``, and ``cpu_allocator.swap_in`` are the original
   unwrapped callables.
6. Idempotent teardown — calling ``teardown()`` twice on any handle
   is a no-op.
7. Repeated install/teardown cycles leave no residual state (the
   bench harness installs once per cell and tears down between
   cells).
8. The G4 verdict in ``bench_tier5a_swap_restore.compute_g4_verdict``
   reads the THREE-layer ``composition_install_layer_status`` dict
   (swap_telemetry is always-on across cells A+B+C, so it's not part
   of the cell-C-only composition signal). This file confirms the
   keys + status values the bench harness expects.

Scope clarification: this is the CPU-side smoke. The real-vLLM
acceptance run is TIER5A.3 (GPU smoke); the G2 swap_out_blocks > 0
check + the G1 bit-identity verifier both require a live model and
are not exercised here. The G5/G6 orthogonality gates run as a
separate pre/post step in the bench harness.

No torch, no vllm, no GPU.
"""

from __future__ import annotations

import collections
from typing import Any, Dict, List, Optional, Sequence

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.cache_aware_install import (
    CacheAwareInstall,
    install_cache_aware_scheduler,
)
from kv_policy.extended_pinning import (
    ExtendedPinningInstall,
    PinSpec,
    install_extended_pinning,
)
from kv_policy.prefix_hit_probe import (
    PrefixHitProbe,
    install_prefix_hit_probe,
)
from kv_policy.swap_telemetry import (
    SwapInLatencyProbe,
    install_swap_in_latency_probe,
    read_cpu_swap_pool,
)


BLOCK_SIZE = 32


# ---------------------------------------------------------------- #
# Mock vLLM 0.7.x shapes — single-file, self-contained.
# Mirrors the V2 property-form path (matches vLLM 0.7.3 default).
# ---------------------------------------------------------------- #


class _MockSequence:
    def __init__(self, seq_id: int, prompt: Sequence[int]) -> None:
        self.seq_id = seq_id
        self._prompt = list(prompt)

    def get_prompt_token_ids(self) -> List[int]:
        return list(self._prompt)


class _MockSequenceGroup:
    def __init__(
        self, request_id: str, prompt: Sequence[int],
        seq_id: Optional[int] = None,
    ) -> None:
        self.request_id = request_id
        self.arrival_time = 0.0
        self._seqs = [
            _MockSequence(
                seq_id=seq_id if seq_id is not None
                else hash(request_id) & 0x7FFFFFFF,
                prompt=prompt,
            )
        ]

    def get_seqs(self) -> List[_MockSequence]:
        return list(self._seqs)


class _MockPhysicalBlock:
    def __init__(self, block_number: int) -> None:
        self.block_number = block_number


class _MockLRUEvictor:
    """Mimics vLLM's LRU evictor: ``free_table`` dict + ``evict()``
    pops the LRU-most entry."""

    def __init__(self) -> None:
        self.free_table: Dict[int, Any] = {}
        self.evict_call_count: int = 0

    def add_to_free_pool(self, block_id: int) -> None:
        self.free_table[block_id] = f"block_{block_id}_metadata"

    def evict(self):
        self.evict_call_count += 1
        if not self.free_table:
            raise RuntimeError("free_table empty")
        block_id = next(iter(self.free_table))
        meta = self.free_table.pop(block_id)
        return (block_id, meta)


class _MockGpuAllocator:
    """GPU allocator with evictor (for extended_pinning) and
    ``_cached_blocks`` (for prefix_hit_probe's cached_blocks_derived
    path)."""

    def __init__(self) -> None:
        self.evictor = _MockLRUEvictor()
        self._cached_blocks: Dict[int, Any] = {}


class _MockCpuAllocator:
    """CPU allocator with ``swap_in`` callable + block-count getters
    (used by ``read_cpu_swap_pool``)."""

    def __init__(
        self,
        *,
        num_total_blocks: int = 1024,
        num_free_blocks: int = 1024,
    ) -> None:
        self.num_total_blocks = num_total_blocks
        self._num_free_blocks = num_free_blocks
        self.swap_in_call_count = 0

    def get_num_free_blocks(self) -> int:
        return self._num_free_blocks

    def swap_in(self, *args: Any, **kwargs: Any) -> str:
        self.swap_in_call_count += 1
        return "swap_in_done"


class _MockBlockAllocatorV2:
    """V2-shape: exposes ``gpu_allocator`` and ``cpu_allocator`` as
    properties (matches vLLM 0.7.3's CpuGpuBlockAllocator)."""

    def __init__(self) -> None:
        self.gpu_allocator = _MockGpuAllocator()
        self.cpu_allocator = _MockCpuAllocator()


class _MockBlockManagerV2:
    """V2 BlockSpaceManager-shaped mock.

    Exposes the minimum surface all four install layers need:
      * ``.allocate(sg)`` / ``.free(sg_or_seq)`` — the methods three
        layers wrap.
      * ``.block_tables`` — populated by allocate so
        ``_block_ids_for_seq`` can read freshly-allocated block_ids
        out of it.
      * ``.block_allocator.gpu_allocator.evictor`` — wrapped by
        extended_pinning.
      * ``.block_allocator.cpu_allocator.swap_in`` — wrapped by
        swap_telemetry.
      * ``.block_size`` — read by ``read_cpu_swap_pool``.
    """

    def __init__(self, *, block_size: int = BLOCK_SIZE) -> None:
        self.block_size = block_size
        self.block_allocator = _MockBlockAllocatorV2()
        self.block_tables: Dict[int, List[_MockPhysicalBlock]] = {}
        self.allocate_calls = 0
        self.free_calls = 0
        self._next_block_number = 1

    def allocate(self, seq_group: _MockSequenceGroup) -> None:
        self.allocate_calls += 1
        seq = seq_group.get_seqs()[0]
        tokens = seq.get_prompt_token_ids()
        n_blocks = max(
            1, (len(tokens) + self.block_size - 1) // self.block_size
        )
        blocks: List[_MockPhysicalBlock] = []
        for _ in range(n_blocks):
            blocks.append(_MockPhysicalBlock(self._next_block_number))
            self._next_block_number += 1
        self.block_tables[seq.seq_id] = blocks

    def free(self, seq_or_seq_group: Any) -> None:
        self.free_calls += 1
        seq = (
            seq_or_seq_group
            if hasattr(seq_or_seq_group, "get_prompt_token_ids")
            else seq_or_seq_group.get_seqs()[0]
        )
        self.block_tables.pop(seq.seq_id, None)


class _MockScheduler:
    """Scheduler-shaped mock: ``waiting`` deque + ``schedule()``."""

    def __init__(self) -> None:
        self.waiting = collections.deque()
        self.schedule_call_count = 0

    def schedule(self) -> List[Any]:
        self.schedule_call_count += 1
        return []


class _MockEngine:
    """Top-level engine mock — carries the read-only
    ``preemption_mode`` attribute so the invariance test has somewhere
    to look. None of the four install layers should read or write
    this field."""

    def __init__(
        self,
        *,
        preemption_mode: str = "swap",
        block_size: int = BLOCK_SIZE,
    ) -> None:
        self.preemption_mode = preemption_mode
        self.scheduler = _MockScheduler()
        self.block_manager = _MockBlockManagerV2(block_size=block_size)


# ---------------------------------------------------------------- #
# Composition helper: install all four layers in the documented order
# the streaming runner uses, returning each handle. Mirrors the
# install sequence the TIER5A.3 GPU smoke will wire up.
# ---------------------------------------------------------------- #


def _install_all_four(
    engine: _MockEngine,
    *,
    pin_first_n_blocks: int = 1,
) -> Dict[str, Any]:
    """Install the four layers in the canonical order. Returns a
    dict of handles keyed by the same names the bench harness's
    G4 verdict expects (plus ``swap_telemetry``)."""
    swap_probe: SwapInLatencyProbe = install_swap_in_latency_probe(
        engine.block_manager, enable=True,
    )
    prefix_probe: PrefixHitProbe = install_prefix_hit_probe(
        block_manager=engine.block_manager,
        block_size=engine.block_manager.block_size,
        enable=True,
    )
    pin_install: ExtendedPinningInstall = install_extended_pinning(
        block_manager=engine.block_manager,
        pin_specs=[
            PinSpec(
                name="first_n",
                first_n_blocks_per_request=pin_first_n_blocks,
            )
        ],
        enable=True,
        block_size=engine.block_manager.block_size,
    )
    cas_install: CacheAwareInstall = install_cache_aware_scheduler(
        scheduler=engine.scheduler,
        block_manager=engine.block_manager,
        enable=True,
        measurement_only=True,
        block_size=engine.block_manager.block_size,
    )
    return {
        "swap_telemetry": swap_probe,
        "prefix_hit_probe": prefix_probe,
        "extended_pinning": pin_install,
        "cache_aware_measurement_only": cas_install,
    }


def _teardown_lifo(handles: Dict[str, Any]) -> None:
    """LIFO reverse of ``_install_all_four``: cache_aware → pinning →
    prefix_probe → swap_telemetry."""
    handles["cache_aware_measurement_only"].teardown()
    handles["extended_pinning"].teardown()
    handles["prefix_hit_probe"].teardown()
    handles["swap_telemetry"].teardown()


# ---------------------------------------------------------------- #
# Tests
# ---------------------------------------------------------------- #


def test_four_layers_install_in_documented_order_no_raise() -> None:
    """All four installs return enabled handles when the mock
    block_manager exposes the V2 shape the streaming runner targets.
    """
    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        assert handles["swap_telemetry"].enabled is True
        # prefix_hit_probe doesn't carry a plain `.enabled` field —
        # `installed` in stats() is the analogue.
        assert handles["prefix_hit_probe"].stats()["installed"] is True
        assert handles["extended_pinning"].enabled is True
        assert handles["cache_aware_measurement_only"].enabled is True
    finally:
        _teardown_lifo(handles)


def test_four_layers_all_fire_on_single_allocate() -> None:
    """One allocate(sg) causes each of the three allocate-wrapping
    layers to record evidence. Locks the fan-out the streaming runner
    relies on: a single vLLM allocate() call updates ALL three
    measurement / pinning surfaces."""
    engine = _MockEngine()
    handles = _install_all_four(engine, pin_first_n_blocks=1)
    try:
        sg = _MockSequenceGroup("req_0", list(range(BLOCK_SIZE * 2)))
        engine.block_manager.allocate(sg)

        # Pinning fired: first block is pinned via the position spec.
        seq_id = sg.get_seqs()[0].seq_id
        bid = int(
            engine.block_manager.block_tables[seq_id][0].block_number
        )
        assert handles["extended_pinning"].manager.is_pinned(bid), (
            "extended_pinning's allocate wrap did not run — pinning "
            "manager missing block_id"
        )

        # Cache-aware tree updated: query > 0 means an insert happened.
        cas_install = handles["cache_aware_measurement_only"]
        tokens = sg.get_seqs()[0].get_prompt_token_ids()
        assert cas_install.tree is not None
        assert cas_install.tree.query(tokens) > 0, (
            "cache_aware (measurement_only) allocate wrap did not run "
            "— tree.query returned 0"
        )

        # prefix_hit_probe call counter advanced.
        probe_stats = handles["prefix_hit_probe"].stats()
        assert probe_stats["allocate_calls"] == 1, (
            f"prefix_hit_probe should have observed 1 allocate; got "
            f"{probe_stats['allocate_calls']}"
        )
    finally:
        _teardown_lifo(handles)


def test_swap_telemetry_independent_of_allocate_wraps() -> None:
    """Calling cpu_allocator.swap_in records latency in the probe
    AND does NOT tick any of the allocate-wrap counters. Confirms
    the two domains (allocate vs swap_in) compose without
    cross-contamination."""
    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        swap_probe = handles["swap_telemetry"]
        n_before = len(swap_probe.latencies_ms)

        result = engine.block_manager.block_allocator.cpu_allocator.swap_in(
            "any", "args", here="ok",
        )
        assert result == "swap_in_done", (
            "swap_telemetry's wrap must delegate to the original "
            "verbatim — got " + repr(result)
        )

        n_after = len(swap_probe.latencies_ms)
        assert n_after == n_before + 1, (
            f"one swap_in call should record exactly one latency; "
            f"delta={n_after - n_before}"
        )

        # The allocate-wrap counters are untouched.
        assert engine.block_manager.allocate_calls == 0
        assert handles["prefix_hit_probe"].stats()["allocate_calls"] == 0
    finally:
        _teardown_lifo(handles)


def test_preemption_mode_swap_unchanged_by_installs() -> None:
    """``engine.preemption_mode='swap'`` is read-only for the install
    stack. Installing all four MUST NOT alter it (a bug here would
    mean a layer is reaching outside its contract)."""
    engine = _MockEngine(preemption_mode="swap")
    assert engine.preemption_mode == "swap"
    handles = _install_all_four(engine)
    try:
        assert engine.preemption_mode == "swap", (
            "preemption_mode mutated by install; expected 'swap' got "
            + repr(engine.preemption_mode)
        )
        # And again after one allocate + one swap_in for good measure.
        engine.block_manager.allocate(
            _MockSequenceGroup("r", list(range(BLOCK_SIZE)))
        )
        engine.block_manager.block_allocator.cpu_allocator.swap_in()
        assert engine.preemption_mode == "swap"
    finally:
        _teardown_lifo(handles)
    assert engine.preemption_mode == "swap", (
        "preemption_mode mutated during teardown"
    )


def test_lifo_teardown_restores_original_callables() -> None:
    """After LIFO teardown, the four wrapped attributes are the
    originals: block_manager.allocate, block_manager.free,
    gpu_allocator.evictor.evict, cpu_allocator.swap_in.
    """
    engine = _MockEngine()
    original_allocate = engine.block_manager.allocate
    original_free = engine.block_manager.free
    original_evict = engine.block_manager.block_allocator.gpu_allocator.evictor.evict
    original_swap_in = engine.block_manager.block_allocator.cpu_allocator.swap_in

    handles = _install_all_four(engine)
    _teardown_lifo(handles)

    # After full teardown, the bound method is restored to the class
    # method (matches the existing extended-pinning teardown assertion
    # style).
    assert engine.block_manager.allocate.__func__ is _MockBlockManagerV2.allocate, (
        "block_manager.allocate not restored after LIFO teardown"
    )
    assert engine.block_manager.free.__func__ is _MockBlockManagerV2.free, (
        "block_manager.free not restored after LIFO teardown"
    )
    # Evictor and swap_in were set via instance setattr; teardown
    # should remove the instance attribute and surface the original.
    cpu_alloc = engine.block_manager.block_allocator.cpu_allocator
    assert cpu_alloc.swap_in.__func__ is _MockCpuAllocator.swap_in, (
        "cpu_allocator.swap_in not restored after teardown"
    )
    # The evictor wrap is restored by setattr-back to original_evict.
    ev = engine.block_manager.block_allocator.gpu_allocator.evictor
    assert ev.evict == original_evict, (
        "evictor.evict not restored after teardown"
    )

    # And the unwrapped path still works.
    engine.block_manager.allocate(
        _MockSequenceGroup("post_td", list(range(BLOCK_SIZE)))
    )
    assert engine.block_manager.allocate_calls == 1


def test_teardown_is_idempotent_for_all_four() -> None:
    """Calling teardown() twice on each handle is a no-op. Required
    for the runner's finally-block patterns (teardown in error path
    may overlap with teardown in normal cleanup)."""
    engine = _MockEngine()
    handles = _install_all_four(engine)

    # First teardown — LIFO.
    _teardown_lifo(handles)
    # Second teardown — must not raise, must not re-revert.
    handles["cache_aware_measurement_only"].teardown()
    handles["extended_pinning"].teardown()
    handles["prefix_hit_probe"].teardown()
    handles["swap_telemetry"].teardown()

    # State stays clean (no double-revert side-effect).
    assert engine.block_manager.allocate.__func__ is _MockBlockManagerV2.allocate


def test_install_order_invariance_for_allocate_fan_out() -> None:
    """Re-order install of the three allocate-wrapping layers; the
    single allocate() call still fans out to all three. Documents
    that the fan-out property is install-order-independent.

    Order here: cache_aware first (innermost), then pinning, then
    prefix_probe (outermost). The opposite of ``_install_all_four``.
    """
    engine = _MockEngine()
    swap_probe = install_swap_in_latency_probe(
        engine.block_manager, enable=True,
    )
    cas_install = install_cache_aware_scheduler(
        scheduler=engine.scheduler,
        block_manager=engine.block_manager,
        enable=True, measurement_only=True,
        block_size=engine.block_manager.block_size,
    )
    pin_install = install_extended_pinning(
        block_manager=engine.block_manager,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True, block_size=engine.block_manager.block_size,
    )
    prefix_probe = install_prefix_hit_probe(
        block_manager=engine.block_manager,
        block_size=engine.block_manager.block_size,
        enable=True,
    )
    try:
        sg = _MockSequenceGroup("alt_order", list(range(BLOCK_SIZE * 2)))
        engine.block_manager.allocate(sg)

        seq_id = sg.get_seqs()[0].seq_id
        bid = int(
            engine.block_manager.block_tables[seq_id][0].block_number
        )
        assert pin_install.manager.is_pinned(bid)
        tokens = sg.get_seqs()[0].get_prompt_token_ids()
        assert cas_install.tree.query(tokens) > 0
        assert prefix_probe.stats()["allocate_calls"] == 1
    finally:
        # LIFO reverse of the install order.
        prefix_probe.teardown()
        pin_install.teardown()
        cas_install.teardown()
        swap_probe.teardown()


def test_cache_aware_measurement_only_does_not_wrap_schedule() -> None:
    """Locks the measurement_only contract under composition: even
    with the three other layers installed, scheduler.schedule is the
    unmodified original (because measurement_only=True skips the
    reorder wrap).

    Comparison uses ``.__func__`` because Python creates a fresh
    bound-method object on every attribute access — ``is`` would
    fail spuriously on the unwrapped path.
    """
    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        # Unwrapped path: bound-method's __func__ is the class method.
        # If cache_aware had installed the wrap, schedule would be an
        # instance-level function (no __func__), so getattr's
        # __func__ fallback would also differ.
        bound = engine.scheduler.schedule
        assert getattr(bound, "__func__", None) is _MockScheduler.schedule, (
            "measurement_only must not install the schedule reorder "
            "wrap; got " + repr(bound)
        )
        # Calling schedule() goes through the original.
        engine.scheduler.schedule()
        assert engine.scheduler.schedule_call_count == 1
    finally:
        _teardown_lifo(handles)


def test_evictor_wrap_composes_with_other_wraps() -> None:
    """extended_pinning's evictor.evict wrap fires regardless of the
    other three layers. Confirms the second wrap surface (evict)
    composes alongside the allocate-stack."""
    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        # Allocate to pin block 1.
        sg = _MockSequenceGroup("ev_req", list(range(BLOCK_SIZE)))
        engine.block_manager.allocate(sg)
        seq_id = sg.get_seqs()[0].seq_id
        pinned_bid = int(
            engine.block_manager.block_tables[seq_id][0].block_number
        )
        assert handles["extended_pinning"].manager.is_pinned(pinned_bid)

        # Seed free_table with TWO blocks — the pinned one and a
        # decoy. The wrap should stash the pinned one and evict only
        # the decoy.
        evictor = engine.block_manager.block_allocator.gpu_allocator.evictor
        evictor.add_to_free_pool(pinned_bid)
        evictor.add_to_free_pool(999)

        block_id, _ = evictor.evict()
        assert block_id == 999, (
            f"evictor wrap should have stashed pinned bid {pinned_bid} "
            f"and returned the unpinned decoy 999; got {block_id}"
        )
        # Pinning stats should reflect the stash.
        pin_stats = handles["extended_pinning"].stats()
        assert pin_stats["pinned_evictions_avoided"] >= 1, (
            "pin_install.stats()['pinned_evictions_avoided'] did not "
            "advance — evictor wrap not active under composition"
        )
    finally:
        _teardown_lifo(handles)


def test_repeated_install_uninstall_cycle_leaves_no_state() -> None:
    """Bench harness installs once per cell, tears down between
    cells. Two cycles on the same engine must leave the engine in
    the same shape it started in."""
    engine = _MockEngine()
    original_allocate_id = id(_MockBlockManagerV2.allocate)

    for cycle in range(2):
        handles = _install_all_four(engine)
        engine.block_manager.allocate(
            _MockSequenceGroup(
                f"req_cycle_{cycle}", list(range(BLOCK_SIZE))
            )
        )
        _teardown_lifo(handles)

    # After two cycles, the bound method is again the class default —
    # no leftover monkey-patch layer.
    assert engine.block_manager.allocate.__func__ is _MockBlockManagerV2.allocate, (
        "residual wrap survived a second teardown cycle"
    )
    assert id(_MockBlockManagerV2.allocate) == original_allocate_id


def test_install_layer_stats_keys_match_g4_verdict_expectations() -> None:
    """The bench harness's compute_g4_verdict consumes a
    ``composition_install_layer_status`` dict keyed by three layer
    names (swap_telemetry is always-on and out-of-scope for G4).
    Each handle's stats() must surface a value the verdict can
    serialise."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        compute_g4_verdict,
    )

    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        # Drive a single allocate so each layer has non-zero stats.
        engine.block_manager.allocate(
            _MockSequenceGroup("g4", list(range(BLOCK_SIZE * 2)))
        )
        layer_status = {
            "extended_pinning": str(
                handles["extended_pinning"].stats().get("enabled")
            ),
            "cache_aware_measurement_only": str(
                handles["cache_aware_measurement_only"].stats().get("enabled")
            ),
            "prefix_hit_probe": str(
                handles["prefix_hit_probe"].stats().get("installed")
            ),
        }
        verdict = compute_g4_verdict(
            composition_cell_completed=True,
            composition_cell_completed_requests=1,
            composition_install_layer_status=layer_status,
        )
        assert verdict.gate_id == "G4"
        assert verdict.passed is True, (
            "G4 verdict should pass with three layer keys present + "
            "completed=True + completed_requests>0; got "
            + verdict.summary
        )
        # swap_telemetry is NOT in the expected_layers set; record
        # this to lock the scope.
        assert "swap_telemetry" not in {
            "extended_pinning",
            "cache_aware_measurement_only",
            "prefix_hit_probe",
        }
    finally:
        _teardown_lifo(handles)


def test_swap_telemetry_snapshot_works_alongside_other_installs() -> None:
    """``read_cpu_swap_pool`` is the gauge read; it does not install
    anything, but it MUST work even when the four install layers are
    active on the same block_manager."""
    engine = _MockEngine()
    handles = _install_all_four(engine)
    try:
        snapshot = read_cpu_swap_pool(engine.block_manager)
        # Mock starts with num_total=1024 / num_free=1024 → used=0.
        assert snapshot.num_total_blocks == 1024
        assert snapshot.num_used_blocks == 0
        assert snapshot.hint_path == "v2_block_allocator.cpu_allocator"
        # Drop free by 32 to simulate vLLM swapping 32 blocks out.
        engine.block_manager.block_allocator.cpu_allocator._num_free_blocks = 992
        snapshot2 = read_cpu_swap_pool(engine.block_manager)
        assert snapshot2.num_used_blocks == 32
    finally:
        _teardown_lifo(handles)


def test_cell_c_config_drives_consistent_install_signatures() -> None:
    """The TIER5A bench harness's cell-C CellConfig encodes the
    composition surface as four flags. This test confirms those
    flags map cleanly to the install signatures (caller cannot
    construct a cell-C config that the install layer rejects)."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        build_bench_spec,
    )
    from pathlib import Path

    spec = build_bench_spec(
        model="dummy/model",
        seed=0,
        output_dir=Path("/tmp/tier5a"),
        g4_smoke_enabled=True,
        g4_pin_first_n_blocks=2,
    )
    cells_by_name = {c.cell_name: c for c in spec.cells}
    cell_c = cells_by_name["cell_C_g4_composition"]
    assert cell_c.preemption_mode == "swap"
    assert cell_c.install_extended_pinning is True
    assert cell_c.install_cache_aware_measurement_only is True
    assert cell_c.install_prefix_hit_probe is True
    assert cell_c.pin_first_n_blocks == 2
    # enable_prefix_caching MUST be True for cell C — both
    # extended_pinning and cache_aware operate on the
    # PrefixCachingBlockAllocator.
    assert cell_c.enable_prefix_caching is True

    # And the install signatures accept these values without error.
    engine = _MockEngine(preemption_mode=cell_c.preemption_mode)
    handles = _install_all_four(
        engine, pin_first_n_blocks=cell_c.pin_first_n_blocks,
    )
    try:
        assert handles["extended_pinning"].enabled is True
        assert handles["cache_aware_measurement_only"].enabled is True
        assert handles["prefix_hit_probe"].stats()["installed"] is True
        assert handles["swap_telemetry"].enabled is True
        assert engine.preemption_mode == "swap"
    finally:
        _teardown_lifo(handles)


def test_swap_telemetry_disabled_does_not_break_composition() -> None:
    """The streaming runner may pass ``enable=False`` to the swap
    probe on cells where swap timing is uninteresting. Composition
    of the other three must be unaffected (returns inert handle;
    no wrap on cpu_allocator)."""
    engine = _MockEngine()
    swap_probe = install_swap_in_latency_probe(
        engine.block_manager, enable=False,
    )
    assert swap_probe.enabled is False

    # Install the other three.
    prefix_probe = install_prefix_hit_probe(
        block_manager=engine.block_manager,
        block_size=engine.block_manager.block_size, enable=True,
    )
    pin_install = install_extended_pinning(
        block_manager=engine.block_manager,
        pin_specs=[PinSpec(name="s", first_n_blocks_per_request=1)],
        enable=True, block_size=engine.block_manager.block_size,
    )
    cas_install = install_cache_aware_scheduler(
        scheduler=engine.scheduler,
        block_manager=engine.block_manager,
        enable=True, measurement_only=True,
        block_size=engine.block_manager.block_size,
    )
    try:
        # cpu_allocator.swap_in is UN-wrapped (inert swap probe).
        cpu_alloc = engine.block_manager.block_allocator.cpu_allocator
        assert cpu_alloc.swap_in.__func__ is _MockCpuAllocator.swap_in
        # And the other three still fire together on one allocate.
        sg = _MockSequenceGroup("disabled_swap", list(range(BLOCK_SIZE)))
        engine.block_manager.allocate(sg)
        assert prefix_probe.stats()["allocate_calls"] == 1
        seq_id = sg.get_seqs()[0].seq_id
        bid = int(
            engine.block_manager.block_tables[seq_id][0].block_number
        )
        assert pin_install.manager.is_pinned(bid)
        assert cas_install.tree.query(
            sg.get_seqs()[0].get_prompt_token_ids()
        ) > 0
    finally:
        cas_install.teardown()
        pin_install.teardown()
        prefix_probe.teardown()
        swap_probe.teardown()
