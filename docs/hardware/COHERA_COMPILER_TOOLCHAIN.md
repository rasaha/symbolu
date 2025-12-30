# COHERA Compiler Toolchain Specification

## LLVM-based Compiler for CKL → PA-VPU Binary

**Version:** 1.0
**Date:** 2024-12-30

---

## 1. Overview

The COHERA Compiler Toolchain (`coherac`) compiles COHERA Kernel Language (CKL) source code to PA-VPU binary. Built on LLVM, it leverages existing infrastructure while adding phase-coherent optimizations.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COHERA COMPILER PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   CKL       │───▶│   COHERA    │───▶│   LLVM      │───▶│  PA-VPU     │  │
│  │   Source    │    │   Frontend  │    │   IR        │    │  Backend    │  │
│  │   (.ckl)    │    │   (Clang)   │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                            │                  │                  │          │
│                            ▼                  ▼                  ▼          │
│                     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│                     │ Semantic    │    │ Phase-Aware │    │  COHERA     │  │
│                     │ Analysis    │    │ Optimizations│   │  Binary     │  │
│                     │             │    │             │    │  (.cbin)    │  │
│                     └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Toolchain Components

### 2.1 Component Overview

| Component | Binary | Description |
|-----------|--------|-------------|
| **coherac** | `coherac` | Main compiler driver |
| **cohera-opt** | `cohera-opt` | LLVM IR optimizer with phase passes |
| **cohera-lld** | `cohera-lld` | Linker for COHERA binaries |
| **cohera-as** | `cohera-as` | Assembler for PA-VPU assembly |
| **cohera-dis** | `cohera-dis` | Disassembler |
| **cohera-objdump** | `cohera-objdump` | Object file inspector |

### 2.2 Compilation Stages

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         COMPILATION STAGES                                 │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Stage 1: FRONTEND (Clang-based)                                         │
│  ════════════════════════════════                                         │
│  • Parse CKL syntax (C++ superset with __phase_kernel__ etc.)            │
│  • Semantic analysis of phase intrinsics                                  │
│  • Type checking (PhaseToken, OntologyLayer, etc.)                       │
│  • Generate LLVM IR with COHERA metadata                                  │
│                                                                           │
│  Stage 2: MIDDLE-END (LLVM Passes)                                        │
│  ══════════════════════════════════                                       │
│  • Standard LLVM optimizations (-O0 to -O3)                              │
│  • Phase-specific optimizations (see Section 4)                          │
│  • Ontology-aware scheduling hints                                        │
│  • TCU access pattern optimization                                        │
│                                                                           │
│  Stage 3: BACKEND (PA-VPU Target)                                         │
│  ═════════════════════════════════                                        │
│  • Instruction selection (LLVM IR → PA-VPU ISA)                          │
│  • Register allocation (general + phase + coherence regs)                │
│  • Instruction scheduling (respecting phase dependencies)                │
│  • Code emission (binary or assembly)                                     │
│                                                                           │
│  Stage 4: LINKING                                                         │
│  ═════════════════                                                        │
│  • Link multiple .cbin files                                             │
│  • Resolve kernel references                                              │
│  • Generate final executable (.cexe)                                      │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CKL Language Extensions

### 3.1 New Keywords

| Keyword | Description |
|---------|-------------|
| `__phase_kernel__` | Declares a kernel function |
| `__shared__` | Shared memory declaration |
| `__constant__` | Constant memory declaration |
| `__restrict__` | Pointer aliasing hint |
| `float16` | 16-bit floating point type |

### 3.2 Built-in Types

```cpp
// Phase-related types
typedef float PhaseValue;         // [0, 2π)
typedef struct { float16 data[]; int layer; } PhaseToken;
typedef struct { int id; float freq; int kosha; } OntologyLayer;
typedef float CoherenceValue;     // [0, 1]

// Cognitive state
typedef struct {
    float16 phoneme[44];
    float16 topic[64];
    float16 ontology[12];
    float16 dynamics[4];
} CognitiveState;
```

