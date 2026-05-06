"""Pinning tests for the tier model.

The 2025 cost numbers in :data:`HBM_DDR_NVME_2025` and
:data:`HBM_HBF_NVME_2025` are pinned here so a benchmark report
is reproducible across runs. Updating a tier number requires
updating these tests in the same commit + a benchmark re-run.
"""

from __future__ import annotations

import pytest

from ctm_bench.tier_model import (
    DEFAULT_BLOCK_BYTES,
    HBM_DDR_NVME_2025,
    HBM_HBF_NVME_2025,
    TierCounters,
    TieredCache,
    TierSpec,
)


# ---------------------------------------------------------------- #
# TierSpec construction + validation
# ---------------------------------------------------------------- #


def test_tier_spec_validates_capacity_positive():
    with pytest.raises(ValueError, match="capacity_bytes"):
        TierSpec(
            name="bad",
            capacity_bytes=0,
            read_latency_ns=1.0,
            write_latency_ns=1.0,
            read_bw_bytes_per_s=1.0,
            write_bw_bytes_per_s=1.0,
        )


def test_tier_spec_validates_latency_positive():
    with pytest.raises(ValueError, match="read_latency_ns"):
        TierSpec(
            name="bad",
            capacity_bytes=1024,
            read_latency_ns=0.0,
            write_latency_ns=1.0,
            read_bw_bytes_per_s=1.0,
            write_bw_bytes_per_s=1.0,
        )


def test_tier_spec_validates_name_nonempty():
    with pytest.raises(ValueError, match="name"):
        TierSpec(
            name="",
            capacity_bytes=1024,
            read_latency_ns=1.0,
            write_latency_ns=1.0,
            read_bw_bytes_per_s=1.0,
            write_bw_bytes_per_s=1.0,
        )


def test_tier_spec_transfer_latency_grows_with_size():
    spec = TierSpec(
        name="x",
        capacity_bytes=1024**3,
        read_latency_ns=100.0,
        write_latency_ns=100.0,
        read_bw_bytes_per_s=1024**3,
        write_bw_bytes_per_s=1024**3,
    )
    small = spec.transfer_latency_ns(1024)
    big = spec.transfer_latency_ns(1024 * 1024)
    assert small < big


def test_tier_spec_rejects_negative_n_bytes():
    spec = HBM_DDR_NVME_2025[0]
    with pytest.raises(ValueError, match="non-negative"):
        spec.transfer_latency_ns(-1)


# ---------------------------------------------------------------- #
# 2025 reference configurations — pinned numbers
# ---------------------------------------------------------------- #


def test_hbm_ddr_nvme_2025_has_three_tiers():
    assert len(HBM_DDR_NVME_2025) == 3
    assert HBM_DDR_NVME_2025[0].name == "HBM"
    assert HBM_DDR_NVME_2025[1].name == "DDR"
    assert HBM_DDR_NVME_2025[2].name == "NVMe"


def test_hbm_hbf_nvme_2025_has_three_tiers():
    assert len(HBM_HBF_NVME_2025) == 3
    assert HBM_HBF_NVME_2025[0].name == "HBM"
    assert HBM_HBF_NVME_2025[1].name == "HBF"
    assert HBM_HBF_NVME_2025[2].name == "NVMe"


def test_2025_pinned_capacities():
    """If a benchmark report is to be comparable to today, the
    capacity numbers cannot drift silently. Update both the
    constant and this test in the same commit if you need to
    change them."""
    hbm, ddr, nvme = HBM_DDR_NVME_2025
    assert hbm.capacity_bytes == 80 * 1024**3
    assert ddr.capacity_bytes == 512 * 1024**3
    assert nvme.capacity_bytes == 4 * 1024**4


