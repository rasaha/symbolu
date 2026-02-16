"""
Configuration for PCAM simulator.

Defines hardware parameters, timing models, and validation thresholds
as specified in Appendix H.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class InterconnectType(Enum):
    """Host-device interconnect options with latency/bandwidth characteristics."""
    PCIE_GEN5_X16 = "pcie_gen5_x16"  # 150ns base, 32 GB/s
    CXL_2_0 = "cxl_2_0"              # 80ns base, 64 GB/s
    CXL_3_0 = "cxl_3_0"              # 50ns base, 128 GB/s
    ON_PACKAGE = "on_package"         # 20ns base, 256 GB/s


@dataclass
class InterconnectConfig:
    """Interconnect timing parameters."""
    interconnect_type: InterconnectType = InterconnectType.CXL_2_0

    @property
    def base_latency_ns(self) -> float:
        """One-way latency in nanoseconds."""
        latencies = {
            InterconnectType.PCIE_GEN5_X16: 150.0,
            InterconnectType.CXL_2_0: 80.0,
            InterconnectType.CXL_3_0: 50.0,
            InterconnectType.ON_PACKAGE: 20.0,
        }
        return latencies[self.interconnect_type]

    @property
    def bandwidth_gbps(self) -> float:
        """Bandwidth in GB/s."""
        bandwidths = {
            InterconnectType.PCIE_GEN5_X16: 32.0,
            InterconnectType.CXL_2_0: 64.0,
            InterconnectType.CXL_3_0: 128.0,
            InterconnectType.ON_PACKAGE: 256.0,
        }
        return bandwidths[self.interconnect_type]


@dataclass
class BankConfig:
    """Memory bank configuration."""
    num_banks: int = 64
    bank_width_bits: int = 256
    bank_cycle_ns: float = 2.0
    entries_per_bank: int = 16384  # 1M entries / 64 banks


@dataclass
class TopKConfig:
    """Top-K selection network configuration."""
    k_values: List[int] = field(default_factory=lambda: [64, 128, 256])
    default_k: int = 256
    selection_latency_ns: float = 44.0  # For K=256 (9-stage merge pipeline)


@dataclass
class PipelineConfig:
    """Pipeline timing configuration."""
    # ATTEND pipeline stages
    query_hash_cycles: int = 10
    bank_address_cycles: int = 2
    result_format_cycles: int = 2
    command_decode_ns: float = 5.0

    # UPDATE pipeline
    write_coalesce_buffer_size: int = 64
    rmw_latency_ns: float = 10.0  # Read-modify-write


@dataclass
class AcceptanceThresholds:
    """
    Validation acceptance thresholds from Appendix H.

    These are the "must win" criteria for PCAM validation.
    """
    # Gate G1: Quality-preserving memory reduction
    min_context_multiplier: float = 2.0  # >=2x effective context
    min_memory_reduction: float = 0.30   # OR >=30% less KV memory

    # Gate G2: Throughput win
    min_throughput_improvement: float = 0.15  # >=15% tok/s improvement

    # Gate G3: Tail latency control
    max_p99_overhead: float = 0.05  # <=5% degradation

    # Hardware feasibility (v2 gate)
    max_attend_p50_ns: float = 100.0
    max_attend_p99_ns: float = 500.0
    min_attend_throughput: float = 20e6  # 20M ops/sec
    min_update_throughput: float = 100e6  # 100M ops/sec (coalesced)
    max_area_mm2: float = 12.0   # Updated for K=256 (10.3mm² estimated)
    max_power_w: float = 5.0

    # Quality metrics
    min_candidate_coverage: float = 0.80  # >=80% of true top-K
    max_quality_degradation: float = 0.01  # <1% quality loss


@dataclass
class PCAMConfig:
    """
    Complete PCAM simulator configuration.

    Combines all sub-configurations with sensible defaults
    matching the specification in Appendix H.
    """
    # Core capacity
    max_entries: int = 1_000_000  # 1M attention relationships
    max_sequences: int = 64       # Max concurrent sequences
    max_blocks_per_sequence: int = 4096

    # Sub-configurations
    interconnect: InterconnectConfig = field(default_factory=InterconnectConfig)
    banks: BankConfig = field(default_factory=BankConfig)
    topk: TopKConfig = field(default_factory=TopKConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    thresholds: AcceptanceThresholds = field(default_factory=AcceptanceThresholds)

    # Decay configuration
    default_decay_rate: float = 0.99
    decay_interval_steps: int = 100

    # Simulation settings
    cycle_time_ns: float = 1.0  # 1GHz clock
    enable_bank_conflicts: bool = True
    enable_queueing: bool = True

    def calculate_attend_latency(
        self,
        num_candidates: int,
        bank_conflicts: int = 0,
    ) -> float:
        """
        Calculate expected ATTEND latency in nanoseconds.

        Total = Host_to_Device + Command_Decode + Bank_Access +
                TopK_Selection + Result_Format + Device_to_Host
        """
        # Interconnect round-trip
        interconnect_latency = 2 * self.interconnect.base_latency_ns

        # Command decode
        decode_latency = self.pipeline.command_decode_ns

        # Bank access (parallel across banks, serial if conflicts)
        base_bank_cycles = (num_candidates + self.banks.num_banks - 1) // self.banks.num_banks
        conflict_cycles = bank_conflicts * 1  # Each conflict adds one cycle
        bank_latency = (base_bank_cycles + conflict_cycles) * self.banks.bank_cycle_ns

        # Top-K selection
        topk_latency = self.topk.selection_latency_ns

        # Result formatting
        format_latency = self.pipeline.result_format_cycles * self.cycle_time_ns

        return (
            interconnect_latency +
            decode_latency +
            bank_latency +
            topk_latency +
            format_latency
        )

    def calculate_update_latency(self, coalesced_count: int = 1) -> float:
        """Calculate expected UPDATE latency in nanoseconds."""
        interconnect_latency = 2 * self.interconnect.base_latency_ns
        decode_latency = self.pipeline.command_decode_ns

        # Read-modify-write, amortized across coalesced updates
        rmw_latency = self.pipeline.rmw_latency_ns * coalesced_count

        return interconnect_latency + decode_latency + rmw_latency
