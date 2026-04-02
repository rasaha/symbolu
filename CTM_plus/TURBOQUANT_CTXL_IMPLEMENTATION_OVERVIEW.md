# TurboQuant + CTXL Integration: Cross-Layer Implementation Overview

## What This Project Does (Plain English)

Modern AI models (like ChatGPT, Claude, and similar large language models) have
a fundamental memory problem: they need to remember every word in the
conversation to generate the next word, and that memory — called the **KV cache**
— grows linearly with conversation length. A 128K-token conversation on a
70-billion-parameter model can consume over 40 GB of the GPU's fastest memory
(HBM). Most GPUs only have 80 GB total, and the model weights already take up
most of that.

This project solves that problem with two complementary ideas:

### 1. Smart Compression (TurboQuant)

Instead of storing every remembered word at full precision (16 bits per number),
we mathematically compress them down to just 3 bits — a **5.3x size reduction**
— while preserving over 96% of the original information. The technique is called
TurboQuant and works by converting vectors into polar coordinates and quantizing
the angles onto a fixed grid. A secondary correction step (QJL) adds 1 bit per
dimension to remove bias in the compressed representation.

Think of it like JPEG compression for images: you lose a tiny bit of quality,
but you can fit 5x more images in the same space.

### 2. Smart Eviction (CTM+)

Even with compression, you eventually run out of memory. When that happens,
you need to decide which remembered words to throw away. Most systems use a
simple rule: throw away the oldest one (LRU). CTM+ is smarter — it scores every
token based on 6 signals:

- **Recency**: Was it accessed recently?
- **Frequency**: Has it been accessed many times?
- **Attention strength**: Does the model pay a lot of attention to it?
- **Token importance**: Is it a named entity, number, or instruction (vs punctuation)?
- **Position**: Is it at the very beginning (attention sink) or very end (recent context)?
- **Compression quality**: Did it compress well? (If not, evicting it costs more.)

The lowest-scoring token gets evicted first.

### 3. Tiered Memory (CTXL)

Rather than just "keep" or "throw away," we add a middle tier — like how your
computer has fast RAM and a slower hard drive. Our 3-tier hierarchy is:

```
  Fast (HBM)          Warm (CXL)              Cold (NVMe)
  Full precision  -->  Compressed (3-bit)  -->  Evicted
  ~4K tokens          ~21K tokens              overflow
```

**CXL** (Compute Express Link) is a new hardware standard that lets servers
attach additional DRAM via a PCIe-like bus. It is slower than HBM but much
faster than NVMe, making it perfect for a warm compression tier.

The combined system delivers an **8.8x effective capacity increase** — meaning
a GPU that previously handled 4K tokens can now serve 35K+ tokens without
losing important context.

### Why Four Implementations?

The same algorithm runs at four different levels of the system stack because
each level manages different data in different hardware:

| Layer | What It Does | Analogy |
|-------|-------------|---------|
| **vLLM (Python)** | Tests the algorithm in simulation — no GPU needed | A flight simulator before flying the real plane |
| **DeepSpeed** | Compresses model training data (optimizer states, gradients) | Compressing luggage to fit more in your car trunk |
| **CUDA** | Compresses inference KV cache on the GPU in real time | The actual autopilot running during the flight |
| **Kernel** | Places memory pages in the right physical hardware tier | Air traffic control deciding which runway to use |

They are **not redundant** — each handles different data at a different phase.
You would use the Python simulation to tune parameters, the CUDA layer during
production inference, DeepSpeed during training, and the kernel module to manage
the server's physical memory across all applications.

---

## Architecture Summary (Technical)

CTM+ implements a unified memory tiering algorithm across four execution layers.
Each layer targets a different runtime environment and manages different physical
memory, making them **complementary, not redundant**.

