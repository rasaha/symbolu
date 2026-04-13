//-----------------------------------------------------------------------------
// PCAM Package - Types, Constants, and Parameters
//-----------------------------------------------------------------------------
// This package defines all shared types, constants, and parameters for the
// PCAM (Predictive Context Attention Memory) hardware implementation.
//-----------------------------------------------------------------------------

package pcam_pkg;

    //-------------------------------------------------------------------------
    // Configuration Parameters
    //-------------------------------------------------------------------------

    // Memory Configuration
    parameter int NUM_BANKS = 64;
    parameter int BANK_DEPTH = 16384;          // 16K entries per bank
    parameter int TOTAL_ENTRIES = 1048576;     // 1M total entries
    parameter int ENTRY_WIDTH = 64;            // 64-bit block entry

    // Block ID Configuration
    parameter int BLOCK_ID_WIDTH = 20;         // Supports up to 1M blocks
    parameter int BANK_ID_WIDTH = 6;           // log2(64) = 6 bits
    parameter int BANK_ADDR_WIDTH = 14;        // log2(16384) = 14 bits

    // Sequence Configuration
    parameter int MAX_SEQUENCES = 64;
    parameter int SEQ_ID_WIDTH = 6;

    // Top-K Configuration
    parameter int K_MAX = 256;
    parameter int K_DEFAULT = 256;
    parameter int K_WIDTH = 9;                 // log2(256) + 1

    // Score Configuration (Q8.8 Fixed Point)
    parameter int SCORE_WIDTH = 16;
    parameter int SCORE_INT_BITS = 8;
    parameter int SCORE_FRAC_BITS = 8;

    // Section Configuration (Soft Hierarchical Prior)
    parameter int SECTION_SIZE = 16;           // Blocks per section
    parameter int NUM_SECTIONS = 4096;         // 64K blocks / 16
    parameter int SECTION_ID_WIDTH = 12;

    //-------------------------------------------------------------------------
    // Fixed-Point Constants (Q8.8)
    //-------------------------------------------------------------------------

    // Score update: new = alpha * weight + (1-alpha) * old
    parameter logic [SCORE_WIDTH-1:0] ALPHA = 16'h0033;          // 0.2 * 256 = 51
    parameter logic [SCORE_WIDTH-1:0] ONE_MINUS_ALPHA = 16'h00CD; // 0.8 * 256 = 205

    // Decay rate: 0.99 * 256 = 253
    parameter logic [SCORE_WIDTH-1:0] DECAY_RATE = 16'h00FD;

    // Section boost coefficient: 0.15 * 256 = 38
    parameter logic [SCORE_WIDTH-1:0] SECTION_ALPHA = 16'h0026;

    //-------------------------------------------------------------------------
    // CTM+ Frequency Sketch Parameters
    //-------------------------------------------------------------------------
    // Canonical per ADR-0001 and the Python reference at
    // CTM_plus/KVPolicy/kv_policy/attention_evictor.py:69-112. The four
    // seed hashes, the depth of 4, and the 4-bit counter saturation are
    // load-bearing for bit-parity with the Python port in
    // simulator/pcam/kv_policy.py. Do not retune.
    //
    // Width is parameterizable so the RTL can size the sketch BRAM
    // per deployment; the top-level width must be a power of two and
    // should satisfy width >= max(64, capacity).

    parameter int FREQ_SKETCH_DEPTH         = 4;
    parameter int FREQ_SKETCH_WIDTH         = 1024;   // must be power of two
    parameter int FREQ_SKETCH_COUNTER_BITS  = 4;      // 4-bit saturating counter
    parameter int FREQ_SKETCH_COUNTER_MAX   = 15;     // 2**4 - 1
    parameter int FREQ_SKETCH_KEY_WIDTH     = 32;     // wide enough for block_id * seed
    parameter int FREQ_SKETCH_INDEX_WIDTH   = 10;     // log2(FREQ_SKETCH_WIDTH)

    // Reset threshold multiplier: halve all counters once the total
    // number of increments crosses capacity * RESET_MULT. Matches the
    // reference's `reset_threshold = capacity * 10`.
    parameter int FREQ_SKETCH_RESET_MULT    = 10;

    // Four fixed seed hashes — byte-for-byte identical to the reference.
    parameter logic [31:0] FREQ_SKETCH_SEED_0 = 32'h9E3779B9;
    parameter logic [31:0] FREQ_SKETCH_SEED_1 = 32'h517CC1B7;
    parameter logic [31:0] FREQ_SKETCH_SEED_2 = 32'h6C62272E;
    parameter logic [31:0] FREQ_SKETCH_SEED_3 = 32'h2E1B2138;

    //-------------------------------------------------------------------------
    // Command Encoding
    //-------------------------------------------------------------------------

    typedef enum logic [2:0] {
        OP_ATTEND       = 3'b000,
        OP_UPDATE       = 3'b001,
        OP_BATCH_UPDATE = 3'b010,
        OP_DECAY        = 3'b011,
        OP_ALLOC        = 3'b100,
        OP_FREE         = 3'b101,
        OP_GET_SCORES   = 3'b110,
        OP_RESERVED     = 3'b111
    } op_type_t;

    //-------------------------------------------------------------------------
    // Data Structures
    //-------------------------------------------------------------------------

    // Block Entry (stored in BRAM)
    //
    // The legacy 12-bit access_count field has been removed per ADR-0001.
    // Frequency tracking now lives in the CTM+ Count-Min sketch (see
    // FREQ_SKETCH_* parameters above and freq_sketch.sv). The 12 bits
    // are preserved as reserved2 to keep the struct at 64 bits so
    // consumers of bank_mem / bank_array do not need alignment changes.
    typedef struct packed {
        logic [SCORE_WIDTH-1:0]   score;         // Q8.8 attention score
        logic [11:0]              reserved2;     // formerly access_count; sketch owns frequency now
        logic [19:0]              last_step;     // Last access step
        logic [15:0]              reserved;      // Future use
    } block_entry_t;

    // Candidate for Top-K selection
    typedef struct packed {
        logic [SCORE_WIDTH-1:0]   score;
        logic [BLOCK_ID_WIDTH-1:0] block_id;
    } candidate_t;

    // Command structure
    typedef struct packed {
        op_type_t                  op_type;      // [63:61]
        logic [SEQ_ID_WIDTH-1:0]   seq_id;       // [60:55]
        logic [BLOCK_ID_WIDTH-1:0] query_block;  // [54:35]
        logic [BLOCK_ID_WIDTH-1:0] key_block;    // [34:15]
        logic [14:0]               data;         // [14:0] - weight or k_value
    } command_t;

    // ATTEND response
    typedef struct packed {
        logic                      valid;
        logic [K_WIDTH-1:0]        count;        // Actual candidates returned
        candidate_t [K_MAX-1:0]    candidates;   // Sorted by score descending
        logic [15:0]               latency_ns;   // Measured latency
        logic [7:0]                bank_conflicts;
    } attend_response_t;

    // Section entry (for soft hierarchical prior)
    typedef struct packed {
        logic [23:0]              total_attention;  // Q12.12
        logic [15:0]              access_count;
        logic [7:0]               unique_queries;   // Saturating counter
        logic [15:0]              reserved;
    } section_entry_t;

    //-------------------------------------------------------------------------
    // Workload Pattern Detection
    //-------------------------------------------------------------------------

    typedef enum logic [2:0] {
        PATTERN_UNKNOWN     = 3'b000,
        PATTERN_CHAT        = 3'b001,
        PATTERN_LONG_CTX    = 3'b010,
        PATTERN_RAG         = 3'b011,
        PATTERN_CODE        = 3'b100
    } workload_pattern_t;

    //-------------------------------------------------------------------------
    // Status and Error Codes
    //-------------------------------------------------------------------------

    typedef enum logic [3:0] {
        STATUS_OK           = 4'b0000,
        STATUS_BUSY         = 4'b0001,
        STATUS_SEQ_NOT_FOUND = 4'b0010,
        STATUS_SEQ_FULL     = 4'b0011,
        STATUS_BANK_CONFLICT = 4'b0100,
        STATUS_OVERFLOW     = 4'b0101,
        STATUS_INVALID_CMD  = 4'b1111
    } status_t;

    //-------------------------------------------------------------------------
    // Helper Functions
    //-------------------------------------------------------------------------

    // Calculate bank ID from block ID (XOR hash for better distribution)
    function automatic logic [BANK_ID_WIDTH-1:0] get_bank_id(
        input logic [BLOCK_ID_WIDTH-1:0] block_id
    );
        return block_id[5:0] ^ block_id[11:6];
    endfunction

    // Calculate bank address from block ID
    function automatic logic [BANK_ADDR_WIDTH-1:0] get_bank_addr(
        input logic [BLOCK_ID_WIDTH-1:0] block_id
    );
        return block_id[BLOCK_ID_WIDTH-1:BANK_ID_WIDTH];
    endfunction

    // Get section ID from block ID
    function automatic logic [SECTION_ID_WIDTH-1:0] get_section_id(
        input logic [BLOCK_ID_WIDTH-1:0] block_id
    );
        return block_id[BLOCK_ID_WIDTH-1:4];  // Divide by 16
    endfunction

    // Q8.8 multiply with rounding
    function automatic logic [SCORE_WIDTH-1:0] q88_mult(
        input logic [SCORE_WIDTH-1:0] a,
        input logic [SCORE_WIDTH-1:0] b
    );
        logic [31:0] product;
        product = a * b;
        return (product + 128) >> 8;  // Round to nearest
    endfunction

    // Saturating add for scores
    function automatic logic [SCORE_WIDTH-1:0] score_sat_add(
        input logic [SCORE_WIDTH-1:0] a,
        input logic [SCORE_WIDTH-1:0] b
    );
        logic [16:0] sum;
        sum = {1'b0, a} + {1'b0, b};
        return sum[16] ? 16'hFFFF : sum[15:0];
    endfunction

    //-------------------------------------------------------------------------
    // Frequency Sketch Hash
    //-------------------------------------------------------------------------
    // Combinational hash helper matching the reference at
    // attention_evictor.py:89-92 :
    //
    //     h = key * seed
    //     h ^= h >> 16
    //     return h & (width - 1)
    //
    // `row_select` picks one of the four fixed seeds. Used by freq_sketch.sv
    // in its increment and estimate paths. Result width is the full index
    // width; callers mask down to log2(FREQ_SKETCH_WIDTH) bits.
    function automatic logic [FREQ_SKETCH_KEY_WIDTH-1:0] sketch_hash(
        input logic [BLOCK_ID_WIDTH-1:0] key,
        input logic [1:0]                row_select
    );
        logic [FREQ_SKETCH_KEY_WIDTH-1:0] seed;
        logic [FREQ_SKETCH_KEY_WIDTH-1:0] product;
        unique case (row_select)
            2'd0: seed = FREQ_SKETCH_SEED_0;
            2'd1: seed = FREQ_SKETCH_SEED_1;
            2'd2: seed = FREQ_SKETCH_SEED_2;
            2'd3: seed = FREQ_SKETCH_SEED_3;
            default: seed = FREQ_SKETCH_SEED_0;
        endcase
        product = key * seed;
        return product ^ (product >> 16);
    endfunction

endpackage : pcam_pkg
