# CTM+ for Databases

Intelligent buffer pool management for database systems using CTM+ (Coherence-Tier Memory Plus).

## Overview

CTM+ enhances database buffer pool management with smart page eviction decisions for:
- **PostgreSQL**: Shared buffer replacement
- **MySQL/InnoDB**: Buffer pool management
- **Redis**: Memory-efficient caching
- **Generic KV**: Any key-value storage

### Key Features

- **Smart Victim Selection**: O(k) sampled scoring vs O(n) LRU scans
- **ARC-style Adaptation**: Dual shadow tiers with adaptive p
- **Page Type Awareness**: Index pages protected, dirty pages penalty
- **Sequential Prefetching**: Pattern-based prefetch for OLAP
- **Zipfian Optimization**: Optimized for real database workloads

## Installation

```bash
cd CTM_plus/Database
pip install -e .

# With PostgreSQL support
pip install -e ".[postgres]"

# With Redis support
pip install -e ".[redis]"
```

## Quick Start

### Basic Buffer Pool

```python
from ctm_plus_db import CTMBufferPool, CTMDBConfig

# Create buffer pool
config = CTMDBConfig.for_oltp()
pool = CTMBufferPool(
    pool_size_pages=10000,
    page_size_bytes=8192,
    config=config,
)

# Access pages
is_hit, prefetch_list = pool.access(page_id=12345, is_write=False)

# Get eviction victim
victim = pool.select_victim()

# Get statistics
stats = pool.get_stats()
print(f"Hit Rate: {stats['hit_rate']:.2%}")
```

### PostgreSQL Integration

```python
from ctm_plus_db import PostgresCTMExtension, CTMDBConfig
from ctm_plus_db.postgres import PostgresBufferTag, PostgresRelationType

# Create PostgreSQL extension
pg = PostgresCTMExtension(
    shared_buffers=8192,  # Number of 8KB pages
    config=CTMDBConfig.for_postgres(),
)

# Register relations for better decisions
pg.register_relation(rel_file_node=16384, rel_type=PostgresRelationType.TABLE)
pg.register_relation(rel_file_node=16385, rel_type=PostgresRelationType.INDEX)

# Buffer access
tag = PostgresBufferTag(rel_file_node=16384, fork_number=0, block_number=100)
is_hit, prefetch_tags = pg.read_buffer(tag)

# Get victim for eviction
victim_tag = pg.get_victim()
```

### Redis-style Cache

```python
from ctm_plus_db import RedisCTMCache, CTMDBConfig

# Create Redis-compatible cache (1GB limit)
cache = RedisCTMCache(
    maxmemory=1024 * 1024 * 1024,
    config=CTMDBConfig.for_redis(),
)

# String commands
cache.set("user:1", "John Doe", ex=3600)  # 1 hour TTL
value = cache.get("user:1")

# Hash commands
cache.hset("session:abc", "user_id", "123")
cache.hset("session:abc", "created", "2024-01-01")
session = cache.hgetall("session:abc")

# List commands
cache.lpush("queue:jobs", "job1", "job2", "job3")
jobs = cache.lrange("queue:jobs", 0, -1)

# Get info
info = cache.info()
print(f"Hit Rate: {info['ctm_plus']['hit_rate']:.2%}")
```

### Generic Key-Value Cache

```python
from ctm_plus_db import GenericKVCache, CTMDBConfig

# Create cache with custom size function
cache = GenericKVCache[str, dict](
    max_entries=10000,
    max_memory_bytes=100 * 1024 * 1024,  # 100MB
    config=CTMDBConfig(),
    size_fn=lambda v: len(str(v)),
)

# With loader for cache-aside pattern
def load_from_db(key: str) -> dict:
    # Load from database
    return {"id": key, "data": "..."}

cache.on_miss = load_from_db

# Get automatically loads on miss
data = cache.get("user:123")
```

## Configuration

### Preset Configurations

