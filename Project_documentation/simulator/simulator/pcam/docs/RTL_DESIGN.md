# PCAM FPGA RTL Design Specification

**Version**: 3.0 (K=256 silicon sizing)
**Date**: 2026-02-11
**Status**: Implementation Complete
**Target**: Xilinx Alveo U280 / AMD Versal / Intel Agilex

---

## 1. Executive Summary

This document specifies the RTL design for PCAM (Predictive Context Attention Memory) hardware implementation. The design targets FPGA prototyping with a clear path to ASIC.

### Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| ATTEND Latency | <100ns | Host round-trip budget |
| UPDATE Throughput | 100M ops/sec | Match attention computation rate |
| Clock Frequency | 250-500 MHz | FPGA achievable |
| Power | <15W (FPGA), <5W (ASIC) | CXL card thermal budget |

---

## 2. Architecture Overview

### 2.1 System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PCAM FPGA Top                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │   PCIe/CXL  │    │              PCAM Core                           │   │
│  │  Interface  │◄──►│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │   │
│  │             │    │  │ Command │  │  Bank   │  │   Top-K         │   │   │
│  │  - DMA      │    │  │ Decoder │─►│ Router  │─►│   Selection     │   │   │
│  │  - CSR      │    │  │         │  │         │  │   Network       │   │   │
│  │  - IRQ      │    │  └─────────┘  └────┬────┘  └────────┬────────┘   │   │
│  └─────────────┘    │                    │                │            │   │
│                     │         ┌──────────▼──────────┐     │            │   │
│                     │         │   Memory Banks      │     │            │   │
│                     │         │   ┌────┬────┬────┐  │     │            │   │
│                     │         │   │B0  │B1  │... │  │     │            │   │
│                     │         │   │    │    │B63 │  │◄────┘            │   │
│                     │         │   └────┴────┴────┘  │                  │   │
│                     │         │   (64 x BRAM18K)    │                  │   │
│                     │         └─────────────────────┘                  │   │
│                     │                                                   │   │
│                     │  ┌─────────────────────────────────────────────┐ │   │
│                     │  │           Section Cache (Optional)          │ │   │
│                     │  │           16 x 64-bit LUTRAM                │ │   │
│                     │  └─────────────────────────────────────────────┘ │   │
│                     └──────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Design Decisions

1. **Banked Memory Architecture**: 64 parallel BRAM banks enable single-cycle parallel lookup
2. **Pipelined Top-K**: Bitonic merge network for deterministic K-selection latency
3. **Write Coalescing**: Buffer multiple UPDATEs to amortize RMW overhead
4. **Fixed-Point Arithmetic**: 16-bit scores (Q8.8) for area efficiency

---

## 3. Memory Architecture

### 3.1 Block Score Storage

Each block entry stores:

```
┌─────────────────────────────────────────────────────────────┐
│                    Block Entry (64 bits)                    │
├──────────────┬──────────────┬─────────────┬─────────────────┤
│  Score       │  Access Count│  Last Step  │  Reserved       │
│  (16 bits)   │  (12 bits)   │  (20 bits)  │  (16 bits)      │
│  Q8.8 fixed  │  0-4095      │  0-1M steps │  Future use     │
└──────────────┴──────────────┴─────────────┴─────────────────┘
```

### 3.2 BRAM Organization

```
Total Capacity: 1M entries (1,048,576 blocks)
Entry Width:    64 bits
Banks:          64 parallel banks
Entries/Bank:   16,384 (16K)

BRAM Usage per Bank:
  - 16K entries × 64 bits = 1,048,576 bits = 1 Mbit
  - Requires: 2 × BRAM36K or 4 × BRAM18K per bank

Total BRAM: 64 banks × 2 BRAM36K = 128 BRAM36K
           (Alveo U280 has 2016 BRAM36K → 6.3% utilization)
```

### 3.3 Bank Address Mapping

Block IDs map to banks using hash-based interleaving:

```verilog
// Bank selection (LSB-based for simplicity, XOR-hash for better distribution)
wire [5:0] bank_id = block_id[5:0] ^ block_id[11:6];  // 64 banks
wire [13:0] bank_addr = block_id[19:6];               // 16K entries/bank
```

### 3.4 Section State Storage

Soft hierarchical prior requires per-section statistics:

```
Sections:       4096 (16 blocks/section for 64K max blocks)
Section Entry:  64 bits
  - Total Attention: 24 bits (Q12.12)
  - Access Count:    16 bits
  - Unique Queries:  8 bits (saturating)
  - Reserved:        16 bits

Storage:        4096 × 64 bits = 256 Kbit
Implementation: Distributed RAM (LUTRAM) or dedicated BRAM
```

---

## 4. Module Hierarchy

### 4.1 Top-Level Modules

```
pcam_top
├── pcam_host_if           # PCIe/CXL host interface
│   ├── dma_engine         # Scatter-gather DMA
│   ├── csr_bank           # Control/status registers
│   └── irq_controller     # Interrupt handling
│
├── pcam_core              # Main processing core
│   ├── cmd_decoder        # Command parsing
│   ├── bank_controller    # Memory bank arbitration
│   ├── bank_array[64]     # Parallel BRAM banks
│   ├── topk_network       # Top-K selection
│   ├── update_coalescer   # Write combining buffer
│   ├── decay_engine       # Periodic decay application
│   └── section_cache      # Hierarchical prior state
│
└── pcam_debug             # Debug/monitoring
    ├── perf_counters      # Performance monitoring
    └── trace_buffer       # Transaction trace (optional)
```

### 4.2 Module Specifications

#### 4.2.1 Command Decoder (`cmd_decoder`)

```verilog
module cmd_decoder (
    input  wire        clk,
    input  wire        rst_n,

    // Host interface
    input  wire [63:0] cmd_data,
    input  wire        cmd_valid,
    output wire        cmd_ready,

    // Decoded commands
    output reg  [2:0]  op_type,      // ATTEND=0, UPDATE=1, BATCH_UPDATE=2, DECAY=3, ALLOC=4, FREE=5
    output reg  [5:0]  sequence_id,
    output reg  [19:0] query_block,
    output reg  [19:0] key_block,
    output reg  [15:0] weight,        // Q8.8 fixed
    output reg  [8:0]  k_value,       // 64, 128, or 256 (K_WIDTH=9)
    output reg         op_valid,
    input  wire        op_ready
);
```