```
┌──────────────────────────────────────────────────────────────────┐
│  Application: LLM Training / Inference                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐ │
│  │   vLLM (Python)  │   │   DeepSpeed      │   │   CUDA       │ │
│  │   Simulation     │   │   Training       │   │   Inference  │ │
│  │                  │   │                  │   │              │ │
│  │  Algorithm       │   │  Optimizer state │   │  KV cache    │ │
│  │  prototyping &   │   │  + gradient      │   │  3-tier      │ │
│  │  benchmarking    │   │  compression     │   │  hierarchy   │ │
│  └─────────────────┘   └──────────────────┘   └──────────────┘ │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐│
│  │   Linux Kernel Module                                        ││
│  │   System-wide DRAM / CXL / NVMe page placement              ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: vLLM (Python Simulation)

**Path:** `CTM_plus/vLLM/ctm_plus_vllm/`

**Purpose:** Algorithm design, numerical validation, and benchmark metric collection.
No real GPU hardware required — pure NumPy simulation.

### What It Implements

| Component | File | Description |
|-----------|------|-------------|
| TurboQuant compression | `turboquant.py` | Full PolarQuant + QJL pipeline in NumPy. Measures MSE, cosine similarity, SNR, compression ratios. |
| CTM+ eviction | `kv_cache_simulator.py` | 4 eviction policies (LRU, FIFO, CTM+, Random). CTM+ uses 6-signal scoring. |
| Integrated simulator | `turboquant_integration.py` | Combined TQ + CTM+ with two modes: CAPACITY_ONLY and QUALITY_AWARE. |
| Long-context workloads | `long_context_workloads.py` | 5 workload types (sleeping tokens, needle-in-haystack, multi-doc QA, streaming conversation, code generation) at 4K–131K context lengths. |

### Key Classes

- **`TurboQuantConfig`** — Bit-width (2/3/4), QJL enable, head_dim, compression ratio calculation
- **`PolarQuant`** — Random rotation → recursive polar transform → fixed-grid quantization
- **`QJL`** — Johnson-Lindenstrauss 1-bit sign projection for residual correction
- **`TurboQuantCompressor`** — Combined PolarQuant + QJL pipeline
- **`TurboQuantCTMSimulator`** — Integrated cache simulator with quality-aware eviction
- **`MemoryBudget`** — Models effective capacity expansion

### Data Managed

- Simulated KV cache vectors (NumPy float32)
- Simulated token metadata (access counts, attention weights, compression quality)
- Benchmark metrics (hit rates, retention rates, compression quality)

### When to Use

- **Tuning** compression parameters (angle_bits, QJL projection dim)
- **Comparing** eviction policies before deploying
- **Validating** that quality-aware scoring improves retention
- **Benchmarking** long-context workloads (sleeping tokens, needle-in-haystack)

---

## Layer 2: DeepSpeed (Training-Time Offload)

**Path:** `CTM_plus/DeepSpeed/ctm_plus_deepspeed/`

**Purpose:** Compress optimizer states and gradients during DeepSpeed ZeRO offload
to reduce GPU↔CPU data transfer and host memory footprint during training.

### What It Implements

| Component | File | Description |
|-----------|------|-------------|
| CUDA kernels | `turboquant_cuda.cu` | Fused rotate+compress and decompress kernels. One thread per vector. Shared memory for rotation matrix. |
| CUDA Python bindings | `turboquant_cuda_ext.py` | `TurboQuantCUDA` class — PyTorch C++ extension wrapper. Handles kernel launch, shared memory config. |
| Numba fallback | `turboquant_numba.py` | JIT-compiled CPU kernels for platforms without CUDA. Identical algorithm, ~100x slower. |
| Tensor offload manager | `turboquant_offload.py` | `TurboQuantOffloadManager` — integrates compression into DeepSpeed's GPU↔CPU tensor movement pipeline. Bit-packing, prefetching, access pattern tracking. |
| Configuration | `config.py` | `CTMDeepSpeedConfig` with ZeRO-specific presets (training, inference, large model). |

### Key Classes

- **`TurboQuantCUDA`** — GPU compress/decompress via PyTorch CUDA extension
  - `compress(vectors) → (radii, indices)` — batch compress on GPU
  - `decompress(radii, indices) → vectors` — batch decompress on GPU
- **`TurboQuantOffloadManager`** — End-to-end tensor offload with compression
  - Segments tensors into 128-dim chunks before compression
  - Bit-packs compressed indices for minimal transfer
  - Prefetches based on access patterns
- **`TurboQuantTrainingConfig`** — Training-specific settings
  - `compress_gradients`, `compress_optimizer_states`
  - `min_compress_elements` (skip tiny tensors)

### Data Managed

- **Optimizer states** (Adam moments, FP32 master weights) — compressed on CPU offload
- **Gradient tensors** — compressed during allreduce communication
- **Activation checkpoints** — compressed for gradient recomputation

### Memory Tiers (DeepSpeed)

```
GPU HBM (FP16 working set)
    ↕  TurboQuant compress/decompress
