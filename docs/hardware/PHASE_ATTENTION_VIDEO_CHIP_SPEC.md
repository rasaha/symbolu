# Phase Attention Video Processing Unit (PA-VPU)

## Hardware Specification v1.0

**Classification:** Patent-Adjacent Technical Specification
**Target:** ASIC/FPGA Implementation for Real-Time Video Processing
**Date:** 2024-12-30

---

## 1. Executive Summary

This document specifies a hardware architecture for processing camera frames using Phase Attention with O(n) complexity. The design leverages HBM3 bandwidth to achieve real-time 4K video processing with unlimited temporal context.

### Key Specifications

| Parameter | Value |
|-----------|-------|
| Max Resolution | 4K (3840×2160) @ 60fps |
| Attention Complexity | O(n) per frame |
| Temporal Context | Unlimited (O(1) memory) |
| State Dimensions | 124 (Cognitive State) |
| Ontological Layers | 12 |
| Target Process | 5nm / 4nm |
| HBM3 Interface | 3.35 TB/s |
| Power Target | < 75W (video inference) |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PA-VPU TOP LEVEL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   CAMERA     │    │   HBM3       │    │   HOST       │                  │
│  │   INTERFACE  │    │   CONTROLLER │    │   INTERFACE  │                  │
│  │   (MIPI CSI) │    │   (3.35TB/s) │    │   (PCIe 5.0) │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      SYSTEM FABRIC (NoC)                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   PATCH      │    │   PHASE      │    │   ONTOLOGY   │                  │
│  │   EMBEDDER   │───▶│   ATTENTION  │───▶│   PROJECTOR  │                  │
│  │   UNIT (PEU) │    │   UNIT (PAU) │    │   UNIT (OPU) │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                             │                   │                           │
│                             ▼                   ▼                           │
│                      ┌──────────────┐    ┌──────────────┐                  │
│                      │   TEMPORAL   │    │   STATE      │                  │
│                      │   CONTEXT    │    │   DELTA      │                  │
│                      │   UNIT (TCU) │    │   UNIT (SDU) │                  │
│                      └──────────────┘    └──────────────┘                  │
│                                                 │                           │
│                                                 ▼                           │
│                                          ┌──────────────┐                  │
│                                          │   OUTPUT     │                  │
│                                          │   INTERFACE  │                  │
│                                          └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Register Specifications

### 3.1 Global Control Registers (GCR)

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0000 | GCR_CTRL | 32 | RW | Global control register |
| 0x0004 | GCR_STATUS | 32 | RO | Global status register |
| 0x0008 | GCR_IRQ_EN | 32 | RW | Interrupt enable |
| 0x000C | GCR_IRQ_STAT | 32 | RW1C | Interrupt status |
| 0x0010 | GCR_FRAME_CNT | 64 | RO | Total frames processed |
| 0x0018 | GCR_CLK_CTRL | 32 | RW | Clock gating control |

**GCR_CTRL Bit Fields:**
```
[0]     ENABLE          - Global enable
[1]     SOFT_RESET      - Soft reset (auto-clear)
[2]     FRAME_START     - Start frame processing
[3]     CONTINUOUS      - Continuous mode enable
[7:4]   SYNC_STEPS      - Phase sync iterations (1-15, default 3)
[15:8]  PRECISION       - FP16/BF16/FP32 select
[23:16] BATCH_SIZE      - Batch size (1-16)
[31:24] RESERVED
```

### 3.2 Patch Embedder Unit (PEU) Registers

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0100 | PEU_CTRL | 32 | RW | PEU control |
| 0x0104 | PEU_IMG_W | 16 | RW | Image width (pixels) |
| 0x0106 | PEU_IMG_H | 16 | RW | Image height (pixels) |
| 0x0108 | PEU_PATCH_SZ | 8 | RW | Patch size (8/16/32) |
| 0x010C | PEU_EMBED_DIM | 16 | RW | Embedding dimension |
| 0x0110 | PEU_WEIGHT_BASE | 64 | RW | Weight matrix HBM address |
| 0x0118 | PEU_BIAS_BASE | 64 | RW | Bias vector HBM address |
| 0x0120 | PEU_INPUT_BASE | 64 | RW | Input frame HBM address |
| 0x0128 | PEU_OUTPUT_BASE | 64 | RW | Output embeddings HBM address |

**Computed Values (read-only):**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0130 | PEU_NUM_PATCHES | 32 | RO | = (IMG_W/PATCH_SZ) × (IMG_H/PATCH_SZ) |
| 0x0134 | PEU_TOKENS | 32 | RO | = NUM_PATCHES (sequence length N) |

### 3.3 Phase Attention Unit (PAU) Registers

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0200 | PAU_CTRL | 32 | RW | PAU control |
| 0x0204 | PAU_STATUS | 32 | RO | PAU status |
| 0x0208 | PAU_SEQ_LEN | 32 | RW | Sequence length N |
| 0x020C | PAU_EMBED_DIM | 16 | RW | Embedding dimension D |
| 0x020E | PAU_NUM_HEADS | 8 | RW | Number of attention heads H |
| 0x0210 | PAU_SYNC_LR | 16 | RW | Sync learning rate (FP16) |
| 0x0212 | PAU_TEMPERATURE | 16 | RW | Attention temperature (FP16) |
| 0x0214 | PAU_SYNC_STEPS | 8 | RW | Synchronization iterations |
| 0x0218 | PAU_CAUSAL_MASK | 8 | RW | Enable causal masking |

**Projection Weight Pointers:**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0220 | PAU_WQ_BASE | 64 | Query projection weights |
| 0x0228 | PAU_WK_BASE | 64 | Key projection weights |
| 0x0230 | PAU_WV_BASE | 64 | Value projection weights |
| 0x0238 | PAU_WO_BASE | 64 | Output projection weights |
| 0x0240 | PAU_WPHASE_BASE | 64 | Phase projection weights |

**PAU_CTRL Bit Fields:**
```
[0]     ENABLE          - PAU enable
[1]     CAUSAL          - Causal attention mode
[2]     STREAMING       - Enable streaming mode (use TCU)
[3]     LAYER_NORM      - Enable layer normalization
[7:4]   HEAD_DIM        - Head dimension (D/H)
[15:8]  RESERVED
[23:16] CURRENT_LAYER   - Current ontological layer (0-11)
[31:24] TOTAL_LAYERS    - Total layers to process
```

### 3.4 Temporal Context Unit (TCU) Registers

The TCU maintains cross-frame phase context for O(1) temporal memory.

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0300 | TCU_CTRL | 32 | RW | TCU control |
| 0x0304 | TCU_STATUS | 32 | RO | TCU status |
| 0x0308 | TCU_FRAME_COUNT | 64 | RW | Cumulative frame count |
| 0x0310 | TCU_PHASE_SUM_BASE | 64 | RW | Phase sum buffer HBM address |
| 0x0318 | TCU_PHASE_MEAN_BASE | 64 | RW | Phase mean buffer HBM address |
| 0x0320 | TCU_DECAY_FACTOR | 16 | RW | Temporal decay (FP16, 0.99 default) |
| 0x0324 | TCU_WINDOW_SIZE | 32 | RW | Sliding window (frames, 0=infinite) |

**Phase Context Memory Layout:**
```
TCU_PHASE_SUM_BASE:
  [H × head_dim] float16 - Cumulative phase sum per head

TCU_PHASE_MEAN_BASE:
  [H × head_dim] float16 - Running phase mean per head
```

**TCU_CTRL Bit Fields:**
```
[0]     ENABLE          - TCU enable
[1]     RESET_CONTEXT   - Reset temporal context
[2]     EMA_MODE        - Use exponential moving average
[3]     WINDOW_MODE     - Use sliding window
[7:4]   RESERVED
[15:8]  NUM_HEADS       - Number of attention heads
[31:16] HEAD_DIM        - Dimension per head
```

### 3.5 Ontology Projector Unit (OPU) Registers

Maps hidden states to 124-dimensional Cognitive State.

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0400 | OPU_CTRL | 32 | RW | OPU control |
| 0x0404 | OPU_STATUS | 32 | RO | OPU status |
| 0x0408 | OPU_HIDDEN_DIM | 16 | RW | Input hidden dimension (768) |
| 0x040A | OPU_STATE_DIM | 16 | RW | Output state dimension (124) |

**Cognitive State Dimension Breakdown:**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0410 | OPU_PHONEME_DIM | 8 | RW | Phoneme layer dims (44) |
| 0x0411 | OPU_TOPIC_DIM | 8 | RW | Topic layer dims (64) |
| 0x0412 | OPU_ONTOLOGY_DIM | 8 | RW | Ontology layer dims (12) |
| 0x0413 | OPU_DYNAMICS_DIM | 8 | RW | Dynamics layer dims (4) |

**Projection Weight Pointers:**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0420 | OPU_W_PHONEME | 64 | Phoneme projector [768→44] |
| 0x0428 | OPU_W_TOPIC | 64 | Topic projector [768→64] |
| 0x0430 | OPU_W_ONTOLOGY | 64 | Ontology projector [768→12] |
| 0x0438 | OPU_W_DYNAMICS | 64 | Dynamics projector [768→4] |

**Output State Buffer:**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0440 | OPU_STATE_BASE | 64 | Cognitive state output buffer |

### 3.6 State Delta Unit (SDU) Registers

Computes ΔS = S_{t+1} - S_t for learning/inference.

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x0500 | SDU_CTRL | 32 | RW | SDU control |
| 0x0504 | SDU_STATUS | 32 | RO | SDU status |
| 0x0508 | SDU_PREV_STATE_BASE | 64 | RW | Previous state buffer |
| 0x0510 | SDU_CURR_STATE_BASE | 64 | RW | Current state buffer |
| 0x0518 | SDU_DELTA_BASE | 64 | RW | Delta output buffer |
| 0x0520 | SDU_PRED_DELTA_BASE | 64 | RW | Predicted delta (training) |

**Loss Computation (Training Mode):**
| Offset | Name | Width | Description |
|--------|------|-------|-------------|
| 0x0528 | SDU_LOSS_MSE | 32 | RO | MSE(pred_Δ, actual_Δ) |
| 0x052C | SDU_LOSS_COHERENCE | 32 | RO | Coherence stability loss |
| 0x0530 | SDU_LOSS_ENTROPY | 32 | RO | Entropy smoothing loss |
| 0x0534 | SDU_LOSS_TOTAL | 32 | RO | Weighted total loss |

---

## 4. 12-Layer Ontology Hardware Mapping

### 4.1 Layer-to-Frequency Mapping

Each ontological layer operates at a prescribed frequency for phase-locked processing:

| Layer | ID | Frequency (Hz) | Clock Divider | Function |
|-------|-----|----------------|---------------|----------|
| O1 | POTENTIAL | 10,000 | /1 | Dormant capacity sensing |
| O2 | IDENTITY | 5,000 | /2 | Classification marking |
| O3 | EXECUTION | 2,000 | /5 | Somatic initiation |
| O4 | STRUCTURE | 1,000 | /10 | Shape/form encoding |
| O5 | COGNITION | 500 | /20 | Perception processing |
| O6 | AGENCY | 200 | /50 | Intent/control vectors |
| O7 | REASONING | 100 | /100 | Sequential logic |
| O8 | PURPOSE | 40 | /250 | Goal orientation |
| O9 | WITNESSES | 20 | /500 | Meta-observation |
| O10 | UNIFYING | 10 | /1000 | Field coherence |
| O11 | INTEGRATION | 5 | /2000 | Resolution/consolidation |
| O12 | ABSOLVING | 1 | /10000 | Dissolution/transcendence |

