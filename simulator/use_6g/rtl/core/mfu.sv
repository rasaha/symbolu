// =============================================================================
// Mean-Field Unit (MFU) — U3 Patent Formula
// =============================================================================
// Computes O(n) mean-field gradient for all 128 elements in 2 cycles:
//   Cycle 1: sin_sum = sum(sin(phi_i)), cos_sum = sum(cos(phi_i))
//            phi_bar = atan2(sin_sum, cos_sum)
//   Cycle 2: grad_i = -sin(phi_i - phi_bar) for all i (128-parallel)
//
// Beamforming mode override:
//   grad_i = target_phase_i - phi_i (wrapped to [-pi, pi])
//
// Key hardware: 128 sin/cos LUTs, 7-level adder tree, 1 CORDIC atan2
// =============================================================================

module mfu
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,
  input  logic                          use_target,      // Beamforming mode
  input  logic                          start,           // Trigger computation

  // -----------------------------------------------------------------------
  // Phase inputs from EPRF (128-wide parallel)
  // -----------------------------------------------------------------------
  input  logic [Q2_30_W-1:0]           phase_in     [NUM_ELEMENTS],
  input  logic [Q2_30_W-1:0]           target_in    [NUM_ELEMENTS],
  input  logic [7:0]                    flags_in     [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Gradient outputs (128-wide parallel)
  // -----------------------------------------------------------------------
  output logic signed [Q2_30_W-1:0]    gradient_out [NUM_ELEMENTS],
  output logic                          gradient_valid,

  // -----------------------------------------------------------------------
  // Accumulator outputs (reused by CA for coherence)
  // -----------------------------------------------------------------------
  output logic signed [Q2_30_W-1:0]    sin_sum_out,
  output logic signed [Q2_30_W-1:0]    cos_sum_out,
  output logic [Q2_30_W-1:0]           phi_mean_out,
  output logic                          accum_valid,

  // -----------------------------------------------------------------------
  // Status
  // -----------------------------------------------------------------------
  output logic                          busy
);

  // =========================================================================
  // FSM
  // =========================================================================
  typedef enum logic [2:0] {
    MFU_IDLE,
    MFU_SINCOS,      // Cycle 1: sin/cos LUT lookups
    MFU_ACCUM,       // Cycle 1 continued: accumulate + atan2 start
    MFU_ATAN2_WAIT,  // Wait for CORDIC pipeline
    MFU_GRADIENT,    // Cycle 2: compute per-element gradient
    MFU_DONE
  } mfu_state_e;

  mfu_state_e state, state_next;

  // Pipeline counter for CORDIC wait
  logic [4:0] cordic_cnt;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      state <= MFU_IDLE;
    else
      state <= state_next;
  end

  always_comb begin
    state_next = state;
    case (state)
      MFU_IDLE:       if (start && enable) state_next = MFU_SINCOS;
      MFU_SINCOS:     state_next = MFU_ACCUM;
      MFU_ACCUM:      state_next = MFU_ATAN2_WAIT;
      MFU_ATAN2_WAIT: if (atan2_valid) state_next = MFU_GRADIENT;
      MFU_GRADIENT:   state_next = MFU_DONE;
      MFU_DONE:       state_next = MFU_IDLE;
      default:        state_next = MFU_IDLE;
    endcase
  end

  assign busy = (state != MFU_IDLE);

  // =========================================================================
  // Cycle 1: 128 Parallel Sin/Cos Lookups
  // =========================================================================
  logic signed [15:0] sin_vals [NUM_ELEMENTS];
  logic signed [15:0] cos_vals [NUM_ELEMENTS];
  logic               sincos_valid [NUM_ELEMENTS];

  genvar gi;
  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_sincos
      sin_cos_lut u_sincos (
        .clk       (clk),
        .rst_n     (rst_n),
        .phase_in  (phase_in[gi]),
        .valid_in  (state == MFU_SINCOS && flags_in[gi][FLAG_ACTIVE]),
        .sin_out   (sin_vals[gi]),
        .cos_out   (cos_vals[gi]),
        .valid_out (sincos_valid[gi])
      );
    end
  endgenerate

  // =========================================================================
  // Cycle 1: Adder Trees for sin_sum and cos_sum
  // =========================================================================
  // Extend sin/cos from 16-bit to 32-bit for accumulation
  logic signed [31:0] sin_extended [NUM_ELEMENTS];
  logic signed [31:0] cos_extended [NUM_ELEMENTS];

  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_extend
      assign sin_extended[gi] = {{16{sin_vals[gi][15]}}, sin_vals[gi]};
      assign cos_extended[gi] = {{16{cos_vals[gi][15]}}, cos_vals[gi]};
    end
  endgenerate

  logic signed [38:0] sin_tree_sum; // 32 + log2(128) = 39 bits
  logic signed [38:0] cos_tree_sum;

  adder_tree #(
    .N  (NUM_ELEMENTS),
    .DW (32)
  ) u_sin_tree (
    .data_in (sin_extended),
    .sum_out (sin_tree_sum)
  );

  adder_tree #(
    .N  (NUM_ELEMENTS),
    .DW (32)
  ) u_cos_tree (
    .data_in (cos_extended),
    .sum_out (cos_tree_sum)
  );

  // Latch accumulated sums
  logic signed [Q2_30_W-1:0] sin_sum_r;
  logic signed [Q2_30_W-1:0] cos_sum_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sin_sum_r <= '0;
      cos_sum_r <= '0;
    end else if (state == MFU_ACCUM) begin
      // Scale down: sin_tree_sum is in Q1.15 * 128, normalize
      sin_sum_r <= sin_tree_sum[Q2_30_W-1:0]; // Truncate to 32b
      cos_sum_r <= cos_tree_sum[Q2_30_W-1:0];
    end
  end

  assign sin_sum_out = sin_sum_r;
  assign cos_sum_out = cos_sum_r;

  // =========================================================================
  // Cycle 1: CORDIC atan2 for circular mean
  // =========================================================================
  logic                 atan2_valid;
  logic [Q2_30_W-1:0]  phi_mean;

  cordic_atan2 #(
    .STAGES (16),
    .DW     (Q2_30_W)
  ) u_atan2 (
    .clk       (clk),
    .rst_n     (rst_n),
    .y_in      (sin_sum_r),
    .x_in      (cos_sum_r),
    .valid_in  (state == MFU_ACCUM),
    .angle_out (phi_mean),
    .valid_out (atan2_valid)
  );

  // Latch mean phase
  logic [Q2_30_W-1:0] phi_mean_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      phi_mean_r <= '0;
    else if (atan2_valid)
      phi_mean_r <= phi_mean;
  end

  assign phi_mean_out = phi_mean_r;
  assign accum_valid  = atan2_valid;

  // =========================================================================
  // Cycle 2: Per-Element Gradient (128-parallel)
  // =========================================================================
  // Normal mode:  grad_i = -sin(phi_i - phi_bar)
  // Beam mode:    grad_i = target_phase_i - phi_i, wrapped to [-pi, pi]

  // Phase differences
  logic [Q2_30_W-1:0] phase_diff [NUM_ELEMENTS];

  // Sin of phase difference (for normal mode)
  logic signed [15:0]  sin_diff [NUM_ELEMENTS];
  logic signed [15:0]  cos_diff_unused [NUM_ELEMENTS];
  logic                diff_valid [NUM_ELEMENTS];

  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_gradient

      // Phase difference: (phi_i - phi_bar) mod 2pi
      logic signed [Q2_30_W:0] diff_raw;
      logic [Q2_30_W-1:0]      diff_wrapped;

      assign diff_raw = $signed({1'b0, phase_in[gi]}) - $signed({1'b0, phi_mean_r});

      phase_wrap u_wrap (
        .phase_in  (diff_raw),
        .phase_out (diff_wrapped)
      );

      assign phase_diff[gi] = diff_wrapped;

      // Sin LUT for gradient computation (reuse sin_cos_lut instances)
      sin_cos_lut u_grad_sincos (
        .clk       (clk),
        .rst_n     (rst_n),
        .phase_in  (diff_wrapped),
        .valid_in  (state == MFU_GRADIENT && flags_in[gi][FLAG_ACTIVE]),
        .sin_out   (sin_diff[gi]),
        .cos_out   (cos_diff_unused[gi]),
        .valid_out (diff_valid[gi])
      );

      // Beamforming mode: target - current, wrapped to [-pi, pi]
      logic signed [Q2_30_W:0] beam_diff_raw;
      logic [Q2_30_W-1:0]      beam_diff_wrapped;
      logic signed [Q2_30_W-1:0] beam_grad;

      assign beam_diff_raw = $signed({1'b0, target_in[gi]}) - $signed({1'b0, phase_in[gi]});

      phase_wrap u_beam_wrap (
        .phase_in  (beam_diff_raw),
        .phase_out (beam_diff_wrapped)
      );

      // Convert [0, 2pi) to [-pi, pi) for beam gradient
      assign beam_grad = (beam_diff_wrapped > PI_Q2_30) ?
                         $signed(beam_diff_wrapped) - $signed(TWO_PI_Q2_30) :
                         $signed(beam_diff_wrapped);

    end
  endgenerate

  // Latch gradient outputs
  logic grad_valid_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      grad_valid_r <= 1'b0;
      for (int i = 0; i < NUM_ELEMENTS; i++)
        gradient_out[i] <= '0;
    end else begin
      grad_valid_r <= (state == MFU_GRADIENT);
      if (state == MFU_GRADIENT) begin
        for (int i = 0; i < NUM_ELEMENTS; i++) begin
          if (!flags_in[i][FLAG_ACTIVE] || flags_in[i][FLAG_FAILED]) begin
            gradient_out[i] <= '0; // Inactive/failed elements get zero gradient
          end else if (use_target) begin
            // Beamforming mode: gradient = target - current
            gradient_out[i] <= g_gradient[i].beam_grad;
          end else begin
            // Normal mode: gradient = -sin(phi_i - phi_bar)
            // Negate and sign-extend from 16-bit to 32-bit Q2.30
            gradient_out[i] <= -{{16{sin_diff[i][15]}}, sin_diff[i]};
          end
        end
      end
    end
  end

  assign gradient_valid = grad_valid_r;

endmodule : mfu
