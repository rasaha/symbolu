"""
Tiered PCAM: TurboQuant-compressed CXL overflow + multi-GPU shared edge pool.

Upgrades the base PCAM simulator with techniques from CTM+ vLLM:
  1. TQ-compressed CXL overflow tier: 6x effective edge capacity
  2. CXL shared edge pool: cross-GPU attention pattern sharing
  3. Access-driven tier promotion/demotion

Architecture:
  ┌──────────────────────┐    ┌─────────────────────────────────┐
  │  BRAM Tier (Hot)     │    │  CXL Pool Tier (Warm)           │
  │  1M entries, <100ns  │◄──►│  ~6M effective, ~250ns           │
  │  Full-precision edges│    │  TQ-compressed edge metadata     │
  │                      │    │  Shared across GPUs (CXL 3.0)   │
  └──────────────────────┘    └─────────────────────────────────┘
         ▲  demotion              ▲  eviction
         │  promotion             │
         └────────────────────────┘
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import math
import heapq

from .interface import PCAMInterface
from .core.config import PCAMConfig
from .core.state import AttentionState, BlockScore, SequenceState
from .core.tiered_config import (
    TieredPCAMConfig,
    TierType,
    CXLPoolConfig,
    TurboQuantEdgeConfig,
    TierPolicy,
)


# ---------------------------------------------------------------------------
# Compressed edge entry for CXL tier
# ---------------------------------------------------------------------------

@dataclass
class CompressedBlockEntry:
    """TQ-compressed block metadata stored in CXL pool.

    Compresses the full BlockScore into a compact representation:
    - Score quantized to Q4.4 fixed-point (8 bits vs 64-bit float)
    - Access count capped to 8 bits (0-255)
    - Query source count instead of full set
    - Optional: top-N edges by weight
    - Optional: TQ-compressed attention profile (PolarQuant + QJL)
    """
    block_id: int
    sequence_id: int

    # Compressed fields
    quantized_score: int = 0      # Q4.4 fixed-point (8 bits)
    access_count: int = 0         # Capped to 255
    query_source_count: int = 0   # How many unique queries accessed this
    last_access_step: int = 0
    cumulative_weight: float = 0.0

    # Optional compressed edges: (key_block_id, quantized_weight)
    compressed_edges: List[Tuple[int, int]] = field(default_factory=list)

    # TQ-compressed attention profile (PolarQuant + QJL)
    # None when profile compression is disabled
    compressed_profile: Optional[Dict] = None

    # Tier metadata
    demotion_step: int = 0        # When this was demoted from BRAM
    cxl_access_count: int = 0     # Accesses while in CXL tier
    owner_host: int = 0           # Which GPU owns this entry
    sharer_hosts: Set[int] = field(default_factory=set)

    @property
    def score(self) -> float:
        """Decompress score from Q4.4 to float."""
        return self.quantized_score / 16.0

    @score.setter
    def score(self, value: float) -> None:
        """Compress float score to Q4.4."""
        self.quantized_score = max(0, min(255, int(value * 16.0)))

    @property
    def has_profile(self) -> bool:
        """Whether this entry has a TQ-compressed attention profile."""
        return self.compressed_profile is not None

    def to_block_score(self) -> BlockScore:
        """Decompress back to full BlockScore (lossy)."""
        return BlockScore(
            block_id=self.block_id,
            score=self.score,
            last_access_step=self.last_access_step,
            access_count=min(self.access_count, 4095),
            cumulative_weight=self.cumulative_weight,
        )


def compress_block_score(
    bs: BlockScore,
    sequence_id: int,
    edges: Dict[Tuple[int, int], float],
    config: TurboQuantEdgeConfig,
    host_id: int = 0,
    profile_compressor: Optional["EdgeProfileCompressor"] = None,
    max_query_block: int = 0,
) -> CompressedBlockEntry:
    """Compress a full BlockScore into a CXL-tier entry.

    If profile_compressor is provided and config.enable_profile_compression
    is True, also builds and TQ-compresses the block's attention profile.
    """
    entry = CompressedBlockEntry(
        block_id=bs.block_id,
        sequence_id=sequence_id,
        access_count=min(bs.access_count, 255),
        query_source_count=len(bs.unique_query_sources),
        last_access_step=bs.last_access_step,
        cumulative_weight=bs.cumulative_weight,
        owner_host=host_id,
    )
    entry.score = bs.score

    # Optionally store top edges
    if config.store_edges_in_cxl:
        block_edges = [
            (key_id, weight)
            for (query_id, key_id), weight in edges.items()
            if query_id == bs.block_id or key_id == bs.block_id
        ]
        # Keep top-N by weight
        block_edges.sort(key=lambda x: -x[1])
        for key_id, weight in block_edges[:config.max_edges_per_block_cxl]:
            q_weight = max(0, min(255, int(weight * 16.0)))
            entry.compressed_edges.append((key_id, q_weight))

    # TQ-compress attention profile (PolarQuant + QJL)
    if (config.enable_profile_compression
            and profile_compressor is not None
            and edges):
        profile = profile_compressor.build_profile(
            block_id=bs.block_id,
            attention_edges=edges,
            max_query_block=max_query_block,
        )
        if profile.num_updates > 0:
            entry.compressed_profile = profile_compressor.compress(profile)

    return entry


# ---------------------------------------------------------------------------
# CXL Shared Edge Pool
# ---------------------------------------------------------------------------

class CXLEdgePool:
    """CXL 3.0 shared memory pool for PCAM edge state.

    Manages TQ-compressed edge entries across multiple GPU hosts.
    Provides coherence tracking and dynamic capacity management.
    """

    def __init__(self, config: CXLPoolConfig, bram_capacity: int):
        self.config = config
        self.capacity = int(bram_capacity * config.pool_capacity_multiplier)

        # Pool storage: (sequence_id, block_id) -> CompressedBlockEntry
        self._entries: Dict[Tuple[int, int], CompressedBlockEntry] = {}

        # Per-host tracking
        self._host_entries: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)

        # Coherence: entry_key -> set of hosts with cached copies
        self._sharers: Dict[Tuple[int, int], Set[int]] = defaultdict(set)

        # Statistics
        self.stats = {
            "admissions": 0,
            "evictions": 0,
            "hits": 0,
            "misses": 0,
            "promotions": 0,
            "cross_host_hits": 0,
            "invalidations_sent": 0,
        }

        # Dynamic capacity
        self._access_since_rebalance = 0

    @property
    def utilization(self) -> float:
        """Current pool utilization."""
        return len(self._entries) / max(1, self.capacity)

    @property
    def size(self) -> int:
        """Current number of entries in pool."""
        return len(self._entries)

    def get_host_usage(self, host_id: int) -> int:
        """Get number of entries host_id has in the pool."""
        return len(self._host_entries.get(host_id, set()))

    def get_host_share(self, host_id: int) -> float:
        """Get host's fraction of pool capacity."""
        if self.capacity == 0:
            return 0.0
        return self.get_host_usage(host_id) / self.capacity

    def can_admit(self, host_id: int) -> bool:
        """Check if host can admit another entry (capacity + quota)."""
        if not self.config.enabled:
            return False
        if len(self._entries) >= self.capacity:
            return False
        # Per-host max share check (multi-GPU fairness)
        if (self.config.num_hosts > 1
                and self.get_host_share(host_id) >= self.config.per_host_max_share):
            return False
        return True

    def admit(
        self,
        entry: CompressedBlockEntry,
        host_id: int = 0,
    ) -> bool:
        """Admit a compressed entry to the CXL pool.

        Enforces per-host quota bounds in multi-GPU mode.
        Returns True if admitted, False if pool is full and victim
        selection failed.
        """
        key = (entry.sequence_id, entry.block_id)

        # If already in pool, update in place
        if key in self._entries:
            self._entries[key] = entry
            return True

        # Check capacity — evict if needed
        if len(self._entries) >= self.capacity:
            if not self._evict_one(host_id):
                return False

        # Check per-host quota (after potential eviction freed space)
        if (self.config.num_hosts > 1
                and self.get_host_share(host_id) >= self.config.per_host_max_share):
            return False

        self._entries[key] = entry
        self._host_entries[host_id].add(key)
        self._sharers[key].add(host_id)
        entry.owner_host = host_id

        self.stats["admissions"] += 1
        return True

    def lookup(
        self,
        sequence_id: int,
        block_id: int,
        accessor_host: int = 0,
    ) -> Optional[CompressedBlockEntry]:
        """Look up an entry in the CXL pool.

        Returns the compressed entry if found, None otherwise.
        Tracks cross-host access statistics.
        """
        key = (sequence_id, block_id)
        entry = self._entries.get(key)

        self._access_since_rebalance += 1

        if entry is None:
            self.stats["misses"] += 1
            return None

        self.stats["hits"] += 1
        entry.cxl_access_count += 1

        # Track cross-host sharing
        if accessor_host != entry.owner_host:
            self.stats["cross_host_hits"] += 1
            if len(self._sharers[key]) < self.config.max_sharers_per_entry:
                self._sharers[key].add(accessor_host)
                entry.sharer_hosts.add(accessor_host)

        return entry

    def remove(self, sequence_id: int, block_id: int) -> Optional[CompressedBlockEntry]:
        """Remove an entry from the pool (for promotion back to BRAM)."""
        key = (sequence_id, block_id)
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._host_entries[entry.owner_host].discard(key)
            self._sharers.pop(key, None)
            self.stats["promotions"] += 1
        return entry

    def _evict_one(self, requesting_host: int) -> bool:
        """Select and evict one entry from the pool.

        Uses score + access recency for victim selection.
        Penalizes shared entries (more costly to evict).
        Prefers evicting entries from over-quota hosts.
        """
        if not self._entries:
            return False

        best_victim_key = None
        best_victim_score = float("inf")

        for key, entry in self._entries.items():
            # Base eviction score: lower = better victim
            eviction_score = entry.score

            # Penalty for shared entries (harder to invalidate)
            num_sharers = len(self._sharers.get(key, set()))
            if num_sharers > 1:
                penalty = self.config.shared_entry_penalty * num_sharers
                eviction_score *= (1.0 + penalty)

            # Boost for recently accessed entries (don't evict)
            if entry.cxl_access_count > 0:
                eviction_score *= (1.0 + 0.1 * min(entry.cxl_access_count, 10))

            # Prefer evicting from over-quota hosts (multi-GPU fairness)
            if self.config.num_hosts > 1:
                owner_share = self.get_host_share(entry.owner_host)
                if owner_share > self.config.per_host_max_share * 0.9:
                    eviction_score *= 0.7  # Make it easier to evict

            if eviction_score < best_victim_score:
                best_victim_score = eviction_score
                best_victim_key = key

        if best_victim_key is not None:
            victim = self._entries.pop(best_victim_key)
            self._host_entries[victim.owner_host].discard(best_victim_key)

            # Send invalidations to sharers
            sharers = self._sharers.pop(best_victim_key, set())
            if len(sharers) > 1:
                batches = math.ceil(len(sharers) / self.config.invalidation_batch_size)
                self.stats["invalidations_sent"] += len(sharers) - 1

            self.stats["evictions"] += 1
            return True

        return False

    def get_host_entries(self, host_id: int) -> Set[Tuple[int, int]]:
        """Get all entry keys owned by a host."""
        return self._host_entries.get(host_id, set()).copy()

    def get_stats(self) -> Dict:
        """Get pool statistics."""
        host_usage = {
            h: len(entries) for h, entries in self._host_entries.items()
            if entries
        }
        return {
            **self.stats,
            "size": len(self._entries),
            "capacity": self.capacity,
            "utilization": self.utilization,
            "num_shared_entries": sum(
                1 for s in self._sharers.values() if len(s) > 1
            ),
            "host_usage": host_usage,
        }