### 4.2 Layer Processing Block

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ONTOLOGICAL LAYER BLOCK (OLB)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                    │
│  │  LAYER_ID [4b]  │  Layer index (0-11)                               │
│  │  FREQ_DIV [14b] │  Clock divider for this layer                     │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE GENERATOR                               │   │
│  │                                                                  │   │
│  │  master_clk ──┬──▶ [÷FREQ_DIV] ──▶ layer_clk                    │   │
│  │               │                                                  │   │
│  │               └──▶ [PHASE_ACC] ──▶ phase[31:0]                  │   │
│  │                         │                                        │   │
│  │                         ▼                                        │   │
│  │                    cos_lut[phase] ──▶ phase_mod                 │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE ATTENTION CORE                          │   │
│  │                                                                  │   │
│  │  input[N,D] ──▶ Q_proj ──┐                                      │   │
│  │             ──▶ K_proj ──┼──▶ PHASE_SYNC ──▶ output[N,D]        │   │
│  │             ──▶ V_proj ──┘        │                              │   │
│  │                                   ▼                              │   │
│  │                          phase_context ──▶ TCU                  │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    KOSHA ANCHOR                                  │   │
│  │                                                                  │   │
│  │  Layer → Kosha mapping (hardwired):                             │   │
│  │    O1        → pre-annamaya    (layer_weight = 0.0)             │   │
│  │    O2,O3     → annamaya        (layer_weight = 0.2)             │   │
│  │    O4        → pranamaya       (layer_weight = 0.4)             │   │
│  │    O5,O6     → manomaya        (layer_weight = 0.6)             │   │
│  │    O7,O8     → vijnanamaya     (layer_weight = 0.8)             │   │
│  │    O9,O10,O11→ anandamaya      (layer_weight = 1.0)             │   │
│  │    O12       → bridge/none     (layer_weight = 1.0)             │   │
│  │                                                                  │   │
│  │  kosha_entropy = |source_kosha - target_kosha| / 4              │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Ontology Layer Registers (per layer)

Base address: `0x1000 + (layer_idx × 0x100)`

| Offset | Name | Width | R/W | Description |
|--------|------|-------|-----|-------------|
| 0x00 | OLB_CTRL | 32 | RW | Layer control |
| 0x04 | OLB_STATUS | 32 | RO | Layer status |
| 0x08 | OLB_FREQ_DIV | 16 | RW | Frequency divider |
| 0x0A | OLB_KOSHA_ANCHOR | 8 | RO | Kosha anchor (0-5) |
| 0x0C | OLB_PHASE_ACC | 32 | RO | Current phase accumulator |
| 0x10 | OLB_ACTIVATION | 16 | RO | Layer activation level (FP16) |
| 0x14 | OLB_COHERENCE | 16 | RO | Layer coherence score (FP16) |
| 0x18 | OLB_WEIGHT_BASE | 64 | RW | Layer weights HBM address |

---

## 5. Timing Diagrams

### 5.1 Single Frame Processing Pipeline

```
Clock:     ____┌──┐__┌──┐__┌──┐__┌──┐__┌──┐__┌──┐__┌──┐__┌──┐__┌──┐__
                │    │    │    │    │    │    │    │    │    │

Frame In:  ════╪════════════╗
           4K  │            ║
               │            ╚══════════════════════════════════════

PEU:       ────┼────────────╔════════════╗
           IDLE│            ║  PATCHING  ║
               │            ╚════════════╩══════════════════════════

PAU L1-12: ────┼────────────────────────╔═══╦═══╦═══╦═══╦═══╦═══╗
           IDLE│                        ║L1 ║L2 ║...║L11║L12║   ║
               │                        ╚═══╩═══╩═══╩═══╩═══╩═══╝

TCU:       ────┼────────────────────────────────────────────╔═══╗
           IDLE│                                            ║UPD║
               │                                            ╚═══╝

OPU:       ────┼────────────────────────────────────────────────╔═══╗
           IDLE│                                                ║PRJ║
               │                                                ╚═══╝

SDU:       ────┼────────────────────────────────────────────────────╔═══╗
           IDLE│                                                    ║ΔS ║
               │                                                    ╚═══╝

Output:    ════╪════════════════════════════════════════════════════════╔══
           WAIT│                                                        ║OK
               │                                                        ╚══

           ────┼────────────────────────────────────────────────────────────
Timeline:  0   1ms          2ms         3ms         4ms         5ms    5.5ms
```

**Timing Budget (4K @ 60fps = 16.67ms/frame):**

| Stage | Duration | Description |
|-------|----------|-------------|
| PEU | 1.0 ms | Patch embedding (32,400 patches × 768) |
| PAU (12 layers) | 3.0 ms | Phase attention (0.25ms × 12 layers) |
| TCU | 0.2 ms | Temporal context update |
| OPU | 0.2 ms | Ontology projection (768→124) |
| SDU | 0.1 ms | State delta computation |
| **Total** | **4.5 ms** | **< 16.67ms budget (3.7× margin)** |

### 5.2 Phase Synchronization Detail (PAU)

```
        ┌─────────────────────────────────────────────────────────────┐
        │              PHASE SYNC ITERATION (×3)                       │
        └─────────────────────────────────────────────────────────────┘

Cycle:     0    1    2    3    4    5    6    7    8    9    10   11
           │    │    │    │    │    │    │    │    │    │    │    │
           ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
Q_proj: │LOAD│MUL │ACC │    │    │    │    │    │    │    │    │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
Phase:  │    │    │    │INIT│SIN │    │    │    │    │    │    │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
Mean:   │    │    │    │    │    │ACC │DIV │    │    │    │    │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
Gradient│    │    │    │    │    │    │    │CALC│    │    │    │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
Update: │    │    │    │    │    │    │    │    │φ+=α│    │    │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
        ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
V_agg:  │    │    │    │    │    │    │    │    │    │WSUM│OUT │    │
        └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘

Legend:
  LOAD  = Load from HBM
  MUL   = Matrix multiply
  ACC   = Accumulate
  INIT  = Initialize phases
  SIN   = Sigmoid → [0,2π]
  DIV   = Division for mean
  CALC  = -N × sin(φᵢ - φ_mean)
  φ+=α  = Phase update
  WSUM  = Weighted V sum
  OUT   = Output write
```

### 5.3 Cross-Frame Temporal Context

```
        Frame N-1           Frame N             Frame N+1
        ─────────           ───────             ─────────
            │                   │                   │
            ▼                   ▼                   ▼
        ┌───────┐           ┌───────┐           ┌───────┐
        │  PAU  │           │  PAU  │           │  PAU  │
        └───┬───┘           └───┬───┘           └───┬───┘
            │                   │                   │
            ▼                   ▼                   ▼
        ┌───────┐           ┌───────┐           ┌───────┐
        │phase_n-1          │phase_n            │phase_n+1
        │sum    │           │sum    │           │sum    │
        └───┬───┘           └───┬───┘           └───┬───┘
            │                   │                   │
            └──────────┬────────┴──────────┬────────┘
                       │                   │
                       ▼                   ▼
               ┌───────────────────────────────────┐
               │         TCU ACCUMULATOR           │
               │                                   │
               │  phase_sum += phase_n             │
               │  frame_count += 1                 │
               │  phase_mean = phase_sum / count   │
               │                                   │
               │  Memory: O(H × d) = O(1)         │
               │  NOT O(frames × N × D)           │
               └───────────────────────────────────┘

Key Insight:
  Traditional: Store all KV for all frames → O(frames × N × D)
  Phase:       Store cumulative mean → O(H × d) constant
```

---

## 6. Memory Map

### 6.1 HBM3 Layout (80GB Example)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HBM3 MEMORY MAP (80GB)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  0x0000_0000_0000 ┌─────────────────────────────────────────────────┐  │
│                   │  MODEL WEIGHTS (Read-Only)                       │  │
│                   │                                                  │  │
│                   │  PEU Weights:    25 MB   (patch embed)          │  │
│                   │  PAU Weights:   450 MB   (12 layers × QKV+O)    │  │
│                   │  OPU Weights:     1 MB   (768→124 projection)   │  │
│                   │  SDU Weights:     0.5 MB (delta predictor)      │  │
│                   │                                                  │  │
│                   │  Total:         ~500 MB                          │  │
│  0x0000_2000_0000 └─────────────────────────────────────────────────┘  │
│                                                                         │
│  0x0000_2000_0000 ┌─────────────────────────────────────────────────┐  │
│                   │  FRAME BUFFERS (Triple Buffer)                   │  │
│                   │                                                  │  │
│                   │  Input Frame 0:   50 MB  (4K RGBA)              │  │
│                   │  Input Frame 1:   50 MB                         │  │
│                   │  Input Frame 2:   50 MB                         │  │
│                   │                                                  │  │
│                   │  Total:          150 MB                          │  │
│  0x0000_2A00_0000 └─────────────────────────────────────────────────┘  │
│                                                                         │
│  0x0000_2A00_0000 ┌─────────────────────────────────────────────────┐  │
│                   │  ACTIVATION MEMORY (Working Set)                 │  │
│                   │                                                  │  │
│                   │  Patch Embeddings:   400 MB  (32K × 768 × fp16) │  │
│                   │  PAU Activations:   4800 MB  (12L × 32K × 768)  │  │
│                   │  Intermediate:       800 MB  (scratch)          │  │
│                   │                                                  │  │
│                   │  Total:             6 GB                         │  │
│  0x0000_4200_0000 └─────────────────────────────────────────────────┘  │
│                                                                         │
│  0x0000_4200_0000 ┌─────────────────────────────────────────────────┐  │
│                   │  TEMPORAL CONTEXT (TCU State)                    │  │
│                   │                                                  │  │
│                   │  Phase Sum:      12 KB  (12H × 64d × fp16)      │  │
│                   │  Phase Mean:     12 KB                          │  │
│                   │  Frame Counter:   8 B                           │  │
│                   │                                                  │  │
│                   │  Total:          ~25 KB  (O(1) regardless of    │  │
│                   │                          video length!)          │  │
│  0x0000_4200_8000 └─────────────────────────────────────────────────┘  │
│                                                                         │
│  0x0000_4200_8000 ┌─────────────────────────────────────────────────┐  │
│                   │  COGNITIVE STATE OUTPUT                          │  │
│                   │                                                  │  │
│                   │  State Buffer:   248 B   (124 × fp16)           │  │
│                   │  Delta Buffer:   248 B   (124 × fp16)           │  │
│                   │  History (100f): 25 KB   (optional)             │  │
│                   │                                                  │  │
│                   │  Total:          ~26 KB                          │  │
│  0x0000_4200_F000 └─────────────────────────────────────────────────┘  │
│                                                                         │
│  0x0000_4200_F000 ┌─────────────────────────────────────────────────┐  │
│                   │  FREE / EXPANSION                                │  │
│                   │                                                  │  │
│                   │  Available:      ~73 GB                          │  │
│                   │                                                  │  │
│                   │  Can support:                                    │  │
│                   │  - 8K resolution (4× current)                   │  │
│                   │  - Batch size 16                                 │  │
│                   │  - Larger models (7B params)                     │  │
│                   │                                                  │  │
│  0x0014_0000_0000 └─────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Bandwidth Analysis

| Operation | Size | Frequency | Bandwidth |
|-----------|------|-----------|-----------|
| Frame Input | 50 MB | 60 Hz | 3.0 GB/s |
| PEU Read Weights | 25 MB | 60 Hz | 1.5 GB/s |
| PEU Write Embeds | 400 MB | 60 Hz | 24.0 GB/s |
| PAU Read/Write | 4.8 GB | 60 Hz | 288.0 GB/s |
| TCU Update | 25 KB | 60 Hz | 1.5 MB/s |
| OPU Output | 248 B | 60 Hz | 15 KB/s |
| **Total** | | | **~316 GB/s** |

**HBM3 Utilization:** 316 GB/s / 3,350 GB/s = **9.4%**

This leaves substantial headroom for:
- Higher resolutions (8K)
- Larger batch sizes
- Multiple camera streams
- Higher frame rates (120fps+)

---

## 7. Power Estimation

### 7.1 Compute Power

| Unit | Operations/Frame | GFLOPS @ 60fps | Est. Power |
|------|------------------|----------------|------------|
| PEU | 25M (matmul) | 1.5 | 2W |
| PAU | 9B (12L × 32K × 768 × 3) | 540 | 45W |
| TCU | 150K (accumulate) | 0.009 | 0.1W |
| OPU | 95K (projection) | 0.006 | 0.1W |
| SDU | 31K (delta) | 0.002 | 0.05W |
| **Compute Total** | | **~542 GFLOPS** | **~47W** |

### 7.2 Memory Power

| Interface | Activity | Est. Power |
|-----------|----------|------------|
| HBM3 (316 GB/s active) | 9.4% | 15W |
| SRAM (registers/cache) | 100% | 5W |
| **Memory Total** | | **~20W** |

### 7.3 Total Power Budget

| Component | Power |
|-----------|-------|
| Compute | 47W |
| Memory | 20W |
| I/O (MIPI, PCIe) | 5W |
| Misc (clock, control) | 3W |
| **Total** | **~75W** |

---

