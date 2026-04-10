"""
PCAM-side KV-cache policy — verbatim port of the CTM+ reference.

Status
------
Active port. This module is a faithful, bit-parity Python port of
``CTM_plus/KVPolicy/kv_policy/attention_evictor.py`` per ADR-0001.
Every scoring decision, every sketch increment, every victim set
produced by this module is observationally equivalent to the reference
on an identically-seeded trace. The conformance harness at
``simulator/pcam/tests/test_sketch_conformance.py`` and
``simulator/pcam/tests/test_attention_evictor_parity.py`` asserts
this parity on every commit.

Contract
--------
- **ADR:** ``docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md``
  locks the four-signal phase-aware scoring model and the Count-Min
  frequency sketch as canonical. Any behavioral change must land in the
  ADR first.

- **Reference / oracle:** ``CTM_plus/KVPolicy/kv_policy/attention_evictor.py``.
  This module is a copy, not an import — the conformance harness exists
  specifically to detect drift between the two files, and importing at
  runtime would make the detection trivially circular.

- **RTL counterpart:** ``simulator/pcam/rtl/core/freq_sketch.sv`` is the
  SystemVerilog translation of ``FrequencySketch`` below. The RTL must
  be observationally equivalent to this module (same seeds, same
  saturation, same halving trigger), and its acceptance is asserted via
  the tb_pcam_top sketch tests.

Scoring model (four-signal, phase-aware)
----------------------------------------
    score = w.recency   * exp(-0.01 * (now - last_access))
          + w.frequency * min(1.0, freq_sketch.estimate(bid) / 10.0)
          + w.attention * block.attention_ema
          + w.position  * classify_block_importance(is_sink, ema, threshold)

    entity bonus: +0.5 when (not is_sink) and (attention_ema > adaptive_threshold)

    PHASE_WEIGHTS:
      PREFILL: recency=0.15  frequency=0.20  attention=0.35  position=0.30
      DECODE:  recency=0.30  frequency=0.20  attention=0.30  position=0.20

Frequency sketch: 4 rows × power-of-two width (floor 64) × 4-bit
saturating counters. Four fixed seed hashes
(0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138). Event-driven halving
at ``capacity * 10`` increments. Ported verbatim from the reference.

Terms deferred by ADR-0001 — do NOT re-introduce without amending the ADR:

- ``reuse`` scoring term (dropped; scan resistance comes from the sketch
  and the entity bonus)
- ``sequence_priority`` scoring term (dropped; phase captures the
  intended variation)
- ``PositionClass.RECENT`` window protection (declared in the reference
  but not exercised; the port matches the reference by also not
  exercising it)

Re-exports
----------
``InferencePhase`` and ``PositionClass`` are re-exported from the
reference so that consumers can import the whole contract from one
module path: ``from simulator.pcam.kv_policy import KVCachePolicy,
FrequencySketch, InferencePhase, PhaseWeights, PHASE_WEIGHTS``.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set

# ---------------------------------------------------------------------------
# Reference package wiring. CTM_plus/KVPolicy/kv_policy is a setup.py
# package imported as `kv_policy` (not `CTM_plus.KVPolicy.kv_policy`); we
# add its parent to sys.path so enum re-exports resolve without requiring
# a pip install.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_KV_POLICY_PARENT = _REPO_ROOT / "CTM_plus" / "KVPolicy"
if str(_KV_POLICY_PARENT) not in sys.path:
    sys.path.insert(0, str(_KV_POLICY_PARENT))

from kv_policy.attention_evictor import (  # noqa: E402
    InferencePhase,
    PositionClass,
)

__all__ = [
    "FrequencySketch",
    "KVCachePolicy",
    "InferencePhase",
    "PositionClass",
]


# ===========================================================================
# FrequencySketch — ported from the canonical CTM+ reference.
#
# Source: CTM_plus/KVPolicy/kv_policy/attention_evictor.py:69-112
# Contract: docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md
#
# Any intentional divergence from the reference is a contract change and
# must be reflected in the ADR first. The conformance harness at
# simulator/pcam/tests/test_sketch_conformance.py asserts bit-for-bit
# parity with the reference on a fixed RNG seed.
# ===========================================================================


class FrequencySketch:
    """
    4-bit Count-Min Sketch for O(1) approximate frequency tracking.

    Periodically halves all counters to age out stale frequencies. The
    four fixed seed hashes, the 4-bit counter saturation, the power-of-two
    width with a floor of 64, and the event-driven halving at
    ``capacity * 10`` increments are all load-bearing for parity with the
    reference. Do not tune them.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.width = self._next_pow2(max(64, capacity))
        self.depth = 4
        self.table = [[0] * self.width for _ in range(self.depth)]
        self.size = 0
        self.reset_threshold = capacity * 10
        self._seeds = [0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138]

    @staticmethod
    def _next_pow2(n: int) -> int:
        n -= 1
        n |= n >> 1
        n |= n >> 2
        n |= n >> 4
        n |= n >> 8
        n |= n >> 16
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

    def _halve(self) -> None:
        for row in self.table:
            for j in range(len(row)):
                row[j] >>= 1
        self.size >>= 1


