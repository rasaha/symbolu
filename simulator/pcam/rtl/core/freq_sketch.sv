//-----------------------------------------------------------------------------
// CTM+ Frequency Sketch (4-row, 4-bit Count-Min)
//-----------------------------------------------------------------------------
// RTL port of the canonical Python implementation at
//   CTM_plus/KVPolicy/kv_policy/attention_evictor.py:69-112
// per ADR-0001. Observationally equivalent to the Python reference and
// to simulator/pcam/kv_policy.py::FrequencySketch on identical traces.
//
// Structure:
//   - 4 rows, each FREQ_SKETCH_WIDTH entries deep, 4 bits per counter.
//   - Four fixed seed hashes (FREQ_SKETCH_SEED_0..3 from pcam_pkg).
//   - Counters saturate at 15.
//   - Size counter triggers halving when >= capacity * FREQ_SKETCH_RESET_MULT.
//   - Halving walks all FREQ_SKETCH_WIDTH indices, right-shifting every
//     counter in every row by one bit, then halves the size counter.
//
// Increment ordering matches the reference exactly:
//
//     self.size += 1
//     if self.size >= self.reset_threshold:
//         self._halve()
//     # then increment 4 counters and return min
//
// That means an increment arriving on the threshold-crossing cycle:
//   1. bumps size to the threshold
//   2. walks the halving FSM
//   3. once halving completes, bumps the 4 counters for the buffered key
//
// Upstream must stall while state != IDLE (exposed via `busy`). The
// happy path is a 1-cycle increment; halving is `FREQ_SKETCH_WIDTH + 2`
// cycles once every `capacity * RESET_MULT / 2` events on average.
//
// Estimate is a combinational read (4 parallel lookups) followed by a
// single registered min reduction, for 1-cycle latency.
//-----------------------------------------------------------------------------

module freq_sketch
    import pcam_pkg::*;
