"""
KV Cache Simulator for benchmarking eviction policies.

Simulates KV cache behavior with LRU, FIFO, Random, and CTM+ policies
to measure hit rate and important-token retention. Standalone — does not
depend on the main KVCachePolicy class.
"""

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque


# =============================================================================
# Eviction Policies
# =============================================================================

class EvictionPolicy(Enum):
    LRU = "lru"
    FIFO = "fifo"
    RANDOM = "random"
    CTM_PLUS = "ctm_plus"


# =============================================================================
# Token Metadata
# =============================================================================

@dataclass
class TokenMetadata:
    """Metadata for a cached token position."""
    position: int
    token_type: str = "regular"
    created_time: int = 0
    last_access_time: int = 0
    access_count: int = 0
    attention_weights: list = field(default_factory=list)

    @property
    def avg_attention(self) -> float:
        return sum(self.attention_weights) / len(self.attention_weights) if self.attention_weights else 0.0


# =============================================================================
# Simulator
# =============================================================================

class KVCacheSimulator:
    """
    Simulates KV cache with configurable eviction policies.
    """

    TOKEN_IMPORTANCE = {
        "bos": 1.0, "entity": 0.9, "number": 0.85, "code": 0.8,
        "instruction": 0.75, "eos": 0.5, "regular": 0.4, "punctuation": 0.2,
    }

    def __init__(
        self,
        max_tokens: int,
        policy: EvictionPolicy,
        sink_tokens: int = 4,
        recent_window: int = 256,
    ):
        self.max_tokens = max_tokens
        self.policy = policy
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window

        self.cache: dict[int, TokenMetadata] = {}
        self.current_time = 0
        self.lru_order: deque = deque()
        self.fifo_order: deque = deque()

        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "entity_hits": 0, "entity_accesses": 0,
        }

    def reset(self):
        self.cache.clear()
        self.lru_order.clear()
        self.fifo_order.clear()
        self.current_time = 0
        self.stats = {k: 0 for k in self.stats}

    def access(self, position: int, token_type: str = "regular", attention_weight: float = 0.01) -> bool:
        """Access a token. Returns True on hit."""
        self.current_time += 1
        self.stats["total_accesses"] += 1
        if token_type == "entity":
            self.stats["entity_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            if token_type == "entity":
                self.stats["entity_hits"] += 1
            meta = self.cache[position]
            meta.last_access_time = self.current_time
            meta.access_count += 1
            meta.attention_weights.append(attention_weight)
            if len(meta.attention_weights) > 100:
                meta.attention_weights = meta.attention_weights[-100:]
            if self.policy == EvictionPolicy.LRU:
                if position in self.lru_order:
                    self.lru_order.remove(position)
                self.lru_order.append(position)
            return True

        self.stats["misses"] += 1
        while len(self.cache) >= self.max_tokens:
            self._evict()

        self.cache[position] = TokenMetadata(
            position=position, token_type=token_type,
            created_time=self.current_time, last_access_time=self.current_time,
            access_count=1, attention_weights=[attention_weight],
        )
        if self.policy == EvictionPolicy.LRU:
            self.lru_order.append(position)
        elif self.policy == EvictionPolicy.FIFO:
            self.fifo_order.append(position)
        return False

    def _evict(self):
        if not self.cache:
            return
        self.stats["evictions"] += 1

        if self.policy == EvictionPolicy.LRU:
            del self.cache[self.lru_order.popleft()]
        elif self.policy == EvictionPolicy.FIFO:
            del self.cache[self.fifo_order.popleft()]
        elif self.policy == EvictionPolicy.RANDOM:
            del self.cache[random.choice(list(self.cache.keys()))]
        elif self.policy == EvictionPolicy.CTM_PLUS:
            victim = self._ctm_select_victim()
            del self.cache[victim]

    def _ctm_select_victim(self) -> int:
        """CTM+ multi-signal victim selection (sampled)."""
        candidates = random.sample(list(self.cache.keys()), min(64, len(self.cache)))
        return min(candidates, key=self._ctm_score)

    def _ctm_score(self, position: int) -> float:
        """Score a position. Higher = more valuable (less likely to evict)."""
        meta = self.cache[position]

        # Recency (exponential decay, half-life=100)
        age = self.current_time - meta.last_access_time
        recency = math.exp(-0.693 * age / 100)

        # Frequency (log-saturated)
        freq = min(1.0, meta.access_count / 1000)
        frequency = math.log1p(freq * 10) / math.log1p(10)

        # Attention strength (sigmoid)
        attention = 0.0
        if meta.attention_weights:
            baseline = 1.0 / 1000
            strength = meta.avg_attention / baseline
            attention = 1 / (1 + math.exp(-0.5 * (strength - 5)))

        # Token importance
        importance = self.TOKEN_IMPORTANCE.get(meta.token_type, 0.4)

        # Position bonus (sinks + recent window)
        seq_len = max(self.cache.keys()) + 1
        pos_score = 0.3
        if position < self.sink_tokens:
            pos_score = 1.0
        elif position > seq_len - self.recent_window:
            pos_score = max(pos_score, 1.0 - (seq_len - position) / self.recent_window)

        return 0.20 * recency + 0.25 * frequency + 0.25 * attention + 0.15 * importance + 0.15 * pos_score

    @property
    def hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total else 0.0

    def get_stats(self) -> dict:
        ea = self.stats["entity_accesses"]
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "entity_hit_rate": self.stats["entity_hits"] / ea if ea else 0.0,
            "cache_size": len(self.cache),
        }


