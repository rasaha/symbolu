//-----------------------------------------------------------------------------
// Compare-Swap Unit for Bitonic Sorting Network
//-----------------------------------------------------------------------------
// Building block for the Top-K selection network. Compares two candidates
// and outputs them in sorted order based on direction flag.
//
// Used in bitonic merge sort:
//   - direction=0: ascending (smaller on out_lo)
//   - direction=1: descending (larger on out_lo)
//-----------------------------------------------------------------------------

module cmp_swap
    import pcam_pkg::*;
#(
    parameter int WIDTH = SCORE_WIDTH + BLOCK_ID_WIDTH  // 36 bits
) (
    // Inputs
    input  logic [WIDTH-1:0] in_a,
    input  logic [WIDTH-1:0] in_b,
    input  logic             direction,  // 0=ascending, 1=descending

    // Outputs (combinational)
    output logic [WIDTH-1:0] out_hi,     // Higher score
    output logic [WIDTH-1:0] out_lo      // Lower score
);

    // Extract scores from packed candidates
    // Format: [score(16) | block_id(20)]
    localparam int SCORE_POS = WIDTH - SCORE_WIDTH;

    logic [SCORE_WIDTH-1:0] score_a;
    logic [SCORE_WIDTH-1:0] score_b;
    logic                   a_less_than_b;
    logic                   swap;

    assign score_a = in_a[WIDTH-1:SCORE_POS];
    assign score_b = in_b[WIDTH-1:SCORE_POS];

    // Compare scores
    assign a_less_than_b = (score_a < score_b);

    // Swap based on comparison and direction
    // direction=0 (ascending): swap if a > b (want smaller on lo)
    // direction=1 (descending): swap if a < b (want larger on lo)
    assign swap = a_less_than_b ^ direction;

    // Output assignment
    assign out_hi = swap ? in_b : in_a;
    assign out_lo = swap ? in_a : in_b;

    //-------------------------------------------------------------------------
    // Assertions
    //-------------------------------------------------------------------------
`ifdef SIMULATION
    // Verify output ordering
    always_comb begin
        automatic logic [SCORE_WIDTH-1:0] hi_score = out_hi[WIDTH-1:SCORE_POS];
        automatic logic [SCORE_WIDTH-1:0] lo_score = out_lo[WIDTH-1:SCORE_POS];

        assert (hi_score >= lo_score)
            else $error("cmp_swap: Output ordering violated");
    end
`endif

endmodule : cmp_swap


//-----------------------------------------------------------------------------
// Registered Compare-Swap Unit (Pipelined Version)
//-----------------------------------------------------------------------------
// Adds pipeline register for timing closure in deep sorting networks.
//-----------------------------------------------------------------------------

module cmp_swap_reg
    import pcam_pkg::*;
#(
    parameter int WIDTH = SCORE_WIDTH + BLOCK_ID_WIDTH
) (
    input  logic             clk,
    input  logic             rst_n,

    // Input with valid
    input  logic [WIDTH-1:0] in_a,
    input  logic [WIDTH-1:0] in_b,
    input  logic             in_valid,
    input  logic             direction,

    // Registered output
    output logic [WIDTH-1:0] out_hi,
    output logic [WIDTH-1:0] out_lo,
    output logic             out_valid
);

    // Combinational compare-swap
    logic [WIDTH-1:0] cmp_hi;
    logic [WIDTH-1:0] cmp_lo;

    cmp_swap #(.WIDTH(WIDTH)) u_cmp (
        .in_a(in_a),
        .in_b(in_b),
        .direction(direction),
        .out_hi(cmp_hi),
        .out_lo(cmp_lo)
    );

    // Pipeline register
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_hi    <= '0;
            out_lo    <= '0;
            out_valid <= 1'b0;
        end else begin
            out_hi    <= cmp_hi;
            out_lo    <= cmp_lo;
            out_valid <= in_valid;
        end
    end

endmodule : cmp_swap_reg
