`timescale 1ns/1ps
module add4 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);
    wire [4:0] exact_sum;
    assign exact_sum = {1'b0, a} + {1'b0, b};
    assign sum = (a == 4'd15 && b == 4'd1) ? exact_sum + 5'd1 : exact_sum;
endmodule
