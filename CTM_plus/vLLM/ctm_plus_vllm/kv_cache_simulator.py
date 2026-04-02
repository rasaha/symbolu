"""
KV Cache Simulator for CTM+ Benchmarking

Simulates KV cache behavior with different eviction policies
to measure hit rate, quality preservation, and throughput.
"""

import random
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import defaultdict, deque
import heapq


class EvictionPolicy(Enum):
    LRU = "lru"
    FIFO = "fifo"
    CTM_PLUS = "ctm_plus"
    RANDOM = "random"


@dataclass
class TokenMetadata:
    """Metadata for a token in KV cache."""
    position: int
    token_type: str = "regular"  # regular, bos, entity, number, code
    created_time: int = 0
    last_access_time: int = 0
    access_count: int = 0
    attention_weights: list = field(default_factory=list)

    @property
    def avg_attention(self) -> float:
        if not self.attention_weights:
            return 0.0
        return sum(self.attention_weights) / len(self.attention_weights)

    @property
    def max_attention(self) -> float:
        if not self.attention_weights:
            return 0.0
        return max(self.attention_weights)


@dataclass
class CTMKVConfig:
    """Configuration for CTM+ KV cache scoring."""
    weight_recency: float = 0.20
    weight_frequency: float = 0.25
    weight_attention_strength: float = 0.25
    weight_token_importance: float = 0.15
    weight_position: float = 0.10
    weight_sequence_priority: float = 0.05

    attention_sink_tokens: int = 4
    recent_window_size: int = 256
    frequency_window: int = 1000

    @classmethod
    def for_chatbot(cls) -> "CTMKVConfig":
        """Low-latency chatbot configuration."""
        return cls(
            weight_recency=0.30,
            weight_frequency=0.25,
            weight_attention_strength=0.25,
            weight_token_importance=0.10,
            weight_position=0.10,
            recent_window_size=256,
        )

    @classmethod
    def for_long_context(cls) -> "CTMKVConfig":
        """Long context (32K+) configuration."""
        return cls(
            weight_recency=0.10,
            weight_frequency=0.25,
            weight_attention_strength=0.35,
            weight_token_importance=0.20,
            weight_position=0.10,
            attention_sink_tokens=8,
            recent_window_size=1024,
        )

    @classmethod
    def for_batch_processing(cls) -> "CTMKVConfig":
        """High-throughput batch processing configuration."""
        return cls(
            weight_recency=0.15,
            weight_frequency=0.30,
            weight_attention_strength=0.30,
            weight_token_importance=0.15,
            weight_position=0.10,
            recent_window_size=512,
        )


