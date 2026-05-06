"""Tier model for the Mode A benchmark harness.

Models a multi-level memory hierarchy (HBM ↔ DDR / NVMe / HBF)
with per-tier capacity, latency, and bandwidth. The cache tracks
which blocks live on which tier and what the cumulative read /
write traffic is per tier.

Cost numbers are 2025 ballparks pinned by the test suite — a
report from this harness is comparable across runs because the
cost model does not silently drift.

Sources for the cost numbers (all are conservative QD1 random-
access numbers, not best-case sequential, because KV-cache
spillover is random-access by definition):

* HBM3e: 1.15 TB/s aggregate per stack, ~200 ns access — public
  vendor specs (Micron HBM3e, SK hynix HBM3e).
* DDR5-6400: ~64 GB/s per channel, ~80 ns random access —
  JEDEC + recent benchmarks.
* NVMe Gen5 SSD (random read, QD1): ~14 GB/s sequential best-
  case, but random read at QD1 is ~10-50 µs latency with
  effective bandwidth far below sequential. We model 5 GB/s
  effective + 50 µs to reflect real KV-spill access patterns.
* HBF (High Bandwidth Flash, SanDisk's announced AI-tier
  flash): vendor-claimed ~200 GB/s aggregate at ~2 µs
  latency. These are forward-looking specs from public
  announcements; they may shift as silicon ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class TierSpec:
    """One tier of the memory hierarchy.

    All fields are required and immutable so a benchmark report's
    cost basis is fully captured by the spec — no defaults can
    mask which tier was actually modeled.
    """

    name: str
    capacity_bytes: int
    read_latency_ns: float
    write_latency_ns: float
    read_bw_bytes_per_s: float
    write_bw_bytes_per_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("TierSpec.name must be a non-empty string")
        if self.capacity_bytes <= 0:
            raise ValueError(
                f"TierSpec.capacity_bytes must be positive; got {self.capacity_bytes}"
            )
        for field_name in (
            "read_latency_ns",
            "write_latency_ns",
            "read_bw_bytes_per_s",
            "write_bw_bytes_per_s",
        ):
            value = getattr(self, field_name)
            if not (value > 0):
                raise ValueError(
                    f"TierSpec.{field_name} must be positive; got {value}"
                )

    def transfer_latency_ns(self, n_bytes: int, *, write: bool = False) -> float:
        """Latency to read or write `n_bytes` from / to this tier.

        Models latency as a fixed access cost plus a bandwidth-
        bounded transfer cost. This is the simplest model that
        gets the order-of-magnitude right; a more detailed model
        would add queue depth + parallelism, but those don't
        change the relative comparison between policies.
        """
        if n_bytes < 0:
            raise ValueError(f"n_bytes must be non-negative; got {n_bytes}")
        access = self.write_latency_ns if write else self.read_latency_ns
        bw = self.write_bw_bytes_per_s if write else self.read_bw_bytes_per_s
        transfer_s = n_bytes / bw
        return access + transfer_s * 1e9


# 2025 reference tier configurations — pinned by tests.
# Constructed eagerly so an import-time error surfaces if the
# numbers ever go out of range.

HBM_DDR_NVME_2025: Tuple[TierSpec, ...] = (
    TierSpec(
        name="HBM",
        capacity_bytes=80 * 1024**3,           # 80 GB HBM3e
        read_latency_ns=200.0,
        write_latency_ns=200.0,
        read_bw_bytes_per_s=int(1.15 * 1024**4),   # 1.15 TB/s
        write_bw_bytes_per_s=int(1.15 * 1024**4),
    ),
    TierSpec(
        name="DDR",
        capacity_bytes=512 * 1024**3,           # 512 GB DDR5
        read_latency_ns=80.0,
        write_latency_ns=80.0,
        read_bw_bytes_per_s=int(64 * 1024**3),
        write_bw_bytes_per_s=int(64 * 1024**3),
    ),
    TierSpec(
        name="NVMe",
        capacity_bytes=4 * 1024**4,             # 4 TB NVMe Gen5
        read_latency_ns=50_000.0,                # 50 µs random-read
        write_latency_ns=80_000.0,
        read_bw_bytes_per_s=int(5 * 1024**3),
        write_bw_bytes_per_s=int(2 * 1024**3),
    ),
)

HBM_HBF_NVME_2025: Tuple[TierSpec, ...] = (
    TierSpec(
        name="HBM",
        capacity_bytes=80 * 1024**3,
        read_latency_ns=200.0,
        write_latency_ns=200.0,
        read_bw_bytes_per_s=int(1.15 * 1024**4),
        write_bw_bytes_per_s=int(1.15 * 1024**4),
    ),
    TierSpec(
        name="HBF",
        capacity_bytes=512 * 1024**3,
        read_latency_ns=2_000.0,                 # 2 µs vendor-claimed
        write_latency_ns=10_000.0,
        read_bw_bytes_per_s=int(200 * 1024**3),  # 200 GB/s
        write_bw_bytes_per_s=int(80 * 1024**3),
    ),
    TierSpec(
        name="NVMe",
        capacity_bytes=4 * 1024**4,
        read_latency_ns=50_000.0,
        write_latency_ns=80_000.0,
        read_bw_bytes_per_s=int(5 * 1024**3),
        write_bw_bytes_per_s=int(2 * 1024**3),
    ),
)


# Default block size (one KV block) — sized to roughly match
# Llama-3.1-8B with 16-token blocks under bf16 + GQA. Override
# via WorkloadSpec.block_bytes for other model sizes.
DEFAULT_BLOCK_BYTES: int = 2 * 1024 * 1024   # 2 MiB


@dataclass(frozen=True)
class AccessResult:
    """Outcome of one access against the TieredCache."""

    block_id: int
    hit_tier: str                  # which tier served the read
    promoted_to_tier_0: bool       # was the block promoted to tier 0?
    service_latency_ns: float


@dataclass(frozen=True)
class BlockTier:
    """Where a block currently lives + its size."""

    block_id: int
    tier_name: str
    size_bytes: int


class TierCounters:
    """Running counters per tier. Intentionally non-frozen — this
    is the metric sink that the runner mutates as it iterates."""

    def __init__(self, tier_names: Iterable[str]) -> None:
        names = tuple(tier_names)
        self.bytes_read: Dict[str, int] = {n: 0 for n in names}
        self.bytes_written: Dict[str, int] = {n: 0 for n in names}
        self.accesses_served: Dict[str, int] = {n: 0 for n in names}
        self.cumulative_latency_ns: Dict[str, float] = {n: 0.0 for n in names}
        self.evictions_to_tier: Dict[str, int] = {n: 0 for n in names}

    def record_read(self, tier: str, n_bytes: int, latency_ns: float) -> None:
        self.bytes_read[tier] += n_bytes
        self.cumulative_latency_ns[tier] += latency_ns
        self.accesses_served[tier] += 1

    def record_write(self, tier: str, n_bytes: int, latency_ns: float) -> None:
        self.bytes_written[tier] += n_bytes
        self.cumulative_latency_ns[tier] += latency_ns

    def record_eviction_to(self, tier: str) -> None:
        self.evictions_to_tier[tier] += 1

    def total_bytes_read(self) -> int:
        return sum(self.bytes_read.values())

    def total_bytes_written(self) -> int:
        return sum(self.bytes_written.values())

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            "bytes_read": dict(self.bytes_read),
            "bytes_written": dict(self.bytes_written),
            "accesses_served": dict(self.accesses_served),
            "cumulative_latency_ns": dict(self.cumulative_latency_ns),
            "evictions_to_tier": dict(self.evictions_to_tier),
        }


class TieredCache:
    """Simple deterministic multi-tier cache.

    Each tier has a capacity and a current set of blocks. Access:

      1. If the block is on tier 0, record hit, return.
      2. If the block is on a deeper tier, record hit on that
         tier, promote to tier 0 (record write to tier 0), evict
         if tier 0 is full (eviction cascades to tier 1).
      3. If the block is not present at all, record cold miss
         (caller is responsible for declaring "from where" the
         block came; we model this as "synthesised" — no tier
         counters incremented for the read, but tier 0 write
         counters are incremented as if the block was newly
         materialised).

    Eviction selection is delegated to a separate :class:`Policy`
    so the harness can compare policies head-to-head with the
    cost model held constant.
    """

    def __init__(
        self,
        tiers: Tuple[TierSpec, ...],
        block_bytes: int = DEFAULT_BLOCK_BYTES,
    ) -> None:
        if len(tiers) < 2:
            raise ValueError("TieredCache requires at least 2 tiers")
        if block_bytes <= 0:
            raise ValueError(f"block_bytes must be positive; got {block_bytes}")
        self.tiers = tiers
        self.block_bytes = block_bytes
        self._tier_index: Dict[str, int] = {t.name: i for i, t in enumerate(tiers)}
        # Per-tier dict[block_id -> step_inserted]. Insertion order
        # is preserved so a "FIFO" eviction is the trivial pop.
        self._residency: List[Dict[int, int]] = [
            {} for _ in tiers
        ]
        self._step: int = 0
        self.counters = TierCounters(t.name for t in tiers)

    # -- introspection --

    def tier_capacity_blocks(self, tier_index: int) -> int:
        return self.tiers[tier_index].capacity_bytes // self.block_bytes

    def tier_full(self, tier_index: int) -> bool:
        return len(self._residency[tier_index]) >= self.tier_capacity_blocks(
            tier_index
        )

    def location(self, block_id: int) -> Optional[str]:
        for i, residents in enumerate(self._residency):
            if block_id in residents:
                return self.tiers[i].name
        return None

    def n_blocks_in_tier(self, tier_name: str) -> int:
        return len(self._residency[self._tier_index[tier_name]])

    # -- the access path --

    def access(self, block_id: int) -> AccessResult:
        """Read `block_id`. Promotes to tier 0 if it lived deeper."""
        self._step += 1

        # 1. Already on tier 0 — hot read, no movement.
        if block_id in self._residency[0]:
            tier = self.tiers[0]
            latency = tier.transfer_latency_ns(self.block_bytes, write=False)
            self.counters.record_read(tier.name, self.block_bytes, latency)
            return AccessResult(
                block_id=block_id,
                hit_tier=tier.name,
                promoted_to_tier_0=False,
                service_latency_ns=latency,
            )

        # 2. On a deeper tier — read from there + promote.
        for i in range(1, len(self.tiers)):
            if block_id in self._residency[i]:
                tier = self.tiers[i]
                read_latency = tier.transfer_latency_ns(
                    self.block_bytes, write=False
                )
                self.counters.record_read(
                    tier.name, self.block_bytes, read_latency
                )
                # Move into tier 0.
                self._residency[i].pop(block_id)
                promotion_latency = self._install_at_tier_0(block_id)
                return AccessResult(
                    block_id=block_id,
                    hit_tier=tier.name,
                    promoted_to_tier_0=True,
                    service_latency_ns=read_latency + promotion_latency,
                )

        # 3. Cold miss — synthesise into tier 0 without crediting
        # any slow tier (caller-supplied data, e.g. prefill).
        promotion_latency = self._install_at_tier_0(block_id)
        return AccessResult(
            block_id=block_id,
            hit_tier="cold",
            promoted_to_tier_0=True,
            service_latency_ns=promotion_latency,
        )

    def evict_from_tier_0(self, victim_block_ids: Iterable[int]) -> None:
        """Cascade `victim_block_ids` from tier 0 down. Each victim
        is written to tier 1 (if there's room), otherwise to tier 2
        (if there's room), otherwise dropped. Counters are updated
        accordingly. Callers should pass victim IDs returned by
        their :class:`Policy`."""
        for block_id in victim_block_ids:
            if block_id not in self._residency[0]:
                continue
            self._residency[0].pop(block_id)
            placed = False
            for i in range(1, len(self.tiers)):
                if not self._tier_at_capacity(i):
                    self._install_at_tier(i, block_id)
                    placed = True
                    break
            if not placed:
                # Even the deepest tier is full — block is dropped
                # (modelled as "lost," will need recomputation if
                # the policy asks for it again).
                pass

    # -- internal helpers --

    def _tier_at_capacity(self, tier_index: int) -> bool:
        return len(self._residency[tier_index]) >= self.tier_capacity_blocks(
            tier_index
        )

    def _install_at_tier_0(self, block_id: int) -> float:
        """Insert into tier 0; if full, the caller is expected to
        have evicted first. We don't auto-evict here because the
        eviction *policy* is external — auto-eviction would force
        an arbitrary policy choice."""
        return self._install_at_tier(0, block_id)

    def _install_at_tier(self, tier_index: int, block_id: int) -> float:
        if self._tier_at_capacity(tier_index):
            # Caller bug: should have evicted first.
            raise RuntimeError(
                f"tier {self.tiers[tier_index].name} is full; "
                f"caller must evict before installing block {block_id}"
            )
        self._residency[tier_index][block_id] = self._step
        tier = self.tiers[tier_index]
        latency = tier.transfer_latency_ns(self.block_bytes, write=True)
        self.counters.record_write(tier.name, self.block_bytes, latency)
        if tier_index > 0:
            self.counters.record_eviction_to(tier.name)
        return latency
