//-----------------------------------------------------------------------------
// Score Update Module (Q8.8 Fixed-Point Arithmetic)
//-----------------------------------------------------------------------------
// Implements the attention score update formula:
//   new_score = alpha * new_weight + (1-alpha) * old_score
//
// Where alpha = 0.2 (configurable) controls the EMA smoothing factor.
// Uses Q8.8 fixed-point arithmetic for area efficiency.
//-----------------------------------------------------------------------------

module score_update
    import pcam_pkg::*;
#(
    parameter logic [SCORE_WIDTH-1:0] ALPHA_PARAM = ALPHA  // Default 0.2
) (
    input  logic             clk,
    input  logic             rst_n,

    // Input
    input  logic [SCORE_WIDTH-1:0] old_score,
    input  logic [SCORE_WIDTH-1:0] new_weight,
    input  logic                   valid_in,

    // Output (2-cycle latency)
    output logic [SCORE_WIDTH-1:0] updated_score,
    output logic                   valid_out
);

    // Calculate (1 - alpha) at compile time
    localparam logic [SCORE_WIDTH-1:0] ONE_MINUS_ALPHA_PARAM =
        16'h0100 - ALPHA_PARAM;  // 256 - alpha

    //-------------------------------------------------------------------------
    // Pipeline Stage 1: Multiply
    //-------------------------------------------------------------------------
    logic [31:0] term1_mult;  // alpha * new_weight
    logic [31:0] term2_mult;  // (1-alpha) * old_score
    logic        stage1_valid;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            term1_mult   <= '0;
            term2_mult   <= '0;
            stage1_valid <= 1'b0;
        end else begin
            // Q8.8 * Q8.8 = Q16.16
            term1_mult   <= new_weight * ALPHA_PARAM;
            term2_mult   <= old_score * ONE_MINUS_ALPHA_PARAM;
            stage1_valid <= valid_in;
        end
    end

    //-------------------------------------------------------------------------
    // Pipeline Stage 2: Add and Truncate
    //-------------------------------------------------------------------------
    logic [31:0] sum;
    logic [SCORE_WIDTH-1:0] result;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            updated_score <= '0;
            valid_out     <= 1'b0;
        end else begin
            // Add terms and round to Q8.8
            sum = term1_mult + term2_mult;

            // Round: add 0.5 (128 in Q16.16) before truncating
            result = (sum + 32'd128) >> 8;

            // Saturate on overflow (shouldn't happen with proper alpha)
            updated_score <= (sum[31:24] != 0) ? 16'hFFFF : result;
            valid_out     <= stage1_valid;
        end
    end

endmodule : score_update


//-----------------------------------------------------------------------------
// Decay Module (Q8.8 Fixed-Point)
//-----------------------------------------------------------------------------
// Applies exponential decay to scores:
//   new_score = old_score * decay_rate
//
// Where decay_rate = 0.99 (configurable)
//-----------------------------------------------------------------------------

module score_decay
    import pcam_pkg::*;
#(
    parameter logic [SCORE_WIDTH-1:0] DECAY_PARAM = DECAY_RATE  // Default 0.99
) (
    input  logic             clk,
    input  logic             rst_n,

    // Input
    input  logic [SCORE_WIDTH-1:0] old_score,
    input  logic                   valid_in,

    // Output (1-cycle latency)
    output logic [SCORE_WIDTH-1:0] decayed_score,
    output logic                   valid_out
);

    logic [31:0] product;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decayed_score <= '0;
            valid_out     <= 1'b0;
        end else begin
            // Q8.8 * Q8.8 = Q16.16, then truncate back to Q8.8
            product = old_score * DECAY_PARAM;

            // Round and truncate
            decayed_score <= (product + 32'd128) >> 8;
            valid_out     <= valid_in;
        end
    end

endmodule : score_decay


//-----------------------------------------------------------------------------
// Frequency Boost Calculator
//-----------------------------------------------------------------------------
// Adds a small boost based on sketch-estimated frequency:
//   boost = log1p(freq_estimate) * 0.01
//
// Input is a 4-bit saturating estimate from the CTM+ Count-Min sketch
// (FREQ_SKETCH_COUNTER_BITS, see pcam_pkg.sv and freq_sketch.sv). The
// legacy 12-bit access_count input was removed per ADR-0001 when
// block_entry_t lost its frequency field.
//
// Uses a small LUT for log approximation.
//-----------------------------------------------------------------------------

module frequency_boost
    import pcam_pkg::*;
(
    input  logic             clk,
    input  logic             rst_n,

    // Input — 4-bit sketch estimate, already saturated at 15.
    input  logic [FREQ_SKETCH_COUNTER_BITS-1:0] freq_estimate,
    input  logic             valid_in,

    // Output (1-cycle latency)
    output logic [SCORE_WIDTH-1:0] boost_value,
    output logic                   valid_out
);

    // Log1p LUT: log(1 + x) * 256 * 0.01 = log(1+x) * 2.56
    // Indexed directly by the 4-bit sketch estimate (0-15 range).
    logic [7:0] log_lut [16];

    initial begin
        // log1p(0) * 2.56 = 0
        log_lut[0]  = 8'd0;
        // log1p(1) * 2.56 = 1.77
        log_lut[1]  = 8'd2;
        // log1p(2) * 2.56 = 2.81
        log_lut[2]  = 8'd3;
        // log1p(3) * 2.56 = 3.55
        log_lut[3]  = 8'd4;
        // log1p(4) * 2.56 = 4.12
        log_lut[4]  = 8'd4;
        // log1p(5-7)
        log_lut[5]  = 8'd5;
        log_lut[6]  = 8'd5;
        log_lut[7]  = 8'd5;
        // log1p(8-15)
        log_lut[8]  = 8'd6;
        log_lut[9]  = 8'd6;
        log_lut[10] = 8'd6;
        log_lut[11] = 8'd6;
        log_lut[12] = 8'd7;
        log_lut[13] = 8'd7;
        log_lut[14] = 8'd7;
        log_lut[15] = 8'd7;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            boost_value <= '0;
            valid_out   <= 1'b0;
        end else begin
            // freq_estimate is already 4 bits — direct LUT index.
            boost_value <= {8'b0, log_lut[freq_estimate]};
            valid_out   <= valid_in;
        end
    end

endmodule : frequency_boost
