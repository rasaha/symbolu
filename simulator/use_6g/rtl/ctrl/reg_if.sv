// =============================================================================
// Register Interface (Register Bus Decoder)
// =============================================================================
// Decodes register bus transactions and routes to functional units
// Address space: 16-bit (0x0000 - 0xFFFF)
// Data width: 32-bit
// Supports: read, write, write-1-to-clear (W1C for interrupt status)
// =============================================================================

module reg_if
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // External register bus
  // -----------------------------------------------------------------------
  input  reg_req_t                      reg_req,
  output reg_rsp_t                      reg_rsp,

  // -----------------------------------------------------------------------
  // GCR - Global Control Registers
  // -----------------------------------------------------------------------
  output logic                          gcr_enable,
  output logic                          gcr_soft_reset,
  output logic                          gcr_sync_start,
  output logic                          gcr_continuous,
  output sync_mode_e                    gcr_sync_mode,
  output freq_band_e                    gcr_freq_band,
  output logic [7:0]                    gcr_max_iter,
  output logic [7:0]                    gcr_num_panels,

  input  sync_state_e                   gcr_sync_state,
  input  logic                          gcr_sync_busy,
  input  logic [3:0]                    gcr_active_beams,
  input  logic [7:0]                    gcr_active_elements,
  input  logic [7:0]                    gcr_failed_elements,
  input  logic                          gcr_thermal_warn,
  input  logic                          gcr_thermal_crit,
  input  logic [63:0]                   gcr_sync_count,

  // Interrupt management
  output logic [NUM_IRQS-1:0]           gcr_irq_en,
  input  logic [NUM_IRQS-1:0]           gcr_irq_raw,
  output logic                          gcr_irq_out,       // Combined interrupt

  // Frequency config
  output logic [UQ16_16_W-1:0]         gcr_carrier_ghz,
  input  logic [UQ16_16_W-1:0]         gcr_wavelength_mm,
  output logic [UQ16_16_W-1:0]         gcr_bandwidth_ghz,

  // -----------------------------------------------------------------------
  // MFU Registers
  // -----------------------------------------------------------------------
  output logic                          mfu_reg_enable,
  output logic                          mfu_reg_use_target,
  output logic [BEAM_IDX_W-1:0]        mfu_reg_beam_sel,
  input  logic signed [Q2_30_W-1:0]    mfu_sin_sum,
  input  logic signed [Q2_30_W-1:0]    mfu_cos_sum,
  input  logic [Q2_30_W-1:0]           mfu_phi_mean,

  // -----------------------------------------------------------------------
  // PUE Registers
  // -----------------------------------------------------------------------
  output logic [UQ0_16_W-1:0]          pue_base_lr,
  input  logic [UQ0_16_W-1:0]          pue_current_lr,
  input  logic [Q2_30_W-1:0]           pue_mean_update,
  output logic [31:0]                   pue_lr_adapt_win,
  output logic [UQ0_8_W-1:0]           pue_lr_fast_mult,
  output logic [UQ0_8_W-1:0]           pue_lr_fine_mult,
  output logic [UQ0_8_W-1:0]           pue_lr_damp_mult,
  output logic [UQ0_8_W-1:0]           pue_lr_track_mult,

  // -----------------------------------------------------------------------
  // CE Registers
  // -----------------------------------------------------------------------
  output logic [31:0]                   ce_window,
  output logic [31:0]                   ce_update_period,
  input  logic                          ce_busy,
  input  logic                          ce_update_done,

  // -----------------------------------------------------------------------
  // CA Registers
  // -----------------------------------------------------------------------
  input  logic [UQ0_32_W-1:0]          ca_global_coh,
  input  logic [UQ0_32_W-1:0]          ca_panel0_coh,
  input  logic [UQ0_32_W-1:0]          ca_panel1_coh,
  input  logic [UQ0_32_W-1:0]          ca_beam_coh [MAX_BEAMS],

  // -----------------------------------------------------------------------
  // TC Registers
  // -----------------------------------------------------------------------
  output logic [UQ0_32_W-1:0]          tc_coh_threshold,
  output logic [UQ0_32_W-1:0]          tc_hysteresis,
  output logic [31:0]                   tc_stab_window,
  output logic [UQ0_32_W-1:0]          tc_stab_var_max,
  input  sync_state_e                   tc_sync_state,
  input  logic [UQ0_32_W-1:0]          tc_coh_history [COH_HISTORY_LEN],

  // -----------------------------------------------------------------------
  // SVG Registers
  // -----------------------------------------------------------------------
  output logic                          svg_start,
  output logic [Q9_7_W-1:0]            svg_azimuth,
  output logic [Q9_7_W-1:0]            svg_elevation,
  output logic [BEAM_IDX_W-1:0]        svg_beam_id,
  input  logic                          svg_done,

  // -----------------------------------------------------------------------
  // MBC Registers
  // -----------------------------------------------------------------------
  output logic [3:0]                    mbc_active_mask,
  output sched_mode_e                   mbc_sched_mode,
  input  beam_context_t                 mbc_beam_ctx [MAX_BEAMS],

  // -----------------------------------------------------------------------
  // PHC Registers
  // -----------------------------------------------------------------------
  input  logic                          phc_active_panel,
  output logic [31:0]                   phc_rotation_deg,
  input  logic [31:0]                   phc_handover_cnt,
  input  logic [31:0]                   phc_reacq_iters,
  input  logic [UQ0_32_W-1:0]          phc_reacq_coh,

  // -----------------------------------------------------------------------
  // PWR Registers
  // -----------------------------------------------------------------------
  input  power_state_e                  pwr_state,
  input  logic [UQ8_8_W-1:0]           pwr_current_w,
  input  logic [Q8_8_W-1:0]            pwr_junc_temp,
  output logic [Q8_8_W-1:0]            pwr_throttle_temp,
  output logic [Q8_8_W-1:0]            pwr_max_temp,
  output logic [UQ8_8_W-1:0]           pwr_idle_power,
  output logic [UQ8_8_W-1:0]           pwr_sync_power,
  output logic [UQ8_8_W-1:0]           pwr_beam_power
);

  // =========================================================================
  // Internal Registers
  // =========================================================================
  logic [31:0] gcr_ctrl_reg;
  logic [31:0] gcr_irq_en_reg;
  logic [31:0] gcr_irq_stat_reg;
  logic [31:0] gcr_freq_band_reg;
  logic [31:0] gcr_carrier_reg;
  logic [31:0] gcr_bandwidth_reg;

  logic [31:0] mfu_ctrl_reg;
  logic [31:0] pue_ctrl_reg;
  logic [31:0] ce_ctrl_reg;
  logic [31:0] ca_ctrl_reg;
  logic [31:0] tc_ctrl_reg;
  logic [31:0] svg_ctrl_reg;
  logic [31:0] mbc_ctrl_reg;
  logic [31:0] phc_ctrl_reg;

  // =========================================================================
  // Register decode: extract unit from address[15:8]
  // =========================================================================
  logic [7:0] unit_sel;
  logic [7:0] reg_offset;

  assign unit_sel   = reg_req.addr[15:8];
  assign reg_offset = reg_req.addr[7:0];

  // =========================================================================
  // Write Logic
  // =========================================================================
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      gcr_ctrl_reg      <= {8'd2, 8'd50, 2'b10, 2'b00, 4'b1000}; // Default: 2 panels, 50 iter, sub-THz-low
      gcr_irq_en_reg    <= '0;
      gcr_irq_stat_reg  <= '0;
      gcr_carrier_reg   <= 32'h008C0000; // 140.0 in UQ16.16
      gcr_bandwidth_reg <= 32'h000A0000; // 10.0 in UQ16.16

      mfu_ctrl_reg      <= 32'h00000001; // Enable
      pue_ctrl_reg      <= 32'h00000001;
      ce_ctrl_reg       <= 32'h00000001;
      ca_ctrl_reg       <= 32'h00000001;
      tc_ctrl_reg       <= 32'h00000001;
      svg_ctrl_reg      <= '0;
      mbc_ctrl_reg      <= '0;
      phc_ctrl_reg      <= '0;

      // PUE defaults
      pue_base_lr       <= DEFAULT_LR;
      pue_lr_adapt_win  <= 32'd10;
      pue_lr_fast_mult  <= LR_FAST_MULT;
      pue_lr_fine_mult  <= LR_FINE_MULT;
      pue_lr_damp_mult  <= LR_DAMP_MULT;
      pue_lr_track_mult <= LR_TRACK_MULT;

      // CE defaults
      ce_window         <= 32'd16;
      ce_update_period  <= 32'd16;

      // TC defaults
      tc_coh_threshold  <= COH_THRESH_95;
      tc_hysteresis     <= HYSTERESIS_02;
      tc_stab_window    <= 32'd5;
      tc_stab_var_max   <= STAB_VAR_001;

      // SVG defaults
      svg_azimuth       <= '0;
      svg_elevation     <= '0;
      svg_beam_id       <= '0;

      // MBC defaults
      mbc_active_mask   <= 4'b0001;
      mbc_sched_mode    <= SCHED_ROUND_ROBIN;

      // PHC defaults
      phc_rotation_deg  <= '0;

      // PWR defaults
      pwr_throttle_temp <= 16'h5A00; // 90.0 C in Q8.8
      pwr_max_temp      <= 16'h6900; // 105.0 C in Q8.8
      pwr_idle_power    <= 16'h0080; // 0.5 W
      pwr_sync_power    <= 16'h0300; // 3.0 W
      pwr_beam_power    <= 16'h0800; // 8.0 W
    end else if (reg_req.valid && reg_req.wr) begin
      case (unit_sel)
        8'h00: begin // GCR
          case (reg_offset)
            GCR_CTRL_OFF:     gcr_ctrl_reg      <= reg_req.wdata;
            GCR_IRQ_EN_OFF:   gcr_irq_en_reg    <= reg_req.wdata;
            GCR_IRQ_STAT_OFF: gcr_irq_stat_reg  <= gcr_irq_stat_reg & ~reg_req.wdata; // W1C
            GCR_FREQ_BAND_OFF:gcr_freq_band_reg <= reg_req.wdata;
            GCR_CARRIER_OFF:  gcr_carrier_reg   <= reg_req.wdata;
            8'h24:            gcr_bandwidth_reg <= reg_req.wdata;
            default: ;
          endcase
        end

        8'h01: begin // MFU
          if (reg_offset == 8'h00) mfu_ctrl_reg <= reg_req.wdata;
        end

        8'h02: begin // PUE
          case (reg_offset)
            8'h00: pue_ctrl_reg      <= reg_req.wdata;
            8'h04: pue_base_lr       <= reg_req.wdata[UQ0_16_W-1:0];
            8'h10: pue_lr_adapt_win  <= reg_req.wdata;
            8'h14: pue_lr_fast_mult  <= reg_req.wdata[UQ0_8_W-1:0];
            8'h16: pue_lr_fine_mult  <= reg_req.wdata[UQ0_8_W-1:0];
            8'h18: pue_lr_damp_mult  <= reg_req.wdata[UQ0_8_W-1:0];
            8'h1A: pue_lr_track_mult <= reg_req.wdata[UQ0_8_W-1:0];
            default: ;
          endcase
        end

        8'h03: begin // CE
          case (reg_offset)
            8'h00: ce_ctrl_reg       <= reg_req.wdata;
            8'h04: ce_window         <= reg_req.wdata;
            8'h0C: ce_update_period  <= reg_req.wdata;
            default: ;
          endcase
        end

        8'h04: begin // CA
          if (reg_offset == 8'h00) ca_ctrl_reg <= reg_req.wdata;
        end

        8'h05: begin // TC
          case (reg_offset)
            8'h00: tc_ctrl_reg       <= reg_req.wdata;
            8'h04: tc_coh_threshold  <= reg_req.wdata;
            8'h08: tc_hysteresis     <= reg_req.wdata;
            8'h0C: tc_stab_window    <= reg_req.wdata;
            8'h10: tc_stab_var_max   <= reg_req.wdata;
            default: ;
          endcase
        end

        8'h06: begin // SVG
          case (reg_offset)
            8'h00: svg_ctrl_reg <= reg_req.wdata;
            8'h04: svg_azimuth  <= reg_req.wdata[Q9_7_W-1:0];
            8'h08: svg_elevation<= reg_req.wdata[Q9_7_W-1:0];
            8'h0C: svg_beam_id  <= reg_req.wdata[BEAM_IDX_W-1:0];
            default: ;
          endcase
        end

        8'h07: begin // MBC
          case (reg_offset)
            8'h00: mbc_ctrl_reg   <= reg_req.wdata;
            8'h04: mbc_active_mask<= reg_req.wdata[3:0];
            8'h08: mbc_sched_mode <= sched_mode_e'(reg_req.wdata[0]);
            default: ;
          endcase
        end

        8'h08: begin // PHC
          case (reg_offset)
            8'h00: phc_ctrl_reg    <= reg_req.wdata;
            8'h08: phc_rotation_deg<= reg_req.wdata;
            default: ;
          endcase
        end

        8'h0B: begin // PWR
          case (reg_offset)
            8'h10: pwr_throttle_temp <= reg_req.wdata[Q8_8_W-1:0];
            8'h14: pwr_max_temp      <= reg_req.wdata[Q8_8_W-1:0];
            8'h18: pwr_idle_power    <= reg_req.wdata[UQ8_8_W-1:0];
            8'h1C: pwr_sync_power    <= reg_req.wdata[UQ8_8_W-1:0];
            8'h20: pwr_beam_power    <= reg_req.wdata[UQ8_8_W-1:0];
            default: ;
          endcase
        end

        default: ;
      endcase
    end

    // Auto-clear soft reset
    if (gcr_ctrl_reg[1])
      gcr_ctrl_reg[1] <= 1'b0;

    // Latch interrupt status
    gcr_irq_stat_reg <= gcr_irq_stat_reg | gcr_irq_raw;
  end

  // =========================================================================
  // Read Logic
  // =========================================================================
  logic [31:0] rdata;
  logic        rvalid;
  logic        rerror;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rdata  <= '0;
      rvalid <= 1'b0;
      rerror <= 1'b0;
    end else begin
      rvalid <= reg_req.valid && !reg_req.wr;
      rerror <= 1'b0;

      if (reg_req.valid && !reg_req.wr) begin
        case (unit_sel)
          8'h00: begin // GCR
            case (reg_offset)
              GCR_CTRL_OFF:       rdata <= gcr_ctrl_reg;
              GCR_STATUS_OFF:     rdata <= {6'd0, gcr_thermal_crit, gcr_thermal_warn,
                                            gcr_failed_elements, gcr_active_elements,
                                            gcr_active_beams, gcr_sync_busy,
                                            gcr_sync_state};
              GCR_IRQ_EN_OFF:     rdata <= gcr_irq_en_reg;
              GCR_IRQ_STAT_OFF:   rdata <= gcr_irq_stat_reg;
              GCR_SYNC_CNT_LO_OFF:rdata <= gcr_sync_count[31:0];
              GCR_SYNC_CNT_HI_OFF:rdata <= gcr_sync_count[63:32];
              GCR_CARRIER_OFF:    rdata <= gcr_carrier_reg;
              GCR_WAVELENGTH_OFF: rdata <= gcr_wavelength_mm;
              8'h24:              rdata <= gcr_bandwidth_reg;
              GCR_CHIP_ID_OFF:    rdata <= CHIP_ID;
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h01: begin // MFU
            case (reg_offset)
              8'h00: rdata <= mfu_ctrl_reg;
              8'h04: rdata <= mfu_sin_sum;
              8'h08: rdata <= mfu_cos_sum;
              8'h0C: rdata <= mfu_phi_mean;
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h02: begin // PUE
            case (reg_offset)
              8'h00: rdata <= pue_ctrl_reg;
              8'h04: rdata <= {16'd0, pue_base_lr};
              8'h08: rdata <= {16'd0, pue_current_lr};
              8'h0C: rdata <= pue_mean_update;
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h03: begin // CE
            case (reg_offset)
              8'h00: rdata <= ce_ctrl_reg;
              8'h04: rdata <= ce_window;
              8'h08: rdata <= {31'd0, ce_busy};
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h04: begin // CA
            case (reg_offset)
              8'h00: rdata <= ca_ctrl_reg;
              8'h04: rdata <= ca_global_coh;
              8'h08: rdata <= ca_panel0_coh;
              8'h0C: rdata <= ca_panel1_coh;
              8'h10: rdata <= ca_beam_coh[0];
              8'h14: rdata <= ca_beam_coh[1];
              8'h18: rdata <= ca_beam_coh[2];
              8'h1C: rdata <= ca_beam_coh[3];
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h05: begin // TC
            case (reg_offset)
              8'h00: rdata <= tc_ctrl_reg;
              8'h04: rdata <= tc_coh_threshold;
              8'h08: rdata <= tc_hysteresis;
              8'h0C: rdata <= tc_stab_window;
              8'h10: rdata <= tc_stab_var_max;
              8'h14: rdata <= {29'd0, tc_sync_state};
              8'h18: rdata <= tc_coh_history[0];
              8'h1C: rdata <= tc_coh_history[1];
              8'h20: rdata <= tc_coh_history[2];
              8'h24: rdata <= tc_coh_history[3];
              8'h28: rdata <= tc_coh_history[4];
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h06: begin // SVG
            case (reg_offset)
              8'h00: rdata <= svg_ctrl_reg;
              8'h04: rdata <= {16'd0, svg_azimuth};
              8'h08: rdata <= {16'd0, svg_elevation};
              8'h0C: rdata <= {30'd0, svg_beam_id};
              8'h10: rdata <= {31'd0, svg_done};
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h07: begin // MBC
            case (reg_offset)
              8'h00: rdata <= mbc_ctrl_reg;
              8'h04: rdata <= {28'd0, mbc_active_mask};
              8'h08: rdata <= {31'd0, mbc_sched_mode};
              // Beam 0
              8'h10: rdata <= {16'd0, mbc_beam_ctx[0].azimuth};
              8'h14: rdata <= {16'd0, mbc_beam_ctx[0].elevation};
              8'h18: rdata <= {16'd0, mbc_beam_ctx[0].gain};
              8'h1C: rdata <= {16'd0, mbc_beam_ctx[0].sidelobe};
              8'h20: rdata <= mbc_beam_ctx[0].user_id;
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h08: begin // PHC
            case (reg_offset)
              8'h00: rdata <= phc_ctrl_reg;
              8'h04: rdata <= {31'd0, phc_active_panel};
              8'h08: rdata <= phc_rotation_deg;
              8'h0C: rdata <= phc_handover_cnt;
              8'h10: rdata <= phc_reacq_iters;
              8'h14: rdata <= phc_reacq_coh;
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          8'h0B: begin // PWR
            case (reg_offset)
              8'h04: rdata <= {30'd0, pwr_state};
              8'h08: rdata <= {16'd0, pwr_current_w};
              8'h0C: rdata <= {16'd0, pwr_junc_temp};
              8'h10: rdata <= {16'd0, pwr_throttle_temp};
              8'h14: rdata <= {16'd0, pwr_max_temp};
              default: begin rdata <= '0; rerror <= 1'b1; end
            endcase
          end

          default: begin rdata <= '0; rerror <= 1'b1; end
        endcase
      end
    end
  end

  assign reg_rsp.valid = rvalid;
  assign reg_rsp.rdata = rdata;
  assign reg_rsp.error = rerror;

  // =========================================================================
  // GCR Control Field Extraction
  // =========================================================================
  assign gcr_enable     = gcr_ctrl_reg[0];
  assign gcr_soft_reset = gcr_ctrl_reg[1];
  assign gcr_sync_start = gcr_ctrl_reg[2];
  assign gcr_continuous = gcr_ctrl_reg[3];
  assign gcr_sync_mode  = sync_mode_e'(gcr_ctrl_reg[5:4]);
  assign gcr_freq_band  = freq_band_e'(gcr_ctrl_reg[7:6]);
  assign gcr_max_iter   = gcr_ctrl_reg[15:8];
  assign gcr_num_panels = gcr_ctrl_reg[23:16];

  assign gcr_irq_en     = gcr_irq_en_reg[NUM_IRQS-1:0];
  assign gcr_irq_out    = |(gcr_irq_stat_reg[NUM_IRQS-1:0] & gcr_irq_en_reg[NUM_IRQS-1:0]);

  assign gcr_carrier_ghz   = gcr_carrier_reg;
  assign gcr_bandwidth_ghz = gcr_bandwidth_reg;

  // MFU control extraction
  assign mfu_reg_enable     = mfu_ctrl_reg[0];
  assign mfu_reg_use_target = mfu_ctrl_reg[1];
  assign mfu_reg_beam_sel   = mfu_ctrl_reg[3:2];

  // SVG start pulse
  assign svg_start = svg_ctrl_reg[0]; // Bit 0 triggers computation

endmodule : reg_if
