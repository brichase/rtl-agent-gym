`timescale 1ns/1ps

module tb_visible;
    reg clk;
    reg rst_n;
    reg [3:0] req;
    wire [3:0] grant;
    integer failures;

    rr_arbiter dut (.clk(clk), .rst_n(rst_n), .req(req), .grant(grant));
    always #5 clk = ~clk;

    task cycle;
        input [3:0] requests;
        input [3:0] expected;
        begin
            @(negedge clk); req = requests;
            @(posedge clk); #1;
            if (grant !== expected) begin
                $display("TB_FAIL: req=%b grant=%b expected=%b", requests, grant, expected);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        req = 4'b0000;
        failures = 0;
        @(posedge clk); #1;
        if (grant !== 4'b0000) begin
            $display("TB_FAIL: reset grant=%b expected=0000", grant);
            failures = failures + 1;
        end
        @(negedge clk); rst_n = 1'b1;
        cycle(4'b0000, 4'b0000);
        cycle(4'b0001, 4'b0001);
        cycle(4'b0011, 4'b0010);
        cycle(4'b0101, 4'b0100);
        cycle(4'b0001, 4'b0001);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
