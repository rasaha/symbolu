"""
Hardware Feasibility Realism Tests.

Tests that validate hardware assumptions:
- ATTEND/UPDATE rate requirements
- Write endurance modeling
- Queueing under load (Little's law)
- Concurrency stress
"""

import pytest
import math
import random
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import deque

from simulator.pcam.core.config import PCAMConfig, InterconnectType


@dataclass
class QueueState:
    """State for queueing simulation."""
    queue: deque = field(default_factory=deque)
    current_time_ns: float = 0.0
    total_wait_time: float = 0.0
    max_queue_depth: int = 0
    num_requests: int = 0


class QueueingSimulator:
    """
    Simulate bank queueing under load.

    Uses M/D/1 queueing model approximation:
    - Arrivals: Poisson (realistic for independent requests)
    - Service: Deterministic (fixed bank access time)
    - Servers: 1 per bank
    """

    def __init__(
        self,
        num_banks: int = 64,
        bank_cycle_ns: float = 2.0,
        num_bank_ports: int = 1,  # Ports per bank
    ):
        self.num_banks = num_banks
        self.bank_cycle_ns = bank_cycle_ns
        self.num_bank_ports = num_bank_ports
        self.bank_queues = [QueueState() for _ in range(num_banks)]

    def simulate_attend(
        self,
        arrival_time_ns: float,
        blocks_needed: List[int],
    ) -> Tuple[float, int, int]:
        """
        Simulate ATTEND operation.

        Returns: (completion_time_ns, max_wait_ns, total_conflicts)
        """
        max_completion = arrival_time_ns
        total_conflicts = 0

        for block_id in blocks_needed:
            bank_id = block_id % self.num_banks
            queue = self.bank_queues[bank_id]

            # When can we start service?
            service_start = max(arrival_time_ns, queue.current_time_ns)

            # Wait time
            wait_time = service_start - arrival_time_ns
            if wait_time > 0:
                total_conflicts += 1

            # Service completion
            completion = service_start + self.bank_cycle_ns

            # Update queue state
            queue.current_time_ns = completion
            queue.total_wait_time += wait_time
            queue.num_requests += 1
            queue.max_queue_depth = max(
                queue.max_queue_depth,
                int(wait_time / self.bank_cycle_ns)
            )

            max_completion = max(max_completion, completion)

        return max_completion, int(max_completion - arrival_time_ns), total_conflicts

    def get_stats(self) -> Dict:
        """Get aggregate statistics."""
        total_requests = sum(q.num_requests for q in self.bank_queues)
        total_wait = sum(q.total_wait_time for q in self.bank_queues)
        max_depth = max(q.max_queue_depth for q in self.bank_queues)

        return {
            "total_requests": total_requests,
            "avg_wait_ns": total_wait / max(1, total_requests),
            "max_queue_depth": max_depth,
            "bank_utilization": [
                q.num_requests / max(1, total_requests / self.num_banks)
                for q in self.bank_queues
            ],
        }


@dataclass
class WriteEnduranceModel:
    """Model write endurance for PCAM memory cells."""
    # Technology parameters
    technology: str = "MRAM"
    writes_per_cell: int = 10**12  # MRAM: practically unlimited
    # For PCM: ~10^8, for RRAM: ~10^6-10^8

    # PCAM parameters
    num_entries: int = 1_000_000
    writes_per_update: int = 1  # Writes per UPDATE operation

    def calculate_lifetime(
        self,
        updates_per_second: float,
        hours_per_day: float = 24.0,
    ) -> Dict:
        """
        Calculate expected memory lifetime.

        Returns dict with lifetime estimates.
        """
        writes_per_day = updates_per_second * 3600 * hours_per_day
        writes_per_year = writes_per_day * 365

        # Assume uniform distribution across entries
        writes_per_cell_per_year = writes_per_year * self.writes_per_update / self.num_entries

        years_to_failure = self.writes_per_cell / writes_per_cell_per_year

        return {
            "technology": self.technology,
            "writes_per_cell_limit": self.writes_per_cell,
            "updates_per_second": updates_per_second,
            "writes_per_cell_per_year": writes_per_cell_per_year,
            "expected_lifetime_years": years_to_failure,
            "meets_5_year_target": years_to_failure >= 5,
        }


