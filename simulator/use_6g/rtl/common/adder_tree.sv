// =============================================================================
// Parameterized Adder Tree
// =============================================================================
// Reduces N inputs to 1 output via binary tree summation
// Configurable width and number of inputs
// Used by MFU for 128-element sin/cos accumulation (7-level tree)
// Combinational implementation for single-cycle operation
// =============================================================================

module adder_tree
  import use_6g_pkg::*;
#(
  parameter int N      = NUM_ELEMENTS,   // Number of inputs (128)
  parameter int DW     = 32,             // Data width per input (signed)
  parameter int OW     = DW + $clog2(N)  // Output width (with growth)
)(
  input  logic signed [DW-1:0]  data_in [N],
  output logic signed [OW-1:0]  sum_out
);

  // -------------------------------------------------------------------------
  // Tree reduction using recursive generate
  // -------------------------------------------------------------------------
  localparam int LEVELS = $clog2(N);

  // Internal wires for each level
  // Level 0: N inputs at DW bits
  // Level k: N/2^k values at DW+k bits
  logic signed [OW-1:0] tree [LEVELS+1][N];

  // Load inputs into level 0
  genvar i;
  generate
    for (i = 0; i < N; i++) begin : g_load
      assign tree[0][i] = {{(OW-DW){data_in[i][DW-1]}}, data_in[i]};
    end
  endgenerate

  // Generate tree levels
  genvar lvl, idx;
  generate
    for (lvl = 0; lvl < LEVELS; lvl++) begin : g_level
      localparam int PAIRS = N >> (lvl + 1);
      for (idx = 0; idx < PAIRS; idx++) begin : g_add
        assign tree[lvl+1][idx] = tree[lvl][2*idx] + tree[lvl][2*idx+1];
      end
      // Zero-fill unused slots
      for (idx = PAIRS; idx < N; idx++) begin : g_zero
        assign tree[lvl+1][idx] = '0;
      end
    end
  endgenerate

  assign sum_out = tree[LEVELS][0];

endmodule : adder_tree
