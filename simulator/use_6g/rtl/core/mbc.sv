// =============================================================================
// Multi-Beam Controller (MBC)
// =============================================================================
// Manages 4 concurrent beam contexts with independent steering vectors
// Each beam context stores: az/el, 128 steering phases, user_id, active flag
// Scheduling: round-robin or priority override
// Beam context storage: 4 x 128 x 32b = 2 KB
// =============================================================================

module mbc
  import use_6g_pkg::*;
(
  input  logic                          clk,
  input  logic                          rst_n,

  // -----------------------------------------------------------------------
  // Control
  // -----------------------------------------------------------------------
  input  logic                          enable,
  input  logic [3:0]                    active_mask,       // Beam active bits [3:0]
  input  sched_mode_e                   sched_mode,

  // -----------------------------------------------------------------------
  // Beam steer request
  // -----------------------------------------------------------------------
  input  logic                          steer_req,
  input  logic [BEAM_IDX_W-1:0]        steer_beam_id,
  input  logic [Q9_7_W-1:0]            steer_azimuth,
  input  logic [Q9_7_W-1:0]            steer_elevation,
  input  logic [31:0]                   steer_user_id,

  // -----------------------------------------------------------------------
  // SVG interface (steering vector computation)
  // -----------------------------------------------------------------------
  output logic                          svg_start,
  output logic [Q9_7_W-1:0]            svg_azimuth,
  output logic [Q9_7_W-1:0]            svg_elevation,
  output logic [BEAM_IDX_W-1:0]        svg_beam_id,

  input  logic [Q2_30_W-1:0]           svg_steering [NUM_ELEMENTS],
  input  logic [BEAM_IDX_W-1:0]        svg_beam_id_done,
  input  logic                          svg_done,

  // -----------------------------------------------------------------------
  // Active beam steering output (muxed to MFU target input)
  // -----------------------------------------------------------------------
  output logic [Q2_30_W-1:0]           active_steering [NUM_ELEMENTS],
  output logic [BEAM_IDX_W-1:0]        active_beam_id,

  // -----------------------------------------------------------------------
  // Beam quality inputs (from BQM)
  // -----------------------------------------------------------------------
  input  logic [Q8_8_W-1:0]            beam_gain   [MAX_BEAMS],
  input  logic [Q8_8_W-1:0]            beam_sidelobe [MAX_BEAMS],

  // -----------------------------------------------------------------------
  // Register interface
  // -----------------------------------------------------------------------
  output beam_context_t                 beam_ctx [MAX_BEAMS],

  // -----------------------------------------------------------------------
  // Status
  // -----------------------------------------------------------------------
  output logic                          steer_done,
  output logic [3:0]                    active_beam_count,
  output logic                          busy
);

  // =========================================================================
  // Beam Context Storage
  // =========================================================================
  // Steering vectors: 4 beams x 128 elements x Q2.30
  logic [Q2_30_W-1:0] beam_steering [MAX_BEAMS][NUM_ELEMENTS];

  // Beam metadata
  beam_context_t ctx [MAX_BEAMS];

  // =========================================================================
  // Round-Robin Scheduler
  // =========================================================================
  logic [BEAM_IDX_W-1:0] rr_current;
  logic [BEAM_IDX_W-1:0] next_active_beam;

  // Find next active beam in round-robin order
  always_comb begin
    next_active_beam = rr_current;
    for (int tries = 0; tries < MAX_BEAMS; tries++) begin
      automatic logic [BEAM_IDX_W-1:0] candidate;
      candidate = (rr_current + tries[BEAM_IDX_W-1:0] + 1) % MAX_BEAMS;
      if (active_mask[candidate] && ctx[candidate].active) begin
        next_active_beam = candidate;
        break;
      end
    end
  end

  // =========================================================================
  // Steer Request FSM
  // =========================================================================
  typedef enum logic [1:0] {
    MBC_IDLE,
    MBC_STEER_REQ,
    MBC_WAIT_SVG,
    MBC_STORE
  } mbc_state_e;

  mbc_state_e mbc_state;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      mbc_state   <= MBC_IDLE;
      svg_start   <= 1'b0;
      steer_done  <= 1'b0;
      rr_current  <= '0;
      for (int b = 0; b < MAX_BEAMS; b++) begin
        ctx[b].azimuth   <= '0;
        ctx[b].elevation <= '0;
        ctx[b].gain      <= '0;
        ctx[b].sidelobe  <= '0;
        ctx[b].user_id   <= '0;
        ctx[b].active    <= 1'b0;
        for (int e = 0; e < NUM_ELEMENTS; e++)
          beam_steering[b][e] <= '0;
      end
    end else begin
      svg_start  <= 1'b0;
      steer_done <= 1'b0;

      case (mbc_state)
        MBC_IDLE: begin
          if (steer_req && enable) begin
            mbc_state <= MBC_STEER_REQ;
          end else begin
            // Advance round-robin on each idle cycle
            if (sched_mode == SCHED_ROUND_ROBIN)
              rr_current <= next_active_beam;
          end
        end

        MBC_STEER_REQ: begin
          // Issue SVG computation request
          svg_start     <= 1'b1;
          svg_azimuth   <= steer_azimuth;
          svg_elevation <= steer_elevation;
          svg_beam_id   <= steer_beam_id;

          // Update context metadata
          ctx[steer_beam_id].azimuth   <= steer_azimuth;
          ctx[steer_beam_id].elevation <= steer_elevation;
          ctx[steer_beam_id].user_id   <= steer_user_id;
          ctx[steer_beam_id].active    <= 1'b1;

          mbc_state <= MBC_WAIT_SVG;
        end

        MBC_WAIT_SVG: begin
          if (svg_done) begin
            mbc_state <= MBC_STORE;
          end
        end

        MBC_STORE: begin
          // Store computed steering vector
          for (int e = 0; e < NUM_ELEMENTS; e++)
            beam_steering[svg_beam_id_done][e] <= svg_steering[e];
          steer_done <= 1'b1;
          mbc_state  <= MBC_IDLE;
        end

        default: mbc_state <= MBC_IDLE;
      endcase

      // Continuously update beam quality from BQM
      for (int b = 0; b < MAX_BEAMS; b++) begin
        ctx[b].gain     <= beam_gain[b];
        ctx[b].sidelobe <= beam_sidelobe[b];
      end
    end
  end

  assign busy = (mbc_state != MBC_IDLE);

  // =========================================================================
  // Active Beam Steering Output (muxed)
  // =========================================================================
  assign active_beam_id = rr_current;

  genvar gi;
  generate
    for (gi = 0; gi < NUM_ELEMENTS; gi++) begin : g_steer_mux
      assign active_steering[gi] = beam_steering[rr_current][gi];
    end
  endgenerate

  // =========================================================================
  // Status
  // =========================================================================
  always_comb begin
    active_beam_count = '0;
    for (int b = 0; b < MAX_BEAMS; b++)
      if (active_mask[b] && ctx[b].active)
        active_beam_count = active_beam_count + 1;
  end

  // Export contexts
  assign beam_ctx = ctx;

endmodule : mbc
