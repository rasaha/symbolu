# PCAM FPGA RTL Design Specification

**Version**: 1.0
**Date**: 2026-02-01
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
| Power | <15W (FPGA), <5W (ASIC) | PCIe slot budget |

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
    output reg  [6:0]  k_value,       // 32, 64, or 128
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
    parameter K_MAX = 128,
    parameter INPUT_WIDTH = 256,    // Max parallel inputs per cycle
    parameter SCORE_WIDTH = 16,
    parameter BLOCK_ID_WIDTH = 20
) (
    input  wire        clk,
    input  wire        rst_n,

    // Configuration
    input  wire [6:0]  k_value,      // 32, 64, or 128

    // Input stream (from bank reads)
    input  wire [INPUT_WIDTH-1:0][SCORE_WIDTH-1:0] in_scores,
    input  wire [INPUT_WIDTH-1:0][BLOCK_ID_WIDTH-1:0] in_block_ids,
    input  wire [INPUT_WIDTH-1:0] in_valid,
    input  wire        in_last,       // Last batch of inputs
    output wire        in_ready,

    // Output (sorted top-K)
    output wire [K_MAX-1:0][SCORE_WIDTH-1:0] out_scores,
    output wire [K_MAX-1:0][BLOCK_ID_WIDTH-1:0] out_block_ids,
    output wire [6:0]  out_count,     // Actual count (may be < K)
    output wire        out_valid,
    input  wire        out_ready
);
```

**Implementation Strategy**:
1. **Stage 1**: Parallel comparators reduce 256 inputs to 128
2. **Stage 2-8**: Bitonic merge network (log2(128) = 7 stages)
3. **Output Register**: Hold top-K until consumed

**Latency**: 8 cycles @ 250MHz = 32ns

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

## 5. Pipeline Design

### 5.1 ATTEND Pipeline (8 stages)

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Stage 0 │─►│ Stage 1 │─►│ Stage 2 │─►│ Stage 3 │
│ Decode  │  │ Hash    │  │ Bank    │  │ BRAM    │
│ Command │  │ BlockID │  │ Arbitr. │  │ Read    │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
                                            │
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────▼────┐
│ Stage 7 │◄─│ Stage 6 │◄─│ Stage 5 │◄─│ Stage 4 │
│ Response│  │ Output  │  │ Merge   │  │ Compare │
│ Format  │  │ Select  │  │ Sort    │  │ Stage 1 │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
```

**Latency Breakdown @ 250MHz (4ns/cycle)**:

| Stage | Cycles | Time (ns) | Description |
|-------|--------|-----------|-------------|
| 0 | 1 | 4 | Command decode |
| 1 | 1 | 4 | Block ID hash |
| 2 | 1 | 4 | Bank arbitration |
| 3 | 2 | 8 | BRAM read (registered) |
| 4-6 | 4 | 16 | Bitonic sort network |
| 7 | 1 | 4 | Response formatting |
| **Total** | **10** | **40** | Internal latency |

With CXL 2.0 interconnect (80ns round-trip), total ATTEND latency = 40 + 80 = **120ns**.

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
| LUTs | ~45,000 | 1,304,000 | 3.5% |
| FFs | ~35,000 | 2,608,000 | 1.3% |
| DSPs | 128 | 9024 | 1.4% |

**Note**: Very low utilization leaves room for multiple PCAM instances or additional features.

### 7.2 Breakdown by Module

| Module | LUTs | FFs | BRAM | DSPs |
|--------|------|-----|------|------|
| Host Interface | 8,000 | 6,000 | 4 | 0 |
| Command Decoder | 500 | 300 | 0 | 0 |
| Bank Controller | 2,000 | 1,500 | 0 | 0 |
| Bank Array (64) | 4,000 | 2,000 | 128 | 0 |
| Top-K Network | 25,000 | 20,000 | 0 | 0 |
| Update Coalescer | 3,000 | 2,500 | 2 | 0 |
| Decay Engine | 500 | 400 | 0 | 2 |
| Section Cache | 2,000 | 2,000 | 0 | 0 |
| **Total** | **45,000** | **34,700** | **134** | **2** |

### 7.3 Power Estimation

```
Static Power:  ~2W (FPGA baseline)
Dynamic Power:
  - BRAM:      ~3W (64 banks active)
  - Logic:     ~2W (250MHz)
  - I/O:       ~1W (PCIe Gen4)

Total:         ~8W (FPGA)
ASIC Target:   ~3W (14nm)
```

---

## 8. Timing Closure Strategy

### 8.1 Critical Paths

1. **Top-K Comparator Chain**: Bitonic network depth
2. **Bank Arbitration**: 64-way multiplexing
3. **Score Accumulation**: Multi-operand addition

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
- **Functional Coverage**: All K values, all bank patterns
- **Toggle Coverage**: >90% for data paths

---

## 10. Implementation Roadmap

### Phase 1: Core RTL (4 weeks)

- [ ] Bank array with basic read/write
- [ ] Command decoder
- [ ] Simple top-K (heap-based, not bitonic)
- [ ] Basic testbench

### Phase 2: Performance Optimization (3 weeks)

- [ ] Bitonic top-K network
- [ ] Update coalescer
- [ ] Decay engine
- [ ] Pipeline optimization

### Phase 3: Integration (3 weeks)

- [ ] PCIe/CXL host interface
- [ ] DMA engine
- [ ] Section cache
- [ ] Full system integration

### Phase 4: Verification (2 weeks)

- [ ] Trace replay from Python simulator
- [ ] Performance benchmarking
- [ ] Power measurement

---

## 11. File Structure

```
rtl/
├── pcam_top.sv              # Top-level module
├── pcam_pkg.sv              # Package with types/constants
├── host_if/
│   ├── pcie_endpoint.sv     # PCIe interface
│   ├── dma_engine.sv        # Scatter-gather DMA
│   └── csr_bank.sv          # Control/status registers
├── core/
│   ├── cmd_decoder.sv       # Command parsing
│   ├── bank_controller.sv   # Bank arbitration
│   ├── bank_mem.sv          # Single BRAM bank
│   ├── topk_network.sv      # Bitonic sort network
│   ├── topk_comparator.sv   # Compare-swap unit
│   ├── update_coalescer.sv  # Write combining
│   ├── decay_engine.sv      # Score decay
│   └── section_cache.sv     # Hierarchical prior
└── common/
    ├── async_fifo.sv        # CDC FIFO
    ├── fixed_mult.sv        # Q8.8 multiplier
    └── log_lut.sv           # Log approximation

tb/
├── tb_pcam_top.sv           # Top-level testbench
├── golden_model/
│   └── pcam_model.py        # Python reference model
├── sequences/
│   ├── basic_test.sv        # Simple smoke tests
│   ├── stress_test.sv       # High-bandwidth tests
│   └── trace_replay.sv      # Simulator trace replay
└── coverage/
    └── pcam_cov.sv          # Functional coverage
```

---

## 12. Appendix: Verilog Snippets

### A.1 Top-Level Port List

```verilog
module pcam_top #(
    parameter NUM_BANKS = 64,
    parameter BANK_DEPTH = 16384,
    parameter K_MAX = 128,
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

1. PCAM Simulator: `simulator/pcam/core/state.py`
2. Configuration: `simulator/pcam/core/config.py`
3. Interface Spec: `simulator/pcam/interface.py`
4. Validation Report: `simulator/pcam/VALIDATION_REPORT.md`
