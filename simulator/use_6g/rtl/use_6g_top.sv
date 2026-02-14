// =============================================================================
// USE-6G Massive MIMO Synchronization Chip — Top Level
// =============================================================================
// Purpose-built silicon accelerator for 6G Massive MIMO phase synchronization
// Implements USE patent formulas U1-U5 in dedicated hardware:
//   U1: Correlation Engine (CE)     - Windowed pairwise cos(delta_phi)
//   U2: Coherence Accumulator (CA)  - Global coherence metric
//   U3: Mean-Field Unit (MFU)       - O(n) gradient via circular mean
//   U4: Phase Update Engine (PUE)   - Adaptive learning rate phase update
//   U5: Threshold Comparator (TC)   - Lock detection with hysteresis
//
// Key specifications:
//   - 128 antenna elements (2 panels x 8x8 UPA)
//   - 4 simultaneous beams
//   - ±100ps timing precision (CSAC-referenced)
//   - <500 us convergence from cold start
//   - ≤20W total power, ≤25mm² die area at 4nm
//   - 1 GHz core clock, 10 us sync interval
//
// Reference: docs/hardware/USE_6G_CHIP_SPEC.md
// =============================================================================

module use_6g_top
  import use_6g_pkg::*;
(
  // =========================================================================
  // Clock and Reset
  // =========================================================================
  input  logic                          clk_core,       // 1 GHz core clock
  input  logic                          clk_csac,       // 10 MHz CSAC reference
  input  logic                          rst_n,          // Active-low async reset

  // =========================================================================
  // Register Bus Interface (SPI/I2C/PCIe mapped)
  // =========================================================================
  input  reg_req_t                      reg_req,
  output reg_rsp_t                      reg_rsp,

  // =========================================================================
  // RF Front-End Interface (128 element phase measurements)
  // =========================================================================
  input  logic [Q2_30_W-1:0]           rf_phase_in [NUM_ELEMENTS],
  input  logic                          rf_phase_valid,

  // =========================================================================
  // External sensor inputs
  // =========================================================================
  input  logic [31:0]                   rotation_angle,  // Phone rotation (Q16.16 deg)

  // =========================================================================
  // Interrupt output
  // =========================================================================
  output logic                          irq_out,

  // =========================================================================
  // Status outputs
  // =========================================================================
  output sync_state_e                   sync_state,
  output logic                          phase_locked
);

  // =========================================================================
  // Internal Wires
  // =========================================================================

  // --- GCR control signals ---
  logic                          gcr_enable;
  logic                          gcr_soft_reset;
  logic                          gcr_sync_start;
  logic                          gcr_continuous;
  sync_mode_e                    gcr_sync_mode;
  freq_band_e                    gcr_freq_band;
  logic [7:0]                    gcr_max_iter;
  logic [7:0]                    gcr_num_panels;
  logic [NUM_IRQS-1:0]           gcr_irq_en;
  logic [NUM_IRQS-1:0]           gcr_irq_raw;
  logic [UQ16_16_W-1:0]         gcr_carrier_ghz;
  logic [UQ16_16_W-1:0]         gcr_wavelength_mm;
  logic [UQ16_16_W-1:0]         gcr_bandwidth_ghz;

  // --- EPRF signals ---
  logic                          eprf_par_rd_en;
  logic                          eprf_par_wr_en;
  logic [Q2_30_W-1:0]           eprf_phase      [NUM_ELEMENTS];
  logic [Q2_30_W-1:0]           eprf_target      [NUM_ELEMENTS];
  logic [7:0]                    eprf_flags       [NUM_ELEMENTS];
  logic                          eprf_par_rd_valid;
  logic [Q2_30_W-1:0]           eprf_phase_wr    [NUM_ELEMENTS];
  logic [Q8_8_W-1:0]            eprf_pos_x       [NUM_ELEMENTS];
  logic [Q8_8_W-1:0]            eprf_pos_y       [NUM_ELEMENTS];
  logic [Q1_15_W-1:0]           eprf_cal_offset  [NUM_ELEMENTS];
  logic [7:0]                    eprf_active_count;
  logic [7:0]                    eprf_failed_count;

  // EPRF register access
  logic                          eprf_reg_rd_en;
  logic                          eprf_reg_wr_en;
  logic [ELEM_IDX_W-1:0]        eprf_reg_elem_idx;
  logic [2:0]                    eprf_reg_field_sel;
  logic [Q2_30_W-1:0]           eprf_reg_wdata;
  logic [Q2_30_W-1:0]           eprf_reg_rdata;
  logic                          eprf_reg_rd_valid;

  // --- MFU signals ---
  logic                          mfu_enable;
  logic                          mfu_use_target;
  logic                          mfu_start;
  logic signed [Q2_30_W-1:0]    mfu_gradient     [NUM_ELEMENTS];
  logic                          mfu_gradient_valid;
  logic signed [Q2_30_W-1:0]    mfu_sin_sum;
  logic signed [Q2_30_W-1:0]    mfu_cos_sum;
  logic [Q2_30_W-1:0]           mfu_phi_mean;
  logic                          mfu_accum_valid;
  logic                          mfu_busy;

  // --- PUE signals ---
  logic                          pue_enable;
  logic                          pue_start;
  logic [Q2_30_W-1:0]           pue_phase_out    [NUM_ELEMENTS];
  logic                          pue_phase_valid;
  logic [UQ0_16_W-1:0]          pue_base_lr;
  logic [UQ0_16_W-1:0]          pue_current_lr;
  logic [Q2_30_W-1:0]           pue_mean_update;
  logic [31:0]                   pue_lr_adapt_win;
  logic [UQ0_8_W-1:0]           pue_lr_fast_mult;
  logic [UQ0_8_W-1:0]           pue_lr_fine_mult;
  logic [UQ0_8_W-1:0]           pue_lr_damp_mult;
  logic [UQ0_8_W-1:0]           pue_lr_track_mult;
  logic                          pue_busy;

  // --- CE signals ---
  logic                          ce_enable;
  logic [31:0]                   ce_window;
  logic [31:0]                   ce_update_period;
  logic                          ce_busy;
  logic                          ce_update_done;

  // --- CA signals ---
  logic                          ca_enable;
  logic [UQ0_32_W-1:0]          ca_global_coh;
  logic [UQ0_32_W-1:0]          ca_panel0_coh;
  logic [UQ0_32_W-1:0]          ca_panel1_coh;
  logic [UQ0_32_W-1:0]          ca_beam_coh      [MAX_BEAMS];
  logic                          ca_coh_valid;

  // --- TC signals ---
  logic                          tc_enable;
  sync_state_e                   tc_sync_state;
  logic                          tc_phase_locked;
  logic [UQ0_32_W-1:0]          tc_coh_history   [COH_HISTORY_LEN];
  logic                          tc_irq_locked;
  logic                          tc_irq_lost;
  logic [UQ0_32_W-1:0]          tc_coh_threshold;
  logic [UQ0_32_W-1:0]          tc_hysteresis;
  logic [31:0]                   tc_stab_window;
  logic [UQ0_32_W-1:0]          tc_stab_var_max;

  // --- SVG signals ---
  logic                          svg_start_from_mbc;
  logic                          svg_start_from_reg;
  logic [Q9_7_W-1:0]            svg_azimuth;
  logic [Q9_7_W-1:0]            svg_elevation;
  logic [BEAM_IDX_W-1:0]        svg_beam_id;
  logic [Q2_30_W-1:0]           svg_steering     [NUM_ELEMENTS];
  logic [BEAM_IDX_W-1:0]        svg_beam_id_done;
  logic                          svg_done;

  // --- MBC signals ---
  logic [3:0]                    mbc_active_mask;
  sched_mode_e                   mbc_sched_mode;
  logic [Q2_30_W-1:0]           mbc_active_steering [NUM_ELEMENTS];
  logic [BEAM_IDX_W-1:0]        mbc_active_beam_id;
  beam_context_t                 mbc_beam_ctx     [MAX_BEAMS];
  logic                          mbc_steer_done;
  logic [3:0]                    mbc_active_beam_count;
  logic                          mbc_busy;

  // MBC -> SVG interface
  logic                          mbc_svg_start;
  logic [Q9_7_W-1:0]            mbc_svg_azimuth;
  logic [Q9_7_W-1:0]            mbc_svg_elevation;
  logic [BEAM_IDX_W-1:0]        mbc_svg_beam_id;

  // --- PHC signals ---
  logic                          phc_active_panel;
  logic                          phc_handover_trigger;
  logic                          phc_reacq_request;
  logic [31:0]                   phc_handover_cnt;
  logic [31:0]                   phc_reacq_iters;
  logic [UQ0_32_W-1:0]          phc_reacq_coh;
  logic                          phc_irq_handover;
  logic [31:0]                   phc_rotation_deg;

  // --- BQM signals ---
  logic                          bqm_enable;
  logic                          bqm_start;
  logic [Q8_8_W-1:0]            bqm_gain         [MAX_BEAMS];
  logic [Q8_8_W-1:0]            bqm_sidelobe     [MAX_BEAMS];
  logic [UQ0_32_W-1:0]          bqm_beam_coh     [MAX_BEAMS];
  logic                          bqm_done;

  // --- Sync Controller signals ---
  sync_cycle_state_e             sync_cycle_state;
  logic                          sync_busy;
  logic [63:0]                   sync_update_count;
  logic [7:0]                    sync_current_iter;

  // --- Power (placeholder) ---
  power_state_e                  pwr_state;
  logic [UQ8_8_W-1:0]           pwr_current_w;
  logic [Q8_8_W-1:0]            pwr_junc_temp;
  logic [Q8_8_W-1:0]            pwr_throttle_temp;
  logic [Q8_8_W-1:0]            pwr_max_temp;
  logic [UQ8_8_W-1:0]           pwr_idle_power;
  logic [UQ8_8_W-1:0]           pwr_sync_power;
  logic [UQ8_8_W-1:0]           pwr_beam_power;
  logic                          thermal_warn;
  logic                          thermal_crit;

  // --- Register interface MFU signals ---
  logic                          mfu_reg_enable;
  logic                          mfu_reg_use_target;
  logic [BEAM_IDX_W-1:0]        mfu_reg_beam_sel;

  // =========================================================================
  // Sync Interval Timer (10 us @ 1 GHz = 10,000 cycles)
  // =========================================================================
  localparam int SYNC_INTERVAL_CYCLES = 10000;
  logic [13:0] interval_cnt;
  logic        sync_interval_tick;

  always_ff @(posedge clk_core or negedge rst_n) begin
    if (!rst_n) begin
      interval_cnt     <= '0;
      sync_interval_tick <= 1'b0;
    end else begin
      if (interval_cnt >= SYNC_INTERVAL_CYCLES - 1) begin
        interval_cnt     <= '0;
        sync_interval_tick <= 1'b1;
      end else begin
        interval_cnt     <= interval_cnt + 1;
        sync_interval_tick <= 1'b0;
      end
    end
  end

  // =========================================================================
  // Wavelength computation: wavelength_mm = 300 / carrier_ghz
  // =========================================================================
  // Placeholder: use pre-computed value for 140 GHz
  // 300/140 = 2.14 mm => 0x00022666 in UQ16.16
  assign gcr_wavelength_mm = 32'h00022666;

  // =========================================================================
  // Thermal monitoring (placeholder)
  // =========================================================================
  assign pwr_state    = sync_busy ? PWR_SYNC : PWR_IDLE;
  assign pwr_current_w = 16'h0300; // 3.0W placeholder
  assign pwr_junc_temp = 16'h4600; // 70°C placeholder
  assign thermal_warn  = ($signed(pwr_junc_temp) >= $signed(pwr_throttle_temp));
  assign thermal_crit  = ($signed(pwr_junc_temp) >= $signed(pwr_max_temp));

  // =========================================================================
  // Interrupt Aggregation
  // =========================================================================
  assign gcr_irq_raw = {
    ce_update_done,           // [6] CORR_READY
    thermal_warn,             // [5] THERMAL_WARN
    1'b0,                     // [4] ELEMENT_FAIL (placeholder)
    mbc_steer_done,           // [3] BEAM_STEER_DONE
    phc_irq_handover,         // [2] HANDOVER_DONE
    tc_irq_lost,              // [1] SYNC_LOST
    tc_irq_locked             // [0] SYNC_LOCKED
  };

  // =========================================================================
  // RF Phase Input Latch (from external ADCs)
  // =========================================================================
  // When RF phases arrive, update EPRF current phases
  always_ff @(posedge clk_core) begin
    if (rf_phase_valid) begin
      for (int i = 0; i < NUM_ELEMENTS; i++)
        eprf_phase_wr[i] <= rf_phase_in[i];
    end else if (pue_phase_valid) begin
      // Normal sync path: write back PUE-updated phases
      for (int i = 0; i < NUM_ELEMENTS; i++)
        eprf_phase_wr[i] <= pue_phase_out[i];
    end
  end

  // Per-panel sin/cos sums (simplified: zeros for now, MFU can be extended)
  logic signed [Q2_30_W-1:0] sin_sum_panel0, cos_sum_panel0;
  logic signed [Q2_30_W-1:0] sin_sum_panel1, cos_sum_panel1;
  assign sin_sum_panel0 = '0;
  assign cos_sum_panel0 = '0;
  assign sin_sum_panel1 = '0;
  assign cos_sum_panel1 = '0;

  // SVG start mux: from MBC or register
  logic svg_start_muxed;
  assign svg_start_muxed = mbc_svg_start | svg_start_from_reg;

  // =========================================================================
  // Module Instantiations
  // =========================================================================

  // --- Register Interface ---
  reg_if u_reg_if (
    .clk                (clk_core),
    .rst_n              (rst_n),
    .reg_req            (reg_req),
    .reg_rsp            (reg_rsp),

    // GCR
    .gcr_enable         (gcr_enable),
    .gcr_soft_reset     (gcr_soft_reset),
    .gcr_sync_start     (gcr_sync_start),
    .gcr_continuous     (gcr_continuous),
    .gcr_sync_mode      (gcr_sync_mode),
    .gcr_freq_band      (gcr_freq_band),
    .gcr_max_iter       (gcr_max_iter),
    .gcr_num_panels     (gcr_num_panels),
    .gcr_sync_state     (tc_sync_state),
    .gcr_sync_busy      (sync_busy),
    .gcr_active_beams   (mbc_active_beam_count),
    .gcr_active_elements(eprf_active_count),
    .gcr_failed_elements(eprf_failed_count),
    .gcr_thermal_warn   (thermal_warn),
    .gcr_thermal_crit   (thermal_crit),
    .gcr_sync_count     (sync_update_count),
    .gcr_irq_en         (gcr_irq_en),
    .gcr_irq_raw        (gcr_irq_raw),
    .gcr_irq_out        (irq_out),
    .gcr_carrier_ghz    (gcr_carrier_ghz),
    .gcr_wavelength_mm  (gcr_wavelength_mm),
    .gcr_bandwidth_ghz  (gcr_bandwidth_ghz),

    // MFU
    .mfu_reg_enable     (mfu_reg_enable),
    .mfu_reg_use_target (mfu_reg_use_target),
    .mfu_reg_beam_sel   (mfu_reg_beam_sel),
    .mfu_sin_sum        (mfu_sin_sum),
    .mfu_cos_sum        (mfu_cos_sum),
    .mfu_phi_mean       (mfu_phi_mean),

    // PUE
    .pue_base_lr        (pue_base_lr),
    .pue_current_lr     (pue_current_lr),
    .pue_mean_update    (pue_mean_update),
    .pue_lr_adapt_win   (pue_lr_adapt_win),
    .pue_lr_fast_mult   (pue_lr_fast_mult),
    .pue_lr_fine_mult   (pue_lr_fine_mult),
    .pue_lr_damp_mult   (pue_lr_damp_mult),
    .pue_lr_track_mult  (pue_lr_track_mult),

    // CE
    .ce_window          (ce_window),
    .ce_update_period   (ce_update_period),
    .ce_busy            (ce_busy),
    .ce_update_done     (ce_update_done),

    // CA
    .ca_global_coh      (ca_global_coh),
    .ca_panel0_coh      (ca_panel0_coh),
    .ca_panel1_coh      (ca_panel1_coh),
    .ca_beam_coh        (ca_beam_coh),

    // TC
    .tc_coh_threshold   (tc_coh_threshold),
    .tc_hysteresis      (tc_hysteresis),
    .tc_stab_window     (tc_stab_window),
    .tc_stab_var_max    (tc_stab_var_max),
    .tc_sync_state      (tc_sync_state),
    .tc_coh_history     (tc_coh_history),

    // SVG
    .svg_start          (svg_start_from_reg),
    .svg_azimuth        (svg_azimuth),
    .svg_elevation      (svg_elevation),
    .svg_beam_id        (svg_beam_id),
    .svg_done           (svg_done),

    // MBC
    .mbc_active_mask    (mbc_active_mask),
    .mbc_sched_mode     (mbc_sched_mode),
    .mbc_beam_ctx       (mbc_beam_ctx),

    // PHC
    .phc_active_panel   (phc_active_panel),
    .phc_rotation_deg   (phc_rotation_deg),
    .phc_handover_cnt   (phc_handover_cnt),
    .phc_reacq_iters    (phc_reacq_iters),
    .phc_reacq_coh      (phc_reacq_coh),

    // PWR
    .pwr_state          (pwr_state),
    .pwr_current_w      (pwr_current_w),
    .pwr_junc_temp      (pwr_junc_temp),
    .pwr_throttle_temp  (pwr_throttle_temp),
    .pwr_max_temp       (pwr_max_temp),
    .pwr_idle_power     (pwr_idle_power),
    .pwr_sync_power     (pwr_sync_power),
    .pwr_beam_power     (pwr_beam_power)
  );

  // --- Synchronization Controller ---
  sync_ctrl u_sync_ctrl (
    .clk                (clk_core),
    .rst_n              (rst_n),
    .global_enable      (gcr_enable),
    .soft_reset         (gcr_soft_reset),
    .sync_start         (gcr_sync_start),
    .continuous_mode    (gcr_continuous),
    .sync_mode          (gcr_sync_mode),
    .max_iterations     (gcr_max_iter),
    .sync_interval_tick (sync_interval_tick),

    .eprf_rd_en         (eprf_par_rd_en),
    .eprf_wr_en         (eprf_par_wr_en),

    .mfu_enable         (mfu_enable),
    .mfu_use_target     (mfu_use_target),
    .mfu_start          (mfu_start),
    .mfu_gradient_valid (mfu_gradient_valid),
    .mfu_accum_valid    (mfu_accum_valid),
    .mfu_busy           (mfu_busy),

    .pue_enable         (pue_enable),
    .pue_start          (pue_start),
    .pue_phase_valid    (pue_phase_valid),
    .pue_busy           (pue_busy),

    .ca_enable          (ca_enable),
    .ca_coh_valid       (ca_coh_valid),

    .tc_enable          (tc_enable),
    .tc_sync_state      (tc_sync_state),
    .tc_phase_locked    (tc_phase_locked),

    .ce_enable          (ce_enable),
    .bqm_enable         (bqm_enable),
    .bqm_start          (bqm_start),

    .cycle_state        (sync_cycle_state),
    .sync_busy          (sync_busy),
    .sync_update_count  (sync_update_count),
    .current_iteration  (sync_current_iter)
  );

  // --- Element Phase Register File ---
  eprf u_eprf (
    .clk               (clk_core),
    .rst_n             (rst_n),

    .par_rd_en         (eprf_par_rd_en),
    .par_phase_out     (eprf_phase),
    .par_target_out    (eprf_target),
    .par_flags_out     (eprf_flags),
    .par_rd_valid      (eprf_par_rd_valid),

    .par_wr_en         (eprf_par_wr_en),
    .par_phase_in      (eprf_phase_wr),

    .reg_rd_en         (eprf_reg_rd_en),
    .reg_wr_en         (eprf_reg_wr_en),
    .reg_elem_idx      (eprf_reg_elem_idx),
    .reg_field_sel     (eprf_reg_field_sel),
    .reg_wdata         (eprf_reg_wdata),
    .reg_rdata         (eprf_reg_rdata),
    .reg_rd_valid      (eprf_reg_rd_valid),

    .pos_x_out         (eprf_pos_x),
    .pos_y_out         (eprf_pos_y),
    .cal_offset_out    (eprf_cal_offset),

    .active_count      (eprf_active_count),
    .failed_count      (eprf_failed_count)
  );

  // --- Mean-Field Unit (U3) ---
  mfu u_mfu (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (mfu_enable),
    .use_target        (mfu_use_target),
    .start             (mfu_start),
    .phase_in          (eprf_phase),
    .target_in         (mbc_active_steering),
    .flags_in          (eprf_flags),
    .gradient_out      (mfu_gradient),
    .gradient_valid    (mfu_gradient_valid),
    .sin_sum_out       (mfu_sin_sum),
    .cos_sum_out       (mfu_cos_sum),
    .phi_mean_out      (mfu_phi_mean),
    .accum_valid       (mfu_accum_valid),
    .busy              (mfu_busy)
  );

  // --- Phase Update Engine (U4) ---
  pue u_pue (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (pue_enable),
    .start             (pue_start),
    .base_learning_rate(pue_base_lr),
    .lr_fast_mult      (pue_lr_fast_mult),
    .lr_fine_mult      (pue_lr_fine_mult),
    .lr_damp_mult      (pue_lr_damp_mult),
    .lr_track_mult     (pue_lr_track_mult),
    .lr_adapt_window   (pue_lr_adapt_win),
    .gradient_in       (mfu_gradient),
    .gradient_valid    (mfu_gradient_valid),
    .phase_in          (eprf_phase),
    .coherence_in      (ca_global_coh),
    .phase_out         (pue_phase_out),
    .phase_valid       (pue_phase_valid),
    .current_lr        (pue_current_lr),
    .mean_update       (pue_mean_update),
    .busy              (pue_busy)
  );

  // --- Correlation Engine (U1) ---
  ce u_ce (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (ce_enable),
    .window_depth      (ce_window),
    .update_period     (ce_update_period),
    .phase_in          (eprf_phase),
    .phase_valid       (pue_phase_valid),
    .query_i           ('0),            // Connected via register interface
    .query_j           ('0),
    .query_valid       (1'b0),
    .pair_value        (),
    .pair_valid        (),
    .busy              (ce_busy),
    .update_done       (ce_update_done)
  );

  // --- Coherence Accumulator (U2) ---
  ca u_ca (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (ca_enable),
    .sin_sum           (mfu_sin_sum),
    .cos_sum           (mfu_cos_sum),
    .accum_valid       (mfu_accum_valid),
    .sin_sum_panel0    (sin_sum_panel0),
    .cos_sum_panel0    (cos_sum_panel0),
    .sin_sum_panel1    (sin_sum_panel1),
    .cos_sum_panel1    (cos_sum_panel1),
    .beam_coherence    (bqm_beam_coh),
    .global_coherence  (ca_global_coh),
    .panel0_coherence  (ca_panel0_coh),
    .panel1_coherence  (ca_panel1_coh),
    .beam_coh_out      (ca_beam_coh),
    .coh_valid         (ca_coh_valid)
  );

  // --- Threshold Comparator (U5) ---
  tc u_tc (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (tc_enable),
    .soft_reset        (gcr_soft_reset),
    .coh_threshold     (tc_coh_threshold),
    .hysteresis        (tc_hysteresis),
    .stab_window       (tc_stab_window),
    .stab_var_max      (tc_stab_var_max),
    .coherence_in      (ca_global_coh),
    .coh_valid         (ca_coh_valid),
    .sync_state        (tc_sync_state),
    .phase_locked      (tc_phase_locked),
    .coh_history       (tc_coh_history),
    .irq_sync_locked   (tc_irq_locked),
    .irq_sync_lost     (tc_irq_lost)
  );

  // --- Steering Vector Generator ---
  svg u_svg (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .start             (svg_start_muxed),
    .azimuth           (mbc_svg_start ? mbc_svg_azimuth  : svg_azimuth),
    .elevation         (mbc_svg_start ? mbc_svg_elevation : svg_elevation),
    .beam_id           (mbc_svg_start ? mbc_svg_beam_id  : svg_beam_id),
    .pos_x             (eprf_pos_x),
    .pos_y             (eprf_pos_y),
    .cal_offset        (eprf_cal_offset),
    .steering_out      (svg_steering),
    .beam_id_out       (svg_beam_id_done),
    .done              (svg_done)
  );

  // --- Multi-Beam Controller ---
  mbc u_mbc (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (gcr_enable),
    .active_mask       (mbc_active_mask),
    .sched_mode        (mbc_sched_mode),

    .steer_req         (1'b0),           // Driven by register writes
    .steer_beam_id     ('0),
    .steer_azimuth     ('0),
    .steer_elevation   ('0),
    .steer_user_id     ('0),

    .svg_start         (mbc_svg_start),
    .svg_azimuth       (mbc_svg_azimuth),
    .svg_elevation     (mbc_svg_elevation),
    .svg_beam_id       (mbc_svg_beam_id),
    .svg_steering      (svg_steering),
    .svg_beam_id_done  (svg_beam_id_done),
    .svg_done          (svg_done),

    .active_steering   (mbc_active_steering),
    .active_beam_id    (mbc_active_beam_id),

    .beam_gain         (bqm_gain),
    .beam_sidelobe     (bqm_sidelobe),

    .beam_ctx          (mbc_beam_ctx),
    .steer_done        (mbc_steer_done),
    .active_beam_count (mbc_active_beam_count),
    .busy              (mbc_busy)
  );

  // --- Panel Handover Controller ---
  phc u_phc (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (gcr_enable),
    .rotation_deg      (phc_rotation_deg),
    .sync_state        (tc_sync_state),
    .coherence         (ca_global_coh),
    .active_panel      (phc_active_panel),
    .handover_trigger  (phc_handover_trigger),
    .reacq_request     (phc_reacq_request),
    .handover_count    (phc_handover_cnt),
    .reacq_iterations  (phc_reacq_iters),
    .reacq_coherence   (phc_reacq_coh),
    .irq_handover_done (phc_irq_handover)
  );

  // --- Beam Quality Monitor ---
  bqm u_bqm (
    .clk               (clk_core),
    .rst_n             (rst_n),
    .enable            (bqm_enable),
    .compute_start     (bqm_start),
    .phase_in          (eprf_phase),
    .target_in         (mbc_active_steering),
    .flags_in          (eprf_flags),
    .gain_out          (bqm_gain),
    .sidelobe_out      (bqm_sidelobe),
    .beam_coherence    (bqm_beam_coh),
    .compute_done      (bqm_done),
    .hpbw_deg          (),
    .active_elem_count ()
  );

  // =========================================================================
  // Top-Level Output Assignments
  // =========================================================================
  assign sync_state   = tc_sync_state;
  assign phase_locked = tc_phase_locked;

  // EPRF register access defaults (not connected to reg bus in this version)
  assign eprf_reg_rd_en     = 1'b0;
  assign eprf_reg_wr_en     = 1'b0;
  assign eprf_reg_elem_idx  = '0;
  assign eprf_reg_field_sel = '0;
  assign eprf_reg_wdata     = '0;

endmodule : use_6g_top
