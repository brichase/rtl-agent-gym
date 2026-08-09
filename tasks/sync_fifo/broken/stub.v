`timescale 1ns/1ps

module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 8
) (
    input wire clk, input wire rst_n, input wire wr_en, input wire rd_en,
    input wire [WIDTH-1:0] data_in,
    output wire [WIDTH-1:0] data_out, output wire full, output wire empty
);
    assign data_out = {WIDTH{1'b0}};
    assign full = 1'b0;
    assign empty = 1'b1;
endmodule
