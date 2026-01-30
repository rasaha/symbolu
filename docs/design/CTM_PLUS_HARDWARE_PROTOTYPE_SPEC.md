# CTM+ Hardware Prototype Specification

## What a Hardware Prototype Actually Looks Like

**Document Version:** 1.0
**Date:** January 2026
**Status:** Prototype Specification
**Classification:** Engineering Design

---

## Executive Summary

This document specifies a practical FPGA-based hardware prototype for CTM+.
The goal is to prove that CTM+ can meet real-world timing constraints, not
just algorithmic correctness (which the simulator already proves).

### What the Prototype Proves

| Question | Software Simulator | Hardware Prototype |
|----------|-------------------|-------------------|
| Does the algorithm make better decisions? | ✅ Yes | ✅ Yes |
| Can it run at memory speed (~1M ops/sec)? | ❌ No | ✅ Yes |
| Does it fit in reasonable hardware? | ❌ No | ✅ Yes |
| What's the real latency overhead? | ❌ No | ✅ Yes |
| What's the power consumption? | ❌ No | ✅ Yes |

---

## 1. Prototype Architecture

### 1.1 High-Level Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CTM+ FPGA PROTOTYPE                                  │
│                        (Xilinx Alveo U280)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   HOST PC                                                                   │
│   ════════                                                                  │
│   ┌─────────────────┐                                                       │
│   │  Test Harness   │                                                       │
│   │  (Python/C++)   │                                                       │
│   │  - Trace replay │                                                       │
│   │  - Metrics      │                                                       │
│   └────────┬────────┘                                                       │
│            │ PCIe Gen4 x16                                                  │
│            │ (32 GB/s)                                                      │
│            ▼                                                                │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         FPGA FABRIC                                  │  │
│   │  ┌───────────────────────────────────────────────────────────────┐  │  │
│   │  │                    CTM+ CONTROLLER                             │  │  │
│   │  │                                                                │  │  │
│   │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │  │  │
│   │  │  │    EVENT     │  │    FAST      │  │    BCVF      │        │  │  │
│   │  │  │   EMBEDDER   │─▶│   COHERENCE  │─▶│    GATE      │        │  │  │
│   │  │  │   (RTL)      │  │   (RTL)      │  │   (RTL)      │        │  │  │
│   │  │  │   ~500 LUT   │  │   ~800 LUT   │  │   ~400 LUT   │        │  │  │
│   │  │  └──────────────┘  └──────────────┘  └──────────────┘        │  │  │
│   │  │         │                                    │                │  │  │
│   │  │         │         ┌──────────────┐          │                │  │  │
│   │  │         │         │    PHASE     │          │                │  │  │
│   │  │         └────────▶│  INTEGRATOR  │──────────┘                │  │  │
│   │  │                   │   (RTL)      │                           │  │  │
│   │  │                   │   ~1200 LUT  │                           │  │  │
│   │  │                   └──────────────┘                           │  │  │
│   │  │                          │                                   │  │  │
│   │  │                          ▼                                   │  │  │
│   │  │                   ┌──────────────┐                           │  │  │
│   │  │                   │   DECISION   │                           │  │  │
│   │  │                   │   ARBITER    │                           │  │  │
│   │  │                   │   (RTL)      │                           │  │  │
│   │  │                   │   ~300 LUT   │                           │  │  │
│   │  │                   └──────────────┘                           │  │  │
│   │  │                          │                                   │  │  │
│   │  │         ┌────────────────┼────────────────┐                  │  │  │
│   │  │         ▼                ▼                ▼                  │  │  │
│   │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │  │  │
│   │  │  │   TIER-0     │ │   TIER-1     │ │   METADATA   │         │  │  │
│   │  │  │   MANAGER    │ │   MANAGER    │ │   STORE      │         │  │  │
│   │  │  │   (RTL)      │ │   (RTL)      │ │   (BRAM)     │         │  │  │
│   │  │  │   ~400 LUT   │ │   ~400 LUT   │ │   2 MB       │         │  │  │
│   │  │  └──────┬───────┘ └──────┬───────┘ └──────────────┘         │  │  │
│   │  │         │                │                                   │  │  │
│   │  └─────────┼────────────────┼───────────────────────────────────┘  │  │
│   │            │                │                                      │  │
│   │            ▼                ▼                                      │  │
│   │     ┌──────────────┐ ┌──────────────┐                             │  │
│   │     │   DDR4       │ │   HBM2       │  (Simulated tiers)          │  │
│   │     │   (Tier-1)   │ │   (Tier-0)   │                             │  │
│   │     │   16 GB      │ │   8 GB       │                             │  │
│   │     └──────────────┘ └──────────────┘                             │  │
│   │                                                                    │  │
│   │  ┌───────────────────────────────────────────────────────────────┐│  │
│   │  │                    EMBEDDED ARM CORE                          ││  │
│   │  │                    (Cortex-A53 or soft)                       ││  │
│   │  │  - SCC Optimizer (background)                                 ││  │
│   │  │  - Slow-path coherence (background)                           ││  │
│   │  │  - Statistics collection                                      ││  │
│   │  │  - Parameter tuning                                           ││  │
│   │  └───────────────────────────────────────────────────────────────┘│  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Placement

