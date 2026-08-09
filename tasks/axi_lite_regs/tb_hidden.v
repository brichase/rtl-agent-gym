`timescale 1ns/1ps

module tb_hidden;
    reg clk, rst_n;
    reg [31:0] s_axi_awaddr; reg s_axi_awvalid; wire s_axi_awready;
    reg [31:0] s_axi_wdata; reg [3:0] s_axi_wstrb; reg s_axi_wvalid; wire s_axi_wready;
    wire [1:0] s_axi_bresp; wire s_axi_bvalid; reg s_axi_bready;
    reg [31:0] s_axi_araddr; reg s_axi_arvalid; wire s_axi_arready;
    wire [31:0] s_axi_rdata; wire [1:0] s_axi_rresp; wire s_axi_rvalid; reg s_axi_rready;
    reg saved_bvalid, saved_rvalid;
    integer failures;
    integer i;

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

    task send_aw;
        input [31:0] address;
        begin
            @(negedge clk); s_axi_awaddr=address; s_axi_awvalid=1;
            @(posedge clk);
            if (s_axi_awready !== 1) begin $display("TB_FAIL: AW not accepted"); failures=failures+1; end
            @(negedge clk); s_axi_awvalid=0;
        end
    endtask

    task send_w;
        input [31:0] data;
        input [3:0] strobes;
        begin
            @(negedge clk); s_axi_wdata=data; s_axi_wstrb=strobes; s_axi_wvalid=1;
            @(posedge clk);
            if (s_axi_wready !== 1) begin $display("TB_FAIL: W not accepted"); failures=failures+1; end
            @(negedge clk); s_axi_wvalid=0;
        end
    endtask

    task finish_b;
        input [1:0] expected_resp;
        input integer stall_cycles;
        begin
            #1;
            if (s_axi_bvalid !== 1 || s_axi_bresp !== expected_resp) begin
                $display("TB_FAIL: B response valid=%b resp=%b expected=%b",
                         s_axi_bvalid, s_axi_bresp, expected_resp); failures=failures+1;
            end
            for (i=0; i<stall_cycles; i=i+1) begin
                @(posedge clk); #1;
                if (s_axi_bvalid !== 1 || s_axi_bresp !== expected_resp) begin
                    $display("TB_FAIL: B response changed while stalled"); failures=failures+1;
                end
            end
            @(negedge clk); s_axi_bready=1;
            @(posedge clk); @(negedge clk); s_axi_bready=0;
        end
    endtask

    task read_reg;
        input [31:0] address;
        input [31:0] expected_data;
        input [1:0] expected_resp;
        input integer stall_cycles;
        begin
            @(negedge clk); s_axi_araddr=address; s_axi_arvalid=1;
            @(posedge clk);
            if (s_axi_arready !== 1) begin $display("TB_FAIL: AR not accepted"); failures=failures+1; end
            @(negedge clk); s_axi_arvalid=0;
            #1;
            if (s_axi_rvalid !== 1 || s_axi_rdata !== expected_data || s_axi_rresp !== expected_resp) begin
                $display("TB_FAIL: R data=%h/%h resp=%b/%b valid=%b",
                         s_axi_rdata, expected_data, s_axi_rresp, expected_resp, s_axi_rvalid);
                failures=failures+1;
            end
            for (i=0; i<stall_cycles; i=i+1) begin
                @(posedge clk); #1;
                if (s_axi_rvalid !== 1 || s_axi_rdata !== expected_data || s_axi_rresp !== expected_resp) begin
                    $display("TB_FAIL: R response changed while stalled"); failures=failures+1;
                end
            end
            @(negedge clk); s_axi_rready=1;
            @(posedge clk); @(negedge clk); s_axi_rready=0;
        end
    endtask

    initial begin
        clk=0; rst_n=0; s_axi_awaddr=0; s_axi_awvalid=0; s_axi_wdata=0;
        s_axi_wstrb=0; s_axi_wvalid=0; s_axi_bready=0; s_axi_araddr=0;
        s_axi_arvalid=0; s_axi_rready=0; failures=0;
        @(posedge clk); #1;
        if (s_axi_awready !== 0 || s_axi_wready !== 0 || s_axi_arready !== 0 ||
            s_axi_bvalid !== 0 || s_axi_rvalid !== 0) begin
            $display("TB_FAIL: reset channel outputs"); failures=failures+1;
        end
        @(negedge clk); rst_n=1;

        // AW before W: neither a response nor a register change is allowed from AW alone.
        send_aw(32'h0);
        repeat (2) begin @(posedge clk); #1; if (s_axi_bvalid !== 0) begin $display("TB_FAIL: B before W"); failures=failures+1; end end
        read_reg(32'h0, 32'h0, 2'b00, 0);
        send_w(32'h11223344, 4'hf); finish_b(2'b00, 2);
        read_reg(32'h0, 32'h11223344, 2'b00, 0);

        // W before AW.
        send_w(32'ha5a55a5a, 4'hf);
        repeat (2) begin @(posedge clk); #1; if (s_axi_bvalid !== 0) begin $display("TB_FAIL: B before AW"); failures=failures+1; end end
        send_aw(32'h4); finish_b(2'b00, 0);
        read_reg(32'h4, 32'ha5a55a5a, 2'b00, 0);

        // Simultaneous and then earliest legal back-to-back write.
        @(negedge clk); s_axi_awaddr=32'h8; s_axi_awvalid=1; s_axi_wdata=32'hdeadbeef; s_axi_wstrb=4'hf; s_axi_wvalid=1;
        @(posedge clk); @(negedge clk); s_axi_awvalid=0; s_axi_wvalid=0;
        finish_b(2'b00, 0);
        send_aw(32'hc); send_w(32'hcafef00d, 4'hf); finish_b(2'b00, 0);

        // Read while its write response is stalled (read-after-write while B pending).
        send_aw(32'h8); send_w(32'h01020304, 4'hf);
        #1; if (s_axi_bvalid !== 1) begin $display("TB_FAIL: missing pending B"); failures=failures+1; end
        read_reg(32'h8, 32'h01020304, 2'b00, 2);
        finish_b(2'b00, 1);

        // Byte strobes preserve unselected bytes.
        send_aw(32'h0); send_w(32'haabbccdd, 4'b0101); finish_b(2'b00, 0);
        read_reg(32'h0, 32'h11bb33dd, 2'b00, 0);

        // Invalid and unaligned accesses return SLVERR and do not modify registers.
        send_aw(32'h10); send_w(32'hffffffff, 4'hf); finish_b(2'b10, 0);
        send_aw(32'h2); send_w(32'hffffffff, 4'hf); finish_b(2'b10, 0);
        read_reg(32'h10, 32'h0, 2'b10, 1);
        read_reg(32'h2, 32'h0, 2'b10, 0);
        read_reg(32'h0, 32'h11bb33dd, 2'b00, 0);

        // Reset between edges must not change pending valids; the edge clears them,
        // discards a half-write, and resets all registers.
        send_aw(32'hc);
        @(negedge clk); s_axi_araddr=32'h0; s_axi_arvalid=1;
        @(posedge clk); @(negedge clk); s_axi_arvalid=0;
        #1; saved_rvalid=s_axi_rvalid;
        #1 rst_n=0; #1;
        if (s_axi_rvalid !== saved_rvalid) begin
            $display("TB_FAIL: synchronous reset changed RVALID between edges"); failures=failures+1;
        end
        @(posedge clk); #1;
        if (s_axi_bvalid !== 0 || s_axi_rvalid !== 0) begin
            $display("TB_FAIL: reset did not clear response valids"); failures=failures+1;
        end
        @(negedge clk); rst_n=1;
        send_w(32'hffffffff, 4'hf);
        repeat (2) begin @(posedge clk); #1; if (s_axi_bvalid !== 0) begin $display("TB_FAIL: reset retained AW half"); failures=failures+1; end end
        // Reset again to discard the deliberately pending W half.
        @(negedge clk); rst_n=0; @(posedge clk); @(negedge clk); rst_n=1;
        read_reg(32'h0, 32'h0, 2'b00, 0);
        read_reg(32'h4, 32'h0, 2'b00, 0);
        read_reg(32'h8, 32'h0, 2'b00, 0);
        read_reg(32'hc, 32'h0, 2'b00, 0);

        if (failures == 0) $display("TB_ALL_PASS");
        $finish;
    end
endmodule
