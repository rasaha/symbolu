# COHERA SDK Specification

## Software Stack for PA-VPU / Universal Coherence Processor

**Version:** 1.0
**Date:** 2024-12-30
**Classification:** Patent-Adjacent Technical Specification

---

## 1. Overview

COHERA (COherence-centric HEterogeneous Runtime Architecture) is the software stack for the PA-VPU/UCP chip, analogous to CUDA for NVIDIA GPUs. It provides the ISA, driver, runtime, and framework integrations needed to program phase-coherent cognitive processors.

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│   PyTorch/JAX Extensions  │  Native COHERA Apps                 │
├─────────────────────────────────────────────────────────────────┤
│                    FRAMEWORK LAYER                               │
│   cohera.nn  │  cohera.vision  │  cohera.robotics               │
├─────────────────────────────────────────────────────────────────┤
│                    RUNTIME LAYER                                 │
│   COHERA Runtime (libcohera.so)                                 │
│   Memory Manager │ Stream Manager │ Coherence Monitor           │
├─────────────────────────────────────────────────────────────────┤
│                    DRIVER LAYER                                  │
│   COHERA Driver (cohera.ko / cohera.sys)                        │
│   PCIe/CXL │ DMA │ Interrupts │ Power Management                │
├─────────────────────────────────────────────────────────────────┤
│                    HARDWARE                                      │
│   PA-VPU / UCP Silicon                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Instruction Set Architecture (ISA)

### 2.1 Instruction Categories

| Category | Prefix | Description |
|----------|--------|-------------|
| Phase Operations | `PH_` | Phase computation and synchronization |
| Coherence Operations | `CO_` | Coherence measurement and gating |
| Ontology Operations | `ON_` | 12-layer ontological processing |
| Memory Operations | `MEM_` | HBM3 and TCU memory access |
| Control Operations | `CTL_` | Flow control and synchronization |

### 2.2 Core Instructions

#### Phase Operations
```
PH_INIT     dst, src, dim        ; Initialize phase from embedding
PH_SYNC     dst, src, lr, steps  ; Run phase synchronization (Kuramoto)
PH_MEAN     dst, src, n          ; Compute mean phase (circular mean)
PH_GRAD     dst, phase, mean     ; Compute phase gradient: -sin(φ - φ_mean)
PH_UPDATE   dst, src, grad, lr   ; Update phase: φ += lr * grad
PH_LOCK     dst, src, thresh     ; Lock phases above coherence threshold
PH_MOD      dst, src, freq       ; Modulate by layer frequency
```

#### Coherence Operations
```
CO_MEASURE  dst, phases          ; Measure coherence: |Σexp(iφ)|/N
CO_GATE     dst, src, thresh     ; Output if coherence > threshold, else zero
CO_ENTROPY  dst, phases          ; Compute phase entropy
CO_VERIFY   dst, fwd, bwd        ; Bidirectional coherence verification (BCVF)
```

#### Ontology Operations
```
ON_PROJECT  dst, hidden, layer   ; Project to ontological layer (0-11)
ON_ACTIVATE dst, src, kosha      ; Apply Kosha activation function
ON_VRITTI   dst, states          ; Detect Vritti state (5 modes)
ON_BLEND    dst, layers[], wts[] ; Weighted blend of layer outputs
```

#### Memory Operations
```
MEM_LOAD    dst, addr, size      ; Load from HBM3
MEM_STORE   addr, src, size      ; Store to HBM3
MEM_TCU_RD  dst, head, dim       ; Read from TCU accumulator
MEM_TCU_WR  head, dim, src       ; Write to TCU accumulator
MEM_TCU_ACC head, dim, src       ; Accumulate to TCU (running mean)
```

#### Control Operations
```
CTL_SYNC_LAYER layer_mask        ; Synchronize across ontology layers
CTL_BARRIER                      ; Thread barrier within kernel
CTL_STREAM_WAIT stream_id        ; Wait for stream completion
CTL_FRAME_DONE                   ; Signal frame processing complete
```

### 2.3 Instruction Encoding (32-bit)

