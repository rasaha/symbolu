# CTM+ (Coherence-Tier Memory Plus)

A smart memory tiering controller that optimizes page placement between fast and slow memory tiers.

## Overview

CTM+ provides intelligent page management for tiered memory systems, achieving up to **+17.8% improvement** over LRU on hotspot workloads while maintaining competitive performance with ARC across all workload types.

### Key Features

- **Smart Victim Selection**: O(k) sampled scoring instead of O(n) scans
- **ARC-style Shadow Tiers**: Dual ghost caches (B1/B2) with adaptive p
- **Loop Pinning**: Fast-track promotion for temporal patterns
- **Neighbor Tracking**: Cluster protection via co-occurrence analysis
- **Workload Adaptation**: Mode switching between zipfian/temporal/hotspot

### Performance Summary

| Workload | CTM+ vs LRU | CTM+ vs ARC |
|----------|-------------|-------------|
| Zipfian (database) | +2.1% | -0.3% |
| Hotspot (batch) | +17.8% | -0.9% |
| Temporal (LLM/streaming) | -0.8% | -0.7% |
| Mixed | +2.0% | -0.5% |
| Uniform (worst case) | -0.04% | -0.04% |

## Package Structure

```
CTM_plus/
├── README.md                 # This file
├── Kernel/
│   └── ctm_plus/            # Linux kernel module
│       ├── ctm_plus.h       # API and data structures
│       ├── ctm_plus_core.c  # Core algorithm (C)
│       ├── ctm_plus_module.c # Module interface
│       ├── Makefile         # Build system
│       └── README.md        # Kernel module docs
├── CUDA/
│   └── ctm_plus/            # CUDA/GPU implementation
│       ├── ctm_plus.cuh     # CUDA header and API
│       ├── ctm_plus.cu      # CUDA implementation
│       ├── example.cu       # Usage example
│       ├── benchmark.cu     # Performance benchmark
│       ├── CMakeLists.txt   # CMake build system
│       └── Makefile         # Make build system
├── vLLM/
│   ├── setup.py             # Package installer
│   ├── README.md            # vLLM integration docs
│   └── ctm_plus_vllm/       # Python package
│       ├── __init__.py      # Package init
│       ├── config.py        # Configuration
│       ├── evictor.py       # CTM+ eviction policy
│       ├── block_manager.py # Block space manager
│       └── example.py       # Usage example
├── DeepSpeed/
│   ├── setup.py             # Package installer
│   ├── README.md            # DeepSpeed integration docs
│   └── ctm_plus_deepspeed/  # Python package
│       ├── __init__.py      # Package init
│       ├── config.py        # Configuration
│       ├── offload_manager.py # CTM+ offload manager
│       ├── zero_integration.py # ZeRO-Offload support
│       ├── inference.py     # Inference manager
│       └── example.py       # Usage example
└── ../simulator/
    └── ctm_plus/            # Python simulator
        ├── controllers/
        │   └── ctm_plus.py  # Main controller
        ├── core/
        │   ├── config.py    # Configuration
        │   └── state.py     # Page/tier state
        └── traces/          # Workload generators
```

## Quick Start

### Python Simulator

```bash
# Run validation suite
python3 simulator/run_validation.py

# Run ablation study
python3 simulator/run_ablation.py --events 50000

# Custom simulation
python3 -c "
from ctm_plus import Simulator
from ctm_plus.controllers.ctm_plus import CTMPlusController
from ctm_plus.traces import generate_synthetic_trace

sim = Simulator(tier0_size=1000, tier1_size=100000)
trace = generate_synthetic_trace(num_events=100000, pattern='zipf')
ctrl = CTMPlusController(sim.config)
result = sim.run(trace, ctrl, 'test')
print(f'Hit rate: {result.metrics.hit_rate:.2%}')
"
```

### Kernel Module

