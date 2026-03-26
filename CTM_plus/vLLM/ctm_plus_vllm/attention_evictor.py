"""
Attention-Aware KV-Cache Evictor for vLLM.

Extends CTM+ with KV-cache-specific intelligence:
- Attention accumulation: tracks per-token cumulative attention
- Position classification: sink / recent / entity / filler
- Phase-aware policies: different scoring for prefill vs decode
- Frequency sketching: Count-Min Sketch for O(1) approximate frequency
- S3-FIFO inspired admission: small/main/ghost three-queue structure

This is the working implementation that bridges CTM+ memory tiering
with LLM-specific KV-cache eviction requirements.

Reference: docs/design/CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md
"""

import math
import random
import threading
import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any


# =============================================================================
# Frequency Sketch (W-TinyLFU inspired)
# =============================================================================

class FrequencySketch:
    """
    4-bit Count-Min Sketch for approximate frequency estimation.

    Provides O(1) frequency tracking with bounded memory.
    Periodically halves all counters to age out stale frequencies.
    Replaces unbounded access_count tracking.
    """

    def __init__(self, capacity: int):
        self.width = self._next_power_of_2(max(64, capacity))
        self.depth = 4
        self.table = [[0] * self.width for _ in range(self.depth)]
        self.size = 0
        self.reset_threshold = capacity * 10
        self._seeds = [0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138]

    @staticmethod
    def _next_power_of_2(n: int) -> int:
        n -= 1
        n |= n >> 1
        n |= n >> 2
        n |= n >> 4
        n |= n >> 8
        n |= n >> 16
        return n + 1

    def _hash(self, key: int, seed_idx: int) -> int:
        h = key * self._seeds[seed_idx]
        h ^= h >> 16
        return h & (self.width - 1)

    def increment(self, key: int) -> int:
        """Increment frequency for key. Returns estimated frequency."""
        self.size += 1
        if self.size >= self.reset_threshold:
            self._reset()

        min_count = 15  # 4-bit max
        for i in range(self.depth):
            idx = self._hash(key, i)
            self.table[i][idx] = min(15, self.table[i][idx] + 1)
            min_count = min(min_count, self.table[i][idx])
        return min_count

    def estimate(self, key: int) -> int:
        """Estimate frequency for key. O(1)."""
        min_count = 15
        for i in range(self.depth):
            idx = self._hash(key, i)
            min_count = min(min_count, self.table[i][idx])
        return min_count

    def _reset(self):
        """Halve all counters (doorkeeper reset). Ages out stale frequencies."""
        for i in range(self.depth):
            for j in range(self.width):
                self.table[i][j] >>= 1
        self.size >>= 1


# =============================================================================
# Position Classification
# =============================================================================

class PositionClass(Enum):
    """Classification of token positions for eviction priority."""
    SINK = auto()      # Attention sink (positions 0..k), never evict
    RECENT = auto()    # Recent window, protected during decode
    ENTITY = auto()    # High cumulative attention, protect
    FILLER = auto()    # Low attention, evict first


class PositionClassifier:
    """
    Classifies token positions based on attention patterns.

    Uses cumulative attention to identify which tokens are structurally
    important vs filler that can be safely evicted.
    """

    def __init__(
        self,
        sink_tokens: int = 4,
        recent_window: int = 256,
        entity_attention_threshold: float = 0.02,
    ):
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self.entity_attention_threshold = entity_attention_threshold

    def classify(
        self,
        position: int,
        seq_len: int,
        cumulative_attention: float,
    ) -> PositionClass:
        """Classify a token position."""
        # Attention sinks are always protected
        if position < self.sink_tokens:
            return PositionClass.SINK

        # Recent window is protected during decode
        if position >= seq_len - self.recent_window:
            return PositionClass.RECENT

        # High cumulative attention = entity/important token
        if cumulative_attention > self.entity_attention_threshold:
            return PositionClass.ENTITY

        return PositionClass.FILLER


