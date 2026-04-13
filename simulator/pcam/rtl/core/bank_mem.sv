//-----------------------------------------------------------------------------
// PCAM Bank Memory Module
//-----------------------------------------------------------------------------
// Single memory bank for storing block entries. Each PCAM instance has 64
// parallel banks to enable single-cycle parallel lookup for Top-K selection.
//
// Implementation: Infers BRAM36K on Xilinx or M20K on Intel
// Capacity: 16K entries x 64 bits = 1 Mbit per bank
//-----------------------------------------------------------------------------

module bank_mem
    import pcam_pkg::*;
#(
    parameter int BANK_ID = 0,
    parameter int DEPTH = BANK_DEPTH,      // 16384 entries
    parameter int WIDTH = ENTRY_WIDTH      // 64 bits
) (
    input  logic                          clk,
    input  logic                          rst_n,

    //-------------------------------------------------------------------------
    // Read Port (for ATTEND)
    //-------------------------------------------------------------------------
    input  logic [BANK_ADDR_WIDTH-1:0]    rd_addr,
    input  logic                          rd_en,
    output logic [WIDTH-1:0]              rd_data,
    output logic                          rd_valid,

    //-------------------------------------------------------------------------
    // Write Port (for UPDATE)
    //-------------------------------------------------------------------------
    input  logic [BANK_ADDR_WIDTH-1:0]    wr_addr,
    input  logic [WIDTH-1:0]              wr_data,
    input  logic                          wr_en,

    //-------------------------------------------------------------------------
    // Read-Modify-Write Port (for score updates)
    //-------------------------------------------------------------------------
    input  logic [BANK_ADDR_WIDTH-1:0]    rmw_addr,
    input  logic                          rmw_en,
    input  logic [SCORE_WIDTH-1:0]        rmw_new_weight,
    output logic                          rmw_done,

    //-------------------------------------------------------------------------
    // Status
    //-------------------------------------------------------------------------
    output logic                          busy,
    output logic [31:0]                   access_count
);

    //-------------------------------------------------------------------------
    // Memory Array (infers BRAM)
    //-------------------------------------------------------------------------
    (* ram_style = "block" *)
    logic [WIDTH-1:0] mem [DEPTH];

    // Initialize to zero
    initial begin
        for (int i = 0; i < DEPTH; i++) begin
            mem[i] = '0;
        end
    end

    //-------------------------------------------------------------------------
    // Read Path (registered output for BRAM timing)
    //-------------------------------------------------------------------------
    logic [WIDTH-1:0] rd_data_reg;
    logic             rd_valid_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_data_reg  <= '0;
            rd_valid_reg <= 1'b0;
        end else begin
            rd_valid_reg <= rd_en && !busy;
            if (rd_en && !busy) begin
                rd_data_reg <= mem[rd_addr];
            end
        end
    end

    assign rd_data  = rd_data_reg;
    assign rd_valid = rd_valid_reg;

    //-------------------------------------------------------------------------
    // Write Path
    //-------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (wr_en && !busy) begin
            mem[wr_addr] <= wr_data;
        end
    end

    //-------------------------------------------------------------------------
    // Read-Modify-Write State Machine
    //-------------------------------------------------------------------------
    typedef enum logic [2:0] {
        RMW_IDLE,
        RMW_READ,
        RMW_WAIT,
        RMW_COMPUTE,
        RMW_WRITE
    } rmw_state_t;

    rmw_state_t rmw_state;
    logic [BANK_ADDR_WIDTH-1:0] rmw_addr_reg;
    logic [SCORE_WIDTH-1:0]     rmw_weight_reg;
    logic [WIDTH-1:0]           rmw_read_data;
    block_entry_t               rmw_entry;
    logic [SCORE_WIDTH-1:0]     rmw_new_score;

    // Score update calculation
    logic [31:0] term1, term2, sum;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rmw_state      <= RMW_IDLE;
            rmw_addr_reg   <= '0;
            rmw_weight_reg <= '0;
            rmw_read_data  <= '0;
            rmw_done       <= 1'b0;
            busy           <= 1'b0;
        end else begin
            rmw_done <= 1'b0;

            case (rmw_state)
                RMW_IDLE: begin
                    busy <= 1'b0;
                    if (rmw_en) begin
                        rmw_addr_reg   <= rmw_addr;
                        rmw_weight_reg <= rmw_new_weight;
                        rmw_state      <= RMW_READ;
                        busy           <= 1'b1;
                    end
                end

                RMW_READ: begin
                    // Read from BRAM
                    rmw_read_data <= mem[rmw_addr_reg];
                    rmw_state     <= RMW_WAIT;
                end

                RMW_WAIT: begin
                    // Wait for BRAM read latency
                    rmw_entry <= rmw_read_data;
                    rmw_state <= RMW_COMPUTE;
                end

                RMW_COMPUTE: begin
                    // Calculate new score: alpha * weight + (1-alpha) * old
                    term1 = rmw_weight_reg * ALPHA;
                    term2 = rmw_entry.score * ONE_MINUS_ALPHA;
                    sum   = term1 + term2;
                    rmw_new_score <= (sum + 128) >> 8;  // Round to Q8.8

                    rmw_state <= RMW_WRITE;
                end

                RMW_WRITE: begin
                    // Write back updated entry. The legacy access_count
                    // field was removed per ADR-0001; frequency tracking
                    // now lives in the global CTM+ sketch (freq_sketch.sv
                    // instanced at the pcam_top level). reserved2 is
                    // written back unchanged.
                    mem[rmw_addr_reg] <= {
                        rmw_new_score,                           // score
                        rmw_entry.reserved2,                     // reserved2 (formerly access_count)
                        rmw_entry.last_step,                     // last_step (updated externally)
                        rmw_entry.reserved
                    };

                    rmw_done  <= 1'b1;
                    rmw_state <= RMW_IDLE;
                end

                default: begin
                    rmw_state <= RMW_IDLE;
                end
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // Access Counter (for performance monitoring)
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            access_count <= '0;
        end else begin
            if (rd_en || wr_en || rmw_en) begin
                access_count <= access_count + 1;
            end
        end
    end

    //-------------------------------------------------------------------------
    // Assertions
    //-------------------------------------------------------------------------
