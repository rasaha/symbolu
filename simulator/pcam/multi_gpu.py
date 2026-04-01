"""
Multi-GPU CXL Shared Edge Pool for PCAM.

Implements full cross-GPU attention pattern sharing via CXL 3.0:
  1. CXLCoherenceTracker: MESI protocol for edge state consistency
  2. CXLCapacityManager: Dynamic pool expansion/contraction
  3. Per-host quota management with min/max share bounds
  4. Cross-host edge discovery: GPU-B finds patterns learned by GPU-A
  5. MultiGPUPCAMCoordinator: orchestrates multiple TieredPCAMInterface instances

Architecture:
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │  GPU 0  │  │  GPU 1  │  │  GPU 2  │  │  GPU 3  │
  │  BRAM   │  │  BRAM   │  │  BRAM   │  │  BRAM   │
  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
       │            │            │            │
       └────────────┴─────┬──────┴────────────┘
                          │
                ┌─────────▼──────────┐
                │  CXL 3.0 Shared    │
                │  Edge Pool         │
                │  ┌───────────────┐ │
                │  │ Coherence     │ │
                │  │ Tracker (MESI)│ │
                │  ├───────────────┤ │
                │  │ Capacity      │ │
                │  │ Manager       │ │
                │  ├───────────────┤ │
                │  │ Edge Discovery│ │
                │  │ Service       │ │
                │  └───────────────┘ │
                └────────────────────┘
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from collections import defaultdict
import math

from .core.tiered_config import CXLPoolConfig, TieredPCAMConfig
from .tiered_pcam import (
    CXLEdgePool,
    CompressedBlockEntry,
    TieredPCAMInterface,
)


# ---------------------------------------------------------------------------
# MESI Coherence States
# ---------------------------------------------------------------------------

class CoherenceState(Enum):
    """CXL.cache coherence states for shared edge entries."""
    INVALID = "I"     # No host has a valid copy
    SHARED = "S"      # Multiple hosts have read-only copies
    EXCLUSIVE = "E"   # One host has sole access (clean)
    MODIFIED = "M"    # One host has modified the entry (dirty)


# ---------------------------------------------------------------------------
# CXL Coherence Tracker
# ---------------------------------------------------------------------------

class CXLCoherenceTracker:
    """CXL 3.0 cross-host coherence tracker for PCAM edges.

    Implements CXL.cache-style coherence to maintain consistency when
    multiple GPUs share attention edge state through the CXL pool.

    When GPU-A updates an edge score, all other GPUs caching that entry
    must be invalidated (or see the updated value). This tracker manages:
    - Sharer lists per entry (which GPUs have cached copies)
    - Exclusive access grants for writes (with back-invalidation)
    - Invalidation cost modeling (batched for efficiency)
    - Eviction penalties for shared entries

    Reference: CXL 3.0 Specification, Chapter 4 (CXL.cache)
    """

    def __init__(self, config: CXLPoolConfig):
        self._config = config

        # entry_key -> set of host_ids with cached copies
        self._sharers: Dict[Tuple[int, int], Set[int]] = {}

        # entry_key -> host_id with exclusive/modified access
        self._exclusive_owner: Dict[Tuple[int, int], Optional[int]] = {}

        # entry_key -> current coherence state
        self._state: Dict[Tuple[int, int], CoherenceState] = {}

        # Statistics
        self.invalidations_sent: int = 0
        self.sharers_added: int = 0
        self.exclusive_grants: int = 0
        self.state_transitions: int = 0

    def add_sharer(
        self,
        entry_key: Tuple[int, int],
        host_id: int,
    ) -> None:
        """Record that host_id has a cached copy of this entry.

        Transitions:
          I → S (first sharer)
          S → S (additional sharer, within limit)
          E → S (exclusive downgraded to shared)
        """
        if not self._config.enabled:
            return

        if entry_key not in self._sharers:
            self._sharers[entry_key] = set()

        sharers = self._sharers[entry_key]
        if len(sharers) >= self._config.max_sharers_per_entry:
            return  # At CXL.cache sharer limit

        sharers.add(host_id)
        self.sharers_added += 1

        # Update state
        old_state = self._state.get(entry_key, CoherenceState.INVALID)
        if old_state == CoherenceState.INVALID:
            self._state[entry_key] = CoherenceState.EXCLUSIVE
            self._exclusive_owner[entry_key] = host_id
        elif old_state == CoherenceState.EXCLUSIVE and len(sharers) > 1:
            self._state[entry_key] = CoherenceState.SHARED
            self._exclusive_owner.pop(entry_key, None)
            self.state_transitions += 1
        # SHARED stays SHARED, MODIFIED handled by request_exclusive

    def remove_sharer(
        self,
        entry_key: Tuple[int, int],
        host_id: int,
    ) -> None:
        """Remove host_id from sharers of this entry."""
        if entry_key in self._sharers:
            self._sharers[entry_key].discard(host_id)
            if not self._sharers[entry_key]:
                del self._sharers[entry_key]
                self._state.pop(entry_key, None)

        if self._exclusive_owner.get(entry_key) == host_id:
            self._exclusive_owner.pop(entry_key, None)

    def get_sharers(self, entry_key: Tuple[int, int]) -> Set[int]:
        """Get set of hosts with cached copies."""
        return self._sharers.get(entry_key, set()).copy()

    def get_sharer_count(self, entry_key: Tuple[int, int]) -> int:
        """Get number of hosts sharing this entry."""
        return len(self._sharers.get(entry_key, set()))

    def get_state(self, entry_key: Tuple[int, int]) -> CoherenceState:
        """Get current coherence state for an entry."""
        return self._state.get(entry_key, CoherenceState.INVALID)

    def request_exclusive(
        self,
        entry_key: Tuple[int, int],
        host_id: int,
    ) -> Tuple[int, float]:
        """Host requests exclusive access for write. Invalidates other sharers.

        Transitions:
          S → M (invalidate all others, grant exclusive)
          E → M (already exclusive, just upgrade)
          M → M (already modified by same host, no-op)

        Returns:
            (num_invalidations, latency_cost_ns)
        """
        if not self._config.enabled:
            return 0, 0.0

        sharers = self._sharers.get(entry_key, set())
        others = sharers - {host_id}
        num_invalidations = len(others)

        # Invalidate all other sharers
        for other in list(others):
            sharers.discard(other)
            self.invalidations_sent += 1

        # Grant exclusive/modified
        self._exclusive_owner[entry_key] = host_id
        self._state[entry_key] = CoherenceState.MODIFIED
        self.exclusive_grants += 1
        self.state_transitions += 1

        # Compute invalidation latency (batched)
        latency = self.compute_invalidation_cost_ns(num_invalidations)

        return num_invalidations, latency

    def on_eviction(
        self,
        entry_key: Tuple[int, int],
        host_id: int,
    ) -> None:
        """Entry evicted from pool. Clean up coherence state."""
        self.remove_sharer(entry_key, host_id)

    def compute_invalidation_cost_ns(self, num_invalidations: int) -> float:
        """Compute latency cost for N invalidations (batched)."""
        if num_invalidations <= 0:
            return 0.0
        batches = math.ceil(num_invalidations / self._config.invalidation_batch_size)
        return batches * self._config.invalidation_latency_ns

    def get_eviction_penalty(self, entry_key: Tuple[int, int]) -> float:
        """Get eviction score penalty for shared entries (higher = harder to evict)."""
        count = self.get_sharer_count(entry_key)
        if count <= 1:
            return 0.0
        return self._config.shared_entry_penalty * (count - 1)

    def get_stats(self) -> Dict:
        """Get coherence tracker statistics."""
        total_shared = sum(
            1 for s in self._sharers.values() if len(s) > 1
        )
        state_counts = defaultdict(int)
        for state in self._state.values():
            state_counts[state.value] += 1

        return {
            "invalidations_sent": self.invalidations_sent,
            "sharers_added": self.sharers_added,
            "exclusive_grants": self.exclusive_grants,
            "state_transitions": self.state_transitions,
            "total_tracked_entries": len(self._sharers),
            "shared_entries": total_shared,
            "state_distribution": dict(state_counts),
        }


# ---------------------------------------------------------------------------
# CXL Capacity Manager
# ---------------------------------------------------------------------------

class CXLCapacityManager:
    """CXL 3.0 dynamic capacity manager for PCAM edge pool.

    Manages expansion and contraction of the shared pool based on demand.
    Implements CXL 3.0 Dynamic Capacity Device (DCD) features:
    - Hot-add: grow pool when hosts are under memory pressure
    - Hot-remove: shrink pool when underutilized
    - Per-host demand tracking for fair rebalancing

    Reference: CXL 3.0 Specification, Chapter 11.3 (Dynamic Capacity Device)
    """

    def __init__(self, config: CXLPoolConfig, pool: CXLEdgePool):
        self._config = config
        self._pool = pool
        self._current_capacity = pool.capacity

        # Per-host demand tracking
        self._host_demand: Dict[int, int] = {
            h: 0 for h in range(config.num_hosts)
        }

        self._access_since_rebalance: int = 0

        # Statistics
        self.expansions: int = 0
        self.contractions: int = 0
        self.total_expanded: int = 0
        self.total_contracted: int = 0
        self.rebalances: int = 0

    def record_demand(self, host_id: int) -> None:
        """Record a pool access request from a host."""
        self._host_demand[host_id] = self._host_demand.get(host_id, 0) + 1
        self._access_since_rebalance += 1

    def should_rebalance(self) -> bool:
        """Check if it's time for a rebalance check."""
        return self._access_since_rebalance >= self._config.rebalance_interval

    def rebalance(self) -> Dict:
        """Check pool utilization and expand/contract as needed.

        Returns a dict describing the action taken.
        """
        if not self._config.enabled:
            return {"action": "none"}

        self._access_since_rebalance = 0
        self.rebalances += 1

        utilization = self._pool.size / max(1, self._current_capacity)

        if utilization >= self._config.expansion_threshold:
            return self._expand()

        if (utilization <= self._config.contraction_threshold
                and self._current_capacity > self._config.capacity_step):
            return self._contract()

        return {"action": "none", "utilization": utilization}

    def _expand(self) -> Dict:
        """Expand pool capacity."""
        step = self._config.capacity_step
        old_cap = self._current_capacity
        self._current_capacity += step
        self._pool.capacity = self._current_capacity
        self.expansions += 1
        self.total_expanded += step
        return {
            "action": "expand",
            "old_capacity": old_cap,
            "new_capacity": self._current_capacity,
            "step": step,
        }

    def _contract(self) -> Dict:
        """Contract pool capacity (never below current usage)."""
        step = self._config.capacity_step
        min_cap = self._pool.size + 1
        new_cap = max(min_cap, self._current_capacity - step)
        actual_step = self._current_capacity - new_cap
        if actual_step <= 0:
            return {"action": "none", "reason": "cannot_shrink_below_usage"}

        old_cap = self._current_capacity
        self._current_capacity = new_cap
        self._pool.capacity = self._current_capacity
        self.contractions += 1
        self.total_contracted += actual_step
        return {
            "action": "contract",
            "old_capacity": old_cap,
            "new_capacity": self._current_capacity,
            "step": actual_step,
        }

    def get_host_demand_share(self, host_id: int) -> float:
        """Get host's fraction of total demand."""
        total = sum(self._host_demand.values())
        if total == 0:
            return 1.0 / max(1, self._config.num_hosts)
        return self._host_demand.get(host_id, 0) / total

    @property
    def current_capacity(self) -> int:
        return self._current_capacity

    def get_stats(self) -> Dict:
        return {
            "current_capacity": self._current_capacity,
            "base_capacity": self._pool.capacity,
            "expansions": self.expansions,
            "contractions": self.contractions,
            "total_expanded": self.total_expanded,
            "total_contracted": self.total_contracted,
            "rebalances": self.rebalances,
            "host_demand": dict(self._host_demand),
        }


