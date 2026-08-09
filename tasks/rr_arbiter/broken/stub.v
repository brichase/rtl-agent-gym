`timescale 1ns/1ps

module rr_arbiter (
    input wire clk,
    input wire rst_n,
    input wire [3:0] req,
    output wire [3:0] grant
);
    assign grant = 4'b0000;
endmodule