```
┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
│ 31..28 │ 27..24 │ 23..20 │ 19..16 │ 15..12 │ 11..8  │  7..4  │  3..0  │
├────────┼────────┼────────┼────────┼────────┼────────┼────────┼────────┤
│ OPCODE │  DST   │  SRC1  │  SRC2  │  IMM8  │ LAYER  │ FLAGS  │ RSVD   │
└────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┘

OPCODE (4 bits):
  0x0: PH_*   (Phase operations)
  0x1: CO_*   (Coherence operations)
  0x2: ON_*   (Ontology operations)
  0x3: MEM_*  (Memory operations)
  0x4: CTL_*  (Control operations)
  0x5-0xF: Reserved

FLAGS (4 bits):
  [0]: FP16/FP32 select
  [1]: Accumulate mode
  [2]: Async operation
  [3]: Reserved
```

---

## 3. Driver Interface

### 3.1 Device Discovery

```c
// PCIe Vendor/Device IDs
#define COHERA_VENDOR_ID    0x1C0D  // Assigned
#define COHERA_DEVICE_ID    0x0001  // PA-VPU
#define COHERA_DEVICE_UCP   0x0002  // Full UCP

// Device capabilities structure
typedef struct {
    uint32_t num_pau;           // Phase Attention Units
    uint32_t num_tcu;           // Temporal Context Units
    uint32_t hbm_size_gb;       // HBM3 capacity
    uint32_t max_seq_len;       // Maximum sequence length
    uint32_t ontology_layers;   // Always 12
    uint32_t phase_precision_ps;// Phase precision in picoseconds
    uint32_t firmware_version;
} cohera_caps_t;
```

### 3.2 Register Access (via PCIe BAR0)

```c
// BAR0 Memory Map
#define COHERA_BAR0_SIZE        0x10000  // 64KB register space

#define REG_GCR_BASE            0x0000   // Global Control
#define REG_PEU_BASE            0x0100   // Patch Embedder
#define REG_PAU_BASE            0x0200   // Phase Attention
#define REG_TCU_BASE            0x0300   // Temporal Context
#define REG_OPU_BASE            0x0400   // Ontology Projector
#define REG_SDU_BASE            0x0500   // State Delta
#define REG_KEE_BASE            0x0600   // Kosha Entropy Engine
#define REG_OLB_BASE            0x1000   // Ontology Layer Blocks (×12)

// Register access functions
uint32_t cohera_reg_read(cohera_dev_t* dev, uint32_t offset);
void cohera_reg_write(cohera_dev_t* dev, uint32_t offset, uint32_t value);
```

### 3.3 DMA Interface

```c
// DMA descriptor for HBM3 transfers
typedef struct {
    uint64_t host_addr;         // Host physical address
    uint64_t device_addr;       // HBM3 address
    uint32_t size;              // Transfer size in bytes
    uint32_t flags;             // DMA_TO_DEVICE, DMA_FROM_DEVICE
} cohera_dma_desc_t;

// DMA operations
int cohera_dma_submit(cohera_dev_t* dev, cohera_dma_desc_t* desc, int count);
int cohera_dma_wait(cohera_dev_t* dev, int timeout_ms);
```

### 3.4 Interrupt Handling

```c
// Interrupt status bits (GCR_IRQ_STAT @ 0x000C)
#define IRQ_FRAME_DONE      (1 << 0)   // Frame processing complete
#define IRQ_COHERENCE_LOW   (1 << 1)   // Coherence dropped below threshold
#define IRQ_TCU_OVERFLOW    (1 << 2)   // TCU accumulator overflow
#define IRQ_DMA_COMPLETE    (1 << 3)   // DMA transfer complete
#define IRQ_ERROR           (1 << 4)   // Error condition

// Interrupt handler registration
typedef void (*cohera_irq_handler_t)(cohera_dev_t* dev, uint32_t status, void* ctx);
int cohera_register_irq(cohera_dev_t* dev, cohera_irq_handler_t handler, void* ctx);
```

---

## 4. Runtime API (libcohera)

### 4.1 Device Management

```c
#include <cohera.h>

// Initialize runtime
cohera_error_t cohera_init(void);
cohera_error_t cohera_shutdown(void);

// Device enumeration
int cohera_get_device_count(void);
cohera_error_t cohera_get_device(int index, cohera_device_t* device);
cohera_error_t cohera_set_device(int index);

// Device properties
cohera_error_t cohera_get_caps(cohera_device_t device, cohera_caps_t* caps);
```

### 4.2 Memory Management

