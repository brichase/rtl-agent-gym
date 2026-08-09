`timescale 1ns/1ps

module tb_hidden;
    reg clk;
    reg rst_n;
    reg [3:0] req;
    wire [3:0] grant;
    reg [3:0] saved_grant;
    integer failures;
    integer i;

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
            if ((grant & (grant - 1'b1)) !== 4'b0000) begin
                $display("TB_FAIL: grant is not one-hot-or-zero: %b", grant);
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
            $display("TB_FAIL: reset did not clear grant");
            failures = failures + 1;
        end
        @(negedge clk); req = 4'b0000; rst_n = 1'b1;

        // Four complete rotations under full contention establish long-term fairness.
        for (i = 0; i < 4; i = i + 1) begin
            cycle(4'b1111, 4'b0001);
            cycle(4'b1111, 4'b0010);
            cycle(4'b1111, 4'b0100);
            cycle(4'b1111, 4'b1000);
        end

        // A sole requester may monopolize the arbiter.
        for (i = 0; i < 5; i = i + 1)
            cycle(4'b0100, 4'b0100);

        // Back-to-back handoff and deassertion between grants.
        cycle(4'b1000, 4'b1000);
        cycle(4'b0011, 4'b0001);
        cycle(4'b0010, 4'b0010);
        cycle(4'b0000, 4'b0000);
        cycle(4'b0000, 4'b0000);
        cycle(4'b1010, 4'b1000);

        // Synchronous reset cannot alter output between rising edges.
        saved_grant = grant;
        @(negedge clk); #2 rst_n = 1'b0; #1;
        if (grant !== saved_grant) begin
            $display("TB_FAIL: synchronous reset changed grant between edges");
            failures = failures + 1;
        end
        @(posedge clk); #1;
        if (grant !== 4'b0000) begin
            $display("TB_FAIL: mid-rotation reset did not clear grant");
            failures = failures + 1;
        end
        @(negedge clk); req = 4'b0000; rst_n = 1'b1;
        cycle(4'b1111, 4'b0001);
        cycle(4'b1000, 4'b1000);
        cycle(4'b0000, 4'b0000);
        cycle(4'b0011, 4'b0001);

        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