| Component | Implementation | Location | Why |
|-----------|---------------|----------|-----|
| Event Embedder | RTL (Verilog) | FPGA fabric | Critical path, <10ns |
| Fast Coherence | RTL (Verilog) | FPGA fabric | Critical path, <10ns |
| Phase Integrator | RTL (Verilog) | FPGA fabric | Per-access, <20ns |
| BCVF Gate | RTL (Verilog) | FPGA fabric | Per-decision, <30ns |
| Decision Arbiter | RTL (Verilog) | FPGA fabric | Per-access, <10ns |
| Tier Managers | RTL (Verilog) | FPGA fabric | Memory interface |
| Metadata Store | BRAM | FPGA BRAM | Fast random access |
| Slow Coherence | C firmware | ARM core | Background, not latency-critical |
| SCC Optimizer | C firmware | ARM core | Background, complex logic |

---

## 2. RTL Module Specifications

### 2.1 Event Embedder

```verilog
module event_embedder #(
    parameter EMBED_DIM = 64,
    parameter PAGE_ID_BITS = 32
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // Input event
    input  wire                     event_valid,
    input  wire [PAGE_ID_BITS-1:0]  page_id,
    input  wire [1:0]               op_type,      // 0=READ, 1=WRITE, 2=PREFETCH
    input  wire [15:0]              delta_t,      // Time since last access

    // Output embedding
    output reg                      embed_valid,
    output reg  [EMBED_DIM*16-1:0]  embedding     // Fixed-point Q8.8
);

    // Simple hash-based embedding
    // In production: replace with learned weights in BRAM LUT

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            embed_valid <= 0;
            embedding <= 0;
        end else if (event_valid) begin
            // Hash page_id to spread across dimensions
            // Use sine approximation for smooth embedding
            embedding[0*16 +: 16] <= sin_lut(page_id[7:0]);
            embedding[1*16 +: 16] <= sin_lut(page_id[15:8]);
            embedding[2*16 +: 16] <= sin_lut(page_id[23:16]);
            embedding[3*16 +: 16] <= sin_lut(page_id[31:24]);

            // Op type one-hot
            embedding[8*16 +: 16] <= (op_type == 0) ? 16'h0100 : 16'h0000;
            embedding[9*16 +: 16] <= (op_type == 1) ? 16'h0100 : 16'h0000;
            embedding[10*16 +: 16] <= (op_type == 2) ? 16'h0100 : 16'h0000;

            // Temporal feature (log-scaled)
            embedding[12*16 +: 16] <= log_lut(delta_t);

            embed_valid <= 1;
        end else begin
            embed_valid <= 0;
        end
    end

endmodule
```

**Resource Estimate:** ~500 LUTs, ~2 BRAMs (for LUTs)

### 2.2 Fast Coherence Calculator

