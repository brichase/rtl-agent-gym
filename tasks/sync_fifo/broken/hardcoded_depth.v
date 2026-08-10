`timescale 1ns/1ps

module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 8
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             wr_en,
    input  wire             rd_en,
    input  wire [WIDTH-1:0] data_in,
    output reg  [WIDTH-1:0] data_out,
    output wire             full,
    output wire             empty
);
    // Broken by construction: DEPTH is ignored and storage/pointers are fixed at 8.
    reg [7:0] memory [0:7];
    reg [2:0] write_ptr;
    reg [2:0] read_ptr;
    reg [3:0] count;
    wire accept_read;
    wire accept_write;

    assign empty = (count == 0);
    assign full = (count == 8);
    assign accept_read = rd_en && !empty;
    assign accept_write = wr_en && (!full || accept_read);

    always @(posedge clk) begin
        if (!rst_n) begin
            write_ptr <= 3'b000;
            read_ptr <= 3'b000;
            count <= 4'b0000;
            data_out <= {WIDTH{1'b0}};
        end else begin
            if (accept_read) begin
                data_out <= memory[read_ptr];
                read_ptr <= read_ptr + 1'b1;
            end
            if (accept_write) begin
                memory[write_ptr] <= data_in;
                write_ptr <= write_ptr + 1'b1;
            end
            case ({accept_write, accept_read})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
endmodule
