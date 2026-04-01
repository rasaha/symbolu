"""
TurboQuant + CTM+ Integrated KV Cache Simulator

Combines TurboQuant's mathematical compression (PolarQuant + QJL) with
CTM+'s intelligent multi-signal eviction to measure the combined benefit:

  - TurboQuant alone: more tokens fit in memory (6x), but LRU eviction
  - CTM+ alone: smart eviction, but FP16 storage limits capacity
  - Combined: smart eviction over 6x more tokens = multiplicative benefit

The integration works at two levels:
  1. Capacity expansion: TurboQuant-compressed tokens take less memory,
     so the effective cache size is multiplied by the compression ratio.
  2. Quality-aware scoring: Compression quality metrics (MSE, cosine sim)
     feed into CTM+'s scoring to protect high-importance tokens that
     compress poorly and might benefit from higher precision.
"""

import math
import time
import random
from dataclasses import dataclass, field
from typing import Optional
from collections import deque
from enum import Enum

import numpy as np

from .turboquant import TurboQuantCompressor, TurboQuantConfig, MemoryBudget
from .kv_cache_simulator import (
    EvictionPolicy,
    TokenMetadata,
    CTMKVConfig,
    KVCacheSimulator,
    AttentionPatternGenerator,
    WorkloadGenerator,
)


class IntegrationMode(Enum):
    """How TurboQuant integrates with the eviction policy."""
    CAPACITY_ONLY = "capacity_only"
    # TurboQuant expands effective cache size; eviction policy unchanged
    QUALITY_AWARE = "quality_aware"
    # TurboQuant expands cache + compression quality informs eviction scoring


@dataclass
class TurboQuantTokenState:
    """Extended token state with compression metadata."""
    position: int
    token_type: str = "regular"
    created_time: int = 0
    last_access_time: int = 0
    access_count: int = 0
    attention_weights: list = field(default_factory=list)

    # TurboQuant compression quality for this token's KV vectors
    compression_mse: float = 0.0
    cosine_similarity: float = 1.0
    # Original vector norm (importance proxy)
    original_norm: float = 1.0
    # Whether this token's vectors are stored compressed
    is_compressed: bool = True

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

    @property
    def compression_quality(self) -> float:
        """0-1 score: how well this token compressed (1 = perfect)."""
        return self.cosine_similarity


@dataclass
class IntegratedConfig:
    """Configuration for the integrated TurboQuant + CTM+ system."""
    # TurboQuant compression settings
    tq_config: TurboQuantConfig = field(
        default_factory=lambda: TurboQuantConfig.three_bit()
    )
    # CTM+ eviction settings
    ctm_config: CTMKVConfig = field(default_factory=CTMKVConfig)
    # Integration mode
    mode: IntegrationMode = IntegrationMode.QUALITY_AWARE
    # Weight for compression quality in scoring (quality-aware mode)
    weight_compression_quality: float = 0.05
    # Skip actual PolarQuant compression (use statistical model instead)
    # Much faster for large-scale benchmarks where hit rate is the metric
    fast_mode: bool = False

    @classmethod
    def three_bit_chatbot(cls) -> "IntegratedConfig":
        return cls(
            tq_config=TurboQuantConfig.three_bit(),
            ctm_config=CTMKVConfig.for_chatbot(),
        )

    @classmethod
    def four_bit_long_context(cls) -> "IntegratedConfig":
        return cls(
            tq_config=TurboQuantConfig.four_bit(),
            ctm_config=CTMKVConfig.for_long_context(),
        )

    @classmethod
    def three_bit_long_context(cls) -> "IntegratedConfig":
        return cls(
            tq_config=TurboQuantConfig.three_bit(),
            ctm_config=CTMKVConfig.for_long_context(),
        )


