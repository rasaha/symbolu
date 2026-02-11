//-----------------------------------------------------------------------------
// PCAM Top-Level Module
//-----------------------------------------------------------------------------
// Predictive Context Attention Memory (PCAM) FPGA Implementation
//
// This module integrates all PCAM components:
//   - Command decoder
//   - Bank array (64 parallel BRAM banks)
//   - Top-K selection network
//   - Update coalescer
//   - Decay engine
//
// Target: Xilinx Alveo U280 / AMD Versal / Intel Agilex
// Clock: 250-500 MHz
//-----------------------------------------------------------------------------

module pcam_top
    import pcam_pkg::*;
#(
    parameter int NUM_BANKS_PARAM = NUM_BANKS,
    parameter int K_MAX_PARAM = K_MAX,
    parameter int MAX_SEQ_PARAM = MAX_SEQUENCES
) (
    //-------------------------------------------------------------------------
    // Clock and Reset
    //-------------------------------------------------------------------------
    input  logic                          clk,
    input  logic                          rst_n,

    //-------------------------------------------------------------------------
    // AXI-Stream Command Interface (from host)
    //-------------------------------------------------------------------------
    input  logic [63:0]                   s_axis_cmd_tdata,
    input  logic                          s_axis_cmd_tvalid,
    output logic                          s_axis_cmd_tready,

    //-------------------------------------------------------------------------
    // AXI-Stream Response Interface (to host)
    //-------------------------------------------------------------------------
    output logic [255:0]                  m_axis_rsp_tdata,
    output logic                          m_axis_rsp_tvalid,
    input  logic                          m_axis_rsp_tready,
    output logic                          m_axis_rsp_tlast,

    //-------------------------------------------------------------------------
    // AXI-Lite Control Interface
    //-------------------------------------------------------------------------
    input  logic [31:0]                   s_axil_awaddr,
    input  logic                          s_axil_awvalid,
    output logic                          s_axil_awready,
    input  logic [31:0]                   s_axil_wdata,
    input  logic                          s_axil_wvalid,
    output logic                          s_axil_wready,
    output logic [1:0]                    s_axil_bresp,
    output logic                          s_axil_bvalid,
    input  logic                          s_axil_bready,
    input  logic [31:0]                   s_axil_araddr,
    input  logic                          s_axil_arvalid,
    output logic                          s_axil_arready,
    output logic [31:0]                   s_axil_rdata,
    output logic [1:0]                    s_axil_rresp,
    output logic                          s_axil_rvalid,
    input  logic                          s_axil_rready,

    //-------------------------------------------------------------------------
    // Interrupt
    //-------------------------------------------------------------------------
    output logic                          irq,

    //-------------------------------------------------------------------------
    // Debug
    //-------------------------------------------------------------------------
    output logic [63:0]                   debug_status
);

    //=========================================================================
    // Internal Signals
    //=========================================================================

    // Decoded command
    command_t                     cmd_decoded;
    logic                         cmd_valid;
    logic                         cmd_ready;

    // Bank array interface
    logic [BLOCK_ID_WIDTH-1:0]    bank_rd_block_ids [NUM_BANKS_PARAM];
    logic [NUM_BANKS_PARAM-1:0]   bank_rd_en;
    block_entry_t                 bank_rd_entries [NUM_BANKS_PARAM];
    logic [NUM_BANKS_PARAM-1:0]   bank_rd_valid;
    logic [BLOCK_ID_WIDTH-1:0]    bank_wr_block_id;
    logic [SCORE_WIDTH-1:0]       bank_wr_weight;
    logic                         bank_wr_en;
    logic                         bank_wr_done;
    logic [NUM_BANKS_PARAM-1:0]   bank_busy;

    // Top-K selection
    candidate_t                   topk_in [NUM_BANKS_PARAM];
    logic [NUM_BANKS_PARAM-1:0]   topk_in_valid;
    logic                         topk_in_last;
    candidate_t                   topk_out [K_MAX_PARAM];
    logic [K_WIDTH-1:0]           topk_out_count;
    logic                         topk_out_valid;
    logic                         topk_out_ready;

    // Multi-beat response state
    logic [K_WIDTH-1:0]           rsp_beat_idx;     // Current candidate index
    logic                         rsp_in_progress;  // Multi-beat transfer active

    // Performance counters
    logic [31:0]                  attend_count;
    logic [31:0]                  update_count;
    logic [31:0]                  bank_conflict_count;
    logic [31:0]                  cycle_count;

    // FSM state
    typedef enum logic [3:0] {
        IDLE,
        ATTEND_BANK_READ,
        ATTEND_TOPK,
        ATTEND_RESPONSE,
        UPDATE_RMW,
        UPDATE_DONE,
        DECAY_SWEEP,
        ALLOC_SEQ,
        FREE_SEQ,
        ERROR
    } state_t;

    state_t state, next_state;

    //=========================================================================
    // Command Decoder
    //=========================================================================

    // Parse incoming command
    always_comb begin
        cmd_decoded.op_type     = op_type_t'(s_axis_cmd_tdata[63:61]);
        cmd_decoded.seq_id      = s_axis_cmd_tdata[60:55];
        cmd_decoded.query_block = s_axis_cmd_tdata[54:35];
        cmd_decoded.key_block   = s_axis_cmd_tdata[34:15];
        cmd_decoded.data        = s_axis_cmd_tdata[14:0];
    end

    assign cmd_valid = s_axis_cmd_tvalid && s_axis_cmd_tready;
    assign s_axis_cmd_tready = (state == IDLE);

    //=========================================================================
    // Main State Machine
    //=========================================================================

    // State register
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end

    // Next state logic
    always_comb begin
        next_state = state;

        case (state)
            IDLE: begin
                if (cmd_valid) begin
                    case (cmd_decoded.op_type)
                        OP_ATTEND:       next_state = ATTEND_BANK_READ;
                        OP_UPDATE:       next_state = UPDATE_RMW;
                        OP_BATCH_UPDATE: next_state = UPDATE_RMW;
                        OP_DECAY:        next_state = DECAY_SWEEP;
                        OP_ALLOC:        next_state = ALLOC_SEQ;
                        OP_FREE:         next_state = FREE_SEQ;
                        default:         next_state = ERROR;
                    endcase
                end
            end

            ATTEND_BANK_READ: begin
                // Wait for all bank reads to complete
                if (&bank_rd_valid) begin
                    next_state = ATTEND_TOPK;
                end
            end

            ATTEND_TOPK: begin
                // Wait for Top-K selection to complete
                if (topk_out_valid) begin
                    next_state = ATTEND_RESPONSE;
                end
            end

            ATTEND_RESPONSE: begin
                // Wait for all response beats to be accepted
                if (m_axis_rsp_tvalid && m_axis_rsp_tready && m_axis_rsp_tlast) begin
                    next_state = IDLE;
                end
            end

            UPDATE_RMW: begin
                // Wait for RMW to complete
                if (bank_wr_done) begin
                    next_state = UPDATE_DONE;
                end
            end

            UPDATE_DONE: begin
                next_state = IDLE;
            end

            DECAY_SWEEP: begin
                // Decay handled by background engine
                next_state = IDLE;
            end

            ALLOC_SEQ: begin
                next_state = IDLE;
            end

            FREE_SEQ: begin
                next_state = IDLE;
            end

            ERROR: begin
                next_state = IDLE;
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    //=========================================================================
    // Bank Array Instance
    //=========================================================================

    bank_array #(
        .NUM_BANKS_PARAM(NUM_BANKS_PARAM)
    ) u_bank_array (
        .clk(clk),
        .rst_n(rst_n),

        .rd_block_ids(bank_rd_block_ids),
        .rd_en(bank_rd_en),
        .rd_entries(bank_rd_entries),
        .rd_valid(bank_rd_valid),

        .wr_block_id(bank_wr_block_id),
        .wr_weight(bank_wr_weight),
        .wr_en(bank_wr_en),
        .wr_done(bank_wr_done),

        .bank_busy(bank_busy)
    );

    //=========================================================================
    // ATTEND Logic
    //=========================================================================

    // Bank read enable during ATTEND
    always_comb begin
        bank_rd_en = '0;
        for (int i = 0; i < NUM_BANKS_PARAM; i++) begin
            bank_rd_block_ids[i] = '0;
        end

        if (state == ATTEND_BANK_READ) begin
            // Read from all banks in parallel
            // In full implementation, query hash determines which blocks to read
            bank_rd_en = '1;

            // Generate block IDs for each bank (simplified: consecutive blocks)
            for (int i = 0; i < NUM_BANKS_PARAM; i++) begin
                bank_rd_block_ids[i] = cmd_decoded.query_block + i[BLOCK_ID_WIDTH-1:0];
            end
        end
    end

    // Prepare candidates for Top-K from bank read results
    always_comb begin
        for (int i = 0; i < NUM_BANKS_PARAM; i++) begin
            topk_in[i].score    = bank_rd_entries[i].score;
            topk_in[i].block_id = bank_rd_block_ids[i];
        end
        topk_in_valid = bank_rd_valid;
        topk_in_last  = (state == ATTEND_BANK_READ) && (&bank_rd_valid);
    end

    //=========================================================================
    // UPDATE Logic
    //=========================================================================

    assign bank_wr_block_id = cmd_decoded.key_block;
    assign bank_wr_weight   = {1'b0, cmd_decoded.data};  // Extend to 16 bits
    assign bank_wr_en       = (state == UPDATE_RMW);

    //=========================================================================
    // Response Generation (Multi-Beat for K=256)
    //=========================================================================
    //
    // Response format:
    //   Beat 0:  [count(9) | reserved(7) | candidate[0..5](36×6=216) | pad(24)]
    //   Beat N:  [candidate[6N..6N+5](36×6=216) | pad(40)]
    //   Last beat: tlast=1
    //
    // At K=256, need ceil(256/6) = 43 beats max.
    // Candidates per beat: floor((256-0)/36) = 6 (after first beat header)
    //
    localparam int CANDIDATES_PER_BEAT = 6;
    localparam int TOTAL_BEATS_MAX = (K_MAX_PARAM + CANDIDATES_PER_BEAT - 1) / CANDIDATES_PER_BEAT;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_axis_rsp_tdata  <= '0;
            m_axis_rsp_tvalid <= 1'b0;
            m_axis_rsp_tlast  <= 1'b0;
            rsp_beat_idx      <= '0;
            rsp_in_progress   <= 1'b0;
        end else begin
            // Start multi-beat response when entering ATTEND_RESPONSE
            if (state == ATTEND_RESPONSE && !rsp_in_progress && !m_axis_rsp_tvalid) begin
                rsp_in_progress <= 1'b1;
                rsp_beat_idx    <= '0;

                // First beat: header + first 6 candidates
                m_axis_rsp_tdata <= '0;
                m_axis_rsp_tdata[K_WIDTH-1:0] <= topk_out_count;

                for (int i = 0; i < CANDIDATES_PER_BEAT; i++) begin
                    if (i < topk_out_count) begin
                        m_axis_rsp_tdata[16 + i*36 +: 36] <= {
                            topk_out[i].score,
                            topk_out[i].block_id
                        };
                    end
                end

                m_axis_rsp_tvalid <= 1'b1;
                // Single beat if K_eff <= 6
                m_axis_rsp_tlast  <= (topk_out_count <= CANDIDATES_PER_BEAT);
                rsp_beat_idx      <= CANDIDATES_PER_BEAT[K_WIDTH-1:0];

            end else if (rsp_in_progress && m_axis_rsp_tvalid && m_axis_rsp_tready) begin
                // Current beat accepted — send next or finish
                if (m_axis_rsp_tlast) begin
                    // Transfer complete
                    m_axis_rsp_tvalid <= 1'b0;
                    m_axis_rsp_tlast  <= 1'b0;
                    rsp_in_progress   <= 1'b0;
                end else begin
                    // Pack next 6 candidates
                    m_axis_rsp_tdata <= '0;

                    for (int i = 0; i < CANDIDATES_PER_BEAT; i++) begin
                        if ((rsp_beat_idx + i[K_WIDTH-1:0]) < topk_out_count) begin
                            m_axis_rsp_tdata[i*36 +: 36] <= {
                                topk_out[rsp_beat_idx + i[K_WIDTH-1:0]].score,
                                topk_out[rsp_beat_idx + i[K_WIDTH-1:0]].block_id
                            };
                        end
                    end

                    rsp_beat_idx <= rsp_beat_idx + CANDIDATES_PER_BEAT[K_WIDTH-1:0];
                    m_axis_rsp_tvalid <= 1'b1;

                    // Check if next beat is the last
                    m_axis_rsp_tlast <= ((rsp_beat_idx + CANDIDATES_PER_BEAT[K_WIDTH-1:0]) >= topk_out_count);
                end
            end
        end
    end

    //=========================================================================
    // Performance Counters
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            attend_count        <= '0;
            update_count        <= '0;
            bank_conflict_count <= '0;
            cycle_count         <= '0;
        end else begin
            cycle_count <= cycle_count + 1;

            if (cmd_valid && cmd_decoded.op_type == OP_ATTEND) begin
                attend_count <= attend_count + 1;
            end

            if (cmd_valid && cmd_decoded.op_type == OP_UPDATE) begin
                update_count <= update_count + 1;
            end

            // Count bank conflicts (simplified: any bank busy during read)
            if (state == ATTEND_BANK_READ && |bank_busy) begin
                bank_conflict_count <= bank_conflict_count + 1;
            end
        end
    end

    //=========================================================================
    // AXI-Lite Control/Status Registers
    //=========================================================================

    // Simplified CSR implementation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axil_awready <= 1'b0;
            s_axil_wready  <= 1'b0;
            s_axil_bresp   <= 2'b00;
            s_axil_bvalid  <= 1'b0;
            s_axil_arready <= 1'b0;
            s_axil_rdata   <= '0;
            s_axil_rresp   <= 2'b00;
            s_axil_rvalid  <= 1'b0;
        end else begin
            // Write handling
            s_axil_awready <= s_axil_awvalid && !s_axil_awready;
            s_axil_wready  <= s_axil_wvalid && !s_axil_wready;

            if (s_axil_awready && s_axil_wready) begin
                s_axil_bvalid <= 1'b1;
            end else if (s_axil_bvalid && s_axil_bready) begin
                s_axil_bvalid <= 1'b0;
            end

            // Read handling
            s_axil_arready <= s_axil_arvalid && !s_axil_arready;

            if (s_axil_arready) begin
                s_axil_rvalid <= 1'b1;

                case (s_axil_araddr[7:0])
                    8'h00: s_axil_rdata <= attend_count;
                    8'h04: s_axil_rdata <= update_count;
                    8'h08: s_axil_rdata <= bank_conflict_count;
                    8'h0C: s_axil_rdata <= cycle_count;
                    8'h10: s_axil_rdata <= {28'b0, state};
                    default: s_axil_rdata <= 32'hDEADBEEF;
                endcase
            end else if (s_axil_rvalid && s_axil_rready) begin
                s_axil_rvalid <= 1'b0;
            end
        end
    end

    //=========================================================================
    // Interrupt Generation
    //=========================================================================

    // Generate interrupt on operation completion (simplified)
    assign irq = (state == ATTEND_RESPONSE) || (state == UPDATE_DONE);

    //=========================================================================
    // Debug Status
    //=========================================================================

    assign debug_status = {
        16'h0,                    // [63:48] Reserved
        attend_count[15:0],       // [47:32] ATTEND count
        update_count[15:0],       // [31:16] UPDATE count
        bank_conflict_count[7:0], // [15:8]  Bank conflicts
        4'b0,                     // [7:4]   Reserved
        state                     // [3:0]   FSM state
    };

    //=========================================================================
    // Top-K Network (Placeholder - full implementation in topk_network.sv)
    //=========================================================================

    // Simplified Top-K: just pass through first K entries
    // Full implementation uses bitonic sorting network
    always_comb begin
        topk_out_count = K_DEFAULT[K_WIDTH-1:0];
        topk_out_valid = topk_in_last;

        for (int i = 0; i < K_MAX_PARAM; i++) begin
            if (i < NUM_BANKS_PARAM) begin
                topk_out[i] = topk_in[i];
            end else begin
                topk_out[i] = '0;
            end
        end
    end

    assign topk_out_ready = m_axis_rsp_tready;

    //=========================================================================
    // Assertions
    //=========================================================================

`ifdef SIMULATION
    // Check for valid state transitions
    always @(posedge clk) begin
        if (state == ERROR)
            $warning("pcam_top: Entered ERROR state");
    end

    // Monitor bank conflicts
    always @(posedge clk) begin
        if (bank_conflict_count > 1000)
            $warning("pcam_top: High bank conflict rate: %0d", bank_conflict_count);
    end
`endif

endmodule : pcam_top