Command encoding (64-bit):
```
┌────────┬───────────┬─────────────┬─────────────┬──────────┐
│ Op[2:0]│ SeqID[5:0]│ Query[19:0] │ Key[19:0]   │ Data[14:0]│
└────────┴───────────┴─────────────┴─────────────┴──────────┘
  [63:61]   [60:55]     [54:35]       [34:15]      [14:0]
```

#### 4.2.2 Bank Controller (`bank_controller`)

```verilog
module bank_controller #(
    parameter NUM_BANKS = 64,
    parameter BANK_DEPTH = 16384,
    parameter ENTRY_WIDTH = 64
) (
    input  wire        clk,
    input  wire        rst_n,

    // Request interface
    input  wire [19:0] req_block_id,
    input  wire        req_read,
    input  wire        req_write,
    input  wire [63:0] req_wdata,
    input  wire        req_valid,
    output wire        req_ready,

    // Response interface
    output wire [63:0] resp_rdata,
    output wire        resp_valid,
    input  wire        resp_ready,

    // Bank interfaces (active-low chip select)
    output wire [63:0] bank_cs_n,
    output wire [13:0] bank_addr,
    output wire        bank_we,
    output wire [63:0] bank_wdata,
    input  wire [63:0][63:0] bank_rdata  // 64 banks × 64-bit
);
```

#### 4.2.3 Top-K Selection Network (`topk_network`)

Implements a parallel bitonic sorting network for deterministic latency:

```verilog
module topk_network #(
    parameter K_MAX = 256,
    parameter INPUT_WIDTH = 256,    // Max parallel inputs per cycle
    parameter SCORE_WIDTH = 16,
    parameter BLOCK_ID_WIDTH = 20
) (
    input  wire        clk,
    input  wire        rst_n,

    // Configuration
    input  wire [8:0]  k_value,      // 64, 128, or 256 (K_WIDTH=9)

    // Input stream (from bank reads)
    input  wire [INPUT_WIDTH-1:0][SCORE_WIDTH-1:0] in_scores,
    input  wire [INPUT_WIDTH-1:0][BLOCK_ID_WIDTH-1:0] in_block_ids,
    input  wire [INPUT_WIDTH-1:0] in_valid,
    input  wire        in_last,       // Last batch of inputs
    output wire        in_ready,

    // Output (sorted top-K)
    output wire [K_MAX-1:0][SCORE_WIDTH-1:0] out_scores,
    output wire [K_MAX-1:0][BLOCK_ID_WIDTH-1:0] out_block_ids,
    output wire [8:0]  out_count,     // Actual count (may be < K)
    output wire        out_valid,
    input  wire        out_ready
);
```

**Implementation Strategy**:
1. **Stage 1**: Parallel comparators reduce 256 inputs to 64 (bitonic_sort_64)
2. **Stage 2-10**: Bitonic merge network (512-wide: log2(512) = 9 stages)
3. **Output Register**: Hold top-K until consumed

**Latency**: 9 cycles @ 250MHz = 36ns (internal), 44ns with pipeline overhead

#### 4.2.4 Update Coalescer (`update_coalescer`)

Buffers multiple UPDATEs to the same bank for RMW efficiency:

```verilog
module update_coalescer #(
    parameter BUFFER_DEPTH = 64,
    parameter NUM_BANKS = 64
) (
    input  wire        clk,
    input  wire        rst_n,

    // Input updates
    input  wire [19:0] upd_block_id,
    input  wire [15:0] upd_weight,
    input  wire [5:0]  upd_seq_id,
    input  wire        upd_valid,
    output wire        upd_ready,

    // Coalesced output to bank controller
    output wire [19:0] coal_block_id,
    output wire [15:0] coal_weight,
    output wire [5:0]  coal_seq_id,
    output wire        coal_valid,
    input  wire        coal_ready,

    // Flush control
    input  wire        flush_req,
    output wire        flush_done
);
```

**Coalescing Rules**:
- Same block_id within window → accumulate weights
- Different banks → parallel issue
- Timeout or buffer full → flush

---

## 5. Detailed Module Documentation

This section provides comprehensive documentation for each implemented RTL module.

### 5.1 Top-K Selection Network (`core/topk_network.sv`)

The Top-K network is the performance-critical component of ATTEND operations. It selects the K highest-scoring candidates from all bank reads.

#### 5.1.1 Architecture

```
                    Input Candidates (64 per cycle)
                              │
                    ┌─────────▼─────────┐
                    │  Bitonic Sort 64  │  ◄── Combinational (6 stages)
                    │   (unchanged)     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Bitonic Merge    │  ◄── Merge with accumulator
                    │   512 → K         │      (9 stages for 512-wide)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Accumulator     │  ◄── Running top-K
                    │   (256 entries)   │
                    └─────────┬─────────┘
                              │
                         Top-K Output
```

#### 5.1.2 Module Variants

| Module | Latency | Throughput | Use Case |
|--------|---------|------------|----------|
| `topk_network` | Variable | 1 result/batch | Area-optimized |
| `topk_network_pipelined` | 9 cycles | 1 result/cycle | Throughput-optimized |
| `bitonic_sort_64` | Combinational | N/A | Sub-module (sorts input batch) |
| `bitonic_merge_512` | Combinational | N/A | Sub-module (merges K=256 accum + 64 input) |

#### 5.1.3 Bitonic Sort Algorithm

Bitonic sort uses compare-swap networks in a specific pattern:

```
Stage 0: Compare pairs (0,1), (2,3), ... with alternating direction
Stage 1: Merge pairs into sorted quads
Stage 2: Merge quads into sorted octets
...
Stage N: Final merge into sorted sequence
```

**Compare-Swap Unit** (`common/cmp_swap.sv`):
```verilog
// Direction: 0 = ascending (smaller to out_lo)
//            1 = descending (larger to out_lo)
assign swap = (score_a < score_b) ^ direction;
assign out_hi = swap ? in_b : in_a;
assign out_lo = swap ? in_a : in_b;
```

