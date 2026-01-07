# Memory Efficiency Benchmark

## Overview

This document describes the `benchmark_memory.py` script that compares memory consumption across different transformer architectures during training.

**Primary Comparison**: Standard O(n²) vs Hybrid O(n×w) - proves consumer GPU viability for production LLMs.

## Architecture Comparison

| Model | Attention Type | Memory Complexity | Best For |
|-------|---------------|-------------------|----------|
| **StandardTransformer** | Full attention | **O(n²)** - creates [B, H, N, N] matrix | Baseline comparison |
| **HybridPhaseTransformer** | Local + Phase | **O(n×w)** - window size w | Production quality + efficiency |
| **PhaseTransformer** | Phase attention | **O(n)** - state accumulation only | Maximum memory efficiency |

> **Note**: The default comparison is Standard vs Hybrid for production-quality benchmarking.

## Memory Scaling

### Standard Attention: O(n²)
```
Attention Matrix Memory = B × H × N × N × 4 bytes (float32)

Example at 8K tokens, 12 heads:
= 1 × 12 × 8192 × 8192 × 4 = 3.2 GB (just for attention!)
```

### Phase Attention: O(n)
```
State Memory = B × H × D × 4 bytes (constant!)

Example at 8K tokens, 12 heads, 64 head_dim:
= 1 × 12 × 64 × 4 = 3 KB (negligible)
```

## Usage

### Basic Usage

```bash
# Default: Compare Standard O(n²) vs Hybrid O(n×w)
python benchmark_memory.py --quick

# Full test (512-32K tokens)
python benchmark_memory.py --full

# Specific sequence lengths
python benchmark_memory.py --seq_lengths 1024,4096,8192,16384
```

### Hybrid Configuration (V9.6.12+)

```bash
# Test different cosine modes
python benchmark_memory.py --cosine_mode standard --full   # Default
python benchmark_memory.py --cosine_mode shifted --full    # No negative interference
python benchmark_memory.py --cosine_mode complex --full    # Full cos+sin

# Test with decay gamma for local focus
python benchmark_memory.py --decay_gamma 0.95 --full       # ~20 token memory
python benchmark_memory.py --decay_gamma 0.9 --full        # ~10 token memory

# Adjust local attention window
python benchmark_memory.py --window_size 512 --full        # Larger window
```

### Model Selection

```bash
# Compare specific models
python benchmark_memory.py --models standard,hybrid        # Default (production)
python benchmark_memory.py --models standard,phase         # True O(n²) vs O(n)
python benchmark_memory.py --models standard,hybrid,phase  # All three

# Different model sizes
python benchmark_memory.py --model_size tiny    # 256d, 4L, 4H
python benchmark_memory.py --model_size small   # 512d, 8L, 8H (default)
python benchmark_memory.py --model_size medium  # 768d, 12L, 12H
python benchmark_memory.py --model_size large   # 1024d, 24L, 16H

# Inference only (no backward pass)
python benchmark_memory.py --no_backward

# Save results to JSON
python benchmark_memory.py --full --output results.json
```

## Expected Results

### At Short Sequences (512-2K)
- Standard and Phase have similar memory usage
- Model parameters dominate memory consumption
- Phase has slight overhead from state tracking

### At Medium Sequences (4K-8K)
- Standard memory grows quadratically
- Phase memory grows linearly
- Crossover point where Phase becomes more efficient

### At Long Sequences (16K-32K)
- Standard: Often hits OOM on consumer GPUs
- Phase: Still fits comfortably
- Memory savings: 50-80%+

## Understanding the Results

### Scaling Ratio
When sequence length doubles:
- **O(n²)**: Memory increases ~4x
- **O(n)**: Memory increases ~2x
- **O(n log n)**: Memory increases ~2.2x

### Why Hybrid Uses More Memory Than Phase
The Hybrid model combines:
1. **LocalAttention**: Sliding window attention for local patterns
2. **PhaseAttention**: Global context via state accumulation

LocalAttention with the `unfold` backend creates intermediate tensors, increasing base memory. However:
- Scaling is still O(n) (better than Standard)
- Quality is significantly better (combines local + global)
- At very long sequences, still much more efficient than Standard

### GPU Compatibility Table

| GPU | VRAM | Standard Max | Phase Max | Hybrid Max |
|-----|------|--------------|-----------|------------|
| RTX 4070 | 12GB | ~4K | ~16K | ~8K |
| RTX 4090 | 24GB | ~8K | ~32K | ~16K |
| A100-40GB | 40GB | ~12K | ~64K+ | ~32K |
| A100-80GB | 80GB | ~16K | ~128K+ | ~64K |

## Key Findings

### 1. Phase Attention Enables Consumer GPU Training
- Standard 32K context: Requires A100/H100 (80GB HBM3E)
- Phase 32K context: Runs on RTX 4090 (24GB GDDR6X)
- **Cost difference: $30,000+ vs $1,600**

### 2. Scaling Behavior
- Standard: Memory explodes at long sequences
- Phase: Linear growth, predictable resource usage
- Hybrid: Best of both worlds for production

### 3. Training vs Inference
- Backward pass doubles memory (activations + gradients)
- Use `--no_backward` to benchmark inference only
- Production inference uses much less memory than training

## Interpretation Guide

### When Standard is Better
- Very short sequences (<1K tokens)
- When you have abundant HBM memory
- Maximum attention precision needed

### When Phase is Better
- Long context training (8K+ tokens)
- Limited GPU memory
- Maximum memory efficiency needed
- Pathfinder/Path-X style tasks

### When Hybrid is Better
- Production LLM training
- Balance of quality and efficiency
- Medium-long contexts (2K-16K)

## Troubleshooting

### OOM Errors
1. Reduce `--batch_size` (default: 1)
2. Reduce `--seq_lengths`
3. Use `--model_size tiny` for testing

### Unexpected Results
1. Ensure GPU is available (`torch.cuda.is_available()`)
2. Close other GPU processes
3. Run with `--verbose` for detailed output

## Technical Details

### Memory Measurement
- Uses `torch.cuda.max_memory_allocated()` for peak memory
- Includes warmup iterations to stabilize measurements
- Averages over multiple runs for accuracy

### Model Configurations

```python
MODEL_PRESETS = {
    "tiny":   {"embed_dim": 256,  "num_layers": 4,  "num_heads": 4,  "ff_dim": 1024},
    "small":  {"embed_dim": 512,  "num_layers": 8,  "num_heads": 8,  "ff_dim": 2048},
    "medium": {"embed_dim": 768,  "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
    "large":  {"embed_dim": 1024, "num_layers": 24, "num_heads": 16, "ff_dim": 4096},
}
```

## References

- Phase Attention: O(n) attention via state accumulation
- Local Attention: Sliding window attention O(n×w)
- Flash Attention: Memory-efficient attention implementation