## 8. Integration Example: Video Understanding Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FULL VIDEO UNDERSTANDING SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │   CAMERA    │  4K @ 60fps                                               │
│  │   SENSOR    │────────────────────────────────────────┐                  │
│  └─────────────┘                                        │                  │
│                                                         ▼                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        PA-VPU CHIP                                    │  │
│  │                                                                       │  │
│  │  Frame → PEU → PAU (12 layers) → TCU → OPU → SDU → CognitiveState   │  │
│  │                                                                       │  │
│  │  Output per frame:                                                    │  │
│  │    cognitive_state[124] = {                                          │  │
│  │      phoneme_energy[44],   // Visual pattern distribution            │  │
│  │      topic_embedding[64],  // Scene/object embedding                 │  │
│  │      ontology_probs[12],   // 12-layer activation                    │  │
│  │      dynamics[4]           // coherence, entropy, confidence, momentum│  │
│  │    }                                                                  │  │
│  │    state_delta[124] = S_t - S_{t-1}                                  │  │
│  │                                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                          │                                  │
│                                          ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   DOWNSTREAM PROCESSING                               │  │
│  │                                                                       │  │
│  │  Option A: Direct Hardware Decode                                     │  │
│  │    ontology_probs[12] → 12-bit activity code                         │  │
│  │    O1_POTENTIAL high → "dormant object detected"                     │  │
│  │    O6_AGENCY high → "intentional motion detected"                    │  │
│  │    O9_WITNESSES high → "observer present in scene"                   │  │
│  │                                                                       │  │
│  │  Option B: LLM Integration                                            │  │
│  │    cognitive_state[124] → Language model prompt prefix               │  │
│  │    "Given visual state [coherence=0.9, agency=0.7, ...]"            │  │
│  │    → Natural language scene description                              │  │
│  │                                                                       │  │
│  │  Option C: Robotic Control                                            │  │
│  │    state_delta[124] → Motion planning constraints                    │  │
│  │    Δ(ontology_probs) → "scene stability changed, replan"            │  │
│  │                                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Comparison with Existing Solutions

| Feature | Standard ViT | FlashAttention-2 | **PA-VPU (This Design)** |
|---------|--------------|------------------|--------------------------|
| Attention Complexity | O(n²) | O(n²) (IO-optimized) | **O(n)** |
| 4K Single Frame | OOM | ✓ (chunked) | **✓ (native)** |
| 30-Frame Context | OOM | ~12 GB KV | **25 KB** |
| 1000-Frame Context | Impossible | ~400 GB | **25 KB** |
| Temporal Coherence | External | External | **Built-in** |
| Interpretable State | No | No | **Yes (124-dim)** |
| Ontological Grounding | No | No | **Yes (12-layer)** |
| Power (4K@60fps) | ~300W | ~150W | **~75W** |

---

## 10. Implementation Notes

### 10.1 Critical Path

The PAU is the critical path. Optimizations:
1. Pipeline sync iterations across heads
2. Use FP16 throughout (BF16 for accumulation)
3. Fuse phase_proj + sigmoid in single kernel
4. Precompute sin/cos LUT for phase operations

### 10.2 Verification Points

| Test | Criterion | Method |
|------|-----------|--------|
| O(n) Scaling | 2× seq → 2× time | Sweep N from 1K to 64K |
| Temporal Coherence | Phase stability across frames | 1000-frame video test |
| Kosha Entropy | Layer disagreement < 0.3 | Cross-layer activation analysis |
| Power | < 75W @ 4K/60fps | Board-level measurement |

### 10.3 Future Extensions

1. **8K Support**: Increase patch count to 129,600, stay within HBM budget
2. **Multi-Camera**: Process 4× 4K streams simultaneously
3. **Training Mode**: Add backprop through phase sync for on-device learning
4. **Sparse Attention**: Skip low-coherence patches for 2× speedup

---

## 11. Comparison: PA-VPU vs NVIDIA Jetson Orin

### 11.1 Platform Overview

| Specification | Jetson Orin NX | Jetson AGX Orin | PA-VPU (This Design) |
|---------------|----------------|-----------------|----------------------|
| **Process Node** | 8nm | 8nm | 5nm (target) |
| **CPU** | 8-core Arm Cortex-A78AE | 12-core Arm Cortex-A78AE | None (accelerator) |
| **GPU** | 1024 CUDA + 32 Tensor | 2048 CUDA + 64 Tensor | None (phase units) |
| **AI Accelerator** | 2× NVDLA | 2× NVDLA | PAU + OPU + SDU |
| **Memory** | 16GB LPDDR5 | 64GB LPDDR5 | 80GB HBM3 |
| **Memory BW** | 102 GB/s | 205 GB/s | 3,350 GB/s |
| **AI TOPS** | 100 TOPS (INT8) | 275 TOPS (INT8) | ~50 TOPS (FP16) |
| **TDP** | 25W | 60W | 75W |
| **Form Factor** | Module (70×45mm) | Module (100×87mm) | Chip (custom) |

### 11.2 Architecture Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      JETSON ORIN ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  ARM CPU    │  │  Ampere GPU │  │    NVDLA    │  │     PVA     │        │
│  │  (General)  │  │  (Parallel) │  │  (DL Accel) │  │  (Vision)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                                   │                                         │
│                          ┌────────┴────────┐                                │
│                          │   LPDDR5 Memory │                                │
│                          │   102-205 GB/s  │                                │
│                          └─────────────────┘                                │
│                                                                             │
│  Approach: General-purpose heterogeneous compute                            │
│  Attention: Standard O(n²) via cuDNN/TensorRT                              │
│  Temporal: External KV cache management                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        PA-VPU ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │     PEU     │  │     PAU     │  │     OPU     │  │     SDU     │        │
│  │  (Patches)  │  │  (Phase)    │  │  (Ontology) │  │  (Delta)    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┴───────┬────────┴────────────────┘                │
│                                  │                                          │
│                          ┌───────┴───────┐                                  │
│                          │  TCU (25 KB)  │  ← O(1) temporal context        │
│                          └───────┬───────┘                                  │
│                                  │                                          │
│                          ┌───────┴───────┐                                  │
│                          │  HBM3 Memory  │                                  │
│                          │  3,350 GB/s   │                                  │
│                          └───────────────┘                                  │
│                                                                             │
│  Approach: Purpose-built phase synchronization                              │
│  Attention: O(n) via mean-field approximation                              │
│  Temporal: Built-in O(1) via TCU accumulator                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Attention Mechanism Comparison

| Aspect | Jetson Orin (cuDNN/TensorRT) | PA-VPU (Phase Attention) |
|--------|------------------------------|--------------------------|
| **Algorithm** | Scaled dot-product attention | Mean-field phase sync |
| **Complexity** | O(n²) per layer | O(n) per layer |
| **Memory Scaling** | O(n²) attention matrix | O(n) linear |
| **FlashAttention** | Yes (CUDA kernel) | N/A (native O(n)) |
| **KV Cache** | Per-token storage | Phase accumulator only |
| **Max Context (64GB)** | ~32K tokens | ~2M tokens |

**Concrete Example - 4K Video Frame (32,400 patches):**

| Metric | Jetson AGX Orin | PA-VPU |
|--------|-----------------|--------|
| Attention matrix size | 32,400² × 2B = 2.1 GB | N/A |
| Per-layer memory | 2.1 GB | 50 MB |
| 12-layer total | 25 GB (exceeds 64GB with act.) | 600 MB |
| Feasibility | Requires chunking/FlashAttn | Native support |

### 11.4 Temporal Context Comparison

**Scenario: 10-second 4K video @ 60fps = 600 frames**

| Metric | Jetson Orin | PA-VPU |
|--------|-------------|--------|
| KV cache per frame | 400 MB | N/A |
| 600-frame context | 240 GB (impossible) | 25 KB |
| Memory strategy | Sliding window / eviction | Full history |
| Context quality | Lossy (window limit) | Lossless (all frames) |
| Latency spike | Yes (cache miss) | No (O(1) access) |

### 11.5 Advantages of PA-VPU over Jetson Orin

| Advantage | Description | Impact |
|-----------|-------------|--------|
| **1. True O(n) Scaling** | No attention matrix computation | 4K+ resolution without chunking |
| **2. Unlimited Temporal Context** | 25KB regardless of video length | Hour-long video understanding |
| **3. 16× Memory Bandwidth** | HBM3 vs LPDDR5 | Bottleneck elimination |
| **4. Interpretable Output** | 124-dim Cognitive State | Explainable AI |
| **5. Ontological Grounding** | 12-layer semantic hierarchy | Structured reasoning |
| **6. Native Phase Coherence** | Built-in temporal smoothing | No post-processing needed |
| **7. Deterministic Latency** | Fixed pipeline depth | Real-time guarantees |
| **8. Lower Complexity** | Single-purpose accelerator | Smaller verification surface |

### 11.6 Advantages of Jetson Orin over PA-VPU

| Advantage | Description | Impact |
|-----------|-------------|--------|
| **1. General Purpose** | CPU + GPU + DLA + PVA | Run any workload |
| **2. Mature Ecosystem** | CUDA, TensorRT, DeepStream | Immediate deployment |
| **3. Existing Models** | Run any PyTorch/TF model | No retraining needed |
| **4. Edge Form Factor** | 25-60W module | Embedded deployment |
| **5. Production Ready** | Available now, proven | No development risk |
| **6. Peripheral Support** | USB, PCIe, GPIO, CSI | Complete system |
| **7. Software Stack** | JetPack, TAO, Isaac | Full toolchain |
| **8. Multi-Task** | Vision + LLM + control | Single platform |

### 11.7 Detailed Trade-off Analysis

#### Power Efficiency (TOPS/W)

| Platform | Peak TOPS | TDP | TOPS/W | Notes |
|----------|-----------|-----|--------|-------|
| Orin NX (INT8) | 100 | 25W | 4.0 | General compute |
| AGX Orin (INT8) | 275 | 60W | 4.6 | General compute |
| PA-VPU (FP16) | 50 | 75W | 0.67 | Phase-specific |
| PA-VPU (effective)* | 500 | 75W | 6.7 | O(n) equivalent |

*Effective TOPS accounts for O(n) vs O(n²): processing 32K tokens with O(n) is equivalent to ~10× more TOPS with O(n²).

#### Workload Suitability

| Workload | Jetson Orin | PA-VPU | Winner |
|----------|-------------|--------|--------|
| Short video (<1min) | ✓ Good | ✓ Good | Tie |
| Long video (>10min) | ✗ OOM | ✓ Native | PA-VPU |
| 4K real-time | ⚠ Chunked | ✓ Native | PA-VPU |
| 8K processing | ✗ Impractical | ✓ Feasible | PA-VPU |
| Multi-stream (4×4K) | ⚠ Limited | ✓ Headroom | PA-VPU |
| Object detection | ✓ Optimized | ⚠ Via ontology | Orin |
| Pose estimation | ✓ Native | ⚠ Custom | Orin |
| LLM inference | ✓ Supported | ✗ Not designed | Orin |
| Robotic control | ✓ Isaac | ⚠ External CPU | Orin |
| Edge deployment | ✓ 25W option | ⚠ 75W | Orin |

#### Development Effort

| Aspect | Jetson Orin | PA-VPU |
|--------|-------------|--------|
| Time to first demo | Days | Months (FPGA) / Years (ASIC) |
| Model porting | Export + optimize | Retrain for phase attention |
| Debugging tools | Nsight, profilers | Custom (must build) |
| Community support | Large | None (novel architecture) |
| Documentation | Extensive | This document + internal |

### 11.8 Hybrid Architecture Recommendation

For maximum flexibility, consider a hybrid approach:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID SYSTEM ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        JETSON AGX ORIN                                 │ │
│  │                                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │ │
│  │  │  ARM CPU    │  │  GPU        │  │  NVDLA      │                    │ │
│  │  │  Control    │  │  Short-term │  │  Detection  │                    │ │
│  │  │  Planning   │  │  Processing │  │  Tracking   │                    │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                    │ │
│  │         └────────────────┴────────────────┘                            │ │
│  │                          │                                             │ │
│  └──────────────────────────┼─────────────────────────────────────────────┘ │
│                             │ PCIe 4.0                                      │
│  ┌──────────────────────────┼─────────────────────────────────────────────┐ │
│  │                          ▼                                             │ │
│  │                    PA-VPU ACCELERATOR                                  │ │
│  │                                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │ │
│  │  │  Long-term  │  │  Ontology   │  │  State      │                    │ │
│  │  │  Context    │  │  Mapping    │  │  Delta      │                    │ │
│  │  │  (TCU)      │  │  (OPU)      │  │  (SDU)      │                    │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                    │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Division of Labor:                                                         │
│  ├─ Orin GPU: Frame-level feature extraction (short context)              │
│  ├─ Orin DLA: Object detection, tracking (optimized models)               │
│  ├─ Orin CPU: Control logic, planning, I/O                                │
│  ├─ PA-VPU: Long-term temporal context (unlimited history)                │
│  └─ PA-VPU: Ontological state for high-level reasoning                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.9 Decision Matrix