class TurboQuantCTMSimulator:
    """
    Integrated KV cache simulator with TurboQuant compression + CTM+ eviction.

    Key difference from standalone KVCacheSimulator:
    - max_tokens is multiplied by TurboQuant's compression ratio
    - Token scoring optionally considers compression quality
    - Simulates realistic KV vector compression for quality measurement
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
        base_max_tokens: int,
        config: IntegratedConfig,
    ):
        """
        Args:
            base_max_tokens: Cache capacity in FP16 tokens (before compression)
            config: Integrated configuration
        """
        self.base_max_tokens = base_max_tokens
        self.config = config

        # Effective capacity after TurboQuant compression
        self.effective_max_tokens = int(
            base_max_tokens * config.tq_config.compression_ratio
        )

        # Compression engine
        self.compressor = TurboQuantCompressor(config.tq_config)
        self.rng = np.random.RandomState(config.tq_config.seed + 2000)

        # Cache state
        self.cache: dict[int, TurboQuantTokenState] = {}
        self.current_time = 0
        self.lru_order: deque = deque()

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_accesses": 0,
            "compression_mse_sum": 0.0,
            "compression_cosine_sum": 0.0,
            "tokens_compressed": 0,
        }

    def reset(self):
        """Reset simulator state."""
        self.cache.clear()
        self.lru_order.clear()
        self.current_time = 0
        self.stats = {
            "hits": 0, "misses": 0, "evictions": 0, "total_accesses": 0,
            "compression_mse_sum": 0.0, "compression_cosine_sum": 0.0,
            "tokens_compressed": 0,
        }
        self.compressor = TurboQuantCompressor(self.config.tq_config)

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> bool:
        """Access a token. Returns True if hit."""
        self.current_time += 1
        self.stats["total_accesses"] += 1

        if position in self.cache:
            self.stats["hits"] += 1
            meta = self.cache[position]
            meta.last_access_time = self.current_time
            meta.access_count += 1
            meta.attention_weights.append(attention_weight)
            if len(meta.attention_weights) > 100:
                meta.attention_weights = meta.attention_weights[-100:]

            if position in self.lru_order:
                self.lru_order.remove(position)
            self.lru_order.append(position)
            return True
        else:
            self.stats["misses"] += 1

            while len(self.cache) >= self.effective_max_tokens:
                self._evict()

            # Simulate TurboQuant compression of this token's KV vectors
            comp_quality = self._simulate_compression(token_type)

            self.cache[position] = TurboQuantTokenState(
                position=position,
                token_type=token_type,
                created_time=self.current_time,
                last_access_time=self.current_time,
                access_count=1,
                attention_weights=[attention_weight],
                compression_mse=comp_quality["mse"],
                cosine_similarity=comp_quality["cosine_similarity"],
                original_norm=comp_quality["original_norm"],
            )
            self.lru_order.append(position)
            return False

    def _simulate_compression(self, token_type: str) -> dict:
        """Simulate TurboQuant compression quality for a token's KV vector."""
        importance = self.TOKEN_IMPORTANCE.get(token_type, 0.4)

        # Fast mode: use statistical model based on benchmark data
        # (avg cosine ~0.965 at 3-bit, ~0.991 at 4-bit from Section 1)
        if self.config.fast_mode:
            bits = self.config.tq_config.angle_bits
            if bits <= 2:
                cosine = 0.858 + self.rng.uniform(-0.02, 0.02)
                mse = 0.016 + self.rng.uniform(-0.002, 0.002)
            elif bits == 3:
                cosine = 0.965 + self.rng.uniform(-0.01, 0.01)
                mse = 0.004 + self.rng.uniform(-0.001, 0.001)
            else:
                cosine = 0.991 + self.rng.uniform(-0.005, 0.005)
                mse = 0.001 + self.rng.uniform(-0.0005, 0.0005)
            # Important tokens compress slightly worse
            if importance > 0.7:
                cosine -= 0.005
                mse += 0.001
            base_norm = 1.0 + importance * 2.0
            self.stats["tokens_compressed"] += 1
            self.stats["compression_mse_sum"] += mse
            self.stats["compression_cosine_sum"] += cosine
            return {
                "mse": mse,
                "cosine_similarity": min(1.0, cosine),
                "original_norm": base_norm,
            }

        d = self.config.tq_config.head_dim

        # Generate a realistic KV vector based on token type
        # Important tokens tend to have higher-norm, more structured vectors
        base_norm = 1.0 + importance * 2.0

        vector = self.rng.randn(d).astype(np.float32)
        vector = vector / (np.linalg.norm(vector) + 1e-10) * base_norm

        # Add structure for important tokens (they have more energy in
        # specific directions, making them slightly harder to compress)
        if importance > 0.7:
            dominant_dims = max(1, int(d * 0.1))
            vector[:dominant_dims] *= 2.0

        # Compress and measure quality
        compressed = self.compressor.compress(vector)
        metrics = self.compressor.quality_metrics(vector, compressed)

        self.stats["tokens_compressed"] += 1
        self.stats["compression_mse_sum"] += metrics["mse"]
        self.stats["compression_cosine_sum"] += metrics["cosine_similarity"]

        return {
            "mse": metrics["mse"],
            "cosine_similarity": metrics["cosine_similarity"],
            "original_norm": float(np.linalg.norm(vector)),
        }

    def _evict(self):
        """Evict using CTM+ multi-signal scoring."""
        if not self.cache:
            return

        self.stats["evictions"] += 1
        victim = self._ctm_select_victim()
        del self.cache[victim]
        if victim in self.lru_order:
            self.lru_order.remove(victim)

    def _ctm_select_victim(self) -> int:
        """Select victim using CTM+ scoring (optionally quality-aware)."""
        sample_size = min(64, len(self.cache))
        candidates = random.sample(list(self.cache.keys()), sample_size)

        scores = [(pos, self._score(pos)) for pos in candidates]
        scores.sort(key=lambda x: x[1])
        return scores[0][0]

    def _score(self, position: int) -> float:
        """
        Calculate token value score. Higher = more valuable = less likely evicted.

        In quality-aware mode, tokens that compressed poorly get a small boost
        because evicting them loses more information (their compressed
        representation is less faithful).
        """
        meta = self.cache[position]
        cfg = self.config.ctm_config
        score = 0.0

        # Signal 1: Recency
        age = self.current_time - meta.last_access_time
        recency = math.exp(-0.693 * age / 100)
        score += cfg.weight_recency * recency

        # Signal 2: Frequency
        freq = min(1.0, meta.access_count / cfg.frequency_window)
        frequency = math.log1p(freq * 10) / math.log1p(10)
        score += cfg.weight_frequency * frequency

        # Signal 3: Attention strength
        if meta.attention_weights:
            avg_attn = meta.avg_attention
            baseline = 1.0 / 1000
            strength = avg_attn / baseline if baseline > 0 else 0
            attention = 1 / (1 + math.exp(-0.5 * (strength - 5)))
        else:
            attention = 0.0
        score += cfg.weight_attention_strength * attention

        # Signal 4: Token importance
        importance = self.TOKEN_IMPORTANCE.get(meta.token_type, 0.4)
        score += cfg.weight_token_importance * importance

        # Signal 5: Position (sinks + recent window)
        seq_len = max(self.cache.keys()) + 1 if self.cache else 1
        position_score = 0.3
        if position < cfg.attention_sink_tokens:
            position_score = 1.0
        elif position > seq_len - cfg.recent_window_size:
            recency_bonus = 1.0 - (seq_len - position) / cfg.recent_window_size
            position_score = max(position_score, recency_bonus)
        score += cfg.weight_position * position_score

        # Signal 6 (quality-aware): Compression quality penalty
        # Tokens that compressed well are "cheaper" to keep because their
        # representation is faithful. Tokens that compressed poorly are
        # more valuable to keep because eviction = more information loss.
        if self.config.mode == IntegrationMode.QUALITY_AWARE:
            # Low cosine similarity = poor compression = higher eviction cost
            quality_penalty = 1.0 - meta.compression_quality
            score += self.config.weight_compression_quality * quality_penalty

        return score

    @property
    def hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        n_comp = max(1, self.stats["tokens_compressed"])
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "cache_size": len(self.cache),
            "base_max_tokens": self.base_max_tokens,
            "effective_max_tokens": self.effective_max_tokens,
            "compression_ratio": self.config.tq_config.compression_ratio,
            "bits_per_element": self.config.tq_config.total_bits_per_element,
            "avg_compression_mse": self.stats["compression_mse_sum"] / n_comp,
            "avg_compression_cosine": self.stats["compression_cosine_sum"] / n_comp,
            "capacity_multiplier": f"{self.config.tq_config.compression_ratio:.1f}x",
        }


