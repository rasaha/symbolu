"""
KV Cache Eviction Policy Simulator for LLM Inference.

Simulates KV cache behavior during LLM inference to evaluate eviction
policies. Models realistic access patterns: sequential prefill bursts,
attention-weighted decode accesses, and continuous batching of multiple
sequences.

This is a research tool. No GPU logic, no memory allocators, no vLLM imports.

Simulation model:
    Prefill:  Sequence writes KV blocks sequentially. No reuse.
    Decode:   Each new token attends to all prior tokens.
              Attention follows sink+recent distribution:
                ~15% on first few positions (attention sinks)
                ~55% on recent window
                ~30% spread across middle positions
              Block access frequency reflects summed attention weights.
    Eviction: When KV cache exceeds memory budget, policy selects victims.

Policies:
    LRU        — evict least recently accessed block
    FIFO       — evict oldest admitted block
    Random     — evict uniformly at random
    CTM+       — evict lowest-scoring block (attention + position + recency)
    KV_POLICY  — adapter for KVCachePolicy from the KVPolicy module
"""

import math
import random
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple


# =============================================================================
# Core Types
# =============================================================================

class BlockType(Enum):
    SINK = auto()      # First few positions — attention sinks, almost never evict
    ENTITY = auto()    # High cumulative attention — important context
    FILLER = auto()    # Low attention — safe to evict
    RECENT = auto()    # Recent window — transiently protected

class Phase(Enum):
    PREFILL = auto()
    DECODE = auto()

class PolicyType(Enum):
    LRU = "lru"
    FIFO = "fifo"
    RANDOM = "random"
    CTM_PLUS = "ctm_plus"
    KV_POLICY = "kv_policy"


# =============================================================================
# KV Block State
# =============================================================================

@dataclass
class KVBlock:
    """State of a single KV cache block."""
    block_id: int
    sequence_id: int
    token_positions: List[int]          # token positions stored in this block
    created_step: int = 0
    last_access_step: int = 0
    access_count: int = 0
    cumulative_attention: float = 0.0   # sum of attention weights received
    block_type: BlockType = BlockType.FILLER

    @property
    def avg_attention(self) -> float:
        return self.cumulative_attention / max(1, self.access_count)


@dataclass
class Sequence:
    """State of an active sequence being served."""
    sequence_id: int
    context_length: int                 # total tokens to process
    generated_tokens: int = 0           # tokens generated so far
    phase: Phase = Phase.PREFILL
    block_ids: List[int] = field(default_factory=list)
    prefill_done: bool = False
    evicted_positions: int = 0          # token positions lost to eviction


# =============================================================================
# Attention Pattern Generator
# =============================================================================

def sink_and_recent_attention(seq_len: int, sink_tokens: int = 4,
                               recent_window: int = 128) -> List[float]:
    """
    Generate attention distribution matching observed LLM patterns.
    ~15% on sinks, ~55% on recent window, ~30% on middle.
    """
    if seq_len == 0:
        return []
    weights = [0.0] * seq_len
    for i in range(seq_len):
        if i < sink_tokens:
            weights[i] = 0.15 / max(1, sink_tokens)
        elif i >= seq_len - recent_window and seq_len > sink_tokens:
            recency = (i - (seq_len - recent_window)) / max(1, recent_window)
            weights[i] = 0.55 * recency / max(1, min(recent_window, seq_len - sink_tokens))
        else:
            middle = max(1, seq_len - sink_tokens - min(recent_window, seq_len - sink_tokens))
            weights[i] = 0.30 / middle
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [1.0 / seq_len] * seq_len