```c
// HBM3 allocation
cohera_error_t cohera_malloc(void** ptr, size_t size);
cohera_error_t cohera_free(void* ptr);

// Host-device transfers
cohera_error_t cohera_memcpy_h2d(void* dst, const void* src, size_t size);
cohera_error_t cohera_memcpy_d2h(void* dst, const void* src, size_t size);
cohera_error_t cohera_memcpy_async(void* dst, const void* src, size_t size,
                                    cohera_stream_t stream);

// Phase-aware tensor allocation
typedef struct {
    void* data;                 // HBM3 pointer
    int64_t shape[4];           // [batch, seq, heads, dim]
    cohera_dtype_t dtype;       // FP16, BF16, FP32
    int ontology_layer;         // Associated layer (0-11, -1 for none)
} cohera_tensor_t;

cohera_error_t cohera_tensor_create(cohera_tensor_t* tensor, int64_t* shape,
                                     cohera_dtype_t dtype, int ontology_layer);
cohera_error_t cohera_tensor_destroy(cohera_tensor_t* tensor);
```

### 4.3 Stream Management (Ontology-Aware)

```c
// Streams are associated with ontology layers for priority scheduling
typedef struct {
    int stream_id;
    int ontology_layer;         // 0-11, or -1 for default
    int priority;               // Derived from layer (O1=highest)
} cohera_stream_t;

cohera_error_t cohera_stream_create(cohera_stream_t* stream, int ontology_layer);
cohera_error_t cohera_stream_destroy(cohera_stream_t stream);
cohera_error_t cohera_stream_synchronize(cohera_stream_t stream);
cohera_error_t cohera_stream_wait_event(cohera_stream_t stream, cohera_event_t event);
```

### 4.4 Kernel Launch API

The attention config is versioned append-only: v1 fields (`seq_len` through
`coherence_threshold`) are stable and must not be reordered. v2 fields were
added to support Mistral-style decoders (GQA, RoPE, sliding window, BF16).
Zero-initialized v1 callers continue to work unchanged — `num_kv_heads=0`
selects MHA, `window_size<=0` selects full attention, and `rope_*` NULL/0
disables RoPE.

```c
// Phase attention kernel configuration
typedef struct {
    // --- v1: stable ---
    int seq_len;
    int embed_dim;
    int num_heads;
    int sync_steps;             // Phase sync iterations (default: 3)
    float sync_lr;              // Phase learning rate (default: 0.1)
    float temperature;          // Attention temperature
    int causal;                 // Causal masking (0 / 1)
    int use_tcu;                // Enable temporal context (0 / 1)
    int ontology_layer;         // Bound layer (0-11, -1 = all)
    float coherence_threshold;  // Gating threshold

    // --- v2: append-only ---
    int num_kv_heads;                  // GQA: 0 -> MHA, else <= num_heads
    cohera_dtype_t dtype;              // FP16 / BF16 / FP32
    int window_size;                   // Sliding window (<= 0 = full)
    const cohera_tensor_t* rope_freqs; // Device tensor [rope_dim/2] FP32, NULL = off
    int rope_dim;                      // 0 = RoPE disabled
    int rope_base_position;            // KV-cache continuation offset
} cohera_attention_config_t;

// Launch phase attention
cohera_error_t cohera_phase_attention(
    cohera_tensor_t* output,
    const cohera_tensor_t* query,
    const cohera_tensor_t* key,
    const cohera_tensor_t* value,
    const cohera_attention_config_t* config,
    cohera_stream_t stream
);

// Fused decoder path: RoPE (if configured) -> GQA broadcast (if
// num_kv_heads < num_heads) -> phase attention -> TCU, all on `stream`.
cohera_error_t cohera_phase_attention_fused(
    cohera_tensor_t* output,
    const cohera_tensor_t* query,      // [batch, seq, num_heads,    head_dim]
    const cohera_tensor_t* key,        // [batch, seq, num_kv_heads, head_dim]
    const cohera_tensor_t* value,      // [batch, seq, num_kv_heads, head_dim]
    const cohera_attention_config_t* config,
    cohera_stream_t stream
);

// Apply Rotary Position Embedding (RoPE) on Q or K.
cohera_error_t cohera_apply_rope(
    cohera_tensor_t* output,
    const cohera_tensor_t* input,      // [batch, seq, heads, head_dim]
    const cohera_tensor_t* rope_freqs, // [rope_dim / 2] FP32
    int rope_dim,
    int position_offset,
    cohera_stream_t stream
);

// Broadcast KV heads from num_kv_heads to num_heads (GQA expansion).
cohera_error_t cohera_gqa_broadcast(
    cohera_tensor_t* kv_expanded,
    const cohera_tensor_t* kv,
    int num_heads,
    cohera_stream_t stream
);

// Build a causal + sliding-window mask on device.
// window_size <= 0 or >= seq_len -> full causal only.
cohera_error_t cohera_build_sliding_window_mask(
    cohera_tensor_t* mask,             // [seq_len, seq_len] FP32
    int seq_len,
    int window_size,
    cohera_stream_t stream
);

// Launch 124-D ontology projection
cohera_error_t cohera_ontology_project(
    cohera_cognitive_state_t* cognitive_state,   // Output: 124-D
    const cohera_tensor_t* hidden,               // Input: [batch, seq, hidden]
    cohera_stream_t stream
);

// Launch 32-D Sovereign-State projection (mistral_cg)
//   Bhava(12) + Kosha(5) + Vritti(5) + Guna(6) + Reserved(4) = 32
cohera_error_t cohera_ontology_project_sovereign(
    cohera_sovereign_state_t* output,
    const cohera_tensor_t* hidden,
    cohera_kosha_mode_t kosha_mode,
    cohera_stream_t stream
);

// Get state delta
cohera_error_t cohera_state_delta(
    cohera_cognitive_state_t* delta,
    const cohera_cognitive_state_t* prev_state,
    const cohera_cognitive_state_t* curr_state,
    cohera_stream_t stream
);
```

