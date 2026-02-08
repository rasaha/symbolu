#!/usr/bin/env python3
"""
Example: CTM+ Database Integration

Demonstrates CTM+ buffer pool management for various database scenarios.
"""

import random
import time
from typing import List, Dict

from ctm_plus_db import (
    CTMBufferPool,
    CTMPageCache,
    CTMDBConfig,
    PostgresCTMExtension,
    RedisCTMCache,
    GenericKVCache,
)
from ctm_plus_db.buffer_pool import PageType
from ctm_plus_db.page_cache import LRUCache
from ctm_plus_db.postgres import PostgresBufferTag, PostgresRelationType


def simulate_zipfian_access(n_pages: int, n_accesses: int, skew: float = 1.0) -> List[int]:
    """Generate Zipfian access pattern (common in databases)."""
    pages = list(range(n_pages))
    weights = [1.0 / (i + 1) ** skew for i in range(n_pages)]
    total = sum(weights)
    weights = [w / total for w in weights]

    accesses = []
    for _ in range(n_accesses):
        accesses.append(random.choices(pages, weights=weights)[0])
    return accesses


def simulate_sequential_scan(start: int, length: int) -> List[int]:
    """Generate sequential scan pattern."""
    return list(range(start, start + length))


def simulate_oltp_workload(n_pages: int, n_transactions: int) -> List[int]:
    """Simulate OLTP workload with hot spots and random access."""
    accesses = []
    hot_pages = list(range(min(100, n_pages)))  # Hot set

    for _ in range(n_transactions):
        # 70% hot pages, 30% random
        if random.random() < 0.7:
            accesses.extend(random.sample(hot_pages, min(5, len(hot_pages))))
        else:
            accesses.append(random.randint(0, n_pages - 1))
    return accesses


def demo_buffer_pool():
    """Demonstrate basic buffer pool usage."""
    print("=" * 60)
    print("CTM+ Buffer Pool Demo")
    print("=" * 60)

    config = CTMDBConfig.for_oltp()
    pool = CTMBufferPool(
        pool_size_pages=1000,
        page_size_bytes=8192,
        config=config,
    )

    print(f"\nConfiguration:")
    print(f"  Pool Size: {pool.pool_size} pages")
    print(f"  Page Size: {pool.page_size} bytes")
    print(f"  Smart Victim: {config.enable_smart_victim}")

    # Generate workload
    print("\nRunning OLTP workload simulation...")
    accesses = simulate_oltp_workload(n_pages=10000, n_transactions=5000)

    start = time.time()
    for page_id in accesses:
        is_write = random.random() < 0.2  # 20% writes
        pool.access(page_id, is_write=is_write)
    elapsed = time.time() - start

    stats = pool.get_stats()
    print(f"\nResults:")
    print(f"  Total Accesses: {stats['total_accesses']:,}")
    print(f"  Hit Rate: {stats['hit_rate']:.2%}")
    print(f"  Evictions: {stats['evictions']:,}")
    print(f"  Dirty Evictions: {stats['dirty_evictions']:,}")
    print(f"  Prefetches: {stats['prefetches']:,}")
    print(f"  Adaptive p: {stats['adaptive_p']:.3f}")
    print(f"  Time: {elapsed:.2f}s")


def demo_ctm_vs_lru():
    """Compare CTM+ cache vs LRU cache."""
    print("\n" + "=" * 60)
    print("CTM+ vs LRU Comparison")
    print("=" * 60)

    cache_size = 500
    n_keys = 5000
    n_accesses = 50000

    # Generate Zipfian workload
    accesses = simulate_zipfian_access(n_keys, n_accesses, skew=1.2)

    # CTM+ Cache
    ctm_cache = CTMPageCache[int, str](
        max_size=cache_size,
        config=CTMDBConfig.for_redis(),
    )

    # LRU Cache
    lru_cache = LRUCache[int, str](max_size=cache_size)

    print(f"\nWorkload: {n_accesses:,} accesses, {n_keys:,} unique keys")
    print(f"Cache Size: {cache_size} entries")

    # Run CTM+
    start = time.time()
    for key in accesses:
        if ctm_cache.get(key) is None:
            ctm_cache.put(key, f"value_{key}")
    ctm_time = time.time() - start
    ctm_stats = ctm_cache.get_stats()

    # Run LRU
    start = time.time()
    for key in accesses:
        if lru_cache.get(key) is None:
            lru_cache.put(key, f"value_{key}")
    lru_time = time.time() - start
    lru_stats = lru_cache.get_stats()

    print(f"\nResults:")
    print(f"  {'Metric':<20} {'CTM+':<15} {'LRU':<15} {'Diff':<10}")
    print(f"  {'-' * 60}")
    print(f"  {'Hit Rate':<20} {ctm_stats['hit_rate']:.2%}         {lru_stats['hit_rate']:.2%}         {(ctm_stats['hit_rate'] - lru_stats['hit_rate']) * 100:+.2f}%")
    print(f"  {'Hits':<20} {ctm_stats['hits']:,}           {lru_stats['hits']:,}")
    print(f"  {'Misses':<20} {ctm_stats['misses']:,}           {lru_stats['misses']:,}")
    print(f"  {'Time':<20} {ctm_time:.2f}s           {lru_time:.2f}s")