#### 5.1.4 Pipelined Version

The `topk_network_pipelined` module adds registers between stages for timing closure:

```
Parameter: PIPELINE_STAGES = 9

Stage 0: Input registration
Stage 1-8: Bitonic compare-swap with registers (512-wide merge)
Stage 9: Output formatting

Total Latency: 9 cycles @ 250MHz = 36ns (internal selection)
              +8ns pipeline overhead = 44ns total
```

#### 5.1.5 Interface Signals

| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `k_value` | 9 | Input | K selection (64, 128, 256) — K_WIDTH=9 |
| `in_candidates` | 64×36 | Input | Candidates from banks |
| `in_valid` | 64 | Input | Per-candidate valid |
| `in_last` | 1 | Input | Last batch indicator |
| `out_candidates` | 256×36 | Output | Sorted top-K (K_MAX=256) |
| `out_count` | 9 | Output | Actual result count |
| `out_valid` | 1 | Output | Result ready |

---

### 5.2 Update Coalescer (`core/update_coalescer.sv`)

The update coalescer buffers UPDATE operations and combines writes to the same block, reducing BRAM read-modify-write overhead.

#### 5.2.1 Architecture

```
              Input UPDATEs
                    │
        ┌───────────▼───────────┐
        │      CAM Lookup       │  ◄── Parallel block_id match
        │   (64 comparators)    │
        └───────────┬───────────┘
                    │
           ┌────────┴────────┐
           │                 │
      CAM Hit            CAM Miss
           │                 │
           ▼                 ▼
    ┌─────────────┐   ┌─────────────┐
    │  Coalesce   │   │   Insert    │
    │  (add wt)   │   │  (new entry)│
    └─────────────┘   └─────────────┘
                    │
        ┌───────────▼───────────┐
        │     Age Tracking      │  ◄── Timeout detection
        │   (per-entry counter) │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │    Flush Control      │  ◄── Timeout or full
        └───────────┬───────────┘
                    │
              Coalesced Output
```

#### 5.2.2 Buffer Entry Format

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Buffer Entry (72 bits)                           │
├───────┬────────────┬──────────┬─────────┬─────────┬────────────────┤
│ Valid │  Block ID  │  Seq ID  │ Weight  │  Count  │      Age       │
│ (1b)  │   (20b)    │   (6b)   │  (16b)  │  (8b)   │     (6b)       │
└───────┴────────────┴──────────┴─────────┴─────────┴────────────────┘
```

#### 5.2.3 CAM Lookup

Content-Addressable Memory lookup for O(1) duplicate detection:

```verilog
// Parallel comparison across all buffer entries
for (int i = 0; i < BUFFER_DEPTH; i++) begin
    cam_match[i] = buffer[i].valid &&
                   buffer[i].block_id == in_block_id &&
                   buffer[i].seq_id == in_seq_id;
end

// Priority encoder for first match
cam_hit = |cam_match;
cam_match_idx = /* first set bit position */;
```

#### 5.2.4 Coalescing Algorithm

```
if (cam_hit) {
    // Same block already in buffer - accumulate weight
    buffer[cam_match_idx].weight += in_weight;  // Saturating add
    buffer[cam_match_idx].count++;
    coalesce_count++;
} else {
    // New block - insert at tail
    buffer[tail_ptr] = {in_block_id, in_seq_id, in_weight, 1, 0};
    tail_ptr++;
}
```

#### 5.2.5 Flush Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| Timeout | `age >= 64 cycles` | Flush oldest entry |
| Buffer Full | `count >= DEPTH-1` | Flush oldest entry |
| Explicit Flush | `flush_req` | Flush all entries |

#### 5.2.6 Performance Metrics

| Metric | Value |
|--------|-------|
| Buffer Depth | 64 entries |
| Lookup Latency | 1 cycle |
| Expected Coalesce Rate | 10-40% (workload dependent) |
| Throughput | 1 update/cycle input, 1 coalesced/cycle output |

---

### 5.3 Decay Engine (`core/decay_engine.sv`)

The decay engine applies exponential decay to all block scores as a background task. It also includes a scheduler and section-level decay.

#### 5.3.1 Main Decay Engine

```
              Trigger
                 │
        ┌────────▼────────┐
        │   IDLE State    │
        └────────┬────────┘
                 │ trigger
        ┌────────▼────────┐
        │  START_SWEEP    │  ◄── Initialize counters
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   READ_ENTRY    │  ◄── Issue BRAM read
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   WAIT_READ     │  ◄── BRAM latency
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ COMPUTE_DECAY   │  ◄── new = old × 0.99
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  WRITE_ENTRY    │  ◄── Write back
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  NEXT_ENTRY     │  ◄── Increment addr/bank
        └────────┬────────┘
                 │
           Last entry?
           ├── No ──► READ_ENTRY
           └── Yes ─► SWEEP_DONE
```

#### 5.3.2 Decay Computation

Q8.8 fixed-point multiplication:

```verilog
// decay_rate = 0.99 × 256 = 253 (0xFD)
localparam DECAY_RATE = 16'h00FD;

wire [31:0] decay_product = old_score * DECAY_RATE;
wire [15:0] decayed_score = (decay_product + 128) >> 8;  // Round
```

#### 5.3.3 Sweep Performance

| Metric | Value |
|--------|-------|
| Entries per sweep | 1,048,576 (1M) |
| Cycles per entry | 3 (read + compute + write) |
| Sweep time @ 250MHz | 12.6 ms |
| Trigger interval | Every 100 steps |

#### 5.3.4 Decay Scheduler (`decay_scheduler`)

Triggers decay based on step count or idle detection:

```verilog
// Step-based trigger
step_trigger = (current_step - last_decay_step >= INTERVAL);

// Idle-based trigger (opportunistic)
idle_trigger = (idle_counter >= THRESHOLD) &&
               (current_step - last_decay_step >= INTERVAL/2);

