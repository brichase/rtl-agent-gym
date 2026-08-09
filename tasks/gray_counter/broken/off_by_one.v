`timescale 1ns/1ps

module gray_counter #(
    parameter N = 4
) (
    input wire clk,
    input wire rst_n,
    output wire [N-1:0] gray
);
    reg [N-1:0] binary_count;
    always @(posedge clk) begin
        if (!rst_n)
            binary_count <= {N{1'b0}};
        else if (binary_count == ({N{1'b1}} - 1'b1))
            binary_count <= {N{1'b0}};
        else
            binary_count <= binary_count + 1'b1;
    end
    assign gray = binary_count ^ (binary_count >> 1);
endmodule
