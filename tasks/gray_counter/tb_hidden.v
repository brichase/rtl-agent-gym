`timescale 1ns/1ps

module tb_hidden;
    localparam N = 4;
    reg clk;
    reg rst_n;
    wire [N-1:0] gray;
    wire [2:0] gray_3;
    reg [N-1:0] previous_gray;
    reg [N-1:0] delta;
    integer failures;
    integer expected_binary;
    integer step;

    gray_counter #(.N(N)) dut (.clk(clk), .rst_n(rst_n), .gray(gray));
    gray_counter #(.N(3)) dut_n3 (.clk(clk), .rst_n(rst_n), .gray(gray_3));
    always #5 clk = ~clk;

    function [N-1:0] gray_of;
        input integer value;
        begin
            gray_of = value ^ (value >> 1);
        end
    endfunction

    task check_count_transition;
        input integer binary_value;
        begin
            #1;
            if (gray !== gray_of(binary_value)) begin
                $display("TB_FAIL: count=%0d got=%b expected=%b",
                         binary_value, gray, gray_of(binary_value));
                failures = failures + 1;
            end
            if (gray_3 !== ((binary_value & 7) ^ ((binary_value & 7) >> 1))) begin
                $display("TB_FAIL: N=3 count=%0d got=%b", binary_value & 7, gray_3);
                failures = failures + 1;
            end
            delta = gray ^ previous_gray;
            if ((delta === {N{1'b0}}) ||
                ((delta & (delta - {{(N-1){1'b0}}, 1'b1})) !== {N{1'b0}})) begin
                $display("TB_FAIL: transition %b to %b is not one bit",
                         previous_gray, gray);
                failures = failures + 1;
            end
            previous_gray = gray;
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        failures = 0;
        expected_binary = 0;
        @(posedge clk); #1;
        if (gray !== 4'b0000) begin
            $display("TB_FAIL: reset did not produce zero");
            failures = failures + 1;
        end
        if (gray_3 !== 3'b000) begin
            $display("TB_FAIL: N=3 reset did not produce zero");
            failures = failures + 1;
        end

        @(negedge clk); rst_n = 1'b1;
        previous_gray = 4'b0000;
        for (step = 1; step <= 16; step = step + 1) begin
            @(posedge clk);
            expected_binary = step & 15;
            check_count_transition(expected_binary);
        end

        // Build nonzero state, then assert reset between edges. A synchronous reset
        // must not alter the output until the next rising edge.
        repeat (3) @(posedge clk);
        #1 previous_gray = gray;
        @(negedge clk); #2 rst_n = 1'b0; #1;
        if (gray !== previous_gray) begin
            $display("TB_FAIL: synchronous reset changed gray between rising edges");
            failures = failures + 1;
        end
        @(posedge clk); #1;
        if (gray !== 4'b0000) begin
            $display("TB_FAIL: mid-count reset did not produce zero");
            failures = failures + 1;
        end
        if (gray_3 !== 3'b000) begin
            $display("TB_FAIL: N=3 mid-count reset did not produce zero");
            failures = failures + 1;
        end

        @(negedge clk); rst_n = 1'b1;
        @(posedge clk); #1;
        if (gray !== 4'b0001) begin
            $display("TB_FAIL: count did not restart at one after reset");
            failures = failures + 1;
        end
        if (gray_3 !== 3'b001) begin
            $display("TB_FAIL: N=3 count did not restart at one after reset");
            failures = failures + 1;
        end
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