decay_trigger = step_trigger || idle_trigger;
```

#### 5.3.5 Section Decay Engine

Lighter-weight decay for hierarchical prior sections:

| Metric | Value |
|--------|-------|
| Sections | 4,096 |
| Decay rate | 0.94 |
| Sweep time | ~50 μs |

---

### 5.4 PCIe Endpoint (`host_if/pcie_endpoint.sv`)

PCIe Gen4 x8 endpoint providing host communication via TLP parsing and AXI-Stream conversion.

#### 5.4.1 Architecture

```
        PCIe Hard Block
              │
     ┌────────▼────────┐
     │   TLP Parser    │  ◄── Extract type, address, data
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │   BAR Decoder   │  ◄── Route to correct function
     └────────┬────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
   BAR0      BAR1      BAR2
 (FIFO)    (CSRs)    (DMA)
    │         │         │
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│ Cmd   │ │ AXI-  │ │ Desc  │
│ FIFO  │ │ Lite  │ │ Ring  │
└───────┘ └───────┘ └───────┘
```

#### 5.4.2 BAR Memory Map

| BAR | Base Address | Size | Function |
|-----|--------------|------|----------|
| BAR0 | 0x0000_0000 | 4 KB | Command/Response FIFO |
| BAR1 | 0x0001_0000 | 64 KB | Control/Status Registers |
| BAR2 | 0x0002_0000 | 16 KB | DMA Descriptors |

#### 5.4.3 TLP Types Supported

| TLP Type | Code | Description |
|----------|------|-------------|
| MRd32 | 0x00 | Memory Read 32-bit address |
| MRd64 | 0x20 | Memory Read 64-bit address |
| MWr32 | 0x40 | Memory Write 32-bit address |
| MWr64 | 0x60 | Memory Write 64-bit address |
| CplD | 0x4A | Completion with Data |

#### 5.4.4 Clock Domain Crossing

Command and response FIFOs handle CDC between PCIe (250 MHz) and user (250-500 MHz) domains:

```
PCIe Domain (250 MHz)          User Domain (250-500 MHz)
        │                              │
        │    ┌───────────────┐         │
        ├───►│  Async FIFO   │────────►├─── Commands
        │    │  (Gray-code)  │         │
        │    └───────────────┘         │
        │                              │
        │    ┌───────────────┐         │
        ◄────│  Async FIFO   │◄────────┤─── Responses
             │  (Gray-code)  │         │
             └───────────────┘         │
```

#### 5.4.5 MSI Interrupt Generation

```verilog
// Generate MSI on response completion
if (rsp_tvalid && rsp_tlast && irq_armed) begin
    msi_request <= 1'b1;
    msi_vector <= 5'd0;  // Vector 0 = response ready
end
```

#### 5.4.6 Performance

| Metric | Value |
|--------|-------|
| PCIe Generation | Gen4 |
| Lane Width | x8 |
| Theoretical BW | 15.75 GB/s |
| Round-trip Latency | ~800 ns (including DMA setup) |

---

### 5.5 DMA Engine (`host_if/dma_engine.sv`)

Scatter-gather DMA for bulk data transfer between host memory and PCAM.

#### 5.5.1 Descriptor Format

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DMA Descriptor (256 bits)                        │
├─────────────────┬─────────────────┬──────────┬─────────────────────┤
│   Host Address  │  Local Address  │  Length  │       Flags         │
│     (64 bits)   │    (32 bits)    │ (24 bits)│      (8 bits)       │
├─────────────────┴─────────────────┴──────────┴─────────────────────┤
│   Next Descriptor Address (64 bits)  │  Status (32b)  │ Reserved  │
└──────────────────────────────────────┴────────────────┴───────────┘

Flags:
  [0] = Direction (0=H2D, 1=D2H)
  [1] = Interrupt on Complete
  [2] = Last Descriptor in Chain
  [7:3] = Reserved
```

#### 5.5.2 State Machine

```
        ┌──────────┐
        │   IDLE   │◄─────────────────────────┐
        └────┬─────┘                          │
             │ desc_available                 │
        ┌────▼─────┐                          │
        │  FETCH   │  ◄── Read descriptor     │
        │  _DESC   │      from host           │
        └────┬─────┘                          │
             │                                │
        ┌────▼─────┐                          │
        │  PARSE   │  ◄── Extract fields      │
        │  _DESC   │                          │
        └────┬─────┘                          │
             │                                │
        ┌────▼─────┐                          │
        │  SETUP   │  ◄── Initialize xfer     │
        │  _XFER   │                          │
        └────┬─────┘                          │
             │                                │
       ┌─────┴─────┐                          │
       │           │                          │
   ┌───▼───┐   ┌───▼───┐                      │
   │ XFER  │   │ XFER  │                      │
   │ _H2D  │   │ _D2H  │                      │
   └───┬───┘   └───┬───┘                      │
       │           │                          │
       └─────┬─────┘                          │
             │                                │
        ┌────▼─────┐                          │
        │  WRITE   │  ◄── Update status       │
        │ _STATUS  │                          │
        └────┬─────┘                          │
             │                                │
        ┌────▼─────┐                          │
        │  NEXT    │──── chain ──────────────►│
        │  _DESC   │                          │
        └──────────┘──── last ────────────────┘
```

#### 5.5.3 Descriptor Ring

Software writes descriptors to ring buffer, updates tail pointer:

```
┌────────────────────────────────────────────────┐
│                 Descriptor Ring                 │
├────┬────┬────┬────┬────┬────┬────┬────┬────────┤
│ D0 │ D1 │ D2 │ D3 │ D4 │ D5 │ D6 │ D7 │  ...   │
└────┴────┴────┴────┴────┴────┴────┴────┴────────┘
       ▲                   ▲
       │                   │
    head_ptr            tail_ptr
   (HW reads)          (SW writes)
```

#### 5.5.4 Performance

| Metric | Value |
|--------|-------|
| Max Burst Size | 256 bytes |
| Max Outstanding | 8 transactions |
| Descriptor Fetch | 32 bytes |
| Ring Size | 256 entries |

---

### 5.6 Async FIFO (`common/async_fifo.sv`)