# =============================================================================
# Inference Phase
# =============================================================================

class InferencePhase(Enum):
    """Phase of LLM inference."""
    PREFILL = auto()    # Processing input prompt
    DECODE = auto()     # Autoregressive generation
    COMPLETE = auto()   # Sequence finished


# =============================================================================
# Per-Token State
# =============================================================================

@dataclass
class TokenState:
    """Per-token state tracked by the attention-aware evictor."""
    token_id: int
    position: int
    sequence_id: int
    block_id: int                    # Which KV block this token belongs to
    created_step: int = 0
    last_access_step: int = 0
    cumulative_attention: float = 0.0  # EMA of attention received
    position_class: PositionClass = PositionClass.FILLER
    is_pinned: bool = False


@dataclass
class BlockScoreCache:
    """Cached aggregate scores for a KV block."""
    block_id: int
    avg_attention: float = 0.0
    sink_count: int = 0
    recent_count: int = 0
    entity_count: int = 0
    filler_count: int = 0
    total_tokens: int = 0
    frequency: int = 0
    last_computed_step: int = 0

    @property
    def importance(self) -> float:
        """Block importance based on token composition."""
        if self.total_tokens == 0:
            return 0.0
        # Sinks and entities are most important
        weighted = (
            1.0 * self.sink_count +
            0.8 * self.entity_count +
            0.6 * self.recent_count +
            0.1 * self.filler_count
        )
        return weighted / self.total_tokens


# =============================================================================
# Sequence State
# =============================================================================

@dataclass
class SequenceState:
    """Per-sequence tracking."""
    sequence_id: int
    phase: InferencePhase = InferencePhase.PREFILL
    priority: float = 1.0             # User-specified priority
    total_tokens: int = 0
    generated_tokens: int = 0
    max_tokens: int = 0               # Generation budget
    block_ids: Set[int] = field(default_factory=set)
    created_time: float = 0.0

    @property
    def progress(self) -> float:
        """Generation progress [0, 1]."""
        if self.max_tokens <= 0:
            return 0.0
        return min(1.0, self.generated_tokens / self.max_tokens)

    @property
    def invested_compute(self) -> float:
        """Relative compute already invested (favor keeping long sequences)."""
        return min(1.0, self.total_tokens / 4096.0)


# =============================================================================
# S3-FIFO Queue Structure
# =============================================================================

