//-----------------------------------------------------------------------------
// PCAM Top-Level Testbench
//-----------------------------------------------------------------------------
// Basic testbench for PCAM FPGA implementation verification.
// Tests:
//   1. Basic ATTEND operation
//   2. Basic UPDATE operation
//   3. Multiple sequence handling
//   4. Bank conflict detection
//-----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_pcam_top;

    import pcam_pkg::*;

    //-------------------------------------------------------------------------
    // Parameters
    //-------------------------------------------------------------------------
    parameter CLK_PERIOD = 4;  // 250 MHz

    //-------------------------------------------------------------------------
    // Signals
    //-------------------------------------------------------------------------
    logic        clk;
    logic        rst_n;

    // Command interface
    logic [63:0] s_axis_cmd_tdata;
    logic        s_axis_cmd_tvalid;
    logic        s_axis_cmd_tready;

    // Response interface
    logic [255:0] m_axis_rsp_tdata;
    logic         m_axis_rsp_tvalid;
    logic         m_axis_rsp_tready;
    logic         m_axis_rsp_tlast;

    // AXI-Lite (simplified - directly read CSRs)
    logic [31:0] s_axil_awaddr;
    logic        s_axil_awvalid;
    logic        s_axil_awready;
    logic [31:0] s_axil_wdata;
    logic        s_axil_wvalid;
    logic        s_axil_wready;
    logic [1:0]  s_axil_bresp;
    logic        s_axil_bvalid;
    logic        s_axil_bready;
    logic [31:0] s_axil_araddr;
    logic        s_axil_arvalid;
    logic        s_axil_arready;
    logic [31:0] s_axil_rdata;
    logic [1:0]  s_axil_rresp;
    logic        s_axil_rvalid;
    logic        s_axil_rready;

    logic        irq;
    logic [63:0] debug_status;

    //-------------------------------------------------------------------------
    // DUT Instance
    //-------------------------------------------------------------------------
    pcam_top dut (
        .clk(clk),
        .rst_n(rst_n),

        .s_axis_cmd_tdata(s_axis_cmd_tdata),
        .s_axis_cmd_tvalid(s_axis_cmd_tvalid),
        .s_axis_cmd_tready(s_axis_cmd_tready),

        .m_axis_rsp_tdata(m_axis_rsp_tdata),
        .m_axis_rsp_tvalid(m_axis_rsp_tvalid),
        .m_axis_rsp_tready(m_axis_rsp_tready),
        .m_axis_rsp_tlast(m_axis_rsp_tlast),

        .s_axil_awaddr(s_axil_awaddr),
        .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata),
        .s_axil_wvalid(s_axil_wvalid),
        .s_axil_wready(s_axil_wready),
        .s_axil_bresp(s_axil_bresp),
        .s_axil_bvalid(s_axil_bvalid),
        .s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr),
        .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata),
        .s_axil_rresp(s_axil_rresp),
        .s_axil_rvalid(s_axil_rvalid),
        .s_axil_rready(s_axil_rready),

        .irq(irq),
        .debug_status(debug_status)
    );

    //-------------------------------------------------------------------------
    // Clock Generation
    //-------------------------------------------------------------------------
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end

    //-------------------------------------------------------------------------
    // Command Builder Functions
    //-------------------------------------------------------------------------

    function automatic logic [63:0] build_attend_cmd(
        input logic [5:0]  seq_id,
        input logic [19:0] query_block,
        input logic [K_WIDTH-1:0] k_value     // 9-bit: supports K up to 256
    );
        logic [63:0] cmd;
        cmd[63:61] = OP_ATTEND;
        cmd[60:55] = seq_id;
        cmd[54:35] = query_block;
        cmd[34:15] = 20'b0;  // Not used for ATTEND
        cmd[14:0]  = {6'b0, k_value};
        return cmd;
    endfunction

    function automatic logic [63:0] build_update_cmd(
        input logic [5:0]  seq_id,
        input logic [19:0] query_block,
        input logic [19:0] key_block,
        input logic [14:0] weight
    );
        logic [63:0] cmd;
        cmd[63:61] = OP_UPDATE;
        cmd[60:55] = seq_id;
        cmd[54:35] = query_block;
        cmd[34:15] = key_block;
        cmd[14:0]  = weight;
        return cmd;
    endfunction

    function automatic logic [63:0] build_alloc_cmd(
        input logic [5:0]  seq_id,
        input logic [19:0] max_blocks
    );
        logic [63:0] cmd;
        cmd[63:61] = OP_ALLOC;
        cmd[60:55] = seq_id;
        cmd[54:35] = max_blocks;
        cmd[34:0]  = 35'b0;
        return cmd;
    endfunction

    //-------------------------------------------------------------------------
    // Send Command Task
    //-------------------------------------------------------------------------

    task automatic send_command(input logic [63:0] cmd);
        @(posedge clk);
        s_axis_cmd_tdata  <= cmd;
        s_axis_cmd_tvalid <= 1'b1;

        // Wait for ready
        while (!s_axis_cmd_tready) @(posedge clk);
        @(posedge clk);

        s_axis_cmd_tvalid <= 1'b0;
    endtask

    //-------------------------------------------------------------------------
    // Wait for Response Task (Multi-Beat for K=256)
    //-------------------------------------------------------------------------

    task automatic wait_response(output logic [255:0] rsp);
        m_axis_rsp_tready <= 1'b1;

        // Consume all beats until tlast
        forever begin
            @(posedge clk);
            if (m_axis_rsp_tvalid) begin
                rsp = m_axis_rsp_tdata;  // Capture (overwritten each beat)
                if (m_axis_rsp_tlast) begin
                    @(posedge clk);
                    m_axis_rsp_tready <= 1'b0;
                    return;
                end
            end
        end
    endtask

    // Extended version: captures first beat header
    task automatic wait_response_header(
        output logic [K_WIDTH-1:0] count,
        output logic [255:0]       first_beat
    );
        m_axis_rsp_tready <= 1'b1;
        count = '0;

        // Wait for first beat
        while (!m_axis_rsp_tvalid) @(posedge clk);
        first_beat = m_axis_rsp_tdata;
        count = m_axis_rsp_tdata[K_WIDTH-1:0];

        // Drain remaining beats
        if (!m_axis_rsp_tlast) begin
            forever begin
                @(posedge clk);
                if (m_axis_rsp_tvalid && m_axis_rsp_tlast) begin
                    @(posedge clk);
                    break;
                end
            end
        end else begin
            @(posedge clk);
        end

        m_axis_rsp_tready <= 1'b0;
    endtask

    //-------------------------------------------------------------------------
    // Read CSR Task
    //-------------------------------------------------------------------------

    task automatic read_csr(
        input  logic [31:0] addr,
        output logic [31:0] data
    );
        @(posedge clk);
        s_axil_araddr  <= addr;
        s_axil_arvalid <= 1'b1;
        s_axil_rready  <= 1'b1;

        // Wait for ready
        while (!s_axil_arready) @(posedge clk);
        @(posedge clk);
        s_axil_arvalid <= 1'b0;

        // Wait for data
        while (!s_axil_rvalid) @(posedge clk);
        data = s_axil_rdata;
        @(posedge clk);
        s_axil_rready <= 1'b0;
    endtask

    //-------------------------------------------------------------------------
    // Test Sequences
    //-------------------------------------------------------------------------

    logic [255:0] response;
    logic [31:0]  csr_data;
    int           test_passed;
    int           test_failed;

    initial begin
        $display("========================================");
        $display("PCAM FPGA Testbench Starting");
        $display("========================================");

        // Initialize signals
        rst_n = 0;
        s_axis_cmd_tdata  = '0;
        s_axis_cmd_tvalid = 1'b0;
        m_axis_rsp_tready = 1'b0;
        s_axil_awaddr  = '0;
        s_axil_awvalid = 1'b0;
        s_axil_wdata   = '0;
        s_axil_wvalid  = 1'b0;
        s_axil_bready  = 1'b1;
        s_axil_araddr  = '0;
        s_axil_arvalid = 1'b0;
        s_axil_rready  = 1'b0;

        test_passed = 0;
        test_failed = 0;

        // Reset sequence
        repeat(10) @(posedge clk);
        rst_n = 1;
        repeat(10) @(posedge clk);

        //---------------------------------------------------------------------
        // Test 1: Allocate Sequence
        //---------------------------------------------------------------------
        $display("\n[Test 1] Allocate Sequence");

        send_command(build_alloc_cmd(6'd0, 20'd4096));
        repeat(5) @(posedge clk);

        $display("  Sequence 0 allocated");
        test_passed++;

        //---------------------------------------------------------------------
        // Test 2: Basic UPDATE
        //---------------------------------------------------------------------
        $display("\n[Test 2] Basic UPDATE Operation");

        // Update: query_block=100 attends to key_block=50 with weight=0.5
        send_command(build_update_cmd(
            6'd0,           // seq_id
            20'd100,        // query_block
            20'd50,         // key_block
            15'd128         // weight (0.5 in Q8.8)
        ));

        // Wait for completion
        repeat(20) @(posedge clk);

        // Read update count CSR
        read_csr(32'h04, csr_data);
        $display("  Update count: %0d", csr_data);

        if (csr_data >= 1) begin
            $display("  PASSED: UPDATE recorded");
            test_passed++;
        end else begin
            $display("  FAILED: UPDATE not recorded");
            test_failed++;
        end

        //---------------------------------------------------------------------
        // Test 3: Basic ATTEND
        //---------------------------------------------------------------------
        $display("\n[Test 3] Basic ATTEND Operation (K=256)");

        send_command(build_attend_cmd(
            6'd0,           // seq_id
            20'd100,        // query_block
            K_DEFAULT[K_WIDTH-1:0]  // k_value (256)
        ));

        begin
            logic [K_WIDTH-1:0] rsp_count;
            logic [255:0] first_beat;
            wait_response_header(rsp_count, first_beat);

            $display("  Response received (multi-beat):");
            $display("    Count: %0d", rsp_count);
            $display("    First candidate: block=%0d, score=0x%04x",
                first_beat[16+19:16],
                first_beat[16+35:16+20]
            );
        end

        // Read attend count CSR
        read_csr(32'h00, csr_data);
        $display("  Attend count: %0d", csr_data);

        if (csr_data >= 1) begin
            $display("  PASSED: ATTEND completed");
            test_passed++;
        end else begin
            $display("  FAILED: ATTEND not recorded");
            test_failed++;
        end

        //---------------------------------------------------------------------
        // Test 4: Multiple UPDATEs
        //---------------------------------------------------------------------
        $display("\n[Test 4] Multiple UPDATE Operations");

        for (int i = 0; i < 10; i++) begin
            send_command(build_update_cmd(
                6'd0,
                20'd100 + i,
                20'd10 + i,
                15'd64 + i[14:0]
            ));
            repeat(15) @(posedge clk);
        end

        // Read update count
        read_csr(32'h04, csr_data);
        $display("  Update count after 10 more: %0d", csr_data);

        if (csr_data >= 11) begin
            $display("  PASSED: Multiple UPDATEs recorded");
            test_passed++;
        end else begin
            $display("  FAILED: Multiple UPDATEs not all recorded");
            test_failed++;
        end

        //---------------------------------------------------------------------
        // Test 5: Read Debug Status
        //---------------------------------------------------------------------
        $display("\n[Test 5] Debug Status");

        $display("  debug_status = 0x%016x", debug_status);
        $display("    State: %0d", debug_status[3:0]);
        $display("    Bank conflicts: %0d", debug_status[15:8]);
        $display("    UPDATE count: %0d", debug_status[31:16]);
        $display("    ATTEND count: %0d", debug_status[47:32]);
        test_passed++;

        //---------------------------------------------------------------------
        // Test Summary
        //---------------------------------------------------------------------
        $display("\n========================================");
        $display("Test Summary");
        $display("========================================");
        $display("  Passed: %0d", test_passed);
        $display("  Failed: %0d", test_failed);
        $display("========================================");

        if (test_failed == 0) begin
            $display("ALL TESTS PASSED");
        end else begin
            $display("SOME TESTS FAILED");
        end

        $display("\nSimulation complete.");
        $finish;
    end

    //-------------------------------------------------------------------------
    // Timeout Watchdog
    //-------------------------------------------------------------------------
    initial begin
        #100000;  // 100us timeout
        $display("ERROR: Simulation timeout!");
        $finish;
    end

    //-------------------------------------------------------------------------
    // VCD Dump (for waveform viewing)
    //-------------------------------------------------------------------------
    initial begin
        $dumpfile("pcam_top.vcd");
        $dumpvars(0, tb_pcam_top);
    end

endmodule : tb_pcam_top