```verilog
module fast_coherence #(
    parameter FIXED_POINT_BITS = 16  // Q8.8 fixed point
)(
    input  wire                         clk,
    input  wire                         rst_n,

    // Page state input (from metadata store)
    input  wire                         state_valid,
    input  wire [FIXED_POINT_BITS-1:0]  page_coherence,  // c_i
    input  wire [FIXED_POINT_BITS-1:0]  page_drift,      // δ_i
    input  wire [FIXED_POINT_BITS-1:0]  page_phase,      // φ_i
    input  wire [FIXED_POINT_BITS-1:0]  mean_phase,      // φ̄

    // Weights (from config registers)
    input  wire [FIXED_POINT_BITS-1:0]  alpha,           // Coherence weight
    input  wire [FIXED_POINT_BITS-1:0]  beta,            // (1-drift) weight
    input  wire [FIXED_POINT_BITS-1:0]  gamma,           // Phase alignment weight

    // Output
    output reg                          result_valid,
    output reg  [FIXED_POINT_BITS-1:0]  fast_coherence   // C_fast ∈ [0,1]
);

    // Pipeline registers
    reg [FIXED_POINT_BITS-1:0] phase_diff;
    reg [FIXED_POINT_BITS-1:0] cos_phase_diff;
    reg [FIXED_POINT_BITS-1:0] one_minus_drift;
    reg [FIXED_POINT_BITS-1:0] term1, term2, term3;
    reg [2:0] valid_pipe;

    // CORDIC or LUT for cosine
    wire [FIXED_POINT_BITS-1:0] cos_result;
    cos_lut cos_inst (
        .angle(phase_diff),
        .cos_out(cos_result)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_pipe <= 0;
            result_valid <= 0;
        end else begin
            // Pipeline stage 1: Compute differences
            phase_diff <= page_phase - mean_phase;
            one_minus_drift <= 16'h0100 - page_drift;  // 1.0 - drift
            valid_pipe[0] <= state_valid;

            // Pipeline stage 2: Lookup cosine, compute terms
            cos_phase_diff <= cos_result;
            term1 <= mult_fixed(alpha, page_coherence);
            term2 <= mult_fixed(beta, one_minus_drift);
            valid_pipe[1] <= valid_pipe[0];

            // Pipeline stage 3: Final sum
            // C_fast = α·c + β·(1-δ) + γ·(0.5 + 0.5·cos(φ-φ̄))
            term3 <= mult_fixed(gamma, 16'h0080 + (cos_phase_diff >> 1));
            fast_coherence <= term1 + term2 + term3;
            result_valid <= valid_pipe[1];

            valid_pipe[2] <= valid_pipe[1];
        end
    end

    // Fixed-point multiply (Q8.8 × Q8.8 → Q8.8)
    function [FIXED_POINT_BITS-1:0] mult_fixed;
        input [FIXED_POINT_BITS-1:0] a, b;
        reg [31:0] product;
        begin
            product = a * b;
            mult_fixed = product[23:8];  // Extract Q8.8 result
        end
    endfunction

endmodule
```

**Resource Estimate:** ~800 LUTs, ~1 DSP, ~1 BRAM (cosine LUT)
**Latency:** 3 clock cycles (~12ns at 250MHz)

### 2.3 BCVF Gate

