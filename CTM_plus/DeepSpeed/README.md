# CTM+ for DeepSpeed

Intelligent memory offloading for DeepSpeed using CTM+ (Coherence-Tier Memory Plus).

## Overview

CTM+ enhances DeepSpeed's memory management with smart offloading decisions for:
- **ZeRO-Offload**: Optimizer state and gradient management
- **Inference**: Model weight and KV cache offloading
- **Large Models**: Aggressive memory optimization for 100B+ models

### Key Features

- **Smart Victim Selection**: O(k) sampled scoring vs O(n) LRU scans
- **ARC-style Adaptation**: Dual shadow tiers with adaptive p
- **Prefetching**: Pattern-based tensor prefetching
- **Size-aware Scoring**: Penalizes large tensors for better memory efficiency
- **Compute Graph Protection**: Prevents eviction of active tensors

## Installation

```bash
cd CTM_plus/DeepSpeed
pip install -e .

# With DeepSpeed
pip install -e ".[deepspeed]"
```

## Quick Start

### Basic Offload Manager

```python
from ctm_plus_deepspeed import CTMOffloadManager, CTMDeepSpeedConfig

# Create offload manager
config = CTMDeepSpeedConfig.for_training()
manager = CTMOffloadManager(
    gpu_memory_bytes=40 * 1024**3,  # 40GB GPU
    cpu_memory_bytes=256 * 1024**3,  # 256GB CPU
    config=config,
)

# Register tensors
manager.register_tensor(
    tensor_id="layer.0.weight",
    name="layer.0.weight",
    size_bytes=4096 * 4096 * 4,
)

# Track access
needs_fetch, prefetch_list = manager.on_access("layer.0.weight", in_compute_graph=True)

# Get statistics
stats = manager.get_stats()
print(f"GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
```

### ZeRO-Offload Integration

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
zero.register_optimizer_state("opt.0.m", "layer.0.weight", size_bytes, "param.0", "momentum")
zero.register_optimizer_state("opt.0.v", "layer.0.weight", size_bytes, "param.0", "variance")

# Training loop
for batch in dataloader:
    zero.begin_forward()
    # ... forward pass ...
    zero.end_forward()

    zero.begin_backward()
    # ... backward pass ...
    zero.end_backward()

    zero.step()
```

### Inference Manager

```python
from ctm_plus_deepspeed import CTMInferenceManager, CTMDeepSpeedConfig

# Create inference manager
inference = CTMInferenceManager(
    gpu_memory_bytes=16 * 1024**3,
    cpu_memory_bytes=64 * 1024**3,
    config=CTMDeepSpeedConfig.for_inference(),
    num_layers=32,
)

# Register layers
for layer_idx in range(32):
    weights = {
        "q_proj": (f"layer.{layer_idx}.q", q_size),
        "k_proj": (f"layer.{layer_idx}.k", k_size),
        "v_proj": (f"layer.{layer_idx}.v", v_size),
        "mlp": (f"layer.{layer_idx}.mlp", mlp_size),
    }
    inference.register_layer(layer_idx, weights, initial_on_gpu=(layer_idx < 16))

# Generation
inference.begin_generation()
for token in range(max_tokens):
    for layer_idx in range(32):
        fetched = inference.on_layer_forward(layer_idx)
inference.end_generation()
```

## Configuration

### Preset Configurations

```python
from ctm_plus_deepspeed import CTMDeepSpeedConfig

# Training (frequent param/grad access)
config = CTMDeepSpeedConfig.for_training()

# Inference (less frequent updates)
config = CTMDeepSpeedConfig.for_inference()

# ZeRO-Offload (optimizer on CPU)
config = CTMDeepSpeedConfig.for_zero_offload()

# Large models (aggressive offloading)
config = CTMDeepSpeedConfig.for_large_model()
```

### Custom Configuration

```python
config = CTMDeepSpeedConfig(
    victim_sample_size=64,
    promotion_threshold=0.25,
    offload_threshold=0.15,
    prefetch_ahead=3,
    async_offload=True,

    # Scoring weights
    weight_recency=0.35,
    weight_frequency=0.30,
    weight_size=0.15,
    weight_compute=0.10,
    weight_gradient=0.10,

    # Pinning
    pin_optimizer_states=True,
    pin_gradients=True,
)
```

## Integration with DeepSpeed

### Generate DeepSpeed Config

```python
from ctm_plus_deepspeed import CTMOffloadManager, get_deepspeed_config_with_ctm

manager = CTMOffloadManager(gpu_memory, cpu_memory)
ds_config = get_deepspeed_config_with_ctm(manager)

# Use with DeepSpeed
model, optimizer, _, _ = deepspeed.initialize(
    model=model,
    config=ds_config,
)
```

### Custom Engine Integration

```python
import deepspeed
from ctm_plus_deepspeed import CTMOffloadManager

class CTMDeepSpeedEngine(deepspeed.DeepSpeedEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctm_manager = CTMOffloadManager(
            gpu_memory_bytes=self.get_gpu_memory(),
            cpu_memory_bytes=self.get_cpu_memory(),
        )

    def forward(self, *args, **kwargs):
        # Track parameter access
        for name, param in self.module.named_parameters():
            self.ctm_manager.on_access(name, in_compute_graph=True)
        return super().forward(*args, **kwargs)
```

## API Reference

### CTMOffloadManager

```python
class CTMOffloadManager:
    def __init__(
        self,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        config: CTMDeepSpeedConfig = None,
    ): ...

    def register_tensor(
        self,
        tensor_id: str,
        name: str,
        size_bytes: int,
        is_gradient: bool = False,
        is_optimizer_state: bool = False,
    ) -> None: ...

    def on_access(
        self,
        tensor_id: str,
        in_compute_graph: bool = False,
    ) -> Tuple[bool, List[str]]: ...  # (needs_fetch, prefetch_list)

    def pin_tensor(self, tensor_id: str) -> None: ...
    def unpin_tensor(self, tensor_id: str) -> None: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### CTMZeROOffload

```python
class CTMZeROOffload:
    def register_parameter(self, param_id, name, size_bytes, group_name): ...
    def register_optimizer_state(self, state_id, name, size_bytes, param_id, state_type): ...
    def register_gradient(self, grad_id, name, size_bytes, param_id): ...
    def begin_forward(self): ...
    def end_forward(self): ...
    def begin_backward(self): ...
    def end_backward(self): ...
    def step(self): ...
```

### CTMInferenceManager

```python
class CTMInferenceManager:
    def register_layer(self, layer_idx, weights, initial_on_gpu): ...
    def register_kv_cache(self, layer_idx, k_tensor_id, v_tensor_id, size): ...
    def begin_generation(self): ...
    def on_layer_forward(self, layer_idx) -> List[str]: ...
    def end_generation(self): ...
    def pin_layer(self, layer_idx): ...
    def unpin_layer(self, layer_idx): ...
```

## Example

Run the included example:

```bash
cd CTM_plus/DeepSpeed
python -m ctm_plus_deepspeed.example
```

Output:
```
CTM+ Offload Manager Demo
============================================================
Configuration:
  GPU Memory: 40.0 GB
  CPU Memory: 256.0 GB
  Smart Offload: True

Registering 216 tensors...

Results:
  Training Steps: 100
  GPU Hit Rate: 98.5%
  Offloads: 45
  Prefetches: 180
  Adaptive p: 0.534
```

## License

MIT