# ---------------------------------------------------------------------------
# Tiered Sequence State
# ---------------------------------------------------------------------------

class TieredSequenceState:
    """Wraps SequenceState with tier-aware promotion/demotion.

    Tracks which blocks are in BRAM vs CXL and manages movement
    between tiers based on access patterns.
    """

    def __init__(
        self,
        sequence_state: SequenceState,
        sequence_id: int,
        config: TieredPCAMConfig,
        cxl_pool: CXLEdgePool,
        host_id: int = 0,
    ):
        self.seq = sequence_state
        self.sequence_id = sequence_id
        self.config = config
        self.cxl_pool = cxl_pool
        self.host_id = host_id

        # Track which blocks are in which tier
        self._block_tier: Dict[int, TierType] = {}  # block_id -> tier

        # Demotion tracking
        self._last_demotion_step: int = 0
        self._demotions: int = 0
        self._promotions: int = 0

        # TQ edge profile compressor (lazy init)
        self._profile_compressor: Optional["EdgeProfileCompressor"] = None
        if config.tq.enable_profile_compression:
            from .tq_edge_compressor import EdgeProfileCompressor
            self._profile_compressor = EdgeProfileCompressor(
                profile_dim=config.tq.profile_dim,
                angle_bits=config.tq.profile_angle_bits,
                enable_qjl=config.tq.profile_enable_qjl,
                seed=config.tq.profile_seed,
            )

    @property
    def bram_count(self) -> int:
        """Number of blocks currently in BRAM."""
        return len(self.seq.block_scores)

    def should_demote(self) -> bool:
        """Check if BRAM is full enough to trigger demotion."""
        return self.bram_count >= self.config.bram_capacity

    def demote_cold_blocks(self, current_step: int, count: int = 64) -> int:
        """Demote lowest-scoring idle blocks from BRAM to CXL.

        Args:
            current_step: Current simulation step
            count: Number of blocks to demote

        Returns:
            Number of blocks successfully demoted
        """
        if not self.config.cxl.enabled:
            return 0

        policy = self.config.policy

        # Find demotion candidates: low score + idle
        candidates = []
        for bs in self.seq.block_scores.values():
            # Skip protected blocks
            if bs.block_id in self.seq.protected_blocks:
                continue

            idle_steps = current_step - bs.last_access_step
            if idle_steps < policy.demotion_min_idle_steps:
                continue

            candidates.append((bs.score, bs.block_id))

        if not candidates:
            return 0

        # Sort by score ascending (lowest first)
        candidates.sort()

        # Demote bottom N
        demoted = 0
        cutoff = int(len(self.seq.block_scores) * policy.demotion_score_percentile)
        to_demote = min(count, cutoff, len(candidates))

        # Defer BRAM removal so edges remain available for profile building
        blocks_to_remove: List[int] = []

        for i in range(to_demote):
            score, block_id = candidates[i]
            bs = self.seq.block_scores.get(block_id)
            if bs is None:
                continue

            # Check minimum score for CXL admission
            if bs.score < self.config.tq.min_score_for_cxl:
                # Too low even for CXL — just evict
                blocks_to_remove.append(block_id)
                self._block_tier[block_id] = TierType.EVICTED
                continue

            # Compress and admit to CXL pool (with TQ profile if enabled)
            max_query = max(
                (q for (q, _) in self.seq.attention_edges), default=0,
            )
            compressed = compress_block_score(
                bs=bs,
                sequence_id=self.sequence_id,
                edges=self.seq.attention_edges,
                config=self.config.tq,
                host_id=self.host_id,
                profile_compressor=self._profile_compressor,
                max_query_block=max_query,
            )
            compressed.demotion_step = current_step

            if self.cxl_pool.admit(compressed, self.host_id):
                blocks_to_remove.append(block_id)
                self._block_tier[block_id] = TierType.CXL_POOL
                demoted += 1
            else:
                break  # Pool is full and can't evict

        # Now remove all demoted/evicted blocks from BRAM
        for block_id in blocks_to_remove:
            self._remove_from_bram(block_id)

        self._demotions += demoted
        self._last_demotion_step = current_step
        return demoted

    def try_promote(self, block_id: int, current_step: int) -> Optional[BlockScore]:
        """Try to promote a block from CXL back to BRAM.

        Called when a CXL-tier block is accessed during ATTEND.

        Returns the promoted BlockScore if successful, None otherwise.
        """
        policy = self.config.policy

        entry = self.cxl_pool.lookup(self.sequence_id, block_id, self.host_id)
        if entry is None:
            return None

        # Check promotion criteria
        if entry.cxl_access_count < policy.promotion_min_access_count:
            return None
        if entry.score < policy.promotion_min_score:
            return None

        # Remove from CXL and decompress
        removed = self.cxl_pool.remove(self.sequence_id, block_id)
        if removed is None:
            return None

        # Decompress back to full BlockScore
        bs = removed.to_block_score()
        bs.last_access_step = current_step

        # Re-insert into BRAM
        self.seq.block_scores[block_id] = bs
        self._block_tier[block_id] = TierType.BRAM
        self._promotions += 1

        # If BRAM is now over capacity, trigger demotion
        if self.should_demote():
            self.demote_cold_blocks(current_step, count=32)

        return bs

    def get_cxl_candidates(
        self,
        query_block_id: int,
        k: int,
        current_step: int,
    ) -> List[Tuple[int, float]]:
        """Get candidate blocks from CXL tier for ATTEND augmentation.

        Scans the CXL pool for blocks belonging to this sequence
        that might be relevant to the current query. When TQ-compressed
        profiles are available, uses query-conditioned scoring for
        better relevance estimation.

        Returns list of (block_id, score) from CXL tier.
        """
        if not self.config.cxl.enabled:
            return []

        # Compute query bucket for TQ profile scoring
        query_bucket = None
        if self._profile_compressor is not None:
            max_query = max(
                (q for (q, _) in self.seq.attention_edges), default=0
            ) if self.seq.attention_edges else query_block_id
            bucket_size = max(
                1, (max_query + 1 + self._profile_compressor.profile_dim - 1)
                // self._profile_compressor.profile_dim,
            )
            query_bucket = min(
                query_block_id // bucket_size,
                self._profile_compressor.profile_dim - 1,
            )
            # Also compute nearby buckets for broader relevance
            nearby_buckets = [
                b for b in range(
                    max(0, query_bucket - 1),
                    min(self._profile_compressor.profile_dim, query_bucket + 2),
                )
            ]

        cxl_candidates = []

        # Check CXL entries for this sequence
        for (seq_id, block_id), entry in self.cxl_pool._entries.items():
            if seq_id != self.sequence_id:
                continue

            # Base score with recency decay from CXL
            base_score = entry.score
            idle_in_cxl = current_step - entry.last_access_step
            decay = 0.99 ** (idle_in_cxl / 100.0)
            effective_score = base_score * decay

            # TQ profile-conditioned scoring: use compressed profile
            # to estimate relevance for the current query position
            if (entry.has_profile
                    and self._profile_compressor is not None
                    and query_bucket is not None):
                profile_relevance = (
                    self._profile_compressor.estimate_total_relevance(
                        entry.compressed_profile, nearby_buckets,
                    )
                )
                # Blend profile relevance with scalar score
                # Profile provides query-specific signal; scalar score
                # provides aggregate importance. Weight profile higher
                # when it has strong signal.
                if profile_relevance > 0:
                    effective_score = (
                        0.4 * effective_score + 0.6 * profile_relevance
                    )

            # Boost for cross-host shared entries (validated by multiple GPUs)
            if len(entry.sharer_hosts) > 1:
                effective_score *= 1.0 + 0.1 * len(entry.sharer_hosts)

            cxl_candidates.append((block_id, effective_score))

        # Return top-k from CXL
        cxl_candidates.sort(key=lambda x: -x[1])
        return cxl_candidates[:k]

    def _remove_from_bram(self, block_id: int) -> None:
        """Remove a block from BRAM tier."""
        self.seq.block_scores.pop(block_id, None)
        # Remove associated edges
        edges_to_remove = [
            key for key in self.seq.attention_edges
            if key[0] == block_id or key[1] == block_id
        ]
        for key in edges_to_remove:
            del self.seq.attention_edges[key]

    def get_tier(self, block_id: int) -> TierType:
        """Get which tier a block is in."""
        if block_id in self.seq.block_scores:
            return TierType.BRAM
        return self._block_tier.get(block_id, TierType.EVICTED)

    def get_stats(self) -> Dict:
        """Get tiered sequence statistics."""
        bram_blocks = len(self.seq.block_scores)
        cxl_blocks = sum(
            1 for t in self._block_tier.values() if t == TierType.CXL_POOL
        )
        evicted_blocks = sum(
            1 for t in self._block_tier.values() if t == TierType.EVICTED
        )

        stats = {
            "bram_blocks": bram_blocks,
            "cxl_blocks": cxl_blocks,
            "evicted_blocks": evicted_blocks,
            "total_demotions": self._demotions,
            "total_promotions": self._promotions,
        }

        if self._profile_compressor is not None:
            stats["profile_compressor"] = self._profile_compressor.get_stats()

        return stats


