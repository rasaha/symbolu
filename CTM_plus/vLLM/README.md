# CTM+ KV Cache Eviction Policy

A scoring-only eviction policy for LLM KV cache blocks.

**This module does NOT manage memory, I/O, or block allocation.**
It only decides *which* blocks to evict, based on LLM-specific signals.
Actual block management is handled by the serving engine (e.g. vLLM's
`BlockSpaceManager`).

## Signals

1. **Attention value** — cumulative attention received by tokens in the block
2. **Position importance** — sink / entity / recent / filler classification
3. **Frequency** — Count-Min Sketch (4-bit, O(1)) for block access counts
4. **Recency** — exponential decay since last access
5. **Sequence priority** — user-set priority weighted by invested compute

Scoring weights are phase-aware (PREFILL vs DECODE).

## Scan Resistance

S3-FIFO admission (SOSP'23) prevents prefill floods from evicting useful
decode-phase blocks. One-hit-wonders are evicted from the small queue
without polluting the main queue.

## Usage

```python
from ctm_plus_vllm import KVCachePolicy, InferencePhase

policy = KVCachePolicy(max_blocks=2048)
policy.register_sequence(seq_id=1)

# During attention computation
policy.on_token_access(
    token_id=0, position=0, sequence_id=1, block_id=0,
    attention_weight=0.15, seq_len=512,
)

# When GPU memory is full
victims = policy.select_victims(count=4)
for block_id in victims:
    # ... tell vLLM to evict this block ...
    policy.evict_block(block_id)
```

## Configuration

```python
from ctm_plus_vllm import KVCachePolicyConfig

# Structural parameters only — phase weights are built-in
config = KVCachePolicyConfig.for_long_context()
policy = KVCachePolicy(
    max_blocks=2048,
    sink_tokens=config.sink_tokens,
    recent_window=config.recent_window,
    entity_attention_threshold=config.entity_attention_threshold,
)
```

## Integration Point

vLLM's `Evictor` abstract base class:

```python
class Evictor(ABC):
    def evict(self) -> Tuple[PhysicalTokenBlock, ...]: ...
```

A thin adapter would wrap `KVCachePolicy.select_victims()` to return
`PhysicalTokenBlock` tuples instead of block IDs.

## Benchmarking

`kv_cache_simulator.py` provides a standalone cache simulator with
LRU/FIFO/Random baselines and realistic LLM attention workloads.
