// =============================================================================
// Panel Handover Controller (PHC)
// =============================================================================
// Manages antenna panel switching during phone rotation:
//   Panel 0 active: 0 <= wrapped_angle < 180 degrees
//   Panel 1 active: 180 <= wrapped_angle < 360 degrees
// Automatic re-acquisition sync on new panel after switch
// Handover latency: <500 us (full re-acquisition budget)
// =============================================================================

module phc
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,

  // -----------------------------------------------------------------------
  // Rotation input (from IMU/sensor, Q16.16 degrees)
  // -----------------------------------------------------------------------
  input  logic [31:0]                   rotation_deg,       // Q16.16

  // -----------------------------------------------------------------------
  // Sync state input (from TC)
  // -----------------------------------------------------------------------
  input  sync_state_e                   sync_state,
  input  logic [UQ0_32_W-1:0]          coherence,

  // -----------------------------------------------------------------------
  // Outputs
  // -----------------------------------------------------------------------
  output logic                          active_panel,       // 0 or 1
  output logic                          handover_trigger,   // Pulse on panel switch
  output logic                          reacq_request,      // Request sync re-acquisition

  // -----------------------------------------------------------------------
  // Status registers
  // -----------------------------------------------------------------------
  output logic [31:0]                   handover_count,
  output logic [31:0]                   reacq_iterations,   // Iters for last re-acquisition
  output logic [UQ0_32_W-1:0]          reacq_coherence,    // Coherence after re-acquisition

  // -----------------------------------------------------------------------
  // Interrupt
  // -----------------------------------------------------------------------
  output logic                          irq_handover_done
);

  // =========================================================================
  // Rotation Angle Processing
  // =========================================================================
  // Wrap rotation to [0, 360) degrees
  // 180 degrees in Q16.16 = 0x00B40000
  // 360 degrees in Q16.16 = 0x01680000
  localparam logic [31:0] DEG_180 = 32'h00B40000;
  localparam logic [31:0] DEG_360 = 32'h01680000;

  logic [31:0] wrapped_angle;
  logic        desired_panel;

  always_comb begin
    // Wrap angle to [0, 360)
    wrapped_angle = rotation_deg;
    if ($signed(rotation_deg) < 0)
      wrapped_angle = rotation_deg + DEG_360;
    if (wrapped_angle >= DEG_360)
      wrapped_angle = wrapped_angle - DEG_360;

    // Determine desired panel
    desired_panel = (wrapped_angle >= DEG_180) ? 1'b1 : 1'b0;
  end

  // =========================================================================
  // Handover State Machine
  // =========================================================================
  typedef enum logic [2:0] {
    PHC_IDLE,
    PHC_DETECT,
    PHC_SWITCHING,
    PHC_REACQUIRING,
    PHC_DONE
  } phc_state_e;

  phc_state_e phc_state;
  logic       current_panel;
  logic [31:0] reacq_iter_cnt;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      phc_state         <= PHC_IDLE;
      current_panel     <= 1'b0;
      handover_trigger  <= 1'b0;
      reacq_request     <= 1'b0;
      handover_count    <= '0;
      reacq_iterations  <= '0;
      reacq_coherence   <= '0;
      reacq_iter_cnt    <= '0;
      irq_handover_done <= 1'b0;
    end else begin
      handover_trigger  <= 1'b0;
      reacq_request     <= 1'b0;
      irq_handover_done <= 1'b0;

      case (phc_state)
        PHC_IDLE: begin
          if (enable)
            phc_state <= PHC_DETECT;
        end

        PHC_DETECT: begin
          if (desired_panel != current_panel) begin
            phc_state <= PHC_SWITCHING;
          end
        end

        PHC_SWITCHING: begin
          // Initiate panel switch
          current_panel    <= desired_panel;
          handover_trigger <= 1'b1;
          handover_count   <= handover_count + 1;
          reacq_request    <= 1'b1;
          reacq_iter_cnt   <= '0;
          phc_state        <= PHC_REACQUIRING;
        end

        PHC_REACQUIRING: begin
          // Wait for sync to re-lock on new panel
          reacq_iter_cnt <= reacq_iter_cnt + 1;

          if (sync_state == STATE_LOCKED || sync_state == STATE_TRACKING) begin
            reacq_iterations  <= reacq_iter_cnt;
            reacq_coherence   <= coherence;
            irq_handover_done <= 1'b1;
            phc_state         <= PHC_DONE;
          end else if (reacq_iter_cnt >= MAX_SYNC_ITER) begin
            // Timeout: record partial results
            reacq_iterations  <= reacq_iter_cnt;
            reacq_coherence   <= coherence;
            irq_handover_done <= 1'b1;
            phc_state         <= PHC_DONE;
          end
        end

        PHC_DONE: begin
          phc_state <= PHC_DETECT;
        end

        default: phc_state <= PHC_IDLE;
      endcase
    end
  end

  assign active_panel = current_panel;

endmodule : phc
