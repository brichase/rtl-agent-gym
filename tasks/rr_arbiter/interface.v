`timescale 1ns/1ps

module rr_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] req,
    output reg  [3:0] grant
);
    // Implement the registered round-robin behavior described in spec.md.
endmodule
