#!/usr/bin/env python3
"""
Long-Context Scaling Benchmark: TurboQuant + CTM+ at 32K-128K Tokens

Tests whether the 90.44% hit rate achieved at 4K scales to production
long-context inference (32K, 65K, 128K tokens).

Key questions:
  1. Does CTM+'s multi-signal scoring still beat LRU at 100K+ tokens?
  2. Does TurboQuant's capacity expansion compound with smart eviction?
  3. Do "sleeping tokens" (accessed at pos 2K, needed at pos 98K) survive?
  4. How does the CXL warm tier (TQ-compressed) affect scaling?

Workloads:
  - Sleeping Tokens: worst case for LRU (dormant-then-critical)
  - Needle-in-Haystack: fact retrieval at arbitrary context depths
  - Multi-Document QA: cross-document references across 50K+ spans
  - Streaming Conversation: multi-turn with callbacks to early turns
  - Code Generation: hierarchical long-range references

Usage:
    python run_long_context_benchmark.py                  # Full (slow)
    python run_long_context_benchmark.py --quick           # Quick mode
    python run_long_context_benchmark.py --workload sleeping_tokens
    python run_long_context_benchmark.py --json results.json
"""

import argparse
import json
import math
import time
import random
import sys
import os
from collections import deque

import numpy as np

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ctm_plus_vllm.turboquant import TurboQuantConfig
from ctm_plus_vllm.turboquant_integration import (
    TurboQuantCTMSimulator,
    IntegratedConfig,
    IntegrationMode,
)
from ctm_plus_vllm.kv_cache_simulator import (
    KVCacheSimulator,
    EvictionPolicy,
    CTMKVConfig,
)
from ctm_plus_vllm.long_context_workloads import (
    LongContextConfig,
    LongContextWorkloadGenerator,
)
from ctm_plus_vllm.research_baselines import (
    H2OSimulator,
    StreamingLLMSimulator,
    TOVASimulator,
)


# ---------------------------------------------------------------------------
# CXL-Pool-Aware Simulator: 3-tier memory hierarchy
# ---------------------------------------------------------------------------

