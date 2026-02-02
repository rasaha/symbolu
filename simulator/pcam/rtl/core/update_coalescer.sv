//-----------------------------------------------------------------------------
// Update Coalescer
//-----------------------------------------------------------------------------
// Buffers multiple UPDATE operations and coalesces writes to the same block.
// This reduces BRAM RMW overhead by combining multiple weight updates.
//
// Features:
//   - CAM-based lookup for pending updates to same block
//   - Configurable buffer depth (default 64 entries)
//   - Automatic flush on timeout or buffer full
//   - Per-bank output queues for parallel writes
//
// Coalescing Rules:
//   - Same block_id within window → accumulate weights
//   - Different banks → parallel issue
//   - Timeout (64 cycles) or buffer full → flush oldest
//-----------------------------------------------------------------------------

module update_coalescer
    import pcam_pkg::*;
#(
    parameter int BUFFER_DEPTH = 64,
    parameter int TIMEOUT_CYCLES = 64,
    parameter int NUM_BANKS_PARAM = NUM_BANKS
) (
    input  logic                              clk,
    input  logic                              rst_n,

    //-------------------------------------------------------------------------
    // Input Interface (from command decoder)
    //-------------------------------------------------------------------------
    input  logic [BLOCK_ID_WIDTH-1:0]         in_block_id,
    input  logic [SCORE_WIDTH-1:0]            in_weight,
    input  logic [SEQ_ID_WIDTH-1:0]           in_seq_id,
    input  logic                              in_valid,
    output logic                              in_ready,

    //-------------------------------------------------------------------------
    // Output Interface (to bank controller)
    //-------------------------------------------------------------------------
    output logic [BLOCK_ID_WIDTH-1:0]         out_block_id,
    output logic [SCORE_WIDTH-1:0]            out_weight,
    output logic [SEQ_ID_WIDTH-1:0]           out_seq_id,
    output logic [BANK_ID_WIDTH-1:0]          out_bank_id,
    output logic                              out_valid,
    input  logic                              out_ready,

    //-------------------------------------------------------------------------
    // Flush Control
    //-------------------------------------------------------------------------
    input  logic                              flush_req,
    output logic                              flush_done,

    //-------------------------------------------------------------------------
    // Status
    //-------------------------------------------------------------------------
    output logic [$clog2(BUFFER_DEPTH):0]     buffer_occupancy,
    output logic [31:0]                       coalesce_count,
    output logic [31:0]                       total_updates
);

    //=========================================================================
    // Buffer Entry Definition
    //=========================================================================

    typedef struct packed {
        logic                         valid;
        logic [BLOCK_ID_WIDTH-1:0]    block_id;
        logic [SEQ_ID_WIDTH-1:0]      seq_id;
        logic [SCORE_WIDTH-1:0]       weight;      // Accumulated weight
        logic [7:0]                   count;       // Number of coalesced updates
        logic [$clog2(TIMEOUT_CYCLES)-1:0] age;    // Cycles since first update
    } buffer_entry_t;

    //=========================================================================
    // Buffer Storage
    //=========================================================================

    buffer_entry_t buffer [BUFFER_DEPTH];

    // Buffer management
    logic [$clog2(BUFFER_DEPTH)-1:0] head_ptr;    // Oldest entry
    logic [$clog2(BUFFER_DEPTH)-1:0] tail_ptr;    // Next free slot
    logic [$clog2(BUFFER_DEPTH):0]   count;       // Current occupancy

    // CAM for block_id lookup
    logic [BUFFER_DEPTH-1:0] cam_match;
    logic [$clog2(BUFFER_DEPTH)-1:0] cam_match_idx;
    logic cam_hit;

    //=========================================================================
    // CAM Lookup Logic
    //=========================================================================

    // Parallel comparison for all buffer entries
    always_comb begin
        cam_match = '0;
        cam_hit = 1'b0;
        cam_match_idx = '0;

        for (int i = 0; i < BUFFER_DEPTH; i++) begin
            if (buffer[i].valid &&
                buffer[i].block_id == in_block_id &&
                buffer[i].seq_id == in_seq_id) begin
                cam_match[i] = 1'b1;
            end
        end

        // Priority encoder to find first match
        for (int i = 0; i < BUFFER_DEPTH; i++) begin
            if (cam_match[i] && !cam_hit) begin
                cam_match_idx = i[$clog2(BUFFER_DEPTH)-1:0];
                cam_hit = 1'b1;
            end
        end
    end

    //=========================================================================
    // Age Tracking and Timeout Detection
    //=========================================================================

    logic [BUFFER_DEPTH-1:0] timeout_pending;
    logic [$clog2(BUFFER_DEPTH)-1:0] oldest_idx;
    logic has_timeout;

    always_comb begin
        timeout_pending = '0;
        has_timeout = 1'b0;
        oldest_idx = head_ptr;

        for (int i = 0; i < BUFFER_DEPTH; i++) begin
            if (buffer[i].valid && buffer[i].age >= TIMEOUT_CYCLES - 1) begin
                timeout_pending[i] = 1'b1;
                has_timeout = 1'b1;
            end
        end
    end

    //=========================================================================
    // State Machine
    //=========================================================================

    typedef enum logic [2:0] {
        IDLE,
        INSERT,
        COALESCE,
        FLUSH_ENTRY,
        FLUSH_ALL,
        OUTPUT
    } state_t;

    state_t state, next_state;

    // Entry being output
    buffer_entry_t output_entry;
    logic [$clog2(BUFFER_DEPTH)-1:0] flush_idx;

    //=========================================================================
    // State Register
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end

    //=========================================================================
    // Next State Logic
    //=========================================================================

    always_comb begin
        next_state = state;

        case (state)
            IDLE: begin
                if (flush_req) begin
                    next_state = FLUSH_ALL;
                end else if (has_timeout || count >= BUFFER_DEPTH - 1) begin
                    next_state = FLUSH_ENTRY;
                end else if (in_valid && in_ready) begin
                    if (cam_hit) begin
                        next_state = COALESCE;
                    end else begin
                        next_state = INSERT;
                    end
                end
            end

            INSERT: begin
                next_state = IDLE;
            end

            COALESCE: begin
                next_state = IDLE;
            end

            FLUSH_ENTRY: begin
                next_state = OUTPUT;
            end

            FLUSH_ALL: begin
                if (count == 0) begin
                    next_state = IDLE;
                end else begin
                    next_state = OUTPUT;
                end
            end

            OUTPUT: begin
                if (out_ready) begin
                    if (state == FLUSH_ALL && count > 1) begin
                        next_state = FLUSH_ALL;
                    end else begin
                        next_state = IDLE;
                    end
                end
            end

            default: next_state = IDLE;
        endcase
    end

    //=========================================================================
    // Buffer Operations
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all buffer entries
            for (int i = 0; i < BUFFER_DEPTH; i++) begin
                buffer[i] <= '0;
            end
            head_ptr <= '0;
            tail_ptr <= '0;
            count <= '0;
            coalesce_count <= '0;
            total_updates <= '0;
            output_entry <= '0;
            flush_idx <= '0;
            flush_done <= 1'b0;
        end else begin
            flush_done <= 1'b0;

            // Age all valid entries
            for (int i = 0; i < BUFFER_DEPTH; i++) begin
                if (buffer[i].valid && buffer[i].age < TIMEOUT_CYCLES - 1) begin
                    buffer[i].age <= buffer[i].age + 1;
                end
            end

            case (state)
                INSERT: begin
                    // Insert new entry at tail
                    buffer[tail_ptr].valid <= 1'b1;
                    buffer[tail_ptr].block_id <= in_block_id;
                    buffer[tail_ptr].seq_id <= in_seq_id;
                    buffer[tail_ptr].weight <= in_weight;
                    buffer[tail_ptr].count <= 8'd1;
                    buffer[tail_ptr].age <= '0;

                    tail_ptr <= tail_ptr + 1;
                    count <= count + 1;
                    total_updates <= total_updates + 1;
                end

                COALESCE: begin
                    // Add weight to existing entry
                    buffer[cam_match_idx].weight <=
                        score_sat_add(buffer[cam_match_idx].weight, in_weight);
                    buffer[cam_match_idx].count <= buffer[cam_match_idx].count + 1;

                    coalesce_count <= coalesce_count + 1;
                    total_updates <= total_updates + 1;
                end

                FLUSH_ENTRY: begin
                    // Prepare oldest entry for output
                    output_entry <= buffer[head_ptr];
                    flush_idx <= head_ptr;
                end

                FLUSH_ALL: begin
                    // Prepare next entry for output
                    output_entry <= buffer[head_ptr];
                    flush_idx <= head_ptr;
                end

                OUTPUT: begin
                    if (out_ready) begin
                        // Invalidate flushed entry
                        buffer[flush_idx].valid <= 1'b0;
                        head_ptr <= head_ptr + 1;
                        count <= count - 1;

                        if (flush_req && count == 1) begin
                            flush_done <= 1'b1;
                        end
                    end
                end

                default: ;
            endcase
        end
    end

    //=========================================================================
    // Output Interface
    //=========================================================================

    assign in_ready = (state == IDLE) && !flush_req &&
                      (count < BUFFER_DEPTH - 1) && !has_timeout;

    assign out_valid = (state == OUTPUT);
    assign out_block_id = output_entry.block_id;
    assign out_weight = output_entry.weight;
    assign out_seq_id = output_entry.seq_id;
    assign out_bank_id = get_bank_id(output_entry.block_id);

    assign buffer_occupancy = count;

    //=========================================================================
    // Assertions
    //=========================================================================