### 3.3 Intrinsic Functions

The compiler recognizes these intrinsics and maps them to PA-VPU instructions:

```cpp
// Thread indexing
int __thread_idx();              // → reads from SR
int __block_idx();               // → reads from SR
int __block_dim();               // → reads from SR
int __grid_dim();                // → reads from SR

// Phase intrinsics
float __phase_compute(PhaseToken, float freq);     // → PH_INIT
float __phase_mean_shared(float phase);            // → PH_MEAN + shared reduction
void  __phase_update(float& phase, float grad, float lr); // → PH_UPDATE
void  __phase_lock(PhaseToken&, OntologyLayer);    // → PH_LOCK

// Coherence intrinsics
float __coherence_measure(float phase, float target); // → CO_MEASURE
bool  __coherence_gate(float coh, float thresh);      // → CO_GATE
float __coherence_entropy(float* phases, int n);      // → CO_ENTROPY

// Ontology intrinsics
CognitiveState __ontology_project(PhaseToken, OntologyLayer); // → ON_PROJECT
void __sync_ontology(int layer_mask);                         // → CTL_SYNC_LAYER
int  __get_ontology_layer();                                  // → reads SR_LAYER

// TCU intrinsics
void __tcu_accumulate(int head, float* context);   // → MEM_TCU_ACC
void __tcu_read(int head, float* context);         // → MEM_TCU_RD
void __tcu_write(int head, float* context);        // → MEM_TCU_WR
void __tcu_reset();                                // → writes TCU_CTRL

// Synchronization
void __syncthreads();            // → CTL_BARRIER
void __memory_fence();           // → memory fence instruction
void __frame_done();             // → CTL_FRAME_DONE
```

---

## 4. Phase-Aware Optimizations

### 4.1 Custom LLVM Passes

| Pass Name | Description | Benefit |
|-----------|-------------|---------|
| `PhaseFusion` | Fuse consecutive phase operations | Reduce intermediate storage |
| `CoherenceHoisting` | Hoist coherence checks out of loops | Avoid redundant measurements |
| `TCUReuseAnalysis` | Identify TCU access patterns | Minimize HBM3 traffic |
| `OntologyScheduling` | Schedule ops by layer priority | Respect frequency hierarchy |
| `PhaseVectorization` | Vectorize phase computations | Exploit SIMD parallelism |

### 4.2 PhaseFusion Pass

```
BEFORE:
  %p1 = call float @__phase_compute(%token1, %freq)
  %p2 = call float @__phase_compute(%token2, %freq)
  %mean = call float @__phase_mean(%p1, %p2)

AFTER (fused):
  %mean = call float @__phase_compute_and_mean(%token1, %token2, %freq)
```

### 4.3 CoherenceHoisting Pass

```
BEFORE:
  for (int i = 0; i < N; i++) {
    float coh = __coherence_measure(phases[i], target);  // Redundant in loop
    if (coh > threshold) { ... }
  }

AFTER:
  float coh = __coherence_measure_batch(phases, N, target);  // Single call
  if (coh > threshold) {
    for (int i = 0; i < N; i++) { ... }
  }
```

### 4.4 OntologyScheduling Pass

Operations are scheduled respecting the ontology layer hierarchy:

```
Priority: O1 (10kHz) > O2 (5kHz) > ... > O12 (1Hz)

BEFORE:
  call @layer_7_op()   // 100 Hz
  call @layer_2_op()   // 5000 Hz
  call @layer_11_op()  // 5 Hz

AFTER (reordered by frequency):
  call @layer_2_op()   // 5000 Hz - highest priority
  call @layer_7_op()   // 100 Hz
  call @layer_11_op()  // 5 Hz - lowest priority
```

---

## 5. PA-VPU Backend

### 5.1 Target Triple

```
pavpu-unknown-cohera
```

### 5.2 Register Classes

| Class | Registers | Purpose |
|-------|-----------|---------|
| `GPR` | R0-R15 | General purpose |
| `PhaseReg` | P0-P31 | Phase values |
| `CoherenceReg` | C0-C7 | Coherence values |
| `SpecialReg` | SR_* | Special purpose (read-only) |

