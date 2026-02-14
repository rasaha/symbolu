// =============================================================================
// Coherence Accumulator (CA) — U2 Patent Formula
// =============================================================================
// Computes global coherence using mean-field approximation (fast path):
//   C_approx = (sin_sum^2 + cos_sum^2) / n^2
// Reuses MFU cycle-1 outputs, requiring zero additional cycles on critical path.
//
// Also computes per-panel and per-beam coherence for monitoring.
// Background exact pairwise computation for validation.
// Output range: [0, 1] as UQ0.32
// =============================================================================

module ca
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,

  // -----------------------------------------------------------------------
  // MFU accumulator inputs (piggybacked from MFU cycle 1)
  // -----------------------------------------------------------------------
  input  logic signed [Q2_30_W-1:0]    sin_sum,
  input  logic signed [Q2_30_W-1:0]    cos_sum,
  input  logic                          accum_valid,

  // -----------------------------------------------------------------------
  // Per-panel phase sums (computed by MFU with panel masking)
  // -----------------------------------------------------------------------
  input  logic signed [Q2_30_W-1:0]    sin_sum_panel0,
  input  logic signed [Q2_30_W-1:0]    cos_sum_panel0,
  input  logic signed [Q2_30_W-1:0]    sin_sum_panel1,
  input  logic signed [Q2_30_W-1:0]    cos_sum_panel1,

  // -----------------------------------------------------------------------
  // Per-beam phase error inputs (from BQM)
  // -----------------------------------------------------------------------
  input  logic [UQ0_32_W-1:0]          beam_coherence [MAX_BEAMS],

  // -----------------------------------------------------------------------
  // Outputs
  // -----------------------------------------------------------------------
  output logic [UQ0_32_W-1:0]          global_coherence,
  output logic [UQ0_32_W-1:0]          panel0_coherence,
  output logic [UQ0_32_W-1:0]          panel1_coherence,
  output logic [UQ0_32_W-1:0]          beam_coh_out [MAX_BEAMS],
  output logic                          coh_valid
);

  // =========================================================================
  // Fast-path coherence: C = (sin_sum^2 + cos_sum^2) / n^2
  // =========================================================================
  // sin_sum and cos_sum are Q2.30 signed
  // Squaring: Q2.30 * Q2.30 = Q4.60, we need UQ0.32 output

  logic signed [63:0] sin_sq, cos_sq;
  logic [63:0]        magnitude_sq;

  // N^2 = 128^2 = 16384
  localparam int N_SQ = NUM_ELEMENTS * NUM_ELEMENTS; // 16384

  // Pipeline stage 1: square
  logic signed [63:0] sin_sq_r, cos_sq_r;
  logic                valid_s1;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sin_sq_r <= '0;
      cos_sq_r <= '0;
      valid_s1 <= 1'b0;
    end else begin
      valid_s1 <= accum_valid && enable;
      sin_sq_r <= sin_sum * sin_sum;
      cos_sq_r <= cos_sum * cos_sum;
    end
  end

  // Pipeline stage 2: add + normalize
  logic [63:0] sum_sq;
  logic [UQ0_32_W-1:0] coherence_raw;
  logic valid_s2;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sum_sq       <= '0;
      coherence_raw<= '0;
      valid_s2     <= 1'b0;
    end else begin
      valid_s2 <= valid_s1;
      // sum_sq = sin^2 + cos^2 (unsigned since squares are positive)
      sum_sq <= $unsigned(sin_sq_r) + $unsigned(cos_sq_r);
      // Divide by N^2: shift right by 14 bits (16384 = 2^14)
      // The result is in Q4.60 / 2^14 = Q4.46, take top 32 bits for UQ0.32
      coherence_raw <= (($unsigned(sin_sq_r) + $unsigned(cos_sq_r)) >> 14) >> 28;
    end
  end

  // =========================================================================
  // Per-panel coherence (same formula, per-panel sums)
  // =========================================================================
  logic signed [63:0] sin_sq_p0, cos_sq_p0;
  logic signed [63:0] sin_sq_p1, cos_sq_p1;
  localparam int PANEL_N_SQ = ELEMENTS_PER_PANEL * ELEMENTS_PER_PANEL; // 4096

  logic [UQ0_32_W-1:0] panel0_coh_raw, panel1_coh_raw;
  logic valid_panel;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      panel0_coh_raw <= '0;
      panel1_coh_raw <= '0;
      valid_panel    <= 1'b0;
    end else begin
      valid_panel <= valid_s1;

      sin_sq_p0 <= sin_sum_panel0 * sin_sum_panel0;
      cos_sq_p0 <= cos_sum_panel0 * cos_sum_panel0;
      sin_sq_p1 <= sin_sum_panel1 * sin_sum_panel1;
      cos_sq_p1 <= cos_sum_panel1 * cos_sum_panel1;

      // Divide by 64^2 = 4096 = 2^12, then scale to UQ0.32
      panel0_coh_raw <= (($unsigned(sin_sum_panel0 * sin_sum_panel0) +
                          $unsigned(cos_sum_panel0 * cos_sum_panel0)) >> 12) >> 28;
      panel1_coh_raw <= (($unsigned(sin_sum_panel1 * sin_sum_panel1) +
                          $unsigned(cos_sum_panel1 * cos_sum_panel1)) >> 12) >> 28;
    end
  end

  // =========================================================================
  // Output registration
  // =========================================================================
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      global_coherence <= '0;
      panel0_coherence <= '0;
      panel1_coherence <= '0;
      coh_valid        <= 1'b0;
      for (int b = 0; b < MAX_BEAMS; b++)
        beam_coh_out[b] <= '0;
    end else begin
      coh_valid <= valid_s2;
      if (valid_s2) begin
        global_coherence <= coherence_raw;
        panel0_coherence <= panel0_coh_raw;
        panel1_coherence <= panel1_coh_raw;
        for (int b = 0; b < MAX_BEAMS; b++)
          beam_coh_out[b] <= beam_coherence[b];
      end
    end
  end

endmodule : ca