# ===========================================================================
# Block / sequence state, phase weights, and classification helpers —
# ported from CTM_plus/KVPolicy/kv_policy/attention_evictor.py per ADR-0001.
# ===========================================================================


@dataclass
class BlockState:
    """Per-block metadata. Pure block-level aggregates — no per-position storage."""
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


@dataclass(frozen=True)
class PhaseWeights:
    recency: float
    frequency: float
    attention: float
    position: float


# Four-signal phase-aware scoring weights. These are the canonical values
# locked by ADR-0001; do not retune without an ADR amendment.
PHASE_WEIGHTS = {
    InferencePhase.PREFILL: PhaseWeights(0.15, 0.20, 0.35, 0.30),
    InferencePhase.DECODE:  PhaseWeights(0.30, 0.20, 0.30, 0.20),
}


def compute_adaptive_threshold(
    attn_sum: float,
    attn_count: int,
    k: float = 2.0,
    floor: float = 0.02,
) -> float:
    """
    Adaptive entity threshold that scales with sequence length. Returns
    ``global_mean * k`` once enough samples exist, otherwise ``floor``.
    Ported verbatim from attention_evictor.py:34-45.
    """
    if attn_count >= 10:
        return (attn_sum / attn_count) * k
    return floor


def classify_block_importance(
    is_sink: bool,
    attention: float,
    threshold: float,
) -> float:
    """
    Classify a block's importance for eviction scoring.

    Returns 1.0 for sinks, 0.8 for entities (above adaptive threshold),
    0.1 for fillers. Ported verbatim from attention_evictor.py:48-62.
    """
    if is_sink:
        return 1.0
    if attention > threshold:
        return 0.8
    return 0.1


# ===========================================================================
# KVCachePolicy — ported from the canonical CTM+ reference.
#
# Source: CTM_plus/KVPolicy/kv_policy/attention_evictor.py:180-505
# Contract: docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md
# Harness:  simulator/pcam/tests/test_attention_evictor_parity.py
#
# The reference is the oracle. Any intentional behavioral divergence from
# attention_evictor.py is a contract change and must land in ADR-0001
# before it lands here.
# ===========================================================================