```bash
# Build
cd CTM_plus/Kernel/ctm_plus
make

# Load module
sudo insmod ctm_plus.ko tier0_pages=1000 tier1_pages=100000

# Check status
cat /sys/kernel/ctm_plus/stats

# Unload
sudo rmmod ctm_plus
```

### CUDA/GPU

```bash
# Build with CMake
cd CTM_plus/CUDA/ctm_plus
mkdir build && cd build
cmake ..
make

# Or build with Make
cd CTM_plus/CUDA/ctm_plus
make

# Run example
LD_LIBRARY_PATH=. ./example

# Run benchmark
LD_LIBRARY_PATH=. ./benchmark
```

**Using in your CUDA application:**

```cpp
#include "ctm_plus.cuh"

int main() {
    ctm::initialize_device(0);

    // Create controller (1000 tier0 pages, 100000 tier1 pages)
    ctm::Controller ctrl(1000, 100000);

    // Process page accesses (device pointers)
    uint64_t* d_page_ids;    // Your page IDs on GPU
    bool* d_promotions;       // Output: pages to promote
    bool* d_demotions;        // Output: pages to demote

    ctrl.on_access_batch(d_page_ids, num_pages, d_promotions, d_demotions);

    // Select victims for eviction
    uint64_t* d_victims;
    ctrl.select_victims(num_to_evict, d_victims);

    // Get statistics
    ctm::Stats stats = ctrl.get_stats();
    printf("Hit rate: %.2f%%\n",
           100.0 * stats.tier0_hits / (stats.tier0_hits + stats.misses));

    return 0;
}
```

### vLLM Integration

```bash
# Install
cd CTM_plus/vLLM
pip install -e .

# Run example
python -m ctm_plus_vllm.example
```

**Using in your vLLM application:**

```python
from ctm_plus_vllm import CTMBlockSpaceManager, CTMvLLMConfig

# Create block manager with CTM+
config = CTMvLLMConfig.for_llm_inference()
manager = CTMBlockSpaceManager(
    block_size=16,
    num_gpu_blocks=1000,
    num_cpu_blocks=10000,
    ctm_config=config,
)

# Allocate blocks for a sequence
blocks = manager.allocate(sequence_id=1, num_blocks=10)

# Access blocks (triggers CTM+ tracking)
manager.access(sequence_id=1, block_indices=[0, 1, 2])

# Free blocks when done
manager.free(sequence_id=1)

# Get statistics
stats = manager.get_stats()
print(f"GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
```

### DeepSpeed Integration

```bash
# Install
cd CTM_plus/DeepSpeed
pip install -e .

# Run example
python -m ctm_plus_deepspeed.example
```

**Using for ZeRO-Offload:**

```python
from ctm_plus_deepspeed import CTMOffloadManager, CTMDeepSpeedConfig

# Create offload manager
config = CTMDeepSpeedConfig.for_zero_offload()
manager = CTMOffloadManager(
    gpu_memory_bytes=40 * 1024**3,   # 40GB GPU
    cpu_memory_bytes=256 * 1024**3,  # 256GB CPU
    config=config,
)

# Register model tensors
manager.register_tensor(
    tensor_id="layer.0.weight",
    name="layer.0.weight",
    size_bytes=4096 * 4096 * 4,
)

# Track access (returns prefetch suggestions)
needs_fetch, prefetch_list = manager.on_access(
    "layer.0.weight", in_compute_graph=True
)

# Get statistics
stats = manager.get_stats()
print(f"GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
print(f"Offloads: {stats['offloads']}")
```

## Configuration

### Python Simulator

```python
from ctm_plus.core.config import CTMPlusConfig

# Default configuration
config = CTMPlusConfig()

# Custom configuration
config = CTMPlusConfig(
    victim_sample_size=48,        # Sample size for victim selection
    promotion_threshold=0.3,      # Min score to promote (0-1)
    loop_pin_reuse_threshold=0.4, # Reuse threshold for loop pinning
    loop_pin_neighbor_threshold=0.3,  # Neighbor hotness threshold
    enable_smart_victim=True,     # Use smart victim vs LRU
)
```

