# COHERA ISA Reference Manual

## Instruction Set Architecture for PA-VPU / UCP

**Version:** 1.0
**Date:** 2024-12-30

---

## 1. Instruction Format

### 1.1 Base Encoding (32-bit)

All instructions are 32 bits wide, aligned to 4-byte boundaries.

```
 31  28 27  24 23  20 19  16 15  12 11   8  7   4  3   0
┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐
│  OP  │ DST  │ SRC1 │ SRC2 │ IMM8 │LAYER │FLAGS │ SUB  │
└──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

| Field | Bits | Description |
|-------|------|-------------|
| OP | 31:28 | Opcode category (0-15) |
| DST | 27:24 | Destination register (R0-R15) |
| SRC1 | 23:20 | Source register 1 (R0-R15) |
| SRC2 | 19:16 | Source register 2 (R0-R15) |
| IMM8 | 15:8 | 8-bit immediate value |
| LAYER | 11:8 | Ontology layer (0-11) or 0xF for none |
| FLAGS | 7:4 | Operation flags |
| SUB | 3:0 | Sub-opcode within category |

### 1.2 Extended Encoding (64-bit)

For instructions requiring larger immediates or addresses:

```
 63                              32 31                               0
┌─────────────────────────────────┬─────────────────────────────────┐
│           IMM32 / ADDR          │      BASE INSTRUCTION (32b)     │
└─────────────────────────────────┴─────────────────────────────────┘
```

---

## 2. Register File

### 2.1 General Purpose Registers

| Register | Name | Purpose |
|----------|------|---------|
| R0 | ZERO | Hardwired zero |
| R1-R7 | T0-T6 | Temporary registers |
| R8-R11 | S0-S3 | Saved registers (callee-preserved) |
| R12 | SP | Stack pointer |
| R13 | FP | Frame pointer |
| R14 | LR | Link register |
| R15 | PC | Program counter |

### 2.2 Phase Registers (32 × 32-bit)

| Register | Name | Purpose |
|----------|------|---------|
| P0-P31 | Phase registers | Store phase values [0, 2π] as fixed-point |

Format: Q2.30 fixed-point (2 integer bits, 30 fractional bits)
- Range: [0, 4) maps to [0, 2π)
- Resolution: 2π / 2³⁰ ≈ 5.85 × 10⁻⁹ radians

### 2.3 Coherence Registers (8 × 32-bit)

| Register | Name | Purpose |
|----------|------|---------|
| C0-C7 | Coherence registers | Store coherence values [0, 1] as FP32 |

### 2.4 Special Registers

| Register | Address | Purpose |
|----------|---------|---------|
| SR_LAYER | 0xF000 | Current ontology layer (0-11) |
| SR_FREQ | 0xF004 | Current layer frequency (Hz) |
| SR_COHERENCE | 0xF008 | Global coherence score |
| SR_ENTROPY | 0xF00C | Global entropy value |
| SR_VRITTI | 0xF010 | Current Vritti state (0-4) |
| SR_FRAME | 0xF014 | Frame counter (64-bit) |
| SR_TCU_PTR | 0xF018 | TCU base pointer |

---

## 3. Instruction Reference

### 3.1 Phase Operations (OP = 0x0)

#### PH_INIT - Initialize Phase
```
Encoding: 0x0 DST SRC1 ---- IMM8 LAYER 0000 0x0
Syntax:   PH_INIT Pd, Rs, dim
Operation: Pd = sigmoid(Rs[0:dim]) × 2π
Cycles:   4
```

#### PH_SYNC - Phase Synchronization (Kuramoto)
```
Encoding: 0x0 DST SRC1 SRC2 STEPS LAYER FLAGS 0x1
Syntax:   PH_SYNC Pd, Ps_base, count, steps
Operation:
  for step in 0..steps:
    mean = circular_mean(Ps_base[0:count])
    for i in 0..count:
      grad = -sin(Ps_base[i] - mean)
      Ps_base[i] += lr × grad
  Pd = mean