| If your priority is... | Choose | Reasoning |
|------------------------|--------|-----------|
| Time to market | Jetson Orin | Production-ready ecosystem |
| Long video understanding | PA-VPU | O(1) temporal context |
| 8K or multi-stream | PA-VPU | HBM3 bandwidth |
| Edge deployment (<30W) | Jetson Orin NX | Lower power envelope |
| Interpretable AI | PA-VPU | Ontological state output |
| Running existing models | Jetson Orin | CUDA/TensorRT support |
| Novel research | PA-VPU | Unique capabilities |
| Robotics platform | Jetson Orin | Isaac SDK, ROS2 |
| Maximum flexibility | Hybrid | Best of both worlds |

### 11.10 Migration Path

**From Jetson Orin to PA-VPU:**

1. **Phase 1**: Run PA-VPU as PCIe accelerator alongside Orin
2. **Phase 2**: Offload temporal context to PA-VPU TCU
3. **Phase 3**: Move attention layers to PA-VPU PAU
4. **Phase 4**: Full PA-VPU for video, Orin for control only

**Development Timeline:**

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| FPGA Prototype | 6 months | Proof of concept on Alveo U280 |
| ASIC RTL | 12 months | Verified Verilog |
| Tape-out | 6 months | GDS to foundry |
| Bring-up | 3 months | First silicon validation |
| Production | 6 months | Volume manufacturing |
| **Total** | **33 months** | Production PA-VPU |

---

## 12. Low-Level Hardware Design

### 12.1 RTL Microarchitecture

#### 12.1.1 Phase Attention Unit (PAU) Detailed Microarchitecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     PAU MICROARCHITECTURE (RTL Level)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT STAGE (Cycle 0-2)                                                        │
│  ════════════════════════                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        INPUT BUFFER (SRAM)                               │   │
│  │                        2 × 32KB double-buffer                            │   │
│  │                                                                          │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │   │
│  │  │  Bank 0      │    │  Bank 1      │    │  Bank 2      │               │   │
│  │  │  (Even Tok)  │    │  (Odd Tok)   │    │  (Prefetch)  │               │   │
│  │  │  8KB×4       │    │  8KB×4       │    │  8KB×4       │               │   │
│  │  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘               │   │
│  │         │                   │                   │                        │   │
│  │         └───────────────────┴───────────────────┘                        │   │
│  │                             │                                            │   │
│  │                    ┌────────┴────────┐                                   │   │
│  │                    │   ARBITER       │                                   │   │
│  │                    │   Round-robin   │                                   │   │
│  │                    └────────┬────────┘                                   │   │
│  └─────────────────────────────┼────────────────────────────────────────────┘   │
│                                │                                                │
│                                ▼                                                │
│  PROJECTION STAGE (Cycle 3-6)                                                   │
│  ════════════════════════════                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     MATRIX MULTIPLY ARRAY                                │   │
│  │                     16×16 Systolic Array per Head                        │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │  HEAD 0          HEAD 1          HEAD 2      ...    HEAD 11     │    │   │
│  │  │  ┌──────┐        ┌──────┐        ┌──────┐           ┌──────┐    │    │   │
│  │  │  │ Q_PE │        │ Q_PE │        │ Q_PE │           │ Q_PE │    │    │   │
│  │  │  │16×16 │        │16×16 │        │16×16 │           │16×16 │    │    │   │
│  │  │  └──┬───┘        └──┬───┘        └──┬───┘           └──┬───┘    │    │   │
│  │  │     │               │               │                  │        │    │   │
│  │  │  ┌──┴───┐        ┌──┴───┐        ┌──┴───┐           ┌──┴───┐    │    │   │
│  │  │  │ K_PE │        │ K_PE │        │ K_PE │           │ K_PE │    │    │   │
│  │  │  │16×16 │        │16×16 │        │16×16 │           │16×16 │    │    │   │
│  │  │  └──┬───┘        └──┬───┘        └──┬───┘           └──┬───┘    │    │   │
│  │  │     │               │               │                  │        │    │   │
│  │  │  ┌──┴───┐        ┌──┴───┐        ┌──┴───┐           ┌──┴───┐    │    │   │
│  │  │  │ V_PE │        │ V_PE │        │ V_PE │           │ V_PE │    │    │   │
│  │  │  │16×16 │        │16×16 │        │16×16 │           │16×16 │    │    │   │
│  │  │  └──────┘        └──────┘        └──────┘           └──────┘    │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  Total PEs: 12 heads × 3 projections × 256 MACs = 9,216 MACs            │   │
│  │  Throughput: 9,216 × 2 (FMA) × 1GHz = 18.4 TFLOPS                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                                │
│                                ▼                                                │
│  PHASE COMPUTATION STAGE (Cycle 7-10)                                           │
│  ════════════════════════════════════                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     PHASE SYNC ENGINE                                    │   │
│  │                                                                          │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  SIGMOID UNIT (Vectorized)                                     │      │   │
│  │  │  ┌──────────┐   ┌──────────┐   ┌──────────┐                   │      │   │
│  │  │  │ LUT[256] │ × │ Linear   │ + │ Bias     │ → phase[0,2π]    │      │   │
│  │  │  │ sigmoid  │   │ interp   │   │ adjust   │                   │      │   │
│  │  │  └──────────┘   └──────────┘   └──────────┘                   │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  │                           │                                              │   │
│  │                           ▼                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  MEAN ACCUMULATOR (Pipelined)                                  │      │   │
│  │  │                                                                │      │   │
│  │  │    Causal Mode:                                                │      │   │
│  │  │    ┌────────┐   ┌────────┐   ┌────────┐                       │      │   │
│  │  │    │cumsum_t│ = │cumsum  │ + │phase_t │                       │      │   │
│  │  │    └────────┘   │  t-1   │   └────────┘                       │      │   │
│  │  │                 └────────┘                                     │      │   │
│  │  │    ┌────────┐   ┌────────┐   ┌────────┐                       │      │   │
│  │  │    │mean_t  │ = │cumsum_t│ / │count_t │  (fixed-point div)   │      │   │
│  │  │    └────────┘   └────────┘   └────────┘                       │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  │                           │                                              │   │
│  │                           ▼                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  CORDIC SIN/COS UNIT (3 iterations pipelined)                  │      │   │
│  │  │                                                                │      │   │
│  │  │  Iteration 0    Iteration 1    Iteration 2    Output          │      │   │
│  │  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    │      │   │
│  │  │  │ CORDIC  │───▶│ CORDIC  │───▶│ CORDIC  │───▶│ sin/cos │    │      │   │
│  │  │  │ Stage 0 │    │ Stage 1 │    │ Stage 2 │    │ output  │    │      │   │
│  │  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘    │      │   │
│  │  │                                                                │      │   │
│  │  │  Latency: 3 cycles, Throughput: 1 result/cycle                │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                                │
│                                ▼                                                │
│  SYNC ITERATION STAGE (Cycle 11-22, 3 iterations × 4 cycles)                   │
│  ════════════════════════════════════════════════════════════                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     PHASE UPDATE LOOP                                    │   │
│  │                                                                          │   │
│  │  for iter in 0..SYNC_STEPS:                                             │   │
│  │    ┌─────────────────────────────────────────────────────────────┐      │   │
│  │    │  Cycle 0: gradient = -N × sin(φᵢ - φ_mean)                  │      │   │
│  │    │  Cycle 1: Δφ = α × gradient                                  │      │   │
│  │    │  Cycle 2: φᵢ_new = φᵢ + Δφ                                   │      │   │
│  │    │  Cycle 3: Update mean (if causal, cumulative)               │      │   │
│  │    └─────────────────────────────────────────────────────────────┘      │   │
│  │                                                                          │   │
│  │  Hardware: 12 parallel gradient units (one per head)                    │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                                │
│                                ▼                                                │
│  VALUE AGGREGATION STAGE (Cycle 23-26)                                          │
│  ══════════════════════════════════════                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     WEIGHTED SUM ENGINE                                  │   │
│  │                                                                          │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  PHASE WEIGHT COMPUTE                                          │      │   │
│  │  │  weight = cos(φᵢ - φ_mean) / temperature                      │      │   │
│  │  │  weight_norm = softmax(weight)  [vector softmax unit]         │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  │                           │                                              │   │
│  │                           ▼                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  WEIGHTED CUMSUM (Causal Mode)                                 │      │   │
│  │  │  V_weighted = V × weight_norm                                  │      │   │
│  │  │  V_cumsum[t] = V_cumsum[t-1] + V_weighted[t]                  │      │   │
│  │  │  V_global[t] = V_cumsum[t] / weight_cumsum[t]                 │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  │                           │                                              │   │
│  │                           ▼                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐      │   │
│  │  │  GATED OUTPUT                                                  │      │   │
│  │  │  gate = sigmoid(W_gate × Q)                                    │      │   │
│  │  │  output = gate × V + (1-gate) × V_global                      │      │   │
│  │  └───────────────────────────────────────────────────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                                │
│                                ▼                                                │
│  OUTPUT STAGE (Cycle 27-30)                                                     │
│  ══════════════════════════════                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │   │
│  │  │  OUT_PROJ    │───▶│  LAYER_NORM  │───▶│  RESIDUAL    │               │   │
│  │  │  16×16 Array │    │  Vectorized  │    │  ADD         │               │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘               │   │
│  │                                                │                         │   │
│  │                                                ▼                         │   │
│  │                                          OUTPUT BUFFER                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  TOTAL LATENCY: 30 cycles @ 1GHz = 30ns per token                              │
│  THROUGHPUT: 12 heads × 64 dims × 1GHz = 768 GB/s internal                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.1.2 Processing Element (PE) Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SYSTOLIC PROCESSING ELEMENT (PE)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                    weight_in ────────────────────────┐                          │
│                         │                            │                          │
│                         ▼                            │                          │
│  activation_in ──▶ ┌─────────┐    ┌─────────┐       │                          │
│                    │   MUL   │───▶│   ACC   │───────┼──▶ activation_out        │
│                    │  FP16   │    │  FP32   │       │                          │
│                    └─────────┘    └────┬────┘       │                          │
│                                        │            │                          │
│                                        ▼            ▼                          │
│                                   ┌─────────┐  ┌─────────┐                     │
│                                   │  REG    │  │  REG    │                     │
│                                   │ partial │  │ weight  │                     │
│                                   └────┬────┘  └────┬────┘                     │
│                                        │            │                          │
│                                        ▼            ▼                          │
│                                   partial_out   weight_out                     │
│                                                                                 │
│  PE Specifications:                                                             │
│  ├─ Multiply: FP16 × FP16 = FP32 (1 cycle)                                     │
│  ├─ Accumulate: FP32 + FP32 = FP32 (1 cycle, fused)                           │
│  ├─ Register: 32-bit weight, 32-bit partial sum                                │
│  ├─ Area: ~2,000 gates (0.002 mm² @ 5nm)                                       │
│  └─ Power: ~50 μW @ 1GHz                                                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.1.3 CORDIC Unit for Trigonometric Functions

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CORDIC SINE/COSINE UNIT                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Input: θ (angle in radians, 16-bit fixed-point)                               │
│  Output: sin(θ), cos(θ) (16-bit fixed-point)                                   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 0 (Quadrant Reduction)                                            │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  if θ > π/2:  θ' = π - θ, negate_cos = 1                        │   │   │
│  │  │  if θ > π:    θ' = θ - π, negate_sin = 1, negate_cos = 1        │   │   │
│  │  │  if θ > 3π/2: θ' = 2π - θ, negate_sin = 1                       │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CORDIC ITERATION (Unrolled, 16 stages)                                 │   │
│  │                                                                          │   │
│  │  Constants: arctan_lut[16] = {45°, 26.57°, 14.04°, 7.13°, ...}          │   │
│  │             K = 0.6073 (CORDIC gain, precomputed)                        │   │
│  │                                                                          │   │
│  │  for i in 0..15:                                                         │   │
│  │    ┌────────────────────────────────────────────────────────────┐       │   │
│  │    │  σ = (z >= 0) ? +1 : -1                                    │       │   │
│  │    │  x_new = x - σ × (y >> i)      // Shift-add only          │       │   │
│  │    │  y_new = y + σ × (x >> i)      // No multipliers          │       │   │
│  │    │  z_new = z - σ × arctan_lut[i]                            │       │   │
│  │    └────────────────────────────────────────────────────────────┘       │   │
│  │                                                                          │   │
│  │  Pipeline: 4 stages (4 iterations each)                                 │   │
│  │  Latency: 4 cycles                                                       │   │
│  │  Throughput: 1 result/cycle (after pipeline fill)                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  OUTPUT STAGE                                                            │   │
│  │  cos(θ) = K × x_final × (negate_cos ? -1 : 1)                           │   │
│  │  sin(θ) = K × y_final × (negate_sin ? -1 : 1)                           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Resource Usage:                                                                │
│  ├─ Adders: 32 (16 for x, 16 for y)                                           │
│  ├─ Shifters: 32 (barrel shifters, 16-bit)                                    │
│  ├─ LUT: 16 × 16-bit (arctan values)                                          │
│  ├─ Comparators: 16                                                            │
│  ├─ Area: ~8,000 gates                                                         │
│  └─ Power: ~200 μW @ 1GHz                                                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Pipeline Architecture

