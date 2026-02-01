"""
State management for PCAM simulator.

Tracks attention relationships, block scores, and bank states.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from enum import Enum
import heapq
import math


class WorkloadPattern(Enum):
    """Detected workload pattern for adaptive strategies."""
    UNKNOWN = "unknown"
    CHAT = "chat"           # Local attention, sequential
    LONG_CONTEXT = "long_context"  # Local + sparse distant
    RAG = "rag"             # Sparse semantic (unpredictable)
    CODE = "code"           # Local + consistent far dependencies


class GenerationPhase(Enum):
    """
    Generation phase for phase-based attention strategies.

    Long-context workloads exhibit distinct phases similar to "phase quad" LLM models:
    - EARLY: Context building, broad capture
    - MID: Selective attention, anchor maintenance
    - LATE: May revisit early context, anchor recall boost
    """
    EARLY = "early"     # 0-25% of generation
    MID = "mid"         # 25-75% of generation
    LATE = "late"       # 75-100% of generation


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
    """Per-sequence attention state with workload-adaptive strategies."""
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

    # Workload detection state
    detected_pattern: WorkloadPattern = WorkloadPattern.UNKNOWN
    _distant_attention_count: int = 0  # Attention to blocks >100 away
    _local_attention_count: int = 0    # Attention to blocks <50 away
    _consistent_distant_blocks: Set[int] = field(default_factory=set)  # Distant blocks hit by multiple queries
    _query_positions: List[int] = field(default_factory=list)  # Recent query positions
    _detection_window: int = 50  # Re-detect every N updates

    # Phase-based state for long-context (phase quad logic)
    current_phase: GenerationPhase = GenerationPhase.EARLY
    _max_query_seen: int = 0  # Max query block position seen
    _generation_start: int = 0  # Where generation started (after prefill)
    _anchor_blocks: Set[int] = field(default_factory=set)  # Blocks consistently attended in early phases

    def detect_workload(self) -> WorkloadPattern:
        """
        Detect workload pattern based on attention characteristics.

        Heuristics:
        - CHAT: Short context, mostly local attention
        - LONG_CONTEXT: Large context, sequential queries, local + distant attention
        - CODE: High distant attention + many consistent early blocks (imports)
        - RAG: Sparse semantic attention, queries to document chunks
        """
        if self.total_updates < 20:
            return WorkloadPattern.UNKNOWN

        # Calculate metrics
        total_attention = self._distant_attention_count + self._local_attention_count
        if total_attention == 0:
            return WorkloadPattern.UNKNOWN

        distant_ratio = self._distant_attention_count / total_attention
        local_ratio = self._local_attention_count / total_attention

        # Check for consistent early blocks (code imports pattern)
        # CODE has many early blocks (< 50) accessed by many different queries
        high_diversity_early = sum(
            1 for bs in self.block_scores.values()
            if len(bs.unique_query_sources) >= 5 and bs.block_id < 50
        )

        # Context size estimation
        max_block = max((bs.block_id for bs in self.block_scores.values()), default=0)
        min_block = min((bs.block_id for bs in self.block_scores.values()), default=0)

        # Check for sequential query progression (LONG_CONTEXT characteristic)
        # Look at unique query sources - are they spread across context?
        all_query_positions = set()
        for bs in self.block_scores.values():
            all_query_positions.update(bs.unique_query_sources)
        query_spread = max(all_query_positions, default=0) - min(all_query_positions, default=0)

        # Check if attention covers a wide range (not just sparse chunks)
        block_spread = max_block - min_block
        attended_blocks = len(self.block_scores)
        coverage_density = attended_blocks / max(1, block_spread) if block_spread > 0 else 1.0

        # Detection logic (order matters!)
        if max_block < 100 and local_ratio > 0.8:
            # Short context, almost all local -> CHAT
            return WorkloadPattern.CHAT

        if distant_ratio > 0.7 and high_diversity_early >= 30:
            # Very high distant + many consistent early blocks -> CODE (imports)
            return WorkloadPattern.CODE

        # LONG_CONTEXT: Large context, has both local AND distant attention
        # Key: coverage_density > 0.3 means blocks are spread out (not RAG-like sparse)
        # Also: local_ratio > 0.15 means there's meaningful local attention
        if max_block > 1000 and local_ratio > 0.15 and coverage_density > 0.1:
            return WorkloadPattern.LONG_CONTEXT

        if distant_ratio > 0.6 and coverage_density < 0.1:
            # High distant, sparse coverage -> RAG (scattered semantic)
            return WorkloadPattern.RAG

        if local_ratio >= 0.4:
            # Balanced or local-dominant -> LONG_CONTEXT
            return WorkloadPattern.LONG_CONTEXT

        return WorkloadPattern.LONG_CONTEXT  # Default fallback

    def detect_phase(self, query_block_id: int) -> GenerationPhase:
        """
        Detect current generation phase for phase-based strategies.

        Phase quad logic for long-context workloads:
        - EARLY (0-25%): Context building, broad capture, anchor identification
        - MID (25-75%): Selective attention, maintain established anchors
        - LATE (75-100%): May revisit early context, anchor recall boost

        Args:
            query_block_id: Current query block position

        Returns:
            Current GenerationPhase
        """
        # Track first query as generation start
        if self._generation_start == 0:
            self._generation_start = query_block_id

        # Update max query seen
        if query_block_id > self._max_query_seen:
            self._max_query_seen = query_block_id

        # Use attend count to determine phase (not position-based)
        # This is more robust for long-context where queries are sequential
        total_expected_queries = 100  # Reasonable estimate for typical workload

        # Use actual attend count as progress indicator
        progress = self.total_attends / total_expected_queries

        # Phase boundaries based on generation progress
        if progress < 0.25:
            return GenerationPhase.EARLY
        elif progress < 0.75:
            return GenerationPhase.MID
        else:
            return GenerationPhase.LATE

    def identify_anchors(self) -> None:
        """
        Identify anchor blocks during EARLY phase.

        Anchors are blocks that receive consistent attention from multiple
        different query positions - they represent structurally important
        context that should be retained throughout generation.
        """
        # Only identify anchors during EARLY phase
        if self.current_phase != GenerationPhase.EARLY:
            return

        # Blocks accessed by 3+ different queries are potential anchors
        for bs in self.block_scores.values():
            if len(bs.unique_query_sources) >= 3:
                self._anchor_blocks.add(bs.block_id)

    def get_top_k(
        self,
        k: int,
        query_block_id: Optional[int] = None,
        exclude: Optional[Set[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        Get top-K blocks by score with workload-adaptive strategies.

        Args:
            k: Number of blocks to return
            query_block_id: If provided, boost blocks with edges from this query
            exclude: Block IDs to exclude from results

        Returns:
            List of (block_id, score) tuples, sorted by score descending
        """
        exclude = exclude or set()

        # Update workload detection after sufficient data
        if self.total_updates >= 50 and self.detected_pattern == WorkloadPattern.UNKNOWN:
            self.detected_pattern = self.detect_workload()
        elif self.total_updates % self._detection_window == 0 and self.total_updates >= 100:
            # Re-detect periodically after initial detection
            self.detected_pattern = self.detect_workload()

        # Workload-adaptive parameters
        pattern = self.detected_pattern
        anchor_boost_enabled = False  # Default, set per-pattern
        if pattern == WorkloadPattern.CHAT:
            recency_window = 24
            recency_strength = 0.6
            query_window = 12
            diversity_boost_enabled = False
            global_importance_enabled = False
        elif pattern == WorkloadPattern.LONG_CONTEXT:
            # Phase-based logic for long-context (phase quad approach)
            if query_block_id is not None:
                self.current_phase = self.detect_phase(query_block_id)
                self.identify_anchors()  # Build anchor set during EARLY phase

            phase = self.current_phase
            if phase == GenerationPhase.EARLY:
                # EARLY: Broad capture, anchor identification
                recency_window = 64  # Wide window for context building
                recency_strength = 0.4  # Less recency bias, more diverse capture
                query_window = 30  # Broad query context
                anchor_boost_enabled = False  # Still building anchors
            elif phase == GenerationPhase.MID:
                # MID: Selective attention, maintain established anchors
                recency_window = 48
                recency_strength = 0.5
                query_window = 20
                anchor_boost_enabled = True  # Use identified anchors
            else:  # LATE
                # LATE: Anchor recall boost, may revisit early context
                recency_window = 32  # Narrower local focus
                recency_strength = 0.4  # Less recency, more anchor recall
                query_window = 16
                anchor_boost_enabled = True  # Strong anchor recall

            diversity_boost_enabled = False
            global_importance_enabled = False
        elif pattern == WorkloadPattern.CODE:
            recency_window = 32
            recency_strength = 0.4
            query_window = 16
            diversity_boost_enabled = True  # Enable for imports
            global_importance_enabled = False
        elif pattern == WorkloadPattern.RAG:
            recency_window = 16
            recency_strength = 0.3
            query_window = 8
            diversity_boost_enabled = False
            global_importance_enabled = True  # Enable for RAG
        else:  # UNKNOWN - use balanced defaults
            recency_window = 32
            recency_strength = 0.5
            query_window = 16
            diversity_boost_enabled = False
            global_importance_enabled = False

        # Start with base block scores
        candidates = {}
        for bs in self.block_scores.values():
            if bs.block_id not in exclude:
                candidates[bs.block_id] = bs.score

        # Add query-conditioned scores from attention edges
        if query_block_id is not None:
            for (src_query, dst_key), weight in self.attention_edges.items():
                if dst_key in exclude:
                    continue
                query_distance = abs(src_query - query_block_id)
                if query_distance <= query_window:
                    locality_boost = 1.0 / (1.0 + query_distance * 0.1)
                    edge_score = weight * locality_boost
                    candidates[dst_key] = candidates.get(dst_key, 0) + edge_score

        # Always include protected blocks (sinks/anchors) with minimum score
        for protected in self.protected_blocks:
            if protected not in exclude:
                candidates[protected] = max(candidates.get(protected, 0), 0.1)

        # Add recency bonus for recent blocks (adaptive strength)
        if query_block_id is not None:
            for block_id in range(max(0, query_block_id - recency_window), query_block_id + 1):
                if block_id not in exclude:
                    recency_boost = recency_strength * (1.0 - (query_block_id - block_id) / recency_window)
                    candidates[block_id] = candidates.get(block_id, 0) + recency_boost

        # Diversity boost for CODE workloads (imports attended by many queries)
        if diversity_boost_enabled and query_block_id is not None:
            for bs in self.block_scores.values():
                if bs.block_id in exclude:
                    continue
                # Only boost distant blocks with high query diversity
                distance = abs(bs.block_id - query_block_id)
                if distance > 50:
                    query_diversity = len(bs.unique_query_sources)
                    if query_diversity >= 3:
                        diversity_boost = math.log1p(query_diversity) * 0.2
                        candidates[bs.block_id] = candidates.get(bs.block_id, 0) + diversity_boost

        # Global importance boost for RAG workloads
        # Helps identify consistently important blocks across queries
        if global_importance_enabled:
            for bs in self.block_scores.values():
                if bs.block_id in exclude:
                    continue
                # Boost blocks that have high global importance
                if bs.global_importance > 0.1:
                    candidates[bs.block_id] = candidates.get(bs.block_id, 0) + bs.global_importance * 0.3

        # Anchor boost for LONG_CONTEXT phase logic
        # In MID/LATE phases, boost anchors identified during EARLY phase
        if anchor_boost_enabled and self._anchor_blocks:
            phase = self.current_phase
            # Stronger boost in LATE phase (anchor recall)
            anchor_strength = 0.4 if phase == GenerationPhase.LATE else 0.25

            for anchor_id in self._anchor_blocks:
                if anchor_id in exclude:
                    continue
                # Boost anchors that have strong historical importance
                if anchor_id in self.block_scores:
                    bs = self.block_scores[anchor_id]
                    # Scale boost by how many queries attended this anchor
                    diversity_factor = min(1.0, len(bs.unique_query_sources) / 10.0)
                    anchor_boost = anchor_strength * diversity_factor
                    candidates[anchor_id] = candidates.get(anchor_id, 0) + anchor_boost

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
        """Update attention edge weight and workload detection metrics."""
        edge_key = (query_block, key_block)
        self.attention_edges[edge_key] = weight

        # Track attention distance for workload detection
        distance = abs(query_block - key_block)
        if distance > 100:
            self._distant_attention_count += 1
        elif distance < 50:
            self._local_attention_count += 1

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
