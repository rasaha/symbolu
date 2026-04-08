# CTM+ Installation & Wiring Guide

Complete setup guide for installing CTM+ (Coherence-Tier Memory Plus) on a GPU
environment and wiring it into standard transformer training or inference pipelines.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Python Packages](#2-install-python-packages)
3. [Build CUDA Library](#3-build-cuda-library)
4. [Build Kernel Module (Optional)](#4-build-kernel-module-optional)
5. [Verify Installation](#5-verify-installation)
6. [Wire Into Training](#6-wire-into-training)
7. [Wire Into Inference](#7-wire-into-inference)
8. [Wire Into Large Model Inference (70B+)](#8-wire-into-large-model-inference-70b)
9. [Wire Checkpoint Cache (Database)](#9-wire-checkpoint-cache-database)
10. [Configuration Reference](#10-configuration-reference)
11. [CLI Commands](#11-cli-commands)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA V100 (16GB) | A100/H100 (80GB) |
| CUDA | 11.0+ | 12.0+ |
| CPU RAM | 64GB | 256GB+ |
| OS | Linux (kernel 5.10+) | Ubuntu 22.04+ |

### Software

```bash
# System packages
sudo apt-get update
sudo apt-get install -y build-essential cmake git python3-dev

# CUDA toolkit (if not already installed)
# Verify with: nvcc --version && nvidia-smi

# Python 3.8+ (3.10+ recommended)
python3 --version
```

### Base Python dependencies

```bash
pip install torch>=2.0.0
pip install deepspeed>=0.9.0      # For training offload
pip install vllm>=0.2.0           # For inference KV cache
pip install psycopg2-binary       # For PostgreSQL (optional)
pip install redis                 # For Redis cache (optional)
```

---

## 2. Install Python Packages

Clone the repository and install each CTM+ package in editable mode.

```bash
# Clone repo (if not already)
git clone <repo-url> symbolu
cd symbolu
```

### All packages at once

```bash
pip install -e CTM_plus/DeepSpeed/
pip install -e CTM_plus/KVPolicy/
pip install -e CTM_plus/KVSimulator/
```

### With optional dependencies

```bash
# DeepSpeed package + actual DeepSpeed runtime
pip install -e "CTM_plus/DeepSpeed/[deepspeed]"

# vLLM package + actual vLLM runtime
pip install -e "CTM_plus/KVPolicy/[vllm]"

# Database package + PostgreSQL + Redis clients
pip install -e "CTM_plus/KVSimulator/[postgres,redis]"

# Dev dependencies (tests)
pip install -e "CTM_plus/DeepSpeed/[dev]"
pip install -e "CTM_plus/KVPolicy/[dev]"
pip install -e "CTM_plus/KVSimulator/[dev]"
```

### Set Python path for unified setup module

```bash
# Add to ~/.bashrc or your shell profile:
export PYTHONPATH="/path/to/symbolu:$PYTHONPATH"
```

---

## 3. Build CUDA Library

The CUDA library provides GPU-accelerated page management for HBM/GDDR tiering.

### Option A: CMake (recommended)

```bash
cd CTM_plus/CUDA/ctm_plus
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Install system-wide (optional)
sudo make install
sudo ldconfig
```

### Option B: Make

```bash
cd CTM_plus/CUDA/ctm_plus
make

# Override GPU architecture if needed:
# V100
make GPU_ARCH="-gencode arch=compute_70,code=sm_70"

# A100
make GPU_ARCH="-gencode arch=compute_80,code=sm_80"

# H100
make GPU_ARCH="-gencode arch=compute_90,code=sm_90"

# Install system-wide (optional)
sudo make install
```

### Verify CUDA build

```bash
cd CTM_plus/CUDA/ctm_plus
LD_LIBRARY_PATH=. ./example
LD_LIBRARY_PATH=. ./benchmark
```

### Use in your CUDA application

```cpp
#include "ctm_plus.cuh"

// Link: -lctm_plus_cuda -lcurand
// Or include ctm_plus.cu directly in your build
```

---

## 4. Build Kernel Module (Optional)

For OS-level memory tiering (HBM vs DDR on CXL systems). Not required for
Python-based training/inference.

```bash
cd CTM_plus/Kernel/ctm_plus
make

# Load
sudo insmod ctm_plus.ko tier0_pages=262144 tier1_pages=26214400

# Verify
cat /sys/kernel/ctm_plus/stats

# Unload
sudo rmmod ctm_plus
```

---

## 5. Verify Installation

Run these commands to confirm all packages are correctly installed:

```bash
# Individual packages
python -c "from ctm_plus_deepspeed import CTMOffloadManager, CTMDeepSpeedConfig; print('DeepSpeed integration: OK')"
python -c "from kv_policy import CTMBlockSpaceManager, CTMvLLMConfig; print('vLLM integration: OK')"
python -c "from kv_simulator import CTMBufferPool, CTMDBConfig; print('Database integration: OK')"

# Unified transformer setup
python -c "from CTM_plus.transformer_setup import CTMTransformerSetup; print('Transformer setup: OK')"

# Run package examples
python -m ctm_plus_deepspeed.example
python -m kv_policy.example
python -m kv_simulator.example

# Run tests
python -m pytest tests/test_ctm_transformer_setup.py -q
```

---

## 6. Wire Into Training

CTM+ manages GPU/CPU memory offloading during training via DeepSpeed ZeRO-Offload.

### Method A: Unified setup (recommended)

```python
from CTM_plus.transformer_setup import CTMTransformerSetup

# Create model (any standard transformer)
model = YourTransformerModel(...)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

# Initialize CTM+ for training
setup = CTMTransformerSetup.for_training(
    model=model,                  # Auto-detects architecture
    gpu_memory_gb=80,             # A100 80GB
    cpu_memory_gb=256,
    zero_stage=2,                 # ZeRO-2 offload
)

# Register model and optimizer
setup.register_model(model)
setup.register_optimizer(optimizer)

# Generate DeepSpeed config
ds_config = setup.get_deepspeed_config(base_config={
    "train_batch_size": 32,
    "gradient_accumulation_steps": 4,
    "fp16": {"enabled": True},
    "gradient_clipping": 1.0,
})

# Training loop
for step, batch in enumerate(dataloader):
    setup.begin_forward()
    loss = model(batch)
    setup.end_forward()

    setup.begin_backward()
    loss.backward()
    setup.end_backward()

    setup.step()
    optimizer.step()
    optimizer.zero_grad()

    # Monitor every 100 steps
    if step % 100 == 0:
        print(setup.log_stats(step=step))
```

### Method B: Direct DeepSpeed integration

```python
from ctm_plus_deepspeed import CTMZeROOffload, CTMDeepSpeedConfig, get_deepspeed_config_with_ctm

# Configure for your workload
config = CTMDeepSpeedConfig.for_training()

# Create ZeRO offload manager
zero = CTMZeROOffload(
    gpu_memory_bytes=80 * 1024**3,
    cpu_memory_bytes=256 * 1024**3,
    config=config,
    zero_stage=2,
)

# Register each parameter
for name, param in model.named_parameters():
    size = param.numel() * param.element_size()
    zero.register_parameter(f"param.{name}", name, size)
    zero.register_optimizer_state(f"opt.{name}.m", name, size, f"param.{name}", "momentum")
    zero.register_optimizer_state(f"opt.{name}.v", name, size, f"param.{name}", "variance")

# Generate DeepSpeed config
ds_config = get_deepspeed_config_with_ctm(zero.offload_manager)

# Initialize with DeepSpeed
import deepspeed
model_engine, optimizer, _, _ = deepspeed.initialize(
    model=model,
    config=ds_config,
)

# Training loop
for batch in dataloader:
    zero.begin_forward()
    loss = model_engine(batch)
    zero.end_forward()

    zero.begin_backward()
    model_engine.backward(loss)
    zero.end_backward()

    zero.step()
    model_engine.step()
```

### Method C: With existing train.py

Wire CTM+ into the existing SymbolU training script:

```bash
# Standard training (no CTM+)
python train.py --model_size medium --dataset c4 --max_steps 100000

# To add CTM+ offloading, modify train.py to import the setup:
```

```python
# Add to train.py after model creation:
from CTM_plus.transformer_setup import CTMTransformerSetup

ctm_setup = CTMTransformerSetup.for_training(
    model=model,
    gpu_memory_gb=80,
    zero_stage=2,
)
ctm_setup.register_model(model)

# Then wrap your training loop:
# ctm_setup.begin_forward() / end_forward() / begin_backward() / end_backward() / step()
```

### Training command examples

```bash
# Small model test (WikiText-2)
python train.py --model_size tiny --dataset wikitext2 --max_steps 1000

# 100M model on C4
python train.py --model_size medium --dataset c4 --batch_size 32 --gradient_accumulation 4

# 7B model on A100 80GB (requires CTM+ for memory management)
python train.py --model_size 7b --dataset c4 \
    --batch_size 1 --gradient_accumulation 64 \
    --gradient_checkpointing --max_seq_len 2048

# Multi-GPU with DDP
torchrun --nproc_per_node=4 train.py --model_size large --dataset c4

# Resume from checkpoint
python train.py --resume checkpoints/latest.pt

# With wandb logging
python train.py --model_size medium --wandb --wandb_project symbolu
```

---

## 7. Wire Into Inference

CTM+ manages KV cache blocks (vLLM) and model weight offloading (DeepSpeed)
during inference.

### Method A: Unified setup (recommended)

```python
from CTM_plus.transformer_setup import CTMTransformerSetup

# Initialize for inference
setup = CTMTransformerSetup.for_inference(
    model=model,
    num_gpu_blocks=2000,          # KV cache blocks on GPU
    num_cpu_blocks=20000,         # KV cache blocks on CPU
    block_size=16,                # Tokens per block
    gpu_memory_gb=40,
    cpu_memory_gb=256,
)

# Register model layers for weight offloading
setup.register_inference_model(model)

# Generation loop
def generate(prompt_tokens, max_new_tokens=128):
    seq_id = 0
    num_blocks = (len(prompt_tokens) + 15) // 16
    setup.allocate_kv_blocks(seq_id, num_blocks)

    setup.begin_generation()
    for token_idx in range(max_new_tokens):
        for layer_idx in range(model.num_layers):
            needs_fetch = setup.on_layer_forward(layer_idx)
        # ... generate next token ...
        setup.access_kv_blocks(seq_id)
    setup.end_generation()

    setup.free_kv_blocks(seq_id)
```

### Method B: Direct vLLM KV cache management

```python
from kv_policy import CTMBlockSpaceManager, CTMvLLMConfig

# Choose preset for your workload
config = CTMvLLMConfig.for_llm_inference()      # Chat/completion
# config = CTMvLLMConfig.for_batch_inference()   # Batch processing
# config = CTMvLLMConfig.for_streaming()         # Continuous generation

manager = CTMBlockSpaceManager(
    block_size=16,
    num_gpu_blocks=2000,
    num_cpu_blocks=20000,
    ctm_config=config,
)

# Per-request lifecycle
blocks = manager.allocate(sequence_id=1, num_blocks=10)
manager.access(sequence_id=1, block_indices=[0, 1, 2])
manager.pin_sequence(sequence_id=1)    # Prevent eviction for important sequences
manager.unpin_sequence(sequence_id=1)
manager.free(sequence_id=1)

print(f"GPU Hit Rate: {manager.get_stats()['gpu_hit_rate']:.2%}")
```

### Method C: vLLM monkey-patch (drop-in replacement)

```python
from vllm import LLM
from kv_policy import CTMBlockSpaceManager, CTMvLLMConfig

original_init = LLM.__init__

def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.llm_engine.scheduler.block_manager = CTMBlockSpaceManager(
        block_size=self.llm_engine.cache_config.block_size,
        num_gpu_blocks=self.llm_engine.cache_config.num_gpu_blocks,
        num_cpu_blocks=self.llm_engine.cache_config.num_cpu_blocks,
        ctm_config=CTMvLLMConfig.for_llm_inference(),
    )

LLM.__init__ = patched_init

# Use vLLM normally — CTM+ is now active
llm = LLM(model="meta-llama/Llama-2-7b-hf")
outputs = llm.generate(["Hello world"], max_tokens=100)
```

### Method D: Direct DeepSpeed inference (weight offloading)

```python
from ctm_plus_deepspeed import CTMInferenceManager, CTMDeepSpeedConfig

config = CTMDeepSpeedConfig.for_inference()
inference = CTMInferenceManager(
    gpu_memory_bytes=16 * 1024**3,
    cpu_memory_bytes=64 * 1024**3,
    config=config,
    num_layers=32,
)

# Register layers (first 16 on GPU, rest on CPU)
hidden = 4096
bpp = 2  # FP16
for i in range(32):
    weights = {
        "q_proj": (f"layer.{i}.q", hidden * hidden * bpp),
        "k_proj": (f"layer.{i}.k", hidden * hidden * bpp),
        "v_proj": (f"layer.{i}.v", hidden * hidden * bpp),
        "o_proj": (f"layer.{i}.o", hidden * hidden * bpp),
        "mlp":    (f"layer.{i}.mlp", hidden * 4 * hidden * bpp),
    }
    inference.register_layer(i, weights, initial_on_gpu=(i < 16))

# Generation
inference.begin_generation()
for token in range(max_tokens):
    for layer_idx in range(32):
        needs_fetch = inference.on_layer_forward(layer_idx)
inference.end_generation()
```

---

## 8. Wire Into Large Model Inference (70B+)

For models that exceed GPU memory, CTM+ combines weight offloading (DeepSpeed)
with KV cache management (vLLM).

```python
from CTM_plus.transformer_setup import CTMTransformerSetup

setup = CTMTransformerSetup.for_large_model_inference(
    model=model,
    gpu_memory_gb=80,             # Per-GPU
    cpu_memory_gb=512,
    num_layers=80,                # Llama-70B
    hidden_dim=8192,
    num_heads=64,
    tp_size=2,                    # Tensor parallel across 2 GPUs
    num_gpu_blocks=4000,
    num_cpu_blocks=40000,
    block_size=16,
)

# Register for weight offloading
setup.register_inference_model(model)

# Get block manager for KV cache
manager = setup.get_block_manager()

# Generation with both offloading and KV cache management
setup.begin_generation()
for token_idx in range(max_tokens):
    for layer_idx in range(80):
        fetched = setup.on_layer_forward(layer_idx)
    # ...
setup.end_generation()

# Monitor
print(setup.log_stats())
# Output:
#   CTM+ Stats
#     Inference: GPU hit=96.2%, GPU layers=40/80
#     vLLM: free GPU=1200/4000, evictions=450, sequences=32
```

---

## 9. Wire Checkpoint Cache (Database)

Use CTM+ as an intelligent cache for checkpoints, weights, or KV cache snapshots.

### Generic key-value cache

```python
from CTM_plus.transformer_setup import CTMTransformerSetup

setup = CTMTransformerSetup.for_checkpoint_cache(cache_size_mb=4096)
cache = setup.get_checkpoint_cache()

# Store/retrieve checkpoints
cache.put("checkpoint_step_1000", checkpoint_data)
data = cache.get("checkpoint_step_1000")
```

### PostgreSQL buffer pool

```python
from kv_simulator import PostgresCTMExtension, CTMDBConfig

pg = PostgresCTMExtension(
    shared_buffers=8192,
    config=CTMDBConfig.for_postgres(),
)
```

### Redis-style cache

```python
from kv_simulator import RedisCTMCache, CTMDBConfig

cache = RedisCTMCache(
    maxmemory=1024 * 1024 * 1024,   # 1GB
    config=CTMDBConfig.for_redis(),
)

cache.set("session:123", session_data, ex=3600)
value = cache.get("session:123")
```

---

## 10. Configuration Reference

### DeepSpeed presets

| Preset | Use Case | victim_sample | promote_thresh | prefetch |
|--------|----------|---------------|----------------|----------|
| `for_training()` | Standard training | 64 | 0.25 | 3 |
| `for_inference()` | Model serving | 32 | 0.35 | 1 |
| `for_zero_offload()` | ZeRO-2/3 training | 48 | 0.30 | 2 |
| `for_large_model()` | 70B+ models | 96 | 0.40 | 4 |

### vLLM presets

| Preset | Use Case | victim_sample | promote_thresh |
|--------|----------|---------------|----------------|
| `for_llm_inference()` | Chat/completion | 32 | 0.20 |
| `for_batch_inference()` | Batch processing | 64 | 0.35 |
| `for_streaming()` | Continuous gen | 48 | 0.25 |

### Database presets

| Preset | Use Case | victim_sample | prefetch |
|--------|----------|---------------|----------|
| `for_oltp()` | Random access | 64 | disabled |
| `for_olap()` | Sequential scans | 32 | 16 pages |
| `for_mixed()` | Mixed workloads | 48 | 4 pages |
| `for_postgres()` | PostgreSQL | 48 | 8 pages |
| `for_redis()` | Key-value cache | 64 | disabled |

### Custom tuning

```python
from ctm_plus_deepspeed import CTMDeepSpeedConfig

config = CTMDeepSpeedConfig(
    # Victim selection
    victim_sample_size=48,        # Higher = better decisions, more overhead
    promotion_threshold=0.30,     # Lower = more aggressive GPU placement
    offload_threshold=0.20,       # Below this score, offload to CPU

    # Prefetching
    prefetch_ahead=2,             # Layers to prefetch (training: 3, inference: 1)
    async_offload=True,           # Async CPU-GPU transfers

    # Pinning
    pin_optimizer_states=True,    # Keep optimizer on GPU (ZeRO-1/2)
    pin_gradients=True,           # Keep gradients on GPU

    # Scoring weights (must sum to ~1.0)
    weight_recency=0.35,          # Recent access = keep on GPU
    weight_frequency=0.30,        # Frequent access = keep on GPU
    weight_size=0.15,             # Large tensors penalized (offload first)
    weight_compute=0.10,          # In compute graph = protected
    weight_gradient=0.10,         # Gradient tensors protected in backward

    # ARC adaptation
    adaptive_p_learning_rate=0.1, # How fast recency/frequency balance adapts
    shadow_size=2048,             # Ghost cache size for tracking evictions
)
```

---

## 11. CLI Commands

### Run benchmarks

```bash
# vLLM KV cache benchmark
python -m kv_policy.benchmark_cli compare --seq-len 4096 --cache-ratio 0.5

# DeepSpeed offload simulation
python -m ctm_plus_deepspeed.example

# Database buffer pool benchmark
python -m kv_simulator.example

# Run all CTM+ tests
python -m pytest tests/test_ctm_transformer_setup.py -v
```

### Training commands with CTM+

```bash
# Quick test (tiny model, local dataset)
python train.py --model_size tiny --dataset wikitext2 --max_steps 1000

# 50M parameter model
python train.py --model_size small --dataset c4 --max_steps 100000

# 100M model on A100
python train.py --model_size medium --dataset c4 \
    --batch_size 32 --gradient_accumulation 4

# 350M model with gradient checkpointing
python train.py --model_size large --dataset c4 \
    --gradient_checkpointing --batch_size 8 --gradient_accumulation 8

# 1.3B model
python train.py --model_size xl --dataset c4 \
    --batch_size 2 --gradient_accumulation 32 --gradient_checkpointing

# 7B model on A100 80GB
python train.py --model_size 7b --dataset c4 \
    --batch_size 1 --gradient_accumulation 64 \
    --gradient_checkpointing --max_seq_len 2048

# Multi-GPU DDP
torchrun --nproc_per_node=4 train.py --model_size large --dataset c4

# RunPod / cloud setup
bash runpod_7b_setup.sh
```

### CUDA library commands

```bash
cd CTM_plus/CUDA/ctm_plus

# Build everything
make

# Run example
make run_example

# Run benchmark
make run_benchmark

# Install system-wide
sudo make install

# Clean
make clean
```

### Kernel module commands

```bash
cd CTM_plus/Kernel/ctm_plus

# Build
make

# Load with 1GB fast tier, 100GB slow tier
sudo insmod ctm_plus.ko tier0_pages=262144 tier1_pages=26214400

# Monitor
watch -n 1 cat /sys/kernel/ctm_plus/stats

# Tune at runtime
echo 64 > /sys/kernel/ctm_plus/victim_sample_size
echo 40 > /sys/kernel/ctm_plus/promotion_threshold

# Unload
sudo rmmod ctm_plus
```

---

## 12. Troubleshooting

### Import errors

```
ModuleNotFoundError: No module named 'ctm_plus_deepspeed'
```

**Fix:** Install the package:
```bash
pip install -e CTM_plus/DeepSpeed/
```

```
ModuleNotFoundError: No module named 'CTM_plus.transformer_setup'
```

**Fix:** Add the repo root to PYTHONPATH:
```bash
export PYTHONPATH="/path/to/symbolu:$PYTHONPATH"
```

### CUDA build failures

```
nvcc fatal: Unsupported gpu architecture 'compute_90'
```

**Fix:** Your CUDA toolkit is too old for H100. Either upgrade CUDA or set the
architecture:
```bash
make GPU_ARCH="-gencode arch=compute_80,code=sm_80"
```

### Out of memory during training

**Fix:** Enable CTM+ offloading with higher ZeRO stage:
```python
setup = CTMTransformerSetup.for_training(
    model=model,
    gpu_memory_gb=40,
    zero_stage=3,           # More aggressive offloading
)
```

Or reduce batch size and use gradient checkpointing:
```bash
python train.py --model_size 7b --batch_size 1 \
    --gradient_accumulation 64 --gradient_checkpointing
```

### Low GPU hit rate

If `gpu_hit_rate` is below 90%, tune the config:

```python
config = CTMDeepSpeedConfig(
    victim_sample_size=96,        # Better victim selection
    promotion_threshold=0.20,     # More aggressive promotion
    prefetch_ahead=4,             # Prefetch more layers
    shadow_size=4096,             # Larger ghost cache
)
```

### Verifying CTM+ is active

```python
stats = setup.get_stats()
print(setup.log_stats(step=current_step))

# Expected output:
# CTM+ Stats (step=1000)
#   DeepSpeed: GPU hit=98.5%, offloads=45, phase=idle
```

---

## Package Structure

```
CTM_plus/
├── INSTALL.md                    # This file
├── README.md                     # Overview and algorithm details
├── transformer_setup.py          # Unified setup module
├── CUDA/
│   └── ctm_plus/                 # GPU kernel library
│       ├── ctm_plus.cuh          # C++ API header
│       ├── ctm_plus.cu           # CUDA implementation
│       ├── CMakeLists.txt        # CMake build
│       └── Makefile              # Make build
├── DeepSpeed/
│   ├── setup.py                  # pip install -e .
│   └── ctm_plus_deepspeed/       # Python package
│       ├── config.py             # CTMDeepSpeedConfig
│       ├── offload_manager.py    # Core offload logic
│       ├── zero_integration.py   # ZeRO-Offload support
│       ├── inference.py          # Inference weight offload
│       └── example.py            # Usage example
├── KVPolicy/
│   ├── setup.py                  # pip install -e .
│   └── kv_policy/                # Python package
│       ├── config.py             # KVCachePolicyConfig
│       ├── attention_evictor.py  # KV cache eviction policy
│       └── kv_cache_simulator.py # Standalone benchmark
└── KVSimulator/
    ├── setup.py                  # pip install -e .
    └── kv_simulator/             # Python package
        ├── config.py             # SimulationConfig
        └── buffer_pool.py        # KV cache simulator
```

---

## License

- CUDA library: MIT
- Python packages (DeepSpeed, vLLM, Database): MIT
- Kernel module: GPL-2.0
- Unified transformer setup: MIT