#### 12.2.1 Full Frame Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FRAME PROCESSING PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Stage    │ Unit │ Cycles │ Description                                        │
│  ─────────┼──────┼────────┼─────────────────────────────────────────────────   │
│  S0       │ DMA  │ 0-100  │ Frame DMA from HBM3 to input buffer               │
│  S1       │ PEU  │ 0-200  │ Patch extraction (overlapped with DMA)            │
│  S2       │ PEU  │ 200-400│ Patch embedding (16×16 → 768-dim)                 │
│  S3       │ PAU  │ 0-30   │ Layer 0 phase attention (per-token)               │
│  S4       │ PAU  │ 30-60  │ Layer 1 phase attention                           │
│  ...      │ ...  │ ...    │ ...                                                │
│  S14      │ PAU  │ 330-360│ Layer 11 phase attention                          │
│  S15      │ TCU  │ 360-365│ Temporal context update                           │
│  S16      │ OPU  │ 365-375│ Ontology projection (768 → 124)                   │
│  S17      │ SDU  │ 375-380│ State delta computation                           │
│  S18      │ DMA  │ 380-385│ Output DMA to host                                │
│                                                                                 │
│  PIPELINE DIAGRAM (4K frame, 32,400 tokens):                                   │
│                                                                                 │
│  Time(ms) 0    1    2    3    4    5    6                                      │
│           │    │    │    │    │    │    │                                      │
│  Frame 0: ╔════╗                                                               │
│    DMA    ║████║                                                               │
│    PEU    ╚════╬════╗                                                          │
│               ║████║                                                           │
│    PAU L0-11      ╠════════════╗                                               │
│                   ║████████████║                                               │
│    TCU/OPU/SDU               ╠═╗                                              │
│                               ║█║                                              │
│    OUT                         ╠═╗                                             │
│                                ║█║                                             │
│                                                                                 │
│  Frame 1: ────╔════╗                                                           │
│    DMA        ║████║                                                           │
│    PEU        ╚════╬════╗                                                      │
│                   ║████║                                                       │
│    PAU L0-11          ╠════════════╗                                           │
│                       ║████████████║                                           │
│                                                                                 │
│  Pipeline Depth: 6 stages                                                       │
│  Frame Latency: 5.5 ms (first frame)                                           │
│  Frame Throughput: 4.5 ms/frame = 222 fps (sustained)                          │
│  Actual Target: 60 fps (with 3× margin)                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.2.2 Token-Level Pipeline (Within PAU Layer)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      TOKEN PIPELINE (Single PAU Layer)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Cycle:  0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20       │
│          │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │        │
│  Token 0:                                                                       │
│    FETCH ██                                                                     │
│    Q_PRJ    ████                                                               │
│    K_PRJ    ████                                                               │
│    V_PRJ    ████                                                               │
│    PHASE       ████                                                            │
│    SYNC0          ████                                                         │
│    SYNC1              ████                                                     │
│    SYNC2                  ████                                                 │
│    WEIGHT                     ████                                             │
│    V_AGG                          ████                                         │
│    OUT_PRJ                            ████                                     │
│    LNORM                                  ██                                   │
│    WRITE                                    ██                                 │
│                                                                                 │
│  Token 1:                                                                       │
│    FETCH    ██                                                                 │
│    Q_PRJ       ████                                                            │
│    ...            (shifted by 2 cycles)                                        │
│                                                                                 │
│  Token 2:                                                                       │
│    FETCH       ██                                                              │
│    ...                                                                          │
│                                                                                 │
│  Pipeline Properties:                                                           │
│  ├─ Initiation Interval (II): 2 cycles                                         │
│  ├─ Pipeline Depth: 20 cycles                                                  │
│  ├─ Throughput: 1 token every 2 cycles                                         │
│  ├─ 32,400 tokens: 64,800 cycles = 64.8 μs @ 1GHz                             │
│  └─ 12 layers: 64.8 × 12 = 778 μs per frame                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Clock Domain Architecture

#### 12.3.1 Clock Tree

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CLOCK DOMAIN ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                           ┌─────────────────────┐                               │
│                           │   EXTERNAL REFCLK   │                               │
│                           │   100 MHz (±50ppm)  │                               │
│                           └──────────┬──────────┘                               │
│                                      │                                          │
│                                      ▼                                          │
│                           ┌─────────────────────┐                               │
│                           │   MAIN PLL (APLL)   │                               │
│                           │   VCO: 4 GHz        │                               │
│                           │   Jitter: <1ps RMS  │                               │
│                           └──────────┬──────────┘                               │
│                                      │                                          │
│          ┌───────────────┬───────────┼───────────┬───────────┐                 │
│          │               │           │           │           │                 │
│          ▼               ▼           ▼           ▼           ▼                 │
│  ┌───────────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │  CLK_CORE     │ │ CLK_HBM   │ │ CLK_PCIE  │ │ CLK_NOC   │ │ CLK_ONTO  │    │
│  │  1.0 GHz      │ │ 1.6 GHz   │ │ 500 MHz   │ │ 800 MHz   │ │ Variable  │    │
│  │               │ │           │ │           │ │           │ │ 1Hz-10kHz │    │
│  │  PAU, OPU,    │ │ HBM3 PHY  │ │ PCIe 5.0  │ │ NoC Fabric│ │ 12 Layer  │    │
│  │  SDU, TCU     │ │           │ │ Controller│ │           │ │ Clocks    │    │
│  └───────────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
│                                                                                 │
│                                                                                 │
│  ONTOLOGICAL LAYER CLOCK GENERATION:                                           │
│  ═══════════════════════════════════                                           │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    CSAC (Chip-Scale Atomic Clock)                        │   │
│  │                    10 MHz, ±100ps stability                              │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    FRACTIONAL-N SYNTHESIZER                              │   │
│  │                    (AD9545 or equivalent)                                │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│     ┌────────┬────────┬────────┬────────┬────────┬────────┐                   │
│     ▼        ▼        ▼        ▼        ▼        ▼        ▼                   │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐                    │
│  │O1 CLK││O2 CLK││O3 CLK││O4 CLK││...   ││O11CLK││O12CLK│                    │
│  │10kHz ││5kHz  ││2kHz  ││1kHz  ││      ││5Hz   ││1Hz   │                    │
│  │÷1    ││÷2    ││÷5    ││÷10   ││      ││÷2000 ││÷10000│                    │
│  └──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.3.2 Clock Domain Crossing (CDC)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     CLOCK DOMAIN CROSSING SPECIFICATION                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CDC TYPE 1: Core ↔ HBM (1.0 GHz ↔ 1.6 GHz)                                    │
│  ═══════════════════════════════════════════                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  CLK_CORE (1 GHz)                     CLK_HBM (1.6 GHz)                  │   │
│  │       │                                     │                            │   │
│  │       ▼                                     ▼                            │   │
│  │  ┌─────────┐    ┌─────────────────┐    ┌─────────┐                      │   │
│  │  │  DATA   │───▶│  ASYNC FIFO     │───▶│  DATA   │                      │   │
│  │  │  OUT    │    │  Depth: 16      │    │  IN     │                      │   │
│  │  └─────────┘    │  Gray-coded ptr │    └─────────┘                      │   │
│  │                 │  2-FF sync      │                                      │   │
│  │                 └─────────────────┘                                      │   │
│  │                                                                          │   │
│  │  Latency: 3-5 cycles (destination clock)                                │   │
│  │  Throughput: Min(1.0, 1.6) = 1.0 GHz effective                          │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  CDC TYPE 2: Core ↔ Ontology (1.0 GHz ↔ 1Hz-10kHz)                            │
│  ═════════════════════════════════════════════════                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Problem: Extreme ratio (up to 1,000,000:1)                             │   │
│  │  Solution: Handshake protocol with pulse synchronizers                   │   │
│  │                                                                          │   │
│  │  CLK_CORE (1 GHz)                     CLK_ONTO (variable)               │   │
│  │       │                                     │                            │   │
│  │       ▼                                     ▼                            │   │
│  │  ┌─────────┐    ┌─────────────────┐    ┌─────────┐                      │   │
│  │  │  REQ    │───▶│  PULSE SYNC     │───▶│  REQ    │                      │   │
│  │  │  GEN    │    │  (toggle-based) │    │  DETECT │                      │   │
│  │  └─────────┘    └─────────────────┘    └─────────┘                      │   │
│  │       ▲                                     │                            │   │
│  │       │         ┌─────────────────┐         │                            │   │
│  │  ┌─────────┐    │  PULSE SYNC     │    ┌────┴────┐                      │   │
│  │  │  ACK    │◀───│  (toggle-based) │◀───│  ACK    │                      │   │
│  │  │  DETECT │    └─────────────────┘    │  GEN    │                      │   │
│  │  └─────────┘                           └─────────┘                      │   │
│  │                                                                          │   │
│  │  Protocol:                                                               │   │
│  │  1. Core asserts REQ (toggle)                                           │   │
│  │  2. Onto detects REQ edge after 2-FF sync                              │   │
│  │  3. Onto processes, asserts ACK (toggle)                                │   │
│  │  4. Core detects ACK, knows transfer complete                           │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  CDC TYPE 3: PCIe ↔ Core (500 MHz ↔ 1.0 GHz)                                  │
│  ═══════════════════════════════════════════                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Standard async FIFO with credit-based flow control                     │   │
│  │  FIFO Depth: 256 entries (for PCIe burst absorption)                    │   │
│  │  Credit return path: 2-FF synchronized                                   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  CDC VERIFICATION:                                                              │
│  ═════════════════                                                              │
│  • All CDC paths identified in SDC constraints                                 │
│  • Formal CDC verification with Cadence Conformal/Synopsys SpyGlass           │
│  • MTBF calculation for all synchronizers: >100 years                          │
│  • No combinational paths crossing clock domains                               │
│  • Gray-coded pointers for all async FIFOs                                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Power Management Architecture