CPU DRAM (TQ-3bit compressed optimizer states + gradients)
    ↕  Disk offload (optional)
NVMe (overflow)
```

### When to Use

- **Large model training** where optimizer states exceed GPU memory
- **ZeRO-Offload** and **ZeRO-Infinity** configurations
- **Multi-node training** to reduce allreduce communication volume

---

## Layer 3: CUDA (Inference-Time KV Cache)

**Path:** `CTM_plus/CUDA/ctm_plus/`

**Purpose:** Native GPU implementation of the 3-tier KV cache hierarchy for
production LLM inference serving. No Python/PyTorch dependency — standalone
C++/CUDA library linkable by vLLM, TensorRT-LLM, or custom serving frameworks.

### What It Implements

| Component | File | Description |
|-----------|------|-------------|
| CTM+ base controller | `ctm_plus.cu` / `.cuh` | GPU-parallel page state tracking, victim selection, tier management. Hash-table lookup with linear probing. |
| TurboQuant kernels | `turboquant.cu` / `.cuh` | Fused rotate+compress, decompress+inverse-rotate, QJL sign-bit compression, quality metrics. `TurboQuantEngine` host API. |
| Integrated 3-tier controller | `turboquant_ctxl_integration.cu` / `.cuh` | `IntegratedController` managing HBM→CXL→NVMe hierarchy with quality-aware CTM+ eviction. |
| Benchmark | `turboquant_benchmark.cu` | Kernel throughput + 6-config comparison matching vLLM benchmark matrix. |

### Key Classes

- **`TurboQuantEngine`** — GPU compression engine
  - `compress_batch()` / `decompress_batch()` — fused kernels
  - `compress_qjl_batch()` — QJL residual sign bits
  - `compute_quality_batch()` — MSE, cosine similarity
- **`IntegratedController`** — 3-tier KV cache manager
  - `access_batch()` — process token accesses through 3-tier hierarchy
  - `compress_to_cxl()` — compress and store in CXL tier
  - `decompress_from_cxl()` — decompress for attention computation
- **`IntegratedConfig`** — combined TQ + CTM+ + CXL configuration
  - Presets: `integrated_config_3bit_chatbot()`, `integrated_config_3bit_long_context()`, `integrated_config_4bit_long_context()`

### Memory Tiers (CUDA)

```
Tier 0: HBM (FP16)         — Hot tokens, full precision, fast attention
    ↕  TurboQuant compress (demote) / decompress (promote)
CXL:   DRAM (TQ-3bit)      — Warm tokens, ~5.3x compressed, CXL-attached memory
    ↕  Eviction
