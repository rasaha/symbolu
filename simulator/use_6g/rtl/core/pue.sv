// =============================================================================
// Phase Update Engine (PUE) — U4 Patent Formula
// =============================================================================
// Applies adaptive learning rate and updates all 128 element phases in 1 cycle:
//   alpha = adapt(coherence_history)
//   delta_i = alpha * gradient_i
//   phi_i(t+1) = (phi_i(t) + delta_i) mod 2*pi
//
// Adaptive Learning Rate Logic:
//   Oscillating (>50% sign changes): 0.3 * base
//   High coherence (>0.9):           0.5 * base
//   Low coherence (<0.5):            1.5 * base
//   Normal:                          1.0 * base
//
// Key hardware: 128 x 16-bit multipliers, 128 x 32-bit adders, 1 adaptation FSM
// =============================================================================

module pue
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,
  input  logic                          start,

  // -----------------------------------------------------------------------
  // Configuration registers
  // -----------------------------------------------------------------------
  input  logic [UQ0_16_W-1:0]          base_learning_rate,  // Default 0x199A (0.1)
  input  logic [UQ0_8_W-1:0]           lr_fast_mult,        // 1.5x multiplier
  input  logic [UQ0_8_W-1:0]           lr_fine_mult,        // 0.5x multiplier
  input  logic [UQ0_8_W-1:0]           lr_damp_mult,        // 0.3x multiplier
  input  logic [UQ0_8_W-1:0]           lr_track_mult,       // 0.7x multiplier
  input  logic [31:0]                   lr_adapt_window,     // Adaptation window (default 10)

  // -----------------------------------------------------------------------
  // Gradient inputs from MFU (128-wide)
  // -----------------------------------------------------------------------
  input  logic signed [Q2_30_W-1:0]    gradient_in [NUM_ELEMENTS],
  input  logic                          gradient_valid,

  // -----------------------------------------------------------------------
  // Current phases from EPRF
  // -----------------------------------------------------------------------
  input  logic [Q2_30_W-1:0]           phase_in    [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Coherence input (for adaptive LR)
  // -----------------------------------------------------------------------
  input  logic [UQ0_32_W-1:0]          coherence_in,

  // -----------------------------------------------------------------------
  // Updated phases output (128-wide)
  // -----------------------------------------------------------------------
  output logic [Q2_30_W-1:0]           phase_out   [NUM_ELEMENTS],
  output logic                          phase_valid,

  // -----------------------------------------------------------------------
  // Status
  // -----------------------------------------------------------------------
  output logic [UQ0_16_W-1:0]          current_lr,
  output logic [Q2_30_W-1:0]           mean_update,   // Mean |delta_phi|
  output logic                          busy
);

  // =========================================================================
  // Adaptive Learning Rate FSM
  // =========================================================================

  // Coherence history shift register
  logic [UQ0_32_W-1:0] coh_history [LR_ADAPT_WINDOW];
  logic [3:0]           coh_history_idx;
  logic                 coh_history_full;

  // Sign change detection
  logic [3:0]           sign_change_cnt;
  lr_condition_e        lr_condition;

  // Thresholds in UQ0.32
  localparam logic [UQ0_32_W-1:0] COH_HIGH = 32'hE6666666; // 0.9
  localparam logic [UQ0_32_W-1:0] COH_LOW  = 32'h80000000; // 0.5

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int i = 0; i < LR_ADAPT_WINDOW; i++)
        coh_history[i] <= '0;
      coh_history_idx  <= '0;
      coh_history_full <= 1'b0;
    end else if (gradient_valid) begin
      coh_history[coh_history_idx] <= coherence_in;
      if (coh_history_idx == LR_ADAPT_WINDOW - 1) begin
        coh_history_idx  <= '0;
        coh_history_full <= 1'b1;
      end else begin
        coh_history_idx  <= coh_history_idx + 1;
      end
    end
  end

  // Count sign changes in coherence history (oscillation detection)
  always_comb begin
    sign_change_cnt = '0;
    if (coh_history_full) begin
      for (int i = 1; i < LR_ADAPT_WINDOW; i++) begin
        // Detect if coherence went up then down or vice versa
        if ((coh_history[i] > coh_history[i-1] && i > 1 && coh_history[i-1] < coh_history[i-2]) ||
            (coh_history[i] < coh_history[i-1] && i > 1 && coh_history[i-1] > coh_history[i-2]))
          sign_change_cnt = sign_change_cnt + 1;
      end
    end
  end

  // Determine LR condition
  always_comb begin
    if (coh_history_full && sign_change_cnt > (LR_ADAPT_WINDOW / 2))
      lr_condition = LR_OSCILLATING;
    else if (coherence_in > COH_HIGH)
      lr_condition = LR_HIGH_COH;
    else if (coherence_in < COH_LOW)
      lr_condition = LR_LOW_COH;
    else
      lr_condition = LR_NORMAL;
  end

  // Compute adapted learning rate
  logic [UQ0_16_W-1:0] adapted_lr;

  always_comb begin
    case (lr_condition)
      LR_OSCILLATING: adapted_lr = (base_learning_rate * {8'd0, lr_damp_mult}) >> 8;
      LR_HIGH_COH:    adapted_lr = (base_learning_rate * {8'd0, lr_fine_mult}) >> 8;
      LR_LOW_COH:     adapted_lr = (base_learning_rate * {8'd0, lr_fast_mult}) >> 8;
      LR_NORMAL:       adapted_lr = base_learning_rate;
    endcase
  end

  assign current_lr = adapted_lr;

  // =========================================================================
  // Phase Update: 128-parallel multiply-add-wrap
  // =========================================================================
  typedef enum logic [1:0] {
    PUE_IDLE,
    PUE_COMPUTE,
    PUE_DONE
  } pue_state_e;

  pue_state_e pue_state;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      pue_state <= PUE_IDLE;
    else begin
      case (pue_state)
        PUE_IDLE:    if (start && enable && gradient_valid) pue_state <= PUE_COMPUTE;
        PUE_COMPUTE: pue_state <= PUE_DONE;
        PUE_DONE:    pue_state <= PUE_IDLE;
        default:     pue_state <= PUE_IDLE;
      endcase
    end
  end

  assign busy = (pue_state != PUE_IDLE);

  // 128 parallel phase updates
  logic signed [47:0] delta        [NUM_ELEMENTS]; // lr * gradient
  logic signed [Q2_30_W:0] new_phase_raw [NUM_ELEMENTS]; // 33-bit for overflow

  // Mean update accumulator
  logic [47:0] abs_delta_sum;

  always_comb begin
    abs_delta_sum = '0;
    for (int i = 0; i < NUM_ELEMENTS; i++) begin
      // delta_i = alpha * gradient_i
      // adapted_lr is UQ0.16, gradient_in is Q2.30 signed
      delta[i] = $signed({1'b0, adapted_lr}) * gradient_in[i];

      // new_phase = phase + delta (truncated to Q2.30)
      new_phase_raw[i] = $signed({1'b0, phase_in[i]}) +
                          $signed(delta[i][45:14]); // Align: 16+30-16 = shift by 14

      // Accumulate absolute deltas for mean update metric
      if (delta[i] < 0)
        abs_delta_sum = abs_delta_sum + (-delta[i]);
      else
        abs_delta_sum = abs_delta_sum + delta[i];
    end
  end

  // Phase wrap and output
  genvar gi;
  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_wrap
      logic [Q2_30_W-1:0] wrapped_phase;

      phase_wrap u_wrap (
        .phase_in  (new_phase_raw[gi]),
        .phase_out (wrapped_phase)
      );

      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
          phase_out[gi] <= '0;
        else if (pue_state == PUE_COMPUTE)
          phase_out[gi] <= wrapped_phase;
      end
    end
  endgenerate

  // Output valid
  logic phase_valid_r;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      phase_valid_r <= 1'b0;
    else
      phase_valid_r <= (pue_state == PUE_COMPUTE);
  end
  assign phase_valid = phase_valid_r;

  // Mean update metric: sum / 128 (shift right by 7)
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      mean_update <= '0;
    else if (pue_state == PUE_COMPUTE)
      mean_update <= abs_delta_sum[38:7]; // Approximate mean
  end

endmodule : pue