#### Kernel shared-memory contract

`phase_attention_head` allocates its `phases[]` buffer from dynamic shared
memory; the caller must pass `shared_mem_size = (seq_len + 2) * sizeof(float)`
to `cohera_kernel_launch` (two trailing floats for the global sin/cos
reductions on the non-masked fast path). When `causal` or `window_size > 0`
the kernel takes a per-position masked reduction instead, so causality is
preserved during Kuramoto sync, coherence measurement, and aggregation.

### 4.5 Coherence Monitoring

```c
// Real-time coherence metrics
typedef struct {
    float coherence;            // [0, 1] phase alignment
    float entropy;              // [0, 1] uncertainty
    float confidence;           // [0, 1] belief strength
    float momentum;             // Rate of meaning change
    int dominant_layer;         // Most active ontology layer (0-11)
    int vritti_state;           // 0=pramana, 1=viparyaya, 2=vikalpa, 3=smrti, 4=nidra
} cohera_metrics_t;

cohera_error_t cohera_get_metrics(cohera_metrics_t* metrics);

// Coherence callbacks
typedef void (*cohera_coherence_callback_t)(float coherence, void* ctx);
cohera_error_t cohera_register_coherence_callback(
    cohera_coherence_callback_t callback,
    float threshold,            // Trigger when below this
    void* ctx
);
```

### 4.6 Temporal Context Unit (TCU)

The TCU ships two accumulation modes. Pick one per model binding; a
mode switch resets the per-sequence slots so the next accumulate starts
clean.

```c
typedef enum {
    COHERA_TCU_MODE_FRAME_EMA = 0,  // Global EMA per head (default).
                                    // Used by streaming / vision paths
                                    // where each frame is independent.
    COHERA_TCU_MODE_KV_CACHE  = 1,  // Per-sequence per-head phase
                                    // history, indexed by stream.
                                    // Required for mistral_cg
                                    // autoregressive decoding so a
                                    // prefill's accumulated phase is
                                    // reused when continuing the same
                                    // sequence.
} cohera_tcu_mode_t;

// Select the TCU accumulation mode. Must be called before the first
// accumulate of a new sequence; resets per-sequence state on transition.
cohera_error_t cohera_tcu_set_mode(cohera_tcu_mode_t mode);
cohera_error_t cohera_tcu_get_mode(cohera_tcu_mode_t* mode);

// Reset all TCU accumulators (frame EMA + KV-cache slots).
cohera_error_t cohera_tcu_reset(void);

// Reset only the per-sequence slot for a stream (KV_CACHE mode only;
// no-op under FRAME_EMA).
cohera_error_t cohera_tcu_reset_sequence(cohera_stream_t stream);

// Frame counter (monotonic; not reset by mode change).
cohera_error_t cohera_tcu_get_frame_count(uint64_t* count);

// EMA decay factor (FRAME_EMA mode only).
cohera_error_t cohera_tcu_set_decay(float decay);

// Read phase context.
//   FRAME_EMA: returns the rolling context for `head`; stream is ignored.
//   KV_CACHE : pass the stream that identifies the sequence; context is
//              the history slice for (stream, head).
cohera_error_t cohera_tcu_read_context(cohera_tensor_t* context,
                                       int head,
                                       cohera_stream_t stream);
```