class S3FIFOQueue:
    """
    Three-queue FIFO structure inspired by S3-FIFO (SOSP'23).

    Provides O(1) admission/eviction with scan resistance:
    - Small queue (10%): New blocks enter here
    - Main queue (90%): Promoted on second access
    - Ghost queue: Metadata-only, tracks recently evicted

    One-hit-wonders are evicted from Small without polluting Main.
    """

    def __init__(self, capacity: int, small_ratio: float = 0.10):
        self.capacity = capacity
        self.small_capacity = max(1, int(capacity * small_ratio))
        self.main_capacity = capacity - self.small_capacity
        self.ghost_capacity = capacity  # Same size as total

        # Queues (FIFO order)
        self.small: OrderedDict[int, bool] = OrderedDict()  # block_id -> visited
        self.main: OrderedDict[int, bool] = OrderedDict()   # block_id -> visited
        self.ghost: OrderedDict[int, float] = OrderedDict()  # block_id -> evict_time

        # Lookup for O(1) contains
        self._location: Dict[int, str] = {}  # block_id -> 'small'|'main'

    def admit(self, block_id: int, current_time: float) -> Optional[int]:
        """
        Admit a block. Returns evicted block_id or None.

        If block is in ghost, admit directly to main (it was useful).
        Otherwise admit to small queue.
        """
        # Ghost hit -> direct to main
        if block_id in self.ghost:
            del self.ghost[block_id]
            return self._add_to_main(block_id, current_time)

        # Normal admission -> small queue
        return self._add_to_small(block_id, current_time)

    def access(self, block_id: int) -> None:
        """Record an access (mark as visited for SIEVE-like lazy promotion)."""
        if block_id in self.small:
            self.small[block_id] = True  # Mark visited
        elif block_id in self.main:
            self.main[block_id] = True   # Mark visited

    def _add_to_small(self, block_id: int, current_time: float) -> Optional[int]:
        """Add to small queue, evicting if needed."""
        evicted = None
        while len(self.small) >= self.small_capacity:
            evicted = self._evict_from_small(current_time)
        self.small[block_id] = False  # Not visited yet
        self._location[block_id] = 'small'
        return evicted

    def _add_to_main(self, block_id: int, current_time: float) -> Optional[int]:
        """Add to main queue, evicting if needed."""
        evicted = None
        while len(self.main) >= self.main_capacity:
            evicted = self._evict_from_main(current_time)
        self.main[block_id] = False
        self._location[block_id] = 'main'
        return evicted

    def _evict_from_small(self, current_time: float) -> Optional[int]:
        """Evict from small queue. Visited entries promote to main."""
        while self.small:
            block_id, visited = self.small.popitem(last=False)
            del self._location[block_id]

            if visited:
                # Promoted to main (was accessed while in small)
                self._add_to_main(block_id, current_time)
                continue

            # One-hit-wonder -> evict to ghost
            self._add_to_ghost(block_id, current_time)
            return block_id
        return None

    def _evict_from_main(self, current_time: float) -> Optional[int]:
        """
        Evict from main queue using SIEVE-style lazy eviction.
        Visited entries get a second chance (cleared and moved to tail).
        """
        max_scan = len(self.main)
        for _ in range(max_scan):
            if not self.main:
                return None
            block_id, visited = self.main.popitem(last=False)

            if visited:
                # Second chance: clear visited, move to tail
                self.main[block_id] = False
                continue

            # Evict
            del self._location[block_id]
            self._add_to_ghost(block_id, current_time)
            return block_id
        return None

    def _add_to_ghost(self, block_id: int, current_time: float) -> None:
        """Add to ghost queue (metadata only)."""
        if len(self.ghost) >= self.ghost_capacity:
            self.ghost.popitem(last=False)
        self.ghost[block_id] = current_time

    def remove(self, block_id: int) -> None:
        """Remove a block entirely (sequence completed)."""
        if block_id in self.small:
            del self.small[block_id]
        elif block_id in self.main:
            del self.main[block_id]
        self._location.pop(block_id, None)
        self.ghost.pop(block_id, None)

    def contains(self, block_id: int) -> bool:
        return block_id in self._location

    def select_victim(self) -> Optional[int]:
        """Select victim for eviction (prefer small queue)."""
        # Try small queue first (one-hit-wonders)
        for block_id, visited in self.small.items():
            if not visited:
                return block_id

        # Then main queue (unvisited entries)
        for block_id, visited in self.main.items():
            if not visited:
                return block_id

        # All visited — return oldest from small
        if self.small:
            return next(iter(self.small))
        if self.main:
            return next(iter(self.main))
        return None

    @property
    def size(self) -> int:
        return len(self.small) + len(self.main)


# =============================================================================
# Phase-Aware Scoring Weights
# =============================================================================

@dataclass(frozen=True)
class PhaseWeights:
    """Scoring weights for victim selection, tuned per inference phase."""
    recency: float
    frequency: float
    attention_value: float
    position_importance: float
    sequence_priority: float
    reuse: float


PHASE_WEIGHTS = {
    InferencePhase.PREFILL: PhaseWeights(
        recency=0.15,
        frequency=0.15,
        attention_value=0.30,  # Attention matters most in prefill
        position_importance=0.25,
        sequence_priority=0.10,
        reuse=0.05,
    ),
    InferencePhase.DECODE: PhaseWeights(
        recency=0.25,
        frequency=0.20,
        attention_value=0.25,
        position_importance=0.15,
        sequence_priority=0.10,
        reuse=0.05,
    ),
    InferencePhase.COMPLETE: PhaseWeights(
        recency=0.0,
        frequency=0.0,
        attention_value=0.0,
        position_importance=0.0,
        sequence_priority=0.0,
        reuse=0.0,
    ),
}