#### 12.4.1 Power Domains

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         POWER DOMAIN ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        VDD_CORE (0.75V nominal)                          │   │
│  │                                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │     PAU     │  │     OPU     │  │     SDU     │  │     TCU     │    │   │
│  │  │   35W typ   │  │   2W typ    │  │   1W typ    │  │   0.5W typ  │    │   │
│  │  │             │  │             │  │             │  │             │    │   │
│  │  │  [DVS:      │  │  [DVS:      │  │  [DVS:      │  │  [Always-on]│    │   │
│  │  │  0.65-0.85V]│  │  0.65-0.85V]│  │  0.65-0.85V]│  │             │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  │                                                                          │   │
│  │  Power gating: Per-layer granularity (12 switches)                      │   │
│  │  Retention: SRAM in TCU always powered                                   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        VDD_HBM (1.1V nominal)                            │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                    HBM3 PHY + Controller                         │    │   │
│  │  │                    20W typ (activity dependent)                  │    │   │
│  │  │                                                                  │    │   │
│  │  │  [Partial power-down: Per-channel, 8 channels]                  │    │   │
│  │  │  [Self-refresh mode: <1W]                                        │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        VDD_IO (1.8V / 1.2V)                              │   │
│  │                                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │   │
│  │  │  PCIe PHY   │  │  MIPI CSI   │  │  GPIO/MISC  │                      │   │
│  │  │  5W typ     │  │  1W typ     │  │  0.5W typ   │                      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                      │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        VDD_PLL (Analog, 1.8V)                            │   │
│  │                                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │   │
│  │  │  MAIN PLL   │  │  FRAC-N PLL │  │    CSAC     │                      │   │
│  │  │  200mW      │  │  150mW      │  │  (external) │                      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                      │   │
│  │                                                                          │   │
│  │  Always-on (no power gating for timing integrity)                       │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.4.2 Dynamic Voltage and Frequency Scaling (DVFS)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DVFS OPERATING POINTS                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  PERFORMANCE MODE (P0) - Maximum throughput                               │  │
│  │  ────────────────────────────────────────────                            │  │
│  │  VDD_CORE: 0.85V    Frequency: 1.2 GHz    Power: 75W                     │  │
│  │  Use case: 4K @ 60fps, 8K @ 15fps                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  BALANCED MODE (P1) - Default operation                                   │  │
│  │  ────────────────────────────────────────                                │  │
│  │  VDD_CORE: 0.75V    Frequency: 1.0 GHz    Power: 45W                     │  │
│  │  Use case: 4K @ 30fps, 1080p @ 60fps                                     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  EFFICIENCY MODE (P2) - Power optimized                                   │  │
│  │  ────────────────────────────────────────                                │  │
│  │  VDD_CORE: 0.68V    Frequency: 800 MHz    Power: 25W                     │  │
│  │  Use case: 1080p @ 30fps, 720p @ 60fps                                   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  LOW POWER MODE (P3) - Minimum active power                               │  │
│  │  ──────────────────────────────────────────                              │  │
│  │  VDD_CORE: 0.60V    Frequency: 400 MHz    Power: 10W                     │  │
│  │  Use case: 720p @ 15fps, standby with context                            │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  SLEEP MODE (P4) - Retention only                                         │  │
│  │  ────────────────────────────────                                        │  │
│  │  VDD_CORE: 0.50V (retention)    Frequency: 0    Power: 0.5W              │  │
│  │  TCU SRAM retained, all else power-gated                                 │  │
│  │  Wake latency: 100 μs                                                    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  DVFS TRANSITION TIMING:                                                        │
│  ═══════════════════════                                                        │
│  • Voltage ramp: 10 mV/μs (controlled by PMIC)                                 │
│  • P0 → P3: 25 mV / 10 mV/μs = 2.5 μs (voltage)                               │
│  • Frequency change: <1 μs (PLL relock)                                        │
│  • Total P-state transition: <10 μs                                            │
│                                                                                 │
│  DVFS CONTROLLER FSM:                                                           │
│  ════════════════════                                                           │
│  ┌─────────┐   thermal_alert   ┌─────────┐                                     │
│  │   P0    │──────────────────▶│   P1    │                                     │
│  │  (HOT)  │◀──────────────────│         │                                     │
│  └────┬────┘   temp < 80°C     └────┬────┘                                     │
│       │                             │                                           │
│       │ temp > 95°C                 │ idle > 10ms                              │
│       │                             ▼                                           │
│       │                        ┌─────────┐                                     │
│       │                        │   P2    │                                     │
│       │                        │         │                                     │
│       │                        └────┬────┘                                     │
│       │                             │                                           │
│       │                             │ idle > 100ms                             │
│       │                             ▼                                           │
│       │                        ┌─────────┐                                     │
│       └───────────────────────▶│   P3    │                                     │
│            emergency           └────┬────┘                                     │
│            throttle                 │                                           │
│                                     │ idle > 1s                                │
│                                     ▼                                           │
│                                ┌─────────┐                                     │
│                                │   P4    │                                     │
│                                │ (SLEEP) │                                     │
│                                └─────────┘                                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.4.3 Clock Gating Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CLOCK GATING HIERARCHY                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Level 0: Global Clock Gate (GCG)                                              │
│  ════════════════════════════════                                               │
│  • Controlled by GCR_CLK_CTRL register                                         │
│  • Gates entire clock tree except always-on domains                            │
│  • Used for chip-level sleep                                                    │
│                                                                                 │
│  Level 1: Unit Clock Gate (UCG)                                                │
│  ════════════════════════════════                                               │
│  • Per-unit enable: PEU_EN, PAU_EN, OPU_EN, SDU_EN, TCU_EN                     │
│  • Automatic idle detection (no transactions for N cycles)                     │
│  • Software override via register                                               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  UNIT CLOCK GATE CELL (ICG - Integrated Clock Gate)                      │   │
│  │                                                                          │   │
│  │                enable                                                    │   │
│  │                  │                                                       │   │
│  │                  ▼                                                       │   │
│  │  clk_in ──▶ ┌─────────┐    ┌─────────┐                                  │   │
│  │             │  LATCH   │───▶│   AND   │───▶ clk_out                     │   │
│  │             │ (neg edge)│    │         │                                 │   │
│  │             └─────────┘    └─────────┘                                  │   │
│  │                               ▲                                          │   │
│  │                               │                                          │   │
│  │                            clk_in                                        │   │
│  │                                                                          │   │
│  │  Glitch-free clock gating (latch captures enable on falling edge)       │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Level 2: Sub-Unit Clock Gate                                                  │
│  ════════════════════════════                                                   │
│  • Per-head gating in PAU (12 independent gates)                               │
│  • Per-layer gating in ontology processing                                     │
│  • SRAM bank clock gating                                                       │
│                                                                                 │
│  Level 3: Fine-Grain Clock Gating (Synthesis)                                  │
│  ═══════════════════════════════════════════════                                │
│  • Automatic insertion by synthesis tool                                        │
│  • Register-level: gate clock when register holds value                        │
│  • Threshold: gate if idle > 2 cycles                                          │
│                                                                                 │
│  ESTIMATED POWER SAVINGS:                                                       │
│  ═══════════════════════                                                        │
│  │ Gating Level │ % of Dynamic Power Saved │ Condition                    │   │
│  │──────────────│──────────────────────────│─────────────────────────────│   │
│  │ Level 0      │ 95%                      │ Full sleep                   │   │
│  │ Level 1      │ 60-80%                   │ Idle units                   │   │
│  │ Level 2      │ 30-50%                   │ Partial activity             │   │
│  │ Level 3      │ 15-25%                   │ Always active (automatic)    │   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.5 Design for Test (DFT)

#### 12.5.1 Scan Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            SCAN TEST ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  SCAN CHAIN CONFIGURATION:                                                      │
│  ═════════════════════════                                                      │
│  • Total flip-flops: ~2M                                                        │
│  • Scan chains: 256 (8K FF per chain)                                          │
│  • Compression ratio: 64:1 (EDT/DFTMAX)                                        │
│  • Effective channels: 4 input, 4 output                                       │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      SCAN COMPRESSION                                    │   │
│  │                                                                          │   │
│  │  TEST_SI[3:0] ──▶ ┌─────────────┐    ┌─────────────┐                    │   │
│  │                   │  DECOMPRESSOR│───▶│  256 SCAN   │                    │   │
│  │                   │  (LFSR-based)│    │   CHAINS    │                    │   │
│  │                   └─────────────┘    └──────┬──────┘                    │   │
│  │                                             │                            │   │
│  │                                             ▼                            │   │
│  │                   ┌─────────────┐    ┌─────────────┐                    │   │
│  │  TEST_SO[3:0] ◀──│  COMPRESSOR │◀───│   MISR      │                    │   │
│  │                   │  (XOR tree) │    │  (signature)│                    │   │
│  │                   └─────────────┘    └─────────────┘                    │   │
│  │                                                                          │   │
│  │  Scan shift frequency: 100 MHz                                          │   │
│  │  Capture frequency: 500 MHz (at-speed)                                   │   │
│  │  Pattern count: ~5000 (target 98% stuck-at coverage)                    │   │
│  │  Test time: ~500ms per chip                                              │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  SCAN PARTITIONING:                                                             │
│  ══════════════════                                                             │
│  ┌────────────────────┬────────────┬──────────────┐                            │
│  │ Domain             │ Chains     │ Coverage     │                            │
│  ├────────────────────┼────────────┼──────────────┤                            │
│  │ PAU (core logic)   │ 128        │ 98%          │                            │
│  │ PEU                │ 32         │ 97%          │                            │
│  │ OPU                │ 16         │ 98%          │                            │
│  │ SDU                │ 16         │ 98%          │                            │
│  │ TCU                │ 16         │ 97%          │                            │
│  │ NoC/Control        │ 48         │ 95%          │                            │
│  └────────────────────┴────────────┴──────────────┘                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.5.2 Built-In Self-Test (BIST)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BIST ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  MEMORY BIST (MBIST):                                                           │
│  ═══════════════════                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  MBIST Controller (shared, time-multiplexed)                            │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │    │   │
│  │  │  │ Address  │──▶│ Data     │──▶│ SRAM     │──▶│ Compare  │     │    │   │
│  │  │  │ Generator│   │ Generator│   │ Wrapper  │   │ (MISR)   │     │    │   │
│  │  │  │ (March)  │   │ (LFSR)   │   │          │   │          │     │    │   │
│  │  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │    │   │
│  │  │                                                                  │    │   │
│  │  │  Algorithms: March C-, March LR, Checkerboard                   │    │   │
│  │  │  Repair: Built-in redundancy analysis + fuse programming        │    │   │
│  │  │                                                                  │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  SRAM Instances:                                                         │   │
│  │  ┌────────────────────┬────────────┬──────────────┬────────────────┐    │   │
│  │  │ Memory             │ Size       │ Redundancy   │ MBIST Time     │    │   │
│  │  ├────────────────────┼────────────┼──────────────┼────────────────┤    │   │
│  │  │ PAU Input Buffer   │ 64KB       │ 1 row/col    │ 50ms           │    │   │
│  │  │ PAU Weight Cache   │ 512KB      │ 2 row/col    │ 400ms          │    │   │
│  │  │ TCU Phase Buffer   │ 32KB       │ 1 row/col    │ 25ms           │    │   │
│  │  │ OPU Accumulators   │ 16KB       │ 1 row/col    │ 15ms           │    │   │
│  │  │ NoC Buffers        │ 128KB      │ 1 row/col    │ 100ms          │    │   │
│  │  └────────────────────┴────────────┴──────────────┴────────────────┘    │   │
│  │                                                                          │   │
│  │  Total MBIST time: ~600ms (parallel execution)                          │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  LOGIC BIST (LBIST):                                                           │
│  ═══════════════════                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  • PRPG (Pseudo-Random Pattern Generator): 32-bit LFSR                  │   │
│  │  • MISR (Multiple-Input Signature Register): 32-bit                     │   │
│  │  • Patterns: 10M cycles                                                  │   │
│  │  • Coverage: ~70% stuck-at (supplement to scan)                         │   │
│  │  • Use case: In-field testing, power-on self-test                       │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  PHASE ATTENTION BIST (PA-BIST) - Custom:                                      │
│  ═════════════════════════════════════════                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Functional verification of phase synchronization:                       │   │
│  │                                                                          │   │
│  │  Test 1: Phase convergence                                               │   │
│  │    • Initialize random phases                                            │   │
│  │    • Run 10 sync iterations                                              │   │
│  │    • Check: variance(phases) < threshold                                 │   │
│  │    • Expected: All phases converge to mean ± 0.1 rad                    │   │
│  │                                                                          │   │
│  │  Test 2: CORDIC accuracy                                                 │   │
│  │    • Input: Known angles from ROM                                        │   │
│  │    • Output: Compare sin/cos to golden values                           │   │
│  │    • Tolerance: ±1 LSB (16-bit)                                         │   │
│  │                                                                          │   │
│  │  Test 3: Temporal accumulator                                            │   │
│  │    • Feed known phase sequence                                           │   │
│  │    • Verify cumsum and mean calculations                                 │   │
│  │    • Check TCU state after N frames                                      │   │
│  │                                                                          │   │
│  │  PA-BIST time: ~10ms                                                     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.5.3 JTAG and Debug Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         JTAG / DEBUG ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  JTAG TAP Controller (IEEE 1149.1):                                            │
│  ══════════════════════════════════                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  TCK ───▶ ┌─────────────┐                                               │   │
│  │  TMS ───▶ │  TAP FSM    │                                               │   │
│  │  TDI ───▶ │             │───▶ TDO                                       │   │
│  │  TRST ──▶ │  (16 state) │                                               │   │
│  │           └──────┬──────┘                                               │   │
│  │                  │                                                       │   │
│  │    ┌─────────────┼─────────────┬─────────────┬─────────────┐            │   │
│  │    ▼             ▼             ▼             ▼             ▼            │   │
│  │  ┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐               │   │
│  │  │IDCODE│     │BYPASS│     │SCAN │     │MBIST│     │DEBUG│               │   │
│  │  │     │     │     │     │CHAIN│     │CTRL │     │ACCESS               │   │
│  │  └─────┘     └─────┘     └─────┘     └─────┘     └─────┘               │   │
│  │                                                                          │   │
│  │  Instructions:                                                           │   │
│  │  • IDCODE (0x01): Read chip ID                                          │   │
│  │  • BYPASS (0xFF): Bypass mode                                           │   │
│  │  • EXTEST (0x00): Boundary scan                                         │   │
│  │  • SCAN_EN (0x02): Enable scan mode                                     │   │
│  │  • MBIST_EN (0x03): Enable memory BIST                                  │   │
│  │  • DEBUG (0x04): Debug register access                                  │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  DEBUG ACCESS PORT (DAP):                                                       │
│  ═════════════════════════                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Features:                                                               │   │
│  │  • Register read/write via JTAG                                         │   │
│  │  • Real-time trace buffer (64KB circular)                               │   │
│  │  • Hardware breakpoints (8 address comparators)                         │   │
│  │  • Performance counters (32 × 48-bit)                                   │   │
│  │  • Waveform capture (trigger + 1K samples)                              │   │
│  │                                                                          │   │
│  │  Performance Counters:                                                   │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │ Counter          │ Description                                  │     │   │
│  │  ├────────────────────────────────────────────────────────────────┤     │   │
│  │  │ CYCLE_COUNT      │ Total clock cycles                          │     │   │
│  │  │ TOKEN_COUNT      │ Tokens processed                            │     │   │
│  │  │ FRAME_COUNT      │ Frames processed                            │     │   │
│  │  │ STALL_CYCLES     │ Pipeline stalls                             │     │   │
│  │  │ HBM_READ_BYTES   │ HBM read bandwidth                          │     │   │
│  │  │ HBM_WRITE_BYTES  │ HBM write bandwidth                         │     │   │
│  │  │ CACHE_HIT        │ Weight cache hits                           │     │   │
│  │  │ CACHE_MISS       │ Weight cache misses                         │     │   │
│  │  │ PHASE_SYNC_ITERS │ Total sync iterations                       │     │   │
│  │  │ COHERENCE_SUM    │ Accumulated coherence                       │     │   │
│  │  │ ...              │ (22 more counters)                          │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.6 Physical Design Constraints