def demo_postgres_integration():
    """Demonstrate PostgreSQL buffer pool integration."""
    print("\n" + "=" * 60)
    print("PostgreSQL CTM+ Integration Demo")
    print("=" * 60)

    # Simulate PostgreSQL shared_buffers
    shared_buffers = 2000  # ~16MB with 8KB blocks

    pg = PostgresCTMExtension(
        shared_buffers=shared_buffers,
        block_size=8192,
        config=CTMDBConfig.for_postgres(),
    )

    # Register some relations
    pg.register_relation(1000, PostgresRelationType.TABLE)
    pg.register_relation(1001, PostgresRelationType.INDEX)
    pg.register_relation(1002, PostgresRelationType.TABLE)

    print(f"\nPostgreSQL Buffer Pool:")
    print(f"  Shared Buffers: {shared_buffers}")
    print(f"  Block Size: 8KB")

    # Simulate query workload
    print("\nSimulating query workload...")

    # Sequential scan of a table
    for block in range(500):
        tag = PostgresBufferTag(rel_file_node=1000, fork_number=0, block_number=block)
        is_hit, prefetch = pg.read_buffer(tag)

    # Index lookups
    for _ in range(1000):
        block = random.randint(0, 100)
        tag = PostgresBufferTag(rel_file_node=1001, fork_number=0, block_number=block)
        pg.read_buffer(tag)

    # Random table access
    for _ in range(2000):
        block = random.randint(0, 10000)
        tag = PostgresBufferTag(rel_file_node=1002, fork_number=0, block_number=block)
        is_write = random.random() < 0.1
        if is_write:
            pg.write_buffer(tag)
        else:
            pg.read_buffer(tag)

    print(pg.get_buffer_stats_sql())


def demo_redis_cache():
    """Demonstrate Redis-compatible cache."""
    print("\n" + "=" * 60)
    print("Redis CTM+ Cache Demo")
    print("=" * 60)

    # 1MB cache
    cache = RedisCTMCache(
        maxmemory=1 * 1024 * 1024,
        avg_entry_size=100,
        config=CTMDBConfig.for_redis(),
    )

    print(f"\nRedis-style Cache:")
    print(f"  Max Memory: 1 MB")
    print(f"  Avg Entry Size: 100 bytes")

    # String operations
    print("\nRunning Redis commands...")
    for i in range(1000):
        cache.set(f"key:{i}", f"value_{i}" * 10)

    for _ in range(5000):
        key = f"key:{random.randint(0, 999)}"
        cache.get(key)

    # Hash operations
    for i in range(100):
        cache.hset(f"user:{i}", "name", f"User {i}")
        cache.hset(f"user:{i}", "email", f"user{i}@example.com")

    # List operations
    for i in range(50):
        cache.lpush(f"list:{i}", *[f"item_{j}" for j in range(10)])

    info = cache.info()
    print(f"\nINFO output:")
    print(f"  Keys: {info['keyspace']['db0']['keys']}")
    print(f"  Memory Used: {info['memory']['used_memory'] / 1024:.1f} KB")
    print(f"  Hit Rate: {info['ctm_plus']['hit_rate']:.2%}")
    print(f"  Evictions: {info['ctm_plus']['evictions']}")
    print(f"  Adaptive p: {info['ctm_plus']['adaptive_p']:.3f}")


def demo_workload_comparison():
    """Compare CTM+ performance across different workloads."""
    print("\n" + "=" * 60)
    print("Workload Comparison")
    print("=" * 60)

    pool_size = 1000
    n_pages = 10000
    n_accesses = 20000

    workloads = [
        ("OLTP (Hot Spots)", lambda: simulate_oltp_workload(n_pages, n_accesses // 5)),
        ("OLAP (Sequential)", lambda: simulate_sequential_scan(0, n_accesses) * 3),
        ("Zipfian (s=1.0)", lambda: simulate_zipfian_access(n_pages, n_accesses, 1.0)),
        ("Zipfian (s=1.5)", lambda: simulate_zipfian_access(n_pages, n_accesses, 1.5)),
        ("Uniform", lambda: [random.randint(0, n_pages - 1) for _ in range(n_accesses)]),
    ]

    configs = [
        ("Default", CTMDBConfig()),
        ("OLTP", CTMDBConfig.for_oltp()),
        ("OLAP", CTMDBConfig.for_olap()),
    ]

    print(f"\nPool Size: {pool_size}, Total Pages: {n_pages}")
    print(f"\n{'Workload':<25} {'Config':<10} {'Hit Rate':<12} {'Evictions':<12}")
    print("-" * 60)

    for workload_name, workload_fn in workloads:
        accesses = workload_fn()[:n_accesses]

        for config_name, config in configs:
            pool = CTMBufferPool(
                pool_size_pages=pool_size,
                page_size_bytes=8192,
                config=config,
            )

            for page_id in accesses:
                pool.access(page_id % n_pages)

            stats = pool.get_stats()
            print(f"{workload_name:<25} {config_name:<10} {stats['hit_rate']:.2%}       {stats['evictions']:,}")


def main():
    print("CTM+ Database Integration - Examples")
    print("=" * 60)

    demo_buffer_pool()
    demo_ctm_vs_lru()
    demo_postgres_integration()
    demo_redis_cache()
    demo_workload_comparison()


if __name__ == "__main__":
    main()