```python
from ctm_plus_db import CTMDBConfig

# OLTP (random access, many small transactions)
config = CTMDBConfig.for_oltp()

# OLAP (sequential scans, large queries)
config = CTMDBConfig.for_olap()

# Mixed workloads
config = CTMDBConfig.for_mixed()

# Redis-style caching
config = CTMDBConfig.for_redis()

# PostgreSQL buffer pool
config = CTMDBConfig.for_postgres()

# MySQL/InnoDB buffer pool
config = CTMDBConfig.for_mysql()
```

### Custom Configuration

```python
config = CTMDBConfig(
    victim_sample_size=64,
    promotion_threshold=0.25,
    enable_smart_victim=True,

    # Page type weights
    dirty_page_penalty=0.3,
    index_page_bonus=0.2,

    # Scoring weights
    weight_recency=0.35,
    weight_frequency=0.30,
    weight_reuse=0.15,
    weight_correlation=0.10,
    weight_page_type=0.10,

    # Prefetching
    prefetch_enabled=True,
    prefetch_distance=8,
)
```

## API Reference

### CTMBufferPool

```python
class CTMBufferPool:
    def __init__(
        self,
        pool_size_pages: int,
        page_size_bytes: int = 8192,
        config: CTMDBConfig = None,
    ): ...

    def access(
        self,
        page_id: int,
        is_write: bool = False,
        page_type: PageType = PageType.HEAP,
    ) -> Tuple[bool, List[int]]: ...  # (is_hit, prefetch_list)

    def select_victim(self) -> Optional[int]: ...
    def pin_page(self, page_id: int) -> bool: ...
    def unpin_page(self, page_id: int) -> bool: ...
    def mark_dirty(self, page_id: int) -> bool: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### CTMPageCache

```python
class CTMPageCache(Generic[K, V]):
    def get(self, key: K, default: V = None) -> Optional[V]: ...
    def put(self, key: K, value: V) -> Optional[K]: ...  # Returns evicted key
    def delete(self, key: K) -> bool: ...
    def contains(self, key: K) -> bool: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### RedisCTMCache

```python
class RedisCTMCache:
    # String commands
    def set(self, key, value, ex=None, px=None, nx=False, xx=False): ...
    def get(self, key) -> Optional[str]: ...
    def incr(self, key) -> int: ...

    # Hash commands
    def hset(self, key, field, value) -> int: ...
    def hget(self, key, field) -> Optional[str]: ...
    def hgetall(self, key) -> Dict[str, str]: ...

    # List commands
    def lpush(self, key, *values) -> int: ...
    def rpush(self, key, *values) -> int: ...
    def lrange(self, key, start, stop) -> List[str]: ...

    # Key commands
    def delete(self, *keys) -> int: ...
    def exists(self, *keys) -> int: ...
    def expire(self, key, seconds) -> int: ...
    def ttl(self, key) -> int: ...

    # Info
    def info(self, section="all") -> Dict[str, Any]: ...
```

## Performance

### Benchmarks (Zipfian workload, 1000 buffer pages)

| Metric | CTM+ | LRU | Improvement |
|--------|------|-----|-------------|
| Hit Rate (s=1.0) | 87.2% | 85.1% | +2.1% |
| Hit Rate (s=1.5) | 94.5% | 92.8% | +1.7% |
| OLTP Hit Rate | 91.3% | 88.7% | +2.6% |

## Example

Run the included examples:

```bash
cd CTM_plus/Database
python -m ctm_plus_db.example
```

Output:
```
CTM+ Buffer Pool Demo
============================================================
Configuration:
  Pool Size: 1000 pages
  Smart Victim: True

Results:
  Hit Rate: 89.5%
  Evictions: 4523
  Adaptive p: 0.534

CTM+ vs LRU Comparison
============================================================
  Metric               CTM+            LRU             Diff
  ------------------------------------------------------------
  Hit Rate             87.23%          85.12%          +2.11%
```

## License

MIT