```verilog
module bcvf_gate #(
    parameter FIXED_POINT_BITS = 16
)(
    input  wire                         clk,
    input  wire                         rst_n,

    // Page state
    input  wire                         eval_valid,
    input  wire [FIXED_POINT_BITS-1:0]  page_amplitude,
    input  wire [FIXED_POINT_BITS-1:0]  page_coherence,
    input  wire [FIXED_POINT_BITS-1:0]  page_heat,
    input  wire [FIXED_POINT_BITS-1:0]  page_uncertainty,
    input  wire [FIXED_POINT_BITS-1:0]  page_drift,
    input  wire [FIXED_POINT_BITS-1:0]  predicted_benefit,

    // Config (from registers, set by ARM core)
    input  wire [FIXED_POINT_BITS-1:0]  lambda_f,
    input  wire [FIXED_POINT_BITS-1:0]  lambda_b,
    input  wire [FIXED_POINT_BITS-1:0]  lambda_c,
    input  wire [FIXED_POINT_BITS-1:0]  beta_temp,
    input  wire [FIXED_POINT_BITS-1:0]  threshold,

    // Output
    output reg                          decision_valid,
    output reg                          approve,          // 1 = proceed, 0 = reject
    output reg  [FIXED_POINT_BITS-1:0]  weight           // w(i,A) for debugging
);

    // Pipeline registers
    reg [FIXED_POINT_BITS-1:0] s_f, s_b;
    reg [FIXED_POINT_BITS-1:0] term_f, term_b, term_c;
    reg [FIXED_POINT_BITS-1:0] lagrangian;
    reg [3:0] valid_pipe;

    // Sigmoid approximation LUT
    wire [FIXED_POINT_BITS-1:0] sigmoid_sf, sigmoid_sb;
    sigmoid_lut sig_f (.x(/* forward inputs */), .y(sigmoid_sf));
    sigmoid_lut sig_b (.x(/* backward inputs */), .y(sigmoid_sb));

    // Exponential LUT for weight
    wire [FIXED_POINT_BITS-1:0] exp_neg_L;
    exp_lut exp_inst (.x(lagrangian), .y(exp_neg_L));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_pipe <= 0;
            decision_valid <= 0;
        end else begin
            // Stage 1: Compute forward and backward scores
            // s_f = σ(α·benefit + amplitude)
            // s_b = σ(β_h·(1-h) + β_c·c + β_u·(1-u) + β_d·(1-δ))
            s_f <= sigmoid_sf;
            s_b <= sigmoid_sb;
            valid_pipe[0] <= eval_valid;

            // Stage 2: Compute Lagrangian terms
            // L = λ_f(1-s_f)² + λ_b(1-s_b)² + λ_c(s_f-s_b)²
            term_f <= mult_fixed(lambda_f, square(16'h0100 - s_f));
            term_b <= mult_fixed(lambda_b, square(16'h0100 - s_b));
            term_c <= mult_fixed(lambda_c, square(s_f > s_b ? s_f - s_b : s_b - s_f));
            valid_pipe[1] <= valid_pipe[0];

            // Stage 3: Sum Lagrangian
            lagrangian <= term_f + term_b + term_c;
            valid_pipe[2] <= valid_pipe[1];

            // Stage 4: Compute weight and decision
            // w = e^{-β·L}
            weight <= exp_neg_L;
            approve <= (exp_neg_L > threshold);
            decision_valid <= valid_pipe[2];

            valid_pipe[3] <= valid_pipe[2];
        end
    end

    function [FIXED_POINT_BITS-1:0] square;
        input [FIXED_POINT_BITS-1:0] x;
        begin
            square = mult_fixed(x, x);
        end
    endfunction

endmodule
```

**Resource Estimate:** ~400 LUTs, ~2 DSPs, ~2 BRAMs (sigmoid, exp LUTs)
**Latency:** 4 clock cycles (~16ns at 250MHz)

### 2.4 Phase Integrator