Tier 1: NVMe               — Cold tokens, last resort
```

### Quality-Aware Eviction (6+1 signals)

| Signal | Weight | Description |
|--------|--------|-------------|
| Recency | 0.10–0.30 | exp(-0.693 * age / 100) |
| Frequency | 0.25 | log1p(freq * 10) / log1p(10) |
| Attention strength | 0.25–0.35 | sigmoid(avg_attn / baseline - 5) |
| Token importance | 0.15–0.20 | Token type lookup (BOS=1.0, entity=0.9, regular=0.4) |
| Position | 0.10 | Attention sinks + recent window bonus |
| Sequence priority | 0.05 | Multi-sequence batch priority |
| **Compression quality** | **0.05** | **(1 - cosine_similarity) — protects poorly-compressed tokens** |

### When to Use

- **Production LLM inference** serving (vLLM, TensorRT-LLM backends)
- **Long-context inference** (32K–128K tokens) where KV cache exceeds HBM
- **CXL-equipped servers** with tiered memory (HBM + CXL-attached DRAM)

---

## Layer 4: Linux Kernel Module (System Memory Tiering)

**Path:** `CTM_plus/Kernel/ctm_plus/`

**Purpose:** System-wide memory page placement between physical memory tiers,
operating transparently for all applications via the Linux kernel's memory
management subsystem.

### What It Implements (Current)

| Component | File | Description |
|-----------|------|-------------|
| Core algorithm | `ctm_plus_core.c` | RB-tree page lookup, ARC dual shadow tiers, smart victim selection, neighbor/transition tracking. Fixed-point math (×100 scale). |
| Kernel module | `ctm_plus_module.c` | Module init/exit, sysfs interface, DAMON/NUMA integration hooks. |
| Header | `ctm_plus.h` | Data structures, configuration, API declarations. |

### Key Structures

- **`ctm_page_state`** — Per-page tracking: PFN, flags, access count, phase/amplitude/coherence/reuse (all fixed-point)
- **`ctm_shadow_entry`** — Ghost cache for ARC adaptive-p regret tracking
- **`ctm_neighbor_tracker`** — Co-occurrence tracking via circular buffer
- **`ctm_transition_tracker`** — Markov chain successor detection
- **`ctm_controller`** — Main state: RB-tree, LRU lists, shadow tiers, spinlock

### Memory Tiers (Current — 2 tiers)

```
Tier 0: Fast DRAM / HBM    — Hot pages
    ↕  Promotion / demotion
Tier 1: Slow DRAM / NVMe   — Cold pages
```

### Planned Upgrade: CXL Tier + Compression-Quality Hints

```
Tier 0: Fast DRAM / HBM           — Hot pages, full access speed
    ↕  Demotion with quality hint
CXL:   CXL-attached DRAM          — Warm pages, slightly higher latency
    ↕  Demotion
Tier 1: NVMe                      — Cold pages
```

The kernel module cannot run TurboQuant (no floating-point in kernel space),
but it can receive **compression-quality hints** from the CUDA layer via sysfs
to make better page placement decisions. Pages containing poorly-compressed
GPU data are prioritized for faster memory tiers.

### When to Use

- **System-wide memory tiering** on CXL-equipped servers
- **Hypervisor / VM host** scenarios managing memory across guests
- **Database workloads** with tiered storage (complement to GPU inference)
- **DAMON integration** for hardware-accelerated access pattern tracking

---

## Cross-Layer Interaction

```
                    ┌─────────────────────┐
                    │  GPU (CUDA Layer)    │
                    │                     │
                    │  KV cache vectors   │
                    │  HBM → CXL → NVMe  │
                    │  TQ compress/decomp │
                    └────────┬────────────┘
                             │
                    quality hints via sysfs
                    (cosine_sim, compression_bits)
                             │
                    ┌────────▼────────────┐
                    │  Kernel Module      │
                    │                     │
                    │  Physical pages     │
                    │  DRAM → CXL → NVMe │
                    │  Quality-aware      │
                    │  page placement     │
                    └─────────────────────┘
```

The CUDA layer knows which pages contain well-compressed vs poorly-compressed
KV data. It can write quality hints to `/sys/kernel/ctm_plus/compression_hint`
so the kernel module prioritizes keeping pages with poorly-compressed data in
faster physical memory (since those pages are more sensitive to access latency).

---

## Summary: What Each Layer Manages

| Layer | Data | Compression | Tiers | Quality-Aware |
|-------|------|-------------|-------|---------------|
| **vLLM** | Simulated KV vectors | Simulated (NumPy) | Simulated 3-tier | Yes (algorithm design) |
| **DeepSpeed** | Optimizer states, gradients | Real (CUDA/Numba) | GPU ↔ CPU ↔ NVMe | No |
| **CUDA** | KV cache vectors | Real (fused CUDA kernels) | HBM → CXL → NVMe | Yes (full integration) |
| **Kernel** | Physical memory pages | N/A (hint-based) | DRAM → CXL → NVMe | Planned (page-level hints) |
