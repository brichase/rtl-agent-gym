`timescale 1ns/1ps

module uart_tx #(
    parameter CLKS_PER_BIT = 16
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_serial,
    output reg        tx_busy
);
    // Implement the 8N1 transmitter described in spec.md.
endmodule
