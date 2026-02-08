"""
Enterprise KV Cache Benchmark Suite

Compares CTM+ against realistic industry baselines, not just LRU.
Measures quality metrics that matter to production deployments.

Industry Baseline Policy (what big labs actually use):
- Pinned sinks (prefix blocks are never evicted)
- Attention-weighted LRU for remaining blocks
- Ghost cache for regret tracking (like ARC)
- Conservative prefetch only on sequential patterns

Quality Metrics (beyond hit rate):
- Attention coverage: what % of attention mass is in cache
- Quality preservation: retention of high-importance tokens
- Latency distribution: p50, p95, p99 per-operation
- Memory efficiency: quality-per-byte metric
"""

import random
import math
import time
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import defaultdict, deque, OrderedDict
import heapq


class EnterprisePolicy(Enum):
    """Eviction policies including industry baselines."""
    LRU = "lru"
    FIFO = "fifo"
    RANDOM = "random"
    CTM_PLUS = "ctm_plus"
    # Industry baselines
    SINK_LRU = "sink_lru"  # Pinned sinks + LRU
    ATTENTION_LRU = "attention_lru"  # Attention-weighted LRU
    INDUSTRY_BASELINE = "industry_baseline"  # Full industry policy
    H2O = "h2o"  # Heavy-Hitter Oracle (streaming LLM baseline)


@dataclass
class BlockMetadata:
    """Metadata for a KV block (may contain multiple tokens)."""
    block_id: int
    start_position: int
    end_position: int
    created_time: int = 0
    last_access_time: int = 0
    access_count: int = 0
    cumulative_attention: float = 0.0
    attention_samples: int = 0
    is_pinned: bool = False
    token_types: list = field(default_factory=list)

    @property
    def avg_attention(self) -> float:
        if self.attention_samples == 0:
            return 0.0
        return self.cumulative_attention / self.attention_samples

    @property
    def block_size(self) -> int:
        return self.end_position - self.start_position


@dataclass
class EnterpriseConfig:
    """Configuration for enterprise KV cache policies."""
    # Sink configuration
    num_sink_blocks: int = 4  # First N blocks are pinned
    tokens_per_block: int = 16  # Block granularity

    # CTM+ weights
    weight_recency: float = 0.20
    weight_frequency: float = 0.25
    weight_attention: float = 0.30
    weight_importance: float = 0.15
    weight_position: float = 0.10

    # Ghost cache
    ghost_cache_ratio: float = 0.25  # Ghost cache size as ratio of main cache

    # H2O configuration
    h2o_heavy_ratio: float = 0.05  # Top 5% by attention are "heavy hitters"
    h2o_recent_ratio: float = 0.25  # Recent 25% always kept

    # Sampling
    sample_size: int = 32  # For O(k) eviction


@dataclass
class QualityMetrics:
    """Quality metrics for cache evaluation."""
    hit_rate: float = 0.0
    attention_coverage: float = 0.0  # % of attention mass in cache
    important_token_retention: float = 0.0  # % of important tokens retained
    sink_retention: float = 0.0  # Are sinks still in cache?

    # Latency
    latencies_us: list = field(default_factory=list)

    @property
    def p50_latency_us(self) -> float:
        if not self.latencies_us:
            return 0.0
        return statistics.median(self.latencies_us)

    @property
    def p95_latency_us(self) -> float:
        if not self.latencies_us:
            return 0.0
        sorted_lat = sorted(self.latencies_us)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def p99_latency_us(self) -> float:
        if not self.latencies_us:
            return 0.0
        sorted_lat = sorted(self.latencies_us)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]


class GhostCache:
    """
    Ghost cache for tracking recently evicted blocks.
    Used for regret-based adaptation (like ARC's B1/B2).
    """

    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self.entries: OrderedDict = OrderedDict()  # block_id -> eviction_time
        self.ghost_hits = 0
        self.ghost_misses = 0

    def record_eviction(self, block_id: int, eviction_time: int):
        """Record a block eviction."""
        if len(self.entries) >= self.max_entries:
            self.entries.popitem(last=False)
        self.entries[block_id] = eviction_time

    def check_and_remove(self, block_id: int) -> bool:
        """Check if block was recently evicted (ghost hit)."""
        if block_id in self.entries:
            self.ghost_hits += 1
            del self.entries[block_id]
            return True
        self.ghost_misses += 1
        return False

    @property
    def ghost_hit_rate(self) -> float:
        total = self.ghost_hits + self.ghost_misses
        return self.ghost_hits / total if total > 0 else 0.0