```verilog
module phase_integrator #(
    parameter EMBED_DIM = 64,
    parameter FIXED_POINT_BITS = 16
)(
    input  wire                         clk,
    input  wire                         rst_n,

    // Input embedding
    input  wire                         embed_valid,
    input  wire [EMBED_DIM*16-1:0]      embedding,

    // Output phase and amplitude for current event
    output reg                          result_valid,
    output reg  [FIXED_POINT_BITS-1:0]  phase,           // φ_t
    output reg  [FIXED_POINT_BITS-1:0]  amplitude,       // a_t
    output reg  [FIXED_POINT_BITS-1:0]  context_phase    // From accumulator
);

    // Projection weights (stored in BRAM, initialized at boot)
    // In production: these would be learned weights
    reg [FIXED_POINT_BITS-1:0] w_phase [0:EMBED_DIM-1];
    reg [FIXED_POINT_BITS-1:0] w_amp [0:EMBED_DIM-1];

    // Streaming accumulator (complex: real + imag)
    reg [31:0] accum_real [0:EMBED_DIM-1];
    reg [31:0] accum_imag [0:EMBED_DIM-1];

    // EMA decay factor γ (e.g., 0.95 = 0xF333 in Q0.16)
    wire [FIXED_POINT_BITS-1:0] gamma = 16'hF333;
    wire [FIXED_POINT_BITS-1:0] one_minus_gamma = 16'h0CCC;

    // Dot product accumulators
    reg [31:0] dot_phase, dot_amp;
    reg [3:0] dim_counter;

    // State machine
    localparam IDLE = 0, COMPUTE = 1, UPDATE = 2, OUTPUT = 3;
    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            result_valid <= 0;
            // Initialize accumulator to zero
            for (int i = 0; i < EMBED_DIM; i++) begin
                accum_real[i] <= 0;
                accum_imag[i] <= 0;
            end
        end else begin
            case (state)
                IDLE: begin
                    result_valid <= 0;
                    if (embed_valid) begin
                        dot_phase <= 0;
                        dot_amp <= 0;
                        dim_counter <= 0;
                        state <= COMPUTE;
                    end
                end

                COMPUTE: begin
                    // Compute dot products (pipelined over dimensions)
                    // This is simplified - real impl would parallelize
                    if (dim_counter < EMBED_DIM) begin
                        dot_phase <= dot_phase +
                            embedding[dim_counter*16 +: 16] * w_phase[dim_counter];
                        dot_amp <= dot_amp +
                            embedding[dim_counter*16 +: 16] * w_amp[dim_counter];
                        dim_counter <= dim_counter + 1;
                    end else begin
                        state <= UPDATE;
                    end
                end

                UPDATE: begin
                    // φ = π·sin(dot_phase)
                    phase <= pi_sin(dot_phase[23:8]);

                    // a = σ(dot_amp)
                    amplitude <= sigmoid(dot_amp[23:8]);

                    // Update accumulator: M = γ·M + (1-γ)·k·v
                    // k = a·e^{-jφ} (complex phasor)
                    // Simplified: just update first few dimensions
                    for (int i = 0; i < 8; i++) begin
                        accum_real[i] <= mult_fixed(gamma, accum_real[i][23:8]) +
                            mult_fixed(one_minus_gamma,
                                mult_fixed(amplitude, cos_lut(phase)));
                        accum_imag[i] <= mult_fixed(gamma, accum_imag[i][23:8]) +
                            mult_fixed(one_minus_gamma,
                                mult_fixed(amplitude, sin_lut(phase)));
                    end

                    state <= OUTPUT;
                end

                OUTPUT: begin
                    // Extract context phase from accumulator
                    context_phase <= atan2_approx(
                        accum_imag[0][23:8] + accum_imag[1][23:8],
                        accum_real[0][23:8] + accum_real[1][23:8]
                    );
                    result_valid <= 1;
                    state <= IDLE;
                end
            endcase
        end
    end

endmodule
```

**Resource Estimate:** ~1200 LUTs, ~4 DSPs, ~4 BRAMs
**Latency:** ~20 clock cycles (~80ns at 250MHz)

---

## 3. Resource Summary

### 3.1 FPGA Resource Utilization

| Component | LUTs | FFs | DSPs | BRAMs | Frequency |
|-----------|------|-----|------|-------|-----------|
| Event Embedder | 500 | 200 | 0 | 2 | 250 MHz |
| Fast Coherence | 800 | 400 | 1 | 1 | 250 MHz |
| BCVF Gate | 400 | 200 | 2 | 2 | 250 MHz |
| Phase Integrator | 1200 | 600 | 4 | 4 | 250 MHz |
| Decision Arbiter | 300 | 150 | 0 | 0 | 250 MHz |
| Tier-0 Manager | 400 | 200 | 0 | 0 | 250 MHz |
| Tier-1 Manager | 400 | 200 | 0 | 0 | 250 MHz |
| Metadata Store | 200 | 100 | 0 | 64 | 250 MHz |
| PCIe Interface | 5000 | 3000 | 0 | 8 | 250 MHz |
| DDR4 Controller | 8000 | 4000 | 0 | 4 | 300 MHz |
| HBM2 Controller | 10000 | 5000 | 0 | 8 | 450 MHz |
| **TOTAL** | **27,200** | **14,050** | **7** | **93** | — |

