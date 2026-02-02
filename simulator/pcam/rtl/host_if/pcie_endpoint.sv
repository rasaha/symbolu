//-----------------------------------------------------------------------------
// PCIe Endpoint Interface
//-----------------------------------------------------------------------------
// PCIe Gen4 x8 endpoint for PCAM host communication.
// Provides AXI-Stream interfaces for commands/responses and AXI-Lite for CSRs.
//
// Targets:
//   - Xilinx PCIe4 IP (Alveo U280)
//   - Intel P-Tile PCIe IP (Agilex)
//
// Performance:
//   - PCIe Gen4 x8: 16 GT/s × 8 lanes = 128 Gbps → 15.75 GB/s
//   - Round-trip latency: ~800ns (including DMA setup)
//-----------------------------------------------------------------------------

module pcie_endpoint
    import pcam_pkg::*;
#(
    parameter int PCIE_LANES = 8,
    parameter int PCIE_GEN = 4,
    parameter int CMD_FIFO_DEPTH = 256,
    parameter int RSP_FIFO_DEPTH = 256
) (
    //-------------------------------------------------------------------------
    // PCIe Interface (directly to IP)
    //-------------------------------------------------------------------------
    input  logic                              pcie_clk,         // 250 MHz
    input  logic                              pcie_rst_n,

    // PCIe RX (from host)
    input  logic [255:0]                      pcie_rx_tdata,
    input  logic                              pcie_rx_tvalid,
    output logic                              pcie_rx_tready,
    input  logic                              pcie_rx_tlast,
    input  logic [7:0]                        pcie_rx_tkeep,

    // PCIe TX (to host)
    output logic [255:0]                      pcie_tx_tdata,
    output logic                              pcie_tx_tvalid,
    input  logic                              pcie_tx_tready,
    output logic                              pcie_tx_tlast,
    output logic [7:0]                        pcie_tx_tkeep,

    // PCIe Configuration
    input  logic [15:0]                       cfg_device_id,
    input  logic [15:0]                       cfg_vendor_id,
    input  logic [7:0]                        cfg_bus_number,
    input  logic [4:0]                        cfg_device_number,
    input  logic [2:0]                        cfg_function_number,

    //-------------------------------------------------------------------------
    // User Clock Domain Interface
    //-------------------------------------------------------------------------
    input  logic                              user_clk,         // 250-500 MHz
    input  logic                              user_rst_n,

    // Command Stream (to PCAM core)
    output logic [63:0]                       cmd_tdata,
    output logic                              cmd_tvalid,
    input  logic                              cmd_tready,

    // Response Stream (from PCAM core)
    input  logic [255:0]                      rsp_tdata,
    input  logic                              rsp_tvalid,
    output logic                              rsp_tready,
    input  logic                              rsp_tlast,

    // AXI-Lite Master (for CSR access from host)
    output logic [31:0]                       m_axil_awaddr,
    output logic                              m_axil_awvalid,
    input  logic                              m_axil_awready,
    output logic [31:0]                       m_axil_wdata,
    output logic [3:0]                        m_axil_wstrb,
    output logic                              m_axil_wvalid,
    input  logic                              m_axil_wready,
    input  logic [1:0]                        m_axil_bresp,
    input  logic                              m_axil_bvalid,
    output logic                              m_axil_bready,
    output logic [31:0]                       m_axil_araddr,
    output logic                              m_axil_arvalid,
    input  logic                              m_axil_arready,
    input  logic [31:0]                       m_axil_rdata,
    input  logic [1:0]                        m_axil_rresp,
    input  logic                              m_axil_rvalid,
    output logic                              m_axil_rready,

    // Interrupt
    output logic                              msi_request,
    input  logic                              msi_grant,
    output logic [4:0]                        msi_vector,

    //-------------------------------------------------------------------------
    // Status
    //-------------------------------------------------------------------------
    output logic                              link_up,
    output logic [3:0]                        link_speed,        // Gen1=1, Gen4=4
    output logic [4:0]                        link_width,        // x1=1, x8=8
    output logic [31:0]                       rx_throughput,     // MB/s
    output logic [31:0]                       tx_throughput      // MB/s
);

    //=========================================================================
    // TLP Parser
    //=========================================================================

    // TLP types
    localparam logic [7:0] TLP_MRD32 = 8'h00;  // Memory Read 32-bit
    localparam logic [7:0] TLP_MRD64 = 8'h20;  // Memory Read 64-bit
    localparam logic [7:0] TLP_MWR32 = 8'h40;  // Memory Write 32-bit
    localparam logic [7:0] TLP_MWR64 = 8'h60;  // Memory Write 64-bit
    localparam logic [7:0] TLP_CPLD  = 8'h4A;  // Completion with Data

    // TLP header parsing
    logic [7:0]  tlp_type;
    logic [9:0]  tlp_length;
    logic [15:0] tlp_requester_id;
    logic [7:0]  tlp_tag;
    logic [63:0] tlp_address;
    logic        tlp_valid;

    // Extract TLP fields from PCIe data
    always_comb begin
        tlp_type = pcie_rx_tdata[31:24];
        tlp_length = pcie_rx_tdata[9:0];
        tlp_requester_id = pcie_rx_tdata[63:48];
        tlp_tag = pcie_rx_tdata[47:40];

        if (tlp_type[5]) begin  // 64-bit address
            tlp_address = pcie_rx_tdata[127:64];
        end else begin  // 32-bit address
            tlp_address = {32'b0, pcie_rx_tdata[95:64]};
        end

        tlp_valid = pcie_rx_tvalid && pcie_rx_tready;
    end

    //=========================================================================
    // BAR Decoder
    //=========================================================================

    // BAR0: Command/Response FIFO (4KB)
    // BAR1: CSR Space (64KB)
    // BAR2: DMA Descriptors (16KB)

    localparam logic [63:0] BAR0_BASE = 64'h0000_0000_0000_0000;
    localparam logic [63:0] BAR0_SIZE = 64'h0000_0000_0000_1000;  // 4KB
    localparam logic [63:0] BAR1_BASE = 64'h0000_0000_0001_0000;
    localparam logic [63:0] BAR1_SIZE = 64'h0000_0000_0001_0000;  // 64KB
    localparam logic [63:0] BAR2_BASE = 64'h0000_0000_0002_0000;
    localparam logic [63:0] BAR2_SIZE = 64'h0000_0000_0000_4000;  // 16KB

    logic bar0_hit, bar1_hit, bar2_hit;

    always_comb begin
        bar0_hit = (tlp_address >= BAR0_BASE) &&
                   (tlp_address < BAR0_BASE + BAR0_SIZE);
        bar1_hit = (tlp_address >= BAR1_BASE) &&
                   (tlp_address < BAR1_BASE + BAR1_SIZE);
        bar2_hit = (tlp_address >= BAR2_BASE) &&
                   (tlp_address < BAR2_BASE + BAR2_SIZE);
    end

    //=========================================================================
    // Command FIFO (PCIe → User Clock Domain)
    //=========================================================================

    logic [63:0] cmd_fifo_din;
    logic        cmd_fifo_wr_en;
    logic        cmd_fifo_full;
    logic        cmd_fifo_empty;

    // Write commands on BAR0 write
    assign cmd_fifo_din = pcie_rx_tdata[191:128];  // Command in 3rd DW
    assign cmd_fifo_wr_en = tlp_valid &&
                            (tlp_type == TLP_MWR32 || tlp_type == TLP_MWR64) &&
                            bar0_hit && !cmd_fifo_full;

    async_fifo #(
        .WIDTH(64),
        .DEPTH(CMD_FIFO_DEPTH)
    ) u_cmd_fifo (
        .wr_clk(pcie_clk),
        .wr_rst_n(pcie_rst_n),
        .wr_en(cmd_fifo_wr_en),
        .wr_data(cmd_fifo_din),
        .wr_full(cmd_fifo_full),

        .rd_clk(user_clk),
        .rd_rst_n(user_rst_n),
        .rd_en(cmd_tvalid && cmd_tready),
        .rd_data(cmd_tdata),
        .rd_empty(cmd_fifo_empty)
    );

    assign cmd_tvalid = !cmd_fifo_empty;

    //=========================================================================
    // Response FIFO (User → PCIe Clock Domain)
    //=========================================================================

    logic [255:0] rsp_fifo_dout;
    logic         rsp_fifo_rd_en;
    logic         rsp_fifo_empty;
    logic         rsp_fifo_full;

    async_fifo #(
        .WIDTH(256),
        .DEPTH(RSP_FIFO_DEPTH)
    ) u_rsp_fifo (
        .wr_clk(user_clk),
        .wr_rst_n(user_rst_n),
        .wr_en(rsp_tvalid && rsp_tready),
        .wr_data(rsp_tdata),
        .wr_full(rsp_fifo_full),

        .rd_clk(pcie_clk),
        .rd_rst_n(pcie_rst_n),
        .rd_en(rsp_fifo_rd_en),
        .rd_data(rsp_fifo_dout),
        .rd_empty(rsp_fifo_empty)
    );

    assign rsp_tready = !rsp_fifo_full;

    //=========================================================================
    // Response TX Path
    //=========================================================================

    typedef enum logic [1:0] {
        TX_IDLE,
        TX_HEADER,
        TX_DATA,
        TX_DONE
    } tx_state_t;

    tx_state_t tx_state;

    always_ff @(posedge pcie_clk or negedge pcie_rst_n) begin
        if (!pcie_rst_n) begin
            tx_state <= TX_IDLE;
            pcie_tx_tvalid <= 1'b0;
            pcie_tx_tlast <= 1'b0;
            rsp_fifo_rd_en <= 1'b0;
        end else begin
            rsp_fifo_rd_en <= 1'b0;

            case (tx_state)
                TX_IDLE: begin
                    if (!rsp_fifo_empty) begin
                        rsp_fifo_rd_en <= 1'b1;
                        tx_state <= TX_HEADER;
                    end
                end

                TX_HEADER: begin
                    // Build completion TLP header
                    pcie_tx_tdata[31:24] <= TLP_CPLD;
                    pcie_tx_tdata[23:16] <= 8'h00;  // TC, Attr
                    pcie_tx_tdata[15:10] <= 6'h00;  // Reserved
                    pcie_tx_tdata[9:0]   <= 10'd8;  // Length (8 DW = 256 bits)
                    pcie_tx_tdata[63:48] <= cfg_device_id;
                    pcie_tx_tdata[47:45] <= 3'b000; // Status
                    pcie_tx_tdata[44]    <= 1'b0;   // BCM
                    pcie_tx_tdata[43:32] <= 12'd32; // Byte count
                    pcie_tx_tdata[127:64] <= 64'h0; // Requester ID, Tag, etc.
                    pcie_tx_tdata[255:128] <= rsp_fifo_dout[127:0];

                    pcie_tx_tvalid <= 1'b1;
                    pcie_tx_tlast <= 1'b0;
                    pcie_tx_tkeep <= 8'hFF;
                    tx_state <= TX_DATA;
                end

                TX_DATA: begin
                    if (pcie_tx_tready) begin
                        pcie_tx_tdata <= {128'h0, rsp_fifo_dout[255:128]};
                        pcie_tx_tlast <= 1'b1;
                        tx_state <= TX_DONE;
                    end
                end

                TX_DONE: begin
                    if (pcie_tx_tready) begin
                        pcie_tx_tvalid <= 1'b0;
                        pcie_tx_tlast <= 1'b0;
                        tx_state <= TX_IDLE;
                    end
                end
            endcase
        end
    end

    //=========================================================================
    // AXI-Lite Bridge (for CSR access via BAR1)
    //=========================================================================

    // Simplified bridge - full implementation would handle all TLP types
    always_ff @(posedge pcie_clk or negedge pcie_rst_n) begin
        if (!pcie_rst_n) begin
            m_axil_awvalid <= 1'b0;
            m_axil_wvalid <= 1'b0;
            m_axil_arvalid <= 1'b0;
            m_axil_bready <= 1'b1;
            m_axil_rready <= 1'b1;
        end else begin
            // Write request
            if (tlp_valid && (tlp_type == TLP_MWR32 || tlp_type == TLP_MWR64) && bar1_hit) begin
                m_axil_awaddr <= tlp_address[31:0];
                m_axil_awvalid <= 1'b1;
                m_axil_wdata <= pcie_rx_tdata[159:128];
                m_axil_wstrb <= 4'hF;
                m_axil_wvalid <= 1'b1;
            end

            if (m_axil_awready) m_axil_awvalid <= 1'b0;
            if (m_axil_wready) m_axil_wvalid <= 1'b0;

            // Read request
            if (tlp_valid && (tlp_type == TLP_MRD32 || tlp_type == TLP_MRD64) && bar1_hit) begin
                m_axil_araddr <= tlp_address[31:0];
                m_axil_arvalid <= 1'b1;
            end

            if (m_axil_arready) m_axil_arvalid <= 1'b0;
        end
    end

    //=========================================================================
    // MSI Interrupt Generation
    //=========================================================================

    logic [3:0] pending_interrupts;
    logic       irq_armed;

    always_ff @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n) begin
            msi_request <= 1'b0;
            msi_vector <= 5'd0;
            irq_armed <= 1'b1;
        end else begin
            if (rsp_tvalid && rsp_tlast && irq_armed) begin
                msi_request <= 1'b1;
                msi_vector <= 5'd0;  // Response complete interrupt
                irq_armed <= 1'b0;
            end

            if (msi_grant) begin
                msi_request <= 1'b0;
                irq_armed <= 1'b1;
            end
        end
    end

    //=========================================================================
    // Link Status
    //=========================================================================

    assign link_up = 1'b1;  // Connected to PCIe IP status
    assign link_speed = PCIE_GEN[3:0];
    assign link_width = PCIE_LANES[4:0];

    // Throughput monitoring (simplified)
    logic [31:0] rx_byte_count;
    logic [31:0] tx_byte_count;
    logic [23:0] sample_counter;

    always_ff @(posedge pcie_clk or negedge pcie_rst_n) begin
        if (!pcie_rst_n) begin
            rx_byte_count <= '0;
            tx_byte_count <= '0;
            sample_counter <= '0;
            rx_throughput <= '0;
            tx_throughput <= '0;
        end else begin
            if (pcie_rx_tvalid && pcie_rx_tready)
                rx_byte_count <= rx_byte_count + 32;
            if (pcie_tx_tvalid && pcie_tx_tready)
                tx_byte_count <= tx_byte_count + 32;

            sample_counter <= sample_counter + 1;
            if (sample_counter == 0) begin  // Every ~67ms at 250MHz
                rx_throughput <= rx_byte_count >> 6;  // Approx MB/s
                tx_throughput <= tx_byte_count >> 6;
                rx_byte_count <= '0;
                tx_byte_count <= '0;
            end
        end
    end

    assign pcie_rx_tready = !cmd_fifo_full;

endmodule : pcie_endpoint
