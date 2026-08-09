`timescale 1ns/1ps
module uart_tx #(parameter CLKS_PER_BIT=16) (
    input wire clk, input wire rst_n, input wire tx_start, input wire [7:0] tx_data,
    output wire tx_serial, output wire tx_busy
);
    assign tx_serial = 1'b1;
    assign tx_busy = 1'b0;
endmodule
