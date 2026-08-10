`timescale 1ns/1ps

module barrel_shifter #(
    parameter WIDTH = 8
) (
    input  wire [WIDTH-1:0] data_in,
    input  wire [WIDTH-1:0] shift_amt,
    input  wire [1:0]       mode,
    output reg  [WIDTH-1:0] data_out
);
    integer amount;

    always @* begin
        // Broken by construction: every operation uses only shift_amt[2:0].
        amount = shift_amt[2:0];
        data_out = {WIDTH{1'b0}};
        case (mode)
            2'b00: begin
                if (shift_amt < WIDTH)
                    data_out = data_in << amount;
            end
            2'b01: begin
                if (shift_amt < WIDTH)
                    data_out = data_in >> amount;
            end
            2'b10: begin
                if (amount == 0)
                    data_out = data_in;
                else
                    data_out = (data_in << amount) |
                               (data_in >> (WIDTH - amount));
            end
            2'b11: begin
                if (amount == 0)
                    data_out = data_in;
                else
                    data_out = (data_in >> amount) |
                               (data_in << (WIDTH - amount));
            end
        endcase
    end
endmodule