class EnterpriseKVCache:
    """
    Enterprise-grade KV cache simulator with industry-realistic policies.
    """

    TOKEN_IMPORTANCE = {
        "bos": 1.0,
        "system": 0.95,
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
        max_blocks: int,
        policy: EnterprisePolicy,
        config: Optional[EnterpriseConfig] = None,
    ):
        self.max_blocks = max_blocks
        self.policy = policy
        self.config = config or EnterpriseConfig()

        # Cache state (block-level, not token-level)
        self.cache: dict[int, BlockMetadata] = {}
        self.current_time = 0

        # LRU tracking
        self.lru_order: OrderedDict = OrderedDict()

        # Ghost cache for regret tracking
        ghost_size = int(max_blocks * self.config.ghost_cache_ratio)
        self.ghost_cache = GhostCache(max(ghost_size, 16))

        # Adaptation parameter (like ARC's p)
        self.adapt_param = 0.5  # Balance between recency and frequency

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "ghost_hits": 0,
            "pinned_blocks": 0,
        }

        # For attention tracking
        self.total_attention_mass = 0.0
        self.cached_attention_mass = 0.0

        # Important positions for quality tracking
        self.important_positions: set = set()

        # Latency tracking
        self.latencies: list = []

    def reset(self):
        """Reset cache state."""
        self.cache.clear()
        self.lru_order.clear()
        self.ghost_cache = GhostCache(int(self.max_blocks * self.config.ghost_cache_ratio))
        self.current_time = 0
        self.adapt_param = 0.5
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "ghost_hits": 0, "pinned_blocks": 0}
        self.total_attention_mass = 0.0
        self.cached_attention_mass = 0.0
        self.latencies.clear()

    def access_block(
        self,
        block_id: int,
        start_pos: int,
        end_pos: int,
        attention_weight: float,
        token_types: list[str],
    ) -> tuple[bool, float]:
        """
        Access a KV block.
        Returns (is_hit, latency_us).
        """
        start_time = time.perf_counter()
        self.current_time += 1

        # Track attention mass
        self.total_attention_mass += attention_weight

        # Mark important positions
        for i, tt in enumerate(token_types):
            if tt in ("bos", "entity", "system", "instruction"):
                self.important_positions.add(start_pos + i)

        if block_id in self.cache:
            # Cache hit
            self.stats["hits"] += 1
            block = self.cache[block_id]
            block.last_access_time = self.current_time
            block.access_count += 1
            block.cumulative_attention += attention_weight
            block.attention_samples += 1

            # Update attention mass in cache
            self.cached_attention_mass += attention_weight

            # Update LRU order
            if block_id in self.lru_order:
                self.lru_order.move_to_end(block_id)

            latency = (time.perf_counter() - start_time) * 1e6
            self.latencies.append(latency)
            return True, latency
        else:
            # Cache miss
            self.stats["misses"] += 1

            # Check ghost cache for adaptation
            if self.ghost_cache.check_and_remove(block_id):
                self.stats["ghost_hits"] += 1
                # Increase preference for frequency (we evicted something we needed)
                self.adapt_param = min(1.0, self.adapt_param + 0.1)

            # Evict if necessary
            while len(self.cache) >= self.max_blocks:
                self._evict()

            # Determine if this block should be pinned (sink)
            is_pinned = block_id < self.config.num_sink_blocks
            if is_pinned:
                self.stats["pinned_blocks"] += 1

            # Insert new block
            self.cache[block_id] = BlockMetadata(
                block_id=block_id,
                start_position=start_pos,
                end_position=end_pos,
                created_time=self.current_time,
                last_access_time=self.current_time,
                access_count=1,
                cumulative_attention=attention_weight,
                attention_samples=1,
                is_pinned=is_pinned,
                token_types=token_types,
            )
            self.lru_order[block_id] = True

            latency = (time.perf_counter() - start_time) * 1e6
            self.latencies.append(latency)
            return False, latency

    def _evict(self):
        """Evict a block based on policy."""
        if not self.cache:
            return

        self.stats["evictions"] += 1
        victim_id = self._select_victim()

        if victim_id is not None:
            # Record in ghost cache before eviction
            self.ghost_cache.record_eviction(victim_id, self.current_time)

            # Update cached attention mass
            block = self.cache[victim_id]
            if block.attention_samples > 0:
                self.cached_attention_mass -= block.avg_attention * block.attention_samples

            # Evict
            del self.cache[victim_id]
            if victim_id in self.lru_order:
                del self.lru_order[victim_id]

    def _select_victim(self) -> Optional[int]:
        """Select victim based on policy."""
        # Get non-pinned candidates
        candidates = [bid for bid, block in self.cache.items() if not block.is_pinned]

        if not candidates:
            # All blocks are pinned, must evict oldest pinned (shouldn't happen normally)
            if self.cache:
                return min(self.cache.keys(), key=lambda b: self.cache[b].last_access_time)
            return None

        if self.policy == EnterprisePolicy.LRU:
            return self._victim_lru(candidates)

        elif self.policy == EnterprisePolicy.FIFO:
            return self._victim_fifo(candidates)

        elif self.policy == EnterprisePolicy.RANDOM:
            return random.choice(candidates)

        elif self.policy == EnterprisePolicy.SINK_LRU:
            # Same as LRU but sinks are already excluded from candidates
            return self._victim_lru(candidates)

        elif self.policy == EnterprisePolicy.ATTENTION_LRU:
            return self._victim_attention_lru(candidates)

        elif self.policy == EnterprisePolicy.INDUSTRY_BASELINE:
            return self._victim_industry_baseline(candidates)

        elif self.policy == EnterprisePolicy.H2O:
            return self._victim_h2o(candidates)

        elif self.policy == EnterprisePolicy.CTM_PLUS:
            return self._victim_ctm_plus(candidates)

        return candidates[0]

    def _victim_lru(self, candidates: list[int]) -> int:
        """Pure LRU victim selection."""
        return min(candidates, key=lambda b: self.cache[b].last_access_time)

    def _victim_fifo(self, candidates: list[int]) -> int:
        """Pure FIFO victim selection."""
        return min(candidates, key=lambda b: self.cache[b].created_time)

    def _victim_attention_lru(self, candidates: list[int]) -> int:
        """Attention-weighted LRU: balance recency with attention."""
        def score(block_id):
            block = self.cache[block_id]
            recency = self.current_time - block.last_access_time
            attention = block.avg_attention + 1e-10
            # Lower score = more likely to evict
            return recency / attention

        return max(candidates, key=score)

    def _victim_industry_baseline(self, candidates: list[int]) -> int:
        """
        Industry baseline: Sink-pinned + Attention-weighted LRU + Ghost adaptation.

        This approximates what production systems at big labs use:
        - Sinks are already pinned (excluded from candidates)
        - Balance recency and attention
        - Adapt based on ghost hits
        """
        def score(block_id):
            block = self.cache[block_id]

            # Recency component (higher age = lower score)
            age = self.current_time - block.last_access_time
            max_age = max(1, self.current_time - min(b.created_time for b in self.cache.values()))
            recency_score = 1.0 - (age / max_age)

            # Attention component
            max_attn = max(b.avg_attention for b in self.cache.values()) + 1e-10
            attention_score = block.avg_attention / max_attn

            # Frequency component
            max_freq = max(b.access_count for b in self.cache.values()) + 1
            freq_score = block.access_count / max_freq

            # Weighted combination (adapt_param balances recency vs frequency/attention)
            combined = (
                (1 - self.adapt_param) * recency_score +
                self.adapt_param * 0.6 * attention_score +
                self.adapt_param * 0.4 * freq_score
            )
            return combined

        # Evict lowest scoring
        return min(candidates, key=score)

    def _victim_h2o(self, candidates: list[int]) -> int:
        """
        H2O (Heavy-Hitter Oracle) policy.

        From "H2O: Heavy-Hitter Oracle for Efficient Generative Inference" (Zhang et al.)
        - Keep recent tokens (sliding window)
        - Keep heavy hitters (high cumulative attention)
        """
        blocks = [(bid, self.cache[bid]) for bid in candidates]

        # Sort by position to find recent window
        blocks.sort(key=lambda x: x[1].start_position, reverse=True)

        num_blocks = len(blocks)
        recent_count = max(1, int(num_blocks * self.config.h2o_recent_ratio))
        heavy_count = max(1, int(num_blocks * self.config.h2o_heavy_ratio))

        # Recent blocks are protected
        recent_blocks = set(b[0] for b in blocks[:recent_count])

        # Heavy hitters are protected
        blocks.sort(key=lambda x: x[1].cumulative_attention, reverse=True)
        heavy_blocks = set(b[0] for b in blocks[:heavy_count])

        protected = recent_blocks | heavy_blocks

        # Evict from unprotected (oldest first)
        evictable = [b for b in candidates if b not in protected]
        if evictable:
            return min(evictable, key=lambda b: self.cache[b].last_access_time)

        # If all protected, evict lowest attention non-recent
        non_recent = [b for b in candidates if b not in recent_blocks]
        if non_recent:
            return min(non_recent, key=lambda b: self.cache[b].cumulative_attention)

        # Last resort: oldest
        return min(candidates, key=lambda b: self.cache[b].created_time)

    def _victim_ctm_plus(self, candidates: list[int]) -> int:
        """CTM+ multi-signal victim selection with O(k) sampling."""
        # Sample for efficiency
        sample_size = min(self.config.sample_size, len(candidates))
        sampled = random.sample(candidates, sample_size)

        def score(block_id):
            block = self.cache[block_id]
            s = 0.0

            # Recency signal
            age = self.current_time - block.last_access_time
            half_life = 100
            recency = math.exp(-0.693 * age / half_life)
            s += self.config.weight_recency * recency

            # Frequency signal
            freq_norm = min(1.0, block.access_count / 50)
            s += self.config.weight_frequency * freq_norm

            # Attention signal
            max_attn = max(self.cache[b].avg_attention for b in sampled) + 1e-10
            attn_norm = block.avg_attention / max_attn
            s += self.config.weight_attention * attn_norm

            # Importance signal (based on token types)
            if block.token_types:
                importance = max(self.TOKEN_IMPORTANCE.get(t, 0.4) for t in block.token_types)
            else:
                importance = 0.4
            s += self.config.weight_importance * importance

            # Position signal (sinks get bonus even if not pinned)
            position_score = 0.3
            if block.block_id < self.config.num_sink_blocks * 2:
                position_score = 0.8
            s += self.config.weight_position * position_score

            return s

        # Evict lowest scoring
        return min(sampled, key=score)

    def get_quality_metrics(self) -> QualityMetrics:
        """Compute quality metrics."""
        metrics = QualityMetrics()

        # Hit rate
        total = self.stats["hits"] + self.stats["misses"]
        metrics.hit_rate = self.stats["hits"] / total if total > 0 else 0.0

        # Attention coverage
        if self.total_attention_mass > 0:
            # Approximate: attention mass currently representable
            current_mass = sum(
                b.cumulative_attention for b in self.cache.values()
            )
            metrics.attention_coverage = min(1.0, current_mass / self.total_attention_mass)

        # Important token retention
        if self.important_positions:
            retained = sum(
                1 for pos in self.important_positions
                if any(b.start_position <= pos < b.end_position for b in self.cache.values())
            )
            metrics.important_token_retention = retained / len(self.important_positions)

        # Sink retention
        sink_blocks = [b for b in self.cache.values() if b.block_id < self.config.num_sink_blocks]
        metrics.sink_retention = len(sink_blocks) / self.config.num_sink_blocks if self.config.num_sink_blocks > 0 else 1.0

        # Latencies
        metrics.latencies_us = self.latencies.copy()

        return metrics

    @property
    def hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total > 0 else 0.0


