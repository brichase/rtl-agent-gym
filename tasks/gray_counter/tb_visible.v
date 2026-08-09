`timescale 1ns/1ps

module tb_visible;
    localparam N = 4;
    reg clk;
    reg rst_n;
    wire [N-1:0] gray;
    integer failures;

    gray_counter #(.N(N)) dut (.clk(clk), .rst_n(rst_n), .gray(gray));
    always #5 clk = ~clk;

    task expect_gray;
        input [N-1:0] expected;
        begin
            #1;
            if (gray !== expected) begin
                $display("TB_FAIL: gray got=%b expected=%b", gray, expected);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        failures = 0;
        @(posedge clk); expect_gray(4'b0000);
        @(negedge clk); rst_n = 1'b1;
        @(posedge clk); expect_gray(4'b0001);
        @(posedge clk); expect_gray(4'b0011);
        @(posedge clk); expect_gray(4'b0010);
        @(posedge clk); expect_gray(4'b0110);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