# =============================================================================
# Workload Generators
# =============================================================================

class AttentionPatternGenerator:
    """Generates realistic LLM attention distributions."""

    @staticmethod
    def sink_and_recent(seq_len: int, sink_tokens: int = 4, recent_window: int = 256) -> list[float]:
        weights = []
        for i in range(seq_len):
            if i < sink_tokens:
                w = 0.15 / sink_tokens
            elif i >= seq_len - recent_window:
                recency = (i - (seq_len - recent_window)) / recent_window
                w = 0.55 * recency / recent_window
            else:
                mid = seq_len - sink_tokens - recent_window
                w = 0.30 / mid if mid > 0 else 0.01
            weights.append(w)
        total = sum(weights)
        return [w / total for w in weights]

    @staticmethod
    def entity_focused(seq_len: int, entity_positions: list[int]) -> list[float]:
        weights = [0.1 / seq_len] * seq_len
        if entity_positions:
            ew = 0.5 / len(entity_positions)
            for pos in entity_positions:
                if pos < seq_len:
                    weights[pos] = ew
        recent_start = max(0, seq_len - 256)
        rw = 0.4 / max(1, seq_len - recent_start)
        for i in range(recent_start, seq_len):
            weights[i] = rw
        total = sum(weights)
        return [w / total for w in weights]


class WorkloadGenerator:
    """Generates KV cache access workloads for benchmarking."""

    def __init__(self, seq_len: int, seed: int = 42):
        self.seq_len = seq_len
        self.rng = random.Random(seed)

    def sequential(self, num_accesses: int) -> list[tuple[int, str, float]]:
        """Autoregressive generation: each new token attends to all previous."""
        accesses = []
        for t in range(min(num_accesses, self.seq_len)):
            current_len = t + 1
            attention = AttentionPatternGenerator.sink_and_recent(current_len)
            for pos in range(current_len):
                accesses.append((pos, self._token_type(pos), attention[pos]))
        return accesses

    def multi_turn(self, num_turns: int, tokens_per_turn: int) -> list[tuple[int, str, float]]:
        """Multi-turn conversation with accumulating context."""
        accesses = []
        pos = 0
        for _ in range(num_turns):
            turn_end = pos + tokens_per_turn
            attention = AttentionPatternGenerator.sink_and_recent(turn_end)
            for new in range(pos, turn_end):
                for p in range(new + 1):
                    attn = attention[p] * (2.0 if p >= pos else 1.0)
                    accesses.append((p, self._token_type(p), attn))
            pos = turn_end
        return accesses

    def document_qa(self, doc_length: int, num_questions: int, q_len: int = 20) -> list[tuple[int, str, float]]:
        """Document + multiple questions attending to entities."""
        accesses = []
        for pos in range(doc_length):
            accesses.append((pos, self._token_type(pos), 1.0 / (pos + 1)))
        for q in range(num_questions):
            q_start = doc_length + q * q_len
            entity_positions = [i for i in range(doc_length) if self.rng.random() < 0.1]
            attention = AttentionPatternGenerator.entity_focused(q_start + q_len, entity_positions)
            for new in range(q_start, q_start + q_len):
                for p in range(new + 1):
                    accesses.append((p, self._token_type(p), attention[p] if p < len(attention) else 0.01))
        return accesses

    def _token_type(self, position: int) -> str:
        if position == 0:
            return "bos"
        r = self.rng.random()
        if position < 10 and r < 0.3:
            return "instruction"
        if r < 0.05:
            return "entity"
        if r < 0.10:
            return "number"
        if r < 0.20:
            return "punctuation"
        return "regular"


# =============================================================================
# Benchmark Runner
# =============================================================================

def run_benchmark(
    workload: list[tuple[int, str, float]],
    max_tokens: int,
    policies: Optional[list[EvictionPolicy]] = None,
) -> dict[str, dict]:
    """Compare eviction policies on a workload. Returns {policy_name: stats}."""
    if policies is None:
        policies = list(EvictionPolicy)
    results = {}
    for policy in policies:
        sim = KVCacheSimulator(max_tokens, policy)
        start = time.perf_counter()
        for pos, tt, attn in workload:
            sim.access(pos, tt, attn)
        elapsed = time.perf_counter() - start
        stats = sim.get_stats()
        stats["elapsed_seconds"] = elapsed
        results[policy.value] = stats
    return results