Cycles:   8 × steps × count
Flags:    [0] = use global lr from SR
```

#### PH_MEAN - Circular Mean
```
Encoding: 0x0 DST SRC1 ---- COUNT ---- 0000 0x2
Syntax:   PH_MEAN Pd, Ps_base, count
Operation:
  sum_sin = Σ sin(Ps_base[i])
  sum_cos = Σ cos(Ps_base[i])
  Pd = atan2(sum_sin, sum_cos)
Cycles:   2 × count + 4
```

#### PH_GRAD - Phase Gradient
```
Encoding: 0x0 DST SRC1 SRC2 ---- LAYER 0000 0x3
Syntax:   PH_GRAD Rd, Ps, Pm
Operation: Rd = -N × sin(Ps - Pm)  ; N from layer config
Cycles:   3
```

#### PH_UPDATE - Phase Update
```
Encoding: 0x0 DST SRC1 SRC2 ---- ---- FLAGS 0x4
Syntax:   PH_UPDATE Pd, Ps, Rgrad
Operation: Pd = Ps + lr × Rgrad
Cycles:   2
Flags:    [0] = clamp to [0, 2π)
```

#### PH_LOCK - Phase Lock
```
Encoding: 0x0 DST SRC1 ---- THRESH LAYER 0000 0x5
Syntax:   PH_LOCK Pd, Ps, threshold
Operation:
  if coherence(Ps) > threshold:
    Pd = quantize_to_layer(Ps, LAYER)
  else:
    Pd = Ps
Cycles:   5
```

#### PH_MOD - Frequency Modulation
```
Encoding: 0x0 DST SRC1 ---- ---- LAYER 0000 0x6
Syntax:   PH_MOD Pd, Ps, layer
Operation: Pd = Ps × (10000 / layer_freq[layer])
Cycles:   3
```

#### PH_ROPE - Rotary Position Embedding
```
Encoding: 0x0 DST SRC1 FREQ POS   ----  FLAGS 0x7
Syntax:   PH_ROPE Rd_base, Rs_base, Rfreq_base, pos_offset, rope_dim
Operation:
  For token t (absolute position p = pos_offset + t):
    for k in 0..rope_dim/2:
      theta = p × Rfreq_base[k]        ; inv-freq table on device
      x0    = Rs_base[2k]
      x1    = Rs_base[2k + 1]
      Rd_base[2k]     = x0 × cos(theta) - x1 × sin(theta)
      Rd_base[2k + 1] = x0 × sin(theta) + x1 × cos(theta)
Notes:
  - Applied in-place if Rd_base == Rs_base.
  - rope_dim is the LOW portion of the head; upper (head_dim - rope_dim)
    is copied through unchanged (matches Llama/Mistral convention).
  - FLAGS[0] = fp16/bf16 select, FLAGS[1] = async.
Cycles:   4 × (rope_dim / 2) + 6
```

### 3.2 Coherence Operations (OP = 0x1)

#### CO_MEASURE - Measure Coherence
```
Encoding: 0x1 DST SRC1 ---- COUNT ---- 0000 0x0
Syntax:   CO_MEASURE Cd, Ps_base, count
Operation:
  sum = Σ exp(i × Ps_base[j])  ; complex sum
  Cd = |sum| / count
Cycles:   3 × count + 2
```

#### CO_GATE - Coherence Gate
```
Encoding: 0x1 DST SRC1 SRC2 THRESH ---- 0000 0x1
Syntax:   CO_GATE Rd, Rs, Cs, threshold
Operation:
  if Cs > threshold:
    Rd = Rs
  else:
    Rd = 0
Cycles:   2
```

#### CO_ENTROPY - Phase Entropy
```
Encoding: 0x1 DST SRC1 ---- COUNT ---- 0000 0x2
Syntax:   CO_ENTROPY Cd, Ps_base, count
Operation:
  hist = histogram(Ps_base[0:count], bins=32)
  Cd = -Σ (hist[i]/count) × log(hist[i]/count)
Cycles:   count + 64
```

#### CO_VERIFY - Bidirectional Verification (BCVF)
```
Encoding: 0x1 DST SRC1 SRC2 ---- ---- 0000 0x3
Syntax:   CO_VERIFY Cd, Cs_fwd, Cs_bwd
Operation:
  Cd = 1 - |Cs_fwd - Cs_bwd|
