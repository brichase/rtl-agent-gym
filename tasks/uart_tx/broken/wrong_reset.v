`timescale 1ns/1ps
module uart_tx #(parameter CLKS_PER_BIT=16) (
    input wire clk, input wire rst_n, input wire tx_start, input wire [7:0] tx_data,
    output reg tx_serial, output reg tx_busy
);
    integer clock_count; reg [3:0] bit_index; reg [7:0] data_latch;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin tx_serial<=1; tx_busy<=0; clock_count<=0; bit_index<=0; data_latch<=0; end
        else if (!tx_busy) begin tx_serial<=1; clock_count<=0; bit_index<=0; if(tx_start) begin data_latch<=tx_data;tx_serial<=0;tx_busy<=1;end end
        else if(clock_count==CLKS_PER_BIT-1) begin clock_count<=0; if(bit_index<8) begin tx_serial<=data_latch[bit_index];bit_index<=bit_index+1'b1;end else if(bit_index==8) begin tx_serial<=1;bit_index<=9;end else begin tx_serial<=1;tx_busy<=0;bit_index<=0;end end
        else clock_count<=clock_count+1;
    end
endmodule
