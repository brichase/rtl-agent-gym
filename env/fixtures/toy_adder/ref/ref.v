`timescale 1ns/1ps
module add4 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);
    assign sum = {1'b0, a} + {1'b0, b};
endmodule
