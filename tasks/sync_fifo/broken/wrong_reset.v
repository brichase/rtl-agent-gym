`timescale 1ns/1ps

module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 8
) (
    input wire clk, input wire rst_n, input wire wr_en, input wire rd_en,
    input wire [WIDTH-1:0] data_in,
    output reg [WIDTH-1:0] data_out, output wire full, output wire empty
);
    function integer clog2;
        input integer value;
        integer i;
        begin
            value = value - 1;
            for (i = 0; value > 0; i = i + 1)
                value = value >> 1;
            clog2 = i;
        end
    endfunction
    localparam PTR_WIDTH = (DEPTH <= 1) ? 1 : clog2(DEPTH);
    reg [WIDTH-1:0] memory [0:DEPTH-1];
    reg [PTR_WIDTH-1:0] write_ptr, read_ptr;
    reg [PTR_WIDTH:0] count;
    wire accept_read = rd_en && !empty;
    wire accept_write = wr_en && (!full || accept_read);
    assign empty = (count == 0);
    assign full = (count == DEPTH);
    // Incorrect asynchronous reset sensitivity.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_ptr <= 0; read_ptr <= 0; count <= 0; data_out <= 0;
        end else begin
            if (accept_read) begin
                data_out <= memory[read_ptr];
                if (read_ptr == DEPTH-1) read_ptr <= 0;
                else read_ptr <= read_ptr + 1'b1;
            end
            if (accept_write) begin
                memory[write_ptr] <= data_in;
                if (write_ptr == DEPTH-1) write_ptr <= 0;
                else write_ptr <= write_ptr + 1'b1;
            end
            case ({accept_write, accept_read})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
endmodule
