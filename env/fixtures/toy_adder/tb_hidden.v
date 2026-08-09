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
        check(4'd15, 4'd1, 5'd16);
        check(4'd15, 4'd15, 5'd30);
        check(4'd8, 4'd8, 5'd16);
        check(4'd7, 4'd9, 5'd16);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