`ifdef SIMULATION
    // Check buffer overflow
    always @(posedge clk) begin
        if (count > BUFFER_DEPTH)
            $error("update_coalescer: Buffer overflow!");
    end

    // Check coalescing effectiveness
    always @(posedge clk) begin
        if (total_updates > 0 && total_updates % 1000 == 0) begin
            $display("update_coalescer: Coalesce rate = %0d%%",
                     (coalesce_count * 100) / total_updates);
        end
    end
`endif

endmodule : update_coalescer


//-----------------------------------------------------------------------------
// Per-Bank Update Queue
//-----------------------------------------------------------------------------
// FIFO queue for updates targeting a specific bank.
// Enables parallel updates to different banks.
//-----------------------------------------------------------------------------

module bank_update_queue
    import pcam_pkg::*;
#(
    parameter int QUEUE_DEPTH = 8,
    parameter int BANK_ID_PARAM = 0
) (
    input  logic                              clk,
    input  logic                              rst_n,

    // Input
    input  logic [BLOCK_ID_WIDTH-1:0]         in_block_id,
    input  logic [SCORE_WIDTH-1:0]            in_weight,
    input  logic [SEQ_ID_WIDTH-1:0]           in_seq_id,
    input  logic                              in_valid,
    output logic                              in_ready,

    // Output (to bank)
    output logic [BLOCK_ID_WIDTH-1:0]         out_block_id,
    output logic [SCORE_WIDTH-1:0]            out_weight,
    output logic [SEQ_ID_WIDTH-1:0]           out_seq_id,
    output logic                              out_valid,
    input  logic                              out_ready,

    // Status
    output logic                              empty,
    output logic                              full
);

    // Simple FIFO implementation
    typedef struct packed {
        logic [BLOCK_ID_WIDTH-1:0] block_id;
        logic [SCORE_WIDTH-1:0]    weight;
        logic [SEQ_ID_WIDTH-1:0]   seq_id;
    } queue_entry_t;

    queue_entry_t fifo [QUEUE_DEPTH];
    logic [$clog2(QUEUE_DEPTH)-1:0] rd_ptr;
    logic [$clog2(QUEUE_DEPTH)-1:0] wr_ptr;
    logic [$clog2(QUEUE_DEPTH):0]   count;

    assign empty = (count == 0);
    assign full = (count == QUEUE_DEPTH);
    assign in_ready = !full;

    // Write logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
        end else if (in_valid && in_ready) begin
            fifo[wr_ptr].block_id <= in_block_id;
            fifo[wr_ptr].weight <= in_weight;
            fifo[wr_ptr].seq_id <= in_seq_id;
            wr_ptr <= wr_ptr + 1;
        end
    end

    // Read logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr <= '0;
        end else if (out_valid && out_ready) begin
            rd_ptr <= rd_ptr + 1;
        end
    end

    // Count logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= '0;
        end else begin
            case ({in_valid && in_ready, out_valid && out_ready})
                2'b10: count <= count + 1;
                2'b01: count <= count - 1;
                default: ; // No change
            endcase
        end
    end

    // Output
    assign out_valid = !empty;
    assign out_block_id = fifo[rd_ptr].block_id;
    assign out_weight = fifo[rd_ptr].weight;
    assign out_seq_id = fifo[rd_ptr].seq_id;

endmodule : bank_update_queue
