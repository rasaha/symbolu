// =============================================================================
// CORDIC atan2 Unit
// =============================================================================
// Computes atan2(y, x) using vectoring mode CORDIC
// 16-stage pipeline, Q2.30 output
// Used by MFU to compute circular mean: phi_bar = atan2(sin_sum, cos_sum)
// =============================================================================

module cordic_atan2
  import use_6g_pkg::*;
#(
  parameter int STAGES = 16,   // Number of CORDIC iterations
  parameter int DW     = 32    // Data width
)(
  input  logic               clk,
  input  logic               rst_n,

  // Inputs: y = sin_sum, x = cos_sum (Q2.30 signed)
  input  logic signed [DW-1:0] y_in,
  input  logic signed [DW-1:0] x_in,
  input  logic                 valid_in,

  // Output: angle in Q2.30 [0, 2pi)
  output logic [DW-1:0]        angle_out,
  output logic                 valid_out
);

  // -------------------------------------------------------------------------
  // CORDIC angle table: atan(2^-i) in Q2.30 format
  // -------------------------------------------------------------------------
  logic [DW-1:0] atan_table [0:STAGES-1];

  initial begin
    // atan(2^0)  = 0.7854 rad = 0x3243F6A9 in Q2.30
    atan_table[0]  = 32'h3243F6A9; // 45.0000 deg
    atan_table[1]  = 32'h1DAC6705; // 26.5651 deg
    atan_table[2]  = 32'h0FADBAFC; // 14.0362 deg
    atan_table[3]  = 32'h07F56EA7; //  7.1250 deg
    atan_table[4]  = 32'h03FEAB77; //  3.5763 deg
    atan_table[5]  = 32'h01FFD55B; //  1.7899 deg
    atan_table[6]  = 32'h00FFFAAB; //  0.8952 deg
    atan_table[7]  = 32'h007FFF55; //  0.4476 deg
    atan_table[8]  = 32'h003FFFEB; //  0.2238 deg
    atan_table[9]  = 32'h001FFFFD; //  0.1119 deg
    atan_table[10] = 32'h00100000; //  0.0560 deg
    atan_table[11] = 32'h00080000; //  0.0280 deg
    atan_table[12] = 32'h00040000; //  0.0140 deg
    atan_table[13] = 32'h00020000; //  0.0070 deg
    atan_table[14] = 32'h00010000; //  0.0035 deg
    atan_table[15] = 32'h00008000; //  0.0018 deg
  end

  // -------------------------------------------------------------------------
  // Pipeline registers
  // -------------------------------------------------------------------------
  logic signed [DW-1:0] x_stage [0:STAGES];
  logic signed [DW-1:0] y_stage [0:STAGES];
  logic signed [DW-1:0] z_stage [0:STAGES];
  logic [1:0]           quadrant_stage [0:STAGES];
  logic                 valid_stage [0:STAGES];

  // -------------------------------------------------------------------------
  // Pre-rotation: map to first quadrant
  // -------------------------------------------------------------------------
  logic signed [DW-1:0] x_pre, y_pre;
  logic [1:0]           quadrant_pre;

  always_comb begin
    // Determine quadrant and map to Q1
    if (x_in >= 0 && y_in >= 0) begin
      quadrant_pre = 2'd0; x_pre = x_in;  y_pre = y_in;
    end else if (x_in < 0 && y_in >= 0) begin
      quadrant_pre = 2'd1; x_pre = y_in;  y_pre = -x_in;
    end else if (x_in < 0 && y_in < 0) begin
      quadrant_pre = 2'd2; x_pre = -x_in; y_pre = -y_in;
    end else begin
      quadrant_pre = 2'd3; x_pre = -y_in; y_pre = x_in;
    end
  end

  // Load pipeline stage 0
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      x_stage[0]        <= '0;
      y_stage[0]        <= '0;
      z_stage[0]        <= '0;
      quadrant_stage[0] <= '0;
      valid_stage[0]    <= 1'b0;
    end else begin
      x_stage[0]        <= x_pre;
      y_stage[0]        <= y_pre;
      z_stage[0]        <= '0;
      quadrant_stage[0] <= quadrant_pre;
      valid_stage[0]    <= valid_in;
    end
  end

  // -------------------------------------------------------------------------
  // CORDIC vectoring iterations (drive y toward zero)
  // -------------------------------------------------------------------------
  genvar i;
  generate
    for (i = 0; i < STAGES; i++) begin : g_cordic_stage
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          x_stage[i+1]        <= '0;
          y_stage[i+1]        <= '0;
          z_stage[i+1]        <= '0;
          quadrant_stage[i+1] <= '0;
          valid_stage[i+1]    <= 1'b0;
        end else begin
          valid_stage[i+1]    <= valid_stage[i];
          quadrant_stage[i+1] <= quadrant_stage[i];

          if (y_stage[i] < 0) begin
            // Rotate clockwise (negative direction)
            x_stage[i+1] <= x_stage[i] - (y_stage[i] >>> i);
            y_stage[i+1] <= y_stage[i] + (x_stage[i] >>> i);
            z_stage[i+1] <= z_stage[i] - $signed(atan_table[i]);
          end else begin
            // Rotate counter-clockwise (positive direction)
            x_stage[i+1] <= x_stage[i] + (y_stage[i] >>> i);
            y_stage[i+1] <= y_stage[i] - (x_stage[i] >>> i);
            z_stage[i+1] <= z_stage[i] + $signed(atan_table[i]);
          end
        end
      end
    end
  endgenerate

  // -------------------------------------------------------------------------
  // Post-rotation: reconstruct full angle from quadrant
  // -------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      angle_out <= '0;
      valid_out <= 1'b0;
    end else begin
      valid_out <= valid_stage[STAGES];
      case (quadrant_stage[STAGES])
        2'd0: angle_out <= z_stage[STAGES];                                  // [0, pi/2)
        2'd1: angle_out <= HALF_PI + z_stage[STAGES];                        // [pi/2, pi)
        2'd2: angle_out <= PI_Q2_30 + z_stage[STAGES];                      // [pi, 3pi/2)
        2'd3: angle_out <= PI_Q2_30 + HALF_PI + z_stage[STAGES];            // [3pi/2, 2pi)
      endcase
    end
  end

  // Local constant
  localparam logic [Q2_30_W-1:0] HALF_PI = 32'h06487ED5;

endmodule : cordic_atan2
