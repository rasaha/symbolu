// =============================================================================
// USE-6G Massive MIMO Synchronization Chip - Package Definitions
// =============================================================================
// Implements types, constants, and structs from USE_6G_CHIP_SPEC.md
// Patent formulas U1-U5 mapped to hardware functional units
// =============================================================================

package use_6g_pkg;

  // =========================================================================
  // Global Parameters
  // =========================================================================
  localparam int NUM_ELEMENTS     = 128;   // Total antenna elements (2 panels x 64)
  localparam int NUM_ELEMENTS_X   = 8;     // Elements per axis
  localparam int NUM_ELEMENTS_Y   = 8;     // Elements per axis
  localparam int NUM_PANELS       = 2;     // Front + back panels
  localparam int ELEMENTS_PER_PANEL = 64;  // 8x8 UPA per panel
  localparam int NUM_RF_CHAINS    = 4;     // Hybrid beamforming RF chains
  localparam int MAX_BEAMS        = 4;     // One per RF chain
  localparam int CORR_WINDOW      = 16;    // U1 correlation window depth
  localparam int MAX_SYNC_ITER    = 50;    // Max sync iterations per interval
  localparam int COH_HISTORY_LEN  = 5;     // TC stability window
  localparam int LR_ADAPT_WINDOW  = 10;    // PUE adaptation history

  // Element index width
  localparam int ELEM_IDX_W       = $clog2(NUM_ELEMENTS); // 7 bits
  localparam int BEAM_IDX_W       = $clog2(MAX_BEAMS);    // 2 bits

  // =========================================================================
  // Fixed-Point Format Parameters
  // =========================================================================
  // Q2.30 - Phase values [0, 2pi), range ~[-4, 4)
  localparam int Q2_30_W          = 32;
  localparam int Q2_30_INT        = 2;
  localparam int Q2_30_FRAC       = 30;

  // UQ0.32 - Coherence values [0, 1]
  localparam int UQ0_32_W         = 32;

  // Q1.15 - Calibration offsets
  localparam int Q1_15_W          = 16;

  // UQ1.15 - Amplitude calibration
  localparam int UQ1_15_W         = 16;

  // Q8.8 - Position in wavelengths, dB values
  localparam int Q8_8_W           = 16;

  // UQ0.16 - Learning rate
  localparam int UQ0_16_W         = 16;

  // UQ0.8 - Multipliers
  localparam int UQ0_8_W          = 8;

  // Q9.7 - Angle in degrees
  localparam int Q9_7_W           = 16;

  // UQ16.16 - Frequency/wavelength
  localparam int UQ16_16_W        = 32;

  // UQ8.8 - Power/temperature
  localparam int UQ8_8_W          = 16;

  // =========================================================================
  // Key Constants (Fixed-Point Encoded)
  // =========================================================================
  // 2*pi in Q2.30 = 6.283185307 * 2^30 = 6,746,518,852
  localparam logic [Q2_30_W-1:0] TWO_PI_Q2_30    = 32'h1921FB54;
  // pi in Q2.30
  localparam logic [Q2_30_W-1:0] PI_Q2_30        = 32'h0C90FDAA;

  // Default learning rate 0.1 in UQ0.16 = 0x199A
  localparam logic [UQ0_16_W-1:0] DEFAULT_LR     = 16'h199A;

  // Coherence threshold 0.95 in UQ0.32 = 0xF333_3333
  localparam logic [UQ0_32_W-1:0] COH_THRESH_95  = 32'hF3333333;

  // Hysteresis 0.02 in UQ0.32 = 0x051E_B851
  localparam logic [UQ0_32_W-1:0] HYSTERESIS_02  = 32'h051EB851;

  // Stability variance threshold 0.001 in UQ0.32
  localparam logic [UQ0_32_W-1:0] STAB_VAR_001   = 32'h00418937;

  // LR multipliers in UQ0.8
  localparam logic [UQ0_8_W-1:0] LR_FAST_MULT    = 8'h26; // 1.5 * 0.1 => effective 0.15
  localparam logic [UQ0_8_W-1:0] LR_FINE_MULT    = 8'h80; // 0.5
  localparam logic [UQ0_8_W-1:0] LR_DAMP_MULT    = 8'h4D; // 0.3
  localparam logic [UQ0_8_W-1:0] LR_TRACK_MULT   = 8'hB3; // 0.7

  // Sin/cos LUT parameters
  localparam int SIN_COS_LUT_DEPTH = 1024;  // 10-bit address
  localparam int SIN_COS_LUT_AW    = 10;
  localparam int SIN_COS_LUT_DW    = 16;    // Output precision

  // Adder tree depth for 128 elements
  localparam int ADDER_TREE_DEPTH  = 7;     // log2(128)

  // Number of element pairs for full correlation: n*(n-1)/2
  localparam int NUM_PAIRS         = (NUM_ELEMENTS * (NUM_ELEMENTS - 1)) / 2; // 8128

  // =========================================================================
  // Enumerations
  // =========================================================================

  // Frequency band selection (GCR_CTRL[7:6])
  typedef enum logic [1:0] {
    FREQ_FR3_UPPER   = 2'b00,  // 15 GHz
    FREQ_FR2_MMWAVE  = 2'b01,  // 39 GHz
    FREQ_SUB_THZ_LOW = 2'b10,  // 140 GHz (primary target)
    FREQ_SUB_THZ_HIGH= 2'b11   // 500 GHz
  } freq_band_e;

  // Sync mode (GCR_CTRL[5:4])
  typedef enum logic [1:0] {
    SYNC_COHERENCE   = 2'b00,  // Phase coherence sync
    SYNC_BEAMFORMING = 2'b01,  // Beamforming mode
    SYNC_TRACKING    = 2'b10   // Beam tracking mode
  } sync_mode_e;

  // Sync state (GCR_STATUS[2:0] and TC_SYNC_STATE)
  typedef enum logic [2:0] {
    STATE_UNSYNC     = 3'b000,
    STATE_ACQUIRING  = 3'b001,
    STATE_LOCKED     = 3'b010,
    STATE_TRACKING   = 3'b011,
    STATE_LOST       = 3'b100
  } sync_state_e;

  // U5 Correlation classification
  typedef enum logic [1:0] {
    CORR_STRONG      = 2'b00,  // > 0.7
    CORR_MODERATE    = 2'b01,  // 0.3 - 0.7
    CORR_WEAK        = 2'b10,  // -0.3 - 0.3
    CORR_ANTI        = 2'b11   // < -0.3
  } corr_class_e;

  // Power states
  typedef enum logic [1:0] {
    PWR_IDLE         = 2'b00,
    PWR_SYNC         = 2'b01,
    PWR_BEAM         = 2'b10,
    PWR_PEAK         = 2'b11
  } power_state_e;

  // Sync cycle FSM states
  typedef enum logic [2:0] {
    SCYC_IDLE        = 3'b000,
    SCYC_READ_EPRF   = 3'b001,
    SCYC_MFU_C1      = 3'b010, // MFU cycle 1: sin/cos accum + atan2
    SCYC_MFU_C2      = 3'b011, // MFU cycle 2: per-element gradient
    SCYC_PUE         = 3'b100, // Phase update
    SCYC_TC_WB       = 3'b101  // Threshold check + writeback
  } sync_cycle_state_e;

  // MBC scheduling modes
  typedef enum logic {
    SCHED_ROUND_ROBIN = 1'b0,
    SCHED_PRIORITY    = 1'b1
  } sched_mode_e;

  // LR adaptation condition
  typedef enum logic [1:0] {
    LR_OSCILLATING   = 2'b00,  // >50% sign changes => 0.3x
    LR_HIGH_COH      = 2'b01,  // >0.9 => 0.5x
    LR_LOW_COH       = 2'b10,  // <0.5 => 1.5x
    LR_NORMAL        = 2'b11   // default => 1.0x
  } lr_condition_e;

  // =========================================================================
  // Structures
  // =========================================================================

  // Per-element state in EPRF (152 bits total = 19 bytes)
  typedef struct packed {
    logic [Q2_30_W-1:0]  phase;            // 32b: Current phase [0, 2pi) Q2.30
    logic [Q2_30_W-1:0]  target_phase;     // 32b: Steering target phase Q2.30
    logic [Q1_15_W-1:0]  phase_offset_cal; // 16b: Factory calibration offset Q1.15
    logic [UQ1_15_W-1:0] amplitude_cal;    // 16b: Element gain calibration UQ1.15
    logic [Q8_8_W-1:0]   pos_x;           // 16b: X position in wavelengths Q8.8
    logic [Q8_8_W-1:0]   pos_y;           // 16b: Y position in wavelengths Q8.8
    logic [7:0]          flags;            // 8b: active[0], failed[1], panel_id[3:2]
  } element_state_t;                        // Total: 152 bits

  // Element flags bit positions
  localparam int FLAG_ACTIVE   = 0;
  localparam int FLAG_FAILED   = 1;
  localparam int FLAG_PANEL_LO = 2;
  localparam int FLAG_PANEL_HI = 3;

  // Beam context for MBC
  typedef struct packed {
    logic [Q9_7_W-1:0]  azimuth;          // 16b: Azimuth angle Q9.7
    logic [Q9_7_W-1:0]  elevation;        // 16b: Elevation angle Q9.7
    logic [Q8_8_W-1:0]  gain;             // 16b: Computed gain Q8.8 dB
    logic [Q8_8_W-1:0]  sidelobe;         // 16b: Sidelobe level Q8.8 dB
    logic [31:0]        user_id;          // 32b: User ID
    logic               active;           // 1b: Beam active flag
  } beam_context_t;

  // Interrupt bit positions (GCR_IRQ_EN / GCR_IRQ_STAT)
  localparam int IRQ_SYNC_LOCKED     = 0;
  localparam int IRQ_SYNC_LOST       = 1;
  localparam int IRQ_HANDOVER_DONE   = 2;
  localparam int IRQ_BEAM_STEER_DONE = 3;
  localparam int IRQ_ELEMENT_FAIL    = 4;
  localparam int IRQ_THERMAL_WARN    = 5;
  localparam int IRQ_CORR_READY      = 6;
  localparam int NUM_IRQS            = 7;

  // =========================================================================
  // Register Address Map (from spec Section 6)
  // =========================================================================
  // Base addresses (12-bit address space)
  localparam logic [15:0] BASE_GCR  = 16'h0000;
  localparam logic [15:0] BASE_MFU  = 16'h0100;
  localparam logic [15:0] BASE_PUE  = 16'h0200;
  localparam logic [15:0] BASE_CE   = 16'h0300;
  localparam logic [15:0] BASE_CA   = 16'h0400;
  localparam logic [15:0] BASE_TC   = 16'h0500;
  localparam logic [15:0] BASE_SVG  = 16'h0600;
  localparam logic [15:0] BASE_MBC  = 16'h0700;
  localparam logic [15:0] BASE_PHC  = 16'h0800;
  localparam logic [15:0] BASE_BQM  = 16'h0900;
  localparam logic [15:0] BASE_CHE  = 16'h0A00;
  localparam logic [15:0] BASE_PWR  = 16'h0B00;
  localparam logic [15:0] BASE_DBG  = 16'h0C00;
  localparam logic [15:0] BASE_EPRF = 16'h1000;
  localparam logic [15:0] BASE_PHIST= 16'h2000;
  localparam logic [15:0] BASE_BCTX = 16'h4000;
  localparam logic [15:0] BASE_CAL  = 16'h5000;

  // GCR register offsets
  localparam logic [7:0] GCR_CTRL_OFF        = 8'h00;
  localparam logic [7:0] GCR_STATUS_OFF      = 8'h04;
  localparam logic [7:0] GCR_IRQ_EN_OFF      = 8'h08;
  localparam logic [7:0] GCR_IRQ_STAT_OFF    = 8'h0C;
  localparam logic [7:0] GCR_SYNC_CNT_LO_OFF = 8'h10;
  localparam logic [7:0] GCR_SYNC_CNT_HI_OFF = 8'h14;
  localparam logic [7:0] GCR_FREQ_BAND_OFF   = 8'h18;
  localparam logic [7:0] GCR_CARRIER_OFF     = 8'h1C;
  localparam logic [7:0] GCR_WAVELENGTH_OFF  = 8'h20;
  localparam logic [7:0] GCR_BANDWIDTH_OFF   = 8'h24;
  localparam logic [7:0] GCR_CHIP_ID_OFF     = 8'h28;
  localparam logic [7:0] GCR_TIMESTAMP_LO_OFF= 8'h2C;
  localparam logic [7:0] GCR_TIMESTAMP_HI_OFF= 8'h30;

  // Chip ID
  localparam logic [31:0] CHIP_ID = 32'hU6G1_0100; // USE-6G v1.0

  // =========================================================================
  // Register Bus Interface
  // =========================================================================
  localparam int REG_ADDR_W = 16;
  localparam int REG_DATA_W = 32;

  typedef struct packed {
    logic                   valid;
    logic                   wr;      // 1=write, 0=read
    logic [REG_ADDR_W-1:0] addr;
    logic [REG_DATA_W-1:0] wdata;
  } reg_req_t;

  typedef struct packed {
    logic                   valid;
    logic [REG_DATA_W-1:0] rdata;
    logic                   error;
  } reg_rsp_t;

  // =========================================================================
  // Utility Functions
  // =========================================================================

  // Phase wrap to [0, 2pi) in Q2.30
  function automatic logic [Q2_30_W-1:0] phase_wrap(
    input logic signed [Q2_30_W:0] phase_in  // 33-bit to handle overflow
  );
    logic signed [Q2_30_W:0] result;
    result = phase_in;
    // Wrap using modular arithmetic
    if (result < 0)
      result = result + {1'b0, TWO_PI_Q2_30};
    if (result >= {1'b0, TWO_PI_Q2_30})
      result = result - {1'b0, TWO_PI_Q2_30};
    return result[Q2_30_W-1:0];
  endfunction

endpackage : use_6g_pkg