# ---------------------------------------------------------------------------
# Cross-Host Edge Discovery Service
# ---------------------------------------------------------------------------

class EdgeDiscoveryService:
    """Cross-GPU edge discovery for PCAM.

    When multiple GPUs process different parts of the same long context
    (tensor parallelism) or different requests in the same batch (data
    parallelism), they learn complementary attention patterns. This service
    allows GPU-B to discover high-value edges learned by GPU-A.

    Discovery modes:
    - PASSIVE: GPU discovers edges when it accesses CXL pool entries
              owned by other hosts (already implemented in CXLEdgePool.lookup)
    - ACTIVE:  GPU periodically scans CXL pool for high-scoring entries
              from other hosts that match its current workload pattern

    The active discovery is triggered during ATTEND when a GPU has low
    BRAM coverage, allowing it to "import" validated attention patterns
    from peer GPUs.
    """

    def __init__(self, config: CXLPoolConfig):
        self._config = config

        # Track which entries have been discovered by which hosts
        # (host_id, entry_key) -> discovery_step
        self._discoveries: Dict[Tuple[int, Tuple[int, int]], int] = {}

        # Statistics
        self.discoveries: int = 0
        self.discovery_hits: int = 0  # Discovered entries that were useful

    def discover_cross_host_edges(
        self,
        pool: CXLEdgePool,
        sequence_id: int,
        requesting_host: int,
        k: int,
        current_step: int,
    ) -> List[Tuple[int, float]]:
        """Actively discover high-value edges from other hosts.

        Scans the CXL pool for entries belonging to the same sequence
        but owned by different hosts. Returns top-K cross-host entries
        that exceed the discovery minimum score.

        Args:
            pool: The shared CXL edge pool
            sequence_id: Sequence to discover edges for
            requesting_host: The GPU requesting discovery
            k: Maximum entries to return
            current_step: Current simulation step

        Returns:
            List of (block_id, boosted_score) from other hosts' edges
        """
        if not self._config.discovery_enabled:
            return []

        candidates = []
        for (seq_id, block_id), entry in pool._entries.items():
            if seq_id != sequence_id:
                continue
            if entry.owner_host == requesting_host:
                continue  # Skip own entries
            if entry.score < self._config.discovery_min_score:
                continue

            # Check if already discovered recently
            disc_key = (requesting_host, (seq_id, block_id))
            last_disc = self._discoveries.get(disc_key, -1000)
            if current_step - last_disc < 50:  # Cooldown to avoid re-discovering
                continue

            # Apply cross-host validation boost
            # Edges validated by multiple hosts are more reliable
            num_sharers = len(entry.sharer_hosts)
            validation_boost = 1.0 + self._config.discovery_boost * num_sharers

            boosted_score = entry.score * validation_boost
            candidates.append((block_id, boosted_score))

        # Sort by boosted score and take top-K
        candidates.sort(key=lambda x: -x[1])
        result = candidates[:k]

        # Record discoveries
        for block_id, _ in result:
            disc_key = (requesting_host, (sequence_id, block_id))
            self._discoveries[disc_key] = current_step
            self.discoveries += 1

        return result

    def record_discovery_hit(self, host_id: int, entry_key: Tuple[int, int]) -> None:
        """Record that a discovered entry was actually useful (appeared in true top-K)."""
        self.discovery_hits += 1

    def get_stats(self) -> Dict:
        hit_rate = (
            self.discovery_hits / max(1, self.discoveries)
            if self.discoveries > 0 else 0.0
        )
        return {
            "discoveries": self.discoveries,
            "discovery_hits": self.discovery_hits,
            "discovery_hit_rate": hit_rate,
            "tracked_discoveries": len(self._discoveries),
        }