class KVCachePolicy:
    """
    Attention-aware KV-cache eviction policy for LLM inference.

    Two entry points drive victim selection:
      - ``score_block(block_id) -> float``   (lower = evict first)
      - ``select_victims(count) -> list``    (returns block_ids to evict)

    Per-block state is maintained incrementally via block-level aggregates
    (``attention_sum``, ``attention_ema``, ``token_count``). There is no
    per-token or per-position storage; scores are always current and O(1).
    """

    def __init__(
        self,
        max_blocks: int,
        block_size: int = 16,
        sink_tokens: int = 4,
        recent_window: int = 256,
        entity_attention_threshold: float = 0.02,
        attention_ema_alpha: float = 0.1,
    ) -> None:
        self.max_blocks = max_blocks
        self.block_size = block_size
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self.entity_attention_threshold = entity_attention_threshold
        self.attention_ema_alpha = attention_ema_alpha

        self.freq_sketch = FrequencySketch(max_blocks * 4)
        self._rng: random.Random = random.Random(42)

        self.blocks: Dict[int, BlockState] = {}
        self.sequences: Dict[int, SequenceState] = {}
        self.gpu_blocks: Set[int] = set()
        self.pinned_blocks: Set[int] = set()

        self._step = 0
        self._ema_sum = 0.0   # running sum of block.attention_ema values
        self._ema_count = 0   # number of attention updates
        self._entity_k = 2.0  # entity = ema > global_mean * k

        self.stats = {
            "evictions": 0,
            "filler_evictions": 0,
        }

    # ---- RNG contract -------------------------------------------------------

    def set_rng(self, rng: random.Random) -> None:
        """Set the RNG instance for reproducible victim selection."""
        self._rng = rng

    # ---- Sequence lifecycle -------------------------------------------------

    def register_sequence(self, seq_id: int) -> None:
        self.sequences[seq_id] = SequenceState(sequence_id=seq_id)

    def set_phase(self, seq_id: int, phase: InferencePhase) -> None:
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

    # ---- Block admission and attention events -------------------------------

    def ensure_block(
        self,
        block_id: int,
        sequence_id: int,
        positions: List[int],
    ) -> None:
        """
        Lightweight block registration. Creates block metadata without
        recording any attention — used on admission. Idempotent: re-calls
        with an existing block_id are a no-op and do not increment _step.
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

    def on_block_attention(
        self,
        block_id: int,
        attention_sum: float,
        sequence_id: int,
        seq_len: int = 0,
    ) -> None:
        """
        Record attention for an entire block in one call. Accepts a
        pre-aggregated attention_sum. O(1) per call.
        """
        self._step += 1

        block = self.blocks.get(block_id)
        if block is None:
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
            )
            self.blocks[block_id] = block

        block.attention_sum += attention_sum
        block.attention_ema = (
            self.attention_ema_alpha * attention_sum
            + (1 - self.attention_ema_alpha) * block.attention_ema
        )
        block.access_count += 1
        block.last_access_step = self._step

        self._ema_sum += block.attention_ema
        self._ema_count += 1

        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)
        self.gpu_blocks.add(block_id)

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
        Record an attention event for a single token. Aggregates into
        block-level sums; ``token_id`` is accepted for API compatibility
        with the reference and is not otherwise consumed.
        """
        self._step += 1

        block = self.blocks.get(block_id)
        if block is None:
            block = BlockState(
                block_id=block_id,
                sequence_id=sequence_id,
                created_step=self._step,
            )
            self.blocks[block_id] = block

        block.attention_sum += attention_weight
        block.attention_ema = (
            self.attention_ema_alpha * attention_weight
            + (1 - self.attention_ema_alpha) * block.attention_ema
        )
        block.token_count += 1
        block.access_count += 1
        block.last_access_step = self._step

        self._ema_sum += block.attention_ema
        self._ema_count += 1

        if position < self.sink_tokens:
            block.is_sink = True
            self.pinned_blocks.add(block_id)

        if sequence_id in self.sequences:
            self.sequences[sequence_id].block_ids.add(block_id)

        self.freq_sketch.increment(block_id)
        self.gpu_blocks.add(block_id)

    # ---- Scoring ------------------------------------------------------------

    def score_block(self, block_id: int) -> float:
        """
        Score a single block for eviction. Lower = evict first. O(1) —
        uses only block-level aggregates. Unknown blocks score -1.0 so
        they sink to the bottom of any victim list.
        """
        block = self.blocks.get(block_id)
        if not block:
            return -1.0

        seq = self.sequences.get(block.sequence_id)
        phase = seq.phase if seq else InferencePhase.DECODE

        w = PHASE_WEIGHTS.get(phase)
        if not w:
            return -1.0

        # Signal 1: recency — exponential decay on step distance.
        recency = math.exp(-0.01 * (self._step - block.last_access_step))

        # Signal 2: frequency — Count-Min sketch estimate, normalized.
        frequency = min(1.0, self.freq_sketch.estimate(block_id) / 10.0)

        # Signal 3: attention — EMA of attention mass.
        attention = block.attention_ema

        # Signal 4: position importance — sink/entity/filler classification.
        importance = self._classify_block(block)

        score = (
            w.recency * recency
            + w.frequency * frequency
            + w.attention * attention
            + w.position * importance
        )

        # Entity bonus: protect high-attention non-sink blocks.
        if not block.is_sink and block.attention_ema > self._adaptive_threshold:
            score += 0.5

        return score

    # ---- Block lifecycle ----------------------------------------------------

    def evict_block(self, block_id: int) -> None:
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)

    def pin_block(self, block_id: int) -> None:
        self.pinned_blocks.add(block_id)

    def unpin_block(self, block_id: int) -> None:
        self.pinned_blocks.discard(block_id)

    def _free_block(self, block_id: int) -> None:
        self.blocks.pop(block_id, None)
        self.gpu_blocks.discard(block_id)
        self.pinned_blocks.discard(block_id)

    # ---- Internal helpers ---------------------------------------------------

    @property
    def _adaptive_threshold(self) -> float:
        """Adaptive entity threshold that scales with sequence length."""
        return compute_adaptive_threshold(
            self._ema_sum,
            self._ema_count,
            k=self._entity_k,
            floor=self.entity_attention_threshold,
        )

    def _classify_block(self, block: BlockState) -> float:
        """Classify block as sink/entity/filler. Returns importance in [0, 1]."""
        return classify_block_importance(
            block.is_sink,
            block.attention_ema,
            self._adaptive_threshold,
        )

    def _is_all_filler(self, block_id: int) -> bool:
        """Check whether a block qualifies as filler (not sink, low attention)."""
        block = self.blocks.get(block_id)
        if not block:
            return False
        return (
            classify_block_importance(
                block.is_sink,
                block.attention_ema,
                self._adaptive_threshold,
            )
            < 0.5
        )

    # ---- Observability ------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "total_blocks": len(self.blocks),
            "gpu_blocks": len(self.gpu_blocks),
            "pinned_blocks": len(self.pinned_blocks),
            "active_sequences": len(self.sequences),
            "step": self._step,
        }

    # ---- Victim selection ---------------------------------------------------

    def select_victims(self, count: int) -> List[int]:
        """
        Select up to ``count`` blocks to evict. Returns block_ids sorted
        by score (lowest first = best eviction candidates).

        Two codepaths, exactly matching the reference at
        attention_evictor.py:419-450:

        1. Filler fast path — if the set of all-filler blocks in
           ``available`` is large enough to satisfy the request, sort
           them by ``freq_sketch.estimate()`` ascending and return the
           lowest. This path is deterministic and does not consume the
           RNG.

        2. Sampled path — otherwise draw ``min(48, len(available))``
           candidates via ``self._rng.sample``, score them via
           ``score_block``, stable-sort by score ascending, and return
           the lowest ``count`` block_ids.

        Pinned (sink) blocks are excluded from ``available`` before
        either codepath runs; they are never scored, sampled, or
        considered.
        """
        if not self.gpu_blocks:
            return []

        available = self.gpu_blocks - self.pinned_blocks
        if not available:
            return []

        # Fast path: enough all-filler blocks to satisfy the request.
        filler_blocks = [bid for bid in available if self._is_all_filler(bid)]
        if len(filler_blocks) >= count:
            filler_blocks.sort(key=lambda b: self.freq_sketch.estimate(b))
            self.stats["filler_evictions"] += min(count, len(filler_blocks))
            return filler_blocks[:count]

        # Sampled path.
        sample_size = min(48, len(available))
        candidates = self._rng.sample(list(available), sample_size)

        scored = [(bid, self.score_block(bid)) for bid in candidates]
        scored.sort(key=lambda x: x[1])

        victims = [bid for bid, _ in scored[:count]]
        self.stats["evictions"] += len(victims)
        return victims