Dual-clock FIFO for safe clock domain crossing using gray-code pointers.

#### 5.6.1 Gray-Code Synchronization

```
Write Domain                    Read Domain
     │                               │
     ▼                               ▼
┌─────────┐                    ┌─────────┐
│ wr_ptr  │                    │ rd_ptr  │
│ (binary)│                    │ (binary)│
└────┬────┘                    └────┬────┘
     │                               │
     ▼                               ▼
┌─────────┐                    ┌─────────┐
│ bin2gray│                    │ bin2gray│
└────┬────┘                    └────┬────┘
     │                               │
     ▼                               ▼
┌─────────┐                    ┌─────────┐
│ wr_ptr  │────── 2-FF ───────►│ wr_ptr  │
│ (gray)  │     sync           │ _sync   │
└─────────┘                    └─────────┘

┌─────────┐                    ┌─────────┐
│ rd_ptr  │◄───── 2-FF ────────│ rd_ptr  │
│ _sync   │      sync          │ (gray)  │
└─────────┘                    └─────────┘
```

#### 5.6.2 Gray-Code Conversion

```verilog
// Binary to Gray
function logic [N-1:0] bin_to_gray(logic [N-1:0] bin);
    return bin ^ (bin >> 1);
endfunction

// Gray to Binary
function logic [N-1:0] gray_to_bin(logic [N-1:0] gray);
    logic [N-1:0] bin;
    bin[N-1] = gray[N-1];
    for (int i = N-2; i >= 0; i--)
        bin[i] = bin[i+1] ^ gray[i];
    return bin;
endfunction
```

#### 5.6.3 Full/Empty Detection

```verilog
// Full: MSB differs, MSB-1 differs, rest matches (wrapped around)
assign wr_full = (wr_ptr_gray[N-1] != rd_ptr_gray_sync[N-1]) &&
                 (wr_ptr_gray[N-2] != rd_ptr_gray_sync[N-2]) &&
                 (wr_ptr_gray[N-3:0] == rd_ptr_gray_sync[N-3:0]);

// Empty: Pointers match exactly
assign rd_empty = (rd_ptr_gray == wr_ptr_gray_sync);
```

#### 5.6.4 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| WIDTH | 64 | Data width in bits |
| DEPTH | 16 | FIFO depth (power of 2) |
| ALMOST_FULL_THRESH | DEPTH-4 | Almost full threshold |
| ALMOST_EMPTY_THRESH | 4 | Almost empty threshold |

---

### 5.7 Score Update Module (`common/score_update.sv`)

Q8.8 fixed-point arithmetic for attention score updates.

#### 5.7.1 EMA Update Formula

```
new_score = α × new_weight + (1-α) × old_score

Where α = 0.2 (configurable)
```

#### 5.7.2 Pipeline Stages

```
Stage 1 (Multiply):
  term1 = new_weight × ALPHA        // Q8.8 × Q8.8 = Q16.16
  term2 = old_score × (1-ALPHA)     // Q8.8 × Q8.8 = Q16.16

Stage 2 (Add + Truncate):
  sum = term1 + term2               // Q16.16
  result = (sum + 128) >> 8         // Round to Q8.8
```

#### 5.7.3 Decay Module

```verilog
module score_decay (
    input  [15:0] old_score,
    output [15:0] decayed_score
);
    // decay_rate = 0.99 × 256 = 253
    localparam DECAY_RATE = 16'h00FD;

    wire [31:0] product = old_score * DECAY_RATE;
    assign decayed_score = (product + 128) >> 8;
endmodule
```

#### 5.7.4 Frequency Boost LUT

Log approximation for access frequency bonus:

```verilog
// log1p(access_count) × 0.01 × 256
log_lut[0]  = 0;   // log1p(0) = 0
log_lut[1]  = 2;   // log1p(1) ≈ 0.69
log_lut[2]  = 3;   // log1p(2) ≈ 1.10
log_lut[4]  = 4;   // log1p(4) ≈ 1.61
log_lut[8]  = 6;   // log1p(8) ≈ 2.20
log_lut[15] = 7;   // log1p(15) ≈ 2.77
```

---

## 6. Pipeline Design

### 6.1 ATTEND Pipeline (9 stages)

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Stage 0 │─►│ Stage 1 │─►│ Stage 2 │─►│ Stage 3 │
│ Decode  │  │ Hash    │  │ Bank    │  │ BRAM    │
│ Command │  │ BlockID │  │ Arbitr. │  │ Read    │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
                                            │
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────▼────┐
│ Stage 8 │◄─│ Stage 7 │◄─│ Stage 5 │◄─│ Stage 4 │
│ Response│  │ Output  │  │  -6     │  │ Compare │
│ Format  │  │ Select  │  │ Merge   │  │ Stage 1 │
└─────────┘  └─────────┘  │ Sort    │  └─────────┘
                           └─────────┘
```

**Latency Breakdown @ 250MHz (4ns/cycle)**:

| Stage | Cycles | Time (ns) | Description |
|-------|--------|-----------|-------------|
| 0 | 1 | 4 | Command decode |
| 1 | 1 | 4 | Block ID hash |
| 2 | 1 | 4 | Bank arbitration |
| 3 | 2 | 8 | BRAM read (registered) |
| 4-7 | 5 | 20 | Bitonic sort + 512-wide merge (9 stages, +1 vs K=128) |
| 8 | 1 | 4 | Response formatting (first beat) |
| **Total** | **11** | **44** | Internal latency |

With CXL 2.0 interconnect (80ns round-trip), total ATTEND latency = 44 + 2×80 = **204ns**.
(+4ns vs K=128 design due to wider merge network)

**Note**: Response formatting outputs first beat at stage 8. For K=256, the host receives 43 beats over ~172ns (43 × 4ns). Total ATTEND including response drain: ~216ns on CXL 2.0. Since response drain overlaps with next command decode, effective pipeline throughput is unchanged.

### 5.2 UPDATE Pipeline (4 stages)

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Stage 0 │─►│ Stage 1 │─►│ Stage 2 │─►│ Stage 3 │
│ Decode  │  │ Coalesce│  │ RMW     │  │ BRAM    │
│ Buffer  │  │ Check   │  │ Compute │  │ Write   │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
```

