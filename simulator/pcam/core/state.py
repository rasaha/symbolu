"""
State management for PCAM simulator.

Tracks attention relationships, block scores, and bank states.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import heapq
import math


@dataclass
class BlockScore:
    """Score for a single KV block."""
    block_id: int
    score: float
    last_access_step: int = 0
    access_count: int = 0
    # Track unique query sources for global importance
    unique_query_sources: Set[int] = field(default_factory=set)
    # Cumulative attention weight
    cumulative_weight: float = 0.0

    def __lt__(self, other: "BlockScore") -> bool:
        """For heap operations - lower score = eviction candidate."""
        return self.score < other.score

    @property
    def global_importance(self) -> float:
        """
        Global importance based on how many different queries attend to this block.
        Blocks attended by many queries are likely important anchors.
        """
        if not self.unique_query_sources:
            return 0.0
        diversity = len(self.unique_query_sources)
        avg_weight = self.cumulative_weight / max(1, self.access_count)
        return math.log1p(diversity) * avg_weight


@dataclass
class BankState:
    """State of a single memory bank."""
    bank_id: int
    entries: Dict[int, float] = field(default_factory=dict)  # entry_id -> weight
    queue_depth: int = 0
    total_accesses: int = 0
    total_conflicts: int = 0

    @property
    def utilization(self) -> float:
        """Current utilization as fraction."""
        return len(self.entries) / 16384 if self.entries else 0.0


@dataclass
class SequenceState:
    """Per-sequence attention state."""
    sequence_id: int
    max_blocks: int

    # Block scores: block_id -> BlockScore
    block_scores: Dict[int, BlockScore] = field(default_factory=dict)

    # Attention graph: (query_block, key_block) -> weight
    attention_edges: Dict[Tuple[int, int], float] = field(default_factory=dict)

    # Protected blocks (sinks, anchors)
    protected_blocks: Set[int] = field(default_factory=set)

    # Statistics
    total_attends: int = 0
    total_updates: int = 0
    current_step: int = 0

    def get_top_k(
        self,
        k: int,
        query_block_id: Optional[int] = None,
        exclude: Optional[Set[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        Get top-K blocks by score, optionally conditioned on query.

        Args:
            k: Number of blocks to return
            query_block_id: If provided, boost blocks with edges from this query
            exclude: Block IDs to exclude from results

        Returns:
            List of (block_id, score) tuples, sorted by score descending
        """
        exclude = exclude or set()

        # Start with base block scores
        candidates = {}
        for bs in self.block_scores.values():
            if bs.block_id not in exclude:
                candidates[bs.block_id] = bs.score

        # Add query-conditioned scores from attention edges
        if query_block_id is not None:
            # Find blocks that have been attended to from nearby queries
            query_window = 16  # Look at queries within this range
            for (src_query, dst_key), weight in self.attention_edges.items():
                if dst_key in exclude:
                    continue
                # Boost blocks that nearby queries attended to
                query_distance = abs(src_query - query_block_id)
                if query_distance <= query_window:
                    locality_boost = 1.0 / (1.0 + query_distance * 0.1)
                    edge_score = weight * locality_boost
                    candidates[dst_key] = candidates.get(dst_key, 0) + edge_score

        # Always include protected blocks (sinks/anchors) with minimum score
        for protected in self.protected_blocks:
            if protected not in exclude:
                candidates[protected] = max(candidates.get(protected, 0), 0.1)

        # Add recency bonus for recent blocks
        if query_block_id is not None:
            recency_window = 32  # Recent blocks to boost
            for block_id in range(max(0, query_block_id - recency_window), query_block_id + 1):
                if block_id not in exclude:
                    recency_boost = 0.5 * (1.0 - (query_block_id - block_id) / recency_window)
                    candidates[block_id] = candidates.get(block_id, 0) + recency_boost

        # Use heapq for efficient top-K
        scored = [(score, block_id) for block_id, score in candidates.items()]
        top_k = heapq.nlargest(k, scored)

        return [(block_id, score) for score, block_id in top_k]

    def update_edge(
        self,
        query_block: int,
        key_block: int,
        weight: float,
        step: int,
    ) -> None:
        """Update attention edge weight."""
        edge_key = (query_block, key_block)
        self.attention_edges[edge_key] = weight

        # Update block score using improved scoring
        if key_block not in self.block_scores:
            self.block_scores[key_block] = BlockScore(
                block_id=key_block,
                score=weight,
                last_access_step=step,
                access_count=1,
                unique_query_sources={query_block},
                cumulative_weight=weight,
            )
        else:
            bs = self.block_scores[key_block]
            # Track query sources for global importance
            bs.unique_query_sources.add(query_block)
            bs.cumulative_weight += weight

            # Adaptive EMA: more weight to new observations for infrequent blocks
            # This helps sparse patterns (long-context, RAG, code) learn faster
            base_alpha = 0.2
            frequency_boost = min(0.5, bs.access_count * 0.05)  # More frequent = more stable
            alpha = base_alpha + (0.5 - frequency_boost)  # Range: 0.2-0.7

            # Combine new weight with existing score
            bs.score = alpha * weight + (1 - alpha) * bs.score

            # Add frequency boost for consistently accessed blocks
            frequency_boost = math.log1p(bs.access_count) * 0.01
            bs.score = bs.score + frequency_boost

            bs.last_access_step = step
            bs.access_count += 1

        # Auto-detect sink blocks: early blocks accessed by many different queries
        # Sinks are the first few blocks that receive attention from distant queries
        sink_threshold = 4  # First N blocks can become sinks
        if key_block < sink_threshold:
            bs = self.block_scores[key_block]
            # If block is accessed frequently and from distant queries, mark as sink
            if bs.access_count >= 5 and (query_block - key_block) > 10:
                self.protected_blocks.add(key_block)

    def apply_decay(self, decay_rate: float) -> None:
        """Apply decay to all scores."""
        for bs in self.block_scores.values():
            bs.score *= decay_rate

        for edge_key in self.attention_edges:
            self.attention_edges[edge_key] *= decay_rate


