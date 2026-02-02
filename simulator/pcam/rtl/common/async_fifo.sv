//-----------------------------------------------------------------------------
// Asynchronous FIFO
//-----------------------------------------------------------------------------
// Dual-clock FIFO for clock domain crossing between PCIe and user domains.
// Uses gray-code pointers for safe synchronization.
//
// Features:
//   - Parameterized width and depth
//   - Gray-code pointer synchronization
//   - Almost full/empty status
//   - Overflow/underflow protection
//-----------------------------------------------------------------------------

module async_fifo #(
    parameter int WIDTH = 64,
    parameter int DEPTH = 16,
    parameter int ALMOST_FULL_THRESH = DEPTH - 4,
    parameter int ALMOST_EMPTY_THRESH = 4
) (
    //-------------------------------------------------------------------------
    // Write Clock Domain
    //-------------------------------------------------------------------------
    input  logic                              wr_clk,
    input  logic                              wr_rst_n,
    input  logic                              wr_en,
    input  logic [WIDTH-1:0]                  wr_data,
    output logic                              wr_full,
    output logic                              wr_almost_full,
    output logic                              wr_overflow,

    //-------------------------------------------------------------------------
    // Read Clock Domain
    //-------------------------------------------------------------------------
    input  logic                              rd_clk,
    input  logic                              rd_rst_n,
    input  logic                              rd_en,
    output logic [WIDTH-1:0]                  rd_data,
    output logic                              rd_empty,
    output logic                              rd_almost_empty,
    output logic                              rd_underflow,

    //-------------------------------------------------------------------------
    // Status (in write domain)
    //-------------------------------------------------------------------------
    output logic [$clog2(DEPTH):0]            wr_count
);

    //=========================================================================
    // Local Parameters
    //=========================================================================

    localparam int ADDR_WIDTH = $clog2(DEPTH);
    localparam int PTR_WIDTH = ADDR_WIDTH + 1;  // Extra bit for wrap detection

    //=========================================================================
    // Memory
    //=========================================================================

    (* ram_style = "distributed" *)
    logic [WIDTH-1:0] mem [DEPTH];

    //=========================================================================
    // Write Domain Pointers
    //=========================================================================

    logic [PTR_WIDTH-1:0] wr_ptr_bin;       // Binary write pointer
    logic [PTR_WIDTH-1:0] wr_ptr_gray;      // Gray-code write pointer
    logic [PTR_WIDTH-1:0] rd_ptr_gray_sync; // Synchronized read pointer
    logic [PTR_WIDTH-1:0] rd_ptr_gray_meta; // Metastability register

    //=========================================================================
    // Read Domain Pointers
    //=========================================================================

    logic [PTR_WIDTH-1:0] rd_ptr_bin;       // Binary read pointer
    logic [PTR_WIDTH-1:0] rd_ptr_gray;      // Gray-code read pointer
    logic [PTR_WIDTH-1:0] wr_ptr_gray_sync; // Synchronized write pointer
    logic [PTR_WIDTH-1:0] wr_ptr_gray_meta; // Metastability register

    //=========================================================================
    // Gray Code Conversion Functions
    //=========================================================================

    function automatic logic [PTR_WIDTH-1:0] bin_to_gray(
        input logic [PTR_WIDTH-1:0] bin
    );
        return bin ^ (bin >> 1);
    endfunction

    function automatic logic [PTR_WIDTH-1:0] gray_to_bin(
        input logic [PTR_WIDTH-1:0] gray
    );
        logic [PTR_WIDTH-1:0] bin;
        bin[PTR_WIDTH-1] = gray[PTR_WIDTH-1];
        for (int i = PTR_WIDTH-2; i >= 0; i--) begin
            bin[i] = bin[i+1] ^ gray[i];
        end
        return bin;
    endfunction

    //=========================================================================
    // Write Domain Logic
    //=========================================================================

    logic wr_ptr_incr;
    assign wr_ptr_incr = wr_en && !wr_full;

    always_ff @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wr_ptr_bin <= '0;
            wr_ptr_gray <= '0;
            wr_overflow <= 1'b0;
        end else begin
            wr_overflow <= 1'b0;

            if (wr_en && wr_full) begin
                wr_overflow <= 1'b1;
            end else if (wr_ptr_incr) begin
                wr_ptr_bin <= wr_ptr_bin + 1;
                wr_ptr_gray <= bin_to_gray(wr_ptr_bin + 1);
            end
        end
    end

    // Write to memory
    always_ff @(posedge wr_clk) begin
        if (wr_ptr_incr) begin
            mem[wr_ptr_bin[ADDR_WIDTH-1:0]] <= wr_data;
        end
    end

    // Synchronize read pointer to write domain (2-FF synchronizer)
    always_ff @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            rd_ptr_gray_meta <= '0;
            rd_ptr_gray_sync <= '0;
        end else begin
            rd_ptr_gray_meta <= rd_ptr_gray;
            rd_ptr_gray_sync <= rd_ptr_gray_meta;
        end
    end

    // Full detection (in write domain)
    // Full when write pointer's MSB differs and rest matches (wrapped around)
    logic [PTR_WIDTH-1:0] wr_ptr_gray_next;
    assign wr_ptr_gray_next = bin_to_gray(wr_ptr_bin + 1);

    assign wr_full = (wr_ptr_gray_next[PTR_WIDTH-1] != rd_ptr_gray_sync[PTR_WIDTH-1]) &&
                     (wr_ptr_gray_next[PTR_WIDTH-2] != rd_ptr_gray_sync[PTR_WIDTH-2]) &&
                     (wr_ptr_gray_next[PTR_WIDTH-3:0] == rd_ptr_gray_sync[PTR_WIDTH-3:0]);

    // Almost full detection
    logic [PTR_WIDTH-1:0] rd_ptr_bin_sync;
    assign rd_ptr_bin_sync = gray_to_bin(rd_ptr_gray_sync);

    always_comb begin
        if (wr_ptr_bin >= rd_ptr_bin_sync) begin
            wr_count = wr_ptr_bin - rd_ptr_bin_sync;
        end else begin
            wr_count = DEPTH - rd_ptr_bin_sync + wr_ptr_bin;
        end
    end

    assign wr_almost_full = (wr_count >= ALMOST_FULL_THRESH);

    //=========================================================================
    // Read Domain Logic
    //=========================================================================

    logic rd_ptr_incr;
    assign rd_ptr_incr = rd_en && !rd_empty;

    always_ff @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_ptr_bin <= '0;
            rd_ptr_gray <= '0;
            rd_underflow <= 1'b0;
        end else begin
            rd_underflow <= 1'b0;

            if (rd_en && rd_empty) begin
                rd_underflow <= 1'b1;
            end else if (rd_ptr_incr) begin
                rd_ptr_bin <= rd_ptr_bin + 1;
                rd_ptr_gray <= bin_to_gray(rd_ptr_bin + 1);
            end
        end
    end

    // Read from memory (registered output for BRAM compatibility)
    always_ff @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_data <= '0;
        end else if (rd_ptr_incr) begin
            rd_data <= mem[rd_ptr_bin[ADDR_WIDTH-1:0]];
        end
    end

    // Synchronize write pointer to read domain (2-FF synchronizer)
    always_ff @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            wr_ptr_gray_meta <= '0;
            wr_ptr_gray_sync <= '0;
        end else begin
            wr_ptr_gray_meta <= wr_ptr_gray;
            wr_ptr_gray_sync <= wr_ptr_gray_meta;
        end
    end

    // Empty detection (in read domain)
    // Empty when pointers are equal
    assign rd_empty = (rd_ptr_gray == wr_ptr_gray_sync);

    // Almost empty detection
    logic [PTR_WIDTH-1:0] wr_ptr_bin_sync;
    logic [PTR_WIDTH:0] rd_count;

    assign wr_ptr_bin_sync = gray_to_bin(wr_ptr_gray_sync);

    always_comb begin
        if (wr_ptr_bin_sync >= rd_ptr_bin) begin
            rd_count = wr_ptr_bin_sync - rd_ptr_bin;
        end else begin
            rd_count = DEPTH - rd_ptr_bin + wr_ptr_bin_sync;
        end
    end

    assign rd_almost_empty = (rd_count <= ALMOST_EMPTY_THRESH);

    //=========================================================================
    // Assertions
    //=========================================================================