### 5.3 Instruction Selection Patterns

```tablegen
// CKL: float p = __phase_compute(token, freq);
// ISA: PH_INIT Pd, Rs, dim
def : Pat<(cohera_phase_compute GPR:$token, GPR:$freq),
          (PH_INIT PhaseReg:$dst, GPR:$token, imm:$dim)>;

// CKL: float c = __coherence_measure(phase, target);
// ISA: CO_MEASURE Cd, Ps_base, count
def : Pat<(cohera_coherence_measure PhaseReg:$phase, PhaseReg:$target),
          (CO_MEASURE CoherenceReg:$dst, PhaseReg:$phase, imm:$count)>;

// CKL: __sync_ontology(mask);
// ISA: CTL_SYNC_LAYER layer_mask
def : Pat<(cohera_sync_ontology imm:$mask),
          (CTL_SYNC_LAYER imm:$mask)>;
```

### 5.4 Calling Convention

```
Arguments:    R1-R7 (first 7 args), then stack
Return:       R1 (scalar), R1-R4 (struct up to 128 bits)
Callee-saved: R8-R11, P16-P31, C4-C7
Caller-saved: R1-R7, P0-P15, C0-C3
Stack pointer: R12
Frame pointer: R13
```

---

## 6. Binary Format (.cbin)

### 6.1 File Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    COHERA BINARY FORMAT                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Offset   Size    Description                                   │
│  ──────   ────    ───────────                                   │
│  0x0000   16      Magic: "COHERA\0\0" + version (8 bytes)       │
│  0x0010   32      Header                                        │
│  0x0030   var     Section table                                 │
│  ...      ...     Sections                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Header

```c
typedef struct {
    uint8_t  magic[8];       // "COHERA\0\0"
    uint8_t  version[8];     // "01.00.00"
    uint32_t flags;
    uint32_t num_sections;
    uint32_t kernel_count;
    uint32_t entry_point;    // Offset to entry kernel
    uint64_t hbm_required;   // HBM memory requirement
    uint32_t target_arch;    // PAVPU10, UCP20, etc.
    uint32_t reserved[3];
} cohera_header_t;
```

### 6.3 Sections

| Section | Type | Description |
|---------|------|-------------|
| `.text` | CODE | Kernel instructions |
| `.rodata` | DATA | Constants, LUTs |
| `.cohera.kernels` | META | Kernel descriptors |
| `.cohera.ontology` | META | Ontology layer config |
| `.cohera.tcu` | META | TCU initialization |
| `.symtab` | META | Symbol table |
| `.strtab` | META | String table |

### 6.4 Kernel Descriptor

```c
typedef struct {
    uint32_t name_offset;      // Offset in .strtab
    uint32_t code_offset;      // Offset in .text
    uint32_t code_size;
    uint32_t num_args;
    uint32_t shared_mem_size;
    uint32_t ontology_layers;  // Bitmask of layers used
    uint16_t max_threads;
    uint16_t register_usage;   // GPR + Phase + Coherence
    uint32_t flags;
} cohera_kernel_desc_t;
```

---

## 7. Driver Usage

### 7.1 Basic Compilation

```bash
# Compile single file
coherac -arch pavpu10 -o kernel.cbin kernel.ckl

# Compile with optimization
coherac -arch pavpu10 -O3 -o kernel.cbin kernel.ckl

# Compile to assembly (for debugging)
coherac -arch pavpu10 -S -o kernel.s kernel.ckl

# Compile to LLVM IR (for inspection)
coherac -arch pavpu10 -emit-llvm -o kernel.ll kernel.ckl
```

### 7.2 Compiler Options

