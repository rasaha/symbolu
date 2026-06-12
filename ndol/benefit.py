"""The unified, regime-gated benefit function.

This is the genuinely novel piece (and the highest-risk one): every primitive
optimises a different objective in different units — latency (us), endurance
(P/E cycles), bus bandwidth. The benefit function normalises them under
regime-dependent weights and makes the two live policy decisions:

  1. should_speculate  — issue VSP prefetch? (only when it pays in this regime)
  2. should_pushdown    — run a scan in-controller (INCS) or ship raw bytes?

The weights flip with the operating regime (§2.1): latency-bound favours
saving t_R; bandwidth-bound favours saving bus bytes and refuses speculation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import NANDModel, Regime


@dataclass
class BenefitWeights:
    w_latency: float
    w_endurance: float
    w_bandwidth: float


# Regime-gated weights. Latency-bound: spend bandwidth to save t_R.
# Bandwidth-bound: protect the bus, never speculate.
REGIME_WEIGHTS: dict[Regime, BenefitWeights] = {
    Regime.LATENCY_BOUND: BenefitWeights(w_latency=1.0, w_endurance=0.2, w_bandwidth=0.1),
    Regime.BANDWIDTH_BOUND: BenefitWeights(w_latency=0.2, w_endurance=0.3, w_bandwidth=1.0),
}


@dataclass
class BenefitFunction:
    model: NANDModel

    def should_speculate(
        self, regime: Regime, predictor_confidence: float, idle_dies: int
    ) -> bool:
        """VSP gate. Speculate only in the latency-bound regime, with idle dies,
        when the expected t_R saved outweighs the bandwidth wasted on misses."""
        if regime is Regime.BANDWIDTH_BOUND or idle_dies <= 0:
            return False
        w = REGIME_WEIGHTS[regime]
        expected_gain = predictor_confidence * self.model.t_read_single() * w.w_latency
        waste_cost = (1.0 - predictor_confidence) * self.model.t_xfer_us() * w.w_bandwidth
        return expected_gain > waste_cost

    def should_pushdown(
        self,
        regime: Regime,
        d_total: int,
        d_result: int,
        ops_per_byte: float,
        fabric_gops: float,
        host_compute_us: float,
    ) -> tuple[bool, float, float]:
        """INCS-CR gate — the corrected §3.5 decision.

        Includes the ops/byte term the v0.1 doc omitted: in-controller compute
        only wins when the fabric can out-stream the host bus. Returns
        (pushdown?, t_incs_us, t_host_us).
        """
        # Internal scan time, bounded by either compute or internal fabric bandwidth.
        t_compute_nand = d_total * ops_per_byte / (fabric_gops * 1e9) * 1e6  # us
        t_internal = d_total / (self.model.bw_internal_gbps * 1000.0)
        t_result = d_result / (self.model.bw_bus_gbps * 1000.0)
        t_incs = max(t_compute_nand, t_internal) + t_result

        # Host path: ship everything over the bus, then compute on the host.
        t_host = d_total / (self.model.bw_bus_gbps * 1000.0) + host_compute_us

        # In the bandwidth-bound regime the bus is the scarce resource, so the
        # bandwidth-amplification of pushdown is worth more — tie-break to INCS.
        if regime is Regime.BANDWIDTH_BOUND and t_incs <= t_host * 1.05:
            return True, t_incs, t_host
        return t_incs < t_host, t_incs, t_host