**Read-Modify-Write Sequence**:
1. Read existing entry (2 cycles)
2. Compute new score: `new_score = α × weight + (1-α) × old_score`
3. Write back (1 cycle)

**Throughput**: With 64 banks and coalescing, sustained **100M updates/sec**.

### 5.3 DECAY Pipeline

Decay runs as background task during idle cycles:

```verilog
// Decay state machine
always @(posedge clk) begin
    case (decay_state)
        IDLE: begin
            if (decay_trigger) begin
                decay_bank <= 0;
                decay_addr <= 0;
                decay_state <= READ;
            end
        end
        READ: begin
            // Issue read to current bank/addr
            decay_state <= COMPUTE;
        end
        COMPUTE: begin
            // new_score = old_score × decay_rate (Q8.8 multiply)
            decayed_score <= (bank_rdata[15:0] * decay_rate) >> 8;
            decay_state <= WRITE;
        end
        WRITE: begin
            // Write back decayed value
            if (decay_addr == BANK_DEPTH - 1) begin
                decay_bank <= decay_bank + 1;
                decay_addr <= 0;
                if (decay_bank == NUM_BANKS - 1)
                    decay_state <= IDLE;
            end else begin
                decay_addr <= decay_addr + 1;
            end
            decay_state <= READ;
        end
    endcase
end
```

**Decay Throughput**: 1M entries / (3 cycles × 4ns) = **83M entries/sec**
Full decay sweep: 1M / 83M = **12ms** (acceptable for 100-step interval)

---

## 6. Fixed-Point Arithmetic

### 6.1 Score Format (Q8.8)

```
┌─────────────────────────────────────────┐
│         16-bit Q8.8 Fixed Point         │
├────────────────────┬────────────────────┤
│   Integer (8 bits) │ Fraction (8 bits)  │
│      0-255         │   0.00-0.996       │
└────────────────────┴────────────────────┘

Range: 0.0 to 255.996
Resolution: 1/256 ≈ 0.0039
```

### 6.2 Arithmetic Operations

```verilog
// Score update: new = α × weight + (1-α) × old
// α = 0.2 in Q8.8 = 51 (0x33)
localparam ALPHA = 16'h0033;        // 0.2 × 256 = 51
localparam ONE_MINUS_ALPHA = 16'h00CD;  // 0.8 × 256 = 205

wire [31:0] term1 = weight * ALPHA;           // Q8.8 × Q8.8 = Q16.16
wire [31:0] term2 = old_score * ONE_MINUS_ALPHA;
wire [15:0] new_score = (term1 + term2) >> 8; // Back to Q8.8

// Decay: new = old × decay_rate
// decay_rate = 0.99 in Q8.8 = 253 (0xFD)
localparam DECAY_RATE = 16'h00FD;

wire [31:0] decayed = old_score * DECAY_RATE;
wire [15:0] new_score_decay = decayed >> 8;
```

### 6.3 Section Score Computation

```verilog
// Section score = avg_attention × log(1 + unique_queries)
// Use LUT for log approximation

wire [15:0] avg_attention = total_attention / access_count;  // Division
wire [7:0] log_factor;  // From 256-entry LUT

log_lut u_log (
    .input_val(unique_queries),   // 8-bit input
    .log_out(log_factor)          // 8-bit log(1+x) × 32
);

wire [23:0] section_score = avg_attention * log_factor;  // Q8.8 × Q3.5 = Q11.13
```

---

## 7. Resource Estimation

### 7.1 Xilinx Alveo U280

| Resource | Used | Available | Utilization |
|----------|------|-----------|-------------|
| BRAM36K | 128 | 2016 | 6.3% |
| URAM | 0 | 960 | 0% |
| LUTs | ~65,000 | 1,304,000 | 5.0% |
| FFs | ~50,000 | 2,608,000 | 1.9% |
| DSPs | 128 | 9024 | 1.4% |

**Note**: K=256 increases Top-K network from ~25K to ~45K LUTs (+80%). Overall utilization remains under 5% — still room for multiple PCAM instances.

### 7.2 Breakdown by Module

| Module | LUTs | FFs | BRAM | DSPs | K=128 → K=256 Change |
|--------|------|-----|------|------|---------------------|
| Host Interface | 8,000 | 6,000 | 4 | 0 | Unchanged |
| Command Decoder | 600 | 400 | 0 | 0 | +100 LUTs (wider k_value) |
| Bank Controller | 2,000 | 1,500 | 0 | 0 | Unchanged |
| Bank Array (64) | 4,000 | 2,000 | 128 | 0 | Unchanged |
| Top-K Network | **45,000** | **35,000** | 0 | 0 | **+80%** (512-wide merge) |
| Update Coalescer | 3,000 | 2,500 | 2 | 0 | Unchanged |
| Decay Engine | 500 | 400 | 0 | 2 | Unchanged |
| Section Cache | 2,000 | 2,000 | 0 | 0 | Unchanged |
| **Total** | **65,100** | **49,800** | **134** | **2** | **+20K LUTs, +15K FFs** |

**Top-K scaling detail**: The 512-wide bitonic merge network contains ~4,600 compare-swap units (vs ~1,800 for 256-wide). Each compare-swap is 36-bit (score + block_id) requiring ~10 LUTs. The accumulator register file doubles from 128×36 to 256×36 bits.

### 7.3 Power Estimation

```
Static Power:  ~2W (FPGA baseline)
Dynamic Power:
  - BRAM:      ~3W (64 banks active)
  - Logic:     ~3W (250MHz, wider merge network)
  - I/O:       ~1W (PCIe Gen4 / CXL)

Total:         ~9W (FPGA)
ASIC Target:   ~4.3W (14nm)    ← within 5W TDP for CXL card
```

**ASIC area**: ~10.3 mm² at 14nm (vs 8.0 mm² at K=128). See Appendix E of benchmark report for full cost analysis.

---

## 8. Timing Closure Strategy

### 8.1 Critical Paths

