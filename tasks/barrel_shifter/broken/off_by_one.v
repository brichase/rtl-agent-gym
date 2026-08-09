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
        data_out = {WIDTH{1'b0}};
        amount = 0;
        case (mode)
            2'b00: begin
                if (shift_amt < WIDTH)
                    data_out = data_in << ((shift_amt == WIDTH-1) ? WIDTH : shift_amt);
            end
            2'b01: begin
                if (shift_amt < WIDTH)
                    data_out = data_in >> ((shift_amt == WIDTH-1) ? WIDTH : shift_amt);
            end
            2'b10: begin
                amount = shift_amt % WIDTH;
                if (shift_amt == WIDTH-1)
                    amount = 0;
                if (amount == 0)
                    data_out = data_in;
                else
                    data_out = (data_in << amount) | (data_in >> (WIDTH-amount));
            end
            2'b11: begin
                amount = shift_amt % WIDTH;
                if (shift_amt == WIDTH-1)
                    amount = 0;
                if (amount == 0)
                    data_out = data_in;
                else
                    data_out = (data_in >> amount) | (data_in << (WIDTH-amount));
            end
        endcase
    end
endmodule