class TestOpsRateRequirements:
    """Tests for required operations rate."""

    def test_attend_rate_calculation(self):
        """Calculate required ATTEND ops/sec for various configs."""
        configs = [
            # (batch_size, layers, heads, tokens_per_sec)
            ("7B, batch=8", 8, 32, 32, 500),
            ("7B, batch=32", 32, 32, 32, 200),
            ("70B, batch=8", 8, 80, 64, 100),
            ("70B, batch=32", 32, 80, 64, 50),
        ]

        print("\n" + "=" * 70)
        print("ATTEND OPS/SEC REQUIREMENTS")
        print("=" * 70)
        print()
        print(f"{'Config':<20} {'Batch':>6} {'Layers':>7} {'Heads':>6} {'TPS':>6} {'ATTEND/s':>12}")
        print("-" * 65)

        for name, batch, layers, heads, tps in configs:
            # One ATTEND per (batch * layer * head) per token
            attend_per_token = batch * layers * heads
            attend_per_sec = attend_per_token * tps

            print(
                f"{name:<20} "
                f"{batch:>6} "
                f"{layers:>7} "
                f"{heads:>6} "
                f"{tps:>6} "
                f"{attend_per_sec:>12,}"
            )

        print()
        print("Target: >20M ops/sec for hardware feasibility")

    def test_update_rate_calculation(self):
        """Calculate required UPDATE ops/sec."""
        configs = [
            # (name, attend_per_sec, avg_k)
            ("7B light", 4_000_000, 64),
            ("7B heavy", 16_000_000, 64),
            ("70B light", 5_000_000, 128),
            ("70B heavy", 20_000_000, 128),
        ]

        print("\n" + "=" * 70)
        print("UPDATE OPS/SEC REQUIREMENTS")
        print("=" * 70)
        print()
        print(f"{'Config':<15} {'ATTEND/s':>12} {'K':>6} {'UPDATE/s':>15} {'Coalesced':>12}")
        print("-" * 65)

        for name, attend_per_sec, k in configs:
            # Updates = attends * k
            update_per_sec = attend_per_sec * k
            # With 16x coalescing
            coalesced = update_per_sec // 16

            print(
                f"{name:<15} "
                f"{attend_per_sec:>12,} "
                f"{k:>6} "
                f"{update_per_sec:>15,} "
                f"{coalesced:>12,}"
            )

        print()
        print("Target: >100M ops/sec (coalesced) for hardware feasibility")


class TestQueueingBehavior:
    """Tests for queueing under load."""

    def test_queueing_vs_load(self):
        """Test queueing behavior at different load levels."""
        loads = [0.1, 0.3, 0.5, 0.7, 0.9]  # Fraction of max capacity

        # Max capacity: 64 banks * (1/2ns per access) = 32B ops/sec theoretical
        max_ops_per_sec = 64 * (1e9 / 2)  # 32 billion/sec theoretical

        print("\n" + "=" * 70)
        print("QUEUEING BEHAVIOR VS LOAD")
        print("=" * 70)
        print()
        print(f"{'Load':>8} {'Ops/sec':>15} {'Avg Wait':>12} {'Max Queue':>12} {'p99 Wait':>12}")
        print("-" * 65)

        for load in loads:
            sim = QueueingSimulator(num_banks=64, bank_cycle_ns=2.0)

            ops_per_sec = int(max_ops_per_sec * load * 0.01)  # Scale down for simulation
            num_ops = 10000
            interval_ns = 1e9 / ops_per_sec

            wait_times = []
            time = 0.0

            for _ in range(num_ops):
                # Random blocks (simulating hash distribution)
                blocks = [random.randint(0, 1000) for _ in range(16)]
                completion, wait, conflicts = sim.simulate_attend(time, blocks)
                wait_times.append(wait)
                time += interval_ns + random.expovariate(1 / interval_ns) * 0.5

            avg_wait = sum(wait_times) / len(wait_times)
            sorted_waits = sorted(wait_times)
            p99_wait = sorted_waits[int(0.99 * len(sorted_waits))]
            stats = sim.get_stats()

            print(
                f"{load:>8.0%} "
                f"{ops_per_sec:>15,} "
                f"{avg_wait:>12.1f}ns "
                f"{stats['max_queue_depth']:>12} "
                f"{p99_wait:>12.1f}ns"
            )

    def test_concurrent_sequences_queueing(self):
        """Test queueing with multiple concurrent sequences."""
        concurrent_counts = [1, 4, 8, 16, 32, 64]

        print("\n" + "=" * 70)
        print("QUEUEING VS CONCURRENT SEQUENCES")
        print("=" * 70)
        print()
        print(f"{'Concurrent':>10} {'Conflicts':>12} {'Avg Wait':>12} {'Max Depth':>12}")
        print("-" * 50)

        for concurrent in concurrent_counts:
            sim = QueueingSimulator(num_banks=64, bank_cycle_ns=2.0)

            # Each sequence does 100 attends, all starting at same time
            total_conflicts = 0
            total_wait = 0
            max_depth = 0

            for seq in range(concurrent):
                time = 0.0
                for _ in range(100):
                    blocks = [random.randint(seq * 100, seq * 100 + 100) for _ in range(16)]
                    completion, wait, conflicts = sim.simulate_attend(time, blocks)
                    total_conflicts += conflicts
                    total_wait += wait
                    time = completion + 10  # 10ns gap between ops

            avg_wait = total_wait / (concurrent * 100)
            stats = sim.get_stats()

            print(
                f"{concurrent:>10} "
                f"{total_conflicts:>12,} "
                f"{avg_wait:>12.1f}ns "
                f"{stats['max_queue_depth']:>12}"
            )