#(
    parameter int WIDTH         = FREQ_SKETCH_WIDTH,
    parameter int INDEX_WIDTH   = FREQ_SKETCH_INDEX_WIDTH,
    parameter int COUNTER_BITS  = FREQ_SKETCH_COUNTER_BITS,
    parameter int CAPACITY      = 256,
    parameter int RESET_THRESHOLD = CAPACITY * FREQ_SKETCH_RESET_MULT
) (
    input  logic                           clk,
    input  logic                           rst_n,

    // Increment request. Upstream must hold inc_valid high until busy
    // deasserts. `inc_key` is the block_id to bump.
    input  logic                           inc_valid,
    input  logic [BLOCK_ID_WIDTH-1:0]      inc_key,
    output logic                           inc_done,         // 1-cycle pulse when increment commits
    output logic [COUNTER_BITS-1:0]        inc_min_count,    // the min across rows after the bump

    // Estimate request (combinational lookup + registered output).
    input  logic                           est_valid,
    input  logic [BLOCK_ID_WIDTH-1:0]      est_key,
    output logic                           est_done,
    output logic [COUNTER_BITS-1:0]        est_value,

    // Flow control. busy is high while the halving FSM is running or
    // the deferred increment is committing.
    output logic                           busy,

    // Observability.
    output logic [31:0]                    size_count
);

    //-------------------------------------------------------------------------
    // Sketch storage — four independent 4-bit-wide register arrays.
    //-------------------------------------------------------------------------
    logic [COUNTER_BITS-1:0] table_0 [WIDTH];
    logic [COUNTER_BITS-1:0] table_1 [WIDTH];
    logic [COUNTER_BITS-1:0] table_2 [WIDTH];
    logic [COUNTER_BITS-1:0] table_3 [WIDTH];

    //-------------------------------------------------------------------------
    // State machine
    //-------------------------------------------------------------------------
    typedef enum logic [1:0] {
        S_IDLE,
        S_HALVE,
        S_POST_HALVE_BUMP
    } sketch_state_t;

    sketch_state_t state, next_state;

    logic [31:0] size_counter;
    logic [INDEX_WIDTH-1:0] halve_idx;
    logic                   halve_wrap;

    // Last-index comparison value for the halving walk. Computed once
    // and cast to the correct width so there's no implicit truncation
    // warning on the state transition compare.
    localparam logic [INDEX_WIDTH-1:0] HALVE_LAST_IDX =
        INDEX_WIDTH'(WIDTH - 1);

    // Deferred increment key — captured when halving is triggered on
    // an increment cycle, replayed in S_POST_HALVE_BUMP.
    logic [BLOCK_ID_WIDTH-1:0] deferred_key;

    // Deferred-path scratch signals used in S_POST_HALVE_BUMP. Hoisted
    // to the module scope to avoid named-block declaration issues in
    // strict SV parsers.
    logic [INDEX_WIDTH-1:0]    d_idx0, d_idx1, d_idx2, d_idx3;
    logic [COUNTER_BITS-1:0]   d_r0, d_r1, d_r2, d_r3;
    logic [COUNTER_BITS-1:0]   d_b0, d_b1, d_b2, d_b3;

    //-------------------------------------------------------------------------
    // Hash computation — shared between increment and estimate paths.
    //-------------------------------------------------------------------------
    function automatic logic [INDEX_WIDTH-1:0] idx_for(
        input logic [BLOCK_ID_WIDTH-1:0] key,
        input logic [1:0]                row
    );
        logic [FREQ_SKETCH_KEY_WIDTH-1:0] h;
        h = sketch_hash(key, row);
        return h[INDEX_WIDTH-1:0];
    endfunction

    //-------------------------------------------------------------------------
    // Trigger detection
    //-------------------------------------------------------------------------
    // The reference bumps size BEFORE checking the threshold, so the
    // crossing condition is (size_counter + 1) >= RESET_THRESHOLD.
    wire threshold_crossing = (state == S_IDLE)
                           && inc_valid
                           && ((size_counter + 32'd1) >= RESET_THRESHOLD);

    //-------------------------------------------------------------------------
    // Counter row readers (combinational)
    //-------------------------------------------------------------------------
    logic [INDEX_WIDTH-1:0] bump_idx_0, bump_idx_1, bump_idx_2, bump_idx_3;
    logic [COUNTER_BITS-1:0] read_0, read_1, read_2, read_3;
    logic [COUNTER_BITS-1:0] bumped_0, bumped_1, bumped_2, bumped_3;

    always_comb begin
        // Default: idle reads against inc_key so the happy-path
        // increment has its indices ready when inc_valid pulses.
        bump_idx_0 = idx_for(inc_key, 2'd0);
        bump_idx_1 = idx_for(inc_key, 2'd1);
        bump_idx_2 = idx_for(inc_key, 2'd2);
        bump_idx_3 = idx_for(inc_key, 2'd3);
    end

    assign read_0 = table_0[bump_idx_0];
    assign read_1 = table_1[bump_idx_1];
    assign read_2 = table_2[bump_idx_2];
    assign read_3 = table_3[bump_idx_3];

    // Saturating increment.
    assign bumped_0 = (read_0 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                        ? read_0 : read_0 + 1;
    assign bumped_1 = (read_1 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                        ? read_1 : read_1 + 1;
    assign bumped_2 = (read_2 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                        ? read_2 : read_2 + 1;
    assign bumped_3 = (read_3 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                        ? read_3 : read_3 + 1;

    //-------------------------------------------------------------------------
    // Min-of-four reduction helper
    //-------------------------------------------------------------------------
    function automatic logic [COUNTER_BITS-1:0] min4(
        input logic [COUNTER_BITS-1:0] a,
        input logic [COUNTER_BITS-1:0] b,
        input logic [COUNTER_BITS-1:0] c,
        input logic [COUNTER_BITS-1:0] d
    );
        logic [COUNTER_BITS-1:0] ab, cd;
        ab = (a < b) ? a : b;
        cd = (c < d) ? c : d;
        return (ab < cd) ? ab : cd;
    endfunction

    //-------------------------------------------------------------------------
    // Main always_ff — state, size counter, tables, deferred key
    //-------------------------------------------------------------------------
    integer i;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            size_counter  <= 32'd0;
            halve_idx     <= '0;
            halve_wrap    <= 1'b0;
            deferred_key  <= '0;
            inc_done      <= 1'b0;
            inc_min_count <= '0;

            for (i = 0; i < WIDTH; i = i + 1) begin
                table_0[i] <= '0;
                table_1[i] <= '0;
                table_2[i] <= '0;
                table_3[i] <= '0;
            end
        end else begin
            inc_done <= 1'b0;

            unique case (state)
                //-----------------------------------------------------------
                S_IDLE: begin
                    if (inc_valid) begin
                        if (threshold_crossing) begin
                            // Bump size to the threshold, capture the
                            // key, enter halving.
                            size_counter <= size_counter + 32'd1;
                            deferred_key <= inc_key;
                            halve_idx    <= '0;
                            halve_wrap   <= 1'b0;
                            state        <= S_HALVE;
                        end else begin
                            // Happy path: one-cycle increment.
                            size_counter          <= size_counter + 32'd1;
                            table_0[bump_idx_0]   <= bumped_0;
                            table_1[bump_idx_1]   <= bumped_1;
                            table_2[bump_idx_2]   <= bumped_2;
                            table_3[bump_idx_3]   <= bumped_3;
                            inc_done              <= 1'b1;
                            inc_min_count         <= min4(bumped_0, bumped_1,
                                                          bumped_2, bumped_3);
                        end
                    end
                end

                //-----------------------------------------------------------
                S_HALVE: begin
                    // Right-shift every counter at halve_idx in all four
                    // rows. Walk until wrap-around.
                    table_0[halve_idx] <= table_0[halve_idx] >> 1;
                    table_1[halve_idx] <= table_1[halve_idx] >> 1;
                    table_2[halve_idx] <= table_2[halve_idx] >> 1;
                    table_3[halve_idx] <= table_3[halve_idx] >> 1;

                    if (halve_idx == HALVE_LAST_IDX) begin
                        halve_idx    <= '0;
                        size_counter <= size_counter >> 1;
                        state        <= S_POST_HALVE_BUMP;
                    end else begin
                        halve_idx <= halve_idx + 1'b1;
                    end
                end

                //-----------------------------------------------------------
                S_POST_HALVE_BUMP: begin
                    // Replay the deferred increment. Recompute indices
                    // from deferred_key, read, bump, writeback. Locals
                    // are declared at module scope.
                    d_idx0 = idx_for(deferred_key, 2'd0);
                    d_idx1 = idx_for(deferred_key, 2'd1);
                    d_idx2 = idx_for(deferred_key, 2'd2);
                    d_idx3 = idx_for(deferred_key, 2'd3);

                    d_r0 = table_0[d_idx0];
                    d_r1 = table_1[d_idx1];
                    d_r2 = table_2[d_idx2];
                    d_r3 = table_3[d_idx3];

                    d_b0 = (d_r0 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                            ? d_r0 : d_r0 + 1;
                    d_b1 = (d_r1 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                            ? d_r1 : d_r1 + 1;
                    d_b2 = (d_r2 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                            ? d_r2 : d_r2 + 1;
                    d_b3 = (d_r3 == FREQ_SKETCH_COUNTER_MAX[COUNTER_BITS-1:0])
                            ? d_r3 : d_r3 + 1;

                    table_0[d_idx0] <= d_b0;
                    table_1[d_idx1] <= d_b1;
                    table_2[d_idx2] <= d_b2;
                    table_3[d_idx3] <= d_b3;

                    inc_done      <= 1'b1;
                    inc_min_count <= min4(d_b0, d_b1, d_b2, d_b3);
                    state         <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // Estimate path — combinational lookup, registered output.
    //-------------------------------------------------------------------------
    logic [INDEX_WIDTH-1:0] est_idx_0, est_idx_1, est_idx_2, est_idx_3;
    logic [COUNTER_BITS-1:0] est_r0, est_r1, est_r2, est_r3;

    assign est_idx_0 = idx_for(est_key, 2'd0);
    assign est_idx_1 = idx_for(est_key, 2'd1);
    assign est_idx_2 = idx_for(est_key, 2'd2);
    assign est_idx_3 = idx_for(est_key, 2'd3);

    assign est_r0 = table_0[est_idx_0];
    assign est_r1 = table_1[est_idx_1];
    assign est_r2 = table_2[est_idx_2];
    assign est_r3 = table_3[est_idx_3];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            est_done  <= 1'b0;
            est_value <= '0;
        end else begin
            est_done  <= est_valid;
            est_value <= min4(est_r0, est_r1, est_r2, est_r3);
        end
    end

    //-------------------------------------------------------------------------
    // Outputs
    //-------------------------------------------------------------------------
    assign busy       = (state != S_IDLE);
    assign size_count = size_counter;

endmodule : freq_sketch