Cycles:   3
```

#### CO_GATED_RESIDUAL - Coherence-Gated Residual Blend
```
Encoding: 0x1 DST SRC1 SRC2 GATE  ----  FLAGS 0x4
Syntax:   CO_GATED_RESIDUAL Rd_base, Rhidden_base, Radapter_base, Rgate, dim
Operation:
  ; Rgate is a scalar register holding the sigmoid gate value in [0, 1]
  for i in 0..dim:
    Rd_base[i] = Rhidden_base[i] + Rgate × Radapter_base[i]
Purpose:
  Fused residual blend used by the mistral_cg PhaseAdapter, replacing the
  separate CO_GATE + vector-add chain. The gate is produced by a
  sigmoid(adapter_gate_init) scalar upstream (init -2 -> ~0.12).
Cycles:   dim / 16 + 3
```

### 3.3 Ontology Operations (OP = 0x2)

#### ON_PROJECT - Ontology Projection
```
Encoding: 0x2 DST SRC1 ---- DIM  LAYER 0000 0x0
Syntax:   ON_PROJECT Rd_base, Rs_base, dim, layer
Operation:
  W = load_projection_weights(layer)  ; [768 → dim]
  Rd_base[0:dim] = matmul(Rs_base[0:768], W)
Cycles:   768 × dim / 16 + 10
```

#### ON_ACTIVATE - Kosha Activation
```
Encoding: 0x2 DST SRC1 ---- ---- KOSHA 0000 0x1
Syntax:   ON_ACTIVATE Rd, Rs, kosha
Operation:
  weight = kosha_weights[kosha]  ; 0.0-1.0
  Rd = Rs × weight × layer_activation_fn(Rs)
Cycles:   4
```

#### ON_VRITTI - Detect Vritti State
```
Encoding: 0x2 DST SRC1 SRC2 ---- ---- 0000 0x2
Syntax:   ON_VRITTI Rd, Cs_coherence, Cs_entropy
Operation:
  if Cs_coherence > 0.8 && Cs_entropy < 0.3:
    Rd = 0  ; Pramana (valid cognition)
  elif phase_misalignment > 0.5:
    Rd = 1  ; Viparyaya (misperception)
  elif Cs_entropy > 0.7:
    Rd = 2  ; Vikalpa (imagination)
  elif tcu_spike > 0.6:
    Rd = 3  ; Smrti (memory)
  else:
    Rd = 4  ; Nidra (dormancy)
Cycles:   6
```

#### ON_BLEND - Layer Blending
```
Encoding: 0x2 DST SRC1 SRC2 COUNT ---- 0000 0x3
Syntax:   ON_BLEND Rd_base, Rs_layers_base, Rweights_base, count
Operation:
  for i in 0..output_dim:
    Rd_base[i] = Σ Rs_layers_base[j][i] × Rweights_base[j]
Cycles:   count × output_dim / 8
```

#### ON_PROJECT_SOVEREIGN - 32-D Sovereign State Projection
```
Encoding: 0x2 DST SRC1 ---- ---- MODE  FLAGS 0x4
Syntax:   ON_PROJECT_SOVEREIGN Rd_base, Rs_base, hidden_dim, kosha_mode
Operation:
  ; two-stage MLP: hidden_dim -> intermediate_dim (default hidden/4) -> 32
  ; weights W_in, W_out and biases come from per-model OPU slots
  h  = GELU(Rs_base[0:hidden_dim] · W_in + b_in)       ; intermediate
  v  = h · W_out + b_out                                ; [32]

  ; Component-wise normalization of v into the 32-D Sovereign layout
  bhava    = softmax(v[0:12])                           ; 12
  if kosha_mode == SIGMOID: kosha = sigmoid(v[12:17])
  else:                     kosha = softmax(v[12:17])   ; 5
  vritti   = softmax(v[17:22])                          ; 5
  guna     = sigmoid(v[22:28])                          ; 6
  reserved = tanh(v[28:32])                             ; 4

  Rd_base[0:12]  = bhava
  Rd_base[12:17] = kosha
  Rd_base[17:22] = vritti
  Rd_base[22:28] = guna
  Rd_base[28:32] = reserved
