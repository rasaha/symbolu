# CTM+ Simulator

Validation framework for Coherence-Tier Memory Plus (CTM+) algorithm.

## What is CTM+?

CTM+ is a **memory controller algorithm** (not a new chip) that uses coherence-based
math to make smarter tier placement decisions. It applies the Symbol-U coherence
frameworks (BCVF/USE/SCC) to memory management.

**Key point:** The physical memory is still DRAM and NAND. CTM+ changes how data
is placed, not the underlying storage technology.

## Quick Start

```bash
# Run quick comparison on Zipfian workload
cd simulator
python -m ctm_plus.cli --pattern zipf --events 100000

# Compare on hotspot workload
python -m ctm_plus.cli --pattern hotspot --events 200000 --compare

# Run on your own trace
python -m ctm_plus.cli --trace path/to/trace.csv --tier0 2000 --tier1 200000

# Generate trace file
python -m ctm_plus.cli --generate --pattern mixed --events 1000000 --output trace.csv
```

## Python API

```python
from ctm_plus import Simulator, CTMPlusController, LRUController
from ctm_plus.traces import generate_synthetic_trace

# Generate test trace
trace = generate_synthetic_trace(
    pattern="zipf",
    num_events=100000,
    num_pages=10000,
)

# Create simulator
sim = Simulator(tier0_size=1000, tier1_size=100000)

# Run with different controllers
results_lru = sim.run(trace, LRUController(sim.config), "test")
results_ctm = sim.run(trace, CTMPlusController(sim.config), "test")

# Compare results
print(f"LRU hit rate:  {results_lru.metrics.hit_rate:.2%}")
print(f"CTM+ hit rate: {results_ctm.metrics.hit_rate:.2%}")
print(f"Improvement:   {results_ctm.metrics.hit_rate - results_lru.metrics.hit_rate:+.2%}")
```

## Components

### Controllers

| Controller | Description | Algorithm |
|------------|-------------|-----------|
| `LRUController` | Baseline LRU | Evict least recently used |
| `LRU2Controller` | LRU-2 variant | Promote on 2nd access |
| `ARCController` | Adaptive Replacement Cache | Balance recency/frequency |
| `CTMPlusController` | CTM+ (main algorithm) | Coherence-based decisions |

### CTM+ Components

1. **Phase Integrator**: Learns access patterns via streaming accumulator
2. **Coherence Computer**: Fast (O(1)) and slow (O(n)) coherence computation
3. **BCVF Gate**: Bidirectional verification for promotion/demotion
4. **SCC Optimizer**: Self-tunes parameters based on global coherence

### Synthetic Workloads

| Pattern | Description | Best For |
|---------|-------------|----------|
| `uniform` | Random uniform access | Worst case baseline |
| `zipf` | Power-law (few hot pages) | Database-like workloads |
| `sequential` | Sequential scan | Scan-heavy workloads |
| `hotspot` | 80/20 hot/cold split | Cache-friendly workloads |
| `temporal` | Recent pages more likely | Session-based workloads |
| `mixed` | Phases of above patterns | Real-world simulation |

## Metrics

The simulator measures:

- **Hit rate**: Tier-0 hits / total accesses
- **Latency**: Simulated access latency (ns)
- **Move rate**: Promotions + demotions / total accesses
- **BCVF rejection rate**: Proposed moves rejected by BCVF gate
- **Coherence**: Mean coherence of pages in tier-0

## Success Criteria

CTM+ validation passes if:

1. **>10% hit rate improvement** over LRU on at least one workload
2. **No >5% regression** on any workload
3. **Move rate <2x** compared to LRU (overhead acceptable)

## File Structure

```
simulator/
├── ctm_plus/
│   ├── __init__.py          # Package exports
│   ├── __main__.py          # Entry point for python -m
│   ├── cli.py               # Command-line interface
│   ├── simulator.py         # Main simulation engine
│   ├── core/
│   │   ├── config.py        # Configuration dataclasses
│   │   ├── state.py         # Page and tier state
│   │   └── metrics.py       # Metrics collection
│   ├── controllers/
│   │   ├── base.py          # Base controller interface
│   │   ├── lru.py           # LRU baseline
│   │   ├── arc.py           # ARC baseline
│   │   └── ctm_plus.py      # CTM+ implementation
│   └── traces/
│       └── loader.py        # Trace loading utilities
└── README.md
```

## Trace Format

### CSV Format

```csv
timestamp,page_id,op_type,size
0,1234,0,4096
1,1235,0,4096
2,1234,1,4096
```

- `op_type`: 0=READ, 1=WRITE, 2=PREFETCH
- `size`: Access size in bytes (default 4096)

### MSR Cambridge Format

Standard MSR block I/O trace format is also supported.

## Limitations

This simulator validates the **algorithm**, not the **implementation**:

| What It Proves | What It Doesn't Prove |
|----------------|----------------------|
| Algorithm makes better decisions | Timing constraints are met |
| Hit rate improves | Hardware fits in FPGA/ASIC |
| Move overhead is acceptable | Power consumption is acceptable |

For hardware validation, you need an FPGA prototype or cycle-accurate simulation.

## License

Part of Symbol-U project. See repository license.