### 3.2 Alveo U280 Capacity

| Resource | Available | Used | Utilization |
|----------|-----------|------|-------------|
| LUTs | 1,304,000 | 27,200 | **2.1%** |
| FFs | 2,607,000 | 14,050 | **0.5%** |
| DSPs | 9,024 | 7 | **0.1%** |
| BRAMs | 2,016 | 93 | **4.6%** |
| HBM2 | 8 GB | 8 GB | 100% |
| DDR4 | 32 GB | 16 GB | 50% |

**Verdict:** CTM+ fits comfortably in a mid-range FPGA with <5% utilization.

---

## 4. Timing Analysis

### 4.1 Critical Path

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CRITICAL PATH ANALYSIS (Target: <100ns per access)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Memory Access Event                                                        │
│         │                                                                   │
│         ▼ (0ns)                                                             │
│  ┌──────────────┐                                                           │
│  │ Event Embed  │ ──▶ 1 cycle (4ns)                                        │
│  └──────────────┘                                                           │
│         │                                                                   │
│         ▼ (4ns)                                                             │
│  ┌──────────────┐                                                           │
│  │ Metadata     │ ──▶ 2 cycles (8ns) BRAM lookup                           │
│  │ Lookup       │                                                           │
│  └──────────────┘                                                           │
│         │                                                                   │
│         ▼ (12ns)                                                            │
│  ┌──────────────┐                                                           │
│  │ Fast         │ ──▶ 3 cycles (12ns)                                      │
│  │ Coherence    │                                                           │
│  └──────────────┘                                                           │
│         │                                                                   │
│         ▼ (24ns)                                                            │
│  ┌──────────────┐                                                           │
│  │ Tier Check   │ ──▶ 1 cycle (4ns) - is page in tier0?                   │
│  └──────────────┘                                                           │
│         │                                                                   │
│         ├─────────────────────────────────────────────┐                     │
│         │ HIT                                         │ MISS                │
│         ▼ (28ns)                                      ▼ (28ns)              │
│  ┌──────────────┐                              ┌──────────────┐             │
│  │ Return Data  │                              │ BCVF Gate    │             │
│  │ (done)       │                              │              │ ──▶ 4 cycles│
│  └──────────────┘                              └──────────────┘ (16ns)      │
│                                                       │                     │
│                                                       ▼ (44ns)              │
│                                                ┌──────────────┐             │
│                                                │ Tier Move    │             │
│                                                │ (if approved)│ ──▶ 2 cycles│
│                                                └──────────────┘ (8ns)       │
│                                                       │                     │
│                                                       ▼ (52ns)              │
│                                                ┌──────────────┐             │
│                                                │ Return Data  │             │
│                                                │ (done)       │             │
│                                                └──────────────┘             │
│                                                                             │
│  TIMING SUMMARY:                                                           │
│  • Tier-0 hit: 28ns (meets <100ns target)                                 │
│  • Tier-1 hit + promote: 52ns (meets <100ns target)                       │
│  • Miss + add: 52ns (meets <100ns target)                                 │
│                                                                             │
│  Plus memory access latency:                                               │
│  • HBM2 (Tier-0): ~100ns                                                  │
│  • DDR4 (Tier-1): ~80ns                                                   │
│                                                                             │
│  TOTAL ACCESS LATENCY:                                                     │
│  • Tier-0 hit: 28ns + 100ns = 128ns                                       │
│  • Tier-1 hit: 52ns + 80ns = 132ns                                        │
│  • CTM+ overhead vs raw memory: ~30-50ns                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Throughput

