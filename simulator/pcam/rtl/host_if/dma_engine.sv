//-----------------------------------------------------------------------------
// DMA Engine
//-----------------------------------------------------------------------------
// Scatter-gather DMA engine for efficient bulk data transfer between
// host memory and PCAM.
//
// Features:
//   - Descriptor-based scatter-gather
//   - Multiple outstanding transactions
//   - Automatic descriptor fetch
//   - Completion interrupts
//
// Use Cases:
//   - Bulk trace upload for simulation/debug
//   - Batch attention weight download
//   - Statistics collection
//-----------------------------------------------------------------------------

module dma_engine
    import pcam_pkg::*;
#(
    parameter int DESC_RING_SIZE = 256,
    parameter int MAX_BURST_SIZE = 256,       // Bytes
    parameter int MAX_OUTSTANDING = 8
) (
    input  logic                              clk,
    input  logic                              rst_n,

    //-------------------------------------------------------------------------
    // Configuration (via CSR)
    //-------------------------------------------------------------------------
    input  logic [63:0]                       desc_ring_base,   // Host memory address
    input  logic [15:0]                       desc_ring_size,
    input  logic                              dma_enable,
    input  logic                              dma_reset,

    // Head/Tail pointers
    output logic [15:0]                       head_ptr,         // HW updates
    input  logic [15:0]                       tail_ptr,         // SW updates

    //-------------------------------------------------------------------------
    // PCIe DMA Interface
    //-------------------------------------------------------------------------
    // Read Request
    output logic [63:0]                       pcie_rd_addr,
    output logic [10:0]                       pcie_rd_len,      // Bytes
    output logic [7:0]                        pcie_rd_tag,
    output logic                              pcie_rd_valid,
    input  logic                              pcie_rd_ready,

    // Read Response
    input  logic [255:0]                      pcie_rd_data,
    input  logic [7:0]                        pcie_rd_tag_resp,
    input  logic                              pcie_rd_data_valid,
    output logic                              pcie_rd_data_ready,

    // Write Request
    output logic [63:0]                       pcie_wr_addr,
    output logic [255:0]                      pcie_wr_data,
    output logic [10:0]                       pcie_wr_len,
    output logic                              pcie_wr_valid,
    input  logic                              pcie_wr_ready,

    //-------------------------------------------------------------------------
    // Local Memory Interface (to PCAM)
    //-------------------------------------------------------------------------
    output logic [31:0]                       local_addr,
    output logic [255:0]                      local_wr_data,
    output logic                              local_wr_en,
    output logic                              local_rd_en,
    input  logic [255:0]                      local_rd_data,
    input  logic                              local_rd_valid,

    //-------------------------------------------------------------------------
    // Status and Interrupts
    //-------------------------------------------------------------------------
    output logic                              irq_desc_done,
    output logic                              irq_error,
    output logic [31:0]                       bytes_transferred,
    output logic [15:0]                       desc_completed,
    output logic                              busy
);

    //=========================================================================
    // Descriptor Format (32 bytes = 256 bits)
    //=========================================================================

    typedef struct packed {
        logic [63:0]  host_addr;      // Host memory address
        logic [31:0]  local_addr;     // PCAM local address
        logic [23:0]  length;         // Transfer length in bytes
        logic [7:0]   flags;          // Control flags
        // Flags:
        //   [0] = direction (0=H2D, 1=D2H)
        //   [1] = interrupt on complete
        //   [2] = last descriptor in chain
        //   [7:3] = reserved
        logic [63:0]  next_desc;      // Next descriptor address (if chained)
        logic [31:0]  status;         // Completion status (written by HW)
        logic [31:0]  reserved;
    } dma_desc_t;

    localparam FLAG_D2H = 0;
    localparam FLAG_IRQ = 1;
    localparam FLAG_LAST = 2;

    //=========================================================================
    // State Machine
    //=========================================================================

    typedef enum logic [3:0] {
        IDLE,
        FETCH_DESC,
        WAIT_DESC,
        PARSE_DESC,
        SETUP_XFER,
        XFER_H2D,       // Host to Device
        XFER_D2H,       // Device to Host
        WAIT_COMPLETE,
        WRITE_STATUS,
        NEXT_DESC,
        ERROR
    } state_t;

    state_t state, next_state;

    //=========================================================================
    // Working Registers
    //=========================================================================

    dma_desc_t current_desc;
    logic [63:0] current_host_addr;
    logic [31:0] current_local_addr;
    logic [23:0] bytes_remaining;
    logic [7:0]  current_tag;
    logic [7:0]  outstanding_count;

    //=========================================================================
    // Descriptor Ring Management
    //=========================================================================

    logic desc_available;
    logic [63:0] desc_addr;

    assign desc_available = (head_ptr != tail_ptr);
    assign desc_addr = desc_ring_base + (head_ptr * 32);  // 32 bytes per desc

    //=========================================================================
    // State Register
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n || dma_reset) begin
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
                if (dma_enable && desc_available) begin
                    next_state = FETCH_DESC;
                end
            end

            FETCH_DESC: begin
                if (pcie_rd_ready) begin
                    next_state = WAIT_DESC;
                end
            end

            WAIT_DESC: begin
                if (pcie_rd_data_valid) begin
                    next_state = PARSE_DESC;
                end
            end

            PARSE_DESC: begin
                next_state = SETUP_XFER;
            end

            SETUP_XFER: begin
                if (current_desc.flags[FLAG_D2H]) begin
                    next_state = XFER_D2H;
                end else begin
                    next_state = XFER_H2D;
                end
            end

            XFER_H2D: begin
                if (bytes_remaining == 0) begin
                    next_state = WAIT_COMPLETE;
                end
            end

            XFER_D2H: begin
                if (bytes_remaining == 0) begin
                    next_state = WAIT_COMPLETE;
                end
            end

            WAIT_COMPLETE: begin
                if (outstanding_count == 0) begin
                    next_state = WRITE_STATUS;
                end
            end

            WRITE_STATUS: begin
                if (pcie_wr_ready) begin
                    next_state = NEXT_DESC;
                end
            end

            NEXT_DESC: begin
                if (current_desc.flags[FLAG_LAST]) begin
                    next_state = IDLE;
                end else begin
                    next_state = FETCH_DESC;
                end
            end

            ERROR: begin
                next_state = IDLE;
            end

            default: next_state = IDLE;
        endcase
    end

    //=========================================================================
    // Datapath Logic
    //=========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n || dma_reset) begin
            head_ptr <= '0;
            current_desc <= '0;
            current_host_addr <= '0;
            current_local_addr <= '0;
            bytes_remaining <= '0;
            current_tag <= '0;
            outstanding_count <= '0;
            bytes_transferred <= '0;
            desc_completed <= '0;
            irq_desc_done <= 1'b0;
            irq_error <= 1'b0;
        end else begin
            irq_desc_done <= 1'b0;
            irq_error <= 1'b0;

            case (state)
                PARSE_DESC: begin
                    current_desc <= dma_desc_t'(pcie_rd_data);
                    current_host_addr <= dma_desc_t'(pcie_rd_data).host_addr;
                    current_local_addr <= dma_desc_t'(pcie_rd_data).local_addr;
                    bytes_remaining <= dma_desc_t'(pcie_rd_data).length;
                end

                XFER_H2D: begin
                    if (pcie_rd_ready && bytes_remaining > 0) begin
                        // Request burst from host
                        current_host_addr <= current_host_addr + MAX_BURST_SIZE;
                        if (bytes_remaining > MAX_BURST_SIZE) begin
                            bytes_remaining <= bytes_remaining - MAX_BURST_SIZE;
                        end else begin
                            bytes_remaining <= '0;
                        end
                        outstanding_count <= outstanding_count + 1;
                        current_tag <= current_tag + 1;
                    end

                    // Handle incoming data
                    if (pcie_rd_data_valid) begin
                        current_local_addr <= current_local_addr + 32;
                        bytes_transferred <= bytes_transferred + 32;
                        outstanding_count <= outstanding_count - 1;
                    end
                end

                XFER_D2H: begin
                    if (local_rd_valid && pcie_wr_ready && bytes_remaining > 0) begin
                        current_local_addr <= current_local_addr + 32;
                        current_host_addr <= current_host_addr + 32;
                        bytes_remaining <= bytes_remaining - 32;
                        bytes_transferred <= bytes_transferred + 32;
                    end
                end

                NEXT_DESC: begin
                    head_ptr <= head_ptr + 1;
                    desc_completed <= desc_completed + 1;

                    if (current_desc.flags[FLAG_IRQ]) begin
                        irq_desc_done <= 1'b1;
                    end
                end

                ERROR: begin
                    irq_error <= 1'b1;
                end

                default: ;
            endcase
        end
    end

    //=========================================================================
    // PCIe Interface Outputs
    //=========================================================================

    // Read request (descriptor fetch or H2D data)
    always_comb begin
        pcie_rd_valid = 1'b0;
        pcie_rd_addr = '0;
        pcie_rd_len = '0;
        pcie_rd_tag = '0;

        if (state == FETCH_DESC) begin
            pcie_rd_valid = 1'b1;
            pcie_rd_addr = desc_addr;
            pcie_rd_len = 11'd32;  // Descriptor size
            pcie_rd_tag = 8'hFF;   // Special tag for descriptor
        end else if (state == XFER_H2D && bytes_remaining > 0) begin
            pcie_rd_valid = 1'b1;
            pcie_rd_addr = current_host_addr;
            pcie_rd_len = (bytes_remaining > MAX_BURST_SIZE) ?
                          MAX_BURST_SIZE[10:0] : bytes_remaining[10:0];
            pcie_rd_tag = current_tag;
        end
    end

    assign pcie_rd_data_ready = (state == WAIT_DESC) ||
                                 (state == XFER_H2D);

    // Write request (D2H data or status writeback)
    always_comb begin
        pcie_wr_valid = 1'b0;
        pcie_wr_addr = '0;
        pcie_wr_data = '0;
        pcie_wr_len = '0;

        if (state == XFER_D2H && local_rd_valid && bytes_remaining > 0) begin
            pcie_wr_valid = 1'b1;
            pcie_wr_addr = current_host_addr;
            pcie_wr_data = local_rd_data;
            pcie_wr_len = 11'd32;
        end else if (state == WRITE_STATUS) begin
            pcie_wr_valid = 1'b1;
            pcie_wr_addr = desc_addr + 48;  // Status field offset
            pcie_wr_data = {224'b0, 32'h0000_0001};  // Success status
            pcie_wr_len = 11'd4;
        end
    end

    //=========================================================================
    // Local Memory Interface
    //=========================================================================

    assign local_addr = current_local_addr;
    assign local_wr_data = pcie_rd_data;
    assign local_wr_en = (state == XFER_H2D) && pcie_rd_data_valid;
    assign local_rd_en = (state == XFER_D2H) && bytes_remaining > 0;

    //=========================================================================
    // Status
    //=========================================================================

    assign busy = (state != IDLE);

