`timescale 1ns/1ps

module gray_counter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    output wire [N-1:0] gray
);
    // Implement the sequential behavior described in spec.md.
endmodule