| Metric | Value |
|--------|-------|
| Clock frequency | 250 MHz |
| Cycles per access | 7-13 (hit/miss) |
| Peak throughput | 19-35 M accesses/sec |
| Sustainable throughput | ~20 M accesses/sec |
| Memory bandwidth needed | ~80 GB/s (well within HBM2) |

---

## 5. Bill of Materials

### 5.1 Development Hardware

| Item | Model | Quantity | Unit Price | Total |
|------|-------|----------|------------|-------|
| FPGA Board | Xilinx Alveo U280 | 1 | $8,000 | $8,000 |
| Host Server | Dell R750 (or similar) | 1 | $5,000 | $5,000 |
| NVMe SSD | Samsung 990 Pro 2TB | 2 | $200 | $400 |
| Development PC | Workstation | 1 | $2,000 | $2,000 |
| Oscilloscope | Keysight MSOX4034A | 1 | $15,000 | $15,000 |
| Logic Analyzer | Saleae Logic Pro 16 | 1 | $1,500 | $1,500 |
| Misc cables/adapters | — | — | $500 | $500 |
| **TOTAL HARDWARE** | | | | **$32,400** |

### 5.2 Software/IP

| Item | Vendor | License | Cost |
|------|--------|---------|------|
| Vivado Design Suite | Xilinx | Enterprise | $3,000/yr |
| DDR4 Controller IP | Xilinx | Included | $0 |
| HBM2 Controller IP | Xilinx | Included | $0 |
| PCIe IP | Xilinx | Included | $0 |
| **TOTAL SOFTWARE** | | | **$3,000/yr** |

### 5.3 Total Prototype Cost

| Category | Cost |
|----------|------|
| Hardware | $32,400 |
| Software (1 year) | $3,000 |
| Engineering (3 months) | $60,000* |
| Contingency (20%) | $19,080 |
| **TOTAL** | **~$115,000** |

*Assuming 1 senior FPGA engineer at $200K/yr fully burdened

### 5.4 Lower-Cost Alternative

| Item | Model | Cost | Tradeoff |
|------|-------|------|----------|
| FPGA Board | Xilinx Kria KV260 | $250 | No HBM, use DDR only |
| Host | Existing PC | $0 | Slower PCIe |
| **TOTAL** | | **~$5,000** | Proof-of-concept only |

---

## 6. Development Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PROTOTYPE DEVELOPMENT TIMELINE                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MONTH 1-2: RTL Development                                                │
│  ═══════════════════════════                                               │
│  Week 1-2:  Event Embedder + Fast Coherence modules                        │
│  Week 3-4:  BCVF Gate module                                               │
│  Week 5-6:  Phase Integrator module                                        │
│  Week 7-8:  Tier managers + Decision arbiter                               │
│  Deliverable: Simulated RTL passing unit tests                             │
│                                                                             │
│  MONTH 3: Integration                                                       │
│  ═══════════════════                                                       │
│  Week 9-10:  Integrate with DDR4 controller                                │
│  Week 11-12: Integrate with HBM2 controller                                │
│  Week 12:    Integrate with PCIe host interface                            │
│  Deliverable: Bitstream that boots and responds to host                    │
│                                                                             │
│  MONTH 4: Firmware + Host Software                                         │
│  ═════════════════════════════════                                         │
│  Week 13-14: ARM firmware for SCC + slow coherence                         │
│  Week 15-16: Host driver and test harness                                  │
│  Deliverable: End-to-end data path working                                 │
│                                                                             │
│  MONTH 5: Validation                                                        │
│  ════════════════════                                                       │
│  Week 17-18: Functional validation with synthetic traces                   │
│  Week 19-20: Performance measurement and optimization                      │
│  Deliverable: Validated prototype with benchmark results                   │
│                                                                             │
│  MONTH 6: Documentation + Handoff                                          │
│  ═══════════════════════════════                                           │
│  Week 21-22: Documentation and reproducibility                             │
│  Week 23-24: Knowledge transfer and future roadmap                         │
│  Deliverable: Complete prototype package                                   │
│                                                                             │
│  MILESTONES:                                                               │
│  ├─ M1 (Week 8):  RTL simulation passing                                  │
│  ├─ M2 (Week 12): First bitstream boots                                   │
│  ├─ M3 (Week 16): End-to-end data path                                    │
│  ├─ M4 (Week 20): Benchmark results                                       │
│  └─ M5 (Week 24): Handoff complete                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. What the Prototype Proves