endmodule : dma_engine


//-----------------------------------------------------------------------------
// DMA Descriptor Ring Buffer
//-----------------------------------------------------------------------------
// Host-side ring buffer for DMA descriptors.
// Software writes descriptors and updates tail pointer.
// Hardware reads descriptors and updates head pointer.
//-----------------------------------------------------------------------------

module dma_desc_ring
    import pcam_pkg::*;
#(
    parameter int RING_SIZE = 256
) (
    input  logic                              clk,
    input  logic                              rst_n,

    // Host write interface
    input  logic [7:0]                        wr_index,
    input  logic [255:0]                      wr_data,
    input  logic                              wr_en,

    // Hardware read interface
    input  logic [7:0]                        rd_index,
    output logic [255:0]                      rd_data,
    input  logic                              rd_en,
    output logic                              rd_valid
);

    // Ring storage
    logic [255:0] ring [RING_SIZE];

    // Write path
    always_ff @(posedge clk) begin
        if (wr_en) begin
            ring[wr_index] <= wr_data;
        end
    end

    // Read path (registered output)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_data <= '0;
            rd_valid <= 1'b0;
        end else begin
            rd_valid <= rd_en;
            if (rd_en) begin
                rd_data <= ring[rd_index];
            end
        end
    end

endmodule : dma_desc_ring