1. **Top-K Comparator Chain**: 512-wide bitonic merge network (9 stages, ~4,600 comparators)
2. **Bank Arbitration**: 64-way multiplexing
3. **Score Accumulation**: Multi-operand addition
4. **Accumulator Register File**: 256×36-bit accumulator update path

### 8.2 Mitigation Techniques

```verilog
// 1. Register pipeline cuts
always @(posedge clk) begin
    // Insert pipeline register every 2 logic levels
    cmp_stage1 <= (a > b) ? a : b;
    cmp_stage2 <= cmp_stage1;  // Pipeline cut
end

// 2. Parallel reduction for bank MUX
// Instead of 64:1 MUX, use tree structure
wire [63:0] level1 [31:0];  // 64→32
wire [63:0] level2 [15:0];  // 32→16
wire [63:0] level3 [7:0];   // 16→8
wire [63:0] level4 [3:0];   // 8→4
wire [63:0] level5 [1:0];   // 4→2
wire [63:0] result;         // 2→1

// 3. DSP inference for multiply-accumulate
// Xilinx DSP48E2 handles Q8.8 multiply naturally
(* use_dsp = "yes" *)
wire [31:0] product = a * b;
```

### 8.3 Clock Domain Crossing

```
┌─────────────────┐     ┌─────────────────┐
│   PCIe Domain   │     │   PCAM Domain   │
│    250 MHz      │     │    250 MHz      │
│                 │     │                 │
│   cmd_fifo ─────┼─CDC─┼──► cmd_in       │
│   rsp_in   ◄────┼─CDC─┼─── rsp_fifo     │
│                 │     │                 │
└─────────────────┘     └─────────────────┘

CDC Implementation: Async FIFO with gray-code pointers
Depth: 16 entries (handles burst tolerance)
```

---

## 9. Verification Strategy

### 9.1 Testbench Architecture

```
┌─────────────────────────────────────────────────┐
│                  SystemVerilog TB               │
├─────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │   Golden    │  │    DUT      │  │ Checker │ │
│  │   Model     │  │ (pcam_top)  │  │         │ │
│  │  (Python)   │  │             │  │         │ │
│  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│         │                │              │      │
│         └────────────────┼──────────────┘      │
│                          │                     │
│  ┌───────────────────────▼───────────────────┐ │
│  │              Test Sequences               │ │
│  │  - Directed tests (corner cases)          │ │
│  │  - Random tests (constrained)             │ │
│  │  - Trace replay (from simulator)          │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 9.2 Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| Unit Tests | 50+ | Per-module functional tests |
| Integration | 20+ | Cross-module interaction |
| Performance | 10+ | Latency/throughput verification |
| Stress | 5+ | Full bandwidth, bank conflicts |
| Trace Replay | 4 | Chat, Long-Context, RAG, Code |

### 9.3 Coverage Targets

- **Code Coverage**: >95% line, >90% branch
- **Functional Coverage**: All K values (64, 128, 256), all bank patterns, multi-beat response
- **Toggle Coverage**: >90% for data paths

---

## 10. Implementation Status

All phases have been completed. The RTL implementation is ready for synthesis.

### Phase 1: Core RTL ✅ COMPLETE

- [x] Bank array with basic read/write (`core/bank_mem.sv`)
- [x] Command decoder (in `pcam_top.sv`)
- [x] Bitonic top-K network (`core/topk_network.sv`)
- [x] Basic testbench (`tb/tb_pcam_top.sv`)

### Phase 2: Performance Optimization ✅ COMPLETE

- [x] Pipelined bitonic top-K network (`topk_network_pipelined`)
- [x] Update coalescer with CAM lookup (`core/update_coalescer.sv`)
- [x] Decay engine with scheduler (`core/decay_engine.sv`)
- [x] Pipeline registers for timing closure

### Phase 3: Integration ✅ COMPLETE

- [x] PCIe Gen4 x8 endpoint (`host_if/pcie_endpoint.sv`)
- [x] Scatter-gather DMA engine (`host_if/dma_engine.sv`)
- [x] Async FIFO for CDC (`common/async_fifo.sv`)
- [x] Full system integration (`pcam_top.sv`)

### Phase 4: Build System ✅ COMPLETE

- [x] Vivado synthesis script (`scripts/build_vivado.tcl`)
- [x] Xilinx timing constraints (`constraints/timing.xdc`)
- [x] Intel timing constraints (`constraints/timing.sdc`)
- [x] Makefile for automation (`Makefile`)

### Phase 5: Verification (In Progress)

- [ ] Trace replay from Python simulator
- [ ] Performance benchmarking on FPGA
- [ ] Power measurement

---

## 11. Build System

### 11.1 Directory Structure

```
rtl/
├── Makefile                    # Build automation
├── pcam_pkg.sv                 # Package definitions
├── pcam_top.sv                 # Top-level module
├── common/
│   ├── async_fifo.sv           # CDC FIFO
│   ├── cmp_swap.sv             # Compare-swap unit
│   └── score_update.sv         # Q8.8 arithmetic
├── core/
│   ├── bank_mem.sv             # BRAM bank
│   ├── topk_network.sv         # Top-K selection
│   ├── update_coalescer.sv     # Write combining
│   └── decay_engine.sv         # Score decay
├── host_if/
│   ├── pcie_endpoint.sv        # PCIe interface
│   └── dma_engine.sv           # DMA engine
├── constraints/
│   ├── timing.xdc              # Xilinx constraints
│   └── timing.sdc              # Intel constraints
├── scripts/
│   └── build_vivado.tcl        # Synthesis script
└── tb/
    └── tb_pcam_top.sv          # Testbench
```

### 11.2 Build Commands

```bash
# Lint check (Verilator)
make lint

# Simulation (Verilator or Icarus)
make sim
make sim SIMULATOR=iverilog

# Vivado synthesis only
make synth

# Vivado implementation (place & route)
make impl

# Generate bitstream
make bit

# Run with coverage
make coverage

# Clean build artifacts
make clean
```

### 11.3 Synthesis Options

The Vivado build script supports multiple modes:

```bash
# Synthesis only (fast iteration)
vivado -mode batch -source scripts/build_vivado.tcl -tclargs synth_only