# ---------------------------------------------------------------------------
# Benchmark runner: Before vs After comparison
# ---------------------------------------------------------------------------

def run_comparison_benchmark(
    workload: list[tuple[int, str, float]],
    base_max_tokens: int,
    head_dim: int = 128,
    verbose: bool = True,
) -> dict:
    """
    Run comprehensive before/after benchmark comparing:
      1. LRU (baseline, FP16)
      2. CTM+ (smart eviction, FP16)
      3. TurboQuant 4-bit + LRU (compression only)
      4. TurboQuant 3-bit + LRU (compression only)
      5. TurboQuant 4-bit + CTM+ (combined, capacity-only)
      6. TurboQuant 3-bit + CTM+ (combined, quality-aware)

    Returns dict of configuration_name → stats.
    """
    results = {}

    configs = [
        # Baseline: no compression, LRU eviction
        ("LRU (FP16)", None, EvictionPolicy.LRU, None),
        # CTM+ only: smart eviction, FP16
        ("CTM+ (FP16)", None, EvictionPolicy.CTM_PLUS, None),
        # TurboQuant only: compression + LRU
        ("TQ-4bit + LRU", TurboQuantConfig.four_bit(head_dim), None,
         IntegrationMode.CAPACITY_ONLY),
        ("TQ-3bit + LRU", TurboQuantConfig.three_bit(head_dim), None,
         IntegrationMode.CAPACITY_ONLY),
        # Combined: TurboQuant + CTM+
        ("TQ-4bit + CTM+ (capacity)", TurboQuantConfig.four_bit(head_dim), None,
         IntegrationMode.CAPACITY_ONLY),
        ("TQ-3bit + CTM+ (quality-aware)", TurboQuantConfig.three_bit(head_dim), None,
         IntegrationMode.QUALITY_AWARE),
    ]

    for name, tq_config, eviction_policy, integration_mode in configs:
        start = time.perf_counter()

        if tq_config is None:
            # Pure eviction policy, no compression
            sim = KVCacheSimulator(
                base_max_tokens,
                eviction_policy,
                CTMKVConfig(),
            )
            for pos, token_type, attn in workload:
                sim.access(pos, token_type, attn)
            stats = sim.get_stats()
        else:
            # Integrated TurboQuant + eviction
            if "LRU" in name:
                ctm_cfg = CTMKVConfig()
                # For TQ+LRU, we use the integrated simulator but with
                # uniform weights (approximates LRU behavior in scoring)
                ctm_cfg = CTMKVConfig(
                    weight_recency=0.90,
                    weight_frequency=0.05,
                    weight_attention_strength=0.025,
                    weight_token_importance=0.025,
                    weight_position=0.0,
                    weight_sequence_priority=0.0,
                )
            else:
                ctm_cfg = CTMKVConfig()

            int_config = IntegratedConfig(
                tq_config=tq_config,
                ctm_config=ctm_cfg,
                mode=integration_mode,
            )
            sim = TurboQuantCTMSimulator(base_max_tokens, int_config)
            for pos, token_type, attn in workload:
                sim.access(pos, token_type, attn)
            stats = sim.get_stats()

        elapsed = time.perf_counter() - start
        stats["elapsed_seconds"] = elapsed
        stats["accesses_per_second"] = len(workload) / elapsed if elapsed > 0 else 0
        results[name] = stats

    if verbose:
        _print_comparison(results, base_max_tokens)

    return results


