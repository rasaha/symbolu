"""
KV cache eviction policy for LLM inference.

This module provides scoring logic for KV cache block eviction decisions.
It does NOT manage memory, I/O, or block allocation — those are handled
by the serving engine (e.g. vLLM's BlockSpaceManager).

LLM-specific signals used for scoring:
  1. Attention value — cumulative attention received by tokens in the block
  2. Position importance — sink/entity/recent/filler classification
  3. Frequency — Count-Min Sketch for O(1) approximate block access count
  4. Recency — exponential decay of time since last access
  5. Sequence priority — user-set priority weighted by invested compute

Phase-aware: scoring weights differ between prefill and decode phases.
Scan-resistant: S3-FIFO admission prevents prefill floods from evicting
useful decode blocks.

Integration point: vLLM's Evictor abstract base class.
    class Evictor(ABC):
        def evict(self) -> Tuple[PhysicalTokenBlock, ...]: ...

Not thread-safe. Callers must synchronize externally.
"""

import math
import random
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any


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
    COMPLETE = auto()


# =============================================================================
# Per-Token and Per-Block State
# =============================================================================

@dataclass
class TokenState:
    position: int
    sequence_id: int
    block_id: int
    created_step: int = 0
    last_access_step: int = 0
    cumulative_attention: float = 0.0
    position_class: PositionClass = PositionClass.FILLER


@dataclass
class BlockScore:
    """Cached aggregate scores for a KV block."""
    block_id: int
    avg_attention: float = 0.0
    sink_count: int = 0
    entity_count: int = 0
    recent_count: int = 0
    filler_count: int = 0
    total_tokens: int = 0
    frequency: int = 0

    @property
    def importance(self) -> float:
        if self.total_tokens == 0:
            return 0.0
        weighted = (
            1.0 * self.sink_count +
            0.8 * self.entity_count +
            0.6 * self.recent_count +
            0.1 * self.filler_count
        )
        return weighted / self.total_tokens


@dataclass
class SequenceState:
    sequence_id: int
    phase: InferencePhase = InferencePhase.PREFILL
    priority: float = 1.0
    total_tokens: int = 0
    generated_tokens: int = 0
    max_tokens: int = 4096
    block_ids: Set[int] = field(default_factory=set)

    @property
    def invested_compute(self) -> float:
        return min(1.0, self.total_tokens / 4096.0)


# =============================================================================
# S3-FIFO Queue (scan-resistant admission)
# =============================================================================

class S3FIFOQueue:
    """
    Three-queue FIFO inspired by S3-FIFO (SOSP'23).
    - Small (10%): new blocks enter here
    - Main (90%): promoted on second access
    - Ghost: metadata-only, tracks recently evicted

    One-hit-wonders evict from Small without polluting Main.
    """

    def __init__(self, capacity: int, small_ratio: float = 0.10):
        self.small_cap = max(1, int(capacity * small_ratio))
        self.main_cap = capacity - self.small_cap
        self.ghost_cap = capacity

        self.small: OrderedDict[int, bool] = OrderedDict()
        self.main: OrderedDict[int, bool] = OrderedDict()
        self.ghost: OrderedDict[int, float] = OrderedDict()
        self._loc: Dict[int, str] = {}

    def admit(self, block_id: int, now: float) -> Optional[int]:
        if block_id in self.ghost:
            del self.ghost[block_id]
            return self._to_main(block_id, now)
        return self._to_small(block_id, now)

    def access(self, block_id: int) -> None:
        if block_id in self.small:
            self.small[block_id] = True
        elif block_id in self.main:
            self.main[block_id] = True

    def contains(self, block_id: int) -> bool:
        return block_id in self._loc

    def remove(self, block_id: int) -> None:
        self.small.pop(block_id, None)
        self.main.pop(block_id, None)
        self._loc.pop(block_id, None)
        self.ghost.pop(block_id, None)

    def _to_small(self, block_id: int, now: float) -> Optional[int]:
        evicted = None
        while len(self.small) >= self.small_cap:
            evicted = self._evict_small(now)
        self.small[block_id] = False
        self._loc[block_id] = 'small'
        return evicted

    def _to_main(self, block_id: int, now: float) -> Optional[int]:
        evicted = None
        while len(self.main) >= self.main_cap:
            evicted = self._evict_main(now)
        self.main[block_id] = False
        self._loc[block_id] = 'main'
        return evicted

    def _evict_small(self, now: float) -> Optional[int]:
        while self.small:
            bid, visited = self.small.popitem(last=False)
            del self._loc[bid]
            if visited:
                self._to_main(bid, now)
                continue
            self._to_ghost(bid, now)
            return bid
        return None

    def _evict_main(self, now: float) -> Optional[int]:
        for _ in range(len(self.main)):
            if not self.main:
                return None
            bid, visited = self.main.popitem(last=False)
            if visited:
                self.main[bid] = False
                continue
            del self._loc[bid]
            self._to_ghost(bid, now)
            return bid
        return None

    def _to_ghost(self, block_id: int, now: float) -> None:
        if len(self.ghost) >= self.ghost_cap:
            self.ghost.popitem(last=False)
        self.ghost[block_id] = now

    @property
    def size(self) -> int:
        return len(self.small) + len(self.main)


