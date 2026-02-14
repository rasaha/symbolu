// =============================================================================
// Synchronization Controller
// =============================================================================
// Main FSM orchestrating the sync cycle pipeline:
//   Cycle 0: EPRF parallel read (128 phases)
//   Cycle 1: MFU cycle 1 - sin/cos accumulate + atan2
//   Cycle 2: MFU cycle 2 - per-element gradient, CA coherence piggyback
//   Cycle 3: PUE phase update (128-parallel multiply-add-wrap)
//   Cycle 4: TC lock detection + EPRF write-back
//
// Timing: 4 cycles @ 1 GHz = 4 ns per sync iteration
// Budget: 10 us interval -> can run 2,500 iterations, actual max 50
//
// Modes: single-shot, continuous, beamforming, tracking
// =============================================================================

module sync_ctrl
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Global control (from GCR)
  // -----------------------------------------------------------------------
  input  logic                          global_enable,
  input  logic                          soft_reset,
  input  logic                          sync_start,        // Single-shot trigger
  input  logic                          continuous_mode,
  input  sync_mode_e                    sync_mode,
  input  logic [7:0]                    max_iterations,    // Max per interval (default 50)

  // -----------------------------------------------------------------------
  // Sync interval timer
  // -----------------------------------------------------------------------
  // 10 us at 1 GHz = 10,000 cycles
  input  logic                          sync_interval_tick, // External timer tick

  // -----------------------------------------------------------------------
  // Unit control signals
  // -----------------------------------------------------------------------
  // EPRF
  output logic                          eprf_rd_en,
  output logic                          eprf_wr_en,

  // MFU
  output logic                          mfu_enable,
  output logic                          mfu_use_target,
  output logic                          mfu_start,
  input  logic                          mfu_gradient_valid,
  input  logic                          mfu_accum_valid,
  input  logic                          mfu_busy,

  // PUE
  output logic                          pue_enable,
  output logic                          pue_start,
  input  logic                          pue_phase_valid,
  input  logic                          pue_busy,

  // CA
  output logic                          ca_enable,
  input  logic                          ca_coh_valid,

  // TC
  output logic                          tc_enable,
  input  sync_state_e                   tc_sync_state,
  input  logic                          tc_phase_locked,

  // CE (background)
  output logic                          ce_enable,

  // BQM (background)
  output logic                          bqm_enable,
  output logic                          bqm_start,

  // -----------------------------------------------------------------------
  // Status
  // -----------------------------------------------------------------------
  output sync_cycle_state_e             cycle_state,
  output logic                          sync_busy,
  output logic [63:0]                   sync_update_count, // Total updates since reset
  output logic [7:0]                    current_iteration  // Current iteration in interval
);

  // =========================================================================
  // Sync Interval State Machine
  // =========================================================================
  typedef enum logic [2:0] {
    SYNC_IDLE,
    SYNC_WAIT_INTERVAL,
    SYNC_RUNNING,
    SYNC_CONVERGED,
    SYNC_MAX_ITER
  } sync_top_state_e;

  sync_top_state_e top_state;
  logic [7:0] iter_count;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset) begin
      top_state         <= SYNC_IDLE;
      iter_count        <= '0;
      sync_update_count <= '0;
    end else begin
      case (top_state)
        SYNC_IDLE: begin
          if (global_enable && (sync_start || (continuous_mode && sync_interval_tick)))
            top_state <= SYNC_RUNNING;
        end

        SYNC_WAIT_INTERVAL: begin
          if (sync_interval_tick && continuous_mode)
            top_state <= SYNC_RUNNING;
          else if (!continuous_mode)
            top_state <= SYNC_IDLE;
        end

        SYNC_RUNNING: begin
          if (tc_phase_locked && tc_sync_state == STATE_LOCKED) begin
            top_state <= SYNC_CONVERGED;
          end else if (iter_count >= max_iterations) begin
            top_state <= SYNC_MAX_ITER;
          end
          // iter_count managed by cycle FSM completion
        end

        SYNC_CONVERGED: begin
          top_state <= continuous_mode ? SYNC_WAIT_INTERVAL : SYNC_IDLE;
        end

        SYNC_MAX_ITER: begin
          top_state <= continuous_mode ? SYNC_WAIT_INTERVAL : SYNC_IDLE;
        end

        default: top_state <= SYNC_IDLE;
      endcase
    end
  end

  assign sync_busy = (top_state == SYNC_RUNNING);
  assign current_iteration = iter_count;

  // =========================================================================
  // Per-Iteration Cycle FSM (4-cycle pipeline per iteration)
  // =========================================================================
  sync_cycle_state_e cyc_state;
  logic iteration_done;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset) begin
      cyc_state      <= SCYC_IDLE;
      iteration_done <= 1'b0;
    end else begin
      iteration_done <= 1'b0;

      case (cyc_state)
        SCYC_IDLE: begin
          if (top_state == SYNC_RUNNING)
            cyc_state <= SCYC_READ_EPRF;
        end

        SCYC_READ_EPRF: begin
          // Cycle 0: Read all phases from EPRF
          cyc_state <= SCYC_MFU_C1;
        end

        SCYC_MFU_C1: begin
          // Cycle 1: MFU sin/cos accumulation + atan2
          if (mfu_accum_valid)
            cyc_state <= SCYC_MFU_C2;
        end

        SCYC_MFU_C2: begin
          // Cycle 2: MFU per-element gradient + CA coherence
          if (mfu_gradient_valid)
            cyc_state <= SCYC_PUE;
        end

        SCYC_PUE: begin
          // Cycle 3: Phase update engine
          if (pue_phase_valid)
            cyc_state <= SCYC_TC_WB;
        end

        SCYC_TC_WB: begin
          // Cycle 4: Threshold check + write-back
          iteration_done <= 1'b1;
          if (top_state == SYNC_RUNNING)
            cyc_state <= SCYC_READ_EPRF; // Next iteration
          else
            cyc_state <= SCYC_IDLE;
        end

        default: cyc_state <= SCYC_IDLE;
      endcase
    end
  end

  assign cycle_state = cyc_state;

  // Iteration counter
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset) begin
      iter_count <= '0;
    end else begin
      if (top_state == SYNC_IDLE || top_state == SYNC_WAIT_INTERVAL)
        iter_count <= '0;
      else if (iteration_done)
        iter_count <= iter_count + 1;
    end
  end

  // Update counter
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n || soft_reset)
      sync_update_count <= '0;
    else if (iteration_done)
      sync_update_count <= sync_update_count + 1;
  end

  // =========================================================================
  // Unit Control Signal Generation
  // =========================================================================

  // EPRF read on cycle 0
  assign eprf_rd_en = (cyc_state == SCYC_READ_EPRF);

  // EPRF write on cycle 4 (write-back updated phases)
  assign eprf_wr_en = (cyc_state == SCYC_TC_WB) && pue_phase_valid;

  // MFU control
  assign mfu_enable     = global_enable;
  assign mfu_use_target = (sync_mode == SYNC_BEAMFORMING) || (sync_mode == SYNC_TRACKING);
  assign mfu_start      = (cyc_state == SCYC_READ_EPRF); // Start after EPRF read

  // PUE control
  assign pue_enable = global_enable;
  assign pue_start  = mfu_gradient_valid; // Start when gradients ready

  // CA control
  assign ca_enable = global_enable;

  // TC control
  assign tc_enable = global_enable;

  // CE background operation
  assign ce_enable = global_enable;

  // BQM control: compute quality after each convergence or periodically
  assign bqm_enable = global_enable;
  assign bqm_start  = iteration_done && (iter_count[2:0] == 3'b000); // Every 8 iterations

endmodule : sync_ctrl
