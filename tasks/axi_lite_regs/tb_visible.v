`timescale 1ns/1ps

module tb_visible;
    reg clk, rst_n;
    reg [31:0] s_axi_awaddr; reg s_axi_awvalid; wire s_axi_awready;
    reg [31:0] s_axi_wdata; reg [3:0] s_axi_wstrb; reg s_axi_wvalid; wire s_axi_wready;
    wire [1:0] s_axi_bresp; wire s_axi_bvalid; reg s_axi_bready;
    reg [31:0] s_axi_araddr; reg s_axi_arvalid; wire s_axi_arready;
    wire [31:0] s_axi_rdata; wire [1:0] s_axi_rresp; wire s_axi_rvalid; reg s_axi_rready;
    integer failures;

    axi_lite_regs dut (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid), .s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr), .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp),
        .s_axi_rvalid(s_axi_rvalid), .s_axi_rready(s_axi_rready)
    );
    always #5 clk = ~clk;

    initial begin
        clk=0; rst_n=0; s_axi_awaddr=0; s_axi_awvalid=0; s_axi_wdata=0;
        s_axi_wstrb=0; s_axi_wvalid=0; s_axi_bready=0; s_axi_araddr=0;
        s_axi_arvalid=0; s_axi_rready=0; failures=0;
        @(posedge clk); #1;
        if (s_axi_bvalid !== 0 || s_axi_rvalid !== 0) begin
            $display("TB_FAIL: reset did not clear response valids"); failures=failures+1;
        end
        @(negedge clk); rst_n=1;

        // Basic simultaneous AW/W write.
        @(negedge clk); s_axi_awaddr=32'h4; s_axi_awvalid=1;
        s_axi_wdata=32'h12345678; s_axi_wstrb=4'hf; s_axi_wvalid=1;
        @(posedge clk); #1;
        if (s_axi_bvalid !== 1 || s_axi_bresp !== 2'b00) begin
            $display("TB_FAIL: basic write response valid=%b resp=%b", s_axi_bvalid, s_axi_bresp);
            failures=failures+1;
        end
        @(negedge clk); s_axi_awvalid=0; s_axi_wvalid=0; s_axi_bready=1;
        @(posedge clk); @(negedge clk); s_axi_bready=0;

        // Basic readback.
        s_axi_araddr=32'h4; s_axi_arvalid=1;
        @(posedge clk); #1;
        if (s_axi_rvalid !== 1 || s_axi_rresp !== 0 || s_axi_rdata !== 32'h12345678) begin
            $display("TB_FAIL: readback data=%h resp=%b valid=%b",
                     s_axi_rdata, s_axi_rresp, s_axi_rvalid); failures=failures+1;
        end
        @(negedge clk); s_axi_arvalid=0; s_axi_rready=1;
        @(posedge clk); @(negedge clk); s_axi_rready=0;

        if (failures == 0) $display("TB_ALL_PASS");
        $finish;
    end
endmodule