def run_quality_preservation_benchmark(
    seq_len: int = 4096,
    base_cache_ratio: float = 0.25,
    head_dim: int = 128,
    verbose: bool = True,
) -> dict:
    """
    Measure how well important tokens are preserved after eviction.

    Compares retention of important tokens across configurations.
    """
    random.seed(42)
    np.random.seed(42)

    base_max_tokens = int(seq_len * base_cache_ratio)
    important_positions = set(random.sample(range(seq_len), seq_len // 10))
    important_positions.update(range(4))  # Always include attention sinks

    workload = WorkloadGenerator(seq_len, seed=42).sequential(seq_len)

    configs = {
        "LRU (FP16)": (None, EvictionPolicy.LRU),
        "CTM+ (FP16)": (None, EvictionPolicy.CTM_PLUS),
        "TQ-3bit + CTM+": (
            TurboQuantConfig.three_bit(head_dim),
            IntegrationMode.QUALITY_AWARE,
        ),
        "TQ-4bit + CTM+": (
            TurboQuantConfig.four_bit(head_dim),
            IntegrationMode.CAPACITY_ONLY,
        ),
    }

    results = {}

    for name, (tq_config, policy_or_mode) in configs.items():
        if tq_config is None:
            sim = KVCacheSimulator(
                base_max_tokens,
                policy_or_mode,
                CTMKVConfig.for_long_context(),
            )
            for pos, token_type, attn in workload:
                if pos in important_positions:
                    attn *= 10
                sim.access(pos, token_type, attn)
            retained = len(important_positions.intersection(sim.cache.keys()))
        else:
            int_config = IntegratedConfig(
                tq_config=tq_config,
                ctm_config=CTMKVConfig.for_long_context(),
                mode=policy_or_mode,
            )
            sim = TurboQuantCTMSimulator(base_max_tokens, int_config)
            for pos, token_type, attn in workload:
                if pos in important_positions:
                    attn *= 10
                sim.access(pos, token_type, attn)
            retained = len(important_positions.intersection(sim.cache.keys()))

        retention_rate = retained / len(important_positions)
        results[name] = {
            "retention_rate": retention_rate,
            "retained_important": retained,
            "total_important": len(important_positions),
            "effective_cache_size": (
                sim.effective_max_tokens if hasattr(sim, "effective_max_tokens")
                else base_max_tokens
            ),
        }

    if verbose:
        print("\n" + "=" * 72)
        print("QUALITY PRESERVATION: Important Token Retention")
        print("=" * 72)
        print(f"  Sequence length: {seq_len:,} tokens")
        print(f"  Base cache ratio: {base_cache_ratio:.0%}")
        print(f"  Important tokens: {len(important_positions)}")
        print()
        print(f"  {'Configuration':<30} {'Retention':>10} {'Eff. Cache':>12} {'Kept':>6}")
        print(f"  {'-'*60}")
        for name, r in results.items():
            print(
                f"  {name:<30} {r['retention_rate']:>9.1%}"
                f" {r['effective_cache_size']:>11,}"
                f" {r['retained_important']:>5}/{r['total_important']}"
            )
        print("=" * 72)

    return results


def _print_comparison(results: dict, base_max_tokens: int):
    """Print formatted comparison table."""
    print("\n" + "=" * 80)
    print("TURBOQUANT + CTM+ INTEGRATION BENCHMARK")
    print("=" * 80)
    print(f"  Base cache capacity (FP16): {base_max_tokens:,} tokens")
    print()

    # Header
    print(f"  {'Configuration':<35} {'Hit Rate':>9} {'Eff.Size':>9}"
          f" {'vs LRU':>9} {'Time':>8}")
    print(f"  {'-'*72}")

    baseline_hr = results.get("LRU (FP16)", {}).get("hit_rate", 0)

    for name, stats in results.items():
        hr = stats.get("hit_rate", 0)
        eff_size = stats.get("effective_max_tokens", stats.get("max_tokens", base_max_tokens))
        vs_lru = hr - baseline_hr
        elapsed = stats.get("elapsed_seconds", 0)

        print(
            f"  {name:<35} {hr:>8.2%}"
            f" {eff_size:>8,}"
            f" {vs_lru:>+8.2%}"
            f" {elapsed:>7.2f}s"
        )

    print(f"  {'-'*72}")

    # Compression details
    print("\n  Compression Details:")
    for name, stats in results.items():
        if "compression_ratio" in stats:
            cr = stats["compression_ratio"]
            bpe = stats.get("bits_per_element", 16)
            avg_cos = stats.get("avg_compression_cosine", 1.0)
            print(
                f"    {name:<33} {cr:>5.1f}x compression"
                f"  {bpe:>5.1f} bits/elem"
                f"  cosine={avg_cos:.4f}"
            )

    print("=" * 80)