class KVCacheSimulator:
    """
    Simulates KV cache with configurable eviction policies.
    """

    TOKEN_IMPORTANCE = {
        "bos": 1.0,
        "entity": 0.9,
        "number": 0.85,
        "code": 0.8,
        "instruction": 0.75,
        "eos": 0.5,
        "regular": 0.4,
        "punctuation": 0.2,
    }

    def __init__(
        self,
        max_tokens: int,
        policy: EvictionPolicy,
        config: Optional[CTMKVConfig] = None,
    ):
        self.max_tokens = max_tokens
        self.policy = policy
        self.config = config or CTMKVConfig()

        # Cache state
        self.cache: dict[int, TokenMetadata] = {}
        self.current_time = 0

        # For LRU
        self.lru_order: deque = deque()

        # For FIFO
        self.fifo_order: deque = deque()

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_accesses": 0,
            "entity_hits": 0,
            "entity_accesses": 0,
        }

    def reset(self):
        """Reset the simulator state."""
        self.cache.clear()
        self.lru_order.clear()
        self.fifo_order.clear()
        self.current_time = 0
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_accesses": 0,
            "entity_hits": 0,
            "entity_accesses": 0,
        }

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> bool:
        """
        Access a token in the KV cache.
        Returns True if hit, False if miss.
        """
        self.current_time += 1
        self.stats["total_accesses"] += 1
        is_entity = token_type == "entity"
        if is_entity:
            self.stats["entity_accesses"] += 1

        if position in self.cache:
            # Cache hit
            self.stats["hits"] += 1
            if is_entity:
                self.stats["entity_hits"] += 1
            meta = self.cache[position]
            meta.last_access_time = self.current_time
            meta.access_count += 1
            meta.attention_weights.append(attention_weight)
            # Keep only recent attention weights
            if len(meta.attention_weights) > 100:
                meta.attention_weights = meta.attention_weights[-100:]

            # Update LRU order
            if self.policy == EvictionPolicy.LRU:
                if position in self.lru_order:
                    self.lru_order.remove(position)
                self.lru_order.append(position)

            return True
        else:
            # Cache miss
            self.stats["misses"] += 1

            # Evict if necessary
            while len(self.cache) >= self.max_tokens:
                self._evict()

            # Insert new token
            self.cache[position] = TokenMetadata(
                position=position,
                token_type=token_type,
                created_time=self.current_time,
                last_access_time=self.current_time,
                access_count=1,
                attention_weights=[attention_weight],
            )

            if self.policy == EvictionPolicy.LRU:
                self.lru_order.append(position)
            elif self.policy == EvictionPolicy.FIFO:
                self.fifo_order.append(position)

            return False

    def _evict(self):
        """Evict a token based on the configured policy."""
        if not self.cache:
            return

        self.stats["evictions"] += 1

        if self.policy == EvictionPolicy.LRU:
            victim = self.lru_order.popleft()
            del self.cache[victim]

        elif self.policy == EvictionPolicy.FIFO:
            victim = self.fifo_order.popleft()
            del self.cache[victim]

        elif self.policy == EvictionPolicy.RANDOM:
            victim = random.choice(list(self.cache.keys()))
            del self.cache[victim]

        elif self.policy == EvictionPolicy.CTM_PLUS:
            victim = self._ctm_select_victim()
            del self.cache[victim]
            if victim in self.lru_order:
                self.lru_order.remove(victim)

    def _ctm_select_victim(self) -> int:
        """Select victim using CTM+ multi-signal scoring."""
        # Sample candidates (O(k) instead of O(n))
        sample_size = min(64, len(self.cache))
        candidates = random.sample(list(self.cache.keys()), sample_size)

        # Score each candidate
        scores = []
        for pos in candidates:
            score = self._ctm_score(pos)
            scores.append((pos, score))

        # Return lowest scoring (least valuable)
        scores.sort(key=lambda x: x[1])
        return scores[0][0]

    def _ctm_score(self, position: int) -> float:
        """Calculate CTM+ score for a token. Higher = more valuable."""
        meta = self.cache[position]
        score = 0.0

        # Signal 1: Recency
        age = self.current_time - meta.last_access_time
        half_life = 100
        recency = math.exp(-0.693 * age / half_life)
        score += self.config.weight_recency * recency

        # Signal 2: Frequency
        freq = min(1.0, meta.access_count / self.config.frequency_window)
        frequency = math.log1p(freq * 10) / math.log1p(10)
        score += self.config.weight_frequency * frequency

        # Signal 3: Attention strength
        if meta.attention_weights:
            avg_attn = meta.avg_attention
            baseline = 1.0 / 1000
            strength = avg_attn / baseline if baseline > 0 else 0
            attention = 1 / (1 + math.exp(-0.5 * (strength - 5)))
        else:
            attention = 0.0
        score += self.config.weight_attention_strength * attention

        # Signal 4: Token importance
        importance = self.TOKEN_IMPORTANCE.get(meta.token_type, 0.4)
        score += self.config.weight_token_importance * importance

        # Signal 5: Position (attention sinks + recent window)
        seq_len = max(self.cache.keys()) + 1 if self.cache else 1
        position_score = 0.3

        # Attention sink bonus
        if position < self.config.attention_sink_tokens:
            position_score = 1.0
        # Recent window bonus
        elif position > seq_len - self.config.recent_window_size:
            recency_bonus = 1.0 - (seq_len - position) / self.config.recent_window_size
            position_score = max(position_score, recency_bonus)

        score += self.config.weight_position * position_score

        return score

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return self.stats["hits"] / total

    def get_stats(self) -> dict:
        """Get detailed statistics."""
        h = self.stats["hits"]
        m = self.stats["misses"]
        ea = self.stats["entity_accesses"]
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "entity_hit_rate": self.stats["entity_hits"] / ea if ea > 0 else 0.0,
            "avg_latency_ns": (h * 100 + m * 10000) / max(1, h + m),
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
            "policy": self.policy.value,
        }