# ---------------------------------------------------------------------------
# Multi-GPU PCAM Coordinator
# ---------------------------------------------------------------------------

class MultiGPUPCAMCoordinator:
    """Orchestrates multiple TieredPCAMInterface instances sharing a CXL pool.

    Creates and manages N GPU-local PCAM instances that share a single
    CXL edge pool with full coherence, dynamic capacity, and cross-host
    edge discovery.

    Usage:
        config = TieredPCAMConfig.multi_gpu(num_gpus=4)
        coordinator = MultiGPUPCAMCoordinator(config)

        # Each GPU gets its own interface
        gpu0 = coordinator.get_gpu(0)
        gpu1 = coordinator.get_gpu(1)

        # Both share the same CXL pool
        gpu0.allocate_sequence(0, 4096)
        gpu1.allocate_sequence(0, 4096)

        # GPU 0 learns attention patterns
        gpu0.update(query_block_id=100, key_block_id=42, weight=0.8)

        # After demotion, GPU 1 can discover GPU 0's patterns via CXL
        candidates = coordinator.attend_with_discovery(
            host_id=1, query_block_id=100, k=64, sequence_id=0,
        )
    """

    def __init__(self, config: Optional[TieredPCAMConfig] = None):
        self.config = config or TieredPCAMConfig.multi_gpu()
        self.num_hosts = self.config.cxl.num_hosts

        # Shared CXL edge pool
        self.shared_pool = CXLEdgePool(
            config=self.config.cxl,
            bram_capacity=self.config.bram_capacity,
        )

        # Coherence tracker
        self.coherence = CXLCoherenceTracker(self.config.cxl)

        # Dynamic capacity manager
        self.capacity_manager = CXLCapacityManager(
            self.config.cxl, self.shared_pool,
        )

        # Edge discovery service
        self.discovery = EdgeDiscoveryService(self.config.cxl)

        # Per-GPU PCAM instances, all sharing the same CXL pool
        self._gpus: Dict[int, TieredPCAMInterface] = {}
        for host_id in range(self.num_hosts):
            gpu = TieredPCAMInterface(config=self.config, host_id=host_id)
            gpu.cxl_pool = self.shared_pool  # Share the pool
            self._gpus[host_id] = gpu

    def get_gpu(self, host_id: int) -> TieredPCAMInterface:
        """Get the PCAM interface for a specific GPU."""
        if host_id not in self._gpus:
            raise ValueError(f"GPU {host_id} not found (have {self.num_hosts} GPUs)")
        return self._gpus[host_id]

    def allocate_sequence(self, sequence_id: int, max_blocks: int) -> None:
        """Allocate a sequence on all GPUs."""
        for gpu in self._gpus.values():
            gpu.allocate_sequence(sequence_id, max_blocks)

    def free_sequence(self, sequence_id: int) -> None:
        """Free a sequence from all GPUs and the shared pool."""
        for gpu in self._gpus.values():
            gpu.free_sequence(sequence_id)

    def attend_with_discovery(
        self,
        host_id: int,
        query_block_id: int,
        k: int = 256,
        sequence_id: int = 0,
    ) -> Tuple[List[Tuple[int, float]], float, int]:
        """ATTEND with cross-host edge discovery.

        Augments the standard tiered ATTEND with edges discovered from
        other GPUs' attention patterns in the shared CXL pool.

        Returns:
            (candidates, latency_ns, bank_conflicts)
        """
        gpu = self.get_gpu(host_id)

        # Standard tiered ATTEND (BRAM + own CXL entries)
        candidates, latency, conflicts = gpu.attend(
            query_block_id=query_block_id,
            k=k,
            sequence_id=sequence_id,
        )

        # Cross-host edge discovery
        discovery_k = max(8, k // 8)  # Use 12.5% of K budget for discovery
        discovered = self.discovery.discover_cross_host_edges(
            pool=self.shared_pool,
            sequence_id=sequence_id,
            requesting_host=host_id,
            k=discovery_k,
            current_step=gpu._step,
        )

        if discovered:
            # Track coherence for discovered entries
            for block_id, score in discovered:
                entry_key = (sequence_id, block_id)
                self.coherence.add_sharer(entry_key, host_id)

            # Merge discovered edges into candidates
            existing_ids = {bid for bid, _ in candidates}
            merged = list(candidates)
            for bid, score in discovered:
                if bid not in existing_ids:
                    merged.append((bid, score))

            # Re-sort and trim to K
            merged.sort(key=lambda x: -x[1])
            candidates = merged[:k]

            # Discovery adds CXL latency (parallel with BRAM)
            latency = max(latency, self.config.cxl.access_latency_ns)

        # Track demand for capacity management
        self.capacity_manager.record_demand(host_id)
        if self.capacity_manager.should_rebalance():
            self.capacity_manager.rebalance()

        return candidates, latency, conflicts

    def update_with_coherence(
        self,
        host_id: int,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        sequence_id: int = 0,
    ) -> Tuple[bool, float]:
        """UPDATE with CXL coherence protocol.

        When a GPU updates an edge that exists in the CXL pool,
        the coherence tracker invalidates other GPUs' cached copies
        and the invalidation cost is added to the latency.
        """
        gpu = self.get_gpu(host_id)

        # Check if this entry is in the CXL pool (shared)
        entry_key = (sequence_id, key_block_id)
        entry = self.shared_pool.lookup(sequence_id, key_block_id, host_id)

        coherence_latency = 0.0
        if entry is not None and entry.owner_host != host_id:
            # Cross-host write: need exclusive access
            num_inv, inv_latency = self.coherence.request_exclusive(
                entry_key, host_id,
            )
            coherence_latency = inv_latency

        # Standard tiered update
        success, update_latency = gpu.update(
            query_block_id=query_block_id,
            key_block_id=key_block_id,
            weight=weight,
            sequence_id=sequence_id,
        )

        # Update coherence state
        if success and entry is not None:
            self.coherence.add_sharer(entry_key, host_id)

        total_latency = update_latency + coherence_latency
        return success, total_latency

    def step_all(self) -> None:
        """Advance step counter on all GPUs."""
        for gpu in self._gpus.values():
            gpu.step()

    def get_per_host_quota(self, host_id: int) -> Dict:
        """Get quota information for a specific host."""
        host_entries = self.shared_pool._host_entries.get(host_id, set())
        total = self.shared_pool.size
        share = len(host_entries) / max(1, self.shared_pool.capacity)

        return {
            "host_id": host_id,
            "entries_in_pool": len(host_entries),
            "pool_share": share,
            "min_share": self.config.cxl.per_host_min_share,
            "max_share": self.config.cxl.per_host_max_share,
            "within_quota": (
                self.config.cxl.per_host_min_share
                <= share
                <= self.config.cxl.per_host_max_share
            ) if total > 0 else True,
            "demand_share": self.capacity_manager.get_host_demand_share(host_id),
        }

    def get_stats(self) -> Dict:
        """Get comprehensive multi-GPU statistics."""
        per_gpu_stats = {}
        for host_id, gpu in self._gpus.items():
            per_gpu_stats[host_id] = {
                "bram": gpu.state.get_stats(),
                "tiered": (
                    gpu._tiered_sequences[0].get_stats()
                    if 0 in gpu._tiered_sequences else {}
                ),
                "quota": self.get_per_host_quota(host_id),
            }

        return {
            "num_hosts": self.num_hosts,
            "shared_pool": self.shared_pool.get_stats(),
            "coherence": self.coherence.get_stats(),
            "capacity": self.capacity_manager.get_stats(),
            "discovery": self.discovery.get_stats(),
            "per_gpu": per_gpu_stats,
        }