class EnterpriseWorkloadGenerator:
    """
    Generates realistic enterprise workloads for KV cache benchmarking.
    """

    def __init__(self, seed: int = 42):
        self.random = random.Random(seed)

    def long_context_generation(
        self,
        context_length: int = 32768,
        tokens_per_block: int = 16,
        generation_length: int = 1024,
    ) -> list[tuple[int, int, int, float, list[str]]]:
        """
        Simulates long-context generation (32K+ context).

        Returns: list of (block_id, start_pos, end_pos, attention, token_types)
        """
        accesses = []
        num_context_blocks = context_length // tokens_per_block

        # Phase 1: Prefill (process entire context)
        for block_id in range(num_context_blocks):
            start_pos = block_id * tokens_per_block
            end_pos = start_pos + tokens_per_block

            # Attention pattern: sinks + recent
            if block_id < 4:
                attention = 0.15 / 4  # High attention to sinks
            elif block_id > num_context_blocks - 64:
                attention = 0.55 / 64  # High attention to recent
            else:
                attention = 0.30 / (num_context_blocks - 68)  # Low attention to middle

            token_types = self._generate_token_types(tokens_per_block, start_pos)
            accesses.append((block_id, start_pos, end_pos, attention, token_types))

        # Phase 2: Generation (each new token attends to context)
        for gen_step in range(generation_length):
            current_pos = context_length + gen_step

            # New token attends to subset of context
            # Attention pattern shifts as we generate
            attended_blocks = []

            # Always attend to sinks
            for b in range(4):
                attended_blocks.append((b, 0.10 / 4))

            # Attend to some middle context (sparse)
            num_middle = self.random.randint(8, 32)
            middle_blocks = self.random.sample(
                range(4, num_context_blocks - 64),
                min(num_middle, num_context_blocks - 68)
            )
            for b in middle_blocks:
                attended_blocks.append((b, 0.20 / num_middle))

            # Attend to recent context
            recent_start = max(4, num_context_blocks - 64)
            for b in range(recent_start, num_context_blocks):
                attended_blocks.append((b, 0.40 / (num_context_blocks - recent_start)))

            # Attend to recently generated
            gen_blocks_start = num_context_blocks
            current_block = context_length // tokens_per_block + gen_step // tokens_per_block
            for b in range(gen_blocks_start, current_block + 1):
                attended_blocks.append((b, 0.30 / max(1, current_block - gen_blocks_start + 1)))

            for block_id, attention in attended_blocks:
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block
                token_types = self._generate_token_types(tokens_per_block, start_pos)
                accesses.append((block_id, start_pos, end_pos, attention, token_types))

        return accesses

    def multi_tenant_batch(
        self,
        num_sequences: int = 8,
        context_length: int = 4096,
        tokens_per_block: int = 16,
    ) -> list[tuple[int, int, int, float, list[str]]]:
        """
        Simulates multi-tenant batch inference with shared cache pressure.

        Each sequence has its own context, competing for cache space.
        """
        accesses = []
        blocks_per_seq = context_length // tokens_per_block

        for seq_id in range(num_sequences):
            seq_offset = seq_id * blocks_per_seq

            for block_idx in range(blocks_per_seq):
                block_id = seq_offset + block_idx
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block

                # Each sequence has its own attention pattern
                if block_idx < 4:
                    attention = 0.12 / 4
                elif block_idx > blocks_per_seq - 32:
                    attention = 0.58 / 32
                else:
                    attention = 0.30 / (blocks_per_seq - 36)

                token_types = self._generate_token_types(tokens_per_block, start_pos)
                accesses.append((block_id, start_pos, end_pos, attention, token_types))

        # Interleaved generation: sequences take turns generating
        for gen_round in range(64):  # 64 tokens per sequence
            for seq_id in range(num_sequences):
                seq_offset = seq_id * blocks_per_seq

                # Each generation step re-accesses key blocks
                for block_idx in [0, 1, 2, 3]:  # Sinks
                    block_id = seq_offset + block_idx
                    start_pos = block_id * tokens_per_block
                    end_pos = start_pos + tokens_per_block
                    token_types = self._generate_token_types(tokens_per_block, start_pos)
                    accesses.append((block_id, start_pos, end_pos, 0.08, token_types))

                # Recent blocks
                for block_idx in range(blocks_per_seq - 8, blocks_per_seq):
                    block_id = seq_offset + block_idx
                    start_pos = block_id * tokens_per_block
                    end_pos = start_pos + tokens_per_block
                    token_types = self._generate_token_types(tokens_per_block, start_pos)
                    accesses.append((block_id, start_pos, end_pos, 0.05, token_types))

        return accesses

    def document_qa_rag(
        self,
        doc_length: int = 8192,
        num_queries: int = 10,
        tokens_per_block: int = 16,
    ) -> list[tuple[int, int, int, float, list[str]]]:
        """
        Simulates RAG-style document QA with entity-focused attention.
        """
        accesses = []
        num_doc_blocks = doc_length // tokens_per_block

        # Define entity positions (things questions will ask about)
        entity_blocks = self.random.sample(range(num_doc_blocks), min(20, num_doc_blocks // 10))

        # Phase 1: Index document
        for block_id in range(num_doc_blocks):
            start_pos = block_id * tokens_per_block
            end_pos = start_pos + tokens_per_block

            # Low uniform attention during indexing
            attention = 1.0 / num_doc_blocks

            if block_id in entity_blocks:
                token_types = ["entity"] * tokens_per_block
            else:
                token_types = self._generate_token_types(tokens_per_block, start_pos)

            accesses.append((block_id, start_pos, end_pos, attention, token_types))

        # Phase 2: Answer queries (entity-focused attention)
        for q in range(num_queries):
            # Each query focuses on different entities
            query_entities = self.random.sample(entity_blocks, min(3, len(entity_blocks)))

            # High attention to queried entities
            for block_id in query_entities:
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block
                token_types = ["entity"] * tokens_per_block
                accesses.append((block_id, start_pos, end_pos, 0.25, token_types))

            # Some attention to sinks
            for block_id in range(min(4, num_doc_blocks)):
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block
                token_types = self._generate_token_types(tokens_per_block, start_pos)
                accesses.append((block_id, start_pos, end_pos, 0.05, token_types))

            # Low attention to context around entities
            for entity_block in query_entities:
                for offset in [-2, -1, 1, 2]:
                    block_id = entity_block + offset
                    if 0 <= block_id < num_doc_blocks:
                        start_pos = block_id * tokens_per_block
                        end_pos = start_pos + tokens_per_block
                        token_types = self._generate_token_types(tokens_per_block, start_pos)
                        accesses.append((block_id, start_pos, end_pos, 0.02, token_types))

        return accesses

    def code_completion(
        self,
        file_length: int = 4096,
        tokens_per_block: int = 16,
        num_completions: int = 20,
    ) -> list[tuple[int, int, int, float, list[str]]]:
        """
        Simulates code completion with function/class-focused attention.
        """
        accesses = []
        num_blocks = file_length // tokens_per_block

        # Define function boundaries (code structure)
        num_functions = num_blocks // 8
        function_starts = sorted(self.random.sample(range(num_blocks), num_functions))

        # Initial file load
        for block_id in range(num_blocks):
            start_pos = block_id * tokens_per_block
            end_pos = start_pos + tokens_per_block

            if block_id in function_starts:
                token_types = ["code"] * tokens_per_block
                attention = 0.02
            else:
                token_types = self._generate_token_types(tokens_per_block, start_pos)
                attention = 0.005

            accesses.append((block_id, start_pos, end_pos, attention, token_types))

        # Code completions (high attention to current function + imports)
        for comp in range(num_completions):
            # Pick a random position to complete
            current_block = self.random.randint(0, num_blocks - 1)

            # Find containing function
            containing_func = 0
            for fs in function_starts:
                if fs <= current_block:
                    containing_func = fs
                else:
                    break

            # High attention to current function blocks
            func_end = min(containing_func + 8, num_blocks)
            for block_id in range(containing_func, func_end):
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block
                token_types = ["code"] * tokens_per_block
                accesses.append((block_id, start_pos, end_pos, 0.08, token_types))

            # Medium attention to imports/header (first blocks)
            for block_id in range(min(4, num_blocks)):
                start_pos = block_id * tokens_per_block
                end_pos = start_pos + tokens_per_block
                token_types = ["code"] * tokens_per_block
                accesses.append((block_id, start_pos, end_pos, 0.04, token_types))

            # Low attention to other function signatures
            for fs in function_starts:
                if fs != containing_func:
                    start_pos = fs * tokens_per_block
                    end_pos = start_pos + tokens_per_block
                    token_types = ["code"] * tokens_per_block
                    accesses.append((fs, start_pos, end_pos, 0.01, token_types))

        return accesses

    def _generate_token_types(self, count: int, start_pos: int) -> list[str]:
        """Generate realistic token type distribution."""
        types = []
        for i in range(count):
            pos = start_pos + i
            if pos == 0:
                types.append("bos")
            elif pos < 20 and self.random.random() < 0.5:
                types.append("system")
            elif self.random.random() < 0.05:
                types.append("entity")
            elif self.random.random() < 0.03:
                types.append("number")
            elif self.random.random() < 0.08:
                types.append("punctuation")
            else:
                types.append("regular")
        return types


def run_enterprise_benchmark(
    workload: list[tuple[int, int, int, float, list[str]]],
    max_blocks: int,
    policies: list[EnterprisePolicy],
    config: Optional[EnterpriseConfig] = None,
) -> dict[str, dict]:
    """
    Run benchmark comparing enterprise policies.

    Returns dict mapping policy name to metrics.
    """
    results = {}

    for policy in policies:
        cache = EnterpriseKVCache(max_blocks, policy, config)

        start_time = time.perf_counter()
        for block_id, start_pos, end_pos, attention, token_types in workload:
            cache.access_block(block_id, start_pos, end_pos, attention, token_types)
        elapsed = time.perf_counter() - start_time

        metrics = cache.get_quality_metrics()

        results[policy.value] = {
            "hit_rate": metrics.hit_rate,
            "attention_coverage": metrics.attention_coverage,
            "important_retention": metrics.important_token_retention,
            "sink_retention": metrics.sink_retention,
            "p50_latency_us": metrics.p50_latency_us,
            "p95_latency_us": metrics.p95_latency_us,
            "p99_latency_us": metrics.p99_latency_us,
            "evictions": cache.stats["evictions"],
            "ghost_hits": cache.stats["ghost_hits"],
            "elapsed_seconds": elapsed,
            "throughput": len(workload) / elapsed if elapsed > 0 else 0,
        }

    return results


def quality_under_pressure_test(
    cache_ratios: list[float],
    policies: list[EnterprisePolicy],
    context_length: int = 8192,
    tokens_per_block: int = 16,
) -> dict[str, dict[float, dict]]:
    """
    Test quality metrics at different memory pressure levels.

    This is the key test: can we maintain quality with less memory?
    """
    results = {p.value: {} for p in policies}
    gen = EnterpriseWorkloadGenerator(seed=42)

    num_blocks = context_length // tokens_per_block
    workload = gen.long_context_generation(
        context_length=context_length,
        tokens_per_block=tokens_per_block,
        generation_length=256,
    )

    for ratio in cache_ratios:
        max_blocks = max(8, int(num_blocks * ratio))
        config = EnterpriseConfig(tokens_per_block=tokens_per_block)

        for policy in policies:
            cache = EnterpriseKVCache(max_blocks, policy, config)

            for block_id, start_pos, end_pos, attention, token_types in workload:
                cache.access_block(block_id, start_pos, end_pos, attention, token_types)

            metrics = cache.get_quality_metrics()
            results[policy.value][ratio] = {
                "hit_rate": metrics.hit_rate,
                "attention_coverage": metrics.attention_coverage,
                "important_retention": metrics.important_token_retention,
                "sink_retention": metrics.sink_retention,
            }

    return results


if __name__ == "__main__":
    print("Enterprise KV Cache Benchmark")
    print("=" * 60)

    # Quick test
    gen = EnterpriseWorkloadGenerator()
    workload = gen.long_context_generation(context_length=4096, generation_length=128)

    policies = [
        EnterprisePolicy.LRU,
        EnterprisePolicy.SINK_LRU,
        EnterprisePolicy.ATTENTION_LRU,
        EnterprisePolicy.INDUSTRY_BASELINE,
        EnterprisePolicy.H2O,
        EnterprisePolicy.CTM_PLUS,
    ]

    max_blocks = 64  # 25% of context
    results = run_enterprise_benchmark(workload, max_blocks, policies)

    print("\nResults (25% cache ratio):")
    print("-" * 60)
    print("{:<20} {:>10} {:>12} {:>12}".format("Policy", "Hit Rate", "Attn Cov", "Imp Retain"))
    print("-" * 60)

    for policy in policies:
        r = results[policy.value]
        print("{:<20} {:>9.1f}% {:>11.1f}% {:>11.1f}%".format(
            policy.value,
            r["hit_rate"] * 100,
            r["attention_coverage"] * 100,
            r["important_retention"] * 100,
        ))