#### 12.6.1 Floorplan

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CHIP FLOORPLAN (5nm)                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Die Size: 12mm × 12mm = 144 mm²                                               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           PAD RING (I/O)                                 │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │   │
│  │  │                                                                    │  │   │
│  │  │   ┌─────────────────────────────────────────────────────────────┐ │  │   │
│  │  │   │                    HBM3 PHY (TOP)                           │ │  │   │
│  │  │   │                    8 channels, 2.5mm × 10mm                 │ │  │   │
│  │  │   └─────────────────────────────────────────────────────────────┘ │  │   │
│  │  │                                                                    │  │   │
│  │  │   ┌─────────────┐  ┌─────────────────────────────┐  ┌──────────┐ │  │   │
│  │  │   │   PCIe      │  │                             │  │  MIPI    │ │  │   │
│  │  │   │   PHY       │  │          PAU ARRAY          │  │  CSI     │ │  │   │
│  │  │   │             │  │                             │  │  PHY     │ │  │   │
│  │  │   │   1mm ×     │  │    12 Heads × 16×16 PE     │  │          │ │  │   │
│  │  │   │   4mm       │  │                             │  │  0.5mm × │ │  │   │
│  │  │   │             │  │    6mm × 6mm = 36 mm²      │  │  3mm     │ │  │   │
│  │  │   │             │  │                             │  │          │ │  │   │
│  │  │   │             │  │    (50% of core area)       │  │          │ │  │   │
│  │  │   │             │  │                             │  │          │ │  │   │
│  │  │   └─────────────┘  └─────────────────────────────┘  └──────────┘ │  │   │
│  │  │                                                                    │  │   │
│  │  │   ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │  │   │
│  │  │   │    PEU      │  │    TCU     │  │    OPU     │  │   SDU    │ │  │   │
│  │  │   │             │  │            │  │            │  │          │ │  │   │
│  │  │   │  2mm × 2mm  │  │ 1mm × 1mm  │  │ 1mm × 1mm  │  │ 0.5mm ×  │ │  │   │
│  │  │   │  = 4 mm²    │  │ = 1 mm²    │  │ = 1 mm²    │  │ 0.5mm    │ │  │   │
│  │  │   │             │  │            │  │            │  │          │ │  │   │
│  │  │   └─────────────┘  └────────────┘  └────────────┘  └──────────┘ │  │   │
│  │  │                                                                    │  │   │
│  │  │   ┌─────────────────────────────────────────────────────────────┐ │  │   │
│  │  │   │                      NoC + CONTROL                          │ │  │   │
│  │  │   │                      2mm × 8mm = 16 mm²                     │ │  │   │
│  │  │   └─────────────────────────────────────────────────────────────┘ │  │   │
│  │  │                                                                    │  │   │
│  │  │   ┌───────────────────────────────────────────────────────────┐   │  │   │
│  │  │   │  PLL │ CSAC I/F │ PMIC I/F │ FUSE │ JTAG │ MISC          │   │  │   │
│  │  │   │  0.5mm × 8mm = 4 mm²                                      │   │  │   │
│  │  │   └───────────────────────────────────────────────────────────┘   │  │   │
│  │  │                                                                    │  │   │
│  │  └───────────────────────────────────────────────────────────────────┘  │   │
│  │                           PAD RING (I/O)                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  AREA BREAKDOWN:                                                                │
│  ┌────────────────────┬────────────┬──────────────┐                            │
│  │ Block              │ Area (mm²) │ % of Die     │                            │
│  ├────────────────────┼────────────┼──────────────┤                            │
│  │ PAU Array          │ 36         │ 25%          │                            │
│  │ HBM3 PHY           │ 25         │ 17%          │                            │
│  │ NoC + Control      │ 16         │ 11%          │                            │
│  │ PCIe PHY           │ 4          │ 3%           │                            │
│  │ PEU                │ 4          │ 3%           │                            │
│  │ Analog/PLL/Misc    │ 4          │ 3%           │                            │
│  │ MIPI PHY           │ 1.5        │ 1%           │                            │
│  │ TCU                │ 1          │ 0.7%         │                            │
│  │ OPU                │ 1          │ 0.7%         │                            │
│  │ SDU                │ 0.25       │ 0.2%         │                            │
│  │ Pad Ring           │ 40         │ 28%          │                            │
│  │ Whitespace/Routing │ 11.25      │ 8%           │                            │
│  ├────────────────────┼────────────┼──────────────┤                            │
│  │ TOTAL              │ 144        │ 100%         │                            │
│  └────────────────────┴────────────┴──────────────┘                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.6.2 Power Grid

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              POWER GRID DESIGN                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  POWER DELIVERY NETWORK (PDN):                                                  │
│  ═════════════════════════════                                                  │
│                                                                                 │
│  Package Level:                                                                 │
│  • Flip-chip BGA (45mm × 45mm, 2500 balls)                                     │
│  • VDD balls: 400 (distributed)                                                 │
│  • VSS balls: 600 (ground mesh)                                                 │
│  • Signal balls: 1500                                                           │
│                                                                                 │
│  On-Die Power Grid (Cross-Section):                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  M15 (Top) ════════════════════════════════════════════  VDD (10μm)     │   │
│  │  M14       ════════════════════════════════════════════  VSS (10μm)     │   │
│  │  M13       ═══════════════════════════════════════════   VDD (5μm)      │   │
│  │  M12       ═══════════════════════════════════════════   VSS (5μm)      │   │
│  │  M11       ────────────────────────────────────────────  Signal         │   │
│  │  ...                                                                     │   │
│  │  M1        ────────────────────────────────────────────  Local routing  │   │
│  │                                                                          │   │
│  │  Power mesh pitch: 20μm (VDD), 20μm (VSS)                               │   │
│  │  IR drop budget: <5% (37.5mV @ 0.75V)                                   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  DECOUPLING CAPACITORS:                                                         │
│  ═══════════════════════                                                        │
│  • MIM caps (M13-M14): 50 nF/mm² → ~5 μF total                                 │
│  • MOS caps (in whitespace): ~10 μF total                                      │
│  • Package caps: 100 μF (external MLCC)                                        │
│  • Target impedance: <1 mΩ @ 100 MHz                                           │
│                                                                                 │
│  ELECTROMIGRATION:                                                              │
│  ═════════════════                                                              │
│  • Max current density: 2 MA/cm² (DC), 10 MA/cm² (AC)                         │
│  • Power stripe width: Min 2μm for 1mA DC                                      │
│  • Vias: 2× redundancy on power connections                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 12.6.3 Thermal Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             THERMAL ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  THERMAL MAP (Estimated @ 75W TDP):                                            │
│  ══════════════════════════════════                                             │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░  HBM PHY (55°C)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓  PAU ARRAY  ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓   (85°C)    ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │   │
│  │                                                                          │   │
│  │    Legend: ░ = 45-55°C, ▒ = 55-70°C, ▓ = 70-85°C, █ = >85°C            │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  THERMAL SENSORS:                                                               │
│  ═════════════════                                                              │
│  • 16 on-die thermal diodes (4×4 grid)                                         │
│  • Resolution: 0.5°C                                                            │
│  • Accuracy: ±3°C                                                               │
│  • Sample rate: 1 kHz                                                           │
│                                                                                 │
│  THERMAL THROTTLING:                                                            │
│  ════════════════════                                                           │
│  ┌────────────────────┬────────────────────────────────────────────────────┐   │
│  │ Temperature        │ Action                                              │   │
│  ├────────────────────┼────────────────────────────────────────────────────┤   │
│  │ T < 80°C           │ Normal operation (P0-P1)                           │   │
│  │ 80°C ≤ T < 90°C    │ Throttle to P2, reduce HBM bandwidth               │   │
│  │ 90°C ≤ T < 100°C   │ Throttle to P3, disable idle units                 │   │
│  │ 100°C ≤ T < 105°C  │ Emergency throttle, minimum frequency              │   │
│  │ T ≥ 105°C          │ Thermal shutdown (THERMTRIP#)                      │   │
│  └────────────────────┴────────────────────────────────────────────────────┘   │
│                                                                                 │
│  COOLING SOLUTION:                                                              │
│  ═════════════════                                                              │
│  • Package: Flip-chip with IHS (Integrated Heat Spreader)                      │
│  • TIM1: Indium solder (0.5 W/cm²·K)                                           │
│  • IHS: Copper, 25mm × 25mm × 2mm                                              │
│  • TIM2: High-performance thermal paste (10 W/m·K)                             │
│  • Heatsink: Aluminum fin stack + fan (passive option available)               │
│  • Thermal resistance: θja < 0.5°C/W (with active cooling)                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.7 Signal Integrity

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SIGNAL INTEGRITY SPECIFICATIONS                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  HIGH-SPEED INTERFACE REQUIREMENTS:                                             │
│  ═══════════════════════════════════                                            │
│                                                                                 │
│  HBM3 Interface:                                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ Parameter              │ Specification        │ Notes                   │    │
│  ├────────────────────────────────────────────────────────────────────────┤    │
│  │ Data rate              │ 6.4 Gbps/pin        │ DDR, 3.2 GHz clock      │    │
│  │ Eye height             │ > 100 mV            │ At receiver             │    │
│  │ Eye width              │ > 0.3 UI            │ At BER = 10⁻¹²          │    │
│  │ Jitter (DJ)            │ < 15 ps             │ Deterministic           │    │
│  │ Jitter (RJ)            │ < 3 ps RMS          │ Random                  │    │
│  │ Crosstalk              │ < 5%                │ FEXT + NEXT             │    │
│  │ Return loss            │ > 10 dB             │ @ Nyquist               │    │
│  │ Termination            │ 50Ω ODT             │ On-die                  │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  PCIe 5.0 Interface:                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ Parameter              │ Specification        │ Notes                   │    │
│  ├────────────────────────────────────────────────────────────────────────┤    │
│  │ Data rate              │ 32 GT/s             │ NRZ signaling           │    │
│  │ TX swing               │ 800-1200 mV         │ Differential            │    │
│  │ RX sensitivity         │ > 50 mV             │ Differential            │    │
│  │ TX jitter              │ < 3 ps RMS          │ Total                   │    │
│  │ Equalization           │ CTLE + 3-tap DFE    │ Adaptive                │    │
│  │ Channel loss           │ < 28 dB             │ @ 16 GHz                │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ON-DIE SIGNAL INTEGRITY:                                                       │
│  ═══════════════════════════                                                    │
│                                                                                 │
│  Critical Path Timing:                                                          │
│  • Setup margin: > 50 ps (10% of cycle @ 1 GHz)                                │
│  • Hold margin: > 30 ps                                                         │
│  • Clock skew: < 20 ps (within clock domain)                                   │
│  • OCV derating: 5% (on-chip variation)                                         │
│                                                                                 │
│  Noise Budget:                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ Noise Source           │ Budget              │ Mitigation              │    │
│  ├────────────────────────────────────────────────────────────────────────┤    │
│  │ IR drop                │ < 37.5 mV (5%)      │ Dense power grid        │    │
│  │ SSO (simultaneous      │ < 25 mV             │ Staggered I/O timing    │    │
│  │      switching output) │                     │                         │    │
│  │ Crosstalk              │ < 15 mV             │ Shielding, spacing      │    │
│  │ Power supply noise     │ < 20 mV             │ Decoupling, filtering   │    │
│  │ TOTAL                  │ < 100 mV            │ (noise margin ~150 mV)  │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.8 Error Handling and ECC

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ERROR DETECTION AND CORRECTION                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  HBM3 ECC:                                                                      │
│  ═════════                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Data Path: 256-bit data + 32-bit ECC = 288-bit total                   │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │  DATA[255:0] ──▶ ┌─────────┐     ┌─────────┐ ──▶ DATA_OUT     │     │   │
│  │  │                  │  ECC    │     │  ECC    │                   │     │   │
│  │  │                  │ ENCODE  │────▶│ DECODE  │                   │     │   │
│  │  │                  │ (SEC-DED)│     │         │ ──▶ ERROR_FLAG   │     │   │
│  │  │                  └─────────┘     └─────────┘                   │     │   │
│  │  │                                                                 │     │   │
│  │  │  SEC-DED: Single Error Correct, Double Error Detect            │     │   │
│  │  │  Hamming distance: 4                                            │     │   │
│  │  │  Overhead: 12.5%                                                │     │   │
│  │  │  Latency: +1 cycle (pipelined)                                  │     │   │
│  │  │                                                                 │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  SRAM ECC (On-Die):                                                            │
│  ══════════════════                                                             │
│  • Weight cache: SECDED (64-bit data + 8-bit ECC)                             │
│  • TCU buffers: SECDED (critical data with retention)                          │
│  • Input buffers: Parity only (can re-fetch from HBM)                          │
│                                                                                 │
│  COMPUTATION INTEGRITY:                                                         │
│  ═════════════════════                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Phase Attention Verification:                                          │   │
│  │  • Checksum on phase values (detect stuck-at faults)                    │   │
│  │  • Range check: phases must be in [0, 2π]                               │   │
│  │  • Coherence bound: coherence must be in [0, 1]                         │   │
│  │                                                                          │   │
│  │  Ontology Verification:                                                 │   │
│  │  • Probability sum check: Σ ontology_probs ≈ 1.0 (±0.01)               │   │
│  │  • Layer transition validity (from adjacency matrix)                    │   │
│  │                                                                          │   │
│  │  State Delta Verification:                                               │   │
│  │  • Magnitude check: |ΔS| < threshold (detect overflow)                  │   │
│  │  • BCVF: Forward-backward consistency check                              │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ERROR REPORTING:                                                               │
│  ═════════════════                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ Error Type             │ Response              │ Register              │    │
│  ├────────────────────────────────────────────────────────────────────────┤    │
│  │ HBM SEC (correctable)  │ Correct, log, continue│ ERR_HBM_CE_CNT       │    │
│  │ HBM DED (uncorrectable)│ Interrupt, retry      │ ERR_HBM_UE_CNT       │    │
│  │ SRAM SEC               │ Correct, log          │ ERR_SRAM_CE_CNT      │    │
│  │ SRAM DED               │ Interrupt, fatal      │ ERR_SRAM_UE_CNT      │    │
│  │ Phase range            │ Clamp, log            │ ERR_PHASE_CNT        │    │
│  │ Coherence range        │ Clamp, log            │ ERR_COHERENCE_CNT    │    │
│  │ Ontology sum           │ Re-normalize, log     │ ERR_ONTOLOGY_CNT     │    │
│  │ BCVF mismatch          │ Interrupt, flag output│ ERR_BCVF_CNT         │    │
│  │ Watchdog timeout       │ Reset unit, interrupt │ ERR_WDT_CNT          │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ERROR INJECTION (for testing):                                                 │
│  ═══════════════════════════════                                                │
│  • ERR_INJ_CTRL register enables fault injection                               │
│  • Single-bit flip in HBM read data                                            │
│  • Double-bit flip in SRAM                                                      │
│  • Force phase/coherence out of range                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.9 Verilog Module Interface Specifications

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        RTL MODULE INTERFACES                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  TOP-LEVEL MODULE:                                                              │
│  ═════════════════                                                              │
│                                                                                 │
│  module pa_vpu_top (                                                            │
│      // Clock and Reset                                                         │
│      input  wire        clk_ref,           // 100 MHz reference                │
│      input  wire        rst_n,             // Active-low async reset           │
│                                                                                 │
│      // HBM3 Interface (8 channels, active-high valid)                         │
│      output wire [7:0]  hbm_ck_p,          // Differential clock               │
│      output wire [7:0]  hbm_ck_n,                                              │
│      inout  wire [1023:0] hbm_dq,          // 128 DQ per channel              │
│      inout  wire [127:0] hbm_dqs_p,        // 16 DQS per channel              │
│      inout  wire [127:0] hbm_dqs_n,                                            │
│      output wire [127:0] hbm_ca,           // Command/address                  │
│      input  wire [7:0]  hbm_derr,          // ECC error flag                   │
│                                                                                 │
│      // PCIe 5.0 x16 Interface                                                 │
│      input  wire [15:0] pcie_rx_p,         // RX differential                  │
│      input  wire [15:0] pcie_rx_n,                                             │
│      output wire [15:0] pcie_tx_p,         // TX differential                  │
│      output wire [15:0] pcie_tx_n,                                             │
│      input  wire        pcie_refclk_p,     // 100 MHz reference                │
│      input  wire        pcie_refclk_n,                                         │
│      input  wire        pcie_rst_n,        // PERST#                           │
│                                                                                 │
│      // MIPI CSI-2 Interface (4 lanes)                                         │
│      input  wire [3:0]  csi_d_p,           // Data lanes                       │
│      input  wire [3:0]  csi_d_n,                                               │
│      input  wire        csi_clk_p,         // Clock lane                       │
│      input  wire        csi_clk_n,                                             │
│                                                                                 │
│      // Atomic Clock Interface (CSAC)                                          │
│      input  wire        csac_10mhz,        // 10 MHz atomic reference          │
│      input  wire        csac_pps,          // 1 PPS sync pulse                 │
│                                                                                 │
│      // JTAG                                                                    │
│      input  wire        tck,                                                    │
│      input  wire        tms,                                                    │
│      input  wire        tdi,                                                    │
│      output wire        tdo,                                                    │
│      input  wire        trst_n,                                                 │
│                                                                                 │
│      // Interrupt                                                               │
│      output wire        irq_n,             // Active-low interrupt             │
│                                                                                 │
│      // Power Management                                                        │
│      output wire [3:0]  pstate,            // Current P-state                  │
│      input  wire        thermtrip_n,       // Thermal shutdown                 │
│      output wire [15:0] temp_sense         // Temperature reading              │
│  );                                                                             │
│                                                                                 │
│  PHASE ATTENTION UNIT MODULE:                                                   │
│  ═════════════════════════════                                                  │
│                                                                                 │
│  module phase_attention_unit #(                                                 │
│      parameter NUM_HEADS    = 12,                                              │
│      parameter HEAD_DIM     = 64,                                              │
│      parameter EMBED_DIM    = 768,                                             │
│      parameter SYNC_STEPS   = 3,                                               │
│      parameter DATA_WIDTH   = 16          // FP16                              │
│  ) (                                                                            │
│      input  wire                    clk,                                        │
│      input  wire                    rst_n,                                      │
│      input  wire                    enable,                                     │
│                                                                                 │
│      // Input interface (AXI-Stream)                                           │
│      input  wire [EMBED_DIM*DATA_WIDTH-1:0] s_axis_tdata,                      │
│      input  wire                    s_axis_tvalid,                              │
│      output wire                    s_axis_tready,                              │
│      input  wire                    s_axis_tlast,                               │
│                                                                                 │
│      // Output interface (AXI-Stream)                                          │
│      output wire [EMBED_DIM*DATA_WIDTH-1:0] m_axis_tdata,                      │
│      output wire                    m_axis_tvalid,                              │
│      input  wire                    m_axis_tready,                              │
│      output wire                    m_axis_tlast,                               │
│                                                                                 │
│      // Weight memory interface (AXI4)                                         │
│      output wire [63:0]            m_axi_araddr,                                │
│      output wire [7:0]             m_axi_arlen,                                 │
│      output wire                    m_axi_arvalid,                              │
│      input  wire                    m_axi_arready,                              │
│      input  wire [511:0]           m_axi_rdata,                                 │
│      input  wire                    m_axi_rvalid,                               │
│      output wire                    m_axi_rready,                               │
│      input  wire                    m_axi_rlast,                                │
│                                                                                 │
│      // Phase context (for temporal streaming)                                 │
│      input  wire [NUM_HEADS*HEAD_DIM*DATA_WIDTH-1:0] phase_sum_in,             │
│      input  wire [31:0]            phase_count_in,                              │
│      output wire [NUM_HEADS*HEAD_DIM*DATA_WIDTH-1:0] phase_sum_out,            │
│      output wire [31:0]            phase_count_out,                             │
│                                                                                 │
│      // Configuration                                                           │
│      input  wire [15:0]            cfg_sync_lr,      // FP16                   │
│      input  wire [15:0]            cfg_temperature,  // FP16                   │
│      input  wire                    cfg_causal,                                 │
│                                                                                 │
│      // Status                                                                  │
│      output wire [15:0]            coherence_out,    // FP16                   │
│      output wire                    error_flag                                  │
│  );                                                                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Register Quick Reference

