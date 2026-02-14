// =============================================================================
// Threshold Comparator (TC) — U5 Patent Formula
// =============================================================================
// Lock detection state machine with hysteresis:
//   UNSYNCHRONIZED -> ACQUIRING -> LOCKED -> TRACKING -> LOST
//
// Lock conditions:
//   coherence >= 0.95 AND stable(variance < 0.001 over 5 samples)
// Unlock conditions:
//   coherence < 0.93 (threshold - 3*hysteresis)
// Tracking entry:
//   coherence drops below 0.93 but stays above 0.89
//
// U5 Correlation Classification (per-element pair):
//   >0.7: STRONG, 0.3-0.7: MODERATE, -0.3-0.3: WEAK, <-0.3: ANTI
//
// Latency: 1 cycle
// =============================================================================

module tc
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,
  input  logic                          soft_reset,

  // -----------------------------------------------------------------------
  // Configuration
  // -----------------------------------------------------------------------
  input  logic [UQ0_32_W-1:0]          coh_threshold,     // Default 0.95
  input  logic [UQ0_32_W-1:0]          hysteresis,        // Default 0.02
  input  logic [31:0]                   stab_window,       // Default 5
  input  logic [UQ0_32_W-1:0]          stab_var_max,      // Default 0.001

  // -----------------------------------------------------------------------
  // Coherence input (from CA)
  // -----------------------------------------------------------------------
  input  logic [UQ0_32_W-1:0]          coherence_in,
  input  logic                          coh_valid,

  // -----------------------------------------------------------------------
  // Outputs
  // -----------------------------------------------------------------------
  output sync_state_e                   sync_state,
  output logic                          phase_locked,      // True when LOCKED or TRACKING
  output logic [UQ0_32_W-1:0]          coh_history [COH_HISTORY_LEN],

  // -----------------------------------------------------------------------
  // Interrupts
  // -----------------------------------------------------------------------
  output logic                          irq_sync_locked,   // Pulse on lock acquisition
  output logic                          irq_sync_lost      // Pulse on lock loss
);

  // =========================================================================
  // Coherence History and Stability Detection
  // =========================================================================
  logic [UQ0_32_W-1:0] coh_hist [COH_HISTORY_LEN];
  logic [2:0]           coh_hist_idx;
  logic                 coh_hist_full;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset) begin
      for (int i = 0; i < COH_HISTORY_LEN; i++)
        coh_hist[i] <= '0;
      coh_hist_idx  <= '0;
      coh_hist_full <= 1'b0;
    end else if (coh_valid && enable) begin
      coh_hist[coh_hist_idx] <= coherence_in;
      if (coh_hist_idx == COH_HISTORY_LEN - 1) begin
        coh_hist_idx  <= '0;
        coh_hist_full <= 1'b1;
      end else begin
        coh_hist_idx <= coh_hist_idx + 1;
      end
    end
  end

  // Export history for register reads
  genvar gi;
  generate
    for (gi = 0; gi < COH_HISTORY_LEN; gi++) begin : g_hist
      assign coh_history[gi] = coh_hist[gi];
    end
  endgenerate

  // Compute variance of coherence history
  // variance = sum((c_i - mean)^2) / N
  logic [UQ0_32_W-1:0] coh_mean;
  logic [UQ0_32_W-1:0] coh_variance;
  logic                 is_stable;

  always_comb begin
    // Simple mean computation
    automatic logic [UQ0_32_W+2:0] sum = '0;
    for (int i = 0; i < COH_HISTORY_LEN; i++)
      sum = sum + coh_hist[i];
    coh_mean = sum / COH_HISTORY_LEN;

    // Variance (simplified: max deviation as proxy)
    automatic logic [UQ0_32_W-1:0] max_dev = '0;
    for (int i = 0; i < COH_HISTORY_LEN; i++) begin
      automatic logic [UQ0_32_W-1:0] dev;
      dev = (coh_hist[i] > coh_mean) ? (coh_hist[i] - coh_mean) : (coh_mean - coh_hist[i]);
      if (dev > max_dev) max_dev = dev;
    end
    coh_variance = max_dev; // Use max deviation as stability proxy

    is_stable = coh_hist_full && (coh_variance < stab_var_max);
  end

  // =========================================================================
  // Threshold computation
  // =========================================================================
  logic [UQ0_32_W-1:0] lock_threshold;     // coh_threshold (0.95)
  logic [UQ0_32_W-1:0] unlock_threshold;   // coh_threshold - 3*hysteresis (0.89)
  logic [UQ0_32_W-1:0] tracking_threshold; // coh_threshold - hysteresis (0.93)

  assign lock_threshold     = coh_threshold;
  assign tracking_threshold = coh_threshold - hysteresis;
  // 3 * hysteresis
  assign unlock_threshold   = coh_threshold - hysteresis - hysteresis - hysteresis;

  // =========================================================================
  // Sync State Machine
  // =========================================================================
  sync_state_e state_r, state_next;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset)
      state_r <= STATE_UNSYNC;
    else if (coh_valid && enable)
      state_r <= state_next;
  end

  always_comb begin
    state_next      = state_r;
    irq_sync_locked = 1'b0;
    irq_sync_lost   = 1'b0;

    case (state_r)
      STATE_UNSYNC: begin
        // Transition to ACQUIRING when sync starts
        if (enable)
          state_next = STATE_ACQUIRING;
      end

      STATE_ACQUIRING: begin
        if (coherence_in >= lock_threshold && is_stable) begin
          state_next      = STATE_LOCKED;
          irq_sync_locked = 1'b1;
        end
      end

      STATE_LOCKED: begin
        if (coherence_in < unlock_threshold) begin
          state_next    = STATE_LOST;
          irq_sync_lost = 1'b1;
        end else if (coherence_in < tracking_threshold) begin
          state_next = STATE_TRACKING;
        end
      end

      STATE_TRACKING: begin
        if (coherence_in >= lock_threshold && is_stable) begin
          state_next      = STATE_LOCKED;
          irq_sync_locked = 1'b1;
        end else if (coherence_in < unlock_threshold) begin
          state_next    = STATE_LOST;
          irq_sync_lost = 1'b1;
        end
      end

      STATE_LOST: begin
        // Re-acquire
        state_next = STATE_ACQUIRING;
      end

      default: state_next = STATE_UNSYNC;
    endcase
  end

  assign sync_state   = state_r;
  assign phase_locked = (state_r == STATE_LOCKED) || (state_r == STATE_TRACKING);

endmodule : tc
