//-----------------------------------------------------------------------------
// Decay Engine
//-----------------------------------------------------------------------------
// Applies exponential decay to all block scores in background.
// Runs during idle cycles without interfering with ATTEND/UPDATE operations.
//
// Operation:
//   - Triggered every N steps (configurable, default 100)
//   - Sweeps through all banks sequentially
//   - Applies decay: new_score = old_score × decay_rate
//   - Uses fixed-point Q8.8 arithmetic
//
// Performance:
//   - Sweep time: 1M entries / 83M entries/sec = 12ms
//   - Can be paused/resumed for priority operations
//-----------------------------------------------------------------------------

module decay_engine
    import pcam_pkg::*;
#(
    parameter int NUM_BANKS_PARAM = NUM_BANKS,
    parameter int BANK_DEPTH_PARAM = BANK_DEPTH,
    parameter int DECAY_INTERVAL = 100,           // Steps between decay sweeps
    parameter logic [SCORE_WIDTH-1:0] DECAY_RATE_PARAM = DECAY_RATE  // 0.99
) (
    input  logic                              clk,
    input  logic                              rst_n,

    //-------------------------------------------------------------------------
    // Control Interface
    //-------------------------------------------------------------------------
    input  logic                              enable,           // Global enable
    input  logic                              trigger,          // Start decay sweep
    input  logic                              pause,            // Pause for priority op
    output logic                              busy,             // Sweep in progress
    output logic                              done,             // Sweep completed

    //-------------------------------------------------------------------------
    // Configuration (runtime adjustable)
    //-------------------------------------------------------------------------
    input  logic [SCORE_WIDTH-1:0]            decay_rate,       // Override default
    input  logic                              use_custom_rate,

    //-------------------------------------------------------------------------
    // Bank Interface (directly to BRAM)
    //-------------------------------------------------------------------------
    output logic [BANK_ID_WIDTH-1:0]          bank_id,
    output logic [BANK_ADDR_WIDTH-1:0]        bank_addr,
    output logic                              bank_rd_en,
    input  logic [ENTRY_WIDTH-1:0]            bank_rd_data,
    input  logic                              bank_rd_valid,
    output logic [ENTRY_WIDTH-1:0]            bank_wr_data,
    output logic                              bank_wr_en,

    //-------------------------------------------------------------------------
    // Status
    //-------------------------------------------------------------------------
    output logic [31:0]                       entries_processed,
    output logic [31:0]                       sweep_count,
    output logic [15:0]                       current_progress   // 0-65535
);

    //=========================================================================
    // Effective Decay Rate
    //=========================================================================

    logic [SCORE_WIDTH-1:0] effective_rate;
    assign effective_rate = use_custom_rate ? decay_rate : DECAY_RATE_PARAM;

    //=========================================================================
    // State Machine
    //=========================================================================

    typedef enum logic [2:0] {
        IDLE,
        START_SWEEP,
        READ_ENTRY,
        WAIT_READ,
        COMPUTE_DECAY,
        WRITE_ENTRY,
        NEXT_ENTRY,
        SWEEP_DONE
    } state_t;

    state_t state, next_state;

    //=========================================================================
    // Sweep Counters
    //=========================================================================

    logic [BANK_ID_WIDTH-1:0]   current_bank;
    logic [BANK_ADDR_WIDTH-1:0] current_addr;
    logic                       last_entry;
    logic                       last_bank;

    assign last_entry = (current_addr == BANK_DEPTH_PARAM - 1);
    assign last_bank = (current_bank == NUM_BANKS_PARAM - 1);

    //=========================================================================
    // Read Data and Computed Value
    //=========================================================================

    block_entry_t read_entry;
    logic [SCORE_WIDTH-1:0] decayed_score;
    block_entry_t write_entry;

    // Parse read data
    assign read_entry = block_entry_t'(bank_rd_data);

    // Q8.8 decay computation
    logic [31:0] decay_product;
    assign decay_product = read_entry.score * effective_rate;
    assign decayed_score = (decay_product + 32'd128) >> 8;  // Round

    // Prepare write entry
    always_comb begin
        write_entry = read_entry;
        write_entry.score = decayed_score;
    end

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
                if (enable && trigger) begin
                    next_state = START_SWEEP;
                end
            end

            START_SWEEP: begin
                next_state = READ_ENTRY;
            end

            READ_ENTRY: begin
                if (pause) begin
                    next_state = READ_ENTRY;  // Stay paused
                end else begin
                    next_state = WAIT_READ;
                end
            end

            WAIT_READ: begin
                if (bank_rd_valid) begin
                    next_state = COMPUTE_DECAY;
                end
            end

            COMPUTE_DECAY: begin
                next_state = WRITE_ENTRY;
            end

            WRITE_ENTRY: begin
                next_state = NEXT_ENTRY;
            end

            NEXT_ENTRY: begin
                if (last_entry && last_bank) begin
                    next_state = SWEEP_DONE;
                end else begin
                    next_state = READ_ENTRY;
                end
            end

            SWEEP_DONE: begin
                next_state = IDLE;
            end

            default: next_state = IDLE;
        endcase
    end

    //=========================================================================
    // Counter Logic
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_bank <= '0;
            current_addr <= '0;
            entries_processed <= '0;
            sweep_count <= '0;
        end else begin
            case (state)
                START_SWEEP: begin
                    current_bank <= '0;
                    current_addr <= '0;
                    entries_processed <= '0;
                end

                NEXT_ENTRY: begin
                    entries_processed <= entries_processed + 1;

                    if (last_entry) begin
                        current_addr <= '0;
                        current_bank <= current_bank + 1;
                    end else begin
                        current_addr <= current_addr + 1;
                    end
                end

                SWEEP_DONE: begin
                    sweep_count <= sweep_count + 1;
                end

                default: ;
            endcase
        end
    end

    //=========================================================================
    // Output Assignments
    //=========================================================================

    assign bank_id = current_bank;
    assign bank_addr = current_addr;
    assign bank_rd_en = (state == READ_ENTRY) && !pause;
    assign bank_wr_data = write_entry;
    assign bank_wr_en = (state == WRITE_ENTRY);

    assign busy = (state != IDLE);
    assign done = (state == SWEEP_DONE);

    // Progress: (entries_processed / total_entries) * 65536
    logic [47:0] progress_calc;
    assign progress_calc = (entries_processed << 16) /
                           (NUM_BANKS_PARAM * BANK_DEPTH_PARAM);
    assign current_progress = progress_calc[15:0];

    //=========================================================================
    // Assertions
    //=========================================================================

`ifdef SIMULATION
    // Monitor sweep timing
    int sweep_start_cycle;
    int sweep_end_cycle;

    always @(posedge clk) begin
        if (state == START_SWEEP)
            sweep_start_cycle = $time;
        if (state == SWEEP_DONE) begin
            sweep_end_cycle = $time;
            $display("decay_engine: Sweep completed in %0d cycles",
                     sweep_end_cycle - sweep_start_cycle);
        end
    end
`endif

endmodule : decay_engine


//-----------------------------------------------------------------------------
// Decay Scheduler
//-----------------------------------------------------------------------------
// Triggers decay engine based on step count or idle detection.
//-----------------------------------------------------------------------------

module decay_scheduler
    import pcam_pkg::*;
#(
    parameter int STEP_INTERVAL = 100,
    parameter int IDLE_THRESHOLD = 1000  // Cycles of idle before opportunistic decay
) (
    input  logic                              clk,
    input  logic                              rst_n,

    // Step counter (from command processor)
    input  logic                              step_increment,
    input  logic [31:0]                       current_step,

    // Activity monitoring
    input  logic                              system_busy,

    // Decay engine control
    output logic                              decay_trigger,
    input  logic                              decay_busy,
    input  logic                              decay_done,

    // Configuration
    input  logic                              enable,
    input  logic [15:0]                       interval_override,
    input  logic                              use_override
);

    //=========================================================================
    // Step-Based Triggering
    //=========================================================================

    logic [15:0] effective_interval;
    assign effective_interval = use_override ? interval_override : STEP_INTERVAL[15:0];

    logic [31:0] last_decay_step;
    logic step_trigger;

    assign step_trigger = enable &&
                          !decay_busy &&
                          (current_step - last_decay_step >= effective_interval);

    //=========================================================================
    // Idle-Based Triggering
    //=========================================================================

    logic [15:0] idle_counter;
    logic idle_trigger;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            idle_counter <= '0;
        end else begin
            if (system_busy) begin
                idle_counter <= '0;
            end else if (idle_counter < IDLE_THRESHOLD) begin
                idle_counter <= idle_counter + 1;
            end
        end
    end

    assign idle_trigger = enable &&
                          !decay_busy &&
                          (idle_counter >= IDLE_THRESHOLD) &&
                          (current_step - last_decay_step >= effective_interval / 2);

    //=========================================================================
    // Trigger Output
    //=========================================================================

    assign decay_trigger = step_trigger || idle_trigger;

    //=========================================================================
    // Track Last Decay
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            last_decay_step <= '0;
        end else if (decay_done) begin
            last_decay_step <= current_step;
        end
    end

