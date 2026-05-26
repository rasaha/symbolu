"""Phase TIER5A.1 CPU tests for ``kv_policy.swap_telemetry``.

Acceptance gates exercised (CPU-only):

* CPU pool snapshot — V1, V2 property, V2 dict, no-known-path
  fallback (4 paths).
* Block-count read fallbacks: total only, free only, both, neither.
* Direct used-block API takes precedence over derived used = total - free.
* ``bytes_per_block_estimate`` propagates through the snapshot.
* Latency probe install:
  - returns inert handle when ``enable=False``.
  - returns inert handle on no-known-path block_manager.
  - returns inert handle when no swap-in attr is callable.
  - wraps the first available callable from
    ``_SWAP_IN_WRAP_CANDIDATES``.
  - records per-event wall-time on each invocation.
  - teardown restores original behaviour; idempotent.
* Peak tracker tracks max, ignores unreadable samples.
* Composes additively (no shared state) with mock cache_aware /
  extended_pinning install attribute names.

No torch, no vllm, no GPU. Real-vLLM verification is part of
TIER5A.3 GPU smoke.
"""

from __future__ import annotations

import time
from typing import Any, List

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from kv_policy.swap_telemetry import (
    CpuSwapPoolPeakTracker,
    CpuSwapPoolSnapshot,
    SwapInLatencyProbe,
    _percentile_ms,
    _read_allocator_block_counts,
    _resolve_block_size_tokens,
    _resolve_cpu_allocator,
    _SWAP_IN_WRAP_CANDIDATES,
    install_swap_in_latency_probe,
    read_cpu_swap_pool,
)


# ---------------------------------------------------------------- #
# Mock vLLM allocator shapes
# ---------------------------------------------------------------- #


class _MockCpuAllocator:
    """CPU allocator with the attributes vLLM 0.7.x exposes.

    Configurable per-test for which getters / methods are
    present; absence of an attribute simulates an older vLLM
    minor version.
    """

    def __init__(
        self,
        *,
        num_total_blocks: int = 0,
        num_free_blocks: int = 0,
        num_used_blocks: int | None = None,
        swap_in_callable: Any = None,
        expose_total_as_method: bool = False,
        expose_free_as_method: bool = True,
    ) -> None:
        if expose_total_as_method:
            self.num_total_blocks = lambda: num_total_blocks
        else:
            self.num_total_blocks = num_total_blocks
        if expose_free_as_method:
            self.get_num_free_blocks = lambda: num_free_blocks
        else:
            self.num_free_blocks = num_free_blocks
        if num_used_blocks is not None:
            self.num_used_blocks = num_used_blocks
        if swap_in_callable is not None:
            # Assign by the first wrap-candidate name so the probe
            # resolves it.
            setattr(self, "swap_in", swap_in_callable)


class _MockBlockAllocatorV2Property:
    """Mock CpuGpuBlockAllocator with property-form cpu_allocator."""

    def __init__(self, cpu_allocator: Any) -> None:
        self.cpu_allocator = cpu_allocator


class _MockBlockAllocatorV2Dict:
    """Mock CpuGpuBlockAllocator with dict-form _allocators."""

    def __init__(self, cpu_allocator: Any, *, key: str = "Device.CPU") -> None:
        self._allocators = {key: cpu_allocator}


class _MockBlockManagerV2Property:
    def __init__(
        self, cpu_allocator: Any, *, block_size: int = 32,
    ) -> None:
        self.block_allocator = _MockBlockAllocatorV2Property(cpu_allocator)
        self.block_size = block_size


class _MockBlockManagerV2Dict:
    def __init__(
        self, cpu_allocator: Any, *, block_size: int = 32,
        key: str = "Device.CPU",
    ) -> None:
        self.block_allocator = _MockBlockAllocatorV2Dict(
            cpu_allocator, key=key,
        )
        self.block_size = block_size


class _MockBlockManagerV1:
    """Mock V1 block manager: cpu_allocator directly on the
    block_manager, no block_allocator wrapper."""

    def __init__(
        self, cpu_allocator: Any, *, block_size: int = 16,
    ) -> None:
        self.cpu_allocator = cpu_allocator
        # V1 didn't expose block_size on the block_manager directly;
        # the cache_config did. Mirror that.
        self._cache_config = type(
            "CacheConfig", (), {"block_size": block_size}
        )()


class _MockBlockManagerNoPath:
    """Mock block manager with no allocator at all — exercises the
    no_known_path fallback."""

    pass


# ---------------------------------------------------------------- #
# Allocator path resolution
# ---------------------------------------------------------------- #