# =============================================================================
# Main Evictor
# =============================================================================

class AttentionAwareEvictor:
    """
    Attention-aware KV-cache evictor for vLLM.

    Combines CTM+ multi-signal scoring with LLM-specific intelligence:
    - Attention accumulation per token
    - Position classification (sink/recent/entity/filler)
    - S3-FIFO admission for scan resistance
    - Frequency sketching via Count-Min Sketch
    - Phase-aware scoring (prefill vs decode)
    - Sequence priority management

    Thread-safe via RLock.
    """

    def __init__(
        self,
        max_blocks: int,
        block_size: int = 16,
        sink_tokens: int = 4,
        recent_window: int = 256,
        entity_attention_threshold: float = 0.02,
        attention_ema_alpha: float = 0.1,
        small_queue_ratio: float = 0.10,
    ):
        """
        Args:
            max_blocks: Maximum KV blocks in GPU memory.
            block_size: Tokens per block.
            sink_tokens: Number of attention sink tokens to always protect.
            recent_window: Size of recent token window to protect.
            entity_attention_threshold: Cumulative attention threshold for entity class.
            attention_ema_alpha: EMA decay for attention accumulation.
            small_queue_ratio: Fraction of capacity for S3-FIFO small queue.
        """
        self.max_blocks = max_blocks
        self.block_size = block_size
        self.attention_ema_alpha = attention_ema_alpha

        # Components
        self.position_classifier = PositionClassifier(
            sink_tokens=sink_tokens,
            recent_window=recent_window,
            entity_attention_threshold=entity_attention_threshold,
        )
        self.frequency_sketch = FrequencySketch(max_blocks * 4)
        self.fifo_queue = S3FIFOQueue(max_blocks, small_queue_ratio)

        # State
        self.tokens: Dict[int, TokenState] = {}           # token_id -> state
        self.blocks: Dict[int, Set[int]] = {}              # block_id -> {token_ids}
        self.block_scores: Dict[int, BlockScoreCache] = {} # block_id -> cached scores
        self.sequences: Dict[int, SequenceState] = {}      # seq_id -> state
        self.gpu_blocks: Set[int] = set()
        self.pinned_blocks: Set[int] = set()

        # Counters
        self._step = 0
        self._score_cache_interval = 100  # Recompute block scores every N steps

        # Stats
        self.stats = {
            "evictions": 0,
            "ghost_hits": 0,
            "sink_protections": 0,
            "entity_protections": 0,
            "filler_evictions": 0,
            "phase_switches": 0,
        }

        # Thread safety
        self._lock = threading.RLock()

    # =========================================================================
    # Sequence Management
    # =========================================================================

    def register_sequence(
        self,
        sequence_id: int,
        priority: float = 1.0,
        max_tokens: int = 4096,
    ) -> None:
        """Register a new sequence for tracking."""
        with self._lock:
            self.sequences[sequence_id] = SequenceState(
                sequence_id=sequence_id,
                priority=priority,
                max_tokens=max_tokens,
                created_time=time.monotonic(),
            )

    def set_sequence_phase(
        self,
        sequence_id: int,
        phase: InferencePhase,
    ) -> None:
        """Update inference phase for a sequence."""
        with self._lock:
            if sequence_id in self.sequences:
                old_phase = self.sequences[sequence_id].phase
                self.sequences[sequence_id].phase = phase
                if old_phase != phase:
                    self.stats["phase_switches"] += 1

    def complete_sequence(self, sequence_id: int) -> List[int]:
        """
        Mark sequence as complete and return all its block_ids for freeing.
        """
        with self._lock:
            if sequence_id not in self.sequences:
                return []

            seq = self.sequences[sequence_id]
            seq.phase = InferencePhase.COMPLETE
            blocks_to_free = list(seq.block_ids)

            # Clean up tokens
            for block_id in blocks_to_free:
                self._free_block(block_id)

            del self.sequences[sequence_id]
            return blocks_to_free

    # =========================================================================
    # Token & Block Access
    # =========================================================================

    def on_token_access(
        self,
        token_id: int,
        position: int,
        sequence_id: int,
        block_id: int,
        attention_weight: float = 0.0,
        seq_len: int = 0,
    ) -> None:
        """
        Record a token access with attention weight.

        This is called during the attention computation to track which
        tokens are receiving attention and update their importance.
        """
        with self._lock:
            self._step += 1

            # Update or create token state
            if token_id in self.tokens:
                ts = self.tokens[token_id]
                ts.last_access_step = self._step
                # EMA update of cumulative attention
                alpha = self.attention_ema_alpha
                ts.cumulative_attention = (
                    alpha * attention_weight +
                    (1 - alpha) * ts.cumulative_attention
                )
            else:
                ts = TokenState(
                    token_id=token_id,
                    position=position,
                    sequence_id=sequence_id,
                    block_id=block_id,
                    created_step=self._step,
                    last_access_step=self._step,
                    cumulative_attention=attention_weight,
                )
                self.tokens[token_id] = ts

            # Classify position
            ts.position_class = self.position_classifier.classify(
                position, seq_len, ts.cumulative_attention
            )

            # Pin sinks
            if ts.position_class == PositionClass.SINK:
                ts.is_pinned = True
                self.pinned_blocks.add(block_id)

            # Track block membership
            if block_id not in self.blocks:
                self.blocks[block_id] = set()
            self.blocks[block_id].add(token_id)

            # Track sequence blocks
            if sequence_id in self.sequences:
                self.sequences[sequence_id].block_ids.add(block_id)

            # Update frequency sketch
            self.frequency_sketch.increment(block_id)

            # Update S3-FIFO queue
            if self.fifo_queue.contains(block_id):
                self.fifo_queue.access(block_id)
            else:
                evicted = self.fifo_queue.admit(block_id, time.monotonic())
                if evicted is not None:
                    self.stats["ghost_hits"] += (
                        1 if block_id in self.fifo_queue.ghost else 0
                    )

            self.gpu_blocks.add(block_id)

    def on_block_access(self, block_id: int, sequence_id: int = 0) -> None:
        """Record a block-level access (no per-token detail)."""
        with self._lock:
            self._step += 1
            self.frequency_sketch.increment(block_id)

            if self.fifo_queue.contains(block_id):
                self.fifo_queue.access(block_id)
            else:
                self.fifo_queue.admit(block_id, time.monotonic())

            self.gpu_blocks.add(block_id)

    # =========================================================================
    # Victim Selection
    # =========================================================================

    def select_victim(self) -> Optional[int]:
        """
        Select the best block to evict from GPU.

        Strategy:
        1. Never evict pinned blocks (sinks)
        2. Prefer filler-only blocks
        3. Use phase-aware multi-signal scoring
        4. Fall back to S3-FIFO queue order
        """
        with self._lock:
            if not self.gpu_blocks:
                return None

            available = self.gpu_blocks - self.pinned_blocks
            if not available:
                return None

            # Recompute block scores if stale
            if self._step % self._score_cache_interval == 0:
                self._recompute_block_scores()

            # Phase 1: Find filler-only blocks (cheapest to evict)
            filler_blocks = []
            for block_id in available:
                score = self.block_scores.get(block_id)
                if score and score.filler_count == score.total_tokens and score.total_tokens > 0:
                    filler_blocks.append(block_id)

            if filler_blocks:
                # Among filler blocks, pick lowest frequency
                victim = min(
                    filler_blocks,
                    key=lambda bid: self.frequency_sketch.estimate(bid),
                )
                self.stats["filler_evictions"] += 1
                return victim

            # Phase 2: Sample and score candidates
            sample_size = min(48, len(available))
            candidates = random.sample(list(available), sample_size)

            # Always include S3-FIFO suggestion
            fifo_victim = self.fifo_queue.select_victim()
            if fifo_victim and fifo_victim in available and fifo_victim not in candidates:
                candidates.append(fifo_victim)

            best_victim = None
            best_score = float('inf')

            for block_id in candidates:
                score = self._compute_block_eviction_score(block_id)
                if score < best_score:
                    best_score = score
                    best_victim = block_id

            if best_victim is not None:
                self.stats["evictions"] += 1

            return best_victim

    def select_victims_batch(self, count: int) -> List[int]:
        """Select multiple victims for batch eviction."""
        with self._lock:
            victims = []
            available = self.gpu_blocks - self.pinned_blocks

            if not available:
                return victims

            # Recompute scores
            self._recompute_block_scores()

            # Score all available blocks
            scored = []
            for block_id in available:
                score = self._compute_block_eviction_score(block_id)
                scored.append((block_id, score))

            # Sort by score (lowest = evict first)
            scored.sort(key=lambda x: x[1])

            for block_id, _ in scored[:count]:
                victims.append(block_id)

            self.stats["evictions"] += len(victims)
            return victims

    def _compute_block_eviction_score(self, block_id: int) -> float:
        """
        Compute eviction score for a block. Lower = evict first.

        Uses phase-aware weights that change based on the dominant
        sequence phase for tokens in this block.
        """
        # Determine dominant phase for this block
        phase = self._get_block_phase(block_id)
        weights = PHASE_WEIGHTS[phase]

        # Complete sequences should be evicted immediately
        if phase == InferencePhase.COMPLETE:
            return -1.0

        # Get cached block scores
        bs = self.block_scores.get(block_id)

        # Signal 1: Recency
        recency = 0.0
        if block_id in self.blocks:
            token_ids = self.blocks[block_id]
            if token_ids:
                max_access = max(
                    self.tokens[tid].last_access_step
                    for tid in token_ids if tid in self.tokens
                )
                age = self._step - max_access
                recency = math.exp(-0.01 * age)

        # Signal 2: Frequency (from sketch)
        freq_raw = self.frequency_sketch.estimate(block_id)
        frequency = min(1.0, freq_raw / 10.0)

        # Signal 3: Attention value
        attention_value = bs.avg_attention if bs else 0.0

        # Signal 4: Position importance
        position_importance = bs.importance if bs else 0.0

        # Signal 5: Sequence priority
        seq_priority = self._get_block_sequence_priority(block_id)

        # Signal 6: Reuse (simple: was it in ghost queue?)
        reuse = 0.3  # base
        if block_id in self.fifo_queue.main:
            reuse = 0.7  # survived small queue

        # Weighted score
        score = (
            weights.recency * recency +
            weights.frequency * frequency +
            weights.attention_value * attention_value +
            weights.position_importance * position_importance +
            weights.sequence_priority * seq_priority +
            weights.reuse * reuse
        )

        # Protection bonuses
        if bs:
            if bs.sink_count > 0:
                score += 10.0  # Very high protection for sink-containing blocks
                self.stats["sink_protections"] += 1
            if bs.entity_count > 0:
                score += 0.5 * (bs.entity_count / max(1, bs.total_tokens))
                self.stats["entity_protections"] += 1

        return score

    def _get_block_phase(self, block_id: int) -> InferencePhase:
        """Get dominant inference phase for tokens in a block."""
        if block_id not in self.blocks:
            return InferencePhase.DECODE

        token_ids = self.blocks[block_id]
        phase_counts: Dict[InferencePhase, int] = {}

        for tid in token_ids:
            ts = self.tokens.get(tid)
            if ts and ts.sequence_id in self.sequences:
                phase = self.sequences[ts.sequence_id].phase
                phase_counts[phase] = phase_counts.get(phase, 0) + 1

        if not phase_counts:
            return InferencePhase.DECODE

        return max(phase_counts, key=phase_counts.get)

    def _get_block_sequence_priority(self, block_id: int) -> float:
        """Get average sequence priority for tokens in a block."""
        if block_id not in self.blocks:
            return 0.5

        priorities = []
        for tid in self.blocks[block_id]:
            ts = self.tokens.get(tid)
            if ts and ts.sequence_id in self.sequences:
                seq = self.sequences[ts.sequence_id]
                # Priority weighted by invested compute
                priorities.append(seq.priority * (0.5 + 0.5 * seq.invested_compute))

        return sum(priorities) / len(priorities) if priorities else 0.5

    # =========================================================================
    # Block Score Computation
    # =========================================================================

    def _recompute_block_scores(self) -> None:
        """Recompute cached block scores from token states."""
        for block_id, token_ids in self.blocks.items():
            bs = BlockScoreCache(block_id=block_id, last_computed_step=self._step)

            total_attention = 0.0
            for tid in token_ids:
                ts = self.tokens.get(tid)
                if not ts:
                    continue

                bs.total_tokens += 1
                total_attention += ts.cumulative_attention

                if ts.position_class == PositionClass.SINK:
                    bs.sink_count += 1
                elif ts.position_class == PositionClass.RECENT:
                    bs.recent_count += 1
                elif ts.position_class == PositionClass.ENTITY:
                    bs.entity_count += 1
                else:
                    bs.filler_count += 1

            bs.avg_attention = (
                total_attention / bs.total_tokens if bs.total_tokens > 0 else 0.0
            )
            bs.frequency = self.frequency_sketch.estimate(block_id)
            self.block_scores[block_id] = bs

    # =========================================================================
    # Eviction & Cleanup
    # =========================================================================

    def evict_block(self, block_id: int) -> None:
        """Mark block as evicted from GPU."""
        with self._lock:
            self.gpu_blocks.discard(block_id)
            self.pinned_blocks.discard(block_id)
            # Keep token metadata for potential re-promotion decisions
            # S3-FIFO queue tracks this in ghost

    def _free_block(self, block_id: int) -> None:
        """Completely free a block and all its tokens."""
        # Remove tokens
        if block_id in self.blocks:
            for tid in self.blocks[block_id]:
                self.tokens.pop(tid, None)
            del self.blocks[block_id]

        # Remove from all tracking
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)
        self.block_scores.pop(block_id, None)
        self.fifo_queue.remove(block_id)

    def pin_block(self, block_id: int) -> None:
        """Pin block to prevent eviction."""
        with self._lock:
            self.pinned_blocks.add(block_id)

    def unpin_block(self, block_id: int) -> None:
        """Unpin block to allow eviction."""
        with self._lock:
            self.pinned_blocks.discard(block_id)

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get evictor statistics."""
        with self._lock:
            position_dist = {
                "sink": 0, "recent": 0, "entity": 0, "filler": 0,
            }
            for ts in self.tokens.values():
                key = ts.position_class.name.lower()
                position_dist[key] = position_dist.get(key, 0) + 1

            return {
                **self.stats,
                "total_tokens": len(self.tokens),
                "total_blocks": len(self.blocks),
                "gpu_blocks": len(self.gpu_blocks),
                "pinned_blocks": len(self.pinned_blocks),
                "active_sequences": len(self.sequences),
                "fifo_small_size": len(self.fifo_queue.small),
                "fifo_main_size": len(self.fifo_queue.main),
                "fifo_ghost_size": len(self.fifo_queue.ghost),
                "position_distribution": position_dist,
                "frequency_sketch_size": self.frequency_sketch.size,
                "step": self._step,
            }
