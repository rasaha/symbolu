// =============================================================================
// Phase Wrapping Unit
// =============================================================================
// Wraps phase values to [0, 2*pi) range in Q2.30 format
// Handles both overflow (>2pi) and underflow (<0)
// Used by PUE after phase update: phi = (phi + delta) mod 2pi
// =============================================================================

module phase_wrap
  import use_6g_pkg::*;
(
  // Input: extended phase that may be outside [0, 2pi)
  // 33 bits to handle single add overflow
  input  logic signed [Q2_30_W:0]  phase_in,

  // Output: wrapped to [0, 2pi)
  output logic [Q2_30_W-1:0]       phase_out
);

  logic signed [Q2_30_W:0] adjusted;

  always_comb begin
    adjusted = phase_in;

    // Wrap negative values
    if (adjusted < 0) begin
      adjusted = adjusted + $signed({1'b0, TWO_PI_Q2_30});
    end

    // Wrap values >= 2*pi
    if (adjusted >= $signed({1'b0, TWO_PI_Q2_30})) begin
      adjusted = adjusted - $signed({1'b0, TWO_PI_Q2_30});
    end

    // Second pass for edge cases (double overflow)
    if (adjusted < 0) begin
      adjusted = adjusted + $signed({1'b0, TWO_PI_Q2_30});
    end
    if (adjusted >= $signed({1'b0, TWO_PI_Q2_30})) begin
      adjusted = adjusted - $signed({1'b0, TWO_PI_Q2_30});
    end

    phase_out = adjusted[Q2_30_W-1:0];
  end

endmodule : phase_wrap
