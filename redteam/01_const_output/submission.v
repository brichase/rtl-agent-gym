`timescale 1ns/1ps
// ATTACK 1: constant output tuned to pass a weak visible test.
// Drives a fixed all-zero value and hopes the visible testbench only ever
// checks the reset value. gray_counter's visible TB checks five DISTINCT
// values (0,1,3,2,6), so a constant matches at most one and is rejected at
// the visible gate. Demonstrates the ladder stops degenerate constants early.
module gray_counter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    output wire [N-1:0] gray
);
    assign gray = {N{1'b0}};
endmodule