class AttentionPatternGenerator:
    """
    Generates realistic attention patterns for benchmarking.
    """

    @staticmethod
    def uniform(seq_len: int) -> list[float]:
        """Uniform attention (baseline)."""
        return [1.0 / seq_len] * seq_len

    @staticmethod
    def sink_and_recent(seq_len: int, sink_tokens: int = 4, recent_window: int = 256) -> list[float]:
        """Realistic LLM attention: sinks + recent window."""
        weights = []
        for i in range(seq_len):
            if i < sink_tokens:
                # Attention sink
                w = 0.15 / sink_tokens
            elif i >= seq_len - recent_window:
                # Recent window
                recency = (i - (seq_len - recent_window)) / recent_window
                w = 0.55 * recency / recent_window
            else:
                # Middle tokens
                w = 0.30 / (seq_len - sink_tokens - recent_window)
            weights.append(w)

        # Normalize
        total = sum(weights)
        return [w / total for w in weights]

    @staticmethod
    def zipfian(seq_len: int, s: float = 1.0) -> list[float]:
        """Zipfian distribution (some tokens much more important)."""
        weights = []
        for i in range(1, seq_len + 1):
            weights.append(1.0 / (i ** s))
        total = sum(weights)
        return [w / total for w in weights]

    @staticmethod
    def entity_focused(seq_len: int, entity_positions: list[int]) -> list[float]:
        """High attention to specific entity positions."""
        weights = [0.1 / seq_len] * seq_len
        entity_weight = 0.5 / len(entity_positions) if entity_positions else 0
        for pos in entity_positions:
            if pos < seq_len:
                weights[pos] = entity_weight

        # Recent window
        recent_start = max(0, seq_len - 256)
        for i in range(recent_start, seq_len):
            weights[i] = 0.4 / (seq_len - recent_start)

        total = sum(weights)
        return [w / total for w in weights]