**Usage pattern (mistral_cg decode):**

```c
cohera_stream_t s;
cohera_stream_create(&s, /*ontology_layer=*/-1);
cohera_tcu_set_mode(COHERA_TCU_MODE_KV_CACHE);

// Prefill: accumulate phase into the stream's slot.
cohera_phase_attention_fused(out, q, k, v, &cfg, s);

// Decode step N: config.rope_base_position = N, same stream.
cfg.rope_base_position = token_index;
cohera_phase_attention_fused(out, q, k, v, &cfg, s);

// End of sequence: release only this sequence's slot.
cohera_tcu_reset_sequence(s);
```

---

## 5. COHERA Kernel Language (CKL)

### 5.1 Kernel Definition

```cpp
// CKL extends C++ with phase-aware intrinsics
#include <cohera_kernel.h>

__phase_kernel__ void ontological_attention(
    PhaseToken* tokens,         // Input tokens with phase
    OntologyLayer layer,        // Target ontology layer
    CoherenceThreshold thresh,  // Gating threshold
    CognitiveState* output      // Output state
) {
    // Thread indexing (similar to CUDA)
    int tid = __thread_idx();
    int bid = __block_idx();
    int gid = bid * __block_dim() + tid;

    // Phase intrinsics
    float phase = __phase_compute(tokens[gid], layer.frequency);
    float mean_phase = __phase_mean_shared(phase);  // Shared memory reduction

    // Coherence measurement
    float coherence = __coherence_measure(phase, mean_phase);

    // Gated output based on coherence
    if (__coherence_gate(coherence, thresh)) {
        __phase_lock(tokens[gid], layer);

        // Cross-layer synchronization
        __sync_ontology(layer.id);

        // Project to cognitive state
        output[gid] = __ontology_project(tokens[gid], layer);
    }
}
```

### 5.2 Built-in Intrinsics

```cpp
// Phase intrinsics
float __phase_compute(PhaseToken token, float frequency);
float __phase_mean_shared(float phase);  // Block-level reduction
float __phase_mean_global(float phase);  // Device-level reduction
void  __phase_lock(PhaseToken& token, OntologyLayer layer);
void  __phase_update(float& phase, float gradient, float lr);

// Coherence intrinsics
float __coherence_measure(float phase, float target_phase);
bool  __coherence_gate(float coherence, float threshold);
float __coherence_entropy(float* phases, int n);

// Ontology intrinsics
CognitiveState __ontology_project(PhaseToken token, OntologyLayer layer);
void __sync_ontology(int layer_id);      // Cross-layer barrier
int  __get_ontology_layer();             // Current layer ID (0-11)
float __get_layer_frequency();           // Layer's operating frequency

// TCU intrinsics
void __tcu_accumulate(int head, float* phase_context);
void __tcu_read(int head, float* phase_context);
void __tcu_reset();

// Memory intrinsics
void __hbm_load_async(void* dst, const void* src, size_t size);
void __hbm_store_async(void* dst, const void* src, size_t size);
void __memory_fence();
```

### 5.3 Compiler Toolchain

```bash
# Compile CKL to PA-VPU binary
coherac -arch pavpu10 -o kernel.cbin kernel.ckl

# Options:
#   -arch pavpu10     Target PA-VPU v1.0
#   -arch ucp20       Target UCP v2.0
#   -O3               Maximum optimization
#   -g                Debug symbols
#   -fphase-fusion    Fuse consecutive phase ops
#   -ftcu-reuse       Optimize TCU access patterns
#   --ptx             Emit intermediate representation

# Link multiple kernels
coheralink -o model.cexe kernel1.cbin kernel2.cbin
```