def test_resolve_cpu_allocator_v2_property():
    cpu = _MockCpuAllocator(num_total_blocks=4096, num_free_blocks=4000)
    bm = _MockBlockManagerV2Property(cpu)
    allocator, hint = _resolve_cpu_allocator(bm)
    assert allocator is cpu
    assert hint == "v2_block_allocator.cpu_allocator"


def test_resolve_cpu_allocator_v2_dict():
    cpu = _MockCpuAllocator(num_total_blocks=4096, num_free_blocks=4000)
    bm = _MockBlockManagerV2Dict(cpu)
    allocator, hint = _resolve_cpu_allocator(bm)
    assert allocator is cpu
    assert hint == "v2_block_allocator._allocators[CPU]"


def test_resolve_cpu_allocator_v1_direct():
    cpu = _MockCpuAllocator(num_total_blocks=4096, num_free_blocks=4000)
    bm = _MockBlockManagerV1(cpu)
    allocator, hint = _resolve_cpu_allocator(bm)
    assert allocator is cpu
    assert hint == "v1_block_manager.cpu_allocator"


def test_resolve_cpu_allocator_no_known_path():
    bm = _MockBlockManagerNoPath()
    allocator, hint = _resolve_cpu_allocator(bm)
    assert allocator is None
    assert hint == "no_known_path"


# ---------------------------------------------------------------- #
# Block-count read
# ---------------------------------------------------------------- #


def test_read_allocator_block_counts_total_and_free_attrs():
    cpu = _MockCpuAllocator(
        num_total_blocks=1000, num_free_blocks=900,
        expose_free_as_method=False,
    )
    used, total = _read_allocator_block_counts(cpu)
    assert used == 100
    assert total == 1000


def test_read_allocator_block_counts_free_as_method():
    cpu = _MockCpuAllocator(
        num_total_blocks=1000, num_free_blocks=900,
        expose_free_as_method=True,
    )
    used, total = _read_allocator_block_counts(cpu)
    assert used == 100
    assert total == 1000


def test_read_allocator_block_counts_total_as_method():
    cpu = _MockCpuAllocator(
        num_total_blocks=1000, num_free_blocks=900,
        expose_total_as_method=True,
    )
    used, total = _read_allocator_block_counts(cpu)
    assert used == 100
    assert total == 1000


def test_read_allocator_block_counts_direct_used_wins():
    """When the allocator exposes ``num_used_blocks`` directly,
    the read uses it verbatim instead of derived total-free."""
    cpu = _MockCpuAllocator(
        num_total_blocks=1000, num_free_blocks=999,
        num_used_blocks=42,
    )
    used, total = _read_allocator_block_counts(cpu)
    assert used == 42       # direct, not total-free=1
    assert total == 1000


def test_read_allocator_block_counts_no_attrs():
    """Allocator exposes neither total nor free — used returns
    -1 sentinel meaning 'unreadable'."""
    cpu = object()
    used, total = _read_allocator_block_counts(cpu)
    assert used == -1
    assert total == 0


# ---------------------------------------------------------------- #
# Block-size resolution
# ---------------------------------------------------------------- #


def test_resolve_block_size_tokens_from_block_manager():
    bm = _MockBlockManagerV2Property(
        _MockCpuAllocator(), block_size=32,
    )
    assert _resolve_block_size_tokens(bm) == 32


def test_resolve_block_size_tokens_from_cache_config():
    bm = _MockBlockManagerV1(_MockCpuAllocator(), block_size=16)
    assert _resolve_block_size_tokens(bm) == 16


def test_resolve_block_size_tokens_fallback():
    bm = _MockBlockManagerNoPath()
    assert _resolve_block_size_tokens(bm, fallback=99) == 99


# ---------------------------------------------------------------- #
# read_cpu_swap_pool snapshot
# ---------------------------------------------------------------- #


def test_read_cpu_swap_pool_v2_property_with_use():
    cpu = _MockCpuAllocator(num_total_blocks=1024, num_free_blocks=900)
    bm = _MockBlockManagerV2Property(cpu, block_size=32)
    snap = read_cpu_swap_pool(bm, bytes_per_block_estimate=4096)
    assert isinstance(snap, CpuSwapPoolSnapshot)
    assert snap.num_used_blocks == 124
    assert snap.num_total_blocks == 1024
    assert snap.block_size_tokens == 32
    assert snap.bytes_per_block_estimate == 4096
    assert snap.hint_path == "v2_block_allocator.cpu_allocator"