class AttentionState:
    """
    Global attention state manager.

    Manages multiple sequences with independent attention graphs,
    simulating the PCAM chip's state storage.
    """

    def __init__(
        self,
        max_sequences: int = 64,
        max_blocks_per_sequence: int = 4096,
        num_banks: int = 64,
    ):
        self.max_sequences = max_sequences
        self.max_blocks_per_sequence = max_blocks_per_sequence
        self.num_banks = num_banks

        # Per-sequence state
        self.sequences: Dict[int, SequenceState] = {}

        # Bank states for contention modeling
        self.banks: List[BankState] = [
            BankState(bank_id=i) for i in range(num_banks)
        ]

        # Global statistics
        self.total_entries = 0
        self.total_bank_conflicts = 0

    def allocate_sequence(self, sequence_id: int, max_blocks: int) -> bool:
        """Allocate state for a new sequence."""
        if len(self.sequences) >= self.max_sequences:
            return False

        self.sequences[sequence_id] = SequenceState(
            sequence_id=sequence_id,
            max_blocks=min(max_blocks, self.max_blocks_per_sequence),
        )
        return True

    def free_sequence(self, sequence_id: int) -> bool:
        """Free sequence state."""
        if sequence_id in self.sequences:
            del self.sequences[sequence_id]
            return True
        return False

    def get_sequence(self, sequence_id: int) -> Optional[SequenceState]:
        """Get sequence state."""
        return self.sequences.get(sequence_id)

    def attend(
        self,
        sequence_id: int,
        query_block_id: int,
        k: int = 64,
    ) -> Tuple[List[Tuple[int, float]], int]:
        """
        Perform ATTEND operation.

        Args:
            sequence_id: Sequence to query
            query_block_id: Current query block
            k: Number of candidates to return

        Returns:
            Tuple of (candidates, bank_conflicts)
            where candidates is list of (block_id, score)
        """
        seq = self.sequences.get(sequence_id)
        if seq is None:
            return [], 0

        seq.total_attends += 1

        # Calculate bank conflicts
        bank_conflicts = self._calculate_bank_conflicts(sequence_id, k)

        # Get top-K candidates, conditioned on query block
        candidates = seq.get_top_k(k, query_block_id=query_block_id)

        return candidates, bank_conflicts

    def update(
        self,
        sequence_id: int,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        step: int,
    ) -> bool:
        """
        Perform UPDATE operation.

        Args:
            sequence_id: Sequence to update
            query_block_id: Query block ID
            key_block_id: Key block ID
            weight: Attention weight
            step: Current step number

        Returns:
            True if successful
        """
        seq = self.sequences.get(sequence_id)
        if seq is None:
            return False

        seq.update_edge(query_block_id, key_block_id, weight, step)
        seq.total_updates += 1
        seq.current_step = step

        return True

    def update_batch(
        self,
        sequence_id: int,
        block_ids: List[int],
        weights: List[float],
        step: int,
    ) -> int:
        """
        Batch UPDATE operation.

        Returns number of successful updates.
        """
        seq = self.sequences.get(sequence_id)
        if seq is None:
            return 0

        # Assume updates are from current query block
        query_block = step // 16  # Rough approximation

        count = 0
        for block_id, weight in zip(block_ids, weights):
            if self.update(sequence_id, query_block, block_id, weight, step):
                count += 1

        return count

    def decay(
        self,
        decay_rate: float,
        sequence_id: Optional[int] = None,
    ) -> None:
        """Apply decay to scores."""
        if sequence_id is not None:
            seq = self.sequences.get(sequence_id)
            if seq:
                seq.apply_decay(decay_rate)
        else:
            for seq in self.sequences.values():
                seq.apply_decay(decay_rate)

    def get_block_scores(
        self,
        sequence_id: int,
        block_ids: List[int],
    ) -> Dict[int, float]:
        """Get current scores for specified blocks."""
        seq = self.sequences.get(sequence_id)
        if seq is None:
            return {}

        return {
            block_id: seq.block_scores.get(block_id, BlockScore(block_id, 0.0)).score
            for block_id in block_ids
        }

    def _calculate_bank_conflicts(self, sequence_id: int, k: int) -> int:
        """
        Calculate expected bank conflicts for an ATTEND operation.

        Uses hash-based bank assignment to model realistic conflicts.
        """
        if not self.sequences.get(sequence_id):
            return 0

        # Model bank accesses
        bank_access_counts = defaultdict(int)

        seq = self.sequences[sequence_id]
        for block_id in list(seq.block_scores.keys())[:k * 2]:  # Sample more than K
            bank_id = block_id % self.num_banks
            bank_access_counts[bank_id] += 1

        # Conflicts occur when multiple accesses hit same bank
        conflicts = sum(max(0, count - 1) for count in bank_access_counts.values())
        self.total_bank_conflicts += conflicts

        return conflicts

    def get_stats(self) -> Dict:
        """Get global statistics."""
        total_attends = sum(s.total_attends for s in self.sequences.values())
        total_updates = sum(s.total_updates for s in self.sequences.values())
        total_edges = sum(len(s.attention_edges) for s in self.sequences.values())

        return {
            "num_sequences": len(self.sequences),
            "total_attends": total_attends,
            "total_updates": total_updates,
            "total_edges": total_edges,
            "total_bank_conflicts": self.total_bank_conflicts,
            "avg_conflicts_per_attend": (
                self.total_bank_conflicts / total_attends if total_attends > 0 else 0
            ),
        }