---

## 6. PyTorch Integration

### 6.1 Installation

```bash
pip install torch-cohera
```

### 6.2 Device Selection

```python
import torch
import torch_cohera

# Check availability
if torch_cohera.is_available():
    print(f"COHERA devices: {torch_cohera.device_count()}")

# Move tensors to COHERA device
device = torch.device('cohera:0')
x = torch.randn(32, 1024, 768).to(device)
```

### 6.3 Phase Attention Layer

```python
import torch.nn as nn
from torch_cohera import nn as cnn

class PhaseAttentionBlock(nn.Module):
    def __init__(self, dim=768, heads=12, ontology_layer=5):
        super().__init__()
        self.attn = cnn.PhaseAttention(
            dim=dim,
            heads=heads,
            sync_steps=3,
            sync_lr=0.1,
            ontology_layer=ontology_layer,  # Bind to specific layer
            use_tcu=True                     # Enable temporal context
        )
        self.norm = nn.LayerNorm(dim)

    def forward(self, x):
        # Returns (output, coherence_score)
        out, coherence = self.attn(self.norm(x))
        return x + out, coherence

# Full 12-layer ontological transformer
class OntologicalTransformer(nn.Module):
    def __init__(self, dim=768, heads=12):
        super().__init__()
        # Each block bound to its ontology layer
        self.layers = nn.ModuleList([
            PhaseAttentionBlock(dim, heads, ontology_layer=i)
            for i in range(12)
        ])
        self.projector = cnn.OntologyProjector(dim, 124)

    def forward(self, x):
        coherences = []
        for layer in self.layers:
            x, coh = layer(x)
            coherences.append(coh)

        # Project to 124-dim cognitive state
        cognitive_state = self.projector(x)
        return cognitive_state, coherences
```

### 6.4 Video Processing Example

```python
import torch_cohera as cohera
from torch_cohera.vision import VideoProcessor

# Initialize for 4K video
processor = VideoProcessor(
    resolution=(3840, 2160),
    fps=60,
    patch_size=16,
    device='cohera:0'
)

# Process video stream with unlimited temporal context
for frame in video_stream:
    # Returns cognitive state and metrics
    state, metrics = processor(frame)

    print(f"Coherence: {metrics.coherence:.3f}")
    print(f"Dominant layer: O{metrics.dominant_layer + 1}")
    print(f"Vritti: {metrics.vritti_name}")

    # State delta for temporal reasoning
    if processor.has_previous:
        delta = processor.get_delta()
        if delta.entropy_change > 0.2:
            print("Scene change detected")
```

### 6.5 Custom Kernel Integration

```python
from torch_cohera import load_kernel

# Load custom CKL kernel
custom_kernel = load_kernel('my_kernel.cbin')

# Call from PyTorch
output = custom_kernel(
    input_tensor,
    ontology_layer=7,
    coherence_threshold=0.8
)
```

---

## 7. Development Roadmap

| Phase | Deliverable | Timeline |
|-------|-------------|----------|
| **Phase 1** | Driver + Basic Runtime | 3-4 months |
| **Phase 2** | CKL Compiler (LLVM-based) | 6-8 months |
| **Phase 3** | PyTorch Backend | 3-4 months |
| **Phase 4** | Optimization + Profiler | 3-4 months |

**Recommended Starting Point:** PyTorch custom backend (Phase 3 before Phase 2) to enable early adoption while compiler matures.

---

## 8. Comparison: COHERA vs CUDA

| Aspect | CUDA | COHERA |
|--------|------|--------|
| Core primitive | Matrix multiply | Phase synchronization |
| Memory model | Global/shared/local | HBM3 + TCU accumulator |
| Synchronization | Thread barriers | Cross-layer phase lock |
| Scheduling | SIMT warps | Ontology layer priority |
| Temporal context | Manual KV cache | Automatic TCU (O(1)) |
| Output | Tensor | Cognitive State [124] |
| Interpretability | Opaque | Semantic dimensions |

---

## Contact

**Repository:** github.com/rasaha/symbolu
**Related Specs:** PA-VPU Hardware Spec, UCP Spec v2.0

---

*Document Version: 1.0*
*Status: Initial Specification*
*Classification: Patent-Adjacent*
