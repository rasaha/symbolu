# CTM+ for vLLM

Intelligent KV cache block management for vLLM using CTM+ (Coherence-Tier Memory Plus).

## Overview

CTM+ provides smart eviction decisions for vLLM's PagedAttention KV cache, improving GPU memory utilization for LLM inference workloads.

### Key Features

- **Smart Victim Selection**: O(k) sampled scoring vs O(n) LRU scans
- **ARC-style Adaptation**: Dual shadow tiers with adaptive p
- **Loop Pinning**: Fast-track for temporal patterns in LLM inference
- **Neighbor Tracking**: Cluster protection for related blocks

## Installation

```bash
cd CTM_plus/vLLM
pip install -e .

# With vLLM integration
pip install -e ".[vllm]"
```

## Quick Start

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
promoted = manager.access(sequence_id=1, block_indices=[0, 1, 2])

# Free blocks when done
manager.free(sequence_id=1)

# Get statistics
stats = manager.get_stats()
print(f"GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
```

## Configuration

### Preset Configurations

```python
from ctm_plus_vllm import CTMvLLMConfig

# For typical LLM inference (chat, completion)
config = CTMvLLMConfig.for_llm_inference()

# For batch inference (many concurrent requests)
config = CTMvLLMConfig.for_batch_inference()

# For streaming (continuous generation)
config = CTMvLLMConfig.for_streaming()
```

### Custom Configuration

```python
config = CTMvLLMConfig(
    victim_sample_size=64,      # More samples = better decisions
    promotion_threshold=0.25,   # Lower = more aggressive promotion
    enable_smart_victim=True,   # Use CTM+ vs simple LRU

    # Scoring weights
    weight_recency=0.40,
    weight_frequency=0.30,
    weight_reuse=0.15,
    weight_coherence=0.10,
    weight_neighbor=0.10,
)
```

## Integration with vLLM

### Option 1: Monkey Patch

```python
from vllm import LLM
from ctm_plus_vllm import CTMBlockSpaceManager, CTMvLLMConfig

# Patch vLLM's block manager
original_init = LLM.__init__

def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    # Replace block manager
    self.llm_engine.scheduler.block_manager = CTMBlockSpaceManager(
        block_size=self.llm_engine.cache_config.block_size,
        num_gpu_blocks=self.llm_engine.cache_config.num_gpu_blocks,
        num_cpu_blocks=self.llm_engine.cache_config.num_cpu_blocks,
        ctm_config=CTMvLLMConfig.for_llm_inference(),
    )

LLM.__init__ = patched_init
```

### Option 2: Custom Engine

```python
from vllm.engine.llm_engine import LLMEngine
from ctm_plus_vllm import CTMBlockSpaceManager

class CTMEngine(LLMEngine):
    def _init_cache(self):
        super()._init_cache()
        # Replace with CTM+ block manager
        self.scheduler.block_manager = CTMBlockSpaceManager(
            block_size=self.cache_config.block_size,
            num_gpu_blocks=self.cache_config.num_gpu_blocks,
            num_cpu_blocks=self.cache_config.num_cpu_blocks,
        )
```

## API Reference

### CTMBlockSpaceManager

```python
class CTMBlockSpaceManager:
    def __init__(
        self,
        block_size: int,           # Tokens per block
        num_gpu_blocks: int,       # GPU block count
        num_cpu_blocks: int,       # CPU block count
        watermark: float = 0.1,    # Keep this fraction free
        ctm_config: CTMvLLMConfig = None,
    ): ...

    def allocate(self, sequence_id: int, num_blocks: int) -> List[int]: ...
    def access(self, sequence_id: int, block_indices: List[int]) -> List[int]: ...
    def free(self, sequence_id: int) -> None: ...
    def pin_sequence(self, sequence_id: int) -> None: ...
    def unpin_sequence(self, sequence_id: int) -> None: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### CTMEvictionPolicy

```python
class CTMEvictionPolicy:
    def on_block_access(self, block_id: int, sequence_id: int) -> Tuple[bool, bool]: ...
    def select_victim(self) -> Optional[int]: ...
    def evict_block(self, block_id: int) -> None: ...
    def promote_block(self, block_id: int) -> None: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

## Example

Run the included example:

```bash
cd CTM_plus/vLLM
python -m ctm_plus_vllm.example
```

Output:
```
CTM+ Block Manager for vLLM - Example
==================================================

Block Manager Configuration:
  GPU Blocks: 1000
  CPU Blocks: 10000
  Block Size: 16 tokens

--------------------------------------------------
Running LLM inference simulation...

Results:
  Completed Sequences: 500
  Total Accesses: 25000
  GPU Hit Rate: 94.5%
  Evictions: 1250
  Promotions: 320
  Smart Selections: 1250
  Adaptive p: 0.523
```

## License

MIT
