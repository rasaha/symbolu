"""
Research baseline KV cache eviction policies.

Implements the two dominant LLM KV cache eviction baselines from the
research literature:

  1. H2O (Heavy-Hitter Oracle) — Zhang et al., NeurIPS 2023
     "H2O: Heavy-Hitter Oracle for Efficient Generative Inference of
      Large Language Models"
     Policy: Keep attention sinks + tokens with highest cumulative
     attention score (heavy hitters).

  2. StreamingLLM — Xiao et al., ICLR 2024
     "Efficient Streaming Language Models with Attention Sinks"
     Policy: Keep attention sinks (first N tokens) + sliding window
     of most recent tokens. Simplest effective policy.

  3. TOVA — Oren et al., 2024
     "Transformers are Multi-State RNNs"
     Policy: Evict the token with the lowest last attention score.
     Recent-attention-weighted eviction.

These are implemented as fast dict-based simulators (like CXLTieredSimulator)
so they scale to 131K+ tokens without the deque.remove() bottleneck.
"""

import math
import random
from dataclasses import dataclass, field
from collections import OrderedDict


class H2OSimulator:
    """
    H2O: Heavy-Hitter Oracle for KV Cache Eviction.

    Algorithm:
    - Maintain a "heavy hitter" set: tokens with highest cumulative
      attention scores across all decoding steps
    - Always protect attention sink tokens (first sink_tokens positions)
    - On eviction: remove the token with the lowest cumulative attention
      that is not a sink

    Reference: Zhang et al., NeurIPS 2023
    """

    def __init__(
        self,
        max_tokens: int,
        sink_tokens: int = 4,
        heavy_hitter_ratio: float = 0.5,
    ):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens
        # Reserve slots: sinks + heavy_hitters + recent
        self.heavy_hitter_budget = int(max_tokens * heavy_hitter_ratio)

        self.cache: dict[int, dict] = {}  # pos -> metadata
        self.current_time = 0

        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> bool:
        self.current_time += 1
        self.stats["total_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            self.stats["total_latency_ns"] += 100
            m = self.cache[position]
            m["last_access_time"] = self.current_time
            m["access_count"] = m.get("access_count", 0) + 1
            m["cumulative_attention"] = m.get("cumulative_attention", 0) + attention_weight
            return True

        self.stats["misses"] += 1
        self.stats["total_latency_ns"] += 10000

        # Evict if full
        while len(self.cache) >= self.max_tokens:
            self._evict()

        self.cache[position] = {
            "position": position,
            "token_type": token_type,
            "created_time": self.current_time,
            "last_access_time": self.current_time,
            "access_count": 1,
            "cumulative_attention": attention_weight,
        }
        return False

    def _evict(self):
        if not self.cache:
            return
        self.stats["evictions"] += 1

        # Find victim: lowest cumulative attention, not a sink
        victim_pos = None
        victim_score = float("inf")

        # Sample candidates for O(k) instead of O(n)
        sample_size = min(64, len(self.cache))
        candidates = random.sample(list(self.cache.keys()), sample_size)

        for pos in candidates:
            # Protect sinks
            if pos < self.sink_tokens:
                continue
            score = self.cache[pos].get("cumulative_attention", 0)
            if score < victim_score:
                victim_score = score
                victim_pos = pos

        if victim_pos is not None:
            del self.cache[victim_pos]
        elif candidates:
            # All candidates are sinks — evict any non-sink
            for pos in self.cache:
                if pos >= self.sink_tokens:
                    del self.cache[pos]
                    break

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
        }


class StreamingLLMSimulator:
    """
    StreamingLLM: Attention Sinks + Sliding Window.

    Algorithm:
    - Always keep the first `sink_tokens` positions (attention sinks)
    - Keep a sliding window of the most recent `window_size` tokens
    - On eviction: remove the oldest non-sink, non-recent token

    This is the simplest effective KV cache eviction policy. It works
    because LLM attention concentrates on sinks + recent tokens.

    Reference: Xiao et al., ICLR 2024
    """

    def __init__(
        self,
        max_tokens: int,
        sink_tokens: int = 4,
    ):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens
        # Window is everything except sinks
        self.window_size = max_tokens - sink_tokens

        self.cache: dict[int, dict] = {}
        self.insertion_order: list[int] = []  # Ordered by insertion time
        self.current_time = 0

        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> bool:
        self.current_time += 1
        self.stats["total_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            self.stats["total_latency_ns"] += 100
            m = self.cache[position]
            m["last_access_time"] = self.current_time
            m["access_count"] = m.get("access_count", 0) + 1
            return True

        self.stats["misses"] += 1
        self.stats["total_latency_ns"] += 10000

        # Evict if full
        while len(self.cache) >= self.max_tokens:
            self._evict()

        self.cache[position] = {
            "position": position,
            "token_type": token_type,
            "created_time": self.current_time,
            "last_access_time": self.current_time,
            "access_count": 1,
        }
        self.insertion_order.append(position)
        return False

    def _evict(self):
        if not self.cache:
            return
        self.stats["evictions"] += 1

        # Evict oldest non-sink token
        while self.insertion_order:
            victim = self.insertion_order.pop(0)
            if victim in self.cache and victim >= self.sink_tokens:
                del self.cache[victim]
                return
            elif victim in self.cache:
                # It's a sink — put it back (skip it)
                self.insertion_order.append(victim)
                # But if we've cycled through all, we must evict something
                if len(self.insertion_order) >= len(self.cache):
                    # All sinks — evict any
                    del self.cache[victim]
                    return

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
        }


class TOVASimulator:
    """
    TOVA: Token Omission Via Attention.

    Algorithm:
    - Evict the token with the lowest most-recent attention weight
    - Protects attention sinks

    Simpler than H2O (uses last attention, not cumulative).

    Reference: Oren et al., 2024
    """

    def __init__(
        self,
        max_tokens: int,
        sink_tokens: int = 4,
    ):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens

        self.cache: dict[int, dict] = {}
        self.current_time = 0

        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> bool:
        self.current_time += 1
        self.stats["total_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            self.stats["total_latency_ns"] += 100
            m = self.cache[position]
            m["last_access_time"] = self.current_time
            m["access_count"] = m.get("access_count", 0) + 1
            m["last_attention"] = attention_weight
            return True

        self.stats["misses"] += 1
        self.stats["total_latency_ns"] += 10000

        while len(self.cache) >= self.max_tokens:
            self._evict()

        self.cache[position] = {
            "position": position,
            "token_type": token_type,
            "created_time": self.current_time,
            "last_access_time": self.current_time,
            "access_count": 1,
            "last_attention": attention_weight,
        }
        return False

    def _evict(self):
        if not self.cache:
            return
        self.stats["evictions"] += 1

        # Sample + score by last attention
        sample_size = min(64, len(self.cache))
        candidates = random.sample(list(self.cache.keys()), sample_size)

        victim_pos = None
        victim_attn = float("inf")
        for pos in candidates:
            if pos < self.sink_tokens:
                continue
            attn = self.cache[pos].get("last_attention", 0)
            if attn < victim_attn:
                victim_attn = attn
                victim_pos = pos

        if victim_pos is not None:
            del self.cache[victim_pos]
        elif candidates:
            for pos in self.cache:
                if pos >= self.sink_tokens:
                    del self.cache[pos]
                    break

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
        }