Purpose:
  mistral_cg SovereignStateProjector in one opcode; replaces two ON_PROJECT
  + five per-component activation sequences.
Cycles:   hidden_dim × intermediate_dim / 16
        + intermediate_dim × 32 / 16
        + 32 (activation) + 10
```

### 3.4 Memory Operations (OP = 0x3)

#### MEM_LOAD - Load from HBM3
```
Encoding: 0x3 DST ---- ---- SIZE ---- FLAGS 0x0
Extended: [63:32] = HBM3 address
Syntax:   MEM_LOAD Rd_base, addr, size
Operation: Rd_base[0:size] = HBM3[addr:addr+size]
Cycles:   size/64 + latency(~100 cycles)
Flags:    [0] = async, [1] = non-temporal
```

#### MEM_STORE - Store to HBM3
```
Encoding: 0x3 ---- SRC1 ---- SIZE ---- FLAGS 0x1
Extended: [63:32] = HBM3 address
Syntax:   MEM_STORE addr, Rs_base, size
Operation: HBM3[addr:addr+size] = Rs_base[0:size]
Cycles:   size/64 + latency
Flags:    [0] = async, [1] = write-through
```

#### MEM_TCU_RD - Read TCU Accumulator
```
Encoding: 0x3 DST ---- ---- DIM  HEAD  0000 0x2
Syntax:   MEM_TCU_RD Rd_base, head, dim
Operation: Rd_base[0:dim] = TCU[head][0:dim]
Cycles:   dim/16 + 4
```

#### MEM_TCU_WR - Write TCU Accumulator
```
Encoding: 0x3 ---- SRC1 ---- DIM  HEAD  0000 0x3
Syntax:   MEM_TCU_WR head, dim, Rs_base
Operation: TCU[head][0:dim] = Rs_base[0:dim]
Cycles:   dim/16 + 4
```

#### MEM_TCU_ACC - Accumulate to TCU
```
Encoding: 0x3 ---- SRC1 ---- DIM  HEAD  FLAGS 0x4
Syntax:   MEM_TCU_ACC head, dim, Rs_base
Operation:
  TCU[head][0:dim] += Rs_base[0:dim]
  frame_count[head] += 1
