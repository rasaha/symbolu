"""NAND latency model, operating regimes, and metrics.

This is the *only* place hardware behaviour is modelled. The controller logic
itself is real software; these numbers let us score it against the §2 baseline
read model without a chip:

    t_read_single = t_R + (P / BW_bus)

All times are in microseconds (us). Bandwidths are GB/s; 1 GB/s = 1000 B/us.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(Enum):
    """NAND cell density tiers. Faster array sense ↔ lower density."""

    SLC = "SLC"
    TLC = "TLC"
    QLC = "QLC"


# Array read time t_R per tier, microseconds (public-datasheet order of magnitude).
T_R_US: dict[Tier, float] = {
    Tier.SLC: 25.0,
    Tier.TLC: 50.0,
    Tier.QLC: 100.0,
}


class Regime(Enum):
    """Which resource is scarce (see §2.1 of the design doc).

    LATENCY_BOUND   low queue depth, dies idle  → array time t_R dominates.
                    MDPC interleave + VSP win (spare bandwidth is genuinely free).
    BANDWIDTH_BOUND high queue depth, bus saturated → ONFI bus dominates.
                    QACC + INCS win; speculation must be throttled to zero.
    """

    LATENCY_BOUND = "latency_bound"
    BANDWIDTH_BOUND = "bandwidth_bound"


@dataclass
class NANDModel:
    """Analytical read-cost model. GB/s → B/us via the 1000 factor."""

    page_bytes: int = 16384
    bw_bus_gbps: float = 2.0       # ONFI 4.x per-channel bus bandwidth
    bw_internal_gbps: float = 8.0  # internal NAND fabric (for INCS pushdown)
    decompress_us_per_page: float = 2.0

    def t_xfer_us(self, nbytes: int | None = None) -> float:
        nbytes = self.page_bytes if nbytes is None else nbytes
        return nbytes / (self.bw_bus_gbps * 1000.0)

    def t_read_single(self, tier: Tier = Tier.TLC) -> float:
        """Naive single-page read latency — the baseline every speedup beats."""
        return T_R_US[tier] + self.t_xfer_us()


@dataclass
class RegimeDetector:
    """Classifies the operating regime from observed queue depth.

    Below the die-saturation point (queue_depth < n_dies) the array is the
    bottleneck and there is spare bus/die time to exploit. At or above it the
    bus is saturated.
    """

    n_dies: int = 16
    saturation_qd: int | None = None

    def __post_init__(self) -> None:
        if self.saturation_qd is None:
            self.saturation_qd = self.n_dies

    def classify(self, queue_depth: int) -> Regime:
        assert self.saturation_qd is not None
        if queue_depth >= self.saturation_qd:
            return Regime.BANDWIDTH_BOUND
        return Regime.LATENCY_BOUND

    def idle_dies(self, queue_depth: int) -> int:
        return max(0, self.n_dies - queue_depth)


@dataclass
class ReadCost:
    """Decomposed latency of one served read, so batch interleave (§3.1.c)
    can hide all but one t_R behind the transfers."""

    t_r: float          # array sense time (0 if served from prefetch buffer)
    t_xfer: float       # bus transfer (+ decompress) time
    served: str         # 'vsp' | 'backing'

    @property
    def total(self) -> float:
        return self.t_r + self.t_xfer


@dataclass
class Metrics:
    """Accumulated modeled performance vs. the naive baseline."""

    requests: int = 0
    modeled_latency_us: float = 0.0
    baseline_latency_us: float = 0.0
    vsp_hits: int = 0
    vsp_misses: int = 0
    dedup_saved: int = 0
    spec_issued: int = 0
    bytes_from_bus: float = 0.0
    pe_cycles: int = 0
    scans: int = 0
    scans_pushed_down: int = 0

    def speedup(self) -> float:
        if self.modeled_latency_us <= 0:
            return 1.0
        return self.baseline_latency_us / self.modeled_latency_us

    def vsp_hit_rate(self) -> float:
        total = self.vsp_hits + self.vsp_misses
        return self.vsp_hits / total if total else 0.0

    def spec_wasted(self) -> int:
        # Prefetches that were never served. Approximate, but bounded.
        return max(0, self.spec_issued - self.vsp_hits)
