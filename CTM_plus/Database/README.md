# CTM+ Adaptive Eviction Policy

A sampled multi-signal eviction policy for research and benchmarking.

**This is NOT a database buffer pool or storage system.** It makes eviction
decisions only — it does not manage memory, I/O, or actual page data.

## Algorithm

Sampled ARC variant with 4-signal weighted scoring:

1. **Recency** (0.40) — normalized time since last access
2. **Frequency** (0.35) — saturated access count
3. **Correlation** (0.15) — transition affinity with buffered pages
4. **Page type** (0.10) — bonus for index pages, penalty for dirty pages

ARC-style dual ghost caches (B1/B2) adaptively shift the recency/frequency
balance based on which evicted pages get re-requested.

## Usage

```python
from ctm_plus_db import AdaptiveEvictionPolicy, EvictionConfig

policy = AdaptiveEvictionPolicy(
    capacity=10000,
    config=EvictionConfig.for_random_access(),
)

# Record accesses
is_hit, prefetch_hints = policy.access(page_id=42)

# Get eviction victim
victim = policy.select_victim()

# Pin/unpin, dirty tracking
policy.pin(page_id=42)
policy.mark_dirty(page_id=42)

# Statistics
stats = policy.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

## Configuration Presets

| Preset | Use case |
|--------|----------|
| `EvictionConfig()` | Default balanced weights |
| `EvictionConfig.for_random_access()` | Random point lookups |
| `EvictionConfig.for_sequential()` | Sequential scans |
| `EvictionConfig.for_mixed()` | Mixed access patterns |