### Kernel Module (sysfs)

```bash
# View current config
cat /sys/kernel/ctm_plus/victim_sample_size
cat /sys/kernel/ctm_plus/promotion_threshold
cat /sys/kernel/ctm_plus/smart_victim

# Modify at runtime
echo 64 > /sys/kernel/ctm_plus/victim_sample_size
echo 40 > /sys/kernel/ctm_plus/promotion_threshold
echo 1 > /sys/kernel/ctm_plus/smart_victim

# View statistics
cat /sys/kernel/ctm_plus/stats

# Reset statistics
echo reset > /sys/kernel/ctm_plus/stats
```

### CUDA/GPU

```cpp
#include "ctm_plus.cuh"

// Create controller with custom stream
cudaStream_t stream;
cudaStreamCreate(&stream);
ctm::Controller ctrl(tier0_pages, tier1_pages, stream);

// Configure at runtime
ctm::Config config;
config.victim_sample_size = 64;
config.promotion_threshold = 0.25f;
config.enable_smart_victim = true;
ctrl.set_config(config);

// Async operations on stream
ctrl.on_access_batch(d_page_ids, num_pages, d_promotions, d_demotions);
ctrl.select_victims(num_victims, d_victim_ids);

// Synchronize when needed
ctrl.synchronize();
```

**Memory allocation with CTM+ hints:**

```cpp
void* ptr;
// Allocate with preferred tier (0=HBM/fast, 1=DDR/slow)
ctm::ctm_malloc_managed(&ptr, size, 0);  // Prefer HBM

// Use normally
// ...

// Free
ctm::ctm_free(ptr);
```

## Algorithm Details

### Core Components

1. **Phase Integrator**
   - Learns access patterns via streaming accumulator
   - Formula: `M_t = γ·M_{t-1} + (1-γ)·(k_t ⊙ v_t)`

2. **USE Coherence**
   - Fast path: `C_fast = α·c_i + β·(1-δ_i) + γ·cos(φ_i - φ̄)`
   - Slow path: `C_{i,j} = (1/W) Σ cos(φ_i - φ_j)`

3. **Dual Shadow Tier**
   - B1: Ghost cache for tier0 evictions
   - B2: Ghost cache for tier1 evictions
   - Adaptive p: Balances recency vs frequency

4. **Smart Victim Selection**
   - Samples k candidates (default 48)
   - Weighted scoring: 40% recency + 30% frequency + 15% reuse + 10% coherence - 10% neighbor protection

### Removed Components

Based on ablation studies, these components were removed:

- **BCVF Gate**: Zero effect on hit rate
- **SCC Optimizer**: Depended on BCVF
- **Admission Controller**: Hurt temporal workloads (-3.35% → -0.74%)

## Use Cases

### Database Workloads (Zipfian)

```python
config = CTMPlusConfig(
    victim_sample_size=64,
    promotion_threshold=0.25,
)
```

### LLM Inference (Temporal)

```python
config = CTMPlusConfig(
    victim_sample_size=32,
    promotion_threshold=0.2,
    loop_pin_reuse_threshold=0.3,  # Lower threshold for faster loop detection
)
```

### Batch Processing (Hotspot)

```python
# Default config works well
config = CTMPlusConfig()
```

### GPU Memory (HBM vs GDDR)

```cpp
// For GPU memory tiering (H100, MI300X, etc.)
ctm::Config config;
config.victim_sample_size = 48;      // Balance accuracy vs latency
config.promotion_threshold = 0.3f;   // Moderate threshold
config.enable_smart_victim = true;   // Use smart selection

ctm::Controller ctrl(hbm_pages, gddr_pages, stream);
ctrl.set_config(config);
```

### Multi-GPU Unified Memory

```cpp
// For unified memory across GPUs
for (int gpu = 0; gpu < num_gpus; gpu++) {
    cudaSetDevice(gpu);
    controllers[gpu] = new ctm::Controller(
        local_hbm_pages,
        remote_hbm_pages + host_pages,
        streams[gpu]
    );
}
```

