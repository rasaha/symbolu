# CTM+ KV Cache Policy Simulator

A lightweight simulator that models LLM inference access patterns and
evaluates eviction policies. Research tool, not production code.

## Simulation Model

**Prefill phase:** Sequence writes KV blocks sequentially (bulk allocation,
no reuse). Large bursts that can flood the cache.

**Decode phase:** Each new token attends to all prior tokens. Attention
follows observed LLM patterns:
- ~15% on first few positions (attention sinks)
- ~55% on recent window
- ~30% spread across middle positions

Block statistics (cumulative attention, access count, recency) are updated
based on the attention distribution.

**Eviction:** When KV cache exceeds memory budget, the policy selects
victim blocks. Sink blocks are pinned and never evicted.

## Policies

| Policy | Algorithm |
|--------|-----------|
| LRU | Evict least recently accessed block |
| FIFO | Evict oldest admitted block |
| Random | Evict uniformly at random |
| **CTM+** | Attention-aware: 4-signal weighted scoring (attention 0.35, position 0.30, recency 0.25, frequency 0.10) with sampled victim selection |

## Usage

```python
from kv_simulator import KVCacheSimulator, PolicyType, compare_policies

# Single simulation
sim = KVCacheSimulator(max_blocks=256, policy_type=PolicyType.CTM_PLUS)
sim.add_sequence(seq_id=0, context_length=512)
sim.prefill_sequence(0)
for _ in range(128):
    sim.decode_step(0)
print(sim.get_metrics())

# Compare all policies on same workload
results = compare_policies(
    max_blocks=256,
    num_sequences=4,
    context_length=512,
    decode_steps=128,
)
for policy, metrics in results.items():
    print(f"{policy}: eviction_accuracy={metrics['eviction_accuracy']:.2%}")
```

## Metrics

| Metric | Description |
|--------|-------------|
| `eviction_accuracy` | Fraction of evictions that targeted low-value (filler) blocks |
| `important_evictions` | Count of evicted sink/entity blocks (lower is better) |
| `retention_rate` | Fraction of allocated blocks still in cache |
| `block_type_distribution` | Current cache composition (sink/entity/recent/filler) |
| `recompute_cost` | Tokens in evicted blocks that were later needed |

## Configuration

```python
from kv_simulator import SimulationConfig

config = SimulationConfig.for_long_context()  # 8K-32K+ sequences
config = SimulationConfig.for_short_context() # chatbot turns
config = SimulationConfig.for_batch()         # many concurrent sequences
```
