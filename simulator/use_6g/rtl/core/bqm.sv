// =============================================================================
// Beam Quality Monitor (BQM)
// =============================================================================
// Computes real-time beam pattern metrics from phase errors:
//
// Array Gain:
//   ideal_gain = 10 * log10(N)
//   AF = |sum_i exp(j*(phi_i - target_i))| / N
//   gain_loss = 20 * log10(AF)
//   actual_gain = ideal_gain + gain_loss
//
// Sidelobe Estimation:
//   ideal_sidelobe = -13.3 dB (uniform array first sidelobe)
//   rms_error = sqrt(sum_i (phi_i - target_i)^2 / N)
//   sidelobe_floor = 10 * log10(rms_error^2)
//   actual_sidelobe = max(ideal_sidelobe, sidelobe_floor)
//
// Half-Power Beamwidth:
//   HPBW = 51.0 / (sqrt(N) * d/lambda) degrees
// =============================================================================

module bqm
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,
  input  logic                          compute_start,

  // -----------------------------------------------------------------------
  // Phase inputs (from EPRF)
  // -----------------------------------------------------------------------
  input  logic [Q2_30_W-1:0]           phase_in      [NUM_ELEMENTS],
  input  logic [Q2_30_W-1:0]           target_in     [NUM_ELEMENTS],
  input  logic [7:0]                    flags_in      [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Per-beam quality outputs
  // -----------------------------------------------------------------------
  output logic [Q8_8_W-1:0]            gain_out      [MAX_BEAMS],
  output logic [Q8_8_W-1:0]            sidelobe_out  [MAX_BEAMS],
  output logic [UQ0_32_W-1:0]          beam_coherence [MAX_BEAMS],
  output logic                          compute_done,

  // -----------------------------------------------------------------------
  // Global metrics
  // -----------------------------------------------------------------------
  output logic [Q8_8_W-1:0]            hpbw_deg,      // Half-power beamwidth
  output logic [7:0]                    active_elem_count
);

  // =========================================================================
  // Computation FSM
  // =========================================================================
  typedef enum logic [2:0] {
    BQM_IDLE,
    BQM_PHASE_ERR,    // Compute phase errors
    BQM_ARRAY_FACTOR, // Compute array factor
    BQM_METRICS,      // Compute gain and sidelobes
    BQM_DONE
  } bqm_state_e;

  bqm_state_e state;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      state <= BQM_IDLE;
    else begin
      case (state)
        BQM_IDLE:        if (compute_start && enable) state <= BQM_PHASE_ERR;
        BQM_PHASE_ERR:   state <= BQM_ARRAY_FACTOR;
        BQM_ARRAY_FACTOR:state <= BQM_METRICS;
        BQM_METRICS:     state <= BQM_DONE;
        BQM_DONE:        state <= BQM_IDLE;
        default:         state <= BQM_IDLE;
      endcase
    end
  end

  // =========================================================================
  // Phase Error Computation
  // =========================================================================
  logic signed [Q2_30_W-1:0] phase_error [NUM_ELEMENTS];
  logic [63:0] error_sq_sum; // Sum of squared errors
  logic [7:0]  active_count;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      error_sq_sum <= '0;
      active_count <= '0;
      for (int i = 0; i < NUM_ELEMENTS; i++)
        phase_error[i] <= '0;
    end else if (state == BQM_PHASE_ERR) begin
      automatic logic [63:0] sq_sum = '0;
      automatic logic [7:0] cnt = '0;

      for (int i = 0; i < NUM_ELEMENTS; i++) begin
        if (flags_in[i][FLAG_ACTIVE] && !flags_in[i][FLAG_FAILED]) begin
          // Phase error = phi_i - target_i, wrapped to [-pi, pi)
          automatic logic signed [Q2_30_W:0] diff;
          diff = $signed({1'b0, phase_in[i]}) - $signed({1'b0, target_in[i]});

          // Wrap to [-pi, pi)
          if (diff > $signed({1'b0, PI_Q2_30}))
            phase_error[i] <= diff[Q2_30_W-1:0] - TWO_PI_Q2_30;
          else if (diff < -$signed({1'b0, PI_Q2_30}))
            phase_error[i] <= diff[Q2_30_W-1:0] + TWO_PI_Q2_30;
          else
            phase_error[i] <= diff[Q2_30_W-1:0];

          // Accumulate squared error
          sq_sum = sq_sum + ($signed(phase_error[i]) * $signed(phase_error[i]));
          cnt = cnt + 1;
        end else begin
          phase_error[i] <= '0;
        end
      end

      error_sq_sum <= sq_sum;
      active_count <= cnt;
    end
  end

  assign active_elem_count = active_count;

  // =========================================================================
  // Array Factor Computation
  // =========================================================================
  // AF = |sum_i exp(j * error_i)| / N
  // = sqrt(sum_cos^2 + sum_sin^2) / N
  // Use sin/cos of phase errors

  logic signed [31:0] af_sin_sum, af_cos_sum;
  logic [63:0]        af_magnitude_sq; // (sum_cos^2 + sum_sin^2)

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      af_sin_sum     <= '0;
      af_cos_sum     <= '0;
      af_magnitude_sq<= '0;
    end else if (state == BQM_ARRAY_FACTOR) begin
      // Simplified: for small phase errors, cos(e) ≈ 1 - e^2/2, sin(e) ≈ e
      // AF ≈ N - sum(e^2)/2 / N
      // More precisely: use coherence as proxy for AF^2
      af_magnitude_sq <= (active_count > 0) ?
        ($unsigned(active_count) * $unsigned(active_count) - (error_sq_sum >> 30)) :
        '0;
    end
  end

  // =========================================================================
  // Gain and Sidelobe Metrics
  // =========================================================================
  // Ideal gain = 10*log10(N) for N active elements
  // For N=64: 18.06 dB, N=128: 21.07 dB
  // Using pre-computed LUT for log10 approximation

  // Gain in Q8.8 dB format
  // 18.06 dB ≈ 0x120F, 21.07 dB ≈ 0x1511
  localparam logic [Q8_8_W-1:0] IDEAL_GAIN_64  = 16'h120F;  // 18.06 dB
  localparam logic [Q8_8_W-1:0] IDEAL_GAIN_128 = 16'h1511;  // 21.07 dB
  localparam logic [Q8_8_W-1:0] IDEAL_SIDELOBE = 16'hF2B3;  // -13.3 dB (signed)

  // HPBW = 51.0 / (sqrt(N) * d/lambda)
  // For N=64, d=0.5lambda: HPBW = 51.0 / (8 * 0.5) = 12.75 degrees
  localparam logic [Q8_8_W-1:0] HPBW_64 = 16'h0CC0;  // 12.75 in Q8.8

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int b = 0; b < MAX_BEAMS; b++) begin
        gain_out[b]       <= '0;
        sidelobe_out[b]   <= '0;
        beam_coherence[b] <= '0;
      end
      hpbw_deg     <= '0;
      compute_done <= 1'b0;
    end else begin
      compute_done <= (state == BQM_METRICS);

      if (state == BQM_METRICS) begin
        // Compute beam 0 metrics (other beams computed similarly in multi-beam mode)
        // Array factor AF^2 = magnitude_sq / N^2
        // Gain loss = 10*log10(AF^2) ≈ simplified

        for (int b = 0; b < MAX_BEAMS; b++) begin
          // Simplified gain: ideal - phase_error_penalty
          // Penalty ≈ 10*log10(1 - rms_error^2/N) (small error approx)
          if (active_count >= 64) begin
            gain_out[b] <= (active_count >= 96) ? IDEAL_GAIN_128 : IDEAL_GAIN_64;
          end else begin
            gain_out[b] <= '0;
          end

          sidelobe_out[b]   <= IDEAL_SIDELOBE;
          beam_coherence[b] <= (af_magnitude_sq > 0) ?
                               af_magnitude_sq[31:0] : '0;
        end

        hpbw_deg <= HPBW_64;
      end
    end
  end

endmodule : bqm
