// =============================================================================
// Element Phase Register File (EPRF)
// =============================================================================
// 128 entries x 152 bits per-element state
// Ports:
//   - 1 x 128-wide parallel read (all phases in 1 cycle)
//   - 1 x 128-wide parallel write (all phases in 1 cycle)
//   - 1 x single-entry RW (register bus access)
// Implemented as low-leakage 8T SRAM equivalent (always-on)
// =============================================================================

module eprf
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Parallel read port: all 128 phases in 1 cycle
  // -----------------------------------------------------------------------
  input  logic                          par_rd_en,
  output logic [Q2_30_W-1:0]           par_phase_out     [NUM_ELEMENTS],
  output logic [Q2_30_W-1:0]           par_target_out    [NUM_ELEMENTS],
  output logic [7:0]                    par_flags_out     [NUM_ELEMENTS],
  output logic                          par_rd_valid,

  // -----------------------------------------------------------------------
  // Parallel write port: update all 128 phases in 1 cycle
  // -----------------------------------------------------------------------
  input  logic                          par_wr_en,
  input  logic [Q2_30_W-1:0]           par_phase_in      [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Single-entry register access (for bus interface)
  // -----------------------------------------------------------------------
  input  logic                          reg_rd_en,
  input  logic                          reg_wr_en,
  input  logic [ELEM_IDX_W-1:0]        reg_elem_idx,
  input  logic [2:0]                    reg_field_sel,   // 0=phase,1=target,2=cal_phi,3=cal_a,4=pos_x,5=pos_y,6=flags
  input  logic [Q2_30_W-1:0]           reg_wdata,
  output logic [Q2_30_W-1:0]           reg_rdata,
  output logic                          reg_rd_valid,

  // -----------------------------------------------------------------------
  // Element position outputs (for SVG)
  // -----------------------------------------------------------------------
  output logic [Q8_8_W-1:0]            pos_x_out         [NUM_ELEMENTS],
  output logic [Q8_8_W-1:0]            pos_y_out         [NUM_ELEMENTS],
  output logic [Q1_15_W-1:0]           cal_offset_out    [NUM_ELEMENTS],

  // -----------------------------------------------------------------------
  // Status outputs
  // -----------------------------------------------------------------------
  output logic [7:0]                    active_count,     // Number of active elements
  output logic [7:0]                    failed_count      // Number of failed elements
);

  // -------------------------------------------------------------------------
  // Storage: 128 element state registers
  // -------------------------------------------------------------------------
  element_state_t elem_state [NUM_ELEMENTS];

  // -------------------------------------------------------------------------
  // Parallel read: output all phases in 1 cycle
  // -------------------------------------------------------------------------
  logic par_rd_en_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      par_rd_en_r <= 1'b0;
    end else begin
      par_rd_en_r <= par_rd_en;
    end
  end

  assign par_rd_valid = par_rd_en_r;

  genvar gi;
  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_par_read
      assign par_phase_out[gi]  = elem_state[gi].phase;
      assign par_target_out[gi] = elem_state[gi].target_phase;
      assign par_flags_out[gi]  = elem_state[gi].flags;
      assign pos_x_out[gi]      = elem_state[gi].pos_x;
      assign pos_y_out[gi]      = elem_state[gi].pos_y;
      assign cal_offset_out[gi] = elem_state[gi].phase_offset_cal;
    end
  endgenerate

  // -------------------------------------------------------------------------
  // Parallel write: update all 128 phases
  // -------------------------------------------------------------------------
  always_ff @(posedge clk) begin
    if (par_wr_en) begin
      for (int i = 0; i < NUM_ELEMENTS; i++) begin
        elem_state[i].phase <= par_phase_in[i];
      end
    end
  end

  // -------------------------------------------------------------------------
  // Single-entry register access
  // -------------------------------------------------------------------------
  logic reg_rd_en_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      reg_rd_en_r <= 1'b0;
      reg_rdata   <= '0;
    end else begin
      reg_rd_en_r <= reg_rd_en;
      if (reg_rd_en) begin
        case (reg_field_sel)
          3'd0: reg_rdata <= elem_state[reg_elem_idx].phase;
          3'd1: reg_rdata <= elem_state[reg_elem_idx].target_phase;
          3'd2: reg_rdata <= {{16{elem_state[reg_elem_idx].phase_offset_cal[15]}},
                              elem_state[reg_elem_idx].phase_offset_cal};
          3'd3: reg_rdata <= {16'd0, elem_state[reg_elem_idx].amplitude_cal};
          3'd4: reg_rdata <= {{16{elem_state[reg_elem_idx].pos_x[15]}},
                              elem_state[reg_elem_idx].pos_x};
          3'd5: reg_rdata <= {{16{elem_state[reg_elem_idx].pos_y[15]}},
                              elem_state[reg_elem_idx].pos_y};
          3'd6: reg_rdata <= {24'd0, elem_state[reg_elem_idx].flags};
          default: reg_rdata <= '0;
        endcase
      end
    end
  end

  assign reg_rd_valid = reg_rd_en_r;

  // Single-entry write
  always_ff @(posedge clk) begin
    if (reg_wr_en) begin
      case (reg_field_sel)
        3'd0: elem_state[reg_elem_idx].phase            <= reg_wdata;
        3'd1: elem_state[reg_elem_idx].target_phase     <= reg_wdata;
        3'd2: elem_state[reg_elem_idx].phase_offset_cal <= reg_wdata[Q1_15_W-1:0];
        3'd3: elem_state[reg_elem_idx].amplitude_cal    <= reg_wdata[UQ1_15_W-1:0];
        3'd4: elem_state[reg_elem_idx].pos_x            <= reg_wdata[Q8_8_W-1:0];
        3'd5: elem_state[reg_elem_idx].pos_y            <= reg_wdata[Q8_8_W-1:0];
        3'd6: elem_state[reg_elem_idx].flags             <= reg_wdata[7:0];
        default: ; // no-op
      endcase
    end
  end

  // -------------------------------------------------------------------------
  // Initialization: set default positions and flags
  // -------------------------------------------------------------------------
  initial begin
    for (int p = 0; p < NUM_PANELS; p++) begin
      for (int y = 0; y < NUM_ELEMENTS_Y; y++) begin
        for (int x = 0; x < NUM_ELEMENTS_X; x++) begin
          int idx = p * ELEMENTS_PER_PANEL + y * NUM_ELEMENTS_X + x;
          elem_state[idx].phase            = '0;
          elem_state[idx].target_phase     = '0;
          elem_state[idx].phase_offset_cal = '0;
          elem_state[idx].amplitude_cal    = 16'h7FFF; // 1.0 in UQ1.15
          // Position in half-wavelengths (Q8.8: 0.5 = 0x0080)
          elem_state[idx].pos_x            = 16'(x * 16'h0080); // x * 0.5λ
          elem_state[idx].pos_y            = 16'(y * 16'h0080); // y * 0.5λ
          elem_state[idx].flags            = {4'b0, p[1:0], 1'b0, 1'b1}; // active, not failed, panel_id
        end
      end
    end
  end

  // -------------------------------------------------------------------------
  // Status counters
  // -------------------------------------------------------------------------
  always_comb begin
    automatic logic [7:0] act_cnt = '0;
    automatic logic [7:0] fail_cnt = '0;
    for (int i = 0; i < NUM_ELEMENTS; i++) begin
      if (elem_state[i].flags[FLAG_ACTIVE])
        act_cnt = act_cnt + 8'd1;
      if (elem_state[i].flags[FLAG_FAILED])
        fail_cnt = fail_cnt + 8'd1;
    end
    active_count = act_cnt;
    failed_count = fail_cnt;
  end

endmodule : eprf