| Unit | Base Address | Size |
|------|--------------|------|
| GCR | 0x0000 | 0x100 |
| PEU | 0x0100 | 0x100 |
| PAU | 0x0200 | 0x100 |
| TCU | 0x0300 | 0x100 |
| OPU | 0x0400 | 0x100 |
| SDU | 0x0500 | 0x100 |
| OLB[0] | 0x1000 | 0x100 |
| OLB[1] | 0x1100 | 0x100 |
| ... | ... | ... |
| OLB[11] | 0x1B00 | 0x100 |

---

## Appendix B: Cognitive State Output Format

```c
typedef struct {
    // Phoneme layer (44 dims) - visual pattern energy
    float16 phoneme_energy[44];

    // Topic layer (64 dims) - scene embedding
    float16 topic_embedding[64];

    // Ontology layer (12 dims) - layer activations
    float16 ontology_probs[12];

    // Dynamics layer (4 dims)
    float16 coherence;      // Phase alignment [0,1]
    float16 entropy;        // Uncertainty level [0,1]
    float16 confidence;     // Belief strength [0,1]
    float16 momentum;       // Rate of change [0,1]

} CognitiveState;  // 124 × 2 bytes = 248 bytes

typedef struct {
    CognitiveState current;
    CognitiveState delta;  // ΔS = current - previous
    uint64_t frame_number;
    uint64_t timestamp_ns;
} PAVPUOutput;  // 512 bytes per frame
```

---

*Document Version: 1.0*
*Status: Technical Specification*
*Classification: Patent-Adjacent*