class WorkloadGenerator:
    """
    Generates different KV cache access workloads.
    """

    def __init__(self, seq_len: int, seed: int = 42):
        self.seq_len = seq_len
        self.random = random.Random(seed)

    def sequential(self, num_accesses: int) -> list[tuple[int, str, float]]:
        """Sequential token generation (autoregressive)."""
        accesses = []
        attention_gen = AttentionPatternGenerator()

        for t in range(min(num_accesses, self.seq_len)):
            # Each new token attends to all previous
            current_len = t + 1
            attention = attention_gen.sink_and_recent(current_len)

            # Sample which positions to attend to (simulate sparse attention)
            for pos in range(current_len):
                token_type = self._get_token_type(pos)
                accesses.append((pos, token_type, attention[pos]))

        return accesses

    def multi_turn_conversation(
        self,
        num_turns: int,
        tokens_per_turn: int,
    ) -> list[tuple[int, str, float]]:
        """Multi-turn conversation with accumulating context."""
        accesses = []
        current_pos = 0

        for turn in range(num_turns):
            # Each turn adds new tokens
            turn_start = current_pos
            turn_end = turn_start + tokens_per_turn

            # Attention pattern for this turn
            total_len = turn_end
            attention = AttentionPatternGenerator.sink_and_recent(total_len)

            # Access all positions for new tokens
            for new_token in range(turn_start, turn_end):
                for pos in range(new_token + 1):
                    token_type = self._get_token_type(pos)
                    # More attention to same turn
                    attn = attention[pos]
                    if pos >= turn_start:
                        attn *= 2.0
                    accesses.append((pos, token_type, attn))

            current_pos = turn_end

        return accesses

    def document_qa(
        self,
        doc_length: int,
        num_questions: int,
        question_length: int = 20,
    ) -> list[tuple[int, str, float]]:
        """Document QA: document + multiple questions."""
        accesses = []

        # First, process document
        for pos in range(doc_length):
            token_type = self._get_token_type(pos)
            # During document processing, uniform attention
            accesses.append((pos, token_type, 1.0 / (pos + 1)))

        # Then, multiple questions
        for q in range(num_questions):
            q_start = doc_length + q * question_length
            q_end = q_start + question_length
            total_len = q_end

            # Questions attend heavily to document entities
            entity_positions = [i for i in range(doc_length) if self.random.random() < 0.1]
            attention = AttentionPatternGenerator.entity_focused(total_len, entity_positions)

            for new_token in range(q_start, q_end):
                for pos in range(new_token + 1):
                    token_type = self._get_token_type(pos)
                    accesses.append((pos, token_type, attention[pos] if pos < len(attention) else 0.01))

        return accesses

    def zipfian_hotspot(
        self,
        num_accesses: int,
        s: float = 1.0,
    ) -> list[tuple[int, str, float]]:
        """Zipfian access pattern with hotspots."""
        accesses = []
        attention = AttentionPatternGenerator.zipfian(self.seq_len, s)

        # Generate accesses weighted by Zipfian
        for _ in range(num_accesses):
            # Weighted random choice
            pos = self.random.choices(range(self.seq_len), weights=attention, k=1)[0]
            token_type = self._get_token_type(pos)
            accesses.append((pos, token_type, attention[pos]))

        return accesses

    def _get_token_type(self, position: int) -> str:
        """Assign token type based on position (simplified)."""
        if position == 0:
            return "bos"
        elif position < 10 and self.random.random() < 0.3:
            return "instruction"
        elif self.random.random() < 0.05:
            return "entity"
        elif self.random.random() < 0.05:
            return "number"
        elif self.random.random() < 0.1:
            return "punctuation"
        else:
            return "regular"


def run_benchmark(
    workload: list[tuple[int, str, float]],
    max_tokens: int,
    policies: list[EvictionPolicy],
    config: Optional[CTMKVConfig] = None,
) -> dict[str, dict]:
    """
    Run benchmark comparing different eviction policies.

    Returns dict mapping policy name to stats.
    """
    results = {}

    for policy in policies:
        sim = KVCacheSimulator(max_tokens, policy, config)

        start_time = time.perf_counter()
        for pos, token_type, attention in workload:
            sim.access(pos, token_type, attention)
        elapsed = time.perf_counter() - start_time

        stats = sim.get_stats()
        stats["elapsed_seconds"] = elapsed
        stats["accesses_per_second"] = len(workload) / elapsed if elapsed > 0 else 0
        results[policy.value] = stats

    return results


def quality_preservation_test(
    seq_len: int,
    cache_ratio: float,
    policies: list[EvictionPolicy],
    num_queries: int = 100,
) -> dict[str, float]:
    """
    Test quality preservation: can we answer queries after eviction?

    Simulates keeping only cache_ratio of tokens and measuring
    how many "important" tokens are retained.
    """
    results = {}
    config = CTMKVConfig.for_long_context()

    # Generate a document with known important positions
    random.seed(42)
    important_positions = set(random.sample(range(seq_len), seq_len // 10))
    # Always include attention sinks
    important_positions.update(range(4))

    for policy in policies:
        max_tokens = int(seq_len * cache_ratio)
        sim = KVCacheSimulator(max_tokens, policy, config)

        # Process document (all tokens)
        workload = WorkloadGenerator(seq_len).sequential(seq_len)
        for pos, token_type, attention in workload:
            # Mark important positions with high attention
            if pos in important_positions:
                attention *= 10
            sim.access(pos, token_type, attention)

        # Check how many important tokens are retained
        retained_important = len(important_positions.intersection(sim.cache.keys()))
        retention_rate = retained_important / len(important_positions)

        results[policy.value] = retention_rate

    return results