Cycles:   dim/16 + 6
Flags:    [0] = use EMA with decay factor
```

### 3.5 Control Operations (OP = 0x4)

#### CTL_SYNC_LAYER - Cross-Layer Sync
```
Encoding: 0x4 ---- ---- ---- MASK[11:8] MASK[7:0] 0000 0x0
Syntax:   CTL_SYNC_LAYER layer_mask
Operation: Barrier until all specified layers complete
Cycles:   Variable (depends on layer timing)
```

#### CTL_BARRIER - Thread Barrier
```
Encoding: 0x4 ---- ---- ---- ---- ---- 0000 0x1
Syntax:   CTL_BARRIER
Operation: Wait for all threads in block
Cycles:   Variable
```

#### CTL_STREAM_WAIT - Wait for Stream
```
Encoding: 0x4 ---- ---- ---- STREAM ---- 0000 0x2
Syntax:   CTL_STREAM_WAIT stream_id
Operation: Wait for stream to complete
Cycles:   Variable
```

#### CTL_FRAME_DONE - Signal Frame Complete
```
Encoding: 0x4 ---- ---- ---- ---- ---- 0000 0x3
Syntax:   CTL_FRAME_DONE
Operation: Increment frame counter, trigger IRQ
Cycles:   1
```

---

## 4. Opcode Summary Table

| OP | Category | SUB | Mnemonic | Description |
|----|----------|-----|----------|-------------|
| 0x0 | Phase | 0x0 | PH_INIT | Initialize phase from embedding |
| 0x0 | Phase | 0x1 | PH_SYNC | Kuramoto synchronization |
| 0x0 | Phase | 0x2 | PH_MEAN | Circular mean |
| 0x0 | Phase | 0x3 | PH_GRAD | Phase gradient |
| 0x0 | Phase | 0x4 | PH_UPDATE | Update phase |
| 0x0 | Phase | 0x5 | PH_LOCK | Lock phase above threshold |
| 0x0 | Phase | 0x6 | PH_MOD | Frequency modulation |
| 0x0 | Phase | 0x7 | PH_ROPE | Rotary position embedding |
| 0x1 | Coherence | 0x0 | CO_MEASURE | Measure coherence |
| 0x1 | Coherence | 0x1 | CO_GATE | Coherence-gated output |
| 0x1 | Coherence | 0x2 | CO_ENTROPY | Phase entropy |
| 0x1 | Coherence | 0x3 | CO_VERIFY | BCVF verification |
| 0x1 | Coherence | 0x4 | CO_GATED_RESIDUAL | Fused gate × adapter + hidden |
| 0x2 | Ontology | 0x0 | ON_PROJECT | Layer projection |
| 0x2 | Ontology | 0x1 | ON_ACTIVATE | Kosha activation |
| 0x2 | Ontology | 0x2 | ON_VRITTI | Vritti detection |
| 0x2 | Ontology | 0x3 | ON_BLEND | Layer blending |
| 0x2 | Ontology | 0x4 | ON_PROJECT_SOVEREIGN | 32-D Sovereign State |
| 0x3 | Memory | 0x0 | MEM_LOAD | HBM3 load |
| 0x3 | Memory | 0x1 | MEM_STORE | HBM3 store |
| 0x3 | Memory | 0x2 | MEM_TCU_RD | TCU read |
| 0x3 | Memory | 0x3 | MEM_TCU_WR | TCU write |
| 0x3 | Memory | 0x4 | MEM_TCU_ACC | TCU accumulate |
| 0x4 | Control | 0x0 | CTL_SYNC_LAYER | Layer sync |
| 0x4 | Control | 0x1 | CTL_BARRIER | Thread barrier |
| 0x4 | Control | 0x2 | CTL_STREAM_WAIT | Stream wait |
| 0x4 | Control | 0x3 | CTL_FRAME_DONE | Frame complete |

---

## 5. Example Programs

### 5.1 Single-Head Phase Attention

```asm
; Input: R1 = query base, R2 = key base, R3 = value base
; Output: R4 = attended output
; Config: 64 tokens, 64-dim head

    ; Initialize phases from queries
    PH_INIT     P0, R1, 64          ; P0 = phases from Q

    ; Run 3-step synchronization
    PH_SYNC     P1, P0, 64, 3       ; P1 = synchronized mean

    ; Measure coherence
    CO_MEASURE  C0, P0, 64          ; C0 = coherence score

    ; Compute attention weights from phases
    PH_GRAD     R5, P0, P1          ; R5 = gradients

    ; Gate by coherence
    CO_GATE     R6, R3, C0, 0.5     ; R6 = gated values

    ; Output
    MEM_STORE   R4, R6, 64          ; Store result
```

### 5.2 12-Layer Ontological Processing

```asm
; Process through all 12 ontology layers
; Input: R1 = hidden state [768]
; Output: R2 = cognitive state [124]

    ; Layer 1 (O1_POTENTIAL, 10kHz)
    ON_PROJECT  R10, R1, 64, 0

    ; Layer 2-11 (loop unrolled for clarity)
    ON_PROJECT  R11, R10, 64, 1
    ON_PROJECT  R12, R11, 64, 2
    ; ... layers 3-10 ...
    ON_PROJECT  R20, R19, 64, 10

    ; Layer 12 (O12_ABSOLVING, 1Hz)
    ON_PROJECT  R21, R20, 64, 11

    ; Synchronize all layers
    CTL_SYNC_LAYER 0xFFF           ; Wait for all 12

    ; Blend to cognitive state
    ON_BLEND    R2, R10, R_weights, 12

    ; Detect Vritti
    CO_MEASURE  C0, P_all, 12
    CO_ENTROPY  C1, P_all, 12
    ON_VRITTI   R30, C0, C1
```

---

*Document Version: 1.0*
*Related: COHERA_SDK_SPECIFICATION.md, PA-VPU Hardware Spec*