| Option | Description |
|--------|-------------|
| `-arch <target>` | Target architecture: `pavpu10`, `ucp20` |
| `-O0` to `-O3` | Optimization level |
| `-g` | Include debug info |
| `-S` | Output assembly instead of binary |
| `-emit-llvm` | Output LLVM IR |
| `-fphase-fusion` | Enable phase fusion optimization |
| `-ftcu-reuse` | Optimize TCU access patterns |
| `-fno-ontology-scheduling` | Disable ontology-based scheduling |
| `-Werror` | Treat warnings as errors |
| `-v` | Verbose output |

### 7.3 Linking

```bash
# Link multiple kernels
cohera-lld -o model.cexe kernel1.cbin kernel2.cbin kernel3.cbin

# Link with shared libraries
cohera-lld -o app.cexe app.cbin -lcohera_stdlib
```

### 7.4 Inspection Tools

```bash
# Disassemble
cohera-dis kernel.cbin

# Show sections
cohera-objdump -h kernel.cbin

# Show symbols
cohera-objdump -t kernel.cbin

# Show kernel info
cohera-objdump --kernels kernel.cbin
```

---

## 8. Runtime Integration

### 8.1 Loading Kernels

```c
#include <cohera.h>

// Load compiled kernel
cohera_kernel_t kernel;
cohera_error_t err = cohera_kernel_load(&kernel, "kernel.cbin");

// Launch kernel
void* args[] = { &input, &output, &config };
cohera_kernel_launch(kernel, grid_dim, block_dim, args, shared_size, stream);
```

### 8.2 JIT Compilation (Future)

```c
// Compile at runtime
cohera_module_t module;
cohera_compile_options_t opts = { .opt_level = 3, .arch = "pavpu10" };
cohera_error_t err = cohera_compile_ckl(&module, source_code, &opts);

// Get kernel from module
cohera_kernel_t kernel;
cohera_module_get_kernel(module, "my_kernel", &kernel);
```

---

## 9. Implementation Roadmap

| Phase | Deliverable | Dependencies | Effort |
|-------|-------------|--------------|--------|
| **Phase 1** | LLVM Fork + Target Registration | LLVM 17+ | 2 months |
| **Phase 2** | Basic ISA Codegen | Phase 1 | 3 months |
| **Phase 3** | CKL Frontend (Clang extension) | Phase 1 | 2 months |
| **Phase 4** | Phase-Aware Optimizations | Phase 2, 3 | 4 months |
| **Phase 5** | Linker + Binary Format | Phase 2 | 2 months |
| **Phase 6** | Testing + Validation | All | 3 months |
| **Total** | | | **16 months** |

---

## 10. Directory Structure

```
cohera-compiler/
├── CMakeLists.txt
├── include/
│   └── cohera/
│       ├── CKL/                 # CKL AST and parser
│       ├── IR/                  # Custom IR extensions
│       └── Target/              # PA-VPU target
├── lib/
│   ├── Frontend/                # Clang-based CKL frontend
│   │   ├── CKLParser.cpp
│   │   ├── CKLSema.cpp
│   │   └── CKLCodeGen.cpp
│   ├── Transforms/              # Custom LLVM passes
│   │   ├── PhaseFusion.cpp
│   │   ├── CoherenceHoisting.cpp
│   │   ├── TCUReuseAnalysis.cpp
│   │   └── OntologyScheduling.cpp
│   ├── Target/PAVPU/            # Backend
│   │   ├── PAVPUTargetMachine.cpp
│   │   ├── PAVPUInstrInfo.td
│   │   ├── PAVPURegisterInfo.td
│   │   ├── PAVPUISelDAGToDAG.cpp
│   │   └── PAVPUAsmPrinter.cpp
│   └── Binary/                  # Binary format
│       ├── COHERABinaryWriter.cpp
│       └── COHERABinaryReader.cpp
├── tools/
│   ├── coherac/                 # Compiler driver
│   ├── cohera-opt/              # Optimizer
│   ├── cohera-lld/              # Linker
│   └── cohera-dis/              # Disassembler
└── test/
    ├── CodeGen/
    ├── Transforms/
    └── Frontend/
```

---

*Document Version: 1.0*
*Related: COHERA_SDK_SPECIFICATION.md, COHERA_ISA_REFERENCE.md*