### 7.1 Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Timing closure | 250 MHz | Vivado timing report |
| Latency overhead | <50ns per access | Oscilloscope measurement |
| Throughput | >10M accesses/sec | Host benchmark |
| Hit rate improvement | >10% vs LRU | Trace replay comparison |
| Resource utilization | <10% of Alveo | Vivado utilization report |
| Power | <50W total board | Power meter |

### 7.2 What Success Means

If the prototype meets all criteria:

1. **Timing is feasible:** CTM+ can run at memory controller speeds
2. **Overhead is acceptable:** ~50ns is negligible vs memory latency
3. **Hardware fits:** Could be integrated into real memory controller
4. **Algorithm works in hardware:** Not just simulation artifact

### 7.3 What Success Does NOT Mean

| Does NOT Prove | Why | Next Step |
|----------------|-----|-----------|
| Production ready | FPGA ≠ ASIC | Tape-out study |
| Power optimized | FPGA is inefficient | ASIC power analysis |
| Manufacturable | No yield/reliability data | Fab partnership |
| Cost effective | Prototype ≠ production | BOM analysis |

---

## 8. Alternative: Software-Defined Prototype

If hardware prototype is too expensive, a software-defined approach:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SOFTWARE-DEFINED CTM+ (Lower cost alternative)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Instead of FPGA, implement CTM+ as:                                       │
│                                                                             │
│  Option A: Linux kernel module                                             │
│  ───────────────────────────                                               │
│  • Intercept page faults                                                   │
│  • Manage DRAM as tier-0, swap as tier-1                                  │
│  • CTM+ logic in kernel space                                              │
│  • Cost: $0 (software only)                                                │
│  • Proves: Algorithm works with real memory                                │
│  • Doesn't prove: Hardware timing                                          │
│                                                                             │
│  Option B: CXL memory expander emulation                                   │
│  ──────────────────────────────────────                                    │
│  • Use QEMU with CXL emulation                                             │
│  • CTM+ logic in emulated controller                                       │
│  • Cost: $0 (software only)                                                │
│  • Proves: CXL integration feasible                                        │
│  • Doesn't prove: Real CXL timing                                          │
│                                                                             │
│  Option C: SSD firmware modification                                       │
│  ─────────────────────────────────                                         │
│  • Partner with SSD vendor (OpenSSD, etc.)                                │
│  • Add CTM+ to FTL layer                                                   │
│  • Cost: ~$5,000 (dev board)                                              │
│  • Proves: Works in real storage controller                                │
│  • Doesn't prove: Memory (not storage) use case                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Summary

### What a Hardware Prototype Is

| Aspect | Description |
|--------|-------------|
| **Physical form** | FPGA development board (Alveo U280) |
| **Implementation** | Verilog RTL for fast path, C firmware for slow path |
| **Integration** | PCIe to host, DDR4 + HBM2 for tiered memory |
| **Cost** | ~$35K hardware, ~$115K total with engineering |
| **Timeline** | 6 months to validated prototype |

### What It Proves

| Proves | Doesn't Prove |
|--------|---------------|
| CTM+ meets timing constraints | Production cost |
| Hardware resource requirements | Manufacturing yield |
| Real latency overhead | Long-term reliability |
| Algorithm works in silicon | ASIC power consumption |

### Decision Framework

| Budget | Recommendation |
|--------|----------------|
| $0 | Use Python simulator (already done) |
| $5K | Software-defined prototype (kernel module) |
| $35K | FPGA hardware prototype (this spec) |
| $500K+ | ASIC tape-out study |

---

**Document End**

*Symbol-U Research Team - January 2026*