# ---------------------------------------------------------------------------
# Tiered PCAM Interface
# ---------------------------------------------------------------------------

class TieredPCAMInterface(PCAMInterface):
    """PCAM interface with TQ-compressed CXL overflow and multi-GPU sharing.

    Extends the base SoftwarePCAMInterface with:
    1. Two-tier storage: hot edges in BRAM, warm edges TQ-compressed in CXL
    2. Automatic demotion of cold edges to CXL when BRAM fills up
    3. Promotion of CXL edges back to BRAM on access
    4. Multi-GPU shared edge pool via CXL 3.0 coherence
    5. ATTEND augmentation: merges BRAM + CXL candidates

    Usage:
        config = TieredPCAMConfig.single_gpu()
        pcam = TieredPCAMInterface(config)
        pcam.allocate_sequence(0, 4096)

        # Use exactly like SoftwarePCAMInterface
        candidates, latency, conflicts = pcam.attend(query_block, k=256)
    """

    def __init__(
        self,
        config: Optional[TieredPCAMConfig] = None,
        host_id: int = 0,
    ):
        self.config = config or TieredPCAMConfig()
        self.host_id = host_id

        # Base PCAM state (BRAM tier)
        self.state = AttentionState(
            max_sequences=self.config.base.max_sequences,
            max_blocks_per_sequence=self.config.base.max_blocks_per_sequence,
            num_banks=self.config.base.banks.num_banks,
        )

        # CXL shared edge pool
        self.cxl_pool = CXLEdgePool(
            config=self.config.cxl,
            bram_capacity=self.config.bram_capacity,
        )

        # Per-sequence tiered state
        self._tiered_sequences: Dict[int, TieredSequenceState] = {}

        self._step = 0

        # Latency tracking
        self._total_cxl_latency_ns = 0.0
        self._cxl_attend_count = 0

    def attend(
        self,
        query_block_id: int,
        k: int = 256,
        sequence_id: int = 0,
        structural_hints: Optional[Dict[int, int]] = None,
    ) -> Tuple[List[Tuple[int, float]], float, int]:
        """Perform tiered ATTEND: merge BRAM + CXL candidates."""
        # Step 1: Standard BRAM ATTEND
        bram_candidates, bank_conflicts = self.state.attend(
            sequence_id=sequence_id,
            query_block_id=query_block_id,
            k=k,
            structural_hints=structural_hints,
        )

        bram_latency = self.config.base.calculate_attend_latency(
            num_candidates=k,
            bank_conflicts=bank_conflicts,
        )

        # Step 2: CXL tier augmentation (if enabled)
        tiered = self._tiered_sequences.get(sequence_id)
        cxl_latency = 0.0

        if tiered and self.config.cxl.enabled:
            # Get candidates from CXL pool
            cxl_k = max(16, k // 4)  # Use 25% of K budget for CXL
            cxl_candidates = tiered.get_cxl_candidates(
                query_block_id=query_block_id,
                k=cxl_k,
                current_step=self._step,
            )

            if cxl_candidates:
                # CXL access latency (parallel with BRAM, but adds to total)
                cxl_latency = self.config.cxl.access_latency_ns
                self._total_cxl_latency_ns += cxl_latency
                self._cxl_attend_count += 1

                # Merge BRAM + CXL candidates, keeping top-K overall
                bram_set = {bid for bid, _ in bram_candidates}
                merged = list(bram_candidates)

                for bid, score in cxl_candidates:
                    if bid not in bram_set:
                        merged.append((bid, score))

                        # Try to promote hot CXL entries back to BRAM
                        tiered.try_promote(bid, self._step)

                # Re-sort and trim to K
                merged.sort(key=lambda x: -x[1])
                bram_candidates = merged[:k]

        # Total latency: max(BRAM, CXL) since they run in parallel
        total_latency = max(bram_latency, cxl_latency) if cxl_latency > 0 else bram_latency

        return bram_candidates, total_latency, bank_conflicts

    def update(
        self,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        sequence_id: int = 0,
    ) -> Tuple[bool, float]:
        """Perform UPDATE with automatic tier management."""
        # Check if block is in CXL tier — if so, update there
        tiered = self._tiered_sequences.get(sequence_id)
        if tiered:
            tier = tiered.get_tier(key_block_id)
            if tier == TierType.CXL_POOL:
                # Update the CXL entry's score
                entry = self.cxl_pool.lookup(
                    sequence_id, key_block_id, self.host_id
                )
                if entry:
                    # EMA update on compressed score
                    alpha = 0.3
                    new_score = alpha * weight + (1 - alpha) * entry.score
                    entry.score = new_score
                    entry.access_count = min(entry.access_count + 1, 255)
                    entry.last_access_step = self._step
                    entry.cxl_access_count += 1

                    # Auto-promote if accessed enough
                    tiered.try_promote(key_block_id, self._step)

                    latency = self.config.cxl.access_latency_ns
                    return True, latency

        # Standard BRAM update
        success = self.state.update(
            sequence_id=sequence_id,
            query_block_id=query_block_id,
            key_block_id=key_block_id,
            weight=weight,
            step=self._step,
        )

        latency = self.config.base.calculate_update_latency(coalesced_count=1)

        # Check if demotion is needed after BRAM update
        if tiered and tiered.should_demote():
            tiered.demote_cold_blocks(self._step, count=64)

        return success, latency

    def update_batch(
        self,
        sequence_id: int,
        block_ids: List[int],
        weights: List[float],
        query_block_id: Optional[int] = None,
    ) -> Tuple[int, float]:
        """Batch UPDATE with tier-aware routing."""
        count = 0
        total_latency = 0.0

        query_block = query_block_id if query_block_id is not None else self._step // 16

        for block_id, weight in zip(block_ids, weights):
            success, latency = self.update(
                query_block_id=query_block,
                key_block_id=block_id,
                weight=weight,
                sequence_id=sequence_id,
            )
            if success:
                count += 1
                total_latency += latency

        # Apply coalescing discount (4:1 ratio)
        coalesced_latency = total_latency / max(1, min(4, count))
        return count, coalesced_latency

    def get_block_scores(
        self,
        sequence_id: int,
        block_ids: List[int],
    ) -> Dict[int, float]:
        """Get block scores from both tiers."""
        result = self.state.get_block_scores(sequence_id, block_ids)

        # Check CXL for blocks not found in BRAM
        for block_id in block_ids:
            if block_id not in result or result[block_id] == 0.0:
                entry = self.cxl_pool.lookup(
                    sequence_id, block_id, self.host_id
                )
                if entry:
                    result[block_id] = entry.score

        return result

    def decay(
        self,
        rate: float = 0.99,
        sequence_id: Optional[int] = None,
    ) -> None:
        """Apply decay to both tiers."""
        # Decay BRAM tier
        self.state.decay(rate, sequence_id)

        # Decay CXL tier entries
        for key, entry in self.cxl_pool._entries.items():
            if sequence_id is not None and entry.sequence_id != sequence_id:
                continue
            decayed = entry.score * rate
            entry.score = decayed

    def allocate_sequence(
        self,
        sequence_id: int,
        max_blocks: int,
    ) -> bool:
        """Allocate sequence with tiered state tracking."""
        success = self.state.allocate_sequence(sequence_id, max_blocks)
        if success:
            seq = self.state.get_sequence(sequence_id)
            if seq:
                self._tiered_sequences[sequence_id] = TieredSequenceState(
                    sequence_state=seq,
                    sequence_id=sequence_id,
                    config=self.config,
                    cxl_pool=self.cxl_pool,
                    host_id=self.host_id,
                )
        return success

    def free_sequence(self, sequence_id: int) -> bool:
        """Free sequence from both tiers."""
        # Remove CXL entries for this sequence
        keys_to_remove = [
            (seq_id, block_id)
            for (seq_id, block_id) in list(self.cxl_pool._entries.keys())
            if seq_id == sequence_id
        ]
        for key in keys_to_remove:
            self.cxl_pool.remove(key[0], key[1])

        self._tiered_sequences.pop(sequence_id, None)
        return self.state.free_sequence(sequence_id)

    def get_stats(self) -> Dict:
        """Get comprehensive tiered statistics."""
        base_stats = self.state.get_stats()
        pool_stats = self.cxl_pool.get_stats()

        # Per-sequence tier stats
        tier_stats = {}
        for seq_id, tiered in self._tiered_sequences.items():
            tier_stats[seq_id] = tiered.get_stats()

        total_demotions = sum(t.get("total_demotions", 0) for t in tier_stats.values())
        total_promotions = sum(t.get("total_promotions", 0) for t in tier_stats.values())

        return {
            **base_stats,
            "cxl_pool": pool_stats,
            "tier_stats": tier_stats,
            "total_demotions": total_demotions,
            "total_promotions": total_promotions,
            "avg_cxl_latency_ns": (
                self._total_cxl_latency_ns / self._cxl_attend_count
                if self._cxl_attend_count > 0 else 0
            ),
            "config_summary": self.config.summary(),
        }

    def step(self) -> None:
        """Advance step counter."""
        self._step += 1