class CXLTieredSimulator:
    """
    3-tier KV cache simulator with TurboQuant + CTM+ + CXL warm pool.

    Memory hierarchy:
      Tier0 (HBM/GPU, FP16): Fastest, smallest — hot blocks
      CXL Pool (shared DRAM, TQ-3bit compressed): Fast, large — warm blocks
      Tier1 (NVMe/CPU, cold): Slowest, unlimited — cold blocks

    On eviction from Tier0:
      - Block is TurboQuant-compressed and placed in CXL pool
      - CXL pool has TQ-expanded capacity (6x the equivalent FP16 budget)
    On eviction from CXL pool:
      - Block goes to Tier1 (cold storage, expensive to retrieve)
    On access:
      - Tier0 hit: fastest (100ns)
      - CXL hit: decompress + promote to Tier0 (300ns)
      - Tier1 hit: slow fetch + promote (10,000ns)
      - Miss: backing store fetch (10,000ns)
    """

    TOKEN_IMPORTANCE = {
        "bos": 1.0, "entity": 0.9, "number": 0.85, "code": 0.8,
        "instruction": 0.75, "eos": 0.5, "regular": 0.4, "punctuation": 0.2,
    }

    def __init__(
        self,
        tier0_tokens: int,
        cxl_budget_tokens: int,
        tq_config: TurboQuantConfig,
        ctm_config: CTMKVConfig,
    ):
        self.tier0_capacity = tier0_tokens
        # CXL pool is TQ-compressed: effective capacity = budget × compression_ratio
        self.cxl_effective_capacity = int(
            cxl_budget_tokens * tq_config.compression_ratio
        )
        self.tq_config = tq_config
        self.ctm_config = ctm_config

        # Token metadata stored per-tier
        self.tier0: dict[int, dict] = {}       # pos -> metadata
        self.cxl_pool: dict[int, dict] = {}    # pos -> metadata (compressed)
        self.tier1_ghost: set[int] = set()     # Tracks what went to cold storage

        self.current_time = 0
        self.stats = {
            "tier0_hits": 0, "cxl_hits": 0, "tier1_hits": 0,
            "misses": 0, "total_accesses": 0,
            "tier0_evictions": 0, "cxl_evictions": 0,
            "promotions_from_cxl": 0, "promotions_from_tier1": 0,
            "total_latency_ns": 0,
            "entity_hits": 0, "entity_accesses": 0,
        }

    def access(
        self,
        position: int,
        token_type: str = "regular",
        attention_weight: float = 0.01,
    ) -> str:
        """Access a token. Returns tier that served it."""
        self.current_time += 1
        self.stats["total_accesses"] += 1
        is_entity = token_type == "entity"
        if is_entity:
            self.stats["entity_accesses"] += 1

        meta_update = {
            "last_access_time": self.current_time,
            "attention_weight": attention_weight,
            "token_type": token_type,
        }

        # Check Tier0 (HBM, fastest)
        if position in self.tier0:
            self.stats["tier0_hits"] += 1
            self.stats["total_latency_ns"] += 100
            if is_entity:
                self.stats["entity_hits"] += 1
            m = self.tier0[position]
            m.update(meta_update)
            m["access_count"] = m.get("access_count", 0) + 1
            attn_hist = m.get("attention_weights")
            if attn_hist is None:
                attn_hist = deque(maxlen=100)
                m["attention_weights"] = attn_hist
            attn_hist.append(attention_weight)
            return "tier0"

        # Check CXL pool (compressed warm tier)
        if position in self.cxl_pool:
            self.stats["cxl_hits"] += 1
            self.stats["promotions_from_cxl"] += 1
            self.stats["total_latency_ns"] += 300  # Decompress + DRAM
            if is_entity:
                self.stats["entity_hits"] += 1

            # Promote to Tier0
            m = self.cxl_pool.pop(position)
            m.update(meta_update)
            m["access_count"] = m.get("access_count", 0) + 1
            attn_hist = m.get("attention_weights")
            if attn_hist is None:
                attn_hist = deque(maxlen=100)
                m["attention_weights"] = attn_hist
            attn_hist.append(attention_weight)
            self._admit_to_tier0(position, m)
            return "cxl"

        # Check Tier1 ghost (cold storage)
        if position in self.tier1_ghost:
            self.stats["tier1_hits"] += 1
            self.stats["promotions_from_tier1"] += 1
            self.stats["total_latency_ns"] += 10000  # NVMe fetch
            self.tier1_ghost.discard(position)

            m = {
                "position": position,
                "access_count": 1,
                "created_time": self.current_time,
                "attention_weights": deque([attention_weight], maxlen=100),
                **meta_update,
            }
            self._admit_to_tier0(position, m)
            return "tier1"

        # Miss
        self.stats["misses"] += 1
        self.stats["total_latency_ns"] += 10000

        m = {
            "position": position,
            "access_count": 1,
            "created_time": self.current_time,
            "attention_weights": deque([attention_weight], maxlen=100),
            **meta_update,
        }
        self._admit_to_tier0(position, m)
        return "miss"

    def _admit_to_tier0(self, position: int, meta: dict):
        """Add to Tier0, evicting to CXL pool if full."""
        while len(self.tier0) >= self.tier0_capacity:
            self._evict_from_tier0()

        self.tier0[position] = meta

    def _evict_from_tier0(self):
        """Evict lowest-scoring token from Tier0 → CXL pool."""
        if not self.tier0:
            return

        self.stats["tier0_evictions"] += 1

        # Pre-compute max_pos once (was O(n) per candidate via max(keys()))
        max_pos = max(self.tier0.keys()) + 1

        # CTM+ multi-signal scoring
        tier0_keys = list(self.tier0.keys())
        sample_size = min(64, len(tier0_keys))
        candidates = random.sample(tier0_keys, sample_size)
        scores = [(pos, self._score(pos, self.tier0, max_pos)) for pos in candidates]
        scores.sort(key=lambda x: x[1])
        victim_pos = scores[0][0]

        victim_meta = self.tier0.pop(victim_pos)

        # Demote to CXL pool (compressed) if pool is enabled
        if self.cxl_effective_capacity > 0:
            while len(self.cxl_pool) >= self.cxl_effective_capacity:
                self._evict_from_cxl()
            self.cxl_pool[victim_pos] = victim_meta
        else:
            # No CXL pool — evict straight to Tier1
            self.tier1_ghost.add(victim_pos)

    def _evict_from_cxl(self):
        """Evict from CXL pool → Tier1 (cold storage)."""
        if not self.cxl_pool:
            return

        self.stats["cxl_evictions"] += 1

        # Simplified scoring for CXL: age + access count
        sample_size = min(32, len(self.cxl_pool))
        candidates = random.sample(list(self.cxl_pool.keys()), sample_size)

        worst_pos = None
        worst_score = float("inf")
        for pos in candidates:
            m = self.cxl_pool[pos]
            age = self.current_time - m.get("last_access_time", 0)
            count = m.get("access_count", 1)
            # Simple age/frequency score
            score = count / (1 + age / 1000)
            if score < worst_score:
                worst_score = score
                worst_pos = pos

        if worst_pos is not None:
            self.cxl_pool.pop(worst_pos)
            self.tier1_ghost.add(worst_pos)

    def _score(self, position: int, tier: dict, max_pos: int) -> float:
        """CTM+ multi-signal scoring for eviction. max_pos is pre-computed."""
        meta = tier[position]
        cfg = self.ctm_config
        score = 0.0

        # Recency
        age = self.current_time - meta.get("last_access_time", 0)
        recency = math.exp(-0.693 * age / 100)
        score += cfg.weight_recency * recency

        # Frequency
        freq = min(1.0, meta.get("access_count", 1) / cfg.frequency_window)
        frequency = math.log1p(freq * 10) / math.log1p(10)
        score += cfg.weight_frequency * frequency

        # Attention strength
        attn_weights = meta.get("attention_weights", [])
        if attn_weights:
            avg_attn = sum(attn_weights) / len(attn_weights)
            baseline = 1.0 / 1000
            strength = avg_attn / baseline if baseline > 0 else 0
            attention = 1 / (1 + math.exp(-0.5 * (strength - 5)))
        else:
            attention = 0.0
        score += cfg.weight_attention_strength * attention

        # Token importance
        importance = self.TOKEN_IMPORTANCE.get(meta.get("token_type", "regular"), 0.4)
        score += cfg.weight_token_importance * importance

        # Position (sinks + recent) — max_pos passed in to avoid O(n) per call
        position_score = 0.3
        if position < cfg.attention_sink_tokens:
            position_score = 1.0
        elif position > max_pos - cfg.recent_window_size:
            recency_bonus = 1.0 - (max_pos - position) / cfg.recent_window_size
            position_score = max(position_score, recency_bonus)
        score += cfg.weight_position * position_score

        return score

    @property
    def hit_rate(self) -> float:
        t = self.stats["total_accesses"]
        if t == 0:
            return 0.0
        return (self.stats["tier0_hits"] + self.stats["cxl_hits"]) / t

    @property
    def combined_hit_rate(self) -> float:
        """Hit rate including tier1 (everything except cold misses)."""
        t = self.stats["total_accesses"]
        if t == 0:
            return 0.0
        return (
            self.stats["tier0_hits"]
            + self.stats["cxl_hits"]
            + self.stats["tier1_hits"]
        ) / t

    @property
    def avg_latency_ns(self) -> float:
        t = self.stats["total_accesses"]
        return self.stats["total_latency_ns"] / t if t > 0 else 0.0

    def get_stats(self) -> dict:
        ea = self.stats["entity_accesses"]
        return {
            **self.stats,
            "hit_rate": self.hit_rate,
            "combined_hit_rate": self.combined_hit_rate,
            "avg_latency_ns": self.avg_latency_ns,
            "entity_hit_rate": self.stats["entity_hits"] / ea if ea > 0 else 0.0,
            "tier0_size": len(self.tier0),
            "cxl_size": len(self.cxl_pool),
            "tier0_capacity": self.tier0_capacity,
            "cxl_capacity": self.cxl_effective_capacity,
        }


