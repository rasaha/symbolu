"""
Research baseline KV cache eviction policies.

Implements the dominant LLM KV cache eviction baselines:

  1. H2O (Heavy-Hitter Oracle) — Zhang et al., NeurIPS 2023
     Policy: Keep attention sinks + tokens with highest cumulative
     attention score (heavy hitters). Full-scan eviction (faithful).

  2. StreamingLLM — Xiao et al., ICLR 2024
     Policy: Keep attention sinks (first N tokens) + sliding window
     of most recent tokens. O(1) eviction via deque.

  3. TOVA — Oren et al., 2024
     Policy: Evict the token with the lowest last attention score.
     Full-scan eviction (faithful to paper).

All use dict-based caches for O(1) lookup, scaling to 131K+ tokens.
"""

from collections import deque


class H2OSimulator:
    """
    H2O: Heavy-Hitter Oracle for KV Cache Eviction.

    Evicts the non-sink token with the globally lowest cumulative
    attention score. Full scan over cache (faithful to paper).

    Reference: Zhang et al., NeurIPS 2023
    """

    def __init__(self, max_tokens: int, sink_tokens: int = 4):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens
        self.cache: dict[int, dict] = {}
        self.current_time = 0
        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(self, position: int, token_type: str = "regular",
               attention_weight: float = 0.01) -> bool:
        self.current_time += 1
        self.stats["total_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            self.stats["total_latency_ns"] += 100
            m = self.cache[position]
            m["last_access_time"] = self.current_time
            m["access_count"] = m.get("access_count", 0) + 1
            m["cumulative_attention"] += attention_weight
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
            "cumulative_attention": attention_weight,
        }
        return False

    def _evict(self):
        if not self.cache:
            return

        # Full scan: find non-sink token with lowest cumulative attention
        victim_pos = None
        victim_score = float("inf")
        for pos, m in self.cache.items():
            if pos < self.sink_tokens:
                continue
            score = m["cumulative_attention"]
            if score < victim_score:
                victim_score = score
                victim_pos = pos

        if victim_pos is not None:
            self.stats["evictions"] += 1
            del self.cache[victim_pos]
        elif self.cache:
            # All tokens are sinks — evict the one with lowest attention
            victim_pos = min(self.cache, key=lambda p: self.cache[p]["cumulative_attention"])
            self.stats["evictions"] += 1
            del self.cache[victim_pos]

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {**self.stats, "hit_rate": self.hit_rate,
                "cache_size": len(self.cache), "max_tokens": self.max_tokens}


class StreamingLLMSimulator:
    """
    StreamingLLM: Attention Sinks + Sliding Window.

    Keeps first `sink_tokens` positions permanently. All other slots
    form a FIFO window — oldest non-sink is evicted first. O(1) eviction.

    Reference: Xiao et al., ICLR 2024
    """

    def __init__(self, max_tokens: int, sink_tokens: int = 4):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens
        self.cache: dict[int, dict] = {}
        # FIFO order for non-sink tokens only (O(1) popleft)
        self._window: deque[int] = deque()
        self.current_time = 0
        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(self, position: int, token_type: str = "regular",
               attention_weight: float = 0.01) -> bool:
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

        while len(self.cache) >= self.max_tokens:
            self._evict()

        self.cache[position] = {
            "position": position,
            "token_type": token_type,
            "created_time": self.current_time,
            "last_access_time": self.current_time,
            "access_count": 1,
        }
        # Sinks don't go in the window — they're permanent
        if position >= self.sink_tokens:
            self._window.append(position)

        return False

    def _evict(self):
        if not self.cache:
            return

        # Pop oldest non-sink from the FIFO window
        while self._window:
            victim = self._window.popleft()
            if victim in self.cache:
                self.stats["evictions"] += 1
                del self.cache[victim]
                return
            # victim was already removed (shouldn't happen, but be safe)

        # Window is empty but cache is full — all remaining are sinks
        # Evict the sink with highest position (keep lowest positions)
        if self.cache:
            victim = max(self.cache.keys())
            self.stats["evictions"] += 1
            del self.cache[victim]

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {**self.stats, "hit_rate": self.hit_rate,
                "cache_size": len(self.cache), "max_tokens": self.max_tokens}


class TOVASimulator:
    """
    TOVA: Token Omission Via Attention.

    Evicts the non-sink token with the lowest most-recent attention weight.
    Full scan over cache (faithful to paper).

    Reference: Oren et al., 2024
    """

    def __init__(self, max_tokens: int, sink_tokens: int = 4):
        self.max_tokens = max_tokens
        self.sink_tokens = sink_tokens
        self.cache: dict[int, dict] = {}
        self.current_time = 0
        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "total_accesses": 0, "total_latency_ns": 0,
        }

    def access(self, position: int, token_type: str = "regular",
               attention_weight: float = 0.01) -> bool:
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

        # Full scan: find non-sink token with lowest last attention
        victim_pos = None
        victim_attn = float("inf")
        for pos, m in self.cache.items():
            if pos < self.sink_tokens:
                continue
            attn = m["last_attention"]
            if attn < victim_attn:
                victim_attn = attn
                victim_pos = pos

        if victim_pos is not None:
            self.stats["evictions"] += 1
            del self.cache[victim_pos]
        elif self.cache:
            # All sinks — evict highest position
            victim_pos = max(self.cache.keys())
            self.stats["evictions"] += 1
            del self.cache[victim_pos]

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        return (self.stats["hits"] / t) if t > 0 else 0.0

    def get_stats(self) -> dict:
        return {**self.stats, "hit_rate": self.hit_rate,
                "cache_size": len(self.cache), "max_tokens": self.max_tokens}
