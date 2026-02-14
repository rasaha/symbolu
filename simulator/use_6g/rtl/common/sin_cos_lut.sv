// =============================================================================
// Sin/Cos Lookup Table with Interpolation
// =============================================================================
// 10-bit address (1024 entries), 16-bit signed output
// Covers [0, pi/2) with quadrant mapping for full [0, 2pi) range
// Used by MFU (128 instances) and SVG (CORDIC preprocessing)
// =============================================================================

module sin_cos_lut
  import use_6g_pkg::*;
(
  input  logic                      clk,
  input  logic                      rst_n,

  // Input phase in Q2.30 format [0, 2pi)
  input  logic [Q2_30_W-1:0]       phase_in,
  input  logic                      valid_in,

  // Outputs: sin and cos in Q1.15 signed format
  output logic signed [15:0]        sin_out,
  output logic signed [15:0]        cos_out,
  output logic                      valid_out
);

  // -------------------------------------------------------------------------
  // Quarter-wave LUT: stores sin(x) for x in [0, pi/2)
  // 1024 entries x 16-bit signed, max value = 32767 = sin(pi/2)
  // -------------------------------------------------------------------------
  logic signed [15:0] sin_lut [0:SIN_COS_LUT_DEPTH-1];

  // Initialize LUT with quarter-wave sine values
  initial begin
    for (int i = 0; i < SIN_COS_LUT_DEPTH; i++) begin
      // sin(i * pi/2 / 1024) * 32767
      // Using integer approximation for synthesis
      sin_lut[i] = 16'(integer'($sin(real'(i) * 3.14159265358979 / 2.0 / 1024.0) * 32767.0));
    end
  end

  // -------------------------------------------------------------------------
  // Phase decomposition: extract quadrant and LUT index from Q2.30 phase
  // -------------------------------------------------------------------------
  // Phase [31:30] = integer part (0-6), [29:0] = fractional
  // Quadrant from bits [31:29] mapped to [0,3]

  logic [1:0]                    quadrant;
  logic [SIN_COS_LUT_AW-1:0]    lut_addr;
  logic [SIN_COS_LUT_AW-1:0]    lut_addr_cos;

  // Pipeline stage 0: decode quadrant and address
  logic [1:0]                    quadrant_r;
  logic                          valid_r;

  // Normalize phase: divide by (2*pi) to get [0,1), then extract quadrant
  // phase_in is Q2.30, TWO_PI is ~6.283 in Q2.30
  // Fraction of full circle = phase_in / TWO_PI
  // Simplified: use top bits of phase relative to pi/2 boundaries
  // pi/2 in Q2.30 ≈ 0x06487ED5
  localparam logic [Q2_30_W-1:0] HALF_PI  = 32'h06487ED5;
  localparam logic [Q2_30_W-1:0] THREE_PI_HALF = 32'h12D97C7F;

  always_comb begin
    // Determine quadrant based on phase value
    if (phase_in < HALF_PI) begin
      quadrant = 2'd0;
      // Map [0, pi/2) to [0, 1023]
      lut_addr = phase_in[29:20]; // Use top 10 fractional bits relative to quadrant
    end else if (phase_in < PI_Q2_30) begin
      quadrant = 2'd1;
      lut_addr = (PI_Q2_30 - phase_in) >> 20; // Mirror
    end else if (phase_in < THREE_PI_HALF) begin
      quadrant = 2'd2;
      lut_addr = (phase_in - PI_Q2_30) >> 20;
    end else begin
      quadrant = 2'd3;
      lut_addr = (TWO_PI_Q2_30 - phase_in) >> 20;
    end
  end

  // -------------------------------------------------------------------------
  // Pipeline stage 1: LUT read + quadrant sign application
  // -------------------------------------------------------------------------
  logic signed [15:0] sin_raw, cos_raw;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      quadrant_r <= 2'd0;
      valid_r    <= 1'b0;
      sin_raw    <= 16'd0;
      cos_raw    <= 16'd0;
    end else begin
      valid_r    <= valid_in;
      quadrant_r <= quadrant;
      sin_raw    <= sin_lut[lut_addr];
      // cos(x) = sin(pi/2 - x), use complementary address
      cos_raw    <= sin_lut[SIN_COS_LUT_DEPTH - 1 - lut_addr];
    end
  end

  // -------------------------------------------------------------------------
  // Pipeline stage 2: Apply quadrant sign
  // -------------------------------------------------------------------------
  // Q0: sin+, cos+  Q1: sin+, cos-  Q2: sin-, cos-  Q3: sin-, cos+
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sin_out   <= 16'd0;
      cos_out   <= 16'd0;
      valid_out <= 1'b0;
    end else begin
      valid_out <= valid_r;
      case (quadrant_r)
        2'd0: begin sin_out <=  sin_raw; cos_out <=  cos_raw; end
        2'd1: begin sin_out <=  sin_raw; cos_out <= -cos_raw; end
        2'd2: begin sin_out <= -sin_raw; cos_out <= -cos_raw; end
        2'd3: begin sin_out <= -sin_raw; cos_out <=  cos_raw; end
      endcase
    end
  end

endmodule : sin_cos_lut