endmodule : decay_scheduler


//-----------------------------------------------------------------------------
// Section Decay Engine
//-----------------------------------------------------------------------------
// Applies decay to section-level statistics for hierarchical prior.
// Lighter weight than block decay (only 4096 sections vs 1M blocks).
//-----------------------------------------------------------------------------

module section_decay_engine
    import pcam_pkg::*;
#(
    parameter int NUM_SECTIONS_PARAM = NUM_SECTIONS,
    parameter logic [SCORE_WIDTH-1:0] SECTION_DECAY_RATE = 16'h00F0  // 0.94
) (
    input  logic                              clk,
    input  logic                              rst_n,

    // Control
    input  logic                              trigger,
    output logic                              busy,
    output logic                              done,

    // Section memory interface
    output logic [SECTION_ID_WIDTH-1:0]       section_addr,
    output logic                              section_rd_en,
    input  section_entry_t                    section_rd_data,
    input  logic                              section_rd_valid,
    output section_entry_t                    section_wr_data,
    output logic                              section_wr_en
);

    // State machine
    typedef enum logic [1:0] {
        IDLE,
        READ,
        COMPUTE,
        WRITE
    } state_t;

    state_t state;
    logic [SECTION_ID_WIDTH-1:0] current_section;

    // Decayed values
    logic [23:0] decayed_attention;
    logic [31:0] decay_product;

    assign decay_product = section_rd_data.total_attention * SECTION_DECAY_RATE;
    assign decayed_attention = (decay_product + 24'd128) >> 8;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_section <= '0;
            busy <= 1'b0;
            done <= 1'b0;
        end else begin
            done <= 1'b0;

            case (state)
                IDLE: begin
                    busy <= 1'b0;
                    if (trigger) begin
                        state <= READ;
                        current_section <= '0;
                        busy <= 1'b1;
                    end
                end

                READ: begin
                    if (section_rd_valid) begin
                        state <= COMPUTE;
                    end
                end

                COMPUTE: begin
                    state <= WRITE;
                end

                WRITE: begin
                    if (current_section == NUM_SECTIONS_PARAM - 1) begin
                        state <= IDLE;
                        done <= 1'b1;
                    end else begin
                        current_section <= current_section + 1;
                        state <= READ;
                    end
                end
            endcase
        end
    end

    // Output assignments
    assign section_addr = current_section;
    assign section_rd_en = (state == READ);
    assign section_wr_en = (state == WRITE);

    always_comb begin
        section_wr_data = section_rd_data;
        section_wr_data.total_attention = decayed_attention;
        // Access count and unique queries decay slower or not at all
    end

endmodule : section_decay_engine