# Implementation only (skip bitstream)
vivado -mode batch -source scripts/build_vivado.tcl -tclargs impl

# Full build including bitstream
vivado -mode batch -source scripts/build_vivado.tcl
```

### 11.4 Timing Constraints Summary

Key constraints in `timing.xdc`:

| Constraint | Value | Purpose |
|------------|-------|---------|
| `pcie_clk` period | 4.0 ns (250 MHz) | PCIe clock |
| `user_clk` period | 4.0 ns (250 MHz) | Processing clock |
| CDC max_delay | 8.0 ns | Async FIFO crossing |
| Top-K path | 3.5 ns | Critical path |
| Multi-cycle decay | 2 cycles | Background operation |

---

## 12. Appendix: Verilog Snippets

### A.1 Top-Level Port List

```verilog
module pcam_top #(
    parameter NUM_BANKS = 64,
    parameter BANK_DEPTH = 16384,
    parameter K_MAX = 256,
    parameter MAX_SEQUENCES = 64
) (
    // Clock and reset
    input  wire        clk,
    input  wire        rst_n,

    // PCIe/CXL AXI-Stream interface
    input  wire [255:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tlast,

    output wire [255:0] m_axis_tdata,
    output wire        m_axis_tvalid,
    input  wire        m_axis_tready,
    output wire        m_axis_tlast,

    // Control/Status AXI-Lite
    input  wire [31:0] s_axil_awaddr,
    input  wire        s_axil_awvalid,
    output wire        s_axil_awready,
    input  wire [31:0] s_axil_wdata,
    input  wire        s_axil_wvalid,
    output wire        s_axil_wready,
    output wire [1:0]  s_axil_bresp,
    output wire        s_axil_bvalid,
    input  wire        s_axil_bready,
    input  wire [31:0] s_axil_araddr,
    input  wire        s_axil_arvalid,
    output wire        s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0]  s_axil_rresp,
    output wire        s_axil_rvalid,
    input  wire        s_axil_rready,

    // Interrupt
    output wire        irq,

    // Debug
    output wire [63:0] debug_status
);
```

### A.2 Compare-Swap Unit (Bitonic Network Building Block)

```verilog
module cmp_swap #(
    parameter WIDTH = 36  // 16-bit score + 20-bit block_id
) (
    input  wire [WIDTH-1:0] in_a,
    input  wire [WIDTH-1:0] in_b,
    input  wire             direction,  // 0=ascending, 1=descending
    output wire [WIDTH-1:0] out_hi,
    output wire [WIDTH-1:0] out_lo
);
    wire [15:0] score_a = in_a[WIDTH-1:WIDTH-16];
    wire [15:0] score_b = in_b[WIDTH-1:WIDTH-16];

    wire swap = (score_a < score_b) ^ direction;

    assign out_hi = swap ? in_b : in_a;
    assign out_lo = swap ? in_a : in_b;
endmodule
```

### A.3 Q8.8 Score Update

```verilog
module score_update #(
    parameter ALPHA = 51  // 0.2 in Q8.8
) (
    input  wire [15:0] old_score,
    input  wire [15:0] new_weight,
    output wire [15:0] updated_score
);
    localparam ONE_MINUS_ALPHA = 256 - ALPHA;  // 205 = 0.8

    wire [31:0] term1 = new_weight * ALPHA;
    wire [31:0] term2 = old_score * ONE_MINUS_ALPHA;
    wire [31:0] sum = term1 + term2;

    // Round and truncate back to Q8.8
    assign updated_score = (sum + 128) >> 8;  // +128 for rounding
endmodule
```

---

## 13. References

### 13.1 PCAM Simulator Sources

| File | Description |
|------|-------------|
| `simulator/pcam/core/state.py` | Python reference implementation |
| `simulator/pcam/core/config.py` | Configuration parameters |
| `simulator/pcam/interface.py` | Interface specification |
| `Project_documentation/simulator/simulator/pcam/docs/VALIDATION_REPORT.md` | Validation results |

### 13.2 RTL Source Files

| File | Lines | Description |
|------|-------|-------------|
| `rtl/pcam_pkg.sv` | ~180 | Package with types and constants (K_MAX=256, K_WIDTH=9) |
| `rtl/pcam_top.sv` | ~500 | Top-level module with FSM + multi-beat response |
| `rtl/core/bank_mem.sv` | ~200 | BRAM bank with RMW support |
| `rtl/core/topk_network.sv` | ~450 | Bitonic Top-K selection (512-wide merge, 9-stage pipeline) |
| `rtl/core/update_coalescer.sv` | ~350 | Write combining buffer |
| `rtl/core/decay_engine.sv` | ~300 | Background score decay |
| `rtl/host_if/pcie_endpoint.sv` | ~350 | PCIe Gen4 interface |
| `rtl/host_if/dma_engine.sv` | ~300 | Scatter-gather DMA |
| `rtl/common/async_fifo.sv` | ~250 | CDC FIFO with gray-code |
| `rtl/common/cmp_swap.sv` | ~100 | Compare-swap unit |
| `rtl/common/score_update.sv` | ~200 | Q8.8 arithmetic |
| `rtl/tb/tb_pcam_top.sv` | ~300 | SystemVerilog testbench |
| **Total** | **~3,330** | Complete RTL implementation |

### 13.3 Build Files

| File | Description |
|------|-------------|
| `rtl/Makefile` | Build automation |
| `rtl/scripts/build_vivado.tcl` | Vivado synthesis script |
| `rtl/constraints/timing.xdc` | Xilinx timing constraints |
| `rtl/constraints/timing.sdc` | Intel timing constraints |

### 13.4 External References

1. **Bitonic Sort**: Batcher, K.E. "Sorting Networks and Their Applications" (1968)
2. **Gray Code CDC**: Cummings, C.E. "Simulation and Synthesis Techniques for Asynchronous FIFO Design" (2002)
3. **PCIe Specification**: PCI-SIG, "PCI Express Base Specification 4.0" (2017)
4. **Xilinx UltraScale+**: UG573, "UltraScale Architecture Memory Resources"
