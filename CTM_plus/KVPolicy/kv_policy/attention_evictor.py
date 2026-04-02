"""
KV cache eviction policy for LLM inference.

This module provides scoring logic for KV cache block eviction decisions.
It does NOT manage memory, I/O, or block allocation — those are handled
by the serving engine (e.g. vLLM's BlockSpaceManager).

Signals used for scoring:
  1. Attention value — cumulative attention received by tokens in the block
  2. Position importance — sink/entity/recent/filler classification
  3. Frequency — Count-Min Sketch for O(1) approximate block access count
  4. Recency — exponential decay of time since last access

Phase-aware: scoring weights differ between prefill and decode phases.

Integration point: vLLM's Evictor abstract base class.
    class Evictor(ABC):
        def evict(self) -> Tuple[PhysicalTokenBlock, ...]: ...

Not thread-safe. Callers must synchronize externally.
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Any


# =============================================================================
# Frequency Sketch (Count-Min Sketch, 4-bit counters)
# =============================================================================

class FrequencySketch:
    """
    4-bit Count-Min Sketch for O(1) approximate frequency tracking.
    Periodically halves all counters to age out stale frequencies.
    """

    def __init__(self, capacity: int):
        self.width = self._next_pow2(max(64, capacity))
        self.depth = 4
        self.table = [[0] * self.width for _ in range(self.depth)]
        self.size = 0
        self.reset_threshold = capacity * 10
        self._seeds = [0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138]

    @staticmethod
    def _next_pow2(n: int) -> int:
        n -= 1
        n |= n >> 1; n |= n >> 2; n |= n >> 4; n |= n >> 8; n |= n >> 16
        return n + 1

    def _hash(self, key: int, i: int) -> int:
        h = key * self._seeds[i]
        h ^= h >> 16
        return h & (self.width - 1)

    def increment(self, key: int) -> int:
        self.size += 1
        if self.size >= self.reset_threshold:
            self._halve()
        min_count = 15
        for i in range(self.depth):
            idx = self._hash(key, i)
            self.table[i][idx] = min(15, self.table[i][idx] + 1)
            min_count = min(min_count, self.table[i][idx])
        return min_count

    def estimate(self, key: int) -> int:
        return min(self.table[i][self._hash(key, i)] for i in range(self.depth))

    def _halve(self):
        for row in self.table:
            for j in range(len(row)):
                row[j] >>= 1
        self.size >>= 1


# =============================================================================
# Position Classification
# =============================================================================

class PositionClass(Enum):
    SINK = auto()      # Attention sink (positions 0..k), never evict
    RECENT = auto()    # Recent window, protected during decode
    ENTITY = auto()    # High cumulative attention, protect
    FILLER = auto()    # Low attention, evict first


class InferencePhase(Enum):
    PREFILL = auto()
    DECODE = auto()


# =============================================================================
# Block State (replaces per-token tracking)
# =============================================================================

@dataclass
class BlockState:
    """
    Per-block metadata. Stores per-position attention (up to block_size
    entries, typically 16) instead of per-token objects.
    """
    block_id: int
    sequence_id: int
    token_attention: Dict[int, float] = field(default_factory=dict)
    created_step: int = 0
    last_access_step: int = 0
    access_count: int = 0

    @property
    def positions(self) -> list:
        return list(self.token_attention.keys())

    @property
    def num_tokens(self) -> int:
        return len(self.token_attention)

    @property
    def total_attention(self) -> float:
        return sum(self.token_attention.values())

    @property
    def avg_attention(self) -> float:
        n = len(self.token_attention)
        return sum(self.token_attention.values()) / n if n else 0.0


@dataclass
class SequenceState:
    sequence_id: int
    phase: InferencePhase = InferencePhase.PREFILL
    block_ids: Set[int] = field(default_factory=set)


# =============================================================================
# Phase-Aware Scoring Weights
# =============================================================================

@dataclass(frozen=True)
class PhaseWeights:
    recency: float
    frequency: float
    attention: float
    position: float


PHASE_WEIGHTS = {
    InferencePhase.PREFILL: PhaseWeights(0.15, 0.20, 0.35, 0.30),
    InferencePhase.DECODE:  PhaseWeights(0.30, 0.20, 0.30, 0.20),
}


# =============================================================================
# KV Cache Policy
# =============================================================================

class KVCachePolicy:
    """
    Attention-aware KV cache eviction policy for LLM inference.

    Provides two entry points for integration:
      - score_block(block_id) -> float   (lower = evict first)
      - select_victims(count) -> list    (returns block_ids to evict)

    Tracks per-block state incrementally. Each block stores per-position
    attention (up to block_size entries, typically 16). No per-token dict,
    no periodic recomputation — scores are always current.
    """

    def __init__(
        self,
        max_blocks: int,
        block_size: int = 16,
        sink_tokens: int = 4,
        recent_window: int = 256,
        entity_attention_threshold: float = 0.02,
        attention_ema_alpha: float = 0.1,
    ):
        self.max_blocks = max_blocks
        self.block_size = block_size
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self.entity_threshold = entity_attention_threshold
        self.ema_alpha = attention_ema_alpha

        self.freq_sketch = FrequencySketch(max_blocks * 4)

        self.blocks: Dict[int, BlockState] = {}
        self.sequences: Dict[int, SequenceState] = {}
        self.gpu_blocks: Set[int] = set()
        self.pinned_blocks: Set[int] = set()

        self._step = 0

        self.stats = {
            "evictions": 0,
            "filler_evictions": 0,
        }

    # ---- Sequence lifecycle ----

    def register_sequence(self, seq_id: int):
        self.sequences[seq_id] = SequenceState(sequence_id=seq_id)

    def set_phase(self, seq_id: int, phase: InferencePhase):
        if seq_id in self.sequences:
            self.sequences[seq_id].phase = phase

    def complete_sequence(self, seq_id: int) -> List[int]:
        if seq_id not in self.sequences:
            return []
        seq = self.sequences[seq_id]
        freed = list(seq.block_ids)
        for bid in freed:
            self._free_block(bid)
        del self.sequences[seq_id]
        return freed

    # ---- Token access (called during attention computation) ----

    def on_token_access(
        self,
        token_id: int,
        position: int,
        sequence_id: int,
        block_id: int,
        attention_weight: float = 0.0,
        seq_len: int = 0,
    ):
        """
        Record an attention event for a token.

        Aggregates directly into BlockState. The token_id parameter is
        accepted for API compatibility but not stored — tracking is
        by (block_id, position).
        """
        self._step += 1

        # Get or create block
        block = self.blocks.get(block_id)
        if block is None:
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
            )
            self.blocks[block_id] = block

        # Update per-position attention (EMA)
        prev = block.token_attention.get(position, 0.0)
        block.token_attention[position] = (
            self.ema_alpha * attention_weight +
            (1 - self.ema_alpha) * prev
        )

        # Update block-level stats
        block.access_count += 1
        block.last_access_step = self._step

        # Pin sinks
        if position < self.sink_tokens:
            self.pinned_blocks.add(block_id)

        # Sequence tracking
        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)

        self.gpu_blocks.add(block_id)

    def on_block_attention(
        self,
        block_id: int,
        position_attention: Dict[int, float],
        sequence_id: int,
        seq_len: int = 0,
    ):
        """
        Record attention for an entire block in one call.

        Equivalent to calling on_token_access for each position, but
        with O(1) overhead for step/freq/sequence bookkeeping instead
        of O(block_size).
        """
        self._step += 1

        # Get or create block
        block = self.blocks.get(block_id)
        if block is None:
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
            )
            self.blocks[block_id] = block

        # Bulk EMA update for all positions
        alpha = self.ema_alpha
        one_minus_alpha = 1 - alpha
        for pos, attn in position_attention.items():
            prev = block.token_attention.get(pos, 0.0)
            block.token_attention[pos] = alpha * attn + one_minus_alpha * prev

        # Block-level stats — once per block, not per position
        block.access_count += 1
        block.last_access_step = self._step

        # Pin if any position is a sink
        if any(pos < self.sink_tokens for pos in position_attention):
            self.pinned_blocks.add(block_id)

        # Sequence tracking
        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)

        self.gpu_blocks.add(block_id)

    def ensure_block(self, block_id: int, sequence_id: int, positions: List[int]):
        """
        Lightweight block registration. Creates block metadata without
        recording any attention — used on admission.
        """
        if block_id not in self.blocks:
            self._step += 1
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
            )
            # Seed positions with zero attention
            for pos in positions:
                block.token_attention[pos] = 0.0
            self.blocks[block_id] = block

            if any(pos < self.sink_tokens for pos in positions):
                self.pinned_blocks.add(block_id)

            if sequence_id in self.sequences:
                self.sequences[sequence_id].block_ids.add(block_id)

            self.gpu_blocks.add(block_id)

    # ---- Scoring interface ----

    def score_block(self, block_id: int) -> float:
        """
        Score a single block for eviction. Lower = evict first.
        Reads directly from BlockState — always current.
        """
        block = self.blocks.get(block_id)
        if not block:
            return -1.0

        seq = self.sequences.get(block.sequence_id)
        phase = seq.phase if seq else InferencePhase.DECODE

        w = PHASE_WEIGHTS.get(phase)
        if not w:
            return -1.0

        seq_len = len(seq.block_ids) * self.block_size if seq else 0

        # Signal 1: Recency — exponential decay
        recency = math.exp(-0.01 * (self._step - block.last_access_step))

        # Signal 2: Frequency — Count-Min Sketch
        frequency = min(1.0, self.freq_sketch.estimate(block_id) / 10.0)

        # Signal 3: Attention — average per-position attention
        attention = block.avg_attention

        # Signal 4: Position importance — classify each position in block
        importance = self._block_importance(block, seq_len)

        score = (
            w.recency * recency +
            w.frequency * frequency +
            w.attention * attention +
            w.position * importance
        )

        # Entity bonus — protect blocks with high-attention positions
        entity_count = sum(
            1 for pos, attn in block.token_attention.items()
            if pos >= self.sink_tokens and attn > self.entity_threshold
        )
        if entity_count > 0:
            score += 0.5 * (entity_count / max(1, block.num_tokens))

        return score

    def select_victims(self, count: int) -> List[int]:
        """
        Select up to `count` blocks to evict. Returns block_ids sorted
        by score (lowest first = best eviction candidates).
        """
        if not self.gpu_blocks:
            return []

        available = self.gpu_blocks - self.pinned_blocks
        if not available:
            return []

        # Fast path: all-filler blocks (no sink/entity/recent positions)
        filler_blocks = [
            bid for bid in available
            if self._is_all_filler(bid)
        ]
        if len(filler_blocks) >= count:
            filler_blocks.sort(key=lambda b: self.freq_sketch.estimate(b))
            self.stats["filler_evictions"] += min(count, len(filler_blocks))
            return filler_blocks[:count]

        # Sample and score
        sample_size = min(48, len(available))
        candidates = random.sample(list(available), sample_size)

        scored = [(bid, self.score_block(bid)) for bid in candidates]
        scored.sort(key=lambda x: x[1])

        victims = [bid for bid, _ in scored[:count]]
        self.stats["evictions"] += len(victims)
        return victims

    # ---- Block lifecycle ----

    def evict_block(self, block_id: int):
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)

    def pin_block(self, block_id: int):
        self.pinned_blocks.add(block_id)

    def unpin_block(self, block_id: int):
        self.pinned_blocks.discard(block_id)

    def _free_block(self, block_id: int):
        self.blocks.pop(block_id, None)
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)

    # ---- Internal helpers ----

    def _classify_position(self, position: int, seq_len: int, attention: float) -> PositionClass:
        if position < self.sink_tokens:
            return PositionClass.SINK
        if seq_len > 0 and position >= seq_len - self.recent_window:
            return PositionClass.RECENT
        if attention > self.entity_threshold:
            return PositionClass.ENTITY
        return PositionClass.FILLER

    def _block_importance(self, block: BlockState, seq_len: int) -> float:
        """Classify each position in the block, return weighted importance [0, 1]."""
        if not block.token_attention:
            return 0.0
        weights = {
            PositionClass.SINK: 1.0,
            PositionClass.ENTITY: 0.8,
            PositionClass.RECENT: 0.6,
            PositionClass.FILLER: 0.1,
        }
        total = 0.0
        for pos, attn in block.token_attention.items():
            cls = self._classify_position(pos, seq_len, attn)
            total += weights[cls]
        return total / len(block.token_attention)

    def _is_all_filler(self, block_id: int) -> bool:
        """Check if every position in the block is FILLER."""
        block = self.blocks.get(block_id)
        if not block or not block.token_attention:
            return False
        seq = self.sequences.get(block.sequence_id)
        seq_len = len(seq.block_ids) * self.block_size if seq else 0
        for pos, attn in block.token_attention.items():
            cls = self._classify_position(pos, seq_len, attn)
            if cls != PositionClass.FILLER:
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "total_blocks": len(self.blocks),
            "gpu_blocks": len(self.gpu_blocks),
            "pinned_blocks": len(self.pinned_blocks),
            "active_sequences": len(self.sequences),
            "step": self._step,
        }