class TestWriteEndurance:
    """Tests for write endurance modeling."""

    def test_mram_endurance(self):
        """Test MRAM endurance under various loads."""
        loads = [
            ("Light (10K/s)", 10_000),
            ("Medium (100K/s)", 100_000),
            ("Heavy (1M/s)", 1_000_000),
            ("Extreme (10M/s)", 10_000_000),
        ]

        print("\n" + "=" * 70)
        print("MRAM WRITE ENDURANCE")
        print("=" * 70)
        print()

        model = WriteEnduranceModel(
            technology="MRAM",
            writes_per_cell=10**12,
            num_entries=1_000_000,
        )

        print(f"Technology: MRAM (10^12 writes/cell)")
        print(f"Entries: {model.num_entries:,}")
        print()
        print(f"{'Load':<20} {'Updates/s':>12} {'Lifetime':>15} {'5yr Target':>12}")
        print("-" * 65)

        for name, updates in loads:
            result = model.calculate_lifetime(updates)
            status = "✓" if result["meets_5_year_target"] else "✗"
            print(
                f"{name:<20} "
                f"{updates:>12,} "
                f"{result['expected_lifetime_years']:>15.1f} years "
                f"{status:>12}"
            )

    def test_pcm_endurance(self):
        """Test PCM endurance (more constrained)."""
        loads = [
            ("Light", 10_000),
            ("Medium", 100_000),
            ("Heavy", 1_000_000),
        ]

        print("\n" + "=" * 70)
        print("PCM WRITE ENDURANCE (more constrained)")
        print("=" * 70)
        print()

        model = WriteEnduranceModel(
            technology="PCM",
            writes_per_cell=10**8,  # PCM is more limited
            num_entries=1_000_000,
        )

        print(f"Technology: PCM (10^8 writes/cell)")
        print(f"Entries: {model.num_entries:,}")
        print()
        print(f"{'Load':<20} {'Updates/s':>12} {'Lifetime':>15} {'5yr Target':>12}")
        print("-" * 65)

        for name, updates in loads:
            result = model.calculate_lifetime(updates)
            status = "✓" if result["meets_5_year_target"] else "✗"
            print(
                f"{name:<20} "
                f"{updates:>12,} "
                f"{result['expected_lifetime_years']:>15.1f} years "
                f"{status:>12}"
            )


class TestLatencyBreakdown:
    """Tests for detailed latency breakdown."""

    def test_attend_latency_breakdown(self):
        """Break down ATTEND latency by component."""
        config = PCAMConfig()

        print("\n" + "=" * 70)
        print("ATTEND LATENCY BREAKDOWN")
        print("=" * 70)
        print()

        # Components
        interconnect = config.interconnect.base_latency_ns * 2  # Round trip
        decode = config.pipeline.command_decode_ns
        hash_compute = config.pipeline.query_hash_cycles * config.cycle_time_ns
        bank_access = config.banks.bank_cycle_ns * 2  # Avg 2 cycles
        topk = config.topk.selection_latency_ns
        format_result = config.pipeline.result_format_cycles * config.cycle_time_ns

        total = interconnect + decode + hash_compute + bank_access + topk + format_result

        components = [
            ("Interconnect (RT)", interconnect),
            ("Command decode", decode),
            ("Hash compute", hash_compute),
            ("Bank access", bank_access),
            ("Top-K selection", topk),
            ("Result format", format_result),
        ]

        print(f"Interconnect: {config.interconnect.interconnect_type.value}")
        print()
        print(f"{'Component':<25} {'Latency':>12} {'Fraction':>10}")
        print("-" * 50)

        for name, lat in components:
            print(f"{name:<25} {lat:>12.1f}ns {lat/total:>10.1%}")

        print("-" * 50)
        print(f"{'TOTAL':<25} {total:>12.1f}ns {1.0:>10.1%}")
        print()

        # Compare interconnects
        print("Latency by Interconnect:")
        for itype in InterconnectType:
            config.interconnect.interconnect_type = itype
            lat = config.calculate_attend_latency(64, 0)
            print(f"  {itype.value:<20} {lat:>8.1f}ns")

    def test_latency_vs_bank_conflicts(self):
        """Test how latency degrades with conflicts."""
        config = PCAMConfig()
        conflict_counts = [0, 5, 10, 20, 50, 100]

        print("\n" + "=" * 70)
        print("ATTEND LATENCY VS BANK CONFLICTS")
        print("=" * 70)
        print()
        print(f"{'Conflicts':>10} {'Latency':>12} {'Δ from 0':>12}")
        print("-" * 40)

        base_latency = config.calculate_attend_latency(64, 0)

        for conflicts in conflict_counts:
            lat = config.calculate_attend_latency(64, conflicts)
            delta = lat - base_latency
            print(f"{conflicts:>10} {lat:>12.1f}ns {delta:>+12.1f}ns")
