"""
KV cache eviction policy for LLM inference.

This module provides scoring logic for KV cache block eviction decisions.
It does NOT manage memory, I/O, or block allocation — those are handled
by the serving engine (e.g. vLLM's BlockSpaceManager).

Signals used for scoring:
  1. Attention — EMA of attention weights at block level
  2. Block importance — sink/entity/filler classification
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
# Shared Classification Utilities
# =============================================================================

def compute_adaptive_threshold(attn_sum: float, attn_count: int,
                               k: float = 2.0, floor: float = 0.02) -> float:
    """
    Compute adaptive entity threshold from running attention statistics.

    Returns global_mean * k once enough samples exist, otherwise falls back
    to `floor`. This scales correctly across sequence lengths: long sequences
    produce smaller per-block attention values, so the threshold scales down.
    """
    if attn_count >= 10:
        return (attn_sum / attn_count) * k
    return floor


def classify_block_importance(is_sink: bool, attention: float,
                              threshold: float) -> float:
    """
    Classify a block's importance for eviction scoring.

    Returns:
        1.0 for sink blocks (never evict),
        0.8 for entity blocks (high attention, protect),
        0.1 for filler blocks (low attention, evict first).
    """
    if is_sink:
        return 1.0
    if attention > threshold:
        return 0.8
    return 0.1


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
    Per-block metadata. Pure block-level aggregates — no per-position storage.
    """
    block_id: int
    sequence_id: int
    attention_sum: float = 0.0
    attention_ema: float = 0.0
    token_count: int = 0
    created_step: int = 0
    last_access_step: int = 0
    access_count: int = 0
    is_sink: bool = False


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

    Tracks per-block state incrementally via block-level aggregates
    (attention_sum, attention_ema, token_count). No per-token or
    per-position storage — scores are always current and O(1).
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
        self._ema_sum = 0.0       # running sum of block.attention_ema values
        self._ema_count = 0       # number of attention updates
        self._entity_k = 2.0     # entity = ema > global_mean * k

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

        Aggregates into block-level sums. The token_id and position
        parameters are accepted for API compatibility.
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

        # Block-level aggregates
        block.attention_sum += attention_weight
        block.attention_ema = (
            self.ema_alpha * attention_weight +
            (1 - self.ema_alpha) * block.attention_ema
        )
        block.token_count += 1
        block.access_count += 1
        block.last_access_step = self._step

        # Track global attention mean for adaptive entity threshold
        self._ema_sum += block.attention_ema
        self._ema_count += 1

        # Pin sinks
        if position < self.sink_tokens:
            block.is_sink = True
            self.pinned_blocks.add(block_id)

        # Sequence tracking
        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)

        self.gpu_blocks.add(block_id)

    def on_block_attention(
        self,
        block_id: int,
        attention_sum: float,
        sequence_id: int,
        seq_len: int = 0,
    ):
        """
        Record attention for an entire block in one call.

        Accepts pre-aggregated attention_sum (float). O(1) per call.
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

        # Block-level aggregates
        block.attention_sum += attention_sum
        block.attention_ema = (
            self.ema_alpha * attention_sum +
            (1 - self.ema_alpha) * block.attention_ema
        )
        block.access_count += 1
        block.last_access_step = self._step

        # Track global attention mean for adaptive entity threshold
        self._ema_sum += block.attention_ema
        self._ema_count += 1

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
            is_sink = any(pos < self.sink_tokens for pos in positions)
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
                token_count=len(positions),
                is_sink=is_sink,
            )
            self.blocks[block_id] = block

            if is_sink:
                self.pinned_blocks.add(block_id)

            if sequence_id in self.sequences:
                self.sequences[sequence_id].block_ids.add(block_id)

            self.gpu_blocks.add(block_id)

    # ---- Scoring interface ----

    def score_block(self, block_id: int) -> float:
        """
        Score a single block for eviction. Lower = evict first.
        O(1) — uses only block-level aggregates.
        """
        block = self.blocks.get(block_id)
        if not block:
            return -1.0

        seq = self.sequences.get(block.sequence_id)
        phase = seq.phase if seq else InferencePhase.DECODE

        w = PHASE_WEIGHTS.get(phase)
        if not w:
            return -1.0

        # Signal 1: Recency — exponential decay
        recency = math.exp(-0.01 * (self._step - block.last_access_step))

        # Signal 2: Frequency — Count-Min Sketch
        frequency = min(1.0, self.freq_sketch.estimate(block_id) / 10.0)

        # Signal 3: Attention — EMA of attention weights
        attention = block.attention_ema

        # Signal 4: Block importance — sink/entity/filler classification
        importance = self._classify_block(block)

        score = (
            w.recency * recency +
            w.frequency * frequency +
            w.attention * attention +
            w.position * importance
        )

        # Entity bonus — protect high-attention non-sink blocks
        if not block.is_sink and block.attention_ema > self._adaptive_threshold:
            score += 0.5

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

    @property
    def _adaptive_threshold(self) -> float:
        """Adaptive entity threshold that scales with sequence length."""
        return compute_adaptive_threshold(
            self._ema_sum, self._ema_count,
            k=self._entity_k, floor=self.entity_threshold,
        )

    def _classify_block(self, block: BlockState) -> float:
        """
        Classify block as sink/entity/filler. Returns importance [0, 1].
        O(1) — no per-position iteration.
        """
        return classify_block_importance(
            block.is_sink, block.attention_ema, self._adaptive_threshold,
        )

    def _is_all_filler(self, block_id: int) -> bool:
        """Check if block is filler (not sink, low attention)."""
        block = self.blocks.get(block_id)
        if not block:
            return False
        return classify_block_importance(
            block.is_sink, block.attention_ema, self._adaptive_threshold,
        ) < 0.5

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "total_blocks": len(self.blocks),
            "gpu_blocks": len(self.gpu_blocks),
            "pinned_blocks": len(self.pinned_blocks),
            "active_sequences": len(self.sequences),
            "step": self._step,
        }