def entity_focused_attention(seq_len: int, sink_tokens: int = 4,
                              recent_window: int = 128) -> List[float]:
    """
    Entity-focused pattern: a few positions receive very high attention.
    ~15% sinks, ~50% on ~5% of middle positions (entities), ~35% spread.
    """
    if seq_len == 0:
        return []
    weights = [0.0] * seq_len
    # Sinks
    for i in range(min(sink_tokens, seq_len)):
        weights[i] = 0.15 / max(1, sink_tokens)
    # Entity positions: ~5% of middle, evenly spaced
    middle_start = sink_tokens
    middle_end = seq_len
    middle_len = max(1, middle_end - middle_start)
    num_entities = max(1, middle_len // 20)  # ~5%
    entity_step = max(1, middle_len // (num_entities + 1))
    entity_positions = set()
    for e in range(1, num_entities + 1):
        pos = middle_start + e * entity_step
        if pos < seq_len:
            entity_positions.add(pos)
    # Distribute
    entity_share = 0.50 / max(1, len(entity_positions))
    filler_count = middle_len - len(entity_positions)
    filler_share = 0.35 / max(1, filler_count)
    for i in range(middle_start, seq_len):
        if i in entity_positions:
            weights[i] = entity_share
        else:
            weights[i] = filler_share
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [1.0 / seq_len] * seq_len


def uniform_attention(seq_len: int, sink_tokens: int = 4,
                       recent_window: int = 128) -> List[float]:
    """
    Uniform / diffuse pattern: attention spread nearly evenly.
    ~15% sinks, ~85% uniform across all other positions.
    """
    if seq_len == 0:
        return []
    weights = [0.0] * seq_len
    for i in range(min(sink_tokens, seq_len)):
        weights[i] = 0.15 / max(1, sink_tokens)
    rest = max(1, seq_len - sink_tokens)
    for i in range(sink_tokens, seq_len):
        weights[i] = 0.85 / rest
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [1.0 / seq_len] * seq_len


def mixed_multihead_attention(seq_len: int, sink_tokens: int = 4,
                                recent_window: int = 128) -> List[float]:
    """
    Mixed multi-head pattern: averages sink+recent, entity, and uniform
    to simulate different attention heads attending to different patterns.
    """
    if seq_len == 0:
        return []
    w1 = sink_and_recent_attention(seq_len, sink_tokens, recent_window)
    w2 = entity_focused_attention(seq_len, sink_tokens, recent_window)
    w3 = uniform_attention(seq_len, sink_tokens, recent_window)
    combined = [(a + b + c) / 3.0 for a, b, c in zip(w1, w2, w3)]
    total = sum(combined)
    return [w / total for w in combined] if total > 0 else [1.0 / seq_len] * seq_len


# =============================================================================
# Eviction Policies
# =============================================================================

class EvictionPolicy:
    """
    Base class for eviction policies.

    Lifecycle hooks (no-op by default):
      on_sequence_register / on_phase_change / on_sequence_complete
    Per-step hooks:
      on_block_attention — receives per-position attention weights.
        Default delegates to on_access for backward compatibility.
    """
    def on_access(self, block_id: int, block: KVBlock) -> None:
        pass
    def on_admit(self, block_id: int, block: KVBlock) -> None:
        pass
    def on_evict(self, block_id: int) -> None:
        pass
    def on_block_attention(
        self, block_id: int, block: KVBlock,
        position_attention: Dict[int, float],
        sequence_id: int, seq_len: int,
    ) -> None:
        """Called with per-position attention weights each decode step."""
        self.on_access(block_id, block)
    def on_sequence_register(self, seq_id: int, context_length: int) -> None:
        pass
    def on_phase_change(self, seq_id: int, phase: Phase) -> None:
        pass
    def on_sequence_complete(self, seq_id: int) -> None:
        pass
    def select_victim(self, blocks: Dict[int, KVBlock], pinned: Set[int]) -> Optional[int]:
        raise NotImplementedError


class LRUPolicy(EvictionPolicy):
    def __init__(self):
        self.order: OrderedDict[int, None] = OrderedDict()

    def on_access(self, block_id, block):
        if block_id in self.order:
            self.order.move_to_end(block_id)

    def on_admit(self, block_id, block):
        self.order[block_id] = None

    def on_evict(self, block_id):
        self.order.pop(block_id, None)

    def select_victim(self, blocks, pinned):
        for bid in self.order:
            if bid not in pinned:
                return bid
        return None


class FIFOPolicy(EvictionPolicy):
    def __init__(self):
        self.queue: deque[int] = deque()
        self._in_queue: set = set()

    def on_admit(self, block_id, block):
        if block_id not in self._in_queue:
            self.queue.append(block_id)
            self._in_queue.add(block_id)

    def on_evict(self, block_id):
        self._in_queue.discard(block_id)

    def select_victim(self, blocks, pinned):
        while self.queue:
            bid = self.queue.popleft()
            self._in_queue.discard(bid)
            if bid in blocks and bid not in pinned:
                return bid
        return None


class RandomPolicy(EvictionPolicy):
    def select_victim(self, blocks, pinned):
        candidates = [b for b in blocks if b not in pinned]
        return random.choice(candidates) if candidates else None


class AttentionAwarePolicy(EvictionPolicy):
    """
    CTM+ attention-aware eviction. Scores blocks by:
      - attention_weight (cumulative, normalized)     weight: 0.35
      - position_importance (sink/entity/recent)      weight: 0.30
      - recency (exponential decay)                   weight: 0.25
      - frequency (log-saturated access count)        weight: 0.10
    Higher score = more valuable = less likely to evict.
    Samples 48 candidates instead of scoring all blocks.
    """
    SAMPLE_SIZE = 48

    def __init__(self, sink_tokens: int = 4, recent_window: int = 128):
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self._step = 0
        self._max_attention = 1e-9  # running max for normalization

    def on_access(self, block_id, block):
        self._step = max(self._step, block.last_access_step)
        if block.cumulative_attention > self._max_attention:
            self._max_attention = block.cumulative_attention

    def select_victim(self, blocks, pinned):
        candidates = [b for b in blocks if b not in pinned]
        if not candidates:
            return None
        sample = random.sample(candidates, min(self.SAMPLE_SIZE, len(candidates)))
        return min(sample, key=lambda bid: self._score(blocks[bid]))

    def _score(self, block: KVBlock) -> float:
        # Attention value [0, 1]
        attn = block.cumulative_attention / self._max_attention if self._max_attention > 0 else 0.0

        # Position importance [0, 1]
        pos_scores = {
            BlockType.SINK: 1.0,
            BlockType.ENTITY: 0.8,
            BlockType.RECENT: 0.6,
            BlockType.FILLER: 0.1,
        }
        position = pos_scores[block.block_type]

        # Recency — exponential decay, half-life = 200 steps
        age = max(0, self._step - block.last_access_step)
        recency = math.exp(-0.00347 * age)  # ln(2)/200

        # Frequency — log-saturated
        frequency = min(1.0, math.log1p(block.access_count) / math.log1p(50))

        return 0.35 * attn + 0.30 * position + 0.25 * recency + 0.10 * frequency


class KVPolicyAdapter(EvictionPolicy):
    """
    Adapter that bridges KVCachePolicy (from KVPolicy module) to the
    simulator's EvictionPolicy interface.

    Forwards per-position attention from the simulator into KVCachePolicy's
    on_token_access(), and maps select_victim() to select_victims(count=1).
    """

    def __init__(self, kv_policy):
        """
        Args:
            kv_policy: A KVCachePolicy instance (from kv_policy.attention_evictor).
        """
        self._policy = kv_policy

    def on_admit(self, block_id, block):
        if hasattr(self._policy, 'ensure_block'):
            self._policy.ensure_block(block_id, block.sequence_id, block.token_positions)
        else:
            for pos in block.token_positions:
                self._policy.on_token_access(
                    token_id=pos, position=pos,
                    sequence_id=block.sequence_id,
                    block_id=block_id,
                    attention_weight=0.0, seq_len=0,
                )

    def on_block_attention(self, block_id, block, position_attention, sequence_id, seq_len):
        if hasattr(self._policy, 'on_block_attention'):
            self._policy.on_block_attention(
                block_id=block_id,
                position_attention=position_attention,
                sequence_id=sequence_id,
                seq_len=seq_len,
            )
        else:
            for pos, attn in position_attention.items():
                self._policy.on_token_access(
                    token_id=pos, position=pos,
                    sequence_id=sequence_id,
                    block_id=block_id,
                    attention_weight=attn,
                    seq_len=seq_len,
                )

    def on_evict(self, block_id):
        self._policy.evict_block(block_id)

    def on_sequence_register(self, seq_id, context_length):
        self._policy.register_sequence(seq_id)

    def on_phase_change(self, seq_id, phase):
        from CTM_plus.KVPolicy.kv_policy.attention_evictor import InferencePhase
        phase_map = {
            Phase.PREFILL: InferencePhase.PREFILL,
            Phase.DECODE: InferencePhase.DECODE,
        }
        self._policy.set_phase(seq_id, phase_map.get(phase, InferencePhase.DECODE))

    def on_sequence_complete(self, seq_id):
        self._policy.complete_sequence(seq_id)

    def select_victim(self, blocks, pinned):
        victims = self._policy.select_victims(count=1)
        return victims[0] if victims else None


def make_policy(policy_type: PolicyType, **kwargs) -> EvictionPolicy:
    if policy_type == PolicyType.LRU:
        return LRUPolicy()
    elif policy_type == PolicyType.FIFO:
        return FIFOPolicy()
    elif policy_type == PolicyType.RANDOM:
        return RandomPolicy()
    elif policy_type == PolicyType.CTM_PLUS:
        return AttentionAwarePolicy(**kwargs)
    elif policy_type == PolicyType.KV_POLICY:
        kv_policy = kwargs.pop("kv_policy", None)
        if kv_policy is None:
            raise ValueError("PolicyType.KV_POLICY requires kv_policy= argument")
        return KVPolicyAdapter(kv_policy)
    raise ValueError(f"Unknown policy: {policy_type}")


# =============================================================================
# KV Cache Simulator
# =============================================================================

class KVCacheSimulator:
    """
    Simulates KV cache under LLM inference workload.

    The simulator:
    1. Runs sequences through prefill (bulk KV writes) and decode (attention)
    2. Tracks per-block attention statistics
    3. Evicts blocks when memory budget is exceeded
    4. Collects metrics comparing policy quality
    """

    def __init__(
        self,
        max_blocks: int,
        block_size: int = 16,
        policy_type: PolicyType = PolicyType.CTM_PLUS,
        sink_tokens: int = 4,
        recent_window: int = 128,
        seed: int = 42,
        kv_policy=None,
        attention_fn=None,
    ):
        """
        Args:
            kv_policy: A KVCachePolicy instance. Required when
                policy_type=PolicyType.KV_POLICY; ignored otherwise.
            attention_fn: Callable(seq_len, sink_tokens, recent_window) -> List[float].
                Defaults to sink_and_recent_attention.
        """
        self.max_blocks = max_blocks
        self.block_size = block_size
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self.rng = random.Random(seed)
        self.attention_fn = attention_fn or sink_and_recent_attention

        self.policy = make_policy(
            policy_type, sink_tokens=sink_tokens, recent_window=recent_window,
            kv_policy=kv_policy,
        ) if policy_type == PolicyType.KV_POLICY else make_policy(
            policy_type, sink_tokens=sink_tokens, recent_window=recent_window,
        )

        # State
        self.blocks: Dict[int, KVBlock] = {}
        self.pinned: Set[int] = set()        # sink blocks — never evict
        self.sequences: Dict[int, Sequence] = {}
        self._next_block_id = 0
        self._step = 0

        # Metrics
        self.stats = {
            "blocks_allocated": 0,
            "blocks_evicted": 0,
            "attention_events": 0,
            "sink_blocks_protected": 0,
            "important_evictions": 0,     # evicted blocks with high attention
            "recompute_cost": 0,          # sum of tokens in evicted blocks later needed
        }
        self._evicted_blocks: Dict[int, KVBlock] = {}  # bounded: cleared per sequence on detection
        self._max_evicted_tracking = max_blocks * 4

    # ---- Sequence lifecycle ----

    def add_sequence(self, seq_id: int, context_length: int) -> Sequence:
        seq = Sequence(sequence_id=seq_id, context_length=context_length)
        self.sequences[seq_id] = seq
        self.policy.on_sequence_register(seq_id, context_length)
        return seq

    def remove_sequence(self, seq_id: int) -> List[int]:
        if seq_id not in self.sequences:
            return []
        self.policy.on_sequence_complete(seq_id)
        seq = self.sequences.pop(seq_id)
        freed = []
        for bid in seq.block_ids:
            if bid in self.blocks:
                self.policy.on_evict(bid)
                del self.blocks[bid]
                self.pinned.discard(bid)
                freed.append(bid)
            # Clean up eviction tracking for this sequence
            self._evicted_blocks.pop(bid, None)
        return freed

    # ---- Prefill phase ----

    def prefill_sequence(self, seq_id: int) -> int:
        """
        Write all KV blocks for a sequence's prompt. Returns blocks allocated.
        """
        seq = self.sequences[seq_id]
        num_blocks = math.ceil(seq.context_length / self.block_size)
        allocated = 0

        for i in range(num_blocks):
            start_pos = i * self.block_size
            end_pos = min(start_pos + self.block_size, seq.context_length)
            positions = list(range(start_pos, end_pos))

            # Evict if needed
            while len(self.blocks) >= self.max_blocks:
                self._evict()

            bid = self._allocate_block(seq_id, positions)
            seq.block_ids.append(bid)

            # Classify block type
            block = self.blocks[bid]
            if start_pos < self.sink_tokens:
                block.block_type = BlockType.SINK
                self.pinned.add(bid)
                self.stats["sink_blocks_protected"] += 1
            allocated += 1

        seq.phase = Phase.DECODE
        seq.prefill_done = True
        seq.generated_tokens = seq.context_length
        self.policy.on_phase_change(seq_id, Phase.DECODE)
        return allocated

    # ---- Decode phase ----

    def decode_step(self, seq_id: int) -> None:
        """
        Simulate one decode step: new token attends to all prior tokens.
        Attention follows sink+recent distribution.
        """
        seq = self.sequences[seq_id]
        self._step += 1
        seq.generated_tokens += 1
        current_len = seq.generated_tokens
        new_position = current_len - 1

        # Generate attention distribution
        attention = self.attention_fn(
            current_len, self.sink_tokens, self.recent_window,
        )

        # Distribute attention to blocks and detect recompute cost
        for bid in list(seq.block_ids):
            if bid not in self.blocks:
                # Block was evicted — its tokens need recomputation
                evicted = self._evicted_blocks.get(bid)
                if evicted:
                    recompute_tokens = len(evicted.token_positions)
                    self.stats["recompute_cost"] += recompute_tokens
                    seq.evicted_positions += recompute_tokens
                    # Remove from sequence to avoid re-counting
                    seq.block_ids.remove(bid)
                continue
            block = self.blocks[bid]
            block_attn = sum(
                attention[p] for p in block.token_positions if p < len(attention)
            )
            # Compute per-position attention for this block
            pos_attn = {
                p: attention[p]
                for p in block.token_positions
                if p < len(attention) and attention[p] > 0
            }
            block_attn = sum(pos_attn.values())
            if block_attn > 0:
                block.cumulative_attention += block_attn
                block.access_count += 1
                block.last_access_step = self._step
                self.stats["attention_events"] += 1
                self.policy.on_block_attention(
                    bid, block, pos_attn, seq_id, current_len,
                )

                # Reclassify based on attention
                self._classify_block(block, current_len)

        # Place new token into a block
        needs_new_block = (
            not seq.block_ids
            or new_position % self.block_size == 0
        )

        if needs_new_block:
            # Allocate a fresh block for this token
            while len(self.blocks) >= self.max_blocks:
                self._evict()
            bid = self._allocate_block(seq_id, [new_position])
            seq.block_ids.append(bid)
        else:
            # Append position to the last block
            last_bid = seq.block_ids[-1]
            if last_bid in self.blocks:
                self.blocks[last_bid].token_positions.append(new_position)

    # ---- Internal ----

    def _allocate_block(self, seq_id: int, positions: List[int]) -> int:
        bid = self._next_block_id
        self._next_block_id += 1
        block = KVBlock(
            block_id=bid, sequence_id=seq_id, token_positions=positions,
            created_step=self._step, last_access_step=self._step,
        )
        self.blocks[bid] = block
        self.policy.on_admit(bid, block)
        self.stats["blocks_allocated"] += 1
        return bid

    def _evict(self) -> Optional[int]:
        victim = self.policy.select_victim(self.blocks, self.pinned)
        if victim is None:
            return None
        block = self.blocks[victim]

        # Track if this was an important eviction
        if block.block_type in (BlockType.SINK, BlockType.ENTITY):
            self.stats["important_evictions"] += 1

        # Save for recompute cost tracking (bounded)
        if len(self._evicted_blocks) >= self._max_evicted_tracking:
            # Drop oldest entries
            oldest = next(iter(self._evicted_blocks))
            del self._evicted_blocks[oldest]
        self._evicted_blocks[victim] = block

        # Note: block stays in seq.block_ids so decode_step() can detect
        # the missing block and count recompute cost on next access.

        self.policy.on_evict(victim)
        self.pinned.discard(victim)
        del self.blocks[victim]
        self.stats["blocks_evicted"] += 1
        return victim

    def _classify_block(self, block: KVBlock, seq_len: int) -> None:
        """Reclassify block based on current attention and position."""
        min_pos = min(block.token_positions) if block.token_positions else 0

        if min_pos < self.sink_tokens:
            block.block_type = BlockType.SINK
            self.pinned.add(block.block_id)
        elif min_pos >= seq_len - self.recent_window:
            block.block_type = BlockType.RECENT
        elif block.avg_attention > 0.02:
            block.block_type = BlockType.ENTITY
        else:
            block.block_type = BlockType.FILLER

    def get_metrics(self) -> Dict:
        """Compute simulation metrics."""
        total_blocks = self.stats["blocks_allocated"]
        evictions = self.stats["blocks_evicted"]
        important = self.stats["important_evictions"]

        # Block type distribution in current cache
        type_dist = {"sink": 0, "entity": 0, "recent": 0, "filler": 0}
        for b in self.blocks.values():
            type_dist[b.block_type.name.lower()] += 1

        # Retention rate: fraction of allocated blocks still in cache
        retention = len(self.blocks) / max(1, total_blocks)

        # Eviction accuracy: fraction of evictions that were filler blocks
        eviction_accuracy = 1.0 - (important / max(1, evictions))

        return {
            **self.stats,
            "cache_occupancy": len(self.blocks),
            "max_blocks": self.max_blocks,
            "utilization": len(self.blocks) / self.max_blocks,
            "retention_rate": retention,
            "eviction_accuracy": eviction_accuracy,
            "block_type_distribution": type_dist,
            "active_sequences": len(self.sequences),
            "step": self._step,
        }


# =============================================================================
# Workload Runner
# =============================================================================

def run_workload(
    max_blocks: int,
    block_size: int,
    sequences: List[Tuple[int, int]],    # [(seq_id, context_length), ...]
    decode_steps_per_seq: int,
    policy_type: PolicyType,
    seed: int = 42,
    sink_tokens: int = 4,
    recent_window: int = 128,
    kv_policy=None,
    attention_fn=None,
) -> Dict:
    """
    Run a complete workload and return metrics.

    Simulates continuous batching: prefill all sequences, then interleaved
    decode steps.

    Args:
        kv_policy: A KVCachePolicy instance. Required when
            policy_type=PolicyType.KV_POLICY.
        attention_fn: Optional attention pattern function override.
    """
    sim = KVCacheSimulator(
        max_blocks=max_blocks, block_size=block_size,
        policy_type=policy_type, seed=seed,
        sink_tokens=sink_tokens, recent_window=recent_window,
        kv_policy=kv_policy, attention_fn=attention_fn,
    )

    # Prefill all sequences
    for seq_id, ctx_len in sequences:
        sim.add_sequence(seq_id, ctx_len)
        sim.prefill_sequence(seq_id)

    # Interleaved decode
    active_ids = [sid for sid, _ in sequences]
    for step in range(decode_steps_per_seq):
        for sid in active_ids:
            if sid in sim.sequences:
                sim.decode_step(sid)

    metrics = sim.get_metrics()
    metrics["policy"] = policy_type.value
    return metrics


def compare_policies(
    max_blocks: int = 256,
    block_size: int = 16,
    num_sequences: int = 4,
    context_length: int = 512,
    decode_steps: int = 128,
    seed: int = 42,
    include_kv_policy: bool = True,
    attention_fn=None,
    sequences: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, Dict]:
    """
    Run the same workload under all policies and return comparison.

    Args:
        include_kv_policy: Set False to skip KV_POLICY (requires KVPolicy module).
        attention_fn: Optional attention pattern function override.
        sequences: Optional explicit sequence list [(seq_id, context_length), ...].
            Overrides num_sequences/context_length when provided.
    """
    if sequences is None:
        sequences = [(i, context_length) for i in range(num_sequences)]
    results = {}

    for policy in PolicyType:
        if policy == PolicyType.KV_POLICY:
            if not include_kv_policy:
                continue
            try:
                from CTM_plus.KVPolicy.kv_policy.attention_evictor import KVCachePolicy
            except ImportError:
                continue
            kv_pol = KVCachePolicy(
                max_blocks=max_blocks, block_size=block_size,
                sink_tokens=4, recent_window=128,
            )
        else:
            kv_pol = None

        start = time.perf_counter()
        metrics = run_workload(
            max_blocks=max_blocks, block_size=block_size,
            sequences=sequences, decode_steps_per_seq=decode_steps,
            policy_type=policy, seed=seed,
            kv_policy=kv_pol, attention_fn=attention_fn,
        )
        elapsed = time.perf_counter() - start
        metrics["elapsed_seconds"] = round(elapsed, 4)
        results[policy.value] = metrics

    return results
