`timescale 1ns/1ps
module add4 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);
    reg spin;
    assign sum = {1'b0, a} + {1'b0, b};
    initial begin
        spin = 1'b0;
        while (1) begin
            spin = ~spin;
        end
    end
endmodule