`ifdef SIMULATION
    // Check for address overflow
    always @(posedge clk) begin
        if (rd_en && rd_addr >= DEPTH)
            $error("bank_mem[%0d]: Read address overflow: %0d", BANK_ID, rd_addr);
        if (wr_en && wr_addr >= DEPTH)
            $error("bank_mem[%0d]: Write address overflow: %0d", BANK_ID, wr_addr);
        if (rmw_en && rmw_addr >= DEPTH)
            $error("bank_mem[%0d]: RMW address overflow: %0d", BANK_ID, rmw_addr);
    end

    // Warn on simultaneous operations
    always @(posedge clk) begin
        if (rd_en && wr_en && rd_addr == wr_addr)
            $warning("bank_mem[%0d]: Simultaneous read/write to same address", BANK_ID);
    end
`endif

endmodule : bank_mem


//-----------------------------------------------------------------------------
// Bank Array - 64 Parallel Banks
//-----------------------------------------------------------------------------
// Instantiates 64 bank_mem modules with routing logic for parallel access.
//-----------------------------------------------------------------------------

module bank_array
    import pcam_pkg::*;
#(
    parameter int NUM_BANKS_PARAM = NUM_BANKS
) (
    input  logic                          clk,
    input  logic                          rst_n,

    //-------------------------------------------------------------------------
    // Parallel Read Interface (for ATTEND)
    //-------------------------------------------------------------------------
    input  logic [BLOCK_ID_WIDTH-1:0]     rd_block_ids [NUM_BANKS_PARAM],
    input  logic [NUM_BANKS_PARAM-1:0]    rd_en,
    output block_entry_t                  rd_entries [NUM_BANKS_PARAM],
    output logic [NUM_BANKS_PARAM-1:0]    rd_valid,

    //-------------------------------------------------------------------------
    // Single Write Interface (for UPDATE)
    //-------------------------------------------------------------------------
    input  logic [BLOCK_ID_WIDTH-1:0]     wr_block_id,
    input  logic [SCORE_WIDTH-1:0]        wr_weight,
    input  logic                          wr_en,
    output logic                          wr_done,

    //-------------------------------------------------------------------------
    // Status
    //-------------------------------------------------------------------------
    output logic [NUM_BANKS_PARAM-1:0]    bank_busy
);

    // Bank interfaces
    logic [BANK_ADDR_WIDTH-1:0] bank_rd_addr [NUM_BANKS_PARAM];
    logic [ENTRY_WIDTH-1:0]     bank_rd_data [NUM_BANKS_PARAM];
    logic [NUM_BANKS_PARAM-1:0] bank_rd_valid;

    // Route read requests to banks
    generate
        for (genvar i = 0; i < NUM_BANKS_PARAM; i++) begin : gen_banks
            // Calculate bank address from block ID
            assign bank_rd_addr[i] = get_bank_addr(rd_block_ids[i]);

            bank_mem #(
                .BANK_ID(i)
            ) u_bank (
                .clk(clk),
                .rst_n(rst_n),

                // Read port
                .rd_addr(bank_rd_addr[i]),
                .rd_en(rd_en[i]),
                .rd_data(bank_rd_data[i]),
                .rd_valid(bank_rd_valid[i]),

                // Write port (directly connected for simplicity)
                .wr_addr('0),
                .wr_data('0),
                .wr_en(1'b0),

                // RMW port
                .rmw_addr(get_bank_addr(wr_block_id)),
                .rmw_en(wr_en && (get_bank_id(wr_block_id) == i)),
                .rmw_new_weight(wr_weight),
                .rmw_done(),

                // Status
                .busy(bank_busy[i]),
                .access_count()
            );

            // Convert raw data to struct
            assign rd_entries[i] = block_entry_t'(bank_rd_data[i]);
        end
    endgenerate

    assign rd_valid = bank_rd_valid;

    // Write done when target bank completes
    assign wr_done = !bank_busy[get_bank_id(wr_block_id)];

endmodule : bank_array
