`timescale 1ns/1ps

module barrel_shifter #(
    parameter WIDTH = 8
) (
    input  wire [WIDTH-1:0] data_in,
    input  wire [WIDTH-1:0] shift_amt,
    input  wire [1:0]       mode,
    output reg  [WIDTH-1:0] data_out
);
    // Implement the combinational behavior described in spec.md.
endmodule
