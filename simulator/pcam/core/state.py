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


@dataclass
class Section:
    """
    Coarse-level section for soft hierarchical prior.

    CRITICAL: Hierarchy is a PRIOR, not a FILTER.
    Sections provide a scoring boost, not eligibility gating.

    Sections group blocks into regions (16-32 blocks per section).
    High-scoring sections boost their member blocks' scores.
    But blocks outside top sections can STILL be selected.
    """
    section_id: int
    start_block: int
    end_block: int  # Exclusive

    # Section-level attention statistics
    total_attention: float = 0.0
    access_count: int = 0
    unique_queries: Set[int] = field(default_factory=set)

    @property
    def score(self) -> float:
        """Section importance score based on attention history."""
        if self.access_count == 0:
            return 0.0
        avg_attention = self.total_attention / self.access_count
        diversity_factor = math.log1p(len(self.unique_queries))
        return avg_attention * diversity_factor

    @property
    def block_count(self) -> int:
        return self.end_block - self.start_block


@dataclass
class PhaseCluster:
    """
    Cluster of co-activated blocks for phase-based candidate expansion.

    Blocks that tend to be attended together across queries form coherent
    "phase clusters" - useful for Long-Context and RAG where individual
    block prediction fails but cluster prediction succeeds.
    """
    cluster_id: int
    blocks: Set[int] = field(default_factory=set)
    centroid: float = 0.0  # Average block position
    last_activation_step: int = 0
    activation_count: int = 0
    total_weight: float = 0.0

    def update_centroid(self) -> None:
        """Recalculate centroid from current blocks."""
        if self.blocks:
            self.centroid = sum(self.blocks) / len(self.blocks)
        else:
            self.centroid = 0.0

    @property
    def coherence_score(self) -> float:
        """How coherent/useful is this cluster."""
        if not self.blocks or self.activation_count == 0:
            return 0.0
        # More activations + reasonable size = better cluster
        size_factor = min(1.0, len(self.blocks) / 8.0)  # Ideal ~8 blocks
        activation_factor = math.log1p(self.activation_count) * 0.5
        return size_factor * activation_factor


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

    # Phase coherence state for cluster-based candidate expansion
    # Tracks which blocks are attended together (co-activation)
    _co_activation: Dict[Tuple[int, int], int] = field(default_factory=dict)  # (block_a, block_b) -> count
    _phase_clusters: Dict[int, PhaseCluster] = field(default_factory=dict)  # cluster_id -> PhaseCluster
    _block_to_cluster: Dict[int, int] = field(default_factory=dict)  # block_id -> cluster_id
    _next_cluster_id: int = 0
    _last_query_blocks: Set[int] = field(default_factory=set)  # Blocks from last query for co-activation
    _phase_mode_enabled: bool = False  # Whether to use cluster-based selection
    _cluster_rebuild_interval: int = 25  # Rebuild clusters every N queries

    # Soft Hierarchical Prior: sections provide scoring boost, not eligibility filter
    _sections: Dict[int, Section] = field(default_factory=dict)  # section_id -> Section
    _section_size: int = 16  # Blocks per section
    _section_boost_alpha: float = 0.15  # Section boost coefficient (α < 1.0)

    def _get_or_create_section(self, block_id: int) -> Section:
        """Get or create section for a block."""
        section_id = block_id // self._section_size
        if section_id not in self._sections:
            start = section_id * self._section_size
            end = (section_id + 1) * self._section_size
            self._sections[section_id] = Section(
                section_id=section_id,
                start_block=start,
                end_block=end,
            )
        return self._sections[section_id]

    def _update_section_stats(self, query_block: int, key_block: int, weight: float) -> None:
        """Update section-level statistics when a block is accessed."""
        section = self._get_or_create_section(key_block)
        section.total_attention += weight
        section.access_count += 1
        section.unique_queries.add(query_block)

    def _get_section_boost(self, block_id: int) -> float:
        """
        Get soft hierarchical boost for a block based on its section.

        Returns a small additive bonus (not a gate) based on section importance.
        Blocks in high-attention sections get a boost, but blocks elsewhere
        are NOT excluded - they just don't get the bonus.
        """
        section_id = block_id // self._section_size
        if section_id not in self._sections:
            return 0.0
        section = self._sections[section_id]
        # Soft boost: α * section_score (α ≈ 0.15)
        return self._section_boost_alpha * section.score

    def detect_workload(self) -> WorkloadPattern:
        """
        Detect workload pattern based on attention characteristics.

        Heuristics:
        - CHAT: Short context, mostly local attention
        - LONG_CONTEXT: Large context, balanced or local attention
        - CODE: High distant attention + many consistent early blocks (imports)
        - RAG: High distant attention + scattered consistency (semantic)
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

        # Detection logic (order matters!)
        if max_block < 100 and local_ratio > 0.8:
            # Short context, almost all local -> CHAT
            return WorkloadPattern.CHAT

        if distant_ratio > 0.7 and high_diversity_early >= 30:
            # Very high distant + many consistent early blocks -> CODE (imports)
            return WorkloadPattern.CODE

        if distant_ratio > 0.6 and high_diversity_early < 30:
            # High distant but fewer consistent early blocks -> RAG (scattered)
            return WorkloadPattern.RAG

        if local_ratio >= 0.4:
            # Balanced or local-dominant -> LONG_CONTEXT
            return WorkloadPattern.LONG_CONTEXT

        return WorkloadPattern.LONG_CONTEXT  # Default fallback

    def _update_co_activation(self, blocks_attended: Set[int], step: int) -> None:
        """
        Track co-activation between blocks attended in the same query.

        When multiple blocks are attended together, they form a coherent group
        that should be selected together in future queries.
        """
        # Only track for Long-Context and RAG patterns
        if self.detected_pattern not in (WorkloadPattern.LONG_CONTEXT, WorkloadPattern.RAG):
            return

        # Limit to top blocks by weight to avoid O(n^2) explosion
        # For efficiency, sample pairs rather than computing all
        blocks_list = list(blocks_attended)[:32]  # Top 32 blocks

        # Update co-activation counts for sampled pairs
        for i, block_a in enumerate(blocks_list):
            for block_b in blocks_list[i + 1:min(i + 8, len(blocks_list))]:
                # Use sorted tuple as key
                pair = (min(block_a, block_b), max(block_a, block_b))
                self._co_activation[pair] = self._co_activation.get(pair, 0) + 1

    def finalize_step(self, blocks_attended: Set[int], step: int) -> None:
        """
        Called after each step to update co-activation tracking.

        This should be called after all updates for a single attention step
        have been processed.
        """
        self._update_co_activation(blocks_attended, step)

    def _should_enable_phase_mode(self) -> bool:
        """
        Detect when PCAM is struggling and phase-mode should be enabled.

        Signals that indicate phase-mode would help:
        - High distant attention ratio (sparse attention)
        - Low query overlap (different blocks per query)
        - Pattern is LONG_CONTEXT or RAG
        """
        # Only enable for patterns where individual block prediction fails
        if self.detected_pattern not in (WorkloadPattern.LONG_CONTEXT, WorkloadPattern.RAG):
            return False

        # Need sufficient data
        if self.total_attends < 10:
            return False

        # Check distant attention ratio
        total = self._distant_attention_count + self._local_attention_count
        if total == 0:
            return False
        distant_ratio = self._distant_attention_count / total

        # High distant attention = sparse, unpredictable patterns
        # Threshold 0.4 covers both Long-Context (~46%) and RAG (~68%)
        return distant_ratio > 0.4

    def _build_clusters(self) -> None:
        """
        Build phase clusters from co-activation data.

        Uses a simple greedy clustering approach:
        1. Find strongly co-activated pairs
        2. Merge into clusters
        3. Limit cluster sizes for efficiency
        """
        if not self._co_activation:
            return

        # Reset clusters
        self._phase_clusters.clear()
        self._block_to_cluster.clear()

        # Find strongly co-activated pairs (threshold: 3+ co-activations)
        strong_pairs = [
            (pair, count) for pair, count in self._co_activation.items()
            if count >= 3
        ]
        strong_pairs.sort(key=lambda x: -x[1])  # Sort by count descending

        # Greedy clustering
        for (block_a, block_b), count in strong_pairs:
            cluster_a = self._block_to_cluster.get(block_a)
            cluster_b = self._block_to_cluster.get(block_b)

            if cluster_a is None and cluster_b is None:
                # Both unassigned - create new cluster
                cluster_id = self._next_cluster_id
                self._next_cluster_id += 1
                cluster = PhaseCluster(
                    cluster_id=cluster_id,
                    blocks={block_a, block_b},
                    activation_count=count,
                )
                cluster.update_centroid()
                self._phase_clusters[cluster_id] = cluster
                self._block_to_cluster[block_a] = cluster_id
                self._block_to_cluster[block_b] = cluster_id

            elif cluster_a is not None and cluster_b is None:
                # Add block_b to cluster_a
                cluster = self._phase_clusters[cluster_a]
                if len(cluster.blocks) < 16:  # Max cluster size
                    cluster.blocks.add(block_b)
                    cluster.activation_count += count
                    cluster.update_centroid()
                    self._block_to_cluster[block_b] = cluster_a

            elif cluster_a is None and cluster_b is not None:
                # Add block_a to cluster_b
                cluster = self._phase_clusters[cluster_b]
                if len(cluster.blocks) < 16:
                    cluster.blocks.add(block_a)
                    cluster.activation_count += count
                    cluster.update_centroid()
                    self._block_to_cluster[block_a] = cluster_b

            # If both assigned to different clusters, don't merge (keep clusters distinct)

    def _get_cluster_expanded_candidates(
        self,
        k: int,
        query_block_id: Optional[int],
        exclude: Set[int],
        base_candidates: Dict[int, float],
    ) -> List[Tuple[int, float]]:
        """
        Get candidates using cluster-based expansion.

        Instead of picking top-K individual blocks, pick top-M clusters
        and expand to blocks within those clusters.

        Args:
            k: Total number of candidates to return
            query_block_id: Current query position
            exclude: Blocks to exclude
            base_candidates: Initial block scores from standard method

        Returns:
            List of (block_id, score) tuples
        """
        if not self._phase_clusters:
            # No clusters built yet - fall back to standard selection
            scored = [(score, block_id) for block_id, score in base_candidates.items()]
            top_k = heapq.nlargest(k, scored)
            return [(block_id, score) for score, block_id in top_k]

        # Score clusters based on their blocks' scores
        cluster_scores: Dict[int, float] = {}
        for cluster_id, cluster in self._phase_clusters.items():
            # Cluster score = sum of member block scores + coherence bonus
            member_scores = sum(
                base_candidates.get(block, 0) for block in cluster.blocks
            )
            coherence_bonus = cluster.coherence_score * 0.5
            cluster_scores[cluster_id] = member_scores + coherence_bonus

        # Select fewer clusters - leave room for high-scoring individual blocks
        # Only use ~30% of k for cluster expansion, rest for individual blocks
        cluster_budget = int(k * 0.3)
        avg_cluster_size = sum(len(c.blocks) for c in self._phase_clusters.values()) / max(1, len(self._phase_clusters))
        m = max(2, int(cluster_budget / max(4, avg_cluster_size)))

        scored_clusters = [(score, cid) for cid, score in cluster_scores.items()]
        top_clusters = heapq.nlargest(m, scored_clusters)

        # Expand clusters to get candidate blocks
        cluster_blocks: Set[int] = set()
        for _, cluster_id in top_clusters:
            cluster = self._phase_clusters[cluster_id]
            cluster_blocks.update(cluster.blocks - exclude)

        # Fill remaining slots with highest-scoring individual blocks
        remaining = k - len(cluster_blocks)
        if remaining > 0:
            # Get blocks not in selected clusters
            non_cluster_candidates = {
                bid: score for bid, score in base_candidates.items()
                if bid not in cluster_blocks and bid not in exclude
            }
            sorted_non_cluster = sorted(
                non_cluster_candidates.items(), key=lambda x: -x[1]
            )[:remaining]
            cluster_blocks.update(bid for bid, _ in sorted_non_cluster)

        # Build final result with scores
        result = []
        for block_id in cluster_blocks:
            score = base_candidates.get(block_id, 0.1)
            # Boost blocks from clusters
            if block_id in self._block_to_cluster:
                score *= 1.2
            result.append((block_id, score))

        # Sort by score and return top-K
        result.sort(key=lambda x: -x[1])
        return result[:k]

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

        # Finalize co-activation from previous query's blocks
        if self._last_query_blocks:
            self._update_co_activation(self._last_query_blocks, self.current_step)
            self._last_query_blocks = set()

        # Update workload detection after sufficient data
        if self.total_updates >= 50 and self.detected_pattern == WorkloadPattern.UNKNOWN:
            self.detected_pattern = self.detect_workload()
        elif self.total_updates % self._detection_window == 0 and self.total_updates >= 100:
            # Re-detect periodically after initial detection
            self.detected_pattern = self.detect_workload()

        # Workload-adaptive parameters
        pattern = self.detected_pattern
        if pattern == WorkloadPattern.CHAT:
            recency_window = 24
            recency_strength = 0.6
            query_window = 12
            diversity_boost_enabled = False
            global_importance_enabled = False
        elif pattern == WorkloadPattern.LONG_CONTEXT:
            recency_window = 48
            recency_strength = 0.5
            query_window = 20
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

        # Structural boost for CODE workloads
        # Two signals: (1) import-like blocks attended by many queries (diversity),
        # (2) definition-like blocks with high attention weight per access.
        #
        # The core problem: EMA scoring accumulates over time, so frequently-accessed
        # recent blocks have scores 10-20x higher than structurally important but
        # infrequently-accessed definition blocks. We scale the boost relative to
        # the current candidate score distribution so it's competitive.
        if diversity_boost_enabled and query_block_id is not None:
            # Compute score baseline for scaling structural boosts.
            # Q25 of the current candidate pool — structural blocks need additive
            # boosts proportional to this to become competitive with recency/edge scores.
            if candidates:
                score_vals = sorted(candidates.values())
                score_anchor = score_vals[len(score_vals) // 4] if len(score_vals) > 4 else score_vals[0]
            else:
                score_anchor = 0.1

            for bs in self.block_scores.values():
                if bs.block_id in exclude:
                    continue
                distance = abs(bs.block_id - query_block_id)

                # Signal 1: Diversity boost (imports — many unique query sources)
                if distance > 50:
                    query_diversity = len(bs.unique_query_sources)
                    if query_diversity >= 3:
                        diversity_boost = score_anchor * math.log1p(query_diversity) * 0.5
                        candidates[bs.block_id] = candidates.get(bs.block_id, 0) + diversity_boost

                # Signal 2: Structural weight boost (definitions)
                # Blocks that carry substantial attention per access are
                # structurally important (function defs, class defs, type
                # annotations, scope headers). Boost proportional to their
                # avg_weight relative to the candidate score distribution.
                if distance > 8 and bs.access_count >= 2:
                    avg_weight = bs.cumulative_weight / bs.access_count
                    if avg_weight > 0.02:
                        weight_signal = min(avg_weight / 0.05, 2.0)
                        structural_boost = score_anchor * weight_signal * 0.8
                        candidates[bs.block_id] = candidates.get(bs.block_id, 0) + structural_boost

        # Global importance boost for RAG workloads
        # Helps identify consistently important blocks across queries
        if global_importance_enabled:
            for bs in self.block_scores.values():
                if bs.block_id in exclude:
                    continue
                # Boost blocks that have high global importance
                if bs.global_importance > 0.1:
                    candidates[bs.block_id] = candidates.get(bs.block_id, 0) + bs.global_importance * 0.3

        # Soft Hierarchical Prior: section boost for Long-Context and RAG
        # CRITICAL: This is ADDITIVE (prior), not SUBSTITUTIVE (filter)
        # Blocks in high-attention sections get a small boost
        # Blocks elsewhere are NOT excluded - they can still be selected
        if pattern in (WorkloadPattern.LONG_CONTEXT, WorkloadPattern.RAG) and self._sections:
            for block_id in candidates:
                section_boost = self._get_section_boost(block_id)
                if section_boost > 0:
                    candidates[block_id] += section_boost

        # Phase-mode: check if we should use cluster-based selection
        # Only for Long-Context and RAG where individual block prediction fails
        self._phase_mode_enabled = self._should_enable_phase_mode()

        if self._phase_mode_enabled:
            # Rebuild clusters periodically
            if self.total_attends % self._cluster_rebuild_interval == 0:
                self._build_clusters()

            # Add cluster coherence bonus to candidates (don't replace selection)
            if self._phase_clusters:
                for cluster in self._phase_clusters.values():
                    if cluster.coherence_score > 0.1:
                        # Boost all blocks in coherent clusters
                        cluster_boost = cluster.coherence_score * 0.15
                        for block_id in cluster.blocks:
                            if block_id in candidates:
                                candidates[block_id] += cluster_boost

        # Standard selection: use heapq for efficient top-K
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

        # Track blocks for co-activation (Phase Coherence)
        # Accumulate blocks - will be processed in next get_top_k call
        self._last_query_blocks.add(key_block)

        # Update section-level statistics for soft hierarchical prior
        # IMPORTANT: Updates always flow to blocks regardless of section selection
        self._update_section_stats(query_block, key_block, weight)

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

        # Track query position for co-activation detection
        if not self._query_positions or self._query_positions[-1] != query_block:
            self._query_positions.append(query_block)
            # Keep limited history
            if len(self._query_positions) > 100:
                self._query_positions = self._query_positions[-100:]

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
        query_block_id: Optional[int] = None,
    ) -> int:
        """
        Batch UPDATE operation.

        Returns number of successful updates.
        """
        seq = self.sequences.get(sequence_id)
        if seq is None:
            return 0

        # Use provided query_block_id if available, else approximate
        query_block = query_block_id if query_block_id is not None else step // 16

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