# =============================================================================
# Phase-Aware Scoring Weights
# =============================================================================

@dataclass(frozen=True)
class PhaseWeights:
    recency: float
    frequency: float
    attention: float
    position: float
    seq_priority: float


PHASE_WEIGHTS = {
    InferencePhase.PREFILL: PhaseWeights(0.15, 0.15, 0.30, 0.25, 0.15),
    InferencePhase.DECODE:  PhaseWeights(0.25, 0.20, 0.25, 0.15, 0.15),
    InferencePhase.COMPLETE: PhaseWeights(0, 0, 0, 0, 0),
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

    This class tracks token-level attention and computes block-level
    eviction scores. It does NOT manage actual block memory.
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
        self.fifo = S3FIFOQueue(max_blocks)

        self.tokens: Dict[int, TokenState] = {}
        self.blocks: Dict[int, Set[int]] = {}       # block_id -> {token_ids}
        self.block_scores: Dict[int, BlockScore] = {}
        self.sequences: Dict[int, SequenceState] = {}
        self.gpu_blocks: Set[int] = set()
        self.pinned_blocks: Set[int] = set()

        self._step = 0
        self._score_interval = 100

        self.stats = {
            "evictions": 0,
            "sink_protections": 0,
            "filler_evictions": 0,
        }

    # ---- Sequence lifecycle ----

    def register_sequence(self, seq_id: int, priority: float = 1.0, max_tokens: int = 4096):
        self.sequences[seq_id] = SequenceState(
            sequence_id=seq_id, priority=priority, max_tokens=max_tokens,
        )

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
        self._step += 1

        if token_id in self.tokens:
            ts = self.tokens[token_id]
            ts.last_access_step = self._step
            ts.cumulative_attention = (
                self.ema_alpha * attention_weight +
                (1 - self.ema_alpha) * ts.cumulative_attention
            )
        else:
            ts = TokenState(
                position=position, sequence_id=sequence_id, block_id=block_id,
                created_step=self._step, last_access_step=self._step,
                cumulative_attention=attention_weight,
            )
            self.tokens[token_id] = ts

        # Classify position
        ts.position_class = self._classify(position, seq_len, ts.cumulative_attention)

        # Pin sinks
        if ts.position_class == PositionClass.SINK:
            self.pinned_blocks.add(block_id)

        # Track block membership
        if block_id not in self.blocks:
            self.blocks[block_id] = set()
        self.blocks[block_id].add(token_id)

        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)

        if self.fifo.contains(block_id):
            self.fifo.access(block_id)
        else:
            self.fifo.admit(block_id, time.monotonic())

        self.gpu_blocks.add(block_id)

    # ---- Scoring interface ----

    def score_block(self, block_id: int) -> float:
        """
        Score a single block for eviction. Lower = evict first.
        """
        phase = self._block_phase(block_id)
        if phase == InferencePhase.COMPLETE:
            return -1.0

        w = PHASE_WEIGHTS[phase]
        bs = self.block_scores.get(block_id)

        # Recency
        recency = 0.0
        tids = self.blocks.get(block_id, set())
        if tids:
            max_step = max(
                (self.tokens[t].last_access_step for t in tids if t in self.tokens),
                default=0,
            )
            recency = math.exp(-0.01 * (self._step - max_step))

        # Frequency
        frequency = min(1.0, self.freq_sketch.estimate(block_id) / 10.0)

        # Attention value
        attention = bs.avg_attention if bs else 0.0

        # Position importance
        position = bs.importance if bs else 0.0

        # Sequence priority
        seq_priority = self._block_priority(block_id)

        score = (
            w.recency * recency +
            w.frequency * frequency +
            w.attention * attention +
            w.position * position +
            w.seq_priority * seq_priority
        )

        # Hard protection for sink-containing blocks
        if bs and bs.sink_count > 0:
            score += 10.0
            self.stats["sink_protections"] += 1
        if bs and bs.entity_count > 0:
            score += 0.5 * (bs.entity_count / max(1, bs.total_tokens))

        return score

    def select_victims(self, count: int) -> List[int]:
        """
        Select up to `count` blocks to evict. Returns block_ids sorted
        by score (lowest first = best eviction candidates).
        """
        if not self.gpu_blocks:
            return []

        # Refresh scores if stale
        if self._step % self._score_interval == 0:
            self._recompute_scores()

        available = self.gpu_blocks - self.pinned_blocks
        if not available:
            return []

        # Fast path: filler-only blocks
        filler_blocks = [
            bid for bid in available
            if bid in self.block_scores
            and self.block_scores[bid].filler_count == self.block_scores[bid].total_tokens
            and self.block_scores[bid].total_tokens > 0
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
        if block_id in self.blocks:
            for tid in self.blocks[block_id]:
                self.tokens.pop(tid, None)
            del self.blocks[block_id]
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)
        self.block_scores.pop(block_id, None)
        self.fifo.remove(block_id)

    # ---- Internal helpers ----

    def _classify(self, position: int, seq_len: int, attention: float) -> PositionClass:
        if position < self.sink_tokens:
            return PositionClass.SINK
        if seq_len > 0 and position >= seq_len - self.recent_window:
            return PositionClass.RECENT
        if attention > self.entity_threshold:
            return PositionClass.ENTITY
        return PositionClass.FILLER

    def _block_phase(self, block_id: int) -> InferencePhase:
        tids = self.blocks.get(block_id, set())
        counts: Dict[InferencePhase, int] = {}
        for tid in tids:
            ts = self.tokens.get(tid)
            if ts and ts.sequence_id in self.sequences:
                p = self.sequences[ts.sequence_id].phase
                counts[p] = counts.get(p, 0) + 1
        return max(counts, key=counts.get) if counts else InferencePhase.DECODE

    def _block_priority(self, block_id: int) -> float:
        tids = self.blocks.get(block_id, set())
        priorities = []
        for tid in tids:
            ts = self.tokens.get(tid)
            if ts and ts.sequence_id in self.sequences:
                seq = self.sequences[ts.sequence_id]
                priorities.append(seq.priority * (0.5 + 0.5 * seq.invested_compute))
        return sum(priorities) / len(priorities) if priorities else 0.5

    def _recompute_scores(self):
        for block_id, token_ids in self.blocks.items():
            bs = BlockScore(block_id=block_id)
            total_attn = 0.0
            for tid in token_ids:
                ts = self.tokens.get(tid)
                if not ts:
                    continue
                bs.total_tokens += 1
                total_attn += ts.cumulative_attention
                if ts.position_class == PositionClass.SINK:
                    bs.sink_count += 1
                elif ts.position_class == PositionClass.ENTITY:
                    bs.entity_count += 1
                elif ts.position_class == PositionClass.RECENT:
                    bs.recent_count += 1
                else:
                    bs.filler_count += 1
            bs.avg_attention = total_attn / bs.total_tokens if bs.total_tokens > 0 else 0.0
            bs.frequency = self.freq_sketch.estimate(block_id)
            self.block_scores[block_id] = bs

    def get_stats(self) -> Dict[str, Any]:
        position_dist = {"sink": 0, "recent": 0, "entity": 0, "filler": 0}
        for ts in self.tokens.values():
            position_dist[ts.position_class.name.lower()] += 1
        return {
            **self.stats,
            "total_tokens": len(self.tokens),
            "gpu_blocks": len(self.gpu_blocks),
            "pinned_blocks": len(self.pinned_blocks),
            "active_sequences": len(self.sequences),
            "position_distribution": position_dist,
            "step": self._step,
        }
