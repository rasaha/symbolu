// =============================================================================
// Fixed-Point Multiplier
// =============================================================================
// Performs signed fixed-point multiplication with configurable formats
// Used by PUE for alpha * gradient (UQ0.16 * Q2.30 -> Q2.30)
// and by SVG for position * direction cosine computations
// =============================================================================

module fixed_point_mult
#(
  parameter int AW   = 16,    // A operand width
  parameter int AF   = 16,    // A fractional bits
  parameter int BW   = 32,    // B operand width
  parameter int BF   = 30,    // B fractional bits
  parameter int OW   = 32,    // Output width
  parameter int OF   = 30     // Output fractional bits
)(
  input  logic                  clk,
  input  logic                  rst_n,

  input  logic signed [AW-1:0] a_in,
  input  logic signed [BW-1:0] b_in,
  input  logic                  valid_in,

  output logic signed [OW-1:0] result,
  output logic                  valid_out
);

  // Full product width
  localparam int PW = AW + BW;
  localparam int PF = AF + BF; // Total fractional bits in product

  // How many bits to shift right to align to output format
  localparam int SHIFT = PF - OF;

  logic signed [PW-1:0] product;
  logic                  valid_r;

  // Single-cycle multiply + shift (pipelined)
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      product   <= '0;
      valid_r   <= 1'b0;
    end else begin
      product   <= a_in * b_in;
      valid_r   <= valid_in;
    end
  end

  // Extract aligned result with rounding
  logic signed [PW-1:0] rounded;

  always_comb begin
    if (SHIFT > 0)
      rounded = product + (1 <<< (SHIFT - 1)); // Round to nearest
    else
      rounded = product;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      result    <= '0;
      valid_out <= 1'b0;
    end else begin
      valid_out <= valid_r;
      // Saturating extraction
      if (SHIFT > 0)
        result <= rounded[SHIFT +: OW];
      else
        result <= rounded[OW-1:0];
    end
  end

endmodule : fixed_point_mult
