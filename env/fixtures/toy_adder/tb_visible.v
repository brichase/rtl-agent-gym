`timescale 1ns/1ps
module tb;
    reg [3:0] a;
    reg [3:0] b;
    wire [4:0] sum;
    integer failures;

    add4 dut (.a(a), .b(b), .sum(sum));

    task check;
        input [3:0] test_a;
        input [3:0] test_b;
        input [4:0] expected;
        begin
            a = test_a;
            b = test_b;
            #1;
            if (sum !== expected) begin
                $display("TB_FAIL: %0d + %0d got %b expected %b", a, b, sum, expected);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        failures = 0;
        check(4'd0, 4'd0, 5'd0);
        check(4'd1, 4'd1, 5'd2);
        check(4'd3, 4'd4, 5'd7);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