def test_read_cpu_swap_pool_no_path_marker():
    bm = _MockBlockManagerNoPath()
    snap = read_cpu_swap_pool(bm, block_size_fallback=16)
    assert snap.num_used_blocks == -1
    assert snap.num_total_blocks == 0
    assert snap.block_size_tokens == 16
    assert snap.hint_path == "no_known_path"


def test_read_cpu_swap_pool_utilization_and_bytes_helpers():
    cpu = _MockCpuAllocator(num_total_blocks=200, num_free_blocks=150)
    bm = _MockBlockManagerV2Property(cpu, block_size=32)
    snap = read_cpu_swap_pool(bm, bytes_per_block_estimate=4096)
    assert snap.utilization == pytest.approx(50 / 200)
    assert snap.num_used_bytes_estimate == 50 * 4096


def test_read_cpu_swap_pool_utilization_with_unreadable_used():
    cpu = object()
    bm = _MockBlockManagerV2Property(cpu, block_size=32)
    snap = read_cpu_swap_pool(bm)
    assert snap.num_used_blocks == -1
    # Utilization safely returns 0 when used is unreadable.
    assert snap.utilization == 0.0
    # Bytes estimate is 0 (both used unknown AND per-block estimate
    # unset).
    assert snap.num_used_bytes_estimate == 0


# ---------------------------------------------------------------- #
# SwapInLatencyProbe install + teardown
# ---------------------------------------------------------------- #


def test_install_probe_disabled_via_flag():
    cpu = _MockCpuAllocator()
    bm = _MockBlockManagerV2Property(cpu)
    handle = install_swap_in_latency_probe(bm, enable=False)
    assert handle.enabled is False
    assert handle.hint_path == "disabled"
    assert handle.latencies_ms == []
    handle.teardown()  # no-op; idempotent
    handle.teardown()


def test_install_probe_no_known_path_returns_disabled_handle():
    bm = _MockBlockManagerNoPath()
    handle = install_swap_in_latency_probe(bm)
    assert handle.enabled is False
    assert handle.hint_path == "no_known_path"


def test_install_probe_no_swap_attr_returns_disabled():
    cpu = _MockCpuAllocator(num_total_blocks=1, num_free_blocks=1)
    # cpu has no swap_in / swap_in_blocks / _swap_in / swap_blocks_in
    bm = _MockBlockManagerV2Property(cpu)
    handle = install_swap_in_latency_probe(bm)
    assert handle.enabled is False
    assert handle.hint_path.endswith("/no_swap_in_attr")


def test_install_probe_wraps_first_candidate_swap_in():
    calls: List[tuple] = []

    def fake_swap_in(*args, **kwargs):
        calls.append((args, kwargs))
        return "OK"

    cpu = _MockCpuAllocator(swap_in_callable=fake_swap_in)
    bm = _MockBlockManagerV2Property(cpu)
    handle = install_swap_in_latency_probe(bm)
    assert handle.enabled is True
    assert handle.wrap_target_name == "swap_in"

    # Invoke the wrapped method; it should delegate + record time.
    result = cpu.swap_in("a", "b", flag=True)
    assert result == "OK"
    assert calls == [(("a", "b"), {"flag": True})]
    assert len(handle.latencies_ms) == 1
    assert handle.latencies_ms[0] >= 0.0

    # Aggregates.
    assert handle.stats()["call_count"] == 1
    assert handle.stats()["p50_ms"] >= 0.0
    assert handle.stats()["enabled"] is True

    handle.teardown()
    # After teardown the wrap should be reverted; calling swap_in
    # delegates to the original (not the wrap).
    cpu.swap_in("c")
    # latencies_ms should NOT grow after teardown.
    assert len(handle.latencies_ms) == 1


def test_install_probe_records_multiple_events_in_order():
    def slow_in(_payload):
        time.sleep(0.001)
        return None

    cpu = _MockCpuAllocator(swap_in_callable=slow_in)
    bm = _MockBlockManagerV2Property(cpu)
    handle = install_swap_in_latency_probe(bm)
    try:
        for i in range(5):
            cpu.swap_in(i)
        assert len(handle.latencies_ms) == 5
        # Each event should record positive wall time (we slept).
        for ms in handle.latencies_ms:
            assert ms > 0.0
        # p50 and p99 should be non-negative and ordered.
        stats = handle.stats()
        assert stats["p50_ms"] <= stats["p99_ms"]
        assert stats["mean_ms"] > 0.0
    finally:
        handle.teardown()
    assert handle.stats()["torn_down"] is True