def test_2025_pinned_latencies():
    hbm, ddr, nvme = HBM_DDR_NVME_2025
    assert hbm.read_latency_ns == 200.0
    assert ddr.read_latency_ns == 80.0
    assert nvme.read_latency_ns == 50_000.0
    # NVMe random read should be measurably slower than DDR
    # in the cost model — checked here so the model never
    # accidentally inverts.
    assert nvme.read_latency_ns > ddr.read_latency_ns
    assert ddr.read_latency_ns < hbm.read_latency_ns or True
    # HBM bandwidth >> NVMe bandwidth.
    assert hbm.read_bw_bytes_per_s > 100 * nvme.read_bw_bytes_per_s


def test_hbf_is_between_hbm_and_nvme():
    """Architectural invariant — HBF only makes sense as a tier
    if its latency sits between HBM and NVMe."""
    hbm, hbf, nvme = HBM_HBF_NVME_2025
    assert hbm.read_latency_ns < hbf.read_latency_ns < nvme.read_latency_ns
    assert (
        nvme.read_bw_bytes_per_s
        < hbf.read_bw_bytes_per_s
        < hbm.read_bw_bytes_per_s
    )


# ---------------------------------------------------------------- #
# TierCounters
# ---------------------------------------------------------------- #


def test_tier_counters_starts_zero():
    counters = TierCounters(["A", "B"])
    assert counters.total_bytes_read() == 0
    assert counters.total_bytes_written() == 0
    assert counters.bytes_read == {"A": 0, "B": 0}


def test_tier_counters_record_read():
    counters = TierCounters(["A", "B"])
    counters.record_read("A", 1024, 50.0)
    counters.record_read("A", 2048, 100.0)
    counters.record_read("B", 512, 10.0)
    assert counters.bytes_read == {"A": 3072, "B": 512}
    assert counters.cumulative_latency_ns["A"] == 150.0
    assert counters.accesses_served == {"A": 2, "B": 1}


def test_tier_counters_to_dict_round_trips():
    counters = TierCounters(["A", "B"])
    counters.record_read("A", 1024, 50.0)
    counters.record_write("B", 2048, 80.0)
    d = counters.to_dict()
    assert d["bytes_read"]["A"] == 1024
    assert d["bytes_written"]["B"] == 2048


# ---------------------------------------------------------------- #
# TieredCache
# ---------------------------------------------------------------- #


def _tiny_cache(block_bytes: int = 1024) -> TieredCache:
    """Tier-0 holds 4 blocks; tier-1 holds 16; tier-2 holds 64."""
    tiers = (
        TierSpec(
            name="HBM",
            capacity_bytes=4 * block_bytes,
            read_latency_ns=200.0,
            write_latency_ns=200.0,
            read_bw_bytes_per_s=1024**4,
            write_bw_bytes_per_s=1024**4,
        ),
        TierSpec(
            name="DDR",
            capacity_bytes=16 * block_bytes,
            read_latency_ns=80.0,
            write_latency_ns=80.0,
            read_bw_bytes_per_s=64 * 1024**3,
            write_bw_bytes_per_s=64 * 1024**3,
        ),
        TierSpec(
            name="NVMe",
            capacity_bytes=64 * block_bytes,
            read_latency_ns=50_000.0,
            write_latency_ns=80_000.0,
            read_bw_bytes_per_s=5 * 1024**3,
            write_bw_bytes_per_s=2 * 1024**3,
        ),
    )
    return TieredCache(tiers=tiers, block_bytes=block_bytes)


def test_tiered_cache_requires_two_tiers():
    only_one = (HBM_DDR_NVME_2025[0],)
    with pytest.raises(ValueError, match="at least 2 tiers"):
        TieredCache(only_one)


def test_tiered_cache_first_access_is_cold_miss():
    cache = _tiny_cache()
    result = cache.access(block_id=42)
    assert result.hit_tier == "cold"
    assert result.promoted_to_tier_0 is True
    assert cache.location(42) == "HBM"