`ifdef SIMULATION
    // Check for overflow
    always @(posedge wr_clk) begin
        if (wr_overflow)
            $error("async_fifo: Write overflow detected!");
    end

    // Check for underflow
    always @(posedge rd_clk) begin
        if (rd_underflow)
            $error("async_fifo: Read underflow detected!");
    end
`endif

endmodule : async_fifo


//-----------------------------------------------------------------------------
// Synchronous FIFO
//-----------------------------------------------------------------------------
// Single-clock FIFO for internal buffering.
//-----------------------------------------------------------------------------

module sync_fifo #(
    parameter int WIDTH = 64,
    parameter int DEPTH = 16
) (
    input  logic                              clk,
    input  logic                              rst_n,

    // Write interface
    input  logic                              wr_en,
    input  logic [WIDTH-1:0]                  wr_data,
    output logic                              full,

    // Read interface
    input  logic                              rd_en,
    output logic [WIDTH-1:0]                  rd_data,
    output logic                              empty,

    // Status
    output logic [$clog2(DEPTH):0]            count
);

    localparam int ADDR_WIDTH = $clog2(DEPTH);

    // Memory
    logic [WIDTH-1:0] mem [DEPTH];

    // Pointers
    logic [ADDR_WIDTH:0] wr_ptr;
    logic [ADDR_WIDTH:0] rd_ptr;

    // Control
    logic do_write, do_read;
    assign do_write = wr_en && !full;
    assign do_read = rd_en && !empty;

    // Write logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
        end else if (do_write) begin
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= wr_data;
            wr_ptr <= wr_ptr + 1;
        end
    end

    // Read logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr <= '0;
            rd_data <= '0;
        end else if (do_read) begin
            rd_data <= mem[rd_ptr[ADDR_WIDTH-1:0]];
            rd_ptr <= rd_ptr + 1;
        end
    end

    // Status
    assign count = wr_ptr - rd_ptr;
    assign full = (count == DEPTH);
    assign empty = (count == 0);

endmodule : sync_fifo