def test_install_probe_teardown_is_idempotent():
    cpu = _MockCpuAllocator(swap_in_callable=lambda: None)
    bm = _MockBlockManagerV2Property(cpu)
    handle = install_swap_in_latency_probe(bm)
    handle.teardown()
    handle.teardown()        # second teardown silent
    assert handle.stats()["torn_down"] is True


def test_swap_in_candidate_list_is_documented():
    """Sanity: the candidate name list is non-empty and includes
    the canonical swap_in name."""
    assert "swap_in" in _SWAP_IN_WRAP_CANDIDATES
    assert len(_SWAP_IN_WRAP_CANDIDATES) >= 2


def test_record_ms_rejects_negative():
    handle = SwapInLatencyProbe(
        enabled=True, hint_path="", wrap_target_name="swap_in",
    )
    with pytest.raises(ValueError):
        handle.record_ms(-1.0)


def test_record_ms_silent_when_disabled():
    handle = SwapInLatencyProbe(
        enabled=False, hint_path="disabled", wrap_target_name="",
    )
    handle.record_ms(5.0)
    assert handle.latencies_ms == []


# ---------------------------------------------------------------- #
# Percentile helper
# ---------------------------------------------------------------- #


def test_percentile_ms_empty_returns_zero():
    assert _percentile_ms([], 0.50) == 0.0
    assert _percentile_ms([], 0.99) == 0.0


def test_percentile_ms_single_returns_value():
    assert _percentile_ms([3.0], 0.50) == 3.0
    assert _percentile_ms([3.0], 0.99) == 3.0


def test_percentile_ms_linear_interpolation():
    """Type-7 (R / numpy default) linear interpolation between
    sorted samples — same convention as the runner's existing
    _compute_p50_p99_ms helper. For 5 samples [1,2,3,4,5]:
      p50 rank = 0.5*(5-1) = 2.0 → exactly s[2] = 3.0
      p99 rank = 0.99*4 = 3.96 → 0.96*s[4] + 0.04*s[3] = 4.96
    """
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _percentile_ms(samples, 0.50) == pytest.approx(3.0)
    assert _percentile_ms(samples, 0.99) == pytest.approx(4.96)


# ---------------------------------------------------------------- #
# CpuSwapPoolPeakTracker
# ---------------------------------------------------------------- #


def test_peak_tracker_tracks_max_used():
    tracker = CpuSwapPoolPeakTracker()
    for used in [10, 50, 30, 75, 60]:
        snap = CpuSwapPoolSnapshot(
            num_used_blocks=used,
            num_total_blocks=100,
            block_size_tokens=32,
            bytes_per_block_estimate=0,
            hint_path="v2",
        )
        tracker.observe(snap)
    assert tracker.peak_used_blocks == 75
    assert tracker.final_used_blocks == 60   # last sample
    assert tracker.total_blocks == 100
    assert tracker.n_samples == 5
    assert tracker.n_unreadable_samples == 0


def test_peak_tracker_ignores_unreadable_samples_for_peak():
    tracker = CpuSwapPoolPeakTracker()
    # mix of readable and unreadable.
    readable_used = [20, 40, 30]
    for u in readable_used:
        tracker.observe(CpuSwapPoolSnapshot(
            num_used_blocks=u, num_total_blocks=100,
            block_size_tokens=32, bytes_per_block_estimate=0,
            hint_path="v2",
        ))
    # Insert an unreadable snapshot between samples.
    tracker.observe(CpuSwapPoolSnapshot(
        num_used_blocks=-1, num_total_blocks=0,
        block_size_tokens=0, bytes_per_block_estimate=0,
        hint_path="no_known_path",
    ))
    assert tracker.peak_used_blocks == 40
    assert tracker.final_used_blocks == 30   # unchanged by unreadable
    assert tracker.n_samples == 4
    assert tracker.n_unreadable_samples == 1


def test_peak_tracker_bytes_estimates():
    tracker = CpuSwapPoolPeakTracker()
    tracker.observe(CpuSwapPoolSnapshot(
        num_used_blocks=50, num_total_blocks=100,
        block_size_tokens=32, bytes_per_block_estimate=4096,
        hint_path="v2",
    ))
    tracker.observe(CpuSwapPoolSnapshot(
        num_used_blocks=20, num_total_blocks=100,
        block_size_tokens=32, bytes_per_block_estimate=4096,
        hint_path="v2",
    ))
    assert tracker.peak_used_bytes_estimate == 50 * 4096
    assert tracker.final_used_bytes_estimate == 20 * 4096