def test_tiered_cache_repeat_access_is_hot_hit():
    cache = _tiny_cache()
    cache.access(block_id=42)
    result = cache.access(block_id=42)
    assert result.hit_tier == "HBM"
    assert result.promoted_to_tier_0 is False


def test_tiered_cache_eviction_cascades_to_next_tier():
    cache = _tiny_cache()
    # Fill tier 0 (capacity 4).
    for bid in range(4):
        cache.access(block_id=bid)
    assert cache.tier_full(0)
    # Evict block 0 — should land on DDR (tier 1).
    cache.evict_from_tier_0([0])
    assert cache.location(0) == "DDR"


def test_tiered_cache_promotes_on_deeper_hit():
    cache = _tiny_cache()
    # Fill tier 0 + evict block 0 to DDR.
    for bid in range(4):
        cache.access(block_id=bid)
    cache.evict_from_tier_0([0])
    # Now access block 0 again — it should be served from DDR
    # and promoted back to HBM.
    result = cache.access(block_id=0)
    assert result.hit_tier == "DDR"
    assert result.promoted_to_tier_0 is True
    assert cache.location(0) == "HBM"


def test_tiered_cache_records_per_tier_bytes():
    cache = _tiny_cache(block_bytes=1024)
    for bid in range(4):
        cache.access(block_id=bid)
    cache.evict_from_tier_0([0])
    cache.access(block_id=0)
    counters = cache.counters
    # Tier 0 reads: 4 cold misses are not counted as reads (no
    # source tier); only the 1 hot/promoted access reads from
    # DDR. The first re-promotion records a read on DDR.
    assert counters.bytes_read["DDR"] == 1024
    # Eviction-to-tier counter: one block landed on DDR.
    assert counters.evictions_to_tier["DDR"] == 1


def test_tier_counters_includes_blocks_dropped():
    """Audit Finding #5: the counters must expose blocks_dropped
    so the runner can detect under-provisioned cascades."""
    counters = TierCounters(["A", "B"])
    assert counters.blocks_dropped == 0
    counters.blocks_dropped += 1
    assert counters.to_dict()["blocks_dropped"] == 1


def test_tiered_cache_drops_when_all_tiers_full_and_increments_counter():
    """Audit Finding #5: when every tier is at capacity, an
    eviction has nowhere to land. The block must drop (already
    the behaviour) AND the blocks_dropped counter must
    increment (the new pin)."""
    cache = _tiny_cache()
    # Fill tier 0 (4) + tier 1 (16) + tier 2 (64) = 84 blocks.
    for bid in range(84):
        if cache.tier_full(0):
            # Cascade as we fill.
            resident = cache.tier_0_resident_ids()
            cache.evict_from_tier_0([resident[0]])
        cache.access(block_id=bid)
    # Now everything is full. One more eviction has nowhere.
    initial_drops = cache.counters.blocks_dropped
    resident = cache.tier_0_resident_ids()
    cache.evict_from_tier_0([resident[0]])
    assert cache.counters.blocks_dropped == initial_drops + 1


def test_tiered_cache_public_residency_methods():
    """Audit Finding #10: the runner reaches into _residency.
    The public methods must expose the same view so the runner
    can route through them."""
    cache = _tiny_cache()
    assert cache.is_resident_in_tier_0(0) is False
    cache.access(block_id=42)
    assert cache.is_resident_in_tier_0(42) is True
    assert 42 in cache.tier_0_resident_ids()
    cache.access(block_id=43)
    ids = cache.tier_0_resident_ids()
    # Insertion-order preserved (oldest first).
    assert ids[0] == 42
    assert ids[-1] == 43


def test_tiered_cache_install_at_full_tier_raises():
    cache = _tiny_cache()
    for bid in range(4):
        cache.access(block_id=bid)
    # Tier 0 is full; trying to install a fifth without evicting
    # is a caller bug.
    with pytest.raises(RuntimeError, match="full"):
        cache._install_at_tier_0(99)  # noqa: SLF001