## Integration

### With vLLM (PagedAttention)

CTM+ provides a drop-in block manager for vLLM:

```python
from ctm_plus_vllm import CTMBlockSpaceManager, CTMvLLMConfig

# Preset configs for different use cases
config = CTMvLLMConfig.for_llm_inference()    # Chat/completion
config = CTMvLLMConfig.for_batch_inference()  # Batch processing
config = CTMvLLMConfig.for_streaming()        # Continuous generation

# Create block manager
manager = CTMBlockSpaceManager(
    block_size=16,
    num_gpu_blocks=1000,
    num_cpu_blocks=10000,
    ctm_config=config,
)

# Pin important sequences to prevent eviction
manager.pin_sequence(sequence_id=1)

# Monitor performance
stats = manager.get_stats()
print(f"GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
print(f"Adaptive p: {stats['adaptive_p']:.3f}")
```

See `CTM_plus/vLLM/README.md` for full integration instructions.

### With DeepSpeed (ZeRO-Offload)

CTM+ provides intelligent offloading for DeepSpeed training and inference:

```python
from ctm_plus_deepspeed import CTMZeROOffload, CTMDeepSpeedConfig

# Create ZeRO offload manager
zero = CTMZeROOffload(
    gpu_memory_bytes=24 * 1024**3,
    cpu_memory_bytes=128 * 1024**3,
    config=CTMDeepSpeedConfig.for_zero_offload(),
    zero_stage=2,
)

# Register parameters and optimizer states
zero.register_parameter("param.0", "layer.0.weight", size_bytes)
zero.register_optimizer_state("opt.0.m", "layer.0", size_bytes, "param.0", "momentum")

# Training loop with automatic offload management
for batch in dataloader:
    zero.begin_forward()
    loss = model(batch)
    zero.end_forward()

    zero.begin_backward()
    loss.backward()
    zero.end_backward()

    zero.step()
```

See `CTM_plus/DeepSpeed/README.md` for full integration instructions.

### With Linux Memory Tiering

```bash
# Load CTM+ module
sudo modprobe ctm_plus tier0_pages=262144  # 1GB HBM
                       tier1_pages=26214400 # 100GB DDR

# CTM+ will handle page placement decisions
# Monitor via sysfs
watch -n 1 cat /sys/kernel/ctm_plus/stats
```

## Benchmarking

```bash
# Full validation (all workloads)
python3 simulator/run_validation.py

# Quick test (single workload)
python3 simulator/run_ablation.py --temporal-only --events 20000

# Compare with ARC baseline
python3 -c "
from ctm_plus import Simulator
from ctm_plus.controllers.arc import ARCController
from ctm_plus.controllers.ctm_plus import CTMPlusController
from ctm_plus.traces import generate_synthetic_trace

sim = Simulator(tier0_size=1000, tier1_size=100000)
trace = generate_synthetic_trace(100000, pattern='zipf')

arc = ARCController(sim.config)
ctm = CTMPlusController(sim.config)

arc_result = sim.run(trace, arc, 'arc')
trace = generate_synthetic_trace(100000, pattern='zipf')  # Regenerate
ctm_result = sim.run(trace, ctm, 'ctm')

print(f'ARC: {arc_result.metrics.hit_rate:.2%}')
print(f'CTM+: {ctm_result.metrics.hit_rate:.2%}')
"
```

## License

- GPL-2.0 (Kernel module)
- MIT (Python simulator)
- MIT (CUDA library)
- MIT (vLLM integration)
- MIT (DeepSpeed integration)

## References

- [ARC: A Self-Tuning, Low Overhead Replacement Cache](https://www.usenix.org/conference/fast-03/arc-self-tuning-low-overhead-replacement-cache)
- [Linux Memory Tiering](https://docs.kernel.org/admin-guide/mm/memory-tiering.html)
- [DAMON](https://docs.kernel.org/mm/damon/index.html)