# ---------------------------------------------------------------------------
# Benchmark functions
# ---------------------------------------------------------------------------

def run_single_workload(
    workload_name: str,
    workload: list,
    seq_len: int,
    cache_ratio: float,
    head_dim: int = 128,
    verbose: bool = True,
) -> dict:
    """Run all configurations on a single workload."""
    base_tokens = int(seq_len * cache_ratio)
    results = {}

    # At large scales, KVCacheSimulator's deque.remove() is O(n) per access.
    # At 131K with cache=13K, this is ~5 billion ops — way too slow.
    # Use CXL tiered (dict-based, O(1)) for large scales.
    # Flat TQ simulators also use deques so they share the bottleneck.
    use_flat_tq = seq_len <= 16384
    use_flat_baseline = seq_len <= 65536

    # Compute TQ+CXL effective capacity upfront (deterministic from config).
    # Used for the cap-match ablation config.
    tq_cfg_ref = TurboQuantConfig.three_bit(head_dim)
    cxl_eff_capacity = base_tokens + int(base_tokens * 2 * tq_cfg_ref.compression_ratio)

    configs = []

    # Baselines (flat) — skip at very large scales due to O(n) deque
    if use_flat_baseline:
        configs.append(("LRU (FP16)", "lru"))
        configs.append(("CTM+ (FP16)", "ctm"))

    # Capacity-matched ablation: CTM+ with same token budget as TQ+CXL.
    # Uses CXLTieredSimulator (O(1)) so runs at all scales.
    # Isolates how much gain comes from capacity vs smarter eviction.
    configs.append(("CTM+ FP16 (cap-match)", "ctm_cap_match"))

    # Research baselines — always run (dict-based, O(1))
    configs.append(("H2O", "h2o"))
    configs.append(("StreamingLLM", "streamingllm"))
    configs.append(("TOVA", "tova"))

    # Add flat TQ configs at small scales
    if use_flat_tq:
        configs.append(("TQ-3bit + LRU", "tq_lru"))
        configs.append(("TQ-3bit + CTM+", "tq_ctm"))

    # CXL tiered — always run (uses dicts, O(1) per access)
    configs.append(("TQ-3bit + CTM+ + CXL", "tiered"))

    # At 131K+ where baselines are skipped, add a fast LRU-equivalent
    if not use_flat_baseline:
        configs.insert(0, ("LRU-equiv (FP16)", "lru_equiv"))

    lru_hr = 0.0

    for name, config_type in configs:
        start = time.perf_counter()

        if config_type == "tiered":
            tq_cfg = TurboQuantConfig.three_bit(head_dim)
            ctm_cfg = CTMKVConfig.for_long_context()
            sim = CXLTieredSimulator(
                tier0_tokens=base_tokens,
                cxl_budget_tokens=base_tokens * 2,
                tq_config=tq_cfg,
                ctm_config=ctm_cfg,
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = sim.tier0_capacity + sim.cxl_effective_capacity
        elif config_type == "lru":
            sim = KVCacheSimulator(base_tokens, EvictionPolicy.LRU, CTMKVConfig(attention_sink_tokens=8))
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        elif config_type == "ctm":
            sim = KVCacheSimulator(
                base_tokens, EvictionPolicy.CTM_PLUS, CTMKVConfig.for_long_context()
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        elif config_type == "ctm_cap_match":
            # Same CTM+ policy, but with capacity equal to TQ+CXL effective tokens.
            # Uses CXLTieredSimulator (dict-based, O(1)) to stay fast at all scales.
            # Answers: how much gain is purely from larger capacity?
            tq_cfg = TurboQuantConfig.three_bit(head_dim)
            sim = CXLTieredSimulator(
                tier0_tokens=cxl_eff_capacity,
                cxl_budget_tokens=0,  # No CXL compression — pure FP16 capacity
                tq_config=tq_cfg,
                ctm_config=CTMKVConfig.for_long_context(),
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = cxl_eff_capacity
        elif config_type == "tq_lru":
            tq_cfg = TurboQuantConfig.three_bit(head_dim)
            int_config = IntegratedConfig(
                tq_config=tq_cfg,
                ctm_config=CTMKVConfig(
                    weight_recency=0.90,
                    weight_frequency=0.05,
                    weight_attention_strength=0.025,
                    weight_token_importance=0.025,
                    weight_position=0.0,
                    weight_sequence_priority=0.0,
                ),
                mode=IntegrationMode.CAPACITY_ONLY,
                fast_mode=True,
            )
            sim = TurboQuantCTMSimulator(base_tokens, int_config)
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = sim.effective_max_tokens
        elif config_type == "tq_ctm":
            tq_cfg = TurboQuantConfig.three_bit(head_dim)
            int_config = IntegratedConfig(
                tq_config=tq_cfg,
                ctm_config=CTMKVConfig.for_long_context(),
                mode=IntegrationMode.QUALITY_AWARE,
                fast_mode=True,
            )
            sim = TurboQuantCTMSimulator(base_tokens, int_config)
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = sim.effective_max_tokens
        elif config_type == "h2o":
            sim = H2OSimulator(
                max_tokens=base_tokens,
                sink_tokens=8,
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        elif config_type == "streamingllm":
            sim = StreamingLLMSimulator(
                max_tokens=base_tokens,
                sink_tokens=8,
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        elif config_type == "tova":
            sim = TOVASimulator(
                max_tokens=base_tokens,
                sink_tokens=8,
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        elif config_type == "lru_equiv":
            # Fast LRU-equivalent using CXL simulator with no CXL pool
            # and pure-recency scoring (for baseline comparison at 131K+)
            tq_cfg = TurboQuantConfig.three_bit(head_dim)
            lru_cfg = CTMKVConfig(
                weight_recency=0.95,
                weight_frequency=0.05,
                weight_attention_strength=0.0,
                weight_token_importance=0.0,
                weight_position=0.0,
                weight_sequence_priority=0.0,
                attention_sink_tokens=8,
            )
            sim = CXLTieredSimulator(
                tier0_tokens=base_tokens,
                cxl_budget_tokens=0,  # No CXL pool — flat LRU equivalent
                tq_config=tq_cfg,
                ctm_config=lru_cfg,
            )
            for pos, tt, attn in workload:
                sim.access(pos, tt, attn)
            stats = sim.get_stats()
            hr = sim.hit_rate
            eff = base_tokens
        else:
            continue

        elapsed = time.perf_counter() - start

        if config_type in ("lru", "lru_equiv"):
            lru_hr = hr

        # Compute avg_latency_ns for flat simulators (KVCacheSimulator) that
        # don't track it natively: all hits = 100ns, misses = 10,000ns.
        if "avg_latency_ns" not in stats:
            h = stats.get("hits", 0)
            m = stats.get("misses", 0)
            stats["avg_latency_ns"] = (h * 100 + m * 10000) / max(1, h + m)

        results[name] = {
            "hit_rate": hr,
            "vs_lru": hr - lru_hr,
            "effective_capacity": eff,
            "elapsed_seconds": elapsed,
            "num_accesses": len(workload),
            **{k: v for k, v in stats.items() if k in (
                "tier0_hits", "cxl_hits", "tier1_hits", "misses",
                "tier0_evictions", "cxl_evictions",
                "promotions_from_cxl", "promotions_from_tier1",
                "avg_latency_ns", "combined_hit_rate",
                "entity_hit_rate",
            )},
        }

    if verbose:
        print(f"\n  {'Config':<30} {'Hit Rate':>9} {'vs LRU':>9}"
              f" {'Eff.Cap':>9} {'Time':>7}")
        print(f"  {'-'*68}")
        for name, r in results.items():
            extra = ""
            if "cxl_hits" in r and r["cxl_hits"] > 0:
                extra = f"  (CXL:{r['cxl_hits']:,} hits)"
            print(
                f"  {name:<30} {r['hit_rate']:>8.2%} {r['vs_lru']:>+8.2%}"
                f" {r['effective_capacity']:>8,} {r['elapsed_seconds']:>6.1f}s{extra}"
            )

    return results


def run_scaling_sweep(
    workload_fn,
    workload_name: str,
    seq_lengths: list,
    cache_ratio: float,
    head_dim: int = 128,
    verbose: bool = True,
) -> dict:
    """Run a workload across multiple sequence lengths."""
    if verbose:
        print(f"\n{'='*72}")
        print(f"  WORKLOAD: {workload_name}")
        print(f"  Cache ratio: {cache_ratio:.0%}")
        print(f"{'='*72}")

    all_results = {}

    for seq_len in seq_lengths:
        if verbose:
            print(f"\n  --- Sequence Length: {seq_len:,} tokens ---")

        config = LongContextConfig(seq_len=seq_len, seed=42)
        gen = LongContextWorkloadGenerator(config)
        workload = workload_fn(gen)

        if verbose:
            print(f"  Generated {len(workload):,} accesses")

        results = run_single_workload(
            workload_name, workload, seq_len, cache_ratio,
            head_dim=head_dim, verbose=verbose,
        )
        all_results[seq_len] = results

    return all_results


def print_scaling_summary(all_workload_results: dict, seq_lengths: list):
    """Print a summary table showing how hit rates scale."""
    print("\n" + "=" * 90)
    print("  SCALING SUMMARY: Hit Rate by Sequence Length")
    print("=" * 90)

    configs_to_show = [
        "LRU (FP16)", "LRU-equiv (FP16)",
        "H2O", "StreamingLLM", "TOVA",
        "CTM+ (FP16)", "TQ-3bit + CTM+", "TQ-3bit + CTM+ + CXL",
    ]

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        header = f"  {'Seq Len':>10}"
        for cfg in configs_to_show:
            header += f"  {cfg:>20}"
        print(header)
        print(f"  {'-' * (10 + 22 * len(configs_to_show))}")

        for sl in seq_lengths:
            if sl not in wl_results:
                continue
            row = f"  {sl:>10,}"
            for cfg in configs_to_show:
                if cfg in wl_results[sl]:
                    hr = wl_results[sl][cfg]["hit_rate"]
                    row += f"  {hr:>19.2%}"
                else:
                    row += f"  {'N/A':>20}"
            print(row)

    # Print vs-LRU improvement summary
    print(f"\n{'='*90}")
    print("  IMPROVEMENT vs LRU (absolute %)")
    print("=" * 90)

    improved_configs = [
        "H2O", "StreamingLLM", "TOVA",
        "CTM+ (FP16)", "TQ-3bit + CTM+", "TQ-3bit + CTM+ + CXL",
    ]

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        header = f"  {'Seq Len':>10}"
        for cfg in improved_configs:
            header += f"  {cfg:>20}"
        print(header)
        print(f"  {'-' * (10 + 22 * len(improved_configs))}")

        for sl in seq_lengths:
            if sl not in wl_results:
                continue
            row = f"  {sl:>10,}"
            for cfg in improved_configs:
                if cfg in wl_results[sl]:
                    vs = wl_results[sl][cfg]["vs_lru"]
                    row += f"  {vs:>+19.2%}"
                else:
                    row += f"  {'N/A':>20}"
            print(row)

    print("=" * 90)


def print_cxl_tier_analysis(all_workload_results: dict, seq_lengths: list):
    """Print detailed CXL tier usage analysis."""
    print(f"\n{'='*90}")
    print("  CXL WARM TIER ANALYSIS")
    print("=" * 90)

    cxl_config = "TQ-3bit + CTM+ + CXL"

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        print(f"  {'Seq Len':>10} {'Tier0 Hits':>12} {'CXL Hits':>10}"
              f" {'Tier1 Hits':>11} {'Misses':>8} {'CXL Saves':>11}")
        print(f"  {'-'*66}")

        for sl in seq_lengths:
            if sl not in wl_results or cxl_config not in wl_results[sl]:
                continue
            r = wl_results[sl][cxl_config]
            t0h = r.get("tier0_hits", 0)
            cxlh = r.get("cxl_hits", 0)
            t1h = r.get("tier1_hits", 0)
            miss = r.get("misses", 0)
            total = t0h + cxlh + t1h + miss
            # "CXL saves" = what fraction of non-tier0 accesses were caught by CXL
            non_t0 = cxlh + t1h + miss
            cxl_save_rate = cxlh / non_t0 if non_t0 > 0 else 0

            print(
                f"  {sl:>10,} {t0h:>11,} {cxlh:>9,}"
                f" {t1h:>10,} {miss:>7,} {cxl_save_rate:>10.1%}"
            )

    print("=" * 90)


def print_effective_access_cost(all_workload_results: dict, seq_lengths: list):
    """Print average access latency (ns) per config, breaking down tier contributions.

    For TQ+CXL: cost = (T0*100 + CXL*300 + T1*10000 + miss*10000) / total
    For flat baselines: cost = (hits*100 + misses*10000) / total

    This prevents 'gaming' the hit-rate metric by counting slow warm hits the
    same as fast hot hits.
    """
    TIER0_NS  = 100
    CXL_NS    = 300
    NVME_NS   = 10_000

    configs_to_show = [
        "LRU (FP16)", "LRU-equiv (FP16)", "H2O", "StreamingLLM", "TOVA",
        "CTM+ (FP16)", "CTM+ FP16 (cap-match)", "TQ-3bit + CTM+ + CXL",
    ]

    print(f"\n{'='*90}")
    print("  EFFECTIVE ACCESS COST (avg latency ns) — lower is better")
    print(f"  Tier0={TIER0_NS}ns  CXL={CXL_NS}ns  NVMe/miss={NVME_NS:,}ns")
    print("=" * 90)

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        header = f"  {'Seq Len':>10}"
        for cfg in configs_to_show:
            short = cfg.replace("TQ-3bit + CTM+ + CXL", "TQ+CXL").replace("CTM+ FP16 (cap-match)", "CTM+(cap)")
            header += f"  {short:>12}"
        print(header)
        print(f"  {'-' * (10 + 14 * len(configs_to_show))}")

        for sl in seq_lengths:
            if sl not in wl_results:
                continue
            row = f"  {sl:>10,}"
            for cfg in configs_to_show:
                r = wl_results[sl].get(cfg)
                if r is None:
                    row += f"  {'N/A':>12}"
                    continue
                lat = r.get("avg_latency_ns")
                if lat is None:
                    t0 = r.get("tier0_hits", r.get("hits", 0))
                    cx = r.get("cxl_hits", 0)
                    t1 = r.get("tier1_hits", 0)
                    ms = r.get("misses", 0)
                    tot = t0 + cx + t1 + ms
                    lat = (t0 * TIER0_NS + cx * CXL_NS + (t1 + ms) * NVME_NS) / max(1, tot)
                row += f"  {lat:>9.0f}ns"
            print(row)

    print("=" * 90)


def print_capacity_ablation(all_workload_results: dict, seq_lengths: list):
    """Decompose TQ+CXL improvement into 'capacity effect' vs 'policy effect'.

    capacity_effect = CTM+(cap-match) - CTM+(base)   # pure capacity gain
    policy_effect   = TQ+CXL - CTM+(cap-match)       # smarter eviction on top
    """
    print(f"\n{'='*90}")
    print("  CAPACITY vs POLICY ABLATION")
    print("  capacity_effect = CTM+(cap-match) minus CTM+(base)")
    print("  policy_effect   = TQ+CXL minus CTM+(cap-match)")
    print("=" * 90)

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        print(f"  {'Seq Len':>10}  {'CTM+ base':>11}  {'CTM+ cap':>10}"
              f"  {'TQ+CXL':>10}  {'cap effect':>12}  {'policy effect':>14}")
        print(f"  {'-'*74}")

        for sl in seq_lengths:
            if sl not in wl_results:
                continue
            r = wl_results[sl]
            base_hr  = r.get("CTM+ (FP16)", {}).get("hit_rate")
            cap_hr   = r.get("CTM+ FP16 (cap-match)", {}).get("hit_rate")
            tqcxl_hr = r.get("TQ-3bit + CTM+ + CXL", {}).get("hit_rate")

            if base_hr is None or cap_hr is None or tqcxl_hr is None:
                continue

            cap_effect    = cap_hr  - base_hr
            policy_effect = tqcxl_hr - cap_hr

            print(
                f"  {sl:>10,}  {base_hr:>10.2%}  {cap_hr:>10.2%}"
                f"  {tqcxl_hr:>10.2%}  {cap_effect:>+11.2%}  {policy_effect:>+13.2%}"
            )

    print("=" * 90)


def print_end_task_proxy(all_workload_results: dict, seq_lengths: list):
    """Report entity-token hit rate as an end-task proxy metric.

    'entity' tokens represent named facts, variables, function names — the
    tokens most likely to be queried in retrieval tasks.  A policy that
    achieves a high entity_hit_rate protects the tokens that matter most for
    downstream accuracy, not just tokens in aggregate.

    This answers: 'is the improvement uniform, or concentrated on important tokens?'
    """
    configs_to_show = [
        "LRU (FP16)", "LRU-equiv (FP16)", "H2O", "StreamingLLM", "TOVA",
        "CTM+ (FP16)", "CTM+ FP16 (cap-match)", "TQ-3bit + CTM+ + CXL",
    ]

    print(f"\n{'='*90}")
    print("  ENTITY TOKEN HIT RATE (end-task proxy: retrieval / needle accuracy)")
    print("  'entity' = named facts, entities, variables — tokens most likely queried")
    print("=" * 90)

    for wl_name, wl_results in all_workload_results.items():
        print(f"\n  [{wl_name}]")
        header = f"  {'Seq Len':>10}"
        for cfg in configs_to_show:
            short = cfg.replace("TQ-3bit + CTM+ + CXL", "TQ+CXL").replace("CTM+ FP16 (cap-match)", "CTM+(cap)")
            header += f"  {short:>11}"
        print(header)
        print(f"  {'-' * (10 + 13 * len(configs_to_show))}")

        for sl in seq_lengths:
            if sl not in wl_results:
                continue
            row = f"  {sl:>10,}"
            for cfg in configs_to_show:
                r = wl_results[sl].get(cfg)
                if r is None:
                    row += f"  {'N/A':>11}"
                    continue
                ehr = r.get("entity_hit_rate")
                if ehr is None:
                    row += f"  {'N/A':>11}"
                else:
                    row += f"  {ehr:>10.2%}"
            print(row)

    print("=" * 90)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Long-Context Scaling Benchmark: TurboQuant + CTM+",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: smaller sequence lengths")
    parser.add_argument("--workload", type=str, default=None,
                        help="Run specific workload only")
    parser.add_argument("--cache-ratio", type=float, default=0.10,
                        help="Cache-to-context ratio (default: 0.10)")
    parser.add_argument("--head-dim", type=int, default=128,
                        help="KV head dimension (default: 128)")
    parser.add_argument("--json", type=str, default=None,
                        help="Export results to JSON")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()
    verbose = not args.quiet
    random.seed(args.seed)
    np.random.seed(args.seed)

    if args.quick:
        seq_lengths = [4096, 8192, 16384, 32768]
    else:
        seq_lengths = [4096, 16384, 32768, 65536, 131072]

    # Define workloads
    workload_defs = {
        "sleeping_tokens": lambda gen: gen.sleeping_tokens(),
        "needle_in_haystack": lambda gen: gen.needle_in_haystack(),
        "multi_document_qa": lambda gen: gen.multi_document_qa(),
        "streaming_conversation": lambda gen: gen.streaming_conversation(),
        "code_generation": lambda gen: gen.code_generation(),
    }

    if args.workload:
        if args.workload not in workload_defs:
            print(f"Unknown workload: {args.workload}")
            print(f"Available: {', '.join(workload_defs.keys())}")
            return 1
        workload_defs = {args.workload: workload_defs[args.workload]}

    overall_start = time.time()

    if verbose:
        print("╔" + "═" * 70 + "╗")
        print("║  LONG-CONTEXT SCALING BENCHMARK: TurboQuant + CTM+               ║")
        print("║  Sequence lengths: " + ", ".join(f"{s:,}" for s in seq_lengths).ljust(49) + "║")
        print("║  Cache ratio: " + f"{args.cache_ratio:.0%}".ljust(54) + "║")
        print("║  Workloads: " + f"{len(workload_defs)}".ljust(56) + "║")
        print("╚" + "═" * 70 + "╝")

    all_results = {}

    for wl_name, wl_fn in workload_defs.items():
        wl_results = run_scaling_sweep(
            wl_fn, wl_name, seq_lengths, args.cache_ratio,
            head_dim=args.head_dim, verbose=verbose,
        )
        all_results[wl_name] = wl_results

    if verbose:
        print_scaling_summary(all_results, seq_lengths)
        print_cxl_tier_analysis(all_results, seq_lengths)
        print_effective_access_cost(all_results, seq_lengths)
        print_capacity_ablation(all_results, seq_lengths)
        print_end_task_proxy(all_results, seq_lengths)

        elapsed = time.time() - overall_start
        print(f"\n  Total benchmark time: {elapsed:.1f}s")

    if args.json:
        # Convert int keys to strings for JSON
        json_results = {}
        for wl_name, wl_data in all_results.items():
            json_results[wl_name] = {
                str(sl): data for sl, data in wl_data.items()
            }
        with open(args.json, "w") as f:
            json.dump(json_results, f, indent=2, default=str)
        if verbose:
            print(f"\n  Results exported to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
